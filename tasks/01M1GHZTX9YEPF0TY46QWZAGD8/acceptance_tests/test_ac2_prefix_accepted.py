"""Приёмочный тест 01M1GHZTX9YEPF0TY46QWZAGD8 — AC-2
(tasks/01M1GHZTX9YEPF0TY46QWZAGD8/SPEC.md, «Критерии приёмки»).

AC-2: «approve <id> <первые 8+ символов зафиксированного sha> проходит
так же, как с полным sha.»

Красен до реализации: сегодня `fsm.confirm_fixation` сравнивает
переданный `sha` с зафиксированным `current` СТРОГО на равенство строк
(`sha != current`) — восьмисимвольный префикс `current` заведомо не
равен 40-символьному `current` целиком, поэтому approve с префиксом
отклоняется тем же `sys.exit`'ом, что и approve с произвольно неверным
значением, вместо перехода. Тест ниже падает на этом отказе (переход
не случается / вылетает необработанное исключение).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class Ac2PrefixAcceptedTest(RealPultGitTest):

    def test_ac2_eight_char_prefix_of_fixed_sha_passes_like_full_sha(self):
        """approve с первыми 8 символами зафиксированного sha переводит
        задачу так же, как approve с полным sha (`spec_gate -> in_dev`).

        Ловит мутацию: если реализация продолжит требовать полного
        совпадения `sha == current` (не срезая `current` до длины
        переданного префикса перед сравнением), approve с 8-символьным
        префиксом отклонится `sys.exit`'ом вместо перехода в `in_dev`.
        """
        sha = self.enter_spec_gate()
        prefix = sha[:8]
        self.assertNotEqual(prefix, sha, "предпосылка теста: префикс короче")

        self.capture(fsm.cmd_approve, self.TASK, prefix)

        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "in_dev",
            "approve с уникальным 8-символьным префиксом обязан пройти "
            "так же, как approve с полным зафиксированным sha")


if __name__ == "__main__":
    unittest.main()
