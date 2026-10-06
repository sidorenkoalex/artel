"""Удержание `approve` на гейте мержа по зависимостям `merge_after` (AC-6..AC-8).

Группа: долгоживущий
Красен до реализации: колонки merge_after в таблице tasks нет и гейт SPEC значение не записывает — сценарии с зависимостями (AC-6, AC-7, AC-8 «все в done») краснеют на предпосылке «колонка merge_after не записана», а без неё гейт мержа зависимостей не читает и смержил бы задачу; сценарий AC-8 без поля зелёный с рождения.

Сценарий — сквозной `fsm.cmd_approve` задачи артели в настоящем
git-репозитории песочницы (`tests/sandbox.py::RealGitSandbox`) с настоящим
bare `origin`: ветка задачи несёт файл кода, SPEC.md и PLAN.md лежат в
ссылке документов (автокоммит шага `checkpoint.commit_step_artifacts`).
Значение `merge_after` задача получает штатным путём — `approve` гейта SPEC
со SPEC, несущим поле; затем задача переводится на `merge_gate`, а
зависимостям выставляются состояния сценария. Подменены только внешние
проверки, которых у песочницы нет: цвет CI ветки и main, Draft MR форжа и
полный прогон набора. Мьютекс merge-окна и вход в очередь наблюдаются
обёртками публичных `merge_lock.acquire`/`merge_queue.wait_for_window`
(вызов исполняется настоящий) и строками БД `store.merge_lock_row`/
`store.merge_queue_rows`. Число зависимостей, их состояния и порядок — от
зерна; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import random
import socket
import unittest
from unittest import mock

from orchestrator import (acceptance, catalog, checkpoint, ci, config, fsm,
                          github_adapter, idgen, merge_lock, merge_queue, store)
from tests.sandbox import (ARTEL_TEST_PROFILE, RealGitSandbox,
                           _alive_foreign_pid, capture)

TARGETS_YAML = """targets:
  {name}:
    forge: github
    url: http://localhost/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: feature.txt
budget_usd: 30
{field_line}---

# SPEC: фикстура гейта мержа

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.

## Не входит

Ничего.
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: фикстура

## Подход

Фикстура.

## Шаги

1. Фикстура.

## Покрытие требований

Фикстура.

## Влияние на систему

