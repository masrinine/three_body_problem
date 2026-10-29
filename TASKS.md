# Commercial readiness tasks (target: US$5–10 add-on)

Baseline: Blender **5.2.2 LTS**, repository state at 2026-10-23. Priorities:

- **P0** — blocks a paid release (data loss, broken core flow, packaging).
- **P1** — required for a credible $5–10 product (accuracy evidence, docs, demo, compatibility).
- **P2** — polish and maintainability.
- **Final** — the license decision, intentionally scheduled last.

Release gate: a new user can install the extension zip on Blender **5.2 LTS or newer**,
create 3 bodies, pick a preset, bake 250 frames, render, and unbake — with no console errors
and no lost animation.

## P0 — release blockers (done)

- [x] **1. Make Unbake safe on slotted actions**
  - `keyframes.py` reads F-curves through
    `ad.action.layers[*].strips[*].channelbag(ad.action_slot)`; `remove_location_fcurves`
    deletes only `data_path == "location"` and clears `animation_data` only when no F-curves,
    NLA tracks, or drivers remain. No legacy `Action.fcurves` path is kept (5.2+ only).
  - Verified by `tests/blender_test.py::test_unbake_preserves_other_animation`: location keys
    are removed, rotation/scale keys survive, the object returns to `initial_location`.

- [x] **2. Make spatial scale and collision units consistent**
  - Canonical spec: stored `initial_location` and `velocity` are **world-space**. Applying a
    preset multiplies both by `S`; `G = G_base · S³ · gravity_strength`; softening scales with
    `S`. Changing `Simulation Scale` rescales stored locations and velocities by `new_S/old_S`
    (`properties.update_simulation_scale`), preserving the normalized path.
  - Collision radii are **world-space radii** (not diameters): auto uses the full mesh radius
    from `matrix_world.to_3x3()` (rotation/scale/parents included), manual is used as-is, and
    `Radius Offset` is added at full strength. No hidden `S` multiplication.
  - Verified by `tests/test_physics.py::test_scale_invariance` (S=5 vs S=10 normalized paths
    match) and `test_collision_changes_trajectory`.

- [x] **3. Extract a headless, cancellable simulation core**
  - `algo.simulate_frames(...)` is bpy-free and yields `FrameState` per frame; `bake.py`
    translates scene properties into it and owns keyframe application. The modal operator
    schedules 4 frames per timer tick and cancels on ESC.
  - Verified by `tests/blender_test.py::test_sync_bake_and_linear_keys` /
    `test_simulate_frame_count` (10 frames → 10 location keys per object) and the
    `bake.bake_sync` helper used everywhere in headless tests.

- [x] **4. Protect baked results from stale inputs**
  - While `is_baked` (or `is_baking`) the Bodies, Presets, and Settings panels are disabled;
    the Bake button is disabled once baked. `bake.build_context` rejects a second bake,
    enforces `N == 3` for presets, and validates mass/location/velocity/frame range/FPS/scale.
  - Verified by `test_rebake_blocked_while_baked` and `test_invalid_frame_range_is_rejected`.

- [x] **5. Set keyframe interpolation deliberately**
  - `bake.finalize` sets every baked location F-curve to `LINEAR`.
  - Verified by `test_sync_bake_and_linear_keys`.

- [x] **6. Remove or implement dead state**
  - Deleted `sim_method`, `cache_path`, `softening`, the unused `gravitational_constant`, and
    the unused internal `collision_radius`. Every remaining `Scene.three_body_props` field is
    read by the bake path or UI.

- [x] **7. Ship installable packaging**
  - Added `blender_manifest.toml` (`blender_version_min = "5.2.0"`, version `1.1.0`) and
    `tools/build_addon.py`, which produces `dist/three_body_problem-1.1.0-extension.zip`
    (root manifest) and `...-legacy.zip` (top-level `three_body_problem/` folder).
  - Verified: `blender --command extension validate dist/three_body_problem-1.1.0-extension.zip`
    succeeds; `bl_info` version/min match the manifest
    (`tests/test_physics.py::ManifestTests`).

## P1 — required for a $5–10 product

