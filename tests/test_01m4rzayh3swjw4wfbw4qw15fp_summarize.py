"""Сводка метрики разведки роли — `explore_metric.summarize`.

Функция сводки принимает строки журнала (доступ по ключу), текущий момент,
число суток и роли и возвращает «роль → показатели»: число шагов и первых
прогонов, шаги Codex, медианы вызовов до первой правки кода и до первой
записи любого вида, долю разведки, счётчики «правок не распознано»,
«записей вне рабочей копии», «логов не найдено», топ чтений и искомых строк.
Логи шагов — синтетические файлы во временном каталоге, строки журнала —
словари; ни настоящих `.artel/logs`, ни `state.db` тест не читает. Номера
задач, числа вызовов и часть путей — случайные; зерно печатается и входит
в текст провала.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/explore_metric.py ещё нет — имя `explore_metric` равно None, каждый тест падает на обращении к `summarize`.
"""
import ast
import inspect
import json
import random
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from orchestrator import retro
from orchestrator.providers import claude, codex

try:
    from orchestrator import explore_metric
except ImportError:  # модуля ещё нет: тесты красны, сбор файла цел
    explore_metric = None

LIMIT = claude.TOOL_ARGUMENT_LIMIT
PREFIX = claude.TOOL_CALL_LINE_PREFIX
STARTED = "agent run started"
KNOWN, PARTIAL = retro.TOKEN_JOURNAL_ACTIONS
CLAUDE = claude.CLI_NAME
CODEX = codex.CLI_NAME

#: Имя каталога документов задачи в рабочей копии — форма пути в логе,
#: которую метрика разбирает (не адрес документов этой задачи).
DOCS_DIR = "tasks"
DOCS_LABEL = "<документы задачи>"
HOME = "/u"
PROJECT = "p"
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
NOW = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
JOURNAL_COLUMNS = {"id", "task_id", "ts", "actor", "action", "detail"}
SUMMARY_KEYS = {
    "steps", "first_runs", "codex_steps", "median_calls",
    "median_to_code_edit", "no_code_edit", "median_to_write", "no_write",
    "share", "no_boundary", "unrecognized_edits", "outside_writes",
    "logs_missing", "top_reads", "truncated_reads", "reads_total",
    "top_searches",
}


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%SZ")


def wt_new(tid: str, rel: str) -> str:
    """Рабочая копия в текущей раскладке пульта."""
    return f"{HOME}/.artel/projects/{PROJECT}/worktrees/{tid}/{rel}"


def wt_old(tid: str, rel: str) -> str:
    """Рабочая копия в старой раскладке пульта."""
    return f"{HOME}/.artel/worktrees/{tid}/{rel}"


def docs_abs(tid: str, rel: str) -> str:
    """Каталог документов задачи в текущей раскладке пульта."""
    return f"{HOME}/.artel/projects/{PROJECT}/{DOCS_DIR}/{tid}/{rel}"


def docs_in_wt(tid: str, rel: str) -> str:
    """Путь документа задачи внутри рабочей копии (без префикса формы)."""
    return f"{DOCS_DIR}/{tid}/{rel}"


def file_change(*paths: str) -> str:
    """Аргумент `file_change` так, как его рисует лог Codex: JSON-перечень
    правок с сортированными ключами."""
    return json.dumps([{"kind": "update", "path": p} for p in paths],
                      ensure_ascii=False, sort_keys=True)


def exact_rel(prefix: str, length: int, stem: str = "orchestrator/") -> str:
    """Относительный путь, с которым `prefix + путь` ровно `length` символов."""
    filler = length - len(prefix) - len(stem) - len(".py")
    assert filler > 0, (prefix, length)
    return f"{stem}{'f' * filler}.py"


def reads(count: int, tag: str) -> list:
    return [("Read", f"wt:src/{tag}_{i}.py") for i in range(count)]


class TrackedRow:
    """Строка журнала с доступом по ключу, запоминающая прочитанные колонки."""

    def __init__(self, fields: dict, seen: set):
        self.fields = fields
        self.seen = seen

    def __getitem__(self, key):
        self.seen.add(key)
        return self.fields[key]

    def keys(self):
        return list(self.fields)


class SummaryCase(unittest.TestCase):
    """Журнал и логи сценария во временном каталоге."""

    def setUp(self):
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.rows = []

    def msg(self, extra: str = "") -> str:
        return f"зерно: {self.seed}; {extra}"

    def tid(self) -> str:
        return "01M9" + "".join(self.rng.choice(ALPHABET) for _ in range(22))

    def add_row(self, task: str, actor: str, action: str, detail: str,
                moment: datetime) -> None:
        self.rows.append({"id": len(self.rows) + 1, "task_id": task,
                          "ts": stamp(moment), "actor": actor,
                          "action": action, "detail": detail})

    def write_log(self, path: Path, calls) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["старт шага роли"]
        for name, arg in calls:
            lines.append(f"{PREFIX}{name} {arg}")
            lines.append("  вывод инструмента")
        lines.append("шаг завершён")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def started_detail(self, log) -> str:
        log_part = f"лог: {log}, " if log is not None else ""
        return (f"попытка 1/1, model=fixture-model, {log_part}"
                f"промпт: {self.dir / 'prompt.md'}, окружение: fixture")

    def step(self, task: str, role: str, calls, *, n: int = 1,
             ago: timedelta = HOUR, provider: str | None = None,
             cost_action: str = KNOWN, log_dir: Path | None = None) -> Path:
        """Шаг роли: лог `<задача>-<роль>-<n>.log`, запись «agent run
        started» и, если назван провайдер, запись стоимости за ней."""
        path = self.write_log((log_dir or self.dir) / f"{task}-{role}-{n}.log",
                              calls)
        self.add_row(task, role, STARTED, self.started_detail(path), NOW - ago)
        if provider is not None:
            self.add_row(task, role, cost_action,
                         f"попытка 1/1, model=fixture-model, provider={provider}: "
                         f"стоимость $0.0100", NOW - ago)
        return path

    def summary(self, roles, days: int = 7, rows=None, now: datetime = NOW) -> dict:
        return explore_metric.summarize(
            list(self.rows if rows is None else rows), now, days, list(roles))

    def role(self, role: str, **kwargs) -> dict:
        return self.summary([role], **kwargs)[role]


