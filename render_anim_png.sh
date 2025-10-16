#!/bin/sh
if [ -z "$1" ] || [ -z "$2" ]; then
  echo /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F PNG -a
  /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F PNG -a
else
  echo /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F PNG -s $1 -e $2 -a
  /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F PNG -s $1 -e $2 -a
fi
