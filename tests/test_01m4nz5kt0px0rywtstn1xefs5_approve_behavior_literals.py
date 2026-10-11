"""Сверка раздела SPEC «Меняемое поведение» на `approve` гейта SPEC: «было»
среди литералов утверждений метода и его помощников первого уровня на
main, смена вида утверждения, нечитаемый и контейнерный литерал (AC-4,
AC-5, AC-6, AC-7).

Группа: долгоживущий

Красен до реализации: approve сверяет только существование названного метода в голове main — строки с «было», которого нет в коде метода, со сменой вида утверждения, со словами, выражением, именем или контейнером вместо литерала проходят в `tests_writing` с записью «объявлена смена поведения тестов» вместо мягкого отказа; AC-5 (было в помощнике первого уровня проходит) и вторая половина AC-6 (пара литералов проходит) зелены с рождения — сегодня approve пропускает любую пару существующего метода.

Песочница — `tests.sandbox.GitignoreCommittedRealGitSandbox`: пульт и клон
артели — один настоящий git-репозиторий `self.root`, голый origin. База —
коммит на main (и в origin) с `app.py` и файлами тестов фикстуры; задача
артели заводится `catalog.cmd_new`; SPEC с разделом «Меняемое поведение»,
PLAN и планка коммитятся в ссылку документов задачи; задача ставится на
`spec_gate`; `approve` — `fsm.cmd_approve`. Связка «approve — разбор guard
— голова main в git — журнал FSM» и есть предмет проверки. Несколько
отказов одного теста идут подряд на одной задаче: после мягкого отказа она
остаётся на `spec_gate`, SPEC правится новым коммитом в ссылку документов,
approve повторяется. Имена методов и классов, значения литералов и номера
требований — из `random`; зерно печатается и входит в текст каждого
провала.

Провалидирован временным стабом сверки в `fsm._behavior_change_declaration`
поверх разбора guard (откачен, не закоммичен): все тесты зелены; мутанты
стаба «сверка вида отключена», «помощники из других модулей не видны»,
«литералы по всему файлу», «было ищется подстрокой текста», «литерал
проверяется только у стало», «контейнер засчитывается» красят свои тесты.
"""
import contextlib
import io
import os
import random
import re
import unittest
from unittest import mock

from orchestrator import catalog, config, fsm, projects, store, workspace
from tests.sandbox import GitignoreCommittedRealGitSandbox

DOCS_REF_PREFIX = "refs/artifacts/"
DECLARED_ACTION = "объявлена смена поведения тестов"
APPROVE_REFUSED = "approve отклонён"
NEED_LITERAL = "нужен литерал"
NEED_SCALAR = "нужен скалярный литерал"
OTHER_KIND = "другой вид утверждения"
REQUIREMENTS = 9

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
zones: tests/, app.py
budget_usd: 30
---

# SPEC: фикстура смены поведения

## Контекст

Фикстура песочницы.

## Требования

{requirements}

## Критерии приёмки

AC-1. Фикстурный критерий.
{section}
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
        self.assertEqual(1 + 1, 2)
