"""`answer` со строкой мандата при цикле `auto`, ждущем зону: pid цикла в записи «auto старт», приём без отказа по lease, прежний отказ при шаге и в `verifying` (AC-13 … AC-15).

Группа: долгоживущий
Красен до реализации: запись «auto старт» несёт деталь «состояние <состояние>, лимит <N> шагов» без pid цикла, а `answer` с файлом со строкой мандата при lease живого цикла `auto`, ждущего зону, отказывает по lease «задачу прямо сейчас ведёт процесс …» — ANSWER не создаётся.

AC-13 (отказ при входе в ожидание от убитого цикла и lease ручного `run`),
AC-14 и AC-15 держат сегодняшний отказ по lease против правки, которая
откроет приём мимо него.

Провалидировано временным стабом реализации поверх ветки задачи (pid в
детали записи старта, приём `answer` при lease живого ждущего цикла;
удалён, не закоммичен): все методы файла зелёные.

Связка, которую держит файл: команда `answer` (`answer.cmd_answer`) —
lease задачи (`leases`, `lease.acquire`) — журнал задачи — ссылка
документов `refs/artifacts/<id>` в настоящем git песочницы; для записи
старта — цикл `auto.cmd_auto` над задачей в состоянии без роли.

Песочница — `real_git` (`tests.sandbox.RealGitSandbox`) с закоммиченным
`.gitignore` пульта: задача заведена `catalog.cmd_new` и переведена прямой
записью БД в нужное состояние. Цикл `auto`, держащий lease, разыгрывается
так, как его оставляет настоящий цикл: живой процесс держит lease задачи
своим pid, запись «auto старт» с его pid и сессией, вход в ожидание зоны
(`zone_lock.wait_enter_action`) без закрытия, зону держит другая задача
с начатым шагом разработчика. Эталон текста отказа «как на main для той
же сессии» — `lease.acquire` той же сессии над тем же lease (без
побочных эффектов в ветке отказа). Сессия держателя, зона, текст
основания и путь мандата — из `random`; зерно печатается и входит в
текст провала.
"""
import contextlib
import io
import os
import random
import signal
import socket
from dataclasses import dataclass

import pytest

from orchestrator import (answer, auto, catalog, config, idgen, lease, projects,
                          store, zone_lock)
from orchestrator.advance_gates import mandate
from tests import mandate_matrix
from tests.sandbox import GITIGNORE_TEXT, _alive_foreign_pid, _dead_pid

DOCS_REF_PREFIX = "refs/artifacts/"
MANDATE_ACTION_PREFIX = "ANSWER создан (мандат на ослабление тестов:"
NEXT_STEP_HINT = "указание дойдёт до роли на её следующем шаге"
ROLE_STEP_STARTED = "agent run started"
ROLE_STEP_FINISHED = "agent run finished"

ARTEL_TARGETS = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

SPEC_TEMPLATE = """---
task: TASK_ID
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: <название задачи>

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

WORDS = ("разбор", "падение", "причина", "модуль", "фикстура", "импорт",
         "порядок", "песочница", "ветка", "журнал", "шаг", "проверка")


def run_cmd(fn, *args) -> tuple:
    """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
    buf = io.StringIO()
    failed = False
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fn(*args)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                failed = True
                buf.write(f"\n{exc.code}")
    return buf.getvalue(), failed


