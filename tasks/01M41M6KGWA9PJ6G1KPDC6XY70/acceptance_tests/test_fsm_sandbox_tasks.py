"""Песочница `FsmTest` не сорит в каталог задач корня запуска; сторож и неизменность утверждений (AC-7, AC-8, AC-9).

Группа: разовый

Красен до реализации: в ссылке документов задачи ещё нет PLAN.md с приложением к `tests/test_invariants.py` — чтение PLAN/наложение приложения отказывает.

Группа «разовый»: предмет — `tests/test_invariants.py` в дереве ветки с
наложенным приложением PLAN этой задачи (SPEC, преамбула «Критериев
приёмки»); после мержа приложения проверять не на чем.

«Корень запуска» — копия дерева ветки с наложенным приложением
(`_plank.applied_tree`): `config.ROOT` там вычисляется от расположения
`orchestrator/config.py`, то есть указывает на саму копию, и её `tasks/`
— «настоящий `config.TASKS` корня запуска». Прогоны идут отдельным
процессом с рабочим каталогом в копии, рабочую копию кода они не трогают.
"""
import ast
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from collections import Counter
from pathlib import Path

from _plank import (INV_REL, appendices_or_fail, apply_appendices,
                    applied_tree, clean_tree, git)

PYTEST = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
          "-p", "timeout", "-o", "timeout=120", "-q"]

# Зонд AC-7: подкласс `FsmTest` в копии; внутри теста фиксирует
# `config.TASKS`, `self.tdir` и содержимое настоящего `<корень>/tasks/`.
PROBE = textwrap.dedent('''
    import json, os, sys, unittest
    from pathlib import Path
    sys.path.insert(0, os.getcwd())
    from orchestrator import config
    real = Path(config.TASKS).resolve()
    listing = lambda: sorted(os.listdir(real)) if real.is_dir() else []
    seen = {"real": str(real), "before": listing()}
    import tests.test_invariants as ti

    class Probe(ti.FsmTest):
        def runTest(self):
            seen["tasks"] = str(Path(config.TASKS).resolve())
            seen["tdir"] = str(Path(self.tdir).resolve())
            seen["tdir_is_dir"] = Path(self.tdir).is_dir()
            seen["during"] = listing()

    result = unittest.TestResult()
    Probe().run(result)
    seen["errors"] = [str(e[1])[-2000:] for e in result.errors + result.failures]
    seen["after"] = listing()
    print("PROBE=" + json.dumps(seen))
''')


def classes(text: str) -> dict[str, ast.ClassDef]:
    return {n.name: n for n in ast.parse(text).body
            if isinstance(n, ast.ClassDef)}


def fsm_family(text: str) -> set[str]:
    """`FsmTest` и все его наследники модуля (транзитивно)."""
    cls = classes(text)
    family, grew = {"FsmTest"}, True
    while grew:
        grew = False
        for name, node in cls.items():
            bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
            if name not in family and bases & family:
                family.add(name)
                grew = True
    return family


def method_index(text: str) -> dict[tuple[str, str], ast.FunctionDef]:
    return {(c.name, f.name): f
            for c in classes(text).values() for f in c.body
            if isinstance(f, ast.FunctionDef) and f.name.startswith("test")}


def method_node(text: str, cls: str, name: str) -> ast.FunctionDef:
    node = classes(text)[cls]
    return next(f for f in node.body
                if isinstance(f, ast.FunctionDef) and f.name == name)


def asserts(fn: ast.FunctionDef) -> Counter:
    out = Counter()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            out[ast.unparse(node)] += 1
        elif isinstance(node, ast.Call):
            f = node.func
            name = (f.attr if isinstance(f, ast.Attribute)
                    else f.id if isinstance(f, ast.Name) else "")
            if name.startswith("assert") or name in ("fail", "skipTest"):
                out[ast.unparse(node)] += 1
    return out


def original_text(case) -> str:
    res = git("show", f"HEAD:{INV_REL}")
    case.assertEqual(res.returncode, 0, res.stderr)
    return res.stdout


def tasks_listing(root: Path) -> list[str]:
    d = root / "tasks"
    return sorted(os.listdir(d)) if d.is_dir() else []


