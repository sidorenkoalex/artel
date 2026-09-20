"""Манифест объявленного стека пульта (SPEC 01M1RDCAFENSW2VVAPECHCVGMM,
требование 1): минимальная версия Python, внешние инструменты (`git`,
`gh`, `claude`) с минимальной версией и способом проверки, список
допустимых исключений правила «сторонних пакетов нет» (`pytest`/
`pytest-timeout`/`pytest-xdist` — SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8,
требование 1).

Единственный источник значений — этот модуль; `docs/stack.md` описывает
то же самое человекочитаемо и ссылается сюда, не дублируя числа.

`check_stack()` (требование 4) сравнивает факт с манифестом: только
`subprocess.run` локальных CLI, без сети (docs/invariants.md,
инвариант 35).

Таблица «модель роли -> минимальная версия CLI» (`MODEL_MIN_CLI_VERSION`,
SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ) живёт здесь же: `model_cli_verdict` —
один вердикт для предполётной сверки шага роли, строк `check_stack()` и
отказа после попытки класса «модель не поддерживается CLI».
"""
import re
import subprocess
import sys
from collections import namedtuple
from pathlib import Path
from typing import Optional

from . import config

# Расположение копии кода, которой ЭТОТ модуль реально исполняется
# (ANSWER-7, 01M1TKP6AAY4W8GDGZNA9R0JZT) — вычислено один раз при
# импорте, отдельной именованной константой, а не инлайн в
# `_main_copy_root()`: тесты подменяют её тем же приёмом, что и
# `config.ROOT`/`config.VENV_DIR` (`mock.patch.object(stack,
# "_MODULE_ROOT", ...)`), не трогая при этом реальное значение
# `__file__` модуля.
_MODULE_ROOT = Path(__file__).resolve().parent.parent

# `X | None` в аннотациях кода пульта (например,
# orchestrator/doctor.py::cli_version) требует Python 3.10+ без
# `from __future__ import annotations` — 3.11 фиксирует уже принятое
# решение с запасом, не голый минимум для этого синтаксиса (TZ.md).
#
# Сам этот модуль (и `config.py`, от которого он зависит) держится
# ЗАВЕДОМО 3.9-совместимым (SPEC 01M1SHK3MD4ZF9NYXSCT67J8AP, требование
# 2): `_main_copy_root()` ниже несёт `Optional[Path]`, не `Path | None`
# — точка входа `orchestrator/artel.py` читает `REQUIRED_PYTHON` прямым
# импортом ДО того, как проверить версию интерпретатора, и падение на
# разборе аннотации здесь было бы тем же классом отказа, от которого
# спасает вся эта проверка.
REQUIRED_PYTHON = (3, 11)

# Версия основных джобов CI и локальной разработки (01M1RDCCKBQMJ5G2K9
# ANJP059H, ANSWER-1, вопрос 2) — отдельная от REQUIRED_PYTHON (минимум
# поддержки): поднимается Оператором вместе с pyenv, не автоматически.
CURRENT_STABLE_PYTHON = (3, 13)

# Список допустимых исключений правила «сторонних пакетов нет» — записи
# вида (модуль, причина). Первое расширение (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8,
# требование 1, AC-2): переход на pytest (роадмап §3, фаза S, решение
# Оператора 05.09) требует трёх сторонних пакетов, воспроизводимо
# закреплённых `config.REQUIREMENTS_LOCK`. Имена — ИМПОРТИРУЕМЫЕ (не
# написание PyPI: дефис в имени пакета не бывает валидным идентификатором
# Python) — ровно то, что реально встретится в `import`-операторе, который
# ловит сканер `tests/test_invariants.py::StdlibOnlyImportsInvariantTest`.
THIRD_PARTY_EXCEPTIONS = (
    ("pytest", "переход на pytest (роадмап §3, фаза S, решение Оператора "
               "05.09) — тестовый фреймворк вместо unittest; сам раннер "
               "пульта на pytest — P1, вне этой задачи"),
    ("pytest_timeout", "плагин pytest — таймаут прогона одного теста, тот "
                       "же переход на pytest, что и запись выше"),
    ("xdist", "плагин pytest-xdist — параллельный прогон тестов, тот же "
             "переход на pytest; сам параллельный прогон в пульте — P2, "
             "вне этой задачи"),
)

