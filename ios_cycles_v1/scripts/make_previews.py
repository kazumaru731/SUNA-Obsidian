"""Review boards and same-phase, linear-light whole-frame blends.

Blends are review material only. All production frames originate in Cycles.
"""
import argparse
import json
import math
import os
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import *
from encode_assets import rgb, crop, quality, ROIS, encoding_args, metadata_check, decode_frames

PREVIEWS=PACKAGE/'previews'
FONT_PATH='C:/Windows/Fonts/segoeui.ttf'


def font(size=18):
    try:
        return ImageFont.truetype(FONT_PATH,size)
    except OSError:
        return ImageFont.load_default(size=size)


def linear(a):
    a=a.astype(np.float32)/255
    return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)


def display(a):
    a=np.maximum(a,0)
    return np.clip(np.rint(255*np.where(a<=.0031308,12.92*a,1.055*a**(1/2.4)-.055)),0,255).astype(np.uint8)


def mix(a,b,weight):
    return display((1-weight)*linear(a)+weight*linear(b))


def board(images, labels, path, width=400, height=480, columns=3, footer=None):
    rows=math.ceil(len(images)/columns)
    result=Image.new('RGB',(columns*width,rows*(height+42)+(44 if footer else 0)),(21,25,28))
    draw=ImageDraw.Draw(result)
    for i,(im,label) in enumerate(zip(images,labels)):
        if isinstance(im,np.ndarray):
            im=Image.fromarray(im)
        im=im.convert('RGB').resize((width,height),Image.Resampling.LANCZOS)
        x,y=(i%columns)*width,(i//columns)*(height+42)
        draw.text((x+12,y+10),label,font=font(17),fill=(220,208,183))
        result.paste(im,(x,y+42))
    if footer:
        draw.text((12,result.height-31),footer,font=font(15),fill=(188,190,190))
    result.save(path)


def references():
    PREVIEWS.mkdir(exist_ok=True)
    original=rgb(REFERENCE)
    resized=np.asarray(Image.fromarray(original).resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS))
    reproduced=rgb(PREVIEWS/'reference_reproduced.png')
    periodic=rgb(frame_path(50,0))
    board([resized,reproduced,periodic],
          ['Original HERO / resized','Original scene / 192 samples','Periodic 50% / phase 0'],
          PREVIEWS/'reference_comparison.png',width=440,height=528,
          footer='Approved HERO camera, materials, lighting and AgX. Only grain motion is retimed.')
    phases=[0,12,24,36,47]
    board([rgb(frame_path(r,0)) for r in PILOT],
          [f'Remaining {r}% / t=0' for r in PILOT],
          PREVIEWS/'pilot_states.png',width=293,height=352)
    pairs=[(49,50),(50,51),(1,0)]
    details=[]; labels=[]; measures=[]
    for a,b in pairs:
        left,right=rgb(frame_path(a,0)),rgb(frame_path(b,0))
        blended=mix(left,right,.5)
        box=(315,530,560,844)
        for arr,label in [(left,str(a)+'%'),(blended,'50/50 linear-light mix'),(right,str(b)+'%')]:
            details.append(crop(arr,box)); labels.append(f'{a} -> {b} | {label}')
        measures.append({'pair':[a,b],'phase':0,
             'staticMetalDifference':quality(crop(left,ROIS['staticMetal']),crop(right,ROIS['staticMetal'])),
             'note':'Surface height and refraction are expected to change with remaining sand.'})
    board(details,labels,PREVIEWS/'transition_detail.png',width=330,height=423,
          footer='Magnified lower chamber. Compare endpoints and the synchronized blend; no grain overlay.')
    board([crop(rgb(frame_path(50,f)),(399,520,483,804)) for f in phases],
          [f'50% / frame {f:02d}' for f in phases],PREVIEWS/'loop_phase_detail.png',
          width=168,height=568,columns=5,
          footer='Sampling times: 0, 0.5, 1, 1.5, 47/24 s. t=2 is excluded from the clip.')
    write_json(PACKAGE/'checks'/'reference_comparison.json',{
        'sourceHeroSha256':digest(REFERENCE),'reproducedSha256':digest(PREVIEWS/'reference_reproduced.png'),
        'periodic50Phase0Sha256':digest(frame_path(50,0)),
        'reproducedVsPeriodic':quality(reproduced,periodic),
        'resizedHeroVsReproduced':quality(resized,reproduced),
        'neighborPhase0':measures,
        'note':'Different output resolution and grain time mapping can change stochastic samples; inspect the board.'})


