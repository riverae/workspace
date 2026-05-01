# Blender Render Pipeline — Claude Context

## Environment
- Blender 5.1.1 → `/opt/blender_5.1/blender`
- Container on WSL2 Ubuntu; `/workspace` and `/root/.claude` are WSL-side volumes (persist across rebuilds)
- GPU: NVIDIA RTX 3080 Laptop | Windows driver 581.29 / WSL 580.82.10
- **OptiX renders go to RunPod** — OptiX is not achievable in WSL2 Docker (see memory for details)

## Required docker run flags
```
--gpus all
-e NVIDIA_DRIVER_CAPABILITIES=all
-v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro
-v /workspace:/workspace
-v /root/.claude:/root/.claude
```

## Asset workflow
Blend files are authored on Windows. Before uploading to RunPod, run the **Localize and Pack** addon (see `localize_pack_addon.md`) to copy all external assets into the blend directory and pack them into the `.blend` binary. The blend should be fully self-contained before upload.

## Key script: `scripts/setgpu.py`
Pre-script passed to every Blender render via `-P`. Handles GPU configuration only — asset remapping is the addon's responsibility.

1. **GPU setup** — Honors the blend's configured device (OptiX/CUDA/CPU). Fallback chain: blend's choice → OptiX → CUDA → CPU.
2. **Custom camera detection** — The blend uses a CUSTOM (Lens Simulation) camera that CUDA can't render (produces black). Script auto-falls back to CPU if OptiX is unavailable.
3. **OIDN denoising** — If denoising is enabled in the blend, forces OIDN with GPU acceleration.

## Render scripts
| Script | Description |
|--------|-------------|
| `render_frame.sh [frame...]` | Single or multiple frames, EXR or PNG per scene settings |
| `render_anim_exr.sh [start end]` | Full animation, OPEN_EXR_MULTILAYER |
| `render_anim_png.sh [start end]` | Full animation, PNG (Blender 4.5 — needs update) |
| `render_easystates.sh [dir]` | EasyStates addon batch render (Blender 4.5 — needs update) |
| `render_upload.sh <dir>` | 7-zip + Dropbox upload of renders folder |
| `render_download.sh [index]` | Dropbox download of blend file |
