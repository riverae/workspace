#!/bin/sh
echo /opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py --python-expr 'import bpy; bpy.context.scene.easystates_manager.render_output="/workspace/renders/output/"; bpy.ops.easystates.background_render()' -F OPEN_EXR_MULTILAYER
/opt/blender_4.5/blender -b /workspace/projects/*.blend -o /workspace/renders/output/ -P /workspace/scripts/setgpu.py --python-expr 'import bpy; bpy.context.scene.easystates_manager.render_output="/workspace/renders/output/"; bpy.ops.easystates.background_render()' -F OPEN_EXR_MULTILAYER
