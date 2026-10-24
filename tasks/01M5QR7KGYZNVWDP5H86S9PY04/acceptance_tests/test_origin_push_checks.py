"""Одна проверка remote при отправке документов и досылка в сверке с origin только при расхождении (AC-1 — AC-10).

Группа: разовый

Красен до реализации: `_send` проверяет remote дважды (`git remote get-url origin` и `git remote` из `has_no_remote`), а `origin_sync_refusal` досылает ссылку `git push` до сверки всегда, даже при совпадении с origin и при недоступном origin — test_ac1, test_ac4, test_ac6 красные; test_ac2, test_ac3, test_ac5, test_ac7 — test_ac10 держат прежние исходы и тексты (требования 1-2 SPEC) и зелёные.

Почему разовый, а не долгоживущий: критерии AC-1/AC-2 называют закрытую
`artifact_branch._send`, а статика долгоживущего файла не пускает ни
закрытых имён, ни импорта `orchestrator.artifact_branch`/`gitcmd`
(`scripts/guard.py::_GIT_MODULES`, признак «git-модуль»). Долгоживущий
файл требования 3 SPEC — работа разработчика.

Песочница — настоящий git (`origin_real_git`, `tests/fixtures.py`):
пульт — `root`, bare-origin — `add_origin()`; задача артели в `in_dev`
с первым коммитом ссылки `refs/artifacts/<id>` через `commit_files`.
Шпион стоит на `subprocess.run`, которым `gitcmd` запускает каждый git
(`gitcmd.git`/`in_repo`/`carpentry`), — видит и `has_no_remote`; подкоманда
берётся сквозь пары `-C <клон>` (`strip_dash_c`).
"""
import contextlib
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import artifact_branch, config, store
from tests.sandbox import init_bare_origin, strip_dash_c

TASK = "01UNITORIGINPUSHCHK1"
PUSH_FAILED = "push артефактной ветки FAILED"