class SummaryContractTest(SummaryCase):
    """AC-1: контракт функции сводки и независимость модуля."""

    def test_ac1_module_imports_neither_report_nor_artel(self):
        """Модуль сводки читается как текст и разбирается деревом Python.

        Ни одна инструкция импорта не называет модули `report` и `artel`
        пакета пульта (ни `from . import report`, ни `from orchestrator
        import artel`, ни `import orchestrator.report`).

        Ловит мутацию: регулярное выражение пути лога взято импортом из
        `report` (`from .report import …`) вместо своего объявления — в
        дереве модуля появится импорт `report`, и тест покраснеет.
        """
        tree = ast.parse(inspect.getsource(explore_metric))
        named = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                named += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                named.append(module)
                named += [f"{module}.{alias.name}" for alias in node.names]
        forbidden = [name for name in named
                     if name.split(".")[-1] in ("report", "artel")
                     or any(part in ("report", "artel")
                            for part in name.split(".")[:-1])]
        self.assertEqual([], forbidden, "модуль сводки импортирует report/artel")

    def test_ac1_contract_keys_and_journal_columns_read(self):
        """Строки журнала с лишними колонками отданы функции сводки.

        Параметры `steps, now, days, roles` у функции есть; результат —
        словарь по каждой роли со всеми ключами показателей; у строк
        прочитаны только колонки `id, task_id, ts, actor, action, detail`
        (лишние `target`, `session_id` не тронуты).

        Ловит мутацию: функция читает `row["target"]` (или копирует строку
        целиком `dict(row)`) — множество прочитанных колонок выйдет за
        шесть названных, и тест покраснеет; потерянный ключ показателя
        (например, `no_write`) — тоже.
        """
        parameters = inspect.signature(explore_metric.summarize).parameters
        for name in ("steps", "now", "days", "roles"):
            self.assertIn(name, parameters)
        task = self.tid()
        self.step(task, "developer",
                  reads(self.rng.randint(1, 5), "a") + [("Edit", "wt:a.py")],
                  provider=CLAUDE)
        self.step(task, "analyst", reads(2, "b") + [("Write", "docs:PLAN.md")])
        seen: set = set()
        rows = [TrackedRow({**row, "target": "artel", "session_id": "s"}, seen)
                for row in self.rows]

        result = explore_metric.summarize(rows, NOW, 7, ["developer", "analyst"])

        for role in ("developer", "analyst"):
            self.assertLessEqual(SUMMARY_KEYS, set(result[role]),
                                 self.msg(f"ключи показателей {role}"))
        self.assertLessEqual(seen, JOURNAL_COLUMNS,
                             self.msg(f"прочитаны колонки {sorted(seen)}"))

    def test_ac1_rows_are_ordered_by_id_inside_the_function(self):
        """Журнал отдан функции в обратном порядке `id`.

        Два шага одной задачи и роли, за каждым — своя запись стоимости
        (первый — Claude, второй — Codex). Функция сама упорядочивает
        записи по `id`: шаг Codex один, чтение первого шага (Claude) в
        топе, чтение второго (Codex) — нет.

        Ловит мутацию: строки разбираются в порядке поступления, без
        сортировки по `id` — второму шагу достанется стоимость первого
        (`provider=claude`), первый останется без записи и уйдёт в Claude
        по именам вызовов: `codex_steps` станет 0, а чтение второго шага
        попадёт в топ.
        """
        task = self.tid()
        self.step(task, "developer", [("Read", "wt:src/first.py"),
                                      ("Edit", "wt:x.py")],
                  n=1, provider=CLAUDE)
        self.step(task, "developer", [("Read", "wt:src/second.py"),
                                      ("Edit", "wt:x.py")],
                  n=2, provider=CODEX)

        result = self.role("developer", rows=list(reversed(self.rows)))

        self.assertEqual(1, result["codex_steps"], self.msg())
        top = dict(result["top_reads"])
        self.assertEqual(1, top.get("src/first.py"), self.msg(str(top)))
        self.assertNotIn("src/second.py", top, self.msg(str(top)))

    def test_ac1_log_path_with_space_and_comma_is_read(self):
        """Лог шага лежит в каталоге, имя которого несёт пробел и запятую.

        Путь из записи «agent run started» разобран целиком: лог прочитан
        (логов не найдено — 0), его вызовы посчитаны.

        Ловит мутацию: путь лога выделяется до первой запятой или первого
        пробела (а не до «, промпт: », как у `report._LOG_PATH_RE`) — лог
        не найдётся, `logs_missing` станет 1, а медиана вызовов — `None`.
        """
        calls = reads(self.rng.randint(1, 6), "c") + [("Edit", "wt:a.py")]
        self.step(self.tid(), "developer", calls,
                  log_dir=self.dir / "лог с пробелом, и запятой")

        result = self.role("developer")

        self.assertEqual(0, result["logs_missing"], self.msg())
        self.assertEqual(1, result["steps"], self.msg())
        self.assertEqual(len(calls), result["median_calls"], self.msg())


