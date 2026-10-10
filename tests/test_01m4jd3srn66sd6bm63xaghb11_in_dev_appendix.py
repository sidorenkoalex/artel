"""Рубеж `in_dev -> verifying` и приложения PLAN: прогон планки и долгоживущих файлов на дереве с приложениями, именованный отказ неприменимого, пропуск уже наложенного в базе.

Группа: долгоживущий
Красен до реализации: test_ac1 — рубеж гоняет планку и долгоживущие файлы в рабочей копии без приложений PLAN, тест задачи, которому нужна правка защищённого теста, красен, задача остаётся в `in_dev`; test_ac2 — отказ гейта применимости называет пути приложения, но не его номер. Зелёные с рождения: test_ac4 (гейт применимости уже пропускает приложение, наложенное в базе, записью нынешней формы, планка в рабочей копии видит правку базы) и test_ac7 (неприменимое в обе стороны приложение отказывает и сегодня).

Песочница — `tests.sandbox.GitignoreCommittedRealGitSandbox`: пульт и
клон артели — один настоящий git-репозиторий `self.root`, голый origin,
запись артели с профилем тестов. База (`main`) несёт защищённый тест
(первый путь `tests/…py` из `config.PROTECTED_PATHS`) и защищённые
markdown-файлы — тексты-фикстуры из строк «строка базы NN». Задача
заводится `catalog.cmd_new`, SPEC, PLAN и планка — коммитом в ссылку
документов, `approve` на `spec_gate`; долгоживущий файл задачи — в ветке и
в origin, перечень его суммы — в дереве лока. Переход — `fsm.cmd_advance`
из `in_dev`, все рубежи перехода настоящие, pytest — настоящий.

Планка и долгоживущий файл задачи сами пишут каждое своё исполнение в
журнал вне репозитория и красны, пока в защищённом тесте дерева прогона
нет правки приложения (планка смотрит от каталога запуска pytest,
долгоживущий файл — от своего расположения). Правки, их строки, число
приложений и место нужного среди них — от зерна; зерно печатается и входит
в текст каждого провала.

Признание «приложение уже в базе» — Оператор внёс правку приложения в
`main` раньше, чем ветка задачи от него отошла: в базе сравнения и в
дереве ветки правка уже есть, прямой `git apply` отказывает, обратная
проверка проходит.

Валидировано временным стабом реализации (прогон рубежа через
`appendix_tree.suite_tree` с записью пропуска, номер приложения в отказе
гейта применимости): все тесты файла зелёные, стаб удалён.
"""
import contextlib
import hashlib
import io
import os
import random
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import catalog, config, fsm, projects, store, workspace
from orchestrator.advance_gates import plan_appendix
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox

DOCS_REF_PREFIX = "refs/artifacts/"
REFUSED_PREFIX = "переход отклонён"
RED_PLANK_ACTION = "переход отклонён: приёмочные тесты"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"

# Защищённые пути — от `config.PROTECTED_PATHS`, не литералом: перечень
# меняет Оператор. Защищённый тест — путь под `tests/`; прочие — markdown
# вне `tests/` и `.github/` (текст фикстуры в защищённом конфиге читался бы
# пультом как конфиг).
PROTECTED_TEST = next(p for p in config.PROTECTED_PATHS
                      if p.startswith("tests/") and p.endswith(".py"))
PROTECTED_MD = [p for p in config.PROTECTED_PATHS
                if p.endswith(".md") and "*" not in p
                and not p.startswith(("tests/", ".github"))]

