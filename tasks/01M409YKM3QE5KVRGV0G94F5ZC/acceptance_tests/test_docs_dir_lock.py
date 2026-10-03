"""AC-10 (часть): правка планки ролью в каталоге документов после лока
отклоняется локом `acceptance_tests/`.

Группа: разовый

Красен до реализации: каталога документов `.artel/projects/<проект>/tasks/<id>/` пульт не заводит и автокоммит шага его не читает (собирает `tasks/<id>/` рабочей копии кода) — правка планки ролью там не доходит до ссылки, лок сверять не с чем, переход `in_dev -> verifying` не получает отказа лока.

Группа «разовый»: сценарий зовёт закрытый узел сверки лока как контроль
до шага — долгоживущему файлу это запрещено. Сценарий — на настоящем git
(`_sandbox.LockedDocsSandbox`): лок записан штатным выходом из
`tests_writing`, шаг developer — штатный `runner.cmd_run`. Имена и тексты
случайные, зерно печатается и входит в текст провала.
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, store  # noqa: E402
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402

from _sandbox import LockedDocsSandbox, docs_dir  # noqa: E402

LOCK_ACTION = "переход отклонён: лок приёмочных тестов"


class RoleEditsPlankInDocsDirTest(LockedDocsSandbox):

    def test_ac10_plank_edit_in_docs_dir_refused_by_lock(self):
        """Правка планки ролью в каталоге документов после лока — отказ лока.

        Сценарий: задача после выхода из `tests_writing` (лок записан) в
        `in_dev`, в ссылке готовый PLAN. Контроль: до шага сверка лока не
        отказывает. Шаг developer: «роль» в каталоге документов случайно
        либо переписывает залоченный файл планки, либо добавляет новый
        `acceptance_tests/test_<x>.py`. После шага `advance` оставляет
        задачу в `in_dev`, журнал несёт «переход отклонён: лок приёмочных
        тестов».

        Ловит мутацию: автокоммит шага после выноса читает каталог
        документов только для SPEC/PLAN/REVIEW и не переносит
        `acceptance_tests/` (или читает рабочую копию кода) — правка
        планки не в ссылке, лок не срабатывает; сверка лока после выноса
        сравнивает дерево лока с выкладкой на диске, а не с головой
        ссылки."""
        conn = store.db()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            refused_before = acceptance_gates._acceptance_lock_refuses(
                conn, self.TASK, store.get_task(conn, self.TASK),
                artifact_branch.branch_name(self.TASK), True)
        self.assertFalse(refused_before, self.note(
            f"фикстура: лок отказывает до правки\n{buf.getvalue()}"))
        if self.rnd.random() < 0.5:
            rel, kind = self.plank_rel, "правка залоченного файла"
        else:
            rel, kind = f"acceptance_tests/test_{self.word()}.py", "новый файл"
        text = f"# правка роли после лока {self.word()}\n"
        print(f"вариант правки: {kind}")

        def role(cmd, kwargs):
            path = docs_dir(self.TASK) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        step = self.run_step(role)

        self.assertTrue(step["calls"], self.note(
            f"агент не запущен: {step['refusal']}\n{step['output']}"))
        out = self.advance()
        state = store.get_task(store.db(), self.TASK)["state"]
        self.assertEqual(state, "in_dev", self.note(
            f"{kind} {rel}: переход прошёл\n{out}"))
        self.assertIn(LOCK_ACTION, self.journal_text(), self.note(
            f"{kind} {rel}: нет отказа лока\n{out}"))


if __name__ == "__main__":
    unittest.main()
