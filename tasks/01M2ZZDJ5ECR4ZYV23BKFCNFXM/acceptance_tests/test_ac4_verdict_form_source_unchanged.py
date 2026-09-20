"""AC-4 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: часть «форма вердикта» не меняет
ни источник, ни текст.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Часть «форма вердикта» попадает в пакет тем же источником и тем
же текстом, что до задачи.

Зелёный с рождения: критерий закрепляет СУЩЕСТВУЮЩЕЕ поведение —
`templates/REVIEW.md` читается сборщиком с кодовой ветки задачи
(`orchestrator/review.py::review_package`, `form_rel`), и эта задача
источник части не трогает; тест обязан быть зелёным и до, и после
правки, а покраснеть — ровно тогда, когда разработчик заодно переведёт
форму вердикта на резолвер артефактов задачи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

FORM_LABEL = "templates/REVIEW.md"
OTHER_FORM_BODY = "МАРКЕР-ЧУЖОЙ-ФОРМЫ-ИЗ-АРТЕФАКТНОЙ-ВЕТКИ"
OTHER_FORM_TEXT = f"---\ntype: review\n---\n\n# REVIEW\n\n{OTHER_FORM_BODY}\n"


class VerdictFormSourceTest(_sandbox.ReviewPackagePlankSandbox):

    def test_ac4_form_comes_from_the_same_source_as_before(self):
        """Артефактная ветка задачи несёт СВОЙ `templates/REVIEW.md` с
        другим текстом, кодовая — прежний: часть «форма вердикта» обязана
        показать текст кодовой ветки, то есть тот же источник, что и до
        задачи.

        Ловит мутацию: разработчик заводит один резолвер источника на все
        части пакета и уводит форму вердикта на артефактную ветку вместе
        со SPEC/PLAN/REVIEW — в пакет уйдёт чужой текст формы, и обе
        проверки покраснеют.
        """
        self.commit_files(self.artifact_branch,
                          {FORM_LABEL: OTHER_FORM_TEXT},
                          "своя форма вердикта в артефактной ветке")
        self.put_in_artifact_branch()

        text = self.package()["text"]

        self.assertIn(_sandbox.FORM_BODY, text,
                      "форма вердикта читается с кодовой ветки задачи")
        self.assertNotIn(OTHER_FORM_BODY, text,
                         "источник формы вердикта этой задачей не меняется")

    def test_ac4_form_part_keeps_its_label_and_full_text(self):
        """Часть формы вердикта остаётся именованной («форма вердикта») и
        несёт текст шаблона целиком, а не выдержку из него.

        Ловит мутацию: часть формы вклеена в пакет новым кодом чтения
        артефактов, потерявшим суффикс метки `(форма вердикта)` — по
        заголовку ревьювер перестанет отличать шаблон вердикта от
        прошлого REVIEW.md задачи, и assertIn покраснеет.
        """
        text = self.package()["text"]

        header = _sandbox.part_header(text, FORM_LABEL)
        self.assertIn("форма вердикта", header,
                      f"часть формы вердикта не названа: {header!r}")
        body = _sandbox.part_body(text, FORM_LABEL)
        self.assertIn(_sandbox.FORM_TEXT.strip(), body,
                      "текст шаблона вердикта обязан идти целиком")


if __name__ == "__main__":
    unittest.main()
