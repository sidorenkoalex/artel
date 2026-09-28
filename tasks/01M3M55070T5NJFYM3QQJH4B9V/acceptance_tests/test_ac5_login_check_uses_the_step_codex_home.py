"""AC-5: проверка входа, которой прогон отказывает до первого шага роли,
зовётся с тем же значением `CODEX_HOME`, которое получит шаг роли в этом
же клоне.

Зелёный с рождения: связка держится и сегодня — узел `doctor.
check_codex_chatgpt_auth` берёт окружение у того же `CodexProvider.
environment`, что отдаёт его шагу. Тест сторожит, чтобы задача не разорвала
эту связку половинчатой правкой: предполёту — пультовский путь своим
выражением, шагу — прежний клоновский.

Узел проверки входа работает НАСТОЯЩИЙ, но живой клиент Codex не
запускается и связка ключей не спрашивается: подменён `subprocess` фасада
`doctor` (процесс не спавнится вовсе) и резолв пути инструмента.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _clone_env import CloneEnvCase  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402


class LoginCheckCodexHomeTest(CloneEnvCase):
    """AC-5: `CODEX_HOME` предполётной проверки входа и `CODEX_HOME` шага."""

    def test_ac5_the_preflight_login_check_runs_with_the_step_codex_home(self):
        """`codex login status`, которым прогон проверяет вход до первого
        шага роли, запускается с тем же `CODEX_HOME`, что несёт окружение
        шага роли в этом же блоке клона.

        Ловит мутацию: пультовский путь подставлен только предполёту
        (проверка входа собирает окружение собственным выражением), а
        `CodexProvider.environment` оставлен считать `CODEX_HOME` от
        переадресованного `config.ROLE_HOME` — зелёная строка предполёта
        доказывала бы вход дома, которым шаг НЕ пойдёт, и прогон платил бы
        падением авторизации уже за деньги, после зелёного предполёта.
        """
        with self.fake_git(), self.real_login_check() as envs:
            with canary._ephemeral_clone(codex_auth=self.auth()):
                step_env = self.step_env()

        self.assertTrue(envs, "предпосылка: проверка входа звала CLI")
        for index, env in enumerate(envs):
            with self.subTest(call=index):
                self.assertEqual(step_env.get(codex_provider.HOME_ENV),
                                 env.get(codex_provider.HOME_ENV))


if __name__ == "__main__":
    unittest.main()
