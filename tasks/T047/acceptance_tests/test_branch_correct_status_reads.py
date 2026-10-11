"""Приёмочные тесты T047: ветко-корректные чтения статусов SPEC.md и
REVIEW.md на переходах `spec_writing -> spec_gate` и `review ->
acceptance/in_dev` (tasks/T047/SPEC.md, критерии AC-1..AC-6).

Песочница с настоящим git (`RealGitBranchTest`) — тот же приём, что
`RealGitBranchTest` в tasks/T031/acceptance_tests/test_branch_correct_reads.py:
только настоящий git воспроизводит класс дефекта (T030/T031) — рабочее
дерево пульта стоит на main, пока артефакт задачи закоммичен только на
ВЕТКЕ задачи (журнал T046 27.08.2026, T045 27.08.2026, SPEC «Контекст»).

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002): этот модуль кодирует новые пункты
инварианта 28 реестра (docs/invariants.md) — его отключение или
ослабление допустимо только Оператором отдельным ADR.
"""
import contextlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import catalog, config, fsm, gitcmd, store  # noqa: E402
from orchestrator import workspace  # noqa: E402
from tests.sandbox import fake_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: маркер-содержимого-ветки-задачи-t047

## Контекст

Этот SPEC.md со статусом `ready` существует ТОЛЬКО на ветке задачи из
песочницы теста — если чтение статуса не ветко-корректно, рабочее
дерево на main его не увидит.

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий фиктивной задачи.
AC-2. Второй критерий фиктивной задачи.

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

# REVIEW: маркер-содержимого-ветки-задачи-t047

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания

- ...

## Вердикт

approved

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный (фикстура; секция
обязательна для approved с T072 — дочинено Оператором 01.09, ANSWER T085).
"""

REVIEW_CHANGES_REQUESTED = """---
task: {task}
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 2
---

# REVIEW: маркер-содержимого-ветки-задачи-t047

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | FAIL | почини X |

## Замечания

- почини X

## Вердикт

changes_requested
"""


class RealGitBranchTest(unittest.TestCase):
    """ROOT — свежий репозиторий с веткой main и заведённой задачей (id —
    ULID, SPEC T094 требование 2: `self.TASK` заполняется РЕАЛЬНЫМ
    возвратом `cmd_new` в `setUp`, не литералом `T001`); ветка задачи
    создаётся ролью (`git checkout -b`) уже после `cmd_new`, как в
    реальном флоу — до этого момента она попросту не существует в git
    (легитимный ранний момент жизни задачи, ADR-0003 3д)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
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
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("WORKTREES", self.root / ".artel" / "worktrees")):
            self.patches.enter_context(mock.patch.object(config, attr, value))

        self.capture(catalog.cmd_init)
        with redirect_stdout(io.StringIO()):
            self.TASK = catalog.cmd_new("Ветко-корректные чтения статусов")
        self.tdir = config.TASKS / self.TASK
        self.branch = store.get_task(store.db(), self.TASK)["branch"]

    # -- git/процесс -------------------------------------------------

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
        """Переключает чекаут `self.root`. `cmd_new` (T048) уже завела
        РЕАЛЬНЫЙ linked worktree на `self.branch` (`workspace.ensure`) —
        git не даёт держать одну ветку разом в `self.root` и в linked
        worktree, так что заход НА `self.branch` сначала убирает
        воркдерево, а уход с неё — восстанавливает (тот же приём, что
        tasks/T031/acceptance_tests/test_branch_correct_reads.py
        `RealGitBranchTest.checkout`)."""
        if branch == self.branch:
            self.capture(workspace.remove, self.TASK)
        args = ["checkout", "-q"]
        if create:
            args.append("-b")
        args.append(branch)
        self.git(*args)
        if branch != self.branch:
            workspace.ensure(self.TASK, self.branch)

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

    # -- артефакты -------------------------------------------------

    def commit_task_dir(self, message: str = "артефакт") -> None:
        self.git("add", f"tasks/{self.TASK}")
        self.git("commit", "-q", "-m", message)

    def write(self, name: str, template: str) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(template.format(task=self.TASK),
                                      encoding="utf-8")

    def write_on_task_branch(self, name: str, template: str) -> None:
        """Артефакт коммитится на ВЕТКЕ задачи, рабочее дерево пульта
        остаётся на main (SPEC «Контекст», журнал T046/T045 27.08.2026):
        реалистичный расклад — до merge_gate ветка задачи в main не
        мержится (ADR-0003). Ветка `self.branch` уже существует (её
        завёл `cmd_new`/`workspace.ensure` в setUp) — без `create=True`,
        иначе git отказал бы «уже существует»."""
        self.checkout(self.branch)
        self.write(name, template)
        self.commit_task_dir(f"{name} задачи")
        self.checkout(config.MAIN_BRANCH)


