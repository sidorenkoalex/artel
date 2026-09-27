"""Общие помощники планки 01M3HJQV2QV9BXNXSH3F8STAYH (канарейка переживает
эскалацию по бюджету и позволяет выбрать шаблон).

Четыре предмета, нужные больше чем одному файлу планки:

1. **Пул шаблонов** (`PoolSandbox`) — НАСТОЯЩИЙ git-корень пульта (целевой
   sha прогона разрешается локально, без обращения к origin) и пул из трёх
   `*.md` шаблонов ВНЕ корня. Два приёма: `run_templates` (какие шаблоны
   прогон реально взял и в каком порядке — `canary._run_one_task`
   подменён, ни одного клона) и `refuse` (именованный отказ вместе с
   тремя фактами «до прогона»: ни одного `git clone`, ни одной строки
   `tasks`, ни одного обращения к origin).
2. **Прогон одной задачи без эфемерного клона** (`ClonelessRunSandbox`) —
   `canary._run_one_task` целиком, но `_ephemeral_clone` подменён
   контекстом, который ничего не клонирует и не переадресует пути
   `config`. Так БД прогона остаётся БД песочницы и журнал задачи
   читается ПОСЛЕ прогона (клон свою БД уносит с собой), а вождение
   задачи — настоящее `canary._drive_task` поверх синтетического
   `auto.cmd_auto`: расход шага и эскалацию по бюджету пишет живой
   `budget.enforce_budget` (требование 6 SPEC называет именно его
   причину), не подделка. Сам жизненный цикл клона — предмет чужой,
   уже залоченной планки (01M1NEEWH5K1XPFRDGRMPYSBXJ, AC-2/AC-4), не
   этой.
3. **«Как было до задачи»** (`base_sha`, `main_source`, `main_tree_files`,
   `CONFIG_NUMERIC_BEFORE`) — имя новой константы-множителя и состав
   чужих тестов планка не угадывает: и то, и другое ищется как разница с
   общим предком ветки и `config.MAIN_BRANCH`, читаемым через `git show`.
4. **Мелкие разборы текста** (`amounts`, `mentions_amount`, `doc_blocks`) —
   сумма в строке отчёта/журнала сверяется числом, а не подстрокой:
   `$20.00`, `$20` и `20.0` — одна и та же сумма, и критерий формы записи
   не фиксирует.

Артефакты задачи (SPEC.md/PLAN.md/REVIEW.md) планка не читает вовсе — ни с
диска, ни из ветки: её предмет — код, документация и БД пульта.

Имя файла с ведущим подчёркиванием — единственная форма общего кода планки,
которую checkpoint не отбрасывает (skills/test-authoring.md). Лёгкую
песочницу переходов FSM этот файл не переопределяет и не копирует:
`RealGitSandbox` импортируется из `tests/sandbox.py`.
"""
import functools
import io
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest import mock

import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (artel, budget, canary, config,  # noqa: E402
                          pool_seal, runner, store)
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK_ID = "01M3HJQV2QV9BXNXSH3F8STAYH"

TESTS_DIR = REPO_ROOT / "tests"
DOCS_DIR = REPO_ROOT / "docs"

#: Штамп прогона для прямых вызовов `canary._run_one_task` — сам по себе
#: ничего не проверяет, только ключует строку `canary_runs`.
RUN_STAMP = "20260927T000000Z"


# --- «как было до задачи» ------------------------------------------------

def _git(*args) -> tuple:
    """(код возврата, stdout) команды git в РЕПОЗИТОРИИ рабочей копии.

    Не `gitcmd` (он ходит в `config.ROOT`): песочницы планки уводят
    `config.ROOT` во временный каталог, а читать «как было до задачи» нужно
    именно из репозитория ветки.
    """
    res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                         capture_output=True, text=True)
    return res.returncode, res.stdout


#: Голова `main` на момент заведения задачи — запас на случай, когда ветки
#: `config.MAIN_BRANCH` в репозитории прогона нет вовсе и общий предок не
#: вычисляется.
BASE_SHA_FALLBACK = "5ec64e1c"


