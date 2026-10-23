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

- [ ] **8. Compatibility matrix and CI**
  - Confirm on every Blender release that the slotted-action helpers, the
    `POLYLINE_UNIFORM_COLOR` uniforms, registration, and `bl_info` parsing still work. The
    minimum is 5.2; older 4.x/3.x releases are explicitly out of scope.
  - Add CI: `py_compile` + numpy physics tests on every push; optionally a downloaded-Blender
    headless register/smoke job. Keep runtime code free of pip dependencies.

- [x] **9. Regression tests for the physics**
  - `tests/test_physics.py` covers all 9 presets for 250 frames, a <1% energy-drift budget,
    finite-value checks, scale invariance, cancellation, validation, the speed safety limit,
    and collision behavior. `tests/blender_test.py` covers the Blender integration.
  - Remaining (nice-to-have): a negative test that deliberately breaks the force law, and a
    Leapfrog-vs-RK45 parity check.

- [ ] **10. Deduplicate and verify velocity visualization**
  - `visualization.py` and `gizmos.py` both draw velocity arrows when `show_velocity_vectors`
    is on; the draw handler now sets `viewportSize`/`lineWidth` for `POLYLINE_UNIFORM_COLOR`,
    but the duplicate remains.
  - Work: keep one renderer (gizmos are the interactive choice) or make them mutually
    exclusive. Done when exactly one arrow per body, no GPU warnings, arrows follow the object.

- [ ] **11. First-run UX and demo content**
  - The default enum is `FIGURE_8`, but no preset state is applied at registration; assigning
    objects (Auto Setup) flips the model to `CUSTOM`. There is no explicit "Apply Preset"
    action and no demo scene.
  - Work: add an explicit "Apply Preset" action (or apply on setup), a one-click demo scene with
    camera/light/materials/backdrop, reset-to-defaults, and short tooltips. Consider motion paths
    enabled by default in the demo.

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

8 → 9 → 10 → 11 → 12 → 13 → 14, then 15 → 16 → 17, with **18 (license) last**.
