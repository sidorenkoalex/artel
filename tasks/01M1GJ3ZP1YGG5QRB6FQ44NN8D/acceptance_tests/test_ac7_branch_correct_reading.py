"""AC-7 (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md): «Чтение
acceptance_tests/ ветко-корректно: под чужим чекаутом рабочей копии
пульта (не на ветке задачи) команда всё равно читает содержимое
tasks/<id>/acceptance_tests/ с ветки задачи через git, а не с диска
рабочей копии.»

Реальный git, конфликтующее содержимое на диске и на ветке — тот же
приём, что `tests/test_answer_branch_reads.py` и
`tests/test_fsm_branch_correct_status_reads.py`: расхождение диска и
ветки заглушкой `gitcmd.git` не изобразить, а простое отсутствие
каталога на диске (как в `_AnswerRealGitSandbox`) доказывает только
«не падает без диска», не «не подглядывает в диск, если там что-то
есть». Здесь диск несёт ДРУГОЕ содержимое — сильнее.

Фикстурные методы ниже не названы `test_ac<n>_...` намеренно (та же
осторожность, что `tasks/T081/acceptance_tests/test_ac1_non_test_files_
excluded.py`, коммит 7cb7e25): `guard.scan_acceptance_tests` читает
сырой текст `.py`-файлов регуляркой — такой литерал в исходнике ЭТОГО
файла читался бы как настоящее покрытие задачи 01M1GJ3ZP1YGG5QRB6FQ44NN8D
(класс дефекта ANSWER-1, 31.08). Критерию AC-7 не важно, как названы
методы фикстуры — важно лишь то, с какой стороны (ветка или диск) взят
их текст.

Красен до реализации: `_sandbox.discover_dry_run_command_name()` падает
`AssertionError` — новой команды в таблице диспетчера ещё нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

from _sandbox import DryRunSandbox  # noqa: E402

BRANCH_TEST_FILE = '''"""Фикстура ветки — единственно верный источник.

Зелёный с рождения: файл-фикстура другой задачи, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest


class BranchFixtureTest(unittest.TestCase):

    def test_branch_marker(self):
        """Фикстура — существует только на ветке задачи."""
        pass
'''

DISK_TEST_FILE = '''"""Фикстура диска — не должна попасть в вывод.

Зелёный с рождения: файл-фикстура другой задачи, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest


class DiskFixtureTest(unittest.TestCase):

    def test_disk_marker(self):
        """Фикстура — лежит только на диске рабочей копии, не в git."""
        pass
'''

AC_SECTION = "AC-1. Критерий фикстуры.\n"


class BranchCorrectReadingTest(DryRunSandbox):

    def test_ac7_reads_branch_content_ignoring_conflicting_disk_content(self):
        """Ветка задачи несёт `test_from_branch.py`; диск рабочей копии
        (не закоммиченный, лежит только в рабочем дереве текущего
        чекаута — main) несёт ДРУГОЙ, конфликтующий
        `test_from_disk.py`. Текущий чекаут — main, не ветка задачи.
        Вывод обязан назвать файл/метод с ветки и НЕ назвать файл/метод
        с диска.

        Ловит мутацию: команда сканирует
        `tasks/<id>/acceptance_tests/` через `Path.glob`/`os.walk` по
        РАБОЧЕЙ КОПИИ вместо `git show`/`git ls-tree` по ветке (инвариант
        28 нарушен) — тогда вывод назвал бы файл/метод с диска
        (test_from_disk.py/test_disk_marker) вместо файла/метода с
        ветки, либо оба сразу.
        """
        self.commit_fixture(AC_SECTION,
                            {"test_from_branch.py": BRANCH_TEST_FILE})
        self.seed_task()

        current = self.git("rev-parse", "--abbrev-ref", "HEAD").strip()
        self.assertEqual(current, config.MAIN_BRANCH,
                         "подготовка сценария не на главной ветке")

        disk_dir = self.root / "tasks" / self.TASK / "acceptance_tests"
        disk_dir.mkdir(parents=True, exist_ok=True)
        (disk_dir / "test_from_disk.py").write_text(DISK_TEST_FILE,
                                                     encoding="utf-8")

        out = self.run_dry_run()

        self.assertIn("test_from_branch.py", out,
                     "вывод не содержит файл, реально закоммиченный на "
                     "ветке задачи")
        self.assertIn("test_branch_marker", out,
                     "вывод не содержит тестовый метод с ветки задачи")
        self.assertNotIn("test_from_disk.py", out,
                         "вывод содержит файл с диска рабочей копии — "
                         "чтение идёт мимо ветки задачи")
        self.assertNotIn("test_disk_marker", out,
                         "вывод содержит тестовый метод с диска рабочей "
                         "копии — чтение идёт мимо ветки задачи")


if __name__ == "__main__":
    unittest.main()
