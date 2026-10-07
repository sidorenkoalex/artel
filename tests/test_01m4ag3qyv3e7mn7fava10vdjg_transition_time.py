"""Связка перехода, прогона файла и записи времени в журнал задачи.

Группа: долгоживущий
Красен до реализации: рубеж ещё не записывает время отдельных файлов в журнал.

Песочница `tests.sandbox.GitignoreCommittedRealGitSandbox`: настоящий git,
артефактная ссылка, рабочая копия задачи, команда `advance`, БД и pytest.
Докстринги методов называют проверяемую связку.
"""

import contextlib
import hashlib
import io
import os
import random
import re
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (artifact_branch, checkpoint, config, fsm, idgen,
                          store, workspace)
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox


TARGETS = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

SPEC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/
budget_usd: 30
---

# SPEC: замер файла песочницы

## Контекст
Фикстура.

## Требования
1. Фикстура.

## Критерии приёмки
AC-1. Фикстурный критерий.

## Не входит
Ничего.
"""

PLAN = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: замер файла песочницы

## Подход
Фикстура.

## Шаги
1. Фикстура.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Нет.
"""

PLANK = '''"""Фикстура разовой группы.

Группа: разовый
Зелёный с рождения: проверяет только фикстурный исход.
"""
import unittest

class FixturePlank(unittest.TestCase):
    def test_fixture_plank(self):
        """Фикстурный прогон возвращает заданный исход.

        Ловит мутацию: изменение ожидаемого исхода красит фикстуру.
        """
        self.assertEqual(1 + 1, {expected})
'''

LONG_LIVED = '''"""Фикстура долгоживущего файла.

Группа: долгоживущий
"""
import unittest

class FixtureLongLived(unittest.TestCase):
    def test_fixture_file(self):
        """Фикстурный файл завершается зелёным.

        Ловит мутацию: изменение ожидаемого числа красит фикстуру.
        """
        self.assertEqual(2 + 2, 4)
'''


class TransitionTimeTest(GitignoreCommittedRealGitSandbox):
    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.add_synced_origin()
        config.TARGETS.write_text(TARGETS, encoding="utf-8")
        self.use_role_map()
        for patcher in (mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                        mock.patch("orchestrator.doctor.preflight_checks",
                                   lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)

    def context(self, text):
        return f"зерно: {self.seed}; {text}"

    def command(self, fn, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def prepare(self, *, green):
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-file-time"
        store.insert_task(store.db(), task_id, "Замер файла", "in_dev", branch,
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.context(error))
        rels = [f"tests/test_{task_id.lower()}_{name}.py"
                for name in ("first", "second")]
        for rel in rels:
            code_file = wt / rel
            code_file.parent.mkdir(parents=True, exist_ok=True)
            code_file.write_text(LONG_LIVED, encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", "файл замера")
        self.git("push", "-q", "origin", f"{branch}:{branch}")
        docs = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / task_id
        (docs / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC.format(task=task_id), encoding="utf-8")
        (docs / "PLAN.md").write_text(PLAN.format(task=task_id), encoding="utf-8")
        (docs / "acceptance_tests" / "test_plank.py").write_text(
            PLANK.format(expected=2 if green else 3), encoding="utf-8")
        manifest = "".join(
            f"{hashlib.sha256((wt / rel).read_bytes()).hexdigest()}  {rel}\n"
            for rel in rels)
        (docs / "acceptance_tests" / guard.LONG_LIVED_MANIFEST_NAME).write_text(
            manifest, encoding="utf-8")
        checkpoint.commit_step_artifacts(store.db(), task_id, "developer")
        lock_sha = artifact_branch.rev_sha(task_id, f"refs/artifacts/{task_id}")
        self.assertTrue(lock_sha, self.context("ссылка документов не создана"))
        store.update_task(store.db(), task_id, tests_locked_sha=lock_sha,
                          draft_mr_created=1)
        store.record_fixation(store.db(), task_id)
        return task_id, rels

    def transition(self, task_id):
        rows = store.task_steps(store.db(), task_id)
        before = rows[-1]["id"] if rows else 0
        out = self.command(fsm.cmd_advance, task_id)
        after = [dict(row) for row in store.task_steps(store.db(), task_id)
                 if row["id"] > before]
        state = store.get_task(store.db(), task_id)["state"]
        journal = "\n".join(f"{row['action']}: {row['detail']}" for row in after)
        return state, journal, out

    def test_ac4_transition_journals_each_file_time(self):
        """Связка команда–FSM–БД–git записывает путь и время файла на зелёном рубеже.

        Ловит мутацию: рубеж гоняет долгоживущий файл, но не журналирует его
        время — в новых строках журнала отсутствуют путь и число секунд.
        """
        task_id, rels = self.prepare(green=True)
        with mock.patch.object(config, "LONG_LIVED_FILE_WARN_SEC", 0, create=True):
            state, journal, out = self.transition(task_id)
        self.assertEqual(state, "verifying", self.context(out + journal))
        for rel in rels:
            with self.subTest(rel=rel):
                self.assertIn(rel, journal, self.context(journal))
                self.assertRegex(journal, re.escape(rel) + r"[^\n]*\d+(?:[.,]\d+)?",
                                 self.context(journal))
        self.assertRegex(journal.lower(), r"предупрежд|превыш|сверх",
                         self.context(journal))

    def test_ac7_warning_does_not_override_red_result(self):
        """Связка команда–FSM–БД–git оставляет красный рубеж отказом при превышении.

        Ловит мутацию: предупреждение о медленном файле ошибочно превращает
        красный прогон в переход `verifying`.
        """
        task_id, rels = self.prepare(green=False)
        with mock.patch.object(config, "LONG_LIVED_FILE_WARN_SEC", 0, create=True):
            state, journal, out = self.transition(task_id)
        self.assertEqual(state, "in_dev", self.context(out + journal))
        self.assertIn("приёмочные тесты", journal + out,
                      self.context(out + journal))
        self.assertIn(rels[0], journal, self.context(journal))
        self.assertRegex(journal.lower(), r"предупрежд|превыш|сверх",
                         self.context(journal))
