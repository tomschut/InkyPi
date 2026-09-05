"""Verify an already-started isolated inkypi-haos-test container, then replace it."""
import json
import subprocess
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:18084'
NAME = 'inkypi-haos-test'


def command(*args):
    return subprocess.check_output(['podman', *args], text=True).strip()


def verify():
    for _ in range(45):
        try:
            with urllib.request.urlopen(BASE + '/api/current_frame', timeout=2) as response:
                body = response.read()
                headers = response.headers
            break
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    else:
        raise AssertionError(command('logs', NAME))
    assert len(body) == 960000
    for endpoint in ('/', '/api/current_image'):
        with urllib.request.urlopen(BASE + endpoint, timeout=5) as response:
            assert response.status == 200
            if endpoint.endswith('current_image'):
                assert response.read().startswith(b'\x89PNG')
    for key, value in (('If-Modified-Since', headers['Last-Modified']), ('If-None-Match', headers['ETag'])):
        try:
            urllib.request.urlopen(urllib.request.Request(BASE + '/api/current_frame', headers={key: value}))
        except urllib.error.HTTPError as exc:
            assert exc.code == 304
        else:
            raise AssertionError('Expected 304')
    return body, headers['ETag']


first, etag = verify()
print('Initial startup, UI, PNG, 960000-byte BIN and both 304 validators passed', flush=True)
command('exec', NAME, 'python', '-c', '''
from pathlib import Path
import json
p=Path('/app/src/config/device.json')
c=json.loads(p.read_text()); c['name']='Persistence test'; p.write_text(json.dumps(c))
Path('/app/.env').write_text('NEOFRAME_TEST=nonsecret-marker\\n')
Path('/app/src/static/images/persistence-test.txt').write_text('kept')
assert p.resolve()==Path('/data/device.json')
assert Path('/app/.env').resolve()==Path('/data/.env')
''')
command('stop', NAME)
command('rm', NAME)
command('run', '-d', '--init', '--name', NAME, '-p', '127.0.0.1:18084:80', '-v', 'inkypi-haos-test-data:/data:Z', 'inkypi-neoframe-haos:0.1.0')
second, second_etag = verify()
assert first == second and etag == second_etag
command('exec', NAME, 'python', '-c', '''
from pathlib import Path
import json
assert json.loads(Path('/app/src/config/device.json').read_text())['name']=='Persistence test'
assert Path('/app/.env').read_text()=='NEOFRAME_TEST=nonsecret-marker\\n'
assert Path('/app/src/static/images/persistence-test.txt').read_text()=='kept'
''')
print('Container replacement preserved settings, API-key file, images, frame and ETag', flush=True)
command('stop', NAME)
command('rm', NAME)
command('volume', 'rm', 'inkypi-haos-test-data')
print('Isolated test container and volume removed; main service untouched', flush=True)
