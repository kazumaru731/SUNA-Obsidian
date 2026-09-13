"""Temporal QC on the delivered/decoded movie, including H.264 quantization."""
import argparse
from common import *
from encode_assets import clip_path, decode_frames, crop, quality, ROIS


def report_path(remaining):
    return PACKAGE/'checks'/'temporal'/f'remaining_{remaining:03d}.json'


def audit(remaining):
    path=clip_path(remaining)
    sha=digest(path)
    code=digest(__file__)
    old=read_json(report_path(remaining),{})
    if old.get('passed') and old.get('clipSha256')==sha and old.get('auditCodeSha256')==code:
        return old
    first=previous=None
    stream=[]; metal=[]; count=0
    for frame in decode_frames(path):
        count+=1
        if first is None:
            first=frame.copy()
        if previous is not None:
            stream.append(quality(crop(frame,ROIS['stream']),crop(previous,ROIS['stream']))['mae8bit'])
            metal.append(quality(crop(frame,ROIS['staticMetal']),crop(previous,ROIS['staticMetal']))['mae8bit'])
        previous=frame
    assert count==FRAMES
    seam_stream=quality(crop(first,ROIS['stream']),crop(previous,ROIS['stream']))['mae8bit']
    seam_metal=quality(crop(first,ROIS['staticMetal']),crop(previous,ROIS['staticMetal']))['mae8bit']
    assert max(metal+[seam_metal])<2.0,'Visible static-region temporal instability after encoding'
    assert seam_stream<=max(stream)*1.5+.2,'Decoded video seam is an outlier'
    if remaining==0:
        assert max(stream+metal+[seam_stream,seam_metal])==0
    result={'passed':True,'remainingFraction':remaining/100,'clipSha256':sha,
        'auditCodeSha256':code,'decodedFrames':count,
        'streamAdjacentMAERange':[min(stream),max(stream)],'streamSeamMAE':seam_stream,
        'staticMetalAdjacentMAEMax':max(metal),'staticMetalSeamMAE':seam_metal,
        'note':'Measurements use every decoded MP4 frame after explicit BT.709 -> sRGB conversion, not just PNG masters.'}
    write_json(report_path(remaining),result)
    print('DECODED_TEMPORAL_QC_PASSED',remaining,seam_stream,seam_metal,flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--states',default=','.join(map(str,PILOT)))
    args=parser.parse_args()
    for remaining in map(int,args.states.split(',')):
        audit(remaining)
