"""Команда `suite-run`: прогон ветки задачи артели на временном дереве
«рабочая копия задачи (с незакоммиченными правками) плюс приложения PLAN»;
прогон базы — без приложений задачи.

Группа: долгоживущий
Красен до реализации: прогон ветки suite-run идёт в рабочей копии задачи без приложений PLAN (а до подтяжки main команды suite-run в диспетчере копии пульта нет вовсе — «Неизвестная команда»), тест-проба красен, отказа на неприменимом приложении и сбое git нет, признака «с приложениями PLAN» в отчёте нет. Валидация стабом невозможна: команда suite-run — предмет задачи-зависимости мержа, её кода в дереве ещё нет. test_ac9 и test_ac11 держат поведение самой команды без приложений.

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`, клон
артели — сам репозиторий песочницы) и КОПИЯ кода пульта (`orchestrator/`,
`scripts/`) в её корне: `config.ROOT` считается от расположения
`config.py`, поэтому команда, вызванная подпроцессом из копии, и её
фоновый процесс видят пути песочницы (БД, логи, `targets.yaml`, область
проектов). В конец `config.py` копии дописана параллель 1; в конец
`acceptance.py` копии — наблюдатель публичного узла `run_full_suite`
(корень вызова) и бросок исключения по файлу-флагу.

Профиль тестов артели в `targets.yaml` песочницы — `[<интерпретатор>, -m,
pytest]`. Ветка задачи несёт тест-пробу `tests/test_probe_*.py`, красный,
пока в защищённых файлах дерева прогона нет правок приложений PLAN; он
пишет в журнал наблюдения корень, cwd и исход. Сбой git — обёртка `git`
первой в `PATH` команды (ненулевой код на `git apply` либо `git worktree
add`). `TMPDIR` команды — каталог наблюдения: после прогона в нём пусто.
Команда зовётся подпроцессом в своей группе процессов без `ARTEL_ROLE`;
отчёт забирается `suite-run <id> --wait 1`.
"""
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from orchestrator import acceptance, catalog, checkpoint, config, idgen, store, workspace
from tests.sandbox import RealGitSandbox, capture, make_project_repo

CODE_ROOT = Path(acceptance.__file__).resolve().parent.parent
STILL_RUNNING = "ещё идёт"
WITH_APPENDICES = "с приложениями plan"

