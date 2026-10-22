"""Общий код планки: стороны сравнения файлов зоны, группы подслучаев, прогоны.

База — `_pult.DIFF_BASE` (точка расхождения ветки задачи с `origin`), голова —
файлы рабочей копии кода (`_pult.CODE_ROOT`). Учёт утверждений —
`guard.test_assertions` с модулями `tests/` той же стороны.

Наблюдение «какой подслучай исполняет метод»: методы-кандидаты (методы со
старыми именами и все тестовые методы файла, которых нет на базе) гоняются
из свежей копии модуля головы, а помощники, через которые подслучай
проходит дословно перенесённым телом, подменяются записывающими заглушками:
`places`/`calls_of`/`context` (profile_callers), `scenario`/`check_home`/
`wrapper_records` (pytest_own_places), `new_task`/`spec`/`enter_audit`/
`assert_depth` (test_ac9), `fail_gate`/`cli`/`live_sha` (test_ac20),
`developer_advance` (outcome_gate). Заглушка `developer_advance` после записи
прерывает метод — один вызов на подслучай; цикл подслучаев под `subTest`
дал бы несколько записей.
"""
import ast
import collections
import functools
import itertools
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, artifact_text  # noqa: E402

ROOT = Path(CODE_ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests  # noqa: E402,F401  — пакет для копий модулей
from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402

PROFILE = "tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py"
OUTCOME = "tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py"
AUDIT = "tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py"
OWN = "tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py"
ZONE = (PROFILE, OUTCOME, AUDIT, OWN)
SANDBOX = "tests/sandbox.py"

EXT_KIND = "pult-pytest внешнего проекта"
ARTEL_KIND = "артель"
P_EXT = "PultUnchangedTest::test_ac10_external_pult_pytest_unchanged"
P_ARTEL = "PultUnchangedTest::test_ac10_artel_unchanged"
O_GIT = "Ac4PrepareTest::test_ac4_git_preparation_failures_refuse"
O_SIDE = "Ac4PrepareTest::test_ac4_side_not_started_or_timeout_refuses_naming_side"
O_PREP = "Ac7RerunPrepareTest::test_ac7_rerun_preparation_refusals"
O_RED = "Ac7RerunPrepareTest::test_ac7_branch_rerun_red_kinds"
O_VERDICT = "Ac8VerdictByRecordTest::test_ac8_broken_unstable_and_flaky_on_base"
O_MANDATE = "Ac11MandateTest::test_ac11_file_and_prefix_mandate_cover_findings"
A_SIGNAL = "SignalDepthTest::test_ac9_each_signal_alone_switches_to_full_review"
A_FAIL = "AcceptAuditFailTest::test_ac20_fail_verdict_needs_flag_in_both_forms"
W_FRESH = "PytestOwnEnvironmentTest::test_ac3_home_fresh_and_removed_after_completion"
W_REMOVED = "PytestOwnEnvironmentTest::test_ac3_home_removed_after_timeout_and_exception"
W_CHILD = "PytestOwnProcessGroupTest::test_ac6_child_gone_after_timeout_and_exception"

SPLIT = {
    PROFILE: (P_EXT, P_ARTEL),
    OUTCOME: (O_GIT, O_SIDE, O_PREP, O_RED, O_VERDICT, O_MANDATE),
    AUDIT: (A_SIGNAL, A_FAIL),
    OWN: (W_FRESH, W_REMOVED, W_CHILD),
}
ALL_SPLIT = [(rel, name) for rel, names in SPLIT.items() for name in names]
# Число подслучаев методов outcome_gate по перечню «Контекст» SPEC.
OUTCOME_SUBCASES = {O_GIT: 4, O_SIDE: 4, O_PREP: 5, O_RED: 5, O_VERDICT: 3,
                    O_MANDATE: 4}
AC9_FIXED = ("ADR в ТЗ", "бюджет 44", "бюджет 45", "защищённый путь",
             "мандат в ANSWER", "приложение PLAN")
AC9_FIRST = "ADR в ТЗ"
TESTS_DIR_CLASSES = 13
EXTRA_PLACE = "новое место планки"
EXTRA_CATEGORY = "новая_категория_планки"
SHORT_LIMIT, AC20_LIMIT = 10.0, 20.0
FREE_LOAD = 4.0
SEP = guard.TEST_NAME_SEP


# ------------------------------------------------------------ стороны

@functools.lru_cache(maxsize=None)
def base_text(rel: str):
    res = subprocess.run(["git", "-C", str(ROOT), "show", f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True, encoding="utf-8")
    return res.stdout if res.returncode == 0 else None


def head_text(rel: str):
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.is_file() else None


def modules(side: str) -> guard.TestModules:
    load = base_text if side == "base" else head_text
    return guard.TestModules(load)


def assertions(rel: str, side: str) -> dict:
    text = base_text(rel) if side == "base" else head_text(rel)
    return guard.test_assertions(text, rel, modules(side)) or {}


def qualified(text: str) -> dict:
    return guard._collect_qualified_test_functions(ast.parse(text))


def class_defs(text: str) -> dict:
    return {n.name: n for n in ast.parse(text).body if isinstance(n, ast.ClassDef)}


def new_names(rel: str) -> list:
    return sorted(set(qualified(head_text(rel))) - set(qualified(base_text(rel))))


def candidates(rel: str) -> list:
    """Методы со старыми именами и все тестовые методы файла, которых нет на базе."""
    return sorted(set(SPLIT[rel]) | set(new_names(rel)))


def docstring(node) -> str:
    return ast.get_docstring(node) or ""


def norm(text: str) -> str:
    return " ".join(text.split())


def shares(full, k: int) -> list:
    ordered = sorted(full)
    return [ordered[i::k] for i in range(k)]


def load_now() -> float:
    return os.getloadavg()[0]


# ------------------------------------------------------------ прогоны

_COUNTER = itertools.count()


def load_module(rel: str, text: str):
    """Свежая копия модуля `rel` из текста `text` в пакете `tests`."""
    name = f"tests._plank_{Path(rel).stem}_{next(_COUNTER)}"
    mod = types.ModuleType(name)
    mod.__file__ = str(ROOT / rel)
    mod.__package__ = "tests"
    sys.modules[name] = mod
    exec(compile(text, str(ROOT / rel), "exec"), mod.__dict__)
    return mod


class Run:
    def __init__(self, records, duration, problems):
        self.records = records
        self.duration = duration
        self.problems = problems


def run_methods(mod, names, make_stubs=None) -> dict:
    """{имя: Run} — каждый метод своим экземпляром класса копии модуля."""
    out = {}
    for q in names:
        cls_name, meth = q.split(SEP)
        cls = getattr(mod, cls_name)
        records: list = []
        with ExitStack() as stack:
            for attr, fn in (make_stubs(mod, cls, records) if make_stubs else {}).items():
                stack.enter_context(mock.patch.object(cls, attr, fn, create=True))
            test = cls(meth)
            result = unittest.TestResult()
            start = time.monotonic()
            test.run(result)
            duration = time.monotonic() - start
        problems = [text for _t, text in result.errors + result.failures]
        out[q] = Run(records, duration, problems)
    return out


class _Stop(Exception):
    """Заглушка `developer_advance` прерывает подслучай после записи."""


class _Probe:
    def children_gone(self):
        return True

    def records(self, name):
        return []


def _profile_stubs(mod, cls, records):
    orig_places = getattr(cls, "places")

    def places(self):
        items = list(orig_places(self)) + [(EXTRA_PLACE, None, False, None)]
        return [(item[0], (lambda: ("T", "", [])), *item[2:]) for item in items]

    def calls_of(self, label, run):
        records.append(("place", label))
        return []

    def context(self, *args, **kwargs):
        return ""

    return {"places": places, "calls_of": calls_of, "context": context}


def _own_stubs(mod, cls, records):
    def scenario(self, place, mode):
        records.append(("scenario", place, mode))
        return {"probe": _Probe(), "result": None, "error": None,
                "pult_env": {}, "leak": {}}

    def check_home(self, place, run, outcome):
        records.append(("home", place))

    def wrapper_records(self, place, run):
        return []

    return {"scenario": scenario, "check_home": check_home,
            "wrapper_records": wrapper_records}


def _audit_stubs(mod, cls, records):
    flag = mod.FLAG

    def new_task(self, tz=""):
        return "T"

    def nothing(self, *args, **kwargs):
        return ""

    def assert_depth(self, task, full, names, case):
        records.append(("depth", case))
        return ""

    def fail_gate(self):
        records.append(("fail_gate",))
        return "T"

    def cli(self, *argv):
        records.append(("cli", *argv))
        return f"{flag} не совпадает"

    def live_sha(self, task):
        records.append(("live_sha",))
        return "abc123"

    return {"new_task": new_task, "add_answer": nothing, "spec": nothing,
            "enter_audit": nothing, "assert_depth": assert_depth,
            "fail_gate": fail_gate, "cli": cli, "live_sha": live_sha,
            "state": lambda self, task: "spec_gate",
            "max_step_id": lambda self, task: 0,
            "journal": lambda self, task: "",
            "text_since": lambda self, task, start: ""}


def _outcome_stubs(mod, cls, records):
    def developer_advance(self, *args, **kwargs):
        records.append(("advance",))
        raise _Stop()

    return {"developer_advance": developer_advance}


def own_text_with_extra_place() -> str:
    """Текст головы pytest_own_places с лишним элементом в конце `PLACES`."""
    text = head_text(OWN)
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "PLACES" for t in n.targets))
    lines = text.splitlines(keepends=True)
    offset = sum(len(line.encode("utf-8")) for line in lines[:node.value.end_lineno - 1])
    raw = text.encode("utf-8")
    end = offset + node.value.end_col_offset - 1  # перед закрывающей скобкой
    return (raw[:end] + f', "{EXTRA_PLACE}"'.encode("utf-8") + raw[end:]).decode("utf-8")


