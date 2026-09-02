"""Приёмочные тесты T031: ветко-корректные чтения артефактов задачи
(tasks/T031/SPEC.md, критерии AC-1–AC-7).

Классы названы по критериям SPEC. Песочница — реальный git-репозиторий
(`RealGitBranchTest`, тот же приём, что `RealPultGitTest` в
tests/test_git_fixation.py и `LockTest` в tests/test_acceptance_tests_flow.py):
только настоящий git воспроизводит класс дефекта, который вскрыла
контрольная задача T030 — рабочее дерево пульта «съезжает» на ветку
ДРУГОЙ задачи (здесь — `OTHER_BRANCH`, по образцу `task/t029-...` из
журнала T030), пока текущая задача читается по путям на диске, будто
дерево всё ещё стоит на её собственной ветке.

AC-1 тестируется с замоканным `fsm.confirm_fixation`: гейт approve
по sha (SPEC T021) — независимый от AC-1 критерий (AC-4 этой же
задачи); не изолировав его, тест AC-1 стал бы заложником состояния
починки AC-4 в одну или другую сторону, а не проверял бы маршрутизацию
spec_gate саму по себе.

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002): этот модуль (end-to-end по каждому
месту чтения) кодирует инвариант 28 реестра (docs/invariants.md) — его
отключение или ослабление допустимо только Оператором отдельным ADR.
"""
import contextlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import brief, catalog, config, fixation, fsm, store  # noqa: E402
from orchestrator import runner, workspace  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SPEC_V2 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: маркер-содержимого-ветки-задачи-t031

## Контекст

Этот SPEC.md существует ТОЛЬКО на ветке задачи из песочницы теста —
если он виден при чекауте другой ветки, чтение не ветко-корректно.

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий фиктивной задачи, проверяемый тестом.
AC-2. Второй критерий фиктивной задачи, проверяемый тестом или пометкой.

## Не входит
"""

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: фиктивная задача песочницы

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

AC_TEST_BOTH_COVERED = """\"\"\"Зелёный с рождения: фикстура T031, обе критерии проверены сразу.\"\"\"
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac2_second_criterion(self):
        self.assertEqual(1 + 1, 2)
