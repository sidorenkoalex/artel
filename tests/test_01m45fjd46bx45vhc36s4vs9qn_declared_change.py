"""Смена ожидания в существующем тесте по разделу SPEC «Меняемое поведение»:
сверка раздела на approve гейта SPEC, различение смены ожидания и
ослабления на рубежах `in_dev -> verifying` и гейта мержа, строгость,
двусторонний прогон, храповик, журнал рубежей и раздел ревью-пакета (AC-2
на `advance`, AC-3..AC-27).

Группа: долгоживущий

Красен до реализации: approve раздел «Меняемое поведение» не сверяет и
записи «объявлена смена поведения тестов» не пишет; изменённые утверждения
гейт неослабления только наблюдает — переход и мерж от них не зависят,
записей «утверждения тестов: исход рубежа» и «двусторонний прогон
пройден» нет, двусторонний прогон не запускается, ревью-пакет несёт
прежний текст «переход и мерж от них не зависят»; `advance` из
`spec_writing` форму раздела не проверяет. Сценарии «не находка»
(`test_ac5_added_and_reordered_assertions_are_no_change`) и «канарейка и
внешний target» (`test_ac12_*`) держат сегодняшнее поведение рядом с
новым и зелёны с рождения; `test_ac25_merge_gate_runs_no_pytest_*` красен
на второй половине (сдвиг головы не эскалирует). Храповика нет:
функции `test_integrity.ratchet_finding` нет — `test_ac26_*` её класса
падают на `AttributeError`, а покрытая мандатом убыль в журнале
разрешения не несёт чисел «было → стало».

AC-26 проверяется двумя тестами по решению Оператора (ANSWER-1 задачи):
через рубеж — покрытая мандатом убыль уходит в журнал «ослабление тестов
разрешено мандатом Оператора» с числами и файлом, переход проходит; на
уровне функции храповика — убыль без мандата даёт находку, мандат на файл
её снимает (при требованиях 5 и 12 убыль как единственная непокрытая
находка прохода через полный рубеж недостижима). Оба теста AC-26
провалидированы стабом в памяти процесса (код не правился): стаб
`ratchet_finding` по `guard.qualified_test_methods`/`guard.test_assertions`
зелен на 20 зёрнах, его мутант без сравнения итога «head не меньше base»
красен; обёртка `test_integrity.uncovered`, добавляющая находку храповика
при пустом остатке и снимающая её мандатом в журнал разрешения, зелена на
6 зёрнах (обе формы убыли).

Песочница — `tests.sandbox.GitignoreCommittedRealGitSandbox`: пульт и
клон артели — один настоящий git-репозиторий `self.root`, голый origin
(`add_synced_origin`). База — коммит на main с `app.py` и файлом тестов
фикстуры; задача артели заводится `catalog.cmd_new`; SPEC (с разделом
«Меняемое поведение» или без него), PLAN и зелёная планка коммитятся в
ссылку документов задачи; `approve` на `spec_gate` — `fsm.cmd_approve`;
голова — коммит в рабочей копии задачи, отправленный в origin; переход —
`fsm.cmd_advance` из `in_dev` (все рубежи перехода настоящие); гейт мержа —
публичный `test_integrity.merge_gate_escalates`; ревью-пакет —
`review.review_package`; мандат — `ANSWER-1.md` в ссылке документов
коммитом ответа Оператора. Двусторонний прогон идёт настоящим pytest:
тесты фикстуры сверяют `app.VALUE`, база и голова дают разные значения.
Где свойство наблюдаемо только на запуске процессов (таймаут pytest, сбой
`git worktree add`, исключение, «pytest не запускался»), подменяется
`subprocess.Popen` обёрткой поверх настоящего: она запоминает каждый
запуск и подменяет только нужный. Имя файла тестов, имя класса, значения
литералов и номера требований — из `random`; зерно печатается и входит в
текст каждого провала.

Стаб полной реализации (approve, узел различения, строгость, двусторонний
прогон, храповик, ревью-пакет — шесть модулей) не строился; обвязка
проверена на сегодняшнем коде отдельно: отказ перехода и эскалация мержа
на исчезнувшем методе читаются `refusal`/`merge_gate`, мандат `ANSWER-1`
принимается, ревью-пакет несёт прежнюю строку наблюдения, подмены
запусков дают `TimeoutExpired` и код 128 с меткой, а фикстуры
двустороннего прогона в настоящем pytest падают ровно так, как задумано
(AssertionError с обеих сторон; зелёная новая версия на базе и старая на
ветке; ImportError при сборке, AttributeError в `setUp`,
ZeroDivisionError в call).
"""
import contextlib
import io
import os
import random
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (artifact_source, catalog, config, fsm, fsm_advance,
                          projects, review, store, workspace)
from orchestrator.advance_gates import test_integrity
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox, declare_target

DOCS_REF_PREFIX = "refs/artifacts/"

DECLARED_ACTION = "объявлена смена поведения тестов"
OUTCOME_ACTION = "утверждения тестов: исход рубежа"
TWO_SIDED_ACTION = "двусторонний прогон пройден"
OBSERVATION_ACTION = "изменены утверждения тестов (наблюдение)"
REFUSAL_ACTION = test_integrity.TEST_INTEGRITY_REFUSAL_ACTION
ALLOWED_ACTION = test_integrity.TEST_INTEGRITY_ALLOWED_ACTION
MARKER = test_integrity.TEST_WEAKENING_MANDATE_MARKER
APPROVE_REFUSED = "approve отклонён"
OUTSIDE = "смена вне раздела «Меняемое поведение»"
MISMATCH = "смена не совпала с объявленным"
COMPUTED = "литерал заменён вычисленным значением"
UNRATED = "правило не умеет оценить строгость"
EXPECTATION = "смена ожидания по SPEC (требование {n})"
NOT_PROOF = "не доказательство"
NEW_ON_BASE = "новая версия на базе"
OLD_ON_BRANCH = "старая версия на ветке"
TWO_SIDED_MISSING = "двусторонний прогон для текущей головы не записан"
CHANGED = "утверждения изменены в"
REVIEW_SECTION = "Изменённые утверждения тестов"
OLD_REVIEW_TEXT = "переход и мерж от них не зависят"
NEW_REVIEW_TEXT = ("смена утверждений вне раздела «Меняемое поведение» SPEC "
                   "и ослабление отказывают переходу in_dev -> verifying и "
                   "эскалируют гейт мержа до мандата Оператора")
WEAKENING = re.compile(r"ослаблени\w*\s*:\s*\S")
PASSED = re.compile(r"(?<!не )пройден")
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


def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def method_text(name: str, lines: list) -> str:
    """Метод фикстуры с заявкой мутации (её требует соседний гейт перехода)."""
    body = "".join(f"        {line}\n" for line in lines)
    return (f"\n    def {name}(self):\n"
            f'        """Фикстура {name}.\n\n'
            f"        Ловит мутацию: фикстура песочницы.\n"
            f'        """\n{body}')


def fixture_source(cls: str, methods: dict, header: str = "") -> str:
    """Файл тестов фикстуры: класс `cls`, {имя метода: [строки тела]}."""
    text = f"import unittest\n\nimport app\n{header}\n\nclass {cls}(unittest.TestCase):\n"
    for name, lines in methods.items():
        text += method_text(name, lines)
    return text


def pairs_text(pairs: list) -> str:
    return "; ".join(f"`{old}` → `{new}`" for old, new in pairs)


def segment(text: str, name: str, names) -> str:
    """Кусок `text` от первого вхождения `name` до первого вхождения
    любого другого имени из `names` после него (или до конца); пусто —
    `name` в тексте нет."""
    start = text.find(name)
    if start < 0:
        return ""
    end = len(text)
    for other in names:
        if other == name:
            continue
        pos = text.find(other, start + len(name))
        if 0 <= pos < end:
            end = pos
    return text[start:end]


class TimeoutProc:
    """Процесс, у которого истекает любое ожидание с таймаутом."""

    def __init__(self, args):
        self.args = args
        self.returncode = None
        self.pid = 0
        self.stdin = self.stdout = self.stderr = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def communicate(self, input=None, timeout=None):
        raise subprocess.TimeoutExpired(self.args, timeout or 0)

    def wait(self, timeout=None):
        if timeout is not None:
            raise subprocess.TimeoutExpired(self.args, timeout)
        self.returncode = -9
        return -9

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    terminate = kill


def is_pytest_node(argv: list) -> bool:
    """Запуск pytest по узлу `<файл>.py::…` (не прогон каталога планки)."""
    return any("pytest" in a for a in argv) and any(".py::" in a for a in argv)


def is_worktree_add(argv: list) -> bool:
    return bool(argv) and argv[0].rsplit("/", 1)[-1] == "git" \
        and "worktree" in argv and "add" in argv


def worktree_add_path(argv: list) -> str:
    after = argv[argv.index("add") + 1:]
    paths = [a for a in after if not a.startswith("-")]
    return paths[0] if paths else ""


class SpawnSpy:
    """Обёртка над настоящим `subprocess.Popen`: запоминает (argv, cwd)
    каждого запуска; `rule(argv)` может вернуть замену — callable того же
    вида, что `Popen`."""

    def __init__(self, real, rule=None):
        self.real = real
        self.rule = rule
        self.calls: list = []

    def __call__(self, args, *rest, **kwargs):
        argv = [str(a) for a in args] if isinstance(args, (list, tuple)) \
            else [str(args)]
        self.calls.append((argv, str(kwargs.get("cwd") or "")))
        substitute = self.rule(argv) if self.rule else None
        if substitute is not None:
            return substitute(args, *rest, **kwargs)
        return self.real(args, *rest, **kwargs)

    def pytest_nodes(self) -> list:
        return [(argv, cwd) for argv, cwd in self.calls if is_pytest_node(argv)]

    def pytest_any(self) -> list:
        return [argv for argv, _cwd in self.calls
                if any("pytest" in a for a in argv)]

    def worktree_adds(self) -> list:
        return [argv for argv, _cwd in self.calls if is_worktree_add(argv)]


