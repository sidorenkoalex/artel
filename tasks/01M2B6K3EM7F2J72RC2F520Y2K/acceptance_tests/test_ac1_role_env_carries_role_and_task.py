"""AC-1 (SPEC 01M2B6K3EM7F2J72RC2F520Y2K) — `runner.role_env` кладёт в
окружение процесса роли `ARTEL_ROLE=<имя роли>` и `ARTEL_TASK=<id
задачи>`; вызовы без указания задачи (`orchestrator/doctor/*`, часть
тестов) продолжают работать без правки.

Красен до реализации: `role_env` сегодня принимает только `role` —
двухаргументный вызов `role_env("developer", TASK_ID)` падает `TypeError`
(лишний позиционный аргумент), значений ARTEL_ROLE/ARTEL_TASK в
окружении ещё нет вовсе.

Песочница — `tests.sandbox.TmpRootTest` (skill test-authoring, «Лёгкая
песочница переходов — не копия, импорт»): та же база, на которой уже
стоит `tests.test_multitarget.RoleEnvTest`, а не собственная копия
патчей `stack.check_stack`/`gitcmd.subprocess.run`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _helpers import ARTEL_ROLE_VAR, ARTEL_TASK_VAR, TASK_ID  # noqa: E402

from orchestrator import config, runner  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class RoleEnvArtelVarsTest(TmpRootTest):

    def test_ac1_role_and_task_land_in_env_under_their_literal_names(self):
        """Вызов `role_env(role, task_id)` кладёт в результат обе
        переменные под точными именами из требования 1, со значениями
        роли и id задачи как есть, не тронутыми.

        Ловит мутацию: `role_env` игнорирует второй аргумент (не
        прокидывает `ARTEL_TASK` вовсе) либо путает роль и id задачи
        местами — тест покраснеет на несовпадении значения по ключу.
        """
        env = runner.role_env("developer", TASK_ID)

        self.assertEqual(env.get(ARTEL_ROLE_VAR), "developer")
        self.assertEqual(env.get(ARTEL_TASK_VAR), TASK_ID)

    def test_ac1_rest_of_environment_is_untouched_by_the_new_vars(self):
        """Остальной состав окружения (HOME/CLAUDE_CONFIG_DIR курируемого
        слоя) не меняется добавлением ARTEL_ROLE/ARTEL_TASK — те же
        значения, что и без учёта задачи.

        Ловит мутацию: реализация требования 1 задета через переписывание
        `role_env` с побочным сносом сборки HOME/CLAUDE_CONFIG_DIR (например
        перестановка порядка `setdefault`/прямого присваивания) — тест
        покраснеет на несовпадении с `config.ROLE_HOME`/`ROLE_CONFIG_DIR`.
        """
        env = runner.role_env("developer", TASK_ID)

        self.assertEqual(env["HOME"], str(config.ROLE_HOME))
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(config.ROLE_CONFIG_DIR))

    def test_ac1_config_module_names_both_env_var_constants(self):
        """`orchestrator/config.py` несёт именованные константы для
        `ARTEL_ROLE`/`ARTEL_TASK` — требование 1 называет это явно как
        источник имён, не буквальные строки прямо в `runner.py`.

        Ловит мутацию: имя переменной окружения зашито строковым литералом
        прямо в `runner.role_env` без константы в `config.py` — тогда ни
        одно значение атрибута `config` не будет равно `"ARTEL_ROLE"`/
        `"ARTEL_TASK"`, и тест не найдёт совпадения ни по одному атрибуту.
        """
        config_values = {
            getattr(config, name) for name in dir(config)
            if name.isupper() and isinstance(getattr(config, name), str)
        }

        self.assertIn(ARTEL_ROLE_VAR, config_values)
        self.assertIn(ARTEL_TASK_VAR, config_values)

    def test_ac1_calls_without_task_id_keep_working(self):
        """Существующие вызовы `role_env()`/`role_env(role)` без указания
        задачи (`orchestrator/doctor/*`, часть тестов) продолжают работать
        без правки — не поднимают исключение только из-за нового
        параметра.

        Ловит мутацию: параметр задачи сделан обязательным (без значения
        по умолчанию) — оба вызова ниже упадут `TypeError` вместо того,
        чтобы вернуть окружение.
        """
        env_bare = runner.role_env()
        env_role_only = runner.role_env("developer")

        self.assertEqual(env_role_only.get(ARTEL_ROLE_VAR), "developer")
        self.assertIsInstance(env_bare, dict)


if __name__ == "__main__":
    unittest.main()
