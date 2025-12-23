import re
import os

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
issues = []
for dirpath, dirnames, filenames in os.walk(root):
    # skip virtualenvs and .git
    if '.venv' in dirpath or 'venv' in dirpath or '.git' in dirpath:
        continue
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        path = os.path.join(dirpath, fn)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            continue
        text = ''.join(lines)
        # find defs
        defs = {}
        for i, line in enumerate(lines, start=1):
            m = re.match(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(|^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:(]", line)
            if m:
                name = m.group(1) or m.group(2)
                defs[name] = i
        # for each def, search for first call
        for name, def_line in defs.items():
            # skip common dunder names
            if name.startswith('__') and name.endswith('__'):
                continue
            pattern = re.compile(r"\b" + re.escape(name) + r"\s*\(")
            first_call = None
            for i, line in enumerate(lines, start=1):
                if pattern.search(line):
                    first_call = i
                    break
            if first_call and first_call < def_line:
                issues.append((path, name, first_call, def_line))

if not issues:
    print('No potential call-before-def issues found.')
else:
    print('Potential issues (file, name, first_call_line, def_line):')
    for it in issues:
        print(it)
