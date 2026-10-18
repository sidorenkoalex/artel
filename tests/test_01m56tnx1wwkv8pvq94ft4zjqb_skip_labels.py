"""Гейт неослабления видит пропуск через имя-метку и модульные пропуски (AC-1..AC-8).

Группа: долгоживущий
Красен до реализации: гейт опознаёт пропуск только по последнему сегменту имени декоратора (`@requires_pg` — не пропуск), смотрит лишь декораторы и тела функций (`pytestmark`, модульные `pytest.skip(..., allow_module_level=True)` и `pytest.importorskip(...)` не видны) и сравнивает маркер текстом (смена значения метки при прежнем `@requires_pg` не видна) — поэтому гейт мержа не эскалирует и деталь не называет методов с меткой и методов файлов с модульным пропуском; проходы условного пропуска (AC-3, AC-5, AC-7) без записи в журнале.

Связка «профиль проекта задачи — узел сравнения гейта неослабления —
git»: настоящий git песочницы (`tests.sandbox.RealGitSandbox`) — клон
артели с bare `origin` и клон учебного внешнего проекта
(`tests.sandbox.make_project_repo`) с профилем `runner: pytest-own`,
`workdir: backend`, `weakening_scope: [backend/tests/**/*.py]`. База
файлов — коммит основной ветки клона и его `origin`, голова — коммит
ветки задачи в рабочей копии (`workspace.ensure`); документы задачи —
автокоммитом шага (`checkpoint.commit_step_artifacts`). Вход узла — гейт
мержа `test_integrity.merge_gate_escalates` с областью профиля проекта
задачи (`project_profile.for_task`) и веткой документов
(`artifact_source.resolve`), как его зовёт `fsm_merge_gate`. Наблюдаемое
— эскалация и её деталь (находки «<файл>: <маркер> на <имя>», тот же вид,
что у прямого `@pytest.mark.skipif`) и запись журнала
`test_integrity.TEST_INTEGRITY_CONDITIONAL_SKIP_ACTION` об условном
пропуске, прошедшем послабление.

Провалидировано временным стабом реализации (удалён, не закоммичен):
разрешение метки своего модуля и импорта через модули стороны, марки
`pytestmark` и модульные вызовы пропуска на каждом тестовом методе
файла, сравнение по значению метки, поиск импортёров изменённой метки
вне диффа — все методы зелёные.

Имена файлов, модулей, меток, классов, методов, переменных окружения и
причины — случайные при каждом запуске; зерно печатается и входит в текст
каждого провала.
"""
import contextlib
import io
import os
import random
import re
import unittest
from unittest import mock

from orchestrator import (artifact_source, checkpoint, config,
                          github_adapter, idgen, project_profile, store,
                          workspace)
from orchestrator.advance_gates import test_integrity
from tests.sandbox import (RealGitSandbox, artel_target_entry,
                           make_project_repo)

ARTEL = config.DEFAULT_TARGET
BACKEND = "uchebnyybackend"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
SEP = "::"
ESCALATED_ACTION = "state -> escalated"

# (каталог тестов, зоны задачи, префикс имени модуля импорта) по target'у:
# у бэкенда `workdir: backend` — `tests.<x>` это `backend/tests/<x>.py`.
STACKS = {BACKEND: ("backend/tests", "backend/", "tests"),
          ARTEL: ("tests", "tests/", "tests")}

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

# PLAN: фикстура пропусков

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

# SPEC: фикстура пропусков

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

HEADER = ("import contextlib\nimport os\nimport sys\nimport unittest\n\n"
          "import pytest\n")


def expected_value(name: str) -> int:
    """Ожидаемое значение утверждения метода — от имени, одинаково в базе
    и в голове: утверждения сценариев не меняются."""
    return sum(map(ord, name)) % 997


def klass(name: str, methods, decorators=()) -> str:
    """Класс `unittest.TestCase`: `methods` — [(имя, [декораторы])]."""
    lines = [f"@{d}" for d in decorators]
    lines += [f"class {name}(unittest.TestCase):", ""]
    for method, decos in methods:
        lines += [f"    @{d}" for d in decos]
        lines += [f"    def {method}(self):",
                  f"        self.assertEqual(compute(), "
                  f"{expected_value(method)})", ""]
    return "\n".join(lines) + "\n"


def function(name: str) -> str:
    """Тестовая функция модуля в стиле pytest."""
    return (f"def {name}():\n"
            f"    assert compute() == {expected_value(name)}\n")


def module(prelude: str, *parts: str) -> str:
    """Файл теста: импорты, `prelude` уровня модуля, классы и функции."""
    head = HEADER + (f"\n{prelude.rstrip()}\n" if prelude else "")
    return head + "\n\n" + "\n\n".join(parts)


