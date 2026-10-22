"""Долгоживущие файлы с меткой `AC-<n>: ` на выходе из `tests_writing` и в `preflight`: трассируемость, строка группы, статика, файл не с меткой и не Python; прежние исходы у артели, `test_profile` и явной пары.

Группа: долгоживущий
Красен до реализации: запись с компонентом `pult-vitest` и полем `long_lived` отказывает «long_lived исполняется после G2б» — профиль проекта не прочитан, переход и предпроверка отказывают на профиле, не доходя до трассируемости, групп и статики (AC-6…AC-10), чекпоинт не коммитит долгоживущий файл, перечня нет (AC-5), `amend-tests` не находит ветку документов, `plank-run` ищет путь в планке (AC-11, AC-12); у правила планки нет разбора строки группы и заявки мутации в комментарии, так что `.test.jsx` планки без строки группы проходит гейт групп; прежние исходы артели, `test_profile` и явной пары (AC-13) держат поведение базы ветки и зелены с рождения.

Стенд — настоящий git (`tests.sandbox.GitignoreCommittedRealGitSandbox`):
клон артели — корень песочницы с bare `origin`; учебные внешние проекты —
`tests.sandbox.make_project_repo` со своим `origin` и записью в
`targets.yaml` песочницы. Задачи заведены в БД (`store.insert_task`),
рабочая копия кода — `workspace.ensure`, черновик планки — в каталоге
документов. Переход — штатные чекпоинты шага
(`checkpoint.commit_step_artifacts`, `checkpoint.commit_success_checkpoint`)
и `fsm.cmd_advance`; текст места — detail записи журнала отказа.
Предпроверка — `preflight.cmd_preflight`; текст места — строки раздела.
Связка «запись проекта — профиль — дифф кодовой ветки — FSM».

Раннер Vitest не нужен ни одному отказу (гейты групп и долгоживущих стоят
до сухого сбора), но переход без отказа доходит до сухого сбора: запуск
`node_modules/.bin/vitest` и установка подменены шпионом
`subprocess.Popen` без Node и без сети (отчёт пульта с одним тестом);
прочие вызовы — настоящий `subprocess`.

AC-10 требует профиля, которого запись не пропустит: построенный профиль
подаётся подменой публичного `project_profile.decide` для учебного проекта
(`dataclasses.replace` настоящего профиля).

Имена проектов, подкаталогов, файлов, номера и тексты — из `random`; зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
разбор строки группы и заявки мутации в комментарии над вызовом у файлов
с меткой, признаки текста, отказ «не файл с меткой и не Python», пары
(путь, текст) в трассируемости, отказ G3б `amend-tests` — все методы файла
зелёные; снятие проверки заявки в стабе краснит методы заявки AC-8.
Сценарии прежнего поведения (AC-13) зелёные и на базе ветки; обвязка
AC-5/AC-11/AC-12 отдельно прогнана на записи с явной парой той же формы.
"""
import contextlib
import dataclasses
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from orchestrator import (amend, checkpoint, config, fsm, github_adapter,
                          plank_run, preflight, project_profile, store,
                          workspace)
from orchestrator.advance_gates import acceptance as acceptance_gates
from orchestrator.advance_gates import tests_writing as transition_gates
from scripts import guard
from tests.sandbox import (ARTEL_TEST_PROFILE, GitignoreCommittedRealGitSandbox,
                           make_project_repo)

REAL_POPEN = subprocess.Popen
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
TASKS_DIR = "tasks"
PLANK_DIR = "acceptance_tests"
HEADER = re.compile(r"^(\S.*?): (пройдена|отказ)$")
TRACE_ACTION = "переход отклонён: трассируемость AC"
TEMPLATE = "frontend/src/<dir>/<name>.<id>.test.jsx"
FIRST_COMMENT = "в первом комментарии файла"
NOT_LABELLED = ("не файл с меткой AC-<n>: и не Python — группа и статика не "
                "проверяемы")
NO_CLAIM_TAIL = ("долгоживущего файла без «Ловит мутацию: …» в комментарии "
                 "над вызовом")
VITEST_BIN = project_profile.VITEST_BASE_ARGV[0]
VITEST_REPORT_ARGS = ["--reporter=default", "--reporter={pult_reporter}",
                      "--outputFile={path}"]

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def spec_text(task_id: str, numbers) -> str:
    items = "\n\n".join(f"AC-{n}. Критерий фикстуры номер {n}." for n in
                        sorted(numbers))
    return ("---\ntask: " + task_id + "\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n"
            "# SPEC: фикстура меток\n\n## Контекст\n\n## Требования\n\n"
            f"## Критерии приёмки\n\n{items}\n\n## Не входит\n")


def sections(output: str) -> dict:
    """{проверка: (исход, [строки])} вывода предпроверки."""
    found, current = {}, None
    for raw in output.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line[0].isspace():
            if current is not None:
                current[1].append(line.strip())
            continue
        match = HEADER.match(line)
        current = None
        if match:
            current = (match.group(2), [])
            found[match.group(1)] = current
    return found


def arg_value(args: list, flag: str) -> str | None:
    for i, arg in enumerate(args):
        if arg == flag and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith(flag + "="):
            return arg[len(flag) + 1:]
    return None


