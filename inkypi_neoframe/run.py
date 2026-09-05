"""Persist user state in Supervisor's /data volume, then start InkyPi."""
import os
from pathlib import Path
import shutil
import sys


def prepare(app=Path('/app'), data=Path('/data')):
    data.mkdir(parents=True, exist_ok=True)
    for relative, name in (
        ('src/config/device.json', 'device.json'),
        ('src/static/images', 'images'),
        ('.env', '.env'),
    ):
        source = app / relative
        target = data / name
        if not target.exists():
            if source.is_dir():
                shutil.copytree(source, target)
            elif source.exists():
                shutil.copy2(source, target)
            else:
                target.touch(mode=0o600)
        if source.is_symlink():
            source.unlink()
        elif source.is_dir():
            shutil.rmtree(source)
        elif source.exists():
            source.unlink()
        source.symlink_to(target, target_is_directory=target.is_dir())


if __name__ == '__main__':
    prepare()
    os.chdir('/app')
    os.execv(sys.executable, [sys.executable, 'src/inkypi.py'])
