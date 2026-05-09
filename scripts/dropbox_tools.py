import os
import io
import asyncio
import aiohttp
import json

import pandas as pd
from os import listdir
import argparse

from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.exceptions import AuthError, ApiError
from dropbox.files import CommitInfo, WriteMode, UploadSessionCursor
import dropbox
from tqdm import tqdm

RUNPOD_POD_ID = None
LOCAL_FOLDER_PATH = '/workspace/projects'
LOCAL_RENDERED_FOLDER_PATH = '/workspace/projects'
local_project_files = listdir(LOCAL_FOLDER_PATH)
DROPBOX_DOWNLOAD_FOLDER_PATH = '/RunPod_Project_Download'
DROPBOX_UPLOAD_FOLDER_PATH = '/RunPod_Project_Upload'
TOKEN_FILE = '/workspace/scripts/token_dropbox.txt'
DOWNLOAD_CHUNK_SIZE = 128 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 128 * 1024 * 1024
CONCURRENCY_LIMIT = 16

def get_access_token():
    try:
        return open(TOKEN_FILE).read().strip()
    except FileNotFoundError:
        return None

def create_dropbox_client(access_token):
    return dropbox.Dropbox(oauth2_access_token=access_token)

def authenticate_and_save_token():
    """Authenticate with Dropbox and save the resulting access token to TOKEN_FILE."""
    APP_KEY = os.environ['APP_KEY']
    APP_SECRET = os.environ['APP_SECRET']
    auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
    authorize_url = auth_flow.start()

    print("1. Go to: " + authorize_url)
    print("2. Click \"Allow\" (you might have to log in first).")
    print("3. Copy the authorization code.")
    auth_code = input("Enter the authorization code here: ").strip()

    oauth_result = auth_flow.finish(auth_code)
    access_token = oauth_result.access_token

    with open(TOKEN_FILE, 'w') as file:
        file.write(access_token)

    return access_token

def connect_to_dropbox():
    """Establish a connection to Dropbox using the token stored in
    TOKEN_FILE. If the token is invalid, authenticate with the user and
    store the new token.
    """
    access_token = get_access_token()
    if not access_token:
        access_token = authenticate_and_save_token()

    try:
        dbx = create_dropbox_client(access_token)
        dbx.users_get_space_usage()
    except AuthError as err:
        print(f"Error authenticating with Dropbox: {err}")
        access_token = authenticate_and_save_token()
        dbx = create_dropbox_client(access_token)

    return dbx



def list_files():
    """List files in the Dropbox folder specified by the DROPBOX_FOLDER_PATH
    environment variable.

    Returns a Pandas DataFrame with the following columns:
        - name: the name of the file
        - id: the Dropbox file ID
        - path_display: the Dropbox file path
        - client_modified: the date and time the file was last modified
        - size: the size of the file in bytes

    Raises an exception if there is an error listing the files.
    """
    dbx = connect_to_dropbox()
    files_list = []

    try:
        files = dbx.files_list_folder(DROPBOX_DOWNLOAD_FOLDER_PATH).entries
        for file in files:
            if isinstance(file, dropbox.files.FileMetadata):
                metadata = {
                    "name": file.name,
                    "id": file.id,
                    "path_display": file.path_display,
                    "client_modified": file.client_modified,
                    "size": file.size
                }
                files_list.append(metadata)
        df = pd.DataFrame.from_records(files_list)
        return dbx, df.sort_values(by="size", ascending=False)
    except Exception as e:
        raise Exception("Error listing files") from e

async def download_chunk(session, url, start_byte, end_byte, file_part_id, semaphore):
    """Downloads a specific chunk of the file."""
    headers = {'Range': f'bytes={start_byte}-{end_byte}'}
    
    try:
        async with semaphore:
            print(f"Downloading part {file_part_id}: bytes {start_byte}-{end_byte}")
            async with session.get(url, headers=headers) as response:
                if response.status != 206: # 206 means Partial Content
                    print(f"Error downloading chunk {file_part_id}: HTTP Status {response.status}")
                    return None
                
                return await response.read()
    except ApiError as err:
        print(f"Dropbox API error: {err}")
    except Exception as err:
        print(f"An error occurred: {err}")

async def download_file_chunked(index):
    
    dbx, df = list_files()
    file_name = df.loc[index, 'name']
    file_path = df.loc[index, 'path_display']

    if file_name not in local_project_files:
        try:
            metadata, result = dbx.files_download(file_path)
            temp_link = dbx.files_get_temporary_link(file_path).link
            file_size = metadata.size
            print(f"Found file: {metadata.name}, Size: {file_size} bytes")

            num_chunks = (file_size + DOWNLOAD_CHUNK_SIZE - 1) // DOWNLOAD_CHUNK_SIZE
            tasks = []
            semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)  # Limit concurrent tasks

            async with aiohttp.ClientSession() as session:
                for i in range(num_chunks):
                    start = i * DOWNLOAD_CHUNK_SIZE
                    end = min((i + 1) * DOWNLOAD_CHUNK_SIZE - 1, file_size - 1)

                    task = asyncio.create_task(download_chunk(session, temp_link, start, end, i, semaphore))
                    tasks.append(task)

                chunks = await asyncio.gather(*tasks)

            # Reassemble the file from downloaded chunks
            with open(os.path.join(LOCAL_FOLDER_PATH, file_name), 'wb') as f:
                for chunk in chunks:
                    if chunk:
                        f.write(chunk)
            print(f"Downloaded {file_name} to {LOCAL_FOLDER_PATH}")

        except ApiError as err:
            print(f"Dropbox API error: {err}")
        except Exception as err:
            print(f"An error occurred: {err}")

