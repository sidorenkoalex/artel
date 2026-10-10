"""Признание «приложение PLAN уже в базе» у дерева полного прогона (`appendix_tree.suite_tree`) и у CI ветки (`scripts/plan_appendix_ci.py`) и сверка их ответов.

Группа: долгоживущий
Красен до реализации: test_ac3 и test_ac8 — CI-скрипт накладывает приложение только прямым `git apply`, на уже наложенной в дереве чекаута правке завершается кодом 1 «не накладывается на дерево чекаута», а `suite_tree` пропускает то же приложение — ответы расходятся; test_ac6 — `suite_tree` пропускает уже наложенное приложение без записи журнала (только признак «уже в дереве: приложения N»). Зелёные с рождения: test_ac7 (неприменимое в обе стороны приложение и сегодня отказ у обоих узлов) и test_ac9 (CI-скрипт сегодня не импортирует пакет `orchestrator`).

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`, клон
артели — сам репозиторий песочницы) с bare `origin`: задача артели с
рабочей копией (`workspace.ensure`) на ветке, отправленной в `origin`; PLAN
и SPEC — в ссылке документов задачи автокоммитом пульта
(`checkpoint.commit_step_artifacts`), ссылка документов отправлена в
`origin`, как её отправляет пульт.

Узел пульта — `appendix_tree.suite_tree` (путь автогейта, approve и
suite-run) на голове ветки задачи либо на рабочей копии (от зерна). Узел
CI — сценарий `scripts/plan_appendix_ci.py` этой рабочей копии кода,
запущенный отдельным процессом из корня «раннера» — клона `origin` на
ветке задачи — с переменными окружения Actions пуша ветки.

«Уже в базе» — Оператор внёс правку приложения в `main` раньше, чем ветка
задачи от него отошла: в дереве ветки (и в чекауте раннера) правка уже
есть. «Ни прямо, ни обратно» — в `main` внесена только одна из двух правок
приложения. Файлы, строки правок, число приложений и место нужного — от
зерна; зерно печатается и входит в текст каждого провала.

AC-9 читается как запрет прямого импорта: сценарий сам не импортирует
модулей пакета `orchestrator` (его разбор `scripts.guard` — путь «только
чтение» этой задачи, его зависимости предмет критерия не составляют).

Валидировано временным стабом реализации (обратная проверка и строка
«уже в базе» в CI-скрипте, запись пропуска в `suite_tree`): все тесты
файла зелёные на нескольких зёрнах, стаб удалён.
"""
import ast
import os
import random
import re
import subprocess
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

from orchestrator import (appendix_tree, catalog, checkpoint, config, idgen,
                          store, workspace)
from orchestrator.advance_gates import plan_appendix
from tests.sandbox import RealGitSandbox, capture

CODE_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = CODE_ROOT / "scripts" / "plan_appendix_ci.py"
DOCS_REF_PREFIX = "refs/artifacts/"
IN_BASE_WORDS = "уже в базе"

# Защищённые файлы — от `config.PROTECTED_PATHS`, не литералом: перечень
# меняет Оператор. Markdown вне `tests/` и `.github/`: текст фикстуры в
# защищённом конфиге читался бы пультом как конфиг.
PROTECTED_FILES = [p for p in config.PROTECTED_PATHS
                   if p.endswith(".md") and "*" not in p
                   and not p.startswith(("tests/", ".github"))]

TARGETS_YAML = """targets:
  {name}:
    forge: github
    url: http://localhost/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

BASE_LINES = [f"строка базы {n:02d} из 80" for n in range(1, 81)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
# Строки правок — через восемь: контекст хунка соседней правки их не
# задевает; десяти строк хватает на все случаи сверки (до шести правок).
EDIT_LINES = BASE_LINES[::8]

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: feature.txt
---

# SPEC: фикстура

## Контекст

## Требования

## Критерии приёмки

AC-1. Фикстура.

## Не входит
"""

APPLIED, IN_BASE, REFUSED = "наложено", "уже в базе", "отказ"


