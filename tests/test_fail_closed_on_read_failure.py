"""Сбой чтения записи проекта или БД отказывает, а не пропускает проверку
(SPEC 01M6EZXVFGXC6WBDA9QJESAZRW): гейт мержа, черновой MR, единая точка
отправки; правило признака (а) `mr-sync` (требование 9)."""
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import (config, forge, fsm_merge_gate, github_adapter,
                          gitcmd, idgen, keychain, repo_context, store,
                          targets)

EXTERNAL = "qfailclosed"


def _task(target: str, state: str = "merge_gate",
          branch: str | None = None) -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, "Задача", state,
                      branch or f"task/{task_id.lower()}-x", target,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def _raise(exc):
    def fail(*args, **kwargs):
        raise exc
    return fail


def _actions(task_id: str) -> list:
    return [(r["action"], r["detail"] or "")
            for r in store.task_steps(store.db(), task_id)]


# --------------------------------------------------- people_entry (треб. 1)


def test_people_entry_raises_on_unread_entry(monkeypatch):
    """`people_entry` проекта вне артели при непрочитанной записи бросает `TargetsError`.

    Ловит мутацию: `people_entry` ловит `TargetsError` и отдаёт `None` —
    «запись не прочитана» читается как «гейт не target-human».
    """
    monkeypatch.setattr(github_adapter, "_people_entry_record",
                        _raise(targets.TargetsError("сбой")))
    with pytest.raises(targets.TargetsError):
        github_adapter.people_entry(EXTERNAL)


def test_people_entry_artel_does_not_read_entry(monkeypatch):
    """`people_entry` артели запись не читает: `None` и при сломанном читателе.

    Ловит мутацию: проверка артели убрана — читатель зван, `TargetsError`
    летит из `people_entry(config.DEFAULT_TARGET)`.
    """
    reader = mock.Mock(side_effect=targets.TargetsError("сбой"))
    monkeypatch.setattr(github_adapter, "_people_entry_record", reader)
    assert github_adapter.people_entry(config.DEFAULT_TARGET) is None
    reader.assert_not_called()


def test_ensure_forge_draft_mr_unread_entry_returns_reason(monkeypatch):
    """`ensure_forge_draft_mr` при непрочитанной записи возвращает причину «запись проекта не прочитана», MR не открывает.

    Ловит мутацию: ловля `TargetsError` в `ensure_forge_draft_mr` убрана —
    исключение летит; либо сбой обращён в `None` — переход идёт без MR.
    """
    monkeypatch.setattr(github_adapter, "_people_entry_record",
                        _raise(targets.TargetsError("сбой чтения")))
    open_mr = mock.Mock()
    monkeypatch.setattr(github_adapter, "open_forge_mr", open_mr)
    reason = github_adapter.ensure_forge_draft_mr(
        mock.Mock(), "T1", {"is_canary": 0, "target": EXTERNAL})
    assert reason == f"{github_adapter.ENTRY_UNREAD_DETAIL}: сбой чтения"
    open_mr.assert_not_called()


@pytest.mark.parametrize("gate", ["target-human", "operator"])
def test_merge_gate_unread_entry_refuses_external(real_git, monkeypatch, gate):
    """Гейт мержа задачи внешнего проекта при сбое читателя записи `people_entry` — `("stopped",)` и одна запись `PEOPLE_REFUSED_ACTION`, без слияния и отправки.

    Ловит мутацию: место вызова `people_entry` в `_cmd_approve_merge_gate`
    не ловит `TargetsError` (`except` иного класса) — исключение летит из
    гейта; либо сбой ведёт путём слияния в `base` — записи отказа нет.
    """
    from tests import test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery as delivery
    stand = delivery.Stand(real_git)
    stand.record(gate=gate, forge_name="github" if gate == "operator"
                 else "gitlab")
    task_id = stand.new_task(state="merge_gate", published=True)
    monkeypatch.setattr(github_adapter, "_people_entry_record",
                        _raise(targets.TargetsError("сбой чтения")))
    stand.reset_spies()
    before = len(stand.rows(task_id))
    row = dict(store.get_task(stand.conn, task_id))
    out = fsm_merge_gate._cmd_approve_merge_gate(
        stand.conn, task_id, "merge_gate", store.get_task(stand.conn, task_id))
    new = [(r["action"], r["detail"] or "")
           for r in stand.rows(task_id)[before:]]
    assert out == ("stopped",), new
    assert len(new) == 1, new
    assert new[0][0] == fsm_merge_gate.PEOPLE_REFUSED_ACTION, new
    assert new[0][1].startswith(
        f"{github_adapter.ENTRY_UNREAD_DETAIL}: сбой чтения"), new
    assert dict(store.get_task(stand.conn, task_id)) == row
    assert stand.pushes == []
    assert [c for c in stand.git_calls if delivery.git_sub(c) == "merge"] == []


