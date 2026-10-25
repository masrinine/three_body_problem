# AGENTS.md

Blender add-on (Python + `bpy` + bundled `numpy`) that simulates three-body systems and bakes
the result to object-location keyframes. UI labels are English; README and many code comments
are Japanese.

## Fast start

- The repository root **is** the add-on package. The folder must be named `three_body_problem`
  (it contains `__init__.py` with `bl_info` and `blender_manifest.toml`).
- The only runtime dependency is Blender's bundled `numpy`; do not introduce pip-only imports.
- **Supported baseline: Blender 5.2 LTS or newer only.** 4.x/3.x are out of scope;
  `bl_info["blender"]` and the manifest both require `5.2.0`.
- Syntax check (any Python 3.11+; does not import `bpy`):
  ```powershell
  python -m py_compile __init__.py algo.py bake.py gizmos.py handlers.py keyframes.py operators.py panels.py presets.py properties.py
  ```
- Physics tests (plain Python + numpy, loaded by path — no `bpy`):
  ```powershell
  .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
  ```
- Blender headless integration tests:
  ```powershell
  & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python-exit-code 1 --python tests\blender_test.py
  ```
- Test artifacts are gitignored. The committed automated tests are
  `tests/test_physics.py` and `tests/blender_test.py`; generated renders/reports belong in
  `tests/output/` and local manual-test helpers in `tests/manual/` (for example
  `tests/manual/render_check.py`, which bakes a preset and renders trajectory images).
- Load/register/unregister smoke test (Blender is not on PATH on this machine):
  ```powershell
  & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python-expr "import sys; sys.path.insert(0, r'D:\GitHub'); import three_body_problem; three_body_problem.register(); three_body_problem.unregister(); print('REGISTER OK')"
  ```
  `sys.path` needs the **parent** of the repo (`D:\GitHub` here), not the repo itself.
- Package build + validation:
  ```powershell
  python tools\build_addon.py
  & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --command extension validate dist\three_body_problem-1.1.0-extension.zip
  ```
- CI: `.github/workflows/ci.yml` runs `py_compile`, the bpy-free physics tests, and the
  package build on every push, plus a cached Blender 5.2.2 job that runs the headless
  integration tests and validates the extension. `COMPATIBILITY.md` holds the version matrix
  and the manual release checklist.
- Dev install: either install `dist\...-extension.zip` from Preferences > Get Extensions >
  Install from Disk, or copy/junction the repo to
  `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\three_body_problem` and enable
  "Three Body Problem". The README recommends the VS Code "Blender Development" extension for
  reload-on-edit.

## Traps that cost time

- **`.venv` is not the runtime.** It has `fake-bpy-module` (typing stubs only), numpy, and
  matplotlib. `import bpy` there is an empty stub, so importing this package raises
  `AttributeError: module 'bpy' has no attribute 'types'`. Use Blender's bundled Python for
  `bpy` code. `algo.py` and `presets.py` are bpy-free and are loaded directly by path in
  `tests/test_physics.py`.
- **The modal operator still does not advance headless.** In `--background`,
  `bpy.ops.three_body.bake_simulation()` returns `RUNNING_MODAL` and never processes a frame.
  Use `bake.bake_sync(context)` (returns `(ctx, last_state, status, error)`) for headless bakes
  and tests; `algo.simulate_frames` is the bpy-free core.
- **`Action.fcurves` does not exist in 5.2** (slotted actions). Use the helpers in
  `keyframes.py` (`iter_action_fcurves`, `remove_location_fcurves`,
  `set_location_interpolation`), which read
  `ad.action.layers[*].strips[*].channelbag(ad.action_slot).fcurves`. Do not reach for
  `action.fcurves` or `animation_data_clear()` directly.
- **Scale is a coupled contract.** Stored `initial_location` and `velocity` are world-space.
  Preset application multiplies both by `S`; bake uses `G = G_base · S³ · gravity_strength`
  and softening `· S`. `properties.update_simulation_scale` rescales stored positions and
  velocities by `new_S/old_S` when `S` changes. Do not change one without the others, and keep
  `_last_simulation_scale` in sync (`update_preset_values`, `register`, `cleanup_on_load`).
- **Collision radii are world-space radii** (not diameters), computed from
  `matrix_world.to_3x3()` so rotation/scale/parents are included; modifiers are ignored,
  `Radius Offset` is added at full strength, and there is no hidden `S` multiplication. This is
  the intended spec — do not "fix" it back to the old mixed units.
- Bake sets location F-curves to `LINEAR` in `bake.finalize`; do not leave the default Bezier.
- Velocity arrows are drawn by `gizmos.py` only; `visualization.py` (the duplicate GPU draw
  handler) was removed in P1-10. Arrows start at `obj.matrix_world.translation` (world space),
  are skipped for hidden objects and for zero velocity, and use `velocity_gizmo_scale`. The
  `Viewport Display` panel stays editable after a bake because the display is visual only.
- `test_folder/` contains large `.blend`/`.aep` fixtures and is gitignored. Never read, edit, or
  commit it. Ignore `__pycache__` (mixed 3.11/3.12 artifacts).

## Architecture map

- `__init__.py` — `bl_info`; registration order is properties → operators → gizmos → panels →
  handlers (reverse on unregister).
- `blender_manifest.toml` — extension metadata (Blender 5.2+, version 1.1.0, MIT placeholder).
- `properties.py` — all persistent state hangs off `Scene.three_body_props`; `bodies` is a
  collection of `BodyProperties`. Editing mass/location/velocity switches `simulation_model` to
  `CUSTOM` via `update_custom_on_edit`; preset application uses `_updating_from_preset` to
  suppress that, and `update_simulation_scale` rescales stored state.
- `presets.py` — 9 `ThreeBodyPreset` entries. Pure data + numpy; carries `G`, `softening`, and
  `steps_per_frame`.
- `algo.py` — pure numpy physics plus the bpy-free core `simulate_frames`/`advance_frame`.
  Raises `SimulationTimeout` / `StabilityError` (both subclass `SimulationError`) to abort
  unsafe bakes.
- `bake.py` — Blender glue: `build_context` (validation + unit scaling), `simulate`,
  `apply_frame`, `finalize`, and `bake_sync` for headless use.
- `keyframes.py` — slotted-action F-curve helpers (iterate, remove location keys, set
  interpolation).
- `operators.py` — modal bake (4 frames/tick, ESC cancel), unbake, setup spheres, capture/apply
  locations, sync collection. `add_body` / `remove_body` live in `panels.py`, not here.
- `panels.py` — sidebar UI, including the `is_baked`/`is_baking` locks and the
  `Viewport Display` sub-panel, which is never locked because it only affects drawing.
- `handlers.py` — depsgraph location sync (start frame only), `is_baking` reset and
  `_last_simulation_scale` init on file load.
- Presets require exactly 3 bodies; `bake.build_context` enforces it. Custom systems accept any
  `N >= 1`.

## Quality bar

Preparing for paid distribution (~US$5–10). The prioritized backlog with acceptance criteria is
in `TASKS.md` (P0 done; the license decision is the final task). Verify claims in real Blender
5.2, not just with `py_compile`.
