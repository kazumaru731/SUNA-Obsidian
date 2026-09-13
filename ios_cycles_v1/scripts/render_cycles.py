"""Blender render worker. Source file is never saved or changed.

blender -b --python scripts/render_cycles.py -- --states 0,1,49,50,51,100
Use --frames 0,12,24,36,47 for an initial contact sheet, then resume all phases.
"""
import argparse
import math
import os
import shutil
import sys
import time
from pathlib import Path
import bpy
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
import motion

def extract_poses(scene, objects):
    poses = {}
    for name,obj in objects.items():
        keys = obj.data.shape_keys
        basis = np.empty((len(obj.data.vertices),3),dtype=np.float32)
        keys.key_blocks[0].data.foreach_get('co',basis.ravel())
        offsets=[]
        for key in list(keys.key_blocks)[1:]:
            assert key.relative_key == keys.key_blocks[0]
            coords=np.empty_like(basis)
            key.data.foreach_get('co',coords.ravel())
            offsets.append(coords-basis)
        states=[]
        for remaining in range(101):
            frame=1+(100-remaining)*2.4
            scene.frame_set(int(frame),subframe=frame%1)
            coords=basis.copy()
            for key,offset in zip(list(keys.key_blocks)[1:],offsets):
                if key.value:
                    coords+=offset*key.value
            states.append(coords)
        poses[name]=np.stack(states)
    return poses

def mesh_volume(mesh,coordinates):
    mesh.calc_loop_triangles()
    tris=np.array([t.vertices[:] for t in mesh.loop_triangles])
    a,b,c=(coordinates[tris[:,i]].astype(np.float64) for i in range(3))
    return float(np.einsum('ij,ij->i',a,np.cross(b,c)).sum()/6)

def setup():
    check_source()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    s=bpy.context.scene
    assert bpy.app.version_string=='5.0.1'
    assert s.camera.name==RENDER['camera']
    assert s.view_settings.view_transform==RENDER['viewTransform']
    assert s.view_settings.look==RENDER['look']
    assert abs(s.view_settings.exposure-.35)<1e-6
    s.render.engine='CYCLES'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use=d.type=='OPTIX'
    assert any(d.use for d in prefs.devices),'An existing OPTIX GPU is required.'
    s.cycles.device='GPU'
    s.cycles.samples=192
    s.cycles.adaptive_threshold=.01
    s.cycles.use_denoising=True
    s.cycles.denoiser='OPENIMAGEDENOISE'
    s.cycles.denoising_prefilter='ACCURATE'
    s.cycles.use_animated_seed=False
    s.cycles.seed=0
    assert s.cycles.max_bounces==16 and s.cycles.transmission_bounces==12
    assert s.cycles.glossy_bounces==8 and s.cycles.transparent_max_bounces==16
    s.render.resolution_x,s.render.resolution_y=WIDTH,HEIGHT
    s.render.resolution_percentage=100
    s.render.pixel_aspect_x=s.render.pixel_aspect_y=1
    s.render.image_settings.media_type='IMAGE'
    s.render.image_settings.file_format='PNG'
    s.render.image_settings.color_mode='RGB'
    s.render.image_settings.color_depth='16'
    s.render.image_settings.compression=15
    s.render.fps=FPS
    s.render.fps_base=1
    s.render.film_transparent=False
    s.render.use_persistent_data=True
    s.render.use_motion_blur=False
    s.frame_start,s.frame_end=1,FRAMES
    objects={name:bpy.data.objects[f'{name.title()} reservoir / animated sand'] for name in ['upper','lower']}
    poses=extract_poses(s,objects)
    MASTERS.mkdir(exist_ok=True)
    np.savez_compressed(MASTERS/'original_reservoir_poses.npz',**poses)
    volumes=[]
    for remaining in range(101):
        upper=mesh_volume(objects['upper'].data,poses['upper'][remaining])
        lower=mesh_volume(objects['lower'].data,poses['lower'][remaining])
        volumes.append({'remaining':remaining,'upperVolume':upper,'lowerVolume':lower,'sum':upper+lower})
    assert all(volumes[i+1]['upperVolume']>=volumes[i]['upperVolume']-1e-8 for i in range(100))
    assert all(volumes[i+1]['lowerVolume']<=volumes[i]['lowerVolume']+1e-8 for i in range(100))
    error=max(abs(v['sum']-.85)/.85 for v in volumes)
    assert error<.02
    write_json(PACKAGE/'checks'/'reservoir_validation.json',{'passed':True,'sourceShapesPreserved':True,'monotonic':True,'maxRelativeVolumeError':error,'states':volumes})
    write_json(PACKAGE/'checks'/'motion_validation.json',motion.verify(poses))
    for obj in objects.values():
        # Keep the original undeformed mesh / Basis. Generated texture coordinates
        # are evaluated from this rest geometry. Replacing it with the posed mesh
        # changes the approved sand bump pattern even with unchanged shaders.
        obj.data.shape_keys.animation_data_clear()
        for key in list(obj.data.shape_keys.key_blocks)[1:]:
            key.value=0
        frozen=obj.shape_key_add(name='SUNA / frozen original reservoir pose')
        frozen.relative_key=obj.data.shape_keys.key_blocks[0]
        frozen.value=1
    flow=bpy.data.objects['Quartz / accelerating stream and ballistic rebounds']
    flow.shape_key_clear()
    assert len(flow.data.vertices)==motion.COUNT
    spin_attr=flow.data.attributes.new('suna_spin_offset','FLOAT_VECTOR','POINT')
    tree=flow.modifiers[0].node_group
    instance=next(n for n in tree.nodes if n.bl_idname=='GeometryNodeInstanceOnPoints')
    rotation_link=next(l for l in tree.links if l.to_socket==instance.inputs['Rotation'])
    rotation=rotation_link.from_node
    tree.links.remove(rotation_link)
    for link in list(tree.links):
        if link.to_node==rotation and link.to_socket==rotation.inputs['Seed']:
            tree.links.remove(link)
    rotation.inputs['Seed'].default_value=121
    attr=tree.nodes.new('GeometryNodeInputNamedAttribute')
    attr.data_type='FLOAT_VECTOR'
    attr.inputs['Name'].default_value='suna_spin_offset'
    add=tree.nodes.new('ShaderNodeVectorMath')
    add.operation='ADD'
    tree.links.new(rotation.outputs['Value'],add.inputs[0])
    tree.links.new(attr.outputs['Attribute'],add.inputs[1])
    tree.links.new(add.outputs['Vector'],instance.inputs['Rotation'])
    return s,objects,flow,spin_attr,poses

