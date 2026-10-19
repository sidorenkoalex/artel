"""Правило планки компонента: допустимые файлы, метка `AC-<n>: `, пометки `//`, маркер красноты в первом комментарии, `plank_rule` проекта.

Группа: долгоживущий
Красен до реализации: в `scripts/guard.py` нет `PlankRule`/`DEFAULT_PLANK_RULE`, у функций чтения планки нет параметра правила, в `orchestrator/project_profile.py` нет `plank_rule`, у `Profile` нет полей `tests`/`plank_layout` — тесты падают на отсутствующих именах; тексты и области чтения артели (AC-15) держат поведение main и зелёны с рождения.

Предмет — чистые функции разбора `scripts/guard.py` (статический текст
планки на диске временного каталога) и `project_profile.plank_rule` /
`project_profile.decide` (чтение записи `targets.yaml` песочницы). Связка
с git и FSM здесь не нужна: правило строится по записи проекта, разбор —
по текстам файлов. Песочница путей `config` — `tests.sandbox.TmpRootTest`
(запись артели в `targets.yaml` кладёт она сама); клон внешнего проекта —
`tests.sandbox.make_project_repo` (нужен `decide`).

Параметр правила у прежних функций `guard` SPEC называет только
«необязательным параметром», не именем: помощник `with_rule` находит
единственный новый необязательный параметр сигнатуры (при нескольких —
тот, в чьём имени есть `rule`) и передаёт правило по его имени.

Имена компонентов, файлов, номера критериев, тексты литералов и выбор
кавычек — из `random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`PlankRule`/`DEFAULT_PLANK_RULE`, разбор меток `AC-<n>: `, пометок `//` и
первого комментария, параметр правила у прежних функций `guard`,
`plank_rule` и поля `Profile.tests`/`plank_layout` — все методы файла
зелёные.
"""
import inspect
import random
import tempfile
import unittest
from pathlib import Path

from orchestrator import config, preflight, project_profile, targets
from scripts import guard
from tests.sandbox import TmpRootTest, artel_target_entry, make_project_repo

LETTERS = "abcdefghijkmnpqrstuvwxyz"

VITEST_COMMAND = ["node_modules/.bin/vitest", "run", "--config",
                  "vitest.config.js", "--allowOnly=false", "--update=false",
                  "--retry=0"]
PYTEST_COMMAND = ["python3", "-m", "pytest"]

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

# Прежние параметры функций `guard`, читающих планку (сигнатуры main).
OLD_PARAMS = {
    "scan_acceptance_tests": {"tdir"},
    "acceptance_traceability_errors": {"tdir", "extra_sources"},
    "scan_redness_markers": {"tdir"},
    "scan_id_format_samples": {"tdir"},
    "scan_indented_ac_markers": {"tdir"},
    "count_test_methods": {"tdir"},
    "is_extraneous_acceptance_test_file": {"rel_to_acceptance_tests"},
}

REDNESS_HEAD = "// Красен до реализации: фикстура песочницы.\n"
IMPORTS = "import { describe, expect, it, test } from 'vitest';\n"

# Тексты отказов артели — побайтно по main (требование 10).
DOCSTRING_PLACE = "в докстринге модуля"
FIRST_COMMENT_PLACE = "в первом комментарии файла"


def flow(items) -> str:
    return "[" + ", ".join(str(item) for item in items) + "]"


def block(fields: dict, indent: str) -> str:
    out = []
    for key, value in fields.items():
        if isinstance(value, (list, tuple)):
            out.append(f"{indent}{key}: {flow(value)}\n")
        else:
            out.append(f"{indent}{key}: {value}\n")
    return "".join(out)


def components_entry(name: str, comps: list) -> str:
    """Запись проекта с `components:`; `comps` — (имя, поля) по порядку."""
    text = ENTRY_HEAD.format(name=name) + "    components:\n"
    for comp, fields in comps:
        text += f"      {comp}:\n" + block(fields, "        ")
    return text


def profile_entry(name: str, fields: dict) -> str:
    return ENTRY_HEAD.format(name=name) + "    test_profile:\n" + \
        block(fields, "      ")


def spec_text(numbers) -> str:
    items = "\n".join(f"AC-{n}. Фикстурный критерий номер {n}." for n in
                      sorted(numbers))
    return ("---\ntask: FIXTURE\ntype: spec\nauthor_role: analyst\n"
            "status: ready\nschema_version: 5\n---\n\n# SPEC: фикстура\n\n"
            "## Требования\n\n1. Фикстура.\n\n## Критерии приёмки\n\n"
            f"{items}\n\n## Не входит\n\nНичего.\n")


def public_texts(obj) -> list:
    """Строки, которые объект несёт в публичных невызываемых атрибутах."""
    texts = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        value = getattr(obj, name, None)
        if callable(value):
            continue
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, (tuple, list)):
            texts.extend(str(item) for item in value)
        elif value is not None:
            texts.append(str(value))
    return texts


