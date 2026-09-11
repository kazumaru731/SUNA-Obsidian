# SUNA — Obsidian

iPhoneのタイマー向けに制作した、オリジナルのBlender製砂時計です。
黒いチタン、細いシャンパンゴールドのインレイ、透明なガラス、淡い金色の砂で構成しています。

## 納品ファイル

- `output/SUNA_Obsidian.blend` — 編集用マスター。Blender 5.0.1で制作・検証。
- `output/renders/suna_hero.png` — 1100 × 1320、16bitのスタジオレンダー。
- `output/renders/suna_grain_detail.png` — 1200 × 1200、砂とガラスの拡大レンダー。
- `output/SUNA_motion.mp4` — 640 × 800、24fps、6秒の動作プレビュー。
- `output/SUNA_motion.gif` — 共有しやすい384 × 480のループプレビュー。
- `output/widget/suna_remaining_*.png` — 残量100 / 75 / 50 / 25 / 0%、1024 × 1024の透過PNG。
- `output/widget/manifest.json` — 画像名・残量・対応フレームの一覧。
- `output/widget/widget_preview.png` — 小さな表示サイズでの視認性確認。

## モデルと動き

ガラスは外側・内側を持つ中空メッシュです。壁厚は約1mm相当、屈折率は1.46。Cyclesで反射と屈折を計算し、縦長の光源で輪郭を出しています。ガラス、金属、砂のマテリアルはノードから調整できます。

砂には非金属の鉱物マテリアル、微細な凹凸、Geometry Nodesによる小さな多面体の粒を組み合わせています。上側は中心がくぼみながら減り、下側は斜面を持つ山として積もります。落下粒340個と着地付近の粒125個を個別に動かしています。

アニメーションは見た目を調整した決定的な動きです。砂量は数値積分で上下を対応させていますが、粒同士の衝突を全て解くDEM・剛体シミュレーションではありません。形状変化と粒の位置はシェイプキーに保存済みで、ファイルを開く際にPythonの自動実行を許可する必要はありません。

## Blenderでの使用

1. `output/SUNA_Obsidian.blend`を開きます。
2. 121フレームが標準の半分の状態です。1〜241フレーム、24fps、10秒で砂が移動します。
3. タイムラインのマーカーで100 / 75 / 50 / 25 / 0%へ移動できます。
4. HEROは全体、WIDGETは小型表示、MACROは砂の拡大用カメラです。
5. コレクション01〜04が本体、05が撮影環境、06がカメラです。

MP4はマスター全体の動きを6秒に短縮したプレビューです。編集用マスターの長さは10秒のままです。実際のタイマー時間に合わせる場合は、シェイプキーのアクションを同じ倍率でリタイミングしてください。

## iPhoneウィジェット向け

透過PNGは、背景を透過させつつスタジオの反射を残しています。任意の背景のリアルタイム屈折まで再現する画像ではないため、暗い背景・明るい背景の両方で合成結果を確認してください。

WidgetKitへの組み込みには、残量に対応するPNGをタイムラインの各状態へ割り当てる使い方を想定しています。連続した3D動画はアプリ内表示・動作確認用です。WidgetKitの更新とアニメーションはOSの制御を受けるため、この動画をウィジェットで常時再生する実装は本成果物には含みません。

- Apple: [Keeping a widget up to date](https://developer.apple.com/documentation/widgetkit/keeping-a-widget-up-to-date/)
- Apple: [Animating data updates in widgets and Live Activities](https://developer.apple.com/documentation/widgetkit/animating-data-updates-in-widgets-and-live-activities)
- Blender: [Glass BSDF](https://docs.blender.org/manual/en/5.0/render/shader_nodes/shader/glass.html)

## 再生成

追加のアドオンや外部テクスチャは不要です。

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe' --background --factory-startup --python .\create_hourglass.py
& 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe' --background --python .\render_delivery.py -- stills
& 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe' --background --python .\render_delivery.py -- animation
& 'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe' --background --python .\encode_animation.py
```

`output/checks/`に砂量・モデル再読込・画像の検証結果を保存しています。
