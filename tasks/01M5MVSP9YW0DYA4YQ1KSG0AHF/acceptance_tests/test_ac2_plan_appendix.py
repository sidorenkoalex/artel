"""Приложение 1 PLAN к `tests/test_invariants.py`: дословно из SPEC, применяется к ветке, с ним линт-класс зелёный; к PLAN приложено сравнение разборов.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё нет — `artifact_text("PLAN.md")` возвращает `None`; модуля `orchestrator/test_lint.py` нет — приложение импортирует его, и `DeterministicTestsLintTest` с приложением не собирается.

Источник SPEC.md и PLAN.md — ссылка документов задачи через помощник пульта
`_pult.artifact_text`; применимость — `_pult.apply_check` к дереву HEAD
рабочей копии кода. Прогон класса с приложением — во временной копии:
каталог `tests/` рабочей копии скопирован, приложение наложено `git apply`
на копию `tests/test_invariants.py` (если оно уже в дереве — копия как
есть), остальные каталоги рабочей копии — символическими ссылками.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

TARGET = "tests/test_invariants.py"
LINT_CLASS = "DeterministicTestsLintTest"
FROZEN_TEST = "test_rule_corpus_is_frozen"
FENCE = re.compile(r"```diff\n(.*?)\n```", re.S)
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
           "GIT_COMMON_DIR", "GIT_PREFIX")


def appendix(text: str) -> str | None:
    """Блок ```diff```, правящий `tests/test_invariants.py`, с переводом
    строки в конце; `None` — блока нет."""
    for match in FENCE.finditer(text or ""):
        body = match.group(1)
        if body.startswith(f"diff --git a/{TARGET} b/{TARGET}"):
            return body + "\n"
    return None


class PlanAppendixTest(unittest.TestCase):

    def plan_diff(self) -> str:
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md нет в ссылке документов задачи")
        diff = appendix(plan)
        self.assertIsNotNone(diff, f"в PLAN.md нет приложения к {TARGET}")
        return diff

    def test_ac2_appendix_verbatim_and_applies(self):
        """Приложение к `tests/test_invariants.py` в PLAN побайтно равно приложению SPEC и применяется к ветке.

        Сценарий: из SPEC.md и PLAN.md ссылки документов извлекается блок
        ```diff```, начинающийся с `diff --git a/tests/test_invariants.py`;
        блоки равны побайтно. `git apply --check` блока к дереву HEAD
        рабочей копии проходит — либо проходит обратное наложение (Оператор
        уже внёс приложение в ветку).

        Ловит мутацию: разработчик правит текст приложения (меняет образцы
        `_RULE_CORPUS`, тексты находок или перечень `_EXCEPTIONS`) — блоки
        расходятся; хедер хунка не совпадает с файлом ветки — `git apply
        --check` отказывает в обе стороны.
        """
        spec_diff = appendix(artifact_text("SPEC.md"))
        self.assertIsNotNone(spec_diff, f"в SPEC.md нет приложения к {TARGET}")
        self.assertEqual(spec_diff, self.plan_diff(),
                         "приложение PLAN расходится с приложением SPEC")
        forward = apply_check(spec_diff)
        if forward:
            self.assertEqual("", apply_check(spec_diff, reverse=True),
                             f"приложение не применяется к ветке:\n{forward}")

    def test_ac2_lint_class_green_with_appendix(self):
        """С приложением `DeterministicTestsLintTest` целиком зелёный, включая `test_rule_corpus_is_frozen` и проверку перечня `_EXCEPTIONS`.

        Сценарий: временная копия рабочей копии кода (каталог `tests/`
        скопирован, прочее — ссылками); если приложение ещё не в дереве,
        оно накладывается `git apply` на копию `tests/test_invariants.py`.
        `pytest tests/test_invariants.py -k DeterministicTestsLintTest` в
        копии завершается кодом 0, и `test_rule_corpus_is_frozen` в выводе
        пройден.

        Ловит мутацию: `orchestrator/test_lint.py` отдаёт другие тексты
        находок или пропускает вид нарушения — закреплённый набор образцов
        краснеет; перенос сместил адреса «файл::метод» — дерево `tests/`
        получает нарушения вне перечня `_EXCEPTIONS`.
        """
        diff = self.plan_diff()
        root = Path(CODE_ROOT)
        tmp = Path(tempfile.mkdtemp(prefix="ac2-appendix-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for entry in root.iterdir():
            if entry.name in (".git", "tests", "tasks") or entry.name.startswith("."):
                continue
            os.symlink(entry, tmp / entry.name)
        shutil.copytree(root / "tests", tmp / "tests",
                        ignore=shutil.ignore_patterns("__pycache__"))
        env = {k: v for k, v in os.environ.items() if k not in GIT_ENV}
        env["GIT_CEILING_DIRECTORIES"] = str(tmp.parent)
        if apply_check(diff) == "":
            patch = tmp / "appendix.diff"
            patch.write_text(diff, encoding="utf-8")
            res = subprocess.run(["git", "apply", str(patch)], cwd=tmp, env=env,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(res.returncode, 0, f"git apply: {res.stderr}")
            patch.unlink()
        run = subprocess.run(
            [sys.executable, "-m", "pytest", TARGET, "-k", LINT_CLASS,
             "-p", "no:cacheprovider", "-q", "-rA"],
            cwd=tmp, env=env, capture_output=True, text=True, timeout=100)
        output = run.stdout + run.stderr
        self.assertEqual(run.returncode, 0, output[-4000:])
        self.assertRegex(output, rf"PASSED [^\n]*{LINT_CLASS}::{FROZEN_TEST}",
                         output[-4000:])

    def test_ac2_plan_carries_equivalence_output(self):
        """К PLAN приложен вывод однократного сравнения `test_lint.findings` с прежним разбором — с числом ключей.

        Сценарий: PLAN.md ссылки документов называет `test_lint.findings`
        и несёт строку, где сказано о ключах и стоит число (число ключей
        сравнения на дереве `tests/`). Побайтное равенство по существу
        сверяет ревьювер по самому выводу.

        Ловит мутацию: разработчик не приложил вывод сравнения (только
        утверждение «эквивалентно» без чисел) — в PLAN нет строки о
        ключах с числом.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md нет в ссылке документов задачи")
        self.assertIn("test_lint.findings", plan)
        self.assertTrue(any("ключ" in line.lower() and re.search(r"\d", line)
                            for line in plan.splitlines()),
                        "в PLAN нет вывода сравнения с числом ключей")


if __name__ == "__main__":
    unittest.main()
