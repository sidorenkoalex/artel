"""Общее для нескольких файлов планки 01M3HP7RQEY0SBYNKQ902QD2CZ
(не `test_*.py`: подхватывается только импортом из `test_ac*.py`).

Шесть вещей, которые нужны больше чем одному критерию:

1. Сборка текста карты исполнителей из НАСТОЯЩЕЙ карты репозитория с
   заменой полей у названных ролей (`roles_text_with`) и с добавлением
   новой agent-роли (`add_agent_role`) — AC-3, AC-4, AC-5, AC-8 разыгрывают
   именно такие карты.
2. Копия дерева кода, в которой подменённый текст лежит настоящим
   `roles.yaml` (`repo_copy`). Копия, а не правка файла на месте: карту
   читают и `tests/sandbox.py`, и `tests/test_runner_role_model.py` путём,
   вычисленным от `__file__` собственного модуля, а правка файла
   репозитория на время прогона оставила бы дерево пульта испорченным при
   любом обрыве.
3. Прогон pytest подпроцессом (`run_pytest`) и несколько прогонов
   одновременно (`run_pytest_many`) — единственный способ отдать тестам
   `tests/` другую карту исполнителей, не импортируя их в процесс планки
   (`tests/sandbox.py` при импорте уводит `config.MODELS_LOCAL` в свой
   временный каталог и патчит `shutil.which` на весь процесс).
4. Перечень файлов `tests/`, читающих боевую карту (`map_reader_tests`) —
   тем же разбором AST, которым его сверяет AC-1, и та же функция называет
   МЕСТА чтения для AC-6.
5. Разбор перечня PLAN.md (`plan_entries`) — PLAN читается ТОЛЬКО из
   артефактной ветки (`gitcmd.show`): в среде прогона гейта на диске лежит
   один `acceptance_tests/`, и чтение PLAN.md с диска было бы зелёным у
   роли и красным на гейте.
6. Сверка файлов `tests/` с базой сравнения ветки (AC-7, AC-9): база —
   `gitcmd.diff_base` (тот же узел, которым пульт считает точку
   расхождения ветки задачи), разбор тестовых методов — `scripts/guard.py`
   (`qualified_test_methods`), чтобы «что считается тестовым методом»
   здесь и на гейте решалось одним кодом.

Ярусы, провайдер по умолчанию и модель яруса берутся ДИНАМИЧЕСКИ
(`models.TIERS`, `providers.DEFAULT_PROVIDER`, `models.
local_template_layer()`): перечень ярусов и шаблон локального слоя —
крутилки Оператора, и планка обязана пережить их поворот. Имена `analyst`
и `codex` — литералы: их называют сами критерии AC-5 и AC-7.
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (artifact_branch, config, gitcmd,  # noqa: E402
                          models, providers, yamlmini)
from scripts import guard  # noqa: E402

TASK_ID = "01M3HP7RQEY0SBYNKQ902QD2CZ"

#: Корень дерева КОДА под проверкой — тот же, от которого пульт читает
#: `roles.yaml` и запускает `tests/` (`orchestrator/config.py::ROOT`).
REPO_ROOT = Path(config.ROOT).resolve()

TESTS_DIR = "tests"
SANDBOX = "tests/sandbox.py"
ROLES_REL = "roles.yaml"

#: Роль и провайдер, названные критериями AC-5 и AC-7 прямым текстом.
ANALYST = "analyst"
CODEX = "codex"

#: Файл, чей исход критерий AC-5 называет отдельно: его предмет — маршрут
#: роли analyst, а не карта исполнителей, поэтому он же — обязательный
#: пункт перечня AC-1 и обязательный член списка «предмет не карта» AC-2.
ANALYST_TEST = "tests/test_analyst_role.py"

#: Каталоги, которые копии дерева не нужны: `.git` (копия и не должна быть
#: репозиторием — прогон в ней ничего не коммитит), `.artel` (рабочее
#: состояние пульта, включая worktree самой этой задачи), `tasks`
#: (артефакты; планка живёт в них и копировала бы себя).
_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".artel", "tasks", "__pycache__", ".pytest_cache", "*.pyc",
    ".mypy_cache", "node_modules", ".venv", "venv")

#: Строки итога pytest, называющие упавший/сломавшийся тест по nodeid
#: (`-rfE`): и провал, и ошибка — одинаково красный исход.
_FAILED_NODEID = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.M)


# ------------------------------------------------- карта исполнителей

def real_roles_text() -> str:
    """Настоящая карта исполнителей репозитория текстом."""
    return (REPO_ROOT / ROLES_REL).read_text(encoding="utf-8")


def role_entries(text: str) -> dict:
    """{роль: её запись} по тексту карты исполнителей."""
    return yamlmini.mapping(text).get("roles") or {}


def agent_roles(text: str) -> list:
    """Имена agent-ролей карты — тот же критерий, что у
    `orchestrator/stack.py::model_providers` (`executor: agent`)."""
    return sorted(role for role, entry in role_entries(text).items()
                  if isinstance(entry, dict) and entry.get("executor") == "agent")


def roles_text_with(text: str, overrides: dict) -> str:
    """Тот же текст карты исполнителей, где у каждой роли из `overrides`
    названные поля заменены заданными значениями (существующее поле
    снимается, новое встаёт сразу под заголовком роли — тот же приём, что
    `tests/test_runner_role_model.py::_roles_yaml_text` применяет к одной
    роли). Значение `None` — поле только снимается. Остальные строки файла
    не трогаются.

    `overrides` — {роль: {поле: значение|None}}.
    """
    out, current = [], None
    for line in text.splitlines(keepends=True):
        head = line.rstrip()
        is_header = (line.startswith("  ") and not line.startswith("    ")
                     and head.endswith(":"))
        if is_header:
            current = head.strip().rstrip(":")
            out.append(line)
            for field, value in (overrides.get(current) or {}).items():
                if value is not None:
                    out.append(f"    {field}: {value}\n")
            continue
        if line.strip() and not line.startswith("    "):
            current = None
        fields = overrides.get(current) or {}
        if fields and any(line.lstrip().startswith(f"{field}:")
                          for field in fields):
            continue
        out.append(line)
    return "".join(out)


def add_agent_role(text: str, name: str, fields: dict) -> str:
    """Тот же текст карты исполнителей плюс ещё одна роль `name` с полями
    `fields`, вписанная последней записью раздела `roles:` (AC-4).

    Конец раздела ищется по отступу, а не по имени соседнего ключа: что
    именно стоит в файле после ролей — дело Оператора."""
    lines = text.splitlines(keepends=True)
    inside, last = False, None
    for i, line in enumerate(lines):
        if not inside:
            if line.rstrip() == "roles:":
                inside = True
            continue
        if line.strip() and not line.startswith("  "):
            break
        if line.strip():
            last = i
    if last is None:
        raise AssertionError(f"в {ROLES_REL} не найден раздел 'roles:' с "
                            f"записями — добавлять роль некуда")
    block = [f"  {name}:\n"] + [f"    {k}: {v}\n" for k, v in fields.items()]
    return "".join(lines[:last + 1] + block + lines[last + 1:])


def alt_tier(text: str) -> str:
    """Ярус перечня `models.TIERS`, на котором в карте `text` не стоит ни
    одна agent-роль, — «ярус, отличный от остальных agent-ролей» из
    формулировки AC-7.

    Перечень ярусов берётся у `orchestrator/models.py`, а не литералом:
    это крутилка Оператора."""
    entries = role_entries(text)
    taken = {entries[role].get("model_tier") for role in agent_roles(text)}
    free = [tier for tier in models.TIERS if tier not in taken]
    if not free:
        raise AssertionError(
            f"agent-роли карты заняли все ярусы перечня "
            f"{', '.join(models.TIERS)} — яруса «отличного от остальных» в "
            f"перечне не осталось")
    return free[0]


def template_tier_model() -> str:
    """Модель первого яруса шаблона локального слоя пульта
    (`models.LOCAL_TEMPLATE`) — модель провайдера по умолчанию, какой её
    видит песочница `tests/` сегодня."""
    layer = models.local_template_layer()
    for tier in models.TIERS:
        if tier in layer.tiers:
            return layer.tiers[tier]
    raise AssertionError("шаблон локального слоя не называет ни одного "
                         "яруса перечня models.TIERS")


# ------------------------------------------------- перечень читателей карты

#: Чем выражено чтение боевой карты в тексте файла `tests/` — три пути,
#: перечисленные формулировкой AC-1 («прямо, через `config.ROLES`/
#: `config.MODELS` либо через помощники песочницы»).
_CONFIG_MAP_ATTRS = ("ROLES", "MODELS")
_MAP_LITERALS = ("roles.yaml", "models.yaml")
_SANDBOX_MAP_HELPERS = ("SANDBOX_ROLES_TEXT", "roles_text_on_default_provider",
                        "_roles_yaml_text", "_tiers_text", "_REAL_ROLES_TEXT")

#: Вызовы, которыми путь превращается в содержимое файла — ими и только
#: ими отличается ЧТЕНИЕ карты от упоминания её адреса в тексте отказа
#: (`f"{config.ROLES}: роль не описана"` картой не пользуется).
_READ_ATTRS = ("read_text", "read_bytes", "open")


def _addresses_real_map(node: ast.AST) -> bool:
    """Выражение `node` адресует боевой `roles.yaml`/`models.yaml`."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr in _CONFIG_MAP_ATTRS \
                and isinstance(sub.value, ast.Name) and sub.value.id == "config":
            return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                and sub.value in _MAP_LITERALS:
            return True
    return False


