"""Учебный проект из двух компонентов (SPEC, требование 6; AC-22) и лёгкая
песочница мест таблицы «Места задачи и исход при отказе `for_task`».

`backend` — `junit-xml` с командой pytest; `frontend` — `pult-vitest`,
`depends_on` вида `files` на `backend/seed/`. Задача заводится строкой БД с
зонами одного из вариантов: `frontend`, `backend` (компонент задачи),
`both`, `outside`, `none` (три варианта отказа AC-24).
"""
import contextlib
import io
import random
import re
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import config, project_profile, store
from tests.sandbox import TaskIdSchemaConnTmpRootTest, make_project_repo

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

ENTRY_HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


BACKEND_LIMIT = 311
FRONTEND_LIMIT = 422
FRONTEND_CHECK = ["frontend-check", "--strict"]
FRONTEND_KNOWLEDGE = "docs/frontend-guide.md"

BACKEND_FIELDS = {
    "command": flow(["python3", "-m", "pytest"]),
    "report": "junit-xml",
    "long_lived_dir": "backend/tests",
    "long_lived_name": "test_<id>_<name>.py",
    "weakening_scope": flow(["backend/tests/**"]),
    "mutation_claim_scope": flow(["backend/tests/test_*.py"]),
    "failure_errors": flow(["AssertionError"]),
    "tests": flow(["backend/tests/**/test_*.py"]),
    "plank_layout": "backend/tests/.pb/<id>",
    "paths": flow(["^backend/"]),
    "test_support": flow(["backend/testkit/**"]),
    "full_suite_timeout_sec": str(BACKEND_LIMIT),
}

FRONTEND_FIELDS = {
    "command": flow(project_profile.VITEST_BASE_ARGV),
    "report": "pult-vitest",
    "tests": flow(["frontend/src/**/*.test.jsx"]),
    "plank_layout": "frontend/src/.pv/<id>",
    "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx",
    "weakening_scope": flow(["frontend/src/**"]),
    "mutation_claim_scope": flow(["frontend/claims/**"]),
    "failure_errors": flow(["AssertionError"]),
    "paths": flow(["^frontend/"]),
    "test_support": flow(["frontend/e2e/**"]),
    "checks_local": flow(FRONTEND_CHECK),
    "knowledge": flow([FRONTEND_KNOWLEDGE]),
    "full_suite_timeout_sec": str(FRONTEND_LIMIT),
}

FRONTEND_DEPENDS = ("        depends_on:\n"
                    "          backend:\n"
                    "            via: files\n"
                    "            paths: [^backend/seed/]\n")

# Зоны вариантов задачи (строка `zones` задачи; `None` — зоны не заданы).
ZONES = {
    "frontend": "frontend/src/App.jsx",
    "backend": "backend/app.py",
    "both": "backend/app.py, frontend/src/App.jsx",
    "outside": "docs/notes.md",
    "none": None,
}
REFUSAL_VARIANTS = ("both", "outside", "none")

NOT_SET = ("зоны задачи не заданы — компонент задачи на записи из нескольких "
           "компонентов не выбран")
NOT_TOUCHED = "зоны задачи не задевают ни одного компонента записи"
SEVERAL = re.compile(r"задача затрагивает несколько компонентов \(([^)]*)\) — "
                     r"дели задачу по компонентам \(решение Оператора 20\.10\)")


def component_block(name: str, fields: dict, extra: str = "") -> str:
    lines = [f"      {name}:\n"]
    lines += [f"        {key}: {value}\n" for key, value in fields.items()]
    return "".join(lines) + extra


def training_entry(name: str, *, backend: dict | None = None,
                   frontend: dict | None = None) -> str:
    """Запись учебного проекта; `backend`/`frontend` — поля компонентов
    (по умолчанию — поля учебного проекта)."""
    return (ENTRY_HEAD.format(name=name) + "    components:\n"
            + component_block("backend", backend or BACKEND_FIELDS)
            + component_block("frontend", frontend or FRONTEND_FIELDS,
                              FRONTEND_DEPENDS))


