#!/bin/sh

DIR="/workspace/projects"

if [ -z "$1" ]; then
  python /workspace/scripts/list.py
else
  if [ -n "$(find "$DIR" -maxdepth 1 -name '*.blend' -type f -print -quit)" ]; then
    rm /workspace/projects/*.blend
  fi
  python /workspace/scripts/list.py --index $1
fi
