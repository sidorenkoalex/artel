"""Строка мандата Оператора: один разбор на все три места и проверка
элементов при записи ответа (SPEC 01M3GKJBXEBHB6ZA48J7VG8Z8W, требования
1-2).

До этой задачи «маркер → список элементов» разбирался трижды независимо —
в `orchestrator/answer.py`, в гейте зон и в гейте неослабления тестов, — и
элемент, не совпавший ни с одним путём, гейтом МОЛЧА не засчитывался
(прецедент 26.09: «Расширение зон разрешено: orchestrator/artel.py —
только разбор аргументов…» — элемент после пути пояснение, не путь).
Здесь живёт единственный разбор (`elements`) и единственное правило
годности элемента (`refusals`); накопление элементов по строкам и по
файлам ANSWER остаётся за потребителями — разбирается ОДНА строка.

Оба маркера мандата стоят тоже здесь, а не по прежним адресам
(`zones._ZONES_MANDATE_MARKER`, `test_integrity.
TEST_WEAKENING_MANDATE_MARKER` — теперь реэкспорт): проверка требования 2
обязана перебрать оба вида мандата, а при маркерах по старым адресам
импорт был бы циклом (`mandate` -> `test_integrity` -> `zones` ->
`mandate`).
"""
import re
from pathlib import Path

from scripts import guard

from .. import gitcmd

# Маркер мандата Оператора на расширение зон (SPEC 01M1P9QCHPHSCEA6TK13PV85SP,
# ANSWER-1.md, п.2, канал ADR-0012) — строка в ЛЮБОМ ANSWER-n.md задачи,
# разбирается только по этому префиксу; свободный текст ANSWER не
# анализируется.
_ZONES_MANDATE_MARKER = "Расширение зон разрешено:"

# Маркер мандата Оператора на ослабление тестов (SPEC
# 01M3FQ2V77QNK95Z599DM124QN, требование 4) — по образцу маркера зон выше:
# разбирается только по этому префиксу и перечню через запятую, свободный
# текст ANSWER (в том числе ссылка на основание) не анализируется.
TEST_WEAKENING_MANDATE_MARKER = "Ослабление тестов разрешено:"

# Оба вида мандата, и ровно два: новых видов задача не вводит («Не входит»
# SPEC). Порядок — порядок появления в пульте, на результат не влияет.
MANDATE_MARKERS = (_ZONES_MANDATE_MARKER, TEST_WEAKENING_MANDATE_MARKER)

# Путь репозитория в элементе мандата: буквы, цифры, `_`, `-`, `.` и `/`.
# Абсолютный путь отсекается требованием к первому символу, сегмент `..` —
# отдельной проверкой в `_looks_like_path` (регулярному выражению его
# удобнее не знать).
_PATH_RE = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_./-]*\Z")

# Часть квалифицированного имени за `::` (`<Класс>`, `<метод>`) — то же
# подмножество, что даёт `guard.qualified_test_methods` на именах питона.
_NAME_PART_RE = re.compile(r"[A-Za-z0-9_]+\Z")


def _split_zone_paths(raw) -> list[str]:
    """Список путей через запятую — тот же формат, что несёт `zones:` части
    1 (01M1NKVPD2A79PQ6K0JVV1B2Q1) и строки `Пути:`/`Расширение зон
    разрешено:` ANSWER-1.md этой задачи. `raw` — `None`/пустая строка (поле
    не заполнено) даёт пустой список, не ошибку."""
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def elements(line: str, marker: str) -> list[str] | None:
    """Элементы ОДНОЙ строки мандата `marker`: `strip` строки, отсечение
    префикса-маркера, деление по запятым, отбрасывание пустых элементов
    (требование 1).

    `None` — строка мандатом `marker` не является (после `strip` не
    начинается с маркера): маркер, процитированный в середине абзаца, за
    мандат не принимается — то же правило `startswith`, что несли все три
    прежних разбора.

    Пустой список — маркер есть, а непустого элемента за ним нет ни
    одного. Отличать этот случай от `None` нужно требованию 2г: голый
    маркер — ошибка Оператора, а не «строка не о мандате», и прежние
    разборы, дававшие `[]` на оба случая, поймать её не могли.
    """
    stripped = line.strip()
    if not stripped.startswith(marker):
        return None
    return _split_zone_paths(stripped[len(marker):])


def _looks_like_path(text: str) -> bool:
    """Элемент похож на путь репозитория (требование 2а): без абсолютного
    корня и без сегмента `..`. Запись зоны-каталога с `/` на конце
    (`tests/`, как пишутся `config.COMMON_ZONES`) — законная форма."""
    if not _PATH_RE.match(text):
        return False
    return ".." not in text.split("/")


def in_weakening_scope(path: str) -> bool:
    """Путь принадлежит области гейта неослабления тестов — `tests/**/*.py`
    на любой глубине. Формула живёт здесь, а `test_integrity._in_scope`
    её зовёт: проверка при записи обязана отказывать ровно тому, что гейт
    ЗАВЕДОМО не засчитает (REVIEW итерация 1, R1-F2). Элемент «tests/» или
    «tests/fixtures/data.json» под областью не лежит, с находкой гейта
    (сверка точным вхождением) не совпадёт никогда — и без этого правила
    молча не срабатывал бы ровно так же, как элемент-пояснение 26.09."""
    return bool(path) and path.startswith("tests/") and path.endswith(".py")


