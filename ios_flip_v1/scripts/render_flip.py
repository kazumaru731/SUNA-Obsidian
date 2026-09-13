"""Build an independently playable Blender bake and render the flip/icon assets."""
import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ios_flip_v1'
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT/'ios_cycles_v1'/'scripts'))
from bake_flip import transform, COUNT, FPS, DURATION
from common import SOURCE, SOURCE_SHA256, digest, png_info, write_json, read_json
import motion

def linear(action):
    if action:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points: key.interpolation='LINEAR'

def bake_keys(obj,coordinates):
    if obj.data.shape_keys:
        obj.data.shape_keys.animation_data_clear()
        for key in list(obj.data.shape_keys.key_blocks)[1:]: key.value=0
    else:
        obj.shape_key_add(name='Basis')
    basis=obj.data.shape_keys.key_blocks[0]
    for k,coords in enumerate(coordinates):
        key=obj.shape_key_add(name=f'Flip bake / {k:02d}')
        key.relative_key=basis
        key.data.foreach_set('co',np.asarray(coords,dtype=np.float32).ravel())
        if k:
            key.value=0; key.keyframe_insert('value',frame=k)
        key.value=1; key.keyframe_insert('value',frame=k+1)
        if k<len(coordinates)-1:
            key.value=0; key.keyframe_insert('value',frame=k+2)
        key.value=0
    linear(obj.data.shape_keys.animation_data.action)

def configure(s,preview=False):
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use=d.type=='OPTIX'
    assert any(d.use for d in prefs.devices)
    s.cycles.device='GPU'
    s.cycles.samples=32 if preview else 192
    s.cycles.adaptive_threshold=.035 if preview else .01
    s.cycles.use_denoising=True
    s.cycles.denoiser='OPENIMAGEDENOISE'
    s.cycles.denoising_prefilter='ACCURATE'
    s.cycles.use_animated_seed=False; s.cycles.seed=0
    s.render.resolution_x,s.render.resolution_y=880,1056
    s.render.resolution_percentage=50 if preview else 100
    s.render.pixel_aspect_x=s.render.pixel_aspect_y=1
    s.render.image_settings.file_format='PNG'
    s.render.image_settings.color_mode='RGB'
    s.render.image_settings.color_depth='16'
    s.render.image_settings.compression=15
    s.render.use_persistent_data=True
    s.render.use_motion_blur=False
    s.render.film_transparent=False
    s.render.fps=24; s.render.fps_base=1
    s.frame_start=1; s.frame_end=30

def make_overlay(parent,data):
    mesh=bpy.data.meshes.new('Flip / gravity grains')
    mesh.from_pydata(data[0].tolist(),[],[])
    obj=bpy.data.objects.new('Flip / sliding and tumbling grains',mesh)
    bpy.data.collections['04 / Falling grains and impact scatter'].objects.link(obj)
    obj.parent=parent
    bake_keys(obj,data)
    ng=bpy.data.node_groups.new('Flip / faceted quartz grains','GeometryNodeTree')
    ng.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    n,l=ng.nodes,ng.links
    inp=n.new('NodeGroupInput'); out=n.new('NodeGroupOutput')
    ico=n.new('GeometryNodeMeshIcoSphere'); ico.inputs['Radius'].default_value=1
    ico.inputs['Subdivisions'].default_value=1
    mat=n.new('GeometryNodeSetMaterial'); mat.inputs['Material'].default_value=bpy.data.materials['07 / Quartz granules — faceted, nonmetallic']
    l.new(ico.outputs['Mesh'],mat.inputs['Geometry'])
    inst=n.new('GeometryNodeInstanceOnPoints')
    l.new(inp.outputs['Geometry'],inst.inputs['Points'])
    l.new(mat.outputs['Geometry'],inst.inputs['Instance'])
    sz=n.new('FunctionNodeRandomValue'); sz.data_type='FLOAT_VECTOR'
    sz.inputs['Min'].default_value=(.0023,.0025,.003)
    sz.inputs['Max'].default_value=(.0044,.0045,.006)
    sz.inputs['Seed'].default_value=128
    l.new(sz.outputs['Value'],inst.inputs['Scale'])
    rot=n.new('FunctionNodeRandomValue'); rot.data_type='FLOAT_VECTOR'
    rot.inputs['Min'].default_value=(0,0,0); rot.inputs['Max'].default_value=(math.tau,)*3
    rot.inputs['Seed'].default_value=207
    clock=n.new('GeometryNodeInputSceneTime')
    spin=n.new('ShaderNodeVectorMath'); spin.operation='ADD'
    l.new(rot.outputs['Value'],spin.inputs[0]); l.new(clock.outputs['Seconds'],spin.inputs[1])
    l.new(spin.outputs['Vector'],inst.inputs['Rotation'])
    l.new(inst.outputs['Instances'],out.inputs['Geometry'])
    obj.modifiers.new('Baked quartz grains','NODES').node_group=ng
    obj.hide_render=False; obj.keyframe_insert('hide_render',frame=26)
    obj.hide_render=True; obj.keyframe_insert('hide_render',frame=27)
    return obj