BASE_LINES = [f"# строка базы {n:02d} из 40" for n in range(1, 41)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
# Строки правок — через восемь: контекст хунка соседней правки их не
# задевает, диффы от базы ложатся друг на друга в любом порядке.
EDIT_LINES = BASE_LINES[::8]

ARTEL_TARGETS = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/
budget_usd: 30
---

# SPEC: фикстура приложений на рубеже

## Контекст

Фикстура песочницы.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстурный критерий.

## Не входит

Ничего.
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: фикстура

## Подход

Фикстура.

## Шаги

1. Фикстура.

## Покрытие требований

Фикстура.

## Влияние на систему

Нет.
{sections}"""

PLANK_TEXT = '''"""Фикстура планки песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest
from pathlib import Path

RUNS = Path({runs!r})


class FixturePlankTest(unittest.TestCase):

    def test_fixture_plank(self):
        """Фикстурный метод: правка приложения в дереве прогона."""
        with RUNS.open("a", encoding="utf-8") as fh:
            fh.write("планка\\n")
        text = (Path.cwd() / {rel!r}).read_text(encoding="utf-8")
        self.assertIn({marker!r}, text)
'''

LONG_LIVED_TEXT = '''"""Фикстура долгоживущего файла песочницы.

Группа: долгоживущий
"""
import unittest
from pathlib import Path

RUNS = Path({runs!r})


class {cls}(unittest.TestCase):

    def {method}(self):
        """Фикстурный метод.

        Ловит мутацию: фикстура песочницы — правки приложения нет в дереве.
        """
        with RUNS.open("a", encoding="utf-8") as fh:
            fh.write("долгоживущий\\n")
        root = Path(__file__).resolve().parent.parent
        text = (root / {rel!r}).read_text(encoding="utf-8")
        self.assertIn({marker!r}, text)
'''


def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(length))


def names_number(text: str, number: int) -> bool:
    """Текст называет номер приложения рядом со словом «приложение»."""
    return re.search(rf"приложени\w*\s*(PLAN\s*)?(№\s*)?{number}\b", text,
                     re.IGNORECASE) is not None


class InDevAppendixSandbox(GitignoreCommittedRealGitSandbox):
    """База с защищённым тестом и markdown-файлами; задача артели в
    `in_dev` с планкой и долгоживущим файлом, ждущими правки приложения."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.case = ""
        self.assertTrue(PROTECTED_MD, self.note(
            "в config.PROTECTED_PATHS нет защищённого markdown-файла"))
        for rel in [PROTECTED_TEST, *PROTECTED_MD]:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(BASE_TEXT, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", "защищённые файлы-фикстуры")
        self.origin = self.add_synced_origin()
        config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        self.use_role_map()
        templates = self.root / ".artel" / "templates-fixture"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "SPEC.md").write_text(SPEC_TEXT.format(task="TASK_ID"),
                                           encoding="utf-8")
        for patcher in (
                mock.patch.object(config, "TEMPLATES", templates),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        runs_dir = Path(tempfile.mkdtemp(prefix="artel-appendix-runs-"))
        self.addCleanup(shutil.rmtree, runs_dir, ignore_errors=True)
        self.runs = runs_dir / f"runs-{word(self.rng)}.txt"
        self.case = ""
        self.task_id = ""
        self.wt = None

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {self.case or 'сценарий'}; {text}"

    def run_cmd(self, fn, *args, **kwargs) -> str:
        """Вывод команды вместе с текстом ненулевого `SystemExit`."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def marker(self) -> str:
        return f"# правка {word(self.rng)} {self.rng.randrange(10**6)}"

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

    def edit(self, rel: str, replacements: dict) -> None:
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            self.assertIn(old, text)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    def operator_commits_to_main(self, edits: dict) -> None:
        """Коммит Оператора в `main` (и в origin) — до того, как ветка
        задачи от него отойдёт."""
        self.checkout(config.MAIN_BRANCH)
        for rel, replacements in edits.items():
            self.edit(rel, replacements)
        self.git("add", "--", *edits)
        self.git("commit", "-q", "-m", "оператор: правка защищённого файла")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

    def other_appendices(self, count: int) -> list:
        """`count` применимых к базе приложений к защищённым markdown-файлам
        (строки разные, файл — от зерна)."""
        lines = self.rng.sample(EDIT_LINES, count)
        return [self.diff_of({self.rng.choice(PROTECTED_MD):
                              {line: self.marker()}}) for line in lines]

    def docs_head(self) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        DOCS_REF_PREFIX + self.task_id).strip()

    def commit_docs(self, files: dict, message: str) -> None:
        """Коммит `files` (путь внутри каталога задачи -> текст) в ссылку
        документов: отдельная рабочая копия на её голове и `update-ref`."""
        old = self.docs_head()
        self.assertTrue(old, self.note("ссылки документов нет"))
        scratch = self.root / ".artel" / f"docs-copy-{self.rng.randrange(1 << 30)}"
        self.git("worktree", "add", "-q", "--detach", str(scratch), old)
        try:
            for rel, text in files.items():
                target = scratch / "tasks" / self.task_id / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            self.git("-C", str(scratch), "add", "-A")
            self.git("-C", str(scratch), "commit", "-q", "-m", message)
            new = self.git("-C", str(scratch), "rev-parse", "HEAD").strip()
        finally:
            self.git("worktree", "remove", "--force", str(scratch))
        self.git("update-ref", DOCS_REF_PREFIX + self.task_id, new, old)
        store.record_fixation(store.db(), self.task_id)

    def plan(self, diffs: list) -> str:
        sections = "".join(
            f"\n## Приложение {i}: {word(self.rng)}\n\n```diff\n{diff}```\n"
            for i, diff in enumerate(diffs, 1))
        return PLAN_TEXT.format(task=self.task_id, sections=sections)

    def prepare(self, diffs: list, marker: str) -> None:
        """Задача в `in_dev`: PLAN с приложениями `diffs` (в этом порядке),
        планка и долгоживущий файл, которым нужна строка `marker` в
        защищённом тесте дерева прогона."""
        self.checkout(config.MAIN_BRANCH)
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        before = {row["id"] for row in store.all_tasks(store.db())}
        self.run_cmd(catalog.cmd_new, f"Приложения на рубеже {self.seed}",
                     target=config.DEFAULT_TARGET)
        created = [row["id"] for row in store.all_tasks(store.db())
                   if row["id"] not in before]
        self.assertEqual(len(created), 1, self.note("задача не заведена"))
        self.task_id = created[0]
        branch = store.get_task(store.db(), self.task_id)["branch"]
        if not self.git("branch", "--list", branch).strip():
            self.git("branch", branch, config.MAIN_BRANCH)
        self.wt, error = workspace.ensure(self.task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        plank = PLANK_TEXT.format(runs=str(self.runs), rel=PROTECTED_TEST,
                                  marker=marker)
        self.commit_docs({"SPEC.md": SPEC_TEXT.format(task=self.task_id),
                          "PLAN.md": self.plan(diffs),
                          "acceptance_tests/test_plank.py": plank},
                         "документы задачи")
        store.update_task(store.db(), self.task_id, state="spec_gate")
        store.record_fixation(store.db(), self.task_id)
        out = self.run_cmd(fsm.cmd_approve, self.task_id)
        self.assertEqual(self.state(), "tests_writing",
                         self.note(f"предпосылка: approve не прошёл:\n{out}"))
        rel = f"tests/test_{self.task_id.lower()}_{word(self.rng)}.py"
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(LONG_LIVED_TEXT.format(
            runs=str(self.runs), cls=f"Fx{word(self.rng).capitalize()}Test",
            method=f"test_fx_{word(self.rng)}", rel=PROTECTED_TEST,
            marker=marker), encoding="utf-8")
        self.git("-C", str(self.wt), "add", "-A")
        self.git("-C", str(self.wt), "commit", "-q", "-m", "долгоживущий файл")
        self.git("push", "-q", "-f", "origin", f"{branch}:{branch}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.commit_docs({f"acceptance_tests/{guard.LONG_LIVED_MANIFEST_NAME}":
                          f"{digest}  {rel}\n"}, "перечень долгоживущих")
        store.update_task(store.db(), self.task_id,
                          tests_locked_sha=self.docs_head(), state="in_dev",
                          draft_mr_created=1)
        store.record_fixation(store.db(), self.task_id)
        self.runs.unlink(missing_ok=True)

    def advance(self) -> str:
        return self.run_cmd(fsm.cmd_advance, self.task_id)

    def state(self) -> str:
        return store.get_task(store.db(), self.task_id)["state"]

    def steps(self) -> list:
        return list(store.task_steps(store.db(), self.task_id))

    def journal(self) -> list:
        return [f"{s['action']} | {s['detail'] or ''}" for s in self.steps()]

    def executions(self) -> list:
        if not self.runs.exists():
            return []
        return self.runs.read_text(encoding="utf-8").splitlines()

    def context(self, out: str) -> str:
        return self.note(f"исполнения: {self.executions()}\nвывод advance:\n"
                         f"{out}\nжурнал:\n" + "\n".join(self.journal()))


class AppendixTreeOnBoundaryTest(InDevAppendixSandbox):

    def test_ac1_boundary_green_only_with_applied_appendix(self):
        """Тест задачи красен без приложения к защищённому тесту — рубеж проходит, а без наложения красен.

        Сценарий: PLAN несёт одно-три приложения (место нужного — от зерна):
        одно правит строку защищённого теста, прочие — защищённые
        markdown-файлы. Планка и долгоживущий файл задачи красны, пока в
        защищённом тесте дерева прогона нет этой правки. `advance` из
        `in_dev`: задача в `verifying`, планка и долгоживущий файл
        исполнялись. Контроль — та же задача (тот же код ветки), PLAN без
        приложений: рубеж красен — задача в `in_dev` с отказом «приёмочные
        тесты».

        Ловит мутацию: рубеж по-прежнему гоняет планку в рабочей копии без
        приложений PLAN — планка и долгоживущий файл не видят правки, задача
        остаётся в `in_dev` с отказом «приёмочные тесты»; дерево с
        приложениями собрано, но pytest запущен с каталогом рабочей копии —
        планка не видит правки; накладывается только первое приложение
        (`break` после первого `git apply`) — правка защищённого теста не на
        первом месте не доходит до дерева.
        """
        marker = self.marker()
        needed = self.diff_of({PROTECTED_TEST: {self.rng.choice(EDIT_LINES):
                                                marker}})
        diffs = self.other_appendices(self.rng.randint(0, 2))
        diffs.insert(self.rng.randrange(len(diffs) + 1), needed)
        self.case = f"приложений {len(diffs)}, нужное — {diffs.index(needed) + 1}"
        self.prepare(diffs, marker)

        out = self.advance()

        context = self.context(out)
        self.assertEqual(self.state(), "verifying", context)
        self.assertIn("планка", self.executions(), context)
        self.assertIn("долгоживущий", self.executions(), context)

        self.case = "контроль: PLAN без приложений"
        self.prepare([], marker)
        out = self.advance()
        context = self.context(out)
        self.assertEqual(self.state(), "in_dev", context)
        self.assertTrue([e for e in self.journal()
                         if e.startswith(RED_PLANK_ACTION)], context)


class InapplicableOnBoundaryTest(InDevAppendixSandbox):

    def test_ac2_inapplicable_appendix_refused_with_number_and_paths(self):
        """Приложение, не ложащееся ни прямо, ни обратно, — именованный отказ без прогона планки.

        Сценарий: PLAN несёт одно-три приложения; одно (место — от зерна)
        правит защищённый тест по строкам контекста, которых нет ни в базе,
        ни в ветке, прочие — применимые правки markdown-файлов. `advance` из
        `in_dev`: задача осталась в `in_dev`, среди записей отказа перехода
        есть запись, называющая номер неприменимого приложения и его путь;
        ни планка, ни долгоживущий файл не исполнялись.

        Ловит мутацию: отказ называет приложение только путём («приложение
        PLAN <путь> не применяется»), без номера; неприменимое приложение
        пропущено, и рубеж гоняет планку с остальными — планка исполнялась;
        отказ наложения на рубеже не останавливает переход — прогон идёт в
        рабочей копии без приложений.
        """
        marker = self.marker()
        bad = (f"diff --git a/{PROTECTED_TEST} b/{PROTECTED_TEST}\n"
               f"--- a/{PROTECTED_TEST}\n+++ b/{PROTECTED_TEST}\n"
               f"@@ -1,3 +1,3 @@\n # строки, которой нет\n-# и этой нет\n"
               f"+{marker}\n # и этой нет\n")
        diffs = self.other_appendices(self.rng.randint(0, 2))
        number = self.rng.randrange(len(diffs) + 1) + 1
        diffs.insert(number - 1, bad)
        self.case = f"приложений {len(diffs)}, неприменимое — {number}"
        self.prepare(diffs, marker)

        out = self.advance()

        context = self.context(out)
        self.assertEqual(self.state(), "in_dev", context)
        refusals = [e for e in self.journal() if e.startswith(REFUSED_PREFIX)]
        self.assertTrue(refusals, context)
        named = [e for e in refusals
                 if names_number(e, number) and PROTECTED_TEST in e]
        self.assertTrue(named, self.note(
            f"отказ не называет приложение {number} и путь {PROTECTED_TEST}:\n"
            + "\n".join(refusals)))
        self.assertEqual(self.executions(), [], context)


class AlreadyInBaseOnBoundaryTest(InDevAppendixSandbox):

    def test_ac4_appendix_in_base_skipped_with_journal_record(self):
        """Приложение, уже наложенное в базе, рубеж пропускает записью журнала с номером и путями.

        Сценарий: Оператор внёс правку приложения к защищённому тесту в
        `main` до того, как ветка задачи отошла; PLAN несёт это приложение и
        ещё ноль-два применимых (место уже наложенного — от зерна). Планка и
        долгоживущий файл ждут правки. `advance` из `in_dev`: задача в
        `verifying`; в журнале задачи есть запись с действием ровно
        `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION + ": " + <путь>` и
        подробностями, содержащими «приложение N (<путь>)» с номером этого
        приложения.

        Ловит мутацию: дерево прогона на рубеже накладывает приложения без
        обратной проверки — уже наложенное «не накладывается», переход
        отказан; запись пропуска пишется прежней формой вложенной проверки
        дерева («уже в дереве: приложения N») либо не пишется вовсе —
        записи с действием `PLAN_APPENDIX_ALREADY_IN_BASE_ACTION: <путь>`
        нет; номер в подробностях считается с нуля — «приложение N» не
        совпадает с местом в PLAN.
        """
        marker = self.marker()
        edit = {PROTECTED_TEST: {self.rng.choice(EDIT_LINES): marker}}
        applied = self.diff_of(edit)
        diffs = self.other_appendices(self.rng.randint(0, 2))
        number = self.rng.randrange(len(diffs) + 1) + 1
        diffs.insert(number - 1, applied)
        self.case = f"приложений {len(diffs)}, уже в базе — {number}"
        self.operator_commits_to_main(edit)
        self.prepare(diffs, marker)

        out = self.advance()

        context = self.context(out)
        self.assertEqual(self.state(), "verifying", context)
        action = f"{plan_appendix.PLAN_APPENDIX_ALREADY_IN_BASE_ACTION}: {PROTECTED_TEST}"
        detail = f"приложение {number} ({PROTECTED_TEST})"
        records = [s for s in self.steps() if s["action"] == action
                   and detail in (s["detail"] or "")]
        self.assertTrue(records, self.note(
            f"нет записи «{action}» с «{detail}»:\n" + "\n".join(self.journal())))


class NeitherWayOnBoundaryTest(InDevAppendixSandbox):

    def test_ac7_half_applied_appendix_refused_at_in_dev_exit(self):
        """Приложение, наложенное в базе наполовину, — отказ на выходе из `in_dev`.

        Сценарий: приложение правит две строки защищённого теста; Оператор
        внёс в `main` до отхода ветки только одну из них (какую — от зерна).
        Ни прямой `git apply`, ни обратная проверка такое приложение не
        проходят. `advance` из `in_dev`: задача осталась в `in_dev`, есть
        запись отказа перехода, называющая путь приложения; записи
        «приложение PLAN уже в базе» нет.

        Ловит мутацию: общее правило признания считает «уже в базе» любое
        приложение, не легшее прямо (обратная проверка не зовётся или её
        ответ не читается), — переход проходит в `verifying` с записью
        «приложение PLAN уже в базе»; обратная проверка зовётся без
        `--check` и сама меняет дерево — исход тот же.
        """
        first, second = self.rng.sample(EDIT_LINES, 2)
        marker_a, marker_b = self.marker(), self.marker()
        whole = {PROTECTED_TEST: {first: marker_a, second: marker_b}}
        old, new = self.rng.choice([(first, marker_a), (second, marker_b)])
        half = {PROTECTED_TEST: {old: new}}
        self.case = f"в базе наложена правка строки «{old}»"
        diff = self.diff_of(whole)
        self.operator_commits_to_main(half)
        self.prepare([diff], marker_a)

        out = self.advance()

        context = self.context(out)
        self.assertEqual(self.state(), "in_dev", context)
        refusals = [e for e in self.journal()
                    if e.startswith(REFUSED_PREFIX) and PROTECTED_TEST in e]
        self.assertTrue(refusals, context)
        self.assertFalse([s for s in self.steps() if s["action"].startswith(
            plan_appendix.PLAN_APPENDIX_ALREADY_IN_BASE_ACTION)], context)


if __name__ == "__main__":
    unittest.main()
