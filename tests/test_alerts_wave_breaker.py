"""Юнит-тесты стоп-крана волны, часть 1 (tasks/01M1THKPNZ11DBZAQDMJ33EMJR/
SPEC.md): `alerts.check_wave_breaker_failure`/`check_wave_breaker_timeout`
и их общий счётчик `_wave_breaker_task_count` — в изоляции от журнала
попытки агента и `runner.cmd_run`.

Сквозные сценарии через реальный фейковый агент (обе точки вызова
`orchestrator/runner.py`, полный путь `_record_failure_classification`/
таймаута) несёт залоченная приёмочная планка задачи
(`tasks/01M1THKPNZ11DBZAQDMJ33EMJR/acceptance_tests/`, `_sandbox.
WaveBreakerSandbox`) — здесь только сами новые функции `alerts.py`,
журнал `steps` заполняется напрямую (тот же приём, что `tests/
test_doctor.py`, вставка `INSERT INTO steps` с явным `ts`), без обвязки
`cmd_run`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, config, failure_classification, store  # noqa: E402
from tests.sandbox import TmpRootTest, _ts_ago  # noqa: E402

FOREIGN_TARGET = "внешний-проект"


class WaveBreakerTestBase(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())

    def make_task(self, task_id: str, target: str | None = None) -> None:
        store.insert_task(store.db(), task_id, task_id, "in_dev",
                          f"task/{task_id}", target or config.DEFAULT_TARGET,
                          10.0)

    def log_failure(self, task_id: str, failure_class: str,
                    seconds_ago: float = 0) -> None:
        conn = store.db()
        label = failure_classification.CLASS_LABELS[failure_class]
        detail = f"попытка 1/3: {label}; текст: ..."
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (task_id, store.task_target(conn, task_id), _ts_ago(seconds_ago),
             "developer", alerts.WAVE_BREAKER_FAILURE_ACTION, detail))
        conn.commit()

    def log_timeout(self, task_id: str, seconds_ago: float = 0) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (task_id, store.task_target(conn, task_id), _ts_ago(seconds_ago),
             "developer", alerts.WAVE_BREAKER_TIMEOUT_ACTION, "30 мин, ..."))
        conn.commit()

    def wave_breaker_alerts(self) -> list:
        return [row for row in alerts.open_alerts(store.db(), "incident")
                if row["source"] == alerts.WAVE_BREAKER_SOURCE]


class CheckWaveBreakerFailureTest(WaveBreakerTestBase):

    def test_three_distinct_tasks_reach_threshold(self):
        """Три разные задачи класса 1б — алерт заводится, называет класс
        и число задач.

        Ловит мутацию: `>=` заменено на `>`, либо класс/число задач не
        подставлены в текст сообщения — тогда алерт не откроется на ровно
        трёх задачах, либо в тексте не будет «1б» или «3»."""
        for i in range(3):
            task = f"T00{i}"
            self.make_task(task)
            self.log_failure(task, "1b")

        opened = alerts.check_wave_breaker_failure(store.db(), "1b")

        self.assertTrue(opened)
        found = self.wave_breaker_alerts()
        self.assertEqual(len(found), 1)
        self.assertIn("1б", found[0]["message"])
        self.assertIn("3", found[0]["message"])

    def test_two_distinct_tasks_below_threshold_no_alert(self):
        """Две разные задачи — порог `config.WAVE_BREAKER_TASKS=3` не
        достигнут, алерт не заводится.

        Ловит мутацию: сравнение `>=` заменено на `>` или порог занижен —
        тогда алерт появился бы уже на второй задаче."""
        for i in range(2):
            task = f"T00{i}"
            self.make_task(task)
            self.log_failure(task, "1b")

        opened = alerts.check_wave_breaker_failure(store.db(), "1b")

        self.assertFalse(opened)
        self.assertEqual(self.wave_breaker_alerts(), [])

    def test_repeated_failures_of_the_same_task_count_once(self):
        """Три события ОДНОГО класса у ОДНОЙ задачи — не набирают порог
        (считаются задачи, не строки журнала).

        Ловит мутацию: подсчёт числа строк журнала вместо `len(set(task_id))`
        — тогда одна задача с тремя событиями подняла бы алерт здесь."""
        task = "T001"
        self.make_task(task)
        for _ in range(3):
            self.log_failure(task, "1b")

        opened = alerts.check_wave_breaker_failure(store.db(), "1b")

        self.assertFalse(opened)
        self.assertEqual(self.wave_breaker_alerts(), [])

    def test_different_classes_are_not_summed(self):
        """По одной задаче на класс 1а/1б/системный кандидат — ни один
        класс отдельно не набирает порог 3.

        Ловит мутацию: счётчик ключуется только по (target, окно), без
        учёта класса — тогда суммарные три отказа подняли бы алерт."""
        classes = ("1a", "1b", "system_candidate")
        for i, cls in enumerate(classes):
            task = f"T00{i}"
            self.make_task(task)
            self.log_failure(task, cls)

        for cls in classes:
            with self.subTest(cls=cls):
                opened = alerts.check_wave_breaker_failure(store.db(), cls)
                self.assertFalse(opened)
        self.assertEqual(self.wave_breaker_alerts(), [])

    def test_events_outside_the_window_are_not_counted(self):
        """Отказ за пределами `config.WAVE_BREAKER_WINDOW_SEC` — не в счёте.

        Ловит мутацию: окно не сверяется вовсе (учитываются все события
        когда-либо) — тогда старый отказ добавился бы к текущим двум и
        ошибочно поднял алерт."""
        stale = "T-STALE"
        self.make_task(stale)
        self.log_failure(stale, "1b",
                         seconds_ago=config.WAVE_BREAKER_WINDOW_SEC + 60)
        for i in range(2):
            task = f"T00{i}"
            self.make_task(task)
            self.log_failure(task, "1b")

        opened = alerts.check_wave_breaker_failure(store.db(), "1b")

        self.assertFalse(opened)

    def test_foreign_target_is_not_counted(self):
        """Задачи внешнего target не учитываются счётчиком стоп-крана self.

        Ловит мутацию: фильтр по `target=config.DEFAULT_TARGET` убран —
        тогда три задачи внешнего target подняли бы алерт self."""
        for i in range(3):
            task = f"T00{i}"
            self.make_task(task, target=FOREIGN_TARGET)
            self.log_failure(task, "1b")

        opened = alerts.check_wave_breaker_failure(store.db(), "1b")

        self.assertFalse(opened)
        self.assertEqual(self.wave_breaker_alerts(), [])

    def test_non_transient_class_is_ignored(self):
        """«Обрыв потока»/session_limit не входят в связку
        `TRANSIENT_SYSTEM_CLASSES` — вызов с ними не считает и не заводит
        алерт, даже если журнал уже несёт три задачи такого класса.

        Ловит мутацию: фильтр по `TRANSIENT_SYSTEM_CLASSES` снят или
        `stream_broken` ошибочно включён в связку — тогда три задачи
        этого класса подняли бы алерт наравне с 1а/1б."""
        for i in range(3):
            task = f"T00{i}"
            self.make_task(task)
            self.log_failure(task, "stream_broken")

        opened = alerts.check_wave_breaker_failure(store.db(), "stream_broken")

        self.assertFalse(opened)
        self.assertEqual(self.wave_breaker_alerts(), [])

    def test_none_failure_class_is_ignored(self):
        """`failure_class=None` (текст попытки не распознан классификатором)
        — вызов не падает и не заводит алерт.

        Ловит мутацию: убрана ранняя проверка на `None` — тогда обращение
        к `CLASS_LABELS[None]`/`TRANSIENT_SYSTEM_CLASSES` упадёт
        исключением либо ошибочно откроет алерт."""
        opened = alerts.check_wave_breaker_failure(store.db(), None)

        self.assertFalse(opened)

    def test_reaching_the_threshold_again_does_not_duplicate_the_alert(self):
        """Открытый алерт того же класса остаётся один при повторном
        достижении порога (дедуп по префиксу сообщения, не по тексту).

        Ловит мутацию: дедуп по буквальному `raise_alert(message=...)` —
        второе срабатывание называет другое число задач (6, не 3), точное
        совпадение не сработает, и откроется второй алерт."""
        for i in range(3):
            task = f"T00{i}"
            self.make_task(task)
            self.log_failure(task, "1b")
        alerts.check_wave_breaker_failure(store.db(), "1b")
        first = self.wave_breaker_alerts()
        self.assertEqual(len(first), 1)

        for i in range(3, 6):
            task = f"T00{i}"
            self.make_task(task)
            self.log_failure(task, "1b")
        alerts.check_wave_breaker_failure(store.db(), "1b")
        second = self.wave_breaker_alerts()

        self.assertEqual(len(second), 1)
        self.assertEqual(first[0]["id"], second[0]["id"])

    def test_message_names_the_configured_window_in_minutes(self):
        """Текст алерта называет окно в минутах, посчитанных из
        `config.WAVE_BREAKER_WINDOW_SEC`, не зашитое число.

        Ловит мутацию: минуты в сообщении зашиты константой (например,
        15) вместо вычисления из `config.WAVE_BREAKER_WINDOW_SEC` —
        тогда при окне 120 сек (2 минуты) в тексте осталось бы «15»,
        не «2»."""
        from unittest import mock
        with mock.patch.object(config, "WAVE_BREAKER_WINDOW_SEC", 120):
            for i in range(3):
                task = f"T00{i}"
                self.make_task(task)
                self.log_failure(task, "1b")
            alerts.check_wave_breaker_failure(store.db(), "1b")

        found = self.wave_breaker_alerts()
        self.assertEqual(len(found), 1)
        self.assertIn("2", found[0]["message"])


class CheckWaveBreakerTimeoutTest(WaveBreakerTestBase):

    def test_three_distinct_timeouts_raise_incident_naming_timeout(self):
        """Три разные задачи с таймаутом шага — алерт заводится, сообщение
        называет класс «таймаут».

        Ловит мутацию: класс «таймаут шага» не выделен отдельно от
        `check_wave_breaker_failure`, либо текст сообщения не называет
        таймаут — тогда `assertIn("таймаут", ...)` не пройдёт, либо алерт
        не откроется на трёх задачах."""
        for i in range(3):
            task = f"T00{i}"
            self.make_task(task)
            self.log_timeout(task)

        opened = alerts.check_wave_breaker_timeout(store.db())

        self.assertTrue(opened)
        found = self.wave_breaker_alerts()
        self.assertEqual(len(found), 1)
        self.assertIn("таймаут", found[0]["message"].lower())

    def test_two_distinct_timeouts_below_threshold_no_alert(self):
        """Две разные задачи с таймаутом — порог не достигнут, алерт не
        заводится.

        Ловит мутацию: порог занижен или сравнение `>=` заменено на `>`
        — тогда алерт открылся бы уже на двух задачах."""
        for i in range(2):
            task = f"T00{i}"
            self.make_task(task)
            self.log_timeout(task)

        opened = alerts.check_wave_breaker_timeout(store.db())

        self.assertFalse(opened)

    def test_timeout_is_not_summed_with_failure_classes(self):
        """Один таймаут плюс один отказ 1б у другой задачи — ни счётчик
        таймаута, ни счётчик 1б не достигают порога сами по себе.

        Ловит мутацию: счётчик таймаута и счётчик отказа делят один и тот
        же ключ/множество задач — тогда таймаут и отказ 1б суммировались
        бы в общий счёт и один из вызовов ошибочно вернул бы True."""
        timeout_task = "T-TIMEOUT"
        self.make_task(timeout_task)
        self.log_timeout(timeout_task)
        failure_task = "T-1B"
        self.make_task(failure_task)
        self.log_failure(failure_task, "1b")

        self.assertFalse(alerts.check_wave_breaker_timeout(store.db()))
        self.assertFalse(alerts.check_wave_breaker_failure(store.db(), "1b"))


if __name__ == "__main__":
    unittest.main()
