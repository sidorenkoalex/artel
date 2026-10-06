"""Сквозной поток задачи внешнего проекта: гейты `in_dev`, подтяжка, гейт мержа.

Группа: долгоживущий
Красен до реализации: у задачи внешнего проекта после отказа git на коммите пульта переход не отказывает по незакоммиченному результату шага, гейт «замечания ревью не отработаны» не проверяется, на входе в `merge_gate` не считается `diff_bytes`, а подтяжка main берёт базу проекта собственным разрешением `fsm.py` из `targets.yaml`, мимо `repo_context.resolve`.

SPEC задачи: AC-4, AC-7, AC-10, AC-11 (строки 12-13,
17, 23, 26 таблицы требования 1) и сквозные AC-15/AC-16 (требования 4-5).
Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): пульт и клон
артели — репозиторий песочницы с синхронным `origin`; внешний проект —
свой клон с голым `origin` в роли форджа (`make_project_repo`), запись
`targets.yaml` с `no_paths` из случайных путей и — у одной песочницы —
профилем тестов. На `main` проекта до заведения задач лежит тест
`tests/test_<имя>.py`. Задача заводится строкой БД, рабочей копией
`workspace.ensure`, коммитом кода и документами в ссылке документов
(`checkpoint.commit_step_artifacts`); переход — `fsm.cmd_advance`, гейт
мержа — `fsm.cmd_approve`. Обращения к форджу (Draft MR, CI ветки и main)
и полный прогон тестов подменены публичными заглушками.

Имена проектов, путей, тестов и значения порождаются модулем `random` при
каждом запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import dataclasses
import io
import os
import random
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, catalog, checkpoint, ci, config, fsm,
                          github_adapter, idgen, project_profile,
                          repo_context, review, store, workspace)
from orchestrator.advance_gates import test_integrity
from tests.sandbox import RealGitSandbox, capture, make_project_repo

ZONES_ACTION = "переход отклонён: гейт зон"
PROTECTED_ACTION = "переход отклонён: защищённый путь"
MUTATION_ACTION = "переход отклонён: гейт заявки мутации"
REWORK_ACTION = "переход отклонён: замечания ревью не отработаны"
UNCOMMITTED_ACTION = "переход отклонён: результат шага не закоммичен"
PROTECTED_MERGE_TEXT = "защищённый путь {rel} — правит только Оператор коммитом в main"

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
"""

PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура сквозного потока внешнего проекта

## Подход
Фикстура сценария.

## Шаги
1. Правка.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Нет.
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: фикстура сквозного потока внешнего проекта

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

REVIEW_TEXT = """---
task: {task}
type: review
author_role: reviewer
status: changes_requested
iteration: {iteration}
schema_version: 1
---

# REVIEW: фикстура

## Замечания
1. Почини {word}.
"""


