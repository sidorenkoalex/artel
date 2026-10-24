"""Гейт неослабления по исходам G3б-2: прежние версии тестов на коде ветки, заменяемые тесты, строгий режим, исключения в коде, доказательство на мерже.

Группа: долгоживущий
Красен до реализации: гейт исходов сравнивает только полные наборы базы и головы — третьей выписки головы с прежними версиями изменённых файлов `tests`/`test_support` нет (нет прогонов на ней, нет строки «прежние версии: …», нет находок «прежняя версия красная/нестабильна на коде ветки»), утверждённые замены гейт не читает (нет находок о заменах и строки «заменён по SPEC»), строгого режима и находок «исключение в коде» нет, сбой `diff --name-status`/`diff -M -U0` не отказывает, мандат на путь файла кода вне `weakening_scope` `answer` отклоняет; зелены и на базе ветки методы, держащие поведение без новых находок: AC-6 (без находок прежних версий старшая находка — единственная), AC-9 (а)/(в) и AC-10 (C пуст — третьей выписки нет), второй метод AC-22 (вне границы — прежний отказ `answer`), первый подслучай AC-25 (только «сломан правкой») и AC-30 (`test_profile` без гейта).

Стенд — песочница гейта исходов G3а-1а и её надстройка гейта мержа
(`tests.test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.MergeOutcomeSandbox`
поверх `tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.OutcomeGateSandbox`):
настоящий git, учебный внешний проект с единственным компонентом
`junit-xml` на поддельном `pytest` (`python-ast` по умолчанию) либо
`pult-vitest` без Node (строгий режим), раннер подменён шпионом
`subprocess.Popen`, исход теста задаётся сценарием по стороне прогона.

Сторона «прежние версии» (`OLD`): дерево прогона — выписка головы
(`app.py` с меткой головы) в каталоге `scratch` гейта (рядом лежит маркер
владельца `liveness.GATE_OWNER_MARKER`), имя каталога выписки — не `base`
и не `head`. Исход теста на этой стороне — последовательность сценария
`cases[(путь, имя)][OLD]` (по умолчанию `passed`); «спасатель» `rescue` —
пути, при наличии которых в дереве прогона прежняя версия зелёная
(подмена сломанной функции добавленным `conftest.py`). Шпион
`subprocess.run` записывает каждую `worktree add` из кадров модуля гейта
(путь и наличие маркера владельца рядом в момент вызова) и, по правилу
сценария `git_fail`, отвечает отказом git.

Утверждённая замена — запись журнала `mandate.REPLACED_TESTS_ACTION` с
пунктом `guard.ReplacedTest(...).line` (та же форма, что пишет `approve`
гейта SPEC). Мандат Оператора — `answer.cmd_answer` с маркером и матрицей
неослабления.

Имена проектов, файлов, тестов, позиции строк и выбор исходов — из
`random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
поля профиля и `layers_of`, мандат на путь в границе, третья выписка с
восстановлением C и удалением файлов `A`, перепрогоны прежних версий,
находки замен, строгого режима и исключений в коде, порядок строк записи,
отпечаток с элементами замен и `_proven` по новым видам — все методы файла
зелёные; мутация «находка прежней версии при находке прежнего вида» красит
AC-6 и AC-17.
"""
import contextlib
import hashlib
import io
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

from orchestrator import answer, liveness, project_profile, store
from orchestrator.advance_gates import mandate
from scripts import guard
from tests.sandbox import make_project_repo
from tests.outcome_gate_sandbox import (
    ENTRY_HEAD, MATRIX_HEADERS, OutcomeGateSandbox, flow, js_source,
    py_source)
from tests.test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate import (
    MergeOutcomeSandbox)

GATE_MODULE = "orchestrator.advance_gates.outcome_integrity"
OLD = "old"
SIDES = ("base", "head")

OUTCOME_ACTION = "переход отклонён: гейт неослабления по исходам"
BROKEN_ACTION = "переход отклонён: гейт неослабления по исходам — сломан правкой"
PREPARE_ACTION = "переход отклонён: гейт неослабления по исходам — подготовка"
PASSED_ACTION = "гейт неослабления по исходам пройден"
MANDATE_MARKER = "Ослабление тестов разрешено:"
ID_MARKER = "Ослабление теста по идентификатору разрешено:"

GONE = "исчез"
SKIPPED = "стал пропуском"
PRIOR_RED = "прежняя версия красная на коде ветки"
PRIOR_UNSTABLE = "прежняя версия нестабильна на коде ветки"
REPL_MISSING = "заменяемый тест не найден в отчёте базы"
REPL_NOT_GREEN = "заменяемый тест не зелёный на базе"
REPL_NEEDLESS = "замена не нужна: прежняя версия зелёная на коде ветки"
STRICT = "строгий режим — правка существующего файла"
CODE_EXC = "исключение в коде"
FLAKY = "нестабилен и на базе"
REPLACED = "заменён по SPEC"
COVERED_BY_REPLACEMENT = " — покрыто мандатом замена SPEC → AC-{n}"
PRIOR_LINE = re.compile(r"^прежние версии: файлов (\d+); прогонов (\d+)$")
PROOF_LINE = re.compile(
    r"^голова ([0-9a-f]{40}); база ([0-9a-f]{40}); ключ (\S+); мандат (\S+)$")
COUNTS_MARK = "тестов базы"
# Подстроки исключений в коде — перечень требования 7 SPEC.
TOKENS = ("v8 ignore", "istanbul ignore", "c8 ignore", "eslint-disable",
          "import.meta.env.MODE", "process.env.VITEST", "NODE_ENV")
# Метка файла тестов, который на этой стороне даёт только запись ошибки
# уровня файла (сбор модуля).
FILE_ERROR_MARK = "# сбор-ошибка сценария"
CLAIM = "Ловит мутацию: фикстура сценария — исход теста другой."


class Moved(NamedTuple):
    """Значение правки сценария: `git mv <source> <путь>` без правки строк."""
    source: str


class Link(NamedTuple):
    """Значение правки сценария: путь становится символьной ссылкой."""
    target: str


