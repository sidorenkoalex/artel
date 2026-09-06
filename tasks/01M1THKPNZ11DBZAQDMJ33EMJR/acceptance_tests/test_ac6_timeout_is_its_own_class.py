"""Приёмочный тест AC-6 — tasks/01M1THKPNZ11DBZAQDMJ33EMJR/SPEC.md.

AC-6. Таймаут шага (журнальная запись «agent run TIMEOUT») учитывается
отдельным классом наравне с классами `TRANSIENT_SYSTEM_CLASSES`.

Красен до реализации: ДА — счётчика/алерта стоп-крана волны в коде нет
вовсе, «agent run TIMEOUT» журналируется (`orchestrator/runner.py:855`)
но ничем не агрегируется.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WaveBreakerSandbox  # noqa: E402


class Ac6TimeoutIsItsOwnClassTest(WaveBreakerSandbox):

    def test_ac6_three_distinct_timeouts_raise_incident_alert(self):
        """Три разные задачи подряд обрываются таймаутом шага (без
        ретрая, тем же приёмом, что и существующий тест `tests/
        test_agent_failure.py::CmdRunFailureTest.
        test_timeout_is_not_retried`) — «agent run TIMEOUT» учитывается
        как самостоятельный класс, наравне с 1а/1б/«системный кандидат»:
        три разные задачи с этим классом обязаны поднять алерт стоп-крана
        волны, называющий таймаут.

        Ловит мутацию: таймаут шага не подключён к счётчику вовсе (только
        классы `TRANSIENT_SYSTEM_CLASSES` из `failure_classification.py`
        учтены, а вторая точка вызова требования 3 — журнал «agent run
        TIMEOUT» — забыта) — тогда алерт не появится вовсе, несмотря на
        три однотипных отказа.
        """
        for title in ("Первая", "Вторая", "Третья"):
            task = self.new_task(title)
            self.fail_timeout(task)

        found = self.wave_breaker_alerts()

        self.assertEqual(
            len(found), 1,
            f"три разные задачи, оборвавшиеся таймаутом шага, обязаны "
            f"поднять ровно один алерт стоп-крана волны; открытые "
            f"incident-алерты: "
            f"{[r['message'] for r in self.open_incident_alerts()]}")
        self.assertIn(
            "таймаут", found[0]["message"].lower(),
            f"сообщение обязано называть класс «таймаут шага» (SPEC "
            f"требование 2); сообщение: {found[0]['message']!r}")


if __name__ == "__main__":
    unittest.main()
