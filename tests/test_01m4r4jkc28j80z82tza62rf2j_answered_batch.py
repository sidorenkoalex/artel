"""Отвеченный батч вопросов аналитика не эскалирует задачу повторно:
признак «батч вопросов отвечен» на `approve` из эскалации и пропуск батча
с тем же хэшем в переходе `spec_writing` (AC-1 — AC-10).

Группа: долгоживущий

Красен до реализации: `approve` из эскалации по батчу признака «батч вопросов отвечен» не пишет (в `orchestrator/fsm.py` нет такой константы — AC-1, AC-4, AC-9, AC-10 (г) и подтест «возврат к раннему батчу» AC-6 падают на отсутствии строки признака), а `advance` из `spec_writing` эскалирует признанный батч по самому наличию `QUESTIONS.md` (AC-5, AC-7, AC-10 (а)); зелены с рождения сценарии прежнего поведения — признак не пишется (AC-2, AC-3), эскалация нового/изменённого батча (AC-6), рубеж до шага аналитика (AC-8, AC-10 (д)), AC-10 (б), (в).

Связка, которую держит файл, — «команда (`fsm.cmd_approve`/
`fsm.cmd_advance`) — FSM — журнал задачи — источник документов»:
`tests.sandbox.LightTransitionSandbox`, документы задачи на диске
`config.TASKS/<id>/` (песочница читает их как ветку документов, путь
`foreign=True`). Путь диска (`foreign=False`) — подмена публичного
`artifact_source.resolve`, как в `tests/test_artifact_escalation_marker.py`.
Сценарий «документы только на ветке, каталога на диске нет» — подмена
`gitcmd.show`/`gitcmd.ls_tree_files` словарём в памяти (`BranchDocs`).

Шаг аналитика — запись журнала `analyst` / `agent run finished`, та же,
что читает `auto._role_step_since_state_entry`. Текст батча (кириллица —
отличает UTF-8 от иных кодировок), номера ANSWER и метки версий — из
`random`; зерно печатается и входит в текст провала.

Провалидирован временным стабом реализации (откачен, не закоммичен):
все тесты зелены; мутанты стаба «нет проверки шага аналитика», «сравнение
с любой строкой признака», «признак до сверки ANSWER», «хэш не
сравнивается», «номер ANSWER = число файлов», «пропуск только на
ветке», «фраза не в detail перехода», «признак после set_state», «хэш
со strip», «approve читает только диск», «escalated_from/answer_baseline
не проверяются», «сбой чтения не обработан», «наличие QUESTIONS.md не
проверяется», «батч удаляется при пропуске», «пропуск после guard»
красят свои тесты.

Строка признака ищется по действию: значение строковой константы модуля
`orchestrator/fsm.py`, содержащее «батч вопросов отвечен» (имя константы
SPEC не называет). Строка пропуска — по формулировке «батч вопросов
признан отвеченным (ANSWER-n)» в действии или detail записи журнала.
"""
import hashlib
import os
import random
import re
import shutil
import unittest
from contextlib import ExitStack
from unittest import mock

from orchestrator import artifact_source, catalog, config, fsm, store
from tests.sandbox import LightTransitionSandbox, capture_new_task_id

ANSWERED_PHRASE = "батч вопросов отвечен"
SKIPPED_PHRASE = "батч вопросов признан отвеченным"
CYRILLIC = "абвгдежзиклмнопрстуфхцчшэюя"

QUESTIONS_TEXT = """---
task: {task}
type: questions
author_role: analyst
status: ready
schema_version: 2
---

# QUESTIONS: батч {marker}

## Вопросы

1. **Вопрос «{marker}»?**
   - A) да, {marker}
     - ломается: ничего, фикстура
     - ослабляется: ничего, фикстура
     - цена: нет
     - чьё решение: Оператор
   - B) нет
     - ломается: ничего, фикстура
     - ослабляется: ничего, фикстура
     - цена: нет
     - чьё решение: Оператор
   - дефолт: A.
"""

ANSWER_TEXT = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-{n}: ответ Оператора

## Ответы

1. A.
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: {status}
schema_version: 5
zones: tests/
budget_usd: 30
---

# SPEC: фикстура отвеченного батча

## Контекст

Фикстура.

## Требования

1. Требование фикстуры.

## Критерии приёмки

AC-1. Критерий фикстуры.

## Не входит

Ничего.
"""

TZ_TEXT = """# ТЗ фикстуры

