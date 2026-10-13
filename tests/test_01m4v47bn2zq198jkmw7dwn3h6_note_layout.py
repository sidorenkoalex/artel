"""Выкладка записок проверяющим ролям через настоящий путь подготовки.

Группа: долгоживущий
Красен до реализации: запуск не передаёт роль в подготовку, а выкладка копирует чужие записки из ссылки документов.
"""

import unittest
from pathlib import Path
from unittest import mock

from orchestrator import checkpoint, config, runner, store, workspace
from tests.sandbox import RealGitSandbox


class NoteLayoutTest(RealGitSandbox):
    TASK = "01" + "0" * 24
    ROLES = ("analyst", "spec_auditor", "test_author", "developer", "reviewer")

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        self.conn = store.db()
        self.branch = "task/fixture-notes"
        store.insert_task(self.conn, self.TASK, "Записки", "review",
                          self.branch, config.DEFAULT_TARGET, 25.0)
        self.wt, error = workspace.ensure(self.TASK, self.branch)
        self.assertIsNone(error)
        self.docs = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / self.TASK
        self.docs.mkdir(parents=True)
        for name, text in (
                ("TZ.md", "тз\n"), ("SPEC.md", "спецификация\n"),
                ("ANSWER-1.md", "ответ\n"),
                ("SPEC-AUDIT.md", "аудит\n"), ("REVIEW.md", "ревью\n")):
            (self.docs / name).write_text(text)
        nested = self.docs / "acceptance_tests" / "NOTE-analyst.md"
        nested.parent.mkdir()
        nested.write_text("вложенный файл\n")
        for role in self.ROLES:
            self.docs.mkdir(parents=True, exist_ok=True)
            (self.docs / f"NOTE-{role}.md").write_text(f"записка {role}\n")
            checkpoint.commit_step_artifacts(self.conn, self.TASK, role)

    def test_ac1_spec_auditor_launch_exposes_only_own_note(self):
        """Запуск аудитора до создания процесса выкладывает только его записку.

        Ловит мутацию: запуск перестал передавать роль в подготовку — наблюдатель
        процесса видит на диске чужую записку.
        """
        role = "spec_auditor"
        seen = []

        def observe(_cmd, **_kwargs):
            seen.append({name: (self.docs / f"NOTE-{name}.md").exists()
                         for name in self.ROLES})
            raise FileNotFoundError("агент подменён")

        with mock.patch.object(runner, "spawn_agent", side_effect=observe), \
                mock.patch.object(runner, "role_env", return_value={}):
            runner.run_agent_once(self.conn, self.TASK, role, "промпт", 1)
        self.assertEqual(seen, [{name: name == role for name in self.ROLES}])

    def test_ac2_reviewer_launch_exposes_only_own_note(self):
        """Запуск ревьювера до создания процесса выкладывает только его записку.

        Ловит мутацию: запуск перестал передавать роль в подготовку — наблюдатель
        процесса видит на диске чужую записку.
        """
        role = "reviewer"
        seen = []

        def observe(_cmd, **_kwargs):
            seen.append({name: (self.docs / f"NOTE-{name}.md").exists()
                         for name in self.ROLES})
            raise FileNotFoundError("агент подменён")

        with mock.patch.object(runner, "spawn_agent", side_effect=observe), \
                mock.patch.object(runner, "role_env", return_value={}):
            runner.run_agent_once(self.conn, self.TASK, role, "промпт", 1)
        self.assertEqual(seen, [{name: name == role for name in self.ROLES}])

    def test_ac3_normal_and_fallback_layout_clean_stale_top_level_notes(self):
        """Обычная и запасная выкладки очищают осевшие записки первого уровня.

        Ловит мутацию: запасная ветка после ошибки чтения оставляет старые
        записки — в каталоге проверяющей роли остаётся чужой файл.
        """
        for role in ("spec_auditor", "reviewer"):
            with self.subTest(role=role):
                for name in self.ROLES:
                    (self.docs / f"NOTE-{name}.md").parent.mkdir(parents=True,
                                                                    exist_ok=True)
                    (self.docs / f"NOTE-{name}.md").write_text("осело\n")
                runner.role_cwd(self.conn, self.TASK, config.DEFAULT_TARGET,
                                role=role)
                self.assertEqual(
                    {name for name in self.ROLES
                     if (self.docs / f"NOTE-{name}.md").exists()}, {role})
                nested = self.docs / "acceptance_tests" / "NOTE-analyst.md"
                self.assertEqual(nested.read_text(), "вложенный файл\n")

                for name in self.ROLES:
                    (self.docs / f"NOTE-{name}.md").write_text("осело\n")
                legacy = self.wt / "tasks" / self.TASK / "TZ.md"
                legacy.parent.mkdir(parents=True, exist_ok=True)
                legacy.write_text("тз из рабочей копии\n")
                with mock.patch("orchestrator.artifact_branch.materialize_task_dir",
                                return_value=""):
                    runner.role_cwd(self.conn, self.TASK,
                                    config.DEFAULT_TARGET, role=role)
                self.assertEqual(
                    {name for name in self.ROLES
                     if (self.docs / f"NOTE-{name}.md").exists()}, {role})
                self.assertEqual(nested.read_text(), "вложенный файл\n")

    def test_ac4_unconfirmed_layout_skips_launch_and_journals_refusal(self):
        """Ошибки чтения и удаления завершают подготовку до процесса роли.

        Ловит мутацию: ошибка удаления чужой записки проглатывается —
        вызывается запуск процесса при небезопасном составе выкладки.
        """
        original_unlink = Path.unlink

        def reject_foreign_note(path, *args, **kwargs):
            if path == self.docs / "NOTE-analyst.md":
                raise OSError("сбой удаления")
            return original_unlink(path, *args, **kwargs)

        for role in ("spec_auditor", "reviewer"):
            with self.subTest(role=role):
                with mock.patch("orchestrator.artifact_branch.materialize_task_dir",
                                side_effect=OSError("сбой проверки")), \
                        mock.patch.object(runner, "spawn_agent") as spawn, \
                        mock.patch.object(runner, "role_env", return_value={}):
                    outcome, _reason, _class = runner.run_agent_once(
                        self.conn, self.TASK, role, "промпт", 1)
                self.assertEqual(outcome, "skipped")
                spawn.assert_not_called()
                skipped_before = sum(
                    row["action"] == "agent run SKIPPED"
                    for row in store.task_steps(self.conn, self.TASK))
                self.assertGreater(skipped_before, 0)
                with mock.patch.object(Path, "unlink", new=reject_foreign_note), \
                        mock.patch.object(runner, "spawn_agent") as spawn, \
                        mock.patch.object(runner, "role_env", return_value={}):
                    outcome, _reason, _class = runner.run_agent_once(
                        self.conn, self.TASK, role, "промпт", 1)
                self.assertEqual(outcome, "skipped")
                spawn.assert_not_called()
                skipped_after = sum(
                    row["action"] == "agent run SKIPPED"
                    for row in store.task_steps(self.conn, self.TASK))
                self.assertEqual(skipped_after, skipped_before + 1)

    def test_ac5_source_notes_survive_filtered_layout_and_autocommit(self):
        """Фильтрация диска не удаляет записки ссылки и обычные документы.

        Ловит мутацию: автокоммит трактует скрытую чужую записку как удалённую
        ролью — её путь исчезает из ссылки документов.
        """
        for role in ("spec_auditor", "reviewer"):
            with self.subTest(role=role):
                runner.role_cwd(self.conn, self.TASK, config.DEFAULT_TARGET,
                                role=role)
                for name in ("TZ.md", "SPEC.md", "ANSWER-1.md",
                             "SPEC-AUDIT.md", "REVIEW.md"):
                    self.assertTrue((self.docs / name).exists(), name)
                checkpoint.commit_step_artifacts(self.conn, self.TASK, role)
                runner.role_cwd(self.conn, self.TASK, config.DEFAULT_TARGET)
                for name in self.ROLES:
                    self.assertEqual(
                        (self.docs / f"NOTE-{name}.md").read_text(),
                        f"записка {name}\n")

        for role in (None, "developer", "analyst", "test_author"):
            with self.subTest(role=role):
                if role is None:
                    runner.role_cwd(self.conn, self.TASK, config.DEFAULT_TARGET)
                else:
                    runner.role_cwd(self.conn, self.TASK,
                                    config.DEFAULT_TARGET, role=role)
                self.assertTrue(all((self.docs / f"NOTE-{name}.md").exists()
                                    for name in self.ROLES))


if __name__ == "__main__":
    unittest.main()
