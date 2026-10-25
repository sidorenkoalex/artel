"""Песочницы гейта исходов G3б-2: прежние версии, заменяемые тесты, строгий режим."""
import contextlib
import hashlib
import io
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

from orchestrator import answer, liveness, project_profile, store
from orchestrator.advance_gates import mandate
from scripts import guard
from tests.sandbox import make_project_repo
from tests.outcome_gate_sandbox import (
    ENTRY_HEAD, MATRIX_HEADERS, OutcomeGateSandbox, flow, js_source,
    py_source)
from tests.merge_outcome_sandbox import (
    MergeOutcomeSandbox)

GATE_MODULE = "orchestrator.advance_gates.outcome_integrity"
OLD = "old"
SIDES = ("base", "head")

OUTCOME_ACTION = "переход отклонён: гейт неослабления по исходам"
BROKEN_ACTION = "переход отклонён: гейт неослабления по исходам — сломан правкой"
PREPARE_ACTION = "переход отклонён: гейт неослабления по исходам — подготовка"
PASSED_ACTION = "гейт неослабления по исходам пройден"
MANDATE_MARKER = "Ослабление тестов разрешено:"
ID_MARKER = "Ослабление теста по идентификатору разрешено:"

GONE = "исчез"
SKIPPED = "стал пропуском"
PRIOR_RED = "прежняя версия красная на коде ветки"
PRIOR_UNSTABLE = "прежняя версия нестабильна на коде ветки"
REPL_MISSING = "заменяемый тест не найден в отчёте базы"
REPL_NOT_GREEN = "заменяемый тест не зелёный на базе"
REPL_NEEDLESS = "замена не нужна: прежняя версия зелёная на коде ветки"
STRICT = "строгий режим — правка существующего файла"
CODE_EXC = "исключение в коде"
FLAKY = "нестабилен и на базе"
REPLACED = "заменён по SPEC"
COVERED_BY_REPLACEMENT = " — покрыто мандатом замена SPEC → AC-{n}"
PRIOR_LINE = re.compile(r"^прежние версии: файлов (\d+); прогонов (\d+)$")
PROOF_LINE = re.compile(
    r"^голова ([0-9a-f]{40}); база ([0-9a-f]{40}); ключ (\S+); мандат (\S+)$")
COUNTS_MARK = "тестов базы"
# Подстроки исключений в коде — перечень требования 7 SPEC.
TOKENS = ("v8 ignore", "istanbul ignore", "c8 ignore", "eslint-disable",
          "import.meta.env.MODE", "process.env.VITEST", "NODE_ENV")
# Метка файла тестов, который на этой стороне даёт только запись ошибки
# уровня файла (сбор модуля).
FILE_ERROR_MARK = "# сбор-ошибка сценария"
CLAIM = "Ловит мутацию: фикстура сценария — исход теста другой."


class Moved(NamedTuple):
    """Значение правки сценария: `git mv <source> <путь>` без правки строк."""
    source: str


class Link(NamedTuple):
    """Значение правки сценария: путь становится символьной ссылкой."""
    target: str


