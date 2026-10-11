"""Предпроверка выхода из `tests_writing`: команда `artel.py preflight <id>`.

Группа: долгоживущий

Красен до реализации: команды `preflight` и модуля `orchestrator/preflight.py` ещё нет — `artel.py preflight <id>` отказывает «Неизвестная команда» с кодом 1 без единого заголовка проверки, сторож не находит модуля предпроверки; `test_ac9_autocommit_calls_input_filters` зелен с рождения — держит уже существующий вызов фильтра входа в `orchestrator/checkpoint.py`.

Стенд — настоящий git (`tests/sandbox.py::RealGitSandbox`): клон артели —
корень песочницы, синхронный bare `origin`, задачи заведены в БД пульта
напрямую (`store.insert_task`), рабочая копия кода — `workspace.ensure`.
Черновик test_author лежит в каталоге документов задачи
(`config.PROJECTS/<проект>/` + каталог задач + id), долгоживущие файлы — в
каталоге `tests` рабочей копии кода, незакоммиченными. Строки предпроверки
сверяются со строками, которые на тех же файлах пишет в журнал настоящий
переход: черновик переносится в ссылку документов и кодовую ветку штатными
чекпоинтами шага (`checkpoint.commit_step_artifacts`,
`checkpoint.commit_success_checkpoint`), затем `fsm.cmd_advance`. Гейты
перехода не подменяются.

Форма вывода — по SPEC: заголовок проверки «<проверка>: пройдена» или
«<проверка>: отказ» с начала строки, под заголовком отказа — строки ошибок
с отступом, текст строки — текст ошибки перехода. Имена проверок тесты не
знают и не утверждают.

Сторож (AC-9) читает тела `_tests_writing_ac_state`, гейта групп и гейта
долгоживущих файлов разбором исходника модулей (`ast`), не обращением к
закрытым именам. Число функций, перечень фильтров входа и перечень «не
проверяется» сторож берёт из SPEC: фильтр входа сейчас ровно один —
`guard.is_extraneous_acceptance_test_file`.

Идентификаторы задач, имена файлов, число критериев и непокрытый критерий
— от зерна; зерно печатается и входит в текст провала.
"""
import ast
import contextlib
import inspect
import io
import itertools
import os
import random
import re
import sqlite3
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (acceptance, artel, checkpoint, config, fsm,
                          project_profile, store, workspace)
from orchestrator.advance_gates import tests_writing as transition_gates
from scripts import guard
from tests.sandbox import ARTEL_TEST_PROFILE, RealGitSandbox, make_project_repo

ULID_LETTERS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
WORD_LETTERS = "abcdefghjkmnpqrstvwxyz"
TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
SEP = ":" + "//"
# Образец формата id задачи (`scripts/id_format_patterns.txt`) — собран по
# частям: этот файл сам не несёт образца.
ID_FORMAT_SAMPLE = "T%" + "03d"

TRACE_ACTION = "переход отклонён: трассируемость AC"
NOT_CHECKED = "не проверяется предпроверкой (проверит переход): "
NO_PROFILE = "не проверяется предпроверкой: у проекта нет профиля тестов"
ROLE_REFUSAL = "команда недоступна процессу роли"
HEADER = re.compile(r"^(\S.*?): (пройдена|отказ)$")

# Перечень «фильтры входа» (SPEC, требование 2): «сейчас в нём ровно
# `guard.is_extraneous_acceptance_test_file`».
INPUT_FILTERS = frozenset({"is_extraneous_acceptance_test_file"})
# Тела перехода, чьи вызовы guard сверяет сторож (SPEC, требование 12).
TRANSITION_BODIES = ((fsm, "_tests_writing_ac_state"),
                     (transition_gates, "_tests_writing_test_groups_gate"),
                     (transition_gates, "_tests_writing_long_lived_gate"))
DENIED_GIT = frozenset({"commit", "commit-tree", "push", "update-ref"})
CODE_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_SOURCE = CODE_ROOT / "orchestrator" / "preflight.py"
REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(ULID_LETTERS) for _ in range(24))


def word(rng: random.Random) -> str:
    return "".join(rng.choice(WORD_LETTERS) for _ in range(6))


def spec_text(task_id: str, count: int) -> str:
    items = "\n\n".join(f"AC-{n}. Критерий фикстуры номер {n}."
                        for n in range(1, count + 1))
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура предпроверки\n\n## Контекст\n\n## Требования\n\n"
            "## Критерии приёмки\n\n" + items + "\n\n## Не входит\n")


def plank_source(name: str, acs, *, marker: bool = True,
                 group: str | None = guard.GROUP_ONE_OFF,
                 extra: str = "") -> str:
    """Текст файла `test_*.py` планки: методы `test_ac<n>_…` по `acs`."""
    lines = ['"""Фикстура планки ' + name + ".", ""]
    if group:
        lines.append("Группа: " + group)
    if marker:
        lines.append("Красен до реализации: фикстура " + name + " ждёт кода.")
    lines += ['"""', "import unittest", ""]
    if extra:
        lines += [extra, ""]
    lines += ["", "class FixturePlankTest(unittest.TestCase):", ""]
    names = [f"test_ac{n}_{name}" for n in acs] or [f"test_{name}"]
    for method in names:
        lines += [f"    def {method}(self):", '        """Фикстурный метод."""',
                  "        self.assertTrue(True)", ""]
    return "\n".join(lines)


def long_lived_source(name: str, acs, *, claims: bool = True,
                      group: str | None = guard.GROUP_LONG_LIVED,
                      address: str | None = None) -> str:
    """Текст долгоживущего файла: методы `test_ac<n>_…` по `acs`."""
    lines = ['"""Долгоживущая фикстура ' + name + ".", ""]
    if group:
        lines.append("Группа: " + group)
    lines += ['"""', "import random", "import unittest", ""]
    if address:
        lines += [f"ADDRESS = {address!r}", ""]
    lines += ["", "class FixtureLongLivedTest(unittest.TestCase):", ""]
    names = [f"test_ac{n}_{name}" for n in acs] or [f"test_{name}"]
    for method in names:
        lines += [f"    def {method}(self):", '        """Фикстурный метод.', ""]
        if claims:
            lines.append(f"        Ловит мутацию: фикстура {name} — сумма "
                         f"перестаёт совпадать.")
        lines += ['        """', "        seed = random.randrange(1 << 30)",
                  '        print(f"зерно: {seed}")',
                  '        self.assertEqual(seed + 1, 1 + seed, f"зерно: {seed}")',
                  ""]
    return "\n".join(lines)


def sections(output: str) -> list:
    """[(проверка, исход, [строки под заголовком])] вывода предпроверки."""
    found, current = [], None
    for raw in output.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line[0].isspace():
            if current is not None:
                current[2].append(line.strip())
            continue
        match = HEADER.match(line)
        current = [match.group(1), match.group(2), []] if match else None
        if current is not None:
            found.append(current)
    return found


