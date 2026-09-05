"""AC-7 (tasks/01M1REVP9WGRHDDNVEVE8BBH0Z/SPEC.md): «В том же случае
недоступности origin `doctor` без `--fix` печатает «критерий не вычислим
без origin» вместо списка кандидатов.»

Требование 6 (и AC-7) не упоминают FAIL/ненулевой код возврата, в отличие
от требования 5/AC-6, которые прямо требуют FAIL только для `doctor
--fix`. Предпросмотр — информационная строка (тот же класс, что
`check_root_pin`, который тоже деградирует до `ok`, если origin не
ответил, а не до FAIL): `doctor` без `--fix` не обязан падать из-за одной
лишь недоступности origin.

Красен до реализации: сегодня у `doctor` без `--fix` нет ветки кода для
предпросмотра кандидатов вовсе (см. AC-4) — фразы «критерий не вычислим
без origin» в выводе не будет, вне зависимости от origin.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import doctor  # noqa: E402
from tests.sandbox import capture  # noqa: E402

from _sandbox import ArtifactOriginSandbox  # noqa: E402


class Ac7OriginUnavailablePreviewMessageTest(ArtifactOriginSandbox):

    def test_ac7_preview_reports_uncomputable_criterion_instead_of_a_list(self):
        """origin недоступен, `doctor` без `--fix`: вместо числа/имён
        кандидатов — фраза «критерий не вычислим без origin»; ни одна
        ветка не тронута, команда не падает.

        Ловит мутацию: предпросмотр деградирует до «сирот не найдено»
        (тихо считает пустым списком, как AC-6 недопустимо для `--fix`) —
        тогда вывод не содержал бы честного «не вычислим», молчаливо
        имитируя «ничего страшного», хотя критерий на самом деле не
        проверен.
        """
        self.local_only_artifact_branch("t777")
        self.make_origin_unreachable()

        with mock.patch.object(doctor, "all_checks", lambda conn: []):
            out = capture(doctor.cmd_doctor)  # fix=False по умолчанию

        self.assertIn("критерий не вычислим без origin", out)
        self.assertNotIn("artifact/t777", out)
        self.assertTrue(self.branch_exists_locally("artifact/t777"))


if __name__ == "__main__":
    unittest.main()
