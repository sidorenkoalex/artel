"""Гейт неослабления видит смену аргументов `parametrize` у метода с прежним именем; литерал `parametrize` не объявляется в «Меняемом поведении» (AC-4..AC-7).

Группа: долгоживущий
Красен до реализации: узел сравнения сверяет утверждения и маркеры пропуска, но не декораторы параметризации, `pytestmark` с `parametrize` и константы модуля, на которые они ссылаются, — поэтому удаление варианта, смена значений и имён аргументов и `pytest.param(..., marks=pytest.mark.skip)` у метода с прежним именем не дают ни отказа перехода, ни находки `uncovered`, ни записи в журнале и строки ревью-пакета (AC-4, AC-5, AC-6); добавленный вариант проходит молча, без записи и строки (AC-5); AC-7 держит сегодняшнее правило `guard.method_literal_keys` и зелён с рождения.

Связка «профиль проекта задачи — узел сравнения гейта неослабления —
git»: настоящий git песочницы (`tests.sandbox.RealGitSandbox`) — клон
артели с bare `origin` и клон учебного внешнего проекта
(`tests.sandbox.make_project_repo`) с профилем `runner: pytest-own`,
`workdir: backend`, `weakening_scope: [backend/tests/**/*.py]`. База
файлов — коммит основной ветки клона и его `origin`, голова — коммит
ветки задачи в рабочей копии (`workspace.ensure`); документы задачи —
автокоммитом шага (`checkpoint.commit_step_artifacts`). Канал находки —
тот же, что у изменённого утверждения без объявления: рубеж `in_dev →
verifying` — публичной командой `fsm.cmd_advance` (запись отказа
`test_integrity.TEST_INTEGRITY_REFUSAL_ACTION`); `test_integrity.uncovered`
(находки без мандата и записи журнала прохода) и
`test_integrity.review_lines` (раздел ревью-пакета) — с областью профиля
проекта задачи и веткой документов, как их зовут пульт и ревью. Мандат
Оператора — публичной командой `answer.cmd_answer`; объявленная смена
литерала — запись approve гейта SPEC
`test_integrity.DECLARED_CHANGE_ACTION` в журнале задачи (раздел
«Меняемое поведение» принимает только пути `tests/…`, поэтому объявленная
смена — у артели). AC-7 — модульный тест `guard.method_literal_keys` и
`guard.behavior_change_refusals` без песочницы.

Провалидировано временным стабом реализации (удалён, не закоммичен):
сравнение текстов вариантов `parametrize` метода во всех формах (декоратор
метода и класса, `pytestmark` модуля и класса, константа модуля) с
находкой на удаление/изменение/марку пропуска и записью журнала и строкой
ревью-пакета на добавленный вариант — все методы зелёные.

Имена файлов, классов, методов, вариантов и значения литералов —
случайные при каждом запуске; зерно печатается и входит в текст каждого
провала.
"""
import contextlib
import io
import os
import random
import re
import unittest
from unittest import mock

from orchestrator import (answer, artifact_source, checkpoint, config, fsm,
                          github_adapter, idgen, project_profile, store,
                          workspace)
from orchestrator.advance_gates import mandate, test_integrity
from scripts import guard
from tests.sandbox import (RealGitSandbox, artel_target_entry,
                           make_project_repo)

ARTEL = config.DEFAULT_TARGET
BACKEND = "uchebnyybackend"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
SEP = "::"
WEAKENING = mandate.TEST_WEAKENING_MANDATE_MARKER
INDEPENDENT_CHECK = "Независимая проверка: матрица подтверждена Оператором"
MATRIX_HEADERS = ("Что меняется", "Какое свойство сейчас держит",
                  "Остаётся ли свойство после изменения",
                  "Чем покрыто после", "Решение")

# (каталог тестов, зоны задачи) по target'у.
STACKS = {BACKEND: ("backend/tests", "backend/"), ARTEL: ("tests", "tests/")}

EXT_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: backend/tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [backend/tests/**/*.py]
      mutation_claim_scope: [backend/tests/**/test_*.py]
      report: junit-xml
      install: []
      runner: pytest-own
      workdir: backend
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура параметризации

## Подход
Фикстура сценария.

## Шаги
1. Правка.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Нет.
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: фикстура параметризации

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

DOCSTRING = ['"""Фикстура сценария.', "",
             "Ловит мутацию: фикстура песочницы.", '"""']


