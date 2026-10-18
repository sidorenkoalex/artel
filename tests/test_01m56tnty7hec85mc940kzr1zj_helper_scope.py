"""Гейт неослабления прослеживает помощников по области ослабления проекта задачи (AC-1..AC-5).

Группа: долгоживущий
Красен до реализации: вызывающие ослабленного помощника ищутся только в `tests/`, имя модуля импорта переводится как `tests.x` → `tests/x.py` без `workdir` профиля, относительный импорт разрешается от пути от корня репозитория, а импортированная функция прослеживается только из `tests/sandbox.py` — поэтому у учебного внешнего проекта помощник `backend/tests/rbac_support.py`, функция `tests/x.py` при пустом `workdir` и функция `backend/tests/x.py` по `from .x import f` находки на вызывающем не дают (AC-1, AC-2, AC-3: эскалации и отказа нет), и контрольная находка AC-4 (помощник в области) тоже не появляется; артель (AC-5) держит сегодняшние исходы и зелёна с рождения.

Связка «профиль проекта задачи — узел сравнения гейта — git»: настоящий
git песочницы (`tests.sandbox.RealGitSandbox`) — клон артели с bare
`origin` и клоны двух учебных внешних проектов
(`tests.sandbox.make_project_repo`): «бэкенд» — профиль `runner:
pytest-own`, `workdir: backend`, `weakening_scope: [backend/tests/**/*.py]`;
«плоский» — пустой `workdir`, `weakening_scope: [tests/**/*.py]`. База
файлов — коммит на основной ветке клона и его `origin`, голова — коммит
ветки задачи в рабочей копии (`workspace.ensure`); документы задачи —
автокоммитом шага (`checkpoint.commit_step_artifacts`). Входы узла
зовутся так, как их зовёт пульт: рубеж `in_dev → verifying` — публичной
командой `fsm.cmd_advance`; гейт мержа (`merge_gate_escalates`) и раздел
ревью-пакета (`review_lines`) — с областью `in_weakening_scope` профиля
проекта задачи (`project_profile.for_task`) и веткой документов
`artifact_source.resolve`, как в `fsm_merge_gate` и `review`.
Наблюдаемое — запись отказа рубежа, деталь эскалации гейта мержа в
журнале задачи, строки раздела ревью-пакета.

Провалидировано временным стабом реализации (удалён, не закоммичен):
режим и `workdir` из профиля задачи на узле `_evaluate`, перевод имени
модуля и относительного импорта с учётом `workdir`, функция любого модуля
области помощником у внешнего проекта, поиск вызывающих по области — все
методы зелёные.

Имена модулей, функций, классов, методов и ожидаемые значения — случайные
при каждом запуске; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import unittest
from unittest import mock

from orchestrator import (artifact_source, checkpoint, config, fsm,
                          github_adapter, idgen, project_profile, store,
                          workspace)
from orchestrator.advance_gates import test_integrity
from tests.sandbox import (RealGitSandbox, artel_target_entry,
                           make_project_repo)

ARTEL = config.DEFAULT_TARGET
BACKEND = "uchebnyybackend"
FLAT = "uchebnyyploskiy"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
SEP = "::"
ESCALATED_ACTION = "state -> escalated"
RBAC_SUPPORT = "backend/tests/rbac_support.py"

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
      long_lived_dir: {lld}
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [{lld}/**/*.py]
      mutation_claim_scope: [{lld}/**/test_*.py]
      report: junit-xml
      install: []
{extra}"""

