"""Алерт 80 % конверта эпика после начисления стоимости шага: обе ветви учёта `runner` и `pause --now`.

Группа: долгоживущий
Красен до реализации: команд `epic new`/`epic envelope` и таблицы `epics` нет — заведение эпика сценария падает отказом «Неизвестная команда epic»; вызова `budget.check_epic_alert` после начисления нет — алерта с id эпика нет.

Связка, которую держит файл: «начисление стоимости шага — алерт — БД».
Шаг роли — настоящий `runner.cmd_run(<id>)` с подменённым процессом
агента (`runner.spawn_agent` -> `tests.sandbox.FakeProc`): финальное
событие со стоимостью ведёт учёт в ветку `spend.charge_step`, обрыв
stdout-пайпа после usage-событий — в ветку `spend.charge_missing_result`.
`pause --now` — настоящий `pause.cmd_pause_now(<id>)` над живым процессом
lease (как `tests/test_pause_now.py`), чекпоинт подменён. Эпик —
командой `epic new … --envelope N` через `artel.main()` (SPEC шага Э1),
конверт — `epic envelope`, подтверждение алерта — `alert-ack`. Алерт
эпика — строка `alerts`, в тексте которой есть id эпика.

Суммы начислений и потраченного до шага порождаются модулем `random` при
каждом запуске; зерно печатается и входит в текст провала.

Провалидировано временным стабом реализации Э1+Э2а (таблица `epics`, команды
`epic …`, проверки `runner`, алерт `budget`, строки `watch`, остановка
`auto`, граф `merge_after`; удалён, не закоммичен): все методы файла
зелёные; правдоподобные мутации стаба, названные в заявках, их красят.
"""
import io
import json
import os
import random
import socket
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import pytest

from orchestrator import (agent_log, artel, checkpoint, config, pause,
                          runner, store)
from tests.sandbox import (DeveloperBriefTmpRootTest, FakeProc, FakeStream,
                           LightTransitionSandbox, capture, event, patch_sleep,
                           sync_spec_from_worktree)


def result_event(usd: float) -> str:
    return event(type="result", subtype="success", is_error=False,
                 result="готово", total_cost_usd=usd,
                 usage={"input_tokens": 100, "output_tokens": 20})


def usage_event() -> str:
    return event(type="assistant", message={
        "role": "assistant", "content": [{"type": "text", "text": "работаю"}],
        "usage": {"input_tokens": 200000, "output_tokens": 50000}})


class BrokenPipeStream(FakeStream):
    """Пайп, обрывающийся после заготовленных строк: `OSError` вместо EOF."""

    def __next__(self) -> str:
        try:
            return next(self.lines)
        except StopIteration:
            raise OSError("обрыв stdout-пайпа шага") from None


def cli(*argv: str) -> str:
    buf = io.StringIO()
    with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
            redirect_stdout(buf), redirect_stderr(buf):
        artel.main()
    return buf.getvalue()


def new_epic(seed: int, envelope) -> str:
    title = f"Эпик алерта {seed:x}-{random.randrange(1 << 20):x}"
    cli("epic", "new", config.DEFAULT_TARGET, title, "--goal", "Цель сценария",
        "--envelope", f"{envelope}")
    row = store.db().execute("SELECT id FROM epics WHERE title=?",
                             (title,)).fetchone()
    assert row is not None, f"зерно {seed}: эпик «{title}» не заведён"
    return row["id"]


def epic_alerts(epic_id: str) -> list:
    return [dict(r) for r in store.db().execute("SELECT * FROM alerts ORDER BY id")
            if epic_id in " ".join(str(v) for v in dict(r).values())]


def open_epic_alerts(epic_id: str) -> list:
    return [a for a in epic_alerts(epic_id)
            if any(a["id"] == r["id"] for r in store.open_alerts(store.db(), None))]


class ChargingSandbox(LightTransitionSandbox, DeveloperBriefTmpRootTest):
    """Лёгкая песочница переходов поверх скилов и фикстур брифа разработчика:
    шаг роли собирает бриф и доходит до запуска агента."""