class StepSelectionTest(SummaryCase):
    """AC-2: шаги — только из записей «agent run started»."""

    def test_ac2_command_log_not_named_by_a_record_is_ignored(self):
        """Рядом с логом шага лежит `<id>-auto-1.log` с теми же строками.

        Журнал команды пульта несёт те же вызовы и одно своё чтение, но ни
        одна запись «agent run started» его не называет: шаг один, число
        вызовов — как в логе шага, чтения журнала команды в топе нет.

        Ловит мутацию: логи перебираются маской каталога `<id>-*.log` —
        журнал команды станет вторым шагом (`steps` 2), а его чтение
        `src/auto_only.py` попадёт в топ.
        """
        task = self.tid()
        calls = reads(self.rng.randint(1, 4), "d") + [("Edit", "wt:a.py")]
        self.step(task, "developer", calls)
        self.write_log(self.dir / f"{task}-auto-1.log",
                       calls + [("Read", "wt:src/auto_only.py")])

        result = self.role("developer")

        self.assertEqual(1, result["steps"], self.msg())
        self.assertEqual(len(calls), result["median_calls"], self.msg())
        self.assertNotIn("src/auto_only.py", dict(result["top_reads"]),
                         self.msg())

    def test_ac2_same_log_path_is_counted_once(self):
        """Две записи «agent run started» называют один и тот же лог.

        Шаг считается один раз: `steps` 1, чтения лога в топе — по разу.

        Ловит мутацию: повторный путь лога не отбрасывается — шагов
        станет 2, а каждое чтение посчитано дважды.
        """
        task = self.tid()
        path = self.step(task, "developer",
                         [("Read", "wt:src/once.py"), ("Edit", "wt:a.py")])
        self.add_row(task, "developer", STARTED, self.started_detail(path),
                     NOW - HOUR)

        result = self.role("developer")

        self.assertEqual(1, result["steps"], self.msg())
        self.assertEqual(1, dict(result["top_reads"]).get("src/once.py"),
                         self.msg())

    def test_ac2_first_run_is_taken_from_log_number(self):
        """Первый прогон — `<n>` = 1 в имени лога, а не первая запись журнала.

        Задача A: прогоны 1 и 2; задача B: только прогон 2 (первый вне
        журнала); задача C: запись прогона 3 стоит в журнале раньше записи
        прогона 1. Первых прогонов ровно два — A-1 и C-1.

        Ловит мутацию: первым прогоном считается первая запись задачи и
        роли в журнале — B-2 и C-3 станут первыми, A-1 и C-1 нет; счёт
        сменится, а если считать «первым» и то и другое — станет больше
        двух.
        """
        a, b, c = self.tid(), self.tid(), self.tid()
        edit = [("Edit", "wt:a.py")]
        self.step(a, "developer", edit, n=1)
        self.step(a, "developer", edit, n=2)
        self.step(b, "developer", edit, n=2)
        self.step(c, "developer", edit, n=3)
        self.step(c, "developer", edit, n=1)

        result = self.role("developer")

        self.assertEqual(5, result["steps"], self.msg())
        self.assertEqual(2, result["first_runs"], self.msg())


class PeriodTest(SummaryCase):
    """AC-3: граница периода — полная метка `ts`, включительно."""

    def test_ac3_period_boundary_uses_full_timestamp(self):
        """Три шага у границы периода случайной длины N суток.

        Шаг ровно N суток назад и шаг на секунду моложе входят; шаг на
        секунду старше — в ту же календарную дату — не входит.

        Ловит мутацию: период сравнивается по дате (`ts[:10]`) — шаг на
        секунду старше границы войдёт (`steps` 3 и его чтение в топе);
        строгое `>` вместо `>=` — выпадет шаг ровно N суток назад.
        """
        days = self.rng.randint(1, 30)
        now = datetime(2026, 10, 13, self.rng.randint(1, 22),
                       self.rng.randint(0, 59), self.rng.randint(1, 58),
                       tzinfo=timezone.utc)
        cases = {"exact": timedelta(days=days),
                 "younger": timedelta(days=days) - timedelta(seconds=1),
                 "older": timedelta(days=days) + timedelta(seconds=1)}
        for name, ago in cases.items():
            path = self.write_log(self.dir / f"{name}-developer-1.log",
                                  [("Read", f"wt:src/{name}.py"),
                                   ("Edit", "wt:a.py")])
            self.add_row(self.tid(), "developer", STARTED,
                         self.started_detail(path), now - ago)
        older_ts = self.rows[-1]["ts"]
        cutoff = stamp(now - timedelta(days=days))
        self.assertEqual(cutoff[:10], older_ts[:10], "фикстура: та же дата")

        result = self.role("developer", days=days, now=now)

        top = dict(result["top_reads"])
        self.assertEqual(2, result["steps"], self.msg(f"N={days}"))
        self.assertIn("src/exact.py", top, self.msg(f"N={days}"))
        self.assertIn("src/younger.py", top, self.msg(f"N={days}"))
        self.assertNotIn("src/older.py", top, self.msg(f"N={days}"))


