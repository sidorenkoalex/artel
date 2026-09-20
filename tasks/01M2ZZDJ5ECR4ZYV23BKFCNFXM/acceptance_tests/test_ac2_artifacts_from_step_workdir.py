"""AC-2 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: откат на каталог `tasks/<id>/`
РАБОЧЕГО КАТАЛОГА ШАГА, названный отдельным источником.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. Тех же файлов нет в артефактной ветке, но они есть в каталоге
`tasks/<id>/` рабочего каталога шага — пакет несёт их тела, а заголовок
части называет источником рабочий каталог, отличая его от артефактной
ветки.

Красен до реализации: откат сборщика сегодня смотрит в ГЛАВНУЮ копию
пульта (`orchestrator/review.py::artifact_text` — `config.ROOT / rel`),
а не в рабочий каталог шага (`config.WORKTREES/<id>` для self-target) —
файл, лежащий только там, в пакет не попадает вовсе, и часть несёт
«(не показан: …)».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402


class StepWorkdirFallbackTest(_sandbox.ReviewPackagePlankSandbox):

    def test_ac2_bodies_come_from_the_step_workdir_when_the_branch_has_none(self):
        """Артефактов в артефактной ветке нет; те же файлы лежат в
        `tasks/<id>/` рабочего каталога шага — пакет обязан нести их
        тела, а не строку «(не показан: …)».

        Ловит мутацию: откат оставлен на главную копию пульта
        (`config.ROOT / rel`) — файл рабочего каталога шага не прочитан,
        и часть пакета объявит артефакт непоказанным.
        """
        self.put_in_step_workdir()

        text = self.package()["text"]

        self.assertIn(_sandbox.SPEC_BODY, text, "тело SPEC.md рабочего каталога")
        self.assertIn(_sandbox.PLAN_BODY, text, "тело PLAN.md рабочего каталога")
        self.assertIn(_sandbox.REVIEW_BODY, text,
                      "тело REVIEW.md рабочего каталога")
        for name in _sandbox.ARTIFACT_NAMES:
            self.assertNotIn(
                "не показан", _sandbox.part_body(text, self.task_rel(name)),
                f"{name} лежит в рабочем каталоге шага — часть пакета не "
                f"вправе объявлять его непоказанным")

    def test_ac2_header_names_the_workdir_apart_from_the_artifact_branch(self):
        """Один и тот же байт-в-байт текст SPEC.md показан дважды: сперва
        из артефактной ветки, затем (после удаления из неё) из рабочего
        каталога шага. Размер и sha256 в обоих заголовках совпадают —
        значит различить их может только названный источник, и заголовки
        обязаны отличаться.

        Ловит мутацию: откат на рабочий каталог шага сделан молча, без
        пометки об источнике (возврат пустой `note`, как у ветки) — оба
        заголовка станут одинаковыми, и assertNotEqual покраснеет.
        """
        spec_rel = self.task_rel("SPEC.md")
        self.put_in_artifact_branch()
        from_branch = _sandbox.part_header(self.package()["text"], spec_rel)
        self.assertTrue(from_branch, "части SPEC.md нет в пакете из ветки")

        self.drop_from_artifact_branch()
        self.put_in_step_workdir()
        from_workdir = _sandbox.part_header(self.package()["text"], spec_rel)

        self.assertTrue(from_workdir,
                        "части SPEC.md нет в пакете из рабочего каталога")
        self.assertNotIn("не показан", from_workdir)
        self.assertNotEqual(
            from_branch, from_workdir,
            "заголовок части обязан называть источник — рабочий каталог "
            "шага должен отличаться от артефактной ветки (текст файла, а "
            "значит размер и sha256, в обоих случаях один и тот же)")

    def test_ac2_pult_copy_is_not_the_step_workdir(self):
        """Файлов нет ни в артефактной ветке, ни в рабочем каталоге шага,
        но они есть в главной копии пульта (`config.TASKS/<id>/`) —
        источником она быть перестала, тела в пакет не идут.

        Ловит мутацию: откат оставлен на `config.ROOT`/`config.TASKS`
        вместо рабочего каталога шага — тела найдутся в главной копии, и
        assertNotIn покраснеет.
        """
        self.put_in_pult_copy()

        text = self.package()["text"]

        self.assertNotIn(_sandbox.SPEC_BODY, text,
                         "главная копия пульта источником артефактов пакета "
                         "больше не является")
        self.assertNotIn(_sandbox.PLAN_BODY, text)


if __name__ == "__main__":
    unittest.main()