# ------------------------------------------- гейт мержа (треб. 3, 8)


def test_awaiting_limit_unread_entry_refuses(initialized_tmp_root, monkeypatch):
    """`_awaiting_limit_refuses` при `TargetsError` — отказ «предел awaiting_human не проверен», а не пропуск предела.

    Ловит мутацию: `except TargetsError: return False` оставлен — ответ
    `False`, записи отказа нет, MR открылся бы мимо `max_awaiting`.
    """
    task_id = _task(EXTERNAL)
    monkeypatch.setattr(fsm_merge_gate.targets, "target",
                        _raise(targets.TargetsError("сбой")))
    ctx = SimpleNamespace(target=EXTERNAL)
    assert fsm_merge_gate._awaiting_limit_refuses(store.db(), task_id, ctx)
    refused = [d for a, d in _actions(task_id)
               if a == fsm_merge_gate.PEOPLE_REFUSED_ACTION]
    assert len(refused) == 1, _actions(task_id)
    assert refused[0].startswith(
        f"{fsm_merge_gate.AWAITING_UNCHECKED_DETAIL}: "
        f"{github_adapter.ENTRY_UNREAD_DETAIL}: сбой")


@pytest.mark.parametrize("state", ["locked", "", None])
def test_mr_incident_unknown_state_refuses(initialized_tmp_root, monkeypatch,
                                           state):
    """`_mr_incident_stops`: статус MR вне `opened`/`merged`/`closed` — отказ гейта, задача на гейте.

    Ловит мутацию: неизвестный статус проходит (`if not detail: return
    False`) — ответ `False`, записи отказа нет.
    """
    task_id = _task(EXTERNAL)
    store.set_mr_link(store.db(), task_id, 7, "https://localhost/mr/7")
    fields = {} if state is None else {"state": state}
    monkeypatch.setattr(fsm_merge_gate.forge, "mr_status",
                        lambda target, iid: forge.MergeRequest(iid=iid, **fields))
    ctx = SimpleNamespace(target=EXTERNAL, path=None)
    assert fsm_merge_gate._mr_incident_stops(store.db(), task_id, "merge_gate",
                                             ctx)
    assert store.task_state(store.db(), task_id) == "merge_gate"
    refused = [d for a, d in _actions(task_id)
               if a == fsm_merge_gate.MR_REFUSED_ACTION]
    assert refused and refused[0].startswith(
        fsm_merge_gate.MR_STATE_UNKNOWN_DETAIL), _actions(task_id)


# --------------------------------------- точка отправки (треб. 4, 7)


def test_in_flight_refusal_external_unread_entry(initialized_tmp_root,
                                                 monkeypatch):
    """`in_flight_refusal` задачи внешнего проекта при `TargetsError` — причина, не `None`.

    Ловит мутацию: `except TargetsError: return None` для любого проекта —
    `amend-tests` коммитит при неизвестном пределе.
    """
    task_id = _task(EXTERNAL, "in_dev")
    monkeypatch.setattr(targets, "load", _raise(targets.TargetsError("сбой")))
    why = gitcmd.in_flight_refusal(task_id)
    assert why and why.startswith(gitcmd.IN_FLIGHT_UNCHECKED), why
    assert gitcmd.IN_FLIGHT_LIMIT_REASON not in why


