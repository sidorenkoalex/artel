"""Сценарий эталона мест таблицы «Места задачи и исход при отказе `for_task`»
у записей, которых задача касаться не должна (AC-15, AC-26): артель, запись
`test_profile`, записи из одного компонента (в границе гейта исходов и вне
её), задача-канарейка.

Файл исполняется отдельным процессом: `python3 _etalon.py <зерно>` из корня
дерева кода (пина или ветки задачи — `PYTHONPATH` указывает на него), печатает
JSON выводов мест между строками-метками. Импортирует только то, что есть в
коде пина: `orchestrator`, `tests.sandbox`. Пути песочницы, sha и метки
времени нормализуются — эталон сравним между двумя запусками.
"""
import contextlib
import io
import json
import random
import re
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import (acceptance, amend, catalog, checkpoint, config,
                          knowledge_cards, preflight, project_profile, runner,
                          store, workspace)
from orchestrator.advance_gates import mandate
from tests.sandbox import RealGitSandbox, capture, make_project_repo

BEGIN = "=== ЭТАЛОН НАЧАЛО ==="
END = "=== ЭТАЛОН КОНЕЦ ==="
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

TEST_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

APP = """    components:
      app:
        command: [python3, -m, pytest]
{report}        long_lived_dir: backend/tests
        long_lived_name: test_<id>_<name>.py
        weakening_scope: [backend/tests/**]
        mutation_claim_scope: [backend/tests/test_*.py]
        failure_errors: [AssertionError]
        tests: [backend/tests/**/test_*.py]
        plank_layout: backend/tests/.pb/<id>
        paths: [^backend/]
        test_support: [backend/testkit/**]
        full_suite_timeout_sec: 311
"""

WEB = """    components:
      web:
        command: [{vitest}]
        report: pult-vitest
        tests: [frontend/src/**/*.test.jsx]
        plank_layout: frontend/src/.pv/<id>
        long_lived: frontend/src/<dir>/<name>.<id>.test.jsx
        weakening_scope: [frontend/src/**]
        mutation_claim_scope: [frontend/claims/**]
        failure_errors: [AssertionError]
        paths: [^frontend/]
        checks_local: [frontend-check, --strict]
        knowledge: [docs/frontend-guide.md]
        full_suite_timeout_sec: 422
"""

PROFILE_FIELDS = ("component", "command", "report", "long_lived_dir",
                  "long_lived_name", "long_lived", "weakening_scope",
                  "mutation_claim_scope", "tests", "test_support", "paths",
                  "plank_layout", "checks_local", "knowledge",
                  "full_suite_timeout_sec")

WEAKEN_PATHS = ("tests/test_old.py", "backend/tests/test_old.py",
                "backend/app.py", "frontend/src/ui/old.test.jsx",
                "frontend/src/App.jsx", "docs/notes.md")
ID_COMPONENTS = ("app", "web", "frontend", "nosuch")
COVER_CELLS = ("tests/test_new.py:1", "backend/tests/test_new.py:1",
               "`app:backend/tests/test_a.py::test_x`",
               "`web:frontend/src/a.test.jsx::t > x`",
               "frontend/src/ui/new.test.jsx", "backend/app.py", "не покрыто")
MATRIX_HEADERS = ("Что меняется", "Какое свойство сейчас держит (тест)",
                  "Остаётся ли свойство после изменения",
                  "Чем покрыто после (тест файл:строка) или «не покрыто»",
                  "Решение")

RESULT: dict = {}


def _summary(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseException):
        return f"{type(value).__name__}: {value}"
    if isinstance(value, (tuple, list)):
        return [_summary(v) for v in value]
    if hasattr(value, "refusal") and hasattr(value, "skip"):
        return {"refusal": getattr(value, "refusal", None),
                "skip": _summary(getattr(value, "skip", None)),
                "profile": _summary(getattr(value, "profile", None))}
    if hasattr(value, "command"):
        return {f: _summary(getattr(value, f, None)) for f in PROFILE_FIELDS}
    return type(value).__name__


