"""AC-6: `role_env(role, task_id)` — прежняя сигнатура, прежний набор
ключей и значений.

Зелёный с рождения: окружение роли собрано до задачи и не меняется ею —
тест стережёт его через рефакторинг и покраснеет, если провайдерская
часть окружения потеряет ключ, пустит в шаг переменную вне белого списка
манифеста или переставит интерпретатор роли в PATH.
"""
import inspect
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, keychain, runner, stack
from tests.sandbox import TmpRootTest

ROLE = "developer"
TASK = "zadacha-planki-provaydera"
LEAK_NAME = "ARTEL_PLANKA_MARKER_VNE_SPISKA"
LEAK_VALUE = "znachenie-Operatora-ne-dlya-roli"


def expected_tool_dirs() -> set:
    """Каталоги инструментов манифеста — тем же правилом, что объявляет
    сам манифест: для `python3` каталог интерпретатора пульта, для
    остальных — каталог резолва `shutil.which`."""
    dirs = set()
    for name in stack.DECLARED_TOOLS:
        if name == "python3":
            dirs.add(str(Path(sys.executable).parent))
        else:
            dirs.add(str(Path(shutil.which(name)).parent))
    return dirs


class RoleEnvTest(TmpRootTest):
    """Окружение шага роли во временном `config`-корне песочницы."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(keychain, "token", lambda slot: "tok-test")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac6_signature_and_named_keys_stay_as_before(self):
        """Сигнатура `(role=None, task_id=None)`, HOME/CLAUDE_CONFIG_DIR
        — на курируемый слой, метки роли и задачи — из переданных
        значений, PATH начинается каталогом интерпретатора роли и несёт
        каталоги инструментов манифеста.

        Ловит мутацию: провайдерская часть окружения возвращает HOME
        строкой реального `$HOME` Оператора (или теряет
        CLAUDE_CONFIG_DIR), либо PATH собирается с каталогом venv не
        первым — голый `python3` шага снова резолвится в интерпретатор
        Оператора.
        """
        params = inspect.signature(runner.role_env).parameters
        self.assertEqual(list(params), ["role", "task_id"])
        self.assertEqual([p.default for p in params.values()], [None, None])

        env = runner.role_env(ROLE, TASK)

        self.assertEqual(env["HOME"], str(config.ROLE_HOME))
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(config.ROLE_CONFIG_DIR))
        self.assertEqual(env[config.ARTEL_ROLE_ENV], ROLE)
        self.assertEqual(env[config.ARTEL_TASK_ENV], TASK)
        dirs = env["PATH"].split(os.pathsep)
        self.assertEqual(dirs[0], str(config.VENV_DIR / "bin"))
        self.assertEqual(set(dirs[1:]), expected_tool_dirs())

    def test_ac6_call_without_role_and_task_carries_no_markers(self):
        """Вызов без аргументов (`doctor` зовёт его так) не несёт меток
        роли и задачи вовсе.

        Ловит мутацию: метки ставятся безусловно — процесс `doctor`
        получает `ARTEL_ROLE=None`/пустую строку и начинает выглядеть
        процессом роли для кода, который читает эти переменные.
        """
        env = runner.role_env()

        self.assertNotIn(config.ARTEL_ROLE_ENV, env)
        self.assertNotIn(config.ARTEL_TASK_ENV, env)

    def test_ac6_environment_outside_the_allowlist_does_not_reach_the_role(self):
        """Переменная Оператора вне белого списка манифеста в окружение
        роли не попадает, а разрешённая доходит своим значением.

        Ловит мутацию: провайдерская часть окружения собирается копией
        `os.environ` (`dict(os.environ) | {...}`) — весь мир Оператора
        снова течёт в шаг, а сужение до белого списка остаётся только в
        докстринге.
        """
        with mock.patch.dict(os.environ,
                             {LEAK_NAME: LEAK_VALUE, "LANG": "ru_RU.UTF-8"}):
            env = runner.role_env(ROLE, TASK)

        self.assertNotIn(LEAK_NAME, env)
        self.assertNotIn(LEAK_VALUE, list(env.values()))
        self.assertEqual(env["LANG"], "ru_RU.UTF-8")

        prefixes = tuple(stack.ROLE_ENV_ALLOWLIST_PREFIXES)
        allowed = set(stack.ROLE_ENV_ALLOWLIST) | {
            "PATH", config.ARTEL_ROLE_ENV, config.ARTEL_TASK_ENV}
        extra = sorted(name for name in env
                       if name not in allowed and not name.startswith(prefixes))
        self.assertEqual(extra, [])


if __name__ == "__main__":
    unittest.main()
