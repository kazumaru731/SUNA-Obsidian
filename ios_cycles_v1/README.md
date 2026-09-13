# SUNA Obsidian — iOS Cycles 素材

元の Blender 5.0.1 完成データから、砂量を固定した2秒ループを生成するローカル実装です。カメラ、ガラス、砂、刻印、背景、照明、床の反射、AgX 色管理を保持します。

**納品状態は `manifest.json` の `status` と `validatedClipCount` を確認してください。** `partial` は途中の素材です。101本の復号・検証とZIP作成がすべて成功した場合だけ、`checks/completion.json` が作成されます。試作ZIPと完成ZIPは別名です。

## 保存場所

- アプリ用素材：`D:\Projects\suna\ios_cycles_v1\`
- PNGマスター：`D:\Projects\suna\ios_cycles_v1_masters\frames\remaining_NNN\frame_0000.png` ～ `frame_0047.png`
- 原本の保管コピー：`D:\Projects\suna\ios_cycles_v1_masters\source\`
- 検証済み受け渡しZIP：`ios_cycles_v1\handoff\`
- 現在の進捗：`checks/batch_status.json`、各フレーム：`checks/worker_status.json`
- 実測時間・容量・未生成の残量：`checks/validation.json`

初期試作で砂のテクスチャ座標が変わる問題を発見し、修正しました。比較用の旧試作は `ios_cycles_v1_masters/archive/rest_coordinates_trial/` に隔離してあります。アプリ用素材や完成判定には使用しません。

## 出力仕様

880×1056、正方画素、24fps、48フレーム、2秒。時刻は0～47/24秒で、2秒地点の重複フレームはありません。`remaining_100.mp4` は上が全量、`remaining_000.mp4` は下が全量です。**ファイル名は残量であり、経過率ではありません。**

| 素材 | 内容 |
|---|---|
| `clips/remaining_001.mp4` ～ `remaining_100.mp4` | 残量固定、落下・着地粒だけが周期運動 |
| `clips/remaining_000.mp4` | 流れのない終了状態、復号後も同一の48フレーム |
| `stills/idle_full.png` | 開始前の上側全量、流れなし |
| `stills/finished_empty.png` | 終了時の下側全量、流れなし |

Cycles 192サンプル、適応閾値0.01、OPTIX／RTX 2080 Ti、OIDN Accurate、固定シード0。反射・透過バウンスは元の16／12／8／16。HEROカメラ、AgX、Medium High Contrast、露出0.35、ガンマ1を使用します。モーションブラーは使用しません。

PNGは背景込み16bit RGB、表示変換済みsRGBです。MP4はH.264 High、level 4.1、yuv420p、CRF 14、slow、音声なし、CFR 24fps、先頭IDR、fast start。sRGBからBT.709の伝達関数・マトリクス・リミテッドレンジへ `zscale` で実変換し、BT.709として明記します。メタデータの付け替えだけで済ませていません。0%では同一のIDRデータを48回使用し、Pフレーム圧縮による静止画の微小変化も防ぎます。

実際のエンコードコマンドと全フレームの誤差測定は `checks/clips/remaining_NNN.json` にあります。復号後の比較ではBT.709をsRGBへ逆変換します。比較数値はPillowが読み出した8bit表示値で算出します。保存されたPNG自体は16bitです。

## 砂量と運動

元のシェイプキーを残量に対応するフレーム `1 + (100 - 残量%) × 2.4` で評価します。元のBasisと未変形メッシュを保持し、専用の固定シェイプキーに評価済み座標を設定します。これにより、砂材質のGenerated座標と元の凹凸模様が変化しません。

粒は元の340落下粒＋125着地粒を使用します。粒ID、サイズの乱数、材質、密度、共通シード29を維持します。周期を閉じるため落下周期を毎秒2.6回から2.5回、着地周期を2.8回から3回へ調整しています。粒の回転も2秒で同じ姿勢になります。元の制作と同じく演出した粒運動であり、粒状体の物理シミュレーションではありません。

軌道は時刻から直接評価します。リセットをまたぐ位置の補間は行いません。落下は着地点から喉元、着地粒は砂面から中央接地点へ再出現します。着地点は各残量の元の下側メッシュに追従します。ガラスの屈折・反射、影まで含めたシーン全体を毎フレームCyclesで描画します。

## Macアプリ側への受け渡し

時計から残量 `r` を求め、`p = clamp(r, 0, 1) × 100`、`lo = floor(p)`、`hi = min(100, lo + 1)`、`weight = p - lo` とします。`lo` と `hi` の動画を**同じ位相**で表示します。共通の再生時計から `phase = time % 2`、フレームインデックス `floor(phase × 24)` を使用します。

混合は正しい色管理で映像を復号した後、線形光RGBで行います。非線形のsRGB/BT.709値を単純に平均すると、中間の明るさが試作と異なります。`previews/loop_and_transition_check.mp4` はこの混合方法で作成しています。初期状態は待機PNG、開始直後は100%動画、終了時は終了PNGです。1%→0%の間は静止0%動画と同位相で混合できます。

表示は5:6の縦横比を維持し、砂時計と床の反射をクロップしないレイアウトにします。混合確認動画は納品MP4を復号したフレーム同士で作成しており、それぞれのH.264圧縮の影響も含みます。

画素の混合は実際の中間3D形状の描画と完全には一致しません。特に拡大時の細粒とガラス越しの砂面には混合の差が残り得ます。試作の確認範囲と判定は `checks/pilot_gate.json` を参照してください。iPhoneの表示・署名・インストール・一時停止等のアプリ制御はMac側の担当です。ウィジェットの既存5段階PNGも変更していません。

## 実行・再開・停止

このWindows環境ではBlender 5.0.1、Python 3＋numpy＋Pillow、同梱のローカルFFmpegを使用します。モデルやスクリプトを変更すると署名が変わり、古いフレームの混入を拒否します。元の `output/SUNA_Obsidian.blend` には保存しません。

PowerShellでプロジェクトフォルダから実行します。

```powershell
Set-Location D:\Projects\suna

