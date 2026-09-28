"""AC-4: прогон на наборе, ни одна роль которого не идёт провайдером
`codex`, и прогон без `--set` не меняют ни дом роли клона, ни окружение
шага.

Зелёный с рождения: сегодня оба прогона и так не переносят в клон ничего
(`codex_auth` = `None`) — тест держит существующее поведение и сторожит,
чтобы подмена `CODEX_HOME` не оказалась безусловной, то есть включённой и
для набора на провайдере по умолчанию.

Настоящий клиент Codex не запускается, связка ключей не спрашивается: на
этих прогонах проверка входа не зовётся вовсе, что тест и проверяет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _clone_env import CloneEnvCase, env_of_role_home  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config  # noqa: E402


class RunsWithoutCodexRolesTest(CloneEnvCase):
    """AC-4: набор без ролей Codex и прогон без `--set`."""

    def test_ac4_a_plan_without_codex_roles_carries_no_auth_into_the_clone(self):
        """План набора, у которого нет ролей на провайдере `codex`, и план
        набора ПО УМОЛЧАНИЮ (прогон без `--set`) оба дают `None` вместо
        входа Codex — в блок клона переносить нечего.

        Ловит мутацию: перенос включается самим фактом названного набора
        (условие записано как «передан `--set`», а не «есть роль на
        `codex`») — прогон на наборе моделей провайдера по умолчанию
        требовал бы указателя связки ключей в доме роли пульта и отказывал
        бы там, где до задачи проходил.
        """
        default_plan = canary._set_plan(config.CANARY_DEFAULT_SET)
        claude_plan = canary.CanarySetPlan("nabor-bez-codex", {}, None, "", ())

        self.assertEqual((), default_plan.codex_roles)
        self.assertIsNone(canary._codex_clone_auth(default_plan))
        self.assertIsNone(canary._codex_clone_auth(claude_plan))

    def test_ac4_the_clone_role_home_and_the_step_env_stay_as_they_were(self):
        """Блок клона без входа Codex не кладёт в дом роли клона указатель
        связки ключей, а окружение шага внутри блока остаётся тремя именами
        от `config.ROLE_HOME` клона.

        Ловит мутацию: пультовский `CODEX_HOME` подставляется на входе в
        блок безусловно, не по наличию входа Codex — шаг роли на прогоне
        без ролей Codex получал бы каталог клиента ПУЛЬТА, то есть прогон
        перестал бы проверять дом роли того sha, ради которого заводится
        клон.
        """
        with self.fake_git():
            with canary._ephemeral_clone(codex_auth=None):
                clone_role_home = config.ROLE_HOME
                env = self.step_env()
                pointer = clone_role_home / canary._KEYCHAIN_POINTER_REL
                pointer_exists = pointer.exists()

        self.assertFalse(pointer_exists)
        for name, value in env_of_role_home(clone_role_home).items():
            with self.subTest(name=name):
                self.assertEqual(value, env.get(name))


if __name__ == "__main__":
    unittest.main()