class MissingLogsTest(SummaryCase):
    """AC-4: лог не найден — счётчик, не падение."""

    def test_ac4_missing_or_unreadable_logs_are_counted(self):
        """Запись без пути лога, путь к отсутствующему файлу и каталог на
        месте файла.

        Сводка не падает; «логов не найдено» — 3; обычный шаг рядом
        посчитан как обычно.

        Ловит мутацию: `OSError` чтения каталога (или отсутствующего
        файла) не перехвачен — сводка упадёт `IsADirectoryError`/
        `FileNotFoundError`; запись без пути пропущена молча — счётчик
        станет 2.
        """
        self.add_row(self.tid(), "developer", STARTED,
                     self.started_detail(None), NOW - HOUR)
        self.add_row(self.tid(), "developer", STARTED,
                     self.started_detail(self.dir / "gone-developer-1.log"),
                     NOW - HOUR)
        folder = self.dir / "folder-developer-1.log"
        folder.mkdir()
        self.add_row(self.tid(), "developer", STARTED,
                     self.started_detail(folder), NOW - HOUR)
        self.step(self.tid(), "developer",
                  [("Read", "wt:src/ok.py"), ("Edit", "wt:a.py")])

        result = self.role("developer")

        self.assertEqual(3, result["logs_missing"], self.msg())
        self.assertEqual(1, dict(result["top_reads"]).get("src/ok.py"),
                         self.msg())


class PathClassTest(SummaryCase):
    """AC-5: нормализация пути и класс правки."""

    def expect_class(self, kind: str, tool: str, arg: str, before: int,
                     result: dict, label: str) -> None:
        msg = self.msg(f"{label}: {tool} {arg!r}")
        self.assertEqual(0, result["unrecognized_edits"], msg)
        self.assertEqual(before, result["median_to_write"], msg)
        if kind == "code":
            self.assertEqual(0, result["no_code_edit"], msg)
            self.assertEqual(before, result["median_to_code_edit"], msg)
            self.assertEqual(0, result["outside_writes"], msg)
        else:
            self.assertEqual(1, result["no_code_edit"], msg)
            self.assertIsNone(result["median_to_code_edit"], msg)
            self.assertEqual(1 if kind == "outside" else 0,
                             result["outside_writes"], msg)

    def test_ac5_path_forms_give_code_doc_or_outside(self):
        """Шаг developer: случайное число чтений, одна правка, чтение после.

        Каждая форма пути перебирается каждым инструментом правки (Edit,
        Write, MultiEdit, `file_change` — где аргумент короче предела):
        `wt:` и абсолютный путь рабочей копии обеих раскладок — правка
        кода; путь рабочей копии на каталог документов (обе раскладки),
        `docs:PLAN.md` и абсолютный путь каталога документов — запись
        документа; временный каталог и главная копия — запись вне рабочей
        копии.

        Ловит мутацию: путь рабочей копии на каталог документов засчитан
        правкой кода (или `docs:` принят за путь рабочей копии) — у формы
        «документ» `no_code_edit` станет 0; MultiEdit или `file_change` не
        признан правкой — у формы «код» `median_to_write` станет `None`;
        старая раскладка `.artel/worktrees/<id>/` не распознана — правка
        уйдёт во «вне рабочей копии».
        """
        tid = self.tid()
        forms = (
            ("code", "wt:orchestrator/x.py"),
            ("code", wt_new(tid, "orchestrator/x.py")),
            ("code", wt_old(tid, "orchestrator/x.py")),
            ("code", wt_new(tid, "x.py")),
            ("doc", wt_new(tid, docs_in_wt(tid, "PLAN.md"))),
            ("doc", wt_old(tid, docs_in_wt(tid, "PLAN.md"))),
            ("doc", "docs:PLAN.md"),
            ("doc", docs_abs(tid, "PLAN.md")),
            ("outside", "/tmp/scratch/x.py"),
            ("outside", f"{HOME}/orchestrator/x.py"),
        )
        covered = set()
        for kind, path in forms:
            for tool in ("Edit", "Write", "MultiEdit", "file_change"):
                arg = file_change(path) if tool == "file_change" else path
                if len(arg) >= LIMIT:
                    continue
                covered.add((kind, tool))
                with self.subTest(kind=kind, tool=tool, path=path):
                    self.rows = []
                    before = self.rng.randint(1, 6)
                    self.step(tid, "developer",
                              reads(before, "e") + [(tool, arg)]
                              + reads(1, "after"))
                    self.expect_class(kind, tool, arg, before,
                                      self.role("developer"), kind)
        for kind in ("code", "doc", "outside"):
            self.assertIn((kind, "file_change"), covered, "фикстура")

    def test_ac5_file_change_takes_first_visible_path(self):
        """Перечень `file_change` с двумя правками.

        Класс берётся по первому полю `path`: код, затем вне рабочей копии
        — правка кода; вне рабочей копии, затем код — запись вне рабочей
        копии.

        Ловит мутацию: берётся последнее (или любое кодовое) поле `path`
        перечня — первый случай останется кодом, а второй станет правкой
        кода (`no_code_edit` 0 вместо 1).
        """
        tid = self.tid()
        for first_kind, paths in (("code", ("wt:a.py", "/tmp/b.py")),
                                  ("outside", ("/tmp/b.py", "wt:a.py"))):
            with self.subTest(first=first_kind):
                self.rows = []
                arg = file_change(*paths)
                self.assertLess(len(arg), LIMIT, "фикстура")
                self.step(tid, "developer",
                          reads(2, "g") + [("file_change", arg)])
                self.expect_class(first_kind, "file_change", arg, 2,
                                  self.role("developer"), first_kind)


