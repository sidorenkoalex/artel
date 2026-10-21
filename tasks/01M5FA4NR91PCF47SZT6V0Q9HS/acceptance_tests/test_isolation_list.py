"""Изоляция классов перечня требования 5 от настоящего реестра живой канарейки: статический разбор признаков (1)–(3) и динамическая сверка признака (2).

Группа: разовый
Красен до реализации: у `CmdCanaryTemplateSelectionTest` (`tests/test_canary_template_flag.py`) и `DoctorFixOrderTest` (`tests/test_doctor_closed_ref_fix.py`) нет ни изолирующей основы, ни подмены `config.ROOT`/`canary._live_dir` в `setUp` — статический разбор не находит у них признака, а после их `setUp` функция реестра получает каталог под настоящим корнем пульта.

Перечень — 119 классов в 61 файле из требования 5 SPEC (копия ниже, в
том же виде строк «- `tests/<файл>.py`: `Класс`, …»). К нему
добавляются: классы, записанные разработчиком в PLAN.md (артефакт задачи
читается помощником пульта `artifact_text`) строками того же вида, и
каждый класс `tests/`, вызывающий `cmd_doctor(fix=True)` (прямой вызов с
`fix=True`, позиционный `cmd_doctor(False, True)`, передача
`cmd_doctor` в обёртку вместе с `fix=True`, вызов метода класса или его
предка, делающего такой вызов).

Статический разбор (модуль `ast`, классы перечня не исполняются): основы
признака (1) — `TmpRootTest` и `RealGitSandbox` из `tests/sandbox.py`,
`FsmTest` из `tests/test_invariants.py`; имена баз разрешаются по
импортам и присваиваниям модуля (с учётом строки определения класса),
по импортам из других файлов `tests/` и по псевдонимам. Корень кода —
`Path(orchestrator.__file__).resolve().parents[1]`, тот же, от которого
AC-20 сверяет пути.
"""
import ast
import importlib
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import orchestrator  # noqa: E402
from _pult import artifact_text  # noqa: E402
from orchestrator import canary  # noqa: E402

ROOT = Path(orchestrator.__file__).resolve().parents[1]
TESTS = ROOT / "tests"

