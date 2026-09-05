"""AC-3 (tasks/01M1R5B570KMS26NQ6J2G2WXZB/SPEC.md): grep по `tests/` на
использование `_ts_ago`/`config.LEASE_STALE_AFTER_SEC` с запасом ≤ 5
секунд от порога со стороны «ещё не протух» — каждое найденное такое
место (кроме уже покрытых AC-1/AC-2 в `tests/test_parallel_limit.py`)
должно быть приведено к тому же приёму устранения зависимости от
реального времени.

На момент постановки SPEC такое место во всём `tests/` было ровно одно
(`tests/test_parallel_limit.py:68`, уже отдельно покрыт AC-1/AC-2) — сам
SPEC («Материалы») явно требует не считать этот список готовым, а
перепроверить. Тест ниже воспроизводит тот же grep программно и
дважды: сначала как факт (baseline — вне `test_parallel_limit.py`
рискованных мест нет и сегодня), затем как регрессионный барьер —
критерий будет нарушен, если ГДЕ УГОДНО в `tests/`, кроме уже
проверяемого файла, появится точно такой же рискованный запас (свежая
копипаста старого приёма в `test_lease.py`/`test_merge_lock.py`/
`test_release.py` или в новом файле).

Зелёный с рождения: на диске сегодня (проверено эмпирически перед
записью — `grep -rn "LEASE_STALE_AFTER_SEC\\s*-" tests/` даёт
единственное совпадение, и оно в `test_parallel_limit.py`) вне
`test_parallel_limit.py` рискованных мест нет — тест сразу проходит и
охраняет это состояние как инвариант задачи.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

TESTS_DIR = REPO_ROOT / "tests"
RISKY_MARGIN_SEC = 5
COVERED_ELSEWHERE = {"test_parallel_limit.py"}

# Ищет каждый ВЫЗОВ `_ts_ago(config.LEASE_STALE_AFTER_SEC ...)` — именно
# так во всём `tests/` конструируется метка heartbeat относительно
# порога (см. SPEC, «Материалы»: `tests/sandbox.py::_ts_ago` — единственное
# определение). Не голое упоминание имени константы: докстринги вида
# «Ловит мутацию: если порог config.LEASE_STALE_AFTER_SEC …» упоминают имя
# константы прозой, без вызова `_ts_ago`, и не должны попадать в находки.
THRESHOLD_USAGE = re.compile(
    r"_ts_ago\(\s*config\.LEASE_STALE_AFTER_SEC\s*(?:([+-])\s*(\d+))?\s*\)")


def _risky_margin(sign, digits) -> bool:
    """Со стороны «ещё не протух» — это `-` (запас = число) или голое
    употребление без знака (запас = 0); сторона `+` всегда безопасна:
    добавление времени только удаляет heartbeat от границы, не
    приближает."""
    if sign == "+":
        return False
    margin = int(digits) if digits else 0
    return margin <= RISKY_MARGIN_SEC


def find_risky_threshold_usages(exclude_filenames=COVERED_ELSEWHERE):
    findings = []
    for path in sorted(TESTS_DIR.glob("*.py")):
        if path.name in exclude_filenames:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in THRESHOLD_USAGE.finditer(line):
                if _risky_margin(match.group(1), match.group(2)):
                    findings.append((str(path.relative_to(REPO_ROOT)),
                                     lineno, line.strip()))
    return findings


class NoNewRiskyThresholdMarginTest(unittest.TestCase):

    def test_ac3_grep_audit_finds_no_risky_margin_outside_test_parallel_limit(self):
        """Живой grep по `tests/*.py` (кроме `test_parallel_limit.py`, уже
        покрытого AC-1/AC-2) не находит употреблений
        `config.LEASE_STALE_AFTER_SEC` с запасом ≤ 5 секунд со стороны
        «ещё не протух».

        Ловит мутацию: копипаста старого приёма `_ts_ago(config.
        LEASE_STALE_AFTER_SEC - 1)` (или любого другого запаса ≤ 5 сек
        с той же стороны) в `test_lease.py`, `test_merge_lock.py`,
        `test_release.py` или новый тестовый файл — находка сразу
        попадёт в список и тест покраснеет.
        """
        findings = find_risky_threshold_usages()

        self.assertEqual(
            findings, [],
            f"найден рискованный запас (≤{RISKY_MARGIN_SEC} сек, сторона "
            f"«ещё не протух») вне test_parallel_limit.py — приведи к "
            f"приёму AC-1/AC-2: {findings}")


if __name__ == "__main__":
    unittest.main()
