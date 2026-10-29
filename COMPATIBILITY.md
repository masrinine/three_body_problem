# Blender compatibility

**Baseline: Blender 5.2 LTS or newer.** The add-on uses slotted actions
(`Action.fcurves` was removed in 5.2), so Blender 4.x and 3.x are explicitly
unsupported.

| Blender | Status | Verified | Notes |
|---|---|---|---|
| 5.2.2 LTS | Supported (baseline) | 2026-10-28 | `py_compile`, 12 bpy-free physics tests, 17 headless Blender tests, extension manifest validation, manual GUI checklist |
| 5.3.x / 6.x | Expected to work | not yet | run the release checklist below on each new release |
| 4.2 LTS and older | Unsupported | — | no slotted actions; do not install |

`bl_info["blender"]` and `blender_manifest.toml` both require `5.2.0`.
`register()` also raises a clear error when `bpy.app.version` is older, which
catches development installs that bypass the add-on metadata.

## Release checklist for a new Blender version

1. Build the package:
   ```powershell
   python tools\build_addon.py
   ```
2. Validate the extension manifest:
   ```powershell
   & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --command extension validate dist\three_body_problem-1.1.0-extension.zip
   ```
3. Install the zip in a clean profile; enable, disable, and re-enable it.
4. Run the headless integration suite:
   ```powershell
   & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python-exit-code 1 --python tests\blender_test.py
   ```
5. Fresh file: `Auto Setup` with Figure-8, `Bake All`, `Unbake All`, then
   `Reset Settings`; confirm the reset dialog appears, settings return to
   defaults, bodies/preset are preserved, and the button is disabled while
   baked.
6. Bake Figure-8 for 250 frames and confirm `Physics Accuracy` is high and no
   console errors appear.
7. Unbake and confirm that rotation/scale animation on the objects survives.
8. In the viewport, confirm exactly one velocity arrow per body (`Viewport
   Display > Show Velocity Vectors`), no GPU/shader warnings in the system
   console, and that the arrows follow the objects while scrubbing a baked
   animation.
9. Save, reload, and confirm `is_baking=False` and `is_baked` survive.

CI (`.github/workflows/ci.yml`) runs steps 1-4 on every push for Blender 5.2.2.
The Blender binary is downloaded from `download.blender.org` and cached between
runs.
