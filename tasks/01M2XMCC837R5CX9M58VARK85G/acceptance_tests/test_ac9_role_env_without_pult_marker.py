"""AC-9: окружение роли (`runner.role_env`) маркер пульта не несёт — даже
когда `ARTEL_PULT_GIT` выставлен в окружении процесса пульта.

Зелёный с рождения: белый список `stack.ROLE_ENV_ALLOWLIST` уже сегодня отсекает любую переменную вне манифеста — тест сторожит, чтобы реализация задачи не завела маркер в этот список и не обошла фильтр.
"""
import os
import subprocess
import unittest
from unittest import mock

from orchestrator import runner, stack
from tests.sandbox import TmpRootTest

from _hooks import MARKER_ENV, MARKER_VALUE


def fake_git_config(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git`: отвечает на `config --get user.*`, иначе молчит —
    тот же приём, что у `tests/test_multitarget.py::fake_git_config`."""
    answers = {"user.name": "Роль Артели", "user.email": "role@artel.invalid"}
    value = answers.get(args[-1], "") if args[:2] == ("config", "--get") else ""
    return subprocess.CompletedProcess(list(args), 0, f"{value}\n", "")


class RoleEnvCarriesNoPultMarkerTest(TmpRootTest):

    def role_env(self) -> dict:
        with mock.patch.object(runner.gitcmd, "git", fake_git_config), \
                mock.patch.object(runner.keychain, "token", lambda slot: None):
            return runner.role_env("developer", "01PLANKTASK")

    def test_ac9_pult_marker_does_not_leak_into_the_role_environment(self):
        """Шаг роли не получает `ARTEL_PULT_GIT` ни когда переменной нет у
        пульта, ни когда она есть: хук — вторая линия защиты main от роли,
        и роль не должна уметь её снять просто унаследовав окружение.

        Ловит мутацию: реализация вносит `ARTEL_PULT_GIT` в
        `stack.ROLE_ENV_ALLOWLIST` (например, «чтобы шаг не спотыкался о
        хук») — тогда выставленная у пульта переменная прошла бы фильтр и
        вторая сверка ниже покраснела бы.
        """
        with mock.patch.dict(os.environ):
            os.environ.pop(MARKER_ENV, None)
            self.assertNotIn(MARKER_ENV, self.role_env())

        with mock.patch.dict(os.environ, {MARKER_ENV: MARKER_VALUE}):
            self.assertNotIn(MARKER_ENV, self.role_env())

        self.assertNotIn(MARKER_ENV, stack.ROLE_ENV_ALLOWLIST)


if __name__ == "__main__":
    unittest.main()
