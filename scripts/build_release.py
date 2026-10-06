#!/usr/bin/env python3
"""Build the allowlisted skill ZIP. Experiments, fixtures and evidence are never packaged."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '3.0.0-dev'
FILES = ('SKILL.md', 'agents/openai.yaml', 'assets/tiers.json',
         'scripts/ud.py', 'scripts/jev.py', 'scripts/ladder.py', 'scripts/workers.py')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', default='dist')
    p.add_argument('--check', action='store_true')
    a = p.parse_args()
    base = ROOT / '.agents/skills/ultra-delegation'
    present = {str(f.relative_to(base)) for f in base.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    missing, extra = set(FILES) - present, present - set(FILES)
    if missing or extra:
        raise SystemExit(f'skill files do not match the allowlist: missing {sorted(missing)}, extra {sorted(extra)}')
    if a.check:
        return
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f'ultra-delegation-{VERSION}.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            info = zipfile.ZipInfo('ultra-delegation/' + name, date_time=(2026, 10, 4, 0, 0, 0))
            info.external_attr = (0o755 if name.endswith('ud.py') else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (base / name).read_bytes())
    print(target)


if __name__ == '__main__':
    main()
