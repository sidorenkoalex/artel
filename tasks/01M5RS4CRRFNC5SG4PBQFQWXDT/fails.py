"""Временный разбор строк падения логов mutation-run (удаляется после шага)."""
import re
import sys
from pathlib import Path

LOGS = Path("/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5RS4CRRFNC5SG4PBQFQWXDT")
TASK = ("Ac3GreenPriorTest", "Ac10EmptyPriorSetTest", "Ac4PriorRedTest",
        "Ac5PriorUnstableTest", "Ac6OneFindingPerIdTest", "Ac7RunScopeTest",
        "Ac8RestoredPathsTest", "Ac9NoTestsFieldTest", "Ac11PrepareTest",
        "Ac12DiffFailureTest", "Ac13OwnerMarkerTest",
        "Ac32AddedFilesRemovedTest", "Ac33SkippedMissingRedTest",
        "Ac30OutOfBoundsTest")
HEAD = re.compile(r"^_{3,} (\S+) _{3,}$")
SITE = re.compile(r"^(tests/[\w./-]+\.py):(\d+): (\w+)")

run = sys.argv[1]
for log in sorted(LOGS.glob(f"01M5RS4CRRFNC5SG4PBQFQWXDT-mutation-run-{run}-p*.log")):
    number = int(log.stem.rsplit("-p", 1)[1])
    current, found = None, []
    for line in log.read_text(errors="replace").splitlines():
        m = HEAD.match(line)
        if m:
            current = m.group(1)
            continue
        s = SITE.match(line)
        if s and current:
            found.append((current, f"{s.group(1)}:{s.group(2)}", s.group(3)))
            current = None
    timeout = "Timeout" in log.read_text(errors="replace")
    for name, site, exc in found:
        mine = name.split(".")[0] in TASK or name.startswith("test_")
        if mine:
            print(f"{number:03d}\t{name}\t{site}\t{exc}" + ("\tTIMEOUT-В-ЛОГЕ" if timeout else ""))
