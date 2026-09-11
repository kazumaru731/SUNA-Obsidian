"""Render the portable SUNA master. Pass -- stills or -- animation."""
import bpy
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
mode=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'stills'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'SUNA_Obsidian.blend'))
s=bpy.context.scene
p=bpy.context.preferences.addons['cycles'].preferences
p.compute_device_type='OPTIX'
p.get_devices()
for d in p.devices:
    d.use=d.type=='OPTIX'
s.cycles.device='GPU'
s.render.image_settings.file_format='PNG'
s.render.image_settings.color_mode='RGBA'
s.render.resolution_percentage=100
s.render.use_file_extension=True

def render(path,frame=121,size=(1100,1320),samples=192):
    s.frame_set(int(frame),subframe=float(frame)%1)
    s.render.resolution_x,s.render.resolution_y=size
    s.cycles.samples=samples
    s.render.filepath=str(path)
    start=time.time()
    bpy.ops.render.render(write_still=True)
    print('DELIVERED',path.name,'seconds',round(time.time()-start,2),flush=True)

if mode=='stills':
    s.cycles.adaptive_threshold=.01
    s.render.image_settings.color_depth='16'
    render(OUT/'renders'/'suna_hero.png')
    s.camera=bpy.data.objects['Camera / MACRO — grains at the throat']
    render(OUT/'renders'/'suna_grain_detail.png',size=(1200,1200),samples=192)
    s.camera=bpy.data.objects['Camera / WIDGET — readable silhouette']
    bpy.data.objects['Studio / seamless graphite floor'].hide_render=True
    s.render.film_transparent=True
    s.cycles.film_transparent_glass=True
    s.cycles.film_transparent_roughness=.1
    s.render.image_settings.color_depth='8'
    manifest={'name':'SUNA Obsidian','format':'RGBA PNG / sRGB','size':[1024,1024],'glass':'Transparent-film glass, studio reflection retained','states':[]}
    for remaining in [100,75,50,25,0]:
        frame=1+(100-remaining)*2.4
        filename=f'suna_remaining_{remaining:03d}.png'
        render(OUT/'widget'/filename,frame,size=(1024,1024),samples=128)
        manifest['states'].append({'remainingFraction':remaining/100,'elapsedFraction':1-remaining/100,'frame':frame,'file':filename})
    (OUT/'widget'/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
elif mode=='animation':
    s.render.image_settings.color_depth='8'
    s.cycles.adaptive_threshold=.028
    s.cycles.use_animated_seed=True
    s.render.use_persistent_data=True
    # A six-second, 24 fps demonstration of the ten-second editable master.
    for index in range(144):
        frame=1+240*index/143
        path=OUT/'animation'/f'frame_{index:04d}.png'
        if path.exists():
            continue
        render(path,frame,size=(640,800),samples=40)
    (OUT/'animation'/'animation.json').write_text(json.dumps({'fps':24,'frames':144,'durationSeconds':6,'resolution':[640,800],'sourceTimelineSeconds':10,'note':'Six second presentation of the normalized timer; master remains 10 seconds at 24 fps.'},indent=2),encoding='utf-8')
else:
    raise ValueError(mode)
print('RENDER_BATCH_COMPLETE',mode,flush=True)
