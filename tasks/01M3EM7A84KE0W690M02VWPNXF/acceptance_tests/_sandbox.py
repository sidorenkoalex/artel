"""Общая фикстура приёмочных тестов 01M3EM7A84KE0W690M02VWPNXF:
неразрешённый конфликт СОДЕРЖИМОГО подтяжки, эскалирующий задачу из
ЗАДАННОГО состояния, и цикл `auto` поверх возврата из этой эскалации.

Два входа в один и тот же конфликт — по тому, что называет сам критерий:

- `escalate_via_pull_conflict(state)` — общий узел всех четырёх точек
  подтяжки (`fsm._pull_main_or_escalate`, «Контекст» SPEC: `_approve_
  acceptance`, обработчик `in_dev` `fsm_advance.py`, `fsm_merge_gate::
  _sync_main_or_wait`, `canary::_pass_acceptance_gate` ходят через него):
  состояния AC-1/AC-2 различаются ровно параметром `state`, поэтому
  сравнивать их между собой честно только одним и тем же узлом;
- `escalate_via_merge_gate()` — узел ИМЕННО гейта мержа
  (`fsm_merge_gate::_sync_main_or_wait`), которым сценарии AC-3/AC-4
  воспроизводят живой случай 21.09. Полное тело `_cmd_approve_merge_gate`
  здесь не зовётся намеренно: до подтяжки оно ходит в мьютекс merge,
  origin и CI, а конфликт подтяжки останавливает гейт РАНЬШЕ всего этого
  (`sync_outcome != "fresh"` -> `("stopped",)`).

Не копия `tests/sandbox.py::LightTransitionSandbox` (скил test-authoring,
«Лёгкая песочница переходов — не копия, импорт») — тонкая надстройка над
ней: конфликт заводится единственным новым узлом (`conflict_handler`,
через уже существующую точку расширения `self.in_repo_handlers`),
агент-заглушку цикла `auto` песочница тоже не копирует, а берёт готовой из
`tests/test_auto_cycle.py::FakeRun` (тот же приём, что уже применяет
`tasks/01M290PYPV5T2NFW1Y0HB8BD6E/acceptance_tests/_sandbox.py` для того
же самого цикла).
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import (acceptance, auto, ci, config, fsm,  # noqa: E402
                          fsm_merge_gate, gitcmd, pull, repo_context, runner,
                          store)
from tests.sandbox import LightTransitionSandbox  # noqa: E402
from tests.test_auto_cycle import FakeRun  # noqa: E402

__all__ = ["PullConflictSandbox", "CONFLICT_FILE", "ESCALATION_ACTION",
           "ROLE_STEP_ACTION", "STREAK_STOP_PHRASE"]

# Конфликтующий файл сценария — НЕ `docs/codebase-map.md`: авторазрешение
# карты (SPEC T067) к нему не применяется, конфликт остаётся неразрешённым.
CONFLICT_FILE = "module.py"
MERGE_STDOUT = f"CONFLICT (content): Merge conflict in {CONFLICT_FILE}\n"

# Действия журнала существующих узлов, читаемые планкой по тексту:
# `store.set_state` пишет `f"state -> {state}"`, `runner`/`FakeRun` —
# «agent run finished» под именем роли шага (`auto._role_step_since_state_
# entry` ищет именно эту пару action/actor).
ESCALATION_ACTION = "state -> escalated"
ROLE_STEP_ACTION = "agent run finished"

# Текст стоп-крана серии меток конфликта подтяжки (`auto._pre_advance_step`,
# приёмка 01M290PYPV5T2NFW1Y0HB8BD6E AC-4) — существующее поведение, от
# которого AC-4 требует НЕ срабатывать в своём сценарии.
STREAK_STOP_PHRASE = "предварительный advance дважды упёрся"


class PullConflictSandbox(LightTransitionSandbox):
    """`LightTransitionSandbox` + агент-заглушка цикла `auto` + конфликт
    подтяжки и возврат из эскалации, специфичные ровно этой планке."""

    def setUp(self):
        super().setUp()
        self.agent = FakeRun()
        run_patcher = mock.patch.object(runner, "cmd_run", self.agent)
        run_patcher.start()
        self.addCleanup(run_patcher.stop)

    # ------------------------------------------------------- конфликт

    def conflict_handler(self, files: list, merge_stdout: str = MERGE_STDOUT):
        """Хук `self.in_repo_handlers`: `git merge` конфликтует, `git diff
        --name-only --diff-filter=U` называет `files`, `merge --abort`
        успешен — ровно то, чего сценарий требует от подтяжки; остальное
        (checkout/add/commit WIP-чекпоинта) делегируется дефолту
        `LightTransitionSandbox` (`fake_git`, безусловный успех)."""
        def handler(repo, *args) -> subprocess.CompletedProcess | None:
            if args[:1] == ("merge",) and "--abort" in args:
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args[:1] == ("merge",):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, merge_stdout, "")
            if args[:2] == ("diff", "--name-only"):
                text = "\n".join(files) + ("\n" if files else "")
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, text, "")
            return None
        return handler

    def arm_conflict(self, *, conflict_files: tuple = (CONFLICT_FILE,),
                     behind: int = 3) -> None:
        """Ветка отстала на `behind` коммитов, а merge конфликтует — оба
        условия входа в неразрешённый конфликт содержимого."""
        self.in_repo_handlers.append(self.conflict_handler(list(conflict_files)))
        behind_patcher = mock.patch.object(
            gitcmd, "commits_behind", return_value=behind)
        behind_patcher.start()
        self.addCleanup(behind_patcher.stop)

    def clear_conflict(self) -> None:
        """Конфликт разрешён (шаг роли отработал) — следующая подтяжка
        идёт дефолтом песочницы, то есть чисто: ветка всё ещё отстала
        (`commits_behind` остаётся замоканной), merge проходит."""
        self.in_repo_handlers.clear()

    # ------------------------------------------------------- эскалация

    def escalate_via_pull_conflict(self, state: str) -> str:
        """Конфликт подтяжки при задаче в состоянии `state` через общий
        узел всех точек подтяжки. Возврат — контрактная строка исхода
        (`"escalated"`/`"refused"`/`"fresh"`/`"pulled"`)."""
        self.set_state(state)
        self.arm_conflict()
        return fsm._pull_main_or_escalate(store.db(), self.TASK,
                                          self.task_row(), state)

    def escalate_via_merge_gate(self) -> tuple:
        """Тот же конфликт на ГЕЙТЕ МЕРЖА — через узел свежести самого
        гейта (`_sync_main_or_wait`, зовётся телом `approve` merge_gate
        первым же шагом после публикации головы). Возврат — сигнал этого
        узла вызывающему циклу гейта (`("stopped",)` на эскалации)."""
        self.set_state("merge_gate")
        self.arm_conflict()
        ctx = repo_context.resolve(config.DEFAULT_TARGET)
        return fsm_merge_gate._sync_main_or_wait(
            store.db(), self.TASK, self.task_row(), "merge_gate",
            self.branch, ctx)

    # --------------------------------------------------------- возврат

    def write_answer(self) -> Path:
        """Следующий `ANSWER-n.md` — безвредно независимо от того, требует
        ли `approve` именно его (`answer_baseline` у этого класса эскалации
        остаётся `None`)."""
        n = len(sorted(self.tdir.glob("ANSWER-*.md"))) + 1
        path = self.tdir / f"ANSWER-{n}.md"
        self.tdir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\ntask: {self.TASK}\ntype: answer\nauthor_role: operator\n"
            f"schema_version: 1\n---\n\n# ANSWER-{n}\n\nКонфликт подтяжки "
            f"разобран, продолжаем.\n", encoding="utf-8")
        return path

    def approve(self) -> str:
        self.write_answer()
        return self.capture(fsm.cmd_approve, self.TASK)

    # ------------------------------------------------------------ auto

    def auto(self) -> str:
        """Один вызов `auto.cmd_auto` с армированной заглушкой агента.

        Приёмочная планка (`acceptance.run`) и статус CI ветки
        (`ci.verifying_status`) подменены зелёными: предмет сценариев —
        предварительный advance и шаг роли, не прогон планки и не опрос
        CI, а без подмены опрос `verifying` спал бы
        `config.VERIFYING_POLL_INTERVAL_SEC` на каждой итерации и уходил
        бы за настоящим ответом gh."""
        self.agent.arm(config.AUTO_MAX_STEPS)
        with mock.patch.object(acceptance, "run", return_value=(True, "ok")), \
             mock.patch.object(
                 ci, "verifying_status",
                 return_value=(ci.VERIFYING_GREEN,
                               "CI ветки зелёный (заглушка планки)")):
            return self.capture(auto.cmd_auto, self.TASK)

    # ------------------------------------------------------------ журнал

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def rows_with(self, action: str) -> list:
        return [r for r in self.journal_rows() if r["action"] == action]

    def marker_rows(self) -> list:
        return self.rows_with(pull.PULL_CONFLICT_ROLE_STEP_MARKER)

    def escalation_rows(self) -> list:
        return self.rows_with(ESCALATION_ACTION)

    def role_run_count(self) -> int:
        return len(self.agent.calls)
