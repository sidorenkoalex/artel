"""AC-5 (tasks/T048/SPEC.md): роль `analyst` стартует на задаче,
созданной новым флоу (`new ... --tz`), и читает `TZ.md` без ручных
действий Оператора.

`new` по новому флоу не кладёт `tasks/<id>/TZ.md` на диск главной копии
вовсе (AC-1) — он живёт только в ветке/worktree задачи. Если вход роли
(`orchestrator/runner.py step_role`) продолжает проверять файл на диске
main (требование 7, старое поведение), `run` откажет с «SPEC пишет
Оператор — TZ.md не заведён», хотя ТЗ реально есть. Тест прогоняет `run`
по-настоящему (с подменённым процессом агента) и проверяет, что роль
стартовала и увидела TZ.md там, где он реально лежит.
"""
import unittest
from pathlib import Path

from orchestrator import store  # noqa: E402

from _sandbox import AnalystRunTaskTest  # noqa: E402

TITLE = "Аналитик на новом флоу"
TZ_TEXT = "ТЗ нового флоу: аналитик обязан увидеть этот текст в worktree.\n"


class AnalystStartsFromBranchTest(AnalystRunTaskTest):

    def test_ac5_analyst_starts_and_reads_tz_without_operator_action(self):
        tz_path = self.write_tz_file(TZ_TEXT)
        self.cli_new(TITLE, tz_path)
        task_id = self.last_task_row()["id"]
        self.assertEqual(store.db().execute(
            "SELECT state FROM tasks WHERE id=?",
            (task_id,)).fetchone()["state"], "spec_writing")

        popen, out = self.run_agent(task_id)

        popen.assert_called_once()
        self.assertNotIn("SPEC пишет Оператор", out,
                         "run обязан стартовать analyst, а не отказывать "
                         "по отсутствию TZ.md на диске main")

        prompt_path = Path(popen.call_args.kwargs["stdin"].name)
        prompt = prompt_path.read_text(encoding="utf-8")
        self.assertIn("Роль: аналитик", prompt)
        self.assertIn("TZ.md", prompt)

        cwd = Path(popen.call_args.kwargs["cwd"])
        tz_in_place = cwd / "tasks" / task_id / "TZ.md"
        self.assertTrue(
            tz_in_place.is_file(),
            "рабочий каталог шага обязан реально содержать TZ.md — без "
            "ручного переноса Оператором")
        self.assertIn(TZ_TEXT.strip(),
                      tz_in_place.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
