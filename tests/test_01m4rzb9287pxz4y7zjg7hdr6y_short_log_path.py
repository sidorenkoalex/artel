"""Короткий путь файла в строке вызова лога шага роли (`wt:` / `docs:`): общая функция `base.short_log_path`, строки лога Claude и Codex, неизменность `ToolCall.argument` и потока событий, группы Write блока test_author отчёта.

Группа: долгоживущий

Красен до реализации: функции `base.short_log_path` ещё нет, а оба провайдера пишут путь файла в строку лога целиком и обрезают его до 100 символов — строки `· Read wt:…`/`· file_change wt:…` не получаются, подмена `base.short_log_path` падает AttributeError, а отчёт не относит `wt:tests/…`/`docs:acceptance_tests/…` к группам Write.

Поверхность — только публичная: `ClaudeProvider().parse_output_line` и
`CodexProvider().parse_output_line` (строка `stream-json` / `codex exec
--json` -> `StreamEvent`), функция `base.short_log_path`, константы
`TOOL_ARGUMENT_LIMIT`/`TOOL_CALL_LINE_PREFIX` провайдеров, отчёт
`report.cmd_report` (раздел о шагах test_author в `.artel/report.html`).

«Строка, как до задачи» считается здесь же формулой прежнего рендера
(`old_line`): аргумент в одну строку по пробелам, срез до 100 символов,
`· <имя> <срез>`, хвостовые пробелы сняты, перевод строки.

Каталог документов задачи в путях фикстур собирается из имени
`DOCS_DIR`, а не литералом: путь вида `…/.artel/projects/<проект>/<DOCS_DIR>/<id>/X`.

Пути, проекты, идентификаторы и хвосты — из `random`; зерно печатается
(`зерно: N`) и входит в текст каждого провала.

Валидация стабом: временный стаб `base.short_log_path` (разбор по
сегментам `/.artel/`, `projects/<проект>/`, `worktrees/<id>/`,
`<DOCS_DIR>/<id>/`, отказ на пустом хвосте и на `.artel-canary`), его вызов
в `claude._render_block` для `file_path` и в `codex._tool_call_event` для
`path`/`changes`, расширенные регулярные выражения `report.WRITE_GROUPS` и
«н/д» для `wt:`/`docs:` — все тесты зелёные; стаб удалён.
"""
import ast
import copy
import html
import json
import os
import random
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from orchestrator import agent_log, config, report, spend, store
from orchestrator.providers import base, claude, codex
from orchestrator.providers.base import ToolCall, ToolResult
from tests.sandbox import SchemaTmpRootTest

LIMIT = 100
LINE_PREFIX = "· "
DOCS_DIR = "tasks"
ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
FILE_TOOLS = ("Read", "Edit", "Write", "MultiEdit")


def old_line(name, argument) -> str:
    """Строка вызова в форме рендера до задачи."""
    flat = " ".join(str(argument).split())[:LIMIT]
    return f"{LINE_PREFIX}{name} {flat}".rstrip() + "\n"


def claude_line(name: str, tool_input: dict) -> str:
    raw = json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "toolu_1", "name": name,
         "input": tool_input}]}}, ensure_ascii=False)
    return claude.ClaudeProvider().parse_output_line(raw).log_text


def codex_event(item: dict):
    raw = json.dumps({"type": "item.started", "item": item},
                     ensure_ascii=False)
    return codex.CodexProvider().parse_output_line(raw)


def codex_line(item: dict) -> str:
    return codex_event(item).log_text


