"""Finish/verify the pilot already being rendered by a separately started worker."""
import time
from common import *
from encode_assets import encode
from run_batch import ready
from package_delivery import build
from make_previews import references,compression_board,video,denoising_board,seam_and_phone_boards,midpoint_boards
from audit_trajectories import audit
from audit_decoded_motion import audit as audit_video_motion

if __name__=='__main__':
    pending=set(PILOT)
    deadline=time.monotonic()+7200
    while pending:
        for remaining in sorted(pending):
            if ready(remaining):
                encode(remaining)
                audit_video_motion(remaining)
                pending.remove(remaining)
                build()
        if not pending:
            break
        status=read_json(PACKAGE/'checks'/'worker_status.json',{})
        if status.get('status') in ['failed','paused','complete']:
            raise RuntimeError(f'Pilot worker stopped before all states are ready: {status}; pending={pending}')
        if time.monotonic()>deadline:
            raise RuntimeError(f'Pilot exceeded two-hour wait; inspect the worker log. pending={pending}')
        time.sleep(10)
    audit()
    references()
    compression_board()
    denoising_board()
    seam_and_phone_boards()
    midpoint_boards()
    video()
    build()
    write_json(PACKAGE/'checks'/'pilot_status.json',{
        'status':'ready_for_visual_review','renderSignature':fingerprint(),
        'states':PILOT,'phaseCount':FRAMES})
    print('PILOT_READY_FOR_VISUAL_REVIEW',flush=True)
