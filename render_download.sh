#!/bin/sh

DIR="/workspace/projects"

if [ -z "$1" ]; then
  python /workspace/scripts/dropbox_tools.py
else
  if [ -n "$(find "$DIR" -maxdepth 1 -name '*.blend' -type f -print -quit)" ]; then
    rm /workspace/projects/*.blend
  fi
  python /workspace/scripts/dropbox_tools.py --index $1
fi