'''

# Пары видов утверждений для AC-6: (вид «было», вид «стало», аргументы).
KIND_PAIRS = (
    ("assertIn", "assertNotIn", "a, b"),
    ("assertNotIn", "assertIn", "a, b"),
    ("assertTrue", "assertFalse", "x"),
    ("assertEqual", "assertNotEqual", "x, y"),
    ("assertIsNone", "assertIsNotNone", "x"),
    ("assertEqual", "assertIn", "x, y"),
)


def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def method(name: str, body: list, doc: str = "") -> str:
    """Метод класса фикстуры: `doc` — докстринг (пусто — без него)."""
    lines = [f"\n    def {name}(self):\n"]
    if doc:
        lines.append(f'        """{doc}"""\n')
    lines += [f"        {line}\n" for line in body]
    return "".join(lines)


def fixture_source(cls: str, methods: list, header: str = "",
                   base: str = "unittest.TestCase") -> str:
    """Файл тестов фикстуры: класс `cls` с базой `base` и методами."""
    return (f"import unittest\n\nimport app\n{header}\n\n"
            f"class {cls}({base}):\n" + "".join(methods))


class ApproveLiteralSandbox(GitignoreCommittedRealGitSandbox):
    """Задача артели на `spec_gate`: база на main, SPEC с разделом
    «Меняемое поведение» в ссылке документов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.cls = f"Fx{word(self.rng).capitalize()}Test"
        self.path = f"tests/test_fx_{word(self.rng)}.py"
        self.add_synced_origin()
        config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        self.use_role_map()
        templates = self.root / ".artel" / "templates-fixture"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "SPEC.md").write_text(
            SPEC_TEXT.format(task="TASK_ID", requirements="1. Фикстура.",
                             section=""), encoding="utf-8")
        for patcher in (
                mock.patch.object(config, "TEMPLATES", templates),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.task_id = ""

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

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

    def line(self, name: str, pairs: list, req: int = 1) -> str:
        """Строка раздела «Меняемое поведение»: пары — тексты в обратных
        кавычках как есть."""
        text = "; ".join(f"`{old}` → `{new}`" for old, new in pairs)
        return f"- `{self.path}::{self.cls}::{name}`: {text} (требование {req})"

    def spec_text(self, section: list) -> str:
        requirements = "\n".join(f"{n}. Требование фикстуры номер {n}."
                                 for n in range(1, REQUIREMENTS + 1))
        body = ("\n## Меняемое поведение\n\nСмены ожидания фикстуры.\n\n"
                + "\n".join(section) + "\n")
        return SPEC_TEXT.format(task=self.task_id, requirements=requirements,
                                section=body)

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

    def start(self, base: dict, section: list) -> str:
        """База на main и в origin, задача, документы, `spec_gate`,
        `approve` — вывод approve."""
        for rel, text in base.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        before = {row["id"] for row in store.all_tasks(store.db())}
        self.run_cmd(catalog.cmd_new, f"Смена поведения {self.seed}",
                     target=config.DEFAULT_TARGET)
        created = [row["id"] for row in store.all_tasks(store.db())
                   if row["id"] not in before]
        self.assertEqual(len(created), 1, self.note("задача не заведена"))
        self.task_id = created[0]
        branch = store.get_task(store.db(), self.task_id)["branch"]
        if not self.git("branch", "--list", branch).strip():
            self.git("branch", branch, config.MAIN_BRANCH)
        _wt, error = workspace.ensure(self.task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.commit_docs({"SPEC.md": self.spec_text(section),
                          "PLAN.md": PLAN_TEXT.format(task=self.task_id),
                          "acceptance_tests/test_plank.py": PLANK_TEXT},
                         "документы задачи")
        store.update_task(store.db(), self.task_id, state="spec_gate")
        store.record_fixation(store.db(), self.task_id)
        return self.approve()

    def approve(self) -> str:
        store.record_fixation(store.db(), self.task_id)
        return self.run_cmd(fsm.cmd_approve, self.task_id)

    def reapprove(self, section: list) -> str:
        """Правка SPEC (новый раздел) коммитом в ссылку документов и
        повторный approve той же задачи на `spec_gate`."""
        self.commit_docs({"SPEC.md": self.spec_text(section)}, "правка SPEC")
        return self.approve()

    def state(self) -> str:
        return store.get_task(store.db(), self.task_id)["state"]

    def details(self, action: str) -> list:
        return [s["detail"] or "" for s in store.task_steps(store.db(), self.task_id)
                if s["action"] == action]

    def journal_text(self) -> str:
        return "\n".join(f"{s['action']} | {s['detail'] or ''}"
                         for s in store.task_steps(store.db(), self.task_id))

    def refusals(self) -> list:
        return [d for d in self.details(APPROVE_REFUSED) if d.strip()]

    def soft_refusal(self, out: str, before: int, what: str) -> str:
        """Мягкий отказ approve: задача на `spec_gate`, новая непустая
        запись «approve отклонён», записи объявления нет. Возврат — текст
        причины."""
        context = self.note(f"{what}\nвывод approve:\n{out}\n"
                            f"журнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "spec_gate", context)
        refused = self.refusals()
        self.assertGreater(len(refused), before, context)
        self.assertEqual(self.details(DECLARED_ACTION), [], context)
        return refused[-1]

    def run_refusal_rounds(self, base: dict, rounds: list, check) -> None:
        """Каждый раунд — (раздел, описание, аргумент `check`): первый —
        approve новой задачи на базе `base`, остальные — правка SPEC и
        повторный approve той же задачи; после каждого — мягкий отказ и
        `check(причина, контекст, аргумент)`."""
        for index, (section, what, arg) in enumerate(rounds):
            before = len(self.refusals()) if self.task_id else 0
            out = self.start(base, section) if index == 0 else self.reapprove(section)
            reason = self.soft_refusal(out, before, what)
            check(reason, self.note(f"{what}\nпричина: {reason}"), arg)


# ---------------------------------------------------------------------------
# AC-4: «было» нет среди литералов кода метода и его помощников.

class WasNotInMethodCodeTest(ApproveLiteralSandbox):

    def test_ac4_was_absent_from_method_and_helpers_refuses_approve(self):
        """«было», которого нет среди литералов кода метода и его помощников, — мягкий отказ approve с методом и фрагментом.

        Сценарий: в файле на main метод-цель (утверждение с литералом
        `<v><d>`, вызов своего помощника с другим литералом, однострочный
        докстринг из случайного слова) и метод того же класса, который
        цель не вызывает, с литералом-словом. Три раунда на одной задаче,
        у каждого раздел с одной строкой о цели: «было» `v` (есть лишь
        внутри `<v><d>`); «было» — слово из невызываемого метода; «было»
        — слово докстринга цели. Каждый раз задача остаётся на
        `spec_gate`, есть новая запись «approve отклонён», её причина
        называет метод-цель и фрагмент «было», записи «объявлена смена
        поведения тестов» нет.

        Ловит мутацию: approve не сверяет «было» с кодом — первый раунд
        проходит в `tests_writing`; «было» ищется по всему файлу — второй
        раунд проходит; «было» ищется подстрокой текста метода — первый
        (и третий) проходят; докстринг засчитывается литералом — третий
        проходит.
        """
        v = self.rng.randrange(1, 10)
        code_value = v * 10 + self.rng.randrange(0, 10)
        helper_value = self.rng.randrange(100, 1000)
        other_word = f"other-{word(self.rng)}"
        doc_word = f"doc{word(self.rng)}"
        target = f"test_target_{word(self.rng)}"
        helper = f"check_{word(self.rng)}"
        other = self.rng.choice([f"test_other_{word(self.rng)}",
                                 f"check_other_{word(self.rng)}"])
        source = fixture_source(self.cls, [
            method(target, [f"self.assertEqual(app.VALUE, {code_value})",
                            f"self.{helper}()"], doc=doc_word),
            method(helper, [f"self.assertGreater(app.VALUE, {helper_value})"]),
            method(other, [f"self.assertEqual(app.NAME, {other_word!r})"]),
        ])
        base = {"app.py": f"VALUE = {code_value}\nNAME = {other_word!r}\n",
                self.path: source}
        req = self.rng.choice([n for n in range(1, REQUIREMENTS + 1) if n != v])
        rounds = [
            ([self.line(target, [(str(v), str(v + 10 * self.rng.randrange(20, 90)))], req)],
             f"«было» {v} — только подстрока литерала {code_value}",
             rf"(?<![\w.]){v}(?![\w.])"),
            ([self.line(target, [(repr(other_word), repr(f"new-{word(self.rng)}"))], req)],
             f"«было» {other_word!r} — литерал невызываемого метода {other}",
             re.escape(other_word)),
            ([self.line(target, [(repr(doc_word), repr(f"new-{word(self.rng)}"))], req)],
             f"«было» {doc_word!r} — только докстринг метода",
             re.escape(doc_word)),
        ]

        def check(reason, context, fragment):
            self.assertIn(target, reason, context)
            self.assertRegex(reason, fragment, context)

        self.run_refusal_rounds(base, rounds, check)


# ---------------------------------------------------------------------------
# AC-5: «было» в помощнике первого уровня, в том числе из другого модуля.

class WasInHelperPassesTest(ApproveLiteralSandbox):

    def test_ac5_was_in_first_level_helpers_passes_with_one_declaration(self):
        """«было» из литерала помощника первого уровня (свой класс, `tests/sandbox.py`, базовый класс другого файла) и `-N` метода проходят approve.

        Сценарий: на main файл тестов с классом, унаследованным от
        базового класса из другого файла `tests/`; модуль
        `tests/sandbox.py` с функцией-помощником. Четыре метода: зовёт
        помощник своего класса; зовёт функцию `tests/sandbox.py`; зовёт
        метод базового класса; утверждает `-N` сам. У каждого из первых
        трёх «было» — строковый литерал только из утверждения помощника (в
        самом методе его нет), у четвёртого — `-N`. Раздел — четыре строки
        с литеральными парами. approve переводит задачу в `tests_writing`,
        запись «объявлена смена поведения тестов» ровно одна, записи
        «approve отклонён» нет.

        Ловит мутацию: помощники первого уровня не просматриваются
        (литералы берутся только из тела самого метода) — отказ approve,
        задача на `spec_gate`; не просматриваются функции `tests/sandbox.py`
        или базовые классы из другого файла — тот же отказ по своей
        строке; знак `-` не читается частью литерала (ищется `N`) — отказ
        по четвёртой строке.
        """
        mod = f"fx_base_{word(self.rng)}"
        base_cls = f"FxBase{word(self.rng).capitalize()}"
        sandbox_fn = f"check_fx_{word(self.rng)}"
        own_helper = f"check_own_{word(self.rng)}"
        base_helper = f"check_base_{word(self.rng)}"
        own_lit, sandbox_lit, base_lit = (f"{kind}-{word(self.rng)}"
                                          for kind in ("own", "sandbox", "base"))
        negative = self.rng.randrange(1, 500)
        names = {kind: f"test_{kind}_{word(self.rng)}"
                 for kind in ("own", "sandbox", "base", "negative")}
        source = fixture_source(self.cls, [
            method(own_helper, [f"self.assertEqual(app.NAME, {own_lit!r})"]),
            method(names["own"], [f"self.{own_helper}()",
                                  "self.assertTrue(app.NAME)"]),
            method(names["sandbox"], [f"{sandbox_fn}(self)",
                                      "self.assertTrue(app.NAME)"]),
            method(names["base"], [f"self.{base_helper}()"]),
            method(names["negative"], [f"self.assertEqual(app.VALUE, -{negative})"]),
        ], header=(f"from tests.sandbox import {sandbox_fn}\n"
                   f"from tests.{mod} import {base_cls}"), base=base_cls)
        base = {
            "app.py": f"VALUE = -{negative}\nNAME = 'x'\n",
            "tests/__init__.py": "",
            "tests/sandbox.py": (f"import app\n\n\ndef {sandbox_fn}(case):\n"
                                 f"    case.assertEqual(app.NAME, {sandbox_lit!r})\n"),
            f"tests/{mod}.py": (f"import unittest\n\nimport app\n\n\n"
                                f"class {base_cls}(unittest.TestCase):\n"
                                f"{method(base_helper, [f'self.assertEqual(app.NAME, {base_lit!r})'])}"),
            self.path: source,
        }
        reqs = [self.rng.randrange(1, REQUIREMENTS + 1) for _ in range(4)]
        section = [
            self.line(names["own"], [(repr(own_lit), repr(f"new-{word(self.rng)}"))], reqs[0]),
            self.line(names["sandbox"], [(repr(sandbox_lit), repr(f"new-{word(self.rng)}"))], reqs[1]),
            self.line(names["base"], [(repr(base_lit), repr(f"new-{word(self.rng)}"))], reqs[2]),
            self.line(names["negative"], [(f"-{negative}", f"-{negative + 1}")], reqs[3]),
        ]
        out = self.start(base, section)
        context = self.note(f"вывод approve:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "tests_writing", context)
        self.assertEqual(len(self.details(DECLARED_ACTION)), 1, context)
        self.assertEqual(self.refusals(), [], context)


# ---------------------------------------------------------------------------
# AC-6: смена вида утверждения — отказ со своей причиной.

class AssertionKindChangeTest(ApproveLiteralSandbox):

    def test_ac6_kind_change_refused_and_literal_pair_passes(self):
        """Пара вызовов утверждений разного вида — мягкий отказ со сменой вида и без «нужен литерал»; пара литералов проходит.

        Сценарий: метод на main с утверждением `assertEqual` и строковым
        литералом. Раунд 1: строка раздела о нём с парой вызовов
        утверждений разного вида (пара видов и аргументы — из зерна).
        Задача остаётся на `spec_gate`, причина называет оба вида или
        «другой вид утверждения», говорит вынести смену вопросом
        Оператору и не содержит «нужен литерал»; записи объявления нет.
        Раунд 2: правка SPEC — та же строка с парой литералов, «было» —
        литерал метода. approve переводит задачу в `tests_writing` и пишет
        одну запись «объявлена смена поведения тестов».

        Ловит мутацию: сверка вида утверждения отключена — пара вызовов
        уходит в сверку литерала, причина «нужен литерал» без смены вида;
        сверка вида идёт после сверки литерала — то же; вид сверяется и у
        пары литералов — второй раунд отказан.
        """
        old_kind, new_kind, args = self.rng.choice(KIND_PAIRS)
        lit = f"was-{word(self.rng)}"
        name = f"test_kind_{word(self.rng)}"
        base = {"app.py": f"NAME = {lit!r}\n",
                self.path: fixture_source(self.cls, [
                    method(name, [f"self.assertEqual(app.NAME, {lit!r})"])])}
        req = self.rng.randrange(1, REQUIREMENTS + 1)
        section = [self.line(name, [(f"self.{old_kind}({args})",
                                     f"self.{new_kind}({args})")], req)]
        out = self.start(base, section)
        reason = self.soft_refusal(out, 0, f"смена вида {old_kind} → {new_kind}")
        context = self.note(f"смена вида {old_kind} → {new_kind}\nпричина: {reason}")
        self.assertTrue((old_kind in reason and new_kind in reason)
                        or OTHER_KIND in reason, context)
        self.assertIn("вопрос", reason.lower(), context)
        self.assertIn("оператор", reason.lower(), context)
        self.assertNotIn(NEED_LITERAL, reason, context)

        out = self.reapprove([self.line(name, [(repr(lit), repr(f"new-{word(self.rng)}"))], req)])
        context = self.note(f"пара литералов\nвывод approve:\n{out}\n"
                            f"журнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "tests_writing", context)
        self.assertEqual(len(self.details(DECLARED_ACTION)), 1, context)


# ---------------------------------------------------------------------------
# AC-7: «было»/«стало» не литерал или контейнер.

class NotLiteralRefusalTest(ApproveLiteralSandbox):

    def test_ac7_unreadable_side_refuses_with_need_literal(self):
        """Слова, выражение того же вида утверждения или имя на месте «было» или «стало» — отказ «нужен литерал» с методом и фрагментом.

        Сценарий: метод на main утверждает `assertEqual(app.VALUE, N)`.
        Раунды на одной задаче (порядок из зерна), у каждого — строка
        раздела о методе с одной парой: нечитаемое «стало» при «было»
        `N` и нечитаемое «было» при читаемом «стало» — для слов, вызова
        `self.assertEqual(x, …)` и имени; плюс пара, где обе стороны —
        вызовы одного вида, и пара двух имён. Каждый раз задача остаётся
        на `spec_gate`, причина содержит «нужен литерал», имя метода и
        нечитаемый фрагмент; записи объявления нет.

        Ловит мутацию: сверки литерала нет — раунд с нечитаемым «стало»
        проходит в `tests_writing`; литерал проверяется только у «стало»
        — раунд с нечитаемым «было» отказывается иной причиной (нет в
        коде) без «нужен литерал»; пара одного вида утверждения
        принимается за смену вида — причина без «нужен литерал».
        """
        old = self.rng.randrange(10, 500)
        new = old + self.rng.randrange(1, 500)
        name = f"test_value_{word(self.rng)}"
        base = {"app.py": f"VALUE = {old}\n",
                self.path: fixture_source(self.cls, [
                    method(name, [f"self.assertEqual(app.VALUE, {old})"])])}
        words = f"отказ без {word(self.rng)}"
        call_old = f"self.assertEqual(x, {old})"
        call_new = f"self.assertEqual(x, {new})"
        const = f"LIMIT_{word(self.rng).upper()}"
        cases = [
            (str(old), words, "слова на месте «стало»", [words]),
            (words, str(new), "слова на месте «было»", [words]),
            (str(old), call_new, "вызов на месте «стало»", [call_new]),
            (call_old, str(new), "вызов на месте «было»", [call_old]),
            (str(old), f"{const}2", "имя на месте «стало»", [f"{const}2"]),
            (const, str(new), "имя на месте «было»", [const]),
            (call_old, call_new, "вызовы одного вида с обеих сторон", [call_old, call_new]),
            (const, f"{const}2", "имена с обеих сторон", [const, f"{const}2"]),
        ]
        self.rng.shuffle(cases)
        req = self.rng.randrange(1, REQUIREMENTS + 1)
        rounds = [([self.line(name, [(was, became)], req)], what, fragments)
                  for was, became, what, fragments in cases]

        def check(reason, context, fragments):
            self.assertIn(NEED_LITERAL, reason, context)
            self.assertIn(name, reason, context)
            self.assertTrue(any(f in reason for f in fragments), context)

        self.run_refusal_rounds(base, rounds, check)

    def test_ac7_container_pair_refuses_with_need_scalar_literal(self):
        """Пара контейнеров `[a, b]` → `[a, c]` — мягкий отказ «нужен скалярный литерал».

        Сценарий: метод на main утверждает равенство списку `[a, b]`
        (числа из зерна); строка раздела о нём с парой `[a, b]` → `[a, c]`.
        Задача остаётся на `spec_gate`, причина содержит «нужен скалярный
        литерал» и имя метода; записи объявления нет.

        Ловит мутацию: контейнер засчитывается литералом — пара уходит в
        поиск «было» среди литералов кода (там лишь `a` и `b` по
        отдельности) и отказ приходит без «нужен скалярный литерал», либо
        approve проходит.
        """
        a, b = self.rng.sample(range(1, 100), 2)
        c = b + self.rng.randrange(1, 100)
        name = f"test_items_{word(self.rng)}"
        base = {"app.py": f"ITEMS = [{a}, {b}]\n",
                self.path: fixture_source(self.cls, [
                    method(name, [f"self.assertEqual(app.ITEMS, [{a}, {b}])"])])}
        section = [self.line(name, [(f"[{a}, {b}]", f"[{a}, {c}]")],
                             self.rng.randrange(1, REQUIREMENTS + 1))]
        out = self.start(base, section)
        reason = self.soft_refusal(out, 0, f"контейнеры [{a}, {b}] → [{a}, {c}]")
        context = self.note(f"причина: {reason}")
        self.assertIn(NEED_SCALAR, reason, context)
        self.assertIn(name, reason, context)


if __name__ == "__main__":
    unittest.main()
