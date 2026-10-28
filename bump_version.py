#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Incrémente la version du plugin et synchronise version.py + metadata.txt.

Usage:
    python bump_version.py [patch|minor|major]
    (défaut : patch)

Exemple : 0.10.3 --patch--> 0.10.4 --minor--> 0.11.0 --major--> 1.0.0

Les notes de la future version s'écrivent en tête de CHANGELOG.md sous le titre
`# [Non publié]` : ce script le renomme en `# [X.Y.Z] - AAAA-MM-JJ` avec la
version calculée, pour ne jamais avoir à deviner le numéro à l'avance. Sans
section « Non publié », il refuse d'incrémenter (release sans notes).
"""

import sys
import re
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent

UNRELEASED_RE = re.compile(r'^# \[(?:Non publié|Unreleased)\][^\n]*$', re.MULTILINE | re.IGNORECASE)


def read_current_version():
    content = (BASE / 'version.py').read_text(encoding='utf-8')
    m = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', content)
    if not m:
        print("ERREUR : __version__ introuvable dans version.py", file=sys.stderr)
        sys.exit(1)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump(part):
    major, minor, patch = read_current_version()
    old = f"{major}.{minor}.{patch}"

    if part == 'major':
        major += 1; minor = 0; patch = 0
    elif part == 'minor':
        minor += 1; patch = 0
    else:  # patch
        patch += 1

    new = f"{major}.{minor}.{patch}"
    new_info = f"({major}, {minor}, {patch})"

    # --- CHANGELOG.md : la première section doit être « Non publié » ---
    # Vérifié avant toute écriture : en cas d'erreur, aucun fichier n'est modifié.
    clog_path = BASE / 'CHANGELOG.md'
    clog_content = clog_path.read_text(encoding='utf-8')
    first_title = next((l for l in clog_content.splitlines() if l.startswith('# [')), '')
    if not UNRELEASED_RE.match(first_title):
        print(
            "ERREUR : CHANGELOG.md ne commence pas par une section « # [Non publié] ».\n"
            f"  Première section trouvée : {first_title or '(aucune)'}\n"
            "  Ajoutez en tête les notes de cette version sous « # [Non publié] » "
            "(le numéro et la date sont renseignés automatiquement).",
            file=sys.stderr
        )
        sys.exit(1)
    clog_content = UNRELEASED_RE.sub(f"# [{new}] - {date.today().isoformat()}", clog_content, count=1)
    clog_path.write_text(clog_content, encoding='utf-8')

    # --- version.py ---
    vpath = BASE / 'version.py'
    content = vpath.read_text(encoding='utf-8')
    content = re.sub(
        r'__version__ = "\d+\.\d+\.\d+"',
        f'__version__ = "{new}"',
        content
    )
    content = re.sub(
        r'__version_info__ = \(\d+, \d+, \d+\)',
        f'__version_info__ = {new_info}',
        content
    )
    vpath.write_text(content, encoding='utf-8')

    # --- metadata.txt ---
    mpath = BASE / 'metadata.txt'
    meta = mpath.read_text(encoding='utf-8')
    meta = re.sub(r'^version=\d+\.\d+\.\d+', f'version={new}', meta, flags=re.MULTILINE)

    # Synchroniser le champ changelog= depuis CHANGELOG.md (10 dernières versions)
    sections = re.split(r'(?=^# \[)', clog_content, flags=re.MULTILINE)
    sections = [s.strip() for s in sections if s.strip()][:10]
    lines_out = []
    for sec in sections:
        sec_lines = sec.splitlines()
        title_m = re.match(r'^# \[(.+?)\]\s*-\s*(\S+)', sec_lines[0])
        if title_m:
            lines_out.append(f"    Version {title_m.group(1)} ({title_m.group(2)})")
        for l in sec_lines[1:]:
            l = l.strip()
            if not l:
                continue
            if l.startswith('###'):
                pass  # on ignore les sous-titres
            elif l.startswith('-'):
                lines_out.append(f"    {l}")
    changelog_val = '\n'.join(lines_out)
    # Nettoyer le markdown et les caractères non-ASCII courants
    changelog_val = re.sub(r'\*\*(.+?)\*\*', r'\1', changelog_val)  # **bold**
    changelog_val = re.sub(r'\*(.+?)\*', r'\1', changelog_val)       # *italic*
    changelog_val = re.sub(r'`(.+?)`', r'\1', changelog_val)         # `code`
    changelog_val = (changelog_val
        .replace('\u2192', '->')
        .replace('\u2190', '<-')
        .replace('\u2026', '...')
        .replace('\u2019', "'").replace('\u2018', "'")
        .replace('\u201c', '"').replace('\u201d', '"')
        .replace('\u00ae', '(R)').replace('\u00a9', '(c)')
    )
    # Remplacer le bloc changelog= (multilignes indentées)
    _repl = f'changelog={changelog_val}\n'
    meta = re.sub(
        r'^changelog=.*?(?=^\S|\Z)',
        lambda m: _repl,
        meta,
        flags=re.MULTILINE | re.DOTALL
    )

    mpath.write_text(meta, encoding='utf-8')

    # --- README.md ---
    rpath = BASE / 'README.md'
    readme = rpath.read_text(encoding='utf-8')
    readme = re.sub(
        r'Version actuelle : \*\*\d+\.\d+\.\d+\*\*',
        f'Version actuelle : **{new}**',
        readme
    )
    rpath.write_text(readme, encoding='utf-8')

    print(f"Version : {old} → {new}", file=sys.stderr)
    print(new)  # stdout : capturé par build.bat
    return 0


if __name__ == '__main__':
    part = sys.argv[1].lower() if len(sys.argv) > 1 else 'patch'
    if part not in ('patch', 'minor', 'major'):
        print(f"ERREUR : argument invalide '{part}'. Utilisez patch, minor ou major.", file=sys.stderr)
        sys.exit(1)
    sys.exit(bump(part))