def single_entry(name: str, comp: str, fields: dict) -> str:
    """Запись из одного компонента `comp` с полями `fields`."""
    return (ENTRY_HEAD.format(name=name) + "    components:\n"
            + component_block(comp, fields))


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def check_variant_text(test, text: str, variant: str, where: str) -> None:
    """Текст исхода места несёт отказ AC-3 своего варианта зон."""
    text = text or ""
    if variant == "none":
        test.assertIn(NOT_SET, text, f"{where}: вариант «зоны не заданы»:\n{text}")
    elif variant == "outside":
        test.assertIn(NOT_TOUCHED, text,
                      f"{where}: вариант «зоны вне компонентов»:\n{text}")
    else:
        match = SEVERAL.search(text)
        test.assertIsNotNone(match, f"{where}: вариант «зоны в обоих "
                                    f"компонентах»:\n{text}")
        test.assertIn("backend", match.group(1), f"{where}: {text}")
        test.assertIn("frontend", match.group(1), f"{where}: {text}")


def outcome_text(fn, *args, **kwargs) -> tuple:
    """(возвращённое значение, текст исхода): вывод stdout/stderr, текст
    `SystemExit` и исключения, `repr` возвращённого значения — исход места
    любой формы читается одним текстом."""
    buf = io.StringIO()
    value = None
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            value = fn(*args, **kwargs)
        except SystemExit as exc:
            buf.write(f"\nSystemExit: {exc.code}")
            value = exc
        except Exception as exc:  # noqa: BLE001 — исход места любой формы
            buf.write(f"\n{type(exc).__name__}: {exc}")
            value = exc
    return value, f"{buf.getvalue()}\n{value!r}\n{_detail_of(value)}"


def _detail_of(value) -> str:
    parts = []
    for attr in ("action", "detail", "hint", "refusal"):
        item = getattr(value, attr, None)
        if isinstance(item, str):
            parts.append(item)
    if isinstance(value, (tuple, list)):
        parts += [str(v) for v in value]
    return "\n".join(parts)


class TrainingSandbox(TaskIdSchemaConnTmpRootTest):
    """`targets.yaml` песочницы — артель и учебный проект; клон проекта —
    настоящий git без `origin`; задачи — строки БД с зонами варианта."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.project = f"uch{''.join(self.rng.choice('abcdefghkmnp') for _ in range(5))}"
        self.append_entry(training_entry(self.project))
        self.clone = make_project_repo(self.project, origin=False)

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def append_entry(self, text: str) -> None:
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + text,
                                  encoding="utf-8")

    def task(self, variant: str, state: str = "in_dev", *, target=None,
             canary: bool = False) -> SimpleNamespace:
        """Задача варианта зон `variant` в состоянии `state`."""
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-uch"
        target = target or self.project
        store.insert_task(self.conn, tid, f"Задача {variant}", state, branch,
                          target, 25.0, is_canary=canary)
        zones = ZONES.get(variant)
        if zones is not None:
            store.update_task(self.conn, tid, zones=zones)
        return SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                               target=target, variant=variant,
                               row=store.get_task(self.conn, tid))

    def row(self, t):
        return store.get_task(self.conn, t.id)

    def journal(self, t) -> list:
        return [(r["action"], r["detail"] or "") for r in self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (t.id,))]

    def journal_text(self, t) -> str:
        return "\n".join(f"{a}: {d}" for a, d in self.journal(t))

    def details(self, t, action: str) -> list:
        return [d for a, d in self.journal(t) if a == action]

    def profile_of(self, comp: str):
        """Профиль компонента учебного проекта (для сверки областей)."""
        (profile,) = project_profile.component_profiles(self.project, (comp,))
        return profile


def patch_all(*patchers):
    """Стек подмен одним менеджером."""
    stack = contextlib.ExitStack()
    for patcher in patchers:
        stack.enter_context(patcher)
    return stack


@contextlib.contextmanager
def yielding(value):
    yield value


def fake_tree(root: Path):
    """Дерево прогона `appendix_tree.suite_tree` без приложений PLAN."""
    return SimpleNamespace(root=root, refusal="", fixable=False, note="",
                           warning="", mark=lambda text, *a, **k: text)


def sqlite_conn(conn) -> bool:
    return isinstance(conn, sqlite3.Connection)


__all__ = ["mock"]
