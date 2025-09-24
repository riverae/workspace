#!/bin/sh

PROJ_DIR="/workspace/projects"
RENDER_DIR="/workspace/renders"

if [ -z "$1" ]; then
  echo "No file provided for upload."
else
  #zip -0 -r $PROJ_DIR/$1.zip $RENDER_DIR/$1
  7z a -mx0 -bt $PROJ_DIR/$1.7z $RENDER_DIR/$1
  python /workspace/scripts/dropbox_tools.py --filename $1.zip
fi