def map_read_sites(source: str) -> list:
    """Номера строк, где `source` ЧИТАЕТ содержимое боевой карты
    (`<адрес карты>.read_text()`/`open(<адрес карты>)`) — AC-6."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover - файл репозитория
        raise AssertionError(f"файл tests/ не разбирается: {exc}") from exc
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _READ_ATTRS \
                and _addresses_real_map(func.value):
            lines.append(node.lineno)
        elif isinstance(func, ast.Name) and func.id == "open" and node.args \
                and _addresses_real_map(node.args[0]):
            lines.append(node.lineno)
    return sorted(lines)


def models_local_assignments(source: str) -> list:
    """Номера строк, где `source` ПРИСВАИВАЕТ `config.MODELS_LOCAL` —
    выдача локального слоя моделей как фикстуры процесса (AC-6). Правка
    содержимого уже выданного слоя (`config.MODELS_LOCAL.write_text`) сюда
    не попадает: это сценарий теста, а не выдача фикстуры."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover - файл репозитория
        raise AssertionError(f"файл tests/ не разбирается: {exc}") from exc
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) \
                    and target.attr == "MODELS_LOCAL" \
                    and isinstance(target.value, ast.Name) \
                    and target.value.id == "config":
                lines.append(node.lineno)
    return sorted(lines)


