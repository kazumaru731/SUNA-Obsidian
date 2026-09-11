"""SUNA / Obsidian — original Blender 5 hourglass, in millimetre-inspired studio units.

Run: blender --background --factory-startup --python create_hourglass.py
No add-ons, downloads, external textures or auto-run handlers are required.
"""
import bpy
import math
import os
import json
import random
import sys
from pathlib import Path
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
OUT.mkdir(exist_ok=True)
for folder in ['renders', 'widget', 'animation', 'checks']:
    (OUT / folder).mkdir(exist_ok=True)
random.seed(291)
FPS, END = 24, 241
TAU = math.tau

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for datablocks in [bpy.data.materials, bpy.data.node_groups, bpy.data.collections]:
    for block in list(datablocks):
        if block.users == 0:
            datablocks.remove(block)
scene = bpy.context.scene
scene.name = 'SUNA | Obsidian — Master'
scene.render.engine = 'CYCLES'
scene.cycles.samples = 160
scene.cycles.use_denoising = True
scene.cycles.adaptive_threshold = 0.012
scene.cycles.max_bounces = 16
scene.cycles.transmission_bounces = 12
scene.cycles.glossy_bounces = 8
scene.cycles.transparent_max_bounces = 16
scene.cycles.sample_clamp_indirect = 3
scene.cycles.use_light_tree = True
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == 'OPTIX'
    scene.cycles.device = 'GPU'
except Exception:
    scene.cycles.device = 'CPU'
scene.render.resolution_x = 1100
scene.render.resolution_y = 1320
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '16'
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, END
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = 0.35
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.04
scene['design'] = 'SUNA / OBSIDIAN — smoked-black titanium, clear borosilicate, champagne quartz'
scene['animation'] = '10 second normalized timer; 1=start, 121=half, 241=empty. Retiming through NLA/Dope Sheet.'
scene['simulation_note'] = 'Deterministic art-directed animation. Reservoir volumes match numerically; ballistic stream and impact grains are baked shape keys. Not a DEM simulation.'

def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

body_col = collection('01 / Glass and machined titanium')
detail_col = collection('02 / Champagne inlay and engraving')
sand_col = collection('03 / Sand reservoirs — volume matched')
flow_col = collection('04 / Falling grains and impact scatter')
studio_col = collection('05 / Reflection studio')
camera_col = collection('06 / Cameras')