LIST_TEXT = """
- `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`: `BaselineModelsChangeTest`, `CodexRoleOfTheSetTest`, `DefaultRunCloneLayerTest`, `RunSummaryModelsTest`, `SetByRolesTest`
- `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`: `RoleModelsDoctorLinesTest`
- `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`: `CanaryAcceptanceResultTest`
- `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`: `DoctorMainCiLineTest`, `MergeGuardAfterSnapshotTest`, `MergeWaitsForMainCiTest`, `NextMergeRefusedOnRedMainTest`, `RedMergeThenDocCommitTest`
- `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`: `CanaryCodexHomeTest`
- `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`: `CanaryProfileTest`
- `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`: `DoctorStaleCyclesTest`
- `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`: `DropPendingTest`, `HeldRecordBaseTest`, `ImmediatePinCheckTest`, `LegacyRecordTest`, `MatchingBaseSendTest`, `NewFileBaseTest`, `PendingListTest`, `RoleRefusalTest`, `StaleBaseRefusalTest`
- `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`: `AdmitShortfallTest`, `AdmitWriteTest`, `CleanRunTest`
- `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`: `DoctorSetProvidersTest`
- `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`: `PultWritesAfterRoleMoveTest`
- `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`: `CloneCreationTest`, `CloneHooksFromPinTest`, `EndToEndMainCopyUntouchedTest`, `HeldRecordBaseFromCloneTest`, `MergeGateStepsOnCloneTest`, `OperatorCommandsThroughCloneTest`
- `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`: `AlreadyAppliedAppendixTest`
- `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`: `MergeGateDoneDependenciesTest`
- `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`: `ArtelFullSuiteClassesTest`, `ExternalAppendixTest`, `GeneratorMapTest`, `NoGeneratorMapTest`, `ProfileSuiteTest`, `ProtectedDiffTest`
- `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`: `MergeGateUnchangedTest`
- `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`: `PredicateGitTest`
- `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`: `ProfileLimitCutsGateRunTest`
- `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`: `DoctorLimitLineTest`
- `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`: `DoctorDurationTest`
- `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`: `CanaryDoctorTest`
- `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`: `CanaryLifecycleTest`
- `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`: `AutogateSkipTest`, `CanaryCloneSkipTest`
- `tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py`: `HookAndDocumentationTest`
- `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`: `WatchContractTest`
- `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`: `DoctorWorktreeDbTest`
- `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`: `OriginSweepTest`
- `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`: `MergeGateAlreadyInBaseTest`
- `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`: `PostMergeMapInterpreterTest`
- `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`: `NotesNearLimitTest`
- `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`: `ArtelMergeTest`, `ClosingFailureTest`, `ExternalMergeTest`
- `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`: `DoctorQuietTest`, `DoctorTamperTest`
- `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`: `NoteMergeGateTest`
- `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py`: `KnowledgeCommitTest`
- `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`: `ArtelCodeMergeTest`, `ArtelMergeTest`
- `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`: `MergeGateTest`, `PultUnchangedTest`
- `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`: `ProjectDoctorTest`
- `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py`: `NoteWindowProjectTest`
- `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`: `SilenceWindowAllRowsTest`
- `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`: `EarlySignalCanaryTest`
- `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`: `DoctorOnComponentRecordsTest`, `PathsSourceTest`, `TestProfileRecordsUnchangedTest`, `ToolVersionTest`, `WorkdirTest`
- `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`: `CanaryRegistryTest`
- `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`: `CanaryWindowTest`
- `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`: `Ac14OutOfBoundsTest`, `Ac4ProofTest`, `Ac5ProofMismatchTest`, `Ac6LegacyRecordTest`, `Ac7MergeBaseTest`
- `tests/test_canary_live_registry_units.py`: `LiveRunsSweepTest`
- `tests/test_canary_template_flag.py`: `CmdCanaryTemplateSelectionTest`
- `tests/test_doc_commit.py`: `DocCommitPushTest`, `DocCommitRefusalTest`, `PinBaseCheckTest`, `SilenceWindowAndFlushTest`
- `tests/test_doc_commit_held_base.py`: `NetworkHoldBaseTest`
- `tests/test_doc_commit_suite_gate.py`: `AcceptRedOnDocsPathTest`, `AcceptRedTest`, `GateRefusalLeavesNoDirtTest`, `HeldConfigRecordFlushTest`, `RedSuiteTest`, `SuiteTreeTest`
- `tests/test_doctor.py`: `DoctorCommandTest`
- `tests/test_doctor_canary_pool.py`: `CanaryPoolDriftCheckTest`
- `tests/test_doctor_closed_ref_fix.py`: `DoctorFixOrderTest`
- `tests/test_fsm_merge_gate_done_snapshot.py`: `DonePathSnapshotTest`
- `tests/test_git_hooks.py`: `FixGitHooksTest`
- `tests/test_invariants.py`: `MainCopyGitUnchangedDuringTaskTest`, `ManualGatesNeedTheOperatorTest`, `MergeNeedsGreenCiTest`, `MergeOnlyFromMergeGateTest`
- `tests/test_merge_gate_ci_wait.py`: `MovedMainRetryInCycleTest`
- `tests/test_notes.py`: `CmdNoteArgumentValidationTest`, `SilenceWindowReasonTest`, `WindowBypassAndNoWindowTest`, `WindowHoldsValidNoteTest`
- `tests/test_notes_apply.py`: `ApplyRefusalTest`, `ApplySilenceWindowTest`, `ApplySuccessTest`
- `tests/test_notes_row_format.py`: `StateFlagAliasTest`
- `tests/test_plan_appendix.py`: `MergeAppendixTest`
- `tests/test_providers.py`: `AllChecksProviderNamesTest`
"""

