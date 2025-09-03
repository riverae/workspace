import dropbox
from dropbox.exceptions import AuthError
from dropbox import DropboxOAuth2FlowNoRedirect
import pandas as pd
import os
from os import listdir
from os import path
import argparse

LOCAL_FOLDER_PATH = '/workspace/projects'
local_project_files = listdir(LOCAL_FOLDER_PATH)
APP_KEY = 'vm62c8tizuiqmer'
APP_SECRET = '6gha4cjy20tq8vt'
token_file = '/workspace/scripts/token_dropbox.txt'

def connect():
    try:
        access_token = open(token_file).read()
        dbx = dropbox.Dropbox(oauth2_access_token=access_token.strip())
        print('Authenticated')
    except Exception as e:
        print('Error connecting to Dropbox with access token: ' + str(e))
        auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
        authorize_url = auth_flow.start()

        print("1. Go to: " + authorize_url)
        print("2. Click \"Allow\" (you might have to log in first).")
        print("3. Copy the authorization code.")
        auth_code = input("Enter the authorization code here: ").strip()


        oauth_result = auth_flow.finish(auth_code)
        dbx = dropbox.Dropbox(oauth2_access_token=oauth_result.access_token)
        if os.path.exists(token_file):
            os.remove(token_file)
        with open(token_file, 'w') as file:
            file.write(oauth_result.access_token)

    return dbx

def list_files():
    dbx = connect()
    try:
        files = dbx.files_list_folder('').entries
        files_list = []

        for file in files:
            if isinstance(file, dropbox.files.FileMetadata):
                metadata = {
                    'name': file.name,
                    'id': file.id,
                    'path_display': file.path_display,
                    'client_modified': file.client_modified,
                    'size': file.size
                }
                files_list.append(metadata)
        df = pd.DataFrame.from_records(files_list)
        return dbx, df.sort_values(by='size', ascending=False)

    except Exception as e:
        print('Error'+str(e))

def download_file(index):
    dbx, df = list_files()
    name = df.at[index,'name']
    path = df.at[index,'path_display']
    print(df.loc[index])
    if name not in local_project_files:
        metadata, result = dbx.files_download(path)
        with open(f'{LOCAL_FOLDER_PATH}/{name}', 'wb') as f:
            f.write(result.content)
        print('Downloaded: '+ name)

def download_files():
    dbx, df = list_files()
    for name, path in zip(df.loc[:, 'name'], df.loc[:, 'path_display']):
        if name not in local_project_files:
            metadata, result = dbx.files_download(path)
            with open(f'{LOCAL_FOLDER_PATH}/{name}', 'wb') as f:
                f.write(result.content)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=argparse.SUPPRESS)
    args = parser.parse_args()

    if "index" in args:
        download_file(index=int(args.index))
    else:
        dbx, df = list_files()
        print(df)
        #print(local_project_files)

