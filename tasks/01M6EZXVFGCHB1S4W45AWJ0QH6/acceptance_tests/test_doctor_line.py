"""Строка `doctor` `clone-push-hook` по клону проекта `target-human` и её починка `doctor --fix`; `core.hooksPath` рабочей копии задачи и отказ отправки из неё.

Группа: разовый
Красен до реализации: `check_clone_hooks` не выдаёт строки `clone-push-hook`, `_fix_project_clones` не возвращает хуки `target-human`, файл политики и `core.hooksPath` клона к эталону, а `gitcmd` не сверяет `core.hooksPath` конфигурации рабочей копии — шпион видит отправку из неё.

Группа «разовый» — по правилу guard, не по смыслу свойства: стенд
сверяет эталон хука с коммитом `HEAD` главной копии и отправку `gitcmd`
настоящим git (`scripts/guard.py::SIGN_GIT_CALL`, `_GIT_MODULES`).

Стенд — `_stand.Stand` поверх `real_git`: каталог `scripts/git-hooks`
проверяемого дерева закоммичен в `config.ROOT`; клон проекта
`target-human` заводит `workspace.ensure_clone`. Строка — из
`doctor.check_clone_hooks()`, починка — `doctor._fix_project_clones()`
(точки, которые называет требование 8 SPEC). Каждый сценарий сначала
видит строку `ok` у свежего клона — `fail` после порчи вызван ею. Зерно
`random` печатается и входит в текст провала.
"""
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _stand import TARGET_HUMAN, Stand, git, out  # noqa: E402

from orchestrator import config, doctor, gitcmd  # noqa: E402

CHECK = "clone-push-hook"


@pytest.fixture
def stand(real_git, monkeypatch, tmp_path):
    return Stand(real_git, monkeypatch, tmp_path)


def line(stand):
    found = [c for c in doctor.check_clone_hooks() if c.name == CHECK]
    assert len(found) == 1, stand.note(f"строки {CHECK}: {found}")
    return found[0]


def healthy_clone(stand) -> tuple:
    """(имя, клон) проекта `target-human`; строка у свежего клона — `ok`."""
    name, clone, _bare = stand.project(TARGET_HUMAN)
    fresh = line(stand)
    assert fresh.status == "ok", stand.note(f"свежий клон: {fresh.status} {fresh.detail}")
    return name, clone


def fix() -> None:
    doctor._fix_project_clones()


def hook_rel(hook: str) -> str:
    return f"scripts/git-hooks/{TARGET_HUMAN}/{hook}"


# -------------------------------------------------------------------- AC-11

def test_ac11_changed_pre_push_fails_and_fix_restores(stand):
    """`pre-push` каталога хуков `target-human`, изменённый против эталона из `HEAD`, даёт `fail`; после починки файл равен эталону, строка `ok`.

    Сценарий: к `<config.ROOT>/scripts/git-hooks/target-human/pre-push`
    дописана строка; строка `clone-push-hook` — `fail`; `doctor --fix` —
    файл побайтно равен `git show HEAD:<путь>`, строка `ok`.

    Ловит мутацию: сверка хука по наличию файла, а не по контрольной сумме
    с эталоном из `HEAD`; починка не переписывает изменённый файл.
    """
    _name, _clone = healthy_clone(stand)
    hook = stand.human_hooks_dir() / "pre-push"
    with hook.open("a", encoding="utf-8") as fh:
        fh.write("exit 0\n")
    broken = line(stand)
    assert broken.status == "fail", stand.note(f"{broken.status}: {broken.detail}")
    fix()
    assert hook.read_bytes() == stand.head_text(hook_rel("pre-push")), \
        stand.note("pre-push не равен эталону после --fix")
    repaired = line(stand)
    assert repaired.status == "ok", stand.note(f"{repaired.status}: {repaired.detail}")


# -------------------------------------------------------------------- AC-12

@pytest.mark.parametrize("damage", ["changed", "deleted"])
def test_ac12_policy_changed_or_deleted_fails_and_fix_restores(stand, damage):
    """Файл политики, изменённый против эталона по записи или удалённый, даёт `fail`; после починки он равен эталону, строка `ok`.

    Сценарий: в `<клон>/.git/artel-push-policy` значение `base` подменено
    либо файл удалён; строка — `fail`; `doctor --fix` — файл побайтно равен
    эталону по записи, строка `ok`.

    Ловит мутацию: строка проверяет только наличие файла политики (подмена
    `base` проходит) либо починка не пишет файл, если он есть.
    """
    name, clone = healthy_clone(stand)
    policy = stand.policy_path(clone)
    if damage == "deleted":
        policy.unlink()
    else:
        text = policy.read_text(encoding="utf-8").replace(
            f"base={config.MAIN_BRANCH}\n", f"base={stand.name('b')}\n")
        policy.write_text(text, encoding="utf-8")
    broken = line(stand)
    assert broken.status == "fail", stand.note(f"{damage}: {broken.status} {broken.detail}")
    fix()
    assert policy.is_file() and policy.read_bytes() == stand.expected_policy(name), \
        stand.note(f"{damage}: политика после --fix не эталон")
    repaired = line(stand)
    assert repaired.status == "ok", stand.note(f"{repaired.status}: {repaired.detail}")