# ---------------------------------------------------------------------
# AC-1: spec_writing -> spec_gate без ручного чекаута, статус SPEC.md
# закоммичен только на ветке задачи.

class SpecWritingBranchRoutingTest(RealGitBranchTest):

    def test_ac1_ready_spec_on_task_branch_advances_without_manual_checkout(self):
        self.write_on_task_branch("SPEC.md", SPEC_READY)
        self.assertEqual(
            gitcmd.current_branch(), config.MAIN_BRANCH,
            "подготовка теста не удалась: рабочее дерево обязано остаться "
            "на main")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "spec_gate",
            "рабочее дерево пульта на main, SPEC.md со статусом ready "
            "закоммичен только на ветке задачи — advance обязан перевести "
            "spec_writing -> spec_gate без ручного чекаута Оператора "
            "(SPEC T047 AC-1)")


# ---------------------------------------------------------------------
# AC-2: review -> acceptance/in_dev по вердикту REVIEW.md, закоммиченному
# только на ветке задачи, без ручного чекаута.

class ReviewBranchRoutingTest(RealGitBranchTest):

    def test_ac2_approved_verdict_on_task_branch_advances_to_acceptance(self):
        """SPEC T079, требование 4 СУПЕРСЕДИРУЕТ буквальный «в acceptance»
        этого имени (имя сохранено байт-в-байт — прецедент AC-7/T031:
        тестовый метод не исчезает без ADR): `review -> acceptance`
        обзавёлся промежуточным `verifying` (ожидание зелёного CI головы
        ветки) — тело проверяет актуальный первый шаг того же
        branch-корректного маршрута."""
        self.write_on_task_branch("REVIEW.md", REVIEW_APPROVED)
        self.set_state("review")
        self.assertEqual(
            gitcmd.current_branch(), config.MAIN_BRANCH,
            "подготовка теста не удалась: рабочее дерево обязано остаться "
            "на main")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "рабочее дерево пульта на main, вердикт REVIEW.md (approved, "
            "iteration=1) закоммичен только на ветке задачи — advance "
            "обязан перевести review -> verifying по вердикту без "
            "ручного чекаута Оператора (SPEC T047 AC-2, SPEC T079 "
            "требование 4)")

    def test_ac2_changes_requested_verdict_on_task_branch_advances_to_in_dev(self):
        self.write_on_task_branch("REVIEW.md", REVIEW_CHANGES_REQUESTED)
        self.set_state("review")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "in_dev",
            "рабочее дерево пульта на main, вердикт REVIEW.md "
            "(changes_requested, iteration=1) закоммичен только на ветке "
            "задачи — advance обязан перевести review -> in_dev по "
            "вердикту без ручного чекаута Оператора (SPEC T047 AC-2)")


# ---------------------------------------------------------------------
# AC-3: прежнее поведение без git и без ветки задачи не меняется — тот же
# паттерн деградации, что и в существующих ветко-корректных местах
# (SPEC, требование 5).

class NoTaskBranchDegradationTest(RealGitBranchTest):
    """Настоящий git; сценарий «ветки задачи ещё нет» — с T045 `cmd_new`
    заводит worktree/ветку сразу (`workspace.ensure`, `_new_dogfood`),
    естественного раннего момента жизни задачи без ветки (ADR-0003 3д,
    как было до T045) больше не бывает — `setUp` ниже ВОСПРОИЗВОДИТ его
    явным удалением: `on_foreign_branch` обязан деградировать в прежний
    путь чтения с диска одинаково, естественно ветки нет или она удалена
    явно — с точки зрения проверяемого кода разницы нет."""

    def setUp(self):
        super().setUp()
        self.capture(workspace.remove, self.TASK)
        self.git("branch", "-D", self.branch)

    def test_ac3_spec_writing_transition_unaffected_without_task_branch(self):
        self.assertFalse(
            gitcmd.branch_exists(self.branch),
            "подготовка теста не удалась: ветка задачи не должна "
            "существовать в git до этого сценария")
        # Коммит прямо на main (ветки задачи ещё нет — роль коммитит на
        # том, что выписано; иначе _dirty_refuses отклонил бы переход по
        # незакоммиченной копии, не по существу этого сценария).
        self.write("SPEC.md", SPEC_READY)
        self.commit_task_dir("SPEC.md на main — ветки задачи ещё нет")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "spec_gate",
            "ветка задачи ещё не создана в git — spec_writing -> "
            "spec_gate обязан работать прежним способом (чтение с диска), "
            "как до T047 (SPEC, требование 5, AC-3)")

    def test_ac3_review_transition_unaffected_without_task_branch(self):
        """SPEC T079, требование 4 СУПЕРСЕДИРУЕТ буквальный «в acceptance»
        (см. тот же класс адаптации в `ReviewBranchRoutingTest.
        test_ac2_approved_verdict_on_task_branch_advances_to_acceptance`
        выше) — `verifying` вставлен между `review` и `acceptance`."""
        self.write("REVIEW.md", REVIEW_APPROVED)
        self.commit_task_dir("REVIEW.md на main — ветки задачи ещё нет")
        self.set_state("review")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "ветка задачи ещё не создана в git — review -> verifying "
            "обязан работать прежним способом (чтение с диска), как до "
            "T047 (SPEC, требование 5, AC-3; SPEC T079 требование 4)")


