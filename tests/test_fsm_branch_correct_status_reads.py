"""Юнит-тесты ветко-корректных чтений SPEC.md/REVIEW.md/QUESTIONS.md в
`orchestrator/fsm.py` (SPEC T047): дополняют залоченные приёмочные тесты
`tasks/T047/acceptance_tests/test_branch_correct_status_reads.py` (AC-1..
AC-3) сценариями, которые они не покрывают — эскалация по QUESTIONS.md
на чужом чекауте, отказ (не молчаливое ожидание) при отсутствующем на
ветке ОБЯЗАТЕЛЬНОМ артефакте, и что guard проверяет именно текст ветки,
а не диск.

Реальный git (не заглушка), тем же приёмом, что
`tests/test_gitcmd_branch_reads.py` и приёмочные тесты этой задачи: сам
предмет проверки — расхождение диска и ветки, заглушкой это не
изобразить.
"""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artifact_branch, catalog, config, fsm,  # noqa: E402
                          gitcmd, store)
from tests.sandbox import (ALL_CONFIG_ATTRS, TmpRootTest,  # noqa: E402
                           capture_new_task_id, resilient_tmp_cleanup)

REPO_ROOT = Path(__file__).resolve().parent.parent

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: маркер ветки задачи

## Контекст
Существует только на ветке задачи.

## Требования
1. ...

## Критерии приёмки
AC-1. Критерий.

## Не входит
"""

REVIEW_APPROVED = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: маркер ветки задачи

## Соответствие SPEC
| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания
- ...

## Вердикт
approved

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""

QUESTIONS_READY = """---
task: {task}
type: questions
author_role: analyst
status: ready
schema_version: 2
---

# QUESTIONS: маркер ветки задачи

## Вопросы
1. **Вопрос?** — варианты: A) да; B) нет — дефолт: A.
"""


class RealGitBranchTest(TmpRootTest):
    """ROOT — свежий репозиторий с main; `cmd_new` (A7, generic-путь,
    AC-5) коммитит шаблонный SPEC.md плотницки в АРТЕФАКТНУЮ ВЕТКУ
    ПУЛЬТА (`artifact/<id>`, `artifact_branch.commit_files`), не в
    кодовую ветку/worktree задачи (`cmd_new` их больше не заводит вовсе)
    — ROOT остаётся на main. Дальнейшие артефакты этот тест коммитит
    ПРЯМО В АРТЕФАКТНУЮ ВЕТКУ (чекаутом в ROOT — реальный git, песочница
    временная, не рабочее дерево пульта), затем возвращает ROOT на
    main."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        import shutil
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        for attr in ALL_CONFIG_ATTRS:
            self.patches.enter_context(
                mock.patch.object(config, attr, self._patched_path(attr)))

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Ветко-корректные чтения статусов")
        self.tdir = config.TASKS / self.TASK
        self.branch = store.get_task(store.db(), self.TASK)["branch"]
        self.artifact_branch = artifact_branch.branch_name(self.TASK)

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def checkout(self, branch: str, create: bool = False) -> None:
        args = ["checkout", "-q"]
        if create:
            args.append("-b")
        args.append(branch)
        self.git(*args)

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def commit_task_dir(self, message: str = "артефакт") -> None:
        self.git("add", f"tasks/{self.TASK}")
        self.git("commit", "-q", "-m", message)

    def write(self, name: str, template: str) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(template.format(task=self.TASK),
                                      encoding="utf-8")

    def write_on_task_branch(self, name: str, template: str) -> None:
        """Кладёт файл прямо в АРТЕФАКТНУЮ ВЕТКУ ПУЛЬТА (A7 — веткой-
        источником `tasks/<id>/` служит она, не кодовая ветка задачи) и
        коммитит его там же, чекаутом в ROOT — реальный git песочницы,
        не рабочее дерево пульта."""
        self.checkout(self.artifact_branch)
        d = self.root / "tasks" / self.TASK
        (d / name).parent.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(template.format(task=self.TASK),
                              encoding="utf-8")
        self.git("add", f"tasks/{self.TASK}")
        self.git("commit", "-q", "-m", f"{name} задачи")
        self.checkout(config.MAIN_BRANCH)


# ---------------------------------------------------------------------
# QUESTIONS.md — необязательный артефакт: на чужом чекауте его наличие
# на ВЕТКЕ задачи обязано эскалировать так же, как наличие на диске
# (требование 3, явно названное SPEC).

