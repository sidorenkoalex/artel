"""Эскалация разработчика через `PLAN.md status: escalate` пишет признак
`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER`, и после ответа Оператора и
`approve` цикл `auto` первым делом зовёт developer, а не перечитывает
прежний PLAN.md (AC-1..AC-4).

Группа: долгоживущий

Красен до реализации: эскалация через PLAN.md признака не пишет — AC-1
не находит его за `state -> escalated`, а в сквозном сценарии AC-3/AC-4
пред-advance после `approve` снова эскалирует по прежнему PLAN.md без
шага developer. AC-2 зелёный с рождения: бюджетная эскалация признака не
пишет и сегодня, тест держит это свойство против выноса признака в общий
узел.

Песочница — `tests.sandbox.LightTransitionSandbox` (диск — единственный
источник артефактов, git подменён); шаг роли подменён сценарием
`ScriptedStep` поверх публичного `runner.cmd_run`, который, как
настоящий шаг, журналирует `agent run finished` под ролью шага.
Тексты `## Эскалация` и разбиение бюджета берутся случайными при каждом
запуске; зерно печатается и входит в текст провала.
"""
import random
import unittest
from unittest import mock

from orchestrator import auto, budget, ci, config, fsm, runner, store
from tests.sandbox import LightTransitionSandbox

MARKER = fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER
APPROVE_RETURN_DETAIL = "эскалация разрешена, продолжаем"
NOT_NEEDED_ACTION = ("шаг developer не нужен: переход выполнен по готовым "
                     "артефактам")
# Бухгалтерия вокруг перехода, не событие самого перехода: lease пишется
# до разбора перехода, фиксация sha — хуком `store.set_state` после каждого
# перехода (тот же фильтр, что у `tests/test_artifact_escalation_marker.py`).
FIXATION_ACTION = "sha зафиксирован"
FIRST_ENTRY_DETAIL = "гейт SPEC пройден — приёмочные тесты до кода"

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: {status}
schema_version: 1
---

# PLAN: эскалация разработчика

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
{escalation}"""

ESCALATION_SECTION = """
## Эскалация

**Вопросы**

1. {question} — варианты: A) да; B) нет — дефолт: A.

**Контекст** — фикстура песочницы.

**Блокирует** — {blocked}.
"""

ANSWER_MD = """---
task: {task}
type: answer
schema_version: 1
---

# ANSWER-{n}

## Ответы

1. {reply}
"""

QUESTIONS = ("Расширять ли зону на соседний модуль?",
             "Оставлять ли прежний формат журнала?",
             "Принимать ли повтор шага без нового батча?",
             "Считать ли пустой ответ согласием?")


class ScriptedStep:
    """Подмена `runner.cmd_run`: шаг роли — заготовленное действие сценария.

    Роль читается ДО эффекта сценария (эффект может сменить состояние) и
    журналируется записью `agent run finished` — той же, что пишет
    настоящий шаг и ищет рубеж переделки цикла. Потолок вызовов — чтобы
    неостановленный цикл падал, а не висел.
    """

    def __init__(self):
        self.script: list = []
        self.roles: list[str] = []
        self.limit = config.AUTO_MAX_STEPS

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        if len(self.roles) >= self.limit:
            raise AssertionError("цикл не остановился за AUTO_MAX_STEPS шагов")
        conn = store.db()
        role = runner.step_role(store.get_task(conn, task_id))
        self.roles.append(role)
        if self.script:
            self.script.pop(0)()
        store.journal(conn, task_id, role, "agent run finished",
                      "rc=0, сценарий песочницы")


class PlanEscalationSandbox(LightTransitionSandbox):
    """Задача в `in_dev`, шаг роли — `ScriptedStep`, CI — красный (цикл
    не уходит дальше `verifying`, если вдруг туда дойдёт)."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.tdir.mkdir(parents=True, exist_ok=True)
        self.step = ScriptedStep()
        self.patch(runner, "cmd_run", self.step)
        self.patch(ci, "verifying_status",
                   lambda branch: (ci.VERIFYING_RED, "CI песочницы красный"))

    def patch(self, target, attr: str, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def why(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    # ------------------------------------------------------------ фикстуры

    def write_plan(self, status: str, with_escalation: bool = True) -> str:
        question = self.rng.choice(QUESTIONS)
        escalation = (ESCALATION_SECTION.format(
            question=question, blocked=f"шаг {self.rng.randint(1, 99)} плана")
            if with_escalation else "")
        (self.tdir / "PLAN.md").write_text(
            PLAN_MD.format(task=self.TASK, status=status, escalation=escalation),
            encoding="utf-8")
        return question

    def write_answer(self, n: int) -> None:
        (self.tdir / f"ANSWER-{n}.md").write_text(
            ANSWER_MD.format(task=self.TASK, n=n,
                             reply=self.rng.choice(("A", "B", "да, расширяй"))),
            encoding="utf-8")

    def enter_in_dev(self) -> None:
        """Задача в `in_dev` с журналом первого входа и отработавшим шагом
        developer — как у задачи, чей разработчик сдал PLAN.md."""
        self.set_state("in_dev")
        conn = store.db()
        store.journal(conn, self.TASK, "fsm", "state -> in_dev",
                      FIRST_ENTRY_DETAIL)
        store.journal(conn, self.TASK, "developer", "agent run finished",
                      "rc=0, шаг до эскалации")

    # ------------------------------------------------------------ журнал

    def rows(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
                if r["actor"] != "lease" and r["action"] != FIXATION_ACTION]

    def escalate_through_plan(self) -> None:
        self.enter_in_dev()
        self.write_plan("escalate")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "escalated",
                         self.why("эскалация через PLAN.md не воспроизведена"))

    def answer_and_approve(self) -> None:
        self.write_answer(1)
        out = self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "in_dev",
                         self.why(f"approve не вернул задачу в in_dev:\n{out}"))

    def run_auto(self) -> str:
        return self.capture(auto.cmd_auto, self.TASK)

    def rows_after_return(self) -> list:
        """Записи журнала начиная с ПОСЛЕДНЕЙ записи возврата `approve`."""
        rows = self.rows()
        returns = [i for i, r in enumerate(rows)
                   if r["action"] == "state -> in_dev"
                   and r["detail"] == APPROVE_RETURN_DETAIL]
        self.assertTrue(returns, self.why("в журнале нет возврата approve"))
        return rows[returns[-1]:]


