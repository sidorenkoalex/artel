"""Коммит результата шага пультом: штатный коммит — норма, отказ git —
именованная запись журнала без потери работы, эскалация роли проходит
сквозь коммит пульта.

Группа: долгоживущий
Красен до реализации: отказ git на коммите пульта сегодня молчит — запись журнала без имени операции и текста git (test_ac3, test_ac4), advance после отказа уводит задачу дальше по PLAN (test_ac3); test_ac2 и test_ac5 держат уже существующее поведение и зелены с рождения.

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`): репозиторий
пульта с bare `origin`, задача target по умолчанию в `in_dev`/
`tests_writing`, worktree её кодовой ветки (`workspace.ensure`). Шаг роли
изображён прямо: файлы пишутся в worktree, затем — тем же порядком, что у
штатного завершения шага в `runner` — чекпоинт успешного шага
(`checkpoint.commit_success_checkpoint`), автокоммит артефактов шага
(`checkpoint.commit_step_artifacts`) и `fsm.cmd_advance`. Отказ git —
настоящий, не подмена: хук `pre-commit` с ненулевым кодом (операция
`commit`) и занятый `index.lock` рабочей копии (операция `add`). Имена
файлов и текст отказа хука порождаются при каждом запуске от зерна.
"""
import io
import random
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from orchestrator import alerts, checkpoint, config, fsm, store, workspace
from scripts import guard
from tests.sandbox import RealGitSandbox

FIXTURE_TASK = "01M0000000000000000000PCFX"
FIXTURE_BRANCH = "task/fixture-pult-commit"

PLAN_ESCALATE = """---
task: {task}
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: фикстура коммита пультом

## Подход
Фикстура песочницы.

## Шаги
1. Фикстура.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Фикстура песочницы, систему не затрагивает.

## Эскалация
- **Вопросы** — вопрос фикстуры {tag}: вариант А или Б? Дефолт — А.
- **Контекст** — фикстура песочницы.
- **Блокирует** — фикстура песочницы.
"""

# «роль обязана коммитить», но не «роль не обязана коммитить».
ROLE_MUST_COMMIT = re.compile(r"(?<!не )обязан\w*\s+коммит|роль\s+обязан",
                              re.I)
FAILURE_ACTION = re.compile(r"FAILED|провал|отклон|отказ", re.I)
DEFECT_WORDS = re.compile(r"дефект|нарушени", re.I)


class _PultCommitSandbox(RealGitSandbox):
    """Задача в `in_dev` с worktree кодовой ветки на настоящем git."""

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        store.insert_task(self.conn, FIXTURE_TASK, "Фикстура коммита пультом",
                          "in_dev", FIXTURE_BRANCH, config.DEFAULT_TARGET, 25.0)
        wt, error = workspace.ensure(FIXTURE_TASK, FIXTURE_BRANCH)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt = wt

    # --- окружение шага ---------------------------------------------------

    def wt_git(self, *args: str) -> str:
        return self.git("-C", str(self.wt), *args)

    def wt_head(self) -> str:
        return self.wt_git("rev-parse", "HEAD").strip()

    def write(self, rel: str, text: str) -> Path:
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def code_file(self) -> tuple[str, str]:
        n = self.rng.randrange(10 ** 6)
        return (f"pkg{n % 7}/module_{n}.py",
                f"VALUE = {n}\n" * (1 + self.rng.randrange(5)))

    def write_plan_escalate(self) -> None:
        self.write(str(Path("tasks", FIXTURE_TASK, "PLAN.md")),
                   PLAN_ESCALATE.format(task=FIXTURE_TASK, tag=self.seed))

    def reject_commits_with_hook(self) -> str:
        """Хук `pre-commit`, отказывающий любому коммиту с текстом в stderr;
        возвращает этот текст."""
        token = f"hook-refusal-{self.seed}"
        common = Path(self.git("rev-parse", "--git-common-dir").strip())
        if not common.is_absolute():
            common = self.root / common
        hook = common / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(f"#!/bin/sh\necho '{token}' >&2\nexit 1\n",
                        encoding="utf-8")
        hook.chmod(0o755)
        self.addCleanup(hook.unlink, missing_ok=True)
        self.hook = hook
        return token

    def lock_index(self) -> Path:
        """Занятый `index.lock` worktree — `git add` отказывает «File exists»."""
        lock = Path(self.wt_git("rev-parse", "--git-path", "index.lock").strip())
        if not lock.is_absolute():
            lock = self.wt / lock
        lock.write_text("", encoding="utf-8")
        self.addCleanup(lock.unlink, missing_ok=True)
        self.lock = lock
        return lock

    # --- шаг пульта и наблюдения -----------------------------------------

    def last_step_id(self) -> int:
        rows = store.task_steps(self.conn, FIXTURE_TASK)
        return rows[-1]["id"] if rows else 0

    def steps_since(self, since: int) -> list:
        return [r for r in store.task_steps(self.conn, FIXTURE_TASK)
                if r["id"] > since]

    @staticmethod
    def render(rows) -> str:
        return "\n".join(f"[{r['actor']}] {r['action']} | {r['detail'] or ''}"
                         for r in rows)

    def finish_step(self, role: str) -> None:
        """Штатное завершение шага пультом: код, затем артефакты шага."""
        checkpoint.commit_success_checkpoint(self.conn, FIXTURE_TASK, role)
        checkpoint.commit_step_artifacts(self.conn, FIXTURE_TASK, role)

    def advance(self) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                fsm.cmd_advance(FIXTURE_TASK)
            except SystemExit as exc:
                buf.write(f"\nSystemExit(advance): {exc}")
        return buf.getvalue()

    def state(self) -> str:
        return store.get_task(self.conn, FIXTURE_TASK)["state"]

    def porcelain(self) -> str:
        return self.wt_git("status", "--porcelain=v1", "--untracked-files=all")


