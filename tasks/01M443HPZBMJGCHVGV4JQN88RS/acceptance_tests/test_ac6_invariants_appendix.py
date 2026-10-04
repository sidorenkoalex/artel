"""Приложение PLAN к `tests/test_invariants.py`: применяется, убирает подмены, несёт свой сторож (AC-6).

Группа: разовый

Красен до реализации: в ссылке документов задачи ещё нет PLAN.md — чтение PLAN из ссылки отказывает.

Группа «разовый»: предмет — PLAN.md этой задачи и его приложение; после
мержа проверять не на чем (свойство самого `tests/test_invariants.py`
дальше держит добавленный приложением метод).

PLAN.md читается из ссылки документов `refs/artifacts/<id>`
(`gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`), не с диска;
приложения разбирает тот же узел, что гейт приложений PLAN
(`guard.plan_appendices`), и кладёт подряд на копию чистого дерева HEAD
ветки (`git archive HEAD` + свой `git init`).
"""
import ast
import re
import subprocess
import sys
import unittest

from _plank import (INV_REL, appendices_or_fail, clean_tree, git,
                    global_sleep_patches)

ADDED_TEST = re.compile(r"^\+\s*def (test_\w+)\s*\(", re.MULTILINE)
PROBE = ('\n\ndef _sleep_guard_probe():\n'
         '    from unittest import mock\n'
         '    return mock.patch("time.sleep")\n')


def _node_ids(source: str, names: set[str]) -> list[str]:
    """Адреса pytest `<файл>::<Класс>::<метод>` методов `names` исходника."""
    ids = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef):
            ids += [f"{INV_REL}::{node.name}::{item.name}" for item in node.body
                    if isinstance(item, ast.FunctionDef) and item.name in names]
        elif isinstance(node, ast.FunctionDef) and node.name in names:
            ids.append(f"{INV_REL}::{node.name}")
    return ids


def _run(tree, ids: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *ids, "-q", "-p", "no:cacheprovider"],
        cwd=tree, capture_output=True, text=True, timeout=100)


class InvariantsAppendixTest(unittest.TestCase):

    def test_ac6_appendix_applies_removes_patches_and_adds_green_guard(self):
        """Приложение PLAN к `tests/test_invariants.py` проходит `git apply --check`, после наложения подмен нет, добавленный метод-сторож зелёный.

        Сценарий: среди приложений PLAN есть приложение к
        `tests/test_invariants.py`; на копии чистого дерева HEAD ветки
        каждое приложение по порядку проходит `git apply --check` и
        ложится `git apply`. В наложенном `tests/test_invariants.py` поиск
        сторожа задачи (`global_sleep_patches`) находок не даёт. Приложение
        добавляет хотя бы один метод `def test_…`; добавленные методы
        зелёные в наложенном дереве, а после дописки в конец файла функции
        с `mock.patch("time.sleep")` хотя бы один из них краснеет — он
        действительно прогоняет поиск по исходнику `tests/test_invariants.py`.

        Ловит мутацию: хунк приложения с диапазоном, не совпадающим с
        текущим файлом (`git apply --check` отказывает); приложение правит
        строку ~702 и забывает ~1343 (`mock.patch.object(runner.time,
        "sleep", …)` — находка поиска); добавленный метод проверяет
        другой файл или константу, а не исходник `tests/test_invariants.py`
        (дописанная подмена его не красит).
        """
        appendices = appendices_or_fail(self)
        mine = [a for a in appendices if INV_REL in a.paths]
        self.assertTrue(mine, f"в PLAN нет приложения к {INV_REL}")

        tree = clean_tree("artel-sleep-guard-applied-")
        for appendix in appendices:
            for args in (["--check"], []):
                res = git("apply", *args, "-", cwd=tree, input=appendix.diff)
                self.assertEqual(
                    res.returncode, 0,
                    f"git apply {' '.join(args)} приложения {appendix.paths}: "
                    f"{(res.stderr or res.stdout).strip()[:500]}")

        target = tree / INV_REL
        applied = target.read_text(encoding="utf-8")
        findings = global_sleep_patches(applied, INV_REL)
        self.assertEqual(findings, [], "\n".join(findings))

        added = {n for a in mine for n in ADDED_TEST.findall(a.diff)}
        ids = _node_ids(applied, added)
        self.assertTrue(ids, f"приложение не добавляет в {INV_REL} "
                             f"ни одного метода def test_…")
        green = _run(tree, ids)
        self.assertEqual(green.returncode, 0,
                         f"добавленные методы {ids} не зелёные:\n"
                         f"{green.stdout[-3000:]}\n{green.stderr[-1000:]}")

        target.write_text(applied + PROBE, encoding="utf-8")
        red = _run(tree, ids)
        self.assertEqual(red.returncode, 1,
                         f"добавленные методы {ids} не замечают "
                         f"mock.patch(\"time.sleep\") в {INV_REL}:\n"
                         f"{red.stdout[-2000:]}")


if __name__ == "__main__":
    unittest.main()
