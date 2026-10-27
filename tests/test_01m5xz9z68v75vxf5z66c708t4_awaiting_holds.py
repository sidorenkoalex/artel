"""Задача в `awaiting_human` для механизмов пульта: `auto` останавливается без алерта, зоны держатся по `awaiting_holds_zones`, зависимый по `merge_after` ждёт `done`, `doctor` не проверяет свежесть её ветки.

Группа: долгоживущий
Красен до реализации: `awaiting_human` нет в `config.AUTO_STOP` и в перечне остановок без алерта — `auto` открывает алерт `attention`; нет в `zone_lock.BLOCKING_STATES` и поле `awaiting_holds_zones` записи не читается — зона свободна при `true`; `doctor` сверяет свежесть ветки задачи в `awaiting_human`. Тест `merge_after` держит существующее поведение и зелёный с рождения.

Песочницы: `light_transition` для цикла `auto` (связка «цикл `auto` —
`runner.cmd_run` — журнал — алерты»; агент, рабочий каталог и
предполётная проверка подменены отказом — до них цикл дойти не должен),
`initialized_tmp_root` для зон, `merge_after` и `doctor` (связка «модуль —
строки задач в БД — журнал»). Состояние `awaiting_human` ставится прямой
установкой в БД. Имена проектов, зоны и id — из `random`, зерно
печатается и входит в текст провала.
"""
import io
import os
import random
import signal
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import pytest

from orchestrator import (alerts, auto, config, doctor, idgen, merge_after, runner,
                          store, targets, workspace, zone_lock)

STATE = "awaiting_human"
LETTERS = "abcdefghijkmnopqrstuvwxyz"


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


def word(rng: random.Random, n: int = 6) -> str:
    return "".join(rng.choice(LETTERS) for _ in range(n))


def insert(state: str, target: str = config.DEFAULT_TARGET, *,
           zones: str | None = None) -> str:
    task_id = idgen.new_task_id()
    conn = store.db()
    store.insert_task(conn, task_id, f"Задача {task_id[-6:]}", "in_dev",
                      f"task/{task_id.lower()}-w", target,
                      config.DEFAULT_BUDGET_USD)
    if zones is not None:
        store.update_task(conn, task_id, zones=zones)
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()
    return task_id


# --- AC-10 -----------------------------------------------------------------

@pytest.fixture
def auto_pult(light_transition, monkeypatch):
    """Цикл `auto` без роли в окружении, с восстановлением обработчика
    SIGTERM, который `auto` ставит себе."""
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "")
    previous = signal.getsignal(signal.SIGTERM)
    yield light_transition
    signal.signal(signal.SIGTERM, previous)


def run_auto(task_id: str) -> tuple:
    """(вывод, записи журнала задачи за цикл, подмена агента)."""
    before = len(store.task_steps(store.db(), task_id))
    spawn = mock.Mock(side_effect=AssertionError("агент запущен"))
    ensure = mock.Mock(side_effect=AssertionError("рабочий каталог готовится"))
    preflight = mock.Mock(side_effect=AssertionError("дошёл до предполёта"))
    buf = io.StringIO()
    with mock.patch.object(runner, "spawn_agent", spawn), \
            mock.patch.object(workspace, "ensure", ensure), \
            mock.patch("orchestrator.doctor.preflight_checks", preflight), \
            redirect_stdout(buf), redirect_stderr(buf):
        try:
            auto.cmd_auto(task_id)
        except SystemExit as exc:
            buf.write(f"\n{exc}")
    return buf.getvalue(), store.task_steps(store.db(), task_id)[before:], spawn


def test_ac10_auto_stops_on_awaiting_human_without_alert(auto_pult, seed):
    """`auto` по задаче в `awaiting_human` останавливается записью «auto остановлен» без алерта `attention`.

    Сценарий: задача в `awaiting_human`; `auto.cmd_auto(id)`: агент не
    запущен, в журнале за цикл есть запись `zone_lock.AUTO_STOPPED_ACTION`
    с состоянием `awaiting_human` в начале детали, открытых алертов
    `attention` нет, задача осталась в `awaiting_human`. Контроль: задача
    в `escalated` той же песочницы — `auto` открывает алерт `attention`
    (детектор алерта жив).

    Ловит мутацию: `awaiting_human` добавлен в `config.AUTO_STOP`, но не в
    перечень остановок без алерта — алерт `attention` открыт; в
    `AUTO_STOP` состояния нет — цикл не узнаёт состояние без роли и
    останавливается неузнанным отказом с алертом.
    """
    task_id = insert(STATE)
    out, rows, spawn = run_auto(task_id)
    journal = "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}" for r in rows)
    note = f"зерно: {seed}; вывод:\n{out}\nжурнал:\n{journal}"
    spawn.assert_not_called()
    stops = [r for r in rows if r["action"] == zone_lock.AUTO_STOPPED_ACTION]
    assert stops, note
    assert (stops[-1]["detail"] or "").startswith(STATE), note
    assert alerts.open_alerts(store.db(), "attention") == [], note
    assert store.get_task(store.db(), task_id)["state"] == STATE, note
    escalated = insert("escalated")
    run_auto(escalated)
    assert alerts.open_alerts(store.db(), "attention") != [], (
        f"зерно: {seed}: контроль escalated не открыл алерт")


