"""Фикстуры вывода pytest и поиск узла разбора — общее для нескольких
файлов планки задачи 01M3FQ3JVC3DGGM33XCX8TC7ME (не `test_*.py`:
подхватывается только импортом из `test_ac*.py`).

Имя узла разбора вывода pytest ни один критерий приёмки не называет
(SPEC требование 1 говорит «ОДИН узел в `orchestrator/acceptance.py`»,
без имени), поэтому планка ищет его ПОВЕДЕНИЕМ: функция модуля
`orchestrator.acceptance`, которая на тексте прогона со строками `FAILED
<nodeid>` и итоговой строкой pytest отдаёт и то, и другое. Разработчик
свободен в имени и в форме возврата (строка, кортеж, именованный
кортеж) — `digest_text` ниже сводит любую из них к тексту выжимки.

Двух ложных кандидатов поиск отсекает намеренно, иначе тесты AC-1/AC-2
зеленели бы на функциях, разбора не делающих вовсе:
- проброс текста как есть (`acceptance._timeout_text`) — по равенству
  выжимки входу;
- отрезание хвоста (любой помощник вида `tail[-N:]`) — по `BODY_MARKER`:
  маркер стоит в теле traceback ВНУТРИ последних `config.LOG_TAIL_LINES`
  строк фикстуры, поэтому голый хвост его несёт, а выжимка «имена
  упавших + итоговая строка» — нет;
- функция, чей текст прогона попадает в возврат подстановкой
  (`acceptance._pytest_command(*args)`) — по форме сигнатуры
  (`_takes_one_or_two_positionals`).
"""
import inspect
import re

from orchestrator import acceptance

# Итоговая строка pytest фикстуры красного прогона — той же формы, что
# ловит существующая `amend._RUN_SUMMARY` («N failed, M passed … in Xs»).
SUMMARY_LINE = "2 failed, 305 passed, 1 warning in 71.23s"

# Имена упавших тестов фикстуры: строки `FAILED <nodeid>` блока
# «short test summary info» настоящего вывода pytest.
FAILED_NODEIDS = (
    "tests/test_fsm_autogate.py::FullSuiteDetailTest::test_detail_names_failed",
    "tests/test_acceptance.py::RunFullSuiteTest::test_log_file_is_created",
)

# Маркер в НАЧАЛЕ вывода прогона: в выжимку (хвост/итог) он попасть не
# может — по нему отличается настоящая выжимка от проброса всего текста
# и проверяется, что в файл лога ушёл ПОЛНЫЙ вывод, а не его хвост.
HEAD_MARKER = "MARKER-NACHALA-VYVODA-PROGONA"

# Маркер в КОНЦЕ вывода без итоговой строки и без `FAILED`: выжимка
# такого вывода — его хвост, значит маркер обязан в ней быть.
TAIL_MARKER = "MARKER-KONCA-VYVODA-BEZ-ITOGA"

# Маркер в теле traceback, стоящий БЛИЗКО к концу вывода — внутри
# последних `config.LOG_TAIL_LINES` строк, но ВНЕ блока «short test
# summary info» и итоговой строки. Голый хвост вывода его несёт, выжимка
# «имена упавших + итоговая строка» — нет: по нему узел разбора
# отличается от любой функции, просто отрезающей хвост (`_bounded`/
# `_timeout_text` и подобные помощники того же модуля).
BODY_MARKER = "MARKER-TELA-VYVODA-NE-VYZHIMKA"


def _progress_lines(count: int) -> list[str]:
    """Строки прогресса воркеров xdist — тело вывода между заголовком
    сессии и блоком «short test summary info»."""
    return [f"[gw{i % 8}] [ {i}%] PASSED tests/test_module_{i}.py::Case::test_{i}"
            for i in range(1, count + 1)]


def red_output(failed_nodeids=FAILED_NODEIDS,
               summary_line: str = SUMMARY_LINE) -> str:
    """Вывод красного прогона полного набора: заголовок сессии с
    `HEAD_MARKER`, длинное тело прогресса, traceback, блок «short test
    summary info» со строками `FAILED <nodeid>` и итоговая строка."""
    lines = [
        "============================= test session starts ==============================",
        f"platform darwin -- Python 3.13.2, pytest-8.3.4 -- {HEAD_MARKER}",
        "rootdir: /wt, configfile: pyproject.toml",
        "plugins: xdist-3.6.1, timeout-2.3.1",
        "8 workers [306 items]",
    ]
    lines += _progress_lines(60)
    lines += [
        "=================================== FAILURES ===================================",
        "___________________ FullSuiteDetailTest.test_detail_names_failed ________________",
        "    self.assertIn(nodeid, detail)",
        f"AssertionError: {BODY_MARKER} not found in 'автогейт: ...'",
        "=========================== short test summary info ============================",
    ]
    lines += [f"FAILED {nodeid} - AssertionError: имя упавшего теста"
              for nodeid in failed_nodeids]
    lines.append(f"================= {summary_line} =================")
    return "\n".join(lines) + "\n"