class PriorSandbox(MergeOutcomeSandbox):
    """Песочница G3а-1а и гейта мержа плюс сторона прежних версий, учёт
    `worktree add` гейта, проекты с полями `tests`/`test_support`/`layers`/
    `paths`, утверждённые замены и мандаты Оператора."""

    def setUp(self):
        # Шпионы песочницы ставятся в её `setUp` и сразу зовутся.
        self.gate_adds: list = []
        self.rescue: tuple = ()
        self.watch_old: tuple = ()
        self.run_root = None
        super().setUp()

    # --- шпионы ---------------------------------------------------------

    def in_outcome_gate(self) -> bool:
        frame = sys._getframe(1)
        while frame is not None:
            if frame.f_globals.get("__name__") == GATE_MODULE:
                return True
            frame = frame.f_back
        return False

    @staticmethod
    def add_path(args) -> Path | None:
        """Путь выписки аргументов `worktree add`; `None` — не она."""
        parts = [str(a) for a in args]
        if "worktree" not in parts or "add" not in parts:
            return None
        rest = [p for p in parts[parts.index("add") + 1:] if not p.startswith("-")]
        return Path(rest[0]) if rest else None

    def spy_run(self, argv, *args, **kwargs):
        if isinstance(argv, (list, tuple)) and argv and argv[0] == "git":
            path = self.add_path(argv[1:])
            if path is not None and self.in_outcome_gate():
                self.gate_adds.append({
                    "path": path,
                    "marker": (path.parent / liveness.GATE_OWNER_MARKER).exists()})
        return super().spy_run(argv, *args, **kwargs)

    @staticmethod
    def tree_root(cwd: Path) -> Path:
        for folder in (cwd, *cwd.parents):
            if (folder / ".git").exists():
                return folder
        return cwd

    def side_of(self, cwd: Path) -> str:
        side = OutcomeGateSandbox.side_of(cwd)
        if side != "head":
            return side
        root = self.tree_root(Path(cwd))
        if root.name not in SIDES and \
                (root.parent / liveness.GATE_OWNER_MARKER).exists():
            return OLD
        return side

    def runner_run(self, kind, parts, cwd, args, kwargs):
        self.run_root = self.tree_root(Path(cwd))
        proc = super().runner_run(kind, parts, cwd, args, kwargs)
        self.runs[-1]["seen"] = {rel: (self.run_root / rel).exists()
                                 for rel in self.watch_old}
        return proc

    def outcome_of(self, side: str, rel: str, name: str) -> str:
        if side == OLD and self.rescue and self.run_root is not None and any(
                (self.run_root / p).exists() for p in self.rescue):
            return "passed"
        return super().outcome_of(side, rel, name)

    def junit_report(self, run: dict, files: list) -> tuple:
        broken = [rel for rel, text in files if FILE_ERROR_MARK in text]
        text, red = super().junit_report(
            run, [(rel, body) for rel, body in files if FILE_ERROR_MARK not in body])
        if not broken:
            return text, red
        cases = "".join(
            f'<testcase file="{rel}" classname="" name="{rel[:-3].replace("/", ".")}"'
            f' time="0.01"><error message="collection failure">ImportError: '
            f'сбор сценария</error></testcase>' for rel in broken)
        return text.replace("</testsuite>", cases + "</testsuite>", 1), True

    def run_advance(self, tid: str) -> tuple:
        self.gate_adds.clear()
        return super().run_advance(tid)

    def approve(self, t) -> tuple:
        self.gate_adds.clear()
        return super().approve(t)

    # --- проекты --------------------------------------------------------

    def entry(self, fields: dict) -> tuple:
        name, comp = f"j{self.word()}", f"c{self.word()}"
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 f"      {comp}:\n"]
        for key, value in fields.items():
            lines.append(f"        {key}: {value}\n")
        self.append_entry("".join(lines))
        return name, comp

    def project(self, kind: str, fields: dict, files: dict) -> SimpleNamespace:
        name, comp = self.entry(fields)
        clone = make_project_repo(name)
        self.commit_project(clone, files)
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comp, layout=fields["plank_layout"],
                               kind=kind, clone=clone)

    def junit(self, tests: dict, extra: dict | None = None,
              files: dict | None = None) -> SimpleNamespace:
        """Компонент `junit-xml` на поддельном `pytest` (действующие слои —
        `python-ast`); `tests` — {путь: [имена]} тестов базы; `extra` — поля
        записи сверх прежних (значения — текстом YAML); `files` — прочие
        файлы базы."""
        fields = {"command": flow([str(self.pytest_cmd)]),
                  "report": "junit-xml",
                  "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": flow(["tests/**"]),
                  "mutation_claim_scope": flow(["tests/**"]),
                  "failure_errors": flow(["AssertionError"]),
                  "plank_layout": f".pj{self.word(5)}/<id>"}
        fields.update(extra or {})
        base = {"app.py": "APP = 'base'\n", **(files or {})}
        base.update({rel: py_source(names) for rel, names in tests.items()})
        return self.project("junit", fields, base)

    def vitest(self, tests: dict, extra: dict | None = None,
               files: dict | None = None) -> SimpleNamespace:
        """Компонент `pult-vitest` (строгий режим: слоёв нет); `tests` —
        {путь: [имена]} тестов базы."""
        fields = {"command": flow(self.vitest_argv()),
                  "report": "pult-vitest",
                  "report_args": flow(["--reporter=default",
                                       "--reporter={pult_reporter}",
                                       "--outputFile={path}"]),
                  "install": flow([str(self.installer)]),
                  "tests": flow(["frontend/src/**/*.test.jsx"]),
                  "plank_layout": f"frontend/src/.pv{self.word(5)}/<id>",
                  "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx",
                  "weakening_scope": flow(["frontend/src/**"]),
                  "mutation_claim_scope": flow(["frontend/claims/**"]),
                  "failure_errors": flow(["AssertionError"]),
                  "select": flow([f"--sel{self.word()}", "{tests}"])}
        fields.update(extra or {})
        name, comp = self.entry(fields)
        self.append_entry("        tools:\n"
                          f'          vitest: "{self.vitest_version}"\n')
        clone = make_project_repo(name)
        base = {"package.json": '{"name": "web"}\n',
                "vitest.config.js": "export default {}\n",
                "package-lock.json": '{"lockfileVersion": 3}\n',
                "app.py": "APP = 'base'\n", **(files or {})}
        base.update({rel: js_source(names) for rel, names in tests.items()})
        self.commit_project(clone, base)
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comp, layout=fields["plank_layout"],
                               kind="vitest", clone=clone)

    @staticmethod
    def vitest_argv() -> tuple:
        return project_profile.VITEST_BASE_ARGV

    def commit_code(self, t, changes: dict, message: str = "код разработчика"):
        """Коммит правки кодовой ветки: значение — текст, байты, `None`
        (удалить), `Moved` (переименовать) или `Link` (символьная ссылка)."""
        files = {"app.py": f"APP = 'head-{self.word()}'\n", **changes}
        # Зоны — все пути веток задачи: повторный шаг не сужает их.
        zones = set(getattr(t, "zones", ())) | set(files)
        t.zones = zones
        for rel, value in files.items():
            path = t.wt / rel
            if value is None:
                self.git("-C", str(t.wt), "rm", "-q", "--", rel)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, Moved):
                zones.add(value.source)
                self.git("-C", str(t.wt), "mv", value.source, rel)
                continue
            if isinstance(value, Link):
                if path.exists() or path.is_symlink():
                    path.unlink()
                os.symlink(value.target, path)
            elif isinstance(value, bytes):
                path.write_bytes(value)
            else:
                path.write_text(value, encoding="utf-8")
            self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", message)
        store.update_task(self.conn, t.id, zones=", ".join(sorted(zones)))

    # --- замены и мандаты -----------------------------------------------

    def approve_replacements(self, t, items: dict) -> None:
        """Запись утверждённых замен `{идентификатор: номер критерия}`."""
        detail = "\n".join(
            guard.ReplacedTest(cid, n, f"замена сценария {self.word()}").line
            for cid, n in items.items())
        store.journal(self.conn, t.id, "operator",
                      mandate.REPLACED_TESTS_ACTION, detail)

    def operator_answer(self, t, paths=(), ids=(), covered="tests/sandbox.py:1"):
        """ANSWER Оператора (`answer.cmd_answer`) с мандатом на `paths`
        (прежний маркер) и `ids` (по строке маркера по идентификатору):
        (принят ли, вывод)."""
        head = []
        if paths:
            head.append(f"{MANDATE_MARKER} {', '.join(paths)}")
        head += [f"{ID_MARKER} {cid}" for cid in ids]
        row = (", ".join(f"`{e}`" for e in (*paths, *ids)),
               "фикстура теста — tests/sandbox.py:1", "да", covered, "ок")
        text = ("\n\n".join(head) + "\n\n"
                "Независимая проверка: матрица подтверждена\n\n"
                f"Основание: решение Оператора ({self.seed}).\n\n"
                "## Матрица неослабления\n\n"
                "| " + " | ".join(MATRIX_HEADERS) + " |\n"
                + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
                + "| " + " | ".join(row) + " |\n")
        path = self.root / ".artel" / f"answer-{self.word()}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        code = None
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                answer.cmd_answer(t.id, str(path))
            except SystemExit as exc:
                code = exc.code
        return code in (None, 0), f"код {code}: {buf.getvalue()}"

    def grant(self, t, paths=(), ids=(), covered="tests/sandbox.py:1") -> None:
        ok, output = self.operator_answer(t, paths, ids, covered)
        self.assertTrue(ok, self.note(f"answer отказала: {output}"))

    # --- наблюдения -----------------------------------------------------

    def third_adds(self) -> list:
        return [a for a in self.gate_adds if a["path"].name not in SIDES]

    def old_runs(self) -> list:
        return [r for r in self.runs if r["side"] == OLD and not r["plank"]]

    def old_files(self) -> set:
        return {rel for r in self.old_runs() for rel in r["files"]}

    def passed(self, rows: list, output: str) -> str:
        found = self.details(rows, PASSED_ACTION)
        self.assertTrue(found, f"записи «{PASSED_ACTION}» нет:\n"
                        + self.explain(rows, output))
        return found[-1]

    @staticmethod
    def starting(detail: str, prefix: str) -> list:
        return [line for line in detail.splitlines() if line.startswith(prefix)]

    def touch_py(self) -> str:
        return f"\n# правка {self.word()}\n"

    def touch_js(self) -> str:
        return f"\n// правка {self.word()}\n"

    def edited_py(self, names) -> str:
        return py_source(names) + self.touch_py()

    def edited_js(self, names) -> str:
        return js_source(names) + self.touch_js()


# ---------------------------------------------------------------- AC-3

class Ac3GreenPriorTest(PriorSandbox):

    def test_ac3_green_prior_version_passes_with_prior_line(self):
        """Изменённые файлы тестов, прежние версии которых зелёные на коде ветки, находок не дают: гейт пройден, запись несёт «прежние версии: файлов <n>; прогонов <m>».

        Сценарий: проект `junit-xml`, один или два (из `random`) файла
        тестов базы изменены веткой (тесты прежние, добавлена строка
        комментария), ещё один файл не тронут. На стороне прежних версий
        исход по умолчанию — `passed`. Отказа гейта исходов нет; в записи
        пройденного гейта ровно одна строка «прежние версии: …», `n` —
        число изменённых файлов, `m` — число прогонов на стороне прежних
        версий (не меньше одного); на этой стороне гонялись ровно
        изменённые файлы.

        Ловит мутацию: третья выписка не делается — прогонов на стороне
        прежних версий нет и строки нет; строка пишется без чисел или
        считает файлы набора C вместе с неизменённым файлом — `n` не тот;
        гоняется весь набор вместо файлов C — на стороне прежних версий
        гонялся и неизменённый файл.
        """
        count = self.rng.randint(1, 2)
        rels = [self.py_rel() for _ in range(count)]
        tests = {rel: [self.py_name(), self.py_name()] for rel in rels}
        tests[self.py_rel()] = [self.py_name()]
        project = self.junit(tests)
        t = self.task(project)
        rows, output = self.developer_advance(
            t, {rel: self.edited_py(tests[rel]) for rel in rels})
        self.no_gate_refusal(rows, output)
        detail = self.passed(rows, output)
        prior = [PRIOR_LINE.match(line) for line in detail.splitlines()]
        prior = [m for m in prior if m]
        self.assertEqual(len(prior), 1, self.explain(rows, output))
        files, runs = (int(x) for x in prior[0].groups())
        self.assertEqual(files, count, self.explain(rows, output))
        self.assertGreaterEqual(runs, 1, self.explain(rows, output))
        self.assertEqual(runs, len(self.old_runs()), self.explain(rows, output))
        self.assertEqual(self.old_files(), set(rels), self.explain(rows, output))


# ---------------------------------------------------------------- AC-10

class Ac10EmptyPriorSetTest(PriorSandbox):

    def test_ac10_empty_set_no_third_checkout(self):
        """Набор C пуст — третьей выписки нет: ни `worktree add` прежних версий, ни прогона, ни строки «прежние версии: …».

        Сценарий: проект `junit-xml`, ветка правит только код (`app.py`) и
        добавляет файл кода вне тестов. Гейт пройден; среди `worktree add`
        гейта нет выписки с каталогом, отличным от `base`/`head`; прогонов
        на стороне прежних версий нет; в записи пройденного гейта нет
        строки «прежние версии: …».

        Ловит мутацию: шаг прежних версий исполняется и при пустом C —
        третья `worktree add` и строка «прежние версии: файлов 0; …» в
        записи.
        """
        project = self.junit({self.py_rel(): [self.py_name()]})
        t = self.task(project)
        rows, output = self.developer_advance(
            t, {f"lib/{self.word()}.py": "VALUE = 1\n"})
        self.no_gate_refusal(rows, output)
        detail = self.passed(rows, output)
        self.assertEqual(self.third_adds(), [], self.explain(rows, output))
        self.assertEqual(self.old_runs(), [], self.explain(rows, output))
        self.assertFalse(any(PRIOR_LINE.match(line) or line.startswith("прежние версии")
                             for line in detail.splitlines()),
                         self.explain(rows, output))


# ---------------------------------------------------------------- AC-4

class Ac4PriorRedTest(PriorSandbox):

    def test_ac4_prior_red_thrice_refuses_outcome(self):
        """Прежняя версия изменённого теста трижды красная на коде ветки при зелёной базе — отказ «… по исходам» со строкой «прежняя версия красная на коде ветки: <идентификатор> — прежняя версия: …; база: …».

        Сценарий: проект `junit-xml`; тест базы `PASS_TO_PASS`, на голове
        зелёный, его файл изменён веткой (добавлен комментарий); на стороне
        прежних версий тест `failed` во всех прогонах, база зелёна во всех.
        Действие отказа — общее «переход отклонён: гейт неослабления по
        исходам»; ровно одна строка детали с идентификатором, начинается с
        «прежняя версия красная на коде ветки: <id> — прежняя версия: » и
        несёт «; база: ».

        Ловит мутацию: прежние версии не гоняются — переход в `verifying`;
        красная прежняя версия отнесена к «сломан правкой» — действие
        «… — сломан правкой»; исходы строки без «прежняя версия: » или
        без базы — строка другой формы.
        """
        rel, name, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit({rel: [name, other]})
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["passed"],
                                   OLD: ["failed"]}
        rows, output = self.developer_advance(t, {rel: self.edited_py([name, other])})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        cid = self.case_id(project, rel, name)
        lines = self.lines_with(detail, cid)
        self.assertEqual(len(lines), 1, self.explain(rows, output))
        self.assertTrue(lines[0].startswith(f"{PRIOR_RED}: {cid} — прежняя версия: "),
                        self.explain(rows, output))
        self.assertIn("; база: ", lines[0], self.explain(rows, output))