- [x] **8. Compatibility matrix and CI**
  - `COMPATIBILITY.md` documents 5.2.2 LTS as the verified baseline, 5.3/6.x as
    expected-but-unverified, 4.x/3.x as unsupported, and a manual release checklist.
    `register()` now raises a clear error when `bpy.app.version < (5, 2, 0)`.
  - `.github/workflows/ci.yml` has two jobs:
    - `python-tests`: `py_compile`, the bpy-free physics suite, and `tools/build_addon.py`,
      with the zips uploaded as an artifact.
    - `blender-tests`: downloads and caches Blender 5.2.2 Linux, installs the runtime
      libraries, runs `tests/blender_test.py` headless, then validates the extension zip.
  - Verified locally: YAML parses, the Blender download URL returns HTTP 200, and every CI
    command passes on 5.2.2. The first remote run will confirm the Linux job.

- [x] **9. Regression tests for the physics**
  - `tests/test_physics.py` covers all 9 presets for 250 frames, a <1% energy-drift budget,
    finite-value checks, scale invariance, cancellation, validation, the speed safety limit,
    and collision behavior. `tests/blender_test.py` covers the Blender integration.
  - Remaining (nice-to-have): a negative test that deliberately breaks the force law, and a
    Leapfrog-vs-RK45 parity check.

- [x] **10. Deduplicate and verify velocity visualization**
  - `visualization.py` (the `POST_VIEW` draw handler) was deleted; `gizmos.py` is the single
    renderer. `__init__.py`, the CI `py_compile` list, `README.md`, `AGENTS.md`, and
    `COMPATIBILITY.md` no longer reference it.
  - `gizmos.py` now starts each arrow at `obj.matrix_world.translation` (world space; the old
    `obj.location` was parent space), skips hidden objects via `visible_get()`, draws nothing
    for zero/degenerate velocity, grows the pool to 128, and `poll()` also requires
    `show_velocity_vectors`.
  - Added the `Viewport Display` sub-panel (`Show Velocity Vectors`, `Gizmo Drawing Scale`) that
    stays editable while baked/baking; the scale was removed from `Simulation Settings`. Both
    properties now tag 3D Viewports for redraw.
  - Verified on 5.2.2: `py_compile`, the 12 bpy-free physics tests, 11 headless Blender tests
    (including the world-space matrix, zero-velocity, visibility, and `poll()` checks), and
    extension validate.
  - Manual GUI check (scripted screenshots in `tests/output/gui_check/`, top orthographic view):
    exactly one arrow per body with controlled orthogonal velocities; `scale 0.1/0.5/1/2`
    changes the length; zero velocity and hidden objects draw no arrow; arrows follow objects
    during a baked scrub (frames 1 vs 40), after parenting to a moved/rotated empty, and after
    moving the objects; four bodies render four arrows; the `Viewport Display` panel draws and
    stays enabled while baked; the Blender console shows no GPU/shader warnings.

