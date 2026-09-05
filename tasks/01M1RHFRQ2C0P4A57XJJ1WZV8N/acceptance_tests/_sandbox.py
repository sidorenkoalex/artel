"""Общие фикстуры приёмочных тестов 01M1RHFRQ2C0P4A57XJJ1WZV8N (регрессия
№13 — `auto` пропускает шаг роли после возврата с основанием переделки,
см. tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/SPEC.md).

Два семейства сценариев, две песочницы:

- AC-1/AC-2/AC-5/AC-8/AC-9 — поведение ЦИКЛА `auto` (`orchestrator/
  auto.py`), условие которого читает ЖУРНАЛ (`state -> in_dev`/`agent run
  finished`), не git — те же лёгкие фикстуры, что уже несёт `tests/
  test_auto_cycle.py::AutoCycleTest` (fake_git, диск как источник
  артефактов): `agent_step` ниже — общий помощник, которым тестовые
  сценарии описывают «роль сделала шаг» так, как это делает НАСТОЯЩИЙ
  `orchestrator/runner.py::_cmd_run` — журналирует `agent run finished`
  под именем РОЛИ, активной на момент вызова (не после побочного
  эффекта, который эта роль могла произвести) — код требования 1 ищет
  именно эту запись, а не сам факт вызова `cmd_run`.

- AC-3/AC-4/AC-6/AC-7 — гейт `in_dev -> review` (`orchestrator/
  fsm_advance.py`), сверяющий REVIEW.md и кодовую ветку «по времени/sha,
  не по тексту» (SPEC, требование 3): REVIEW.md живёт в АРТЕФАКТНОЙ ветке
  пульта, код — в ОТДЕЛЬНОЙ кодовой ветке задачи (`orchestrator/
  artifact_source.py` — `foreign` всегда `True`, tasks/<id>/ никогда не
  живёт в кодовой ветке) — единственный способ сравнить события на двух
  независимых ветках без общего родителя это время коммитов, не sha
  (ancestry между ними отсутствует), поэтому `ReviewGateGitSandbox`
  ставит коммитам ЯВНЫЕ отметки времени (`GIT_AUTHOR_DATE`/
  `GIT_COMMITTER_DATE`) — без этого секундная гранулярность реальных
  часов иногда схлопнула бы «до» и «после» в одну секунду и сделала бы
  тест случайно зелёным/красным по гонке, а не по существу проверки.
"""
import os
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import artifact_branch, config, runner, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest, PLAN_MD, REVIEW_MD  # noqa: E402,F401

__all__ = ["AutoCycleTest", "PLAN_MD", "REVIEW_MD", "agent_step",
          "agent_run_finished_actors", "ReviewGateGitSandbox", "RoleTaggedSpy"]


def agent_run_finished_actors(conn, task_id: str) -> list:
    """Роли (`actor`), под которыми журнал несёт `agent run finished` этой
    задачи, по порядку записи — сильнее голого числа вызовов `FakeRun`
    (`agent.calls`): различает, КАКАЯ роль реально отработала шаг, а не
    просто сколько раз `cmd_run` был вызван вообще (сценарий-регрессия
    может вызвать `cmd_run` для ДРУГОЙ роли, совпав числом вызовов со
    сценарием-фиксом чисто случайно — см. `agent_step` выше)."""
    return [row["actor"] for row in store.task_steps(conn, task_id)
           if row["action"] == "agent run finished"]


class RoleTaggedSpy:
    """Подмена `runner.cmd_run`, которая ничего не исполняет, а лишь
    запоминает РОЛЬ, активную на момент вызова (`runner.step_role`), не
    сам факт вызова — нужна там, где важно доказать ОТСУТСТВИЕ конкретной
    роли среди вызовов (AC-6: «developer снова не звался»), а не просто
    общее их число."""

    def __init__(self, conn) -> None:
        self.conn = conn
        self.calls: list = []

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        t = store.get_task(self.conn, task_id)
        self.calls.append(runner.step_role(t))


def agent_step(conn, task_id: str, effect=None):
    """Один элемент `FakeRun.script` (см. `tests/test_auto_cycle.py`),
    который, в отличие от простого `lambda: None`/`lambda: self.write_...`,
    журналирует `agent run finished` под именем РОЛИ, активной в момент
    вызова — тем же action/actor, что и настоящий `orchestrator/
    runner.py::_cmd_run` (строка 745: `store.journal(conn, task_id, role,
    "agent run finished", ...)`). Требование 1 ищет именно эту запись
    («запись agent run finished роли developer после записи state ->
    in_dev»); голого факта вызова `cmd_run` (который и без этого помощника
    пишет `FakeRun.calls`) недостаточно — фейк цикла `auto` в `tests/
    test_auto_cycle.py` самого журнала не оставляет.

    Роль читается ДО `effect()`, не после: `effect` может сам сменить
    состояние задачи (например, эскалировать её) — запись обязана
    называть роль ШАГА, который «только что отработал», а не роль
    состояния, в которое эффект её увёл.
    """
    def run() -> None:
        t = store.get_task(conn, task_id)
        role = runner.step_role(t)
        if effect is not None:
            effect()
        store.journal(conn, task_id, role, "agent run finished",
                      "rc=0, тестовая заглушка приёмочного теста")
    return run