def finding_pattern(name: str):
    """Находка вида прямого декоратора пропуска — «<файл>: <маркер> на
    <имя>» в детали эскалации (элементы через «; »); за именем — конец
    элемента или пояснение, но не продолжение имени (`Класс` ≠
    `Класс::test_x`)."""
    return re.compile(rf"(?:^|; )[^;\n]+: [^;\n]* на {re.escape(name)}"
                      rf"(?![\w:])", re.M)


class Expect:
    """Ожидаемые исходы сценария: `found` — (случай, имя) находки;
    `passed` — (случай, примета в записи журнала, причина, имена без
    находки); `absent` — (случай, имя) без находки."""

    def __init__(self):
        self.found: list = []
        self.passed: list = []
        self.absent: list = []

    def merge(self, other: "Expect") -> "Expect":
        self.found += other.found
        self.passed += other.passed
        self.absent += other.absent
        return self


class SkipGateSandbox(RealGitSandbox):
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

    def name(self, prefix: str) -> str:
        return f"{prefix}{self.word()}"

    def klass_name(self, prefix: str) -> str:
        return f"{prefix}{self.word().capitalize()}Test"

    def reason(self) -> str:
        return f"нужна база {self.word()}"

    def condition(self) -> str:
        return f"not os.environ.get({self.word().upper()!r})"

    def file_path(self, target: str) -> str:
        return f"{STACKS[target][0]}/test_{self.word()}.py"

    def why(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # ------------------------------------------------------- задача и ветка

    def write(self, root, files: dict) -> None:
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def new_task(self, target: str, base: dict, head: dict) -> str:
        """Задача `target` в `in_dev`: `base` — на основной ветке клона и
        в его `origin`, `head` — коммит ветки задачи поверх неё (файл вне
        `head` не меняется); PLAN.md/SPEC.md — в ссылке документов."""
        clone = self.clones[target]
        self.write(clone, base)
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "-m", "база тестов")
        self.git("-C", str(clone), "push", "-q", "origin", config.MAIN_BRANCH)
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-propuski"
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

    def merge_gate(self, task_id: str) -> tuple:
        """(эскалировал ли гейт мержа, деталь эскалации, записи об условном
        пропуске, весь журнал) — входы те же, что передаёт
        `fsm_merge_gate`."""
        decision = project_profile.for_task(self.conn, task_id)
        self.assertIsNotNone(decision.profile, self.why(
            f"фикстура: профиль задачи не прочитан: {decision}"))
        docs, _foreign = artifact_source.resolve(self.conn, task_id)
        t = store.get_task(self.conn, task_id)
        escalated = test_integrity.merge_gate_escalates(
            self.conn, task_id, t["state"], t["branch"], docs,
            scope=decision.profile.in_weakening_scope)
        rows = store.task_steps(self.conn, task_id)
        detail = "\n".join(r["detail"] or "" for r in rows
                           if r["action"] == ESCALATED_ACTION)
        conditional = "\n".join(
            r["detail"] or "" for r in rows if r["action"]
            == test_integrity.TEST_INTEGRITY_CONDITIONAL_SKIP_ACTION)
        everything = "\n".join(f"{r['action']} | {r['detail'] or ''}"
                               for r in rows)
        return escalated, detail, conditional, everything

    def run_case(self, target: str, scenarios) -> None:
        """Сценарии `scenarios` — [(база, голова, Expect)] — одной задачей
        `target`; гейт мержа сверяется с объединёнными ожиданиями."""
        base, head, expect = {}, {}, Expect()
        for b, h, e in scenarios:
            base.update(b)
            head.update(h)
            expect.merge(e)
        task_id = self.new_task(target, base, head)
        escalated, detail, conditional, everything = self.merge_gate(task_id)
        if expect.found:
            self.assertTrue(escalated, self.why(
                f"гейт мержа не эскалировал:\n{everything}"))
        else:
            self.assertFalse(escalated, self.why(
                f"гейт мержа эскалировал проход:\n{everything}"))
        for case, name in expect.found:
            with self.subTest(case=case, name=name):
                self.assertRegex(detail, finding_pattern(name), self.why(
                    f"{case}: нет находки пропуска на {name}:\n{everything}"))
        for case, needle, reason, names in expect.passed:
            with self.subTest(case=case, needle=needle):
                self.assertIn(needle, conditional, self.why(
                    f"{case}: нет записи об условном пропуске {needle}:\n"
                    f"{everything}"))
                self.assertIn(reason, conditional, self.why(
                    f"{case}: запись об условном пропуске без причины "
                    f"«{reason}»:\n{everything}"))
                for name in names:
                    self.assertNotRegex(detail, finding_pattern(name),
                                        self.why(f"{case}: находка на "
                                                 f"{name}:\n{everything}"))
        for case, name in expect.absent:
            with self.subTest(case=case, name=name):
                self.assertNotRegex(detail, finding_pattern(name), self.why(
                    f"{case}: находка на {name}:\n{everything}"))

    # ------------------------------------------------------ сценарии меток

    def same_module_labels(self, target: str) -> tuple:
        """AC-1: метод базы получил `@<метка>`, метка связана в том же
        модуле одной из четырёх форм без причины; контроль — прямой
        `@pytest.mark.skipif(<условие>)` и метод без декоратора."""
        path = self.file_path(target)
        forms = (("skipif без причины", f"pytest.mark.skipif({self.condition()})"),
                 ("pytest.mark.skip", "pytest.mark.skip()"),
                 ("pytest.mark.xfail", "pytest.mark.xfail()"),
                 ("unittest.skip", f"unittest.skip({self.reason()!r})"))
        labels = [(case, self.name("requires_"), value)
                  for case, value in forms]
        prelude = "\n".join(f"{label} = {value}" for _c, label, value in labels)
        cls = self.klass_name("Label")
        labelled = [self.name("test_") for _ in labels]
        direct, control = self.name("test_"), self.name("test_")
        plain = [(m, []) for m in labelled + [direct, control]]
        decorated = [(m, [label]) for m, (_c, label, _v) in zip(labelled, labels)]
        decorated += [(direct, [f"pytest.mark.skipif({self.condition()})"]),
                      (control, [])]
        # Метка связана в базе заранее либо появляется вместе с декоратором.
        in_base = self.rng.random() < 0.5
        base = {path: module(prelude if in_base else "", klass(cls, plain))}
        head = {path: module(prelude, klass(cls, decorated))}
        expect = Expect()
        expect.found += [(f"AC-1 {case}", f"{cls}{SEP}{m}")
                         for m, (case, _l, _v) in zip(labelled, labels)]
        expect.found.append(("AC-1 контроль: прямой декоратор",
                             f"{cls}{SEP}{direct}"))
        expect.absent.append(("AC-1 метод без метки", f"{cls}{SEP}{control}"))
        return base, head, expect

    def imported_label(self, target: str, mod_path: str, dotted: str,
                       case: str) -> tuple:
        """AC-2: метод базы получил `@<метка>`, метка импортирована из
        модуля тестов проекта, неизменного в ветке."""
        label = self.name("requires_")
        path = self.file_path(target)
        cls = self.klass_name("Imported")
        method, control = self.name("test_"), self.name("test_")
        base = {mod_path: f"import os\n\nimport pytest\n\n{label} = "
                          f"pytest.mark.skipif({self.condition()})\n",
                path: module("", klass(cls, [(method, []), (control, [])]))}
        head = {path: module(f"from {dotted} import {label}",
                             klass(cls, [(method, [label]), (control, [])]))}
        expect = Expect()
        expect.found.append((case, f"{cls}{SEP}{method}"))
        expect.absent.append((f"{case}: метод без метки",
                              f"{cls}{SEP}{control}"))
        return base, head, expect

    def conditional_labels(self, target: str) -> tuple:
        """AC-3: условная метка с причиной — проход на новом методе и
        находка на методе базы; метка декоратором класса нового файла —
        находка; безусловная метка с причиной и `skipif(reason=…)` без
        условия на новом методе — находки."""
        path, new_path = self.file_path(target), self.file_path(target)
        cond_reason, skip_reason = self.reason(), self.reason()
        bare_reason, class_reason = self.reason(), self.reason()
        cond, skip, bare = (self.name("requires_"), self.name("requires_"),
                            self.name("requires_"))
        prelude = (f"{cond} = pytest.mark.skipif({self.condition()}, "
                   f"reason={cond_reason!r})\n"
                   f"{skip} = pytest.mark.skip(reason={skip_reason!r})\n"
                   f"{bare} = pytest.mark.skipif(reason={bare_reason!r})")
        cls = self.klass_name("Cond")
        old, control = self.name("test_"), self.name("test_")
        new_cond, new_skip, new_bare = (self.name("test_"), self.name("test_"),
                                        self.name("test_"))
        base = {path: module("", klass(cls, [(old, []), (control, [])]))}
        head_cls = klass(cls, [(old, [cond]), (control, []),
                               (new_cond, [cond]), (new_skip, [skip]),
                               (new_bare, [bare])])
        new_cls = self.klass_name("NewFile")
        class_label = self.name("requires_")
        new_methods = [self.name("test_"), self.name("test_")]
        head = {path: module(prelude, head_cls),
                new_path: module(
                    f"{class_label} = pytest.mark.skipif({self.condition()}, "
                    f"reason={class_reason!r})",
                    klass(new_cls, [(m, []) for m in new_methods],
                          decorators=[class_label]))}
        expect = Expect()
        expect.passed.append(("AC-3 условная метка на новом методе",
                              f"{cls}{SEP}{new_cond}", cond_reason,
                              [f"{cls}{SEP}{new_cond}"]))
        expect.found += [
            ("AC-3 условная метка на методе базы", f"{cls}{SEP}{old}"),
            ("AC-3 метка декоратором класса в новом файле", new_cls),
            ("AC-3 метка pytest.mark.skip(reason=…) на новом методе",
             f"{cls}{SEP}{new_skip}"),
            ("AC-3 метка skipif(reason=…) без условия на новом методе",
             f"{cls}{SEP}{new_bare}")]
        expect.absent.append(("AC-3 метод без метки", f"{cls}{SEP}{control}"))
        return base, head, expect

    def changed_label_values(self, target: str) -> tuple:
        """AC-4 (метка в том же модуле): значение метки метода и метки
        класса сменилось с `skipif(False, …)` на `skip(…)` при прежнем
        тексте декоратора; значение `pytestmark` сменилось на
        `skipif(True, …)`."""
        reason = self.reason()
        before = f"pytest.mark.skipif(False, reason={reason!r})"
        after = f"pytest.mark.skip(reason={reason!r})"
        # Метка метода в том же модуле.
        label, path = self.name("requires_"), self.file_path(target)
        cls = self.klass_name("Value")
        method, control = self.name("test_"), self.name("test_")
        body = klass(cls, [(method, [label]), (control, [])])
        # Метка декоратором класса.
        c_label, c_path = self.name("requires_"), self.file_path(target)
        c_cls = self.klass_name("ClassValue")
        c_body = klass(c_cls, [(self.name("test_"), []),
                               (self.name("test_"), [])],
                       decorators=[c_label])
        # pytestmark файла.
        p_path, p_cls = self.file_path(target), self.klass_name("Mark")
        p_methods = [self.name("test_"), self.name("test_")]
        p_func = self.name("test_")
        p_body = (klass(p_cls, [(m, []) for m in p_methods]), function(p_func))
        mark_reason, cond = self.reason(), self.condition()
        base = {path: module(f"{label} = {before}", body),
                c_path: module(f"{c_label} = {before}", c_body),
                p_path: module(f"pytestmark = pytest.mark.skipif({cond}, "
                               f"reason={mark_reason!r})", *p_body)}
        head = {path: module(f"{label} = {after}", body),
                c_path: module(f"{c_label} = {after}", c_body),
                p_path: module(f"pytestmark = pytest.mark.skipif(True, "
                               f"reason={mark_reason!r})", *p_body)}
        expect = Expect()
        expect.found += [
            ("AC-4 смена значения метки в том же модуле", f"{cls}{SEP}{method}"),
            ("AC-4 смена значения метки декоратора класса", c_cls)]
        expect.found += [("AC-4 смена значения pytestmark", f"{p_cls}{SEP}{m}")
                         for m in p_methods]
        expect.found.append(("AC-4 смена значения pytestmark (функция)",
                             p_func))
        expect.absent.append(("AC-4 метод без метки", f"{cls}{SEP}{control}"))
        return base, head, expect

    def changed_imported_label(self, target: str, mod_path: str,
                               dotted: str, case: str) -> tuple:
        """AC-4 (импортированная метка): в ветке меняется только значение
        метки в её модуле, файл теста с `@<метка>` не меняется."""
        reason = self.reason()
        label = self.name("requires_")
        path, cls = self.file_path(target), self.klass_name("Import")
        method, control = self.name("test_"), self.name("test_")
        test_text = module(f"from {dotted} import {label}",
                           klass(cls, [(method, [label]), (control, [])]))
        base = {mod_path: f"import pytest\n\n{label} = pytest.mark.skipif("
                          f"False, reason={reason!r})\n",
                path: test_text}
        head = {mod_path: f"import pytest\n\n{label} = pytest.mark.skip("
                          f"reason={reason!r})\n"}
        expect = Expect()
        expect.found.append((case, f"{cls}{SEP}{method}"))
        expect.absent.append((f"{case}: метод без метки",
                              f"{cls}{SEP}{control}"))
        return base, head, expect

    # -------------------------------------------- сценарии модульных пропусков

    def file_methods(self, prefix: str) -> tuple:
        """(класс, его методы, функция модуля, текст тел, все имена)."""
        cls = self.klass_name(prefix)
        methods = [self.name("test_"), self.name("test_")]
        func = self.name("test_")
        parts = (klass(cls, [(m, []) for m in methods]), function(func))
        return parts, [f"{cls}{SEP}{m}" for m in methods] + [func]

    def module_case(self, target: str, prelude: str, case: str,
                    in_base: bool) -> tuple:
        """Файл, которому в ветке добавлен модульный пропуск `prelude`:
        `in_base` — тестовые методы файла есть в базе, иначе файл новый."""
        path = self.file_path(target)
        parts, names = self.file_methods("Mod")
        base = {path: module("", *parts)} if in_base else {}
        head = {path: module(prelude, *parts)}
        return path, names, base, head

    def module_findings(self, target: str, cases) -> tuple:
        """Сценарии модульных пропусков с находкой на каждом тестовом
        методе файла: `cases` — [(случай, prelude, в базе ли методы)]."""
        base, head, expect = {}, {}, Expect()
        for case, prelude, in_base in cases:
            _path, names, b, h = self.module_case(target, prelude, case,
                                                  in_base)
            base.update(b)
            head.update(h)
            expect.found += [(case, name) for name in names]
        return base, head, expect

    def module_pass(self, target: str, prelude: str, reason: str,
                    case: str) -> tuple:
        """Новый файл, все тестовые методы которого новые, с условным
        модульным пропуском `prelude` с причиной — проход с записью."""
        path, names, base, head = self.module_case(target, prelude, case,
                                                   in_base=False)
        expect = Expect()
        expect.passed.append((case, path, reason, names))
        return base, head, expect

    def pytestmark_cases(self, target: str) -> list:
        """AC-5: `pytestmark` с безусловной маркой (одна и списком) и с
        условной маркой с причиной в файлах с методами базы — находки;
        условная с причиной в новом файле — проход."""
        reason = self.reason()
        return [
            self.module_findings(target, [
                ("AC-5 pytestmark = skip", f"pytestmark = pytest.mark.skip("
                 f"reason={self.reason()!r})", True),
                ("AC-5 pytestmark = [skip]", "pytestmark = [pytest.mark."
                 f"filterwarnings('ignore'), pytest.mark.skip("
                 f"reason={self.reason()!r})]", True),
                ("AC-5 pytestmark = skipif с причиной, методы базы",
                 f"pytestmark = pytest.mark.skipif({self.condition()}, "
                 f"reason={self.reason()!r})", True)]),
            self.module_pass(target, f"pytestmark = pytest.mark.skipif("
                             f"{self.condition()}, reason={reason!r})",
                             reason, "AC-5 pytestmark = skipif в новом файле")]

    def module_skip_cases(self, target: str) -> list:
        """AC-6: `pytest.skip(..., allow_module_level=True)` уровня модуля
        — находка вне `if`, внутри `if` с причиной-константой, внутри
        `except ImportError:` (методы базы) и внутри `except ImportError:`
        нового файла."""
        def call() -> str:
            return f"pytest.skip({self.reason()!r}, allow_module_level=True)"

        def guarded() -> str:
            return (f"try:\n    import {self.word()}\n"
                    f"except ImportError:\n    {call()}")

        return [self.module_findings(target, [
            ("AC-6 pytest.skip уровня модуля вне if", call(), True),
            ("AC-6 pytest.skip внутри if с причиной",
             f"if {self.condition()}:\n    {call()}", True),
            ("AC-6 pytest.skip внутри except ImportError, методы базы",
             guarded(), True),
            ("AC-6 pytest.skip внутри except ImportError, новый файл",
             guarded(), False)])]

    def importorskip_cases(self, target: str) -> list:
        """AC-7: `pytest.importorskip(...)` уровня модуля — находка вне
        `if`, внутри `if` с `reason=`, внутри `try` и `with` (методы базы),
        внутри `if` без `reason=` в новом файле; внутри `if` с `reason=` в
        новом файле — проход."""
        def call(reason: str = "") -> str:
            tail = f", reason={reason!r}" if reason else ""
            return f"{self.name('pg_')} = pytest.importorskip({self.word()!r}{tail})"

        reason = self.reason()
        return [
            self.module_findings(target, [
                ("AC-7 importorskip вне if", call(), True),
                ("AC-7 importorskip внутри if с reason",
                 f"if {self.condition()}:\n    {call(self.reason())}", True),
                ("AC-7 importorskip внутри try",
                 f"try:\n    {call()}\nexcept Exception:\n    pass", True),
                ("AC-7 importorskip внутри with",
                 f"with contextlib.suppress(Exception):\n    {call()}", True),
                ("AC-7 importorskip внутри if без reason, новый файл",
                 f"if {self.condition()}:\n    {call()}", False)]),
            self.module_pass(target, f"if {self.condition()}:\n    "
                             f"{call(reason)}", reason,
                             "AC-7 importorskip внутри if с reason, новый файл")]

    def scope_module(self, target: str) -> tuple:
        """(путь модуля меток в области тестов проекта, имя для импорта)."""
        mod = self.name("marks_")
        tdir, _zones, package = STACKS[target]
        return f"{tdir}/{mod}.py", f"{package}.{mod}"


