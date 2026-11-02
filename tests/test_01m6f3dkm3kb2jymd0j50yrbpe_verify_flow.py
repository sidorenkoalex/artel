"""Ожидание ручной проверки `human:<имя>` на `verifying`, команды Оператора `verify-ok`/`verify-fail`, `auto` и надзор эпика на ожидании.

Группа: долгоживущий
Красен до реализации: поля `verify` записи нет (запись с ним не загружается — каждый опрос `verifying` отказывает «запись проекта не прочитана»), задача после зелёного CI уходит в `review` без записи «ждёт проверки …», команд `verify-ok`/`verify-fail` нет (`artel.main` выходит «Неизвестная команда»), `auto` на `verifying` опрашивает CI до границы отрезка, надзор эпика запускает задаче дочерний `auto`.

Связка «команда пульта — FSM — база — git»: каждый сценарий доходит до
поведения через публичный вход — `fsm.cmd_advance` (опрос `verifying`),
`artel.main` с `sys.argv` команд `verify-ok`/`verify-fail`,
`catalog.cmd_status` (строка `status`), `board.build_model` (`waiting_on`),
`watch.cmd_watch --observation --notify` (уведомления),
`brief.developer_brief` (раздел «Причина возврата»), `auto.cmd_auto` и
`auto.cmd_auto_epic` (надзор эпика) — в настоящем git песочницы
(`tests.sandbox.RealGitSandbox`): клон внешнего проекта
(`tests.sandbox.make_project_repo`), запись проекта `forge: gitlab` — в
локальном слое (`targets.local_path()`), у одного проекта с полем
`description.verify`, у другого без него. Поддержка `gitlab` — подменой
`targets.SUPPORTED_FORGES`.

CI головы — ответ подделки хостинга `pipeline_status` по sha коммита
(реестр `forge.IMPLEMENTATIONS`, ключ `gitlab`): зелёный, идущий или
красный по сценарию. Гейт по исходам у проекта без компонентов `ci`
проходит пусто; «гейт по исходам не пройден» разыгрывается подменой
публичной функции `verifying_gate` во всех модулях пульта, которые её
держат: она отвечает ожиданием (`VerifyingVerdict(False, <причина>)`).

Вход в `verifying` и возврат из эскалации разыгрываются записью перехода
`store.set_state` (так их оставили бы `advance` из `in_dev` и `approve`
Оператора) — предмет файла начинается с опроса `verifying`. Голова ветки —
настоящий коммит рабочей копии задачи. Отметка проверки ищется в БД без
знания схемы: строка любой таблицы, кроме журнала `steps`, значения
которой содержат id задачи и имя проверки (и, где сказано, sha и итог).

`auto` и надзор эпика гоняются на подменённых часах (`time` модуля `auto`,
`store.now`): пауза сдвигает часы, по исчерпании отрезка сценария цикл
обрывается исключением теста. Дочерний `auto` надзора — вызов
`auto.cmd_auto` в процессе теста с подменённым процессом (pid не жив).

Имена проектов, проверок, итогов и причин — из `random`; зерно печатается и
входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен): поле
`verify`, ожидание с записью «ждёт проверки <имя> по sha <sha>» по визиту и
голове, строка `status`, `waiting_on` `operator`, значимая для `watch`
запись, потолок не к ожиданию, команды `verify-ok`/`verify-fail` с
таблицей отметок и счётчиком возвратов, остановка `auto` без алерта и
признак надзора — все методы файла зелёные.
"""
import contextlib
import io
import os
import random
import re
import signal
import subprocess
import sys
import time
from unittest import mock

import pytest

from orchestrator import (alerts, artel, auto, board, brief, budget, catalog,
                          checkpoint, ci, config, epics, forge, fsm, idgen,
                          keychain, store, targets, watch, workspace,
                          zone_lock)
from orchestrator.advance_gates import outcome_integrity
from tests.sandbox import make_project_repo, patch_sleep

LETTERS = "abcdefghijkmnopqrstuvwxyz"
NAME_CHARS = "abcdefghijkmnopqrstuvwxyz0123456789-"
IDENTITY = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")
NOT_EXPECTED = "проверка не ожидается для этой головы"
OTHER_HEAD = "отметка для другой головы"
WAITS = "ждёт проверки"
TO_REVIEW = "state -> review"
TO_IN_DEV = "state -> in_dev"
TO_ESCALATED = "state -> escalated"
TO_VERIFYING = "state -> verifying"
JOURNAL_TABLE = "steps"
DEAD_PID_BASE = 1_900_000_000

ENTRY = """  {name}:
    description:
      base: {base}
      test_profile:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
{verify}    policy:
      no_paths: []
      project_skills: []
      merge_gate: operator
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
    machine:
      forge: gitlab
      url: https://localhost/grp/{name}
      token_slot: {name}-token
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: app.py, kod/
budget_usd: 30
---

# SPEC: фикстура проверки verify

## Контекст

Фикстура песочницы.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстурный критерий.

## Не входит

Ничего.
"""


class Halt(BaseException):
    """Граница отрезка подменённых часов: обрывает цикл `auto`/надзора."""


class FakeForge:
    """Подделка хостинга `gitlab`: `pipeline_status` — вердикт сценария по
    sha (по умолчанию зелёный); прочие вызовы — отказ с причиной."""

    CI_BY_PIPELINE = True

    def __init__(self):
        self.verdicts: dict = {}

    def pipeline_status(self, target, sha):
        verdict = self.verdicts.get(sha, forge.GREEN)
        reason = {forge.GREEN: "", forge.RED: "задание unit: failed",
                  forge.RUNNING: "задание unit: running"}.get(verdict, "сценарий")
        status = {forge.GREEN: "success", forge.RED: "failed"}.get(verdict, "running")
        return forge.PipelineStatus(verdict, reason, [forge.Job("unit", status)])

    def __getattr__(self, name):
        if name.startswith("__") or name not in forge.RESULT_TYPES:
            raise AttributeError(name)

        def other(*args):
            return forge.RESULT_TYPES[name](reason=f"подделка: {name} не отвечает")
        return other


class DeadProc:
    """Подменённый процесс дочернего `auto`: вышел, pid не жив."""

    def __init__(self, pid: int):
        self.pid = pid
        self.returncode = 0

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0


class Clock:
    """Часы пульта на время `auto`/надзора: заместитель ссылки модуля
    `auto` на `time` и `store.now`; `sleep` сдвигает часы, за границей
    отрезка — `Halt`."""

    def __init__(self):
        self.t = float(int(time.time()) + 3600)
        self.end = self.t
        self.sleeps = 0

    def __getattr__(self, name):
        return getattr(time, name)

    def time(self) -> float:
        return self.t

    def monotonic(self) -> float:
        return self.t

    def now(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(self.t))

    def sleep(self, seconds) -> None:
        self.sleeps += 1
        self.t += float(seconds)
        if self.t >= self.end or self.sleeps > 2000:
            raise Halt()


