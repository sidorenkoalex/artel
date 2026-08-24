"""Тесты guard на переходах FSM (см. tasks/T017/SPEC.md, требование 5).

Guard был автоматическим условием перехода только на словах: его звал CI
после пуша и роль по инструкции, а `advance` двигал задачу по одному лишь
полю `status`. Здесь проверяется, что проверку делает код перехода: артефакт
со сломанной структурой задачу не двигает, отказ называет файл и причину,
а состояние остаётся прежним.

Песочница как в остальных FSM-тестах: БД и артефакты во временном каталоге,
git и `claude` сюда не заходят.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, fsm, gitcmd, store  # noqa: E402

# Валидные артефакты; «портит» их фикстура — выбрасыванием секции.
SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: guard на переходах

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: guard на переходах

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 1
---

# REVIEW: guard на переходах

## Соответствие SPEC

## Замечания

## Вердикт
"""

# состояние -> (артефакт-условие перехода, заготовка, состояние после)
TRANSITIONS = {
    "spec_writing": ("SPEC.md", SPEC_MD, "spec_gate"),
    "in_dev": ("PLAN.md", PLAN_MD, "review"),
    "review": ("REVIEW.md", REVIEW_MD, "acceptance"),
}


class AdvanceGuardTest(unittest.TestCase):

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(gitcmd, "git", lambda *a: None)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Guard на переходах")
        self.tdir = config.TASKS / self.TASK

    # ------------------------------------------------------------ утилиты

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def state(self) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()[0]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write(self, name: str, text: str) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(text.format(task=self.TASK),
                                      encoding="utf-8")

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def prepare(self, state: str) -> tuple[str, str]:
        """Готовит задачу к переходу из `state`; возвращает файл и заготовку."""
        name, template, _ = TRANSITIONS[state]
        for other, (other_name, other_template, _) in TRANSITIONS.items():
            if other != state:
                self.write(other_name, other_template)
        self.set_state(state)
        return name, template

    # ----------------------------------------------------------- сценарии

    def test_every_transition_checks_its_own_artifact(self):
        """Требование 5: артефакт без обязательной секции перехода не даёт."""
        for state, (name, template, _) in TRANSITIONS.items():
            with self.subTest(состояние=state, артефакт=name):
                self.prepare(state)
                broken = template.split("\n## ")[0] + "\n"  # секции срезаны
                self.write(name, broken)

                out = self.capture(fsm.cmd_advance, self.TASK)

                self.assertEqual(self.state(), state, "задача не сдвинулась")
                self.assertIn(name, out, "отказ называет файл")
                self.assertIn("не проходит guard", out)
                self.assertIn("обязательная секция", out, "названа причина")

    def test_valid_artifacts_still_move_the_task(self):
        """Контроль: guard — условие перехода, а не запрет переходов."""
        for state, (name, template, after) in TRANSITIONS.items():
            with self.subTest(состояние=state):
                self.prepare(state)
                self.write(name, template)

                self.capture(fsm.cmd_advance, self.TASK)

                self.assertEqual(self.state(), after)

    def test_future_schema_version_stops_the_transition(self):
        """Расхождение форматов ловится проверкой, а не сбоем читателя."""
        name, template = self.prepare("in_dev")
        self.write(name, template.replace("schema_version: 1",
                                          "schema_version: 999"))

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")
        self.assertIn("schema_version 999", out)

    def test_unreadable_artifact_never_moves_the_task(self):
        """Нечитаемый артефакт — сообщение Оператору, а не исключение парсера.

        До guard такая задача не доходит: frontmatter не прочитан, значит
        и `status` не ready. Существенно, что ни один из двух путей не
        роняет `advance` трейсбеком и не двигает задачу.
        """
        name, _ = self.prepare("in_dev")
        (self.tdir / name).write_bytes(b"---\ntask: T\xff01\n---\n")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")
        self.assertIn(name, out)

    def test_the_refusal_is_in_the_journal(self):
        """Разбор потом идёт по журналу, а не по потерянному выводу."""
        name, template = self.prepare("in_dev")
        self.write(name, template.split("\n## ")[0] + "\n")

        self.capture(fsm.cmd_advance, self.TASK)

        details = self.journal_details("переход отклонён guard'ом")
        self.assertEqual(len(details), 1)
        self.assertIn("Влияние на систему", details[0])

    def test_broken_spec_does_not_apply_its_budget(self):
        """Отклонённый переход не имеет побочных эффектов: потолок не встал."""
        name, template = self.prepare("spec_writing")
        self.write(name, template.split("\n## ")[0].replace(
            "schema_version: 1", "schema_version: 1\nbudget_usd: 3") + "\n")

        self.capture(fsm.cmd_advance, self.TASK)

        row = store.db().execute("SELECT * FROM tasks WHERE id=?",
                                 (self.TASK,)).fetchone()
        self.assertEqual(self.state(), "spec_writing")
        self.assertIsNone(row["budget_source"], "бюджет из SPEC не применён")
        self.assertEqual(row["budget_usd"], config.DEFAULT_BUDGET_USD)

    def test_stale_verdict_is_still_stale_after_the_guard(self):
        """Guard добавлен к проверкам вердикта, а не вместо них."""
        name, template = self.prepare("review")
        self.write(name, template)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "acceptance")

        self.set_state("review")
        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review")
        self.assertIn("уже учтён", out)


if __name__ == "__main__":
    unittest.main()