# AC-1 -----------------------------------------------------------------------

class SameModuleLabelTest(SkipGateSandbox):

    def test_ac1_label_in_same_module_found_like_direct_decorator(self):
        """Учебный бэкенд: метод базы получил `@<метка>`, связанную в том же модуле, — находка вида прямого `@pytest.mark.skipif`.

        Файл `backend/tests/test_<x>.py` с методами базы; в ветке четыре
        метода получают по метке, связанной в том же модуле:
        `pytest.mark.skipif(<условие>)` без причины, `pytest.mark.skip()`,
        `pytest.mark.xfail()`, `unittest.skip("…")` (метки связаны в базе
        заранее либо в ветке — случайно); контроль — прямой
        `@pytest.mark.skipif(<условие>)` на пятом методе и метод без
        декоратора. Гейт мержа эскалирует; деталь несёт находку «<файл>:
        <маркер> на <Класс>::<метод>» на каждом из четырёх методов с меткой
        и на прямом декораторе; метод без декоратора не назван.

        Ловит мутацию: пропуск решается по последнему сегменту имени
        декоратора (`requires_x` — не пропуск) — четыре метода с меткой не
        названы; метка разрешается только для `skipif` — не названы методы
        с `skip`/`xfail`/`unittest.skip`; находка ставится всем методам
        файла — назван метод без декоратора.
        """
        self.run_case(BACKEND, [self.same_module_labels(BACKEND)])


