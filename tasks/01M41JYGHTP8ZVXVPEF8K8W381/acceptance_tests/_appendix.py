"""Общие помощники планки задачи 01M41JYGHTP8ZVXVPEF8K8W381: приложения
PLAN.md к защищённым `.github/workflows/ci.yml` и `tests/test_invariants.py`,
разбор `ci.yml` по отступам и временная копия дерева кода с применёнными
приложениями.

Предмет задачи приезжает в main приложением PLAN.md (SPEC, требования 4 и
6), а не коммитом в ветку задачи, поэтому наблюдаемое свойство критериев —
файлы ПОСЛЕ применения приложений:

- PLAN.md читается ТОЛЬКО с артефактной ветки задачи (`gitcmd.show` +
  `artifact_branch.branch_name`): на прогоне гейта на диске есть лишь
  `acceptance_tests/`;
- приложения разбираются штатным разбором пульта (`guard.plan_appendices`)
  и применяются подряд тем же вызовом, что у гейта применимости и цикла
  мержа (`plan_appendix.git_apply`);
- база сравнения — `gitcmd.diff_base` ветки задачи (точка расхождения с
  `origin/<основная ветка>`);
- исполняемые проверки (AC-4, AC-6, AC-7) идут во временной копии рабочего
  дерева кода ветки (без `tasks/`), куда наложены приложения: ни рабочая
  копия, ни репозиторий не трогаются, а песочница `FsmTest`, если она всё же
  пишет в каталог задач корня запуска, пишет в каталог задач КОПИИ — там его
  и видно.
"""
import ast
import contextlib
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, config, gitcmd  # noqa: E402
from orchestrator.advance_gates import plan_appendix  # noqa: E402
from scripts import guard  # noqa: E402

TASK_ID = "01M41JYGHTP8ZVXVPEF8K8W381"
CI_YML = ".github/workflows/ci.yml"
INVARIANTS = "tests/test_invariants.py"
TARGETS = (CI_YML, INVARIANTS)
PYTEST_TAIL = ("-p", "no:cacheprovider", "-p", "timeout", "-o", "timeout=120")


# ------------------------------------------------------------ состояние

class State:
    """Слепок приложений PLAN: `base` — файлы базы сравнения, `applied` —
    они же после применения всех приложений подряд."""

    def __init__(self, plan, plan_reason, branch, base_sha, base, applied,
                 appendices, parse_errors, apply_failures):
        self.plan = plan
        self.plan_reason = plan_reason
        self.branch = branch
        self.base_sha = base_sha
        self.base = base
        self.applied = applied
        self.appendices = appendices
        self.parse_errors = parse_errors
        self.apply_failures = apply_failures

    def paths(self) -> list:
        return [p for a in self.appendices for p in a.paths]

    def diagnosis(self) -> str:
        """Одна строка о состоянии приложений — в сообщение каждого отказа:
        «нет такой строки в ci.yml» иначе не отличить от «PLAN.md ещё не
        заведён» и «приложение не применилось»."""
        parts = [f"ветка задачи: {self.branch or '—'}",
                 f"база сравнения: {self.base_sha or '—'}"]
        if self.plan is None:
            parts.append(f"PLAN.md с артефактной ветки не прочитан: "
                         f"{self.plan_reason or '—'}")
        else:
            parts.append(f"приложений разобрано: {len(self.appendices)} "
                         f"{[list(a.paths) for a in self.appendices]}")
        if self.parse_errors:
            parts.append(f"ошибки разбора: {'; '.join(self.parse_errors)}")
        if self.apply_failures:
            parts.append(f"не применились: {'; '.join(self.apply_failures)}")
        return "; ".join(parts)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT,
                          capture_output=True, text=True)


def task_branch() -> str:
    """Ветка КОДА задачи: HEAD рабочего каталога прогона (гейт гоняет
    планку в рабочей копии задачи); из главной копии пульта — по имени из
    списка веток, иначе базой оказалась бы голова main."""
    prefix = f"task/{TASK_ID.lower()}-"
    head = _git("rev-parse", "--abbrev-ref", "HEAD")
    name = head.stdout.strip() if head.returncode == 0 else ""
    if name.startswith(prefix):
        return name
    listed = _git("branch", "--list", f"{prefix}*",
                  "--format=%(refname:short)")
    branches = [ln.strip() for ln in listed.stdout.splitlines()
                if ln.strip()] if listed.returncode == 0 else []
    return branches[0] if branches else name


