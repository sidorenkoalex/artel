"""Очередь зоны решает, чей первый шаг разработчика стартует на свободной зоне.

Группа: долгоживущий
Красен до реализации: `zone_lock.blocking_conflict`/`claim` решают только по занятости зоны — на свободной зоне `claim` проходит у любой ожидающей задачи, отказов «ждёт очереди зоны: впереди …» и «ждёт зону ради зависимости …» нет, `queue_position` на свободной зоне конкурентов не видит (0/0), а `zone-reorder` без аргументов печатает «переставлена».

SPEC задачи «Очередь зоны решает старт», AC-1..AC-7 и часть AC-8 об
отказе `run`: ожидающие задачи `in_dev` (не занимающие зону) с
пересекающимися — в том числе вложенными — зонами образуют одну очередь;
свободную зону получает первая по очереди задача, которая может
стартовать (живой lease, не на паузе, не в эскалации, без незавершённой
зависимости `merge_after`, ждущей ту же зону). Порядок: позиция
`zone-reorder`, затем зависимость раньше зависящей, затем момент approve
SPEC. `queue_position`, `status` и `doctor` показывают ту же очередь.

«Живой цикл» задачи — живой lease (`lease.acquire` своей сессией);
момент approve SPEC — записи журнала `state -> spec_gate` и следующая за
ней `state -> tests_writing`, тем порядком, каким их пишет `set_state`.

Пути зон, id задач, порядок approve и случаи условий порождаются модулем
`random` при каждом запуске; зерно печатается и входит в текст провала.
"""
import io
import random
import string
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from orchestrator import catalog, config, doctor, lease, runner, store, zone_lock
from tests.sandbox import InitializedTmpRootTest, capture

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
QUEUE_TEXT = "ждёт очереди зоны: впереди"
DEPENDENCY_TEXT = "ждёт зону ради зависимости"
NOT_HOLDING = "не держит очередь"
REORDER_HINT = "zone-reorder <id1> <id2> ..."