def video():
    from encode_assets import clip_path
    # Five seconds each: two visible wraps and an in-progress third loop.
    # Transition blocks use a 4-second triangle weight while phase advances at 24 fps.
    blocks=[('loop',r,r) for r in [100,50,1,0]]+[
        ('blend',49,50),('blend',50,51),('blend',1,0)]
    count=5*FPS*len(blocks)
    path=PREVIEWS/'loop_and_transition_check.mp4'
    partial=path.with_name(path.stem+'.partial.mp4')
    args=[ffmpeg_binary(),'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24',
          '-s',f'{WIDTH}x{HEIGHT}','-framerate','24','-i','pipe:0']+encoding_args(partial,count)
    log=PACKAGE/'checks'/'preview_encode.log'
    timeline=[]
    with log.open('wb') as err:
        p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err)
        try:
            for block,(kind,a,b) in enumerate(blocks):
                # Exercise the delivered videos, including their independent
                # H.264 quantization, rather than blending only pristine PNGs.
                left=list(decode_frames(clip_path(a)))
                right=left if a==b else list(decode_frames(clip_path(b)))
                assert len(left)==FRAMES and len(right)==FRAMES
                timeline.append({'startSeconds':block*5,'endSeconds':(block+1)*5,
                                 'kind':kind,'remainingPercent':[a,b]})
                for i in range(5*FPS):
                    phase=i%FRAMES
                    w=(1-abs((i/(2*FPS))%2-1)) if kind=='blend' else 0
                    arr=mix(left[phase],right[phase],w) if kind=='blend' else left[phase]
                    im=Image.fromarray(arr)
                    draw=ImageDraw.Draw(im)
                    draw.rectangle((0,0,WIDTH,43),fill=(20,24,27))
                    label=(f'LOOP  |  remaining {a}%' if kind=='loop' else
                           f'SAME-PHASE BLEND  |  {a}% -> {b}%  |  weight {w:.2f}')
                    draw.text((18,11),label,font=font(20),fill=(226,215,187))
                    p.stdin.write(np.asarray(im).tobytes())
            p.stdin.close()
            assert p.wait()==0,log.read_text(errors='replace')
        finally:
            if p.poll() is None:
                p.terminate(); p.wait()
    metadata=metadata_check(partial,count)
    # Decode the complete preview too; it must not end on an incomplete transition block.
    assert sum(1 for _ in decode_frames(partial))==count
    os.replace(partial,path)
    write_json(PACKAGE/'checks'/'preview_validation.json',{
        **metadata,'sha256':digest(path),'timeline':timeline,
        'mixing':'Decoded delivered MP4 frames, synchronized phase, linear-light sRGB blending',
        'videoSource':'Validated H.264 clips, decoded from tagged BT.709 into sRGB before linear-light blending',
        'reviewOnly':True,'renderSignature':fingerprint()})