def get_available_ram_bytes():
    """Return available system RAM in bytes via /proc/meminfo."""
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 8 * 1024 * 1024 * 1024  # 8GB fallback


def calculate_upload_params(file_size):
    """Derive queue depth and worker count from available RAM.

    Uses 60% of available RAM as the chunk buffer. Worker count is capped at
    64 since network throughput saturates well before that. Both scale up
    automatically on high-RAM containers.
    """
    available = get_available_ram_bytes()
    buffer_budget = int(available * 0.6)
    max_buffered = max(4, buffer_budget // UPLOAD_CHUNK_SIZE)
    total_chunks = (file_size + UPLOAD_CHUNK_SIZE - 1) // UPLOAD_CHUNK_SIZE
    queue_depth = min(max_buffered, total_chunks)
    workers = min(64, max(8, queue_depth))

    print(f"  Available RAM : {available / 1024**3:.1f} GB")
    print(f"  Buffer budget : {buffer_budget / 1024**3:.1f} GB "
          f"({queue_depth} × {UPLOAD_CHUNK_SIZE // 1024**2} MB chunks)")
    print(f"  Workers       : {workers}  |  Total chunks: {total_chunks}")

    return queue_depth, workers


async def _chunk_producer(local_path, file_size, queue):
    """Read the file sequentially and push chunks into the bounded queue.

    Blocks when the queue is full, keeping only as many chunks in memory
    as the queue depth allows.
    """
    offset = 0
    with open(local_path, 'rb') as f:
        while True:
            data = f.read(UPLOAD_CHUNK_SIZE)
            if not data:
                break
            is_last = (offset + len(data) >= file_size)
            await queue.put((offset, data, is_last))
            offset += len(data)


async def _chunk_uploader(token, session_id, queue, results, pbar):
    """Pull chunks from the queue and upload to Dropbox."""
    url = "https://content.dropboxapi.com/2/files/upload_session/append_v2"
    while True:
        offset, data, is_last = await queue.get()
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps({
                    "cursor": {"session_id": session_id, "offset": offset},
                    "close": is_last,
                }),
            }
            async with aiohttp.ClientSession() as http:
                async with http.post(url, headers=headers, data=data) as response:
                    response.raise_for_status()
            results[offset] = True
            pbar.update(len(data))
        except Exception as e:
            results[offset] = e
            tqdm.write(f"  FAILED offset {offset // 1024**2} MB: {e}")
        finally:
            queue.task_done()


async def upload_file_chunked(filename):
    """Upload a file to Dropbox using a concurrent chunked session.

    Queue depth and worker count scale automatically with available RAM so
    small containers stay within memory limits and large containers saturate
    the network.
    """
    dbx = connect_to_dropbox()
    token = dbx._oauth2_access_token
    local_path = os.path.join(LOCAL_FOLDER_PATH, filename)
    dropbox_path = os.path.join(DROPBOX_UPLOAD_FOLDER_PATH, filename)
    file_size = os.path.getsize(local_path)

    print(f"Uploading: {local_path}  ({file_size / 1024**3:.2f} GB)")

    if file_size <= UPLOAD_CHUNK_SIZE:
        print("Small file — using single-request upload.")
        with open(local_path, 'rb') as f:
            dbx.files_upload(f.read(), dropbox_path)
        print("Upload complete.")
        return

    queue_depth, num_workers = calculate_upload_params(file_size)

    session_id = dbx.files_upload_session_start(
        b'', session_type=dropbox.files.UploadSessionType.concurrent
    ).session_id
    print(f"Session started: {session_id}")

    queue = asyncio.Queue(maxsize=queue_depth)
    results = {}

    with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024,
              desc=filename, dynamic_ncols=True) as pbar:
        producer = asyncio.create_task(_chunk_producer(local_path, file_size, queue))
        workers = [
            asyncio.create_task(_chunk_uploader(token, session_id, queue, results, pbar))
            for _ in range(num_workers)
        ]

        await producer
        await queue.join()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    failures = {off: err for off, err in results.items() if err is not True}
    if failures:
        print(f"Upload failed — {len(failures)} chunk(s) errored:")
        for off, err in failures.items():
            print(f"  offset {off // 1024**2} MB: {err}")
        return

    print("All chunks uploaded — finishing session...")
    try:
        dbx.files_upload_session_finish(
            b'',
            dropbox.files.UploadSessionCursor(session_id=session_id, offset=file_size),
            dropbox.files.CommitInfo(path=dropbox_path),
        )
        print(f"Done: {dropbox_path}")
    except Exception as err:
        print(f"Error finishing session: {err}")


async def main():
    RUNPOD_POD_ID = os.environ.get('RUNPOD_POD_ID')
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=argparse.SUPPRESS)
    parser.add_argument("--filename", default=argparse.SUPPRESS, type=str)
    args = parser.parse_args()

    if not RUNPOD_POD_ID:
        DOWNLOAD_CHUNK_SIZE = 64 * 1024 * 1024
        UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024
        CONCURRENCY_LIMIT = 8        
        print("RUNPOD_POD environment not detected.")        

    if "index" in args:
        await download_file_chunked(index=int(args.index))
    elif "filename" in args:
        await upload_file_chunked(args.filename)
    else:
        _, df = list_files()
        print(df)

if __name__ == '__main__':
    asyncio.run(main())        
        