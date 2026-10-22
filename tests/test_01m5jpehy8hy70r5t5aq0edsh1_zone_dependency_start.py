"""Незавершённая зависимость `merge_after` с общей зоной держит старт последователя в любом состоянии.

Группа: долгоживущий
Красен до реализации: `zone_lock` ищет ждущую зависимость только среди задач очереди (`in_dev`) и только прямую — зависимость в `escalated`/`spec_writing`/`spec_audit`/`spec_gate`/`tests_writing` и транзитивная старт не держат (`claim` C проходит), задача, ждущая такую зависимость, держит очередь (`claim` D отказывает), а `doctor` не пишет «взаимная блокировка» и выходов `answer`/`zone-release`; `merge_after` с id, которого нет в БД, роняет `claim` (`store.get_task` в обходе зависимостей очереди — «Задача … не найдена»); тесты прежнего поведения (AC-4, AC-5, отрицательный AC-7) зелены и сейчас.

Критерии AC-1..AC-7 и AC-9 задачи «Зависимость merge_after с общей зоной
держит старт последователя в любом незавершённом состоянии»: первый шаг
разработчика задачи C (`in_dev`, зона свободна) не стартует, пока у неё
есть прямая или транзитивная зависимость `merge_after` в любом состоянии,
кроме `done`/`killed`, с пересекающейся зоной; отказ и показ называют
зависимость и её состояние; занятая другой задачей зона главнее; задача,
ждущая зону ради зависимости, очередь не держит; `doctor` (`zone-waits`)
называет уже возникшую взаимную блокировку и выходы Оператора.

Связка: `zone_lock.claim` — БД пульта (`store`, журнал занятости, lease) —
показ `catalog.cmd_status`/`doctor.check_zone_waits`; песочница —
инициализированный пульт `InitializedTmpRootTest` (приём песочницы очереди
зоны). Пути зон, id задач и состояния зависимостей порождаются модулем
`random` при каждом запуске; зерно печатается и входит в текст провала.
"""
import random
import string
from contextlib import contextmanager

from orchestrator import catalog, config, doctor, lease, store, zone_lock
from tests.sandbox import InitializedTmpRootTest, capture

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
DEPENDENCY_TEXT = "ждёт зону ради зависимости"
QUEUE_TEXT = "ждёт очереди зоны: впереди"
NOT_HOLDING = "не держит очередь"
MUTUAL = "взаимная блокировка"
DEFERRED = "после перехода держателя в merge_gate"
MANDATE = "Зависимости мержа:"

# Состояния зависимости из AC-1 — зону ещё не занимают.
EARLY_STATES = ("escalated", "spec_writing", "spec_audit", "spec_gate",
                "tests_writing")
# Любое незавершённое состояние (AC-4).
UNFINISHED_STATES = EARLY_STATES + ("in_dev", "review", "verifying",
                                    "acceptance", "merge_gate")


