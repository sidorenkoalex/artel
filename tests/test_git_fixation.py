"""Git-первичка артефактов и approve-по-sha (tasks/T021/SPEC.md, критерии 1–7).

Классы названы по требованиям SPEC: git-репо каталога проекта без remote
(1), коммит артефактного репо внешнего target на переходе FSM (2),
sha+чистота ветки пульта в журнале догфуда (3), approve с привязкой
к sha (4), сверка при старте шага (5), инвариант реестра (6, docs/
invariants.md #25), функция «нет remote» (7).

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002): `FsmDecidesOnlyOnFixedHashesTest`,
`IntegrityIncidentBlocksRunTest`, `ApproveByShaTest` и
`ExternalApproveDoesNotCommitOthersWorkInProgressTest` кодируют инвариант
25 реестра — их отключение или ослабление допустимо только Оператором
отдельным ADR (как и `tests/test_invariants.py`).

Для внешнего target песочница — как в `test_multitarget_invariants.py`:
пути `config` подменяются на временный каталог, git — настоящий (сама
суть фиксации — git-операции, подменять их заглушками нечем проверять).
Для догфуда — как `test_invariants.PultArtifactIsolationTest`: временный
каталог САМ является git-репозиторием (ROOT пульта), потому что здесь
проверяется именно чтение реального состояния рабочей копии, а не
поведение FSM в его отсутствие (это уже покрыто тем, что старые тесты
T001–T020 остаются зелёными без правок — они используют заглушки
`gitcmd.git`, и живая фиксация на них вырождается в «сверять не с чем»,
см. tasks/T021/PLAN.md, «Подход»).
"""
import contextlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (catalog, config, fixation, fsm,  # noqa: E402
                          gitcmd, projects, runner, store)
from tests.sandbox import TmpRootTest, capture  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

TARGETS_YAML = """targets:
  sled:
    forge: github
    url: https://example.invalid/sled
    base: main
    token_slot: sled-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

# SPEC.md минимальный и валидный по guard (образец test_multitarget_invariants.py).
SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: git-фиксация

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

# PLAN.md минимальный и валидный по guard — для сверки чистоты advance
# (T033): ExternalTargetAdvanceIgnoresDirtyCheckTest ниже.
PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: git-фиксация — внешний target

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class FakeStream:
    """Пайп процесса: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        pass


class FakeProc:
    """Процесс агента: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class _GitFixationTmpRootTest(TmpRootTest):
    """Песочница мультитаргета: пути `config` — во временном каталоге, git настоящий."""

    PATCHED_ATTRS = ("ROOT", "DB", "TASKS", "LOGS", "PROJECTS",
                     "ROLE_HOME", "ROLE_CONFIG_DIR", "TARGETS")


TmpRootTest = _GitFixationTmpRootTest


class ArtifactRepoInitTest(TmpRootTest):
    """Требование 1: git-репо каталога проекта — без remote, с .gitignore."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")

    def repo(self) -> Path:
        return config.PROJECTS / "sled"

    def test_init_creates_a_git_repo_without_a_remote(self):
        capture(projects.cmd_target_init, "sled")

        self.assertTrue((self.repo() / ".git").is_dir())
        self.assertTrue(gitcmd.has_no_remote(self.repo()))

    def test_gitignore_excludes_workspace_and_logs(self):
        capture(projects.cmd_target_init, "sled")

        lines = (self.repo() / ".gitignore").read_text(
            encoding="utf-8").splitlines()
        self.assertIn("workspace/", lines)
        self.assertIn("logs/", lines)

    def test_second_init_does_not_change_state_or_fail(self):
        capture(projects.cmd_target_init, "sled")
        (self.repo() / "tasks" / "T001").mkdir(parents=True)

        out = capture(projects.cmd_target_init, "sled")

        self.assertIn("уже было", out)
        self.assertTrue((self.repo() / ".git").is_dir())
        self.assertTrue((self.repo() / "tasks" / "T001").is_dir(),
                        "повторная инициализация не трогает содержимое")


