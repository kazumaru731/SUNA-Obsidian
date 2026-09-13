"""Extract representative frames from the final decoded transition movie."""
from common import *
from encode_assets import decode_frames
from make_previews import board, PREVIEWS

times=list(range(20,35))
selected={t*FPS:t for t in times}
images=[]; labels=[]
for index,frame in enumerate(decode_frames(PREVIEWS/'loop_and_transition_check.mp4')):
    if index in selected:
        images.append(frame)
        labels.append(f'Decoded preview / t={selected[index]}s')
assert len(images)==len(times)
board(images,labels,PREVIEWS/'decoded_transition_contact.png',width=220,height=264,columns=5,
      footer='Rows: 49 <-> 50%, 50 <-> 51%, 1 <-> 0%. Both endpoints and intermediate weights from the delivered preview.')
print('TRANSITION_VIDEO_FRAMES_EXTRACTED')
