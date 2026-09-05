"""AC-5 (tasks/01M1REVP9WGRHDDNVEVE8BBH0Z/SPEC.md): «`doctor --fix`
печатает тот же список кандидатов (число и первые N имён с той же
пометкой) до удаления и число фактически удалённых веток после.»

Один кандидат (не публикуется на origin), явно НЕ содержащий цифру `1` в
своём имени (`t777`/`t778`) — единственная цифра `1`, обособленная
словесной границей, которая может появиться в выводе при подменённом
`doctor.all_checks -> []`, это и есть искомое число (единица дважды:
предпросмотр и факт удаления). Один кандидат — тест не зависит от
значения `config.DOCTOR_ORPHAN_PREVIEW_LIMIT` (AC-4 уже кроет усечение
по N отдельно): единственный кандидат всегда попадает в «первые N».

Красен до реализации: сегодня `cmd_doctor(fix=True)` не печатает
предпросмотр ДО удаления вовсе (только список удалённого после) — число
кандидатов до удаления в выводе не появится.
"""
import re
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import doctor  # noqa: E402
from tests.sandbox import capture  # noqa: E402

from _sandbox import ArtifactOriginSandbox  # noqa: E402


class Ac5FixPrintsPreviewThenDeletedCountTest(ArtifactOriginSandbox):

    def test_ac5_prints_candidate_preview_before_and_deleted_count_after(self):
        """Ровно один кандидат-сирота: предпросмотр (число+имя+пометка
        `--fix`) печатается, ветка реально удаляется, число фактически
        удалённых веток тоже появляется в выводе.

        Ловит мутацию: `cmd_doctor(fix=True)` печатает только список
        удалённых ПОСЛЕ (прежнее поведение), без предпросмотра числа
        кандидатов ДО удаления, — обособленная «1» встретится в выводе
        только один раз вместо двух.
        """
        self.local_only_artifact_branch("t777")

        with mock.patch.object(doctor, "all_checks", lambda conn: []):
            out = capture(lambda: doctor.cmd_doctor(fix=True))

        self.assertIn("artifact/t777", out)
        self.assertIn("--fix", out)
        standalone_ones = re.findall(r"(?<!\w)1(?!\w)", out)
        self.assertGreaterEqual(
            len(standalone_ones), 2,
            f"ожидалось число кандидатов до удаления И число фактически "
            f"удалённых после — обе единицы, вывод:\n{out}")
        self.assertFalse(self.branch_exists_locally("artifact/t777"),
                         "единственный кандидат обязан быть удалён")

    def test_ac5_no_candidates_reports_nothing_deleted(self):
        """Кандидатов нет (ветка известна БД) — предпросмотр и итог
        сходятся на «ничего не найдено/удалено», ветка на месте.

        Ловит мутацию: отсутствие кандидатов трактуется как ошибка/пустой
        предпросмотр без явного «0» — например, `IndexError` на пустом
        списке имён при печати первых N (тот же класс мутации, что и
        AC-4 «нет кандидатов»), либо ложное сообщение об удалении.
        """
        self.push_artifact_branch("t001")

        with mock.patch.object(doctor, "all_checks", lambda conn: []):
            capture(lambda: doctor.cmd_doctor(fix=True))  # не должно бросить

        self.assertTrue(self.branch_exists_locally("artifact/t001"))


if __name__ == "__main__":
    unittest.main()
