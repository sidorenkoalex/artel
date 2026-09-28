"""AC-2: в том же окружении шага клона `HOME` — дом роли КЛОНА, `ZDOTDIR`
— каталог клиента дома роли клона, и ни одно из трёх имён не указывает ни
на `~/.codex` Оператора, ни на его `HOME`.

Зелёный с рождения: свойство держится и сегодня (все три имени считаются от
дома роли клона, личных путей Оператора среди них нет) — тест сторожит, что
подмена `CODEX_HOME` пультовским путём не утащит за собой два остальных
имени и не вернёт роль в user-слой Оператора.

Настоящий клиент Codex не запускается, связка ключей не спрашивается:
исход проверки входа подменён `ok`, git фальшивый.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _clone_env import CloneEnvCase  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402


class CloneStepEnvIsolationTest(CloneEnvCase):
    """AC-2: два остальных имени окружения шага клона и граница с
    окружением Оператора."""

    def clone_env(self) -> tuple:
        """(окружение шага, дом роли клона) изнутри блока эфемерного клона,
        заведённого с входом Codex."""
        with self.fake_git(), self.login_check():
            with canary._ephemeral_clone(codex_auth=self.auth()):
                return self.step_env(), config.ROLE_HOME

    def test_ac2_home_stays_the_clone_role_home(self):
        """`HOME` шага внутри клона — дом роли КЛОНА.

        Ловит мутацию: пультовским сделан не только `CODEX_HOME`, но и
        `HOME` (подмена написана как «дом роли пульта целиком») — шаг
        перестал бы видеть перенесённый в клон указатель связки ключей, а
        `_install_codex_pointer` клал бы его в каталог, которого шаг не
        читает; заодно в клон вернулось бы состояние пульта, которое
        требование 1 делить не собиралось.
        """
        env, clone_role_home = self.clone_env()

        self.assertEqual(str(clone_role_home), env.get("HOME"))

    def test_ac2_zdotdir_stays_the_clone_client_directory(self):
        """`ZDOTDIR` шага внутри клона — каталог клиента дома роли КЛОНА.

        Ловит мутацию: подмена сделана символьной ссылкой каталога клиента
        дома роли клона (или переносом обоих имён разом) — `ZDOTDIR` уехал
        бы в дом роли пульта вместе с `CODEX_HOME`, и под канарейкой
        перестал бы проверяться `.zshenv` проверяемого sha: паритет PATH
        держался бы файлом пульта, а не файлом клона.
        """
        env, clone_role_home = self.clone_env()
        expected = clone_role_home / codex_provider.DEPLOYED_HOME_DIR

        self.assertEqual(str(expected), env.get(codex_provider.ZDOTDIR_ENV))

    def test_ac2_no_name_points_at_the_operator_home_or_his_codex(self):
        """Ни одно из трёх имён окружения шага не равно `HOME` Оператора и
        не равно его `~/.codex`.

        Ловит мутацию: «дом роли пульта» посчитан от `Path.home()`
        (наследованного `HOME` процесса) вместо `config.ROLE_HOME` пульта —
        шаг роли получил бы личный каталог Оператора со всеми его
        MCP-серверами и правилами, то есть ровно ту конфиг-инъекцию, ради
        исключения которой дом роли и заводится.
        """
        env, _clone_role_home = self.clone_env()
        operator_home = Path.home()
        forbidden = {str(operator_home),
                     str(operator_home / codex_provider.DEPLOYED_HOME_DIR)}

        for name in ("HOME", codex_provider.HOME_ENV,
                     codex_provider.ZDOTDIR_ENV):
            with self.subTest(name=name):
                self.assertNotIn(env.get(name), forbidden)


if __name__ == "__main__":
    unittest.main()