class NoRemoteCheckTest(TmpRootTest):
    """Требование 7: функция проверки «у артефактного репо нет remote»."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")
        capture(projects.cmd_target_init, "sled")

    def test_freshly_initialized_repo_has_no_remote(self):
        self.assertTrue(projects.artifact_repo_has_no_remote("sled"))

    def test_repo_with_a_remote_is_detected(self):
        repo = config.PROJECTS / "sled"
        gitcmd.in_repo(repo, "remote", "add", "origin",
                       "https://example.invalid/x")

        self.assertFalse(projects.artifact_repo_has_no_remote("sled"))


class ExternalTransitionCommitsTest(TmpRootTest):
    """Требование 2: переход FSM задачи внешнего target коммитит его репо."""

    TASK = "SLED-T001"

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")
        capture(projects.cmd_target_init, "sled")
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача sled",
                          "spec_writing", f"task/{self.TASK.lower()}",
                          "sled", 25.0)
        tdir = config.PROJECTS / "sled" / "tasks" / self.TASK
        tdir.mkdir(parents=True)
        (tdir / "SPEC.md").write_text("# SPEC заглушка\n", encoding="utf-8")

    def repo(self) -> Path:
        return config.PROJECTS / "sled"

    def test_transition_commits_the_artifact_repo(self):
        self.assertEqual(gitcmd.head_sha(self.repo()), "",
                         "до перехода в репо ещё нет коммитов")

        capture(store.set_state, store.db(), self.TASK, "in_dev",
               "operator", "тест")

        sha = gitcmd.head_sha(self.repo())
        self.assertNotEqual(sha, "")
        shown = gitcmd.in_repo(self.repo(), "show", "--stat", sha).stdout
        self.assertIn("SPEC.md", shown)

    def test_sha_lands_in_the_journal(self):
        capture(store.set_state, store.db(), self.TASK, "in_dev",
               "operator", "тест")

        sha = gitcmd.head_sha(self.repo())
        entries = [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                   if r["action"] == "sha зафиксирован"]
        self.assertEqual(len(entries), 1)
        self.assertIn(sha, entries[0])
        self.assertIn("target=sled", entries[0])
        self.assertEqual(store.get_task(store.db(), self.TASK)["fixed_sha"], sha)

    def test_second_transition_without_changes_reuses_the_head(self):
        capture(store.set_state, store.db(), self.TASK, "in_dev",
               "operator", "тест")
        first = gitcmd.head_sha(self.repo())

        capture(store.set_state, store.db(), self.TASK, "review",
               "operator", "тест")

        self.assertEqual(gitcmd.head_sha(self.repo()), first,
                         "нечего коммитить — HEAD не двигается")


class ExternalTargetAdvanceIgnoresDirtyCheckTest(TmpRootTest):
    """T033, требование 4 (PLAN «Риски»): сверка чистоты `advance` —
    только догфуд. Для внешнего target артефактный репозиторий коммитит
    сам оркестратор целиком уже ПОСЛЕ решения перейти (`fixation.
    _fix_external`, `ExternalTransitionCommitsTest` выше) — до перехода
    PLAN.md там закономерно не закоммичен, это не забытый коммит роли.
    Наивная сверка блокировала бы `advance` для внешнего target навсегда.
    """

    TASK = "SLED-T001"

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")
        capture(projects.cmd_target_init, "sled")
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача sled", "in_dev",
                          f"task/{self.TASK.lower()}", "sled", 25.0)
        # Гейтинг advance читает артефакты из tasks/<id> ПУЛЬТА (до A7,
        # ADR-0003 3д — независимо от target шага, см. ExternalIntegrity
        # IncidentBlocksRunTest.make_task ниже), не из репо target'а —
        # его этот тест намеренно не трогает вовсе.
        (config.TASKS / self.TASK).mkdir(parents=True)
        (config.TASKS / self.TASK / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")

    def test_uncommitted_plan_still_advances_for_external_target(self):
        out = capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "review",
                         "внешний target не блокируется сверкой чистоты")
        self.assertNotIn("не закоммичен", out)


class ExternalIntegrityIncidentBlocksRunTest(TmpRootTest):
    """Требование 5 (REVIEW.md T021, замечание 2, итерация 1): сверка при
    старте шага для ВНЕШНЕГО target через `runner.cmd_run`.

    До этой правки `TmpRootTest`-песочница проверяла только инициализацию
    репо и коммит фиксации (`ArtifactRepoInitTest`, `NoRemoteCheckTest`,
    `ExternalTransitionCommitsTest`) — ни один тест не доходил до
    `runner.cmd_run`, хотя `runner.role_cwd` уже умеет запускать шаг для
    внешнего target. Именно этот пробел не поймал дефект замечания 1
    (`check_integrity` коммитила чужой незакоммиченный артефакт).
    """

    TASK = "SLED-T001"
    OTHER = "SLED-T002"

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")
        capture(projects.cmd_target_init, "sled")
        capture(catalog.cmd_init)
        # `runner.cmd_run` для роли developer читает skills/*.md по имени
        # из roles.yaml (conventions-core, escalation-rules, coding-standards).
        shutil.copytree(REPO_ROOT / "skills", config.ROOT / "skills")
        # T028: бриф роли developer читает docs/codebase-map.md и CLAUDE.md
        # из config.ROOT (пульт, не workspace target'а) — без них шаг падает
        # ENOENT до того, как дойдёт до сверки целостности, которую этот
        # класс проверяет.
        (config.ROOT / "docs").mkdir()
        (config.ROOT / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (config.ROOT / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        patcher = mock.patch.object(runner.keychain, "token",
                                    lambda slot: "tok-test")
        patcher.start()
        self.addCleanup(patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def repo(self) -> Path:
        return config.PROJECTS / "sled"

    def make_task(self, task_id: str) -> str:
        """Заводит задачу сразу в in_dev с зафиксированными SPEC/PLAN.

        Возвращает sha, записанный переходом в `tasks.fixed_sha`.
        """
        store.insert_task(store.db(), task_id, f"Задача {task_id}",
                          "spec_writing", f"task/{task_id.lower()}",
                          "sled", 25.0)
        tdir = self.repo() / "tasks" / task_id
        tdir.mkdir(parents=True)
        (tdir / "SPEC.md").write_text("# SPEC заглушка\n", encoding="utf-8")
        (tdir / "PLAN.md").write_text("# PLAN заглушка\n", encoding="utf-8")
        # T028: бриф роли developer читает tasks/<id>/SPEC.md из ROOT пульта
        # (config.TASKS), а не из репо target'а, — тот же адрес, что и
        # `catalog.cmd_new` (артефакты задачи живут в пульте, ADR-0003 3д,
        # «особый случай», до A7 — независимо от target шага).
        (config.TASKS / task_id).mkdir(parents=True, exist_ok=True)
        (config.TASKS / task_id / "SPEC.md").write_text(
            "# SPEC заглушка\n", encoding="utf-8")
        capture(store.set_state, store.db(), task_id, "in_dev",
               "operator", "тест: вход в in_dev")
        return store.get_task(store.db(), task_id)["fixed_sha"]

    def run_faked(self, task_id: str):
        """Тот же приём, что и `RealPultGitTest.run_faked`: настоящий git,
        подложный только запуск `claude`."""
        real_popen = subprocess.Popen

        def side_effect(cmd, *args, **kwargs):
            if cmd and cmd[0] == "claude":
                return FakeProc(["готово\n"])
            return real_popen(cmd, *args, **kwargs)

        with mock.patch.object(runner, "spawn_agent",
                               side_effect=side_effect) as popen:
            out = capture(runner.cmd_run, task_id)
        return out, popen

    def claude_launches(self, popen) -> list:
        return [c for c in popen.call_args_list
               if c.args and c.args[0] and c.args[0][0] == "claude"]

    def test_tampering_after_fixation_blocks_the_run(self):
        self.make_task(self.TASK)
        (self.repo() / "tasks" / self.TASK / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")

        out, popen = self.run_faked(self.TASK)

        self.assertEqual(self.claude_launches(popen), [])
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        self.assertIn("инцидент целостности", out)
        # «грязная копия», не «sha разошёлся»: если бы check_integrity
        # (как до фикса замечания 1) сама закоммитила подмену, sha уже
        # успел бы уйти вперёд, и причина отказа звучала бы иначе.
        self.assertIn("грязная копия", out)

    def test_clean_state_runs_normally(self):
        self.make_task(self.TASK)

        out, popen = self.run_faked(self.TASK)

        self.assertEqual(len(self.claude_launches(popen)), 1)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "in_dev")

    def test_check_integrity_does_not_commit_when_tampered(self):
        """Прямая проверка замечания 1: `check_integrity` — не `fix()`,
        коммитить не имеет права даже когда есть что коммитить."""
        fixed = self.make_task(self.TASK)
        (self.repo() / "tasks" / self.TASK / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")

        reason = fixation.check_integrity(store.db(), self.TASK)

        self.assertIsNotNone(reason)
        self.assertIn("грязная копия", reason)
        self.assertEqual(gitcmd.head_sha(self.repo()), fixed,
                         "check_integrity — проверка, не точка фиксации")
        status = gitcmd.in_repo(self.repo(), "status", "--porcelain").stdout
        self.assertIn(f"tasks/{self.TASK}/SPEC.md", status,
                      "подмена осталась незакоммиченной")

    def test_check_integrity_does_not_commit_another_tasks_work_in_progress(self):
        """Сценарий поломки из замечания 1 REVIEW.md: задача A ещё пишет
        файл (не закоммичен), Оператор запускает `run` для задачи B того
        же target — `check_integrity(B)` не смеет утащить WIP A в коммит
        фиксации B и сдвинуть HEAD, который ни A, ни B не просили сдвигать.
        """
        head_before = self.make_task(self.TASK)
        # Задача A (OTHER) существует, но её СОБСТВЕННЫЙ переход ещё не
        # случился — роль просто пишет файл в общем репо target'а, не
        # коммитя (в отличие от `make_task`, здесь нет `store.set_state`,
        # то есть нет и легитимной фиксации, которая бы сама сдвинула
        # HEAD — единственная причина «грязно» ниже это WIP A).
        store.insert_task(store.db(), self.OTHER, f"Задача {self.OTHER}",
                          "in_dev", f"task/{self.OTHER.lower()}",
                          "sled", 25.0)
        (self.repo() / "tasks" / self.OTHER).mkdir(parents=True)
        (self.repo() / "tasks" / self.OTHER / "PLAN.md").write_text(
            "A ещё работает\n", encoding="utf-8")

        reason = fixation.check_integrity(store.db(), self.TASK)

        self.assertIsNotNone(reason)
        self.assertIn("грязная копия", reason)
        # HEAD артефактного репо не сдвинулся — WIP задачи A остался
        # незакоммиченным, а не был подхвачен коммитом фиксации B.
        self.assertEqual(gitcmd.head_sha(self.repo()), head_before,
                         "check_integrity(B) не смеет коммитить WIP задачи A")
        status = gitcmd.in_repo(self.repo(), "status", "--porcelain").stdout
        self.assertIn(f"tasks/{self.OTHER}", status,
                      "правка A осталась незакоммиченной, не подмешана в коммит B")

        # Через runner.cmd_run — тот же путь, каким Оператор реально
        # столкнётся со сценарием: репо-широкая «чистота» (требование 2 —
        # коммит целиком, не по задачам) блокирует и B тоже — известное
        # ограничение гранулярности A2b при нескольких активных задачах
        # одного target (tasks/T021/PLAN.md «Риски»), но это отказ, а не
        # порча истории: HEAD и здесь не двигается заранее самой проверкой.
        out, popen = self.run_faked(self.TASK)

        self.assertEqual(self.claude_launches(popen), [])
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        self.assertIn("грязная копия", out)


class ExternalApproveDoesNotCommitOthersWorkInProgressTest(TmpRootTest):
    """Требование 4 (REVIEW.md T021, замечание 1, итерация 2): `approve`
    для одной задачи внешнего target не смеет коммитить незакоммиченный
    WIP ДРУГОЙ задачи того же target как побочный эффект сверки sha —
    тот же класс дефекта, что закрыт для `check_integrity` в итерации 1
    (`ExternalIntegrityIncidentBlocksRunTest`), теперь для
    `fsm.confirm_fixation`/`cmd_approve`: до фикса она сравнивала через
    мутирующий `fixation.fix()`, а не через нечитающий `fixation.read()`.
    """

    TASK = "SLED-T001"
    OTHER = "SLED-T002"

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")
        capture(projects.cmd_target_init, "sled")
        capture(catalog.cmd_init)

    def repo(self) -> Path:
        return config.PROJECTS / "sled"

    def enter_spec_gate(self, task_id: str) -> str:
        """Заводит задачу в `spec_gate` с зафиксированным SPEC.md,
        возвращает sha, записанный переходом в `tasks.fixed_sha`."""
        store.insert_task(store.db(), task_id, f"Задача {task_id}",
                          "spec_writing", f"task/{task_id.lower()}",
                          "sled", 25.0)
        tdir = self.repo() / "tasks" / task_id
        tdir.mkdir(parents=True)
        (tdir / "SPEC.md").write_text("# SPEC заглушка\n", encoding="utf-8")
        capture(store.set_state, store.db(), task_id, "spec_gate",
               "operator", "тест: вход в spec_gate")
        return store.get_task(store.db(), task_id)["fixed_sha"]

    def write_uncommitted_wip(self, task_id: str) -> None:
        """Роль другой задачи ещё пишет файл, не коммитя (обычный WIP)."""
        tdir = self.repo() / "tasks" / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text("другая задача ещё работает\n",
                                      encoding="utf-8")

    def status(self) -> str:
        return gitcmd.in_repo(self.repo(), "status", "--porcelain").stdout

    def test_approve_without_sha_does_not_commit_another_tasks_wip(self):
        sha = self.enter_spec_gate(self.TASK)
        self.write_uncommitted_wip(self.OTHER)
        head_before = gitcmd.head_sha(self.repo())

        out = capture(fsm.cmd_approve, self.TASK)

        self.assertIn(sha, out)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate", "approve без sha — мягкий возврат, не переход")
        self.assertEqual(gitcmd.head_sha(self.repo()), head_before,
                         "approve без sha не имеет права коммитить")
        self.assertIn(f"tasks/{self.OTHER}", self.status(),
                      "WIP другой задачи остался незакоммиченным")

    def test_rejected_approve_does_not_commit_another_tasks_wip(self):
        self.enter_spec_gate(self.TASK)
        self.write_uncommitted_wip(self.OTHER)
        head_before = gitcmd.head_sha(self.repo())
        wrong = "0" * 40

        with self.assertRaises(SystemExit):
            capture(fsm.cmd_approve, self.TASK, wrong)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate")
        self.assertEqual(gitcmd.head_sha(self.repo()), head_before,
                         "отказанный approve не имеет права коммитить")
        self.assertIn(f"tasks/{self.OTHER}", self.status(),
                      "WIP другой задачи остался незакоммиченным")

    def test_approve_with_matching_sha_still_transitions(self):
        """Контроль: сам фикс не ломает штатный успешный approve."""
        sha = self.enter_spec_gate(self.TASK)

        capture(fsm.cmd_approve, self.TASK, sha)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "in_dev")


class RealPultGitTest(unittest.TestCase):
    """Песочница догфуда: ROOT — настоящий git-репозиторий (как test_invariants.

    PultArtifactIsolationTest): здесь проверяется чтение РЕАЛЬНОГО
    состояния рабочей копии, заглушкой git его не изобразить.
    """

    TASK = "T001"

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
        # T028: бриф роли developer/analyst читает docs/codebase-map.md и
        # CLAUDE.md из config.ROOT — без них шаг падает ENOENT до того, как
        # дойдёт до реального git, который эта песочница проверяет.
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
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
                            ("TARGETS", self.root / "targets.yaml"),
                            ("WORKTREES", self.root / ".artel" / "worktrees")):
            self.patches.enter_context(mock.patch.object(config, attr, value))
        self.patches.enter_context(mock.patch.object(
            runner.keychain, "token", lambda slot: "tok-test"))
        self.patches.enter_context(mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: []))

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Git-фиксация")  # заводит T001

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    capture = staticmethod(capture)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def commit_task_dir(self, message: str = "артефакт") -> None:
        self.git("add", f"tasks/{self.TASK}")
        self.git("commit", "-q", "-m", message)

    def enter_spec_gate(self) -> str:
        (config.TASKS / self.TASK / "SPEC.md").write_text(
            SPEC_READY.format(task=self.TASK), encoding="utf-8")
        self.commit_task_dir()
        self.capture(fsm.cmd_advance, self.TASK)
        return self.head()

    def enter_in_dev(self) -> str:
        sha = self.enter_spec_gate()
        self.capture(fsm.cmd_approve, self.TASK, sha)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "in_dev")
        return sha

    def run_faked(self):
        """Прогон `cmd_run` с подложным агентом, но НАСТОЯЩИМ git.

        `subprocess.Popen` — один и тот же модульный объект что у
        `runner`, что у `gitcmd` (через `subprocess.run`): голая подмена
        `return_value` вернула бы `FakeProc` и на попытках `gitcmd.git`
        сходить в реальный репозиторий этой песочницы, а `subprocess.run`
        не переживёт `Popen`, не умеющий быть контекстным менеджером.
        `side_effect` пропускает наружу только запуск `claude`.
        """
        real_popen = subprocess.Popen

        def side_effect(cmd, *args, **kwargs):
            if cmd and cmd[0] == "claude":
                return FakeProc(["готово\n"])
            return real_popen(cmd, *args, **kwargs)

        with mock.patch.object(runner, "spawn_agent",
                               side_effect=side_effect) as popen:
            out = self.capture(runner.cmd_run, self.TASK)
        return out, popen

    def claude_launches(self, popen) -> list:
        """Вызовы `popen`, которые реально запускали `claude`, не git.

        `popen` — общий мок и для агента, и (через `subprocess.run` внутри
        `gitcmd.git`) для настоящих git-команд этой песочницы: его
        `call_count`/`assert_called_once` считает и то, и другое.
        Проверять надо запуск именно агента.
        """
        return [c for c in popen.call_args_list
               if c.args and c.args[0] and c.args[0][0] == "claude"]


class DogfoodTransitionJournalsShaTest(RealPultGitTest):
    """Требование 3: переход догфуд-задачи журналит head sha + чистоту."""

    def test_journal_gets_head_sha_and_cleanliness(self):
        sha = self.enter_spec_gate()

        entries = [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                   if r["action"] == "sha зафиксирован"]
        self.assertEqual(len(entries), 1)
        self.assertIn(sha, entries[0])
        self.assertIn("чисто=True", entries[0])
        self.assertEqual(store.get_task(store.db(), self.TASK)["fixed_sha"], sha)

    def test_uncommitted_artifact_is_journaled_as_dirty(self):
        """T033: грязная копия теперь ОТКАЗЫВАЕТ переходу (симметрия с
        `approve`, инцидент T032), а не журналит фиксацию с чисто=False
        поверх состоявшегося перехода — старое поведение и было тем самым
        дефектом асимметрии, который T033 закрывает."""
        (config.TASKS / self.TASK / "SPEC.md").write_text(
            SPEC_READY.format(task=self.TASK), encoding="utf-8")
        # SPEC.md написан, но НЕ закоммичен — грязная копия tasks/<id>.

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_writing", "переход по грязной копии не случился")
        fixed = [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                 if r["action"] == "sha зафиксирован"]
        self.assertEqual(fixed, [], "грязный переход фиксацию не журналит")
        refused = [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                   if "не закоммичен" in r["detail"]]
        self.assertTrue(refused, "отказ по грязной копии журналится отдельно")


class ApproveByShaTest(RealPultGitTest):
    """Требование 4: approve с привязкой к sha."""

    def test_approve_without_sha_prints_current_and_does_not_transition(self):
        sha = self.enter_spec_gate()

        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertIn(sha, out)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate")

    def test_approve_with_a_mismatched_sha_is_refused(self):
        self.enter_spec_gate()
        wrong = "0" * 40

        with self.assertRaises(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK, wrong)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate")

    def test_approve_with_the_matching_sha_passes(self):
        sha = self.enter_spec_gate()

        self.capture(fsm.cmd_approve, self.TASK, sha)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "in_dev")

    def test_approve_on_escalated_with_matching_sha_returns_to_escalated_from(self):
        """`escalated` тоже входит в APPROVE_NEEDS_SHA (fsm.py:110) — это
        единственный путь выхода из инцидента целостности после того, как
        Оператор разобрался и подтвердил актуальное состояние.
        """
        self.enter_in_dev()
        (config.TASKS / self.TASK / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")
        self.run_faked()  # инцидент целостности -> escalated, escalated_from=in_dev
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        self.commit_task_dir("подтверждено Оператором")

        self.capture(fsm.cmd_approve, self.TASK, self.head())

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "in_dev", "escalated_from вернул задачу в in_dev")


class IntegrityIncidentBlocksRunTest(RealPultGitTest):
    """Требование 5: сверка при старте шага — изменение после approve отказывает."""

    def test_uncommitted_change_after_approve_blocks_the_run(self):
        self.enter_in_dev()
        (config.TASKS / self.TASK / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")

        out, popen = self.run_faked()

        self.assertEqual(self.claude_launches(popen), [])
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        self.assertIn("инцидент целостности", out)

    def test_committed_change_after_approve_also_blocks_the_run(self):
        """Разошедшийся sha — не только грязная копия, но и посторонний коммит."""
        self.enter_in_dev()
        (config.TASKS / self.TASK / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")
        self.commit_task_dir("посторонняя правка")

        out, popen = self.run_faked()

        self.assertEqual(self.claude_launches(popen), [])
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        self.assertIn("инцидент целостности", out)

    def test_clean_unchanged_state_runs_normally(self):
        """Контроль: без вмешательства сверка не мешает обычному запуску."""
        self.enter_in_dev()

        out, popen = self.run_faked()

        self.assertEqual(len(self.claude_launches(popen)), 1)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "in_dev")


class FsmDecidesOnlyOnFixedHashesTest(RealPultGitTest):
    """Инвариант 25 (docs/invariants.md): FSM решает только по артефактам,
    чьи хэши зафиксированы её журналом.

    Источник угрозы — ADR-0003 3в: роль (или ручная правка) с доступом
    к тому же ROOT, что и оркестратор, меняет control-артефакт задачи
    в обход гейта. Подмена PLAN.md здесь — не «код разработчика»
    (тот вне зоны хэш-фиксации), а именно управляющий вход следующего
    гейта — то, ради чего фиксация и существует.
    """

    def test_tampering_between_approve_and_run_is_caught_not_silently_used(self):
        self.enter_in_dev()

        (config.TASKS / self.TASK / "PLAN.md").write_text(
            "самозванный PLAN, гейт не проходил\n", encoding="utf-8")
        self.commit_task_dir("чужая правка мимо гейта")

        out, popen = self.run_faked()

        self.assertEqual(self.claude_launches(popen), [])
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        self.assertIn("инцидент целостности", out)

    def test_mutation_without_the_check_would_run_on_tampered_state(self):
        """Мутационная проверка PLAN: без вызова `check_integrity` подмена
        осталась бы незамеченной и агент бы стартовал.
        """
        self.enter_in_dev()
        (config.TASKS / self.TASK / "PLAN.md").write_text(
            "самозванный PLAN\n", encoding="utf-8")
        self.commit_task_dir("чужая правка мимо гейта")

        with mock.patch.object(fixation, "check_integrity",
                               lambda conn, task_id: None):
            _, popen = self.run_faked()

        self.assertEqual(len(self.claude_launches(popen)), 1)


if __name__ == "__main__":
    unittest.main()
