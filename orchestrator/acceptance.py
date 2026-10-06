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
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Iterator, NamedTuple

from scripts import guard

from . import agent_log, artifact_branch, ci, config, gitcmd, stack, suite_lock


def _pytest_command(*args: str, command: list[str] | None = None) -> list[str]:
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
    returncode вместо тихого пропуска таймаута отдельного теста.

    `command` — начало команды из профиля тестов проекта
    (`project_profile.Profile.command`, SPEC 01M45FJVGQT1K0P8HDEXZX6HS7,
    требование 1): первый элемент `python3` — тот же интерпретатор venv
    пульта, пути тестов и флаги пульта добавляются к нему; не назван —
    команда пульта. Интерпретатор резолвится здесь, при сборке команды
    прогона, а не в гейте: гейт, чей прогон не состоится, venv не ищет."""
    head = (list(command) if command
            else [stack.pytest_python_executable(), "-m", "pytest"])
    if head[0] == "python3":
        head[0] = stack.pytest_python_executable()
    return [*head, *args,
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
    return ([str(tests_dir)] if plank_present(tests_dir) else []) + list(extra)


def plank_present(tests_dir: Path) -> bool:
    """В каталоге планки есть что-то кроме помощника пульта `_pult.py`
    (`materialize_*` кладут его и к пустой планке) и кеша байткода: только
    помощник — та же «планка не заведена», что и отсутствие каталога.
    Вопрос «есть ли планка» после выкладки задаётся этой функцией, не
    `is_dir()` каталога."""
    if not tests_dir.is_dir():
        return False
    return any(p.name not in (PLANK_HELPER_NAME, "__pycache__")
               for p in tests_dir.iterdir())


def run(tdir: Path, cwd: Path | None = None,
        extra: list[str] = (),
        command: list[str] | None = None) -> tuple[bool, str]:
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

    `command` — начало команды из профиля тестов проекта
    (`_pytest_command`).
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
                _pytest_command(*targets, command=command),
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
            extra: list[str] = (),
            command: list[str] | None = None) -> tuple[bool, str]:
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
    (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 3). `command` — тот же
    контракт, что у `run()`.
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
                _pytest_command(*targets, "--collect-only", "-q",
                                command=command),
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

    В ветке нет `acceptance_tests/` — валидный исход: в каталоге планки
    лежит только помощник пульта `_pult.py` (SPEC
    01M44EP4Q927DJXVX9YMMZ0B7V, требование 3), и `run()`/`collect()`/
    `summary()` читают такой каталог через `plank_present` как «тесты не
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
    # Список и тексты читаются по sha, разрешённому один раз: коммит в
    # ссылку посреди выкладки не смешивает две ревизии, а помощник планки
    # (`_pult.py`) называет ровно ту ревизию, с которой выложены файлы.
    revision = _docs_revision(task_id, branch)
    source = revision or branch
    paths = artifact_branch.ls_tree(task_id, source,
                                    f"tasks/{task_id}/acceptance_tests")
    if paths is None:
        return tdir
    wanted: dict[str, str] = {}
    for rel in paths:
        if not rel.startswith(prefix):
            continue
        text, _ = artifact_branch.show(task_id, source, rel)
        if text is not None:
            wanted[rel[len(prefix):]] = text
    _write_plank(tests_dir, _with_plank_helper(task_id, wanted, code_dir,
                                               revision))
    return tdir


# Имя файла помощника пульта в каталоге планки (SPEC
# 01M44EP4Q927DJXVX9YMMZ0B7V, требования 3, 5): зарезервировано — свой файл
# планки с этим именем отклоняет выход из `tests_writing`
# (`advance_gates/tests_writing.py`), а при выкладке побеждает файл пульта.
PLANK_HELPER_NAME = "_pult.py"

# Блок значений выкладки в исходном тексте помощника: строка `ИМЯ = …`
# заменяется целиком подставленным литералом.
_PLANK_HELPER_SOURCE = Path(__file__).with_name("plank_helper.py")
_PLANK_HELPER_VALUE_NAMES = ("TASK_ID", "CODE_ROOT", "DOCS_REPO",
                             "DOCS_REVISION", "DIFF_BASE", "DIFF_BASE_SOURCE")


def _docs_revision(task_id: str, rev: str) -> str:
    """sha коммита `rev` (имя ссылки документов или уже sha) в репозитории
    задачи; пустая строка — git не ответил или ревизии нет."""
    res = artifact_branch.git(task_id, "rev-parse", "--verify", "--quiet",
                              f"{rev}^{{commit}}")
    if res is None or res.returncode != 0:
        return ""
    return res.stdout.strip()


def _plank_helper_text(task_id: str, code_dir: Path, revision: str) -> str:
    """Исходный текст `orchestrator/plank_helper.py` с подставленными
    значениями выкладки. База диффа и её источник — `gitcmd.diff_base`/
    `diff_base_source` той же пары, что у гейта зон (`_zones_gate`): ветка
    задачи из БД в клоне проекта `workspace.task_repo` — рабочая копия
    делит с ним ссылки, а её собственный git на пути выкладки не
    спрашивается. Строки задачи в БД нет (песочница без пульта) — ветка
    под HEAD рабочей копии. Помощник базу сам не считает."""
    from . import store, workspace  # workspace -> runner -> acceptance
    code_dir = Path(code_dir).resolve()
    branch = (store.task_branch(store.db(), task_id)
              if config.DB.exists() else "")
    repo = workspace.task_repo(task_id)
    if not branch:
        branch = gitcmd.current_branch(code_dir) or "HEAD"
        repo = code_dir
    values = {
        "TASK_ID": task_id,
        "CODE_ROOT": str(code_dir),
        "DOCS_REPO": str(artifact_branch.task_repo(task_id)),
        "DOCS_REVISION": revision,
        "DIFF_BASE": gitcmd.diff_base(branch, repo=repo),
        "DIFF_BASE_SOURCE": gitcmd.diff_base_source(branch, repo=repo),
    }
    text = _PLANK_HELPER_SOURCE.read_text(encoding="utf-8")
    for name in _PLANK_HELPER_VALUE_NAMES:
        text, count = re.subn(rf"^{name} = .*$",
                              lambda _m, n=name: f"{n} = {values[n]!r}",
                              text, count=1, flags=re.MULTILINE)
        if count != 1:
            raise RuntimeError(f"{_PLANK_HELPER_SOURCE}: нет строки "
                               f"значения выкладки {name}")
    return text


def _with_plank_helper(task_id: str, wanted: dict[str, str | bytes],
                       code_dir: Path, revision: str
                       ) -> dict[str, str | bytes]:
    """`wanted` плюс помощник пульта: поверх одноимённого файла планки (он
    побеждает) и вне прунинга `_write_plank`. Кладётся и к пустой планке —
    роль, гоняющая свои проверки рядом, получает помощник всегда; каталог,
    где кроме помощника ничего нет, `plank_present` по-прежнему читает как
    «тесты не заведены»."""
    return {**wanted,
            PLANK_HELPER_NAME: _plank_helper_text(task_id, code_dir, revision)}


def _write_plank(tests_dir: Path, wanted: dict[str, str | bytes]) -> None:
    """Каталог планки `tests_dir` ровно с файлами `wanted` (путь от
    каталога планки -> содержимое): лишний файл на диске убирается, не
    просто дополняется — общий узел выкладки из ссылки документов и из
    черновика (`materialize_files`)."""
    if tests_dir.is_dir():
        for path in sorted(tests_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(tests_dir).as_posix()
            if rel not in wanted:
                path.unlink()
    for rel, content in wanted.items():
        dest = tests_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            dest.write_bytes(content)
        else:
            dest.write_text(content, encoding="utf-8")


def materialize_files(task_id: str, files: dict[str, str | bytes],
                      code_dir: Path) -> Path:
    """`tasks/<id>/acceptance_tests/` каталога `code_dir` из явного набора
    файлов — черновика планки, ещё не зафиксированного в ссылке документов
    (`plank-run` в `tests_writing`, SPEC 01M41R4YAM4NGEQXW1FWH7T22M,
    требование 1). Возврат — тот же, что у `materialize_from_branch`.

    Ревизия ссылки документов помощника `_pult.py` — голова ссылки на
    момент выкладки: черновик в ссылку ещё не записан, артефакты задачи
    планка читает оттуда."""
    tdir = code_dir / "tasks" / task_id
    revision = _docs_revision(task_id, artifact_branch.branch_name(task_id))
    _write_plank(tdir / "acceptance_tests",
                 _with_plank_helper(task_id, files, code_dir, revision))
    return tdir


def drop_from_code_copy(task_id: str, code_dir: Path) -> None:
    """Убирает `tasks/<id>/` из рабочей копии кода `code_dir` (ADR-0021,
    этап 1): документы задачи там не лежат, планка — только на время
    прогона (`plank_in_code_copy`). Главная копия пульта (`config.ROOT`)
    не трогается: там `tasks/<id>/` — легаси-каталог задач старше T094, не
    выкладка прогона."""
    if Path(code_dir).resolve() == config.ROOT.resolve():
        return
    shutil.rmtree(Path(code_dir) / "tasks" / task_id, ignore_errors=True)


@contextlib.contextmanager
def plank_in_code_copy(task_id: str, branch: str, code_dir: Path,
                       files: dict[str, str | bytes] | None = None
                       ) -> Iterator[Path]:
    """`materialize_from_branch` на время блока `with` и уборка выкладки в
    `finally` — на зелёном, красном исходе и на исключении внутри прогона
    (ADR-0021 п.13, этап 1): прогону планка нужна в рабочей копии кода
    (её `__file__` находит код ветки задачи), после него — нет.

    `files` — выложить этот набор (`materialize_files`) вместо головы
    `branch`: черновик планки `plank-run` в `tests_writing` (SPEC
    01M41R4YAM4NGEQXW1FWH7T22M, требование 1) — уборка та же."""
    try:
        if files is None:
            yield materialize_from_branch(task_id, branch, code_dir)
        else:
            yield materialize_files(task_id, files, code_dir)
    finally:
        drop_from_code_copy(task_id, code_dir)


def run_plank(targets: list[str], cwd: Path) -> tuple[int | None, str]:
    """(код выхода pytest, весь вывод) — прогон `targets` тем же раннером
    (`_pytest_command`, `_pytest_env`) и тем же таймаутом
    (`config.ACCEPTANCE_TIMEOUT_SEC`), что `run()` пульта, но для человека
    или роли, а не гейта: вывод не обрезается, код выхода не сворачивается
    в «зелёно/красно» (`plank-run`, SPEC 01M41R4YAM4NGEQXW1FWH7T22M,
    требование 1). `None` — прогон превысил таймаут."""
    try:
        with _pytest_env() as env:
            res = subprocess.run(
                _pytest_command(*targets),
                cwd=cwd, env=env, capture_output=True, text=True,
                timeout=config.ACCEPTANCE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        return None, (_timeout_text(exc.stdout) + _timeout_text(exc.stderr)
                      + f"\nпрогон превысил {config.ACCEPTANCE_TIMEOUT_SEC}с "
                        f"— завис или ждёт сетевой ответ")
    return res.returncode, res.stdout + res.stderr


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
# Прогон не запускался: замок полных прогонов машины занят дольше
# `config.FULL_SUITE_LOCK_WAIT_SEC` (SPEC 01M46D5T8SZ9D6S34TZFX8S46V,
# требование 2) — ни красный прогон, ни таймаут прогона. Константа —
# одновременно начало текста исхода (`_not_started_note`), по которому его
# различает `_full_suite_outcome`.
FULL_SUITE_NOT_STARTED = "прогон не начат"

# Запись журнала задачи об ожидании замка прогоном гейта (требование 2).
FULL_SUITE_LOCK_WAIT_ACTION = "полный прогон ждёт замок"

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


def _not_started_note(holder: dict) -> str:
    """Текст исхода «прогон не начат» — функция по тому же доводу, что
    `_full_suite_timeout_note`: предел ожидания подменяют тесты."""
    return (f"{FULL_SUITE_NOT_STARTED}: машина занята прогоном "
            f"{suite_lock.describe(holder)} — замок полных прогонов не "
            f"освободился за {config.FULL_SUITE_LOCK_WAIT_SEC} с ожидания, "
            f"pytest не запускался")


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
    if output.startswith(f"{FULL_SUITE_NOT_STARTED}: "):
        return FULL_SUITE_NOT_STARTED
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
                       log_path: Path | None, note: str = "") -> str:
    """Строка журнала об исходе прогона: различимая причина, выжимка
    разбора и путь к файлу лога (требования 4-6). `note` — текст исхода
    «прогон не начат» с держателем замка."""
    if outcome == FULL_SUITE_NO_TESTS:
        # Прогона не было — ни выжимки, ни лога не существует.
        return FULL_SUITE_NO_TESTS_NOTE
    if outcome == FULL_SUITE_NOT_STARTED:
        return note or FULL_SUITE_NOT_STARTED
    head = {
        FULL_SUITE_GREEN: "полный набор tests/ зелёный",
        FULL_SUITE_RED: "полный набор tests/ красный",
        FULL_SUITE_TIMEOUT: _full_suite_timeout_note(),
    }[outcome]
    log_note = f" (лог прогона: {log_path})" if log_path is not None else ""
    return f"{head}: {digest}{log_note}"


def run_full_suite(root: Path, command: list[str] | None = None,
                   targets: tuple = ("tests",), extra: tuple = (),
                   log: Path | None = None) -> tuple[bool, str]:
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

    Параметры команды `suite-run` (SPEC 01M462QACEH29RPRD2RZHGHQFM,
    требования 1, 6, 10); гейты их не передают, и их прогон не меняется:
    `command` — начало команды из профиля тестов проекта (как у `run()`);
    `targets` — пути или id тестов вместо `tests` (повтор упавших);
    `extra` — флаги pytest после флагов параллели; `log` — вывод идёт
    прямо в этот файл по ходу прогона (ход прогона читается из него, пока
    прогон идёт), а на пределе времени убивается вся группа процессов
    pytest с рабочими xdist — фоновому прогону некому добить сирот.

    Прогон идёт под замком полных прогонов машины (`suite_lock`, SPEC
    01M46D5T8SZ9D6S34TZFX8S46V, требования 1-4), `_machine_lock`: прогон
    без задачи (`notes`) пишет ожидание в вывод; процесс, уже держащий
    замок (`full_suite` гейта, фоновый процесс `suite-run`), идёт без
    второго взятия.
    """
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return False, FULL_SUITE_NO_TESTS_NOTE
    argv = _pytest_command(*targets, command=command) + [
        "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist", *extra]
    with _machine_lock(None) as holder:
        if holder is not None:
            return False, _not_started_note(holder)
        return _run_full_suite_now(argv, root, log)