def build():
    assert digest(SOURCE)==SOURCE_SHA256
    assert read_json(OUT/'checks'/'bake_validation.json')['passed']
    data=np.load(OUT/'bake'/'flip_bake.npz')
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    s=bpy.context.scene
    configure(s)
    root=bpy.data.objects.new('Flip / 180 degree lift and return',None)
    s.collection.objects.link(root)
    for col in list(bpy.data.collections):
        if col.name[:2] in ['01','02','03','04']:
            for obj in list(col.objects):
                world=obj.matrix_world.copy()
                obj.parent=root; obj.matrix_world=world
    root.rotation_mode='QUATERNION'
    for k in range(COUNT+1):
        rot,lift,_=transform(k/FPS)
        root.location=lift; root.rotation_quaternion=Matrix(rot).to_quaternion()
        root.keyframe_insert('location',frame=k+1)
        root.keyframe_insert('rotation_quaternion',frame=k+1)
    linear(root.animation_data.action)
    upper=bpy.data.objects['Upper reservoir / animated sand']
    lower=bpy.data.objects['Lower reservoir / animated sand']
    bake_keys(upper,data['bed'])
    bake_keys(lower,np.repeat(data['lower'][None],COUNT+1,axis=0))
    # Keep original textures/rest coordinates. During the turn, expose grains on
    # every bed face; return to the original upper-surface selection at frame 27.
    tree=upper.modifiers[0].node_group
    dist=next(n for n in tree.nodes if n.bl_idname=='GeometryNodeDistributePointsOnFaces')
    old=next(l for l in tree.links if l.to_socket==dist.inputs['Selection'])
    attr=old.from_socket; tree.links.remove(old)
    clock=tree.nodes.new('GeometryNodeInputSceneTime')
    comp=tree.nodes.new('ShaderNodeMath'); comp.operation='LESS_THAN'; comp.inputs[1].default_value=27
    tree.links.new(clock.outputs['Frame'],comp.inputs[0])
    either=tree.nodes.new('FunctionNodeBooleanMath'); either.operation='OR'
    tree.links.new(attr,either.inputs[0]); tree.links.new(comp.outputs[0],either.inputs[1])
    tree.links.new(either.outputs[0],dist.inputs['Selection'])
    flow=bpy.data.objects['Quartz / accelerating stream and ballistic rebounds']
    flow.shape_key_clear()
    states=[]
    for k in range(COUNT+1):
        coords,_,_,_=motion.evaluate(k/FPS-DURATION,data['lower'],100)
        # Release through the throat only after the body has returned upright.
        reach=float(np.clip((k-24)/3,0,1))**2
        coords[:motion.COUNT_STREAM,2]=-.013+(coords[:motion.COUNT_STREAM,2]+.013)*reach
        if k<27: coords[motion.COUNT_STREAM:]=(0,0,-1.60)
        states.append(coords)
    bake_keys(flow,np.array(states))
    flow.hide_render=True; flow.keyframe_insert('hide_render',frame=24)
    flow.hide_render=False; flow.keyframe_insert('hide_render',frame=25)
    tree=flow.modifiers[0].node_group
    inst=next(n for n in tree.nodes if n.bl_idname=='GeometryNodeInstanceOnPoints')
    old=next(l for l in tree.links if l.to_socket==inst.inputs['Rotation'])
    random=old.from_node; tree.links.remove(old)
    for link in list(tree.links):
        if link.to_node==random and link.to_socket==random.inputs['Seed']: tree.links.remove(link)
    random.inputs['Seed'].default_value=121
    spin=flow.data.attributes.new('flip_spin_cycles','FLOAT_VECTOR','POINT')
    spin.data.foreach_set('vector',motion.SPIN_CYCLES.astype(np.float32).ravel())
    att=tree.nodes.new('GeometryNodeInputNamedAttribute'); att.data_type='FLOAT_VECTOR'
    att.inputs['Name'].default_value='flip_spin_cycles'
    clock=tree.nodes.new('GeometryNodeInputSceneTime')
    subtract=tree.nodes.new('ShaderNodeMath'); subtract.operation='SUBTRACT'
    subtract.inputs[1].default_value=DURATION+1/FPS
    tree.links.new(clock.outputs['Seconds'],subtract.inputs[0])
    wrap=tree.nodes.new('ShaderNodeMath'); wrap.operation='WRAP'
    wrap.inputs[1].default_value=2; wrap.inputs[2].default_value=0
    tree.links.new(subtract.outputs[0],wrap.inputs[0])
    pi=tree.nodes.new('ShaderNodeMath'); pi.operation='MULTIPLY'; pi.inputs[1].default_value=math.pi
    tree.links.new(wrap.outputs[0],pi.inputs[0])
    scale=tree.nodes.new('ShaderNodeVectorMath'); scale.operation='SCALE'
    tree.links.new(att.outputs['Attribute'],scale.inputs[0]); tree.links.new(pi.outputs[0],scale.inputs['Scale'])
    add=tree.nodes.new('ShaderNodeVectorMath'); add.operation='ADD'
    tree.links.new(random.outputs['Value'],add.inputs[0]); tree.links.new(scale.outputs['Vector'],add.inputs[1])
    tree.links.new(add.outputs['Vector'],inst.inputs['Rotation'])
    make_overlay(root,data['particles'])
    s.name='SUNA / gravity flip — baked 30 frames'
    s['flip_contract']='Frames 1–30 = 1.25 seconds at 24 fps. Next regular loop starts at phase 0. Frame 31 is a validation endpoint, not included in MP4.'
    s['sand_method']='Gravity-oriented volume-constrained bed + world-space ballistic surface grains. Art-directed bake, not DEM.'
    # Check fixed camera and actual metal/glass vertices against frame and floor.
    dg=bpy.context.evaluated_depsgraph_get()
    audit=[]
    for k in range(COUNT+1):
        s.frame_set(k+1); dg.update()
        combined=[]
        for colname in ['01 / Glass and machined titanium','02 / Champagne inlay and engraving']:
            for obj in bpy.data.collections[colname].objects:
                evaluated=obj.evaluated_get(dg)
                mesh=evaluated.to_mesh()
                p=np.array([v.co[:] for v in mesh.vertices])
                if len(p):
                    mat=np.asarray(evaluated.matrix_world)
                    combined.append(p@mat[:3,:3].T+mat[:3,3])
                evaluated.to_mesh_clear()
        p=np.concatenate(combined)
        cam=np.asarray(s.camera.matrix_world.inverted())
        cp=p@cam[:3,:3].T+cam[:3,3]
        projection=np.asarray(s.camera.calc_matrix_camera(dg,x=880,y=1056,scale_x=1,scale_y=1))
        ndc=np.column_stack((cp,np.ones(len(cp))))@projection.T
        ndc=ndc[:,:3]/ndc[:,3,None]
        audit.append({'frame':k,'minXY':ndc[:,:2].min(axis=0).tolist(),
                      'maxXY':ndc[:,:2].max(axis=0).tolist(),'floorGap':float(p[:,2].min()+1.691)})
    passed=all(min(a['minXY'])>=-1 and max(a['maxXY'])<=1 and a['floorGap']>=-.001 for a in audit)
    write_json(OUT/'checks'/'framing_validation.json',{'passed':passed,'cameraFixed':True,'backgroundFixed':True,'samples':audit})
    assert passed, 'Framing or floor collision failed'
    s.frame_set(1)
    (OUT/'blend').mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'blend'/'SUNA_flip_baked.blend'))
    assert digest(SOURCE)==SOURCE_SHA256
    return s