@functools.lru_cache(maxsize=1)
def base_sha() -> str:
    """Sha, относительно которого читается «как было до задачи»: общий
    предок ветки задачи и `config.MAIN_BRANCH`.

    Общий предок, а не прибитый литерал: ветка задачи подтягивает main по
    ходу работы (правило свежести), и прибитый sha объявлял бы чужую
    правку, приехавшую подтяжкой, правкой этой ветки.
    """
    code, out = _git("merge-base", "HEAD", config.MAIN_BRANCH)
    if code == 0 and out.strip():
        return out.strip()
    return BASE_SHA_FALLBACK


def main_source(rel_path: str) -> str:
    """Текст файла `rel_path` в коммите `base_sha()` — только через git, не
    с диска рабочей копии."""
    code, text = _git("show", f"{base_sha()}:{rel_path}")
    if code != 0:
        raise AssertionError(f"{base_sha()}:{rel_path} не прочитан")
    return text


def main_tree_files(rel_dir: str) -> list:
    """Пути файлов каталога `rel_dir` в дереве коммита `base_sha()`."""
    code, text = _git("ls-tree", "-r", "--name-only", base_sha(), rel_dir)
    if code != 0:
        raise AssertionError(f"дерево {base_sha()} не прочитано")
    return [line for line in text.splitlines() if line]


TEST_METHOD_RE = re.compile(r"^\s*def (test_\w+)", re.M)


def unittest_method_names(source: str) -> set:
    return set(TEST_METHOD_RE.findall(source))


#: Числовые константы `orchestrator/config.py`, существовавшие ДО этой
#: задачи: именованная константа-множитель потолка (требование 7) ищется
#: как разница с этим перечнем, чтобы планка не угадывала её имя.
CONFIG_NUMERIC_BEFORE = (
    'ACCEPTANCE_TIMEOUT_SEC', 'AGENT_ATTEMPTS', 'AGENT_RETRIES',
    'AGENT_TIMEOUT_SEC', 'ALERT_ARCHIVE_DAYS', 'AUTO_MAX_STEPS',
    'AUTO_STALL_STEPS_LIMIT', 'BUDGET_ALERT_RATIO',
    'BUDGET_CALIBRATION_FLOOR_USD', 'CANARY_DEVIATION_RATIO',
    'CANARY_MAX_DEV_RETRIES', 'CANARY_MAX_ESCALATION_CYCLES',
    'CANARY_MAX_MERGES_SINCE_GREEN', 'CANARY_MAX_STALL_ITERS',
    'CI_CHECKS_MAX_PAGES', 'CI_CHECKS_PER_PAGE', 'CI_RERUN_WAIT_SEC',
    'CI_RUNS_PER_PAGE', 'CI_RUN_LIST_LIMIT', 'CONTEXT_FILE_MAX_BYTES',
    'CONTEXT_PART_MAX_BYTES', 'DEFAULT_BUDGET_USD', 'DOCTOR_MIN_FREE_MB',
    'DOCTOR_ORPHAN_PREVIEW_LIMIT', 'FULL_SUITE_TIMEOUT_SEC',
    'GH_TIMEOUT_SEC', 'HUNG_TEST_RUN_AGE_SEC', 'LEASE_STALE_AFTER_SEC',
    'LIMIT_ACCEPT_REJECTS', 'LIMIT_REVIEW_ITERS', 'LOG_RETENTION_DAYS',
    'LOG_RETENTION_KEEP_TASKS', 'LOG_TAIL_CHARS', 'LOG_TAIL_LINES',
    'MAP_GROWTH_CALIBRATION_MERGES', 'MAP_GROWTH_CALLS_ESTIMATE',
    'MAP_GROWTH_RATIO', 'MAP_JUMP_RATIO', 'MAX_PARALLEL_TASKS',
    'MERGE_GATE_CI_WAIT_CEILING_SEC', 'MERGE_GATE_CI_WAIT_POLL_SEC',
    'MERGE_QUEUE_WAIT_CEILING_SEC', 'MODEL_TARIFF_MAX_AGE_DAYS',
    'PROGRAM_STOP_LOSS_USD', 'PUMP_JOIN_TIMEOUT_SEC', 'RETRY_BACKOFF_SEC',
    'REVIEW_SNAPSHOT_DIFF_MAX_BYTES', 'ROLE_BUDGET_CAP',
    'SPLIT_SIGNAL_AC_COUNT', 'SPLIT_SIGNAL_BUDGET_USD',
    'SPLIT_SIGNAL_DIFF_FORECAST_RATIO', 'SPLIT_SIGNAL_ZONE_FILES',
    'STALE_BRANCH_WARN_COMMITS', 'STEP_COST_ESTIMATE_USD',
    'TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD', 'TRANSIENT_SYSTEM_BACKOFF_SEC',
    'VERIFYING_CEILING_SEC', 'VERIFYING_POLL_INTERVAL_SEC',
    'WAVE_BREAKER_TASKS', 'WAVE_BREAKER_WINDOW_SEC', 'ZONE_WAIT_MAX_SEC',
    'ZONE_WAIT_POLL_SEC')


