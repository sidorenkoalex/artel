"""AC-6 (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md): «Коммит правки
формирует сама команда стандартным сообщением, включающим основание
(--reason); ссылка на ADR в сообщении коммита не требуется.»

Красен до реализации: `_sandbox.discover_amend_command_name()` падает
`AssertionError` — новой команды правки планки в таблице диспетчера ещё
нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AC_TEST_AMENDED_V1, AmendSandbox  # noqa: E402


class CommitMessageTest(AmendSandbox):

    def test_ac6_commit_message_includes_the_passed_reason(self):
        """После успешной правки последний коммит на ветке задачи обязан
        нести переданное основание в своём сообщении — коммит формирует
        сама команда, не Оператор вручную.

        Ловит мутацию: команда коммитит правку статическим шаблоном
        («amend: acceptance_tests») без подстановки `--reason` —
        основание передано, но нигде не видно в истории git.
        """
        self.enter_in_dev()
        self.write_acceptance_tests(AC_TEST_AMENDED_V1)
        reason = "устранён конфликт форматирования с линтером (ADR-0012 п.1а)"

        self.run_amend(reason=reason)

        message = self.git_wt("log", "-1", "--format=%B")
        self.assertIn(
            reason, message,
            f"сообщение последнего коммита не содержит основание "
            f"«{reason}»: {message!r}")


if __name__ == "__main__":
    unittest.main()
