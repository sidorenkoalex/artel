"""AC-3: вне блока эфемерного клона окружение шага Codex — прежние три
имени от `config.ROLE_HOME`; выход из блока, в том числе выход исключением,
это поведение восстанавливает.

Зелёный с рождения: вне клона окружение шага и сегодня считается от
`config.ROLE_HOME` — тест держит существующее поведение и сторожит утечку
подмены наружу блока (не снятый по выходу указатель пультовского пути).

Клон заводится без настоящего git, исход проверки входа подменён: предмет
— окружение боевого шага, не авторизация. Настоящий клиент Codex не
запускается, связка ключей не спрашивается.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _clone_env import CloneEnvCase, env_of_role_home  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config  # noqa: E402


class StepEnvOutsideCloneTest(CloneEnvCase):
    """AC-3: окружение боевого шага до и после блока клона."""

    def assert_env_follows_role_home(self):
        """Окружение шага — ровно три имени, посчитанные от текущего
        `config.ROLE_HOME`, каким бы он ни был.

        Проверяется ВКЛЮЧЕНИЕ трёх пар, а не полный состав словаря:
        критерий требует прежних значений трёх имён, а не запрета
        когда-нибудь добавить четвёртое.
        """
        fresh = self.tdir / "another-pult" / ".artel" / "home"
        with mock.patch.object(config, "ROLE_HOME", fresh):
            env = self.step_env()
        for name, value in env_of_role_home(fresh).items():
            with self.subTest(name=name):
                self.assertEqual(value, env.get(name))

    def test_ac3_env_is_unchanged_before_and_after_a_normal_clone_block(self):
        """Окружение шага до входа в блок клона и после штатного выхода из
        него совпадает, и после выхода оно снова следует за
        `config.ROLE_HOME`.

        Ловит мутацию: пультовский путь `CODEX_HOME` запоминается модульным
        состоянием на входе в блок и не снимается по выходу — боевой шаг
        после первого же прогона канарейки получал бы `CODEX_HOME`,
        зафиксированный на момент того прогона, вместо адреса, посчитанного
        от `config.ROLE_HOME` в момент шага.
        """
        before = self.step_env()

        with self.fake_git(), self.login_check():
            with canary._ephemeral_clone(codex_auth=self.auth()):
                pass

        after = self.step_env()
        self.assertEqual(before, after)
        for name, value in env_of_role_home(self.pult_role_home).items():
            with self.subTest(name=name):
                self.assertEqual(value, after.get(name))
        self.assert_env_follows_role_home()

    def test_ac3_env_is_restored_when_the_clone_block_exits_by_exception(self):
        """Выход из блока клона ИСКЛЮЧЕНИЕМ возвращает прежнее окружение
        шага так же, как штатный выход.

        Ловит мутацию: снятие подмены написано последней строкой тела
        блока, а не в `finally` — упавший прогон канарейки (а падает он
        штатно: `git clone` не создан, checkout не удался) оставлял бы
        пультовский `CODEX_HOME` в окружении всех последующих боевых шагов
        процесса.
        """
        before = self.step_env()

        with self.fake_git(), self.login_check():
            with self.assertRaises(ValueError):
                with canary._ephemeral_clone(codex_auth=self.auth()):
                    raise ValueError("боевой отказ внутри блока клона")

        self.assertEqual(before, self.step_env())
        self.assert_env_follows_role_home()


if __name__ == "__main__":
    unittest.main()