Сделать фикстуру.
"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def disk_path():
    """Путь диска `spec_writing`/approve: `artifact_source.resolve`
    отвечает `foreign=False`."""
    return mock.patch.object(
        artifact_source, "resolve",
        lambda conn, task_id: (f"artifacts/{task_id}", False))


def answered_actions() -> set:
    """Значения строковых констант `orchestrator/fsm.py` с формулировкой
    признака «батч вопросов отвечен»."""
    return {value for value in vars(fsm).values()
            if isinstance(value, str) and ANSWERED_PHRASE in value.lower()}


class BranchDocs:
    """Ветка документов в памяти: `rel` -> текст; подменяет `gitcmd.show`
    и `gitcmd.ls_tree_files`, диск `config.TASKS` не участвует.
    `failing` — множество имён файлов, чтение которых отвечает сбоем git."""

    def __init__(self):
        self.files: dict = {}
        self.failing: set = set()

    def show(self, branch, rel, *, repo=None):
        if rel.rsplit("/", 1)[-1] in self.failing:
            return None, "git: сбой чтения (фикстура)"
        if rel in self.files:
            return self.files[rel], ""
        return None, "файла нет на ветке"

    def ls_tree_files(self, branch, rel_dir, *, repo=None):
        if rel_dir in self.files:
            return [rel_dir]
        prefix = rel_dir.rstrip("/") + "/"
        return sorted(rel for rel in self.files if rel.startswith(prefix))


class AnsweredBatchSandbox(LightTransitionSandbox):
    """Сценарии батча: эскалация, ответ, approve, шаг аналитика, advance."""

    TASK_TITLE = "Отвеченный батч вопросов"

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.branch_docs = None
        self.guard_calls: list = []
        real_guard = fsm.guard_refuses

        def spy_guard(conn, task_id, path, text=None):
            self.guard_calls.append((task_id, str(path)))
            return real_guard(conn, task_id, path, text=text)

        patcher = mock.patch.object(fsm, "guard_refuses", spy_guard)
        patcher.start()
        self.addCleanup(patcher.stop)

    # -- окружение ---------------------------------------------------------

    def use_branch_only(self) -> None:
        """Документы задачи — только на ветке в памяти; каталога на диске нет."""
        self.branch_docs = BranchDocs()
        for patcher in (mock.patch("orchestrator.gitcmd.show",
                                   self.branch_docs.show),
                        mock.patch("orchestrator.gitcmd.ls_tree_files",
                                   self.branch_docs.ls_tree_files)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def note(self, task: str, text: str = "") -> str:
        rows = "\n".join(f"  {r['actor']} | {r['action']} | {r['detail']}"
                         for r in self.steps(task))
        return f"{text}\nжурнал {task}:\n{rows}\n(зерно: {self.seed})"

    # -- документы ---------------------------------------------------------

    @staticmethod
    def doc_rel(task: str, name: str) -> str:
        """Путь документа на ветке: `<каталог задач>/<id>/<имя>`."""
        return f"{config.TASKS.name}/{task}/{name}"

    def put(self, task: str, name: str, text: str) -> None:
        if self.branch_docs is not None:
            self.branch_docs.files[self.doc_rel(task, name)] = text
            return
        tdir = config.TASKS / task
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / name).write_text(text, encoding="utf-8")

    def has_doc(self, task: str, name: str) -> bool:
        if self.branch_docs is not None:
            return self.doc_rel(task, name) in self.branch_docs.files
        return (config.TASKS / task / name).is_file()

    def drop(self, task: str, name: str) -> None:
        if self.branch_docs is not None:
            self.branch_docs.files.pop(self.doc_rel(task, name), None)
            return
        path = config.TASKS / task / name
        if path.exists():
            path.unlink()

    def word(self) -> str:
        return "".join(self.rng.choice(CYRILLIC) for _ in range(8))

    def questions(self, task: str, marker: str | None = None) -> str:
        text = QUESTIONS_TEXT.format(task=task, marker=marker or self.word())
        self.put(task, "QUESTIONS.md", text)
        return text

    def answer(self, task: str, n: int) -> None:
        self.put(task, f"ANSWER-{n}.md", ANSWER_TEXT.format(task=task, n=n))

    def spec(self, task: str, status: str = "ready") -> None:
        self.put(task, "SPEC.md", SPEC_TEXT.format(task=task, status=status))

    # -- задача и журнал ---------------------------------------------------

    def new_task(self, tz: bool = True) -> str:
        """Новая задача в `spec_writing`; `tz` — с `TZ.md` (роль analyst)."""
        _, task = capture_new_task_id(catalog.cmd_new, self.TASK_TITLE)
        if self.branch_docs is not None:
            shutil.rmtree(config.TASKS / task, ignore_errors=True)
        if tz:
            self.put(task, "TZ.md", TZ_TEXT)
        else:
            self.drop(task, "TZ.md")
        self.put_state(task, "spec_writing")
        return task

    def row(self, task: str):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (task,)).fetchone()

    def task_state(self, task: str) -> str:
        return self.row(task)["state"]

    def put_state(self, task: str, state: str, **fields) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task))
        conn.commit()
        if fields:
            store.update_task(conn, task, **fields)

    def steps(self, task: str) -> list:
        return list(store.task_steps(store.db(), task))

    def analyst_step(self, task: str) -> None:
        store.journal(store.db(), task, "analyst", "agent run finished", "rc=0")

    def advance(self, task: str) -> str:
        try:
            return self.capture(fsm.cmd_advance, task)
        except SystemExit as exc:
            return f"SystemExit: {exc.code}"

    def approve(self, task: str) -> str:
        try:
            return self.capture(fsm.cmd_approve, task)
        except SystemExit as exc:
            return f"SystemExit: {exc.code}"

    def answered_rows(self, task: str, start: int = 0) -> list:
        actions = answered_actions()
        return [r for r in self.steps(task)[start:] if r["action"] in actions]

    def skipped_rows(self, task: str, start: int = 0) -> list:
        return [r for r in self.steps(task)[start:]
                if not r["action"].startswith("state -> ")
                and SKIPPED_PHRASE in f"{r['action']} {r['detail']}"]

    def questions_guarded(self, task: str, start: int = 0) -> bool:
        return any(t == task and path.endswith("QUESTIONS.md")
                   for t, path in self.guard_calls[start:])

    # -- сценарий ----------------------------------------------------------

    def escalate(self, task: str) -> None:
        """`advance` из `spec_writing` с батчем — задача в `escalated`."""
        out = self.advance(task)
        self.assertEqual(self.task_state(task), "escalated",
                         self.note(task, f"батч не эскалировал:\n{out}"))

    def answered_cycle(self, task: str, n: int) -> str:
        """ANSWER-n и `approve` эскалации; задача обязана вернуться в
        `spec_writing`."""
        self.answer(task, n)
        out = self.approve(task)
        self.assertEqual(self.task_state(task), "spec_writing",
                         self.note(task, f"approve не вернул задачу:\n{out}"))
        return out

    def answered_batch(self, task: str, n: int = 1) -> str:
        """Батч эскалирован, отвечен ANSWER-n, задача возвращена approve и
        аналитик отработал шаг; возвращает текст батча."""
        text = self.questions(task)
        self.escalate(task)
        self.answered_cycle(task, n)
        self.analyst_step(task)
        return text


