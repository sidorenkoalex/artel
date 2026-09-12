"""Приёмочный тест AC-3 задачи 01M2B6JS2BZNBW9WSHT1RPFXTE (note: окно
тишины): при удержании по AC-2 команда печатает сообщение «заметка
удержана: <причина окна тишины>; отправка — note --flush либо
автоматически следующим note вне окна» — фиксированные пролог и эпилог
байт-в-байт, свободная середина — причина открытого окна (какой из
двух триггеров АС-1 сработал).

Красен до реализации: команда сегодня ничего не печатает при
удержании (единственный текст удержания сегодня — сообщение сетевого
отказа через `sys.exit`, другой текст и другой канал) — тест красен на
`assertIn("заметка удержана:", captured)`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402

_PREFIX = "заметка удержана:"
_SUFFIX = ("отправка — note --flush либо автоматически следующим note "
          "вне окна")


class HoldMessageTextTest(NoteSandbox):

    def test_ac3_message_prefix_and_suffix_on_task_state_trigger(self):
        """Окно открыто задачей в `acceptance` — сообщение несёт
        фиксированный пролог и эпилог, между ними непустая причина.

        Ловит мутацию: реализация молчит при удержании (возвращает без
        `print`) — тест красен на пустом `captured`.
        """
        self.insert_task_in_state("acceptance")

        captured = self.capture(
            notes.cmd_note,
            ["копилка", "--text", "9 | 09.09 | тест сообщения | orchestrator/m.py"])

        self.assertIn(_PREFIX, captured, captured)
        self.assertIn(_SUFFIX, captured, captured)
        between = captured.split(_PREFIX, 1)[1].split(";", 1)[0].strip()
        self.assertTrue(between, "причина окна тишины не должна быть пустой")

    def test_ac3_message_prefix_and_suffix_on_live_merge_lock_trigger(self):
        """Тот же формат сообщения, когда триггер — живой держатель
        `merge_locks`, а не состояние задачи (второй рукав условия ИЛИ
        АС-1) — оба триггера обязаны печатать сообщение того же вида.

        Ловит мутацию: сообщение зашито под конкретный триггер (например,
        текст «причины» хардкодит имя состояния задачи и остаётся
        пустым/неверным для триггера merge_locks) — тест красен на
        отсутствии непустой причины в этом сценарии.
        """
        self.set_live_merge_lock()

        captured = self.capture(
            notes.cmd_note,
            ["копилка", "--text", "9 | 09.09 | тест держателя | orchestrator/h.py"])

        self.assertIn(_PREFIX, captured, captured)
        self.assertIn(_SUFFIX, captured, captured)
        between = captured.split(_PREFIX, 1)[1].split(";", 1)[0].strip()
        self.assertTrue(between, "причина окна тишины не должна быть пустой")


if __name__ == "__main__":
    unittest.main()