# Таймаут ОТДЕЛЬНОГО теста pytest-timeout (SPEC 01M1TKP6AAY4W8GDGZNA9R0JZT,
# требование 4) — не таймаут ВСЕГО прогона (те остаются `config.py`:
# `ACCEPTANCE_TIMEOUT_SEC`/`FULL_SUITE_TIMEOUT_SEC`). `pyproject.toml`
# (`[tool.pytest.ini_options] timeout`, требование 6) несёт то же число
# литералом — TOML не умеет читать значение отсюда, синхронность двух
# мест сверяет `tests/test_stack.py`.
PER_TEST_TIMEOUT_SEC = 120

ToolRequirement = namedtuple("ToolRequirement", "minimum command")

def _provider_tools() -> dict:
    """Записи манифеста инструментов, объявленные самими провайдерами
    исполнителя роли (SPEC 01M2ZNTHSNFYSTF904P6SZTPYF, требование 6,
    AC-8): имя и минимальную версию CLI знает провайдер
    (`orchestrator/providers/`), форму записи манифеста — манифест.
    До этой задачи запись `claude` стояла здесь литералом, и второй
    провайдер правил бы этот файл руками.

    Импорт пакета провайдеров безопасен на пути импорта самого
    `stack.py` под интерпретатором 3.9 (докстринг у `REQUIRED_PYTHON`):
    пакет на уровне модуля тянет только стандартную библиотеку и себя
    же, а пульт читает лениво, внутри методов.
    """
    from .providers import cli_tools
    return {tool.name: ToolRequirement(tool.minimum, tool.command)
            for tool in cli_tools().values()}


REQUIRED_TOOLS = {
    "git": ToolRequirement((2, 30, 0), ("git", "--version")),
    "gh": ToolRequirement((2, 0, 0), ("gh", "--version")),
}
# Инструменты провайдеров — после общих: порядок ключей задаёт порядок
# строк `check_stack()` и порядок каталогов PATH роли (`DECLARED_TOOLS`
# ниже), а он не менялся с T019 (git, gh, claude).
REQUIRED_TOOLS.update(_provider_tools())

# Таблица «модель роли -> минимальная версия CLI claude» (SPEC
# 01M2XJKV84SQ9VEVR0VNVKDNGJ, требование 2): состав правит Оператор
# приложением, код только читает (`model_cli_verdict`). Модель, которой
# здесь нет, — не отказ ни в одной из точек чтения (предполёт шага,
# `check_stack`, разбор провала попытки): предупреждение «модель не в
# таблице совместимости», запуск как есть. Первая запись — инцидент
# 19.09 (01M2XFSJ1Z, 01M2XFSE8G): «API Error: 400 … does not support this
# model; version 2.1.251 or newer is required» за 0 токенов, три попытки
# по 120 с и эскалация — при причине, известной до запуска агента.
# Минимум инструмента `REQUIRED_TOOLS["claude"]` (1.0.0) остаётся рядом,
# не вместо: это нижняя граница самого CLI, а не связка с моделями.
MODEL_MIN_CLI_VERSION = {
    "claude-fable-5-1": (2, 1, 251),
}

# Тексты требований 3-4 той же SPEC — дословно, одним источником для
# предполётного отказа шага (`runner._refuse_before_start`), отказа после
# попытки класса «модель не поддерживается CLI» (`runner.
# _run_developer_step`) и строк `check_stack()`: три точки называют один и
# тот же исход одними и теми же словами, `auto` печатает подсказку из
# текста самого отказа (правка `auto.py`/`config.AUTO_STOP_*` — вне зон).
MODEL_UNSUPPORTED_PREFIX = "модель роли не поддерживается CLI"
MODEL_NOT_IN_TABLE_WARNING = "модель не в таблице совместимости"
CLI_UPGRADE_HINT = "обнови CLI либо смени model роли в roles.yaml"

# Инструменты, чей абсолютный путь `orchestrator.runner.role_env` резолвит
# через `shutil.which` для сборки PATH роли (SPEC
# 01M1RDCEF0JZ4AVQRE43JFH8TN, требование 1, AC-1/AC-2): те же три внешних
# CLI, что и `REQUIRED_TOOLS`, плюс `python3` — интерпретатор роли, для
# которого сам which-путь не используется (роль получает каталог
# `sys.executable` пульта, AC-3), но присутствие в PATH/системе всё равно
# проверяется тем же способом (AC-6 — отсутствие ЛЮБОГО из четырёх обязано
# останавливать шаг, включая python3).
DECLARED_TOOLS = ("python3",) + tuple(REQUIRED_TOOLS.keys())