# ---------------------------------------------------------------------------
# AC-1: признак на approve.

class AnsweredMarkOnApproveTest(AnsweredBatchSandbox):

    def assert_mark(self, task: str, text: str, last_n: int, start: int) -> None:
        self.assertTrue(answered_actions(), self.note(
            task, "в orchestrator/fsm.py нет константы «батч вопросов отвечен»"))
        rows = self.steps(task)
        marks = [i for i, r in enumerate(rows) if i >= start
                 and r["action"] in answered_actions()]
        self.assertEqual(len(marks), 1, self.note(task, "строк признака не одна"))
        detail = rows[marks[0]]["detail"] or ""
        self.assertIn(f"sha256={sha256_text(text)}", detail, self.note(task))
        rest = detail.replace(sha256_text(text), "")
        self.assertRegex(rest, rf"(?<!\d){last_n}(?!\d)", self.note(
            task, f"в detail признака нет номера ANSWER-{last_n}"))
        returns = [i for i, r in enumerate(rows) if i >= start
                   and r["action"] == "state -> spec_writing"]
        self.assertTrue(returns, self.note(task, "approve не сменил состояние"))
        self.assertLess(marks[0], returns[0], self.note(
            task, "признак записан не раньше смены состояния approve"))

    def test_ac1_approve_marks_batch_with_hash_and_max_answer_number(self):
        """Approve эскалации по батчу пишет признак с sha256 текста и максимальным номером ANSWER до смены состояния.

        Сценарий: до эскалации у задачи уже лежит ANSWER-k (k — из
        зерна), батч эскалирует (`answer_baseline` = 1), Оператор кладёт
        ANSWER-m с m > k + 1 (пропуск номеров), `approve`. В журнале ровно
        одна строка с действием-константой «батч вопросов отвечен», её
        detail несёт `sha256=<sha256 UTF-8 текста QUESTIONS.md>` и m, и
        она стоит раньше записи `state -> spec_writing` этого approve.
        Варианты — путь ветки документов и путь диска (`foreign=False`).

        Ловит мутацию: признак не пишется вовсе — строки нет; номер ANSWER
        берётся числом файлов (2), а не максимумом n — в detail нет m;
        хэш берётся по `ANSWER`/SPEC или по байтам в иной кодировке — нет
        `sha256=` нужного значения; признак пишется после `set_state` —
        он позже записи `state -> spec_writing`.
        """
        for disk in (False, True):
            with self.subTest(path="диск" if disk else "ветка"):
                with ExitStack() as stack:
                    if disk:
                        stack.enter_context(disk_path())
                    task = self.new_task()
                    k = self.rng.randrange(1, 4)
                    m = k + self.rng.randrange(2, 5)
                    self.answer(task, k)
                    text = self.questions(task)
                    self.escalate(task)
                    start = len(self.steps(task))
                    self.answered_cycle(task, m)
                    self.assert_mark(task, text, m, start)

    def test_ac1_approve_marks_batch_present_only_on_docs_branch(self):
        """Признак пишется, когда батч и ANSWER лежат только на ветке документов, а каталога задачи на диске нет.

        Сценарий: ветка документов — словарь в памяти, `config.TASKS/<id>/`
        удалён; ANSWER-1 и ANSWER-3 на ветке (ANSWER-3 — ответ на
        эскалацию). Approve пишет признак с sha256 текста батча ветки и
        номером 3 до смены состояния.

        Ловит мутацию: approve читает QUESTIONS.md только с диска
        `config.TASKS` (не через `artifact_source.resolve` и ветку) —
        файла нет, строка признака не пишется; номер ANSWER берётся
        `glob` по диску — номера нет.
        """
        self.use_branch_only()
        task = self.new_task()
        self.assertFalse((config.TASKS / task).exists())
        self.answer(task, 1)
        text = self.questions(task)
        self.escalate(task)
        start = len(self.steps(task))
        self.answered_cycle(task, 3)
        self.assertFalse((config.TASKS / task).exists())
        self.assert_mark(task, text, 3, start)


