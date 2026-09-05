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

from . import ci, config, gitcmd


def run(tdir: Path, code_root: Path | None = None) -> tuple[bool, str]:
    """(зелёно, хвост вывода) — детерминированный прогон unittest'ом с
    `code_root`, равным рабочему каталогу кода задачи (SPEC
    01M1RNZ6V7TTTTYAHBMF8JBQQS, требование 2, AC-2/AC-3; контракт имени
    параметра — hotfix 88b38022, ADR-0013): планка, резолвящая
    `orchestrator/` и через `__file__` (материализация
    `materialize_from_branch` кладёт её по штатному пути
    `tasks/<id>/acceptance_tests/` ИМЕННО этого каталога), и через
    неявную вставку `cwd` в `sys.path`, которую делает `python3 -m
    unittest discover`, обязаны видеть один и тот же код. `code_root=None`
    (вызовы вне зоны этой задачи, например `orchestrator/amend.py`) —
    прежнее поведение, `config.ROOT`.

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
    run_cwd = code_root if code_root is not None else config.ROOT
    location_note = f"планка: {tests_dir}, cwd: {run_cwd}"
    try:
        res = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", str(tests_dir)],
            cwd=run_cwd, capture_output=True, text=True,
            timeout=config.ACCEPTANCE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        tail = ((exc.stdout or "") + (exc.stderr or ""))[-2000:]
        return False, (f"{location_note}\nпрогон превысил "
                       f"{config.ACCEPTANCE_TIMEOUT_SEC}с — завис или ждёт "
                       f"сетевой ответ\n{tail}")
    tail = (res.stdout + res.stderr)[-2000:]
    return res.returncode == 0, f"{location_note}\n{tail}"


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
    `root` (SPEC T066, требование 2в): условие автогейта acceptance,
    тем же приёмом discover, что штатный CI-джоб `python`
    (`.github/workflows/ci.yml`) и `run()` выше для acceptance_tests/.

    `tests/` нет вовсе — не «зелено»: в отличие от `run()` (отсутствие
    acceptance_tests/ — легитимный «нечего гонять»), отсутствие ПОЛНОГО
    набора в worktree ветки задачи ничего не проверяет и не имеет права
    сойти за пройденное условие автогейта.
    """
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return False, "tests/ нет в worktree — полный набор не проверен"
    try:
        res = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", "tests"],
            cwd=root, capture_output=True, text=True,
            timeout=config.FULL_SUITE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        tail = ((exc.stdout or "") + (exc.stderr or ""))[-2000:]
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
