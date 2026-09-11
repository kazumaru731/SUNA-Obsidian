"""Assemble size proofs and verify exported images with Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json
import zipfile
import sys

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',size)

def image_proof():
    board=Image.new('RGB',(1160,690),(18,21,24))
    d=ImageDraw.Draw(board)
    d.text((40,24),'S U N A  /  O B S I D I A N',font=font(24),fill=(230,218,190))
    d.text((40,61),'Widget assets  /  5 remaining-time states  /  dark & light backgrounds',font=font(15),fill=(150,157,163))
    checks=[]
    for j,remaining in enumerate([100,75,50,25,0]):
        path=OUT/'widget'/f'suna_remaining_{remaining:03d}.png'
        im=Image.open(path).convert('RGBA')
        extrema=im.getchannel('A').getextrema()
        assert im.size==(1024,1024)
        assert extrema==(0,255)
        assert im.getpixel((0,0))[3]==0
        bbox=im.getchannel('A').getbbox()
        assert bbox[0]>0 and bbox[1]>0 and bbox[2]<1024 and bbox[3]<1024
        checks.append({'file':path.name,'dimensions':list(im.size),'alphaExtrema':list(extrema),'nonemptyBounds':list(bbox)})
        for row,bg in enumerate([(29,34,39),(236,234,228)]):
            x,y=40+j*224,110+row*276
            card=Image.new('RGBA',(208,224),(*bg,255))
            small=im.resize((196,196),Image.Resampling.LANCZOS)
            card.alpha_composite(small,(6,3))
            dc=ImageDraw.Draw(card)
            fill=(230,217,185) if row==0 else (68,60,47)
            dc.text((104,198),f'{remaining}%',font=font(16),fill=fill,anchor='mt')
            mask=Image.new('L',card.size,0)
            ImageDraw.Draw(mask).rounded_rectangle((0,0,207,223),radius=24,fill=255)
            board.paste(card.convert('RGB'),(x,y),mask)
    d.text((40,354),'DARK',font=font(12),fill=(145,153,160))
    d.text((40,630),'LIGHT',font=font(12),fill=(145,153,160))
    board.save(OUT/'widget'/'widget_preview.png')
    (OUT/'checks'/'image_validation.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')

def animated_preview():
    frames=[]
    for i in range(144):
        im=Image.open(OUT/'animation'/f'frame_{i:04d}.png').convert('RGB')
        assert im.size==(640,800)
        im.thumbnail((384,480),Image.Resampling.LANCZOS)
        frames.append(im)
    # One palette across the entire film avoids per-frame palette flicker.
    atlas=Image.new('RGB',(384*6,480))
    for j,k in enumerate([0,28,57,86,115,143]):
        atlas.paste(frames[k],(384*j,0))
    palette=atlas.quantize(colors=192,method=Image.Quantize.MEDIANCUT)
    frames=[f.quantize(palette=palette,dither=Image.Dither.FLOYDSTEINBERG) for f in frames]
    durations=[40 if i%6!=5 else 50 for i in range(144)]
    frames[0].save(OUT/'SUNA_motion.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=False,disposal=2)

def package():
    with zipfile.ZipFile(OUT/'SUNA_Obsidian_delivery.zip','w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for path in [ROOT/'README.md',ROOT/'create_hourglass.py',ROOT/'render_delivery.py',ROOT/'encode_animation.py',ROOT/'validate_model.py',ROOT/'package_delivery.py']:
            z.write(path,path.name)
        for path in OUT.rglob('*'):
            if path.is_file() and path.suffix!='.zip' and path.suffix!='.blend1' and not ('animation' in path.parts and path.suffix=='.png') and path.name!='first_preview.png':
                z.write(path,'output/'+path.relative_to(OUT).as_posix())

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'proof'
    if mode=='proof':
        image_proof()
    elif mode=='finish':
        animated_preview()
        package()
    print('PACKAGE_COMPLETE',mode)
