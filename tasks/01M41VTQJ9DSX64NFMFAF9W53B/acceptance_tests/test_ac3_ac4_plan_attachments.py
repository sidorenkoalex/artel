"""AC-3, AC-4 — 01M41VTQJ9DSX64NFMFAF9W53B: приложения к PLAN.md для
`.github/workflows/ci.yml` и для `docs/invariants.md` +
`tests/test_invariants.py`.

Группа: разовый

Красен до реализации: PLAN.md задачи пишет роль developer — до неё в ссылке документов его нет, и ни одного приложения извлечь не из чего.

Источник PLAN.md — ссылка документов задачи (`gitcmd.show(artifact_branch.
branch_name(TASK_ID), "tasks/<id>/PLAN.md")`), не диск. Приложения —
unified-диффы в фенсированных блоках ```diff (или ```patch) PLAN.md; блок
может нести один файл или несколько (`diff --git a/X b/X` либо `--- a/X` /
`+++ b/X`), секции раскладываются по пути `+++ b/<путь>`. Если один путь
встречается в PLAN несколько раз, берётся последняя секция.

Чистое дерево — отдельный `git worktree --detach` во временном каталоге на
базе ветки задачи `gitcmd.diff_base("HEAD")` (точка расхождения с
`origin/main`). На нём: `git apply --check` приложения к `ci.yml`, затем
его применение; затем `git apply --check` и применение приложения к
`docs/invariants.md`/`tests/test_invariants.py`. Если приложение уже
применено Оператором и подтянуто в ветку (прямой `--check` отказывает, а
`--check --reverse` проходит) — дерево уже несёт результат, приложение
считается корректным и повторно не накладывается.

Проверки содержимого после применения:
- `ci.yml` (AC-3) — разбор блоками отступов, как у
  `CiJobsByPushClassInvariantTest`: в секции `on:` (без строк-комментариев
  и хвостовых `# …`) нет `artifact/`; в задании `guard` (без строк-
  комментариев) нет `--artifact-branch`; ни одна строка `if:` под `jobs:`
  не ссылается на `refs/heads/artifact/`;
- `docs/invariants.md` (AC-4) — строки таблицы `| <номер> | …`: номера
  попарно различны; строка 36 ровно одна, во второй колонке ни одна
  фраза (части, разделённые `;` и `.`), упоминающая `artifact/`, не
  обходится без слова «гейт» (требование CI на `artifact/**` снято, а не
  переформулировано), колонка называет гейты переходов (`гейт` и
  `переход`) и задания `python-min` и `python`; строка «Порядок
  состояний FSM» несёт номер, отличный от 36;
- `CiJobsByPushClassInvariantTest` из `tests/test_invariants.py`
  временного дерева проходит pytest на `ci.yml` того же дерева.

Подтверждение `git apply --check` в PLAN (часть AC-3/AC-4) проверяется
по тексту PLAN: строка `git apply --check` в нём есть.

Планка провалидирована временным стабом: PLAN с диффами, снятыми с
временной правки `ci.yml`, `docs/invariants.md` и `tests/test_invariants.py`
(правка откачена), — все методы зелёные.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, config, gitcmd  # noqa: E402

TASK_ID = "01M41VTQJ9DSX64NFMFAF9W53B"
CI_YML = ".github/workflows/ci.yml"
INVARIANTS_MD = "docs/invariants.md"
TEST_INVARIANTS = "tests/test_invariants.py"

_FENCE_RE = re.compile(r"^```(?:diff|patch)[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)
_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|(.*)$")


def _plan_text() -> str | None:
    """PLAN.md из ссылки документов задачи."""
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    return text or None


def _split_sections(block: str) -> list[tuple[str, str]]:
    """[(путь, текст секции)] одного блока диффа."""
    sections: list[list[str]] = []
    cur: list[str] | None = None
    git_header_open = False
    for ln in block.splitlines():
        if ln.startswith("diff --git "):
            cur = [ln]
            sections.append(cur)
            git_header_open = True
            continue
        if ln.startswith("--- ") and not git_header_open:
            cur = [ln]
            sections.append(cur)
            continue
        if ln.startswith("+++ "):
            git_header_open = False
        if cur is not None:
            cur.append(ln)
    out = []
    for sec in sections:
        path = None
        for ln in sec:
            if ln.startswith("+++ "):
                target = ln[4:].split("\t")[0].strip()
                path = target[2:] if target.startswith("b/") else target
                break
        if path is None and sec[0].startswith("diff --git "):
            m = re.match(r"diff --git a/(\S+) b/(\S+)", sec[0])
            path = m.group(2) if m else None
        if path:
            out.append((path, "\n".join(sec) + "\n"))
    return out


def plan_attachments(plan: str) -> dict[str, str]:
    """{путь: последняя секция диффа} по всем блокам ```diff PLAN.md."""
    found: dict[str, str] = {}
    for block in _FENCE_RE.findall(plan):
        for path, text in _split_sections(block):
            found[path] = text
    return found


def _git(cwd, *args, input_text=None):
    return subprocess.run(["git", *args], cwd=cwd, input=input_text,
                          capture_output=True, text=True)


def _strip_comment(ln: str) -> str:
    if ln.strip().startswith("#"):
        return ""
    return re.split(r"\s#", ln, maxsplit=1)[0]


def _top_block(text: str, key: str) -> list[str]:
    out, inside = [], False
    for ln in text.splitlines():
        if ln and not ln[0].isspace():
            inside = ln.split(":")[0].strip().strip("'\"") == key
            continue
        if inside:
            out.append(ln)
    return out


def _job_block(text: str, job: str) -> list[str]:
    out, inside = [], False
    for ln in _top_block(text, "jobs"):
        if ln.startswith("  ") and len(ln) > 2 and not ln[2].isspace():
            inside = ln.strip().split(":")[0] == job
            continue
        if inside:
            out.append(ln)
    return out


def _table_rows(md: str) -> list[tuple[int, str]]:
    rows = []
    for ln in md.splitlines():
        m = _ROW_RE.match(ln)
        if m:
            rows.append((int(m.group(1)), m.group(2)))
    return rows


def _statement(rest: str) -> str:
    """Вторая колонка строки таблицы (сам инвариант)."""
    return rest.split(" | ")[0] if " | " in rest else rest.split("|")[0]


class PlanAttachmentsTest(unittest.TestCase):
    """Приложения PLAN.md, наложенные на чистое дерево базы ветки задачи."""

    plan = None
    attachments: dict = {}
    tree: Path | None = None
    problems: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.problems = {}
        cls.plan = _plan_text()
        if cls.plan is None:
            cls.problems["plan"] = (
                f"PLAN.md нет в ссылке документов "
                f"{artifact_branch.branch_name(TASK_ID)} — приложения AC-3/"
                f"AC-4 пишет роль developer")
            return
        cls.attachments = plan_attachments(cls.plan)
        base = gitcmd.diff_base("HEAD")
        if not base:
            cls.problems["plan"] = "gitcmd.diff_base(HEAD) не ответил"
            return
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tree = Path(cls._tmp.name) / "tree"
        res = _git(config.ROOT, "worktree", "add", "--detach", "--quiet",
                   str(cls.tree), base)
        if res.returncode != 0:
            cls.problems["plan"] = f"git worktree add отказал: {res.stderr}"
            cls.tree = None
            return
        cls._apply("ci", [CI_YML])
        cls._apply("invariants", [INVARIANTS_MD, TEST_INVARIANTS])

    @classmethod
    def _apply(cls, key: str, paths: list[str]):
        present = [p for p in paths if p in cls.attachments]
        if not present:
            cls.problems[key] = (f"PLAN.md не несёт блока ```diff ни по "
                                 f"одному из путей {paths}")
            return
        if key == "invariants" and INVARIANTS_MD not in present:
            cls.problems[key] = f"PLAN.md не несёт диффа по {INVARIANTS_MD}"
            return
        patch = "".join(cls.attachments[p] for p in present)
        check = _git(cls.tree, "apply", "--check", "-", input_text=patch)
        if check.returncode == 0:
            res = _git(cls.tree, "apply", "-", input_text=patch)
            if res.returncode != 0:
                cls.problems[key] = f"git apply отказал: {res.stderr}"
            return
        reverse = _git(cls.tree, "apply", "--check", "--reverse", "-",
                       input_text=patch)
        if reverse.returncode != 0:
            cls.problems[key] = (
                f"git apply --check приложения {present} на чистом дереве "
                f"отказал и прямо, и обратно:\n{check.stderr}\n"
                f"{reverse.stderr}")

    @classmethod
    def tearDownClass(cls):
        if cls.tree is not None:
            _git(config.ROOT, "worktree", "remove", "--force", str(cls.tree))
        tmp = getattr(cls, "_tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def _require(self, *keys: str):
        for key in ("plan", *keys):
            if key in self.problems:
                self.fail(self.problems[key])

    def _read(self, rel: str) -> str:
        return (self.tree / rel).read_text(encoding="utf-8")

    # --- AC-3 -------------------------------------------------------------

    def test_ac3_ci_attachment_applies_and_is_confirmed_in_plan(self):
        """PLAN несёт дифф по `.github/workflows/ci.yml`, он проходит `git apply --check` на чистом дереве, PLAN это подтверждает.

        Ловит мутацию: заголовок хунка приложения не совпадает с реальным
        диапазоном строк `ci.yml` (класс T046/T047) — `git apply --check`
        отказывает и прямо, и обратно; либо подтверждение прогона в PLAN
        не записано — строки `git apply --check` в PLAN нет.
        """
        self._require("ci")
        self.assertIn("git apply --check", self.plan,
                      "PLAN не подтверждает прогон git apply --check")

    def test_ac3_ci_yml_after_attachment_has_no_artifact_branch(self):
        """После приложения в `ci.yml` нет триггера, развилки и условий для `artifact/`.

        Ловит мутацию: приложение убирает `artifact/**` из
        `on.push.branches`, но оставляет в задании `guard` развилку
        `GUARD_ARGS="--all --artifact-branch"` или условие
        `!startsWith(github.ref, 'refs/heads/artifact/')` у
        `canary-guid-leak` — соответствующая строка останется в файле.
        """
        self._require("ci")
        ci = self._read(CI_YML)
        on_lines = [_strip_comment(ln) for ln in _top_block(ci, "on")]
        self.assertTrue(any(ln.strip() for ln in on_lines),
                        "в ci.yml после приложения нет секции on:")
        self.assertFalse([ln for ln in on_lines if "artifact/" in ln],
                         "on: всё ещё несёт artifact/")
        guard = _job_block(ci, "guard")
        self.assertTrue(guard, "в ci.yml нет задания guard")
        self.assertFalse(
            [ln for ln in guard if "--artifact-branch" in _strip_comment(ln)],
            "задание guard всё ещё несёт развилку --artifact-branch")
        conditions = [ln for ln in _top_block(ci, "jobs")
                      if re.match(r"\s+(-\s+)?if:", ln)
                      and "refs/heads/artifact/" in ln]
        self.assertFalse(conditions,
                         "условия заданий ссылаются на refs/heads/artifact/")

    # --- AC-4 -------------------------------------------------------------

    def test_ac4_invariants_attachment_applies_and_is_confirmed_in_plan(self):
        """PLAN несёт дифф по `docs/invariants.md` (и `tests/test_invariants.py`), он проходит `git apply --check` поверх приложения к `ci.yml`.

        Ловит мутацию: дифф `docs/invariants.md` снят с рабочей копии, где
        строки уже сдвинуты чужой правкой, — хунк не ложится на чистое
        дерево, `git apply --check` отказывает и прямо, и обратно.
        """
        self._require("ci", "invariants")
        self.assertIn("git apply --check", self.plan,
                      "PLAN не подтверждает прогон git apply --check")

    def test_ac4_invariant_numbers_are_unique(self):
        """После приложения в таблице `docs/invariants.md` нет двух строк с одним номером.

        Ловит мутацию: приложение правит текст первого инварианта 36, но
        не перенумеровывает второй («Порядок состояний FSM») — номер 36
        встречается дважды.
        """
        self._require("ci", "invariants")
        numbers = [n for n, _ in _table_rows(self._read(INVARIANTS_MD))]
        self.assertTrue(numbers, "в docs/invariants.md не найдено строк таблицы")
        dups = sorted({n for n in numbers if numbers.count(n) > 1})
        self.assertEqual([], dups, f"номера инвариантов повторяются: {dups}")

    def test_ac4_invariant_36_drops_artifact_ci_and_names_gates_and_python_min(self):
        """Инвариант 36 после приложения не требует CI на `artifact/**`, называет гейты переходов и задания `python-min` и `python`.

        Ловит мутацию: из перечня веток убран `artifact/**`, но хвост «а
        job `guard` не исключает `refs/heads/artifact/`» оставлен, или не
        дописано задание `python-min`, или не названа замена гейтами
        переходов — фраза с `artifact/` без слова «гейт», либо нет
        `python-min`/`гейт`/`переход` в тексте строки 36.
        """
        self._require("ci", "invariants")
        rows = [rest for n, rest in _table_rows(self._read(INVARIANTS_MD))
                if n == 36]
        self.assertEqual(1, len(rows), f"строк с номером 36: {len(rows)}")
        stmt = _statement(rows[0])
        low = stmt.lower()
        for phrase in re.split(r"[;.]\s", stmt):
            if "artifact/" in phrase:
                self.assertIn("гейт", phrase.lower(),
                              f"инвариант 36 по-прежнему требует CI на "
                              f"artifact/: {phrase!r}")
        self.assertIn("гейт", low, "инвариант 36 не называет гейты переходов")
        self.assertIn("переход", low,
                      "инвариант 36 не называет гейты переходов")
        self.assertIn("python-min", stmt,
                      "инвариант 36 не называет задание python-min")
        self.assertRegex(stmt, r"python(?!-min)",
                         "инвариант 36 не называет задание python")

    def test_ac4_fsm_order_invariant_gets_new_number(self):
        """Бывший второй инвариант 36 («Порядок состояний FSM») после приложения несёт номер, отличный от 36.

        Ловит мутацию: приложение перенумеровывает не тот инвариант
        (первый 36 вместо второго) или вовсе не трогает номер строки
        «Порядок состояний FSM» — она остаётся под номером 36.
        """
        self._require("ci", "invariants")
        rows = [n for n, rest in _table_rows(self._read(INVARIANTS_MD))
                if "Порядок состояний FSM" in _statement(rest)]
        self.assertEqual(1, len(rows),
                         f"строк «Порядок состояний FSM»: {len(rows)}")
        self.assertNotEqual(36, rows[0])

    def test_ac4_ci_jobs_invariant_test_green_on_patched_ci_yml(self):
        """`CiJobsByPushClassInvariantTest` дерева с обоими приложениями зелёный на его `ci.yml`.

        Ловит мутацию: приложение к `tests/test_invariants.py` оставляет в
        `CiJobsByPushClassInvariantTest` требование триггера или условия
        для `artifact/**`, а приложение к `ci.yml` их убрало — pytest этого
        класса во временном дереве падает.
        """
        self._require("ci", "invariants")
        res = subprocess.run(
            [sys.executable, "-m", "pytest", TEST_INVARIANTS,
             "-k", "CiJobsByPushClassInvariantTest", "-p", "no:cacheprovider",
             "-q"],
            cwd=self.tree, capture_output=True, text=True, timeout=110)
        self.assertEqual(0, res.returncode,
                         f"CiJobsByPushClassInvariantTest не зелёный:\n"
                         f"{res.stdout[-3000:]}\n{res.stderr[-2000:]}")
        self.assertIn("passed", res.stdout)


if __name__ == "__main__":
    unittest.main()
