"""Приёмочные тесты T071: ветко-корректное чтение SPEC.md на переходе
`spec_gate` внутри `_cmd_approve` идёт через общий узел
`_read_branch_text_or_refuse` (T047), а не через прямой `gitcmd.show`
(tasks/T071/SPEC.md, критерии AC-1..AC-5).

Красен до реализации: до правки `_cmd_approve` (orchestrator/fsm.py,
ветка `spec_gate`, ~1091-1101) по-прежнему вызывает `gitcmd.show`
напрямую вместо `_read_branch_text_or_refuse` — `AC1SharedNodeCalledTest`
и `AC4NoDirectGitcmdShowTest` падают на этом (узел не вызван / прямой
вызов найден статически). `AC2RefusalStopsApproveTest` и
`AC3BranchCorrectReadTest` зелёные уже сейчас: наблюдаемое поведение
(отказ без смены состояния, чтение с ветки) обеспечивает прежний
inline-код, правка его не меняет (SPEC, требование 2/3) — эти два теста
фиксируют регресс, если правка случайно изменит решения FSM.

Песочница с настоящим git и настоящим worktree задачи (`RealGitTaskTest`)
— пост-T045/T069 приём (`catalog.cmd_new` заводит SPEC.md/TZ.md СРАЗУ в
ветку задачи через `workspace.ensure`, отдельный linked worktree —
`config.WORKTREES/<task>`, не чекаут ветки в основной рабочей копии), тот
же приём, что `CanarySandbox`/`SmartAgent._commit` в
`tasks/T065/acceptance_tests/_sandbox.py`: артефакты коммитятся файловой
записью + `git add`/`git commit` внутри linked worktree, рабочая копия
пульта (`self.root`) остаётся на main на протяжении всего теста —
`gitcmd.on_foreign_branch(branch)` истинно с рождения задачи, без
дополнительных ручных чекаутов (устаревший приём `checkout -b` в main,
использованный tasks/T031 и tasks/T047, конфликтует с уже
зарегистрированным linked worktree той же ветки и здесь не годится).

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002): этот модуль кодирует ветко-корректное
чтение для последнего непереведённого узлом T047 читателя (инвариант 28
реестра, docs/invariants.md) — его отключение или ослабление допустимо
только Оператором отдельным ADR.
"""
import ast
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import catalog, config, fixation, fsm, gitcmd, store  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: маркер-содержимого-ветки-задачи-t071

## Контекст

Этот SPEC.md со статусом `ready` (schema_version 2, AC-разметка, без
skip_tests) существует ТОЛЬКО на ветке задачи из песочницы теста — если
чтение не ветко-корректно, рабочее дерево на main его не увидит и
решение FSM разойдётся (шаблонный SPEC.md, который `cmd_new` кладёт на
диск main-worktree пульта, не несёт ни `status: ready`, ни
`schema_version: 2`).

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий фиктивной задачи.
AC-2. Второй критерий фиктивной задачи.

