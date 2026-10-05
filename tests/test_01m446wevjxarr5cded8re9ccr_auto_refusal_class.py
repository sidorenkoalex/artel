"""Реакция цикла `auto` на отказ предварительного `advance` — по классу отказа.

Отказ класса «чинит роль» (недостаток артефакта или кода роли текущего
состояния) запускает шаг роли этого состояния, и бриф шага несёт действие и
подробность отказа; тот же отказ после завершённого шага той же роли в том же
визите — остановка с действием в причине. Отказ класса «чинит Оператор», как
и отказ, которого нет в перечне классов, — остановка с первого раза, без шага
роли. Отказ guard'а артефакта — класс «чинит роль». Ограничители цикла
(`config.AUTO_STALL_STEPS_LIMIT`, `config.AUTO_MAX_STEPS`) считают и шаги роли
на отказах класса «чинит роль».

Группа: долгоживущий
Красен до реализации: сегодня `auto` вне `in_dev` запускает роль на любом журналируемом отказе (отказ класса «чинит Оператор» не останавливает цикл), в `in_dev` на отказах вроде «гейт заявки мутации»/«приёмочные тесты» роль не запускается вовсе, а отказ guard'а останавливает цикл сразу без шага роли — AC-1, AC-2, AC-3, AC-4, AC-9, AC-13 падают.

Публичная поверхность: цикл — `auto.cmd_auto(<id>)`; предварительный
`advance` — подменённый `fsm.cmd_advance` (журналирует заданный отказ актором
`fsm` и, как настоящий, возвращает `True` только на отказе guard'а); шаг роли —
подменённый `runner.cmd_run` (журналирует `agent run finished` под ролью шага,
как настоящий успешный шаг); бриф шага — блок истории отказов
`brief.advance_refusal_history`, тот же вызов, которым его собирает настоящий
`run`; причина остановки — запись журнала `auto остановлен`. Действия
отказов — тексты таблицы «Перечень отказов» SPEC задачи (как сейчас).
Состояние, действие и подробность отказа выбираются случайно; зерно
печатается и входит в текст провала.
"""
import random
import signal
import unittest
from unittest import mock

from orchestrator import auto, brief, config, fsm, runner, store
from tests.sandbox import LightTransitionSandbox, capture

GUARD = "переход отклонён guard'ом"

#: Класс «чинит роль» (без подкласса «роль ещё не закончила») по состояниям.
ROLE_FIXABLE = {
    "spec_writing": (GUARD,),
    "tests_writing": (
        GUARD,
        "переход отклонён: трассируемость AC",
        "переход отклонён: посторонние файлы планки",
        "переход отклонён: группы приёмочных тестов",
        "переход отклонён: долгоживущие файлы tests/",
        "переход отклонён: планка читает артефакты с диска",
        "переход отклонён: планка не собирается",
    ),
    "in_dev": (
        GUARD,
        "переход отклонён: защищённый путь",
        "переход отклонён: гейт зон — мандат есть, раздел PLAN не оформлен",
        "переход отклонён: приложение PLAN неприменимо",
        "переход отклонён: гейт заявки мутации",
        "переход отклонён: приёмочные тесты",
    ),
    "review": (
        GUARD,
        "переход отклонён",
        "переход отклонён: код сменился после вердикта",
        "переход отклонён: реестр замечаний",
    ),
}

