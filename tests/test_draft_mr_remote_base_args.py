"""Юнит-тест адреса базы сверки черновика запроса на слияние (SPEC
01M3YDHTY1Y67KB98FVSHREC4N, требование 1): fetch идёт за веткой `base`
target'а (`targets.yaml`), а не за `config.MAIN_BRANCH`, и подсчёт коммитов
сравнивает ветку с ПОЛУЧЕННЫМ sha, а не с именем ветки.

Долгоживущий файл задачи (`tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_
remote_base.py`) держит target'ы с `base: main` — там адрес из
`config.MAIN_BRANCH` и адрес из target'а совпадают и не различаются.
"""
import subprocess
import unittest
from unittest import mock

from orchestrator import config, github_adapter, workspace


class RemoteBaseAddressTest(unittest.TestCase):

    def test_fetch_follows_the_target_base_and_counts_over_its_sha(self):
        """База target'а — `develop`: fetch `origin develop`, подсчёт —
        `commits_behind(<sha головы>, <ветка>)`, ноль — пропуск без push.

        Ловит мутацию: fetch запрошен за `config.MAIN_BRANCH` вместо `base`
        target'а, либо в `commits_behind` передано имя базы вместо
        полученного sha (локальная ветка `develop` снова решает за удалённую).
        """
        fetches, counts = [], []

        def fake_fetch(remote, ref, *, repo=None):
            fetches.append((remote, ref, repo))
            return "c0ffee" * 6 + "abcd", ""

        def fake_count(branch, base=None, repo=None):
            counts.append((branch, base, repo))
            return 0

        git = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        gh = mock.Mock()
        with mock.patch.object(github_adapter.targets, "target",
                               lambda name: {"forge": "github",
                                             "base": "develop"}), \
                mock.patch.object(github_adapter.gitcmd, "fetch_ref_sha",
                                  fake_fetch), \
                mock.patch.object(github_adapter.gitcmd, "commits_behind",
                                  fake_count), \
                mock.patch.object(github_adapter.gitcmd, "git", git), \
                mock.patch.object(github_adapter.ci, "gh", gh), \
                mock.patch.object(github_adapter.store, "journal") as journal, \
                mock.patch.object(github_adapter.store, "update_task"):
            github_adapter.ensure_draft_mr(
                mock.Mock(), "T001",
                {"target": "artel", "branch": "task/t001-x", "title": "x",
                 "draft_mr_created": 0, "is_canary": 0})

        # Репозиторий — клон артели (ADR-0021 п.1, этап 2; SPEC
        # 01M42PENCS26D0656X8FR7DFA7, AC-6), не `None` (главная копия).
        clone = workspace.repo(config.DEFAULT_TARGET)
        self.assertEqual(fetches, [("origin", "develop", clone)])
        self.assertEqual(counts, [("c0ffee" * 6 + "abcd", "task/t001-x", clone)])
        git.assert_not_called()
        gh.assert_not_called()
        self.assertEqual(journal.call_args.args[3],
                         github_adapter.DRAFT_MR_SKIPPED_ACTION)
        self.assertIn("origin/develop", journal.call_args.args[4])


if __name__ == "__main__":
    unittest.main()