class PlankRuleSandbox(TmpRootTest):
    """`targets.yaml` песочницы с записью артели и учебными проектами;
    каталог планки — временный каталог с `SPEC.md` и `acceptance_tests/`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        self.entries: list = []
        self.write_targets()

    # ------------------------------------------------------------ входы

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def numbers(self, count: int) -> list:
        return self.rng.sample(range(1, 60), count)

    def literal(self, n: int, quote: str | None = None) -> str:
        quote = quote or self.rng.choice(["'", '"', "`"])
        return f"{quote}AC-{n}: кнопка {self.word()} работает{quote}"

    # ------------------------------------------------------------ записи

    def write_targets(self) -> None:
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry() + "".join(self.entries),
            encoding="utf-8")

    def add_entry(self, entry: str, name: str, clone: bool = False) -> None:
        self.entries.append(entry)
        self.write_targets()
        if clone:
            make_project_repo(name, origin=False)

    def vitest_fields(self, mask: str | None, report: str = "pult-vitest",
                      single: bool = True, prefix: str = "web") -> dict:
        fields = {"command": VITEST_COMMAND}
        if single:
            fields.update(long_lived_dir=f"{prefix}/src",
                          long_lived_name="<id>_<name>.test.js")
        else:
            fields["paths"] = [f"^{prefix}/"]
        fields.update(weakening_scope=[f"{prefix}/src/**"],
                      mutation_claim_scope=[f"{prefix}/src/**"],
                      report=report)
        if mask is not None:
            fields["tests"] = [mask]
        return fields

    def pytest_fields(self, single: bool = True, prefix: str = "back",
                      tests: bool = True) -> dict:
        fields = {"command": PYTEST_COMMAND}
        if single:
            fields.update(long_lived_dir="tests",
                          long_lived_name="test_<id>_<name>.py")
        else:
            fields["paths"] = [f"^{prefix}/"]
        fields.update(weakening_scope=["tests/**/*.py"],
                      mutation_claim_scope=["tests/test_*.py"],
                      report="junit-xml")
        if tests:
            fields["tests"] = [f"{prefix}/tests/**/test_*.py"]
        return fields

    def vitest_project(self, ext: str = "jsx") -> tuple:
        """(проект, компонент, маска, правило) — запись с одним компонентом
        `pult-vitest` и маской `tests`."""
        name, comp = f"p{self.word()}", f"v{self.word()}"
        mask = f"web/src/**/*.test.{ext}"
        self.add_entry(components_entry(name, [(comp, self.vitest_fields(mask))]),
                       name)
        return name, comp, mask, project_profile.plank_rule(name)

    # ------------------------------------------------------------ планка

    def plank(self, files: dict, numbers=()) -> Path:
        """Каталог задачи во временном каталоге: `SPEC.md` с критериями
        `numbers` и файлы `acceptance_tests/`."""
        tdir = Path(tempfile.mkdtemp(prefix="plank-", dir=self.root))
        (tdir / "SPEC.md").write_text(spec_text(numbers), encoding="utf-8")
        tests_dir = tdir / "acceptance_tests"
        tests_dir.mkdir()
        for rel, text in files.items():
            path = tests_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return tdir

    def with_rule(self, fn, *args, rule):
        """Вызов прежней функции `guard` с правилом — по имени её нового
        необязательного параметра."""
        old = OLD_PARAMS[fn.__name__]
        params = [p for p in inspect.signature(fn).parameters.values()
                  if p.name not in old and p.default is not inspect.Parameter.empty
                  and p.kind not in (inspect.Parameter.VAR_POSITIONAL,
                                     inspect.Parameter.VAR_KEYWORD)]
        if len(params) > 1:
            params = [p for p in params if "rule" in p.name.lower()]
        self.assertEqual(len(params), 1, self.note(
            f"у guard.{fn.__name__} нет единственного нового необязательного "
            f"параметра правила: {inspect.signature(fn)}"))
        return fn(*args, **{params[0].name: rule})

    def covered(self, tdir: Path, rule) -> set:
        tested, _markers = self.with_rule(guard.scan_acceptance_tests, tdir,
                                          rule=rule)
        return set(tested)

    def markers(self, tdir: Path, rule) -> dict:
        _tested, markers = self.with_rule(guard.scan_acceptance_tests, tdir,
                                          rule=rule)
        return dict(markers)

    def trace(self, tdir: Path, rule) -> list:
        return list(self.with_rule(guard.acceptance_traceability_errors, tdir,
                                   rule=rule))

    def jsx(self, body: str, head: str = REDNESS_HEAD) -> str:
        return head + IMPORTS + "\n" + body


class PlankFileRulesTest(PlankRuleSandbox):

    def test_ac1_vitest_test_file_allowed_and_covers_criterion(self):
        """Файл `a.test.jsx` компонента `pult-vitest` допустим и его `it('AC-n: …')` покрывает критерий.

        Сценарий: запись с одним компонентом `pult-vitest` (`tests:
        [web/src/**/*.test.jsx]`), SPEC с одним критерием AC-n (n
        случайный), в планке — `<имя>.test.jsx` с маркером красноты в
        первом комментарии и вызовом `it('AC-n: …')`. Файл не посторонний
        по правилу проекта (`is_extraneous_acceptance_test_file` с правилом,
        `component_of` — имя компонента), трассируемость по правилу без
        ошибок, критерий в покрытых.

        Ловит мутацию: правило проекта строится без последнего сегмента
        масок `tests` (файл `.test.jsx` — посторонний) либо разбор планки
        с правилом по-прежнему ищет только `def test_ac<n>_` — AC-n
        остаётся «нет теста и нет пометки».
        """
        _name, comp, _mask, rule = self.vitest_project()
        n = self.numbers(1)[0]
        fname = f"{self.word()}.test.jsx"
        tdir = self.plank({fname: self.jsx(
            f"it({self.literal(n)}, () => {{ expect(1).toBe(1); }});\n")}, [n])
        self.assertFalse(self.with_rule(guard.is_extraneous_acceptance_test_file,
                                        fname, rule=rule), self.note(fname))
        self.assertEqual(rule.component_of(fname), comp, self.note(fname))
        self.assertIn(n, self.covered(tdir, rule), self.note())
        self.assertEqual(self.trace(tdir, rule), [], self.note())

    def test_ac17_masks_and_is_test_of_vitest_rule(self):
        """`masks` отдаёт маски `tests` компонента, `is_test` различает тестовый файл и помощник.

        Сценарий: компонент `pult-vitest` с `tests:
        [frontend/src/**/*.test.jsx]` (имя случайное). `masks(<имя>)` —
        ровно эта маска; `is_test` истинно для `a.test.jsx` и файла со
        случайным именем `<w>.test.jsx`, ложно для `_util.jsx` и
        `_<w>.jsx`.

        Ловит мутацию: `is_test` отвечает «допустим ли файл» (помощник
        `_util.jsx` — тестовый) либо `masks` возвращает последние сегменты
        (`*.test.jsx`) вместо масок записи.
        """
        name, comp = f"p{self.word()}", f"v{self.word()}"
        mask = "frontend/src/**/*.test.jsx"
        self.add_entry(components_entry(
            name, [(comp, self.vitest_fields(mask, prefix="frontend"))]), name)
        rule = project_profile.plank_rule(name)
        self.assertEqual(list(rule.masks(comp)), [mask], self.note())
        for fname in ("a.test.jsx", f"{self.word()}.test.jsx"):
            with self.subTest(fname=fname):
                self.assertTrue(rule.is_test(fname), self.note(fname))
        for fname in ("_util.jsx", f"_{self.word()}.jsx"):
            with self.subTest(fname=fname):
                self.assertFalse(rule.is_test(fname), self.note(fname))


class LabelFormsTest(PlankRuleSandbox):

    def test_ac2_each_with_multiline_table_covers_criterion(self):
        """`test.each([...])('AC-n: %s', …)` с многострочной таблицей покрывает AC-n.

        Сценарий: таблица `.each` из случайного числа строк, каждая на
        своей строке файла; литерал — первый аргумент второго вызова, в
        случайных кавычках без `${`.

        Ловит мутацию: разбор `.each` ищет закрывающую скобку таблицы на
        той же строке (многострочная таблица не распознаётся) либо
        берёт литерал из первого вызова — AC-n не покрыт.
        """
        _name, _comp, _mask, rule = self.vitest_project()
        n = self.numbers(1)[0]
        rows = "".join(f"  [{self.rng.randint(0, 9)}, {self.rng.randint(0, 9)}],\n"
                       for _ in range(self.rng.randint(2, 5)))
        quote = self.rng.choice(["'", '"', "`"])
        body = (f"test.each([\n{rows}])({quote}AC-{n}: сумма %i и %i{quote}, "
                f"(a, b) => {{\n  expect(a + b).toBeGreaterThanOrEqual(0);\n}});\n")
        tdir = self.plank({f"{self.word()}.test.jsx": self.jsx(body)}, [n])
        self.assertEqual(self.covered(tdir, rule), {n}, self.note(body))
        self.assertEqual(self.trace(tdir, rule), [], self.note(body))

    def test_ac3_each_test_form_covers_its_own_criterion(self):
        """Каждая форма вызова требования 4 покрывает свой критерий, запрещённые формы — нет.

        Сценарий: по файлу на форму, номер критерия у каждой свой и
        случайный. Покрывают: `it`, `test`, `it.concurrent`,
        `test.sequential`, `it.concurrent.sequential`, `test.each(...)`,
        `it.concurrent.each(...)`, литерал в `'`, `"` и обратных кавычках,
        вызов с отступом внутри `describe`. Не покрывают: обратные кавычки
        с `${`, литерал не со строгого `AC-<n>: ` (ведущий пробел, `ac-`,
        нет пробела после двоеточия, нет двоеточия, префикс), вызов не в
        начале строки (`foo.it(...)`, `x = test(...)`).

        Ловит мутацию: регулярное выражение метки не заякорено на начало
        строки (покрывают `foo.it`/`x = test`), не отсекает `${` в
        обратных кавычках, не разрешает отступ либо цепочку
        `.concurrent`/`.sequential`, либо не требует пробела после
        `AC-<n>:` — расходится хотя бы одна форма.
        """
        _name, _comp, _mask, rule = self.vitest_project()
        word = self.word
        positive = {
            "it": lambda n: f"it({self.literal(n)}, () => {{}});\n",
            "test": lambda n: f"test({self.literal(n)}, () => {{}});\n",
            "it.concurrent": lambda n: f"it.concurrent({self.literal(n)}, async () => {{}});\n",
            "test.sequential": lambda n: f"test.sequential({self.literal(n)}, () => {{}});\n",
            "it.concurrent.sequential":
                lambda n: f"it.concurrent.sequential({self.literal(n)}, () => {{}});\n",
            "test.each": lambda n: f"test.each([[1], [2]])({self.literal(n)}, (x) => {{}});\n",
            "it.concurrent.each":
                lambda n: f"it.concurrent.each([1, 2])({self.literal(n)}, async (x) => {{}});\n",
            "одинарные кавычки": lambda n: f"it({self.literal(n, chr(39))}, () => {{}});\n",
            "двойные кавычки": lambda n: f"it({self.literal(n, chr(34))}, () => {{}});\n",
            "обратные кавычки": lambda n: f"it({self.literal(n, chr(96))}, () => {{}});\n",
            "с отступом": lambda n: (f"describe('группа {word()}', () => {{\n"
                                     f"{' ' * self.rng.choice([2, 4])}"
                                     f"it({self.literal(n)}, () => {{}});\n}});\n"),
        }
        negative = {
            "обратные кавычки с ${": lambda n: f"it(`AC-{n}: значение ${{x}}`, () => {{}});\n",
            "ведущий пробел": lambda n: f"it(' AC-{n}: {word()}', () => {{}});\n",
            "строчные ac-": lambda n: f"it('ac-{n}: {word()}', () => {{}});\n",
            "без пробела после двоеточия": lambda n: f"it('AC-{n}:{word()}', () => {{}});\n",
            "без двоеточия": lambda n: f"it('AC-{n} {word()}', () => {{}});\n",
            "префикс перед меткой": lambda n: f"it('x AC-{n}: {word()}', () => {{}});\n",
            "foo.it": lambda n: f"foo.it('AC-{n}: {word()}', () => {{}});\n",
            "x = test": lambda n: f"x = test('AC-{n}: {word()}', () => {{}});\n",
        }
        numbers = self.numbers(len(positive) + len(negative))
        for (form, make), n in zip(list(positive.items()) + list(negative.items()),
                                   numbers):
            body = make(n)
            tdir = self.plank({f"{word()}.test.jsx": self.jsx(body)}, [n])
            expected = {n} if form in positive else set()
            with self.subTest(form=form):
                self.assertEqual(self.covered(tdir, rule), expected,
                                 self.note(f"форма {form}:\n{body}"))

    def test_ac4_describe_label_does_not_cover_and_hint_names_it_form(self):
        """`describe('AC-n: …')` критерий не покрывает; подсказка «нет теста» называет форму `it('AC-n: …')`.

        Сценарий: в файле `describe('AC-n: …', …)` с вложенным `it` без
        метки; SPEC с критерием AC-n. Критерий не в покрытых; ошибка
        трассируемости по правилу для AC-n называет `it('AC-n:`.

        Ловит мутацию: метка ищется в любом вызове с литералом (`describe`
        покрывает критерий) либо подсказка «нет теста» у компонента с
        меткой `AC-<n>: ` остаётся прежней `def test_ac<n>_...`.
        """
        _name, _comp, _mask, rule = self.vitest_project()
        n = self.numbers(1)[0]
        body = (f"describe({self.literal(n)}, () => {{\n"
                f"  it('без метки {self.word()}', () => {{ expect(1).toBe(1); }});\n"
                f"}});\n")
        tdir = self.plank({f"{self.word()}.test.jsx": self.jsx(body)}, [n])
        self.assertNotIn(n, self.covered(tdir, rule), self.note(body))
        errors = [e for e in self.trace(tdir, rule) if e.startswith(f"AC-{n}:")]
        self.assertEqual(len(errors), 1, self.note(f"{body}\n{errors}"))
        self.assertIn(f"it('AC-{n}:", errors[0], self.note(errors[0]))

    def test_ac18_helper_label_does_not_cover_and_id_sample_found_in_jsx(self):
        """`it('AC-n: …')` в помощнике `_util.jsx` критерий не покрывает; образец формата идентификатора в `.jsx` — находка.

        Сценарий: помощник `_<w>.jsx` с вызовом `it('AC-n: …')` и строкой
        с образцом формата идентификатора; тестовый файл `<w>.test.jsx` без
        метки AC-n, тоже с образцом. AC-n не покрыт; `scan_id_format_samples`
        с правилом называет оба файла.

        Ловит мутацию: трассируемость по правилу читает все допустимые
        файлы, а не только тестовые (помощник покрывает AC-n), либо
        образец идентификатора ищется только в `*.py` — `.jsx` не
        проверяются.
        """
        _name, _comp, _mask, rule = self.vitest_project()
        n = self.numbers(1)[0]
        sample = "T%" + "03d"
        helper, test_file = f"_{self.word()}.jsx", f"{self.word()}.test.jsx"
        tdir = self.plank({
            helper: (f"// помощник\nexport const fmt = '{sample}';\n"
                     f"it({self.literal(n)}, () => {{}});\n"),
            test_file: self.jsx(f"const fmt = '{sample}';\n"
                                f"it('без метки', () => {{}});\n"),
        }, [n])
        self.assertNotIn(n, self.covered(tdir, rule), self.note())
        errors = self.with_rule(guard.scan_id_format_samples, tdir, rule=rule)
        for fname in (helper, test_file):
            with self.subTest(fname=fname):
                self.assertTrue(any(fname in e for e in errors),
                                self.note(f"{fname}: {errors}"))


class MarkersTest(PlankRuleSandbox):

    def test_ac5_slash_marker_and_indented_refusal(self):
        """`// AC-n: manual — причина` в начале строки — пометка; с отступом — отказ с префиксом `//`; `# AC-n` в `.jsx` — не пометка.

        Сценарий: три планки компонента `pult-vitest` с критерием AC-n:
        пометка `//` в начале строки (критерий помечен, ошибок нет);
        та же пометка с отступом внутри блока (отказ ровно текстом шаблона
        с `'// AC-n: manual'`); `# AC-n: manual — …` в `.jsx` (пометки
        нет — AC-n «нет теста»). У артели (без правила) пометка `#` с
        отступом в `test_*.py` — побайтно прежний текст с `#`.

        Ловит мутацию: синтаксис пометок не берётся из правила (`//` не
        видится, `#` в `.jsx` засчитывается) либо текст отказа отступа
        у компонента подставляет прежний префикс `#`.
        """
        _name, _comp, _mask, rule = self.vitest_project()
        n = self.numbers(1)[0]
        reason = f"причина {self.word()}"
        cases = {
            "в начале строки": f"// AC-{n}: manual — {reason}\n",
            "с отступом": (f"describe('группа', () => {{\n"
                           f"  // AC-{n}: manual — {reason}\n}});\n"),
            "решётка в jsx": f"# AC-{n}: manual — {reason}\n",
        }
        indented = (f"маркер '// AC-{n}: manual' с отступом не учитывается "
                    f"каталогом — вынеси в начало строки либо убери")
        for case, body in cases.items():
            tdir = self.plank({f"{self.word()}.test.jsx": self.jsx(body)}, [n])
            markers = self.markers(tdir, rule)
            errors = self.trace(tdir, rule)
            with self.subTest(case=case):
                if case == "в начале строки":
                    self.assertEqual(markers.get(n), ("manual", reason),
                                     self.note(body))
                    self.assertEqual(errors, [], self.note(body))
                elif case == "с отступом":
                    self.assertNotIn(n, markers, self.note(body))
                    self.assertTrue(any(e.endswith(indented) for e in errors),
                                    self.note(f"{body}\n{errors}"))
                else:
                    self.assertNotIn(n, markers, self.note(body))
                    self.assertTrue(any(e.startswith(f"AC-{n}: нет теста")
                                        for e in errors),
                                    self.note(f"{body}\n{errors}"))
        artel_text = ("import unittest\n\n\nclass T(unittest.TestCase):\n\n"
                      "    def test_x(self):\n"
                      f"        # AC-{n}: manual — {reason}\n"
                      "        self.assertTrue(True)\n")
        tdir = self.plank({f"test_{self.word()}.py": artel_text}, [n])
        artel_indented = (f"маркер '# AC-{n}: manual' с отступом не учитывается "
                          f"каталогом — вынеси в начало строки либо убери")
        errors = guard.acceptance_traceability_errors(tdir)
        self.assertTrue(any(e.endswith(artel_indented) for e in errors),
                        self.note(f"{errors}"))

    def test_ac10_redness_marker_in_first_comment(self):
        """Маркер красноты файла `*.test.jsx` ищется только в первом комментарии; отказ называет «в первом комментарии файла».

        Сценарий: тестовые файлы компонента `pult-vitest` с маркером —
        в одной строке `//`, во второй из подряд идущих строк `//`, в одном
        блоке `/* … */` (засчитываются); без маркера, с маркером после
        первой строки кода, с маркером во втором блоке `/* */`
        (отказ). Текст отказа — прежний текст артели для того же файла, где
        «в докстринге модуля» заменено на «в первом комментарии файла».

        Ловит мутацию: маркер ищется в любом комментарии файла (засчитан
        маркер после кода или во втором блоке) либо текст отказа у
        не-pytest файла остаётся «в докстринге модуля».
        """
        _name, _comp, _mask, rule = self.vitest_project()
        why = f"объяснение {self.word()}"
        code = "it('без метки', () => {});\n"
        marker = f"Красен до реализации: {why}"
        accepted = {
            "одна строка //": f"// {marker}\n{IMPORTS}{code}",
            "вторая строка //": f"// заголовок {self.word()}\n// {marker}\n{IMPORTS}{code}",
            "один блок /* */": f"/*\n * заголовок\n * {marker}\n */\n{IMPORTS}{code}",
        }
        refused = {
            "без маркера": f"// заголовок {self.word()}\n{IMPORTS}{code}",
            "после первой строки кода": f"{IMPORTS}// {marker}\n{code}",
            "во втором блоке /* */": (f"/* заголовок {self.word()} */\n"
                                      f"/* {marker} */\n{IMPORTS}{code}"),
        }
        artel_tdir = self.plank({"test_x.py": "import unittest\n"})
        artel_errors = guard.scan_redness_markers(artel_tdir)
        self.assertEqual(len(artel_errors), 1, self.note(f"{artel_errors}"))
        self.assertIn(DOCSTRING_PLACE, artel_errors[0])
        suffix = artel_errors[0].split(": ", 1)[1].replace(DOCSTRING_PLACE,
                                                           FIRST_COMMENT_PLACE)
        for case, text in {**accepted, **refused}.items():
            fname = f"{self.word()}.test.jsx"
            tdir = self.plank({fname: text})
            errors = self.with_rule(guard.scan_redness_markers, tdir, rule=rule)
            mine = [e for e in errors if fname in e]
            with self.subTest(case=case):
                if case in accepted:
                    self.assertEqual(mine, [], self.note(f"{case}:\n{text}"))
                else:
                    self.assertEqual(len(mine), 1, self.note(f"{case}:\n{text}\n{errors}"))
                    self.assertTrue(mine[0].endswith(suffix),
                                    self.note(f"{mine[0]}\n!=\n…{suffix}"))
                    self.assertNotIn(DOCSTRING_PLACE, mine[0])


class PlankRuleOfProjectTest(PlankRuleSandbox):

    def assert_default_membership(self, rule, label: str) -> None:
        """Принадлежность файлов правила совпадает с `DEFAULT_PLANK_RULE`."""
        names = ["test_a.py", f"test_{self.word()}.py", f"_{self.word()}.py",
                 "markers.py", "__init__.py", "a.test.jsx", "_util.jsx",
                 "vitest.config.js", "conftest.py", "_pult.py", "PASSPORT.md",
                 "sub/test_a.py", f"{self.word()}.md", "long_lived.sha256.txt"]
        default = guard.DEFAULT_PLANK_RULE
        for name in names:
            with self.subTest(label=label, name=name):
                self.assertEqual(rule.component_of(name) is None,
                                 default.component_of(name) is None,
                                 self.note(f"{label}: {name}"))

    def test_ac9_default_rule_cases(self):
        """`plank_rule` отдаёт `DEFAULT_PLANK_RULE` артели, записи `test_profile`, непрочитанной записи и компоненту с pytest.

        Сценарий: артель — при годном `targets.yaml` и при испорченном
        (запись не читается); внешний проект с `test_profile`; внешний
        проект, чья запись не годна (неизвестное значение `report`), и
        проект, которого нет в `targets.yaml`, — без исключения наружу;
        единственный компонент `junit-xml` с командой `python3 -m pytest`
        и маской `tests`.

        Ловит мутацию: у артели правило строится по записи (испорченный
        `targets.yaml` роняет `TargetsError`), `TargetsError` внешней
        записи выходит наружу, либо компонент с pytest-командой и `tests`
        получает правило по маскам.
        """
        default = guard.DEFAULT_PLANK_RULE
        self.assertEqual(project_profile.plank_rule(config.DEFAULT_TARGET),
                         default, self.note("артель"))
        prof_name = f"p{self.word()}"
        self.add_entry(profile_entry(prof_name, {
            "command": PYTEST_COMMAND, "long_lived_dir": "tests",
            "long_lived_name": "test_<id>_<name>.py",
            "weakening_scope": ["tests/**/*.py"],
            "mutation_claim_scope": ["tests/test_*.py"]}), prof_name)
        pytest_name, pytest_comp = f"p{self.word()}", f"j{self.word()}"
        self.add_entry(components_entry(pytest_name, [
            (pytest_comp, self.pytest_fields())]), pytest_name)
        for label, name in (("test_profile", prof_name),
                            ("компонент pytest", pytest_name),
                            ("не объявлен", f"p{self.word()}")):
            with self.subTest(label=label):
                try:
                    rule = project_profile.plank_rule(name)
                except targets.TargetsError as exc:
                    self.fail(self.note(f"{label}: TargetsError наружу: {exc}"))
                self.assertEqual(rule, default, self.note(label))
        broken = f"p{self.word()}"
        self.add_entry(components_entry(broken, [
            (f"v{self.word()}", self.vitest_fields(
                "web/src/**/*.test.jsx", report=f"bogus-{self.word()}"))]), broken)
        for label, name in (("непрочитанная запись", broken),
                            ("артель при непрочитанном targets.yaml",
                             config.DEFAULT_TARGET)):
            with self.subTest(label=label):
                try:
                    rule = project_profile.plank_rule(name)
                except targets.TargetsError as exc:
                    self.fail(self.note(f"{label}: TargetsError наружу: {exc}"))
                self.assertEqual(rule, default, self.note(label))
        config.TARGETS.write_text("это не yaml: [", encoding="utf-8")
        self.assertEqual(project_profile.plank_rule(config.DEFAULT_TARGET),
                         default, self.note("артель без читаемого targets.yaml"))

    def test_ac9_multi_component_membership_and_always_stray(self):
        """Правило записи из нескольких компонентов строится без отказа: файл — первому подходящему компоненту; посторонние — всегда.

        Сценарий: запись из двух компонентов — `junit-xml` на pytest и
        `pult-vitest` с `tests` (порядок записи случайный): `a.test.jsx` и
        `_util.jsx` — компоненту `pult-vitest`, `test_a.py` и `_h.py` —
        компоненту pytest. Вторая запись — два компонента `pult-vitest`,
        оба с масками `*.test.jsx` в разных каталогах: файл — первому в
        порядке записи (имена случайные, первый не обязательно меньше
        лексикографически). При любом правиле (обе записи и
        `DEFAULT_PLANK_RULE`) `_pult.py`, `PASSPORT.md`, `conftest.py` и
        вложенный путь — посторонние, `long_lived.sha256.txt` допустим.

        Ловит мутацию: компоненты перебираются в отсортированном порядке
        (не в порядке записи), правило записи из нескольких компонентов
        идёт через `decide` и отказывает (правило-умолчание), либо
        `conftest.py`/`_pult.py` пропускаются правилом компонента.
        """
        name, junit_comp, vite_comp = f"p{self.word()}", f"j{self.word()}", \
            f"v{self.word()}"
        comps = [(junit_comp, self.pytest_fields(single=False)),
                 (vite_comp, self.vitest_fields("front/src/**/*.test.jsx",
                                                single=False, prefix="front"))]
        self.rng.shuffle(comps)
        self.add_entry(components_entry(name, comps), name)
        rule = project_profile.plank_rule(name)
        expected = {"a.test.jsx": vite_comp, "_util.jsx": vite_comp,
                    f"{self.word()}.test.jsx": vite_comp,
                    "test_a.py": junit_comp, f"_{self.word()}.py": junit_comp}
        for fname, comp in expected.items():
            with self.subTest(fname=fname):
                self.assertEqual(rule.component_of(fname), comp,
                                 self.note(f"{fname}; порядок {comps}"))
        twin = f"p{self.word()}"
        first, second = f"v{self.word()}", f"v{self.word()}"
        if first < second:
            first, second = second, first
        self.add_entry(components_entry(twin, [
            (first, self.vitest_fields("a/src/**/*.test.jsx", single=False,
                                       prefix="a")),
            (second, self.vitest_fields("b/src/**/*.test.jsx", single=False,
                                        prefix="b"))]), twin)
        twin_rule = project_profile.plank_rule(twin)
        self.assertEqual(twin_rule.component_of("x.test.jsx"), first,
                         self.note(f"первый {first}, второй {second}"))
        for label, any_rule in (("два компонента", rule),
                                ("два pult-vitest", twin_rule),
                                ("умолчание", guard.DEFAULT_PLANK_RULE)):
            for stray in ("_pult.py", "PASSPORT.md", "conftest.py",
                          "sub/a.test.jsx", f"{self.word()}/test_a.py"):
                with self.subTest(label=label, stray=stray):
                    self.assertIsNone(any_rule.component_of(stray),
                                      self.note(f"{label}: {stray}"))
            with self.subTest(label=label, name="long_lived.sha256.txt"):
                self.assertIsNotNone(any_rule.component_of("long_lived.sha256.txt"),
                                     self.note(label))

    def test_ac7_junit_pytest_component_same_as_artel(self):
        """Компонент `junit-xml` на pytest: правило — умолчание, `conftest.py` посторонний, разбор как у артели.

        Сценарий: единственный компонент `junit-xml` с командой
        `python3 -m pytest` и маской `tests`. Правило равно
        `DEFAULT_PLANK_RULE`; `conftest.py` посторонний по
        `is_extraneous_acceptance_test_file` с правилом; разбор планки из
        `test_*.py` со случайными методами `test_ac<n>_`, пометками `#` и
        файла `.test.jsx` с `it('AC-m: …')` с этим правилом совпадает с
        разбором без правила.

        Ловит мутацию: компонент с pytest-командой получает правило по
        маскам `tests` (`test_a.py` вне маски `back/tests/**/test_*.py` по
        последнему сегменту — посторонний, `.jsx` читается), либо
        `conftest.py` проходит.
        """
        name, comp = f"p{self.word()}", f"j{self.word()}"
        self.add_entry(components_entry(name, [(comp, self.pytest_fields())]),
                       name)
        rule = project_profile.plank_rule(name)
        self.assertEqual(rule, guard.DEFAULT_PLANK_RULE, self.note())
        self.assertTrue(self.with_rule(guard.is_extraneous_acceptance_test_file,
                                       "conftest.py", rule=rule), self.note())
        a, b, m = self.numbers(3)
        reason = f"причина {self.word()}"
        py = ("import unittest\n\n\nclass T(unittest.TestCase):\n\n"
              f"    def test_ac{a}_{self.word()}(self):\n        pass\n")
        tdir = self.plank({f"test_{self.word()}.py": py + f"# AC-{b}: manual — {reason}\n",
                           f"{self.word()}.test.jsx": self.jsx(
                               f"it({self.literal(m)}, () => {{}});\n")}, [a, b, m])
        with_rule = self.with_rule(guard.scan_acceptance_tests, tdir, rule=rule)
        self.assertEqual(tuple(with_rule), tuple(guard.scan_acceptance_tests(tdir)),
                         self.note())
        self.assertEqual(self.trace(tdir, rule),
                         guard.acceptance_traceability_errors(tdir), self.note())

    def test_ac8_vitest_without_tests_refusal_with_default_rule(self):
        """Компонент `report: pult-vitest` без `tests` даёт отказ построения: правило-умолчание с причиной.

        Сценарий: компонент `pult-vitest` без `tests` со случайным именем
        (не `pult-vitest`) — единственный в записи и второй после
        компонента pytest. `plank_rule` возвращает правило с
        принадлежностью файлов `DEFAULT_PLANK_RULE` (`test_a.py` допустим,
        `a.test.jsx` посторонний), а правило несёт текст «у компонента
        <имя> нет tests — допустимые файлы планки не определены».

        Ловит мутацию: признак отказа берётся по имени компонента
        (`pult-vitest`), а не по полю `report` — компонент с другим именем
        без отказа; либо причина отказа теряется (правило-умолчание без
        текста).
        """
        single, comp = f"p{self.word()}", f"c{self.word()}"
        self.add_entry(components_entry(single, [
            (comp, self.vitest_fields(None))]), single)
        multi, junit_comp, comp2 = f"p{self.word()}", f"j{self.word()}", \
            f"c{self.word()}"
        self.add_entry(components_entry(multi, [
            (junit_comp, self.pytest_fields(single=False)),
            (comp2, self.vitest_fields(None, single=False, prefix="front"))]), multi)
        for label, name, bad in (("единственный", single, comp),
                                 ("второй", multi, comp2)):
            rule = project_profile.plank_rule(name)
            reason = (f"у компонента {bad} нет tests — допустимые файлы "
                      f"планки не определены")
            with self.subTest(label=label):
                self.assert_default_membership(rule, label)
                self.assertTrue(any(reason in text for text in public_texts(rule)),
                                self.note(f"{label}: причины нет в правиле "
                                          f"{public_texts(rule)}"))

    def test_ac16_profile_carries_tests_and_plank_layout_outside_equality(self):
        """`Profile.tests` и `Profile.plank_layout` заполнены полями компонента и не участвуют в сравнении профилей.

        Сценарий: проект с `test_profile` и проект с единственным
        компонентом с теми же подполями плюс `tests` и `plank_layout`
        (значения случайные). Профиль `decide` второго и его профиль
        `component_profiles` несут эти значения; профили `decide` двух
        проектов равны.

        Ловит мутацию: поля добавлены в `Profile` со сравнением (профили
        расходятся) либо `_with_component_fields` их не заполняет
        (пустые значения у профиля компонента).
        """
        sub = {"command": PYTEST_COMMAND, "long_lived_dir": "tests",
               "long_lived_name": "test_<id>_<name>.py",
               "weakening_scope": ["tests/**/*.py"],
               "mutation_claim_scope": ["tests/test_*.py"]}
        mask = f"{self.word()}/**/test_*.py"
        layout = f"{self.word()}/plank_<id>"
        prof_name, comp_name, comp = f"p{self.word()}", f"p{self.word()}", \
            f"c{self.word()}"
        self.add_entry(profile_entry(prof_name, sub), prof_name, clone=True)
        self.add_entry(components_entry(comp_name, [
            (comp, {**sub, "tests": [mask], "plank_layout": layout})]),
            comp_name, clone=True)
        prof = project_profile.decide(prof_name).profile
        mine = project_profile.decide(comp_name).profile
        self.assertIsNotNone(prof, self.note(project_profile.decide(prof_name).refusal))
        self.assertIsNotNone(mine, self.note(project_profile.decide(comp_name).refusal))
        listed = project_profile.component_profiles(comp_name)
        for label, profile in (("decide", mine), ("component_profiles", listed[0])):
            with self.subTest(label=label):
                self.assertEqual(list(profile.tests), [mask], self.note(label))
                self.assertEqual(profile.plank_layout, layout, self.note(label))
        self.assertEqual(prof, mine, self.note("профили test_profile и компонента"))


class ArtelUnchangedTest(PlankRuleSandbox):

    def test_ac15_texts_and_compositions_unchanged(self):
        """Тексты и составы требования 10 у артели — побайтно прежние.

        Сценарий: константы отказов и состав фильтров предпроверки
        сверяются с литералами main; отказы трассируемости артели на
        планке, дающей все пять видов отказа (номера случайные), равны
        списку прежних текстов; отказ маркера красноты — прежний текст.

        Ловит мутацию: правка шаблона отказа ради префикса компонента
        задевает артель (меняется `#` в подсказке «нет теста» или текст
        отказа маркера красноты), либо в `INPUT_FILTERS` добавлен фильтр.
        """
        self.assertEqual(guard.EXTRANEOUS_ACCEPTANCE_FILE_REASON,
                         "посторонний файл в каталоге планки")
        self.assertEqual(guard.RESERVED_PLANK_HELPER_HINT,
                         "имя занято помощником пульта")
        self.assertEqual(guard.INDENTED_AC_MARKER_REASON_TMPL,
                         "маркер '# AC-{n}: {kind}' с отступом не учитывается "
                         "каталогом — вынеси в начало строки либо убери")
        self.assertEqual(preflight.INPUT_FILTERS,
                         (guard.is_extraneous_acceptance_test_file,))
        from orchestrator import checkpoint
        self.assertEqual(checkpoint.STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX,
                         "в каталоге планки посторонние файлы: ")
        free, ghost, empty, wrong_ci, foreign = sorted(self.numbers(5))
        py = ("\"\"\"Планка.\n\nКрасен до реализации: фикстура.\n\"\"\"\n"
              "import unittest\n\n\nclass T(unittest.TestCase):\n\n"
              f"    def test_ac{foreign}_{self.word()}(self):\n        pass\n\n"
              f"# AC-{ghost}: manual — нет такого\n"
              f"# AC-{empty}: skip\n"
              f"# AC-{wrong_ci}: ci — проверит CI\n")
        tdir = self.plank({"test_a.py": py}, [free, empty, wrong_ci])
        expected = [
            f"AC-{free}: нет теста и нет пометки manual/skip/escalate — "
            f"добавь тестовый метод 'def test_ac{free}_...' в "
            f"acceptance_tests/, либо пометку "
            f"'# AC-{free}: manual|skip|escalate — причина' в том же каталоге",
            f"AC-{empty}: пометка skip без причины — впиши причину после "
            f"тире в той же строке, например '# AC-{empty}: skip — <причина>'",
            f"AC-{ghost}: пометка на критерий, которого нет в SPEC — убери "
            f"эту пометку либо добавь критерий AC-{ghost} в раздел «Критерии "
            f"приёмки» SPEC",
            f"AC-{wrong_ci}: пометка ci на критерий, формулировка которого не "
            f"про существующие тесты (нет ни одного из ключевых слов "
            f"«существующ», tests/, «зелён», «не ослаб») — замени пометку на "
            f"'manual' либо перефразируй критерий",
            f"AC-{foreign}: тест на критерий, которого нет в SPEC (SPEC T023, "
            f"требование 3 — только из критериев) — переименуй тест на "
            f"существующий AC-номер либо добавь критерий AC-{foreign} в раздел "
            f"«Критерии приёмки» SPEC",
        ]
        errors = guard.acceptance_traceability_errors(tdir)
        self.assertEqual(sorted(errors), sorted(expected), self.note())
        bare = self.plank({"test_b.py": "import unittest\n"})
        label = str(bare / "acceptance_tests" / "test_b.py")
        self.assertEqual(guard.scan_redness_markers(bare), [
            f"{label}: нет маркера «Красен до реализации:» или «Зелёный "
            f"с рождения:» с непустым объяснением на той же строке сразу "
            f"после двоеточия в докстринге модуля — допиши объяснение "
            f"сразу после двоеточия на той же строке, например «Красен "
            f"до реализации: <причина>» (перенос объяснения на "
            f"следующую строку не считается заполненным маркером)"], self.note())

    def test_ac15_disk_read_areas_unchanged(self):
        """Области чтения диска у артели прежние: разбор — `test_*.py`, счёт методов и образец идентификатора — все `*.py`.

        Сценарий: в планке `test_a.py` с методом `test_ac<a>_`,
        вспомогательный `_<w>.py` с методом `test_ac<b>_` и пометкой `#`,
        вложенный `sub/<w>.py` с методом, `.jsx` с `it('AC-c: …')`; образец
        идентификатора — в `_<w>.py` и в `.jsx`. Без правила: покрыт только
        AC-a (помощник и `.jsx` не читаются разбором), счёт методов —
        методы всех `*.py` вложенно, образец найден в `_<w>.py` и не
        найден в `.jsx`.

        Ловит мутацию: функции без правила переведены на правило-умолчание
        с его фильтром (`component_of`) — счёт методов перестаёт видеть
        вложенный `sub/<w>.py`, либо разбор начинает читать `_*.py`/`.jsx`.
        """
        a, b, c = self.numbers(3)
        sample = "T%" + "03d"
        helper, nested = f"_{self.word()}.py", f"sub/{self.word()}.py"
        methods = self.rng.randint(1, 4)
        files = {
            "test_a.py": ("import unittest\n\n\nclass T(unittest.TestCase):\n\n"
                          f"    def test_ac{a}_x(self):\n        pass\n"),
            helper: (f"FMT = '{sample}'\n\n# AC-{b}: manual — помощник\n\n\n"
                     f"def test_ac{b}_helper():\n    pass\n"),
            nested: "".join(f"def test_n{i}():\n    pass\n\n\n"
                            for i in range(methods)),
            f"{self.word()}.test.jsx": (f"const fmt = '{sample}';\n"
                                       f"it({self.literal(c)}, () => {{}});\n"),
        }
        tdir = self.plank(files, [a, b, c])
        tested, markers = guard.scan_acceptance_tests(tdir)
        self.assertEqual(set(tested), {a}, self.note())
        self.assertNotIn(b, markers, self.note())
        self.assertEqual(guard.count_test_methods(tdir), 2 + methods, self.note())
        samples = guard.scan_id_format_samples(tdir)
        self.assertTrue(any(helper in e for e in samples), self.note(f"{samples}"))
        self.assertFalse(any(".jsx" in e for e in samples), self.note(f"{samples}"))


if __name__ == "__main__":
    unittest.main()
