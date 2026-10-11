"""Приёмочные тесты T082 — AC-13.

Источник — tasks/T082/SPEC.md, «Критерии приёмки».

AC-13. Журнал шага (`store.journal`) содержит сырой текст ошибки (или
совпавший якорный фрагмент) для каждой неудачной попытки, классов
1а/1б/«обрыв потока»/«системный кандидат»/2 (AC-1–AC-5) — не только
файл лога попытки.

Критерий сформулирован буквально как «текст присутствует где-то в
store.journal, не только в файле лога» — без требования к конкретному
action/полю (SPEC не называет ни то ни другое). Тест поэтому ищет
подстроку по ВСЕЙ БД журнала задачи (`SELECT detail FROM steps ...`),
а не в конкретной записи: тем самым он проверяет ровно то, что говорит
AC-13, не домысливая формат «структурного» хранения (SPEC требование 6
называет его целью — переиспользование для будущего пополнения списков
подстрок, — но не форматом самой записи).

Зелёный с рождения: для ВСЕХ пяти классов `orchestrator/runner.py`
СЕГОДНЯ уже копирует хвост лога попытки (`agent_log.log_tail`) в
`store.journal` записью `agent run FAILED` (см. `runner.py:846-848`) —
при коротком логе (одна строка ошибки, как в этих тестах) хвост
содержит её целиком, поэтому буквальный текст критерия уже выполняется
СЕГОДНЯ (проверено прогоном на немодифицированном коде при подготовке
файла — все пять тестов зелёные без единой правки runner.py).

Это верно и полезно как регрессионный тест (он поймает случайную потерю
`log_tail`/детали из журнала при рефакторинге классификации под T082),
но НЕ доказывает «структурности» хранения в духе SPEC «Контекст» (текст
там же называет сегодняшнее совмещение хвоста внутри строки причины
неструктурным) — эта грань критерия критерий не формализует отдельно
от буквальной формулировки AC-13, и тест её поэтому не проверяет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import RunnerSandbox  # noqa: E402

from orchestrator import config  # noqa: E402

# По одной короткой сигнатуре на каждый класс требований 1-2 (AC-1..AC-5).
CLASS_SIGNATURES = {
    "1а": "API Error: 403 Request not allowed",
    "1б": "API Error: Connection refused (ConnectionRefused)",
    "обрыв потока": "API Error: Connection lost mid-response. The "
                    "response above may be incomplete.",
    "системный кандидат": "API Error: 529 Overloaded, please retry later",
    "2 (session limit)": "usage limit reached, resets at 20:00",
}


class JournalCarriesRawErrorTextTest(RunnerSandbox):

    def _assert_phrase_in_journal(self, phrase: str) -> None:
        out = self.run_agent(*[(1, [f"{phrase}\n"])] * config.AGENT_ATTEMPTS)

        self.assertIn(
            phrase.lower(), self.journal_blob(),
            f"AC-13: сырой текст ошибки провалившейся попытки обязан "
            f"попасть в store.journal (не только в файл лога); "
            f"вывод run: {out!r}, журнал: {self.journal_blob()!r}")

    def test_ac13_class_1a_text_in_journal(self):
        self._assert_phrase_in_journal(CLASS_SIGNATURES["1а"])

    def test_ac13_class_1b_text_in_journal(self):
        self._assert_phrase_in_journal(CLASS_SIGNATURES["1б"])

    def test_ac13_stream_broken_text_in_journal(self):
        self._assert_phrase_in_journal(CLASS_SIGNATURES["обрыв потока"])

    def test_ac13_system_candidate_text_in_journal(self):
        self._assert_phrase_in_journal(CLASS_SIGNATURES["системный кандидат"])

    def test_ac13_class_2_text_in_journal(self):
        self._assert_phrase_in_journal(CLASS_SIGNATURES["2 (session limit)"])


if __name__ == "__main__":
    unittest.main()
