"""Прогон и сводка приёмочных тестов задачи: tasks/<id>/acceptance_tests/
(SPEC T023, требование 6).

Разбор AC-разметки и пометок manual/skip/escalate живёт в scripts/guard.py
(`scan_acceptance_tests`) — тот же код держит трассируемость на выходе
из tests_writing (orchestrator/fsm.py) и сводку здесь: расхождение
источников иначе обнаруживалось бы разными числами в разных местах,
а не проверкой. guard.py содержимое файлов принципиально не исполняет
(его докстринг) — прогон и сбор тестов поэтому здесь, не там.
"""
import subprocess
from pathlib import Path

from scripts import guard

from . import ci, config, gitcmd, stack


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


def run(tdir: Path, cwd: Path | None = None) -> tuple[bool, str]:
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
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return True, "acceptance_tests/ нет — приёмочные тесты не заведены"
    run_cwd = cwd if cwd is not None else config.ROOT
    location_note = f"планка: {tests_dir}, cwd: {run_cwd}"
    try:
        res = subprocess.run(
            _pytest_command(str(tests_dir)),
            cwd=run_cwd, capture_output=True, text=True,
            timeout=config.ACCEPTANCE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        tail = (_timeout_text(exc.stdout) + _timeout_text(exc.stderr))[-2000:]
        return False, (f"{location_note}\nпрогон превысил "
                       f"{config.ACCEPTANCE_TIMEOUT_SEC}с — завис или ждёт "
                       f"сетевой ответ\n{tail}")
    tail = (res.stdout + res.stderr)[-2000:]
    return res.returncode == 0, f"{location_note}\n{tail}"


def collect(tdir: Path, cwd: Path | None = None) -> tuple[bool, str]:
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
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return True, "acceptance_tests/ нет — приёмочные тесты не заведены"
    run_cwd = cwd if cwd is not None else config.ROOT
    location_note = f"планка: {tests_dir}, cwd: {run_cwd}"
    try:
        res = subprocess.run(
            _pytest_command(str(tests_dir), "--collect-only", "-q"),
            cwd=run_cwd, capture_output=True, text=True,
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


def run_full_suite(root: Path) -> tuple[bool, str]:
    """(зелено, хвост вывода) — прогон ПОЛНОГО пакета `tests/` каталога
    `root` через pytest (SPEC T066, требование 2в; переход раннера —
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
    (AC-3). Срез хвоста `[-2000:]` ниже не меняется (AC-5): построчный
    вывод воркеров xdist многословнее последовательного, но финальная
    строка "N passed" остаётся в КОНЦЕ вывода, который и берёт срез.
    """
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return False, "tests/ нет в worktree — полный набор не проверен"
    try:
        res = subprocess.run(
            _pytest_command("tests") + ["-n", str(config.FULL_SUITE_WORKERS),
                                        "-p", "xdist"],
            cwd=root, capture_output=True, text=True,
            timeout=config.FULL_SUITE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        tail = (_timeout_text(exc.stdout) + _timeout_text(exc.stderr))[-2000:]
        return False, (f"прогон полного набора tests/ превысил "
                       f"{config.FULL_SUITE_TIMEOUT_SEC}с — завис или ждёт "
                       f"сетевой ответ\n{tail}")
    tail = (res.stdout + res.stderr)[-2000:]
    return res.returncode == 0, tail


def summary(tdir: Path, branch: str | None = None) -> str:
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
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return "acceptance_tests/ нет — приёмочные тесты не заведены"
    _, markers = guard.scan_acceptance_tests(tdir)
    manual = sorted(n for n, (kind, _) in markers.items() if kind == "manual")
    skip = sorted(n for n, (kind, _) in markers.items() if kind == "skip")
    ci_ns = sorted(n for n, (kind, _) in markers.items() if kind == "ci")
    count = guard.count_test_methods(tdir)
    lines = [f"приёмочные тесты: {count} тест(ов), "
             f"{len(manual)} manual, {len(skip)} skip, {len(ci_ns)} ci"]
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
