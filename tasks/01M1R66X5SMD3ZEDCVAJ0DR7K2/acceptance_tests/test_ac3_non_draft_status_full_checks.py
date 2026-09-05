"""Приёмочные тесты 01M1R66X5SMD3ZEDCVAJ0DR7K2 — AC-3 (с включённым
режимом артефактной ветки и status, отличным от draft, у тех же четырёх
типов — все текущие правила содержания применяются без исключений,
результат совпадает с проверкой без режима).

Красен до реализации: сегодня флаг `--artifact-branch` не распознан
(см. докстринг `test_ac2_draft_downgraded_to_warning.py`) — прогон С
флагом сегодня падает по ДРУГОЙ причине («файл не найден» для самого
имени флага), поэтому число нарушений «с флагом» и «без флага» сегодня
НЕ совпадает (расходится именно на два фиктивных «файл не найден»)
— тест ниже сравнивает число упоминаний стабильной фразы текущего кода
(`отсутствует обязательная секция`), не сами exit-коды, поэтому
покраснеет он не на расхождении кодов, а на расхождении этого счётчика.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FILE_NAME_BY_TYPE, MISSING_SECTION_PHRASE,  # noqa: E402
                      NON_DRAFT_STATUS, generic_broken_text, run_main)


class NonDraftResultMatchesNoModeTest(unittest.TestCase):
    """«Сдан»-статус (draft заменён валидным не-draft значением из
    `RULES`) с разбитым содержимым — режим включён или нет, результат
    один и тот же: и код выхода (1 — нарушение реальное), и число
    найденных нарушений."""

    def test_ac3_broken_non_draft_artifact_fails_the_same_way_with_or_without_the_flag(self):
        """Для каждого из четырёх типов requirement 2: прогон одного и
        того же «сданного» (не-draft) разбитого артефакта дважды — с
        флагом `--artifact-branch` и без него; оба прогона отказывают
        (exit 1), и число вхождений фразы про отсутствующую секцию
        совпадает.

        Ловит мутацию: разработчик понижает нарушения ЛЮБОГО статуса
        (не только `draft`) до предупреждения, пока включён режим
        (например путает `!=` на `==` в сравнении статуса на «draft») —
        тогда прогон С флагом для «сданного» артефакта дал бы exit 0 и
        нулевое число упоминаний фразы, разойдясь с прогоном без флага.
        """
        for atype, name in FILE_NAME_BY_TYPE.items():
            with self.subTest(тип=atype):
                status = NON_DRAFT_STATUS[atype]
                text = generic_broken_text(atype, status)

                code_off, out_off = run_main({f"tasks/T1/{name}": text},
                                             artifact_branch=False)
                code_on, out_on = run_main({f"tasks/T1/{name}": text},
                                           artifact_branch=True)

                self.assertEqual(code_off, 1, out_off)
                self.assertEqual(code_on, 1, out_on)
                count_off = out_off.count(MISSING_SECTION_PHRASE)
                count_on = out_on.count(MISSING_SECTION_PHRASE)
                self.assertGreaterEqual(count_off, 1, out_off)
                self.assertEqual(
                    count_off, count_on,
                    f"{atype}: без флага {count_off} упоминаний, с флагом "
                    f"{count_on} — режим не должен менять число найденных "
                    f"нарушений для не-draft статуса")


if __name__ == "__main__":
    unittest.main()
