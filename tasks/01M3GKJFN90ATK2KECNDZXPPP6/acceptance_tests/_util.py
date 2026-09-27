"""Общие помощники планки 01M3GKJFN90ATK2KECNDZXPPP6 (индекс журнала и одна
выборка для report/watch; нормализация явного `--sha` канарейки).

Пять предметов, нужные больше чем одному файлу планки:

1. **Снимок индексов `steps`** (`steps_index_names`, `index_columns`,
   `task_id_index_names`, `steps_index_map`) — планка не угадывает ИМЯ
   индекса (критерии его не фиксируют): «индекс по `steps(task_id)`» она
   узнаёт по составу колонок из `PRAGMA index_info`, ровно `(task_id,)`.
2. **Счётчик запросов к `steps`** (`StepsQueries`) — `sqlite3.Connection.
   set_trace_callback`, тем же приёмом, что назван требованием 6 SPEC.
3. **Счётчик СТРОК, отданных SQL** (`RowCountingConn`) — обёртка
   соединения: `watch._emit_steps` получает соединение параметром, так
   что подменять в нём нечего, достаточно передать обёртку.
4. **Прежний способ чтения журнала** (`old_task_steps`,
   `old_journal_reading`) — выборка `SELECT * FROM steps WHERE task_id=?
   ORDER BY id` НА КАЖДУЮ задачу, то есть эталон AC-4/AC-5 и AC-6.
   Записан здесь сырым SQL, а не через `store.task_steps`: зона задачи
   включает `orchestrator/store.py`, и эталон «как было» не должен
   меняться вместе с той функцией.
5. **Песочницы** — `JournalSandbox` (БД пульта с журналом нескольких
   задач) и `CanaryShaSandbox` (пульт с пулом из одного шаблона, без
   единого клона и без живого CLI). Обе стоят на песочницах
   `tests/sandbox.py` (`TmpRootTest`/`SchemaConnTmpRootTest`), своих копий
   не заводят.

Артефакты задачи (SPEC/PLAN/REVIEW) планка не читает вовсе — ни с диска,
ни из артефактной ветки: её предмет целиком в коде и в БД пульта.

Имя файла с ведущим подчёркиванием — единственная форма общего кода
планки, которую checkpoint не отбрасывает (skills/test-authoring.md).
"""
import io
import json
import re
import sqlite3
import subprocess
import sys
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (canary, config, report,  # noqa: E402
                          spend, store, watch)
from tests.sandbox import SchemaConnTmpRootTest, TmpRootTest  # noqa: E402

TASK_ID = "01M3GKJFN90ATK2KECNDZXPPP6"

STEPS_TABLE = "steps"

#: Запрос «читает таблицу `steps`»: `FROM steps` либо `JOIN steps`
#: независимо от регистра и переносов строк. Предмет счёта — именно
#: чтение журнала, не запись в него (`INSERT INTO steps`).
STEPS_READ_RE = re.compile(r"\b(?:from|join)\s+steps\b", re.I)


# --- индексы `steps` ----------------------------------------------------

def steps_index_names(conn) -> list:
    """Имена всех индексов таблицы `steps` этой БД, по алфавиту."""
    return sorted(row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
        (STEPS_TABLE,)))


def index_columns(conn, index_name: str) -> list:
    """Колонки индекса по порядку ключа (`PRAGMA index_info`)."""
    rows = sorted(conn.execute(f"PRAGMA index_info({index_name})"),
                  key=lambda row: row[0])
    return [row[2] for row in rows]


def steps_index_map(conn) -> dict:
    """{имя индекса `steps`: кортеж его колонок} — сравнимый снимок НАБОРА
    индексов таблицы (AC-2 сравнивает набор новой БД с набором
    мигрированной)."""
    return {name: tuple(index_columns(conn, name))
            for name in steps_index_names(conn)}