## Не входит
"""


class RealGitTaskTest(unittest.TestCase):
    """ROOT — свежий репозиторий с веткой main; `catalog.cmd_new` тем же
    путём, что и живой пульт, заводит T001 в её СОБСТВЕННОМ linked
    worktree (`config.WORKTREES/T001`) на её же ветке — рабочая копия
    `self.root` остаётся на main всё время сценария."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        import shutil
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        gitignore = REPO_ROOT / ".gitignore"
        if gitignore.exists():
            shutil.copy(gitignore, self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("WORKTREES", self.root / ".artel" / "worktrees")):
            self.patches.enter_context(mock.patch.object(config, attr, value))

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Ветко-корректное чтение SPEC в approve")
        self.branch = store.get_task(store.db(), self.TASK)["branch"]
        self.wt_path = config.WORKTREES / self.TASK

    # -- git/процесс -------------------------------------------------

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def git_in_worktree(self, *args: str) -> None:
        res = gitcmd.in_repo(self.wt_path, *args)
        self.assertTrue(
            res is not None and res.returncode == 0,
            f"git -C {self.wt_path} {' '.join(args)}: "
            f"{res.stderr if res is not None else '— git не ответил'}")

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    # -- задача / состояние -------------------------------------------

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def journal_all(self) -> list[str]:
        return [f"{r['action']}: {r['detail']}"
               for r in store.task_steps(store.db(), self.TASK)]

    # -- артефакты на ветке задачи (linked worktree) -------------------

    def commit_in_worktree(self, message: str) -> None:
        self.git_in_worktree("-c", f"user.name={fixation.FIXATION_AUTHOR_NAME}",
                             "-c", f"user.email={fixation.FIXATION_AUTHOR_EMAIL}",
                             "commit", "-q", "-m", message)

    def write_spec_ready_on_task_branch(self) -> None:
        """Перезаписывает шаблонный SPEC.md (который `cmd_new` уже
        закоммитил) на v2/ready/AC-размеченный, новым коммитом ветки
        задачи в её linked worktree."""
        spec_path = self.wt_path / "tasks" / self.TASK / "SPEC.md"
        spec_path.write_text(SPEC_READY.format(task=self.TASK), encoding="utf-8")
        self.git_in_worktree("add", f"tasks/{self.TASK}/SPEC.md")
        self.commit_in_worktree("SPEC.md ready задачи")

    def remove_spec_from_task_branch(self) -> None:
        """Убирает SPEC.md с ветки задачи новым коммитом — воспроизводит
        отказ узла (файл не найден на ветке), не отсутствие самой ветки
        (AC-2 сценарий)."""
        self.git_in_worktree("rm", "-q", f"tasks/{self.TASK}/SPEC.md")
        self.commit_in_worktree("убрать SPEC.md (тест AC-2)")


# ---------------------------------------------------------------------
# AC-1: чтение SPEC.md в spec_gate идёт через общий узел
# `_read_branch_text_or_refuse`, а не через прямой `gitcmd.show`.

class AC1SharedNodeCalledTest(RealGitTaskTest):

    def test_ac1_spec_gate_uses_shared_node_when_on_foreign_branch(self):
        self.set_state("spec_gate")
        self.assertTrue(
            gitcmd.on_foreign_branch(self.branch),
            "подготовка теста не удалась: рабочее дерево пульта обязано "
            "стоять не на ветке задачи (linked worktree её держит "
            "отдельно), а ветка задачи обязана существовать")

        fake_text = SPEC_READY.format(task=self.TASK)
        with mock.patch.object(
                fsm, "_read_branch_text_or_refuse",
                return_value=fake_text) as node_spy, \
             mock.patch.object(
                fsm.gitcmd, "show",
                return_value=(None, "AC-1: gitcmd.show вызван напрямую, "
                             "минуя общий узел")) as show_spy, \
             mock.patch.object(fsm, "confirm_fixation", return_value=True):
            # Пока код зовёт gitcmd.show напрямую (до правки AC-1), это
            # заканчивается именованным отказом approve (SystemExit) —
            # он здесь не по существу теста, ловим его, чтобы дойти до
            # диагностичных assert'ов ниже, а не до сырого краша.
            try:
                self.capture(fsm.cmd_approve, self.TASK)
            except SystemExit:
                pass

        node_spy.assert_called_once_with(
            mock.ANY, self.TASK, self.branch, "SPEC.md")
        show_spy.assert_not_called()


# ---------------------------------------------------------------------
# AC-2: при отказе узла approve останавливает попытку именованным
# отказом и не переводит задачу в другое состояние.