#: Классы, которые требование 5 называет по имени (изолированы признаком (2)).
DYNAMIC_REQUIRED = {
    ("tests/test_canary_template_flag.py", "CmdCanaryTemplateSelectionTest"),
    ("tests/test_doctor_canary_pool.py", "CanaryPoolDriftCheckTest"),
    ("tests/test_doctor_closed_ref_fix.py", "DoctorFixOrderTest"),
}
#: Долгоживущие файлы планки этой задачи: их классы сверяются на признак
#: изоляции наравне с перечнем, но записи в отчёте не требуют — они и есть
#: тесты задачи.
OWN_PREFIX = "tests/test_01m5fa4nr91pcf47szt6v0q9hs_"
FIX_CALLERS_NAMED = {"DoctorFixOrderTest", "FixGitHooksTest", "PultWritesAfterRoleMoveTest"}
BASES = {("tests/sandbox.py", "TmpRootTest"): "TmpRootTest",
         ("tests/sandbox.py", "RealGitSandbox"): "RealGitSandbox",
         ("tests/test_invariants.py", "FsmTest"): "FsmTest"}
CONDITIONAL_BASES = {"TmpRootTest", "RealGitSandbox"}


def parse_list(text: str) -> set:
    """{(путь файла, класс)} из строк вида «- `tests/<файл>.py`: `A`, `B`»."""
    pairs = set()
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("- `tests/") or "`:" not in line:
            continue
        head, tail = line[2:].split("`:", 1)
        rel = head.strip("` ")
        for part in tail.split(","):
            name = part.strip().strip("`").strip()
            if name.isidentifier():
                pairs.add((rel, name))
    return pairs


# ---------------------------------------------------------------- модули

class Module:
    """Разобранный файл `tests/`: классы и привязки имён верхнего уровня по строкам."""

    def __init__(self, rel: str):
        self.rel = rel
        self.tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)
        self.classes = {}
        self.bindings = {}
        self._collect(self.tree.body)

    def _bind(self, name: str, lineno: int, kind: str, payload) -> None:
        self.bindings.setdefault(name, []).append((lineno, kind, payload))

    def _collect(self, body) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                self.classes.setdefault(node.name, node)
                self._bind(node.name, node.lineno, "class", node)
            elif isinstance(node, ast.ImportFrom):
                module = ("." * node.level) + (node.module or "")
                for alias in node.names:
                    self._bind(alias.asname or alias.name, node.lineno, "from",
                               (module, alias.name))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        self._bind(alias.asname, node.lineno, "module", alias.name)
                    else:
                        top = alias.name.split(".")[0]
                        self._bind(top, node.lineno, "module", top)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(
                            node.value, (ast.Name, ast.Attribute)):
                        self._bind(target.id, node.lineno, "expr", node.value)
            elif isinstance(node, (ast.If, ast.Try)):
                self._collect(node.body)
                for handler in getattr(node, "handlers", []):
                    self._collect(handler.body)
                self._collect(node.orelse)
                self._collect(getattr(node, "finalbody", []))

    def binding(self, name: str, before):
        options = self.bindings.get(name, [])
        if before is not None:
            earlier = [b for b in options if b[0] < before]
            if earlier:
                return earlier[-1]
        return options[-1] if options else None


_MODULES = {}


def module(rel: str):
    if rel not in _MODULES:
        _MODULES[rel] = Module(rel) if (ROOT / rel).is_file() else None
    return _MODULES[rel]


def module_file(name: str):
    """Путь файла `tests/` по имени модуля импорта; `None` — не файл `tests/`."""
    bare = name.lstrip(".")
    if not bare:
        return None
    parts = bare.split(".")
    if parts[0] == "tests":
        parts = parts[1:]
    if not parts:
        return None
    rel = "tests/" + "/".join(parts) + ".py"
    return rel if (ROOT / rel).is_file() else None


def resolve_name(rel: str, name: str, before=None, local=None, depth=0):
    """("base", имя) | ("class", rel, ClassDef) | None — во что разрешается имя модуля."""
    if depth > 30:
        return None
    if local and name in local:
        kind, payload = local[name]
        return _follow(rel, kind, payload, depth)
    mod = module(rel)
    if mod is None:
        return None
    found = mod.binding(name, before)
    if found is None:
        return None
    lineno, kind, payload = found
    if kind == "class":
        if (rel, name) in BASES:
            return ("base", BASES[(rel, name)])
        return ("class", rel, payload)
    if kind == "expr":
        return resolve_expr(rel, payload, lineno, local, depth + 1)
    return _follow(rel, kind, payload, depth)


