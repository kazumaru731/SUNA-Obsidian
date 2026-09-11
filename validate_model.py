import bpy
import json
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'SUNA_Obsidian.blend'))
s=bpy.context.scene
reservoirs=[bpy.data.objects[f'{k} reservoir / animated sand'] for k in ['Upper','Lower']]
for obj in reservoirs:
    for mod in obj.modifiers:
        mod.show_viewport=False
results=[]
for f in [1,31,61,91,121,151,181,211,241]:
    s.frame_set(f)
    deps=bpy.context.evaluated_depsgraph_get()
    volumes=[]
    for obj in reservoirs:
        ev=obj.evaluated_get(deps)
        mesh=ev.to_mesh()
        mesh.calc_loop_triangles()
        coords=np.array([v.co[:] for v in mesh.vertices])
        triangles=np.array([t.vertices[:] for t in mesh.loop_triangles])
        a,b,c=(coords[triangles[:,i]] for i in range(3))
        volume=float(np.einsum('ij,ij->i',a,np.cross(b,c)).sum()/6)
        assert np.isfinite(coords).all()
        assert volume>=-1e-6
        volumes.append(volume)
        ev.to_mesh_clear()
    results.append({'frame':f,'upper':volumes[0],'lower':volumes[1],'total':sum(volumes)})
variation=max(abs(x['total']-.85)/.85 for x in results)
assert variation<.02,variation
report={'masterOpens':True,'noExternalTextures':len([i for i in bpy.data.images if i.source=='FILE' and i.filepath])==0,'noScriptHandlers':len(bpy.app.handlers.frame_change_post)==0,'geometryVolumeDeviationPercent':variation*100,'frames':results}
(OUT/'checks'/'model_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
