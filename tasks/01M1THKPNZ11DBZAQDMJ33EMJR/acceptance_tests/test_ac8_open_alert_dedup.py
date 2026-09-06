"""Приёмочный тест AC-8 — tasks/01M1THKPNZ11DBZAQDMJ33EMJR/SPEC.md.

AC-8. Пока алерт стоп-крана данного класса уже открыт, повторное
достижение порога тем же классом не заводит второй такой же алерт
(дедуп по target+kind+source+класс).

Дедуп — НЕ по буквальному тексту сообщения (число задач N в тексте
меняется от срабатывания к срабатыванию: 3, затем 6) — тем же приёмом,
что `alerts.raise_token_rate_divergence_alert` (SPEC, «Материалы»).
Обычный `alerts.raise_alert` дедупит по точному `message` — с ним три
новые задачи задачи после первого срабатывания завели бы ВТОРОЙ алерт
с другим текстом («...у 6 задач...»), поэтому этот тест — прямая
проверка того, что реализация НЕ использует `raise_alert` буквально.

Красен до реализации: ДА — счётчика/алерта стоп-крана волны нет вовсе,
`wave_breaker_alerts()` пуст на каждом шаге сценария.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WaveBreakerSandbox  # noqa: E402

CLASS_1B_TEXT = "API Error: Connection refused (ConnectionRefused)"


class Ac8OpenAlertDedupTest(WaveBreakerSandbox):

    def test_ac8_reaching_the_threshold_again_does_not_duplicate_the_alert(self):
        """Три задачи класса 1б поднимают алерт стоп-крана волны; ещё три
        РАЗНЫЕ задачи того же класса в пределах того же окна снова
        доводят число различных задач до порога (уже 6 из 6) — открытый
        алерт этого класса остаётся ОДИН, не заводится второй.

        Ловит мутацию: дедуп по буквальному тексту сообщения
        (`alerts.raise_alert` напрямую, без обхода как у
        `raise_token_rate_divergence_alert`) — сообщение второго
        срабатывания называет другое число задач (6, не 3), точное
        совпадение текста не сработает, и второй алерт откроется рядом с
        первым.
        """
        for title in ("Первая", "Вторая", "Третья"):
            task = self.new_task(title)
            self.fail_class(task, CLASS_1B_TEXT)

        first_round = self.wave_breaker_alerts()
        self.assertEqual(len(first_round), 1, "первое срабатывание — один алерт")

        for title in ("Четвёртая", "Пятая", "Шестая"):
            task = self.new_task(title)
            self.fail_class(task, CLASS_1B_TEXT)

        second_round = self.wave_breaker_alerts()

        self.assertEqual(
            len(second_round), 1,
            f"открытый алерт стоп-крана волны этого класса обязан "
            f"остаться один после повторного достижения порога; "
            f"найдено: {[r['message'] for r in second_round]}")
        self.assertEqual(
            first_round[0]["id"], second_round[0]["id"],
            "это обязана быть ТА ЖЕ строка алерта, не новая с тем же текстом")


if __name__ == "__main__":
    unittest.main()
