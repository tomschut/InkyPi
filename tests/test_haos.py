"""Supervisor-style persistent storage and add-on archive checks."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('haos_run', ROOT / 'inkypi_neoframe/run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def seed(app):
    (app / 'src/config').mkdir(parents=True)
    (app / 'src/static/images').mkdir(parents=True)
    (app / 'src/config/device.json').write_text('{"startup":true}')
    (app / 'src/static/images/default.png').write_bytes(b'default')


def test_persistence_across_container_replacement(tmp_path):
    app, replacement, data = (tmp_path / name for name in ('app', 'replacement', 'data'))
    seed(app)
    runner.prepare(app, data)
    config = app / 'src/config/device.json'
    config.write_text(json.dumps({'startup': False, 'playlist_config': {'custom': 'kept'}}))
    (app / '.env').write_text('TEST_KEY=nonsecret-test-value\n')
    images = app / 'src/static/images'
    (images / 'current_frame.bin').write_bytes(b'frame')
    (images / 'upload.png').write_bytes(b'upload')
    runner.prepare(app, data)
    seed(replacement)
    runner.prepare(replacement, data)
    assert json.loads((replacement / 'src/config/device.json').read_text())['playlist_config']=={'custom':'kept'}
    assert (replacement / '.env').read_text()=='TEST_KEY=nonsecret-test-value\n'
    assert (replacement / 'src/static/images/current_frame.bin').read_bytes()==b'frame'
    assert (replacement / 'src/static/images/upload.png').read_bytes()==b'upload'
    assert (replacement / 'src/config/device.json').is_symlink()


def test_addon_archive_contents():
    # inkypi_neoframe/ is self-contained (its Dockerfile clones this fork
    # directly), so there is nothing to sync -- just archive it.
    subprocess.run([sys.executable, str(ROOT / 'scripts/package_addon.py')], check=True)
    with tarfile.open(ROOT / 'dist/inkypi-neoframe-haos.tar.gz') as archive:
        names = archive.getnames()
        for expected in (
            'inkypi_neoframe/config.yaml',
            'inkypi_neoframe/Dockerfile',
            'inkypi_neoframe/run.py',
            'inkypi_neoframe/device.json',
        ):
            assert expected in names
        assert all(not n.startswith('/') and '..' not in Path(n).parts for n in names)
        assert not any('__pycache__' in n for n in names)