def signal_constant_name() -> str:
    for name in dir(config):
        value = getattr(config, name)
        if isinstance(value, dict) and len(value) >= 4 and all(
                isinstance(v, (list, tuple, frozenset, set)) and v
                for v in value.values()):
            paths = {p for v in value.values() for p in v if isinstance(p, str)}
            if {"orchestrator/advance_gates/", "gates.yaml"} <= paths:
                return name
    raise AssertionError("константа путей-признаков в config не найдена")


@functools.lru_cache(maxsize=None)
def fake_runs(rel: str, chunk: int = 0, chunks: int = 1) -> dict:
    """Прогон кандидатов файла `rel` с записывающими заглушками (кэш)."""
    names = candidates(rel)[chunk::chunks]
    if rel == PROFILE:
        return run_methods(load_module(rel, head_text(rel)), names, _profile_stubs)
    if rel == OWN:
        return run_methods(load_module(rel, own_text_with_extra_place()), names,
                           _own_stubs)
    if rel == AUDIT:
        const = getattr(config, signal_constant_name())
        with mock.patch.dict(const, {EXTRA_CATEGORY: ("plank_extra/",)}):
            return run_methods(load_module(rel, head_text(rel)), names, _audit_stubs)
    return run_methods(load_module(rel, head_text(rel)), names, _outcome_stubs)


