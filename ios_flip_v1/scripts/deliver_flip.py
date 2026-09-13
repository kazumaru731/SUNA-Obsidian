"""Encode, fully decode, compare the transition, and assemble the Mac handoff."""
import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from PIL.PngImagePlugin import PngInfo

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'ios_flip_v1'
sys.path.insert(0,str(ROOT/'ios_cycles_v1'/'scripts'))
from common import digest,png_info,read_json,write_json,ffmpeg_binary,SOURCE,SOURCE_SHA256
from encode_assets import execute,encoding_args,metadata_check,decode_frames,rgb,quality,TO_VIDEO

def board(paths,labels,output,width=264,height=317,columns=5):
    rows=math.ceil(len(paths)/columns)
    im=Image.new('RGB',(columns*width,rows*(height+32)),(22,26,29))
    draw=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',15)
    for i,(path,label) in enumerate(zip(paths,labels)):
        x,y=i%columns*width,i//columns*(height+32)
        tile=Image.open(path).convert('RGB').resize((width,height),Image.Resampling.LANCZOS)
        im.paste(tile,(x,y+32)); draw.text((x+8,y+6),label,font=font,fill=(233,220,190))
    im.save(output)

def draft_board():
    folder=OUT/'previews'/'draft'
    paths=sorted(folder.glob('frame_*.png'))
    board(paths,[f'{int(p.stem[-4:])/24:.3f} s' for p in paths],OUT/'previews'/'draft_contact.png',columns=4)

def decoded_board():
    record=read_json(OUT/'checks'/'delivery_validation.json',{})
    assert record.get('videoSha256')==digest(OUT/'clips'/'start_flip.mp4')
    frames=[0,7,12,13,19,24,27,29]
    board([OUT/'masters'/'review'/f'frame_{k+12:04d}.png' for k in frames],
          [f'Decoded flip {k/24:.3f} s' for k in frames],
          OUT/'previews'/'decoded_contact.png',columns=4)
    board([OUT/'masters'/'review'/f'frame_{k:04d}.png' for k in [39,40,41,42,43,44]],
          ['Flip 27','Flip 28','Flip 29','Loop 0','Loop 1','Loop 2'],
          OUT/'previews'/'decoded_transition.png',columns=6)

