"""`acceptance_tests/` в рабочей копии кода — только на время прогона:
лежит во время прогона и убран после него при зелёном, красном исходе и
при сбое прогона.

Группа: разовый

Красен до реализации: прогон приёмочных тестов на переходе `in_dev -> verifying` (`advance_gates/acceptance._acceptance_run_refuses`) материализует планку в рабочую копию кода и после прогона её не убирает — `tasks/<id>/acceptance_tests/` остаётся в `.artel/worktrees/<id>` при любом исходе (AC-7 во второй половине, AC-8, AC-9); первая половина AC-7 (планка на месте во время прогона) держится уже сегодня.

Группа «разовый»: сценарий собран на лёгкой песочнице переходов
(`tests/sandbox.py::LightTransitionSandbox`) с подменой прогона pytest и
патчами её узлов (`gitcmd.commits_behind`, `workspace.on_task_branch`) —
для долгоживущего файла это лишние факты устройства. Постоянных сторожей
того же свойства в `tests/` пишет разработчик (SPEC, требование 7).

Сценарий (`_sandbox.AcceptanceRunSandbox`): задача артели в `in_dev`,
PLAN `ready`, в источнике документов — планка из случайного набора файлов
`test_*.py`; ветка не отстала от `main`, рабочая копия кода на ветке
задачи. Публичный `fsm.cmd_advance` доходит до прогона приёмочных тестов;
вызов pytest по каталогу `acceptance_tests` перехвачен шпионом
`subprocess.run`: он запоминает `cwd` прогона и файлы планки под ним и
отдаёт зелёный исход (код 0), красный (код 1) либо исключение. Прочие
вызовы `subprocess.run` идут как были. Зерно печатается и входит в текст
провала.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AcceptanceRunSandbox  # noqa: E402


def real(path) -> str:
    return os.path.realpath(str(path))


class PlankOnlyDuringRunTest(AcceptanceRunSandbox):

    def assert_run_saw_plank(self, outcome: dict) -> None:
        """Прогон был, его `cwd` — рабочая копия кода задачи, и под ним в
        `tasks/<id>/acceptance_tests/` лежала вся планка."""
        runs = outcome["runs"]
        self.assertTrue(runs, self.note(
            f"прогона приёмочных тестов не было: {outcome['output']}"))
        for run in runs:
            self.assertEqual(real(run["cwd"]), real(self.code_root), self.note(
                f"прогон не в рабочей копии кода: {run['cwd']}"))
            self.assertIsNotNone(run["files"], self.note(
                "во время прогона acceptance_tests/ в рабочей копии кода нет"))
            self.assertTrue(self.plank <= set(run["files"]), self.note(
                f"во время прогона не вся планка: {run['files']}, "
                f"ожидалось {sorted(self.plank)}"))

    def assert_plank_gone(self, outcome: dict, why: str) -> None:
        self.assertFalse(self.plank_dir().exists(), self.note(
            f"{why}: после прогона {self.plank_dir()} остался: "
            f"{sorted(p.name for p in self.plank_dir().rglob('*'))}"))

    def test_ac7_plank_present_during_green_run_and_gone_after(self):
        """Зелёный прогон: планка на месте во время прогона и убрана после.

        Сценарий: прогон pytest отдаёт код 0. Во время прогона `cwd` —
        рабочая копия кода задачи и под ней лежит вся планка
        (`tasks/<id>/acceptance_tests/` со всеми файлами источника);
        переход состоялся (`verifying`); после `advance` каталога
        `acceptance_tests/` в рабочей копии кода нет.

        Ловит мутацию: планка не выкладывается в рабочую копию кода (её
        `Path(__file__).parents[3]` не находит код) — во время прогона
        каталога нет; уборка после зелёного прогона забыта либо стоит до
        прогона/сводки и выкидывает файлы раньше времени."""
        outcome = self.advance_with_run("green")

        self.assertIsNone(outcome["crashed"], self.note(repr(outcome["crashed"])))
        self.assert_run_saw_plank(outcome)
        self.assertEqual(outcome["state"], "verifying", self.note(
            f"зелёный прогон не дал перехода:\n{outcome['output']}"))
        self.assert_plank_gone(outcome, "зелёный исход")

    def test_ac8_plank_gone_after_red_run(self):
        """Красный прогон: после него `acceptance_tests/` в рабочей копии кода нет.

        Сценарий: прогон pytest отдаёт код 1. Переход отклонён (задача
        осталась в `in_dev`), прогон видел планку в рабочей копии кода, а
        после `advance` каталога `acceptance_tests/` там нет.

        Ловит мутацию: уборка стоит только на пути зелёного исхода (после
        сводки приёмки) — ранний возврат отказа «приёмочные тесты
        красные» её минует, и планка остаётся."""
        outcome = self.advance_with_run("red")

        self.assertIsNone(outcome["crashed"], self.note(repr(outcome["crashed"])))
        self.assert_run_saw_plank(outcome)
        self.assertEqual(outcome["state"], "in_dev", self.note(
            f"красный прогон пропустил переход:\n{outcome['output']}"))
        self.assert_plank_gone(outcome, "красный исход")

    def test_ac9_plank_gone_after_crash_inside_run(self):
        """Сбой внутри прогона: после него `acceptance_tests/` в рабочей копии кода нет.

        Сценарий: вызов pytest поднимает исключение. Прогон начался при
        выложенной планке; исключение выходит из `advance` или
        перехватывается пультом (тест принимает оба исхода), задача не
        уходит в `verifying`, а каталога `acceptance_tests/` в рабочей
        копии кода после этого нет.

        Ловит мутацию: уборка — обычная строка после прогона, а не
        `finally`: исключение внутри прогона её пропускает, и планка
        остаётся в рабочей копии кода."""
        outcome = self.advance_with_run("crash")

        self.assert_run_saw_plank(outcome)
        self.assertNotEqual(outcome["state"], "verifying", self.note(
            "сбой прогона засчитан зелёным"))
        self.assert_plank_gone(outcome, "сбой прогона")


if __name__ == "__main__":
    unittest.main()
