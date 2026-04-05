"""
Preset Models for Three Body Problem.
Contains initial conditions and parameters for famous three-body configurations.
Sources follow established numerical studies (e.g., Chenciner & Montgomery for Figure-8).
"""
import numpy as np

class ThreeBodyPreset:
    def __init__(self, name, masses, positions, velocities, G=1.0, softening=0.01, steps_per_frame=10):
        self.name = name
        self.masses = np.array(masses)
        self.positions = np.array(positions)
        self.velocities = np.array(velocities)
        self.G = G
        self.softening = softening
        self.steps_per_frame = steps_per_frame # Internal sub-stepping for precision

PRESETS = {
    'FIGURE_8': ThreeBodyPreset(
        name="Figure-Eight (Stable)",
        masses=[1.0, 1.0, 1.0],
        # Coordinates from Chenciner & Montgomery (2000)
        positions=[
            [0.97000436, -0.24308753, 0.0],
            [-0.97000436, 0.24308753, 0.0],
            [0.0, 0.0, 0.0]
        ],
        velocities=[
            [0.466203685, 0.43236573, 0.0],
            [0.466203685, 0.43236573, 0.0],
            [-0.93240737, -0.86473146, 0.0]
        ],
        G=1.0,
        softening=0.0, # Figure-8 is mathematically precise without softening
        steps_per_frame=20
    ),
    
    'LAGRANGE_L4': ThreeBodyPreset(
        name="Lagrange Point L4 (Restricted)",
        masses=[100.0, 1.0, 0.001], # Sun, Planet, Small Body
        positions=[
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [5.0, 8.660254, 0.0] # 60 degrees (Equilateral triangle)
        ],
        velocities=[
            [0.0, 0.0, 0.0],
            [0.0, 3.162277, 0.0], # Keplerian velocity v = sqrt(G*M/R)
            [-2.7386, 1.5811, 0.0] # Velocity for circular orbit at L4
        ],
        G=1.0,
        softening=0.01,
        steps_per_frame=10
    ),

    'PYTHAGOREAN': ThreeBodyPreset(
        name="Pythagorean Problem (Burrau's Problem)",
        masses=[3.0, 4.0, 5.0],
        positions=[
            [1.0, 3.0, 0.0],
            [-2.0, -1.0, 0.0],
            [1.0, -1.0, 0.0]
        ],
        velocities=[
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0]
        ],
        G=1.0,
        softening=0.05, # Pythagorean problem has close encounters, softening required
        steps_per_frame=50 # High precision needed for chaotic changes
    ),

    'DRAGON': ThreeBodyPreset(
        name="The Dragon (3D)",
        masses=[1.0, 1.0, 1.0],
        # Initial conditions inspired by Šuvakov & Dmitrašinović 3D periodic solutions
        # Adjusted for visual 3D movement
        positions=[
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 0.5]
        ],
        velocities=[
            [0.0, 0.8, 0.3],
            [0.0, -0.8, 0.3],
            [0.0, 0.0, -0.6]
        ],
        G=1.5,
        softening=0.02,
        steps_per_frame=40
    ),

    'BUTTERFLY_3D': ThreeBodyPreset(
        name="Butterfly 3D (Hill's Type)",
        masses=[10.0, 10.0, 1.0],
        positions=[
            [1.5, 0.0, 0.1],
            [-1.5, 0.0, -0.1],
            [0.0, 0.0, 0.0]
        ],
        velocities=[
            [0.0, 1.2, 0.2],
            [0.0, -1.2, -0.2],
            [0.0, 0.0, 0.5]
        ],
        G=2.0,
        softening=0.05,
        steps_per_frame=30
    ),

    'YARN': ThreeBodyPreset(
        name="The Yarn (Spherical 3D)",
        masses=[1.0, 1.0, 1.0],
        positions=[
            [1.0, 1.0, 1.0],
            [-1.0, -1.0, 1.0],
            [0.0, 0.0, -1.0]
        ],
        velocities=[
            [0.5, -0.5, 0.2],
            [-0.5, 0.5, 0.2],
            [0.0, 0.0, -0.4]
        ],
        G=1.2,
        softening=0.03,
        steps_per_frame=40
    )
}