class PlanEscalationMarkerTest(PlanEscalationSandbox):
    """AC-1, AC-2: признак пишет эскалация через PLAN.md, бюджетная — нет."""

    def test_ac1_plan_escalation_journals_the_marker_right_after_the_transition(self):
        """`PLAN.md status: escalate` в `in_dev`: `cmd_advance` уводит задачу
        в `escalated`, и следующая запись журнала за `state -> escalated` —
        признак с тем же `detail` и `actor = fsm`.

        Сценарий повторяется для PLAN.md с разделом «## Эскалация»
        случайного содержания и без раздела (у перехода тогда короткий
        `detail`).

        Ловит мутацию: `_in_dev_plan_escalate` не пишет признак (за
        переходом в журнале нет записи признака) или пишет его ДО
        `store.set_state` (признак стоит перед переходом, а за переходом —
        иная запись либо конец журнала).
        """
        for with_escalation in (True, False):
            with self.subTest(раздел_эскалации=with_escalation):
                self.set_state("in_dev")
                store.journal(store.db(), self.TASK, "fsm", "state -> in_dev",
                              FIRST_ENTRY_DETAIL)
                self.write_plan("escalate", with_escalation=with_escalation)

                out = self.capture(fsm.cmd_advance, self.TASK)

                self.assertEqual(self.state(), "escalated",
                                 self.why(f"эскалации нет:\n{out}"))
                rows = self.rows()
                last = max(i for i, r in enumerate(rows)
                           if r["action"] == "state -> escalated")
                self.assertLess(last + 1, len(rows), self.why(
                    "за state -> escalated в журнале ничего нет"))
                escalated, marker = rows[last], rows[last + 1]
                self.assertEqual(marker["action"], MARKER, self.why(
                    f"за переходом стоит «{marker['action']}», не признак"))
                self.assertEqual(marker["actor"], "fsm", self.why("actor"))
                self.assertEqual(marker["detail"], escalated["detail"],
                                 self.why("detail признака не равен detail "
                                          "перехода"))

    def test_ac2_budget_escalation_from_in_dev_journals_no_marker(self):
        """Шаг developer исчерпал потолок: `budget.enforce_budget` уводит
        задачу из `in_dev` в `escalated` — признака нет ни одного.

        Сценарий идёт через цикл `auto`, чтобы `fsm_advance.in_dev`
        реально исполнился (пред-advance перед шагом роли, PLAN.md ещё не
        ready), а сам шаг — как настоящий `runner` после шага — добавляет
        стоимость и зовёт `budget.enforce_budget`. Потолок и расход —
        случайные, расход заведомо выше потолка.

        Ловит мутацию: признак вынесен в общий узел перехода в `escalated`
        (`store.set_state`) — бюджетная эскалация получит запись признака;
        либо в начало `fsm_advance.in_dev` — пред-advance перед шагом
        запишет признак ещё до эскалации.
        """
        ceiling = float(self.rng.randint(5, 60))
        overshoot = ceiling + self.rng.randint(1, 20)
        self.set_state("in_dev")
        store.update_task(store.db(), self.TASK, budget_usd=ceiling,
                          spent_usd=0.0)
        self.write_plan("in_progress", with_escalation=False)

        def exhaust_budget():
            conn = store.db()
            store.update_task(conn, self.TASK, spent_usd=overshoot)
            budget.enforce_budget(conn, self.TASK, "in_dev")

        self.step.script = [exhaust_budget]

        out = self.run_auto()

        self.assertEqual(self.state(), "escalated",
                         self.why(f"бюджетная эскалация не воспроизведена:\n{out}"))
        self.assertEqual(self.step.roles, ["developer"],
                         self.why("шаг developer не исполнился ровно раз"))
        self.assertNotIn(MARKER, [r["action"] for r in self.rows()],
                         self.why("бюджетная эскалация получила признак"))


