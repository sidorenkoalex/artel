"""Юнит-тесты `orchestrator.runner.wave_breaker_alerts_open` — стоп-кран
волны, часть 2 (tasks/01M1THKRK8HPXA7Y2SRB0RFTN2/SPEC.md, требования 1,
3-5).

Сквозной путь «открытый алерт отказывает `run`/`auto`» несёт залоченная
приёмочная планка задачи (`tasks/01M1THKRK8HPXA7Y2SRB0RFTN2/
acceptance_tests/`); здесь — сам геттер в изоляции (тот же приём, что
`tests/test_alerts_wave_breaker.py` уже применил к части 1): фильтр по
`target`/`source`/`kind`, дедуп по нескольким открытым алертам сразу,
неучёт подтверждённых.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, config, runner, store  # noqa: E402
from tests.sandbox import SchemaTmpRootTest  # noqa: E402

OTHER_TARGET = "sled"


class WaveBreakerAlertsOpenTest(SchemaTmpRootTest):

    def raise_wave_breaker(self, target: str | None = None,
                           message: str = "стоп-кран волны: класс 1б у 3 "
                                          "задач за 15 минут") -> None:
        conn = store.db()
        target = config.DEFAULT_TARGET if target is None else target
        opened = alerts.raise_alert(conn, target, "incident", "wave_breaker",
                                    message)
        assert opened, "фикстура не смогла завести алерт"

    def test_no_alerts_returns_empty_list(self):
        """Ловит мутацию: функция, возвращающая непустой список без
        единой строки в БД, сломала бы любую задачу target self сразу
        после `init` — никто не смог бы стартовать первый же шаг."""
        self.assertEqual(runner.wave_breaker_alerts_open(store.db()), [])

    def test_open_self_wave_breaker_incident_is_returned(self):
        self.raise_wave_breaker()

        found = runner.wave_breaker_alerts_open(store.db())

        self.assertEqual(len(found), 1)
        self.assertIn("стоп-кран", found[0]["message"])

    def test_foreign_target_alert_is_not_returned(self):
        """Ловит мутацию: если фильтр по `target` уберут, алерт другого
        target ошибочно заблокировал бы self."""
        self.raise_wave_breaker(target=OTHER_TARGET)

        self.assertEqual(runner.wave_breaker_alerts_open(store.db()), [])

    def test_other_incident_source_is_not_returned(self):
        """Ловит мутацию: если фильтр по `source` уберут, ЛЮБОЙ
        `kind=incident` (сироты веток, recovery) ошибочно блокировал бы
        `run`/`auto`, а не только стоп-кран волны."""
        conn = store.db()
        alerts.raise_alert(conn, config.DEFAULT_TARGET, "incident",
                           "orphan-branches", "осиротевшая ветка найдена")

        self.assertEqual(runner.wave_breaker_alerts_open(conn), [])

    def test_other_kind_same_target_is_not_returned(self):
        """`kind=attention`/`warning` того же target — не стоп-кран,
        функция обязана их игнорировать даже при совпадающем target."""
        conn = store.db()
        alerts.raise_attention_alert(conn, "T001", "auto остановлен")

        self.assertEqual(runner.wave_breaker_alerts_open(conn), [])

    def test_acked_alert_is_not_returned(self):
        """Ловит мутацию: если функция читала бы алерты без фильтра
        `ack_ts IS NULL` (например, отдельным SQL мимо `alerts.
        open_alerts`), `alert-ack` не снимал бы блокировку вовсе."""
        self.raise_wave_breaker()
        conn = store.db()
        alert_id = runner.wave_breaker_alerts_open(conn)[0]["id"]

        error = alerts.ack(conn, alert_id, "operator", "")

        self.assertIsNone(error)
        self.assertEqual(runner.wave_breaker_alerts_open(conn), [])

    def test_two_distinct_classes_are_both_returned(self):
        """Два разных класса стоп-крана (1б и таймаут) открыты
        одновременно — оба возвращаются, не только первый найденный.

        Ловит мутацию: если функция возвращала бы одну строку вместо
        списка, `doctor`/`status` пропустили бы второй активный класс."""
        conn = store.db()
        self.raise_wave_breaker(
            message="стоп-кран волны: класс 1б у 3 задач за 15 минут")
        self.raise_wave_breaker(
            message="стоп-кран волны: таймаут шага у 3 задач за 15 минут")

        found = runner.wave_breaker_alerts_open(conn)

        self.assertEqual(len(found), 2)


if __name__ == "__main__":
    unittest.main()