@contextlib.contextmanager
def git_spy():
    """Список подкоманд git (кортежи аргументов без `-C <путь>`) всех
    процессов, запущенных внутри блока."""
    calls = []
    real_run = subprocess.run

    def spy(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            calls.append(strip_dash_c(cmd[1:]))
        return real_run(cmd, *args, **kwargs)

    with mock.patch.object(subprocess, "run", side_effect=spy):
        yield calls


def subcommands(calls) -> list:
    return [c[0] if c else "" for c in calls]


def journal_rows():
    return list(store.task_steps(store.db(), TASK))


def _make_task():
    store.insert_task(store.db(), TASK, "Задача", "in_dev",
                      f"task/{TASK.lower()}-x", config.DEFAULT_TARGET, 25.0)


def _commit(name: str, text: str) -> str:
    return artifact_branch.commit_files(
        TASK, {f"tasks/{TASK}/{name}": text}, f"{TASK}: {name}")


def _git_out(sb, *args) -> str:
    return sb.git(*args).strip()


def _origin_head(sb, ref: str) -> str:
    out = sb.git("ls-remote", sb.bare, ref).split()
    return out[0] if out else ""


def _local_head(sb, ref: str) -> str:
    return sb.git("for-each-ref", "--format=%(objectname)", ref).strip()


@pytest.fixture
def docs_ref(origin_real_git):
    """Пульт с bare-origin, задача артели и первый коммит её ссылки
    документов, уже отправленный в origin."""
    sb = origin_real_git
    sb.add_origin()
    sb.git("push", "-q", "origin", f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    _make_task()
    ref = artifact_branch.branch_name(TASK)
    head0 = _commit("SPEC.md", "спека\n")
    return SimpleNamespace(sb=sb, ref=ref, head0=head0,
                           repo=artifact_branch.task_repo(TASK))


@pytest.fixture
def docs_ref_without_origin(origin_real_git):
    """Пульт без единого remote, задача артели и первый коммит её ссылки
    документов (отправлять некуда)."""
    sb = origin_real_git
    _make_task()
    ref = artifact_branch.branch_name(TASK)
    head0 = _commit("SPEC.md", "спека\n")
    return SimpleNamespace(sb=sb, ref=ref, head0=head0,
                           repo=artifact_branch.task_repo(TASK))


def break_origin(sb) -> None:
    sb.git("remote", "set-url", "origin",
           str(sb.root / ".artel" / "нет-такого-origin.git"))


def restore_origin(sb) -> None:
    sb.git("remote", "set-url", "origin", sb.bare)


def commit_unsent(env, name: str) -> str:
    """Коммит ссылки, не дошедший до origin (origin недоступен на время
    записи), — локальная ссылка впереди origin."""
    break_origin(env.sb)
    try:
        return _commit(name, f"{name}\n")
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


# --- AC-1 ---------------------------------------------------------------

def test_ac1_send_checks_remote_once_before_push(docs_ref):
    """Локальная ссылка впереди origin, `_send` досылает её.

    Перед первым `git push` в процессах git ровно один вызов `git remote …`;
    отправка проходит (`True`, origin равен локальной голове).

    Ловит мутацию: `_send` по-прежнему зовёт `_attempt_push` без признака
    проверенного origin — перед `git push` два вызова `git remote`
    (`get-url origin` и голый `remote` из `has_no_remote`).
    """
    assert docs_ref.head0, "предусловие: первый коммит ссылки"
    head = commit_unsent(docs_ref, "PLAN.md")
    assert head and _origin_head(docs_ref.sb, docs_ref.ref) == docs_ref.head0

    with git_spy() as calls:
        ok = artifact_branch._send(TASK, docs_ref.repo)

    names = subcommands(calls)
    assert ok is True
    assert "push" in names, f"git push не было: {calls}"
    before_push = names[:names.index("push")]
    assert before_push.count("remote") == 1, (
        f"вызовы git до push: {calls[:names.index('push')]}")
    assert _origin_head(docs_ref.sb, docs_ref.ref) == head


# --- AC-2 ---------------------------------------------------------------

def test_ac2_send_without_origin_name_does_not_push(docs_ref_without_origin,
                                                    tmp_path):
    """У репозитория есть remote `upstream`, но не `origin`.

    `_send` не запускает `git push`, возвращает `False` и не пишет в журнал
    задачи ни одной новой записи.

    Ловит мутацию: `_send` пропускает `_origin_configured` и полагается на
    `has_no_remote` (remote не пуст) — `git push origin` уходит, падает, и
    в журнале появляется запись «push артефактной ветки FAILED».
    """
    env = docs_ref_without_origin
    assert env.head0, "предусловие: первый коммит ссылки"
    bare = tmp_path / "upstream.git"
    init_bare_origin(bare, env.sb.git)
    env.sb.git("remote", "add", "upstream", str(bare))
    before = len(journal_rows())

    with git_spy() as calls:
        ok = artifact_branch._send(TASK, env.repo)

    assert ok is False
    assert "push" not in subcommands(calls), f"вызовы git: {calls}"
    assert len(journal_rows()) == before, [
        (r["action"], r["detail"]) for r in journal_rows()[before:]]


# --- AC-3 ---------------------------------------------------------------

def test_ac3_push_without_remote_is_no_origin(docs_ref_without_origin):
    """У репозитория нет ни одного remote; зовут `push(task_id)`.

    Возврат `False`, в журнале — отказ с причиной `PUSH_REASON_NO_ORIGIN`,
    `git push` не запускался.

    Ловит мутацию: признак «origin уже проверен» по умолчанию истинен, и
    `push` перестаёт проверять `has_no_remote` — `git push` уходит в пустоту,
    причина отказа в журнале «сеть», а не «нет origin».
    """
    env = docs_ref_without_origin
    assert env.head0, "предусловие: первый коммит ссылки"
    before = len(journal_rows())

    with git_spy() as calls:
        ok = artifact_branch.push(TASK)

    assert ok is False
    assert "push" not in subcommands(calls), f"вызовы git: {calls}"
    new = journal_rows()[before:]
    assert any(r["action"] == PUSH_FAILED
               and r["detail"].startswith(artifact_branch.PUSH_REASON_NO_ORIGIN)
               for r in new), [(r["action"], r["detail"]) for r in new]


# --- AC-4 ---------------------------------------------------------------

def test_ac4_synced_ref_is_not_pushed(docs_ref):
    """Локальная `refs/artifacts/<id>` совпадает с origin.

    `origin_sync_refusal` возвращает `None` и не запускает `git push`.

    Ловит мутацию: досылка `_send` по-прежнему стоит до сверки при любом
    непустом `local` — при совпадающих ссылках уходит лишний `git push`.
    """
    assert docs_ref.head0
    assert _origin_head(docs_ref.sb, docs_ref.ref) == docs_ref.head0

    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    assert refusal is None
    assert "push" not in subcommands(calls), f"вызовы git: {calls}"


# --- AC-5 ---------------------------------------------------------------

def test_ac5_local_ahead_pushes_then_rechecks(docs_ref):
    """Локальная ссылка впереди origin.

    `origin_sync_refusal` запускает `git push`, после него — повторный
    `git ls-remote`, и возвращает `None`; origin догнал локальную голову.

    Ловит мутацию: после досылки нет повторной сверки, сравнивается
    прежний ответ `ls-remote` — функция отказывает «расходится с origin»
    (или после `git push` нет ни одного `ls-remote`).
    """
    head = commit_unsent(docs_ref, "PLAN.md")
    assert head and _origin_head(docs_ref.sb, docs_ref.ref) == docs_ref.head0

    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    names = subcommands(calls)
    assert refusal is None
    assert "push" in names, f"вызовы git: {calls}"
    assert "ls-remote" in names[names.index("push") + 1:], (
        f"нет сверки после push: {calls}")
    assert _origin_head(docs_ref.sb, docs_ref.ref) == head


# --- AC-6 ---------------------------------------------------------------

def test_ac6_unreachable_origin_refused_without_push(docs_ref):
    """origin недоступен (адрес ведёт в несуществующий каталог).

    `origin_sync_refusal` возвращает «отказ: origin не ответил на сверку
    <ветка> — <причина>» и не запускает `git push`.

    Ловит мутацию: досылка остаётся до первой сверки — `git push` в
    недоступный origin уходит (и пишет «push артефактной ветки FAILED»).
    """
    assert docs_ref.head0
    break_origin(docs_ref.sb)

    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    prefix = f"отказ: origin не ответил на сверку {docs_ref.ref} — "
    assert refusal is not None and refusal.startswith(prefix), refusal
    assert refusal[len(prefix):].strip(), f"причина пуста: {refusal!r}"
    assert "push" not in subcommands(calls), f"вызовы git: {calls}"


# --- AC-7 ---------------------------------------------------------------

def test_ac7_absent_in_origin_and_push_rejected(docs_ref):
    """Ссылки нет в origin, а origin отвергает её запись.

    `origin_sync_refusal` возвращает прежний отказ «отказ: <ветка> нет в
    origin (локально <sha>) — документы задачи не отправлены».

    Ловит мутацию: при отсутствии ссылки в origin функция после неудачной
    досылки отдаёт текст «расходится с origin» (ветка `not remote`
    потеряна) либо `None`.
    """
    env = docs_ref
    env.sb.git("push", "-q", "origin", f":{env.ref}")
    reject_ref_pushes(env.sb)
    local = _local_head(env.sb, env.ref)
    assert local == env.head0

    refusal = artifact_branch.origin_sync_refusal(TASK)

    assert refusal == (f"отказ: {env.ref} нет в origin (локально {local}) "
                       f"— документы задачи не отправлены")


# --- AC-8 ---------------------------------------------------------------

def test_ac8_diverged_after_push_refused(docs_ref):
    """В origin и локально — разные коммиты поверх общей головы.

    Досылка отвергнута (не fast-forward); `origin_sync_refusal` возвращает
    прежний отказ «отказ: <ветка> расходится с origin — локально <sha>, в
    origin <sha>» с обоими sha.

    Ловит мутацию: сравнение после досылки берёт sha первой сверки или
    меняет местами sha в тексте — отказ называет не те голову и origin.
    """
    env = docs_ref
    tree = _git_out(env.sb, "rev-parse", f"{env.head0}^{{tree}}")
    foreign = _git_out(env.sb, "commit-tree", tree, "-p", env.head0,
                       "-m", "чужой коммит")
    env.sb.git("push", "-q", "origin", f"{foreign}:{env.ref}")
    local = commit_unsent(env, "PLAN.md")
    assert local and local != foreign
    assert _origin_head(env.sb, env.ref) == foreign

    refusal = artifact_branch.origin_sync_refusal(TASK)

    assert refusal == (f"отказ: {env.ref} расходится с origin — локально "
                       f"{local}, в origin {foreign}")


# --- AC-9 ---------------------------------------------------------------

def test_ac9_absent_in_origin_pushed_then_rechecked(docs_ref):
    """Ссылки нет в origin, origin принимает запись.

    `origin_sync_refusal` запускает `git push`, после него — повторный
    `git ls-remote`, и возвращает `None`; ссылка появилась в origin.

    Ловит мутацию: при отсутствии ссылки в origin досылки нет (досылка
    только при «оба sha непусты и различны») — функция отказывает «нет в
    origin».
    """
    env = docs_ref
    env.sb.git("push", "-q", "origin", f":{env.ref}")
    assert _origin_head(env.sb, env.ref) == ""

    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    names = subcommands(calls)
    assert refusal is None
    assert "push" in names, f"вызовы git: {calls}"
    assert "ls-remote" in names[names.index("push") + 1:], (
        f"нет сверки после push: {calls}")
    assert _origin_head(env.sb, env.ref) == env.head0


# --- AC-10 --------------------------------------------------------------

def test_ac10_no_local_ref_refused_without_push(docs_ref):
    """Локальной `refs/artifacts/<id>` нет, в origin она есть.

    `origin_sync_refusal` не запускает `git push` и возвращает прежний отказ
    «отказ: <ветка> расходится с origin — локально (нет), в origin <sha>».

    Ловит мутацию: отправка при любом расхождении без проверки непустого
    `local` (`if local != remote: _send(...)`) — уходит `git push`.
    """
    env = docs_ref
    remote = _origin_head(env.sb, env.ref)
    assert remote == env.head0
    env.sb.git("update-ref", "-d", env.ref)
    assert _local_head(env.sb, env.ref) == ""

    with git_spy() as calls:
        refusal = artifact_branch.origin_sync_refusal(TASK)

    assert refusal == (f"отказ: {env.ref} расходится с origin — локально "
                       f"(нет), в origin {remote}")
    assert "push" not in subcommands(calls), f"вызовы git: {calls}"
