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

LOCAL_FOLDER_PATH = '/workspace/projects'
LOCAL_RENDERED_FOLDER_PATH = '/workspace/projects'
local_project_files = listdir(LOCAL_FOLDER_PATH)
DROPBOX_DOWNLOAD_FOLDER_PATH = '/RunPod_Project_Download'
DROPBOX_UPLOAD_FOLDER_PATH = '/RunPod_Project_Upload'
TOKEN_FILE = '/workspace/scripts/token_dropbox.txt'
DOWNLOAD_CHUNK_SIZE = 128 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024
CONCURRENCY_LIMIT = 10

def get_access_token():
    try:
        return open(TOKEN_FILE).read().strip()
    except FileNotFoundError:
        return None

def create_dropbox_client(access_token):
    return dropbox.Dropbox(oauth2_access_token=access_token)

def authenticate_and_save_token():
    """Authenticate with Dropbox and save the resulting access token to
    TOKEN_FILE.
    """
    app_key = os.environ['APP_KEY']
    app_secret = os.environ['APP_SECRET']
    auth_flow = DropboxOAuth2FlowNoRedirect(app_key, app_secret)
    authorization_url = auth_flow.start()

    print(f"1. Go to: {authorization_url}")
    print("2. Click \"Allow\" (you might have to log in first).")
    print("3. Copy the authorization code.")
    authorization_code = input("Enter the authorization code here: ").strip()

    oauth_result = auth_flow.finish(authorization_code)
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


def authenticate_and_save_token():
    """Authenticate with Dropbox and save the resulting access token to
    TOKEN_FILE.
    """
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
            semaphore = asyncio.Semaphore(16)  # Limit concurrent tasks

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

async def upload_chunk_worker(DROPBOX_ACCESS_TOKEN, session, session_id, task_queue, results):
    """
    A worker that pulls chunks from a queue and uploads them.
    """
    while True:
        try:
            offset, data, is_last_chunk = await task_queue.get()
            print(f"Uploading part at offset {offset}")
            url = "https://content.dropboxapi.com/2/files/upload_session/append_v2"
            
            api_arg = {
                "cursor": {"session_id": session_id, "offset": offset},
                "close": is_last_chunk
            }
            
            # Use json.dumps to ensure correct JSON formatting
            headers = {
                "Authorization": f"Bearer {DROPBOX_ACCESS_TOKEN}",
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps(api_arg)
            }
            
            async with session.post(url, headers=headers, data=data) as response:
                response.raise_for_status()
                results.append((offset, True))
                print(f"Successfully uploaded part at offset {offset}")
        except asyncio.QueueEmpty:
            break
        except aiohttp.ClientResponseError as e:
            print(f"Error uploading chunk at offset {offset}: {e.status}, message='{e.message}'")
            results.append((offset, False, e))
        except Exception as e:
            print(f"An unexpected error occurred for chunk at offset {offset}: {e}")
            results.append((offset, False, e))
        finally:
            task_queue.task_done()

async def upload_file_chunked(filename):
    """
    Uploads a large file to Dropbox in multiple chunks concurrently.
    """
    dbx = connect_to_dropbox()
    DROPBOX_ACCESS_TOKEN = dbx._oauth2_access_token    
    local_path = os.path.join(LOCAL_FOLDER_PATH, filename)
    file_size = os.path.getsize(local_path)
    print(f"File size: {file_size}")
    dropbox_path = os.path.join(DROPBOX_UPLOAD_FOLDER_PATH, filename)

    file_size = os.path.getsize(local_path)
    if file_size <= UPLOAD_CHUNK_SIZE:
        print("File size is small enough for a single upload. Using standard upload.")
        with open(local_path, "rb") as f:
            dbx.files_upload(f.read(), dropbox_path)
        print("Standard upload complete.")
        return

    print(f"Starting concurrent upload session for file: {local_path}")
    session_start_result = dbx.files_upload_session_start(
        b'',
        session_type=dropbox.files.UploadSessionType.concurrent
    )
    session_id = session_start_result.session_id
    print(f"Upload session started with ID: {session_id}")

    task_queue = asyncio.Queue()
    offset = 0
    with open(local_path, "rb") as f:
        while True:
            data = f.read(UPLOAD_CHUNK_SIZE)
            if not data:
                break
            
            is_last_chunk = (offset + len(data) >= file_size)
            await task_queue.put((offset, data, is_last_chunk))
            offset += len(data)

    results = []
    async with aiohttp.ClientSession() as session:
        workers = [
            asyncio.create_task(upload_chunk_worker(DROPBOX_ACCESS_TOKEN, session, session_id, task_queue, results))
            for _ in range(CONCURRENCY_LIMIT)
        ]
        await task_queue.join()
        for worker in workers:
            worker.cancel()
        
        await asyncio.gather(*workers, return_exceptions=True)

    if any(not success for _, success, *err in results):
        print("One or more chunks failed to upload. Aborting.")
        return

    print(f"All chunks uploaded. Finishing upload session...")
    try:
        commit_info = dropbox.files.CommitInfo(path=dropbox_path)
        cursor = dropbox.files.UploadSessionCursor(session_id=session_id, offset=file_size)
        
        dbx.files_upload_session_finish(io.BytesIO(b'').getvalue(), cursor, commit_info)
        print(f"Successfully uploaded file to {dropbox_path}")
    except dropbox.exceptions.ApiError as err:
        print(f"Error finishing upload session: {err}")
    except Exception as err:
        print(f"An error occurred during chunked upload: {err}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=argparse.SUPPRESS)
    parser.add_argument("--filename", default=argparse.SUPPRESS, type=str)
    args = parser.parse_args()

    if "index" in args:
        await download_file_chunked(index=int(args.index))
    elif "filename" in args:
        await upload_file_chunked(args.filename)
    else:
        _, df = list_files()
        print(df)

if __name__ == '__main__':
    asyncio.run(main())        
        