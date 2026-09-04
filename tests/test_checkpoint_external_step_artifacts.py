"""Юнит-тесты `checkpoint._commit_external_step_artifacts` (SPEC T094,
требование 8, AC-9 — REVIEW.md итерация 1, замечание 2).

До правки `checkpoint.commit_step_artifacts` безусловно пропускала любой
target, кроме self: роль внешнего target писала `tasks/<id>/` в клон
кода целевого (`runner.role_cwd`), и ни один код не переносил эти файлы
в артефактную ветку пульта — прямое нарушение требования 8 на первом же
реальном шаге роли (не только на `cmd_new`, который уже был покрыт
`tasks/T094/acceptance_tests/test_ac9_role_step_artifact_branch.py`).

Песочница — `RealGitSandbox` (пульт — реальный git-репозиторий с main),
рабочий каталог внешнего target — обычная директория на диске (клон кода
целевого не обязан быть git-репозиторием для этой проверки: функция
читает файлы с диска, коммитит их плотницки в артефактную ветку ПУЛЬТА
и убирает исходники — ни то, ни другое не требует git внутри workspace).
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import checkpoint, config, gitcmd, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TARGET = "extproj"

QUESTIONS_MD = """---
task: x
type: questions
author_role: analyst
status: draft
---
# QUESTIONS
"""


class CommitExternalStepArtifactsTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.TASK = "01EXTTASKPREFIXSTEP01"
        conn = store.db()
        store.insert_task(conn, self.TASK, "Задача внешнего target",
                          "in_dev", f"task/{self.TASK.lower()}-x", TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.workspace_root = config.PROJECTS / TARGET / "workspace"
        self.task_dir = self.workspace_root / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def write(self, rel: str, text: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def artifact_branch_files(self) -> list[str]:
        branch = f"artifact/{self.TASK.lower()}"
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []

    def test_role_written_artifacts_land_in_the_pult_artifact_branch(self):
        self.write("PLAN.md", "---\ntask: x\n---\n# PLAN\n")

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertIn("артефактная ветка", detail)
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", self.artifact_branch_files())

    def test_committed_artifacts_are_removed_from_the_target_code_workspace(self):
        # Требование 8: кодовая ветка/рабочий каталог целевого свободны от
        # tasks/<id>/ после автокоммита — иначе следующий коммит роли
        # (`git add -A` в её собственном клоне) подхватил бы их в код.
        self.write("PLAN.md", "черновик")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        self.assertFalse(self.task_dir.exists(),
                         "tasks/<id>/ обязан быть убран из клона целевого")
        self.assertTrue(self.workspace_root.exists(),
                        "сам рабочий каталог роли не трогаем, только tasks/<id>/")

    def test_no_tasks_dir_written_is_not_an_error(self):
        # Роль на этом шаге правила только код, tasks/<id>/ не трогала.
        self.task_dir.rmdir()

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.artifact_branch_files(), [])

    def test_second_step_accumulates_onto_the_first_not_replaces_it(self):
        self.write("PLAN.md", "план разработчика")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        self.task_dir.mkdir(parents=True)
        self.write("REVIEW.md", "ревью")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "reviewer")

        branch = f"artifact/{self.TASK.lower()}"
        plan_text, _ = gitcmd.show(branch, f"tasks/{self.TASK}/PLAN.md")
        review_text, _ = gitcmd.show(branch, f"tasks/{self.TASK}/REVIEW.md")
        self.assertEqual(plan_text, "план разработчика")
        self.assertEqual(review_text, "ревью")

    def test_same_role_second_step_drops_a_file_it_no_longer_writes(self):
        """SPEC 01M1KT0792125J9ZNJNZJ86E9Q, требование 4/AC-6: файл,
        который сама РОЛЬ больше не пишет на своём следующем шаге,
        обязан пропасть из артефактной ветки — не путать с файлом ДРУГОЙ
        роли (тест выше), который переживает чужой автокоммит."""
        self.write("QUESTIONS.md", QUESTIONS_MD)
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "analyst")
        self.assertIn(f"tasks/{self.TASK}/QUESTIONS.md",
                      self.artifact_branch_files())

        self.task_dir.mkdir(parents=True)
        self.write("SPEC.md", "спека готова")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "analyst")

        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/SPEC.md", files)
        self.assertNotIn(f"tasks/{self.TASK}/QUESTIONS.md", files)

    def test_same_role_deletion_does_not_remove_another_roles_file(self):
        """Регресс-контроль симметрии для предыдущего теста: удаление,
        обнаруженное для РОЛИ analyst, не имеет права задеть файл,
        последний раз тронутый ДРУГОЙ ролью (developer) — иначе фикс
        AC-6 стал бы той же поломкой, что и `test_second_step_
        accumulates_onto_the_first_not_replaces_it` ловит для обычного
        случая."""
        self.write("PLAN.md", "план разработчика")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        self.task_dir.mkdir(parents=True)
        self.write("QUESTIONS.md", QUESTIONS_MD)
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "analyst")

        self.task_dir.mkdir(parents=True)
        self.write("SPEC.md", "спека готова")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "analyst")

        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/SPEC.md", files)
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", files,
                      "файл чужой роли не должен пострадать от удаления, "
                      "обнаруженного для другой роли")
        self.assertNotIn(f"tasks/{self.TASK}/QUESTIONS.md", files)

    def test_same_role_second_step_in_the_same_state_does_not_drop_an_untouched_file(self):
        """REVIEW.md итерация 1, замечание R1-F1: та же роль (developer),
        второй шаг В ТОМ ЖЕ состоянии (auto-цикл `in_dev`/`reject` из
        `acceptance`) — файл предыдущего шага (PLAN.md, `type: plan`) НЕ
        переписан на этом шаге, но роль пишет ДРУГОЙ файл в тот же
        `task_dir` (например, разметку `REVIEW.md` по правилу «Реестр
        замечаний»). «Последний коммит пути — автокоммит этой же роли»
        совпадает 1-в-1 с легитимным сценарием QUESTIONS.md (тест выше)
        — единственное, что их различает, это `type` фронтматтера:
        PLAN.md не должен исчезнуть, потому что его тип не в списке
        удаляемых, даже когда роль в это раз его не переписала.

        Ловит мутацию: снятие второго условия («последний коммит пути
        — автокоммит той же роли» без проверки `type` кандидата ∈
        `_DELETABLE_ARTIFACT_TYPES`) — тогда PLAN.md пропадает из
        артефактной ветки на этом шаге."""
        self.write("PLAN.md", "---\ntask: x\ntype: plan\n---\n# PLAN\n")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        self.task_dir.mkdir(parents=True)
        self.write("REVIEW.md", "---\ntask: x\ntype: review\n---\n# REVIEW\n")
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/REVIEW.md", files)
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", files,
                      "файл, не переписанный на повторном шаге ТОЙ ЖЕ "
                      "роли в ТОМ ЖЕ состоянии, не должен молча исчезать")

    def test_binary_file_is_not_lost(self):
        # REVIEW.md T094 итерация 2, замечание 1 (major): раньше
        # `read_text(encoding="utf-8")` молча пропускал файл, не проходящий
        # UTF-8-декодирование, а `shutil.rmtree` затем удалял его с диска
        # без следа и без сигнала об этом — ни в артефактной ветке, ни на
        # диске. Здесь смесь текстового и бинарного файла: оба обязаны
        # попасть в артефактную ветку, ничего не должно потеряться.
        self.write("PLAN.md", "план разработчика")
        binary = bytes(range(256)) + b"\x89PNG\r\n\x1a\n"
        (self.task_dir / "screenshot.png").write_bytes(binary)

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertIn("артефактная ветка", detail)
        committed = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", committed)
        self.assertIn(f"tasks/{self.TASK}/screenshot.png", committed)
        self.assertFalse(self.task_dir.exists())
        cat = subprocess.run(
            ["git", "show", f"artifact/{self.TASK.lower()}:"
             f"tasks/{self.TASK}/screenshot.png"],
            cwd=config.ROOT, capture_output=True)
        self.assertEqual(cat.returncode, 0)
        self.assertEqual(cat.stdout, binary)

    def test_all_files_binary_still_commits_and_clears_the_dir(self):
        # Второй, менее острый случай того же замечания: если ВСЕ файлы
        # каталога не текстовые, `files` раньше оставался пустым и функция
        # возвращала "" ДО rmtree — данные не терялись физически, но и не
        # коммитились НИКОГДА (перманентное нарушение требования 8 для
        # такого содержимого). Теперь бинарные файлы коммитятся как любые
        # другие.
        self.task_dir.rmdir()
        self.task_dir.mkdir()
        (self.task_dir / "blob.bin").write_bytes(b"\x00\x01\xff\xfe")

        detail = checkpoint.commit_step_artifacts(store.db(), self.TASK,
                                                   "developer")

        self.assertIn("артефактная ветка", detail)
        self.assertIn(f"tasks/{self.TASK}/blob.bin", self.artifact_branch_files())
        self.assertFalse(self.task_dir.exists())

    def test_journal_records_the_autocommit(self):
        self.write("PLAN.md", "черновик")

        checkpoint.commit_step_artifacts(store.db(), self.TASK, "developer")

        details = [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, "автокоммит артефактов шага (артефактная ветка)"))]
        self.assertTrue(details)
        self.assertIn(self.TASK, details[-1])


if __name__ == "__main__":
    unittest.main()