# Белый список переменных окружения роли (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN,
# требования 2, 5, AC-4/AC-5): единственный источник для
# `orchestrator.runner.role_env` — роль не наследует `os.environ` Оператора
# целиком, только эти имена, у каждого есть причина.
ROLE_ENV_ALLOWLIST = {
    "HOME": "домашний каталог курируемого слоя роли (git-конфиг, CLI claude)",
    "CLAUDE_CONFIG_DIR": "путь курируемого `.claude/` роли (ADR-0003 п.14)",
    "GIT_AUTHOR_NAME": "автор коммита роли — предписанный git commit шага",
    "GIT_AUTHOR_EMAIL": "почта автора коммита роли",
    "GIT_COMMITTER_NAME": "коммитер коммита роли — то же требование git",
    "GIT_COMMITTER_EMAIL": "почта коммитера коммита роли",
    "CLAUDE_CODE_OAUTH_TOKEN": "токен подписки CLI claude для роли",
    "ANTHROPIC_API_KEY": "альтернативный канал токена CLI claude (ambient)",
    "LANG": "локаль — предсказуемый разбор вывода CLI claude/git",
    "TMPDIR": "временный каталог — CLI claude/git пишут туда рабочие файлы",
    "TERM": "тип терминала — вывод CLI claude зависит от него",
}

# Семейство локали (LC_ALL, LC_CTYPE, ...) — префиксом, а не перечислением:
# та же причина, что и у LANG выше, но имён в семействе много и заранее не
# перечислить (требование 2 SPEC называет «LANG/LC_*» одной строкой).
ROLE_ENV_ALLOWLIST_PREFIXES = {
    "LC_": "семейство локали (LC_ALL и т.п.) — тот же повод, что и LANG",
}

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

StackCheck = namedtuple("StackCheck", "name status detail")


def _interpreter_provenance_text() -> str:
    """Требование 7/AC-7: фактический путь исполняемого интерпретатора и
    факт существования `.artel/venv` — ДОПОЛНИТЕЛЬНАЯ строка проверки
    `python`, не влияющая на её статус (тот остаётся функцией только
    версии, см. `_python_check` ниже)."""
    venv_dir = Path(config.VENV_DIR)
    venv_state = "существует" if venv_dir.is_dir() else "не существует"
    return f"запущен {sys.executable}, .artel/venv ({venv_dir}) {venv_state}"


def _python_check() -> StackCheck:
    running = tuple(sys.version_info[:2])
    version_text = ".".join(str(part) for part in sys.version_info[:3])
    provenance = _interpreter_provenance_text()
    if running >= REQUIRED_PYTHON:
        return StackCheck("python", "ok", f"Python {version_text}; {provenance}")
    required_text = ".".join(str(part) for part in REQUIRED_PYTHON)
    return StackCheck(
        "python", "warn",
        f"Python {version_text} ниже минимальной {required_text}; {provenance}")


def version_text(version: tuple) -> str:
    """`(2, 1, 251)` -> `2.1.251` — одна форма печати версий для строк
    инструментов, строк моделей ролей и отказов шага в `runner`."""
    return ".".join(str(part) for part in version)


def _probe_tool(name: str, requirement: ToolRequirement):
    """Одна проверка инструмента манифеста И разобранная версия одним
    подпроцессом: `(StackCheck, Optional[tuple])`. Версия `None` —
    инструмент не найден или его вывод не распознан (статус проверки
    называет, что именно). Разобранную версию `claude` `check_stack()`
    отдаёт строкам моделей ролей (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ,
    требование 5) — без второго `claude --version` на каждую роль:
    `check_stack()` зовётся `runner._venv_interpreter_bin` на каждом шаге
    роли, лишние подпроцессы там платятся за каждый запуск агента."""
    command = list(requirement.command)
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return StackCheck(
            name, "fail",
            f"{name} не найден в PATH/системе (команда "
            f"`{' '.join(command)}` не выполнилась)"), None

    match = VERSION_RE.search(result.stdout)
    if match is None:
        return StackCheck(
            name, "warn",
            f"{name}: версия не распозналась в выводе `{' '.join(command)}`"), None

    version = tuple(int(part) for part in match.group(0).split("."))
    if version >= requirement.minimum:
        return StackCheck(name, "ok", f"{name} {match.group(0)}"), version
    return StackCheck(
        name, "warn",
        f"{name} {match.group(0)} ниже минимальной "
        f"{version_text(requirement.minimum)}"), version


