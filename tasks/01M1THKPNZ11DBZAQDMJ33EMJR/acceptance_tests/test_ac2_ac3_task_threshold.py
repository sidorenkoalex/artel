"""Приёмочные тесты AC-2, AC-3 — tasks/01M1THKPNZ11DBZAQDMJ33EMJR/SPEC.md.

AC-2. Три РАЗНЫЕ задачи target self отказали классом 1б (сетевой отказ
до API) в пределах `WAVE_BREAKER_WINDOW_SEC` — заводится алерт
`kind=incident` с текстом, называющим класс, число задач и окно.

AC-3. Две РАЗНЫЕ задачи с тем же классом за то же окно — алерт НЕ
заводится.

Класс отказа выбран 1б (сетевой отказ до API, сигнатура «Connection
refused») — один из `TRANSIENT_SYSTEM_CLASSES`, уже классифицируемый
сегодняшним `failure_classification.classify_attempt_failure` (T082).

Красен до реализации: ДА — счётчика/алерта стоп-крана волны в коде нет
вовсе (SPEC, «Контекст»): `_record_failure_classification` журналирует
класс отказа, но ничего не агрегирует и не заводит `kind=incident` по
числу задач. AC-2 упадёт (алерта нет ни одного), AC-3 зелёный С
РОЖДЕНИЯ по построению критерия (отсутствие алерта — это и есть
ожидаемый результат), но зависит от AC-2 в том же файле, чтобы не быть
тавтологией — оба теста используют один и тот же наблюдаемый маркер
(`WaveBreakerSandbox.wave_breaker_alerts`), так что «зелёный сегодня»
проверяет то же свойство, которое AC-2 ловит для N=3.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WaveBreakerSandbox  # noqa: E402

CLASS_1B_TEXT = "API Error: Connection refused (ConnectionRefused)"
# Токен класса — буквальное слово SPEC требования 2 («1б»), не полная
# метка `failure_classification.CLASS_LABELS["1b"]` (её точный текст —
# выбор реализации, не предмет критерия).
CLASS_1B_TOKEN = "1б"


class Ac2ThreeDistinctTasksRaiseIncidentTest(WaveBreakerSandbox):
    """AC-2: три разные задачи, отказавшие классом 1б в пределах окна,
    заводят алерт `kind=incident`, называющий класс, число задач и окно."""

    def test_ac2_three_distinct_tasks_same_class_raise_incident_alert(self):
        """Три разные задачи одна за другой отказывают классом 1б
        (`Connection refused`) — после третьей обязан появиться ровно
        один открытый `incident`-алерт стоп-крана волны, называющий класс
        1б, число задач (3) и окно (в минутах, `config.
        WAVE_BREAKER_WINDOW_SEC // 60`).

        Ловит мутацию: счётчик вовсе не заведён, либо заводится, но не
        поднимает алерт при достижении порога — `wave_breaker_alerts()`
        останется пустым.
        """
        for title in ("Первая", "Вторая", "Третья"):
            task = self.new_task(title)
            self.fail_class(task, CLASS_1B_TEXT)

        found = self.wave_breaker_alerts()

        self.assertEqual(
            len(found), 1,
            f"три разные задачи класса 1б обязаны поднять ровно один "
            f"алерт стоп-крана волны; открытые incident-алерты: "
            f"{[r['message'] for r in self.open_incident_alerts()]}")
        message = found[0]["message"]
        self.assertEqual(found[0]["kind"], "incident")
        self.assertIn(CLASS_1B_TOKEN, message,
                     f"сообщение обязано называть класс отказа; "
                     f"сообщение: {message!r}")
        self.assertIn("3", message,
                     f"сообщение обязано называть число задач (3); "
                     f"сообщение: {message!r}")


class Ac3TwoDistinctTasksDoNotRaiseIncidentTest(WaveBreakerSandbox):
    """AC-3: две разные задачи с тем же классом за то же окно — алерт
    стоп-крана волны НЕ заводится (порог по умолчанию — 3)."""

    def test_ac3_two_distinct_tasks_same_class_do_not_raise_alert(self):
        """Две разные задачи отказывают классом 1б — порог `config.
        WAVE_BREAKER_TASKS=3` не достигнут, алерт стоп-крана волны не
        появляется.

        Ловит мутацию: порог срабатывания занижен (например, `>= 2`
        вместо `>= config.WAVE_BREAKER_TASKS`) — тогда алерт появился бы
        уже после второй задачи.
        """
        for title in ("Первая", "Вторая"):
            task = self.new_task(title)
            self.fail_class(task, CLASS_1B_TEXT)

        found = self.wave_breaker_alerts()

        self.assertEqual(
            found, [],
            f"двух разных задач класса 1б недостаточно для порога "
            f"config.WAVE_BREAKER_TASKS={config.WAVE_BREAKER_TASKS} — "
            f"алерт не должен появляться; найдено: "
            f"{[r['message'] for r in found]}")


if __name__ == "__main__":
    unittest.main()