def _follow(rel, kind, payload, depth):
    if kind == "from":
        source, name = payload
        target = module_file(source)
        if target is None:
            return ("module", module_file(f"{source}.{name}")) if module_file(
                f"{source}.{name}") else None
        return resolve_name(target, name, None, None, depth + 1)
    if kind == "module":
        target = module_file(payload)
        return ("module", target) if target else None
    if kind == "class":
        return ("class", rel, payload)
    return None


def resolve_expr(rel: str, expr, before=None, local=None, depth=0):
    if isinstance(expr, ast.Name):
        return resolve_name(rel, expr.id, before, local, depth + 1)
    if isinstance(expr, ast.Attribute):
        owner = resolve_expr(rel, expr.value, before, local, depth + 1)
        if owner and owner[0] == "module":
            return resolve_name(owner[1], expr.attr, None, None, depth + 1)
    return None


def local_imports(func) -> dict:
    """Импорты и определения классов в теле функции: имя → привязка."""
    local = {}
    for node in ast.walk(func):
        if isinstance(node, ast.ImportFrom):
            module_name = ("." * node.level) + (node.module or "")
            for alias in node.names:
                local[alias.asname or alias.name] = ("from", (module_name, alias.name))
        elif isinstance(node, ast.ClassDef) and node is not func:
            local[node.name] = ("class", node)
    return local


# --------------------------------------------------------------- признаки

def _has_super_setup(func) -> bool:
    for node in ast.walk(func):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setUp"):
            value = node.func.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) \
                    and value.func.id == "super":
                return True
            if isinstance(value, (ast.Name, ast.Attribute)) and node.args:
                return True
    return False


def chain_defects(chain: list) -> list:
    """Сужения `PATCHED_ATTRS` без `ROOT` и `setUp` без `super().setUp()` в цепочке."""
    defects = []
    for rel, cdef in chain:
        for node in cdef.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "PATCHED_ATTRS" for t in node.targets):
                value = node.value
                if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
                    names = {e.value for e in value.elts if isinstance(e, ast.Constant)}
                    if "ROOT" not in names:
                        defects.append(f"{rel}::{cdef.name}: PATCHED_ATTRS без ROOT")
                elif not (isinstance(value, ast.Name) and value.id == "ALL_CONFIG_ATTRS"):
                    defects.append(f"{rel}::{cdef.name}: PATCHED_ATTRS не литерал")
            if isinstance(node, ast.FunctionDef) and node.name == "setUp" \
                    and not _has_super_setup(node):
                defects.append(f"{rel}::{cdef.name}: setUp без super().setUp()")
    return defects


def base_chains(rel: str, cdef, local=None, seen=None):
    """Пары (основа, цепочка от класса до основы без неё) по всем путям наследования."""
    seen = set() if seen is None else seen
    key = (rel, cdef.name, cdef.lineno)
    if key in seen:
        return []
    seen = seen | {key}
    found = []
    for base in cdef.bases:
        target = resolve_expr(rel, base, cdef.lineno if local is None else None, local)
        if target is None:
            continue
        if target[0] == "base":
            found.append((target[1], [(rel, cdef)]))
        elif target[0] == "class":
            _kind, base_rel, base_def = target
            for name, chain in base_chains(base_rel, base_def, None, seen):
                found.append((name, [(rel, cdef), *chain]))
    return found


def sign1(rel: str, cdef, local=None) -> tuple:
    """(признак (1) есть, пояснение)."""
    notes = []
    for base, chain in base_chains(rel, cdef, local):
        if base not in CONDITIONAL_BASES:
            return True, base
        defects = chain_defects(chain)
        if not defects:
            return True, base
        notes.append(f"основа {base} не засчитана: {'; '.join(defects)}")
    return False, "; ".join(notes) or "изолирующей основы в цепочке нет"


def _setups(rel: str, cdef) -> list:
    """`setUp` класса и его предков из `tests/` до первой основы."""
    found = []
    stack, seen = [(rel, cdef)], set()
    while stack:
        cur_rel, cur = stack.pop()
        if (cur_rel, cur.name) in seen:
            continue
        seen.add((cur_rel, cur.name))
        found += [n for n in cur.body if isinstance(n, ast.FunctionDef) and n.name == "setUp"]
        for base in cur.bases:
            target = resolve_expr(cur_rel, base, cur.lineno)
            if target and target[0] == "class":
                stack.append((target[1], target[2]))
    return found


