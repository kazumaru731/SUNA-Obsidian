"""Verify this run's recorded pause/resume checkpoint without changing masters."""
from datetime import datetime,timezone
from common import *

checkpoint=read_json(PACKAGE/'checks'/'resume_checkpoint.json')
assert checkpoint and checkpoint['beforePause']
for record in checkpoint['beforePause']:
    path=Path(record['path'])
    assert digest(path)==record['sha256'],'A completed frame was replaced after resume'
    assert path.stat().st_mtime_ns==record['mtimeNs'],'A completed frame was rewritten after resume'
status=read_json(PACKAGE/'checks'/'batch_status.json')
worker=read_json(PACKAGE/'checks'/'worker_status.json')
assert status['status']=='rendering' and status['stage']=='full'
assert worker['status']=='rendering' and worker['remaining']==2 and worker['frame']>=4
created=datetime.fromtimestamp(Path(status['log']).stat().st_ctime,timezone.utc).replace(microsecond=0)
events=[json.loads(line) for line in (PACKAGE/'checks'/'render_events.jsonl').read_text().splitlines()]
skips={e['frame'] for e in events if e.get('event')=='skip' and e.get('remaining')==2
       and datetime.strptime(e['utc'],'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)>=created}
assert {0,1,2,3}.issubset(skips)
check_source()
write_json(PACKAGE/'checks'/'resume_validation.json',{
    'passed':True,'renderSignature':fingerprint(),'checkpointFramesPreserved':len(checkpoint['beforePause']),
    'preservedSHA256AndModificationTimes':True,'lastSavedPhaseBeforePause':3,'firstNewPhaseAfterResume':4,
    'verifiedSkippedPhases':sorted(skips),'workerPID':status['workerPID'],
    'resumedWorkerLog':status['log'],'sourcePreserved':True})
print('PAUSE_RESUME_VERIFIED',sorted(skips))
