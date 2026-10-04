"""Сценарий CI `scripts/plan_appendix_ci.py`: приложения PLAN задачи на дереве раннера.

Группа: долгоживущий
Красен до реализации: сценария scripts/plan_appendix_ci.py ещё нет — его запуск в дереве раннера падает «can't open file», код выхода ненулевой, приложения не наложены.

Песочница воспроизводит прогон CI по пушу ветки задачи
(`tests/sandbox.py::RealGitSandbox` + bare `origin`):

- репозиторий автора несёт на `main` код пульта (копию `orchestrator/` и
  `scripts/` этой рабочей копии — сценарий и разбор
  `guard.plan_appendices` идут из неё) и защищённые файлы-фикстуры; ветка
  задачи `task/<id в нижнем регистре>-<слаг>` правит код задачи и
  отправлена в `origin`;
- ссылка документов `refs/artifacts/<id>` (id в исходном регистре) живёт
  только в `origin` — её отправляет пульт, в ветке задачи PLAN.md нет;
- «раннер» — неглубокий клон `origin` на ветке задачи (так её выписывает
  `actions/checkout`); сценарий запускается из корня раннера
  `python3 scripts/plan_appendix_ci.py` без аргументов, с переменными
  окружения Actions пуша ветки (`GITHUB_REF`, `GITHUB_REF_NAME`,
  `GITHUB_EVENT_NAME`, `GITHUB_SHA`, `GITHUB_WORKSPACE`) — тем же
  способом, каким CI зовёт соседний `scripts/ci_push_class.py`.

«Имя» приложения в выводе — любая из его опознавательных черт: путь из
заголовка `diff --git`, текст заголовка раздела «## Приложение…» или его
порядковый номер рядом со словом «приложение» (SPEC, требование 3:
«заголовок/номер»).
"""
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import checkpoint, config, idgen
from tests.sandbox import RealGitSandbox

CODE_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_REL = "scripts/plan_appendix_ci.py"

# Защищённые пути — от `config.PROTECTED_PATHS`, не литералом: перечень
# меняет Оператор. Защищённый тест — файл под `tests/`; прочие защищённые
# файлы — markdown вне `tests/` и `.github/`: текст фикстуры в защищённом
# конфиге (`pyproject.toml`, `tox.ini`, YAML пульта) ломал бы сам прогон.
PROTECTED_TEST = next(p for p in config.PROTECTED_PATHS
                      if p.startswith("tests/") and p.endswith(".py"))
PROTECTED_FILES = [p for p in config.PROTECTED_PATHS
                   if p.endswith(".md") and "*" not in p
                   and not p.startswith(("tests/", ".github"))]

SLUG_WORDS = ("ci", "vetki", "zadachi", "fix", "plan", "x", "2", "shag")
HEADING_WORDS = ("правка", "шаг", "сторож", "настройка", "перечень")