class DeclaredChangeSandbox(GitignoreCommittedRealGitSandbox):
    """Задача артели от `spec_gate` до `in_dev`: база на main, SPEC с
    разделом «Меняемое поведение» в ссылке документов, голова в рабочей
    копии задачи и в origin."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.cls = f"Fx{word(self.rng).capitalize()}Test"
        self.path = f"tests/test_fx_{word(self.rng)}.py"
        self.origin = self.add_synced_origin()
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
        self.branch = ""
        self.wt = None

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

    def name(self, method: str) -> str:
        return f"{self.cls}::{method}"

    def full(self, method: str) -> str:
        return f"{self.path}::{self.cls}::{method}"

    def line(self, method: str, pairs: list, req: int) -> str:
        """Строка раздела «Меняемое поведение» (требование 1 SPEC)."""
        return f"- `{self.full(method)}`: {pairs_text(pairs)} (требование {req})"

    def spec_text(self, section) -> str:
        requirements = "\n".join(f"{n}. Требование фикстуры номер {n}."
                                 for n in range(1, REQUIREMENTS + 1))
        body = "" if section is None else (
            "\n## Меняемое поведение\n\nСмены ожидания фикстуры.\n\n"
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
        # Сдвиг ссылки документов сценарием — правка Оператора, не мимо пульта.
        store.record_fixation(store.db(), self.task_id)

    # --- сценарий ------------------------------------------------------

    def start(self, base: dict, section, approve: bool = True) -> str:
        """База на main, задача, документы; `approve` на `spec_gate` (если
        `approve`) — вывод approve."""
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
        self.branch = self.row()["branch"]
        if not self.git("branch", "--list", self.branch).strip():
            self.git("branch", self.branch, config.MAIN_BRANCH)
        self.wt, error = workspace.ensure(self.task_id, self.branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.commit_docs({"SPEC.md": self.spec_text(section),
                          "PLAN.md": PLAN_TEXT.format(task=self.task_id),
                          "acceptance_tests/test_plank.py": PLANK_TEXT},
                         "документы задачи")
        store.update_task(store.db(), self.task_id, state="spec_gate")
        store.record_fixation(store.db(), self.task_id)
        if not approve:
            return ""
        return self.approve()

    def approve(self) -> str:
        store.record_fixation(store.db(), self.task_id)
        return self.run_cmd(fsm.cmd_approve, self.task_id)

    def edit_spec(self, section) -> None:
        self.commit_docs({"SPEC.md": self.spec_text(section)}, "правка SPEC")

    def to_in_dev(self) -> None:
        store.update_task(store.db(), self.task_id,
                          tests_locked_sha=self.docs_head(), state="in_dev",
                          draft_mr_created=1)
        store.record_fixation(store.db(), self.task_id)

    def head(self, files: dict, message: str = "голова") -> None:
        for rel, text in files.items():
            target = self.wt / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self.git("-C", str(self.wt), "add", "-A")
        self.git("-C", str(self.wt), "commit", "-q", "-m", message)
        self.git("push", "-q", "-f", "origin", f"{self.branch}:{self.branch}")

    def head_sha(self) -> str:
        return self.git("rev-parse", f"refs/heads/{self.branch}").strip()

    def mandate(self, elements: str) -> None:
        """`ANSWER-1.md` с мандатом ослабления — коммит ответа Оператора."""
        self.commit_docs({"ANSWER-1.md": f"# Ответ Оператора\n\n{MARKER} "
                                         f"{elements}\nОснование: решение "
                                         f"Оператора ({self.seed}).\n"},
                         f"{self.task_id}: ANSWER-1 — ответ Оператора")

    def advance(self) -> str:
        return self.run_cmd(fsm.cmd_advance, self.task_id)

    def scenario(self, base: dict, head: dict, section,
                 elements: str = "") -> str:
        """База, approve, `in_dev`, голова, мандат (если `elements`) и
        `advance` — вывод advance."""
        out = self.start(base, section)
        self.assertEqual(self.state(), "tests_writing",
                         self.note(f"предпосылка: approve не прошёл:\n{out}"))
        self.to_in_dev()
        self.head(head)
        if elements:
            self.mandate(elements)
        return self.advance()

    @contextlib.contextmanager
    def spawn_spy(self, rule=None):
        spy = SpawnSpy(subprocess.Popen, rule)
        with mock.patch.object(subprocess, "Popen", spy):
            yield spy

    def row(self):
        return store.get_task(store.db(), self.task_id)

    def state(self) -> str:
        return self.row()["state"]

    def steps(self) -> list:
        return [(s["id"], s["action"], s["detail"] or "")
                for s in store.task_steps(store.db(), self.task_id)]

    def details(self, action: str) -> list:
        return [detail for _id, act, detail in self.steps() if act == action]

    def journal_text(self) -> str:
        return "\n".join(f"{act} | {detail}" for _id, act, detail in self.steps())

    def refusal(self) -> str:
        found = self.details(REFUSAL_ACTION)
        return found[-1] if found else ""

    def outcome(self) -> str:
        found = self.details(OUTCOME_ACTION)
        return found[-1] if found else ""

    def merge_gate(self) -> bool:
        docs, _foreign = artifact_source.resolve(store.db(), self.task_id)
        return test_integrity.merge_gate_escalates(
            store.db(), self.task_id, self.state(), self.branch, docs)

    def review_text(self) -> str:
        return review.review_package(store.db(), self.task_id,
                                     self.row()["title"], self.branch)["text"]

    def worktree_paths(self) -> set:
        out = self.git("worktree", "list", "--porcelain")
        return {line.split(" ", 1)[1] for line in out.splitlines()
                if line.startswith("worktree ")}

    # --- фикстуры двустороннего прогона --------------------------------

    def value_change(self, base_value, head_value, old, new,
                     method: str = "test_value") -> tuple:
        """(база, голова): `app.VALUE` = `base_value`/`head_value`, метод
        `method` сверяет `app.VALUE` с `old`/`new`."""
        base = {"app.py": f"VALUE = {base_value!r}\n",
                self.path: fixture_source(self.cls, {
                    method: [f"self.assertEqual(app.VALUE, {old!r})"]})}
        head = {"app.py": f"VALUE = {head_value!r}\n",
                self.path: fixture_source(self.cls, {
                    method: [f"self.assertEqual(app.VALUE, {new!r})"]})}
        return base, head

    def two_values(self) -> tuple:
        old = self.rng.randrange(10, 500)
        return old, old + self.rng.randrange(1, 500)

    def two_words(self) -> tuple:
        old = f"было-{word(self.rng)}"
        return old, f"стало-{word(self.rng)}"

    def declared_value(self, base_value=None, head_value=None,
                       n: int = 2) -> tuple:
        """Задача в `in_dev` с объявленной сменой литерала `test_value`
        (`old` -> `new`); `app.VALUE` на базе и на ветке — `base_value`/
        `head_value` (по умолчанию `old`/`new`). Возврат — (old, new)."""
        old, new = self.two_values()
        base, head = self.value_change(
            old if base_value is None else base_value(old, new),
            new if head_value is None else head_value(old, new), old, new)
        out = self.start(base, [self.line("test_value", [(repr(old), repr(new))], n)])
        self.assertEqual(self.state(), "tests_writing",
                         self.note(f"предпосылка: approve не прошёл:\n{out}"))
        self.to_in_dev()
        self.head(head)
        return old, new

    def undeclared_scenario(self) -> tuple:
        """Смена литерала в методе вне перечня; раздел — от зерна: нет
        вовсе либо называет другой (неизменённый) метод."""
        old, new = self.two_values()
        base = {"app.py": f"VALUE = {old}\n", self.path: fixture_source(self.cls, {
            "test_value": [f"self.assertEqual(app.VALUE, {old})"],
            "test_kept": ["self.assertTrue(app.VALUE)"]})}
        head = {"app.py": f"VALUE = {new}\n", self.path: fixture_source(self.cls, {
            "test_value": [f"self.assertEqual(app.VALUE, {new})"],
            "test_kept": ["self.assertTrue(app.VALUE)"]})}
        section = None if self.rng.random() < 0.5 else [
            self.line("test_kept", [("1", "2")], 1)]
        return base, head, section


# ---------------------------------------------------------------------------
# AC-2 (вторая половина): форма раздела на `advance` из `spec_writing`.

class SpecWritingFormTest(DeclaredChangeSandbox):

    def test_ac2_spec_writing_advance_refuses_line_without_class(self):
        """SPEC со строкой раздела без класса не уходит из `spec_writing`, отказ называет строку.

        Сценарий: SPEC в ссылке документов несёт годную строку раздела и
        строку `путь::метод` без класса со случайным именем метода; задача
        в `spec_writing`, `advance`. Задача остаётся в `spec_writing`, а
        вывод либо журнал называют негодную строку (имя её метода).

        Ловит мутацию: проверка формы раздела подключена только к CLI
        `guard.py`, а не к переходу `spec_writing -> spec_gate` — задача
        уходит на `spec_gate`; имя без класса принимается за годное — то же.
        """
        good = self.rng.choice(["test_value", "test_other"])
        bad = f"test_noclass_{word(self.rng)}"
        old, new = self.two_values()
        base = {"app.py": "VALUE = 1\n",
                self.path: fixture_source(self.cls, {
                    good: ["self.assertEqual(app.VALUE, 1)"],
                    bad: ["self.assertTrue(app.VALUE)"]})}
        section = [self.line(good, [(repr(old), repr(new))], 1),
                   f"- `{self.path}::{bad}`: `{old!r}` → `{new!r}` (требование 2)"]
        self.start(base, section, approve=False)
        store.update_task(store.db(), self.task_id, state="spec_writing")
        out = self.advance()
        context = self.note(f"вывод:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "spec_writing", context)
        self.assertIn(bad, out + self.journal_text(), context)


# ---------------------------------------------------------------------------
# AC-3, AC-4: approve гейта SPEC сверяет раздел с main.

class ApproveDeclaredTest(DeclaredChangeSandbox):

    def base_two(self) -> dict:
        return {"app.py": "VALUE = 1\n",
                self.path: fixture_source(self.cls, {
                    "test_first": ["self.assertEqual(app.VALUE, 1)"],
                    "test_second": ["self.assertIn('a', 'abc')",
                                    "self.assertEqual(app.VALUE, 1)"]})}

    def assert_soft_refusal(self, out: str, named: str) -> None:
        context = self.note(f"вывод approve:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "spec_gate", context)
        refused = [d for d in self.details(APPROVE_REFUSED) if d.strip()]
        self.assertTrue(refused, context)
        self.assertIn(named, refused[-1], context)
        self.assertEqual(self.details(DECLARED_ACTION), [], context)

    def test_ac3_missing_method_in_main_refuses_approve(self):
        """Раздел называет метод, которого в файле на main нет, — мягкий отказ approve с именем метода.

        Сценарий: файл тестов на main есть, в разделе — годная строка и
        строка о методе со случайным именем, которого в файле нет.
        `approve` оставляет задачу на `spec_gate`, запись «approve
        отклонён» называет отсутствующий метод, записи «объявлена смена
        поведения тестов» нет.

        Ловит мутацию: сверка с main проверяет только существование файла —
        approve проходит в `tests_writing`; метод ищется голым именем без
        класса — тоже проходит, если такой метод есть в другом классе.
        """
        missing = f"test_missing_{word(self.rng)}"
        old, new = self.two_values()
        section = [self.line("test_first", [(repr(1), repr(old))], 1),
                   self.line(missing, [(repr(old), repr(new))], 2)]
        out = self.start(self.base_two(), section)
        self.assert_soft_refusal(out, missing)

    def test_ac3_missing_file_in_main_refuses_approve(self):
        """Раздел называет метод в файле, которого на main нет, — мягкий отказ approve с именем метода.

        Ловит мутацию: отсутствующий файл на main читается как «сверять
        нечего» и строка пропускается — approve проходит в `tests_writing`.
        """
        ghost = f"tests/test_ghost_{word(self.rng)}.py"
        method = f"test_ghost_{word(self.rng)}"
        section = [f"- `{ghost}::{self.cls}::{method}`: `1` → `2` (требование 3)"]
        out = self.start(self.base_two(), section)
        self.assert_soft_refusal(out, method)

    def test_ac3_git_silence_on_main_refuses_approve(self):
        """Ветки main в репозитории задачи нет — git молчит, approve мягко отказывает с причиной.

        Сценарий: после посева main переименована, ссылка `origin/main`
        удалена; раздел годный. `approve` оставляет задачу на `spec_gate`,
        есть непустая запись «approve отклонён», записи «объявлена смена
        поведения тестов» нет.

        Ловит мутацию: молчание git при чтении main трактуется как «метод
        есть» (fail-open) — approve проходит и пишет запись объявления.
        """
        section = [self.line("test_first", [("1", "2")], 1)]
        self.start(self.base_two(), section, approve=False)
        self.git("branch", "-m", config.MAIN_BRANCH, f"moved-{word(self.rng)}")
        self.git("update-ref", "-d", f"refs/remotes/origin/{config.MAIN_BRANCH}")
        out = self.approve()
        context = self.note(f"вывод approve:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "spec_gate", context)
        refused = [d for d in self.details(APPROVE_REFUSED) if d.strip()]
        self.assertTrue(refused, context)
        self.assertEqual(self.details(DECLARED_ACTION), [], context)

    def test_ac4_approve_journals_one_declaration_with_pairs_and_requirements(self):
        """Успешный approve пишет одну запись объявления: каждый метод, его пары и номер требования.

        Сценарий: два метода — с одной парой и с двумя парами «было →
        стало» (строковые литералы из случайных букв), номера требований
        случайны. Задача уходит в `tests_writing`, запись «объявлена смена
        поведения тестов» ровно одна, её кусок о каждом методе называет все
        его литералы и номер требования.

        Ловит мутацию: запись пишется на каждую строку раздела — записей
        две; вторая пара строки теряется при разборе `; ` — литералов
        второй пары в записи нет; номер требования не переносится — его
        цифры в куске метода нет.
        """
        a1, b1 = self.two_words()
        a2, b2 = self.two_words()
        a3, b3 = self.two_words()
        r1, r2 = self.rng.sample(range(2, REQUIREMENTS + 1), 2)
        section = [self.line("test_first", [(repr(a1), repr(b1))], r1),
                   self.line("test_second", [(repr(a2), repr(b2)),
                                             (repr(a3), repr(b3))], r2)]
        out = self.start(self.base_two(), section)
        context = self.note(f"вывод approve:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "tests_writing", context)
        records = self.details(DECLARED_ACTION)
        self.assertEqual(len(records), 1, context)
        names = (self.name("test_first"), self.name("test_second"))
        first = segment(records[0], names[0], names)
        second = segment(records[0], names[1], names)
        for text, expected in ((first, (a1, b1, str(r1))),
                               (second, (a2, b2, a3, b3, str(r2)))):
            for item in expected:
                self.assertIn(item, text, self.note(
                    f"нет «{item}» в куске записи: {text!r}; запись: {records[0]}"))

    def test_ac4_approve_without_section_writes_no_declaration(self):
        """SPEC без раздела: approve проходит в `tests_writing` без записи объявления.

        Ловит мутацию: запись объявления пишется и на пустом перечне —
        появляется запись «объявлена смена поведения тестов»; отсутствие
        раздела считается ошибкой сверки — approve отклонён.
        """
        out = self.start(self.base_two(), None)
        context = self.note(f"вывод approve:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "tests_writing", context)
        self.assertEqual(self.details(DECLARED_ACTION), [], context)


# ---------------------------------------------------------------------------
# AC-5: различение смены ожидания, ослабления и «смены нет».

class DistinctionTest(DeclaredChangeSandbox):

    def test_ac5_literal_change_is_expectation_change_with_actual_pair(self):
        """Смена только литерала — смена ожидания: отказ несовпадения называет фактическую пару.

        Сценарий: метод из раздела, в нём единственная правка — строковый
        литерал `было-…` -> `стало-…`; объявлена иная пара. Отказ перехода
        называет метод, причину «смена не совпала с объявленным» и оба
        фактических литерала, а не «ослабление».

        Ловит мутацию: маскирование литералов не делается и правка
        литерала уходит в «иную смену» — причина «ослабление», пары нет;
        фактическая пара берётся не из позиции константы — литералов в
        отказе нет.
        """
        old, new = self.two_words()
        other = f"иное-{word(self.rng)}"
        base = {"app.py": "VALUE = 1\n", self.path: fixture_source(self.cls, {
            "test_word": [f"self.assertEqual(app.VALUE, {old!r})"]})}
        head = {"app.py": "VALUE = 1\n", self.path: fixture_source(self.cls, {
            "test_word": [f"self.assertEqual(app.VALUE, {new!r})"]})}
        out = self.scenario(base, head, [
            self.line("test_word", [(repr(old), repr(other))], 2)])
        detail = self.refusal()
        context = self.note(f"отказ: {detail}\nвывод:\n{out}")
        self.assertEqual(self.state(), "in_dev", context)
        self.assertIn(self.name("test_word"), detail, context)
        self.assertIn(MISMATCH, detail, context)
        self.assertIn(old, detail, context)
        self.assertIn(new, detail, context)
        self.assertNotRegex(detail, WEAKENING, context)

    def test_ac5_kind_change_removed_and_call_are_weakening(self):
        """Смена вида утверждения, удаление утверждения и литерал -> вызов — ослабление/иная смена.

        Сценарий: пять методов из раздела (каждому объявлена своя пара):
        `assertEqual` -> `assertIn`, -> `assertTrue`, -> `assertIsNotNone`;
        удалённое из двух утверждение; литерал -> вызов функции. Отказ
        перехода называет каждый метод с причиной «ослабление: <признак>»,
        ни один — «смена не совпала с объявленным».

        Ловит мутацию: маскированная форма сравнивается без имени вида
        утверждения — смена вида признаётся сменой ожидания и уходит в
        «не совпала»; удаление утверждения при R ⊂ base не находка; вызов
        на месте литерала маскируется как литерал.
        """
        v = self.rng.randrange(10, 99)
        base_methods = {
            "test_to_in": [f"self.assertEqual(app.VALUE, {v})"],
            "test_to_true": [f"self.assertEqual(app.VALUE, {v})"],
            "test_to_not_none": [f"self.assertEqual(app.VALUE, {v})"],
            "test_removed": [f"self.assertEqual(app.VALUE, {v})",
                             "self.assertTrue(app.VALUE)"],
            "test_to_call": [f"self.assertEqual(app.VALUE, {v})"],
        }
        head_methods = {
            "test_to_in": [f"self.assertIn(app.VALUE, [{v}])"],
            "test_to_true": ["self.assertTrue(app.VALUE)"],
            "test_to_not_none": ["self.assertIsNotNone(app.VALUE)"],
            "test_removed": ["self.assertTrue(app.VALUE)"],
            "test_to_call": ["self.assertEqual(app.VALUE, expected())"],
        }
        header = f"\n\ndef expected():\n    return {v}\n"
        base = {"app.py": f"VALUE = {v}\n",
                self.path: fixture_source(self.cls, base_methods, header)}
        head = {"app.py": f"VALUE = {v}\n",
                self.path: fixture_source(self.cls, head_methods, header)}
        section = [self.line(m, [(str(v), str(v + 1))], 1 + i % REQUIREMENTS)
                   for i, m in enumerate(base_methods)]
        out = self.scenario(base, head, section)
        detail = self.refusal()
        names = [self.name(m) for m in base_methods]
        for name in names:
            part = segment(detail, name, names)
            context = self.note(f"{name}: {part!r}\nотказ: {detail}\nвывод:\n{out}")
            self.assertTrue(part, context)
            self.assertRegex(part, WEAKENING, context)
            self.assertNotIn(MISMATCH, part, context)

    def test_ac5_added_and_reordered_assertions_are_no_change(self):
        """Только добавленное и только переставленные утверждения — смены нет, переход проходит.

        Сценарий: раздела нет; в одном методе добавлено утверждение, в
        другом два утверждения переставлены, `app.py` изменён. Переход
        доходит до `verifying`, записи отказа гейта неослабления нет.

        Ловит мутацию: R считается разницей множеств head и base в обе
        стороны (A без R) — добавленное утверждение становится «сменой
        вне раздела» и переход отклонён; сравнение по позициям вместо
        мультимножеств — перестановка становится находкой.
        """
        v = self.rng.randrange(10, 99)
        base = {"app.py": f"VALUE = {v}\n", self.path: fixture_source(self.cls, {
            "test_added": [f"self.assertEqual(app.VALUE, {v})"],
            "test_reordered": [f"self.assertEqual(app.VALUE, {v})",
                               "self.assertTrue(app.VALUE)"]})}
        head = {"app.py": f"VALUE = {v}\nEXTRA = {v + 1}\n",
                self.path: fixture_source(self.cls, {
                    "test_added": [f"self.assertEqual(app.VALUE, {v})",
                                   f"self.assertEqual(app.EXTRA, {v + 1})"],
                    "test_reordered": ["self.assertTrue(app.VALUE)",
                                       f"self.assertEqual(app.VALUE, {v})"]})}
        out = self.scenario(base, head, None)
        context = self.note(f"вывод:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "verifying", context)
        self.assertEqual(self.refusal(), "", context)


# ---------------------------------------------------------------------------
# AC-6..AC-11: исходы рубежей.

class OutcomeTest(DeclaredChangeSandbox):

    def test_ac6_declared_literal_change_passes_and_journals_outcome(self):
        """Объявленная смена литерала с совпавшей парой и доказанным двусторонним прогоном проходит переход.

        Сценарий: `app.VALUE` и литерал метода сменены одинаково
        (случайные числа), пара объявлена в разделе с номером требования N.
        Переход доходит до `verifying`; запись «утверждения тестов: исход
        рубежа» называет `путь::Класс::метод` с исходом «смена ожидания по
        SPEC (требование N)».

        Ловит мутацию: изменённые утверждения влиты в узел отказа без
        исключения для объявленных — переход отклонён «смена вне раздела»;
        запись исхода не пишется на проходе без находок; номер требования
        берётся не из строки раздела.
        """
        old, new = self.two_values()
        n = self.rng.randrange(1, REQUIREMENTS + 1)
        base, head = self.value_change(old, new, old, new)
        out = self.scenario(base, head,
                            [self.line("test_value", [(repr(old), repr(new))], n)])
        context = self.note(f"вывод:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "verifying", context)
        outcome = self.outcome()
        self.assertIn(self.full("test_value"), outcome, context)
        self.assertIn(EXPECTATION.format(n=n),
                      segment(outcome, self.full("test_value"), ()), context)

    def test_ac7_undeclared_literal_change_refuses_transition_and_escalates_merge(self):
        """Смена литерала в методе вне перечня отклоняет переход «смена вне раздела» и эскалирует мерж.

        Сценарий: раздела нет либо он называет другой метод (от зерна).
        `advance` оставляет задачу в `in_dev`, запись «переход отклонён:
        гейт неослабления тестов» называет файл, `Класс::метод` и причину
        «смена вне раздела «Меняемое поведение»». Гейт мержа на том же
        диффе возвращает `True`, задача в `escalated`.

        Ловит мутацию: изменённые утверждения по-прежнему только
        наблюдаются — переход проходит, мерж не эскалирует; находка
        подключена к переходу, но не к гейту мержа.
        """
        base, head, section = self.undeclared_scenario()
        out = self.scenario(base, head, section)
        detail = self.refusal()
        context = self.note(f"отказ: {detail}\nвывод:\n{out}")
        self.assertEqual(self.state(), "in_dev", context)
        self.assertIn(self.path, detail, context)
        self.assertIn(self.name("test_value"), detail, context)
        self.assertIn(OUTSIDE, detail, context)
        self.assertTrue(self.merge_gate(), context)
        self.assertEqual(self.state(), "escalated", context)

    def weakening_files(self) -> tuple:
        v = self.rng.randrange(10, 99)
        base = {"app.py": f"VALUE = {v}\n", self.path: fixture_source(self.cls, {
            "test_in": [f"self.assertEqual(app.VALUE, {v})"],
            "test_true": [f"self.assertEqual(app.VALUE, {v})"],
            "test_dropped": [f"self.assertEqual(app.VALUE, {v})",
                             "self.assertTrue(app.VALUE)"],
            "test_spare": ["self.assertTrue(app.VALUE)"]})}
        head = {"app.py": f"VALUE = {v}\n", self.path: fixture_source(self.cls, {
            "test_in": [f"self.assertIn(app.VALUE, [{v}])"],
            "test_true": ["self.assertTrue(app.VALUE)"],
            "test_dropped": ["self.assertTrue(app.VALUE)"],
            "test_spare": ["self.assertTrue(app.VALUE)"]})}
        section = [self.line(m, [(str(v), str(v + 1))], 2)
                   for m in ("test_in", "test_true", "test_dropped")]
        return base, head, section

    def test_ac8_weakening_in_declared_methods_refuses_and_escalates_merge(self):
        """`assertEqual` -> `assertIn`/`assertTrue` и удаление утверждения отказывают даже в объявленных методах.

        Сценарий: три метода объявлены в разделе, в каждом — ослабление.
        Отказ перехода называет каждый из трёх; гейт мержа на том же
        диффе эскалирует.

        Ловит мутацию: метод из перечня пропускается без различения
        смены ожидания и ослабления — отказа нет; находки ослабления
        не доходят до гейта мержа.
        """
        base, head, section = self.weakening_files()
        out = self.scenario(base, head, section)
        detail = self.refusal()
        context = self.note(f"отказ: {detail}\nвывод:\n{out}")
        self.assertEqual(self.state(), "in_dev", context)
        for method in ("test_in", "test_true", "test_dropped"):
            self.assertIn(self.name(method), detail, context)
        self.assertTrue(self.merge_gate(), context)
        self.assertEqual(self.state(), "escalated", context)

    def mandate_files(self) -> tuple:
        """Дифф AC-7 и AC-8 вместе: смена вне перечня и три ослабления."""
        base, head, section = self.weakening_files()
        old, new = self.two_values()
        for files, value in ((base, old), (head, new)):
            files[self.path] += method_text(
                "test_outside", [f"self.assertEqual(abs({value}), {value})"])
        return base, head, section

    def assert_mandate_passes(self, elements: str) -> None:
        base, head, section = self.mandate_files()
        out = self.scenario(base, head, section, elements=elements)
        context = self.note(f"мандат: {elements}\nвывод:\n{out}\n"
                            f"журнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "verifying", context)
        allowed = "\n".join(self.details(ALLOWED_ACTION))
        for method in ("test_in", "test_true", "test_dropped", "test_outside"):
            self.assertIn(self.name(method), allowed, context)

    def test_ac9_path_mandate_covers_findings(self):
        """Мандат на путь файла снимает находки AC-7 и AC-8: переход проходит, журнал разрешения называет их.

        Ловит мутацию: новые находки об утверждениях заводятся без пути
        файла среди элементов мандата — мандат их не снимает, переход
        отклонён; покрытая находка не уходит в запись «ослабление тестов
        разрешено мандатом Оператора».
        """
        self.assert_mandate_passes(self.path)

    def test_ac9_class_mandate_covers_findings(self):
        """Мандат `путь::Класс` снимает находки AC-7 и AC-8 его методов.

        Ловит мутацию: у новых находок пустое квалифицированное имя (или
        только имя метода) — элемент-класс их не покрывает, переход
        отклонён.
        """
        self.assert_mandate_passes(f"{self.path}::{self.cls}")

    def test_ac9_method_mandate_covers_findings(self):
        """Мандат `путь::Класс::метод` на каждый изменённый метод снимает его находку.

        Ловит мутацию: находка заводится под именем файла или класса —
        элементы-методы её не покрывают, переход отклонён.
        """
        self.assert_mandate_passes(", ".join(
            self.full(m) for m in ("test_in", "test_true", "test_dropped",
                                   "test_outside")))

    def test_ac9_other_method_mandate_does_not_cover(self):
        """Мандат на другой метод того же файла находку смены вне перечня не снимает.

        Сценарий: дифф AC-7, мандат назван на неизменённый `test_kept`.
        Переход отклонён, отказ называет `test_value`.

        Ловит мутацию: мандат сверяется по префиксу пути или находка
        заводится под именем файла — мандат на соседний метод её снимает.
        """
        base, head, _section = self.undeclared_scenario()
        out = self.scenario(base, head, None, elements=self.full("test_kept"))
        detail = self.refusal()
        context = self.note(f"отказ: {detail}\nвывод:\n{out}")
        self.assertEqual(self.state(), "in_dev", context)
        self.assertIn(self.name("test_value"), detail, context)

    def test_ac10_pair_mismatch_refuses_naming_actual_pair(self):
        """Смена литерала в объявленном методе с другой фактической парой отклоняет переход, отказ называет фактическую пару.

        Ловит мутацию: сверка с объявленным сравнивает только факт
        смены, не значения — переход проходит; пары сравниваются строкой
        исходника, а не `literal_eval` по типу и значению, и при этом в
        отказ не попадают фактические значения.
        """
        old, new = self.two_values()
        declared = new + self.rng.randrange(1, 50)
        base, head = self.value_change(old, new, old, new)
        out = self.scenario(base, head, [
            self.line("test_value", [(repr(old), repr(declared))], 3)])
        detail = self.refusal()
        context = self.note(f"отказ: {detail}\nвывод:\n{out}")
        self.assertEqual(self.state(), "in_dev", context)
        self.assertIn(self.name("test_value"), detail, context)
        self.assertIn(MISMATCH, detail, context)
        part = segment(detail, self.name("test_value"), ())
        self.assertIn(str(old), part, context)
        self.assertIn(str(new), part, context)

    def test_ac11_spec_edit_after_approve_does_not_change_outcome(self):
        """Правка раздела после approve на исход рубежа не влияет — действует перечень записи approve.

        Сценарий: на approve объявлен `test_value` (его пара совпадает с
        фактической), `test_late` не объявлен. После approve раздел
        переписан: `test_late` объявлен с совпадающей парой, `test_value` —
        с несовпадающей. Отказ перехода называет `test_late` с причиной
        «смена вне раздела», а `test_value` в отказе не назван.

        Ловит мутацию: узел читает объявленное из текущего текста SPEC —
        отказ называет `test_value` «не совпала», а `test_late` проходит.
        """
        old, new = self.two_values()
        late_old, late_new = self.two_words()
        base = {"app.py": f"VALUE = {old}\nWORD = {late_old!r}\n",
                self.path: fixture_source(self.cls, {
                    "test_value": [f"self.assertEqual(app.VALUE, {old})"],
                    "test_late": [f"self.assertEqual(app.WORD, {late_old!r})"]})}
        head = {"app.py": f"VALUE = {new}\nWORD = {late_new!r}\n",
                self.path: fixture_source(self.cls, {
                    "test_value": [f"self.assertEqual(app.VALUE, {new})"],
                    "test_late": [f"self.assertEqual(app.WORD, {late_new!r})"]})}
        out = self.start(base, [self.line("test_value", [(repr(old), repr(new))], 4)])
        self.assertEqual(self.state(), "tests_writing",
                         self.note(f"предпосылка: approve не прошёл:\n{out}"))
        self.edit_spec([
            self.line("test_value", [(repr(old), repr(new + 1))], 4),
            self.line("test_late", [(repr(late_old), repr(late_new))], 5)])
        self.to_in_dev()
        self.head(head)
        out = self.advance()
        detail = self.refusal()
        names = (self.name("test_value"), self.name("test_late"))
        context = self.note(f"отказ: {detail}\nвывод:\n{out}")
        self.assertEqual(self.state(), "in_dev", context)
        self.assertIn(OUTSIDE, segment(detail, names[1], names), context)
        self.assertNotIn(names[0], detail, context)


# ---------------------------------------------------------------------------
# AC-12: канареечная задача и внешний target.

class OutOfScopeTest(DeclaredChangeSandbox):

    def assert_untouched(self, out: str) -> None:
        context = self.note(f"вывод:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.refusal(), "", context)
        self.assertEqual(self.details(OUTCOME_ACTION), [], context)
        self.assertEqual(self.details(TWO_SIDED_ACTION), [], context)
        self.assertEqual(self.state(), "verifying", context)

    def test_ac12_canary_task_passes_without_new_records(self):
        """Канареечная задача на диффе AC-7 проходит переход без записей исхода и двустороннего прогона.

        Ловит мутацию: условие «канарейка — гейт не проверяется» снято при
        переносе находок в узел отказа — переход отклонён «смена вне
        раздела».
        """
        base, head, section = self.undeclared_scenario()
        self.start(base, section)
        self.to_in_dev()
        store.update_task(store.db(), self.task_id, is_canary=1)
        self.head(head)
        self.assert_untouched(self.advance())

    def test_ac12_external_target_task_passes_without_new_records(self):
        """Задача внешнего target на диффе AC-7 проходит переход без записей исхода и двустороннего прогона.

        Сценарий: обработчик `fsm_advance.in_dev` получает строку задачи с
        target, отличным от `config.DEFAULT_TARGET` (остальные рубежи
        читают тот же клон, что у задачи артели).

        Ловит мутацию: условие «внешний target — гейт не проверяется» снято
        — переход отклонён «смена вне раздела».
        """
        base, head, section = self.undeclared_scenario()
        self.start(base, section)
        self.to_in_dev()
        self.head(head)
        conn = store.db()
        row = dict(store.get_task(conn, self.task_id))
        row["target"] = f"{config.DEFAULT_TARGET}-{word(self.rng)}"
        # Внешний проект объявлен в targets.yaml без профиля тестов: проект
        # с неразрешённым контекстом гейт отклоняет (SPEC
        # 01M45FJVGQT1K0P8HDEXZX6HS7, требования 3, 5).
        declare_target(row["target"])
        out =self.run_cmd(fsm_advance.in_dev, conn, self.task_id, row,
                           config.TASKS / self.task_id, config.DEFAULT_TARGET,
                           "in_dev")
        self.assert_untouched(out)


# ---------------------------------------------------------------------------
# AC-13, AC-14: журнал рубежей и ревью-пакет.

class JournalAndReviewTest(DeclaredChangeSandbox):

    def mixed(self) -> tuple:
        """`test_out` — смена вне перечня, `test_decl` — объявленная смена
        с совпавшей парой (требование N)."""
        old, new = self.two_values()
        w_old, w_new = self.two_words()
        n = self.rng.randrange(1, REQUIREMENTS + 1)
        base = {"app.py": f"VALUE = {old}\nWORD = {w_old!r}\n",
                self.path: fixture_source(self.cls, {
                    "test_out": [f"self.assertEqual(app.VALUE, {old})"],
                    "test_decl": [f"self.assertEqual(app.WORD, {w_old!r})"]})}
        head = {"app.py": f"VALUE = {new}\nWORD = {w_new!r}\n",
                self.path: fixture_source(self.cls, {
                    "test_out": [f"self.assertEqual(app.VALUE, {new})"],
                    "test_decl": [f"self.assertEqual(app.WORD, {w_new!r})"]})}
        section = [self.line("test_decl", [(repr(w_old), repr(w_new))], n)]
        texts = {"test_out": f"self.assertEqual(app.VALUE, {old})",
                 "test_decl": f"self.assertEqual(app.WORD, {w_old!r})"}
        return base, head, section, n, texts, (w_old, w_new)

    def test_ac13_both_rubezhs_keep_observation_and_journal_outcome(self):
        """Оба рубежа пишут прежнюю запись наблюдения и запись исхода с каждым изменённым методом.

        Сценарий: смена вне перечня и объявленная смена в одном файле.
        После перехода и после гейта мержа: запись «изменены утверждения
        тестов (наблюдение)» в прежней форме «<путь>: утверждения изменены
        в <Класс>::<метод>: <текст base>» по обоим методам (по одной на
        рубеж); запись «утверждения тестов: исход рубежа» называет оба
        метода как `путь::Класс::метод`, у смены вне перечня — причину
        «смена вне раздела», у объявленной на переходе — «смена ожидания
        по SPEC (требование N)».

        Ловит мутацию: запись наблюдения заменена записью исхода — прежней
        записи нет; запись исхода пишется только при отказе или только на
        одном рубеже — на гейте мержа её нет; метод с исходом «смена
        ожидания» из записи исхода выпадает.
        """
        base, head, section, n, texts, _pair = self.mixed()
        self.scenario(base, head, section)
        names = [self.full(m) for m in texts]
        transition_outcome = self.outcome()
        self.merge_gate()
        observations = self.details(OBSERVATION_ACTION)
        outcomes = self.details(OUTCOME_ACTION)
        context = self.note(f"журнал:\n{self.journal_text()}")
        self.assertEqual(len(observations), 2, context)
        for observation in observations:
            for method, text in texts.items():
                self.assertIn(f"{self.path}: {CHANGED} {self.name(method)}: "
                              f"{text}", observation, context)
        self.assertEqual(len(outcomes), 2, context)
        for outcome in outcomes:
            for name in names:
                self.assertIn(name, outcome, context)
        self.assertIn(OUTSIDE, segment(transition_outcome, names[0], names), context)
        self.assertIn(EXPECTATION.format(n=n),
                      segment(transition_outcome, names[1], names), context)

    def test_ac14_review_package_section_carries_observation_outcome_and_pair(self):
        """Раздел ревью-пакета несёт прежнюю строку наблюдения, исход рубежа и строку «было → стало (требование N)».

        Ловит мутацию: в раздел ревью-пакета не добавлен исход рубежа или
        строка объявленной пары из записи approve; прежний текст
        «переход и мерж от них не зависят» не заменён.
        """
        base, head, section, n, texts, (w_old, w_new) = self.mixed()
        self.scenario(base, head, section)
        text = self.review_text()
        context = self.note(f"пакет:\n{text}")
        self.assertIn(REVIEW_SECTION, text, context)
        part = text[text.index(REVIEW_SECTION):]
        names = [self.name(m) for m in texts]
        out_part = segment(part, names[0], names)
        decl_part = segment(part, names[1], names)
        for method, piece in (("test_out", out_part), ("test_decl", decl_part)):
            self.assertIn(f"{self.path}: {CHANGED} {self.name(method)}: "
                          f"{texts[method]}", part, context)
            self.assertTrue(piece, context)
        self.assertIn(OUTSIDE, out_part, context)
        self.assertIn(EXPECTATION.format(n=n), decl_part, context)
        self.assertIn("→", decl_part, context)
        self.assertIn(w_old, decl_part, context)
        self.assertIn(w_new, decl_part, context)
        self.assertIn(f"(требование {n})", decl_part, context)
        self.assertNotIn(OLD_REVIEW_TEXT, text, context)
        self.assertIn(NEW_REVIEW_TEXT, text.replace("`", ""), context)


# ---------------------------------------------------------------------------
# AC-15..AC-18: строгость нового ожидания.

class StrictnessTest(DeclaredChangeSandbox):

    def strictness_scenario(self, weak: dict, tight: dict,
                            header: str = "") -> tuple:
        """`weak`/`tight`: {метод: (строка base, строка head, пара)} — пары
        объявлены как есть; (текст отказа, вывод)."""
        methods = {**weak, **tight}
        base = {"app.py": "VALUE = 1\nRATIO = 0.5\nTEXT = 'abcdef'\nCOUNT = 30\n"
                          "\n\ndef check(value):\n    return value > 0\n",
                self.path: fixture_source(self.cls, {m: [b] for m, (b, _h, _p)
                                                  in methods.items()}, header)}
        head = {"app.py": base["app.py"],
                self.path: fixture_source(self.cls, {m: [h] for m, (_b, h, _p)
                                                  in methods.items()}, header)}
        section = [self.line(m, [p], 1 + i % REQUIREMENTS)
                   for i, (m, (_b, _h, p)) in enumerate(methods.items())]
        out = self.scenario(base, head, section)
        return self.refusal(), out

    def assert_weak_and_tight(self, detail: str, out: str, weak, tight,
                              others=()) -> None:
        """Каждый метод `weak` назван в отказе с «ослабление: <признак>»,
        ни один метод `tight` в отказе не назван; `others` — прочие методы
        сценария (границы кусков отказа)."""
        names = [self.name(m) for m in list(weak) + list(tight) + list(others)]
        for method in weak:
            part = segment(detail, self.name(method), names)
            context = self.note(f"{method}: {part!r}\nотказ: {detail}\nвывод:\n{out}")
            self.assertTrue(part, context)
            self.assertRegex(part, WEAKENING, context)
        for method in tight:
            self.assertNotIn(self.name(method), detail, self.note(
                f"ужесточение {method} стало находкой: {detail}"))
        self.assertEqual(self.state(), "in_dev", self.note(f"вывод:\n{out}"))

    def test_ac15_widened_tolerance_refuses_with_sign(self):
        """`delta` больше, `places` меньше у `assertAlmostEqual`, `rel`/`abs` больше у `pytest.approx` — отказ с признаком.

        Рядом ужесточения той же формы (`delta` меньше, `places` больше)
        находкой не становятся.

        Ловит мутацию: строгость допуска не оценивается и смена его
        значения проходит как равенство — ослабленные методы не в отказе;
        направление сравнения перепутано (`places` больше считается
        ослаблением) — ужесточение в отказе.
        """
        d = self.rng.choice((0.01, 0.02, 0.05))
        p = self.rng.randrange(3, 7)
        weak = {
            "test_delta_wide": (f"self.assertAlmostEqual(app.RATIO, 0.5, delta={d})",
                                f"self.assertAlmostEqual(app.RATIO, 0.5, delta={d * 10})",
                                (repr(d), repr(d * 10))),
            "test_places_less": (f"self.assertAlmostEqual(app.RATIO, 0.5, places={p})",
                                 f"self.assertAlmostEqual(app.RATIO, 0.5, places={p - 2})",
                                 (repr(p), repr(p - 2))),
            "test_rel_wide": (f"assert app.RATIO == pytest.approx(0.5, rel={d})",
                              f"assert app.RATIO == pytest.approx(0.5, rel={d * 10})",
                              (repr(d), repr(d * 10))),
            "test_abs_wide": (f"assert app.RATIO == pytest.approx(0.5, abs={d})",
                              f"assert app.RATIO == pytest.approx(0.5, abs={d * 10})",
                              (repr(d), repr(d * 10))),
        }
        tight = {
            "test_delta_narrow": (f"self.assertAlmostEqual(app.RATIO, 0.5, delta={d * 10})",
                                  f"self.assertAlmostEqual(app.RATIO, 0.5, delta={d})",
                                  (repr(d * 10), repr(d))),
            "test_places_more": (f"self.assertAlmostEqual(app.RATIO, 0.5, places={p})",
                                 f"self.assertAlmostEqual(app.RATIO, 0.5, places={p + 2})",
                                 (repr(p), repr(p + 2))),
        }
        detail, out = self.strictness_scenario(weak, tight, "\nimport pytest\n")
        self.assert_weak_and_tight(detail, out, weak, tight)

    def test_ac16_regex_lost_anchor_or_added_wildcard_refuses_with_sign(self):
        """Регулярное выражение `assertRegex`/`assertRaisesRegex` потеряло якорь или получило `.*`/`.+` — отказ с признаком.

        Рядом добавленный якорь (ужесточение) находкой не становится.

        Ловит мутацию: строгость регулярного выражения не оценивается —
        ослабленные методы не в отказе; подсчёт якорей перепутан с
        подсчётом `.*` — добавленный якорь в отказе.
        """
        core = word(self.rng, 5)
        weak = {
            "test_lost_dollar": (f"self.assertRegex(app.TEXT, {('^' + core + '$')!r})",
                                 f"self.assertRegex(app.TEXT, {('^' + core)!r})",
                                 (repr("^" + core + "$"), repr("^" + core))),
            "test_lost_caret": (f"self.assertRegex(app.TEXT, {('^' + core)!r})",
                                f"self.assertRegex(app.TEXT, {core!r})",
                                (repr("^" + core), repr(core))),
            "test_lost_a": (f"self.assertRaisesRegex(ValueError, {(chr(92) + 'A' + core)!r}, int, 'x')",
                            f"self.assertRaisesRegex(ValueError, {core!r}, int, 'x')",
                            (repr(chr(92) + "A" + core), repr(core))),
            "test_lost_z": (f"self.assertRegex(app.TEXT, {(core + chr(92) + 'Z')!r})",
                            f"self.assertRegex(app.TEXT, {core!r})",
                            (repr(core + chr(92) + "Z"), repr(core))),
            "test_star": (f"self.assertRegex(app.TEXT, {('^' + core + '$')!r})",
                          f"self.assertRegex(app.TEXT, {('^' + core[:2] + '.*' + core[2:] + '$')!r})",
                          (repr("^" + core + "$"),
                           repr("^" + core[:2] + ".*" + core[2:] + "$"))),
            "test_plus": (f"self.assertRegex(app.TEXT, {('^' + core + '$')!r})",
                          f"self.assertRegex(app.TEXT, {('^' + core[:2] + '.+' + core[2:] + '$')!r})",
                          (repr("^" + core + "$"),
                           repr("^" + core[:2] + ".+" + core[2:] + "$"))),
        }
        tight = {
            "test_anchor_added": (f"self.assertRegex(app.TEXT, {core!r})",
                                  f"self.assertRegex(app.TEXT, {('^' + core)!r})",
                                  (repr(core), repr("^" + core))),
        }
        detail, out = self.strictness_scenario(weak, tight)
        self.assert_weak_and_tight(detail, out, weak, tight)

    def test_ac17_literal_replaced_by_call_or_module_attribute_refuses(self):
        """Ожидаемый литерал заменён вызовом либо атрибутом импортированного модуля — отказ «литерал заменён вычисленным значением».

        Ловит мутацию: вычисленное значение на месте литерала
        маскируется как литерал (или как «иная смена» без признака) —
        отказ не называет признак «литерал заменён вычисленным значением».
        """
        v = self.rng.randrange(10, 99)
        weak = {
            "test_by_call": (f"self.assertEqual(app.VALUE, {v})",
                             "self.assertEqual(app.VALUE, expected())",
                             (repr(v), repr(v + 1))),
            "test_by_attr": (f"self.assertEqual(app.VALUE, {v})",
                             "self.assertEqual(app.VALUE, app.COUNT)",
                             (repr(v), repr(v + 1))),
        }
        detail, out = self.strictness_scenario(
            weak, {}, f"\n\ndef expected():\n    return {v}\n")
        for method in weak:
            part = segment(detail, self.name(method), [self.name(m) for m in weak])
            self.assertIn(COMPUTED, part, self.note(
                f"{method}: {part!r}\nотказ: {detail}\nвывод:\n{out}"))
        self.assertEqual(self.state(), "in_dev", self.note(f"вывод:\n{out}"))

    def test_ac18_substring_lower_bound_and_unrated_position_refuse(self):
        """Строка `assertIn` -> собственная подстрока и граница `assertGreater` вниз — отказ; константа внутри вызова в `assertTrue` — «правило не умеет оценить строгость».

        Рядом надстрока в `assertIn` и граница `assertGreater` вверх
        находкой не становятся.

        Ловит мутацию: «вхождение» и «порядок» не оцениваются и проходят
        как равенство — ослабленные методы не в отказе; константа на
        неоцениваемой позиции пропускается как равенство — метода
        `test_unrated` в отказе нет; направление границы перепутано —
        граница вверх в отказе.
        """
        text = word(self.rng, 6)
        low = self.rng.randrange(10, 20)
        weak = {
            "test_substring": (f"self.assertIn({text!r}, app.TEXT)",
                               f"self.assertIn({text[:3]!r}, app.TEXT)",
                               (repr(text), repr(text[:3]))),
            "test_bound_down": (f"self.assertGreater(app.COUNT, {low})",
                                f"self.assertGreater(app.COUNT, {low - 5})",
                                (repr(low), repr(low - 5))),
        }
        unrated = {
            "test_unrated": (f"self.assertTrue(app.check({low}))",
                             f"self.assertTrue(app.check({low + 1}))",
                             (repr(low), repr(low + 1))),
        }
        tight = {
            "test_superstring": (f"self.assertIn({text[:3]!r}, app.TEXT)",
                                 f"self.assertIn({text!r}, app.TEXT)",
                                 (repr(text[:3]), repr(text))),
            "test_bound_up": (f"self.assertGreater(app.COUNT, {low})",
                              f"self.assertGreater(app.COUNT, {low + 5})",
                              (repr(low), repr(low + 5))),
        }
        detail, out = self.strictness_scenario({**weak, **unrated}, tight)
        self.assert_weak_and_tight(detail, out, weak, tight, unrated)
        names = [self.name(m) for m in list(weak) + list(unrated) + list(tight)]
        part = segment(detail, self.name("test_unrated"), names)
        self.assertIn(UNRATED, part, self.note(f"отказ: {detail}"))


# ---------------------------------------------------------------------------
# AC-19..AC-24, AC-27: двусторонний прогон на переходе.

def timeout_rule(argv: list):
    """Подмена запуска pytest по узлу процессом с истекающим ожиданием."""
    return (lambda args, *a, **k: TimeoutProc(args)) if is_pytest_node(argv) \
        else None


class TwoSidedTest(DeclaredChangeSandbox):

    def assert_refused(self, out: str, *needles) -> str:
        """Переход отклонён гейтом неослабления, отказ называет
        `test_value` и каждую из `needles` (строка или шаблон), записи
        «двусторонний прогон пройден» нет."""
        detail = self.refusal()
        context = self.note(f"отказ: {detail}\nвывод:\n{out}\nжурнал:\n"
                            f"{self.journal_text()}")
        self.assertEqual(self.state(), "in_dev", context)
        self.assertIn(self.name("test_value"), detail, context)
        for needle in needles:
            if isinstance(needle, re.Pattern):
                self.assertRegex(detail, needle, context)
            else:
                self.assertIn(needle, detail, context)
        self.assertEqual(self.details(TWO_SIDED_ACTION), [], context)
        return detail

    def start_declared(self, base: dict, head: dict, old, new) -> None:
        out = self.start(base, [self.line("test_value", [(repr(old), repr(new))], 2)])
        self.assertEqual(self.state(), "tests_writing",
                         self.note(f"предпосылка: approve не прошёл:\n{out}"))
        self.to_in_dev()
        self.head(head)

    def test_ac19_new_version_green_on_base_refuses(self):
        """Новая версия метода зелёная на дереве базы — отказ с именем метода и стороной «новая версия на базе».

        Сценарий: `app.VALUE` уже на базе равно новому ожиданию; литерал
        метода сменён и объявлен.

        Ловит мутацию: прогон новой версии на базе не делается или его
        зелёный исход не проверяется — переход проходит.
        """
        self.declared_value(base_value=lambda old, new: new)
        self.assert_refused(self.advance(), NEW_ON_BASE)

    def test_ac20_old_version_green_on_branch_refuses(self):
        """Старая версия метода зелёная на дереве головы ветки — отказ с именем метода и стороной «старая версия на ветке».

        Сценарий: литерал метода сменён и объявлен, а `app.VALUE` на ветке
        не менялся — поведение не сменилось.

        Ловит мутацию: прогон старой версии на ветке не делается или его
        зелёный исход не проверяется — переход проходит.
        """
        self.declared_value(head_value=lambda old, new: old)
        self.assert_refused(self.advance(), OLD_ON_BRANCH)

    def test_ac21_import_error_is_not_proof(self):
        """Новая версия на базе падает ошибкой импорта — отказ «не доказательство» с видом ошибки.

        Сценарий: новая версия файла тестов импортирует имя, которое
        `app.py` заводит только на ветке.

        Ловит мутацию: падение засчитывается по коду возврата pytest, а
        не по классу исключения и фазе узла — ошибка сборки принята за
        доказательство, переход проходит.
        """
        token = f"ONLY_{word(self.rng).upper()}"
        old, new = self.two_values()
        base, head = self.value_change(old, new, old, new)
        head["app.py"] += f"{token} = 1\n"
        head[self.path] = head[self.path].replace(
            "import app\n", f"import app\nfrom app import {token}\n", 1)
        self.start_declared(base, head, old, new)
        self.assert_refused(self.advance(), NOT_PROOF, re.compile(
            r"ImportError|ModuleNotFoundError|импорт|сбор|collect", re.I))

    def test_ac21_setup_error_is_not_proof(self):
        """Новая версия на базе падает в `setUp` — отказ «не доказательство» с видом ошибки.

        Сценарий: новая версия класса заводит `setUp`, который зовёт
        функцию `app`, существующую только на ветке.

        Ловит мутацию: фаза узла не различается — провал `setUp` с
        исключением принят за провал утверждения, переход проходит.
        """
        helper = f"make_{word(self.rng)}"
        old, new = self.two_values()
        base, head = self.value_change(old, new, old, new)
        head["app.py"] += f"\n\ndef {helper}():\n    return 1\n"
        head[self.path] = head[self.path].replace(
            "(unittest.TestCase):\n",
            f"(unittest.TestCase):\n\n    def setUp(self):\n"
            f"        self.helper = app.{helper}()\n", 1)
        self.start_declared(base, head, old, new)
        self.assert_refused(self.advance(), NOT_PROOF, re.compile(
            r"setUp|setup|подготов|фикстур", re.I))

    def test_ac21_other_exception_in_call_is_not_proof(self):
        """Новая версия на базе падает в фазе call исключением не `AssertionError` — отказ «не доказательство» с видом ошибки.

        Сценарий: на базе `app.value()` делит на ноль, на ветке
        возвращает новое значение; метод сверяет `app.value()`.

        Ловит мутацию: любое проваленное в фазе call засчитывается
        доказательством без проверки класса исключения — переход
        проходит.
        """
        old, new = self.two_values()
        base = {"app.py": "def value():\n    return 1 / 0\n",
                self.path: fixture_source(self.cls, {
                    "test_value": [f"self.assertEqual(app.value(), {old})"]})}
        head = {"app.py": f"def value():\n    return {new}\n",
                self.path: fixture_source(self.cls, {
                    "test_value": [f"self.assertEqual(app.value(), {new})"]})}
        self.start_declared(base, head, old, new)
        self.assert_refused(self.advance(), NOT_PROOF, re.compile(
            r"ZeroDivisionError|call", re.I))

    def test_ac22_pytest_timeout_refuses(self):
        """Таймаут прогона pytest по узлу отклоняет переход с причиной «таймаут».

        Подменён только запуск pytest по узлу `…py::…`: любое ожидание
        с таймаутом у него истекает.

        Ловит мутацию: таймаут прогона трактуется как пропуск стороны
        (fail-open) — переход проходит; исключение таймаута не
        перехватывается и роняет `advance`.
        """
        self.declared_value()
        with self.spawn_spy(timeout_rule) as spy:
            out = self.advance()
        self.assertTrue(spy.pytest_nodes(), self.note(
            f"pytest по узлу не запускался:\n{out}"))
        self.assert_refused(out, "таймаут")

    def test_ac22_git_failure_on_worktree_add_refuses(self):
        """Сбой `git worktree add` при заведении временного дерева отклоняет переход и называет причину.

        Подменён только запуск `git … worktree add`: вместо него — процесс
        с ненулевым кодом и случайной меткой в stderr.

        Ловит мутацию: сбой заведения дерева трактуется как «сравнивать
        нечем — пропустить» — переход проходит.
        """
        token = f"отказ-дерева-{word(self.rng)}"
        self.declared_value()
        failing = [sys.executable, "-c",
                   f"import sys; sys.stderr.write({token!r}); sys.exit(128)"]
        real = subprocess.Popen
        rule = (lambda argv: (lambda args, *a, **k: real(failing, *a, **k))
                if is_worktree_add(argv) else None)
        with self.spawn_spy(rule) as spy:
            out = self.advance()
        self.assertTrue(spy.worktree_adds(), self.note(
            f"git worktree add не вызывался:\n{out}"))
        detail = self.assert_refused(out)
        self.assertRegex(detail, re.compile(f"{re.escape(token)}|git|дерев", re.I),
                         self.note(f"причина не названа: {detail}"))

    def assert_trees_removed(self, spy: SpawnSpy, before: set, out: str) -> None:
        context = self.note(f"вывод:\n{out}\nзапуски:\n{spy.calls}")
        self.assertTrue(spy.worktree_adds(), context)
        self.assertEqual(self.worktree_paths(), before, context)
        made = [worktree_add_path(argv) for argv in spy.worktree_adds()]
        made += [cwd for _argv, cwd in spy.pytest_nodes()]
        leftovers = [p for p in made
                     if p and p not in (str(self.root), str(self.wt))
                     and Path(p).exists()]
        self.assertEqual(leftovers, [], context)

    def test_ac23_trees_removed_after_refusal_timeout_pass_and_exception(self):
        """Временные деревья убраны при каждом исходе: отказ, таймаут, пройден, исключение.

        Сценарий: четыре прогона рубежа в одной задаче — на ветке, где
        старая версия зелёная (отказ); с подменой запуска pytest по узлу
        на таймаут; на годной ветке (пройден); с подменой запуска pytest
        по узлу на исключение. После каждого `git worktree list` клона
        совпадает с перечнем до рубежа, а каталоги деревьев и рабочие
        каталоги прогонов pytest не существуют.

        Ловит мутацию: уборка стоит только на пути успеха (не в
        `finally`) — после отказа, таймаута или исключения дерево остаётся
        в `git worktree list` и на диске.
        """
        _old, new = self.declared_value(head_value=lambda old, new: old)
        before = self.worktree_paths()

        def boom(args, *a, **k):
            raise RuntimeError(f"сбой-запуска-{self.seed}")

        def run(label: str, rule) -> None:
            store.update_task(store.db(), self.task_id, state="in_dev")
            with self.spawn_spy(rule) as spy:
                try:
                    out = self.advance()
                except Exception as exc:  # noqa: BLE001 — предмет: уборка при любом исходе
                    out = repr(exc)
            self.assert_trees_removed(spy, before, f"[{label}] {out}")

        run("отказ", None)
        run("таймаут", timeout_rule)
        (self.wt / "app.py").write_text(f"VALUE = {new}\n", encoding="utf-8")
        self.head({}, "голова с новым значением")
        run("пройден", None)
        self.assertEqual(self.state(), "verifying", self.note(self.journal_text()))
        run("исключение", lambda argv: boom if is_pytest_node(argv) else None)

    def test_ac24_both_sides_fail_on_assertion_passes_and_records(self):
        """Обе стороны падают на утверждении — переход проходит, запись «двусторонний прогон пройден» несёт sha головы и метод.

        Ловит мутацию: запись не пишется или пишется без sha головы —
        гейт мержа не сможет сверить голову; прогон объявленного метода
        не запускается вовсе — pytest по узлу не вызывался.
        """
        self.declared_value()
        sha = self.head_sha()
        with self.spawn_spy() as spy:
            out = self.advance()
        context = self.note(f"вывод:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertEqual(self.state(), "verifying", context)
        self.assertGreaterEqual(len(spy.pytest_nodes()), 2, context)
        records = self.details(TWO_SIDED_ACTION)
        self.assertEqual(len(records), 1, context)
        self.assertIn(sha[:7], records[0], context)
        self.assertIn(self.name("test_value"), records[0], context)

    def assert_no_run(self, spy: SpawnSpy, out: str) -> None:
        context = self.note(f"вывод:\n{out}\nзапуски:\n{spy.calls}")
        self.assertEqual(spy.pytest_nodes(), [], context)
        self.assertEqual(spy.worktree_adds(), [], context)
        self.assertEqual(self.details(TWO_SIDED_ACTION), [], context)

    def test_ac24_no_declaration_runs_nothing(self):
        """У задачи нет записи объявления — ни git-деревьев, ни pytest по узлу, ни записи прогона.

        Сценарий: SPEC без раздела, в голове добавлено утверждение и
        сменён `app.py`; переход проходит.

        Ловит мутацию: двусторонний прогон запускается на любом
        изменённом файле тестов без проверки записи объявления — в
        запусках появляются `git worktree add` и pytest по узлу.
        """
        v = self.rng.randrange(10, 99)
        base = {"app.py": f"VALUE = {v}\n", self.path: fixture_source(self.cls, {
            "test_value": [f"self.assertEqual(app.VALUE, {v})"]})}
        head = {"app.py": f"VALUE = {v}\nEXTRA = 1\n",
                self.path: fixture_source(self.cls, {
                    "test_value": [f"self.assertEqual(app.VALUE, {v})",
                                   "self.assertEqual(app.EXTRA, 1)"]})}
        out = self.start(base, None)
        self.assertEqual(self.state(), "tests_writing", self.note(out))
        self.to_in_dev()
        self.head(head)
        with self.spawn_spy() as spy:
            out = self.advance()
        self.assertEqual(self.state(), "verifying", self.note(out))
        self.assert_no_run(spy, out)

    def test_ac24_uncovered_finding_runs_nothing(self):
        """Сравнение дало непокрытую находку — двусторонний прогон не выполняется.

        Сценарий: объявленная смена `test_value` (исход 7а) рядом со
        сменой литерала в необъявленном `test_other`; переход отклонён.

        Ловит мутацию: прогон стоит до сравнения или не смотрит на
        непокрытые находки — в запусках появляются `git worktree add` и
        pytest по узлу.
        """
        old, new = self.two_values()
        base, head = self.value_change(old, new, old, new)
        base[self.path] += method_text("test_other", [f"self.assertEqual(abs({old}), {old})"])
        head[self.path] += method_text("test_other", [f"self.assertEqual(abs({new}), {new})"])
        self.start_declared(base, head, old, new)
        with self.spawn_spy() as spy:
            out = self.advance()
        self.assertEqual(self.state(), "in_dev", self.note(out))
        self.assertIn(self.name("test_other"), self.refusal(), self.note(out))
        self.assert_no_run(spy, out)

    def test_ac27_review_package_names_two_sided_result_for_current_head(self):
        """Раздел ревью-пакета для метода исхода 7а: «не записан» до прогона, «пройден» после, «не записан» после сдвига головы.

        Ловит мутацию: итог прогона в пакете не сверяется с текущей
        головой — после сдвига головы пакет всё ещё говорит «пройден»;
        итог не выводится вовсе.
        """
        self.declared_value()
        name = self.name("test_value")

        def piece() -> str:
            text = self.review_text()
            self.assertIn(REVIEW_SECTION, text, self.note(text))
            return segment(text[text.index(REVIEW_SECTION):], name, ())

        before = piece()
        self.assertIn("не записан", before, self.note(before))
        out = self.advance()
        self.assertEqual(self.state(), "verifying", self.note(out))
        after = piece()
        self.assertRegex(after, PASSED, self.note(after))
        self.assertNotIn("не записан", after, self.note(after))
        (self.wt / "app.py").write_text(
            (self.wt / "app.py").read_text(encoding="utf-8") + "# сдвиг\n",
            encoding="utf-8")
        self.head({}, "сдвиг головы")
        moved = piece()
        self.assertIn("не записан", moved, self.note(moved))


# ---------------------------------------------------------------------------
# AC-25: гейт мержа не повторяет прогон.

class MergeGateTwoSidedTest(DeclaredChangeSandbox):

    def test_ac25_merge_gate_runs_no_pytest_and_escalates_moved_head(self):
        """Гейт мержа не запускает pytest: при записи прогона для текущей головы проходит, после сдвига головы эскалирует с именем метода.

        Сценарий: объявленная смена прошла переход (запись «двусторонний
        прогон пройден» есть). Гейт мержа под обёрткой запусков: pytest не
        запускался, результат `False`. Затем в ветку добавлен коммит —
        гейт мержа возвращает `True`, задача в `escalated`, новые записи
        журнала называют метод.

        Ловит мутацию: гейт мержа повторяет двусторонний прогон — в
        запусках pytest; запись прогона сверяется не с текущей головой —
        сдвинутая голова проходит мерж.
        """
        self.declared_value()
        out = self.advance()
        self.assertEqual(self.state(), "verifying", self.note(out))
        with self.spawn_spy() as spy:
            escalated = self.merge_gate()
        context = self.note(f"журнал:\n{self.journal_text()}\nзапуски:\n{spy.calls}")
        self.assertEqual(spy.pytest_any(), [], context)
        self.assertFalse(escalated, context)
        self.assertEqual(self.state(), "verifying", context)
        last = self.steps()[-1][0]
        (self.wt / "app.py").write_text(
            (self.wt / "app.py").read_text(encoding="utf-8") + "# сдвиг\n",
            encoding="utf-8")
        self.head({}, "сдвиг головы")
        with self.spawn_spy() as spy:
            escalated = self.merge_gate()
        context = self.note(f"журнал:\n{self.journal_text()}\nзапуски:\n{spy.calls}")
        self.assertEqual(spy.pytest_any(), [], context)
        self.assertTrue(escalated, context)
        self.assertEqual(self.state(), "escalated", context)
        fresh = "\n".join(d for i, _a, d in self.steps() if i > last)
        self.assertIn(self.name("test_value"), fresh, context)


# ---------------------------------------------------------------------------
# AC-26: храповик (ANSWER-1: через рубеж — покрытая мандатом убыль в
# журнале разрешения; на уровне функции — находка без иных находок).

def fixture_counts(sources) -> tuple:
    """(методы, утверждения) по текстам файлов тестов; `None` — ноль."""
    methods = assertions = 0
    for source in sources:
        if source is None:
            continue
        methods += len(guard.qualified_test_methods(source))
        assertions += sum(len(found) for found in
                          (guard.test_assertions(source) or {}).values())
    return methods, assertions


def counts_pattern(before: int, after: int) -> str:
    return rf"(?<!\d){before}\s*→\s*{after}(?!\d)"


class RatchetGateTest(DeclaredChangeSandbox):

    def test_ac26_mandate_covered_decline_is_journaled_with_counts(self):
        """Убыль методов либо утверждений, покрытая мандатом на файл, уходит в журнал разрешения с числами «было → стало» и файлом; переход проходит.

        Сценарий: раздела нет. Файл тестов фикстуры в базе — несколько
        методов по нескольку утверждений; в голове (от зерна) исчез один
        метод либо из метода удалено утверждение. Мандат ANSWER-1 — путь
        файла. `advance` доводит задачу до `verifying`, запись «ослабление
        тестов разрешено мандатом Оператора» называет файл и числа «было →
        стало» методов и утверждений диффа `tests/` (по
        `guard.qualified_test_methods`/`guard.test_assertions`).

        Ловит мутацию: находка храповика не заводится, когда прочие
        находки прохода покрыты мандатом (условие «нет иных находок»
        проверяется до снятия покрытых) — в журнале разрешения нет чисел
        «было → стало»; покрытая убыль не уходит в журнал разрешения.
        """
        lines = ["self.assertEqual(app.VALUE, {v})", "self.assertTrue(app.VALUE)",
                 "self.assertGreater(app.VALUE, 0)", "self.assertIsNotNone(app.VALUE)"]
        v = self.rng.randrange(10, 99)
        base_methods = {
            f"test_{word(self.rng)}_{i}": [line.format(v=v) for line in
                                           self.rng.sample(lines, self.rng.randrange(2, 5))]
            for i in range(self.rng.randrange(3, 6))}
        head_methods = {name: list(body) for name, body in base_methods.items()}
        victim = self.rng.choice(sorted(head_methods))
        mode = self.rng.choice(("метод", "утверждение"))
        if mode == "метод":
            del head_methods[victim]
        else:
            head_methods[victim].pop(self.rng.randrange(len(head_methods[victim])))
        base_src = fixture_source(self.cls, base_methods)
        head_src = fixture_source(self.cls, head_methods)
        base = {"app.py": f"VALUE = {v}\n", self.path: base_src}
        head = {"app.py": f"VALUE = {v}\n", self.path: head_src}
        (bm, ba), (hm, ha) = fixture_counts([base_src]), fixture_counts([head_src])
        out = self.scenario(base, head, None, elements=self.path)
        allowed = "\n".join(self.details(ALLOWED_ACTION))
        context = self.note(f"убыль: {mode} {victim}; методы {bm} → {hm}, "
                            f"утверждения {ba} → {ha}\nразрешено: {allowed}\n"
                            f"вывод:\n{out}\nжурнал:\n{self.journal_text()}")
        self.assertTrue(hm < bm or ha < ba, context)
        self.assertEqual(self.state(), "verifying", context)
        self.assertIn(self.path, allowed, context)
        self.assertRegex(allowed, counts_pattern(bm, hm), context)
        self.assertRegex(allowed, counts_pattern(ba, ha), context)


class RatchetFindingTest(unittest.TestCase):
    """Функция храповика узла `test_integrity` на синтетических входах.

    Контракт вызова (решение Оператора, ANSWER-1 задачи):
    `test_integrity.ratchet_finding(base, head, mandate)`, где `base`/`head`
    — {путь файла диффа `tests/`: текст файла либо `None`} базы и головы,
    `mandate` — {элемент мандата: источник ANSWER-n}. Возврат ложен, когда
    находки нет; иначе его текст (`str`) называет числа «было → стало»
    методов и утверждений и файлы с убылью.
    """

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.cls = f"Fx{word(self.rng).capitalize()}Test"
        self.declining = f"tests/test_fx_{word(self.rng)}.py"
        self.growing = f"tests/test_fy_{word(self.rng)}.py"

    def note(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def methods(self, count: int, size: int) -> dict:
        return {f"test_{word(self.rng)}_{i}": [
            f"self.assertEqual(app.VALUE, {self.rng.randrange(10, 99)})"
            for _ in range(size)] for i in range(count)}

    def sources(self, decline: bool) -> tuple:
        """(base, head): файл `declining` теряет метод либо утверждения,
        файл `growing` прибавляет одно утверждение; при `decline` итог
        диффа убывает, иначе убыль первого файла не больше прибыли второго."""
        a_base = self.methods(self.rng.randrange(2, 5), 3)
        a_head = {name: list(body) for name, body in a_base.items()}
        victim = self.rng.choice(sorted(a_head))
        mode = self.rng.choice(("метод", "утверждение"))
        if decline and mode == "метод":
            del a_head[victim]
        elif decline:
            del a_head[victim][:2]
        else:
            a_head[victim].pop()
        b_base = self.methods(self.rng.randrange(1, 4), 2)
        b_head = {name: list(body) for name, body in b_base.items()}
        b_head[self.rng.choice(sorted(b_head))].append("self.assertTrue(app.VALUE)")
        if not decline:
            b_head[f"test_{word(self.rng)}_new"] = ["self.assertTrue(app.VALUE)"]
        base = {self.declining: fixture_source(self.cls, a_base),
                self.growing: fixture_source(self.cls, b_base)}
        head = {self.declining: fixture_source(self.cls, a_head),
                self.growing: fixture_source(self.cls, b_head)}
        return base, head

    def test_ac26_decline_alone_is_finding_and_file_mandate_covers_it(self):
        """Убыль итога диффа без мандата — находка с числами «было → стало» и файлом убыли; мандат на этот файл её снимает.

        Сценарий: два файла диффа `tests/` — один теряет метод или два
        утверждения (от зерна), другой прибавляет одно утверждение; итог
        убывает. Без мандата возврат истинен, его текст называет числа
        «было → стало» методов и утверждений (по
        `guard.qualified_test_methods`/`guard.test_assertions`) и файл с
        убылью, но не файл с прибылью. Мандат на файл с убылью — находки
        нет; мандат только на файл с прибылью — находка остаётся.

        Ловит мутацию: снятие сравнения «head не меньше base» по одной из
        сторон (методы или утверждения) — убыль этой стороны не находка;
        в находку попадают все файлы диффа, а не только с убылью; мандат
        засчитывается элементом любого файла диффа — мандат на файл с
        прибылью снимает находку.
        """
        base, head = self.sources(decline=True)
        (bm, ba) = fixture_counts(base.values())
        (hm, ha) = fixture_counts(head.values())
        found = test_integrity.ratchet_finding(base, head, {})
        text = str(found)
        context = self.note(f"методы {bm} → {hm}, утверждения {ba} → {ha}\n"
                            f"находка: {text}")
        self.assertTrue(hm < bm or ha < ba, context)
        self.assertTrue(found, context)
        self.assertIn(self.declining, text, context)
        self.assertNotIn(self.growing, text, context)
        self.assertRegex(text, counts_pattern(bm, hm), context)
        self.assertRegex(text, counts_pattern(ba, ha), context)
        covered = test_integrity.ratchet_finding(
            base, head, {self.declining: "ANSWER-1"})
        self.assertFalse(covered, self.note(f"мандат на файл убыли: {covered}"))
        other = test_integrity.ratchet_finding(
            base, head, {self.growing: "ANSWER-1"})
        self.assertTrue(other, self.note("мандат на файл прибыли снял находку"))

    def test_ac26_no_decline_is_no_finding(self):
        """Итог диффа не убыл — находки нет, хотя один из файлов потерял утверждение.

        Сценарий: файл с убылью теряет одно утверждение, другой файл
        прибавляет утверждение и метод; итог методов и утверждений не
        меньше базы, мандата нет — возврат ложен.

        Ловит мутацию: сравнение «head не меньше base» снято либо идёт по
        каждому файлу отдельно, а не по итогу диффа — находка на итоге без
        убыли.
        """
        base, head = self.sources(decline=False)
        (bm, ba) = fixture_counts(base.values())
        (hm, ha) = fixture_counts(head.values())
        found = test_integrity.ratchet_finding(base, head, {})
        context = self.note(f"методы {bm} → {hm}, утверждения {ba} → {ha}\n"
                            f"находка: {found}")
        self.assertTrue(hm >= bm and ha >= ba, context)
        self.assertFalse(found, context)


if __name__ == "__main__":
    unittest.main()