class AC2RefusalStopsApproveTest(RealGitTaskTest):

    def test_ac2_node_refusal_stops_approve_without_state_change(self):
        self.remove_spec_from_task_branch()
        self.set_state("spec_gate")
        self.assertTrue(
            gitcmd.on_foreign_branch(self.branch),
            "подготовка теста не удалась: рабочее дерево пульта обязано "
            "стоять не на ветке задачи, а ветка задачи обязана "
            "существовать")

        refusal_text = ""
        with mock.patch.object(fsm, "confirm_fixation", return_value=True):
            try:
                self.capture(fsm.cmd_approve, self.TASK)
            except SystemExit as exc:
                refusal_text = str(exc)

        self.assertEqual(
            self.state(), "spec_gate",
            "отказ узла (SPEC.md ветки не прочитан — на ветке нет файла) "
            "обязан оставить задачу в spec_gate: approve не переводит "
            "задачу в другое состояние при отказе (SPEC T071 AC-2)")

        journal = " ".join(self.journal_all()).lower()
        combined = (refusal_text + " " + journal).lower()
        self.assertTrue(
            "ветк" in combined or "не прочитан" in combined,
            "отказ обязан быть именованным — упоминать причину «дерево "
            "не на ветке задачи» либо «SPEC.md ... не прочитан», в "
            "сообщении SystemExit или в журнале задачи (SPEC T071 AC-2)")


# ---------------------------------------------------------------------
# AC-3: сценарий «SPEC.md перехода approve/spec_gate читается с ветки
# задачи, а не с диска рабочей копии» покрыт тестом (по образцу T047).

class AC3BranchCorrectReadTest(RealGitTaskTest):

    def test_ac3_spec_gate_approve_reads_spec_from_task_branch_not_worktree(self):
        self.write_spec_ready_on_task_branch()
        self.set_state("spec_gate")
        self.assertEqual(
            gitcmd.current_branch(), config.MAIN_BRANCH,
            "подготовка теста не удалась: рабочее дерево пульта обязано "
            "остаться на main")
        disk_spec = (config.TASKS / self.TASK / "SPEC.md")
        self.assertFalse(
            disk_spec.exists(),
            "подготовка теста не удалась: SPEC.md на диске main-рабочей "
            "копии пульта (config.TASKS) не должен существовать — "
            "cmd_new писал его только в linked worktree ветки задачи")

        with mock.patch.object(fsm, "confirm_fixation", return_value=True):
            self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(
            self.state(), "tests_writing",
            "рабочее дерево пульта на main (SPEC.md там вовсе не "
            "существует), SPEC.md ready/schema_version 2/AC-размеченный "
            "закоммичен только на ветке задачи — approve обязан "
            "прочитать его С ВЕТКИ и перевести spec_gate -> tests_writing "
            "без ручного чекаута Оператора (SPEC T071 AC-3)")


# ---------------------------------------------------------------------
# AC-4: после правки чтение SPEC.md на переходе spec_gate нигде не
# обращается к gitcmd.show в обход `_read_branch_text_or_refuse`
# (статическая проверка AST функции `_cmd_approve`).

class AC4NoDirectGitcmdShowTest(unittest.TestCase):

    def test_ac4_cmd_approve_does_not_call_gitcmd_show_directly(self):
        source = (REPO_ROOT / "orchestrator" / "fsm.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source)
        func = next(
            (node for node in ast.walk(tree)
             if isinstance(node, ast.FunctionDef) and node.name == "_cmd_approve"),
            None)
        self.assertIsNotNone(
            func, "_cmd_approve не найден в orchestrator/fsm.py")

        direct_show_calls = [
            node for node in ast.walk(func)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "show"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "gitcmd"
        ]
        self.assertEqual(
            direct_show_calls, [],
            "_cmd_approve по-прежнему вызывает gitcmd.show напрямую — "
            "чтение SPEC.md на переходе spec_gate обязано идти только "
            "через общий узел _read_branch_text_or_refuse, без обхода "
            "(SPEC T071 AC-4)")


# AC-5: manual — критерий уже покрыт `.github/workflows/ci.yml` (шаг
# `unittest discover -s tests`, обязательный статус-чек ветки и условие
# merge_gate, orchestrator/fsm.py `_cmd_approve` при state == "merge_gate"
# через `ci.branch_status`): полный набор тестов зелёный — то, что
# проверяет штатный CI-гейт на каждом коммите ветки, а не отдельный
# unittest этого набора (то же основание, что AC-5 в
# tasks/T047/acceptance_tests/test_branch_correct_status_reads.py).


if __name__ == "__main__":
    unittest.main()