def relink(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj

def material(name, color, roughness=0.4, metallic=0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*color, 1)
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Metallic'].default_value = metallic
    bs.inputs['Roughness'].default_value = roughness
    return m, bs

titanium, bs = material('01 / Obsidian — finely brushed titanium', (.021, .027, .033), .29, .86)
n = titanium.node_tree.nodes
l = titanium.node_tree.links
tex = n.new('ShaderNodeTexNoise')
tex.inputs['Scale'].default_value = 160
tex.inputs['Detail'].default_value = 2
bump = n.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = .12
bump.inputs['Distance'].default_value = .0008
l.new(tex.outputs['Fac'], bump.inputs['Height'])
l.new(bump.outputs['Normal'], bs.inputs['Normal'])
bs.inputs['Anisotropic'].default_value = .35

gold, bs = material('02 / Champagne — satin PVD inlay', (.63, .43, .205), .24, .82)
bs.inputs['Anisotropic'].default_value = .28
dark, _ = material('03 / Recessed elastomer gasket', (.008, .009, .011), .55, .05)
etch, _ = material('04 / Laser etched warm silver', (.42, .40, .34), .40, .64)

glass = bpy.data.materials.new('05 / Clear borosilicate — solid 1.0 mm walls')
glass.use_nodes = True
glass.diffuse_color = (.86, .96, .98, .15)
n = glass.node_tree.nodes
n.clear()
l = glass.node_tree.links
o = n.new('ShaderNodeOutputMaterial')
g = n.new('ShaderNodeBsdfGlass')
g.name = 'True dielectric reflection + refraction'
g.inputs['Color'].default_value = (.992, .999, 1, 1)
g.inputs['Roughness'].default_value = .018
g.inputs['IOR'].default_value = 1.46
l.new(g.outputs[0], o.inputs['Surface'])
absorb = n.new('ShaderNodeVolumeAbsorption')
absorb.inputs['Color'].default_value = (.78, .94, .95, 1)
absorb.inputs['Density'].default_value = .035
l.new(absorb.outputs[0], o.inputs['Volume'])
glass['wall_thickness'] = '0.026 scene units, approximately 1.04 mm at project scale'

sand, bs = material('06 / Champagne quartz — dry mineral sand', (.59, .42, .21), .63, 0)
bs.inputs['Specular IOR Level'].default_value = .29
n = sand.node_tree.nodes
l = sand.node_tree.links
noise = n.new('ShaderNodeTexNoise')
noise.name = 'Mineral colour variation / individual grains'
noise.inputs['Scale'].default_value = 195
noise.inputs['Detail'].default_value = 2
ramp = n.new('ShaderNodeValToRGB')
ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
palette = [(0.18,(.16,.095,.038,1)),(.38,(.40,.255,.105,1)),(.53,(.67,.49,.265,1)),(.68,(.86,.72,.47,1)),(.84,(.96,.88,.68,1))]
for i,(pos,col) in enumerate(palette):
    e = ramp.color_ramp.elements[0] if i == 0 else ramp.color_ramp.elements.new(pos)
    e.position, e.color = pos, col
l.new(noise.outputs['Fac'], ramp.inputs[0])
l.new(ramp.outputs['Color'], bs.inputs['Base Color'])
micro = n.new('ShaderNodeTexVoronoi')
micro.inputs['Scale'].default_value = 450
micro.distance = 'EUCLIDEAN'
micro.feature = 'DISTANCE_TO_EDGE'
b = n.new('ShaderNodeBump')
b.inputs['Strength'].default_value = .45
b.inputs['Distance'].default_value = .0045
l.new(micro.outputs['Distance'], b.inputs['Height'])
l.new(b.outputs['Normal'], bs.inputs['Normal'])

grain, bs = material('07 / Quartz granules — faceted, nonmetallic', (.70,.51,.28), .48, 0)
bs.inputs['Specular IOR Level'].default_value = .33
n = grain.node_tree.nodes
l = grain.node_tree.links
info = n.new('ShaderNodeObjectInfo')
rc = n.new('ShaderNodeValToRGB')
rc.color_ramp.elements[0].color = (.28,.16,.06,1)
rc.color_ramp.elements[1].color = (.91,.78,.51,1)
l.new(info.outputs['Random'],rc.inputs[0])
l.new(rc.outputs[0],bs.inputs['Base Color'])

def mesh_obj(name, verts, faces, col, mat, smooth=True):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name,mesh)
    col.objects.link(obj)
    if mat:
        mesh.materials.append(mat)
    if smooth:
        for p in mesh.polygons:
            p.use_smooth = True
    return obj

def lathe(name, profile, col, mat, segments=192):
    verts = [(r*math.cos(TAU*j/segments),r*math.sin(TAU*j/segments),z) for r,z in profile for j in range(segments)]
    faces = []
    for i in range(len(profile)):
        k = (i+1)%len(profile)
        for j in range(segments):
            q = (j+1)%segments
            faces.append((i*segments+j,i*segments+q,k*segments+q,k*segments+j))
    return mesh_obj(name,verts,faces,col,mat)

def cylinder(name, radius, depth, z, mat, bevel=.018, col=body_col):
    bpy.ops.mesh.primitive_cylinder_add(vertices=192,radius=radius,depth=depth,location=(0,0,z))
    obj = relink(bpy.context.object,col)
    obj.name = name
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    mod = obj.modifiers.new('Precision rounded edge','BEVEL')
    mod.width, mod.segments = bevel, 4
    norm = obj.modifiers.new('Machined surface normals','WEIGHTED_NORMAL')
    norm.keep_sharp = True
    return obj

def torus(name,radius,minor,z,mat):
    bpy.ops.mesh.primitive_torus_add(major_segments=192,minor_segments=12,location=(0,0,z),major_radius=radius,minor_radius=minor)
    obj = relink(bpy.context.object,detail_col)
    obj.name = name
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj

# Shape-preserving cubic Hermite interpolation: no ripples in the optical wall.
Z = np.array([0,.08,.22,.42,.70,.98,1.17,1.37,1.53])
R = np.array([.060,.084,.235,.478,.741,.878,.895,.831,.704])
sec = np.diff(R)/np.diff(Z)
der = np.zeros(len(Z))
der[0],der[-1] = 0,sec[-1]
for i in range(1,len(Z)-1):
    if sec[i-1]*sec[i] > 0:
        der[i] = 2/(1/sec[i-1]+1/sec[i])