def _tool_check(name: str, requirement: ToolRequirement) -> StackCheck:
    return _probe_tool(name, requirement)[0]


def installed_cli_version() -> Optional[tuple]:
    """Установленная версия CLI `claude` кортежем — тот же вызов и разбор
    `claude --version`, что у проверки инструмента манифеста (SPEC
    01M2XJKV84SQ9VEVR0VNVKDNGJ, требование 3: «уже разбирается
    `stack._tool_check`»); `None` — не определилась. Для предполётной
    сверки ОДНОЙ модели шага роли (`runner._refuse_before_start`) — не
    полный `check_stack()`, который тянул бы `git`/`gh`/venv-проверки ради
    одного числа."""
    return _probe_tool("claude", REQUIRED_TOOLS["claude"])[1]


ModelCliVerdict = namedtuple("ModelCliVerdict", "status detail")


def model_cli_verdict(model: str, installed: Optional[tuple]) -> ModelCliVerdict:
    """Сверка модели роли с установленной версией CLI по таблице
    `MODEL_MIN_CLI_VERSION` (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ, требования
    2, 3, 5): чистая функция, одна на три точки чтения таблицы.

    - модели нет в таблице — `warn` «модель не в таблице совместимости»
      (не отказ, AC-5/AC-8), значение `installed` не участвует;
    - версия CLI не определилась — `warn`: сверять не с чем, отказать
      по неизвестному числу было бы отказом по причине вне предмета;
    - `installed >= минимум` — `ok` («CLI X ≥ Y — ok»);
    - иначе — `fail` с текстом отказа требования 3 и подсказкой.
    """
    minimum = MODEL_MIN_CLI_VERSION.get(model)
    if minimum is None:
        return ModelCliVerdict(
            "warn",
            f"{MODEL_NOT_IN_TABLE_WARNING} (stack.MODEL_MIN_CLI_VERSION) — "
            f"с версией CLI не сверена, запуск как есть")
    if installed is None:
        return ModelCliVerdict(
            "warn",
            f"версия CLI не определилась (`claude --version`) — модель "
            f"требует claude ≥ {version_text(minimum)}, сверить не с чем")
    if installed >= minimum:
        return ModelCliVerdict(
            "ok",
            f"CLI {version_text(installed)} ≥ {version_text(minimum)} — ok")
    return ModelCliVerdict(
        "fail",
        f"{MODEL_UNSUPPORTED_PREFIX}: {model} требует claude ≥ "
        f"{version_text(minimum)}, установлен {version_text(installed)}; "
        f"{CLI_UPGRADE_HINT}")


def _model_checks(installed: Optional[tuple]) -> list:
    """Требование 5/AC-10: по строке на каждую роль `roles.yaml` с
    `executor: agent` и полем `model` — `ok`/`fail`/`warn` вердиктом
    `model_cli_verdict`. Роли без `executor: agent` (`orchestrator`,
    `verifier`) строки не получают даже с полем `model`: модель там не
    уходит в CLI. Нечитаемый `roles.yaml`/значение поля — одна строка
    `warn`, не исключение: `check_stack()` — диагностика, ронять её
    нечитаемой картой ролей значило бы прятать остальные строки.

    `roles` импортируется здесь, не на уровне модуля: `orchestrator/
    roles.py` несёт `str | None` в сигнатурах, а этот модуль обязан
    импортироваться интерпретатором 3.9 (докстринг у `REQUIRED_PYTHON`).
    Имя строки `model-<роль>` сознательно без «venv»: фильтр `runner.
    _venv_interpreter_bin` (`"venv" in c.name`) не должен её видеть.
    """
    from . import roles
    checks = []
    try:
        entries = roles.load()
    except roles.RolesError as exc:
        return [StackCheck("model-roles", "warn",
                           f"модели ролей не сверены: {exc}")]
    for role, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("executor") != "agent":
            continue
        if entry.get("model") is None:
            continue
        try:
            model = roles.model(role)
        except roles.RolesError as exc:
            checks.append(StackCheck(f"model-{role}", "warn",
                                     f"модель роли {role} не прочитана: {exc}"))
            continue
        verdict = model_cli_verdict(model, installed)
        checks.append(StackCheck(
            f"model-{role}", verdict.status,
            f"модель роли {role} {model}: {verdict.detail}"))
    return checks


