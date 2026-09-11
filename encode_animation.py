"""Encode rendered PNGs with Blender's bundled FFmpeg (no external installation)."""
import bpy
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene
s.name='SUNA / film assembly'
s.render.resolution_x=640
s.render.resolution_y=800
s.render.resolution_percentage=100
s.render.fps=24
s.frame_start=1
s.frame_end=144
s.render.image_settings.media_type='VIDEO'
s.render.ffmpeg.format='MPEG4'
s.render.ffmpeg.codec='H264'
s.render.ffmpeg.constant_rate_factor='HIGH'
s.render.ffmpeg.ffmpeg_preset='GOOD'
s.render.filepath=str(OUT/'SUNA_motion.mp4')
s.render.film_transparent=False
s.view_settings.view_transform='Standard'
s.view_settings.look='None'
s.view_settings.exposure=0
s.view_settings.gamma=1
ed=s.sequence_editor_create()
strips=ed.strips
seq=strips.new_image('SUNA / 24 fps',str(OUT/'animation'/'frame_0000.png'),channel=1,frame_start=1)
for i in range(1,144):
    seq.elements.append(f'frame_{i:04d}.png')
seq.frame_final_duration=144
s.render.use_sequencer=True
bpy.ops.render.render(animation=True)
video=OUT/'SUNA_motion.mp4'
if not video.exists():
    candidates=list(OUT.glob('SUNA_motion*.mp4'))
    assert len(candidates)==1,candidates
    candidates[0].rename(video)
assert video.stat().st_size>1000
probe=strips.new_movie('Verify encoded movie',str(video),channel=2,frame_start=200)
assert probe.frame_duration==144,probe.frame_duration
assert round(probe.fps)==24,probe.fps
assert probe.elements[0].orig_width==640
assert probe.elements[0].orig_height==800
(OUT/'checks'/'video_validation.json').write_text(json.dumps({'decoded':True,'frames':probe.frame_duration,'fps':probe.fps,'width':probe.elements[0].orig_width,'height':probe.elements[0].orig_height,'bytes':video.stat().st_size},indent=2),encoding='utf-8')
s.render.image_settings.media_type='IMAGE'
s.render.image_settings.file_format='PNG'
s.render.filepath=str(OUT/'checks'/'encoded_frame_0071.png')
s.frame_set(271)
bpy.ops.render.render(write_still=True)
print('SUNA_VIDEO_COMPLETE',flush=True)