def outer(z):
    z = np.clip(np.abs(z),0,1.53)
    i = np.clip(np.searchsorted(Z,z)-1,0,len(Z)-2)
    h = Z[i+1]-Z[i]
    t = (z-Z[i])/h
    return (2*t**3-3*t**2+1)*R[i]+(t**3-2*t**2+t)*h*der[i]+(-2*t**3+3*t**2)*R[i+1]+(t**3-t**2)*h*der[i+1]

zs = np.linspace(-1.53,1.53,309)
profile = [(float(outer(z)),float(z)) for z in zs]
profile += [(float(outer(z)-.026),float(z)) for z in reversed(zs)]
glass_obj = lathe('Borosilicate / continuous hollow hourglass',profile,body_col,glass)
glass_obj['construction'] = 'Watertight annular shell with real interior and exterior surfaces; caps seal both ends.'

for sign,label in [(1,'Crown'),(-1,'Base')]:
    cylinder(f'{label} / obsidian titanium',.786,.174,sign*1.583,titanium,.028)
    cylinder(f'{label} / recessed glass seat',.718,.034,sign*1.502,dark,.009)
    cylinder(f'{label} / champagne edge band',.787,.013,sign*1.551,gold,.004,detail_col)
    torus(f'{label} / fine perimeter bevel',.753,.006,sign*1.667,gold)
    cylinder(f'{label} / brushed inset face',.699,.008,sign*1.673,titanium,.005)

# Subtle minute graduations on the top face; one larger mark every five minutes.
verts, faces = [], []
for i in range(60):
    angle = i*TAU/60
    r1,r2 = (.706,.737) if i%5==0 else (.721,.735)
    width = .0028 if i%5==0 else .00145
    a = len(verts)
    for r,w in [(r1,-width),(r2,-width),(r2,width),(r1,width)]:
        verts.append((r*math.cos(angle)-w*math.sin(angle),r*math.sin(angle)+w*math.cos(angle),1.675))
    faces.append(tuple(range(a,a+4)))
mesh_obj('Crown / 60 precision minute indices',verts,faces,detail_col,etch,False)

def label(text,name,size,location,rotation=(0,0,0),mat=etch):
    curve = bpy.data.curves.new(name,'FONT')
    curve.body = text
    curve.size = size
    curve.space_character = 1.35
    curve.align_x = 'CENTER'
    curve.align_y = 'CENTER'
    curve.extrude = .00015
    curve.bevel_depth = .00005
    obj = bpy.data.objects.new(name,curve)
    detail_col.objects.link(obj)
    obj.location, obj.rotation_euler = location,rotation
    curve.materials.append(mat)
    return obj

label('S U N A','Crown / wordmark',.088,(0,-.04,1.680))
label('O B S I D I A N','Crown / edition',.022,(0,-.17,1.680))
# A tiny inset gold index at the front of the lower rim.
bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.016,location=(0,-.786,-1.579))
dot = relink(bpy.context.object,detail_col)
dot.name = 'Base / single champagne index'
dot.scale = (1,.24,1)
dot.data.materials.append(gold)

# Reservoir boundaries are integrated numerically, then baked as compatible meshes.
z_in = np.linspace(0,1.17,2400)
r_in = outer(z_in)-.026-.007
r_grid = np.linspace(0,float(r_in.max())-.001,1400)
upper_floor = np.interp(r_grid,r_in,z_in)
lower_ceiling = -upper_floor-.004
bottom_z = np.linspace(1.17,1.526,1200)
bottom_r = outer(bottom_z)-.026-.007
lower_floor = -np.interp(r_grid,bottom_r[::-1],bottom_z[::-1])
lower_floor = np.where(r_grid <= bottom_r[-1],-1.526,lower_floor)
TOTAL = .85

def solve_surface(kind,amount):
    if kind == 'upper':
        floor = upper_floor
        crater_depth = .12*min(1,amount/.04)
        shape = -crater_depth*np.exp(-(r_grid/.155)**2)
        ceiling = np.full_like(r_grid,1.15)
        lo,hi = -.03,1.15
    else:
        floor = lower_floor
        shape = -.57*(np.sqrt(r_grid**2+.018**2)-.018)
        shape += .0028*np.sin(r_grid*175)*np.exp(-r_grid*5)*min(1,amount/.06)
        ceiling = lower_ceiling
        lo,hi = -1.56,0
    for _ in range(48):
        h = (lo+hi)/2
        surf = np.maximum(floor,np.minimum(h+shape,ceiling))
        vol = float(np.trapz(TAU*r_grid*(surf-floor),r_grid))
        if vol < amount:
            lo = h
        else:
            hi = h
    surf = np.maximum(floor,np.minimum((lo+hi)/2+shape,ceiling))
    active = np.where(surf-floor > .000001)[0]
    extent = float(r_grid[active[-1]]) if len(active) else .000001
    return surf,floor,extent,(lo+hi)/2

