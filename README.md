# Three Body Problem - Blender Addon

Blender 上で複雑な三体問題（Three-Body Problem）の数値シミュレーションを行い、天体のアニメーションを自動生成するアドオンです。

## 動作環境

- **Blender 5.2 LTS 以降**（スロット付きアクション API を使用するため、5.2 未満では動作しません）
- 追加の Python パッケージは不要です（Blender 同梱の `numpy` のみを使用）
- 対応バージョンの検証状況とリリースチェックリストは [COMPATIBILITY.md](COMPATIBILITY.md) を参照してください。

## インストール

1. `dist/three_body_problem-1.1.0-extension.zip` を用意します（同梱されていない場合は `python tools/build_addon.py` で生成できます）。
2. Blender の `Edit > Preferences > Get Extensions` を開き、右上のメニューから `Install from Disk...` を選び、zip を指定します。
3. `Preferences > Add-ons` で "Three Body Problem" を有効化します。

旧形式（`bl_info`）でのインストールが必要な場合は `dist/three_body_problem-1.1.0-legacy.zip` を `Install from Disk...` に指定してください。

## 特徴

- **厳選されたプリセットモデル**: 制御の難しい三体問題において、数学的に興味深い挙動を示す9つのモデルをプリセットとして用意。
- **高精度な数値計算**: 適応刻みのルンゲ＝クッタ法（RK45）と、エネルギー保存に優れた Leapfrog 法を切り替え可能。
- **3Dシミュレーション**: 平面的な動きだけでなく、3次元的に複雑に絡み合う立体的な軌道解にも対応。
- **自動ベイク機能**: シミュレーション結果をロケーションキーフレームとして書き出し、即座にレンダリングや編集が可能。キーフレームはリニア補間で作成されます。
- **安全なアンバイク**: ベイク後に `Unbake All` を押すと、ロケーションキーだけを削除します。回転・スケールなど他のアニメーションは保持されます。
- **スケーラブルな調整**: 位置と速度はワールド座標で保持され、`Simulation Scale` の変更時には自動的に再スケールされます（万有引力定数は S³ でスケール）。

## 搭載プリセット

### 2D / 準安定モデル
- **Figure-Eight**: 3つの天体が「8の字」を描きながら追いかけ合う最も有名な安定解。
- **Lagrangian Points (L4)**: 重い二天体のラグランジュ点において、小さな天体が安定して留まる系。
- **Pythagorean**: 3:4:5 の質量比を持つ三体が、カオス的で激しい相互作用の末に一星が弾き飛ばされる古典的問題。

### 3D / 立体モデル
- **The Dragon**: 空間をひねりながら移動する、3次元的な8の字の変種。
- **Butterfly 3D**: 二天体のペアの周囲を、第三の天体が「蝶の羽」のように上下左右に大きく横断。
- **The Yarn**: 特定の平面に捕らわれず、空間を毛糸玉のように均等に埋めていく高難度な3D解。
- **Chaotic Clover 3D / Double Hex 3D / Pythagorean 3D**: 長時間のカオス挙動を示す発展的な3Dモデル。

## 使用方法

1. **セットアップ**: サイドバーの `three_body_problem` タブで `Auto Setup` を押すと、UV球が3つ作成され自動的に割り当てられます（既存オブジェクトを使う場合は Body 1〜3 に割り当ててください）。
2. **モデル選択**: `Preset Model` から好みの挙動を選択します。プリセットは必ず3体で使用します。
3. **調整**: `Simulation Scale` で広がりを、`Time Scale` で速さを調整します。位置・速度はワールド座標として表示されます。
4. **実行**: `Bake All` を押すと、指定したフレーム範囲（`Start Frame`〜`End Frame`）にキーフレームが生成され、シーンのフレーム範囲もその範囲に設定されます。
5. **やり直し**: 別の設定で再ベイクする場合は、先に `Unbake All` を押してください。ベイク中に入力パネルはロックされます。

### 衝突判定
- `Enable Collision` を有効にすると、天体同士の反発・減衰が働きます。
- 衝突半径は**ワールド座標の半径**（直径ではありません）として扱われます。
- `Auto Radius` はメッシュの頂点から実際のサイズを計算します（モディファイアは考慮しません）。手動指定の場合は `Manual Radius`、微調整は `Radius Offset` を使用します。

## Tips
- **軌跡の表示**: Blender の `Motion Paths`（オブジェクトプロパティ > モーションパス）を有効にすると、美しい幾何学的な軌道を確認しやすくなります。
- **速度ベクトルの表示**: サイドバーの `Viewport Display` で `Show Velocity Vectors` を切り替え、`Gizmo Drawing Scale` で矢印の長さを調整できます。この設定は表示専用のため、ベイク後でも変更できます。
- **積分法の選択**: 円軌道など長時間の安定性が重要な場合は `Leapfrog`、近接遭遇が多い系では `RK45` が適しています。
- **開発時のデバッグ**: VS Code の `Blender Development` 拡張機能を用い、アドオンのロード/リロードが可能です。

## 開発者向け

- 構文チェック:
  ```powershell
  python -m py_compile __init__.py algo.py bake.py gizmos.py handlers.py keyframes.py operators.py panels.py presets.py properties.py
  ```
- 物理コアのテスト（`bpy` 不要、`.venv` の numpy を使用）:
  ```powershell
  .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
  ```
- Blender 統合テスト（ヘッドレス）:
  ```powershell
  & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python-exit-code 1 --python tests\blender_test.py
  ```
- パッケージ生成:
  ```powershell
  python tools\build_addon.py
  & 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --command extension validate dist\three_body_problem-1.1.0-extension.zip
  ```

## ライセンス

[LICENSE](LICENSE) を参照してください。現在は MIT を仮採用しており、最終的なライセンス判断は `TASKS.md` の最後のタスクで行います。
