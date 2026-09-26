"""Юнит-тесты набора состояний, эскалация которых по НЕРАЗРЕШЁННОМУ
конфликту содержимого подтяжки метит задачу
`pull.PULL_CONFLICT_ROLE_STEP_MARKER` (SPEC 01M3EM7A84KE0W690M02VWPNXF,
требования 1-5): `pull.PULL_CONFLICT_MARKED_STATES` — ровно `in_dev`,
`acceptance`, `merge_gate`, и ни одного состояния сверх них.

Почему набор именно такой: сама эта эскалация `escalated_from` не пишет,
а возврат из `escalated` считает состояние как `escalated_from or
"in_dev"` — из всех трёх состояний возврат уходит в `in_dev`, где
следующий шаг и есть шаг разработчика, единственного, кому конфликт по
силам разрешить. Без метки `auto` после возврата делал предварительный
advance, повторял ту же подтяжку, ловил тот же конфликт и эскалировал
снова (живой случай 21.09, задача 01M31DRD81).

Песочница — `tests/sandbox.py::LightTransitionSandbox` (скил
test-authoring, «Лёгкая песочница переходов — не копия, импорт»); своего
здесь только конфликтующий `git merge` (единственный хук
`self.in_repo_handlers`) и возврат из эскалации. Агент-заглушка цикла
`auto` тоже не копируется — берётся готовой из
`tests/test_auto_cycle.py::FakeRun`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, auto, ci, config, fsm,  # noqa: E402
                          fsm_merge_gate, gitcmd, pull, repo_context, runner,
                          store)
from tests.sandbox import LightTransitionSandbox  # noqa: E402
from tests.test_auto_cycle import FakeRun  # noqa: E402

# Конфликтующий файл сценария — НЕ `docs/codebase-map.md`: авторазрешение
# карты (SPEC T067) к нему не применяется, конфликт остаётся неразрешённым.
CONFLICT_FILE = "module.py"
MERGE_STDOUT = f"CONFLICT (content): Merge conflict in {CONFLICT_FILE}\n"

# Действия журнала существующих узлов, читаемые тестами по тексту:
# `store.set_state` пишет `f"state -> {state}"`, `FakeRun` — «agent run
# finished» под именем роли шага.
ESCALATION_ACTION = "state -> escalated"
ROLE_STEP_ACTION = "agent run finished"

# Текст стоп-крана серии меток конфликта подтяжки
# (`auto._pre_advance_step`, SPEC 01M290PYPV5T2NFW1Y0HB8BD6E) —
# существующее поведение, от которого требование 4 требует НЕ срабатывать.
STREAK_STOP_PHRASE = "предварительный advance дважды упёрся"


class PullConflictCase(LightTransitionSandbox):
    """Конфликт подтяжки из заданного состояния и возврат из этой
    эскалации — общая обвязка тестов файла, сама тестов не несёт."""

    def setUp(self):
        super().setUp()
        self.agent = FakeRun()
        run_patcher = mock.patch.object(runner, "cmd_run", self.agent)
        run_patcher.start()
        self.addCleanup(run_patcher.stop)

    # ------------------------------------------------------- конфликт

    def _conflict_handler(self, files: list):
        """Хук `self.in_repo_handlers`: `git merge` конфликтует, `git diff
        --name-only --diff-filter=U` называет `files`, `merge --abort`
        успешен; остальное (checkout/add/commit WIP-чекпоинта) — дефолту
        `LightTransitionSandbox`."""
        def handler(repo, *args) -> subprocess.CompletedProcess | None:
            if args[:1] == ("merge",) and "--abort" in args:
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args[:1] == ("merge",):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, MERGE_STDOUT, "")
            if args[:2] == ("diff", "--name-only"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0,
                    "\n".join(files) + "\n", "")
            return None
        return handler

    def arm_conflict(self, behind: int = 3) -> None:
        """Ветка отстала на `behind` коммитов, а merge конфликтует — оба
        условия входа в неразрешённый конфликт содержимого."""
        self.in_repo_handlers.append(self._conflict_handler([CONFLICT_FILE]))
        behind_patcher = mock.patch.object(
            gitcmd, "commits_behind", return_value=behind)
        behind_patcher.start()
        self.addCleanup(behind_patcher.stop)

    def clear_conflict(self) -> None:
        """Конфликт разрешён (шаг роли отработал) — следующая подтяжка
        идёт дефолтом песочницы: ветка всё ещё отстала, merge проходит."""
        self.in_repo_handlers.clear()

    # ------------------------------------------------------- эскалация

    def escalate_from(self, state: str) -> str:
        """Конфликт подтяжки при задаче в `state` через общий узел всех
        точек подтяжки (`fsm._pull_main_or_escalate`): состояния
        различаются ровно этим параметром, поэтому сравнивать их между
        собой честно только одним и тем же узлом."""
        self.set_state(state)
        self.arm_conflict()
        return fsm._pull_main_or_escalate(store.db(), self.TASK,
                                          self.task_row(), state)

    def escalate_via_merge_gate(self) -> tuple:
        """Тот же конфликт на ГЕЙТЕ МЕРЖА — через узел свежести самого
        гейта. Полное тело `approve` merge_gate не зовётся: до подтяжки
        оно ходит в мьютекс merge, origin и CI, а конфликт останавливает
        гейт раньше всего этого."""
        self.set_state("merge_gate")
        self.arm_conflict()
        ctx = repo_context.resolve(config.DEFAULT_TARGET)
        return fsm_merge_gate._sync_main_or_wait(
            store.db(), self.TASK, self.task_row(), "merge_gate",
            self.branch, ctx)

    # --------------------------------------------------------- возврат

    def approve(self) -> str:
        """Возврат Оператора из эскалации. `ANSWER-n.md` кладётся
        безвредно независимо от того, требует ли его `approve` для этого
        класса эскалации."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        n = len(sorted(self.tdir.glob("ANSWER-*.md"))) + 1
        (self.tdir / f"ANSWER-{n}.md").write_text(
            f"---\ntask: {self.TASK}\ntype: answer\nauthor_role: operator\n"
            f"schema_version: 1\n---\n\n# ANSWER-{n}\n\nКонфликт подтяжки "
            f"разобран, продолжаем.\n", encoding="utf-8")
        return self.capture(fsm.cmd_approve, self.TASK)

    # ------------------------------------------------------------ auto

    def auto(self) -> str:
        """Один вызов `auto.cmd_auto` с армированной заглушкой агента.
        Приёмочная планка и статус CI подменены зелёными: предмет тестов —
        предварительный advance и шаг роли, а без подмены опрос
        `verifying` спал бы на каждой итерации и уходил за настоящим
        ответом gh."""
        self.agent.arm(config.AUTO_MAX_STEPS)
        with mock.patch.object(acceptance, "run", return_value=(True, "ok")), \
             mock.patch.object(
                 ci, "verifying_status",
                 return_value=(ci.VERIFYING_GREEN, "CI зелёный (заглушка)")):
            return self.capture(auto.cmd_auto, self.TASK)

    # ---------------------------------------------------------- журнал

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def rows_with(self, action: str) -> list:
        return [r for r in self.journal_rows() if r["action"] == action]

    def marker_rows(self) -> list:
        return self.rows_with(pull.PULL_CONFLICT_ROLE_STEP_MARKER)


