import numpy as np
import time

class SimulationError(Exception):
    """Base exception for simulation safety triggers"""
    pass

class TimeoutError(SimulationError):
    pass

class StabilityError(SimulationError):
    pass

def calculate_acceleration(positions, velocities, masses, G=1.0, softening=0.0, radii=None):
    """
    Highly optimized vectorized calculation of gravitational and repulsive forces.
    """
    N = positions.shape[0]
    if N < 2:
        return np.zeros_like(positions)

    # 1. Gravitational Forces
    # diff[i, j] is the vector from body i to body j
    diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
    dist_sq = np.sum(diff**2, axis=-1)
    
    # NaN/Zero protection using softening and epsilon
    eps = 1e-12
    # Gravity falls off as 1/r^2, vector direction adds 1/r, total 1/r^3
    dist_inv3 = (dist_sq + softening**2 + eps)**(-1.5)
    
    # Mask out self-interaction
    diag_indices = np.arange(N)
    dist_inv3[diag_indices, diag_indices] = 0.0
    
    # Acceleration = sum_j (G * m_j * unit_vector_ij / dist_ij^2)
    # weights: (N, N, 1) = G * m_j * (dist_ij^2 + soft^2)^(-1.5)
    weights = (G * masses)[np.newaxis, :, np.newaxis] * dist_inv3[:, :, np.newaxis]
    acceleration = np.sum(weights * diff, axis=1)

    # 2. Repulsion and Damping (Collision handling)
    if radii is not None:
        dist = np.sqrt(dist_sq + eps)
        thresholds = radii[np.newaxis, :] + radii[:, np.newaxis]
        
        # Only compute where bodies actually overlap
        contact_mask = (dist < thresholds)
        # Exclude self-collision
        contact_mask[diag_indices, diag_indices] = False

        if np.any(contact_mask):
            # Ratio of (ideal distance / actual distance)
            # Clip to prevent extreme values if centers are nearly identical
            ratio = np.clip(thresholds / dist, 1.0, 10.0)
            
            # Repulsion Magnitude (Power law r^-6 for stability)
            # magnitude: (N, N)
            repulsion_mag = (G * masses[np.newaxis, :]) * (ratio**6 - 1.0)
            repulsion_mag = np.where(contact_mask, repulsion_mag, 0.0)
            
            # Add to acceleration (pointing away from collider)
            # diff is (pos_j - pos_i), so -diff is (pos_i - pos_j)
            # No need to divide by dist again if we normalize diff properly
            unit_diff = diff / dist[:, :, np.newaxis]
            acceleration -= np.sum(repulsion_mag[:, :, np.newaxis] * unit_diff, axis=1)

            # Damping (Relative velocity reduction)
            # rel_vel[i, j] = v_j - v_i
            rel_vel = velocities[np.newaxis, :, :] - velocities[:, np.newaxis, :]
            
            # Projection of relative velocity onto the collision normal (diff)
            # negative values mean they are moving towards each other
            vel_projection = np.sum(rel_vel * unit_diff, axis=-1)
            damp_mask = contact_mask & (vel_projection < 0)
            
            # Linear damping based on overlap depth
            damping_coeff = 0.5 * (ratio - 1.0)
            damping_force = np.where(damp_mask[:, :, np.newaxis], 
                                     damping_coeff[:, :, np.newaxis] * rel_vel * masses[np.newaxis, :, np.newaxis], 
                                     0.0)
            acceleration -= np.sum(damping_force, axis=1)
                
    return acceleration

def calculate_total_energy(positions, velocities, masses, G=1.0, softening=0.0):
    """
    Calculate total system energy (Kinetic + Potential).
    Hamiltonian H = T + V
    """
    N = positions.shape[0]
    if N < 2:
        return 0.0
    
    # 1. Kinetic Energy T = sum(0.5 * m_i * v_i^2)
    v_sq = np.sum(velocities**2, axis=-1)
    T = 0.5 * np.sum(masses * v_sq)
    
    # 2. Potential Energy V = -sum_{i<j} (G * m_i * m_j / dist_ij)
    # diff[i, j] is direction
    diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
    dist = np.sqrt(np.sum(diff**2, axis=-1) + softening**2 + 1e-12)
    
    # Potential weights
    m_prod = masses[np.newaxis, :] * masses[:, np.newaxis]
    V_matrix = -G * m_prod / dist
    
    # Only summed for i < j to avoid double counting and self-interaction
    # np.triu_indices(N, 1) gets indices for upper triangle excluding diagonal
    i_idx, j_idx = np.triu_indices(N, k=1)
    V = np.sum(V_matrix[i_idx, j_idx])
    
    return T + V

