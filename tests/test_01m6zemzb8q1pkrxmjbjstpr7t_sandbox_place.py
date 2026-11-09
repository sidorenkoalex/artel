"""Песочница процесса тестов уводит место шаблонов байткода от места по умолчанию (AC-15).

Группа: долгоживущий
Красен до реализации: `config.PYCACHE_TEMPLATES_ENV`/`config.pycache_templates_dir` ещё нет — чтение имени переменной падает `AttributeError`, `tests/sandbox.py` переменную места дочерним процессам не ставит.

Связка «импорт `tests.sandbox` — константа `config` и переменная окружения
— дочерние процессы»: подмену наследуют только настоящие дочерние процессы.
Дочерний pytest гоняет залоченный файл
`tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py` и прочие долгоживущие
файлы этой задачи (тот же префикс имени, что у этого файла) с `TMPDIR` в
каталоге теста и без переменной места в окружении; место по умолчанию
этого процесса — `<TMPDIR>/pycache-templates-<uid>`. Процесс — в своей
группе, с пределом времени; по пределу снимается вся группа.

Провалидировано временным стабом реализации (удалён, не закоммичен): оба
метода зелёные; снятая переменная окружения в `tests/sandbox.py` краснит
первый, снятая подмена места целиком — второй (место по умолчанию
создаёт живой прогон ac6 залоченного файла).
"""
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from orchestrator import config, stack
from tests import sandbox  # noqa: F401 — импорт ставит подмену места

pytestmark = pytest.mark.size("large")

LOCKED_FILE = "test_01m3y7g6t3mk7a899521vf9n7b_pycache.py"
CHILD_TIMEOUT_SEC = 100
# Дочерние pytest, между которыми делятся тесты: файлы задачи гоняют
# настоящие прогоны pytest, одним процессом они близки к пределу времени
# теста. Не xdist: рабочий процесс xdist внутри шага роли отказывает
# сторож `conftest.py` (у него нет аргументов-путей).
CHILD_SHARDS = 4
ENV_PROBE = "import os, sys\nsys.stdout.write(os.environ.get(sys.argv[1], '<нет>'))\n"


def sibling_files() -> list:
    """Долгоживущие файлы задачи рядом с этим, кроме него самого."""
    here = Path(__file__).resolve()
    prefix = "_".join(here.name.split("_")[:2]) + "_"
    return sorted(f"{here.parent.name}/{p.name}"
                  for p in here.parent.glob(prefix + "*.py") if p != here)


def run_group(argv, *, cwd, env, timeout) -> tuple:
    """(код, вывод) процесса в своей группе; по пределу — снять группу."""
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return None, out
    return proc.returncode, out


def run_shards(argvs, *, cwd, env, timeout, logs: Path) -> list:
    """[(код, вывод)] процессов, идущих одновременно, каждый в своей группе
    и со своим файлом вывода; общий предел — `timeout`, по нему снимаются
    группы оставшихся."""
    procs = []
    for index, argv in enumerate(argvs):
        log = logs / f"shard{index}.log"
        with open(log, "wb") as fh:
            procs.append((subprocess.Popen(argv, cwd=cwd, env=env, stdout=fh,
                                           stderr=subprocess.STDOUT,
                                           start_new_session=True), log))
    deadline = time.monotonic() + timeout
    results = []
    for proc, log in procs:
        try:
            code = proc.wait(timeout=max(1.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            code = None
        results.append((code, log.read_text(encoding="utf-8", errors="replace")))
    return results


def test_ac15_child_process_inherits_sandbox_place():
    """Дочерний процесс процесса тестов видит переменную места со значением песочницы.

    `tests.sandbox` импортирован; интерпретатор пульта, запущенный
    `subprocess` без явного `env`, печатает значение переменной
    `config.PYCACHE_TEMPLATES_ENV`: оно равно `config.PYCACHE_TEMPLATES_DIR`
    процесса тестов и не равно месту по умолчанию от системного временного
    каталога.

    Ловит мутацию: `tests/sandbox.py` ставит только константу `config`, а
    переменную окружения процесса не ставит — дочерний процесс печатает
    «<нет>».
    """
    name = config.PYCACHE_TEMPLATES_ENV
    place = config.PYCACHE_TEMPLATES_DIR
    default = config.pycache_templates_dir({}, tempfile.gettempdir(), os.getuid(),
                                           str(config.ROOT))
    code, out = run_group([stack.pytest_python_executable(), "-c", ENV_PROBE, name],
                          cwd=str(config.ROOT), env=None, timeout=60)
    assert code == 0, out
    assert place, "место шаблонов песочницы не задано"
    assert out == str(place), f"дочерний процесс видит {out!r}, песочница {place!r}"
    assert out != default, f"место песочницы — место по умолчанию {default}"


def test_ac15_suite_does_not_touch_default_template_place(tmp_path):
    """Дочерний pytest набора задачи не создаёт место шаблонов по умолчанию.

    `TMPDIR` дочернего процесса — каталог теста, переменной места в его
    окружении нет. Дочерний pytest гоняет залоченный файл кеша байткода и
    прочие долгоживущие файлы задачи. Каталога
    `<TMPDIR>/pycache-templates-<uid>` нет ни до, ни после; прогон зелёный.

    Ловит мутацию: подмена места в `tests/sandbox.py` снята или ставится
    после импорта модулей, уже прочитавших место, — живой прогон
    залоченного теста ac6 собирает шаблон в месте по умолчанию, каталог
    появляется.
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    child_tmp = tmp_path / f"tmp{seed}"
    child_tmp.mkdir()
    default = child_tmp / f"pycache-templates-{os.getuid()}"
    env = {k: v for k, v in os.environ.items()
           if k not in (config.PYCACHE_TEMPLATES_ENV, "PYTHONPYCACHEPREFIX")}
    env["TMPDIR"] = str(child_tmp)
    # Пути от корня в форме `tests/<файл>`: так их принимает и сторож роли
    # `conftest.py`, когда тест гоняется внутри шага роли.
    files = [f"{Path(__file__).resolve().parent.name}/{LOCKED_FILE}", *sibling_files()]
    assert not default.exists(), f"зерно {seed}: место по умолчанию уже есть"
    head = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    code, listing = run_group([*head, "--collect-only", *files], cwd=str(config.ROOT),
                              env=env, timeout=CHILD_TIMEOUT_SEC)
    assert code == 0, f"зерно {seed}: сбор дочернего прогона ({code})\n{listing[-3000:]}"
    nodes = [line for line in listing.splitlines() if "::" in line]
    assert nodes, f"зерно {seed}: дочерний сбор пуст\n{listing[-3000:]}"
    random.Random(seed).shuffle(nodes)
    shards = [nodes[i::CHILD_SHARDS] for i in range(CHILD_SHARDS)]
    results = run_shards([[*head, *shard] for shard in shards if shard],
                         cwd=str(config.ROOT), env=env, timeout=CHILD_TIMEOUT_SEC,
                         logs=tmp_path)
    tails = "\n".join(out[-1500:] for _code, out in results)
    assert not default.exists(), f"зерно {seed}: создано {default}\n{tails}"
    assert all(code == 0 for code, _out in results), (
        f"зерно {seed}: дочерний прогон красный "
        f"{[code for code, _out in results]}\n{tails}")