def python_version_string() -> str:
    """Версия для `actions/setup-python` (`python-version`) — текущая
    стабильная версия основных джобов CI (01M1RDCCKBQMJ5G2K9ANJP059H,
    требование 1): `CURRENT_STABLE_PYTHON` в формате `major.minor`, без
    посторонних символов — так, как `setup-python` принимает значение.
    """
    return ".".join(str(part) for part in CURRENT_STABLE_PYTHON)


PINNED_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)\s*==\s*([A-Za-z0-9][A-Za-z0-9_.+-]*)\s*$")


def _normalize_package_name(name: str) -> str:
    """`PyTest-XDist` -> `pytest-xdist`: `_`/`-` и регистр взаимозаменяемы
    в написании имени пакета pip (PEP 503) — без нормализации сверка
    `requirements.lock` с выводом `pip freeze` ловила бы написание, не
    расхождение версии."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_pinned_versions(text: str) -> dict:
    """{нормализованное_имя: версия} из текста в формате `pip`
    (`name==version` построчно, остальное — комментарии/пустые строки —
    игнорируется). Общий разбор для файла закреплённых версий и вывода
    `pip freeze` — оба несут один и тот же формат строк."""
    pinned = {}
    for line in text.splitlines():
        match = PINNED_LINE_RE.match(line)
        if match is None:
            continue
        name, version = match.groups()
        pinned[_normalize_package_name(name)] = version
    return pinned


def _main_copy_root() -> Optional[Path]:
    """Корень ГЛАВНОЙ копии репозитория, если копия кода, которой ЭТОТ
    модуль реально исполняется, — git-worktree (ANSWER-6/ANSWER-7,
    01M1TKP6AAY4W8GDGZNA9R0JZT): `git rev-parse --git-common-dir`
    называет ОБЩИЙ `.git`-каталог (`<главная копия>/.git`) независимо от
    того, worktree это или сама главная копия — родитель этого каталога
    и есть искомый корень. Для самой главной копии совпадает с корнем
    кода (вырожденный, но безопасный случай — вызывающий код всё равно
    проверяет venv там же, где уже проверил его через `config.VENV_DIR`).

    Отправная точка — `_MODULE_ROOT` (расположение самого модуля), НЕ
    `config.ROOT` (ANSWER-7): `tests/sandbox.py::RealGitSandbox`
    подменяет `config.ROOT` на временный git-репозиторий, никак не
    связанный с настоящей копией пульта — `git rev-parse` из НЕГО не
    находит venv главной копии вообще (временный репозиторий её не
    несёт), хотя исполняемый код физически лежит в настоящей копии.
    `_MODULE_ROOT` не подменяется песочницами и указывает на копию
    кода, которая реально работает — ровно ту, чей venv нужен.

    `None` — git не ответил или ответ пуст: fail-closed, вызывающий код
    падает дальше на `sys.executable`, не гадает путь по несуществующему
    ответу."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=_MODULE_ROOT,
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    text = res.stdout.strip()
    if not text:
        return None
    git_dir = Path(text)
    if not git_dir.is_absolute():
        git_dir = (_MODULE_ROOT / git_dir).resolve()
    return git_dir.parent


def pytest_python_executable() -> str:
    """Интерпретатор, которым пульт запускает pytest
    (`orchestrator/acceptance.py::run()`/`run_full_suite()`, требование 8/
    AC-12) — голый `python3` резолвился бы по PATH ВЫЗЫВАЮЩЕГО процесса
    (гейты/`amend-tests` пульт зовёт из собственного окружения, не из
    `runner.role_env` — тот PATH только у роли), где сторонние пакеты
    пульта (`pytest-timeout` и т.п., `THIRD_PARTY_EXCEPTIONS` выше) могут
    отсутствовать (ANSWER-4, диагноз AC-7).

    Порядок поиска (ANSWER-6: планку пульт гоняет против worktree задачи,
    `acceptance.run(tdir, cwd=<worktree>)`, где `.artel/venv` не
    существует — этому venv соответствует только ГЛАВНАЯ копия, из
    которой worktree создан):

    1. `config.VENV_DIR/bin/python3` — venv рядом с `config.ROOT`, как
       у главной копии (прежнее поведение).
    2. иначе venv главной копии, найденный через `_main_copy_root()`.
    3. иначе `sys.executable` (интерпретатор самого процесса пульта) с
       предупреждением в stderr — venv не найден нигде, тот же принцип,
       что и WARN `_venv_exists_check` ниже, но для точки, где отсутствие
       venv молча меняет интерпретатор, а не просто печатает диагностику.
    """
    venv_python = Path(config.VENV_DIR) / "bin" / "python3"
    if venv_python.is_file():
        return str(venv_python)
    main_root = _main_copy_root()
    if main_root is not None:
        main_venv_python = main_root / ".artel" / "venv" / "bin" / "python3"
        if main_venv_python.is_file():
            return str(main_venv_python)
    print(f"[stack] venv не найден ни в {config.VENV_DIR}, ни в главной "
         f"копии репозитория — тесты пульта пойдут интерпретатором "
         f"{sys.executable}", file=sys.stderr)
    return sys.executable