def output_without_summary_and_failed() -> str:
    """Вывод, в котором нет ни итоговой строки pytest, ни строк `FAILED
    <nodeid>`: сбор набора оборвался до первого теста. Единственная
    выжимка, которая тут возможна, — хвост вывода (`TAIL_MARKER`)."""
    return (
        "ImportError while loading conftest '/wt/tests/conftest.py'.\n"
        "Traceback (most recent call last):\n"
        "  File \"/wt/tests/conftest.py\", line 4, in <module>\n"
        "    import orchestrator.net_takogo_modulya\n"
        f"ModuleNotFoundError: No module named '{TAIL_MARKER}'\n"
    )


def huge_red_output(failed_count: int = 200) -> str:
    """Красный прогон, в котором строк `FAILED <nodeid>` заведомо больше
    `config.LOG_TAIL_LINES`, а сам вывод длиннее `config.LOG_TAIL_CHARS`
    — фикстура для ограничения объёма выжимки."""
    nodeids = [
        f"tests/test_module_{i:03d}.py::VeryLongNamedTestCase{i:03d}"
        f"::test_some_rather_long_scenario_name_{i:03d}"
        for i in range(failed_count)
    ]
    return red_output(failed_nodeids=nodeids)


# ---------------------------------------------------------------- узел разбора


def digest_text(result) -> str:
    """Текст выжимки из того, что вернул узел разбора, какой бы формы
    возврат ни выбрал разработчик: строка — как есть; кортеж/список —
    его непустые элементы (вложенный список имён — поэлементно) по
    строке на элемент; что-то иное — `str()`."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, (tuple, list)):
        parts: list[str] = []
        for item in result:
            if isinstance(item, (tuple, list)):
                parts.extend(str(x) for x in item if x)
            elif item:
                parts.append(str(item))
        return "\n".join(parts)
    return str(result)


_POSITIONAL_KINDS = (inspect.Parameter.POSITIONAL_ONLY,
                     inspect.Parameter.POSITIONAL_OR_KEYWORD)


def _takes_one_or_two_positionals(fn) -> bool:
    """Функция принимает текст прогона позиционно: ровно один или два
    обязательных позиционных параметра, и `*args` среди них нет.

    Отсечение по форме сигнатуры, а не по результату: `acceptance.
    _pytest_command(*args)` подставляет полученный текст в список команды
    и потому «несёт» и итоговую строку, и имена упавших — под проверку
    по одному результату он подошёл бы ложно."""
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return False
    if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params):
        return False
    required = [p for p in params
                if p.kind in _POSITIONAL_KINDS
                and p.default is inspect.Parameter.empty]
    return 1 <= len(required) <= 2


def _module_functions() -> list:
    """Функции, ОБЪЯВЛЕННЫЕ в `orchestrator/acceptance.py` (не
    импортированные туда) и принимающие текст прогона позиционно, в
    стабильном порядке имён."""
    return [fn for _name, fn in sorted(vars(acceptance).items())
            if inspect.isfunction(fn)
            and getattr(fn, "__module__", "") == acceptance.__name__
            and _takes_one_or_two_positionals(fn)]


def call_with_output(fn, text: str):
    """Результат `fn(text)` либо `fn(text, None)` (узел с вторым
    позиционным параметром); `None` — вызов не состоялся: функция ждёт
    не текст прогона (например `run_full_suite(root: Path)` падает на
    `root / "tests"`), и кандидатом она не является."""
    for args in ((text,), (text, None)):
        try:
            return fn(*args)
        except Exception:  # noqa: BLE001 — не тот кандидат, а не дефект
            continue
    return None


def is_parse_node_digest(text: str, digest: str) -> bool:
    """Выжимка `digest` — результат РАЗБОРА вывода `text`, а не его
    проброс и не отрезанный хвост: несёт итоговую строку и оба имени
    упавших тестов, не равна входу целиком и не тащит тело вывода
    (`BODY_MARKER` лежит внутри последних `config.LOG_TAIL_LINES` строк —
    голый хвост его несёт, разбор нет)."""
    if not digest or digest == text or BODY_MARKER in digest:
        return False
    return all(piece in digest for piece in (SUMMARY_LINE, *FAILED_NODEIDS))


def find_parse_node():
    """(функция, выжимка) узла разбора вывода pytest, найденного
    поведением на `red_output()` (`is_parse_node_digest`);
    `(None, "")` — такого узла в модуле нет."""
    text = red_output()
    for fn in _module_functions():
        digest = digest_text(call_with_output(fn, text))
        if is_parse_node_digest(text, digest):
            return fn, digest
    return None, ""


NO_PARSE_NODE_HINT = (
    "в orchestrator/acceptance.py нет функции, которая по тексту прогона "
    "отдаёт итоговую строку pytest и имена упавших тестов (SPEC требование "
    "1, AC-1): ни одна функция модуля не вернула выжимку с "
    f"{SUMMARY_LINE!r} и именами {FAILED_NODEIDS}")


def log_file_number(name: str):
    """Номер прогона из имени файла лога (`…-1.log` -> 1); `None` —
    в имени нет числа перед расширением. Точное имя файла критерий
    приёмки не фиксирует (SPEC требование 3 допускает «иное имя по
    образцу `agent_log.new_agent_log`»), фиксирует только нумерацию."""
    match = re.search(r"(\d+)\.log$", name)
    return int(match.group(1)) if match else None
