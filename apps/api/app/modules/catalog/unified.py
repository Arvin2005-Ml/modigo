"""One on-disk catalog; legacy release identities and provenance are retained."""
import json
from functools import lru_cache
from app.modules.catalog.bootstrap import ROOT

@lru_cache(maxsize=1)
def unified_catalog():
    data = json.loads((ROOT / 'content/activities.json').read_text(encoding='utf-8'))
    if data.get('format') != 'funilo_unified_catalog_v1' or not isinstance(data.get('releases'), dict):
        raise ValueError('Invalid unified catalog')
    seen = set()
    for version, release in data['releases'].items():
        if release.get('version') != version:
            raise ValueError('Release identity mismatch')
        for entry in release['entries']:
            key = entry['key']
            if key in seen:
                raise ValueError('Duplicate activity identity in catalog')
            seen.add(key)
    return data


def release(version):
    return unified_catalog()['releases'][version]


def write_release(data):
    """Replace one authored release in the local source file atomically."""
    import os
    import tempfile
    document = json.loads((ROOT / 'content/activities.json').read_text(encoding='utf-8'))
    if document.get('format') != 'funilo_unified_catalog_v1':
        raise ValueError('Invalid unified catalog')
    if data['version'] not in document['releases']:
        raise ValueError('Unknown release; add it explicitly to the unified catalog')
    document['releases'][data['version']] = data
    target = ROOT / 'content/activities.json'
    fd, name = tempfile.mkstemp(dir=target.parent, prefix='.activities-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(document, output, ensure_ascii=False, indent=2)
            output.write('\n')
        os.replace(name, target)
    finally:
        if os.path.exists(name): os.unlink(name)
    unified_catalog.cache_clear()
