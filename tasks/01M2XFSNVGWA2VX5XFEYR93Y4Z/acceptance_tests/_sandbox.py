"""Общий сценарий планки 01M2XFSNVGWA2VX5XFEYR93Y4Z: задача в `in_dev`,
дифф ветки трогает путь вне заявленных zones, мандат Оператора и раздел
«## Расширение зон» PLAN.md выставляются тестом по отдельности.

Тонкая надстройка над `tests/sandbox.py::RealGitSandbox` (скил
test-authoring, «Лёгкая песочница переходов — не копия, импорт»):
собственных копий `disk_backed_show`/`disk_backed_ls_tree_files`/
`advance_from_in_dev` здесь нет — настоящий git нужен по существу
(`_zones_gate` считает `git diff` merge-base ветки задачи, а
`_answer_commit_is_role_step_autocommit` читает СООБЩЕНИЕ коммита
`ANSWER-*.md`, и то и другое заглушкой не изобразить).

Имя действия отказа «мандат есть, раздела PLAN нет» SPEC не фиксирует
(требование 1: «например ...»), поэтому ни один файл планки его не
зашивает литералом: `mandate_refusal_action()` ниже добывает текст,
прогоняя НАСТОЯЩИЙ гейт зон на сценарии AC-1, и тесты AC-3/AC-5
работают уже с добытым значением.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (artifact_branch, catalog, config,  # noqa: E402
                          fsm_advance, gitcmd, store, workspace)
from tests.sandbox import (RealGitSandbox, capture,  # noqa: E402
                           capture_new_task_id)

# Заявленная зона задачи и путь ЗА её пределами — предмет сверки гейта.
# `docs/` намеренно: ни `config.COMMON_ZONES`, ни `config.PROTECTED_PATHS`
# его не накрывают (`docs/adr/`, `docs/invariants.md`,
# `docs/codebase-map.md` — накрывают, поэтому не они).
DECLARED_ZONE = "orchestrator/store.py"
OUT_OF_ZONE_PATH = "docs/extra_module.md"

# Действие отказа гейта зон БЕЗ мандата — сегодняшнее, неизменяемое
# (AC-2): единственный литерал имени действия во всей планке.
OLD_ZONES_REFUSAL_ACTION = "переход отклонён: гейт зон"

# Подсказка отказа гейта зон БЕЗ мандата, байт-в-байт как сегодня
# (`orchestrator/advance_gates/zones.py::_zones_gate`, ветка `out_of_zone`).
# `{task}` — единственная подстановка.
OLD_ZONES_REFUSAL_HINT = (
    "сократи дифф до заявленных zones либо оформи раздел "
    "«## Расширение зон» в PLAN.md с обоснованием и мандатом "
    "Оператора («Расширение зон разрешено: <пути>» в ANSWER-n.md), и "
    "повтори artel.py advance {task}")

_PLAN_HEAD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: гейт зон при выданном мандате

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

_PLAN_EXTENSION_SECTION = """
## Расширение зон

Пути: {paths}

Обоснование: правка затрагивает путь вне заявленных zones.
"""

_MANDATE_ANSWER = """---
task: {task}
type: answer
schema_version: 1
---

# ANSWER-1

## Ответы

Расширение зон разрешено: {paths}