def _apply_to_dir(directory: Path, appendices) -> list:
    """Приложения подряд на дерево `directory`; список отказов git."""
    failures = []
    for appendix in appendices:
        answer = plan_appendix.git_apply(directory, appendix)
        if answer:
            failures.append(f"{', '.join(appendix.paths)}: {answer}")
    return failures


@functools.lru_cache(maxsize=1)
def state() -> State:
    """Слепок — один раз на процесс прогона планки."""
    plan, plan_reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                   f"tasks/{TASK_ID}/PLAN.md")
    branch = task_branch()
    base_sha = gitcmd.diff_base(branch) if branch else None
    base = {}
    if base_sha:
        for rel in TARGETS:
            base[rel] = gitcmd.show(base_sha, rel)[0]
    appendices, parse_errors = (guard.plan_appendices(plan) if plan
                                else ([], []))
    applied, failures = dict(base), []
    if appendices and base_sha:
        wanted = set(TARGETS) | {p for a in appendices for p in a.paths}
        tmp = Path(tempfile.mkdtemp(prefix="artel-01m41-base-"))
        try:
            for rel in sorted(wanted):
                text = base[rel] if rel in base else gitcmd.show(base_sha,
                                                                 rel)[0]
                if text is None:
                    continue
                dest = tmp / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")
            failures = _apply_to_dir(tmp, appendices)
            applied = {rel: ((tmp / rel).read_text(encoding="utf-8")
                             if (tmp / rel).is_file() else None)
                       for rel in TARGETS}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return State(plan=plan, plan_reason=plan_reason, branch=branch,
                 base_sha=base_sha or "", base=base, applied=applied,
                 appendices=list(appendices),
                 parse_errors=tuple(parse_errors),
                 apply_failures=tuple(failures))


def applied_text(rel: str) -> str:
    return state().applied.get(rel) or ""


def base_text(rel: str) -> str:
    return state().base.get(rel) or ""


def appendices_for(rel: str) -> list:
    return [a for a in state().appendices if rel in a.paths]


_DIFF_FENCE_RE = re.compile(r"^```diff[^\n]*\n.*?(?:^```[^\n]*$|\Z)",
                            re.M | re.S)


def plan_prose() -> str:
    """Текст PLAN.md без блоков ```diff — то, что PLAN говорит СВОИМИ
    словами, а не строки самого диффа (иначе «PLAN называет X» выполнялось
    бы контекстной строкой приложения)."""
    return _DIFF_FENCE_RE.sub("", state().plan or "")


# ------------------------------------------------------- разбор ci.yml
#
# Полного YAML у пульта нет (`orchestrator/yamlmini.py` блочные списки не
# читает) — разбор по отступам, тем же приёмом, что у
# `tests/test_invariants.py` для `ci.yml`: job — ключ с отступом 2 под
# `jobs:`, его поля — отступ 4, шаг — `      - ` (отступ 6).

def top_block(text: str, key: str) -> list:
    out, inside = [], False
    for ln in text.splitlines():
        if ln and not ln[0].isspace():
            inside = ln.split(":")[0] == key
            continue
        if inside:
            out.append(ln)
    return out


def job_ids(text: str) -> list:
    return [ln.strip().split(":")[0] for ln in top_block(text, "jobs")
            if ln.startswith("  ") and len(ln) > 2 and not ln[2].isspace()
            and not ln.strip().startswith("#")]


def job_block(text: str, job: str) -> list:
    out, inside = [], False
    for ln in top_block(text, "jobs"):
        if ln.startswith("  ") and len(ln) > 2 and not ln[2].isspace():
            inside = ln.strip().split(":")[0] == job
            continue
        if inside:
            out.append(ln)
    return out


def own_field(block: list, key: str) -> list:
    """Строки поля job (отступ 4) `key:` вместе с его вложенными строками."""
    out, inside = [], False
    for ln in block:
        if re.match(r"    \S", ln):
            inside = bool(re.match(rf"    {re.escape(key)}:", ln))
        if inside:
            out.append(ln)
    return out