# ---------------------------------------------------------------- AC-5

class Ac5PriorUnstableTest(PriorSandbox):

    def test_ac5_prior_mixed_is_unstable_finding(self):
        """Прежняя версия красная и зелёная вперемешку на третьей выписке — находка «прежняя версия нестабильна на коде ветки» и общий отказ.

        Сценарий: проект `junit-xml`, файл теста изменён веткой; на
        стороне прежних версий первый прогон `failed`, перепрогоны — смесь
        `failed`/`passed` (порядок из `random`); база зелёна. Отказ «… по
        исходам», строка детали начинается с «прежняя версия нестабильна на
        коде ветки: <id> — прежняя версия: »; строки «прежняя версия
        красная …» по нему нет.

        Ловит мутацию: смесь исходов отнесена к «красной» — строка «прежняя
        версия красная на коде ветки»; перепрогонов на третьей выписке нет —
        один красный прогон даёт «красная».
        """
        rel, name, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit({rel: [name, other]})
        t = self.task(project)
        old = self.rng.choice((["failed", "passed", "failed"],
                               ["failed", "failed", "passed"],
                               ["failed", "passed", "passed"]))
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["passed"], OLD: old}
        rows, output = self.developer_advance(t, {rel: self.edited_py([name, other])})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        cid = self.case_id(project, rel, name)
        self.assertTrue(self.starting(detail, f"{PRIOR_UNSTABLE}: {cid} — прежняя версия: "),
                        self.explain(rows, output) + f"\nисходы: {old}")
        self.assertFalse(self.starting(detail, f"{PRIOR_RED}: {cid}"),
                         self.explain(rows, output))

    def test_ac5_red_base_rerun_is_flaky_line_not_finding(self):
        """Прежняя версия красная, база красна в одном из перепрогонов — не находка, а строка «нестабилен и на базе: <идентификатор>» в записи пройденного гейта.

        Сценарий: проект `junit-xml`, файл теста изменён веткой; прежняя
        версия `failed` во всех прогонах; база в полном прогоне зелёна, в
        одном из двух перепрогонов (из `random`) — `failed` или `error`.
        Отказа гейта исходов нет; запись пройденного гейта несёт строку
        «нестабилен и на базе: <id>» и не несёт строки находки прежней
        версии по нему.

        Ловит мутацию: база в перепрогонах прежних версий не гоняется либо
        её краснота не читается — отказ «прежняя версия красная на коде
        ветки»; строка о базе не пишется — её нет в записи.
        """
        rel, name, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit({rel: [name, other]})
        t = self.task(project)
        base = ["passed", "passed", "passed"]
        base[self.rng.choice((1, 2))] = self.rng.choice(("failed", "error"))
        self.cases[(rel, name)] = {"base": base, "head": ["passed"], OLD: ["failed"]}
        rows, output = self.developer_advance(t, {rel: self.edited_py([name, other])})
        self.no_gate_refusal(rows, output)
        detail = self.passed(rows, output)
        cid = self.case_id(project, rel, name)
        self.assertIn(f"{FLAKY}: {cid}", detail.splitlines(), self.explain(rows, output))
        self.assertFalse(self.starting(detail, f"{PRIOR_RED}: {cid}"),
                         self.explain(rows, output))


# ---------------------------------------------------------------- AC-6

class Ac6OneFindingPerIdTest(PriorSandbox):

    def test_ac6_old_kind_finding_wins_single_line(self):
        """Тест с находкой прежнего вида («стал пропуском»), прежняя версия которого красная на коде ветки, — в детали отказа ровно одна строка с его идентификатором, строка старшей находки.

        Сценарий: проект `junit-xml`, файл теста изменён веткой; тест базы
        зелёный, на голове `skipped`, прежняя версия `failed` во всех
        прогонах. Отказ «… по исходам»: строк с идентификатором — одна, она
        начинается с «стал пропуском: <id> — ».

        Ловит мутацию: находка прежней версии добавляется к находке
        прежнего вида — две строки с идентификатором.
        """
        rel, name, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit({rel: [name, other]})
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["skipped"],
                                   OLD: ["failed"]}
        rows, output = self.developer_advance(t, {rel: self.edited_py([name, other])})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        cid = self.case_id(project, rel, name)
        lines = self.lines_with(detail, cid)
        self.assertEqual(len(lines), 1, self.explain(rows, output))
        self.assertTrue(lines[0].startswith(f"{SKIPPED}: {cid} — "),
                        self.explain(rows, output))


# ---------------------------------------------------------------- AC-7

class Ac7RunScopeTest(PriorSandbox):

    def test_ac7_test_support_change_runs_full_suite(self):
        """Изменён только файл под маской `test_support` — на третьей выписке гоняется полный набор компонента (`fresh`).

        Сценарий: проект `junit-xml` с `test_support: [support/**]`; ветка
        правит только `support/<имя>.py`. Среди вызовов полного набора есть
        вызов на стороне прежних версий с `fresh=True`; гейт пройден.

        Ловит мутацию: путь `test_support` не входит в C — третьей выписки
        и полного набора на ней нет; при пути `test_support` гоняются
        только файлы C — полного набора на стороне прежних версий нет.
        """
        support = f"support/{self.word()}.py"
        project = self.junit({self.py_rel(): [self.py_name()]},
                             extra={"test_support": flow(["support/**"])},
                             files={support: "HELPER = 1\n"})
        t = self.task(project)
        rows, output = self.developer_advance(t, {support: "HELPER = 2\n"})
        self.no_gate_refusal(rows, output)
        self.passed(rows, output)
        self.assertTrue(any(c["side"] == OLD and c["fresh"] for c in self.suite_calls),
                        self.explain(rows, output))

    def test_ac7_tests_change_runs_only_changed_files(self):
        """Изменены только файлы `tests` — на третьей выписке гоняются ровно эти файлы, без полного набора.

        Сценарий: проект `junit-xml` с тремя файлами тестов; ветка правит
        два из них (выбор из `random`). На стороне прежних версий нет
        полного прогона и вызова полного набора, а объединение файлов
        прогонов — ровно два изменённых файла.

        Ловит мутацию: на третьей выписке всегда гоняется полный набор —
        полный прогон на стороне прежних версий; гоняются и неизменённые
        файлы отчёта базы — лишний файл.
        """
        tests = {self.py_rel(): [self.py_name()] for _ in range(3)}
        changed = self.rng.sample(sorted(tests), 2)
        project = self.junit(tests)
        t = self.task(project)
        rows, output = self.developer_advance(
            t, {rel: self.edited_py(tests[rel]) for rel in changed})
        self.no_gate_refusal(rows, output)
        self.assertTrue(self.old_runs(), self.explain(rows, output))
        self.assertFalse(any(r["full"] for r in self.old_runs()), self.explain(rows, output))
        self.assertFalse(any(c["side"] == OLD for c in self.suite_calls),
                         self.explain(rows, output))
        self.assertEqual(self.old_files(), set(changed), self.explain(rows, output))


# ---------------------------------------------------------------- AC-8

class Ac8RestoredPathsTest(PriorSandbox):

    def test_ac8_deleted_file_restored_and_judged(self):
        """Удалённый файл тестов на третьей выписке восстановлен, его тесты базы судятся.

        Сценарий: проект `junit-xml`, два файла тестов; ветка удаляет один
        (мандат Оператора на его путь — исчезновение законно). Гейт пройден;
        на стороне прежних версий гонялся удалённый файл, в записи — «прежние
        версии: файлов 1; …».

        Ловит мутацию: записи `D` выброшены из C — третьей выписки нет;
        удалённый путь не восстанавливается командой `git checkout <база>
        -- <пути>` — файла в прогоне нет.
        """
        gone, keep = self.py_rel(), self.py_rel()
        project = self.junit({gone: [self.py_name()], keep: [self.py_name()]})
        t = self.task(project)
        self.grant(t, paths=[gone])
        rows, output = self.developer_advance(t, {gone: None}, finished=True)
        self.no_gate_refusal(rows, output)
        detail = self.passed(rows, output)
        self.assertIn(gone, self.old_files(), self.explain(rows, output))
        prior = [PRIOR_LINE.match(line) for line in detail.splitlines()]
        self.assertEqual([m.group(1) for m in prior if m], ["1"], self.explain(rows, output))

    def test_ac8_renamed_file_old_path_restored_new_stays(self):
        """У переименованного файла тестов на третьей выписке восстановлен прежний путь, новый путь остаётся.

        Сценарий: проект `junit-xml`; ветка переименовывает файл тестов
        (`git mv` без правки строк — статус `R100`), мандат Оператора на оба
        пути. На стороне прежних версий гонялся прежний путь; в момент
        прогона в дереве третьей выписки есть и прежний, и новый путь.

        Ловит мутацию: у `R` берётся новый путь — прежний не восстановлен
        и не гонялся; новый путь удалён с третьей выписки — его нет в
        дереве.
        """
        old_rel, new_rel = self.py_rel(), self.py_rel()
        project = self.junit({old_rel: [self.py_name()], self.py_rel(): [self.py_name()]})
        t = self.task(project)
        self.grant(t, paths=[old_rel, new_rel])
        self.watch_old = (old_rel, new_rel)
        rows, output = self.developer_advance(t, {new_rel: Moved(old_rel)}, finished=True)
        self.no_gate_refusal(rows, output)
        runs = [r for r in self.old_runs() if old_rel in r["files"]]
        self.assertTrue(runs, self.explain(rows, output))
        self.assertTrue(all(r["seen"][old_rel] and r["seen"][new_rel] for r in runs),
                        self.explain(rows, output) + f"\n{[r['seen'] for r in runs]}")

    def test_ac8_type_changed_file_in_set(self):
        """Запись со статусом `T` (файл тестов стал символьной ссылкой) входит в C — прежняя версия гоняется.

        Сценарий: проект `junit-xml`; ветка заменяет файл тестов
        символьной ссылкой на копию его текста под `tests/data/`; мандат
        Оператора на путь. На стороне прежних версий гонялся этот путь.

        Ловит мутацию: в C берутся только статусы `M`/`D`/`R` — запись `T`
        выпала, третьей выписки нет.
        """
        rel, name = self.py_rel(), self.py_name()
        project = self.junit({rel: [name], self.py_rel(): [self.py_name()]})
        t = self.task(project)
        data = f"tests/data/{self.word()}.txt"
        self.grant(t, paths=[rel])
        rows, output = self.developer_advance(
            t, {data: py_source([name]), rel: Link(os.path.relpath(data, "tests"))},
            finished=True)
        self.no_gate_refusal(rows, output)
        self.assertIn(rel, self.old_files(), self.explain(rows, output))