class MarkedStatesSetTest(unittest.TestCase):
    """Требование 2: набор состояний, получающих метку, — ровно три, и
    правда о нём живёт в одной константе, а не в литерале внутри
    функции."""

    def test_marked_states_are_exactly_the_three_returning_to_in_dev(self):
        """`pull.PULL_CONFLICT_MARKED_STATES` — ровно `in_dev`,
        `acceptance`, `merge_gate`.

        Ловит мутацию: в набор дописано четвёртое состояние (`review`,
        `verifying`, `spec_gate`), из которого возврат из эскалации
        уходит не в `in_dev`, либо одно из трёх из него выпало —
        `assertEqual` ниже это поймает.
        """
        self.assertEqual(pull.PULL_CONFLICT_MARKED_STATES,
                         ("in_dev", "acceptance", "merge_gate"))


class MarkerPerStateTest(PullConflictCase):
    """Требования 1-2 (AC-1/AC-2): метка пишется для каждого из трёх
    состояний набора и не пишется для состояния вне него."""

    def assert_marked(self, state: str) -> None:
        """Задача эскалирована, метка ровно одна, её `detail` совпадает с
        `detail` записи эскалации (по нему Оператор читает, ЧЕМ помечена
        задача)."""
        outcome = self.escalate_from(state)

        self.assertEqual(outcome, "escalated")
        self.assertEqual(self.state(), "escalated")
        escalations = self.rows_with(ESCALATION_ACTION)
        self.assertEqual(len(escalations), 1)
        markers = self.marker_rows()
        self.assertEqual(
            len(markers), 1,
            f"конфликт подтяжки из состояния {state} не пометил задачу "
            f"признаком «нужен шаг роли до следующего предварительного "
            f"advance»")
        self.assertEqual(markers[0]["detail"], escalations[0]["detail"])
        self.assertIn(CONFLICT_FILE, markers[0]["detail"])

    def test_marker_is_written_for_in_dev(self):
        """Конфликт подтяжки при задаче в `in_dev` метит её.

        Ловит мутацию: расширяя условие на три состояния, разработчик
        подменяет набор (`if state in ("acceptance", "merge_gate")`) и
        теряет уже работавший случай `in_dev` — `assertEqual(len(markers),
        1)` это поймает.
        """
        self.assert_marked("in_dev")

    def test_marker_is_written_for_acceptance(self):
        """Тот же конфликт при задаче в `acceptance` (подтяжку там зовут
        `fsm._approve_acceptance` и `canary._pass_acceptance_gate`).

        Ловит мутацию: условие записи метки осталось `if state ==
        "in_dev"` либо расширено только на `merge_gate` (случай из копилки
        21.09 разобран, симметричный случай приёмки забыт) — записи метки
        в журнале не появится, и `assertEqual(len(markers), 1)` это
        поймает.
        """
        self.assert_marked("acceptance")

    def test_marker_is_written_for_merge_gate(self):
        """Тот же конфликт при задаче в `merge_gate` (подтяжку там зовёт
        `fsm_merge_gate._sync_main_or_wait`) — живой случай 21.09.

        Ловит мутацию: условие записи метки осталось `if state ==
        "in_dev"`, либо метка пишется со своим собственным `detail`
        (пустым, либо `note` без префикса «конфликт подтяжки … в
        ветку …») — `assertEqual(len(markers), 1)`/`assertEqual` по
        `detail` это поймают.
        """
        self.assert_marked("merge_gate")

    def test_no_marker_for_a_state_outside_the_set(self):
        """Тот же конфликт при задаче в состоянии вне набора (`review`)
        эскалирует её как прежде, но метки не оставляет.

        Ловит мутацию: условие записи метки снято целиком (`store.journal`
        вынесен из-под `if`, метка пишется на ЛЮБОЙ эскалации конфликта
        подтяжки) — в журнале появится запись метки для `review`, и
        `assertEqual(len(markers), 0)` это поймает; `assertEqual` по
        состоянию и `assertIn` по `detail` эскалации поймают обратную
        мутацию — сужение самой эскалации вместе с меткой.
        """
        outcome = self.escalate_from("review")

        self.assertEqual(outcome, "escalated")
        self.assertEqual(self.state(), "escalated")
        escalations = self.rows_with(ESCALATION_ACTION)
        self.assertEqual(len(escalations), 1)
        self.assertIn(CONFLICT_FILE, escalations[0]["detail"])
        self.assertEqual(
            len(self.marker_rows()), 0,
            "состояние review вне набора «возврат ведёт в in_dev» получило "
            "метку конфликта подтяжки")


