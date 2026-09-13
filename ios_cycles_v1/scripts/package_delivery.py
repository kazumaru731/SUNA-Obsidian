"""Build truthful partial/full manifests and a portable app handoff ZIP."""
import argparse
import statistics
import time
import zipfile
from common import *
from encode_assets import ENCODING, encoder_signature, clip_record, clip_path, master_inventory
from audit_decoded_motion import report_path as temporal_report


def progress():
    signature=fingerprint()
    frames=[]
    for path in (MASTERS/'frames').glob('remaining_*/frame_*.json'):
        m=read_json(path,{})
        if m.get('renderSignature')==signature and path.with_suffix('.png').is_file():
            frames.append(m)
    dynamic=[m for m in frames if m.get('operation')=='cycles_render']
    mean=statistics.mean(m['renderSeconds'] for m in dynamic) if dynamic else 12
    average_bytes=statistics.mean(m['bytes'] for m in dynamic) if dynamic else 3500000
    completed=len(dynamic)
    return {'renderedMasterFrames':len(frames),'expectedMasterFrames':101*FRAMES,
        'dynamicFramesCompleted':completed,'dynamicFramesExpected':100*FRAMES,
        'meanMeasuredRenderSeconds':mean,'measuredDynamicRenderSeconds':sum(m['renderSeconds'] for m in dynamic),
        'remainingRenderHoursEstimate':max(0,100*FRAMES-completed)*mean/3600,
        'totalRenderHoursEstimate':100*FRAMES*mean/3600,
        'masterBytesEstimate':int(101*FRAMES*average_bytes),
        'masterBytesCurrently':sum(m['bytes'] for m in frames),
        'estimateNote':'Render-only estimate; allow 10-20% for encoding, verification, GPU load and startup.'}


def collect_clips(verify_masters=False):
    signature=fingerprint()
    enc_signature=encoder_signature()
    valid=[]; expected=[]
    for remaining in range(101):
        path=clip_path(remaining)
        m=read_json(clip_record(remaining),{})
        good=(m.get('passed') and m.get('renderSignature')==signature and
              m.get('encoderSignature')==enc_signature and path.exists() and digest(path)==m.get('sha256'))
        temporal=read_json(temporal_report(remaining),{})
        good=good and temporal.get('passed') and temporal.get('clipSha256')==m.get('sha256')
        if good and verify_masters:
            good=master_inventory(remaining,signature)[0]==m['inputSha256']
        entry={'remainingFraction':remaining/100,
               'path':f'clips/remaining_{remaining:03d}.mp4',
               'status':'validated' if good else 'pending',
               'sha256':m['sha256'] if good else None,
               'bytes':m['bytes'] if good else None,
               'frameCount':FRAMES,'durationSeconds':PERIOD,
               'flowing':remaining>0}
        expected.append(entry)
        if good:
            valid.append(m)
    return valid,expected


