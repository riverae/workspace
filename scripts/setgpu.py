import bpy
import sys
import os

# Set this to wherever you place the botaniq_full folder on Linux.
# Leave as empty string to skip remapping.
BOTANIQ_LINUX_ROOT = "/workspace/assets/botaniq_full"

# Old Windows-side root as it appears in the blend file's library paths.
BOTANIQ_WIN_ROOT = "/c/Users/Bryan/polygoniq_asset_packs/botaniq_full"


def _normalize_win_path(raw):
    """Convert Windows-style path (backslashes, drive letter) to Unix style."""
    p = raw.replace('\\', '/')
    # C:/... -> /c/...
    if len(p) >= 3 and p[1] == ':' and p[2] == '/':
        p = '/' + p[0].lower() + p[2:]
    return p


def remap_missing_libraries():
    """Redirect broken Windows library paths to the Linux asset location."""
    if not BOTANIQ_LINUX_ROOT:
        print("  BOTANIQ_LINUX_ROOT not set — skipping remap.")
        return

    print(f"  Scanning {len(bpy.data.libraries)} linked libraries...")
    remapped = 0
    missing_on_disk = 0

    for lib in bpy.data.libraries:
        normed = _normalize_win_path(lib.filepath)

        if BOTANIQ_WIN_ROOT not in normed:
            continue

        new_path = normed.replace(BOTANIQ_WIN_ROOT, BOTANIQ_LINUX_ROOT)
        if os.path.exists(new_path):
            lib.filepath = new_path
            lib.reload()
            remapped += 1
            print(f"  Remapped: {new_path}")
        else:
            missing_on_disk += 1
            print(f"  MISSING on disk: {new_path}")

    if remapped:
        print(f"Library remap complete: {remapped} remapped, {missing_on_disk} still missing.")
    elif missing_on_disk:
        print(f"Library remap: {missing_on_disk} paths matched but files not yet at {BOTANIQ_LINUX_ROOT}")
    else:
        print(f"Library remap: no botaniq libraries found — check BOTANIQ_WIN_ROOT value.")


def setup_gpu_rendering():
    """Validate and enforce GPU rendering based on blend file settings.

    Honors the blend's configured compute device, then falls back through
    OPTIX → CUDA → CPU. Returns the device type string actually applied,
    or None if the render engine is not Cycles.
    """
    prefs = bpy.context.preferences.addons['cycles'].preferences
    scene = bpy.context.scene

    if scene.render.engine != 'CYCLES':
        print(f"  Render engine is {scene.render.engine}, not Cycles — skipping GPU setup.")
        return None

    if scene.cycles.device == 'CPU':
        print("  Blend configured for CPU rendering — keeping CPU.")
        return 'CPU'

    # Build fallback chain: blend's choice first, then remaining GPU backends
    requested = prefs.compute_device_type
    chain = [requested]
    for backend in ('OPTIX', 'CUDA'):
        if backend not in chain:
            chain.append(backend)

    print(f"  Blend requests: {requested}. Fallback chain: {' → '.join(chain)} → CPU")

    for device_type in chain:
        prefs.compute_device_type = device_type
        prefs.refresh_devices()
        if any(d.type == device_type for d in prefs.devices):
            for d in prefs.devices:
                d.use = (d.type == device_type)
            print(f"  GPU device set: {device_type}")
            return device_type

    print("  No GPU devices found — falling back to CPU.")
    scene.cycles.device = 'CPU'
    return 'CPU'


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


def check_and_fix_custom_camera(gpu_type):
    """Detect Blender 5.x CUSTOM camera type and switch to CPU if needed.

    Blender 5.x Lens Simulation cameras use shader-defined ray generation
    (camera.type == 'CUSTOM').  CUDA cannot evaluate custom camera shaders —
    it renders pure black.  OptiX supports it; CPU supports it via OSL.
    When OptiX is unavailable, fall back to CPU so the render is correct.
    Returns True if the device was switched to CPU.
    """
    scene = bpy.context.scene
    cam_obj = scene.camera
    if not cam_obj or cam_obj.data.type != 'CUSTOM':
        return False
    if gpu_type == 'OPTIX':
        print("CUSTOM (LensSim) camera on OptiX — OK.")
        return False
    print(f"CUSTOM (LensSim) camera detected on {gpu_type}: "
          "CUDA cannot render custom camera rays → switching to CPU.")
    print("  Re-run on hardware with OptiX support for GPU rendering.")
    scene.cycles.device = 'CPU'
    return True


def setup_gpu_and_denoiser():
    """Main entry: configure GPU & enforce OIDN denoising if enabled"""
    scene = bpy.context.scene

    print("Remapping missing library paths...")
    remap_missing_libraries()

    print("Configuring GPU rendering...")
    gpu = setup_gpu_rendering()
    if gpu is None:
        print("GPU setup skipped (non-Cycles engine).")
        return

    print(f"GPU setup complete: {gpu}")

    check_and_fix_custom_camera(gpu)

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

    # Camera deep-dive
    cam_obj = scene.camera
    if cam_obj:
        cam = cam_obj.data
        print("=== Camera Diagnostics ===")
        print(f"  Type: {cam.type}")
        print(f"  Lens: {cam.lens}mm, Sensor: {cam.sensor_width}x{cam.sensor_height}mm")
        print(f"  Clip: {cam.clip_start} – {cam.clip_end}")
        print(f"  DOF: {'on, f/' + str(round(cam.dof.aperture_fstop,1)) if cam.dof.use_dof else 'off'}")
        loc = cam_obj.matrix_world.translation
        print(f"  World location: ({loc.x:.2f}, {loc.y:.2f}, {loc.z:.2f})")
        # Check for a glass plane / lens rig object near the camera
        import mathutils
        nearby = [o.name for o in bpy.data.objects
                  if o.type == 'MESH'
                  and (o.matrix_world.translation - loc).length < 2.0
                  and o.name != cam_obj.name]
        print(f"  Mesh objects within 2m of camera: {nearby if nearby else 'none'}")

    # Light summary
    lights = [o for o in bpy.data.objects if o.type == 'LIGHT']
    print(f"Lights in scene: {len(lights)} → {[o.name for o in lights[:6]]}")
    world = scene.world
    print(f"World: {world.name if world else 'NONE'}, use_nodes={world.use_nodes if world else 'n/a'}")

    # Bounce / clamp summary
    lp = scene.cycles
    print(f"Light paths: max={lp.max_bounces}, trans={lp.transmission_bounces}, "
          f"clamp_dir={lp.sample_clamp_direct}, clamp_ind={lp.sample_clamp_indirect}")


if __name__ == '__main__':
    try:
        setup_gpu_and_denoiser()
        print("Setup completed successfully.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
