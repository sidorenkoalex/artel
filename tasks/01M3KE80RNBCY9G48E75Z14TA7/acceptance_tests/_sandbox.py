"""Общая песочница планки 01M3KE80RNBCY9G48E75Z14TA7 — закрытие задачи и
снимок `refs/artifacts/<id>`.

Тонкая надстройка сценария над `tests.sandbox.RealGitSandbox` (скил
test-authoring, «Лёгкая песочница переходов»): своих копий
`disk_backed_*`/`advance_from_in_dev` здесь нет и быть не может — предмет
планки и есть СОДЕРЖИМОЕ ссылки `refs/artifacts/<id>` в origin целевого и
момент её появления относительно удаления веток, то есть настоящий git, а
не патчи чтения веток.

Устройство сценария (то же, что уже используют
`tests/test_fsm_merge_gate_done_snapshot.py` и планка T094): `self.root` —
пульт с bare-origin; `self.target_origin` — bare-репозиторий, имитирующий
форндж целевого (сеть не участвует); `self.target_workspace` —
`config.PROJECTS/<target>/workspace`, рабочий клон целевого, куда мержится
кодовая ветка задачи. Артефактная ветка задачи (`tasks/<id>/`) живёт в
пульте.

Фикстура каталога приёмочных тестов лежит здесь, а не в `test_*.py`:
guard разбирает AC-разметку и пометки только по `test_*.py`
(`scripts/guard.py::scan_acceptance_tests`), и литерал-фикстура с
`# AC-n: manual` в тестовом файле читался бы как настоящая пометка этой
задачи.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import (artifact_branch, ci, config,  # noqa: E402
                          fsm_merge_gate, snapshot, store)
from tests.sandbox import RealGitSandbox, resilient_tmp_cleanup  # noqa: E402

EXTERNAL_TARGET = "extproj"

TARGETS_YAML = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: https://example.invalid/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
  {EXTERNAL_TARGET}:
    forge: github
    url: https://example.invalid/{EXTERNAL_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {EXTERNAL_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

#: Первое предложение «Контекста» фикстурного SPEC.md — то самое S из
#: AC-10/AC-11. Вторая фраза нужна, чтобы отличать «полное первое
#: предложение» от «весь раздел целиком».
FIXTURE_GIST_SENTENCE = "Снимок закрытия несёт ретроспективу задачи."

FIXTURE_SPEC = (
    "---\n"
    "type: spec\n"
    "status: ready\n"
    "---\n"
    "\n"
    "# SPEC: фикстура планки\n"
    "\n"
    "## Контекст\n"
    "\n"
    + FIXTURE_GIST_SENTENCE
    + " Второе предложение в «Суть» не попадает.\n"
    "\n"
    "## Требования\n"
    "\n"
    "1. Фикстура.\n"
)

#: Имена тестовых методов фикстурного каталога приёмочных тестов. Собраны
#: списком и подставляются форматированием: написанные прямо в исходнике
#: строки `def test_...` посчитались бы `guard.count_test_methods` как
#: тесты САМОЙ этой планки (он читает все `*.py`, включая `_sandbox.py`).
FIXTURE_TEST_METHODS = ("alpha", "beta", "gamma")
FIXTURE_TEST_COUNT = len(FIXTURE_TEST_METHODS)
FIXTURE_MANUAL_COUNT = 1
FIXTURE_SKIP_COUNT = 1


def fixture_plank_source() -> str:
    """Исходник фикстурного `test_*.py`: три тестовых метода, одна пометка
    `manual`, одна пометка `skip` — числа `FIXTURE_*_COUNT` выше.

    Номера критериев фикстуры заведомо не пересекаются с номерами этой
    задачи (сотня и выше): счётчикам номер безразличен, а спутать чужую
    пометку со своей — нет.
    """
    head = (
        "import unittest\n"
        "\n"
        "\n"
        "# AC-101: manual — фикстура планки, пометка для счётчика manual\n"
        "# AC-102: skip — фикстура планки, пометка для счётчика skip\n"
        "class FixturePlank(unittest.TestCase):\n"
    )
    body = "".join("    def test_ac{}_{}(self):\n        pass\n\n".format(i, name)
                   for i, name in enumerate(FIXTURE_TEST_METHODS, start=103))
    return head + body


def fixture_artifact_files(task_id: str) -> dict:
    """`tasks/<id>/` артефактной ветки: SPEC.md с известным первым
    предложением «Контекста» и каталог приёмочных тестов с известными
    числами тестов/manual/skip."""
    return {
        f"tasks/{task_id}/SPEC.md": FIXTURE_SPEC,
        f"tasks/{task_id}/acceptance_tests/test_fixture.py":
            fixture_plank_source(),
    }


class ClosingSnapshotSandbox(RealGitSandbox):
    """Пульт + внешний target с bare-origin; помощники чтения снимка
    `refs/artifacts/<id>` и двух путей закрытия задачи (мерж и `kill`)."""

    TARGET = EXTERNAL_TARGET
    TITLE = "Задача внешнего target"
    CI_NOTE = "зелёный (тест)"

    def setUp(self):
        super().setUp()
        # Окружение строится фикстурой сценария: карта целевых пишется во
        # временный каталог песочницы (`config.TARGETS` патчен туда
        # `TmpRootTest`), настоящие `targets.yaml`/`roles.yaml`/`skills/`
        # репозитория не читаются вовсе — их правка Оператором планку не
        # касается. Схему БД ставит `RealGitSandbox.setUp`, задачи заводятся
        # напрямую через `store.insert_task`, поэтому `catalog.cmd_init`
        # здесь не нужен.
        config.TARGETS.write_text(TARGETS_YAML, encoding="utf-8")

        # Bare-origin пульта: артефактная ветка пушится туда, и без
        # настроенного origin git отказывает раньше предмета теста.
        pult_origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pult_origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(pult_origin))
        self.git("remote", "add", "origin", str(pult_origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.target_origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b",
                        config.MAIN_BRANCH, str(self.target_origin)],
                       check=True, capture_output=True, text=True)

        self.target_workspace = config.PROJECTS / self.TARGET / "workspace"
        self.target_workspace.mkdir(parents=True)
        self.wgit("init", "-q", "-b", config.MAIN_BRANCH)
        self.wgit("remote", "add", "origin", str(self.target_origin))
        self.wgit("config", "user.email", "artel@example.invalid")
        self.wgit("config", "user.name", "artel tests")
        (self.target_workspace / "marker.txt").write_text("main\n",
                                                          encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", "init")
        self.wgit("push", "-q", "origin", config.MAIN_BRANCH)

        ci_patcher = mock.patch.object(ci, "branch_status",
                                       lambda branch: (True, self.CI_NOTE))
        ci_patcher.start()
        self.addCleanup(ci_patcher.stop)

    # --- git-помощники ----------------------------------------------------

    def wgit(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.target_workspace,
                             capture_output=True, text=True)
        assert res.returncode == 0, f"git {' '.join(args)}: {res.stderr}"
        return res.stdout

    def origin_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.target_origin), *args],
                              capture_output=True, text=True)

    def break_target_origin(self) -> None:
        """Origin целевого недостижим — push снимка отказывает (тот же
        приём, что `tasks/T094/acceptance_tests/test_ac15_snapshot_push_
        failure.py`: сеть не участвует, несуществующий локальный путь
        отказывает тем же кодом возврата)."""
        self.wgit("remote", "set-url", "origin",
                  "/nonexistent/does-not-exist.git")

    # --- чтение снимка ----------------------------------------------------

    def snapshot_ref(self, task_id: str) -> str:
        return snapshot.SNAPSHOT_REF_TMPL.format(task_id=task_id)

    def snapshot_ref_exists(self, task_id: str) -> bool:
        return self.origin_git("show-ref", "--verify", "--quiet",
                               self.snapshot_ref(task_id)).returncode == 0

    def snapshot_retro_text(self, task_id: str) -> str:
        """Текст ретроспективы ИЗ СНИМКА — `git show` по ссылке
        `refs/artifacts/<id>` bare-репозитория целевого."""
        rel = snapshot.RETRO_REL_TMPL.format(task_id=task_id)
        res = self.origin_git("show", f"{self.snapshot_ref(task_id)}:{rel}")
        assert res.returncode == 0, (
            f"снимок {task_id} не несёт {rel}: {res.stderr.strip()}")
        return res.stdout

    def snapshot_commit_subject(self, task_id: str) -> str:
        res = self.origin_git("log", "-1", "--format=%s",
                              self.snapshot_ref(task_id))
        assert res.returncode == 0, (
            f"снимок {task_id} не читается: {res.stderr.strip()}")
        return res.stdout.strip()

    # --- заведение задач и пути закрытия ----------------------------------

    def code_branch(self, task_id: str) -> str:
        return f"task/{task_id.lower()}-plank"

    def seed_task(self, task_id: str, state: str, files: dict | None = None,
                  *, is_canary: bool = False) -> str:
        """Строка задачи внешнего target напрямую в БД (тем же приёмом, что
        `tests/test_multitarget.py`) + её артефактная ветка в пульте."""
        store.insert_task(store.db(), task_id, self.TITLE, state,
                          self.code_branch(task_id), self.TARGET,
                          config.DEFAULT_BUDGET_USD, is_canary=is_canary)
        artifact_branch.commit_files(
            task_id, files if files is not None
            else {f"tasks/{task_id}/PLAN.md": "план\n"},
            f"{task_id}: артефакты задачи")
        return self.code_branch(task_id)

    def seed_merge_gate_task(self, task_id: str, files: dict | None = None,
                             *, is_canary: bool = False) -> str:
        """Задача на гейте merge: строка БД, артефактная ветка пульта и
        кодовая ветка с одним коммитом в клоне целевого."""
        branch = self.seed_task(task_id, "merge_gate", files,
                                is_canary=is_canary)
        self.wgit("checkout", "-q", "-b", branch)
        (self.target_workspace / "feature.txt").write_text(
            "код фичи\n", encoding="utf-8")
        self.wgit("add", "feature.txt")
        self.wgit("commit", "-q", "-m", f"{task_id}: код фичи")
        return branch

    def approve_merge(self, task_id: str) -> tuple:
        """Тело окна `merge_gate -> done` напрямую — тем же приёмом, что
        `tests/test_fsm_merge_gate_done_snapshot.py`: минуя lease/мьютекс/
        подтверждение sha, которых это тело не касается. `confirmed_ci_note`
        подставляется явно — его дал бы вызывающий цикл после зелёного
        `ci.branch_status`, замоканного в `setUp`."""
        t = store.get_task(store.db(), task_id)
        return fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), task_id, "merge_gate", t,
            confirmed_ci_note=self.CI_NOTE)