def build(require_complete=False, verify_masters=False):
    check_source()
    valid,expected=collect_clips(verify_masters)
    gate=read_json(PACKAGE/'checks'/'pilot_gate.json',{})
    gate_ok=bool(gate.get('passed') and gate.get('renderSignature')==fingerprint()
                 and gate.get('encoderSignature')==encoder_signature()
                 and len(gate.get('pilotClips',[]))==len(PILOT) and gate.get('evidence'))
    if gate_ok:
        for entry in gate['evidence']+gate['pilotClips']:
            path=PACKAGE/entry['path']
            if not path.is_file() or digest(path)!=entry['sha256']:
                gate_ok=False
                break
    required_previews=['reference_comparison.png','loop_and_transition_check.mp4']
    previews=[{'path':'previews/'+name,'sha256':digest(PACKAGE/'previews'/name)}
              for name in required_previews if (PACKAGE/'previews'/name).exists()]
    preview_check=read_json(PACKAGE/'checks'/'preview_validation.json',{})
    preview_ok=(preview_check.get('passed') and preview_check.get('renderSignature')==fingerprint()
                and len(previews)==len(required_previews)
                and preview_check.get('sha256')==digest(PACKAGE/'previews'/'loop_and_transition_check.mp4'))
    stills=[]
    audit=read_json(PACKAGE/'checks'/'source_audit.json',{})
    for name,remaining,role in [('idle_full.png',1,'idle_no_flow'),('finished_empty.png',0,'finished_no_flow')]:
        path=PACKAGE/'stills'/name
        m=png_info(path)
        approved=next(v for v in audit['measurements'] if v['path']=='stills/'+name)
        assert m['sha256']==approved['sha256'],'The audited still has changed'
        stills.append({'path':'stills/'+name,'remainingFraction':remaining,'role':role,
                       'sha256':m['sha256'],'bytes':m['bytes'],'flowing':False})
    numerical={name:read_json(PACKAGE/'checks'/name,{}) for name in [
        'motion_validation.json','reservoir_validation.json','trajectory_validation.json']}
    numeric_ok=all(v.get('passed') for v in numerical.values())
    complete=bool(len(valid)==101 and gate_ok and preview_ok and numeric_ok)
    if require_complete and not complete:
        raise RuntimeError(f'Delivery incomplete: {len(valid)}/101 validated clips; pilot={gate_ok}; preview={preview_ok}; motion={numeric_ok}')
    status='complete' if complete else 'partial'
    stats=progress()
    if valid:
        moving=[v['bytes'] for v in valid if v['remainingFraction']>0]
        stats['appClipBytesCurrent']=sum(v['bytes'] for v in valid)
        stats['appClipBytesEstimate']=int(statistics.mean(moving)*100+2335265) if moving else None
    manifest={'schemaVersion':1,'assetSet':'SUNA Obsidian / iOS Cycles v1',
        'status':status,'generatedAtUTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'remainingDirection':'1.0 = all sand in upper reservoir; 0.0 = finished, all in lower reservoir. Filenames encode remaining percent, never elapsed percent.',
        'source':{'commit':SOURCE_COMMIT,'path':'output/SUNA_Obsidian.blend','sha256':SOURCE_SHA256,
                  'blenderVersion':'5.0.1','referenceImageSha256':digest(REFERENCE)},
        'resolution':{'width':WIDTH,'height':HEIGHT,'pixelAspect':[1,1]},
        'fps':FPS,'frameCount':FRAMES,'loopDurationSeconds':PERIOD,
        'sampleTimesSeconds':{'first':0,'last':47/24,'duplicateEndpoint':False},
        'color':{'master':'16-bit RGB PNG, display-referred sRGB, full range',
                 'video':{'primaries':'BT.709','transfer':'BT.709','matrix':'BT.709','range':'limited'},
                 'conversion':'Explicit sRGB transfer conversion to BT.709 through FFmpeg zscale; not metadata-only tagging.'},
        'renderSignature':fingerprint(),'renderSettings':RENDER,'encoding':ENCODING,
        'mixing':{'space':'linear-light after correctly decoding the tagged video',
                  'phase':'Use one shared clock modulo 2 seconds. Both video frames have the same phase index.',
                  'weight':'p=clamp(remainingFraction,0,1)*100; lo=floor(p); hi=min(100,lo+1); weight=p-lo',
                  'idle':'Use stills/idle_full.png before starting.',
                  'finished':'Use stills/finished_empty.png at zero; the 0% static clip supports the 1% -> 0% blend.'},
        'expectedClipCount':101,'validatedClipCount':len(valid),'clips':expected,'stills':stills,
        'previews':previews,'masterStorage':'../ios_cycles_v1_masters/frames/',
        'validation':'checks/validation.json','appIntegration':'Mac/iPhone implementation and device validation are outside this delivery.'}
    validation={'schemaVersion':1,'status':status,'complete':complete,
        'sourcePreserved':True,'sourceSha256':SOURCE_SHA256,
        'renderSignature':fingerprint(),'validatedClips':len(valid),'expectedClips':101,
        'missingRemainingPercents':[i for i,e in enumerate(expected) if e['status']!='validated'],
        'pilotGatePassed':bool(gate_ok),'previewVerified':bool(preview_ok),
        'motionAndVolumesPassed':numeric_ok,
        'stillsPassed':True,'masterChecks':'CRC, full PNG decompression, RGB16 format, input SHA-256 and render signature before each encode.',
        'videoChecks':'All decoded frames, dimensions, duration, CFR timestamps, first IDR, profile, color tags, audio absence, black frames, compression error, seam and static metal.',
        'decodedTemporalReports':'checks/temporal/remaining_NNN.json',
        'numericalReports':list(numerical),'visualReview':'checks/pilot_gate.json',
        'iPhoneDeviceTest':'not performed; Mac team responsibility',
        'measurements':stats}
    write_json(PACKAGE/'manifest.json',manifest)
    write_json(PACKAGE/'checks'/'validation.json',validation)
    return manifest,validation


def archive(require_complete=False):
    manifest,validation=build(require_complete,verify_masters=True)
    out=PACKAGE/'handoff'
    out.mkdir(exist_ok=True)
    suffix='' if validation['complete'] else '_pilot'
    path=out/f'SUNA_Obsidian_ios_cycles_v1{suffix}.zip'
    partial=path.with_name(path.stem+'.partial.zip')
    files=[PACKAGE/'manifest.json',PACKAGE/'README.md']
    files += [PACKAGE/v['path'] for v in manifest['clips'] if v['status']=='validated']
    files += [PACKAGE/v['path'] for v in manifest['stills']]
    for folder,patterns in [('previews',['*.png','*.mp4']),('checks',['*.json']),
                            ('scripts',['*.py','*.ps1']),('docs',['*.md'])]:
        for pattern in patterns:
            files += list((PACKAGE/folder).glob(pattern))
    for entry in manifest['clips']:
        if entry['status']=='validated':
            files.append(clip_record(round(entry['remainingFraction']*100)))
            files.append(temporal_report(round(entry['remainingFraction']*100)))
    # Runtime status and prior archive hashes describe this PC, not the portable
    # asset set. In particular, do not embed a stale self-referential ZIP hash.
    runtime_names={'batch_status.json','worker_status.json','completion.json','pilot_status.json'}
    files=sorted({p for p in files if p.name not in runtime_names})
    with zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in files:
            name='ios_cycles_v1/'+file.relative_to(PACKAGE).as_posix()
            z.write(file,name,compress_type=zipfile.ZIP_STORED if file.suffix in ['.png','.mp4'] else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(partial) as z:
        assert z.testzip() is None
    os.replace(partial,path)
    sha=digest(path)
    path.with_suffix('.zip.sha256').write_text(sha+'  '+path.name+'\n',encoding='utf-8')
    if validation['complete']:
        write_json(PACKAGE/'checks'/'completion.json',{
            'complete':True,'archive':str(path),'archiveSha256':sha,
            'validatedClipCount':101,'renderSignature':fingerprint(),
            'completedAtUTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    print('ARCHIVE_READY',path,sha,flush=True)
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--require-complete',action='store_true')
    parser.add_argument('--archive',action='store_true')
    parser.add_argument('--verify-masters',action='store_true')
    args=parser.parse_args()
    if args.archive:
        archive(args.require_complete)
    else:
        m,v=build(args.require_complete,args.verify_masters)
        print(json.dumps({'status':m['status'],'validatedClips':m['validatedClipCount'],'measurements':v['measurements']},indent=2))