# ---------------------------------------------------------------- AC-9

class Ac9NoTestsFieldTest(PriorSandbox):

    def test_ac9_code_only_and_new_file_no_third_checkout(self):
        """Компонент без поля `tests`: ветка правит только код либо добавляет новый файл тестов (`A`) — третьей выписки нет.

        Сценарий (подслучай — свежая задача): (а) правка только кода; (в)
        новый файл тестов `tests/test_<имя>.py` с зелёным тестом. В обоих —
        гейт пройден, среди `worktree add` гейта нет третьей выписки,
        прогонов на стороне прежних версий нет.

        Ловит мутацию: у компонента без `tests` C — все файлы отчёта базы
        (буквальное «все файлы») — третья выписка при правке кода; файлы
        `A` входят в C — третья выписка при новом файле.
        """
        for label in ("код", "новый файл"):
            with self.subTest(case=label, seed=self.seed):
                project = self.junit({self.py_rel(): [self.py_name()],
                                      self.py_rel(): [self.py_name()]})
                t = self.task(project)
                changes = ({f"lib/{self.word()}.py": "VALUE = 2\n"} if label == "код"
                           else {self.py_rel(): py_source([self.py_name()])})
                rows, output = self.developer_advance(t, changes)
                self.no_gate_refusal(rows, output)
                self.passed(rows, output)
                self.assertEqual(self.third_adds(), [], self.explain(rows, output))
                self.assertEqual(self.old_runs(), [], self.explain(rows, output))

    def test_ac9_changed_base_file_and_file_level_record_in_set(self):
        """Компонент без поля `tests`: изменённый файл отчёта базы — единственный файл прогона прежних версий; файл с одной лишь записью ошибки уровня файла входит в C.

        Сценарий (подслучай — свежая задача): (б) три файла тестов базы,
        ветка правит один (из `random`) — на стороне прежних версий
        гоняется только он; (г) файл базы, у которого в отчёте базы только
        запись ошибки сбора модуля, ветка исправляет — он гоняется на
        стороне прежних версий.

        Ловит мутацию: C — все файлы отчёта базы — на третьей выписке
        гоняются и неизменённые файлы; файлы записей ошибок уровня файла
        не входят в перечень отчёта базы — (г) без третьей выписки.
        """
        with self.subTest(case="правка файла", seed=self.seed):
            tests = {self.py_rel(): [self.py_name()] for _ in range(3)}
            rel = self.rng.choice(sorted(tests))
            project = self.junit(tests)
            t = self.task(project)
            rows, output = self.developer_advance(t, {rel: self.edited_py(tests[rel])})
            self.no_gate_refusal(rows, output)
            self.assertEqual(self.old_files(), {rel}, self.explain(rows, output))
        with self.subTest(case="ошибка уровня файла", seed=self.seed):
            rel, names = self.py_rel(), [self.py_name()]
            project = self.junit({self.py_rel(): [self.py_name()]},
                                 files={rel: FILE_ERROR_MARK + "\n" + py_source(names)})
            t = self.task(project)
            rows, output = self.developer_advance(t, {rel: py_source(names)})
            self.no_gate_refusal(rows, output)
            self.assertIn(rel, self.old_files(), self.explain(rows, output))


# --------------------------------------------------------------- AC-11

class Ac11PrepareTest(PriorSandbox):

    def test_ac11_third_checkout_failure_refuses_prepare(self):
        """Сбой `worktree add` третьей выписки — отказ подготовки, переход не совершён, каталога выписки нет.

        Сценарий: проект `junit-xml`, файл тестов изменён веткой; git
        отказывает `worktree add` гейта с каталогом, отличным от
        `base`/`head`. Отказ «… — подготовка», задача в `in_dev`, после
        гейта пути третьей выписки нет.

        Ловит мутацию: сбой выписки проглочен как пустой C — гейт пройден,
        задача в `verifying`.
        """
        rel, names = self.py_rel(), [self.py_name()]
        project = self.junit({rel: names})
        t = self.task(project)

        def third(args):
            path = self.add_path(args)
            return path is not None and path.name not in SIDES
        self.git_fail = third
        rows, output = self.developer_advance(t, {rel: self.edited_py(names)})
        self.git_fail = None
        self.refusal(rows, output, PREPARE_ACTION)
        self.assertTrue(self.third_adds(), self.explain(rows, output))
        for add in self.third_adds():
            self.assertFalse(add["path"].exists(), self.explain(rows, output))

    def test_ac11_third_run_failure_refuses_prepare(self):
        """Прогон на третьей выписке превысил предел — отказ подготовки, переход не совершён, выписка убрана.

        Сценарий: проект `junit-xml`, файл тестов изменён веткой; раннер на
        стороне прежних версий превышает предел времени. Отказ «… —
        подготовка», задача в `in_dev`, каталога третьей выписки после
        гейта нет.

        Ловит мутацию: таймаут прогона прежних версий считается красным
        исходом или пропуском — отказ иного действия либо проход; уборка
        третьей выписки не в `finally` — каталог остался.
        """
        rel, names = self.py_rel(), [self.py_name()]
        project = self.junit({rel: names})
        t = self.task(project)
        self.timeout_when = lambda run: run["side"] == OLD
        rows, output = self.developer_advance(t, {rel: self.edited_py(names)})
        self.timeout_when = None
        self.refusal(rows, output, PREPARE_ACTION)
        self.assertTrue(self.third_adds(), self.explain(rows, output))
        for add in self.third_adds():
            self.assertFalse(add["path"].exists(), self.explain(rows, output))


# --------------------------------------------------------------- AC-12

class Ac12DiffFailureTest(PriorSandbox):

    def test_ac12_diff_failures_refuse_prepare(self):
        """Сбой `git diff --name-status` базы и головы либо `git diff -M -U0` базы и головы — отказ подготовки, переход не совершён.

        Сценарий (подслучай — свежая задача): ветка правит файл тестов и
        добавляет в файл кода строку с `NODE_ENV`; git в кадрах гейта
        отказывает (а) `diff` с `--name-status`; (б) `diff` с `-U0`. В обоих
        — отказ «… — подготовка», задача в `in_dev`.

        Ловит мутацию: `None` диффа имён — пустой C и ноль находок
        строгого режима — гейт идёт дальше; сбой `diff -U0` — ноль находок
        «исключение в коде» — отказ общего действия либо проход.
        """
        rules = {"name-status": lambda args: "diff" in args and "--name-status" in args,
                 "U0": lambda args: "diff" in args and "-U0" in args}
        for label, rule in rules.items():
            with self.subTest(case=label, seed=self.seed):
                rel, names = self.py_rel(), [self.py_name()]
                project = self.junit({rel: names})
                t = self.task(project)
                self.git_fail = rule
                rows, output = self.developer_advance(
                    t, {rel: self.edited_py(names),
                        f"lib/{self.word()}.py": "import os\nMODE = os.environ['NODE_ENV']\n"})
                self.git_fail = None
                self.refusal(rows, output, PREPARE_ACTION)


# --------------------------------------------------------------- AC-13

class Ac13OwnerMarkerTest(PriorSandbox):

    def test_ac13_third_checkout_in_scratch_with_marker_and_removed(self):
        """Третья выписка заводится в том же `scratch`, где уже лежит маркер владельца, и убирается после гейта.

        Сценарий: проект `junit-xml`, файл тестов изменён веткой. Среди
        `worktree add` гейта есть третья выписка; в момент вызова рядом с её
        каталогом лежит `liveness.GATE_OWNER_MARKER`, её родитель — тот же
        каталог, что у выписки базы; после гейта каталога третьей выписки
        нет.

        Ловит мутацию: третья выписка — во временном каталоге вне `scratch`
        (без маркера владельца) — маркера рядом нет и родитель другой;
        выписка не попадает в `trees` и не убирается — каталог остался.
        """
        rel, names = self.py_rel(), [self.py_name()]
        project = self.junit({rel: names})
        t = self.task(project)
        rows, output = self.developer_advance(t, {rel: self.edited_py(names)})
        third = self.third_adds()
        self.assertEqual(len(third), 1, self.explain(rows, output) + f"\n{self.gate_adds}")
        base = [a for a in self.gate_adds if a["path"].name == "base"]
        self.assertTrue(base, self.explain(rows, output))
        self.assertTrue(third[0]["marker"], self.explain(rows, output))
        self.assertEqual(third[0]["path"].parent, base[0]["path"].parent,
                         self.explain(rows, output))
        self.assertFalse(third[0]["path"].exists(), self.explain(rows, output))


# ------------------------------------------------- заменяемые тесты (требование 4)

class ReplacementSandbox(PriorSandbox):

    def replaced(self, base, head, old, edit: bool = False,
                 more: dict | None = None):
        """Задача с утверждённой заменой теста `rname` файла `rel` (рядом —
        тест `other`, `self.other`): исходы сценария по сторонам; `edit` —
        ветка правит файл (комментарий); `more` — прочие файлы тестов
        базы. (проект, задача, путь, идентификатор, номер критерия, правка
        кода)."""
        rel, rname, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit({rel: [rname, other], **(more or {})})
        t = self.task(project)
        rid = self.case_id(project, rel, rname)
        n = self.rng.randrange(1, 60)
        self.approve_replacements(t, {rid: n})
        self.cases[(rel, rname)] = {"base": base, "head": head, OLD: old}
        self.other = other
        changes = {rel: self.edited_py([rname, other])} if edit else {}
        return project, t, rel, rid, n, changes


class Ac14ReplacementMissingTest(ReplacementSandbox):

    def test_ac14_replacement_absent_from_base_report(self):
        """Утверждённый заменяемый тест, которого нет в отчёте базы, — находка «заменяемый тест не найден в отчёте базы» и отказ.

        Сценарий: проект `junit-xml`; утверждена замена идентификатора
        `<компонент>:<файл базы>::test_<слово>`, такого теста в файле базы
        нет. Отказ «… по исходам», строка детали начинается с «заменяемый
        тест не найден в отчёте базы: <id> — » и несёт «база: ».

        Ловит мутацию: замены гейт не читает — переход в `verifying`;
        отсутствие в отчёте базы пропускается молча — отказа нет.
        """
        rel = self.py_rel()
        project = self.junit({rel: [self.py_name(), self.py_name()]})
        t = self.task(project)
        rid = self.case_id(project, rel, self.py_name())
        self.approve_replacements(t, {rid: self.rng.randrange(1, 60)})
        rows, output = self.developer_advance(t)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        lines = self.starting(detail, f"{REPL_MISSING}: {rid} — ")
        self.assertEqual(len(lines), 1, self.explain(rows, output))
        self.assertIn("база: ", lines[0], self.explain(rows, output))


