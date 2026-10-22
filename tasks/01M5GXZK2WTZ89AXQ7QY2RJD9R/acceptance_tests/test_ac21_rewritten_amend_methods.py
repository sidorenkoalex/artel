"""AC-21: три метода, закреплявшие временный отказ `LABELLED_REFUSAL`, остаются в наборе со всеми прежними случаями и ждут прохода; константы `AMEND_REFUSAL` и общие помощники не тронуты.

Группа: разовый
Красен до реализации: методы ещё утверждают отказ G3б (`assertIn(AMEND_REFUSAL, …)`) и на коде базы ветки зелены — на базе они не падают ни в одном случае.

Факт задачи — правка двух существующих файлов `tests/` по мандату Оператора
(ANSWER-1, условия 1–5): исходные тексты на голове рабочей копии и на базе
диффа (`_pult.DIFF_BASE`, чтение `git show`). Чувствительность нового
ожидания проверяется прогоном: на ветке задачи три метода зелёные; те же
методы (файлы головы) в рабочей копии базы — где `amend-tests` ещё отказывает
файлам с меткой — красны в каждом прежнем случае (у метода рабочей копии —
четыре упавших подслучая, у `--from-branch` — два, у `Ac25` — сам метод):
так «проход» каждого случая наблюдается без чтения устройства метода.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

LABELLED = "tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py"
FAIL_TO_PASS = "tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py"
AC11 = "Ac11AmendLabelledRefusalTest"
AC25 = "Ac25AmendAndTemplateTest"
WORKTREE = "test_ac11_worktree_mode_refuses_labelled_files"
FROM_BRANCH = "test_ac11_from_branch_mode_refuses_labelled_files"
MD_ONLY = "test_ac25_amend_md_only_plank_labelled_long_lived_refused"
NODES = {f"{LABELLED}::{AC11}::{WORKTREE}": 4,
         f"{LABELLED}::{AC11}::{FROM_BRANCH}": 2,
         f"{FAIL_TO_PASS}::{AC25}::{MD_ONLY}": 1}
ALLOWED = {(LABELLED, AC11, WORKTREE), (LABELLED, AC11, FROM_BRANCH),
           (FAIL_TO_PASS, AC25, MD_ONLY)}
CONSTANT = "AMEND_REFUSAL"
SHARED = ("LabelledSandbox", "CarryOverSandbox", "FailToPassSandbox")

REPO_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR",
            "GIT_NAMESPACE", "GIT_PREFIX")


def clean_env() -> dict:
    """Окружение без переменных, которыми git находит репозиторий в обход
    `-C` (тот же перечень, что у помощника пульта)."""
    return {k: v for k, v in os.environ.items() if k not in REPO_ENV}


def git_show(rel: str) -> str:
    res = subprocess.run(["git", "-C", CODE_ROOT, "show", f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True, timeout=60,
                         env=clean_env())
    if res.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{rel}: {res.stderr}")
    return res.stdout


def head_text(rel: str) -> str:
    return (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")


def parts(source: str) -> dict:
    """{(класс, имя): исходный текст} функций классов и модуля (класс —
    "" у функций модуля), {(имя класса, None): текст класса}."""
    tree = ast.parse(source)
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[("", node.name)] = ast.get_source_segment(source, node)
        if isinstance(node, ast.ClassDef):
            out[(node.name, None)] = ast.get_source_segment(source, node)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[(node.name, item.name)] = ast.get_source_segment(
                        source, item)
    return out


def constant_value(source: str):
    """Значение модульного присваивания `AMEND_REFUSAL`; `None` — его нет."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == CONSTANT for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def constant_uses(source: str) -> list:
    """(строка, вызов-владелец или "") каждого чтения имени `AMEND_REFUSAL`."""
    tree = ast.parse(source)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == CONSTANT and \
                isinstance(node.ctx, ast.Load):
            owner = parents.get(node)
            call = ""
            if isinstance(owner, ast.Call) and node in owner.args and \
                    isinstance(owner.func, ast.Attribute):
                call = owner.func.attr
            uses.append((node.lineno, call))
    return uses


def run_nodes(cwd: str, nodes) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pytest", *nodes, "-q",
                           "-rA", "-p", "no:cacheprovider"], cwd=cwd,
                          capture_output=True, text=True, timeout=110,
                          env=clean_env())


