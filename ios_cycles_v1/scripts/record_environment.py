"""Record reproducibility information without host names or device identifiers."""
import platform
import subprocess
import sys
import numpy
import PIL
from common import *

if __name__=='__main__':
    ffmpeg=subprocess.run([ffmpeg_binary(),'-version'],capture_output=True,text=True,check=True).stdout.splitlines()[0]
    gpu=subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total',
        '--format=csv,noheader'],capture_output=True,text=True,check=True).stdout.strip()
    source_files={p.name:digest(p) for p in (MASTERS/'source').iterdir() if p.is_file()}
    value={'operatingSystem':platform.platform(),'pythonVersion':sys.version,
        'numpyVersion':numpy.__version__,'pillowVersion':PIL.__version__,
        'ffmpeg':ffmpeg,'gpuNameDriverMemory':gpu,'blenderVersion':'5.0.1',
        'ffmpegZipSha256':digest(PACKAGE/'tools'/'ffmpeg-release-essentials.zip'),
        'sourceCopiesSha256':source_files,'renderSignature':fingerprint()}
    write_json(PACKAGE/'checks'/'environment.json',value)
    print('ENVIRONMENT_RECORDED')
