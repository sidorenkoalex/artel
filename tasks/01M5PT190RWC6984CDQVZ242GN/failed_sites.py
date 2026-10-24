"""Место упавшего утверждения каждого убившего узла по логам патчей mutation-run.

Запуск: python3 failed_sites.py <номер прогона> [<номер прогона> …]
Печать: <мутация>\t<тест>\t<файл>:<строка>\t<тип исключения> — последняя
строка `tests/<файл>.py:<n>: <Ошибка>` в секции падения теста.
"""
import re
import sys
from pathlib import Path

LOGS = Path("/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/"
            "01M5PT190RWC6984CDQVZ242GN")
SECTION = re.compile(r"^_{3,} (?:\w+\.)?(test\w+(?:\[[^\]]*\])?) _{3,}$")
SITE = re.compile(r"^(tests/[\w./-]+\.py):(\d+): (\w+)")
SUMMARY = re.compile(r"^={3,} .*(?:passed|failed).* in [\d.]+s")

for run in sys.argv[1:]:
    for log in sorted(LOGS.glob(f"*-mutation-run-{run}-p*.log")):
        number = int(log.stem.rsplit("-p", 1)[1])
        current, site = None, None
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            head = SECTION.match(line.strip())
            if head or line.startswith("=") and "short test summary" in line:
                if current:
                    print(f"{number}\t{current}\t{site}")
                current, site = (head.group(1) if head else None), None
                continue
            found = SITE.match(line.strip())
            if current and found:
                site = f"{found.group(1)}:{found.group(2)}\t{found.group(3)}"
        if current:
            print(f"{number}\t{current}\t{site}")
    control = next(LOGS.glob(f"*-mutation-run-{run}-control.log"), None)
    if control:
        for line in control.read_text(encoding="utf-8", errors="replace").splitlines():
            if SUMMARY.match(line.strip()):
                print(f"control {run}\t{line.strip()}")