class LabelledSandbox(GitignoreCommittedRealGitSandbox):
    """Клон артели с `origin`; учебные проекты и задачи заводит сценарий."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        fake = Path(tempfile.mkdtemp(prefix="artel-fake-")).resolve()
        self.addCleanup(shutil.rmtree, fake, True)
        self.installer = fake / f"install{self.word()}"
        self.installer.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.installer.chmod(0o755)
        self.vitest_version = next(
            f"{major}.0.0" for major, flags in
            project_profile.VITEST_VERSION_FLAGS.items()
            if flags.require_assertions)
        self.vitest_runs: list = []
        for patcher in (
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  lambda *args, **kwargs: (True, "")),
                mock.patch.object(subprocess, "Popen", self.spy_popen)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        self.clones = {config.DEFAULT_TARGET: self.root}
        self.conn = store.db()

    # --- входы ----------------------------------------------------------

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # --- шпион Vitest ---------------------------------------------------

    def answer(self, code: int, out: str, args, kwargs):
        script = f"import sys; sys.stdout.write({out!r}); sys.exit({code})"
        return REAL_POPEN([sys.executable, "-c", script], *args, **kwargs)

    def spy_popen(self, argv, *args, **kwargs):
        if not isinstance(argv, (list, tuple)) or not argv:
            return REAL_POPEN(argv, *args, **kwargs)
        parts = [str(a) for a in argv]
        if parts[0] == str(self.installer):
            cwd = Path(str(kwargs.get("cwd") or os.getcwd()))
            (cwd / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)
            return self.answer(0, "", args, kwargs)
        if parts[0] != VITEST_BIN:
            return REAL_POPEN(argv, *args, **kwargs)
        if parts[1:2] == ["--version"]:
            return self.answer(0, f"vitest/{self.vitest_version}\n", args, kwargs)
        self.vitest_runs.append(parts)
        path = arg_value(parts, "--outputFile")
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps({"tests": [{
                "file": "frontend/src/a.test.jsx", "name": "ok",
                "state": "pass", "mode": "run", "fails": False,
                "retry_count": 0, "error_name": None, "timeout": False,
                "hook": None, "duration_ms": 5}]}), encoding="utf-8")
        return self.answer(0, "1 passed in 0.01s\n", args, kwargs)

    # --- проекты --------------------------------------------------------

    def vitest_fields(self, template: bool) -> dict:
        fields = {"command": flow(project_profile.VITEST_BASE_ARGV),
                  "report": "pult-vitest",
                  "report_args": flow(VITEST_REPORT_ARGS),
                  "failure_errors": flow(["AssertionError"]),
                  "select": flow([f"--sel{self.word()}", "{tests}"]),
                  "install": flow([str(self.installer)]),
                  "tests": flow(["frontend/src/**/*.test.jsx"]),
                  "plank_layout": f"frontend/src/.pv{self.word(5)}/<id>",
                  "weakening_scope": flow(["frontend/src/**"]),
                  "mutation_claim_scope": flow(["frontend/src/**"])}
        if template:
            fields["long_lived"] = TEMPLATE
        else:
            fields.update(long_lived_dir="frontend/src",
                          long_lived_name="<id>_<name>.test.js")
        return fields

    def append_entry(self, text: str) -> None:
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + text,
                                  encoding="utf-8")

    def vitest_project(self, template: bool = True) -> str:
        """Учебный проект с единственным компонентом `pult-vitest`:
        шаблон `long_lived` либо явная пара `frontend/src` /
        `<id>_<name>.test.js`."""
        name, comp = f"v{self.word()}", f"c{self.word()}"
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 f"      {comp}:\n"]
        for key, value in self.vitest_fields(template).items():
            lines.append(f"        {key}: {value}\n")
        lines.append("        tools:\n")
        lines.append(f'          vitest: "{self.vitest_version}"\n')
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        files = {"package.json": '{"name": "web"}\n',
                 "vitest.config.js": "export default {}\n",
                 "package-lock.json": json.dumps({"lockfileVersion": 3}) + "\n",
                 "frontend/src/app.jsx": "export const app = 1;\n"}
        for rel, text in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.clones[name] = clone
        return name

    def python_project(self) -> str:
        """Учебный проект с записью `test_profile` на pytest (как sled):
        `tests`, `test_<id>_<name>.py`."""
        name = f"s{self.word()}"
        self.clones[name] = make_project_repo(name)
        self.append_entry(ARTEL_TEST_PROFILE)
        return name

    # --- задачи ---------------------------------------------------------

    def new_task(self, target: str, numbers=(1,), state: str = "tests_writing"):
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, "Фикстура меток", state, branch,
                          target, 25.0)
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                            target=target, wt=Path(wt))
        t.docs = config.PROJECTS / target / TASKS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(tid, numbers),
                                        encoding="utf-8")
        return t

    def write_plank(self, t, files: dict) -> None:
        # Чекпоинт шага уносит черновик в ссылку документов и чистит каталог.
        t.plank.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (t.plank / name).write_text(text, encoding="utf-8")

    def write_code(self, t, rel: str, text: str) -> None:
        path = t.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def labelled_rel(self, t, ext: str = "test.jsx") -> str:
        """Путь долгоживущего файла задачи по шаблону, со случайной
        глубиной `<каталог>` (от нуля до двух сегментов)."""
        depth = self.rng.randint(0, 2)
        sub = "".join(f"{self.word(5)}/" for _ in range(depth))
        return f"frontend/src/{sub}{self.word()}.{t.low}.{ext}"

    # --- тексты фикстур -------------------------------------------------

    def plank_jsx(self, numbers=(1,), head: str | None = None) -> str:
        """Файл планки с меткой: строка группы «разовый», маркер красноты,
        по тесту `it('AC-<n>: …')` на критерий."""
        if head is None:
            head = ("// Группа: разовый\n"
                    f"// Красен до реализации: фикстура {self.word()}.\n")
        body = "".join(f"it('AC-{n}: кнопка {self.word()}', () => "
                       f"{{ expect({n}).toBe({n}); }});\n" for n in numbers)
        return head + "import { expect, it } from 'vitest';\n\n" + body

    def claim(self) -> str:
        return f"// Ловит мутацию: фикстура {self.word()} — сумма другая.\n"

    def long_jsx(self, numbers=(1,), head: str | None = None,
                 claims: bool = True) -> str:
        """Долгоживущий файл с меткой: строка группы «долгоживущий» в
        первом комментарии и «Ловит мутацию: …» над каждым вызовом."""
        if head is None:
            head = ("// Группа: долгоживущий\n"
                    f"// Красен до реализации: фикстура {self.word()}.\n")
        body = ""
        for n in numbers:
            body += (self.claim() if claims else "") + (
                f"it('AC-{n}: модуль {self.word()}', () => "
                f"{{ expect({n} + 1).toBe({n + 1}); }});\n\n")
        return head + "import { expect, it } from 'vitest';\n\n" + body

    def one_off_py(self, numbers=(1,)) -> str:
        name = self.word()
        lines = ['"""Разовая фикстура ' + name + ".", "",
                 "Группа: " + guard.GROUP_ONE_OFF,
                 "Красен " + "до реализации: фикстура " + name + " ждёт кода.",
                 '"""', "import unittest", "", "",
                 "class FixturePlankTest(unittest.TestCase):", ""]
        for n in numbers:
            lines += [f"    def test_ac{n}_{name}(self):",
                      '        """Фикстурный метод."""',
                      "        self.assertEqual(2 + 2, 4)", ""]
        return "\n".join(lines)

    def long_py(self, group: str = guard.GROUP_LONG_LIVED,
                claim: bool = True) -> str:
        name = self.word()
        lines = ['"""Долгоживущая фикстура ' + name + ".", "",
                 "Группа: " + group,
                 "Красен " + "до реализации: фикстура " + name + " ждёт кода.",
                 '"""', "import random", "import unittest", "", "",
                 "class FixtureLongLivedTest(unittest.TestCase):", "",
                 f"    def test_ac1_{name}(self):",
                 '        """Фикстурный метод.']
        if claim:
            lines += ["", "        Ловит " + "мутацию: фикстура " + name
                      + " — сумма перестаёт совпадать."]
        lines += ['        """', "        seed = random.randrange(1 << 30)",
                  '        self.assertEqual(seed + 1, 1 + seed, f"зерно: {seed}")',
                  ""]
        return "\n".join(lines)

    # --- места ----------------------------------------------------------

    def advance(self, t, checkpoint_code: bool = True) -> tuple:
        """Черновик — в ссылку документов (и кодовую ветку чекпоинтом
        шага), затем `advance`: (новые записи журнала, вывод)."""
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        if checkpoint_code:
            checkpoint.commit_success_checkpoint(self.conn, t.id, "test_author")
        before = len(store.task_steps(self.conn, t.id))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(t.id)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        return rows, buf.getvalue()

    def details(self, rows: list, action: str) -> list:
        return [r["detail"] or "" for r in rows if r["action"] == action]

    def refusal(self, t, action: str, **kwargs) -> str:
        """detail записи отказа `action` перехода задачи `t`; провал —
        записи нет."""
        rows, output = self.advance(t, **kwargs)
        found = self.details(rows, action)
        self.assertTrue(found, self.note(
            f"advance не записал «{action}»:\n"
            f"{[(r['action'], r['detail']) for r in rows]}\n{output}"))
        return found[-1]

    def run_preflight(self, t) -> tuple:
        """(разделы, весь вывод) предпроверки задачи `t`."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                preflight.cmd_preflight(t.id)
            except SystemExit as exc:
                out.write(f"\nSystemExit: {exc.code}")
        output = out.getvalue()
        return sections(output), output

    def preflight_lines(self, t, check: str) -> tuple:
        """(исход, строки) раздела `check` предпроверки задачи `t`."""
        found, output = self.run_preflight(t)
        self.assertIn(check, found, self.note(f"нет раздела {check}:\n{output}"))
        return found[check]

    def lines_of(self, text: str, rel: str) -> list:
        """Ошибки текста места, относящиеся к файлу `rel`."""
        parts = re.split(r"; |\n", text)
        return [p for p in parts if rel in p]


# ---------------------------------------------------------------- AC-6

class Ac6LabelledTraceabilityTest(LabelledSandbox):

    def test_ac6_long_lived_it_label_covers_criterion_on_transition(self):
        """`it('AC-n: …')` долгоживущего `.jsx` покрывает AC-n на выходе из `tests_writing`.

        Сценарий: SPEC с тремя критериями (номера от зерна); планка
        `.test.jsx` покрывает второй, долгоживущий файл по шаблону —
        первый, третий не покрыт ничем. Переход отклонён записью
        «переход отклонён: трассируемость AC»: в ней третий критерий и нет
        первого.

        Ловит мутацию: долгоживущие источники трассируемости разбираются
        только как Python (`def test_ac<n>_`) — первый критерий тоже
        назван непокрытым; источники переданы без пути — правило планки не
        узнаёт файл с меткой, и первый критерий не покрыт.
        """
        a, b, c = self.rng.sample(range(2, 40), 3)
        name = self.vitest_project()
        t = self.new_task(name, numbers=(a, b, c))
        self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx((b,))})
        self.write_code(t, self.labelled_rel(t), self.long_jsx((a,)))
        detail = self.refusal(t, TRACE_ACTION)
        self.assertIn(f"AC-{c}:", detail, self.note(detail))
        self.assertNotIn(f"AC-{a}:", detail, self.note(detail))

    def test_ac6_long_lived_it_label_covers_criterion_in_preflight(self):
        """`it('AC-n: …')` долгоживущего `.jsx` рабочей копии покрывает AC-n в разделе трассируемости предпроверки.

        Сценарий: тот же черновик, что у перехода, без чекпоинтов:
        раздел «трассируемость AC» — отказ, его строки называют третий
        критерий и не называют первый.

        Ловит мутацию: предпроверка передаёт долгоживущие тексты без
        правила планки — первый критерий не покрыт.
        """
        a, b, c = self.rng.sample(range(2, 40), 3)
        name = self.vitest_project()
        t = self.new_task(name, numbers=(a, b, c))
        self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx((b,))})
        self.write_code(t, self.labelled_rel(t), self.long_jsx((a,)))
        outcome, lines = self.preflight_lines(t, preflight.CHECK_TRACEABILITY)
        text = "\n".join(lines)
        self.assertEqual(outcome, preflight.REFUSED, self.note(text))
        self.assertIn(f"AC-{c}:", text, self.note(text))
        self.assertNotIn(f"AC-{a}:", text, self.note(text))

    def test_ac6_traceability_errors_extra_sources_with_rule(self):
        """`guard.acceptance_traceability_errors` с правилом планки засчитывает `it('AC-n: …')` долгоживущего файла из `extra_sources` парой (путь, текст).

        Сценарий: каталог задачи во временном каталоге — SPEC с тремя
        критериями, планка `.test.jsx` покрывает второй; `extra_sources` —
        пара (путь долгоживущего файла, текст с `it('AC-<первый>: …')`),
        правило — `project_profile.plank_rule` учебного проекта. Ошибки
        называют третий критерий и не называют первый.

        Ловит мутацию: `extra_sources` разбираются без правила — метка
        `it(...)` не засчитана, первый критерий в ошибках.
        """
        a, b, c = self.rng.sample(range(2, 40), 3)
        name = self.vitest_project()
        rule = project_profile.plank_rule(name)
        tdir = Path(tempfile.mkdtemp(prefix="trace-", dir=self.root))
        (tdir / "SPEC.md").write_text(spec_text(ulid(self.rng), (a, b, c)),
                                      encoding="utf-8")
        (tdir / PLANK_DIR).mkdir()
        (tdir / PLANK_DIR / f"ac{self.word()}.test.jsx").write_text(
            self.plank_jsx((b,)), encoding="utf-8")
        rel = f"frontend/src/{self.word()}/{self.word()}.{ulid(self.rng).lower()}.test.jsx"
        errors = "\n".join(guard.acceptance_traceability_errors(
            tdir, extra_sources=[(rel, self.long_jsx((a,)))], rule=rule))
        self.assertIn(f"AC-{c}:", errors, self.note(errors))
        self.assertNotIn(f"AC-{a}:", errors, self.note(errors))


# ---------------------------------------------------------------- AC-7

class Ac7LabelledGroupLineTest(LabelledSandbox):

    def heads(self) -> list:
        """(случай, первый комментарий) без строки «Группа: долгоживущий»."""
        return [("нет строки группы",
                 f"// Красен до реализации: фикстура {self.word()}.\n"),
                ("иное значение",
                 f"// Группа: {self.word()}\n"
                 f"// Красен до реализации: фикстура {self.word()}.\n")]

    def test_ac7_missing_group_line_refused_on_transition(self):
        """Долгоживущий `.jsx` без «Группа: долгоживущий» в первом комментарии — отказ выхода из `tests_writing` с именем файла и «в первом комментарии файла».

        Сценарий: для каждого случая (нет строки группы; иное значение) —
        планка покрывает критерий, долгоживущий файл по шаблону с таким
        первым комментарием; запись отказа долгоживущих файлов называет
        путь файла и фразу «в первом комментарии файла».

        Ловит мутацию: строка группы файла с меткой читается из докстринга
        Python — файл молча пропущен (`.jsx` не разбирается), отказа нет;
        место в тексте — «в докстринге модуля».
        """
        name = self.vitest_project()
        for label, head in self.heads():
            with self.subTest(case=label, seed=self.seed):
                t = self.new_task(name)
                self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx()})
                rel = self.labelled_rel(t)
                self.write_code(t, rel, self.long_jsx(head=head))
                detail = self.refusal(t, transition_gates.LONG_LIVED_ACTION)
                mine = "\n".join(self.lines_of(detail, rel))
                self.assertIn(FIRST_COMMENT, mine, self.note(detail))

    def test_ac7_missing_group_line_refused_in_preflight(self):
        """Тот же долгоживущий `.jsx` — отказ раздела «долгоживущие файлы» предпроверки с именем файла и «в первом комментарии файла».

        Сценарий: для каждого случая — черновик задачи без чекпоинтов;
        раздел «долгоживущие файлы» — отказ, строка с путём файла несёт
        фразу «в первом комментарии файла».

        Ловит мутацию: `preflight` разбирает долгоживущие файлы только как
        Python — раздел «пройдена».
        """
        name = self.vitest_project()
        for label, head in self.heads():
            with self.subTest(case=label, seed=self.seed):
                t = self.new_task(name)
                self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx()})
                rel = self.labelled_rel(t)
                self.write_code(t, rel, self.long_jsx(head=head))
                outcome, lines = self.preflight_lines(t, preflight.CHECK_LONG_LIVED)
                mine = "\n".join(line for line in lines if rel in line)
                self.assertEqual(outcome, preflight.REFUSED, self.note(str(lines)))
                self.assertIn(FIRST_COMMENT, mine, self.note(str(lines)))

    def test_ac7_block_comment_group_line_recognized(self):
        """Строка группы в блоке `/* … */` с ведущей « * » распознаётся — ни переход, ни предпроверка не называют строку группы файла.

        Сценарий: долгоживущий файл с первым комментарием
        `/*\\n * Группа: долгоживущий\\n * Красен до реализации: …\\n */` и
        одним вызовом без «Ловит мутацию: …» (чтобы гейт заведомо
        отработал). Отказ перехода и раздел предпроверки называют файл
        только за заявку мутации: строк «в первом комментарии файла» и
        «Группа: долгоживущий» о файле нет.

        Ловит мутацию: ведущая « * » не снимается — «Группа:» не в начале
        строки комментария, строка группы не найдена.
        """
        name = self.vitest_project()
        head = ("/*\n * Группа: долгоживущий\n"
                f" * Красен до реализации: фикстура {self.word()}.\n */\n")
        t = self.new_task(name)
        self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx()})
        rel = self.labelled_rel(t)
        self.write_code(t, rel, self.long_jsx(head=head, claims=False))
        outcome, lines = self.preflight_lines(t, preflight.CHECK_LONG_LIVED)
        detail = self.refusal(t, transition_gates.LONG_LIVED_ACTION)
        for place, text in (("переход", "\n".join(self.lines_of(detail, rel))),
                            ("preflight", "\n".join(l for l in lines if rel in l))):
            with self.subTest(place=place, seed=self.seed):
                self.assertIn(NO_CLAIM_TAIL, text, self.note(text))
                self.assertNotIn(FIRST_COMMENT, text, self.note(text))
                self.assertNotIn("нет строки «Группа", text, self.note(text))


# ---------------------------------------------------------------- AC-8

class Ac8LabelledStaticsTest(LabelledSandbox):

    def both_places(self, source_of) -> tuple:
        """(строки перехода о файле, строки предпроверки о файле, путь,
        задача предпроверки) для долгоживущего файла `source_of(t)`."""
        name = self.vitest_project()
        texts = {}
        for place in ("переход", "preflight"):
            t = self.new_task(name)
            self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx()})
            rel = self.labelled_rel(t)
            self.write_code(t, rel, source_of(t))
            if place == "preflight":
                outcome, lines = self.preflight_lines(t, preflight.CHECK_LONG_LIVED)
                texts[place] = (outcome, [l for l in lines if l.startswith(rel)], rel)
            else:
                rows, output = self.advance(t)
                found = self.details(rows, transition_gates.LONG_LIVED_ACTION)
                texts[place] = (found, self.lines_of(found[-1], rel) if found else [],
                                rel, output, rows)
        return texts

    def assert_refused_line(self, source_of, expected_of) -> None:
        """Оба места отказывают строкой `expected_of(путь, задача)`."""
        texts = self.both_places(source_of)
        for place, data in texts.items():
            with self.subTest(place=place, seed=self.seed):
                rel, lines = data[2], data[1]
                expected = expected_of(rel)
                self.assertTrue(any(expected in line for line in lines),
                                self.note(f"{place}: нет «{expected}»: {data}"))

    def assert_passes(self, source_of) -> None:
        """Ни одно место не называет файл."""
        texts = self.both_places(source_of)
        found, lines, rel = texts["переход"][:3]
        self.assertEqual(lines, [], self.note(f"переход: {texts['переход']}"))
        outcome, plines, _rel = texts["preflight"]
        self.assertEqual(plines, [], self.note(f"preflight: {texts['preflight']}"))
        self.assertEqual(outcome, preflight.PASSED,
                         self.note(f"preflight: {texts['preflight']}"))

    def sign_line(self, rel: str, line: int, sign: str) -> str:
        return f"{rel}:{line}: признак «{sign}»"

    def test_ac8_tasks_literal_in_code_refused(self):
        """Литерал каталога задач с косой чертой в коде долгоживущего `.jsx` — отказ обоих мест с путём, номером строки и признаком `guard.SIGN_TASKS`.

        Сценарий: в теле файла строка `const p = '<каталог задач>/x';` —
        строка с номером от состава файла; переход и предпроверка несут
        «<путь>:<строка>: признак «<SIGN_TASKS>»».

        Ловит мутацию: статика файла с меткой не исполняется (разбор только
        Python) — отказа нет; номер строки считается от первого вызова
        теста, а не от начала файла.
        """
        literal = TASKS_DIR + "/"

        def source(t):
            text = self.long_jsx()
            return text + f"const p = '{literal}{self.word()}';\n"

        self.assert_refused_line(
            self.remember(source, literal),
            lambda rel: self.sign_line(rel, self.needle_line, guard.SIGN_TASKS))

    def remember(self, source_of, needle: str):
        """Обёртка `source_of`, запоминающая номер строки `needle` в
        последнем тексте."""
        def wrapped(t):
            text = source_of(t)
            self.needle_line = next(i for i, line in
                                    enumerate(text.splitlines(), start=1)
                                    if needle.lower() in line.lower())
            return text
        return wrapped

    def test_ac8_tasks_literal_in_comment_refused(self):
        """Литерал каталога задач с косой чертой в комментарии долгоживущего `.jsx` — тот же отказ с номером строки комментария.

        Сценарий: строка `// путь <каталог задач>/x` между вызовами; оба
        места несут «<путь>:<строка>: признак «<SIGN_TASKS>»».

        Ловит мутацию: признак ищется только вне комментариев — отказа нет.
        """
        literal = TASKS_DIR + "/"

        def source(t):
            return self.long_jsx() + f"// путь {literal}{self.word()}\n"

        self.assert_refused_line(
            self.remember(source, literal),
            lambda rel: self.sign_line(rel, self.needle_line, guard.SIGN_TASKS))

    def test_ac8_task_id_any_case_refused(self):
        """Идентификатор задачи в любом регистре, в коде и в комментарии, — отказ обоих мест с номером строки и признаком «номер задачи».

        Сценарий: для каждого варианта (верхний регистр в строке кода,
        нижний регистр в комментарии, смешанный регистр в коде) файл несёт
        id своей задачи; оба места несут «<путь>:<строка>: признак «номер
        задачи»».

        Ловит мутацию: сравнение с учётом регистра — вариант в другом
        регистре проходит; комментарии исключены — вариант в комментарии
        проходит.
        """
        variants = [
            ("верхний в коде", lambda tid: f"const id = '{tid.upper()}';\n"),
            ("нижний в комментарии", lambda tid: f"// задача {tid.lower()}\n"),
            ("смешанный в коде", lambda tid: "const id = '"
             + "".join(ch.lower() if i % 2 else ch for i, ch in enumerate(tid))
             + "';\n"),
        ]
        for label, tail in variants:
            with self.subTest(case=label, seed=self.seed):
                def source(t, tail=tail):
                    return self.long_jsx() + tail(t.id)

                def wrapped(t, source=source):
                    text = source(t)
                    self.needle_line = len(text.splitlines())
                    return text
                self.assert_refused_line(
                    wrapped, lambda rel: self.sign_line(rel, self.needle_line,
                                                        guard.SIGN_TASK_ID))

    def call_refusal(self, rel: str, line: int, name: str) -> str:
        return f"{rel}:{line}: тест «{name}» {NO_CLAIM_TAIL}"

    def test_ac8_call_without_claim_refused(self):
        """Вызов теста без «Ловит мутацию: …» в комментарии над ним — отказ обоих мест с путём, строкой головы вызова и именем теста.

        Сценарий: файл с двумя вызовами `it('AC-1: …')`, у второго заявки
        нет; оба места несут «<путь>:<строка>: тест «<имя>» долгоживущего
        файла без «Ловит мутацию: …» в комментарии над вызовом» для
        второго вызова.

        Ловит мутацию: заявка ищется в любом месте файла — одна заявка на
        файл покрывает оба вызова, отказа нет.
        """
        test_name = f"AC-1: модуль {self.word()}"

        def source(t):
            text = self.long_jsx()
            text += f"it('{test_name}', () => {{ expect(1).toBe(1); }});\n"
            self.needle_line = len(text.splitlines())
            return text
        self.assert_refused_line(
            source, lambda rel: self.call_refusal(rel, self.needle_line, test_name))

    def test_ac8_blank_line_breaks_claim_comment(self):
        """Пустая строка между комментарием «Ловит мутацию: …» и вызовом обрывает комментарий — отказ обоих мест.

        Сценарий: над вторым вызовом — комментарий с заявкой, затем пустая
        строка, затем вызов; оба места несут отказ вызова без заявки для
        него.

        Ловит мутацию: комментарий над вызовом ищется через пустые строки —
        заявка засчитана, отказа нет.
        """
        test_name = f"AC-1: модуль {self.word()}"

        def source(t):
            text = self.long_jsx() + self.claim() + "\n"
            text += f"it('{test_name}', () => {{ expect(1).toBe(1); }});\n"
            self.needle_line = len(text.splitlines())
            return text
        self.assert_refused_line(
            source, lambda rel: self.call_refusal(rel, self.needle_line, test_name))

    def test_ac8_clean_file_with_claims_passes(self):
        """Файл с «Ловит мутацию: …» над каждым вызовом и без признаков — ни переход, ни предпроверка его не называют.

        Сценарий: долгоживущий `.jsx` с тремя вызовами (`it`, `test`, `it`
        с номерами от зерна), над каждым — заявка; раздел «долгоживущие
        файлы» предпроверки — «пройдена», в отказах перехода файла нет.

        Ловит мутацию: заявка требуется у каждого литерала `AC-<n>:`, а не
        у вызова, или голова вызова `test(` не распознана — ложный отказ;
        признак номера задачи срабатывает на имени файла — ложный отказ.
        """
        def source(t):
            text = self.long_jsx((1,))
            text += self.claim() + (f"test('AC-1: ещё {self.word()}', () => "
                                    "{ expect(2).toBe(2); });\n")
            return text
        self.assert_passes(source)

    def each_source(self, claim: bool, name: str):
        def source(t):
            text = self.long_jsx()
            if claim:
                text += self.claim()
            text += "it.each([\n  [1, 2],\n  [2, 3],\n])"
            self.needle_line = len(text.splitlines())
            text += f"('{name}', (a, b) => {{ expect(a + 1).toBe(b); }});\n"
            return text
        return source

    def test_ac8_each_with_multiline_table_claim_recognized(self):
        """Заявка над `it.each(` с многострочной таблицей распознаётся — файл проходит оба места.

        Сценарий: над строкой `it.each([` — комментарий «Ловит мутацию:
        …», таблица на трёх строках, затем `('AC-1: …', …)`; раздел
        предпроверки «пройдена», в отказах перехода файла нет.

        Ловит мутацию: голова вызова `.each(` считается по строке имени
        теста после таблицы — комментарий не «прямо над» ней, ложный
        отказ.
        """
        self.assert_passes(self.each_source(True, f"AC-1: таблица {self.word()}"))

    def test_ac8_each_without_claim_refused_at_head_line(self):
        """Вызов `it.each(` с многострочной таблицей без заявки — отказ обоих мест со строкой головы `.each(`.

        Сценарий: тот же вызов без комментария; оба места несут отказ
        вызова без заявки с номером строки, где стоит `.each(`.

        Ловит мутацию: `.each(` не распознан как вызов теста — отказа нет;
        строка отказа — строка имени теста, а не головы.
        """
        test_name = f"AC-1: таблица {self.word()}"
        source = self.each_source(False, test_name)

        def wrapped(t):
            text = source(t)
            self.needle_line = next(i for i, line in
                                    enumerate(text.splitlines(), start=1)
                                    if ".each(" in line)
            return text
        self.assert_refused_line(
            wrapped, lambda rel: self.call_refusal(rel, self.needle_line, test_name))

    def test_ac8_block_comment_claim_recognized(self):
        """«Ловит мутацию: …» в блоке `/* … */` с ведущей « * » над вызовом распознаётся — файл проходит оба места.

        Сценарий: над вызовом — блок `/**\\n * Ловит мутацию: …\\n */`,
        кончающийся строкой прямо над головой вызова.

        Ловит мутацию: учитываются только строки `//` — ложный отказ;
        ведущая « * » не снимается — заявка не найдена.
        """
        def source(t):
            head = ("// Группа: долгоживущий\n"
                    f"// Красен до реализации: фикстура {self.word()}.\n")
            return (head + "import { expect, it } from 'vitest';\n\n"
                    f"/**\n * Ловит мутацию: фикстура {self.word()} — иначе.\n"
                    " */\n"
                    f"it('AC-1: блок {self.word()}', () => {{ expect(1).toBe(1); }});\n")
        self.assert_passes(source)

    def test_ac8_block_comment_group_line_recognized(self):
        """«Группа: долгоживущий» в первом блоке `/* … */` с ведущей « * » распознаётся — файл проходит оба места.

        Сценарий: первый комментарий —
        `/*\\n * Группа: долгоживущий\\n * Красен до реализации: …\\n */`,
        над каждым вызовом — заявка; раздел предпроверки «пройдена», в
        отказах перехода файла нет.

        Ловит мутацию: строка группы ищется только в строках `//` — файл
        назван без строки группы.
        """
        def source(t):
            head = ("/*\n * Группа: долгоживущий\n"
                    f" * Красен до реализации: фикстура {self.word()}.\n */\n")
            return self.long_jsx(head=head)
        self.assert_passes(source)


# ---------------------------------------------------------------- AC-9

class Ac9LabelledPlankGroupTest(LabelledSandbox):

    def test_ac9_plank_jsx_without_group_line_refused(self):
        """Файл планки `.test.jsx` без строки группы в первом комментарии — отказ гейта групп перехода и раздела «строка группы» предпроверки с «в первом комментарии файла».

        Сценарий: планка — один `.test.jsx` с маркером красноты и без
        строки группы, покрывает критерий; переход записывает «переход
        отклонён: группы приёмочных тестов» с именем файла и фразой; раздел
        «строка группы» предпроверки — отказ, строка с именем файла несёт
        фразу.

        Ловит мутацию: гейт групп читает только `test_*.py` — файл с меткой
        проходит без строки группы.
        """
        name = self.vitest_project()
        head = f"// Красен до реализации: фикстура {self.word()}.\n"
        for place in ("переход", "preflight"):
            with self.subTest(place=place, seed=self.seed):
                t = self.new_task(name)
                plank_name = f"ac{self.word()}.test.jsx"
                self.write_plank(t, {plank_name: self.plank_jsx(head=head)})
                if place == "переход":
                    detail = self.refusal(t, transition_gates.TEST_GROUPS_ACTION)
                    mine = "\n".join(self.lines_of(detail, plank_name))
                else:
                    outcome, lines = self.preflight_lines(t, preflight.CHECK_GROUPS)
                    self.assertEqual(outcome, preflight.REFUSED, self.note(str(lines)))
                    mine = "\n".join(l for l in lines if plank_name in l)
                self.assertIn(FIRST_COMMENT, mine, self.note(mine))

    def test_ac9_plank_jsx_long_lived_group_names_template_example(self):
        """Файл планки с меткой и «Группа: долгоживущий» — отказ `long_lived_plank_errors` с примером `frontend/src/<каталог>/<имя>.<id>.test.jsx`.

        Сценарий: планка — `.test.jsx` с «Группа: долгоживущий» в первом
        комментарии и заявкой над вызовом; переход (гейт групп) и раздел
        «строка группы» предпроверки называют файл и «перенеси файл в
        frontend/src/<каталог>/<имя>.<id>.test.jsx кодовой ветки».

        Ловит мутацию: подсказка склеена прежним `{prefix}<имя>.py` — в
        ней `frontend/src/<dir>/` и `.py`; файл с меткой не разбирается —
        отказа нет.
        """
        name = self.vitest_project()
        for place in ("переход", "preflight"):
            with self.subTest(place=place, seed=self.seed):
                t = self.new_task(name)
                plank_name = f"ac{self.word()}.test.jsx"
                self.write_plank(t, {plank_name: self.long_jsx()})
                expected = (f"перенеси файл в frontend/src/<каталог>/<имя>."
                            f"{t.low}.test.jsx кодовой ветки")
                if place == "переход":
                    detail = self.refusal(t, transition_gates.TEST_GROUPS_ACTION)
                    mine = "\n".join(self.lines_of(detail, plank_name))
                else:
                    _outcome, lines = self.preflight_lines(t, preflight.CHECK_GROUPS)
                    mine = "\n".join(l for l in lines if plank_name in l)
                self.assertIn(expected, mine, self.note(mine))


# ---------------------------------------------------------------- AC-10

class Ac10NotLabelledNotPythonTest(LabelledSandbox):

    def built(self, name: str, template: bool):
        """Подмена `project_profile.decide`: у проекта `name` — профиль с
        шаблоном `.test.ts` (маски `tests` — только `*.test.jsx`) и
        `long_lived_template` непустым при `template`, иначе пустым."""
        real = project_profile.decide

        def decide(target):
            decision = real(target)
            if target != name or decision.profile is None:
                return decision
            profile = dataclasses.replace(
                decision.profile, long_lived_dir="frontend/src",
                long_lived_name="<dir>/<name>.<id>.test.ts",
                long_lived_template=("frontend/src/<dir>/<name>.<id>.test.ts"
                                     if template else ""))
            return dataclasses.replace(decision, profile=profile)
        return mock.patch.object(project_profile, "decide", decide)

    def texts(self, name: str, template: bool) -> tuple:
        """(строки перехода о файле, строки предпроверки о файле, путь)."""
        found = {}
        with self.built(name, template):
            for place in ("переход", "preflight"):
                t = self.new_task(name)
                self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx()})
                rel = self.labelled_rel(t, ext="test.ts")
                self.write_code(t, rel, self.long_jsx())
                if place == "переход":
                    rows, _output = self.advance(t)
                    details = self.details(rows, transition_gates.LONG_LIVED_ACTION)
                    found[place] = (rel, [l for d in details
                                          for l in self.lines_of(d, rel)])
                else:
                    sect, _output = self.run_preflight(t)
                    lines = sect.get(preflight.CHECK_LONG_LIVED, ("", []))[1]
                    found[place] = (rel, [l for l in lines if rel in l])
        return found

    def test_ac10_not_labelled_not_python_refused_same_text(self):
        """Профиль с непустым `long_lived_template` и долгоживущим `.test.ts` не под маски — отказ гейта долгоживущих перехода и предпроверки одним текстом.

        Сценарий: учебный проект с шаблоном `.test.jsx`, профиль подменён
        построенным (шаблон и имя `.test.ts`, маски `tests` прежние).
        Долгоживущий `frontend/src/<каталог>/<имя>.<id>.test.ts`: запись
        отказа долгоживущих файлов перехода и раздел «долгоживущие файлы»
        предпроверки несут «<путь>: не файл с меткой AC-<n>: и не Python —
        группа и статика не проверяемы», строки равны.

        Ловит мутацию: защитная проверка не добавлена — файл разбирается
        как Python и молча проходит; добавлена только в переход либо только
        в предпроверку — в другом месте строки нет; тексты мест различаются.
        """
        name = self.vitest_project()
        found = self.texts(name, template=True)
        lines = {}
        for place, (rel, mine) in found.items():
            expected = f"{rel}: {NOT_LABELLED}"
            with self.subTest(place=place, seed=self.seed):
                hits = [l for l in mine if expected in l]
                self.assertTrue(hits, self.note(f"{place}: {mine}"))
                lines[place] = hits[0].replace(rel, "<путь>").split(
                    "<путь>: ", 1)[1].split(";")[0]
        self.assertEqual(lines.get("переход"), lines.get("preflight"),
                         self.note(str(lines)))

    def test_ac10_empty_template_profile_no_refusal(self):
        """Тот же файл при профиле с пустым `long_lived_template` — отказа «не файл с меткой и не Python» нет ни в одном месте.

        Сценарий: подменённый профиль с теми же парой и масками, но пустым
        `long_lived_template`; строки «не файл с меткой AC-<n>: и не
        Python» о файле нет ни в отказах перехода, ни в предпроверке.

        Ловит мутацию: защитная проверка не смотрит на `long_lived_template`
        — явные пары с не-Python именем (sled) получают отказ.
        """
        name = self.vitest_project()
        found = self.texts(name, template=False)
        for place, (_rel, mine) in found.items():
            with self.subTest(place=place, seed=self.seed):
                self.assertFalse([l for l in mine if NOT_LABELLED in l],
                                 self.note(f"{place}: {mine}"))


# ---------------------------------------------------------------- AC-13

class Ac13OldOutcomesTest(LabelledSandbox):

    def test_ac13_pair_non_python_long_lived_unparsed_as_before(self):
        """Явная пара с `<id>_<name>.test.js`: долгоживущий файл без строки группы и с id задачи — ни отказа «не файл с меткой…», ни разбора группы и статики.

        Сценарий: компонент `pult-vitest` с парой `frontend/src` /
        `<id>_<name>.test.js`; файл `frontend/src/<id>_<имя>.test.js` без
        строки группы, без заявок и с id задачи в тексте. Переход не
        записывает отказа долгоживущих файлов; раздел «долгоживущие файлы»
        предпроверки — «пройдена».

        Ловит мутацию: новая проверка «не файл с меткой и не Python» или
        разбор по правилу-метке применены к явной паре — отказ о файле.
        """
        name = self.vitest_project(template=False)
        for place in ("переход", "preflight"):
            with self.subTest(place=place, seed=self.seed):
                t = self.new_task(name)
                self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx()})
                rel = f"frontend/src/{t.low}_{self.word()}.test.js"
                self.write_code(t, rel, f"// {t.id}\nit('x', () => {{}});\n")
                if place == "переход":
                    rows, output = self.advance(t)
                    self.assertEqual(
                        self.details(rows, transition_gates.LONG_LIVED_ACTION), [],
                        self.note(output))
                else:
                    outcome, lines = self.preflight_lines(t, preflight.CHECK_LONG_LIVED)
                    self.assertEqual(outcome, preflight.PASSED, self.note(str(lines)))

    def python_cases(self) -> list:
        """(вид, проект) проектов на pytest: артель и `test_profile` sled."""
        return [("артель", config.DEFAULT_TARGET), ("sled", self.python_project())]

    def long_rel(self, t) -> str:
        return f"tests/test_{t.low}_{self.word()}.py"

    def hint(self, t) -> str:
        return (f"test_author только добавляет файлы tests/test_{t.low}_<имя>.py "
                f"со строкой «Группа: долгоживущий»; верни прочее к базе ветки "
                f"и повтори artel.py advance {t.id}")

    def test_ac13_python_long_lived_refusals_unchanged(self):
        """Артель и `test_profile`: отказы долгоживущего Python-файла — прежнее действие, прежние тексты и подсказка; предпроверка — те же строки.

        Сценарий: для каждого проекта на pytest — (а) долгоживущий файл с
        методом без заявки: действие «переход отклонён: долгоживущие файлы
        tests/», строка «метод … долгоживущего файла без «Ловит мутацию: …»
        в докстринге («Зелёный с рождения» её не заменяет)», подсказка
        «test_author только добавляет файлы tests/test_<id>_<имя>.py …»;
        раздел предпроверки несёт ту же строку о методе; (б) файл с
        «Группа: разовый»: «<путь>: нет строки «Группа: долгоживущий» — в
        tests/ кодовой ветки только долгоживущие файлы».

        Ловит мутацию: разбор Python переведён на первый комментарий —
        докстринг не прочитан, отказ о группе вместо заявки; подсказка
        собрана новой функцией примера — текст иной.
        """
        self.assertEqual(transition_gates.LONG_LIVED_ACTION,
                         "переход отклонён: долгоживущие файлы tests/")
        for kind, target in self.python_cases():
            with self.subTest(kind=kind, case="заявка", seed=self.seed):
                t = self.new_task(target)
                self.write_plank(t, {f"test_{self.word()}.py": self.one_off_py()})
                rel = self.long_rel(t)
                self.write_code(t, rel, self.long_py(claim=False))
                detail = self.refusal(t, transition_gates.LONG_LIVED_ACTION)
                self.assertIn("долгоживущего файла без «Ловит мутацию: …» в "
                              "докстринге («Зелёный с рождения» её не "
                              "заменяет)", detail, self.note(detail))
                self.assertIn(self.hint(t), detail, self.note(detail))
                t2 = self.new_task(target)
                self.write_plank(t2, {f"test_{self.word()}.py": self.one_off_py()})
                rel2 = self.long_rel(t2)
                self.write_code(t2, rel2, self.long_py(claim=False))
                _outcome, lines = self.preflight_lines(t2, preflight.CHECK_LONG_LIVED)
                self.assertTrue(any(l.startswith(rel2) and "в докстринге" in l
                                    for l in lines), self.note(str(lines)))
            with self.subTest(kind=kind, case="группа", seed=self.seed):
                t = self.new_task(target)
                self.write_plank(t, {f"test_{self.word()}.py": self.one_off_py()})
                rel = self.long_rel(t)
                self.write_code(t, rel, self.long_py(group=guard.GROUP_ONE_OFF))
                detail = self.refusal(t, transition_gates.LONG_LIVED_ACTION)
                self.assertIn(f"{rel}: нет строки «Группа: долгоживущий» — в "
                              f"tests/ кодовой ветки только долгоживущие файлы",
                              detail, self.note(detail))

    def test_ac13_python_plank_group_refusals_unchanged(self):
        """Артель и `test_profile`: гейт групп планки на Python — прежние тексты «в докстринге модуля» и «перенеси файл в tests/test_<id>_<имя>.py».

        Сценарий: для каждого проекта на pytest — планка с `test_*.py` без
        строки группы (рядом файл, покрывающий критерий): «нет строки
        группы в докстринге модуля — допиши …»; планка с файлом «Группа:
        долгоживущий»: ««Группа: долгоживущий» в каталоге приёмочных тестов
        — перенеси файл в tests/test_<id>_<имя>.py кодовой ветки».

        Ловит мутацию: текст места строки группы заменён для всех файлов —
        «в первом комментарии файла» у Python; подсказка переноса собрана
        функцией примера — иной хвост.
        """
        for kind, target in self.python_cases():
            with self.subTest(kind=kind, case="нет строки", seed=self.seed):
                t = self.new_task(target)
                bare = f"test_{self.word()}.py"
                self.write_plank(t, {f"test_{self.word()}.py": self.one_off_py(),
                                     bare: '"""Без группы.\n\nКрасен до '
                                     'реализации: фикстура."""\n'})
                detail = self.refusal(t, transition_gates.TEST_GROUPS_ACTION)
                self.assertIn(f"{bare}: нет строки группы в докстринге модуля — "
                              f"допиши «Группа: долгоживущий» или «Группа: "
                              f"разовый»", detail, self.note(detail))
            with self.subTest(kind=kind, case="долгоживущий в планке", seed=self.seed):
                t = self.new_task(target)
                moved = f"test_{self.word()}.py"
                self.write_plank(t, {f"test_{self.word()}.py": self.one_off_py(),
                                     moved: self.long_py()})
                detail = self.refusal(t, transition_gates.TEST_GROUPS_ACTION)
                self.assertIn(f"{moved}: «Группа: долгоживущий» в каталоге "
                              f"приёмочных тестов — перенеси файл в "
                              f"tests/test_{t.low}_<имя>.py кодовой ветки",
                              detail, self.note(detail))

    def commit_code(self, t, changes: dict, message: str) -> None:
        """Коммит в кодовую ветку мимо чекпоинта: {путь: текст | None
        (удалить) | ("ссылка", цель) | ("из", старый путь)}."""
        for rel, value in changes.items():
            path = t.wt / rel
            if value is None:
                self.git("-C", str(t.wt), "rm", "-q", "--", rel)
                continue
            if isinstance(value, tuple) and value[0] == "из":
                self.git("-C", str(t.wt), "mv", value[1], rel)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() or path.is_symlink():
                path.unlink()
            if isinstance(value, tuple):
                os.symlink(value[1], path)
            else:
                path.write_text(value, encoding="utf-8")
            self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", message)

    def test_ac13_diff_entry_refusals_unchanged(self):
        """`test_profile` на pytest: отказы правила «только добавление» — прежние тексты каждой записи диффа.

        Сценарий: в `main` проекта — файлы `tests/base_<…>.py`; кодовая
        ветка задачи коммитом мимо чекпоинта несёт по сценарию:
        переименование, правку, удаление файла базы, замену файла базы
        символьной ссылкой (иной статус), файл вне `tests/`, файл в
        `tests/` без префикса задачи. Запись отказа долгоживущих файлов
        несёт прежний текст своей записи диффа: «переименование/копия —
        test_author не трогает существующие файлы», «правка файла базы
        ветки — существующие файлы не трогаются», «удаление файла базы
        ветки — существующие файлы не трогаются», «изменение «T» —
        допустимо только добавление», «путь вне tests/ — кодовая ветка
        несёт только файлы tests/», «файл без префикса задачи — имя
        tests/test_<id>_<имя>.py».

        Ловит мутацию: правило имени с `<dir>` применено к прежнему
        шаблону — файл без префикса признан своим; пример в отказе собран
        новой функцией — иной хвост; ветвь иного статуса снята.
        """
        target = self.python_project()
        clone = self.clones[target]
        bases = {f"tests/base_{self.word()}.py": "X = 1\n" for _ in range(4)}
        for rel, text in bases.items():
            (clone / rel).parent.mkdir(parents=True, exist_ok=True)
            (clone / rel).write_text(text, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "база")
        self.git("-C", str(clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        b1, b2, b3, b4 = sorted(bases)
        cases = [
            ("переименование", lambda t: {f"tests/moved_{self.word()}.py": ("из", b1)},
             "переименование/копия — test_author не трогает существующие файлы"),
            ("правка", lambda t: {b2: "X = 2\n"},
             f"{b2}: правка файла базы ветки — существующие файлы не трогаются"),
            ("удаление", lambda t: {b3: None},
             f"{b3}: удаление файла базы ветки — существующие файлы не трогаются"),
            ("иной статус", lambda t: {b4: ("ссылка", "elsewhere.py")},
             f"{b4}: изменение «T» — допустимо только добавление"),
            ("вне каталога", lambda t: {f"other/x_{self.word()}.py": "Y = 1\n"},
             "путь вне tests/ — кодовая ветка несёт только файлы tests/"),
            ("без префикса", lambda t: {f"tests/test_{self.word()}.py": "Z = 1\n"},
             None),
        ]
        for label, change_of, expected in cases:
            with self.subTest(case=label, seed=self.seed):
                t = self.new_task(target)
                self.write_plank(t, {f"test_{self.word()}.py": self.one_off_py()})
                changes = change_of(t)
                self.commit_code(t, changes, label)
                if expected is None:
                    rel = next(iter(changes))
                    expected = (f"{rel}: файл без префикса задачи — имя "
                                f"tests/test_{t.low}_<имя>.py")
                detail = self.refusal(t, transition_gates.LONG_LIVED_ACTION,
                                      checkpoint_code=False)
                self.assertIn(expected, detail, self.note(detail))
                self.assertIn(self.hint(t), detail, self.note(detail))


# ---------------------------------------------------------------- AC-5

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: фикстура

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class Ac5LabelledLongLivedFlowTest(LabelledSandbox):

    def branch_files(self, t) -> list:
        out = self.git("-C", str(t.wt), "ls-tree", "-r", "--name-only", t.branch)
        return out.split()

    def commit_code(self, t, files: dict, message: str) -> None:
        for rel, text in files.items():
            self.write_code(t, rel, text)
            self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", message)

    def developer_advance(self, t) -> tuple:
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "PLAN.md").write_text(PLAN_READY.format(task=t.id),
                                        encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        before = len(store.task_steps(self.conn, t.id))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(t.id)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        return rows, buf.getvalue()

    def test_ac5_checkpoint_manifest_verification_and_zones(self):
        """Долгоживущий `frontend/src/components/button.<id>.test.jsx` test_author коммитится чекпоинтом, попадает в перечень на выходе из `tests_writing`, сверяется на переходе и признаётся гейтом зон своим.

        Сценарий: компонент `pult-vitest` с шаблоном; задача входит в
        `tests_writing` переходом гейта SPEC (опора честного FAIL_TO_PASS,
        SPEC 01M5AQH8M2DKBV30NBY86J34A7), и отчёт базы на выходе несёт провал
        проверки тестов `AC-<n>`; test_author пишет
        планку и долгоживущий файл. (1) После чекпоинта шага файл есть в
        дереве головы кодовой ветки. (2) `advance` переводит задачу в
        `in_dev`, перечень лока несёт путь файла с SHA-256 его байтов на
        голове ветки. (3) Разработчик меняет этот файл коммитом —
        `advance` из `in_dev` отклонён «переход отклонён: перечень
        долгоживущих тестов» с «<путь> изменён». (4) Файл возвращён,
        разработчик добавляет свой долгоживущий
        `frontend/src/<каталог>/<имя>.<id>.test.jsx` и файл вне зон —
        отказ гейта зон называет только файл вне зон.

        Ловит мутацию: правило имени не знает `<dir>` — чекпоинт откатывает
        файл (его нет на голове), перечень пуст; перечень пишется по
        прежней паре — путь не в перечне; гейт зон сверяет префикс без
        шаблона — свой файл developer назван вне зон.
        """
        name = self.vitest_project()
        t = self.new_task(name)
        # Опора перечня «Зелёный с рождения»: SPEC.md в ссылке документов и
        # переход гейта SPEC; чекпоинт уносит SPEC.md из каталога документов
        # — на старте шага роли пульт материализует его снова.
        store.update_task(self.conn, t.id, state="spec_gate")
        checkpoint.commit_step_artifacts(self.conn, t.id, "analyst")
        store.set_state(self.conn, t.id, "tests_writing", "operator",
                        expected_state="spec_gate",
                        detail=transition_gates.SPEC_GATE_PASSED_DETAIL)
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(spec_text(t.id, (1,)), encoding="utf-8")
        self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx()})
        rel = f"frontend/src/components/button.{t.low}.test.jsx"
        text = self.long_jsx()
        self.write_code(t, rel, text)
        checkpoint.commit_step_artifacts(self.conn, t.id, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, t.id, "test_author")
        self.assertIn(rel, self.branch_files(t), self.note("файл не закоммичен"))

        def failing_base(argv, *args, **kwargs):
            # Отчёт базы: тесты `AC-<n>` переданных раннеру файлов падают
            # провалом проверки (`AssertionError`).
            proc = self.spy_popen(argv, *args, **kwargs)
            parts = [str(a) for a in argv] if isinstance(argv, (list, tuple)) \
                else []
            path = (arg_value(parts, "--outputFile")
                    if parts[:1] == [VITEST_BIN] else None)
            if path:
                cwd = Path(str(kwargs.get("cwd") or os.getcwd()))
                tests = []
                for part in parts[1:]:
                    file = Path(part) if os.path.isabs(part) else cwd / part
                    if not (file.is_file() and file.name.endswith(".test.jsx")):
                        continue
                    tests += [{"file": os.path.relpath(file, cwd),
                               "name": m.group(1), "state": "fail",
                               "mode": "run", "fails": False, "retry_count": 0,
                               "error_name": "AssertionError", "timeout": False,
                               "hook": None, "duration_ms": 5}
                              for m in re.finditer(r"\bit\('(AC-\d+: [^']*)'",
                                                   file.read_text(encoding="utf-8"))]
                Path(path).write_text(json.dumps({"tests": tests}),
                                      encoding="utf-8")
            return proc

        before = len(store.task_steps(self.conn, t.id))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), \
                mock.patch.object(subprocess, "Popen", failing_base):
            try:
                fsm.cmd_advance(t.id)
            except SystemExit as exc:
                buf.write(f"\nSystemExit: {exc.code}")
        row = store.get_task(self.conn, t.id)
        rows = [(r["action"], r["detail"])
                for r in store.task_steps(self.conn, t.id)[before:]]
        self.assertEqual(row["state"], "in_dev",
                         self.note(f"{rows}\n{buf.getvalue()}"))
        digests, reason = acceptance_gates.long_lived_manifest(t.id, row, name)
        self.assertEqual(reason, "", self.note(reason))
        self.assertEqual(digests, {rel: hashlib.sha256(
            text.encode("utf-8")).hexdigest()}, self.note(str(digests)))

        store.update_task(self.conn, t.id, zones="frontend/src/app.jsx")
        self.commit_code(t, {rel: text + "// правка\n"}, "правка теста")
        rows, output = self.developer_advance(t)
        found = self.details(rows, acceptance_gates.LONG_LIVED_MANIFEST_ACTION)
        self.assertTrue(found and f"{rel} изменён" in found[-1],
                        self.note(f"{[(r['action'], r['detail']) for r in rows]}"
                                  f"\n{output}"))

        own = f"frontend/src/{self.word()}/dev_{self.word()}.{t.low}.test.jsx"
        outside = f"other{self.word()}/x.txt"
        self.commit_code(t, {rel: text, own: self.long_jsx(),
                             outside: "вне зон\n",
                             "frontend/src/app.jsx": "export const app = 2;\n"},
                         "код разработчика")
        rows, output = self.developer_advance(t)
        zones = self.details(rows, "переход отклонён: гейт зон")
        self.assertTrue(zones, self.note(
            f"{[(r['action'], r['detail']) for r in rows]}\n{output}"))
        self.assertIn(outside, zones[-1], self.note(zones[-1]))
        self.assertNotIn(own, zones[-1], self.note(zones[-1]))
        self.assertNotIn(rel, zones[-1], self.note(zones[-1]))


