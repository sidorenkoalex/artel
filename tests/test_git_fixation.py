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
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (auto, catalog, config, fixation, fsm,  # noqa: E402
                          fsm_advance, fsm_autogate, gates, github_adapter,
                          gitcmd, projects, runner, store)
from tests.sandbox import (FakeProc, TmpRootTest, capture,  # noqa: E402
                           capture_new_task_id, claude_only_popen,
                           network_guarded_real_run, resilient_tmp_cleanup)

REPO_ROOT = Path(__file__).resolve().parent.parent

TARGETS_YAML = """targets:
  sled:
    forge: github
    url: file:///nonexistent/sled
    base: main
    token_slot: sled-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

# `artel` — обычная запись target (A7, AC-1): `RealPultGitTest` заводит
# self-задачи через generic-путь `cmd_new`, тем же приёмом, что и
# `TARGETS_YAML` выше для 'sled'.
ARTEL_TARGETS_YAML = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

# REVIEW.md-заглушка со статусом ВНЕ config.REVIEW_VERDICTS (SPEC
# 01M1NWCHVTYQ0M8PCJ1YJ2N78P): `fsm_advance.review` читает `status` из
# фронтматтера и, не найдя его среди `REVIEW_VERDICTS`, отказывает
# переходу МОЛЧА (`return False`, без journal-записи) — та же
# «вердикта ещё нет» деградация, на которую и рассчитан этот плейсхолдер
# (см. докстринг `enter_in_dev` — симметрично `PLAN_READY` для in_dev).
REVIEW_DRAFT = """---
task: {task}
type: review
author_role: reviewer
status: draft
schema_version: 1
iteration: 1
---

# REVIEW: git-фиксация — внешний target

## Вердикт
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

# SPEC.md с явным легитимным пропуском планки (регрессия №16,
# 01M283NJV2PNDSS7J2HKS19YHJ) — `guard.requires_ac_markup` читает
# `skip_tests` только при `schema_version >= 2`.
SPEC_SKIP_TESTS = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
skip_tests: true
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


