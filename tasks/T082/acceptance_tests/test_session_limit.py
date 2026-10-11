"""Приёмочные тесты T082 — AC-5, AC-9, AC-10, AC-11.

Источник — tasks/T082/SPEC.md, «Критерии приёмки».

AC-5. Попытка шага с текстом, содержащим «session limit», «usage
limit», «5-hour limit» или «resets at» (без учёта регистра),
классифицируется как класс 2.

AC-9. После неудачной попытки класса 2 остаток автоматических попыток
шага не расходуется — шаг уходит в отказ/эскалацию сразу, не дожидаясь
исчерпания `AGENT_ATTEMPTS`.

AC-10. Отказ/эскалация по AC-9 несёт пометку, что причина —
ограничение сессии подписки и нужно дождаться его сброса (reset).

AC-11. Каждое обнаружение класса 2 у попытки шага открывает или
инкрементирует отдельную запись в alerts (kind=trigger), адресуемую
триггеру №15 (`docs/triggers.md`).

До появления кода классификации ЕДИНСТВЕННЫЙ наблюдаемый эффект класса 2
— именно AC-9 (одна попытка вместо `AGENT_ATTEMPTS`), поэтому AC-5
тестируется через него: каждая из четырёх подстрок требования 2 обязана
сразу останавливать ретраи. AC-11 не задаёт формат «инкремента» (в
таблице `alerts` нет числового счётчика — только (target, kind, source,
message), см. `orchestrator/store.py`) — тест поэтому проверяет то, что
дословно требует критерий: НАЛИЧИЕ открытой записи kind=trigger после
каждого обнаружения (после первого и после второго, отдельным прогоном
через `approve` -> `run`), не конкретный механизм счётчика — это выбор
реализации, не часть формулировки AC.

Красен до реализации: сегодня класс 2 не существует — любой провал
(в т.ч. с текстом «session limit») тратит все `AGENT_ATTEMPTS` попыток
с секундным бэкоффом и эскалирует стандартным сообщением "агент не
отработал за N попытки" без какой-либо пометки про лимит сессии; алерт
kind=trigger не заводится нигде в коде на провал попытки агента вовсе
(проверено прогоном на немодифицированном коде при подготовке файла).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import RunnerSandbox  # noqa: E402

from orchestrator import config  # noqa: E402

class SessionLimitClassificationTest(RunnerSandbox):
    """AC-5: каждая из четырёх подстрок требования 2 — класс 2.

    Один метод на подстроку (не `subTest` в цикле внутри одного метода):
    каждый прогон нуждается в собственной свежей песочнице `setUp`/
    `tearDown` (свой временный каталог, своя БД, свои патчи), а
    `TmpRootTest.setUp` не рассчитан на повторный ручной вызов внутри
    уже идущего теста (`addCleanup` копил бы патчи поверх уже
    накопленных). Тот же приём, что `tasks/T074/acceptance_tests/
    test_ac9_checkpoint_on_abnormal_step_end.py` — несколько методов
    `test_ac9_...*` на один критерий.
    """

    def _assert_single_attempt(self, phrase: str) -> None:
        # Сегодняшний код ретраит класс 2 как обычный провал —
        # `AGENT_ATTEMPTS` заготовленных попыток нужны, чтобы
        # `spawn_agent` не упёрся в `StopIteration` раньше, чем тест
        # дойдёт до содержательного ассерта (красный тест обязан падать
        # на assertEqual, а не на исчерпании side_effect мока).
        out = self.run_agent(*[(1, [f"{phrase}\n"])] * config.AGENT_ATTEMPTS)
        self.assertEqual(
            self.popen.call_count, 1,
            f"AC-5: «{phrase}» обязана классифицироваться как класс 2 — "
            f"один провал обязан сразу остановить ретраи (требование 4), "
            f"не дойти до {config.AGENT_ATTEMPTS} попыток; вывод run: "
            f"{out!r}")

    def test_ac5_session_limit_phrase(self):
        self._assert_single_attempt("You've hit your session limit for now.")

    def test_ac5_usage_limit_phrase(self):
        self._assert_single_attempt("usage limit reached — try again later")

    def test_ac5_5_hour_limit_phrase(self):
        self._assert_single_attempt("5-hour limit reached, try later")

    def test_ac5_resets_at_phrase(self):
        self._assert_single_attempt("Claude usage RESETS AT 09:00 UTC")


class SessionLimitDoesNotSpendAttemptsTest(RunnerSandbox):
    """AC-9: остаток автоматических попыток не расходуется на классе 2."""

    def test_ac9_single_failed_attempt_escalates_without_exhausting_attempts(self):
        out = self.run_agent(*[
            (1, ["session limit reached for this account\n"])
        ] * config.AGENT_ATTEMPTS)

        self.assertEqual(
            self.popen.call_count, 1,
            f"AC-9: класс 2 обязан остановить шаг на первой же провалившейся "
            f"попытке, не расходуя остаток `AGENT_ATTEMPTS="
            f"{config.AGENT_ATTEMPTS}`; вывод run: {out!r}")
        self.assertEqual(
            self.task_row()["state"], "escalated",
            f"AC-9: шаг обязан уйти в отказ/эскалацию сразу, не дожидаясь "
            f"исчерпания попыток; вывод run: {out!r}")


class SessionLimitEscalationNoteTest(RunnerSandbox):
    """AC-10: эскалация несёт пометку о лимите сессии подписки и reset."""

    def test_ac10_escalation_names_subscription_session_limit_and_reset(self):
        out = self.run_agent(*[
            (1, ["usage limit reached, resets at 14:00\n"])
        ] * config.AGENT_ATTEMPTS)

        text = (out + "\n" + self.journal_blob()).lower()
        self.assertTrue(
            "session" in text or "лимит сесси" in text
            or "подписк" in text,
            f"AC-10: эскалация обязана назвать причину — ограничение "
            f"сессии подписки; вывод run: {out!r}, журнал: "
            f"{self.journal_blob()!r}")
        self.assertTrue(
            "reset" in text or "сброс" in text,
            f"AC-10: эскалация обязана упомянуть необходимость дождаться "
            f"сброса (reset) лимита; вывод run: {out!r}, журнал: "
            f"{self.journal_blob()!r}")


class SessionLimitTriggerAlertTest(RunnerSandbox):
    """AC-11: обнаружение класса 2 открывает/инкрементирует alerts kind=trigger
    триггера №15."""

    def trigger_15_alerts(self) -> list:
        text_15 = ("15", "session limit", "сесси")
        return [a for a in self.open_alerts(kind="trigger")
               if any(t in f"{a['source']} {a['message']}".lower()
                      for t in text_15)]

    def test_ac11_first_detection_opens_a_trigger_alert(self):
        out = self.run_agent(*[
            (1, ["5-hour limit reached\n"])
        ] * config.AGENT_ATTEMPTS)

        alerts = self.trigger_15_alerts()
        self.assertTrue(
            alerts,
            f"AC-11: обнаружение класса 2 обязано открыть alerts "
            f"kind=trigger, адресуемую триггеру №15 (docs/triggers.md) — "
            f"открытых trigger-алертов, ссылающихся на лимит сессии/15, "
            f"нет; вывод run: {out!r}")

    def test_ac11_second_detection_still_carries_an_open_trigger_record(self):
        # Первое обнаружение — эскалация; `approve` возвращает шаг в
        # in_dev (SPEC T006, «упавший шаг чинится повтором»), второе
        # обнаружение — независимый провал того же класса. `AGENT_ATTEMPTS`
        # заготовленных попыток на каждый прогон — см. `_assert_single_attempt`.
        self.run_agent(*[
            (1, ["session limit reached again\n"])
        ] * config.AGENT_ATTEMPTS)
        self.approve()
        self.run_agent(*[
            (1, ["session limit reached again\n"])
        ] * config.AGENT_ATTEMPTS)

        alerts = self.trigger_15_alerts()
        self.assertTrue(
            alerts,
            "AC-11: запись триггера №15 обязана остаться (открыта или "
            "инкрементирована), а не исчезнуть, после ВТОРОГО подряд "
            "обнаружения класса 2 — формат «инкремента» SPEC не "
            "фиксирует (в alerts нет числового поля счётчика), поэтому "
            "тест проверяет только наличие открытой записи")


if __name__ == "__main__":
    unittest.main()
