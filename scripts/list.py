import os
import pandas as pd
from os import listdir
import argparse

from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.exceptions import AuthError
import dropbox

LOCAL_FOLDER_PATH = '/workspace/projects'
local_project_files = listdir(LOCAL_FOLDER_PATH)
DROPBOX_FOLDER_PATH = '/RunPod_Project_Download'
TOKEN_FILE = '/workspace/scripts/token_dropbox.txt'

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
        files = dbx.files_list_folder(DROPBOX_FOLDER_PATH).entries
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
        return df.sort_values(by="size", ascending=False)
    except Exception as e:
        raise Exception("Error listing files") from e


def download_file_by_index(index):
    dbx, df = list_files()
    file_name = df.loc[index, 'name']
    file_path = df.loc[index, 'path_display']

    if file_name not in local_project_files:
        result = dbx.files_download(file_path)
        with open(os.path.join(LOCAL_FOLDER_PATH, file_name), 'wb') as file:
            file.write(result.content)
        print(f"Downloaded {file_name} to {LOCAL_FOLDER_PATH}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=argparse.SUPPRESS)
    args = parser.parse_args()

    if "index" in args:
        download_file_by_index(index=int(args.index))
        pass
    else:
        df = list_files()
        print(df)        
        