"""AC-7 — 01M3GKJBXEBHB6ZA48J7VG8Z8W: подсказка `approve` и запись журнала
после успешного `answer` в `escalated`.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. В состоянии `escalated` успешный `answer` печатает строку «дальше:
artel.py approve <id> (снятие эскалации)» и пишет в журнал задачи запись
«ANSWER создан, ждёт approve».

Обе строки критерий задаёт дословно — планка сверяет их как есть, с
подстановкой id задачи в первую.

Красен до реализации: `orchestrator/answer.py:157-160` печатает только
строку о коммите и пишет в журнал действие «ANSWER создан» — ни подсказки
`approve`, ни ожидания в записи журнала сегодня нет, и цикл `auto`
останавливается сразу после ответа (вторая половина прецедента 26.09).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

#: Запись журнала, названная критерием дословно.
JOURNAL_ACTION = "ANSWER создан, ждёт approve"


class ApproveHintInEscalatedTest(_sandbox.AnswerMandateSandbox):

    def hint(self) -> str:
        return f"дальше: artel.py approve {self.TASK} (снятие эскалации)"

    def test_ac7_successful_answer_in_escalated_prints_the_approve_hint(self):
        """Задача в `escalated`, файл ответа без строк мандата — `answer`
        успешен и печатает подсказку «дальше: artel.py approve <id> (снятие
        эскалации)».

        Ловит мутацию: подсказка печатается, но без пояснения назначения
        (или с командой `auto` вместо `approve`, по образцу подсказки
        `zones-extend` рядом) — Оператор снова остаётся без шага, снимающего
        эскалацию, и `auto` стоит после ответа.
        """
        out = self.succeed_answer(_sandbox.PLAIN_ANSWER_TEXT)

        self.assertEqual(["ANSWER-1.md"], self.answer_files())
        self.assertIn(self.hint(), out)

    def test_ac7_successful_answer_in_escalated_journals_waiting_for_approve(self):
        """Тот же вызов пишет в журнал задачи запись «ANSWER создан, ждёт
        approve».

        Ловит мутацию: ожидание `approve` доехало только до stdout, а
        журнал по-прежнему несёт прежнее «ANSWER создан» — журнал остаётся
        единственным следом ответа, который читает и Оператор постфактум, и
        бриф роли, и по нему было бы не видно, что задача ждёт снятия
        эскалации.
        """
        self.succeed_answer(_sandbox.PLAIN_ANSWER_TEXT)

        self.assertTrue(
            any(JOURNAL_ACTION in line for line in self.journal()),
            f"нет записи «{JOURNAL_ACTION}» в журнале: {self.journal()}")

    def test_ac7_hint_and_journal_record_follow_a_mandate_answer_too(self):
        """Критерий говорит «успешный `answer`» без оговорок о содержимом:
        файл со строкой исправного мандата зон в `escalated` получает ту же
        подсказку и ту же запись.

        Ловит мутацию: подсказка и запись повешены на ветку «мандата в файле
        нет» (тот же `if mandate_paths: ... else: ...`, что уже выбирает
        текст записи журнала) — ответ Оператора, попутно выдавший мандат,
        остался бы без шага снятия эскалации.
        """
        out = self.succeed_answer(_sandbox.answer_text(
            _sandbox.zones_mandate_line(_sandbox.EXISTING_FILE)))

        self.assertEqual(["ANSWER-1.md"], self.answer_files())
        self.assertIn(self.hint(), out)
        self.assertTrue(
            any(JOURNAL_ACTION in line for line in self.journal()),
            f"нет записи «{JOURNAL_ACTION}» в журнале: {self.journal()}")


if __name__ == "__main__":
    unittest.main()