class ReviewGateGitSandbox(RealGitSandbox):
    """Гейт `in_dev -> review` (сверка REVIEW.md/кодовой ветки по
    времени): настоящий git (`RealGitSandbox`), REVIEW.md/PLAN.md — в
    артефактной ветке пульта (`artifact_branch.commit_files`, тот же
    приём, что `tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests/
    _sandbox.py::ZonesApproveSandbox`), код — в ОТДЕЛЬНОЙ кодовой ветке
    `task/<id>-x`, ответвлённой от `main`.

    Без «origin» remote в `self.root` (`_pull_main_or_escalate` -> `git
    fetch origin ...` проваливается настоящим git естественно, не
    заглушкой) — сверка свежести с main деградирует на `"fresh"` тем же
    путём, что и в продакшне при недоступном origin, не мешая гейту,
    который проверяют тесты этого файла.
    """

    TASK = "01REGR13REVIEWGATEGIT0001"

    def dated_env(self, iso_ts: str):
        return mock.patch.dict(
            os.environ, {"GIT_AUTHOR_DATE": iso_ts, "GIT_COMMITTER_DATE": iso_ts})

    def commit_code(self, message: str, iso_ts: str) -> None:
        # `git add code.txt`, НЕ `-A`: `config.ROOT` этой песочницы несёт
        # и `.artel/state.db` (`store.create_schema` в `RealGitSandbox.
        # setUp` уже завела его до первого вызова этого метода) —
        # безусловный `-A` закоммитил бы служебный каталог оркестратора
        # В КОДОВУЮ ветку задачи, а следующий `checkout main` (main его в
        # своём дереве не несёт) молча УДАЛИЛ бы файл БД с диска как
        # часть смены веток — ровно это и произошло при первой версии
        # этого метода (диагностировано прогоном тестов файла:
        # `sqlite3.OperationalError: no such table: tasks` на самом
        # первом `store.insert_task` после первого `commit_code`).
        (self.root / "code.txt").write_text(message + "\n", encoding="utf-8")
        with self.dated_env(iso_ts):
            self.git("add", "code.txt")
            self.git("commit", "-q", "-m", message)

    def commit_review(self, status: str, iteration: int, iso_ts: str) -> None:
        text = REVIEW_MD.format(task=self.TASK, status=status, iteration=iteration)
        with self.dated_env(iso_ts):
            artifact_branch.commit_files(
                self.TASK, {f"tasks/{self.TASK}/REVIEW.md": text},
                f"{self.TASK}: REVIEW итерация {iteration}")

    def commit_plan(self, status: str = "ready") -> None:
        text = PLAN_MD.format(task=self.TASK, status=status)
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/PLAN.md": text},
            f"{self.TASK}: PLAN")

    def enter_in_dev_after_changes_requested(self, review_iso_ts: str) -> None:
        """Заводит задачу в `in_dev` с тем же основанием, что и реальный
        возврат `review -> in_dev` (замечания ревью): PLAN.md уже `ready`
        (разработчик не тронул код после вердикта), REVIEW.md текущей
        итерации несёт `changes_requested` с явной отметкой времени
        коммита `review_iso_ts`, код-ветка — единственный уже
        существующий коммит с отметкой ДО неё (намеренно раньше: вызывающий
        код дописывает код-ветку ПОСЛЕ вызова этого метода —
        `commit_developer_fix` ниже, — если сценарию нужен коммит
        разработчика новее вердикта)."""
        self.branch = f"task/{self.TASK.lower()}-x"
        self.checkout(self.branch, create=True)
        self.commit_code("developer: исходная реализация",
                         "2026-01-01T00:00:00+00:00")
        self.checkout(config.MAIN_BRANCH)
        store.insert_task(store.db(), self.TASK,
                          "Гейт неизменённого кода после ревью", "in_dev",
                          self.branch, config.DEFAULT_TARGET, 15.0)
        store.update_task(store.db(), self.TASK, reviewed_iter=1)
        self.commit_plan("ready")
        self.commit_review("changes_requested", 1, review_iso_ts)

    def commit_developer_fix(self, message: str, iso_ts: str) -> None:
        """Ещё один коммит на КОДОВОЙ ветке задачи, ПОСЛЕ вердикта ревью
        (`iso_ts` обязан быть позже отметки, переданной `enter_in_dev_
        after_changes_requested`) — симулирует шаг developer, отработавший
        замечания. Переключает рабочее дерево на ветку задачи и обратно на
        `main`, тем же приёмом, что и сам `enter_in_dev_after_changes_
        requested` — рабочая копия не должна оставаться на чужой ветке
        между шагами теста."""
        self.checkout(self.branch)
        self.commit_code(message, iso_ts)
        self.checkout(config.MAIN_BRANCH)

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def journal_rows(self) -> list[tuple[str, str, str]]:
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]
