"""Одна проверка remote при отправке документов и досылка в сверке с origin
только при расхождении (SPEC 01M5QR7KGYZNVWDP5H86S9PY04, AC-1 — AC-10).

Песочница — настоящий git (`origin_real_git`, `tests/fixtures.py`): пульт —
`root`, bare-origin — `add_origin()`; задача артели в `in_dev` с первым
коммитом ссылки `refs/artifacts/<id>`, уже отправленным в origin. Шпион стоит
на `subprocess.run`, которым `gitcmd` запускает каждый git, — он видит и
`gitcmd.has_no_remote`; подкоманда берётся сквозь пары `-C <клон>`.
"""
import contextlib
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import artifact_branch, config, store
from tests.sandbox import init_bare_origin, strip_dash_c

TASK = "01UNITORIGINPUSHONE1"
PUSH_FAILED = "push артефактной ветки FAILED"


@contextlib.contextmanager
def git_spy():
    """Подкоманды git (без `-C <путь>`) всех процессов внутри блока."""
    calls = []
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            calls.append(strip_dash_c(cmd[1:]))
        return real_run(cmd, *args, **kwargs)

    with mock.patch.object(subprocess, "run", side_effect=spy):
        yield calls


def names_of(calls) -> list:
    return [c[0] if c else "" for c in calls]


def journal_rows() -> list:
    return list(store.task_steps(store.db(), TASK))


def commit(name: str) -> str:
    return artifact_branch.commit_files(
        TASK, {f"tasks/{TASK}/{name}": f"{name}\n"}, f"{TASK}: {name}")


def origin_head(sb, ref: str) -> str:
    out = sb.git("ls-remote", sb.bare, ref).split()
    return out[0] if out else ""


def local_head(sb, ref: str) -> str:
    return sb.git("for-each-ref", "--format=%(objectname)", ref).strip()


def make_env(sb) -> SimpleNamespace:
    store.insert_task(store.db(), TASK, "Задача", "in_dev",
                      f"task/{TASK.lower()}-x", config.DEFAULT_TARGET, 25.0)
    head0 = commit("SPEC.md")
    return SimpleNamespace(sb=sb, ref=artifact_branch.branch_name(TASK),
                           head0=head0, repo=artifact_branch.task_repo(TASK))


@pytest.fixture
def synced(origin_real_git):
    """Пульт с bare-origin; ссылка документов задачи совпадает с origin."""
    origin_real_git.add_origin()
    origin_real_git.git("push", "-q", "origin",
                        f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    return make_env(origin_real_git)


@pytest.fixture
def no_remote(origin_real_git):
    """Пульт без единого remote; ссылка документов задачи есть локально."""
    return make_env(origin_real_git)


def break_origin(sb) -> None:
    sb.git("remote", "set-url", "origin",
           str(sb.root / ".artel" / "нет-такого-origin.git"))


def restore_origin(sb) -> None:
    sb.git("remote", "set-url", "origin", sb.bare)


def commit_unsent(env, name: str) -> str:
    """Коммит ссылки, не дошедший до origin: локальная ссылка впереди."""
    break_origin(env.sb)
    try:
        return commit(name)
    finally:
        restore_origin(env.sb)


def reject_ref_pushes(sb) -> None:
    """origin отвергает запись в `refs/artifacts/*` (`pre-receive`)."""
    hook = Path(sb.bare) / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\n"
        "while read old new ref; do\n"
        "  case \"$ref\" in refs/artifacts/*) exit 1;; esac\n"
        "done\n"
        "exit 0\n", encoding="utf-8")
    hook.chmod(0o755)


def test_send_checks_remote_once_then_pushes(synced):
    """AC-1: `_send` при настроенном origin — один `git remote …` до push.

    Ловит мутацию: `_send` зовёт `_attempt_push` без признака проверенного
    origin — до `git push` два вызова `git remote` (`get-url origin` и
    голый `remote` из `has_no_remote`).
    """
    head = commit_unsent(synced, "PLAN.md")
    assert origin_head(synced.sb, synced.ref) == synced.head0

    with git_spy() as calls:
        ok = artifact_branch._send(TASK, synced.repo)

    names = names_of(calls)
    assert ok is True
    assert "push" in names, calls
    assert names[:names.index("push")].count("remote") == 1, calls
    assert origin_head(synced.sb, synced.ref) == head


def test_send_with_other_remote_name_does_not_push(no_remote, tmp_path):
    """AC-2: remote есть, но не `origin` — нет push, `False`, журнал тих.

    Ловит мутацию: `_send` пропускает `_origin_configured` и полагается на
    `has_no_remote` (remote не пуст) — `git push origin` уходит, падает и
    пишет «push артефактной ветки FAILED».
    """
    bare = tmp_path / "upstream.git"
    init_bare_origin(bare, no_remote.sb.git)
    no_remote.sb.git("remote", "add", "upstream", str(bare))
    before = len(journal_rows())

    with git_spy() as calls:
        ok = artifact_branch._send(TASK, no_remote.repo)

    assert ok is False
    assert "push" not in names_of(calls), calls
    assert len(journal_rows()) == before


