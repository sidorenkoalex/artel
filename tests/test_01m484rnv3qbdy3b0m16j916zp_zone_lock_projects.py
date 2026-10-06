"""Замок зон действует для задачи любого проекта — внутри её проекта.

Группа: долгоживущий
Красен до реализации: `zone_lock.blocking_conflict`/`forecast_overlaps`/`queue_position` и `catalog` (предупреждение `new`, добавка «зона занята» в `status`) пропускают задачи не артели — внешняя задача не получает ни конфликта, ни очереди, ни предупреждения.

SPEC задачи, AC-1 и AC-2 (строки 1-6 таблицы
требования 1): две задачи ОДНОГО внешнего проекта с пересекающимися зонами
— конфликт замка, отказ `run`, позиция в очереди в `status`; задачи РАЗНЫХ
проектов с одинаковыми путями зон друг друга не блокируют. `new` внешнего
проекта предупреждает о пересечении с живой задачей своего проекта, а
`status` задачи до `in_dev` несёт «[зона занята: <id>]».

Имена проектов, пути зон и id задач порождаются модулем `random` при каждом
запуске; зерно печатается и входит в текст провала.
"""
import random
import string

from orchestrator import catalog, config, runner, store, zone_lock
from tests.sandbox import (InitializedTmpRootTest, capture,
                           capture_new_task_id, declare_target,
                           make_project_repo)

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class ZoneProjectsSandbox(InitializedTmpRootTest):
    """Инициализированный пульт с двумя внешними проектами в `targets.yaml`
    и случайными именами/путями сценария."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.ext = "proekt" + "".join(self.rng.choices(string.ascii_lowercase, k=5))
        self.other = "drugoj" + "".join(self.rng.choices(string.ascii_lowercase, k=5))
        declare_target(self.ext)
        declare_target(self.other)
        self.zone = self.random_zone()

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def random_zone(self) -> str:
        word = "".join(self.rng.choices(string.ascii_lowercase, k=7))
        return self.rng.choice([f"src/{word}.py", f"lib/{word}/",
                                f"app/{word}/core.py"])

    def new_id(self) -> str:
        return "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))

    def seed_task(self, target: str, state: str, zones: str,
                  task_id: str = None) -> str:
        task_id = task_id or self.new_id()
        store.insert_task(store.db(), task_id, f"Задача {task_id[-6:]}", state,
                          f"task/{task_id.lower()}-zona", target,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(store.db(), task_id, zones=zones)
        return task_id

    def occupy(self, task_id: str) -> None:
        """Задача заняла зону: атомарный захват от имени разработчика."""
        store.journal(store.db(), task_id, "developer", zone_lock.CLAIM_ACTION,
                      "захват зоны сценария")

    def status_line(self, out: str, task_id: str) -> str:
        lines = [ln for ln in out.splitlines() if ln.startswith(task_id)]
        self.assertEqual(len(lines), 1,
                         self.msg(f"строка {task_id} в status:\n{out}"))
        return lines[0]

    def run_refusal(self, task_id: str) -> str:
        """Текст отказа `run` (SystemExit) — пустая строка, если `run` не
        отказал до запуска шага."""
        try:
            capture(runner.cmd_run, task_id)
        except SystemExit as exc:
            return str(exc.code or "")
        return ""


class ZoneLockSameProjectTest(ZoneProjectsSandbox):

    def test_ac1_same_external_project_conflicts_run_refuses_status_queue(self):
        """Две задачи одного внешнего проекта ждут зону, занятую третьей задачей того же проекта.

        Сценарий: держатель (внешний проект, `in_dev`, захват зоны) и две
        ожидающие задачи того же проекта в `in_dev` с той же зоной.
        Ожидается: у ожидающей `blocking_conflict` называет зону и
        держателя; `run` ожидающей отказывает именованным отказом «зона …
        занята задачей <держатель>» и пишет в журнал
        `zone_lock.REFUSAL_ACTION`; `status` показывает у обеих ожидающих
        ожидание этой зоны и позиции очереди 1/2 и 2/2.

        Ловит мутацию: в `blocking_conflict` осталась развилка `t["target"]
        != config.DEFAULT_TARGET` (или кандидаты-держатели — только задачи
        артели) — конфликта нет, `run` внешней задачи не отказывает по
        зоне, а `status` не несёт «ждёт зоны»; либо `queue_position`
        считает очередь только по артели — у ожидающих нет «очередь N/2».
        """
        holder = self.seed_task(self.ext, "in_dev", self.zone)
        self.occupy(holder)
        waiters = [self.seed_task(self.ext, "in_dev", self.zone)
                   for _ in range(2)]

        for waiter in waiters:
            conflict = zone_lock.blocking_conflict(
                store.db(), waiter, store.get_task(store.db(), waiter))
            self.assertIsNotNone(conflict, self.msg(
                f"задача {waiter} проекта {self.ext} не получила конфликт "
                f"зоны {self.zone}, занятой {holder} того же проекта"))
            self.assertEqual((conflict[0].rstrip("/"), conflict[1]),
                             (self.zone.rstrip("/"), holder), self.msg(
                                 f"конфликт назвал не ту зону/держателя: "
                                 f"{conflict}"))

        refused = self.rng.choice(waiters)
        text = self.run_refusal(refused)
        self.assertIn(f"занята задачей {holder}", text, self.msg(
            f"run {refused} не отказал по зоне; ответ: {text!r}"))
        actions = [r["action"] for r in store.task_steps(store.db(), refused)]
        self.assertIn(zone_lock.REFUSAL_ACTION, actions, self.msg(
            f"журнал {refused} без записи отказа по зоне: {actions}"))

        out = capture(catalog.cmd_status)
        positions = set()
        for waiter in waiters:
            line = self.status_line(out, waiter)
            self.assertIn("ждёт зоны", line, self.msg(
                f"status не показал ожидание зоны у {waiter}: {line}"))
            self.assertIn(holder, line, self.msg(line))
            for pos in ("1/2", "2/2"):
                if f"очередь {pos}" in line:
                    positions.add(pos)
        self.assertEqual(positions, {"1/2", "2/2"}, self.msg(
            f"status не показал позиции очереди зоны:\n{out}"))

    def test_ac1_tasks_of_different_projects_do_not_block_each_other(self):
        """Задачи разных проектов с одинаковыми путями зон друг друга не блокируют.

        Сценарий: в каждом из трёх проектов (артель и два внешних) по
        одной задаче в `in_dev` с одним и тем же путём зоны; одна
        случайная из них заняла зону. Ни одна из остальных не получает
        конфликта и отказа `zone_lock.refusal`, и строка `status` ни у
        одной не несёт «ждёт зоны».

        Ловит мутацию: развилку артели сняли без сверки проекта —
        кандидаты-держатели берутся из задач ВСЕХ проектов, и задача
        другого проекта получает конфликт зоны, занятой чужим
        репозиторием.
        """
        tasks = {target: self.seed_task(target, "in_dev", self.zone)
                 for target in (config.DEFAULT_TARGET, self.ext, self.other)}
        holder_target = self.rng.choice(sorted(tasks))
        self.occupy(tasks[holder_target])
        out = capture(catalog.cmd_status)
        for target, task_id in tasks.items():
            if target == holder_target:
                continue
            row = store.get_task(store.db(), task_id)
            self.assertIsNone(
                zone_lock.blocking_conflict(store.db(), task_id, row),
                self.msg(f"{task_id} ({target}) заблокирован задачей "
                         f"проекта {holder_target}"))
            self.assertIsNone(zone_lock.refusal(store.db(), task_id, row),
                              self.msg(f"отказ {task_id} ({target})"))
            self.assertNotIn("ждёт зоны", self.status_line(out, task_id),
                             self.msg(f"status {task_id} ({target})"))


TZ_TEXT = ("# ТЗ: фикстура зон {word}\n\nТребуется: правка по зонам.\n\n"
           "Зоны: {zones}.\n")


class ZoneForecastExternalTest(ZoneProjectsSandbox):

    def test_ac2_new_of_external_project_warns_about_same_project_overlap(self):
        """`new` внешнего проекта с зоной живой задачи того же проекта печатает и журналирует предупреждение.

        Сценарий: в проекте заведена живая задача (`in_dev`) с зоной;
        задача артели с той же зоной — тоже. `new` внешнего проекта с ТЗ,
        чья строка «Зоны:» называет эту зону, заводит задачу, печатает
        предупреждение о пересечении с задачей своего проекта и пишет в
        её журнал `catalog.ZONE_OVERLAP_ACTION`; задача артели в
        предупреждении не названа (у проектов разные репозитории).

        Ловит мутацию: в `catalog` осталась ранняя отсечка «задача не
        артели предупреждения не получает» — `new` внешнего проекта молчит
        и журнал без записи пересечения; либо прогноз считает задачи всех
        проектов — в предупреждении появляется id задачи артели.
        """
        make_project_repo(self.ext)
        holder = self.seed_task(self.ext, "in_dev", self.zone)
        artel_task = self.seed_task(config.DEFAULT_TARGET, "in_dev", self.zone)
        tz = self.root / ".artel" / f"tz-{self.seed}.md"
        tz.parent.mkdir(parents=True, exist_ok=True)
        tz.write_text(TZ_TEXT.format(word=self.seed, zones=self.zone),
                      encoding="utf-8")
        out, task_id = capture_new_task_id(
            lambda: catalog.cmd_new(f"Фикстура {self.seed}", str(tz),
                                    target=self.ext))
        self.assertTrue(store.task_exists(store.db(), task_id),
                        self.msg("задача не заведена"))
        self.assertIn(holder, out, self.msg(
            f"new не предупредил о пересечении с {holder}:\n{out}"))
        self.assertNotIn(artel_task, out, self.msg(
            f"предупреждение назвало задачу артели {artel_task}:\n{out}"))
        rows = [r for r in store.task_steps(store.db(), task_id)
                if r["action"] == catalog.ZONE_OVERLAP_ACTION]
        self.assertTrue(rows, self.msg("в журнале нет записи пересечения"))
        self.assertIn(holder, rows[-1]["detail"] or "", self.msg(
            f"запись журнала не называет держателя: {rows[-1]['detail']}"))

    def test_ac2_status_suffix_zone_taken_for_external_task_before_in_dev(self):
        """Задача внешнего проекта до `in_dev` получает в `status` добавку «[зона занята: <id>]» от задачи своего проекта.

        Сценарий: для случайного состояния до `in_dev` (`spec_writing`,
        `spec_gate`, `tests_writing`) — задача внешнего проекта с зоной,
        которую держит задача того же проекта в `in_dev`; задача другого
        внешнего проекта с той же зоной тоже в `in_dev`. Строка `status`
        ожидающей несёт «[зона занята: <держатель>]», и держатель другого
        проекта в добавке не назван.

        Ловит мутацию: в `catalog` (добавка прогноза зон) осталась развилка
        `target != DEFAULT_TARGET` — строка внешней задачи без добавки;
        либо прогноз не сверяет проект — в добавке появляется id задачи
        другого проекта.
        """
        holder = self.seed_task(self.ext, "in_dev", self.zone)
        foreign = self.seed_task(self.other, "in_dev", self.zone)
        state = self.rng.choice(sorted(zone_lock.LATER_STATES))
        waiter = self.seed_task(self.ext, state, self.zone)
        line = self.status_line(capture(catalog.cmd_status), waiter)
        self.assertIn(f"[зона занята: {holder}]", line, self.msg(
            f"status {waiter} ({state}) без добавки «зона занята»: {line}"))
        self.assertNotIn(foreign, line, self.msg(
            f"добавка назвала задачу другого проекта {foreign}: {line}"))
