"""Обязательства PLAN задачи: вывод поиска вызовов `gitcmd` (AC-8),
приложение к инвариантам с новым тестом (AC-14), перечень изменений
существующих тестов и заявки мутаций (AC-15).

Группа: разовый

Источник PLAN — ссылка документов задачи `refs/artifacts/<id>` (чтение
`git show` в рабочей копии кода, где идёт прогон), не диск. Дифф задачи —
от точки расхождения `gitcmd.diff_base` (с `origin/main`, если он есть).

AC-14 проверяется исполнением: копия дерева рабочей копии кода (без
`.git`), на неё накладываются приложения PLAN в их порядке (`git apply
--check`, затем `git apply`), в ней гоняется новый тест
`tests/test_invariants.py` — он обязан быть зелёным, — а затем тот же тест
с внедрённой мутацией: обёртка `gitcmd.git` копии дерева повторяет в git
главной копии (`config.ROOT` на момент вызова) каждое заведение ветки
задачи (вариант «ветка») либо каждую рабочую копию, заводимую в клоне
проекта не под ветку задачи, то есть временную рабочую копию мержа
(вариант «рабочая копия»). Под каждой мутацией новый тест обязан
покраснеть.

Красен до реализации: PLAN.md задачи ещё нет в ссылке документов —
приложения, вывода поиска и перечня изменений тестов взять негде.

Провалидирован стабом (удалён): синтетический PLAN со строкой поиска,
перечнем изменения теста с пунктом ADR-0021 и приложением к инвариантам,
чей новый тест сверяет ветки и рабочие копии главной копии и в середине,
и в конце сценария, — все семь методов зелёные; тест приложения, сверяющий
только конец сценария, проваливает проверку мутации «рабочая копия», а
сверяющий только рабочие копии — мутации «ветка».
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import gitcmd
from scripts import guard

TASK_ID = "01M42PENCS26D0656X8FR7DFA7"
PLAN_REV = f"refs/artifacts/{TASK_ID}:tasks/{TASK_ID}/PLAN.md"
LONG_LIVED_PREFIX = f"tests/test_{TASK_ID.lower()}_"
INVARIANTS_DOC = "docs/invariants.md"
INVARIANTS_TEST = "tests/test_invariants.py"
ANY_PROJECT = ("любого проекта", "любой проект", "включая артель")
COPY_IGNORE = shutil.ignore_patterns(".git", "tasks", ".artel", "__pycache__",
                                     ".pytest_cache")
NEW_TEST_TIMEOUT_SEC = 110


def code_dir() -> Path:
    """Рабочая копия кода, где идёт прогон планки (cwd pytest)."""
    return Path.cwd()


def git(*args: str, cwd: Path | None = None, input_text: str | None = None
        ) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd or code_dir(),
                          capture_output=True, text=True, input=input_text)


def plan_text() -> str | None:
    res = git("show", PLAN_REV)
    return res.stdout if res.returncode == 0 else None


def base_sha() -> str | None:
    return gitcmd.diff_base("HEAD", repo=code_dir())


def file_at(rev: str, rel: str) -> str | None:
    res = git("show", f"{rev}:{rel}")
    return res.stdout if res.returncode == 0 else None


class PlanSource(unittest.TestCase):

    def plan(self) -> str:
        text = plan_text()
        self.assertIsNotNone(text, f"PLAN.md нет в {PLAN_REV}")
        return text


# --------------------------------------------------------------------- AC-8

GREP_LINE = re.compile(r"orchestrator/[\w/]+\.py:\d+:.*\bgitcmd\.\w+\(")


class GitcmdSearchOutputInPlanTest(PlanSource):

    def test_ac8_plan_carries_search_output_over_orchestrator(self):
        """PLAN несёт вывод поиска вызовов `gitcmd` по `orchestrator/`:
        строки вида `orchestrator/<модуль>.py:<строка>:… gitcmd.<имя>(`.

        Само свойство «каждый вызов без репозитория — из перечня
        требования 4» держит долгоживущий файл задачи
        (`tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py`).

        Ловит мутацию: PLAN утверждает «вызовов вне перечня нет» без
        вывода поиска — строк формата `grep -n` нет.
        """
        lines = [ln for ln in self.plan().splitlines() if GREP_LINE.search(ln)]
        self.assertTrue(lines, "в PLAN нет вывода поиска вызовов gitcmd "
                               "по orchestrator/ (строк файл:строка:текст)")


# -------------------------------------------------------------------- AC-14

def appendices(plan: str) -> list:
    found, errors = guard.plan_appendices(plan)
    if errors:
        raise AssertionError(f"приложения PLAN не разобраны: {errors}")
    return found


def applied_tree(test: unittest.TestCase, plan: str) -> Path:
    """Копия рабочей копии кода с наложенными приложениями PLAN."""
    tmp = Path(tempfile.mkdtemp(prefix="plank-appendix-"))
    test.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
    tree = tmp / "tree"
    shutil.copytree(code_dir(), tree, ignore=COPY_IGNORE, symlinks=True)
    for appendix in appendices(plan):
        diff = appendix.diff if appendix.diff.endswith("\n") else appendix.diff + "\n"
        check = git("apply", "--check", "-", cwd=tree, input_text=diff)
        test.assertEqual(check.returncode, 0,
                         f"git apply --check {appendix.paths}: {check.stderr}")
        res = git("apply", "-", cwd=tree, input_text=diff)
        test.assertEqual(res.returncode, 0, f"git apply {appendix.paths}: {res.stderr}")
    return tree


def class_names(source: str) -> set:
    return {node.name for node in ast.parse(source).body
            if isinstance(node, ast.ClassDef)}


def new_test_classes(tree: Path) -> list:
    """Классы `tests/test_invariants.py` дерева с приложениями, которых нет
    в версии рабочей копии кода и у которых есть методы `test_*`."""
    applied = (tree / INVARIANTS_TEST).read_text(encoding="utf-8")
    base = (code_dir() / INVARIANTS_TEST).read_text(encoding="utf-8")
    added = class_names(applied) - class_names(base)
    result = []
    for node in ast.parse(applied).body:
        if isinstance(node, ast.ClassDef) and node.name in added and any(
                isinstance(item, ast.FunctionDef) and item.name.startswith("test")
                for item in node.body):
            result.append(node.name)
    return result


# Мутация копии дерева: обёртка `git` модуля примитивов (через неё идёт и
# `in_repo`). Повторяет в git `config.ROOT` (главная копия на момент
# вызова) заведение ветки задачи либо рабочую копию клона не под ветку
# задачи. Ошибки самой обёртки глотаются: мутация — не предмет отказа.
MUTATION = '''

_zond_git_original = git
_zond_twins = {}


def git(*args):
    res = _zond_git_original(*args)
    try:
        _zond_twin(list(args), res)
    except Exception:
        pass
    return res


def _zond_twin(args, res):
    import os as _os
    from pathlib import Path as _Path
    if res is None or res.returncode != 0 or len(args) < 3 or args[0] != "-C":
        return
    repo, rest = str(_Path(args[1]).resolve()), args[2:]
    if "/.artel/projects/" not in repo + "/":
        return
    mode = _os.environ.get("ARTEL_PLANK_MUTATION")
    creates = ("-b" in rest or "-B" in rest)
    if mode == "branch":
        name = None
        if rest[:2] == ["worktree", "add"] and creates:
            flag = "-b" if "-b" in rest else "-B"
            name = rest[rest.index(flag) + 1]
        elif rest[:1] == ["branch"] and len(rest) > 1 and rest[1].startswith("task/"):
            name = rest[1]
        if name:
            _zond_git_original("branch", "-f", name, "HEAD")
    elif mode == "worktree":
        if rest[:2] == ["worktree", "add"] and not creates:
            path = next(a for a in rest[2:] if not a.startswith("-"))
            twin = path.rstrip("/") + "-glavnaya"
            _zond_git_original("worktree", "add", "--detach", twin, "HEAD")
            _zond_twins[str(_Path(path).resolve())] = twin
        elif rest[:2] == ["worktree", "remove"]:
            path = str(_Path(rest[-1]).resolve())
            twin = _zond_twins.pop(path, None)
            if twin:
                _zond_git_original("worktree", "remove", "--force", twin)
'''


def run_new_tests(tree: Path, classes: list, mutation: str | None
                  ) -> subprocess.CompletedProcess:
    if mutation is not None:
        gitcmd_py = tree / "orchestrator" / "gitcmd.py"
        gitcmd_py.write_text(gitcmd_py.read_text(encoding="utf-8") + MUTATION,
                             encoding="utf-8")
    env = dict(os.environ)
    env.pop("ARTEL_PLANK_MUTATION", None)
    if mutation is not None:
        env["ARTEL_PLANK_MUTATION"] = mutation
    nodes = [f"{INVARIANTS_TEST}::{name}" for name in classes]
    try:
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "-x", *nodes], cwd=tree, env=env, capture_output=True, text=True,
            timeout=NEW_TEST_TIMEOUT_SEC)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(exc.cmd, None, exc.stdout or "",
                                           f"прогон превысил {NEW_TEST_TIMEOUT_SEC} с")


def invariant_row(text: str, number: int) -> str:
    rows = [ln for ln in text.splitlines()
            if re.match(rf"\|\s*{number}\s*\|", ln)]
    return rows[0] if rows else ""


class InvariantsAppendixTest(PlanSource):

    def setUp(self):
        self.plan_md = self.plan()
        self.tree = applied_tree(self, self.plan_md)

    def test_ac14_appendix_covers_invariants_and_applies(self):
        """PLAN несёт приложения к `docs/invariants.md` и
        `tests/test_invariants.py`, их применимость подтверждена строкой
        `git apply --check`; в копии дерева они накладываются по порядку.
        После наложения строки инвариантов 20 и 21 говорят о любом
        проекте, включая артель, строка 21 называет `worktrees/` каталогом
        роли; есть новая строка инварианта о неизменности git главной
        копии; в `tests/test_invariants.py` есть новый класс с тестами.

        Ловит мутацию: приложение ко второму защищённому пути забыто или
        его хунк не накладывается на текущий файл (`git apply --check`
        отказывает).
        """
        paths = {p for a in appendices(self.plan_md) for p in a.paths}
        self.assertIn(INVARIANTS_DOC, paths)
        self.assertIn(INVARIANTS_TEST, paths)
        self.assertIn("git apply --check", self.plan_md)

        applied = (self.tree / INVARIANTS_DOC).read_text(encoding="utf-8")
        base = (code_dir() / INVARIANTS_DOC).read_text(encoding="utf-8")
        row20, row21 = invariant_row(applied, 20), invariant_row(applied, 21)
        self.assertTrue(any(w in row20 for w in ANY_PROJECT), row20)
        self.assertTrue(any(w in row21 for w in ANY_PROJECT), row21)
        self.assertIn("worktrees/", row21)
        new_rows = [ln for ln in applied.splitlines()
                    if ln.startswith("|") and ln not in base.splitlines()
                    and "главн" in ln and ("не меня" in ln or "неизмен" in ln)]
        self.assertTrue(new_rows, "нет строки инварианта «git главной копии "
                                  "пульта не меняется в ходе задачи»")
        self.assertTrue(new_test_classes(self.tree),
                        "приложение не добавляет класса с тестами в "
                        "tests/test_invariants.py")

    def run_mutation(self, mutation: str | None) -> subprocess.CompletedProcess:
        classes = new_test_classes(self.tree)
        self.assertTrue(classes, "нового теста инварианта нет")
        return run_new_tests(self.tree, classes, mutation)

    def test_ac14_new_invariant_test_is_green_on_the_task_code(self):
        """Новый тест инварианта из приложения — зелёный на коде задачи
        (копия дерева с наложенными приложениями, без мутаций).

        Ловит мутацию: тест приложения проверяет не тот объект и падает на
        исправном коде (например, ждёт клон там, где его не заводит
        `new`).
        """
        res = self.run_mutation(None)
        self.assertEqual(res.returncode, 0, f"{res.stdout[-3000:]}\n{res.stderr[-2000:]}")

    def test_ac14_new_invariant_test_reddens_on_task_branch_in_main_copy(self):
        """Мутация «ветка»: каждое заведение ветки задачи в клоне
        повторяется веткой в git главной копии. Новый тест инварианта
        красен.

        Ловит мутацию: тест сверяет только рабочие копии (или только
        HEAD) главной копии — ветка задачи в её `refs/heads` проходит.
        """
        res = self.run_mutation("branch")
        self.assertNotEqual(res.returncode, 0,
                            f"тест зелёный при ветке задачи в главной копии:\n"
                            f"{res.stdout[-2000:]}")

    def test_ac14_new_invariant_test_reddens_on_merge_copy_in_main_copy(self):
        """Мутация «рабочая копия»: каждая рабочая копия клона, заводимая
        не под новую ветку (временная рабочая копия мержа), повторяется
        рабочей копией в git главной копии на время своей жизни. Новый
        тест инварианта красен.

        Ловит мутацию: тест сверяет `git worktree list` главной копии
        только в конце прогона — временная рабочая копия мержа, снятая к
        `done`, проходит незамеченной.
        """
        res = self.run_mutation("worktree")
        self.assertNotEqual(res.returncode, 0,
                            f"тест зелёный при рабочей копии мержа в главной "
                            f"копии:\n{res.stdout[-2000:]}")


# -------------------------------------------------------------------- AC-15

ADR_POINT = re.compile(r"п\.\s*\d+")


def changed_test_files() -> list:
    """(статус, путь) файлов `tests/` диффа задачи от точки расхождения."""
    base = base_sha()
    if not base:
        raise AssertionError("база диффа задачи не определена")
    res = git("diff", "--name-status", "-M", base, "HEAD", "--", "tests/")
    if res.returncode != 0:
        raise AssertionError(f"git diff: {res.stderr}")
    rows = []
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        rows.append((parts[0], parts[-1]))
    return rows


class TestChangesListedInPlanTest(PlanSource):

    def test_ac15_changed_existing_tests_are_listed_with_adr_point(self):
        """Каждый существующий файл `tests/`, изменённый, удалённый или
        переименованный задачей (в том числе
        `tests/test_multitarget_invariants.py`), назван в PLAN строкой,
        несущей ссылку на пункт ADR-0021 («ADR-0021 … п. N»).

        Ловит мутацию: правка существующего теста под новую механику
        (ожидание `.artel/worktrees/`) не попала в перечень PLAN — строки
        с именем файла и пунктом ADR-0021 нет.
        """
        plan = self.plan()
        existing = [path for status, path in changed_test_files()
                    if not status.startswith("A")
                    and not path.startswith(LONG_LIVED_PREFIX)]
        missing = []
        for path in existing:
            name = Path(path).name
            if not any(name in ln and "ADR-0021" in ln and ADR_POINT.search(ln)
                       for ln in plan.splitlines()):
                missing.append(path)
        self.assertEqual(missing, [], "изменения тестов без строки PLAN с "
                                      "пунктом ADR-0021")

    def test_ac15_new_and_changed_tests_carry_mutation_claims(self):
        """В диффе задачи есть тесты `tests/` (новые либо изменённые
        `test_*.py`); у каждого нового и изменённого метода `test_*` в них
        — заявка «Ловит мутацию: …».

        Ловит мутацию: тесты требований 1–7 в `tests/` не написаны либо
        новый метод сдан без заявки мутации.
        """
        self.plan()
        base = base_sha()
        files = [(status, path) for status, path in changed_test_files()
                 if not status.startswith("D") and Path(path).name.startswith("test_")
                 and path.endswith(".py")]
        self.assertTrue(files, "в диффе задачи нет тестов tests/")
        without = []
        for status, path in files:
            head = (code_dir() / path).read_text(encoding="utf-8")
            before = None if status.startswith("A") else file_at(base, path)
            for name in guard.test_functions_without_mutation_claim(before, head):
                without.append(f"{path}::{name}")
        self.assertEqual(without, [], "методы без заявки «Ловит мутацию»")


if __name__ == "__main__":
    unittest.main()