def compression_board(remaining=50):
    from encode_assets import clip_path
    decoder=decode_frames(clip_path(remaining))
    decoded=next(decoder)
    decoder.close()
    master=rgb(frame_path(remaining,0))
    images=[]; labels=[]
    for name in ['stream','engraving','lowerSand']:
        box=ROIS[name]
        # Letterbox crops, preserve aspect ratio and expose magnification.
        for source,label in [(master,'PNG master'),(decoded,'MP4 decoded to sRGB')]:
            im=Image.fromarray(crop(source,box))
            im.thumbnail((420,300),Image.Resampling.LANCZOS)
            canvas=Image.new('RGB',(440,320),(25,28,30))
            canvas.paste(im,((440-im.width)//2,(320-im.height)//2))
            images.append(canvas); labels.append(f'{name} | {label}')
    board(images,labels,PREVIEWS/'compression_comparison.png',width=440,height=320,columns=2,
          footer='H.264 High / CRF 14. Explicit sRGB -> Rec.709 conversion and inverse for this comparison.')


def denoising_board():
    noisy=rgb(PACKAGE/'checks'/'noisy_50_phase0.png')
    clean=rgb(frame_path(50,0))
    box=(399,520,483,804)
    board([crop(noisy,box),crop(clean,box)],['192 samples / no denoise','192 samples / OIDN Accurate'],
          PREVIEWS/'denoising_comparison.png',width=252,height=852,columns=2,
          footer='Same scene / phase. 3x crop for granule retention review.')
    write_json(PACKAGE/'checks'/'denoising_diagnostic.json',{
        'renderSignature':fingerprint(),'noisySha256':digest(PACKAGE/'checks'/'noisy_50_phase0.png'),
        'denoisedSha256':digest(frame_path(50,0)),
        'difference':quality(noisy,clean),
        'note':'Noisy render is diagnostic only. Review particle visibility in denoising_comparison.png.'})


def seam_and_phone_boards():
    from encode_assets import clip_path
    phases=[44,45,46,47,0,1,2,3]
    images=[]; labels=[]
    for remaining in [50,1,100]:
        for frame in phases:
            images.append(crop(rgb(frame_path(remaining,frame)),(399,520,483,804)))
            labels.append(f'{remaining}% / f{frame:02d}')
    board(images,labels,PREVIEWS/'seam_contact.png',width=126,height=426,columns=8,
          footer='Consecutive frames around each wrap: 44,45,46,47 | 0,1,2,3. Particle motion remains at 24 fps.')
    decoder=decode_frames(clip_path(50))
    decoded=next(decoder); decoder.close()
    master=rgb(frame_path(50,0))
    blended=mix(rgb(frame_path(49,0)),master,.5)
    board([master,decoded,blended],['50% / PNG master','50% / decoded MP4','49% + 50% / 50:50 blend'],
          PREVIEWS/'phone_size_comparison.png',width=352,height=422,
          footer='Illustrative 352 px display width. Actual iPhone / display-density validation is the Mac team\'s task.')


def midpoint_boards():
    images=[]; labels=[]; metrics=[]
    for a,b in [(49,50),(50,51)]:
        actual=rgb(PACKAGE/'checks'/f'true_midpoint_{a}_{b}.png')
        blended=mix(rgb(frame_path(a,0)),rgb(frame_path(b,0)),.5)
        for name,box in [('stream',(399,520,483,804)),('sand',(285,768,586,932))]:
            for arr,label in [(actual,'Cycles at half percent'),(blended,'Same-phase video blend')]:
                c=Image.fromarray(crop(arr,box))
                scale=min(360/c.width,360/c.height)
                c=c.resize((round(c.width*scale),round(c.height*scale)),Image.Resampling.LANCZOS)
                canvas=Image.new('RGB',(380,380),(25,28,30))
                canvas.paste(c,((380-c.width)//2,(380-c.height)//2))
                images.append(canvas); labels.append(f'{(a+b)/2}% {name} | {label}')
        metrics.append({'pair':[a,b],'phase':0,'blendVsTrueMidpoint':quality(blended,actual),
                        'regions':{n:quality(crop(blended,box),crop(actual,box)) for n,box in ROIS.items()}})
    board(images,labels,PREVIEWS/'true_midpoint_comparison.png',width=380,height=380,columns=2,
          footer='A whole-frame blend approximates an intermediate 3D render. Inspect residual softness at magnification.')
    write_json(PACKAGE/'checks'/'midpoint_comparison.json',{'renderSignature':fingerprint(),'measurements':metrics})


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--contacts-only',action='store_true')
    args=parser.parse_args()
    references()
    if (PACKAGE/'checks'/'noisy_50_phase0.png').exists():
        denoising_board()
    if not args.contacts_only:
        compression_board()
        seam_and_phone_boards()
        if (PACKAGE/'checks'/'true_midpoint_49_50.png').exists():
            midpoint_boards()
        video()
