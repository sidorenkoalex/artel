"""Общие фикстуры/константы приёмочных тестов задачи
01M1TT9BPBRYMDXXEWVZSRG51V (разрез `orchestrator/doctor.py` на пакет).

Не `test_*.py` — не сканируется guard'ом на AC-маркеры/тест-методы и не
подхватывается `unittest discover`, только импортируется тестами этого
каталога (тот же приём, что `tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/
acceptance_tests/_sandbox.py`).
"""
import ast
import hashlib
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

DOCTOR_PKG_DIR = REPO_ROOT / "orchestrator" / "doctor"

# --- перечень AC-1/AC-10: публичные имена doctor.py + коллаборанты +
# приватные помощники, к которым напрямую обращаются tests/ (снято
# `grep -rho "doctor\.[a-zA-Z_]*" tests/ tasks/*/acceptance_tests/
# orchestrator/ scripts/` 06.09, вручную отфильтровано от фрагментов
# alert-source строк вроде "doctor.recovery"/"doctor.orphans" — те не
# Python-атрибуты, а куски строковых литералов `"doctor.recovery.sha"` и
# т.п., срезанные жадностью регэкспа по первой точке/дефису; ниже — то,
# что реально резолвится как `doctor.<имя>` в коде сегодня).
PUBLIC_FUNC_NAMES = [
    "check_cli_found", "cli_version", "check_cli_version", "check_token",
    "check_git_identity", "check_disk_space", "check_role_home_reference",
    "check_target_layout", "check_target_wrapper", "preflight_checks",
    "isolation_smoke", "live_smoke", "recovery_check", "check_orphans",
    "check_role_log_pool_leak", "check_canary_pool_drift",
    "check_token_repo_scope", "check_branch_freshness", "check_leases",
    "check_merge_lock", "check_hung_test_runs", "check_zone_waits",
    "check_backup_age", "check_task_counters", "check_pending_snapshots",
    "check_remote_empty", "check_base_branch", "check_root_pin",
    "sweep_orphan_artifact_branches", "check_map_growth", "all_checks",
    "cmd_doctor", "cmd_alert_ack",
    # main после 01M1TQ0X14 / 01M1TQ0ZCY (06.09): три новые проверки
    "check_artifact_branch_sync", "check_artifact_branch_ci",
    "check_artifact_branch_parent_ancestry",
]
PUBLIC_CONST_NAMES = [
    "Check", "VERSION_RE", "ISOLATION_MARKER", "ISOLATION_SMOKE_TARGET",
    "LIVE_SMOKE_PROMPT", "LIVE_SMOKE_TIMEOUT_SEC", "LEASE_DEAD_RECHECK_SEC",
    "TARGET_WRAPPER_MARKERS", "ORPHAN_ARTIFACT_BRANCH_SOURCE",
    "MAP_SIZE_ACTION", "MAP_GROWTH_SOURCE", "LABELS",
]
COLLABORATOR_NAMES = [
    "alerts", "artifact_branch", "canary", "coldstart", "config", "gitcmd",
    "liveness", "projects", "roles", "runner", "snapshot", "spend", "stack",
    "store", "targets", "workspace", "zone_lock", "subprocess", "shutil",
    "ci",  # импорт main с 01M1TQ0X14 (06.09)
]
# Приватные помощники, к которым тесты обращаются НАПРЯМУЮ через
# `doctor._имя(...)` (не докстринг-упоминания вроде `doctor._orphan_worktrees`
# в orchestrator/workspace.py:29, где это просто текст комментария о приёме,
# а не реальный вызов атрибута).
PRIVATE_HELPER_NAMES = [
    "_auto_ack_gone", "_fix_ignored_artifact_files",
    "_orphan_artifact_branches", "_print_orphan_branch_candidates",
    "_remote_artifact_branch_names",
]
ALL_REQUIRED_FACADE_NAMES = (
    PUBLIC_FUNC_NAMES + PUBLIC_CONST_NAMES + COLLABORATOR_NAMES
    + PRIVATE_HELPER_NAMES
)

