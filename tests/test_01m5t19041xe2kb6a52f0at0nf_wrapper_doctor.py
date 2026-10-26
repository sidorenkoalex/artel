"""Строка `doctor` `target-wrapper-worktrees`: файлы обвязки на диске рабочих копий задач внешнего проекта; у артели — `ok` «рабочие копии артели полные по замыслу».

Группа: долгоживущий
Красен до реализации: среди строк `doctor.all_checks` нет строки `target-wrapper-worktrees` ни у одного проекта.

Связка, которую держит файл: «запись проекта — рабочие копии задач на
диске — `workspace.ensure` — `doctor.all_checks`». Песочница — настоящий git
(`tests.sandbox.RealGitSandbox`, фикстура `real_git`): внешний проект — клон
с bare `origin` (`tests.sandbox.make_project_repo`), запись с
`agent_wrapper: [harness/]`; в `main` клона — по сценарию корневой
`CLAUDE.md` либо только вложенный `sub/CLAUDE.md`, и `src/m.py`. Рабочая
копия задачи заведена полным `git worktree add` на месте
`workspace.path` (обвязка на диске), затем приведена `workspace.ensure`.
Строки `doctor` — публичный `doctor.all_checks(conn)`, строка ищется по
имени; прочие проверки зовут CLI ролей, `gh` и сетевой git — им отвечает
отказ запуска (приём долгоживущего теста строки `targets-local-layer`).
Имена — от зерна `random`; зерно печатается и входит в текст провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
константа маркеров, формула `**/<каталог>/`, поле `agent_wrapper` в обоих
слоях и переносе, перечень проекта, отказ `knowledge`, зоны каталога
обвязки, источник подсветки, sparse-checkout рабочей копии с игнором и
уборкой путей обвязки, строка `doctor` — все методы зелёные.
"""
import os
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import config, doctor, idgen, store, workspace
from tests.sandbox import artel_target_entry, make_project_repo

EXT = "vnesh"
CHECK = "target-wrapper-worktrees"
ARTEL_FULL = "рабочие копии артели полные по замыслу"
LETTERS = "abcdefghijkmnopqrstuvwxyz"
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}
MARKERS = ("**/.claude/", ".mcp.json", "**/CLAUDE.md", "**/AGENTS.md")

EXT_ENTRY = """  {name}:
    forge: github
    url: http://localhost/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    agent_wrapper: [harness/]
"""


def local_command(argv) -> bool:
    """Локальный процесс песочницы: `ps`, интерпретатор Python, git без сети."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return False
    words = [os.fsdecode(a) for a in argv]
    name = Path(words[0]).name
    if name == "git":
        return not NETWORK_GIT & set(words[1:])
    return name == "ps" or name.startswith("python") or words[0] == sys.executable


def doctor_lines() -> list:
    """Строки `doctor.all_checks`; внешние процессы не запускаются."""
    real_run, real_popen = subprocess.run, subprocess.Popen

    def run(argv, *args, **kwargs):
        if local_command(argv):
            return real_run(argv, *args, **kwargs)
        empty = b"" if not (kwargs.get("text") or kwargs.get("encoding")
                            or kwargs.get("universal_newlines")) else ""
        return subprocess.CompletedProcess(argv, 127, empty, empty)

    def popen(argv, *args, **kwargs):
        if local_command(argv):
            return real_popen(argv, *args, **kwargs)
        raise FileNotFoundError(f"песочница: внешний процесс {argv!r} не запускается")

    with mock.patch.object(subprocess, "run", run), \
            mock.patch.object(subprocess, "Popen", popen):
        return doctor.all_checks(store.db())


@pytest.fixture
def sb(real_git):
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
        yield real_git


@pytest.mark.parametrize("wrapper_file", ["CLAUDE.md", "sub/CLAUDE.md"])
def test_ac23_worktree_wrapper_warn_then_ok_after_ensure(sb, wrapper_file):
    """Файл обвязки на диске рабочей копии — `warn` с путём; после `ensure` — `ok`; detail называет действующий список обвязки; у артели — `ok` «полные по замыслу».

    Сценарий: в дереве проекта — файл обвязки сценария (корневой
    `CLAUDE.md` или вложенный `sub/CLAUDE.md`) и `src/m.py`; рабочая копия
    задачи — полный `git worktree add` на месте `workspace.path`. Строка
    `target-wrapper-worktrees` проекта — `warn`, detail называет путь файла
    и рабочую копию (её путь или id задачи). После `ensure` этой копии —
    `ok`. Detail в обоих случаях называет маркеры обвязки и элемент
    `agent_wrapper` `harness/`. Строка артели — `ok` с пояснением «рабочие
    копии артели полные по замыслу».

    Ловит мутацию: проверка смотрит только корень копии — вложенный
    `sub/CLAUDE.md` даёт `ok`; проверка смотрит клон, а не рабочие копии —
    `warn` и после `ensure`; detail строится из одних маркеров — нет
    `harness/`; у артели строка `warn` по её полной копии.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    clone = make_project_repo(EXT)
    config.TARGETS.write_text("targets:\n" + artel_target_entry()
                              + EXT_ENTRY.format(name=EXT), encoding="utf-8")
    for rel in (wrapper_file, "src/m.py"):
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        (clone / rel).write_text(f"{rel} {seed}\n", encoding="utf-8")
    sb.git("-C", str(clone), "add", "-A")
    sb.git("-C", str(clone), "commit", "-q", "-m", "обвязка проекта")
    sb.git("-C", str(clone), "push", "-q", "origin", config.MAIN_BRANCH)
    task_id = idgen.new_task_id()
    branch = f"task/{task_id.lower()}-" + "".join(rng.choice(LETTERS) for _ in range(5))
    store.insert_task(store.db(), task_id, "Фикстура doctor", "in_dev", branch,
                      EXT, config.DEFAULT_BUDGET_USD)
    wt = workspace.path(task_id, EXT)
    sb.git("-C", str(clone), "worktree", "add", "-q", "-b", branch, str(wt))
    assert (wt / wrapper_file).exists()

    def lines() -> tuple:
        checks = [c for c in doctor_lines() if c.name == CHECK]
        shown = "\n".join(f"[{c.status}] {c.detail}" for c in checks)
        artel = [c for c in checks if ARTEL_FULL in c.detail]
        ext = [c for c in checks if ARTEL_FULL not in c.detail]
        assert len(artel) == 1 and len(ext) == 1, f"зерно: {seed}; {shown}"
        return artel[0], ext[0], f"зерно: {seed}; {shown}"

    artel, ext, note = lines()
    assert artel.status == "ok", note
    assert ext.status == "warn", note
    assert wrapper_file in ext.detail, note
    assert str(wt) in ext.detail or task_id in ext.detail, note
    for item in (*MARKERS, "harness/"):
        assert item in ext.detail, note

    _path, error = workspace.ensure(task_id, branch)
    assert error is None, f"зерно: {seed}; {error}"
    artel, ext, note = lines()
    assert artel.status == "ok", note
    assert ext.status == "ok", note
    for item in (*MARKERS, "harness/"):
        assert item in ext.detail, note