NR, NS = 40, 128
def reservoir_coords(kind,amount):
    surf,floor,extent,h = solve_surface(kind,amount)
    coords = []
    for side in range(2):
        for i in range(NR+1):
            r = extent*max(i/NR,.00001)
            z = float(np.interp(r,r_grid,surf if side==0 else floor))
            for j in range(NS):
                a = j*TAU/NS
                micro = .0013*math.sin(a*19+r*63)*math.sin(a*31-r*105)
                edge = math.sin(math.pi*i/NR)**.5
                dz = micro*edge if side==0 and amount>.00001 else 0
                coords.append((r*math.cos(a),r*math.sin(a),z+dz))
    return np.asarray(coords,dtype=np.float32),h

faces, top_flags = [], []
count = (NR+1)*NS
for side in range(2):
    for i in range(NR):
        for j in range(NS):
            a = side*count+i*NS+j
            b = side*count+i*NS+(j+1)%NS
            c = side*count+(i+1)*NS+(j+1)%NS
            d = side*count+(i+1)*NS+j
            faces.append((a,d,c,b) if side==0 else (a,b,c,d))
            top_flags.append(side==0)
for j in range(NS):
    q = (j+1)%NS
    faces.append((NR*NS+j,count+NR*NS+j,count+NR*NS+q,NR*NS+q))
    top_flags.append(False)
    faces.append((j,q,count+q,count+j))
    top_flags.append(False)

def animate_keys(obj,values,frames):
    obj.shape_key_add(name='Basis')
    for index,(coords,frame) in enumerate(zip(values,frames)):
        key = obj.shape_key_add(name=f'State / {frame:06.2f}')
        key.data.foreach_set('co',np.asarray(coords,dtype=np.float32).ravel())
        if index>0:
            key.value=0
            key.keyframe_insert('value',frame=frames[index-1])
        key.value=1
        key.keyframe_insert('value',frame=frame)
        if index<len(frames)-1:
            key.value=0
            key.keyframe_insert('value',frame=frames[index+1])
        key.value=0
    action = obj.data.shape_keys.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for k in fc.keyframe_points:
                        k.interpolation='LINEAR'

def grain_nodes(obj,surface=False):
    ng=bpy.data.node_groups.new(obj.name+' / instanced mineral granules','GeometryNodeTree')
    ng.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    n,l=ng.nodes,ng.links
    inp=n.new('NodeGroupInput'); inp.location=(-650,100)
    out=n.new('NodeGroupOutput');out.location=(650,100)
    if surface:
        attr=n.new('GeometryNodeInputNamedAttribute');attr.data_type='BOOLEAN';attr.inputs['Name'].default_value='exposed_surface'
        dist=n.new('GeometryNodeDistributePointsOnFaces');dist.distribute_method='RANDOM'
        dist.inputs['Density'].default_value=13500
        dist.inputs['Seed'].default_value=291
        l.new(inp.outputs['Geometry'],dist.inputs['Mesh'])
        l.new(attr.outputs['Attribute'],dist.inputs['Selection'])
        points=dist.outputs['Points']
    else:
        points=inp.outputs['Geometry']
    ico=n.new('GeometryNodeMeshIcoSphere');ico.inputs['Radius'].default_value=1;ico.inputs['Subdivisions'].default_value=1
    setmat=n.new('GeometryNodeSetMaterial');setmat.inputs['Material'].default_value=grain
    l.new(ico.outputs['Mesh'],setmat.inputs['Geometry'])
    inst=n.new('GeometryNodeInstanceOnPoints')
    l.new(points,inst.inputs['Points'])
    l.new(setmat.outputs['Geometry'],inst.inputs['Instance'])
    sz=n.new('FunctionNodeRandomValue');sz.data_type='FLOAT_VECTOR'
    sz.inputs['Min'].default_value=(.0017,.0021,.0019) if surface else (.0023,.0025,.0030)
    sz.inputs['Max'].default_value=(.0043,.0047,.0041) if surface else (.0044,.0045,.0060)
    sz.inputs['Seed'].default_value=128
    l.new(sz.outputs['Value'],inst.inputs['Scale'])
    rot=n.new('FunctionNodeRandomValue');rot.data_type='FLOAT_VECTOR';rot.inputs['Min'].default_value=(0,0,0);rot.inputs['Max'].default_value=(6.28,6.28,6.28)
    if not surface:
        time=n.new('GeometryNodeInputSceneTime')
        l.new(time.outputs['Frame'],rot.inputs['Seed'])
    l.new(rot.outputs['Value'],inst.inputs['Rotation'])
    if surface:
        join=n.new('GeometryNodeJoinGeometry')
        l.new(inp.outputs['Geometry'],join.inputs['Geometry'])
        l.new(inst.outputs['Instances'],join.inputs['Geometry'])
        l.new(join.outputs['Geometry'],out.inputs[0])
    else:
        l.new(inst.outputs['Instances'],out.inputs[0])
    mod=obj.modifiers.new('Real individual quartz grains','NODES');mod.node_group=ng
    return ng

