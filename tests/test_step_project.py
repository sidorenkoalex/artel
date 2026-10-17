"""Проект задачи на пути шага роли и проверка `project_skills` — свойства
сверх долгоживущего файла задачи 01M545EB0A9F191WTDSPCH36GA: пустая колонка
`target`, артель без чтения `targets.yaml`, вырожденные имена скилов,
прямой вызов `runner.run_agent_once` без проекта."""
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import brief, config, gitcmd, runner, store
from tests import test_01m545eb0a9f191wtdspch36ga_project_role_step as long_lived


class StepProjectTest(unittest.TestCase):

    def test_empty_target_refuses_without_artel_fallback(self):
        """Пустая колонка `target` — `StepProjectError` с id задачи.

        Ловит мутацию: пустой `target` откатывается на артель
        (`t["target"] or config.DEFAULT_TARGET`) — функция возвращает
        `("artel", None)` вместо отказа (ANSWER-1 п.3)."""
        for empty in ("", None):
            with self.subTest(target=empty):
                with self.assertRaises(runner.StepProjectError) as caught:
                    runner._step_project({"id": "01TASKX", "target": empty})
                self.assertIn("01TASKX", str(caught.exception))

    def test_artel_resolves_without_reading_targets_yaml(self):
        """Артель определяется без `targets.yaml`: файла нет — проект есть.

        Ловит мутацию: проект артели тоже берётся `targets.target` — при
        нечитаемом `targets.yaml` шаг артели отказывает (ANSWER-1 п.2)."""
        missing = Path("/nonexistent-artel-test") / "targets.yaml"
        with mock.patch.object(config, "TARGETS", missing):
            self.assertEqual(runner._step_project(
                {"id": "01TASKX", "target": config.DEFAULT_TARGET}),
                (config.DEFAULT_TARGET, None))


class ProjectSkillNameTest(unittest.TestCase):

    def test_degenerate_names_refused_even_if_main_has_file(self):
        """Пустое имя, `.` и `..` — отказ по имени, не по чтению main.

        Ловит мутацию: проверка имени ловит только разделитель `/` —
        `..` (файл `skills/...md`) или пустое имя (`skills/.md`) при
        отвечающей голове main проходят без отказа."""
        with mock.patch.object(gitcmd, "show", return_value=("# текст", "")):
            for name in ("", " ", ".", ".."):
                with self.subTest(name=name):
                    refusal = brief.project_skills_refusal(
                        "proekt", {"project_skills": ["good", name]})
                    self.assertIsNotNone(refusal)
                    self.assertIn("proekt", refusal)
                    self.assertIn("project_skills", refusal)
            self.assertIsNone(brief.project_skills_refusal(
                "proekt", {"project_skills": ["good"]}))


class RunAgentOnceProjectTest(long_lived.ProjectStepSandbox):

    def test_direct_call_without_project_refuses_undeclared(self):
        """`run_agent_once` без `project` для необъявленного проекта —
        исход `skipped`, агент не запущен, отказ в журнале.

        Ловит мутацию: прямой вызов без проекта берёт `store.task_target`
        (откат без сверки с `targets.yaml`) — агент уходит в запуск."""
        task = self.new_task(f"neob{long_lived.word(self.rnd)}")
        conn = store.db()
        store.update_task(conn, task, state="review", paused=0)
        spawn = mock.Mock()
        with mock.patch.object(runner, "spawn_agent", spawn):
            outcome, reason, _ = runner.run_agent_once(
                conn, task, "reviewer", "промпт шага", 1)
        self.assertEqual(outcome, "skipped", reason)
        spawn.assert_not_called()
        actions = [row["action"] for row in store.task_steps(conn, task)]
        self.assertIn(runner.STEP_PROJECT_REFUSAL_ACTION, actions)


if __name__ == "__main__":
    unittest.main()
