import numpy as np

def calculate_acceleration(positions, masses, G=1.0, softening=0.0, radii=None):
    """
    各天体に働く加速度を計算します。
    radii: (N,) 各天体の半径。指定がある場合、反発力 (斥力) を付加します。
    """
    N = positions.shape[0]
    acceleration = np.zeros_like(positions)
    
    for i in range(N):
        for j in range(N):
            if i == j:
                continue
            r_vec = positions[j] - positions[i]
            dist_sq = np.sum(r_vec**2)
            dist = np.sqrt(dist_sq)
            
            # 1. 万有引力
            # a = G * m_j * r_vec / (r^2 + eps^2)^(3/2)
            denom = (dist_sq + softening**2)**(1.5)
            
            if denom > 1e-12:
                acceleration[i] += G * masses[j] * r_vec / denom

            # 2. 斥力 (衝突回避)
            if radii is not None:
                threshold = radii[i] + radii[j]
                if dist < threshold and dist > 1e-9:
                    # 以前の指数的な斥力モデル（逆4乗）
                    # 重力定数と質量に比例させ、距離の4乗で反比例
                    repulsion_mag = (G * masses[j]) * ((threshold / dist)**4 - 1.0)
                    acceleration[i] -= repulsion_mag * (r_vec / dist)
                
    return acceleration

def rk4_step(positions, velocities, masses, dt, G=1.0, softening=0.0, radii=None):
    """
    4次ルンゲ＝クッタ法(RK4)を用いて、dt秒後の位置と速度を計算します。
    """
    def compute_derivatives(p, v):
        a = calculate_acceleration(p, masses, G, softening, radii)
        return v, a

    v1, a1 = compute_derivatives(positions, velocities)
    v2, a2 = compute_derivatives(positions + v1 * dt / 2, velocities + a1 * dt / 2)
    v3, a3 = compute_derivatives(positions + v2 * dt / 2, velocities + a2 * dt / 2)
    v4, a4 = compute_derivatives(positions + v3 * dt, velocities + a3 * dt)
    
    next_positions = positions + (dt / 6.0) * (v1 + 2*v2 + 2*v3 + v4)
    next_velocities = velocities + (dt / 6.0) * (a1 + 2*a2 + 2*a3 + a4)
    
    return next_positions, next_velocities

def velocity_verlet_step(positions, velocities, masses, dt, G=1.0, softening=0.0):
    """
    Velocity Verlet法（2次シンプレクティック積分）を用いて、dt秒後の位置と速度を計算します。
    """
    acc_t = calculate_acceleration(positions, masses, G, softening)
    
    # 速度を半ステップ進める
    velocities_half = velocities + acc_t * (dt / 2.0)
    
    # 位置を全ステップ進める
    next_positions = positions + velocities_half * dt
    
    # 新しい位置での加速度を計算
    acc_next = calculate_acceleration(next_positions, masses, G, softening)
    
    # 速度をさらに半ステップ進める
    next_velocities = velocities_half + acc_next * (dt / 2.0)
    
    return next_positions, next_velocities

def rk45_adaptive_step(positions, velocities, masses, dt_frame, G=1.0, softening=0.0, collision_radii=None):
    """
    1フレーム分(dt_frame)の積分を実行するために、適応的時間刻みを用います。
    collision_radii: np.array([r1, r2, r3]) が渡された場合、計算に反映させます。
    """
    t_spent = 0.0
    curr_p = positions.copy()
    curr_v = velocities.copy()
    
    # 基本ステップサイズ（1フレームを小分割）
    h = dt_frame / 10.0
    
    while t_spent < dt_frame:
        if t_spent + h > dt_frame:
            h = dt_frame - t_spent
            
        # 加速度と距離の確認
        acc = calculate_acceleration(curr_p, masses, G, softening, collision_radii)
        
        min_dist = float('inf')
        max_acc = 0.0
        for i in range(len(masses)):
            # 斥力が働いている時は非常に大きくなる加速度を考慮
            a_mag = np.linalg.norm(acc[i])
            if a_mag > max_acc: max_acc = a_mag
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

