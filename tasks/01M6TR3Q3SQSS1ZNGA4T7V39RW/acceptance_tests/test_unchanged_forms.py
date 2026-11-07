"""Прежние формы этой задачи: набор команд роли и побайтно прежние `plank-run`/`suite-run` вне режима запроса — против кода базы ветки.

Группа: разовый
Зелёный с рождения: до кода задачи код ветки равен коду базы — вывод и действие команд совпадают, набор `_ROLE_ALLOWED_COMMANDS` тот же; тест держит, что реализация режима запроса их не меняет.

Код базы — `git archive <DIFF_BASE> orchestrator scripts` рабочей копии
задачи (база — `_pult.DIFF_BASE`, точка расхождения с origin). Сравнение
вывода и действия — две одинаковые песочницы (`real_git`-песочница и копия
пульта из долгоживущего файла задачи `tests/test_01m6tr3q3sqss1znga4t7v39rw_
role_requests.py`, класс `Pult`) с одним зерном: в первой — код базы, во
второй — код ветки; сценарий тот же. Сравниваются нормализованные выводы
команд (корень песочницы, временные каталоги, pid, шестнадцатеричные
хвосты имён и sha, длительности заменены метками) и нормализованные
журналы вызовов команды-заглушки `pytest-own` и подменённого `docker`.
"""
import ast
import io
import os
import random
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

from tests.sandbox import RealGitSandbox  # noqa: E402
from tests.test_01m6tr3q3sqss1znga4t7v39rw_role_requests import Pult  # noqa: E402

ROLE = "test_author"


def base_text(rel: str) -> str:
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show",
                          f"{DIFF_BASE}:{rel}"], capture_output=True,
                         text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return res.stdout


def allowed_commands(text: str) -> str:
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_ROLE_ALLOWED_COMMANDS"
                for t in node.targets):
            return ast.dump(node.value)
    return ""


def test_ac6_role_allowed_commands_set_unchanged():
    """Значение `_ROLE_ALLOWED_COMMANDS` в `orchestrator/artel.py` ветки совпадает со значением базы.

    Сравнивается разобранное выражение присваивания (AST), не строки
    файла: правка комментария-основания над набором законна (требование 5),
    правка самого набора — нет.

    Ловит мутацию: в набор команд роли добавлена или из него убрана
    команда (например, `plank-run` вынесен в отдельный разбор) — дерево
    выражения отличается от базы.
    """
    head = (Path(CODE_ROOT) / "orchestrator" / "artel.py").read_text(
        encoding="utf-8")
    base = allowed_commands(base_text("orchestrator/artel.py"))
    assert base, "в коде базы нет _ROLE_ALLOWED_COMMANDS"
    assert allowed_commands(head) == base