def _uses_map_source(source: str) -> bool:
    """Файл пользуется боевой картой: читает её сам, называет
    `config.ROLES`/`config.MODELS`/адрес карты литералом либо берёт
    помощник песочницы, производный от боевой карты."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover - файл репозитория
        raise AssertionError(f"файл tests/ не разбирается: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _CONFIG_MAP_ATTRS \
                and isinstance(node.value, ast.Name) and node.value.id == "config":
            return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value in _MAP_LITERALS:
            return True
        if isinstance(node, ast.Name) and node.id in _SANDBOX_MAP_HELPERS:
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name in _SANDBOX_MAP_HELPERS:
                    return True
    return False


def tests_py_files() -> list:
    """Пути всех `tests/*.py` рабочей копии кода (включая `sandbox.py`)."""
    return sorted(p.relative_to(REPO_ROOT).as_posix()
                  for p in (REPO_ROOT / TESTS_DIR).rglob("*.py"))


def map_reader_tests() -> list:
    """Файлы `tests/test_*.py`, читающие настоящий `roles.yaml` или
    настоящий `models.yaml` в смысле формулировки AC-1 — плюс
    `ANALYST_TEST`, чью зависимость от поля `provider:` боевой карты
    называет AC-5 прямым текстом.

    `tests/sandbox.py` в перечень не входит: AC-1 говорит о ТЕСТАХ, а
    песочница — их общая обвязка (её собственное чтение карты — предмет
    AC-6, не AC-1)."""
    found = set()
    for rel in tests_py_files():
        name = rel.rsplit("/", 1)[-1]
        if not name.startswith("test_") or rel == SANDBOX:
            continue
        if _uses_map_source(text_on_disk(rel) or ""):
            found.add(rel)
    if (REPO_ROOT / ANALYST_TEST).is_file():
        found.add(ANALYST_TEST)
    return sorted(found)


def roles_named_in(rel: str, text: str) -> set:
    """Роли карты `text`, чьё имя встречается в тексте файла `rel` —
    «роли, которые тест называет» из формулировки AC-3."""
    source = text_on_disk(rel) or ""
    return {role for role in role_entries(text) if role in source}


def tests_module_imports(source: str) -> set:
    """Модули `tests.*`, которые импортирует `source`."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover - файл репозитория
        raise AssertionError(f"файл tests/ не разбирается: {exc}") from exc
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module \
                and node.module.startswith("tests"):
            found.add(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("tests."):
                    found.add(alias.name)
    return found


def module_name(rel: str) -> str:
    """`tests/test_x.py` -> `tests.test_x`."""
    return rel[:-len(".py")].replace("/", ".")


def subject_tests() -> set:
    """Файлы `tests/`, которые PLAN.md назвал тестами, чей предмет — сама
    боевая карта (AC-2). Пустое множество — PLAN.md ещё нет либо вердикта
    в нём нет: классификация только СУЖАЕТ перечень AC-3, поэтому её
    отсутствие делает планку строже, а не мягче."""
    text = plan_text()
    if not text:
        return set()
    return {rel for rel, entry in plan_entries(text).items()
            if entry.get("subject") is True}


def ac3_targets() -> list:
    """Файлы `tests/`, о которых говорит AC-3: читатели боевой карты, чей
    предмет — не карта ролей."""
    subject = subject_tests()
    return [rel for rel in map_reader_tests() if rel not in subject]


def known_skill(text: str) -> str:
    """Имя скила, который уже назван хотя бы одной ролью карты, — иначе
    подменённое значение `skills:` не было бы ДОПУСТИМЫМ (AC-3 говорит о
    допустимых значениях, а не о поломке карты)."""
    names = sorted({skill for entry in role_entries(text).values()
                    if isinstance(entry, dict)
                    for skill in (entry.get("skills") or [])})
    if not names:
        raise AssertionError(f"в {ROLES_REL} ни одна роль не называет "
                            f"скилов — допустимого значения `skills:` не "
                            f"из чего взять")
    return names[0]


def fallback_slot(text: str) -> str:
    """Слот токена, уже названный картой (`token_fallback:` либо слот
    первой роли) — допустимое значение поля `token_slot:`."""
    value = yamlmini.mapping(text).get("token_fallback")
    if isinstance(value, str) and value:
        return value
    for entry in role_entries(text).values():
        if isinstance(entry, dict) and entry.get("token_slot"):
            return entry["token_slot"]
    raise AssertionError(f"в {ROLES_REL} нет ни одного значения "
                        f"`token_slot:` — допустимое значение взять неоткуда")


def other_field_values(text: str, roles) -> dict:
    """Подмена ЧЕТЫРЁХ полей, названных AC-3 (`provider:`, `model_tier:`,
    `skills:`, `token_slot:`), у каждой роли из `roles` — другими
    ДОПУСТИМЫМИ значениями: провайдер из реестра `orchestrator/providers`,
    ярус из перечня `models.TIERS`, скил и слот, уже названные картой.

    Провайдер и ярус проставляются только agent-ролям: у роли, которую
    пульт не запускает агентом, этих полей нет и в боевом файле."""
    tier = alt_tier(text)
    skill = known_skill(text)
    slot = fallback_slot(text)
    agents = set(agent_roles(text))
    overrides = {}
    for role in roles:
        fields = {"skills": f"[{skill}]", "token_slot": slot}
        if role in agents:
            fields["provider"] = CODEX
            fields["model_tier"] = tier
        overrides[role] = fields
    return overrides


def inconsistent_roles_text(text: str) -> str:
    """Карта с НЕСОГЛАСОВАННОЙ правкой — ярус вне перечня `models.TIERS`,
    скил, которого нет в `skills/`, провайдер, которого нет в реестре
    `orchestrator/providers`: правка, от которой тест, чей предмет — сама
    карта, обязан покраснеть (AC-2).

    Три несогласованности сразу, а не одна: разные тесты карты сверяют её
    с разными реестрами, и одной правки могло бы не хватить ни одному из
    них."""
    agents = agent_roles(text)
    if not agents:
        raise AssertionError(f"в {ROLES_REL} нет agent-ролей — несогласовать "
                            f"нечего")
    broken = [{"model_tier": "net-takogo-yarusa"},
              {"skills": "[net-takogo-skila]"},
              {"provider": "net-takogo-provaydera"}]
    overrides = {}
    for i, role in enumerate(agents):
        overrides[role] = broken[i % len(broken)]
    return roles_text_with(text, overrides)


_BASELINE = {}


def baseline_failures(targets):
    """(множество упавших nodeid, список сломавшихся прогонов, отчёт)
    прогона `targets` на НАСТОЯЩЕЙ карте репозитория — исход, с которым
    AC-3 и AC-4 сравнивают исход на подменённой карте («тот же исход», а
    не «зелено»).

    Память на процесс: AC-3 и AC-4 спрашивают один и тот же перечень, а
    второй прогон того же набора не помещается в потолок прогона планки
    (`config.ACCEPTANCE_TIMEOUT_SEC`)."""
    key = tuple(targets)
    if key not in _BASELINE:
        results = run_pytest_many([(REPO_ROOT, list(targets))], timeout=110)
        _BASELINE[key] = (many_failures(results), many_broken(results),
                          many_report(results))
    return _BASELINE[key]


# ------------------------------------------------- PLAN.md

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(\S.*?)\s*$")
_BOLD_LABEL = re.compile(r"^\s{0,3}\*\*(.+?)\*\*\s*:?\s*$")
TEST_PATH = re.compile(r"tests/[\w./-]*\.py")
_FIELDS = re.compile(r"поля\s*[:—–-]+\s*(\S[^\n]*)", re.I)
_SUBJECT = re.compile(
    r"предмет(?:\s+карты)?\s*[:—–-]+\s*(да|нет)", re.I)

#: Форма пункта перечня PLAN.md, которую разбирает планка (AC-1, AC-2).
#: Названа здесь одной строкой, чтобы текст каждого отказа мог её
#: процитировать: догадываться о форме разработчику не нужно.
PLAN_ENTRY_SHAPE = ("- tests/test_x.py — поля: provider, model_tier — "
                    "предмет карты: нет")

#: Форма строки PLAN.md с числом тестов, падавших на карте AC-7 до правки
#: (AC-8) — разбирается по той же терпимой схеме: строка, где есть и «до
#: правки», и «падал», а число берётся первым после слова «падал».
PLAN_FAILED_COUNT_SHAPE = "на карте AC-7 до правки падало тестов: 1"

_BEFORE_FIX = re.compile(r"до\s+правки", re.I)
_FELL = re.compile(r"падал", re.I)
_INT = re.compile(r"\d+")


def plan_failed_count(text: str):
    """Число тестов, падавших на карте AC-7 до правки, из строки PLAN.md;
    `None` — такой строки нет."""
    for line in text.splitlines():
        fell = _FELL.search(line)
        if not fell or not _BEFORE_FIX.search(line):
            continue
        found = _INT.findall(line[fell.end():])
        if found:
            return int(found[0])
    return None


def plan_text():
    """Текст PLAN.md задачи — из АРТЕФАКТНОЙ ветки (`gitcmd.show`), не с
    диска: в среде прогона гейта пульт материализует только
    `acceptance_tests/`, и планка, читающая PLAN.md с диска рабочей копии,
    зелена у роли и красна на гейте. `None` — ветки или файла в ней нет."""
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                               f"tasks/{TASK_ID}/PLAN.md")
    return text