def encode():
    for folder in ['clips','stills','icons','previews','checks','handoff']:
        (OUT/folder).mkdir(exist_ok=True)
    frame_dir=OUT/'masters'/'frames'
    hashes=[]
    render_inputs=''.join(digest(p) for p in [OUT/'scripts'/'render_flip.py',
        OUT/'scripts'/'bake_flip.py',OUT/'bake'/'flip_bake.npz',ROOT/'ios_cycles_v1'/'scripts'/'motion.py'])
    for k in range(31):
        path=frame_dir/f'frame_{k:04d}.png'
        info=png_info(path)
        meta=read_json(path.with_suffix('.json'),{})
        assert meta.get('sha256')==info['sha256'],f'Missing valid frame {k}'
        expected=hashlib.sha256((render_inputs+SOURCE_SHA256+
            str((k+1,192,880,1056,100,'Camera / HERO — studio portrait'))).encode()).hexdigest()
        assert meta.get('renderSignature')==expected,f'Stale render inputs in frame {k}'
        hashes.append(info['sha256'])
    assert read_json(OUT/'checks'/'bake_validation.json')['passed']
    assert read_json(OUT/'checks'/'framing_validation.json')['passed']
    partial=OUT/'clips'/'start_flip.partial.mp4'
    execute([ffmpeg_binary(),'-v','error','-y','-framerate','24','-start_number','0',
             '-i',str(frame_dir/'frame_%04d.png')]+encoding_args(partial,30))
    meta=metadata_check(partial,30)
    decoded=list(decode_frames(partial))
    assert len(decoded)==30
    measurements=[{'frame':k,**quality(rgb(frame_dir/f'frame_{k:04d}.png'),a)} for k,a in enumerate(decoded)]
    assert min(v['psnrDb'] for v in measurements)>35
    assert all(float(a.mean())>5 for a in decoded)
    path=OUT/'clips'/'start_flip.mp4'; os.replace(partial,path)
    shutil.copyfile(frame_dir/'frame_0000.png',OUT/'stills'/'prepare_bottom.png')
    # 8-bit RGB PNG, opaque and unrounded: iOS supplies the icon mask.
    icon=Image.open(OUT/'masters'/'app_icon_1024.png').convert('RGB')
    assert icon.size==(1024,1024)
    icon_meta=read_json(OUT/'masters'/'app_icon_1024.json',{})
    icon_signature=hashlib.sha256((render_inputs+SOURCE_SHA256+
        str((121,192,1024,1024,100,'Camera / WIDGET — readable silhouette'))).encode()).hexdigest()
    assert icon_meta.get('renderSignature')==icon_signature
    assert icon_meta['sha256']==digest(OUT/'masters'/'app_icon_1024.png')
    color_info=PngInfo()
    color_info.add(b'sRGB',bytes([0]))
    icon.save(OUT/'icons'/'AppIcon1024.png',pnginfo=color_info)
    icon_info=png_info(OUT/'icons'/'AppIcon1024.png',strict=False)
    assert icon_info['bitDepth']==8 and icon_info['colorType']==2
    small=Image.new('RGB',(640,180),(22,26,29))
    draw=ImageDraw.Draw(small)
    for x,size in [(20,60),(140,80),(290,120)]:
        small.paste(icon.resize((size,size),Image.Resampling.LANCZOS),(x,25))
        draw.text((x,150),f'{size}px',fill=(230,215,190))
    small.save(OUT/'previews'/'icon_sizes.png')
    # Same time, geometry, lighting and camera at the validation endpoint.
    target_dir=ROOT/'ios_cycles_v1_masters'/'frames'/'remaining_100'
    endpoint=quality(rgb(target_dir/'frame_0000.png'),rgb(frame_dir/'frame_0030.png'))
    last=quality(rgb(target_dir/'frame_0047.png'),rgb(frame_dir/'frame_0029.png'))
    assert endpoint['mae8bit']<.25 and endpoint['psnrDb']>48,endpoint
    assert last['mae8bit']<.25 and last['psnrDb']>48,last
    target_decoded=[]
    for k,a in enumerate(decode_frames(ROOT/'ios_cycles_v1'/'clips'/'remaining_100.mp4')):
        if k<24: target_decoded.append(a)
    seam=quality(decoded[-1],target_decoded[0])
    # Build a viewable proof: 0.5 s preparation, flip, 1 s regular falling sand.
    review=OUT/'masters'/'review'
    review.mkdir(exist_ok=True)
    sequence=[rgb(OUT/'stills'/'prepare_bottom.png')]*12+decoded+target_decoded
    for k,a in enumerate(sequence): Image.fromarray(a).save(review/f'frame_{k:04d}.png')
    execute([ffmpeg_binary(),'-v','error','-y','-framerate','24','-i',str(review/'frame_%04d.png')]+
            encoding_args(OUT/'previews'/'flip_to_timer.mp4',len(sequence)))
    metadata_check(OUT/'previews'/'flip_to_timer.mp4',len(sequence))
    assert sum(1 for _ in decode_frames(OUT/'previews'/'flip_to_timer.mp4'))==len(sequence)
    board([frame_dir/f'frame_{k:04d}.png' for k in range(30)],
          [f'{k/24:.3f} s' for k in range(30)],OUT/'previews'/'all_frames.png',width=220,height=264,columns=6)
    board([frame_dir/'frame_0029.png',target_dir/'frame_0047.png',
           frame_dir/'frame_0030.png',target_dir/'frame_0000.png'],
          ['Flip last: phase 47','Existing phase 47','Flip endpoint: phase 0','Existing phase 0'],
          OUT/'previews'/'transition_match.png',columns=4)
    report={'passed':True,'videoSha256':digest(path),'sourcePreserved':digest(SOURCE)==SOURCE_SHA256,
            'metadata':meta,'allFramesDecoded':True,'frameQuality':measurements,
            'originalLoopEndpointComparison':endpoint,'originalLoopLastPhaseComparison':last,
            'decodedSeamDifference':seam,'masterSha256':hashes,
            'icon':{'width':1024,'height':1024,'mode':'RGB','bitDepth':8,'alpha':False},
            'visualReview':'pending','iPhoneDeviceTest':'not performed'}
    write_json(OUT/'checks'/'delivery_validation.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['frameQuality','masterSha256']},indent=2))

def package():
    validation=read_json(OUT/'checks'/'delivery_validation.json',{})
    visual=read_json(OUT/'checks'/'visual_review.json',{})
    assert validation.get('passed') and visual.get('passed'),'Complete numeric and visual verification first'
    video=OUT/'clips'/'start_flip.mp4'
    assert visual.get('videoSha256')==digest(video)
    assert validation.get('videoSha256')==digest(video)
    validation['visualReview']='checks/visual_review.json'
    validation['visualReviewPassed']=True
    write_json(OUT/'checks'/'delivery_validation.json',validation)
    assets=[]
    for rel,role in [('clips/start_flip.mp4','one_shot_start_flip'),
                     ('stills/prepare_bottom.png','preparing_static'),
                     ('icons/AppIcon1024.png','app_icon_1x1'),
                     ('blend/SUNA_flip_baked.blend','editable_baked_blender_scene')]:
        p=OUT/rel; assets.append({'path':rel,'role':role,'sha256':digest(p),'bytes':p.stat().st_size})
    manifest={'schemaVersion':1,'assetSet':'SUNA start flip and app icon v1','status':'complete_assets',
              'sourceSha256':SOURCE_SHA256,'blenderVersion':'5.0.1','width':880,'height':1056,
              'fps':24,'frameCount':30,'durationSeconds':1.25,
              'videoColor':'BT.709 limited range H.264 High / yuv420p',
              'startState':'Inverted vessel, all sand in the world-lower bulb; use prepare_bottom.png.',
              'nextAsset':'../ios_cycles_v1/clips/remaining_100.mp4',
              'nextPhaseSeconds':0,'nextRemainingFraction':1,
              'timerStartsAfterFlip':True,'loopFlip':False,'backgroundAndCameraFixed':True,
              'assets':assets,'validation':'checks/delivery_validation.json',
              'appIntegrationStatus':'Mac-side responsibility; this delivery contains Blender assets only',
              'sandMethod':'Baked gravity-oriented volume-constrained surface plus gravity-driven contact particles; not a full DEM simulation.'}
    write_json(OUT/'manifest.json',manifest)
    files=[OUT/'manifest.json',OUT/'README.md']
    for folder,patterns in [('clips',['*.mp4']),('stills',['*.png']),('icons',['*.png']),
                            ('blend',['*.blend']),('previews',['*.png','*.mp4']),
                            ('checks',['*.json']),('docs',['*.md']),('scripts',['*.py','*.ps1'])]:
        for pattern in patterns: files+=list((OUT/folder).glob(pattern))
    files=[p for p in files if p.name not in ['render_status.json']]
    path=OUT/'handoff'/'SUNA_flip_icon_v1.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(set(files)): archive.write(p,'ios_flip_v1/'+p.relative_to(OUT).as_posix())
    with zipfile.ZipFile(path) as archive: assert archive.testzip() is None
    path.with_suffix('.zip.sha256').write_text(digest(path)+'  '+path.name+'\n',encoding='ascii')
    print('PACKAGE_COMPLETE',path,path.stat().st_size,digest(path),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--package',action='store_true'); parser.add_argument('--draft-board',action='store_true'); parser.add_argument('--decoded-board',action='store_true')
    args=parser.parse_args()
    if args.package: package()
    elif args.decoded_board: decoded_board()
    elif args.draft_board: draft_board()
    else: encode()