frames = np.linspace(1,END,49).tolist()
volumes=[]
for kind in ['upper','lower']:
    coords,h=reservoir_coords(kind,TOTAL if kind=='upper' else 0)
    obj=mesh_obj(f'{kind.title()} reservoir / animated sand',coords.tolist(),faces,sand_col,sand)
    attr=obj.data.attributes.new('exposed_surface','BOOLEAN','FACE')
    for d,value in zip(attr.data,top_flags):
        d.value=value
    values=[]
    for f in frames:
        p=(f-1)/(END-1)
        amount=TOTAL*((1-p) if kind=='upper' else p)
        coords,h=reservoir_coords(kind,amount)
        values.append(coords)
        surf,floor,_,_=solve_surface(kind,amount)
        actual=float(np.trapz(TAU*r_grid*(surf-floor),r_grid))
        volumes.append({'reservoir':kind,'frame':f,'target':amount,'integrated':actual})
    animate_keys(obj,values,frames)
    grain_nodes(obj,True)
    obj['volume_total']=TOTAL
    obj['volume_fraction']='1-progress' if kind=='upper' else 'progress'

# Bake the stream and rebounds as point positions, retaining light instancing.
N_STREAM,N_IMPACT=340,125
rng=np.random.default_rng(29)
phase=rng.random(N_STREAM)
angle=rng.random(N_STREAM)*TAU
radius=np.sqrt(rng.random(N_STREAM))*.017
impact_phase=rng.random(N_IMPACT)
impact_angle=rng.random(N_IMPACT)*TAU
impact_dist=rng.uniform(.035,.29,N_IMPACT)
flow_values=[]
for frame in range(1,END+1):
    t=(frame-1)/FPS
    p=(frame-1)/(END-1)
    surf,_,extent,h=solve_surface('lower',TOTAL*p)
    land=float(surf[0])+.012
    fall=-.013-land
    q=(phase+t*2.6)%1
    xx=radius*np.cos(angle)+.0025*np.sin(q*23+t*8)
    yy=radius*np.sin(angle)+.0025*np.cos(q*29+t*7)
    zz=-.013-fall*q**1.75
    stream=np.column_stack((xx,yy,zz))
    u=(impact_phase+t*2.8)%1
    rr=impact_dist*u
    aa=impact_angle+.03*np.sin(t*3+impact_angle)
    ground=np.interp(rr,r_grid,surf)
    bounce=4*u*(1-u)*(.018+.024*impact_dist/.29)
    scatter=np.column_stack((rr*np.cos(aa),rr*np.sin(aa),ground+bounce+.004))
    coords=np.vstack((stream,scatter))
    if p>=1:
        coords[:]=(0,0,-1.60)
    elif p>.985:
        mask=np.arange(len(coords))/len(coords)>(1-p)/.015
        coords[mask]=(0,0,-1.60)
    flow_values.append(coords.astype(np.float32))
flow=mesh_obj('Quartz / accelerating stream and ballistic rebounds',flow_values[0].tolist(),[],flow_col,None)
animate_keys(flow,flow_values,list(range(1,END+1)))
grain_nodes(flow,False)
flow['description']='340 stream grains + 125 rebound grains. Accelerating descent, individually varied phases and off-axis impact.'

