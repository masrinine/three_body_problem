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
    Vectorized calculation of gravitational and repulsive forces.
    """
    N = positions.shape[0]
    # Matrix of displacement vectors (N, N, 3)
    # diff[i, j] = positions[j] - positions[i]
    diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
    
    # Square of distances (N, N)
    dist_sq = np.sum(diff**2, axis=-1)
    # Add softening and avoid division by zero
    dist_inv3 = (dist_sq + softening**2)**(-1.5)
    np.fill_diagonal(dist_inv3, 0) # No self-gravity
    
    # Gravity: a_i = sum_j (G * m_j * diff_{ij} / dist_{ij}^3)
    # Result: (N, 3)
    acceleration = G * np.sum(masses[np.newaxis, :, np.newaxis] * diff * dist_inv3[:, :, np.newaxis], axis=1)

    # 2. 斥力 (Repulsion) と Damping
    if radii is not None:
        dist = np.sqrt(dist_sq)
        # Avoid division by zero on diagonal
        np.fill_diagonal(dist, 1.0)
        
        thresholds = radii[np.newaxis, :] + radii[:, np.newaxis]
        # Mask for pairs within contact
        contact_mask = (dist < thresholds) & (dist > 1e-9)
        np.fill_diagonal(contact_mask, False)

        if np.any(contact_mask):
            # Repulsion (r^-6)
            ratio = thresholds / dist
            repulsion_mag = (G * masses[np.newaxis, :]) * (ratio**6 - 1.0)
            # Apply only where in contact
            repulsion_mag = np.where(contact_mask, repulsion_mag, 0)
            acceleration -= np.sum(repulsion_mag[:, :, np.newaxis] * (diff / dist[:, :, np.newaxis]), axis=1)

            # Damping (relative velocity reduction)
            rel_vel = velocities[np.newaxis, :, :] - velocities[:, np.newaxis, :]
            # Dot product of relative velocity and displacement
            vel_in_r_component = np.sum(rel_vel * diff, axis=-1) / (dist_sq + 1e-12)
            
            # Damp only when objects are moving toward each other (vel_in_r_component < 0)
            damp_mask = contact_mask & (vel_in_r_component < 0)
            damping_factor = 0.5 * (ratio - 1.0)
            damping_force = np.where(damp_mask[:, :, np.newaxis], 
                                     damping_factor[:, :, np.newaxis] * rel_vel * masses[np.newaxis, :, np.newaxis], 
                                     0)
            acceleration -= np.sum(damping_force, axis=1)
                
    return acceleration

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
