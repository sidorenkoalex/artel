"""Мерж не ждёт CI main под замком: цвет новой головы main читается после
мержа один раз, идущий CI main дожидается следующий мерж (ADR-0031, этап 2).

Группа: долгоживущий

Красен до реализации: после мержа `_await_main_ci` опрашивает CI новой головы с паузами до 18 минут и не пишет «цвет сверит следующий мерж», а следующий мерж при идущем CI main проходит без ожидания, без досылки документов и без отказа «не завершён».

Зелёным и до реализации остаётся метод AC-6 (сбой `gh` — прежний проход):
он держит прежнее поведение.

Песочница — настоящий git (`real_git`, `tests/fixtures.py`): главная копия
пульта с копией `orchestrator/` и `scripts/` репозитория (гейт мержа зовёт
`scripts/guard.py` дерева мержа), bare `origin`. Задача на `merge_gate` —
кодовая ветка от origin/main, опубликованная в origin, и ссылка документов,
которую заводит строка паспорта перехода `merge_gate -> merge_gate`
(`store.set_state`). Команды зовутся диспетчером `artel.main()` тем же
argv, что набирает Оператор.

Цвет CI main — подменённый `ci.main_line_status`: сценарий задаёт по sha
очередь исходов (зелёный, красный, идёт, неизвестен; последний повторяется),
коммиту вне сценария (новая голова после мержа) достаётся своя копия
очереди «по умолчанию»; каждое чтение записывается с sha и подставным
временем. CI ветки задачи — подменённый `ci.branch_status` той же формой.
Подставной `gh` в начале `PATH` страхует от сети. Часы (`time.monotonic`,
`time.time`) подставные, их двигает только подставная пауза модулей пульта
(`patch_pult_sleep`); пауза падает, когда сумма пауз превысила тройной
`MAIN_CI_WAIT_LIMIT_SEC`, — красная фаза не крутит цикл ожидания вечно.

Число опросов «идёт», запаздывание часов до `approve`, имена проверок и
основание `--fixes-main` выбираются случайно; зерно печатается и входит в
текст провала.
"""
import contextlib
import io
import os
import random
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import artel, catalog, ci, config, fsm_merge_gate, store
from orchestrator.advance_gates import outcome_integrity
from tests.sandbox import ARTEL_TEST_PROFILE, capture, patch_pult_sleep

REPO = Path(__file__).resolve().parent.parent
HEX = re.compile(r"[0-9a-f]{7,40}")
# Верхняя граница окна отказа «не завершён» (AC-4): 20 подставных минут.
WAIT_MAX_SEC = 20 * 60
# Запись о начале ожидания называет ожидание.
WAIT_WORD = re.compile(r"ожида|жд[её]т|дожида", re.IGNORECASE)

# Подставной `gh`: проверки любого коммита зелёные, `run list` пуст. Цвет
# CI сценарии задают подменой `ci`, этот `gh` — только страховка от сети.
FAKE_GH = r'''
import json, re, sys
joined = " ".join(sys.argv[1:])
if re.search(r"commits/[0-9a-fA-F]{7,40}/check-runs", joined):
    runs = [{"name": "tests", "status": "completed", "conclusion": "success"}]
    print(json.dumps({"total_count": 1, "check_runs": runs}))
    sys.exit(0)
if sys.argv[1:3] == ["run", "list"]:
    print("[]")
    sys.exit(0)
sys.stderr.write("gh песочницы: вызов не поддержан: " + joined + "\n")
sys.exit(1)
'''


def names_commit(text: str, sha: str) -> bool:
    """Текст называет коммит `sha` — его префиксом от 7 символов."""
    return any(sha.startswith(token) for token in HEX.findall(text))


def is_green_text(text: str) -> bool:
    return "зелён" in text and "не зелён" not in text and "красн" not in text