def plan_entries(text: str) -> dict:
    """{путь файла `tests/`: пункт перечня} по тексту PLAN.md.

    Пункт — строка, называющая путь, вместе со своими продолжениями (до
    пустой строки либо до строки со следующим путём): перечень одинаково
    может быть списком с переносами и таблицей. У пункта разбираются три
    вещи: заголовок раздела, под которым он стоит (AC-2 требует ОТДЕЛЬНОГО
    списка), перечисленные поля и вердикт «предмет карты: да|нет».

    Один и тот же путь может встретиться и в прозе, и в перечне: остаётся
    пункт, у которого есть вердикт, — иначе первый встреченный.
    """
    lines = text.splitlines()
    section = ""
    entries = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        heading = _HEADING.match(line) or _BOLD_LABEL.match(line)
        if heading:
            section = heading.groups()[-1].strip()
            i += 1
            continue
        paths = TEST_PATH.findall(line)
        if not paths:
            i += 1
            continue
        block = [line]
        j = i + 1
        while j < len(lines) and lines[j].strip() \
                and not TEST_PATH.search(lines[j]) \
                and not (_HEADING.match(lines[j]) or _BOLD_LABEL.match(lines[j])):
            block.append(lines[j])
            j += 1
        body = "\n".join(block)
        fields = _FIELDS.search(body)
        subject = _SUBJECT.search(body)
        for path in paths:
            entry = {"section": section, "line": i + 1,
                     "fields": fields.group(1).strip() if fields else None,
                     "subject": (subject.group(1).lower() == "да"
                                 if subject else None),
                     "text": body}
            old = entries.get(path)
            if old is None or (old["subject"] is None
                              and entry["subject"] is not None):
                entries[path] = entry
        i = j
    return entries