class _GitFixationTmpRootTest(TmpRootTest):
    """Песочница мультитаргета: пути `config` — во временном каталоге, git настоящий."""

    def setUp(self):
        super().setUp()
        # Весь этот файл проверяет НАСТОЯЩИЙ git (см. докстринг модуля) —
        # `SpyRun` базового `TmpRootTest` (заглушка ради плотницкой записи
        # `cmd_new` без реального репозитория, tests/sandbox.py) перекрыт
        # здесь настоящим git через `network_guarded_real_run` (SPEC
        # 01M1QHQ277PQQA894X97RVEX9Y, требование 1) — тот же настоящий
        # `subprocess.run` для всего, кроме сетевых fetch/push/ls-remote/
        # clone с DNS-адресом, которые он отклоняет мгновенно вместо
        # реального обращения к резолверу.
        patcher = mock.patch.object(gitcmd.subprocess, "run",
                                    network_guarded_real_run)
        patcher.start()
        self.addCleanup(patcher.stop)


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
                       "file:///nonexistent/x")

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

        capture(lambda: store.set_state(
            store.db(), self.TASK, "in_dev", "operator",
            expected_state="spec_writing", detail="тест"))

        sha = gitcmd.head_sha(self.repo())
        self.assertNotEqual(sha, "")
        shown = gitcmd.in_repo(self.repo(), "show", "--stat", sha).stdout
        self.assertIn("SPEC.md", shown)

    def test_sha_lands_in_the_journal(self):
        capture(lambda: store.set_state(
            store.db(), self.TASK, "in_dev", "operator",
            expected_state="spec_writing", detail="тест"))

        sha = gitcmd.head_sha(self.repo())
        entries = [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                   if r["action"] == "sha зафиксирован"]
        self.assertEqual(len(entries), 1)
        self.assertIn(sha, entries[0])
        self.assertIn("target=sled", entries[0])
        self.assertEqual(store.get_task(store.db(), self.TASK)["fixed_sha"], sha)

    def test_second_transition_without_changes_reuses_the_head(self):
        capture(lambda: store.set_state(
            store.db(), self.TASK, "in_dev", "operator",
            expected_state="spec_writing", detail="тест"))
        first = gitcmd.head_sha(self.repo())

        capture(lambda: store.set_state(
            store.db(), self.TASK, "review", "operator",
            expected_state="in_dev", detail="тест"))

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
        # SPEC T094, требование 10: гейтинг advance для НЕ-self target
        # читает tasks/<id>/PLAN.md из артефактной ветки ПУЛЬТА
        # (`artifact_source.resolve`), не из `config.TASKS` — ROOT этой
        # песочницы должен быть настоящим git-репозиторием (тот же приём,
        # что `ExternalIntegrityIncidentBlocksRunTest.setUp` ниже).
        subprocess.run(["git", "init", "-q", "-b", config.MAIN_BRANCH],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.email", "artel@example.invalid"],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.name", "artel tests"],
                       cwd=config.ROOT, check=True)
        (config.ROOT / "marker.txt").write_text("main\n", encoding="utf-8")
        shutil.copy(REPO_ROOT / ".gitignore", config.ROOT / ".gitignore")
        subprocess.run(["git", "add", "-A"], cwd=config.ROOT, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"],
                       cwd=config.ROOT, check=True)
        from orchestrator import artifact_branch
        artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/PLAN.md": PLAN_READY.format(task=self.TASK),
             # регрессия №16 (01M283NJV2PNDSS7J2HKS19YHJ): начиная с
             # правки `_acceptance_run_refuses` (материализация планки
             # для собственного/внешнего target), отсутствие SPEC.md в
             # артефактной ветке даёт «планка не найдена в источнике» —
             # SPEC-заглушка нужна здесь именно для легитимного пропуска
             # (`skip_tests`), не для содержания.
             f"tasks/{self.TASK}/SPEC.md": SPEC_SKIP_TESTS.format(task=self.TASK)},
            f"{self.TASK}: PLAN заглушка")

    def test_uncommitted_plan_still_advances_for_external_target(self):
        # ADR-0015: сверка головы на origin переехала на `in_dev ->
        # verifying` — эта песочница не заводит настоящую кодовую ветку
        # `task/sled-t001` (только артефактную PLAN-заглушку), а предмет
        # теста — сверка чистоты, не origin-push (у него свои тесты,
        # `tests/test_github_adapter.py`).
        #
        # Гейт ёмкости (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, AC-10) теперь
        # считает diff в клоне контекста target'а для ЛЮБОГО target —
        # `config.PROJECTS/sled/workspace` здесь пустой каталог, не
        # настоящий git-клон (`cmd_target_init` его не заводит, это ТЗ-2,
        # вне зоны этой задачи), и гейт fail-closed отказал бы переходу
        # по не отвечающему git — предмет ЭТОГО теста (сверка чистоты),
        # не гейт ёмкости, поэтому он замокан отдельно.
        with mock.patch.object(github_adapter, "ensure_head_in_origin",
                              return_value=(True, "")), \
             mock.patch.object(fsm_advance, "_capacity_gate_refuses",
                               return_value=False):
            out = capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "verifying",
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
        # SPEC T094, требование 10: бриф developer для ЛЮБОГО не-self
        # target читает tasks/<id>/ из артефактной ветки ПУЛЬТА
        # (`brief._artifact_source_branch`) — ROOT этой песочницы должен
        # быть настоящим git-репозиторием, не только `config.PROJECTS/sled`.
        subprocess.run(["git", "init", "-q", "-b", config.MAIN_BRANCH],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.email", "artel@example.invalid"],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.name", "artel tests"],
                       cwd=config.ROOT, check=True)
        (config.ROOT / "marker.txt").write_text("main\n", encoding="utf-8")
        # `runner.cmd_run` для роли developer читает skills/*.md по имени
        # из roles.yaml (conventions-core, escalation-rules, coding-standards)
        # — с этой задачи (tasks/01M1K7KP0D8ZKRM9KTE75DCCYR, AC-1) через
        # `git show main:...`, а не с диска: обязаны попасть в коммит НИЖЕ,
        # иначе `git show` не найдёт их в `main` (незакоммиченный диск —
        # ровно тот случай, который AC-1 обязан игнорировать).
        shutil.copytree(REPO_ROOT / "skills", config.ROOT / "skills")
        # T028: бриф роли developer читает docs/codebase-map.md и CLAUDE.md
        # из config.ROOT (пульт, не workspace target'а) — без них шаг падает
        # ENOENT до того, как дойдёт до сверки целостности, которую этот
        # класс проверяет. CLAUDE.md — тоже через `git show main:...` с этой
        # задачи (AC-2), тоже обязан попасть в коммит ниже.
        (config.ROOT / "docs").mkdir()
        (config.ROOT / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (config.ROOT / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        # `.artel/` несёт вложенный git-репозиторий (`config.PROJECTS/sled`,
        # `projects.cmd_target_init` выше) — без `.gitignore` `git add -A`
        # отказывает на нём как на подмодуле без коммита.
        shutil.copy(REPO_ROOT / ".gitignore", config.ROOT / ".gitignore")
        subprocess.run(["git", "add", "-A"], cwd=config.ROOT, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"],
                       cwd=config.ROOT, check=True)
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
        # SPEC T094, требование 10: бриф роли developer для НЕ-self target
        # читает tasks/<id>/SPEC.md из артефактной ветки ПУЛЬТА
        # (`brief._artifact_source_branch`), не из `config.TASKS` — та
        # мирная площадка (ADR-0003 3д, «особый случай») с этой задачи
        # остаётся только за self/догфудом (требование 16).
        from orchestrator import artifact_branch
        # PLAN.md — тоже в артефактную ветку, не только на диск `tdir`
        # выше: `runner.role_cwd` для внешнего target материализует
        # `tasks/<id>/` РОВНО из этой ветки (`materialize_task_dir`) в
        # РАБОЧИЙ каталог роли (`.../workspace/tasks/<id>/`, не в `tdir`)
        # — без записи сюда обязательный артефакт роли developer (SPEC
        # 01M1RQ12JVHE3PQYDFV1XPSTQ3, требование 3) на месте материализации
        # отсутствует, и штатный (rc=0) прогон честно ретраится.
        artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md": "# SPEC заглушка\n",
                     f"tasks/{task_id}/PLAN.md": "# PLAN заглушка\n"},
            f"{task_id}: SPEC заглушка")
        capture(lambda: store.set_state(
            store.db(), task_id, "in_dev", "operator",
            expected_state="spec_writing", detail="тест: вход в in_dev"))
        return store.get_task(store.db(), task_id)["fixed_sha"]

    def run_faked(self, task_id: str):
        """Тот же приём, что и `RealPultGitTest.run_faked`: настоящий git,
        подложный только запуск `claude`."""
        with mock.patch.object(
                runner, "spawn_agent",
                side_effect=claude_only_popen(FakeProc(["готово\n"]))) as popen:
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
        # SPEC T094, требование 10: approve на spec_gate для НЕ-self
        # target читает tasks/<id>/SPEC.md из артефактной ветки ПУЛЬТА
        # (`artifact_source.resolve`) — ROOT этой песочницы должен быть
        # настоящим git-репозиторием (тот же приём, что
        # `ExternalIntegrityIncidentBlocksRunTest.setUp`).
        subprocess.run(["git", "init", "-q", "-b", config.MAIN_BRANCH],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.email", "artel@example.invalid"],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.name", "artel tests"],
                       cwd=config.ROOT, check=True)
        (config.ROOT / "marker.txt").write_text("main\n", encoding="utf-8")
        shutil.copy(REPO_ROOT / ".gitignore", config.ROOT / ".gitignore")
        subprocess.run(["git", "add", "-A"], cwd=config.ROOT, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"],
                       cwd=config.ROOT, check=True)

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
        # SPEC T094, требование 10: approve читает SPEC.md с артефактной
        # ветки пульта для НЕ-self target, не из `self.repo()` (легаси-
        # адрес фиксации, ADR-0005 п.4 до правки — сохраняется для
        # `fixed_sha`, требование 9, но не для содержимого).
        from orchestrator import artifact_branch
        artifact_branch.commit_files(
            task_id, {f"tasks/{task_id}/SPEC.md": "# SPEC заглушка\n"},
            f"{task_id}: SPEC заглушка")
        capture(lambda: store.set_state(
            store.db(), task_id, "spec_gate", "operator",
            expected_state="spec_writing", detail="тест: вход в spec_gate"))
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


