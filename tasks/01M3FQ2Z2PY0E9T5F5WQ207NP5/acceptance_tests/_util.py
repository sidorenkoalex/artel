"""Общие помощники планки 01M3FQ2Z2PY0E9T5F5WQ207NP5 (канарейка на наборе
ролей: провайдер и модели ролей в клоне, бейзлайн по набору).

Четыре предмета, нужные больше чем одному файлу планки:

1. **Канал набора.** Имя параметра, которым имя набора доезжает до
   `canary.cmd_canary` (AC-1), планка не угадывает: она читает его
   ИЗ СИГНАТУРЫ (`set_param_name`), а имя набора по умолчанию — из того,
   что `artel._cmd_canary` передаёт без `--set` (`default_set_name`).
   Так тесты остальных критериев не зависят от того, как разработчик
   назовёт параметр и константу.
2. **Локальный слой пульта с наборами** (`local_layer_text`) — текст
   шаблона `models.LOCAL_TEMPLATE` плюс разделы `overrides:` и
   `canary_sets:`. Наборы записаны ВЛОЖЕННЫМИ БЛОЧНЫМИ отображениями, а
   не потоковыми (`{provider: codex, model: …}`, как в примере
   требования 2 SPEC): единственный разбор YAML в пульте
   (`orchestrator/yamlmini.py`, путь вне зон задачи) потоковые
   ОТОБРАЖЕНИЯ не поддерживает вовсе — только потоковые списки. Оба
   написания задают одно и то же отображение, и критерии приёмки формы
   записи не фиксируют.
3. **Песочница прогона** (`CanarySetSandbox`) — НАСТОЯЩИЙ git-корень с
   `roles.yaml`/`models.yaml` в коммите (целевой sha прогона), локальный
   слой с наборами, пул из одного шаблона. Даёт два приёма: `clone_probe`
   (снять наблюдение ВНУТРИ эфемерного клона и прервать прогон до
   заведения задачи) и `run_canary` (полный прогон с синтетическим
   вождением задачи вместо шагов ролей — живой CLI провайдера не
   запускается).
4. **Чтение main** (`main_source`, `main_tree_files`, `unittest_method_names`,
   `new_check_names`) — исходники коммита main читаются `git show`/`git
   ls-tree` в репозитории рабочей копии, а не с диска ветки.

Артефакты задачи (SPEC.md/PLAN.md/REVIEW.md) планка не читает вовсе: её
предмет — код, документация и БД пульта.

Имя файла с ведущим подчёркиванием — единственная форма общего кода
планки, которую checkpoint не отбрасывает (skills/test-authoring.md).
Лёгкую песочницу переходов FSM этот файл не переопределяет и не копирует:
нужные песочницы импортируются из `tests/sandbox.py`.
"""
import inspect
import io
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (artel, canary, config, models,  # noqa: E402
                          pool_seal, store)
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK_ID = "01M3FQ2Z2PY0E9T5F5WQ207NP5"

#: Коммит `origin/main`, с которым планка сверяет состав тестов и перечень
#: строк `doctor` (голова main на момент заведения задачи — «Материалы»
#: SPEC.md).
MAIN_SHA = "a24d78fc"

TESTS_DIR = REPO_ROOT / "tests"
DOCTOR_DIR = REPO_ROOT / "orchestrator" / "doctor"

# --- наборы-фикстуры ----------------------------------------------------

#: Набор из примера требования 2 SPEC: обе роли одного яруса на ОДНОЙ
#: модели Codex (разные модели одного яруса — отказ требования 6г).
SET_NAME = "codex-strong"
SET_MODEL = "gpt-5.6-terra"
SET_PROVIDER = "codex"
SET_ROLES = ("developer", "reviewer")

#: Второй исправный набор — нужен там, где критерий требует ДВУХ наборов
#: по одному шаблону (AC-7, AC-11).
OTHER_SET_NAME = "codex-cheap"
OTHER_SET_MODEL = "gpt-5.6-luna"

#: Третья модель Codex каталога — для сценария «две роли одного яруса,
#: разные модели» (AC-3в).
THIRD_MODEL = "gpt-5.6-sol"

