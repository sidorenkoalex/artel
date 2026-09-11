"""Приёмочные тесты 01M1TQ11K4WJZD7ZE3MR0J4ZK4 — AC-5..AC-8: подсказка
калибровки при `new` (требование 2).

Фикстура ТЗ (`_sandbox.py::tz_text`) несёт 3 пункта «Требуется:» и 2
пути в «Зоны:» — по таблице AC-1 это базовый уровень, ориентир $35
(файлов зоны меньше порога «5 и более», критериев меньше «6-10» — ни
один из повышающих уровней не задет, так что все тесты этого файла
проверяют поведение подсказки НЕЗАВИСИМО от точности самой таблицы,
которую отдельно проверяют test_ac1_ac2_calibration_table.py).

Смешанная краснота — по методу, не по всему файлу (`cmd_new` сегодня не
разбирает ни «Рамка: $N», ни «Требуется:», ни «Зоны:» вообще: grep по
`orchestrator/catalog.py` на «Рамка»/«Требуется» пуст):

Красен до реализации: `NewHintBaselineOutputTest.test_ac5_...` и
`NewHintWarningPresentTest.test_ac6_...` — вывод `cmd_new` сегодня не
содержит ни одной суммы в долларах и не несёт строку предупреждения ни
в выводе, ни в журнале; оба `assertRegex` этих тестов падают на
отсутствии совпадения.

Зелёный с рождения: `NewHintWarningAbsentTest.test_ac7_...` и оба
метода `NewDoesNotChangeTaskCreationTest` (AC-8) — сегодняшний `cmd_new`
не печатает предупреждение никогда (нечему появляться лишним образом) и
заводит задачу с дефолтным `budget_usd`, не читая «Рамка:» вовсе, так
что оба свойства «нет лишнего предупреждения» и «потолок не меняется»
уже верны ДО этой задачи — тест фиксирует их как регрессионную планку
на будущее, когда код для AC-5/AC-6 появится рядом.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import NewHintSandbox, WARNING_RE, dollar_re  # noqa: E402
from orchestrator import config  # noqa: E402


class NewHintBaselineOutputTest(NewHintSandbox):
    """AC-5: вывод `new` несёт ориентир по таблице AC-1 и разницу с
    рамкой, при рамке ВЫШЕ ориентира (чтобы не пересекаться с AC-6/AC-7
    условием предупреждения — здесь проверяется только базовое
    печатание, не порог)."""

    def test_ac5_new_output_carries_orientir_and_rama_together(self):
        """ТЗ с 3 пунктами «Требуется:», 2 путями «Зоны:» и «Рамка: $50»
        (заметно выше ориентира $35) — вывод `new` несёт обе суммы:
        ориентир таблицы AC-1 ($35) и саму рамку ($50), из которых
        читается разница.

        Ловит мутацию: функция подсказки печатает только рамку, не
        ориентир (или наоборот) — один из двух `assertRegex` ниже
        падает; печатает ориентир только когда рамка НИЖЕ него (спутана
        логика с AC-6/AC-7) — `assertRegex` на $35 тоже падает, потому
        что здесь рамка выше.
        """
        out, task_id = self.new_with_tz(trebuetsya_count=3, zone_files=2,
                                        rama=50)

        self.assertRegex(
            out, dollar_re(35),
            f"вывод new не несёт ориентир $35 по таблице AC-1: {out!r}")
        self.assertRegex(
            out, dollar_re(50),
            f"вывод new не несёт рамку $50 из ТЗ: {out!r}")


class NewHintWarningPresentTest(NewHintSandbox):
    """AC-6: рамка ниже ориентира более чем на треть — предупреждение в
    выводе и запись в журнал."""

    def test_ac6_low_rama_prints_warning_and_journals_it(self):
        """ТЗ с рамкой $10 при ориентире $35 (порог срабатывания —
        $35 * 2/3 ≈ $23.3, $10 заметно ниже) — вывод `new` несёт строку
        «рамка ниже калибровки: $10 против ~$35», и та же строка
        появляется в журнале задачи.

        Ловит мутацию: предупреждение печатается, но не журналируется
        (или наоборот) — один из двух `assertRegex`/`any(...)` ниже
        падает; либо порог сравнения перепутан (например сравнивается с
        половиной вместо трети) — при $10 из $35 (28.6% от ориентира,
        заметно больше трети занижения) предупреждение не появляется
        вовсе.
        """
        out, task_id = self.new_with_tz(trebuetsya_count=3, zone_files=2,
                                        rama=10)

        self.assertRegex(
            out, WARNING_RE,
            f"вывод new не несёт предупреждение о низкой рамке: {out!r}")
        details = self.journal_details(task_id)
        self.assertTrue(
            any(WARNING_RE.search(d or "") for d in details),
            f"журнал задачи не несёт строку предупреждения: {details!r}")


class NewHintWarningAbsentTest(NewHintSandbox):
    """AC-7: рамка не ниже ориентира более чем на треть — ни строки
    предупреждения в выводе, ни записи в журнале."""

    def test_ac7_rama_at_orientir_prints_no_warning(self):
        """ТЗ с рамкой $35 — РОВНО на ориентире (не ниже него вовсе) —
        вывод `new` не содержит строку «рамка ниже калибровки», и
        журнал задачи не несёт такую запись.

        Ловит мутацию: предупреждение печатается при ЛЮБОМ расхождении
        рамки с ориентиром, не только при занижении больше чем на треть
        (например сравнение неравенства направлено не в ту сторону, или
        порог трети не проверяется вовсе) — `assertNotRegex`/`assertFalse`
        ниже падают.
        """
        out, task_id = self.new_with_tz(trebuetsya_count=3, zone_files=2,
                                        rama=35)

        self.assertNotRegex(
            out, WARNING_RE,
            f"вывод new несёт лишнее предупреждение при рамке в норме: "
            f"{out!r}")
        details = self.journal_details(task_id)
        self.assertFalse(
            any(WARNING_RE.search(d or "") for d in details),
            f"журнал задачи несёт лишнюю запись предупреждения: "
            f"{details!r}")


class NewDoesNotChangeTaskCreationTest(NewHintSandbox):
    """AC-8: `new` заводит задачу и не меняет потолок задачи ни при каком
    соотношении рамки и ориентира — поведение заведения (id, ветка,
    дефолтный `budget_usd`) не меняется этой задачей."""

    def test_ac8_low_rama_does_not_lower_or_raise_task_budget(self):
        """ТЗ с занижённой рамкой $10 (тот же сценарий, что и AC-6, где
        предупреждение обязано сработать) — задача всё равно заводится с
        ДЕФОЛТНЫМ потолком `config.DEFAULT_BUDGET_USD`, не с суммой из
        «Рамка:» ТЗ и не с ориентиром таблицы.

        Ловит мутацию: разработчик по ошибке применяет ориентир или
        рамку как потолок заведённой задачи вместо дефолта (например
        трактует предупреждение как команду «поднять потолок сразу») —
        `budget_usd` строки задачи перестаёт быть равен
        `config.DEFAULT_BUDGET_USD`.
        """
        out, task_id = self.new_with_tz(trebuetsya_count=3, zone_files=2,
                                        rama=10)

        row = self.task_row(task_id)
        self.assertEqual(
            row["budget_usd"], config.DEFAULT_BUDGET_USD,
            f"потолок задачи изменился расхождением рамки/ориентира: "
            f"{row['budget_usd']!r}")

    def test_ac8_new_still_creates_a_resolvable_task(self):
        """Заведение задачи по-прежнему успешно возвращает task_id и
        создаёт строку `tasks` — расхождение рамки с ориентиром не
        превращает `new` в отказ (AC-8, «заведение не отказывает»).

        Ловит мутацию: подсказка калибровки останавливает `new`
        (`sys.exit`/исключение) при сильном занижении рамки вместо того,
        чтобы только предупредить — вызов `new_with_tz` не вернётся, тест
        упадёт исключением до первого `assert`.
        """
        out, task_id = self.new_with_tz(trebuetsya_count=3, zone_files=2,
                                        rama=10)

        self.assertTrue(task_id, "cmd_new не вернул task_id")
        row = self.task_row(task_id)
        self.assertEqual(row["state"], "spec_writing")


if __name__ == "__main__":
    unittest.main()
