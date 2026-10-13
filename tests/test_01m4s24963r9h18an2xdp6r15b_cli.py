"""Командная строка генератора справочника ядра и тест-сторож настройки артели.

Группа: долгоживущий
Красен до реализации: файла scripts/core_reference.py ещё нет — запуск `python3 scripts/core_reference.py` кончается кодом 2 «can't open file», stdout пуст.

`python3 scripts/core_reference.py <корень> <модуль>... [--constants-module
… --constants …] [--min-uses N] [--sha …]` печатает справочник по файлам
диска в stdout. Набор файлов: в git-дереве — обычные `.py` из `git
ls-files`; без git — `.py` вне каталогов с ведущей точкой, `__pycache__`,
`node_modules`, `venv`. Разметку строк SPEC не фиксирует: запись функции
ищется по сигнатуре без учёта пробелов.

Тест-сторож гоняет командную строку по рабочему дереву репозитория с
настройкой артели из ТЗ К-3б, заданной в самом тесте; размер выдачи им не
сторожится. Принятый риск SPEC: сторож краснеет у задачи, переименовавшей
одно из шести имён, — её роль правит этот тест в рамках своего SPEC.
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import config
from tests.sandbox import RealGitSandbox

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "core_reference.py"

CORE = ('"""Ядро дерева."""\n\n\n'
        "def edge(v: int) -> int:\n"
        '    """Край дерева."""\n'
        "    return v\n\n\n"
        "def fewer(v: int) -> int:\n"
        '    """Реже порога."""\n'
        "    return v\n")
SETTINGS = '"""Значения дерева."""\n\nTREE_LIMIT = 8128  # предел дерева\n'
USER = "from lib import core\ncore.edge\n"
EDGE = "edge(v: int) -> int"


def squeeze(text: str) -> str:
    return "".join(text.split())


def has_signature(text: str, signature: str) -> bool:
    wanted = squeeze(signature)
    return any(wanted in squeeze(line) for line in text.split("\n"))


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def snapshot(root: Path) -> dict:
    """Путь -> sha256 содержимого всех файлов дерева, кроме `.git`."""
    found = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if ".git" in rel.parts or not path.is_file() or path.is_symlink():
            continue
        found[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def run_cli(root: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, str(SCRIPT), str(root), *args],
                          cwd=cwd, capture_output=True, text=True, env=env,
                          timeout=300)


class PlainTreeCliTest(unittest.TestCase):
    """AC-2: дерево без git — вывод в stdout, умолчание порога, исключённые каталоги."""

    def tree(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def test_ac2_prints_to_stdout_and_writes_nothing(self):
        """Справочник с константой и меткой `--sha` — в stdout; дерево и рабочий каталог не тронуты.

        Ловит мутацию: командная строка пишет справочник файлом (в корень
        дерева или в рабочий каталог процесса) вместо stdout, теряет
        `--sha` (метки нет в выводе) или не передаёт `--constants`
        (значения `8128` нет).
        """
        root, cwd = self.tree(), self.tree()
        files = {"lib/core.py": CORE, "conf/values.py": SETTINGS}
        files.update({f"use/u{i}.py": USER for i in range(3)})
        write(root, files)
        before = snapshot(root)
        res = run_cli(root, "lib/core.py", "conf/values.py",
                      "--constants-module", "conf/values.py",
                      "--constants", "TREE_LIMIT", "--sha", "метка-проверки",
                      cwd=cwd)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertTrue(has_signature(res.stdout, EDGE), res.stdout)
        self.assertIn("метка-проверки", res.stdout)
        self.assertTrue([line for line in res.stdout.split("\n")
                         if "TREE_LIMIT" in line and "8128" in line], res.stdout)
        self.assertEqual(before, snapshot(root), "командная строка изменила дерево")
        self.assertEqual([], sorted(p.name for p in cwd.iterdir()),
                         "командная строка записала файл в рабочий каталог")

    def test_ac2_default_min_uses_equals_config_threshold(self):
        """Без `--min-uses` порог — `config.CORE_REFERENCE_MIN_USES`; явный флаг его меняет.

        Число файлов-пользователей берётся от `config`, не литералом:
        `edge` используется ровно в пороговом числе файлов, `fewer` — на
        один меньше.

        Ловит мутацию: умолчание `--min-uses` разошлось с
        `config.CORE_REFERENCE_MIN_USES` (например, `2` — `fewer` войдёт
        без флага; `4` — `edge` пропадёт) или флаг не читается (`fewer` не
        войдёт при `--min-uses` на единицу ниже).
        """
        threshold = config.CORE_REFERENCE_MIN_USES
        root, cwd = self.tree(), self.tree()
        files = {"lib/core.py": CORE}
        files.update({f"use/e{i}.py": USER for i in range(threshold)})
        files.update({f"use/f{i}.py": "from lib import core\ncore.fewer\n"
                      for i in range(threshold - 1)})
        write(root, files)
        res = run_cli(root, "lib/core.py", cwd=cwd)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertTrue(has_signature(res.stdout, EDGE), res.stdout)
        self.assertNotIn("fewer(", res.stdout)
        res = run_cli(root, "lib/core.py", "--min-uses", str(threshold - 1), cwd=cwd)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertTrue(has_signature(res.stdout, "fewer(v: int) -> int"), res.stdout)

    def test_ac2_without_git_skips_dot_cache_vendor_and_venv_directories(self):
        """Без git третий пользователь `edge` в исключённом каталоге в подсчёт не входит.

        Два пользователя `edge` лежат в обычных каталогах, третий — в
        одном из исключённых (`.hidden`, вложенный `pkg/.dot`,
        `__pycache__`, `node_modules`, `venv`): `edge` ниже порога. Третий
        пользователь в обычном `pkg/` — контроль: `edge` входит.

        Ловит мутацию: обход `rglob("*.py")` без фильтра каталогов (или
        фильтр без одного из имён, или только верхнего уровня) — `edge`
        войдёт в справочник по файлу исключённого каталога.
        """
        cases = (".hidden", "pkg/.dot", "__pycache__", "node_modules", "venv")
        for excluded in cases + ("pkg",):
            with self.subTest(directory=excluded):
                root, cwd = self.tree(), self.tree()
                write(root, {"lib/core.py": CORE, "use/u0.py": USER,
                             "use/u1.py": USER, f"{excluded}/u2.py": USER})
                res = run_cli(root, "lib/core.py", "--min-uses", "3", cwd=cwd)
                self.assertEqual(0, res.returncode, res.stderr)
                found = has_signature(res.stdout, EDGE)
                self.assertEqual(excluded == "pkg", found, res.stdout)


class GitTreeCliTest(RealGitSandbox):
    """AC-2: git-дерево — в разбор только обычные `.py` из `git ls-files`.

    Песочница — настоящий git-репозиторий (`RealGitSandbox`): связка
    «командная строка — индекс git» иначе не воспроизводится.
    """

    def test_ac2_git_tree_reads_only_tracked_regular_py_files(self):
        """Третий пользователь `edge` вне индекса или символьной ссылкой в подсчёт не входит.

        В индексе — модуль и два пользователя `edge`. Третий: файл вне
        индекса; символьная ссылка в индексе на неотслеживаемый файл с
        обращением к `core.edge`; контроль — обычный отслеживаемый файл.

        Ловит мутацию: в git-дереве обход диска вместо `git ls-files`
        (файл вне индекса войдёт) или чтение по символьной ссылке (её
        цель войдёт) — `edge` появится в справочнике.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cwd = Path(tmp.name)
        write(self.root, {"lib/core.py": CORE, "use/u0.py": USER, "use/u1.py": USER})
        self.git("add", "lib/core.py", "use/u0.py", "use/u1.py")
        self.git("commit", "-q", "-m", "дерево")

        def edge_listed() -> bool:
            res = run_cli(self.root, "lib/core.py", "--min-uses", "3", cwd=cwd)
            self.assertEqual(0, res.returncode, res.stderr)
            return has_signature(res.stdout, EDGE)

        with self.subTest(case="файл вне индекса"):
            write(self.root, {"use/u2.py": USER})
            self.assertFalse(edge_listed())
            (self.root / "use" / "u2.py").unlink()
        with self.subTest(case="символьная ссылка в индексе"):
            write(self.root, {"hidden_src/u9.py": USER})
            (self.root / "use" / "u2.py").symlink_to(self.root / "hidden_src" / "u9.py")
            self.git("add", "use/u2.py")
            self.assertFalse(edge_listed())
            self.git("rm", "-q", "--cached", "use/u2.py")
            (self.root / "use" / "u2.py").unlink()
        with self.subTest(case="обычный отслеживаемый файл"):
            write(self.root, {"use/u2.py": USER})
            self.git("add", "use/u2.py")
            self.assertTrue(edge_listed())