def _names_of(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _patches_registry(func) -> bool:
    pairs = {("canary", "_live_dir"), ("config", "ROOT")}
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            consts = [a.value for a in node.args if isinstance(a, ast.Constant)
                      and isinstance(a.value, str)]
            owners = [_names_of(a) for a in node.args]
            if any((o, c) in pairs for o in owners for c in consts):
                return True
            if any(c.endswith(".canary._live_dir") or c.endswith(".config.ROOT")
                   for c in consts):
                return True
        if isinstance(node, (ast.Tuple, ast.List)):
            elts = node.elts
            for left, right in zip(elts, elts[1:]):
                if isinstance(right, ast.Constant) and (_names_of(left), right.value) in pairs:
                    return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and (
                        _names_of(target.value), target.attr) in pairs:
                    return True
    return False


def sign2(rel: str, cdef) -> bool:
    return any(_patches_registry(f) for f in _setups(rel, cdef))


def _test_methods(cdef) -> list:
    return [n for n in cdef.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("test")]


def _contains_call(node) -> bool:
    return any(isinstance(n, ast.Call) for n in ast.walk(node))


def method_sign3(rel: str, func) -> tuple:
    local = local_imports(func)
    local_classes = {}
    instances = {}
    for index, stmt in enumerate(func.body):
        if index == 0 and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue
        if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.Pass)):
            continue
        if isinstance(stmt, ast.ClassDef):
            local_classes[stmt.name] = stmt
            continue
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call) \
                and isinstance(stmt.value.func, ast.Name) \
                and stmt.value.func.id in local_classes \
                and not any(_contains_call(a) for a in stmt.value.args):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    instances[target.id] = local_classes[stmt.value.func.id]
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) \
                and isinstance(stmt.value.func, ast.Attribute) \
                and stmt.value.func.attr == "setUp" \
                and isinstance(stmt.value.func.value, ast.Name) \
                and stmt.value.func.value.id in instances:
            ok, why = sign1(rel, instances[stmt.value.func.value.id], local)
            return ok, (f"{func.name}: вложенная песочница — {why}")
        if _contains_call(stmt):
            return False, f"{func.name}: вызов до setUp вложенной песочницы (строка {stmt.lineno})"
    return False, f"{func.name}: нет setUp вложенной песочницы"


def sign3(rel: str, cdef) -> tuple:
    methods = _test_methods(cdef)
    if not methods:
        return False, "тестовых методов нет"
    notes = []
    for func in methods:
        ok, why = method_sign3(rel, func)
        if not ok:
            return False, why
        notes.append(why)
    return True, "; ".join(notes)


# ---------------------------------------------------------- cmd_doctor(fix)

def _is_fix_call(node) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fix_kw = any(k.arg == "fix" and isinstance(k.value, ast.Constant) and k.value.value is True
                 for k in node.keywords)
    if _names_of(node.func) == "cmd_doctor":
        return fix_kw or (len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                          and node.args[1].value is True)
    return fix_kw and any(_names_of(a) == "cmd_doctor" for a in node.args)


def _calls_fix(func, fix_methods: set) -> bool:
    for node in ast.walk(func):
        if _is_fix_call(node):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "self" \
                and node.func.attr in fix_methods:
            return True
    return False


def fix_methods_of(rel: str, cdef, memo: dict) -> set:
    key = (rel, cdef.name, cdef.lineno)
    if key in memo:
        return memo[key]
    memo[key] = set()
    inherited = set()
    for base in cdef.bases:
        target = resolve_expr(rel, base, cdef.lineno)
        if target and target[0] == "class":
            inherited |= fix_methods_of(target[1], target[2], memo)
    own = set()
    funcs = [n for n in cdef.body if isinstance(n, ast.FunctionDef)]
    changed = True
    while changed:
        changed = False
        for func in funcs:
            if func.name not in own and _calls_fix(func, inherited | own):
                own.add(func.name)
                changed = True
    memo[key] = inherited | own
    return memo[key]


