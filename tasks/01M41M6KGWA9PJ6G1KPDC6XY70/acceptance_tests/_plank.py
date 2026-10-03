"""Общий код разовых файлов планки задачи 01M41M6KGWA9PJ6G1KPDC6XY70.

Не тестовый модуль: префикс `_` обязателен (skills/test-authoring.md).

Держит:
- корень рабочей копии кода, в которую выложена планка (`CODE_ROOT`);
- чтение PLAN.md из ссылки документов задачи (не с диска) и разбор его
  приложений тем же узлом, что гейт приложений PLAN
  (`guard.plan_appendices`);
- «дерево с наложенным приложением» (SPEC, преамбула раздела «Критерии
  приёмки»): копия чистого дерева HEAD ветки (`git archive HEAD`) со своим
  `git init`, на которую приложения PLAN ложатся подряд `git apply` — тем
  же порядком, каким их кладёт мерж; дерево строится один раз на процесс;
- разбор `.github/workflows/ci.yml` по блокам отступов (полного YAML в
  пульте нет намеренно — тот же приём, что
  `tests/test_invariants.py::CiWorkflowKeepsARunForEveryPushTest`).
"""
import atexit
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[3]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from orchestrator import artifact_branch, gitcmd  # noqa: E402
from scripts import guard  # noqa: E402

TASK_ID = "01M41M6KGWA9PJ6G1KPDC6XY70"
CI_REL = ".github/workflows/ci.yml"
INV_REL = "tests/test_invariants.py"
PYTHON_JOB = "python"


def git(*args: str, cwd: Path = CODE_ROOT, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=120, **kw)


def read_plan() -> tuple[str | None, str]:
    """(текст PLAN.md, причина) из ссылки документов задачи — не с диска."""
    return gitcmd.show(artifact_branch.branch_name(TASK_ID),
                       f"tasks/{TASK_ID}/PLAN.md")


def plan_or_fail(case) -> str:
    text, reason = read_plan()
    case.assertIsNotNone(text, f"PLAN.md не прочитан из ссылки документов "
                               f"задачи: {reason}")
    return text


def appendices_or_fail(case):
    """Приложения PLAN без ошибок разбора; иначе — провал с причиной."""
    appendices, errors = guard.plan_appendices(plan_or_fail(case))
    case.assertEqual(errors, [], "ошибки разбора приложений PLAN")
    case.assertTrue(appendices, "в PLAN нет ни одного приложения")
    return appendices


def clean_tree(prefix: str) -> Path:
    """Копия чистого дерева HEAD ветки задачи со своим `git init`;
    каталог убирается на выходе процесса."""
    dest = Path(tempfile.mkdtemp(prefix=prefix))
    atexit.register(shutil.rmtree, dest, ignore_errors=True)
    archive = subprocess.run(["git", "archive", "--format=tar", "HEAD"],
                             cwd=CODE_ROOT, capture_output=True, timeout=120)
    assert archive.returncode == 0, archive.stderr.decode(errors="replace")
    untar = subprocess.run(["tar", "-x", "-f", "-", "-C", str(dest)],
                           input=archive.stdout, capture_output=True,
                           timeout=120)
    assert untar.returncode == 0, untar.stderr.decode(errors="replace")
    res = git("init", "-q", cwd=dest)
    assert res.returncode == 0, res.stderr
    return dest


def apply_appendices(tree: Path, appendices, check_only: bool = False) -> list:
    """Приложения подряд на `tree`; список отказов git (пустой — всё легло)."""
    failures = []
    for appendix in appendices:
        args = ["--check"] if check_only else []
        res = git("apply", *args, "-", cwd=tree, input=appendix.diff)
        if res.returncode != 0:
            failures.append((appendix.paths, (res.stderr or res.stdout)
                             .strip()[:500]))
            if not check_only:
                break
    return failures


_APPLIED: list = []


def applied_tree(case) -> Path:
    """Дерево ветки с наложенными подряд приложениями PLAN (один раз на
    процесс)."""
    if _APPLIED:
        return _APPLIED[0]
    appendices = appendices_or_fail(case)
    tree = clean_tree("artel-ci-min-applied-")
    failures = apply_appendices(tree, appendices)
    case.assertEqual(failures, [], "приложения PLAN не легли на дерево ветки")
    _APPLIED.append(tree)
    return tree


# ------------------------------------------------------------ разбор ci.yml

def _top_block(text: str, key: str) -> list[str]:
    out, inside = [], False
    for ln in text.splitlines():
        if ln and not ln[0].isspace() and not ln.lstrip().startswith("#"):
            inside = ln.split(":")[0] == key
            continue
        if inside:
            out.append(ln)
    return out


def jobs(text: str) -> dict[str, list[str]]:
    """{имя задания: строки его блока} — задание = ключ с отступом 2 под
    `jobs:`. Строки-комментарии (`#` первым непробельным) отброшены:
    упоминание флага в комментарии — не шаг."""
    out: dict[str, list[str]] = {}
    current = None
    for ln in _top_block(text, "jobs"):
        if ln.lstrip().startswith("#"):
            continue
        if ln.startswith("  ") and len(ln) > 2 and not ln[2].isspace():
            current = ln.strip().split(":")[0]
            out[current] = []
            continue
        if current is not None:
            out[current].append(ln)
    return out


def own_field(block: list[str], key: str) -> list[str] | None:
    """Значение собственного поля задания (отступ 4): строка либо блочный
    список. None — поля нет."""
    for i, ln in enumerate(block):
        m = re.match(rf"    {re.escape(key)}:(.*)$", ln)
        if not m:
            continue
        value = m.group(1).split(" #")[0].strip()
        if value.startswith("[") and value.endswith("]"):
            return [v.strip().strip("'\"") for v in value[1:-1].split(",")
                    if v.strip()]
        if value:
            return [value]
        items = []
        for nxt in block[i + 1:]:
            mm = re.match(r"\s{6,}-\s*(\S+)", nxt)
            if not mm:
                break
            items.append(mm.group(1).strip("'\""))
        return items
    return None


def steps(block: list[str]) -> list[str]:
    """Тексты шагов задания (каждый шаг — от своей `- ` с отступом 6),
    продолжения строк `\\` склеены."""
    out: list[list[str]] = []
    for ln in block:
        if re.match(r"      - ", ln):
            out.append([ln])
        elif out:
            out[-1].append(ln)
    return [re.sub(r"\\\n\s*", " ", "\n".join(s)) for s in out]


def step_index(step_texts: list[str], pattern: str) -> int | None:
    for i, s in enumerate(step_texts):
        if re.search(pattern, s):
            return i
    return None


def pytest_lines(block: list[str]) -> list[str]:
    """Строки команд pytest задания (продолжения `\\` склеены)."""
    return [ln for s in steps(block) for ln in s.splitlines()
            if re.search(r"\bpytest\b", ln) and not ln.strip().startswith("#")
            and "name:" not in ln]


def min_jobs(text: str) -> dict[str, list[str]]:
    """Задания, кроме `python`, вызывающие `stack_ci.py --min`."""
    return {name: block for name, block in jobs(text).items()
            if name != PYTHON_JOB
            and re.search(r"stack_ci\.py\s+--min", "\n".join(block))}
