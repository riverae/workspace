#!/bin/sh
/opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py -F OPEN_EXR_MULTILAYER -a
