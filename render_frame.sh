#!/bin/bash
# create a string from the value of arguments
# iterate over each argument and build a string variable


   
if [ -z "$1" ]; then
  echo /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -f 1
  /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -f 1
else
  array=( "$@" )
  items=$(printf " -f %s" "${array[@]}")
  echo /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py${items[@]}
  /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py${items[@]}
fi