def own_scalar(block: list, key: str) -> str | None:
    lines = own_field(block, key)
    if not lines:
        return None
    return lines[0].split(":", 1)[1].strip()


def needs(block: list) -> set:
    lines = own_field(block, "needs")
    if not lines:
        return set()
    head = lines[0].split(":", 1)[1].strip()
    items = []
    if head:
        items = head.strip("[]").split(",")
    for ln in lines[1:]:
        m = re.match(r"\s+-\s*(\S+)", ln)
        if m:
            items.append(m.group(1))
    return {i.strip().strip("'\"") for i in items if i.strip()}


class Step:
    """Шаг job: `lines` — его строки (первая — с `- `, приведённая к
    отступу 8), поля шага — ключи с отступом 8."""

    def __init__(self, lines: list):
        first = lines[0]
        self.raw = lines
        self.lines = [first.replace("- ", "  ", 1)] + lines[1:]

    @property
    def text(self) -> str:
        return "\n".join(self.raw)

    def field(self, key: str) -> list:
        out, inside = [], False
        for ln in self.lines:
            if re.match(r" {8}\S", ln):
                inside = bool(re.match(rf" {{8}}{re.escape(key)}:", ln))
            if inside:
                out.append(ln)
        return out

    def scalar(self, key: str) -> str | None:
        lines = self.field(key)
        return lines[0].split(":", 1)[1].strip() if lines else None

    def run_commands(self) -> tuple:
        """Команды `run:` без строк-комментариев и без отступов."""
        lines = self.field("run")
        if not lines:
            return ()
        head = lines[0].split(":", 1)[1].strip()
        body = [] if head in ("|", ">", "|-", ">-") else [head]
        body += [ln.strip() for ln in lines[1:]]
        return tuple(ln for ln in body if ln and not ln.startswith("#"))

    def with_items(self) -> tuple:
        lines = self.field("with")
        if not lines:
            return ()
        head = lines[0].split(":", 1)[1].strip()
        items = [head] if head else []
        items += [ln.strip() for ln in lines[1:]
                  if ln.strip() and not ln.strip().startswith("#")]
        return tuple(items)

    def signature(self) -> tuple:
        """Команда шага: `uses`, `with`, `run` — без имени и комментариев
        (AC-3 говорит «без изменения их команд», не названий)."""
        return (self.scalar("uses"), self.with_items(), self.run_commands())


def steps(block: list) -> list:
    out, cur, inside = [], None, False
    for ln in block:
        if re.match(r"    \S", ln):
            inside = ln.strip().startswith("steps:")
            if cur:
                out.append(Step(cur))
                cur = None
            continue
        if not inside:
            continue
        if re.match(r" {6}- ", ln):
            if cur:
                out.append(Step(cur))
            cur = [ln]
        elif cur is not None:
            cur.append(ln)
    if cur:
        out.append(Step(cur))
    return out


MIN_MARK = "stack_ci.py --min"


def min_job(text: str) -> str | None:
    """Job, кроме `python`, чьи шаги определяют минимальную версию Python
    (`scripts/stack_ci.py --min`); при нескольких — первый."""
    for job in job_ids(text):
        if job == "python":
            continue
        if any(MIN_MARK in s.text for s in steps(job_block(text, job))):
            return job
    return None


def invariants_pytest_steps(block: list) -> list:
    return [s for s in steps(block)
            if any("pytest" in c and "tests/test_invariants.py" in c
                   for c in s.run_commands())]


# ------------------------------------------- утверждения тестов (AC-6)

def assertion_map(source: str) -> dict:
    """{квалифицированное имя функции: [ast.dump утверждений]} —
    утверждение = `assert` либо вызов `self.assert*`/`self.fail`. Номера
    строк в dump не входят: перенос кода и комментарии сравнение не ломают."""
    tree = ast.parse(source)
    result = {}

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                found = []
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Assert):
                        found.append(ast.dump(sub))
                    elif (isinstance(sub, ast.Call)
                          and isinstance(sub.func, ast.Attribute)
                          and (sub.func.attr.startswith("assert")
                               or sub.func.attr == "fail")):
                        found.append(ast.dump(sub))
                result[name] = found
                visit(child, f"{name}.")

    visit(tree, "")
    return result


