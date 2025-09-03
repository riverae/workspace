#!/bin/sh

DIR="/workspace/projects"
if [ "$(ls -A "$DIR")" ]; then
  rm /workspace/projects/*.blend
fi

if [ -z "$1" ]; then
  python /workspace/scripts/list.py
else
  python /workspace/scripts/list.py --index $1
fi