def _matrix(element: str, covered: str) -> str:
    row = (f"`{element}`", "тест", "остаётся", covered, "ок")
    return ("## Матрица неослабления\n\n"
            "| " + " | ".join(MATRIX_HEADERS) + " |\n"
            + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
            + "| " + " | ".join(row) + " |\n")


class Etalon(RealGitSandbox):

    SEED = 0

    def setUp(self):
        super().setUp()
        self.rng = random.Random(self.SEED)
        self.conn = store.db()
        self.add_synced_origin()
        entries = {"tp": HEAD.format(name="tp") + TEST_PROFILE,
                   "onepy": HEAD.format(name="onepy")
                   + APP.format(report="        report: junit-xml\n"),
                   "onebare": HEAD.format(name="onebare") + APP.format(report=""),
                   "onevt": HEAD.format(name="onevt") + WEB.format(
                       vitest=", ".join(project_profile.VITEST_BASE_ARGV))}
        text = config.TARGETS.read_text(encoding="utf-8").rstrip("\n") + "\n"
        config.TARGETS.write_text(text + "".join(entries.values()),
                                  encoding="utf-8")
        self.clones = {name: make_project_repo(name) for name in entries}
        capture(catalog.cmd_init)
        self.roots = sorted({str(self.root), str(Path(self.root).resolve()),
                             str(Path(tempfile.gettempdir())),
                             str(Path(tempfile.gettempdir()).resolve())},
                            key=len, reverse=True)

    def norm(self, value):
        text = json.dumps(_summary(value), ensure_ascii=False, sort_keys=True) \
            if not isinstance(value, str) else value
        for root in self.roots:
            text = text.replace(root, "<root>")
        text = re.sub(r"\b[0-9a-f]{40}\b", "<sha>", text)
        text = re.sub(r"\b[0-9a-f]{7,12}\b", "<short>", text)
        text = re.sub(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(\.\d+)?Z?", "<ts>", text)
        text = re.sub(r"0x[0-9a-f]+", "0x?", text)
        text = re.sub(r"<root>/[^\s'\"]*", lambda m: re.sub(
            r"(tmp|artel-)[\w-]{6,}", "<tmp>", m.group(0)), text)
        return text

    def place(self, key: str, fn, *args, **kwargs) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                value = fn(*args, **kwargs)
            except SystemExit as exc:
                value = f"SystemExit: {exc.code}"
            except Exception as exc:  # noqa: BLE001 — исход места любой формы
                value = exc
        RESULT[key] = {"value": self.norm(value), "out": self.norm(buf.getvalue())}

    def task(self, target: str, state: str, canary: bool = False) -> str:
        tid = "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))
        store.insert_task(self.conn, tid, f"Задача {target}", state,
                          f"task/{tid.lower()}-e", target, 25.0, is_canary=canary)
        return tid

    def journal(self, tid: str) -> list:
        return [self.norm(f"{r['action']}: {r['detail'] or ''}".replace(tid, "<id>"))
                for r in store.task_steps(self.conn, tid)]

    def test_collect(self):
        targets = (config.DEFAULT_TARGET, "tp", "onepy", "onebare", "onevt")
        for target in targets:
            for canary in (False, True):
                tid = self.task(target, "in_dev", canary)
                k = f"{target}{'/canary' if canary else ''}"
                self.place(f"{k}/for_task", project_profile.for_task, self.conn, tid)
                self.place(f"{k}/decide", project_profile.decide, target)
                for path in WEAKEN_PATHS:
                    line = f"{mandate.TEST_WEAKENING_MANDATE_MARKER} {path}\n"
                    self.place(f"{k}/weaken/{path}", mandate.refusals, line, None,
                               conn=self.conn, task_id=tid)
                    for cell in COVER_CELLS:
                        self.place(f"{k}/matrix/{path}/{cell}",
                                   mandate.matrix_refusals, _matrix(path, cell),
                                   [path], conn=self.conn, task_id=tid)
                for comp in ID_COMPONENTS:
                    for path in ("backend/tests/test_a.py", "frontend/src/a.test.jsx",
                                 "tests/test_a.py"):
                        ident = f"{comp}:{path}::test_x"
                        line = f"{mandate.TEST_ID_MANDATE_MARKER} {ident}\n"
                        self.place(f"{k}/id/{ident}", mandate.refusals, line, None,
                                   conn=self.conn, task_id=tid)
                        self.place(f"{k}/idmatrix/{ident}", mandate.matrix_refusals,
                                   _matrix("x", f"`{ident}`"), [], conn=self.conn,
                                   task_id=tid, test_ids=[])
                self.place(f"{k}/acc_own", acceptance._task_own_profile,
                           self.conn, tid)
                self.place(f"{k}/acc_task", acceptance._task_profile, self.conn, tid)
                self.place(f"{k}/amend_task", amend._task_profile, tid)
                self.place(f"{k}/amend_exit", amend._profile_or_exit, self.conn, tid)
                self.place(f"{k}/knowledge", knowledge_cards.cmd_knowledge,
                           [tid, "::x"])
                RESULT[f"{k}/journal"] = self.journal(tid)
        for target in targets[1:]:
            self.worktree_places(target)

    def worktree_places(self, target: str) -> None:
        tid = self.task(target, "tests_writing")
        branch = store.get_task(self.conn, tid)["branch"]
        wt, error = workspace.ensure(tid, branch, target)
        RESULT[f"{target}/wt"] = self.norm(str(error))
        if error:
            return
        wt = Path(wt)
        low = tid.lower()
        files = {f"tests/test_{low}_x.py": "# t\n",
                 f"backend/tests/test_{low}_x.py": "# t\n",
                 f"frontend/src/ui/btn.{low}.test.jsx": "// t\n",
                 "docs/stray.md": "x\n"}
        docs = self.root / "docs-etalon" / tid
        docs.mkdir(parents=True, exist_ok=True)
        self.place(f"{target}/missing_empty", runner._missing_required_artifact,
                   "test_author", wt, tid, docs_dir=docs, conn=self.conn)
        self.place(f"{target}/preflight", preflight.cmd_preflight, tid)
        for rel, body in files.items():
            (wt / rel).parent.mkdir(parents=True, exist_ok=True)
            (wt / rel).write_text(body, encoding="utf-8")
        self.place(f"{target}/missing_files", runner._missing_required_artifact,
                   "test_author", wt, tid, docs_dir=docs, conn=self.conn)
        self.place(f"{target}/checkpoint_ta", checkpoint.commit_success_checkpoint,
                   self.conn, tid, "test_author")
        head = self.git("-C", str(wt), "ls-tree", "-r", "--name-only", "HEAD")
        RESULT[f"{target}/head_ta"] = sorted(
            p.replace(low, "<id>") for p in head.split() if low in p or "stray" in p)
        store.update_task(self.conn, tid, state="in_dev")
        (wt / "backend" / "app.py").parent.mkdir(parents=True, exist_ok=True)
        (wt / "backend" / "app.py").write_text("x = 1\n", encoding="utf-8")
        self.place(f"{target}/checkpoint_dev", checkpoint.commit_success_checkpoint,
                   self.conn, tid, "developer")
        RESULT[f"{target}/journal_wt"] = self.journal(tid)


def main() -> int:
    Etalon.SEED = int(sys.argv[1])
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Etalon)
    out = io.StringIO()
    result = unittest.TextTestRunner(stream=out, verbosity=0).run(suite)
    if not result.wasSuccessful():
        print(out.getvalue(), file=sys.stderr)
        return 2
    print(BEGIN)
    print(json.dumps(RESULT, ensure_ascii=False, sort_keys=True, indent=1))
    print(END)
    return 0


if __name__ == "__main__":
    sys.exit(main())
