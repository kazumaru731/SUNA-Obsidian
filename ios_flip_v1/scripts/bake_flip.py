"""Deterministic gravity-oriented sand bed and constrained surface-grain bake.

This is an art-directed granular approximation, not a DEM solver. The bulk bed
has a volume-constrained free surface responding to downward world gravity;
independent grains integrate world-space gravity and moving-cavity contact.
The original reservoir topology and rest coordinates are retained by Blender.
"""
import json
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'ios_flip_v1'
FPS, COUNT, DURATION = 24, 30, 1.25
G = np.array([0., 0., -245.25])  # project scale: 0.04 m per scene unit
Z = np.array([0, .08, .22, .42, .70, .98, 1.17, 1.37, 1.53])
R = np.array([.060, .084, .235, .478, .741, .878, .895, .831, .704])
sec = np.diff(R) / np.diff(Z)
der = np.zeros(len(Z))
der[-1] = sec[-1]
for i in range(1, len(Z)-1):
    if sec[i-1]*sec[i] > 0:
        der[i] = 2/(1/sec[i-1]+1/sec[i])

def outer(z):
    z = np.clip(np.abs(z), 0, 1.53)
    i = np.clip(np.searchsorted(Z, z)-1, 0, len(Z)-2)
    h = Z[i+1]-Z[i]
    t = (z-Z[i])/h
    return ((2*t**3-3*t**2+1)*R[i]+(t**3-2*t**2+t)*h*der[i]
            +(-2*t**3+3*t**2)*R[i+1]+(t**3-t**2)*h*der[i+1])

RIGHT = np.array([7., 4., 0.])/math.sqrt(65)
FRONT = np.array([4., -7., 0.])/math.sqrt(65)
AXIS = .78*RIGHT + math.sqrt(1-.78**2)*FRONT

def smooth(x):
    x = np.clip(x, 0, 1)
    return x*x*x*(x*(x*6-15)+10)

def transform(t):
    u = float(smooth((t-2/FPS)/(22/FPS)))
    angle = math.pi*(1-u)
    x,y,z = AXIS
    skew = np.array([[0,-z,y],[z,0,-x],[-y,x,0.]])
    rot = np.eye(3)*math.cos(angle)+(1-math.cos(angle))*np.outer(AXIS,AXIS)+math.sin(angle)*skew
    # Actual radial profile and cap extents; keep the entire body above the floor.
    zz = np.linspace(-1.53,1.53,400)
    extent = max(float(np.max(np.abs(zz*math.cos(angle))+outer(zz)*abs(math.sin(angle)))),
                 1.685*abs(math.cos(angle))+.792*abs(math.sin(angle)))
    lift = max(0.,extent-1.685)+.12*math.sin(math.pi*u)
    return rot, np.array([0.,0.,lift]), angle

def scalar(points, normal):
    # The original draining crater emerges only as the upright pose settles.
    crater = .12*float(smooth((normal[2]-.75)/.25))
    return points @ normal + crater*np.exp(-np.sum(points[...,:2]**2,axis=-1)/.155**2)

def inside(points, normal, height, margin=.055):
    return ((points[...,2]>=.00001)&(points[...,2]<=1.492)&
            (np.linalg.norm(points[...,:2],axis=-1)<=outer(points[...,2])-margin)&
            (scalar(points,normal)<=height))

def triangles():
    faces=[]
    ns,nr=128,40
    count=(nr+1)*ns
    for side in range(2):
        for i in range(nr):
            for j in range(ns):
                a=side*count+i*ns+j; b=side*count+i*ns+(j+1)%ns
                c=side*count+(i+1)*ns+(j+1)%ns; d=side*count+(i+1)*ns+j
                q=(a,d,c,b) if side==0 else (a,b,c,d)
                faces.extend([(q[0],q[1],q[2]),(q[0],q[2],q[3])])
    for j in range(ns):
        q=(j+1)%ns
        for f in [(nr*ns+j,count+nr*ns+j,count+nr*ns+q,nr*ns+q),
                  (j,q,count+q,count+j)]:
            faces.extend([(f[0],f[1],f[2]),(f[0],f[2],f[3])])
    return np.asarray(faces)

