# SUNA：開始時の反転映像とアプリアイコン

既存のBlender 5.0.1原本から、開始前に一度だけ再生する反転映像と、同じ砂時計のアプリアイコンを追加制作しています。成果物の完成状態は `manifest.json` を参照してください。`complete_assets` は素材制作の完了を表し、iOSアプリへの組み込み・実機確認を意味しません。

| ファイル | 用途 |
|---|---|
| `clips/start_flip.mp4` | 1.25秒・24fps・30フレーム、880×1056。開始時に一度だけ再生 |
| `stills/prepare_bottom.png` | 準備姿勢。反転映像の先頭と同じ画像 |
| `icons/AppIcon1024.png` | SUNA本体のAppIcon用。1024×1024、不透明RGB、8bit PNG |
| `previews/flip_to_timer.mp4` | 準備→反転→既存の落砂映像という接続の確認 |
| `previews/all_frames.png` | 全30フレームの一覧 |
| `previews/transition_match.png` | 最終姿勢・砂量・色と既存映像の比較 |
| `previews/icon_sizes.png` | 小さい表示サイズでのアイコン確認 |
| `blend/SUNA_flip_baked.blend` | 背景・カメラ固定、本体と砂のアニメーションをベイク済み。スクリプト自動実行不要 |
| `docs/MAC_INTEGRATION_JA.md` | アプリ側の実装契約と確認項目 |

## 再生契約

`prepare_bottom.png` → `start_flip.mp4` を一度再生 → 既存の `ios_cycles_v1/clips/remaining_100.mp4` の位相0、という順で使います。1.25秒の準備時間はタイマー時間に含めません。残量100%は上側に砂が全量ある状態です。

準備姿勢では本体自体が上下逆です。反転すると既存のHERO構図へ戻り、文字の向きも揃います。画面全体を回転させる処理は不要です。準備・失敗・背景移行の扱いは引き継ぎ文書に記載しています。

## 制作と検証

Cycles 192サンプル、元のガラス・金属・砂材質、反射・屈折バウンス、照明、床、HEROカメラ、AgX色管理を維持しています。アイコンのみ正方形用の既存WIDGETカメラを使います。

砂は、下向きのワールド重力に応答する体積制約付き砂面と、重力・動く内壁・砂面との接触を計算する800粒の表層粒を組み合わせた演出用ベイクです。粒同士の衝突を含む完全なDEMシミュレーションではありません。回転中に砂面が内壁に沿って移動し、最後は元の砂面へ滑らかに戻ります。砂面の頂点と三角形内部、粒の半径込みで内壁とのクリアランスを検査します。

`checks/bake_validation.json` は砂量・内壁・終端形状、`framing_validation.json` は画面内収まり・床との接触、`delivery_validation.json` は全動画フレームの復号・色・圧縮・既存映像への接続、`visual_review.json` は実際の目視結果です。

動画はsRGBのPNGからBT.709へ実変換したH.264 High、yuv420p、音声なしです。PNGは表示変換済みsRGBです。Blenderの31フレーム目は既存動画の位相0に一致する比較用端点で、30フレームのMP4には含めません。

## 再生成

このPCの `ios_cycles_v1_masters/original_reservoir_poses.npz`、既存の `ios_cycles_v1/scripts/` とローカルFFmpeg、Python＋numpy＋Pillowを使います。元の `.blend` と既存の101本は書き換えません。

1. Pythonで `scripts/bake_flip.py` を実行。
2. PowerShellで `& .\ios_flip_v1\scripts\Start-Render.ps1 -Icon` を実行。0〜30のマスターと比較端点、アイコンを非表示のBlenderプロセスで描画します。
3. Pythonで `scripts/deliver_flip.py` を実行してエンコード・数値検証。
4. 実物を目視確認した記録と映像ハッシュを `checks/visual_review.json` に保存。
5. `scripts/deliver_flip.py --package` で検証済みZIPを作成。

正常なフレームは入力署名・SHA-256・PNG全展開を確認して再利用します。`STOP_AFTER_FRAME` が存在すると次のフレーム前に一時停止します。再開するときだけこのマーカーを取り除いて同じコマンドを実行します。

PNG連番と中間ベイクはこのPCに分離保管します。既存の101本のMP4は追加ZIPに重複収録しません。Macでは既存の `ios_cycles_v1/` と新しい `ios_flip_v1/` の両方が必要です。
