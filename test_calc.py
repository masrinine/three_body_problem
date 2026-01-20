import numpy as np
import matplotlib.pyplot as plt

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

    # k1
    v1, a1 = compute_derivatives(positions, velocities)
    
    # k2
    v2, a2 = compute_derivatives(positions + v1 * dt / 2, velocities + a1 * dt / 2)
    
    # k3
    v3, a3 = compute_derivatives(positions + v2 * dt / 2, velocities + a2 * dt / 2)
    
    # k4
    v4, a4 = compute_derivatives(positions + v3 * dt, velocities + a3 * dt)
    
    # 次のステップを計算
    next_positions = positions + (dt / 6.0) * (v1 + 2*v2 + 2*v3 + v4)
    next_velocities = velocities + (dt / 6.0) * (a1 + 2*a2 + 2*a3 + a4)
    
    return next_positions, next_velocities


# 使用例のデモ（軌跡の描画）
if __name__ == "__main__":
    # 3つの天体の質量
    masses = np.array([1.0, 1.0, 1.0])
    
    # 初期座標 (x, y, z) - 8の字軌道の例に近い設定
    positions = np.array([
        [0.97000436, -0.24308753, 0.0],
        [-0.97000436, 0.24308753, 0.0],
        [0.0, 0.0, 0.0]
    ])
    
    # 初期速度 (vx, vy, vz)
    v_const = [0.46620368, 0.43236573, 0.0]
    velocities = np.array([
        v_const,
        v_const,
        [-2 * v_const[0], -2 * v_const[1], 0.0]
    ])
    
    dt = 0.1
    total_steps = 5
    
    # 軌跡保存用のリスト
    history = [positions.copy()]
    
    # シミュレーション実行
    curr_p, curr_v = positions, velocities
    for _ in range(total_steps - 1):
        curr_p, curr_v = rk4_step(curr_p, curr_v, masses, dt)
        history.append(curr_p.copy())
    
    history = np.array(history) # (steps, bodies, coordinates)
    
    # プロット
    plt.figure(figsize=(8, 8))
    colors = ['r', 'g', 'b']
    labels = ['Star 1', 'Star 2', 'Star 3']
    
    for i in range(3):
        # 軌跡（線）ではなく、点を描画
        plt.scatter(history[:, i, 0], history[:, i, 1], color=colors[i], label=labels[i], s=30)

    plt.title("Three-Body Problem (RK4, 10 Points per Star)")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid(True)
    plt.axis('equal')
    
    # PNGとして保存
    output_path = "trajectories.png"
    plt.savefig(output_path)
    print(f"軌跡を {output_path} に保存しました。")
