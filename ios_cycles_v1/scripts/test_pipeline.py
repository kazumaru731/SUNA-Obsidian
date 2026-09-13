"""Failure-path tests: no corrupt master reuse, no premature complete delivery."""
import json
import shutil
import tempfile
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image
from common import *
from package_delivery import build
from run_batch import alive, main


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=PACKAGE/'checks')
        self.root=Path(self.temp.name)
        self.path=self.root/'frame_0000.png'
        shutil.copyfile(frame_path(50,0),self.path)
        write_json(self.path.with_suffix('.json'),{'sha256':digest(self.path),'renderSignature':fingerprint()})

    def tearDown(self):
        self.temp.cleanup()

    def test_good_frame_and_changed_settings(self):
        self.assertTrue(good_frame(self.path,fingerprint()))
        self.assertFalse(good_frame(self.path,'a different render configuration'))

    def test_corrupt_and_truncated_master_rejected(self):
        data=bytearray(self.path.read_bytes())
        data[len(data)//2]^=1
        self.path.write_bytes(data)
        self.assertFalse(good_frame(self.path,fingerprint()))
        self.path.write_bytes(data[:100])
        self.assertFalse(good_frame(self.path,fingerprint()))

    def test_no_hash_sidecar_no_reuse(self):
        self.path.with_suffix('.json').unlink()
        self.assertFalse(good_frame(self.path,fingerprint()))

    def test_wrong_bit_depth_rejected_even_with_matching_hash(self):
        Image.new('RGB',(WIDTH,HEIGHT)).save(self.path)
        write_json(self.path.with_suffix('.json'),{'sha256':digest(self.path),'renderSignature':fingerprint()})
        self.assertFalse(good_frame(self.path,fingerprint()))

    def test_no_current_frame_without_file(self):
        self.path.unlink()
        self.assertFalse(good_frame(self.path,fingerprint()))

    def test_controller_identifies_own_process(self):
        self.assertTrue(alive(os.getpid()))
        self.assertFalse(alive(999999999))


class CompletionTests(unittest.TestCase):
    def test_full_generation_cannot_start_without_review(self):
        if (PACKAGE/'checks'/'pilot_gate.json').exists():
            self.skipTest('Pilot has already been reviewed; preserve that evidence.')
        with patch('run_batch.subprocess.Popen') as process:
            with self.assertRaisesRegex(RuntimeError,'pilot must pass'):
                main('full','unused-blender.exe')
            process.assert_not_called()

    def test_partial_assets_cannot_be_marked_complete(self):
        # This assertion applies to an unfinished pilot. Once production is
        # complete, normal --require-complete validation replaces this test.
        if all((PACKAGE/'clips'/f'remaining_{r:03d}.mp4').exists() for r in range(101)):
            self.skipTest('All states are now present; run full delivery validation.')
        with self.assertRaisesRegex(RuntimeError,'Delivery incomplete'):
            build(require_complete=True)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    write_json(PACKAGE/'checks'/'pipeline_tests.json',{
        'passed':result.wasSuccessful(),'testsRun':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'renderSignature':fingerprint(),'scope':'Corrupt/missing/stale masters, incomplete delivery rejection, gate rejection, and process liveness.'})
    sys.exit(0 if result.wasSuccessful() else 1)
