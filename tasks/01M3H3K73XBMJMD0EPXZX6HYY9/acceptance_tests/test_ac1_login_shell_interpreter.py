"""AC-1 (SPEC 01M3H3K73XBMJMD0EPXZX6HYY9): офлайн-прогон
`/bin/zsh -lc 'command -v python3'` с окружением шага Codex и его домом
роли отвечает путём к интерпретатору пульта, и Codex CLI при этом не
запускается.

Красен до реализации: оболочка входа исполняет `/etc/zprofile` с
`path_helper`, тот ставит системные каталоги В НАЧАЛО PATH, и
`command -v python3` отвечает `/usr/bin/python3` вместо интерпретатора
пульта (проверка Оператора 27.09, «Материалы» SPEC; воспроизведено этим
же прогоном до реализации).

«Интерпретатор пульта» — тот, который `role_env` ставит первым каталогом
PATH роли (`<config.VENV_DIR>/bin`, SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8,
требование 4). Планка подставляет его временным каталогом (см.
`_step_env`), поэтому утверждение теста не зависит от того, что лежит в
`.artel/venv` машины прогона: предмет — порядок PATH после оболочки
входа, а не состояние venv.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.providers import codex as codex_provider  # noqa: E402

from _step_env import LOGIN_SHELL, ProviderStepEnvSandbox  # noqa: E402


class CodexStepLoginShellInterpreterTest(ProviderStepEnvSandbox):

    def test_ac1_login_shell_resolves_python3_to_the_console_interpreter(self):
        """Окружение шага роли на Codex собрано `role_env`, дом роли
        развёрнут из референса; `/bin/zsh -lc 'command -v python3'` с этим
        окружением отвечает ровно путём к интерпретатору пульта
        (`<venv>/bin/python3`).

        Ловит мутацию: изменение PATH оболочкой входа устранено только для
        интерактивного случая (например правка легла в `.zshrc`, который
        `-lc` не читает, либо ключ поставлен лишь в курируемый `config.toml`
        и до окружения команды не доходит) — `command -v python3` снова
        отвечает системным `/usr/bin/python3`, и равенство откажет.
        """
        env = self.step_env(codex_provider.CLI_NAME)

        self.assertEqual(str(self.deployed_home()),
                         env.get(codex_provider.HOME_ENV),
                         "дом роли шага не указывает на развёрнутый слой — "
                         "предпосылка критерия не воспроизведена")

        resolved = self.resolved_after_login_shell(env, "python3")

        self.assertEqual(str(self.venv_bin / "python3"), resolved,
                         f"PATH после оболочки входа: "
                         f"{self.path_after_login_shell(env)}")

    def test_ac1_no_codex_cli_is_spawned_by_the_check(self):
        """Тот же офлайн-прогон не запускает Codex CLI: среди всех
        подпроцессов проверки (сборка окружения зовёт git за идентичностью,
        сама проверка — оболочку входа) нет ни одного с инструментом
        `codex`.

        Ловит мутацию: паритет «доказывается» живым вызовом `codex exec`
        (например проверка спрашивает интерпретатор у самого CLI) — офлайн
        критерия больше нет, каждый прогон платный, и утверждение о
        подпроцессах откажет.
        """
        spawned = self.spawned_commands()

        env = self.step_env(codex_provider.CLI_NAME)
        self.resolved_after_login_shell(env, "python3")

        tools = [Path(str(cmd[0])).name for cmd in spawned
                 if isinstance(cmd, (list, tuple)) and cmd]
        self.assertNotIn(codex_provider.CLI_NAME, tools, tools)
        self.assertIn(Path(LOGIN_SHELL[0]).name, tools,
                      "оболочка входа не запускалась — тест не проверил "
                      "ничего")


if __name__ == "__main__":
    unittest.main()
