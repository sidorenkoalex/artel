"""Приёмочные тесты T078 — отказ advance доносится до следующего запуска роли.

Источник — только tasks/T078/SPEC.md, раздел «Критерии приёмки»
(AC-1..AC-3; AC-4 — tasks/T078/acceptance_tests/test_manual_criteria.py).

Сценарий AC-1 — буквально инцидент T069 (SPEC, «Контекст»): состояние
`tests_writing`, роль `test_author`, реальный отказ `fsm.cmd_advance`
текстом «переход отклонён: трассируемость AC» (orchestrator/fsm.py:770-773).
Песочница и фикстуры SPEC/acceptance_tests — тот же приём, что
`tests/test_acceptance_tests_flow.py::TraceabilityTest`; захват собранного
промпта шага — тот же приём, что `tests/test_agent_prompt.py`
(`runner.spawn_agent` подменён, промпт читается из файла на его `stdin`).

Красен до реализации: `test_ac1_refusal_reason_text_appears_in_the_next_step_prompt`
— сегодня ни `orchestrator/runner.py` (ветки `role == "test_author"/
"developer"` в `_cmd_run`), ни `orchestrator/brief.py` не читают
`store.task_steps` вовсе: ни один компонент брифа не видит записи журнала
«переход отклонён…», значит текст причины прошлого отказа не может попасть
в промпт следующего запуска роли ни при каких условиях (проверено прогоном
перед написанием этого файла — тест падает именно на отсутствии текста
отказа в промпте, не на ошибке стенда).

Зелёный с рождения: `test_ac2_no_refusal_history_means_no_new_refusal_block`
и оба метода `AC3IsolationTest` — сегодня, до реализации T078, промпт шага
СТРУКТУРНО не может нести текст ни одной записи «переход отклонён…» (см.
абзац выше), поэтому и «на чистом пути блока нет» (AC-2), и «отказ чужого
состояния/чужой задачи не течёт» (AC-3) выполняются уже сейчас — но по
не той причине, что будет после реализации (не потому, что реализация
СКОУПИТ выборку по состоянию и задаче, а потому что выборки нет вовсе).
После появления фильтрации по состоянию/задаче (SPEC, требования 1, 4)
эти тесты становятся настоящим регрессионным стражем: ловят как раз
случай «фильтр по состоянию/задаче сломан, отказ течёт отовсюду».
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, fsm, gitcmd, runner, store  # noqa: E402
from tests.sandbox import (FakeProc, capture, fake_git,  # noqa: E402
                           seed_developer_brief_fixtures)

REPO_ROOT = Path(__file__).resolve().parents[3]

SPEC_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: песочница T078

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий, проверяемый тестом.
AC-2. Второй критерий, проверяемый тестом или пометкой.

## Не входит
"""

# Покрыт только AC-1 — трассируемость AC-2 отказывает реально (никакого
# журналирования вручную, текст отказа получаем из настоящего guard'а).
AC_TEST_MISSING_AC2 = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
"""

# Оба критерия покрыты (тест + manual-пометка) — маркер красноты обязателен
# для выхода из tests_writing (SPEC T064), иначе успешный переход отказал
# бы по другой причине.
AC_TEST_BOTH_COVERED = '''"""Красен до реализации: фикстура песочницы покрывает оба критерия SPEC —
тест и manual-пометка, до появления реализации кода задачи."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)