def task_id_index_names(conn) -> list:
    """Индексы `steps`, чей ключ — РОВНО `(task_id,)`.

    Имя индекса критерии не фиксируют, поэтому планка ищет его по составу
    колонок. Ровно `(task_id,)`, а не «первая колонка task_id»: составной
    `steps(task_id, id)` требование 2 SPEC заводить запрещает, и под
    «индекс по `steps(task_id)`» он не подходит.
    """
    return [name for name in steps_index_names(conn)
            if index_columns(conn, name) == ["task_id"]]


def open_db(path: Path) -> sqlite3.Connection:
    """Соединение с файлом БД, отдающее строки по имени колонки — как
    `store.db()`, но без `migrate` на открытии (её зовёт сам тест)."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# --- счётчики обращений к БД -------------------------------------------

class StepsQueries:
    """Счётчик SQL-запросов соединения, читающих `steps`.

    Контекстный менеджер поверх `sqlite3.Connection.set_trace_callback`
    (требование 6 SPEC называет именно этот приём): обратный вызов
    получает текст КАЖДОГО подготовленного запроса соединения.
    """

    def __init__(self, conn):
        self.conn = conn
        self.statements: list = []

    def __enter__(self):
        self.conn.set_trace_callback(self._trace)
        return self

    def __exit__(self, *exc_info):
        self.conn.set_trace_callback(None)
        return False

    def _trace(self, statement) -> None:
        if statement and STEPS_READ_RE.search(str(statement)):
            self.statements.append(str(statement))

    @property
    def count(self) -> int:
        return len(self.statements)


class _Rows:
    """Курсор поверх уже прочитанных строк: `fetchall`/`fetchone`/итерация.

    `RowCountingConn` обязан узнать, СКОЛЬКО строк отдал SQL, то есть
    прочитать курсор до конца сам — читателю после этого отдаётся уже
    вычитанный результат, ведущий себя как курсор.
    """

    def __init__(self, rows: list):
        self._rows = list(rows)
        self._pos = 0

    def fetchall(self) -> list:
        rest, self._pos = self._rows[self._pos:], len(self._rows)
        return rest

    def fetchone(self):
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                return
            yield row


class RowCountingConn:
    """Обёртка соединения, считающая строки, отданные SQL по запросам к
    `steps` (`steps_rows`), и сами эти запросы (`steps_statements`).

    Нужна там, где предмет критерия — не число запросов, а ОБЪЁМ
    прочитанного: «получает из SQL ровно одну строку (не N)» AC-6.
    Остальные атрибуты соединения доезжают как есть (`__getattr__`).
    """

    def __init__(self, conn):
        self._conn = conn
        self.steps_rows = 0
        self.steps_statements: list = []

    def execute(self, sql, parameters=()):
        rows = self._conn.execute(sql, parameters).fetchall()
        if STEPS_READ_RE.search(str(sql)):
            self.steps_statements.append(str(sql))
            self.steps_rows += len(rows)
        return _Rows(rows)

    def __getattr__(self, name):
        return getattr(self._conn, name)


# --- прежний способ чтения журнала -------------------------------------

def old_task_steps(conn, task_id: str) -> list:
    """Журнал ОДНОЙ задачи полной выборкой — прежнее чтение пульта
    (`store.task_steps` до этой задачи), сырым SQL."""
    return conn.execute(
        "SELECT * FROM steps WHERE task_id=? ORDER BY id",
        (task_id,)).fetchall()


def old_all_steps(conn, tasks: list) -> list:
    """Прежний `report._all_steps`: выборка на каждую задачу + сортировка
    склеенного списка по `id` в Python."""
    steps: list = []
    for row in tasks:
        steps.extend(old_task_steps(conn, row["id"]))
    steps.sort(key=lambda r: r["id"])
    return steps


def old_map_size_entries(conn, target: str) -> list:
    """Прежний `report._map_size_entries`: выборка на каждую задачу
    target'а, отбор записей «карта: размер» и разбор их JSON в Python."""
    entries: list = []
    for row in store.all_tasks(conn):
        if row["target"] != target:
            continue
        for step in old_task_steps(conn, row["id"]):
            if step["action"] != report.MAP_SIZE_ACTION:
                continue
            try:
                detail = json.loads(step["detail"])
            except (TypeError, ValueError):
                continue
            entries.append((step["id"], {**detail, "ts": step["ts"]}))
    entries.sort(key=lambda pair: pair[0])
    return [detail for _, detail in entries]