# AC-2 -----------------------------------------------------------------------

class ImportedLabelTest(SkipGateSandbox):

    def test_ac2_label_imported_from_scope_module_found(self):
        """Учебный бэкенд: метод базы получил `@<метка>`, импортированную `from tests.<x> import <метка>`, — находка.

        `workdir: backend`: модуль `backend/tests/<x>.py` (в
        `weakening_scope`, в ветке не меняется) связывает `<метка> =
        pytest.mark.skipif(<условие>)` без причины; в ветке файл
        `backend/tests/test_<y>.py` импортирует метку и ставит её методу
        базы. Гейт мержа эскалирует находкой «… на <Класс>::<метод>»,
        соседний метод не назван.

        Ловит мутацию: `tests.<x>` переводится в `tests/<x>.py` без
        `workdir` — модуль метки не найден, находки нет; импортированная
        метка разрешается только из `tests/sandbox.py` — модуль `<x>` не
        смотрится, находки нет; модуль метки читается только из диффа —
        неизменный модуль не прочитан, находки нет.
        """
        mod_path, dotted = self.scope_module(BACKEND)
        self.run_case(BACKEND, [self.imported_label(
            BACKEND, mod_path, dotted, "AC-2 метка из модуля тестов проекта")])


# AC-3 -----------------------------------------------------------------------

