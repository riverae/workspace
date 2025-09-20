#!/bin/bash
renders_path="/workspace/renders"

if [ -z "$1" ]; then
  dir="output"
else
  dir=$1
fi

if [ ! -d "$renders_path/$dir" ]; then
  mkdir -p "$renders_path/$dir"
fi

echo /opt/blender_4.5/blender -b /workspace/projects/*.blend -P /workspace/scripts/setgpu.py --python-expr 'import bpy; bpy.context.scene.easystates_manager.render_output="/workspace/renders/'$dir'/"; bpy.ops.easystates.background_render()' -F OPEN_EXR_MULTILAYER
/opt/blender_4.5/blender -b /workspace/projects/*.blend -P /workspace/scripts/setgpu.py --python-expr 'import bpy; bpy.context.scene.easystates_manager.render_output="/workspace/renders/'$dir'/"; bpy.ops.easystates.background_render()' -F OPEN_EXR_MULTILAYER
bash /workspace/render_upload.sh $dir