class WatchDone(Exception):
    """Конец одного опроса `watch`."""


def capture_out(fn, *args, **kwargs) -> tuple:
    """(код отказа или None, вывод вместе с текстом `SystemExit`)."""
    buf = io.StringIO()
    code = None
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                code = exc.code
                buf.write(f"\n{exc.code}")
    return code, buf.getvalue()


class Stand:
    """Пульт с двумя внешними проектами `gitlab`: `ext` — с профилем
    `verify` сценария, `plain` — без поля `verify`."""

    def __init__(self, sb):
        self.sb = sb
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.ext = f"v{self.word()}"
        self.plain = f"p{self.word()}"
        self.fake = FakeForge()
        self.checks: list = [self.check_name()]
        self.clock = Clock()
        self.launches: list = []
        for name in IDENTITY:
            os.environ.pop(name, None)
        for patcher in (
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch.object(targets, "SUPPORTED_FORGES", ("github", "gitlab")),
                mock.patch.dict(forge.IMPLEMENTATIONS, {"gitlab": self.fake}),
                mock.patch.object(ci, "gh", lambda *a, **k:
                                  subprocess.CompletedProcess(list(a), 0, "", "")),
                mock.patch.object(keychain, "token", lambda *a, **k: "tok"),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            sb.addCleanup(patcher.stop)
        sb.add_synced_origin()
        self.clones = {self.ext: make_project_repo(self.ext),
                       self.plain: make_project_repo(self.plain)}
        self.record()
        capture_out(catalog.cmd_init)

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def check_name(self) -> str:
        return (self.rng.choice(LETTERS)
                + "".join(self.rng.choice(NAME_CHARS)
                          for _ in range(self.rng.randint(2, 7)))
                + self.rng.choice(LETTERS))

    def text(self) -> str:
        """Итог или причина Оператора: случайные слова."""
        return " ".join(self.word(self.rng.randint(3, 8))
                        for _ in range(self.rng.randint(2, 5)))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def record(self, checks: list | None = None) -> None:
        """Записи двух проектов в локальном слое; у `ext` — `verify` из
        проверок `human:<имя>` (`checks`, по умолчанию текущий набор)."""
        if checks is not None:
            self.checks = list(checks)
        value = ", ".join(f"human:{n}" for n in self.checks)
        text = "targets:\n"
        text += ENTRY.format(name=self.ext, base=config.MAIN_BRANCH,
                             verify=f"      verify: [{value}]\n")
        text += ENTRY.format(name=self.plain, base=config.MAIN_BRANCH, verify="")
        local = targets.local_path()
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------ задачи

    def new_task(self, project: str | None = None, state: str = "verifying",
                 epic: str | None = None) -> str:
        """Задача проекта (по умолчанию `ext`) с коммитом кода в ветке,
        SPEC в ссылке документов и начатым шагом роли; затем вход в
        `state` записью перехода."""
        project = project or self.ext
        task = idgen.new_task_id()
        branch = f"task/{task.lower()}-{self.word()}"
        store.insert_task(self.conn, task, f"Фикстура {self.word()}", "in_dev",
                          branch, project, config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task, zones="app.py, kod/")
        if epic is not None:
            store.update_task(self.conn, task, epic_id=epic)
        wt, error = workspace.ensure(task, branch)
        assert error is None, self.note(f"рабочая копия не заведена: {error}")
        self.commit_code(task)
        docs = config.PROJECTS / project / "tasks" / task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=task), encoding="utf-8")
        capture_out(checkpoint.commit_step_artifacts, self.conn, task, "analyst")
        store.journal(self.conn, task, "developer", "agent run started",
                      "попытка 1/3")
        if state != "in_dev":
            self.move(task, state)
        return task

    def move(self, task: str, state: str, actor: str = "fsm",
             detail: str = "сценарий: переход") -> None:
        store.set_state(self.conn, task, state, actor,
                        expected_state=self.state(task), detail=detail)

    def commit_code(self, task: str) -> str:
        wt = workspace.path(task, store.task_target(self.conn, task))
        path = wt / "kod" / f"{self.word()}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"A = {self.rng.randrange(10 ** 6)}\n", encoding="utf-8")
        self.sb.git("-C", str(wt), "add", "-A")
        self.sb.git("-C", str(wt), "commit", "-q", "-m", f"код {self.word()}")
        return self.head(task)

    def head(self, task: str) -> str:
        t = store.get_task(self.conn, task)
        clone = self.clones[t["target"]]
        return self.sb.git("-C", str(clone), "rev-parse",
                           f"refs/heads/{t['branch']}").strip()

    def ci(self, task: str, verdict: str) -> None:
        self.fake.verdicts[self.head(task)] = verdict

    @contextlib.contextmanager
    def gate_waits(self):
        """Гейт по исходам не пройден: каждая привязка публичной
        `verifying_gate` в модулях пульта отвечает ожиданием."""
        original = outcome_integrity.verifying_gate
        reason = f"отчёт головы не готов: {self.word()}"

        def waiting(conn, task_id, t, state):
            return outcome_integrity.VerifyingVerdict(False, reason)

        with contextlib.ExitStack() as stack:
            for name, module in list(sys.modules.items()):
                if (name.startswith("orchestrator") and module is not None
                        and getattr(module, "verifying_gate", None) is original):
                    stack.enter_context(mock.patch.object(module, "verifying_gate",
                                                          waiting))
            yield

    # ------------------------------------------------------------ команды

    def poll(self, task: str) -> tuple:
        """Один опрос `verifying` (`fsm.cmd_advance`): (новые записи, вывод)."""
        before = len(self.rows(task))
        _code, out = capture_out(fsm.cmd_advance, task)
        return self.rows(task)[before:], out

    def cli(self, *argv) -> tuple:
        """(код отказа или None, вывод, новые записи) `artel.py <argv>`."""
        task = argv[1] if len(argv) > 1 else None
        before = len(self.rows(task)) if task else 0
        with mock.patch.object(sys, "argv", ["artel.py", *[str(a) for a in argv]]):
            code, out = capture_out(artel.main)
        rows = self.rows(task)[before:] if task else []
        return code, out, rows

    def verify_ok(self, task: str, name: str, sha: str, summary: str) -> tuple:
        return self.cli("verify-ok", task, name, sha, summary)

    def verify_fail(self, task: str, name: str, reason: str) -> tuple:
        return self.cli("verify-fail", task, name, reason)

    def task_auto(self, task: str, span: float = 3600) -> str:
        """`auto <id>` на подменённых часах; вывод."""
        self.clock.end = self.clock.t + span
        previous = signal.getsignal(signal.SIGTERM)
        try:
            with mock.patch.object(auto, "time", self.clock), \
                    mock.patch.object(store, "now", self.clock.now):
                try:
                    return capture_out(auto.cmd_auto, task)[1]
                except Halt:
                    return "(цикл auto оборван границей отрезка)"
        finally:
            signal.signal(signal.SIGTERM, previous)

    def epic_of(self, tasks: list) -> tuple:
        """Эпик проекта `ext` с задачами `tasks` и наблюдение над ними;
        (эпик, наблюдение)."""
        epic = epics.new_epic_id()
        store.insert_epic(self.conn, epic, self.ext, f"Эпик {self.word()}",
                          "Цель сценария", None)
        self.conn.commit()
        for task in tasks:
            store.update_task(self.conn, task, epic_id=epic)
        obs = store.register_observation(self.conn, self.ext, "", "",
                                         f"s-{self.word()}", list(tasks))
        return epic, obs

    def supervise(self, epic: str, obs: str, polls: int,
                  run_child: bool = True) -> str:
        """Надзор эпика (`auto.cmd_auto_epic`) на подменённых часах —
        `polls` опросов; дочерний `auto` — `auto.cmd_auto` в процессе
        теста (`run_child`), процесс — с неживым pid. Запуски — в
        `self.launches`."""

        def launch(conn, task_id, observation_id):
            self.launches.append(task_id)
            if run_child:
                saved = self.clock.end
                self.clock.end = self.clock.t + 3600
                try:
                    capture_out(auto.cmd_auto, task_id)
                except Halt:
                    pass
                finally:
                    self.clock.end = saved
            return DeadProc(DEAD_PID_BASE + self.rng.randrange(10 ** 6))

        self.clock.end = self.clock.t + polls * auto.EPIC_POLL_SEC + 1
        previous = signal.getsignal(signal.SIGTERM)
        buf = io.StringIO()
        try:
            with mock.patch.object(auto, "time", self.clock), \
                    mock.patch.object(store, "now", self.clock.now), \
                    contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                try:
                    auto.cmd_auto_epic(epic, obs, launch)
                except Halt:
                    pass
        finally:
            signal.signal(signal.SIGTERM, previous)
        return buf.getvalue()

    def watch_once(self, obs: str) -> str:
        """Один опрос `watch --observation <obs> --notify`; уведомления —
        строками «уведомление: …» (платформа без `osascript`)."""
        row = store.observation(self.conn, obs)
        buf = io.StringIO()

        def stop(_seconds):
            raise WatchDone()

        with patch_sleep(watch, stop), \
                mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": row["session_id"]}), \
                mock.patch.object(sys, "platform", "linux"), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                watch.cmd_watch(["--observation", obs, "--notify"])
            except WatchDone:
                pass
        return buf.getvalue()

    def observe(self, task: str) -> str:
        """Наблюдение над задачей; накопленное до сих пор выбрано опросом."""
        obs = store.register_observation(self.conn, store.task_target(self.conn, task),
                                         "", "", f"w-{self.word()}", [task])
        self.watch_once(obs)
        return obs

    # ------------------------------------------------------------ наблюдение

    def state(self, task: str) -> str:
        return store.get_task(self.conn, task)["state"]

    def rows(self, task: str) -> list:
        return [dict(r) for r in store.task_steps(self.conn, task)]

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.rows(task))

    def why(self, task: str, out: str = "") -> str:
        return self.note(f"проверки {self.checks}; голова {self.head(task)}\n"
                         f"--- вывод:\n{out}\n--- журнал:\n{self.journal(task)}")

    def last_entry(self, task: str) -> int:
        """Индекс последней записи входа в `verifying` в журнале задачи."""
        rows = self.rows(task)
        found = [i for i, r in enumerate(rows) if r["action"] == TO_VERIFYING]
        return found[-1] if found else -1

    @staticmethod
    def wait_matches(rows: list, name: str, sha: str) -> list:
        """Записи «ждёт проверки <name> по sha <префикс sha>» среди `rows`."""
        pattern = re.compile(rf"{WAITS} {re.escape(name)} по sha ([0-9a-f]{{7,40}})")
        found = []
        for r in rows:
            match = pattern.search(f"{r['action']} {r['detail'] or ''}")
            if match and sha.startswith(match.group(1)):
                found.append(r)
        return found

    def visit_waits(self, task: str, name: str, sha: str) -> list:
        """Записи ожидания `name` по `sha` после последнего входа в `verifying`."""
        return self.wait_matches(self.rows(task)[self.last_entry(task) + 1:],
                                 name, sha)

    def status_block(self, task: str) -> str:
        _code, out = capture_out(catalog.cmd_status)
        others = [r["id"] for r in store.all_tasks(self.conn) if r["id"] != task]
        block, inside = [], False
        for line in out.splitlines():
            if task in line:
                inside = True
            elif inside and any(o in line for o in others):
                break
            if inside:
                block.append(line)
        return "\n".join(block)

    def status_waits(self, task: str, name: str, sha: str) -> bool:
        text = self.status_block(task)
        return bool(self.wait_matches([{"action": text, "detail": ""}], name, sha))

    def waiting_on(self, task: str) -> str | None:
        model = board.build_model(self.conn, store.task_target(self.conn, task))
        cards = [c for c in model["cards"] if c["task"] == task]
        return cards[0]["waiting_on"] if cards else None

    def mark_rows(self, task: str, name: str, *values: str) -> list:
        """Строки таблиц БД, кроме журнала, значения которых содержат id
        задачи, имя проверки (`name` или `human:<name>`) и все `values`."""
        found = []
        tables = [r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            if table == JOURNAL_TABLE:
                continue
            for row in self.conn.execute(f'SELECT * FROM "{table}"'):
                cells = {str(v) for v in tuple(row) if v is not None}
                if (task in cells and (name in cells or f"human:{name}" in cells)
                        and all(v in cells for v in values)):
                    found.append((table, tuple(row)))
        return found

    def rows_with(self, table_free_text: str) -> list:
        """Строки таблиц БД, кроме журнала, где какое-то значение равно тексту."""
        found = []
        tables = [r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            if table == JOURNAL_TABLE:
                continue
            for row in self.conn.execute(f'SELECT * FROM "{table}"'):
                if table_free_text in {str(v) for v in tuple(row) if v is not None}:
                    found.append((table, tuple(row)))
        return found

    @staticmethod
    def notices(text: str, task: str) -> list:
        return [line for line in text.splitlines()
                if line.startswith("уведомление:") and task in line]

    def brief_reason(self, task: str) -> str:
        """Текст раздела «Причина возврата» брифа developer; "" — раздела нет."""
        text = brief.developer_brief(self.conn, task)
        header = f"## {brief.RETURN_REASON_HEADER}"
        start = text.find(header)
        if start == -1:
            return ""
        end = text.find(brief.RETURN_REASON_CLOSING, start)
        return text[start:end if end != -1 else len(text)]

    # ------------------------------------------------------------ сценарии

    def waiting_task(self, project: str | None = None) -> tuple:
        """Сценарий AC-4: задача `ext` в `verifying`, CI головы зелёный, гейт
        пройден, один опрос — ожидание первой проверки. (задача, голова,
        записи опроса, вывод)."""
        task = self.new_task(project)
        sha = self.head(task)
        self.ci(task, forge.GREEN)
        rows, out = self.poll(task)
        assert self.state(task) == "verifying", self.why(task, out)
        assert self.visit_waits(task, self.checks[0], sha), self.why(task, out)
        return task, sha, rows, out


@pytest.fixture
def stand(real_git):
    return Stand(real_git)


def refused(stand, task, code, out, rows, state: str, text: str | None = None) -> None:
    """Отказ команды: код выхода ненулевой, `text` в выводе, состояние
    прежнее, переходов в записях команды нет."""
    where = stand.why(task, out)
    assert code is not None, stand.note("команда не отказала\n") + where
    if text is not None:
        assert text in out, stand.note(f"отказ без «{text}»\n") + where
    assert stand.state(task) == state, where
    assert not [r for r in rows if r["action"].startswith("state -> ")], where


def mark_journal(rows: list, name: str) -> list:
    """Записи команды об отметке/возврате: называют проверку и не являются
    ни записью ожидания, ни записью перехода."""
    return [r for r in rows if name in f"{r['action']} {r['detail'] or ''}"
            and WAITS not in f"{r['action']} {r['detail'] or ''}"
            and not r["action"].startswith("state -> ")]


# ---------------------------------------------------------------- AC-3


def test_ac3_project_without_verify_goes_to_review_on_green_ci(stand):
    """Проект без поля `verify`: зелёный CI головы и пустой гейт по исходам ведут задачу из `verifying` в `review` одним опросом, как до задачи.

    Сценарий: задача проекта `plain` (запись без `verify`) в `verifying`,
    CI головы зелёный. Опрос `verifying`: задача в `review` (запись
    `state -> review`), записи «ждёт проверки» нет.

    Ловит мутацию: ожидание отметки включено для любого проекта (пустой
    `verify` читается как ожидание) — задача остаётся в `verifying` с
    записью ожидания; новая проверка поля отказывает записи без `verify` —
    опрос пишет отказ «запись проекта не прочитана» и задача в `verifying`.
    """
    task = stand.new_task(stand.plain)
    stand.ci(task, forge.GREEN)
    rows, out = stand.poll(task)
    assert stand.state(task) == "review", stand.why(task, out)
    assert TO_REVIEW in [r["action"] for r in rows], stand.why(task, out)
    assert not [r for r in rows if WAITS in f"{r['action']} {r['detail'] or ''}"], \
        stand.why(task, out)


# ---------------------------------------------------------------- AC-4


def test_ac4_green_ci_with_verify_waits_for_operator(stand):
    """Проект с `verify: [human:<имя>]`, CI головы зелёный, гейт пройден: после опроса задача в `verifying`, журнал — «ждёт проверки <имя> по sha <голова>», строка `status` — та же, `waiting_on` доски — `operator`.

    Сценарий: задача проекта `ext` (проверка со случайным именем) в
    `verifying`, CI её головы зелёный. До опроса `waiting_on` — `ci`.
    Опрос: задача в `verifying`, записи `state -> review` нет; после
    последней записи входа в `verifying` есть запись «ждёт проверки
    <имя> по sha <sha>», sha — префикс текущей головы; строка задачи в
    `status` несёт тот же текст; карточка доски — `waiting_on: operator`.

    Ловит мутацию: зелёный CI ведёт в `review` и при непустом `verify`;
    запись ожидания называет не текущую голову (sha входа) или не первую
    проверку; строка `status` не обновлена; `board.waiting_on` по-прежнему
    отдаёт `ci` для всего `verifying`.
    """
    task = stand.new_task()
    sha = stand.head(task)
    stand.ci(task, forge.GREEN)
    assert stand.waiting_on(task) == "ci", stand.why(task)
    rows, out = stand.poll(task)
    name = stand.checks[0]
    assert stand.state(task) == "verifying", stand.why(task, out)
    assert TO_REVIEW not in [r["action"] for r in rows], stand.why(task, out)
    assert stand.visit_waits(task, name, sha), stand.why(task, out)
    assert stand.status_waits(task, name, sha), stand.note(
        f"status:\n{stand.status_block(task)}\n") + stand.why(task, out)
    assert stand.waiting_on(task) == "operator", stand.why(task, out)


# ---------------------------------------------------------------- AC-5


def test_ac5_repeated_polls_do_not_repeat_record_or_notice(stand):
    """В сценарии AC-4 повторные опросы в том же визите по той же голове не добавляют второй записи «ждёт проверки» и не дают второго уведомления `watch`.

    Сценарий AC-4 под наблюдением `watch --observation --notify`
    (накопленное до входа в ожидание выбрано). Первый опрос — вход в
    ожидание, опрос `watch` выбирает его. Затем случайное число (2–5)
    опросов `verifying` и снова опрос `watch`: после последней записи
    входа в `verifying` ровно одна запись «ждёт проверки <имя> по sha
    <голова>», второй опрос `watch` не печатает ни одного уведомления,
    называющего задачу.

    Ловит мутацию: запись ожидания пишется на каждом опросе (нет сверки
    «уже было в этом визите по этой голове») — записей несколько и второе
    уведомление; признак «уже было» берётся по всему журналу, а не по
    визиту — здесь не ловится, ловит AC-13.
    """
    task = stand.new_task()
    sha = stand.head(task)
    stand.ci(task, forge.GREEN)
    obs = stand.observe(task)
    stand.poll(task)
    stand.watch_once(obs)
    out = ""
    for _ in range(stand.rng.randint(2, 5)):
        _rows, out = stand.poll(task)
    seen = stand.watch_once(obs)
    where = stand.why(task, out) + f"\n--- watch:\n{seen}"
    assert stand.state(task) == "verifying", where
    assert len(stand.visit_waits(task, stand.checks[0], sha)) == 1, where
    assert stand.notices(seen, task) == [], where


# ---------------------------------------------------------------- AC-6


def test_ac6_ceiling_does_not_apply_to_waiting(stand):
    """В сценарии AC-4 при истёкшем потолке `VERIFYING_CEILING_SEC` очередной опрос не переводит задачу ни в `review`, ни в `escalated`.

    Сценарий AC-4; затем `config.VERIFYING_CEILING_SEC` подменён нулём
    (потолок истёк с момента входа), случайное число (1–3) опросов: задача
    в `verifying`, записей `state -> review`/`state -> escalated` нет.

    Ловит мутацию: ожидание отметки идёт общим путём ожидания CI с
    потолком — эскалация «потолок ожидания CI в verifying исчерпан»;
    истечение потолка считается проходом — `review`.
    """
    task, _sha, _rows, _out = stand.waiting_task()
    actions, out = [], ""
    with mock.patch.object(config, "VERIFYING_CEILING_SEC", 0):
        for _ in range(stand.rng.randint(1, 3)):
            rows, out = stand.poll(task)
            actions += [r["action"] for r in rows]
    assert stand.state(task) == "verifying", stand.why(task, out)
    assert TO_REVIEW not in actions and TO_ESCALATED not in actions, \
        stand.why(task, out)


# ---------------------------------------------------------------- AC-7


def test_ac7_watch_notifies_on_entering_wait(stand):
    """`watch --notify` выдаёт уведомление о задаче, когда она входит в ожидание проверки.

    Сценарий: задача проекта `ext` в `verifying` под наблюдением, CI головы
    идёт — опрос `verifying` (ожидание CI) и опрос `watch`: уведомлений о
    задаче нет. CI становится зелёным — опрос `verifying` (вход в
    ожидание отметки) и опрос `watch`: хотя бы одна строка «уведомление:
    …», называющая задачу.

    Ловит мутацию: запись входа в ожидание не значима для `watch` (класс
    события не уведомляет) — уведомления нет; уведомление на каждый
    опрос CI — строка уже после первого опроса.
    """
    task = stand.new_task()
    stand.ci(task, forge.RUNNING)
    obs = stand.observe(task)
    _rows, out = stand.poll(task)
    seen = stand.watch_once(obs)
    assert stand.notices(seen, task) == [], stand.why(task, out) + f"\n--- watch:\n{seen}"
    stand.ci(task, forge.GREEN)
    _rows, out = stand.poll(task)
    seen = stand.watch_once(obs)
    where = stand.why(task, out) + f"\n--- watch:\n{seen}"
    assert stand.visit_waits(task, stand.checks[0], stand.head(task)), where
    assert stand.notices(seen, task), where


# ---------------------------------------------------------------- AC-8


def test_ac8_verify_ok_moves_waiting_task_to_review(stand):
    """`verify-ok <id> <имя> <текущий sha> "<итог>"` в сценарии AC-4 переводит задачу в `review`; отметка лежит в БД, запись — в журнале.

    Сценарий AC-4; Оператор вызывает `artel.py verify-ok` с именем
    проверки, полным sha текущей головы и случайным итогом. Код выхода 0,
    задача в `review` (запись `state -> review`); в БД строка таблицы вне
    журнала с id задачи, именем проверки, sha и итогом; в записях команды
    — запись, называющая проверку (не запись ожидания и не переход).

    Ловит мутацию: отметка не сохраняется (переход без записи в БД) или
    сохраняется без sha/итога; переход в `review` не делается после
    отметки последней проверки; запись журнала об отметке не пишется.
    """
    task, sha, _rows, _out = stand.waiting_task()
    name, summary = stand.checks[0], stand.text()
    code, out, rows = stand.verify_ok(task, name, sha, summary)
    where = stand.why(task, out)
    assert code is None, where
    assert stand.state(task) == "review", where
    assert TO_REVIEW in [r["action"] for r in rows], where
    assert stand.mark_rows(task, name, sha, summary), where
    assert mark_journal(rows, name), where


# ---------------------------------------------------------------- AC-9


@pytest.mark.parametrize("case", ["CI идёт", "CI красный", "гейт не пройден"])
def test_ac9_verify_ok_refused_before_wait(stand, case):
    """CI головы в ожидании или красный, либо CI зелёный при непройденном гейте по исходам — `verify-ok` с текущим sha отказывает «проверка не ожидается для этой головы», состояние `verifying`, отметки нет.

    Сценарий (по случаю): задача проекта `ext` в `verifying`; CI головы
    идёт, красный или зелёный при гейте по исходам, отвечающем ожиданием;
    опрос `verifying` (записи ожидания нет). `verify-ok <id> <имя> <голова>
    "<итог>"`: ненулевой код выхода, вывод несёт «проверка не ожидается
    для этой головы», задача в `verifying`, в БД нет строки с этим итогом
    и нет отметки проверки.

    Ловит мутацию: `verify-ok` проверяет только состояние и голову (без
    записи ожидания) — отметка и `review` без зелёного CI; запись ожидания
    пишется до гейта по исходам или при не зелёном CI — `verify-ok`
    проходит.
    """
    task = stand.new_task()
    sha = stand.head(task)
    name, summary = stand.checks[0], stand.text()
    stand.ci(task, {"CI идёт": forge.RUNNING, "CI красный": forge.RED}.get(
        case, forge.GREEN))
    with stand.gate_waits() if case == "гейт не пройден" else contextlib.nullcontext():
        _rows, out = stand.poll(task)
    assert stand.state(task) == "verifying", stand.why(task, out)
    code, out, rows = stand.verify_ok(task, name, sha, summary)
    refused(stand, task, code, out, rows, "verifying", NOT_EXPECTED)
    assert stand.rows_with(summary) == [], stand.why(task, out)
    assert stand.mark_rows(task, name) == [], stand.why(task, out)


# ---------------------------------------------------------------- AC-10


@pytest.mark.parametrize("case", ["старый sha", "задача в in_dev",
                                  "задача в review", "имени нет в профиле",
                                  "пустой итог"])
def test_ac10_verify_ok_preconditions_refuse(stand, case):
    """`verify-ok` со старым sha («отметка для другой головы»), для задачи не в `verifying`, для имени вне профиля и с пустым итогом — отказ, состояние прежнее, отметки нет.

    Сценарий: задача в ожидании отметки (AC-4), голова — второй коммит
    ветки. По случаю: (а) sha — предыдущий коммит ветки: отказ с текстом
    «отметка для другой головы», задача в `verifying`; (б), (в) задача
    переведена в `in_dev`/`review`: отказ, состояние прежнее; (г) имя —
    случайное, которого нет в профиле: отказ, `verifying`; (д) итог —
    пустая строка: отказ, `verifying`. Во всех случаях — ненулевой код
    выхода, переходов нет, отметки проверки в БД нет.

    Ловит мутацию: sha не сверяется с текущей головой (или сверяется с
    sha входа в `verifying`) — отметка по старой голове; команда не
    проверяет состояние — отметка у задачи вне `verifying`; имя не
    сверяется с профилем — `review` по чужому имени; пустой итог принят.
    """
    task = stand.new_task()
    old = stand.head(task)
    stand.commit_code(task)
    sha = stand.head(task)
    stand.ci(task, forge.GREEN)
    _rows, out = stand.poll(task)
    name, summary = stand.checks[0], stand.text()
    assert stand.visit_waits(task, name, sha), stand.why(task, out)
    state, text = "verifying", None
    if case == "старый sha":
        sha, text = old, OTHER_HEAD
    elif case.startswith("задача в "):
        state = case.split(" ")[-1]
        stand.move(task, state)
    elif case == "имени нет в профиле":
        name = stand.check_name() + "x"
    else:
        summary = ""
    code, out, rows = stand.verify_ok(task, name, sha, summary)
    refused(stand, task, code, out, rows, state, text)
    assert stand.mark_rows(task, stand.checks[0]) == [], stand.why(task, out)
    assert stand.mark_rows(task, name) == [], stand.why(task, out)


# ---------------------------------------------------------------- AC-11


def test_ac11_status_names_next_unmarked_check(stand):
    """Профиль из двух проверок: после `verify-ok` первой задача в `verifying`, строка `status` — «ждёт проверки <вторая> по sha <голова>»; после `verify-ok` второй — `review`.

    Сценарий: запись `ext` с `verify: [human:<a>, human:<b>]` (случайные
    различные имена); задача в `verifying`, CI зелёный, опрос — ожидание
    `a`. `verify-ok` по `a`: код 0, задача в `verifying`, строка `status`
    — «ждёт проверки b по sha <голова>» и не называет ожидание `a`.
    `verify-ok` по `b`: код 0, задача в `review`.

    Ловит мутацию: `review` после первой же отметки (не все проверки
    профиля); строка `status` после отметки не пересчитывается (по-прежнему
    `a`); отметка второй проверки отказывает (запись ожидания несёт имя
    `a`, а основанием сочтена только для `a`).
    """
    first, second = stand.check_name(), stand.check_name()
    while second == first:
        second = stand.check_name()
    stand.record([first, second])
    task, sha, _rows, _out = stand.waiting_task()
    code, out, _r = stand.verify_ok(task, first, sha, stand.text())
    where = stand.why(task, out) + f"\n--- status:\n{stand.status_block(task)}"
    assert code is None, where
    assert stand.state(task) == "verifying", where
    assert stand.status_waits(task, second, sha), where
    assert not stand.status_waits(task, first, sha), where
    code, out, _r = stand.verify_ok(task, second, sha, stand.text())
    assert code is None, stand.why(task, out)
    assert stand.state(task) == "review", stand.why(task, out)


# ---------------------------------------------------------------- AC-12


def test_ac12_mark_holds_only_for_its_head(stand):
    """Отметка по голове X не действует после новой головы Y: новое ожидание «ждёт проверки <имя> по sha Y», `review` только после отметки по Y.

    Сценарий AC-4 с головой X; `verify-ok` по X — `review`. Задача
    возвращена в `in_dev`, новый коммит — голова Y, снова `verifying`, CI
    Y зелёный. Опрос: задача в `verifying`, запись «ждёт проверки <имя>
    по sha Y» после последнего входа; ещё случайное число опросов — не
    `review`; `verify-ok` с X — отказ «отметка для другой головы»;
    `verify-ok` с Y — `review`.

    Ловит мутацию: отметка ищется по задаче и имени без sha — опрос с
    головой Y ведёт в `review` по отметке X; голова сверяется с sha
    отметки, а не с текущей — `verify-ok` с X проходит.
    """
    task, old, _rows, _out = stand.waiting_task()
    name = stand.checks[0]
    code, out, _r = stand.verify_ok(task, name, old, stand.text())
    assert code is None and stand.state(task) == "review", stand.why(task, out)
    stand.move(task, "in_dev", detail="замечания ревью, итерация 1")
    new = stand.commit_code(task)
    stand.move(task, "verifying")
    stand.ci(task, forge.GREEN)
    actions = []
    for _ in range(stand.rng.randint(2, 4)):
        rows, out = stand.poll(task)
        actions += [r["action"] for r in rows]
    where = stand.why(task, out)
    assert stand.state(task) == "verifying", where
    assert TO_REVIEW not in actions, where
    assert stand.visit_waits(task, name, new), where
    code, out, rows = stand.verify_ok(task, name, old, stand.text())
    refused(stand, task, code, out, rows, "verifying", OTHER_HEAD)
    code, out, _r = stand.verify_ok(task, name, new, stand.text())
    assert code is None and stand.state(task) == "review", stand.why(task, out)


# ---------------------------------------------------------------- AC-13


def test_ac13_same_head_new_visit_needs_new_wait(stand):
    """Новый визит `verifying` с той же головой X после `verify-fail`: прошлое ожидание основанием не служит — до зелёного CI и прохода гейта в этом визите `verify-ok` отказывает, после них — новая запись ожидания, новое уведомление и только затем `review`.

    Сценарий AC-4 под наблюдением `watch --notify` (голова X, запись
    ожидания есть, уведомление выбрано). `verify-fail` — `in_dev`; снова
    вход в `verifying` без новых коммитов (голова X). (1) CI X идёт —
    опрос; `verify-ok` по X отказывает «проверка не ожидается для этой
    головы», отметки с этим итогом нет, `verifying`. (2) CI X зелёный, гейт
    по исходам отвечает ожиданием — опрос; `verify-ok` снова отказывает
    тем же текстом. (3) Гейт пройден — опрос: после записи входа в этот
    визит — запись «ждёт проверки <имя> по sha X», опрос `watch` печатает
    уведомление о задаче; `verify-ok` по X — код 0, `review`.

    Ловит мутацию: основание `verify-ok` ищется по всему журналу, а не
    после последнего входа в `verifying` — отказа в (1)/(2) нет; признак
    «уже было» для записи ожидания — по голове без визита — в (3) новой
    записи и уведомления нет.
    """
    task, sha, _rows, _out = stand.waiting_task()
    name = stand.checks[0]
    obs = stand.observe(task)
    code, out, _r = stand.verify_fail(task, name, stand.text())
    assert code is None and stand.state(task) == "in_dev", stand.why(task, out)
    stand.move(task, "verifying")
    assert stand.head(task) == sha, stand.why(task)
    stand.watch_once(obs)
    for step in ("CI идёт", "гейт не пройден"):
        stand.ci(task, forge.RUNNING if step == "CI идёт" else forge.GREEN)
        with stand.gate_waits() if step == "гейт не пройден" else contextlib.nullcontext():
            _rows, out = stand.poll(task)
        summary = stand.text()
        code, out, rows = stand.verify_ok(task, name, sha, summary)
        refused(stand, task, code, out, rows, "verifying", NOT_EXPECTED)
        assert stand.rows_with(summary) == [], stand.note(f"{step}\n") + stand.why(task, out)
        assert stand.visit_waits(task, name, sha) == [], stand.note(f"{step}\n") + stand.why(task, out)
    _rows, out = stand.poll(task)
    seen = stand.watch_once(obs)
    where = stand.why(task, out) + f"\n--- watch:\n{seen}"
    assert len(stand.visit_waits(task, name, sha)) == 1, where
    assert stand.notices(seen, task), where
    code, out, _r = stand.verify_ok(task, name, sha, stand.text())
    assert code is None and stand.state(task) == "review", stand.why(task, out)


# ---------------------------------------------------------------- AC-14


@pytest.mark.parametrize("case", ["возврат", "задача в in_dev", "задача в review",
                                  "имени нет в профиле", "пустая причина"])
def test_ac14_verify_fail_returns_to_in_dev_with_reason(stand, case):
    """`verify-fail <id> <имя> "<причина>"` из `verifying` — `in_dev`, причина в журнале и в разделе «Причина возврата» брифа developer, `review_iters` прежний; вне `verifying`, с чужим именем или пустой причиной — отказ, состояние прежнее.

    Сценарий: задача в ожидании отметки (AC-4), `review_iters` — случайное
    0…`LIMIT_REVIEW_ITERS`−2. (а) `verify-fail` со случайной причиной: код
    0, задача в `in_dev` (запись `state -> in_dev`), причина — в записи
    команды, в разделе «Причина возврата» брифа `developer`, `review_iters`
    не изменился. (б), (в) задача в `in_dev`/`review`: отказ, состояние
    прежнее. (г) имя вне профиля, (д) пустая причина: отказ, `verifying`.

    Ловит мутацию: возврат пишет причину только в журнал команды, а не в
    запись перехода (бриф без причины); `verify-fail` идёт механизмом
    ревью и увеличивает `review_iters`; пустая причина или чужое имя
    приняты; команда возвращает задачу из любого состояния.
    """
    task, _sha, _rows, _out = stand.waiting_task()
    iters = stand.rng.randint(0, max(config.LIMIT_REVIEW_ITERS - 2, 0))
    store.update_task(stand.conn, task, review_iters=iters)
    name, reason = stand.checks[0], stand.text()
    if case == "возврат":
        code, out, rows = stand.verify_fail(task, name, reason)
        where = stand.why(task, out)
        assert code is None, where
        assert stand.state(task) == "in_dev", where
        assert TO_IN_DEV in [r["action"] for r in rows], where
        assert any(reason in f"{r['action']} {r['detail'] or ''}" for r in rows), where
        assert reason in stand.brief_reason(task), stand.note(
            f"раздел: {stand.brief_reason(task)!r}\n") + where
        assert store.get_task(stand.conn, task)["review_iters"] == iters, where
        return
    state = "verifying"
    if case.startswith("задача в "):
        state = case.split(" ")[-1]
        stand.move(task, state)
    elif case == "имени нет в профиле":
        name = stand.check_name() + "x"
    else:
        reason = ""
    code, out, rows = stand.verify_fail(task, name, reason)
    refused(stand, task, code, out, rows, state)


# ---------------------------------------------------------------- AC-15


def test_ac15_verify_fail_limit_escalates_and_counter_survives(stand):
    """Возврат `verify-fail`, доводящий его счётчик до `LIMIT_REVIEW_ITERS`, — `escalated` с причиной в записи перехода и в брифе после возврата из эскалации; счётчик эскалацией не сбрасывается — следующий `verify-fail` снова эскалирует.

    Сценарий: задача проекта `ext` в `verifying`; `LIMIT_REVIEW_ITERS`
    раз подряд `verify-fail` со своей случайной причиной, между ними —
    снова вход в `verifying`. Первые `LIMIT_REVIEW_ITERS`−1 — `in_dev`;
    последний — `escalated`, текст записи `state -> escalated` содержит
    его причину. Возврат из эскалации в `in_dev` (запись перехода
    Оператора): раздел «Причина возврата» брифа developer несёт ту же
    причину. Снова `verifying`, `verify-fail` с новой причиной —
    `escalated`. `review_iters` за весь сценарий не изменился.

    Ловит мутацию: предела у `verify-fail` нет (каждый — `in_dev`);
    предел сравнивается строго больше (`escalated` на шаг позже); счётчик
    — `review_iters` или обнуляется при эскалации/возврате (после возврата
    `verify-fail` даёт `in_dev`); запись эскалации без причины («лимит
    исчерпан») — бриф её не несёт.
    """
    task = stand.new_task()
    name = stand.checks[0]
    iters = store.get_task(stand.conn, task)["review_iters"]
    limit = config.LIMIT_REVIEW_ITERS
    for i in range(1, limit + 1):
        if stand.state(task) != "verifying":
            stand.move(task, "verifying")
        reason = stand.text()
        code, out, rows = stand.verify_fail(task, name, reason)
        where = stand.note(f"возврат {i}/{limit}\n") + stand.why(task, out)
        assert code is None, where
        expected = "escalated" if i == limit else "in_dev"
        assert stand.state(task) == expected, where
    escalations = [r for r in rows if r["action"] == TO_ESCALATED]
    assert escalations and reason in (escalations[-1]["detail"] or ""), where
    stand.move(task, "in_dev", actor="operator", detail="эскалация разрешена, продолжаем")
    section = stand.brief_reason(task)
    assert reason in section, stand.note(f"раздел: {section!r}\n") + where
    stand.move(task, "verifying")
    again = stand.text()
    code, out, rows = stand.verify_fail(task, name, again)
    where = stand.why(task, out)
    assert code is None, where
    assert stand.state(task) == "escalated", where
    assert store.get_task(stand.conn, task)["review_iters"] == iters, where


# ---------------------------------------------------------------- AC-16


def open_task_alerts(stand, task: str) -> list:
    return [a for a in alerts.open_alerts(stand.conn)
            if a["target"] == task or task in (a["message"] or "")]


def test_ac16_auto_stops_on_wait_without_alert_and_releases_lease(stand):
    """`auto <id>` на задаче в ожидании отметки останавливается: запись остановки, открытого алерта нет, lease снят; задача в `verifying`.

    Сценарий AC-4; `auto <id>` на подменённых часах с отрезком в час
    опросов. Вывод и журнал: запись `AUTO_STOPPED_ACTION` за прогон; в
    открытых алертах нет ни одного по задаче; строки lease задачи нет;
    задача в `verifying`.

    Ловит мутацию: ожидание отметки — исход «проверки идут»: `auto` спит
    и опрашивает до границы отрезка (записи остановки нет); остановка
    с алертом (как на красном CI); lease не снят на этом выходе.
    """
    task, _sha, _rows, _out = stand.waiting_task()
    before = len(stand.rows(task))
    out = stand.task_auto(task)
    rows = stand.rows(task)[before:]
    where = stand.why(task, out)
    assert zone_lock.AUTO_STOPPED_ACTION in [r["action"] for r in rows], where
    assert open_task_alerts(stand, task) == [], where
    assert store.lease_row(stand.conn, task) is None, where
    assert stand.state(task) == "verifying", where


@pytest.mark.parametrize("history", ["без дочернего", "после остановки и budget"])
def test_ac16_epic_supervisor_treats_wait_as_operator_wait(stand, history):
    """Надзор эпика не запускает дочерний `auto` задаче в ожидании отметки и считает её ждущей Оператора: надзор живёт, не завершается.

    Сценарий AC-4 для задачи эпика проекта `ext` (шаг роли начат). По
    случаю: (а) дочернего `auto` у задачи не было; (б) перед надзором
    `auto <id>` остановился на ожидании, затем Оператор поднял бюджет
    (`budget`) — действие Оператора, которое снимает удержание после
    остановки не на гейте. Надзор — случайное число (4–8) опросов: ни
    одного запуска дочернего `auto` задаче; в журнале эпика нет записи
    самостоятельного завершения надзора; задача в `verifying`.

    Ловит мутацию: ожидание отметки не отличается от `verifying` с
    готовой задачей — надзор запускает дочерний `auto` (а); ожидание
    считается остановкой «не на гейте» — после действия Оператора задача
    перезапускается (б); задача в ожидании считается заблокированной —
    надзор завершается сам.
    """
    task, _sha, _rows, _out = stand.waiting_task()
    if history != "без дочернего":
        stand.task_auto(task)
        code, out = capture_out(budget.cmd_budget, task, "77")
        assert code is None, stand.why(task, out)
    epic, obs = stand.epic_of([task])
    out = stand.supervise(epic, obs, stand.rng.randint(4, 8))
    where = stand.why(task, out) + f"\nзапуски: {stand.launches}"
    assert task not in stand.launches, where
    ends = [r for r in store.task_steps(stand.conn, epic)
            if r["action"] == auto.EPIC_SUPERVISOR_END_ACTION]
    assert ends == [], where
    assert stand.state(task) == "verifying", where


# ---------------------------------------------------------------- AC-17


@pytest.mark.parametrize("project", ["с verify", "без verify"])
def test_ac17_red_ci_child_stop_still_holds_task(stand, project):
    """Задача эпика в `verifying` с красным CI головы: дочерний `auto` останавливается, надзор на следующих опросах её удерживает и не перезапускает — и у проекта с `verify`, и без него.

    Сценарий: задача эпика проекта `ext` либо `plain` в `verifying`, CI
    головы красный, шаг роли начат. Надзор: первый опрос запускает
    дочерний `auto` (исполняется в процессе теста и останавливается на
    красном CI, процесс не жив); следующие опросы (всего 5–9) — второго
    запуска нет; в журнале задачи есть запись остановки `auto` на
    `verifying`; задача в `verifying`.

    Ловит мутацию: признак «не удерживает место» распространён на всё
    `verifying` (`verifying` в перечне состояний остановки без удержания)
    — надзор перезапускает задачу с красным CI на следующем опросе;
    красный CI у проекта с `verify` принят за ожидание отметки — `auto`
    не останавливается с алертом или надзор перезапускает.
    """
    task = stand.new_task(stand.ext if project == "с verify" else stand.plain)
    stand.ci(task, forge.RED)
    epic, obs = stand.epic_of([task])
    out = stand.supervise(epic, obs, stand.rng.randint(5, 9))
    where = stand.why(task, out) + f"\nзапуски: {stand.launches}"
    assert stand.launches.count(task) == 1, where
    stops = [r for r in stand.rows(task)
             if r["action"] == zone_lock.AUTO_STOPPED_ACTION
             and (r["detail"] or "").startswith("verifying")]
    assert stops, where
    assert stand.state(task) == "verifying", where


# ---------------------------------------------------------------- AC-18


@pytest.mark.parametrize("command", ["verify-ok", "verify-fail"])
def test_ac18_supervisor_relaunches_after_operator_mark(stand, command):
    """После `verify-ok`, переведшего задачу эпика в `review`, и после `verify-fail`, вернувшего её в `in_dev`, надзор на следующем опросе запускает ей дочерний `auto`.

    Сценарий AC-4 для задачи эпика: надзор (4–6 опросов) задачу не
    запускает. Оператор: `verify-ok` с текущей головой (задача в `review`)
    либо `verify-fail` со случайной причиной (задача в `in_dev`). Надзор
    снова: дочерний `auto` задачи запущен (без исполнения цикла).

    Ловит мутацию: признак «ждёт Оператора» держится по записи ожидания
    из прошлого визита (не по текущему состоянию) — после команды задача
    не запускается; после остановки на ожидании надзор требует ещё
    `epic retry`.
    """
    task, sha, _rows, _out = stand.waiting_task()
    epic, obs = stand.epic_of([task])
    out = stand.supervise(epic, obs, stand.rng.randint(4, 6))
    assert task not in stand.launches, stand.why(task, out)
    if command == "verify-ok":
        code, out, _r = stand.verify_ok(task, stand.checks[0], sha, stand.text())
        expected = "review"
    else:
        code, out, _r = stand.verify_fail(task, stand.checks[0], stand.text())
        expected = "in_dev"
    assert code is None and stand.state(task) == expected, stand.why(task, out)
    out = stand.supervise(epic, obs, 2, run_child=False)
    assert task in stand.launches, stand.why(task, out) + f"\nзапуски: {stand.launches}"


# ---------------------------------------------------------------- AC-19


@pytest.mark.parametrize("case", ["ожидание отметки", "красный CI"])
def test_ac19_auto_and_supervisor_never_mark_or_return(stand, case):
    """Исход, не вызовы: после `auto <id>` и надзора эпика на задаче в ожидании отметки и на задаче с красным CI в БД нет отметок проверок, в журнале — записей отметки или возврата, задача не покинула `verifying`.

    Сценарий (по случаю): задача эпика проекта `ext` в ожидании отметки
    (AC-4) либо в `verifying` с красным CI. Запомнены отметки проверки в
    БД и длина журнала; затем `auto <id>` и надзор эпика (4–8 опросов,
    дочерний `auto` исполняется в процессе теста). После: отметок
    проверки в БД столько же (ни одной); среди новых записей нет записей,
    называющих проверку (кроме записей ожидания), нет `state -> review`,
    `state -> in_dev`; задача в `verifying`.

    Ловит мутацию: `auto` или надзор, увидев ожидание, «помогает» —
    вызывает отметку (`review` и строка отметки) или возврат (`in_dev` и
    запись с причиной); дочерний `auto` проходит гейт ожидания как
    обычный `advance`.
    """
    if case == "ожидание отметки":
        task, _sha, _rows, _out = stand.waiting_task()
    else:
        task = stand.new_task()
        stand.ci(task, forge.RED)
    name = stand.checks[0]
    marks = stand.mark_rows(task, name)
    before = len(stand.rows(task))
    out = stand.task_auto(task)
    epic, obs = stand.epic_of([task])
    out += stand.supervise(epic, obs, stand.rng.randint(4, 8))
    rows = stand.rows(task)[before:]
    where = stand.why(task, out) + f"\nзапуски: {stand.launches}"
    assert stand.mark_rows(task, name) == marks == [], where
    assert mark_journal(rows, name) == [], where
    actions = [r["action"] for r in rows]
    assert TO_REVIEW not in actions and TO_IN_DEV not in actions, where
    assert stand.state(task) == "verifying", where