class TruncatedEditTest(SummaryCase):
    """AC-6: правка с усечённым значением."""

    def padded_segment(self, tid: str, length: int) -> str:
        """Абсолютный путь, у которого `/worktrees/<id>/` кончается ровно на
        символе `length`."""
        tail = f"/.artel/projects/{PROJECT}/worktrees/{tid}/"
        filler = length - len(HOME) - 1 - len(tail)
        self.assertGreater(filler, 0, "фикстура")
        return f"{HOME}/{'d' * filler}{tail}"

    def cases(self, tid: str) -> list:
        long_tail = f"{HOME}/{'d' * 60}/.artel/projects/{PROJECT}/worktrees/{tid}/x.py"
        segment = f"/worktrees/{tid}/"
        no_segment = long_tail[:LIMIT]
        self.assertNotIn(segment, no_segment, "фикстура")
        tas = (self.padded_segment(tid, LIMIT - 3)
               + docs_in_wt(tid, "PLAN.md"))[:LIMIT]
        self.assertTrue(tas.endswith(f"{segment}tas"), "фикстура")
        empty = (self.padded_segment(tid, LIMIT) + "orchestrator/x.py")[:LIMIT]
        self.assertTrue(empty.endswith(segment), "фикстура")
        old_change = file_change(long_tail)[:LIMIT]
        self.assertNotIn(segment, old_change, "фикстура")
        short_first = file_change("/tmp/a.py", long_tail)[:LIMIT]
        self.assertIn('"/tmp/a.py"', short_first, "фикстура")
        short_rest = wt_new(tid, "t")
        self.assertLess(len(short_rest), LIMIT, "фикстура")
        wt_cut = ("wt:orchestrator/" + "w" * 200 + ".py")[:LIMIT]
        docs_cut = ("docs:acceptance_tests/" + "d" * 200)[:LIMIT]
        edit = self.rng.choice(("Edit", "Write", "MultiEdit"))
        return [
            ("unrecognized", edit, no_segment),
            ("unrecognized", edit, tas),
            ("unrecognized", edit, empty),
            ("unrecognized", "file_change", old_change),
            ("unrecognized", "file_change", short_first),
            ("code", edit, short_rest),
            ("code", edit, wt_cut),
            ("docs", edit, docs_cut),
        ]

    def test_ac6_truncated_values_are_classified(self):
        """Шаг developer: случайное число чтений, затем одна правка.

        Усечённое (длиной ровно предел) значение без полного сегмента
        `/worktrees/<id>/`, с остатком «tas» или пустым остатком, усечённый
        `file_change` старой формы и усечённый `file_change` с коротким
        первым путём без сегмента — «правка не распознана»: не правка
        кода, не «вне рабочей копии», счётчик 1, но запись любого вида.
        Не усечённый `…/worktrees/<id>/t` и усечённый `wt:<путь>` — правка
        кода; усечённый `docs:<путь>` — не правка кода.

        Ловит мутацию: остаток «tas» усечённого значения классифицирован
        обычным порядком — правка кода (`no_code_edit` 0); длина меряется
        по извлечённому `path` `file_change`, а не по аргументу — короткий
        `/tmp/a.py` уйдёт во «вне рабочей копии» (`outside_writes` 1);
        короткий не усечённый остаток `t` назван «не распознана».
        """
        tid = self.tid()
        for kind, tool, arg in self.cases(tid):
            with self.subTest(kind=kind, tool=tool, arg=arg):
                self.rows = []
                before = self.rng.randint(1, 6)
                self.step(tid, "developer",
                          reads(before, "h") + [(tool, arg)] + reads(1, "after"))
                result = self.role("developer")
                msg = self.msg(f"{kind}: {tool} {arg!r}")
                self.assertEqual(before, result["median_to_write"], msg)
                if kind == "code":
                    self.assertEqual(0, result["no_code_edit"], msg)
                    self.assertEqual(before, result["median_to_code_edit"], msg)
                    self.assertEqual(0, result["unrecognized_edits"], msg)
                    continue
                self.assertEqual(1, result["no_code_edit"], msg)
                self.assertIsNone(result["median_to_code_edit"], msg)
                if kind == "unrecognized":
                    self.assertEqual(1, result["unrecognized_edits"], msg)
                    self.assertEqual(0, result["outside_writes"], msg)


