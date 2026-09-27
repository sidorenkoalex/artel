"""Общие помощники планки 01M3H3JRBD544GQ10SS3DBGEVP (нужны больше чем
одному `test_*.py`, поэтому модуль с префиксом `_`).

Два предмета: карта исполнителей под тестом (текст РЕАЛЬНОГО `roles.yaml`
пульта, у одной роли переписано поле) и песочница строк `doctor`, в
которой ни один настоящий CLI не запускается — ни `claude`, ни `codex`.

Песочница — надстройка над общей `tests/sandbox.py::TmpRootTest` (пути
`config` во временном каталоге, шаблон локального слоя моделей), а не
собственная копия её патчей: skills/test-authoring.md, «Лёгкая песочница
переходов — не копия, импорт».
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor, keychain, runner, stack  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

#: Роль, которую задача добавляет в перечень предполёта doctor.
ANALYST = "analyst"

#: Каталог подменённых исполняемых файлов: ни один из них не существует и
#: ни разу не запускается — `subprocess.run` пакета `doctor` подменён.
STUB_BIN = "/artel-test-stub-bin"

#: Ответ `codex login status` при подтверждённом подписочном входе — та же
#: формулировка, на которую смотрит `codex_provider.CHATGPT_LOGIN_RE`.
LOGGED_IN_CHATGPT = "Logged in using ChatGPT"

# Ambient-канал токена Claude: обе переменные сильнее слота keychain
# (`check_token` смотрит их первыми), а в окружении прогона они стоят по
# построению — внутри шага роли их кладёт туда сам пульт. Гасим, иначе
# строка `token` вышла бы безымянной («токен уже в окружении»), склейка
# `provider_preflight_checks` схлопнула бы её в ОДНУ на все роли, и тест
# про строку роли analyst краснел бы на машине Оператора без единого
# дефекта в коде.
NO_AMBIENT_TOKEN = {"CLAUDE_CODE_OAUTH_TOKEN": "", "ANTHROPIC_API_KEY": ""}

#: Карта исполнителей, которую не разбирает `yamlmini` (раздел `roles:` —
#: блочный список, а не отображение): сценарий «карта нечитаема».
UNREADABLE_ROLES_TEXT = "roles:\n  - developer\n"

_REAL_ROLES_TEXT = config.ROLES.read_text(encoding="utf-8")


def real_roles_text() -> str:
    """Текст `roles.yaml` пульта как есть — базовая карта всех сценариев."""
    return _REAL_ROLES_TEXT


def roles_text(overrides: dict) -> str:
    """Текст реального `roles.yaml`, где у каждой роли из `overrides`
    (`{роль: {поле: значение}}`) названные поля заменены, а отсутствующие
    — дописаны.

    Правка идёт по блоку роли (строки с отступом 4 пробела после
    заголовка `  <роль>:`), прежняя строка поля снимается целиком вместе
    с её хвостовым комментарием; комментарии-продолжения остаются —
    `yamlmini` пропускает закомментированную строку на любом отступе.
    """
    lines = _REAL_ROLES_TEXT.splitlines(keepends=True)
    for role, fields in overrides.items():
        anchor = f"  {role}:\n"
        if anchor not in lines:
            raise AssertionError(f"роль {role!r} не найдена в {config.ROLES}")
        start = lines.index(anchor)
        end = start + 1
        while end < len(lines) and lines[end].startswith("    "):
            end += 1
        block = lines[start + 1:end]
        for field, value in fields.items():
            block = [f"    {field}: {value}\n"] + [
                line for line in block
                if not line.lstrip().startswith(f"{field}:")]
        lines = lines[:start + 1] + block + lines[end:]
    return "".join(lines)


def roles_with(role: str, **fields) -> str:
    """`roles_text` для одной роли: `roles_with(ANALYST, provider="codex")`."""
    return roles_text({role: fields})


def chain_items(detail: str) -> set:
    """Множество цепочек ролей из текста строки `doctor` вида
    «<заголовок>: <цепочка>, <цепочка>, …» (`role-providers`,
    `models-local`).

    Заголовок отрезается: сравнивать строки целиком нельзя — добавление
    цепочки новой роли меняет и текст вокруг неё, а предмет сравнения —
    именно состав цепочек.
    """
    tail = detail.split(": ", 1)[1] if ": " in detail else detail
    return {item.strip() for item in tail.split(", ") if item.strip()}


class FakeCliRuns:
    """Подмена `subprocess.run` пакета `doctor`: отвечает на `--version`
    обоих CLI и на `codex … login status`, запоминая все вызовы.

    Версии отдаются ДИНАМИЧЕСКИ — пин Claude из `config` и минимум Codex
    из манифеста провайдера: зашитый литерал разошёлся бы с крутилкой
    Оператора при первом же сдвиге пина.
    """

    def __init__(self, login_status: str = LOGGED_IN_CHATGPT,
                 returncode: int = 0):
        self.login_status = login_status
        self.returncode = returncode
        self.calls: list = []

    def __call__(self, args, **kwargs):
        argv = [str(item) for item in args]
        self.calls.append(argv)
        if "login" in argv:
            # Настоящий 0.155.1 печатает результат `login status` в stderr.
            return subprocess.CompletedProcess(argv, self.returncode, "",
                                               f"{self.login_status}\n")
        name = Path(argv[0]).name
        version = (stack.version_text(codex_provider.CLI_MINIMUM)
                   if name == codex_provider.CLI_NAME
                   else config.CLI_VERSION_PIN)
        return subprocess.CompletedProcess(argv, 0, f"{version}\n", "")


class DoctorLinesSandbox(TmpRootTest):
    """Песочница строк `doctor`, зависящих от перечня ролей.

    Поверх `TmpRootTest`: токен роли из подменённого keychain, погашенный
    ambient-канал токена, найденный любой CLI (`which`), резолв
    объявленных инструментов манифеста в подменённый путь и подменённый
    `subprocess.run` пакета `doctor` (`FakeCliRuns`).
    """

    def setUp(self):
        super().setUp()
        self.patch(keychain, "token", lambda slot: "tok-test")
        env_patcher = mock.patch.dict(os.environ, NO_AMBIENT_TOKEN)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        self.patch(doctor.shutil, "which", self._which)
        self.patch(runner, "declared_tool_path",
                   lambda name: f"{STUB_BIN}/{name}")
        self.runs = FakeCliRuns()
        self.patch(doctor.subprocess, "run", self.runs)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _which(self, name, *args, **kwargs):
        return f"{STUB_BIN}/{name}"

    def use_roles(self, text: str) -> None:
        """Карта исполнителей под тестом. Повторный вызов внутри одного
        теста подменяет карту поверх прежней (патчи снимаются штатным
        cleanup в LIFO-порядке) — так пишется сценарий «до и после»."""
        path = self.root / "roles-under-test.yaml"
        path.write_text(text, encoding="utf-8")
        self.patch(config, "ROLES", path)

    def grouped_provider_lines(self) -> dict:
        """`{имя строки: [проверки]}` предполёта провайдеров — тот самый
        склеенный набор, который печатает `doctor`."""
        return doctor.provider_preflight_checks()

    def flat_provider_lines(self) -> set:
        """`{(имя строки, текст)}` — вывод предполёта провайдеров как
        множество строк, годное для сравнения двух прогонов."""
        return {(name, check.detail)
                for name, checks in self.grouped_provider_lines().items()
                for check in checks}
