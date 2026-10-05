"""AC-3, AC-4: сверка незакоммиченного результата шага, паспорт и запись
«sha зафиксирован» — одной веткой логики для артели и внешнего проекта.

Группа: разовый
Обоснование группы: сценарий требует настоящего git задачи (клон проекта,
рабочая копия на ветке задачи, отказ git на коммите пульта настоящим хуком
`pre-commit`, ссылка документов `refs/artifacts/<id>`) и подмен внутренних
зависимостей пульта — долгоживущей группе это запрещено.

Красен до реализации: `fsm._dirty_refuses`/`fsm._tests_writing_ac_state` пропускают сверку незакоммиченного результата шага для не-артели, а `store._append_passport_line`/`store.record_fixation` ветвятся на `config.DEFAULT_TARGET` — у артели нет строки паспорта и поля `артефакты=`.

Песочница — `tests/sandbox.py::RealGitSandbox` (корень — git-репозиторий
артели, он же её клон) и `make_project_repo` (клон внешнего проекта со
своим bare-`origin`). Задача заводится напрямую в БД, рабочая копия —
`workspace.ensure`, как в `tests/test_role_commit_by_pult.py`.
"""
import io
import re
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from orchestrator import (artifact_branch, checkpoint, config, fsm, store,
                          workspace)
from scripts import guard
from tests.sandbox import RealGitSandbox, make_project_repo

EXTERNAL = "extproj"
UNCOMMITTED_REFUSAL = "переход отклонён: результат шага не закоммичен"
FIXATION_ACTION = "sha зафиксирован"
FIXATION_FIELDS = ("target", "sha", "чисто", "код", "артефакты")

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {res.stderr}")
    return res.stdout


class _TaskSandbox(RealGitSandbox):
    """Задача проекта `target` в состоянии `state`, рабочая копия на её
    ветке в клоне проекта."""

    def make_task(self, task_id: str, target: str, state: str) -> None:
        if target == config.DEFAULT_TARGET:
            self.add_synced_origin()
        else:
            make_project_repo(target)
        self.conn = store.db()
        self.task_id = task_id
        self.branch = f"task/{task_id.lower()}-fixture"
        store.insert_task(self.conn, task_id, "Фикстура фиксации", state,
                          self.branch, target, config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(task_id, self.branch)
        self.assertIsNone(error, error)
        self.wt = wt

    def write(self, rel: str, text: str = "x = 1\n") -> None:
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def reject_commits(self) -> Path:
        """Отказ git на любом коммите в репозитории рабочей копии задачи —
        настоящим хуком `pre-commit` (приём `tests/test_role_commit_by_pult.py`)."""
        common = Path(_git(self.wt, "rev-parse", "--git-common-dir").strip())
        if not common.is_absolute():
            common = self.wt / common
        hook = common / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\necho 'hook says no' >&2\nexit 1\n",
                        encoding="utf-8")
        hook.chmod(0o755)
        self.addCleanup(hook.unlink, missing_ok=True)
        return hook

    def fail_pult_commit(self, role: str) -> None:
        hook = self.reject_commits()
        checkpoint.commit_success_checkpoint(self.conn, self.task_id, role)
        self.assertTrue(
            [r for r in store.task_steps(self.conn, self.task_id)
             if r["action"] == checkpoint.PULT_COMMIT_GIT_FAILED_ACTION],
            "сценарий не воспроизвёл отказ git на коммите пульта")
        hook.unlink()

    def advance_refusals(self) -> list[str]:
        since = store.task_steps(self.conn, self.task_id)[-1]["id"]
        with redirect_stdout(io.StringIO()):
            try:
                fsm.cmd_advance(self.task_id)
            except SystemExit:
                pass
        return [r["detail"] for r in store.task_steps(self.conn, self.task_id)
                if r["id"] > since and r["action"] == UNCOMMITTED_REFUSAL]

    def state(self) -> str:
        return store.get_task(self.conn, self.task_id)["state"]