BASE_LINES = [f"строка базы {n:02d} из 40" for n in range(1, 41)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
# Строки правок — через восемь: контекст хунка соседней правки их не
# задевает, диффы от базы ложатся друг на друга в любом порядке.
EDIT_LINES = BASE_LINES[::8]

PROTECTED_TEST_TEXT = '''import unittest
from pathlib import Path


class FeatureTest(unittest.TestCase):

    def test_feature(self):
        root = Path(__file__).resolve().parent.parent
        text = (root / "feature.txt").read_text(encoding="utf-8")
        self.assertEqual(text, "{expected}\\n")
'''

GIT_SHIM = """#!/bin/sh
for a in "$@"; do printf '%s\\t' "$a" >> "{log}"; done
printf '\\n' >> "{log}"
exec "{real}" "$@"
"""


def names_appendix(text: str, path: str, heading: str, number: int) -> bool:
    """Текст называет приложение: его путём, заголовком раздела либо
    номером рядом со словом «приложение»."""
    if path in text or heading in text:
        return True
    return re.search(rf"приложени\w*\s*(№\s*)?{number}\b", text,
                     re.IGNORECASE) is not None


def git_subcommand(argv: list[str]) -> str:
    """Подкоманда git из его argv: первое слово, не опция и не значение
    глобальной опции (`-C <путь>`, `-c <ключ=значение>`)."""
    skip = False
    for arg in argv:
        if skip:
            skip = False
            continue
        if arg in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            skip = True
            continue
        if arg.startswith("-"):
            continue
        return arg
    return ""


class PlanAppendixCiSandbox(RealGitSandbox):
    """Автор, `origin` и раннер CI для ветки задачи со случайным id и
    слагом; на ветке задачи защищённый тест красный (код задачи поменял
    `feature.txt`, тест ждёт прежнего значения)."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.assertGreaterEqual(len(PROTECTED_FILES), 2, self.note(
            "в config.PROTECTED_PATHS нет двух защищённых файлов вне tests/"))
        self.files = self.rng.sample(PROTECTED_FILES, 2)
        self.old = f"прежнее значение {self.rng.randrange(10**6)}"
        self.new = f"новое значение {self.rng.randrange(10**6)}"

        tmp = Path(tempfile.mkdtemp(prefix="artel-plan-appendix-ci-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.tmp = tmp

        with open(self.root / ".gitignore", "a", encoding="utf-8") as fh:
            fh.write("__pycache__/\n*.pyc\n")
        for package in ("orchestrator", "scripts"):
            shutil.copytree(CODE_ROOT / package, self.root / package,
                            ignore=shutil.ignore_patterns("__pycache__",
                                                          "*.pyc"))
        self.write(PROTECTED_TEST, PROTECTED_TEST_TEXT.format(expected=self.old))
        self.write("feature.txt", f"{self.old}\n")
        for rel in self.files:
            self.write(rel, BASE_TEXT)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "код пульта и защищённые файлы")
        self.origin = self.add_synced_origin()

        self.task = idgen.new_task_id()
        slug = "-".join(self.rng.sample(SLUG_WORDS, self.rng.randint(1, 3)))
        self.branch = f"task/{self.task.lower()}-{slug}"
        self.checkout(self.branch, create=True)
        self.write("feature.txt", f"{self.new}\n")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", "код задачи")
        self.git("push", "-q", "origin", self.branch)
        self.checkout(config.MAIN_BRANCH)

    # ------------------------------------------------------------ обвязка

    def note(self, text: str) -> str:
        branch = getattr(self, "branch", "ещё не заведена")
        return f"{text} (зерно {self.seed}, ветка {branch})"

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def heading(self, number: int) -> str:
        word = self.rng.choice(HEADING_WORDS)
        return f"Приложение {number}: {word} {self.rng.randrange(10**6)}"

    def diff_of(self, edits: dict) -> str:
        """Unified-дифф правок `edits` ({путь: {старое: новое}}) к дереву
        ветки задачи — настоящим `git diff`, правка затем откатывается."""
        self.checkout(self.branch)
        for rel, replacements in edits.items():
            path = self.root / rel
            text = path.read_text(encoding="utf-8")
            for old, new in replacements.items():
                self.assertIn(old, text)
                text = text.replace(old, new)
            path.write_text(text, encoding="utf-8")
        diff = self.git("diff", "--", *edits)
        self.git("checkout", "-q", "--", *edits)
        self.checkout(config.MAIN_BRANCH)
        self.assertIn("diff --git a/", diff)
        return diff

    def fixing_diff(self) -> str:
        """Приложение к защищённому тесту, без которого он красный."""
        return self.diff_of({PROTECTED_TEST: {self.old: self.new}})

    def inapplicable_diff(self, rel: str) -> str:
        return (f"diff --git a/{rel} b/{rel}\n--- a/{rel}\n+++ b/{rel}\n"
                f"@@ -1,3 +1,3 @@\n строки, которой нет\n-и этой нет\n"
                f"+правка\n и этой нет\n")

    def plan_text(self, appendices: list[tuple[str, str]],
                  approach_diff: str = "") -> str:
        sections = "".join(f"\n## {heading}\n\n```diff\n{diff}```\n"
                           for heading, diff in appendices)
        approach = f"\n```diff\n{approach_diff}```\n" if approach_diff else ""
        return (f"---\ntask: {self.task}\ntype: plan\n"
                f"author_role: developer\nstatus: ready\n"
                f"schema_version: 2\n---\n\n# PLAN\n\n## Подход\n\n"
                f"Фикстура.\n{approach}{sections}")

    def publish_docs(self, files: dict) -> None:
        """Коммит документов задачи ({имя файла: текст}) в ссылку
        документов `origin` — отдельным репозиторием, мимо ветки задачи."""
        docs = self.tmp / f"docs-{self.rng.randrange(10**9)}"
        self.git("init", "-q", str(docs))
        prefix = checkpoint.task_dir_zone(self.task)
        for name, text in files.items():
            path = docs / prefix / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(docs), "add", "-A")
        self.git("-C", str(docs), "-c", "user.email=artel@example.invalid",
                 "-c", "user.name=artel tests", "commit", "-q", "-m",
                 "документы задачи")
        self.git("-C", str(docs), "push", "-q", "--force", str(self.origin),
                 f"HEAD:refs/artifacts/{self.task}")

    def publish_plan(self, appendices: list[tuple[str, str]]) -> None:
        self.publish_docs({"PLAN.md": self.plan_text(appendices)})

    def runner(self) -> Path:
        """Неглубокий клон `origin` на ветке задачи — дерево раннера CI."""
        runner = self.tmp / f"runner-{self.rng.randrange(10**9)}"
        self.git("clone", "-q", "--depth", "1", "--branch", self.branch,
                 f"file://{self.origin}", str(runner))
        return runner

    def rgit(self, runner: Path, *args: str) -> str:
        return self.git("-C", str(runner), *args)

    def run_script(self, runner: Path, path_prefix: str = "") -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update({
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": f"refs/heads/{self.branch}",
            "GITHUB_REF_NAME": self.branch,
            "GITHUB_REF_TYPE": "branch",
            "GITHUB_SHA": self.rgit(runner, "rev-parse", "HEAD").strip(),
            "GITHUB_WORKSPACE": str(runner),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        if path_prefix:
            env["PATH"] = path_prefix + os.pathsep + env.get("PATH", "")
        return subprocess.run([sys.executable, str(runner / SCRIPT_REL)],
                              cwd=runner, env=env, capture_output=True,
                              text=True, timeout=120)

    def protected_test(self, runner: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-m", "pytest", "-q",
                               "-p", "no:cacheprovider", PROTECTED_TEST],
                              cwd=runner, env=env, capture_output=True,
                              text=True, timeout=120)

    def output(self, res: subprocess.CompletedProcess) -> str:
        return f"код {res.returncode}\n{res.stdout}\n{res.stderr}"


class AppliesAppendicesTest(PlanAppendixCiSandbox):

    def test_ac1_script_applies_appendix_and_protected_test_turns_green(self):
        """Сценарий накладывает приложение PLAN, и красный защищённый тест зеленеет.

        Сценарий: на ветке задачи защищённый тест красный (проверено
        прогоном в раннере до сценария); PLAN в ссылке документов
        `origin` несёт приложение к этому тесту и — от зерна — ещё одно
        приложение к другому защищённому файлу до или после него. Сценарий
        в раннере завершается кодом 0; тот же тест на получившемся дереве
        зелёный; правка второго приложения тоже лежит в дереве раннера.

        Ловит мутацию: сценарий, не накладывающий приложения (разобрал
        PLAN и вышел с кодом 0, либо читает PLAN.md из дерева ветки, где
        его нет), — защищённый тест остаётся красным; вторая мутация —
        накладывается только первое приложение PLAN, и правки второго
        файла в дереве раннера нет.
        """
        marker = f"правка приложения ({self.rng.randrange(10**6)})"
        line = self.rng.choice(EDIT_LINES)
        diffs = [self.fixing_diff()]
        diffs.insert(self.rng.randint(0, 1),
                     self.diff_of({self.files[0]: {line: marker}}))
        self.publish_plan([(self.heading(i + 1), diff)
                           for i, diff in enumerate(diffs)])
        runner = self.runner()
        before = self.protected_test(runner)
        self.assertNotEqual(before.returncode, 0, self.note(
            "предусловие: защищённый тест на ветке без приложения зелёный\n"
            + self.output(before)))

        res = self.run_script(runner)

        self.assertEqual(res.returncode, 0, self.note(self.output(res)))
        after = self.protected_test(runner)
        self.assertEqual(after.returncode, 0, self.note(
            "защищённый тест после сценария красный\n" + self.output(after)
            + "\n--- сценарий:\n" + self.output(res)))
        self.assertIn(marker, (runner / self.files[0]).read_text(
            encoding="utf-8"), self.note("второе приложение не наложено"))


class NothingToApplyTest(PlanAppendixCiSandbox):

    def assert_untouched(self, where: str) -> None:
        runner = self.runner()
        head = self.rgit(runner, "rev-parse", "HEAD").strip()

        res = self.run_script(runner)

        self.assertEqual(res.returncode, 0, self.note(
            f"{where}: {self.output(res)}"))
        self.assertEqual(self.rgit(runner, "status", "--porcelain"), "",
                         self.note(f"{where}: дерево раннера изменено\n"
                                   + self.output(res)))
        self.assertEqual(self.rgit(runner, "rev-parse", "HEAD").strip(), head,
                         self.note(f"{where}: HEAD раннера сдвинут"))

    def test_ac2_no_ref_no_plan_no_appendices_leave_tree_untouched(self):
        """Ветка без приложений: сценарий выходит с кодом 0 и дерево не трогает.

        Сценарий — три состояния `origin` подряд, для каждого свежий
        раннер: ссылки документов задачи нет вовсе; ссылка есть, но
        PLAN.md в ней нет (только SPEC.md); PLAN.md есть, но разделов
        «## Приложение…» в нём нет (есть блок ```diff к защищённому тесту
        в разделе «## Подход» — приложением он не является). Каждый раз — код 0, `git status --porcelain` раннера
        пуст, HEAD прежний.

        Ловит мутацию: отсутствие ссылки или PLAN.md сценарий считает
        ошибкой (ненулевой код — CI любой ветки без приложений красный);
        вторая мутация — сценарий накладывает любой блок ```diff PLAN, а не
        только разделы «## Приложение» (`guard.plan_appendices`), и дерево
        раннера меняется.
        """
        self.assert_untouched("ссылки документов нет")
        self.publish_docs({"SPEC.md": f"---\ntask: {self.task}\n---\n"})
        self.assert_untouched("в ссылке документов нет PLAN.md")
        self.publish_docs({"PLAN.md": self.plan_text([], self.fixing_diff())})
        self.assert_untouched("в PLAN нет приложений")


class InapplicableAppendixTest(PlanAppendixCiSandbox):

    def test_ac3_inapplicable_appendix_fails_with_its_name(self):
        """Неприменимое приложение — ненулевой код и имя этого приложения в выводе.

        Сценарий: PLAN несёт от нуля до двух применимых приложений к одному
        защищённому файлу и затем неприменимое — к другому защищённому
        файлу (контекст хунка не существует в дереве ветки), от зерна —
        ещё одно применимое после него. Сценарий завершается ненулевым
        кодом; его вывод (stdout и stderr) называет неприменимое
        приложение — путём, заголовком или номером.

        Ловит мутацию: сценарий проглатывает отказ `git apply` (печатает
        ответ git и выходит с кодом 0 либо идёт к следующему приложению и
        завершается успехом) — CI ветки зелёный при приложении, которое
        ворота мержа не наложат, и тест краснеет на коде выхода; вторая
        мутация — отказ безымянный («приложение неприменимо» без пути,
        заголовка и номера, ответ git не выведен) — вывод не называет
        неприменимое приложение ничем.
        """
        good_rel, bad_rel = self.files
        before = self.rng.randint(0, 2)
        lines = self.rng.sample(EDIT_LINES, before + 1)
        appendices = [(self.heading(i + 1),
                       self.diff_of({good_rel: {lines[i]: f"правка {i + 1}"}}))
                      for i in range(before)]
        number = before + 1
        bad_heading = self.heading(number)
        appendices.append((bad_heading, self.inapplicable_diff(bad_rel)))
        if self.rng.random() < 0.5:
            appendices.append((self.heading(number + 1), self.diff_of(
                {good_rel: {lines[before]: "правка после"}})))
        self.publish_plan(appendices)
        runner = self.runner()

        res = self.run_script(runner)

        out = self.output(res)
        self.assertNotEqual(res.returncode, 0, self.note(out))
        self.assertTrue(
            names_appendix(res.stdout + res.stderr, bad_rel, bad_heading,
                           number),
            self.note(f"вывод не называет неприменимое приложение "
                      f"№{number} «{bad_heading}» ({bad_rel}):\n{out}"))


class NoCommitNoPushTest(PlanAppendixCiSandbox):

    def refs(self, *git_dir_args: str) -> dict:
        out = self.git(*git_dir_args, "for-each-ref",
                       "--format=%(refname) %(objectname)")
        return dict(line.split(" ", 1) for line in out.splitlines() if line)

    def test_ac4_script_creates_no_commits_and_moves_no_refs(self):
        """Сценарий не коммитит, не пушит и не двигает ссылок раннера и `origin`.

        Сценарий: PLAN с применимым приложением (сценарий его накладывает);
        `git` в PATH сценария — обёртка, журналирующая каждую команду и
        передающая её настоящему git. До и после сценария снимаются
        `git for-each-ref` раннера и `origin` и HEAD раннера. После: HEAD
        прежний; каждая ссылка раннера, бывшая до сценария, на прежнем
        значении и ни одна не удалена; новые ссылки раннера — только вне
        `refs/heads/` и `refs/tags/` (отдельное пространство подтяжки
        PLAN); ссылки `origin` не изменились вовсе; в журнале обёртки нет
        подкоманд `commit` и `push`.

        Ловит мутацию: сценарий фиксирует наложенные приложения коммитом
        (`git commit -am …`) — HEAD раннера сдвинут и в журнале обёртки
        есть `commit`; вторая мутация — сценарий отправляет результат в
        `origin` (`git push`) — ссылки `origin` изменились и в журнале есть
        `push`; третья — PLAN подтягивается в ветку (`git fetch origin
        refs/artifacts/<id>:refs/heads/…`) — новая ссылка под
        `refs/heads/`.
        """
        self.publish_plan([(self.heading(1), self.fixing_diff())])
        runner = self.runner()
        shim_dir = self.tmp / "shim"
        shim_dir.mkdir()
        log = self.tmp / "git-calls.log"
        real_git = shutil.which("git")
        self.assertTrue(real_git, "git не найден в PATH")
        shim = shim_dir / "git"
        shim.write_text(GIT_SHIM.format(log=log, real=real_git),
                        encoding="utf-8")
        shim.chmod(0o755)
        runner_args = ("-C", str(runner))
        origin_args = ("--git-dir", str(self.origin))
        refs_before = self.refs(*runner_args)
        origin_before = self.refs(*origin_args)
        head = self.rgit(runner, "rev-parse", "HEAD").strip()

        res = self.run_script(runner, path_prefix=str(shim_dir))

        out = self.output(res)
        self.assertEqual(res.returncode, 0, self.note(out))
        self.assertEqual(self.rgit(runner, "rev-parse", "HEAD").strip(), head,
                         self.note("HEAD раннера сдвинут\n" + out))
        refs_after = self.refs(*runner_args)
        for ref, sha in refs_before.items():
            self.assertEqual(refs_after.get(ref), sha, self.note(
                f"ссылка раннера {ref} изменена или удалена\n{out}"))
        added = sorted(set(refs_after) - set(refs_before))
        self.assertEqual(
            [r for r in added if r.startswith(("refs/heads/", "refs/tags/"))],
            [], self.note(f"новые ссылки раннера: {added}\n{out}"))
        self.assertEqual(self.refs(*origin_args), origin_before,
                         self.note("ссылки origin изменены\n" + out))
        self.assertTrue(log.exists(), self.note(
            "сценарий ни разу не позвал git из PATH — журнал обёртки пуст"))
        calls = [line.split("\t")[:-1] for line in
                 log.read_text(encoding="utf-8").splitlines() if line]
        forbidden = [c for c in calls if git_subcommand(c) in ("commit", "push")]
        self.assertEqual(forbidden, [], self.note(
            f"сценарий звал git commit/push: {forbidden}"))


if __name__ == "__main__":
    unittest.main()