@pytest.fixture(scope="module")
def base_code():
    dest = Path(tempfile.mkdtemp(prefix="artel-base-code-")).resolve()
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "archive",
                          "--format=tar", str(DIFF_BASE), "orchestrator",
                          "scripts"], capture_output=True, timeout=120)
    if res.returncode == 0:
        tarfile.open(fileobj=io.BytesIO(res.stdout)).extractall(dest, filter="data")
    try:
        yield dest
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def install(p: Pult, source: Path) -> None:
    for name in ("orchestrator", "scripts"):
        shutil.rmtree(p.root / name, ignore_errors=True)
        shutil.copytree(source / name, p.root / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    p.set_config(AGENT_TIMEOUT_SEC=100)


def normalize(text: str, p: Pult, raw_root: str) -> str:
    for old, new in ((str(p.root), "<ROOT>"), (raw_root, "<ROOT>"),
                     (str(p.probe), "<PROBE>")):
        text = text.replace(old, new)
    text = re.sub(r"(/private)?/(var/folders|tmp)/[^\s;,)'\"]+", "<TMP>", text)
    text = re.sub(r"\b[0-9a-f]{7,40}\b", "<HEX>", text)
    text = re.sub(r"\d+\.\d+", "<F>", text)
    text = re.sub(r"pid \d+", "pid <N>", text)
    text = re.sub(r"идёт \d+ с", "идёт <N> с", text)
    return text


def transcript(seed: int, source: Path, case: str) -> tuple:
    """(нормализованные выводы и действия, файлы очереди задачи) сценария
    `case` в свежей песочнице с кодом `source`."""
    rg = RealGitSandbox()
    rg.setUp()
    p = Pult(rg, seed)
    try:
        raw_root = str(rg.root)
        p.build()
        install(p, source)
        if case == "compose_outside":
            target = p.compose_project()
            task, _wt, plank = p.task(target)
            role = None
        elif case == "multi_own_role":
            target, own_zone, _box = p.multi_project()
            task, _wt, plank = p.task(target, zones=own_zone)
            role = ROLE
        else:
            task, _wt, plank = p.task(p.own_project())
            role = ROLE
        p.lease(task)
        commands = [["plank-run", task], ["plank-run", task, plank],
                    ["suite-run", task], ["suite-run", task, "--wait", "1"]]
        lines = []
        for command in commands:
            before_own, before_docker = len(p.own()), len(p.calls())
            code, out = p.cli(*command, role=role)
            own = [(c["argv"], c["cwd"], c["role"])
                   for c in p.own()[before_own:]]
            docker = [(c["kind"], c["sub"], c["rest"])
                      for c in p.calls()[before_docker:]]
            lines.append(normalize(
                f"$ {' '.join(command)}\nкод {code}\n{out}\nзаглушка {own}\n"
                f"docker {docker}\n", p, raw_root))
        return "".join(lines), p.requests(task)
    finally:
        p.stop()
        rg.doCleanups()


@pytest.mark.parametrize("case", ["own_role", "multi_own_role",
                                  "compose_outside"])
@pytest.mark.timeout(400)
def test_ac20_commands_outside_request_mode_unchanged(base_code, case):
    """Вне режима запроса — проект без `compose` в процессе роли, задача компонента `pytest-own` проекта с `compose`, вызов вне шага роли в проекте с `compose` — вывод и действие `plank-run <id>`, `plank-run <id> <файл>`, `suite-run <id>` прежние побайтно; запрос не записан.

    Сценарий одинаковым зерном в двух песочницах — с кодом базы и с кодом
    ветки; `suite-run <id> --wait 1` забирает отчёт прогона. Нормализованные
    выводы, вызовы заглушки и `docker` совпадают; очередь запросов задачи
    пуста.

    Ловит мутацию: режим запроса включается по проекту целиком или вне шага
    роли (вывод «запрос принят», заглушка/`docker` не вызваны, файл в
    очереди); прежний вывод `plank-run`/`suite-run` переписан (иные строки).
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    assert (base_code / "orchestrator" / "artel.py").is_file(), \
        f"код базы {DIFF_BASE} не выложен"
    base, _ = transcript(seed, base_code, case)
    acted = "('compose', 'run'" if case == "compose_outside" else "заглушка [(["
    assert acted in base, f"зерно {seed}: сценарий базы не дошёл до прогона:\n{base}"
    head, queued = transcript(seed, Path(CODE_ROOT), case)
    assert queued == [], f"зерно {seed}: {queued}"
    assert head == base, f"зерно {seed}:\n--- база\n{base}\n--- ветка\n{head}"


@pytest.mark.parametrize("role", [None, ROLE])
@pytest.mark.timeout(300)
def test_ac24_plank_run_forms_unchanged_without_compose(base_code, role):
    """Проект без `compose`: `plank-run <id>` и `plank-run <id> <файл>` — разбор, вывод и действие прежние побайтно (вне шага роли и в процессе роли).

    Ловит мутацию: новый разбор аргументов меняет прежние формы (файл
    планки читается как флаг, иной текст вывода, заглушка зовётся с иными
    аргументами или не зовётся).
    """
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    assert (base_code / "orchestrator" / "artel.py").is_file(), \
        f"код базы {DIFF_BASE} не выложен"
    base, _ = transcript_plank(seed, base_code, role)
    assert "заглушка [([" in base, \
        f"зерно {seed}: сценарий базы не дошёл до прогона:\n{base}"
    head, queued = transcript_plank(seed, Path(CODE_ROOT), role)
    assert queued == [], f"зерно {seed}: {queued}"
    assert head == base, \
        f"зерно {seed}, роль {role}:\n--- база\n{base}\n--- ветка\n{head}"


def transcript_plank(seed: int, source: Path, role) -> tuple:
    rg = RealGitSandbox()
    rg.setUp()
    p = Pult(rg, seed)
    try:
        raw_root = str(rg.root)
        p.build()
        install(p, source)
        task, _wt, plank = p.task(p.own_project())
        p.lease(task)
        lines = []
        for command in (["plank-run", task], ["plank-run", task, plank]):
            before = len(p.own())
            code, out = p.cli(*command, role=role)
            own = [(c["argv"], c["cwd"], c["role"]) for c in p.own()[before:]]
            lines.append(normalize(f"$ {' '.join(command)}\nкод {code}\n{out}\n"
                                   f"заглушка {own}\n", p, raw_root))
        return "".join(lines), p.requests(task)
    finally:
        p.stop()
        rg.doCleanups()
