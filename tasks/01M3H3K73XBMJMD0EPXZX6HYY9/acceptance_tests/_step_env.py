"""Песочница ОКРУЖЕНИЯ ШАГА провайдера для планки задачи
01M3H3K73XBMJMD0EPXZX6HYY9 — тонкая надстройка сценария, не копия
`tests/sandbox.py`.

`tests.sandbox.TmpRootTest` здесь не годится и потому не наследуется:
она уводит во временный каталог САМ `config.ROOT`, а предмет этой планки
— курируемый дом роли, развёрнутый из РЕФЕРЕНСА репозитория
(`docs/reference/role-home/codex/`), то есть из настоящего `config.ROOT`.
Импорт `tests.sandbox` не делается и по второй причине: при импорте он
глобально подменяет `shutil.which` заглушками для `gh`/`claude`
(`_stub_which`), а планка сверяет РЕАЛЬНЫЕ пути резолва инструментов
после оболочки входа — с заглушкой `command -v gh` искал бы
несуществующий каталог и планка краснела бы мимо своего предмета.
`LightTransitionSandbox` не нужна вовсе: переходов FSM планка не
разыгрывает.

Что подменяется и почему:

- `config.VENV_DIR` — временный «venv пульта» с исполняемыми `python3`
  (симлинк на интерпретатор прогона) и `pytest`: рабочая копия задачи
  (worktree) своего `.artel/` не несёт вовсе, а `command -v python3`
  внутри оболочки обязан НАЙТИ файл, иначе резолв честно уедет в
  следующий каталог PATH и планка покраснела бы на отсутствии venv, а не
  на порядке PATH. «Интерпретатор пульта» в терминах планки — именно
  этот, подставленный `role_env` первым каталогом PATH;
- `runner.stack.check_stack` — тот же приём, что у залоченной планки
  `tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests/
  test_ac12_ac13_role_env_venv_interpreter.py`: временный venv не
  согласован с `requirements.lock`, и без подмены `role_env` отказал бы
  `OSError` до предмета проверки;
- `config.ROLE_HOME`/`config.ROLE_CONFIG_DIR` — временный дом роли,
  развёрнутый из референса ТОЙ ЖЕ функцией пульта
  (`catalog._deploy_role_home_reference`), а не копированием руками:
  файл дома роли, появившийся в референсе, планка обязана увидеть тем же
  путём, каким его увидит холодный старт;
- `roles.provider` — исполнитель роли (`providers.name_for_role`): ни
  одна роль в `roles.yaml` не несёт `provider: codex`, выбор идёт
  локальным слоем пульта, которого ни в worktree, ни на раннере нет.
  Тот же приём, что в `tests/test_provider_scoped_step_env.py`;
- `runner.role_token` — keychain в планке не спрашивается: окружение шага
  Claude собирается ради сверки PATH, а не ради токена, и живой
  `security find-generic-password` вправе спросить разрешение и подвесить
  прогон;
- `runner.declared_tool_path` — `codex` входит в манифест только когда
  ярус какой-нибудь роли разрешается в его модель (`stack.required_tools`),
  а локального слоя моделей в worktree нет: без подмены команда шага
  Codex не собралась бы вовсе (`KeyError`), и планка проверяла бы
  состояние манифеста вместо своего предмета.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (catalog, config, providers, roles,  # noqa: E402
                          runner, stack)
from orchestrator.providers import codex as codex_provider  # noqa: E402

#: Оболочка входа, которой шаг Codex исполняет команды (SPEC «Материалы»:
#: проверка Оператора 27.09) — ровно та, которую называет AC-1.
LOGIN_SHELL = ("/bin/zsh", "-lc")

#: Инструменты паритета из AC-2, в порядке критерия.
PARITY_TOOLS = ("python3", "pytest", "git", "gh")

#: Имя файла курируемого конфига дома роли `codex` — то же, что несёт
#: референс и разворачивает холодный старт.
CONFIG_FILE = "config.toml"

#: Имя документа курируемого дома роли `codex`, видимого шагу.
DOC_FILE = "AGENTS.md"

#: Имя ambient-переменной Оператора, которой в белом списке манифеста нет
#: и быть не должно: ею проверяется, что окружение шага собирается списком,
#: а не копией `os.environ`.
AMBIENT_OUTSIDE_ALLOWLIST = "ARTEL_TEST_AMBIENT_LEAK"
AMBIENT_VALUE = "znachenie-operatora-ne-dlya-shaga"


def flatten_toml(table, prefix=""):
    """Плоское отображение «точечный ключ -> значение» разобранного TOML:
    секции и inline-таблицы адресуются так же, как их адресует `-c`-пара
    команды шага Codex."""
    flat = {}
    for key, value in table.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten_toml(value, f"{dotted}."))
        else:
            flat[dotted] = value
    return flat


def as_config_text(value):
    """Значение TOML в том виде, в котором его несёт `-c`-пара команды шага;
    `None` — значение не скалярное, сверять сравнением нечего."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _ok_stack_checks():
    """Все проверки стека зелёные — `role_env` берёт `<venv>/bin` без
    отказа. Настоящая `stack.StackCheck`, а не своя структура: `role_env`
    читает поля `name`/`status`/`detail`."""
    return [stack.StackCheck(name, "ok", "планка: стек не проверяется")
            for name in ("python", "git", "gh", "claude", "venv")]


