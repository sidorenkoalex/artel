"""Повторные прогоны долгоживущих файлов задачи, несущих случайное зерно, на рубеже `in_dev -> verifying` (AC-4..AC-7).

Группа: долгоживущий
Красен до реализации: рубеж гоняет планку и долгоживущие файлы один раз — повторов нет (файл с `import random` исполнен 1 раз вместо 1 + N, тест, красный только в повторе, проходит в `verifying` без эскалации), константы `config.LONG_LIVED_SEED_REPEATS` нет — подмена падает `AttributeError`.

Имя константы числа повторов N: SPEC называет её «именованной
константой `orchestrator/config.py`, значение 3», не давая имени; планка
фиксирует имя `LONG_LIVED_SEED_REPEATS` — подмена значения (AC-5) без
имени невозможна.

Песочница — `tests.sandbox.GitignoreCommittedRealGitSandbox`: пульт и клон
артели — один настоящий git-репозиторий `self.root`, голый origin
(`add_synced_origin`), запись артели в `targets.yaml` с профилем тестов.
Задача артели заводится `catalog.cmd_new`; SPEC, PLAN и планка (один
фикстурный файл) коммитятся в ссылку документов задачи; `approve` на
`spec_gate` — `fsm.cmd_approve`. Долгоживущий файл задачи
(`tests/test_<id>_<имя>.py`) коммитится в рабочую копию ветки и
отправляется в origin; перечень сумм (`guard.LONG_LIVED_MANIFEST_NAME`) —
коммитом в ссылку документов, его голова — лок `tests_locked_sha`. Переход —
`fsm.cmd_advance` из `in_dev`, все рубежи перехода настоящие, pytest —
настоящий.

Фикстурный долгоживущий файл сам считает свои исполнения: каждый запуск
метода дописывает строку в журнал исполнений вне репозитория (временный
каталог) и печатает «зерно: N» из заданного перечня по номеру запуска;
красен он ровно на заданных номерах запусков (0 — первый прогон, 1..N —
повторы). Признак «несёт случайное зерно» — `import random` либо
`from random import …` (форма — от зерна теста); файл без импорта
упоминает слово «random» только в докстринге. Имена класса, метода, файла,
зёрна и номера красных повторов — из `random`; зерно теста печатается и
входит в текст каждого провала.

Стаб реализации не строился (рубеж — `orchestrator/advance_gates/
acceptance.py`, правка кода вне роли): обвязка проверена на сегодняшнем
коде — задача доходит до `verifying` с одним исполнением файла, красный
первый прогон отклоняет переход «приёмочные тесты красные», журнал
исполнений и зёрна в выводе pytest читаются так, как задумано.
"""
import contextlib
import hashlib
import io
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import catalog, config, fsm, projects, store, workspace
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox

DOCS_REF_PREFIX = "refs/artifacts/"
SEED_PHRASE = "тест зависит от случайного зерна"
RED_REFUSAL_ACTION = "переход отклонён: приёмочные тесты"
RED_REFUSAL_OUTPUT = "приёмочные тесты красные"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"

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

# SPEC: фикстура повторов по зерну

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
schema_version: 1
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
"""

PLANK_TEXT = '''"""Фикстура планки песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_fixture_plank(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, {expected})
'''

LONG_LIVED_TEXT = '''"""Фикстура долгоживущего файла песочницы{note}.

Группа: долгоживущий
"""
{imports}import unittest
from pathlib import Path

RUNS = Path({runs!r})
SEEDS = {seeds!r}
RED = {red!r}


class {cls}(unittest.TestCase):

    def {method}(self):
        """Фикстурный метод.

        Ловит мутацию: фикстура песочницы — исход по номеру запуска.
        """
        run = len(RUNS.read_text(encoding="utf-8").splitlines()) \\
            if RUNS.exists() else 0
        with RUNS.open("a", encoding="utf-8") as fh:
            fh.write(f"{{run}}\\n")
        print(f"зерно: {{SEEDS[run % len(SEEDS)]}}")
        self.assertNotIn(run, RED, f"красный запуск {{run}}")
