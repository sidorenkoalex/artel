"""Классы новых отказов честного `FAIL_TO_PASS` и проверки ветки в перечне `REFUSAL_CLASSES` и реакция цикла `auto` на них.

Группа: долгоживущий
Красен до реализации: шести новых действий журнала в `REFUSAL_CLASSES` нет — три действия класса «чинит роль» по умолчанию идут в «чинит Оператор», и `auto` останавливается на находке честного FAIL_TO_PASS вместо шага test_author; проверки «действие есть в перечне» красны для всех шести; остановка `auto` на трёх действиях класса «чинит Оператор» зелена и сегодня (действие вне перечня — тот же класс).

Публичная поверхность: перечень — `refusal_classes.REFUSAL_CLASSES` и
`refusal_classes.refusal_class`; цикл — `auto.cmd_auto(<id>)`;
предварительный `advance` — подменённый `fsm.cmd_advance` (журналирует
заданный отказ актором `fsm`); шаг роли — подменённый `runner.cmd_run`
(журналирует `agent run finished` под ролью шага); бриф шага — блок
истории отказов `brief.advance_refusal_history`; причина остановки —
запись журнала `auto остановлен`. Лёгкая песочница переходов
(`tests.sandbox.LightTransitionSandbox`), каждая подзадача — своя свежая
задача в `tests_writing`. Подробность
отказа и порядок действий — из `random`, зерно печатается и входит в
текст провала.

Провалидировано временным стабом (шесть действий внесены в перечень,
удалён, не закоммичен): все методы файла зелёные.
"""
import random
import signal
import unittest
from unittest import mock

from orchestrator import auto, brief, config, fsm, runner, store
from orchestrator.advance_gates import refusal_classes
from tests.sandbox import LightTransitionSandbox, capture

F2P_ACTION = "переход отклонён: честный FAIL_TO_PASS"
BRANCH_ACTION = "переход отклонён: приёмочные тесты — тест критерия не в отчёте"
SPEC_CHANGED_ACTION = "переход отклонён: SPEC изменён после гейта SPEC"
NO_LIST_ACTION = ("переход отклонён: честный FAIL_TO_PASS — список «провал "
                  "проверки» не задан")
PREPARE_ACTION = "переход отклонён: честный FAIL_TO_PASS — отказ подготовки"
ANCHOR_ACTION = "переход отклонён: честный FAIL_TO_PASS — опора SPEC не найдена"

ROLE_CLASS = (F2P_ACTION, BRANCH_ACTION, SPEC_CHANGED_ACTION)
OPERATOR_CLASS = (NO_LIST_ACTION, PREPARE_ACTION, ANCHOR_ACTION)
MANUAL_STOP = "acceptance"
STOP_ACTION = "auto остановлен"


class ScriptedAdvance:
    """Подмена `fsm.cmd_advance`: каждый вызов исполняет следующий элемент
    сценария — `("->", состояние)` (переход) или `(действие, подробность)`
    (журналируемый отказ); кончился сценарий — ни записи, ни перехода."""

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
            return False
        store.journal(self.conn, task_id, "fsm", first, second)
        print(f"[{task_id}] {first}: {second}")
        return False


class RecordingStep:
    """Подмена `runner.cmd_run`: запоминает роль и блок истории отказов
    брифа и журналирует успешное завершение шага."""

    def __init__(self, conn, cap: int):
        self.conn = conn
        self.cap = cap
        self.steps: list = []

    def __call__(self, task_id, *args, **kwargs) -> None:
        task_id = store.resolve_task_id(self.conn, task_id)
        if sum(1 for s in self.steps if s["task"] == task_id) >= self.cap:
            raise AssertionError(f"цикл не остановился: шагов больше {self.cap}")
        t = store.get_task(self.conn, task_id)
        role = runner.step_role(t)
        block = brief.advance_refusal_history(self.conn, task_id, role,
                                              t["state"])
        self.steps.append({"task": task_id, "role": role, "brief": block})
        store.journal(self.conn, task_id, role, "agent run finished",
                      "rc=0, заглушка шага роли")


class RefusalClassSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
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
        self.counter += 1
        task_id = f"{self.TASK[:-6]}{self.counter:06d}"
        store.insert_task(self.conn, task_id, "Сценарий класса отказа", state,
                          f"task/{task_id.lower()}-klass", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def detail(self) -> str:
        return f"подробность {self.rng.randrange(1 << 40):x}"

    def run_auto(self, task_id: str, script: list) -> str:
        self.advance.script[task_id] = list(script)
        return capture(auto.cmd_auto, task_id)

    def steps_of(self, task_id: str) -> list:
        return [s for s in self.step.steps if s["task"] == task_id]

    def stops(self, task_id: str) -> list:
        return [r["detail"] for r in store.task_steps(self.conn, task_id)
                if r["action"] == STOP_ACTION]


class Ac29RefusalClassesTest(RefusalClassSandbox):

    def test_ac29_new_actions_in_table_with_their_class(self):
        """Шесть новых действий — в `REFUSAL_CLASSES` своим классом: три «чинит роль», три «чинит Оператор».

        Сценарий: для каждого действия (порядок случайный) — оно есть
        ключом перечня, и `refusal_class` отдаёт «чинит роль» для «честный
        FAIL_TO_PASS», «… тест критерия не в отчёте», «SPEC изменён после
        гейта SPEC» и «чинит Оператор» для «… список «провал проверки» не
        задан», «… отказ подготовки», «… опора SPEC не найдена».

        Ловит мутацию: литерал действия не добавлен в перечень (класс
        Оператора по умолчанию) — ключа нет, у трёх действий роли класс
        «чинит Оператор»; действие подготовки внесено классом «чинит роль».
        """
        cases = ([(a, refusal_classes.ROLE_FIXES) for a in ROLE_CLASS]
                 + [(a, refusal_classes.OPERATOR_FIXES) for a in OPERATOR_CLASS])
        self.rng.shuffle(cases)
        for action, kind in cases:
            with self.subTest(action=action, seed=self.seed):
                self.assertIn(action, refusal_classes.REFUSAL_CLASSES,
                              self.note(action))
                self.assertEqual(refusal_classes.refusal_class(action), kind,
                                 self.note(action))

    def test_ac29_auto_returns_finding_to_test_author(self):
        """`auto` возвращает находку честного `FAIL_TO_PASS` роли test_author: шаг роли с отказом в брифе.

        Сценарий: задача в `tests_writing`; предварительный `advance`
        журналирует «переход отклонён: честный FAIL_TO_PASS» со случайной
        подробностью, после шага роли — переход в ручной гейт. Цикл
        запускает ровно один шаг test_author, его бриф несёт действие и
        подробность отказа; остановки «auto остановлен» нет до перехода.

        Ловит мутацию: действие не в перечне — класс «чинит Оператор»,
        цикл останавливается без шага роли.
        """
        task_id = self.fresh_task("tests_writing")
        detail = self.detail()
        out = self.run_auto(task_id, [(F2P_ACTION, detail), ("->", MANUAL_STOP)])
        steps = self.steps_of(task_id)
        self.assertEqual(len(steps), 1, self.note(out))
        self.assertEqual(steps[0]["role"], "test_author", self.note(out))
        self.assertIn(F2P_ACTION, steps[0]["brief"], self.note(out))
        self.assertIn(detail, steps[0]["brief"], self.note(out))

    def test_ac29_auto_stops_on_operator_class_refusals(self):
        """На пустом списке «провал проверки», отказе подготовки и ненайденной опоре SPEC `auto` останавливается без шага роли.

        Сценарий: для каждого из трёх действий (порядок случайный) — свежая
        задача в `tests_writing`, предварительный `advance` журналирует
        отказ. Шагов роли нет, запись «auto остановлен» называет действие,
        задача осталась в `tests_writing`.

        Ловит мутацию: действие внесено классом «чинит роль» — цикл
        запускает шаг test_author.
        """
        actions = list(OPERATOR_CLASS)
        self.rng.shuffle(actions)
        for action in actions:
            with self.subTest(action=action, seed=self.seed):
                task_id = self.fresh_task("tests_writing")
                out = self.run_auto(task_id, [(action, self.detail())])
                self.assertEqual(self.steps_of(task_id), [], self.note(out))
                stops = self.stops(task_id)
                self.assertTrue(stops and action in stops[-1], self.note(out))
                self.assertEqual(store.get_task(self.conn, task_id)["state"],
                                 "tests_writing", self.note(out))

    def test_ac29_auto_stops_on_repeated_spec_changed_after_role_step(self):
        """Отказ «SPEC изменён после гейта SPEC» — шаг роли; тот же отказ после шага роли — остановка `auto`.

        Сценарий: задача в `tests_writing`; `advance` журналирует отказ
        «SPEC изменён после гейта SPEC» дважды подряд. Цикл запускает один
        шаг test_author и после повтора того же отказа останавливается,
        причина остановки называет действие.

        Ловит мутацию: действие не в перечне — остановка без шага роли
        (шагов ноль); действие внесено в подкласс «роль ещё не закончила» —
        повтор не останавливает цикл, шагов больше одного.
        """
        task_id = self.fresh_task("tests_writing")
        out = self.run_auto(task_id, [(SPEC_CHANGED_ACTION, self.detail()),
                                      (SPEC_CHANGED_ACTION, self.detail())])
        self.assertEqual(len(self.steps_of(task_id)), 1, self.note(out))
        stops = self.stops(task_id)
        self.assertTrue(stops and SPEC_CHANGED_ACTION in stops[-1], self.note(out))


if __name__ == "__main__":
    unittest.main()