# ---------------------------------------------------------------------------
# AC-2, AC-3: признак не пишется.

class NoMarkTest(AnsweredBatchSandbox):

    def test_ac2_mark_not_written_when_any_condition_fails(self):
        """Признак не пишется, если не выполнено хотя бы одно условие AC-1.

        Сценарий (подтесты, у каждого своя задача, всё остальное условие
        AC-1 выполнено): `escalated_from = tests_writing`;
        `answer_baseline` пуст; нового ANSWER после эскалации нет —
        approve отклонён сверкой; QUESTIONS.md в документах нет. Ни в
        одном подтесте нет строки «батч вопросов отвечен».

        Ловит мутацию: условие `escalated_from == spec_writing` не
        проверяется — признак у эскалации `tests_writing`; пустой
        `answer_baseline` не проверяется; признак пишется до сверки числа
        ANSWER — строка при отклонённом approve; отсутствие QUESTIONS.md
        не проверяется — строка с хэшем пустого текста.
        """
        with self.subTest(case="escalated_from=tests_writing"):
            task = self.new_task()
            self.questions(task)
            self.answer(task, 1)
            self.put_state(task, "escalated", escalated_from="tests_writing",
                           answer_baseline=0)
            out = self.approve(task)
            self.assertEqual(self.task_state(task), "tests_writing",
                             self.note(task, out))
            self.assertEqual(self.answered_rows(task), [], self.note(task, out))
        with self.subTest(case="answer_baseline пуст"):
            task = self.new_task()
            self.questions(task)
            self.answer(task, 1)
            self.put_state(task, "escalated", escalated_from="spec_writing",
                           answer_baseline=None)
            out = self.approve(task)
            self.assertEqual(self.task_state(task), "spec_writing",
                             self.note(task, out))
            self.assertEqual(self.answered_rows(task), [], self.note(task, out))
        with self.subTest(case="нового ANSWER нет"):
            task = self.new_task()
            self.questions(task)
            self.escalate(task)
            out = self.approve(task)
            self.assertEqual(self.task_state(task), "escalated",
                             self.note(task, out))
            self.assertEqual(self.answered_rows(task), [], self.note(task, out))
        with self.subTest(case="QUESTIONS.md нет"):
            task = self.new_task()
            self.questions(task)
            self.escalate(task)
            self.drop(task, "QUESTIONS.md")
            out = self.answered_cycle(task, 1)
            self.assertEqual(self.answered_rows(task), [], self.note(task, out))

    def test_ac3_unreadable_batch_no_mark_and_approve_passes(self):
        """Непрочитанный при approve QUESTIONS.md: признака нет, задача возвращается в `spec_writing`.

        Сценарий: батч эскалирован и отвечен ANSWER-1; на approve чтение
        QUESTIONS.md с ветки документов отвечает сбоем git (файл в
        перечне ветки есть). Задача в `spec_writing`, строки «батч
        вопросов отвечен» нет.

        Ловит мутацию: сбой чтения не обработан (хэш от `None`) —
        исключение, approve не доходит до смены состояния; сбой чтения
        превращён в отказ approve — задача остаётся в `escalated`; хэш
        берётся от пустой строки — строка признака появляется.
        """
        self.use_branch_only()
        task = self.new_task()
        self.questions(task)
        self.escalate(task)
        self.branch_docs.failing.add("QUESTIONS.md")
        self.answer(task, 1)
        try:
            out = self.approve(task)
        except Exception as exc:  # провал — с текстом исключения
            self.fail(self.note(task, f"approve упал: {exc!r}"))
        self.assertEqual(self.task_state(task), "spec_writing", self.note(task, out))
        self.assertEqual(self.answered_rows(task), [], self.note(task, out))