BACKEND_EXTRA = """      runner: pytest-own
      workdir: backend
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура помощников

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

# SPEC: фикстура помощников

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""


def helper_function(name: str, expected: int, weakened: bool) -> str:
    """Функция-помощник `name(test, value)`: в базе — `assertEqual(value,
    expected)` и `assertIsNotNone(value)`, ослабленная — без
    `assertEqual`."""
    equal = "" if weakened else f"    test.assertEqual(value, {expected})\n"
    return f"\n\ndef {name}(test, value):\n{equal}    test.assertIsNotNone(value)\n"


def helper_module(name: str, expected: int, weakened: bool) -> str:
    return '"""Помощники тестов."""\n' + helper_function(name, expected,
                                                          weakened)


def caller_module(import_line: str, cls: str, method: str, helper: str,
                  control: str, head_note: str = "") -> str:
    """Файл теста: `cls.method` зовёт `helper(self, …)` по импорту
    `import_line`, соседний `cls.control` помощника не зовёт."""
    return (f"{head_note}import unittest\n\n{import_line}\n\n\n"
            f"class {cls}(unittest.TestCase):\n\n"
            f"    def {method}(self):\n"
            f"        {helper}(self, compute())\n\n"
            f"    def {control}(self):\n"
            f"        self.assertTrue(ready())\n")


class HelperScopeSandbox(RealGitSandbox):
    """Клон артели и клоны двух учебных внешних проектов; задачи в
    `in_dev` с базой на основной ветке и головой в ветке задачи."""

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
        self.clones = {ARTEL: self.root,
                       BACKEND: make_project_repo(BACKEND),
                       FLAT: make_project_repo(FLAT)}
        self.conn = store.db()
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + EXT_ENTRY.format(name=BACKEND, base=config.MAIN_BRANCH,
                               lld="backend/tests", extra=BACKEND_EXTRA)
            + EXT_ENTRY.format(name=FLAT, base=config.MAIN_BRANCH,
                               lld="tests", extra=""),
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

    def klass(self, prefix: str) -> str:
        return f"{prefix}{self.word().capitalize()}Test"

    def value(self) -> int:
        return self.rng.randrange(1, 1000)

    def why(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # ------------------------------------------------------- задача и ветка

    def write(self, root, files: dict) -> None:
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit_base(self, target: str, files: dict) -> None:
        """Файлы `files` на основной ветке клона `target` и в его `origin`
        — до заведения рабочей копии задачи."""
        clone = str(self.clones[target])
        self.write(self.clones[target], files)
        self.git("-C", clone, "add", "-A")
        self.git("-C", clone, "commit", "-q", "-m", "база тестов")
        self.git("-C", clone, "push", "-q", "origin", config.MAIN_BRANCH)

    def new_task(self, target: str, base: dict, head: dict,
                 zones: str) -> str:
        """Задача `target` в `in_dev`: `base` — на основной ветке, `head` —
        коммит ветки задачи поверх неё (файл вне `head` не меняется);
        PLAN.md/SPEC.md — в ссылке документов."""
        self.commit_base(target, base)
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-pomoshchniki"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "in_dev", branch, target, config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task_id, zones=zones)
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

    # ---------------------------------------------------------- входы узла

    def entry_args(self, task_id: str) -> tuple:
        """(строка задачи, ветка документов, область профиля задачи) — те
        же значения, что передают `fsm_merge_gate` и `review`."""
        decision = project_profile.for_task(self.conn, task_id)
        self.assertIsNotNone(decision.profile, self.why(
            f"фикстура: профиль задачи не прочитан: {decision}"))
        docs, _foreign = artifact_source.resolve(self.conn, task_id)
        return (store.get_task(self.conn, task_id), docs,
                decision.profile.in_weakening_scope)

    def merge_gate(self, task_id: str) -> tuple:
        """(эскалировал ли гейт мержа, деталь эскалации, весь журнал)."""
        t, docs, scope = self.entry_args(task_id)
        escalated = test_integrity.merge_gate_escalates(
            self.conn, task_id, t["state"], t["branch"], docs, scope=scope)
        rows = store.task_steps(self.conn, task_id)
        detail = "\n".join(r["detail"] or "" for r in rows
                           if r["action"] == ESCALATED_ACTION)
        everything = "\n".join(f"{r['action']} | {r['detail'] or ''}"
                               for r in rows)
        return escalated, detail, everything

    def review(self, task_id: str) -> str:
        """Строки раздела ревью-пакета `review_lines` одной строкой."""
        t, docs, scope = self.entry_args(task_id)
        lines, unobserved, git_detail = test_integrity.review_lines(
            self.conn, task_id, t["branch"], docs, scope=scope)
        self.assertEqual("", git_detail, self.why(f"сбой git: {git_detail}"))
        return "\n".join(lines + unobserved)

    def advance(self, task_id: str) -> tuple:
        """(записи отказа гейта неослабления, все новые записи, вывод)."""
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


# AC-1 -----------------------------------------------------------------------

class RbacSupportAllEntriesTest(HelperScopeSandbox):

    def test_ac1_rbac_support_weakened_found_on_all_three_entries(self):
        """Помощник `backend/tests/rbac_support.py` бэкенд-проекта потерял утверждение — находка на рубеже, гейте мержа и в ревью-пакете.

        Учебный проект `workdir: backend`, `weakening_scope:
        [backend/tests/**/*.py]`. В базе `backend/tests/rbac_support.py`
        держит функцию `<fn>(test, value)` с `assertEqual(value, k)` и
        `assertIsNotNone(value)`; файл `backend/tests/test_<x>.py`
        (случайная глубина под `backend/tests/`) импортирует `from
        tests.rbac_support import <fn>`: метод `<C>::test_<m>` зовёт
        `<fn>(self, …)`, соседний `test_<k>` помощника не зовёт. В ветке
        задачи из помощника удалён `assertEqual`, файл теста не меняется.
        `advance` пишет отказ гейта неослабления, называющий
        `<C>::test_<m>`, задача остаётся в `in_dev`; строки
        `review_lines` называют `<C>::test_<m>`; гейт мержа эскалирует, и
        деталь эскалации называет `<C>::test_<m>`. Соседний метод ни в
        одном из трёх не назван.

        Ловит мутацию: `tests.rbac_support` переводится в
        `tests/rbac_support.py` без `workdir` — модуль не найден, находки
        нет ни на одном входе; вызывающие ищутся в `tests/`, а не по
        области профиля — вызывающий под `backend/tests/` не найден, отказа
        и эскалации нет; режим и профиль подставлены только в одном входе
        (например рубеже, а `review_lines`/`merge_gate_escalates` идут по
        артели) — отстающий вход находки не даёт; находка ставится всем
        методам файла — назван `test_<k>`.
        """
        fn, k = self.name("check_"), self.value()
        cls, method, control = self.klass("Rbac"), self.name("test_"), \
            self.name("test_")
        subdirs = "".join(f"{self.word(4)}/"
                          for _ in range(self.rng.randrange(0, 3)))
        caller = f"backend/tests/{subdirs}test_{self.word()}.py"
        task_id = self.new_task(
            BACKEND,
            {RBAC_SUPPORT: helper_module(fn, k, weakened=False),
             caller: caller_module(f"from tests.rbac_support import {fn}",
                                   cls, method, fn, control)},
            {RBAC_SUPPORT: helper_module(fn, k, weakened=True)},
            zones="backend/")
        found, other = f"{cls}{SEP}{method}", f"{cls}{SEP}{control}"

        with self.subTest(entry="рубеж in_dev → verifying"):
            refusals, text = self.advance(task_id)
            self.assertIn(found, refusals, self.why(
                f"рубеж не отказал находкой у {found}:\n{text}"))
            self.assertNotIn(other, refusals, self.why(text))
            self.assertEqual("in_dev",
                             store.get_task(self.conn, task_id)["state"],
                             self.why(text))

        with self.subTest(entry="review_lines"):
            lines = self.review(task_id)
            self.assertIn(found, lines, self.why(
                f"раздел ревью-пакета не называет {found}:\n{lines}"))
            self.assertNotIn(other, lines, self.why(lines))

        with self.subTest(entry="merge_gate_escalates"):
            escalated, detail, everything = self.merge_gate(task_id)
            self.assertTrue(escalated, self.why(
                f"гейт мержа не эскалировал:\n{everything}"))
            self.assertIn(found, detail, self.why(everything))
            self.assertNotIn(other, detail, self.why(everything))


# AC-2 -----------------------------------------------------------------------

class FlatProjectModuleHelperTest(HelperScopeSandbox):

    def test_ac2_flat_external_project_traces_any_scope_module(self):
        """Внешний проект с пустым `workdir`: функция `tests/<x>.py` (не `tests/sandbox.py`) потеряла утверждение — находка на вызывающем.

        Учебный проект без `workdir`, `weakening_scope: [tests/**/*.py]`.
        В базе `tests/<x>.py` держит `<fn>(test, value)` с `assertEqual` и
        `assertIsNotNone`; неизменённый `tests/test_<y>.py` по `from
        tests.<x> import <fn>` зовёт её из `<C>::test_<m>`, соседний
        `test_<k>` её не зовёт. В ветке из `<fn>` удалён `assertEqual`.
        Гейт мержа эскалирует, деталь называет `<C>::test_<m>`, соседний
        метод не назван.

        Ловит мутацию: режим внешнего проекта выводится из непустого
        `workdir` — при пустом `workdir` проект идёт по правилу артели
        (функции прослеживаются только из `tests/sandbox.py`), эскалации
        нет; функция чужого модуля области прослеживается только при
        `workdir` — то же.
        """
        mod, fn, k = self.name("rules_"), self.name("expect_"), self.value()
        cls, method, control = self.klass("Flat"), self.name("test_"), \
            self.name("test_")
        helper_path, caller = f"tests/{mod}.py", f"tests/test_{self.word()}.py"
        task_id = self.new_task(
            FLAT,
            {helper_path: helper_module(fn, k, weakened=False),
             caller: caller_module(f"from tests.{mod} import {fn}", cls,
                                   method, fn, control)},
            {helper_path: helper_module(fn, k, weakened=True)},
            zones="tests/")

        escalated, detail, everything = self.merge_gate(task_id)
        self.assertTrue(escalated, self.why(
            f"ослабление {helper_path}::{fn} не эскалировало мерж:\n"
            f"{everything}"))
        self.assertIn(f"{cls}{SEP}{method}", detail, self.why(everything))
        self.assertNotIn(f"{cls}{SEP}{control}", detail, self.why(everything))


# AC-3 -----------------------------------------------------------------------

class RelativeImportHelperTest(HelperScopeSandbox):

    def test_ac3_relative_import_resolved_with_workdir(self):
        """Бэкенд-проект: функция `backend/tests/…/<x>.py`, импортированная `from .<x> import <f>`, потеряла утверждение — находка на вызывающем.

        Учебный проект `workdir: backend`. В одном каталоге под
        `backend/tests/` (случайная глубина) — модуль `<x>.py` с
        `<f>(test, value)` (`assertEqual` и `assertIsNotNone`) и
        неизменённый `test_<y>.py`, где `<C>::test_<m>` зовёт `<f>` по
        относительному импорту `from .<x> import <f>`, соседний метод её
        не зовёт. В ветке из `<f>` удалён `assertEqual`. Гейт мержа
        эскалирует, деталь называет `<C>::test_<m>`, соседний не назван.

        Ловит мутацию: относительный импорт разрешается от пути от корня
        репозитория (`backend.tests.<x>`), а затем к нему ещё раз
        приписывается `workdir` — путь `backend/backend/tests/<x>.py`
        не найден, эскалации нет; относительный импорт у внешнего проекта
        не разрешается вовсе — то же.
        """
        subdirs = "".join(f"{self.word(4)}/"
                          for _ in range(self.rng.randrange(0, 3)))
        folder = f"backend/tests/{subdirs}"
        mod, fn, k = self.name("rel_"), self.name("f_"), self.value()
        cls, method, control = self.klass("Rel"), self.name("test_"), \
            self.name("test_")
        helper_path, caller = f"{folder}{mod}.py", \
            f"{folder}test_{self.word()}.py"
        task_id = self.new_task(
            BACKEND,
            {helper_path: helper_module(fn, k, weakened=False),
             caller: caller_module(f"from .{mod} import {fn}", cls, method,
                                   fn, control)},
            {helper_path: helper_module(fn, k, weakened=True)},
            zones="backend/")

        escalated, detail, everything = self.merge_gate(task_id)
        self.assertTrue(escalated, self.why(
            f"ослабление {helper_path}::{fn} по `from .{mod} import {fn}` "
            f"не эскалировало мерж:\n{everything}"))
        self.assertIn(f"{cls}{SEP}{method}", detail, self.why(everything))
        self.assertNotIn(f"{cls}{SEP}{control}", detail, self.why(everything))


# AC-4 -----------------------------------------------------------------------

class OutOfScopeModuleNotHelperTest(HelperScopeSandbox):

    def test_ac4_function_outside_weakening_scope_is_not_helper(self):
        """Бэкенд-проект: функция `backend/app/<x>.py` вне области потеряла утверждение — на вызывающем находки нет.

        Учебный проект `workdir: backend`, `weakening_scope:
        [backend/tests/**/*.py]`. В базе `backend/app/<x>.py` держит
        `<fa>(test, value)` с `assertEqual` и `assertIsNotNone`, тест
        `backend/tests/test_<y>.py` импортирует `from app.<x> import <fa>`
        и зовёт её из `<A>::test_<a>`. В ветке из `<fa>` удалён
        `assertEqual`, а в файл теста добавлена строка комментария — файл
        входит в дифф, и его утверждения сравниваются по модулям обеих
        сторон. Контроль в том же диффе: функция `<fc>` модуля области
        `backend/tests/<z>.py`, вызываемая из неизменённого
        `backend/tests/test_<w>.py` (`<B>::test_<b>`), тоже потеряла
        `assertEqual`. Гейт мержа эскалирует находкой контроля
        (`<B>::test_<b>` в детали), а `<A>::test_<a>` не назван нигде в
        журнале задачи.

        Ловит мутацию: у внешнего проекта помощником прослеживается
        функция любого модуля, к которому ведёт импорт (`app.<x>` →
        `backend/app/<x>.py`), без сверки пути с `weakening_scope` —
        утверждение `<fa>` базы теряется в голове, `<A>::test_<a>` назван
        в эскалации; сверка с областью идёт по пути без `workdir`
        (`app/<x>.py`) и потому всегда ложна — пропадает контрольная
        находка `<B>::test_<b>`.
        """
        app_mod, fa, ka = self.name("svc_"), self.name("grant_"), self.value()
        a_cls, a_method, a_control = self.klass("App"), self.name("test_"), \
            self.name("test_")
        app_path = f"backend/app/{app_mod}.py"
        a_caller = f"backend/tests/test_{self.word()}.py"
        z_mod, fc, kc = self.name("support_"), self.name("check_"), \
            self.value()
        b_cls, b_method, b_control = self.klass("Ctl"), self.name("test_"), \
            self.name("test_")
        z_path = f"backend/tests/{z_mod}.py"
        b_caller = f"backend/tests/test_{self.word()}.py"
        a_import = f"from app.{app_mod} import {fa}"
        task_id = self.new_task(
            BACKEND,
            {app_path: helper_module(fa, ka, weakened=False),
             a_caller: caller_module(a_import, a_cls, a_method, fa, a_control),
             z_path: helper_module(fc, kc, weakened=False),
             b_caller: caller_module(f"from tests.{z_mod} import {fc}", b_cls,
                                     b_method, fc, b_control)},
            {app_path: helper_module(fa, ka, weakened=True),
             a_caller: caller_module(a_import, a_cls, a_method, fa, a_control,
                                     head_note=f"# правка {self.word()}\n"),
             z_path: helper_module(fc, kc, weakened=True)},
            zones="backend/")

        escalated, detail, everything = self.merge_gate(task_id)
        self.assertTrue(escalated, self.why(
            f"контроль: ослабление {z_path}::{fc} не эскалировало мерж:\n"
            f"{everything}"))
        self.assertIn(f"{b_cls}{SEP}{b_method}", detail, self.why(everything))
        self.assertNotIn(f"{a_cls}{SEP}{a_method}", everything, self.why(
            f"функция {app_path} вне области прослежена помощником:\n"
            f"{everything}"))


# AC-5 -----------------------------------------------------------------------

class ArtelHelperOutcomesTest(HelperScopeSandbox):

    def test_ac5_artel_helper_outcomes_unchanged(self):
        """У артели пять прежних исходов помощников в одном диффе: находки (а), (б) есть, (в), (г), (д) — нет.

        Задача артели (`weakening_scope: [tests/**/*.py]` её профиля). В
        ветке теряют утверждение: (а) функция `<fa>` своего модуля
        `tests/test_<a>.py` без префикса `test_` (`assert value == k`),
        её зовёт `<A>::test_<a>` того же файла; (б) функция `<fb>`
        `tests/sandbox.py`, её по `from tests.sandbox import …` зовёт
        `<B>::test_<b>` неизменённого `tests/test_<b>.py`; (в) функция
        `<fv>` модуля `tests/<v>.py` (не `tests/sandbox.py`), её по `from
        tests.<v> import …` зовёт `<V>::test_<v>` неизменённого файла
        `tests/`; (г) функция своего модуля `test_<g>` с префиксом
        `test_`, её зовёт `<G>::test_<gm>` того же файла; (д) ту же
        функцию `<fb>` `tests/sandbox.py` зовёт `<D>::test_<d>`
        неизменённого файла вне `tests/` (`kod/test_<d>.py`). Гейт мержа
        эскалирует; деталь называет `<A>::test_<a>` и `<B>::test_<b>`;
        `<V>::test_<v>`, `<G>::test_<gm>` и `<D>::test_<d>` в журнале
        задачи не названы.

        Ловит мутацию: режим внешнего проекта включён и для артели (или
        выводится из пустого `workdir`) — функция `tests/<v>.py`
        прослеживается, `<V>::test_<v>` назван; функции своего модуля
        выпадают из сбора при переводе на область — нет `<A>::test_<a>`;
        функции `tests/sandbox.py` перестают прослеживаться у артели —
        нет `<B>::test_<b>`; снят отсев префикса `test_` — назван
        `<G>::test_<gm>`; вызывающие у артели ищутся по всему
        репозиторию без отсева области — назван `<D>::test_<d>`.
        """
        names = {key: (self.klass(key.upper()), self.name("test_"))
                 for key in ("a", "b", "v", "g", "d")}
        k = self.value()

        def address(key: str) -> str:
            return f"{names[key][0]}{SEP}{names[key][1]}"

        def one_method(import_line: str, key: str, call: str,
                       prelude: str = "") -> str:
            cls, method = names[key]
            return (f"import unittest\n\n{import_line}\n{prelude}\n\n"
                    f"class {cls}(unittest.TestCase):\n\n"
                    f"    def {method}(self):\n"
                    f"        {call}\n")

        fa, fb, fv, fg = (self.name("own_"), self.name("sb_"),
                          self.name("other_"), self.name("test_"))
        v_mod = self.name("helpers_")

        def own_module(fn: str, key: str, weakened: bool) -> str:
            body = "    use(value)\n" if weakened else \
                f"    assert value == {k}\n    use(value)\n"
            return one_method("", key, f"{fn}(compute())",
                              prelude=f"\n\ndef {fn}(value):\n{body}")

        path_a = f"tests/test_{self.word()}.py"
        path_g = f"tests/test_{self.word()}.py"
        sandbox_path = "tests/sandbox.py"
        v_path = f"tests/{v_mod}.py"
        sandbox_import = f"from tests.sandbox import {fb}"
        base = {
            path_a: own_module(fa, "a", weakened=False),
            sandbox_path: helper_module(fb, k, weakened=False),
            f"tests/test_{self.word()}.py": one_method(
                sandbox_import, "b", f"{fb}(self, compute())"),
            v_path: helper_module(fv, k, weakened=False),
            f"tests/test_{self.word()}.py": one_method(
                f"from tests.{v_mod} import {fv}", "v",
                f"{fv}(self, compute())"),
            path_g: own_module(fg, "g", weakened=False),
            f"kod/test_{self.word()}.py": one_method(
                sandbox_import, "d", f"{fb}(self, compute())"),
        }
        head = {path_a: own_module(fa, "a", weakened=True),
                sandbox_path: helper_module(fb, k, weakened=True),
                v_path: helper_module(fv, k, weakened=True),
                path_g: own_module(fg, "g", weakened=True)}
        task_id = self.new_task(ARTEL, base, head, zones="tests/")

        escalated, detail, everything = self.merge_gate(task_id)
        self.assertTrue(escalated, self.why(
            f"ослабление помощников артели не эскалировало мерж:\n"
            f"{everything}"))
        for case, key, expected in (
                ("(а) функция своего модуля", "a", True),
                ("(б) функция tests/sandbox.py", "b", True),
                ("(в) функция другого модуля tests/", "v", False),
                ("(г) функция своего модуля с префиксом test_", "g", False),
                ("(д) вызывающий вне tests/", "d", False)):
            with self.subTest(case=case):
                if expected:
                    self.assertIn(address(key), detail, self.why(
                        f"{case}: нет находки у {address(key)}:\n"
                        f"{everything}"))
                else:
                    self.assertNotIn(address(key), everything, self.why(
                        f"{case}: находка у {address(key)}:\n{everything}"))


if __name__ == "__main__":
    unittest.main()
