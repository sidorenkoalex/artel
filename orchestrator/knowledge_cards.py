"""Карточки знаний: форма, чтение по видам, сверка места, команда `knowledge`, журнал обращений, подсказка миссии.

Знание, которого нет в коде (правило, причина, чем гейт его ловит,
инциденты), хранится карточками (SPEC 01M4S0JVB85W9TY1ESGNBH97FP, К-4а;
ADR-0003 пп. 3а, 3е, 3з). Два вида: системные — файл
`config.KNOWLEDGE_CARD_SYSTEM_REL` репозитория пульта (защищённый путь),
выдаются задачам всех проектов; проектные — файл поля `knowledge` записи
проекта в `targets.yaml`, выдаются только задачам этого проекта.

Образец формы (каркас для Оператора):

cards:
  merge-lock-order:
    where: [orchestrator/merge_lock.py, orchestrator/fsm_merge_gate.py::merge_gate, orchestrator/advance_gates/*.py]
    rule: "Лок мержа берётся до чтения головы main: иначе гонка двух approve"
    why: инцидент двух одновременных мержей — второй перетёр первый
    check: "tests/test_invariants.py::MergeOnlyFromMergeGateTest"
    example: "with merge_lock.held(conn): head = gitcmd.rev_parse('origin/main')"
    incidents: [01M290PS4Z, T043]

Ключ карточки — её тема, `[a-z0-9][a-z0-9-]{0,47}`. `where` — непустой
список масок пути (`*` — внутри сегмента, `**` — любое число сегментов) и
элементов `<путь>::<символ>` (символ — имена через точку). `rule`, `why` —
обязательные непустые строки; `check` (пусто — «гейтом не ловится»),
`example` — необязательные строки; `incidents` — необязательный список.
Идентификаторы инцидентов — только с буквой: число в потоковом списке
`yamlmini` читает числом, а кавычки в потоковом списке не разбираются.
Двойная кавычка внутри значения не допускается: `yamlmini` не снимает
экранирование, и значение молча разошлось бы с написанным.

Формат — подмножество YAML `yamlmini.mapping`. Повтор ключа карточки или
поля `yamlmini` молча затирает последним значением, поэтому повторы (и
отступы, на которых проход их не увидел бы) ищет отдельный построчный
проход `_line_pass`.

Вызывающие (SPEC 01M4S0K2MJRMVMQWKATAME3RHR, К-4б): `doc-commit`
(`notes.py`) — проверка формы файла `knowledge/<имя>.yaml` до коммита;
команда роли `knowledge <id> <запрос>` (`artel.py`, `cmd_knowledge`) —
карточки по месту с пометкой свежести и одной записью журнала обращения;
строка-подсказка миссии (`role_prompt.py`, `hint_line`) — только ключи тем;
досыл очереди журнала (`suite_lock.py`) и гейт выхода `tests_writing` —
постоянный автор и действия записей этой команды. Бриф текста карточек
не получает.
"""
import ast
import json
import os
import re
import sqlite3
import stat
import sys
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import config, gitcmd, repo_context, targets, yamlmini

SAMPLE = """\
cards:
  merge-lock-order:
    where: [orchestrator/merge_lock.py, orchestrator/fsm_merge_gate.py::merge_gate, orchestrator/advance_gates/*.py]
    rule: "Лок мержа берётся до чтения головы main: иначе гонка двух approve"
    why: инцидент двух одновременных мержей — второй перетёр первый
    check: "tests/test_invariants.py::MergeOnlyFromMergeGateTest"
    example: "with merge_lock.held(conn): head = gitcmd.rev_parse('origin/main')"
    incidents: [01M290PS4Z, T043]
"""

SYSTEM = "system"
PROJECT = "project"

# Закрытый перечень кодов причины отказа (требование 7): «неизвестный
# раздел», «отступ» и прочие случаи формы — подробности кода FIELD_FORM.
GIT_NO_ANSWER = "git не ответил"
FILE_UNREADABLE = "файл не прочитан"
FILE_UNPARSED = "файл не разобран"
KEY_FORM = "ключ не по форме"
FIELD_FORM = "поле не по форме"
DUPLICATE = "повтор"
SIZE_LIMIT = "предел размера"
COUNT_LIMIT = "предел числа карточек"
REFUSAL_CODES = (GIT_NO_ANSWER, FILE_UNREADABLE, FILE_UNPARSED, KEY_FORM,
                 FIELD_FORM, DUPLICATE, SIZE_LIMIT, COUNT_LIMIT)

CARDS = "cards"
NOT_SET_UP = "not_set_up"
REFUSED = "refused"

SECTION = "cards"
KEY_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_PROJECT_FIELD_RE = re.compile(
    r"\.artel/projects/(?P<project>[^/\\]+)/knowledge/(?P<name>[^/\\]+)")

