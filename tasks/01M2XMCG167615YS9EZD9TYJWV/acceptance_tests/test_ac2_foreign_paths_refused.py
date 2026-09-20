"""Приёмочный тест AC-2 задачи 01M2XMCG167615YS9EZD9TYJWV: путь вне
`docs/**` и вне `roles.yaml`/`gates.yaml`/`targets.yaml` (код, тесты,
скилы, шаблоны, `tasks/`) — именованный отказ, без коммита в origin и
без удержанной записи.

Красен до реализации: команды `doc-commit` в диспетчере `artel.py` ещё
нет — отказ приходит от диспетчера («Неизвестная команда»), а не от
команды, и `assert_refused` красен именно на этом маркере, не на
отсутствии коммита.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import DocCommitSandbox  # noqa: E402

REFUSAL = "код и артефакты меняются задачами, не doc-commit"

FOREIGN_PATHS = (
    "orchestrator/notes.py",
    "tests/test_notes.py",
    "skills/test-authoring.md",
    "templates/SPEC.md",
    "tasks/01M2XMCG167615YS9EZD9TYJWV/SPEC.md",
)


class ForeignPathsRefusedTest(DocCommitSandbox):

    def test_ac2_code_and_artifact_paths_refused_without_commit_or_hold(self):
        """Пять путей разных видов (код, тест, скил, шаблон, артефакт
        задачи) по очереди: каждый — отказ с формулировкой критерия,
        origin на месте, `.artel/notes-pending/` пуст.

        Ловит мутацию: список допустимых путей проверяется «от
        противного» — отказываются только пути, начинающиеся с
        `orchestrator/`, а всё остальное (скилы, шаблоны, `tasks/`)
        проходит — тест красен на первом же непокрытом пути:
        отказа нет, origin сдвинулся.
        """
        source = self.source_file("любое содержимое\n")
        before = self.origin_head()

        # Без `subTest`: его падение pytest показывает отдельной записью,
        # а сам тестовый метод при этом считает пройденным — сводка гейта
        # прочитала бы такой AC как зелёный.
        for rel in FOREIGN_PATHS:
            self.assert_refused(
                ["doc-commit", rel, "--from", str(source),
                 "--message", "правка мимо задачи"],
                REFUSAL)
            self.assertEqual(before, self.origin_head(), rel)
            self.assertEqual(self.pending_files(), [], rel)


if __name__ == "__main__":
    unittest.main()