class Ac21RewrittenMethodsTest(unittest.TestCase):

    def test_ac21_constants_helpers_and_other_methods_unchanged(self):
        """Константы `AMEND_REFUSAL` прежнего значения или удалены и читаются только в `assertNotIn`; помощники-песочницы и прочие методы обоих файлов равны базе.

        Сценарий: для каждого из двух файлов — разбор головы и базы.
        Константа: на голове её нет либо значение равно базе; каждое её
        чтение — первый-второй аргумент `assertNotIn`. Классы
        `LabelledSandbox`, `CarryOverSandbox`, `FailToPassSandbox` (те, что
        есть в файле) и каждая функция базы вне трёх методов мандата и
        помощников класса `Ac11AmendLabelledRefusalTest` — исходный текст
        равен базе; три метода на голове есть.

        Ловит мутацию: метод оставлен с `assertIn(AMEND_REFUSAL, …)` —
        чтение константы вне `assertNotIn`; значение константы сменено на
        новый текст; правка общего помощника `LabelledSandbox.locked_task`
        не входит в мандат — текст иной; метод удалён — его нет на голове.
        """
        for rel in (LABELLED, FAIL_TO_PASS):
            head, base = head_text(rel), git_show(rel)
            with self.subTest(rel=rel, part="константа"):
                value = constant_value(head)
                self.assertIn(value, (None, constant_value(base)))
                for line, call in constant_uses(head):
                    self.assertEqual(call, "assertNotIn",
                                     f"{rel}:{line}: {CONSTANT} вне assertNotIn")
            head_parts, base_parts = parts(head), parts(base)
            for cls in SHARED:
                if (cls, None) in base_parts:
                    with self.subTest(rel=rel, cls=cls):
                        self.assertEqual(head_parts.get((cls, None)),
                                         base_parts[(cls, None)])
            for (cls, name), text in base_parts.items():
                if name is None or (rel, cls, name) in ALLOWED or \
                        (rel == LABELLED and cls == AC11):
                    continue
                with self.subTest(rel=rel, cls=cls, name=name):
                    self.assertEqual(head_parts.get((cls, name)), text)
            for path, cls, name in ALLOWED:
                if path == rel:
                    with self.subTest(rel=rel, method=name):
                        self.assertIn((cls, name), head_parts)

    def test_ac21_methods_pass_on_branch(self):
        """Три переписанных метода проходят на коде ветки задачи.

        Ловит мутацию: метод ждёт прохода, а `amend-tests` по-прежнему
        отказывает файлам с меткой либо отказывает годной правке
        долгоживущего файла — метод красен, код выхода pytest не 0.
        """
        res = run_nodes(CODE_ROOT, list(NODES))
        self.assertEqual(res.returncode, 0, res.stdout[-4000:] + res.stderr[-2000:])

    def test_ac21_methods_fail_on_base_in_every_case(self):
        """Те же методы (тексты головы) в рабочей копии базы ветки, где `amend-tests` отказывает файлам с меткой, красны в каждом прежнем случае.

        Сценарий: временная рабочая копия `git worktree add --detach` на
        базе диффа; два файла тестов кладутся туда с головы; прогон трёх
        узлов. Метод рабочей копии — не меньше четырёх упавших подслучаев,
        `--from-branch` — не меньше двух, `Ac25` — упал.

        Ловит мутацию: метод переписан, но по-прежнему проходит и на отказе
        G3б (утверждение отказа заменено на проверку «что-то выведено») —
        на базе зелен; прежний случай выброшен из метода — упавших
        подслучаев меньше прежнего числа.
        """
        tmp = tempfile.mkdtemp(prefix="ac21-base-")
        base_dir = str(Path(tmp) / "base")
        add = subprocess.run(["git", "-C", CODE_ROOT, "worktree", "add", "-q",
                              "--detach", base_dir, DIFF_BASE],
                             capture_output=True, text=True, timeout=60,
                         env=clean_env())
        self.assertEqual(add.returncode, 0, add.stderr)
        try:
            for rel in (LABELLED, FAIL_TO_PASS):
                shutil.copyfile(Path(CODE_ROOT) / rel, Path(base_dir) / rel)
            res = run_nodes(base_dir, list(NODES))
        finally:
            subprocess.run(["git", "-C", CODE_ROOT, "worktree", "remove",
                            "--force", base_dir], capture_output=True,
                           timeout=60, env=clean_env())
            shutil.rmtree(tmp, ignore_errors=True)
        out = res.stdout
        self.assertNotEqual(res.returncode, 0, out[-4000:])
        for node, cases in NODES.items():
            with self.subTest(node=node):
                kind = "SUBFAILED" if cases > 1 else "FAILED"
                failed = len(re.findall(rf"^{kind}\b[^\n]*{re.escape(node)}",
                                        out, re.M))
                self.assertGreaterEqual(failed, cases, out[-4000:])


if __name__ == "__main__":
    unittest.main()