REQUIRED_TEXT = ("rule", "why")
OPTIONAL_TEXT = ("check", "example")
FIELDS = ("where",) + REQUIRED_TEXT + OPTIONAL_TEXT + ("incidents",)

CARD_INDENT = 2
FIELD_INDENT = 4

QUERY_FORM = "запрос формы <путь>, <путь>::<символ> или ::<символ>"


@dataclass(frozen=True)
class Card:
    kind: str
    key: str
    where: tuple[str, ...]
    rule: str
    why: str
    check: str
    example: str
    incidents: tuple[str, ...]


@dataclass(frozen=True)
class Refusal:
    code: str
    detail: str
    file: str
    key: str | None = None
    field: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class KindRead:
    kind: str
    outcome: str
    cards: tuple[Card, ...] = ()
    file: str | None = None
    sha256: str | None = None
    refusal: Refusal | None = None


@dataclass(frozen=True)
class QueryRefusal:
    detail: str


def refusal_text(refusal: Refusal) -> str:
    """Отказ одной строкой: файл, ключ, поле, строка, код и подробность —
    для вывода команды, где поля записи не видны по отдельности."""
    place = [refusal.file]
    if refusal.key is not None:
        place.append(f"карточка {refusal.key}")
    if refusal.field is not None:
        place.append(f"поле {refusal.field}")
    if refusal.line is not None:
        place.append(f"строка {refusal.line}")
    return f"{', '.join(place)}: {refusal.code} — {refusal.detail}"


def is_card_file(rel: str) -> bool:
    """Путь ровно `knowledge/<имя>.yaml` — файл карточек репозитория пульта
    (имя — та же форма, что у поля `knowledge` в `targets.check`)."""
    head, sep, name = rel.partition("/")
    return (head == "knowledge" and bool(sep)
            and bool(targets.KNOWLEDGE_FILE_NAME.fullmatch(name)))


# --- проверка формы ---

def _line_key(content: str) -> str:
    """Ключ строки так, как его отдаёт `yamlmini`: текст до первого `:` с
    обрезкой пробелов по краям (`a :` и `a:` — один ключ)."""
    return content.partition(":")[0].strip()


def _line_pass(text: str, file: str) -> tuple[Refusal | None, dict, dict]:
    """Построчный проход: неизвестный раздел, отступ, повторы (требование 3).

    Возвращает отказ (или `None`) и номера строк: ключ карточки → строка,
    `(ключ, поле)` → строка — их называют отказы проверки значений."""
    card_lines: dict = {}
    field_lines: dict = {}
    seen_section = False
    current = None
    for number, raw in enumerate(text.splitlines(), 1):
        content = raw.strip()
        if not content or content.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key = _line_key(content)
        if indent == 0:
            if key == SECTION and not seen_section:
                seen_section = True
                continue
            what = f"повтор «{SECTION}:»" if key == SECTION else f"«{key}»"
            return Refusal(FIELD_FORM, f"неизвестный раздел {what}: верхний "
                           f"уровень — ровно один раздел «{SECTION}»", file,
                           line=number), card_lines, field_lines
        if not seen_section or indent not in (CARD_INDENT, FIELD_INDENT):
            return Refusal(FIELD_FORM, f"отступ {indent}: ключ карточки — "
                           f"отступ {CARD_INDENT}, поле — {FIELD_INDENT}",
                           file, line=number), card_lines, field_lines
        if indent == CARD_INDENT:
            if key in card_lines:
                return Refusal(DUPLICATE, f"повтор ключа карточки «{key}» "
                               f"(строки {card_lines[key]} и {number})", file,
                               key=key, line=number), card_lines, field_lines
            card_lines[key] = number
            current = key
            continue
        if current is None:
            return Refusal(FIELD_FORM, f"отступ {indent}: поле вне карточки",
                           file, line=number), card_lines, field_lines
        if (current, key) in field_lines:
            return Refusal(DUPLICATE, f"повтор поля «{key}» карточки "
                           f"«{current}» (строки "
                           f"{field_lines[(current, key)]} и {number})", file,
                           key=current, field=key,
                           line=number), card_lines, field_lines
        field_lines[(current, key)] = number
    return None, card_lines, field_lines


def _not_string(value: object) -> str:
    if isinstance(value, bool):
        return "значение не строка: логическое значение"
    if isinstance(value, (int, float)):
        return "значение не строка: число"
    return f"значение не строка: {type(value).__name__}"


def _text_error(value: object, required: bool) -> str | None:
    if value is None:
        return "пусто" if required else None
    if not isinstance(value, str):
        return _not_string(value)
    if required and not value.strip():
        return "пусто"
    if '"' in value:
        return "двойная кавычка внутри значения"
    return None


