"""AC-6 (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md): «Вывод команды
содержит текст «сухой прогон — не является прохождением приёмки»;
результат команды не записывается ни в один артефакт, БД или журнал
задачи.»

Фикстурный метод ниже не назван `test_ac<n>_...` намеренно (та же
осторожность, что `tasks/T081/acceptance_tests/test_ac1_non_test_files_
excluded.py`, коммит 7cb7e25): `guard.scan_acceptance_tests` читает
сырой текст `.py`-файлов регуляркой — такой литерал в исходнике ЭТОГО
файла читался бы как настоящее покрытие задачи 01M1GJ3ZP1YGG5QRB6FQ44NN8D
(класс дефекта ANSWER-1, 31.08).

Красен до реализации: `_sandbox.discover_dry_run_command_name()` падает
`AssertionError` — новой команды в таблице диспетчера ещё нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import store  # noqa: E402

from _sandbox import DryRunSandbox  # noqa: E402

TEST_FILE = '''"""Фикстура.

Зелёный с рождения: файл-фикстура другой задачи, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest


class FixtureTest(unittest.TestCase):

    def test_ordinary_method(self):
        """Фикстура."""
        pass
'''

AC_SECTION = "AC-1. Критерий фикстуры.\n"

MARKER_TEXT = "сухой прогон — не является прохождением приёмки"


class DryRunMarkerAndNoPersistenceTest(DryRunSandbox):

    def test_ac6_output_contains_the_exact_marker_text(self):
        """Дословный (не перефразированный) текст критерия обязан быть в
        выводе — Оператор по этой фразе на приёмке отличает предпросмотр
        от настоящего прохождения (Контекст SPEC).

        Ловит мутацию: реализация печатает смысловой аналог
        («это только просмотр», «dry run, не приёмка») без дословной
        фразы критерия — Оператор перестаёт видеть однозначный маркер,
        assertIn с точным текстом это ловит.
        """
        self.commit_fixture(AC_SECTION, {"test_x.py": TEST_FILE})
        self.seed_task()

        out = self.run_dry_run()

        self.assertIn(MARKER_TEXT, out,
                     "вывод не содержит обязательный дословный текст "
                     "«сухой прогон — не является прохождением приёмки»")

    def test_ac6_result_is_not_persisted_anywhere(self):
        """До вызова на диске рабочей копии нет каталога `tasks/<id>/`
        (артефакты задачи-фикстуры живут только на её ветке) — после
        сухого прогона его по-прежнему нет; журнал и БД не тронуты.

        Ловит мутацию: команда материализует прочитанное на ветке
        содержимое во временный каталог ради разбора и забывает его
        убрать, оставляя `tasks/<id>/` на диске рабочей копии, либо
        пишет собственный файл-сводку рядом — оба случая тест ловит
        проверкой отсутствия каталога на диске ДО и ПОСЛЕ вызова.
        """
        self.commit_fixture(AC_SECTION, {"test_x.py": TEST_FILE})
        self.seed_task()

        task_dir = self.root / "tasks" / self.TASK
        self.assertFalse(task_dir.exists(),
                         "подготовка сценария несёт каталог задачи на диске")
        steps_before = store.task_steps(store.db(), self.TASK)

        self.run_dry_run()

        self.assertFalse(
            task_dir.exists(),
            "после сухого прогона на диске рабочей копии появился "
            "каталог задачи — результат где-то материализован и оставлен")
        steps_after = store.task_steps(store.db(), self.TASK)
        self.assertEqual(len(steps_after), len(steps_before),
                         "сухой прогон дописал запись в журнал задачи")


if __name__ == "__main__":
    unittest.main()