# ---------------------------------------------------------------------------
# AC-4: одна функция хэша.

class BatchHashTest(AnsweredBatchSandbox):

    def test_ac4_hash_same_for_branch_and_disk_and_ignores_mtime(self):
        """Хэш одного текста батча одинаков на ветке и на диске, равен sha256 UTF-8 и не зависит от mtime.

        Сценарий: две задачи с одинаковым кириллическим текстом батча (в
        тексте только id задачи и общая метка): первая проходит approve
        путём ветки, вторая — путём диска; хэши в detail признаков равны
        sha256 своих UTF-8 текстов. Затем у первой задачи (признание —
        путём ветки) mtime QUESTIONS.md сдвинут на случайное число суток,
        шаг аналитика, `advance` путём диска — батч пропущен (задача не
        в `escalated`).

        Ловит мутацию: на одном из путей хэш считается иначе (по байтам
        файла в другой кодировке, по `repr`, с `strip()`, по sha объекта
        git) — значения в detail не равны sha256 текста либо advance на
        диске не узнаёт признание ветки и эскалирует; в хэш подмешано
        время изменения файла — после `utime` эскалация.
        """
        marker = self.word()
        first = self.new_task(tz=False)
        first_text = self.questions(first, marker)
        self.escalate(first)
        self.answered_cycle(first, 1)
        with disk_path():
            second = self.new_task(tz=False)
            second_text = self.questions(second, marker)
            self.escalate(second)
            self.answered_cycle(second, 1)
        for task, text in ((first, first_text), (second, second_text)):
            rows = self.answered_rows(task)
            self.assertEqual(len(rows), 1, self.note(task))
            self.assertIn(f"sha256={sha256_text(text)}", rows[0]["detail"],
                          self.note(task))

        path = config.TASKS / first / "QUESTIONS.md"
        shift = self.rng.randrange(1, 400) * 86400
        stat = path.stat()
        os.utime(path, (stat.st_atime + shift, stat.st_mtime + shift))
        self.spec(first, "draft")
        self.analyst_step(first)
        with disk_path():
            out = self.advance(first)
        self.assertEqual(self.task_state(first), "spec_writing",
                         self.note(first, out))


# ---------------------------------------------------------------------------
# AC-5, AC-7: пропуск признанного батча.