def test_push_without_remote_is_no_origin(no_remote):
    """AC-3: `push(task_id)` без remote — «нет origin» без `git push`.

    Ловит мутацию: признак проверенного origin по умолчанию истинен — `push`
    не проверяет `has_no_remote`, `git push` уходит, причина в журнале
    «сеть», а не «нет origin».
    """
    before = len(journal_rows())

    with git_spy() as calls:
        ok = artifact_branch.push(TASK)

    assert ok is False
    assert "push" not in names_of(calls), calls
    new = journal_rows()[before:]
    assert any(r["action"] == PUSH_FAILED and r["detail"].startswith(
        artifact_branch.PUSH_REASON_NO_ORIGIN) for r in new), [
        (r["action"], r["detail"]) for r in new]


def test_sync_refusal_synced_ref_not_pushed(synced):
    """AC-4: ссылка совпадает с origin — `None` без `git push`.

    Ловит мутацию: досылка стоит до сверки при любом непустом `local` — при
    совпадающих ссылках уходит лишний `git push`.
    """
    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    assert refusal is None
    assert "push" not in names_of(calls), calls


def test_sync_refusal_local_ahead_pushes_then_rechecks(synced):
    """AC-5: локальная впереди — push, затем повторный `ls-remote`, `None`.

    Ловит мутацию: после досылки нет повторной сверки — сравнивается ответ
    первой сверки, и функция отказывает «расходится с origin».
    """
    head = commit_unsent(synced, "PLAN.md")

    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    names = names_of(calls)
    assert refusal is None
    assert "push" in names, calls
    assert "ls-remote" in names[names.index("push") + 1:], calls
    assert origin_head(synced.sb, synced.ref) == head


def test_sync_refusal_unreachable_origin_without_push(synced):
    """AC-6: origin не ответил на первую сверку — прежний отказ, без push.

    Ловит мутацию: досылка остаётся до первой сверки — `git push` в
    недоступный origin уходит и пишет «push артефактной ветки FAILED».
    """
    break_origin(synced.sb)
    before = len(journal_rows())

    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    prefix = f"отказ: origin не ответил на сверку {synced.ref} — "
    assert refusal is not None and refusal.startswith(prefix), refusal
    assert refusal[len(prefix):].strip()
    assert "push" not in names_of(calls), calls
    assert not [r for r in journal_rows()[before:]
                if r["action"] == PUSH_FAILED]


def test_sync_refusal_absent_and_push_rejected(synced):
    """AC-7: ссылки нет в origin, досылка отвергнута — прежний «нет в origin».

    Ловит мутацию: после неудачной досылки ветка `not remote` потеряна —
    функция отдаёт «расходится с origin» либо `None`.
    """
    synced.sb.git("push", "-q", "origin", f":{synced.ref}")
    reject_ref_pushes(synced.sb)
    local = local_head(synced.sb, synced.ref)

    refusal = artifact_branch.origin_sync_refusal(TASK)

    assert refusal == (f"отказ: {synced.ref} нет в origin (локально {local}) "
                       f"— документы задачи не отправлены")


def test_sync_refusal_diverged_after_push(synced):
    """AC-8: после досылки ссылки расходятся — прежний отказ с обоими sha.

    Ловит мутацию: отказ берёт sha первой сверки вместо повторной или меняет
    местами sha — текст называет не те голову и origin.
    """
    sb = synced.sb
    tree = sb.git("rev-parse", f"{synced.head0}^{{tree}}").strip()
    foreign = sb.git("commit-tree", tree, "-p", synced.head0,
                     "-m", "чужой коммит").strip()
    sb.git("push", "-q", "origin", f"{foreign}:{synced.ref}")
    local = commit_unsent(synced, "PLAN.md")

    refusal = artifact_branch.origin_sync_refusal(TASK)

    assert refusal == (f"отказ: {synced.ref} расходится с origin — локально "
                       f"{local}, в origin {foreign}")


def test_sync_refusal_absent_pushed_then_rechecked(synced):
    """AC-9: ссылки нет в origin, досылка удалась — push, `ls-remote`, `None`.

    Ловит мутацию: досылка только при обоих непустых и различных sha — при
    отсутствии ссылки в origin push не уходит, отказ «нет в origin».
    """
    synced.sb.git("push", "-q", "origin", f":{synced.ref}")

    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    names = names_of(calls)
    assert refusal is None
    assert "push" in names, calls
    assert "ls-remote" in names[names.index("push") + 1:], calls
    assert origin_head(synced.sb, synced.ref) == synced.head0


def test_sync_refusal_no_local_ref_without_push(synced):
    """AC-10: локальной ссылки нет, в origin есть — без push, прежний отказ.

    Ловит мутацию: отправка при любом расхождении без проверки непустого
    `local` (`if local != remote: _send(...)`) — уходит `git push`.
    """
    remote = origin_head(synced.sb, synced.ref)
    synced.sb.git("update-ref", "-d", synced.ref)

    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    assert refusal == (f"отказ: {synced.ref} расходится с origin — локально "
                       f"(нет), в origin {remote}")
    assert "push" not in names_of(calls), calls