class MergeGateReturnGivesDeveloperItsStepTest(PullConflictCase):
    """Требование 5, случай 21.09 (AC-3): после возврата из эскалации
    конфликта подтяжки ГЕЙТА МЕРЖА цикл `auto` обязан начать со шага роли
    текущего состояния (`developer` в `in_dev`) — иначе разрешать конфликт
    некому, и Оператор платит лишним кругом `answer`/`approve` за каждый
    такой конфликт."""

    def test_auto_refuses_pre_advance_and_runs_developer_after_the_return(self):
        """Конфликт подтяжки на гейте мержа эскалирует задачу; `approve`
        возврата переводит её в `in_dev`; следующий `auto` журналирует
        `auto.REWORK_REFUSAL_ACTION` и зовёт developer, не сделав до этого
        ни одного предварительного advance.

        Ловит мутацию: метка записана только для `in_dev` (условие не
        расширено на `merge_gate`) — рубеж пред-advance не держится,
        `_pre_advance_step` первым же действием повторяет подтяжку и
        переэскалирует задачу: `auto.REWORK_REFUSAL_ACTION` в журнале не
        появится вовсе, а `state -> escalated` появится ДО шага developer.
        """
        self.write_plan_ready()

        self.assertEqual(self.escalate_via_merge_gate(), ("stopped",))
        self.assertEqual(self.state(), "escalated")

        self.approve()
        self.assertEqual(
            self.state(), "in_dev",
            "возврат из эскалации подтяжки обязан вести в in_dev — "
            "escalated_from эта эскалация не пишет")

        before = len(self.journal_rows())
        self.auto()
        rows = self.journal_rows()[before:]
        actions = [r["action"] for r in rows]

        self.assertIn(
            auto.REWORK_REFUSAL_ACTION, actions,
            "auto не журналировал отказ рубежа переделки — предварительный "
            "advance не был отклонён после возврата из эскалации")
        step_index = next(
            (i for i, r in enumerate(rows)
             if r["action"] == ROLE_STEP_ACTION and r["actor"] == "developer"),
            None)
        self.assertIsNotNone(step_index, "auto не отдал шаг роли developer")
        self.assertLess(actions.index(auto.REWORK_REFUSAL_ACTION), step_index,
                        "отказ рубежа обязан быть журналирован ДО шага "
                        "developer — он и есть причина, по которой шаг отдан")
        self.assertNotIn(
            ESCALATION_ACTION, actions[:step_index],
            "auto сделал предварительный advance до шага developer и снова "
            "эскалировал задачу тем же конфликтом (случай 21.09)")