#: Собственный тариф пульта на модель набора (`overrides:` локального
#: слоя): числа заведомо отличаются от прейскуранта каталога, иначе
#: перенос тарифа в слой клона (AC-4) был бы не наблюдаем.
PULT_OVERRIDE = {
    "input": 1.5,
    "output": 9.0,
    "cache_write": 1.5,
    "cache_read": 0.15,
    "calibrated_at": "2026-09-26",
    "source": "тариф планки 01M3FQ2Z2PY0E9T5F5WQ207NP5",
}

GOOD_SETS = {
    SET_NAME: {role: {"provider": SET_PROVIDER, "model": SET_MODEL}
               for role in SET_ROLES},
    OTHER_SET_NAME: {role: {"provider": SET_PROVIDER, "model": OTHER_SET_MODEL}
                     for role in SET_ROLES},
}

#: Тело шаблона пула: маркер «эскалация не ожидается» (`canary.
#: MARK_EXPECT_ESCALATION_NO`) держит исход прогона без расхождения —
#: именно на таком исходе критерии AC-7/AC-11 заводят и сверяют бейзлайн.
POOL_TEMPLATE_TITLE = "nabor-rolej-kanarejki"
POOL_TEMPLATE_TEXT = (
    "# Синтетическое ТЗ планки набора\n\n"
    f"{canary.MARK_EXPECT_ESCALATION_NO}\n\n"
    "Поправь одну строку и остановись.\n")


def _block(mapping: dict, indent: int) -> list:
    """Вложенное блочное отображение строками — форма, которую разбирает
    `orchestrator/yamlmini.py` (потоковые отображения он не читает)."""
    lines = []
    pad = " " * indent
    for key, value in mapping.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.extend(_block(value, indent + 2))
        else:
            lines.append(f"{pad}{key}: {value}")
    return lines


def local_layer_text(sets: dict | None, overrides: dict | None = None) -> str:
    """Текст локального слоя пульта: шаблон `models.LOCAL_TEMPLATE` плюс
    `overrides:` и `canary_sets:`.

    `sets=None` — слой БЕЗ раздела наборов вовсе (сценарий `warn`
    требования 9/AC-13). Ярусы берутся из шаблона, а не литералами:
    шаблон — крутилка пульта, и его правка не должна красить планку.
    """
    parts = [models.local_template_text()]
    if overrides:
        parts.append("\n".join(["overrides:"]
                               + _block(overrides, 2)) + "\n")
    if sets is not None:
        parts.append("\n".join(["canary_sets:"] + _block(sets, 2)) + "\n")
    return "\n".join(parts)


# --- канал имени набора -------------------------------------------------

#: Параметры `canary.cmd_canary`, существовавшие до этой задачи: имя
#: набора приходит ОДНИМ новым параметром (AC-1).
CMD_CANARY_KNOWN_PARAMS = ("k", "sha")

#: Значение-часовой «параметр не передан вовсе» (прогон без `--set`).
OMIT = object()


def set_param_name() -> str:
    """Имя параметра `canary.cmd_canary`, которым доезжает имя набора."""
    names = [name for name in inspect.signature(canary.cmd_canary).parameters
             if name not in CMD_CANARY_KNOWN_PARAMS]
    if len(names) != 1:
        raise AssertionError(
            "AC-1: имя набора обязано доезжать до canary.cmd_canary ОДНИМ "
            f"новым параметром, найдено: {names or 'ни одного'}")
    return names[0]


def cmd_canary_kwargs(set_name=OMIT, **extra) -> dict:
    """Аргументы вызова `canary.cmd_canary` с именем набора (или без него,
    `set_name=OMIT` — прогон по набору по умолчанию)."""
    kwargs = dict(extra)
    if set_name is not OMIT:
        kwargs[set_param_name()] = set_name
    return kwargs


