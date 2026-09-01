"""AC-10 (tasks/T095/SPEC.md): задача не добавляет регресс-флаги («Не
входит»: «Регресс-флаги — отдельная строка B-вставки роадмапа»).

Регресс-флаги — конкретный, уже описанный в `docs/roadmap.md` («(2)
регресс-флаги в report — неделя против медианы 4 недель ..., пробитие
порога → alerts(kind=threshold), не считать при <5 задач в окне»)
механизм: сравнение недавнего окна с медианой предыдущих недель и алерт
на пробитие порога. Прямая, механическая проверка ДОБАВЛЕННЫХ строк
зоны задачи (`orchestrator/agent_log.py`, `orchestrator/report.py`) на
конструкции этого механизма — вызов статистической медианы
(`statistics.median`/`median(`) и алерт вида `kind="threshold"` /
`kind='threshold'` (сигнатура регресс-флага из того же места
roadmap.md, отличная от произвольного будущего использования слова
«threshold» как текста).

Зелёный с рождения: на момент написания этих тестов зона задачи ещё не
тронута — ни один из паттернов там не встречается.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

ZONE_FILES = ("orchestrator/agent_log.py", "orchestrator/report.py")

MEDIAN_RE = re.compile(r'\bmedian\s*\(')
THRESHOLD_ALERT_KIND_RE = re.compile(
    r'kind\s*=\s*["\']threshold["\']')


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


class NoRegressionFlagsAddedTest(unittest.TestCase):

    def test_ac10_no_median_based_comparison_added_in_zone(self):
        added = _added_lines(ZONE_FILES)
        if added is None:
            self.skipTest("рабочее дерево на main — диффить не с чем")
        offending = [ln for ln in added if MEDIAN_RE.search(ln)]
        self.assertEqual(
            offending, [],
            f"в зоне задачи добавлено сравнение с медианой — признак "
            f"регресс-флага, который SPEC («Не входит») запрещает для "
            f"этой задачи: {offending}")

    def test_ac10_no_threshold_kind_alert_added_in_zone(self):
        added = _added_lines(ZONE_FILES)
        if added is None:
            self.skipTest("рабочее дерево на main — диффить не с чем")
        offending = [ln for ln in added if THRESHOLD_ALERT_KIND_RE.search(ln)]
        self.assertEqual(
            offending, [],
            f"в зоне задачи добавлен алерт kind=\"threshold\" — сигнатура "
            f"регресс-флага (docs/roadmap.md), запрещённого этой задаче: "
            f"{offending}")


if __name__ == "__main__":
    unittest.main()
