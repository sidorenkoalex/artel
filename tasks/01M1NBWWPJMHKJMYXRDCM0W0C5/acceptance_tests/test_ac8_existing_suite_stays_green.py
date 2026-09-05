"""AC-8 (SPEC): существующий набор тестов (`tests/`), включая тесты
`orchestrator/fsm_autogate.py`, остаётся зелёным после правки.

Прогон настоящим `python3 -m unittest` (тем же способом, что
`orchestrator/acceptance.run_full_suite`) — единственный источник
истины «проходят зелёными», не пересказ (тот же приём, что
`tasks/T085/acceptance_tests/test_ac7_program_threshold_alert_tests_
stay_green.py`).

Модули этого списка — не произвольное подмножество, а ИМЕННО те файлы,
чьи тесты упражняют код, который трогает эта задача: `test_git_
fixation.py` несёт единственный сегодняшний тест `fsm_autogate.py`
(`AutogateMergeGateHintIncludesShaTest`, называет модуль явно в SPEC);
`test_gitcmd_branch_reads.py`/`test_fsm_branch_correct_status_reads.py`
покрывают `gitcmd.ls_tree_files`/`gitcmd.show` и приём чтения по ветке,
который эта задача переносит на `_autogate_conditions` (тот же
механизм, что SPEC называет прецедентом — `fsm._tests_writing_ac_
state`); `test_guard_schema.py` покрывает `guard.scan_ac_content` —
ядро разбора AC-пометок, общее для обоих источников (диск и ветка).
Полный `python3 -m unittest discover -s tests` (~1350 тестов, ~165с на
песочнице автора) сюда не включён намеренно: сам прогон занял бы
большую часть бюджета `config.ACCEPTANCE_TIMEOUT_SEC` (300с) КАЖДОГО
будущего прогона приёмки ЭТОЙ задачи — общую регрессию `tests/`
целиком на каждый пуш уже держит CI (`.github/workflows/ci.yml`, джоб
`python`, без такого бюджетного потолка).

Зелёный с рождения: эта задача правит только чтение планки условия «а»
внутри `_autogate_conditions` — сами модули ниже её ещё не касаются, и
уже сегодня (до кода задачи) проходят зелёными.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402

MODULES = ("tests.test_git_fixation", "tests.test_gitcmd_branch_reads",
          "tests.test_fsm_branch_correct_status_reads",
          "tests.test_guard_schema")


class ExistingAutogateRelatedTestsStayGreenTest(unittest.TestCase):

    def test_ac8_fsm_autogate_and_branch_reading_precedent_tests_pass(self):
        res = subprocess.run(
            ["python3", "-m", "unittest", *MODULES],
            cwd=config.ROOT, capture_output=True, text=True, timeout=180)

        self.assertEqual(
            res.returncode, 0,
            f"AC-8: {', '.join(MODULES)} обязаны проходить зелёными "
            f"после правки условия «а» автогейта:\n"
            f"{res.stdout[-3000:]}\n{res.stderr[-3000:]}")


if __name__ == "__main__":
    unittest.main()
