"""AC-13: `tests/test_auto_cycle.py` и существующие тесты lease/liveness
остаются зелёными без ослабления их проверок.

Зелёный с рождения: эта планка не меняет `orchestrator/lease.py`/
`orchestrator/auto.py`/`orchestrator/cleanup.py` сама (test_author не
трогает код репозитория) — перечисленные файлы уже зелены на сегодняшнем
`main` независимо от этой задачи. Ценность теста — не сегодня, а как
регрессионный барьер: после того как разработчик перенесёт код детача из
`keep/01m1nwchvt-code` (SPEC.md, «Материалы»), этот же прогон обязан
остаться зелёным — задачи новой механики (`force` у `lease.acquire`,
обработчик `SIGTERM` в `auto.cmd_auto`, снимок `holder_before` в
`cleanup.cmd_kill`) не имеют права сломать НИ ОДИН существующий тест
lease/liveness/auto-цикла (SPEC, требование монолита; ADR-0002, принцип
целостности — эти файлы не переписываются и не ослабляются самой
задачей).

Не гоняет полный набор `tests/` (skills/test-authoring: это дело CI) —
только файлы, явно названные критерием (`test_auto_cycle.py`) и
непосредственно про lease/liveness (`test_lease.py`, `test_liveness.py`,
`test_lease_pgid_store.py` — единственные файлы `tests/` с этими именами
на сегодняшний день, см. поиск по каталогу на этапе написания планки).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# SPEC называет `tests/test_auto_cycle.py` явно; «существующие тесты
# lease/liveness» — единственные файлы `tests/` этого имени сегодня.
EXISTING_SUITE_MODULES = (
    "tests.test_auto_cycle",
    "tests.test_lease",
    "tests.test_liveness",
    "tests.test_lease_pgid_store",
)

RUN_TIMEOUT_SEC = 300.0


class Ac13ExistingSuiteStaysGreenTest(unittest.TestCase):

    def test_ac13_existing_lease_liveness_and_auto_cycle_tests_stay_green(self):
        """Прогоняет `python3 -m unittest` по фиксированному, названному
        критерием списку файлов (`tests/test_auto_cycle.py`, `tests/
        test_lease.py`, `tests/test_liveness.py`, `tests/test_lease_
        pgid_store.py`) из корня репозитория и проверяет нулевой код
        возврата.

        Ловит мутацию: перенос механики детача (`force` у `lease.
        acquire`/`run_locked`, обработчик `SIGTERM` в `auto.cmd_auto`,
        `holder_before`/SIGKILL в `cleanup.cmd_kill`) меняет поведение
        существующего вызывателя без учёта его текущих тестов — например,
        новый обязательный параметр без дефолта в `lease.acquire`/
        `run_locked` уронит имеющиеся вызовы этих функций тестами
        `test_lease.py`, либо новый обработчик `SIGTERM`, поставленный
        безусловно на весь процесс, изменит поведение уже существующего
        сценария `test_auto_cycle.py`, гоняющего `cmd_auto` в этом же
        интерпретаторе. Тест покраснеет на ненулевом коде возврата
        прогона.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *EXISTING_SUITE_MODULES],
            cwd=REPO_ROOT, capture_output=True, text=True,
            timeout=RUN_TIMEOUT_SEC)

        self.assertEqual(
            result.returncode, 0,
            f"существующий набор lease/liveness/auto-цикла не зелёный:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
