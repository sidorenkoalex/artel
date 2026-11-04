"""AC-14, AC-15, AC-17, AC-19(б): снятие механизма диспетчером, прямой pytest роли, строка doctor, корень без переменной.

Группа: разовый
Предмет критериев — исход вызова git и дочерних процессов пульта под
окружением роли, а правило долгоживущих файлов `tests/` запрещает вызов git
через `subprocess` (`scripts/guard.py::long_lived_sign_hits`); поэтому файл —
в планке. Меняющие команды (`git clean -fX`, проверка doctor) идут только
против дублёра ROOT (`_doubler.Doubler`).

Строка doctor требования 7 ищется как `orchestrator.doctor.check_role_git_boundary()`
(возвращает `doctor.Check`): SPEC имени строки не задаёт, имя выбрано по
образцу соседних строк `doctor.check_*`.

Красен до реализации: обёртки `orchestrator/role_bin/`, переменных `ARTEL_GIT_GUARD_ROOT`/`GIT_CEILING_DIRECTORIES` в `runner.role_env` и строки `doctor.check_role_git_boundary` ещё нет — дочерний процесс команды пульта не видит потолка, `git clean` и `git -C <корень обёртки>` исполняются, пакет обёртки не копируется, у doctor нет атрибута.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _doubler import (OWN, PULT_PHRASE, TASK_RM, WRAPPER_DIR, WRAPPER_ROOT,  # noqa: E402
                      Doubler, output, refusal_problems, without_wrapper)

from orchestrator import artel, knowledge_cards, mutation_run, plank_run, runner  # noqa: E402
from orchestrator import suite_run  # noqa: E402

GUARD_ROOT = "ARTEL_GIT_GUARD_ROOT"
CEILING = "GIT_CEILING_DIRECTORIES"
LONG_LIVED_WITH_CLEAN = "tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py"


@pytest.fixture
def pult(tmp_path, monkeypatch):
    return Doubler(tmp_path, monkeypatch)


def _enter_role_env(monkeypatch, env: dict) -> None:
    """Процесс теста — под окружением роли (так диспетчер запускается шагом роли)."""
    for name in list(os.environ):
        if name not in env:
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def _main(monkeypatch, *argv) -> int:
    monkeypatch.setattr(sys, "argv", ["artel.py", *argv])
    try:
        artel.main()
    except SystemExit as exc:
        if exc.code is None or exc.code == 0:
            return 0
        return exc.code if isinstance(exc.code, int) else 1
    return 0


def _child_env() -> dict:
    """Окружение дочернего процесса, запущенного так, как его запускает команда пульта."""
    res = subprocess.run([sys.executable, "-c",
                          "import json, os; print(json.dumps(dict(os.environ)))"],
                         capture_output=True, text=True, check=True, timeout=60)
    return json.loads(res.stdout)


_COMMANDS = {
    "knowledge": (knowledge_cards, "cmd_knowledge", ["knowledge", OWN, "::x"]),
    "suite-run": (suite_run, "cmd_suite_run", ["suite-run"]),
    "plank-run": (plank_run, "cmd_plank_run", ["plank-run", OWN]),
    "mutation-run": (mutation_run, "cmd_mutation_run", ["mutation-run"]),
}


@pytest.mark.parametrize("command", list(_COMMANDS))
def test_ac14_dispatcher_child_path_without_wrapper(pult, monkeypatch, command):
    """Дочерний процесс команды пульта под признаком роли — PATH роли без каталога обёртки.

    Диспетчер `artel.main()` запускается под окружением роли (признак роли,
    PATH с обёрткой); реализация команды подменена пробой, которая
    запускает дочерний процесс и читает его окружение, и тем же вызовом
    дочерний `git clean -n` в своей рабочей копии. Наблюдается: PATH ребёнка
    — PATH роли без `orchestrator/role_bin/`, прочие элементы и порядок
    прежние; `GIT_CEILING_DIRECTORIES` и `ARTEL_GIT_GUARD_ROOT` ребёнка равны
    значениям окружения роли; дочерний `git clean -n` проходит (код 0).

    Ловит мутацию: диспетчер не снимает обёртку для дочерних процессов —
    дочерний `git clean -n` получает отказ механизма; снимает её вместе с
    потолком (`GIT_CEILING_DIRECTORIES` пропал у ребёнка); переставляет
    элементы PATH.
    """
    env = pult.role_env()
    seen = {}

    def probe(*args, **kwargs):
        seen["env"] = _child_env()
        git = shutil.which("git", path=os.environ["PATH"])
        seen["clean"] = subprocess.run([git, "clean", "-n"], cwd=str(pult.own),
                                       capture_output=True, text=True, timeout=60)

    module, attr, argv = _COMMANDS[command]
    monkeypatch.setattr(module, attr, probe)
    _enter_role_env(monkeypatch, env)

    _main(monkeypatch, *argv)

    child = seen["env"]
    assert env.get(CEILING) and env.get(GUARD_ROOT), sorted(env)
    assert child["PATH"] == without_wrapper(env)["PATH"]
    assert child.get(CEILING) == env.get(CEILING)
    assert child.get(GUARD_ROOT) == env.get(GUARD_ROOT)
    assert seen["clean"].returncode == 0, output(seen["clean"])


@pytest.mark.parametrize("exit_kind", ["return", "system_exit", "exception"])
def test_ac14_os_environ_restored_after_main(pult, monkeypatch, exit_kind):
    """`os.environ` после `artel.main()` под признаком роли совпадает с прежним при любом выходе.

    Реализация команды подменена: обычный возврат, `SystemExit` или
    исключение внутри команды. Наблюдается: словарь `os.environ` после
    вызова равен снимку до вызова (PATH с обёрткой на месте).

    Ловит мутацию: диспетчер снимает обёртку правкой `os.environ` без
    восстановления в `finally` — после `SystemExit` или исключения PATH
    процесса остаётся без каталога обёртки.
    """
    env = pult.role_env()

    def command(rest):
        if exit_kind == "system_exit":
            sys.exit("отказ команды")
        if exit_kind == "exception":
            raise RuntimeError("сбой команды")

    monkeypatch.setattr(knowledge_cards, "cmd_knowledge", command)
    _enter_role_env(monkeypatch, env)
    before = dict(os.environ)

    try:
        _main(monkeypatch, "knowledge", OWN, "::x")
    except RuntimeError:
        pass

    assert dict(os.environ) == before


def test_ac14_knowledge_from_docs_dir_same_as_from_worktree(pult, monkeypatch, capsys):
    """`knowledge` под окружением роли из каталога документов — тот же исход, что из своей копии.

    Каталог документов — подкаталог ROOT, не репозиторий; потолок у
    дочерних процессов на месте. Наблюдается: код возврата и вывод команды
    при текущем каталоге, равном каталогу документов, совпадают с запуском
    из своей рабочей копии.

    Ловит мутацию: вызов git пульта без `-C` исполняется с текущим каталогом
    вызова, а не `<ROOT>` — из каталога документов он упирается в потолок
    («not a git repository») и вывод расходится.
    """
    env = pult.role_env()
    _enter_role_env(monkeypatch, env)
    results = {}
    for place in (pult.own, pult.docs):
        monkeypatch.chdir(place)
        code = _main(monkeypatch, "knowledge", OWN, "::x")
        results[place] = (code, capsys.readouterr().out)

    assert results[pult.docs] == results[pult.own]


def test_ac14_pult_marker_does_not_free_git_clean(pult):
    """`ARTEL_PULT_GIT=1` в окружении роли не освобождает прямой `git clean` в репозитории пульта.

    Ловит мутацию: обёртка пропускает вызов с маркером пульта
    `ARTEL_PULT_GIT` — `git clean -n` в корне дублёра исполняется с кодом 0.
    """
    env = pult.role_env()

    res = pult.run(["clean", "-n"], env, pult.root, {"ARTEL_PULT_GIT": "1"})

    assert res.returncode != 0, output(res)
    assert TASK_RM in output(res), output(res)


_ARTEL_NOISE = {"ARTEL_PULT_GIT": "1", "ARTEL_GIT_GUARD": "0", "ARTEL_GIT_GUARD_OFF": "1",
                "ARTEL_ALLOW_GIT": "1", "ARTEL_ROLE": "", "ARTEL_TASK": ""}


def test_ac14_wrapper_with_artel_vars_still_refuses_clean(pult):
    """Обёртка, вызванная напрямую с `ARTEL_PULT_GIT=1` и посторонними `ARTEL_*`, отказывает на `git clean`.

    `ARTEL_GIT_GUARD_ROOT` — дублёр (из окружения роли). Наблюдается:
    ненулевой код, строка причины, игнорируемые файлы дублёра на месте.

    Ловит мутацию: переменная-выключатель — обёртка пропускает вызов при
    `ARTEL_PULT_GIT=1` (или ином `ARTEL_*`) и `git -C <дублёр> clean -fX`
    удаляет `ignored.txt`.
    """
    env = dict(pult.role_env(), **_ARTEL_NOISE)
    env[GUARD_ROOT] = str(pult.root)

    res = subprocess.run([str(WRAPPER_DIR / "git"), "-C", str(pult.root), "clean", "-fX"],
                         cwd=str(pult.outside), env=env, capture_output=True, text=True,
                         timeout=30)

    assert refusal_problems(res, "pult") == [], output(res)
    assert not pult.missing_ignored(), pult.missing_ignored()


def test_ac14_copied_wrapper_protects_its_own_root(pult, tmp_path):
    """Пакет обёртки, скопированный в дублёр, защищает дублёр и при постороннем `ARTEL_GIT_GUARD_ROOT`.

    `<дублёр>/orchestrator/role_bin` и `<дублёр>/orchestrator/role_git.py` —
    копия пакета; обёртка копии вызвана с `ARTEL_GIT_GUARD_ROOT`, указывающим
    на посторонний временный каталог, и с `ARTEL_PULT_GIT=1`. Наблюдается:
    `git -C <дублёр> clean -fX` — ненулевой код, строка причины, игнорируемые
    файлы дублёра на месте.

    Ловит мутацию: переменная заменяет корень, вычисленный от расположения
    файла обёртки, а не добавляет к нему — дублёр остаётся без защиты и
    `ignored.txt` удаляется.
    """
    assert WRAPPER_DIR.is_dir(), f"нет каталога обёртки {WRAPPER_DIR}"
    target = pult.root / "orchestrator"
    target.mkdir()
    shutil.copytree(WRAPPER_DIR, target / "role_bin", symlinks=True)
    shutil.copy2(WRAPPER_DIR.parent / "role_git.py", target / "role_git.py")
    foreign = tmp_path / "foreign-guard-root"
    foreign.mkdir()
    env = dict(pult.role_env(), **_ARTEL_NOISE)
    env[GUARD_ROOT] = str(foreign)

    res = subprocess.run([str(target / "role_bin" / "git"), "-C", str(pult.root),
                          "clean", "-fX"], cwd=str(pult.outside), env=env,
                         capture_output=True, text=True, timeout=30)

    assert refusal_problems(res, "pult") == [], output(res)
    assert not pult.missing_ignored(), pult.missing_ignored()


def test_ac15_direct_pytest_of_clean_test_under_role_env_green(pult):
    """Прямой `pytest` долгоживущего теста с временным репозиторием и `git clean` под окружением роли — зелёный.

    Файл — `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py` кодовой
    ветки, путь — относительный от корня кода (так роль обязана звать pytest,
    `conftest.py::_is_targeted_path`); процесс pytest получает окружение
    роли артели (PATH с обёрткой, потолок, корень механизма).

    Ловит мутацию: механизм отказывает `git clean` в любом репозитории, а не
    только внутри защищаемого корня, — временные репозитории теста не
    чистятся, тест краснеет.
    """
    env = pult.role_env()

    res = subprocess.run([sys.executable, "-m", "pytest", LONG_LIVED_WITH_CLEAN, "-q",
                          "-p", "no:cacheprovider"],
                         cwd=str(WRAPPER_ROOT), env=env, capture_output=True,
                         text=True, timeout=110)

    assert res.returncode == 0, output(res)[-4000:]


def _boundary_check():
    from orchestrator import doctor
    return doctor.check_role_git_boundary()


def _artel_dirs(pult) -> set:
    return {p.name for p in (pult.root / ".artel").iterdir() if p.is_dir()}


@pytest.mark.parametrize("variant, expected", [
    ("intact", "ok"), ("no_ceiling", "fail"), ("no_wrapper", "fail")])
def test_ac17_doctor_boundary_row(pult, monkeypatch, variant, expected):
    """Строка doctor на исправном окружении — ok, без потолка или без отказа `git clean` — fail.

    Сборка окружения роли (`runner.role_env`) подменена в тесте: без
    `GIT_CEILING_DIRECTORIES` (механизм на месте) либо без каталога обёртки в
    PATH (потолок на месте). Наблюдается: статус строки; игнорируемые файлы
    корня дублёра на месте; новых каталогов в `<ROOT>/.artel` после
    проверки нет (временный подкаталог удалён).

    Ловит мутацию: строка проверяет только часть (а) или только часть (б) —
    одна из подмен даёт ok; временный подкаталог не убирается после
    проверки — в `<ROOT>/.artel` остаётся лишний каталог.
    """
    original = runner.role_env

    def patched(*args, **kwargs):
        env = dict(original(*args, **kwargs))
        if variant == "no_ceiling":
            env.pop(CEILING, None)
        elif variant == "no_wrapper":
            env = without_wrapper(env)
        return env

    monkeypatch.setattr(runner, "role_env", patched)
    before = _artel_dirs(pult)

    check = _boundary_check()

    assert check.status == expected, check.detail
    assert not pult.missing_ignored(), pult.missing_ignored()
    assert _artel_dirs(pult) == before


def test_ac17_doctor_boundary_row_tmpdir_failure(pult, monkeypatch):
    """Создание временного подкаталога `<ROOT>/.artel` отказывает `OSError` — строка fail с причиной.

    Подмена `os.mkdir` отказывает новому каталогу прямо под `<ROOT>/.artel`
    (так отказывает песочница Codex). Наблюдается: `doctor` не падает
    исключением, статус fail, причина непуста.

    Ловит мутацию: `OSError` создания каталога не перехватывается — строка
    падает исключением вместо fail.
    """
    artel_dir = pult.root / ".artel"
    real_mkdir = os.mkdir

    def refusing_mkdir(path, *args, **kwargs):
        target = Path(os.fsdecode(path))
        if target.parent.resolve() == artel_dir and not target.exists():
            raise OSError(13, "Operation not permitted (тест)", str(target))
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", refusing_mkdir)

    check = _boundary_check()

    assert check.status == "fail"
    assert check.detail.strip()


def test_ac19_without_guard_root_variable_wrapper_root_protected(pult):
    """Без `ARTEL_GIT_GUARD_ROOT` механизм защищает корень от расположения файла обёртки.

    Из окружения роли убрана только `ARTEL_GIT_GUARD_ROOT` (обёртка в PATH).
    Наблюдается: `git -C <orchestrator/role_bin/../..> status` — ненулевой код
    и строка причины требования 2 (только читающая команда); `git status`
    во временном репозитории вне этого корня и вне дублёра — код 0.

    Ловит мутацию: без переменной механизм пропускает всё (fail-open) —
    `git -C <корень обёртки> status` исполняется с кодом 0.
    """
    env = pult.role_env()
    env.pop(GUARD_ROOT, None)
    free = pult.base / "free-repo"
    free.mkdir()
    pult.git_seed("init", "-q", cwd=free)

    refused = pult.run(["-C", str(WRAPPER_ROOT), "status"], env, pult.outside)
    passed = pult.run(["status"], env, free)

    assert refusal_problems(refused, "pult") == [], output(refused)
    assert PULT_PHRASE in output(refused)
    assert passed.returncode == 0, output(passed)