# --- перечень AC-3: 18 комментариев-разделителей doctor.py на main к моменту
# разреза (17 сняты 06.09 07:52Z; 18-й — «сверка артефактной ветки с origin/CI»,
# пришёл в main задачей 01M1TQ0X14 06.09 11:15Z — правка планки Оператором
# 06.09 по ADR-0012, состав проверок main до разреза)
# (tasks/01M1TT9BPBRYMDXXEWVZSRG51V/SPEC.md, «Материалы», строки 83, 298,
# 412, 478, 539, 590, 672, 791, 827, 868, 1046, 1275, 1396, 1429, 1573,
# 1620, 1725) — сняты дословно 06.09.
SECTION_MARKERS = [
    "# --- окружение шага (требование 2, 5, 9) ------------------------------",
    "# --- смоук изоляции (требование 6) -------------------------------------",
    "# --- живой смоук CLI (требование 3) -------------------------------------",
    "# --- recovery-сверка (требование 4) -------------------------------------",
    "# --- авто-ack (tasks/T035/SPEC.md, требования 1-7) -----------------------",
    "# --- сироты (требование 8) ----------------------------------------------",
    "# --- изоляция пула канарейки от ролей (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ,",
    "# --- свежесть ветки (SPEC T051, требование 8) -----------------------------",
    "# --- lease с мёртвым pid (SPEC T044, требование 11) ----------------------",
    "# --- рекон осиротевшего шага (SPEC 01M1G..., требование 4, AC-7/AC-8) ---",
    "# --- сторож зависших прогонов тестов --------------------------------------",
    "# --- прочие проверки (требование 9) --------------------------------------",
    "# --- пин запущенной версии (A7, Stage1, требования 5-6, AC-13) ----------",
    "# --- уборка осиротевших артефактных веток (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T,",
    "# --- уборка игнорируемых файлов артефактных веток (SPEC ------------------",
    "# --- наблюдатель роста карты кодовой базы (01M1RFVWV6WWTXRC5F40K61632,",
    "# --- сверка артефактной ветки с origin/CI (SPEC ---------------------------",
    "# --- команда doctor -------------------------------------------------------",
]

# --- перечень AC-3: хэш AST-дерева тела функции (без атрибутов
# позиции/строки — `ast.dump` по умолчанию их не пишет) для каждой
# перенесённой функции, снятый 06.09 с СЕГОДНЯШНЕГО `orchestrator/doctor.py`
# (пересчитать: `ast.dump(ast.parse(inspect.getsource(fn)))`, sha256,
# первые 16 hex-символов). Совпадение хэша после переноса означает «то же
# дерево разбора» — тело функции не переписано (докстрока входит в дерево
# как строковый литерал, так что и её правка меняет хэш; комментарии и
# пробелы вне докстроки на дерево не влияют).
FUNCTION_LOGIC_HASHES = {
    # main после 01M1TQ0X14 / 01M1TQ0ZCY (06.09), сняты с doctor.py main до разреза
    "check_artifact_branch_sync": "5caf200ad060ba08",
    "check_artifact_branch_ci": "3f015bf0bcadab32",
    "check_artifact_branch_parent_ancestry": "a46e1239c182eb0c",
    "_artifact_branch_candidates": "0e203d57115ba8d6",
    "_is_ancestor": "d3e932176d6105c1",
    "_sync_direction": "21486112c1f51f5d",
    "_artifact_branch_ci_runs": "51cb017fbde30ea1",
    "_artifact_branch_first_commit_parent": "9346055c81f53cee",
    "check_cli_found": "5157ec0cfeb3d491",
    "cli_version": "e97973855a21652b",
    "check_cli_version": "72a047662b1d49d2",
    "check_token": "c504c7c1c198bacc",
    "check_git_identity": "c705c31c7c1d282a",
    "check_disk_space": "355711a91074222c",
    "check_role_home_reference": "62e997b6f8d49417",
    "check_target_layout": "4453e8d61897b096",
    "check_target_wrapper": "e8815fac08560af3",
    "preflight_checks": "ae7827b2a4ddaf38",
    "isolation_smoke": "a879f1cb2d14eced",
    "live_smoke": "caa16d35331f8071",
    "recovery_check": "38c227b0c167d698",
    "check_orphans": "26c33c6a35fc8d3d",
    "check_role_log_pool_leak": "4c8d5c405354b76c",
    "check_canary_pool_drift": "617bf4725a806f3e",
    "check_token_repo_scope": "12d2a75780ff426a",
    "check_branch_freshness": "27086ef8c04e006e",
    "check_leases": "1e625f9974924d1a",
    "check_merge_lock": "a1a7ed5d06a67d38",
    "check_hung_test_runs": "6371bd58f098b1f5",
    "check_zone_waits": "e7d5944a7b34fbe2",
    "check_backup_age": "f5e5eea899c56f06",
    "check_task_counters": "13a732b5d95f4da5",
    "check_pending_snapshots": "0d7cc9de4da47a6d",
    "check_remote_empty": "87c2c3a5dd2d2961",
    "check_base_branch": "4ac16111c0dcb569",
    "check_root_pin": "aec0bd051dc330f3",
    "sweep_orphan_artifact_branches": "c8a8e21253d095a4",
    "check_map_growth": "5f374bf88a5da4b3",
    "all_checks": "305087f91fb8fdf9",  # было 1ed701f9c757c996 — до мержей 01M1TQ0X14/01M1TQ0ZCY (три новые строки all_checks); правка Оператора 06.09
    "cmd_doctor": "6702583d007e78e3",
    "cmd_alert_ack": "9b189b6a138e42d5",
    "_auto_ack_gone": "1f246e305730ef52",
    "_fix_ignored_artifact_files": "b8d8bb566d9c0a32",
    "_orphan_artifact_branches": "14badb1294677b9b",
    "_print_orphan_branch_candidates": "205938ada1a9adff",
    "_remote_artifact_branch_names": "e4dba6e36d8dc7a3",
}