class Ac15ReplacementNotGreenTest(ReplacementSandbox):

    def test_ac15_replacement_red_on_base_or_base_rerun(self):
        """Заменяемый тест не из `PASS_TO_PASS` базы либо красный в перепрогоне базы — находка «заменяемый тест не зелёный на базе», отказ, строки «заменён по SPEC» нет.

        Сценарий (подслучай — свежая задача): тест исчез из отчёта ветки,
        прежняя версия `failed` во всех прогонах; (а) на базе `failed`
        (не `PASS_TO_PASS`); (б) база зелёна в полном прогоне и `failed` в
        первом перепрогоне. Отказ «… по исходам»: строка «заменяемый тест не
        зелёный на базе: <id> — …» с «база: »; ни одна запись не несёт
        «заменён по SPEC: <id>».

        Ловит мутацию: зелень базы берётся только из полного прогона — (б)
        без находки и с «заменён по SPEC»; не `PASS_TO_PASS` база не
        проверяется — (а) без находки.
        """
        for label, base in (("не PASS_TO_PASS", ["failed"]),
                            ("перепрогон базы", ["passed", "failed"])):
            with self.subTest(case=label, seed=self.seed):
                project, t, rel, rid, n, changes = self.replaced(
                    base, ["missing"], ["failed"])
                rows, output = self.developer_advance(t, changes)
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                lines = self.starting(detail, f"{REPL_NOT_GREEN}: {rid} — ")
                self.assertEqual(len(lines), 1, self.explain(rows, output))
                self.assertIn("база: ", lines[0], self.explain(rows, output))
                self.assertFalse(any(f"{REPLACED}: {rid}" in x for x in self.texts(rows)),
                                 self.explain(rows, output))


class Ac16ReplacementNeedlessTest(ReplacementSandbox):

    def test_ac16_prior_green_once_is_needless_finding(self):
        """Прежняя версия утверждённого заменяемого теста зелёная хотя бы в одном прогоне третьей выписки — находка «замена не нужна: прежняя версия зелёная на коде ветки» и отказ.

        Сценарий (подслучай — свежая задача): база зелёна, тест исчез из
        отчёта ветки; прежняя версия (а) `passed`; (б) `failed`, затем
        `passed` в перепрогоне. Отказ «… по исходам», строка начинается с
        «замена не нужна: прежняя версия зелёная на коде ветки: <id> —
        прежняя версия: ».

        Ловит мутацию: зелень прежней версии судится только по первому
        прогону — (б) без находки и гейт пройден; находка не пишется вовсе
        — (а) гейт пройден.
        """
        for label, old in (("зелёная", ["passed"]), ("зелёная в перепрогоне",
                                                      ["failed", "passed"])):
            with self.subTest(case=label, seed=self.seed):
                project, t, rel, rid, n, changes = self.replaced(
                    ["passed"], ["missing"], old)
                rows, output = self.developer_advance(t, changes)
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                self.assertTrue(self.starting(
                    detail, f"{REPL_NEEDLESS}: {rid} — прежняя версия: "),
                    self.explain(rows, output))


class Ac17ReplacementCoversTest(ReplacementSandbox):

    def test_ac17_gone_replaced_test_passes_covered_by_replacement(self):
        """Утверждённый заменяемый тест исчез на ветке, прежняя версия трижды красная при зелёной базе (`python-ast`) — гейт пройден, «исчез» покрыт заменой, одна находка на идентификатор.

        Сценарий: проект `junit-xml` (`python-ast`); тест базы зелёный,
        записи на ветке нет, прежняя версия `failed` во всех прогонах.
        Гейт пройден; запись несёт строку «заменён по SPEC: <id> → AC-<n>»,
        строку «исчез: <id> — …», кончающуюся «— покрыто мандатом замена
        SPEC → AC-<n>», и не несёт строки «прежняя версия красная на коде
        ветки: <id>».

        Ловит мутацию: замена не снимает «исчез» — отказ; находка прежней
        версии добавляется при находке «исчез» — вторая строка (и непокрытая
        находка); строка «заменён по SPEC» не пишется.
        """
        project, t, rel, rid, n, changes = self.replaced(
            ["passed"], ["missing"], ["failed"])
        rows, output = self.developer_advance(t, changes)
        self.no_gate_refusal(rows, output)
        detail = self.passed(rows, output)
        lines = detail.splitlines()
        self.assertIn(f"{REPLACED}: {rid} → AC-{n}", lines, self.explain(rows, output))
        gone = self.starting(detail, f"{GONE}: {rid} — ")
        self.assertEqual(len(gone), 1, self.explain(rows, output))
        self.assertTrue(gone[0].endswith(COVERED_BY_REPLACEMENT.format(n=n)),
                        self.explain(rows, output))
        self.assertFalse(self.starting(detail, f"{PRIOR_RED}: {rid}"),
                         self.explain(rows, output))

    def test_ac17_present_replaced_test_prior_red_covered(self):
        """Утверждённый заменяемый тест есть на ветке и зелёный (файл изменён), прежняя версия трижды красная — гейт пройден, находка прежней версии покрыта заменой.

        Сценарий: проект `junit-xml` (`python-ast`); тест базы и ветки
        зелёный, файл изменён веткой (комментарий), прежняя версия `failed`
        во всех прогонах. Гейт пройден; запись несёт «заменён по SPEC: <id>
        → AC-<n>» и строку «прежняя версия красная на коде ветки: <id> — …»,
        кончающуюся «— покрыто мандатом замена SPEC → AC-<n>».

        Ловит мутацию: замена не снимает «прежняя версия красная» — отказ;
        источник покрытия в строке — не «замена SPEC → AC-<n>».
        """
        project, t, rel, rid, n, changes = self.replaced(
            ["passed"], ["passed"], ["failed"], edit=True)
        rows, output = self.developer_advance(t, changes)
        self.no_gate_refusal(rows, output)
        detail = self.passed(rows, output)
        self.assertIn(f"{REPLACED}: {rid} → AC-{n}", detail.splitlines(),
                      self.explain(rows, output))
        red = self.starting(detail, f"{PRIOR_RED}: {rid} — ")
        self.assertEqual(len(red), 1, self.explain(rows, output))
        self.assertTrue(red[0].endswith(COVERED_BY_REPLACEMENT.format(n=n)),
                        self.explain(rows, output))


class Ac18ReplacementLimitsTest(ReplacementSandbox):

    def test_ac18_replacement_does_not_cover_skipped(self):
        """Утверждённая замена не снимает «стал пропуском» своего теста — отказ.

        Сценарий: проект `junit-xml`; утверждённый заменяемый тест на ветке
        `skipped`, база зелёна, прежняя версия `failed` во всех прогонах.
        Отказ «… по исходам» со строкой «стал пропуском: <id> — …».

        Ловит мутацию: замена снимает любую находку своего идентификатора —
        гейт пройден.
        """
        project, t, rel, rid, n, changes = self.replaced(
            ["passed"], ["skipped"], ["failed"])
        rows, output = self.developer_advance(t, changes)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertTrue(self.starting(detail, f"{SKIPPED}: {rid} — "),
                        self.explain(rows, output))

    def test_ac18_undeclared_prior_red_covered_only_by_operator(self):
        """Не заявленный тест, красный на третьей выписке, снимает только мандат Оператора — утверждённая замена соседа его не снимает.

        Сценарий (подслучай — свежая задача): в файле утверждённый
        заменяемый тест (исчез на ветке, прежняя версия красная) и не
        заявленный тест X (зелёный на базе и ветке, прежняя версия `failed`
        во всех прогонах); файл изменён веткой. (а) без мандата — отказ «…
        по исходам» со строкой «прежняя версия красная на коде ветки:
        <X>»; (б) мандат Оператора на путь файла — отказа гейта нет.

        Ловит мутацию: замена покрывает находки всего файла заменяемого
        теста — (а) гейт пройден; мандат Оператора не проверяется для
        находок прежних версий — (б) отказ.
        """
        for label in ("без мандата", "мандат Оператора"):
            with self.subTest(case=label, seed=self.seed):
                project, t, rel, rid, n, changes = self.replaced(
                    ["passed"], ["missing"], ["failed"], edit=True)
                x = self.other
                self.cases[(rel, x)] = {"base": ["passed"], "head": ["passed"],
                                        OLD: ["failed"]}
                if label == "мандат Оператора":
                    self.grant(t, paths=[rel])
                rows, output = self.developer_advance(
                    t, changes, finished=label == "мандат Оператора")
                if label == "без мандата":
                    detail = self.refusal(rows, output, OUTCOME_ACTION)
                    xid = self.case_id(project, rel, x)
                    self.assertTrue(self.starting(detail, f"{PRIOR_RED}: {xid} — "),
                                    self.explain(rows, output))
                else:
                    self.no_gate_refusal(rows, output)


class Ac26RecordOrderTest(ReplacementSandbox):

    def test_ac26_passed_record_line_order(self):
        """Порядок строк записи пройденного гейта: счёт, доказательство, «прежние версии», «нестабилен и на базе», «заменён по SPEC», покрытые находки.

        Сценарий: проект `junit-xml`; файл A с утверждённым заменяемым
        тестом (исчез на ветке, прежняя версия трижды красная, база
        зелёна); файл B изменён веткой, его тест Y — прежняя версия
        красная, база красна в одном перепрогоне. Гейт пройден; индексы
        строк: счёт (с «тестов базы») — 0, доказательство — 1, далее строго
        по возрастанию «прежние версии: …», «нестабилен и на базе: <Y>»,
        «заменён по SPEC: …», строка находки «исчез … — покрыто мандатом …».

        Ловит мутацию: строка «прежние версии» дописана в конец записи или
        перед доказательством; «заменён по SPEC» после покрытых находок;
        строка доказательства сдвинута со второй позиции.
        """
        b_rel, y = self.py_rel(), self.py_name()
        b_names = [y, self.py_name()]
        project, t, rel, rid, n, _changes = self.replaced(
            ["passed"], ["missing"], ["failed"], more={b_rel: b_names})
        base = ["passed", "passed", "passed"]
        base[self.rng.choice((1, 2))] = "failed"
        self.cases[(b_rel, y)] = {"base": base, "head": ["passed"], OLD: ["failed"]}
        rows, output = self.developer_advance(t, {b_rel: self.edited_py(b_names)})
        self.no_gate_refusal(rows, output)
        lines = self.passed(rows, output).splitlines()
        yid = self.case_id(project, b_rel, y)

        def index(pred, what):
            found = [i for i, line in enumerate(lines) if pred(line)]
            self.assertTrue(found, self.explain(rows, output) + f"\nнет строки: {what}")
            return found[0]
        order = [index(lambda s: COUNTS_MARK in s, "счёт"),
                 index(lambda s: PROOF_LINE.match(s.strip()), "доказательство"),
                 index(lambda s: PRIOR_LINE.match(s), "прежние версии"),
                 index(lambda s: s == f"{FLAKY}: {yid}", "нестабилен и на базе"),
                 index(lambda s: s == f"{REPLACED}: {rid} → AC-{n}", "заменён по SPEC"),
                 index(lambda s: s.startswith(f"{GONE}: {rid} — "), "покрытая находка")]
        self.assertEqual(order[:2], [0, 1], self.explain(rows, output))
        self.assertEqual(order, sorted(order), self.explain(rows, output) + f"\n{order}")


