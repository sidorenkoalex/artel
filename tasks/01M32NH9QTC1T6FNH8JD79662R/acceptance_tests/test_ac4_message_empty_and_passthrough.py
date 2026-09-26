"""AC-4: сказанный текст, пустое событие на служебных и незнакомых видах,
сквозной проброс строки, не разобравшейся как JSON-объект.

Красен до реализации: `CodexProvider.parse_output_line` ещё не реализован — базовый интерфейс поднимает `NotImplementedError` на любой строке.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stream import (AGENT_MESSAGE, AGENT_MESSAGE_TEXT,  # noqa: E402
                     BROKEN_JSON_LINE, ERROR_ITEM, ITEM_UPDATED,
                     JSON_ARRAY_LINE, THREAD_STARTED, TRACEBACK_LINE,
                     TURN_STARTED, UNKNOWN_EVENT, UNKNOWN_ITEM, provider)
from orchestrator.providers import base  # noqa: E402


class AgentMessageTest(unittest.TestCase):
    """`agent_message` — то, что исполнитель сказал словами."""

    def test_ac4_agent_message_gives_the_spoken_text(self):
        """Элемент `agent_message` отдаёт свой текст полем `text` события.

        Ловит мутацию: текст сообщения агента кладётся только в строку
        лога — поле `text` события остаётся `None`, и всё, что читает
        сказанное исполнителем помимо лога, перестаёт видеть его слова.
        """
        event = provider().parse_output_line(AGENT_MESSAGE)

        self.assertEqual(event.text, AGENT_MESSAGE_TEXT)


class EmptyEventTest(unittest.TestCase):
    """Служебные и незнакомые виды: пустое событие, не ошибка и не
    исключение."""

    def test_ac4_service_and_unknown_kinds_give_an_empty_event(self):
        """`thread.started`, `turn.started`, незнакомый вид события и
        незнакомый вид элемента дают ровно `base.EMPTY_EVENT`.

        В перечне — `item.updated` и элемент `item.type=error`
        переключения транспорта: это не отдельная механика, а те же
        незнакомые виды, которых образцы не несут, а живой запуск 0.155.1
        несёт (SPEC требование 1, последний абзац).

        Ловит мутацию: незнакомый вид поднимает исключение (или отдаёт
        итог запуска с признаком ошибки) — первая же строка `item.updated`
        живого потока роняет разбор шага либо помечает шаг
        провалившимся, хотя CLI всего лишь дописал прогресс вызова.
        """
        cases = (("thread.started", THREAD_STARTED),
                 ("turn.started", TURN_STARTED),
                 ("незнакомый вид события", UNKNOWN_EVENT),
                 ("item.updated", ITEM_UPDATED),
                 ("незнакомый вид элемента", UNKNOWN_ITEM),
                 ("элемент error", ERROR_ITEM))

        for label, raw in cases:
            with self.subTest(label):
                self.assertEqual(provider().parse_output_line(raw),
                                 base.EMPTY_EVENT)


class PassthroughTest(unittest.TestCase):
    """Строка мимо формата событий: целиком в лог шага, больше нигде."""

    def test_ac4_a_line_that_is_no_json_object_goes_whole_to_the_step_log(self):
        """Строка, не разобравшаяся как JSON-объект (трейсбек CLI, битый
        JSON, JSON-массив), уходит в `log_text` целиком и ни на что
        больше не влияет.

        Ловит мутацию: неразобравшаяся строка возвращает `EMPTY_EVENT`
        («это же не событие») — stderr и трейсбек CLI молча исчезают из
        лога шага, и Оператор разбирает провал по логу, в котором
        причины провала нет.
        """
        for raw in (TRACEBACK_LINE, BROKEN_JSON_LINE, JSON_ARRAY_LINE):
            with self.subTest(raw=raw[:40]):
                event = provider().parse_output_line(raw)

                self.assertEqual(event.log_text, raw,
                                 "строка уходит в лог шага целиком")
                self.assertEqual(
                    event, base.StreamEvent(raw, None, (), (), None, None),
                    "и больше ничего в событии не появляется")


if __name__ == "__main__":
    unittest.main()