class BoundaryTest(SummaryCase):
    """AC-7: «до границы» — строго до граничного вызова."""

    def test_ac7_boundary_call_is_excluded_and_write_differs_from_code(self):
        """Шаг: a чтений, запись документа, b чтений, правка кода, c чтений.

        У developer «до правки кода» — a+1+b, «до записи» — a, доля —
        (a+1+b)/всего; у analyst на том же логе доля — a/всего (граница —
        запись документа), медианы событий те же.

        Ловит мутацию: граничный вызов засчитан «до границы» (+1) или
        вызов перед ним потерян (−1) — медианы сдвинутся на единицу;
        «до первой записи» посчитано как «до правки кода» — медиана до
        записи станет a+1+b вместо a.
        """
        a, b, c = (self.rng.randint(1, 7) for _ in range(3))
        calls = (reads(a, "i") + [("Write", "docs:PLAN.md")] + reads(b, "j")
                 + [("Edit", "wt:orchestrator/x.py")] + reads(c, "k"))
        total = len(calls)
        self.step(self.tid(), "developer", calls)
        self.step(self.tid(), "analyst", calls)

        result = self.summary(["developer", "analyst"])

        for role, share in (("developer", (a + 1 + b) / total),
                            ("analyst", a / total)):
            msg = self.msg(f"{role}: a={a} b={b} c={c}")
            self.assertEqual(a + 1 + b, result[role]["median_to_code_edit"], msg)
            self.assertEqual(a, result[role]["median_to_write"], msg)
            self.assertAlmostEqual(share, result[role]["share"], msg=msg)

    def test_ac7_unrecognized_edit_bounds_analyst_not_developer(self):
        """Шаг: a чтений, нераспознанная (усечённая без сегмента) правка,
        c чтений.

        У analyst граница наступила: шагов без правки 0, доля a/всего. У
        developer — нет: шаг без правки, доля `None`.

        Ловит мутацию: нераспознанная правка не служит записью любого
        вида — у analyst шаг станет «без правки» (`no_boundary` 1, доля
        `None`); или служит правкой кода — у developer граница наступит.
        """
        tid = self.tid()
        a, c = self.rng.randint(1, 7), self.rng.randint(1, 7)
        cut = (f"{HOME}/{'d' * 80}/.artel/projects/{PROJECT}/worktrees/{tid}/"
               "orchestrator/x.py")[:LIMIT]
        calls = reads(a, "l") + [("Edit", cut)] + reads(c, "m")
        self.step(tid, "developer", calls)
        self.step(tid, "analyst", calls)

        result = self.summary(["developer", "analyst"])

        msg = self.msg(f"a={a} c={c}")
        self.assertEqual(0, result["analyst"]["no_boundary"], msg)
        self.assertAlmostEqual(a / len(calls), result["analyst"]["share"], msg=msg)
        self.assertEqual(1, result["developer"]["no_boundary"], msg)
        self.assertIsNone(result["developer"]["share"], msg)

    def test_ac7_write_boundary_roles_do_not_count_it_as_code_edit(self):
        """Шаг analyst, reviewer или spec_auditor: a чтений, запись
        документа, c чтений, правки кода нет.

        Граница роли наступила (шагов без правки 0, доля a/всего), но
        правка кода не наступила: `no_code_edit` 1, медиана до правки кода
        `None`.

        Ловит мутацию: граница роли записи взята как правка кода — у роли
        `no_code_edit` станет 0, а медиана до правки кода — a.
        """
        for role in ("analyst", "reviewer", "spec_auditor"):
            with self.subTest(role=role):
                self.rows = []
                a, c = self.rng.randint(1, 7), self.rng.randint(1, 7)
                calls = reads(a, "n") + [("Write", "docs:REVIEW.md")] + reads(c, "o")
                self.step(self.tid(), role, calls)

                result = self.role(role)

                msg = self.msg(f"{role}: a={a} c={c}")
                self.assertEqual(0, result["no_boundary"], msg)
                self.assertAlmostEqual(a / len(calls), result["share"], msg=msg)
                self.assertEqual(1, result["no_code_edit"], msg)
                self.assertIsNone(result["median_to_code_edit"], msg)


class UnknownRoleTest(SummaryCase):
    """AC-8: роль вне константы границ."""

    def test_ac8_unknown_role_gets_named_refusal(self):
        """Сводка по developer и роли со случайным именем вне константы.

        Исключения нет; у неизвестной роли — словарь с единственным ключом
        `refusal`, текст отказа называет роль; developer посчитан.

        Ловит мутацию: граница неизвестной роли берётся из словаря без
        проверки (`BOUNDARY[role]`) — сводка упадёт `KeyError`; отказ без
        имени роли — текст не назовёт её.
        """
        unknown = f"janitor_{self.rng.randrange(1 << 20):x}"
        self.step(self.tid(), "developer", [("Edit", "wt:a.py")])

        result = self.summary(["developer", unknown])

        self.assertEqual({"refusal"}, set(result[unknown]), self.msg())
        self.assertIn(unknown, result[unknown]["refusal"], self.msg())
        self.assertEqual(1, result["developer"]["steps"], self.msg())


class MedianShareTest(SummaryCase):
    """AC-9: медианы и доля по шагам с наступившим событием."""

    def test_ac9_step_without_boundary_stays_out_of_medians_and_share(self):
        """Четыре шага developer с правкой кода после 2, 4, 8 и 100 чтений
        и шаг без правки из 50 чтений; задачи случайные, порядок шагов в
        журнале случайный.

        Медиана «до правки кода» — 6 (медиана чётного набора, не среднее
        28,5); шаг без правки не входит в неё ни нулём (было бы 4), ни
        полным числом (было бы 8); доля — сумма до границы / сумма всех
        вызовов шагов с правкой (114/128), не среднее долей и без шага
        без правки в знаменателе.

        Ловит мутацию: медиана заменена средним; шаг без правки вошёл в
        медиану нулём или числом вызовов либо в знаменатель доли; доля —
        среднее долей шагов.
        """
        shapes = [(2, 8), (4, 0), (8, 2), (100, 0)]
        self.rng.shuffle(shapes)
        plan = [("edit", s) for s in shapes] + [("none", (50, 0))]
        self.rng.shuffle(plan)
        for kind, (before, after) in plan:
            calls = reads(before, "p") + reads(after, "q")
            if kind == "edit":
                calls = (reads(before, "p") + [("Edit", "wt:orchestrator/x.py")]
                         + reads(after, "q"))
            self.step(self.tid(), "developer", calls)

        result = self.role("developer")

        msg = self.msg(str(plan))
        self.assertEqual(6, result["median_to_code_edit"], msg)
        self.assertEqual(1, result["no_boundary"], msg)
        self.assertEqual(1, result["no_code_edit"], msg)
        self.assertAlmostEqual(114 / 128, result["share"], msg=msg)

    def test_ac9_event_medians_are_independent_of_role_boundary(self):
        """Четыре шага у analyst и те же четыре у developer.

        A: 2 чтения, запись документа, 3 чтения, правка кода, чтение;
        B: 4 чтения, запись документа, 15 чтений; C: 10 чтений, правка
        кода, 2 чтения; D: 30 чтений. У обеих ролей медиана до записи —
        4 (по A, B, C), до правки кода — 8 (по A, C); `no_write` 1,
        `no_code_edit` 2.

        Ловит мутацию: медиана события считается по шагам с границей роли
        — у developer медиана до записи станет 6 (только A, C), у analyst
        медиана до правки кода вберёт B нулём или числом вызовов (6 или
        10); шаг без записи вошёл в медиану до записи (3 или 7).
        """
        doc = [("Write", "docs:PLAN.md")]
        code = [("Edit", "wt:orchestrator/x.py")]
        shapes = {
            "A": reads(2, "s") + doc + reads(3, "t") + code + reads(1, "u"),
            "B": reads(4, "s") + doc + reads(15, "t"),
            "C": reads(10, "s") + code + reads(2, "t"),
            "D": reads(30, "s"),
        }
        names = list(shapes)
        self.rng.shuffle(names)
        for role in ("analyst", "developer"):
            for name in names:
                self.step(self.tid(), role, shapes[name])

        result = self.summary(["analyst", "developer"])

        for role in ("analyst", "developer"):
            msg = self.msg(f"{role}: порядок {names}")
            self.assertEqual(4, result[role]["median_to_write"], msg)
            self.assertEqual(8, result[role]["median_to_code_edit"], msg)
            self.assertEqual(1, result[role]["no_write"], msg)
            self.assertEqual(2, result[role]["no_code_edit"], msg)


