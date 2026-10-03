"""Узел чтения документов задачи в `artifact_branch` (ADR-0021 п.3; SPEC
01M409YNSWACNFKNJE2X263ZSD, ANSWER-1 п.1): читатели (бриф, ревью-пакет,
гейты, автокоммит шага, `amend-tests`, `answer`) называют задачу, а
репозиторий выбирает узел — git главной копии пульта для артели, клон
проекта для внешней задачи. Запись уже покрыта долгоживущим файлом задачи
(`tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py`); здесь —
чтение.

Песочница — `RealGitSandbox` (пульт — настоящий git) и клон внешнего
проекта `make_project_repo`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, config, gitcmd, review, store  # noqa: E402
from tests.sandbox import RealGitSandbox, make_project_repo  # noqa: E402

TARGET = "extproj"
EXTERNAL = "01READNODEEXTERNAL0001"
ARTEL = "01READNODEARTEL0000001"


class ReadNodeSandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.insert_task(conn, EXTERNAL, "Внешняя задача", "in_dev",
                          f"task/{EXTERNAL.lower()}-x", TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.insert_task(conn, ARTEL, "Задача артели", "in_dev",
                          f"task/{ARTEL.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def pult_ref_with(self, task_id: str, rel: str, text: str) -> str:
        """Ссылка `refs/artifacts/<id>` в git ПУЛЬТА мимо узла записи —
        как остаток прежнего устройства."""
        sha = artifact_branch.write_commit(
            config.ROOT, {rel: text}, "в пульте", "t", "t@t.invalid")
        self.assertTrue(sha)
        self.git("update-ref", artifact_branch.branch_name(task_id), sha)
        return sha


class ExternalTaskReadsProjectRepoTest(ReadNodeSandbox):

    def setUp(self):
        super().setUp()
        self.project = make_project_repo(TARGET)
        self.rel = f"tasks/{EXTERNAL}/SPEC.md"
        self.sha = artifact_branch.commit_files(
            EXTERNAL, {self.rel: "спека проекта\n"}, "спека")
        self.assertTrue(self.sha)
        self.ref = artifact_branch.branch_name(EXTERNAL)

    def test_show_ls_tree_and_sha_come_from_the_project_clone(self):
        """Ловит мутацию: узел чтения спрашивает git пульта (вызов
        `gitcmd` без `repo=` клона) — ссылки там нет, `show` вернёт
        `None`, `ls_tree` — пусто, `rev_sha` — пустую строку."""
        text, reason = artifact_branch.show(EXTERNAL, self.ref, self.rel)
        self.assertEqual(text, "спека проекта\n", reason)
        self.assertEqual(artifact_branch.ls_tree(EXTERNAL, self.ref,
                                                 f"tasks/{EXTERNAL}"),
                         [self.rel])
        self.assertEqual(artifact_branch.rev_sha(EXTERNAL, self.ref), self.sha)
        self.assertEqual(gitcmd.branch_head_sha(self.ref, repo=self.project),
                         self.sha)
        self.assertTrue(artifact_branch.on_foreign_rev(EXTERNAL, self.ref))

    def test_pult_copy_of_the_ref_is_not_read(self):
        """Ловит мутацию: узел читает git пульта первым (или откатывается
        на него) — вернул бы текст ссылки пульта вместо текста проекта."""
        self.pult_ref_with(EXTERNAL, self.rel, "чужая копия в пульте\n")

        text, _ = artifact_branch.show(EXTERNAL, self.ref, self.rel)

        self.assertEqual(text, "спека проекта\n")

    def test_review_package_text_reads_the_project_clone(self):
        """Ловит мутацию: `review.artifact_text` с `task_id` читает
        `git show` в пульте — ссылки там нет, текст ушёл бы в откат на диск
        (файла там нет) и компонент пакета оказался бы «не показан»."""
        text, note = review.artifact_text(self.ref, self.rel,
                                          disk_root=self.root / "нет",
                                          task_id=EXTERNAL)

        self.assertEqual(text, "спека проекта\n", note)
        self.assertEqual(note, "")


class ExternalTaskWithoutCloneTest(ReadNodeSandbox):

    def test_no_clone_reads_nothing_even_if_the_pult_has_the_ref(self):
        """Ловит мутацию: без клона проекта узел уходит в git пульта
        (`git -C` в каталоге без `.git` поднимается к `config.ROOT`, либо
        откат на пульт) — прочитал бы ссылку пульта, второй источник
        истины против ADR-0021 п.1."""
        ref = artifact_branch.branch_name(EXTERNAL)
        rel = f"tasks/{EXTERNAL}/SPEC.md"
        self.pult_ref_with(EXTERNAL, rel, "чужая копия в пульте\n")
        # Каталог клона есть, но git в нём нет (`runner.role_cwd` заводит
        # его `mkdir`).
        (config.PROJECTS / TARGET / "workspace").mkdir(parents=True)
        config.TARGETS.write_text(
            "targets:\n"
            f"  {TARGET}:\n"
            "    forge: github\n"
            f"    url: file:///nonexistent/{TARGET}\n"
            f"    base: {config.MAIN_BRANCH}\n"
            f"    token_slot: {TARGET}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n", encoding="utf-8")

        text, reason = artifact_branch.show(EXTERNAL, ref, rel)

        self.assertIsNone(text)
        self.assertEqual(reason, artifact_branch.NO_REPO_REASON)
        self.assertIsNone(artifact_branch.ls_tree(EXTERNAL, ref,
                                                  f"tasks/{EXTERNAL}"))
        self.assertEqual(artifact_branch.rev_sha(EXTERNAL, ref), "")
        self.assertFalse(artifact_branch.on_foreign_rev(EXTERNAL, ref))


class ArtelTaskReadsPultRepoTest(ReadNodeSandbox):

    def test_artel_reads_the_pult_git(self):
        """Ловит мутацию: узел для задачи артели не идёт в git главной
        копии пульта (`repo_for_target` отдаёт `_NO_REPO`) — текст ссылки
        пульта не прочитан, sha пуст."""
        rel = f"tasks/{ARTEL}/SPEC.md"
        sha = artifact_branch.commit_files(ARTEL, {rel: "спека артели\n"},
                                           "спека")
        self.assertTrue(sha)
        ref = artifact_branch.branch_name(ARTEL)

        text, reason = artifact_branch.show(ARTEL, ref, rel)

        self.assertEqual(text, "спека артели\n", reason)
        self.assertEqual(artifact_branch.rev_sha(ARTEL, ref), sha)
        self.assertEqual(gitcmd.branch_head_sha(ref), sha)


if __name__ == "__main__":
    unittest.main()
