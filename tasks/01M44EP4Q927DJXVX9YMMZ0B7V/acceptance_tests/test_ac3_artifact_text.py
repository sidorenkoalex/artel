"""AC-3: `artifact_text(name)` читает ревизию выкладки ссылки документов.

После нового коммита в ссылку помощник по-прежнему отдаёт текст ревизии
выкладки; файла в этой ревизии нет — `None`; сбой git (недоступный
репозиторий ссылки) — исключение `ArtifactReadError`, не `None`.

Группа: разовый
Красен до реализации: выкладка не кладёт `_pult.py` — помощника, а с ним `artifact_text` и `ArtifactReadError`, нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _scenario import SPEC_TEXT, PlankHelperSandbox  # noqa: E402

PLAN_V1 = "---\ntype: plan\n---\n# PLAN ревизии выкладки\n"
PLAN_V2 = "---\ntype: plan\n---\n# PLAN после выкладки\n"


class ArtifactTextTest(PlankHelperSandbox):

    def setUp(self):
        super().setUp()
        self.commit_to_ref({"PLAN.md": PLAN_V1}, "PLAN v1")
        self.helper = self.materialize()

    def test_ac3_reads_materialized_revision_not_ref_head(self):
        """Новый коммит в ссылку не меняет ответ помощника.

        Сценарий: планка выложена при PLAN.md = v1; затем в ссылку
        коммитится PLAN.md = v2. `artifact_text("PLAN.md")` отдаёт v1,
        `artifact_text("SPEC.md")` — SPEC ревизии выкладки.

        Ловит мутацию: помощник читает голову ссылки по имени
        (`refs/artifacts/<id>:…`), а не подставленный sha — после нового
        коммита он отдаёт v2."""
        self.commit_to_ref({"PLAN.md": PLAN_V2}, "PLAN v2")

        self.assertEqual(self.helper.artifact_text("PLAN.md"), PLAN_V1)
        self.assertEqual(self.helper.artifact_text("SPEC.md"), SPEC_TEXT)

    def test_ac3_missing_file_is_none(self):
        """Файла в ревизии выкладки нет — `None`.

        Сценарий: `REVIEW.md` нет нигде; `QUESTIONS.md` появляется в ссылке
        только после выкладки. Для обоих `artifact_text` отдаёт `None`.

        Ловит мутацию: «файла нет» поднимает `ArtifactReadError` (любой
        ненулевой код git — сбой) либо отдаёт пустую строку — вместо
        `None` исключение или `""`."""
        self.commit_to_ref({"QUESTIONS.md": "# вопросы после выкладки\n"},
                           "QUESTIONS")

        self.assertIsNone(self.helper.artifact_text("REVIEW.md"))
        self.assertIsNone(self.helper.artifact_text("QUESTIONS.md"))

    def test_ac3_git_failure_raises_artifact_read_error(self):
        """Недоступный репозиторий ссылки — `ArtifactReadError`, не `None`.

        Сценарий: после выкладки каталог `.git` репозитория ссылки
        документов убран (возвращается на место по окончании теста);
        `artifact_text("SPEC.md")` поднимает `ArtifactReadError`
        помощника.

        Ловит мутацию: любой ненулевой код git трактуется как «файла
        нет» — помощник отдаёт `None`, и планка молча принимает сбой git за
        отсутствие артефакта."""
        error_type = getattr(self.helper, "ArtifactReadError", None)
        self.assertTrue(isinstance(error_type, type)
                        and issubclass(error_type, Exception),
                        "ArtifactReadError нет в выложенном помощнике")
        git_dir = self.task_repo().resolve() / ".git"
        away = git_dir.with_name(".git-away-ac3")
        git_dir.rename(away)
        self.addCleanup(away.rename, git_dir)

        with self.assertRaises(error_type):
            self.helper.artifact_text("SPEC.md")


if __name__ == "__main__":
    unittest.main()