def _venv_exists_check() -> StackCheck:
    """Требование 2/AC-8: `.artel/venv` отсутствует — WARN, называющий
    команду создания (`venv-sync`), а не молчаливая деградация."""
    if Path(config.VENV_DIR).is_dir():
        return StackCheck("venv", "ok", f"venv существует: {config.VENV_DIR}")
    return StackCheck(
        "venv", "warn",
        f"venv не создан ({config.VENV_DIR}) — `python3 artel.py venv-sync`")


def _venv_packages_check() -> StackCheck:
    """Требование 2/AC-7: версии пакетов `.artel/venv` сверены с файлом
    закреплённых версий (`pip freeze` внутри venv против
    `config.REQUIREMENTS_LOCK`) — WARN с именами РАСХОДЯЩИХСЯ пакетов, не
    общей фразой. Зовётся, только когда `_venv_exists_check` уже нашла
    venv на диске (иначе сверять нечего).

    `pytest` среди расходящихся пакетов (отсутствует вовсе или версия не
    та) — требование 8 (SPEC 01M1TKP6AAY4W8GDGZNA9R0JZT, AC-12) требует
    явного упоминания ЕГО доступности ролям/пульту отдельной фразой, не
    растворённого в общем перечне имён через запятую: раннер пульта сам
    на pytest (эта же задача) — его отсутствие в venv роли не «один из
    пакетов», а прямая невозможность прогнать приёмку/полный набор."""
    try:
        pinned = _parse_pinned_versions(
            Path(config.REQUIREMENTS_LOCK).read_text(encoding="utf-8"))
    except OSError as exc:
        return StackCheck(
            "venv-packages", "warn",
            f"файл закреплённых версий не прочитан ({config.REQUIREMENTS_LOCK}): {exc}")

    python = Path(config.VENV_DIR) / "bin" / "python"
    try:
        result = subprocess.run([str(python), "-m", "pip", "freeze"],
                                capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return StackCheck("venv-packages", "warn",
                          f"версии venv не прочитаны (`pip freeze`): {exc}")
    installed = _parse_pinned_versions(result.stdout)

    mismatched = sorted(name for name, version in pinned.items()
                        if installed.get(name) != version)
    if mismatched:
        detail = (f"версии расходятся с файлом закреплённых версий: "
                  f"{', '.join(mismatched)}")
        if "pytest" in mismatched:
            detail += ("; pytest недоступен ролям/пульту требуемой версии "
                      "в этом venv — пересобери venv-sync")
        detail += f"; тесты пульта запускает {pytest_python_executable()}"
        return StackCheck("venv-packages", "warn", detail)
    return StackCheck(
        "venv-packages", "ok",
        f"venv согласован с файлом закреплённых версий; тесты пульта "
        f"запускает {pytest_python_executable()}")


def check_stack() -> list:
    """Требование 4: по одной проверке на каждый инструмент манифеста
    (Python + `git`/`gh`/`claude`) — WARN при заниженной версии, FAIL при
    отсутствии инструмента. Требование 2 (SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8,
    AC-7/AC-8) добавляет проверку `.artel/venv`: существование и, если он
    есть, согласованность его пакетов с файлом закреплённых версий —
    вторая проверка не запускается без первой (нечего сверять без venv).
    Требование 5 (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ, AC-10) добавляет по
    строке на agent-роль `roles.yaml` с полем `model` — версия `claude`
    берётся из уже сделанной проверки инструмента (`_probe_tool`), не
    вторым подпроцессом.
    """
    checks = [_python_check()]
    claude_version = None
    for name, requirement in REQUIRED_TOOLS.items():
        check, version = _probe_tool(name, requirement)
        checks.append(check)
        if name == "claude":
            claude_version = version
    venv_check = _venv_exists_check()
    checks.append(venv_check)
    if venv_check.status == "ok":
        checks.append(_venv_packages_check())
    checks.extend(_model_checks(claude_version))
    return checks