class ConditionalLabelTest(SkipGateSandbox):

    def test_ac3_conditional_label_excused_only_on_new_method(self):
        """Учебный бэкенд: условная метка с причиной проходит на новом методе с записью в журнале и даёт находку на методе базы, на классе и в безусловных формах.

        В ветке файл с методами базы связывает `<c> =
        pytest.mark.skipif(<условие>, reason="R1")`, `<s> =
        pytest.mark.skip(reason="R2")`, `<b> =
        pytest.mark.skipif(reason="R3")`: `@<c>` — на методе базы и на
        новом методе, `@<s>` и `@<b>` — на новых методах; новый файл
        ставит условную метку с причиной декоратором класса с тестовыми
        методами. Гейт мержа эскалирует: находки на методе базы с `@<c>`,
        на новых методах с `@<s>` и `@<b>`, на классе нового файла; новый
        метод с `@<c>` находки не получает, а запись журнала «новый тест с
        условным пропуском» называет его и причину R1; метод без метки не
        назван.

        Ловит мутацию: послабление метки даётся и методу базы — нет
        находки на нём; причина сама по себе послабляет — нет находок с
        `@<s>` и `@<b>`; `skipif` без условия считается условным — нет
        находки с `@<b>`; метка декоратором класса послабляется в новом
        файле — нет находки на классе; условная метка не послабляется
        вовсе — находка на новом методе с `@<c>`, записи журнала нет.
        """
        self.run_case(BACKEND, [self.conditional_labels(BACKEND)])