class ProviderTest(SummaryCase):
    """AC-10: провайдер шага."""

    def test_ac10_provider_record_beats_call_names(self):
        """Пять шагов developer в четырёх задачах.

        T1: `command_execution` + «agent cost KNOWN» `provider=claude` —
        Claude. T2: `command_execution` без записи стоимости — Codex.
        T3: прогон 1 без записи стоимости (только Read/Edit), прогон 2 с
        `file_change` и записью `provider=codex` после него — первый
        Claude, второй Codex. T4: `command_execution` + «agent cost
        PARTIAL» `provider=claude` — Claude. Шагов Codex — 2; чтения шагов
        Codex в топ и в число чтений не попадают.

        Ловит мутацию: имена вызовов берутся приоритетно над записью
        стоимости (T1, T4 станут Codex); запись PARTIAL не учтена (T4 —
        Codex); первому прогону T3 достаётся стоимость соседа за следующим
        «agent run started» (он станет Codex, его чтение пропадёт из топа);
        шаг Codex дал чтения (`src/r2.py` в топе).
        """
        t1, t2, t3, t4 = (self.tid() for _ in range(4))
        shell = ("command_execution", "ls -la")
        code = ("Edit", "wt:orchestrator/x.py")
        self.step(t1, "developer", [("Read", "wt:src/r1.py"), shell, code],
                  provider=CLAUDE)
        self.step(t2, "developer", [("Read", "wt:src/r2.py"), shell, code])
        self.step(t3, "developer", [("Read", "wt:src/r3.py"), code], n=1)
        self.step(t3, "developer",
                  [("Read", "wt:src/r4.py"), shell,
                   ("file_change", file_change("wt:orchestrator/y.py"))],
                  n=2, provider=CODEX)
        self.step(t4, "developer", [("Read", "wt:src/r5.py"), shell, code],
                  provider=CLAUDE, cost_action=PARTIAL)

        result = self.role("developer")

        top = dict(result["top_reads"])
        self.assertEqual(2, result["codex_steps"], self.msg(str(top)))
        for path in ("src/r1.py", "src/r3.py", "src/r5.py"):
            self.assertEqual(1, top.get(path), self.msg(f"{path}: {top}"))
        for path in ("src/r2.py", "src/r4.py"):
            self.assertNotIn(path, top, self.msg(f"{path}: {top}"))
        self.assertEqual(3, result["reads_total"], self.msg())