class SkipAnsweredBatchTest(AnsweredBatchSandbox):

    def run_skip(self, disk: bool, tz: bool, status: str) -> tuple:
        with ExitStack() as stack:
            if disk:
                stack.enter_context(disk_path())
            task = self.new_task(tz=tz)
            n = self.rng.randrange(1, 5)
            for k in range(1, n):
                self.answer(task, k)
            self.answered_batch(task, n)
            self.spec(task, status)
            start = len(self.steps(task))
            guard_start = len(self.guard_calls)
            out = self.advance(task)
        return task, n, start, guard_start, out

    def test_ac5_answered_batch_with_analyst_step_is_skipped(self):
        """Признанный батч после шага аналитика не эскалирует: SPEC ready уходит в аудит/гейт, не ready — остаётся.

        Сценарий (подтесты: путь ветки/диска × задача с ТЗ/без ТЗ ×
        SPEC.md ready/draft): батч эскалирован, отвечен, approve, шаг
        аналитика, `advance`. Задача не в `escalated`; guard на
        QUESTIONS.md не вызывался; при ready — `spec_audit` (с ТЗ) или
        `spec_gate` (без ТЗ), при draft — `spec_writing`; QUESTIONS.md в
        документах на месте.

        Ловит мутацию: пропуск не сделан — батч эскалирует снова; пропуск
        сделан на одном из двух путей (ветка/диск) — подтест другого пути
        эскалирует; пропуск выполнен после `guard_refuses` — вызов guard
        на QUESTIONS.md есть; при пропуске батч удаляется — файла нет.
        """
        expected = {True: "spec_audit", False: "spec_gate"}
        for disk in (False, True):
            for tz in (True, False):
                for status in ("ready", "draft"):
                    with self.subTest(disk=disk, tz=tz, status=status):
                        task, _n, _s, guard_start, out = self.run_skip(
                            disk, tz, status)
                        want = expected[tz] if status == "ready" else "spec_writing"
                        self.assertEqual(self.task_state(task), want,
                                         self.note(task, out))
                        self.assertFalse(self.questions_guarded(task, guard_start),
                                         self.note(task, "guard проверял QUESTIONS.md"))
                        self.assertTrue(self.has_doc(task, "QUESTIONS.md"),
                                        self.note(task))

    def test_ac7_skip_journals_phrase_and_transition_detail(self):
        """Каждый пропуск пишет «батч вопросов признан отвеченным (ANSWER-n)»; detail перехода несёт ту же фразу.

        Сценарий: признанный батч (номер n — из зерна), SPEC.md draft —
        два `advance` подряд дают две строки пропуска с ANSWER-n; затем
        SPEC.md ready — переход в `spec_audit` (с ТЗ) / `spec_gate` (без
        ТЗ), его detail содержит «батч вопросов признан отвеченным
        (ANSWER-n)».

        Ловит мутацию: строка пропуска пишется один раз на задачу, а не
        на каждый пропуск — после второго advance строк одна; номер
        ANSWER не из строки признака (из счёта файлов) — фраза с другим n;
        detail перехода прежний («SPEC готов …») без фразы пропуска.
        """
        for tz, target in ((True, "spec_audit"), (False, "spec_gate")):
            with self.subTest(tz=tz):
                task, n, start, _g, out = self.run_skip(False, tz, "draft")
                self.advance(task)
                phrase = f"{SKIPPED_PHRASE} (ANSWER-{n})"
                rows = [r for r in self.skipped_rows(task, start)
                        if phrase in f"{r['action']} {r['detail']}"]
                self.assertEqual(len(rows), 2, self.note(task, out))
                self.spec(task, "ready")
                self.advance(task)
                self.assertEqual(self.task_state(task), target, self.note(task))
                transitions = [r for r in self.steps(task)
                               if r["action"] == f"state -> {target}"]
                self.assertTrue(transitions, self.note(task))
                self.assertIn(phrase, transitions[-1]["detail"] or "",
                              self.note(task))


# ---------------------------------------------------------------------------
# AC-6: иной хэш — эскалация, как сегодня.