def _path_error(path: str) -> str | None:
    if path.startswith("/"):
        return "путь абсолютный"
    if path.startswith("./"):
        return "путь с префиксом ./"
    if ".." in path.split("/"):
        return "путь с .."
    return None


def _where_item_error(item: object) -> str | None:
    if item is None:
        return "элемент where пуст"
    if not isinstance(item, str):
        return f"элемент where: {_not_string(item)}"
    if not item.strip():
        return "элемент where пуст"
    if '"' in item:
        return "элемент where: двойная кавычка внутри значения"
    path, sep, symbol = item.partition("::")
    if sep:
        if not path:
            return f"элемент where «{item}»: путь пуст"
        if "*" in path:
            return f"элемент where «{item}»: * в пути формы путь::символ"
        if not SYMBOL_RE.fullmatch(symbol):
            return f"элемент where «{item}»: символ не по форме"
    error = _path_error(path)
    return f"элемент where «{item}»: {error}" if error else None


def _list_error(name: str, value: object) -> str | None:
    if not isinstance(value, list):
        return f"{name} не список"
    if name == "where":
        if not value:
            return "where — пустой список"
        for item in value:
            error = _where_item_error(item)
            if error:
                return error
        return None
    for item in value:
        error = _text_error(item, required=True)
        if error:
            return f"элемент incidents: {error}"
    return None


def _check_card(key: str, body: object, kind: str, file: str,
                card_lines: dict, field_lines: dict) -> Card | Refusal:
    line = card_lines.get(key)
    if not KEY_RE.fullmatch(key):
        return Refusal(KEY_FORM, f"ключ «{key}» не по форме "
                       f"{KEY_RE.pattern}", file, key=key, line=line)
    if not isinstance(body, dict):
        return Refusal(FIELD_FORM, "значение карточки не отображение", file,
                       key=key, line=line)
    for name in body:
        if name not in FIELDS:
            return Refusal(FIELD_FORM, f"неизвестное поле «{name}» (известны: "
                           f"{', '.join(FIELDS)})", file, key=key, field=name,
                           line=field_lines.get((key, name)))
    for name in ("where",) + REQUIRED_TEXT:
        if name not in body:
            return Refusal(FIELD_FORM, f"нет поля «{name}»", file, key=key,
                           field=name, line=line)
    for name, value in body.items():
        if name in REQUIRED_TEXT or name in OPTIONAL_TEXT:
            error = _text_error(value, required=name in REQUIRED_TEXT)
        elif name == "incidents" and value is None:
            error = None
        else:
            error = _list_error(name, value)
        if error:
            return Refusal(FIELD_FORM, f"{name}: {error}", file, key=key,
                           field=name, line=field_lines.get((key, name)))
    card = Card(kind=kind, key=key, where=tuple(body["where"]),
                rule=body["rule"], why=body["why"],
                check=body.get("check") or "",
                example=body.get("example") or "",
                incidents=tuple(body.get("incidents") or ()))
    size = (len(card.rule) + len(card.why) + len(card.check)
            + len(card.example) + sum(len(item) for item in card.incidents))
    limit = config.KNOWLEDGE_CARD_MAX_CHARS
    if size > limit:
        return Refusal(SIZE_LIMIT, f"суммарная длина текстовых полей {size}, "
                       f"предел {limit}", file, key=key, line=line)
    return card


def check_text(text: str, file: str, kind: str) -> tuple[Card, ...] | Refusal:
    """Карточки файла либо первый отказ формы (требования 1-4). Чистая
    функция: `file` только называется в отказе."""
    try:
        data = yamlmini.mapping(text)
    except yamlmini.YamlError as exc:
        return Refusal(FILE_UNPARSED, str(exc), file)
    refusal, card_lines, field_lines = _line_pass(text, file)
    if refusal is not None:
        return refusal
    if SECTION not in data:
        return Refusal(FIELD_FORM, f"нет раздела «{SECTION}»", file)
    section = data[SECTION]
    if section is None:
        return ()
    if not isinstance(section, dict):
        return Refusal(FIELD_FORM, f"раздел «{SECTION}» не отображение", file)
    limit = config.KNOWLEDGE_CARD_MAX_PER_FILE
    if len(section) > limit:
        return Refusal(COUNT_LIMIT, f"карточек {len(section)}, предел {limit}",
                       file)
    cards = []
    for key, body in section.items():
        result = _check_card(key, body, kind, file, card_lines, field_lines)
        if isinstance(result, Refusal):
            return result
        cards.append(result)
    return tuple(cards)


# --- чтение по видам ---

def _from_text(kind: str, file: str, text: str) -> KindRead:
    # Внутри функции: верхний импорт замкнул бы цикл
    # notes → knowledge_cards → brief → store → models → notes.
    from . import brief
    result = check_text(text, file, kind)
    if isinstance(result, Refusal):
        return KindRead(kind, REFUSED, file=file, refusal=result)
    return KindRead(kind, CARDS, cards=result, file=file,
                    sha256=brief.component_hash(text))