class SuccessfulPultCommitIsNormTest(_PultCommitSandbox):

    def test_ac2_successful_pult_commit_is_not_a_defect(self):
        """developer оставил код незакоммиченным, пульт его штатно закоммитил.

        Наблюдение: код на голове ветки (коммит состоялся), открытых
        алертов не прибавилось, среди новых записей журнала нет записи
        провала/отказа (FAILED, «провал», «отклонён», «отказ»), и ни одна
        новая запись не несёт слов «дефект» и «нарушение» — в том числе
        запись о самом коммите пульта.

        Ловит мутацию: коммит пультом снова квалифицирован как дефект
        шага — запись «код закоммичен пультом … — дефект шага» или
        `alerts.raise_attention_alert` на этом пути: в журнале появится
        слово «дефект» либо прибавится открытый алерт.
        """
        rel, text = self.code_file()
        self.write(rel, text)
        before_head = self.wt_head()
        alerts_before = len(alerts.open_alerts(self.conn))
        since = self.last_step_id()

        self.finish_step("developer")

        rows = self.steps_since(since)
        journal = self.render(rows)
        context = f"зерно: {self.seed}\n{journal}"
        self.assertNotEqual(self.wt_head(), before_head,
                            f"пульт не закоммитил код шага\n{context}")
        self.assertIn(rel, self.wt_git("show", "--name-only", "--format=",
                                       "HEAD"), context)
        self.assertEqual(len(alerts.open_alerts(self.conn)), alerts_before,
                         f"штатный коммит пульта завёл алерт\n{context}")
        for row in rows:
            self.assertIsNone(FAILURE_ACTION.search(row["action"]),
                              f"запись провала/отказа шага\n{context}")
            self.assertIsNone(
                DEFECT_WORDS.search(f"{row['action']} {row['detail'] or ''}"),
                f"запись квалифицирует коммит пульта как дефект\n{context}")


class PultCommitGitFailureTest(_PultCommitSandbox):

    def test_ac3_git_failure_is_journaled_kept_and_blocks_advance(self):
        """git отказывает на операции коммита пульта — `commit` (хук
        pre-commit) и `add` (занятый index.lock), по отдельности.

        Шаг developer оставил код и PLAN.md `status: escalate` — без
        отказа git `advance` увёл бы задачу в `escalated` (контроль —
        test_ac5). После отказа: новая запись журнала несёт имя операции
        git и текст его ошибки; код на диске прежний, в `git status`
        значится, голова ветки не сдвинулась; причина отказа снята (хук
        удалён, lock убран), и `advance` всё равно оставляет задачу в
        `in_dev`, а его запись отказа называет незакоммиченный результат
        шага («закоммич…», «шаг…»); нигде в журнале и выводе advance нет
        утверждения, что коммитить обязана роль.

        Ловит мутацию: `_commit_worktree_change` по-прежнему возвращает
        «не закоммичено» без записи (нет записи с «commit»/«add» и текстом
        git), либо отказ git сопровождается откатом worktree (`reset
        --hard`/`checkout`) — файла нет на диске или в status, либо
        advance не сверяет незакоммиченный результат — задача уходит в
        `escalated`, либо отказ по грязной копии сохраняет текст «роль
        обязана коммитить артефакты».
        """
        base = self.wt_head()
        for operation in ("commit", "add"):
            with self.subTest(operation=operation):
                try:
                    self._run_failure_scenario(operation)
                finally:
                    for path in (getattr(self, "hook", None),
                                 getattr(self, "lock", None)):
                        if path is not None:
                            path.unlink(missing_ok=True)
                    self.wt_git("reset", "-q", "--hard", base)
                    self.wt_git("clean", "-q", "-fdx", "--", ".")

    def _run_failure_scenario(self, operation: str) -> None:
        store.update_task(self.conn, FIXTURE_TASK, state="in_dev")
        rel, text = self.code_file()
        self.write(rel, text)
        self.write_plan_escalate()
        if operation == "commit":
            error_text = self.reject_commits_with_hook()
            undo = self.hook
        else:
            undo = self.lock_index()
            error_text = "index.lock"
        before_head = self.wt_head()
        since = self.last_step_id()

        self.finish_step("developer")

        rows = self.steps_since(since)
        context = f"зерно: {self.seed}, операция {operation}\n{self.render(rows)}"
        op_re = re.compile(rf"\b{operation}\b")
        named = [r for r in rows
                 if op_re.search(f"{r['action']} {r['detail'] or ''}")
                 and error_text in f"{r['action']} {r['detail'] or ''}"]
        self.assertTrue(named, "нет записи журнала с именем операции git и "
                               f"текстом его ошибки\n{context}")
        self.assertEqual(self.wt_head(), before_head,
                         f"голова ветки сдвинулась\n{context}")
        self.assertEqual((self.wt / rel).read_text(encoding="utf-8"), text,
                         f"код шага откачен или изменён\n{context}")
        self.assertIn(rel, self.porcelain(),
                      f"код шага не значится незакоммиченным\n{context}")

        undo.unlink()
        since_advance = self.last_step_id()
        out = self.advance()
        adv_rows = self.steps_since(since_advance)
        adv_context = (f"{context}\n--- advance ---\n{self.render(adv_rows)}"
                       f"\n{out}")
        self.assertEqual(self.state(), "in_dev",
                         f"advance перевёл задачу после отказа git\n{adv_context}")
        refusals = [f"{r['action']} {r['detail'] or ''}" for r in adv_rows
                    if re.search(r"отклон", r["action"], re.I)]
        self.assertTrue(
            any(re.search(r"закоммич", t, re.I) and re.search(r"шаг", t, re.I)
                for t in refusals),
            f"отказ advance не называет незакоммиченный результат шага\n"
            f"{adv_context}")
        self.assertIsNone(
            ROLE_MUST_COMMIT.search(f"{self.render(adv_rows)}\n{out}"),
            f"отказ advance утверждает, что коммитить обязана роль\n"
            f"{adv_context}")


