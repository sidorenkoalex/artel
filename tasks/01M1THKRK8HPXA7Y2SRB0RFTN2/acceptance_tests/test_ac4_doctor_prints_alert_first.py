"""Приёмочные тесты 01M1THKRK8HPXA7Y2SRB0RFTN2 — AC-4 (SPEC.md).

Красен до реализации: `doctor.cmd_doctor` сейчас не читает
`kind=incident` алерты стоп-крана вовсе (только `kind=trigger`, в самом
конце вывода) — первая напечатанная строка при открытом алерте сейчас
«Осиротевшие артефактные ветки-кандидаты...», не текст, называющий
стоп-кран, поэтому `mentions_stop_crane(lines[0])` не совпадёт. Второй
тест файла (`test_ac4_no_open_alert_prints_nothing_about_stop_crane`) —
зелёный уже сегодня (без алерта упоминать нечего), это база сравнения
для первого, не отдельный предмет требования 3.
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (LightSandbox, capture, doctor,  # noqa: E402
                      mentions_stop_crane, raise_stop_crane_alert, store)


class Ac4DoctorPrintsAlertFirstTest(LightSandbox):
    """AC-4: `doctor` печатает открытый алерт стоп-крана первым пунктом
    вывода, до остальных проверок."""

    def run_doctor(self) -> str:
        # Остальные проверки нейтрализованы (сироты веток — пустой список
        # вместо недоступного origin, обычные doctor-проверки — пустой
        # список): предмет теста — ТОЛЬКО порядок печати алерта стоп-крана
        # относительно остального вывода, не сами эти проверки (они свои
        # у tests/test_doctor.py).
        with mock.patch.object(doctor, "_orphan_artifact_branches",
                               return_value=[]), \
                mock.patch.object(doctor, "all_checks", return_value=[]):
            return capture(doctor.cmd_doctor)

    def test_ac4_open_alert_is_the_first_printed_line(self):
        """Строка, называющая стоп-кран, стоит ПЕРВОЙ в выводе `doctor`
        — раньше сводки осиротевших веток и раньше остальных проверок.

        Ловит мутацию: если печать алерта стоп-крана добавят В КОНЕЦ
        вывода (по образцу существующей секции триггеров вместо начала
        функции), первой строкой останется сводка осиротевших веток, а
        не текст про стоп-кран.
        """
        raise_stop_crane_alert(store.db())

        out = self.run_doctor()

        lines = [line for line in out.splitlines() if line.strip()]
        self.assertTrue(lines, "doctor ничего не напечатал")
        self.assertTrue(mentions_stop_crane(lines[0]),
                       f"первая строка вывода doctor не называет стоп-кран: {lines[0]!r}")

    def test_ac4_no_open_alert_prints_nothing_about_stop_crane(self):
        """Без открытого алерта стоп-крана вывод `doctor` вообще не
        упоминает стоп-кран — базовая линия, отличающая предыдущий тест
        от статичной строки, печатаемой независимо от факта.

        Ловит мутацию: если строку про стоп-кран станут печатать
        безусловно (не проверяя реально ли открыт алерт), это упоминание
        останется и здесь, где алерт не заводился вовсе.
        """
        out = self.run_doctor()

        self.assertFalse(mentions_stop_crane(out))


if __name__ == "__main__":
    import unittest
    unittest.main()
