"""AC-1: `CODEX_HOME` шага роли внутри эфемерного клона канарейки —
каталог клиента Codex дома роли ПУЛЬТА, не одноимённый каталог дома роли
клона.

Красен до реализации: сегодня `CodexProvider.environment` считает все три
имени от `config.ROLE_HOME`, а внутри блока клона он переадресован на дом
роли клона — `CODEX_HOME` шага равен клоновскому каталогу, и утверждение о
пультовском пути не выполняется.

Клон заводится без настоящего git (`_clone_env.CloneEnvCase.fake_git`), а
исход проверки входа подменён `ok`: предмет здесь — окружение шага, не
авторизация. Настоящий клиент Codex не запускается, связка ключей не
спрашивается.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _clone_env import CloneEnvCase  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402


class CloneStepCodexHomeTest(CloneEnvCase):
    """AC-1: адрес каталога клиента Codex в окружении шага клона."""

    def test_ac1_clone_step_env_carries_the_pult_codex_home(self):
        """Внутри блока эфемерного клона, заведённого с входом Codex,
        `CODEX_HOME` шага роли равен `<дом роли пульта>/.codex`, а не
        одноимённому каталогу дома роли клона.

        Ловит мутацию: `CODEX_HOME` по-прежнему считается от
        переадресованного `config.ROLE_HOME` (подмена сделана только для
        предполётной проверки входа либо не сделана вовсе) — значение в
        окружении шага указывает на каталог клона, то есть на путь,
        которым `codex login` запись в связке не заводил, и шаг роли упал
        бы авторизацией до первого токена.
        """
        expected = self.pult_role_home / codex_provider.DEPLOYED_HOME_DIR

        with self.fake_git(), self.login_check():
            with canary._ephemeral_clone(codex_auth=self.auth()):
                inside_role_home = config.ROLE_HOME
                env = self.step_env()

        clone_client_dir = inside_role_home / codex_provider.DEPLOYED_HOME_DIR
        self.assertEqual(str(expected), env.get(codex_provider.HOME_ENV))
        self.assertNotEqual(str(clone_client_dir),
                            env.get(codex_provider.HOME_ENV))

    def test_ac1_the_clone_role_home_is_really_a_different_directory(self):
        """Предпосылка критерия: дом роли клона и дом роли пульта — разные
        каталоги, то есть равенство выше не получено совпадением путей.

        Ловит мутацию: блок клона перестал переадресовывать `ROLE_HOME`
        (имя убрано из `_CLONE_CONFIG_ATTRS` ради «простого» доступа к
        пультовскому `CODEX_HOME`) — вместе с ним в дом роли ПУЛЬТА уехали
        бы и указатель связки ключей, который прогон кладёт внутри блока
        (`_install_codex_pointer`), и `ZDOTDIR` шага: клон перестал бы
        проверять развёрнутый из референса клона `.zshenv`.
        """
        with self.fake_git(), self.login_check():
            with canary._ephemeral_clone(codex_auth=self.auth()):
                inside_role_home = config.ROLE_HOME

        self.assertNotEqual(self.pult_role_home, inside_role_home)
        self.assertEqual(self.clone_role_home, inside_role_home)


if __name__ == "__main__":
    unittest.main()