# ---------------------------------------------------------------- AC-11

AMEND_REFUSAL = ("amend-tests для файлов планки с меткой AC-<n>: — до G3б не "
                 "исполняется; правка планки — reject на гейте")


class Ac11AmendLabelledRefusalTest(LabelledSandbox):

    def locked_task(self) -> tuple:
        """(задача, файлы планки, путь и текст долгоживущего файла) задачи
        `in_dev` с локом планки (`.test.jsx` с меткой и `.md`) и перечнем
        закоммиченного долгоживущего файла с меткой."""
        name = self.vitest_project()
        t = self.new_task(name, state="in_dev")
        rel = self.labelled_rel(t)
        text = self.long_jsx()
        self.write_code(t, rel, text)
        self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", "долгоживущий файл")
        digest = hashlib.sha256((t.wt / rel).read_bytes()).hexdigest()
        plank = {f"ac{self.word()}.test.jsx": self.plank_jsx(),
                 f"n{self.word()}.md": "заметка\n",
                 guard.LONG_LIVED_MANIFEST_NAME:
                     guard.render_long_lived_manifest({rel: digest})}
        self.write_plank(t, plank)
        checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        head = self.docs_head(t)
        self.assertTrue(head, self.note("ссылки документов нет"))
        store.update_task(self.conn, t.id, tests_locked_sha=head)
        store.record_fixation(self.conn, t.id)
        return t, plank, rel, text

    def docs_head(self, t) -> str:
        return self.git("-C", str(self.clones[t.target]), "for-each-ref",
                        "--format=%(objectname)",
                        "refs/artifacts/" + t.id).strip()

    def state_of(self, t) -> tuple:
        row = store.get_task(self.conn, t.id)
        code = self.git("-C", str(t.wt), "rev-parse", t.branch).strip()
        amends = [r for r in store.task_steps(self.conn, t.id)
                  if r["action"] == amend.AMEND_ACTION]
        return (self.docs_head(t), code, row["tests_locked_sha"], len(amends))

    def amend_text(self, t, from_branch: bool = False) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                amend.cmd_amend_tests(t.id, f"правка {self.seed}",
                                      from_branch=from_branch)
            except SystemExit as exc:
                buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def wt_plank(self, t, files: dict) -> None:
        """Правка Оператора: планка в рабочей копии кода целиком."""
        folder = t.wt / TASKS_DIR / t.id / PLANK_DIR
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (folder / name).write_text(text, encoding="utf-8")

    def assert_passed(self, t, text: str, before: tuple) -> tuple:
        """Проход (SPEC 01M5GXZK2WTZ89AXQ7QY2RJD9R, AC-21): вывод без отказа
        G3б и без «amend-tests: отказ», `tests_locked_sha` сдвинут и равен
        голове ветки документов, записей «правка планки» на одну больше."""
        after = self.state_of(t)
        context = self.note(f"{text}\nдо {before}\nпосле {after}")
        self.assertNotIn(AMEND_REFUSAL, text, context)
        self.assertNotIn("amend-tests: отказ", text, context)
        self.assertNotEqual(after[2], before[2], context)
        self.assertEqual(after[2], after[0], context)
        self.assertEqual(after[3], before[3] + 1, context)
        return after

    def last_amend_detail(self, t) -> str:
        return [r["detail"] or "" for r in store.task_steps(self.conn, t.id)
                if r["action"] == amend.AMEND_ACTION][-1]

    def test_ac11_worktree_mode_refuses_labelled_files(self):
        """Рабочая копия: правка `.test.jsx` планки, его удаление, правка только общего файла при лежащем `.test.jsx` и правка долгоживущего файла с меткой — проход проверками файлов с меткой, лок сдвинут (SPEC 01M5GXZK2WTZ89AXQ7QY2RJD9R, AC-21).

        Сценарий: задача `in_dev` с локом. Случаи правки Оператора в
        рабочей копии: (а) изменён `.test.jsx` планки; (б) `.test.jsx`
        удалён из планки (критерий держит долгоживущий файл); (в) изменён
        только `.md` планки, `.test.jsx` без изменений; (г) изменён
        долгоживущий файл с меткой кодовой ветки. В каждом случае вывод без
        отказа G3б и без «amend-tests: отказ», `tests_locked_sha` сдвинут
        на голову ветки документов, записей «правка планки» на одну
        больше. (а), (в) — голова кодовой ветки прежняя; (б) — деталь
        записи несёт «удалены:» с путём `.test.jsx`, в дереве нового лока
        файла нет; (г) — голова кодовой ветки сдвинута коммитом правки,
        перечень нового лока несёт сумму правленого файла.

        Ловит мутацию: отказ G3б оставлен — ни один случай не проходит, лок
        не сдвинут; удаление `.test.jsx` не переносится коммитом правки —
        файл остаётся в дереве нового лока; долгоживущий файл с меткой
        проверяется прежним путём Python — случай (г) отказывает; перечень
        нового лока считается по прежней голове кодовой ветки — сумма
        старого текста.
        """
        def modified(plank):
            out = dict(plank)
            jsx = next(n for n in plank if n.endswith(".test.jsx"))
            out[jsx] = plank[jsx] + "// правка\n"
            return out

        def removed(plank):
            return {n: v for n, v in plank.items() if not n.endswith(".test.jsx")}

        def shared(plank):
            out = dict(plank)
            md = next(n for n in plank if n.endswith(".md"))
            out[md] = plank[md] + "ещё\n"
            return out

        for label, change in (("правка .test.jsx", modified),
                              ("удаление .test.jsx", removed),
                              ("только общий файл", shared),
                              ("долгоживущий с меткой", None)):
            with self.subTest(case=label, seed=self.seed):
                t, plank, rel, text = self.locked_task()
                before = self.state_of(t)
                jsx = next(n for n in plank if n.endswith(".test.jsx"))
                edited = text + "// правка\n"
                if change is None:
                    self.write_code(t, rel, edited)
                else:
                    self.wt_plank(t, change(plank))
                    if label == "удаление .test.jsx":
                        (t.wt / TASKS_DIR / t.id / PLANK_DIR / jsx).unlink(
                            missing_ok=True)
                out = self.amend_text(t)
                after = self.assert_passed(t, out, before)
                context = self.note(f"{label}:\n{out}")
                if change is None:
                    self.assertNotEqual(after[1], before[1], context)
                    digests, reason = acceptance_gates.long_lived_manifest(
                        t.id, store.get_task(self.conn, t.id), t.target)
                    self.assertEqual(reason, "", context)
                    self.assertEqual(
                        digests.get(rel),
                        hashlib.sha256(edited.encode("utf-8")).hexdigest(),
                        self.note(f"перечень: {digests}"))
                else:
                    self.assertEqual(after[1], before[1], context)
                if label == "удаление .test.jsx":
                    detail = self.last_amend_detail(t)
                    self.assertIn("удалены:", detail, context)
                    self.assertIn(jsx, detail.split("удалены:", 1)[1], context)
                    tree = self.git("-C", str(self.clones[t.target]), "ls-tree",
                                    "-r", "--name-only", after[2])
                    self.assertNotIn(f"{PLANK_DIR}/{jsx}", tree, context)

    def test_ac11_from_branch_mode_refuses_labelled_files(self):
        """`--from-branch`: `.test.jsx` с меткой в правке ветки документов или на её голове — проход проверками файлов с меткой, лок сдвинут на голову ветки документов (SPEC 01M5GXZK2WTZ89AXQ7QY2RJD9R, AC-21).

        Сценарий: задача `in_dev` с локом; поверх лока в ветку документов
        записан коммит: (а) с изменённым `.test.jsx`; (б) с изменённым
        только `.md` (`.test.jsx` лежит на голове). `amend-tests
        --from-branch` — вывод без отказа G3б и без «amend-tests: отказ»;
        `tests_locked_sha` равен голове ветки документов после записанного
        коммита; записей «правка планки» на одну больше; голова кодовой
        ветки прежняя.

        Ловит мутацию: отказ G3б оставлен в `--from-branch` — лок не
        сдвинут; проверки файлов с меткой отказывают годной правке
        (строка группы `//` не читается) — «amend-tests: отказ».
        """
        for label, pick in (("правка .test.jsx", ".test.jsx"),
                            ("только общий файл", ".md")):
            with self.subTest(case=label, seed=self.seed):
                t, plank, _rel, _text = self.locked_task()
                name = next(n for n in plank if n.endswith(pick))
                locked = self.docs_head(t)
                self.write_plank(t, {name: plank[name] + "// правка\n"})
                checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
                self.assertNotEqual(self.docs_head(t), locked,
                                    self.note("правка не легла в ветку документов"))
                before = self.state_of(t)
                out = self.amend_text(t, from_branch=True)
                after = self.assert_passed(t, out, before)
                self.assertEqual(after[1], before[1], self.note(f"{label}:\n{out}"))


