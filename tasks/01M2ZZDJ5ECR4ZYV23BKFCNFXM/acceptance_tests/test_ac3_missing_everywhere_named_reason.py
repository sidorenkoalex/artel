"""AC-3 — 01M2ZZDJ5ECR4ZYV23BKFCNFXM: файла нет ни в артефактной ветке,
ни в рабочем каталоге шага — именованная строка с обеими фактическими
причинами, без абсолютного пути.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Файла нет ни в артефактной ветке, ни в рабочем каталоге шага —
часть пакета несёт именованную строку «(не показан: …)» с обеими
фактическими причинами (ветка и рабочий каталог шага); абсолютного пути
в тексте нет.

Красен до реализации: причина «в ветке — …» сегодня приходит от `git show` по КОДОВОЙ ветке задачи (`orchestrator/review.py::artifact_text`), а не по артефактной — в тексте части стоит имя кодовой ветки, которое фактической причиной по этому критерию уже не является.

Два других теста файла (форма именованной строки и отсутствие
абсолютного пути) зелены и до правки намеренно: критерий требует
СОХРАНИТЬ прежнюю именованную строку — они сторожат её от потери при
переписывании чтения артефактов.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

NAMED_RE = re.compile(r"\(не показан: в ветке — (?P<branch>[^;]+); "
                      r"в дереве — (?P<tree>[^)]+)\)")


class MissingArtifactNamesBothReasonsTest(_sandbox.ReviewPackagePlankSandbox):

    def test_ac3_part_keeps_the_named_missing_line_with_both_reasons(self):
        """SPEC.md задачи не закоммичен в артефактную ветку и не лежит в
        рабочем каталоге шага — часть пакета обязана нести прежнюю
        именованную строку «(не показан: в ветке — …; в дереве — …)» с
        непустыми причинами по обеим позициям.

        Ловит мутацию: новый код чтения артефактов возвращает голое
        `None`/пустую строку вместо именованной причины (или роняет одну
        из двух позиций) — регулярка перестанет совпадать, и ревьювер не
        отличит «PLAN не написан» от «пакет не смог его показать».
        """
        text = self.package()["text"]

        body = _sandbox.part_body(text, self.task_rel("SPEC.md"))
        self.assertTrue(body, "в пакете нет части SPEC.md")
        match = NAMED_RE.search(body)
        self.assertIsNotNone(
            match, f"часть SPEC.md не несёт именованной строки отсутствия: "
                   f"{body!r}")
        self.assertTrue(match.group("branch").strip(),
                        "причина по ветке-источнику пуста")
        self.assertTrue(match.group("tree").strip(),
                        "причина по рабочему каталогу шага пуста")

    def test_ac3_branch_reason_is_not_about_the_code_branch(self):
        """Обе причины фактические: причина «в ветке — …» относится к
        ветке-источнику артефактов, а не к кодовой ветке задачи — имени
        кодовой ветки в части пакета быть не должно.

        Ловит мутацию: чтение артефакта оставлено на кодовой ветке
        (`artifact_text(branch, rel)`) — её имя приедет в текст причины
        из stderr `git show <кодовая ветка>:<путь>`, и assertNotIn
        покраснеет.
        """
        body = _sandbox.part_body(self.package()["text"],
                                  self.task_rel("SPEC.md"))

        self.assertNotIn(
            self.BRANCH, body,
            "причина отсутствия обязана называть ветку-источник артефактов, "
            "а не кодовую ветку задачи")

    def test_ac3_no_absolute_path_leaks_into_the_part(self):
        """Причина по рабочему каталогу шага не несёт абсолютного пути:
        текст части уходит в промпт ревьювера, путь рабочей копии в нём
        ничего не значит.

        Ловит мутацию: новый откат отдаёт причиной `str(exc)`
        необработанного `FileNotFoundError`/`OSError` по абсолютному пути
        рабочего каталога шага — корень песочницы окажется в тексте
        части, и assertNotIn покраснеет.
        """
        body = _sandbox.part_body(self.package()["text"],
                                  self.task_rel("SPEC.md"))

        self.assertNotIn(str(self.root), body,
                         "абсолютного пути в тексте части быть не должно")
        self.assertNotIn(str(_sandbox.config.WORKTREES), body)


if __name__ == "__main__":
    unittest.main()