def fix_callers() -> set:
    memo, found = {}, set()
    for path in sorted(TESTS.glob("test_*.py")):
        rel = f"tests/{path.name}"
        mod = module(rel)
        for name, cdef in mod.classes.items():
            if not _test_methods(cdef):
                continue
            methods = fix_methods_of(rel, cdef, memo)
            if any(m.name in methods for m in _test_methods(cdef)) or any(
                    _calls_fix(f, methods) for f in cdef.body
                    if isinstance(f, ast.FunctionDef)):
                found.add((rel, name))
    return found


def plan_text() -> str:
    return artifact_text("PLAN.md") or ""


def checked_classes() -> set:
    return parse_list(LIST_TEXT) | parse_list(plan_text()) | fix_callers()


# ------------------------------------------------------------------ тесты

class IsolationListTest(unittest.TestCase):
    """Перечень требования 5 против исходных текстов `tests/` рабочей копии."""

    def test_ac19_every_listed_class_has_an_isolation_sign(self):
        """Каждый класс перечня (и добавленный PLAN.md, и каждый вызывающий `cmd_doctor(fix=True)`) имеет признак (1), (2) или (3).

        Разбор `ast` без исполнения классов: признак (1) — цепочка баз до
        `TmpRootTest`/`RealGitSandbox` без сужения `PATCHED_ATTRS` без `ROOT`
        и без `setUp` без `super().setUp()` либо до `FsmTest`; (2) — `setUp`
        класса (или его предка из `tests/`) подменяет `config.ROOT` или
        `canary._live_dir`; (3) — в каждом тестовом методе до `setUp`
        экземпляра вложенного подкласса основы нет иных вызовов, кроме
        создания экземпляра. Провал называет каждый класс без признака и
        причину по каждому признаку.

        Ловит мутацию: `DoctorFixOrderTest` или `CmdCanaryTemplateSelectionTest`
        оставлены без подмены каталога реестра в `setUp` (класс без признака
        назван в провале), либо в цепочку класса перечня добавлен `setUp`
        без `super().setUp()` — песочница не поднимается, признак (1)
        снимается.
        """
        pairs = checked_classes()
        self.assertGreaterEqual(len(parse_list(LIST_TEXT)), 119)
        failures = []
        for rel, name in sorted(pairs):
            mod = module(rel)
            if mod is None or name not in mod.classes:
                failures.append(f"{rel}::{name}: класс не найден")
                continue
            cdef = mod.classes[name]
            ok1, why1 = sign1(rel, cdef)
            if ok1:
                continue
            if sign2(rel, cdef):
                continue
            ok3, why3 = sign3(rel, cdef)
            if ok3:
                continue
            failures.append(f"{rel}::{name}: (1) {why1}; (2) нет подмены config.ROOT/"
                            f"canary._live_dir в setUp; (3) {why3}")
        self.assertEqual(failures, [], "классы перечня без признака изоляции:\n"
                         + "\n".join(failures))

    def test_ac19_list_contains_every_cmd_doctor_fix_caller(self):
        """Каждый класс `tests/`, вызывающий `cmd_doctor(fix=True)` (в любой из форм вызова), есть в перечне или назван в PLAN.md.

        Наблюдение: найденные разбором классы-вызыватели — подмножество
        перечня SPEC вместе с классами, названными в PLAN.md (классы
        долгоживущих файлов планки этой задачи записи не требуют); среди
        найденных есть `DoctorFixOrderTest`, `FixGitHooksTest` и
        `PultWritesAfterRoleMoveTest`.

        Ловит мутацию: новый тест с `doctor.cmd_doctor(fix=True)` добавлен в
        `tests/` без записи в отчёте — после починки реестра под `--fix` он
        дошёл бы до настоящего реестра, не будучи сверен на изоляцию.
        """
        callers = fix_callers()
        names = {name for _rel, name in callers}
        for name in FIX_CALLERS_NAMED:
            self.assertIn(name, names, f"разбор не нашёл вызов cmd_doctor(fix=True) "
                                       f"у {name}: {sorted(names)}")
        listed = parse_list(LIST_TEXT) | parse_list(plan_text())
        plan = plan_text()
        missing = sorted(f"{rel}::{name}" for rel, name in callers
                         if (rel, name) not in listed and name not in plan
                         and not rel.startswith(OWN_PREFIX))
        self.assertEqual(missing, [], "классы с cmd_doctor(fix=True) вне перечня и "
                                      "без записи в PLAN.md:\n" + "\n".join(missing))

    def test_ac20_sign2_classes_redirect_the_registry_path(self):
        """Для каждого класса с признаком (2) (и обязательно трёх названных): после его `setUp` функция реестра получает каталог вне корня пульта.

        Сценарий: экземпляр класса на его первом тестовом методе, `setUp()`,
        затем `canary.live_run_note()` и `canary.live_runs()` под слежкой за
        обращениями к файловой системе (`Path.is_dir`/`exists`/`glob`/
        `iterdir`, `os.scandir`/`os.listdir`/`os.path.isdir`): каждый путь,
        к которому обратилась функция реестра, сверяется с корнем
        `Path(orchestrator.__file__).resolve().parents[1]`, снятым до
        подмен. Путь под этим корнем обрывает вызов до чтения (настоящий
        реестр не читается и не убирается) и называется в провале; сбой
        `setUp` или функции реестра — провал; ни одного обращения — провал.
        Уборка экземпляра — `doCleanups()`.

        Ловит мутацию: в `setUp` подменён не тот атрибут (например,
        `canary._pool_dir` вместо `canary._live_dir`) или подмена снимается
        до конца `setUp` — функция реестра идёт в `.artel/` настоящего корня.
        """
        targets = set(DYNAMIC_REQUIRED)
        for rel, name in checked_classes():
            mod = module(rel)
            if mod is not None and name in mod.classes and sign2(rel, mod.classes[name]):
                targets.add((rel, name))
        failures = []
        for rel, name in sorted(targets):
            with self.subTest(класс=f"{rel}::{name}"):
                problem = self.probe(rel, name)
                if problem:
                    failures.append(f"{rel}::{name}: {problem}")
        self.assertEqual(failures, [], "\n".join(failures))

    def probe(self, rel: str, name: str):
        module_name = rel[:-3].replace("/", ".")
        try:
            cls = getattr(importlib.import_module(module_name), name)
        except Exception as exc:  # noqa: BLE001 — провал с причиной
            return f"класс не импортируется: {exc!r}"
        methods = sorted(n for n in dir(cls) if n.startswith("test"))
        if not methods:
            return "тестовых методов нет"
        case = cls(methods[0])
        try:
            case.setUp()
        except Exception as exc:  # noqa: BLE001
            case.doCleanups()
            return f"сбой setUp: {exc!r}"
        try:
            seen, problem = self.spy_registry()
        finally:
            case.doCleanups()
        if problem:
            return problem
        under = [p for p in seen if _under_root(p)]
        if under:
            return f"функция реестра обратилась под корень пульта: {under}"
        if not seen:
            return "функция реестра не обратилась ни к одному пути"
        return None

    def spy_registry(self) -> tuple:
        seen = []

        class Reached(BaseException):
            pass

        def record(path):
            text = os.fspath(path)
            seen.append(text)
            if _under_root(text):
                raise Reached(text)

        def wrap(owner, attr):
            real = getattr(owner, attr)

            def spy(target, *args, **kwargs):
                record(target)
                return real(target, *args, **kwargs)
            return owner, attr, real, spy

        wrappers = [wrap(Path, "is_dir"), wrap(Path, "exists"), wrap(Path, "glob"),
                    wrap(Path, "iterdir"), wrap(os, "scandir"), wrap(os, "listdir"),
                    wrap(os.path, "isdir")]
        for owner, attr, _real, spy in wrappers:
            setattr(owner, attr, spy)
        problem = None
        try:
            for func in (canary.live_run_note, canary.live_runs):
                try:
                    func()
                except Reached:
                    break
                except Exception as exc:  # noqa: BLE001
                    problem = f"сбой {func.__name__}: {exc!r}"
                    break
        finally:
            for owner, attr, real, _spy in wrappers:
                setattr(owner, attr, real)
        return seen, problem


def _under_root(text: str) -> bool:
    try:
        path = Path(text).resolve()
    except (OSError, RuntimeError):
        path = Path(os.path.abspath(text))
    return path == ROOT or ROOT in path.parents


if __name__ == "__main__":
    unittest.main()