def refused_lines(output: str) -> list:
    return [line for _name, outcome, lines in sections(output)
            if outcome == "отказ" for line in lines]


def headers(output: str, outcome: str) -> list:
    return [name for name, got, _lines in sections(output) if got == outcome]


def git_subcommand(cmd) -> str | None:
    """Подкоманда git в argv процесса; не git — `None`."""
    tokens = ([str(t) for t in cmd] if isinstance(cmd, (list, tuple))
              else str(cmd).split())
    if not tokens or Path(tokens[0]).name != "git":
        return None
    rest = iter(tokens[1:])
    for token in rest:
        if token in ("-C", "-c", "--git-dir", "--work-tree"):
            next(rest, None)
            continue
        if token.startswith("-"):
            continue
        return token
    return None


def docstring_nodes(tree: ast.AST) -> set:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                ids.add(id(first.value))
    return ids


def guard_bindings(module_tree: ast.Module) -> tuple[set, dict]:
    """(имена модуля guard, {локальное имя: имя в guard}) по импортам модуля."""
    aliases, imported = set(), {}
    for node in ast.walk(module_tree):
        if not isinstance(node, ast.ImportFrom) or node.level:
            continue
        if node.module == "scripts":
            aliases.update(a.asname or a.name for a in node.names
                           if a.name == "guard")
        elif node.module == "scripts.guard":
            imported.update((a.asname or a.name, a.name) for a in node.names)
    return aliases, imported


def guard_functions(names) -> set:
    return {n for n in names if inspect.isfunction(getattr(guard, n, None))}


def referenced_guard_names(node: ast.AST, aliases: set, imported: dict) -> set:
    names = set()
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
                and sub.value.id in aliases):
            names.add(sub.attr)
        elif isinstance(sub, ast.Name) and sub.id in imported:
            names.add(imported[sub.id])
    return names


def module_tree(module) -> ast.Module:
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def transition_guard_calls() -> tuple[set, list]:
    """(функции guard в трёх телах перехода, имена ненайденных тел)."""
    calls, missing = set(), []
    for module, name in TRANSITION_BODIES:
        tree = module_tree(module)
        aliases, imported = guard_bindings(tree)
        bodies = [n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == name]
        if not bodies:
            missing.append(name)
        for body in bodies:
            calls |= referenced_guard_names(body, aliases, imported)
    return guard_functions(calls), missing


def preflight_guard_names(tree: ast.Module) -> set:
    """Функции guard, которые зовёт или называет `orchestrator/preflight.py`:
    обращения `guard.<имя>`, имена из `scripts.guard` и упоминания
    `guard.<имя>` в строках, не являющихся докстрингами."""
    aliases, imported = guard_bindings(tree)
    names = referenced_guard_names(tree, aliases, imported) | set(imported.values())
    skip = docstring_nodes(tree)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in skip):
            names |= set(re.findall(r"\bguard\.([A-Za-z_]\w*)", node.value))
    return guard_functions(names)


def foreign_guard_imports(tree: ast.Module) -> list:
    """Способы получить guard, отличные от `from scripts import guard` и
    `from scripts.guard import <имена>` (SPEC, требование 12)."""
    found, skip = [], docstring_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "scripts" or alias.name.startswith("scripts.guard"):
                    found.append(f"строка {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module == "scripts":
            for alias in node.names:
                if alias.name == "*" or (alias.name == "guard"
                                         and alias.asname not in (None, "guard")):
                    found.append(f"строка {node.lineno}: from scripts import "
                                 f"{alias.name} as {alias.asname}")
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in skip and "scripts.guard" in node.value):
            found.append(f"строка {node.lineno}: строка «{node.value}»")
    return found