@functools.lru_cache(maxsize=None)
def real_runs(rel: str, chunk: int, chunks: int) -> dict:
    names = candidates(rel)[chunk::chunks]
    return run_methods(load_module(rel, head_text(rel)), names)


def recorded(runs: dict, kind: str) -> dict:
    return {name: [r[1:] for r in run.records if r[0] == kind]
            for name, run in runs.items()}


def describe(runs: dict) -> str:
    return "\n".join(f"{name}: {run.records}" for name, run in sorted(runs.items()))


# ------------------------------------------------------------ группы

def profile_places() -> list:
    """Метки перечня `places` базы (без заглушечного лишнего места): место,
    потерянное перечнем головы, не исполнит ни один метод."""
    return profile_places_of(base_text(PROFILE))


def profile_places_of(text: str) -> list:
    cls = class_defs(text)["ProfileCallersSandbox"]
    func = next(f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name == "places")
    ret = next(n for n in ast.walk(func) if isinstance(n, ast.Return)
               and isinstance(n.value, ast.List))
    return [elt.elts[0].value for elt in ret.value.elts]


def module_places(text: str) -> list:
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "PLACES" for t in n.targets))
    return list(ast.literal_eval(node.value))


def check_partition(per_method: dict, full: list, old: str, min_k: int) -> list:
    """Нарушения разбиения: метки → методы. `per_method` — {метод: [метки]}."""
    problems = []
    counts = collections.Counter(x for labels in per_method.values() for x in labels)
    for label in full:
        if counts[label] != 1:
            problems.append(f"«{label}» исполняется {counts[label]} раз(а)")
    extra = set(counts) - set(full)
    if extra:
        problems.append(f"посторонние метки: {sorted(extra)}")
    k = len(per_method)
    if k < min_k or k > len(full):
        problems.append(f"число долей {k} вне [{min_k}, {len(full)}]")
        return problems
    expected = {frozenset(s) for s in shares(full, k)}
    got = {frozenset(v) for v in per_method.values()}
    if got != expected:
        problems.append(f"доли не равны перечень[i::{k}] после сортировки: "
                        f"{sorted(map(sorted, got))} != {sorted(map(sorted, expected))}")
    if old is None:
        return problems
    if old not in per_method:
        problems.append(f"{old} не исполняет ни одной метки перечня")
    elif frozenset(per_method[old]) != frozenset(shares(full, k)[0]):
        problems.append(f"{old} исполняет {sorted(per_method[old])}, а не первую "
                        f"долю {shares(full, k)[0]}")
    return problems