@dataclass
class World:
    """Пульт на настоящем git; задачи артели заводятся `catalog.cmd_new`."""

    sandbox: object
    seed: int
    rng: random.Random

    def why(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def new_task(self, state: str) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            task = catalog.cmd_new(f"Ожидание {self.rng.randrange(10 ** 6)}",
                                   target=config.DEFAULT_TARGET)
        self.set_state(task, state)
        return task

    def set_state(self, task: str, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task))
        conn.commit()

    def zone_held_by_other(self, task: str) -> str:
        """Зона задачи `task` занята другой задачей (шаг разработчика начат); id держателя."""
        zone = f"zona{self.rng.randrange(1 << 24):x}/modul.py"
        holder = idgen.new_task_id()
        conn = store.db()
        store.insert_task(conn, holder, "Держатель зоны", "in_dev",
                          f"task/{holder.lower()}-h", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(conn, holder, zones=zone)
        store.journal(conn, holder, "developer", ROLE_STEP_STARTED, "попытка 1/3")
        store.update_task(conn, task, zones=zone)
        return holder

    def cycle_started(self, task: str, pid: int, session: str, state: str) -> None:
        """Запись старта цикла `auto` с pid процесса цикла и его сессией."""
        store.journal(store.db(), task, "operator", zone_lock.AUTO_START_ACTION,
                      f"состояние {state}, лимит {config.AUTO_MAX_STEPS} шагов, pid {pid}",
                      session_id=session)

    def enters_zone_wait(self, task: str, holder: str) -> None:
        zone = store.get_task(store.db(), task)["zones"]
        store.journal(store.db(), task, "operator",
                      zone_lock.wait_enter_action(zone, holder, "in_dev"), "")

    def take_lease(self, task: str, session: str, pid: int) -> None:
        conn = store.db()
        store.insert_lease(conn, task, session, pid, socket.gethostname(), store.now())
        conn.commit()

    def lease_row(self, task: str) -> dict | None:
        row = store.lease_row(store.db(), task)
        return dict(row) if row is not None else None

    def own_session(self) -> str:
        return lease.resolve_session_id(None)

    def expected_refusal(self, task: str) -> str:
        """Текст отказа lease той же сессии над текущим lease задачи."""
        refusal, _fresh = lease.acquire(store.db(), task, self.own_session())
        return refusal or ""

    def mandate_file(self) -> tuple:
        """(путь файла answer со строкой мандата тестов, элемент мандата)."""
        element = f"tests/test_{self.rng.randrange(10 ** 6)}.py"
        words = " ".join(self.rng.choice(WORDS) for _ in range(self.rng.randrange(3, 9)))
        text = (f"{mandate.TEST_WEAKENING_MANDATE_MARKER} {element}\n\n"
                f"Основание: {words}.\n")
        path = self.sandbox.root / ".artel" / f"answer-{self.rng.randrange(1 << 40)}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(mandate_matrix.with_matrix(text), encoding="utf-8")
        return str(path), element

    def answers(self, task: str) -> list:
        ref = DOCS_REF_PREFIX + task
        if not self.sandbox.git("for-each-ref", "--format=%(objectname)", ref).strip():
            return []
        return sorted(p for p in self.sandbox.git("ls-tree", "-r", "--name-only",
                                                  ref).splitlines()
                      if p.rsplit("/", 1)[-1].startswith("ANSWER-"))

    def rows(self, task: str) -> list:
        return list(store.task_steps(store.db(), task))


def answer_rel(task: str, n: int) -> str:
    return "/".join(("tasks", task, f"ANSWER-{n}.md"))


@pytest.fixture
def world(real_git, monkeypatch):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    (real_git.root / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
    real_git.git("add", ".gitignore")
    real_git.git("commit", "-q", "-m", "gitignore")
    config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
    run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
    run_cmd(catalog.cmd_init)
    real_git.use_role_map()
    templates = real_git.root / ".artel" / "templates-fixture"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "SPEC.md").write_text(SPEC_TEMPLATE, encoding="utf-8")
    monkeypatch.setattr(config, "TEMPLATES", templates)
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "")
    monkeypatch.setattr("orchestrator.doctor.preflight_checks", lambda *args, **kwargs: [])
    previous = signal.getsignal(signal.SIGTERM)
    yield World(real_git, seed, random.Random(seed))
    signal.signal(signal.SIGTERM, previous)


# --------------------------------------------------------------------- AC-13


@pytest.mark.parametrize("state", ["done", "killed"])
def test_ac13_auto_start_record_carries_cycle_pid(world, state):
    """Цикл `auto` пишет «auto старт» с деталью «состояние <состояние>, лимит <N> шагов, pid <pid>».

    Сценарий: задача в состоянии без агентской роли; `auto.cmd_auto` —
    цикл стартует и сразу останавливается. В журнале задачи ровно одна
    запись «auto старт» актора `operator`, её деталь целиком — «состояние
    <состояние>, лимит `config.AUTO_MAX_STEPS` шагов, pid <pid процесса
    цикла>» (`os.getpid()` процесса, исполнившего цикл).

    Ловит мутацию: деталь без суффикса «, pid <pid>» (прежний текст); pid
    не процесса цикла (pid родителя, pid из lease чужого процесса) либо в
    ином виде (шестнадцатеричный, в скобках); суффикс дописан в другую
    запись, а не в запись старта.
    """
    task = world.new_task(state)
    out, _failed = run_cmd(auto.cmd_auto, task)
    starts = [r for r in world.rows(task) if r["action"] == zone_lock.AUTO_START_ACTION]
    assert len(starts) == 1, world.why(f"записей «auto старт»: {len(starts)}\n{out}")
    assert starts[0]["actor"] == "operator", world.why(starts[0]["actor"])
    expected = (f"состояние {state}, лимит {config.AUTO_MAX_STEPS} шагов, "
                f"pid {os.getpid()}")
    assert starts[0]["detail"] == expected, world.why(
        f"деталь «auto старт»: {starts[0]['detail']!r}, ждали {expected!r}")


