"""Run with Python 3 in the download directory; verifies and merges all parts."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'parts-manifest.json').read_text(encoding='utf-8'))
for part in manifest['parts']:
    path = root / part['name']
    if not path.is_file() or path.stat().st_size != part['size']:
        raise SystemExit(f"Missing or incomplete part: {part['name']}")
target = root / manifest['archive']
if target.exists():
    raise SystemExit(f'Refusing to overwrite existing archive: {target}')
partial = target.with_name(target.name + '.merging')
if partial.exists():
    raise SystemExit(f'Remove or rename the previous incomplete merge first: {partial}')
combined = hashlib.sha256()
try:
    with partial.open('xb') as output:
        for part in manifest['parts']:
            digest = hashlib.sha256()
            with (root / part['name']).open('rb') as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                    digest.update(block)
                    combined.update(block)
                    output.write(block)
            if digest.hexdigest() != part['sha256']:
                raise RuntimeError(f"SHA256 mismatch: {part['name']}; download this part again")
            print(f"Verified {part['name']}", flush=True)
    if partial.stat().st_size != manifest['size'] or combined.hexdigest() != manifest['sha256']:
        raise RuntimeError('Merged archive checksum mismatch')
    partial.rename(target)
except BaseException:
    partial.unlink(missing_ok=True)
    raise
print(f'OK: {target.name}\nSHA256: {combined.hexdigest()}')