def own_groups(runs: dict) -> tuple[dict, list]:
    """{старое имя: {метод: [(место, режим)]}} по записям и неразобранные методы."""
    groups = {W_FRESH: {}, W_REMOVED: {}, W_CHILD: {}}
    stray = []
    for name, run in runs.items():
        pairs = [(r[1], r[2]) for r in run.records if r[0] == "scenario"]
        home = any(r[0] == "home" for r in run.records)
        modes = {m for _p, m in pairs}
        if not pairs:
            stray.append(name)
        elif home and modes == {"pass"}:
            groups[W_FRESH][name] = pairs
        elif home and modes <= {"sleep", "signal"}:
            groups[W_REMOVED][name] = pairs
        elif not home and modes <= {"sleep", "signal"}:
            groups[W_CHILD][name] = pairs
        else:
            stray.append(name)
    return groups, stray


def own_share_problems(group: dict, old: str, modes: tuple, full: list) -> list:
    problems = []
    pairs = collections.Counter(p for v in group.values() for p in v)
    for place in full:
        for mode in modes:
            if pairs[(place, mode)] != 1:
                problems.append(f"({place}, {mode}) исполняется {pairs[(place, mode)]} раз(а)")
    family = {frozenset(p for p, _m in v) for v in group.values()}
    k = len(family)
    if not 2 <= k <= len(full):
        problems.append(f"число долей мест {k} вне [2, {len(full)}]")
        return problems
    expected = {frozenset(s) for s in shares(full, k)}
    if family != expected:
        problems.append(f"доли мест не равны PLACES[i::{k}] после сортировки: "
                        f"{sorted(map(sorted, family))}")
    if old not in group:
        problems.append(f"{old} не в группе своего подслучая")
    elif {p for p, _m in group[old]} != set(shares(full, k)[0]):
        problems.append(f"{old} исполняет места {sorted({p for p, _m in group[old]})}, "
                        f"а не первую долю {shares(full, k)[0]}")
    return problems


def audit_groups(runs: dict) -> tuple[dict, dict, list]:
    """(методы test_ac9 → метки, методы test_ac20 → формы, неразобранные)."""
    signal, fail, stray = {}, {}, []
    for name, run in runs.items():
        depth = [r[1] for r in run.records if r[0] == "depth"]
        gates = [r for r in run.records if r[0] == "fail_gate"]
        if depth and not gates:
            signal[name] = depth
        elif gates and not depth:
            forms = []
            for r in run.records:
                if r[0] == "cli" and len(r) == 5 and r[1] == "approve":
                    forms.append("sha")
                elif r[0] == "cli" and len(r) == 4 and r[1] == "approve":
                    forms.append("short")
            fail[name] = {"gates": len(gates), "forms": sorted(set(forms)),
                          "live_sha": sum(1 for r in run.records if r[0] == "live_sha")}
        else:
            stray.append(name)
    return signal, fail, stray