def test_ac13_answer_with_mandate_accepted_while_live_cycle_waits_zone(world):
    """Lease держит живой цикл `auto` задачи, ждущий зону, — `answer` со строкой мандата принят.

    Сценарий: задача в `in_dev`, её зону держит другая задача; живой
    процесс цикла держит lease задачи своим pid (сессия — вызывающего
    Оператора либо другая, выбор случаен), запись «auto старт» несёт этот
    pid и эту сессию, вход в ожидание зоны открыт, шага роли нет.
    `answer` с файлом со строкой мандата тестов: отказа нет, в ссылке
    документов `ANSWER-1.md`, в журнале запись актора `operator`
    «ANSWER создан (мандат на ослабление тестов: <элемент>)» с путём
    ANSWER в детали, в выводе — «указание дойдёт до роли на её следующем
    шаге»; строка lease цикла та же, что до команды.

    Ловит мутацию: проверка lease по-прежнему отказывает ждущему циклу
    (ANSWER нет); ожидание распознаётся, но приём идёт без записи
    мандата или с записью указания; приём перехватывает lease цикла
    (строка lease переписана); подсказка о следующем шаге не печатается.
    """
    task = world.new_task("in_dev")
    holder = world.zone_held_by_other(task)
    pid = _alive_foreign_pid(world.sandbox)
    session = (world.own_session() if world.rng.randrange(2)
               else f"auto-{world.rng.randrange(10 ** 6)}")
    world.take_lease(task, session, pid)
    world.cycle_started(task, pid, session, "in_dev")
    world.enters_zone_wait(task, holder)
    before = world.lease_row(task)
    path, element = world.mandate_file()

    out, failed = run_cmd(answer.cmd_answer, task, path)

    case = f"сессия цикла {session!r}"
    assert not failed, world.why(f"{case}: answer отказала:\n{out}")
    rel = answer_rel(task, 1)
    assert rel in world.answers(task), world.why(f"{case}: {rel} нет")
    records = [r for r in world.rows(task) if r["actor"] == "operator"
               and r["action"].startswith(MANDATE_ACTION_PREFIX)]
    assert len(records) == 1, world.why(
        f"{case}: записей мандата: {[(r['action'], r['detail']) for r in records]}")
    assert element in records[0]["action"] and records[0]["detail"] == rel, world.why(
        f"{case}: запись мандата {records[0]['action']!r} / {records[0]['detail']!r}")
    assert NEXT_STEP_HINT in out, world.why(f"{case}: нет подсказки о следующем шаге:\n{out}")
    assert world.lease_row(task) == before, world.why(f"{case}: lease цикла изменён")
    assert store.get_task(store.db(), task)["state"] == "in_dev", world.why("состояние сменилось")


def test_ac13_wait_left_by_killed_cycle_with_manual_run_lease_refused(world):
    """Вход в ожидание открыт от убитого цикла, lease держит ручной `run` той же сессии — прежний отказ по lease.

    Сценарий: запись «auto старт» с pid процесса, который уже не жив, вход
    в ожидание зоны открыт; lease задачи держит живой процесс ручного
    `run` той же сессии, что убитый цикл (сессия вызывающего Оператора),
    — записи старта цикла с его pid нет. `answer` со строкой мандата
    отказывает тем же текстом, что `lease.acquire` этой сессии; ANSWER
    не создан.

    Ловит мутацию: ожиданием считается любой открытый вход при живом
    lease, без сверки pid держателя lease с pid записи старта цикла
    (ANSWER создан под чужим шагом); сверяется только сессия.
    """
    task = world.new_task("in_dev")
    holder = world.zone_held_by_other(task)
    session = world.own_session()
    world.cycle_started(task, _dead_pid(), session, "in_dev")
    world.enters_zone_wait(task, holder)
    world.take_lease(task, session, _alive_foreign_pid(world.sandbox))
    expected = world.expected_refusal(task)
    path, _element = world.mandate_file()

    out, failed = run_cmd(answer.cmd_answer, task, path)

    assert expected, world.why("эталон отказа пуст: lease.acquire не отказал")
    assert failed, world.why(f"answer не отказала:\n{out}")
    assert expected in out, world.why(f"текст отказа не тот:\n{out}\nждали: {expected}")
    assert world.answers(task) == [], world.why("ANSWER создан")