def names_number(text: str, number: int) -> bool:
    """Текст называет номер приложения рядом со словом «приложение»."""
    return re.search(rf"приложени\w*\s*(PLAN\s*)?(№\s*)?{number}\b", text,
                     re.IGNORECASE) is not None


class InBaseNodesSandbox(RealGitSandbox):
    """Задачи артели с рабочей копией и PLAN в ссылке документов (локально
    и в `origin`); `origin` синхронный с `main`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.case = ""
        self.assertGreaterEqual(len(PROTECTED_FILES), 2, self.note(
            "в config.PROTECTED_PATHS нет двух защищённых markdown-файлов"))
        self.files = self.rng.sample(PROTECTED_FILES, 2)
        self.lines = self.rng.sample(EDIT_LINES, len(EDIT_LINES))
        self.tmp = Path(tempfile.mkdtemp(prefix="artel-in-base-runner-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        config.TARGETS.write_text(TARGETS_YAML.format(
            name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH),
            encoding="utf-8")
        for rel in self.files:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(BASE_TEXT, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", "защищённые файлы-фикстуры")
        self.origin = self.add_synced_origin()
        capture(catalog.cmd_init)
        self.task = ""

    # ------------------------------------------------------------ обвязка

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed}; {self.case or 'сценарий'})"

    def free_line(self) -> str:
        """Строка базы, которую ещё не правил ни один сценарий файла."""
        return self.lines.pop()

    def marker(self) -> str:
        return f"правка ({self.rng.randrange(10**9)})"

    def edit(self, rel: str, replacements: dict) -> None:
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            self.assertIn(old, text)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    def diff_of(self, edits: dict) -> str:
        """Unified-дифф правок `edits` ({путь: {старое: новое}}) к дереву
        `main` — настоящим `git diff`, правка затем откатывается."""
        self.checkout(config.MAIN_BRANCH)
        for rel, replacements in edits.items():
            self.edit(rel, replacements)
        diff = self.git("diff", "--", *edits)
        self.git("checkout", "-q", "--", *edits)
        self.assertIn("diff --git a/", diff)
        return diff

    def operator_commits_to_main(self, edits: dict) -> None:
        """Коммит Оператора в `main` и `origin` — до отхода ветки задачи."""
        self.checkout(config.MAIN_BRANCH)
        for rel, replacements in edits.items():
            self.edit(rel, replacements)
        self.git("add", "--", *edits)
        self.git("commit", "-q", "-m", "оператор: правка защищённого файла")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

    def make_task(self, diffs: list) -> None:
        """Задача артели: рабочая копия на ветке с кодом задачи (ветка в
        `origin`), PLAN с приложениями `diffs` в ссылке документов (и в
        `origin`)."""
        self.task = idgen.new_task_id()
        self.branch = f"task/{self.task.lower()}-x"
        store.insert_task(store.db(), self.task, f"Задача {self.task}",
                          "acceptance", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(self.task, self.branch,
                                     config.DEFAULT_TARGET)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.wt = Path(wt).resolve()
        (self.wt / "feature.txt").write_text(f"код задачи {self.task}\n",
                                             encoding="utf-8")
        self.git("-C", str(self.wt), "add", "feature.txt")
        self.git("-C", str(self.wt), "commit", "-q", "-m",
                 f"{self.task}: код задачи")
        self.git("-C", str(self.wt), "push", "-q", "origin", self.branch)
        sections = "".join(
            f"\n## Приложение {i}: правка {self.rng.randrange(10**6)}\n\n"
            f"```diff\n{diff}```\n" for i, diff in enumerate(diffs, 1))
        plan = (f"---\ntask: {self.task}\ntype: plan\n"
                f"author_role: developer\nstatus: ready\n"
                f"schema_version: 2\n---\n\n# PLAN\n\n## Подход\n\n"
                f"Фикстура.\n{sections}")
        docs = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / self.task
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=self.task),
                                      encoding="utf-8")
        (docs / "PLAN.md").write_text(plan, encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, store.db(), self.task,
                "developer")
        ref = DOCS_REF_PREFIX + self.task
        self.git("push", "-q", "origin", f"+{ref}:{ref}")

    def steps(self) -> list:
        return list(store.task_steps(store.db(), self.task))

    def journal(self) -> list:
        return [f"{r['action']} | {r['detail'] or ''}" for r in self.steps()]

    def in_base_records(self) -> list:
        return [s for s in self.steps() if s["action"].startswith(
            plan_appendix.PLAN_APPENDIX_ALREADY_IN_BASE_ACTION)]

    def suite_tree(self):
        """Исход `suite_tree` на голове ветки либо на рабочей копии (от
        зерна): (корень прогона, причина отказа, вход)."""
        branch = self.rng.choice([self.branch, None])
        with appendix_tree.suite_tree(store.db(), self.task, self.wt,
                                      branch) as tree:
            return tree.root, tree.refusal, f"branch={branch}"

    def run_ci(self) -> subprocess.CompletedProcess:
        """Сценарий CI этой рабочей копии кода в «раннере» — клоне `origin`
        на ветке задачи — по пушу ветки."""
        runner = self.tmp / f"runner-{self.rng.randrange(10**9)}"
        self.git("clone", "-q", "--depth", "1", "--branch", self.branch,
                 f"file://{self.origin}", str(runner))
        env = dict(os.environ)
        env.update({
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": f"refs/heads/{self.branch}",
            "GITHUB_REF_NAME": self.branch,
            "GITHUB_REF_TYPE": "branch",
            "GITHUB_WORKSPACE": str(runner),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        return subprocess.run([sys.executable, str(SCRIPT)], cwd=runner,
                              env=env, capture_output=True, text=True,
                              timeout=120)

    def output(self, res: subprocess.CompletedProcess) -> str:
        return f"код {res.returncode}\n{res.stdout}\n{res.stderr}"

    def in_base_scenario(self) -> tuple:
        """PLAN с одним-тремя приложениями; одно (место от зерна) Оператор
        внёс в `main` до отхода ветки, прочие применимы. (номер уже
        наложенного, его путь)."""
        total = self.rng.randint(1, 3)
        number = self.rng.randrange(total) + 1
        diffs, applied = [], None
        for i in range(1, total + 1):
            rel = self.files[0] if i == number else self.files[1]
            edit = {rel: {self.free_line(): self.marker()}}
            if i == number:
                applied = edit
            diffs.append(self.diff_of(edit))
        self.operator_commits_to_main(applied)
        self.make_task(diffs)
        return number, self.files[0]

    def neither_way_scenario(self) -> tuple:
        """Одно приложение из двух правок первого файла; в `main` до отхода
        ветки внесена только одна (какая — от зерна). (номер, путь)."""
        first, second = self.free_line(), self.free_line()
        rel = self.files[0]
        whole = {rel: {first: self.marker(), second: self.marker()}}
        diff = self.diff_of(whole)
        line = self.rng.choice([first, second])
        self.operator_commits_to_main({rel: {line: whole[rel][line]}})
        self.make_task([diff])
        return 1, rel

    def applicable_scenario(self) -> tuple:
        """Одно приложение, которое ложится на дерево ветки прямо."""
        rel = self.files[1]
        self.make_task([self.diff_of({rel: {self.free_line(): self.marker()}})])
        return 1, rel


class CiAlreadyInBaseTest(InBaseNodesSandbox):

    def test_ac3_ci_script_passes_appendix_in_base(self):
        """CI-скрипт на ветке с уже наложенным в базе приложением — код 0 и строка «уже в базе» с номером.

        Сценарий: PLAN несёт одно-три приложения, одно из них (место от
        зерна) Оператор внёс в `main` до отхода ветки; раннер — клон ветки.
        Сценарий завершается кодом 0, в его выводе есть строка со словами
        «уже в базе» и номером этого приложения.

        Ловит мутацию: CI-скрипт по-прежнему накладывает только прямым `git
        apply` — уже наложенное «не накладывается на дерево чекаута», код
        1; обратная проверка пропускает приложение молча — строки «уже в
        базе» нет; номер в строке считается с нуля — номер не тот.
        """
        number, rel = self.in_base_scenario()
        self.case = f"уже в базе — приложение {number} ({rel})"

        res = self.run_ci()

        out = self.output(res)
        self.assertEqual(res.returncode, 0, self.note(out))
        lines = [ln for ln in (res.stdout + "\n" + res.stderr).splitlines()
                 if IN_BASE_WORDS in ln and names_number(ln, number)]
        self.assertTrue(lines, self.note(
            f"нет строки «{IN_BASE_WORDS}» с номером {number}:\n{out}"))


class SuiteTreeAlreadyInBaseTest(InBaseNodesSandbox):

    def test_ac6_suite_tree_skips_appendix_in_base_with_journal_record(self):
        """Дерево полного прогона пропускает уже наложенное приложение записью журнала общей формы.

        Сценарий: тот же, что у CI (одно-три приложения, одно уже в базе);
        `suite_tree` на голове ветки либо на рабочей копии (от зерна):
        корень прогона есть, отказа нет; в журнале задачи есть запись с
        действием ровно `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION + ": " +
        <путь>` и подробностями, содержащими «приложение N (<путь>)» с
        номером этого приложения.

        Ловит мутацию: дерево полного прогона признаёт уже наложенное
        прежней вложенной проверкой без записи журнала — записи нет; запись
        пишется своим действием («уже в дереве») — действие не совпадает;
        обратная проверка снята — прогон отказан «не накладывается».
        """
        number, rel = self.in_base_scenario()
        self.case = f"уже в базе — приложение {number} ({rel})"

        root, refusal, entry = self.suite_tree()

        context = self.note(f"{entry}; отказ: {refusal!r}\n"
                            + "\n".join(self.journal()))
        self.assertIsNotNone(root, context)
        self.assertEqual(refusal, "", context)
        action = f"{plan_appendix.PLAN_APPENDIX_ALREADY_IN_BASE_ACTION}: {rel}"
        detail = f"приложение {number} ({rel})"
        records = [s for s in self.steps() if s["action"] == action
                   and detail in (s["detail"] or "")]
        self.assertTrue(records, f"нет записи «{action}» с «{detail}»; {context}")


class NeitherWayNodesTest(InBaseNodesSandbox):

    def test_ac7_half_applied_appendix_refused_by_suite_tree_and_ci(self):
        """Приложение, не ложащееся ни прямо, ни обратно, — отказ дерева полного прогона и код 1 CI-скрипта с номером.

        Сценарий: приложение из двух правок защищённого файла, в `main` до
        отхода ветки внесена одна. `suite_tree`: корня прогона нет, причина
        отказа называет путь приложения, записи «приложение PLAN уже в
        базе» нет. CI-скрипт в раннере на ветке: код 1, в выводе — номер
        приложения.

        Ловит мутацию: общее правило признания считает «уже в базе» любое
        приложение, не легшее прямо (ответ обратной проверки не читается), —
        `suite_tree` даёт корень прогона, CI-скрипт завершается кодом 0;
        правило CI-скрипта зовёт `git apply --reverse` без `--check` — тот
        же исход.
        """
        number, rel = self.neither_way_scenario()
        self.case = f"ни прямо, ни обратно — приложение {number} ({rel})"

        root, refusal, entry = self.suite_tree()

        context = self.note(f"{entry}; отказ: {refusal!r}\n"
                            + "\n".join(self.journal()))
        self.assertIsNone(root, context)
        self.assertIn(rel, refusal, context)
        self.assertEqual(self.in_base_records(), [], context)

        res = self.run_ci()

        out = self.output(res)
        self.assertEqual(res.returncode, 1, self.note(out))
        self.assertTrue(names_number(res.stdout + res.stderr, number),
                        self.note(out))


class ReconciliationTest(InBaseNodesSandbox):

    def pult_answer(self) -> tuple:
        root, refusal, entry = self.suite_tree()
        if root is None:
            answer = REFUSED
        elif self.in_base_records():
            answer = IN_BASE
        else:
            answer = APPLIED
        return answer, f"{entry}; отказ: {refusal!r}; журнал: {self.journal()}"

    def ci_answer(self) -> tuple:
        res = self.run_ci()
        if res.returncode != 0:
            answer = REFUSED
        elif IN_BASE_WORDS in res.stdout + res.stderr:
            answer = IN_BASE
        else:
            answer = APPLIED
        return answer, self.output(res)

    def test_ac8_pult_and_ci_rules_agree_on_each_case(self):
        """Сверка правила пульта и правила CI-скрипта на трёх случаях — ответы совпадают по каждому.

        Сценарий: три задачи (порядок — от зерна): приложение ложится на
        дерево ветки прямо; уже наложено в базе; не ложится ни прямо, ни
        обратно. Ответ пульта — исход дерева полного прогона
        (`suite_tree`): отказ / пропуск с записью «приложение PLAN уже в
        базе» / наложено. Ответ CI — исход сценария в раннере на ветке:
        код 1 / код 0 со строкой «уже в базе» / код 0 без неё. По каждому
        случаю ответы равны, и сверка различает все три случая.

        Ловит мутацию: правило «уже в базе» добавлено только в узлы пульта —
        на уже наложенном CI отвечает отказом, пульт пропуском; правило CI
        принимает любое приложение, не легшее прямо, за наложенное — на
        случае «ни прямо, ни обратно» CI отвечает «уже в базе», пульт
        отказом; пропуск у пульта без записи журнала — пульт отвечает
        «наложено», CI «уже в базе».
        """
        scenarios = [("прямо", self.applicable_scenario),
                     ("уже в базе", self.in_base_scenario),
                     ("ни прямо, ни обратно", self.neither_way_scenario)]
        self.rng.shuffle(scenarios)
        answers = {}
        for name, scenario in scenarios:
            self.case = f"случай «{name}»"
            scenario()
            pult, pult_ctx = self.pult_answer()
            ci, ci_ctx = self.ci_answer()
            self.assertEqual(pult, ci, self.note(
                f"пульт: {pult} ({pult_ctx})\nCI: {ci}\n{ci_ctx}"))
            answers[name] = pult
        self.case = "все случаи"
        self.assertEqual(len(set(answers.values())), 3, self.note(
            f"сверка не различает случаи: {answers}"))


class CiScriptImportsTest(unittest.TestCase):

    def test_ac9_ci_script_does_not_import_orchestrator(self):
        """Сценарий CI сам не импортирует ни одного модуля пакета `orchestrator`.

        Сценарий: разбор текста `scripts/plan_appendix_ci.py` (модуль
        `ast`): ни инструкция `import`, ни `from … import`, ни вызов
        `importlib.import_module`/`__import__` со строкой не называют
        `orchestrator` или его подмодуль — на любом уровне вложенности,
        включая импорт внутри функции.

        Ловит мутацию: CI-скрипт берёт правило «уже в базе» у пульта
        (`from orchestrator.advance_gates.plan_appendix import git_apply`
        или `import orchestrator.appendix_tree` внутри функции) вместо
        своей копии правила — в разборе находится импорт `orchestrator`.
        """
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        found = []
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] if not node.level else []
            elif isinstance(node, ast.Call) and node.args \
                    and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str):
                func = ast.unparse(node.func)
                if func in ("importlib.import_module", "import_module",
                            "__import__"):
                    names = [node.args[0].value]
            found.extend(f"строка {node.lineno}: {name}" for name in names
                         if name.split(".")[0] == "orchestrator")
        self.assertEqual(found, [], f"{SCRIPT} импортирует пакет пульта")


if __name__ == "__main__":
    unittest.main()
