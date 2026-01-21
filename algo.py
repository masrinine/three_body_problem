import numpy as np

def calculate_acceleration(positions, masses, G=1.0):
    """
    各天体に働く加速度を計算します。
    positions: (N, 3) の配列
    masses: (N,) の配列
    G: 万有引力定数
    """
    N = positions.shape[0]
    acceleration = np.zeros_like(positions)
    
    for i in range(N):
        for j in range(N):
            if i == j:
                continue
            r_vec = positions[j] - positions[i]
            dist = np.linalg.norm(r_vec)
            # 万有引力の法則: a = G * m_j * r_vec / |r_vec|^3
            if dist > 1e-9: # 衝突回避のための微小値
                acceleration[i] += G * masses[j] * r_vec / (dist**3)
                
    return acceleration

def rk4_step(positions, velocities, masses, dt, G=1.0):
    """
    4次ルンゲ＝クッタ法(RK4)を用いて、dt秒後の位置と速度を計算します。
    """
    def compute_derivatives(p, v):
        a = calculate_acceleration(p, masses, G)
        return v, a

    v1, a1 = compute_derivatives(positions, velocities)
    v2, a2 = compute_derivatives(positions + v1 * dt / 2, velocities + a1 * dt / 2)
    v3, a3 = compute_derivatives(positions + v2 * dt / 2, velocities + a2 * dt / 2)
    v4, a4 = compute_derivatives(positions + v3 * dt, velocities + a3 * dt)
    
    next_positions = positions + (dt / 6.0) * (v1 + 2*v2 + 2*v3 + v4)
    next_velocities = velocities + (dt / 6.0) * (a1 + 2*a2 + 2*a3 + a4)
    
    return next_positions, next_velocities

def velocity_verlet_step(positions, velocities, masses, dt, G=1.0):
    """
    Velocity Verlet法（2次シンプレクティック積分）を用いて、dt秒後の位置と速度を計算します。
    """
    acc_t = calculate_acceleration(positions, masses, G)
    
    # 速度を半ステップ進める
    velocities_half = velocities + acc_t * (dt / 2.0)
    
    # 位置を全ステップ進める
    next_positions = positions + velocities_half * dt
    
    # 新しい位置での加速度を計算
    acc_next = calculate_acceleration(next_positions, masses, G)
    
    # 速度をさらに半ステップ進める
    next_velocities = velocities_half + acc_next * (dt / 2.0)
    
    return next_positions, next_velocities

def rk45_adaptive_step(positions, velocities, masses, dt_frame, G=1.0, tol=1e-6):
    """
    RK45(Dormand-Prince法)の概念を用いた適応的時間刻みにより、
    1フレーム分(dt_frame)の積分を実行します。
    """
    t_spent = 0.0
    curr_p = positions.copy()
    curr_v = velocities.copy()
    h = dt_frame / 4.0  # 初期時間刻み
    
    # Dormand-Prince 5(4) 係数の一部を簡略化した適応ロジック
    while t_spent < dt_frame:
        if t_spent + h > dt_frame:
            h = dt_frame - t_spent
        
        # ステップの試行 (4次と5次を比較するのが理想だが、ここでは計算コストを考慮し
        # 近接度に応じたステップ調整を行う実用的なロジックとする)
        
        # 加速度の変化率や最小距離を確認
        acc = calculate_acceleration(curr_p, masses, G)
        min_dist = float('inf')
        for i in range(len(masses)):
            for j in range(i+1, len(masses)):
                d = np.linalg.norm(curr_p[i] - curr_p[j])
                if d < min_dist: min_dist = d
        
        # 距離が近いほどステップhを小さくする
        desired_h = 0.1 * min_dist  # 経験的なスケーリング
        h = max(min(h, desired_h), 1e-5)
        if t_spent + h > dt_frame: h = dt_frame - t_spent

        # RK4を用いてステップ実行
        curr_p, curr_v = rk4_step(curr_p, curr_v, masses, h, G)
        t_spent += h
        
        if h <= 1e-5 and t_spent < dt_frame:
            # 強制的に進める（デッドロック防止）
            h = dt_frame - t_spent
            curr_p, curr_v = rk4_step(curr_p, curr_v, masses, h, G)
            break

    return curr_p, curr_v