class PreflightSandbox(RealGitSandbox):
    """Клон артели с `origin`, задачи в БД, черновик в каталоге документов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        self.origins = {config.DEFAULT_TARGET: self.add_synced_origin()}
        self.clones = {config.DEFAULT_TARGET: self.root}
        self.conn = store.db()

    def msg(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    # --- задачи и черновик ------------------------------------------------

    def external_project(self, profile: bool) -> str:
        target = "proj" + word(self.rng)
        clone = make_project_repo(target)
        if profile:
            text = config.TARGETS.read_text(encoding="utf-8")
            config.TARGETS.write_text(text.rstrip("\n") + "\n" + ARTEL_TEST_PROFILE,
                                      encoding="utf-8")
        self.clones[target] = clone
        self.origins[target] = config.PROJECTS / target / "origin.git"
        return target

    def new_task(self, *, target: str | None = None, state: str = "tests_writing",
                 code_copy: bool = True, task_id: str | None = None):
        target = target or config.DEFAULT_TARGET
        tid = task_id or ulid(self.rng)
        branch = f"task/{tid.lower()}-preflight"
        store.insert_task(self.conn, tid, "Фикстура предпроверки", state, branch,
                          target, 25.0)
        t = SimpleNamespace(id=tid, branch=branch, target=target,
                            count=self.rng.randint(2, 4), wt=None)
        t.docs = config.PROJECTS / target / TASKS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(tid, t.count), encoding="utf-8")
        if code_copy:
            wt, error = workspace.ensure(tid, branch)
            self.assertIsNone(error, self.msg(f"рабочая копия не заведена: {error}"))
            t.wt = Path(wt)
        return t

    def write_draft_again(self, t) -> None:
        """Каталог документов после автокоммита шага — как на старте
        следующего шага: SPEC.md на месте, прежних файлов планки нет."""
        for path in sorted(t.plank.glob("*"), reverse=True) if t.plank.is_dir() else ():
            if path.is_file():
                path.unlink()
        t.plank.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(t.id, t.count), encoding="utf-8")

    def write_plank(self, t, files: dict) -> None:
        for name, text in files.items():
            path = t.plank / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def clean_plank(self, t, acs=None) -> dict:
        """Черновик без нарушений: критерии `acs` (все — по умолчанию)
        покрыты одним или двумя файлами `test_*.py`."""
        acs = list(range(1, t.count + 1)) if acs is None else list(acs)
        self.rng.shuffle(acs)
        cut = self.rng.randint(0, len(acs))
        parts = [part for part in (acs[:cut], acs[cut:]) if part] or [[]]
        files = {}
        for part in parts:
            name = word(self.rng)
            files[f"test_{name}.py"] = plank_source(name, sorted(part))
        return files

    def write_long_lived(self, t, text: str) -> str:
        """Долгоживущий файл задачи в рабочей копии кода; путь от её корня."""
        rel = "/".join(("tests", f"test_{t.id.lower()}_{word(self.rng)}.py"))
        path = t.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return rel

    def plank_label(self, t, name: str) -> str:
        return "/".join((TASKS_DIR, t.id, PLANK_DIR, name))

    # --- команды ----------------------------------------------------------

    def cli(self, *args: str, role: str | None = None) -> tuple:
        """(код выхода, весь вывод, сообщение SystemExit) `artel.py <args>`."""
        out, err = io.StringIO(), io.StringIO()
        code = None
        env = {config.ARTEL_ROLE_ENV: role} if role else {}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(sys, "argv", ["artel.py", *args]), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        message = code if isinstance(code, str) else ""
        status = 0 if code is None else (code if isinstance(code, int) else 1)
        text = "\n".join(p for p in (out.getvalue(), err.getvalue(), message) if p)
        return status, text, message

    def preflight(self, arg: str, role: str | None = None) -> tuple:
        status, text, _message = self.cli("preflight", arg, role=role)
        return status, text

    def step_and_advance(self, t) -> tuple:
        """Черновик — в ссылку документов и кодовую ветку чекпоинтами шага,
        затем `advance`: (новые записи журнала, вывод advance)."""
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, t.id, "test_author")
        before = len(store.task_steps(self.conn, t.id))
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                fsm.cmd_advance(t.id)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        return rows, buf.getvalue()

    def refusal_detail(self, rows: list, action: str, output: str) -> str:
        details = [r["detail"] or "" for r in rows if r["action"] == action]
        self.assertTrue(details, self.msg(
            f"advance не записал «{action}»: {rows}\n{output}"))
        return details[-1]

    # --- снимок состояния -------------------------------------------------

    def db_dump(self) -> list:
        conn = sqlite3.connect(f"{Path(config.DB).resolve().as_uri()}?mode=ro",
                               uri=True)
        try:
            return list(conn.iterdump())
        finally:
            conn.close()

    def refs(self, repo: Path, bare: bool = False) -> str:
        where = ("--git-dir", str(repo)) if bare else ("-C", str(repo))
        return self.git(*where, "for-each-ref",
                        "--format=%(refname) %(objectname)")

    def snapshot(self, t) -> dict:
        wt = workspace.path(t.id, t.target)
        state = {"БД": self.db_dump(),
                 "ссылки клона": self.refs(self.clones[t.target]),
                 "ссылки origin": self.refs(self.origins[t.target], bare=True),
                 "рабочая копия есть": wt.is_dir(),
                 "планка выложена": (wt / TASKS_DIR / t.id).exists()}
        if wt.is_dir():
            state["статус рабочей копии"] = self.git(
                "-C", str(wt), "status", "--porcelain=v1", "--untracked-files=all")
            state["голова рабочей копии"] = self.git("-C", str(wt), "rev-parse", "HEAD")
        return state

    def assert_unchanged(self, t, before: dict, label: str, output: str) -> None:
        after = self.snapshot(t)
        for key in before:
            self.assertEqual(before[key], after.get(key), self.msg(
                f"{label}: после preflight изменилось «{key}»\n{output}"))


class DraftRefusalTest(PreflightSandbox):

    def defective_draft(self, t, kind: str) -> None:
        if kind == "непокрытый критерий":
            missing = self.rng.randint(1, t.count)
            acs = [n for n in range(1, t.count + 1) if n != missing]
            self.write_plank(t, self.clean_plank(t, acs))
        elif kind == "нет маркера красноты":
            files = self.clean_plank(t)
            name = self.rng.choice(sorted(files))
            stem = name[len("test_"):-len(".py")]
            acs = [int(n) for n in re.findall(r"def test_ac(\d+)_", files[name])]
            files[name] = plank_source(stem, acs, marker=False)
            self.write_plank(t, files)
        else:
            files = self.clean_plank(t)
            name = self.rng.choice(sorted(files))
            stem = name[len("test_"):-len(".py")]
            acs = [int(n) for n in re.findall(r"def test_ac(\d+)_", files[name])]
            files[name] = plank_source(
                stem, acs, extra=f"NAME_FORMAT = {ID_FORMAT_SAMPLE!r}")
            self.write_plank(t, files)

    def test_ac1_draft_refusals_match_advance_journal(self):
        """Три дефекта черновика: строки отказа предпроверки — строки журнала перехода.

        Сценарий (порядок от зерна, каждый — своя задача в `tests_writing`
        с рабочей копией кода): (а) один критерий не покрыт ни тестом, ни
        пометкой; (б) у одного файла `test_*.py` планки нет маркера
        красноты; (в) в файле планки строка с образцом формата id задачи.
        `preflight <id>` завершается кодом 1; строки под заголовками
        «…: отказ», склеенные через «; » в некотором порядке, дают ровно
        detail записи «переход отклонён: трассируемость AC», которую
        `advance` пишет на тех же файлах после штатного переноса черновика
        в ссылку документов, — в том числе метка файла вида каталог
        задач/<id>/acceptance_tests/<файл>.

        Ловит мутацию: метка файла у маркера или образца id — путь каталога
        документов на диске либо голое имя файла, а не метка перехода
        (строки не совпадают с журналом); трассируемость считается без
        `scan_ac_content` по планке (непокрытый критерий не виден, код 0);
        ошибки печатаются без отступа или с иным текстом.
        """
        kinds = ["непокрытый критерий", "нет маркера красноты", "образец id"]
        self.rng.shuffle(kinds)
        for kind in kinds:
            with self.subTest(kind=kind):
                t = self.new_task()
                self.defective_draft(t, kind)
                status, output = self.preflight(t.id)
                lines = refused_lines(output)
                rows, advanced = self.step_and_advance(t)
                detail = self.refusal_detail(rows, TRACE_ACTION, advanced)
                text = self.msg(f"{kind}\npreflight:\n{output}\nadvance:\n{advanced}")
                self.assertEqual(status, 1, text)
                self.assertTrue(headers(output, "отказ"), text)
                self.assertTrue(lines, text)
                self.assertLessEqual(len(lines), 6, text)
                self.assertTrue(any("; ".join(order) == detail
                                    for order in itertools.permutations(lines)),
                                f"{text}\ndetail журнала: {detail}\nстроки: {lines}")

    def test_ac1_marker_and_group_line_refused_together(self):
        """Файл без маркера красноты и без строки группы: напечатаны оба отказа.

        Сценарий: черновик без иных нарушений; у одного файла `test_*.py`
        планки нет ни маркера «Красен до реализации», ни строки группы.
        Вывод несёт два разных заголовка «…: отказ»: под одним — строка
        ошибки маркера (`guard.redness_marker_errors_from_files` с меткой
        каталог задач/<id>/acceptance_tests/<файл>), под другим — строка
        ошибки строки группы (`guard.group_line_errors_from_files` с меткой
        acceptance_tests/<файл>); код 1.

        Ловит мутацию: предпроверка останавливается на первом отказе (как
        `_run_gates` перехода) — второго заголовка и строки группы нет;
        обе ошибки складываются под один заголовок.
        """
        t = self.new_task()
        files = self.clean_plank(t)
        name = self.rng.choice(sorted(files))
        stem = name[len("test_"):-len(".py")]
        acs = [int(n) for n in re.findall(r"def test_ac(\d+)_", files[name])]
        files[name] = plank_source(stem, acs, marker=False, group=None)
        self.write_plank(t, files)
        marker = guard.redness_marker_errors_from_files(
            [(self.plank_label(t, name), files[name])])
        group = guard.group_line_errors_from_files(
            [("/".join((PLANK_DIR, name)), files[name])])
        status, output = self.preflight(t.id)
        text = self.msg(f"файл {name}\n{output}")
        self.assertEqual(status, 1, text)
        owners = {}
        for check, outcome, lines in sections(output):
            for line in lines:
                if outcome == "отказ":
                    owners.setdefault(line, check)
        for expected in marker + group:
            self.assertIn(expected, owners, text)
        self.assertNotEqual(owners[marker[0]], owners[group[0]], text)
        self.assertGreaterEqual(len(set(headers(output, "отказ"))), 2, text)


class DraftSourceTest(PreflightSandbox):

    def test_ac2_draft_not_docs_ref_decides_traceability(self):
        """Трассируемость судит по черновику каталога документов, не по ссылке.

        Сценарий: (1) в ссылке документов (штатный автокоммит шага) один
        критерий не покрыт, в черновике на диске затем покрыт — вывод без
        заголовка отказа и без строки «AC-<n>: нет теста…», код 0; (2) в
        ссылке покрыт, в черновике затем нет — под заголовком отказа строка
        «AC-<n>: нет теста…», код 1.

        Ловит мутацию: предпроверка читает планку и SPEC со ссылки
        документов (`artifact_branch.show`/`ls_tree`), как переход, — в
        (1) отказ, в (2) «пройдена».
        """
        for ref_covered in self.rng.sample([True, False], 2):
            with self.subTest(ref_covered=ref_covered):
                t = self.new_task()
                missing = self.rng.randint(1, t.count)
                partial = [n for n in range(1, t.count + 1) if n != missing]
                ref_files = self.clean_plank(t, None if ref_covered else partial)
                self.write_plank(t, ref_files)
                checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
                self.write_draft_again(t)
                self.write_plank(t, self.clean_plank(t, partial if ref_covered else None))
                status, output = self.preflight(t.id)
                text = self.msg(f"критерий AC-{missing}\n{output}")
                uncovered = [line for line in refused_lines(output)
                             if line.startswith(f"AC-{missing}: нет теста")]
                if ref_covered:
                    self.assertEqual(status, 1, text)
                    self.assertTrue(uncovered, text)
                else:
                    self.assertEqual(status, 0, text)
                    self.assertEqual(headers(output, "отказ"), [], text)
                    self.assertEqual(uncovered, [], text)

    def test_ac2_nested_plank_file_is_filtered_out(self):
        """Вложенный файл планки, отбрасываемый фильтром автокоммита, не влияет на исход.

        Сценарий: черновик без нарушений плюс
        `acceptance_tests/<подкаталог>/test_<имя>.py` без маркера красноты,
        без строки группы и с методом `test_ac<n>_…` на критерий, которого
        нет в SPEC. Фильтр `guard.is_extraneous_acceptance_test_file`
        отбрасывает файл, а без фильтра ядро маркера красноты дало бы по
        нему ошибку. Вывод без заголовка отказа, код 0.

        Ловит мутацию: планка собирается `rglob("test_*.py")` без фильтра
        входа — отказ маркера, строки группы и трассируемости по
        вложенному файлу, код 1.
        """
        t = self.new_task()
        self.write_plank(t, self.clean_plank(t))
        stem = word(self.rng)
        nested = "/".join((word(self.rng), f"test_{stem}.py"))
        source = plank_source(stem, [t.count + self.rng.randint(1, 5)],
                              marker=False, group=None)
        self.assertTrue(guard.is_extraneous_acceptance_test_file(nested),
                        self.msg(nested))
        self.assertTrue(guard.redness_marker_errors_from_files([(nested, source)]),
                        self.msg("фикстура вложенного файла не даёт ошибки маркера"))
        self.write_plank(t, {nested: source})
        status, output = self.preflight(t.id)
        text = self.msg(f"вложенный {nested}\n{output}")
        self.assertEqual(status, 0, text)
        self.assertEqual(headers(output, "отказ"), [], text)


class LongLivedDraftTest(PreflightSandbox):

    def test_ac3_uncommitted_long_lived_file_covers_criterion(self):
        """Критерий, покрытый только незакоммиченным долгоживущим файлом, — трассируемость пройдена.

        Сценарий: планка покрывает все критерии, кроме одного; его покрывает
        метод `test_ac<n>_…` долгоживущего файла задачи в рабочей копии
        кода, файл не закоммичен (неотслеживаемый). Вывод без заголовка
        отказа и без строки «AC-<n>: нет теста…», код 0.

        Ловит мутацию: долгоживущие файлы читаются с кодовой ветки
        (`gitcmd.show`), а не из рабочей копии, либо их тексты не
        передаются в `scan_ac_content` — критерий не покрыт, отказ, код 1.
        """
        t = self.new_task()
        missing = self.rng.randint(1, t.count)
        self.write_plank(t, self.clean_plank(
            t, [n for n in range(1, t.count + 1) if n != missing]))
        rel = self.write_long_lived(t, long_lived_source(word(self.rng), [missing]))
        untracked = self.git("-C", str(t.wt), "status", "--porcelain=v1",
                             "--untracked-files=all")
        self.assertIn(rel, untracked, self.msg("файл не остался незакоммиченным"))
        status, output = self.preflight(t.id)
        text = self.msg(f"AC-{missing} в {rel}\n{output}")
        self.assertEqual(status, 0, text)
        self.assertEqual(headers(output, "отказ"), [], text)

    def test_ac3_long_lived_core_error_printed(self):
        """Метод долгоживущего файла без «Ловит мутацию» — отказ со строкой ядра.

        Сценарий: черновик без нарушений; незакоммиченный долгоживущий файл
        задачи покрывает критерий, но его методы без «Ловит мутацию: …».
        Каждая строка `guard.long_lived_errors_from_files` по этому файлу
        (метка — путь от корня рабочей копии) стоит под заголовком отказа;
        код 1.

        Ловит мутацию: ядро долгоживущих файлов не зовётся при наличии
        файлов в рабочей копии либо зовётся с меткой-абсолютным путём —
        строки ядра нет, код 0.
        """
        t = self.new_task()
        n = self.rng.randint(1, t.count)
        self.write_plank(t, self.clean_plank(t))
        source = long_lived_source(word(self.rng), [n], claims=False)
        rel = self.write_long_lived(t, source)
        expected = guard.long_lived_errors_from_files([(rel, source)], t.id)
        self.assertTrue(expected, self.msg("фикстура не даёт ошибки ядра"))
        status, output = self.preflight(t.id)
        text = self.msg(f"{rel}\n{output}")
        self.assertEqual(status, 1, text)
        for line in expected:
            self.assertIn(line, refused_lines(output), text)

    def test_ac3_long_lived_without_group_matches_gate_detail(self):
        """Долгоживущий файл без «Группа: долгоживущий» — строка как в detail гейта перехода.

        Сценарий: черновик без нарушений; долгоживущий файл задачи несёт
        строку группы «разовый» либо не несёт её вовсе (от зерна). Вывод
        предпроверки несёт под заголовком отказа строку ошибки; затем шаг
        переносит черновик и файл штатными чекпоинтами, `advance` пишет
        отказ гейта долгоживущих файлов — та же строка входит в его detail
        (часть до «дальше:» через «; »); код предпроверки 1.

        Ловит мутацию: проверка группы долгоживущего файла пропущена
        (вызывается только ядро, а оно молча пропускает файлы иной группы)
        — отказа нет, код 0; строка собрана с иным текстом или меткой.
        """
        t = self.new_task()
        self.write_plank(t, self.clean_plank(t))
        group = self.rng.choice([guard.GROUP_ONE_OFF, None])
        rel = self.write_long_lived(t, long_lived_source(
            word(self.rng), [self.rng.randint(1, t.count)], group=group))
        status, output = self.preflight(t.id)
        rows, advanced = self.step_and_advance(t)
        detail = self.refusal_detail(rows, transition_gates.LONG_LIVED_ACTION,
                                     advanced)
        pieces = [p for p in detail.split("\nдальше:")[0].split("; ")
                  if p.startswith(rel) and guard.GROUP_LONG_LIVED in p]
        text = self.msg(f"группа {group}\npreflight:\n{output}\nadvance:\n{advanced}")
        self.assertTrue(pieces, text)
        self.assertEqual(status, 1, text)
        for piece in pieces:
            self.assertIn(piece, refused_lines(output), text)


class GroupLineTest(PreflightSandbox):

    def test_ac4_group_line_refusals_match_groups_gate(self):
        """Нет строки группы / «Группа: долгоживущий» в планке — строка как в detail гейта групп.

        Сценарий (порядок от зерна, каждый — своя задача): (а) у файла
        `test_*.py` планки нет строки группы — ожидаемая строка
        `guard.group_line_errors_from_files`; (б) файл планки несёт строку
        группы «долгоживущий» — ожидаемая строка `guard.long_lived_plank_errors`
        (каталог и шаблон имени — профиля тестов артели). Метка —
        acceptance_tests/<файл>. Строка стоит под заголовком отказа
        предпроверки, код 1; та же строка входит в detail отказа «переход
        отклонён: группы приёмочных тестов», который `advance` пишет на
        тех же файлах.

        Ловит мутацию: метка строки группы — путь каталога документов либо
        метка каталог задач/<id>/acceptance_tests/… (как у маркера); в
        проверке строки группы нет `long_lived_plank_errors` — в (б)
        отказа нет, код 0.
        """
        profile = project_profile.decide(config.DEFAULT_TARGET).profile
        self.assertIsNotNone(profile, self.msg("у артели песочницы нет профиля"))
        for kind in self.rng.sample(["без строки группы", "долгоживущий в планке"], 2):
            with self.subTest(kind=kind):
                t = self.new_task()
                files = self.clean_plank(t)
                name = self.rng.choice(sorted(files))
                stem = name[len("test_"):-len(".py")]
                acs = [int(n) for n in re.findall(r"def test_ac(\d+)_", files[name])]
                pair = [("/".join((PLANK_DIR, name)), None)]
                if kind == "без строки группы":
                    files[name] = plank_source(stem, acs, group=None)
                    pair = [(pair[0][0], files[name])]
                    expected = guard.group_line_errors_from_files(pair)
                else:
                    files[name] = plank_source(stem, acs, group=guard.GROUP_LONG_LIVED)
                    pair = [(pair[0][0], files[name])]
                    expected = guard.long_lived_plank_errors(
                        pair, t.id, profile.long_lived_dir, profile.long_lived_name)
                self.write_plank(t, files)
                self.assertTrue(expected, self.msg(kind))
                status, output = self.preflight(t.id)
                rows, advanced = self.step_and_advance(t)
                detail = self.refusal_detail(rows, transition_gates.TEST_GROUPS_ACTION,
                                             advanced)
                text = self.msg(f"{kind}\npreflight:\n{output}\nadvance:\n{advanced}")
                self.assertEqual(status, 1, text)
                for line in expected:
                    self.assertIn(line, refused_lines(output), text)
                    self.assertIn(line, detail, text)


class CleanDraftAndProfileTest(PreflightSandbox):

    def test_ac5_clean_draft_passes_and_lists_not_checked(self):
        """Черновик без нарушений: проверки «пройдена», перечень «не проверяется», код 0.

        Сценарий: задача артели, планка покрывает часть критериев,
        незакоммиченный долгоживущий файл без нарушений — остальные. Вывод
        без заголовка отказа, не меньше шести разных заголовков «…:
        пройдена» (шесть проверок требования 3) и не меньше десяти разных
        строк «не проверяется предпроверкой (проверит переход): <имя>»
        (десять пунктов перечня требования 6); код 0.

        Ловит мутацию: перечень «не проверяется» не печатается или
        печатается одной строкой; пройденная проверка молчит (печатаются
        только отказы); исход 0 считается от числа строк вывода.
        """
        t = self.new_task()
        split = self.rng.randint(1, t.count)
        self.write_plank(t, self.clean_plank(t, range(1, split)))
        self.write_long_lived(t, long_lived_source(
            word(self.rng), list(range(split, t.count + 1))))
        status, output = self.preflight(t.id)
        text = self.msg(output)
        self.assertEqual(status, 0, text)
        self.assertEqual(headers(output, "отказ"), [], text)
        self.assertGreaterEqual(len(set(headers(output, "пройдена"))), 6, text)
        not_checked = {line.strip() for line in output.splitlines()
                       if line.strip().startswith(NOT_CHECKED)
                       and line.strip() != NOT_CHECKED.strip()}
        self.assertGreaterEqual(len(not_checked), 10, text)

    def test_ac5_project_without_profile_skips_and_keeps_journal(self):
        """Проект без профиля тестов: проверки групп и долгоживущих не исполнены, журнал прежний.

        Сценарий: внешний проект без `test_profile`, задача в
        `tests_writing` с рабочей копией кода; в черновике файл `test_*.py`
        без строки группы (у проекта с профилем — отказ строки группы).
        Вывод несёт «не проверяется предпроверкой: у проекта нет профиля
        тестов», заголовка отказа нет, код 0; записи журнала задачи до и
        после предпроверки совпадают.

        Ловит мутацию: у проекта без профиля пишется
        `project_profile.journal_skip`, как в переходе, — в журнале новые
        записи; проверка строки группы исполняется без профиля — отказ.
        """
        target = self.external_project(profile=False)
        t = self.new_task(target=target)
        files = self.clean_plank(t)
        name = self.rng.choice(sorted(files))
        stem = name[len("test_"):-len(".py")]
        acs = [int(n) for n in re.findall(r"def test_ac(\d+)_", files[name])]
        files[name] = plank_source(stem, acs, group=None)
        self.write_plank(t, files)
        before = [dict(r) for r in store.task_steps(self.conn, t.id)]
        status, output = self.preflight(t.id)
        after = [dict(r) for r in store.task_steps(self.conn, t.id)]
        text = self.msg(f"проект {target}\n{output}")
        self.assertIn(NO_PROFILE, output, text)
        self.assertEqual(headers(output, "отказ"), [], text)
        self.assertEqual(status, 0, text)
        self.assertEqual(before, after, text)

    def test_ac5_profile_refusal_prints_gate_detail_and_hint(self):
        """Профиль артели не задан: отказ профиля с detail и hint перехода побайтно.

        Сценарий: из записи артели в `targets.yaml` песочницы убрано поле
        `test_profile`; задача артели в `tests_writing` с черновиком без
        нарушений. Под заголовком отказа предпроверки — строка, равная
        detail записи «переход отклонён: профиль тестов проекта», которую
        пишет `advance`, и строка, равная его подсказке («дальше: …»
        вывода перехода); код 1.

        Ловит мутацию: отказ профиля печатает только detail без hint либо
        склеивает их одной строкой; hint собирается своим текстом, а не
        `project_profile.refusal_hint`.
        """
        text = config.TARGETS.read_text(encoding="utf-8")
        self.assertIn(ARTEL_TEST_PROFILE, text, self.msg("нет профиля артели"))
        config.TARGETS.write_text(text.replace(ARTEL_TEST_PROFILE, ""),
                                  encoding="utf-8")
        t = self.new_task()
        self.write_plank(t, self.clean_plank(t))
        status, output = self.preflight(t.id)
        rows, advanced = self.step_and_advance(t)
        detail = self.refusal_detail(rows, project_profile.REFUSAL_ACTION, advanced)
        hints = [line.split("дальше: ", 1)[1] for line in advanced.splitlines()
                 if "дальше: " in line]
        message = self.msg(f"preflight:\n{output}\nadvance:\n{advanced}")
        self.assertTrue(hints, message)
        self.assertEqual(status, 1, message)
        lines = refused_lines(output)
        self.assertIn(detail, lines, message)
        self.assertIn(hints[0], lines, message)


class ReadOnlyTest(PreflightSandbox):

    def scenarios(self) -> list:
        """[(название, задача)] сценариев AC-1–AC-5 и AC-10."""
        out = []
        t = self.new_task()
        split = self.rng.randint(1, t.count)
        self.write_plank(t, self.clean_plank(t, range(1, split)))
        self.write_long_lived(t, long_lived_source(word(self.rng),
                                                   list(range(split, t.count + 1))))
        out.append(("черновик без нарушений", t))

        t = self.new_task()
        files = self.clean_plank(t, range(2, t.count + 1))
        name = sorted(files)[0]
        stem = name[len("test_"):-len(".py")]
        acs = [int(n) for n in re.findall(r"def test_ac(\d+)_", files[name])]
        files[name] = plank_source(stem, acs, marker=False, group=None)
        self.write_plank(t, files)
        self.write_long_lived(t, long_lived_source(word(self.rng), [1], claims=False))
        out.append(("отказы планки и долгоживущих", t))

        t = self.new_task(code_copy=False)
        self.write_plank(t, self.clean_plank(t))
        out.append(("рабочей копии кода нет", t))

        target = self.external_project(profile=False)
        t = self.new_task(target=target)
        self.write_plank(t, self.clean_plank(t))
        out.append(("проект без профиля", t))

        target = self.external_project(profile=True)
        t = self.new_task(target=target)
        self.write_plank(t, self.clean_plank(t))
        host = f"{word(self.rng)}.example"
        self.write_long_lived(t, long_lived_source(
            word(self.rng), [1], address=f"http{SEP}{host}/x"))
        out.append(("внешний проект с адресом", t))
        return out

    def test_ac6_preflight_changes_nothing(self):
        """После предпроверки не изменились БД, ветки, ссылки, рабочая копия; планка не выложена.

        Сценарий: черновик без нарушений; отказы планки и долгоживущего
        файла; задача без рабочей копии кода; внешний проект без профиля;
        внешний проект с профилем и сетевым адресом в долгоживущем файле;
        затем профиль артели убран (отказ профиля). До и после каждого
        `preflight <id>` совпадают: дамп БД пульта (журнал, lease, строка
        задачи), ссылки клона проекта (ветка задачи, ссылка документов),
        ссылки его `origin`, статус и голова рабочей копии кода, её
        наличие; каталога задачи в рабочей копии кода нет.

        Ловит мутацию: предпроверка заводит рабочую копию кода
        (`workspace.ensure`) — у задачи без копии она появилась;
        выкладывает планку для сбора (`materialize_from_branch`) и не
        убирает; пишет запись журнала или берёт lease; коммитит черновик
        в ссылку документов.
        """
        cases = self.scenarios()
        self.rng.shuffle(cases)
        for label, t in cases:
            with self.subTest(case=label):
                before = self.snapshot(t)
                status, output = self.preflight(t.id)
                self.assertIn(status, (0, 1), self.msg(f"{label}\n{output}"))
                self.assertTrue(sections(output), self.msg(
                    f"{label}: проверки не напечатаны\n{output}"))
                self.assert_unchanged(t, before, label, output)
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.replace(ARTEL_TEST_PROFILE, "", 1),
                                  encoding="utf-8")
        t = self.new_task()
        self.write_plank(t, self.clean_plank(t))
        with self.subTest(case="отказ профиля"):
            before = self.snapshot(t)
            status, output = self.preflight(t.id)
            self.assertEqual(status, 1, self.msg(output))
            self.assertTrue(headers(output, "отказ"), self.msg(output))
            self.assert_unchanged(t, before, "отказ профиля", output)


class StateAndIdTest(PreflightSandbox):

    def test_ac7_wrong_state_exits_2(self):
        """Задача не в `tests_writing` — код выхода 2.

        Сценарий: контроль — задача в `tests_writing` с черновиком без
        нарушений даёт код 0; затем задачи в `spec_writing`, `in_dev`,
        `review`, `verifying` (порядок от зерна) с тем же черновиком —
        `preflight <id>` каждой завершается кодом 2.

        Ловит мутацию: состояние не сверяется — проверки исполняются и код
        0; не то состояние даёт код 1 (как отказ проверки).
        """
        control = self.new_task()
        self.write_plank(control, self.clean_plank(control))
        status, output = self.preflight(control.id)
        self.assertEqual(status, 0, self.msg(f"контроль\n{output}"))
        for state in self.rng.sample(["spec_writing", "in_dev", "review",
                                      "verifying"], 4):
            with self.subTest(state=state):
                t = self.new_task(state=state, code_copy=False)
                self.write_plank(t, self.clean_plank(t))
                status, output = self.preflight(t.id)
                self.assertEqual(status, 2, self.msg(f"{state}\n{output}"))

    def test_ac7_unknown_and_ambiguous_id_same_message_as_show(self):
        """Нет задачи или неоднозначный префикс: сообщение как у `show`, код 2.

        Сценарий: две задачи в `tests_writing`, id которых совпадают в
        первых 20 знаках; аргументы — несуществующий id и общий префикс.
        Для каждого сообщение, которым `artel.py show <аргумент>`
        завершается (`store.get_task`/`store.resolve_task_id`), есть в
        выводе `preflight <аргумент>`, код выхода предпроверки 2.

        Ловит мутацию: неоднозначный префикс молча берёт первую задачу —
        проверки исполняются; сообщение своё, а не `show`; код выхода
        сообщения `sys.exit(<текст>)` — 1 вместо 2.
        """
        prefix = ulid(self.rng)[:20]
        for _ in range(2):
            self.new_task(task_id=prefix + ulid(self.rng)[-6:], code_copy=False)
        unknown = ulid(self.rng)
        for arg in (unknown, prefix):
            with self.subTest(arg=arg):
                _code, shown, message = self.cli("show", arg)
                self.assertTrue(message, self.msg(f"show не отказал: {shown}"))
                status, output = self.preflight(arg)
                text = self.msg(f"{arg}\nshow: {message}\npreflight:\n{output}")
                self.assertIn(message, output, text)
                self.assertEqual(status, 2, text)


class RoleAndDatabaseTest(PreflightSandbox):

    def db_files(self) -> dict:
        db = Path(config.DB)
        wal = db.with_name(db.name + "-wal")
        return {p.name: p.read_bytes() for p in (db, wal) if p.is_file()}

    def test_ac8_allowed_in_role_environment(self):
        """Под маркером роли `preflight` не отклоняется белым списком ролей.

        Сценарий: в окружении маркер роли (`config.ARTEL_ROLE_ENV`, роль
        test_author); черновик без нарушений. Вывод без «команда
        недоступна процессу роли», код 0 — тот же, что без маркера.

        Ловит мутацию: `preflight` не внесена в `_ROLE_ALLOWED_COMMANDS` —
        процесс роли получает отказ белого списка, код 1.
        """
        t = self.new_task()
        self.write_plank(t, self.clean_plank(t))
        status, output = self.preflight(t.id, role="test_author")
        self.assertNotIn(ROLE_REFUSAL, output, self.msg(output))
        self.assertEqual(status, 0, self.msg(output))

    def test_ac8_no_store_db_and_db_file_unchanged(self):
        """`store.db()` не вызывается, файлы БД после предпроверки побайтно прежние.

        Сценарий: черновик с отказом и черновик без нарушений (две задачи,
        порядок от зерна); WAL сброшен в файл БД до прогона, соединение
        пульта держится открытым. Во время `preflight <id>` обёртка
        `store.db` не вызвана ни разу; байты файла БД и его `-wal` до и
        после совпадают.

        Ловит мутацию: предпроверка открывает БД `store.db()` (WAL,
        `migrate`) ради чтения строки задачи; пишет в БД (журнал, lease) —
        меняется `-wal`.
        """
        clean = self.new_task()
        self.write_plank(clean, self.clean_plank(clean))
        refused = self.new_task()
        self.write_plank(refused, self.clean_plank(refused, range(2, refused.count + 1)))
        for t, expected in self.rng.sample([(clean, 0), (refused, 1)], 2):
            with self.subTest(task=t.id):
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                before = self.db_files()
                with mock.patch.object(store, "db", wraps=store.db) as opened:
                    status, output = self.preflight(t.id)
                text = self.msg(output)
                self.assertEqual(status, expected, text)
                self.assertTrue(sections(output), text)
                self.assertEqual(opened.call_count, 0, text)
                self.assertEqual(before, self.db_files(), text)

    def test_ac8_readonly_db_file_same_output_and_code(self):
        """Файл БД только на чтение: тот же вывод и код выхода.

        Сценарий: черновик с отказом и черновик без нарушений; каждый
        гоняется `preflight <id>` при обычном файле БД, затем при файле БД
        с правами только на чтение (`chmod 0444`). Вывод и код выхода
        совпадают; код — 1 и 0 соответственно.

        Ловит мутацию: БД открывается на запись (`store.db()` с `PRAGMA
        journal_mode=WAL` и `migrate`) — на файле только для чтения отказ
        `attempt to write a readonly database` вместо проверок.
        """
        clean = self.new_task()
        self.write_plank(clean, self.clean_plank(clean))
        refused = self.new_task()
        self.write_plank(refused, self.clean_plank(refused, range(2, refused.count + 1)))
        db = Path(config.DB)
        mode = db.stat().st_mode
        self.addCleanup(os.chmod, db, mode)
        for t, expected in ((clean, 0), (refused, 1)):
            with self.subTest(task=t.id):
                os.chmod(db, mode)
                writable = self.preflight(t.id)
                os.chmod(db, 0o444)
                readonly = self.preflight(t.id)
                os.chmod(db, mode)
                text = self.msg(f"запись:\n{writable[1]}\nчтение:\n{readonly[1]}")
                self.assertEqual(writable[0], expected, text)
                self.assertEqual(writable, readonly, text)


class SentryTest(PreflightSandbox):

    def preflight_tree(self) -> ast.Module:
        self.assertTrue(PREFLIGHT_SOURCE.is_file(),
                        self.msg(f"нет {PREFLIGHT_SOURCE}"))
        return ast.parse(PREFLIGHT_SOURCE.read_text(encoding="utf-8"))

    def test_ac9_transition_guard_calls_equal_preflight_and_not_checked(self):
        """Функции guard перехода = функции предпроверки и перечня «не проверяется» без фильтров входа.

        Сценарий: разбором исходника собираются функции guard (обращение
        `guard.<имя>`, имя из `scripts.guard`), которые зовут
        `fsm._tests_writing_ac_state`, `_tests_writing_test_groups_gate` и
        `_tests_writing_long_lived_gate`; и функции guard, которые зовёт
        или называет `orchestrator/preflight.py` (те же два способа и
        упоминание `guard.<имя>` в строке, не докстринге). Фильтр входа
        `is_extraneous_acceptance_test_file` в модуле есть; множество
        перехода равно множеству модуля без фильтров входа.

        Ловит мутацию: (а) проверка предпроверки зовёт не то ядро (например
        `scan_redness_markers` вместо `redness_marker_errors_from_files`) —
        ядра перехода нет в модуле; (б) в тело перехода добавлен вызов
        `guard.<новая функция>` — его нет ни в предпроверке, ни в перечне;
        (в) пункт перечня называет функцию, которую переход не зовёт
        (например `scan_artifact_disk_reads`) — лишняя функция в модуле.
        """
        transition, missing = transition_guard_calls()
        self.assertEqual(missing, [], self.msg("тела перехода не найдены"))
        self.assertIn("scan_ac_content", transition, self.msg(str(transition)))
        named = preflight_guard_names(self.preflight_tree())
        self.assertLessEqual(INPUT_FILTERS, named, self.msg(
            f"фильтра входа нет в предпроверке: {sorted(named)}"))
        covered = named - INPUT_FILTERS
        self.assertEqual(
            transition, covered,
            self.msg(f"переход без предпроверки и перечня: "
                     f"{sorted(transition - covered)}; предпроверка и перечень "
                     f"без перехода: {sorted(covered - transition)}"))

    def test_ac9_autocommit_calls_input_filters(self):
        """Автокоммит зовёт каждую функцию перечня «фильтры входа».

        Сценарий: разбором исходника `orchestrator/checkpoint.py`
        собираются вызовы функций guard; каждый фильтр входа предпроверки
        (`is_extraneous_acceptance_test_file`) среди них.

        Ловит мутацию: (ж) автокоммит перестал звать фильтр (своя регулярка
        вместо вызова) либо зовёт другой (`is_extraneous_task_root_file`) —
        фильтры входа предпроверки и автокоммита разошлись.
        """
        tree = module_tree(checkpoint)
        aliases, imported = guard_bindings(tree)
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called |= referenced_guard_names(node.func, aliases, imported)
        self.assertLessEqual(INPUT_FILTERS, called, self.msg(sorted(called)))

    def test_ac9_guard_imported_only_by_allowed_forms(self):
        """guard в предпроверке — только `from scripts import guard` и `from scripts.guard import …`.

        Сценарий: разбором исходника `orchestrator/preflight.py` ищутся
        `import scripts`/`import scripts.guard [as …]`, `from scripts import
        guard as <иное имя>`, `from scripts import *` и строки
        «scripts.guard» вне докстрингов (`importlib.import_module`,
        `__import__`); ни одного нет, и guard импортирован разрешённой
        формой.

        Ловит мутацию: (з) guard импортирован как `import scripts.guard as
        g` или через `importlib` — обращения `g.<имя>` сторож не считает, и
        сверка множеств слепнет.
        """
        tree = self.preflight_tree()
        self.assertEqual(foreign_guard_imports(tree), [], self.msg())
        aliases, imported = guard_bindings(tree)
        self.assertTrue(aliases or imported, self.msg("guard не импортирован"))

    def test_ac9_preflight_under_side_effect_stubs(self):
        """Под заглушками побочных эффектов предпроверка отрабатывает, не задев ни одной.

        Сценарий: заглушки на `store.journal`, `workspace.ensure`,
        `acceptance.materialize_from_branch`,
        `acceptance.drop_from_code_copy` и на запуск git с подкомандой
        commit/commit-tree/push/update-ref (`subprocess.run`/`Popen`)
        записывают обращение и бросают исключение. Сценарии: черновик без
        нарушений (код 0), отказ планки и долгоживущего файла (код 1),
        проект без профиля (код 0). Код выхода ожидаемый, обращений нет.

        Ловит мутацию: (г) предпроверка пишет в журнал (`journal_skip` у
        проекта без профиля, запись отказа); (д) коммитит черновик в
        ссылку документов или делает push; (е) зовёт `workspace.ensure`,
        `materialize_from_branch` или `drop_from_code_copy`, как сухой сбор
        перехода.
        """
        cases = []
        t = self.new_task()
        self.write_plank(t, self.clean_plank(t))
        cases.append(("без нарушений", t, 0))
        t = self.new_task()
        self.write_plank(t, self.clean_plank(t, range(2, t.count + 1)))
        self.write_long_lived(t, long_lived_source(word(self.rng), [1], claims=False))
        cases.append(("отказ", t, 1))
        target = self.external_project(profile=False)
        t = self.new_task(target=target)
        self.write_plank(t, self.clean_plank(t))
        cases.append(("без профиля", t, 0))
        self.rng.shuffle(cases)
        for label, t, expected in cases:
            with self.subTest(case=label):
                hits = []
                with self.side_effect_stubs(hits):
                    status, output = self.preflight(t.id)
                text = self.msg(f"{label}: обращения {hits}\n{output}")
                self.assertEqual(hits, [], text)
                self.assertEqual(status, expected, text)

    @contextlib.contextmanager
    def side_effect_stubs(self, hits: list):
        def deny(name):
            def stub(*_args, **_kwargs):
                hits.append(name)
                raise AssertionError(f"предпроверка позвала {name}")
            return stub

        def git_guarded(real, name):
            def call(cmd, *args, **kwargs):
                sub = git_subcommand(cmd if cmd is not None else kwargs.get("args"))
                if sub in DENIED_GIT:
                    hits.append(f"{name}: git {sub}")
                    raise AssertionError(f"предпроверка позвала git {sub}")
                return real(cmd, *args, **kwargs)
            return call

        with contextlib.ExitStack() as stack:
            for module, attr in ((store, "journal"), (workspace, "ensure"),
                                 (acceptance, "materialize_from_branch"),
                                 (acceptance, "drop_from_code_copy")):
                stack.enter_context(mock.patch.object(
                    module, attr, deny(f"{module.__name__}.{attr}")))
            stack.enter_context(mock.patch.object(
                subprocess, "run", git_guarded(REAL_RUN, "subprocess.run")))
            stack.enter_context(mock.patch.object(
                subprocess, "Popen", git_guarded(REAL_POPEN, "subprocess.Popen")))
            yield


class NetworkAddressTest(PreflightSandbox):

    def test_ac10_network_address_only_for_artel(self):
        """Сетевой адрес в долгоживущем файле: отказ у артели, молчание у внешнего проекта.

        Сценарий: долгоживущий файл задачи (иначе без нарушений) несёт
        адрес со схемой http и DNS-именем (имя от зерна, вне
        `guard.NETWORK_ADDRESS_EXCEPTIONS`). У задачи артели под заголовком
        отказа — строка `guard.network_address_errors_from_files` по этому
        файлу, код 1. У задачи внешнего проекта с профилем тестов строки
        ошибки сетевого адреса в выводе нет.

        Ловит мутацию: признак сетевых адресов передаётся константой
        (`True` — внешний проект получает отказ инварианта 35; `False` —
        артель его не получает), а не `repo_context.is_artel(target)`.
        """
        host = f"{word(self.rng)}.{self.rng.choice(['example', 'test', 'org'])}"
        address = f"http{SEP}{host}/x"
        external = self.external_project(profile=True)
        for target in self.rng.sample([config.DEFAULT_TARGET, external], 2):
            with self.subTest(target=target):
                t = self.new_task(target=target)
                self.write_plank(t, self.clean_plank(t))
                source = long_lived_source(word(self.rng), [1], address=address)
                rel = self.write_long_lived(t, source)
                expected = guard.network_address_errors_from_files([(rel, source)])
                self.assertTrue(expected, self.msg("фикстура без ошибки адреса"))
                status, output = self.preflight(t.id)
                text = self.msg(f"{target}: {rel}\n{output}")
                if target == config.DEFAULT_TARGET:
                    self.assertEqual(status, 1, text)
                    for line in expected:
                        self.assertIn(line, refused_lines(output), text)
                else:
                    self.assertTrue(headers(output, "пройдена"), text)
                    for line in expected:
                        self.assertNotIn(line, output, text)
                    self.assertNotIn("сетевой адрес", output, text)


if __name__ == "__main__":
    unittest.main()