class ArtelSettingSentinelTest(unittest.TestCase):
    """AC-14: настройка артели из ТЗ К-3б выдаёт шесть часто искомых имён."""

    MODULES = ("orchestrator/store.py", "tests/sandbox.py", "orchestrator/gitcmd.py",
               "orchestrator/config.py", "orchestrator/runner.py",
               "orchestrator/fsm.py")
    CONSTANTS = ("PROTECTED_PATHS", "COMMON_ZONES", "STATE_ROLE", "DEFAULT_TARGET")

    def test_ac14_artel_setting_yields_frequently_searched_names(self):
        """По рабочему дереву репозитория выдаются `journal`, `set_state` и четыре константы.

        Константа считается выданной, если кроме строки шапки с перечнем
        есть строка записи с её именем и ни одна строка с её именем не
        говорит «нет в коммите».

        Ловит мутацию: порог считает обращения внутри собственного модуля
        или только `from … import` (функции `journal`/`set_state` зовутся
        как `store.journal(...)` — пропадут), константы ищутся не в модуле
        констант настройки (все четыре — «нет в коммите») или обход
        дерева теряет `tests/` и `orchestrator/` (пропадут пользователи).
        """
        with tempfile.TemporaryDirectory() as cwd:
            res = run_cli(REPO, *self.MODULES,
                          "--constants-module", "orchestrator/config.py",
                          "--constants", *self.CONSTANTS, cwd=Path(cwd))
        self.assertEqual(0, res.returncode, res.stderr)
        out = res.stdout
        for name in ("journal", "set_state"):
            with self.subTest(name=name):
                self.assertRegex(out, rf"(?<!\w){name}\(")
        for name in self.CONSTANTS:
            with self.subTest(name=name):
                rows = [line for line in out.split("\n")
                        if re.search(rf"\b{name}\b", line)]
                self.assertGreaterEqual(len(rows), 2, out[:4000])
                self.assertFalse([line for line in rows if "нет в коммите" in line])


if __name__ == "__main__":
    unittest.main()
