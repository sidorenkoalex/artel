"""Общий код разовых файлов планки задачи 01M443HPZBMJGCHVGV4JQN88RS.

Не тестовый модуль: префикс `_` обязателен (skills/test-authoring.md).

Держит:
- корень рабочей копии кода, в которую выложена планка (`CODE_ROOT`), и
  поиск сторожа из долгоживущего файла задачи
  (`tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py::global_sleep_patches`);
- базу диффа задачи — `gitcmd.diff_base` (точка расхождения с `origin`);
- чтение PLAN.md из ссылки документов задачи (не с диска) и разбор его
  приложений тем же узлом, что гейт приложений PLAN (`guard.plan_appendices`);
- копию чистого дерева HEAD ветки (`git archive HEAD`) со своим `git init`,
  на которую ложатся приложения PLAN.
"""
import atexit
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
from tests.test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard import (  # noqa: E402,F401
    global_sleep_patches)

TASK_ID = "01M443HPZBMJGCHVGV4JQN88RS"
INV_REL = "tests/test_invariants.py"


def git(*args: str, cwd: Path = CODE_ROOT, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=120, **kw)


def base_or_fail(case) -> str:
    """База диффа задачи: точка расхождения HEAD ветки с `origin/main`."""
    base = gitcmd.diff_base("HEAD", CODE_ROOT)
    case.assertTrue(base, "git не дал базу диффа задачи (gitcmd.diff_base)")
    return base


def text_at(rev: str, rel: str) -> str | None:
    res = git("show", f"{rev}:{rel}")
    return res.stdout if res.returncode == 0 else None


def changed_paths(base: str) -> list[str]:
    """Пути, изменённые от базы до рабочего дерева (включая незакоммиченное)."""
    res = git("diff", "--name-only", base, "--")
    assert res.returncode == 0, res.stderr
    return [p for p in res.stdout.splitlines() if p]


def plan_or_fail(case) -> str:
    text, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                               f"tasks/{TASK_ID}/PLAN.md")
    case.assertIsNotNone(text, f"PLAN.md не прочитан из ссылки документов "
                               f"задачи: {reason}")
    return text


def appendices_or_fail(case):
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
