import numpy as np

def calculate_acceleration(positions, masses, G=1.0, softening=0.0):
    """
    各天体に働く加速度を計算します。
    positions: (N, 3) の配列
    masses: (N,) の配列
    G: 万有引力定数
    softening: 距離の計算に加える軟化係数 (epsilon)
    """
    N = positions.shape[0]
    acceleration = np.zeros_like(positions)
    
    for i in range(N):
        for j in range(N):
            if i == j:
                continue
            r_vec = positions[j] - positions[i]
            dist_sq = np.sum(r_vec**2)
            
            # 軟化係数を含めた距離の計算
            # a = G * m_j * r_vec / (r^2 + eps^2)^(3/2)
            denom = (dist_sq + softening**2)**(1.5)
            
            if denom > 1e-12:
                acceleration[i] += G * masses[j] * r_vec / denom
                
    return acceleration

def rk4_step(positions, velocities, masses, dt, G=1.0, softening=0.0):
    """
    4次ルンゲ＝クッタ法(RK4)を用いて、dt秒後の位置と速度を計算します。
    """
    def compute_derivatives(p, v):
        a = calculate_acceleration(p, masses, G, softening)
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

def handle_collisions(positions, velocities, masses, collision_radius):
    """
    天体同士の弾性衝突を処理します。
    """
    N = positions.shape[0]
    new_v = velocities.copy()
    
    for i in range(N):
        for j in range(i + 1, N):
            r_vec = positions[j] - positions[i]
            dist = np.linalg.norm(r_vec)
            
            if dist < collision_radius:
                # 衝突軸
                normal = r_vec / (dist + 1e-9)
                # 相対速度
                relative_v = new_v[j] - new_v[i]
                # 衝突軸方向の速度成分
                v_normal = np.dot(relative_v, normal)
                
                # 近づいている場合のみ反発させる
                if v_normal < 0:
                    # 弾性衝突の公式: v1_new = v1 - 2*m2/(m1+m2) * <v1-v2, p1-p2>/|p1-p2|^2 * (p1-p2)
                    m_sum = masses[i] + masses[j]
                    impulse = (2.0 * v_normal) / m_sum
                    
                    new_v[i] += impulse * masses[j] * normal
                    new_v[j] -= impulse * masses[i] * normal
                    
    return new_v

def rk45_adaptive_step(positions, velocities, masses, dt_frame, G=1.0, softening=0.0, collision_radius=0.0):
    """
    1フレーム分(dt_frame)の積分を実行するために、適応的時間刻みを用います。
    collision_radius > 0 の場合、弾性衝突処理を行います。
    """
    t_spent = 0.0
    curr_p = positions.copy()
    curr_v = velocities.copy()
    
    # 基本ステップサイズ（1フレームを小分割）
    h = dt_frame / 10.0
    
    while t_spent < dt_frame:
        if t_spent + h > dt_frame:
            h = dt_frame - t_spent
        
        # 衝突判定（ステップ実行前）
        if collision_radius > 0:
            curr_v = handle_collisions(curr_p, curr_v, masses, collision_radius)
            
        # 加速度と距離の確認
        acc = calculate_acceleration(curr_p, masses, G, softening)
        
        min_dist = float('inf')
        max_acc = 0.0
        for i in range(len(masses)):
            a_mag = np.linalg.norm(acc[i])
            if a_mag > max_acc: max_acc = a_mag
            for j in range(i+1, len(masses)):
                d = np.linalg.norm(curr_p[i] - curr_p[j])
                if d < min_dist: min_dist = d
        
        # 適応的ステップ制御
        # 1. 距離に基づく制限 (近接遭遇時の精度確保)
        # 2. 加速度に基づく制限 (力場が急変する場所で細かくする)
        max_v = np.linalg.norm(curr_v, axis=1).max()
        
        # 衝突回避のための安全なステップサイズ
        # h ~ 距離 / 速度
        safe_h_dist = 0.05 * min_dist / (max_v + 1e-6)
        
        # 加速度の変化に基づく制限 (エネルギー保存の向上)
        # h ~ sqrt(距離 / 加速度)
        safe_h_acc = 0.05 * np.sqrt(min_dist / (max_acc + 1e-6))
        
        h = min(h, safe_h_dist, safe_h_acc)
        
        # 最小ステップのクランプ（無限ループ防止）
        h = max(h, 1e-7)
        
        if t_spent + h > dt_frame: h = dt_frame - t_spent

        # RK4を用いて一歩進める
        curr_p, curr_v = rk4_step(curr_p, curr_v, masses, h, G, softening)
        t_spent += h
        
    return curr_p, curr_v