def render_states(states,phases):
    signature=fingerprint()
    existing=read_json(MASTERS/'render_contract.json')
    if existing and existing['renderSignature']!=signature:
        # Never silently reuse frames from different code or settings.
        raise RuntimeError('Render contract changed. Use a new master directory or explicitly archive the prior run.')
    write_json(MASTERS/'render_contract.json',{'renderSignature':signature,'sourceSha256':SOURCE_SHA256,'renderSettings':RENDER})
    if set(states)-set(PILOT):
        gate=read_json(PACKAGE/'checks'/'pilot_gate.json',{})
        if not gate.get('passed') or gate.get('renderSignature')!=signature:
            raise RuntimeError('Full generation requires the verified pilot gate for these exact render inputs.')
    s,objects,flow,spin_attr,poses=setup()
    for remaining in states:
        assert 0<=remaining<=100
        for name,obj in objects.items():
            obj.data.shape_keys.key_blocks['SUNA / frozen original reservoir pose'].data.foreach_set('co',poses[name][remaining].ravel())
            obj.data.update()
        flow.hide_render=remaining==0
        for frame in phases:
            assert 0<=frame<FRAMES
            if (PACKAGE/'STOP_AFTER_FRAME').exists():
                write_json(PACKAGE/'checks'/'worker_status.json',{'status':'paused','remaining':remaining,'nextFrame':frame})
                return
            path=frame_path(remaining,frame)
            path.parent.mkdir(parents=True,exist_ok=True)
            if good_frame(path,signature):
                record_event({'event':'skip','remaining':remaining,'frame':frame})
                continue
            partial=path.with_name(path.stem+'.partial.png')
            start=time.monotonic()
            if remaining==0:
                # A true static 0% clip: identical complete Cycles frames, no flow.
                shutil.copyfile(PACKAGE/'stills'/'finished_empty.png',partial)
                operation='static_copy'
            else:
                coords,spin,_,_=motion.evaluate(frame/FPS,poses['lower'][remaining],remaining)
                flow.data.vertices.foreach_set('co',coords.ravel())
                spin_attr.data.foreach_set('vector',spin.ravel())
                flow.data.update()
                s.frame_set(frame+1)
                bpy.context.view_layer.update()
                s.render.filepath=str(partial)
                bpy.ops.render.render(write_still=True)
                operation='cycles_render'
            seconds=time.monotonic()-start
            info=publish_frame(partial,path,{'renderSignature':signature,'remainingFraction':remaining/100,'frame':frame,'timeSeconds':frame/FPS,'renderSeconds':seconds,'operation':operation})
            event={'event':'frame_complete','remaining':remaining,'frame':frame,'seconds':seconds,'bytes':info['bytes'],'operation':operation}
            record_event(event)
            write_json(PACKAGE/'checks'/'worker_status.json',{'status':'rendering',**event})
            print('FRAME_COMPLETE',remaining,frame,round(seconds,3),flush=True)
        print('STATE_COMPLETE',remaining,flush=True)
    check_source()
    write_json(PACKAGE/'checks'/'worker_status.json',{'status':'complete','states':states,'phases':phases,'renderSignature':signature})
    print('CYCLES_BATCH_COMPLETE',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--states',default=','.join(map(str,PILOT)))
    parser.add_argument('--frames',default=','.join(map(str,range(FRAMES))))
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    try:
        render_states([int(x) for x in args.states.split(',')],[int(x) for x in args.frames.split(',')])
    except Exception as e:
        write_json(PACKAGE/'checks'/'worker_status.json',{'status':'failed','error':str(e)})
        raise
