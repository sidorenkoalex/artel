"""AC-8, AC-9 — 01M3PKSWPETC49WFTFZ69GH3F2: сбой и зависание процесса
клона — красный прогон с диагностикой, пульт не падает, клон убран.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-8. Процесс клона завершается ненулевым кодом, не пишет результат или
пишет неразборчивый: прогон красный, вывод процесса клона сохранён в
каталог диагностики прогона, пульт не падает, клон и origin-заглушка
убраны.

AC-9. Процесс клона не завершается за предельное время: он снимается,
прогон красный с диагностикой (вывод процесса сохранён), клон и
origin-заглушка убраны.

Сбой изображается посредником запуска (`_clone_drive.py`): он печатает
случайную метку в stdout и stderr процесса клона и дальше, по режиму,
исполняет настоящий процесс клона и выходит кодом 3 (`fail`), удаляет его
файл результата (`drop`), портит его (`garbage`) — либо не исполняет его
вовсе и спит 600 с (`hang`). «Вывод сохранён» — метка находится в файлах
под `<корень пульта>/.artel/canary/` (каталог диагностики прогона
`_diagnostics_dir`: id задачи при сбое может быть неизвестен, поэтому
ищется по всему дереву прогонов). «Прогон красный» — ни одной строки
`canary_runs` с вердиктом `green`. «Пульт не падает» — `cmd_canary` не
бросает исключения (именованный `SystemExit` падением не считается).

Предельное время: имя константы SPEC оставляет PLAN, поэтому посредник
сжимает любой таймаут, с которым пульт ждёт процесс клона
(`communicate`/`wait`), до нескольких секунд. Пульт, ждущий процесс вовсе
без таймаута, не завершится за таймаут pytest — тест краснеет.

Красен до реализации: процесса клона нет — ведение в процессе пульта
упирается в растяжку песочницы, исключение растяжки роняет `cmd_canary`,
метки в диагностике нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _clone_drive  # noqa: E402


class _CloneFailureTest(_clone_drive.CloneDriveSandbox):

    MODE = None

    def setUp(self):
        super().setUp()
        self.target = self.commit_code(_clone_drive.SCENARIO_GREEN,
                                       self.new_marker("метка"))
        self.diag_mark = self.new_marker("вывод-клона")
        self.run_canary(self.target, mode=self.MODE, marker=self.diag_mark)

    def assert_red_run_with_saved_output(self):
        self.assert_no_crash()
        self.assertEqual(
            len(self.launches), 1,
            f"процесс клона запускался {len(self.launches)} раз\n{self.output}")
        green = [r["task_id"] for r in self.canary_rows() if r["verdict"] == "green"]
        self.assertEqual(green, [], f"сбой процесса клона записан зелёным "
                                    f"(зерно {self.seed})\n{self.output}")
        self.assertIn(
            self.diag_mark, self.diagnostics_text(),
            f"вывод процесса клона не сохранён в каталог диагностики прогона "
            f"(зерно {self.seed})\n{self.output}")
        self.assert_clone_dirs_removed()


class NonZeroExitTest(_CloneFailureTest):
    MODE = "fail"

    def test_ac8_nonzero_exit_is_a_red_run_with_saved_output(self):
        """Процесс клона отработал и записал результат, но вышел кодом 3:
        прогон не зелёный, вывод процесса сохранён в диагностике, пульт не
        упал, клон и origin-заглушка убраны.

        Ловит мутацию: пульт не смотрит на код выхода и принимает
        записанный результат как штатный (строка `canary_runs` с вердиктом
        `green`) либо не сохраняет вывод процесса клона (метки нет под
        `.artel/canary/`).
        """
        self.assert_red_run_with_saved_output()


class MissingResultTest(_CloneFailureTest):
    MODE = "drop"

    def test_ac8_missing_result_is_a_red_run_with_saved_output(self):
        """Процесс клона вышел кодом 0, но файла результата нет: прогон не
        зелёный, вывод процесса сохранён, пульт не упал, клон убран.

        Ловит мутацию: чтение отсутствующего файла результата не
        перехвачено — `FileNotFoundError` роняет `cmd_canary` (и `finally`
        клона — единственная уборка, но вывод процесса теряется).
        """
        self.assert_red_run_with_saved_output()


class GarbageResultTest(_CloneFailureTest):
    MODE = "garbage"

    def test_ac8_unparsable_result_is_a_red_run_with_saved_output(self):
        """Процесс клона вышел кодом 0, но файл результата — не JSON: прогон
        не зелёный, вывод процесса сохранён, пульт не упал, клон убран.

        Ловит мутацию: `json.JSONDecodeError` разбора результата не
        перехвачен и роняет `cmd_canary` — прогон не записан красным, вывод
        процесса клона не сохранён.
        """
        self.assert_red_run_with_saved_output()


class HangingProcessTest(_CloneFailureTest):
    MODE = "hang"

    def test_ac9_hanging_process_is_killed_and_the_run_is_red(self):
        """Процесс клона печатает метку и не завершается: пульт снимает его по
        истечении предельного времени (процесс мёртв к концу прогона),
        прогон не зелёный, вывод процесса сохранён, пульт не упал, клон и
        origin-заглушка убраны.

        Ловит мутацию: пульт ждёт процесс клона без предельного времени
        (прогон висит до таймаута pytest) либо по таймауту бросает
        `subprocess.TimeoutExpired` наружу (пульт падает, вывод процесса не
        сохранён), либо не снимает процесс (он жив после прогона).
        """
        self.assert_red_run_with_saved_output()
        self.assertTrue(self.drive_procs)
        for proc in self.drive_procs:
            self.assertIsNotNone(proc.poll(), f"процесс клона {proc.pid} не снят")


if __name__ == "__main__":
    unittest.main()
