import hashlib, os, tempfile
from pathlib import Path
from urllib.request import urlopen

GCS_PUBLIC_URL = os.environ.get('GCS_MODEL_URL', 'https://storage.googleapis.com/soom-models/movement/aliases/latest.pth')
LOCAL_PATH = Path(os.environ.get('LOCAL_MODEL_PATH', '/opt/models/movement/latest.pth'))
LOCAL_HASH = Path(str(LOCAL_PATH) + '.sha256')

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

def download_to_temp(url: str) -> Path:
    with urlopen(url, timeout=60) as r:
        data = r.read()
    fd, tmp = tempfile.mkstemp(suffix='.pth')
    os.write(fd, data); os.close(fd)
    return Path(tmp)

def main():
    try:
        tmp = download_to_temp(GCS_PUBLIC_URL)
    except Exception as e:
        print('download failed:', e); return
    new_hash = sha256_file(tmp)
    old_hash = LOCAL_HASH.read_text().strip() if LOCAL_HASH.exists() else ''
    if new_hash != old_hash:
        LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp.replace(LOCAL_PATH)
        LOCAL_HASH.write_text(new_hash)
        print('Model updated. Trigger hot‑swap…')
        # TODO: signal your inference service (SIGHUP, REST, file‑watch)
    else:
        print('No model change.')

if __name__ == '__main__':
    main()
