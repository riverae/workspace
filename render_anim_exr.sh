#!/bin/sh
BLENDER_VERSION=5.1.1
if [ -z "$1" ] || [ -z "$2" ]; then
  echo /opt/blender_${BLENDER_VERSION%.*}/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F OPEN_EXR_MULTILAYER -a
  /opt/blender_${BLENDER_VERSION%.*}/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F OPEN_EXR_MULTILAYER -a
else
  echo /opt/blender_${BLENDER_VERSION%.*}/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F OPEN_EXR_MULTILAYER -s $1 -e $2 -a
  /opt/blender_${BLENDER_VERSION%.*}/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F OPEN_EXR_MULTILAYER -s $1 -e $2 -a
fi
