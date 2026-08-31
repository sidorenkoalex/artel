"""Приёмочные тесты T082 — AC-1, AC-2, AC-4, AC-7, AC-8.

Источник — tasks/T082/SPEC.md, «Критерии приёмки».

AC-1. Попытка шага с текстом, содержащим «403» или «Failed to
authenticate» (без учёта регистра), классифицируется как класс 1а.

AC-2. Попытка шага с текстом, содержащим «Connection refused» или
«ConnectionRefused» (без учёта регистра), классифицируется как класс 1б.

AC-4. Попытка шага с текстом, содержащим «API Error:», но не
совпадающим ни с одним списком требований 1–2, классифицируется как
класс 1 («системный кандидат»).

AC-7. После неудачной попытки класса 1а, 1б или «системный кандидат»
пауза перед следующей попыткой того же шага — порядка минут, заметно
больше сегодняшних 5–10 секунд экспоненциального бэкоффа.

AC-8. Число автоматических попыток шага при срабатывании требования 3
не меняется относительно сегодняшнего `AGENT_ATTEMPTS` — увеличивается
только пауза между попытками, не их количество.

Классов 1а/1б/«системный кандидат» сегодня в коде нет вовсе (SPEC,
«Контекст»: любой провал получает одинаковый секундный бэкофф). До
появления кода классификации единственный способ проверить, что
КОНКРЕТНАЯ подстрока попадает именно в этот класс, — наблюдаемый эффект
требования 3 (AC-7): пауза следующей попытки того же шага. Прямой вызов
несуществующей функции классификации был бы фантазией об интерфейсе,
которого SPEC не называет (test-authoring: «работай по SPEC, а не по
собственному дизайну API») — тесты поэтому идут только через
единственную существующую публичную точку входа роли, `runner.cmd_run`
(тот же приём, что и `tests/test_agent_failure.py`).

«Порядка минут» (AC-7) проверяется порогом `MINUTE_ORDER_SEC = 60` —
это дословная нижняя граница слова «минут» во множественном числе;
точное число секунд SPEC не называет (это крутилка реализации, не
предмет критерия), поэтому конкретное значение не зашивается ни в один
ассерт — только порог «заметно больше 5–10 с».

Красен до реализации: 6 из 7 тестов файла — сегодняшний `runner.py`
ретраит любой провал одинаковым секундным бэкоффом
(`config.RETRY_BACKOFF_SEC=5`, удвоение — 5с, 10с для
`AGENT_ATTEMPTS=3`) независимо от текста ошибки. Для любой из сигнатур
этого файла фактическая пауза сегодня 5с/10с — каждый тест на паузу
провалится по `assertGreaterEqual(pause, MINUTE_ORDER_SEC)` (проверено
прогоном на немодифицированном коде при подготовке файла).

Зелёный с рождения: `test_ac8_attempt_count_unchanged_for_transient_system_bundle`
(`BundleAttemptCountTest`) — требование 3/AC-8 требует, чтобы число
попыток НЕ изменилось относительно сегодняшнего `AGENT_ATTEMPTS`,
поэтому сегодняшнее поведение (ровно `AGENT_ATTEMPTS` попыток, эскалация
по исчерпании) уже удовлетворяет критерию буквально — тест ловит
регрессию (случайное урезание/увеличение числа попыток при реализации
классификации), не саму классификацию.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import RunnerSandbox  # noqa: E402

from orchestrator import config  # noqa: E402

# Дословная нижняя граница «порядка минут» (AC-7) — не точное число секунд
# реализации, а порог, отделяющий её от сегодняшних 5-10 с.
MINUTE_ORDER_SEC = 60


class Class1aAuthTest(RunnerSandbox):
    """AC-1: подстроки «403» / «Failed to authenticate» (без учёта регистра)."""

    def test_ac1_403_substring_classified_as_1a(self):
        out = self.run_agent(
            (1, ["упал: API Error: 403 Request not allowed\n"]),
            (0, ["поднялся\n"]),
        )
        self.assertEqual(len(self.pauses), 1)
        self.assertGreaterEqual(
            self.pauses[0], MINUTE_ORDER_SEC,
            f"AC-1: «403» обязана классифицироваться как класс 1а — "
            f"пауза перед повтором обязана быть порядка минут "
            f"(>= {MINUTE_ORDER_SEC} с), не сегодняшних "
            f"{config.RETRY_BACKOFF_SEC} с; вывод run: {out!r}, "
            f"паузы: {self.pauses}")

    def test_ac1_failed_to_authenticate_case_insensitive(self):
        out = self.run_agent(
            (1, ["FAILED TO AUTHENTICATE — токен просрочен\n"]),
            (0, ["поднялся\n"]),
        )
        self.assertGreaterEqual(
            self.pauses[0], MINUTE_ORDER_SEC,
            f"AC-1: «Failed to authenticate» без учёта регистра обязана "
            f"классифицироваться как класс 1а; вывод run: {out!r}, "
            f"паузы: {self.pauses}")


class Class1bNetworkTest(RunnerSandbox):
    """AC-2: подстроки «Connection refused» / «ConnectionRefused»."""

    def test_ac2_connection_refused_classified_as_1b(self):
        out = self.run_agent(
            (1, ["API Error: Connection refused — a firewall or proxy "
                "may be blocking it (ConnectionRefused)\n"]),
            (0, ["поднялся\n"]),
        )
        self.assertGreaterEqual(
            self.pauses[0], MINUTE_ORDER_SEC,
            f"AC-2: «Connection refused»/«ConnectionRefused» обязаны "
            f"классифицироваться как класс 1б — минутный бэкофф; "
            f"вывод run: {out!r}, паузы: {self.pauses}")

    def test_ac2_connectionrefused_case_insensitive_without_spaced_form(self):
        out = self.run_agent(
            (1, ["сеть: connectionrefused, повтор позже\n"]),
            (0, ["поднялся\n"]),
        )
        self.assertGreaterEqual(
            self.pauses[0], MINUTE_ORDER_SEC,
            f"AC-2: «ConnectionRefused» без учёта регистра — класс 1б; "
            f"вывод run: {out!r}, паузы: {self.pauses}")


class SystemCandidateTest(RunnerSandbox):
    """AC-4: «API Error:» без совпадения со списками требований 1-2."""

    def test_ac4_bare_api_error_prefix_classified_as_system_candidate(self):
        # 529/Overloaded — не входит ни в один специфичный список (1а/1б/2):
        # только общий якорь «API Error:» (требование 1, «страховка от
        # промаха мимо конкретной формулировки»).
        out = self.run_agent(
            (1, ["API Error: 529 Overloaded, please retry later\n"]),
            (0, ["поднялся\n"]),
        )
        self.assertGreaterEqual(
            self.pauses[0], MINUTE_ORDER_SEC,
            f"AC-4: «API Error:» без совпадения со списками 1а/1б/2 "
            f"обязана классифицироваться как «системный кандидат» — "
            f"минутный бэкофф; вывод run: {out!r}, паузы: {self.pauses}")


class BundleMagnitudeTest(RunnerSandbox):
    """AC-7: пауза перед следующей попыткой — порядка минут для всей связки
    1а/1б/«системный кандидат» (требование 3), не только первой попытки."""

    def test_ac7_every_retry_pause_of_the_bundle_is_minute_order(self):
        out = self.run_agent(*[
            (1, ["API Error: 403 Request not allowed\n"])
        ] * config.AGENT_ATTEMPTS)

        self.assertEqual(len(self.pauses), config.AGENT_ATTEMPTS - 1)
        for pause in self.pauses:
            self.assertGreaterEqual(
                pause, MINUTE_ORDER_SEC,
                f"AC-7: КАЖДАЯ пауза между попытками связки "
                f"1а/1б/«системный кандидат» обязана быть порядка минут, "
                f"заметно больше сегодняшних 5-10 с; вывод run: {out!r}, "
                f"паузы: {self.pauses}")


class BundleAttemptCountTest(RunnerSandbox):
    """AC-8: число попыток шага не меняется — только пауза между ними.

    Зелёный с рождения (см. докстринг модуля): сегодняшнее поведение уже
    тратит ровно `AGENT_ATTEMPTS` попыток на любой провал — критерий
    буквально о том, что классификация НЕ ДОЛЖНА этого менять."""

    def test_ac8_attempt_count_unchanged_for_transient_system_bundle(self):
        out = self.run_agent(*[
            (1, ["API Error: Connection refused (ConnectionRefused)\n"])
        ] * config.AGENT_ATTEMPTS)

        self.assertEqual(
            self.popen.call_count, config.AGENT_ATTEMPTS,
            f"AC-8: связка 1а/1б/«системный кандидат» обязана исчерпывать "
            f"ровно `config.AGENT_ATTEMPTS` попыток, как и сегодня — "
            f"увеличивается только пауза, не их число; вывод run: {out!r}")
        self.assertEqual(
            self.task_row()["state"], "escalated",
            "исчерпание попыток связки всё ещё приводит к эскалации шага, "
            "как и сегодня (требование 3 не ослабляет инвариант 3)")


if __name__ == "__main__":
    unittest.main()