class ResolvedConflictPassesWithoutStreakStopTest(PullConflictCase):
    """Требование 4 (AC-4): метки требования 1 не подводят задачу под
    стоп-кран серии меток — серия остаётся единичной и гасится переходом в
    следующее состояние."""

    def test_developer_step_then_clean_pull_is_not_stopped_by_the_streak(self):
        """Шаг developer разрешает конфликт (следующая подтяжка чистая) —
        `auto` продвигает задачу дальше `in_dev` и не останавливается
        стоп-краном; на весь сценарий приходится РОВНО одна запись метки.

        Ловит мутацию: метка для трёх состояний записана вторым блоком
        `store.journal` рядом с прежним `if state == "in_dev"` (старая
        ветка не убрана) — один конфликт оставляет ДВЕ записи метки, серия
        сразу достигает порога, и первый же последующий предварительный
        advance останавливает цикл именованной причиной вместо шага роли:
        `assertEqual(len(marker_rows), 1)` это поймает, а `assertNotIn` по
        тексту стоп-крана и `assertIn` по `state -> verifying` — его
        последствие в этом сценарии.
        """
        self.write_plan_ready()
        self.write_acceptance_plank()

        self.escalate_via_merge_gate()
        self.assertEqual(self.state(), "escalated")
        self.approve()
        self.assertEqual(self.state(), "in_dev")

        # Шаг developer: конфликт разрешён, подтяжка после него чистая.
        self.agent.script = [self.clear_conflict]
        out = self.auto()

        self.assertNotIn(
            STREAK_STOP_PHRASE, out,
            "цикл остановлен стоп-краном серии меток, хотя повторная "
            "подтяжка прошла без конфликта")
        rows = self.journal_rows()
        self.assertTrue(
            any(r["action"] == ROLE_STEP_ACTION and r["actor"] == "developer"
                for r in rows),
            "шаг developer не был отдан — сценарий не воспроизведён")
        self.assertIn(
            "state -> verifying", [r["action"] for r in rows],
            "задача не продвинулась дальше in_dev по чистой повторной "
            "подтяжке — цикл остановился раньше")
        self.assertEqual(
            len(self.marker_rows()), 1,
            "на один конфликт подтяжки пришлось не одно вхождение метки — "
            "серия стоп-крана растёт без второго конфликта")


if __name__ == "__main__":
    unittest.main()