def cli_canary_arguments(argv: list) -> dict:
    """Аргументы, с которыми `artel._cmd_canary(argv)` зовёт
    `canary.cmd_canary`, приведённые к именам параметров подписи.

    Сам `canary.cmd_canary` подменяется, прогон не стартует.
    """
    signature = inspect.signature(canary.cmd_canary)
    seen: dict = {}

    def fake(*args, **kwargs):
        seen.update(signature.bind(*args, **kwargs).arguments)

    with mock.patch.object(canary, "cmd_canary", fake):
        artel._cmd_canary(list(argv))
    return seen


def default_set_name() -> str:
    """Имя набора по умолчанию — значение, которое CLI передаёт
    `canary.cmd_canary` без `--set` (AC-1)."""
    value = cli_canary_arguments(["--k", "1"]).get(set_param_name())
    if not isinstance(value, str) or not value:
        raise AssertionError(
            "AC-1: без --set параметр обязан нести имя набора по умолчанию "
            f"непустой строкой, получено {value!r}")
    return value


# --- чтение main --------------------------------------------------------

def _git(*args) -> tuple:
    """(код возврата, stdout) команды git в РЕПОЗИТОРИИ рабочей копии.

    Не `gitcmd` (он ходит в `config.ROOT`): часть песочниц планки уводит
    `config.ROOT` во временный каталог, где git-репозитория нет вовсе, а
    читать исходники main нужно именно из репозитория.
    """
    result = subprocess.run(["git", *args], cwd=REPO_ROOT,
                            capture_output=True, text=True)
    return result.returncode, result.stdout


def main_source(rel_path: str) -> str:
    """Текст файла `rel_path` в коммите `MAIN_SHA` — только через git, не
    с диска рабочей копии."""
    code, text = _git("show", f"{MAIN_SHA}:{rel_path}")
    if code != 0:
        raise AssertionError(f"{MAIN_SHA}:{rel_path} не прочитан")
    return text


def main_tree_files(rel_dir: str) -> list:
    """Пути файлов каталога `rel_dir` в дереве коммита `MAIN_SHA`."""
    code, text = _git("ls-tree", "-r", "--name-only", MAIN_SHA, rel_dir)
    if code != 0:
        raise AssertionError(f"дерево {MAIN_SHA} не прочитано")
    return [line for line in text.splitlines() if line]


TEST_METHOD_RE = re.compile(r"^\s*def (test_\w+)", re.M)
CHECK_FUNC_RE = re.compile(r"^def (check_\w+)", re.M)


def unittest_method_names(source: str) -> set:
    return set(TEST_METHOD_RE.findall(source))


def _check_names_of_tree(read, paths) -> set:
    names = set()
    for path in paths:
        names |= set(CHECK_FUNC_RE.findall(read(path)))
    return names


def new_check_names() -> set:
    """Имена строк `doctor` (`def check_*` пакета `orchestrator/doctor/`),
    появившиеся в ветке относительно `MAIN_SHA`."""
    main_paths = main_tree_files("orchestrator/doctor")
    before = _check_names_of_tree(
        main_source, [p for p in main_paths if p.endswith(".py")])
    after = _check_names_of_tree(
        lambda p: p.read_text(encoding="utf-8"),
        sorted(DOCTOR_DIR.glob("*.py")))
    return after - before


# --- колонки таблиц канарейки ------------------------------------------

#: Колонки, которые таблицы метрик канарейки несли ДО этой задачи
#: (`store._ensure_canary_tables` коммита main) — новая колонка имени
#: набора (и сводки «роль → модель») ищется как разница с этим перечнем,
#: чтобы планка не угадывала её имя.
RUN_COLUMNS_BEFORE = (
    "id", "run_stamp", "title", "task_id", "steps", "cost_usd",
    "review_iterations", "escalations", "outcome", "expected_escalation",
    "actual_escalation", "marker_mismatch", "created_at", "main_sha",
    "verdict")
BASELINE_COLUMNS_BEFORE = ("title", "steps", "cost_usd", "review_iterations",
                           "updated_at")

BASELINE_CREATE_BEFORE = (
    "CREATE TABLE canary_baseline ("
    "  title TEXT PRIMARY KEY, steps INTEGER, cost_usd REAL,"
    "  review_iterations INTEGER, updated_at TEXT)")