def render(s,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    signature=hashlib.sha256((''.join(digest(p) for p in [Path(__file__),
        OUT/'scripts'/'bake_flip.py',OUT/'bake'/'flip_bake.npz',
        ROOT/'ios_cycles_v1'/'scripts'/'motion.py'])+SOURCE_SHA256+
        str((s.frame_current,s.cycles.samples,s.render.resolution_x,
             s.render.resolution_y,s.render.resolution_percentage,s.camera.name))).encode()).hexdigest()
    old=read_json(path.with_suffix('.json'),{})
    if path.exists() and old.get('renderSignature')==signature and digest(path)==old.get('sha256'):
        png_info(path,strict=False)
        print('FLIP_FRAME_VERIFIED_SKIP',path,flush=True)
        return
    partial=path.with_name(path.stem+'.partial.png')
    s.render.filepath=str(partial)
    start=time.monotonic()
    bpy.ops.render.render(write_still=True)
    info=png_info(partial,strict=False)
    os.replace(partial,path)
    write_json(path.with_suffix('.json'),{**info,'seconds':time.monotonic()-start,'frame':s.frame_current,'renderSignature':signature})
    print('FLIP_FRAME_SAVED',path,round(time.monotonic()-start,2),flush=True)

def main(args):
    s=build()
    configure(s,args.preview)
    folder=OUT/('previews/draft' if args.preview else 'masters/frames')
    for k in map(int,args.frames.split(',')):
        if (OUT/'STOP_AFTER_FRAME').exists():
            write_json(OUT/'checks'/'render_status.json',{'status':'paused','nextFrame':k})
            return
        s.frame_set(k+1)
        render(s,folder/f'frame_{k:04d}.png')
        write_json(OUT/'checks'/'render_status.json',{'status':'rendering','draft':args.preview,'lastSavedFrame':k})
    if args.icon:
        # Same source hero scene, 50% sand. Square camera framing is icon-specific.
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
        s=bpy.context.scene; configure(s)
        s.frame_set(121)
        s.camera=bpy.data.objects['Camera / WIDGET — readable silhouette']
        s.camera.data.ortho_scale=3.95
        s.render.resolution_x=s.render.resolution_y=1024
        s.render.resolution_percentage=100
        render(s,OUT/'masters'/'app_icon_1024.png')
    write_json(OUT/'checks'/'render_status.json',{'status':'rendered','draft':args.preview,'frames':args.frames,'sourcePreserved':digest(SOURCE)==SOURCE_SHA256})

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--frames',default=','.join(map(str,range(30))))
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--icon',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    main(args)