# --------------------------------------------------------------------- AC-14


@pytest.mark.parametrize("wait", ["закрыто", "не было"])
def test_ac14_answer_refused_while_agent_step_runs(world, wait):
    """При идущем агентном шаге цикла `answer` со строкой мандата получает прежний отказ по lease.

    Сценарий: задача в `in_dev`; живой цикл `auto` держит lease своим pid
    (сессия вызывающего Оператора), запись «auto старт» с этим pid; цикл
    ведёт шаг разработчика («agent run started» без завершения); вход в
    ожидание зоны до шага уже закрыт «зона свободна через …» либо не
    открывался вовсе. `answer` отказывает тем же текстом, что
    `lease.acquire` этой сессии; ANSWER не создан.

    Ловит мутацию: ждущим считается любой живой цикл `auto` задачи (или
    цикл, у которого когда-либо был вход в ожидание), без сверки, что вход
    не закрыт и шага нет, — ANSWER создан при идущем шаге.
    """
    task = world.new_task("in_dev")
    holder = world.zone_held_by_other(task)
    session = world.own_session()
    pid = _alive_foreign_pid(world.sandbox)
    world.take_lease(task, session, pid)
    world.cycle_started(task, pid, session, "in_dev")
    if wait == "закрыто":
        world.enters_zone_wait(task, holder)
        store.journal(store.db(), task, "operator", zone_lock.wait_exit_action(holder, 1), "")
    store.journal(store.db(), task, "developer", ROLE_STEP_STARTED, "попытка 1/3")
    expected = world.expected_refusal(task)
    path, _element = world.mandate_file()

    out, failed = run_cmd(answer.cmd_answer, task, path)

    case = f"ожидание {wait}"
    assert expected, world.why("эталон отказа пуст: lease.acquire не отказал")
    assert failed, world.why(f"{case}: answer не отказала:\n{out}")
    assert expected in out, world.why(f"{case}: текст отказа не тот:\n{out}\nждали: {expected}")
    assert world.answers(task) == [], world.why(f"{case}: ANSWER создан")


# --------------------------------------------------------------------- AC-15


def test_ac15_answer_refused_in_verifying_while_cycle_waits_ci(world):
    """Задача в `verifying`, lease держит живой цикл, ждущий CI, — `answer` со строкой мандата отказывает прежним текстом.

    Сценарий: задача в `verifying` (шаг разработчика завершён); живой
    цикл `auto` держит lease своим pid (сессия вызывающего Оператора),
    запись «auto старт» с этим pid и состоянием `verifying`. `answer` со
    строкой мандата отказывает тем же текстом, что `lease.acquire` этой
    сессии; ANSWER не создан.

    Ловит мутацию: ждущим считается живой цикл задачи без идущего шага, без
    сверки состояния `in_dev` и открытого входа в ожидание зоны (в
    `verifying` lease не проверяется — `answer` отказывает по состоянию
    другим текстом); отказ по lease в `verifying` заменён отказом по
    состоянию.
    """
    task = world.new_task("verifying")
    session = world.own_session()
    pid = _alive_foreign_pid(world.sandbox)
    conn = store.db()
    store.journal(conn, task, "developer", ROLE_STEP_STARTED, "попытка 1/3")
    store.journal(conn, task, "developer", ROLE_STEP_FINISHED, "rc=0")
    world.take_lease(task, session, pid)
    world.cycle_started(task, pid, session, "verifying")
    expected = world.expected_refusal(task)
    path, _element = world.mandate_file()

    out, failed = run_cmd(answer.cmd_answer, task, path)

    assert expected, world.why("эталон отказа пуст: lease.acquire не отказал")
    assert failed, world.why(f"answer не отказала:\n{out}")
    assert expected in out, world.why(f"текст отказа не тот:\n{out}\nждали: {expected}")
    assert world.answers(task) == [], world.why("ANSWER создан")
