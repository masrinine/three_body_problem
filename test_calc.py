import numpy as np
import matplotlib.pyplot as plt
from algo import rk4_step

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