мандат Оператора: {paths}
"""


class ZonesMandateSandbox(RealGitSandbox):
    """Заведённая задача `self.TASK` в `in_dev` с заявленной зоной
    `DECLARED_ZONE`, настоящей веткой кода и артефактной веткой пульта.

    `add_synced_origin()` обязателен: `workspace.ensure` заводит ветку
    задачи от `origin/<MAIN_BRANCH>` и именованно отказывает без origin
    (SPEC 01M297HFSKV3GVZJ9YF20FZEZE, AC-3).
    """

    TASK_TITLE = "Гейт зон при выданном мандате"

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, self.TASK_TITLE)
        self.conn = store.db()
        self.artifacts_branch = artifact_branch.branch_name(self.TASK)
        self.code_branch = self.row()["branch"]
        store.update_task(self.conn, self.TASK, zones=DECLARED_ZONE,
                          state="in_dev")

    # ------------------------------------------------------------ чтение

    def row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.row()["state"]

    def plan_text(self) -> str | None:
        text, _reason = gitcmd.show(self.artifacts_branch,
                                    f"tasks/{self.TASK}/PLAN.md")
        return text

    def journal_rows(self) -> list:
        return [(r["actor"], r["action"], r["detail"])
                for r in store.task_steps(self.conn, self.TASK)]

    def refusals(self) -> list:
        """(action, detail) записей журнала «переход отклонён...» —
        тот же признак, которым их отбирает `store.refusal_history`."""
        return [(action, detail) for _actor, action, detail
                in self.journal_rows()
                if action.startswith(store.REFUSAL_ACTION_PREFIX)]

    # ------------------------------------------------------------ запись

    def commit_plan(self, extension_paths: str | None = None) -> None:
        """PLAN.md в артефактную ветку: без раздела «## Расширение зон»
        (`extension_paths is None`) либо с разделом, перечисляющим
        `extension_paths` строкой `Пути:`."""
        text = _PLAN_HEAD.format(task=self.TASK)
        if extension_paths is not None:
            text += _PLAN_EXTENSION_SECTION.format(paths=extension_paths)
        sha = artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/PLAN.md": text},
            f"{self.TASK}: PLAN.md")
        self.assertTrue(sha, "PLAN.md не закоммичен в артефактную ветку")

    def commit_mandate(self, paths: str = OUT_OF_ZONE_PATH) -> None:
        """`ANSWER-1.md` со строкой мандата Оператора — сообщение коммита
        НЕ начинается с префикса автокоммита шага роли, поэтому
        `_answer_commit_is_role_step_autocommit` его не отбраковывает."""
        sha = artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/ANSWER-1.md":
                _MANDATE_ANSWER.format(task=self.TASK, paths=paths)},
            f"{self.TASK}: ANSWER-1 — ответ Оператора")
        self.assertTrue(sha, "ANSWER-1.md не закоммичен в артефактную ветку")

    def commit_out_of_zone_file(self, rel: str = OUT_OF_ZONE_PATH) -> None:
        """Коммит файла `rel` в ветку КОДА задачи — он и окажется вне
        заявленных zones при сверке гейта."""
        wt_path, error = workspace.ensure(self.TASK, self.code_branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        target = wt_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("содержимое вне зоны\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(wt_path), "add", rel],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(wt_path), "commit", "-q", "-m",
                        f"{self.TASK}: {rel}"],
                       check=True, capture_output=True)

    def enter_in_dev(self, detail: str = "гейт SPEC пройден — приёмочные "
                                         "тесты до кода") -> None:
        """Запись `state -> in_dev`, которой FSM отмечает вход роли в
        состояние: нижняя граница выборки `store.refusal_history` (AC-4) и
        анкер рубежа `auto._rework_gate_blocks`. Детэйл по умолчанию —
        легитимный первый вход (`auto._LEGIT_FIRST_ENTRY_DETAILS`), чтобы
        рубеж возврата не перехватывал пред-advance до предмета теста."""
        store.journal(self.conn, self.TASK, "fsm", "state -> in_dev", detail)

    def journal_role_step(self, role: str = "developer") -> None:
        """Запись завершённого шага роли — тем же actor/action, что и
        настоящий `orchestrator/runner.py::_cmd_run` при `rc=0`."""
        store.journal(self.conn, self.TASK, role, "agent run finished",
                      "rc=0, тестовая заглушка шага")

    # ------------------------------------------------------------ гейт

    def run_zones_gate(self) -> tuple[bool, str]:
        """(отказал ли гейт, напечатанный им текст) — та же публичная
        обёртка `_zones_gate_refuses`, которую зовёт `fsm_advance` на
        переходе `in_dev -> review`."""
        t = self.row()
        plan = self.plan_text()
        buf = []

        def call():
            return fsm_advance._zones_gate_refuses(
                self.conn, self.TASK, t, self.artifacts_branch, plan)

        out = capture(lambda: buf.append(call()))
        return buf[0], out

    def clear_journal(self) -> None:
        """Журнал задачи начисто — сценарии `auto` строят свою историю с
        нуля, без записей, оставленных разведочным прогоном гейта."""
        self.conn.execute("DELETE FROM steps WHERE task_id=?", (self.TASK,))
        self.conn.commit()


def refusal_history_text(conn, task_id: str, role: str = "developer",
                         state: str = "in_dev") -> str:
    """Блок «история отказов advance», который получит бриф шага роли —
    ровно тот вызов, который делает `orchestrator/brief.py` (AC-4)."""
    from orchestrator import brief
    return brief.advance_refusal_history(conn, task_id, role, state)


class JournalingAdvance:
    """Подмена `fsm.cmd_advance`: журналирует заданную пару
    (action, detail) под actor `fsm` и всегда возвращает `False` —
    состояние не двигает. Тот же приём, что `tests/test_auto_cycle.py::
    FakeAdvance`, но с текстом отказа, добытым у НАСТОЯЩЕГО гейта, а не
    придуманным литералом."""

    def __init__(self, action: str, detail: str):
        self.action = action
        self.detail = detail
        self.calls = 0

    def __call__(self, task_id: str, session_id: str | None = None) -> bool:
        self.calls += 1
        store.journal(store.db(), task_id, "fsm", self.action, self.detail)
        return False


class ScriptedRun:
    """Подмена `runner.cmd_run`: шаг роли без агента. Каждый вызов берёт
    следующий элемент `script` (вызываемый без аргументов — эффект шага)
    и журналирует `agent run finished` под ролью шага, тем же actor/action,
    что настоящий `orchestrator/runner.py::_cmd_run` при `rc=0` — именно
    эту запись читают рубежи `auto.py`.

    `limit` — потолок вызовов: неостановленный цикл обязан упасть
    немедленно, а не крутиться до `config.AUTO_MAX_STEPS` (тот же довод,
    что у `FakeRun.arm` в `tests/test_auto_cycle.py`)."""

    def __init__(self, limit: int, script: list | None = None):
        self.limit = limit
        self.script = list(script or [])
        self.calls: list[str] = []
        self.briefs: list[str] = []

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        if len(self.calls) >= self.limit:
            raise AssertionError(
                f"цикл не остановился: шагов роли больше {self.limit}")
        self.calls.append(task_id)
        conn = store.db()
        state = store.get_task(conn, task_id)["state"]
        role = config.STATE_ROLE.get(state, "developer")
        # Бриф шага собирается ДО эффекта: роль читает историю отказов,
        # накопленную предыдущими итерациями цикла (AC-4/AC-8).
        self.briefs.append(refusal_history_text(conn, task_id, role, state))
        if self.script:
            self.script.pop(0)()
        store.journal(conn, task_id, role, "agent run finished",
                      "rc=0, тестовая заглушка шага роли")