# --- перечень AC-5/AC-11: имена и статусы `Check` из `all_checks(conn)` в
# порядке вызова, снятые 06.09 прогоном `DoctorCommandTest.healthy_mocks()`
# (tests/test_doctor.py) на пустой БД с целевым файлом, декларирующим
# ровно один target `artel` (tests/test_doctor.py:TARGETS_YAML_DOGFOOD_ONLY).
EXPECTED_CHECKS_IN_ORDER = [
    ("cli-found", "ok"), ("cli-version", "ok"),
    ("token", "ok"), ("token", "ok"), ("token", "ok"),
    ("git-identity", "ok"), ("disk-space", "ok"),
    ("role-home-reference", "ok"), ("backup-age", "ok"),
    ("task-counters", "ok"), ("isolation-smoke", "ok"), ("live-smoke", "ok"),
    ("target-layout", "warn"), ("target-wrapper", "ok"),
    ("remote-empty", "skip"), ("base-branch", "skip"), ("recovery", "skip"),
    ("orphans-dirs", "ok"), ("orphans-branches", "ok"),
    ("orphans-worktrees", "ok"), ("leases", "ok"), ("merge-lock", "ok"),
    ("hung-test-runs", "ok"), ("zone-waits", "ok"),
    ("branch-freshness", "ok"),
    ("artifact-branch-parent-ancestry", "skip"),  # main с 01M1TQ0ZCY (06.09)
    ("root-pin", "ok"),
    ("canary-pool-leak", "ok"), ("canary-pool-drift", "ok"),
    ("token-repo-scope", "skip"), ("python", "ok"), ("git", "ok"),
    ("gh", "ok"), ("claude", "ok"), ("venv", "ok"),
]


class _FacadeCollapser(ast.NodeTransformer):
    """Схлопывает `doctor.<имя>` обратно в `<имя>` перед хешированием —
    иначе хеш меняется от единственной механической правки переноса
    (ленивый доступ к коллаборанту через фасад, требование 3 SPEC), даже
    если логика тела не изменилась ни на символ. Правка планки Оператором
    06.09 по эскалации разработчика (ANSWER-3), ADR-0012."""

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id == "doctor":
            return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
        return node


def logic_hash(fn) -> str:
    tree = ast.parse(inspect.getsource(fn))
    tree = _FacadeCollapser().visit(tree)
    ast.fix_missing_locations(tree)
    return hashlib.sha256(ast.dump(tree).encode()).hexdigest()[:16]


def package_py_files():
    return sorted(p for p in DOCTOR_PKG_DIR.glob("*.py") if p.name != "__init__.py")