# ------------------------------------------------- копия дерева кода

def _worktree_files() -> list:
    res = _git("ls-files", "-co", "--exclude-standard", "-z")
    res.check_returncode()
    return [f for f in res.stdout.split("\0")
            if f and not f.startswith("tasks/")]


@contextlib.contextmanager
def scratch_tree(skip: tuple = ()):
    """Временная копия рабочего дерева кода ветки (без `tasks/`) с
    наложенными приложениями PLAN, кроме приложений к путям `skip`.
    Отдаёт (каталог, отказы применения)."""
    tmp = Path(tempfile.mkdtemp(prefix="artel-01m41-scratch-"))
    try:
        for rel in _worktree_files():
            src = REPO_ROOT / rel
            if not src.is_file():
                continue
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        chosen = [a for a in state().appendices
                  if not any(p in skip for p in a.paths)]
        failures = _apply_to_dir(tmp, chosen)
        yield tmp, failures
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_pytest(cwd: Path, targets: list, parallel: bool = False):
    """pytest в копии дерева; признак роли из окружения снят — копия не
    рабочий каталог роли, а сторож роли (`conftest.py`) отказывает
    воркерам xdist под ним."""
    env = dict(os.environ)
    env.pop(config.ARTEL_ROLE_ENV, None)
    args = [sys.executable, "-m", "pytest", "-q", *targets, *PYTEST_TAIL]
    if parallel:
        args += ["-n", "auto", "-p", "xdist"]
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=600)


@functools.lru_cache(maxsize=1)
def invariants_run_applied():
    """Прогон `tests/test_invariants.py` в копии с приложениями — один на
    процесс (его читают AC-4 и AC-6). (код возврата, хвост вывода, отказы
    применения)."""
    with scratch_tree() as (tmp, failures):
        if failures:
            return None, "", tuple(failures)
        res = run_pytest(tmp, [INVARIANTS], parallel=True)
        return res.returncode, (res.stdout + res.stderr)[-3000:], ()


def ci_yml_readers(root: Path) -> list:
    """Модули `orchestrator/`, `scripts/`, `tests/` дерева `root`, ЧИТАЮЩИЕ
    содержимое `ci.yml`: строковый литерал с `ci.yml` (не докстринг) стоит
    внутри вызова `read_text`/`read_bytes`/`open` либо присвоен имени,
    которое такой вызов использует. Литерал-образец пути (список путей для
    проверки защищённости) читателем не считается."""
    readers = []
    for top in ("orchestrator", "scripts", "tests"):
        for path in sorted((root / top).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            if _reads_ci_yml(tree):
                readers.append(path.relative_to(root).as_posix())
    return readers


def _is_ci_literal(node) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and "ci.yml" in node.value and "\n" not in node.value)


def _reads_ci_yml(tree) -> bool:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                _is_ci_literal(n) for n in ast.walk(node.value)):
            for target in node.targets:
                for n in ast.walk(target):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
                    elif isinstance(n, ast.Attribute):
                        names.add(n.attr)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        fname = (func.attr if isinstance(func, ast.Attribute)
                 else func.id if isinstance(func, ast.Name) else "")
        if fname not in ("read_text", "read_bytes", "open"):
            continue
        for sub in ast.walk(node):
            if _is_ci_literal(sub):
                return True
            if isinstance(sub, ast.Name) and sub.id in names:
                return True
            if isinstance(sub, ast.Attribute) and sub.attr in names:
                return True
    return False


def branch_changed_tests() -> list:
    """Файлы `tests/*.py`, добавленные или изменённые веткой задачи (от
    базы сравнения до рабочего дерева, включая незакоммиченные и новые
    неотслеживаемые), кроме защищённого `tests/test_invariants.py`."""
    base = state().base_sha
    changed = set()
    if base:
        res = _git("diff", "--name-only", "--diff-filter=AM", base, "--",
                   "tests/")
        changed |= {ln for ln in res.stdout.splitlines() if ln}
    res = _git("ls-files", "--others", "--exclude-standard", "--", "tests/")
    changed |= {ln for ln in res.stdout.splitlines() if ln}
    return sorted(p for p in changed
                  if p.endswith(".py") and p != INVARIANTS
                  and (REPO_ROOT / p).is_file())
