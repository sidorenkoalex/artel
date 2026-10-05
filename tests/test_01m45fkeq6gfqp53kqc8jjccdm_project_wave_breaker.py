"""Стоп-кран волны работает по проекту: счёт, алерт, отказ `run`, пометка `status`.

Группа: долгоживущий
Красен до реализации: счётчик стоп-крана считает и алерт заводит только для задач артели (`config.DEFAULT_TARGET`), отказ `run` и пометка `status` действуют только для её задач — внешний проект волны не получает.

Внешний проект — запись в `config.TARGETS` песочницы (`make_project_repo`),
задачи — строки БД с его `target`. Журнал отказов пишется публичным
`store.journal` теми же действиями, что журналирует шаг роли
(`alerts.WAVE_BREAKER_FAILURE_ACTION`/`WAVE_BREAKER_TIMEOUT_ACTION`), а
срабатывание решают публичные `alerts.check_wave_breaker_failure`/
`check_wave_breaker_timeout` — те же, что зовёт `runner` после записи
отказа. Порог и окно — из `config`, не литералами.
"""

import random
import unittest
from unittest import mock

from orchestrator import alerts, catalog, config, failure_classification, runner, store
from tests.sandbox import InitializedTmpRootTest, capture, make_project_repo

PROJECT_NAMES = ("ext", "vneshniy", "sled", "client-app")
NON_AGENT_STATE = "spec_gate"
RUN_STATE = "review"


class AgentStartAttempted(Exception):
    """Шаг дошёл до запуска агента — в песочнице дальше идти нельзя."""


