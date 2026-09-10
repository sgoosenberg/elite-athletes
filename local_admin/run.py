"""Local-only Supabase admin. Run with python3 local_admin/run.py."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    path = Path(__file__).with_name('secrets.json')
    try:
        settings = json.loads(path.read_text())
        for name in ('SUPABASE_URL', 'SUPABASE_SECRET_KEY'):
            os.environ[name] = settings[name]
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit('Create local_admin/secrets.json using secrets.example.json first.')
    os.environ['ELITE_ATHLETES_STORAGE'] = 'supabase'
    import portal
    portal.cloud_store.configuration()
    portal.main()


if __name__ == '__main__':
    main()