# --- AC-11 -----------------------------------------------------------------

def declare_project(name: str, holds: str | None) -> None:
    """Запись проекта `target-human` в локальном слое; `holds` —
    значение `policy.awaiting_holds_zones` (None — поля нет)."""
    extra = f"      awaiting_holds_zones: {holds}\n" if holds is not None else ""
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(
        f"targets:\n  {name}:\n"
        f"    description:\n      base: {config.MAIN_BRANCH}\n"
        f"      test_profile:\n        command: [python3, -m, pytest]\n"
        f"        long_lived_dir: tests\n"
        f"        long_lived_name: test_<id>_<name>.py\n"
        f"    policy:\n      no_paths: []\n      project_skills: []\n"
        f"      merge_gate: target-human\n"
        f"      weakening_scope: [tests/**/*.py]\n"
        f"      mutation_claim_scope: [tests/test_*.py]\n" + extra
        + f"    machine:\n      forge: github\n"
        f"      url: https://localhost/team/{name}\n"
        f"      token_slot: {name}-token\n", encoding="utf-8")


def zone_scenario(seed: int, holds: str, monkeypatch) -> tuple:
    """(задача-претендент в `in_dev`, задача в `awaiting_human`, общая
    зона, заметка) проекта со значением `awaiting_holds_zones: holds`."""
    monkeypatch.setattr(targets, "SUPPORTED_MERGE_GATES",
                        ("operator", "target-human"))
    rng = random.Random(seed)
    name = "z" + word(rng, 7)
    declare_project(name, holds)
    zone = f"{word(rng)}/{word(rng)}"
    holder = insert(STATE, name, zones=zone)
    conn = store.db()
    store.journal(conn, holder, "system", "state -> in_dev", "")
    store.journal(conn, holder, "developer", "agent run started", "")
    own = insert("in_dev", name, zones=zone)
    return own, holder, zone, f"зерно: {seed}; проект {name}; зона {zone}; holds {holds}"


def test_ac11_awaiting_human_holds_zones_when_true(initialized_tmp_root, seed, monkeypatch):
    """При `awaiting_holds_zones: true` зона задачи в `awaiting_human` занята — вторая задача получает отказ занятости.

    Сценарий: проект `target-human` с `awaiting_holds_zones: true`; задача
    в `awaiting_human` с зоной, уже державшая её (шаг роли был); вторая
    задача проекта в `in_dev` с пересекающейся зоной:
    `zone_lock.blocking_conflict` называет первую задачу и `awaiting_human`,
    `zone_lock.refusal` — непустой отказ с id первой задачи.

    Ловит мутацию: `awaiting_human` не добавлен в
    `zone_lock.BLOCKING_STATES` — зона свободна, конфликта нет; поле
    читается с обратным смыслом — при `true` зона отпущена.
    """
    own, holder, zone, note = zone_scenario(seed, "true", monkeypatch)
    t = store.get_task(store.db(), own)
    conflict = zone_lock.blocking_conflict(store.db(), own, t)
    assert conflict is not None, f"{note}: конфликта нет"
    assert conflict[1] == holder and conflict[2] == STATE, f"{note}: {conflict}"
    text = zone_lock.refusal(store.db(), own, t)
    assert text and holder in text, f"{note}: {text!r}"