def serialized(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Paths:
    """Генератор путей фикстуры от одного зерна."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def seg(self, low: int = 3, high: int = 9) -> str:
        return "".join(self.rng.choice(ALPHABET)
                       for _ in range(self.rng.randint(low, high)))

    def task_id(self) -> str:
        return self.rng.choice((
            "T" + str(self.rng.randrange(1, 10 ** 4)),
            "01M" + "".join(self.rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                            for _ in range(23))))

    def prefix(self, parts: int = 0) -> str:
        """Абсолютный префикс без `.artel` и без точек в именах."""
        count = parts or self.rng.randint(1, 4)
        return "/" + "/".join(self.seg() for _ in range(count))

    def tail(self, parts: int = 0) -> str:
        count = parts or self.rng.randint(1, 3)
        return "/".join([self.seg() for _ in range(count - 1)]
                        + [self.seg() + ".py"])

    def forms(self, tail: str) -> list:
        """[(полный путь, короткая форма)] — все формы замены AC-2."""
        pre, tid, proj = self.prefix(), self.task_id(), self.seg()
        nested = f"{DOCS_DIR}/{tid}/{tail}"
        return [
            (f"{pre}/.artel/worktrees/{tid}/{tail}", f"wt:{tail}"),
            (f"{pre}/.artel/projects/{proj}/worktrees/{tid}/{tail}",
             f"wt:{tail}"),
            (f"{pre}/.artel/projects/{proj}/{DOCS_DIR}/{tid}/{tail}",
             f"docs:{tail}"),
            (f"{pre}/.artel/worktrees/{tid}/{nested}", f"wt:{nested}"),
            (f"{pre}/.artel/projects/{proj}/worktrees/{tid}/{nested}",
             f"wt:{nested}"),
        ]

    def untouched(self) -> list:
        """Значения, которые сокращение обязано оставить как есть (AC-3)."""
        pre, tid, proj = self.prefix(), self.task_id(), self.seg()
        canary = config.CANARY_POOL_DIRNAME
        tail = self.tail()
        return [
            f"/home/{self.seg()}/my.artel/worktrees/{tid}/{tail}",
            f"{pre}/x.artel/projects/{proj}/{DOCS_DIR}/{tid}/{tail}",
            f"{pre}/.artel/worktrees/{tid}",
            f"{pre}/.artel/worktrees/{tid}/",
            f"{pre}/.artel/projects/{proj}/worktrees/{tid}",
            f"{pre}/.artel/projects/{proj}/worktrees/{tid}/",
            f"{pre}/.artel/projects/{proj}/{DOCS_DIR}/{tid}",
            f"{pre}/.artel/projects/{proj}/{DOCS_DIR}/{tid}/",
            f"{pre}/.artel/logs/{self.seg()}.log",
            f"{pre}/.artel/state.db",
            f"{pre}/.artel/projects/{proj}/repo/{tail}",
            f"{DOCS_DIR}/{tid}/SPEC.md",
            f"{DOCS_DIR}/T005/SPEC.md",
            "orchestrator/artel.py",
            f"worktrees/{tid}/{tail}",
            f"/tmp/{self.seg()}/{tail}",
            f"{pre}/projects/artel/orchestrator/{self.seg()}.py",
            f"/Users/{self.seg()}/{canary}/.artel/worktrees/{tid}/{tail}",
            f"{pre}/.artel/worktrees/{tid}/{canary}/{tail}",
            f"{pre}/.artel/projects/{proj}/{DOCS_DIR}/{tid}/{canary}/{tail}",
        ]


class SeededTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.paths = Paths(self.rng)

    def note(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"


class ShortLogPathTest(SeededTest):

    def test_ac1_claude_file_tools_log_short_worktree_path(self):
        """Read/Edit/Write/MultiEdit с длинным путём рабочей копии дают `· <инструмент> wt:<хвост>` целиком.

        Сценарий: `file_path` =
        `<префикс длиной больше 100>/.artel/projects/<проект>/worktrees/<id>/<хвост>`,
        где `wt:<хвост>` короче 100 символов; для каждого из четырёх
        файловых инструментов строка лога равна `· <имя> wt:<хвост>\\n` —
        хвост виден полностью. Отдельно — путь
        `…/worktrees/<id>/orchestrator/report.py` из формулировки критерия.

        Ловит мутацию: префикс заменён после обрезки (в строке — срез
        абсолютного пути без `wt:`); замена не применена к `file_path`
        (строка несёт абсолютный путь); замена применена только к Read.
        """
        for _ in range(5):
            pre = self.paths.prefix(parts=18)
            while len(pre) <= LIMIT + 20:
                pre += "/" + self.paths.seg()
            tid, proj = self.paths.task_id(), self.paths.seg()
            tail = self.paths.tail(parts=self.rng.randint(4, 8))[:LIMIT - 10]
            tail = tail.rstrip("/") or "x.py"
            root = f"{pre}/.artel/projects/{proj}/worktrees/{tid}"
            cases = [(f"{root}/{tail}", f"wt:{tail}"),
                     (f"{root}/orchestrator/report.py",
                      "wt:orchestrator/report.py")]
            for name in FILE_TOOLS:
                for path, short in cases:
                    with self.subTest(name=name, path=path):
                        self.assertLess(len(short), LIMIT)
                        self.assertEqual(
                            claude_line(name, {"file_path": path}),
                            f"{LINE_PREFIX}{name} {short}\n",
                            self.note(f"путь: {path}"))

    def test_ac2_short_forms_of_worktree_docs_and_nested_layouts(self):
        """Формы замены: `.artel/worktrees/<id>/X` и `.artel/projects/<п>/worktrees/<id>/X` -> `wt:X`, каталог документов -> `docs:X`, вложенная раскладка -> одна замена `wt:<каталог документов>/<id>/X`.

        Сценарий: на случайных префиксах, проектах, идентификаторах и
        хвостах `base.short_log_path` отдаёт ровно ожидаемую форму, и
        строка лога Claude Read несёт её же.

        Ловит мутацию: старая вложенная раскладка дала `docs:X` (выбран
        последний якорь) или `wt:wt:…`/`wt:docs:…` (замена применена
        дважды); форма `projects/<проект>/worktrees/` не распознана; для
        каталога документов выдан `wt:`.
        """
        for _ in range(20):
            for path, short in self.paths.forms(self.paths.tail()):
                with self.subTest(path=path):
                    self.assertEqual(base.short_log_path(path), short,
                                     self.note(f"путь: {path}"))
                    self.assertEqual(claude_line("Read", {"file_path": path}),
                                     old_line("Read", short),
                                     self.note(f"путь: {path}"))

    def test_ac3_values_outside_anchors_are_left_unchanged(self):
        """Не сокращаются: `.artel` не сегментом, путь без хвоста, `logs/`/`state.db`/`repo/`, относительные пути, путь вне `.artel/`, значения с каталогом пула канарейки.

        Сценарий: каждое значение перечня проходит `base.short_log_path`
        без изменений, а строки лога Claude Read и Codex `file_change`
        (`path` элемента и `path` в `changes`) — те же, что до задачи.
        Для значений с `config.CANARY_POOL_DIRNAME` строка лога обоих
        провайдеров по-прежнему несёт эту подстроку — её ищет детектор
        утечки пула.

        Ловит мутацию: `.artel` найден подстрокой (`my.artel/…` -> `wt:`);
        путь без хвоста дал пустое `wt:`/`docs:`; изменены пути
        `…/.artel/logs/…`, `…/.artel/state.db`,
        `…/.artel/projects/<проект>/repo/…`; относительный путь
        `<каталог документов>/T005/SPEC.md` превращён в `docs:SPEC.md`;
        путь вне `.artel/` изменён; значение с `.artel-canary` сокращено —
        подстрока пропала из строки лога.
        """
        canary = config.CANARY_POOL_DIRNAME
        for _ in range(5):
            for value in self.paths.untouched():
                with self.subTest(value=value):
                    context = self.note(f"значение: {value}")
                    self.assertEqual(base.short_log_path(value), value, context)
                    lines = (
                        (claude_line("Read", {"file_path": value}),
                         old_line("Read", value)),
                        (codex_line({"id": "i1", "type": "file_change",
                                     "path": value}),
                         old_line("file_change", value)),
                        (codex_line({"id": "i2", "type": "file_change",
                                     "changes": [{"kind": "add",
                                                  "path": value}]}),
                         old_line("file_change",
                                  serialized([{"kind": "add", "path": value}]))),
                    )
                    for got, want in lines:
                        self.assertEqual(got, want, context)
                        if canary in value and canary in want:
                            self.assertIn(canary, got, context)

    def test_ac4_claude_command_and_pattern_are_not_shortened(self):
        """Bash `command` и Grep `pattern` в строке лога Claude прежние — и с путём рабочей копии внутри, и когда значение само есть такой путь.

        Сценарий: `command` = `cat <путь>`, `python3 <путь> -q` и сам
        `<префикс>/.artel/worktrees/<id>/scripts/run.sh`; Grep с тем же
        путём в `pattern` (в том числе вместе с полем `path`). Строка
        лога — как до задачи.

        Ловит мутацию: замена применена к Bash-команде с абсолютным путём
        или к шаблону Grep; замена применена к `command`/`pattern`,
        которые сами являются абсолютным путём под
        `/.artel/worktrees/<id>/` с хвостом.
        """
        for _ in range(10):
            tid = self.paths.task_id()
            script = f"{self.paths.prefix()}/.artel/worktrees/{tid}/scripts/run.sh"
            inner = self.rng.choice(self.paths.forms(self.paths.tail()))[0]
            cases = [
                ("Bash", {"command": script}),
                ("Bash", {"command": f"cat {inner}"}),
                ("Bash", {"command": f"python3 {inner} -q",
                          "description": "прогон"}),
                ("Grep", {"pattern": script}),
                ("Grep", {"pattern": inner, "path": inner}),
            ]
            for name, tool_input in cases:
                with self.subTest(name=name, tool_input=tool_input):
                    key = "command" if name == "Bash" else "pattern"
                    self.assertEqual(claude_line(name, tool_input),
                                     old_line(name, tool_input[key]),
                                     self.note(f"вход: {tool_input}"))

    def test_ac5_codex_path_or_changes_shortened_command_untouched(self):
        """Codex: `path` элемента, ставший аргументом строки, сокращён; без `path` — сокращён `path` каждого элемента `changes`; команда и прочий текст прежние.

        Сценарий: `file_change` с непустым `path` рабочей копии и
        перечнем `changes` — строка `· file_change wt:X`; `file_change`
        без `path` с двумя правками в разных формах и третьей с
        относительным путём — строка из сериализации перечня с
        сокращёнными путьями обеих правок и нетронутым относительным;
        `command_execution` с `command` = путь рабочей копии и с путём
        внутри команды, `web_search` с таким `query`, `mcp_tool_call` с
        `arguments` = `{"path": <путь>}` — строки как до задачи.

        Ловит мутацию: у элемента с непустым `path` и перечнем `changes`
        замена применена не к `path`, ставшему аргументом строки (строка
        несёт абсолютный путь); `path` самого элемента `file_change` не
        заменён; в `file_change` заменён только первый `path` перечня;
        замена применена к `command_execution` или к `arguments`
        `mcp_tool_call`.
        """
        for _ in range(10):
            tail = self.paths.tail(parts=1)
            forms = self.paths.forms(tail)
            path, short = self.rng.choice(forms)
            other = self.rng.choice(forms)[0]
            with self.subTest(case="path", path=path):
                self.assertEqual(
                    codex_line({"id": "i1", "type": "file_change",
                                "path": path,
                                "changes": [{"kind": "add", "path": other}]}),
                    f"{LINE_PREFIX}file_change {short}\n",
                    self.note(f"путь: {path}"))

            (first, first_short), (second, second_short) = \
                self.rng.sample(forms[:3], 2)
            relative = self.paths.tail()
            changes = [{"kind": "add", "path": first},
                       {"kind": "update", "path": second},
                       {"kind": "delete", "path": relative}]
            expected = [{"kind": "add", "path": first_short},
                        {"kind": "update", "path": second_short},
                        {"kind": "delete", "path": relative}]
            with self.subTest(case="changes", changes=changes):
                self.assertEqual(
                    codex_line({"id": "i2", "type": "file_change",
                                "changes": changes}),
                    old_line("file_change", serialized(expected)),
                    self.note(f"перечень: {changes}"))

            script = (f"{self.paths.prefix()}/.artel/worktrees/"
                      f"{self.paths.task_id()}/scripts/run.sh")
            untouched = [
                ({"id": "c1", "type": "command_execution", "command": script,
                  "status": "in_progress"}, "command_execution", script),
                ({"id": "c2", "type": "command_execution",
                  "command": f"/bin/zsh -lc 'cat {path}'"},
                 "command_execution", f"/bin/zsh -lc 'cat {path}'"),
                ({"id": "c3", "type": "web_search", "query": path},
                 "web_search", path),
                ({"id": "c4", "type": "mcp_tool_call", "server": "fs",
                  "tool": "read", "arguments": {"path": path}},
                 "fs/read", serialized({"path": path})),
            ]
            for item, name, argument in untouched:
                with self.subTest(case=item["type"], item=item):
                    self.assertEqual(codex_line(item), old_line(name, argument),
                                     self.note(f"элемент: {item}"))

    def test_ac6_tool_call_argument_results_tokens_unchanged(self):
        """`ToolCall.argument`, результаты вызовов, учёт токенов и итог запуска не несут короткой формы.

        Сценарий: Claude — сообщение ассистента с текстом, вызовом Read
        по пути рабочей копии и `usage`; сообщение пользователя с
        результатом, в тексте которого тот же путь; итог запуска с этим
        путём в `result`. Codex — `file_change` с `path` и без него
        (`changes`), его `item.completed` с путём в `result`, итог
        `turn.completed`. `ToolCall.argument` равен исходному пути
        (у перечня — его прежней сериализации), тексты результатов и
        итога — исходные, разбивка токенов — по исходным счётчикам.

        Ловит мутацию: замена попала в `ToolCall.argument` (ключ метрики
        трения несёт `wt:`); замена применена к тексту результата вызова
        или итога запуска; сокращение сломало сбор учёта токенов.
        """
        for _ in range(5):
            path, short = self.rng.choice(self.paths.forms(self.paths.tail()))
            context = self.note(f"путь: {path}")
            counts = {key: self.rng.randrange(1, 10 ** 5)
                      for key in config.LEGACY_TOKEN_KIND_NAMES}
            provider = claude.ClaudeProvider()
            event = provider.parse_output_line(json.dumps({
                "type": "assistant", "message": {
                    "usage": counts,
                    "content": [
                        {"type": "text", "text": "Читаю файл."},
                        {"type": "tool_use", "id": "toolu_7", "name": "Read",
                         "input": {"file_path": path}}]}}))
            self.assertEqual(event.tool_calls,
                             (ToolCall("toolu_7", "Read", path),), context)
            self.assertEqual(event.text, "Читаю файл.", context)
            self.assertEqual(event.tokens_by_type,
                             {kind: counts[key] for key, kind
                              in config.LEGACY_TOKEN_KIND_NAMES.items()},
                             context)
            self.assertEqual(event.log_text,
                             "Читаю файл.\n" + old_line("Read", short),
                             context)
            result = provider.parse_output_line(json.dumps({
                "type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "toolu_7",
                     "content": f"{path}: 12 строк"}]}}))
            self.assertEqual(result.tool_results,
                             (ToolResult("toolu_7", f"{path}: 12 строк",
                                         False),), context)
            self.assertEqual(result.log_text, "", context)
            final = provider.parse_output_line(json.dumps({
                "type": "result", "is_error": True, "result": path,
                "total_cost_usd": 0.5, "usage": counts}))
            self.assertEqual(final.run_result.text, path, context)
            self.assertEqual(final.log_text,
                             f"! ошибка агента: {path[:200]}\n", context)

            changes = [{"kind": "add", "path": path}]
            started = codex_event({"id": "f1", "type": "file_change",
                                   "changes": changes})
            self.assertEqual(started.tool_calls,
                             (ToolCall("f1", "file_change",
                                       serialized(changes)),), context)
            started = codex_event({"id": "f2", "type": "file_change",
                                   "path": path})
            self.assertEqual(started.tool_calls,
                             (ToolCall("f2", "file_change", path),), context)
            done = codex.CodexProvider().parse_output_line(json.dumps({
                "type": "item.completed", "item": {
                    "id": "f2", "type": "file_change", "path": path,
                    "result": path, "status": "completed"}}))
            self.assertEqual(done.tool_results,
                             (ToolResult("f2", path, False),), context)
            self.assertEqual(done.log_text, "", context)
            turn = codex.CodexProvider().parse_output_line(json.dumps({
                "type": "turn.completed", "usage": {
                    "input_tokens": 500, "cached_input_tokens": 200,
                    "output_tokens": 70}}))
            self.assertEqual(turn.tokens_by_type,
                             {"input": 300, "output": 70, "cache_write": 0,
                              "cache_read": 200}, context)

    def test_ac7_limit_symbol_and_flattening_kept(self):
        """Предел 100 и символ строки прежние у обоих провайдеров; короткая форма обрезается тем же пределом и сводится в одну строку.

        Сценарий: константы `TOOL_ARGUMENT_LIMIT` = 100 и
        `TOOL_CALL_LINE_PREFIX` = `· ` у Claude и Codex; путь рабочей
        копии с хвостом длиннее 100 символов даёт `· Read ` + первые 100
        символов `wt:<хвост>`; хвост с двойным пробелом и табуляцией
        сведён в одну строку по пробелам, как прежде.

        Ловит мутацию: предел 100 изменён (константа или срез короткой
        формы снят); пробелы короткой формы не сводятся; у Codex срез
        считается по исходному пути, а не по короткой форме.
        """
        for module in (claude, codex):
            with self.subTest(module=module.__name__):
                self.assertEqual(module.TOOL_ARGUMENT_LIMIT, LIMIT)
                self.assertEqual(module.TOOL_CALL_LINE_PREFIX, LINE_PREFIX)
        for _ in range(10):
            tail = self.paths.tail(parts=self.rng.randint(14, 20))
            while len(tail) <= LIMIT:
                tail = self.paths.seg() + "/" + tail
            self.assertGreater(len(tail), LIMIT)
            path, short = self.rng.choice(self.paths.forms(tail)[:3])
            context = self.note(f"путь: {path}")
            self.assertEqual(claude_line("Read", {"file_path": path}),
                             f"{LINE_PREFIX}Read {short[:LIMIT]}\n", context)
            self.assertEqual(codex_line({"id": "i", "type": "file_change",
                                         "path": path}),
                             f"{LINE_PREFIX}file_change {short[:LIMIT]}\n",
                             context)
            spaced_tail = f"{self.paths.seg()}  {self.paths.seg()}\t.py"
            spaced, spaced_short = self.rng.choice(self.paths.forms(spaced_tail)[:3])
            self.assertEqual(claude_line("Write", {"file_path": spaced}),
                             old_line("Write", spaced_short),
                             self.note(f"путь: {spaced!r}"))

    def test_ac8_both_providers_call_shared_module_function(self):
        """Подмена атрибута `base.short_log_path` меняет строку лога и Claude, и Codex; без подмены для одного пути оба дают одну форму.

        Сценарий: `short_log_path` модуля `base` подменён функцией,
        отдающей для строки метку `ZQX-метка`; строка Claude Read и строка
        Codex `file_change` с `path` — `· <имя> ZQX-метка`. Без подмены на
        случайных путях обеих форм аргумент строки Claude, аргумент
        строки Codex и `base.short_log_path(path)` совпадают.

        Ловит мутацию: провайдеры зовут не общую функцию из
        `providers/base.py` (своя копия или привязка
        `from .base import short_log_path` — подмена атрибута не меняет
        строку хотя бы одного провайдера); Claude и Codex дают разную
        форму для одного пути.
        """
        path, _short = self.rng.choice(self.paths.forms(self.paths.tail()))

        def fake(value):
            return "ZQX-метка" if isinstance(value, str) else value

        with mock.patch.object(base, "short_log_path", fake):
            self.assertEqual(claude_line("Read", {"file_path": path}),
                             f"{LINE_PREFIX}Read ZQX-метка\n",
                             self.note(f"путь: {path}"))
            self.assertEqual(codex_line({"id": "i", "type": "file_change",
                                         "path": path}),
                             f"{LINE_PREFIX}file_change ZQX-метка\n",
                             self.note(f"путь: {path}"))
        for _ in range(20):
            values = [p for p, _s in self.paths.forms(self.paths.tail())]
            values += self.rng.sample(self.paths.untouched(), 3)
            for value in values:
                with self.subTest(value=value):
                    want = " ".join(base.short_log_path(value).split())[:LIMIT]
                    self.assertEqual(
                        claude_line("Read", {"file_path": value}),
                        f"{LINE_PREFIX}Read {want}\n", self.note(value))
                    self.assertEqual(
                        codex_line({"id": "i", "type": "file_change",
                                    "path": value}),
                        f"{LINE_PREFIX}file_change {want}\n", self.note(value))

    def test_ac9_garbage_values_and_file_change_shapes_survive(self):
        """Сокращение на `None`, пустой строке, не строке и испорченных перечнях отдаёт значение как есть; испорченный `file_change` не роняет разбор и даёт прежнюю строку.

        Сценарий: `base.short_log_path` на `None`, `""`, числах, словаре,
        перечнях `[]`, `[{"kind": "x"}]`, `[1, None, {"kind": "x"}]`,
        `[{"path": 5}]` — результат равен входу, вход не изменён.
        `file_change` с `changes` = `[1, null, {"kind": "x"}]`, с
        `[{"path": 5, …}]` и с `path` = 5 на уровне элемента (вместе с
        перечнем путей рабочей копии) — разбор без исключения и строка,
        как до задачи.

        Ловит мутацию: `file_change` с `changes` вида
        `[1, null, {"kind": "x"}]`, с `path` неверного вида внутри
        элемента `changes` или на уровне самого элемента уронил разбор
        (`KeyError`/`TypeError`/`AttributeError`) либо дал иную строку,
        чем до задачи (например, путь перечня сокращён, хотя аргументом
        строки стал `path` = 5).
        """
        path, _short = self.rng.choice(self.paths.forms(self.paths.tail()))
        values = [None, "", 5, 3.5, True, [],
                  [{"kind": "x"}], [1, None, {"kind": "x"}],
                  [{"path": 5}], [{"path": None, "kind": "add"}],
                  (path,)]
        for value in values:
            with self.subTest(value=value):
                before = copy.deepcopy(value)
                self.assertEqual(base.short_log_path(value), before,
                                 self.note(repr(value)))
                self.assertEqual(value, before, self.note(repr(value)))
        items = [
            ({"id": "g1", "type": "file_change",
              "changes": [1, None, {"kind": "x"}]},
             serialized([1, None, {"kind": "x"}])),
            ({"id": "g2", "type": "file_change",
              "changes": [{"path": 5, "kind": "add"}]},
             serialized([{"path": 5, "kind": "add"}])),
            ({"id": "g3", "type": "file_change", "path": 5,
              "changes": [{"path": path, "kind": "add"}]}, "5"),
        ]
        for item, argument in items:
            with self.subTest(item=item):
                event = codex_event(item)
                self.assertEqual(event.log_text,
                                 old_line("file_change", argument),
                                 self.note(repr(item)))
                self.assertEqual(event.tool_calls,
                                 (ToolCall(item["id"], "file_change",
                                           argument),),
                                 self.note(repr(item)))

    def test_ac10_base_module_stays_py39_and_stdlib_only(self):
        """`providers/base.py` несёт `short_log_path`, разбирается грамматикой 3.9, без аннотаций `X | None`, на уровне модуля импортирует только стандартную библиотеку.

        Сценарий: исходный текст `base.py` разбирается `ast` с
        `feature_version=(3, 9)`; ни одна аннотация параметра, возврата
        или переменной не содержит оператора `|`; каждый импорт уровня
        модуля (включая вложенные в `if`/`try` уровня модуля) — модуль
        стандартной библиотеки, без относительных импортов.

        Ловит мутацию: у `short_log_path` аннотация `str | None` (в 3.9 —
        TypeError при объявлении); на уровне модуля добавлен
        `from orchestrator import config` ради `CANARY_POOL_DIRNAME` или
        `from . import claude` ради предела.
        """
        self.assertTrue(callable(getattr(base, "short_log_path", None)),
                        "в base.py нет функции short_log_path")
        source = Path(base.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source, feature_version=(3, 9))

        def has_bitor(node) -> bool:
            return node is not None and any(
                isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr)
                for n in ast.walk(node))

        for node in ast.walk(tree):
            annotations = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                annotations.append(node.returns)
                every = (node.args.posonlyargs + node.args.args
                         + node.args.kwonlyargs
                         + [a for a in (node.args.vararg, node.args.kwarg) if a])
                annotations += [a.annotation for a in every]
            elif isinstance(node, ast.AnnAssign):
                annotations.append(node.annotation)
            for annotation in annotations:
                self.assertFalse(has_bitor(annotation),
                                 f"аннотация с «|», строка "
                                 f"{getattr(node, 'lineno', '?')}")

        def module_level(statements):
            for statement in statements:
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    yield statement
                for field in ("body", "orelse", "finalbody", "handlers"):
                    inner = getattr(statement, field, None)
                    if isinstance(inner, list) and not isinstance(
                            statement, (ast.FunctionDef, ast.AsyncFunctionDef,
                                        ast.ClassDef)):
                        yield from module_level(inner)

        for statement in module_level(tree.body):
            if isinstance(statement, ast.ImportFrom):
                self.assertEqual(statement.level, 0,
                                 f"относительный импорт, строка {statement.lineno}")
                names = [statement.module or ""]
            else:
                names = [alias.name for alias in statement.names]
            for name in names:
                self.assertIn(name.split(".")[0], sys.stdlib_module_names,
                              f"импорт не из стандартной библиотеки: {name}, "
                              f"строка {statement.lineno}")


HEADING = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.S | re.I)
TITLE = re.compile(r"test_author|автор\w*\s+тест", re.I)


def text_of(chunk: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", chunk)).split())


def author_section(page: str) -> str:
    """Текст раздела test_author отчёта; пусто — раздела нет."""
    headings = list(HEADING.finditer(page))
    for index, match in enumerate(headings):
        if not TITLE.search(text_of(match.group(2))):
            continue
        level = int(match.group(1))
        end = len(page)
        for later in headings[index + 1:]:
            if int(later.group(1)) <= level:
                end = later.start()
                break
        return text_of(page[match.start():end])
    return ""


def standalone(section: str, value) -> bool:
    return re.search(rf"(?<![\d.,]){re.escape(str(value))}(?!\d)",
                     section) is not None


class ReportWriteGroupsTest(SchemaTmpRootTest):
    """Связка «лог шага — журнал — `report.cmd_report`»: раздел test_author
    отчёта читает строки вызова лога шага и файлы на диске."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.paths = Paths(self.rng)
        tmp_base = "/tmp" if Path("/tmp").is_dir() else None
        self.short = Path(tempfile.mkdtemp(prefix="a", dir=tmp_base)).resolve()
        self.addCleanup(shutil.rmtree, self.short, ignore_errors=True)

    def note(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def files(self, folder: str, counts: list) -> list:
        paths = []
        for count in counts:
            path = self.short / folder / f"test_{self.paths.seg(4, 6)}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(f"x_{i} = {i}\n" for i in range(count)),
                            encoding="utf-8")
            self.assertLess(len(str(path)), LIMIT, self.note(str(path)))
            paths.append(str(path))
        return paths

    def writes(self, paths: list, total: int) -> list:
        chosen = list(paths) + [self.rng.choice(paths)
                                for _ in range(total - len(paths))]
        return [old_line("Write", p) for p in chosen]

    def seed_step(self, lines: list) -> None:
        task = f"T{self.rng.randrange(10 ** 5, 10 ** 6)}"
        conn = store.db()
        store.insert_task(conn, task, f"Задача {task}", "in_dev",
                          f"task/{task.lower()}", config.DEFAULT_TARGET, 25.0)
        self.rng.shuffle(lines)
        config.LOGS.mkdir(parents=True, exist_ok=True)
        log = config.LOGS / f"{task}-test_author-1.log"
        log.write_text("Начинаю шаг.\n" + "".join(lines), encoding="utf-8")
        attempt = f"попытка 1/{config.AGENT_ATTEMPTS}"
        store.journal(conn, task, "test_author", "agent run started",
                      f"{attempt}, model=fx-model, роль test_author, источник "
                      f"модели: фикстура, лог: {log}, промпт: {log}.prompt, "
                      f"окружение: фикстура")
        store.journal(conn, task, "test_author", agent_log.PYTEST_RUN_ACTION,
                      "2 passed in 0.50s")
        store.journal(conn, task, "test_author", spend.KNOWN_COST_JOURNAL_ACTION,
                      f"{attempt}, model=fx-model, provider=claude: "
                      f"input=4321, output=5432, cache_write=0, cache_read=0, "
                      f"actual_usd=0.47")
        store.journal(conn, task, "test_author", "agent run finished",
                      f"rc=0, {attempt}, стоимость $0.4700, токенов 9753, "
                      f"окружение: фикстура")

    def section(self) -> str:
        self.capture(report.cmd_report)
        page = (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")
        return author_section(page)

    def distinct(self, make) -> dict:
        # Числа, которые раздел несёт помимо фикстуры: прогон pytest,
        # токены и дата шага (`ГГГГ-ММ-ДД`); доли (`0.50`, `0.47`) отдельно
        # стоящими не читаются.
        today = [datetime.now(), datetime.now(timezone.utc)]
        reserved = {0, 1, 2, 4321, 5432, 9753}
        reserved |= {d.day for d in today} | {d.month for d in today}
        for _ in range(10 ** 5):
            values = make()
            plain = [v for k, v in values.items() if not k.startswith("_")]
            if len(set(plain)) == len(plain) and not set(plain) & reserved:
                return values
        self.fail(self.note("не подобраны попарно различные числа фикстуры"))

    def test_ac12_short_form_writes_grouped_with_na_lines(self):
        """`· Write wt:tests/…` и `· Write docs:acceptance_tests/…` засчитаны в свои группы Write, их строки — «н/д»; абсолютные пути считаются как прежде.

        Сценарий: лог шага test_author несёт Write по абсолютным путям
        существующих файлов `…/tests/` и `…/acceptance_tests/` и Write по
        коротким путям `wt:tests/<f>` и `docs:acceptance_tests/<f>`.
        Рабочий каталог процесса — временный, в нём лежат файлы
        `tests/<f>` и `acceptance_tests/<f>` с заметным числом строк.
        В разделе: число Write группы = абсолютные + короткие, число
        файлов и строк — только по абсолютным, «н/д» по числу коротких.

        Ловит мутацию: `docs:acceptance_tests/test_x.py` или
        `wt:tests/test_x.py` не попали в группу Write (регулярное
        выражение без «:» слева); путь `wt:` принят за читаемый файл с
        числом строк (префикс снят и файл прочитан от рабочего каталога —
        строки и файлы группы выросли, «н/д» нет).
        """
        def make():
            ft, fa = self.rng.sample(range(3, 9), 2)
            v = {"ft": ft, "fa": fa,
                 "wt": ft + self.rng.randrange(1, 9),
                 "wa": fa + self.rng.randrange(1, 9),
                 "st": self.rng.randrange(3, 20),
                 "sa": self.rng.randrange(3, 20),
                 "_lines_t": [self.rng.randrange(20, 50) for _ in range(ft)],
                 "_lines_a": [self.rng.randrange(20, 50) for _ in range(fa)]}
            v["lt"], v["la"] = sum(v["_lines_t"]), sum(v["_lines_a"])
            v["wt_all"], v["wa_all"] = v["wt"] + v["st"], v["wa"] + v["sa"]
            v["w"] = v["wt_all"] + v["wa_all"]
            return v

        v = self.distinct(make)
        cwd = self.short / "cwd"
        names_t = [f"test_{self.paths.seg(4, 6)}.py" for _ in range(2)]
        names_a = [f"test_{self.paths.seg(4, 6)}.py" for _ in range(2)]
        relative_lines = 700 + self.rng.randrange(50)
        for folder, names in (("tests", names_t), ("acceptance_tests", names_a)):
            for name in names:
                target = cwd / folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("y = 1\n" * relative_lines, encoding="utf-8")
        old_cwd = os.getcwd()
        os.chdir(cwd)
        self.addCleanup(os.chdir, old_cwd)

        lines = (self.writes(self.files("tests", v["_lines_t"]), v["wt"])
                 + self.writes(self.files("plank/acceptance_tests",
                                          v["_lines_a"]), v["wa"])
                 + [old_line("Write", f"wt:tests/{self.rng.choice(names_t)}")
                    for _ in range(v["st"])]
                 + [old_line("Write",
                             f"docs:acceptance_tests/{self.rng.choice(names_a)}")
                    for _ in range(v["sa"])])
        self.seed_step(lines)
        section = self.section()
        context = self.note(f"числа: {v}\nраздел:\n{section}")
        self.assertTrue(section, context)
        self.assertIn("н/д", section, context)
        for key in ("w", "wt_all", "wa_all", "ft", "fa", "lt", "la", "st", "sa"):
            with self.subTest(key=key):
                self.assertTrue(standalone(section, v[key]),
                                self.note(f"нет числа {key}={v[key]}\n{context}"))
        self.assertFalse(standalone(section, relative_lines), context)

    def test_ac12_old_form_lines_give_same_numbers(self):
        """Лог только старой формы (абсолютные пути, обрезанный `…/acceptance`, пропавший файл) даёт те же числа блока test_author, что до задачи.

        Сценарий: Write по абсолютным путям существующих файлов
        `…/tests/` и `…/acceptance_tests/`, строка Write, обрезанная на
        100 символах до `…/acceptance`, и Write по пропавшему файлу
        `…/tests/`. В разделе: Write группы `tests/` и `acceptance_tests/`
        — на единицу больше записей с полным путём, файлов и строк — по
        существующим, «н/д» есть.

        Ловит мутацию: группа `tests/` расширена до подстроки «tests/» без
        разделителя слева — абсолютный `…/acceptance_tests/…` засчитан и в
        `tests/`; «н/д» выдаётся любому пути, не начинающемуся с «/»,
        либо, наоборот, абсолютный путь, видимый короче предела, больше не
        читается с диска — числа строк пропали.
        """
        def make():
            ft, fa = self.rng.sample(range(3, 9), 2)
            v = {"ft": ft, "fa": fa,
                 "wt": ft + self.rng.randrange(1, 9),
                 "wa": fa + self.rng.randrange(1, 9),
                 "_lines_t": [self.rng.randrange(20, 50) for _ in range(ft)],
                 "_lines_a": [self.rng.randrange(20, 50) for _ in range(fa)]}
            v["lt"], v["la"] = sum(v["_lines_t"]), sum(v["_lines_a"])
            v["wt1"], v["wa1"] = v["wt"] + 1, v["wa"] + 1
            v["w"] = v["wt1"] + v["wa1"]
            return v

        v = self.distinct(make)
        prefix = str(self.short / "d")
        filler = LIMIT - len(prefix) - len("/acceptance")
        self.assertGreater(filler, 0, self.note(prefix))
        visible = prefix + "d" * filler + "/acceptance"
        missing = str(self.short / "tests" / f"test_gone_{self.paths.seg()}.py")
        lines = (self.writes(self.files("tests", v["_lines_t"]), v["wt"])
                 + self.writes(self.files("plank/acceptance_tests",
                                          v["_lines_a"]), v["wa"])
                 + [old_line("Write", visible + "_tests/test_cut.py"),
                    old_line("Write", missing)])
        self.seed_step(lines)
        section = self.section()
        context = self.note(f"числа: {v}\nраздел:\n{section}")
        self.assertTrue(section, context)
        self.assertIn("н/д", section, context)
        for key in ("w", "wt1", "wa1", "ft", "fa", "lt", "la"):
            with self.subTest(key=key):
                self.assertTrue(standalone(section, v[key]),
                                self.note(f"нет числа {key}={v[key]}\n{context}"))


if __name__ == "__main__":
    unittest.main()