class UncommittedStepResultExternalTest(_TaskSandbox):

    def test_ac3_in_dev_exit_refuses_external_uncommitted_result(self):
        """Выход из `in_dev` внешней задачи отклоняется по незакоммиченному результату шага.

        Задача внешнего проекта в `in_dev`, PLAN.md `ready` в ссылке
        документов; разработчик оставил код в рабочей копии, git отказал
        коммиту пульта (хук `pre-commit`), хук снят. `advance` оставляет
        задачу в `in_dev` и пишет отказ «результат шага не закоммичен» с
        путём файла — как у задачи артели.

        Ловит мутацию: в `fsm._dirty_refuses` остаётся ранний выход для
        не-артели (`target != config.DEFAULT_TARGET`) — сверки нет, записи
        отказа «результат шага не закоммичен» в журнале нет, задача уходит
        дальше по гейтам `in_dev`."""
        self.make_task("01M0000000000000000000AC3D", EXTERNAL, "in_dev")
        artifact_branch.commit_files(
            self.task_id,
            {f"tasks/{self.task_id}/PLAN.md": PLAN_READY.format(task=self.task_id)},
            f"{self.task_id}: PLAN фикстуры")
        self.write("pkg/code.py")
        self.fail_pult_commit("developer")

        refusals = self.advance_refusals()

        self.assertEqual(self.state(), "in_dev")
        self.assertTrue(refusals, "нет отказа «результат шага не закоммичен»")
        self.assertIn("pkg/code.py", refusals[0])

    def test_ac3_tests_writing_exit_refuses_external_uncommitted_result(self):
        """Выход из `tests_writing` внешней задачи отклоняется по незакоммиченному результату шага.

        Задача внешнего проекта в `tests_writing`; test_author оставил
        долгоживущий тест в рабочей копии, git отказал коммиту пульта, хук
        снят. `advance` оставляет задачу в `tests_writing` и пишет отказ
        «результат шага не закоммичен» с путём этого файла.

        Ловит мутацию: в `fsm._tests_writing_ac_state` сверка остаётся под
        условием `task_target == config.DEFAULT_TARGET` — у внешней задачи
        отказ идёт по иной причине (документы/трассируемость) либо задача
        уходит в `in_dev`, записи «результат шага не закоммичен» нет."""
        self.make_task("01M0000000000000000000AC3T", EXTERNAL, "tests_writing")
        rel = f"{guard.long_lived_path_prefix(self.task_id)}case.py"
        self.write(rel, "def test_ac1_case():\n    pass\n")
        self.fail_pult_commit("test_author")

        refusals = self.advance_refusals()

        self.assertEqual(self.state(), "tests_writing")
        self.assertTrue(refusals, "нет отказа «результат шага не закоммичен»")
        self.assertIn(rel, refusals[0])


class UncommittedStepResultArtelTest(_TaskSandbox):

    def test_ac3_in_dev_exit_refuses_artel_uncommitted_result(self):
        """Выход из `in_dev` задачи артели отклоняется по незакоммиченному результату шага.

        Тот же сценарий, что у внешней задачи, на проекте артели — эталон
        «так же, как задача артели» критерия.

        Зелёный с рождения: держит прежнее поведение артели, которое
        удаление развилки обязано сохранить — отказ с путём файла и
        задача на месте."""
        self.make_task("01M0000000000000000000AC3A", config.DEFAULT_TARGET,
                       "in_dev")
        artifact_branch.commit_files(
            self.task_id,
            {f"tasks/{self.task_id}/PLAN.md": PLAN_READY.format(task=self.task_id)},
            f"{self.task_id}: PLAN фикстуры")
        self.write("pkg/code.py")
        self.fail_pult_commit("developer")

        refusals = self.advance_refusals()

        self.assertEqual(self.state(), "in_dev")
        self.assertTrue(refusals, "нет отказа «результат шага не закоммичен»")
        self.assertIn("pkg/code.py", refusals[0])


def _fields(detail: str) -> dict:
    return dict(re.findall(r"(?:^|,\s*)(\w+)=([^,]*)", detail))


