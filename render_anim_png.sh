#!/bin/bash
BLENDER_VERSION=5.1.1

# Expose WSL2 NVIDIA libs so OptiX stubs can reach the Windows driver via /dev/dxg
if [ -d /usr/lib/wsl/lib ]; then
  export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH}
fi

if [ -z "$1" ] || [ -z "$2" ]; then
  echo /opt/blender_${BLENDER_VERSION%.*}/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F PNG -a
  /opt/blender_${BLENDER_VERSION%.*}/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F PNG -a
else
  echo /opt/blender_${BLENDER_VERSION%.*}/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F PNG -s $1 -e $2 -a
  /opt/blender_${BLENDER_VERSION%.*}/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F PNG -s $1 -e $2 -a
fi