@contextlib.contextmanager
def _machine_lock(task_id: str | None) -> Iterator[dict | None]:
    """Замок полных прогонов машины на время прогона: даёт `None` — замок
    за текущим процессом, иначе держатель, не отпустивший замок за
    `config.FULL_SUITE_LOCK_WAIT_SEC` (прогон тогда не запускается).

    Ожидание — до входа в прогон, поэтому в предел прогона
    `config.FULL_SUITE_TIMEOUT_SEC` не входит (требование 2); взятый здесь
    замок снимается на любом исходе тела — зелёном, красном, таймауте,
    исключении (требование 4). Уже держащий замок процесс его не берёт и
    не снимает: снимет тот, кто брал."""
    if suite_lock.held_by_me():
        yield None
        return
    holder = suite_lock.wait_acquire(
        task_id, suite_lock.KIND_GATE if task_id else suite_lock.KIND_NOTES,
        config.FULL_SUITE_LOCK_WAIT_SEC,
        lambda busy: _journal_lock_wait(task_id, busy))
    if holder is not None:
        yield holder
        return
    try:
        yield None
    finally:
        suite_lock.release()


def _journal_lock_wait(task_id: str | None, holder: dict) -> None:
    """Запись об ожидании замка: журнал задачи и вывод; без задачи —
    только вывод. Сбой записи журнала прогон не роняет: ожидание и сам
    прогон от неё не зависят."""
    text = (f"машина занята прогоном {suite_lock.describe(holder)} — "
            f"полный прогон tests/ ждёт замок не дольше "
            f"{config.FULL_SUITE_LOCK_WAIT_SEC} с; ожидание в предел прогона "
            f"{config.FULL_SUITE_TIMEOUT_SEC} с не входит")
    if task_id:
        from . import store  # store -> ... -> acceptance
        try:
            store.journal(store.db(), task_id, "orchestrator",
                          FULL_SUITE_LOCK_WAIT_ACTION, text)
        except Exception as exc:  # noqa: BLE001 — запись не условие прогона
            text += f" (запись журнала не удалась: {type(exc).__name__})"
    print(f"[{task_id}] {text}" if task_id else text, flush=True)