def _refused(kind: str, file: str | None, code: str, detail: str) -> KindRead:
    return KindRead(kind, REFUSED, file=file,
                    refusal=Refusal(code, detail, file or ""))


def _read_main(kind: str, rel: str) -> KindRead:
    """Файл `knowledge/` репозитория пульта — с головы `config.MAIN_BRANCH`
    главной копии, не с диска (требование 8): карточки — правило системы,
    как скилы, и незакоммиченная правка в выдачу не попадает."""
    root = config.ROOT
    # `.git` рабочей копии `git worktree` — файл, и репозиторий там есть.
    if not (root / ".git").exists():
        return KindRead(kind, NOT_SET_UP, file=rel)
    # Отсутствие файла различается через `ls-tree`: `gitcmd.show` отвечает
    # `(None, причина)` и на отсутствие, и на отказ git.
    res = gitcmd.in_repo(root, "ls-tree", "--name-only", config.MAIN_BRANCH,
                         "--", rel)
    if res is None or res.returncode != 0:
        detail = "" if res is None else (res.stderr or "").strip()[:200]
        return _refused(kind, rel, GIT_NO_ANSWER,
                        f"ls-tree {config.MAIN_BRANCH} -- {rel}: "
                        f"{detail or 'нет ответа'}")
    if not res.stdout.strip():
        return KindRead(kind, NOT_SET_UP, file=rel)
    text, reason = gitcmd.show(config.MAIN_BRANCH, rel, repo=root)
    if text is None:
        return _refused(kind, rel, FILE_UNREADABLE,
                        f"show {config.MAIN_BRANCH}:{rel}: {reason}")
    return _from_text(kind, rel, text)


def _read_disk(kind: str, project: str, rel: str) -> KindRead:
    """Файл `.artel/projects/<проект>/knowledge/<имя>.yaml` — с диска
    области проектов (требование 9). Ссылка, специальный файл и выход по
    `resolve()` из каталога знаний проекта — отказ: проектные карточки
    читаются только из каталога пульта, не из клона и не из чужого проекта."""
    match_ = _PROJECT_FIELD_RE.fullmatch(rel)
    if match_ is None or match_["project"] != project:
        return _refused(kind, rel, FILE_UNREADABLE,
                        "путь поля knowledge не в каталоге знаний проекта")
    root = repo_context.projects_root()
    if root == repo_context.NO_AREA:
        # Песочница с подменённым корнем: боевая область не читается.
        return KindRead(kind, NOT_SET_UP, file=rel)
    name = match_["name"]
    path = root / project / "knowledge" / name
    try:
        info = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return KindRead(kind, NOT_SET_UP, file=rel)
    except OSError as exc:
        return _refused(kind, rel, FILE_UNREADABLE, f"lstat: {exc}")
    if stat.S_ISLNK(info.st_mode):
        return _refused(kind, rel, FILE_UNREADABLE, "файл — символьная ссылка")
    if not stat.S_ISREG(info.st_mode):
        return _refused(kind, rel, FILE_UNREADABLE, "не обычный файл")
    try:
        expected = root.resolve() / project / "knowledge" / name
        if path.resolve(strict=True) != expected:
            return _refused(kind, rel, FILE_UNREADABLE,
                            "путь вышел по resolve() из каталога знаний "
                            "проекта")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return _refused(kind, rel, FILE_UNREADABLE, "не обычный файл")
            chunks = []
            while chunk := os.read(fd, 1 << 16):
                chunks.append(chunk)
        finally:
            os.close(fd)
        text = b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as exc:
        return _refused(kind, rel, FILE_UNREADABLE, f"не UTF-8: {exc}")
    except OSError as exc:
        return _refused(kind, rel, FILE_UNREADABLE, str(exc))
    return _from_text(kind, rel, text)


def _project_field(project: str) -> str | None:
    """Поле `knowledge` записи проекта; `None` — поля нет, записи нет или
    `targets.yaml` не годен: чтение карточек не падает на сломанном файле."""
    try:
        entry = targets.target(project)
    except targets.TargetsError:
        return None
    value = entry.get("knowledge")
    return value if isinstance(value, str) else None


def read_cards(project: str) -> tuple[KindRead, KindRead]:
    """Карточки задачи проекта `project` по видам: системный вид первым,
    проектный вторым (требования 6-9)."""
    system = _read_main(SYSTEM, config.KNOWLEDGE_CARD_SYSTEM_REL)
    rel = _project_field(project)
    if rel is None:
        own = KindRead(PROJECT, NOT_SET_UP)
    elif project == config.DEFAULT_TARGET:
        own = _read_main(PROJECT, rel)
    else:
        own = _read_disk(PROJECT, project, rel)
    return system, own