# 試作。すでに正常なフレームは再利用
& .\ios_cycles_v1\scripts\Start-Render.ps1 -Stage pilot

# 試作の目視・数値検証合格後だけ全量を開始可能
& .\ios_cycles_v1\scripts\Start-Render.ps1 -Stage full

# 現在描画中の1フレームを保存して停止
& .\ios_cycles_v1\scripts\Stop-Render.ps1

# プロセス終了後、検証済みフレームから続行
& .\ios_cycles_v1\scripts\Resume-Render.ps1 -Stage full

Get-Content .\ios_cycles_v1\checks\batch_status.json
& .\ios_cycles_v1\scripts\Show-Status.ps1
```

バッチは非表示プロセスで動作します。実行中は自動スリープを一時的に抑制し、画面は通常どおり消灯可能です。終了時は通常のスリープ設定に戻します。PCの再起動・電源断の後は再開コマンドを実行してください。破損フレームはCRC・全PNG展開・SHA-256で識別して再生成し、正常フレームは描画し直しません。チェックサムと設定署名の一致する動画は再エンコードしません。

手動でワーカーだけを使用する場合、同じフォルダに対して別のバッチを同時実行しないでください。

原本リポジトリを別の環境に復元する場合は、先に `benchmark_source.py` をBlenderで実行し、監査記録・基準再描画・待機/終了PNGを生成します。その後、試作生成と `diagnose_grains.py` によるデノイズ比較を行います。`tools/` の固定FFmpeg環境とPythonのnumpy/Pillowも必要です。レビュー済みの設定を変更した場合は、新しいマスター保存フォルダへ旧成果物を保管してから新しい検証を開始してください。

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe' --background --python-exit-code 1 --python .\ios_cycles_v1\scripts\render_cycles.py -- --states 0,1,49,50,51,100

$taskPython = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPython .\ios_cycles_v1\scripts\encode_assets.py --states 0,1,49,50,51,100
& $taskPython .\ios_cycles_v1\scripts\audit_decoded_motion.py --states 0,1,49,50,51,100
& $taskPython .\ios_cycles_v1\scripts\audit_trajectories.py
& $taskPython .\ios_cycles_v1\scripts\make_previews.py
& $taskPython .\ios_cycles_v1\scripts\package_delivery.py --archive

# 全101本の検証済み素材がなければ失敗する完成パッケージ作成
& $taskPython .\ios_cycles_v1\scripts\package_delivery.py --archive --require-complete
```

`pilot_gate.json` は実際の比較結果に基づくレビュー記録です。未確認のまま `passed` を変更しないでください。出力途中の `.partial.*` は納品に含めません。すべてのフレームと動画の保存・完了記録を段階的に確定します。失敗・未完了を成功扱いする処理はありません。

## 検証と見積もり

`checks/source_audit.json` に原本・カメラ・色管理・静止画の確認、`reservoir_validation.json` に全101残量の単調性と体積、`motion_validation.json` と `trajectory_validation.json` に周期・粒ID・再出現位置の検証を記録します。元の形状を保持した補間における最大総体積誤差は約0.87%です。

代表フレームの初期実測は約12秒。動的4800フレームの描画は約16時間、PNGは約17GB（10進GB）を見込んでいます。エンコード・検証・他のGPU負荷により増減します。最新の実測平均、残り時間の推定、完成済みMP4の容量は `checks/validation.json` と進捗JSONを優先してください。完成済みファイル数と未完了の一覧は混同せず記録します。

ZIPには動画・静止画・比較資料・manifest・検証・生成スクリプトを含め、PNG連番、原本の大容量コピー、FFmpeg本体、作業ログ、旧試作を除きます。PNGマスターと再生成環境はこのPCに分けて保管します。GitHubへのpush・Release作成・公開はこの実装では行いません。

## ツールの出典

ローカルFFmpegは [FFmpeg公式のWindows配布案内](https://ffmpeg.org/download.html) から案内される [Gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/) の `ffmpeg-9.0.1-essentials_build` です。取得ZIPのSHA-256は `fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9`。`tools/ffmpeg-release-essentials.zip` と展開フォルダをローカルに保持しています。システムへのインストールやPATH変更は行っていません。変換設定は [FFmpeg zscaleドキュメント](https://ffmpeg.org/ffmpeg-filters.html#zscale) に従います。

原本コミット：`56776a098ca4da6d38daafd3717b8507c4d4197a`。Blender原本SHA-256：`af18c618df4c096ff7580d97f963bd9ba9ec38cc43f8c0d654a9cc3ba879da9f`。依頼書は `docs/BLENDER_HANDOFF_JA.md` に保管しています。
