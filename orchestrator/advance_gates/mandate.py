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

# Маркер мандата Оператора на зависимости мержа (SPEC
# 01M44EP0D47F498TEE08MNGBYT, требование 3): элементы — id задач (полные или
# префиксы) либо одно слово «нет»; строка задаёт новое значение
# `merge_after` целиком. Элементы — не пути: их проверяет по БД
# `orchestrator/merge_after.py`, а не правила путей ниже.
MERGE_AFTER_MANDATE_MARKER = "Зависимости мержа:"

# Все виды мандата. Порядок — порядок появления в пульте, на результат не
# влияет.
MANDATE_MARKERS = (_ZONES_MANDATE_MARKER, TEST_WEAKENING_MANDATE_MARKER,
                   MERGE_AFTER_MANDATE_MARKER)

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


def _task_decision(conn, task_id: str | None):
    """Решение профиля тестов проекта задачи (`project_profile.for_task`) —
    то же, на котором гейт неослабления берёт свою область; `None` — задача
    не передана (так зовут узел юнит-тесты), действует область артели
    (SPEC 01M55VDVVDVWW2MTJ01F88N5FM, требования 1-2)."""
    if conn is None or not task_id:
        return None
    # Ленивый импорт: `project_profile` тянет `repo_context`/`targets`,
    # которые этому узлу разбора без задачи не нужны.
    from .. import project_profile
    return project_profile.for_task(conn, task_id)


def _weakening_scope_refusal(path: str, decision) -> str | None:
    """Причина отказа пути элемента мандата ослабления по области гейта;
    `None` — путь в области.

    Решение профиля — отказ или пропуск — гейт неослабления на нём мандат
    не засчитает ни при каком пути (отказ перехода либо гейт не
    выполняется), поэтому отказ элементу несёт причину решения, а не текст
    об области, ложно указывающий на ошибку пути."""
    if decision is None:
        if in_weakening_scope(path):
            return None
        return ("путь вне области tests/**/*.py — гейт неослабления "
                "тестов другие пути не рассматривает")
    if decision.refusal:
        return (f"гейт неослабления тестов мандат не засчитает — решение "
                f"профиля тестов проекта: отказ: {decision.refusal}")
    if decision.profile is None:
        return (f"гейт неослабления тестов у проекта не выполняется, "
                f"засчитывать мандат нечему — решение профиля тестов "
                f"проекта: пропуск: {decision.skip}")
    if decision.profile.in_weakening_scope(path):
        return None
    scope = ", ".join(decision.profile.weakening_scope)
    return (f"путь вне области {scope} — гейт неослабления тестов другие "
            f"пути не рассматривает")


