"""Resumable local controller. Full generation requires a reviewed pilot gate.

The worker renders on the GPU while complete states are encoded/checked on the CPU.
No publishing, cloud jobs, login, or network access is performed by this script.
"""
import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from common import *
from encode_assets import encode, encoder_signature
from package_delivery import build, archive, progress
from audit_decoded_motion import audit as audit_video_motion

DEFAULT_BLENDER=r'C:\Program Files\Blender Foundation\Blender 5.0\blender.exe'
LOCK=PACKAGE/'checks'/'batch.lock'
STATUS=PACKAGE/'checks'/'batch_status.json'


def alive(pid):
    if os.name=='nt':
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x1000,False,int(pid))
        if not handle:
            error=ctypes.get_last_error()
            if error==87:
                return False
            # Access denied is not evidence that a process has ended.
            return True
        code=ctypes.c_ulong()
        try:
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):
                return True
            return code.value==259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid),0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def acquire():
    LOCK.parent.mkdir(exist_ok=True)
    if LOCK.exists():
        old=read_json(LOCK,{})
        if not old.get('pid') or alive(old['pid']):
            raise RuntimeError(f'Another controller may be active: {old}. Inspect before resuming.')
        LOCK.unlink()
    fd=os.open(LOCK,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        import json
        json.dump({'pid':os.getpid(),'startedUTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},f)


def set_status(status,**extra):
    write_json(STATUS,{'status':status,'pid':os.getpid(),
        'updatedUTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'renderSignature':fingerprint(),**extra})


def ready(remaining):
    signature=fingerprint()
    return all(read_json(frame_path(remaining,i).with_suffix('.json'),{}).get('renderSignature')==signature
               and frame_path(remaining,i).exists() for i in range(FRAMES))


def main(stage,blender):
    check_source()
    if (PACKAGE/'STOP_AFTER_FRAME').exists():
        raise RuntimeError('Paused by STOP_AFTER_FRAME. Use Resume-Render.ps1 when ready.')
    if stage=='full':
        gate=read_json(PACKAGE/'checks'/'pilot_gate.json',{})
        if not gate.get('passed') or gate.get('renderSignature')!=fingerprint():
            raise RuntimeError('The exact pilot must pass visual and numerical review before full generation.')
        if gate.get('encoderSignature')!=encoder_signature():
            raise RuntimeError('Encoding inputs changed after the pilot review; recheck the pilot.')
        for entry in gate.get('evidence',[])+gate.get('pilotClips',[]):
            if digest(PACKAGE/entry['path'])!=entry['sha256']:
                raise RuntimeError(f'Reviewed pilot evidence changed: {entry["path"]}')
    if not Path(blender).is_file():
        raise RuntimeError(f'Blender executable not found: {blender}')
    acquire()
    process=None
    try:
        previous=read_json(STATUS,{})
        # A killed controller may have left its renderer finishing a frame.
        # Do not spawn another renderer or kill an unowned process.
        if previous.get('workerPID') and alive(previous['workerPID']):
            raise RuntimeError(f'Previous renderer PID {previous["workerPID"]} is still active. Stop it gracefully with Stop-Render.ps1 and wait for its exit.')
        states=PILOT if stage=='pilot' else list(range(101))
        stats=progress()
        estimated_remaining=max(0,stats['masterBytesEstimate']-stats['masterBytesCurrently'])
        if shutil.disk_usage(MASTERS).free<estimated_remaining*1.2+2_000_000_000:
            raise RuntimeError('Not enough free disk space for the remaining PNG masters and verification.')
        if os.name=='nt':
            # Prevent automatic system sleep only while this batch owns the work.
            # The display may turn off; normal sleep behavior is restored in finally.
            if not ctypes.windll.kernel32.SetThreadExecutionState(0x80000001):
                raise ctypes.WinError()
        timestamp=time.strftime('%Y%m%d_%H%M%S')
        log_path=PACKAGE/'checks'/f'blender_{stage}_{timestamp}.log'
        command=[blender,'--background','--python-exit-code','1','--python',
            str(PACKAGE/'scripts'/'render_cycles.py'),'--','--states',','.join(map(str,states))]
        processed=set()
        with log_path.open('wb') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            while True:
                for remaining in states:
                    if remaining not in processed and ready(remaining):
                        set_status('encoding',stage=stage,workerPID=process.pid,
                                   remaining=remaining,validatedClipCount=len(processed),log=str(log_path))
                        encode(remaining)
                        audit_video_motion(remaining)
                        processed.add(remaining)
                        build()
                set_status('rendering',stage=stage,workerPID=process.pid,
                    validatedClipCount=len(processed),worker=read_json(PACKAGE/'checks'/'worker_status.json',{}),
                    measurements=progress(),log=str(log_path))
                if process.poll() is not None:
                    break
                time.sleep(10)
        worker=read_json(PACKAGE/'checks'/'worker_status.json',{})
        if worker.get('status')=='paused':
            set_status('paused',stage=stage,validatedClipCount=len(processed),worker=worker)
            build()
            return
        if process.returncode!=0 or worker.get('status')!='complete':
            raise RuntimeError(f'Blender did not complete (exit {process.returncode}); inspect {log_path}')
        if len(processed)!=len(states):
            raise RuntimeError(f'Missing validated states: {set(states)-processed}')
        if stage=='pilot':
            set_status('building_previews',stage=stage,validatedClipCount=len(processed))
            from make_previews import references,compression_board,video,denoising_board,seam_and_phone_boards
            from audit_trajectories import audit
            audit(); references(); compression_board(); seam_and_phone_boards()
            if (PACKAGE/'checks'/'noisy_50_phase0.png').exists():
                denoising_board()
            video()
            build()
            set_status('pilot_ready_for_review',stage=stage,validatedClipCount=len(processed))
            return
        set_status('final_verification',stage=stage,validatedClipCount=len(processed))
        path=archive(require_complete=True)
        set_status('complete',stage=stage,validatedClipCount=101,archive=str(path),archiveSha256=digest(path))
    except BaseException as exc:
        if process is not None and process.poll() is None:
            (PACKAGE/'STOP_AFTER_FRAME').touch()
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                pass
        set_status('failed',stage=stage,error=str(exc),
                   workerPID=process.pid if process is not None and process.poll() is None else None)
        raise
    finally:
        if os.name=='nt':
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        if read_json(LOCK,{}).get('pid')==os.getpid():
            LOCK.unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['pilot','full'],default='pilot')
    parser.add_argument('--blender',default=DEFAULT_BLENDER)
    args=parser.parse_args()
    main(args.stage,args.blender)
