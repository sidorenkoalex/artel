"""AC-2 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «pid группы (pgid)
агентного шага пишется рядом с существующим pid — в lease и/или журнал
шага — так, чтобы каждый из путей требования 2 мог его прочитать.»

SPEC сознательно не выбирает между lease и журналом («и/или») — тест
поэтому не завязан на конкретное хранилище (колонку `leases` или текст
записи журнала), только на факт: РЕАЛЬНЫЙ pgid спавненного шага (число,
полученное независимо — из файла, который сам пишет скрипт-проба)
где-то среди этих двух источников появляется. `_sandbox.
AgentStepSandbox.assert_lease_pid_unchanged` в других тестах этого
пакета (AC-4/AC-5/AC-6/AC-7/AC-14) полагается ровно на то, что запись
pgid не перезаписывает уже существующий `pid` лизы — это ЖЕ свойство
здесь проверяется явно первым, отдельной проверкой.

Красен до реализации: сегодня `leases` несёт только `pid` пульта, а
журнал шага не содержит числа pgid ни в одной записи — оба источника
(и объединённый текст) не содержат значение, прочитанное из файла-пробы.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AgentStepSandbox, store, wait_for  # noqa: E402


class PgidRecordedTest(AgentStepSandbox):

    PULT_PID_PLACEHOLDER = 999999  # заведомо непохожий на реальный pgid шага

    def test_ac2_pgid_is_recorded_in_lease_or_journal_alongside_existing_pid(self):
        """Существующий pid лизы (представляющий процесс пульта, ведущий
        шаг) уже стоит ДО запуска шага; после реального прогона —
        реальный pgid, записанный скриптом-пробой в файл, ищется среди
        (а) полей строки `leases` и (б) текста журнала задачи.

        Ловит мутацию: если развязка AC-1 заводит новую группу, но
        значение pgid никуда не пишется (ни в БД, ни в журнал) — оно не
        найдётся НИ В ОДНОМ из двух источников, и `assertTrue(found)`
        покраснеет, даже если сам факт «новая группа» (AC-1/AC-13) уже
        починен.
        """
        self.install_dummy_lease(self.PULT_PID_PLACEHOLDER)

        outcome, _, _ = self.run_step(self.pgid_probe_cmd())
        self.assertEqual(outcome, "ok", "шаг-проба не завершился успешно")

        probe = self.probe_path("pgid.txt")
        self.assertTrue(wait_for(probe.exists, timeout=2.0),
                        "скрипт-проба не записал свой pgid")
        recorded_pgid = probe.read_text(encoding="utf-8").strip()

        row = store.lease_row(store.db(), self.TASK)
        lease_text = " ".join(str(v) for v in dict(row).values()) if row else ""
        found_in_lease = recorded_pgid in lease_text.split()
        found_in_journal = recorded_pgid in self.journal_text().split()

        self.assertTrue(
            found_in_lease or found_in_journal,
            f"pgid шага ({recorded_pgid}) не найден ни в строке leases "
            f"({lease_text!r}), ни в журнале задачи — требование 2 "
            f"(AC-3..AC-6) не сможет его прочитать")

        # Существующий pid лизы (представляющий процесс пульта) не должен
        # исчезнуть/перезаписаться записью pgid — иначе адресация путей
        # AC-4/AC-5/AC-6 по нему сломана независимо от того, где именно
        # лежит сам pgid.
        if row is not None:
            self.assertEqual(row["pid"], self.PULT_PID_PLACEHOLDER,
                             "запись pgid перезаписала существующий pid лизы")


if __name__ == "__main__":
    unittest.main()
