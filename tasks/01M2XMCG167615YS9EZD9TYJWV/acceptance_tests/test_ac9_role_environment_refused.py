"""Приёмочный тест AC-9 задачи 01M2XMCG167615YS9EZD9TYJWV: вызов из
окружения роли (`runner.in_role_environment` истинна) отказывает ДО
любой работы с репозиторием — коммита в origin нет, рабочий репозиторий
`.artel/notes-work` даже не заводится.

Красен до реализации: команды `doc-commit` в диспетчере `artel.py` ещё
нет — отказ приходит от диспетчера («Неизвестная команда»), и
`assert_refused` красен на этом маркере, а не на рубеже окружения роли.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, runner  # noqa: E402
from _sandbox import DOC_REL, ROADMAP_TEXT, DocCommitSandbox  # noqa: E402


class RoleEnvironmentRefusedTest(DocCommitSandbox):

    def test_ac9_call_from_role_environment_refuses_before_touching_repo(self):
        """Процессу подставлены оба маркера окружения роли (`HOME` и
        `CLAUDE_CONFIG_DIR` на курируемый слой) — те же, что читает
        `runner.in_role_environment`: вызов отказывает, origin не
        сдвигается, а `.artel/notes-work` остаётся незаведённым — до
        репозитория команда не доходит.

        Ловит мутацию: рубеж окружения роли поставлен не первым
        действием, а после `_ensure_work_repo()`/fetch (по образцу
        переносимой механики `note`) — отказ всё ещё случается, но
        рабочий репозиторий уже создан, и тест красен на существующем
        `.artel/notes-work`.
        """
        source = self.source_file("# Роадмап\n\nправка из-под роли\n")
        before = self.origin_head()
        role_env = {"HOME": str(config.ROLE_HOME),
                    "CLAUDE_CONFIG_DIR": str(config.ROLE_CONFIG_DIR)}

        with mock.patch.dict(os.environ, role_env):
            self.assertTrue(runner.in_role_environment(),
                            "предусловие: маркеры окружения роли выставлены")
            self.assert_refused(["doc-commit", DOC_REL, "--from", str(source),
                                 "--message", "правка из-под роли"])

        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_show(DOC_REL), ROADMAP_TEXT)
        self.assertFalse(self.work_repo_dir().exists(),
                         "рабочий репозиторий заведён до отказа")


if __name__ == "__main__":
    unittest.main()