# --- сверка места ---

def _query_error(query: str) -> str | None:
    limit = config.KNOWLEDGE_CARD_QUERY_MAX_CHARS
    if len(query) > limit:
        return f"длина {len(query)} больше {limit}"
    if any(unicodedata.category(ch) == "Cc" for ch in query):
        return "управляющий символ"
    if query.count("::") > 1:
        return "больше одного ::"
    path, sep, symbol = query.partition("::")
    if not path and not sep:
        return "пустой запрос"
    if sep and not symbol:
        return "символ пуст"
    if path:
        return _path_error(path)
    return None


def _symbol_covers(element: str, query: str) -> bool:
    """Символ элемента равен символу запроса или его префиксу по точкам."""
    return query == element or query.startswith(element + ".")


def _element_matches(element: str, path: str, symbol: str | None) -> bool:
    from .project_profile import mask_matches
    e_path, sep, e_symbol = element.partition("::")
    if not sep:
        return bool(path) and mask_matches(element, path)
    if path and e_path != path:
        return False
    return symbol is None or _symbol_covers(e_symbol, symbol)


def match(query: str, cards: Iterable[Card]) -> tuple[Card, ...] | QueryRefusal:
    """Карточки, чьё `where` подходит под место запроса (требование 10):
    системные, затем проектные, внутри вида — по ключу. Файлов не читает."""
    error = _query_error(query)
    if error:
        return QueryRefusal(f"{QUERY_FORM}, относительный путь без .., без "
                            f"префикса ./ и управляющих символов, не длиннее "
                            f"{config.KNOWLEDGE_CARD_QUERY_MAX_CHARS}: {error}")
    path, sep, symbol = query.partition("::")
    wanted = symbol if sep else None
    found = [card for card in cards
             if any(_element_matches(element, path, wanted)
                    for element in card.where)]
    found.sort(key=lambda card: (card.kind != SYSTEM, card.key))
    return tuple(found)


# --- команда `knowledge`, журнал обращений, подсказка миссии (К-4б) ---
#
# Автор и действия записей команды не совпадают ни с одним автором и
# действием, которым верит читатель журнала (`spec_audit`, `brief`,
# `review`, гейты): запись обращения пишет процесс роли, и доверенной она
# стать не должна (SPEC 01M4S0K2MJRMVMQWKATAME3RHR, требование 5).
JOURNAL_ACTOR = "knowledge-cards"
ACCESS_ACTION = "knowledge: обращение роли"
HINT_REFUSAL_ACTION = "knowledge: темы подсказки не прочитаны"
ACCESS_DETAIL_PREFIX = "обращение к карточкам: "
# Запись «предел исчерпан» — того же действия: признак «уже писалась» и
# исключение из счёта к пределу — по этому префиксу `detail` (требование 6).
EXHAUSTED_PREFIX = "предел журнала обращений исчерпан"
SYSTEM_REFUSAL_DETAIL_MAX = 200

STALE = "возможно устарела"
UNCHECKED = "свежесть не проверена"
NO_WORKTREE = "рабочей копии задачи нет"

QUERY_SYNTAX = "<путь> | <путь>::<символ> | ::<символ>"

_TRY_NODES = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())


def task_project(t) -> str | None:
    """Проект задачи по строке задачи (требования 2, 11): ключ `target` есть
    и непуст — он; есть, но NULL или пуст — `config.DEFAULT_TARGET`, как
    `store.task_target`; ключа нет (словарь без него) — `None`, проектных
    карточек нет."""
    if "target" not in t.keys():
        return None
    return t["target"] or config.DEFAULT_TARGET


def _read_kinds(project: str | None) -> tuple[KindRead, ...]:
    if project is None:
        return (_read_main(SYSTEM, config.KNOWLEDGE_CARD_SYSTEM_REL),)
    return read_cards(project)


def access_tally(rows: Iterable) -> tuple[int, bool]:
    """(число записей обращения, есть ли запись «предел исчерпан») среди
    записей журнала задачи — одна формула счёта для команды и досыла
    очереди (требования 6-7): запись «предел исчерпан» к пределу не идёт."""
    plain, exhausted = 0, False
    for row in rows:
        if row["action"] != ACCESS_ACTION:
            continue
        if (row["detail"] or "").startswith(EXHAUSTED_PREFIX):
            exhausted = True
        else:
            plain += 1
    return plain, exhausted


def exhausted_detail() -> str:
    return (f"{EXHAUSTED_PREFIX}: {config.KNOWLEDGE_CARD_JOURNAL_MAX_PER_TASK} "
            f"записей обращения на задачу, дальнейшие обращения не пишутся")


# --- свежесть элемента `where` формы `p::s` ---