_STUB_VENV_PYTHON_PY = """#!{real_python}
import sys, subprocess
if sys.argv[1:4] == ["-m", "pip", "freeze"]:
    sys.stdout.write(open({lock!r}, encoding="utf-8").read())
    sys.exit(0)
sys.exit(subprocess.run([{real_python!r}] + sys.argv[1:]).returncode)
"""


def _provision_stub_venv(root: Path) -> None:
    """`.artel/venv` + `requirements.lock` для `root`, согласованные друг с
    другом (SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P): `orchestrator.runner.role_env`
    (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 4) с недавних пор
    ОТКАЗЫВАЕТ шагу роли без согласованного `.artel/venv` — той же
    проверкой (`orchestrator.stack.check_stack`), что уже гасит
    `RealPultGitTest`'овский in-process `doctor.preflight_checks` (см.
    `mock.patch` в `RealPultGitTest.setUp` — работает только ВНУТРИ этого
    интерпретатора, не пересекает границу `subprocess.Popen`, которой
    пользуется, например, `tasks/01M1NWCHVTYQ0M8PCJ1YJ2N78P/
    acceptance_tests/_sandbox.py` для настоящего отдельного процесса
    роли). Без этой заглушки шаг роли этой песочницы отказывает раньше,
    чем успевает начаться, — не по причине, которую проверяет тест.

    `bin/python`/`bin/python3` — не настоящий venv, а python-обёртка (не
    `sh`: PATH подставного окружения роли не обязан нести `cat`/`sh` —
    `_allowlisted_env` сужает его до манифеста стека): `-m pip freeze`
    отвечает буквальным содержимым СВОЕГО ЖЕ `requirements.lock` (сверка
    версий тривиально совпадает), любой другой вызов делегируется
    реальному `sys.executable` — код роли, и правда позвавший `python3`,
    получает рабочий интерпретатор, а не сломанную заглушку.
    """
    lock = root / "requirements.lock"
    shutil.copy(REPO_ROOT / "requirements.lock", lock)
    venv_bin = root / ".artel" / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    script = _STUB_VENV_PYTHON_PY.format(lock=str(lock), real_python=sys.executable)
    for name in ("python", "python3"):
        path = venv_bin / name
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP
                  | stat.S_IXOTH)


