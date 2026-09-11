"""Приёмочный тест AC-14 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-14: путь клона репозиторного контекста для target ≠ self буквально
совпадает с адресом, который уже использует `snapshot.publish_and_
cleanup` (`.artel/projects/<target>/workspace`) — эта задача не вводит
для того же target второй/иной путь клона.

Сверяется НАПРЯМУЮ с `orchestrator.snapshot._target_workspace` (сама
функция, не переписанный литерал `config.PROJECTS / target /
"workspace"`) — совпадение с копией той же строки ничего не доказывает
про то, что это ОДИН И ТОТ ЖЕ путь, каким пользуется реальный снапшот
закрытия; расхождение с самой функцией снапшота — ровно то расхождение,
которое требование 13 SPEC (материалы) запрещает.

Красен до реализации: `orchestrator.repo_context` не существует.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, snapshot  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import EXTERNAL_TARGET, ExternalTargetGitSandbox  # noqa: E402


class ClonePathMatchesSnapshotTest(ExternalTargetGitSandbox):

    def test_ac14_repo_context_path_equals_snapshot_target_workspace(self):
        """`repo_context.resolve(target).path` — буквально тот же путь,
        что и `snapshot._target_workspace(target)`.

        Ловит мутацию: реализация заводит СВОЙ путь для клона (например,
        `.artel/projects/<target>/code` вместо `workspace`) — `assertEqual`
        с ЖИВОЙ функцией снапшота, не с переписанной строкой, это поймает.
        """
        from orchestrator import repo_context

        ctx = repo_context.resolve(EXTERNAL_TARGET)

        self.assertEqual(Path(ctx.path),
                         snapshot._target_workspace(EXTERNAL_TARGET))
        self.assertEqual(Path(ctx.path), self.target_workspace)


if __name__ == "__main__":
    import unittest
    unittest.main()
