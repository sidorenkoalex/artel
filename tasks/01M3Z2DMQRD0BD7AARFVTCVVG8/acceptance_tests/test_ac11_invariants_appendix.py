"""AC-11: приложение к PLAN с правками инвариантов применяется, `test_invariants` зелёный.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан — в документах задачи нет ни PLAN, ни приложения с правкой `docs/invariants.md`.

Файл разовый: проверяет PLAN.md этой задачи. PLAN читается из git, не с
диска: сначала из ветки документов прежнего пульта
(`artifact/<id в нижнем регистре>` — этой задачей ведёт пульт до её
мержа), затем по имени `artifact_branch.branch_name` и по
`refs/artifacts/<id>`.

Приложения (`guard.plan_appendices`) по `docs/invariants.md` и
`tests/test_invariants.py` применяются по порядку в отдельной рабочей копии
головы кода задачи (`git worktree add --detach`, затем `git apply --check`
и `git apply`); в ней же гоняется `tests/test_invariants.py` — код и
инвариант меняются одним мержем. Прогон файла длится около двух минут,
поэтому он разбит на срезы по узлам: каждый срез — свой тестовый метод под
потолком таймаута планки.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, gitcmd  # noqa: E402
from scripts import guard  # noqa: E402

TASK_ID = "01M3Z2DMQRD0BD7AARFVTCVVG8"
INVARIANTS = "docs/invariants.md"
INVARIANTS_TEST = "tests/test_invariants.py"
ROWS = ("25", "27", "28", "33", "34", "38")
SLICES = 6
SLICE_TIMEOUT_SEC = 100


def _plan_text() -> str | None:
    for rev in (f"refs/heads/artifact/{TASK_ID.lower()}",
                artifact_branch.branch_name(TASK_ID),
                f"refs/artifacts/{TASK_ID}"):
        text, _ = gitcmd.show(rev, f"tasks/{TASK_ID}/PLAN.md")
        if text:
            return text
    return None


def _git(cwd: Path, *args: str, input_text: str | None = None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, input=input_text)


def _rows(text: str) -> dict:
    rows = {}
    for line in text.splitlines():
        cells = line.split("|")
        if len(cells) > 2 and cells[1].strip() in ROWS:
            rows.setdefault(cells[1].strip(), []).append(line)
    return rows


class _AppendixScratch:
    """Рабочая копия головы кода с применёнными приложениями — одна на класс."""

    error = None
    scratch = None
    base_invariants = None
    nodes = None

    @classmethod
    def build(cls) -> None:
        plan = _plan_text()
        if not plan:
            cls.error = f"PLAN.md задачи не прочитан из git ({TASK_ID})"
            return
        appendices, errors = guard.plan_appendices(plan)
        mine = [a for a in appendices
                if INVARIANTS in a.paths or INVARIANTS_TEST in a.paths]
        if not any(INVARIANTS in a.paths for a in mine):
            cls.error = (f"в PLAN.md нет приложения с правкой {INVARIANTS} "
                         f"(ошибки разбора: {errors})")
            return
        head = _git(REPO_ROOT, "rev-parse", "HEAD").stdout.strip()
        cls.tmp = tempfile.mkdtemp()
        cls.scratch = Path(cls.tmp) / "scratch"
        res = _git(REPO_ROOT, "worktree", "add", "--detach", "--quiet",
                   str(cls.scratch), head)
        if res.returncode != 0:
            cls.error = f"рабочая копия головы не создана: {res.stderr}"
            return
        cls.base_invariants = (cls.scratch / INVARIANTS).read_text(
            encoding="utf-8")
        for appendix in mine:
            check = _git(cls.scratch, "apply", "--check", "-",
                         input_text=appendix.diff)
            if check.returncode != 0:
                cls.error = (f"git apply --check отказал приложению "
                             f"{appendix.paths}: {check.stderr}")
                return
            applied = _git(cls.scratch, "apply", "-", input_text=appendix.diff)
            if applied.returncode != 0:
                cls.error = (f"git apply отказал приложению {appendix.paths}: "
                             f"{applied.stderr}")
                return
        collect = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             "-p", "no:cacheprovider", INVARIANTS_TEST],
            cwd=cls.scratch, capture_output=True, text=True, timeout=120)
        cls.nodes = [line.strip() for line in collect.stdout.splitlines()
                     if line.startswith(f"{INVARIANTS_TEST}::")]
        if not cls.nodes:
            cls.error = (f"{INVARIANTS_TEST} с приложением не собирается:\n"
                         f"{collect.stdout[-2000:]}\n{collect.stderr[-2000:]}")

    @classmethod
    def drop(cls) -> None:
        if cls.scratch is not None:
            _git(REPO_ROOT, "worktree", "remove", "--force", str(cls.scratch))
            shutil.rmtree(cls.tmp, ignore_errors=True)


class Ac11InvariantsAppendixTest(unittest.TestCase):
    """AC-11."""

    @classmethod
    def setUpClass(cls):
        _AppendixScratch.build()

    @classmethod
    def tearDownClass(cls):
        _AppendixScratch.drop()

    def setUp(self):
        if _AppendixScratch.error:
            self.fail(_AppendixScratch.error)

    def test_ac11_appendix_applies_and_edits_named_rows(self):
        """Приложение применяется и правит строки 25, 27, 28, 33, 34, 38.

        Ловит мутацию: приложение правит не все названные в критерии
        инварианты (например только 25 и 27) — строка 33 после применения
        та же, что до него.
        """
        after = (_AppendixScratch.scratch / INVARIANTS).read_text(
            encoding="utf-8")
        before_rows = _rows(_AppendixScratch.base_invariants)
        after_rows = _rows(after)
        unchanged = [n for n in ROWS
                     if before_rows.get(n) == after_rows.get(n)]
        self.assertEqual(unchanged, [],
                         f"приложение не правит строки инвариантов {unchanged}")

    def _run_slice(self, index: int) -> None:
        nodes = _AppendixScratch.nodes[index::SLICES]
        if not nodes:
            return
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             *nodes],
            cwd=_AppendixScratch.scratch, capture_output=True, text=True,
            timeout=SLICE_TIMEOUT_SEC)
        self.assertEqual(res.returncode, 0,
                         f"{INVARIANTS_TEST} с приложением красный (срез "
                         f"{index + 1}/{SLICES}):\n{res.stdout[-4000:]}\n"
                         f"{res.stderr[-2000:]}")

    def test_ac11_invariants_test_green_with_appendix_slice1(self):
        """Срез 1 из 6 узлов `tests/test_invariants.py` зелёный с приложением.

        Ловит мутацию: код задачи меняет механику (ссылка вместо ветки), а
        приложение не правит утверждающий прежнее устройство тест
        инварианта — узел этого среза красный.
        """
        self._run_slice(0)

    def test_ac11_invariants_test_green_with_appendix_slice2(self):
        """Срез 2 из 6 узлов `tests/test_invariants.py` зелёный с приложением.

        Ловит мутацию: та же, что у среза 1, для узлов этого среза.
        """
        self._run_slice(1)

    def test_ac11_invariants_test_green_with_appendix_slice3(self):
        """Срез 3 из 6 узлов `tests/test_invariants.py` зелёный с приложением.

        Ловит мутацию: та же, что у среза 1, для узлов этого среза.
        """
        self._run_slice(2)

    def test_ac11_invariants_test_green_with_appendix_slice4(self):
        """Срез 4 из 6 узлов `tests/test_invariants.py` зелёный с приложением.

        Ловит мутацию: та же, что у среза 1, для узлов этого среза.
        """
        self._run_slice(3)

    def test_ac11_invariants_test_green_with_appendix_slice5(self):
        """Срез 5 из 6 узлов `tests/test_invariants.py` зелёный с приложением.

        Ловит мутацию: та же, что у среза 1, для узлов этого среза.
        """
        self._run_slice(4)

    def test_ac11_invariants_test_green_with_appendix_slice6(self):
        """Срез 6 из 6 узлов `tests/test_invariants.py` зелёный с приложением.

        Ловит мутацию: та же, что у среза 1, для узлов этого среза.
        """
        self._run_slice(5)


if __name__ == "__main__":
    unittest.main()
