"""Подсказка отказа гейта сохранности тестов называет обе формы доставки
мандата — `answer` в `in_dev` и `answer` в `escalated` (AC-7).

Группа: разовый

Красен до реализации: `test_integrity._mandate_hint` называет «команда
answer» без состояния — ни `in_dev`, ни `escalated` в тексте нет.

Почему разовый, а не долгоживущий: SPEC называет поверхностью закрытую
функцию `_mandate_hint`, а публичный путь к её тексту — только stdout
перехода `in_dev -> verifying` через `fsm.cmd_advance`, перед гейтом
которого стоят десяток рубежей (свежесть, ёмкость, зоны, заявка мутации),
проходимых в песочнице лишь подменой закрытых имён `fsm_advance` — правила
долгоживущего файла (только публичный интерфейс) этого не допускают. Сам
текст подсказки после мержа держит обычный набор `tests/` пульта.

AC-1..AC-6 покрыты долгоживущим файлом
`tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py`.
"""
import unittest

from orchestrator.advance_gates import test_integrity

TASK_IDS = ("01M42NB9GKXNP74HAYEJ7C7CA8", "T001")


class MandateHintNamesBothStatesTest(unittest.TestCase):

    def test_ac7_hint_names_answer_in_in_dev_and_in_escalated(self):
        """Подсказка отказа называет команду `answer` и состояния `in_dev` и `escalated`.

        Текст подсказки строится для двух разных идентификаторов задачи;
        в каждом есть «answer», «in_dev» и «escalated», а также сам
        идентификатор (подсказка по-прежнему адресует свою задачу).

        Ловит мутацию: в подсказку добавлен только новый канал (`answer` в
        `in_dev`) и выпал прежний (`escalated`), или наоборот подсказка
        осталась прежней — в тексте нет одного из двух состояний.
        """
        for task_id in TASK_IDS:
            hint = test_integrity._mandate_hint(task_id)
            for word in ("answer", "in_dev", "escalated", task_id):
                self.assertIn(word, hint, f"{task_id}: нет «{word}» в {hint!r}")


if __name__ == "__main__":
    unittest.main()
