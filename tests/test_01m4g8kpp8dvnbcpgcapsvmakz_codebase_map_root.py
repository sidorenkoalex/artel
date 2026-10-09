"""Генератор карты кода пишет карту в дерево самого сценария, не текущего каталога.

Группа: долгоживущий
Красен до реализации: `scripts/codebase_map.py::main` берёт корень от текущего каталога (`repo_root(Path.cwd())`) — карта ложится в чужое дерево, где запущен сценарий, а в дереве сценария её нет.

Сценарий копируется в отдельное временное git-дерево (рядом с ним —
модуль `orchestrator/<случайное имя>.py`), запускается отдельным
процессом `python3 <дерево>/scripts/codebase_map.py` из подкаталога
случайной глубины другого репозитория — песочницы `RealGitSandbox`, где
лежит свой, другой случайный модуль. Проверяется только наблюдаемое:
файл карты в дереве сценария, его содержимое (модули этого дерева, не
чужого) и `git status` чужого репозитория до и после вызова. Имена
порождаются `random` при каждом запуске; зерно печатается и входит в
текст каждого провала.
"""
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from orchestrator import config
from scripts import codebase_map
from tests.sandbox import RealGitSandbox

LETTERS = "abcdefghijklmnopqrstuvwxyz"


class CodebaseMapScriptRootTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = time.time_ns()
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def token(self) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(10))

    def commit_all(self, tree: Path) -> None:
        self.git("-C", str(tree), "add", "-A")
        self.git("-C", str(tree), "-c", "user.name=artel tests",
                 "-c", "user.email=artel@example.invalid",
                 "commit", "-q", "-m", "посев")

    def script_tree(self) -> tuple:
        """Отдельное git-дерево с копией генератора и одним модулем."""
        tree = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, tree, ignore_errors=True)
        self.git("-C", str(tree), "init", "-q", "-b", config.MAIN_BRANCH)
        script = tree / "scripts" / "codebase_map.py"
        script.parent.mkdir(parents=True)
        shutil.copyfile(Path(codebase_map.__file__).resolve(), script)
        module = f"mod_{self.token()}"
        (tree / "orchestrator").mkdir()
        (tree / "orchestrator" / f"{module}.py").write_text(
            f'"""Модуль дерева сценария {module}."""\n', encoding="utf-8")
        self.commit_all(tree)
        return tree, script, module

    def test_ac1_map_lands_in_script_tree_not_in_cwd_tree(self):
        """Сценарий одного дерева запущен из подкаталога другого репозитория.

        Чужой репозиторий (песочница) несёт свой модуль
        `orchestrator/<имя>.py` и подкаталог случайной глубины с
        отслеживаемым файлом — оттуда, как из каталога документов задачи
        внутри главной копии, и запускается сценарий другого дерева. На
        нескольких случайных деревьях: процесс завершается кодом 0;
        `docs/codebase-map.md` появляется в дереве сценария и называет его
        модуль, но не модуль чужого дерева; в чужом репозитории карты нет,
        и его `git status --porcelain` тот же, что до вызова.

        Ловит мутацию: `main` по-прежнему зовёт `repo_root(Path.cwd())`
        (или берёт корень от `Path.cwd()` любым другим способом) — карта
        ляжет в чужой репозиторий (`git status` покажет неотслеживаемый
        `docs/`), а в дереве сценария файла карты не будет.
        """
        foreign_module = f"mod_{self.token()}"
        (self.root / "orchestrator").mkdir()
        (self.root / "orchestrator" / f"{foreign_module}.py").write_text(
            f'"""Модуль чужого дерева {foreign_module}."""\n', encoding="utf-8")
        cwd = self.root.joinpath(*(f"d_{self.token()}"
                                   for _ in range(self.rng.randint(1, 3))))
        cwd.mkdir(parents=True)
        (cwd / "note.txt").write_text("подкаталог\n", encoding="utf-8")
        self.commit_all(self.root)

        for _ in range(2):
            tree, script, module = self.script_tree()
            status_before = self.git("status", "--porcelain")
            with self.subTest(tree=str(tree), cwd=str(cwd)):
                res = subprocess.run([sys.executable, str(script)], cwd=cwd,
                                     capture_output=True, text=True,
                                     timeout=60)
                self.assertEqual(
                    res.returncode, 0,
                    f"зерно {self.seed}: генератор упал: {res.stderr}")
                out = tree / "docs" / "codebase-map.md"
                self.assertTrue(
                    out.is_file(),
                    f"зерно {self.seed}: карты нет в дереве сценария {tree}")
                text = out.read_text(encoding="utf-8")
                self.assertIn(f"orchestrator/{module}.py", text,
                              f"зерно {self.seed}: карта не того дерева")
                self.assertNotIn(foreign_module, text,
                                 f"зерно {self.seed}: в карте модуль "
                                 f"дерева текущего каталога")
                self.assertFalse(
                    (self.root / "docs" / "codebase-map.md").exists(),
                    f"зерно {self.seed}: карта записана в дерево текущего "
                    f"каталога")
                self.assertEqual(
                    self.git("status", "--porcelain"), status_before,
                    f"зерно {self.seed}: дерево текущего каталога изменилось")


if __name__ == "__main__":
    unittest.main()