def rk4_step(positions, velocities, masses, dt, G=1.0, softening=0.0, radii=None):
    """
    4次ルンゲ＝クッタ法(RK4)を用いて、dt秒後の位置と速度を計算します。
    """
    def compute_derivatives(p, v):
        a = calculate_acceleration(p, v, masses, G, softening, radii)
        return v, a

    v1, a1 = compute_derivatives(positions, velocities)
    v2, a2 = compute_derivatives(positions + v1 * dt / 2, velocities + a1 * dt / 2)
    v3, a3 = compute_derivatives(positions + v2 * dt / 2, velocities + a2 * dt / 2)
    v4, a4 = compute_derivatives(positions + v3 * dt, velocities + a3 * dt)
    
    next_positions = positions + (dt / 6.0) * (v1 + 2*v2 + 2*v3 + v4)
    next_velocities = velocities + (dt / 6.0) * (a1 + 2*a2 + 2*a3 + a4)
    
    return next_positions, next_velocities

def leapfrog_step(positions, velocities, masses, dt, G=1.0, softening=0.0, radii=None):
    """
    Leapfrog (Drift-Kick-Drift) integrator. 
    Maintains energy conservation better than RK4 for orbital systems.
    """
    # 1. Half drift
    p_half = positions + velocities * (dt * 0.5)
    
    # 2. Full kick (Acceleration at half positions)
    acc = calculate_acceleration(p_half, velocities, masses, G, softening, radii)
    v_next = velocities + acc * dt
    
    # 3. Half drift
    p_next = p_half + v_next * (dt * 0.5)
    
    return p_next, v_next

def rk45_adaptive_step(positions, velocities, masses, dt_frame, G=1.0, softening=0.0, collision_radii=None, base_substeps=10, timeout_s=5.0, max_v_safety=1000.0):
    """
    1フレーム分(dt_frame)の積分を実行するために、適応的時間刻みを用います。
    collision_radii: np.array([r1, r2, r3]) が渡された場合、計算に反映させます。
    """
    start_time = time.time()
    t_spent = 0.0
    curr_p = positions.copy()
    curr_v = velocities.copy()
    
    # 基本ステップサイズ（1フレームを小分割）
    h = dt_frame / max(float(base_substeps), 1.0)
    
    while t_spent < dt_frame:
        # Time-out Check
        if time.time() - start_time > timeout_s:
            raise TimeoutError(f"Simulation frame exceeded {timeout_s}s limit.")

        if t_spent + h > dt_frame:
            h = dt_frame - t_spent
            
        # 加速度と距離の確認
        acc = calculate_acceleration(curr_p, curr_v, masses, G, softening, collision_radii)
        
        min_dist = float("inf")
        max_acc = 0.0
        for i in range(len(masses)):
            # 斥力が働いている時は非常に大きくなる加速度を考慮
            a_mag = np.linalg.norm(acc[i])
            if a_mag > max_acc: max_acc = a_mag
            
            # Speed safety check
            if np.linalg.norm(curr_v[i]) > max_v_safety:
                raise StabilityError(f"Body {i+1} exceeded speed limit ({max_v_safety}). Simulation aborted for stability.")

            for j in range(i+1, len(masses)):
                d = np.linalg.norm(curr_p[i] - curr_p[j])
                if d < min_dist: min_dist = d
        
        # 適応的ステップ制御
        max_v = np.linalg.norm(curr_v, axis=1).max()
        
        safe_h_dist = 0.05 * min_dist / (max_v + 1e-6)
        safe_h_acc = 0.05 * np.sqrt(min_dist / (max_acc + 1e-6))
        
        h = min(h, safe_h_dist, safe_h_acc)
        h = max(h, 1e-8) # ロールバック前の最小ステップ
        
        if t_spent + h > dt_frame: h = dt_frame - t_spent

        # RK4を用いて一歩進める
        curr_p, curr_v = rk4_step(curr_p, curr_v, masses, h, G, softening, collision_radii)
        t_spent += h
        
    return curr_p, curr_v
