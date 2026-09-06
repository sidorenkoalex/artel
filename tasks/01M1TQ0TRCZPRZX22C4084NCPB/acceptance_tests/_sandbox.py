"""Общая песочница приёмочных тестов 01M1TQ0TRCZPRZX22C4084NCPB (ADR-0015 —
порядок `in_dev -> verifying -> review -> acceptance -> merge_gate`).

Лёгкая песочница без настоящего git (`fake_git` + диск как источник
артефактов) — тот же приём, что `tests/test_review_freshness.py::
ReviewFreshnessScenarioTest`/`tests/test_auto_cycle.py::AutoCycleTest`:
FSM вызывается напрямую (`fsm.cmd_advance`/`cmd_reject`), рубежи
`in_dev` (подтяжка main, гейт зон/ёмкости, лок планки, гейт «замечания
не отработаны») деградируют на свой безопасный вырожденный случай
(«git не ответил / нечего сверять — не отказ»), а спуном под тестом
проверяется не САМА логика гейта (не в объёме этой задачи — SPEC
«Не входит»), а МЕСТО, где он стоит в маршруте (какой переход его
вызывает и не вызывает ли его повторно другой переход).

Не тестовый файл: имя не совпадает с шаблоном `test*.py`, которым
`python3 -m unittest discover` ищет тесты.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (  # noqa: E402
    acceptance, catalog, ci, config, fsm, github_adapter, gitcmd, runner,
    stack, store)
from tests.sandbox import (  # noqa: E402
    SpyRun, _stub_check_stack, capture, capture_new_task_id,
    disk_backed_ls_tree_files, disk_backed_show, fake_git)

__all__ = ["FsmOrderScenarioTest", "PLAN_MD", "REVIEW_MD",
          "green_ci", "red_ci", "running_ci", "none_ci"]

# Дефолт песочницы (тот же приём, что `tests/test_auto_cycle.py`): без
# мока `ci.verifying_status` голова ветки задачи под `fake_git` не
# резолвится (`rev-parse --verify` отвечает отказом) — `verifying_status`
# честно деградирует на `VERIFYING_NONE`, не «красный», а `auto.py::
# _advance_verifying_poll` на этом исходе не останавливает цикл, а
# засыпает НАСТОЯЩИМ `time.sleep(config.VERIFYING_POLL_INTERVAL_SEC)`
# (90с) — тест, ушедший в цикл `auto` из/через `verifying` без явного
# `green_ci()`/`red_ci()`/... поверх, завис бы на этом сне взаправду.
# Красный — безопасный дефолт: тот же исход, что и раньше давало
# отсутствие мока (немедленная остановка), не тихий сон.
_DEFAULT_VERIFYING_NOTE = "CI коммита aaaaaaaa не зелёный: guard=failure"


def _default_verifying_status(branch: str) -> tuple:
    return ci.VERIFYING_RED, _DEFAULT_VERIFYING_NOTE

# Заготовки валидны по guard (T017): артефакт без обязательных секций
# задачу дальше не пускает — тот же набор секций, что и в
# tests/test_review_freshness.py/tests/test_auto_cycle.py.
PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: {status}
schema_version: 1
---

# PLAN: CI до ревью

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 1
---

# REVIEW: CI до ревью

## Соответствие SPEC

## Замечания

## Вердикт

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""


class FsmOrderScenarioTest(unittest.TestCase):
    """Песочница: БД и артефакты во временном каталоге, FSM вызывается
    напрямую (`fsm.cmd_advance`/`cmd_reject`), без полного цикла `auto`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(REPO_ROOT / "templates", root / "templates")
        shutil.copytree(REPO_ROOT / "skills", root / "skills")

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            self._patch(config, attr, value)

        # Ревью-пакет/гейты `in_dev` (T011/T029) собираются настоящим git —
        # в песочнице его нет, `fake_git` отвечает git-идентичностью и
        # вырожденными "нет изменений" на diff-примитивы (см. докстринг
        # модуля).
        self._patch(gitcmd, "git", fake_git)
        self.git_spy = SpyRun()
        self._patch(gitcmd.subprocess, "run", self.git_spy)
        # `artifact_source.resolve` — всегда `foreign=True` (A7): FSM
        # читает PLAN/REVIEW через `gitcmd.show`/`ls_tree_files` — эта
        # песочница без настоящего git ведёт диск `config.TASKS` как
        # единственный источник истины (тот же приём, что
        # `test_review_freshness.py`/`test_auto_cycle.py`).
        self._patch(gitcmd, "show", disk_backed_show)
        self._patch(gitcmd, "ls_tree_files", disk_backed_ls_tree_files)
        self._patch(runner.keychain, "token", lambda slot: "tok-test")
        pf_patcher = mock.patch("orchestrator.doctor.preflight_checks",
                                lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        self._patch(stack, "check_stack", _stub_check_stack)
        # Рубежи AC-3/AC-8 (прогон приёмочной планки, сверка головы на
        # origin) переезжают на `in_dev -> verifying` этой задачей — в
        # ЭТОЙ песочнице нет ни настоящего `acceptance_tests/` каталога,
        # ни настоящего origin, так что оба узла по умолчанию заглушены
        # безобидным "пройдено": тесты, которым нужно доказать, что
        # именно ЭТИ узлы стоят на нужном переходе (`test_ac02_ac08_*`),
        # переопределяют этот патч своим шпионом поверх.
        self._patch(acceptance, "run", lambda *a, **k: (True, "ok"))
        self._patch(github_adapter, "ensure_head_in_origin",
                    lambda *a, **k: (True, ""))
        self._patch(ci, "verifying_status", _default_verifying_status)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "CI до ревью")
        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True, exist_ok=True)

    def _patch(self, target, attr: str, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    capture = staticmethod(capture)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def update_task(self, **fields) -> None:
        store.update_task(store.db(), self.TASK, **fields)

    def write_plan(self, status: str = "ready") -> None:
        (self.tdir / "PLAN.md").write_text(
            PLAN_MD.format(task=self.TASK, status=status), encoding="utf-8")

    def write_review(self, status: str, iteration: int) -> None:
        (self.tdir / "REVIEW.md").write_text(
            REVIEW_MD.format(task=self.TASK, status=status, iteration=iteration),
            encoding="utf-8")

    def journal_actions(self) -> list:
        return [(r["action"], r["detail"]) for r in store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def advance(self) -> str:
        return self.capture(fsm.cmd_advance, self.TASK)

    def enter_in_dev_ready(self) -> None:
        """PLAN.md ready и state=in_dev — минимальный старт для рубежей
        перехода `in_dev -> verifying`."""
        self.write_plan("ready")
        self.set_state("in_dev")


def green_ci(note: str = "CI коммита aaaaaaaa зелёный (2 проверок)"):
    return mock.patch.object(ci, "verifying_status",
                             lambda branch: (ci.VERIFYING_GREEN, note))


def red_ci(note: str = "CI коммита aaaaaaaa не зелёный: guard=failure"):
    return mock.patch.object(ci, "verifying_status",
                             lambda branch: (ci.VERIFYING_RED, note))


def running_ci(note: str = "CI коммита aaaaaaaa ещё идёт: build"):
    return mock.patch.object(ci, "verifying_status",
                             lambda branch: (ci.VERIFYING_RUNNING, note))


def none_ci(note: str = "статус CI неизвестен: голова не в origin"):
    return mock.patch.object(ci, "verifying_status",
                             lambda branch: (ci.VERIFYING_NONE, note))