def _element_refusal(element: str, marker: str,
                     files: list[str] | None, decision=None) -> str | None:
    """Причина, по которой элемент мандата не годен; `None` — годен.

    Порядок — порядок подпунктов требования 2: сначала общее правило 2а
    (пробел, непохожесть на путь), затем правило своего маркера — 2б для
    мандата зон, 2в для мандата ослабления.

    `decision` — решение профиля задачи (`_task_decision`), область мандата
    ослабления; `None` — область артели.
    """
    if any(ch.isspace() for ch in element):
        return ("элемент содержит пробел — пояснение пишется отдельным "
                "абзацем, а не внутри элемента")

    if marker == TEST_WEAKENING_MANDATE_MARKER:
        path, sep, name = element.partition(guard.TEST_NAME_SEP)
        if not _looks_like_path(path):
            return "не похож на путь репозитория"
        scope_refusal = _weakening_scope_refusal(path, decision)
        if scope_refusal is not None:
            return scope_refusal
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
            repo: Path | None = None, *, conn=None,
            task_id: str | None = None) -> list[str]:
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

    `conn`/`task_id` — БД и задача ответа: строку «Зависимости мержа: …»
    (SPEC 01M44EP0D47F498TEE08MNGBYT, требование 3) проверяют правила
    гейта SPEC по БД (`merge_after.value_refusals`); без них — только
    форма элементов. Они же задают область мандата ослабления — профиль
    проекта задачи (`_task_decision`); без них — область артели.
    """
    # Ленивый импорт: `merge_after` сам импортирует этот модуль ради
    # маркера.
    from .. import merge_after
    files = _tree_files(code_branch, repo)
    # Решение профиля — только при строке мандата ослабления: ответу без
    # неё `targets.yaml` не нужен, и его сбой такому ответу не отказывает.
    decision = None
    if any(elements(line, TEST_WEAKENING_MANDATE_MARKER)
           for line in text.splitlines()):
        decision = _task_decision(conn, task_id)
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
            if marker == MERGE_AFTER_MANDATE_MARKER:
                found.extend(f"строка «{shown}»: {reason}" for reason in
                             merge_after.value_refusals(conn, task_id, parsed))
                break
            for element in parsed:
                reason = _element_refusal(element, marker, files, decision)
                if reason is not None:
                    found.append(f"строка «{shown}»: элемент «{element}» — "
                                 f"{reason}")
            break
    repeated = merge_after.lines_refusal(text)
    if repeated is not None:
        found.append(repeated)
    return found


# Матрица неослабления (SPEC 01M4NZ5QRB7MNEYCWGXEWVWFP0, ADR-0022 п.4):
# механика проверяет только ФОРМУ матрицы при мандате — раздел, пять
# канонических столбцов, строки данных, названность каждого элемента и
# «ок при условии» у строки «остаётся, не покрыто»; верность названных
# свойств остаётся за Оператором и независимой проверкой.
MATRIX_DOC_REF = "docs/operator-gates.md, раздел «Матрица неослабления»"

# Маркеры, строка которых — мандат, требующий матрицы. «Зависимости мержа:»
# сюда не входит: это не ослабление и не расширение (требование 1).
MATRIX_MANDATE_MARKERS = (_ZONES_MANDATE_MARKER, TEST_WEAKENING_MANDATE_MARKER)

_MATRIX_HEADING_RE = re.compile(r"##\s+Матрица неослабления(?!\w)")

# Канон заголовков — `docs/operator-gates.md`, раздел «Матрица
# неослабления»; заголовок столбца сравнивается по началу.
MATRIX_HEADERS = ("Что меняется", "Какое свойство сейчас держит",
                  "Остаётся ли свойство после изменения", "Чем покрыто после",
                  "Решение")

_SEPARATOR_CELL_RE = re.compile(r":?-+:?\Z")

# Границы токена в ячейке «Что меняется» (требование 2).
_TOKEN_SPLIT_RE = re.compile(r"[\s`,;()«»]+")

# Ссылка на тест в ячейке «Чем покрыто»: `tests/<…>.py`, за ней может стоять
# `:строка` или `::имя`.
_TEST_REF_RE = re.compile(r"(?<![\w/])tests/[\w./-]*\.py(?!\w)")

# Кандидат в ссылку на тест у задачи с профилем проекта: любой путь `*.py`
# (за ним может стоять `:строка` или `::имя`); ссылкой он становится, только
# если лежит в области ослабления профиля (SPEC 01M55VDVVDVWW2MTJ01F88N5FM,
# требование 4).
_PY_PATH_RE = re.compile(r"(?<![\w./-])[\w][\w./-]*\.py(?!\w)")

_EMPHASIS_RE = re.compile(r"(?<!\S)[*_`]+|[*_`]+(?!\S)")

_CONDITIONAL = "ок при условии"
_REPLACEMENTS_SEPARATORS = ":—-,;."


def _normalized(cell: str) -> str:
    """Нормализация ячейки (SPEC, термины): `strip`, снятие выделения по
    краям слов, нижний регистр, «ё» = «е»."""
    return _EMPHASIS_RE.sub("", cell.strip()).strip().lower().replace("ё", "е")


def matrix_section(text: str) -> str | None:
    """Раздел матрицы: от заголовка `## Матрица неослабления` до следующего
    заголовка уровня 1 или 2 либо до конца текста; `None` — раздела нет."""
    lines = text.splitlines()
    for start, line in enumerate(lines):
        if _MATRIX_HEADING_RE.match(line.strip()):
            break
    else:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith(("# ", "## ")):
            end = i
            break
    return "\n".join(lines[start:end]) + "\n"


def _row_cells(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _matrix_table(section: str) -> tuple[list[str], list[list[str]]] | None:
    """(заголовки, строки данных) первой markdown-таблицы раздела; `None` —
    таблицы со строкой-разделителем нет."""
    lines = section.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        if i + 1 >= len(lines) or not lines[i + 1].strip().startswith("|"):
            return None
        separator = [c for c in _row_cells(lines[i + 1]) if c]
        if not separator or not all(_SEPARATOR_CELL_RE.match(c)
                                    for c in separator):
            return None
        rows = []
        for row_line in lines[i + 2:]:
            if not row_line.strip().startswith("|"):
                break
            cells = _row_cells(row_line)
            if any(cells):
                rows.append(cells)
        return _row_cells(line), rows
    return None


def _headers_ok(headers: list[str]) -> bool:
    return len(headers) == len(MATRIX_HEADERS) and all(
        _normalized(cell).startswith(_normalized(canon))
        for cell, canon in zip(headers, MATRIX_HEADERS))


def _names(cell: str, element: str) -> bool:
    """`element` стоит в ячейке отдельным токеном (требование 2); `/` на
    конце не учитывается — у элемента зон-каталога и у токена."""
    want = element.rstrip("/")
    return any(token.rstrip("/") == want
               for token in _TOKEN_SPLIT_RE.split(cell) if token)


def _remains(cell: str) -> bool:
    return not _normalized(cell).startswith(("нет", "не остается", "исчезает"))


def _covered(cell: str, profile=None) -> bool:
    """Ячейка «Чем покрыто после» несёт ссылку на тест. `profile` — профиль
    тестов проекта задачи: ссылка — путь `*.py` в его области ослабления;
    `None` — прежнее правило `tests/…`."""
    value = _normalized(cell)
    if "не покрыто" in value or value.startswith(("нет", "—", "–", "-")):
        return False
    if profile is None:
        return _TEST_REF_RE.search(value) is not None
    # Путь сверяется с масками без нижнего регистра нормализации: маска
    # профиля сравнивается с путём буквально, как у гейта.
    raw = _EMPHASIS_RE.sub("", cell.strip())
    return any(profile.in_weakening_scope(m.group(0))
               for m in _PY_PATH_RE.finditer(raw))


def _conditional_with_replacements(cell: str) -> bool:
    value = _normalized(cell)
    if not value.startswith(_CONDITIONAL):
        return False
    rest = value[len(_CONDITIONAL):]
    return any(not ch.isspace() and ch not in _REPLACEMENTS_SEPARATORS
               for ch in rest)


def matrix_refusals(text: str, elements: list[str], *, conn=None,
                    task_id: str | None = None) -> list[str]:
    """Причины отказа по форме матрицы неослабления в тексте `text` при
    мандате на `elements` (SPEC 01M4NZ5QRB7MNEYCWGXEWVWFP0, требования 1-3,
    7); пустой список — форма годна. Одна функция на оба канала — `answer`
    и `zones-extend`: правило не может разойтись между ними.

    `conn`/`task_id` — задача ответа: у задачи с профилем проекта ссылка на
    тест в «Чем покрыто после» — путь в области ослабления профиля (SPEC
    01M55VDVVDVWW2MTJ01F88N5FM, требование 4); у артели, без задачи и без
    профиля (решение — отказ или пропуск) — прежнее правило `tests/…`
    (у артели — буквально прежнее, а не его пересказ масками профиля)."""
    from .. import repo_context
    decision = _task_decision(conn, task_id)
    profile = None
    if decision is not None and not repo_context.is_artel(decision.target):
        profile = decision.profile
    section = matrix_section(text)
    if section is None:
        return ["нет раздела «## Матрица неослабления»"]
    table = _matrix_table(section)
    if table is None:
        return ["в разделе «## Матрица неослабления» нет таблицы (строка "
                "заголовков и строка-разделитель)"]
    headers, rows = table
    if not _headers_ok(headers):
        return ["таблица матрицы обязана нести ровно пять столбцов: "
                + ", ".join(f"«{h}…»" for h in MATRIX_HEADERS)
                + f" (сейчас: {', '.join(headers)})"]
    if not rows:
        return ["в таблице матрицы нет ни одной строки данных"]
    found = []
    unnamed = [e for e in elements
               if not any(_names(row[0], e) for row in rows)]
    if unnamed:
        found.append("в столбце «Что меняется» не названы элементы мандата: "
                     + ", ".join(unnamed))
    for number, row in enumerate(rows, start=1):
        cells = row + [""] * (len(MATRIX_HEADERS) - len(row))
        if (_remains(cells[2]) and not _covered(cells[3], profile)
                and not _conditional_with_replacements(cells[4])):
            found.append(f"строка данных {number}: свойство остаётся и не "
                         f"покрыто, а «Решение» не начинается с «ок при "
                         f"условии» с перечнем замен")
    return found