class TestAuthorCommitGitFailureTest(_PultCommitSandbox):

    def test_ac4_test_author_commit_failure_names_git_operation(self):
        """test_author в `tests_writing` оставил свой долгоживущий файл
        `tests/<префикс задачи><имя>.py`, хук pre-commit отказывает коммиту
        пульта.

        Наблюдение: запись `TEST_AUTHOR_NOT_COMMITTED_ACTION` несёт имя
        операции git («commit») и текст ошибки git (вывод хука); файл
        остаётся на диске с прежним содержимым, голова ветки не сдвинулась.

        Ловит мутацию: запись test_author по-прежнему «git не принял
        коммит» без операции и вывода git — в ней нет ни «commit», ни
        текста хука.
        """
        store.update_task(self.conn, FIXTURE_TASK, state="tests_writing")
        name = f"case_{self.rng.randrange(10 ** 6)}"
        rel = f"{guard.long_lived_path_prefix(FIXTURE_TASK)}{name}.py"
        text = f"# долгоживущий файл фикстуры {self.seed}\n"
        self.write(rel, text)
        token = self.reject_commits_with_hook()
        before_head = self.wt_head()
        since = self.last_step_id()

        checkpoint.commit_success_checkpoint(self.conn, FIXTURE_TASK,
                                             "test_author")

        rows = self.steps_since(since)
        context = f"зерно: {self.seed}\n{self.render(rows)}"
        records = [f"{r['action']} {r['detail'] or ''}" for r in rows
                   if r["action"] == checkpoint.TEST_AUTHOR_NOT_COMMITTED_ACTION]
        self.assertTrue(records, f"нет записи test_author о некоммите\n{context}")
        self.assertTrue(
            any(re.search(r"\bcommit\b", r) and token in r for r in records),
            f"запись test_author без операции git и текста ошибки\n{context}")
        self.assertEqual(self.wt_head(), before_head, context)
        self.assertEqual((self.wt / rel).read_text(encoding="utf-8"), text,
                         f"файл test_author не остался в worktree\n{context}")


class RoleEscalationSurvivesPultCommitTest(_PultCommitSandbox):

    def test_ac5_plan_escalate_escalates_after_pult_commit(self):
        """Шаг developer оставил PLAN.md `status: escalate` и
        незакоммиченный код; пульт успешно закоммитил код.

        Наблюдение: код на голове ветки, а `advance` переводит задачу в
        `escalated`.

        Ловит мутацию: новая сверка незакоммиченного результата шага
        срабатывает и после успешного коммита пульта (например, признак
        отказа git не снимается или любой коммит пультом считается
        незавершённым шагом) — `advance` отказывает, задача остаётся в
        `in_dev`.
        """
        rel, text = self.code_file()
        self.write(rel, text)
        self.write_plan_escalate()
        before_head = self.wt_head()
        since = self.last_step_id()

        self.finish_step("developer")
        out = self.advance()

        context = (f"зерно: {self.seed}\n{self.render(self.steps_since(since))}"
                   f"\n{out}")
        self.assertNotEqual(self.wt_head(), before_head,
                            f"пульт не закоммитил код шага\n{context}")
        self.assertEqual(self.state(), "escalated", context)


if __name__ == "__main__":
    unittest.main()
