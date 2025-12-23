import os, re
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
issues = []
for dirpath, dirnames, filenames in os.walk(root):
    if '.venv' in dirpath or 'venv' in dirpath or '.git' in dirpath:
        continue
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        path = os.path.join(dirpath, fn)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception:
            continue
        # find top-level function defs and their spans (start line, end line) using simple indentation
        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"^(\s*)def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
            if not m:
                continue
            indent = len(m.group(1))
            fname = m.group(2)
            start = i
            # find end of this function by scanning until a line with indentation <= indent and non-blank
            end = len(lines)-1
            for j in range(i+1, len(lines)):
                l = lines[j]
                if l.strip()=='' :
                    continue
                leading = len(l) - len(l.lstrip(' '))
                if leading <= indent and re.match(r"^\s*def\s+|^\s*class\s+", l):
                    end = j-1
                    break
            # now within this function, look for nested defs
            for k in range(start+1, end+1):
                m2 = re.match(r"^(\s*)def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", lines[k])
                if not m2:
                    continue
                nindent = len(m2.group(1))
                nested_name = m2.group(2)
                nested_line = k+1
                # search earlier lines (start+1..k-1) for calls to nested_name
                pattern = re.compile(r"\b"+re.escape(nested_name)+r"\s*\(")
                for s in range(start+1, k):
                    if pattern.search(lines[s]):
                        issues.append((path, fname, nested_name, s+1, nested_line))
                        break

if not issues:
    print('No nested call-before-def issues found.')
else:
    print('Nested issues (file, outer_function, nested_name, first_called_line, nested_def_line):')
    for it in issues:
        print(it)