class DependencyZoneSandbox(InitializedTmpRootTest):
    """Инициализированный пульт: задачи артели со случайными зонами,
    зависимостями `merge_after`, порядком approve и живыми lease."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.words = set()
        self.seeded = []

    @contextmanager
    def case(self, *args, **kwargs):
        """Подслучай: задачи, заведённые в нём, закрываются (`done`) и при
        провале — следующий подслучай их не видит."""
        try:
            with self.subTest(*args, **kwargs):
                yield
        finally:
            for task_id in self.seeded:
                store.update_task(store.db(), task_id, state="done")
            self.seeded = []

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
        zones = [f"{self.rng.choice(['src', 'lib', 'app', 'pkg'])}/{self.word()}/"]
        while len(zones) < count - 1:
            zones.append(f"{zones[-1]}{self.word()}/")
        zones.append(f"{zones[-1]}{self.word()}.py")
        return zones

    def overlapping(self, count: int) -> list[str]:
        """`count` попарно пересекающихся зон: случайно вложенные (в
        случайном порядке) либо одна и та же."""
        if self.rng.random() < 0.5:
            zones = self.nested_zones(count)
            self.rng.shuffle(zones)
            return zones
        return [self.same_zone()] * count

    def new_id(self) -> str:
        return "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))

    def seed_task(self, zones: str, state: str = "in_dev",
                  merge_after: str | None = None) -> str:
        task_id = self.new_id()
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {task_id[-6:]}", state,
                          f"task/{task_id.lower()}-zona", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(conn, task_id, zones=zones)
        self.seeded.append(task_id)
        if merge_after is not None:
            store.update_task(conn, task_id, merge_after=merge_after)
        if state == "escalated":
            # Эскалация до первого шага разработчика: старта нет.
            store.update_task(conn, task_id, escalated_from="in_dev")
        return task_id

    def set_state(self, task_id: str, state: str) -> None:
        store.update_task(store.db(), task_id, state=state)

    def occupy(self, task_id: str) -> None:
        """Старт разработчика записан: задача занимает свои зоны."""
        store.journal(store.db(), task_id, "developer", zone_lock.CLAIM_ACTION)

    def approve_in_order(self, *task_ids: str) -> None:
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

    def claim(self, task_id: str) -> str | None:
        conn = store.db()
        refusal, _ = zone_lock.claim(conn, task_id, store.get_task(conn, task_id))
        return refusal

    def assert_claim_passes(self, task_id: str, context: str) -> None:
        refusal = self.claim(task_id)
        self.assertIsNone(refusal, self.msg(
            f"{context}: claim {task_id} отказал: {refusal}"))

    def assert_claim_refused(self, task_id: str, context: str) -> str:
        refusal = self.claim(task_id)
        self.assertIsNotNone(refusal, self.msg(
            f"{context}: claim {task_id} прошёл, ожидался отказ"))
        return refusal

    def assert_names_dependency(self, text: str, dep: str, state: str,
                                context: str) -> None:
        self.assertIn(f"{DEPENDENCY_TEXT} {dep}", text, self.msg(
            f"{context}: нет «{DEPENDENCY_TEXT} {dep}»: {text}"))
        self.assertIn(state, text, self.msg(
            f"{context}: не названо состояние {state}: {text}"))

    def status_line(self, task_id: str) -> str:
        out = capture(catalog.cmd_status)
        lines = [ln for ln in out.splitlines() if ln.startswith(task_id)]
        self.assertEqual(len(lines), 1,
                         self.msg(f"строка {task_id} в status:\n{out}"))
        return lines[0]

    def zone_wait_checks(self) -> list:
        return [c for c in doctor.check_zone_waits(store.db())
                if c.name == "zone-waits"]

    def doctor_detail(self, task_id: str) -> str:
        details = [c.detail for c in self.zone_wait_checks()
                   if c.detail.startswith(task_id)]
        self.assertTrue(details, self.msg(f"{task_id} нет в doctor zone-waits"))
        return "\n".join(details)

    # --- сценарии, общие для критериев и для AC-9 ---

    def scenario_early_dependency_refuses(self, state: str) -> None:
        """C в `in_dev` (зона свободна), зависимость A с общей зоной в
        `state`: `claim` C отказывает с «ждёт зону ради зависимости A» и
        названием состояния A."""
        zone_a, zone_c = self.overlapping(2)
        a = self.seed_task(zone_a, state)
        c = self.seed_task(zone_c, merge_after=a)
        self.approve_in_order(c)
        self.make_live(c)
        refusal = self.assert_claim_refused(c, f"A в {state}")
        self.assert_names_dependency(refusal, a, state, f"A в {state}")

    def scenario_finished_dependency_releases(self, final: str) -> None:
        """Зависимость A в `escalated` держит старт C; после перевода A в
        `final` (`done`/`killed`) `claim` C проходит."""
        zone_a, zone_c = self.overlapping(2)
        a = self.seed_task(zone_a, "escalated")
        c = self.seed_task(zone_c, merge_after=a)
        self.approve_in_order(c)
        self.make_live(c)
        self.assert_claim_refused(c, f"A в escalated (до перевода в {final})")
        self.set_state(a, final)
        self.assert_claim_passes(c, f"A переведена в {final}")

    def scenario_transitive_refuses(self) -> None:
        """Цепочка C → B → A, общая зона только у C и A, A в `escalated`,
        B — в случайном раннем состоянии с другой зоной: `claim` C
        отказывает и называет A."""
        zone_a, zone_c = self.overlapping(2)
        a = self.seed_task(zone_a, "escalated")
        b_state = self.rng.choice(EARLY_STATES)
        b = self.seed_task(self.same_zone(), b_state, merge_after=a)
        c = self.seed_task(zone_c, merge_after=b)
        self.approve_in_order(c)
        self.make_live(c)
        context = f"C → B({b_state}) → A(escalated)"
        refusal = self.assert_claim_refused(c, context)
        self.assertIn(f"{DEPENDENCY_TEXT} {a}", refusal, self.msg(
            f"{context}: отказ не называет A {a}: {refusal}"))

    def scenario_occupied_wins(self) -> None:
        """Зону C занимает другая задача O (старт разработчика записан),
        зависимость A с общей зоной не завершена: отказ `claim` C —
        «занята» с именем O, без «ждёт зону ради зависимости»."""
        zone_a, zone_c, zone_o = self.overlapping(3)
        a_state = self.rng.choice(EARLY_STATES)
        a = self.seed_task(zone_a, a_state)
        o = self.seed_task(zone_o, self.rng.choice(("in_dev", "review",
                                                    "merge_gate")))
        self.occupy(o)
        c = self.seed_task(zone_c, merge_after=a)
        self.approve_in_order(c)
        self.make_live(c)
        context = f"зона занята O, A в {a_state}"
        refusal = self.assert_claim_refused(c, context)
        self.assertIn("занята", refusal, self.msg(f"{context}: {refusal}"))
        self.assertIn(o, refusal, self.msg(
            f"{context}: отказ не называет держателя {o}: {refusal}"))
        self.assertNotIn(DEPENDENCY_TEXT, refusal, self.msg(
            f"{context}: конфликт «зависимость» вместо «занята»: {refusal}"))

    def scenario_dependency_waiter_does_not_hold_queue(self) -> None:
        """C (живой lease) ждёт зависимость A в `escalated` с общей
        свободной зоной, D (живой) стоит позади C в очереди той же зоны:
        `status` и `doctor` называют у C зависимость A, её состояние и
        «не держит очередь»; `claim` D проходит."""
        zone_a, zone_c, zone_d = self.overlapping(3)
        a = self.seed_task(zone_a, "escalated")
        c = self.seed_task(zone_c, merge_after=a)
        d = self.seed_task(zone_d)
        self.approve_in_order(c, d)
        self.make_live(c, d)
        shown = {"status": self.status_line(c), "doctor": self.doctor_detail(c)}
        for source, text in shown.items():
            self.assert_names_dependency(text, a, "escalated", f"{source} C")
            self.assertIn(NOT_HOLDING, text, self.msg(
                f"{source}: C без «{NOT_HOLDING}»: {text}"))
        self.assert_claim_passes(d, "C ждёт зависимость A, D позади C")

    def seed_mutual_block(self, holder_state: str, transitive: bool) -> tuple:
        """Держатель C занимает зону (старт разработчика записан) в
        `holder_state` и зависит от A — прямо либо через B; A в `in_dev`
        ждёт ту же зону. Возвращает (A, C)."""
        zone_a, zone_c = self.overlapping(2)
        a = self.seed_task(zone_a)
        dep = a
        if transitive:
            dep = self.seed_task(self.same_zone(), self.rng.choice(EARLY_STATES),
                                 merge_after=a)
        c = self.seed_task(zone_c, holder_state, merge_after=dep)
        self.occupy(c)
        return a, c

    def mutual_text(self, a: str, c: str, context: str) -> str:
        checks = self.zone_wait_checks()
        text = "\n".join(ch.detail for ch in checks)
        self.assertTrue(any(a in ch.detail and f"{MUTUAL} с {c} по merge_after"
                            in ch.detail for ch in checks), self.msg(
            f"{context}: нет «{MUTUAL} с {c} по merge_after» для {a}:\n{text}"))
        for ch in checks:
            self.assertEqual(ch.status, "warn", self.msg(
                f"{context}: уровень {ch.status}: {ch.detail}"))
        self.assertIn(f"zone-release {a}", text, self.msg(
            f"{context}: нет выхода «zone-release {a}»:\n{text}"))
        self.assertIn(f"answer {c}", text, self.msg(
            f"{context}: нет выхода «answer {c}»:\n{text}"))
        self.assertIn(MANDATE, text, self.msg(
            f"{context}: нет строки мандата «{MANDATE}»:\n{text}"))
        return text

    def scenario_no_mutual_block_without_dependency(self, variant: str) -> None:
        """A в `in_dev` ждёт зону, занятую X, которая от A не зависит ни
        прямо, ни транзитивно (`variant`): `doctor` показывает ожидание A,
        но строку «взаимная блокировка» не пишет."""
        zone_a, zone_x = self.overlapping(2)
        x_state = self.rng.choice(("in_dev", "review", "merge_gate",
                                   "escalated"))
        if variant == "X — зависимость A":
            x = self.seed_task(zone_x, x_state)
            a = self.seed_task(zone_a, merge_after=x)
        elif variant == "X зависит от посторонней задачи":
            other = self.seed_task(self.same_zone(), self.rng.choice(EARLY_STATES))
            x = self.seed_task(zone_x, x_state, merge_after=other)
            a = self.seed_task(zone_a)
        else:
            x = self.seed_task(zone_x, x_state)
            a = self.seed_task(zone_a)
        self.occupy(x)
        context = f"{variant}, X в {x_state}"
        detail = self.doctor_detail(a)
        self.assertIn(x, detail, self.msg(f"{context}: ожидание A без X: {detail}"))
        text = "\n".join(ch.detail for ch in self.zone_wait_checks())
        self.assertNotIn(MUTUAL, text, self.msg(
            f"{context}: ложная «{MUTUAL}»:\n{text}"))


class DependencyHoldsStartTest(DependencyZoneSandbox):

    def test_ac1_dependency_in_early_state_refuses_claim(self):
        """Зависимость A с общей зоной в каждом из ранних состояний держит старт C, отказ называет A и её состояние.

        Сценарий (по случаю на состояние `escalated` до первого шага
        разработчика, `spec_writing`, `spec_audit`, `spec_gate`,
        `tests_writing`): C в `in_dev` с живым lease, `merge_after` C = A,
        зоны C и A пересекаются (вложенные либо одинаковые), зону никто не
        занимает. `claim` C отказывает текстом с «ждёт зону ради
        зависимости <A>» и названием состояния A.

        Ловит мутацию: зависимость ищется только в составе очереди зоны
        (прежнее правило `in_dev`) — A в раннем состоянии не видна,
        `claim` C проходит; либо состояние зависимости в текст не
        подставлено — отказ без названия состояния.
        """
        for state in EARLY_STATES:
            with self.case(состояние_A=state):
                self.scenario_early_dependency_refuses(state)

    def test_ac2_done_killed_or_missing_dependency_does_not_hold(self):
        """После перевода A в `done` или `killed` `claim` C проходит; зависимость, которой нет в БД, старт не держит.

        Сценарий: A в `escalated` с общей зоной держит `claim` C
        (предусловие); A переводится в `done` — `claim` C проходит;
        отдельно (новая пара) — в `killed`, `claim` C проходит. Отдельно:
        `merge_after` C — id, которого нет в БД; `claim` C проходит.

        Ловит мутацию: «завершённым» считается только `done` — `killed`
        зависимость держит старт, и `claim` C после перевода A в `killed`
        отказывает; либо отсутствующая в БД зависимость считается
        незавершённой (или падает чтением строки) — `claim` C отказывает
        или бросает исключение.
        """
        for final in ("done", "killed"):
            with self.case(A_переведена_в=final):
                self.scenario_finished_dependency_releases(final)
        with self.case(зависимость="нет в БД"):
            c = self.seed_task(self.same_zone(), merge_after=self.new_id())
            self.approve_in_order(c)
            self.make_live(c)
            self.assert_claim_passes(c, "зависимости нет в БД")

    def test_ac3_transitive_dependency_refuses_claim(self):
        """Цепочка C → B → A, общая зона только у C и A, A в `escalated`: `claim` C отказывает и называет A.

        Сценарий: B зависит от A, C — от B; зона B не пересекается ни с
        C, ни с A, B в случайном раннем состоянии; зона C и A общая, никем
        не занята. `claim` C отказывает с «ждёт зону ради зависимости <A>».

        Ловит мутацию: проверяются только прямые зависимости C — у B
        общей зоны нет, транзитивная A не видна, `claim` C проходит.
        """
        self.scenario_transitive_refuses()

    def test_ac4_dependency_without_shared_zone_and_escalated_non_dependency(self):
        """Зависимость без общей зоны в любом незавершённом состоянии старт не держит; эскалированная задача без `merge_after` очередь не держит.

        Сценарий 1 (по случаю на каждое незавершённое состояние A): зона A
        не пересекается с зоной C, `merge_after` C = A; `claim` C проходит.
        Сценарий 2: живые A и B в `in_dev` ждут пересекающиеся зоны, SPEC A
        утверждён раньше, `merge_after` у обеих нет; `claim` B отказывает
        «ждёт очереди зоны: впереди <A>»; A уходит в `escalated` — `claim`
        B проходит.

        Ловит мутацию: пересечение зон для зависимостей не проверяется
        (держит любая незавершённая зависимость) — в сценарии 1 `claim` C
        отказывает «ради зависимости A»; либо эскалированная задача без
        зависимости держит очередь — в сценарии 2 `claim` B после
        эскалации A по-прежнему отказывает.
        """
        for state in UNFINISHED_STATES:
            with self.case(состояние_A=state, общая_зона=False):
                a = self.seed_task(self.same_zone(), state)
                c = self.seed_task(self.same_zone(), merge_after=a)
                self.approve_in_order(c)
                self.make_live(c)
                self.assert_claim_passes(c, f"A в {state} без общей зоны")
        with self.case(сценарий="эскалированная без merge_after"):
            zone_a, zone_b = self.overlapping(2)
            a = self.seed_task(zone_a)
            b = self.seed_task(zone_b)
            self.approve_in_order(a, b)
            self.make_live(a, b)
            refusal = self.assert_claim_refused(b, "A ещё в in_dev")
            self.assertIn(f"{QUEUE_TEXT} {a}", refusal, self.msg(refusal))
            store.update_task(store.db(), a, state="escalated",
                              escalated_from="in_dev")
            self.assert_claim_passes(b, "A в escalated, не зависимость B")

    def test_ac5_occupied_zone_wins_over_dependency(self):
        """Зона C занята другой задачей при незавершённой зависимости A с общей зоной: отказ — «занята» с именем держателя.

        Сценарий: держатель O (in_dev/review/merge_gate, старт разработчика
        записан) занимает зону, пересекающуюся с зоной C; зависимость A с
        общей зоной в раннем состоянии. Отказ `claim` C несёт «занята» и id
        O и не несёт «ждёт зону ради зависимости».

        Ловит мутацию: проверка ждущей зависимости поставлена раньше
        держателя зоны — отказ называет «ждёт зону ради зависимости A»
        вместо «занята O».
        """
        self.scenario_occupied_wins()


class DependencyShownTest(DependencyZoneSandbox):

    def test_ac6_status_and_doctor_name_dependency_and_state(self):
        """`status` и `doctor` (`zone-waits`) для C из AC-1 называют зависимость A и её состояние.

        Сценарий (по случаю на каждое раннее состояние A): C в `in_dev` —
        единственная ожидающая на свободной зоне, зависимость A с общей
        зоной. Строка C в `status` и деталь C в `doctor` несут «ждёт зону
        ради зависимости <A>» и название состояния A.

        Ловит мутацию: показ берёт причину по прежнему правилу (зависимость
        только из очереди) — C в `status`/`doctor` не показана вовсе либо
        без «ради зависимости A»; либо состояние в `_reason` не подставлено.
        """
        for state in EARLY_STATES:
            with self.case(состояние_A=state):
                zone_a, zone_c = self.overlapping(2)
                a = self.seed_task(zone_a, state)
                c = self.seed_task(zone_c, merge_after=a)
                self.approve_in_order(c)
                self.make_live(c)
                shown = {"status": self.status_line(c),
                         "doctor": self.doctor_detail(c)}
                for source, text in shown.items():
                    self.assert_names_dependency(text, a, state,
                                                 f"{source}, A в {state}")

    def test_ac6_dependency_waiter_does_not_hold_queue(self):
        """C с живым циклом ждёт зависимость A в `escalated`: D позади C получает зону, C показана с «не держит очередь».

        Сценарий: C и D в `in_dev` с живыми lease, SPEC C утверждён раньше
        D; A — зависимость C в `escalated` с пересекающейся зоной; зону
        никто не занимает. Строки C в `status` и `doctor` несут зависимость
        A, её состояние и «не держит очередь»; `claim` D проходит.

        Ловит мутацию: `_holds_queue` ищет зависимость только в составе
        очереди (прежнее правило) — C держит очередь, `claim` D отказывает
        «впереди C», а показ C идёт без «не держит очередь».
        """
        self.scenario_dependency_waiter_does_not_hold_queue()


class MutualBlockDoctorTest(DependencyZoneSandbox):

    def test_ac7_mutual_block_holder_in_answerable_state(self):
        """Держатель C в `merge_gate` (прямо и транзитивно) или `in_dev` зависит от ждущей A: `doctor` пишет взаимную блокировку и оба выхода, `answer` — прямо.

        Сценарий: C занимает зону (старт разработчика записан), A в
        `in_dev` ждёт ту же зону; `merge_after` C = A, либо C → B → A. В
        проверке `zone-waits` деталь A несёт «взаимная блокировка с <C> по
        merge_after»; выходы — «answer <C>» со строкой «Зависимости мержа:»
        без оговорки «после перехода держателя в merge_gate» и «zone-release
        <A>»; уровень всех строк `zone-waits` — `warn`.

        Ловит мутацию: зависимость держателя от ждущей проверяется только
        прямо — в транзитивном случае строки «взаимная блокировка» нет; либо
        набор состояний прямого `answer` не включает `merge_gate`/`in_dev` —
        выход напечатан с оговоркой «после перехода»; либо проверка
        выдана уровнем incident.
        """
        cases = [("merge_gate", False), ("merge_gate", True), ("in_dev", False)]
        for holder_state, transitive in cases:
            context = f"C в {holder_state}, транзитивно={transitive}"
            with self.case(context):
                a, c = self.seed_mutual_block(holder_state, transitive)
                text = self.mutual_text(a, c, context)
                self.assertNotIn(DEFERRED, text, self.msg(
                    f"{context}: «answer» с оговоркой «{DEFERRED}»:\n{text}"))

    def test_ac7_mutual_block_holder_in_verifying_defers_answer(self):
        """Держатель C в `verifying`: выход `answer` напечатан с оговоркой «после перехода держателя в merge_gate», `zone-release` — прямо.

        Сценарий: C в `verifying` занимает зону и зависит от A, A в
        `in_dev` ждёт ту же зону. Деталь `zone-waits` несёт «взаимная
        блокировка с <C> по merge_after», «после перехода держателя в
        merge_gate: answer <C>», строку «Зависимости мержа:» и «zone-release
        <A>»; уровень — `warn`.

        Ловит мутацию: выход `answer` печатается прямо в любом состоянии
        держателя — оговорки «после перехода держателя в merge_gate» нет.
        """
        a, c = self.seed_mutual_block("verifying", False)
        text = self.mutual_text(a, c, "C в verifying")
        self.assertIn(f"{DEFERRED}: answer {c}", text, self.msg(
            f"C в verifying: нет «{DEFERRED}: answer {c}»:\n{text}"))

    def test_ac7_no_mutual_block_when_holder_does_not_depend(self):
        """A ждёт зону, занятую X, не зависящей от A: строки «взаимная блокировка» нет.

        Сценарий (по случаю на вариант): X без `merge_after`; X — сама
        зависимость A (`merge_after` A = X); X зависит от посторонней
        задачи. X занимает зону, A в `in_dev` её ждёт. `doctor` показывает
        ожидание A с X, но ни одна строка `zone-waits` не несёт «взаимная
        блокировка».

        Ловит мутацию: взаимная блокировка печатается без проверки
        зависимости держателя от ждущей (по одному факту «ждёт занятую
        зону» или по зависимости в обратную сторону A → X) — строка
        «взаимная блокировка с X» появляется.
        """
        for variant in ("X без merge_after", "X — зависимость A",
                        "X зависит от посторонней задачи"):
            with self.case(вариант=variant):
                self.scenario_no_mutual_block_without_dependency(variant)


class MutationSensitivityTest(DependencyZoneSandbox):

    def test_ac9_each_named_mutation_has_distinguishing_scenario(self):
        """Каждая мутация AC-9 меняет исход своего различающего сценария.

        Сценарии (по случаю на мутацию): (1) зависимость в `spec_writing`
        вне очереди — `claim` C отказывает; (2) C, ждущая зависимость, —
        `claim` D позади неё проходит; (3) транзитивная цепочка — `claim` C
        отказывает с A; (4) зависимость переведена в `killed` — `claim` C
        проходит; (5) зона занята O — отказ «занята O», не «зависимость»;
        (6) X без зависимости от A — «взаимная блокировка» не пишется.

        Ловит мутацию: (1) `_start_conflict` ищет зависимость только в
        составе очереди — `claim` C проходит; (2) `_holds_queue` по
        прежнему правилу — `claim` D отказывает «впереди C»; (3) без
        транзитивности — `claim` C проходит; (4) `killed` держит старт —
        `claim` C отказывает; (5) «зависимость» главнее «занята» — отказ
        без имени O; (6) блокировка без проверки зависимости держателя —
        строка «взаимная блокировка» появляется.
        """
        scenarios = {
            "зависимость только из очереди в _start_conflict":
                lambda: self.scenario_early_dependency_refuses("spec_writing"),
            "_holds_queue по прежнему правилу":
                self.scenario_dependency_waiter_does_not_hold_queue,
            "без транзитивной зависимости": self.scenario_transitive_refuses,
            "killed-зависимость держит старт":
                lambda: self.scenario_finished_dependency_releases("killed"),
            "«зависимость» главнее «занята»": self.scenario_occupied_wins,
            "взаимная блокировка без проверки зависимости держателя":
                lambda: self.scenario_no_mutual_block_without_dependency(
                    "X без merge_after"),
        }
        for mutation, scenario in scenarios.items():
            with self.case(мутация=mutation):
                scenario()
