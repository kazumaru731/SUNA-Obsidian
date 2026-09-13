"""Shared delivery contract and durable, verified frame storage (stdlib only)."""
import hashlib
import json
import os
import struct
import time
import zlib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
PROJECT = PACKAGE.parent
MASTERS = PROJECT / 'ios_cycles_v1_masters'
SOURCE = PROJECT / 'output' / 'SUNA_Obsidian.blend'
REFERENCE = PROJECT / 'output' / 'renders' / 'suna_hero.png'
SOURCE_SHA256 = 'af18c618df4c096ff7580d97f963bd9ba9ec38cc43f8c0d654a9cc3ba879da9f'
SOURCE_COMMIT = '56776a098ca4da6d38daafd3717b8507c4d4197a'
PILOT = [0, 1, 49, 50, 51, 100]
WIDTH, HEIGHT, FPS, FRAMES = 880, 1056, 24, 48
PERIOD = 2.0
RENDER = {
    'engine': 'CYCLES', 'samples': 192, 'adaptiveThreshold': .01,
    'resolution': [WIDTH, HEIGHT], 'pixelAspect': [1, 1],
    'denoiser': 'OPENIMAGEDENOISE', 'denoisingPrefilter': 'ACCURATE',
    'useAnimatedSeed': False, 'seed': 0,
    'maxBounces': 16, 'transmissionBounces': 12, 'glossyBounces': 8,
    'transparentMaxBounces': 16, 'masterFormat': '16-bit RGB PNG',
    'displaySpace': 'sRGB', 'viewTransform': 'AgX',
    'look': 'AgX - Medium High Contrast', 'exposure': .35, 'gamma': 1,
    'camera': 'Camera / HERO — studio portrait', 'device': 'OPTIX',
    'fps': FPS, 'frameCount': FRAMES, 'periodSeconds': PERIOD,
    'motionVersion': 'fixed-volume-periodic-v1',
}

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.partial')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)

def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default

def fingerprint():
    inputs = {'sourceSha256': SOURCE_SHA256, 'render': RENDER}
    for name in ['common.py', 'motion.py', 'render_cycles.py']:
        inputs[name] = digest(PACKAGE/'scripts'/name)
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

def png_info(path, strict=True):
    """Check PNG headers, every CRC, and complete decompression; no Pillow dependency."""
    data = Path(path).read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f'Invalid PNG signature: {path}')
    offset, idat, header, ended = 8, [], None, False
    while offset < len(data):
        length = struct.unpack_from('>I', data, offset)[0]
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+length]
        expected = struct.unpack_from('>I', data, offset+8+length)[0]
        if zlib.crc32(kind+payload) & 0xffffffff != expected:
            raise ValueError(f'PNG checksum failed: {path}')
        if kind == b'IHDR':
            header = struct.unpack('>IIBBBBB', payload)
        elif kind == b'IDAT':
            idat.append(payload)
        elif kind == b'IEND':
            ended = True
        offset += length+12
    if not ended or header is None or offset != len(data):
        raise ValueError(f'Incomplete PNG: {path}')
    width, height, depth, color, _, _, interlace = header
    if strict and (width,height,depth,color,interlace) != (WIDTH,HEIGHT,16,2,0):
        raise ValueError(f'Wrong master format {header}: {path}')
    raw = zlib.decompress(b''.join(idat))
    if strict and len(raw) != height*(1+width*6):
        raise ValueError(f'Wrong scanline data: {path}')
    return {'width':width,'height':height,'bitDepth':depth,'colorType':color,
            'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def frame_path(remaining, frame):
    return MASTERS/'frames'/f'remaining_{remaining:03d}'/f'frame_{frame:04d}.png'

def good_frame(path, signature):
    metadata = read_json(Path(path).with_suffix('.json'))
    if not metadata or metadata.get('renderSignature') != signature:
        return False
    try:
        return digest(path) == metadata['sha256'] and png_info(path)['sha256'] == metadata['sha256']
    except (OSError, ValueError, KeyError, struct.error, zlib.error):
        return False

def check_source():
    actual = digest(SOURCE)
    if actual != SOURCE_SHA256:
        raise RuntimeError('The approved master changed. Preserve changes and review the source before continuing.')

def publish_frame(partial, path, metadata):
    info = png_info(partial)
    os.replace(partial, path)
    write_json(path.with_suffix('.json'), {**metadata, **info})
    return info

def record_event(value):
    path = PACKAGE/'checks'/'render_events.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), **value})+'\n')

def ffmpeg_binary(name='ffmpeg'):
    matches = list((PACKAGE/'tools'/'ffmpeg').glob(f'*/bin/{name}.exe'))
    if len(matches) != 1:
        raise RuntimeError(f'Expected one portable {name} executable, found {matches}')
    return str(matches[0])
