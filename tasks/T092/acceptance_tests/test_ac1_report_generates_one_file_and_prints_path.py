"""AC-1 (tasks/T092/SPEC.md): запуск команды `report` без аргументов
задачи генерирует ровно один HTML-файл на диск и печатает в консоль
путь к сгенерированному файлу.

Интерфейс — `orchestrator.report.cmd_report()` без аргументов, см.
докстринг `_sandbox.py`.

Красен до реализации: `orchestrator/report.py` не существует
(`from orchestrator import report` в `_sandbox.ReportSandboxTest.setUp`
падает `ImportError`).
"""
import unittest

from _sandbox import ReportSandboxTest  # noqa: E402


class ReportGeneratesOneFileTest(ReportSandboxTest):

    def test_ac1_call_without_args_creates_exactly_one_html_file(self):
        self.mk_task("T001", "Задача-фикстура для report", "in_dev")

        out, new_files, before, after = self.run_report()

        self.assertEqual(
            len(new_files), 1,
            f"ожидался ровно один новый HTML-файл, получено: {new_files}")
        self.assertTrue(new_files[0].is_file())

    def test_ac1_prints_path_to_generated_file(self):
        self.mk_task("T001", "Задача-фикстура для report", "in_dev")

        out, new_files, before, after = self.run_report()

        path = new_files[0]
        self.assertTrue(
            path.name in out or str(path) in out
            or str(path.relative_to(self.root)) in out,
            f"вывод команды не содержит путь к файлу {path}:\n{out}")

    def test_ac1_no_task_id_argument_required(self):
        """«Без аргументов задачи» — вызов без id какой-либо конкретной
        задачи (сигнатура `cmd_report()` без обязательных параметров),
        не «без задач в БД вообще» (задача-фикстура всё равно есть)."""
        self.mk_task("T001", "Задача-фикстура для report", "in_dev")

        try:
            out = self.capture(self.report.cmd_report)
        except TypeError as exc:
            self.fail(f"cmd_report() обязан вызываться без аргументов: {exc}")


if __name__ == "__main__":
    unittest.main()
