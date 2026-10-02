"""Прогон и сводка приёмочных тестов задачи: tasks/<id>/acceptance_tests/
(SPEC T023, требование 6).

Разбор AC-разметки и пометок manual/skip/escalate живёт в scripts/guard.py
(`scan_acceptance_tests`) — тот же код держит трассируемость на выходе
из tests_writing (orchestrator/fsm.py) и сводку здесь: расхождение
источников иначе обнаруживалось бы разными числами в разных местах,
а не проверкой. guard.py содержимое файлов принципиально не исполняет
(его докстринг) — прогон и сбор тестов поэтому здесь, не там.
"""
import contextlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Iterator, NamedTuple

from scripts import guard

from . import agent_log, ci, config, gitcmd, stack


def _pytest_command(*args: str) -> list[str]:
    """Общая часть команды pytest обоих раннеров: интерпретатор venv
    пульта (`stack.pytest_python_executable()` — не голый `"python3"`,
    резолвящийся по PATH ВЫЗЫВАЮЩЕГО процесса, а не роли: гейты/
    `amend-tests` пульт зовёт из собственного окружения, не из
    `runner.role_env`, тот PATH только у роли — ANSWER-4, диагноз AC-7),
    без кеша (требование 5), и ЯВНАЯ загрузка `pytest-timeout` по
    каноническому имени точки входа `timeout` (не `pytest_timeout` — имя
    импортируемого модуля: `-p pytest_timeout` заставляет pytest
    импортировать его как отдельный плагин ДО разбора точек входа
    setuptools, и последующая автозагрузка того же модуля под именем
    `timeout` падает `ValueError: Plugin already registered under a
    different name` — эмпирически найдено этим же прогоном). Явная
    загрузка по имени `timeout` — тот же плагин, что и так подключился бы
    автоматически (никакого эффекта, если он уже установлен), но при ЕГО
    ОТСУТСТВИИ в интерпретаторе даёт громкий `ImportError`/красный
    returncode вместо тихого пропуска таймаута отдельного теста."""
    return [stack.pytest_python_executable(), "-m", "pytest", *args,
            "-p", "no:cacheprovider", "-p", "timeout",
            "-o", f"timeout={stack.PER_TEST_TIMEOUT_SEC}"]


@contextlib.contextmanager
def _pytest_env() -> Iterator[dict[str, str]]:
    """Окружение одного прогона `_pytest_command`: копия `os.environ`
    пульта плюс `PYTHONPYCACHEPREFIX` на свежий временный каталог (SPEC
    01M3Y7G6T3MK7A899521VF9N7B, требования 1, 3, 4).

    Проверка свежести `.pyc` смотрит только на время изменения и размер
    исходника: 02.10 правка с тем же размером в ту же секунду оставила
    `__pycache__` worktree «свежим», и автогейт исполнил старый байткод.
    `PYTHONDONTWRITEBYTECODE` не помогает — уже лежащий `.pyc` всё равно
    читается; отведённый кеш пуст, и исходник компилируется заново.
    Каталог — в системном временном (`tempfile`), то есть вне `cwd`
    прогона и вне `config.ROOT`; рабочие процессы xdist наследуют
    переменную от главного процесса pytest. Уборка — на выходе из блока,
    в том числе по `TimeoutExpired` и любому другому исключению."""
    cache_dir = tempfile.mkdtemp(prefix="artel-pycache-")
    try:
        env = dict(os.environ)
        env["PYTHONPYCACHEPREFIX"] = cache_dir
        yield env
    finally:
        _remove_cache_dir(cache_dir)


# Попытки уборки каталога кеша: на таймауте `subprocess.run` убивает
# главный процесс pytest, а рабочие процессы xdist ещё дописывают `.pyc` —
# `rmtree` ловит «Directory not empty» на каталоге, куда только что лёг файл.
_CACHE_RMTREE_ATTEMPTS = 5
_CACHE_RMTREE_PAUSE_SEC = 0.2