# AC-4 -----------------------------------------------------------------------

class ChangedLabelValueTest(SkipGateSandbox):

    def test_ac4_changed_label_value_found_at_unchanged_decorator(self):
        """Учебный бэкенд: значение метки и `pytestmark` сменилось при прежнем тексте декоратора — находка на тесте, на классе и на методах файла.

        В базе: метка `<a> = pytest.mark.skipif(False, reason="…")` того
        же модуля на методе; метка `<c>` того же вида декоратором класса;
        метка `<i>` в модуле `backend/tests/<x>.py`, импортированная `from
        tests.<x> import <i>` неизменным в ветке файлом теста и стоящая на
        его методе; файл с `pytestmark = pytest.mark.skipif(<условие>,
        reason="…")`. В ветке: значения `<a>`, `<c>`, `<i>` →
        `pytest.mark.skip(reason="…")`, `pytestmark` →
        `pytest.mark.skipif(True, reason="…")`; тексты `@<a>`/`@<c>`/`@<i>`
        прежние. Гейт мержа эскалирует находками на методе с `@<a>`, на
        классе с `@<c>`, на методе с `@<i>` и на каждом тестовом методе
        файла с `pytestmark`; соседние методы без меток не названы.

        Ловит мутацию: маркер сравнивается текстом `@<имя>` — смена
        значения не видна ни на одном случае; файлы, импортирующие
        изменённую метку, ищутся только в диффе — нет находки на методе с
        `@<i>`; смена значения сверяется только у методов — нет находки на
        классе; `pytestmark` сравнивается текстом имени — нет находок на
        методах файла с `pytestmark`.
        """
        mod_path, dotted = self.scope_module(BACKEND)
        self.run_case(BACKEND, [
            self.changed_label_values(BACKEND),
            self.changed_imported_label(
                BACKEND, mod_path, dotted,
                "AC-4 смена значения импортированной метки")])