# ------------------------------------------------- копия дерева и прогоны

def repo_copy(tmpdir, roles_text: str, name: str = "code") -> Path:
    """Копия дерева кода в `tmpdir/name`, у которой `roles.yaml` — заданный
    текст. Возвращает корень копии: прогон pytest с этим `cwd` читает и
    код, и карту исполнителей именно оттуда."""
    dest = Path(tmpdir) / name
    shutil.copytree(REPO_ROOT, dest, ignore=_COPY_IGNORE, symlinks=True)
    (dest / ROLES_REL).write_text(roles_text, encoding="utf-8")
    return dest


def pytest_env(*extra_path) -> dict:
    """Окружение прогона-подпроцесса: без унаследованных настроек pytest
    родительского прогона и без записи `__pycache__` в проверяемое
    дерево."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in extra_path)
    return env


def _pytest_argv(targets, plugins) -> list:
    argv = [sys.executable, "-m", "pytest", *targets,
            "-p", "no:cacheprovider", "-q", "-rfE", "--tb=line"]
    for plugin in plugins:
        argv += ["-p", plugin]
    return argv


def run_pytest(cwd, targets, plugins=(), path_extra=(), timeout=240):
    """Прогон pytest подпроцессом: `targets` — пути файлов либо nodeid,
    `plugins` — модули `-p`, `path_extra` — каталоги в `PYTHONPATH`
    (корень дерева плюс каталог плагина). Возвращает
    `subprocess.CompletedProcess`."""
    cwd = Path(cwd)
    return subprocess.run(_pytest_argv(targets, plugins), cwd=str(cwd),
                          env=pytest_env(cwd, *path_extra),
                          capture_output=True, text=True, timeout=timeout)


def run_pytest_many(jobs, timeout=240) -> list:
    """Несколько прогонов pytest ОДНОВРЕМЕННО, по одному подпроцессу на
    job. `jobs` — последовательность (cwd, targets); возвращает список
    (cwd, targets, returncode, вывод) в том же порядке.

    Одновременно, а не по очереди: у каждого сценария AC-3 своя карта
    исполнителей, то есть своя копия дерева, и последовательный обход
    восьми копий не укладывается в потолок прогона планки
    (`config.ACCEPTANCE_TIMEOUT_SEC`). Набор `tests/` к этому готов — тот
    же способ, каким его гоняет CI (`pytest -n auto`).
    """
    jobs = [(Path(cwd), list(targets)) for cwd, targets in jobs if targets]
    procs = []
    for cwd, targets in jobs:
        procs.append(subprocess.Popen(
            _pytest_argv(targets, ()), cwd=str(cwd), env=pytest_env(cwd),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
    deadline = time.monotonic() + timeout
    results = []
    for (cwd, targets), proc in zip(jobs, procs):
        left = max(1.0, deadline - time.monotonic())
        try:
            out = proc.communicate(timeout=left)[0]
        except subprocess.TimeoutExpired:
            proc.kill()
            out = (proc.communicate()[0] or "") + \
                f"\n<прогон не уложился в {timeout}с>"
        results.append((cwd, targets, proc.returncode, out))
    return results


def failed_nodeids(output: str) -> list:
    """Nodeid упавших и сломавшихся тестов из итога прогона (`-rfE`)."""
    return _FAILED_NODEID.findall(output)


def run_report(result) -> str:
    """Вывод прогона для сообщения об ошибке ассерта — оба потока и код
    возврата: без них красная планка называла бы только «не ноль»."""
    return (f"returncode={result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}")


def many_report(results) -> str:
    """То же для `run_pytest_many`: по одному блоку на прогон."""
    blocks = []
    for cwd, targets, code, out in results:
        blocks.append(f"--- {' '.join(targets)} (returncode={code}) ---\n{out}")
    return "\n".join(blocks)


def many_failures(results) -> set:
    """Множество nodeid упавших и сломавшихся тестов по всем прогонам
    `run_pytest_many`. Только nodeid — исходы двух прогонов сравниваются
    между собой, а состав целей у них разный (AC-3 бьёт файлы на группы,
    базовый прогон — нет)."""
    bad = set()
    for _cwd, _targets, _code, out in results:
        bad.update(failed_nodeids(out))
    return bad


def many_broken(results) -> list:
    """Прогоны `run_pytest_many`, вернувшие ненулевой код БЕЗ единого
    названного nodeid: сломался сбор, упал импорт, процесс не уложился в
    срок. Такой прогон нельзя сравнивать по составу упавших тестов — о
    нём нужно сказать отдельно."""
    return [(targets, code, out) for _cwd, targets, code, out in results
            if code != 0 and not failed_nodeids(out)]


# ------------------------------------------------- плагины-мутации (AC-7)

#: Мутация 1: поле `provider:` карты исполнителей не читается вовсе — у
#: каждой роли провайдер по умолчанию. Ровно это состояние кода делало бы
#: перевод роли analyst на Codex невидимым для тестов.
PROVIDER_BLIND_PLUGIN = "artel_provider_blind"

PROVIDER_BLIND_SOURCE = '''
"""Плагин прогона: провайдер роли не зависит от поля `provider:` карты."""
from orchestrator import providers, roles

_original = roles.provider


def _default_provider(role):
    _original(role)
    return providers.DEFAULT_PROVIDER


roles.provider = _default_provider
'''

#: Мутация 2: локальный слой называет модель провайдера по умолчанию у
#: КАЖДОГО яруса — состояние песочницы до починки задачи, названное
#: разделом «Контекст» SPEC («локальный слой моделей песочницы называет
#: всем ярусам модели Claude»).
DEFAULT_LAYER_PLUGIN = "artel_default_model_layer"

DEFAULT_LAYER_SOURCE = '''
"""Плагин прогона: у каждого яруса локального слоя — модель провайдера по
умолчанию, какую называет шаблон слоя пульта."""
from orchestrator import models

_original = models.load_local


def _template_model():
    layer = models.local_template_layer()
    for tier in models.TIERS:
        if tier in layer.tiers:
            return layer.tiers[tier]
    raise AssertionError("шаблон локального слоя не называет ни один ярус")


def _default_layer(*args, **kwargs):
    layer = _original(*args, **kwargs)
    model = _template_model()
    return layer._replace(tiers={tier: model for tier in layer.tiers})


models.load_local = _default_layer
'''


def write_plugin(tmpdir, name: str, source: str) -> Path:
    """Кладёт плагин-мутацию во временный каталог и отдаёт этот каталог
    (его же нужно добавить в `PYTHONPATH` прогона)."""
    plugin_dir = Path(tmpdir) / f"plugin-{name}"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / f"{name}.py").write_text(source, encoding="utf-8")
    return plugin_dir


# ------------------------------------------------- сверка с базой ветки

def main_base_ref() -> str:
    """Точка расхождения ветки задачи с главной веткой — тем же узлом,
    каким её считает сам пульт (`gitcmd.diff_base`: `origin/<main>`, если
    ref заведён, иначе локальная главная ветка). Пустая строка — git не
    ответил."""
    branch = gitcmd.current_branch() or "HEAD"
    return gitcmd.diff_base(branch) or ""


def text_at(ref: str, rel: str):
    """Текст файла `rel` в дереве `ref`; `None` — файла там нет."""
    return gitcmd.show(ref, rel)[0]


def text_on_disk(rel: str):
    """Текст файла `rel` рабочей копии кода; `None` — файла нет."""
    path = REPO_ROOT / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def changed_tests_files(ref: str) -> list:
    """Пути `tests/*.py`, чей текст на диске отличается от текста в дереве
    `ref` (включая удалённые и добавленные)."""
    base = gitcmd.ls_tree_files(ref, TESTS_DIR) or []
    base = [p for p in base if p.endswith(".py")]
    disk = tests_py_files()
    return [rel for rel in sorted(set(base) | set(disk))
            if text_at(ref, rel) != text_on_disk(rel)]


def changed_test_methods(base_source, head_source) -> list:
    """Квалифицированные имена тестовых методов HEAD-версии файла, которых
    в базовой версии нет вовсе либо текст которых изменился, — та же пара
    критериев («новая» и «изменённая»), которой пользуется
    `scripts/guard.py::test_functions_without_mutation_claim`."""
    if head_source is None:
        return []
    head = guard.qualified_test_methods(head_source)
    base = guard.qualified_test_methods(base_source) if base_source else {}
    changed = []
    for name, node in head.items():
        base_node = base.get(name)
        if base_node is not None and \
                ast.get_source_segment(head_source, node) == \
                ast.get_source_segment(base_source, base_node):
            continue
        changed.append(name)
    return sorted(changed)


def nodeid(rel: str, qualified: str) -> str:
    """`tests/test_x.py` + `Class::test_y` -> nodeid pytest."""
    return f"{rel}::{qualified}"


def default_provider() -> str:
    """Провайдер по умолчанию пульта — динамически, не литералом."""
    return providers.DEFAULT_PROVIDER
