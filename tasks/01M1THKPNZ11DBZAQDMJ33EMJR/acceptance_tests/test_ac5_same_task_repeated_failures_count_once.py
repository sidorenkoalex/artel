"""Приёмочный тест AC-5 — tasks/01M1THKPNZ11DBZAQDMJ33EMJR/SPEC.md.

AC-5. Несколько отказов ОДНОЙ И ТОЙ ЖЕ задачи одного класса в пределах
окна считаются как одна задача, не как несколько событий.

`WaveBreakerSandbox.fail_class` уже гоняет `config.AGENT_ATTEMPTS`
(сегодня 3) провальных попыток ОДНОЙ задачи подряд с одним и тем же
текстом — классификатор журналирует «agent failure classified» на
КАЖДОЙ из них (три события, одна задача). Это ровно тот сценарий,
который наивный подсчёт «по событиям» перепутал бы с тремя разными
задачами.

Красен до реализации: ДА — счётчика нет вовсе, алерт не появляется ни
на каком шаге сценария (см. `test_ac2_ac3_task_threshold.py`, тот же
класс отсутствующей механики).
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WaveBreakerSandbox  # noqa: E402

CLASS_1B_TEXT = "API Error: Connection refused (ConnectionRefused)"

_TASK_COUNT_RE = re.compile(r"у (\d+) задач")


class Ac5RepeatedFailuresOfOneTaskCountOnceTest(WaveBreakerSandbox):

    def test_ac5_one_tasks_retries_do_not_alone_reach_the_threshold(self):
        """Одна задача проходит через `config.AGENT_ATTEMPTS` (3)
        провальных попыток класса 1б подряд — это ТРИ журнальных события
        одного класса, но ОДНА задача; порог `config.WAVE_BREAKER_TASKS`
        (тоже 3) считает задачи, поэтому одна задача его не достигает.

        Ловит мутацию: подсчёт числа СТРОК журнала данного класса вместо
        числа РАЗЛИЧНЫХ `task_id` — тогда уже одна задача с тремя
        провальными попытками подняла бы алерт стоп-крана волны здесь.
        """
        task = self.new_task("Ретраится сама с собой")
        self.fail_class(task, CLASS_1B_TEXT)

        found = self.wave_breaker_alerts()

        self.assertEqual(
            found, [],
            f"три провальные попытки ОДНОЙ задачи не эквивалентны трём "
            f"разным задачам — алерт не должен появиться; найдено: "
            f"{[r['message'] for r in found]}")

    def test_ac5_message_names_three_tasks_not_nine_events(self):
        """Три РАЗНЫЕ задачи (первая — после `config.AGENT_ATTEMPTS`
        собственных провальных попыток, т.е. трёх событий её самой)
        доводят число различных задач класса 1б до 3 — алерт появляется
        и называет именно 3 задачи, не суммарное число журнальных
        событий (3 попытки × 3 задачи = 9).

        Ловит мутацию: счётчик суммирует количество строк журнала этого
        класса, а не `len(set(task_id ...))` — сообщение назвало бы 9
        (или другое число событий), не 3.
        """
        first = self.new_task("Первая")
        self.fail_class(first, CLASS_1B_TEXT)
        second = self.new_task("Вторая")
        self.fail_class(second, CLASS_1B_TEXT)
        third = self.new_task("Третья")
        self.fail_class(third, CLASS_1B_TEXT)

        found = self.wave_breaker_alerts()

        self.assertEqual(len(found), 1)
        match = _TASK_COUNT_RE.search(found[0]["message"])
        self.assertIsNotNone(
            match,
            f"сообщение обязано содержать «у N задач»; сообщение: "
            f"{found[0]['message']!r}")
        self.assertEqual(
            int(match.group(1)), 3,
            f"число задач в сообщении обязано быть 3 (различных задач), "
            f"не 9 (событий журнала: 3 попытки × 3 задачи); сообщение: "
            f"{found[0]['message']!r}")


if __name__ == "__main__":
    unittest.main()
