"""AC-1…AC-5 — линт ожидания по часам и чтения живых файлов из приложения PLAN к `tests/test_invariants.py`.

Линт едет приложением PLAN (SPEC, требование 1: правку
`tests/test_invariants.py` вносит Оператор), поэтому планка исполняет его
так, как он будет жить после наложения: дерево HEAD рабочей копии (без
`tasks/`) выгружается `git archive` во временный каталог, в нём
`tests/test_invariants.py` заменяется текстом после наложения приложения,
временный каталог становится git-репозиторием с одним коммитом, и линт —
классы, которые приложение ДОБАВЛЯЕТ в `tests/test_invariants.py`, —
гоняется там отдельным `python -m pytest` по их адресам. Копия
самодостаточна: `config.ROOT` копии считается от её `orchestrator/config.py`,
`Path(__file__)` линта — от её `tests/`, так что тест-образец, положенный в
`tests/` копии, линт видит, а настоящая рабочая копия не меняется.

PLAN.md читается из ссылки документов помощником пульта
(`_pult.artifact_text`), приложения разбирает тот же `guard.plan_appendices`,
что гейт применимости и мерж. Приложение уже наложено в HEAD (Оператор внёс
его в main, ветка подтянула main) — тогда «после» — сам HEAD, «до» — HEAD с
обратно снятым приложением.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан (его пишет developer после этого шага) — `artifact_text("PLAN.md")` возвращает `None`, приложения с линтом к `tests/test_invariants.py` нет.
"""
import ast
import io
import os
import random
import re
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from scripts import guard  # noqa: E402

INVARIANTS_REL = "tests/test_invariants.py"
SANDBOX_REL = "tests/sandbox.py"
RUN_TIMEOUT_SEC = 100
# Запись перечня исключений: «файл::метод — обоснование» (SPEC, требование 1).
ENTRY_KEY_RE = re.compile(r"^\s*[\w./-]+\.py::[\w.:]+\s*$")
ENTRY_LINE_RE = re.compile(r"^\s*[\w./-]+\.py::[\w.:]+\s*[—–-]+\s*(.*)$", re.DOTALL)
ENTRY_HEAD_RE = re.compile(r"^\s*([\w./-]+\.py)::([\w.:]+)")


# --- приложение и дерево ----------------------------------------------------

def git(*args: str, cwd=None, input_bytes=None) -> bytes:
    res = subprocess.run(["git", *args], cwd=cwd, input=input_bytes,
                         capture_output=True)
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: "
                             f"{res.stderr.decode('utf-8', 'replace')}")
    return res.stdout


def head_text(rel: str) -> str:
    return git("-C", str(CODE_ROOT), "show", f"HEAD:{rel}").decode("utf-8")


def apply_to_text(diff: str, text: str, reverse: bool) -> str | None:
    """Текст `tests/test_invariants.py` после `git apply` (или `-R`)
    приложения к `text` во временном репозитории; `None` — git отказал."""
    with tempfile.TemporaryDirectory(prefix="lint-plank-apply-") as tmp:
        repo = Path(tmp)
        git("init", "-q", str(repo))
        path = repo / INVARIANTS_REL
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
        patch = repo / "appendix.diff"
        patch.write_text(diff, encoding="utf-8")
        args = ["git", "-C", str(repo), "apply", "--include", INVARIANTS_REL]
        res = subprocess.run(args + (["-R"] if reverse else []) + [str(patch)],
                             capture_output=True, text=True)
        if res.returncode != 0:
            return None
        return path.read_text(encoding="utf-8")


def class_names(text: str) -> list:
    return [node.name for node in ast.parse(text).body
            if isinstance(node, ast.ClassDef)]


def lint_from_plan(case: unittest.TestCase) -> tuple:
    """(текст `tests/test_invariants.py` после приложения, имена классов,
    которые приложение добавляет)."""
    plan = artifact_text("PLAN.md")
    case.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов — "
                               "приложение с линтом к tests/test_invariants.py "
                               "вносит developer")
    appendices, errors = guard.plan_appendices(plan)
    case.assertEqual(errors, [], f"приложения PLAN не разобраны: {errors}")
    found = [a for a in appendices if INVARIANTS_REL in a.paths]
    case.assertEqual(len(found), 1, f"приложений к {INVARIANTS_REL} не одно: "
                                    f"{[a.paths for a in appendices]}")
    diff = found[0].diff
    head = head_text(INVARIANTS_REL)
    answer = apply_check(diff)
    if answer == "":
        before, after = head, apply_to_text(diff, head, reverse=False)
        case.assertIsNotNone(after, "git apply приложения к HEAD отказал")
    else:
        reverse = apply_check(diff, reverse=True)
        case.assertEqual(reverse, "", f"приложение к {INVARIANTS_REL} не "
                                      f"применяется к HEAD ({answer}) и не "
                                      f"наложено в нём ({reverse})")
        before, after = apply_to_text(diff, head, reverse=True), head
        case.assertIsNotNone(before, "обратное наложение приложения к HEAD "
                                     "отказало")
    added = [name for name in class_names(after)
             if name not in set(class_names(before))]
    case.assertTrue(added, f"приложение к {INVARIANTS_REL} не добавляет ни "
                           f"одного класса тестов — линта нет")
    return after, added