class ChargingPult:
    """Задача артели в `in_dev` с шагом разработчика, идущим до учёта денег."""

    def __init__(self, sandbox, seed: int):
        self.sandbox = sandbox
        self.seed = seed
        self.rng = random.Random(seed)
        self.task = sandbox.TASK
        sync_spec_from_worktree(self.task)
        store.update_task(store.db(), self.task, state="in_dev")
        self.donor = None

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def seed_plan_marker(self) -> None:
        # Каталог документов задачи артели (ADR-0021): `.artel/projects/<проект>/`
        # и тот же подкаталог задач, что `config.TASKS`.
        tdir = config.PROJECTS / config.DEFAULT_TARGET / config.TASKS.name / self.task
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text("маркер\n", encoding="utf-8")

    def join_epic(self, epic_id: str, spent_before: float) -> None:
        """Задача сценария — в эпике; ещё одна задача эпика несёт
        потраченное до шага `spent_before`."""
        conn = store.db()
        store.update_task(conn, self.task, epic_id=epic_id, spent_usd=0.0)
        self.donor = "01" + "".join(self.rng.choices(
            "0123456789ABCDEFGHJKMNPQRSTVWXYZ", k=24))
        store.insert_task(conn, self.donor, "Задача эпика", "review",
                          f"task/{self.donor.lower()}-donor",
                          config.DEFAULT_TARGET, 1000.0)
        store.update_task(conn, self.donor, epic_id=epic_id,
                          spent_usd=spent_before)

    def run(self, *procs) -> str:
        self.seed_plan_marker()
        buf = io.StringIO()
        with mock.patch.object(runner, "spawn_agent", side_effect=list(procs)), \
                redirect_stdout(buf), redirect_stderr(buf):
            try:
                runner.cmd_run(self.task)
            except SystemExit as exc:
                buf.write(f"\n{exc}")
        if store.get_task(store.db(), self.task)["state"] != "in_dev":
            store.update_task(store.db(), self.task, state="in_dev")
        return buf.getvalue()

    def charge_step(self, usd: float) -> str:
        return self.run(FakeProc([result_event(usd)], 0))

    def charge_broken_pipe(self) -> str:
        procs = []
        for _ in range(config.AGENT_ATTEMPTS):
            proc = FakeProc([], 1)
            proc.stdout = BrokenPipeStream(["агент работает\n", usage_event()])
            procs.append(proc)
        return self.run(*procs)


@pytest.fixture
def charging():
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    sandbox = ChargingSandbox()
    sandbox.setUp()
    patches = [mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
               patch_sleep(runner, lambda _: None),
               mock.patch.object(runner.keychain, "token", lambda slot: "tok-test"),
               mock.patch("orchestrator.doctor.preflight_checks",
                          lambda role, target, **kwargs: [])]
    try:
        for patcher in patches:
            patcher.start()
        yield ChargingPult(sandbox, seed)
    finally:
        for patcher in reversed(patches):
            patcher.stop()
        sandbox.doCleanups()


def test_ac3_charge_step_raises_one_alert_per_envelope(charging):
    """Начисление веткой `charge_step` до $8,50 из $10 поднимает ровно один алерт эпика — и только один.

    Сценарий: конверт $10; до шага по эпику потрачено $8,50 − X; шаг
    разработчика стоит X (случайно $0,10–$2,00) — потрачено ≥ $8,50.
    Алерт эпика ровно один. Следующее начисление при открытом алерте
    второго не поднимает; алерт подтверждён `alert-ack` — и ещё одно
    начисление нового алерта не поднимает.

    Ловит мутацию: вызова `budget.check_epic_alert` в общей точке после
    учёта нет (алерта ноль); признак «алерт уже поднят» берётся из
    открытых алертов, а не из значения конверта — после `alert-ack`
    начисление поднимает второй алерт.
    """
    pult = charging
    epic_id = new_epic(pult.seed, 10)
    cost = pult.rng.randint(10, 200) / 100
    pult.join_epic(epic_id, round(8.5 - cost, 2))
    out = pult.charge_step(cost)
    raised = epic_alerts(epic_id)
    assert len(raised) == 1, pult.msg(f"алерты эпика {raised}; вывод:\n{out}")

    out = pult.charge_step(pult.rng.randint(1, 50) / 100)
    assert len(epic_alerts(epic_id)) == 1, pult.msg(
        f"второй алерт при открытом первом: {epic_alerts(epic_id)}\n{out}")

    cli("alert-ack", str(raised[0]["id"]), "Оператор видел перерасход")
    assert open_epic_alerts(epic_id) == [], pult.msg("алерт не подтверждён")
    out = pult.charge_step(pult.rng.randint(1, 50) / 100)
    assert len(epic_alerts(epic_id)) == 1, pult.msg(
        f"новый алерт после alert-ack при том же конверте: "
        f"{epic_alerts(epic_id)}\n{out}")