class Ac34NeedlessWithGoneTest(ReplacementSandbox):

    def test_ac34_needless_added_despite_gone(self):
        """Утверждённый заменяемый тест исчез на ветке, его прежняя версия зелёная — отказ со строкой «замена не нужна: …» по идентификатору; «исчез» замена снимает.

        Сценарий: проект `junit-xml`; база зелёна, записи на ветке нет,
        прежняя версия `passed`. Отказ «… по исходам»: строка «замена не
        нужна: прежняя версия зелёная на коде ветки: <id> — …» есть, строки
        «исчез: <id> — …» в детали нет.

        Ловит мутацию: правило «одна находка на идентификатор» применено и
        к находкам требования 4 — при «исчез» находки «замена не нужна» нет
        (а «исчез» покрыт — гейт пройден).
        """
        project, t, rel, rid, n, changes = self.replaced(
            ["passed"], ["missing"], ["passed"])
        rows, output = self.developer_advance(t, changes)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertTrue(self.starting(detail, f"{REPL_NEEDLESS}: {rid} — "),
                        self.explain(rows, output))
        self.assertFalse(self.starting(detail, f"{GONE}: {rid} — "),
                         self.explain(rows, output))


# ------------------------------------------------------- строгий режим (требование 5)

class StrictSandbox(PriorSandbox):

    def js_case(self) -> str:
        """Имя теста Vitest без пробела — годится в префикс `путь::имя`."""
        return f"case_{self.word()}"


class Ac19StrictModeTest(StrictSandbox):

    def test_ac19_strict_edit_and_mandates(self):
        """Строгий режим: правка существующего файла `tests` — находка «строгий режим — правка существующего файла: <путь> — статус M»; снимает её только мандат на путь.

        Сценарий (подслучай — свежая задача, проект `pult-vitest`): ветка
        правит существующий файл тестов (комментарий); (а) без мандата —
        отказ «… по исходам» со строкой находки; (б) мандат Оператора
        «Ослабление тестов разрешено: <путь>» — отказа гейта нет; (в) мандат
        по идентификатору теста этого файла; (г) мандат на префикс
        `путь::имя` — в (в) и (г) отказ с той же строкой.

        Ловит мутацию: строгого режима нет — (а) гейт пройден; покрытие
        находки пути правилом `_covering_pair` (мандат по идентификатору или
        префикс) — (в)/(г) без отказа; мандат на путь не сверяется — (б)
        отказ.
        """
        for label in ("без мандата", "путь", "идентификатор", "префикс"):
            with self.subTest(case=label, seed=self.seed):
                rel, names = self.js_rel(), [self.js_case(), self.js_case()]
                project = self.vitest({rel: names})
                t = self.task(project)
                cid = self.case_id(project, rel, names[0])
                covered = f"`{rel}`"
                if label == "путь":
                    self.grant(t, paths=[rel], covered=covered)
                elif label == "идентификатор":
                    self.grant(t, ids=[cid], covered=covered)
                elif label == "префикс":
                    self.grant(t, paths=[f"{rel}::{names[0]}"], covered=covered)
                rows, output = self.developer_advance(
                    t, {rel: self.edited_js(names)}, finished=label != "без мандата")
                line = f"{STRICT}: {rel} — статус M"
                if label == "путь":
                    self.no_gate_refusal(rows, output)
                else:
                    detail = self.refusal(rows, output, OUTCOME_ACTION)
                    self.assertIn(line, detail.splitlines(), self.explain(rows, output))

    def test_ac19_strict_deleted_and_renamed(self):
        """Строгий режим: удалённый файл `tests` — находка со статусом `D`; переименованный — находка с прежним путём и статусом `R…`.

        Сценарий (подслучай — свежая задача, `pult-vitest`): ветка (а)
        удаляет файл тестов; (б) переименовывает его без правки строк. Отказ
        «… по исходам»; в (а) строка «строгий режим — правка существующего
        файла: <путь> — статус D», в (б) — строка, начинающаяся «строгий
        режим — правка существующего файла: <прежний путь> — статус R».

        Ловит мутацию: в строгий режим идут только `M` — (а)/(б) без строки;
        у `R` берётся новый путь — строка с новым путём.
        """
        for label in ("D", "R"):
            with self.subTest(case=label, seed=self.seed):
                rel, names = self.js_rel(), [self.js_case()]
                project = self.vitest({rel: names, self.js_rel(): [self.js_case()]})
                t = self.task(project)
                change = {rel: None} if label == "D" else {self.js_rel(): Moved(rel)}
                rows, output = self.developer_advance(t, change)
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                prefix = f"{STRICT}: {rel} — статус {label}"
                self.assertTrue(self.starting(detail, prefix), self.explain(rows, output))


class Ac20StrictReplacementTest(StrictSandbox):

    def test_ac20_replacement_file_strict_without_path_mandate(self):
        """Строгий режим: файл утверждённого заменяемого теста без мандата на путь — находка строгого режима и отказ; замена снимает лишь «исчез» и «прежняя версия красная».

        Сценарий (подслучай — свежая задача, `pult-vitest`, утверждена
        замена теста R, база R зелёна, прежняя версия R `failed` во всех
        прогонах): (а) ветка удаляет R из файла; (б) R остаётся в тексте
        (записи на ветке нет), ветка правит соседний тест того же файла. В
        обоих — отказ «… по исходам» со строкой «строгий режим — правка
        существующего файла: <путь> — статус M» и без строк «исчез: <R>» и
        «прежняя версия красная на коде ветки: <R>».

        Ловит мутацию: утверждённая замена снимает находку строгого режима
        файла своего теста — гейт пройден; замена не снимает «исчез» — в
        детали строка «исчез: <R>».
        """
        for label in ("удалён", "сосед"):
            with self.subTest(case=label, seed=self.seed):
                rel, rname, other = self.js_rel(), self.js_case(), self.js_case()
                project = self.vitest({rel: [rname, other]})
                t = self.task(project)
                rid = self.case_id(project, rel, rname)
                self.approve_replacements(t, {rid: self.rng.randrange(1, 60)})
                self.cases[(rel, rname)] = {"base": ["passed"], "head": ["missing"],
                                            OLD: ["failed"]}
                if label == "удалён":
                    text = js_source([other])
                else:
                    text = (js_source([rname]) + f"// {CLAIM}\nit('{other}', () => "
                            "{ expect(2).toBe(2); });\n")
                rows, output = self.developer_advance(t, {rel: text})
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                self.assertIn(f"{STRICT}: {rel} — статус M", detail.splitlines(),
                              self.explain(rows, output))
                self.assertFalse(self.starting(detail, f"{GONE}: {rid} — "),
                                 self.explain(rows, output))
                self.assertFalse(self.starting(detail, f"{PRIOR_RED}: {rid} — "),
                                 self.explain(rows, output))


class Ac21PythonAstTest(StrictSandbox):

    def test_ac21_python_ast_only_non_py_support_is_strict(self):
        """Профиль с `python-ast`: правка `.py` под `test_support` и правка файла тестов находки строгого режима не дают, правка не `.py` под `test_support` — даёт.

        Сценарий: проект `junit-xml` с `test_support: [support/**]`; ветка
        правит `support/<имя>.py`, `support/<имя>.json` и существующий файл
        тестов. Отказ «… по исходам»; строки находок строгого режима —
        ровно одна, «строгий режим — правка существующего файла:
        support/<имя>.json — статус M».

        Ловит мутацию: строгий режим не смотрит на слои — находки и на
        `.py`, и на файл тестов; строгий режим выключен целиком при
        `python-ast` — находки `.json` нет и гейт пройден.
        """
        helper, data = f"support/{self.word()}.py", f"support/{self.word()}.json"
        rel, names = self.py_rel(), [self.py_name()]
        project = self.junit({rel: names}, extra={"test_support": flow(["support/**"])},
                             files={helper: "HELPER = 1\n", data: '{"a": 1}\n'})
        t = self.task(project)
        rows, output = self.developer_advance(
            t, {helper: "HELPER = 2\n", data: '{"a": 2}\n', rel: self.edited_py(names)})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertEqual(self.starting(detail, f"{STRICT}: "),
                         [f"{STRICT}: {data} — статус M"], self.explain(rows, output))


# --------------------------------------------- исключения в коде (требования 6, 7)

def env_lines(n: int) -> list:
    return [f"VALUE_{i} = {i}" for i in range(n)]


class Ac22PathMandateTest(StrictSandbox):

    def test_ac22_code_path_mandate_in_bounds_covers_exception(self):
        """У профиля в границе мандат «Ослабление тестов разрешено:» на путь файла кода вне `weakening_scope` принят командой `answer` и снимает находку «исключение в коде».

        Сценарий: проект `junit-xml` (`weakening_scope: tests/**`); ветка
        добавляет в `lib/<имя>.py` строку с `NODE_ENV`. Первый `advance` —
        отказ «… по исходам» со строкой «исключение в коде: <путь> — строка
        <n>: NODE_ENV»; затем `answer` Оператора с мандатом на этот путь —
        принят; повторный `advance` — отказа гейта нет, запись пройденного
        гейта несёт строку этой находки «— покрыто мандатом ANSWER-…».

        Ловит мутацию: прежнее правило области — `answer` отклоняет путь
        вне `weakening_scope`; находка пути покрывается правилом теста —
        повторный `advance` снова отказ.
        """
        code = f"lib/{self.word()}.py"
        project = self.junit({self.py_rel(): [self.py_name()]})
        t = self.task(project)
        lines = env_lines(self.rng.randint(1, 4))
        lines.insert(self.rng.randint(0, len(lines)), "MODE = __import__('os').environ['NODE_ENV']")
        number = lines.index("MODE = __import__('os').environ['NODE_ENV']") + 1
        finding = f"{CODE_EXC}: {code} — строка {number}: NODE_ENV"
        rows, output = self.developer_advance(t, {code: "\n".join(lines) + "\n"})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertIn(finding, detail.splitlines(), self.explain(rows, output))
        self.grant(t, paths=[code])
        rows, output = self.developer_advance(t, {}, finished=True)
        self.no_gate_refusal(rows, output)
        covered = self.starting(self.passed(rows, output), f"{finding} — покрыто мандатом ANSWER-")
        self.assertEqual(len(covered), 1, self.explain(rows, output))

    def test_ac22_out_of_bounds_code_path_refused(self):
        """У профиля вне границы (`test_profile`) элемент мандата на путь вне `weakening_scope` — прежний отказ «путь вне области …».

        Сценарий: учебный проект с записью `test_profile`; `answer`
        Оператора с мандатом на `lib/<имя>.py`. Команда отказывает, текст
        называет элемент и «путь вне области».

        Ловит мутацию: расширение области мандата действует и вне границы
        `in_outcome_bounds` — `answer` принят.
        """
        project = self.junit_project({self.py_rel(): [self.py_name()]}, test_profile=True)
        t = self.task(project)
        code = f"lib/{self.word()}.py"
        ok, output = self.operator_answer(t, paths=[code])
        self.assertFalse(ok, self.note(output))
        self.assertIn(code, output, self.note(output))
        self.assertIn("путь вне области", output, self.note(output))