# Studio is separate so transparent exports can hide the floor in one step.
floor_mat,_=material('08 / Studio — warm graphite',(.019,.023,.027),.3,.18)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-1.691))
floor=relink(bpy.context.object,studio_col);floor.name='Studio / seamless graphite floor';floor.data.materials.append(floor_mat)
world=bpy.data.worlds.new('Studio / neutral soft ambience');world.use_nodes=True
world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.40,.45,.51,1)
world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.21
scene.world=world

def track(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

def area(name,loc,target,power,color,size,sy=None):
    light=bpy.data.lights.new(name,'AREA');light.energy=power;light.color=color
    light.shape='RECTANGLE';light.size=size;light.size_y=sy or size
    obj=bpy.data.objects.new(name,light);studio_col.objects.link(obj);obj.location=loc;track(obj,target)
    return obj

area('Key / tall silk reflection',(-3.2,-4,3.5),(0,0,.1),500,(1,.89,.72),1.6,4.4)
area('Rim / cool optical edge',(2.8,1.8,1.8),(0,0,.0),620,(.72,.85,1),.65,4.0)
area('Left / narrow white strip',(-2.5,.8,.7),(0,0,0),260,(.93,.97,1),.32,3.5)
area('Crown / broad softbox',(.1,1,5),(0,0,0),480,(1,.93,.82),3,2)
area('Sand / soft frontal lift',(0,-4.5,1.4),(0,0,-.15),75,(1,.92,.79),2,2.8)

def camera(name,loc,target,scale):
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=scale
    obj=bpy.data.objects.new(name,data);camera_col.objects.link(obj);obj.location=loc;track(obj,target)
    data.lens=70;data.clip_end=200
    return obj

hero=camera('Camera / HERO — studio portrait',(4,-7,2.8),(0,0,.02),4.18)
widget=camera('Camera / WIDGET — readable silhouette',(3.2,-8,2.4),(0,0,0),3.95)
macro=camera('Camera / MACRO — grains at the throat',(2.4,-6,1.05),(0,0,-.23),1.88)
scene.camera=hero
for f,name in [(1,'START / 100%'),(61,'75% remaining'),(121,'50% remaining'),(181,'25% remaining'),(241,'COMPLETE / 0%')]:
    scene.timeline_markers.new(name,frame=f)
scene.frame_set(121)

# Make the file pleasant to open without requiring script execution.
for obj in bpy.context.selected_objects:
    obj.select_set(False)
glass_obj.select_set(True)
bpy.context.view_layer.objects.active=glass_obj
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type=='VIEW_3D':
            a.spaces.active.region_3d.view_perspective='CAMERA'
            a.spaces.active.shading.type='MATERIAL'
            a.spaces.active.overlay.show_overlays=False

readme=bpy.data.texts.new('READ ME / SUNA')
readme.write('SUNA / OBSIDIAN\nOriginal hourglass for a timer app.\n\nCamera HERO: studio portrait.\nCamera WIDGET: alpha asset.\nCamera MACRO: neck and impact.\n\nTimeline: 1 to 241, 24 fps, 10 seconds. Frame 121 is the hero pose.\nAll movement is baked into shape keys: no auto-run Python or add-ons.\n\nPhysical dielectric: IOR 1.46, actual double surface, roughness .018.\nSand: micro bump + instanced faceted grains.\nVolume matched reservoir meshes with funnel and repose slope.\nStream: accelerating grains and impact scatter; art-directed, not DEM.\n\nCollections 01–04 are the model. 05 is studio. 06 contains cameras.\nFor alpha: hide Studio / seamless graphite floor and set Film Transparent.\nUse rendered progress images for WidgetKit timeline entries; continuous movie is an app/reference asset.\n')
report={'blender':bpy.app.version_string,'frames':END,'fps':FPS,'total_volume_scene_units':TOTAL,'max_volume_error':max(abs(v['integrated']-v['target']) for v in volumes),'volume_checks':volumes,'mesh_objects':len([o for o in scene.objects if o.type=='MESH']),'explicit_stream_grains':N_STREAM,'impact_grains':N_IMPACT}
(OUT/'checks'/'volume_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
scene.render.filepath=str(OUT/'renders'/'suna_hero.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SUNA_Obsidian.blend'))
scene.render.resolution_percentage=50
scene.cycles.samples=48
scene.render.image_settings.color_depth='8'
scene.render.filepath=str(OUT/'checks'/'first_preview.png')
bpy.ops.render.render(write_still=True)
print('SUNA_BUILD_COMPLETE',flush=True)