class PriorSandbox(MergeOutcomeSandbox):
    """Песочница G3а-1а и гейта мержа плюс сторона прежних версий, учёт
    `worktree add` гейта, проекты с полями `tests`/`test_support`/`layers`/
    `paths`, утверждённые замены и мандаты Оператора."""

    def setUp(self):
        # Шпионы песочницы ставятся в её `setUp` и сразу зовутся.
        self.gate_adds: list = []
        self.rescue: tuple = ()
        self.watch_old: tuple = ()
        self.run_root = None
        super().setUp()

    # --- шпионы ---------------------------------------------------------

    def in_outcome_gate(self) -> bool:
        frame = sys._getframe(1)
        while frame is not None:
            if frame.f_globals.get("__name__") == GATE_MODULE:
                return True
            frame = frame.f_back
        return False

    @staticmethod
    def add_path(args) -> Path | None:
        """Путь выписки аргументов `worktree add`; `None` — не она."""
        parts = [str(a) for a in args]
        if "worktree" not in parts or "add" not in parts:
            return None
        rest = [p for p in parts[parts.index("add") + 1:] if not p.startswith("-")]
        return Path(rest[0]) if rest else None

    def spy_run(self, argv, *args, **kwargs):
        if isinstance(argv, (list, tuple)) and argv and argv[0] == "git":
            path = self.add_path(argv[1:])
            if path is not None and self.in_outcome_gate():
                self.gate_adds.append({
                    "path": path,
                    "marker": (path.parent / liveness.GATE_OWNER_MARKER).exists()})
        return super().spy_run(argv, *args, **kwargs)

    @staticmethod
    def tree_root(cwd: Path) -> Path:
        for folder in (cwd, *cwd.parents):
            if (folder / ".git").exists():
                return folder
        return cwd

    def side_of(self, cwd: Path) -> str:
        side = OutcomeGateSandbox.side_of(cwd)
        if side != "head":
            return side
        root = self.tree_root(Path(cwd))
        if root.name not in SIDES and \
                (root.parent / liveness.GATE_OWNER_MARKER).exists():
            return OLD
        return side

    def runner_run(self, kind, parts, cwd, args, kwargs):
        self.run_root = self.tree_root(Path(cwd))
        proc = super().runner_run(kind, parts, cwd, args, kwargs)
        self.runs[-1]["seen"] = {rel: (self.run_root / rel).exists()
                                 for rel in self.watch_old}
        return proc

    def outcome_of(self, side: str, rel: str, name: str) -> str:
        if side == OLD and self.rescue and self.run_root is not None and any(
                (self.run_root / p).exists() for p in self.rescue):
            return "passed"
        return super().outcome_of(side, rel, name)

    def junit_report(self, run: dict, files: list) -> tuple:
        broken = [rel for rel, text in files if FILE_ERROR_MARK in text]
        text, red = super().junit_report(
            run, [(rel, body) for rel, body in files if FILE_ERROR_MARK not in body])
        if not broken:
            return text, red
        cases = "".join(
            f'<testcase file="{rel}" classname="" name="{rel[:-3].replace("/", ".")}"'
            f' time="0.01"><error message="collection failure">ImportError: '
            f'сбор сценария</error></testcase>' for rel in broken)
        return text.replace("</testsuite>", cases + "</testsuite>", 1), True

    def run_advance(self, tid: str) -> tuple:
        self.gate_adds.clear()
        return super().run_advance(tid)

    def approve(self, t) -> tuple:
        self.gate_adds.clear()
        return super().approve(t)

    # --- проекты --------------------------------------------------------

    def entry(self, fields: dict) -> tuple:
        name, comp = f"j{self.word()}", f"c{self.word()}"
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 f"      {comp}:\n"]
        for key, value in fields.items():
            lines.append(f"        {key}: {value}\n")
        self.append_entry("".join(lines))
        return name, comp

    def project(self, kind: str, fields: dict, files: dict) -> SimpleNamespace:
        name, comp = self.entry(fields)
        clone = make_project_repo(name)
        self.commit_project(clone, files)
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comp, layout=fields["plank_layout"],
                               kind=kind, clone=clone)

    def junit(self, tests: dict, extra: dict | None = None,
              files: dict | None = None) -> SimpleNamespace:
        """Компонент `junit-xml` на поддельном `pytest` (действующие слои —
        `python-ast`); `tests` — {путь: [имена]} тестов базы; `extra` — поля
        записи сверх прежних (значения — текстом YAML); `files` — прочие
        файлы базы."""
        fields = {"command": flow([str(self.pytest_cmd)]),
                  "report": "junit-xml",
                  "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": flow(["tests/**"]),
                  "mutation_claim_scope": flow(["tests/**"]),
                  "failure_errors": flow(["AssertionError"]),
                  "plank_layout": f".pj{self.word(5)}/<id>"}
        fields.update(extra or {})
        base = {"app.py": "APP = 'base'\n", **(files or {})}
        base.update({rel: py_source(names) for rel, names in tests.items()})
        return self.project("junit", fields, base)

    def vitest(self, tests: dict, extra: dict | None = None,
               files: dict | None = None) -> SimpleNamespace:
        """Компонент `pult-vitest` (строгий режим: слоёв нет); `tests` —
        {путь: [имена]} тестов базы."""
        fields = {"command": flow(self.vitest_argv()),
                  "report": "pult-vitest",
                  "report_args": flow(["--reporter=default",
                                       "--reporter={pult_reporter}",
                                       "--outputFile={path}"]),
                  "install": flow([str(self.installer)]),
                  "tests": flow(["frontend/src/**/*.test.jsx"]),
                  "plank_layout": f"frontend/src/.pv{self.word(5)}/<id>",
                  "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx",
                  "weakening_scope": flow(["frontend/src/**"]),
                  "mutation_claim_scope": flow(["frontend/claims/**"]),
                  "failure_errors": flow(["AssertionError"]),
                  "select": flow([f"--sel{self.word()}", "{tests}"])}
        fields.update(extra or {})
        name, comp = self.entry(fields)
        self.append_entry("        tools:\n"
                          f'          vitest: "{self.vitest_version}"\n')
        clone = make_project_repo(name)
        base = {"package.json": '{"name": "web"}\n',
                "vitest.config.js": "export default {}\n",
                "package-lock.json": '{"lockfileVersion": 3}\n',
                "app.py": "APP = 'base'\n", **(files or {})}
        base.update({rel: js_source(names) for rel, names in tests.items()})
        self.commit_project(clone, base)
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comp, layout=fields["plank_layout"],
                               kind="vitest", clone=clone)

    @staticmethod
    def vitest_argv() -> tuple:
        return project_profile.VITEST_BASE_ARGV

    def commit_code(self, t, changes: dict, message: str = "код разработчика"):
        """Коммит правки кодовой ветки: значение — текст, байты, `None`
        (удалить), `Moved` (переименовать) или `Link` (символьная ссылка)."""
        files = {"app.py": f"APP = 'head-{self.word()}'\n", **changes}
        # Зоны — все пути веток задачи: повторный шаг не сужает их.
        zones = set(getattr(t, "zones", ())) | set(files)
        t.zones = zones
        for rel, value in files.items():
            path = t.wt / rel
            if value is None:
                self.git("-C", str(t.wt), "rm", "-q", "--", rel)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, Moved):
                zones.add(value.source)
                self.git("-C", str(t.wt), "mv", value.source, rel)
                continue
            if isinstance(value, Link):
                if path.exists() or path.is_symlink():
                    path.unlink()
                os.symlink(value.target, path)
            elif isinstance(value, bytes):
                path.write_bytes(value)
            else:
                path.write_text(value, encoding="utf-8")
            self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", message)
        store.update_task(self.conn, t.id, zones=", ".join(sorted(zones)))

    # --- замены и мандаты -----------------------------------------------

    def approve_replacements(self, t, items: dict) -> None:
        """Запись утверждённых замен `{идентификатор: номер критерия}`."""
        detail = "\n".join(
            guard.ReplacedTest(cid, n, f"замена сценария {self.word()}").line
            for cid, n in items.items())
        store.journal(self.conn, t.id, "operator",
                      mandate.REPLACED_TESTS_ACTION, detail)

    def operator_answer(self, t, paths=(), ids=(), covered="tests/sandbox.py:1"):
        """ANSWER Оператора (`answer.cmd_answer`) с мандатом на `paths`
        (прежний маркер) и `ids` (по строке маркера по идентификатору):
        (принят ли, вывод)."""
        head = []
        if paths:
            head.append(f"{MANDATE_MARKER} {', '.join(paths)}")
        head += [f"{ID_MARKER} {cid}" for cid in ids]
        row = (", ".join(f"`{e}`" for e in (*paths, *ids)),
               "фикстура теста — tests/sandbox.py:1", "да", covered, "ок")
        text = ("\n\n".join(head) + "\n\n"
                "Независимая проверка: матрица подтверждена\n\n"
                f"Основание: решение Оператора ({self.seed}).\n\n"
                "## Матрица неослабления\n\n"
                "| " + " | ".join(MATRIX_HEADERS) + " |\n"
                + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
                + "| " + " | ".join(row) + " |\n")
        path = self.root / ".artel" / f"answer-{self.word()}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        code = None
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                answer.cmd_answer(t.id, str(path))
            except SystemExit as exc:
                code = exc.code
        return code in (None, 0), f"код {code}: {buf.getvalue()}"

    def grant(self, t, paths=(), ids=(), covered="tests/sandbox.py:1") -> None:
        ok, output = self.operator_answer(t, paths, ids, covered)
        self.assertTrue(ok, self.note(f"answer отказала: {output}"))

    # --- наблюдения -----------------------------------------------------

    def third_adds(self) -> list:
        return [a for a in self.gate_adds if a["path"].name not in SIDES]

    def old_runs(self) -> list:
        return [r for r in self.runs if r["side"] == OLD and not r["plank"]]

    def old_files(self) -> set:
        return {rel for r in self.old_runs() for rel in r["files"]}

    def passed(self, rows: list, output: str) -> str:
        found = self.details(rows, PASSED_ACTION)
        self.assertTrue(found, f"записи «{PASSED_ACTION}» нет:\n"
                        + self.explain(rows, output))
        return found[-1]

    @staticmethod
    def starting(detail: str, prefix: str) -> list:
        return [line for line in detail.splitlines() if line.startswith(prefix)]

    def touch_py(self) -> str:
        return f"\n# правка {self.word()}\n"

    def touch_js(self) -> str:
        return f"\n// правка {self.word()}\n"

    def edited_py(self, names) -> str:
        return py_source(names) + self.touch_py()

    def edited_js(self, names) -> str:
        return js_source(names) + self.touch_js()


class ReplacementSandbox(PriorSandbox):

    def replaced(self, base, head, old, edit: bool = False,
                 more: dict | None = None):
        """Задача с утверждённой заменой теста `rname` файла `rel` (рядом —
        тест `other`, `self.other`): исходы сценария по сторонам; `edit` —
        ветка правит файл (комментарий); `more` — прочие файлы тестов
        базы. (проект, задача, путь, идентификатор, номер критерия, правка
        кода)."""
        rel, rname, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit({rel: [rname, other], **(more or {})})
        t = self.task(project)
        rid = self.case_id(project, rel, rname)
        n = self.rng.randrange(1, 60)
        self.approve_replacements(t, {rid: n})
        self.cases[(rel, rname)] = {"base": base, "head": head, OLD: old}
        self.other = other
        changes = {rel: self.edited_py([rname, other])} if edit else {}
        return project, t, rel, rid, n, changes


class StrictSandbox(PriorSandbox):

    def js_case(self) -> str:
        """Имя теста Vitest без пробела — годится в префикс `путь::имя`."""
        return f"case_{self.word()}"
