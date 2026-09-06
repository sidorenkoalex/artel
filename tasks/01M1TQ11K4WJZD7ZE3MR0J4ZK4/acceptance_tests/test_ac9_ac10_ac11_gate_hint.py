"""Приёмочные тесты 01M1TQ11K4WJZD7ZE3MR0J4ZK4 — AC-9..AC-11: подсказка
калибровки на гейте SPEC при `approve` (требование 3).

Фикстура SPEC (`_sandbox.py::spec_text`) несёт 8 критериев `AC-n` и 2
файла в `zones` — по таблице AC-1 это средний уровень, ориентир $45
(отдельно проверяемый test_ac1_ac2_calibration_table.py); здесь важно
только то, что ориентир и действующий `budget_usd` печатаются рядом со
строкой «дальше:», а предупреждение появляется/не появляется по порогу
трети.

Смешанная краснота — по методу, не по всему файлу (`_cmd_approve` на
`spec_gate` сегодня печатает только «дальше: …», см. `orchestrator/
fsm.py:894`/`:899` — ни ориентира, ни действующего `budget_usd`, ни
строки предупреждения):

Красен до реализации: `GateHintBaselineOutputTest.test_ac9_...` и
`GateHintWarningPresentTest.test_ac10_...` — `assertRegex` на суммах
$45/$50 и на `WARNING_RE` не находят совпадений (случайное совпадение
по цифрам с id/sha исключено `\\b`-границей регэкспа и буквальным
префиксом «рамка ниже калибровки»/«$» перед числом).

Зелёный с рождения: `GateHintWarningAbsentTest.test_ac10_...` (вторая
половина AC-10) и `ApproveDoesNotChangeBudgetOrTransitionTest.
test_ac11_...` — сегодняшний approve не печатает предупреждение никогда
(нечему появляться лишним образом при потолке, равном ориентиру) и не
трогает `budget_usd`/переход состояния при расхождении, которого
сегодняшний код вообще не вычисляет, — оба свойства уже верны ДО этой
задачи, тест фиксирует их как регрессионную планку на будущее.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import GateHintSandbox, WARNING_RE, dollar_re  # noqa: E402


class GateHintBaselineOutputTest(GateHintSandbox):
    """AC-9: approve на `spec_gate` печатает рядом со строкой «дальше:»
    ориентир по таблице AC-1 и действующий `budget_usd`."""

    def test_ac9_approve_output_carries_dalshe_orientir_and_budget(self):
        """SPEC с 8 критериями/2 файлами zones (ориентир $45) и
        действующим потолком $50 (выше ориентира, чтобы не задеть
        предупреждение AC-10 в этом тесте) — вывод `approve` несёт и
        привычную строку «дальше:», и ориентир $45, и действующий
        потолок $50.

        Ловит мутацию: подсказка калибровки добавлена, но существующая
        строка «дальше: …» случайно потеряна тем же изменением (замена
        `print`, а не добавление) — `assertIn` на «дальше:» падает;
        подсказка печатает ориентир, но не действующий `budget_usd` (или
        наоборот) — один из `assertRegex` падает.
        """
        task_id = "01BGTHINTAC9BASE00000001"
        sha = self.enter_spec_gate(task_id, ac_count=8, zone_files=2,
                                   budget_usd=50.0)

        out = self.approve(task_id, sha)

        self.assertIn(
            "дальше:", out,
            f"вывод approve потерял привычную строку «дальше:»: {out!r}")
        self.assertRegex(
            out, dollar_re(45),
            f"вывод approve не несёт ориентир $45 по таблице AC-1: {out!r}")
        self.assertRegex(
            out, dollar_re(50),
            f"вывод approve не несёт действующий budget_usd $50: {out!r}")


class GateHintWarningPresentTest(GateHintSandbox):
    """AC-10 (часть 1): `budget_usd` ниже ориентира более чем на треть —
    предупреждение в выводе и запись в журнале."""

    def test_ac10_low_budget_prints_warning_and_journals_it(self):
        """SPEC с ориентиром $45 (8 AC, 2 файла) и действующим потолком
        $20 (порог срабатывания — $45 * 2/3 = $30, $20 заметно ниже) —
        вывод `approve` несёт «рамка ниже калибровки: $20 против ~$45»,
        и та же строка появляется в журнале задачи.

        Ловит мутацию: approve сравнивает `budget_usd` с ориентиром в
        обратную сторону (предупреждает, когда потолок ВЫШЕ ориентира) —
        при потолке $20 из $45 предупреждение не появляется вовсе.
        """
        task_id = "01BGTHINTAC10WARN0000001"
        sha = self.enter_spec_gate(task_id, ac_count=8, zone_files=2,
                                   budget_usd=20.0)

        out = self.approve(task_id, sha)

        self.assertRegex(
            out, WARNING_RE,
            f"вывод approve не несёт предупреждение о низком потолке: "
            f"{out!r}")
        details = self.journal_details(task_id)
        self.assertTrue(
            any(WARNING_RE.search(d or "") for d in details),
            f"журнал задачи не несёт строку предупреждения: {details!r}")


class GateHintWarningAbsentTest(GateHintSandbox):
    """AC-10 (часть 2): `budget_usd` не ниже ориентира более чем на
    треть — ни строки предупреждения, ни записи в журнале."""

    def test_ac10_budget_at_orientir_prints_no_warning(self):
        """SPEC с ориентиром $45 (8 AC, 2 файла) и действующим потолком
        РОВНО $45 — вывод `approve` не содержит «рамка ниже калибровки»,
        и журнал задачи не несёт такую запись.

        Ловит мутацию: предупреждение печатается при ЛЮБОМ несовпадении
        потолка с ориентиром, а не только при занижении больше чем на
        треть (например сравниваются на строгое неравенство `!=` вместо
        порогового расхождения) — при точном совпадении предупреждение
        появилось бы, хотя расхождения нет вовсе.
        """
        task_id = "01BGTHINTAC10NOWARN00001"
        sha = self.enter_spec_gate(task_id, ac_count=8, zone_files=2,
                                   budget_usd=45.0)

        out = self.approve(task_id, sha)

        self.assertNotRegex(
            out, WARNING_RE,
            f"вывод approve несёт лишнее предупреждение при потолке в "
            f"норме: {out!r}")
        details = self.journal_details(task_id)
        self.assertFalse(
            any(WARNING_RE.search(d or "") for d in details),
            f"журнал задачи несёт лишнюю запись предупреждения: "
            f"{details!r}")


class ApproveDoesNotChangeBudgetOrTransitionTest(GateHintSandbox):
    """AC-11: переход `approve` из `spec_gate` завершается как раньше
    (`tests_writing`/`in_dev`) и не меняет `budget_usd` ни при каком
    расхождении с ориентиром — отказ перехода вместо предупреждения
    считается провалом критерия."""

    def test_ac11_low_budget_does_not_block_or_change_the_transition(self):
        """SPEC с сильно заниженным потолком $20 при ориентире $45 (тот
        же сценарий, где предупреждение обязано сработать, AC-10) — гейт
        всё равно переводит задачу дальше состояния `spec_gate` (SPEC
        версии 2 с AC-разметкой без `skip_tests` -> `tests_writing`), и
        `budget_usd` строки задачи остаётся РОВНО тем же значением $20,
        каким был до approve — не заменяется ни на $45 (ориентир), ни на
        что-либо ещё.

        Ловит мутацию: approve отказывает переход при расхождении
        потолка с ориентиром (`sys.exit`/возврат без смены состояния)
        вместо того, чтобы только предупредить — состояние задачи
        остаётся `spec_gate`, `assertEqual` на состоянии падает; либо
        approve «сам» поднимает потолок до ориентира — `budget_usd`
        перестаёт быть равен 20.0.
        """
        task_id = "01BGTHINTAC11NOBLOCK0001"
        sha = self.enter_spec_gate(task_id, ac_count=8, zone_files=2,
                                   budget_usd=20.0)

        self.approve(task_id, sha)

        row = self.task_row(task_id)
        self.assertEqual(
            row["state"], "tests_writing",
            f"approve не перевёл задачу дальше spec_gate: "
            f"{row['state']!r}")
        self.assertEqual(
            row["budget_usd"], 20.0,
            f"approve изменил budget_usd расхождением с ориентиром: "
            f"{row['budget_usd']!r}")


if __name__ == "__main__":
    unittest.main()