class AutoAfterAnsweredPlanEscalationTest(PlanEscalationSandbox):
    """AC-3, AC-4: сквозной сценарий цикла `auto` после ANSWER и approve."""

    def test_ac3_first_action_after_approve_is_the_developer_step(self):
        """Эскалация через PLAN.md, ANSWER-1, `approve`, затем `auto` с
        PLAN.md, оставшимся в `status: escalate`: между возвратом
        «эскалация разрешена, продолжаем» и следующим `state -> escalated`
        стоит `agent run finished` роли developer, а записи «шаг developer
        не нужен: …» до этого шага нет.

        Ловит мутацию: признак убран из `_in_dev_plan_escalate` либо
        `in_dev` исключён из `_REWORK_GATE_STATES` — пред-advance сразу
        после возврата перечитывает прежний PLAN.md и эскалирует без шага
        роли: в журнале появляется «шаг developer не нужен … in_dev ->
        escalated», а `agent run finished` между возвратом и эскалацией
        нет.
        """
        self.escalate_through_plan()
        self.answer_and_approve()

        out = self.run_auto()

        tail = self.rows_after_return()
        escalations = [i for i, r in enumerate(tail)
                       if r["action"] == "state -> escalated"]
        self.assertTrue(escalations, self.why(
            f"после approve задача не эскалировала снова:\n{out}"))
        between = tail[1:escalations[0]]
        dev_steps = [i for i, r in enumerate(between)
                     if r["actor"] == "developer"
                     and r["action"] == "agent run finished"]
        self.assertTrue(dev_steps, self.why(
            "между возвратом approve и эскалацией нет шага developer — "
            "прежний PLAN.md перечитан без шага роли"))
        before_step = between[:dev_steps[0]]
        self.assertNotIn(NOT_NEEDED_ACTION,
                         [r["action"] for r in before_step],
                         self.why("до шага developer переход выполнен по "
                                  "готовым артефактам"))

    def test_ac4_plan_left_in_escalate_after_the_step_escalates_again(self):
        """Продолжение AC-3: шаг developer после ответа оставил PLAN.md в
        `status: escalate` (тем же или переписанным батчем) — задача
        снова уходит в `escalated`, и эта эскалация идёт ПОСЛЕ шага
        developer.

        Ловит мутацию: исправление сделано подавлением escalate при
        наличии ANSWER новее эскалации — после шага developer пред-advance
        не эскалирует, PLAN.md «не ready», цикл гоняет developer до
        лимита шагов и задача остаётся в `in_dev`.
        """
        rewrite = self.rng.choice((False, True))
        print(f"шаг developer переписывает батч: {rewrite}")
        if rewrite:
            self.step.script = [lambda: self.write_plan("escalate")]
        self.escalate_through_plan()
        self.answer_and_approve()

        out = self.run_auto()

        self.assertEqual(self.state(), "escalated", self.why(
            f"новая эскалация роли потерялась (батч переписан: {rewrite}):\n"
            f"{out}"))
        tail = self.rows_after_return()
        actions = [(r["actor"], r["action"]) for r in tail]
        self.assertIn(("developer", "agent run finished"), actions,
                      self.why("шага developer после approve не было"))
        step_at = actions.index(("developer", "agent run finished"))
        self.assertIn("state -> escalated",
                      [a for _actor, a in actions[step_at + 1:]],
                      self.why("эскалации после шага developer нет"))


if __name__ == "__main__":
    unittest.main()
