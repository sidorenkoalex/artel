"""Приёмочные тесты T027 — codebase-map пульта автогеном.

Источник — только tasks/T027/SPEC.md, раздел «Критерии приёмки» (AC-1..AC-9).

Контракт, который SPEC оставляет открытым и который эти тесты фиксируют
как планку для разработчика (не выбор «на свой вкус» из двусмысленности
содержания критерия — это выбор точки входа, без которого критерии
AC-1..AC-8 нельзя проверить вообще никаким тестом):

- Генератор — самостоятельный скрипт `scripts/codebase_map.py`, тем же
  паттерном, что и существующий сосед `scripts/guard.py` (тоже
  запускается CI-джобом как отдельный процесс, тоже читает дерево
  относительно текущего рабочего каталога, а не абсолютного пути пульта:
  `guard.py --all` глобит `Path("tasks")` от cwd, не от `config.ROOT`).
- Запуск: `python3 scripts/codebase_map.py`, cwd = корень дерева, которое
  картируется (в CI это корень пульта после checkout — совпадает с
  `config.ROOT` только потому, что cwd раннера и есть корень репозитория;
  в тестах здесь — корень изолированной фикстуры).
  Выход генератора — `<cwd>/docs/codebase-map.md`.
- Код возврата: 0 — успех, отличный от 0 — провал (AC-8 опирается
  именно на это).

AC-9 (решение Оператора 25.08 по эскалации предыдущего прогона
test_author, зафиксировано в SPEC.md): сверка стухшей карты живёт
в том же CI-джобе, что запускает генератор — не в doctor. Тест ниже
проверяет это статическим разбором того же блока джоба, что и AC-7/
AC-8 (тот же приём: искать сигнатуры сравнения и провала в тексте
шага, не предполагая конкретный синтаксис bash/python реализации).
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "codebase_map.py"
OUTPUT_REL = Path("docs") / "codebase-map.md"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Модули фикстуры: {относительный путь: (докстринг | None, [публичные], [приватные])}
FIXTURE_MODULES = {
    "orchestrator/alpha.py": (
        "Alpha module: handles alpha things.", ["alpha_public"], ["_alpha_hidden"]),
    "orchestrator/beta.py": (
        None, ["beta_public"], ["_beta_hidden"]),
    "scripts/tool.py": (
        "Tool script: does tool things.", ["tool_public"], ["_tool_hidden"]),
    "tests/test_something.py": (
        "Tests for tool.", ["test_dummy"], []),
}
# Модуль во вложенной директории — не должен попасть в карту (без рекурсии).
NESTED_MODULE = "orchestrator/nested/ignored.py"

HEADING_RE = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$", re.M)
NO_DOCSTRING_MARK = "нет docstring"


def _write_module(root: Path, rel_path: str, docstring, public, private) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if docstring is not None:
        lines.append(f'"""{docstring}"""')
    if rel_path == "orchestrator/beta.py":
        # beta зависит от alpha, чтобы проверить обе стороны связи импорта.
        lines.append("from orchestrator import alpha")
    if rel_path == "scripts/tool.py":
        lines.append("from orchestrator import beta")
    if rel_path == "tests/test_something.py":
        lines.append("from scripts import tool")
    for name in public:
        lines.append(f"def {name}():\n    pass")
    for name in private:
        lines.append(f"def {name}():\n    pass")
    path.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def _build_fixture_repo(root: Path) -> None:
    for rel_path, (doc, public, private) in FIXTURE_MODULES.items():
        _write_module(root, rel_path, doc, public, private)
    _write_module(root, NESTED_MODULE, "Should not appear.", ["public_ignored"], [])

    def git(*args: str) -> None:
        res = subprocess.run(["git", *args], cwd=root,
                             capture_output=True, text=True)
        assert res.returncode == 0, f"git {args}: {res.stderr}"

    git("init", "-q", "-b", "main")
    git("config", "user.email", "artel-tests@example.invalid")
    git("config", "user.name", "artel acceptance tests")
    git("add", "-A")
    git("commit", "-q", "-m", "фикстура codebase-map")


def _head_sha(root: Path) -> str:
    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


def _run_generator(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=cwd,
                          capture_output=True, text=True, timeout=60)


def _all_files(root: Path) -> set:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts}


def _headings(text: str):
    """[(уровень #, текст заголовка, позиция начала строки)]."""
    return [(len(m.group(1)), m.group(2), m.start()) for m in HEADING_RE.finditer(text)]


def _section(text: str, module_filename: str) -> str:
    """Срез секции модуля: от его заголовка до следующего заголовка того же
    уровня (или конца файла) — сама проверка того, что заголовки позволяют
    программно вырезать срез одного модуля (AC-6)."""
    headings = _headings(text)
    matches = [(lvl, pos) for lvl, htext, pos in headings if module_filename in htext]
    assert len(matches) == 1, (
        f"{module_filename}: ожидался ровно один заголовок-секция, "
        f"найдено {len(matches)}")
    level, start = matches[0]
    line_end = text.index("\n", start) + 1
    end = len(text)
    for lvl, _htext, pos in headings:
        if pos > start and lvl == level:
            end = pos
            break
    return text[line_end:end]


class CodebaseMapGeneratorTest(unittest.TestCase):
    """AC-1..AC-6, AC-8-смежное: поведение генератора на изолированной
    фикстуре дерева пульта (orchestrator/, scripts/, tests/)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        _build_fixture_repo(self.root)
        self.head_sha = _head_sha(self.root)
        self.files_before = _all_files(self.root)
        self.result = _run_generator(self.root)
        self.output_path = self.root / OUTPUT_REL
        self.text = (self.output_path.read_text(encoding="utf-8")
                    if self.output_path.exists() else "")

    def test_ac1_generator_creates_exactly_one_markdown_file(self):
        new_files = _all_files(self.root) - self.files_before

        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertTrue(self.output_path.is_file(),
                        f"{OUTPUT_REL} не создан; stderr: {self.result.stderr}")
        self.assertEqual(new_files, {OUTPUT_REL.as_posix()})

    def test_ac2_frontmatter_built_at_sha_matches_head(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        match = re.match(r"\A---\n(.*?)\n---\n", self.text, re.S)
        self.assertIsNotNone(match, "нет YAML frontmatter (--- ... ---)")
        front = match.group(1)
        sha_match = re.search(r"^built_at_sha:\s*(\S+)\s*$", front, re.M)
        self.assertIsNotNone(sha_match, f"поле built_at_sha не найдено:\n{front}")
        self.assertEqual(sha_match.group(1), self.head_sha)

    def test_ac3_one_section_per_top_level_module_without_recursion(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        for rel_path in FIXTURE_MODULES:
            filename = Path(rel_path).name
            count = sum(1 for _lvl, htext, _pos in _headings(self.text)
                       if filename in htext)
            self.assertEqual(count, 1, f"{rel_path}: секций найдено {count}")

        nested_name = Path(NESTED_MODULE).name
        count_nested = sum(1 for _lvl, htext, _pos in _headings(self.text)
                          if nested_name in htext)
        self.assertEqual(count_nested, 0,
                         "модуль вложенной директории не должен попасть в карту")

    def test_ac3_module_without_docstring_is_not_skipped(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        # beta.py — без docstring; критерий требует пометку, а не пропуск
        # модуля: секция обязана существовать (см. также test_ac3_one_section...).
        section = _section(self.text, "beta.py")
        self.assertIn(NO_DOCSTRING_MARK, section)

    def test_ac4_section_purpose_line_from_docstring_or_marker(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        for rel_path, (doc, _public, _private) in FIXTURE_MODULES.items():
            filename = Path(rel_path).name
            section = _section(self.text, filename)
            with self.subTest(модуль=rel_path):
                if doc is None:
                    self.assertIn(NO_DOCSTRING_MARK, section)
                else:
                    self.assertIn(doc, section)

    def test_ac4_section_lists_public_functions_not_private(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        for rel_path, (_doc, public, private) in FIXTURE_MODULES.items():
            filename = Path(rel_path).name
            section = _section(self.text, filename)
            with self.subTest(модуль=rel_path):
                for name in public:
                    self.assertIn(name, section, f"{name} не найдена в секции {rel_path}")
                for name in private:
                    self.assertNotIn(name, section,
                                    f"приватная {name} не должна попасть в секцию {rel_path}")

    def test_ac4_section_lists_import_relations_both_directions(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        alpha = _section(self.text, "alpha.py")
        beta = _section(self.text, "beta.py")
        tool = _section(self.text, "tool.py")
        test_something = _section(self.text, "test_something.py")

        # beta импортирует alpha -> у alpha есть импортирующий (beta),
        # у beta — импортируемый (alpha).
        self.assertIn("beta.py", alpha, "alpha: не назван импортирующий её модуль (beta)")
        self.assertIn("alpha.py", beta, "beta: не назван модуль, который она импортирует (alpha)")
        # tool импортирует beta -> симметрично.
        self.assertIn("tool.py", beta, "beta: не назван импортирующий её модуль (tool)")
        self.assertIn("beta.py", tool, "tool: не назван модуль, который она импортирует (beta)")
        # test_something импортирует tool -> симметрично.
        self.assertIn("test_something.py", tool,
                      "tool: не назван импортирующий её модуль (test_something)")
        self.assertIn("tool.py", test_something,
                      "test_something: не назван модуль, который она импортирует (tool)")
        # alpha ни с кем, кроме beta, не связана.
        self.assertNotIn("tool.py", alpha)
        self.assertNotIn("test_something.py", alpha)

    def test_ac5_repeated_run_without_changes_is_byte_identical(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        first_bytes = self.output_path.read_bytes()

        second = _run_generator(self.root)
        second_bytes = self.output_path.read_bytes()

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first_bytes, second_bytes)

    def test_ac6_module_headers_are_uniform_and_individually_sliceable(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        levels = set()
        for rel_path in FIXTURE_MODULES:
            filename = Path(rel_path).name
            matches = [lvl for lvl, htext, _pos in _headings(self.text)
                      if filename in htext]
            self.assertEqual(len(matches), 1)
            levels.add(matches[0])
        self.assertEqual(len(levels), 1,
                         f"заголовки секций модулей на разных уровнях: {levels}")

        # Срез одного модуля (`_section`, использованный выше во всех
        # AC-4-тестах) не должен содержать маркеры соседних модулей —
        # иначе резать «без разбора всего документа» было бы нельзя.
        alpha_section = _section(self.text, "alpha.py")
        self.assertNotIn("Tool script: does tool things.", alpha_section)
        self.assertNotIn("Tests for tool.", alpha_section)


class CiWorkflowTest(unittest.TestCase):
    """AC-7, AC-8: джоб CI, который запускает генератор после мержа в main."""

    JOB_HEADER_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$", re.M)
    GENERATOR_REF = "scripts/codebase_map.py"

    @classmethod
    def setUpClass(cls):
        cls.workflow_files = (sorted(WORKFLOWS_DIR.glob("*.yml"))
                             + sorted(WORKFLOWS_DIR.glob("*.yaml")))

    def _job_blocks(self, text: str) -> dict:
        headers = list(self.JOB_HEADER_RE.finditer(text))
        blocks = {}
        for i, m in enumerate(headers):
            start = m.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            blocks[m.group(1)] = text[start:end]
        return blocks

    def _find_generator_job(self):
        """(имя_файла, имя_джоба, текст_джоба, текст_всего_файла) — первый
        найденный джоб, чей блок ссылается на генератор."""
        for path in self.workflow_files:
            text = path.read_text(encoding="utf-8")
            for name, block in self._job_blocks(text).items():
                if self.GENERATOR_REF in block:
                    return path.name, name, block, text
        return None

    def test_ac7_ci_job_runs_generator_after_merge_to_main(self):
        found = self._find_generator_job()
        self.assertIsNotNone(
            found,
            f"ни один джоб в {WORKFLOWS_DIR} не запускает {self.GENERATOR_REF}")
        _file_name, _job_name, block, file_text = found

        job_scoped_to_main = re.search(r"if:\s*.*\bmain\b", block) is not None

        trigger_section = file_text.split("jobs:", 1)[0]
        branches_match = re.search(r"branches:\s*\[([^\]]*)\]", trigger_section)
        file_scoped_to_main_only = bool(
            branches_match and "main" in branches_match.group(1)
            and "task" not in branches_match.group(1))

        self.assertTrue(
            job_scoped_to_main or file_scoped_to_main_only,
            "джоб с генератором не ограничен веткой main ни условием `if:`, "
            "ни отдельным триггером `on: push: branches:`")

    def test_ac8_generator_failure_is_not_swallowed(self):
        found = self._find_generator_job()
        self.assertIsNotNone(
            found, f"ни один джоб в {WORKFLOWS_DIR} не запускает {self.GENERATOR_REF}")
        _file_name, _job_name, block, _file_text = found

        self.assertNotRegex(block, r"continue-on-error:\s*true",
                            "джоб глушит провал шага continue-on-error")
        self.assertNotIn("|| true", block,
                        "запуск генератора глушит ненулевой код возврата через || true")
        self.assertNotIn("|| exit 0", block,
                        "запуск генератора глушит ненулевой код возврата через || exit 0")

    def test_ac9_same_job_fails_when_mapped_modules_changed_after_built_at_sha(self):
        """AC-9 в редакции Оператора 25.08 (итерация 2, правка залоченного
        теста — право Оператора по A4): стухшая карта = изменения
        отображаемых модулей между built_at_sha и head; сравнение sha
        на равенство структурно невыполнимо — коммит, обновляющий карту,
        не может нести собственный sha (находка ревью, итерация 1)."""
        found = self._find_generator_job()
        self.assertIsNotNone(
            found, f"ни один джоб в {WORKFLOWS_DIR} не запускает {self.GENERATOR_REF}")
        _file_name, _job_name, block, _file_text = found

        self.assertIn(
            "built_at_sha", block,
            "джоб, запускающий генератор, не читает built_at_sha закоммиченной карты")

        diff_ref = re.search(r"git diff --name-only", block)
        self.assertIsNotNone(
            diff_ref,
            "джоб не диффует изменения от built_at_sha до head (git diff --name-only)")

        for mapped in ("orchestrator", "scripts", "tests"):
            self.assertIn(
                mapped, block,
                f"дифф сверки не ограничен отображаемыми модулями ({mapped})")

        fail_on_stale = re.search(r"exit\s+[1-9]\d*|sys\.exit\(\s*[1-9]", block)
        self.assertIsNotNone(
            fail_on_stale,
            "джоб не роняет себя (ненулевой exit) при стухшей карте")


if __name__ == "__main__":
    unittest.main()
