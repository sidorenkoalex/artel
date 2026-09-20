"""AC-1 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: артефакты задачи в пакете берутся
из её АРТЕФАКТНОЙ ветки.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. SPEC.md, PLAN.md и REVIEW.md задачи есть в её артефактной ветке и
отсутствуют в кодовой — собранный ревью-пакет несёт тела всех трёх
(заголовок части с размером и sha256), а не строку «(не показан: …)».

Красен до реализации: сборщик читает три артефакта из КОДОВОЙ ветки
(`orchestrator/review.py::review_package` — `artifact_text(branch, rel)`),
в которой их по условию критерия нет, а откат смотрит в главную копию
пульта — обе части сегодня отвечают «(не показан: …)», тела маркеров
SPEC/PLAN/REVIEW в пакет не попадают.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

HEADER_RE = r" — \d+ байт, sha256=[0-9a-f]{8,}"


class ArtifactBranchIsTheSourceTest(_sandbox.ReviewPackagePlankSandbox):

    def test_ac1_bodies_of_all_three_artifacts_come_from_the_artifact_branch(self):
        """Три артефакта закоммичены только в артефактную ветку задачи;
        кодовая ветка их не несёт — пакет обязан нести тела всех трёх, а
        не строку «(не показан: …)».

        Ловит мутацию: чтение артефактов оставлено на кодовой ветке
        (`artifact_text(branch, rel)`) — тела маркеров в пакет не попадут,
        вместо них встанет «(не показан: …)», и все три assertIn упадут.
        """
        self.put_in_artifact_branch()

        text = self.package()["text"]

        self.assertIn(_sandbox.SPEC_BODY, text, "тело SPEC.md из ветки")
        self.assertIn(_sandbox.PLAN_BODY, text, "тело PLAN.md из ветки")
        self.assertIn(_sandbox.REVIEW_BODY, text, "тело REVIEW.md из ветки")
        for name in _sandbox.ARTIFACT_NAMES:
            self.assertNotIn(
                "не показан", _sandbox.part_body(text, self.task_rel(name)),
                f"{name} есть в артефактной ветке — часть пакета не вправе "
                f"объявлять его непоказанным")

    def test_ac1_each_artifact_header_carries_size_and_sha256(self):
        """Заголовок каждой из трёх частей несёт размер в байтах и
        sha256 — тем же приёмом, что и до задачи.

        Ловит мутацию: тело артефакта вклеено в пакет мимо
        `artifact_part` (например, отдельной f-строкой нового кода
        чтения) — заголовок останется без «N байт, sha256=…», и
        assertRegex покраснеет.
        """
        self.put_in_artifact_branch()

        text = self.package()["text"]

        for name in _sandbox.ARTIFACT_NAMES:
            header = _sandbox.part_header(text, self.task_rel(name))
            self.assertTrue(header, f"в пакете нет части {name}")
            self.assertRegex(header, HEADER_RE,
                             f"заголовок части {name} без размера и sha256")

    def test_ac1_code_branch_copy_is_not_the_source(self):
        """Артефакты лежат и в артефактной, и в кодовой ветке, но с
        РАЗНЫМ содержимым (в кодовой — устаревший текст): пакет обязан
        показать версию артефактной ветки.

        Ловит мутацию: резолвер источника оставлен на кодовой ветке либо
        порядок источников перевёрнут (сначала кодовая, при промахе
        артефактная) — в пакет уйдёт устаревший текст, и assertNotIn
        покраснеет.
        """
        self.commit_files(
            self.BRANCH,
            {self.task_rel(n): f"# УСТАРЕВШАЯ-КОПИЯ-{n}\n"
             for n in _sandbox.ARTIFACT_NAMES},
            "устаревшие артефакты в кодовой ветке")
        self.put_in_artifact_branch()

        text = self.package()["text"]

        self.assertIn(_sandbox.SPEC_BODY, text)
        self.assertNotIn("УСТАРЕВШАЯ-КОПИЯ", text,
                         "источник трёх артефактов — артефактная ветка, "
                         "не кодовая ветка задачи")


if __name__ == "__main__":
    unittest.main()
