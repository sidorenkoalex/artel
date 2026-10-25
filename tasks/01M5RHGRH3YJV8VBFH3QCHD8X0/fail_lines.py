"""Строки падения прогонов mutation-run задачи 01M5RHGRH3YJV8VBFH3QCHD8X0:
для каждого лога патча `<id>-mutation-run-<n>-pNNN.log` — упавший тест и
кадры трассировки `tests/<файл>.py:<строка>` (`in` — кадр вызова, иначе —
место исключения), плюс `Timeout`.

python3 fail_lines.py <номер прогона> [...]
"""
import glob
import re
import sys

TASK = "01M5RHGRH3YJV8VBFH3QCHD8X0"
ROOT = f"/Users/al.sidorenko/projects/artel/.artel/logs/suite-run/{TASK}"
HEAD = re.compile(r"^_+ (\S.*?) _+$")
PLACE = re.compile(r"^(tests/\S+\.py):(\d+):\s?(\S*)")


def main(runs):
    for run in runs:
        for path in sorted(glob.glob(f"{ROOT}/{TASK}-mutation-run-{run}-p*.log")):
            patch = path.rsplit("-p", 1)[1].split(".")[0]
            found = {}
            current = None
            for line in open(path, encoding="utf-8", errors="replace"):
                line = line.rstrip("\n")
                head = HEAD.match(line)
                if head:
                    current = head.group(1)
                    continue
                place = PLACE.match(line)
                if place and current:
                    item = f"{place.group(1).rsplit('/', 1)[-1]}:{place.group(2)} {place.group(3)}"
                    if item not in found.setdefault(current, []):
                        found[current].append(item)
                if "Timeout" in line and current:
                    found.setdefault(current, []).append("Timeout")
            print(f"== прогон {run} патч {patch}")
            for test, places in sorted(found.items()):
                print(f"   {test}: {', '.join(places)}")


if __name__ == "__main__":
    main(sys.argv[1:])