class NoGitDegradationTest(unittest.TestCase):
    """Песочница вовсе без РЕАЛЬНОГО git-репозитория (`gitcmd.git`
    подменена лёгкой общей заглушкой `tests.sandbox.fake_git` — тот же
    приём, что `tests/test_advance_guard.py`, SPEC T045/T048: `cmd_new`
    заводит worktree/ветку плотницки поверх заглушки, полный отказ
    git (`lambda *a: None`) роняет `cmd_new` уже в `setUp`, до сценария,
    который тест проверяет) — сценарий «песочницы без git» из
    требования 5: `gitcmd.on_foreign_branch` здесь всегда `False`
    (`current_branch()` в заглушке пуста), branch-корректные чтения
    обязаны деградировать к чтению с диска. `config.ROOT` не
    подменяется: `catalog.cmd_new` читает реальный `templates/SPEC.md`
    этого репозитория, как и в `test_advance_guard.py`. `self.TASK` —
    реальный возврат `cmd_new` (SPEC T094 требование 2: id — ULID, не
    предсказуемый литерал)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            self.patches.enter_context(mock.patch.object(config, attr, value))
        self.patches.enter_context(
            mock.patch.object(gitcmd, "git", fake_git))

        self.capture(catalog.cmd_init)
        with redirect_stdout(io.StringIO()):
            self.TASK = catalog.cmd_new("Ветко-корректные чтения без git")
        self.tdir = config.TASKS / self.TASK

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write(self, name: str, template: str) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(template.format(task=self.TASK),
                                      encoding="utf-8")

    def test_ac3_spec_writing_transition_unaffected_without_git(self):
        self.write("SPEC.md", SPEC_READY)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "spec_gate",
            "песочница без git (`gitcmd.git` не отвечает) — spec_writing "
            "-> spec_gate обязан работать прежним способом (чтение с "
            "диска), как до T047 (SPEC, требование 5, AC-3)")

    def test_ac3_review_transition_unaffected_without_git(self):
        """SPEC T079, требование 4 СУПЕРСЕДИРУЕТ буквальный «в acceptance»
        (тот же класс адаптации, что `ReviewBranchRoutingTest` выше)."""
        self.write("REVIEW.md", REVIEW_APPROVED)
        self.set_state("review")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "песочница без git (`gitcmd.git` — лёгкая заглушка без "
            "реального репозитория) — review -> verifying обязан "
            "работать прежним способом (чтение с диска), как до T047 "
            "(SPEC, требование 5, AC-3; SPEC T079 требование 4)")


# ---------------------------------------------------------------------
# AC-4: PLAN перечисляет все проверенные места чтений статусов/
# фронтматтеров артефактов на переходах FSM и найденные экземпляры класса
# «артефакто-чтения ветко-зависимы» (SPEC, требование 3 — включая явно
# упомянутые `fresh_verdict_iteration` и чтение QUESTIONS.md в
# spec_writing). PLAN.md появится только на выходе роли developer из
# in_dev — на момент авторства этих тестов файла ещё нет, что нормально
# (test-authoring: «падать на отсутствующей пока реализации — нормально»).

class PlanEnumeratesAuditedPlacesTest(unittest.TestCase):

    PLAN_PATH = REPO_ROOT / "tasks" / "T047" / "PLAN.md"

    def _text(self) -> str:
        self.assertTrue(
            self.PLAN_PATH.exists(),
            f"{self.PLAN_PATH} отсутствует — PLAN обязан перечислить все "
            f"проверенные по требованию 3 места чтений (SPEC T047 AC-4)")
        return self.PLAN_PATH.read_text(encoding="utf-8")

    def test_ac4_plan_mentions_fresh_verdict_iteration(self):
        text = self._text()
        self.assertIn(
            "fresh_verdict_iteration", text,
            "PLAN обязан упомянуть проверку `fresh_verdict_iteration` — "
            "явно названное требованием 3 место, подлежащее проверке на "
            "принадлежность классу «артефакто-чтения ветко-зависимы» "
            "(SPEC T047 AC-4)")

    def test_ac4_plan_mentions_questions_md_in_spec_writing(self):
        text = self._text()
        self.assertIn(
            "QUESTIONS.md", text,
            "PLAN обязан упомянуть чтение QUESTIONS.md в состоянии "
            "spec_writing — явно названное требованием 3 место (SPEC "
            "T047 AC-4)")

    def test_ac4_plan_mentions_both_audited_modules(self):
        text = self._text()
        self.assertIn(
            "fsm.py", text,
            "PLAN обязан назвать orchestrator/fsm.py среди проверенных "
            "по требованию 3 читателей артефактов (SPEC T047 AC-4)")
        self.assertIn(
            "artifacts.py", text,
            "PLAN обязан назвать orchestrator/artifacts.py среди "
            "проверенных по требованию 3 читателей артефактов (SPEC "
            "T047 AC-4)")


# AC-5: manual — критерий уже покрыт `.github/workflows/ci.yml` (шаг
# `unittest discover -s tests`, обязательный статус-чек ветки и условие
# merge_gate, orchestrator/fsm.py `_cmd_approve` при state == "merge_gate"
# через `ci.branch_status`): полный набор тестов зелёный — то, что
# проверяет штатный CI-гейт на каждом коммите ветки, а не отдельный
# unittest этого набора (тем же основанием, что AC-4/AC-5 в
# tasks/T037,T040,T041,T042 — сформулированы идентично).
# AC-5: manual — «полный набор тестов зелёный» уже проверяет штатный
# CI-гейт (.github/workflows/ci.yml) и merge_gate; дублирующий прогон
# здесь не даёт новой гарантии.


# ---------------------------------------------------------------------
# AC-6: docs/invariants.md — защищённый путь (SPEC «Не входит»): диф для
# Оператора приложен к PLAN.md, ветка задачи сам файл не трогает (тот же
# приём, что tasks/T046/acceptance_tests/test_predlozheniya_sisteme.py,
# `ProtectedPathsTest`).

DIFF_TARGET_RE = re.compile(
    r"(?:diff --git |--- |\+\+\+ |\*\*\* )(?:a/|b/)?(docs/invariants\.md)")


class ProtectedInvariantsPathTest(unittest.TestCase):

    @staticmethod
    def _git(*args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()

    def test_ac6_branch_diff_does_not_touch_docs_invariants_directly(self):
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch == "main":
            self.skipTest("рабочее дерево на main — диффить не с чем")
        merge_base = self._git("merge-base", "main", branch)
        changed = self._git("diff", "--name-only", merge_base,
                            branch).splitlines()
        self.assertNotIn(
            "docs/invariants.md", changed,
            "дифф ветки относительно main трогает docs/invariants.md "
            "напрямую — SPEC («Не входит») требует подготовленный дифф "
            "в PLAN.md, не прямой коммит агента (SPEC T047 AC-6)")

    def test_ac6_plan_attaches_diff_for_invariant_28(self):
        plan_path = REPO_ROOT / "tasks" / "T047" / "PLAN.md"
        self.assertTrue(
            plan_path.exists(),
            f"{plan_path} отсутствует — SPEC требует приложить к нему "
            f"подготовленный дифф правки docs/invariants.md (SPEC T047 "
            f"AC-6)")
        text = plan_path.read_text(encoding="utf-8")

        targets = set(DIFF_TARGET_RE.findall(text))
        self.assertIn(
            "docs/invariants.md", targets,
            "PLAN.md не содержит диффа для docs/invariants.md (ожидаются "
            "маркеры унифицированного диффа: 'diff --git', '--- ', "
            "'+++ ' с путём docs/invariants.md) — SPEC T047 AC-6")
        self.assertIn(
            "28", text,
            "PLAN.md не упоминает номер инварианта 28, который правка "
            "обязана дополнить новыми местами (SPEC T047 AC-6)")
        lowered = text.lower()
        self.assertIn(
            "оператор", lowered,
            "PLAN.md не упоминает Оператора — правку docs/invariants.md "
            "коммитит только он (SPEC T047 AC-6, SPEC «Не входит»)")


if __name__ == "__main__":
    unittest.main()
