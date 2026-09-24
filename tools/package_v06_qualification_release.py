"""Package the v0.6 qualification PDF, figures, data, and offline explorer."""

from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'docs/qualification-v06'
DATA = ROOT / 'docs/evidence/v0.6-qualification-report-data.json'
OUT = ROOT / 'work/qualification-v06-release'
FIXED_DATE = (2026, 9, 24, 0, 0, 0)


def put(z: zipfile.ZipFile, path: Path, name: str) -> None:
    info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    z.writestr(info, path.read_bytes())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    pdf = PUBLIC / 'EnvLoop-Computer-Use-Qualification-Report.pdf'
    manuscript = PUBLIC / 'EnvLoop-Computer-Use-Qualification-Report.md'
    qa = PUBLIC / 'publication-qa.json'
    html = PUBLIC / 'index.html'
    figures = sorted((PUBLIC / 'figures').glob('*.png'))
    if len(figures) != 5 or not all(p.is_file() for p in (pdf, manuscript, qa, html, DATA)):
        raise ValueError('release inputs incomplete')
    figure_zip = OUT / 'EnvLoop-v0.6-Qualification-Figures.zip'
    with zipfile.ZipFile(figure_zip, 'w') as archive:
        for figure in figures:
            put(archive, figure, figure.name)
    explorer_zip = OUT / 'EnvLoop-v0.6-Qualification-Explorer.zip'
    with zipfile.ZipFile(explorer_zip, 'w') as archive:
        for path in (html, pdf, manuscript, qa, *figures):
            put(archive, path, 'qualification-v06/' + path.relative_to(PUBLIC).as_posix())
        put(archive, DATA, 'evidence/' + DATA.name)
    release_files = [pdf, manuscript, DATA, qa, figure_zip, explorer_zip]
    checksum = OUT / 'checksums.sha256'
    checksum.write_text(''.join(f'{sha(path)}  {path.name}\n' for path in release_files))
    return [*release_files, checksum]


if __name__ == '__main__':
    for item in package():
        print(item)