- [x] **11. First-run UX and demo content** — complete
  - Verified problem (5.2.2): a fresh file reports `simulation_model = FIGURE_8` with 0 bodies,
    and `Auto Setup` creates a collinear row at ±5 m with velocities of ±0.1 while flipping the
    model to `CUSTOM` (assigning `BodyProperties.obj` triggers `update_custom_on_edit`). The
    preset the UI advertises is never applied, and there is no way to re-apply one.
  - [x] **11a — Apply Preset and a sane Auto Setup**
    - Added `properties.apply_preset_to_bodies` / `_write_preset_to_bodies` (shared with the enum
      callback, never creates empty slots), `three_body.apply_preset` (poll requires a selected
      preset, exactly 3 assigned bodies, and not baked/baking), and an `Apply Preset` button in
      the presets panel.
    - `setup_objects` now remembers the model from before setup and re-applies the selected
      preset when it created exactly 3 bodies; a 4+ body setup stays `CUSTOM` with a warning.
    - Verified on 5.2.2: 4 new headless tests (auto setup applies the preset; re-selecting after
      an edit; the operator restores a drifted preset; refusals for CUSTOM/baked/missing
      object/N!=3), 15 headless Blender tests total, 12 physics tests, build + extension validate.
      GUI: `Auto Setup` leaves Figure-8 applied with the `Apply Preset` button
      (`tests/output/gui_check_11a/`, gitignored).
  - [x] **11b — one-click demo scene**
    - `three_body.create_demo_scene` creates `Three Body Demo` in a new scene (the original scene
      stays untouched): Figure-8, 3 shaded spheres, framed camera, sun/fill/rim lights, dark
      backdrop and world, 1920x1080 EEVEE, 250 frames at 24 fps, and a pre-baked Figure-8 so
      Play works immediately. A second invocation switches to the existing demo without
      duplicating it.
    - The `Create Demo Scene` button lives in the main panel and stays enabled while baked. The
      demo starts with velocity arrows hidden so the render stays clean; the scene camera is
      ready for Numpad 0 / F12.
    - Verified on 5.2.2: `test_demo_scene_created_once` (baked, 3 bodies, camera/lights/backdrop,
      250 frames, 24 fps, moving timeline, idempotent second click, original scene unchanged),
      16 headless tests total, 12 physics tests, build + validate, and a camera-view render at
      frame 60 (`tests/output/gui_check_11b/`, gitignored).
  - [x] **11c — reset and copy polish**
    - `three_body.reset_settings` shows a confirmation dialog and restores the simulation/display
      settings to their RNA defaults without deleting objects or silently reapplying a preset.
      Body slots, assigned objects, and `simulation_model` are kept; `simulation_scale` still
      rescales stored positions/velocities so the system shape is preserved. The reset also
      clears `energy_drift` and `last_simulation_report`, and is refused (with a clear message)
      while baking or baked. The main-panel button is disabled in those states.
    - `Reset Settings` lives in the main panel. README quick start now points to
      Auto Setup → preset check → Bake, documents the demo, and the reset behavior;
      `COMPATIBILITY.md` has a first-run release-checklist item.
    - Verified on 5.2.2: `test_reset_settings` (all settings, body/model preservation, scale,
      baked/baking refusal), 17 headless tests, 12 physics tests, build + validate, and GUI
      screenshots of the dialog and the post-reset panels (`tests/output/gui_check_11c/`,
      gitignored).
  - Acceptance: fresh file → Auto Setup → Figure-8 is applied and the enum stays `FIGURE_8`;
    re-selecting a preset after an edit reapplies it; Apply is refused with a clear message in
    the invalid states; the demo scene is one click, non-destructive, and idempotent; the scale
    contract and N == 3 rule are covered by headless tests plus a GUI screenshot pass.
  - Out of scope: user-saved presets (P2-17), caching, physics changes.

- [ ] **12. Documentation and store assets**
  - README now documents Blender 5.2+, install, all 9 presets, bake/unbake, linear
    interpolation, the world-space collision model, and the developer commands.
  - Remaining: an EN version alongside the JA README, troubleshooting, and a GIF plus 3–5
    screenshots for the store page.

- [ ] **13. Long-run performance and robustness**
  - Frame chunking (4 per tick) and per-frame timeout are in place; `fps > 0`,
    finite masses/locations, frame range, and object validity are validated before a bake.
  - Remaining: cap total bake wall-clock/memory and confirm a 1,000-frame bake stays responsive.

- [ ] **14. Release operations**
  - Add `CHANGELOG.md`, a support/contact section, an issue template, and a repeatable checklist:
    version bump → `python tools/build_addon.py` → extension validate → clean-profile
    install on 5.2 → smoke test → store upload.
  - Done when: two consecutive releases can be produced from the checklist without ad-hoc steps.

## P2 — polish

- [ ] **15. Code hygiene**
  - `algo.TimeoutError` is renamed to `SimulationTimeout` and the redundant second
    `BodyProperties` unregister is gone. Remaining: narrow broad `except Exception`, and add
    type hints or a pyright/mypy config using the existing `fake-bpy-module` stubs.
- [ ] **16. Undo and persistence checks**
  - Verify a bake is a single undo step, unbake is undoable, and reloading a `.blend` mid-bake
    leaves `is_baking=False` (the load handler exists; test it).
- [ ] **17. Preset/save-file extensibility (only if it supports sales)**
  - Consider user-saved initial conditions and preset export/import. Do not add a cache system
    unless it replaces the removed `sim_method`/`cache_path` fields.

## Final — before paid release

- [ ] **18. Decide the paid-distribution license (owner decision, do not silently change)**
  - Evidence: `LICENSE` is MIT (© 2026 Kazuhiro Kanaga) and is the temporary default in the
    manifest. MIT permits buyers to redistribute and resell the add-on, which may conflict with
    a paid product.
  - Work: confirm the intended license with the owner; update `LICENSE`, README, the manifest
    `license` field, and store metadata consistently. MIT is GPL-compatible; a proprietary EULA
    is also possible outside the Blender extensions platform.
  - Done when: the owner has explicitly approved the license and all distribution files agree.

## Suggested order

8 → 9 → 10 → 11a → 11b → 11c → 12 → 13 → 14, then 15 → 16 → 17,
with **18 (license) last**.
