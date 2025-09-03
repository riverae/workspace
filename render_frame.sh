#!/bin/sh
if [ -z "$1" ]; then
  echo /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -f 1
  /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -f 1
else
  echo /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -f $1
  /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -f $1
fi
