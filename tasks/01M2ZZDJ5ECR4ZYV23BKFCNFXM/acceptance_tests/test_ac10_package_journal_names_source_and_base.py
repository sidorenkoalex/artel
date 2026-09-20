"""AC-10 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: запись журнала «ревью-пакет
собран» называет источник артефактов и базу инкремента.

Источник — SPEC.md, «Критерии приёмки»:

AC-10. Запись журнала «ревью-пакет собран» на итерации > 1 несёт
источник артефактов задачи (артефактная ветка / рабочий каталог шага /
не найден) и базу инкремента (sha); на итерации 1 та же запись несёт
источник артефактов и не несёт базы инкремента.

Красен до реализации: `orchestrator/review.py::package_note` пишет
размер, тип diff, номер итерации и — только при откате на рабочее дерево
— список файлов; ни источника артефактов как такового, ни базы
инкремента в записи нет, поэтому дефект класса «пакет собран не от того
sha» по журналу не виден.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402


class PackageJournalNamesSourceAndBaseTest(_sandbox.ReviewPackagePlankSandbox):

    def seed_anchor(self) -> str:
        sha = self.developer_commit(f"{_sandbox.DEV_MARK}-база\n")
        self.journal_verdict_anchor(sha, iteration=1)
        dev_sha = self.developer_commit(f"{_sandbox.DEV_MARK}-итерация-2\n")
        self.journal_transition("review")
        self.journal_fixation(dev_sha)
        return sha

    def package_detail(self, reviewed_iter: int) -> str:
        self.build_prompt(reviewed_iter=reviewed_iter)
        details = self.journal_details(_sandbox.PACKAGE_ACTION)
        self.assertTrue(details, "записи «ревью-пакет собран» нет в журнале")
        return details[-1]

    def assert_names_artifact_branch(self, detail: str) -> None:
        self.assertTrue(
            "артефактн" in detail.lower() or self.artifact_branch in detail,
            f"запись журнала не называет источником артефактную ветку: "
            f"{detail!r}")

    def test_ac10_iteration_over_one_names_the_source_and_the_base(self):
        """Итерация 2, артефакты прочитаны из артефактной ветки: запись
        журнала обязана назвать и источник, и sha базы инкремента.

        Ловит мутацию: в запись добавлен только источник артефактов, а
        база инкремента забыта (или наоборот) — ровно тот пробел,
        из-за которого дефект «diff собран не от того sha» ловится
        глазами в промпте, а не по журналу.
        """
        verdict_sha = self.seed_anchor()
        self.put_in_artifact_branch()

        detail = self.package_detail(reviewed_iter=1)

        self.assert_names_artifact_branch(detail)
        self.assertIn(verdict_sha[:7], detail,
                      "запись журнала не называет базу инкремента")

    def test_ac10_first_iteration_names_the_source_without_a_base(self):
        """Итерация 1: источник артефактов в записи есть, базы инкремента
        нет — её на первой итерации не существует.

        Ловит мутацию: база пишется в запись безусловно (например,
        подставляется merge-base полного diff) — на первой итерации в
        журнале появится sha, который базой инкремента не является, и
        assertNotIn покраснеет.
        """
        verdict_sha = self.seed_anchor()
        self.put_in_artifact_branch()

        detail = self.package_detail(reviewed_iter=0)

        self.assert_names_artifact_branch(detail)
        self.assertNotIn(verdict_sha[:7], detail,
                         "на итерации 1 базы инкремента в записи быть не "
                         "должно")

    def test_ac10_missing_artifacts_are_named_as_not_found(self):
        """Артефактов нет ни в артефактной ветке, ни в рабочем каталоге
        шага — запись журнала называет источник «не найден».

        Ловит мутацию: источник пишется в запись только когда файл
        прочитан (ветка/рабочий каталог), а отсутствие артефактов молча
        пропускается — по журналу «пакет без SPEC и PLAN» перестанет
        отличаться от «пакет с ними», и assertIn покраснеет.
        """
        self.seed_anchor()

        detail = self.package_detail(reviewed_iter=1)

        self.assertIn("не найден", detail.lower(),
                      f"запись журнала не называет источник «не найден»: "
                      f"{detail!r}")


if __name__ == "__main__":
    unittest.main()