def run_pytest(tree: Path, *node_ids: str) -> subprocess.CompletedProcess:
    return subprocess.run([*PYTEST, *node_ids], cwd=tree, capture_output=True,
                          text=True, timeout=110)


class FsmSandboxTasksTest(unittest.TestCase):

    def test_ac7_fsm_sandbox_keeps_tasks_out_of_run_root(self):
        """`FsmTest.setUp` подменяет `config.TASKS` временным каталогом; прогон наследников не меняет `<корень>/tasks/`.

        Сценарий: в копии с наложенным приложением отдельным процессом
        запускается зонд — подкласс `FsmTest`; внутри теста `config.TASKS`
        не равен настоящему `<корень>/tasks`, `self.tdir` существует и
        лежит под подменённым `config.TASKS`, а набор записей настоящего
        `<корень>/tasks/` во время теста и после него равен набору до.
        Затем pytest прогоняет случайный (зерно печатается) тестовый метод
        наследника `FsmTest` и набор записей `<корень>/tasks/` снова
        сравнивается с исходным.

        Ловит мутацию: подмена `config.TASKS` не добавлена (`self.tdir`
        создаётся в настоящем `tasks/` корня — запись видна в наборе во
        время теста); подмена есть, но `self.tdir` по-прежнему строится от
        сохранённого настоящего пути; временный каталог заведён внутри
        `<корень>/tasks/` (новая запись в наборе).
        """
        tree = applied_tree(self)
        text = (tree / INV_REL).read_text(encoding="utf-8")
        before = tasks_listing(tree)

        probe = Path(tempfile.mkdtemp(prefix="artel-ci-min-probe-")) / "probe.py"
        self.addCleanup(shutil.rmtree, probe.parent, ignore_errors=True)
        probe.write_text(PROBE, encoding="utf-8")
        res = subprocess.run([sys.executable, str(probe)], cwd=tree,
                             capture_output=True, text=True, timeout=110)
        line = next((ln for ln in res.stdout.splitlines()
                     if ln.startswith("PROBE=")), None)
        self.assertIsNotNone(line, f"зонд не отчитался: {res.stderr[-2000:]}")
        seen = json.loads(line[len("PROBE="):])
        self.assertEqual(seen["errors"], [], "setUp зонда FsmTest упал")
        real = Path(seen["real"])
        tasks = Path(seen["tasks"])
        tdir = Path(seen["tdir"])
        self.assertNotEqual(tasks, real,
                            "FsmTest.setUp не подменяет config.TASKS")
        self.assertFalse(tasks.is_relative_to(real),
                         f"подменённый config.TASKS {tasks} лежит под {real}")
        self.assertTrue(seen["tdir_is_dir"], "self.tdir не создан")
        self.assertTrue(tdir.is_relative_to(tasks),
                        f"self.tdir {tdir} не под config.TASKS {tasks}")
        self.assertFalse(tdir.is_relative_to(real),
                         f"self.tdir {tdir} лежит в настоящем {real}")
        self.assertEqual(seen["during"], seen["before"],
                         "во время теста в <корень>/tasks/ появились записи")
        self.assertEqual(seen["after"], seen["before"],
                         "после теста набор <корень>/tasks/ изменился")

        seed = random.randrange(2 ** 32)
        print(f"зерно: {seed}")
        family = fsm_family(text) - {"FsmTest"}
        candidates = sorted(f"{INV_REL}::{c}::{m}"
                            for (c, m) in method_index(text) if c in family)
        self.assertTrue(candidates, "у FsmTest нет наследников с тестами")
        node_id = random.Random(seed).choice(candidates)
        run_pytest(tree, node_id)
        self.assertEqual(tasks_listing(tree), before,
                         f"прогон {node_id} изменил набор <корень>/tasks/ "
                         f"(зерно: {seed})")

    def test_ac8_new_guard_method_catches_reverted_setup(self):
        """Новый метод с заявкой «Ловит мутацию» зелёный с правкой `setUp` и красный, когда `FsmTest.setUp` откатан к версии ветки.

        Сценарий: новые тестовые методы приложения — пары (класс, метод),
        которых нет в `tests/test_invariants.py` HEAD ветки, с «Ловит
        мутацию» в докстринге. В копии с наложенным приложением хотя бы
        один из них проходит pytest; во второй копии, где тело
        `FsmTest.setUp` заменено исходным из HEAD ветки (остальное — как
        после приложения), тот же метод падает (код выхода pytest 1 —
        тесты упали, не ошибка сбора).

        Ловит мутацию: сторож не добавлен или без заявки «Ловит мутацию»
        в докстринге; сторож проверяет отсутствие каталога задачи в
        настоящем `tasks/` только после `doCleanups` — исходный
        `addCleanup(shutil.rmtree, self.tdir)` его уже убрал, и сторож
        зелёный и на откатанном `setUp` (провал «ни один новый метод не
        красный с откатанной»).
        """
        tree = applied_tree(self)
        applied = (tree / INV_REL).read_text(encoding="utf-8")
        original = original_text(self)
        old_methods = set(method_index(original))
        new = [(c, m) for (c, m), fn in method_index(applied).items()
               if (c, m) not in old_methods
               and "Ловит мутацию" in (ast.get_docstring(fn) or "")]
        self.assertTrue(new, "в приложении нет нового тестового метода "
                             "с заявкой «Ловит мутацию»")

        orig_setup = method_node(original, "FsmTest", "setUp")
        app_setup = method_node(applied, "FsmTest", "setUp")
        orig_lines = original.splitlines(keepends=True)
        app_lines = applied.splitlines(keepends=True)
        orig_src = "".join(orig_lines[orig_setup.lineno - 1:orig_setup.end_lineno])
        app_src = "".join(app_lines[app_setup.lineno - 1:app_setup.end_lineno])
        self.assertTrue(orig_src != app_src, "приложение не правит FsmTest.setUp")
        mutant_text = "".join(app_lines[:app_setup.lineno - 1] + [orig_src]
                              + app_lines[app_setup.end_lineno:])
        mutant = clean_tree("artel-ci-min-mutant-")
        self.assertEqual(apply_appendices(mutant, appendices_or_fail(self)), [])
        (mutant / INV_REL).write_text(mutant_text, encoding="utf-8")

        report = []
        for cls, name in new:
            node_id = f"{INV_REL}::{cls}::{name}"
            green = run_pytest(tree, node_id)
            red = run_pytest(mutant, node_id)
            report.append((node_id, green.returncode, red.returncode))
            if green.returncode == 0 and red.returncode == 1:
                return
        self.fail(f"ни один новый метод не зелёный с правкой setUp и "
                  f"красный с откатанной (метод, код с правкой, код без): "
                  f"{report}")

    def test_ac9_existing_assertions_not_removed(self):
        """Каждый тестовый метод `tests/test_invariants.py` из HEAD ветки на месте и сохраняет все свои утверждения.

        Сценарий: для каждой пары (класс, метод `test*`) исходного файла
        в файле после приложения есть та же пара, и мультимножество её
        утверждений (`assert*`/`fail`/`skipTest`-вызовы и оператор
        `assert`, нормализованные `ast.unparse`) в исходном входит в
        мультимножество после приложения.

        Ловит мутацию: чтобы позеленить тест, читающий SPEC через
        `config.ROOT/tasks`, приложение удаляет или ослабляет его
        `assertEqual`/`assertIn` (например, `assertEqual` → `assertTrue`
        или сравнение с другим ожиданием); существующий метод удалён или
        переименован.
        """
        applied = (applied_tree(self) / INV_REL).read_text(encoding="utf-8")
        before = method_index(original_text(self))
        after = method_index(applied)
        missing = sorted(f"{c}.{m}" for (c, m) in before if (c, m) not in after)
        self.assertEqual(missing, [], "существующие тестовые методы пропали")
        weakened = {}
        for key, fn in before.items():
            lost = asserts(fn) - asserts(after[key])
            if lost:
                weakened[f"{key[0]}.{key[1]}"] = sorted(lost)
        self.assertEqual(weakened, {}, "утверждения существующих методов "
                                       "удалены или изменены")


if __name__ == "__main__":
    unittest.main()