class MergeEnv:
    """Песочница сценария поверх экземпляра `RealGitSandbox`."""

    def __init__(self, sb):
        self.sb = sb
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.check = f"тесты кода {self.rng.randrange(1000, 9999)}"
        self.clock = 0.0
        self.sleeps: list[tuple[float, float]] = []  # (пауза, часы после)
        self.main_script: dict[str, list[str]] = {}
        self.main_default = ["green"]
        self.main_calls: list[tuple[str, str, float]] = []  # (sha, исход, часы)
        self.on_main_read = None
        self.branch_script = [True]
        self.branch_calls = 0

    # ------------------------------------------------------------ устройство

    def setup(self) -> None:
        sb = self.sb
        root = sb.root
        for name in ("orchestrator", "scripts"):
            shutil.copytree(REPO / name, root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        config.TARGETS.write_text(
            "targets:\n"
            "  artel:\n"
            "    forge: github\n"
            "    url: http://localhost/artel\n"
            f"    base: {config.MAIN_BRANCH}\n"
            "    token_slot: artel-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n"
            + ARTEL_TEST_PROFILE, encoding="utf-8")
        sb.git("add", "-A")
        sb.git("commit", "-q", "-m", "код пульта")
        self.base_sha = sb.git("rev-parse", "HEAD").strip()
        self.origin = sb.add_synced_origin()
        capture(catalog.cmd_init)
        self.conn = store.db()

        bindir = root / ".artel" / "fake-bin"
        bindir.mkdir(parents=True, exist_ok=True)
        gh = bindir / "gh"
        gh.write_text(f"#!{sys.executable}\n{FAKE_GH}", encoding="utf-8")
        gh.chmod(0o755)
        base_mono, base_wall = time.monotonic(), time.time()
        patchers = [
            mock.patch.dict(os.environ, {
                "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}),
            mock.patch("time.monotonic", side_effect=lambda: base_mono + self.clock),
            mock.patch("time.time", side_effect=lambda: base_wall + self.clock),
            mock.patch.object(ci, "main_line_status", side_effect=self.main_status),
            mock.patch.object(ci, "branch_status", side_effect=self.branch_status),
        ]
        for patcher in patchers:
            patcher.start()
            sb.addCleanup(patcher.stop)
        sb.addCleanup(patch_pult_sleep(self.fake_sleep).close)

    def fake_sleep(self, seconds) -> None:
        self.clock += float(seconds)
        self.sleeps.append((float(seconds), self.clock))
        if sum(s for s, _ in self.sleeps) > 3 * fsm_merge_gate.MAIN_CI_WAIT_LIMIT_SEC:
            raise AssertionError(self.msg("ожидание не кончается"))

    # ------------------------------------------------------------- CI

    def status(self, sha: str, kind: str):
        short = sha[:8]
        if kind == "green":
            return ci.MainLineStatus(ci.MAIN_GREEN, sha, [], [], "",
                                     f"CI main {short}: зелёный, проверок 2")
        if kind == "red":
            return ci.MainLineStatus(
                ci.MAIN_RED, sha, [(self.check, "failure", sha)], [], sha,
                f"CI main красный: {self.check} (failure) на {short}")
        if kind == "running":
            return ci.MainLineStatus(ci.MAIN_RUNNING, sha, [],
                                     [(self.check, sha)], "",
                                     f"CI main {short}: идёт — {self.check}")
        return ci.MainLineStatus(ci.MAIN_UNKNOWN, sha, [], [], "",
                                 f"статус CI коммита {short} неизвестен: "
                                 f"gh не ответил")

    def main_status(self, sha, repo=None):
        key = next((k for k in self.main_script
                    if k.startswith(sha) or sha.startswith(k)), None)
        if key is None:
            key = sha
            self.main_script[key] = list(self.main_default)
        queue = self.main_script[key]
        kind = queue.pop(0) if len(queue) > 1 else queue[0]
        self.main_calls.append((key, kind, self.clock))
        if self.on_main_read is not None:
            self.on_main_read(key)
        return self.status(key, kind)

    def branch_status(self, branch, repo=None):
        self.branch_calls += 1
        queue = self.branch_script
        green = queue.pop(0) if len(queue) > 1 else queue[0]
        if green:
            return True, "CI ветки: все проверки прошли"
        return False, "CI ветки ещё идёт"

    def reads(self, sha: str) -> list:
        """Чтения цвета CI main для `sha` по порядку: (исход, часы)."""
        return [(kind, at) for key, kind, at in self.main_calls if key == sha]

    # ------------------------------------------------------------- git

    def origin_main(self) -> str:
        return self.sb.git("-C", str(self.origin), "rev-parse",
                           f"refs/heads/{config.MAIN_BRANCH}").strip()

    def docs_ref_lags(self, task: str) -> bool:
        """Ссылка документов задачи в origin не равна локальной."""
        ref = f"refs/artifacts/{task}"
        local = self.sb.git("for-each-ref", "--format=%(objectname)", ref).strip()
        listed = self.sb.git("ls-remote", str(self.origin), ref).split()
        return (listed[0] if listed else "") != local

    def make_task(self) -> dict:
        """Задача на `merge_gate`: кодовая ветка от origin/main (свежая,
        опубликована) и ссылка документов, отправленная в origin."""
        sb = self.sb
        task = f"01T{self.rng.randrange(1 << 100):022X}"[:26]
        branch = f"task/{task.lower()}-x"
        sb.git("fetch", "-q", "origin")
        sb.git("checkout", "-q", "-b", branch, f"origin/{config.MAIN_BRANCH}")
        code = f"zadacha_{task.lower()}.py"
        (sb.root / code).write_text("VALUE = 1\n", encoding="utf-8")
        sb.git("add", code)
        sb.git("commit", "-q", "-m", f"{task}: код")
        head = sb.git("rev-parse", "HEAD").strip()
        sb.git("push", "-q", "-u", "origin", branch)
        sb.git("checkout", "-q", config.MAIN_BRANCH)
        store.insert_task(self.conn, task, f"Задача {task}", "merge_gate",
                          branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        # Строка паспорта перехода — первый коммит ссылки документов;
        # вне команды пульта узел записи сразу отправляет её в origin.
        capture(passport_commit, self.conn, task)
        return {"id": task, "branch": branch, "head": head,
                "fixed": store.get_task(self.conn, task)["fixed_sha"]}

    # ---------------------------------------------------------- команды

    def cli(self, *argv: str) -> tuple[bool, str]:
        """(успех, stdout + текст отказа) команды `artel.py <argv>`."""
        out = io.StringIO()
        ok, tail = True, ""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    ok, tail = False, f"\n{exc.code}"
        return ok, out.getvalue() + tail

    def state_of(self, task: dict) -> str:
        return store.get_task(self.conn, task["id"])["state"]

    def journal(self, task: dict) -> list:
        """Записи журнала задачи: «действие | подробность»."""
        return [f"{row['action']} | {row['detail'] or ''}"
                for row in store.task_steps(self.conn, task["id"])]

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"


@pytest.fixture
def env(real_git):
    """Песочница мержа артели: главная копия, bare origin, подменённый CI."""
    e = MergeEnv(real_git)
    e.setup()
    return e


def passport_commit(conn, task_id: str) -> None:
    """Переход `merge_gate -> merge_gate`: строка паспорта — новый коммит
    ссылки документов (внутри команды пульта — недосланный)."""
    store.set_state(conn, task_id, "merge_gate", "песочница",
                    expected_state="merge_gate")


# --------------------------------------------------------------------- AC-1

def test_ac1_after_merge_reads_new_head_once_without_pause(env):
    """Мерж артели при зелёном CI прежней головы; CI новой головы main идёт.

    Голова после мержа опрошена ровно один раз, подставная пауза не вызвана
    ни разу, запись «CI main после мержа» называет «идёт — цвет сверит
    следующий мерж», замок мержа артели освобождён, задача в `done`.

    Ловит мутацию: в `_await_main_ci` оставлен опрос с паузой до предела —
    новая голова опрошена много раз, пауза вызвана, запись называет «не
    дождался за 18 мин» вместо «цвет сверит следующий мерж».
    """
    env.main_script[env.base_sha] = ["green"]
    env.main_default = ["running"]
    task = env.make_task()

    ok, out = env.cli("approve", task["id"])
    new_head = env.origin_main()

    assert env.state_of(task) == "done", env.msg(out)
    assert new_head != env.base_sha, env.msg(out)
    assert len(env.reads(new_head)) == 1, env.msg(
        f"чтений CI новой головы {new_head[:8]}: {env.reads(new_head)}")
    assert env.sleeps == [], env.msg(f"паузы после мержа: {env.sleeps}")
    action = fsm_merge_gate.MAIN_CI_AFTER_MERGE_ACTION
    records = [r for r in env.journal(task) if r.startswith(f"{action} |")]
    assert [r for r in records if "идёт — цвет сверит следующий мерж" in r], \
        env.msg(f"записи «{action}»: {records}")
    assert store.project_merge_lock_row(env.conn, config.DEFAULT_TARGET) is None, \
        env.msg("замок мержа не освобождён")


# --------------------------------------------------------------------- AC-2

def test_ac2_next_merge_waits_running_main_until_green(env):
    """CI головы main (прежней, на которую ляжет мерж) k раз «идёт» (k от 2
    до 4), затем зелёный; `approve` задачи на `merge_gate`.

    Мерж дожидается зелёного и проходит: голова main опрошена k+1 раз,
    подставная пауза вызвана k раз; в журнале задачи — запись начала
    ожидания с sha головы main и после неё запись исхода с тем же sha,
    называющая зелёный.

    Ловит мутацию: «одна пауза, затем проход при любом цвете» — голова
    опрошена 2 раза вместо k+1, пауза одна; «идущий CI — проход без
    ожидания» — опрос один, пауз нет, записей начала и исхода ожидания нет.
    """
    k = env.rng.randint(2, 4)
    env.main_script[env.base_sha] = ["running"] * k + ["green"]
    task = env.make_task()

    ok, out = env.cli("approve", task["id"])

    assert ok and env.state_of(task) == "done", env.msg(f"k={k}: {out}")
    assert len(env.reads(env.base_sha)) == k + 1, env.msg(
        f"k={k}: чтения головы main {env.reads(env.base_sha)}")
    assert len(env.sleeps) == k, env.msg(f"k={k}: паузы {env.sleeps}")
    rows = env.journal(task)
    starts = [i for i, r in enumerate(rows)
              if names_commit(r, env.base_sha) and WAIT_WORD.search(r)]
    outcomes = [i for i, r in enumerate(rows)
                if names_commit(r, env.base_sha) and is_green_text(r)]
    assert any(o > s for s in starts for o in outcomes), env.msg(
        f"k={k}: нет начала и зелёного исхода ожидания с "
        f"{env.base_sha[:8]}: {rows}")


# --------------------------------------------------------------------- AC-3

def test_ac3_running_then_red_main_refuses_merge(env):
    """CI головы main 1–3 раза «идёт», затем красный; `approve` задачи.

    Прежний отказ «main красный», задача на `merge_gate`, origin/main не
    сдвинут.

    Ловит мутацию: ожидание идущего CI main кончается проходом по любому
    исходу (или идущий CI — проход без ожидания) — задача мержится поверх
    красного main.
    """
    k = env.rng.randint(1, 3)
    env.main_script[env.base_sha] = ["running"] * k + ["red"]
    task = env.make_task()
    before = env.origin_main()

    ok, out = env.cli("approve", task["id"])

    assert not ok, env.msg(f"мерж при покрасневшем main прошёл: {out}")
    assert "main красный" in out, env.msg(out)
    assert env.state_of(task) == "merge_gate", env.msg(out)
    assert env.origin_main() == before, env.msg(out)


# --------------------------------------------------------------------- AC-4

def test_ac4_running_main_past_limit_refuses_counted_from_wait_start(env):
    """Часы до `approve` сдвинуты не меньше чем на `MAIN_CI_WAIT_LIMIT_SEC`;
    CI ветки задачи 3–5 раз «ещё идёт» (не меньше трёх пауз по
    `MERGE_GATE_CI_WAIT_POLL_SEC`), затем зелёный; CI головы main идёт
    всегда.

    Отказ «CI main <sha> не завершён за N мин — повтори approve», задача на
    `merge_gate`, origin/main не сдвинут; от первого чтения цвета головы
    main до отказа прошло от `MAIN_CI_WAIT_LIMIT_SEC` до 20 подставных
    минут (с точностью до паузы опроса).

    Ловит мутацию: предел отсчитывается от входа в `approve`, от `start`
    внешнего цикла (до ожидания CI ветки) или от подставного начала часов —
    отказ наступает раньше `MAIN_CI_WAIT_LIMIT_SEC` от начала ожидания;
    предела нет — пауза песочницы падает; идущий CI — проход — задача в
    `done`.
    """
    limit = fsm_merge_gate.MAIN_CI_WAIT_LIMIT_SEC
    running_polls = env.rng.randint(3, 5)
    env.branch_script = [False] * running_polls + [True]
    env.main_script[env.base_sha] = ["running"]
    task = env.make_task()
    before = env.origin_main()
    env.clock += limit + env.rng.randint(0, 600)

    ok, out = env.cli("approve", task["id"])

    reads = env.reads(env.base_sha)
    assert reads, env.msg(f"цвет головы main не читался: {out}")
    wait_start = reads[0][1]
    branch_pauses = [s for s, at in env.sleeps if at <= wait_start]
    assert env.branch_calls == running_polls + 1, env.msg(
        f"опросов CI ветки {env.branch_calls}, ждали {running_polls + 1}")
    assert sum(branch_pauses) >= 3 * config.MERGE_GATE_CI_WAIT_POLL_SEC, \
        env.msg(f"паузы ожидания CI ветки: {branch_pauses}")
    assert not ok, env.msg(f"мерж при идущем CI main прошёл: {out}")
    assert f"не завершён за {limit // 60} мин" in out, env.msg(out)
    assert "повтори approve" in out, env.msg(out)
    assert names_commit(out, env.base_sha), env.msg(
        f"отказ не называет {env.base_sha[:8]}: {out}")
    assert env.state_of(task) == "merge_gate", env.msg(out)
    assert env.origin_main() == before, env.msg(out)
    elapsed = env.clock - wait_start
    assert elapsed >= limit, env.msg(f"отказ через {elapsed} с от начала ожидания")
    assert elapsed <= WAIT_MAX_SEC + config.VERIFYING_POLL_INTERVAL_SEC, \
        env.msg(f"отказ через {elapsed} с от начала ожидания")


# --------------------------------------------------------------------- AC-5

def test_ac5_fixes_main_skips_waiting_and_records_reason(env):
    """CI головы main и новой головы после мержа идёт; `approve <id> <sha>
    --fixes-main "<основание>"`.

    Ожидания нет — подставная пауза не вызвана ни разу; задача смержена
    (`done`), основание записано в журнал задачи.

    Ловит мутацию: `--fixes-main` снимает только отказ на красном, а
    идущий CI main мерж всё равно ждёт — паузы есть, по пределу отказ.
    """
    env.main_script[env.base_sha] = ["running"]
    env.main_default = ["running"]
    task = env.make_task()
    reason = (f"чиню main: {env.rng.choice(('README', 'guard', 'тесты'))} "
              f"#{env.rng.randrange(10 ** 6)}")

    ok, out = env.cli("approve", task["id"], task["fixed"],
                      "--fixes-main", reason)

    assert env.sleeps == [], env.msg(f"паузы при --fixes-main: {env.sleeps}; {out}")
    assert env.state_of(task) == "done", env.msg(out)
    assert [r for r in env.journal(task) if reason in r], env.msg(
        f"основания нет в журнале: {env.journal(task)}")


# --------------------------------------------------------------------- AC-6

def test_ac6_unknown_main_passes_without_wait(env):
    """Чтение цвета головы main — сбой `gh` (исход «неизвестен»); `approve`.

    Прежний проход: задача в `done`, пауза не вызвана, в журнале задачи —
    запись, называющая голову main и неизвестный статус.

    Ловит мутацию: неизвестный исход ждут как идущий — паузы до предела и
    отказ «не завершён» вместо прохода.
    """
    env.main_script[env.base_sha] = ["unknown"]
    task = env.make_task()

    ok, out = env.cli("approve", task["id"])

    assert ok and env.state_of(task) == "done", env.msg(out)
    assert env.sleeps == [], env.msg(f"паузы: {env.sleeps}")
    assert [r for r in env.journal(task)
            if names_commit(r, env.base_sha) and "неизвестен" in r], \
        env.msg(f"нет записи о неизвестном CI main: {env.journal(task)}")


# --------------------------------------------------------------------- AC-7

def test_ac7_wait_moves_from_after_merge_to_next_merge(env):
    """Два мержа подряд: CI головы первого мержа k+1 раз «идёт» (k от 2 до
    4), затем зелёный.

    Первый `approve` читает новую голову один раз и не паузит; второй
    `approve` дожидается её зелёного: ещё k+1 чтений, k пауз, задача в
    `done`.

    Ловит мутацию: «идущий CI main — проход без ожидания» в
    `_refuse_if_main_red` — второй мерж читает голову один раз и не паузит;
    «ожидание после мержа оставлено» в `_await_main_ci` — первый мерж
    паузит, дожидаясь зелёного.
    """
    k = env.rng.randint(2, 4)
    env.main_script[env.base_sha] = ["green"]
    env.main_default = ["running"] * (k + 1) + ["green"]
    first = env.make_task()

    ok, out = env.cli("approve", first["id"])
    head = env.origin_main()

    assert env.state_of(first) == "done", env.msg(out)
    assert env.sleeps == [], env.msg(f"k={k}: паузы после мержа {env.sleeps}")
    assert len(env.reads(head)) == 1, env.msg(f"k={k}: {env.reads(head)}")

    second = env.make_task()
    ok, out = env.cli("approve", second["id"])

    assert ok and env.state_of(second) == "done", env.msg(out)
    assert len(env.reads(head)) == 1 + k + 1, env.msg(
        f"k={k}: чтения головы {head[:8]}: {env.reads(head)}")
    assert len(env.sleeps) == k, env.msg(f"k={k}: паузы {env.sleeps}")


# --------------------------------------------------------------------- AC-8

def test_ac8_gh_failure_during_wait_passes_at_once(env):
    """CI головы main 1–3 раза «идёт», затем чтение цвета — сбой `gh`.

    Мерж проходит сразу: задача в `done`, после сбоя пауз нет (паузы — по
    одной на каждое «идёт»), подставное время ожидания меньше
    `MAIN_CI_WAIT_LIMIT_SEC`, в журнале — запись о неизвестном статусе
    головы main.

    Ловит мутацию: при сбое `gh` во время ожидания ждать до предела —
    подставное время ожидания доходит до предела, мерж отказан.
    """
    j = env.rng.randint(1, 3)
    env.main_script[env.base_sha] = ["running"] * j + ["unknown"]
    task = env.make_task()

    ok, out = env.cli("approve", task["id"])

    assert ok and env.state_of(task) == "done", env.msg(f"j={j}: {out}")
    reads = env.reads(env.base_sha)
    assert len(reads) == j + 1, env.msg(f"j={j}: чтения головы main {reads}")
    assert reads[-1][1] - reads[0][1] < fsm_merge_gate.MAIN_CI_WAIT_LIMIT_SEC, \
        env.msg(f"j={j}: {reads}")
    assert len(env.sleeps) == j, env.msg(f"j={j}: паузы {env.sleeps}")
    assert [r for r in env.journal(task)
            if names_commit(r, env.base_sha) and "неизвестен" in r], \
        env.msg(f"нет записи о неизвестном CI main: {env.journal(task)}")


# --------------------------------------------------------------------- AC-9

def test_ac9_docs_ref_synced_when_main_wait_polls(env):
    """CI головы main сначала «идёт», затем зелёный. В теле гейта после
    сверки ссылки документов с origin и до сверки CI main (обёртка
    `outcome_integrity.merge_gate_escalates`) пульт пишет строку паспорта —
    недосланный коммит ссылки документов.

    Связка «команда approve — узел записи документов — git origin»: в
    момент первого опроса ожидания (второе чтение цвета головы main —
    первое после чтения сверки) ссылка документов задачи в голом origin
    равна локальной; перед сверкой CI main коммит был недосланным.

    Ловит мутацию: досылки перед ожиданием CI main нет — коммит паспорта
    уходит в origin только на выходе команды, в момент опроса ожидания
    origin отстаёт.
    """
    env.main_script[env.base_sha] = ["running", "green"]
    task = env.make_task()
    lag_before_check: list[bool] = []
    lag_at_poll: list[bool] = []
    real_gate = outcome_integrity.merge_gate_escalates

    def gate_with_docs_commit(conn, task_id, *args, **kwargs):
        passport_commit(conn, task_id)
        lag_before_check.append(env.docs_ref_lags(task_id))
        return real_gate(conn, task_id, *args, **kwargs)

    def on_read(sha):
        if sha == env.base_sha and len(env.reads(sha)) == 2:
            lag_at_poll.append(env.docs_ref_lags(task["id"]))

    env.on_main_read = on_read
    with mock.patch.object(outcome_integrity, "merge_gate_escalates",
                           side_effect=gate_with_docs_commit):
        ok, out = env.cli("approve", task["id"])

    assert lag_before_check and lag_before_check[-1] is True, env.msg(
        f"коммит перед сверкой CI main не недосланный: {lag_before_check}; {out}; {env.journal(task)}")
    assert lag_at_poll == [False], env.msg(
        f"origin при опросе ожидания CI main: {lag_at_poll}; {out}")