def test_ac11_awaiting_human_frees_zones_when_false(initialized_tmp_root, seed, monkeypatch):
    """При `awaiting_holds_zones: false` зона задачи в `awaiting_human` свободна — отказа занятости нет.

    Сценарий: тот же, что при `true`, но запись проекта с
    `awaiting_holds_zones: false`: `zone_lock.blocking_conflict` — None,
    `zone_lock.refusal` — None.

    Ловит мутацию: поле `awaiting_holds_zones` не читается —
    `awaiting_human` в `BLOCKING_STATES` держит зону при любом значении;
    поле читается из записи артели, а не из записи проекта задачи.
    """
    own, _holder, _zone, note = zone_scenario(seed, "false", monkeypatch)
    t = store.get_task(store.db(), own)
    assert zone_lock.blocking_conflict(store.db(), own, t) is None, note
    assert zone_lock.refusal(store.db(), own, t) is None, note


# --- AC-12 -----------------------------------------------------------------

def test_ac12_merge_after_waits_done_of_awaiting_dependency(initialized_tmp_root, seed):
    """Защита от регрессии: зависимый по `merge_after` от задачи в `awaiting_human` ждёт её `done`.

    Сценарий: задача-зависимость в `awaiting_human`; зависимая — в
    `merge_gate` с `merge_after` на неё (одна или две зависимости, вторая
    — в `done`, порядок случаен). `merge_after.merge_gate_refuses` — True,
    в журнале зависимой запись `MERGE_GATE_WAIT_ACTION`; добавка `status`
    (`merge_after.status_suffix`) называет зависимость и `awaiting_human`.
    После перевода зависимости в `done` — отказа нет.

    Ловит мутацию: `awaiting_human` считается «удовлетворённой»
    зависимостью (сравнение с перечнем «ждущих людей» вместо `!= "done"`)
    — гейт мержа зависимой пропустит её раньше `done` зависимости.
    """
    rng = random.Random(seed)
    dep = insert(STATE)
    deps = [dep]
    if rng.random() < 0.5:
        deps.append(insert("done"))
        rng.shuffle(deps)
    gate = insert("merge_gate")
    conn = store.db()
    store.update_task(conn, gate, merge_after=merge_after.column(deps))
    note = f"зерно: {seed}; зависимости {deps}"
    buf = io.StringIO()
    with redirect_stdout(buf):
        refused = merge_after.merge_gate_refuses(conn, gate, store.get_task(conn, gate))
    assert refused, f"{note}: {buf.getvalue()}"
    rows = store.task_steps(store.db(), gate)
    assert rows and rows[-1]["action"] == merge_after.MERGE_GATE_WAIT_ACTION, note
    suffix = merge_after.status_suffix(conn, store.get_task(conn, gate))
    assert dep in suffix and STATE in suffix, f"{note}: {suffix!r}"
    conn.execute("UPDATE tasks SET state='done' WHERE id=?", (dep,))
    conn.commit()
    with redirect_stdout(io.StringIO()):
        assert not merge_after.merge_gate_refuses(conn, gate, store.get_task(conn, gate)), note


# --- AC-19 -----------------------------------------------------------------

def test_ac19_doctor_skips_freshness_of_awaiting_human_branch(initialized_tmp_root, seed):
    """`doctor` не сверяет свежесть ветки задачи в `awaiting_human`; ветку задачи в `in_dev` — сверяет.

    Сценарий: задача артели в `awaiting_human` и задача в `in_dev`, обе с
    ветками; `gitcmd.in_repo` проверки (через `doctor.gitcmd`) отвечает
    успехом, `commits_behind` подменён и записывает ветку, о которой
    спрошен, отвечая «сильно отстала». `doctor.check_branch_freshness`:
    ветка задачи в `awaiting_human` не спрошена и не названа в проверках;
    ветка задачи в `in_dev` спрошена (контроль).

    Ловит мутацию: в `branch_freshness` пропуск оставлен только для
    окончательных состояний — ветка задачи в `awaiting_human` спрошена и
    получает предупреждение «отстала».
    """
    waiting = insert(STATE)
    working = insert("in_dev")
    branches = {r["id"]: r["branch"] for r in store.all_tasks(store.db())}
    asked = []

    def behind(branch, base=None, repo=None):
        asked.append(branch)
        return config.STALE_BRANCH_WARN_COMMITS + 1

    ok = subprocess.CompletedProcess(["fetch"], 0, "", "")
    with mock.patch.object(doctor.gitcmd, "in_repo", return_value=ok), \
            mock.patch.object(doctor.gitcmd, "commits_behind", behind):
        checks = doctor.check_branch_freshness(store.db())
    note = f"зерно: {seed}; спрошены {asked}; проверки {[c.detail for c in checks]}"
    assert branches[waiting] not in asked, note
    assert not any(waiting in (c.detail or "") for c in checks), note
    assert branches[working] in asked, note
