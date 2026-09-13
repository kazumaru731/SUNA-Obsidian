"""Color-managed encoding, full decoding, and frame-level delivery validation.

Requires Python + numpy + Pillow, and the pinned portable FFmpeg in tools/.
The MP4 is published atomically only after every frame passes validation.
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image
from common import *

TO_VIDEO = ('format=gbrp16le,zscale=matrixin=gbr:matrix=bt709:'
            'transferin=iec61966-2-1:transfer=bt709:'
            'primariesin=bt709:primaries=bt709:rangein=full:range=limited:'
            'dither=error_diffusion,format=yuv420p,setsar=1')
TO_SRGB = ('zscale=matrixin=bt709:matrix=gbr:transferin=bt709:'
           'transfer=iec61966-2-1:primariesin=bt709:primaries=bt709:'
           'rangein=limited:range=full:dither=error_diffusion,format=gbrp,'
           'format=rgb24')
ENCODING = {'encoder':'libx264','profile':'High','level':'4.1','crf':14,
            'preset':'slow','pixelFormat':'yuv420p','bFrames':0,'gop':48,
            'colorPrimaries':'bt709','transfer':'bt709','matrix':'bt709',
            'range':'limited','source':'sRGB full-range RGB16',
            'filter':TO_VIDEO,'audio':False,'fastStart':True,
            'zeroPercent':'Repeat one identical encoded IDR access unit 48 times'}
ROIS = {'stream':(412,530,468,790), 'engraving':(374,110,493,159),
        'upperSand':(290,337,580,410), 'lowerSand':(290,840,585,914),
        'glass':(218,570,642,892), 'staticMetal':(268,96,610,175)}


def execute(args, **kwargs):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, **kwargs)


def clip_path(remaining):
    return PACKAGE/'clips'/f'remaining_{remaining:03d}.mp4'


def clip_record(remaining):
    return PACKAGE/'checks'/'clips'/f'remaining_{remaining:03d}.json'


def encoder_signature():
    # Include the executable and code so a changed encoder cannot reuse a stale QC report.
    version=execute([ffmpeg_binary(),'-version']).stdout.decode().splitlines()[0]
    value={'settings':ENCODING,'version':version,'code':digest(__file__)}
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def master_inventory(remaining, signature=None):
    signature=signature or fingerprint()
    hashes=[]
    for frame in range(FRAMES):
        path=frame_path(remaining,frame)
        if not good_frame(path,signature):
            raise RuntimeError(f'Missing, corrupt, or stale master: {path}')
        hashes.append(digest(path))
    return hashlib.sha256(''.join(hashes).encode()).hexdigest(),hashes


def encoding_args(output, frame_count=FRAMES):
    return ['-vf',TO_VIDEO,'-frames:v',str(frame_count),'-an','-c:v','libx264',
            '-profile:v','high','-level:v','4.1','-preset','slow','-crf','14',
            '-pix_fmt','yuv420p','-r','24','-fps_mode','cfr','-g','48',
            '-keyint_min','48','-sc_threshold','0','-bf','0',
            '-x264-params','open-gop=0:force-cfr=1','-color_primaries','bt709',
            '-color_trc','bt709','-colorspace','bt709','-color_range','tv',
            '-movflags','+faststart','-video_track_timescale','24000',str(output)]


def rgb(path):
    with Image.open(path) as im:
        return np.asarray(im.convert('RGB')).copy()


def psnr(a,b):
    mse=float(np.mean((a.astype(np.float64)-b)**2))
    return round(10*math.log10(255**2/max(mse,1e-10)),3)


def crop(a, box):
    x0,y0,x1,y1=box
    return a[y0:y1,x0:x1]


def quality(a,b):
    delta=a.astype(np.float32)-b
    return {'psnrDb':psnr(a,b),'mae8bit':round(float(np.abs(delta).mean()),4),
            'maxError8bit':int(np.abs(delta).max())}


def metadata_check(path, expected_frames=FRAMES):
    meta=json.loads(execute([ffmpeg_binary('ffprobe'),'-v','error','-show_streams',
        '-show_format','-show_frames','-of','json',str(path)]).stdout)
    streams=meta['streams']
    assert len(streams)==1 and streams[0]['codec_type']=='video','Unexpected streams/audio'
    s=streams[0]
    expected={'codec_name':'h264','profile':'High','pix_fmt':'yuv420p',
              'width':WIDTH,'height':HEIGHT,'sample_aspect_ratio':'1:1',
              'r_frame_rate':'24/1','avg_frame_rate':'24/1',
              'color_range':'tv','color_space':'bt709',
              'color_transfer':'bt709','color_primaries':'bt709'}
    for key,value in expected.items():
        assert s.get(key)==value,(key,s.get(key),value)
    frames=meta['frames']
    assert len(frames)==expected_frames and int(s['nb_frames'])==expected_frames
    assert abs(float(s['duration'])-expected_frames/FPS)<1e-6
    assert frames[0]['key_frame']==1 and frames[0]['pict_type']=='I'
    times=[float(f['best_effort_timestamp_time']) for f in frames]
    assert all(abs(t-i/FPS)<1e-5 for i,t in enumerate(times)),'Irregular timestamps'
    assert all(f['width']==WIDTH and f['height']==HEIGHT for f in frames)
    packet=execute([ffmpeg_binary(),'-v','error','-i',str(path),'-map','0:v:0',
        '-c:v','copy','-bsf:v','h264_mp4toannexb','-frames:v','1','-f','h264','pipe:1']).stdout
    nal_types=[m[0]&31 for m in re.split(b'\x00\x00\x00?\x01',packet) if m]
    assert 5 in nal_types,'First access unit is not IDR'
    data=Path(path).read_bytes()
    assert data.index(b'moov')<data.index(b'mdat'),'Missing fast-start metadata'
    return {'passed':True,'streams':1,'audioStreams':0,'frameCount':len(frames),
            'durationSeconds':float(s['duration']),'firstFrameIDR':True,
            'firstPTS':times[0],'lastPTS':times[-1],'constantFrameRate':True,
            'stream':{k:s[k] for k in expected}}


def decode_frames(path):
    """Decode all frames, explicitly reverse Rec.709 into display-referred sRGB."""
    p=subprocess.Popen([ffmpeg_binary(),'-v','error','-xerror','-i',str(path),
        '-vf',TO_SRGB,'-an','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    size=WIDTH*HEIGHT*3
    try:
        while True:
            data=bytearray()
            while len(data)<size:
                part=p.stdout.read(size-len(data))
                if not part:
                    break
                data.extend(part)
            if not data:
                break
            if len(data)!=size:
                raise RuntimeError('Truncated decoded RGB frame')
            yield np.frombuffer(data,np.uint8).reshape(HEIGHT,WIDTH,3).copy()
        stderr=p.stderr.read().decode(errors='replace')
        if p.wait()!=0:
            raise RuntimeError(stderr)
    finally:
        if p.poll() is None:
            p.terminate()
            p.wait()
        p.stdout.close()
        p.stderr.close()


def validate_video(path, remaining):
    report=metadata_check(path)
    measurements=[]
    means=[]
    static=[]
    motion=[]
    first=previous=None
    frame_hashes=[]
    for i,decoded in enumerate(decode_frames(path)):
        assert i<FRAMES,'Extra decoded frames'
        master=rgb(frame_path(remaining,i))
        m={'frame':i,**quality(master,decoded),
           'regions':{name:quality(crop(master,box),crop(decoded,box)) for name,box in ROIS.items()}}
        m['newBlackPixelsFraction']=float(np.mean((decoded.max(2)<=1)&(master.max(2)>4)))
        m['newWhitePixelsFraction']=float(np.mean((decoded.min(2)>=254)&(master.min(2)<250)))
        assert m['psnrDb']>=37 and m['mae8bit']<=2.0,f'Compression quality failed: {m}'
        assert all(v['psnrDb']>=29 for v in m['regions'].values()),'ROI compression quality failed'
        assert m['newBlackPixelsFraction']<.001 and m['newWhitePixelsFraction']<.001,'Clipping introduced'
        assert float(decoded.std())>12 and float(decoded.mean())>15,'Blank/black frame'
        means.append(float(decoded.mean()))
        measurements.append(m)
        frame_hashes.append(hashlib.sha256(decoded.tobytes()).hexdigest())
        if first is None:
            first=master.copy()
        if previous is not None:
            static.append(quality(crop(previous,ROIS['staticMetal']),crop(master,ROIS['staticMetal']))['mae8bit'])
            motion.append(quality(crop(previous,ROIS['stream']),crop(master,ROIS['stream']))['mae8bit'])
        previous=master
    assert len(measurements)==FRAMES,'Missing decoded frames'
    seam=quality(crop(previous,ROIS['stream']),crop(first,ROIS['stream']))['mae8bit']
    if remaining==0:
        assert len(set(frame_hashes))==1,'Finished clip is not static'
    else:
        assert len(set(frame_hashes))==FRAMES,'Unexpected duplicate moving frames'
        assert max(motion)>0,'Moving clip has no motion'
        assert seam<=max(motion)*1.5+.2,'Loop boundary is an image outlier'
    assert max(static,default=0)<2.0,'Static metal flickers; review denoising'
    return {**report,'passed':True,'fullyDecoded':True,'blackOrMissingFrames':0,
            'psnrDbMinimum':min(m['psnrDb'] for m in measurements),
            'mae8bitMaximum':max(m['mae8bit'] for m in measurements),
            'staticMetalMaxAdjacentMAE':max(static,default=0),
            'streamAdjacentMAE':motion,'streamSeamMAE':seam,
            'frameMeasurements':measurements,'decodedMeanRange':[min(means),max(means)],
            'staticFinishedClip':remaining==0,
            'visualReview':'See pilot_gate.json; numerical checks do not replace visual review.'}


def encode(remaining):
    signature=fingerprint()
    input_hash,hashes=master_inventory(remaining,signature)
    enc_signature=encoder_signature()
    path=clip_path(remaining)
    old=read_json(clip_record(remaining),{})
    if (old.get('passed') and old.get('inputSha256')==input_hash and
        old.get('renderSignature')==signature and
        old.get('encoderSignature')==enc_signature and path.exists() and
        digest(path)==old.get('sha256')):
        print('CLIP_VERIFIED_SKIP',remaining,flush=True)
        return old
    path.parent.mkdir(exist_ok=True)
    partial=path.with_name(path.stem+'.partial.mp4')
    start=time.monotonic()
    args=[ffmpeg_binary(),'-v','error','-y','-framerate',str(FPS),'-start_number','0',
          '-i',str(frame_path(remaining,0).parent/'frame_%04d.png')]+encoding_args(partial)
    if remaining==0:
        # P-frame quantization can creep on an unchanged source. Reuse one IDR
        # so the finished clip is also pixel-identical after lossy decoding.
        single=path.with_name(path.stem+'.single.partial.mp4')
        first_args=args[:args.index('-vf')]+encoding_args(single,1)
        execute(first_args)
        repeat_args=[ffmpeg_binary(),'-v','error','-y','-stream_loop','47',
            '-i',str(single),'-map','0:v:0','-c:v','copy','-frames:v','48',
            '-an','-movflags','+faststart','-video_track_timescale','24000',str(partial)]
        execute(repeat_args)
        single.unlink()
        args=[first_args,repeat_args]
    else:
        execute(args)
    checks=validate_video(partial,remaining)
    value={**checks,'remainingFraction':remaining/100,'path':str(path.relative_to(PACKAGE)).replace('\\','/'),
        'sha256':digest(partial),'bytes':partial.stat().st_size,'renderSignature':signature,
        'encoderSignature':enc_signature,'inputSha256':input_hash,'masterSha256':hashes,
        'encoding':ENCODING,'encodeAndValidateSeconds':round(time.monotonic()-start,3),
        'command':args}
    os.replace(partial,path)
    write_json(clip_record(remaining),value)
    print('CLIP_COMPLETE',remaining,value['bytes'],value['psnrDbMinimum'],flush=True)
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--states',default=','.join(map(str,PILOT)))
    args=parser.parse_args()
    for remaining in map(int,args.states.split(',')):
        assert 0<=remaining<=100
        encode(remaining)