class RealPultGitTest(_GitFixationTmpRootTest):
    """Песочница self/артель (A7, generic-путь, ANSWER-1 вопрос 1): self
    (`config.DEFAULT_TARGET`) фиксируется тем же кодом, что и ЛЮБОЙ
    внешний target (`ExternalIntegrityIncidentBlocksRunTest` выше) —
    фиксация читает/пишет `config.PROJECTS/artel/tasks/<id>/`, не
    worktree кодовой ветки (та мирная площадка, `_fix_dogfood`, убрана
    вместе с однобраншевым флоу заведения задачи, `catalog._new_dogfood`).
    Содержимое, которое читает FSM (статус SPEC.md и т.п.), живёт
    отдельно — в артефактной ветке пульта (`artifact_branch.py`, M1) —
    `enter_spec_gate` пишет в ОБА места, как и `ExternalIntegrityIncidentBlocksRunTest.make_task`.
    """

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(ARTEL_TARGETS_YAML, encoding="utf-8")
        self.capture(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.capture(catalog.cmd_init)
        # SPEC T094, требование 10: артефактная ветка пульта и её чтение
        # (`artifact_source.resolve`) живут в РЕАЛЬНОМ git-репозитории
        # `config.ROOT`, не в подменённом одними путями `config` каталоге.
        subprocess.run(["git", "init", "-q", "-b", config.MAIN_BRANCH],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.email", "artel@example.invalid"],
                       cwd=config.ROOT, check=True)
        subprocess.run(["git", "config", "user.name", "artel tests"],
                       cwd=config.ROOT, check=True)
        shutil.copytree(REPO_ROOT / "templates", config.ROOT / "templates")
        shutil.copytree(REPO_ROOT / "skills", config.ROOT / "skills")
        shutil.copy(REPO_ROOT / ".gitignore", config.ROOT / ".gitignore")
        # T028: бриф роли developer/analyst читает docs/codebase-map.md и
        # CLAUDE.md из config.ROOT — без них шаг падает ENOENT до того, как
        # дойдёт до реального git, который эта песочница проверяет.
        (config.ROOT / "docs").mkdir()
        (config.ROOT / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (config.ROOT / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        # SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P: `.artel/venv` согласованный с
        # `requirements.lock` — иначе `runner.role_env` отказывает шагу
        # роли ДО его начала любому потребителю этой песочницы, кто
        # реально исполняет шаг отдельным процессом (см. докстринг
        # `_provision_stub_venv`). `.gitignore` уже скопирован выше —
        # `.artel/` в коммит ниже не попадёт, как и в настоящем пульте.
        _provision_stub_venv(config.ROOT)
        subprocess.run(["git", "add", "-A"], cwd=config.ROOT, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"],
                       cwd=config.ROOT, check=True)

        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(mock.patch.object(
            runner.keychain, "token", lambda slot: "tok-test"))
        self.patches.enter_context(mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: []))

        # SPEC T094: id — ULID, не предсказуемый "T001" — берём то, что
        # реально вернул `cmd_new`, а не литерал. `target` не передан —
        # `cmd_new` дефолтится в `config.DEFAULT_TARGET` (A7, требование 2).
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Git-фиксация")

    def repo(self) -> Path:
        """Артефактный репозиторий фиксации self/артели — тот же адрес,
        что `_fix_external`/`_read_external` (`config.PROJECTS/<target>`)."""
        return config.PROJECTS / config.DEFAULT_TARGET

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    capture = staticmethod(capture)

    def task_dir(self) -> Path:
        """Каталог артефактов задачи в РЕПО ФИКСАЦИИ (`fixation._fix_
        external` коммитит именно его целиком, A7 требование 2) — не
        путать с артефактной веткой пульта (M1), где живёт содержимое,
        которое читает FSM (`enter_spec_gate` пишет в оба места)."""
        return self.repo() / "tasks" / self.TASK

    def git_in_worktree(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(self.repo()), *args],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def head(self) -> str:
        """Головной sha репо фиксации self/артели (`fixation._fix_external`,
        A7 требование 2) — то же самое значение, что `tasks.fixed_sha`."""
        return gitcmd.head_sha(self.repo())

    def commit_task_dir(self, message: str = "артефакт") -> None:
        """Коммит МИМО обычной фиксации (`fixation.fix()` внутри `store.
        set_state`) — симулирует постороннюю правку репо фиксации (сама
        фиксация коммитит сама на каждом переходе и в этом явном коммите
        не нуждается, `ExternalTransitionCommitsTest` выше). Идентичность
        коммитера — явными `-c`, репо фиксации (`self.repo()`,
        `projects.init_artifact_repo`) не несёт собственного git-конфига."""
        self.git_in_worktree("add", "-A")
        self.git_in_worktree(
            "-c", f"user.name={fixation.FIXATION_AUTHOR_NAME}",
            "-c", f"user.email={fixation.FIXATION_AUTHOR_EMAIL}",
            "commit", "-q", "-m", message)

    def _seed_artifact_branch(self, rel: str, text: str, message: str) -> None:
        """Содержимое, которое читает FSM (`artifact_source.resolve`,
        SPEC T094 требование 10) — артефактная ветка пульта, ОТДЕЛЬНО от
        репо фиксации (`task_dir()`), тем же приёмом, что `Externa
        lIntegrityIncidentBlocksRunTest.make_task` выше."""
        from orchestrator import artifact_branch
        artifact_branch.commit_files(self.TASK, {rel: text}, message)

    def enter_spec_gate(self) -> str:
        self.task_dir().mkdir(parents=True, exist_ok=True)
        spec_text = SPEC_READY.format(task=self.TASK)
        (self.task_dir() / "SPEC.md").write_text(spec_text, encoding="utf-8")
        self._seed_artifact_branch(f"tasks/{self.TASK}/SPEC.md", spec_text,
                                   f"{self.TASK}: SPEC готов")
        self.capture(fsm.cmd_advance, self.TASK)
        return self.head()

    def enter_in_dev(self) -> str:
        sha = self.enter_spec_gate()
        self.capture(fsm.cmd_approve, self.TASK, sha)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "in_dev")
        # Обязательный артефакт роли developer (SPEC 01M1RQ12JVHE3PQYDFV1XPSTQ3,
        # требование 3) — в артефактную ветку, не только в репо фиксации
        # (`task_dir()`): `runner.role_cwd` материализует `tasks/<id>/` в
        # рабочий каталог роли РОВНО из этой ветки на каждом вызове
        # (`materialize_task_dir`), стирая любой файл, которого там нет —
        # без него штатный (rc=0) прогон `run_faked` честно ретраится
        # вместо одного запуска.
        self._seed_artifact_branch(f"tasks/{self.TASK}/PLAN.md",
                                   PLAN_READY.format(task=self.TASK),
                                   f"{self.TASK}: PLAN заглушка")
        # `PLAN.md` выше уже `status: ready` — «легитимный первый вход»
        # (`auto._is_legit_first_entry_detail`, detail «SPEC schema_version
        # …» записи `state -> in_dev` от `cmd_approve` выше) не держит
        # рубеж переделки для готового артефакта (`auto._rework_gate_
        # blocks`), и потребитель, доводящий цикл ДО реального `auto`
        # (не только `run_faked`), продвигается по нему СРАЗУ, без единого
        # шага developer, — до `review` (`_pre_advance_step`, требование 2
        # SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906). Без `REVIEW.md` в артефактной
        # ветке та же деградация из докстринга выше повторяется для роли
        # reviewer уже НА review — заглушка того же класса, что и PLAN.md,
        # закрывает её: `status: draft` вне `config.REVIEW_VERDICTS` не
        # даёт `review` перейти дальше молча (не расходует лишний прогон
        # роли), а файл уже на месте в рабочем каталоге роли к моменту
        # проверки обязательного артефакта (обнаружено
        # 01M1NWCHVTYQ0M8PCJ1YJ2N78P: без него reviewer ретраился так же,
        # как developer до правки PLAN.md выше).
        self._seed_artifact_branch(f"tasks/{self.TASK}/REVIEW.md",
                                   REVIEW_DRAFT.format(task=self.TASK),
                                   f"{self.TASK}: REVIEW заглушка")
        # Гейт ёмкости diff (05.09, fsm_advance._capacity_gate_refuses)
        # сверяет `MAIN_BRANCH...t["branch"]` в `config.ROOT` (`gitcmd.git`
        # всегда работает там, не в `self.repo()` — тот отдельный
        # git-репозиторий фиксации `config.PROJECTS/<target>`, см.
        # докстринг `RealPultGitTest`) уже на входе в `in_dev -> review`;
        # в реальном потоке ветка задачи к этому моменту всегда существует
        # (её заводит `workspace.ensure` первым же реальным шагом роли), но
        # этот хелпер доводит задачу до `in_dev` в обход роли — без ветки
        # `git diff` отвечает `fatal: bad revision`, и гейт fail-closed
        # отказывает КАЖДОМУ переходу из `in_dev` (обнаружено
        # 01M1NWCHVTYQ0M8PCJ1YJ2N78P: `auto` останавливался раньше, чем
        # успевал начать шаг роли). `git branch` на `MAIN_BRANCH` — то же
        # самое действие, каким `workspace.ensure` завела бы её сама
        # (`workspace.py::ensure`, ветка ещё не в git — "заводится от
        # config.MAIN_BRANCH тем же действием, что и сам worktree").
        # Только если ветки ЕЩЁ нет: некоторые потребители этого хелпера
        # (`tests/test_timeout_checkpoint.py::_WorktreeCheckpointTest`)
        # заводят worktree САМИ, ДО вызова `enter_in_dev` — ветка тогда
        # уже существует и стоит checked out в этом worktree; `git branch
        # -f` на такой ветке отказывает (128: «cannot force update the
        # branch... checked out»). `branch_exists` — та же проверка, что
        # уже применяет сама `workspace.ensure` для решения между `add -b`
        # и `add` без него.
        branch = store.get_task(store.db(), self.TASK)["branch"]
        if branch and not gitcmd.branch_exists(branch):
            subprocess.run(["git", "branch", branch, config.MAIN_BRANCH],
                           cwd=config.ROOT, check=True, capture_output=True)
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
        with mock.patch.object(
                runner, "spawn_agent",
                side_effect=claude_only_popen(FakeProc(["готово\n"]))) as popen:
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
        дефектом асимметрии, который T033 закрывает.

        Статус SPEC.md (SPEC T048) читается с ВЕТКИ задачи, не с диска —
        «ready» обязан быть сперва закоммичен, иначе advance его просто не
        увидит («ещё не ready»), а не дойдёт до сверки чистоты. Грязная
        копия здесь — правка ПОВЕРХ уже закоммиченного ready-SPEC.md.
        """
        spec_text = SPEC_READY.format(task=self.TASK)
        self.task_dir().mkdir(parents=True, exist_ok=True)
        (self.task_dir() / "SPEC.md").write_text(spec_text, encoding="utf-8")
        self.commit_task_dir()
        # Статус SPEC.md читается с артефактной ветки пульта (SPEC T094,
        # требование 10; `enter_spec_gate` выше) — без неё advance
        # отказывает раньше сверки чистоты («ещё не ready»), не дойдя до
        # предмета этого теста.
        self._seed_artifact_branch(f"tasks/{self.TASK}/SPEC.md", spec_text,
                                   f"{self.TASK}: SPEC готов")
        (self.task_dir() / "SPEC.md").write_text(
            spec_text + "\nправка мимо коммита\n", encoding="utf-8")
        # SPEC.md правлен, но правка НЕ закоммичена — грязная копия tasks/<id>.

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_writing", "переход по грязной копии не случился")
        fixed = [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                 if r["action"] == "sha зафиксирован"]
        self.assertEqual(fixed, [], "грязный переход фиксацию не журналит")
        refused = [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                   if "не закоммичен" in r["detail"]]
        self.assertTrue(refused, "отказ по грязной копии журналится отдельно")


class DogfoodTransitionJournalsCodeBranchShaTest(RealPultGitTest):
    """Требование 1 (tasks/01M1P9RJVYHTAC087J4B2CAR44): переход self/
    артели журналит ТАКЖЕ поле `код=` — sha головы КОДОВОЙ ветки задачи
    (`config.ROOT`, где для self реально живёт код), не путать с `sha=`
    (голова репо фиксации `config.PROJECTS/artel`, `DogfoodTransitionJournals
    ShaTest` выше — эта задача его не убирает, только перестаёт им
    пользоваться как базой diff, требование 4)."""

    def test_journal_carries_code_branch_sha_distinct_from_fixation_sha(self):
        """Кодовая ветка задачи — реальная ветка в `config.ROOT`
        (`self.root`), с отдельным коммитом, чтобы её sha заведомо
        отличался от sha репо фиксации, который коммитит тот же переход
        (`fixation._fix_external`) — совпадение значений сделало бы тест
        неразличимым со старым (регрессным) поведением.

        Ловит мутацию: `record_fixation` не добавляет `код=` для default
        target (текущий регресс) — поле в `detail` отсутствует вовсе.
        """
        branch = store.task_branch(store.db(), self.TASK)
        self.git("branch", branch)
        self.git("checkout", branch)
        (self.root / "module.py").write_text("код\n", encoding="utf-8")
        self.git("add", "module.py")
        self.git("commit", "-q", "-m", "код")
        code_sha = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", config.MAIN_BRANCH)

        fixation_sha = self.enter_spec_gate()

        self.assertNotEqual(
            code_sha, fixation_sha,
            "sha кодовой ветки совпал со sha репо фиксации — тест ничего "
            "не доказывает")
        entries = [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                  if r["action"] == "sha зафиксирован"]
        self.assertEqual(len(entries), 1)
        self.assertIn(f"код={code_sha}", entries[0])
        self.assertIn(fixation_sha, entries[0], "sha репо фиксации не убран")


class ApproveByShaTest(RealPultGitTest):
    """Требование 4: approve с привязкой к sha."""

    def test_approve_without_sha_transitions_on_matching_clean_fixation(self):
        """SPEC 01M1SHJX22EMEP4AJ9FFJJ09DC, AC-2: до этой задачи `approve`
        без аргумента НИКОГДА не переводил состояние (формулировка этого
        метода до правки) — он безусловно печатал зафиксированный sha и
        ждал, чтобы Оператор набрал его руками, даже когда живое
        состояние уже совпадало с зафиксированным и копия была чистая.
        Теперь на этом совпадении `approve` сверяет sha сам (той же
        `fixation.read()`, что раньше служила только для подсказки) и
        проводит переход без ручного набора — расхождение/грязная копия
        по-прежнему НЕ пропускают approve (`test_ac1_diverged_or_dirty_
        live_sha_blocks_approve.py`, `test_ac3_diverged_or_dirty_refuses_
        named.py` в приёмочных тестах задачи) — здесь меняется только
        формулировка сценария «живое совпадение», не сам принцип
        инварианта 25 (FSM решает по зафиксированным хэшам)."""
        sha = self.enter_spec_gate()

        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertIn(sha, out)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "in_dev", "живое совпадение и чистая копия "
                         "обязаны переводить состояние без ручного sha")

    def test_approve_without_sha_on_diverged_fixation_is_refused_and_names_both_shas(self):
        """SPEC 01M1SHJX22EMEP4AJ9FFJJ09DC, AC-3 (постоянное покрытие —
        REVIEW.md итерации 1, R1-F3: приёмочная планка задачи эфемерна,
        `confirm_fixation` без такого теста в `tests/` осталась бы без
        регрессионной защиты после мержа). Посторонний коммит поверх
        зафиксированного sha — approve без sha обязан отказать, назвав
        ОБА значения, и не трогать состояние.

        Заодно регрессия R1-F2 (та же итерация): подсказка повтора
        обязана называть ЖИВОЙ sha (с которым явный путь `approve <id>
        <sha>` реально сравнивает — `current.startswith(sha)`), а не
        зафиксированный — иначе подсказанная команда детерминированно
        проваливается второй раз.

        Ловит мутацию: подстановка `{fixed or current}` вместо
        `{current}` в подсказке повтора (регресс R1-F2) — ассерт на
        `f"approve {self.TASK} {live_sha}"` в выводе не пройдёт."""
        fixed_sha = self.enter_spec_gate()
        (self.task_dir() / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")
        self.commit_task_dir("посторонняя правка мимо approve")
        live_sha = self.head()
        self.assertNotEqual(fixed_sha, live_sha,
                            "тест ничего не докажет без реального расхождения")

        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertIn(fixed_sha, out, "зафиксированный sha не назван в отказе")
        self.assertIn(live_sha, out, "живой sha не назван в отказе")
        self.assertIn(f"approve {self.TASK} {live_sha}", out,
                      "подсказка повтора обязана называть живой sha")
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate", "отклонённый approve не двигает состояние")

    def test_approve_without_sha_on_dirty_copy_is_refused_and_state_unchanged(self):
        """SPEC 01M1SHJX22EMEP4AJ9FFJJ09DC, AC-3 (постоянное покрытие,
        R1-F3) — живой sha совпадает с зафиксированным, но рабочая копия
        репо фиксации грязная (правка без коммита): approve без sha
        обязан отказать по грязноте, а не пройти только по совпадению
        sha.

        Ловит мутацию: пропуск проверки `clean` при совпадающем sha
        (переход считался бы подтверждённым по одному лишь совпадению
        sha) — ассерт на неизменённое состояние задачи не пройдёт."""
        fixed_sha = self.enter_spec_gate()
        (self.task_dir() / "SPEC.md").write_text(
            "правка без коммита\n", encoding="utf-8")
        self.assertEqual(self.head(), fixed_sha,
                         "sha не должен был сдвинуться без коммита")

        out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertIn("грязн", out, "отказ обязан называть грязную копию")
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate", "отклонённый approve не двигает состояние")

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
        (self.task_dir() / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")
        self.run_faked()  # инцидент целостности -> escalated, escalated_from=in_dev
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        # Сама эскалация уже зафиксировала тронутое состояние (`store.
        # set_state` -> `record_fixation` -> `fixation.fix()` коммитит
        # репо фиксации целиком на КАЖДОМ переходе, включая переход в
        # escalated) — репо фиксации здесь уже чисто, отдельный коммит
        # «подтверждено Оператором» не нужен (в отличие от старого
        # догфуд-флоу, где `fix()` только читала, не коммитила).

        self.capture(fsm.cmd_approve, self.TASK, self.head())

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "in_dev", "escalated_from вернул задачу в in_dev")


class IntegrityIncidentBlocksRunTest(RealPultGitTest):
    """Требование 5: сверка при старте шага — изменение после approve отказывает."""

    def test_uncommitted_change_after_approve_blocks_the_run(self):
        self.enter_in_dev()
        (self.task_dir() / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")

        out, popen = self.run_faked()

        self.assertEqual(self.claude_launches(popen), [])
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        self.assertIn("инцидент целостности", out)

    def test_committed_change_after_approve_also_blocks_the_run(self):
        """Разошедшийся sha — не только грязная копия, но и посторонний коммит."""
        self.enter_in_dev()
        (self.task_dir() / "SPEC.md").write_text(
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

        (self.task_dir() / "PLAN.md").write_text(
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
        (self.task_dir() / "PLAN.md").write_text(
            "самозванный PLAN\n", encoding="utf-8")
        self.commit_task_dir("чужая правка мимо гейта")

        with mock.patch.object(fixation, "check_integrity",
                               lambda conn, task_id: None):
            _, popen = self.run_faked()

        self.assertEqual(len(self.claude_launches(popen)), 1)


class ApproveShaHintTest(unittest.TestCase):
    """`fixation.approve_sha_hint` (tasks/01M1GHZTX9YEPF0TY46QWZAGD8/SPEC.md,
    требование 1) — узел общий для всех точек печати подсказки `approve`
    с sha; юниты здесь чистые (мокают `fixation.read`), сценарии с
    настоящим git — классы ниже и локальные приёмочные тесты AC-1.
    """

    def test_empty_when_fixation_not_available(self):
        """Фиксации нет (`fixation.read` вернул `available=False`) —
        подсказка остаётся пустой строкой, вырожденный случай без git.

        Ловит мутацию: если проверка `available` уберётся и функция
        начнёт подставлять `current` независимо от него, здесь вместо
        пустой строки окажется мусорное значение первого элемента кортежа.
        """
        with mock.patch.object(fixation, "read", return_value=("", False)):
            self.assertEqual(fixation.approve_sha_hint("T1", "artel"), "")

    def test_leading_space_and_sha_when_fixed(self):
        """Фиксация есть — подсказка равна ровно пробелу и полному sha,
        готовая ко вставке хвостом в строку команды.

        Ловит мутацию: если ведущий пробел потеряется (конкатенация
        `sha` без разделителя) или в подсказку попадёт часть sha вместо
        полного значения, сравнение с ` {sha}` не пройдёт.
        """
        sha = "a" * 40
        with mock.patch.object(fixation, "read", return_value=(sha, True)):
            self.assertEqual(fixation.approve_sha_hint("T1", "artel"), f" {sha}")


class AutoStopHintIncludesShaOnEveryApproveNeedsShaStateTest(RealPultGitTest):
    """Требование 1 (категория «остановки auto»): локальный приёмочный
    тест AC-1 проверяет только `merge_gate` — здесь то же самое для
    остальных трёх состояний `fsm.APPROVE_NEEDS_SHA` (`spec_gate`,
    `acceptance`, `escalated`), которые тоже несут `{sha}` в `config.
    AUTO_STOP` и форматируются тем же `auto.auto_stop_advice`.
    """

    def force_state(self, state: str) -> str:
        conn = store.db()
        current = store.get_task(conn, self.TASK)["state"]
        store.set_state(conn, self.TASK, state, "operator",
                        expected_state=current, detail="тест: подготовка")
        return self.head()

    def _assert_hint_has_sha(self, out: str, sha: str) -> None:
        hint_lines = [line for line in out.splitlines()
                     if "artel.py approve" in line]
        self.assertTrue(hint_lines,
                        f"строка подсказки не найдена в выводе auto:\n{out}")
        self.assertTrue(any(sha in line for line in hint_lines),
                        f"зафиксированный sha {sha} не найден в подсказке:\n{out}")

    def test_spec_gate_auto_stop_hint_includes_full_fixed_sha(self):
        """Остановка `auto` на `spec_gate` печатает подсказку `approve`
        с зафиксированным sha этого состояния.

        Ловит мутацию: если `{sha}` в `config.AUTO_STOP["spec_gate"]`
        забудут подставить (или `auto_stop_advice` не станет вычислять
        `sha_hint` для этого состояния), подсказка останется без sha и
        assertTrue на `any(sha in line ...)` упадёт.
        """
        sha = self.enter_spec_gate()

        out = self.capture(auto.cmd_auto, self.TASK)

        self._assert_hint_has_sha(out, sha)

    def test_acceptance_auto_stop_hint_includes_full_fixed_sha(self):
        """Остановка `auto` на `acceptance` печатает подсказку `approve`
        с зафиксированным sha этого состояния.

        Ловит мутацию: если ветку `acceptance` в `auto_stop_advice`
        забудут включить в список состояний, для которых считается
        `sha_hint`, подсказка останется без sha.
        """
        sha = self.force_state("acceptance")

        out = self.capture(auto.cmd_auto, self.TASK)

        self._assert_hint_has_sha(out, sha)

    def test_escalated_auto_stop_hint_includes_full_fixed_sha(self):
        """Эскалация не по потолку бюджета — `AUTO_STOP["escalated"]`
        несёт `{sha}`; эскалация ПО потолку подменяется на `AUTO_STOP_
        BUDGET` (следующая команда — `budget`, не `approve`) и своего
        теста не требует — она не называет approve вовсе.

        Ловит мутацию: если `{sha}` в `config.AUTO_STOP["escalated"]`
        забудут подставить, подсказка останется без sha и `_assert_hint_
        has_sha` не найдёт его в выводе.
        """
        sha = self.force_state("escalated")

        out = self.capture(auto.cmd_auto, self.TASK)

        self._assert_hint_has_sha(out, sha)


class AutogateMergeGateHintIncludesShaTest(RealPultGitTest):
    """Требование 1 (категория «переход в merge_gate»): вторая точка входа
    в `merge_gate` — автогейт (`fsm_autogate._maybe_autogate_acceptance`,
    не ручной `fsm._cmd_approve`, который уже покрыт AC-1) — несёт то же
    самое `{sha}`.

    Условия автогейта (`_autogate_conditions`) подменены на «всё
    выполнено»: предмет теста — печать подсказки после перехода, не сама
    политика допуска (та своя, `tests/test_...` для `fsm_autogate.py` не
    заводился отдельно — тонкая обвязка, перенесённая из `fsm.py` без
    изменений, T091).
    """

    def test_autogate_transition_hint_includes_full_fixed_sha(self):
        """Автоматический переход `acceptance -> merge_gate` через
        `_maybe_autogate_acceptance` печатает подсказку `approve` с
        зафиксированным sha, как и ручной путь из AC-1.

        Ловит мутацию: если `{sha}` забудут подставить именно в этой
        точке печати (второй сайт, отдельный от `fsm._cmd_approve`),
        подсказка автогейта останется без sha, а `fsm._cmd_approve`
        по-прежнему будет его печатать — асимметрия, которую поймает
        только тест именно этого сайта.
        """
        self.enter_in_dev()
        conn = store.db()
        store.set_state(conn, self.TASK, "acceptance", "operator",
                        expected_state="in_dev", detail="тест: подготовка")
        t = store.get_task(conn, self.TASK)
        fixed_sha = t["fixed_sha"]

        with mock.patch.object(gates, "policy", return_value=gates.AUTO), \
             mock.patch.object(fsm_autogate, "_autogate_conditions",
                               return_value=(["ok"], None)):
            out = self.capture(fsm_autogate._maybe_autogate_acceptance,
                               conn, self.TASK, t, self.task_dir(), 1)

        self.assertEqual(store.get_task(conn, self.TASK)["state"], "merge_gate")
        hint_lines = [line for line in out.splitlines()
                     if "artel.py approve" in line]
        self.assertTrue(hint_lines,
                        f"строка подсказки не найдена в выводе автогейта:\n{out}")
        self.assertTrue(any(fixed_sha in line for line in hint_lines),
                        f"зафиксированный sha {fixed_sha} не найден в "
                        f"подсказке:\n{out}")


class RunnerEscalationHintsIncludeShaTest(RealPultGitTest):
    """Требование 1 (категория «статусные подсказки эскалаций с
    фиксацией»): обе точки `runner._cmd_run`, которые сами уводят задачу
    в `escalated`, несут зафиксированный sha — инцидент целостности
    раньше печатал буквальный плейсхолдер `<sha>` вместо значения.
    """

    def test_integrity_incident_hint_includes_full_fixed_sha(self):
        """Инцидент целостности (артефакт подменён мимо гейта) уводит
        задачу в `escalated` и печатает подсказку `approve` с реальным
        зафиксированным sha вместо буквального плейсхолдера `<sha>`.

        Ловит мутацию: если `runner._cmd_run` на этом пути вернёт
        подсказку без вычисленного `approve_sha_hint` (старое поведение
        — буквальный `<sha>` или пустая подсказка), sha в выводе не
        найдётся.
        """
        self.enter_in_dev()
        (self.task_dir() / "SPEC.md").write_text(
            "подмена мимо гейта\n", encoding="utf-8")

        out, popen = self.run_faked()

        self.assertEqual(self.claude_launches(popen), [])
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        # sha берётся ПОСЛЕ эскалации, не до: сам переход в escalated уже
        # зафиксировал тронутое состояние (`record_fixation` внутри
        # `store.set_state` коммитит репо фиксации целиком на каждом
        # переходе, включая escalated) — подсказка обязана называть ИМЕННО
        # этот новый sha, не тот, что был зафиксирован до подмены.
        sha = self.head()
        hint_lines = [line for line in out.splitlines()
                     if "artel.py approve" in line]
        self.assertTrue(hint_lines,
                        f"строка подсказки не найдена в выводе:\n{out}")
        self.assertTrue(any(sha in line for line in hint_lines),
                        f"зафиксированный sha {sha} не найден в подсказке:\n{out}")

    def test_agent_failure_escalation_hint_includes_full_fixed_sha(self):
        """Провал агента после исчерпанных попыток уводит задачу в
        `escalated` и печатает подсказку `approve` с зафиксированным sha
        — второй сайт эскалации в `runner._cmd_run`, отдельный от
        инцидента целостности.

        Ловит мутацию: если sha подставляется только на пути инцидента
        целостности, а этот сайт (провал агента) забудут завести на тот
        же `approve_sha_hint`, подсказка здесь останется без sha.
        """
        sha = self.enter_in_dev()

        with mock.patch.object(
                runner, "run_agent_once",
                return_value=("failed", "тестовый сбой", "session_limit")):
            out = self.capture(runner.cmd_run, self.TASK)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "escalated")
        hint_lines = [line for line in out.splitlines()
                     if "artel.py approve" in line]
        self.assertTrue(hint_lines,
                        f"строка подсказки не найдена в выводе:\n{out}")
        self.assertTrue(any(sha in line for line in hint_lines),
                        f"зафиксированный sha {sha} не найден в подсказке:\n{out}")


class ApproveAcceptsFixedShaPrefixTest(RealPultGitTest):
    """`fsm.confirm_fixation` (tasks/01M1GHZTX9YEPF0TY46QWZAGD8/SPEC.md,
    требования 2-3): свой юнит-контур поверх настоящего git, за пределами
    локальных приёмочных AC-2..AC-4 — те же сценарии, но с настоящей
    веткой задачи, не только `spec_gate` из их песочницы.
    """

    def test_prefix_of_fixed_sha_transitions_like_the_full_value(self):
        """`approve` с минимально допустимым префиксом (`APPROVE_SHA_
        PREFIX_MIN` символов) зафиксированного sha на реальной ветке
        задачи переводит `spec_gate -> in_dev` так же, как полный sha.

        Ловит мутацию: если сравнение снова станет строгим `sha ==
        current` вместо `current.startswith(sha)` после проверки длины,
        approve с префиксом отклонится и состояние останется `spec_gate`.
        """
        sha = self.enter_spec_gate()
        prefix = sha[:fsm.APPROVE_SHA_PREFIX_MIN]

        self.capture(fsm.cmd_approve, self.TASK, prefix)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "in_dev")

    def test_value_of_min_length_not_a_prefix_is_refused_with_fixed_sha(self):
        """Значение допустимой длины (`APPROVE_SHA_PREFIX_MIN` символов),
        которое НЕ является префиксом зафиксированного sha, отклоняется
        прежним отказом «не совпадает» с печатью зафиксированного sha,
        состояние не двигается.

        Ловит мутацию: если проверка длины подменит собой сравнение
        содержимого (любое значение нужной длины проходит), approve с
        заведомо неверным значением ошибочно переведёт задачу в `in_dev`.
        """
        sha = self.enter_spec_gate()
        wrong = ("0" if sha[0] != "0" else "1") + "0" * (
            fsm.APPROVE_SHA_PREFIX_MIN - 1)
        self.assertFalse(sha.startswith(wrong))

        with self.assertRaises(SystemExit) as ctx:
            self.capture(fsm.cmd_approve, self.TASK, wrong)

        self.assertIn(sha, str(ctx.exception))
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate")

    def test_value_shorter_than_min_length_is_refused_by_name(self):
        """Значение короче `APPROVE_SHA_PREFIX_MIN` символов отклоняется
        отдельным именованным отказом про минимальную длину — раньше
        проверки совпадения, с другим текстом, чем «не совпадает».

        Ловит мутацию: если проверка длины уберётся или переставится
        после сравнения по `startswith` (короткая строка — валидный
        префикс любого sha), короткое значение либо пройдёт как
        approve, либо будет отклонено текстом «не совпадает», а не
        именованным отказом про длину.
        """
        sha = self.enter_spec_gate()
        too_short = sha[:fsm.APPROVE_SHA_PREFIX_MIN - 1]

        with self.assertRaises(SystemExit) as ctx:
            self.capture(fsm.cmd_approve, self.TASK, too_short)

        message = str(ctx.exception)
        self.assertNotIn("не совпадает с зафиксированным", message)
        self.assertIn(str(fsm.APPROVE_SHA_PREFIX_MIN), message)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "spec_gate")


if __name__ == "__main__":
    unittest.main()