class MismatchEscalatesTest(AnsweredBatchSandbox):

    def assert_escalates(self, task: str) -> None:
        start = len(self.steps(task))
        guard_start = len(self.guard_calls)
        out = self.advance(task)
        self.assertEqual(self.task_state(task), "escalated", self.note(task, out))
        self.assertTrue(self.questions_guarded(task, guard_start),
                        self.note(task, "guard не проверил QUESTIONS.md"))
        self.assertEqual(self.skipped_rows(task, start), [], self.note(task))

    def test_ac6_batch_not_matching_last_mark_escalates(self):
        """Батч, не совпадающий по хэшу с последним признаком, эскалирует с проверкой guard.

        Сценарий (подтесты): новый батч без признака (шаг аналитика в
        журнале есть); признанный батч, изменённый после признания (шаг
        аналитика после возврата есть); батч A признан, затем изменён на
        B, эскалирован, отвечен и признан, после шага аналитика текст
        возвращён к A — совпадает только с более ранней строкой
        признака. Во всех — `escalated`, guard вызван на QUESTIONS.md,
        строки пропуска нет.

        Ловит мутацию: пропуск по самому наличию строки признака (хэш не
        сравнивается) — изменённый батч не эскалирует; сравнение с любой
        строкой признака, не с последней — возврат к тексту A не
        эскалирует; признак без строк сравнивается с пустым хэшем —
        новый батч ведёт себя неожиданно.
        """
        for disk in (False, True):
            with ExitStack() as stack:
                if disk:
                    stack.enter_context(disk_path())
                with self.subTest(disk=disk, case="новый батч"):
                    task = self.new_task()
                    self.spec(task, "ready")
                    self.analyst_step(task)
                    self.questions(task)
                    self.assert_escalates(task)
                with self.subTest(disk=disk, case="изменённый батч"):
                    task = self.new_task()
                    self.answered_batch(task, 1)
                    self.spec(task, "ready")
                    self.questions(task)
                    self.assert_escalates(task)
                with self.subTest(disk=disk, case="возврат к раннему батчу"):
                    task = self.new_task()
                    first = self.answered_batch(task, 1)
                    self.spec(task, "draft")
                    self.questions(task)
                    self.escalate(task)
                    self.answered_cycle(task, 2)
                    self.analyst_step(task)
                    self.assertEqual(len(self.answered_rows(task)), 2,
                                     self.note(task))
                    self.put(task, "QUESTIONS.md", first)
                    self.spec(task, "ready")
                    self.assert_escalates(task)


# ---------------------------------------------------------------------------
# AC-8, AC-9: рубеж «сначала шаг аналитика».

class RoleStepGateTest(AnsweredBatchSandbox):

    def approved_without_step(self, task: str) -> None:
        """Шаг аналитика был ДО эскалации; батч эскалирован, отвечен,
        approve — после возврата шага нет."""
        self.questions(task)
        self.analyst_step(task)
        self.escalate(task)
        self.answered_cycle(task, 1)
        self.spec(task, "ready")

    def test_ac8_old_ready_spec_not_advanced_before_analyst_step(self):
        """После approve и до шага аналитика старый SPEC.md ready не уходит из `spec_writing` в аудит/гейт.

        Сценарий (подтесты: путь ветки/диска × с ТЗ/без ТЗ): шаг
        аналитика до эскалации, батч эскалирован, ANSWER-1, approve,
        SPEC.md ready; `advance` до шага аналитика. Задача не в
        `spec_audit`/`spec_gate`.

        Ловит мутацию: пропуск батча проверяет только хэш, без шага
        аналитика после последнего входа — старый SPEC уходит в аудит/
        гейт; шаг аналитика ищется по всему журналу, а не после входа —
        шаг до эскалации засчитан.
        """
        for disk in (False, True):
            for tz in (True, False):
                with ExitStack() as stack, self.subTest(disk=disk, tz=tz):
                    if disk:
                        stack.enter_context(disk_path())
                    task = self.new_task(tz=tz)
                    self.approved_without_step(task)
                    out = self.advance(task)
                    self.assertNotIn(self.task_state(task),
                                     ("spec_audit", "spec_gate"),
                                     self.note(task, out))

    def test_ac9_manual_advance_before_analyst_step_escalates(self):
        """Ручной `advance` сразу после approve, до шага аналитика, эскалирует и проверяет батч guard'ом.

        Сценарий (подтесты: путь ветки/диска): шаг аналитика до
        эскалации, батч эскалирован, ANSWER-1, approve (признак записан —
        проверяется), SPEC.md ready; `fsm.cmd_advance`. Задача в
        `escalated`, guard вызван на QUESTIONS.md, строки «батч вопросов
        признан отвеченным» нет.

        Ловит мутацию: проверка шага аналитика оставлена только в
        пред-advance `auto`, сам переход `spec_writing` её не делает —
        ручной advance пропускает батч и уводит задачу в `spec_audit`.
        """
        for disk in (False, True):
            with ExitStack() as stack, self.subTest(disk=disk):
                if disk:
                    stack.enter_context(disk_path())
                task = self.new_task()
                self.approved_without_step(task)
                self.assertEqual(len(self.answered_rows(task)), 1, self.note(task))
                start = len(self.steps(task))
                guard_start = len(self.guard_calls)
                out = self.advance(task)
                self.assertEqual(self.task_state(task), "escalated",
                                 self.note(task, out))
                self.assertTrue(self.questions_guarded(task, guard_start),
                                self.note(task, out))
                self.assertEqual(self.skipped_rows(task, start), [],
                                 self.note(task, out))