def _defined_names(body: list, prefix: str) -> Iterable[str]:
    """Имена, определённые в теле: `def`, `async def`, `class` (и вложенно —
    тело класса через точку), цели `Assign`/`AnnAssign`/`AugAssign`, в том
    числе в телах `if`/`try` (требование 10)."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield prefix + node.name
        elif isinstance(node, ast.ClassDef):
            yield prefix + node.name
            yield from _defined_names(node.body, f"{prefix}{node.name}.")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                yield from _target_names(target, prefix)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            yield from _target_names(node.target, prefix)
        elif isinstance(node, ast.If):
            yield from _defined_names(node.body + node.orelse, prefix)
        elif isinstance(node, _TRY_NODES):
            handlers = [stmt for handler in node.handlers
                        for stmt in handler.body]
            yield from _defined_names(node.body + handlers + node.orelse
                                      + node.finalbody, prefix)


def _target_names(target: ast.AST, prefix: str) -> Iterable[str]:
    if isinstance(target, ast.Name):
        yield prefix + target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _target_names(element, prefix)
    elif isinstance(target, ast.Starred):
        yield from _target_names(target.value, prefix)


class _Freshness:
    """Проверка свежести карточек одного вызова: файл читается и
    разбирается один раз, сколько бы карточек на него ни ссылалось.

    Источник — рабочая копия задачи, кроме системных карточек задачи
    внешнего проекта: их правило — о коде пульта, и сверяются они с головой
    `main` главной копии пульта (требование 9). Код проекта не
    импортируется и не исполняется: только `ast` и чтение текста."""

    def __init__(self, task_id: str, project: str):
        from . import workspace
        self.project = project
        self.worktree = workspace.path(task_id, project)
        self._files: dict = {}

    def marks(self, card: Card) -> list[str]:
        found = []
        for element in card.where:
            path, sep, symbol = element.partition("::")
            if not sep:
                continue
            mark = self._element(card.kind, path, symbol)
            if mark and mark not in found:
                found.append(mark)
        return found

    def _element(self, kind: str, path: str, symbol: str) -> str | None:
        source = ("main" if kind == SYSTEM
                  and self.project != config.DEFAULT_TARGET else "worktree")
        key = (source, path)
        if key not in self._files:
            self._files[key] = (self._load_main(path) if source == "main"
                                else self._load_worktree(path))
        state, value = self._files[key]
        if state == "missing":
            return f"{STALE}: файл {path} не найден"
        if state == "unchecked":
            return f"{UNCHECKED}: {value}"
        if state == "py":
            found = symbol in value
        else:
            last = symbol.rsplit(".", 1)[-1]
            found = re.search(rf"(?<!\w){re.escape(last)}(?!\w)",
                              value) is not None
        return None if found else f"{STALE}: символ {symbol} не найден в {path}"

    def _load_worktree(self, path: str) -> tuple[str, object]:
        root = self.worktree
        if not root.is_dir():
            return "unchecked", NO_WORKTREE
        limit = config.KNOWLEDGE_CARD_STALE_FILE_MAX_BYTES
        try:
            resolved = (root / path).resolve(strict=True)
        except FileNotFoundError:
            return "missing", None
        except (OSError, RuntimeError) as exc:
            return "unchecked", f"путь не разрешён ({type(exc).__name__})"
        # Ссылка где угодно по пути (каталог или сам файл) уводит `resolve()`
        # от прямой склейки — такой файл не читается.
        if resolved != root.resolve() / Path(path):
            return "unchecked", "ссылка в пути"
        try:
            info = os.lstat(resolved)
            if not stat.S_ISREG(info.st_mode):
                return "unchecked", "не обычный файл"
            if info.st_size > limit:
                return "unchecked", f"файл больше {limit} байт"
            fd = os.open(resolved, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    return "unchecked", "не обычный файл"
                data = os.read(fd, limit + 1)
            finally:
                os.close(fd)
        except OSError as exc:
            return "unchecked", f"файл не прочитан ({type(exc).__name__})"
        if len(data) > limit:
            return "unchecked", f"файл больше {limit} байт"
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return "unchecked", "файл не UTF-8"
        return self._parse(path, text)

    def _load_main(self, path: str) -> tuple[str, object]:
        root = config.ROOT
        if not (root / ".git").exists():
            return "unchecked", "репозитория пульта нет"
        # Отсутствие файла отличается от отказа git тем же `ls-tree`, что у
        # чтения карточек (`_read_main`); режим и размер — до чтения.
        res = gitcmd.in_repo(root, "ls-tree", config.MAIN_BRANCH, "--", path)
        if res is None or res.returncode != 0:
            return "unchecked", GIT_NO_ANSWER
        line = res.stdout.strip()
        if not line:
            return "missing", None
        fields = line.partition("\t")[0].split()
        if len(fields) != 3:
            return "unchecked", GIT_NO_ANSWER
        mode, kind, sha = fields
        if mode == "120000":
            return "unchecked", "символьная ссылка"
        if kind != "blob":
            return "unchecked", "не обычный файл"
        size = gitcmd.in_repo(root, "cat-file", "-s", sha)
        if size is None or size.returncode != 0:
            return "unchecked", GIT_NO_ANSWER
        try:
            size_bytes = int(size.stdout.strip())
        except ValueError:
            return "unchecked", GIT_NO_ANSWER
        limit = config.KNOWLEDGE_CARD_STALE_FILE_MAX_BYTES
        if size_bytes > limit:
            return "unchecked", f"файл больше {limit} байт"
        text, _reason = gitcmd.show(config.MAIN_BRANCH, path, repo=root)
        if text is None:
            return "unchecked", FILE_UNREADABLE
        return self._parse(path, text)

    @staticmethod
    def _parse(path: str, text: str) -> tuple[str, object]:
        if not path.endswith(".py"):
            return "text", text
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
            return "unchecked", type(exc).__name__
        return "py", frozenset(_defined_names(tree.body, ""))


# --- команда `knowledge <id> <запрос>` ---

def _open_db_readonly(arg: str):
    """(соединение `mode=ro`, строка задачи); отказ — `sys.exit`. Команда не
    зовёт `store.db()` для чтения: у шага на Codex БД закрыта на запись."""
    from . import store
    if not config.DB.is_file():
        sys.exit(f"knowledge: БД пульта {config.DB} не найдена")
    conn = store.db_readonly()
    try:
        return conn, store.get_task(conn, arg)
    except BaseException:
        conn.close()
        raise


def _role_label(in_role: bool) -> str:
    if not in_role:
        return "оператор"
    from . import roles
    role = os.environ.get(config.ARTEL_ROLE_ENV) or ""
    try:
        known = roles.load()
    except roles.RolesError:
        known = {}
    return role if role in known else "роль не определена"


def _card_lines(card: Card, marks: list[str]) -> list[str]:
    lines = [f"[{card.kind}] {card.key}",
             f"  where: {', '.join(card.where)}",
             f"  rule: {card.rule}",
             f"  why: {card.why}",
             f"  check: {card.check or 'гейтом не ловится'}"]
    if card.example:
        lines.append(f"  example: {card.example}")
    if card.incidents:
        lines.append(f"  incidents: {', '.join(card.incidents)}")
    lines.extend(f"  {mark}" for mark in marks)
    return lines


def _status_line(read: KindRead, project: str) -> str | None:
    """Строка вида, которая не цитирует файл карточек: «нет поля», «не
    заведён», код отказа. `None` — вид прочитан."""
    if read.outcome == NOT_SET_UP:
        if read.file is None:
            return (f"карточки {read.kind}: нет поля knowledge в записи "
                    f"проекта {project} (targets.yaml)")
        return f"карточки {read.kind}: файл {read.file} не заведён"
    if read.outcome == REFUSED:
        return f"карточки {read.kind} не прочитаны: {read.refusal.code}"
    return None


def _journal_write(task_id: str, action_detail: str) -> None:
    """Запись обращения коротким соединением `store.db()`; БД закрыта на
    запись — в очередь `suite_lock` (требование 4). Не удалась и очередь —
    одна строка в stderr: выдача карточек от журнала не зависит."""
    from . import store, suite_lock, watch
    try:
        conn = store.db()
        try:
            store.journal(conn, task_id, JOURNAL_ACTOR, ACCESS_ACTION,
                          action_detail)
        finally:
            conn.close()
        return
    except (sqlite3.Error, OSError):
        pass
    try:
        if suite_lock.defer_journal({"task_id": task_id,
                                     "action": ACCESS_ACTION,
                                     "detail": action_detail,
                                     "session_id": None, "at": store.now()}):
            return
        reason = "действие не принято очередью"
    except OSError as exc:
        reason = str(exc)
    print(f"knowledge: запись журнала обращения не внесена и не отложена: "
          f"{watch.safe_text(reason)}", file=sys.stderr)


def cmd_knowledge(rest: list) -> None:
    """Карточки по месту запроса для задачи `<id>` (требования 1-10): только
    чтение, кроме одной записи журнала обращения постоянным автором."""
    from . import brief, runner, store, watch
    if len(rest) != 2:
        sys.exit(f"knowledge: синтаксис — knowledge <id> <{QUERY_SYNTAX}>")
    arg, query = rest
    in_role = runner.in_role_environment()
    env_task = os.environ.get(config.ARTEL_TASK_ENV) or ""
    # Роль, распознанная только по дому, не называет свою задачу — сверять
    # `<id>` не с чем (требование 1).
    if in_role and not env_task:
        sys.exit("knowledge: шаг роли без ARTEL_TASK — команда отказывает "
                 "при любом id задачи")
    conn, t = _open_db_readonly(arg)
    try:
        task_id = t["id"]
        if in_role and task_id != env_task:
            sys.exit(f"knowledge: задача {watch.safe_text(arg)} — не задача "
                     f"шага роли ({watch.safe_text(env_task)})")
        found = match(query, ())
        if isinstance(found, QueryRefusal):
            sys.exit(f"knowledge: запрос отвергнут — {found.detail}")
        project = task_project(t) or config.DEFAULT_TARGET
        reads = _read_kinds(project)
        cards = [card for read in reads if read.outcome == CARDS
                 for card in read.cards]
        found = match(query, cards)
        limit = config.KNOWLEDGE_CARD_OUTPUT_MAX
        shown, hidden = found[:limit], found[limit:]
        freshness = _Freshness(task_id, project)
        marks = {(card.kind, card.key): freshness.marks(card)
                 for card in shown}

        print(f"knowledge {task_id}: запрос {watch.safe_text(query)} "
              f"(только чтение)")
        outside: list[str] = []
        inside: list[str] = []
        for read in reads:
            status = _status_line(read, project)
            if status is not None:
                outside.append(status)
            if read.outcome != REFUSED:
                continue
            detail = refusal_text(read.refusal)
            if read.kind == SYSTEM:
                outside[-1] += f" — {detail[:SYSTEM_REFUSAL_DETAIL_MAX]}"
            else:
                inside.append(f"подробность отказа: {detail}")
        for card in shown:
            target = outside if card.kind == SYSTEM else inside
            target.extend(_card_lines(card, marks[(card.kind, card.key)]))
        if hidden:
            rest_line = (f"ещё {len(hidden)} по запросу (уточни путь): "
                         f"{', '.join(card.key for card in hidden)}")
            # Ключи проектных карточек — текст их файла: строка с ними идёт
            # внутрь границы недоверенных данных.
            if any(card.kind == PROJECT for card in hidden):
                inside.append(rest_line)
            else:
                outside.append(rest_line)
        if not shown:
            outside.append("совпавших карточек нет")
        print("\n".join(outside))
        if inside:
            print(brief.BOUNDARY_INSTRUCTION, end="")
            print(brief.wrap_boundary(brief.new_run_id(), "\n".join(inside)))

        n_system = sum(1 for card in shown if card.kind == SYSTEM)
        n_stale = sum(1 for card in shown
                      if any(mark.startswith(STALE)
                             for mark in marks[(card.kind, card.key)]))
        codes = [f"{read.kind}={read.refusal.code}" for read in reads
                 if read.outcome == REFUSED]
        hashes = [f"{read.kind}={read.sha256}" for read in reads
                  if read.sha256]
        detail = (f"{ACCESS_DETAIL_PREFIX}роль {_role_label(in_role)}; "
                  f"запрос {json.dumps(watch.safe_text(query), ensure_ascii=False)}; "
                  f"выдано: системных {n_system}, проектных "
                  f"{len(shown) - n_system}; помечено «{STALE}»: {n_stale}; "
                  f"отказы вида: {', '.join(codes) or 'нет'}; "
                  f"sha256: {', '.join(hashes) or 'нет'}")
        plain, exhausted = access_tally(store.task_steps(conn, task_id))
    finally:
        conn.close()
    if plain < config.KNOWLEDGE_CARD_JOURNAL_MAX_PER_TASK:
        _journal_write(task_id, detail)
    elif not exhausted:
        _journal_write(task_id, exhausted_detail())
    if codes:
        sys.exit(1)


# --- строка-подсказка миссии ---

def hint_line(task_id: str, project: str | None) -> tuple[str, list]:
    """(строка миссии о команде, отказы чтения [(вид, код)]) — требование
    11: ключи тем без текста карточек, коды отказа из закрытого перечня без
    цитат файла."""
    keys: list[str] = []
    refused = []
    for read in _read_kinds(project):
        if read.outcome == CARDS:
            keys.extend(sorted(card.key for card in read.cards))
        elif read.outcome == REFUSED:
            refused.append((read.kind, read.refusal.code))
    cap = config.KNOWLEDGE_CARD_HINT_MAX_KEYS
    topics = ", ".join(keys[:cap]) if keys else "тем нет"
    if len(keys) > cap:
        topics += f" и ещё {len(keys) - cap}"
    pult = config.ROOT / "orchestrator" / "artel.py"
    line = (f"Карточки знаний о ловушках и правилах места — `python3 {pult} "
            f"knowledge {task_id} <{QUERY_SYNTAX}>`, только чтение; темы: "
            f"{topics}")
    for kind, code in refused:
        line += f"; карточки {kind} не прочитаны: {code}"
    return line, refused