#: Класс «чинит Оператор» (действия «как сейчас») по состояниям.
OPERATOR_FIXABLE = {
    "spec_writing": (
        "переход отклонён: результат шага не закоммичен",
        "переход отклонён: рабочая копия артефактов грязная",
    ),
    "tests_writing": (
        "переход отклонён: результат шага не закоммичен",
        "переход отклонён: рабочая копия задачи не заведена",
        "переход отклонён: фиксация не обновлена: голова ссылки документов "
        "не прочитана",
    ),
    "in_dev": (
        "переход отклонён: результат шага не закоммичен",
        "переход отклонён: рабочая копия артефактов грязная",
        "переход отклонён: лок приёмочных тестов",
        "переход отклонён: перечень долгоживущих тестов",
        "переход отклонён: посторонние файлы в worktree",
        "переход отклонён: планка не найдена в источнике",
        "переход отклонён: перечень долгоживущих файлов не прочитан",
        "переход отклонён: гейт ёмкости diff",
        "переход отклонён: гейт зон",
        "переход отклонён: гейт приложений PLAN",
        "переход отклонён: гейт неослабления тестов",
        "переход отклонён: голова не в origin",
    ),
    "review": (
        "переход отклонён: результат шага не закоммичен",
        "переход отклонён: рабочая копия артефактов грязная",
        "переход отклонён: перечень долгоживущих тестов",
    ),
}

AGENT_STATES = tuple(ROLE_FIXABLE)
ROLE_OF = {"spec_writing": "analyst", "tests_writing": "test_author",
           "in_dev": "developer", "review": "reviewer"}

#: Ручное состояние, в которое сценарий уводит задачу, чтобы цикл кончился.
MANUAL_STOP = "acceptance"
STOP_ACTION = "auto остановлен"


def new_seed() -> int:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed


class ScriptedAdvance:
    """Подмена `fsm.cmd_advance`: каждый вызов исполняет следующий элемент
    сценария — `None` (артефакт роли не готов: ни записи, ни перехода),
    `("->", состояние)` (переход по готовому артефакту) или `(действие,
    подробность)` (журналируемый отказ). Кончился сценарий — `None`."""

    def __init__(self, conn):
        self.conn = conn
        self.script: dict = {}
        self.calls: list = []

    def __call__(self, task_id, *args, **kwargs) -> bool:
        task_id = store.resolve_task_id(self.conn, task_id)
        self.calls.append(task_id)
        queue = self.script.get(task_id, [])
        item = queue.pop(0) if queue else None
        if item is None:
            return False
        first, second = item
        if first == "->":
            state = store.get_task(self.conn, task_id)["state"]
            store.set_state(self.conn, task_id, second, "fsm",
                            expected_state=state, detail="сценарий теста")
            print(f"[{task_id}] -> {second}")
            return False
        store.journal(self.conn, task_id, "fsm", first, second)
        print(f"[{task_id}] {first}: {second}")
        return first == GUARD


class RecordingStep:
    """Подмена `runner.cmd_run`: запоминает роль, состояние и блок истории
    отказов брифа на момент шага и журналирует успешное завершение шага."""

    def __init__(self, conn, cap: int):
        self.conn = conn
        self.cap = cap
        self.steps: list = []

    def __call__(self, task_id, *args, **kwargs) -> None:
        task_id = store.resolve_task_id(self.conn, task_id)
        if sum(1 for s in self.steps if s["task"] == task_id) >= self.cap:
            raise AssertionError(f"цикл не остановился: шагов роли больше {self.cap}")
        t = store.get_task(self.conn, task_id)
        role = runner.step_role(t)
        block = brief.advance_refusal_history(self.conn, task_id, role, t["state"])
        self.steps.append({"task": task_id, "role": role, "state": t["state"],
                           "brief": block})
        store.journal(self.conn, task_id, role, "agent run finished",
                      "rc=0, тестовая заглушка шага роли")