class ProviderStepEnvSandbox(unittest.TestCase):
    """Окружение и команда шага РОЛИ на заданном провайдере, собранные
    настоящими `runner.role_env()`/`provider.command()`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

        self.venv_dir = self.tdir / "venv"
        self.venv_bin = self.venv_dir / "bin"
        self.venv_bin.mkdir(parents=True)
        (self.venv_bin / "python3").symlink_to(sys.executable)
        stub = self.venv_bin / "pytest"
        stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        stub.chmod(0o755)

        # Дом роли НЕ создаётся здесь: `_deploy_role_home_reference`
        # разворачивает референс ровно тогда, когда каталога ещё нет.
        self.role_home = self.tdir / "home"

        for patcher in (
                mock.patch.object(config, "VENV_DIR", self.venv_dir),
                mock.patch.object(config, "ROLE_HOME", self.role_home),
                mock.patch.object(config, "ROLE_CONFIG_DIR",
                                  self.role_home / ".claude"),
                mock.patch.object(runner.stack, "check_stack",
                                  _ok_stack_checks),
                mock.patch.object(runner, "role_token",
                                  lambda role=None: None),
                mock.patch.object(runner, "declared_tool_path",
                                  _stub_declared_tool_path)):
            patcher.start()
            self.addCleanup(patcher.stop)

        catalog._deploy_role_home_reference()

    # --- сборка предмета -------------------------------------------------

    def step_env(self, provider_name, role="developer",
                 task_id="01M3H3K73XBMJMD0EPXZX6HYY9", ambient=None):
        """Окружение шага роли `role`, идущей на провайдере
        `provider_name`, при заданных ambient-переменных Оператора."""
        with mock.patch.object(roles, "provider", lambda name: provider_name), \
                mock.patch.dict(os.environ, ambient or {}):
            return runner.role_env(role, task_id)

    def step_command(self, provider_name, model=None):
        """Argv шага роли на провайдере `provider_name`."""
        return providers.get(provider_name).command(model)

    # --- оболочка входа ---------------------------------------------------

    def require_login_shell(self):
        """Оболочка входа AC-1 есть на машине прогона; иначе — честный
        пропуск, а не зелёный тест ни о чём."""
        if not Path(LOGIN_SHELL[0]).exists():
            self.skipTest(f"{LOGIN_SHELL[0]} на машине прогона нет — "
                          f"критерий назван именно этой оболочкой")

    def login_shell_output(self, env, script):
        """Одна строка вывода `script`, исполненного оболочкой входа с
        окружением шага `env`."""
        self.require_login_shell()
        res = subprocess.run([*LOGIN_SHELL, script], env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(0, res.returncode,
                         f"оболочка входа отказала: {res.stderr!r}")
        return res.stdout.strip()

    def resolved_after_login_shell(self, env, tool):
        """Путь, в который резолвится голый вызов `tool` ПОСЛЕ исполнения
        оболочки входа; пустая строка — не резолвится вовсе."""
        return self.login_shell_output(env, f"command -v {tool} || true")

    def path_after_login_shell(self, env):
        """PATH, который видит команда шага после оболочки входа."""
        return self.login_shell_output(env, 'printf %s "$PATH"')

    # --- прочее -----------------------------------------------------------

    def spawned_commands(self):
        """Список argv всех подпроцессов, запущенных с этого момента
        (`subprocess.run` — общий адрес для `gitcmd`, `runner` и самой
        планки): им проверяется утверждение AC-1 «Codex CLI в тесте не
        запускается»."""
        calls = []
        real_run = subprocess.run

        def spy(cmd, *args, **kwargs):
            calls.append(cmd)
            return real_run(cmd, *args, **kwargs)

        patcher = mock.patch.object(subprocess, "run", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def reference_dir(self):
        """Каталог референса курируемого дома роли `codex` в репозитории —
        адрес называет сам провайдер, не литерал планки."""
        return providers.get(codex_provider.CLI_NAME).home_reference().reference

    def deployed_home(self):
        """Развёрнутый дом роли `codex` временного слоя планки."""
        home = providers.get(codex_provider.CLI_NAME).home_reference()
        return config.ROLE_HOME / home.deployed_name

    def curated_config(self):
        """Плоские пары курируемого конфига дома роли `codex` из
        референса — один разбор на обе планки, читающие этот файл."""
        path = self.reference_dir() / CONFIG_FILE
        self.assertTrue(path.is_file(), f"нет курируемого конфига: {path}")
        return flatten_toml(tomllib.loads(path.read_text(encoding="utf-8")))

    def curated_doc_text(self):
        """Текст документа дома роли `codex`, видимого шагу."""
        path = self.reference_dir() / DOC_FILE
        self.assertTrue(path.is_file(), f"нет документа дома роли: {path}")
        return path.read_text(encoding="utf-8")


def _stub_declared_tool_path(name):
    """Абсолютный путь инструмента для argv[0] команды шага: настоящий
    резолв, если инструмент на машине есть, иначе синтетический путь —
    команда шага обязана собираться и на машине без Codex."""
    found = shutil.which(name)
    return found if found is not None else f"/artel-planka-bin/{name}"
