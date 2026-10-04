"""Общий код разовых файлов планки задачи 01M443HV9SJYVYQTHJSQ87QV68.

Не тестовый модуль: префикс `_` обязателен (skills/test-authoring.md).

Держит:
- корень рабочей копии кода, в которую выложена планка (`CODE_ROOT`);
- чтение PLAN.md из ссылки документов задачи (не с диска) и разбор его
  приложений тем же узлом, что гейт приложений PLAN
  (`guard.plan_appendices`);
- «чистое дерево ветки»: копия HEAD ветки (`git archive HEAD`) со своим
  `git init` — на неё приложения PLAN ложатся подряд `git apply`, тем же
  порядком, каким их кладут ворота мержа; на ней же гоняются тесты
  «на дереве ветки без приложений»;
- разбор `.github/workflows/ci.yml` по блокам отступов (полного YAML в
  пульте нет намеренно — тот же приём, что планка
  01M41M6KGWA9PJ6G1KPDC6XY70).
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

TASK_ID = "01M443HV9SJYVYQTHJSQ87QV68"
CI_REL = ".github/workflows/ci.yml"
DOC_REL = "docs/operator-session.md"
SCRIPT_REL = "scripts/plan_appendix_ci.py"
SCRIPT_NAME = "plan_appendix_ci"
TEST_JOBS = ("python", "python-min")


def git(*args: str, cwd: Path = CODE_ROOT, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=120, **kw)


def plan_or_fail(case) -> str:
    """Текст PLAN.md из ссылки документов задачи — не с диска."""
    text, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                               f"tasks/{TASK_ID}/PLAN.md")
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


def added_lines(diff: str) -> str:
    """Добавленные строки unified-диффа (без `+++` заголовков), склеенные."""
    return "\n".join(ln[1:] for ln in diff.splitlines()
                     if ln.startswith("+") and not ln.startswith("+++"))


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
    упоминание сценария в комментарии — не шаг."""
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
