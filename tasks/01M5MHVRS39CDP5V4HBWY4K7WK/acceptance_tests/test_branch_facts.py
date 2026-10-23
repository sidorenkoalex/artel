"""Факты ветки задачи: докстринги команд, новый файл tests/, нетронутость lease.py/answer.py/tests/.

Группа: разовый
Красен до реализации: докстринги cmd_reject/cmd_workspace/cmd_ci_rerun/cmd_run ещё несут «ЗДЕСЬ» и не называют run_task_command, нового файла tests/ с линтером (в) в ветке нет; AC-9 на пустом диффе зелен.

База сравнения — `DIFF_BASE` помощника пульта (точка расхождения ветки с
`origin/main`, тот же расчёт, что гейт зон).
"""
import ast
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

PHRASE = ("Ловит мутацию: в команде возвращена своя копия обвязки или "
          "потерян `session_id`")
BODIES = ("_cmd_spec_audit", "_cmd_reject", "_cmd_pull_main", "_cmd_workspace",
          "_cmd_ci_rerun", "_cmd_run", "_cmd_zones_extend")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", CODE_ROOT, *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def base_text(rel: str) -> str:
    res = git("show", f"{DIFF_BASE}:{rel}")
    if res.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{rel}: {res.stderr.strip()}")
    return res.stdout