'''

RANDOM_IMPORTS = ("import random\n", "from random import randrange\n",
                  "import os\nimport random\n",
                  "from random import Random, randrange\n")


def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(length))


class SeedRepeatSandbox(GitignoreCommittedRealGitSandbox):
    """Задача артели в `in_dev`: документы в ссылке документов, свой
    долгоживущий файл в ветке и в origin, перечень сумм в дереве лока."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
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
        runs_dir = Path(tempfile.mkdtemp(prefix="artel-seed-runs-"))
        self.addCleanup(shutil.rmtree, runs_dir, ignore_errors=True)
        self.runs = runs_dir / f"runs-{word(self.rng)}.txt"
        self.cls = f"Fx{word(self.rng).capitalize()}Test"
        self.method = f"test_fx_{word(self.rng)}"
        self.task_id = ""
        self.branch = ""
        self.wt = None
        self.rel = ""

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

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

    def long_lived_text(self, imports: str, red: set, seeds: list,
                        note: str = "") -> str:
        return LONG_LIVED_TEXT.format(note=note, imports=imports,
                                      runs=str(self.runs), seeds=seeds,
                                      red=sorted(red), cls=self.cls,
                                      method=self.method)

    def random_imports(self) -> str:
        return self.rng.choice(RANDOM_IMPORTS)

    def seeds(self, count: int) -> list:
        """Различимые девятизначные зёрна, по одному на запуск."""
        values: list = []
        while len(values) < count:
            value = self.rng.randrange(100_000_000, 1_000_000_000)
            if value not in values and value != self.seed:
                values.append(value)
        return values

    # --- сценарий ------------------------------------------------------

    def prepare(self, long_lived: str, plank_green: bool = True) -> None:
        """Задача в `in_dev` с долгоживущим файлом `long_lived` в ветке,
        перечнем его суммы в дереве лока и планкой (зелёной или красной)."""
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        before = {row["id"] for row in store.all_tasks(store.db())}
        self.run_cmd(catalog.cmd_new, f"Повторы по зерну {self.seed}",
                     target=config.DEFAULT_TARGET)
        created = [row["id"] for row in store.all_tasks(store.db())
                   if row["id"] not in before]
        self.assertEqual(len(created), 1, self.note("задача не заведена"))
        self.task_id = created[0]
        self.branch = store.get_task(store.db(), self.task_id)["branch"]
        if not self.git("branch", "--list", self.branch).strip():
            self.git("branch", self.branch, config.MAIN_BRANCH)
        self.wt, error = workspace.ensure(self.task_id, self.branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        plank = PLANK_TEXT.format(expected=2 if plank_green else 3)
        self.commit_docs({"SPEC.md": SPEC_TEXT.format(task=self.task_id),
                          "PLAN.md": PLAN_TEXT.format(task=self.task_id),
                          "acceptance_tests/test_plank.py": plank},
                         "документы задачи")
        store.update_task(store.db(), self.task_id, state="spec_gate")
        store.record_fixation(store.db(), self.task_id)
        out = self.run_cmd(fsm.cmd_approve, self.task_id)
        self.assertEqual(self.state(), "tests_writing",
                         self.note(f"предпосылка: approve не прошёл:\n{out}"))
        self.rel = f"tests/test_{self.task_id.lower()}_{word(self.rng)}.py"
        path = self.wt / self.rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(long_lived, encoding="utf-8")
        self.git("-C", str(self.wt), "add", "-A")
        self.git("-C", str(self.wt), "commit", "-q", "-m", "долгоживущий файл")
        self.git("push", "-q", "-f", "origin", f"{self.branch}:{self.branch}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.commit_docs({f"acceptance_tests/{guard.LONG_LIVED_MANIFEST_NAME}":
                          f"{digest}  {self.rel}\n"}, "перечень долгоживущих")
        store.update_task(store.db(), self.task_id,
                          tests_locked_sha=self.docs_head(), state="in_dev",
                          draft_mr_created=1)
        store.record_fixation(store.db(), self.task_id)

    def advance(self) -> str:
        return self.run_cmd(fsm.cmd_advance, self.task_id)

    def state(self) -> str:
        return store.get_task(store.db(), self.task_id)["state"]

    def journal(self) -> list:
        return [f"{s['action']} | {s['detail'] or ''}"
                for s in store.task_steps(store.db(), self.task_id)]

    def executions(self) -> int:
        if not self.runs.exists():
            return 0
        return len(self.runs.read_text(encoding="utf-8").splitlines())

    def context(self, out: str) -> str:
        return self.note(f"файл {self.rel}; исполнений {self.executions()}\n"
                         f"вывод advance:\n{out}\nжурнал:\n"
                         + "\n".join(self.journal()))


# ---------------------------------------------------------------------------
# AC-4: красный только в повторе — эскалация с именем теста и зёрнами.

class SeedDependentEscalationTest(SeedRepeatSandbox):

    def test_ac4_red_only_in_repeat_escalates_with_node_and_seeds(self):
        """Файл с импортом `random`, зелёный в первом прогоне и красный в части повторов, переводит задачу в `escalated` с узлом теста и зёрнами красных повторов.

        Сценарий: долгоживущий файл задачи импортирует `random` (форма
        импорта — от зерна), зелен на первом запуске и красен на непустом
        случайном подмножестве повторов 1..N (N —
        `config.LONG_LIVED_SEED_REPEATS`), каждый запуск печатает своё
        «зерно: …». После `advance` из `in_dev` задача в `escalated`; запись
        журнала со словами «тест зависит от случайного зерна» и вывод
        `advance` называют файл, класс и метод теста и зерно каждого
        красного повтора.

        Ловит мутацию: красный повтор трактуется как прежний отказ
        «приёмочные тесты красные» (задача остаётся в `in_dev`) или
        пропускается (задача в `verifying`); повторы останавливаются на
        первом красном — зерно более позднего красного повтора не названо;
        зерно берётся не из вывода теста, а из счётчика повтора — в детали
        нет напечатанного числа.
        """
        repeats = config.LONG_LIVED_SEED_REPEATS
        indices = list(range(1, repeats + 1))
        red = set(self.rng.sample(indices, self.rng.randint(1, len(indices))))
        seeds = self.seeds(repeats + 1)
        self.prepare(self.long_lived_text(self.random_imports(), red, seeds))

        out = self.advance()

        context = self.context(out)
        self.assertEqual(self.state(), "escalated", context)
        entries = [e for e in self.journal() if SEED_PHRASE in e]
        self.assertTrue(entries, context)
        self.assertIn(SEED_PHRASE, out, context)
        red_seeds = [str(seeds[i]) for i in sorted(red)]
        for where, text in (("журнал", "\n".join(entries)), ("вывод", out)):
            for needle in (Path(self.rel).name, self.cls, self.method,
                           *red_seeds):
                self.assertIn(needle, text,
                              f"{where} не называет {needle}; красные "
                              f"повторы {sorted(red)}; {context}")


# ---------------------------------------------------------------------------
# AC-5: зелёный во всех прогонах — проход, ровно 1 + N исполнений.

class SeedRepeatCountTest(SeedRepeatSandbox):

    def assert_passes_with_runs(self, expected_runs: int, out: str) -> None:
        context = self.context(out)
        self.assertEqual(self.state(), "verifying", context)
        self.assertFalse([e for e in self.journal() if SEED_PHRASE in e],
                         context)
        self.assertEqual(self.executions(), expected_runs, context)

    def test_ac5_green_random_file_runs_one_plus_configured_repeats(self):
        """Зелёный во всех прогонах файл с импортом `random` проходит в `verifying`, исполнен ровно 1 + N раз при N из конфига.

        Сценарий: долгоживущий файл задачи импортирует `random` и зелен на
        любом запуске; `advance` из `in_dev` без подмены константы. Задача в
        `verifying`, записи «тест зависит от случайного зерна» нет, журнал
        исполнений файла — 1 + `config.LONG_LIVED_SEED_REPEATS` строк.

        Ловит мутацию: повторы не выполняются (1 исполнение), выполняются и
        после красного-зелёного сравнения ещё раз прогоном всей планки с
        файлом (лишнее исполнение), либо зелёные повторы ошибочно
        эскалируют задачу.
        """
        repeats = config.LONG_LIVED_SEED_REPEATS
        self.prepare(self.long_lived_text(self.random_imports(), set(),
                                          self.seeds(repeats + 1)))
        out = self.advance()
        self.assert_passes_with_runs(1 + repeats, out)

    def test_ac5_patched_constant_changes_repeat_count(self):
        """Подменённое значение константы повторов читается в момент рубежа: файл исполнен 1 + подменённое N раз.

        Сценарий: на время `advance` `config.LONG_LIVED_SEED_REPEATS`
        подменён случайным значением 1..5, отличным от исходного; файл
        задачи импортирует `random` и зелен. Задача в `verifying`, журнал
        исполнений — 1 + подменённое значение строк.

        Ловит мутацию: число повторов зашито литералом или прочитано
        снимком при импорте модуля (`from config import …`, значение по
        умолчанию параметра) — исполнений 1 + 3 вместо 1 + подменённого.
        """
        original = config.LONG_LIVED_SEED_REPEATS
        value = self.rng.choice([n for n in range(1, 6) if n != original])
        self.prepare(self.long_lived_text(self.random_imports(), set(),
                                          self.seeds(value + 1)))
        with mock.patch.object(config, "LONG_LIVED_SEED_REPEATS", value):
            out = self.advance()
        self.assert_passes_with_runs(1 + value, out)


# ---------------------------------------------------------------------------
# AC-6: без импорта `random` — одно исполнение.

class NoSeedSingleRunTest(SeedRepeatSandbox):

    def test_ac6_file_without_random_import_runs_once(self):
        """Долгоживущий файл без импорта `random` на переходе `in_dev -> verifying` исполнен ровно один раз.

        Сценарий: файл задачи не импортирует `random` (слово «random» есть
        только в его докстринге), печатает «зерно: …» и красен на любом
        повторном запуске (номер ≥ 1). После `advance` из `in_dev` задача в
        `verifying`, журнал исполнений — одна строка, записи «тест зависит
        от случайного зерна» нет.

        Ловит мутацию: признак «несёт зерно» — подстрока `random` в тексте
        файла или строка «зерно:» в выводе, а не импорт модуля — файл
        повторяется, исполнений больше одного, а красный повтор эскалирует
        задачу; повторяются все долгоживущие файлы без разбора — то же.
        """
        repeats = config.LONG_LIVED_SEED_REPEATS
        red = set(range(1, repeats + 2))
        text = self.long_lived_text("", red, self.seeds(repeats + 1),
                                    note=" (модуль random не импортируется)")
        self.assertNotIn("import random", text)
        self.assertNotIn("from random", text)
        self.prepare(text)
        out = self.advance()
        context = self.context(out)
        self.assertEqual(self.state(), "verifying", context)
        self.assertEqual(self.executions(), 1, context)
        self.assertFalse([e for e in self.journal() if SEED_PHRASE in e],
                         context)


# ---------------------------------------------------------------------------
# AC-7: красный первый прогон — прежний отказ, повторов нет.

class RedFirstRunTest(SeedRepeatSandbox):

    def assert_plain_refusal(self, out: str) -> None:
        context = self.context(out)
        self.assertEqual(self.state(), "in_dev", context)
        self.assertIn(RED_REFUSAL_OUTPUT, out, context)
        self.assertTrue([e for e in self.journal()
                         if e.startswith(RED_REFUSAL_ACTION)], context)
        self.assertFalse([e for e in self.journal() if SEED_PHRASE in e],
                         context)
        self.assertEqual(self.executions(), 1, context)

    def test_ac7_red_long_lived_first_run_refuses_without_repeats(self):
        """Долгоживущий файл с `random`, красный в первом прогоне, даёт прежний отказ «приёмочные тесты красные» без повторов.

        Сценарий: файл задачи импортирует `random`, красен на первом запуске
        (на повторах — от зерна, зелен или красен). После `advance` из
        `in_dev` задача остаётся в `in_dev`, вывод несёт «приёмочные тесты
        красные», журнал — запись «переход отклонён: приёмочные тесты»,
        записи «тест зависит от случайного зерна» нет, файл исполнен один раз.

        Ловит мутацию: повторы запускаются до проверки исхода первого
        прогона (исполнений больше одного), либо разный исход первого
        прогона и повторов эскалирует задачу вместо отказа разработчику.
        """
        repeats = config.LONG_LIVED_SEED_REPEATS
        red = {0} | {i for i in range(1, repeats + 1) if self.rng.random() < 0.5}
        self.prepare(self.long_lived_text(self.random_imports(), red,
                                          self.seeds(repeats + 1)))
        out = self.advance()
        self.assert_plain_refusal(out)

    def test_ac7_red_plank_first_run_refuses_without_repeats(self):
        """Красная планка при зелёном долгоживущем файле с `random` даёт прежний отказ без повторов файла.

        Сценарий: файл планки красен, долгоживущий файл задачи импортирует
        `random` и зелен на любом запуске. После `advance` из `in_dev`
        задача остаётся в `in_dev` с отказом «приёмочные тесты красные»,
        долгоживущий файл исполнен ровно один раз — в общем первом прогоне.

        Ловит мутацию: решение о повторах принимается по исходу
        долгоживущих файлов, а не всего первого прогона (планка красная, а
        файл всё равно повторяется — исполнений 1 + N).
        """
        repeats = config.LONG_LIVED_SEED_REPEATS
        self.prepare(self.long_lived_text(self.random_imports(), set(),
                                          self.seeds(repeats + 1)),
                     plank_green=False)
        out = self.advance()
        self.assert_plain_refusal(out)


if __name__ == "__main__":
    unittest.main()
