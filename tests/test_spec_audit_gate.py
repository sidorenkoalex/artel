"""Аудит SPEC (SPEC 01M4MQAGRWMWR0GFDM9086P3TD) — свойства журнала визита,
не покрытые долгоживущими файлами задачи: подсказка остановки `auto` на
гейте при вердикте `fail`, сброс «последнего вердикта» новым входом в
аудит, счёт возвратов только по записям возврата, запись входа при
возврате задачи из эскалации в `spec_audit`.

Песочница — `tests.sandbox.InitializedTmpRootTest`: БД во временном каталоге, строки
задач и записи журнала заводятся публичными `store.insert_task`/
`store.journal`, git не нужен.
"""
import unittest

from orchestrator import auto, config, fsm, store
from orchestrator.advance_gates import spec_audit
from tests.sandbox import InitializedTmpRootTest, capture

TASK = "01M4MQAGRWMWR0GFDM9086P3TE"


class _AuditJournalTest(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Аудит фикстуры", "spec_gate",
                          f"task/{TASK.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def journal(self, action: str, detail: str = "", actor: str = "fsm") -> None:
        store.journal(self.conn, TASK, actor, action, detail)

    def verdict(self, verdict: str) -> None:
        self.journal(spec_audit.VERDICT_ACTION, f"вердикт {verdict}; сигналы: нет")


class AutoStopVerdictTest(_AuditJournalTest):

    def test_gate_stop_names_fail_verdict_and_the_flag(self):
        """Остановка `auto` на гейте SPEC при последнем вердикте fail называет
        вердикт в причине и флаг `--accept-audit-fail` в подсказке; при pass
        — вердикт без флага.

        Ловит мутацию: `auto_stop_advice` не читает вердикт журнала (причина
        без «вердикт fail») или подсказка не называет флаг — Оператор,
        нажав подсказанный `approve`, получает отказ без объяснения, что
        принять fail можно только флагом.
        """
        self.verdict("fail")
        reason, hint = auto.auto_stop_advice(self.conn, TASK, "spec_gate")
        self.assertIn("вердикт fail", reason)
        self.assertIn(spec_audit.ACCEPT_FAIL_FLAG, hint)

        self.verdict("pass")
        reason, hint = auto.auto_stop_advice(self.conn, TASK, "spec_gate")
        self.assertIn("вердикт pass", reason)
        self.assertNotIn(spec_audit.ACCEPT_FAIL_FLAG, hint)


class LastVerdictTest(_AuditJournalTest):

    def test_new_entry_into_audit_clears_the_last_verdict(self):
        """Вердикт, после которого задача снова вошла в `spec_audit`, уже не
        «последний»: `last_verdict` — `None`, пока не записан новый.

        Ловит мутацию: `last_verdict` берёт последнюю запись вердикта без
        сверки со входами — fail прошлого визита держал бы `approve` после
        повторного аудита, ещё не вынесшего вердикт.
        """
        self.verdict("fail")
        self.assertEqual(spec_audit.last_verdict(self.conn, TASK), "fail")
        self.journal("state -> spec_audit")
        self.assertIsNone(spec_audit.last_verdict(self.conn, TASK))
        self.verdict("concerns")
        self.assertEqual(spec_audit.last_verdict(self.conn, TASK), "concerns")

    def test_return_count_counts_only_return_records(self):
        """Счётчик возвратов — число записей возврата аналитику по fail;
        вердикт на гейт, `reject` (вход в `spec_writing`) и новый вход в
        аудит его не меняют и не сбрасывают.

        Ловит мутацию: счётчик ведётся от последнего входа в `spec_writing`
        или считает все записи вердикта — после `reject` третий fail снова
        вернул бы задачу аналитику сверх лимита.
        """
        for _ in range(2):
            self.journal(spec_audit.RETURN_ACTION, "вердикт fail; возврат")
        self.verdict("pass")
        self.journal("state -> spec_writing", "возврат из spec_gate: причина")
        self.journal("state -> spec_audit")
        self.assertEqual(spec_audit.return_count(self.conn, TASK), 2)


class EscalationReturnEntryTest(_AuditJournalTest):

    def test_return_from_escalation_into_audit_records_a_new_entry(self):
        """`approve` из `escalated` с `escalated_from = spec_audit` возвращает
        задачу в аудит и пишет новую запись входа (sha SPEC и сигналы на
        момент возврата).

        Ловит мутацию: возврат из эскалации не пишет запись входа — вердикт
        сверяется с sha SPEC до эскалации, и правка SPEC Оператором за
        эскалацию дала бы вечный отказ «SPEC сменился за визит аудита».
        """
        store.update_task(self.conn, TASK, state="escalated",
                          escalated_from=spec_audit.STATE)
        before = [r["id"] for r in store.task_steps(self.conn, TASK)
                  if r["action"] == spec_audit.ENTRY_ACTION]

        capture(fsm.cmd_approve, TASK)

        self.assertEqual(store.get_task(self.conn, TASK)["state"],
                         spec_audit.STATE)
        after = [r["id"] for r in store.task_steps(self.conn, TASK)
                 if r["action"] == spec_audit.ENTRY_ACTION]
        self.assertEqual(len(after), len(before) + 1)


if __name__ == "__main__":
    unittest.main()