class ProjectWaveBreakerSandbox(InitializedTmpRootTest):
    """Песочница с внешним проектом и счётчиком задач."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.project = self.rng.choice(PROJECT_NAMES)
        make_project_repo(self.project)
        self.conn = store.db()
        self.next_number = 100

    def where(self) -> str:
        return f"зерно {self.seed}, проект {self.project}"

    def make_task(self, target: str, state: str = NON_AGENT_STATE) -> str:
        self.next_number += 1
        task_id = f"T{self.next_number}"
        store.insert_task(self.conn, task_id, f"Задача {task_id}", state,
                          f"task/{task_id.lower()}", target,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def journal_failure(self, task_id: str, failure_class: str) -> None:
        label = failure_classification.CLASS_LABELS[failure_class]
        store.journal(self.conn, task_id, "developer",
                      alerts.WAVE_BREAKER_FAILURE_ACTION,
                      f"попытка 1/3: {label}; текст: ...")

    def journal_timeout(self, task_id: str) -> None:
        store.journal(self.conn, task_id, "developer",
                      alerts.WAVE_BREAKER_TIMEOUT_ACTION,
                      f"{config.AGENT_TIMEOUT_SEC // 60} мин, попытка 1/1")

    def breaker_alerts(self) -> list:
        return [row for row in alerts.open_alerts(self.conn, "incident")
                if row["source"] == alerts.WAVE_BREAKER_SOURCE]

    def open_breaker_alert(self, target: str) -> None:
        label = failure_classification.CLASS_LABELS[
            self.rng.choice(failure_classification.TRANSIENT_SYSTEM_CLASSES)]
        opened = alerts.raise_alert(
            self.conn, target, "incident", alerts.WAVE_BREAKER_SOURCE,
            f"стоп-кран волны: {label} у {config.WAVE_BREAKER_TASKS} задач "
            f"за {config.WAVE_BREAKER_WINDOW_SEC // 60} минут")
        assert opened, "фикстура не смогла завести алерт стоп-крана"

    def run_step(self, task_id: str):
        """`runner.cmd_run` задачи; агент не стартует ни при каком исходе.

        Возвращает (текст отказа или None, был ли запрошен старт агента,
        записи журнала задачи, сделанные этим вызовом)."""
        before = len(store.task_steps(self.conn, task_id))
        spawn = mock.patch.object(runner, "spawn_agent",
                                  side_effect=AgentStartAttempted)
        exit_text = None
        with spawn as spawned:
            try:
                runner.cmd_run(task_id)
            except SystemExit as exc:
                exit_text = str(exc.code)
            except AgentStartAttempted:
                pass
        rows = store.task_steps(self.conn, task_id)[before:]
        return exit_text, spawned.called, rows

    def refused_by_breaker(self, rows) -> bool:
        return any(row["action"] == runner.WAVE_BREAKER_REFUSAL_ACTION
                   for row in rows)

    def status_lines(self) -> dict:
        out = capture(catalog.cmd_status)
        lines = {}
        for line in out.splitlines():
            head = line.strip().split(" ", 1)[0]
            if head:
                lines.setdefault(head, line)
        return lines


class ProjectWaveBreakerCountTest(ProjectWaveBreakerSandbox):
    """Счёт и алерт стоп-крана — по проекту задач, давших отказы."""

    def test_ac2_external_failures_over_threshold_raise_project_alert(self):
        """Отказы одного класса у задач внешнего проекта сверх порога заводят его алерт.

        Сценарий: случайное число (от `config.WAVE_BREAKER_TASKS` до него
        плюс трёх) разных задач внешнего проекта отказали одним случайным
        классом из `TRANSIENT_SYSTEM_CLASSES`; затем срабатывание решает
        `alerts.check_wave_breaker_failure`. Свойство: открыт ровно один
        алерт стоп-крана, его `target` — имя внешнего проекта; алерта с
        `target` артели нет.

        Ловит мутацию: счётчик `_wave_breaker_task_count` по-прежнему
        пропускает задачи с `target`, отличным от `config.DEFAULT_TARGET`,
        либо алерт заводится с `target=config.DEFAULT_TARGET` — тогда
        алерта нет вовсе или его `target` — артель, а не внешний проект.
        """
        for _ in range(3):
            failure_class = self.rng.choice(
                failure_classification.TRANSIENT_SYSTEM_CLASSES)
            count = config.WAVE_BREAKER_TASKS + self.rng.randrange(4)
            for _ in range(count):
                self.journal_failure(self.make_task(self.project), failure_class)

            alerts.check_wave_breaker_failure(self.conn, failure_class)

            label = failure_classification.CLASS_LABELS[failure_class]
            found = [row for row in self.breaker_alerts()
                     if label in row["message"]]
            self.assertEqual(
                [row["target"] for row in found], [self.project],
                f"{self.where()}: класс {failure_class}, задач {count} — "
                f"ждали один алерт стоп-крана с target проекта")
            self.assertNotIn(
                config.DEFAULT_TARGET,
                [row["target"] for row in self.breaker_alerts()],
                f"{self.where()}: отказы внешнего проекта завели алерт артели")

    def test_ac2_external_timeouts_over_threshold_raise_project_alert(self):
        """Таймауты шагов задач внешнего проекта сверх порога заводят его алерт.

        Сценарий: случайное число (не меньше `config.WAVE_BREAKER_TASKS`)
        разных задач внешнего проекта получили таймаут шага; срабатывание
        решает `alerts.check_wave_breaker_timeout`. Свойство: открыт алерт
        стоп-крана с `target` внешнего проекта и меткой класса «таймаут
        шага», алерта артели нет.

        Ловит мутацию: путь таймаута оставлен со сравнением
        `== config.DEFAULT_TARGET` при переводе пути классифицированных
        отказов — тогда таймауты внешнего проекта не заводят алерта.
        """
        count = config.WAVE_BREAKER_TASKS + self.rng.randrange(4)
        for _ in range(count):
            self.journal_timeout(self.make_task(self.project))

        alerts.check_wave_breaker_timeout(self.conn)

        found = [row for row in self.breaker_alerts()
                 if alerts.WAVE_BREAKER_TIMEOUT_LABEL in row["message"]]
        self.assertEqual([row["target"] for row in found], [self.project],
                         f"{self.where()}: задач {count}")

    def test_ac2_projects_are_counted_separately(self):
        """Задачи разных проектов в один счёт стоп-крана не складываются.

        Сценарий: у артели и у внешнего проекта отказали по случайному
        числу задач одним классом — у каждого меньше
        `config.WAVE_BREAKER_TASKS`, но в сумме не меньше порога. Свойство:
        алерта стоп-крана нет ни у одного проекта. Зелёный с рождения
        (сегодня внешние задачи не считаются вовсе) — держит перевод счёта.

        Ловит мутацию: из `_wave_breaker_task_count` фильтр по проекту
        удалён целиком (считаются задачи всех проектов вместе) — тогда
        сумма двух проектов поднимает алерт, хотя ни один порога не достиг.
        """
        threshold = config.WAVE_BREAKER_TASKS
        if threshold < 2:
            self.skipTest("порог меньше двух — сумма двух проектов ниже "
                          "порога каждого невозможна")
        failure_class = self.rng.choice(
            failure_classification.TRANSIENT_SYSTEM_CLASSES)
        own = self.rng.randrange(1, threshold)
        foreign = self.rng.randrange(max(1, threshold - own), threshold)
        for _ in range(own):
            self.journal_failure(self.make_task(config.DEFAULT_TARGET),
                                 failure_class)
        for _ in range(foreign):
            self.journal_failure(self.make_task(self.project), failure_class)

        alerts.check_wave_breaker_failure(self.conn, failure_class)

        self.assertEqual(
            self.breaker_alerts(), [],
            f"{self.where()}: артель {own}, внешний {foreign}, порог "
            f"{threshold} — сумма двух проектов завела алерт")

    def test_ac2_artel_failures_do_not_raise_external_alert(self):
        """Отказы задач артели сверх порога заводят алерт артели, не внешнего проекта.

        Сценарий: случайное число (не меньше `config.WAVE_BREAKER_TASKS`)
        задач артели отказали одним классом, у внешнего проекта задачи есть,
        но без отказов. Свойство: открытые алерты стоп-крана несут только
        `target` артели. Зелёный с рождения — держит, что перевод на проект
        не потерял артель и не разнёс её алерт на все проекты.

        Ловит мутацию: алерт заводится по проекту ПОСЛЕДНЕЙ задачи в
        `store.all_tasks` либо по каждому известному проекту — тогда
        появляется алерт с `target` внешнего проекта.
        """
        failure_class = self.rng.choice(
            failure_classification.TRANSIENT_SYSTEM_CLASSES)
        count = config.WAVE_BREAKER_TASKS + self.rng.randrange(3)
        for _ in range(count):
            self.journal_failure(self.make_task(config.DEFAULT_TARGET),
                                 failure_class)
        for _ in range(self.rng.randrange(1, 4)):
            self.make_task(self.project)

        alerts.check_wave_breaker_failure(self.conn, failure_class)

        self.assertEqual(
            {row["target"] for row in self.breaker_alerts()},
            {config.DEFAULT_TARGET},
            f"{self.where()}: задач артели {count}")


class ProjectWaveBreakerRunTest(ProjectWaveBreakerSandbox):
    """`run` отклоняется по алерту проекта задачи и только по нему."""

    def test_ac2_run_of_external_task_refused_while_its_alert_open(self):
        """Открытый алерт внешнего проекта отклоняет `run` его задачи до старта шага.

        Сценарий: алерт стоп-крана с `target` внешнего проекта открыт;
        `runner.cmd_run` зовётся для случайной из нескольких задач этого
        проекта в агентском состоянии. Свойство: вызов выходит отказом,
        текст которого называет стоп-кран, журнал задачи несёт
        `runner.WAVE_BREAKER_REFUSAL_ACTION`, запуск агента не запрошен.

        Ловит мутацию: в `_refuse_before_start` осталось условие
        `target == config.DEFAULT_TARGET` или `wave_breaker_alerts_open`
        отбирает только алерты артели — тогда задача внешнего проекта идёт
        дальше к старту агента без записи отказа стоп-крана.
        """
        self.open_breaker_alert(self.project)
        tasks = [self.make_task(self.project, RUN_STATE)
                 for _ in range(self.rng.randrange(1, 4))]
        task_id = self.rng.choice(tasks)

        exit_text, spawned, rows = self.run_step(task_id)

        self.assertTrue(self.refused_by_breaker(rows),
                        f"{self.where()}: задача {task_id} — нет записи "
                        f"отказа стоп-крана, выход: {exit_text!r}")
        self.assertIn("стоп-кран", (exit_text or "").lower(),
                      f"{self.where()}: задача {task_id}")
        self.assertFalse(spawned, f"{self.where()}: агент запрошен")

    def test_ac2_external_alert_does_not_block_artel_task(self):
        """Алерт внешнего проекта не отклоняет `run` задачи артели.

        Сценарий: открыт алерт стоп-крана только с `target` внешнего
        проекта; `runner.cmd_run` зовётся для задачи артели. Свойство: в
        журнале задачи нет записи отказа стоп-крана, текст выхода (если
        шаг дальше отказал по иной причине песочницы) стоп-крана не
        называет. Зелёный с рождения — держит, что перевод фильтра на
        проект не стал блокировать по алерту любого проекта.

        Ловит мутацию: `wave_breaker_alerts_open` после удаления
        сравнения с `config.DEFAULT_TARGET` не фильтрует по проекту вовсе
        — тогда алерт внешнего проекта отклоняет и задачу артели.
        """
        self.open_breaker_alert(self.project)
        task_id = self.make_task(config.DEFAULT_TARGET, RUN_STATE)

        exit_text, _spawned, rows = self.run_step(task_id)

        self.assertFalse(self.refused_by_breaker(rows),
                         f"{self.where()}: задача артели отклонена по "
                         f"алерту внешнего проекта: {exit_text!r}")
        self.assertNotIn("стоп-кран", (exit_text or "").lower(),
                         f"{self.where()}")

    def test_ac2_artel_alert_does_not_block_external_task(self):
        """Алерт артели не отклоняет `run` задачи внешнего проекта.

        Сценарий: открыт алерт стоп-крана только с `target` артели;
        `runner.cmd_run` зовётся для задачи внешнего проекта. Свойство: в
        журнале задачи нет записи отказа стоп-крана, текст выхода его не
        называет. Зелёный с рождения (сегодня внешние задачи стоп-кран
        не проверяют вовсе) — держит перевод проверки на проект задачи.

        Ловит мутацию: в `_refuse_before_start` условие на `target`
        задачи удалено, а отбор алертов остался по артели (или не по
        проекту) — тогда алерт артели отклоняет задачу внешнего проекта.
        """
        self.open_breaker_alert(config.DEFAULT_TARGET)
        task_id = self.make_task(self.project, RUN_STATE)

        exit_text, _spawned, rows = self.run_step(task_id)

        self.assertFalse(self.refused_by_breaker(rows),
                         f"{self.where()}: задача внешнего проекта "
                         f"отклонена по алерту артели: {exit_text!r}")
        self.assertNotIn("стоп-кран", (exit_text or "").lower(),
                         f"{self.where()}")


class ProjectWaveBreakerStatusTest(ProjectWaveBreakerSandbox):
    """`status` помечает задачи только того проекта, чей алерт открыт."""

    def seed_tasks(self) -> tuple:
        own = [self.make_task(config.DEFAULT_TARGET, self.rng.choice(
            (NON_AGENT_STATE, RUN_STATE))) for _ in range(self.rng.randrange(1, 4))]
        foreign = [self.make_task(self.project, self.rng.choice(
            (NON_AGENT_STATE, RUN_STATE))) for _ in range(self.rng.randrange(1, 4))]
        return own, foreign

    def marked(self, line: str) -> bool:
        return "стоп-кран" in line.lower()

    def test_ac2_status_marks_external_tasks_not_artel(self):
        """Алерт внешнего проекта помечает в `status` его задачи, но не задачи артели.

        Сценарий: по случайному числу задач у артели и у внешнего проекта,
        открыт алерт стоп-крана с `target` внешнего проекта; печатается
        `catalog.cmd_status`. Свойство: строка каждой задачи внешнего
        проекта несёт пометку стоп-крана, строка ни одной задачи артели —
        нет.

        Ловит мутацию: `_wave_breaker_suffix` по-прежнему возвращает пусто
        для `target`, отличного от `config.DEFAULT_TARGET`, либо пометка
        ставится по любому открытому алерту без сверки его проекта с
        проектом задачи — тогда задачи внешнего проекта не помечены или
        помечены и задачи артели.
        """
        own, foreign = self.seed_tasks()
        self.open_breaker_alert(self.project)

        lines = self.status_lines()

        for task_id in foreign:
            self.assertTrue(self.marked(lines[task_id]),
                            f"{self.where()}: {lines[task_id]!r}")
        for task_id in own:
            self.assertFalse(self.marked(lines[task_id]),
                             f"{self.where()}: {lines[task_id]!r}")

    def test_ac2_status_marks_artel_tasks_not_external(self):
        """Алерт артели помечает в `status` задачи артели, но не внешнего проекта.

        Сценарий: тот же набор задач, открыт алерт стоп-крана только с
        `target` артели. Свойство: строки задач артели помечены, строки
        задач внешнего проекта — нет. Зелёный с рождения — держит, что
        перевод на проект не стал помечать всех по любому алерту.

        Ловит мутацию: пометка ставится всем задачам, если открыт хоть
        один алерт стоп-крана любого проекта — тогда помечены и задачи
        внешнего проекта.
        """
        own, foreign = self.seed_tasks()
        self.open_breaker_alert(config.DEFAULT_TARGET)

        lines = self.status_lines()

        for task_id in own:
            self.assertTrue(self.marked(lines[task_id]),
                            f"{self.where()}: {lines[task_id]!r}")
        for task_id in foreign:
            self.assertFalse(self.marked(lines[task_id]),
                             f"{self.where()}: {lines[task_id]!r}")


if __name__ == "__main__":
    unittest.main()