def head_text(rel: str) -> str:
    return (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")


def exists_at_base(rel: str) -> bool:
    return git("cat-file", "-e", f"{DIFF_BASE}:{rel}").returncode == 0


def top_function(source: str, name: str) -> ast.FunctionDef | None:
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def squash(text: str) -> str:
    return " ".join(text.split())


def new_test_files() -> list[str]:
    """Файлы `tests/`, которых нет в базе: добавленные коммитами ветки и
    неотслеживаемые (правило гейта зон — `changed_paths`)."""
    return sorted(p for p in changed_paths()
                  if p.startswith("tests/") and p.endswith(".py")
                  and not exists_at_base(p)
                  and (Path(CODE_ROOT) / p).is_file())


class DocstringsTest(unittest.TestCase):

    def test_ac7_docstrings_point_to_run_task_command_others_unchanged(self):
        """Четыре докстринга называют `run_task_command` без «ЗДЕСЬ», три прежние.

        Из текущих файлов рабочей копии разбирается AST: докстринги
        `fsm.cmd_reject`, `workspace.cmd_workspace`, `ci_rerun.cmd_ci_rerun`,
        `runner.cmd_run` не содержат «ЗДЕСЬ» и содержат `run_task_command`;
        докстринги `fsm.cmd_spec_audit`, `pull_main.cmd_pull_main`,
        `answer.cmd_zones_extend` побайтно равны докстрингам базы ветки.
        Ловит мутацию: разработчик оставил «ЗДЕСЬ» в одном из четырёх
        докстрингов (не перенёс утверждение о порядке на
        `lease.run_task_command`) либо заодно переписал докстринг
        `cmd_zones_extend`, который решение Оператора велело не трогать.
        """
        for rel, name in (("orchestrator/fsm.py", "cmd_reject"),
                          ("orchestrator/workspace.py", "cmd_workspace"),
                          ("orchestrator/ci_rerun.py", "cmd_ci_rerun"),
                          ("orchestrator/runner.py", "cmd_run")):
            with self.subTest(command=name):
                func = top_function(head_text(rel), name)
                self.assertIsNotNone(func, f"{rel}: нет {name}")
                doc = ast.get_docstring(func, clean=False) or ""
                self.assertNotIn("ЗДЕСЬ", doc, f"{name}: «ЗДЕСЬ» в докстринге")
                self.assertIn("run_task_command", doc,
                              f"{name}: докстринг не называет run_task_command")
        for rel, name in (("orchestrator/fsm.py", "cmd_spec_audit"),
                          ("orchestrator/pull_main.py", "cmd_pull_main"),
                          ("orchestrator/answer.py", "cmd_zones_extend")):
            with self.subTest(command=name):
                head = top_function(head_text(rel), name)
                base = top_function(base_text(rel), name)
                self.assertIsNotNone(head, f"{rel}: нет {name}")
                self.assertIsNotNone(base, f"{rel} базы: нет {name}")
                self.assertEqual(ast.get_docstring(head, clean=False),
                                 ast.get_docstring(base, clean=False),
                                 f"{name}: докстринг изменён относительно main")


class NewTestFileTest(unittest.TestCase):

    def dev_files(self) -> list[str]:
        return [p for p in new_test_files()
                if PHRASE in squash(head_text(p))]

    def test_ac8_new_tests_file_has_checks_and_is_red_on_base(self):
        """В `tests/` добавлен файл с проверками (а)–(г); на коде базы он красен.

        Среди файлов `tests/`, которых нет в базе, ищется файл, где у
        тестового метода в докстринге есть строка «Ловит мутацию: в команде
        возвращена своя копия обвязки или потерян `session_id`» (линтер (в)).
        В том же файле есть обращения к `run_task_command` и `run_locked`
        (а), `SystemExit` (б), `patch.object` тел всех семи `_cmd_*` (г).
        Затем файл кладётся в выгрузку дерева базы ветки (`git archive`) и
        прогоняется pytest: прогон красный, упавших проверок не меньше трёх
        (а, б, в) либо модуль не собирается без `run_task_command`.
        Ловит мутацию: файла нет или линтер без заявленной строки мутации;
        проверки (г) покрывают не все семь команд; проверки написаны так,
        что зелены и на коде до изменения (не ловят возврат копии обвязки).
        """
        files = self.dev_files()
        self.assertTrue(files, "в tests/ нет нового файла с линтером (в) — "
                               f"новые файлы tests/: {new_test_files()}")
        rel = files[0]
        text = head_text(rel)
        tree = ast.parse(text)
        linter = [n.name for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name.startswith("test")
                  and PHRASE in squash(ast.get_docstring(n) or "")]
        self.assertTrue(linter, f"{rel}: строка мутации (в) не в докстринге "
                                f"тестового метода")
        for needle in ("run_task_command", "run_locked", "SystemExit",
                       "patch.object"):
            self.assertIn(needle, text, f"{rel}: нет {needle}")
        for body in BODIES:
            self.assertIn(body, text, f"{rel}: проверка (г) не называет {body}")

        with tempfile.TemporaryDirectory(prefix="ac8-base-") as tmp:
            archive = Path(tmp) / "base.tar"
            res = git("archive", "--format=tar", "-o", str(archive), DIFF_BASE)
            self.assertEqual(res.returncode, 0, res.stderr)
            tree_dir = Path(tmp) / "tree"
            with tarfile.open(archive) as tar:
                tar.extractall(tree_dir, filter="data")
            target = tree_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            run = subprocess.run(
                [sys.executable, "-m", "pytest", rel, "-q",
                 "-p", "no:cacheprovider", "-p", "timeout", "-o", "timeout=60"],
                cwd=tree_dir, capture_output=True, text=True, timeout=100)
        out = run.stdout + run.stderr
        self.assertIn(run.returncode, (1, 2),
                      f"{rel} на коде базы не красен (код {run.returncode}):\n"
                      f"{out[-3000:]}")
        if run.returncode == 1:
            failed = re.search(r"(\d+) failed", out)
            self.assertTrue(failed and int(failed.group(1)) >= 3,
                            f"{rel} на коде базы: упало меньше трёх проверок:\n"
                            f"{out[-3000:]}")


class UntouchedTest(unittest.TestCase):

    def test_ac9_existing_tests_lease_and_answer_untouched(self):
        """Существующие `tests/`, функции `lease.py` и прочее `answer.py` не тронуты.

        По закоммиченному диффу ветки от базы (`--no-renames`) каждый путь
        под `tests/` — добавленный (статус A). Каждая функция верхнего уровня
        `orchestrator/lease.py` базы есть в рабочей копии с тем же текстом.
        В `orchestrator/answer.py` все операторы верхнего уровня, кроме
        `cmd_zones_extend` и импортов, совпадают с базой по тексту и порядку;
        импорты рабочей копии — подмножество импортов базы.
        Ловит мутацию: разработчик подправил существующий тест под новую
        обвязку (`tests/test_workspace.py` — статус M), «заодно» поменял
        `run_locked` (например, умолчание `on_refusal`) либо перевёл на
        `run_task_command` ещё и `cmd_answer` в `answer.py`.
        """
        diff = git("diff", "--name-status", "--no-renames", DIFF_BASE, "HEAD",
                   "--", "tests/")
        self.assertEqual(diff.returncode, 0, diff.stderr)
        for line in diff.stdout.splitlines():
            status, _, path = line.partition("\t")
            with self.subTest(path=path):
                self.assertEqual(status, "A", f"{path}: существующий файл tests/ "
                                              f"изменён ({status})")

        rel = "orchestrator/lease.py"
        base_src, head_src = base_text(rel), head_text(rel)
        head_funcs = {n.name: ast.get_source_segment(head_src, n)
                      for n in ast.parse(head_src).body
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for node in ast.parse(base_src).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                with self.subTest(function=f"lease.{node.name}"):
                    self.assertEqual(head_funcs.get(node.name),
                                     ast.get_source_segment(base_src, node),
                                     f"lease.{node.name} изменена")

        rel = "orchestrator/answer.py"
        base_src, head_src = base_text(rel), head_text(rel)

        def split(src):
            imports, others = set(), []
            for node in ast.parse(src).body:
                if isinstance(node, ast.Import):
                    imports |= {(None, a.name, a.asname) for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    imports |= {((node.level, node.module), a.name, a.asname)
                                for a in node.names}
                elif not (isinstance(node, ast.FunctionDef)
                          and node.name == "cmd_zones_extend"):
                    others.append(ast.get_source_segment(src, node))
            return imports, others

        base_imports, base_others = split(base_src)
        head_imports, head_others = split(head_src)
        self.assertLessEqual(head_imports, base_imports,
                             f"answer.py: новые импорты {head_imports - base_imports}")
        self.assertEqual(head_others, base_others,
                         "answer.py: изменено что-то кроме cmd_zones_extend")


if __name__ == "__main__":
    unittest.main()