class Ac23CodeExceptionsTest(StrictSandbox):

    def test_ac23_each_token_in_added_code_line_and_exemptions(self):
        """Каждая подстрока перечня в добавленной строке файла кода — находка «исключение в коде: <путь> — строка <n>: <подстрока>» с номером по файлу головы; удалённая строка, файл `tests`, файл `test_support`, двоичный файл и переименование без правки строк находок не дают.

        Сценарий: проект `pult-vitest` с `test_support:
        [frontend/setup/**]`; ветка вставляет в `lib/app.js` по строке на
        каждую подстроку на случайные позиции; удаляет строку с подстрокой
        из `lib/gone.js`; переименовывает `lib/old.js` (строка с подстрокой
        в базе) без правки; добавляет строку с подстрокой в файл тестов и в
        файл `test_support`; добавляет двоичный файл с подстрокой. Отказ
        «… по исходам»; строки «исключение в коде: …» детали — ровно по
        одной на каждую подстроку `lib/app.js` с верным номером строки.

        Ловит мутацию: номер строки по файлу базы или по ханку диффа — не
        тот номер; поиск по всем строкам диффа (с удалёнными) — строка для
        `lib/gone.js`; переименование считается новым файлом — строка для
        нового пути; файлы `tests`/`test_support` или двоичный не
        исключены — лишние строки; одна находка на строку при нескольких
        файлах — не хватает строк.
        """
        rel, names = self.js_rel(), [self.js_case()]
        setup = f"frontend/setup/{self.word()}.js"
        base_app = [f"const a{i} = {i};" for i in range(self.rng.randint(2, 6))]
        files = {"lib/app.js": "\n".join(base_app) + "\n",
                 "lib/gone.js": "const g = 1;\n// eslint-disable-next-line\nconst h = 2;\n",
                 "lib/old.js": "const o = 1; /* istanbul ignore next */\n",
                 setup: "export default {};\n"}
        project = self.vitest({rel: names}, extra={"test_support": flow(["frontend/setup/**"])},
                              files=files)
        t = self.task(project)
        head_app = list(base_app)
        for i, token in enumerate(self.rng.sample(TOKENS, len(TOKENS))):
            head_app.insert(self.rng.randint(0, len(head_app)),
                            f"const t{i} = '{token}';")
        expected = set()
        for number, line in enumerate(head_app, start=1):
            for token in TOKENS:
                if f"'{token}'" in line:
                    expected.add(f"{CODE_EXC}: lib/app.js — строка {number}: {token}")
        rows, output = self.developer_advance(t, {
            "lib/app.js": "\n".join(head_app) + "\n",
            "lib/gone.js": "const g = 1;\nconst h = 2;\n",
            "lib/new.js": Moved("lib/old.js"),
            rel: js_source(names) + "// v8 ignore next\n",
            setup: "export default {};\nconst m = process.env.VITEST;\n",
            f"lib/{self.word()}.bin": b"\x00\x01NODE_ENV\x00\xff\x00",
        })
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertEqual(set(self.starting(detail, f"{CODE_EXC}: ")), expected,
                         self.explain(rows, output))
        self.assertEqual(len(expected), len(TOKENS), self.note(str(head_app)))


class Ac24ComponentPathsTest(StrictSandbox):

    def test_ac24_paths_limit_exception_scope(self):
        """Единственный компонент без `paths` — проверка исключений охватывает любой файл репозитория вне `tests`/`test_support`; с `paths` — только файлы под `paths`.

        Сценарий (подслучай — свежая задача, `junit-xml`): ветка добавляет
        строку с `NODE_ENV` в `lib/<имя>.py` и в `misc/<имя>.txt`; (а)
        компонент без `paths` — находки по обоим файлам; (б) `paths: ^lib/`
        — находка только по `lib/<имя>.py`.

        Ловит мутацию: `paths` не читается — в (б) находка и по `misc/…`;
        без `paths` проверяются только файлы `*.py` или только под
        `weakening_scope` — в (а) нет находки по `misc/…`.
        """
        for label in ("без paths", "paths"):
            with self.subTest(case=label, seed=self.seed):
                extra = {"paths": "^lib/"} if label == "paths" else None
                project = self.junit({self.py_rel(): [self.py_name()]}, extra=extra)
                t = self.task(project)
                code, misc = f"lib/{self.word()}.py", f"misc/{self.word()}.txt"
                rows, output = self.developer_advance(t, {
                    code: "import os\nMODE = os.environ['NODE_ENV']\n",
                    misc: "mode: NODE_ENV\n"})
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                expected = {f"{CODE_EXC}: {code} — строка 2: NODE_ENV"}
                if label == "без paths":
                    expected.add(f"{CODE_EXC}: {misc} — строка 1: NODE_ENV")
                self.assertEqual(set(self.starting(detail, f"{CODE_EXC}: ")), expected,
                                 self.explain(rows, output))


class Ac25RefusalActionTest(StrictSandbox):

    def test_ac25_broken_only_vs_new_kind_action_and_hint(self):
        """Отказ только из «сломан правкой» — действие «… — сломан правкой»; при находке нового вида — общее действие, подсказка называет мандат на путь.

        Сценарий (подслучай — свежая задача, `junit-xml`): тест A трижды
        красный на ветке, база зелёна; (а) других находок нет — действие «…
        — сломан правкой»; (б) ещё изменён файл теста B, прежняя версия
        которого трижды красная, — действие «переход отклонён: гейт
        неослабления по исходам», строка подсказки «дальше: …» называет
        маркер «Ослабление тестов разрешено:» и путь.

        Ловит мутацию: находки нового вида причислены к «сломан правкой» —
        в (б) действие «… — сломан правкой»; подсказка прежняя (без пути) —
        в (б) нет слова «путь».
        """
        for label in ("только сломан", "новый вид"):
            with self.subTest(case=label, seed=self.seed):
                a_rel, a = self.py_rel(), self.py_name()
                b_rel, b = self.py_rel(), self.py_name()
                project = self.junit({a_rel: [a, self.py_name()], b_rel: [b]})
                t = self.task(project)
                self.cases[(a_rel, a)] = {"base": ["passed"], "head": ["failed"]}
                changes = {}
                if label == "новый вид":
                    self.cases[(b_rel, b)] = {"base": ["passed"], "head": ["passed"],
                                              OLD: ["failed"]}
                    changes = {b_rel: self.edited_py([b])}
                rows, output = self.developer_advance(t, changes)
                if label == "только сломан":
                    self.refusal(rows, output, BROKEN_ACTION)
                    continue
                self.refusal(rows, output, OUTCOME_ACTION)
                hints = [line for line in output.splitlines() if "дальше:" in line]
                self.assertTrue(hints, self.explain(rows, output))
                self.assertIn(MANDATE_MARKER, hints[-1], self.explain(rows, output))
                self.assertIn("путь", hints[-1], self.explain(rows, output))


class Ac31NoTestsFieldExceptionsTest(StrictSandbox):

    def test_ac31_new_and_unreported_files_under_scope(self):
        """Компонент без поля `tests`: новый модуль кода и существующий файл под `weakening_scope` без записей отчёта — находки «исключение в коде»; новый файл тестов с записями в отчёте головы — нет; тот же текст в новом файле кода вне `weakening_scope` — находка.

        Сценарий: проект `junit-xml` с `weakening_scope: [tests/**,
        src/**]`, в базе `src/util.py` (записей отчёта нет); ветка добавляет
        `src/<имя>.py` со строкой `NODE_ENV` (а), дописывает строку с
        `NODE_ENV` в `src/util.py` (б), добавляет долгоживущий
        `tests/test_<id>_x.py` с тестом, где `monkeypatch.setenv("NODE_ENV",
        …)`, и файл `lib/<имя>.py` с тем же текстом (в). Отказ «… по
        исходам»; строки «исключение в коде: …» — ровно для `src/<имя>.py`,
        `src/util.py` и `lib/<имя>.py` с номерами строк головы.

        Ловит мутацию: все файлы `A` под `weakening_scope` считаются
        тестовыми — нет находки (а); тестовым считается любой файл под
        `weakening_scope` — нет находки (б); новый файл тестов с записями
        считается кодом — лишняя строка для `tests/…`.
        """
        project = self.junit({self.py_rel(): [self.py_name()]},
                             extra={"weakening_scope": flow(["tests/**", "src/**"])},
                             files={"src/util.py": "VALUE = 1\n"})
        t = self.task(project)
        new_mod, lib = f"src/{self.word()}.py", f"lib/{self.word()}.py"
        env_test = ('"""Тесты сценария."""\n\n\ndef test_env(monkeypatch):\n'
                    f'    """{CLAIM}"""\n'
                    '    monkeypatch.setenv("NODE_ENV", "test")\n')
        rows, output = self.developer_advance(t, {
            new_mod: "import os\nMODE = os.environ.get('NODE_ENV')\n",
            "src/util.py": "VALUE = 1\nimport os\nMODE = os.environ['NODE_ENV']\n",
            f"tests/test_{t.low}_x.py": env_test,
            lib: env_test})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertEqual(set(self.starting(detail, f"{CODE_EXC}: ")), {
            f"{CODE_EXC}: {new_mod} — строка 2: NODE_ENV",
            f"{CODE_EXC}: src/util.py — строка 3: NODE_ENV",
            f"{CODE_EXC}: {lib} — строка 6: NODE_ENV"}, self.explain(rows, output))


# --------------------------------------------------------------- AC-32

