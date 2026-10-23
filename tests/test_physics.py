"""Physics-level tests for the bpy-free simulation core.

These tests load ``algo.py`` and ``presets.py`` directly by path so they can run
with a plain Python + numpy interpreter (for example the repository's
``.venv``), without importing ``bpy``:

    .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py"

A separate ``tests/blender_test.py`` covers the Blender integration.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _load(module_name):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


algo = _load("algo")
presets = _load("presets")

FRAMES = 250
FPS = 24


def scaled_inputs(preset, scale):
    """Mirror how the add-on applies Simulation Scale to a preset."""
    masses = np.array(preset.masses, dtype=float)
    positions = np.array(preset.positions, dtype=float) * scale
    velocities = np.array(preset.velocities, dtype=float) * scale
    G = preset.G * scale ** 3
    softening = preset.softening * scale
    return masses, positions, velocities, G, softening


def simulate_preset(key, scale, frames=FRAMES):
    preset = presets.PRESETS[key]
    masses, positions, velocities, G, softening = scaled_inputs(preset, scale)
    return list(algo.simulate_frames(
        masses, positions, velocities,
        start_frame=1, end_frame=frames, fps=FPS,
        G=G, softening=softening,
        substeps=preset.steps_per_frame,
    ))


class PresetPhysicsTests(unittest.TestCase):
    def test_preset_count(self):
        self.assertEqual(len(presets.PRESETS), 9)

    def test_presets_are_finite_and_stable(self):
        """Every shipped preset must run 250 frames without blowing up."""
        for key in presets.PRESETS:
            with self.subTest(preset=key):
                states = simulate_preset(key, scale=5.0)
                self.assertEqual(len(states), FRAMES)
                last = states[-1]
                self.assertTrue(np.all(np.isfinite(last.positions)))
                self.assertTrue(np.all(np.isfinite(last.velocities)))
                # 1% cumulative worst-case Hamiltonian drift budget.
                self.assertLess(last.max_energy_drift, 0.01)

    def test_scale_invariance(self):
        """S=5 and S=10 must trace the same normalized trajectory."""
        states_5 = simulate_preset("FIGURE_8", scale=5.0)
        states_10 = simulate_preset("FIGURE_8", scale=10.0)

        final_5 = states_5[-1].positions
        final_10 = states_10[-1].positions
        np.testing.assert_allclose(final_10 / 10.0, final_5 / 5.0, rtol=1e-6, atol=1e-6)

    def test_frame_count_and_initial_state(self):
        preset = presets.PRESETS["FIGURE_8"]
        masses, positions, velocities, G, softening = scaled_inputs(preset, 5.0)
        states = list(algo.simulate_frames(
            masses, positions, velocities,
            start_frame=1, end_frame=10, fps=FPS,
            G=G, softening=softening, substeps=preset.steps_per_frame,
        ))
        self.assertEqual([state.frame for state in states], list(range(1, 11)))
        np.testing.assert_allclose(states[0].positions, positions)
        np.testing.assert_allclose(states[0].velocities, velocities)
        self.assertFalse(np.allclose(states[-1].positions, positions))

    def test_cancel_stops_early(self):
        preset = presets.PRESETS["FIGURE_8"]
        masses, positions, velocities, G, softening = scaled_inputs(preset, 5.0)
        seen = []

        def cancel():
            return len(seen) >= 3

        for state in algo.simulate_frames(
                masses, positions, velocities,
                start_frame=1, end_frame=100, fps=FPS,
                G=G, softening=softening, substeps=preset.steps_per_frame,
                cancel=cancel):
            seen.append(state.frame)
        self.assertEqual(seen, [1, 2, 3])


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.preset = presets.PRESETS["FIGURE_8"]
        self.masses, self.positions, self.velocities, self.G, self.softening = scaled_inputs(
            self.preset, 5.0
        )

    def _run(self, **overrides):
        kwargs = dict(
            start_frame=1, end_frame=10, fps=FPS,
            G=self.G, softening=self.softening,
            substeps=self.preset.steps_per_frame,
        )
        kwargs.update(overrides)
        return list(algo.simulate_frames(
            self.masses, self.positions, self.velocities, **kwargs
        ))

    def test_invalid_frame_range(self):
        with self.assertRaises(ValueError):
            self._run(start_frame=10, end_frame=5)

    def test_invalid_fps(self):
        with self.assertRaises(ValueError):
            self._run(fps=0)

    def test_invalid_mass(self):
        bad = self.masses.copy()
        bad[0] = 0.0
        with self.assertRaises(ValueError):
            list(algo.simulate_frames(
                bad, self.positions, self.velocities,
                start_frame=1, end_frame=5, fps=FPS,
            ))

    def test_shape_mismatch(self):
        with self.assertRaises(ValueError):
            list(algo.simulate_frames(
                self.masses, self.positions[:2], self.velocities,
                start_frame=1, end_frame=5, fps=FPS,
            ))


class SafetyTests(unittest.TestCase):
    def test_speed_limit_aborts(self):
        masses = np.array([1.0, 1.0, 1.0])
        positions = np.array([[-1.0, 0, 0], [1.0, 0, 0], [0, 5, 0]])
        velocities = np.zeros((3, 3))
        with self.assertRaises(algo.StabilityError):
            list(algo.simulate_frames(
                masses, positions, velocities,
                start_frame=1, end_frame=10, fps=FPS,
                G=1.0, max_v_safety=1e-6,
            ))

    def test_collision_changes_trajectory(self):
        masses = np.array([1.0, 1.0])
        # Offset paths so the free solution misses the singularity but still
        # overlaps inside the combined radius (0.5 + 0.5).
        positions = np.array([[-1.0, -0.3, 0.0], [1.0, 0.3, 0.0]])
        velocities = np.array([[0.5, 0, 0], [-0.5, 0, 0]])
        radii = np.array([0.5, 0.5])

        def run(collision):
            return list(algo.simulate_frames(
                masses, positions, velocities,
                start_frame=1, end_frame=60, fps=FPS,
                softening=0.05, collision_radii=collision,
            ))

        free = run(None)
        hit = run(radii)

        self.assertFalse(np.allclose(free[-1].positions, hit[-1].positions))
        self.assertTrue(np.all(np.isfinite(hit[-1].positions)))

        # Repulsion must keep the bodies further apart than the pure-gravity
        # pass-through, which is the point of enabling collisions.
        min_free = min(float(np.linalg.norm(s.positions[0] - s.positions[1])) for s in free)
        min_hit = min(float(np.linalg.norm(s.positions[0] - s.positions[1])) for s in hit)
        self.assertGreater(min_hit, min_free)


class ManifestTests(unittest.TestCase):
    def test_manifest_matches_bl_info(self):
        import ast
        import tomllib

        with open(ROOT / "blender_manifest.toml", "rb") as handle:
            manifest = tomllib.load(handle)

        tree = ast.parse((ROOT / "__init__.py").read_text(encoding="utf-8"))
        bl_info = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "bl_info"
                    for target in node.targets):
                bl_info = ast.literal_eval(node.value)
        self.assertIsNotNone(bl_info)
        self.assertEqual(manifest["id"], "three_body_problem")
        self.assertEqual(".".join(str(part) for part in bl_info["version"]), manifest["version"])
        self.assertEqual(
            tuple(int(part) for part in manifest["blender_version_min"].split(".")),
            bl_info["blender"],
        )
        self.assertGreaterEqual(bl_info["blender"], (5, 2, 0))


if __name__ == "__main__":
    unittest.main()
