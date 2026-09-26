"""AC-15: шаг роли на Claude совпадает с пином `fd83eb5d` — argv
удовлетворяет пинованному ожиданию, а белый список окружения равен
пинованному минус единственное исчезнувшее имя `OPENAI_API_KEY`.

Красен до реализации: `OPENAI_API_KEY` стоит в
`stack.ROLE_ENV_ALLOWLIST`, поэтому сегодняшний белый список равен пину
ЦЕЛИКОМ, а не пину без этого имени, — тест падает на лишнем имени.
Пинованные ожидания читаются из git (`git show fd83eb5d:<путь>`), не с
диска рабочей копии: пина в рабочей копии ветки задачи уже нет.
"""
import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import config, keychain, runner, stack  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

# AC-15: ci — вторая половина критерия («наборы tests/test_providers.py,
# tests/test_providers_codex.py, tests/test_stack.py, tests/test_doctor.py,
# tests/test_runner_role_model.py, tests/test_models.py проходят зелёными,
# и ни один существующий тест не ослаблен и не удалён») доказывается
# прогоном существующих наборов на CI кодовой ветки и диффом: планка не
# вправе подтверждать неослабление тестов сама — переписанное ожидание
# выглядело бы для неё нормой. Первую половину (argv и окружение шага
# Claude против пина) проверяет тест ниже.

DROPPED_NAME = "OPENAI_API_KEY"
ARGV_TAIL_CONST = "EXPECTED_ARGV_TAIL"
ALLOWLIST_CONST = "ROLE_ENV_ALLOWLIST"
PREFIXES_CONST = "ROLE_ENV_ALLOWLIST_PREFIXES"


def pinned_text(rel: str) -> str:
    """Содержимое файла `rel` НА ПИНЕ — через git, не с диска."""
    res = subprocess.run(["git", "show", f"{_util.PIN}:{rel}"],
                         cwd=_util.REPO_ROOT, capture_output=True, text=True,
                         timeout=30)
    if res.returncode != 0:
        raise AssertionError(f"git show {_util.PIN}:{rel}: {res.stderr}")
    return res.stdout


def _assignment(text: str, name: str):
    """Узел присваивания `name = …` верхнего уровня модуля."""
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets):
            return node
    raise AssertionError(f"присваивание {name} не найдено")


def assignment_source(text: str, name: str) -> str:
    """Исходный ТЕКСТ присваивания — для сверки ожидания «как написано»,
    без исполнения пинованного модуля целиком."""
    return ast.get_source_segment(text, _assignment(text, name))


def assignment_value(text: str, name: str):
    """Значение константы: исполняется РОВНО одна строка присваивания, в
    пространстве имён с `config` (пинованный `EXPECTED_ARGV_TAIL` берёт
    `--setting-sources` от крутилки Оператора, не литералом)."""
    namespace = {"config": config}
    exec(assignment_source(text, name), namespace)  # noqa: S102
    return namespace[name]


def dict_keys(text: str, name: str) -> list:
    """Ключи-литералы словаря-константы `name`."""
    node = _assignment(text, name)
    keys = getattr(node.value, "keys", None)
    if keys is None:
        raise AssertionError(f"{name} — не словарь")
    return [key.value for key in keys if isinstance(key, ast.Constant)]


class ClaudeStepAgainstThePinTest(TmpRootTest):
    """argv и окружение шага роли на Claude — требование 9."""

    def setUp(self):
        super().setUp()
        _util.drop_ambient(self, *_util.CLAUDE_SECRETS,
                           *_util.FORBIDDEN_ENV_NAMES)
        _util.patch(self, keychain, "token", lambda slot: "tok-podpiski")
        _util.stub_tool_path(self)

    def test_ac15_argv_and_the_env_allowlist_differ_from_the_pin_only_by_the_dropped_key(self):
        """argv шага роли на Claude удовлетворяет ПИНОВАННОМУ ожиданию
        (`EXPECTED_ARGV_TAIL` пина), текст этого ожидания в рабочей копии
        не менялся, а белый список окружения равен пинованному минус
        единственное имя `OPENAI_API_KEY`; собранное окружение шага Claude
        несёт прежние HOME/CLAUDE_CONFIG_DIR/токен и не несёт ключа даже
        при заданной ambient-переменной.

        Ловит мутацию: из белого списка вместе с ключом OpenAI уехало
        что-то ещё — например `CODEX_HOME` («тоже про codex»), и шаг роли
        на Codex теряет адрес курируемого дома, либо `ANTHROPIC_API_KEY`,
        и альтернативный канал токена Claude перестаёт работать. Вторая
        мутация: заодно тронута сборка argv шага Claude (ушёл
        `--strict-mcp-config`, переставлены флаги) либо ослаблено само
        пинованное ожидание в `tests/test_providers.py` — требование 9
        держит шаг Claude неизменным, а `providers/claude.py` эта задача
        вообще только читает.
        """
        pinned_tests = pinned_text("tests/test_providers.py")
        pinned_stack = pinned_text("orchestrator/stack.py")
        current_tests = (_util.REPO_ROOT / "tests" / "test_providers.py"
                         ).read_text(encoding="utf-8")
        current_stack = (_util.REPO_ROOT / "orchestrator" / "stack.py"
                         ).read_text(encoding="utf-8")

        self.assertEqual(assignment_source(current_tests, ARGV_TAIL_CONST),
                         assignment_source(pinned_tests, ARGV_TAIL_CONST),
                         "пинованное ожидание argv шага Claude изменено")
        self.assertEqual(runner.role_cmd()[1:],
                         assignment_value(pinned_tests, ARGV_TAIL_CONST))

        pinned_names = dict_keys(pinned_stack, ALLOWLIST_CONST)
        self.assertIn(DROPPED_NAME, pinned_names, pinned_names)
        self.assertEqual(sorted(stack.ROLE_ENV_ALLOWLIST),
                         sorted(name for name in pinned_names
                                if name != DROPPED_NAME))
        self.assertEqual(assignment_source(current_stack, PREFIXES_CONST),
                         assignment_source(pinned_stack, PREFIXES_CONST),
                         "префиксы белого списка изменены — требование 9 их "
                         "не трогает")

        with mock.patch.dict(os.environ, {DROPPED_NAME: "kluch-operatora"}):
            env = runner.role_env("developer", "T1")

        self.assertNotIn(DROPPED_NAME, env)
        self.assertEqual(env["HOME"], str(config.ROLE_HOME))
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(config.ROLE_CONFIG_DIR))
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "tok-podpiski")


if __name__ == "__main__":
    unittest.main()