class TopReadsTest(SummaryCase):
    """AC-11: топ чтений до границы."""

    def test_ac11_top_reads_normalized_truncated_and_bounded(self):
        """Три шага developer: новая раскладка, старая раскладка и шаг без
        правки кода.

        Один файл из двух задач и обеих раскладок (`wt:` тоже) — одна
        строка с числом 3; документы задачи из абсолютного пути, `docs:` и
        `wt:<каталог документов>/<id этой задачи>/X` — к
        `<документы задачи>/X`, путь документов другой задачи — как есть;
        чтение вне рабочей копии — абсолютным путём; аргумент длиной
        предел−1 — полный (абсолютный и `wt:`), длиной предел — обрезан и
        учтён K; Read после границы не в топе; все чтения шага без
        границы — в топе и в M.

        Ловит мутацию: путь длиной ровно предел сочтён полным (попадёт в
        топ, K станет 1) или предел−1 — обрезанным (пропадёт из топа);
        раскладки не сведены (файл даст две-три строки); Read после правки
        попал в топ; шаг без границы не дал чтений (K 2, M 13).
        """
        t1, t2, t3 = self.tid(), self.tid(), self.tid()
        other = self.tid()
        abs_prefix = wt_new(t1, "")
        full_abs_rel = exact_rel(abs_prefix, LIMIT - 1)
        cut_abs_rel = exact_rel(abs_prefix, LIMIT)
        full_wt_rel = exact_rel("wt:", LIMIT - 1)
        cut_wt_rel = exact_rel("wt:", LIMIT, stem="tests/")
        nb_cut_rel = exact_rel("wt:", LIMIT, stem="scripts/")
        code = ("Edit", "wt:orchestrator/x.py")
        self.step(t1, "developer", [
            ("Read", wt_new(t1, "orchestrator/fsm.py")),
            ("Read", docs_abs(t1, "SPEC.md")),
            ("Read", "wt:" + docs_in_wt(t1, "PLAN.md")),
            ("Read", "wt:" + docs_in_wt(other, "PLAN.md")),
            ("Read", "docs:acceptance_tests/test_x.py"),
            ("Read", "/tmp/scratch/notes.txt"),
            ("Read", abs_prefix + full_abs_rel),
            ("Read", abs_prefix + cut_abs_rel),
            ("Read", "wt:" + full_wt_rel),
            ("Read", "wt:" + cut_wt_rel),
            code,
            ("Read", "wt:orchestrator/after_boundary.py"),
        ])
        self.step(t2, "developer", [
            ("Read", wt_old(t2, "orchestrator/fsm.py")),
            ("Read", "wt:orchestrator/fsm.py"),
            ("Read", "docs:SPEC.md"),
            code,
        ])
        self.step(t3, "developer", [
            ("Read", "wt:orchestrator/nobound.py"),
            ("Write", "docs:PLAN.md"),
            ("Read", "wt:" + nb_cut_rel),
        ])
        for arg in (abs_prefix + full_abs_rel, "wt:" + full_wt_rel):
            self.assertEqual(LIMIT - 1, len(arg), "фикстура")
        for arg in (abs_prefix + cut_abs_rel, "wt:" + cut_wt_rel,
                    "wt:" + nb_cut_rel):
            self.assertEqual(LIMIT, len(arg), "фикстура")

        result = self.role("developer")

        top = dict(result["top_reads"])
        msg = self.msg(str(top))
        expected = {
            "orchestrator/fsm.py": 3,
            f"{DOCS_LABEL}/SPEC.md": 2,
            f"{DOCS_LABEL}/PLAN.md": 1,
            docs_in_wt(other, "PLAN.md"): 1,
            f"{DOCS_LABEL}/acceptance_tests/test_x.py": 1,
            "/tmp/scratch/notes.txt": 1,
            full_abs_rel: 1,
            full_wt_rel: 1,
            "orchestrator/nobound.py": 1,
        }
        for path, count in expected.items():
            self.assertEqual(count, top.get(path), f"{path}: {msg}")
        for path in (cut_abs_rel, cut_wt_rel, nb_cut_rel,
                     "orchestrator/after_boundary.py"):
            self.assertNotIn(path, top, msg)
        self.assertEqual(3, result["truncated_reads"], msg)
        self.assertEqual(15, result["reads_total"], msg)


class TopSearchesTest(SummaryCase):
    """AC-12: топ искомых строк до границы."""

    def test_ac12_search_strings_from_grep_and_bash(self):
        """Шаг developer: вызовы Grep и Bash до правки кода, Grep после.

        Grep `needle_alpha` и `grep -rn "needle_alpha"` суммируются (2);
        кавычки сняты; `git ls-files | grep needle_delta` даёт
        `needle_delta`; из `grep … && rg …` взята первая команда; значения
        `rg -t`/`--type`/`-g`/`--glob` шаблоном не считаются; шаблон без
        закрывающей кавычки и шаблон, оборванный пределом длины строки, не
        учтены; Grep после правки не в топе.

        Ловит мутацию: искомая строка взята с кавычками (`"needle_alpha"`
        отдельной строкой, у Grep-ветки 1); взята вторая команда
        (`needle_zeta`); `-t py` сочтён шаблоном (`py` в топе); оборванный
        шаблон учтён; после `|` поиск не распознан (`needle_delta` нет);
        поиск после границы попал в топ.
        """
        cut = "grep -rn needle_long"
        cut += "x" * (LIMIT - len(cut))
        calls = [
            ("Grep", "needle_alpha"),
            ("Bash", 'grep -rn "needle_alpha" orchestrator/'),
            ("Bash", "rg -t py -g '*.py' needle_beta tests"),
            ("Bash", "rg --type py --glob '*.md' needle_gamma"),
            ("Bash", "git ls-files | grep needle_delta"),
            ("Bash", "grep -n needle_eps a.py && rg needle_zeta b.py"),
            ("Bash", "cd orchestrator && grep -n 'needle_quote' fsm.py"),
            ("Bash", 'grep -rn "needle_open orchestrator/'),
            ("Bash", cut),
            ("Edit", "wt:orchestrator/x.py"),
            ("Grep", "needle_after"),
        ]
        self.assertEqual(LIMIT, len(cut), "фикстура")
        self.step(self.tid(), "developer", calls)

        result = self.role("developer")

        top = dict(result["top_searches"])
        msg = self.msg(str(top))
        expected = {"needle_alpha": 2, "needle_beta": 1, "needle_gamma": 1,
                    "needle_delta": 1, "needle_eps": 1, "needle_quote": 1}
        for needle, count in expected.items():
            self.assertEqual(count, top.get(needle), f"{needle}: {msg}")
        for key in top:
            for banned in ("needle_zeta", "needle_open", "needle_long",
                           "needle_after", '"', "'"):
                self.assertNotIn(banned, key, msg)
        for flag_value in ("py", "*.py", "*.md"):
            self.assertNotIn(flag_value, top, msg)


if __name__ == "__main__":
    unittest.main()
