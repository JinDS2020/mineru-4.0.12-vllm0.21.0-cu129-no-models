"""Restore byte-identical split archive from public, SHA256-addressed blobs."""
import base64
import hashlib
import gzip
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
REPO = 'JinDS2020/mineru-4.0.12-vllm0.21.0-cu129-no-models'
TAG = 'mineru-4.0.12-vllm0.21.0-cu129-no-models'
recipe = json.loads(gzip.decompress((ROOT / 'archive-recipe.json.gz').read_bytes()))
manifest = json.loads((ROOT / 'distribution/parts-manifest.json').read_text())
target = Path(os.environ['RUNNER_TEMP']) / 'mineru-release-parts'
target.mkdir(exist_ok=True)

def gh(*args):
    return subprocess.check_output(['gh', *args], text=True).strip()

existing = json.loads(gh('release', 'view', TAG, '--repo', REPO, '--json', 'assets'))['assets']
existing = {item['name']: item for item in existing}
expected_parts = {part['name']: part for part in manifest['parts']}
pool = ThreadPoolExecutor(max_workers=3)
pending_uploads = []

class PartsWriter:
    def __init__(self):
        self.index = 0
        self.output = None
        self.part_hash = None
        self.total_hash = hashlib.sha256()
        self.position = 0
        self.total = 0

    def write(self, data):
        self.total_hash.update(data)
        self.total += len(data)
        cursor = 0
        while cursor < len(data):
            if self.output is None:
                part = manifest['parts'][self.index]
                self.output = (target / part['name']).open('xb')
                self.part_hash = hashlib.sha256()
                self.position = 0
            part = manifest['parts'][self.index]
            chunk = data[cursor:cursor + min(part['size'] - self.position, len(data) - cursor)]
            self.output.write(chunk)
            self.part_hash.update(chunk)
            cursor += len(chunk)
            self.position += len(chunk)
            if self.position == part['size']:
                self.output.close()
                self.output = None
                assert self.part_hash.hexdigest() == part['sha256'], part['name']
                print('Verified part:', part['name'], flush=True)
                pending_uploads.append(pool.submit(upload, target / part['name']))
                self.index += 1

def upload(path):
    if path.name in existing:
        expected = expected_parts.get(path.name)
        if expected is None:
            expected = {'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        previous = existing[path.name]
        if previous['size'] == expected['size'] and previous.get('digest') == 'sha256:' + expected['sha256']:
            print('Already uploaded and verified:', path.name, flush=True)
            return
    for attempt in range(1, 4):
        print(f'Uploading {path.name}, attempt {attempt}', flush=True)
        result = subprocess.run(['gh', 'release', 'upload', TAG, str(path), '--repo', REPO, '--clobber'])
        if result.returncode == 0:
            return
        time.sleep(10)
    raise RuntimeError('Upload failed: ' + path.name)

writer = PartsWriter()
for record in recipe['records']:
    if 'literal' in record:
        writer.write(base64.b64decode(record['literal']))
        continue
    consumed = 0
    blob_hash = hashlib.sha256()
    digest = record['blob']
    print('Fetching verified layer:', digest, record['size'], flush=True)
    for attempt in range(1, 6):
        try:
            token_url = 'https://ghcr.io/token?service=ghcr.io&scope=repository:' + recipe['registry_repo'] + ':pull'
            with urllib.request.urlopen(token_url, timeout=90) as response:
                token = json.load(response)['token']
            headers = {'Authorization': 'Bearer ' + token}
            if consumed:
                headers['Range'] = f'bytes={consumed}-'
            url = 'https://ghcr.io/v2/' + recipe['registry_repo'] + '/blobs/sha256:' + digest
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
                if consumed and response.status != 206:
                    # Some blob stores ignore Range. Discard the verified prefix.
                    skip = consumed
                    while skip:
                        block = response.read(min(skip, 8 * 1024 * 1024))
                        if not block:
                            raise EOFError('Unexpected EOF while skipping prefix')
                        skip -= len(block)
                elif consumed:
                    assert response.headers['Content-Range'].startswith(f'bytes {consumed}-')
                while consumed < record['size']:
                    block = response.read(min(8 * 1024 * 1024, record['size'] - consumed))
                    if not block:
                        raise EOFError('Unexpected EOF in layer')
                    blob_hash.update(block)
                    writer.write(block)
                    consumed += len(block)
            break
        except (OSError, EOFError, urllib.error.URLError, http.client.IncompleteRead):
            if attempt == 5:
                raise
            print(f'Retrying layer at offset {consumed}', flush=True)
            time.sleep(5)
    assert consumed == record['size'] and blob_hash.hexdigest() == digest
assert writer.output is None and writer.index == len(manifest['parts'])
assert writer.total == manifest['size'] and writer.total_hash.hexdigest() == manifest['sha256']
print('PASS: reconstructed archive matches original SHA256:', writer.total_hash.hexdigest(), flush=True)
for future in pending_uploads:
    future.result()
pool.shutdown(wait=True)
for path in sorted((ROOT / 'distribution').iterdir()):
    shutil.copy2(path, target / path.name)
    upload(target / path.name)
remote = json.loads(gh('release', 'view', TAG, '--repo', REPO, '--json', 'assets'))['assets']
remote = {item['name']: item for item in remote}
for path in target.iterdir():
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    assert remote[path.name]['size'] == path.stat().st_size
    assert remote[path.name]['digest'] == 'sha256:' + digest.hexdigest(), path.name
gh('release', 'edit', TAG, '--repo', REPO, '--draft=false', '--latest')
print('PUBLISHED:', gh('release', 'view', TAG, '--repo', REPO, '--json', 'url', '--jq', '.url'), flush=True)