def _remove_cache_dir(path: str) -> None:
    """Удаление каталога кеша прогона с повторами; последняя неудача не
    поднимается — сбой уборки временного каталога не имеет права подменить
    исход прогона, который он обслуживал."""
    for _ in range(_CACHE_RMTREE_ATTEMPTS):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(_CACHE_RMTREE_PAUSE_SEC)
    shutil.rmtree(path, ignore_errors=True)


def _timeout_text(value: bytes | str | None) -> str:
    """`subprocess.TimeoutExpired.stdout`/`.stderr` отдаёт `bytes` ДАЖЕ
    при `text=True`, если процесс успел вывести хоть что-то до самого
    таймаута (наблюдаемое поведение `subprocess.run`, не документированный
    контракт `text=`) — с unittest discover это молчало (тест виснет
    раньше первого вывода), pytest печатает заголовок сессии сразу и
    обнажает несовпадение типов."""
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


# ------------------------------------------------ разбор вывода прогона
#
# Один узел разбора на весь пульт (SPEC 01M3FQ3JVC3DGGM33XCX8TC7ME,
# требование 1): до него признак красноты и итоговую строку читали в двух
# местах по-разному — `amend._RUN_SUMMARY` знал только итоговую строку, а
# автогейт приёмки не читал вывод вовсе и писал одну фразу на три разных
# исхода. Имена упавших тестов не читал никто.

# Итоговая строка pytest (перенесена из `orchestrator/amend.py`, SPEC
# 01M1TKP6AAY4W8GDGZNA9R0JZT, требование 2): «N passed in Xs» / «M failed,
# N passed in Xs», в любом порядке категорий (failed/passed/skipped/error/
# xfailed/xpassed/warning) через запятую, завершается «in <секунды>s» — тем
# же местом, где pytest печатает сводку независимо от порядка
# category-групп в конкретном прогоне.
_RUN_SUMMARY = re.compile(
    r"\d+ (?:passed|failed|error(?:s)?|skipped|xfailed|xpassed|warnings?)"
    r"(?:, \d+ (?:passed|failed|error(?:s)?|skipped|xfailed|xpassed|warnings?))*"
    r" in [\d.]+s")

# Строка блока «short test summary info»: имя упавшего теста. `ERROR` —
# та же категория (требование 1): тест не запустился вовсе (сбой setUp/
# импорта), но назван он там же и тем же форматом, а Оператору нужен
# именно nodeid. Якорь на начало строки обязателен — иначе слово FAILED
# внутри traceback или в сообщении ассерта читалось бы как имя теста.
_FAILED_LINE = re.compile(r"^(?:FAILED|ERROR) \S+.*$", re.MULTILINE)


def run_summary_line(output: str) -> str:
    """Итоговая строка прогона pytest (`N passed in Xs`/`M failed, N
    passed in Xs`) из вывода прогона; пустая строка — строки в выводе
    нет (прогон оборвался раньше сводки, вывод обрезан иначе, чем
    ожидается)."""
    match = _RUN_SUMMARY.search(output)
    return match.group(0).strip() if match else ""


def failed_test_lines(output: str) -> list[str]:
    """Строки `FAILED <nodeid>`/`ERROR <nodeid>` блока «short test summary
    info» — имена упавших тестов вместе с коротким сообщением, которым
    pytest их сопровождает (оно и есть первая версия причины)."""
    return [line.strip() for line in _FAILED_LINE.findall(output)]


def _bounded(text: str) -> str:
    """Текст, ограниченный теми же потолками, что выжимка логов ролей
    (`agent_log.log_tail`, SPEC требование 2): сначала последние
    `config.LOG_TAIL_LINES` строк, затем последние
    `config.LOG_TAIL_CHARS` символов — хвост, а не начало: в конце вывода
    pytest стоит и сводка, и последние упавшие тесты."""
    tail = "\n".join(text.splitlines()[-config.LOG_TAIL_LINES:]).strip()
    return tail[-config.LOG_TAIL_CHARS:]


