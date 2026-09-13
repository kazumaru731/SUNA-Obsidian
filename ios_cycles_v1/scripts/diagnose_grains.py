"""Read-only Blender diagnostic of denoising and frozen original coordinates."""
import sys
from pathlib import Path
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from render_cycles import setup
import motion

s,objects,flow,spin,poses=setup()
for name,obj in objects.items():
    obj.data.shape_keys.key_blocks['SUNA / frozen original reservoir pose'].data.foreach_set('co',poses[name][50].ravel())
    obj.data.update()
coords,rot,_,_=motion.evaluate(0,poses['lower'][50],50)
flow.data.vertices.foreach_set('co',coords.ravel())
spin.data.foreach_set('vector',rot.ravel())
flow.data.update()
s.frame_set(1)
bpy.context.view_layer.update()
s.cycles.use_denoising=False
s.render.filepath=str(PACKAGE/'checks'/'noisy_50_phase0.png')
bpy.ops.render.render(write_still=True)
check_source()
print('NO_DENOISE_DIAGNOSTIC_COMPLETE',flush=True)