"""


class RealGitBranchTest(unittest.TestCase):
    """Песочница с настоящим git: ROOT — свежий репозиторий с веткой main
    и заведённой задачей (id — ULID, SPEC T094 требование 2: `self.TASK`
    заполняется РЕАЛЬНЫМ возвратом `cmd_new` в `setUp`, не литералом);
    `OTHER_BRANCH` существует с самого начала (тот же коммит, что main на
    момент создания задачи) и воспроизводит чужую ветку, на которую
    «съехало» рабочее дерево (журнал T030)."""

    OTHER_BRANCH = "task/t029-drugaya-zadacha"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        # Бриф роли developer читает docs/codebase-map.md и CLAUDE.md из
        # config.ROOT (T028) — без них сборка брифа падает ДО того места,
        # которое проверяет AC-2.
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: " + "0" * 40 + "\n---\n\n# Карта\n",
            encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("PROJECTS", self.root / ".artel" / "projects"),
                            ("ROLE_HOME", self.root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             self.root / ".artel" / "home" / ".claude"),
                            ("WORKTREES", self.root / ".artel" / "worktrees"),
                            ("TARGETS", self.root / "targets.yaml")):
            self.patches.enter_context(mock.patch.object(config, attr, value))
        self.patches.enter_context(mock.patch.object(
            runner.keychain, "token", lambda slot: "tok-test"))
        self.patches.enter_context(mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: []))

        self.capture(catalog.cmd_init)
        with contextlib.redirect_stdout(io.StringIO()):
            self.TASK = catalog.cmd_new("Ветко-корректные чтения")
        self.tdir = config.TASKS / self.TASK
        self.branch = store.get_task(store.db(), self.TASK)["branch"]

        # Чужая ветка задачи T029 уже существует на этом же (раннем)
        # коммите — до того, как на ветку задачи попадёт хоть один
        # артефакт T001.
        self.git("branch", self.OTHER_BRANCH)

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

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def checkout(self, branch: str, create: bool = False) -> None:
        """Переключает чекаут `self.root` (однодеревная модель этого теста,
        старше T045). `cmd_new` (T048) заводит РЕАЛЬНЫЙ linked worktree на
        `self.branch` — git не даёт держать одну ветку разом в `self.root`
        и в linked worktree, так что заход НА `self.branch` сначала убирает
        воркдерево (`workspace.remove`), а уход С нея — восстанавливает его
        (`workspace.ensure`): AC-4 читает «чужой» чекаут именно через
        `workspace.path` (`fixation._fix_dogfood`), ему нужно, чтобы
        воркдерево задачи было на месте, когда `self.root` смотрит в другую
        сторону."""
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

    def write_acceptance_tests(self, content: str,
                               name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def prepare_ready_spec_on_task_branch(self) -> None:
        """SPEC.md v2 с AC-разметкой, ready, закоммичен на ветке задачи —
        главный сценарий: артефакт существует ТОЛЬКО там, main/чужая ветка
        его не видят (реалистично: до merge_gate ветка задачи не мержится
        в main, ADR-0003). Ветка `self.branch` уже существует (её завёл
        `cmd_new` в setUp) — без `-b`, иначе git отказал бы «уже
        существует»."""
        self.checkout(self.branch)
        self.write("SPEC.md", SPEC_V2)
        self.commit_task_dir("SPEC.md ready")


# ---------------------------------------------------------------------
# AC-1: маршрутизация spec_gate.

class SpecGateBranchRoutingTest(RealGitBranchTest):

    def test_ac1_checkout_on_foreign_branch_does_not_silently_skip_tests_writing(self):
        self.prepare_ready_spec_on_task_branch()
        # Рабочее дерево «съехало» на ветку ДРУГОЙ задачи — класс
        # инцидента из журнала T030 (SPEC, «Контекст»).
        self.checkout(self.OTHER_BRANCH)
        self.set_state("spec_gate")

        # Гейт approve-по-sha (AC-4) изолирован: AC-1 проверяет только
        # маршрутизацию spec_gate, не сверку sha.
        with mock.patch.object(fsm, "confirm_fixation", return_value=True):
            self.capture(fsm.cmd_approve, self.TASK)

        state = self.state()
        self.assertNotEqual(
            state, "in_dev",
            "рабочее дерево не на ветке задачи — spec_gate не имеет права "
            "молчаливо трактовать недоступный на текущей ветке SPEC.md как "
            "schema_version 1 без AC-разметки и пропускать tests_writing "
            "(SPEC AC-1)")
        if state == "spec_gate":
            journal = " ".join(self.journal_all()).lower()
            self.assertIn(
                "ветк", journal,
                "явный отказ обязан назвать причину «дерево не на ветке "
                "задачи» и попасть в журнал задачи (SPEC AC-1, AC-5)")
        else:
            self.assertEqual(state, "tests_writing")


# ---------------------------------------------------------------------
# AC-2: сборка брифа роли.

class BriefBuildBranchTest(RealGitBranchTest):

    def test_ac2_brief_build_does_not_crash_with_bare_filenotfound(self):
        self.prepare_ready_spec_on_task_branch()
        self.checkout(self.OTHER_BRANCH)
        conn = store.db()

        try:
            text = brief.developer_brief(conn, self.TASK)
        except FileNotFoundError:
            self.fail(
                "сборка брифа упала голым FileNotFoundError-трейсбеком — "
                "SPEC.md недоступен на текущей ветке; отказ обязан быть "
                "именованным «дерево не на ветке задачи», не падением "
                "(SPEC AC-2)")
        except SystemExit as exc:
            self.assertIn(
                "ветк", str(exc).lower(),
                "именованный отказ обязан называть причину — «дерево не на "
                "ветке задачи» (SPEC AC-2)")
            return
        self.assertIn(
            "маркер-содержимого-ветки-задачи-t031", text,
            "бриф обязан нести SPEC.md ветки задачи, а не молчать о том, "
            "что он его не нашёл")


# ---------------------------------------------------------------------
# AC-3: трассируемость AC (tests_writing -> in_dev) и лок acceptance_tests/
# (in_dev -> review) — обе проверки не зависят от чекаута.

class TraceabilityBranchTest(RealGitBranchTest):

    def _enter_tests_writing_with_complete_coverage_on_branch(self) -> None:
        self.prepare_ready_spec_on_task_branch()
        self.write_acceptance_tests(AC_TEST_BOTH_COVERED)
        self.commit_task_dir("acceptance_tests от test_author")
        self.set_state("tests_writing")

    def test_ac3_traceability_result_is_the_same_regardless_of_checkout(self):
        self._enter_tests_writing_with_complete_coverage_on_branch()

        # Контроль: на своей ветке покрытие полное — переход обязан пройти.
        self.checkout(self.branch)
        self.capture(fsm.cmd_advance, self.TASK)
        on_branch_state = self.state()
        self.assertEqual(
            on_branch_state, "in_dev",
            "контроль: на ветке задачи покрытие AC полное — переход обязан "
            "пройти")

        # То же состояние задачи, рабочее дерево на чужой ветке.
        self.set_state("tests_writing")
        self.checkout(self.OTHER_BRANCH)
        self.capture(fsm.cmd_advance, self.TASK)
        off_branch_state = self.state()

        self.assertEqual(
            off_branch_state, on_branch_state,
            "трассируемость критериев приёмки не должна зависеть от того, "
            "какая ветка сейчас выписана в рабочем дереве (SPEC AC-3)")


class LockBranchTest(RealGitBranchTest):

    def _enter_in_dev_with_tests_committed_on_branch(self) -> None:
        self.prepare_ready_spec_on_task_branch()
        self.write_acceptance_tests(AC_TEST_BOTH_COVERED)
        self.commit_task_dir("acceptance_tests от test_author")
        self.set_state("tests_writing")
        self.checkout(self.branch)
        self.capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev
        self.assertEqual(self.state(), "in_dev", "подготовка теста не удалась")
        self.write("PLAN.md", PLAN_MD)
        self.commit_task_dir("PLAN.md ready")

    def test_ac3_lock_result_is_the_same_regardless_of_checkout(self):
        self._enter_in_dev_with_tests_committed_on_branch()

        # Контроль: на своей ветке лок не нарушен — переход обязан пройти.
        self.checkout(self.branch)
        self.capture(fsm.cmd_advance, self.TASK)
        on_branch_state = self.state()
        self.assertEqual(
            on_branch_state, "review",
            "контроль: лок acceptance_tests/ не нарушен на ветке задачи — "
            "переход обязан пройти")

        self.set_state("in_dev")
        self.checkout(self.OTHER_BRANCH)
        self.capture(fsm.cmd_advance, self.TASK)
        off_branch_state = self.state()

        self.assertEqual(
            off_branch_state, on_branch_state,
            "проверка лока приёмочных тестов не должна зависеть от того, "
            "какая ветка сейчас выписана в рабочем дереве (SPEC AC-3)")


# ---------------------------------------------------------------------
# AC-4: sha догфуд-фиксации — head ветки задачи, не HEAD чекаута.

class FixationBranchTest(RealGitBranchTest):

    def test_ac4_read_uses_task_branch_head_not_current_checkout(self):
        self.prepare_ready_spec_on_task_branch()
        branch_head = self.head()
        self.checkout(self.OTHER_BRANCH)
        self.assertNotEqual(
            self.head(), branch_head,
            "проверка бессмысленна, если чужая ветка указывает на тот же "
            "коммит, что и ветка задачи")

        sha, _clean = fixation.read(self.TASK, config.DEFAULT_TARGET)

        self.assertEqual(
            sha, branch_head,
            "fixation.read() обязан вычислять head ВЕТКИ ЗАДАЧИ, а не HEAD "
            "текущего чекаута рабочей копии (SPEC AC-4)")

    def test_ac4_fix_uses_task_branch_head_not_current_checkout(self):
        self.prepare_ready_spec_on_task_branch()
        branch_head = self.head()
        self.checkout(self.OTHER_BRANCH)

        sha, _clean = fixation.fix(self.TASK, config.DEFAULT_TARGET)

        self.assertEqual(
            sha, branch_head,
            "fixation.fix() обязан фиксировать head ВЕТКИ ЗАДАЧИ, а не HEAD "
            "текущего чекаута рабочей копии (SPEC AC-4)")

    def test_ac4_check_integrity_does_not_flag_incident_on_foreign_checkout(self):
        self.prepare_ready_spec_on_task_branch()
        self.checkout(self.branch)
        self.set_state("spec_gate")
        # Вызывается, пока рабочее дерево ДЕЙСТВИТЕЛЬНО на ветке задачи —
        # sha, вычисленный здесь, легитимен независимо от починки AC-4.
        self.capture(fsm.cmd_approve, self.TASK, self.head())
        self.assertEqual(self.state(), "tests_writing", "подготовка теста не удалась")

        # Ветка задачи не менялась — рабочее дерево переключается на чужую.
        self.checkout(self.OTHER_BRANCH)

        reason = fixation.check_integrity(store.db(), self.TASK)

        self.assertIsNone(
            reason,
            "чужой чекаут рабочей копии — не инцидент целостности задачи, "
            "если её собственная ветка не менялась: check_integrity() "
            "обязан сверяться с head ВЕТКИ ЗАДАЧИ, а не с HEAD текущего "
            "чекаута (SPEC AC-4)")


# ---------------------------------------------------------------------
# AC-5: ни одно из мест AC-1–AC-4 не падает необработанным исключением —
# предельный случай: ветка задачи вовсе не существует в git (удалена),
# рабочее дерево на чужой ветке.

class NoUnhandledExceptionOnMissingBranchTest(RealGitBranchTest):

    def setUp(self):
        super().setUp()
        self.prepare_ready_spec_on_task_branch()
        self.write_acceptance_tests(AC_TEST_BOTH_COVERED)
        self.commit_task_dir("acceptance_tests от test_author")
        self.checkout(self.OTHER_BRANCH)
        # `checkout` выше восстановил linked worktree на `self.branch`
        # (см. её докстринг) — веткой сейчас владеет он же, `-D` без
        # предварительного `workspace.remove` откажет тем же способом,
        # что и живой git.
        self.capture(workspace.remove, self.TASK)
        self.git("branch", "-D", self.branch)  # ветки задачи в git больше нет
        store.update_task(store.db(), self.TASK, fixed_sha="f" * 40)

    def _assert_no_bare_exception(self, fn, *args) -> None:
        try:
            fn(*args)
        except SystemExit:
            pass  # именованный отказ — допустимый исход (SPEC AC-5)
        except Exception as exc:  # noqa: BLE001 — суть теста: нет падения
            self.fail(f"{getattr(fn, '__qualname__', fn)} упал "
                      f"необработанным исключением: {exc!r} (SPEC AC-5)")

    def test_ac5_spec_gate_routing_does_not_raise(self):
        self.set_state("spec_gate")
        with mock.patch.object(fsm, "confirm_fixation", return_value=True):
            self._assert_no_bare_exception(self.capture, fsm.cmd_approve,
                                           self.TASK)

    def test_ac5_brief_build_does_not_raise(self):
        conn = store.db()
        self._assert_no_bare_exception(brief.developer_brief, conn, self.TASK)

    def test_ac5_traceability_check_does_not_raise(self):
        self.set_state("tests_writing")
        self._assert_no_bare_exception(self.capture, fsm.cmd_advance, self.TASK)

    def test_ac5_fixation_check_integrity_does_not_raise(self):
        conn = store.db()
        self._assert_no_bare_exception(fixation.check_integrity, conn, self.TASK)


# AC-6: причина переключения рабочего дерева на task/t029-... перед
# approve T030 — разбор журнала/логов конкретного инцидента и (если это
# дефект механики) код, который его закрывает, либо явная строка в
# PLAN.md «Риски» — не наблюдаемое поведение системы, которое можно
# закодировать unittest'ом; проверяет Оператор на приёмке по журналу
# T030 (~17:35 25.08.2026) и по тексту PLAN.md этой задачи.
# AC-6: manual — разбор конкретного инцидента по журналу T030 и текст
# PLAN.md «Риски»/код-фикс — не выражается unittest'ом, проверяет Оператор


# ---------------------------------------------------------------------
# AC-7 (часть 1, автоматическая половина): ни один существующий тест не
# ослаблен/заскипан/удалён по сравнению с main.

TEST_METHOD_DEF = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.M)
SKIP_DECORATED_METHOD = re.compile(
    r"@unittest\.skip\w*\([^)]*\)\s*\n\s*def\s+(test_\w+)\s*\(", re.M)


class ExistingTestsNotWeakenedTest(unittest.TestCase):
    """Реальный репозиторий (не песочница) — сравнение tests/*.py текущего
    рабочего дерева с содержимым тех же путей на main."""

    def _git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def test_ac7_no_test_method_removed_or_newly_skipped_since_main(self):
        paths = [p for p in self._git(
            "ls-tree", "-r", "--name-only", "main", "--", "tests/").splitlines()
                if p.endswith(".py")]
        removed: list[str] = []
        newly_skipped: list[str] = []

        for path in paths:
            before = self._git("show", f"main:{path}")
            after_file = REPO_ROOT / path
            if not after_file.exists():
                removed.append(f"{path} (файл удалён)")
                continue
            after = after_file.read_text(encoding="utf-8")

            missing = (set(TEST_METHOD_DEF.findall(before))
                      - set(TEST_METHOD_DEF.findall(after)))
            if missing:
                removed.append(f"{path}: {sorted(missing)}")

            newly = (set(SKIP_DECORATED_METHOD.findall(after))
                    - set(SKIP_DECORATED_METHOD.findall(before)))
            if newly:
                newly_skipped.append(f"{path}: {sorted(newly)}")

        self.assertEqual(
            removed, [],
            f"тестовые методы удалены по сравнению с main (SPEC AC-7): "
            f"{removed}")
        self.assertEqual(
            newly_skipped, [],
            f"тестовые методы заскипаны по сравнению с main (SPEC AC-7, "
            f"принцип целостности ADR-0002): {newly_skipped}")


# AC-7 (часть 2): семантическая пара «новая строка реестра
# docs/invariants.md действительно описывает то же поведение, что
# проверяет её тест» — не выражается unittest'ом (тест ловит текст
# ссылки, не смысл), проверяет ревьювер по правилам docs/invariants.md
# «Как добавить инвариант», п.3 (мутационная проверка: тест обязан
# краснеть на умышленно сломанном инварианте).
# AC-7: manual — пара «новая строка реестра invariants.md ↔ новый тест»
# семантически верна; проверяет ревьювер по docs/invariants.md, п.3


if __name__ == "__main__":
    unittest.main()