TRI = triangles()
def volume(points):
    a,b,c=(points[TRI[:,i]] for i in range(3))
    return float(np.einsum('ij,ij->i',a,np.cross(b,c)).sum()/6)

def project(points, margin=.041):
    p=points.copy()
    p[:,2]=np.clip(p[:,2],.006,1.483)
    rr=np.linalg.norm(p[:,:2],axis=1)
    limit=outer(p[:,2])-margin
    p[:,:2]*=np.minimum(1,limit/np.maximum(rr,1e-12))[:,None]
    return p

def rays(center, directions, normal, height):
    low=np.zeros(len(directions)); high=np.full(len(directions),3.)
    for _ in range(27):
        mid=(low+high)/2
        ok=inside(center+mid[:,None]*directions,normal,height)
        low=np.where(ok,mid,low); high=np.where(ok,high,mid)
    return center+low[:,None]*directions

def main():
    (OUT/'bake').mkdir(parents=True,exist_ok=True)
    (OUT/'checks').mkdir(exist_ok=True)
    poses=np.load(ROOT/'ios_cycles_v1_masters'/'original_reservoir_poses.npz')
    reference=poses['upper'][100].astype(float)
    target=volume(reference)
    step=.021
    xx,yy,zz=np.meshgrid(np.arange(-.87,.871,step),np.arange(-.87,.871,step),
                         np.arange(.0105,1.492,step),indexing='ij')
    grid=np.column_stack((xx.ravel(),yy.ravel(),zz.ravel()))
    grid=grid[np.linalg.norm(grid[:,:2],axis=1)<outer(grid[:,2])-.033]
    fraction=target/(len(grid)*step**3)
    final_h=float(np.quantile(scalar(grid,np.array([0.,0.,1.])),fraction))
    ref_center=grid[scalar(grid,np.array([0.,0.,1.]))<=final_h].mean(axis=0)
    dirs=reference-ref_center
    dirs/=np.maximum(np.linalg.norm(dirs,axis=1)[:,None],1e-12)
    normals=[]; normal=np.array([0.,0.,-1.])
    # Gravity direction follows the rotating vessel with a small frictional lag.
    for k in range(COUNT+1):
        for sub in range(20):
            t=max(0,(k-1+(sub+1)/20)/FPS)
            rot,_,_=transform(t)
            gravity_up=rot.T@np.array([0.,0.,1.])
            normal+=(gravity_up-normal)*(1-math.exp(-1/(FPS*20*.025)))
            normal/=np.linalg.norm(normal)
        normals.append(normal.copy())
    beds=[]; heights=[]; centers=[]; records=[]
    for k,normal in enumerate(normals):
        t=k/FPS
        values=scalar(grid,normal)
        h=float(np.quantile(values,fraction))
        center=grid[values<=h].mean(axis=0)
        low,high=h-.075,h+.075
        for _ in range(12):
            h=(low+high)/2
            coords=rays(center,dirs,normal,h)
            if volume(coords)<target: low=h
            else: high=h
        settle=float(smooth((t-21/FPS)/(5/FPS)))
        if settle:
            coords=coords*(1-settle)+reference*settle
        if k>=26:
            coords=reference.copy()
        rot,lift,angle=transform(t)
        clearance=outer(coords[:,2])-.026-np.linalg.norm(coords[:,:2],axis=1)
        beds.append(coords); heights.append(h); centers.append(center)
        records.append({'frame':k,'time':t,'angleDegrees':math.degrees(angle),
                        'sandVolume':volume(coords),'minGlassClearance':float(clearance.min()),
                        'worldFreeSurfaceUpDot':float((rot@normal)[2]),'lift':float(lift[2])})
        print('BED',k,'volume',round(volume(coords),6),'gap',round(float(clearance.min()),6),flush=True)
    # Surface particles: world-space ballistic integration with wall/bed contact.
    rng=np.random.default_rng(207)
    n=800
    normal=normals[0]; h=heights[0]
    candidates=grid[np.abs(scalar(grid,normal)-h)<.035]
    local=candidates[rng.integers(0,len(candidates),n)].copy()
    local+=normal[None,:]*(h-scalar(local,normal)+.004)[:,None]
    local=project(local)
    rot,lift,_=transform(0)
    world=local@rot.T+lift
    velocity=np.zeros_like(world)
    particles=[]; particle_records=[]
    dt=1/(FPS*32)
    for k in range(COUNT+1):
        if k:
            for sub in range(32):
                blend=(sub+1)/32
                t=(k-1+blend)/FPS
                rot,lift,_=transform(t)
                normal=normals[k-1]*(1-blend)+normals[k]*blend
                normal/=np.linalg.norm(normal)
                h=heights[k-1]*(1-blend)+heights[k]*blend
                old=world.copy()
                velocity+=G*dt
                world+=velocity*dt
                local=(world-lift)@rot
                for iteration in range(5):
                    local=project(local)
                    depth=h+.004-scalar(local,normal)
                    local+=normal[None,:]*np.maximum(depth,0)[:,None]
                local=project(local)
                world=local@rot.T+lift
                velocity=(world-old)/dt
                # Dissipative contact; gravity remains world-down at every step.
                velocity*=math.exp(-9*dt)
        local=(world-lift)@rot
        # Bury overlay grains as the exact original surface takes over.
        bury=float(smooth((k-23)/3))
        local=local*(1-bury)+np.tile(ref_center,(n,1))*bury
        local=project(local)
        particles.append(local.copy())
        particle_records.append(float((outer(local[:,2])-.026-np.linalg.norm(local[:,:2],axis=1)-.006).min()))
    bed=np.asarray(beds,dtype=np.float32)
    particles=np.asarray(particles,dtype=np.float32)
    # Audit triangle interiors as well as vertices, because a concave throat
    # could otherwise be crossed by a coarse face.
    mids=bed[:,TRI[:,0]]*.3333333333+bed[:,TRI[:,1]]*.3333333333+bed[:,TRI[:,2]]*.3333333334
    triangle_gap=float((outer(mids[:,:,2])-.026-np.linalg.norm(mids[:,:,:2],axis=2)).min())
    np.savez_compressed(OUT/'bake'/'flip_bake.npz',bed=bed,particles=particles,
                        normals=normals,heights=heights,reference=reference,lower=poses['lower'][100])
    report={'method':'Volume-constrained gravity-oriented bed plus ballistic surface grains; art-directed, not DEM.',
            'gravityWorld':G.tolist(),'sceneUnitMeters':.04,'frameCount':COUNT,'fps':FPS,
            'durationSeconds':DURATION,'bakedSamplesIncludingEndpoint':COUNT+1,
            'targetVolume':target,'samples':records,'minTriangleGlassClearance':triangle_gap,
            'minParticleGlassClearanceIncludingRadius':min(particle_records),
            'terminalOriginalMeshMaxError':float(np.max(np.abs(bed[-1]-reference))),
            'maxRelativeVolumeError':max(abs(r['sandVolume']-target)/target for r in records),
            'localBedMotion':float(np.linalg.norm(bed[12]-bed[0],axis=1).mean()),
            'passed':False}
    report['passed']=bool(triangle_gap>=-.0001 and min(particle_records)>=0 and
                          report['maxRelativeVolumeError']<.03 and report['terminalOriginalMeshMaxError']<1e-6)
    (OUT/'checks'/'bake_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'},indent=2),flush=True)
    if not report['passed']:
        raise RuntimeError('Sand bake validation failed. Inspect before rendering.')

if __name__=='__main__': main()