def method(name: str, args: str, assertion: str, decorators=()) -> str:
    """Тестовый метод класса в стиле pytest: декораторы, аргументы
    варианта `args` (пусто — без них), докстринг с заявкой мутации (её
    требует соседний гейт) и одно утверждение."""
    lines = [f"    @{d}" for d in decorators]
    signature = f"self, {args}" if args else "self"
    lines.append(f"    def {name}({signature}):")
    lines += [f"        {line}" if line else "" for line in DOCSTRING]
    lines.append(f"        {assertion}")
    return "\n".join(lines) + "\n"


def klass(name: str, methods, decorators=(), body: str = "") -> str:
    """Класс в стиле pytest: декораторы класса, строка тела `body`
    (например `pytestmark = …`) и методы."""
    lines = [f"@{d}" for d in decorators] + [f"class {name}:", ""]
    if body:
        lines += [f"    {body}", ""]
    return "\n".join(lines) + "\n" + "\n".join(methods)


def module(prelude: str, *classes: str) -> str:
    head = "import pytest\n\n"
    if prelude:
        head += f"{prelude.rstrip()}\n"
    return head + "\n\n" + "\n\n".join(classes)


def values_text(values) -> str:
    """Текст списка вариантов: элемент — литерал либо готовый текст
    `pytest.param(…)` (обёрнут в `Raw`)."""
    return "[" + ", ".join(v.text if isinstance(v, Raw) else repr(v)
                           for v in values) + "]"


class Raw:
    """Элемент списка вариантов, вставляемый в текст как есть."""

    def __init__(self, text: str):
        self.text = text


def skip_param(value) -> Raw:
    return Raw(f"pytest.param({value!r}, marks=pytest.mark.skip)")


def parametrize(argnames: str, values) -> str:
    return f"pytest.mark.parametrize({argnames!r}, {values_text(values)})"


def mentions(text: str, name: str) -> bool:
    """`text` называет квалифицированное имя `name` — не как префикс
    более длинного имени."""
    return re.search(rf"{re.escape(name)}(?![\w])", text) is not None


