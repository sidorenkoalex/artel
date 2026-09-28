"""Общая фикстура планки 01M3M55070T5NJFYM3QQJH4B9V: пульт во временном
каталоге, эфемерный клон канарейки БЕЗ настоящего git и две подмены узла
проверки входа Codex.

Тонкая надстройка сценария, а не своя копия песочницы: приём «фальшивый
`subprocess.run` + `tempfile.mkdtemp` + заглушенный `catalog.cmd_init`»
взят у `tests/test_canary.py::EphemeralCloneConfigRemapTest`, пересчёт
подпутей `config` — у `pristine_config` там же. Переходов FSM этой задаче
не нужно вовсе, поэтому `LightTransitionSandbox` здесь не импортируется:
импортировать нечего, а не «переписано заново».

Настоящий клиент Codex и системная связка ключей не вызываются ни одним
помощником: `real_login_check` подменяет `subprocess` фасада `doctor`
(узел `check_codex_chatgpt_auth` при этом работает НАСТОЯЩИЙ — предмет
AC-5 в том, с каким окружением он зовёт CLI), `login_check` подменяет сам
узел.
"""
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from importlib import util as importlib_util
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config, doctor, runner  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

#: Роль прогона, идущая провайдером Codex. Имя произвольное: и
#: `CodexProvider.environment`, и `_refuse_unless_clone_logged_in` роль
#: только пересказывают в строках, окружение от неё не зависит.
CODEX_ROLE = "analyst"

#: Байты указателя связки ключей — непустые и уникальные, чтобы равенство
#: байт-в-байт нельзя было получить пустым файлом.
POINTER_BYTES = b"bplist00\xd1\x01\x02plank-keychain-pointer\n"


def pristine_config():
    """Чистая копия `orchestrator/config.py`, загруженная заново.

    Планка спрашивает, как путь ОПРЕДЕЛЁН в коде (`ROOT / <подпуть>`), а не
    чему он равен в этом процессе: часть путей `config` тесты пульта уводят
    во временные каталоги на весь процесс. Модуль самодостаточен
    (импортирует только `pathlib`), поэтому грузится автономно.
    """
    spec = importlib_util.spec_from_file_location(
        "artel_config_plank_pristine", Path(config.__file__))
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def env_of_role_home(role_home: Path) -> dict:
    """Три имени окружения шага Codex, посчитанные от дома роли
    `role_home` — ровно так, как их считает `CodexProvider.environment` до
    этой задачи."""
    client = role_home / codex_provider.DEPLOYED_HOME_DIR
    return {"HOME": str(role_home),
            codex_provider.HOME_ENV: str(client),
            codex_provider.ZDOTDIR_ENV: str(client)}


class CloneEnvCase(unittest.TestCase):
    """Пульт во временном каталоге + эфемерный клон без настоящего git.

    `setUp` уводит ВСЕ пути `config`, которые переадресует клон
    (`canary._CLONE_CONFIG_ATTRS`), под временный `outer_root`: иначе
    прогон писал бы в дом роли машины Оператора, а `_ephemeral_clone`
    считала бы подпути от настоящего корня пульта.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        self.outer_root = self.tdir / "outer"
        self.outer_root.mkdir()
        pristine = pristine_config()
        self.suffixes = {
            attr: getattr(pristine, attr).relative_to(pristine.ROOT)
            for attr in canary._CLONE_CONFIG_ATTRS}
        for attr in canary._CLONE_CONFIG_ATTRS:
            patcher = mock.patch.object(config, attr,
                                        self.outer_root / self.suffixes[attr])
            patcher.start()
            self.addCleanup(patcher.stop)
        self.pult_role_home = config.ROLE_HOME
        self.pult_role_home.mkdir(parents=True, exist_ok=True)
        self.clone_dir = self.tdir / "clone"

    # --- фикстуры клона ---------------------------------------------------

    @property
    def clone_role_home(self) -> Path:
        """Дом роли ВНУТРИ эфемерного клона — тот же подпуть под каталогом
        клона, что у дома роли пульта под корнем пульта."""
        return self.clone_dir / self.suffixes["ROLE_HOME"]

    def auth(self) -> canary.CodexCloneAuth:
        return canary.CodexCloneAuth(CODEX_ROLE, POINTER_BYTES)

    def step_env(self, role: str = CODEX_ROLE) -> dict:
        """Окружение шага роли, идущей провайдером Codex."""
        return codex_provider.CodexProvider().environment(role)

    def _mkdtemp(self, prefix: str = "", **_kw) -> str:
        path = self.tdir / ("origin" if "origin" in prefix else "clone")
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @contextmanager
    def fake_git(self):
        """`_ephemeral_clone` без настоящего git: `git clone` заводит
        каталог, остальные команды отвечают нулём, холодный старт клона
        заглушен."""
        def fake_run(cmd, **_kw):
            if list(cmd[:2]) == ["git", "clone"]:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(canary.tempfile, "mkdtemp",
                               side_effect=self._mkdtemp), \
             mock.patch.object(canary.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(canary.catalog, "cmd_init", lambda: None):
            yield

    # --- подмены проверки входа ------------------------------------------

    @contextmanager
    def login_check(self, *, pult: str = "ok", clone: str = "ok"):
        """Подмена узла `doctor.check_codex_chatgpt_auth` исходом, который
        зависит от ДОМА РОЛИ, каким узел зовут.

        Различитель — `config.ROLE_HOME` в момент вызова: именно от него
        настоящий узел берёт `HOME` процесса `codex login status`
        (`CodexProvider.environment`), а менять его сигнатуру задача не
        вправе (`orchestrator/doctor/` — только для чтения). Значит «вход
        домом роли пульта» и «проверка окружением шага клона» различимы
        ровно этим значением.

        Отдаёт список исходов по порядку вызовов.
        """
        seen: list = []

        def fake(role):
            status = pult if config.ROLE_HOME == self.pult_role_home else clone
            seen.append((config.ROLE_HOME, status))
            detail = (f"роль {role}: вход ChatGPT подтверждён"
                      if status == "ok" else
                      f"роль {role}: код выхода 0, но вход ChatGPT не "
                      f"подтверждён. {doctor.CODEX_AUTH_RECIPE}")
            return doctor.Check(doctor.CODEX_AUTH_CHECK, status, detail)

        with mock.patch.object(doctor, "check_codex_chatgpt_auth", fake):
            yield seen

    @contextmanager
    def real_login_check(self, *, stderr: str = "Logged in using ChatGPT\n",
                         returncode: int = 0):
        """НАСТОЯЩИЙ узел `doctor.check_codex_chatgpt_auth` поверх
        подменённого `subprocess` фасада `doctor` и подменённого резолва
        инструмента.

        Живой CLI не запускается: `declared_tool_path` отдаёт заведомо
        несуществующий путь, а `run` вовсе не спавнит процесс — связка
        ключей не спрашивается ни разу. Отдаёт список ОКРУЖЕНИЙ, с
        которыми узел звал `codex login status`.
        """
        envs: list = []

        class _SubprocessStub:
            TimeoutExpired = subprocess.TimeoutExpired

            @staticmethod
            def run(cmd, **kw):
                envs.append(dict(kw.get("env") or {}))
                return subprocess.CompletedProcess(cmd, returncode, "", stderr)

        with mock.patch.object(doctor, "subprocess", _SubprocessStub), \
             mock.patch.object(runner, "declared_tool_path",
                               lambda name: f"/nonexistent/plank/{name}"):
            yield envs