def test_in_flight_refusal_external_db_error(initialized_tmp_root, monkeypatch):
    """`in_flight_refusal` задачи внешнего проекта при `sqlite3.Error` в счёте — причина, не `None`.

    Ловит мутацию: `except sqlite3.Error: return None` — ответ `None`.
    """
    task_id = _task(EXTERNAL, "in_dev")
    monkeypatch.setattr(targets, "load", lambda: {EXTERNAL: {}})
    monkeypatch.setattr(gitcmd, "_in_flight_refusal",
                        _raise(sqlite3.OperationalError("сбой")))
    why = gitcmd.in_flight_refusal(task_id)
    assert why and gitcmd.DB_UNREAD in why, why


def test_in_flight_refusal_artel_unread_entry_none(initialized_tmp_root,
                                                   monkeypatch):
    """`in_flight_refusal` задачи артели при `TargetsError` — `None`, как прежде.

    Ловит мутацию: отказ при сбое распространён на артель — причина вместо
    `None`, `amend-tests` артели при сломанном `targets.yaml` отказывает.
    """
    task_id = _task(config.DEFAULT_TARGET, "in_dev")
    monkeypatch.setattr(targets, "load", _raise(targets.TargetsError("сбой")))
    assert gitcmd.in_flight_refusal(task_id) is None


def test_in_flight_refusal_code_is_distinct():
    """Код отказа пределом — своя константа, отличная от кода прочих отказов точки отправки.

    Ловит мутацию: `IN_FLIGHT_REFUSAL` равен `PUSH_REFUSAL` (1) или нулю —
    отказ пределом не отличить от прочих отказов по коду.
    """
    assert gitcmd.IN_FLIGHT_REFUSAL not in (0, gitcmd.PUSH_REFUSAL)
    plan = gitcmd._PushPlan([], config.ROOT)
    assert plan.code == gitcmd.PUSH_REFUSAL
    assert gitcmd._refused(["git"], "отказ").returncode == gitcmd.PUSH_REFUSAL


# Стенд отправки: запись проекта в локальном слое, настоящий клон по адресу
# `repo_context.clone_path`; `git push` шпион записывает и не исполняет.

REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen


@pytest.fixture
def pushes(initialized_tmp_root, monkeypatch) -> list:
    sent: list = []

    def is_push(argv) -> bool:
        return isinstance(argv, list) and argv[:1] == ["git"] and "push" in argv

    def run(argv, *args, **kwargs):
        if is_push(argv):
            sent.append(list(argv))
            empty = "" if kwargs.get("text") else b""
            return subprocess.CompletedProcess(argv, 0, empty, empty)
        return REAL_RUN(argv, *args, **kwargs)

    def popen(argv, *args, **kwargs):
        if is_push(argv):
            sent.append(list(argv))
            raise OSError("отправка процессом Popen не исполняется")
        return REAL_POPEN(argv, *args, **kwargs)

    monkeypatch.delenv(config.ARTEL_TASK_ENV, raising=False)
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "")
    monkeypatch.setattr(keychain, "token", lambda *a, **k: "tok")
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    return sent


def _repo(path: Path, origin_url: str) -> Path:
    def git(*args):
        REAL_RUN(["git", *args], cwd=path, check=True, capture_output=True)
    path.mkdir(parents=True)
    git("init", "-q", "-b", config.MAIN_BRANCH)
    git("config", "user.email", "artel@example.invalid")
    git("config", "user.name", "artel tests")
    git("commit", "-q", "--allow-empty", "-m", "init")
    git("remote", "add", "origin", origin_url)
    git("branch", "feature/x")
    return path


def _project_clone(gate: str = "operator", policy: str = "") -> Path:
    """Запись проекта `EXTERNAL` (`forge: github`, гейт `gate`) и его клон."""
    url = f"https://localhost/team/{EXTERNAL}"
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(
        f"targets:\n  {EXTERNAL}:\n"
        f"    description:\n      base: {config.MAIN_BRANCH}\n"
        f"      test_profile:\n        command: [python3, -m, pytest]\n"
        f"        long_lived_dir: tests\n"
        f"        long_lived_name: test_<id>_<name>.py\n"
        f"    policy:\n      no_paths: []\n      project_skills: []\n"
        f"      merge_gate: {gate}\n"
        f"      weakening_scope: [tests/**/*.py]\n"
        f"      mutation_claim_scope: [tests/test_*.py]\n{policy}"
        f"    machine:\n      forge: github\n"
        f"      url: {url}\n"
        f"      token_slot: {EXTERNAL}-token\n", encoding="utf-8")
    return _repo(repo_context.clone_path(EXTERNAL), url)


