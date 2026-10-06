"""Стоп-кран волны — механика пульта: считает и блокирует задачи всех проектов.

Группа: долгоживущий
Красен до реализации: счёт волны (`alerts`) пропускает задачи не артели, отказ старта шага (`runner`) и пометка `status` (`catalog`) действуют только на задачи артели.

SPEC задачи, AC-3 (строки 7-11 таблицы требования 1):
в порог `config.WAVE_BREAKER_TASKS` идут задачи всех проектов; пока алерт
волны открыт, `run` задачи внешнего проекта отказывает записью
`runner.WAVE_BREAKER_REFUSAL_ACTION`, а `status` помечает её «СТОП-КРАН
ВОЛНЫ». Отказы классов окружения пульта пишутся в журнал задач тем же
действием, что пишет шаг (`alerts.WAVE_BREAKER_FAILURE_ACTION` с меткой
класса в тексте) — до проверки `alerts.check_wave_breaker_failure`.

Состав проектов, класс отказа и id задач порождаются модулем `random` при
каждом запуске; зерно печатается и входит в текст провала.
"""
import io
import random
import string
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from orchestrator import (alerts, catalog, config, failure_classification,
                          runner, store)
from tests.sandbox import InitializedTmpRootTest, capture, declare_target

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class WaveBreakerProjectsSandbox(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.ext = "proekt" + "".join(self.rng.choices(string.ascii_lowercase, k=5))
        declare_target(self.ext)
        self.failure_class = self.rng.choice(
            list(failure_classification.TRANSIENT_SYSTEM_CLASSES))

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def new_task(self, target: str, state: str = "in_dev") -> str:
        task_id = "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))
        store.insert_task(store.db(), task_id, f"Задача {task_id[-6:]}", state,
                          f"task/{task_id.lower()}-volna", target,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def log_failure(self, task_id: str) -> None:
        label = failure_classification.CLASS_LABELS[self.failure_class]
        store.journal(store.db(), task_id, "developer",
                      alerts.WAVE_BREAKER_FAILURE_ACTION,
                      f"попытка 1/3: {label}; текст: отказ окружения")

    def wave_alerts(self) -> list:
        return [r for r in alerts.open_alerts(store.db(), "incident")
                if r["source"] == alerts.WAVE_BREAKER_SOURCE]

    def mixed_targets(self, count: int) -> list:
        """`count` проектов задач: хотя бы одна задача внешнего проекта и,
        если задач больше одной, хотя бы одна — артели."""
        targets = [self.rng.choice([config.DEFAULT_TARGET, self.ext])
                   for _ in range(count)]
        targets[0] = self.ext
        if count > 1:
            targets[1] = config.DEFAULT_TARGET
        self.rng.shuffle(targets)
        return targets


class WaveBreakerCountTest(WaveBreakerProjectsSandbox):

    def test_ac3_threshold_counts_tasks_of_all_projects(self):
        """Порог стоп-крана набирают отказы задач любых проектов.

        Сценарий: ровно `config.WAVE_BREAKER_TASKS` задач (среди них —
        задачи внешнего проекта, иногда только они) получили отказ одного
        класса окружения пульта. `alerts.check_wave_breaker_failure`
        открывает алерт волны. Отдельно: только задачи внешнего проекта в
        числе порога — тоже открывает.

        Ловит мутацию: в счёт волны по-прежнему идут только задачи артели —
        отказы задач внешнего проекта не учтены, порог не набран, алерта
        нет.
        """
        only_ext = self.rng.random() < 0.5
        targets = ([self.ext] * config.WAVE_BREAKER_TASKS if only_ext
                   else self.mixed_targets(config.WAVE_BREAKER_TASKS))
        for target in targets:
            self.log_failure(self.new_task(target))
        opened = alerts.check_wave_breaker_failure(store.db(), self.failure_class)
        self.assertTrue(opened, self.msg(
            f"порог из задач проектов {targets} не открыл алерт волны"))
        self.assertEqual(len(self.wave_alerts()), 1, self.msg(
            f"алертов волны: {self.wave_alerts()}"))

    def test_ac3_below_threshold_across_projects_does_not_fire(self):
        """Отказы задач разных проектов ниже порога алерта не открывают.

        Сценарий: `config.WAVE_BREAKER_TASKS - 1` разных задач (артели и
        внешнего проекта вперемешку) получили отказ класса окружения; одна
        из них — ещё дважды. Алерта волны нет.

        Ловит мутацию: счёт волны после снятия развилки считает записи
        отказов, а не разные задачи (или задачу дважды — по проекту и по
        id) — порог «набирается» меньшим числом задач.
        """
        count = config.WAVE_BREAKER_TASKS - 1
        tasks = [self.new_task(t) for t in self.mixed_targets(max(count, 1))][:count]
        for task_id in tasks:
            self.log_failure(task_id)
        if tasks:
            again = self.rng.choice(tasks)
            self.log_failure(again)
            self.log_failure(again)
        opened = alerts.check_wave_breaker_failure(store.db(), self.failure_class)
        self.assertFalse(opened, self.msg("алерт открыт ниже порога"))
        self.assertEqual(self.wave_alerts(), [], self.msg(str(self.wave_alerts())))


class WaveBreakerBlocksExternalTest(WaveBreakerProjectsSandbox):

    def open_wave_from_external_failures(self) -> None:
        for _ in range(config.WAVE_BREAKER_TASKS):
            self.log_failure(self.new_task(self.ext))
        alerts.check_wave_breaker_failure(store.db(), self.failure_class)

    def test_ac3_run_of_external_task_refused_while_alert_open(self):
        """Пока алерт волны открыт, `run` задачи внешнего проекта отказывает записью `runner.WAVE_BREAKER_REFUSAL_ACTION`.

        Сценарий: алерт волны открыт (через порог отказов); задача внешнего
        проекта в случайном агентском состоянии (`tests_writing` или
        `review`). `run` завершается отказом, журнал задачи несёт
        `runner.WAVE_BREAKER_REFUSAL_ACTION`, агент не запускается.

        Ловит мутацию: отказ старта шага по открытому алерту оставлен
        только задачам артели — `run` внешней задачи идёт дальше к запуску
        агента, записи отказа волны нет.
        """
        self.open_wave_from_external_failures()
        if not runner.wave_breaker_alerts_open(store.db()):
            # Алерт не открылся счётом (развилка счёта) — открыть его так, как
            # его заводит пульт: на проект пульта, источником стоп-крана.
            alerts.raise_alert(store.db(), config.DEFAULT_TARGET, "incident",
                               alerts.WAVE_BREAKER_SOURCE,
                               "стоп-кран волны: сценарий теста")
        state = self.rng.choice(["tests_writing", "review"])
        task_id = self.new_task(self.ext, state=state)
        spawn = mock.Mock(side_effect=AssertionError("агент запущен"))
        buf = io.StringIO()
        with mock.patch.object(runner, "spawn_agent", spawn), \
                redirect_stdout(buf), redirect_stderr(buf):
            try:
                runner.cmd_run(task_id)
            except (SystemExit, AssertionError, OSError, RuntimeError) as exc:
                buf.write(f"\n{exc}")
        actions = [r["action"] for r in store.task_steps(store.db(), task_id)]
        self.assertIn(runner.WAVE_BREAKER_REFUSAL_ACTION, actions, self.msg(
            f"run {task_id} ({state}) без отказа волны; журнал {actions}; "
            f"вывод:\n{buf.getvalue()}"))
        spawn.assert_not_called()

    def test_ac3_status_marks_external_task_while_alert_open(self):
        """Пока алерт волны открыт, `status` помечает задачу внешнего проекта «СТОП-КРАН ВОЛНЫ».

        Сценарий: алерт волны открыт отказами задач внешнего проекта;
        строки `status` задачи внешнего проекта и задачи артели несут
        «СТОП-КРАН ВОЛНЫ». После снятия алерта (`alerts.ack`) пометки
        нет.

        Ловит мутацию: пометка стоп-крана в `status` оставлена только
        задачам артели — строка внешней задачи без пометки; либо открытые
        алерты волны отбираются по проекту артели и после правки дедупа не
        находятся — пометки нет ни у кого.
        """
        self.open_wave_from_external_failures()
        ext_task = self.new_task(self.ext, state="review")
        artel_task = self.new_task(config.DEFAULT_TARGET, state="review")
        out = capture(catalog.cmd_status)
        for task_id in (ext_task, artel_task):
            line = next((ln for ln in out.splitlines() if ln.startswith(task_id)), "")
            self.assertIn("СТОП-КРАН ВОЛНЫ", line, self.msg(
                f"строка {task_id} без пометки стоп-крана:\n{out}"))
        for row in self.wave_alerts():
            alerts.ack(store.db(), row["id"], "operator", "снято сценарием")
        out = capture(catalog.cmd_status)
        line = next(ln for ln in out.splitlines() if ln.startswith(ext_task))
        self.assertNotIn("СТОП-КРАН ВОЛНЫ", line, self.msg(line))


if __name__ == "__main__":
    import unittest
    unittest.main()
