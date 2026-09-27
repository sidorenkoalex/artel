"""Паритет PATH команд шага Codex с шагом провайдера по умолчанию (SPEC
01M3H3K73XBMJMD0EPXZX6HYY9, требования 1-5).

Постоянная регрессия поверх приёмочной планки задачи: планка уйдёт вместе
с каталогом задачи, а свойства «обе половины решения стоят на месте»,
«окружение шага несёт адрес дома роли третьим именем» и «оболочка входа с
курируемым файлом дома роли сохраняет PATH пульта» обязаны её пережить.

Codex CLI здесь не запускается ни разу: предмет — файлы референса дома
роли, собранные окружения обоих шагов и поведение самой оболочки входа.
Оболочку входа тест запускает настоящую (`/bin/zsh -lc`) — её и называет
критерий, — а на машине прогона без неё (Linux CI) сверяет ту половину
утверждения, которая от машины не зависит: содержимое курируемого файла.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, keychain, providers, roles, runner  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

#: Оболочка входа, которой шаг Codex исполняет команды (проверка Оператора
#: 27.09, «Материалы» SPEC) — её же называет AC-1.
LOGIN_SHELL = ("/bin/zsh", "-lc")

#: Скрипт оболочки, печатающий PATH ровно как есть.
PRINT_PATH = 'printf %s "$PATH"'

STUB_BIN = "/artel-test-stub-bin"
ALIEN_ZDOTDIR = "/tmp/zsh-dir-operatora-ne-roli"


def _reference() -> Path:
    """Каталог референса курируемого дома роли `codex` — адрес называет сам
    провайдер, не литерал теста."""
    return providers.get("codex").home_reference().reference


def _rc_text() -> str:
    return (_reference() / codex_provider.RC_FILE).read_text(encoding="utf-8")


def _meaningful_lines(text: str) -> list:
    """Строки файла оболочки без комментариев и пустых — то, что оболочка
    действительно исполнит."""
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")]


class CuratedShellRcTest(unittest.TestCase):
    """Половина решения, живущая файлом дома роли (требования 1, 5).

    Песочница `TmpRootTest` здесь не годится: она уводит `config.ROOT` во
    временный каталог, а предмет — файлы РЕФЕРЕНСА репозитория.
    """

    def test_the_curated_rc_file_only_disables_the_global_startup_files(self):
        """Курируемый файл дома роли несёт ровно директиву снятия
        `GLOBAL_RCS` и ничего больше: он исполняется каждой оболочкой шага.

        Ловит мутацию: паритет «починили» дописыванием каталогов роли к
        чужому PATH (`export PATH=$PATH:…`) — системные каталоги остаются
        первыми, порядок каталогов пульта ломается, и `python3` в шаге
        по-прежнему системный; либо в файл дома роли переехал произвольный
        код, исполняемый на каждую команду роли.
        """
        lines = _meaningful_lines(_rc_text())

        self.assertEqual([codex_provider.RC_DIRECTIVE], lines,
                         f"{codex_provider.RC_FILE}: {lines}")

    def test_the_rc_file_is_part_of_the_reference_and_its_home_check(self):
        """Файл лежит в референсе дома роли `codex`, то есть
        разворачивается холодным стартом и сверяется строкой `doctor`
        вместе с остальными файлами референса.

        Ловит мутацию: файл положили прямо в `.artel/home/.codex` живого
        пульта (или в корень дома роли) мимо референса — `.artel/home`
        эфемерен (ADR-0005 п.3), холодный старт вернёт дом роли без него,
        а `doctor` о пропаже не скажет, потому что в референсе её нет.
        """
        path = _reference() / codex_provider.RC_FILE

        self.assertTrue(path.is_file(), path)
        self.assertIn(path, list(_reference().rglob("*")),
                      "сверка дома роли идёт rglob по референсу")

    def test_both_halves_of_the_shell_environment_policy_stand_together(self):
        """Пара политики окружения оболочки стоит и в курируемом
        `config.toml`, и `-c`-парой команды шага — именно она доносит
        `ZDOTDIR` до команды.

        Ловит мутацию: пара осталась только в одной половине — в доме роли
        (тогда на пульте с потерянным `.artel/home` шаг идёт без неё) или
        только в команде шага (тогда Оператор, разворачивающий дом роли
        руками, о ней не знает); либо значение сменили на `core`/`none`,
        при которых CLI `ZDOTDIR` до команды не доносит.
        """
        pair = (codex_provider.SHELL_ENV_INHERIT_KEY,
                codex_provider.SHELL_ENV_INHERIT_VALUE)
        self.assertIn(pair, codex_provider.CONFIG_OVERRIDES)

        with mock.patch.object(runner, "declared_tool_path",
                               lambda name: f"{STUB_BIN}/{name}"):
            argv = providers.get("codex").command()
        overrides = [argv[i + 1] for i, item in enumerate(argv) if item == "-c"]
        self.assertIn(f"{pair[0]}={pair[1]}", overrides, argv)

        config_text = (_reference() / "config.toml").read_text(encoding="utf-8")
        section, _, key = codex_provider.SHELL_ENV_INHERIT_KEY.rpartition(".")
        self.assertIn(f"[{section}]", config_text)
        self.assertIn(f'{key} = "{codex_provider.SHELL_ENV_INHERIT_VALUE}"',
                      config_text)

    def test_agents_md_names_the_interpreter_the_path_and_both_halves(self):
        """`AGENTS.md` дома роли называет интерпретатор пульта с его
        адресом, PATH шага и оба ключа решения.

        Ловит мутацию: механизм починили, а дом роли продолжает молчать о
        том, какой интерпретатор видит шаг, — роль читает то же, что читала
        27.09, и снова ищет `python3.13` перебором; либо ключ решения из
        документа выпал, и Оператор теряет паритет первой же чисткой
        конфига.
        """
        text = (_reference() / "AGENTS.md").read_text(encoding="utf-8")

        for marker in ("PATH", ".artel/venv", "python3",
                       codex_provider.RC_FILE,
                       codex_provider.SHELL_ENV_INHERIT_KEY.split(".")[0],
                       codex_provider.SHELL_ENV_INHERIT_KEY.split(".")[-1]):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


class StepEnvZdotdirTest(TmpRootTest):
    """Половина решения, живущая окружением шага (требование 2)."""

    def setUp(self):
        super().setUp()
        for patcher in (
                mock.patch.object(keychain, "token", lambda slot: "tok-test"),
                mock.patch.object(runner.shutil, "which",
                                  lambda name: f"{STUB_BIN}/{name}")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def step_env(self, provider_name: str) -> dict:
        """Окружение шага роли, идущей на провайдере `provider_name`, —
        настоящей сборкой пульта."""
        with mock.patch.object(roles, "provider", lambda role: provider_name):
            return runner.role_env("developer", "01TESTTASK")

    def test_zdotdir_points_at_the_curated_home_and_overwrites_the_ambient(self):
        """`ZDOTDIR` шага — тот же развёрнутый дом роли, что и `CODEX_HOME`,
        и он сильнее значения Оператора.

        Ловит мутацию: `ZDOTDIR` поставлен `setdefault`-ом «как токен» —
        оболочка шага читает личные zsh-файлы Оператора (конфиг-инъекция,
        ADR-0003 п.14) вместе с его PATH; либо он указывает на корень дома
        роли, где курируемого файла нет, и оболочка входа снова переписывает
        PATH.
        """
        deployed = config.ROLE_HOME / ".codex"

        with mock.patch.dict(os.environ, {"ZDOTDIR": ALIEN_ZDOTDIR}):
            env = providers.get("codex").environment("developer", "T1")

        self.assertEqual(str(deployed), env[codex_provider.ZDOTDIR_ENV])
        self.assertEqual(env[codex_provider.HOME_ENV],
                         env[codex_provider.ZDOTDIR_ENV],
                         "курируемый файл лежит в доме роли")

    def test_the_assembled_step_env_carries_zdotdir_only_for_a_codex_step(self):
        """Собранное окружение шага роли на Codex несёт `ZDOTDIR`, шага на
        провайдере по умолчанию — нет, и PATH у обоих шагов один и тот же.

        Ловит мутацию: `ZDOTDIR` дописан общим белым списком манифеста
        (тогда он приезжает и в шаг Claude, и со значением Оператора), либо
        провайдер начал править PATH под себя — паритет, ради которого
        задача заведена, разошёлся бы ровно на том шаге, который его и
        требует.
        """
        with mock.patch.dict(os.environ, {"ZDOTDIR": ALIEN_ZDOTDIR}):
            codex_env = self.step_env("codex")
            claude_env = self.step_env("claude")

        self.assertEqual(str(config.ROLE_HOME / ".codex"),
                         codex_env[codex_provider.ZDOTDIR_ENV])
        self.assertNotIn(codex_provider.ZDOTDIR_ENV, claude_env,
                         sorted(claude_env))
        self.assertEqual(claude_env["PATH"], codex_env["PATH"])
        self.assertEqual(str(config.VENV_DIR / "bin"),
                         codex_env["PATH"].split(os.pathsep)[0])


class LoginShellKeepsRolePathTest(unittest.TestCase):
    """Обе половины вместе: что видит команда после оболочки ВХОДА
    (требования 1-2)."""

    def path_after_login_shell(self, env: dict) -> str:
        res = subprocess.run([*LOGIN_SHELL, PRINT_PATH], env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(0, res.returncode, res.stderr)
        return res.stdout.strip()

    def test_the_login_shell_keeps_the_role_path_with_the_curated_rc_file(self):
        """Оболочка входа с окружением, несущим `ZDOTDIR` на развёрнутый дом
        роли, печатает PATH пульта без изменений; без курируемого файла тот
        же прогон отдаёт PATH, переписанный `path_helper` из
        `/etc/zprofile`.

        Ловит мутацию: директиву из курируемого файла убрали (или заменили
        правкой `.zshrc`, которого `-lc` не читает вовсе) — PATH роли
        уезжает в хвост за системные каталоги, и равенство откажет, назвав
        оба значения.
        """
        if not Path(LOGIN_SHELL[0]).exists():
            # Машина прогона без оболочки входа (Linux CI): её поведение
            # проверять нечем, но половина утверждения от машины не
            # зависит — курируемый файл несёт директиву.
            self.assertIn(codex_provider.RC_DIRECTIVE, _rc_text())
            return

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = Path(tmp.name)
        # Имитация развёрнутого дома роли: файл берётся из референса, а не
        # пишется тестом — предмет проверки именно курируемый файл.
        deployed = home / ".codex"
        deployed.mkdir()
        shutil.copy2(_reference() / codex_provider.RC_FILE,
                     deployed / codex_provider.RC_FILE)
        role_path = os.pathsep.join([str(home / "venv" / "bin"), "/usr/bin"])
        env = {"HOME": str(home), "PATH": role_path, "TERM": "dumb"}

        without_rc = self.path_after_login_shell(dict(env))
        with_rc = self.path_after_login_shell(
            dict(env, **{codex_provider.ZDOTDIR_ENV: str(deployed)}))

        self.assertNotEqual(
            role_path, without_rc,
            "оболочка входа этой машины PATH не переписывает — предпосылка "
            "требования не воспроизведена, проверять нечего")
        self.assertEqual(role_path, with_rc)


if __name__ == "__main__":
    unittest.main()