# ---------------------------------------------------------------- AC-12

class Ac12PlankRunLongLivedTest(LabelledSandbox):

    def test_ac12_plank_run_recognizes_labelled_long_lived_path(self):
        """`plank-run` по пути `frontend/src/components/button.<id>.test.jsx` признаёт его долгоживущим файлом задачи.

        Сценарий: задача `tests_writing` проекта с шаблоном и черновиком
        планки. Файла в рабочей копии нет — отказ «файла <путь> нет в
        рабочей копии кода» (а не «нет в планке»). Файл есть — вывод несёт
        «долгоживущий файл <путь>» и не несёт «нет в планке»; Vitest
        подменён шпионом, Node не запускается.

        Ловит мутацию: `plank-run` признаёт долгоживущий путь прежним
        правилом без `<dir>` — путь ищется в планке, отказ «нет в планке».
        """
        name = self.vitest_project()
        t = self.new_task(name)
        self.write_plank(t, {f"ac{self.word()}.test.jsx": self.plank_jsx()})
        rel = f"frontend/src/components/button.{t.low}.test.jsx"
        for present in (False, True):
            with self.subTest(present=present, seed=self.seed):
                if present:
                    self.write_code(t, rel, self.long_jsx())
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf), \
                        contextlib.redirect_stderr(buf):
                    try:
                        plank_run.cmd_plank_run(t.id, rel)
                    except SystemExit as exc:
                        buf.write(f"\n{exc.code}")
                output = buf.getvalue()
                self.assertNotIn("нет в планке", output, self.note(output))
                if present:
                    self.assertIn(f"долгоживущий файл {rel}", output,
                                  self.note(output))
                else:
                    self.assertIn(f"файла {rel} нет в рабочей копии кода",
                                  output, self.note(output))


if __name__ == "__main__":
    unittest.main()