def run_digest(output: str) -> str:
    """Выжимка вывода прогона pytest для журнала (требование 1): имена
    упавших тестов и итоговая строка; ни того, ни другого в выводе нет
    (сбор оборвался на conftest, вывод не от pytest) — хвост вывода, чтобы
    диагностика не потерялась совсем.

    Объём — `_bounded` (требование 2): запись журнала читают глазами, а
    красный полный набор бывает и на двести тестов."""
    lines = failed_test_lines(output)
    summary = run_summary_line(output)
    if summary:
        lines.append(summary)
    return _bounded("\n".join(lines) if lines else output)


def _run_targets(tests_dir: Path, extra: list[str]) -> list[str]:
    """Пути одного вызова pytest: каталог планки (если есть) и долгоживущие
    файлы `tests/` кодовой ветки задачи (`extra`, пути от `cwd` прогона,
    SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 3, 9) — обе группы в одном
    прогоне, второго не заводится."""
    return ([str(tests_dir)] if tests_dir.is_dir() else []) + list(extra)


def run(tdir: Path, cwd: Path | None = None,
        extra: list[str] = ()) -> tuple[bool, str]:
    """(зелёно, хвост вывода) — детерминированный прогон pytest'ом (SPEC
    01M1TKP6AAY4W8GDGZNA9R0JZT, требование 1) с `cwd`, равным
    рабочему каталогу кода задачи (SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS,
    требование 2, AC-2/AC-3; контракт имени параметра — hotfix 88b38022,
    ADR-0013; переименован `code_root` -> `cwd` задачей SPEC
    01M1R5B33CC7E6BZK085XV3ZCX, AC-11 — клон контекста target'а, не
    обязательно рабочая копия КОДА в узком смысле прежнего имени):
    `cwd` прогона — единственный способ, которым pytest находит и
    `orchestrator/`-код ветки задачи (материализация
    `materialize_from_branch` кладёт планку по штатному пути
    `tasks/<id>/acceptance_tests/` ИМЕННО этого каталога), и
    `pyproject.toml` корня репозитория (таймаут отдельного теста,
    требования 4/6) — pytest ищет конфигурацию, поднимаясь от `cwd`, тем
    же приёмом, каким раньше unittest discover неявно вставлял `cwd` в
    `sys.path`. `cwd=None` (вызовы вне зоны этой задачи, например
    `orchestrator/amend.py`) — прежнее поведение, `config.ROOT`.

    `-p no:cacheprovider` (требование 5) — `.pytest_cache/` не создаётся
    вовсе, автокоммиту артефактов задачи (`checkpoint.py`) нечего
    случайно подобрать.

    `-o timeout=…` (требование 4, AC-7) передаёт таймаут отдельного теста
    ЯВНО, не полагаясь на то, что pytest сам найдёт `pyproject.toml` по
    `cwd`: планка задачи (`tests_dir`, `materialize_from_branch`) лежит
    ВНЕ дерева `run_cwd`, и pytest определяет rootdir/inifile по общему
    предку АРГУМЕНТОВ пути, а не по `cwd`, когда путь теста передан
    отдельным аргументом (эмпирически подтверждено ANSWER-3.md — `cwd`
    оказался кандидатом для поиска конфигурации НЕ во всех версиях
    поведения, вопреки прежнему предположению; без явного `-o` таймаут
    отдельного теста тихо не применялся, зависший тест не резался раньше
    общего таймаута всего прогона).

    Каталога нет (`skip_tests` либо задача старше T023) — прогонять
    нечего, переход не блокируется: тот же вырожденный случай, что
    и у fixation.read() без фиксации.

    Отказ (красная планка) называет каталог планки и `cwd` прогона одной
    строкой в начале хвоста вывода (SPEC требование 4, AC-6) — иначе
    разбор класса дефекта регрессии №14 снова требовал бы ручной раскопки
    кода вместо чтения журнала.

    `extra` — долгоживущие файлы `tests/` задачи (`_run_targets`): они
    исполняются тем же вызовом pytest, и при пустой планке тоже.
    """
    tests_dir = tdir / "acceptance_tests"
    targets = _run_targets(tests_dir, extra)
    if not targets:
        return True, "acceptance_tests/ нет — приёмочные тесты не заведены"
    run_cwd = cwd if cwd is not None else config.ROOT
    location_note = f"планка: {tests_dir}, cwd: {run_cwd}"
    if extra:
        location_note += f", долгоживущие файлы: {', '.join(extra)}"
    try:
        with _pytest_env() as env:
            res = subprocess.run(
                _pytest_command(*targets),
                cwd=run_cwd, env=env, capture_output=True, text=True,
                timeout=config.ACCEPTANCE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        tail = (_timeout_text(exc.stdout) + _timeout_text(exc.stderr))[-2000:]
        return False, (f"{location_note}\nпрогон превысил "
                       f"{config.ACCEPTANCE_TIMEOUT_SEC}с — завис или ждёт "
                       f"сетевой ответ\n{tail}")
    tail = (res.stdout + res.stderr)[-2000:]
    return res.returncode == 0, f"{location_note}\n{tail}"


def collect(tdir: Path, cwd: Path | None = None,
            extra: list[str] = ()) -> tuple[bool, str]:
    """(собралось, хвост вывода) — сухой сбор планки `pytest
    --collect-only -q` (SPEC 01M2ARQRDV4YY9TVPHXN2E7136, требование 1,
    AC-1/AC-2/AC-3): та же команда, тот же интерпретатор и те же флаги
    окружения, что несёт общая часть `_pytest_command` (venv пульта,
    `-p no:cacheprovider`, явная загрузка `-p timeout`), но без прогона
    ТЕЛ тестов — только импорт модулей и сборка списка тестов. `tdir`/
    `cwd` — тот же контракт, что у `run()` выше.

    Различение исходов — по коду возврата pytest (эмпирически проверено
    этой же задачей, не документированный публичный API, но устойчивое
    поведение текущей мажорной версии): `0` — планка собралась, есть хотя
    бы один тест; `5` (`EXIT_NOTESTSCOLLECTED`) — планка синтаксически
    валидна и импортируется, но не содержит ни одного теста (AC-3, текст
    ровно «планка не содержит ни одного теста» — критерий требует точный
    текст); любой другой код (`2` — сбор прерван ошибкой импорта/
    синтаксиса, и т.п.) — красный сбор, хвост сырого вывода pytest
    называет причину (AC-2). Оба «пустых» исхода (синтаксическая ошибка
    и легитимно пустая планка) печатают в stdout фразу «no tests
    collected» — отличить их текстом самого вывода нельзя, только кодом
    возврата: код 5 отдаётся ТОЛЬКО когда pytest успел собрать дерево без
    единой ошибки и в нём действительно ноль тестов.

    Каталога `acceptance_tests/` нет вовсе — тот же вырожденный случай,
    что и у `run()`: собирать нечего, `(True, ...)`, переход не
    блокируется этой функцией.

    `extra` — тот же контракт, что у `run()`: долгоживущие файлы `tests/`
    собираются тем же вызовом из `cwd` — рабочей копии кодовой ветки
    (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 3).
    """
    tests_dir = tdir / "acceptance_tests"
    targets = _run_targets(tests_dir, extra)
    if not targets:
        return True, "acceptance_tests/ нет — приёмочные тесты не заведены"
    run_cwd = cwd if cwd is not None else config.ROOT
    location_note = f"планка: {tests_dir}, cwd: {run_cwd}"
    if extra:
        location_note += f", долгоживущие файлы: {', '.join(extra)}"
    try:
        with _pytest_env() as env:
            res = subprocess.run(
                _pytest_command(*targets, "--collect-only", "-q"),
                cwd=run_cwd, env=env, capture_output=True, text=True,
                timeout=config.ACCEPTANCE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        tail = (_timeout_text(exc.stdout) + _timeout_text(exc.stderr))[-2000:]
        return False, (f"{location_note}\nсбор превысил "
                       f"{config.ACCEPTANCE_TIMEOUT_SEC}с — завис или ждёт "
                       f"сетевой ответ\n{tail}")
    if res.returncode == 0:
        return True, (res.stdout + res.stderr)[-2000:]
    if res.returncode == 5:
        return False, "планка не содержит ни одного теста"
    tail = (res.stdout + res.stderr)[-2000:]
    return False, f"{location_note}\n{tail}"


def materialize_from_branch(task_id: str, branch: str, code_dir: Path) -> Path:
    """`tasks/<id>/acceptance_tests/` каталога `code_dir` (рабочего
    каталога КОДА задачи — worktree self-target либо workspace внешнего
    target, тот же узел выбора, что `orchestrator/runner.py::role_cwd`),
    материализованный НА МЕСТЕ из ГОЛОВЫ ветки `branch` (SPEC
    01M1RNZ6V7TTTTYAHBMF8JBQQS, требование 1, AC-1) — тот же приём, что
    `artifact_branch.materialize_task_dir` уже применяет к `tasks/<id>/`
    целиком: файл на диске, отсутствующий в ветке (устаревшая копия
    предыдущего прогона — например, от ручного протокола Оператора на
    время бага), убирается, не просто дополняется; поверх временного
    каталога (`tempfile.mkdtemp`, регрессия №14) — планка, резолвящая
    `orchestrator/` от `__file__`, промахивалась мимо кода ветки задачи
    что через `__file__` (вложенность временного каталога не совпадала
    со штатным `tasks/<id>/acceptance_tests/`), что через `cwd`.

    Источник истины остаётся АРТЕФАКТНАЯ ветка задачи (`branch`, решение
    регрессии №12, SPEC «Не входит») — читается всегда через git
    (`gitcmd.ls_tree_files`/`gitcmd.show`), не с диска `code_dir`; меняется
    только каталог, в который планка записывается перед прогоном.

    Ветки нет, или в ней нет `acceptance_tests/` — валидный исход
    (каталог не создаётся/остаётся нетронутым): `run()`/`summary()` уже
    умеют трактовать отсутствие `acceptance_tests/` как «тесты не
    заведены», не отказ.

    Git не ответил на `ls_tree_files` (`None`, отдельно от легитимно
    пустой ветки — `[]`, REVIEW.md итерация 1, R1-F1) — тихая деградация,
    тем же приёмом, что `artifact_branch.materialize_task_dir`: диск не
    трогается вовсе, уже материализованная планка остаётся как есть.
    Иначе транзиентный сбой git на повторной материализации (второй
    проход review, повторная подтяжка main) стирал бы прунингом ниже
    уже реально лежащие на диске файлы планки, и `run()` красил бы
    задачу диагнозом «acceptance_tests красные» вместо честного «git не
    ответил, планка не проверена».

    Возврат — `code_dir / "tasks" / task_id` (совместим с `run()`,
    ожидающим `tdir / "acceptance_tests"`).
    """
    tdir = code_dir / "tasks" / task_id
    tests_dir = tdir / "acceptance_tests"
    prefix = f"tasks/{task_id}/acceptance_tests/"
    paths = gitcmd.ls_tree_files(branch, f"tasks/{task_id}/acceptance_tests")
    if paths is None:
        return tdir
    wanted: dict[str, str] = {}
    for rel in paths:
        if not rel.startswith(prefix):
            continue
        text, _ = gitcmd.show(branch, rel)
        if text is not None:
            wanted[rel[len(prefix):]] = text
    if tests_dir.is_dir():
        for path in sorted(tests_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(tests_dir).as_posix()
            if rel not in wanted:
                path.unlink()
    for rel, text in wanted.items():
        dest = tests_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    return tdir


# ----------------------------------------------- полный набор tests/
#
# Исходы прогона полного набора (SPEC 01M3FQ3JVC3DGGM33XCX8TC7ME,
# требование 4): до этой задачи все три не-зелёных схлопывались в одну
# фразу «полный набор tests/ красный», и причину восстанавливали по
# времени событий (26.09).
FULL_SUITE_GREEN = "зелёный прогон"
FULL_SUITE_RED = "красный прогон"
FULL_SUITE_TIMEOUT = "таймаут прогона"
FULL_SUITE_NO_TESTS = "tests/ нет в worktree"

# Текст вырожденного исхода «в рабочей копии нет каталога tests/» — одна
# константа и для `run_full_suite` (производитель), и для
# `_full_suite_outcome` (потребитель): исход различается по тексту,
# который пульт сам же и написал, и расхождение двух копий этого текста
# молча ломало бы классификацию.
FULL_SUITE_NO_TESTS_NOTE = "tests/ нет в worktree — полный набор не проверен"

# «Роль» в имени файла лога полного набора: `agent_log.new_agent_log`
# складывает имя как `<task>-<role>-<N>.log`, то есть `.artel/logs/
# <id>-fullsuite-<n>.log` (требование 3 прямо разрешает имя по этому
# образцу). Своей нумерации задача не заводит — она там уже есть, и
# второй её источник разошёлся бы с первым.
FULL_SUITE_LOG_KIND = "fullsuite"


def _full_suite_timeout_note() -> str:
    """Текст исхода «прогон не уложился в потолок» — функция, не
    константа: `config.FULL_SUITE_TIMEOUT_SEC` подменяют тесты, и значение
    обязано читаться в момент вызова (тот же довод, что и у
    `FULL_SUITE_NO_TESTS_NOTE` — один текст на производителя и
    потребителя)."""
    return (f"прогон полного набора tests/ превысил "
            f"{config.FULL_SUITE_TIMEOUT_SEC}с — завис или ждёт сетевой "
            f"ответ")


class FullSuiteRun(NamedTuple):
    """Исход прогона полного набора с разбором и файлом лога (SPEC
    01M3FQ3JVC3DGGM33XCX8TC7ME, требования 3-6) — общий для трёх
    потребителей: автогейта приёмки, гейта мержа и `approve` в
    `acceptance`.

    `outcome` — одна из четырёх констант `FULL_SUITE_*`; `digest` —
    выжимка `run_digest`; `log_path` — файл с ПОЛНЫМ выводом прогона
    (`None`: прогона не было вовсе либо запись лога не удалась);
    `detail` — готовая строка для журнала: различимая причина, выжимка и
    путь к логу.
    """

    green: bool
    outcome: str
    digest: str
    log_path: Path | None
    detail: str


def _full_suite_outcome(green: bool, output: str) -> str:
    """Исход прогона по его тексту — по префиксу СВОЕГО ЖЕ сообщения о
    вырожденном исходе (см. `FULL_SUITE_NO_TESTS_NOTE`), не по разбору
    вывода pytest: сам pytest про «каталога нет» и «не уложился в
    потолок» ничего не печатает — это решения `run_full_suite`."""
    if green:
        return FULL_SUITE_GREEN
    if output.startswith(FULL_SUITE_NO_TESTS_NOTE):
        return FULL_SUITE_NO_TESTS
    if output.startswith(_full_suite_timeout_note()):
        return FULL_SUITE_TIMEOUT
    return FULL_SUITE_RED


def _write_full_suite_log(task_id: str, output: str) -> Path | None:
    """Полный вывод прогона — в файл рядом с логами ролей (требование 3);
    `None` — файл не записался.

    Сбой записи лога не имеет права уронить гейт, который этот прогон
    обслуживает (тот же приём деградации, что у `agent_log.stream_to_log`
    для лога шага): запись журнала останется без пути к файлу, но с
    выжимкой разбора."""
    try:
        path = agent_log.new_agent_log(task_id, FULL_SUITE_LOG_KIND)
        path.write_text(output, encoding="utf-8")
        return path
    except OSError:
        return None


def _full_suite_detail(outcome: str, digest: str,
                       log_path: Path | None) -> str:
    """Строка журнала об исходе прогона: различимая причина, выжимка
    разбора и путь к файлу лога (требования 4-6)."""
    if outcome == FULL_SUITE_NO_TESTS:
        # Прогона не было — ни выжимки, ни лога не существует.
        return FULL_SUITE_NO_TESTS_NOTE
    head = {
        FULL_SUITE_GREEN: "полный набор tests/ зелёный",
        FULL_SUITE_RED: "полный набор tests/ красный",
        FULL_SUITE_TIMEOUT: _full_suite_timeout_note(),
    }[outcome]
    log_note = f" (лог прогона: {log_path})" if log_path is not None else ""
    return f"{head}: {digest}{log_note}"


def run_full_suite(root: Path) -> tuple[bool, str]:
    """(зелено, ПОЛНЫЙ вывод прогона) — прогон ПОЛНОГО пакета `tests/`
    каталога `root` через pytest (SPEC T066, требование 2в; переход раннера —
    SPEC 01M1TKP6AAY4W8GDGZNA9R0JZT, требование 1): условие автогейта
    acceptance; штатный CI-джоб `python` (`.github/workflows/ci.yml`)
    остаётся на unittest — переход CI вне зоны этой задачи (SPEC, «Не
    входит»).

    `tests/` нет вовсе — не «зелено»: в отличие от `run()` (отсутствие
    acceptance_tests/ — легитимный «нечего гонять»), отсутствие ПОЛНОГО
    набора в worktree ветки задачи ничего не проверяет и не имеет права
    сойти за пройденное условие автогейта.

    `-p no:cacheprovider` — тот же довод, что у `run()` выше (требование 5).
    `-o timeout=…` — тот же довод, что у `run()` выше (требование 4, AC-7):
    таймаут отдельного теста передаётся явно, не через обнаружение
    `pyproject.toml` pytest'ом самостоятельно.

    `-n config.FULL_SUITE_WORKERS -p xdist` (01M291M2Z76M84GVP25J387A66,
    требование 1/AC-1): параллель только здесь, не в `_pytest_command`
    выше — `run()` (планка задачи) остаётся последовательной (требование
    1, «Не входит»). Явная загрузка `-p xdist`, тем же приёмом, что и
    `-p timeout` в `_pytest_command`: пакета `pytest-xdist` нет в
    интерпретаторе — pytest откажет ненулевым returncode и сообщением о
    неизвестном плагине в stderr, `res.returncode == 0` ниже это ловит
    как обычный красный прогон, без тихого повторного прогона без `-n`
    (AC-3).

    Вывод отдаётся ЦЕЛИКОМ, без прежнего среза `[-2000:]` (SPEC
    01M3FQ3JVC3DGGM33XCX8TC7ME, требование 3): полный вывод нужен файлу
    лога (`full_suite` выше), а в журнал уходит уже не он, а выжимка
    `run_digest`, ограниченная `config.LOG_TAIL_*` — записи журнала от
    этого только короче, чем были со срезом.
    """
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return False, FULL_SUITE_NO_TESTS_NOTE
    try:
        with _pytest_env() as env:
            res = subprocess.run(
                _pytest_command("tests") + [
                    "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"],
                cwd=root, env=env, capture_output=True, text=True,
                timeout=config.FULL_SUITE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        output = _timeout_text(exc.stdout) + _timeout_text(exc.stderr)
        return False, f"{_full_suite_timeout_note()}\n{output}"
    return res.returncode == 0, res.stdout + res.stderr


def full_suite(root: Path, task_id: str) -> FullSuiteRun:
    """Прогон полного набора `tests/` каталога `root` с разбором вывода и
    файлом лога (SPEC 01M3FQ3JVC3DGGM33XCX8TC7ME, требования 3-6) — узел
    для автогейта приёмки, гейта мержа и `approve` в `acceptance`.

    Сам прогон идёт через `run_full_suite` выше, а не в обход неё: это
    единственный вход прогона полного набора во всём пульте (и
    единственная точка его подмены в тестах), а различимость исходов
    держит `_full_suite_outcome` по тексту той же функции.

    Пустой вывод (прогона не было вовсе либо он ничего не напечатал) файла
    лога не заводит: пустой файл в каталоге логов только мешает читать
    настоящие.
    """
    green, output = run_full_suite(root)
    outcome = _full_suite_outcome(green, output)
    log_path = (_write_full_suite_log(task_id, output)
                if outcome != FULL_SUITE_NO_TESTS and output.strip() else None)
    digest = run_digest(output)
    return FullSuiteRun(green, outcome, digest, log_path,
                        _full_suite_detail(outcome, digest, log_path))


def summary(tdir: Path, branch: str | None = None,
            long_lived: list[Path] | None = None) -> str:
    """Сводка в карточку гейта acceptance: пройдено/manual/skip/ci.

    Число тестов — статический счёт (`guard.count_test_methods`), не
    запуск: второй документ-сводка не заводится (требование 3), а
    `unittest.TestLoader().discover()` для этого не годится — импортирует
    модуль по голому имени файла в `sys.modules` процесса, и второй
    прогон на другом каталоге с файлом того же имени падает ImportError
    (обычное дело: разные задачи, один и тот же `test_ac.py`).

    `branch` (01M1SHJTT0V516BWHYXWS50F3G, требование 4/AC-6) — имя
    КОДОВОЙ ветки задачи, тот же параметр, что уже несёт
    `materialize_from_branch(task_id, branch, code_dir)`: критерии с
    пометкой `ci` показываются вместе с результатом
    `ci.verifying_status(branch)`, так же явно, как manual-критерии
    сегодня. `None` (вызывающий не назвал ветку) — критерии `ci`
    называются без опроса CI: сводка не имеет права молчать про их
    существование только потому, что вызывающий не передал `branch`.

    `long_lived` — файлы долгоживущей группы задачи в `tests/`, исполненные
    тем же прогоном (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 9): итог
    называет число тестов обеих групп. `None` — у задачи нет перечня, строки
    групп нет, прежний вид сводки.
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir() and long_lived is None:
        return "acceptance_tests/ нет — приёмочные тесты не заведены"
    _, markers = guard.scan_acceptance_tests(tdir)
    manual = sorted(n for n, (kind, _) in markers.items() if kind == "manual")
    skip = sorted(n for n, (kind, _) in markers.items() if kind == "skip")
    ci_ns = sorted(n for n, (kind, _) in markers.items() if kind == "ci")
    count = guard.count_test_methods(tdir)
    lines = [f"приёмочные тесты: {count} тест(ов), "
             f"{len(manual)} manual, {len(skip)} skip, {len(ci_ns)} ci"]
    if long_lived is not None:
        long_count = 0
        for path in long_lived:
            try:
                long_count += len(guard.TEST_METHOD.findall(
                    path.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                continue
        lines.append(f"одним прогоном: разовая группа — {count} тест(ов), "
                     f"долгоживущая группа — {long_count} тест(ов) в "
                     f"{len(long_lived)} файл(ах) tests/")
    if manual:
        lines.append("manual-критерии (проверяет Оператор на приёмке):")
        for n in manual:
            reason = markers[n][1]
            lines.append(f"  AC-{n}" + (f": {reason}" if reason else ""))
    if ci_ns:
        lines.append("ci-критерии (доказательство — CI кодовой ветки):")
        ci_note = ("статус CI не проверен — ветка не названа" if branch is None
                  else ci.verifying_status(branch)[1])
        for n in ci_ns:
            reason = markers[n][1]
            lines.append(f"  AC-{n}" + (f": {reason}" if reason else "")
                        + f" — {ci_note}")
    return "\n".join(lines)