class Ac32AddedFilesRemovedTest(PriorSandbox):

    def conftest_case(self, extra: dict | None, conftest: str):
        """Ветка добавляет `conftest`, «чинящий» прежнюю версию изменённого
        теста (на стороне прежних версий тест зелёный, только если файл
        есть в дереве): ожидается отказ с находкой прежней версии и
        отсутствие файла на третьей выписке."""
        rel, name = self.py_rel(), self.py_name()
        project = self.junit({rel: [name]}, extra=extra)
        t = self.task(project)
        self.cases[(rel, name)] = {"base": ["passed"], "head": ["passed"], OLD: ["failed"]}
        self.rescue = (conftest,)
        self.watch_old = (conftest,)
        rows, output = self.developer_advance(t, {
            conftest: "import app\n\napp.fixed = True\n", rel: self.edited_py([name])})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        cid = self.case_id(project, rel, name)
        self.assertTrue(self.starting(detail, f"{PRIOR_RED}: {cid} — "),
                        self.explain(rows, output))
        self.assertTrue(self.old_runs(), self.explain(rows, output))
        self.assertFalse(any(r["seen"][conftest] for r in self.old_runs()),
                         self.explain(rows, output))

    def test_ac32_added_conftest_under_test_support_removed(self):
        """Добавленный `conftest.py` под маской `test_support` на третьей выписке удалён: прежняя версия изменённого теста красная — находка и отказ.

        Сценарий: проект `junit-xml` с `test_support: [support/**]`; ветка
        добавляет `support/conftest.py` и правит существующий тест. На
        стороне прежних версий файла нет; отказ «… по исходам» со строкой
        «прежняя версия красная на коде ветки: <id> — …».

        Ловит мутацию: файлы `A` под `test_support` на третьей выписке
        остаются — прежняя версия «спасена», гейт пройден.
        """
        self.conftest_case({"test_support": flow(["support/**"])}, "support/conftest.py")

    def test_ac32_added_conftest_under_tests_masks_removed(self):
        """Добавленный `conftest.py` под масками `tests` компонента с полем `tests` на третьей выписке удалён — находка «прежняя версия красная на коде ветки» и отказ.

        Сценарий: проект `junit-xml` с `tests: [tests/**]`; ветка добавляет
        `tests/conftest.py` и правит существующий тест.

        Ловит мутацию: удаляются только файлы `A` с записями в отчёте —
        `conftest.py` без записей остаётся, гейт пройден.
        """
        self.conftest_case({"tests": flow(["tests/**"])}, "tests/conftest.py")

    def test_ac32_added_conftest_under_scope_without_tests_removed(self):
        """Компонент без `tests` и `test_support`: добавленный `conftest.py` под `weakening_scope` (записей в отчёте головы нет) на третьей выписке удалён — находка и отказ.

        Сценарий: проект `junit-xml` без `tests`/`test_support`
        (`weakening_scope: tests/**`); ветка добавляет `tests/conftest.py` и
        правит существующий тест.

        Ловит мутацию: у компонента без `tests` удаляются только файлы `A`
        с записями в отчёте головы (определение для поиска подстрок) —
        `conftest.py` остаётся, гейт пройден.
        """
        self.conftest_case(None, "tests/conftest.py")


# --------------------------------------------------------------- AC-33

class Ac33SkippedMissingRedTest(PriorSandbox):

    def test_ac33_prior_skipped_or_missing_is_red(self):
        """Исход прежней версии «пропуск» и «нет записи» при зелёной базе — красный: трижды такой исход — находка «прежняя версия красная на коде ветки» и отказ.

        Сценарий (подслучай — свежая задача): проект `junit-xml`, файл
        теста изменён веткой; на стороне прежних версий тест (а) `skipped`
        во всех прогонах; (б) без записи во всех прогонах. Отказ «… по
        исходам» со строкой «прежняя версия красная на коде ветки: <id> — …».

        Ловит мутацию: зелёным считается всё, кроме `failed`/`error` —
        пропуск и отсутствие записи не находка, гейт пройден.
        """
        for label in ("skipped", "missing"):
            with self.subTest(case=label, seed=self.seed):
                rel, names = self.py_rel(), [self.py_name(), self.py_name()]
                project = self.junit({rel: names})
                t = self.task(project)
                self.cases[(rel, names[0])] = {"base": ["passed"], "head": ["passed"],
                                               OLD: [label]}
                rows, output = self.developer_advance(t, {rel: self.edited_py(names)})
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                cid = self.case_id(project, rel, names[0])
                self.assertTrue(self.starting(detail, f"{PRIOR_RED}: {cid} — "),
                                self.explain(rows, output))


# --------------------------------------------------------------- AC-27

class Ac27MergeProofTest(ReplacementSandbox):

    def merged_ready(self):
        """Задача, прошедшая выход из `in_dev` с покрытыми находками новых
        видов: «исключение в коде» под мандатом на путь и «исчез» под
        утверждённой заменой. (задача, идентификатор, номер, путь, причина
        замены, деталь записи)."""
        rel, rname, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit({rel: [rname, other]})
        t = self.task(project)
        rid = self.case_id(project, rel, rname)
        n = self.rng.randrange(1, 60)
        reason = f"замена сценария {self.word()}"
        self.journal_replacements(t, {rid: n}, reason)
        self.cases[(rel, rname)] = {"base": ["passed"], "head": ["missing"], OLD: ["failed"]}
        code = f"lib/{self.word()}.py"
        self.grant(t, paths=[code])
        rows, output = self.developer_advance(
            t, {code: "import os\nMODE = os.environ['NODE_ENV']\n"}, finished=True)
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        detail = self.passed(rows, output)
        self.assertTrue(self.starting(detail, f"{CODE_EXC}: {code} — "),
                        self.explain(rows, output))
        self.assertTrue(self.starting(detail, f"{GONE}: {rid} — "), self.explain(rows, output))
        return t, rid, n, code, reason, detail

    def journal_replacements(self, t, items: dict, reason: str) -> None:
        detail = "\n".join(guard.ReplacedTest(cid, n, reason).line
                           for cid, n in items.items())
        store.journal(self.conn, t.id, "operator", mandate.REPLACED_TESTS_ACTION, detail)

    def test_ac27_proof_with_new_kinds_skips_run(self):
        """Запись пройденного гейта с покрытыми находками нового вида (путь и замена) и той же четвёркой — на мерже нет ни выписки прежних версий, ни полного набора; элементы пути и замены — в отпечатке.

        Сценарий: задача проходит выход из `in_dev` с находкой «исключение
        в коде» под мандатом на путь и находкой «исчез» под утверждённой
        заменой; отпечаток строки доказательства — sha256 отсортированных
        элементов `<путь>` и `замена:<id>→AC-<n>`, соединённых переводом
        строки. Задача на `merge_gate`, `approve`: полный набор не звался,
        третьей выписки и прогонов прежних версий нет, задача в `done`.

        Ловит мутацию: `_proven` не разбирает строки находок новых видов —
        доказательство не совпадает, полный набор прогнан; элемент пути
        или замены не входит в отпечаток — отпечаток иной.
        """
        t, rid, n, code, _reason, detail = self.merged_ready()
        fields = [PROOF_LINE.match(line.strip()) for line in detail.splitlines()]
        fields = [m.groups() for m in fields if m]
        self.assertTrue(fields, self.note(detail))
        wanted = hashlib.sha256("\n".join(sorted(
            {code, f"замена:{rid}→AC-{n}"})).encode("utf-8")).hexdigest()
        self.assertEqual(fields[0][3], wanted, self.note(detail))
        self.to_merge_gate(t)
        rows, output = self.approve(t)
        self.assertEqual(self.suite_calls, [], self.explain(rows, output))
        self.assertEqual(self.third_adds(), [], self.explain(rows, output))
        self.assertEqual(self.old_runs(), [], self.explain(rows, output))
        self.assertEqual(self.state(t), "done", self.explain(rows, output))

    def test_ac27_same_replacements_reapproved_no_run(self):
        """Повторное утверждение SPEC с тем же составом замен после записи — на мерже прогона нет.

        Сценарий: как в доказательстве с новыми видами; после выхода из
        `in_dev` записана ещё одна запись утверждения с той же строкой
        замены. `approve`: полный набор не звался, задача в `done`.

        Ловит мутацию: доказательство сверяет время или номер последней
        записи утверждения, а не состав замен — прогон на мерже.
        """
        t, rid, n, _code, reason, _detail = self.merged_ready()
        self.journal_replacements(t, {rid: n}, reason)
        self.to_merge_gate(t)
        rows, output = self.approve(t)
        self.assertEqual(self.suite_calls, [], self.explain(rows, output))
        self.assertEqual(self.state(t), "done", self.explain(rows, output))

    def test_ac27_changed_replacements_rerun_gate(self):
        """Смена содержимого утверждённых замен после записи (другой номер критерия) — на мерже гейт исполняется прогоном.

        Сценарий: как в доказательстве с новыми видами; после выхода из
        `in_dev` записано утверждение той же замены на другой критерий.
        `approve`: полный набор звался.

        Ловит мутацию: элементы «замена:…» не входят в отпечаток либо
        берутся только покрывшие находки по старой записи — доказательство
        совпадает, прогона нет.
        """
        t, rid, n, _code, reason, _detail = self.merged_ready()
        self.journal_replacements(t, {rid: n % 59 + 1}, reason)
        self.to_merge_gate(t)
        rows, output = self.approve(t)
        self.assertTrue(self.suite_calls, self.explain(rows, output))


# --------------------------------------------------------------- AC-30

class Ac30OutOfBoundsTest(PriorSandbox):

    def test_ac30_test_profile_no_outcome_gate(self):
        """У записи `test_profile` гейт исходов не создаётся и при правках, дающих находки новых видов в границе: нет ни прогона, ни записи журнала.

        Сценарий: учебный проект с `test_profile` (`report: junit-xml`);
        ветка правит файл тестов и добавляет файл кода со строкой
        `NODE_ENV`. `advance` из `in_dev`: полный набор не звался, `worktree
        add` гейта нет, ни одной записи с «по исходам»/«гейт исходов»,
        задача в `verifying`.

        Ловит мутацию: строгий режим, исключения в коде или прежние версии
        исполняются вне границы `in_outcome_bounds` — прогон, выписки и
        записи гейта у `test_profile`.
        """
        rel, names = self.py_rel(), [self.py_name()]
        project = self.junit_project({rel: names}, test_profile=True)
        t = self.task(project)
        rows, output = self.developer_advance(t, {
            rel: self.edited_py(names),
            f"lib/{self.word()}.py": "import os\nMODE = os.environ['NODE_ENV']\n"})
        self.assertEqual(self.suite_calls, [], self.explain(rows, output))
        self.assertEqual(self.gate_adds, [], self.explain(rows, output))
        self.assertEqual(self.gate_rows(rows), [], self.explain(rows, output))
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))


if __name__ == "__main__":
    unittest.main()
