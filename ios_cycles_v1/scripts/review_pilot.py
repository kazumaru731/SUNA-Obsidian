"""Record the visual pilot decision only after all required evidence is present.

Usage: python review_pilot.py --review-file checks/visual_review_notes.json
The review file must be authored after inspecting the referenced visual evidence.
"""
import argparse
from common import *
from encode_assets import encoder_signature
from package_delivery import collect_clips, build


def review(path):
    notes=read_json(path,{})
    required=['referenceAppearance','sandDenoising','seamContinuity','adjacentBlends','phoneSizeCompression']
    assert notes.get('reviewer') and notes.get('method')
    assert all(notes.get(name,{}).get('passed') is True and notes[name].get('observation') for name in required),'Missing actual visual review observations'
    signature=fingerprint()
    assert notes.get('renderSignature')==signature
    valid,_=collect_clips(verify_masters=True)
    pilots=[v for v in valid if round(v['remainingFraction']*100) in PILOT]
    assert len(pilots)==len(PILOT),'All six validated pilot clips are required'
    reference=read_json(PACKAGE/'checks'/'reference_comparison.json',{})
    assert reference.get('reproducedVsPeriodic',{}).get('mae8bit',999)<.05,'Approved HERO appearance regression'
    for name in ['motion_validation.json','reservoir_validation.json','trajectory_validation.json','preview_validation.json']:
        assert read_json(PACKAGE/'checks'/name,{}).get('passed'),name
    preview_check=read_json(PACKAGE/'checks'/'preview_validation.json',{})
    assert preview_check.get('renderSignature')==signature
    assert digest(PACKAGE/'previews'/'loop_and_transition_check.mp4')==preview_check['sha256']
    names=['reference_comparison.png','loop_and_transition_check.mp4','transition_detail.png',
           'compression_comparison.png','denoising_comparison.png','seam_contact.png','phone_size_comparison.png',
           'decoded_transition_contact.png','true_midpoint_comparison.png']
    evidence=[{'path':'previews/'+name,'sha256':digest(PACKAGE/'previews'/name)} for name in names]
    write_json(PACKAGE/'checks'/'pilot_gate.json',{
        'passed':True,'renderSignature':signature,'encoderSignature':encoder_signature(),
        'reviewedAtUTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'visualReview':notes,'evidence':evidence,
        'pilotClips':[{'remainingFraction':v['remainingFraction'],'path':v['path'],'sha256':v['sha256']} for v in pilots],
        'fullProductionAuthorizedBy':'The supplied BLENDER_HANDOFF_JA.md requests full generation after a passing pilot.',
        'actualIPhoneReview':'Not performed on this Windows PC; Mac team responsibility.'})
    build()
    print('PILOT_GATE_PASSED',signature,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--review-file',required=True)
    args=parser.parse_args()
    review(args.review_file)