class ZoneQueueSandbox(InitializedTmpRootTest):
    """Инициализированный пульт: задачи артели в `in_dev` со случайными
    зонами, порядком approve и живыми lease сценария."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.words = set()

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def word(self) -> str:
        while True:
            word = "".join(self.rng.choices(string.ascii_lowercase, k=7))
            if word not in self.words:
                self.words.add(word)
                return word

    def same_zone(self) -> str:
        word = self.word()
        return self.rng.choice([f"src/{word}.py", f"lib/{word}/",
                                f"app/{word}/core.py"])

    def nested_zones(self, count: int) -> list[str]:
        """`count` попарно пересекающихся вложенных зон: каталог, каталог
        внутри него, …, файл внутри последнего каталога."""
        zones = [f"{self.rng.choice(['src', 'lib', 'app', 'pkg'])}/{self.word()}/"]
        while len(zones) < count - 1:
            zones.append(f"{zones[-1]}{self.word()}/")
        zones.append(f"{zones[-1]}{self.word()}.py")
        return zones

    def new_id(self) -> str:
        return "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))

    def seed_task(self, zones: str, state: str = "in_dev") -> str:
        task_id = self.new_id()
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {task_id[-6:]}", state,
                          f"task/{task_id.lower()}-zona", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(conn, task_id, zones=zones)
        return task_id

    def approve_in_order(self, *task_ids: str) -> None:
        """SPEC задач утверждены в порядке `task_ids`; затем все вошли в
        `in_dev`."""
        conn = store.db()
        for task_id in task_ids:
            store.journal(conn, task_id, "fsm", "state -> spec_gate")
            store.journal(conn, task_id, "fsm", "state -> tests_writing")
        for task_id in task_ids:
            store.journal(conn, task_id, "fsm", "state -> in_dev")

    def make_live(self, *task_ids: str) -> None:
        for task_id in task_ids:
            refusal, _ = lease.acquire(store.db(), task_id, f"sess-{task_id}")
            self.assertIsNone(refusal, self.msg(f"lease {task_id}: {refusal}"))

    def finish(self, *task_ids: str) -> None:
        """Задачи сценария закрыты — зону больше не держат и не ждут."""
        for task_id in task_ids:
            store.update_task(store.db(), task_id, state="done")

    def claim(self, task_id: str) -> str | None:
        conn = store.db()
        refusal, _ = zone_lock.claim(conn, task_id, store.get_task(conn, task_id))
        return refusal

    def assert_claim_passes(self, task_id: str, context: str) -> None:
        refusal = self.claim(task_id)
        self.assertIsNone(refusal, self.msg(
            f"{context}: claim {task_id} отказал: {refusal}"))

    def assert_claim_refused(self, task_id: str, expected: str | None,
                             context: str) -> None:
        refusal = self.claim(task_id)
        self.assertIsNotNone(refusal, self.msg(
            f"{context}: claim {task_id} прошёл, ожидался отказ"
            + (f" с «{expected}»" if expected else "")))
        if expected:
            self.assertIn(expected, refusal, self.msg(
                f"{context}: отказ claim {task_id} без «{expected}»: {refusal}"))

    def status_line(self, out: str, task_id: str) -> str:
        lines = [ln for ln in out.splitlines() if ln.startswith(task_id)]
        self.assertEqual(len(lines), 1,
                         self.msg(f"строка {task_id} в status:\n{out}"))
        return lines[0]

    def doctor_details(self, task_id: str) -> list[str]:
        return [c.detail for c in doctor.check_zone_waits(store.db())
                if c.detail.startswith(task_id)]

    def cannot_start_cases(self, escalation: bool = True) -> dict:
        """Условия AC-5, при которых живая задача `in_dev` не может
        стартовать, — применяются к ней по имени условия."""
        def no_live_cycle(task_id):
            lease.release(store.db(), task_id, f"sess-{task_id}")

        def paused(task_id):
            store.update_task(store.db(), task_id, paused=1)

        def escalated(task_id):
            store.update_task(store.db(), task_id, state="escalated",
                              escalated_from="in_dev")

        cases = {"нет живого цикла": no_live_cycle, "пауза": paused}
        if escalation:
            cases["эскалация"] = escalated
        return cases


class QueueDecidesStartTest(ZoneQueueSandbox):

    def test_ac1_nested_zones_earlier_approve_starts_first(self):
        """Две живые ожидающие задачи с вложенными зонами: свободную зону получает та, чей SPEC утверждён раньше.

        Сценарий: зона свободна; задачи A и B в `in_dev` с живым lease ждут
        вложенные зоны (пара из AC — `orchestrator/` и `orchestrator/ci.py`
        — и случайная пара каталог/файл внутри него; кому из двух достаётся
        каталог — случайно); SPEC задачи B утверждён раньше. `claim` A
        отказывает текстом с «ждёт очереди зоны: впереди <B>», `claim` B
        проходит.

        Ловит мутацию: конкуренты очереди отбираются по точному совпадению
        пути (`==`), а не по `_paths_overlap` — вложенные зоны попадают в
        разные очереди, и `claim` A проходит на свободной зоне вместо
        отказа; либо порядок без позиции Оператора берётся не по моменту
        approve — A оказывается впереди, и отказ получает B.
        """
        pairs = [("orchestrator/", "orchestrator/ci.py"),
                 tuple(self.nested_zones(2))]
        for pair in pairs:
            zone_a, zone_b = self.rng.sample(pair, 2)
            with self.subTest(A=zone_a, B=zone_b):
                a = self.seed_task(zone_a)
                b = self.seed_task(zone_b)
                self.approve_in_order(b, a)
                self.make_live(a, b)
                self.assert_claim_refused(a, f"{QUEUE_TEXT} {b}",
                                          f"A={zone_a}, B={zone_b}")
                self.assert_claim_passes(b, f"A={zone_a}, B={zone_b}")
                self.finish(a, b)

    def test_ac2_zone_reorder_changes_who_starts(self):
        """`zone-reorder A B` переставляет исход: стартует A, B получает отказ «впереди A».

        Сценарий AC-1 (SPEC B утверждён раньше, обе живы, зона свободна) —
        для вложенных и для одинаковых зон: до перестановки `claim` A
        отказывает; после `zone-reorder A B` `claim` B отказывает текстом
        с «ждёт очереди зоны: впереди <A>», `claim` A проходит.

        Ловит мутацию: правило старта берёт порядок только по моменту
        approve и не читает `zone_queue_position` — после `zone-reorder`
        `claim` A по-прежнему отказывает, а B проходит.
        """
        variants = {"вложенные": lambda: self.rng.sample(self.nested_zones(2), 2),
                    "одинаковая": lambda: [self.same_zone()] * 2}
        for kind, make_zones in variants.items():
            with self.subTest(зоны=kind):
                zone_a, zone_b = make_zones()
                a = self.seed_task(zone_a)
                b = self.seed_task(zone_b)
                self.approve_in_order(b, a)
                self.make_live(a, b)
                self.assert_claim_refused(a, f"{QUEUE_TEXT} {b}",
                                          f"{kind}, до перестановки")
                capture(zone_lock.cmd_zone_reorder, [a, b])
                self.assert_claim_refused(b, f"{QUEUE_TEXT} {a}",
                                          f"{kind}, после zone-reorder A B")
                self.assert_claim_passes(a, f"{kind}, после zone-reorder A B")
                self.finish(a, b)

    def test_ac3_dependency_chain_starts_in_dependency_order(self):
        """Цепочка C→B→A по `merge_after` при обратном порядке approve стартует A, затем B, затем C.

        Сценарий: три живые задачи `in_dev` на одной свободной зоне; C
        зависит от B, B — от A; SPEC утверждены в порядке C, B, A. На
        каждом шаге при свободной зоне все, кроме ожидаемой, получают
        отказ, а ожидаемая получает зону: сначала A; после её закрытия
        (`done`) — B; после закрытия B — C. Так ни на одном шаге свободная
        зона не остаётся без задачи, способной её получить.

        Ловит мутацию: топологический порядок по `merge_after` не
        применяется (очередь только по approve) — первой зону получает C,
        у которой незавершённая зависимость, и `claim` C проходит вместо
        отказа; либо задача с незавершённой зависимостью держит очередь —
        `claim` A отказывает, и свободную зону не может получить никто.
        """
        zone = self.same_zone()
        a, b, c = (self.seed_task(zone) for _ in range(3))
        store.update_task(store.db(), b, merge_after=a)
        store.update_task(store.db(), c, merge_after=b)
        self.approve_in_order(c, b, a)
        self.make_live(a, b, c)
        names = {a: "A", b: "B", c: "C"}
        remaining = [a, b, c]
        for expected in (a, b, c):
            step = f"шаг «зону получает {names[expected]}»"
            for other in remaining:
                if other != expected:
                    self.assert_claim_refused(other, None,
                                              f"{step}, задача {names[other]}")
            self.assert_claim_passes(expected, step)
            self.finish(expected)
            remaining.remove(expected)

    def test_ac4_unfinished_dependency_refuses_even_when_reordered_ahead(self):
        """Задача C с незавершённой зависимостью A, ждущей ту же зону, получает отказ «ждёт зону ради зависимости A», зону получает A.

        Сценарий: живые C и A в `in_dev` с пересекающимися (вложенными)
        зонами, `merge_after` C = A, зона свободна, порядок approve
        случайный; вариант без перестановки и вариант, где `zone-reorder
        C A` поставил C впереди. В обоих `claim` C отказывает текстом с
        «ждёт зону ради зависимости <A>», `claim` A проходит.

        Ловит мутацию: позиция Оператора `zone-reorder` главнее проверки
        зависимости — в варианте с перестановкой `claim` C проходит, хотя
        A не завершена; либо отказ зависимости не назван отдельным текстом
        (общий «впереди A») — в отказе нет «ждёт зону ради зависимости».
        """
        for reorder in (False, True):
            with self.subTest(zone_reorder_C_A=reorder):
                zone_a, zone_c = self.rng.sample(self.nested_zones(2), 2)
                a = self.seed_task(zone_a)
                c = self.seed_task(zone_c)
                store.update_task(store.db(), c, merge_after=a)
                order = [a, c]
                self.rng.shuffle(order)
                self.approve_in_order(*order)
                self.make_live(a, c)
                if reorder:
                    capture(zone_lock.cmd_zone_reorder, [c, a])
                context = "после zone-reorder C A" if reorder else "без перестановки"
                self.assert_claim_refused(c, f"{DEPENDENCY_TEXT} {a}", context)
                self.assert_claim_passes(a, context)
                self.finish(a, c)

    def test_ac5_first_waiter_that_cannot_start_does_not_hold_queue(self):
        """Первая по очереди задача без живого цикла, на паузе или в эскалации очередь не держит: `claim` следующей проходит.

        Сценарий (по случаю на условие): живые A и B в `in_dev` ждут
        пересекающиеся зоны, SPEC A утверждён раньше; пока A может
        стартовать, `claim` B отказывает «ждёт очереди зоны: впереди <A>».
        Затем у A снимается lease, либо A ставится на паузу, либо уходит в
        эскалацию — и `claim` B проходит.

        Ловит мутацию: при выборе первой по очереди задачи не проверяется
        одно из условий (живость lease, пометка `paused` или состояние
        эскалации) — A по-прежнему стоит впереди, и `claim` B в этом
        случае отказывает «впереди A», хотя A стартовать не может.
        """
        for name, apply in self.cannot_start_cases().items():
            with self.subTest(условие=name):
                zone_a, zone_b = self.rng.choice(
                    [self.nested_zones(2), [self.same_zone()] * 2])
                a = self.seed_task(zone_a)
                b = self.seed_task(zone_b)
                self.approve_in_order(a, b)
                self.make_live(a, b)
                self.assert_claim_refused(b, f"{QUEUE_TEXT} {a}",
                                          f"{name}: A ещё может стартовать")
                apply(a)
                self.assert_claim_passes(b, f"{name}: A не может стартовать")
                self.finish(a, b)


class ShownQueueTest(ZoneQueueSandbox):

    def assert_shown_queue(self, order: list[str], zones: dict,
                           not_holding: set, context: str) -> None:
        """`queue_position`, `status` и `doctor` показывают `order` одной
        очередью; у задач `not_holding` после «очередь N/M» стоит «не держит
        очередь». Показ первой держащей задачи (той, что стартует) в
        `status`/`doctor` не обязателен, но если он есть — с её позицией и
        без пометки."""
        total = len(order)
        out = capture(catalog.cmd_status)
        starter = next(t for t in order if t not in not_holding)
        for pos, task_id in enumerate(order, 1):
            where = f"{context}, задача {pos}/{total} {task_id}"
            marker = f"очередь {pos}/{total}"
            self.assertEqual(
                zone_lock.queue_position(store.db(), task_id, zones[task_id]),
                (pos, total), self.msg(f"{where}: queue_position"))
            line = self.status_line(out, task_id)
            details = self.doctor_details(task_id)
            if task_id == starter:
                if "очередь" in line:
                    self.assertIn(marker, line, self.msg(f"{where}: {line}"))
                    self.assertNotIn(NOT_HOLDING, line, self.msg(f"{where}: {line}"))
                for detail in details:
                    self.assertIn(marker, detail, self.msg(f"{where}: {detail}"))
                    self.assertNotIn(NOT_HOLDING, detail, self.msg(f"{where}: {detail}"))
                continue
            self.assertIn(marker, line, self.msg(f"{where}: status\n{out}"))
            self.assertTrue(details, self.msg(f"{where}: нет в doctor zone-waits"))
            shown = {"status": line, "doctor": details[0]}
            for source, text in shown.items():
                self.assertIn(marker, text, self.msg(f"{where}: {source}: {text}"))
                if task_id in not_holding:
                    self.assertIn(NOT_HOLDING, text, self.msg(
                        f"{where}: {source} без пометки: {text}"))
                    self.assertGreater(text.index(NOT_HOLDING), text.index(marker),
                                       self.msg(f"{where}: {source}: {text}"))
                else:
                    self.assertNotIn(NOT_HOLDING, text, self.msg(
                        f"{where}: {source} с лишней пометкой: {text}"))

    def seed_queue(self) -> tuple[list[str], dict]:
        """Три живые ожидающие задачи с попарно вложенными зонами, порядок
        approve случайный; возвращает порядок approve и зоны задач."""
        zones = self.nested_zones(3)
        self.rng.shuffle(zones)
        tasks = [self.seed_task(zone) for zone in zones]
        order = list(tasks)
        self.rng.shuffle(order)
        self.approve_in_order(*order)
        self.make_live(*tasks)
        return order, dict(zip(tasks, zones))

    def test_ac6_shown_queue_matches_claim_order(self):
        """Порядок `queue_position`/`status`/`doctor` для вложенных зон совпадает с тем, кому `claim` отдаёт зону.

        Сценарий: три живые задачи `in_dev` с попарно вложенными зонами
        (каталог, подкаталог, файл в нём), зона свободна, порядок approve
        случайный. `queue_position` каждой — (её место по approve, 3), то
        же «очередь N/3» в строках `status` и `doctor` ожидающих, без
        пометки «не держит очередь»; `claim` вторых двух отказывает,
        `claim` первой проходит.

        Ловит мутацию: `queue_position` по-прежнему считает конкурентами
        только задачи с точно тем же путём конфликта (`conflict[0] ==
        path`) — вложенные зоны дают разные «всего» (не 3), и позиции
        расходятся с тем, кому `claim` отдаёт зону.
        """
        order, zones = self.seed_queue()
        self.assert_shown_queue(order, zones, set(), "все держат очередь")
        for task_id in order[1:]:
            self.assert_claim_refused(task_id, QUEUE_TEXT, "все держат очередь")
        self.assert_claim_passes(order[0], "все держат очередь")

    def test_ac6_first_not_holding_stays_shown_and_next_starts(self):
        """Первая по позиции задача, не держащая очередь, остаётся в показе на позиции 1 с пометкой, а `claim` проходит у второй.

        Сценарий (по случаю на условие — нет живого lease, пауза): три
        задачи с попарно вложенными зонами, зона свободна; первая по
        approve не может стартовать. `queue_position` первой — (1, 3), её
        строки `status` и `doctor` несут «очередь 1/3» и после неё «не
        держит очередь»; вторая и третья — позиции 2/3 и 3/3 без пометки;
        `claim` третьей отказывает, `claim` второй проходит.

        Ловит мутацию: задача, не держащая очередь, выкинута из состава
        конкурентов показа (а не помечена) — у неё `queue_position` (0, 2)
        и нет «очередь 1/3», у остальных «всего» 2; либо пометка «не держит
        очередь» не выводится — строка первой без неё.
        """
        for name, apply in self.cannot_start_cases(escalation=False).items():
            with self.subTest(условие=name):
                order, zones = self.seed_queue()
                apply(order[0])
                self.assert_shown_queue(order, zones, {order[0]}, name)
                self.assert_claim_refused(order[2], QUEUE_TEXT, name)
                self.assert_claim_passes(order[1], name)
                self.finish(*order)


class ZoneReorderWithoutArgsTest(ZoneQueueSandbox):

    def test_ac7_zone_reorder_without_args_refuses_and_changes_nothing(self):
        """`zone-reorder` без аргументов — отказ с подсказкой формы вызова, позиции очереди не меняются.

        Сценарий: несколько задач со случайными `zone_queue_position`
        (часть — не переставлялась вовсе, `NULL`). Вызов без аргументов
        завершается `SystemExit` с ненулевым кодом; вывод (stdout, stderr
        и текст выхода) несёт «zone-reorder <id1> <id2> ...» и не несёт
        «переставлена»; `zone_queue_position` всех задач — прежние.

        Ловит мутацию: пустой список не отсекается до цикла перестановки —
        команда печатает «[очередь ожидания зоны] переставлена Оператором:
        » и завершается без отказа.
        """
        positions = {}
        for _ in range(self.rng.randint(2, 4)):
            task_id = self.seed_task(self.same_zone())
            position = self.rng.choice([None, self.rng.randrange(10)])
            store.update_task(store.db(), task_id, zone_queue_position=position)
            positions[task_id] = position
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit, msg=self.msg(
                    "zone-reorder без аргументов не отказал")) as caught:
                zone_lock.cmd_zone_reorder([])
        code = caught.exception.code
        self.assertNotIn(code, (0, None), self.msg(f"код выхода {code!r}"))
        text = out.getvalue() + err.getvalue() + (code if isinstance(code, str) else "")
        self.assertIn(REORDER_HINT, text, self.msg(f"нет подсказки: {text!r}"))
        self.assertNotIn("переставлена", text, self.msg(f"вывод: {text!r}"))
        after = {task_id: store.get_task(store.db(), task_id)["zone_queue_position"]
                 for task_id in positions}
        self.assertEqual(after, positions, self.msg("zone_queue_position изменились"))


class RunRefusalTest(ZoneQueueSandbox):

    def run_refusal(self, task_id: str) -> str:
        """Текст отказа `run` (SystemExit) — пустая строка, если `run` не
        отказал."""
        try:
            capture(runner.cmd_run, task_id)
        except SystemExit as exc:
            return str(exc.code or "")
        return ""

    def test_ac8_run_behind_queue_refuses_without_developer_step(self):
        """`run` задачи не впереди очереди на свободной зоне отказывает «ждёт очереди зоны: впереди <id>» и не запускает агента.

        Сценарий: живая A и B в `in_dev` с пересекающимися зонами (случайно
        вложенными или одинаковыми), SPEC A утверждён раньше, зона
        свободна. `run` B завершается отказом с «ждёт очереди зоны: впереди
        <A>», журнал B несёт `zone_lock.REFUSAL_ACTION`, запуск агента
        (`runner.run_agent_once`, подменён шпионом) не вызывался.

        Ловит мутацию: новый отказ очереди вычисляется отдельной функцией,
        которую зовут `status`/`doctor`, но не `zone_lock.claim` — `run` B
        проходит замок зоны и доходит до запуска агента, шпион вызван.
        """
        zone_a, zone_b = self.rng.choice(
            [self.rng.sample(self.nested_zones(2), 2), [self.same_zone()] * 2])
        a = self.seed_task(zone_a)
        b = self.seed_task(zone_b)
        self.approve_in_order(a, b)
        self.make_live(a)
        spy = mock.Mock(return_value=None)
        with mock.patch.object(runner, "run_agent_once", spy):
            text = self.run_refusal(b)
        self.assertIn(f"{QUEUE_TEXT} {a}", text, self.msg(
            f"run {b} не отказал по очереди; ответ: {text!r}"))
        actions = [r["action"] for r in store.task_steps(store.db(), b)]
        self.assertIn(zone_lock.REFUSAL_ACTION, actions, self.msg(
            f"журнал {b} без записи отказа по зоне: {actions}"))
        self.assertFalse(spy.called, self.msg("run запустил агента"))