@contextmanager
def old_journal_reading():
    """Контекст, в котором `report` читает журнал ПРЕЖНИМ способом.

    Отдаёт список имён подменённых функций в порядке их вызова: по нему
    тест убеждается, что эталон действительно прошёл через обе точки,
    названные требованием 3 SPEC, — подмена, которую никто не позвал,
    сравнивала бы новый HTML сам с собой.
    """
    calls: list = []

    def all_steps(conn, tasks):
        calls.append("_all_steps")
        return old_all_steps(conn, tasks)

    def map_size_entries(conn, target):
        calls.append("_map_size_entries")
        return old_map_size_entries(conn, target)

    with mock.patch.object(report, "_all_steps", all_steps), \
         mock.patch.object(report, "_map_size_entries", map_size_entries):
        yield calls


def old_emit_steps_output(conn, task_id: str, events: set, known: int) -> str:
    """Вывод, который ПРЕЖНИЙ `watch._emit_steps` печатал на этой БД:
    полная история задачи из SQL, фильтр `id > known` в Python, печать
    теми же `watch._matches_class`/`watch._print_line`."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        for row in old_task_steps(conn, task_id):
            if row["id"] <= known:
                continue
            if watch._matches_class(row["action"], row["detail"], events):
                watch._print_line(row["ts"], task_id, row["actor"],
                                  row["action"], row["detail"])
    return buf.getvalue()


# --- журнал-фикстура ----------------------------------------------------

#: Роль и модель строки «agent cost KNOWN» фикстуры — панель токенов
#: отчёта разбирает именно такую строку (`spend.known_cost_breakdown`).
KNOWN_COST_MODEL = "planka-model-x"
KNOWN_COST_KINDS = ("input", "output", "cache_write", "cache_read")


def known_cost_detail(usd: float, tokens: dict) -> str:
    """Деталь записи «agent cost KNOWN» — тем форматом, которым её пишет
    `spend.charge_step` (копия формата фикстуры `tests/test_report.py`:
    планка не вправе зависеть от приватных помощников чужого теста)."""
    by_kind = ", ".join(f"{kind}={tokens[kind]}" for kind in KNOWN_COST_KINDS)
    return (f"попытка 1/1, model={KNOWN_COST_MODEL}, provider=planka-cli: "
            f"стоимость ${usd:.4f}, токенов {sum(tokens.values())}, "
            f"источник=факт CLI, разбивка по видам: {by_kind} | "
            f"actual_usd={usd!r}")


def map_size_detail(bytes_total: int) -> str:
    """Деталь записи «карта: размер» — те же ключи, что кладёт
    `fsm_postmerge._journal_map_size` (`codebase_map.map_stats` + `sha`);
    их читает и таблица ряда, и оценка стоимости карты в `report`."""
    return json.dumps(
        {"bytes_total": bytes_total, "sections_total": 12,
         "bytes_by_dir": {"orchestrator": bytes_total // 2,
                          "docs": bytes_total // 2},
         "sha": "0" * 40},
        ensure_ascii=False, separators=(",", ":"))


#: Второй target песочной БД: ряд «карта: размер» отчёта строится ПО
#: TARGET'У (`report._map_size_entries` принимает его параметром), и на БД
#: с единственным target'ом потеря этого фильтра была бы не наблюдаема.
SECOND_TARGET = "planka-vtoroy-target"


class JournalSandbox(SchemaConnTmpRootTest):
    """БД пульта со схемой + журнал нескольких задач + сборка HTML отчёта
    так же, как её делает `report.cmd_report`.

    Задачи заводятся по одному образцу (`seed_tasks`): у каждой — переходы
    состояний обоих актёров, отказ перехода, шаг агента, строка стоимости
    шага и запись «карта: размер». Такой журнал задевает ВСЕ блоки
    отчёта, которые читают `steps` (борд, закрытые задачи, доли гейтов,
    журнал Оператора по дням, трение, панель токенов, ряд роста карты) —
    иначе побайтное сравнение AC-4 сравнивало бы пустые таблицы.

    Задачи чередуют два target'а и два состояния: и ряд роста карты, и
    таблица закрытых задач обязаны отобрать своё подмножество записей, а
    не всё, что нашлось в журнале.
    """

    def setUp(self):
        super().setUp()
        self.seeded = 0

    def seed_tasks(self, count: int) -> list:
        """Заводит `count` новых задач с журналом каждая; возвращает их id."""
        created = []
        for _ in range(count):
            self.seeded += 1
            task_id = f"01M3GKPLANKA{self.seeded:013d}"
            state = "done" if self.seeded % 3 == 0 else "in_dev"
            target = config.DEFAULT_TARGET if self.seeded % 2 else SECOND_TARGET
            store.insert_task(self.conn, task_id, f"Задача планки {task_id}",
                              state, f"task/{task_id.lower()}-planka",
                              target, 25.0)
            self.conn.execute(
                "UPDATE tasks SET spent_usd=?, review_iters=?, diff_bytes=?"
                " WHERE id=?", (1.5 * self.seeded, self.seeded % 3,
                                1024 * self.seeded, task_id))
            self.conn.commit()
            self.seed_journal(task_id)
            created.append(task_id)
        return created

    def seed_journal(self, task_id: str) -> None:
        """Журнал одной задачи — записи всех классов, которые читает отчёт."""
        store.journal(self.conn, task_id, "autogate", "state -> review",
                      "автогейт планки")
        store.journal(self.conn, task_id, "operator", "state -> merge_gate",
                      "гейт Оператора планки")
        store.journal(self.conn, task_id,
                      "fsm", f"{store.REFUSAL_ACTION_PREFIX}: планка",
                      "отказ перехода планки")
        store.journal(self.conn, task_id, "developer", "agent run завершён",
                      "шаг агента планки")
        store.journal(self.conn, task_id, "developer",
                      spend.KNOWN_COST_JOURNAL_ACTION,
                      known_cost_detail(0.75, dict(zip(KNOWN_COST_KINDS,
                                                       (11, 13, 17, 19)))))
        store.journal(self.conn, task_id, "orchestrator",
                      report.MAP_SIZE_ACTION,
                      map_size_detail(100_000 + 1_000 * self.seeded))

    # -- сборка отчёта ---------------------------------------------------

    def report_frame(self) -> dict:
        """Части отчёта, НЕ зависящие от способа чтения журнала, снятые
        ОДИН раз.

        `report.token_rate_divergence` не только читает БД, но и поднимает
        алерт расхождения курса (осознанное исключение из read-only, так
        описано в докстринге `report.cmd_report`) — второй её вызов менял
        бы список открытых алертов, а вместе с ним и HTML, то есть шумел
        бы в побайтном сравнении AC-4 причиной, к чтению журнала
        отношения не имеющей.
        """
        return {
            "tasks": store.all_tasks(self.conn),
            "divergence": report.token_rate_divergence(self.conn),
            "alerts": store.open_alerts(self.conn),
            "total_spent": store.total_spent(self.conn),
            "total_estimate": store.total_estimate(self.conn),
        }

    def report_html(self, frame: dict) -> str:
        """HTML отчёта той же сборкой, что и `report.cmd_report`, но без
        записи файла: предмет критериев — сам документ, а не путь к нему.
        """
        steps = report._all_steps(self.conn, frame["tasks"])
        map_growth_html = report._map_growth_html(self.conn, frame["tasks"])
        return report._render(frame["tasks"], steps, frame["alerts"],
                              frame["total_spent"], frame["total_estimate"],
                              frame["divergence"], map_growth_html)


# --- канарейка: заглушка локального резолва ревизии ---------------------

#: Полный sha, в который резолвится короткий `--sha` планки, и его
#: короткая запись — ровно тот случай БД пульта, который назвал «Контекст»
#: SPEC (прогоны 26.09 записали короткие строки `main_sha`).
FULL_SHA = "3f2a9c1d8e7b6a5f4e3d2c1b0a99887766554433"
SHORT_SHA = FULL_SHA[:7]

#: Голова главной копии, ОТЛИЧНАЯ от `FULL_SHA` — нужна там, где тест
#: обязан различить «разрешил короткий sha» и «свалился на head_sha()».
OTHER_HEAD_SHA = "11223344556677889900aabbccddeeff00112233"

#: sha, которого в локальной базе нет вовсе (AC-8).
UNKNOWN_SHA = "deadbee"

POOL_TEMPLATE_TITLE = "planka-indeksa-zhurnala"
POOL_TEMPLATE_TEXT = (
    "# Синтетическое ТЗ планки 01M3GKJFN90ATK2KECNDZXPPP6\n\n"
    f"{canary.MARK_EXPECT_ESCALATION_NO}\n\n"
    "Поправь одну строку и остановись.\n")


def fake_local_git(resolved: dict, head: str, calls: list | None = None):
    """Заглушка `gitcmd.git`, у которой есть ТОЛЬКО локальная база.

    `rev-parse` отвечает по словарю `resolved` (ревизия -> полный sha),
    `HEAD` — значением `head`; ревизия вне словаря — ненулевой код и текст
    `fatal:`, как у настоящего `git rev-parse --verify` на неизвестном
    объекте. Суффикс `^{commit}` и флаги (`--verify`, `--quiet`) не мешают
    разбору: планка не диктует точную форму вызова, она диктует его
    локальность. Остальные подкоманды — чистый исход, а их аргументы
    доезжают в `calls` (там тест сверяет, что `reset --hard` не звучал).
    """
    def fake(*args: str) -> subprocess.CompletedProcess:
        if calls is not None:
            calls.append(list(args))
        if args and args[0] == "rev-parse":
            for arg in args[1:]:
                if arg.startswith("-"):
                    continue
                revision = arg.split("^")[0]
                if revision == "HEAD":
                    return subprocess.CompletedProcess(
                        list(args), 0, head + "\n", "")
                if revision in resolved:
                    return subprocess.CompletedProcess(
                        list(args), 0, resolved[revision] + "\n", "")
                return subprocess.CompletedProcess(
                    list(args), 128, "",
                    f"fatal: needed a single revision: {arg}\n")
        return subprocess.CompletedProcess(list(args), 0, "", "")
    return fake


#: Метрики канареечной задачи-фикстуры: штатный исход без расхождения
#: маркера — на нём `_record_canary_run` пишет строку `canary_runs`.
FIXTURE_METRICS = {
    "steps": 5,
    "cost_usd": 1.25,
    "review_iterations": 1,
    "escalations": [],
    "outcome": "killed",
    "kill_note": "",
    "test_author_visited": True,
    "dev_retries": 0,
}


class CanaryShaSandbox(TmpRootTest):
    """Пульт во временном каталоге: БД со схемой, пул из одного шаблона,
    подменённый `canary._pool_dir`.

    Настоящий git не нужен: локальный резолв ревизии даёт заглушка
    `fake_local_git`, а эфемерный клон не создаётся ни в одном приёме —
    оба приёма ниже перехватывают его точку входа (`canary.
    _ephemeral_clone`), так что ни `git clone`, ни живой CLI провайдера не
    запускаются.
    """

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.pool_dir = self.root / "planka-pool"
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        (self.pool_dir / f"{POOL_TEMPLATE_TITLE}.md").write_text(
            POOL_TEMPLATE_TEXT, encoding="utf-8")
        patcher = mock.patch.object(canary, "_pool_dir", lambda: self.pool_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    # -- отказ до клона ---------------------------------------------------

    def refuse_explicit_sha(self, sha: str) -> str:
        """Текст именованного отказа `canary.cmd_canary` на явном `--sha`,
        снятый вместе с двумя фактами «до клона»: точка эфемерного клона
        (внутри неё и живёт `git clone`) не входилась ни разу, `git clone`
        не запускался подпроцессом, строка задачи не заведена.

        Запрет выражен исключением в самих подменах, а не проверкой
        задним числом: сработавший запрет обязан назвать, ЧТО случилось
        раньше отказа, — иначе диагноз пришлось бы восстанавливать по
        пустому списку.
        """
        real_run = canary.subprocess.run

        def forbidden_clone(*args, **kwargs):
            raise AssertionError(
                "эфемерный клон создан ДО отказа по явному --sha: "
                "нерезолвимый sha обязан остановить команду раньше клона")

        def watched_run(cmd, *args, **kwargs):
            argv = list(cmd) if not isinstance(cmd, str) else [cmd]
            if argv[:2] == ["git", "clone"]:
                raise AssertionError(
                    "git clone запущен ДО отказа по явному --sha")
            return real_run(cmd, *args, **kwargs)

        def forbidden_cmd_new(*args, **kwargs):
            raise AssertionError(
                "задача заведена ДО отказа по явному --sha")

        with mock.patch.object(canary, "_ephemeral_clone", forbidden_clone), \
             mock.patch.object(canary.subprocess, "run", watched_run), \
             mock.patch.object(canary.catalog, "cmd_new", forbidden_cmd_new), \
             mock.patch.object(canary.gitcmd, "git",
                               fake_local_git({}, OTHER_HEAD_SHA)):
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stdout(io.StringIO()):
                    canary.cmd_canary(k=1, sha=sha)

        self.assertEqual(
            [], store.all_tasks(self.conn),
            "строка задачи осталась в БД после отказа по явному --sha")
        return str(ctx.exception)

    # -- полный прогон без клона ------------------------------------------

    def run_canary(self, sha: str, head: str = OTHER_HEAD_SHA) -> str:
        """Полный `canary.cmd_canary` на явном `--sha`, где ФАЗА 1
        (`canary._run_task_in_ephemeral_clone` — клон, заведение и
        вождение задачи) подменена фикстурой штатного исхода.

        Фазы записи прогона (`_record_canary_run`) и сверки с бейзлайном
        идут настоящими: предмет критерия — строка `canary_runs`, которую
        пишет именно они. Возвращает напечатанный вывод команды.
        """
        task_id = "01M3GKPLANKAKANAREJKA000001"

        def fake_phase_one(template_path, run_stamp, explicit_target_sha,
                           outer_root, layer_text=None):
            return (task_id, POOL_TEMPLATE_TITLE, False, [], FIXTURE_METRICS,
                    False, False, True, None)

        buf = io.StringIO()
        with mock.patch.object(canary, "_run_task_in_ephemeral_clone",
                               fake_phase_one), \
             mock.patch.object(canary.gitcmd, "git",
                               fake_local_git({SHORT_SHA: FULL_SHA}, head)):
            with redirect_stdout(buf):
                canary.cmd_canary(k=1, sha=sha)
        return buf.getvalue()

    def canary_run_rows(self) -> list:
        """Строки `canary_runs` этой БД в порядке записи."""
        return store.db().execute(
            "SELECT * FROM canary_runs ORDER BY id").fetchall()
