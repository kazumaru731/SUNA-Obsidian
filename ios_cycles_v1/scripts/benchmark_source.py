"""Read-only source audit and exact-quality representative render in Blender."""
import bpy
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'ios_cycles_v1'
SOURCE = ROOT / 'output' / 'SUNA_Obsidian.blend'
EXPECTED = 'af18c618df4c096ff7580d97f963bd9ba9ec38cc43f8c0d654a9cc3ba879da9f'
sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
assert sha == EXPECTED, 'Source differs from the approved master; report before rendering.'
(OUT / 'previews').mkdir(exist_ok=True)
(OUT / 'stills').mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
s = bpy.context.scene
hero = bpy.data.objects['Camera / HERO — studio portrait']
assert s.camera == hero
original = {
    'camera': hero.name, 'matrixWorld': [list(v) for v in hero.matrix_world],
    'orthographicScale': hero.data.ortho_scale,
    'viewTransform': s.view_settings.view_transform, 'look': s.view_settings.look,
    'exposure': s.view_settings.exposure, 'gamma': s.view_settings.gamma,
    'displayDevice': s.display_settings.display_device,
    'bounces': {k: getattr(s.cycles, k) for k in ['max_bounces', 'transmission_bounces', 'glossy_bounces', 'transparent_max_bounces']},
    'denoiser': s.cycles.denoiser, 'denoisingUseGpu': s.cycles.denoising_use_gpu,
    'renderSeed': s.cycles.seed,
}
p = bpy.context.preferences.addons['cycles'].preferences
p.compute_device_type = 'OPTIX'
p.get_devices()
for d in p.devices:
    d.use = d.type == 'OPTIX'
s.cycles.device = 'GPU'
s.cycles.samples = 192
s.cycles.adaptive_threshold = .01
s.cycles.use_animated_seed = False
s.render.resolution_x, s.render.resolution_y = 880, 1056
s.render.resolution_percentage = 100
s.render.pixel_aspect_x = s.render.pixel_aspect_y = 1
s.render.image_settings.media_type = 'IMAGE'
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGB'
s.render.image_settings.color_depth = '16'
s.render.film_transparent = False
s.render.use_persistent_data = True
flow = bpy.data.objects['Quartz / accelerating stream and ballistic rebounds']
timings = []
for frame, hidden, rel in [
    (121, False, 'previews/reference_reproduced.png'),
    (1, True, 'stills/idle_full.png'),
    (241, True, 'stills/finished_empty.png'),
]:
    path = OUT / rel
    s.frame_set(frame)
    flow.hide_render = hidden
    s.render.filepath = str(path)
    start = time.monotonic()
    bpy.ops.render.render(write_still=True)
    timing = {'path': rel, 'seconds': time.monotonic()-start, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    timings.append(timing)
    print('BENCHMARK', json.dumps(timing), flush=True)
report = {'sourceSha256': sha, 'sourceCommit': '56776a098ca4da6d38daafd3717b8507c4d4197a', 'blenderVersion': bpy.app.version_string, 'originalScene': original, 'rendering': {'engine':'CYCLES','samples':192,'adaptiveThreshold':.01,'resolution':[880,1056],'pixelAspect':[1,1],'master':'16-bit RGB PNG / sRGB','device':'OPTIX'}, 'measurements':timings}
(OUT/'checks'/'source_audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
print('SOURCE_AUDIT_COMPLETE', flush=True)