class QuestionsOnForeignBranchTest(RealGitBranchTest):

    def test_ready_questions_on_task_branch_escalates_without_manual_checkout(self):
        self.write_on_task_branch("QUESTIONS.md", QUESTIONS_READY)
        self.assertEqual(gitcmd.current_branch(), config.MAIN_BRANCH)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "escalated",
            "QUESTIONS.md закоммичен только на ветке задачи — advance "
            "обязан эскалировать без ручного чекаута (SPEC T047, "
            "требование 3)")
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["escalated_from"],
            "spec_writing")

    def test_no_questions_on_either_side_falls_through_to_spec_check(self):
        """QUESTIONS.md отсутствует и на ветке, и на диске — эскалации
        нет, переход разбирает статус SPEC.md как обычно."""
        self.write_on_task_branch("SPEC.md", SPEC_READY)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "spec_gate")


# ---------------------------------------------------------------------
# Отсутствие ОБЯЗАТЕЛЬНОГО артефакта на реально существующей ветке — это
# именованный отказ (тот же принцип, что уже работал для PLAN.md/in_dev,
# T031), а не молчаливое «ещё не готово» с диска.

class RequiredArtifactMissingOnBranchTest(RealGitBranchTest):

    def _remove_task_dir_from_branch(self) -> None:
        """`cmd_new` (A7) сам коммитит шаблонный SPEC.md в артефактную
        ветку — «ветка есть, а обязательного артефакта на ней нет»
        обычным путём больше не возникает. Симулируем вырожденный случай
        (порча ветки, force-push поверх, ручной `git rm`) явным коммитом
        удаления `tasks/<id>/` поверх того, что уже сделал `cmd_new`."""
        self.checkout(self.artifact_branch)
        self.git("rm", "-r", "-q", f"tasks/{self.TASK}")
        self.git("commit", "-q", "-m", "tasks/ снесён с ветки")
        self.checkout(config.MAIN_BRANCH)

    def test_spec_writing_refuses_when_branch_exists_without_spec_md(self):
        self._remove_task_dir_from_branch()

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "spec_writing",
            "ветка задачи реально существует, но SPEC.md на ней не "
            "закоммичен — переход не имеет права продвинуться")
        self.assertIn("дерево не на ветке задачи", out)
        self.assertIn("SPEC.md", out)

    def test_review_refuses_when_branch_exists_without_review_md(self):
        # REVIEW.md `cmd_new` не пишет вовсе (только SPEC.md/TZ.md,
        # требования 2-3) — ветка и без порчи уже без него.
        self.set_state("review")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review")
        self.assertIn("дерево не на ветке задачи", out)
        self.assertIn("REVIEW.md", out)


# ---------------------------------------------------------------------
# Guard видит ТОТ ЖЕ текст, что определил статус (ветка), не второе
# чтение с диска — той же гарантией, что PLAN.md получил в T031.

BROKEN_SPEC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: сломанная структура

Без обязательных секций — guard.py обязан отказать, если прочитает
именно ЭТОТ текст.
"""


class GuardSeesBranchContentNotDiskTest(RealGitBranchTest):

    def test_broken_main_commit_does_not_block_a_valid_branch_spec(self):
        # main получает СВОЙ SPEC.md, закоммиченный прямо в main
        # (устаревший, structurally сломанный — guard бы отказал, если
        # бы читал его); ветка задачи — СВОЙ, валидный.
        self.write("SPEC.md", BROKEN_SPEC)
        self.commit_task_dir("сломанный SPEC.md — закоммичен прямо в main")
        self.write_on_task_branch("SPEC.md", SPEC_READY)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "spec_gate",
            f"guard обязан был проверить текст ВЕТКИ (валидный), не "
            f"закоммиченный на main (сломанный): {out}")


# ---------------------------------------------------------------------
# git не отвечает на сам вопрос «есть ли QUESTIONS.md» (ls-tree) — тоже
# именованный отказ, не молчаливое «эскалации нет».

class QuestionsLsTreeFailureTest(RealGitBranchTest):

    def test_ls_tree_failure_refuses_the_transition(self):
        self.write_on_task_branch("SPEC.md", SPEC_READY)
        with mock.patch.object(gitcmd, "ls_tree_files",
                               side_effect=lambda *a, **k: None):
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "spec_writing")
        self.assertIn("не удалось проверить наличие QUESTIONS.md", out)


if __name__ == "__main__":
    unittest.main()
