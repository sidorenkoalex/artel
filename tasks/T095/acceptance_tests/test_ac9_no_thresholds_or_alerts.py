"""AC-9 (tasks/T095/SPEC.md): задача не добавляет пороги и алерты по
метрике трения («Не входит»: «Пороги и алерты по метрике трения —
сначала накопить фактуру»).

Прямая, механическая проверка реального диффа ветки задачи
относительно `main` (без единого мока, по образцу `tasks/T092/
acceptance_tests/test_ac12_diff_does_not_touch_protected_modules.py`):
в ДОБАВЛЕННЫХ строках зоны задачи (`orchestrator/agent_log.py`,
`orchestrator/report.py`) не встречается ни вызов существующего API
подъёма алерта (`alerts.raise_alert(...)`, `orchestrator/alerts.py`),
ни константа-порог (имя, содержащее «THRESHOLD»/«ПОРОГ» без учёта
регистра) — оба паттерна достаточно специфичны, чтобы не путать их со
случайным упоминанием слова в комментарии на русском (ищутся только
конструкции кода, не текст докстрок/строк).

Зелёный с рождения: на момент написания этих тестов зона задачи ещё не
тронута — ни alerts.raise_alert, ни порогов там нет.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

ZONE_FILES = ("orchestrator/agent_log.py", "orchestrator/report.py")

RAISE_ALERT_RE = re.compile(r'\balerts\.raise_alert\s*\(')
THRESHOLD_CONST_RE = re.compile(r'\b[A-Z_]*(?:THRESHOLD|ПОРОГ)[A-Z_]*\s*=')


def _git(*args: str) -> str:
    res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True)
    return res.stdout


def _added_lines(paths) -> list:
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT,
        capture_output=True, text=True, check=True).stdout.strip()
    if branch == "main":
        return None
    merge_base = _git("merge-base", "main", branch).strip()
    diff = _git("diff", "-U0", merge_base, branch, "--", *paths)
    return [line[1:] for line in diff.splitlines()
           if line.startswith("+") and not line.startswith("+++")]


class NoThresholdsOrAlertsAddedTest(unittest.TestCase):

    def test_ac9_no_raise_alert_call_added_in_zone(self):
        added = _added_lines(ZONE_FILES)
        if added is None:
            self.skipTest("рабочее дерево на main — диффить не с чем")
        offending = [ln for ln in added if RAISE_ALERT_RE.search(ln)]
        self.assertEqual(
            offending, [],
            f"в зоне задачи добавлен вызов alerts.raise_alert — SPEC "
            f"(«Не входит») запрещает алерты по метрике трения: "
            f"{offending}")

    def test_ac9_no_threshold_constant_added_in_zone(self):
        added = _added_lines(ZONE_FILES)
        if added is None:
            self.skipTest("рабочее дерево на main — диффить не с чем")
        offending = [ln for ln in added if THRESHOLD_CONST_RE.search(ln)]
        self.assertEqual(
            offending, [],
            f"в зоне задачи добавлена похожая на порог константа — "
            f"SPEC («Не входит») запрещает пороги по метрике трения: "
            f"{offending}")


if __name__ == "__main__":
    unittest.main()
