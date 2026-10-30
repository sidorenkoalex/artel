"""Состояние `awaiting_human` в узлах пульта, которые долгоживущие файлы
задачи 01M5XZ9Z68V75VXF5Z66C708T4 не держат: разбор точки отправки
`gitcmd._push_plan`, признак «сервер оставлен людям проекта» уборки `kill`,
прогноз зон `zone_lock.forecast_overlaps` и строка ссылки на MR.
"""
from orchestrator import cleanup, config, gitcmd, idgen, store, targets, zone_lock

STATE = "awaiting_human"


def insert(state: str, target: str = config.DEFAULT_TARGET, *,
           zones: str | None = None) -> tuple[str, str]:
    task_id = idgen.new_task_id()
    branch = f"task/{task_id.lower()}-u"
    conn = store.db()
    store.insert_task(conn, task_id, "Задача", "in_dev", branch, target,
                      config.DEFAULT_BUDGET_USD)
    if zones is not None:
        store.update_task(conn, task_id, zones=zones)
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()
    return task_id, branch


def declare(name: str, gate: str, holds: str | None = None) -> None:
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
        f"      merge_gate: {gate}\n"
        f"      weakening_scope: [tests/**/*.py]\n"
        f"      mutation_claim_scope: [tests/test_*.py]\n" + extra
        + f"    machine:\n      forge: github\n"
        f"      url: https://localhost/team/{name}\n"
        f"      token_slot: {name}-token\n", encoding="utf-8")


def test_push_plan_refuses_every_delete_form_of_awaiting_branch(initialized_tmp_root):
    """Удаление ветки задачи в `awaiting_human` — `--delete`, `-d`, `:<ветка>`,
    `:refs/heads/<ветка>` — отказ разбора отправки с именем состояния; та
    же ветка задачи в `in_dev` (`--delete`) отказа по состоянию не получает.

    Ловит мутацию: `_awaiting_human_spec` смотрит только отправляемые ветки
    (`not s["colon"]`) или стоит за условием «не удаление» — формы удаления
    пройдут без отказа.
    """
    task_id, branch = insert(STATE)
    for args in (["push", "origin", "--delete", branch],
                 ["push", "-d", "origin", branch],
                 ["push", "origin", f":{branch}"],
                 ["push", "origin", f":refs/heads/{branch}"]):
        plan = gitcmd._push_plan(args, config.ROOT, {}, None)
        assert plan is not None and plan.refusal, args
        assert STATE in plan.refusal and task_id in plan.refusal, plan.refusal
    store.update_task(store.db(), task_id, state="in_dev")
    plan = gitcmd._push_plan(["push", "origin", "--delete", branch],
                             config.ROOT, {}, None)
    assert plan is not None and not (plan.refusal or "").count(STATE), plan.refusal


def test_push_plan_ignores_awaiting_task_of_other_branch(initialized_tmp_root):
    """Отказ — только по ветке задачи в `awaiting_human`: отправка чужой
    ветки (задачи в `in_dev`) рядом с такой задачей причину ожидания не
    получает.

    Ловит мутацию: проверка срабатывает на наличии в проекте любой задачи в
    `awaiting_human`, а не на ветке refspec — отправка соседней задачи
    отказана.
    """
    insert(STATE)
    _other, branch = insert("in_dev")
    plan = gitcmd._push_plan(["push", "origin", "--delete", branch],
                             config.ROOT, {}, None)
    assert plan is not None and STATE not in (plan.refusal or ""), plan.refusal


def test_kill_leaves_server_only_for_target_human_after_push(initialized_tmp_root,
                                                             monkeypatch):
    """Признак «сервер оставлен людям проекта» уборки `kill`: `target-human`
    с записью «ветка отправлена» (новой или старой формы) — да; без записи
    — нет; проект `operator` с записью — нет.

    Ловит мутацию: признак берётся по гейту без записи журнала (ветка,
    которой нет на сервере, «оставлена»); запись старого вида без двоеточия
    не узнаётся; предикат перепутан и сервер оставлен проекту `operator`.
    """
    monkeypatch.setattr(targets, "SUPPORTED_MERGE_GATES",
                        ("operator", "target-human"))
    conn = store.db()
    declare("humanp", "target-human")
    sent, branch = insert("in_dev", "humanp")
    legacy, legacy_branch = insert("review", "humanp")
    silent, _ = insert("in_dev", "humanp")
    store.journal(conn, sent, "orchestrator", gitcmd.PUSH_SENT_ACTION,
                  f"{'a' * 40} {branch}")
    store.journal(conn, legacy, "orchestrator", gitcmd.PUSH_SENT_LEGACY_ACTION,
                  f"{'b' * 40} {legacy_branch}")
    assert cleanup._server_left_to_project_people(conn, sent, "humanp")
    assert cleanup._server_left_to_project_people(conn, legacy, "humanp")
    assert not cleanup._server_left_to_project_people(conn, silent, "humanp")
    declare("humanp", "operator")
    assert not cleanup._server_left_to_project_people(conn, sent, "humanp")


def test_forecast_skips_awaiting_zone_only_when_not_held(initialized_tmp_root,
                                                         monkeypatch):
    """Прогноз зон (`status`, `new`) видит зону задачи в `awaiting_human` при
    `awaiting_holds_zones: true` и умолчании и не видит при `false`.

    Ловит мутацию: поле `awaiting_holds_zones` учтено только в отказе
    старта (`_occupier`), а прогноз по-прежнему обещает «зона занята»
    задачей, которая её отпустила.
    """
    monkeypatch.setattr(targets, "SUPPORTED_MERGE_GATES",
                        ("operator", "target-human"))
    for holds, seen in ((None, True), ("true", True), ("false", False)):
        declare("zonep", "target-human", holds)
        conn = store.db()
        conn.execute("DELETE FROM tasks")
        conn.commit()
        holder, _ = insert(STATE, "zonep", zones="pkg/mod.py")
        found = zone_lock.forecast_overlaps(conn, {"pkg/mod.py"},
                                            states=zone_lock.BLOCKING_STATES,
                                            target="zonep")
        assert bool(found) is seen, (holds, found)
        if seen:
            assert found[0][1:] == (holder, STATE), found


def test_mr_link_text_reads_row_columns(initialized_tmp_root):
    """Строка ссылки на MR — из столбцов задачи, записанных
    `store.set_mr_link`; без ссылки — пусто.

    Ловит мутацию: `set_mr_link` пишет не те столбцы (`mr_url` теряется) или
    `mr_link_text` печатает «MR» у задачи без ссылки.
    """
    task_id, _ = insert(STATE)
    conn = store.db()
    assert store.mr_link_text(store.get_task(conn, task_id)) == ""
    url = "https://localhost/team/p/-/merge_requests/17"
    store.set_mr_link(conn, task_id, 17, url)
    row = store.get_task(conn, task_id)
    assert store.mr_link(row) == (17, url)
    assert store.mr_link_text(row) == f"MR !17 {url}"
