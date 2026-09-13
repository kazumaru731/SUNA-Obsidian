"""Cycles references at half-percent states, for assessing whole-frame blending."""
import sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from render_cycles import setup
import motion

s,objects,flow,spin,poses=setup()
for a,b in [(49,50),(50,51)]:
    state={name:(p[a]+p[b])*.5 for name,p in poses.items()}
    for name,obj in objects.items():
        obj.data.shape_keys.key_blocks['SUNA / frozen original reservoir pose'].data.foreach_set('co',state[name].ravel())
        obj.data.update()
    coords,rot,_,_=motion.evaluate(0,state['lower'],(a+b)/2)
    flow.data.vertices.foreach_set('co',coords.ravel())
    spin.data.foreach_set('vector',rot.ravel())
    flow.data.update()
    s.frame_set(1)
    bpy.context.view_layer.update()
    s.render.filepath=str(PACKAGE/'checks'/f'true_midpoint_{a}_{b}.png')
    bpy.ops.render.render(write_still=True)
check_source()
print('TRUE_MIDPOINT_REFERENCES_COMPLETE',flush=True)