Нет.
"""

UNFINISHED_STATES = ("spec_gate", "tests_writing", "in_dev", "verifying",
                     "review", "acceptance", "merge_gate", "escalated")
FEATURE = "feature.txt"
MANDATE_MARKER = "Зависимости мержа:"


class MergeGateDependencySandbox(RealGitSandbox):
    """Задача артели с кодом на своей ветке, `origin` синхронный с `main`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        # Запись артели с профилем тестов (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7,
        # требование 4): без профиля гейт мержа задаче артели отказывает.
        config.TARGETS.write_text(TARGETS_YAML.format(
            name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH)
            + ARTEL_TEST_PROFILE, encoding="utf-8")
        self.origin = self.add_synced_origin()
        capture(catalog.cmd_init)
        self.conn = store.db()

        self.task = idgen.new_task_id()
        self.branch = f"task/{self.task.lower()}-x"
        self.feature_text = f"код задачи {self.seed}\n"
        self.checkout(self.branch, create=True)
        (self.root / FEATURE).write_text(self.feature_text, encoding="utf-8")
        self.git("add", FEATURE)
        self.git("commit", "-q", "-m", f"{self.task}: код задачи")
        self.checkout(config.MAIN_BRANCH)
        store.insert_task(self.conn, self.task, f"Задача {self.task}",
                          "spec_gate", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.object(acceptance, "run_full_suite",
                                  lambda root: (True, "1 passed (тест)")),
                mock.patch.object(ci, "branch_status",
                                  lambda branch, repo=None:
                                  (True, "зелёный (тест)")),
                mock.patch.object(ci, "main_line_status",
                                  lambda sha, repo=None: green_main),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(github_adapter, "undraft_mr",
                                  lambda conn, task_id, t: None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    # --- обвязка -------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def insert_dependency(self, state: str) -> str:
        dep = idgen.new_task_id()
        store.insert_task(self.conn, dep, f"Зависимость {dep}", state,
                          f"task/{dep.lower()}-dep", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        return dep

    def set_state(self, task_id: str, state: str) -> None:
        self.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        self.conn.commit()

    def state(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]

    def run_approve(self) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_approve(self.task)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def seed_dependencies(self, deps: list[str] | None) -> None:
        """SPEC (с `merge_after: deps`; `None` — без поля) и PLAN — в
        ссылку документов; `approve` гейта SPEC записывает значение в БД,
        после чего задача ставится на `merge_gate`."""
        field_line = "" if deps is None else f"merge_after: {', '.join(deps)}\n"
        docs = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / self.task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(
            SPEC_TEXT.format(task=self.task, field_line=field_line),
            encoding="utf-8")
        (docs / "PLAN.md").write_text(PLAN_TEXT.format(task=self.task),
                                      encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, self.conn, self.task, "developer")
        out = self.run_approve()
        self.assertNotEqual(self.state(self.task), "spec_gate", self.note(
            f"предпосылка: approve гейта SPEC не пропустил задачу:\n{out}"))
        if deps is not None:
            self.assertEqual(store.get_task(self.conn, self.task)["merge_after"]
                             is not None, True, self.note(
                                 "предпосылка: колонка merge_after не записана"))
        self.set_state(self.task, "merge_gate")

    def approve_merge_gate(self) -> tuple[str, mock.Mock, mock.Mock]:
        """`approve` на `merge_gate` под обёртками мьютекса и очереди:
        (вывод, обёртка acquire, обёртка wait_for_window)."""
        with mock.patch.object(merge_lock, "acquire",
                               wraps=merge_lock.acquire) as acquire, \
                mock.patch.object(merge_queue, "wait_for_window",
                                  wraps=merge_queue.wait_for_window) as wait:
            out = self.run_approve()
        return out, acquire, wait

    def journal(self) -> list[str]:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(self.conn, self.task)]

    def origin_has_feature(self) -> bool:
        files = self.git("--git-dir", str(self.origin), "ls-tree", "-r",
                         "--name-only", "refs/heads/" + config.MAIN_BRANCH)
        return FEATURE in files.splitlines()

    def assert_held_on_gate(self, out: str, acquire, wait) -> None:
        context = self.note(f"вывод approve:\n{out}\nжурнал: {self.journal()}")
        self.assertEqual(self.state(self.task), "merge_gate", context)
        acquire.assert_not_called()
        wait.assert_not_called()
        self.assertIsNone(store.merge_lock_row(self.conn), context)
        self.assertEqual([r for r in store.merge_queue_rows(self.conn)
                          if r["task_id"] == self.task], [], context)
        self.assertFalse(self.origin_has_feature(), self.note(
            f"merge выполнен вопреки отказу:\n{out}"))


class MergeGateUnfinishedDependencyTest(MergeGateDependencySandbox):

    def test_ac6_unfinished_dependency_refuses_before_merge_window(self):
        """Зависимость не в `done` и не в `killed` — отказ до мьютекса и очереди.

        Сценарий: одна-три зависимости; хотя бы одна в незавершённом живом
        состоянии (от зерна), остальные в `done`. `approve` на
        `merge_gate`: печать и журнал задачи называют каждую незавершённую
        зависимость с её текущим состоянием и подсказку `approve <id>`;
        задача на `merge_gate`, `merge_lock.acquire` и
        `merge_queue.wait_for_window` не вызывались, строки мьютекса и
        очереди нет, `origin/main` файла задачи не получил.

        Ловит мутацию: проверка зависимостей стоит после
        `merge_lock.acquire` (мьютекс берётся и отпускается) либо
        сравнивается с `acceptance` вместо `done` — обёртка `acquire`
        вызвана или задача смержена.
        """
        unfinished = [self.insert_dependency(self.rng.choice(UNFINISHED_STATES))
                      for _ in range(self.rng.randint(1, 2))]
        done = [self.insert_dependency("done")
                for _ in range(self.rng.randint(0, 1))]
        deps = unfinished + done
        self.rng.shuffle(deps)
        states = {d: self.state(d) for d in unfinished}
        self.seed_dependencies(deps)

        out, acquire, wait = self.approve_merge_gate()

        self.assert_held_on_gate(out, acquire, wait)
        journal = "\n".join(self.journal())
        for dep, dep_state in states.items():
            for where, text in (("печать", out), ("журнал", journal)):
                self.assertIn(dep, text, self.note(f"{where} не называет {dep}:\n{text}"))
                self.assertIn(dep_state, text, self.note(
                    f"{where} не называет состояние {dep_state} у {dep}:\n{text}"))
        self.assertIn(f"approve {self.task}", out, self.note(out))
        self.assertIn(f"approve {self.task}", journal, self.note(journal))


class MergeGateKilledDependencyTest(MergeGateDependencySandbox):

    def test_ac7_killed_dependency_names_mandate_channel(self):
        """Убитая зависимость — отдельный именованный отказ с каналом `answer`.

        Сценарий: одна убитая зависимость (на гейте SPEC была живой, убита
        после) и от нуля до двух других — в `done` или незавершённом
        состоянии (от зерна). `approve` на `merge_gate` возвращается сразу:
        сообщение называет убитую зависимость, команду `answer` и строку
        `Зависимости мержа:`; мьютекс и очередь не тронуты, задача на
        `merge_gate`, merge не выполнялся.

        Ловит мутацию: убитая зависимость обрабатывается общей веткой
        «не done» (подсказка повторить approve, без канала снятия) либо
        гейт ждёт её завершения циклом — в выводе нет `answer`/маркера
        мандата, или команда не возвращается до таймаута.
        """
        killed = self.insert_dependency(self.rng.choice(UNFINISHED_STATES))
        others = [self.insert_dependency(self.rng.choice(("done",) + UNFINISHED_STATES))
                  for _ in range(self.rng.randint(0, 2))]
        deps = [killed] + others
        self.rng.shuffle(deps)
        self.seed_dependencies(deps)
        self.set_state(killed, "killed")

        out, acquire, wait = self.approve_merge_gate()

        self.assert_held_on_gate(out, acquire, wait)
        self.assertIn(killed, out, self.note(out))
        self.assertIn("answer", out, self.note(out))
        self.assertIn(MANDATE_MARKER, out, self.note(out))


class MergeGateDoneDependenciesTest(MergeGateDependencySandbox):

    def test_ac8_done_dependencies_merge_through_busy_window(self):
        """Все зависимости в `done` — прежний путь: занятое окно ведёт в очередь, затем merge.

        Сценарий: одна-три зависимости в `done`; мьютекс merge-окна держит
        живой чужой процесс. `approve` на `merge_gate` вызывает
        `merge_lock.acquire`, получает отказ и встаёт в `merge_queue`
        (`wait_for_window`); чужой держатель отпускает окно при входе в
        очередь, задача берёт мьютекс, смержена (`done`), файл задачи — в
        `origin/main`.

        Ловит мутацию: зависимость в `done` считается незавершённой
        (сравнение с другим состоянием) либо непустое поле само по себе
        отказывает — задача остаётся на `merge_gate`, merge нет.
        """
        deps = [self.insert_dependency("in_dev") for _ in range(self.rng.randint(1, 3))]
        self.seed_dependencies(deps)
        for dep in deps:
            self.set_state(dep, "done")
        foreign_sid, foreign_pid = f"chuzhaya-{self.seed}", _alive_foreign_pid(self)
        store.set_merge_lock(self.conn, idgen.new_task_id(), foreign_sid,
                             foreign_pid, socket.gethostname(),
                             store.now())
        real_wait = merge_queue.wait_for_window

        def wait_after_release(conn, task_id, sid):
            store.release_merge_lock(conn, foreign_sid, foreign_pid)
            return real_wait(conn, task_id, sid)

        with mock.patch.object(merge_lock, "acquire",
                               wraps=merge_lock.acquire) as acquire, \
                mock.patch.object(merge_queue, "wait_for_window",
                                  side_effect=wait_after_release) as wait:
            out = self.run_approve()

        context = self.note(f"вывод approve:\n{out}\nжурнал: {self.journal()}")
        self.assertTrue(acquire.called, context)
        wait.assert_called_once()
        self.assertEqual(self.state(self.task), "done", context)
        self.assertTrue(self.origin_has_feature(), context)

    def test_ac8_without_field_merges_as_before(self):
        """Без поля `merge_after` — прежний путь: мьютекс, merge, `done`.

        Сценарий: SPEC без поля; в БД есть посторонние задачи в
        незавершённых состояниях (от зерна), окно свободно. `approve` на
        `merge_gate` берёт мьютекс (`merge_lock.acquire` вызван), в
        очередь не встаёт, задача в `done`, файл задачи в `origin/main`.

        Ловит мутацию: пустое поле читается как перечень всех задач БД
        (или незавершённые посторонние задачи блокируют гейт) — задача
        остаётся на `merge_gate`.
        """
        for _ in range(self.rng.randint(1, 2)):
            self.insert_dependency(self.rng.choice(UNFINISHED_STATES))
        self.seed_dependencies(None)

        out, acquire, wait = self.approve_merge_gate()

        context = self.note(f"вывод approve:\n{out}\nжурнал: {self.journal()}")
        self.assertTrue(acquire.called, context)
        wait.assert_not_called()
        self.assertEqual(self.state(self.task), "done", context)
        self.assertTrue(self.origin_has_feature(), context)


if __name__ == "__main__":
    unittest.main()
