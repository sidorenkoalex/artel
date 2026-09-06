"""Приёмочные тесты AC-1 — tasks/01M1THKPNZ11DBZAQDMJ33EMJR/SPEC.md.

AC-1. `orchestrator/config.py` несёт `WAVE_BREAKER_WINDOW_SEC=900` и
`WAVE_BREAKER_TASKS=3`; функция подсчёта и порог срабатывания читают
именно эти константы (правка констант меняет поведение без правки
остального кода).

Имена констант — не выбор автора тестов: SPEC называет их буквально
(`WAVE_BREAKER_WINDOW_SEC`, `WAVE_BREAKER_TASKS`), в отличие от
прецедента `01M1KCSTBYF1CRJBSY4P6VYQEA` (там имя константы приходилось
фиксировать тестами). Здесь фиксируется только их существование,
значения по умолчанию и, чувствительным тестом, факт, что реализация
ЧИТАЕТ их на каждом сравнении — не копирует значение в отдельную
константу и не хардкодит число вместо чтения атрибута.

Красен до реализации: ДА, весь файл — `orchestrator/config.py` сегодня
не несёт ни `WAVE_BREAKER_WINDOW_SEC`, ни `WAVE_BREAKER_TASKS`
(проверено прогоном на немодифицированном коде: `AttributeError` при
первом же обращении), а стоп-крана волны нет вовсе — второй и третий
тест ниже дополнительно упали бы по отсутствию алерта, даже будь
константы заведены сами по себе.

Песочница — `_sandbox.WaveBreakerSandbox` (см. её докстринг: `runner.
cmd_run` с фейковым агентом — единственная сегодня публичная точка
входа, через которую наблюдаем эффект будущего счётчика).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WaveBreakerSandbox  # noqa: E402

CLASS_1B_TEXT = "API Error: Connection refused (ConnectionRefused)"


class Ac1ConstantsExistTest(unittest.TestCase):
    """AC-1: константы заведены с указанными в SPEC значениями по умолчанию."""

    def test_ac1_window_default_is_900_seconds(self):
        """Ловит мутацию: константа заведена с другим значением (например,
        скопирован какой-то другой таймаут секунд) — SPEC называет именно
        900 (15 минут)."""
        self.assertEqual(config.WAVE_BREAKER_WINDOW_SEC, 900)

    def test_ac1_task_threshold_default_is_3(self):
        """Ловит мутацию: порог заведён со значением, отличным от 3
        (например, скопирован другой лимит соседней механики)."""
        self.assertEqual(config.WAVE_BREAKER_TASKS, 3)


class Ac1ThresholdConstantIsReadDynamicallyTest(WaveBreakerSandbox):
    """AC-1: порог срабатывания читается из `config.WAVE_BREAKER_TASKS`,
    а не зашит литералом 3 — правка константы меняет наблюдаемое
    поведение без правки остального кода."""

    def test_ac1_lowering_the_threshold_makes_two_failures_trigger(self):
        """С порогом, понижённым до 2, ДВЕ разные задачи с одинаковым
        классом отказа (1б) обязаны поднять алерт стоп-крана волны — при
        дефолтном пороге 3 этого не происходит (см. AC-3).

        Ловит мутацию: порог зашит литералом `3` внутри функции подсчёта
        вместо чтения `config.WAVE_BREAKER_TASKS` — тогда понижение
        константы не изменило бы поведение, и этот тест упал бы (алерта
        не было бы вовсе).
        """
        with mock.patch.object(config, "WAVE_BREAKER_TASKS", 2):
            task_a = self.new_task("A")
            task_b = self.new_task("B")
            self.fail_class(task_a, CLASS_1B_TEXT)
            self.fail_class(task_b, CLASS_1B_TEXT)

            found = self.wave_breaker_alerts()

        self.assertEqual(
            len(found), 1,
            f"с порогом 2 две разные задачи класса 1б обязаны поднять "
            f"алерт стоп-крана волны; открытые incident-алерты: "
            f"{[r['message'] for r in self.open_incident_alerts()]}")


class Ac1WindowConstantIsReadDynamicallyTest(WaveBreakerSandbox):
    """AC-1: окно, названное в тексте алерта (M минут), считается от
    `config.WAVE_BREAKER_WINDOW_SEC`, а не от зашитого числа минут."""

    def test_ac1_message_reports_the_configured_window_in_minutes(self):
        """Окно понижено до 120 секунд (2 минуты) — заметно отличается от
        дефолтных 15 минут; текст алерта обязан назвать именно 2 минуты.

        Ловит мутацию: текст алерта хардкодит «15 минут» (или любое
        фиксированное число) вместо `config.WAVE_BREAKER_WINDOW_SEC // 60`
        — тогда сообщение по-прежнему называло бы 15 минут при
        пониженной константе, и `assertIn` ниже упал бы.
        """
        with mock.patch.object(config, "WAVE_BREAKER_WINDOW_SEC", 120):
            for title in ("A", "B", "C"):
                task = self.new_task(title)
                self.fail_class(task, CLASS_1B_TEXT)

            found = self.wave_breaker_alerts()

        self.assertEqual(len(found), 1)
        window_min = 120 // 60
        self.assertIn(
            f"{window_min}", found[0]["message"],
            f"сообщение алерта обязано называть окно в минутах, "
            f"вычисленное из config.WAVE_BREAKER_WINDOW_SEC=120 (2 "
            f"минуты), а не фиксированное число; сообщение: "
            f"{found[0]['message']!r}")


if __name__ == "__main__":
    unittest.main()
