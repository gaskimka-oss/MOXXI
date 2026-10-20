import os, re

pattern = re.compile(r'клан[а-я]*', re.IGNORECASE)
with open('clan_occurrences.txt', 'w', encoding='utf-8') as out_f:
    for f in sorted(os.listdir('.')):
        if f.endswith('.py') and not f.startswith('h_clans'):
            with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                for idx, line in enumerate(fh, 1):
                    s = line.strip()
                    if s.startswith('#'):
                        continue
                    if pattern.search(line) and ('"' in line or "'" in line):
                        out_f.write(f'{f}:{idx}: {s}\n')