# -------------------------------------------------------------------- AC-13

@pytest.mark.parametrize("value", ["foreign", "old", "unset"])
def test_ac13_wrong_clone_hooks_path_fails_and_fix_restores(stand, tmp_path, value):
    """`core.hooksPath` клона — чужой путь, прежний `<config.ROOT>/scripts/git-hooks` или снятый — `fail`; после починки он равен каталогу `target-human`, строка `ok`.

    Сценарий: значение `value` в конфигурации клона; строка — `fail`;
    `doctor --fix` — `core.hooksPath` клона = `<config.ROOT>/scripts/
    git-hooks/target-human`, строка `ok`.

    Ловит мутацию: прежний общий каталог хуков считается верным и для
    `target-human`; снятый `core.hooksPath` не расхождение; починка ставит
    прежний `workspace.hooks_path()`.
    """
    _name, clone = healthy_clone(stand)
    if value == "unset":
        git(clone, "config", "--unset-all", "core.hooksPath")
    else:
        path = tmp_path / "chuzhie" if value == "foreign" else stand.hooks_dir()
        git(clone, "config", "core.hooksPath", str(path))
    broken = line(stand)
    assert broken.status == "fail", stand.note(f"{value}: {broken.status} {broken.detail}")
    fix()
    fixed = out(clone, "config", "--get", "core.hooksPath")
    assert Path(fixed).resolve() == stand.human_hooks_dir().resolve(), \
        stand.note(f"{value}: после --fix {fixed!r}")
    repaired = line(stand)
    assert repaired.status == "ok", stand.note(f"{repaired.status}: {repaired.detail}")


# -------------------------------------------------------------------- AC-14

def test_ac14_worktree_hooks_path_fails_and_push_refused(stand, monkeypatch, tmp_path):
    """`core.hooksPath` с чужим значением в конфигурации рабочей копии задачи клона `target-human` даёт `fail` с этим значением в detail; отправка пульта из неё отказывается до вызова git.

    Сценарий: рабочая копия задачи `<область проекта>/worktrees/<id>` на
    ветке задачи; отправка из неё сначала доходит до шпиона; затем
    `extensions.worktreeConfig = true` и `git config --worktree
    core.hooksPath <чужой путь>`; строка — `fail`, detail содержит чужой
    путь; повтор отправки — ненулевой код, шпион второй отправки не видел.

    Ловит мутацию: строка и сверка `gitcmd` читают `core.hooksPath` только
    из конфигурации клона (`git -C <клон> config`), а не действующую
    конфигурацию рабочих копий из `git worktree list`.
    """
    name, clone = healthy_clone(stand)
    branch = stand.template_branch()
    task_id = stand.task(name, branch)
    wt = Path(config.PROJECTS) / name / "worktrees" / task_id
    stand.commit_branch(clone, branch)
    git(clone, "worktree", "add", "-q", str(wt), branch)
    stand.spy(monkeypatch)
    res = gitcmd.in_repo(wt, "push", "origin", branch)
    assert res.returncode == 0 and len(stand.pushes) == 1, stand.note(
        f"без находок отправка из рабочей копии не дошла до git: {res.stderr}")
    foreign = str(tmp_path / "huki-roli")
    git(clone, "config", "extensions.worktreeConfig", "true")
    git(wt, "config", "--worktree", "core.hooksPath", foreign)
    broken = line(stand)
    assert broken.status == "fail", stand.note(f"{broken.status}: {broken.detail}")
    assert foreign in broken.detail, stand.note(broken.detail)
    res = gitcmd.in_repo(wt, "push", "origin", branch)
    assert res.returncode != 0, stand.note("отправка из рабочей копии не отказана")
    assert len(stand.pushes) == 1, stand.note(f"шпион: {stand.pushes[1:]}")


# -------------------------------------------------------------------- AC-16

@pytest.mark.parametrize("hook", ["pre-push", "pre-commit"])
def test_ac16_hook_without_exec_bit_fails_and_fix_sets_it(stand, hook):
    """`pre-push`, а отдельно `pre-commit` каталога `target-human` без бита исполнения при эталонном содержимом — `fail`; после починки бит стоит, строка `ok`.

    Сценарий: с файла `hook` снят бит исполнения, содержимое прежнее; строка
    — `fail`; `doctor --fix` — у файла есть бит исполнения, строка `ok`.

    Ловит мутацию: сверяется только контрольная сумма (неисполняемый хук с
    эталонным текстом проходит) либо починка переписывает текст, не ставя
    бит.
    """
    _name, _clone = healthy_clone(stand)
    path = stand.human_hooks_dir() / hook
    path.chmod(path.stat().st_mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    assert path.read_bytes() == stand.head_text(hook_rel(hook))
    broken = line(stand)
    assert broken.status == "fail", stand.note(f"{hook}: {broken.status} {broken.detail}")
    fix()
    assert os.access(path, os.X_OK), stand.note(f"{hook}: бит исполнения не поставлен")
    repaired = line(stand)
    assert repaired.status == "ok", stand.note(f"{repaired.status}: {repaired.detail}")
