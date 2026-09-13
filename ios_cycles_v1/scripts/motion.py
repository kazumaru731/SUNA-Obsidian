"""A common 2-second periodic grain clock, independent of the remaining sand volume.

There is no interpolation across particle respawns: each requested time is evaluated
directly. Respawn sites are the throat/landing surface, never an arbitrary air point.
The original 340 + 125 identities, radii and material instances are retained.
"""
import math
import numpy as np

COUNT_STREAM, COUNT_IMPACT = 340, 125
COUNT = COUNT_STREAM + COUNT_IMPACT
PERIOD = 2.0
SEED = 29
TAU = math.tau
_rng = np.random.default_rng(SEED)
PHASE = _rng.random(COUNT_STREAM)
ANGLE = _rng.random(COUNT_STREAM)*TAU
RADIUS = np.sqrt(_rng.random(COUNT_STREAM))*.017
IMPACT_PHASE = _rng.random(COUNT_IMPACT)
IMPACT_ANGLE = _rng.random(COUNT_IMPACT)*TAU
IMPACT_DISTANCE = _rng.uniform(.035,.29,COUNT_IMPACT)
SPIN_CYCLES = _rng.integers(1,5,(COUNT,3))

def ground_height(lower_coordinates, radii, angles):
    """Bilinear interpolation on the original frozen top mesh, including its ripples."""
    surface = np.asarray(lower_coordinates[:5248]).reshape((41,128,3))
    rr = np.linalg.norm(surface[:,0,:2],axis=1)
    radii = np.asarray(radii)
    a = np.asarray(angles)/TAU*128 % 128
    j = np.floor(a).astype(int)
    w = a-j
    heights = surface[:,j,2]*(1-w)+surface[:,(j+1)%128,2]*w
    idx = np.clip(np.searchsorted(rr,radii,side='right')-1,0,39)
    span = np.maximum(rr[idx+1]-rr[idx],1e-12)
    fraction = np.clip((radii-rr[idx])/span,0,1)
    return heights[idx,np.arange(radii.size)]*(1-fraction)+heights[idx+1,np.arange(radii.size)]*fraction

def evaluate(seconds, lower_coordinates, remaining):
    """Return stable-ID positions, continuous spin offsets, and cycle fractions."""
    t = float(seconds) % PERIOD
    q = (PHASE + 2.5*t) % 1.0       # exactly 5 descents in the 2-second period
    u = (IMPACT_PHASE + 3.0*t) % 1.0 # exactly 6 contact/bounce cycles per period
    landing = float(lower_coordinates[0,2])+.012
    distance = -.013-landing
    # Initial offsets reproduce the 50% original HERO's t=5-second phase.
    xx = RADIUS*np.cos(ANGLE)+.0025*np.sin(q*23+40+TAU*t*2)
    yy = RADIUS*np.sin(ANGLE)+.0025*np.cos(q*29+35+TAU*t*1.5)
    zz = -.013-distance*q**1.75
    stream = np.column_stack((xx,yy,zz))
    rr = IMPACT_DISTANCE*u
    aa = IMPACT_ANGLE+.03*np.sin(15+IMPACT_ANGLE+TAU*t*1.5)
    ground = ground_height(lower_coordinates,rr,aa)
    bounce = 4*u*(1-u)*(.018+.024*IMPACT_DISTANCE/.29)
    impacts = np.column_stack((rr*np.cos(aa),rr*np.sin(aa),ground+bounce+.004))
    coords = np.vstack((stream,impacts))
    spin = TAU*SPIN_CYCLES*t/PERIOD
    if remaining == 0:
        coords[:] = (0,0,-1.60)
    return coords.astype(np.float32),spin.astype(np.float32),q,u

def verify(poses):
    results = []
    for remaining in range(101):
        lower = poses['lower'][remaining]
        first,spin0,_,_ = evaluate(0,lower,remaining)
        endpoint,spin2,_,_ = evaluate(2,lower,remaining)
        assert np.array_equal(first,endpoint)
        assert np.array_equal(spin0,spin2)
        samples = [evaluate(i/24,lower,remaining)[0] for i in range(48)]
        samples = np.stack(samples)
        assert np.isfinite(samples).all()
        if remaining:
            assert np.max(np.linalg.norm(samples[:,:COUNT_STREAM,:2],axis=2))<.03
        results.append({'remaining':remaining,'loopEndpointMaxError':float(np.max(np.abs(first-endpoint))),
                        'phaseCount':48,'phaseRangeSeconds':[0,47/24],
                        'landingZ':float(lower[0,2])+.012})
    adjacent=[]
    for a,b in [(49,50),(50,51),(0,1)]:
        ac=evaluate(0,poses['lower'][a],max(1,a))[0]
        bc=evaluate(0,poses['lower'][b],max(1,b))[0]
        assert np.array_equal(ac[:COUNT_STREAM,:2],bc[:COUNT_STREAM,:2])
        adjacent.append({'pair':[a,b],'sameStreamXY':True,'maxWorldDisplacement':float(np.linalg.norm(ac-bc,axis=1).max())})
    return {'passed':True,'remainingStates':results,'adjacentIdentityChecks':adjacent,
            'commonSeed':SEED,'streamGrains':COUNT_STREAM,'impactGrains':COUNT_IMPACT,
            'respawnPolicy':'Direct time evaluation: stream resets from landing to throat; rebounds reset on the sand surface. No keyframe interpolation across a reset.',
            'exactPeriodSeconds':PERIOD,'streamCyclesPerPeriod':5,'impactCyclesPerPeriod':6}