def _qualified_name_ok(name: str) -> bool:
    """Часть элемента мандата ослабления за `::` — непустая цепочка имён
    питона через тот же разделитель (`<Класс>`, `<Класс>::<метод>`), в той
    же форме, в которой находку называет `guard.qualified_test_methods`."""
    parts = name.split(guard.TEST_NAME_SEP)
    return all(_NAME_PART_RE.match(part) for part in parts)


def _tree_has(element: str, files: list[str]) -> bool:
    """Элемент существует в дереве как файл ИЛИ как каталог. Каталога как
    отдельной записи в дереве git нет вовсе — он существует ровно тем, что
    под ним лежат файлы, поэтому вторая половина проверки ищет префикс.
    `/` на конце снимается до сравнения (требование 2б, «с учётом `/` на
    конце»)."""
    norm = element.rstrip("/")
    if norm in files:
        return True
    prefix = norm + "/"
    return any(f.startswith(prefix) for f in files)


def _tree_files(code_branch: str | None,
                repo: Path | None = None) -> list[str] | None:
    """Пути дерева КОДОВОЙ ветки задачи; `None` — git не ответил (ветки
    ещё нет, сбой команды). Проверка существования на `None` не
    применяется — см. `refusals`.

    `repo` — клон проекта, в котором живёт `code_branch` (ADR-0021 п.1)."""
    if not code_branch:
        return None
    return gitcmd.ls_tree_files(code_branch, ".", repo=repo)


def _element_refusal(element: str, marker: str,
                     files: list[str] | None) -> str | None:
    """Причина, по которой элемент мандата не годен; `None` — годен.

    Порядок — порядок подпунктов требования 2: сначала общее правило 2а
    (пробел, непохожесть на путь), затем правило своего маркера — 2б для
    мандата зон, 2в для мандата ослабления.
    """
    if any(ch.isspace() for ch in element):
        return ("элемент содержит пробел — пояснение пишется отдельным "
                "абзацем, а не внутри элемента")

    if marker == TEST_WEAKENING_MANDATE_MARKER:
        path, sep, name = element.partition(guard.TEST_NAME_SEP)
        if not _looks_like_path(path):
            return "не похож на путь репозитория"
        if not in_weakening_scope(path):
            return ("путь вне области tests/**/*.py — гейт неослабления "
                    "тестов другие пути не рассматривает")
        if sep and not _qualified_name_ok(name):
            return f"нарушена форма «путь{guard.TEST_NAME_SEP}имя»"
        # Существование пути тут не проверяется СОЗНАТЕЛЬНО (требование 2б
        # названо только для мандата зон): штатный предмет этого мандата —
        # как раз удалённый файл тестов, которого в дереве ветки уже нет.
        return None

    if not _looks_like_path(element):
        return "не похож на путь репозитория"
    if files is not None and not _tree_has(element, files):
        return "в дереве кодовой ветки задачи нет ни файла, ни каталога"
    return None


def refusals(text: str, code_branch: str | None,
            repo: Path | None = None) -> list[str]:
    """Причины отказа по ВСЕМ строкам мандатов текста файла ответа
    Оператора (требование 2); пустой список — файл проверку прошёл.

    Перебираются все строки и оба маркера, а не первая строка одного
    маркера, как это делал прежний разбор `answer` («Материалы» SPEC):
    прецедент 26.09 повторился бы в файле, где исправный мандат стоит
    первым, а ошибочный — вторым. Каждая причина названа тройкой «строка,
    элемент, причина», чтобы Оператор правил ту строку, которую написал.

    `code_branch` — кодовая ветка задачи, дерево которой отвечает на
    вопрос существования пути (требование 2б). Git на неё не ответил
    (ветки ещё нет, сбой команды) — проверка существования НЕ
    применяется, остальные правила применяются всегда: проверка при записи
    — удобство Оператора перед рубежом, а сам рубеж (гейт зон) остаётся
    fail-closed и на этом же сбое откажет переходу. Обратное решение
    запрещало бы отвечать на эскалацию при молчащем git.

    `repo` — клон проекта, в котором живёт `code_branch` (ADR-0021 п.1).
    """
    files = _tree_files(code_branch, repo)
    found: list[str] = []
    for line in text.splitlines():
        for marker in MANDATE_MARKERS:
            parsed = elements(line, marker)
            if parsed is None:
                continue
            shown = line.strip()
            if not parsed:
                found.append(f"строка «{shown}»: после маркера нет ни одного "
                             f"непустого элемента")
                break
            for element in parsed:
                reason = _element_refusal(element, marker, files)
                if reason is not None:
                    found.append(f"строка «{shown}»: элемент «{element}» — "
                                 f"{reason}")
            break
    return found