class ExternalFlowSandbox(RealGitSandbox):
    """Пульт с клоном артели и внешним проектом с голым `origin`."""

    WITH_PROFILE = False

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        green_main = ci.MainLineStatus(ci.MAIN_GREEN, "", [], [], "",
                                       "зелёный (тест)")
        for patcher in (
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch.object(github_adapter, "ensure_draft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(github_adapter, "undraft_mr",
                                  lambda conn, task_id, t: None),
                mock.patch.object(acceptance, "run_full_suite",
                                  lambda root: (True, "1 passed (тест)")),
                mock.patch.object(ci, "branch_status",
                                  lambda branch, repo=None: (True, "зелёный (тест)")),
                mock.patch.object(ci, "main_line_status",
                                  lambda sha, repo=None: green_main)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.artel_origin = self.add_synced_origin()
        self.ext = "proekt" + self.word(5)
        self.ext_clone = make_project_repo(self.ext)
        self.ext_origin = config.PROJECTS / self.ext / "origin.git"
        self.conn = store.db()
        self.ext_no_paths = []
        while len(self.ext_no_paths) < self.rng.randint(2, 3):
            name = f"zn{self.word()}/"
            if name not in self.ext_no_paths:
                self.ext_no_paths.append(name)
        self.write_targets()
        capture(catalog.cmd_init)
        # Существующий тест проекта — на main и в его origin до задач.
        self.existing_test = f"tests/test_{self.word()}.py"
        self.commit_to_ext_main({self.existing_test: (
            f"def test_{self.word()}():\n    assert {self.seed} == {self.seed}\n")})

    # ------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choices(string.ascii_lowercase, k=size))

    def explain(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def write_targets(self, ext_entry: bool = True) -> None:
        text = "targets:\n" + TARGET_ENTRY.format(
            name=config.DEFAULT_TARGET, url="http://localhost/artel",
            base=config.MAIN_BRANCH,
            no_paths=", ".join(config.PROTECTED_PATHS)) + PROFILE
        if ext_entry:
            text += TARGET_ENTRY.format(
                name=self.ext, url=f"file:///nonexistent/{self.ext}",
                base=config.MAIN_BRANCH, no_paths=", ".join(self.ext_no_paths))
            if self.WITH_PROFILE:
                text += PROFILE
        config.TARGETS.write_text(text, encoding="utf-8")

    def commit_to_ext_main(self, files: dict) -> str:
        for rel, text in files.items():
            path = self.ext_clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(self.ext_clone), "add", "-A")
        self.git("-C", str(self.ext_clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(self.ext_clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        return self.git("-C", str(self.ext_clone), "rev-parse", "HEAD").strip()

    def code_file(self) -> tuple:
        zone = f"pk{self.word()}/"
        return zone, f"{zone}{self.word()}.py"

    def protected_path(self) -> str:
        return f"{self.rng.choice(self.ext_no_paths)}{self.word()}.cfg"

    # ------------------------------------------------------------ задача

    def new_task(self, state: str, zones, code: dict, remove=(),
                 commit_env: dict = None) -> str:
        """Задача проекта в `state`: зоны, коммит кода (`code` — запись,
        `remove` — удаление), PLAN/SPEC в ссылке документов."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-flow"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          state, branch, self.ext, config.DEFAULT_BUDGET_USD)
        if zones:
            store.update_task(self.conn, task_id, zones=", ".join(zones))
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.explain(f"рабочая копия: {error}"))
        self.commit_code(task_id, code, remove, commit_env)
        docs = config.PROJECTS / self.ext / "tasks" / task_id
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "PLAN.md").write_text(PLAN_TEXT.format(task=task_id),
                                      encoding="utf-8")
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=task_id),
                                      encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, self.conn, task_id, "developer")
        return task_id

    def worktree(self, task_id: str) -> Path:
        return Path(workspace.path(task_id))

    def commit_code(self, task_id: str, code: dict, remove=(),
                    env: dict = None) -> str:
        wt = self.worktree(task_id)
        for rel, text in code.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        for rel in remove:
            (wt / rel).unlink()
        with mock.patch.dict(os.environ, env or {}):
            self.git("-C", str(wt), "add", "-A")
            self.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: код задачи")
        return self.git("-C", str(wt), "rev-parse", "HEAD").strip()

    def branch_head(self, task_id: str) -> str:
        return self.git("-C", str(self.ext_clone), "rev-parse",
                        store.get_task(self.conn, task_id)["branch"]).strip()

    # ------------------------------------------------------------ команды

    def run_cmd(self, fn, task_id: str) -> tuple:
        """(новые записи журнала задачи, вывод с текстом отказа)."""
        rows = store.task_steps(self.conn, task_id)
        before = rows[-1]["id"] if rows else 0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(task_id)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        new_rows = [dict(r) for r in store.task_steps(self.conn, task_id)
                    if r["id"] > before]
        return new_rows, buf.getvalue()

    def advance(self, task_id: str) -> tuple:
        return self.run_cmd(fsm.cmd_advance, task_id)

    def approve(self, task_id: str) -> tuple:
        return self.run_cmd(fsm.cmd_approve, task_id)

    def state(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]

    @staticmethod
    def with_action(rows: list, action: str) -> list:
        return [r for r in rows if r["action"] == action]

    def text_of(self, rows: list, out: str) -> str:
        return self.explain("\n".join(f"{r['action']} | {r['detail'] or ''}"
                                      for r in rows) + "\n--- вывод:\n" + out)


# ------------------------------------------------------------- AC-15/AC-16


class _GatesScenarios:
    """Общие сценарии AC-15 (с профилем) и AC-16 (без профиля): гейт зон,
    `no_paths`, эскалация мержа по защищённому пути."""

    def check_zones_gate_refuses_file_outside_zones(self):
        zone, code = self.code_file()
        stray = f"zs{self.word()}/{self.word()}.py"
        task = self.new_task("in_dev", [zone], {code: "A = 1\n", stray: "B = 2\n"})
        rows, out = self.advance(task)
        refusals = self.with_action(rows, ZONES_ACTION)
        self.assertTrue(refusals and stray in refusals[0]["detail"],
                        self.text_of(rows, out))
        self.assertEqual(self.state(task), "in_dev", self.text_of(rows, out))

    def check_no_paths_edit_refused(self):
        zone, code = self.code_file()
        rel = self.protected_path()
        task = self.new_task("in_dev", [zone, rel], {code: "A = 1\n", rel: "x\n"})
        rows, out = self.advance(task)
        refusals = self.with_action(rows, PROTECTED_ACTION)
        self.assertTrue(refusals and rel in refusals[0]["detail"],
                        self.text_of(rows, out))
        self.assertEqual(self.state(task), "in_dev", self.text_of(rows, out))

    def check_merge_with_protected_path_escalates(self):
        rel = self.protected_path()
        code = {f"kod{self.word()}/{self.word()}.py": f"A = {self.seed}\n",
                rel: "защищённое\n"}
        task = self.new_task("merge_gate", None, code)
        rows, out = self.approve(task)
        self.assertEqual(self.state(task), "escalated", self.text_of(rows, out))
        expected = PROTECTED_MERGE_TEXT.format(rel=rel)
        self.assertTrue([r for r in rows if expected in (r["detail"] or "")],
                        self.text_of(rows, out))
        tree = self.git("--git-dir", str(self.ext_origin), "ls-tree", "-r",
                        "--name-only", f"refs/heads/{config.MAIN_BRANCH}")
        self.assertNotIn(rel, tree.splitlines(), self.text_of(rows, out))

    def deleted_test_task(self) -> str:
        zone, code = self.code_file()
        return self.new_task("in_dev", [zone, "tests/"], {code: "A = 1\n"},
                             remove=(self.existing_test,))

    def claimless_test_task(self) -> tuple:
        zone, code = self.code_file()
        rel = f"tests/test_{self.word()}.py"
        task = self.new_task("in_dev", [zone, "tests/"], {
            code: "A = 1\n",
            rel: f"def test_{self.word()}():\n    assert 1 + 1 == 2\n"})
        return task, rel


class ExternalWithProfileTest(_GatesScenarios, ExternalFlowSandbox):
    """AC-15: внешний проект с голым `origin` и профилем тестов."""

    WITH_PROFILE = True

    def test_ac15_a_zones_gate_refuses_file_outside_zones(self):
        """(а) Гейт зон отказывает задаче проекта с профилем на файле вне зон.

        Сценарий: ветка задачи несёт файл кода в заявленной зоне и файл в
        случайном каталоге вне зон; `advance` из `in_dev` пишет отказ
        гейта зон, называющий этот файл, задача остаётся в `in_dev`.

        Ловит мутацию: гейт зон для внешнего проекта сравнивает дифф не в
        его репозитории (или пропускает внешний проект) — отказа нет,
        задача уходит дальше.
        """
        self.check_zones_gate_refuses_file_outside_zones()

    def test_ac15_b_no_paths_edit_refused(self):
        """(б) Правка пути из `no_paths` проекта получает отказ «защищённый путь».

        Сценарий: ветка трогает файл под случайной записью `no_paths`
        проекта; путь покрыт и зонами задачи. `advance` пишет отказ
        «защищённый путь», называющий файл; задача остаётся в `in_dev`.

        Ловит мутацию: перечень защищённых путей внешней задачи берётся из
        `config.PROTECTED_PATHS` пульта, а не из `no_paths` проекта —
        отказа нет.
        """
        self.check_no_paths_edit_refused()

    def test_ac15_c_deleted_test_refused_by_weakening_gate(self):
        """(в) Удаление теста без мандата получает отказ гейта неослабления.

        Сценарий: ветка удаляет тест проекта `tests/test_<имя>.py`,
        существующий на `main`; зоны покрывают `tests/`. `advance` пишет
        отказ `test_integrity.TEST_INTEGRITY_REFUSAL_ACTION`, называющий
        удалённый файл; задача остаётся в `in_dev`.

        Ловит мутацию: гейт неослабления для внешнего проекта сравнивает
        `tests/` не в репозитории проекта (или пропускает его при наличии
        профиля) — удаление проходит без отказа.
        """
        task = self.deleted_test_task()
        rows, out = self.advance(task)
        refusals = self.with_action(rows, test_integrity.TEST_INTEGRITY_REFUSAL_ACTION)
        self.assertTrue(refusals and self.existing_test in refusals[0]["detail"],
                        self.text_of(rows, out))
        self.assertEqual(self.state(task), "in_dev", self.text_of(rows, out))

    def test_ac15_d_new_test_without_claim_refused_by_mutation_gate(self):
        """(г) Новый тест без строки «Ловит мутацию:» получает отказ гейта заявки мутации.

        Сценарий: ветка добавляет `tests/test_<имя>.py` с тестовой
        функцией без докстринга с заявкой; зоны покрывают `tests/`.
        `advance` пишет отказ гейта заявки мутации, называющий файл;
        задача остаётся в `in_dev`.

        Ловит мутацию: гейт заявки мутации для внешнего проекта с
        профилем не включается (как без профиля) — отказа нет.
        """
        task, rel = self.claimless_test_task()
        rows, out = self.advance(task)
        refusals = self.with_action(rows, MUTATION_ACTION)
        self.assertTrue(refusals and rel in refusals[0]["detail"],
                        self.text_of(rows, out))
        self.assertEqual(self.state(task), "in_dev", self.text_of(rows, out))

    def test_ac15_e_merge_of_protected_path_escalates(self):
        """(д) `approve` на гейте мержа задачи, тронувшей защищённый путь проекта, переводит её в `escalated`.

        Сценарий: задача на `merge_gate`, её ветка трогает путь под
        `no_paths` проекта. После `approve` задача в `escalated`, журнал
        называет «защищённый путь <путь>», а `origin/main` проекта этого
        пути не несёт.

        Ловит мутацию: сверка защищённых путей на гейте мержа читает
        перечень пульта вместо `no_paths` проекта — задача мержится, путь
        попадает в `origin/main` проекта.
        """
        self.check_merge_with_protected_path_escalates()


class ExternalWithoutProfileTest(_GatesScenarios, ExternalFlowSandbox):
    """AC-16: тот же проект без профиля тестов."""

    WITH_PROFILE = False

    def skip_actions(self, rows: list) -> list:
        return [r["action"] for r in rows
                if r["action"].startswith(project_profile.SKIP_ACTION)]

    def test_ac16_language_checks_skipped_with_journal_record(self):
        """Без профиля удаление теста и новый тест без заявки не получают отказов неослабления и заявки мутации, а журнал несёт запись о пропуске.

        Сценарий: (1) ветка удаляет существующий тест проекта; (2) ветка
        добавляет тест без «Ловит мутацию:»; зоны покрывают `tests/`. В
        обоих случаях `advance` не пишет ни отказа гейта неослабления, ни
        отказа гейта заявки мутации, а журнал задачи несёт записи
        `project_profile.SKIP_ACTION` о пропуске этих проверок.

        Ловит мутацию: проект без профиля получает языковые проверки
        профиля артели (или отказ «нет профиля», как у артели) — появляется
        отказ гейта неослабления/заявки мутации либо отказ профиля, записи
        о пропуске нет.
        """
        deleted = self.deleted_test_task()
        claimless, _ = self.claimless_test_task()
        for task in (deleted, claimless):
            with self.subTest(task=task, seed=self.seed):
                rows, out = self.advance(task)
                for action in (test_integrity.TEST_INTEGRITY_REFUSAL_ACTION,
                               MUTATION_ACTION, project_profile.REFUSAL_ACTION):
                    self.assertEqual(self.with_action(rows, action), [],
                                     self.text_of(rows, out))
                skips = self.skip_actions(rows)
                self.assertIn(
                    f"{project_profile.SKIP_ACTION}: {project_profile.CHECK_WEAKENING}",
                    skips, self.text_of(rows, out))
                self.assertIn(
                    f"{project_profile.SKIP_ACTION}: {project_profile.CHECK_MUTATION}",
                    skips, self.text_of(rows, out))

    def test_ac16_zones_gate_refuses_file_outside_zones(self):
        """Без профиля гейт зон отказывает на файле вне зон так же, как с профилем.

        Сценарий: тот же, что (а) AC-15, у проекта без профиля тестов.

        Ловит мутацию: отсутствие профиля выключает и гейт зон вместе с
        языковыми проверками — отказа нет.
        """
        self.check_zones_gate_refuses_file_outside_zones()

    def test_ac16_no_paths_edit_refused(self):
        """Без профиля правка пути из `no_paths` получает отказ.

        Сценарий: тот же, что (б) AC-15, у проекта без профиля тестов.

        Ловит мутацию: отсутствие профиля выключает сверку защищённых
        путей — отказа нет.
        """
        self.check_no_paths_edit_refused()

    def test_ac16_merge_with_protected_path_escalates(self):
        """Без профиля мерж задачи с защищённым путём эскалирует.

        Сценарий: тот же, что (д) AC-15, у проекта без профиля тестов.

        Ловит мутацию: гейт мержа проекта без профиля пропускает сверку
        защищённых путей вместе с прогоном тестов — задача мержится.
        """
        self.check_merge_with_protected_path_escalates()


# ------------------------------------------------------------------- AC-4


class UncommittedResultTest(ExternalFlowSandbox):

    def reject_ext_commits(self) -> Path:
        hook = self.ext_clone / ".git" / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\necho 'hook says no' >&2\nexit 1\n",
                        encoding="utf-8")
        hook.chmod(0o755)
        self.addCleanup(hook.unlink, missing_ok=True)
        return hook

    def leave_step_result(self, task_id: str, rel: str) -> None:
        path = self.worktree(task_id) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"X = {self.seed}\n", encoding="utf-8")

    def failed_records(self, task_id: str) -> list:
        return [r for r in store.task_steps(self.conn, task_id)
                if r["action"] == checkpoint.PULT_COMMIT_GIT_FAILED_ACTION]

    def failed_pult_commit(self, task_id: str, rel: str) -> None:
        """Результат шага разработчика в рабочей копии; git отказывает
        коммиту пульта (хук клона проекта) — запись журнала об отказе есть,
        файл не закоммичен."""
        self.leave_step_result(task_id, rel)
        hook = self.reject_ext_commits()
        capture(checkpoint.commit_success_checkpoint, self.conn, task_id,
                "developer")
        hook.unlink()
        self.assertTrue(self.failed_records(task_id), self.explain(
            "git не отказал коммиту пульта — сценарий не построен"))

    def test_ac4_uncommitted_step_result_refuses_in_dev_exit(self):
        """У задачи внешнего проекта незакоммиченный результат шага после отказа git на коммите пульта отказывает переходу из `in_dev`.

        Сценарий: разработчик оставил файл в зоне задачи; git отказал
        коммиту пульта (хук `pre-commit` клона проекта), файл остался в
        рабочей копии. После снятия хука `advance` пишет отказ
        «результат шага не закоммичен», называющий файл; задача остаётся
        в `in_dev`.

        Ловит мутацию: сверка незакоммиченного результата (`_dirty_refuses`)
        оставлена только артели — внешняя задача уходит из `in_dev` с
        незакоммиченным файлом.
        """
        zone, code = self.code_file()
        task = self.new_task("in_dev", [zone], {code: "A = 1\n"})
        rel = f"{zone}{self.word()}.py"
        self.failed_pult_commit(task, rel)
        rows, out = self.advance(task)
        refusals = self.with_action(rows, UNCOMMITTED_ACTION)
        self.assertTrue(refusals and rel in refusals[0]["detail"],
                        self.text_of(rows, out))
        self.assertEqual(self.state(task), "in_dev", self.text_of(rows, out))

    def test_ac4_uncommitted_step_result_refuses_tests_writing_exit(self):
        """Тот же незакоммиченный результат отказывает выходу задачи внешнего проекта из `tests_writing`.

        Сценарий: задача в `tests_writing`; файл автора тестов в зоне задачи
        не закоммичен, журнал несёт запись пульта
        `checkpoint.PULT_COMMIT_GIT_FAILED_ACTION` (git отказал коммиту
        пульта). `advance` пишет отказ «результат шага не закоммичен»,
        называющий файл; задача остаётся в `tests_writing`.

        Ловит мутацию: сверка на выходе `tests_writing` оставлена только
        артели — отказа нет (или задача уходит дальше по другому пути без
        упоминания незакоммиченного результата).
        """
        zone, code = self.code_file()
        task = self.new_task("tests_writing", [zone], {code: "A = 1\n"})
        rel = f"{zone}test_{self.word()}.py"
        self.leave_step_result(task, rel)
        store.journal(self.conn, task, "orchestrator",
                      checkpoint.PULT_COMMIT_GIT_FAILED_ACTION,
                      f"{task}: git commit отказал (хук); изменения оставлены "
                      f"в worktree незакоммиченными, ничего не откачено")
        rows, out = self.advance(task)
        refusals = self.with_action(rows, UNCOMMITTED_ACTION)
        self.assertTrue(refusals and rel in refusals[0]["detail"],
                        self.text_of(rows, out))
        self.assertEqual(self.state(task), "tests_writing",
                         self.text_of(rows, out))


# ------------------------------------------------------------------- AC-11


class ReviewReworkGateTest(ExternalFlowSandbox):

    def dated(self, when: datetime) -> dict:
        stamp = when.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        return {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}

    def task_with_review_verdict(self) -> str:
        """Задача в `in_dev`: код закоммичен ДО вердикта, вердикт ревью
        `changes_requested` — автокоммитом шага reviewer после кода; шага
        developer после вердикта не было."""
        past = datetime.now(timezone.utc) - timedelta(
            hours=self.rng.randint(2, 48))
        zone, code = self.code_file()
        task = self.new_task("in_dev", [zone], {code: "A = 1\n"},
                             commit_env=self.dated(past))
        docs = config.PROJECTS / self.ext / "tasks" / task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "REVIEW.md").write_text(REVIEW_TEXT.format(
            task=task, iteration=self.rng.randint(1, 3), word=self.word()),
            encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, self.conn, task, "reviewer")
        store.journal(self.conn, task, "fsm", "state -> in_dev",
                      "замечания ревью, итерация 1")
        self.zone = zone
        return task

    def test_ac11_review_rework_gate_refuses_external_task(self):
        """Гейт «замечания ревью не отработаны» отказывает задаче внешнего проекта без коммита разработчика после вердикта.

        Сценарий: REVIEW.md в ссылке документов несёт `status:
        changes_requested`, последний коммит кодовой ветки — раньше
        вердикта, шага developer после возврата в `in_dev` нет. `advance`
        пишет отказ «замечания ревью не отработаны», задача остаётся в
        `in_dev`. Вторая задача — тот же вердикт, но после него в ветке
        коммит разработчика: такого отказа нет.

        Ловит мутацию: гейт оставлен только артели (`store.task_target !=
        DEFAULT_TARGET` -> пропуск) — у первой задачи отказа нет; либо
        гейт читает ветку не в репозитории проекта — время коммитов не
        прочитано, и вторая задача получает отказ.
        """
        stale = self.task_with_review_verdict()
        rows, out = self.advance(stale)
        self.assertTrue(self.with_action(rows, REWORK_ACTION),
                        self.text_of(rows, out))
        self.assertEqual(self.state(stale), "in_dev", self.text_of(rows, out))

        reworked = self.task_with_review_verdict()
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        self.commit_code(reworked, {f"{self.zone}{self.word()}.py": "B = 2\n"},
                         env=self.dated(future))
        rows, out = self.advance(reworked)
        self.assertEqual(self.with_action(rows, REWORK_ACTION), [],
                         self.text_of(rows, out))


# ------------------------------------------------------------------- AC-10


class MergeGateDiffBytesTest(ExternalFlowSandbox):

    def test_ac10_diff_bytes_filled_on_entry_into_merge_gate(self):
        """На входе в `merge_gate` у задачи внешнего проекта заполняется `diff_bytes` — размер диффа ветки против базы в репозитории проекта.

        Сценарий: задача проекта в `acceptance` с кодом случайного объёма в
        ветке; `approve` переводит её в `merge_gate`. Колонка `diff_bytes`
        равна числу байт `git diff <база>...<ветка>` в клоне проекта
        (`review.git_diff_part` с `repo=` клона).

        Ловит мутацию: снимок на входе в `merge_gate` считает `diff_bytes`
        только у артели — у внешней задачи колонка пуста; либо дифф
        считается в клоне артели — размер не совпадает (ветки там нет).
        """
        zone, code = self.code_file()
        body = "".join(f"V{i} = {self.rng.randrange(10**6)}\n"
                       for i in range(self.rng.randint(3, 40)))
        task = self.new_task("acceptance", [zone], {code: body})
        rows, out = self.approve(task)
        self.assertEqual(self.state(task), "merge_gate", self.text_of(rows, out))
        branch = store.get_task(self.conn, task)["branch"]
        diff, _, reason = review.git_diff_part(config.MAIN_BRANCH, branch,
                                               repo=self.ext_clone)
        self.assertFalse(reason, self.explain(f"дифф не прочитан: {reason}"))
        got = store.get_task(self.conn, task)["diff_bytes"]
        self.assertEqual(got, len(diff.encode("utf-8")), self.text_of(rows, out))


# -------------------------------------------------------------------- AC-7


class RemoteAndBaseResolutionTest(ExternalFlowSandbox):

    def behind_task(self) -> tuple:
        """Задача проекта в `in_dev`, чья ветка отстала от `origin/main`
        проекта на один коммит. (id, голова ветки до перехода)."""
        zone, code = self.code_file()
        task = self.new_task("in_dev", [zone], {code: "A = 1\n"})
        self.commit_to_ext_main({f"main_{self.word()}.txt": f"{self.seed}\n"})
        return task, self.branch_head(task)

    def test_ac7_pull_takes_base_from_repo_context(self):
        """Подтяжка main задачи внешнего проекта берёт базу из `repo_context.resolve`, без своего разрешения в `fsm.py`.

        Сценарий: ветка задачи отстала от `origin/main` проекта.
        `repo_context.resolve` проекта подменён так, что отдаёт ту же
        запись, но с базой — ветка, которой в `origin` нет: подтяжка
        деградирует как при неответившем git — ветку не трогает. Без
        подмены та же задача (вторая) подтягивает `origin/main` — голова
        ветки сдвигается.

        Ловит мутацию: `fsm.py` по-прежнему сам читает базу проекта из
        `targets.yaml` (дубль `resolve`) — под подменой подтяжка всё равно
        идёт по базе записи, и голова ветки сдвигается.
        """
        real_resolve = repo_context.resolve
        missing = "net-" + self.word()

        def resolve(name):
            ctx = real_resolve(name)
            if ctx is not None and name == self.ext:
                return dataclasses.replace(ctx, base=missing)
            return ctx

        task, head = self.behind_task()
        with mock.patch.object(repo_context, "resolve", resolve):
            rows, out = self.advance(task)
        self.assertEqual(self.branch_head(task), head, self.text_of(
            rows, f"подтяжка шла не по базе repo_context ({missing}):\n{out}"))

        control, control_head = self.behind_task()
        rows, out = self.advance(control)
        self.assertNotEqual(self.branch_head(control), control_head,
                            self.text_of(rows, "без подмены подтяжки нет:\n" + out))

    def test_ac7_unreadable_entry_pull_and_merge_do_not_touch_pult_origin(self):
        """Подтяжка и мерж задачи проекта с нечитаемой записью `targets.yaml` не идут на `origin` пульта.

        Сценарий: задача проекта в `in_dev` (ветка отстала от его
        `origin/main`) и задача на `merge_gate`; затем запись проекта
        убирается из `targets.yaml`. `advance` не меняет голову ветки (не
        подтягивает ни main проекта, ни main пульта); `approve` оставляет
        задачу на `merge_gate`; `origin/main` пульта и проекта не
        сдвигаются.

        Ловит мутацию: при неразрешённом контексте подтяжка/мерж
        откатываются на `origin` пульта (remote `origin` и база
        `config.MAIN_BRANCH` по умолчанию в `config.ROOT`) — история пульта
        попадает в ветку проекта или мерж уходит в `origin` пульта.
        """
        task, head = self.behind_task()
        zone, code = self.code_file()
        merge_task = self.new_task("merge_gate", None, {code: "M = 1\n"})
        pult_main = self.git("--git-dir", str(self.artel_origin), "rev-parse",
                             config.MAIN_BRANCH).strip()
        ext_main = self.git("--git-dir", str(self.ext_origin), "rev-parse",
                            config.MAIN_BRANCH).strip()
        self.write_targets(ext_entry=False)

        rows, out = self.advance(task)
        self.assertEqual(self.branch_head(task), head, self.text_of(rows, out))
        rows, out = self.approve(merge_task)
        self.assertEqual(self.state(merge_task), "merge_gate",
                         self.text_of(rows, out))
        self.assertEqual(self.git("--git-dir", str(self.artel_origin),
                                  "rev-parse", config.MAIN_BRANCH).strip(),
                         pult_main, self.explain("origin пульта сдвинут"))
        self.assertEqual(self.git("--git-dir", str(self.ext_origin),
                                  "rev-parse", config.MAIN_BRANCH).strip(),
                         ext_main, self.explain("origin проекта сдвинут"))

    def test_ac7_artel_with_broken_targets_keeps_origin_and_main(self):
        """Для артели при сломанном `targets.yaml` remote — `origin`, база — `config.MAIN_BRANCH`.

        Сценарий: `targets.yaml` переписан нечитаемым текстом (случайный
        мусор, незакрытая структура); контекст артели разрешается с
        `remote="origin"` и `base=config.MAIN_BRANCH`, а контекст внешнего
        проекта — нет.

        Ловит мутацию: разрешение артели стало читать её запись
        `targets.yaml` (как у любого проекта) — при сломанном файле контекст
        артели не разрешён.
        """
        config.TARGETS.write_text(
            f"targets: [{self.word()}: {{\n  - :: {self.word()}\n",
            encoding="utf-8")
        ctx = repo_context.resolve(config.DEFAULT_TARGET)
        self.assertIsNotNone(ctx, self.explain("контекст артели не разрешён"))
        self.assertEqual((ctx.remote, ctx.base), ("origin", config.MAIN_BRANCH),
                         self.explain(str(ctx)))
        self.assertIsNone(repo_context.resolve(self.ext),
                          self.explain("контекст проекта при сломанном файле"))


if __name__ == "__main__":
    import unittest
    unittest.main()
