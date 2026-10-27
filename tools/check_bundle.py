#!/usr/bin/env python3
"""Read-only package checks; no third-party dependencies or network access."""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ('quiz', 'offer', 'hormozi', 'equalizer', 'design-swarm', 'kp',
          'write-longread', 'stop-slop', 'stephen-king')
errors = []
checks = 0


def check(ok, message):
    global checks
    checks += 1
    if not ok:
        errors.append(message)


for name in SKILLS:
    folder = ROOT / name
    main = folder / 'SKILL.md'
    check(main.is_file(), f'{name}: missing SKILL.md')
    if not main.is_file():
        continue
    text = main.read_text(encoding='utf-8')
    frontmatter = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
    check(bool(frontmatter), f'{name}: invalid frontmatter boundary')
    if frontmatter:
        head = frontmatter.group(1)
        check(bool(re.search(rf'^name:\s*{re.escape(name)}\s*$', head, re.M)),
              f'{name}: mismatched name')
        check(bool(re.search(r'^description:\s*\S', head, re.M)),
              f'{name}: missing description')
    for path in folder.rglob('*'):
        check(not path.is_symlink(), f'{path.relative_to(ROOT)}: symlink not portable')
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        check(path.suffix in ('.md', '.json'), f'{rel}: unexpected file type')
        if path.suffix == '.json':
            try:
                json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, UnicodeError):
                errors.append(f'{rel}: invalid JSON')
        if path.suffix != '.md':
            continue
        content = path.read_text(encoding='utf-8')
        # Known private environment markers and credential formats. Never print matches.
        private = r'/Users/|/home/[^\s/]+/|~/workspace|office/agents/|office-data/|memory\.md|failures\.md'
        secret = r'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{32,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|\b\d{8,12}:[A-Za-z0-9_-]{30,}'
        check(not re.search(private, content, re.I), f'{rel}: private environment marker')
        check(not re.search(secret, content), f'{rel}: possible credential')
        # Validate Markdown relative file links and explicitly referenced bundled resources.
        refs = re.findall(r'\[[^\]]*\]\(([^)]+)\)', content)
        refs += re.findall(r'`((?:references?|evals)/[^`\s]+\.(?:md|json))`', content)
        for ref in refs:
            if re.match(r'\w+://|mailto:|#', ref):
                continue
            ref = ref.split('#', 1)[0]
            if ref:
                check((path.parent / ref).is_file(), f'{rel}: missing local reference {ref}')

for path in ('README.md', 'PORTABILITY.md'):
    content = (ROOT / path).read_text(encoding='utf-8')
    for ref in re.findall(r'\[[^\]]*\]\(([^)]+)\)', content):
        if not re.match(r'\w+://|#', ref):
            check((ROOT / ref.split('#', 1)[0]).is_file(), f'{path}: missing link {ref}')

# Prove clean installation carries all resources and does not depend on the source tree.
with tempfile.TemporaryDirectory(prefix='quiz-offer-install-') as tmp:
    destination = Path(tmp) / 'skills'
    destination.mkdir()
    for name in SKILLS:
        if not (ROOT / name).is_dir():
            continue
        shutil.copytree(ROOT / name, destination / name)
        for source in (ROOT / name).rglob('*'):
            if source.is_file():
                target = destination / source.relative_to(ROOT)
                check(target.is_file() and target.read_bytes() == source.read_bytes(),
                      f'{name}: installation lost resource')

if errors:
    for error in errors:
        print(f'FAIL {error}')
    print(f'{len(errors)} failure(s), {checks} checks')
    sys.exit(1)
print(f'PASS: {len(SKILLS)} skills, {checks} structure/privacy/reference/install checks')
print('Not tested: host auto-discovery, external tools, conversion, or visual quality.')