# ---------------------------------------------------------------------------
# AC-10: тесты на мутации (а)-(д).

class MutationTest(AnsweredBatchSandbox):

    def test_ac10_a_answered_unchanged_batch_does_not_escalate(self):
        """(а) Признанный неизменный батч после шага аналитика не эскалирует.

        Сценарий: батч эскалирован, ANSWER-1, approve, шаг аналитика,
        SPEC.md draft, `advance`. Задача в `spec_writing`.

        Ловит мутацию: отвеченный неизменный батч эскалирует (пропуск не
        срабатывает: признак не пишется, хэш не сравнивается или берётся
        не та строка журнала) — задача в `escalated`.
        """
        task = self.new_task()
        self.answered_batch(task, 1)
        self.spec(task, "draft")
        out = self.advance(task)
        self.assertEqual(self.task_state(task), "spec_writing", self.note(task, out))

    def test_ac10_b_changed_batch_escalates(self):
        """(б) Изменённый после признания батч эскалирует.

        Сценарий: батч признан, шаг аналитика, текст QUESTIONS.md заменён
        новым, `advance`. Задача в `escalated`.

        Ловит мутацию: изменённый батч не эскалирует — пропуск по наличию
        признака без сравнения хэша.
        """
        task = self.new_task()
        self.answered_batch(task, 1)
        self.spec(task, "draft")
        self.questions(task)
        out = self.advance(task)
        self.assertEqual(self.task_state(task), "escalated", self.note(task, out))

    def test_ac10_c_return_to_earlier_answered_batch_escalates(self):
        """(в) Возврат к тексту более раннего признанного батча эскалирует.

        Сценарий: батч A признан, затем B эскалирован, отвечен ANSWER-2 и
        признан; шаг аналитика; QUESTIONS.md снова с текстом A;
        `advance`. Задача в `escalated`.

        Ловит мутацию: возврат к тексту более раннего отвеченного батча не
        эскалирует — хэш сравнивается с любой строкой признака, а не с
        последней.
        """
        task = self.new_task()
        first = self.answered_batch(task, 1)
        self.spec(task, "draft")
        self.questions(task)
        self.escalate(task)
        self.answered_cycle(task, 2)
        self.analyst_step(task)
        self.put(task, "QUESTIONS.md", first)
        out = self.advance(task)
        self.assertEqual(self.task_state(task), "escalated", self.note(task, out))

    def test_ac10_d_no_mark_without_new_answer(self):
        """(г) Approve без нового ANSWER после эскалации не признаёт батч.

        Сценарий: батч эскалирован, ANSWER не добавлен, `approve`
        (отклонён), затем ANSWER-1 и approve. Строка признака одна —
        от второго approve.

        Ловит мутацию: признание батча без ANSWER после эскалации —
        признак пишется до сверки числа ANSWER, у отклонённого approve
        тоже, строк две.
        """
        task = self.new_task()
        self.questions(task)
        self.escalate(task)
        self.approve(task)
        self.assertEqual(self.task_state(task), "escalated", self.note(task))
        self.assertEqual(self.answered_rows(task), [], self.note(task))
        self.answered_cycle(task, 1)
        self.assertEqual(len(self.answered_rows(task)), 1, self.note(task))

    def test_ac10_e_mark_does_not_lift_analyst_step_gate(self):
        """(д) Признание батча не снимает рубеж «сначала шаг аналитика».

        Сценарий: батч эскалирован, ANSWER-1, approve, SPEC.md ready,
        `advance` без шага аналитика. Задача в `escalated`, не в
        `spec_audit`.

        Ловит мутацию: признание снимает рубеж — пропуск батча по одному
        хэшу, без проверки шага аналитика после возврата, и старый SPEC
        уходит в `spec_audit`.
        """
        task = self.new_task()
        self.questions(task)
        self.escalate(task)
        self.answered_cycle(task, 1)
        self.spec(task, "ready")
        out = self.advance(task)
        self.assertEqual(self.task_state(task), "escalated", self.note(task, out))


if __name__ == "__main__":
    unittest.main()
