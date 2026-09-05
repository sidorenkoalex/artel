"""AC-4 (tasks/01M1REVP9WGRHDDNVEVE8BBH0Z/SPEC.md): «`doctor` без `--fix`
печатает число кандидатов на удаление и первые N их имён (N — именованная
константа `orchestrator/config.py`) с пометкой, что их удалит `doctor
--fix`; ни одна ветка при этом не удаляется.»

`N` читается ДИНАМИЧЕСКИ из `config.DOCTOR_ORPHAN_PREVIEW_LIMIT`
(conventions-core, test-authoring: «предпосылки о значениях конфигурации
пиши динамически от config, не литералом») — крутилка Оператора, тест не
имеет права зашивать сегодняшнее значение. Имена веток заведены с
одинаковой шириной нулевого дополнения (`t0000`, `t0001`, …), чтобы
лексикографическая сортировка `_orphan_artifact_branches` совпадала с
числовым порядком независимо от значения N.

`doctor.all_checks` подменена целиком — своя песочница живого/CLI-смоука
не нужна (тот же приём, что `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/
acceptance_tests/test_ac4_orphan_artifact_branch_cleanup.py::
Ac4CmdDoctorGatingTest`).

Красен до реализации: у `doctor` без `--fix` сегодня вообще нет ветки
кода для предпросмотра кандидатов (`cmd_doctor` печатает предпросмотр
только под `if fix:`) — вывод не будет содержать ни числа кандидатов, ни
их имён, ни пометки про `--fix`.
"""
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor  # noqa: E402
from tests.sandbox import capture  # noqa: E402

from _sandbox import ArtifactOriginSandbox  # noqa: E402


class Ac4PreviewListsCandidatesTest(ArtifactOriginSandbox):

    def test_ac4_preview_prints_count_first_n_names_and_fix_note_without_deleting(self):
        """Кандидатов больше N: печатается ПОЛНОЕ число кандидатов, но
        только ПЕРВЫЕ N имён (по сортировке) — остальные не появляются в
        выводе. Ни одна из веток не удаляется.

        Ловит мутацию: код печатает ВСЕ имена кандидатов вместо первых N
        (усечение не реализовано) — тогда имена за пределами N тоже
        оказались бы в выводе, хотя AC-4 требует именно «первые N»; либо
        печатает предпросмотр, но всё равно вызывает удаление — тогда
        ветки исчезли бы из локального репозитория.
        """
        n = config.DOCTOR_ORPHAN_PREVIEW_LIMIT
        total = n + 3
        ids = [f"t{i:04d}" for i in range(total)]
        for tid in ids:
            self.local_only_artifact_branch(tid)

        with mock.patch.object(doctor, "all_checks", lambda conn: []):
            out = capture(doctor.cmd_doctor)

        self.assertIn(str(total), out)
        for tid in ids[:n]:
            self.assertIn(f"artifact/{tid}", out)
        for tid in ids[n:]:
            self.assertNotIn(f"artifact/{tid}", out)
        self.assertIn("--fix", out)
        for tid in ids:
            self.assertTrue(self.branch_exists_locally(f"artifact/{tid}"),
                            f"artifact/{tid} не должна быть удалена предпросмотром")

    def test_ac4_no_candidates_deletes_nothing_and_does_not_crash(self):
        """Пустой список кандидатов (все ветки известны БД или на origin) —
        предпросмотр не падает и не удаляет ничего.

        Ловит мутацию: предпросмотр индексирует первые N имён без проверки
        на пустой список (например, `candidates[0]` без учёта пустоты) —
        упал бы `IndexError`/похожим на пустом кандидате.
        """
        self.push_artifact_branch("t001")

        with mock.patch.object(doctor, "all_checks", lambda conn: []):
            capture(doctor.cmd_doctor)  # не должно бросить исключение

        self.assertTrue(self.branch_exists_locally("artifact/t001"))


if __name__ == "__main__":
    unittest.main()
