"""AC-1, AC-2 (tasks/T057/SPEC.md): `_age_seconds` и `_pid_alive` — каждая
определена ровно один раз в репозитории (вне `tasks/*/acceptance_tests`).

Сейчас (до задачи) обе определены дважды — байт-в-байт:
`_age_seconds` в `orchestrator/lease.py:44` и `orchestrator/merge_lock.py:28`;
`_pid_alive` в `orchestrator/doctor.py:535` и `orchestrator/merge_lock.py:34`
(находки CR-2026-08-28-3/4, docs/audits/code-revision-2026-08-28.md).

Сканируется весь git-отслеживаемый репозиторий (`git ls-files '*.py'`) —
"репозиторий" в тексте критерия, а не только `orchestrator/` — за
исключением `tasks/*/acceptance_tests`, где живут сами приёмочные тесты
(в т.ч. этот файл, упоминающий оба имени в докстринге кода не в счёт —
сравнивается только `def <имя>(`).
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


def _tracked_py_files_outside_acceptance_tests():
    out = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=REPO_ROOT,
        capture_output=True, text=True, check=True).stdout
    paths = []
    for rel in out.splitlines():
        if not rel:
            continue
        parts = Path(rel).parts
        if parts[0] == "tasks":
            continue
        paths.append(REPO_ROOT / rel)
    return paths


def _definition_sites(name):
    pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
    sites = []
    for path in _tracked_py_files_outside_acceptance_tests():
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            sites.append(str(path.relative_to(REPO_ROOT)))
    return sites


class SingleDefinitionTest(unittest.TestCase):

    def test_ac1_age_seconds_defined_exactly_once(self):
        sites = _definition_sites("_age_seconds")
        self.assertEqual(
            len(sites), 1,
            f"_age_seconds обязана иметь ровно одно определение в "
            f"репозитории (вне tasks/*/acceptance_tests), найдено в: "
            f"{sites}")

    def test_ac2_pid_alive_defined_exactly_once(self):
        sites = _definition_sites("_pid_alive")
        self.assertEqual(
            len(sites), 1,
            f"_pid_alive обязана иметь ровно одно определение в "
            f"репозитории (вне tasks/*/acceptance_tests), найдено в: "
            f"{sites}")


if __name__ == "__main__":
    unittest.main()