# AC-2: manual — Оператор проверяет глазами на приёмке
'''


class T078Sandbox(unittest.TestCase):
    """Полная песочница шага (по образцу tests/test_agent_prompt.py
    PromptChannelTest): позволяет и реальный `fsm.cmd_advance`, и реальный
    `runner.cmd_run` с захватом собранного промпта."""

    TASK = "T001"
    OTHER_TASK = "T002"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(REPO_ROOT / "templates", root / "templates")
        shutil.copytree(REPO_ROOT / "skills", root / "skills")
        seed_developer_brief_fixtures(root)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

        self.capture(catalog.cmd_init)

    # ------------------------------------------------------------ утилиты

    capture = staticmethod(capture)

    def new_task(self, title: str) -> None:
        self.capture(catalog.cmd_new, title)

    def tdir(self, task_id: str) -> Path:
        return config.TASKS / task_id

    def write_spec(self, task_id: str) -> None:
        d = self.tdir(task_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "SPEC.md").write_text(SPEC_AC.format(task=task_id),
                                   encoding="utf-8")

    def write_acceptance_tests(self, task_id: str, content: str,
                               name: str = "test_ac.py") -> None:
        d = self.tdir(task_id) / "acceptance_tests"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(content, encoding="utf-8")

    def set_state(self, task_id: str, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        conn.commit()

    def state_of(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["state"]

    def journal_details(self, task_id: str, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (task_id, action))]

    def run_role(self, task_id: str, state: str) -> str:
        """Реальный `cmd_run` в указанном состоянии; возвращает собранный
        промпт шага, прочитанный с того же файла, что получает `spawn_agent`
        на stdin (tests/test_agent_prompt.py, `prompt_path_of`)."""
        self.set_state(task_id, state)
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            self.capture(runner.cmd_run, task_id)
        return Path(popen.call_args.kwargs["stdin"].name).read_text(
            encoding="utf-8")


# --------------------------------------------------------------------------
# AC-1: сценарий T069 — отказ доносится до следующего запуска роли того же
# состояния.

class AC1RefusalReachesNextRunTest(T078Sandbox):

    def test_ac1_refusal_reason_text_appears_in_the_next_step_prompt(self):
        self.new_task("T078 AC-1 сценарий T069")
        self.write_spec(self.TASK)
        self.set_state(self.TASK, "tests_writing")
        self.write_acceptance_tests(self.TASK, AC_TEST_MISSING_AC2)

        # Реальный отказ advance — тот же путь, что инцидент T069
        # (orchestrator/fsm.py:770-773).
        self.capture(fsm.cmd_advance, self.TASK)

        details = self.journal_details(
            self.TASK, "переход отклонён: трассируемость AC")
        self.assertEqual(len(details), 1,
                         "сценарий должен дать ровно один журналируемый "
                         "отказ advance")
        refusal_text = details[0]
        self.assertIn("AC-2", refusal_text, "стенд не воспроизвёл ожидаемый "
                      "отказ — причина не называет недостающий AC-2")

        prompt = self.run_role(self.TASK, "tests_writing")

        self.assertIn(
            refusal_text, prompt,
            "промпт следующего запуска роли того же состояния не несёт "
            "текст журнальной записи «переход отклонён: трассируемость "
            "AC» — ровно инцидент T069 (SPEC T078, AC-1)")


# --------------------------------------------------------------------------
# AC-2: состояние без предыстории отказов — бриф не меняется.

class AC2CleanPathTest(T078Sandbox):

    def test_ac2_no_refusal_history_means_no_new_refusal_block(self):
        self.new_task("T078 AC-2 чистый путь")
        self.write_spec(self.TASK)

        prompt = self.run_role(self.TASK, "tests_writing")

        self.assertNotIn(
            "переход отклонён", prompt,
            "по текущему состоянию задачи отказов advance не было, но "
            "промпт всё равно несёт текст журнальной записи «переход "
            "отклонён…» (SPEC T078, AC-2 — ноль регрессии для чистого "
            "пути)")


# --------------------------------------------------------------------------
# AC-3: отказ ЧУЖОГО состояния той же задачи и отказ ДРУГОЙ задачи не
# просачиваются в бриф роли, запускаемой в конкретном состоянии.

class AC3IsolationTest(T078Sandbox):

    def test_ac3_refusal_of_a_different_state_of_the_same_task_does_not_leak(self):
        self.new_task("T078 AC-3 состояния")
        self.write_spec(self.TASK)
        self.set_state(self.TASK, "tests_writing")
        self.write_acceptance_tests(self.TASK, AC_TEST_MISSING_AC2)

        # Реальный отказ в tests_writing.
        self.capture(fsm.cmd_advance, self.TASK)
        details = self.journal_details(
            self.TASK, "переход отклонён: трассируемость AC")
        self.assertEqual(len(details), 1)
        tests_writing_refusal = details[0]

        # Реальный переход дальше — задача покидает tests_writing.
        self.write_acceptance_tests(self.TASK, AC_TEST_BOTH_COVERED)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(
            self.state_of(self.TASK), "in_dev",
            "сценарий предполагает, что задача реально ушла из "
            "tests_writing — иначе изоляция между состояниями непроверяема")

        prompt = self.run_role(self.TASK, "in_dev")

        self.assertNotIn(
            tests_writing_refusal, prompt,
            "отказ advance состояния tests_writing просочился в бриф "
            "роли, запускаемой в in_dev той же задачи (SPEC T078, AC-3)")

    def test_ac3_refusal_of_another_task_does_not_leak(self):
        self.new_task("T078 AC-3 задача раз")   # T001
        self.new_task("T078 AC-3 задача два")   # T002
        self.write_spec(self.TASK)

        other_task_detail = "T002-only-маркер-стенда-27fbac"
        store.journal(store.db(), self.OTHER_TASK, "fsm",
                      "переход отклонён: рабочая копия артефактов грязная",
                      other_task_detail)

        prompt = self.run_role(self.TASK, "in_dev")

        self.assertNotIn(
            other_task_detail, prompt,
            "отказ advance ДРУГОЙ задачи просочился в бриф роли, "
            "запускаемой в этой задаче (SPEC T078, AC-3)")


if __name__ == "__main__":
    unittest.main()
