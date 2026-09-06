"""Приёмочный тест AC-4 — tasks/01M1THKPNZ11DBZAQDMJ33EMJR/SPEC.md.

AC-4. Отказы РАЗНЫХ классов (по одной задаче на 1а, на 1б, на «таймаут
шага») не суммируются в общий счётчик ни одного отдельного класса.

Красен до реализации: НЕТ — «зелёный с рождения». Счётчика стоп-крана
волны в коде нет вовсе (SPEC, «Контекст»), поэтому НИКАКОЙ алерт не
заводится вообще — критерий буквально требует ОТСУТСТВИЯ алерта, и
сегодняшнее (нулевое) поведение уже ему удовлетворяет. Тест ловит
регрессию конкретного класса реализации — счётчик, суммирующий отказы
РАЗНЫХ классов в одно число вместо трёх независимых, — а не саму
классификацию (для этого он тем не менее гоняет три РЕАЛЬНЫХ отказа,
не заглушку: с default `config.WAVE_BREAKER_TASKS=3` ошибочная
реализация «одна задача — одно событие в общий котёл» подняла бы алерт
уже на третьей задаче, независимо от того, что три класса разные).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WaveBreakerSandbox  # noqa: E402

CLASS_1A_TEXT = "API Error: 403 Request not allowed"
CLASS_1B_TEXT = "API Error: Connection refused (ConnectionRefused)"


class Ac4DifferentClassesNotSummedTest(WaveBreakerSandbox):

    def test_ac4_one_task_each_of_three_different_classes_raises_no_alert(self):
        """Одна задача класса 1а, одна — класса 1б, одна — таймаута шага:
        три отказа, три разных класса, ни по одному не набралось
        `config.WAVE_BREAKER_TASKS` (=3) задач.

        Ловит мутацию: счётчик ключуется только по (target, окно), без
        учёта класса отказа — тогда три задачи РАЗНЫХ классов дали бы
        суммарно 3 «любых» отказа target self и ошибочно подняли бы
        алерт, хотя ни один класс не достиг порога сам по себе.
        """
        task_1a = self.new_task("Класс 1а")
        self.fail_class(task_1a, CLASS_1A_TEXT)

        task_1b = self.new_task("Класс 1б")
        self.fail_class(task_1b, CLASS_1B_TEXT)

        task_timeout = self.new_task("Таймаут")
        self.fail_timeout(task_timeout)

        found = self.wave_breaker_alerts()

        self.assertEqual(
            found, [],
            f"по одной задаче на класс 1а/1б/таймаут не должно поднимать "
            f"алерт стоп-крана волны ни по одному отдельному классу; "
            f"найдено: {[r['message'] for r in found]}")


if __name__ == "__main__":
    unittest.main()