def numeric_config_constants() -> dict:
    """{имя -> значение} числовых констант `config` (без `bool`)."""
    values = {}
    for name in dir(config):
        if not name.isupper():
            continue
        value = getattr(config, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        values[name] = value
    return values


def new_numeric_config_constants() -> dict:
    """Числовые константы `config`, которых до этой задачи не было."""
    return {name: value for name, value in numeric_config_constants().items()
            if name not in CONFIG_NUMERIC_BEFORE}


# --- разборы текста -----------------------------------------------------

#: Число как отдельный токен: `2026-09-27` даёт 2026, 9 и 27, но не 20 —
#: иначе сверка суммы подстрокой ловила бы цифры таймстампа и sha.
AMOUNT_RE = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])")


def amounts(text: str) -> list:
    return [float(token) for token in AMOUNT_RE.findall(text or "")]


def mentions_amount(text: str, value: float) -> bool:
    """В тексте есть число, равное `value` (с точностью до копейки) —
    форма записи (`$20.00`, `$20`, `20.0`) критерием не фиксируется."""
    return any(abs(number - value) < 0.005 for number in amounts(text))


ITEM_START_RE = re.compile(r"^(?:[-*]\s|\d+\.\s|#)")


def doc_blocks(text: str) -> list:
    """Смысловые блоки markdown-документа: абзацы и ОТДЕЛЬНЫЕ пункты
    списка.

    Пункт списка — единица, в которой Оператор читает правило (образец —
    пункт 5 «Аварийного режима» `docs/operator-session.md` про набор
    ролей): проверка «в одном блоке названы и исход, и пин» на целом файле
    была бы бессодержательной, а на абзацах — слепой к спискам.
    """
    blocks, current = [], []
    for line in (text or "").splitlines():
        if not line.strip() or ITEM_START_RE.match(line):
            if current:
                blocks.append("\n".join(current))
            current = []
        if line.strip():
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


# --- пул шаблонов -------------------------------------------------------

#: Стабильные имена шаблонов пула (имя файла без `.md` — именно оно,
#: по требованию 1, называется во флаге).
POOL_TITLES = ("plank-alpha", "plank-beta", "plank-gamma")

#: Файл пула, который шаблоном не является: `k` считается по `*.md`.
POOL_FOREIGN_FILE = "plank-ne-shablon.txt"

#: Тело шаблона: маркер «эскалация ОЖИДАЕТСЯ» (`canary.
#: MARK_EXPECT_ESCALATION_YES`) — эскалация по бюджету в сценариях
#: требований 7-11 реально случается, и с этим маркером исход остаётся БЕЗ
#: расхождения (именно такой исход требует AC-8 от зелёного вердикта).
POOL_TEMPLATE_TEXT = (
    "# Синтетическое ТЗ планки 01M3HJQV2QV9BXNXSH3F8STAYH\n\n"
    f"{canary.MARK_EXPECT_ESCALATION_YES}\n\n"
    "Поправь одну строку и остановись.\n")


class _ProbeStop(Exception):
    """Прерывает прогон в точке наблюдения."""