RUNS_CREATE_BEFORE = (
    "CREATE TABLE canary_runs ("
    "  id INTEGER PRIMARY KEY AUTOINCREMENT, run_stamp TEXT, title TEXT,"
    "  task_id TEXT, steps INTEGER, cost_usd REAL, review_iterations INTEGER,"
    "  escalations INTEGER, outcome TEXT, expected_escalation TEXT,"
    "  actual_escalation INTEGER, marker_mismatch INTEGER, created_at TEXT,"
    "  main_sha TEXT, verdict TEXT)")


def new_columns(conn, table: str, before) -> set:
    return set(store.table_columns(conn, table)) - set(before)


def row_values(row) -> list:
    return [row[key] for key in row.keys()]


# --- песочница прогона --------------------------------------------------

class _ProbeStop(Exception):
    """Прерывает прогон сразу после снятия наблюдения в клоне."""


class CanarySetSandbox(RealGitSandbox):
    """Настоящий git-корень пульта (целевой sha прогона несёт
    `roles.yaml`/`models.yaml`), локальный слой с наборами и пул из одного
    шаблона.

    Живой CLI провайдера не запускается ни в одном приёме: шаги ролей
    подменены синтетическим вождением (`run_canary`) либо прогон
    прерывается до заведения задачи (`clone_probe`).
    """

    SETS = GOOD_SETS
    OVERRIDES = {SET_MODEL: PULT_OVERRIDE}

    def setUp(self):
        super().setUp()
        for name in ("roles.yaml", "models.yaml"):
            shutil.copy2(REPO_ROOT / name, self.root / name)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "карта исполнителей и каталог моделей")
        self.head = self.git("rev-parse", "HEAD").strip()
        self.roles_yaml_text = (REPO_ROOT / "roles.yaml").read_text(
            encoding="utf-8")

        self.write_local_layer(self.SETS, self.OVERRIDES)

        pool = tempfile.mkdtemp(prefix="artel-plank-pool-")
        self.addCleanup(shutil.rmtree, pool, ignore_errors=True)
        self.pool_dir = Path(pool)
        (self.pool_dir / f"{POOL_TEMPLATE_TITLE}.md").write_text(
            POOL_TEMPLATE_TEXT, encoding="utf-8")

        for target, attr, value in (
                (canary, "_pool_dir", lambda: self.pool_dir),
                # Восстановление пула из `catalog.cmd_init` внутри клона
                # трогало бы РЕАЛЬНЫЙ `~/.artel-canary` Оператора и
                # связку ключей — к предмету планки отношения не имеет.
                (pool_seal, "restore_pool_if_missing", lambda conn: None)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.conn = store.db()
        self._task_counter = 0

    def write_local_layer(self, sets, overrides=None) -> None:
        config.MODELS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        config.MODELS_LOCAL.write_text(local_layer_text(sets, overrides),
                                       encoding="utf-8")

    # -- наблюдение внутри клона -----------------------------------------

    def clone_probe(self, probe, set_name=OMIT) -> dict:
        """Запускает `canary.cmd_canary` и снимает `probe()` ВНУТРИ
        эфемерного клона — в момент, когда клон уже собран (локальный слой
        положен), но задача ещё не заведена; дальше прогон прерывается.
        """
        recorded: dict = {}

        def fake_cmd_new(*args, **kwargs):
            recorded.update(probe())
            raise _ProbeStop

        with mock.patch.object(canary.catalog, "cmd_new", fake_cmd_new):
            with self.assertRaises(_ProbeStop):
                with redirect_stdout(io.StringIO()):
                    canary.cmd_canary(**cmd_canary_kwargs(
                        set_name, k=1, sha=self.head))
        return recorded

    # -- полный прогон с синтетическим вождением -------------------------

    def run_canary(self, set_name=OMIT, spent: float = 1.0, steps: int = 3,
                   review_iters: int = 0) -> str:
        """Полный прогон одной канареечной задачи: клон настоящий, фазы
        записи прогона и сверки с бейзлайном настоящие, а заведение задачи
        и её вождение — синтетические (ни одного шага роли, ни одного
        вызова CLI провайдера). Возвращает напечатанный вывод `canary`.

        Исход задачи — штатный kill на `merge_gate` (тот же литерал
        журнала, по которому `canary._kill_outcome_note` называет исход
        «штатно»): именно на таком исходе заводится и сверяется бейзлайн.
        """
        kill_action = canary._MERGE_GATE_KILL_ACTION
        kill_actor = canary.CANARY_MARK_ACTOR

        def fake_cmd_new(title, tz_path=None, canary=False, **kwargs):
            self._task_counter += 1
            task_id = "01M3FQPLANKA" + f"{self._task_counter:014d}"
            conn = store.db()
            store.insert_task(conn, task_id, title, "in_dev",
                              f"task/{task_id.lower()}-kanarejka",
                              config.DEFAULT_TARGET, 10.0, is_canary=True)
            return task_id

        def fake_drive(conn, task_id):
            for number in range(steps):
                store.journal(conn, task_id, "fsm", f"state -> шаг{number}",
                              "синтетический переход планки")
            store.journal(conn, task_id, kill_actor, kill_action,
                          "синтетический штатный исход планки")
            conn.execute(
                "UPDATE tasks SET state='killed', spent_usd=?, review_iters=?"
                " WHERE id=?", (spent, review_iters, task_id))
            conn.commit()

        buf = io.StringIO()
        with mock.patch.object(canary.catalog, "cmd_new", fake_cmd_new), \
             mock.patch.object(canary.workspace, "ensure",
                               lambda task_id, branch: (self.root, None)), \
             mock.patch.object(canary, "_drive_task", fake_drive):
            with redirect_stdout(buf):
                canary.cmd_canary(**cmd_canary_kwargs(set_name, k=1,
                                                      sha=self.head))
        return buf.getvalue()

    # -- отказы до клона --------------------------------------------------

    def refuse_before_clone(self, set_name) -> str:
        """Текст именованного отказа `canary.cmd_canary` на наборе
        `set_name`, снятый вместе с двумя фактами «до клона»: ни одного
        `git clone` и ни одной строки `tasks` (AC-2, AC-3).
        """
        calls = []
        real_run = canary.subprocess.run

        def watched_run(cmd, *args, **kwargs):
            calls.append(list(cmd))
            return real_run(cmd, *args, **kwargs)

        def forbidden_cmd_new(*args, **kwargs):
            raise AssertionError("задача заведена после отказа до клона")

        with mock.patch.object(canary.subprocess, "run", watched_run), \
             mock.patch.object(canary.catalog, "cmd_new", forbidden_cmd_new):
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stdout(io.StringIO()):
                    canary.cmd_canary(**cmd_canary_kwargs(
                        set_name, k=1, sha=self.head))

        clones = [cmd for cmd in calls if cmd[:2] == ["git", "clone"]]
        self.assertEqual([], clones,
                         "эфемерный клон создан ДО отказа по набору")
        self.assertEqual([], store.all_tasks(self.conn),
                         "строка tasks заведена ДО отказа по набору")
        return str(ctx.exception)


class LocalLayerOnlyTest(unittest.TestCase):
    """Локальный слой пульта во временном каталоге + БД со схемой, без
    настоящего git: этого достаточно строке `doctor` по наборам (AC-13).
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        for attr, value in (("ROOT", self.tdir),
                            ("DB", self.tdir / ".artel" / "state.db"),
                            ("MODELS_LOCAL",
                             self.tdir / ".artel" / "models.yaml")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()
        self.write_local_layer(GOOD_SETS, {SET_MODEL: PULT_OVERRIDE})

    def write_local_layer(self, sets, overrides=None) -> None:
        config.MODELS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        config.MODELS_LOCAL.write_text(local_layer_text(sets, overrides),
                                       encoding="utf-8")


def old_schema_conn(path: Path) -> sqlite3.Connection:
    """Соединение с БД, чьи таблицы канарейки заведены ТАК, как их
    заводил пульт до этой задачи (AC-8) — вместе с остальной схемой."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    store.create_schema(conn)
    conn.execute(BASELINE_CREATE_BEFORE)
    conn.execute(RUNS_CREATE_BEFORE)
    conn.commit()
    return conn