# AC-5 -----------------------------------------------------------------------

class PytestmarkTest(SkipGateSandbox):

    def test_ac5_pytestmark_found_on_base_methods_excused_in_new_file(self):
        """Учебный бэкенд: добавленный `pytestmark` с маркой пропуска — находка на методах базы, условный с причиной в новом файле — проход с записью.

        В ветке трём файлам с методами базы добавлен `pytestmark =
        pytest.mark.skip(reason=…)`, список `[…, pytest.mark.skip(…)]` и
        `pytest.mark.skipif(<условие>, reason="…")`; новый файл с новыми
        методами несёт `pytestmark = pytest.mark.skipif(<условие>,
        reason="R")`. Гейт мержа эскалирует находками на каждом тестовом
        методе (методы класса и функция модуля) трёх файлов базы; методы
        нового файла находок не получают, запись журнала «новый тест с
        условным пропуском» называет новый файл и причину R.

        Ловит мутацию: `pytestmark` не разбирается — находок нет;
        разбирается только одна марка, не список — нет находок второго
        файла; условный `pytestmark` с причиной послабляется и методам
        базы — нет находок третьего файла; условный `pytestmark` не
        послабляется в новом файле — находки на его методах, записи нет.
        """
        self.run_case(BACKEND, self.pytestmark_cases(BACKEND))


# AC-6 -----------------------------------------------------------------------

class ModuleLevelSkipTest(SkipGateSandbox):

    def test_ac6_module_level_pytest_skip_found(self):
        """Учебный бэкенд: `pytest.skip(..., allow_module_level=True)` уровня модуля — находка вне `if`, в `if` с причиной, в `except ImportError:` и в новом файле.

        В ветке трём файлам с методами базы добавлен вызов
        `pytest.skip("…", allow_module_level=True)`: прямо на уровне
        модуля, внутри `if <условие>:` с причиной-константой и внутри
        `except ImportError:` блока `try` уровня модуля; новый файл с
        новыми методами несёт тот же вызов внутри `except ImportError:`.
        Гейт мержа эскалирует находками на каждом тестовом методе всех
        четырёх файлов.

        Ловит мутацию: вызовы пропуска ищутся только в телах функций —
        находок нет; уровень модуля — только операторы верхнего уровня —
        нет находок у вызовов внутри `if` и `except`; вызов внутри
        `try`/`except` считается условным — нет находки в новом файле;
        условный модульный вызов послабляется и методам базы — нет находок
        файла с `if`.
        """
        self.run_case(BACKEND, self.module_skip_cases(BACKEND))


# AC-7 -----------------------------------------------------------------------