class PoolSandbox(RealGitSandbox):
    """Настоящий git-корень пульта + пул из трёх шаблонов вне корня.

    Ни один приём этого класса не запускает живой CLI провайдера и не
    доходит до шага роли: прогон либо подменён на уровне
    `canary._run_one_task`, либо прерывается отказом до клона.
    """

    def setUp(self):
        super().setUp()
        self.head = self.git("rev-parse", "HEAD").strip()

        pool = tempfile.mkdtemp(prefix="artel-plank-pool-")
        self.addCleanup(shutil.rmtree, pool, ignore_errors=True)
        self.pool_dir = Path(pool)
        for title in POOL_TITLES:
            (self.pool_dir / f"{title}.md").write_text(POOL_TEMPLATE_TEXT,
                                                       encoding="utf-8")
        (self.pool_dir / POOL_FOREIGN_FILE).write_text("не шаблон\n",
                                                       encoding="utf-8")

        for target, attr, value in (
                (canary, "_pool_dir", lambda: self.pool_dir),
                # Восстановление пула изнутри прогона трогало бы РЕАЛЬНЫЙ
                # `~/.artel-canary` Оператора и связку ключей — к предмету
                # планки отношения не имеет.
                (pool_seal, "restore_pool_if_missing", lambda conn: None)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.conn = store.db()

    # -- какие шаблоны прогон взял ---------------------------------------

    def run_templates(self, argv) -> tuple:
        """(имена шаблонов в порядке прогона, напечатанный вывод) для
        `artel._cmd_canary(argv)`.

        Подменён ровно полный цикл одной задачи (`canary._run_one_task`):
        выбор шаблонов, разбор флагов и первая строка вывода — настоящие,
        клона и задачи не возникает.
        """
        seen = []
        buf = io.StringIO()

        def fake_run_one(template_path, *args, **kwargs):
            seen.append(Path(template_path))

        with mock.patch.object(canary, "_run_one_task", fake_run_one):
            with redirect_stdout(buf):
                artel._cmd_canary(list(argv))
        return seen, buf.getvalue()

    def run_titles(self, argv) -> list:
        """Стабильные имена шаблонов (без `.md`) в порядке прогона."""
        paths, _out = self.run_templates(argv)
        return [path.stem for path in paths]

    # -- отказ до прогона -------------------------------------------------

    def refuse(self, argv) -> str:
        """Текст именованного отказа `canary` вместе с тремя фактами «до
        прогона»: ни одного `git clone`, ни одной строки `tasks`, ни одного
        обращения к origin. Возвращает текст отказа.

        `--sha` в `argv` не передаётся сознательно: без него целевой sha
        прогона берётся с головы `origin/<MAIN_BRANCH>`
        (`gitcmd.fetch_ref_sha`), и «обращения к origin не было» становится
        наблюдаемым фактом, а не словами.
        """
        runs = []
        real_run = canary.subprocess.run

        def watched_run(cmd, *args, **kwargs):
            runs.append(list(cmd))
            return real_run(cmd, *args, **kwargs)

        origin_calls = []

        def watched_fetch(remote, ref, **kwargs):
            origin_calls.append((remote, ref))
            return "", "планка: обращения к origin в отказе быть не должно"

        def forbidden_cmd_new(*args, **kwargs):
            raise AssertionError("задача заведена после отказа")

        with mock.patch.object(canary.subprocess, "run", watched_run), \
             mock.patch.object(canary.gitcmd, "fetch_ref_sha", watched_fetch), \
             mock.patch.object(canary.catalog, "cmd_new", forbidden_cmd_new):
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stdout(io.StringIO()):
                    artel._cmd_canary(list(argv))

        code = ctx.exception.code
        self.assertNotIn(code, (0, None),
                         f"код возврата отказа нулевой: {code!r}")
        clones = [cmd for cmd in runs if cmd[:2] == ["git", "clone"]]
        self.assertEqual([], clones, "эфемерный клон создан ДО отказа")
        self.assertEqual([], store.all_tasks(self.conn),
                         "строка tasks заведена ДО отказа")
        self.assertEqual([], origin_calls, "было обращение к origin ДО отказа")
        return str(code)

    # -- вывод до первого эфемерного клона --------------------------------

    def output_before_first_clone(self, argv) -> str:
        """Вывод прогона, накопленный к моменту создания ПЕРВОГО эфемерного
        клона: наблюдатель `canary.subprocess.run` снимает буфер на первом
        `git clone` и прерывает прогон."""
        buf = io.StringIO()
        snapshot = {}
        real_run = canary.subprocess.run

        def watched_run(cmd, *args, **kwargs):
            if list(cmd)[:2] == ["git", "clone"]:
                snapshot["text"] = buf.getvalue()
                raise _ProbeStop
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(canary.subprocess, "run", watched_run):
            with self.assertRaises(_ProbeStop):
                with redirect_stdout(buf):
                    artel._cmd_canary(list(argv))
        return snapshot.get("text", "")


# --- прогон одной задачи без эфемерного клона ---------------------------

class ClonelessRunSandbox(PoolSandbox):
    """`canary._run_one_task` целиком, но без эфемерного клона: вождение
    задачи — настоящее `canary._drive_task`, шаг роли — синтетический
    `auto.cmd_auto` по сценарию.

    `_ephemeral_clone` подменён контекстом, который ничего не клонирует и
    не переадресует пути `config`: БД прогона остаётся БД песочницы, и
    журнал задачи читается ПОСЛЕ прогона. Жизненный цикл клона — предмет
    залоченной планки 01M1NEEWH5K1XPFRDGRMPYSBXJ (AC-2/AC-4), не этой.

    Три сценария шага роли (`mode` вызова `run_one_task`):

    * `exhaust` — каждый шаг тратит `STEP_COST` и заканчивается живым
      `budget.enforce_budget`: потолок задачи пробивается, потом
      пробивается ещё раз;
    * `green` — до подъёма потолка то же, после подъёма шаги дешёвые и
      задача штатно доходит до `merge_gate`;
    * `stall` — шаг не тратит и не двигает ничего: прежняя стагнация
      (`config.CANARY_MAX_STALL_ITERS`), исход «не сошлась».
    """

    #: Потолок канареечной задачи «из SPEC клона» — подъём считается от
    #: него.
    TASK_BUDGET = 10.0
    #: Стоимость шага роли: двух шагов достаточно, чтобы пробить потолок.
    STEP_COST = 6.0
    #: Стоимость шага после подъёма потолка в сценарии `green`.
    CHEAP_STEP_COST = 0.5
    #: Предохранитель от зацикливания вождения: тест обязан падать
    #: названной причиной, а не висеть до таймаута раннера.
    AUTO_CALL_CEILING = 200

    #: Куда синтетический шаг двигает задачу после подъёма потолка
    #: (сценарий `green`): `verifying` канарейка проходит сама
    #: (`_pass_verifying`), `merge_gate` — её штатный финал.
    GREEN_PATH = {"in_dev": "verifying", "review": "merge_gate"}

    def setUp(self):
        super().setUp()
        self._runs = 0
        self.mode = "exhaust"
        self.auto_calls = 0
        self.budget_seen = []
        self.killed = []
        self.task_id = None

    # -- подмены ----------------------------------------------------------

    def _fake_clone(self, *args, **kwargs):
        @contextmanager
        def ctx():
            yield self.root
        return ctx()

    def _fake_cmd_new(self, title, tz_path=None, canary=False, **kwargs):
        store.insert_task(store.db(), self.task_id, title, "in_dev",
                          f"task/{self.task_id.lower()}-kanarejka",
                          config.DEFAULT_TARGET, self.TASK_BUDGET,
                          is_canary=True)
        return self.task_id

    def _fake_kill(self, task_id):
        """Наблюдаемый эффект `cleanup.cmd_kill` — задача в `killed`;
        worktree/ветку настоящий kill убирает git-ом, к предмету планки это
        отношения не имеет."""
        self.killed.append(task_id)
        conn = store.db()
        current = store.get_task(conn, task_id)["state"]
        if current != "killed":
            store.set_state(conn, task_id, "killed", "test",
                            expected_state=current)

    def _fake_synthetic_answer(self, conn, task_id):
        """Эффект `canary._pass_escalated_with_synthetic_answer` без git:
        настоящая функция коммитит ANSWER в артефактную ветку, а предмет
        сценария — возврат из `escalated`, не устройство ANSWER (тот же
        приём, что и `tests/test_canary.py::DriveTaskEscalationCapTest`)."""
        back = store.get_task(conn, task_id)["escalated_from"] or "in_dev"
        store.update_task(conn, task_id, escalated_from=None,
                          answer_baseline=None)
        store.set_state(conn, task_id, back, "test",
                        expected_state="escalated")

    def _auto(self, task_id):
        self.auto_calls += 1
        if self.auto_calls > self.AUTO_CALL_CEILING:
            raise AssertionError(
                f"вождение задачи не сошлось за {self.AUTO_CALL_CEILING} "
                f"вызовов auto.cmd_auto (сценарий {self.mode})")
        conn = store.db()
        t = store.get_task(conn, task_id)
        if runner.step_role(t) is None:
            return
        self.budget_seen.append(t["budget_usd"] or 0.0)
        getattr(self, f"_step_{self.mode}")(conn, task_id, t["state"])

    # -- сценарии шага роли ------------------------------------------------

    def _step_exhaust(self, conn, task_id, state):
        store.charge(conn, task_id, self.STEP_COST)
        budget.enforce_budget(conn, task_id, state)

    def _step_green(self, conn, task_id, state):
        if self.ceiling_raised():
            store.charge(conn, task_id, self.CHEAP_STEP_COST)
            store.set_state(conn, task_id, self.GREEN_PATH[state], "test",
                            expected_state=state)
            return
        self._step_exhaust(conn, task_id, state)

    def _step_stall(self, conn, task_id, state):
        return

    # -- прогон ------------------------------------------------------------

    def run_one_task(self, mode: str = "exhaust", title: str | None = None) -> str:
        """Полный `canary._run_one_task` по сценарию `mode`; возвращает
        напечатанный отчёт прогона по этой задаче."""
        self.mode = mode
        self.auto_calls = 0
        self.budget_seen = []
        self.killed = []
        self._runs += 1
        self.task_id = f"01M3HJPLANKA{self._runs:014d}"
        self.title = title or POOL_TITLES[self._runs - 1]
        template_path = self.pool_dir / f"{self.title}.md"

        buf = io.StringIO()
        with mock.patch.object(canary, "_ephemeral_clone", self._fake_clone), \
             mock.patch.object(canary.catalog, "cmd_new", self._fake_cmd_new), \
             mock.patch.object(canary.workspace, "ensure",
                               lambda task_id, branch: (self.root, None)), \
             mock.patch.object(canary.auto, "cmd_auto", self._auto), \
             mock.patch.object(canary, "_pass_escalated_with_synthetic_answer",
                               self._fake_synthetic_answer), \
             mock.patch.object(canary.cleanup, "cmd_kill", self._fake_kill):
            with redirect_stdout(buf):
                canary._run_one_task(template_path, RUN_STAMP,
                                     config.CANARY_DEVIATION_RATIO,
                                     self.head, "код пина")
        return buf.getvalue()

    # -- наблюдения --------------------------------------------------------

    def task_row(self, task_id: str | None = None):
        return store.get_task(self.conn, task_id or self.task_id)

    def steps(self, task_id: str | None = None) -> list:
        return store.task_steps(self.conn, task_id or self.task_id)

    def journal_texts(self, task_id: str | None = None) -> list:
        return [f"{r['action']} — {r['detail'] or ''}"
                for r in self.steps(task_id)]

    def transitions(self, task_id: str | None = None) -> list:
        return [r["action"] for r in self.steps(task_id)
                if r["action"].startswith("state -> ")]

    def ceiling_raised(self) -> bool:
        return (self.task_row()["budget_usd"] or 0.0) > self.TASK_BUDGET

    def ceilings_seen(self) -> list:
        """Потолки, которые видел шаг роли, без повторов подряд: длина 2 —
        подъём случился ровно один раз."""
        distinct = []
        for value in self.budget_seen:
            if not distinct or abs(distinct[-1] - value) > 1e-9:
                distinct.append(value)
        return distinct

    def run_row(self, title: str | None = None):
        rows = self.conn.execute(
            "SELECT * FROM canary_runs WHERE title=?",
            (title or self.title,)).fetchall()
        self.assertEqual(1, len(rows),
                         f"строк прогона по шаблону {title or self.title}: "
                         f"{len(rows)}")
        return rows[0]
