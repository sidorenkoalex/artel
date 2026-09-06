"""AC-6 задачи 01M1TKP08PKB87K8772H69GCXJ: весь существующий набор
тестов (включая `tests/test_branch_freshness_gate.py`, `tests/test_fsm_
map_conflict_autoresolve.py`, `tests/test_fsm_merge_conflict_note.py` —
названные SPEC поимённо) проходит без правки утверждений (`assert`).

Прогоняет именно эти три файла отдельным процессом `python3 -m
unittest` (не полный `tests/` — решение Оператора 05.09, «Перед
завершением» скила test-authoring: планка гоняет только затронутые
модули, полный набор — забота CI) — это ровно те три файла, которые
SPEC называет поимённо как обязанные пройти БЕЗ правки assert'ов.

Зелёный с рождения: эти три файла сегодня уже проходят (они существуют
и не тронуты этой задачей) — тест фиксирует это КАК ГАРАНТИЮ на потом:
после переноса логики в `pull.py` тот же прогон обязан остаться
зелёным, иначе рефакторинг сломал наблюдаемое поведение, которое эти
файлы проверяют (сверка свежести, авторазрешение конфликта карты,
текст неразрешённого конфликта).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

EXISTING_SUITE_MODULES = (
    "tests.test_branch_freshness_gate",
    "tests.test_fsm_map_conflict_autoresolve",
    "tests.test_fsm_merge_conflict_note",
)


class Ac6ExistingSuiteStillGreenTest(unittest.TestCase):

    def test_ac6_branch_freshness_map_conflict_and_note_suites_pass(self):
        """Три существующих тестовых файла, названных SPEC поимённо
        (AC-6), проходят целиком — как сегодня, так и после переноса
        логики подтяжки в `orchestrator/pull.py`.

        Ловит мутацию: рефакторинг меняет наблюдаемое поведение подтяжки
        (например, теряет случай «ветка не отстала», путает аргумент
        merge, меняет текст конфликта) — любой из трёх файлов упадёт, и
        `assertEqual(result.returncode, 0, ...)` это поймает вместе с
        полным выводом `unittest` для диагностики.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *EXISTING_SUITE_MODULES],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300)

        self.assertEqual(
            result.returncode, 0,
            f"один из существующих файлов подтяжки упал:\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