class ModuleImportorskipTest(SkipGateSandbox):

    def test_ac7_module_level_importorskip(self):
        """Учебный бэкенд: `pytest.importorskip(...)` уровня модуля — находка на методах базы и без `reason=` в новом файле, с `reason=` в `if` нового файла — проход.

        В ветке четырём файлам с методами базы добавлен
        `pytest.importorskip(…)`: на уровне модуля вне `if`, внутри `if
        <условие>:` с `reason="…"`, внутри блока `try` и внутри блока
        `with`; новый файл с новыми методами несёт вызов внутри `if` без
        `reason=`, другой новый файл — внутри `if` с `reason="R"`. Гейт
        мержа эскалирует находками на каждом тестовом методе пяти файлов;
        методы последнего файла находок не получают, запись журнала «новый
        тест с условным пропуском» называет его и причину R.

        Ловит мутацию: `importorskip` не считается пропуском — находок
        нет; вызов внутри `try`/`with` не считается уровнем модуля — нет
        находок этих файлов; причина `importorskip` берётся позиционным
        аргументом (как у `pytest.skip`) — вызов без `reason=` проходит,
        а с `reason=` — находка; условный вызов с причиной послабляется
        методам базы — нет находок файла с `if`.
        """
        self.run_case(BACKEND, self.importorskip_cases(BACKEND))


# AC-8 -----------------------------------------------------------------------

class ArtelSkipOutcomesTest(SkipGateSandbox):

    def test_ac8_artel_same_module_and_module_level_outcomes(self):
        """Артель: случаи AC-1, AC-3, AC-4 (метка в том же модуле, класс, `pytestmark`), AC-5, AC-6, AC-7 на файлах `tests/` дают те же исходы.

        Одна задача артели (`tests/**/*.py` её профиля) несёт все сценарии
        этих критериев в разных файлах `tests/`: находки — там же, где у
        учебного бэкенда, проходы условного пропуска — с записью журнала,
        методы без меток не названы.

        Ловит мутацию: распознавание метки и модульных пропусков включено
        только в режиме внешнего проекта (по `workdir`/профилю) — у
        артели находок нет и проходов не записано; послабление у артели
        идёт по прежнему правилу текста маркера — нет находок смены
        значения метки и `pytestmark`.
        """
        self.run_case(ARTEL, [self.same_module_labels(ARTEL),
                              self.conditional_labels(ARTEL),
                              self.changed_label_values(ARTEL)]
                      + self.pytestmark_cases(ARTEL)
                      + self.module_skip_cases(ARTEL)
                      + self.importorskip_cases(ARTEL))

    def test_ac8_artel_label_imported_from_sandbox_and_other_module(self):
        """Артель: метка, связанная в `tests/sandbox.py` и в другом модуле `tests/`, импортирована и поставлена методу базы — находка в обоих случаях.

        Модули `tests/sandbox.py` и `tests/marks_<x>.py` (оба в ветке не
        меняются) связывают по метке `pytest.mark.skipif(<условие>)` без
        причины; в ветке два файла теста импортируют их `from
        tests.sandbox import …` и `from tests.marks_<x> import …` и ставят
        методам базы. Гейт мержа эскалирует находками на обоих методах,
        соседние методы не названы.

        Ловит мутацию: у артели импортированная метка разрешается только
        из `tests/sandbox.py` — нет находки с меткой другого модуля;
        только из модулей, отличных от `tests/sandbox.py`, — нет находки с
        меткой песочницы.
        """
        mod_path, dotted = self.scope_module(ARTEL)
        self.run_case(ARTEL, [
            self.imported_label(ARTEL, "tests/sandbox.py", "tests.sandbox",
                                "AC-8 метка из tests/sandbox.py"),
            self.imported_label(ARTEL, mod_path, dotted,
                                "AC-8 метка из другого модуля tests/")])

    def test_ac8_artel_imported_label_value_change_found_outside_diff(self):
        """Артель: меняется только модуль метки (`tests/sandbox.py` либо другой модуль `tests/`), файл теста с `@<метка>` не меняется — находка на тесте.

        Для каждого из двух модулей — своя задача артели: в базе модуль
        связывает `<метка> = pytest.mark.skipif(False, reason="…")`, файл
        теста импортирует её и ставит методу; в ветке меняется только
        значение метки на `pytest.mark.skip(reason="…")`. Гейт мержа
        эскалирует находкой на методе с меткой, соседний метод не назван.

        Ловит мутацию: файлы-импортёры изменённой метки у артели не
        ищутся вне диффа (поиск включён только для внешнего проекта) —
        находки нет; импортёры ищутся только для `tests/sandbox.py` — нет
        находки у модуля `tests/marks_<x>.py`.
        """
        mod_path, dotted = self.scope_module(ARTEL)
        for path, name in (("tests/sandbox.py", "tests.sandbox"),
                           (mod_path, dotted)):
            with self.subTest(module=path):
                self.run_case(ARTEL, [self.changed_imported_label(
                    ARTEL, path, name,
                    f"AC-8 смена значения метки из {path}")])


if __name__ == "__main__":
    unittest.main()
