import bpy
import sys

def setup_gpu_rendering():
    """Enable GPU rendering: prefer OPTIX, fallback to CUDA"""
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.refresh_devices()
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'

    prefs.compute_device_type = 'CUDA'
    found = False
    for d in prefs.devices:
        if d.type == 'CUDA':
            d.use = True
            found = True
        else:
            d.use = False
    return 'CUDA' if found else None


def get_compositor_nodes(scene):
    """Return compositor node list compatible with Blender 4.x and 5.x"""
    # Blender 5.x: compositor moved to compositing_node_group
    ng = getattr(scene, 'compositing_node_group', None)
    if ng is not None:
        return ng.nodes
    # Blender 4.x fallback
    node_tree = getattr(scene, 'node_tree', None)
    if node_tree is not None:
        return node_tree.nodes
    return []


def check_denoising_enabled():
    """Return True if any denoising is enabled in scene, view layer, or compositor"""
    scene = bpy.context.scene
    vl = bpy.context.view_layer
    if getattr(scene.cycles, 'use_denoising', False):
        return True
    if hasattr(vl.cycles, 'use_denoising') and vl.cycles.use_denoising:
        return True
    return any(node.type == 'DENOISE' for node in get_compositor_nodes(scene))


def setup_oidn_denoising():
    """Configure OIDN denoiser for scene, view layer, and compositor with GPU & high quality"""
    scene = bpy.context.scene
    prefs = bpy.context.preferences
    views = bpy.context.view_layer

    # Scene-level denoising
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    if hasattr(scene.cycles, 'denoising_store_passes'):
        scene.cycles.denoising_store_passes = True
    scene.cycles.denoising_prefilter = 'ACCURATE'
    scene.cycles.denoising_quality = 'HIGH'
    # Ensure normal & albedo passes
    if hasattr(views, 'use_pass_normal'):
        views.use_pass_normal = True
    if hasattr(views, 'use_pass_diffuse_color'):
        views.use_pass_diffuse_color = True

    # GPU denoising flags
    if hasattr(scene.cycles, 'use_denoising_gpu'):
        scene.cycles.use_denoising_gpu = True
    if hasattr(scene.cycles, 'denoising_use_gpu'):
        scene.cycles.denoising_use_gpu = True

    # Compositor GPU
    if hasattr(scene.render, 'use_compositor_gpu'):
        scene.render.use_compositor_gpu = True
    if hasattr(prefs.system, 'compositor_device'):
        prefs.system.compositor_device = 'GPU'

    # Node-based compositor
    for node in get_compositor_nodes(scene):
        if node.type == 'DENOISE':
            if hasattr(node, 'use_gpu'):
                node.use_gpu = True
            if hasattr(node, 'use_hdr'):
                node.use_hdr = True


def setup_gpu_and_denoiser():
    """Main entry: configure GPU & enforce OIDN denoising if enabled"""
    scene = bpy.context.scene

    if scene.render.engine != 'CYCLES':
        print("Cycles not active, skipping setup.")
        return

    print("Configuring GPU rendering...")
    gpu = setup_gpu_rendering()
    if not gpu:
        print("No GPU devices found, aborting.")
        return

    print(f"GPU setup complete: {gpu}")

    if not check_denoising_enabled():
        print("Denoising not enabled in file; skipping denoiser setup.")
        return

    print("Denoising enabled: forcing OIDN configuration...")
    setup_oidn_denoising()

    # Optional tile size for GPU
    if hasattr(scene.cycles, 'use_auto_tile'):
        scene.cycles.use_auto_tile = False
    if hasattr(scene.cycles, 'tile_x'):
        scene.cycles.tile_x = 256
    if hasattr(scene.cycles, 'tile_y'):
        scene.cycles.tile_y = 256

    # Summary
    prefs = bpy.context.preferences.addons['cycles'].preferences
    print("=== Final Configuration ===")
    print(f"Compute Type: {prefs.compute_device_type}")
    print(f"Render Device: {scene.cycles.device}")
    print(f"Denoiser: {scene.cycles.denoiser} (GPU)")
    print("Enabled Devices:")
    for d in prefs.devices:
        if d.use:
            print(f"  - {d.name} ({d.type})")

    print("=== Scene Diagnostics ===")
    print(f"Scene: {scene.name}")
    print(f"Resolution: {scene.render.resolution_x}x{scene.render.resolution_y} @ {scene.render.resolution_percentage}%")
    print(f"Output path: {scene.render.filepath}")
    print(f"Output format: {scene.render.image_settings.file_format}")
    print(f"Frame range: {scene.frame_start}-{scene.frame_end}, current: {scene.frame_current}")
    print(f"Camera: {scene.camera.name if scene.camera else 'NONE - NO ACTIVE CAMERA!'}")
    vl = bpy.context.view_layer
    print(f"Active view layer: {vl.name}")
    print(f"View layer use: {vl.use}")
    nodes = get_compositor_nodes(scene)
    file_output_nodes = [n.name for n in nodes if n.type == 'OUTPUT_FILE']
    denoise_nodes = [n.name for n in nodes if n.type == 'DENOISE']
    print(f"Compositor File Output nodes: {file_output_nodes if file_output_nodes else 'none'}")
    print(f"Compositor Denoise nodes: {denoise_nodes if denoise_nodes else 'none'}")


if __name__ == '__main__':
    try:
        setup_gpu_and_denoiser()
        print("Setup completed successfully.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