class LintTree:
    """Копия дерева HEAD (без `tasks/`) с `tests/test_invariants.py` после
    приложения; правки сценария — `write`/`append`, прогон линта — `run`."""

    def __init__(self, invariants_text: str, lint_classes: list):
        self.tmp = tempfile.TemporaryDirectory(prefix="lint-plank-tree-")
        self.root = Path(self.tmp.name)
        self.lint_classes = lint_classes
        archive = git("-C", str(CODE_ROOT), "archive", "--format=tar", "HEAD",
                      "--", ".", ":(exclude)tasks")
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(self.root, filter="data")
        self.write(INVARIANTS_REL, invariants_text)

    def close(self) -> None:
        self.tmp.cleanup()

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def append(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.write_text(path.read_text(encoding="utf-8") + text,
                        encoding="utf-8")

    def run(self) -> tuple:
        """(код выхода pytest, вывод) прогона классов линта в копии; копия
        перед прогоном фиксируется коммитом — линт, перечисляющий файлы
        через git, видит то же, что и обходящий каталог."""
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("GIT_") and k != "PYTEST_ADDOPTS"}
        env.update(GIT_AUTHOR_NAME="plank", GIT_AUTHOR_EMAIL="plank@example.invalid",
                   GIT_COMMITTER_NAME="plank",
                   GIT_COMMITTER_EMAIL="plank@example.invalid",
                   PYTHONDONTWRITEBYTECODE="1")
        if not (self.root / ".git").exists():
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root,
                           env=env, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=self.root, env=env, check=True,
                       capture_output=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "дерево"],
                       cwd=self.root, env=env, check=True, capture_output=True)
        nodes = [f"{INVARIANTS_REL}::{name}" for name in self.lint_classes]
        res = subprocess.run(
            [sys.executable, "-m", "pytest", *nodes, "-q", "-p",
             "no:cacheprovider", "-o", "addopts="],
            cwd=self.root, env=env, capture_output=True, text=True,
            timeout=RUN_TIMEOUT_SEC)
        return res.returncode, res.stdout + res.stderr


# --- тесты-образцы ------------------------------------------------------------

SLEEP_SAMPLES = {
    "пауза в тестовом методе": '''
        import time
        import unittest


        class {cls}(unittest.TestCase):

            def test_{name}(self):
                time.sleep(1)
                self.assertTrue(True)
        ''',
    "пауза в помощнике модуля теста": '''
        import time
        import unittest


        def settle():
            time.sleep(1)


        class {cls}(unittest.TestCase):

            def test_{name}(self):
                settle()
                self.assertTrue(True)
        ''',
}

DEADLINE_SAMPLES = {
    "while до срока": '''
        import time
        import unittest


        class {cls}(unittest.TestCase):

            def ready(self):
                return False

            def test_{name}(self):
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if self.ready():
                        return
                self.fail("не дождались")
        ''',
    "while по прошедшему времени": '''
        import time
        import unittest


        class {cls}(unittest.TestCase):

            def ready(self):
                return False

            def test_{name}(self):
                started = time.monotonic()
                while time.monotonic() - started < 5:
                    if self.ready():
                        return
                self.fail("не дождались")
        ''',
}

TARGETS_SAMPLES = {
    "Path(__file__) прямо": '''
        import unittest
        from pathlib import Path


        class {cls}(unittest.TestCase):

            def test_{name}(self):
                text = (Path(__file__).resolve().parent.parent
                        / "targets.yaml").read_text(encoding="utf-8")
                self.assertIn("artel", text)
        ''',
    "корень репозитория именем модуля": '''
        import unittest
        from pathlib import Path

        REPO_ROOT = Path(__file__).resolve().parents[1]


        class {cls}(unittest.TestCase):

            def test_{name}(self):
                with open(REPO_ROOT / "targets.yaml", encoding="utf-8") as fh:
                    text = fh.read()
                self.assertIn("artel", text)
        ''',
}

SANDBOX_HELPER = '''


def lint_plank_wait_{name}(predicate, timeout=5.0):
    """Помощник песочницы, добавленный планкой: ожидание по часам."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(1)
    return False
'''


def rand_name(rng: random.Random) -> str:
    return "".join(rng.choice("abcdefghijkmnpqrstuvwxyz") for _ in range(10))


class LintAppendixTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.seed = random.randrange(1 << 30)
        print(f"зерно: {cls.seed}")

    def setUp(self):
        self.rng = random.Random(self.seed ^ zlib.crc32(self.id().encode()))

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}"

    def tree(self) -> LintTree:
        after, added = lint_from_plan(self)
        tree = LintTree(after, added)
        self.addCleanup(tree.close)
        return tree

    def sample_rel(self) -> tuple:
        name = rand_name(self.rng)
        return f"tests/test_lintprobe_{name}.py", name

    def assert_red_on_samples(self, samples: dict) -> None:
        tree = self.tree()
        for kind, template in samples.items():
            with self.subTest(образец=kind):
                rel, name = self.sample_rel()
                text = textwrap.dedent(template).format(
                    cls=f"LintProbe{name.capitalize()}Test", name=name)
                path = tree.write(rel, text)
                try:
                    code, out = tree.run()
                finally:
                    path.unlink()
                self.assertNotEqual(code, 0, self.note(
                    f"линт {tree.lint_classes} зелёный на образце «{kind}» "
                    f"({rel}):\n{text}\nвывод pytest:\n{out[-3000:]}"))
                self.assertNotIn("ERROR collecting", out, self.note(
                    f"линт не собрался, а не покраснел:\n{out[-3000:]}"))
                self.assertRegex(out, r"\d+ failed", self.note(
                    f"линт не исполнился (код {code}):\n{out[-3000:]}"))

    # --- AC-1 -----------------------------------------------------------------

    def test_ac1_lint_red_on_sample_with_time_sleep_1(self):
        """Тест-образец с `time.sleep(1)` в `tests/` копии — линт красен.

        Сценарий: в копию дерева HEAD с наложенным приложением кладётся
        `tests/test_lintprobe_<случайное>.py` с `time.sleep(1)` — в самом
        тестовом методе и (отдельный подслучай) в помощнике модуля теста;
        файла нет ни в `tests/sandbox.py`, ни в перечне исключений. Прогон
        классов, добавленных приложением, завершается не нулём, и не из-за
        ошибки сбора.

        Ловит мутацию: линт ищет только `mock.patch(… "sleep" …)`, а не
        вызов `time.sleep` — образец проходит, код выхода 0; линт смотрит
        лишь тела `test_*`-методов — подслучай с помощником модуля зелен;
        исключение задано файлом-маской (`test_*.py`), а не записью
        «файл::метод» — образец попадает под исключение, код 0.
        """
        self.assert_red_on_samples(SLEEP_SAMPLES)

    # --- AC-2 -----------------------------------------------------------------

    def test_ac2_lint_red_on_sample_with_monotonic_deadline_loop(self):
        """Тест-образец с циклом до срока по `time.monotonic()` без паузы — линт красен.

        Сценарий: образец ждёт в `while time.monotonic() < deadline` (и,
        отдельным подслучаем, `while time.monotonic() - started < 5`), не
        вызывая `time.sleep` вовсе, — ловить его может только правило о
        цикле до срока. Прогон линта в копии завершается не нулём.

        Ловит мутацию: правило (а) реализовано только для `time.sleep`, а
        цикл по `time.monotonic()` не проверяется — образец без паузы
        проходит; цикл распознаётся лишь в форме `< deadline` — подслучай
        с разностью проходит.
        """
        self.assert_red_on_samples(DEADLINE_SAMPLES)

    # --- AC-3 -----------------------------------------------------------------

    def test_ac3_lint_red_on_sample_reading_real_targets_yaml(self):
        """Тест-образец, читающий настоящий `targets.yaml` репозитория, — линт красен.

        Сценарий: образец читает `targets.yaml` корня репозитория путём от
        `Path(__file__)` — прямо и через модульное имя `REPO_ROOT`
        (`read_text`, `open`), а не копию песочницы. Прогон линта в копии
        завершается не нулём.

        Ловит мутацию: правило (б) не заведено вовсе либо проверяет только
        `roles.yaml` — образец с `targets.yaml` проходит; правило ищет лишь
        `read_text` у выражения с `__file__` — подслучай `open(REPO_ROOT /
        "targets.yaml")` проходит.
        """
        self.assert_red_on_samples(TARGETS_SAMPLES)

    # --- AC-4 -----------------------------------------------------------------

    def test_ac4_lint_green_on_sandbox_helpers_and_listed_exceptions(self):
        """Линт зелен на помощнике `tests/sandbox.py` и на методах перечня; записи перечня — «файл::метод — обоснование».

        Сценарий: (а) в `tests/sandbox.py` копии дописан помощник с циклом
        до срока по `time.monotonic()` и `time.sleep(1)` — прогон линта
        завершается нулём; (б) в тексте классов линта найдены записи
        перечня исключений — строки «<файл>.py::<метод>» (ключом словаря
        с обоснованием-значением либо одной строкой «… — обоснование»),
        у каждой обоснование непустое, а названный метод есть в названном
        файле дерева HEAD (зелёный прогон дерева в (а) идёт с этими
        методами на месте).

        Ловит мутацию: помощники песочницы не исключены (обход
        `tests/**/*.py` целиком) — прогон (а) красен на добавленном
        помощнике; запись перечня без обоснования (`"…::метод": ""` или
        строка без « — ») — сообщение называет запись; запись ссылается на
        метод, которого в файле нет (опечатка — исключение не действует, а
        нарушение спрятано иначе) — сообщение называет запись.
        """
        after, added = lint_from_plan(self)
        tree = LintTree(after, added)
        self.addCleanup(tree.close)
        name = rand_name(self.rng)
        tree.append(SANDBOX_REL, "\nimport time\n" + SANDBOX_HELPER.format(name=name))
        code, out = tree.run()
        self.assertEqual(code, 0, self.note(
            f"линт {added} красен на помощнике tests/sandbox.py:\n"
            f"{out[-3000:]}"))

        entries = exception_entries(after, added)
        problems = []
        for text, reason in entries:
            if not reason.strip():
                problems.append(f"запись без обоснования: {text!r}")
                continue
            head = ENTRY_HEAD_RE.match(text)
            rel, method = head.group(1), head.group(2).split("::")[-1]
            source = tree_file(rel)
            if source is None:
                problems.append(f"файла записи нет в tests/: {text!r}")
            elif not re.search(rf"\bdef {re.escape(method)}\s*\(", source):
                problems.append(f"метода записи нет в файле: {text!r}")
        self.assertEqual(problems, [], self.note(
            f"перечень исключений линта {added}: {len(entries)} записей"))

    # --- AC-5 -----------------------------------------------------------------

    def test_ac5_lint_green_on_task_tree_with_appendix(self):
        """Линт зелёный на дереве `tests/` ветки задачи с наложенным приложением.

        Сценарий: копия дерева HEAD ветки (с исправлениями задачи и её
        долгоживущими файлами) с `tests/test_invariants.py` после
        приложения; классы, добавленные приложением, прогоняются без
        образцов — код выхода 0.

        Ловит мутацию: существующее нарушение (`time.sleep(0.05)` в
        `wait_until` теста дозора, ожидание `time.time()` пробника) не
        исправлено и не внесено в перечень — линт красен на дереве ветки;
        запись перечня называет метод не тем именем — нарушение не снято.
        """
        tree = self.tree()
        code, out = tree.run()
        self.assertEqual(code, 0, self.note(
            f"линт {tree.lint_classes} красен на дереве ветки задачи:\n"
            f"{out[-4000:]}"))
        self.assertRegex(out, r"\d+ passed", self.note(
            f"прогон линта не исполнил ни одного теста:\n{out[-3000:]}"))


