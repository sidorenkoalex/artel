"""AC-6 (SPEC): записи журнала автогейта, где решение зависит от чтения
планки или её AC-пометок (AC-2..AC-5), называют источник чтения — ветку
и sha артефактной ветки, с которых планка прочитана.

Красен до реализации: сегодняшний код никогда не читает планку по
ветке (условие «а» решается по диску, `guard.scan_acceptance_tests
(acc_tdir)`), поэтому журнал не может называть ветку/sha, с которых
она прочитана — их там физически нет. Тесты покраснеют именно на
отсутствии имени ветки/sha в тексте журнала/вывода, не по случайной
причине.

Провалидировано временным стабом: реализация, дописывающая в перечень
`ok`/в текст `reason` строку вида «источник планки: ветка
<branch>, sha <sha>» (или эквивалентную, называющую оба значения),
зеленит все три сценария этого файла.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AutogateBranchSandbox, CLEAN_PLANKA, MANUAL_PLANKA  # noqa: E402
from orchestrator import artifact_branch  # noqa: E402


class JournalNamesArtifactSourceTest(AutogateBranchSandbox):

    def test_ac6_pass_journal_names_branch_and_sha(self):
        """Условие «а» пройдено (планка чистая) — запись журнала
        перехода `acceptance -> merge_gate` называет ветку и sha, с
        которых планка прочитана.

        Ловит мутацию: реализация проходит условие «а», но пишет в
        журнал только фразу «0 manual, 0 skip критериев» без ветки/sha
        — `assertIn` на оба значения ниже упадёт.
        """
        sha = self.seed_planka(CLEAN_PLANKA)

        self.autogate()

        detail = "\n".join(r[2] for r in self.journal_rows())
        self.assertIn(self.artifact_branch, detail)
        self.assertIn(sha, detail)

    def test_ac6_manual_refusal_journal_names_branch_and_sha(self):
        """Условие «а» отказано по manual-критерию — причина в журнале
        называет ту же ветку и sha, с которых планка прочитана (не
        только формулировку «критерии manual — AC-...», проверенную в
        AC-3).

        Ловит мутацию: отказ по manual печатает только формулировку
        причины без источника чтения — `assertIn` на ветку/sha упадёт.
        """
        sha = self.seed_planka(MANUAL_PLANKA)

        self.autogate()

        detail = "\n".join(r[2] for r in self.journal_rows())
        self.assertIn(self.artifact_branch, detail)
        self.assertIn(sha, detail)

    def test_ac6_missing_planka_refusal_journal_names_branch_and_sha(self):
        """Условие «а» отказано по пустому/отсутствующему каталогу —
        причина в журнале называет ветку и sha, на которых каталог
        отсутствует (не только формулировку причины, проверенную в
        AC-5).

        Ловит мутацию: отказ по пустому каталогу без указания источника
        чтения — `assertIn` на ветку/sha упадёт.
        """
        sha = artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/SPEC.md": "# SPEC\n"},
            "тест: ветка без планки")

        self.autogate()

        detail = "\n".join(r[2] for r in self.journal_rows())
        self.assertIn(self.artifact_branch, detail)
        self.assertIn(sha, detail)


if __name__ == "__main__":
    unittest.main()
