"""Exercise validation and the public CLI without importing Blender."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import generator
import scene_config


class SceneConfiguration(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / 'scene.json').read_text())

    def cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(ROOT / 'generator.py'), *args],
                              cwd=cwd or ROOT, capture_output=True, text=True, timeout=10)

    def test_all_bundled_scenes_validate(self):
        for path in [ROOT / 'scene.json', *sorted((ROOT / 'examples').glob('*.json'))]:
            with self.subTest(scene=path.name):
                scene_config.load_scene(path)

    def test_check_runs_without_blender_or_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.cli('--check', '--scene', str(ROOT / 'scene.json'), cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Scene valid', result.stdout)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_invalid_cli_flags_are_usage_errors(self):
        for args in [('--sceen', 'scene.json'), ('--scene',), ('--preview', '--anim')]:
            with self.subTest(args=args):
                run = self.cli(*args)
                self.assertEqual(run.returncode, 2)
                self.assertNotIn('Traceback', run.stderr)

    def test_missing_key_is_reported_before_blender_import(self):
        del self.cfg['render']['samples']
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            path.write_text(json.dumps(self.cfg))
            result = self.cli('--scene', str(path), cwd=tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('render.samples', result.stderr)
            self.assertNotIn('bpy', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_invalid_values_have_field_specific_errors(self):
        cases = [
            ('render', 'samples', True), ('render', 'resolution', [0, 180]),
            ('camera', 'location', [1, 2]), ('terrain', 'subdivisions', 1),
            ('monoliths', 'count', -1), ('monoliths', 'max_height', 0.5),
            ('fog', 'density', float('nan')), ('render', 'output', ''),
            ('animation', 'frames', 1), ('animation', 'type', 'unknown'),
            ('animation', 'radius', 0), ('animation', 'fps', 0),
        ]
        for section, key, value in cases:
            with self.subTest(field=f'{section}.{key}'):
                cfg = copy.deepcopy(self.cfg)
                cfg[section][key] = value
                with self.assertRaisesRegex(ValueError, f'{section}\\.{key}'):
                    scene_config.validate_scene(cfg)

    def test_animation_required_only_for_animation_modes(self):
        del self.cfg['animation']
        scene_config.validate_scene(self.cfg)
        with self.assertRaisesRegex(ValueError, 'animation'):
            scene_config.validate_scene(self.cfg, require_animation=True)

    def test_dolly_validates_geometry_and_required_coordinates(self):
        self.cfg['animation'].update(type='dolly', start=[0, 0, 1], end=[10, 0, 1])
        scene_config.validate_scene(self.cfg)
        self.cfg['animation']['end'] = [0, 0, 5]
        with self.assertRaisesRegex(ValueError, 'distinct XY'):
            scene_config.validate_scene(self.cfg)
        del self.cfg['animation']['start']
        with self.assertRaisesRegex(ValueError, 'animation.start'):
            scene_config.validate_scene(self.cfg)

    def test_blender_launch_flags_are_kept_separate(self):
        with patch.object(sys, 'argv', ['/app/blender', '--background', '--python', str(ROOT / 'generator.py')]):
            self.assertFalse(generator.arg_repo()['preview'])
        with patch.object(sys, 'argv', ['/app/blender', '--background', '--python', str(ROOT / 'generator.py'), '--', '--anim-preview']):
            opts = generator.arg_repo()
            self.assertTrue(opts['anim'] and opts['anim_preview'])

    def test_bad_json_and_missing_file_report_clean_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            path.write_text('{bad json')
            for candidate in [path, Path(tmp) / 'missing.json']:
                run = self.cli('--check', '--scene', str(candidate))
                self.assertNotEqual(run.returncode, 0)
                self.assertIn('Scene error:', run.stderr)
                self.assertNotIn('Traceback', run.stderr)


if __name__ == '__main__':
    unittest.main()