class PassportAndFixationTest(_TaskSandbox):

    def transition(self) -> None:
        """Переход FSM `in_dev` -> `verifying` через единственную точку
        перехода `store.set_state`."""
        # Код задачи на её ветке — голова кодовой ветки отлична от базы.
        self.write("pkg/feature.py")
        _git(self.wt, "add", "-A")
        _git(self.wt, "commit", "-q", "-m", "код задачи")
        artifact_branch.commit_files(
            self.task_id,
            {f"tasks/{self.task_id}/PLAN.md": PLAN_READY.format(task=self.task_id)},
            f"{self.task_id}: PLAN фикстуры")
        store.set_state(self.conn, self.task_id, "verifying", "fsm",
                        expected_state="in_dev")

    def passport_text(self) -> str | None:
        repo = workspace.repo(store.task_target(self.conn, self.task_id))
        res = subprocess.run(
            ["git", "-C", str(repo), "show",
             f"{artifact_branch.branch_name(self.task_id)}:"
             f"{artifact_branch.PASSPORT_REL_TMPL.format(task_id=self.task_id)}"],
            capture_output=True, text=True)
        return res.stdout if res.returncode == 0 else None

    def fixation_fields(self) -> dict:
        details = [r["detail"] for r in store.task_steps(self.conn, self.task_id)
                   if r["action"] == FIXATION_ACTION]
        self.assertTrue(details, "нет записи «sha зафиксирован»")
        return _fields(details[-1])

    def code_head(self) -> str:
        return _git(self.wt, "rev-parse", "HEAD").strip()

    def test_ac4_artel_transition_appends_passport_line(self):
        """Переход задачи артели дописывает строку паспорта в её ссылку документов.

        Задача артели в `in_dev`, ссылка документов `refs/artifacts/<id>`
        заведена; переход в `verifying` через `store.set_state`. В ссылке
        появляется паспорт со строкой нового состояния — как у задачи
        внешнего проекта на том же переходе.

        Ловит мутацию: `store._append_passport_line` сохраняет ветку
        артели (только `send_pending`) — файла паспорта в ссылке документов
        артели нет, `git show` отказывает."""
        self.make_task("01M0000000000000000000AC4P", config.DEFAULT_TARGET,
                       "in_dev")
        self.transition()

        passport = self.passport_text()
        self.assertIsNotNone(passport, "в ссылке документов артели нет паспорта")
        self.assertIn("verifying", passport)

    def test_ac4_external_transition_appends_passport_line(self):
        """Переход задачи внешнего проекта дописывает строку паспорта в её ссылку документов.

        Эталон критерия «как у внешнего проекта»: тот же переход у задачи
        внешнего проекта.

        Зелёный с рождения: держит поведение внешнего проекта, которое
        удаление развилки обязано сохранить."""
        self.make_task("01M0000000000000000000AC4Q", EXTERNAL, "in_dev")
        self.transition()

        passport = self.passport_text()
        self.assertIsNotNone(passport, "в ссылке документов нет паспорта")
        self.assertIn("verifying", passport)

    def test_ac4_artel_fixation_record_carries_all_fields(self):
        """Запись «sha зафиксирован» задачи артели несёт пять полей, `код=` — голова кодовой ветки.

        Задача артели с коммитом кода на своей ветке переходит в
        `verifying`. Последняя запись «sha зафиксирован» несёт `target=`,
        `sha=`, `чисто=`, `код=`, `артефакты=`; `код=` равен голове кодовой
        ветки задачи в её рабочей копии.

        Ловит мутацию: `store.record_fixation` сохраняет формат артели без
        поля `артефакты=` — поля нет в записи; либо `код=` берётся с базы
        (`main`) вместо ветки задачи — значение не совпадает с головой
        ветки, на которой сделан коммит кода."""
        self.make_task("01M0000000000000000000AC4A", config.DEFAULT_TARGET,
                       "in_dev")
        self.transition()

        fields = self.fixation_fields()
        for name in FIXATION_FIELDS:
            self.assertIn(name, fields, f"нет поля {name}= у задачи артели")
        self.assertEqual(fields["код"], self.code_head())

    def test_ac4_external_fixation_record_carries_all_fields(self):
        """Запись «sha зафиксирован» задачи внешнего проекта несёт те же пять полей, `код=` — голова кодовой ветки.

        Тот же переход у задачи внешнего проекта: тот же набор полей и
        `код=` — голова её кодовой ветки.

        Ловит мутацию: общая ветка `store.record_fixation` после удаления
        развилки берёт `код=` из клона артели (`default_code_sha` без
        учёта проекта задачи) — у внешней задачи ветки там нет, `код=—`
        не совпадает с головой её ветки."""
        self.make_task("01M0000000000000000000AC4E", EXTERNAL, "in_dev")
        self.transition()

        fields = self.fixation_fields()
        for name in FIXATION_FIELDS:
            self.assertIn(name, fields, f"нет поля {name}= у внешней задачи")
        self.assertEqual(fields["код"], self.code_head())


if __name__ == "__main__":
    unittest.main()