def category_labels() -> list:
    const = getattr(config, signal_constant_name())
    return [f"путь {c}" for c in list(const) + [EXTRA_CATEGORY]]


def share_methods() -> dict:
    """{старое имя: [методы-доли]} для перечней требования 3 (по записям)."""
    out = {}
    places = recorded(fake_runs(PROFILE), "place")
    for old, kind in ((P_EXT, EXT_KIND), (P_ARTEL, ARTEL_KIND)):
        out[old] = sorted(n for n, labels in places.items()
                          if labels and all(x[0].startswith(kind + ": ") for x in labels))
    groups, _stray = own_groups(fake_runs(OWN))
    for old, group in groups.items():
        out[old] = sorted(group)
    signal, _fail, _stray = audit_groups(fake_runs(AUDIT))
    out[A_SIGNAL] = sorted(n for n, labels in signal.items()
                           if all(x.startswith("путь ") for x in labels))
    return out


# ------------------------------------------------------------ помощники

def helper_assertion_names(text: str) -> tuple[set, set]:
    """(имена методов классов с утверждениями, имена функций модуля с ними)."""
    methods, functions = set(), set()
    for (cls, name), keys in guard._helper_keys(text).items():
        if keys:
            (methods if cls else functions).add(name)
    return methods, functions


def asserting_calls(func, methods: set, functions: set) -> list:
    found = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name) \
                and callee.value.id == "self" and callee.attr in methods:
            found.append(callee.attr)
        elif isinstance(callee, ast.Name) and callee.id in functions:
            found.append(callee.id)
    return found


def helpers_of(text: str) -> dict:
    """{(класс либо None, имя): узел} нетестовых (не `test_*`, правило
    `guard`) функций и методов модуля — `tests_dir` базы среди них."""
    out = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test_"):
            out[(None, node.name)] = node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and not sub.name.startswith("test_"):
                    out[(node.name, sub.name)] = sub
    return out


def base_classes_in_file(text: str) -> set:
    """Классы файла, от которых наследуют другие классы того же файла."""
    names = set(class_defs(text))
    return {(guard._dotted_name(b) or "").rpartition(".")[2]
            for c in class_defs(text).values() for b in c.bases} & names


def inherited_tests(text: str, cls_name: str) -> set:
    """Тестовые методы, которые класс получает от баз своего файла."""
    defs = class_defs(text)
    found, seen = set(), set()

    def visit(name):
        if name in seen or name not in defs:
            return
        seen.add(name)
        for sub in defs[name].body:
            if isinstance(sub, ast.FunctionDef) and sub.name.startswith("test"):
                found.add(sub.name)
        for b in defs[name].bases:
            visit((guard._dotted_name(b) or "").rpartition(".")[2])

    for b in defs[cls_name].bases:
        visit((guard._dotted_name(b) or "").rpartition(".")[2])
    return found


# ------------------------------------------------------------ сбор pytest

def collect(texts: dict) -> list:
    """nodeid тестов, собранных pytest из файлов `texts` во временном пакете."""
    tmp = Path(tempfile.mkdtemp(prefix="plank-collect-"))
    try:
        (tmp / "tests").mkdir()
        shutil.copy(ROOT / "tests" / "__init__.py", tmp / "tests" / "__init__.py")
        shutil.copy(ROOT / SANDBOX, tmp / SANDBOX)
        for rel, text in texts.items():
            (tmp / rel).write_text(text, encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             "-p", "no:cacheprovider", *texts],
            cwd=tmp, env=env, capture_output=True, text=True, encoding="utf-8",
            timeout=110)
        items = [line.strip() for line in res.stdout.splitlines()
                 if "::" in line and not line.startswith(" ")]
        if res.returncode != 0:
            raise AssertionError(f"сбор pytest вернул {res.returncode}:\n"
                                 f"{res.stdout[-3000:]}\n{res.stderr[-3000:]}")
        return items
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def plan_text() -> str:
    return artifact_text("PLAN.md") or ""