# Защищённые markdown-файлы — от `config.PROTECTED_PATHS`, не литералом.
PROTECTED_FILES = [p for p in config.PROTECTED_PATHS
                   if p.endswith(".md") and "*" not in p
                   and not p.startswith(("tests/", ".github"))]

ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [{python}, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

BASE_LINES = [f"строка базы {n:02d} из 40" for n in range(1, 41)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
EDIT_LINES = BASE_LINES[::8]

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/
---

# SPEC: фикстура

## Контекст

## Требования

## Критерии приёмки

AC-1. Фикстура.

## Не входит
"""

PROBE = '''import json
import os
from pathlib import Path


def test_{name}():
    root = Path(__file__).resolve().parent.parent
    present = all(marker in (root / rel).read_text(encoding="utf-8")
                  for rel, marker in {needs!r})
    with open({journal!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"name": {name!r},
                             "root": os.path.realpath(str(root)),
                             "cwd": os.path.realpath(os.getcwd()),
                             "present": present}}) + "\\n")
    assert present, "правок приложений PLAN в дереве прогона нет"
'''

PASSING = "def test_{name}():\n    assert True\n"
FAILING = "def test_{name}():\n    raise ValueError({message!r})\n"

NODE_PROBE = '''

# Песочница теста suite-run с приложениями: наблюдатель узла полного прогона.
import json as probe_json
import os as probe_os

probe_original_run_full_suite = run_full_suite


def run_full_suite(root, *args, **kwargs):
    with open({path!r}, "a", encoding="utf-8") as fh:
        fh.write(probe_json.dumps({{
            "root": probe_os.path.realpath(str(root)),
            "pid": probe_os.getpid()}}) + "\\n")
    if probe_os.path.exists({flag!r}):
        raise RuntimeError("сбой прогона песочницы")
    return probe_original_run_full_suite(root, *args, **kwargs)
'''

GIT_WRAPPER = '''#!{python}
import os, sys
args = sys.argv[1:]
rest = list(args)
while rest and rest[0] in ("-C", "-c", "--git-dir", "--work-tree"):
    rest = rest[2:]
mode = ""
if os.path.exists({mode_file!r}):
    with open({mode_file!r}, encoding="utf-8") as fh:
        mode = fh.read().strip()
words = " ".join(rest[:2])
if mode and (words == mode or (mode == "apply" and rest[:1] == ["apply"])):
    with open({log_file!r}, "a", encoding="utf-8") as fh:
        fh.write(" ".join(args) + "\\n")
    sys.stderr.write("fatal: сбой git песочницы\\n")
    sys.exit(128)
os.execv({git!r}, [{git!r}, *args])
'''


def names_number(text: str, number: int) -> bool:
    """Текст называет номер приложения рядом со словом «приложение»."""
    return re.search(rf"приложени\w*\s*(№\s*)?{number}\b", text,
                     re.IGNORECASE) is not None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class SuiteRunAppendixSandbox(RealGitSandbox):
    """Копия пульта, профиль тестов артели, задачи артели с рабочими
    копиями и PLAN с приложениями в ссылке документов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.case = ""
        self.assertGreaterEqual(len(PROTECTED_FILES), 2,
                                "в config.PROTECTED_PATHS нет двух "
                                "защищённых markdown-файлов")
        self.files = self.rng.sample(PROTECTED_FILES, 2)

        self.probe = Path(tempfile.mkdtemp(prefix="artel-suite-appendix-")).resolve()
        self.addCleanup(self.stop_everything)
        self.journal_file = self.probe / "probe.jsonl"
        self.node_file = self.probe / "node.jsonl"
        self.raise_flag = self.probe / "raise"
        self.mode_file = self.probe / "git-mode"
        self.git_log = self.probe / "git-failures.log"
        self.tmp_dir = self.probe / "tmp"
        self.tmp_dir.mkdir()
        self.bin_dir = self.probe / "bin"
        self.bin_dir.mkdir()
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git, "git не найден в PATH")
        wrapper = self.bin_dir / "git"
        wrapper.write_text(GIT_WRAPPER.format(
            python=sys.executable, mode_file=str(self.mode_file),
            log_file=str(self.git_log), git=real_git), encoding="utf-8")
        wrapper.chmod(0o755)

        for name in ("orchestrator", "scripts"):
            shutil.copytree(CODE_ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        with open(self.root / ".git" / "info" / "exclude", "a",
                  encoding="utf-8") as fh:
            fh.write("/orchestrator/\n/scripts/\n/targets.yaml\n")
        with open(self.root / "orchestrator" / "config.py", "a",
                  encoding="utf-8") as fh:
            fh.write("\n\n# Песочница теста suite-run с приложениями.\n"
                     "FULL_SUITE_WORKERS = '1'\n")
        with open(self.root / "orchestrator" / "acceptance.py", "a",
                  encoding="utf-8") as fh:
            fh.write(NODE_PROBE.format(path=str(self.node_file),
                                       flag=str(self.raise_flag)))

        self.entries = {config.DEFAULT_TARGET: ENTRY.format(
            name=config.DEFAULT_TARGET, url=f"http://localhost/{config.DEFAULT_TARGET}",
            base=config.MAIN_BRANCH, python=sys.executable)}
        self.write_targets()
        for rel in self.files:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(BASE_TEXT, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", "защищённые файлы-фикстуры")
        self.origin = self.add_synced_origin()
        capture(catalog.cmd_init)
        self.write_targets()

    # --- фикстуры ---------------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed}; {self.case or 'сценарий'})"

    def word(self) -> str:
        return "".join(self.rng.choice("abcdefghijkmnpqrstuvwxyz")
                       for _ in range(8))

    def write_targets(self) -> None:
        text = "targets:\n" + "".join(self.entries.values())
        for path in {Path(config.TARGETS), self.root / "targets.yaml"}:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit_on_main(self, files: dict) -> None:
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", "база: тесты")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

    def probe_source(self, name: str, needs: list) -> str:
        return PROBE.format(name=name, needs=needs,
                            journal=str(self.journal_file))

    def make_task(self, needs: list, target: str = None,
                  committed: dict = None, uncommitted: dict = None) -> None:
        """Задача проекта `target` (по умолчанию — артели) в `in_dev` с
        рабочей копией: тест-проба, которому нужны правки `needs`, и
        файлы `committed` — коммитом ветки, `uncommitted` — правкой рабочего
        дерева без коммита."""
        self.target = target or config.DEFAULT_TARGET
        self.task = idgen.new_task_id()
        self.branch = f"task/{self.task.lower()}-x"
        store.insert_task(store.db(), self.task, f"Задача {self.task}",
                          "in_dev", self.branch, self.target,
                          config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(self.task, self.branch, self.target)
        self.assertIsNone(error, f"рабочая копия не заведена: {error}")
        self.wt = Path(wt).resolve()
        self.probe_name = f"probe_{self.word()}"
        files = {f"tests/test_{self.probe_name}.py":
                 self.probe_source(self.probe_name, needs)}
        files.update(committed or {})
        self.write_wt(files)
        self.git("-C", str(self.wt), "add", "-A")
        self.git("-C", str(self.wt), "commit", "-q", "-m",
                 f"{self.task}: код задачи")
        self.write_wt(uncommitted or {})

    def write_wt(self, files: dict) -> None:
        for rel, text in files.items():
            path = self.wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def edit(self, rel: str, replacements: dict) -> None:
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            self.assertIn(old, text)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    def diff_chain(self, edits: list) -> list:
        diffs = []
        for edit in edits:
            self.git("add", "-A", "--", *self.files)
            for rel, replacements in edit.items():
                self.edit(rel, replacements)
            diff = self.git("diff", "--", *edit)
            self.assertIn("diff --git a/", diff)
            diffs.append(diff)
        self.git("reset", "-q", "--", *self.files)
        self.git("checkout", "-q", "--", *self.files)
        return diffs

    def chained_edits(self, count: int) -> tuple:
        rel = self.files[0]
        current, edits = self.rng.choice(EDIT_LINES), []
        for i in range(count):
            marker = f"правка {i + 1} ({self.rng.randrange(10**6)})"
            edits.append({rel: {current: marker}})
            current = marker
        return self.diff_chain(edits), [(rel, current)]

    def independent_edits(self, count: int) -> tuple:
        diffs, needs = [], []
        for line in self.rng.sample(EDIT_LINES, count):
            rel = self.rng.choice(self.files)
            marker = f"правка ({self.rng.randrange(10**6)})"
            diffs.extend(self.diff_chain([{rel: {line: marker}}]))
            needs.append((rel, marker))
        return diffs, needs

    def inapplicable_scenario(self) -> tuple:
        good = []
        for line in self.rng.sample(EDIT_LINES, self.rng.randint(1, 2)):
            marker = f"правка ({self.rng.randrange(10**6)})"
            good.extend(self.diff_chain([{self.files[1]: {line: marker}}]))
        bad = self.chained_edits(2)[0][1]
        index = self.rng.randrange(len(good) + 1)
        return good[:index] + [bad] + good[index:], index + 1, self.files[0]

    def write_docs(self, diffs: list) -> None:
        sections = "".join(
            f"\n## Приложение {i}: правка {self.rng.randrange(10**6)}\n\n"
            f"```diff\n{diff}```\n" for i, diff in enumerate(diffs, 1))
        plan = (f"---\ntask: {self.task}\ntype: plan\n"
                f"author_role: developer\nstatus: draft\n"
                f"schema_version: 2\n---\n\n# PLAN\n\n## Подход\n\n"
                f"Фикстура.\n{sections}")
        docs = config.PROJECTS / self.target / "tasks" / self.task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=self.task),
                                      encoding="utf-8")
        (docs / "PLAN.md").write_text(plan, encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, store.db(), self.task,
                "developer")

    # --- команда ------------------------------------------------------------

    def cli(self, *args: str, timeout: float = 100) -> tuple:
        """(код выхода, вывод) `artel.py <args>` копии пульта из рабочей
        копии задачи."""
        env = {k: v for k, v in os.environ.items()
               if k != config.ARTEL_ROLE_ENV}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["TMPDIR"] = str(self.tmp_dir)
        env["PATH"] = f"{self.bin_dir}{os.pathsep}{env.get('PATH', '')}"
        proc = subprocess.Popen(
            [sys.executable, str(self.root / "orchestrator" / "artel.py"),
             *args], cwd=str(self.wt), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            raw, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.kill_group(proc.pid)
            proc.communicate()
            self.fail(self.note(f"artel.py {' '.join(args)} не вернулся за "
                                f"{timeout} с"))
        finally:
            self.kill_group(proc.pid)
        return proc.returncode, raw.decode("utf-8", errors="replace")

    @staticmethod
    def kill_group(pgid: int) -> None:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def run_suite(self) -> tuple:
        """`suite-run <id>` и `suite-run <id> --wait 1`: (код запуска, код
        ожидания, общий вывод). Ожидание повторяется, пока прогон идёт."""
        code, out = self.cli("suite-run", self.task)
        wait_code, wait_out = self.cli("suite-run", self.task, "--wait", "1")
        for _ in range(3):
            if STILL_RUNNING not in wait_out:
                break
            wait_code, wait_out = self.cli("suite-run", self.task,
                                           "--wait", "1")
        self.assertNotIn(STILL_RUNNING, wait_out,
                         self.note(f"прогон не завершился:\n{wait_out}"))
        self.settle()
        return code, wait_code, f"{out}\n--- --wait:\n{wait_out}"

    def settle(self, timeout: float = 30) -> None:
        """Ждёт конца фоновых процессов прогона (pid из наблюдателя узла)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not any(pid_alive(n["pid"]) for n in self.nodes()):
                return
            time.sleep(0.2)

    # --- наблюдение ---------------------------------------------------------

    @staticmethod
    def read_jsonl(path: Path) -> list:
        if not path.exists():
            return []
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def probe_records(self) -> list:
        return self.read_jsonl(self.journal_file)

    def nodes(self) -> list:
        return self.read_jsonl(self.node_file)

    def branch_records(self) -> list:
        """Исполнения пробы задачи (прогон ветки), без прогона базы: у базы
        пробы ветки нет."""
        return [r for r in self.probe_records() if r["name"] == self.probe_name]

    def context(self, out: str) -> str:
        return self.note(f"вывод suite-run:\n{out[-4000:]}\n--- узел: "
                         f"{self.nodes()}\n--- проба: {self.probe_records()}"
                         f"\n--- рабочая копия: {self.wt}")

    def reset_observation(self) -> None:
        for path in (self.journal_file, self.node_file, self.git_log):
            path.unlink(missing_ok=True)

    def leftovers(self) -> list:
        """Содержимое `TMPDIR` команды без базового каталога самого pytest
        (`pytest-of-<пользователь>`): его pytest оставляет намеренно, это не
        дерево прогона."""
        return sorted(p.name for p in self.tmp_dir.iterdir()
                      if not p.name.startswith("pytest-of-"))

    def wt_snapshot(self) -> dict:
        wt = ("-C", str(self.wt))
        return {"status": self.git(*wt, "status", "--porcelain",
                                   "--untracked-files=all"),
                "index": self.git(*wt, "ls-files", "--stage"),
                "head": self.git(*wt, "rev-parse", "HEAD"),
                "branch": self.git(*wt, "rev-parse", "--abbrev-ref", "HEAD"),
                "refs": self.git(*wt, "for-each-ref",
                                 "--format=%(refname) %(objectname)",
                                 "refs/heads", "refs/remotes", "refs/tags"),
                "worktrees": self.git(*wt, "worktree", "list", "--porcelain")}

    def assert_branch_run_with_appendices(self, out: str) -> None:
        ctx = self.context(out)
        records = self.branch_records()
        self.assertTrue(records, f"проба ветки не исполнялась; {ctx}")
        self.assertTrue(all(r["present"] for r in records),
                        f"дерево прогона ветки без правок приложений; {ctx}")
        self.assertTrue(all(r["cwd"] != str(self.wt) for r in records),
                        f"прогон ветки шёл в рабочей копии; {ctx}")
        self.assertNotIn(f"test_{self.probe_name}", out,
                         f"отчёт называет пробу упавшей; {ctx}")

    def assert_no_temp_tree(self, before: dict, out: str) -> None:
        ctx = self.context(out)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and self.leftovers():
            time.sleep(0.2)
        self.assertEqual(self.leftovers(), [],
                         f"во временном каталоге команды остались файлы; {ctx}")
        for node in self.nodes():
            if node["root"] != str(self.wt):
                self.assertFalse(Path(node["root"]).exists(),
                                 f"дерево прогона {node['root']} осталось; {ctx}")
        self.assertEqual(self.wt_snapshot()["worktrees"], before["worktrees"],
                         f"git worktree list изменился; {ctx}")

    def stop_everything(self) -> None:
        self.raise_flag.unlink(missing_ok=True)
        self.mode_file.unlink(missing_ok=True)
        pids = {n["pid"] for n in self.nodes()}
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and any(pid_alive(p) for p in pids):
            time.sleep(0.2)
        for pid in pids:
            if pid_alive(pid) and pid != os.getpid():
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        shutil.rmtree(self.probe, ignore_errors=True)


class BranchRunTest(SuiteRunAppendixSandbox):

    def test_ac3_report_without_probe_and_uncommitted_edit_seen(self):
        """`suite-run`: тест, зелёный с приложением, не упал; незакоммиченная правка видна.

        Сценарий: PLAN несёт одно-три приложения (от зерна), тест-проба
        ветки требует их правок; в рабочей копии ещё два теста — один
        зелёный, другой закоммичен зелёным, а незакоммиченной правкой
        переписан падающим. Отчёт `--wait` не называет пробу упавшей,
        называет переписанный тест; проба в прогоне ветки видела правки и
        шла не в рабочей копии.

        Ловит мутацию: прогон ветки по-прежнему в рабочей копии без
        приложений — проба красна и названа в отчёте; временное дерево
        заводится от HEAD ветки без переноса незакоммиченных правок — тест,
        красный только правкой рабочего дерева, в отчёте не назван.
        """
        diffs, needs = self.independent_edits(self.rng.randint(1, 3))
        flip, keep = self.word(), self.word()
        message = f"незакоммиченная правка {self.word()}"
        self.make_task(
            needs,
            committed={f"tests/test_{flip}.py": PASSING.format(name=flip),
                       f"tests/test_{keep}.py": PASSING.format(name=keep)},
            uncommitted={f"tests/test_{flip}.py": FAILING.format(
                name=flip, message=message)})
        self.write_docs(diffs)

        _code, _wait_code, out = self.run_suite()

        self.assert_branch_run_with_appendices(out)
        self.assertIn(f"test_{flip}", out,
                      f"отчёт не называет тест, красный незакоммиченной "
                      f"правкой; {self.context(out)}")
        self.assertNotIn(f"test_{keep}", out, self.context(out))


class OrderTest(SuiteRunAppendixSandbox):

    def test_ac4_chained_appendices_green_in_suite_run(self):
        """`suite-run`: второе приложение, применимое только поверх первого, ложится.

        Сценарий: два цепных приложения к одной строке защищённого файла;
        проба требует маркера второго. Отчёт не называет пробу упавшей,
        проба в прогоне ветки видела маркер второго приложения.

        Ловит мутацию: приложения накладываются в обратном порядке либо
        каждое проверяется против чистого дерева — второе неприменимо,
        прогона ветки нет; наложено только первое — проба красна.
        """
        diffs, needs = self.chained_edits(2)
        self.make_task(needs)
        self.write_docs(diffs)

        _code, _wait_code, out = self.run_suite()

        self.assert_branch_run_with_appendices(out)


class IntactTest(SuiteRunAppendixSandbox):

    def test_ac5_suite_run_leaves_working_copy_and_uncommitted_edits(self):
        """После `suite-run` с приложениями рабочая копия задачи прежняя.

        Сценарий: в рабочей копии — незакоммиченная правка отслеживаемого
        теста и неотслеживаемый файл; PLAN несёт одно-два приложения.
        После прогона `git status --porcelain`, индекс, голова, имя ветки,
        ссылки `refs/heads`/`refs/remotes`/`refs/tags`, `git worktree list`
        — как до прогона; текст незакоммиченной правки на месте; временный
        каталог команды пуст.

        Ловит мутацию: незакоммиченные правки переносятся во временное
        дерево через `git stash` без возврата — правка пропадает из рабочей
        копии; приложения накладываются в рабочей копии и не откатываются —
        статус показывает защищённые файлы; временное дерево не убрано —
        каталог во `TMPDIR` и запись `git worktree list` остаются.
        """
        diffs, needs = self.independent_edits(self.rng.randint(1, 2))
        name = self.word()
        edited = f"tests/test_{name}.py"
        text = FAILING.format(name=name, message=f"правка {self.word()}")
        self.make_task(needs, committed={edited: PASSING.format(name=name)},
                       uncommitted={edited: text,
                                    f"note-{self.word()}.txt": "заметка\n"})
        self.write_docs(diffs)
        before = self.wt_snapshot()

        _code, _wait_code, out = self.run_suite()

        self.assert_branch_run_with_appendices(out)
        after = self.wt_snapshot()
        for key, value in before.items():
            self.assertEqual(after[key], value,
                             f"{key} рабочей копии изменился; {self.context(out)}")
        self.assertEqual((self.wt / edited).read_text(encoding="utf-8"), text,
                         self.context(out))
        self.assert_no_temp_tree(before, out)


class RefusalTest(SuiteRunAppendixSandbox):

    def test_ac6_inapplicable_appendix_refuses_suite_run(self):
        """`suite-run` с неприменимым приложением — отказ без прогона.

        Сценарий: среди двух-трёх приложений одно (место от зерна) не ложится
        на дерево задачи. Запуск или ожидание завершается ненулевым кодом,
        вывод называет номер приложения и его путь; полный набор не
        запускался (узел `run_full_suite` не вызван, проба не исполнялась).

        Ловит мутацию: неприменимое приложение пропущено, прогон идёт с
        остальными — узел вызван; отказ без номера приложения или без пути;
        прогон откатывается в рабочую копию без приложений.
        """
        diffs, number, rel = self.inapplicable_scenario()
        self.make_task([])
        self.write_docs(diffs)

        code, wait_code, out = self.run_suite()

        ctx = self.context(out)
        self.assertTrue(code != 0 or wait_code != 0,
                        f"отказа нет (коды {code}, {wait_code}); {ctx}")
        self.assertTrue(names_number(out, number),
                        f"вывод не называет приложение {number}; {ctx}")
        self.assertIn(rel, out, f"вывод не называет путь {rel}; {ctx}")
        self.assertEqual(self.nodes(), [], f"полный набор запускался; {ctx}")
        self.assertEqual(self.probe_records(), [], ctx)

    def test_ac7_git_failure_refuses_suite_run(self):
        """Сбой git при подготовке дерева или наложении — отказ `suite-run` без прогона.

        Сценарий: для каждого режима сбоя (`git apply`, `git worktree add`
        ненулевым кодом) — задача с применимыми приложениями. Запуск или
        ожидание завершается ненулевым кодом, полный набор не запускался ни
        на временном дереве, ни в рабочей копии. Если реализация вовсе не
        зовёт `git worktree add`, для этого режима держится только запрет
        прогона в рабочей копии без приложений.

        Ловит мутацию: сбой наложения принят за «приложений нет» — прогон
        идёт в рабочей копии (fail-open); ответ `git worktree add` не
        проверен — прогон на пустом каталоге или в рабочей копии.
        """
        for mode in ("apply", "worktree add"):
            self.case = f"режим сбоя {mode}"
            self.reset_observation()
            diffs, needs = self.independent_edits(self.rng.randint(1, 2))
            self.make_task(needs)
            self.write_docs(diffs)
            self.mode_file.write_text(mode, encoding="utf-8")
            try:
                code, wait_code, out = self.run_suite()
            finally:
                self.mode_file.unlink(missing_ok=True)
            ctx = self.context(out) + f"\n--- отказы git: {self.git_log.exists()}"
            self.assertFalse([n for n in self.nodes() if n["root"] == str(self.wt)],
                             f"прогон без приложений в рабочей копии; {ctx}")
            if mode == "worktree add" and not self.git_log.exists():
                continue
            self.assertTrue(self.git_log.exists(), f"git apply не вызывался; {ctx}")
            self.assertTrue(code != 0 or wait_code != 0,
                            f"отказа нет (коды {code}, {wait_code}); {ctx}")
            self.assertEqual(self.branch_records(), [],
                             f"прогон ветки состоялся; {ctx}")


class TempTreeTest(SuiteRunAppendixSandbox):

    OUTCOMES = ("зелёный", "красный", "неприменимое приложение",
                "сбой git", "исключение")

    def test_ac8_temp_tree_absent_after_each_outcome(self):
        """Временного дерева `suite-run` нет после прогона на каждом исходе.

        Сценарий: по задаче на исход — зелёный, красный (проба ждёт правки,
        которой нет в приложениях), неприменимое приложение, сбой `git
        apply`, исключение в ходе прогона (узел `run_full_suite` копии
        бросает по файлу-флагу). После отчёта: корни прогонов вне рабочей
        копии удалены, `TMPDIR` команды пуст, `git worktree list` прежний.

        Ловит мутацию: уборка временного дерева не в `finally` — на
        исключении каталог и запись worktree остаются; на красном исходе
        выход раньше уборки; на отказе наложения дерево не убирается.
        """
        for outcome in self.OUTCOMES:
            self.case = f"исход «{outcome}»"
            self.reset_observation()
            if outcome == "неприменимое приложение":
                diffs, _number, _rel = self.inapplicable_scenario()
                needs = []
            else:
                diffs, needs = self.independent_edits(self.rng.randint(1, 2))
            if outcome == "красный":
                needs = needs + [(self.files[0], f"нет такой правки {self.word()}")]
            self.make_task(needs)
            self.write_docs(diffs)
            before = self.wt_snapshot()
            if outcome == "исключение":
                self.raise_flag.write_text("1", encoding="utf-8")
            if outcome == "сбой git":
                self.mode_file.write_text("apply", encoding="utf-8")
            try:
                _code, _wait_code, out = self.run_suite()
            finally:
                self.raise_flag.unlink(missing_ok=True)
                self.mode_file.unlink(missing_ok=True)
            if outcome in ("зелёный", "красный", "исключение"):
                roots = [n["root"] for n in self.nodes()]
                self.assertTrue(roots, self.context(out))
                self.assertNotIn(str(self.wt), roots, self.context(out))
            self.assert_no_temp_tree(before, out)


class WithoutAppendixTest(SuiteRunAppendixSandbox):

    def test_ac9_no_appendices_or_non_artel_run_in_working_copy(self):
        """Без приложений и для задачи не артели прогон ветки — в рабочей копии.

        Сценарий: задача артели с PLAN без приложений; затем задача внешнего
        проекта (с профилем тестов) с PLAN, несущим приложения. В обоих
        случаях проба ветки исполнялась с cwd, равным рабочей копии задачи,
        и узел `run_full_suite` вызван с этим корнем.

        Ловит мутацию: временное дерево заводится всегда — cwd пробы не
        рабочая копия; проверка `repo_context.is_artel` пропущена — во
        внешнем проекте нет защищённых файлов, `git apply` отказывает и
        прогона ветки нет.
        """
        self.case = "артель без приложений"
        self.make_task([])
        self.write_docs([])
        _code, _wait_code, out = self.run_suite()
        records = self.branch_records()
        self.assertTrue(records, self.context(out))
        self.assertEqual({r["cwd"] for r in records}, {str(self.wt)},
                         self.context(out))
        self.assertIn(str(self.wt), [n["root"] for n in self.nodes()],
                      self.context(out))

        self.case = "внешний проект"
        self.reset_observation()
        target = f"p{self.word()}"
        self.entries[target] = ENTRY.format(
            name=target, url=f"file://{config.PROJECTS / target / 'origin.git'}",
            base=config.MAIN_BRANCH, python=sys.executable)
        self.write_targets()
        make_project_repo(target)
        diffs, _needs = self.independent_edits(self.rng.randint(1, 2))
        self.make_task([], target)
        self.write_docs(diffs)
        _code, _wait_code, out = self.run_suite()
        records = self.branch_records()
        self.assertTrue(records, self.context(out))
        self.assertEqual({r["cwd"] for r in records}, {str(self.wt)},
                         self.context(out))


class ReportMarkTest(SuiteRunAppendixSandbox):

    def test_ac10_report_names_appendix_run_and_paths(self):
        """Отчёт `suite-run` называет прогон с приложениями PLAN и их пути.

        Сценарий: одно-три приложения к одному-двум защищённым файлам;
        отчёт `--wait` содержит признак «с приложениями PLAN» и пути всех
        наложенных приложений.

        Ловит мутацию: отчёт прежнего вида без признака — по нему не
        отличить прогон с приложениями от прогона рабочей копии; в отчёте
        только путь первого приложения.
        """
        diffs, needs = self.independent_edits(self.rng.randint(1, 3))
        self.make_task(needs)
        self.write_docs(diffs)

        _code, _wait_code, out = self.run_suite()

        ctx = self.context(out)
        self.assertIn(WITH_APPENDICES, out.lower(), ctx)
        for rel in sorted({rel for rel, _marker in needs}):
            self.assertIn(rel, out, ctx)


class BaseRunTest(SuiteRunAppendixSandbox):

    def test_ac11_base_run_without_task_appendices(self):
        """Прогон базы `suite-run` идёт без приложений задачи.

        Сценарий: на `main` (база задачи) лежит тест-проба базы, которой
        нужны правки приложений PLAN задачи; на ветке та же проба зелёная
        благодаря приложениям. Сохранённого итога базы нет — прогон базы
        идёт. Проба базы в прогоне базы (cwd вне рабочей копии) исполнялась
        и не видела правок — в итоге базы она красна.

        Ловит мутацию: приложения задачи накладываются и на дерево базы —
        проба базы в прогоне базы видит правки и зелёная; прогон базы идёт
        на том же временном дереве ветки — cwd пробы базы совпадает с
        корнем прогона ветки.
        """
        diffs, needs = self.independent_edits(self.rng.randint(1, 2))
        base_probe = f"probe_{self.word()}"
        self.commit_on_main({f"tests/test_{base_probe}.py":
                             self.probe_source(base_probe, needs)})
        self.make_task(needs)
        self.write_docs(diffs)

        _code, _wait_code, out = self.run_suite()

        ctx = self.context(out)
        records = [r for r in self.probe_records() if r["name"] == base_probe]
        branch_roots = {r["root"] for r in self.branch_records()}
        base = [r for r in records if r["root"] not in branch_roots
                and r["cwd"] != str(self.wt)]
        on_branch = [r for r in records if r["root"] in branch_roots]
        self.assertTrue(on_branch and all(r["present"] for r in on_branch),
                        f"проба базы на ветке не видела приложений; {ctx}")
        self.assertTrue(base, f"прогона базы не было; {ctx}")
        self.assertFalse(any(r["present"] for r in base),
                         f"прогон базы шёл с приложениями задачи; {ctx}")


if __name__ == "__main__":
    unittest.main()
