"""AC-1, AC-2, AC-3: граница подъёма git и отказ git в репозитории пульта и в чужой задаче.

Группа: разовый
Предмет критериев — исход вызова git под окружением роли, а правило
долгоживущих файлов `tests/` запрещает вызов git через `subprocess`
(`scripts/guard.py::long_lived_sign_hits`); поэтому файл — в планке.

Все меняющие команды (`reset --hard`, `checkout -- .`) идут только против
дублёра ROOT (`_doubler.Doubler`), подставленного через `config.ROOT`/
`config.PROJECTS` и `runner.role_env`.

Красен до реализации: `runner.role_env` ещё не кладёт ни `GIT_CEILING_DIRECTORIES`, ни обёртку `orchestrator/role_bin/` в PATH — git из каталогов дублёра находит его репозиторий и исполняет команды без строки отказа механизма.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _doubler import (GIT_NOT_REPO, MODIFIED, TRACKED_MARK, Doubler,  # noqa: E402
                      output, refusal_problems, without_ceiling, without_wrapper)


@pytest.fixture
def pult(tmp_path, monkeypatch):
    return Doubler(tmp_path, monkeypatch)


def _cwd(pult, key: str) -> Path:
    return {
        "docs": pult.docs,
        "tasks": pult.docs.parent,
        "project": pult.area,
        "projects": pult.projects,
        "artel": pult.root / ".artel",
        "artel_logs": pult.root / ".artel" / "logs",
    }[key]


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("cwd_key", ["docs", "tasks", "project", "projects",
                                     "artel", "artel_logs"])
def test_ac1_git_status_from_pult_dirs_does_not_reach_pult_repo(pult, provider, cwd_key):
    """`git status` из каталога внутри `<ROOT>/.artel`, который сам не репозиторий.

    (а) Под окружением роли провайдера — ненулевой код, состояние
    репозитория пульта (изменённый отслеживаемый файл, ветка) не выведено;
    (б) под тем же окружением без каталога обёртки в PATH (так механизм
    требований 2–3 снимает диспетчер, граница на месте) — ненулевой код с
    «not a git repository». Тот же `git status` в своей рабочей копии и в
    клоне проекта — код 0 в обоих окружениях.

    Ловит мутацию: потолок подъёма равен ровно `<ROOT>/.artel` — git из самого
    `<ROOT>/.artel` в окружении (б) находит репозиторий дублёра и печатает
    `docs/pult-marker-file.md`, код 0.
    """
    env = pult.role_env(provider)
    cwd = _cwd(pult, cwd_key)

    full = pult.run(["status"], env, cwd)
    bare = pult.run(["status"], without_wrapper(env), cwd)

    assert full.returncode != 0, output(full)
    assert TRACKED_MARK not in output(full), output(full)
    assert "On branch" not in output(full), output(full)
    assert bare.returncode != 0, output(bare)
    assert GIT_NOT_REPO in output(bare), output(bare)
    assert TRACKED_MARK not in output(bare), output(bare)
    for place in (pult.own, pult.clone):
        for variant in (env, without_wrapper(env)):
            ok = pult.run(["status"], variant, place)
            assert ok.returncode == 0, f"{place}: {output(ok)}"


def _refused_forms(pult) -> dict:
    """{имя формы: (аргументы, текущий каталог, добавка окружения, вид отказа)}."""
    root, own, other = pult.root, pult.own, pult.other
    outside = pult.outside
    link = outside / "link-to-root"
    if not link.exists():
        link.symlink_to(root, target_is_directory=True)
    rel_root = os.path.relpath(root, outside)
    return {
        "C-root": (["-C", str(root), "status"], outside, {}, "pult"),
        "C-artel": (["-C", str(root / ".artel"), "status"], outside, {}, "pult"),
        "C-docs-reset": (["-C", str(root / "docs"), "reset", "--hard"],
                         outside, {}, "pult"),
        "git-dir": ([f"--git-dir={root / '.git'}", "status"], outside, {}, "pult"),
        "GIT_DIR": (["status"], outside, {"GIT_DIR": str(root / ".git")}, "pult"),
        "core-worktree": (["-c", f"core.worktree={root}", "status"], own, {}, "pult"),
        "C-other": (["-C", str(other), "status"], outside, {}, "foreign"),
        "C-other-sub": (["-C", str(other / "sub"), "status"], outside, {}, "foreign"),
        "cwd-docs-reset": (["reset", "--hard"], root / "docs", {}, "pult"),
        "cwd-docs-checkout": (["checkout", "--", "."], root / "docs", {}, "pult"),
        "C-own-then-rel": (["-C", str(own), "-C", "../..", "status"],
                           outside, {}, "pult"),
        "C-outside-then-rel": (["-C", str(outside), "-C", rel_root, "status"],
                               outside, {}, "pult"),
        "C-symlink": (["-C", str(link), "status"], outside, {}, "pult"),
        "cwd-symlink": (["status"], link, {}, "pult"),
    }


@pytest.mark.parametrize("variant", ["role", "no_ceiling"])
@pytest.mark.parametrize("form", [
    "C-root", "C-artel", "C-docs-reset", "git-dir", "GIT_DIR", "core-worktree",
    "C-other", "C-other-sub", "cwd-docs-reset", "cwd-docs-checkout",
    "C-own-then-rel", "C-outside-then-rel", "C-symlink", "cwd-symlink"])
def test_ac2_git_into_pult_or_foreign_worktree_refused(pult, form, variant):
    """Каждая отклоняемая форма AC-2 — под окружением роли и без границы требования 1.

    Форма разыгрывается в дублёре: `-C`/`--git-dir`/`GIT_DIR`/
    `-c core.worktree` на ROOT, `<ROOT>/.artel`, `<ROOT>/docs`; `-C` на чужую
    рабочую копию и её подкаталог; текущий каталог `<ROOT>/docs` для
    `reset --hard`/`checkout -- .`; цепочки `-C` с относительным путём;
    символическая ссылка вне ROOT, ведущая в ROOT. Окружение «no_ceiling» —
    окружение роли без `GIT_CEILING_DIRECTORIES`, механизм на месте, так что
    отказ даёт механизм, а не потолок. Наблюдается: ненулевой код, строка
    причины механизма (не «not a git repository»; «репозиторий пульта» и
    `task-rm` для ROOT, «рабочая копия другой задачи» главной строкой для
    чужой копии) и неизменённый изменённый отслеживаемый файл дублёра.

    Ловит мутацию: текущий каталог вызова проверяется только у `clean`
    (формы cwd-docs-* исполняются и `reset --hard` откатывает файл); путь
    сравнивается на равенство корню, а не на вложенность (C-artel,
    C-docs-reset проходят); учитывается только первый `-C` (C-own-then-rel
    проходит); относительный `-C` разрешается от исходного cwd
    (C-outside-then-rel проходит); `abspath` вместо `realpath` (C-symlink
    проходит в окружении no_ceiling); строка отказа — сообщение git (в
    выводе «not a git repository» без «репозиторий пульта»).
    """
    env = pult.role_env()
    if variant == "no_ceiling":
        env = without_ceiling(env)
    args, cwd, extra, kind = _refused_forms(pult)[form]

    res = pult.run(args, env, cwd, extra)

    problems = refusal_problems(res, kind)
    assert not problems, f"{form}/{variant}: {problems}\n{output(res)}"
    assert pult.tracked.read_text(encoding="utf-8") == MODIFIED, \
        f"{form}/{variant}: отслеживаемый файл дублёра откатился"


@pytest.mark.parametrize("form", ["C-own", "C-own-sub", "C-root-then-own"])
def test_ac2_git_into_own_worktree_passes(pult, form):
    """Своя рабочая копия и её подкаталог — успех, в том числе `-C <ROOT> -C <своя копия>`.

    Ловит мутацию: собственная рабочая копия не исключена из отказа «внутри
    ROOT» либо цепочка `-C` судится по первому `-C` (`-C <ROOT>`) — код
    возврата ненулевой.
    """
    env = pult.role_env()
    args = {
        "C-own": ["-C", str(pult.own), "status"],
        "C-own-sub": ["-C", str(pult.own / "sub"), "status"],
        "C-root-then-own": ["-C", str(pult.root), "-C", str(pult.own), "status"],
    }[form]

    res = pult.run(args, env, pult.outside)

    assert res.returncode == 0, f"{form}: {output(res)}"


@pytest.mark.parametrize("form", ["work-tree-root", "GIT_WORK_TREE-root",
                                  "work-tree-other", "GIT_WORK_TREE-other"])
def test_ac3_work_tree_into_pult_or_foreign_refused(pult, form):
    """`--work-tree`/`GIT_WORK_TREE` на ROOT или на чужую рабочую копию из своей копии.

    Ловит мутацию: механизм не читает `--work-tree`/`GIT_WORK_TREE` (судит
    только текущий каталог — свою рабочую копию) — `git status` исполняется
    с кодом 0 и без строки причины.
    """
    env = pult.role_env()
    root, other = str(pult.root), str(pult.other)
    args, extra, kind = {
        "work-tree-root": ([f"--work-tree={root}", "status"], {}, "pult"),
        "GIT_WORK_TREE-root": (["status"], {"GIT_WORK_TREE": root}, "pult"),
        "work-tree-other": ([f"--work-tree={other}", "status"], {}, "foreign"),
        "GIT_WORK_TREE-other": (["status"], {"GIT_WORK_TREE": other}, "foreign"),
    }[form]

    res = pult.run(args, env, pult.own, extra)

    problems = refusal_problems(res, kind)
    assert not problems, f"{form}: {problems}\n{output(res)}"