class AutoRefusalClassSandbox(LightTransitionSandbox):
    """Лёгкая песочница переходов: `advance` и шаг роли подменены
    сценарием, каждая подзадача сценария — своя свежая задача."""

    def setUp(self):
        super().setUp()
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)
        self.seed = new_seed()
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.advance = ScriptedAdvance(self.conn)
        self.step = RecordingStep(self.conn, config.AUTO_MAX_STEPS + 1)
        for target, attr, value in ((fsm, "cmd_advance", self.advance),
                                    (runner, "cmd_run", self.step)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.counter = 0

    def note(self, extra: str) -> str:
        return f"зерно: {self.seed}; {extra}"

    def fresh_task(self, state: str) -> str:
        """Свежая задача в `state` без записей переходов; в `spec_writing`
        роль analyst подключает заведённый ТЗ."""
        self.counter += 1
        task_id = f"{self.TASK[:-6]}{self.counter:06d}"
        store.insert_task(self.conn, task_id, "Сценарий класса отказа", state,
                          f"task/{task_id.lower()}-klass-otkaza",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        if state == "spec_writing":
            tdir = config.TASKS / task_id
            tdir.mkdir(parents=True, exist_ok=True)
            (tdir / "TZ.md").write_text("# ТЗ сценария\n", encoding="utf-8")
        self.assertEqual(runner.step_role(store.get_task(self.conn, task_id)),
                         ROLE_OF[state], self.note(f"роль состояния {state}"))
        return task_id

    def detail(self) -> str:
        return f"подробность отказа {self.rng.randrange(1 << 40):x}"

    def run_auto(self, task_id: str, script: list) -> str:
        self.advance.script[task_id] = list(script)
        return capture(auto.cmd_auto, task_id)

    def steps_of(self, task_id: str) -> list:
        return [s for s in self.step.steps if s["task"] == task_id]

    def advances_of(self, task_id: str) -> int:
        return sum(1 for called in self.advance.calls if called == task_id)

    def stop_details(self, task_id: str) -> list:
        return [row["detail"] for row in store.task_steps(self.conn, task_id)
                if row["action"] == STOP_ACTION]

    def assert_stopped_naming(self, task_id: str, action: str, why: str, out: str):
        details = self.stop_details(task_id)
        self.assertTrue(details, self.note(f"{why}: цикл не остановлен\n{out}"))
        self.assertIn(action, details[-1], self.note(
            f"{why}: причина остановки не называет действие отказа: "
            f"{details[-1]!r}\n{out}"))

    def assert_operator_class_stop(self, state: str, action: str) -> None:
        task_id = self.fresh_task(state)
        out = self.run_auto(task_id, [(action, self.detail())])
        why = f"{state}, «{action}»"
        self.assertEqual(len(self.steps_of(task_id)), 0, self.note(
            f"{why}: на отказе класса «чинит Оператор» запущен шаг роли\n{out}"))
        self.assertEqual(self.advances_of(task_id), 1, self.note(
            f"{why}: цикл не остановился на первом же отказе\n{out}"))
        self.assertEqual(store.get_task(self.conn, task_id)["state"], state,
                         self.note(why))
        self.assert_stopped_naming(task_id, action, why, out)


class RoleFixableRefusalRunsTheRoleTest(AutoRefusalClassSandbox):

    def test_ac1_role_fixable_refusal_runs_the_role_with_the_refusal_in_the_brief(self):
        """Отказ класса «чинит роль» запускает шаг роли этого состояния с отказом в брифе.

        Сценарий: для каждого состояния из четырёх и каждого действия класса
        «чинит роль» этого состояния (порядок случайный, подробность —
        случайная строка) свежая задача; предварительный `advance`
        журналирует отказ, затем (после шага роли) переводит задачу в ручной
        гейт. Цикл запускает ровно один шаг роли этого состояния, не
        останавливаясь на отказе, и блок истории отказов брифа этого шага
        несёт действие и подробность отказа.

        Ловит мутацию: класс отказа в `in_dev` по-прежнему решает перечень
        «роль ещё не закончила» плюс два действия гейтов зон и приложений —
        на «гейт заявки мутации»/«приёмочные тесты»/«защищённый путь» цикл
        делает холостой шаг без роли и останавливается на повторе, шагов роли
        ноль; либо фильтр брифа вычитает действие класса «чинит роль» — блок
        истории отказов пуст.
        """
        cases = [(state, action) for state, actions in ROLE_FIXABLE.items()
                 for action in actions if action != GUARD]
        self.rng.shuffle(cases)
        for state, action in cases:
            with self.subTest(state=state, action=action):
                task_id = self.fresh_task(state)
                detail = self.detail()
                out = self.run_auto(task_id, [(action, detail), ("->", MANUAL_STOP)])
                why = f"{state}, «{action}»"
                steps = self.steps_of(task_id)
                self.assertEqual(len(steps), 1, self.note(
                    f"{why}: шагов роли {len(steps)} вместо одного\n{out}"))
                self.assertEqual(steps[0]["role"], ROLE_OF[state], self.note(why))
                self.assertIn(action, steps[0]["brief"], self.note(
                    f"{why}: бриф шага не несёт действие отказа"))
                self.assertIn(detail, steps[0]["brief"], self.note(
                    f"{why}: бриф шага не несёт подробность отказа"))
                self.assertEqual(store.get_task(self.conn, task_id)["state"],
                                 MANUAL_STOP, self.note(
                                     f"{why}: цикл остановился, не дойдя до "
                                     f"следующего advance\n{out}"))


class RepeatedRoleFixableRefusalStopsTest(AutoRefusalClassSandbox):

    def test_ac2_same_refusal_after_the_role_step_stops_the_cycle(self):
        """Тот же отказ класса «чинит роль» после шага той же роли — остановка с действием.

        Сценарий: для каждого из четырёх состояний (порядок случайный) —
        случайное действие класса «чинит роль» этого состояния; свежая
        задача, предварительный `advance` журналирует его дважды подряд.
        Между отказами цикл делает ровно один шаг роли; на втором отказе
        цикл останавливается без второго шага, третьего `advance` нет, задача
        в своём состоянии, причина остановки содержит действие отказа.

        Ловит мутацию: защита от кружения (`шаг роли между двумя одинаковыми
        отказами`) осталась только у двух действий `in_dev` — в
        `tests_writing`/`review`/`spec_writing` цикл жжёт шаги роли до порога
        холостых шагов, и причина остановки — «цикл не сходится», а не
        действие отказа.
        """
        states = list(AGENT_STATES)
        self.rng.shuffle(states)
        for state in states:
            action = self.rng.choice([a for a in ROLE_FIXABLE[state] if a != GUARD]
                                     or list(ROLE_FIXABLE[state]))
            with self.subTest(state=state, action=action):
                task_id = self.fresh_task(state)
                out = self.run_auto(task_id, [(action, self.detail()),
                                              (action, self.detail())])
                why = f"{state}, «{action}»"
                self.assertEqual(len(self.steps_of(task_id)), 1, self.note(
                    f"{why}: шагов роли {len(self.steps_of(task_id))} вместо "
                    f"одного\n{out}"))
                self.assertEqual(self.advances_of(task_id), 2, self.note(
                    f"{why}: цикл не остановился на повторе\n{out}"))
                self.assertEqual(store.get_task(self.conn, task_id)["state"],
                                 state, self.note(why))
                self.assert_stopped_naming(task_id, action, why, out)


class OperatorFixableRefusalStopsTest(AutoRefusalClassSandbox):

    def test_ac3_operator_fixable_refusal_stops_on_the_first_refusal(self):
        """Отказ класса «чинит Оператор» — остановка на первом отказе без шага роли.

        Сценарий: для каждого состояния из четырёх и каждого действия класса
        «чинит Оператор» этого состояния (порядок случайный) свежая задача;
        предварительный `advance` журналирует отказ один раз, дальше сценарий
        не отказывает. Цикл не запускает ни одного шага роли, второго
        `advance` нет, задача в своём состоянии, причина остановки содержит
        действие отказа.

        Ловит мутацию: вне `in_dev` журналируемый отказ по-прежнему ведёт
        себя как «роль ещё не закончила» — «результат шага не закоммичен» в
        `review`/`tests_writing`/`spec_writing` запускает роль; либо в
        `in_dev` остановку даёт только второй одинаковый отказ подряд —
        первый отказ даёт холостой шаг и второй `advance`.
        """
        cases = [(state, action) for state, actions in OPERATOR_FIXABLE.items()
                 for action in actions]
        self.rng.shuffle(cases)
        for state, action in cases:
            with self.subTest(state=state, action=action):
                self.assert_operator_class_stop(state, action)


class UnknownRefusalIsOperatorClassTest(AutoRefusalClassSandbox):

    def test_ac4_refusal_missing_from_the_class_list_stops_like_operator_class(self):
        """Отказ «переход отклонён: …», которого нет в перечне классов, — как «чинит Оператор».

        Сценарий: в каждом из четырёх состояний (порядок случайный) свежая
        задача; предварительный `advance` журналирует отказ со случайным,
        заведомо отсутствующим в перечне действием «переход отклонён:
        <случайный хвост>». Цикл останавливается на первом отказе без шага
        роли, причина остановки содержит действие.

        Ловит мутацию: неизвестное действие по умолчанию отнесено к классу
        «чинит роль» (перечень задаёт класс «чинит Оператор», а не наоборот)
        — цикл запускает шаг роли на будущем отказе, которого роль не чинит.
        """
        states = list(AGENT_STATES)
        self.rng.shuffle(states)
        for state in states:
            action = (f"переход отклонён: неведомый гейт "
                      f"{self.rng.randrange(1 << 40):x}")
            with self.subTest(state=state, action=action):
                self.assert_operator_class_stop(state, action)


class GuardRefusalRunsTheRoleOnceTest(AutoRefusalClassSandbox):

    def test_ac9_guard_refusal_runs_one_role_step_then_stops_on_repeat(self):
        """Отказ guard'а артефакта — один шаг роли с текстом guard'а в брифе, повтор — остановка.

        Сценарий: в каждом из четырёх состояний (порядок случайный) свежая
        задача; предварительный `advance` дважды подряд отказывает guard'ом
        (журнал «переход отклонён guard'ом» со случайной подробностью,
        возврат `True`, как у настоящего `cmd_advance`). Цикл делает ровно
        один шаг роли этого состояния — его бриф несёт действие и подробность
        отказа guard'а, — и на втором отказе останавливается без второго
        шага; причина остановки содержит действие отказа guard'а.

        Ловит мутацию: возврат `True` от `cmd_advance` по-прежнему ведёт к
        немедленной остановке «advance отклонён guard'ом» — шагов роли ноль;
        либо guard исключён из защиты от кружения — второй отказ guard'а
        запускает второй шаг роли.
        """
        states = list(AGENT_STATES)
        self.rng.shuffle(states)
        for state in states:
            with self.subTest(state=state):
                task_id = self.fresh_task(state)
                first, second = self.detail(), self.detail()
                out = self.run_auto(task_id, [(GUARD, first), (GUARD, second)])
                why = f"{state}, отказ guard'а"
                steps = self.steps_of(task_id)
                self.assertEqual(len(steps), 1, self.note(
                    f"{why}: шагов роли {len(steps)} вместо одного\n{out}"))
                self.assertEqual(steps[0]["role"], ROLE_OF[state], self.note(why))
                self.assertIn(GUARD, steps[0]["brief"], self.note(
                    f"{why}: бриф шага не несёт отказ guard'а"))
                self.assertIn(first, steps[0]["brief"], self.note(
                    f"{why}: бриф шага не несёт подробность отказа guard'а"))
                self.assertEqual(self.advances_of(task_id), 2, self.note(
                    f"{why}: цикл не остановился на повторе\n{out}"))
                self.assert_stopped_naming(task_id, GUARD, why, out)


class LimitsCountRoleFixableStepsTest(AutoRefusalClassSandbox):

    def in_dev_actions(self) -> list:
        actions = list(ROLE_FIXABLE["in_dev"])
        self.rng.shuffle(actions)
        return actions

    def test_ac13_stall_limit_counts_role_steps_on_role_fixable_refusals(self):
        """Шаги роли на разных отказах «чинит роль» подряд без перехода — «цикл не сходится».

        Сценарий: `in_dev`, порог холостых шагов — случайное число от 2 до
        числа действий класса «чинит роль» `in_dev`; предварительный
        `advance` раз за разом журналирует отказ с НОВЫМ действием этого
        класса (все разные), затем отказывать перестаёт. Цикл
        останавливается причиной «цикл не сходится», сделав не меньше
        порога минус один и не больше порога шагов developer.

        Ловит мутацию: шаг роли на отказе класса «чинит роль» сбрасывает
        счётчик холостых шагов (как переход) — цикл не останавливается
        порогом, пока идут разные отказы, шагов developer больше порога;
        либо такие отказы, как сегодня, дают холостой шаг без роли — шагов
        developer ноль.
        """
        actions = self.in_dev_actions()
        limit = self.rng.randint(2, len(actions))
        with mock.patch.object(config, "AUTO_STALL_STEPS_LIMIT", limit), \
                mock.patch.object(config, "AUTO_MAX_STEPS",
                                  max(config.AUTO_MAX_STEPS, 3 * limit + 3)):
            self.step.cap = 3 * limit + 3
            task_id = self.fresh_task("in_dev")
            out = self.run_auto(task_id, [(a, self.detail()) for a in actions])
        why = f"порог {limit}, отказы {actions}"
        details = self.stop_details(task_id)
        self.assertTrue(details, self.note(f"{why}: цикл не остановлен\n{out}"))
        self.assertIn("цикл не сходится", details[-1], self.note(
            f"{why}: причина остановки {details[-1]!r}\n{out}"))
        made = len(self.steps_of(task_id))
        self.assertGreaterEqual(made, limit - 1, self.note(
            f"{why}: шагов developer {made}\n{out}"))
        self.assertLessEqual(made, limit, self.note(
            f"{why}: шагов developer {made}\n{out}"))

    def test_ac13_step_limit_counts_role_steps_on_role_fixable_refusals(self):
        """Шаги роли на отказах «чинит роль» расходуют общий лимит `AUTO_MAX_STEPS`.

        Сценарий: `in_dev`, лимит шагов за вызов — случайное число от 1 до
        числа действий класса «чинит роль» `in_dev` минус один, порог
        холостых шагов выше всего сценария; предварительный `advance` раз
        за разом журналирует отказ с новым действием этого класса. Цикл
        останавливается причиной «лимит N шагов», сделав от одного до N
        шагов developer.

        Ловит мутацию: шаг роли на отказе класса «чинит роль» не
        засчитывается в лимит шагов — цикл идёт дальше лимита, шагов
        developer больше N; либо такие отказы, как сегодня, дают холостой
        шаг без роли — шагов developer ноль.
        """
        actions = self.in_dev_actions()
        limit = self.rng.randint(1, len(actions) - 1)
        stall = 4 * len(actions) + 4
        with mock.patch.object(config, "AUTO_MAX_STEPS", limit), \
                mock.patch.object(config, "AUTO_STALL_STEPS_LIMIT", stall):
            self.step.cap = stall
            task_id = self.fresh_task("in_dev")
            out = self.run_auto(task_id, [(a, self.detail()) for a in actions])
        why = f"лимит {limit}, отказы {actions}"
        details = self.stop_details(task_id)
        self.assertTrue(details, self.note(f"{why}: цикл не остановлен\n{out}"))
        self.assertIn(f"лимит {limit} шагов", details[-1], self.note(
            f"{why}: причина остановки {details[-1]!r}\n{out}"))
        made = len(self.steps_of(task_id))
        self.assertGreaterEqual(made, 1, self.note(
            f"{why}: шагов developer {made}\n{out}"))
        self.assertLessEqual(made, limit, self.note(
            f"{why}: шагов developer {made}\n{out}"))


if __name__ == "__main__":
    unittest.main()