def _fail_first(monkeypatch, name: str, exc: Exception) -> list:
    """Первый вызов `store.<name>` бросает `exc`, следующие — настоящие."""
    real = getattr(store, name)
    calls: list = []

    def wrapper(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise exc
        return real(*args, **kwargs)

    monkeypatch.setattr(store, name, wrapper)
    return calls


def test_in_flight_limit_refusal_carries_code_from_git_and_in_repo(pushes):
    """Отказ пределом `max_in_flight` из `gitcmd.in_repo` и `gitcmd.git` несёт код `IN_FLIGHT_REFUSAL`, `git push` не вызван.

    Ловит мутацию: убрано `plan.code = IN_FLIGHT_REFUSAL` в `_push_plan` —
    отказ пределом снова с кодом `PUSH_REFUSAL` (1), `github_adapter` не
    отличит его от прочих отказов.
    """
    clone = _project_clone(policy="      max_in_flight: 1\n")
    _task(EXTERNAL, "in_dev", "feature/x")
    other = _task(EXTERNAL, "in_dev")
    store.journal(store.db(), other, "orchestrator", gitcmd.PUSH_SENT_ACTION,
                  f"{'a' * 40} {store.get_task(store.db(), other)['branch']}")
    for res in (gitcmd.in_repo(clone, "push", "origin", "feature/x"),
                gitcmd.git("-C", str(clone), "push", "origin", "feature/x")):
        assert gitcmd.IN_FLIGHT_LIMIT_REASON in (res.stderr or ""), res
        assert res.returncode == gitcmd.IN_FLIGHT_REFUSAL, res
    assert pushes == []


def test_push_plan_in_flight_db_error_external_refused(pushes, monkeypatch):
    """`sqlite3.Error` в счёте `max_in_flight` при отправке проекта вне артели — отказ с причиной, `git push` не вызван.

    Ловит мутацию: в `_push_plan` условие `project != config.DEFAULT_TARGET`
    у `except sqlite3.Error` заменено на `False` — `waiting = None`, предел
    пропущен, шпион видит `git push`.
    """
    clone = _project_clone(policy="      max_in_flight: 1\n")
    _task(EXTERNAL, "in_dev", "feature/x")
    calls = []

    def fail(*args, **kwargs):
        calls.append(args)
        raise sqlite3.OperationalError("сбой")

    monkeypatch.setattr(store, "last_task_step_of", fail)
    res = gitcmd.in_repo(clone, "push", "origin", "feature/x")
    assert calls, "стенд: счёт max_in_flight не читал журнал"
    assert res.returncode != 0, res
    assert gitcmd.IN_FLIGHT_UNCHECKED in (res.stderr or ""), res
    assert pushes == []


def test_in_repo_db_error_refuses_external_not_artel(pushes, monkeypatch):
    """`sqlite3.Error` в чтении `in_repo` (ветки задач проекта): отправка проекта вне артели — отказ, `git push` не вызван; отправка артели идёт.

    Ловит мутацию: в `_awaiting_human_refusal` условие `project ==
    config.DEFAULT_TARGET` заменено на `True` — сбой БД пропускает и
    внешний проект, шпион видит его `git push`.
    """
    clone = _project_clone()
    _task(EXTERNAL, "in_dev", "feature/x")
    calls = _fail_first(monkeypatch, "project_tasks",
                        sqlite3.OperationalError("сбой"))
    res = gitcmd.in_repo(clone, "push", "origin", "feature/x")
    assert calls, "стенд: in_repo не читал БД"
    assert res.returncode != 0 and gitcmd.DB_UNREAD in (res.stderr or ""), res
    assert pushes == []
    artel = _repo(Path(config.ROOT) / "artel-repo",
                  "https://localhost/team/artel")
    _fail_first(monkeypatch, "project_tasks", sqlite3.OperationalError("сбой"))
    res = gitcmd.in_repo(artel, "push", "origin", "feature/x")
    assert res.returncode == 0, res
    assert len(pushes) == 1


def test_url_destination_unread_entries_is_not_artel(monkeypatch):
    """Адрес-URL, не адрес `origin` пульта, при непрочитанных записях — не артель; адрес `origin` пульта — артель.

    Ловит мутацию: при `entries is None` адрес не сверяется — проект
    назначения артель, отправка идёт мимо гейта мержа.
    """
    origin = "https://localhost/team/artel.git"
    monkeypatch.setattr(gitcmd, "_raw_config", lambda *a: origin)
    foreign = "https://localhost/team/other"
    got = gitcmd._destination_project([foreign], config.ROOT, None, None)
    assert got != config.DEFAULT_TARGET
    assert gitcmd._destination_project(["https://localhost/team/artel/"],
                                       config.ROOT, None, None) \
        == config.DEFAULT_TARGET
    assert gitcmd._destination_project(["origin"], config.ROOT, None, None) \
        == config.DEFAULT_TARGET


@pytest.mark.parametrize("code_is_limit", [True, False])
def test_github_draft_mr_reads_limit_by_code(monkeypatch, code_is_limit):
    """Черновой MR GitHub узнаёт отказ пределом по коду: код предела — без алерта; иной код со строкой предела — инцидент.

    Ловит мутацию: `github_adapter` по-прежнему ищет `IN_FLIGHT_LIMIT_REASON`
    в stderr — иной сбой с этой строкой молча принят за очередь.
    """
    code = gitcmd.IN_FLIGHT_REFUSAL if code_is_limit else gitcmd.PUSH_REFUSAL
    push = subprocess.CompletedProcess(
        [], code, "", f"{gitcmd.IN_FLIGHT_LIMIT_REASON}: 2 из 2")
    alert = mock.Mock()
    gh = mock.Mock()
    monkeypatch.setattr(github_adapter, "_is_github_target", lambda name: True)
    monkeypatch.setattr(targets, "target",
                        lambda name: {"forge": "github", "base": "main",
                                      "merge_gate": "operator"})
    monkeypatch.setattr(github_adapter, "_commits_over_base", lambda *a, **k: 1)
    monkeypatch.setattr(github_adapter.repo_context, "resolve", lambda name: None)
    monkeypatch.setattr(github_adapter.artifact_branch, "send_pending",
                        lambda *a, **k: None)
    monkeypatch.setattr(github_adapter.gitcmd, "in_repo", lambda *a, **k: push)
    monkeypatch.setattr(github_adapter.ci, "gh", gh)
    monkeypatch.setattr(github_adapter, "_incident", alert)
    github_adapter.ensure_draft_mr(mock.Mock(), "T1", {
        "target": EXTERNAL, "branch": "task/x", "title": "T",
        "draft_mr_created": 0, "is_canary": 0})
    gh.assert_not_called()
    assert alert.called is not code_is_limit


# ------------------------------------------ признак (а) mr-sync (треб. 9)


def test_mr_sync_opened_mr_sha_in_base_is_not_sign_a(real_git):
    """Открытый MR, чей `sha` уже предок `origin/<base>`: `mr-sync <id> --confirm` без `--by-content` отказывает.

    Ловит мутацию: `state == "merged"` → `True` в `orchestrator/mr_sync.py`
    — `sha` открытого MR засчитан признаком (а), `--confirm` закрывает
    задачу `done`.
    """
    from orchestrator import mr_sync
    from tests import test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync as sync
    stand = sync.Stand(real_git)
    task_id = stand.to_awaiting()
    fork = stand.fork_at[task_id]
    stand.foreign_main()
    stand.reply(task_id, state="opened", sha=fork)
    out = stand.mr_sync(task_id, "--confirm")
    sync.confirm_refused(stand, task_id, out)
    assert stand.state(task_id) == sync.STATE, stand.context(task_id, out)
    assert [r for r in stand.rows(task_id)[stand.marks.get(task_id, 0):]
            if r["action"] == mr_sync.CONFIRM_REFUSED_ACTION]
    assert store.get_task(stand.conn, task_id)["closed_as"] in (None, "")
