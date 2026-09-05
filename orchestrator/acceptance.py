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
import tempfile
from pathlib import Path

from scripts import guard

from . import config, gitcmd


def run(tdir: Path, code_root: Path | None = None) -> tuple[bool, str]:
    """(зелёно, хвост вывода) — детерминированный прогон unittest'ом.

    `code_root` — рабочий каталог прогона, откуда планка импортирует
    пакет оркестратора: для self-target это worktree КОДОВОЙ ВЕТКИ
    задачи, не `config.ROOT` (главная копия стоит на пине запущенной
    версии — старом коде; планка, материализованная из артефактной
    ветки во временный каталог, через `sys.path.insert(parents[3])`
    попадает в случайный путь и импортирует пакет из cwd; hotfix
    аварийного режима 05.09, регрессия №14 флоу A7: тесты hotfix зон
    01M1RR1PZC красные из ROOT и зелёные из worktree). `None` — прежнее
    поведение (`config.ROOT`): внешний target, песочницы без worktree.

    Каталога нет (`skip_tests` либо задача старше T023) — прогонять
    нечего, переход не блокируется: тот же вырожденный случай, что
    и у fixation.read() без фиксации.
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return True, "acceptance_tests/ нет — приёмочные тесты не заведены"
    try:
        res = subprocess.run(
            ["python3", "-m", "unittest", "discover", "-s", str(tests_dir)],
            cwd=code_root or config.ROOT, capture_output=True, text=True,
            timeout=config.ACCEPTANCE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        tail = ((exc.stdout or "") + (exc.stderr or ""))[-2000:]
        return False, (f"прогон превысил {config.ACCEPTANCE_TIMEOUT_SEC}с "
                       f"— завис или ждёт сетевой ответ\n{tail}")
    tail = (res.stdout + res.stderr)[-2000:]
    return res.returncode == 0, tail


def materialize_from_branch(task_id: str, branch: str) -> Path:
    """Временный каталог с `tasks/<id>/acceptance_tests/`, вычитанным из
    ВЕТКИ (SPEC T094, требование 10, реестр PLAN.md пункт 2 — «лок
    acceptance_tests»): внешний target не несёт живого worktree с этим
    каталогом на диске — `acceptance_tests/` живёт только в артефактной
    ветке пульта (`orchestrator/fsm_advance.py::review`/`verifying`
    зовут эту функцию перед `run()`/`summary()`/`guard.
    scan_acceptance_tests`, тем же приёмом, что self читает с
    worktree). Вызывающий код обязан убрать каталог сам (`shutil.
    rmtree`) — эта функция только материализует, не чистит за собой.

    Ветки нет, или в ней нет `acceptance_tests/` — валидный исход
    (пустой каталог): `run()`/`summary()` уже умеют трактовать
    отсутствие `acceptance_tests/` как «тесты не заведены», не отказ.
    """
    tmp_root = Path(tempfile.mkdtemp(prefix=f"artel-acceptance-{task_id}-"))
    prefix = f"tasks/{task_id}/acceptance_tests/"
    paths = gitcmd.ls_tree_files(branch, f"tasks/{task_id}/acceptance_tests") or []
    for rel in paths:
        if not rel.startswith(prefix):
            continue
        text, _ = gitcmd.show(branch, rel)
        if text is None:
            continue
        dest = tmp_root / "acceptance_tests" / rel[len(prefix):]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    return tmp_root


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


def summary(tdir: Path) -> str:
    """Сводка в карточку гейта acceptance: пройдено/manual/skip.

    Число тестов — статический счёт (`guard.count_test_methods`), не
    запуск: второй документ-сводка не заводится (требование 3), а
    `unittest.TestLoader().discover()` для этого не годится — импортирует
    модуль по голому имени файла в `sys.modules` процесса, и второй
    прогон на другом каталоге с файлом того же имени падает ImportError
    (обычное дело: разные задачи, один и тот же `test_ac.py`).
    """
    tests_dir = tdir / "acceptance_tests"
    if not tests_dir.is_dir():
        return "acceptance_tests/ нет — приёмочные тесты не заведены"
    _, markers = guard.scan_acceptance_tests(tdir)
    manual = sorted(n for n, (kind, _) in markers.items() if kind == "manual")
    skip = sorted(n for n, (kind, _) in markers.items() if kind == "skip")
    count = guard.count_test_methods(tdir)
    lines = [f"приёмочные тесты: {count} тест(ов), "
             f"{len(manual)} manual, {len(skip)} skip"]
    if manual:
        lines.append("manual-критерии (проверяет Оператор на приёмке):")
        for n in manual:
            reason = markers[n][1]
            lines.append(f"  AC-{n}" + (f": {reason}" if reason else ""))
    return "\n".join(lines)
