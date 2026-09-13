"""Check one-sided loop limits and all particle respawns at all remaining states."""
import numpy as np
from common import *
import motion


def audit():
    poses=np.load(MASTERS/'original_reservoir_poses.npz')
    epsilon=1e-7
    worst=0.0
    endpoint_gaps=[]
    for remaining in range(1,101):
        lower=poses['lower'][remaining]
        before=motion.evaluate(2-epsilon,lower,remaining)
        after=motion.evaluate(epsilon,lower,remaining)
        jump=float(np.max(np.linalg.norm(before[0]-after[0],axis=1)))
        worst=max(worst,jump)
        assert jump<1e-4,'Position discontinuity at the two-second boundary'
        assert np.max(np.abs(np.cos(before[1])-np.cos(after[1])))<1e-5
        assert np.max(np.abs(np.sin(before[1])-np.sin(after[1])))<1e-5
        # Solve the first true phase wrap of each stable identity, then examine
        # its limits instead of merely checking sampled frame displacements.
        throat_error=landing_error=contact_error=0.0
        for i,phase in enumerate(motion.PHASE):
            t=(1-phase)/2.5
            left=motion.evaluate(t-epsilon,lower,remaining)[0][i]
            right=motion.evaluate(t+epsilon,lower,remaining)[0][i]
            throat_error=max(throat_error,abs(float(right[2])+.013))
            landing_error=max(landing_error,abs(float(left[2])-(float(lower[0,2])+.012)))
        assert throat_error<1e-5 and landing_error<1e-5
        for j,phase in enumerate(motion.IMPACT_PHASE):
            t=(1-phase)/3
            for dt in [-epsilon,epsilon]:
                co=motion.evaluate(t+dt,lower,remaining)[0][motion.COUNT_STREAM+j]
                ground=motion.ground_height(lower,np.array([np.hypot(co[0],co[1])]),np.array([np.arctan2(co[1],co[0])]))[0]
                contact_error=max(contact_error,abs(float(co[2]-ground)-.004))
        assert contact_error<1e-5
        endpoint_gaps.append({'remaining':remaining,'seamLimitPositionError':jump,
            'throatResetError':throat_error,'landingResetError':landing_error,
            'reboundContactResetError':contact_error})
    value={'passed':True,'renderSignature':fingerprint(),'oneSidedLimitEpsilonSeconds':epsilon,
           'maximumSeamLimitPositionError':worst,'states':endpoint_gaps,
           'respawnLocations':'Stream: 0.012 scene units above the sand center -> throat. Impact grains: 0.004 above local surface -> center contact.',
           'speedChangesFromOriginal':{'stream':{'originalCyclesPerSecond':2.6,'new':2.5},
                                       'rebound':{'originalCyclesPerSecond':2.8,'new':3.0}},
           'limitation':'Art-directed particles from the original model; not a granular dynamics simulation.'}
    write_json(PACKAGE/'checks'/'trajectory_validation.json',value)
    print('TRAJECTORIES_PASSED',worst,flush=True)
    return value


if __name__=='__main__':
    audit()