def _run_full_suite_now(argv: list[str], root: Path,
                        log: Path | None) -> tuple[bool, str]:
    """Сам прогон `run_full_suite` — замок уже взят; предел
    `config.FULL_SUITE_TIMEOUT_SEC` отсчитывается отсюда."""
    if log is not None:
        return _run_full_suite_to_log(argv, root, log)
    try:
        with _pytest_env() as env:
            res = subprocess.run(
                argv, cwd=root, env=env, capture_output=True, text=True,
                timeout=config.FULL_SUITE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        output = _timeout_text(exc.stdout) + _timeout_text(exc.stderr)
        return False, f"{_full_suite_timeout_note()}\n{output}"
    return res.returncode == 0, res.stdout + res.stderr


def _kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_full_suite_to_log(argv: list[str], root: Path,
                           log: Path) -> tuple[bool, str]:
    """Прогон `run_full_suite` с выводом прямо в файл `log`. Вывод
    читается из файла байтами с заменой не-UTF-8: чужой проект вправе
    печатать что угодно, а разбор не имеет права уронить фоновый прогон.
    `PYTHONUNBUFFERED` — иначе на пределе времени SIGKILL съел бы
    неслитый буфер, и числа успевшей части пропали бы (требование 6)."""
    timed_out = False
    with _pytest_env() as env, open(log, "wb") as fh:
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(argv, cwd=root, env=env, stdout=fh,
                                stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL,
                                start_new_session=True)
        try:
            code = proc.wait(timeout=config.FULL_SUITE_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(proc.pid)
            proc.wait()
        except BaseException:
            _kill_group(proc.pid)
            proc.wait()
            raise
    output = log.read_bytes().decode("utf-8", errors="replace")
    if timed_out:
        return False, f"{_full_suite_timeout_note()}\n{output}"
    return code == 0, output


# ----------------------------------------- сохранённые итоги полного набора
#
# Перечень упавших тестов завершённого прогона полного набора по sha дерева,
# на котором он шёл (SPEC 01M462QACEH29RPRD2RZHGHQFM, требования 7-8):
# итог базы для `suite-run` любой задачи с этой базой — второй раз база не
# прогоняется. Пишут его гейты (`full_suite`) и прогон базы `suite-run`.

_FAILED_ENTRY = re.compile(r"^(?:FAILED|ERROR) (.+?)(?: - (.*))?$",
                           re.MULTILINE)
_SHORT_SUMMARY_HEADER = re.compile(r"^=+ short test summary info =+$",
                                   re.MULTILINE)
# Разделитель секции вывода pytest («==== FAILURES ====», итоговая строка
# «==== 1 failed in 0.1s ====») — конец блока сводки.
_SECTION_RULE = re.compile(r"^=+ .* =+$", re.MULTILINE)


def short_summary_block(output: str) -> str:
    """Текст блока «short test summary info» — от его заголовка до
    следующего разделителя секции; блока нет — пустая строка. Заголовок —
    последний в выводе: захваченный вывод упавшего теста печатается раньше
    сводки и вправе содержать что угодно, в том числе строки `FAILED …`/
    `ERROR …` (захваченный лог `ERROR    m:файл:строка …`)."""
    headers = list(_SHORT_SUMMARY_HEADER.finditer(output))
    if not headers:
        return ""
    start = headers[-1].end()
    end = _SECTION_RULE.search(output, start)
    return output[start:end.start() if end else len(output)]


def failed_entries(output: str) -> list[tuple[str, str]]:
    """(id теста, первая строка сообщения) из блока «short test summary
    info» — по одной паре на упавший тест, без повторов; сообщения нет —
    пустая строка. Строки вне блока не читаются (`short_summary_block`)."""
    seen = {}
    for node, message in _FAILED_ENTRY.findall(short_summary_block(output)):
        seen.setdefault(node.strip(), (message or "").strip())
    return list(seen.items())


def suite_results_dir() -> Path:
    """Каталог сохранённых итогов — в каталоге логов пульта; функция, а не
    константа: `config.LOGS` подменяют тесты."""
    return config.LOGS / "fullsuite-results"


def saved_failures(sha: str) -> list[str] | None:
    """Перечень упавших сохранённого итога по `sha`; `None` — итога нет
    или файл не читается (прогон базы тогда идёт заново)."""
    path = suite_results_dir() / f"{sha}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        failed = data["failed"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return [str(n) for n in failed] if isinstance(failed, list) else None


def save_failures(sha: str, failed: list[str], source: str) -> None:
    """Итог завершённого прогона по `sha`. Запись через временный файл и
    `replace` — читатель не увидит половину файла; сбой записи не
    поднимается: итог — ускорение `suite-run`, не условие гейта."""
    folder = suite_results_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f".{sha}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps({"sha": sha, "failed": sorted(failed),
                                   "source": source}, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(folder / f"{sha}.json")
    except OSError:
        pass


def clean_tree_sha(root: Path) -> str | None:
    """sha HEAD каталога `root`, если его дерево совпадает с коммитом
    (без изменённых и неотслеживаемых файлов вне `tasks/` — туда пульт
    выкладывает планку); иначе `None`: итог грязного дерева не итог sha."""
    head = gitcmd.in_repo(root, "rev-parse", "HEAD")
    if head is None or head.returncode != 0 or not head.stdout.strip():
        return None
    status = gitcmd.in_repo(root, "status", "--porcelain",
                            "--untracked-files=all", "--", ".",
                            ":(exclude)tasks")
    if status is None or status.returncode != 0 or status.stdout.strip():
        return None
    return head.stdout.strip()


def _remember_gate_failures(root: Path, outcome: str, output: str) -> None:
    """Сохранение итога прогона гейта (требование 7): только завершённый
    прогон с итоговой строкой pytest (требование 8) и только чистое
    дерево. Сбой git здесь — молча без сохранения: исход гейта от этого
    не зависит (требование 1)."""
    if outcome not in (FULL_SUITE_GREEN, FULL_SUITE_RED):
        return
    if not run_summary_line(output):
        return
    try:
        sha = clean_tree_sha(root)
    except (OSError, ValueError, AttributeError):
        return
    if sha:
        save_failures(sha, [node for node, _ in failed_entries(output)],
                      "гейт")


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
    # Замок берётся здесь, а не в `run_full_suite`: ожидание пишется в
    # журнал задачи гейта (требование 2), а `run_full_suite` внутри взятого
    # замка идёт без второго взятия.
    with _machine_lock(task_id) as holder:
        if holder is not None:
            green, output = False, _not_started_note(holder)
        else:
            green, output = run_full_suite(root)
    outcome = _full_suite_outcome(green, output)
    if outcome == FULL_SUITE_NOT_STARTED:
        # Прогона не было: ни лога, ни выжимки, ни итога по sha.
        return FullSuiteRun(green, outcome, "", None,
                            _full_suite_detail(outcome, "", None, output))
    _remember_gate_failures(root, outcome, output)
    log_path = (_write_full_suite_log(task_id, output)
                if outcome != FULL_SUITE_NO_TESTS and output.strip() else None)
    digest = run_digest(output)
    return FullSuiteRun(green, outcome, digest, log_path,
                        _full_suite_detail(outcome, digest, log_path))


def summary(tdir: Path, branch: str | None = None,
            long_lived: list[Path] | None = None,
            repo: Path | None = None) -> str:
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
    if not plank_present(tests_dir) and long_lived is None:
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
                  else ci.verifying_status(branch, repo=repo)[1])
        for n in ci_ns:
            reason = markers[n][1]
            lines.append(f"  AC-{n}" + (f": {reason}" if reason else "")
                        + f" — {ci_note}")
    return "\n".join(lines)