def tree_file(rel: str) -> str | None:
    """Текст файла записи перечня в дереве HEAD: путь от корня либо имя в
    `tests/`."""
    for candidate in (rel, f"tests/{rel}"):
        res = subprocess.run(["git", "-C", str(CODE_ROOT), "show",
                              f"HEAD:{candidate}"], capture_output=True)
        if res.returncode == 0:
            return res.stdout.decode("utf-8", "replace")
    return None


def literal(node) -> str | None:
    """Строковое значение узла: константа, неявная склейка или `+` строк."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = literal(node.left), literal(node.right)
        return None if left is None or right is None else left + right
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None
    return value if isinstance(value, str) else None


def exception_entries(after: str, classes: list) -> list:
    """Записи перечня исключений в классах линта: (текст записи,
    обоснование). Запись — строка вида «<файл>.py::<метод>»: ключ словаря
    или первый элемент пары (обоснование — значение/второй элемент) либо
    одна строка «… — обоснование»."""
    entries = []
    seen = set()
    for node in ast.parse(after).body:
        if not (isinstance(node, ast.ClassDef) and node.name in classes):
            continue
        for sub in ast.walk(node):
            pairs = []
            if isinstance(sub, ast.Dict):
                pairs = [(k, v) for k, v in zip(sub.keys, sub.values)
                         if k is not None]
            elif isinstance(sub, ast.Tuple) and len(sub.elts) == 2:
                pairs = [tuple(sub.elts)]
            for key, value in pairs:
                text = literal(key)
                if text is not None and ENTRY_KEY_RE.match(text):
                    entries.append((text, literal(value) or ""))
                    seen.update(id(n) for n in ast.walk(key))
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                    and id(sub) not in seen):
                if ENTRY_KEY_RE.match(sub.value):
                    entries.append((sub.value, ""))
                    continue
                match = ENTRY_LINE_RE.match(sub.value)
                if match:
                    entries.append((sub.value, match.group(1)))
    return entries


if __name__ == "__main__":
    unittest.main()