def test_ac4_missing_result_branch_raises_alert(charging):
    """Начисление веткой `charge_missing_result` (обрыв пайпа) до ≥ $8,00 из $10 поднимает алерт эпика.

    Сценарий: конверт $10; до шага по эпику потрачено случайно
    $8,00–$9,50; каждая попытка шага разработчика отдаёт usage-событие и
    обрывает stdout-пайп без финального события — учёт идёт веткой
    `spend.charge_missing_result`. Алерт эпика поднят.

    Ловит мутацию: `check_epic_alert` вызван только после ветки
    `charge_step` (внутри `else`), а не в общем хвосте после обеих
    ветвей — алерта нет.
    """
    pult = charging
    epic_id = new_epic(pult.seed, 10)
    pult.join_epic(epic_id, pult.rng.randint(800, 950) / 100)
    out = pult.charge_broken_pipe()
    journal = [r["action"] for r in store.task_steps(store.db(), pult.task)]
    assert not any(a == "agent cost KNOWN" for a in journal), pult.msg(
        f"шаг ушёл не в ветку charge_missing_result: {journal}")
    assert epic_alerts(epic_id), pult.msg(f"алерта эпика нет; вывод:\n{out}")


def test_ac6_new_envelope_restarts_alert_count(charging):
    """После `alert-ack` и `epic envelope 10.5` начисление до ≥ $8,40 поднимает новый алерт.

    Сценарий AC-3: первый алерт при $8,50 из $10, `alert-ack`. Конверт
    изменён командой `epic envelope` на $10,50 (порог $8,40); следующее
    начисление (потрачено уже ≥ $8,40) поднимает новый алерт эпика —
    всего два, открыт один.

    Ловит мутацию: признак «алерт поднят» хранится на эпик без учёта
    значения конверта — после смены конверта алерта нет.
    """
    pult = charging
    epic_id = new_epic(pult.seed, 10)
    cost = pult.rng.randint(10, 200) / 100
    pult.join_epic(epic_id, round(8.5 - cost, 2))
    pult.charge_step(cost)
    raised = epic_alerts(epic_id)
    assert len(raised) == 1, pult.msg(f"{raised}")
    cli("alert-ack", str(raised[0]["id"]), "Оператор видел перерасход")

    cli("epic", "envelope", epic_id, "10.5")
    out = pult.charge_step(pult.rng.randint(1, 50) / 100)
    after = epic_alerts(epic_id)
    assert len(after) == 2, pult.msg(f"алерты эпика {after}; вывод:\n{out}")
    assert len(open_epic_alerts(epic_id)) == 1, pult.msg(f"{after}")


@pytest.fixture
def pausing(initialized_tmp_root):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    procs = []
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}), \
            mock.patch.object(checkpoint, "commit_pause_now_checkpoint",
                              return_value=""):
        yield seed, procs
    for proc in procs:
        if proc.poll() is None:
            proc.kill()
        proc.wait()


def test_ac5_pause_now_partial_charge_raises_alert(pausing):
    """Частичное начисление `pause --now` до ≥ $8,00 из $10 поднимает алерт эпика.

    Сценарий: конверт $10; задача эпика в `in_dev`, её шаг идёт в живом
    процессе под lease этой машины, лог шага несёт usage-событие; по
    эпику уже потрачено случайно $8,00–$9,50. `pause --now` прерывает шаг
    и учитывает частичную стоимость (`spend.charge_missing_result`) —
    алерт эпика поднят.

    Ловит мутацию: вызова `budget.check_epic_alert` после
    `spend.charge_missing_result` в `pause.py` нет — алерта нет.
    """
    seed, procs = pausing
    rng = random.Random(seed)
    epic_id = new_epic(seed, 10)
    conn = store.db()
    task_id = "01" + "".join(rng.choices("0123456789ABCDEFGHJKMNPQRSTVWXYZ", k=24))
    store.insert_task(conn, task_id, "Шаг под паузой", "in_dev",
                      f"task/{task_id.lower()}-pauza", config.DEFAULT_TARGET,
                      1000.0)
    store.update_task(conn, task_id, epic_id=epic_id,
                      spent_usd=rng.randint(800, 950) / 100)
    log_path = agent_log.new_agent_log(task_id, "developer")
    log_path.write_text("агент работает\n" + json.dumps({
        "type": "assistant",
        "message": {"usage": {"input_tokens": 200000, "output_tokens": 50000}}})
        + "\n", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(proc)
    store.insert_lease(conn, task_id, "other-session", proc.pid,
                       socket.gethostname(), store.now())
    out = capture(pause.cmd_pause_now, task_id)
    proc.wait(timeout=10)
    journal = "\n".join(f"{r['action']} | {r['detail']}"
                        for r in store.task_steps(store.db(), task_id))
    assert epic_alerts(epic_id), (f"зерно {seed}: алерта эпика нет; вывод:\n"
                                  f"{out}\nжурнал:\n{journal}")