class ParametrizeGateSandbox(RealGitSandbox):
    """Клон артели и клон учебного бэкенд-проекта; задачи в `in_dev` с
    базой на основной ветке и головой в ветке задачи."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        for patcher in (mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                        mock.patch.object(github_adapter, "ensure_draft_mr",
                                          lambda conn, task_id, t: None),
                        mock.patch("orchestrator.doctor.preflight_checks",
                                   lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        self.clones = {ARTEL: self.root, BACKEND: make_project_repo(BACKEND)}
        self.conn = store.db()
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + EXT_ENTRY.format(name=BACKEND, base=config.MAIN_BRANCH),
            encoding="utf-8")

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        while True:
            found = "".join(self.rng.choice(ALPHABET) for _ in range(size))
            if found not in self.used:
                self.used.add(found)
                return found

    def name(self, prefix: str = "test_") -> str:
        return f"{prefix}{self.word()}"

    def klass_name(self) -> str:
        return f"Test{self.word().capitalize()}"

    def literal(self) -> int:
        return self.rng.randrange(10_000, 100_000)

    def values(self, count: int) -> list:
        return [self.word(5) for _ in range(count)]

    def file_path(self, target: str) -> str:
        subdirs = "".join(f"{self.word(4)}/"
                          for _ in range(self.rng.randrange(0, 2)))
        return f"{STACKS[target][0]}/{subdirs}test_{self.word()}.py"

    def assertion(self, value=None) -> str:
        return f"assert ready() == {self.literal() if value is None else value}"

    def why(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # ------------------------------------------------------- задача и ветка

    def write(self, root, files: dict) -> None:
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def new_task(self, target: str, base: dict, head: dict) -> str:
        """Задача `target` в `in_dev`: `base` — на основной ветке клона и в
        его `origin`, `head` — коммит ветки задачи поверх неё (файл вне
        `head` не меняется); PLAN.md/SPEC.md — в ссылке документов."""
        clone = self.clones[target]
        self.write(clone, base)
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "база тестов")
        self.git("-C", str(clone), "push", "-q", "origin", config.MAIN_BRANCH)
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-parametrizatsiya"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "in_dev", branch, target, config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task_id, zones=STACKS[target][1])
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.why(f"рабочая копия не заведена: {error}"))
        self.write(wt, head)
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: голова")
        docs = config.PROJECTS / target / "tasks" / task_id
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "PLAN.md").write_text(PLAN_TEXT.format(task=task_id),
                                      encoding="utf-8")
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=task_id),
                                      encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            checkpoint.commit_step_artifacts(self.conn, task_id, "developer")
        return task_id

    def declare(self, task_id: str, items) -> None:
        """Запись approve гейта SPEC «объявлена смена поведения тестов»:
        `items` — (путь, квалифицированное имя, было, стало)."""
        lines = [f"- `{path}{SEP}{name}`: `{old}` → `{new}` (требование 1)"
                 for path, name, old, new in items]
        store.journal(self.conn, task_id, "fsm",
                      test_integrity.DECLARED_CHANGE_ACTION, "\n".join(lines))

    # ---------------------------------------------------------- входы узла

    def entry_args(self, task_id: str) -> tuple:
        """(строка задачи, ветка документов, область профиля задачи) — те
        же значения, что передают пульт и ревью."""
        decision = project_profile.for_task(self.conn, task_id)
        self.assertIsNotNone(decision.profile, self.why(
            f"фикстура: профиль задачи не прочитан: {decision}"))
        docs, _foreign = artifact_source.resolve(self.conn, task_id)
        return (store.get_task(self.conn, task_id), docs,
                decision.profile.in_weakening_scope)

    def channel(self, task_id: str) -> tuple:
        """(находки `uncovered` без мандата, записи журнала, сделанные этим
        вызовом, строки раздела ревью-пакета)."""
        t, docs, scope = self.entry_args(task_id)
        rows = store.task_steps(self.conn, task_id)
        before = rows[-1]["id"] if rows else 0
        rest, git_detail = test_integrity.uncovered(
            self.conn, task_id, t["branch"], docs, scope=scope)
        self.assertEqual("", git_detail, self.why(f"сбой git: {git_detail}"))
        journal = "\n".join(f"{r['action']} | {r['detail'] or ''}"
                            for r in store.task_steps(self.conn, task_id)
                            if r["id"] > before)
        lines, unobserved, git_detail = test_integrity.review_lines(
            self.conn, task_id, t["branch"], docs, scope=scope)
        self.assertEqual("", git_detail, self.why(f"сбой git: {git_detail}"))
        return rest, journal, "\n".join(lines + unobserved)

    def advance(self, task_id: str) -> tuple:
        """(записи отказа гейта неослабления, все новые записи и вывод)."""
        rows = store.task_steps(self.conn, task_id)
        before = rows[-1]["id"] if rows else 0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(task_id)
            except SystemExit as exc:
                buf.write(f"\n{exc.code}")
        new = [r for r in store.task_steps(self.conn, task_id)
               if r["id"] > before]
        text = "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in new) + "\n--- вывод:\n" + buf.getvalue()
        refusals = "\n".join(
            r["detail"] or "" for r in new
            if r["action"] == test_integrity.TEST_INTEGRITY_REFUSAL_ACTION)
        return refusals, text

    def weakening_answer(self, task_id: str, element: str,
                         covered_by: str) -> None:
        """`answer` Оператора с мандатом ослабления на `element`, строкой
        независимой проверки и годной по форме матрицей."""
        row = (f"`{element}`", "фикстура сценария", "да", covered_by, "ок")
        text = (f"{WEAKENING} {element}\n\n"
                f"Основание: решение Оператора ({self.seed}).\n\n"
                f"{INDEPENDENT_CHECK}\n\n"
                "## Матрица неослабления\n\n"
                "| " + " | ".join(MATRIX_HEADERS) + " |\n"
                + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
                + "| " + " | ".join(row) + " |\n")
        path = self.root / ".artel" / f"vvod-{self.rng.randrange(1 << 30)}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        failed = ""
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                answer.cmd_answer(task_id, str(path))
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    failed = f"\n{exc.code}"
        self.assertEqual("", failed, self.why(
            f"фикстура: answer отказала мандату {element}:\n"
            f"{buf.getvalue()}{failed}"))

    # ------------------------------------------------------------ проверки

    @staticmethod
    def found(rest, path: str, name: str) -> bool:
        """Среди находок `rest` есть находка о методе `name` файла `path`."""
        return any(f.name == name and path in (f.path, f.alias) for f in rest)

    @staticmethod
    def rest_text(rest) -> str:
        return "\n".join(f"{f.path}{SEP}{f.name} — {f.line}" for f in rest)

    # ------------------------------------------------------- сценарии

    def changed_variants(self, target: str) -> tuple:
        """Файл с методами базы, у которых в ветке меняются аргументы
        `parametrize` (утверждения прежние): (база, голова, путь, класс,
        {случай: метод}, контрольный метод без изменений)."""
        path, cls = self.file_path(target), self.klass_name()
        three, two, kept = self.values(3), self.values(2), self.values(2)
        unchanged = self.values(2)
        pairs = [(v, self.literal()) for v in self.values(2)]
        changed_pairs = [pairs[0], (pairs[1][0], pairs[1][1] + 1)]
        names = {case: self.name() for case in (
            "удаление варианта", "смена значений варианта",
            "смена имени аргумента", "марка пропуска на варианте")}
        control = self.name()
        asserts = {n: self.assertion() for n in list(names.values()) + [control]}

        def body(head: bool) -> str:
            methods = [
                method(names["удаление варианта"], "k",
                       asserts[names["удаление варианта"]],
                       [parametrize("k", three[:2] if head else three)]),
                method(names["смена значений варианта"], "k, v",
                       asserts[names["смена значений варианта"]],
                       [parametrize("k, v", changed_pairs if head else pairs)]),
                method(names["смена имени аргумента"], "q" if head else "k",
                       asserts[names["смена имени аргумента"]],
                       [parametrize("q" if head else "k", two)]),
                method(names["марка пропуска на варианте"], "k",
                       asserts[names["марка пропуска на варианте"]],
                       [parametrize("k", [kept[0], skip_param(kept[1])]
                                    if head else kept)]),
                method(control, "k", asserts[control],
                       [parametrize("k", unchanged)]),
            ]
            return module("", klass(cls, methods))

        return ({path: body(False)}, {path: body(True)}, path, cls, names,
                control)


# AC-4 -----------------------------------------------------------------------

class ChangedParametrizeFindingTest(ParametrizeGateSandbox):

    def test_ac4_changed_parametrize_found_like_undeclared_assertion(self):
        """Учебный бэкенд: смена значения варианта `@pytest.mark.parametrize` у метода с прежним именем — отказ перехода, находка `uncovered`, запись в журнале и строка ревью-пакета; мандат на метод — проход.

        Файл `backend/tests/…/test_<x>.py`, класс в стиле pytest: у метода
        `<C>::test_<m>` в ветке один вариант `parametrize` заменён другим
        значением, утверждение прежнее; соседний параметризованный метод
        не меняется. `advance` пишет отказ гейта неослабления, называющий
        `<C>::test_<m>`, задача остаётся в `in_dev`. `uncovered` даёт
        находку о `<C>::test_<m>` этого файла, записи журнала его вызова
        называют метод, строки `review_lines` — тоже. Соседний метод ни в
        отказе, ни в находках не назван. После `answer` Оператора с
        мандатом `<файл>::<C>::test_<m>` находок `uncovered` нет.

        Ловит мутацию: сравниваются только утверждения, декоратор
        `parametrize` не читается — отказа, находки, записи и строки нет;
        находка уходит в отдельный канал мимо `uncovered`/`review_lines`
        (например только в запись журнала гейта) — нет находки или строки
        ревью-пакета; находка ставится на файл или класс, а не на метод —
        мандат на метод её не снимает; находка ставится всем
        параметризованным методам файла — назван неизменный сосед.
        """
        path, cls = self.file_path(BACKEND), self.klass_name()
        changed, control = self.name(), self.name()
        before, kept = self.values(2), self.values(2)
        after = [before[0], self.word(5)]
        asserts = (self.assertion(), self.assertion())

        def text(values) -> str:
            return module("", klass(cls, [
                method(changed, "k", asserts[0], [parametrize("k", values)]),
                method(control, "k", asserts[1], [parametrize("k", kept)])]))

        task_id = self.new_task(BACKEND, {path: text(before)},
                                {path: text(after)})
        name, other = f"{cls}{SEP}{changed}", f"{cls}{SEP}{control}"

        with self.subTest(entry="рубеж in_dev → verifying"):
            refusals, everything = self.advance(task_id)
            self.assertTrue(mentions(refusals, name), self.why(
                f"рубеж не отказал находкой о {name}:\n{everything}"))
            self.assertFalse(mentions(refusals, other), self.why(everything))
            self.assertEqual("in_dev",
                             store.get_task(self.conn, task_id)["state"],
                             self.why(everything))

        rest, journal, review = self.channel(task_id)
        with self.subTest(entry="uncovered"):
            self.assertTrue(self.found(rest, path, name), self.why(
                f"нет находки о {name}:\n{self.rest_text(rest)}"))
            self.assertFalse(self.found(rest, path, other),
                             self.why(self.rest_text(rest)))
            self.assertTrue(mentions(journal, name), self.why(
                f"журнал вызова не называет {name}:\n{journal}"))
        with self.subTest(entry="review_lines"):
            self.assertTrue(mentions(review, name), self.why(
                f"ревью-пакет не называет {name}:\n{review}"))

        with self.subTest(entry="мандат Оператора на метод"):
            self.weakening_answer(task_id, f"{path}{SEP}{name}",
                                  self.file_path(BACKEND))
            rest, journal, _review = self.channel(task_id)
            self.assertEqual([], rest, self.why(
                f"мандат на {name} не снял находку:\n{self.rest_text(rest)}"
                f"\n{journal}"))

    def test_ac4_declared_literal_change_does_not_cover_parametrize(self):
        """Артель: у метода объявлена и совпала смена литерала утверждения, но изменён и вариант `parametrize` — находка `uncovered` на методе остаётся.

        Файл `tests/…/test_<x>.py` артели: у `<C>::test_<a>` в ветке
        литерал утверждения `<L1>` → `<L2>` и один вариант `parametrize`
        заменён; у `<C>::test_<b>` — только литерал `<L3>` → `<L4>`,
        `parametrize` прежний. Запись approve гейта SPEC объявляет обе
        смены литерала. `uncovered` даёт находку о `<C>::test_<a>` и не
        даёт находки о `<C>::test_<b>` (его смена — объявленная смена
        ожидания).

        Ловит мутацию: объявление литерала метода снимает и находку о его
        `parametrize` (сверка `parametrize` пропускается у метода исхода
        «смена ожидания по SPEC») — находки о `<C>::test_<a>` нет;
        объявление не читается вовсе — находка и о `<C>::test_<b>`.
        """
        path, cls = self.file_path(ARTEL), self.klass_name()
        both, only = self.name(), self.name()
        l1, l2, l3, l4 = (self.literal() for _ in range(4))
        before, kept = self.values(2), self.values(2)
        after = [self.word(5), before[1]]

        def text(head: bool) -> str:
            return module("", klass(cls, [
                method(both, "k", self.assertion(l2 if head else l1),
                       [parametrize("k", after if head else before)]),
                method(only, "k", self.assertion(l4 if head else l3),
                       [parametrize("k", kept)])]))

        task_id = self.new_task(ARTEL, {path: text(False)}, {path: text(True)})
        self.declare(task_id, [(path, f"{cls}{SEP}{both}", l1, l2),
                               (path, f"{cls}{SEP}{only}", l3, l4)])
        rest, journal, _review = self.channel(task_id)
        context = self.why(f"{self.rest_text(rest)}\n{journal}")
        self.assertTrue(self.found(rest, path, f"{cls}{SEP}{both}"), context)
        self.assertFalse(self.found(rest, path, f"{cls}{SEP}{only}"), context)


# AC-5 -----------------------------------------------------------------------

class VariantChangesTest(ParametrizeGateSandbox):

    def test_ac5_removed_changed_and_skipped_variants_found(self):
        """Учебный бэкенд: удаление варианта, смена значений варианта, смена имени аргумента и `pytest.param(..., marks=pytest.mark.skip)` — находка `uncovered`, запись в журнале и строка ревью-пакета на каждом методе.

        Файл `backend/tests/…/test_<x>.py`, класс в стиле pytest, четыре
        метода с прежними именами и утверждениями: `[a, b, c]` → `[a, b]`;
        `[(a, 1), (b, 2)]` → `[(a, 1), (b, 3)]` по аргументам `k, v`;
        аргумент `k` → `q` при тех же вариантах; `[a, b]` → `[a,
        pytest.param(b, marks=pytest.mark.skip)]`. Пятый
        параметризованный метод не меняется. `uncovered` даёт находку о
        каждом из четырёх, записи журнала её вызова и строки
        `review_lines` называют каждый; пятый в находках не назван.

        Ловит мутацию: сравнивается только число вариантов — смена
        значений, имени аргумента и марка пропуска не видны; марка
        `pytest.param(..., marks=…)` снимается перед сравнением как
        оформление — нет находки на четвёртом; сравнивается только список
        значений без имён аргументов — нет находки на третьем; находка без
        записи журнала прохода или строки ревью-пакета — нет записи/строки.
        """
        base, head, path, cls, names, control = self.changed_variants(BACKEND)
        task_id = self.new_task(BACKEND, base, head)
        rest, journal, review = self.channel(task_id)
        for case, method_name in names.items():
            name = f"{cls}{SEP}{method_name}"
            with self.subTest(case=case):
                self.assertTrue(self.found(rest, path, name), self.why(
                    f"{case}: нет находки о {name}:\n{self.rest_text(rest)}"))
                self.assertTrue(mentions(journal, name), self.why(
                    f"{case}: журнал вызова не называет {name}:\n{journal}"))
                self.assertTrue(mentions(review, name), self.why(
                    f"{case}: ревью-пакет не называет {name}:\n{review}"))
        self.assertFalse(self.found(rest, path, f"{cls}{SEP}{control}"),
                         self.why(self.rest_text(rest)))

    def test_ac5_declared_literal_change_keeps_variant_findings(self):
        """Артель: у методов с объявленной и совпавшей сменой литерала удалён вариант, изменено значение варианта, добавлена марка пропуска — находка на каждом.

        Файл `tests/…/test_<x>.py` артели, три метода: в ветке литерал
        утверждения каждого `<old>` → `<new>` (объявлено записью approve
        гейта SPEC) и одновременно `[a, b, c]` → `[a, b]`; `[a, b]` → `[a,
        d]`; `[a, b]` → `[a, pytest.param(b, marks=pytest.mark.skip)]`.
        `uncovered` даёт находку о каждом из трёх методов.

        Ловит мутацию: метод исхода «смена ожидания по SPEC» выводится из
        сверки `parametrize` — находок нет ни на одном; объявление снимает
        только находку на изменённом значении, но не на удалении или марке
        — пропадает одна из трёх.
        """
        path, cls = self.file_path(ARTEL), self.klass_name()
        three, two, kept = self.values(3), self.values(2), self.values(2)
        cases = {
            "удаление варианта": (three, three[:2]),
            "смена значения варианта": (two, [two[0], self.word(5)]),
            "марка пропуска на варианте": (kept, [kept[0], skip_param(kept[1])]),
        }
        names = {case: self.name() for case in cases}
        literals = {case: (self.literal(), self.literal()) for case in cases}

        def text(head: bool) -> str:
            return module("", klass(cls, [
                method(names[case], "k",
                       self.assertion(literals[case][1 if head else 0]),
                       [parametrize("k", cases[case][1 if head else 0])])
                for case in cases]))

        task_id = self.new_task(ARTEL, {path: text(False)}, {path: text(True)})
        self.declare(task_id, [(path, f"{cls}{SEP}{names[c]}", *literals[c])
                               for c in cases])
        rest, journal, _review = self.channel(task_id)
        for case in cases:
            name = f"{cls}{SEP}{names[case]}"
            with self.subTest(case=case):
                self.assertTrue(self.found(rest, path, name), self.why(
                    f"{case}: нет находки о {name}:\n{self.rest_text(rest)}"
                    f"\n{journal}"))

    def test_ac5_added_variant_passes_with_journal_and_review_line(self):
        """Учебный бэкенд: к вариантам метода добавлен новый, прежние не тронуты — без находки и мандата, с записью в журнале и строкой ревью-пакета.

        Файл `backend/tests/…/test_<x>.py`: у метода `<C>::test_<m>` в
        ветке `[a, b]` → `[a, b, c]`, утверждение прежнее; соседний
        параметризованный метод не меняется. `uncovered` не даёт ни одной
        находки (отказа нет, мандата нет); записи журнала её вызова и
        строки `review_lines` называют `<C>::test_<m>`.

        Ловит мутацию: любое изменение списка вариантов — находка
        (добавление не отличено от удаления) — `uncovered` не пуст;
        добавление проходит молча — нет записи журнала и строки
        ревью-пакета; добавление сравнивается по позиции, а не по
        значению, и вариант, вставленный в начало списка, читается как
        смена всех — находка.
        """
        path, cls = self.file_path(BACKEND), self.klass_name()
        grown, control = self.name(), self.name()
        before, kept = self.values(2), self.values(2)
        after = list(before)
        after.insert(self.rng.randrange(0, len(after) + 1), self.word(5))
        asserts = (self.assertion(), self.assertion())

        def text(values) -> str:
            return module("", klass(cls, [
                method(grown, "k", asserts[0], [parametrize("k", values)]),
                method(control, "k", asserts[1], [parametrize("k", kept)])]))

        task_id = self.new_task(BACKEND, {path: text(before)},
                                {path: text(after)})
        name = f"{cls}{SEP}{grown}"
        rest, journal, review = self.channel(task_id)
        self.assertEqual([], rest, self.why(
            f"добавленный вариант дал находку:\n{self.rest_text(rest)}"))
        self.assertTrue(mentions(journal, name), self.why(
            f"журнал вызова не называет {name}:\n{journal}"))
        self.assertTrue(mentions(review, name), self.why(
            f"ревью-пакет не называет {name}:\n{review}"))


# AC-6 -----------------------------------------------------------------------

class ParametrizeFormsTest(ParametrizeGateSandbox):

    def form_files(self, form: str, change: str) -> tuple:
        """(путь, текст базы, текст головы, класс, методы, которые обязана
        назвать находка, методы, которых она называть не вправе, допустимы
        ли находка о классе и о файле целиком).

        `change` — «удаление варианта» (`[a, b, c]` → `[a, b]`) либо «марка
        пропуска» (`[a, b, c]` → `[a, b, pytest.param(c, marks=…)]`)."""
        path, cls = self.file_path(BACKEND), self.klass_name()
        before = self.values(3)
        after = before[:2] if change == "удаление варианта" else \
            before[:2] + [skip_param(before[2])]
        m1, m2 = self.name(), self.name()
        a1, a2 = self.assertion(), self.assertion()

        def text(values) -> str:
            mark = parametrize("k", values)
            if form == "декоратор класса":
                return module("", klass(cls, [method(m1, "k", a1),
                                              method(m2, "k", a2)],
                                        decorators=[mark]))
            if form == "pytestmark модуля":
                return module(f"pytestmark = {mark}",
                              klass(cls, [method(m1, "k", a1),
                                          method(m2, "k", a2)]))
            if form == "pytestmark класса":
                return module("", klass(cls, [method(m1, "k", a1),
                                              method(m2, "k", a2)],
                                        body=f"pytestmark = {mark}"))
            # Константа модуля: текст декоратора одинаков в базе и голове.
            return module(f"CASES = {values_text(values)}",
                          klass(cls, [method(m1, "k", a1, [
                              "pytest.mark.parametrize('k', CASES)"]),
                              method(m2, "", a2)]))

        if form == "константа модуля":
            return path, text(before), text(after), cls, [m1], [m2], False
        return path, text(before), text(after), cls, [m1, m2], [], True

    def test_ac6_all_parametrize_forms_found(self):
        """Учебный бэкенд: удаление варианта и марка пропуска на варианте — находка при `parametrize` декоратором класса, `pytestmark` модуля, `pytestmark` класса и через константу модуля `CASES`.

        Восемь файлов `backend/tests/…/test_<x>.py` (четыре формы × две
        смены), в каждом класс в стиле pytest с двумя методами с прежними
        именами и утверждениями. Варианты `[a, b, c]` в ветке становятся
        `[a, b]` либо `[a, b, pytest.param(c, marks=pytest.mark.skip)]`:
        в аргументе декоратора класса; в `pytestmark =
        pytest.mark.parametrize(...)` уровня модуля; в `pytestmark` тела
        класса; в значении `CASES = [...]` при неизменном тексте
        `@pytest.mark.parametrize('k', CASES)` первого метода (второй
        метод без параметризации). `uncovered` даёт по каждому файлу
        находку о его тестовых методах: у константы — о первом методе
        (второй не назван); у форм класса и модуля — о каждом методе либо
        одна находка о классе или о файле целиком.

        Ловит мутацию: читаются только декораторы метода — нет находок
        форм класса и модуля; `pytestmark` разбирается только на уровне
        модуля — нет находки в теле класса; аргумент-имя сравнивается
        текстом декоратора, а не присвоенным значением — нет находки у
        `CASES`; марка пропуска внутри `pytest.param` не видна ни в одной
        форме — нет находок «марки пропуска».
        """
        cases = []
        base, head = {}, {}
        for form in ("декоратор класса", "pytestmark модуля",
                     "pytestmark класса", "константа модуля"):
            for change in ("удаление варианта", "марка пропуска"):
                path, before, after, cls, named, quiet, broad = \
                    self.form_files(form, change)
                base[path], head[path] = before, after
                cases.append((form, change, path, cls, named, quiet, broad))
        task_id = self.new_task(BACKEND, base, head)
        rest, journal, _review = self.channel(task_id)
        context = f"{self.rest_text(rest)}\n{journal}"
        for form, change, path, cls, named, quiet, broad in cases:
            with self.subTest(form=form, change=change):
                names = [f"{cls}{SEP}{m}" for m in named]
                whole = broad and any(
                    self.found(rest, path, n) for n in (cls, ""))
                each = all(self.found(rest, path, n) for n in names)
                self.assertTrue(whole or each, self.why(
                    f"{form}, {change}: нет находки о {', '.join(names)} "
                    f"файла {path}:\n{context}"))
                for method_name in quiet:
                    self.assertFalse(
                        self.found(rest, path, f"{cls}{SEP}{method_name}"),
                        self.why(f"{form}: назван метод без параметризации "
                                 f"{method_name}:\n{context}"))


# AC-7 -----------------------------------------------------------------------

class ParametrizeLiteralNotDeclarableTest(unittest.TestCase):

    def test_ac7_parametrize_literal_not_in_method_literal_keys(self):
        """Литерал, стоящий только в аргументах `@pytest.mark.parametrize` метода, не входит в `guard.method_literal_keys`, и строка «Меняемого поведения» с ним «было» отказана.

        Метод класса в стиле pytest с декоратором `parametrize` и
        утверждением `assert ready(k) == <L_a>`; варианты — случайные
        литералы, ни один не стоит в утверждении: целые списком, пары
        `(строка, целое)`, `pytest.param(<целое>, id=…)`, аргумент
        `argvalues=` ключевым словом. Для каждой формы ключ литерала
        варианта (`guard.literal_pair_keys`) не входит в
        `guard.method_literal_keys` метода, а `<L_a>` входит;
        `guard.behavior_change_refusals` отказывает строке
        `<литерал варианта>` → `<новое>` и не отказывает строке `<L_a>` →
        `<новое>`.

        Ловит мутацию: аргументы декоратора `parametrize` метода включены в
        позиции литералов `method_literal_keys` (например, чтобы сравнение
        вариантов читало их тем же разбором) — ключ литерала варианта
        входит в набор, и `behavior_change_refusals` принимает строку с
        ним «было»; разбор `pytest.param(…)`/`argvalues=` добавлен только
        для одной формы — краснеет её подтест.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)

        def word() -> str:
            return "".join(rng.choice(ALPHABET) for _ in range(7))

        def number() -> int:
            return rng.randrange(100_000, 1_000_000)

        def key(text: str):
            keys = guard.literal_pair_keys([(text, text)])
            return next(iter(keys))[0] if keys else None

        forms = {}
        ints = [number(), number()]
        forms["целые списком"] = (
            f"@pytest.mark.parametrize('k', {ints!r})", "k", repr(ints[1]))
        pair = (word(), number())
        forms["пары (строка, целое)"] = (
            f"@pytest.mark.parametrize('k, v', [{pair!r}, ({word()!r}, "
            f"{number()})])", "k, v", repr(pair[0]))
        param = number()
        forms["pytest.param"] = (
            f"@pytest.mark.parametrize('k', [pytest.param({param}, "
            f"id={word()!r}), {number()}])", "k", repr(param))
        keyword = number()
        forms["argvalues= ключевым словом"] = (
            f"@pytest.mark.parametrize(argnames='k', argvalues=[{keyword}, "
            f"{number()}])", "k", repr(keyword))
        for form, (decorator, args, literal) in forms.items():
            with self.subTest(form=form):
                cls, name = f"Test{word().capitalize()}", f"test_{word()}"
                asserted = number()
                source = (f"import pytest\n\n\nclass {cls}:\n\n"
                          f"    {decorator}\n"
                          f"    def {name}(self, {args}):\n"
                          f"        assert ready(k) == {asserted}\n")
                path = f"tests/test_{word()}.py"
                qualified = f"{cls}{SEP}{name}"
                keys = guard.method_literal_keys(source, path, qualified)
                why = f"зерно: {seed}; {form}; ключи {keys!r}\n{source}"
                self.assertIsNotNone(keys, why)
                self.assertIn(key(str(asserted)), keys, why)
                self.assertNotIn(key(literal), keys, why)

                def refusals(old: str) -> list:
                    line = (f"- `{path}{SEP}{qualified}`: `{old}` → "
                            f"`{number()}` (требование 1)")
                    item, reason = guard.parse_behavior_change_line(line)
                    self.assertIsNotNone(item, f"{why}\n{reason}")
                    return guard.behavior_change_refusals(item, keys)

                self.assertTrue(refusals(literal), why)
                self.assertEqual([], refusals(str(asserted)), why)


if __name__ == "__main__":
    unittest.main()
