"""Приёмочные тесты T082 — AC-3, AC-12.

Источник — tasks/T082/SPEC.md, «Критерии приёмки».

AC-3. Попытка шага с текстом, содержащим «Connection lost mid-response»
(без учёта регистра), классифицируется как класс «обрыв потока».

AC-12. Неудачная попытка класса «обрыв потока» (AC-3) открывает алерт
`spend.unknown_cost`, если он ещё не открыт для этой попытки.

Требование 5 SPEC формулирует это явно как проверку НЕЗАВИСИМОСТИ от
пути учёта стоимости («независимо от того, каким путём учёта стоимости
попытки она сейчас обрабатывается»), поэтому AC-3/AC-12 тестируются
вместе, двумя разными путями `orchestrator/spend.py`:

1. `test_ac3_no_final_result_event_opens_alert` — финального
   события потока НЕТ вовсе (ни usage, ни таймаута/обрыва пайпа
   Python-уровня, tasks/T040) — сегодня это тихий путь
   `spend.charge_step(cost=None)` («agent cost UNKNOWN», без алерта):
   именно эта комбинация («Connection lost mid-response» в тексте
   попытки, финального `result` не пришло, но и Python-исключения
   чтения пайпа тоже не было — CLI сам закрыл поток корректно с точки
   зрения ОС) — буквально фактура 27.08 (SPEC, «Контекст»: «стоимость
   попытки осталась неизвестной»).
2. `test_ac12_known_cost_path_also_opens_alert` — финальное
   событие ЕСТЬ (стоимость известна, `spend.charge_step(cost=...)`) —
   сегодня этот путь тоже не заводит алерт вовсе, ни при каких текстах
   ошибки. Требование 5 требует алерт и здесь: демонстрирует, что
   классификация «обрыв потока» не завязана на то, какой из путей
   учёта стоимости сработал.

Обе фактуры используют дословную сигнатуру инцидента T043
(`tasks/T082/ANSWER-1.md`): «API Error: Connection lost mid-response.
The response above may be incomplete.»

Красен до реализации: `orchestrator/spend.py` заводит
`spend.unknown_cost` (kind=incident) только внутри
`charge_missing_result` и только при `saw_usage_event=False`
(`orchestrator/spend.py:143-183`) — ни один из двух сценариев этого
файла не проходит через эту функцию (нет ни таймаута, ни
Python-исключения чтения пайпа), поэтому оба теста провалятся по
пустому списку открытых `incident`-алертов (проверено прогоном на
немодифицированном коде при подготовке файла).
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import RunnerSandbox  # noqa: E402

from orchestrator import config  # noqa: E402

# Дословная сигнатура подслучая обрыва потока (ANSWER-1, инцидент T043).
STREAM_BROKEN_LINE = ("API Error: Connection lost mid-response. The "
                     "response above may be incomplete.\n")


class StreamBrokenAlertTest(RunnerSandbox):

    def unknown_cost_alerts(self) -> list:
        return [a for a in self.open_alerts(kind="incident")
               if a["source"] == "spend.unknown_cost"]

    def test_ac3_no_final_result_event_opens_alert(self):
        # Ни финального `type: result`, ни таймаута, ни исключения
        # чтения пайпа: `FakeProc.wait()` сразу отдаёт rc, поток строк
        # исчерпывается штатным `StopIteration` — тот же вырожденный
        # случай, что уже кодирует `spend.charge_step(cost=None)`.
        # Все `AGENT_ATTEMPTS` попыток — одной и той же сигнатурой:
        # `runner.time.sleep` в песочнице не спит, поэтому ретраи не
        # замедляют тест, а алерт-требование 5 не завязано на номер
        # попытки, на которой он открылся.
        out = self.run_agent(*[
            (1, ["агент начал отвечать...\n", STREAM_BROKEN_LINE]),
        ] * config.AGENT_ATTEMPTS)

        alerts = self.unknown_cost_alerts()
        self.assertTrue(
            alerts,
            f"AC-3/AC-12: попытка с «Connection lost mid-response» и без "
            f"финального события потока обязана классифицироваться как "
            f"«обрыв потока» и открыть alerts kind=incident "
            f"source=spend.unknown_cost — открытых алертов нет; "
            f"вывод run: {out!r}")

    def test_ac12_known_cost_path_also_opens_alert(self):
        result_event = json.dumps({
            "type": "result", "is_error": False, "total_cost_usd": 0.031,
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })
        out = self.run_agent(*[
            (1, ["агент начал отвечать...\n", STREAM_BROKEN_LINE,
                f"{result_event}\n"]),
        ] * config.AGENT_ATTEMPTS)

        alerts = self.unknown_cost_alerts()
        self.assertTrue(
            alerts,
            f"AC-3/AC-12: алерт обязан открыться независимо от пути учёта "
            f"стоимости попытки (требование 5) — даже когда стоимость "
            f"попытки ИЗВЕСТНА (финальное событие потока пришло), "
            f"«Connection lost mid-response» в тексте попытки обязана "
            f"открыть spend.unknown_cost; вывод run: {out!r}")
        # Стоимость всё равно должна была быть учтена как обычно —
        # алерт-требование 5 не подменяет собой существующий путь charge_step,
        # а дополняет его (SPEC требование 5: «независимо от того, каким
        # путём... она сейчас обрабатывается», не «вместо»). Каждая из
        # `AGENT_ATTEMPTS` попыток несёт ту же стоимость.
        self.assertAlmostEqual(
            self.task_row()["spent_usd"], 0.031 * config.AGENT_ATTEMPTS,
            places=6,
            msg="известная стоимость каждой попытки обязана остаться "
                "учтена как и раньше — новый алерт не отменяет charge_step")


if __name__ == "__main__":
    unittest.main()
