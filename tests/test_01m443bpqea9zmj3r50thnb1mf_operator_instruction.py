"""Указание Оператора роли: `answer` в `in_dev`/`review` с файлом без строк
мандатов (AC-1..AC-5, AC-7, AC-8).

Группа: долгоживущий

Красен до реализации: `answer` в `in_dev`/`review` принимает файл только со строкой мандата зон или тестов, остальное отказывает «answer доступна только для задачи в состоянии escalated» — ANSWER не создаётся, записи «указание Оператора» нет (AC-1, AC-2, AC-7), пустой файл отказывает тем же текстом без слов «пустой файл указания» (AC-4), а живой чужой lease отказывает ещё раньше «задачу ведёт сессия …» (AC-8).

AC-3 (файл с мандатом — прежняя запись «ANSWER создан (мандат …)») и AC-5
(рубеж окружения роли) зелены с рождения: они держат сегодняшнее
поведение против правки, которая заведёт новую ветку приёма мимо них.

Заменяет: tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py::AnswerInDevWithoutMarkersTest::test_ac5_answer_in_dev_without_markers_keeps_old_refusal

Тот метод утверждает прежний отказ файлу без маркеров в `in_dev` — ровно
то поведение, которое меняет требование 1 этой задачи; его свойство
«маркер, процитированный не в начале строки, мандатом не считается»
здесь держит AC-3 с другой стороны: такой файл принимается как указание,
а не как мандат.

Песочница — `tests.sandbox.GitignoreCommittedRealGitSandbox`: пульт на
настоящем git, задача заведена `catalog.cmd_new` и переведена прямой
записью БД в нужное состояние. Документы задачи читаются из ссылки
документов `refs/artifacts/<id>` в git песочницы, журнал — через
`store.task_steps`. Тексты указаний, число уже существующих ответов,
состояние (`in_dev`/`review`) и вид мандата берутся случайно при каждом
запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import socket
import unittest
from unittest import mock

from orchestrator import (answer, catalog, config, lease, projects, review,
                          runner, store)
from orchestrator.advance_gates import mandate
from tests.sandbox import GitignoreCommittedRealGitSandbox, _alive_foreign_pid

INSTRUCTION_ACTION = "указание Оператора"
ESCALATED_ACTION = "ANSWER создан, ждёт approve"
MANDATE_ACTION_PREFIX = "ANSWER создан (мандат"
EMPTY_REASON = "пустой файл указания"
DOCS_REF_PREFIX = "refs/artifacts/"
# Строка мандата зон — литералом: имя константы в коде закрытое.
ZONES_MARKER = "Расширение зон разрешено:"
STATES = ("in_dev", "review")

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

SPEC_TEMPLATE = """---
task: TASK_ID
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: <название задачи>

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

WORDS = ("разбор", "падение", "причина", "модуль", "фикстура", "импорт",
         "порядок", "песочница", "ветка", "журнал", "шаг", "проверка")


class InstructionSandbox(GitignoreCommittedRealGitSandbox):
    """Пульт на настоящем git; задачи артели заводятся `catalog.cmd_new`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        self.use_role_map()
        templates = self.root / ".artel" / "templates-fixture"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "SPEC.md").write_text(SPEC_TEMPLATE, encoding="utf-8")
        for patcher in (
                mock.patch.object(config, "TEMPLATES", templates),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)

    # ----------------------------------------------------------- задача

    def new_task(self, state: str) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            task = catalog.cmd_new(f"Указание {self.rng.randrange(10 ** 6)}",
                                   target=config.DEFAULT_TARGET)
        self.set_state(task, state)
        return task

    def set_state(self, task: str, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task))
        conn.commit()

    def state(self, task: str) -> str:
        return store.get_task(store.db(), task)["state"]

    def seed_escalation_answers(self, task: str, count: int) -> None:
        """`count` ответов на эскалацию прежним путём (`escalated`), затем
        задача возвращается в своё состояние прямой записью БД."""
        back = self.state(task)
        for i in range(count):
            self.set_state(task, "escalated")
            out, failed = self.run_cmd(answer.cmd_answer, task, self.answer_file(
                f"Ответ на эскалацию {i}: {self.text()}\n"))
            self.assertFalse(failed, self.why(f"ответ на эскалацию отказан:\n{out}"))
        self.set_state(task, back)

    # ---------------------------------------------------------- команда

    def run_cmd(self, fn, *args) -> tuple:
        """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
        buf = io.StringIO()
        failed = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    failed = True
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), failed

    def text(self) -> str:
        """Случайный текст указания без строк мандатов, с уникальной меткой."""
        words = " ".join(self.rng.choice(WORDS)
                         for _ in range(self.rng.randrange(4, 12)))
        return f"Указание {self.rng.randrange(10 ** 9)}: {words}."

    def answer_file(self, text: str) -> str:
        path = self.root / ".artel" / f"answer-{self.rng.randrange(1 << 40)}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    # ------------------------------------------------- ссылка и журнал

    def answers(self, task: str) -> list:
        ref = DOCS_REF_PREFIX + task
        if not self.git("for-each-ref", "--format=%(objectname)", ref).strip():
            return []
        return sorted(p for p in self.git("ls-tree", "-r", "--name-only",
                                          ref).splitlines()
                      if p.rsplit("/", 1)[-1].startswith("ANSWER-"))

    def show(self, task: str, rel: str) -> str:
        return self.git("show", f"{DOCS_REF_PREFIX}{task}:{rel}")

    def rows(self, task: str) -> list:
        return list(store.task_steps(store.db(), task))

    def instruction_rows(self, task: str) -> list:
        return [r for r in self.rows(task)
                if INSTRUCTION_ACTION in (r["action"] or "")]

    def why(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"


def answer_rel(task: str, n: int) -> str:
    return "/".join(("tasks", task, f"ANSWER-{n}.md"))


def random_whitespace(rng: random.Random) -> str:
    """Пустая строка либо одни пробельные символы."""
    return "".join(rng.choice(" \t\n\r") for _ in range(rng.randrange(0, 12)))


# --------------------------------------------------------------------- AC-1

class InstructionAcceptedTest(InstructionSandbox):

    def test_ac1_instruction_in_in_dev_and_review_commits_next_answer(self):
        """Указание в `in_dev` и в `review` — следующий `ANSWER-n.md`, состояние прежнее, запись «указание Оператора».

        Для каждого из двух состояний (в случайном порядке) заводится своя
        задача, у части — 0–2 прежних ответа на эскалацию. `answer` с
        непустым файлом без строк мандатов, вызванная не из окружения роли,
        завершается без отказа: в ссылке документов появился
        `ANSWER-(k+1).md` с текстом файла, состояние задачи то же, в журнале
        есть запись актора `operator`, действие которой содержит «указание
        Оператора», а деталь — путь нового ANSWER.

        Ловит мутацию: ветка `in_dev`/`review` по-прежнему принимает только
        файлы с мандатом — отказ, ANSWER нет; указание принято только в
        `in_dev` (условие `state == "in_dev"`) — в `review` отказ; номер
        ANSWER считается от 1, а не от максимума существующих — путь
        записи не совпадёт с `ANSWER-(k+1).md`; запись журнала — прежняя
        «ANSWER создан» без слов «указание Оператора»; указание переводит
        задачу в `escalated` — состояние не то.
        """
        states = list(STATES)
        self.rng.shuffle(states)
        for state in states:
            with self.subTest(state=state, зерно=self.seed):
                task = self.new_task(state)
                prior = self.rng.randrange(0, 3)
                self.seed_escalation_answers(task, prior)
                text = self.text()

                out, failed = self.run_cmd(answer.cmd_answer, task,
                                           self.answer_file(text + "\n"))

                self.assertFalse(failed, self.why(f"{state}: answer отказала:\n{out}"))
                rel = answer_rel(task, prior + 1)
                found = self.answers(task)
                self.assertIn(rel, found, self.why(f"{state}: {rel} нет: {found}"))
                self.assertIn(text, self.show(task, rel),
                              self.why(f"{state}: в {rel} нет текста указания"))
                self.assertEqual(state, self.state(task),
                                 self.why(f"{state}: состояние сменилось"))
                rows = self.instruction_rows(task)
                self.assertTrue(
                    any(r["actor"] == "operator" and rel in (r["detail"] or "")
                        for r in rows),
                    self.why(f"{state}: нет записи operator «указание "
                             f"Оператора» с {rel}: "
                             f"{[(r['actor'], r['action'], r['detail']) for r in self.rows(task)]}"))


# --------------------------------------------------------------------- AC-2

class InstructionActionDistinctTest(InstructionSandbox):

    def test_ac2_instruction_action_differs_from_mandate_and_escalation_answer(self):
        """Действия трёх случаев приёма различимы: указание, мандат в `in_dev`, ответ в `escalated`.

        Три задачи: ответ на эскалацию в `escalated`, файл со строкой
        мандата (зон или тестов — случайно) в `in_dev`, указание без
        мандатов в `in_dev`. Каждый случай даёт свою запись журнала с
        путём своего ANSWER в детали; три действия попарно различны, только
        действие указания содержит «указание Оператора», действие ответа на
        эскалацию — прежнее «ANSWER создан, ждёт approve», действие мандата
        начинается с «ANSWER создан (мандат».

        Ловит мутацию: указание журналируется тем же действием, что ответ
        в `escalated` («ANSWER создан, ждёт approve») или прежним
        безымянным «ANSWER создан» — действие не содержит «указание
        Оператора»; слова «указание Оператора» дописаны во все записи
        приёма `in_dev`/`review` — их несёт и запись мандата.
        """
        escalated = self.new_task("escalated")
        mandated = self.new_task("in_dev")
        instructed = self.new_task("in_dev")
        files = {
            escalated: f"Ответ на эскалацию: {self.text()}\n",
            mandated: self.mandate_text(),
            instructed: self.text() + "\n",
        }
        actions = {}
        order = list(files)
        self.rng.shuffle(order)
        for task in order:
            out, failed = self.run_cmd(answer.cmd_answer, task,
                                       self.answer_file(files[task]))
            self.assertFalse(failed, self.why(f"answer отказала:\n{out}"))
            rel = answer_rel(task, 1)
            matched = [r["action"] for r in self.rows(task)
                       if r["actor"] == "operator" and rel in (r["detail"] or "")]
            self.assertEqual(1, len(matched),
                             self.why(f"записей приёма с {rel}: {matched}"))
            actions[task] = matched[0]

        self.assertEqual(3, len(set(actions.values())),
                         self.why(f"действия не различимы: {actions}"))
        self.assertIn(INSTRUCTION_ACTION, actions[instructed], self.why(str(actions)))
        self.assertNotIn(INSTRUCTION_ACTION, actions[mandated], self.why(str(actions)))
        self.assertNotIn(INSTRUCTION_ACTION, actions[escalated], self.why(str(actions)))
        self.assertEqual(ESCALATED_ACTION, actions[escalated], self.why(str(actions)))
        self.assertTrue(actions[mandated].startswith(MANDATE_ACTION_PREFIX),
                        self.why(str(actions)))

    def mandate_text(self) -> str:
        if self.rng.randrange(2):
            line = f"{mandate.TEST_WEAKENING_MANDATE_MARKER} tests/test_{self.rng.randrange(10 ** 6)}.py"
        else:
            line = f"{ZONES_MARKER} marker.txt"
        return f"{line}\n\nОснование: {self.text()}\n"


# --------------------------------------------------------------------- AC-3

class MandateKeepsItsRecordTest(InstructionSandbox):

    def test_ac3_mandate_file_keeps_mandate_record_not_instruction(self):
        """Файл со строкой мандата в `in_dev`/`review` — прежняя запись «ANSWER создан (мандат …)», не указание.

        Состояние (`in_dev`/`review`) и вид мандата (зон — существующий
        путь ветки задачи; тестов — случайный путь `tests/…`) выбираются
        случайно; кроме строки мандата файл несёт свободный текст. Команда
        завершается без отказа, `ANSWER-1.md` в ссылке документов,
        состояние прежнее, запись журнала с путём ANSWER начинается с
        «ANSWER создан (мандат» и называет элемент мандата; записи
        «указание Оператора» у задачи нет.

        Ловит мутацию: новая ветка указания поставлена раньше разбора
        мандатов (любой файл в `in_dev`/`review` — указание) — запись
        «указание Оператора» появится, а записи мандата с элементом не
        будет; запись указания пишется вдобавок к записи мандата — у задачи
        появится запись «указание Оператора».
        """
        state = self.rng.choice(STATES)
        task = self.new_task(state)
        if self.rng.randrange(2):
            element = f"tests/test_{self.rng.randrange(10 ** 6)}.py"
            marker = mandate.TEST_WEAKENING_MANDATE_MARKER
        else:
            element = "marker.txt"
            marker = ZONES_MARKER
        text = f"{marker} {element}\n\n{self.text()}\n"

        out, failed = self.run_cmd(answer.cmd_answer, task, self.answer_file(text))

        self.assertFalse(failed, self.why(f"{state}: answer отказала:\n{out}"))
        rel = answer_rel(task, 1)
        self.assertIn(rel, self.answers(task), self.why(out))
        self.assertEqual(state, self.state(task), self.why("состояние сменилось"))
        records = [r["action"] for r in self.rows(task)
                   if rel in (r["detail"] or "")]
        self.assertTrue(
            any(a.startswith(MANDATE_ACTION_PREFIX) and element in a for a in records),
            self.why(f"{state}: нет записи мандата с {element}: {records}"))
        self.assertEqual([], [r["action"] for r in self.instruction_rows(task)],
                         self.why(f"{state}: файл мандата записан как указание"))


# --------------------------------------------------------------------- AC-4

class EmptyInstructionRefusedTest(InstructionSandbox):

    def test_ac4_empty_or_blank_instruction_is_refused_by_name(self):
        """Пустой файл и файл из одних пробельных символов в `in_dev`/`review` — именованный отказ.

        Оба вида файла (нулевой длины и случайная смесь пробелов, табуляций
        и переводов строк) пробуются в каждом из двух состояний, на своей
        задаче. Команда завершается ненулевым кодом, вывод называет «пустой
        файл указания»; ANSWER в ссылке документов не появился, записи
        «указание Оператора» нет, состояние прежнее.

        Ловит мутацию: проверка пустоты сравнивает `raw == ""` без
        `strip()` — файл из пробелов принят как указание, ANSWER-1 создан;
        проверки пустоты нет вовсе — пустой файл принят; отказ прежним
        текстом «answer доступна только для задачи в состоянии escalated»
        — вывод не называет пустой файл указания.
        """
        cases = [(state, kind) for state in STATES for kind in ("zero", "blank")]
        self.rng.shuffle(cases)
        for state, kind in cases:
            with self.subTest(state=state, kind=kind, зерно=self.seed):
                task = self.new_task(state)
                content = "" if kind == "zero" else (
                    random_whitespace(self.rng) + self.rng.choice(" \t\n"))

                out, failed = self.run_cmd(answer.cmd_answer, task,
                                           self.answer_file(content))

                self.assertTrue(failed, self.why(f"{state}/{kind}: не отказала:\n{out}"))
                self.assertIn(EMPTY_REASON, out.lower(),
                              self.why(f"{state}/{kind}: отказ не называет "
                                       f"пустой файл указания:\n{out}"))
                self.assertEqual([], self.answers(task),
                                 self.why(f"{state}/{kind}: ANSWER создан"))
                self.assertEqual([], self.instruction_rows(task),
                                 self.why(f"{state}/{kind}: запись указания есть"))
                self.assertEqual(state, self.state(task), self.why("состояние сменилось"))


# --------------------------------------------------------------------- AC-5

class InstructionFromRoleEnvironmentRefusedTest(InstructionSandbox):

    def test_ac5_instruction_from_role_environment_is_refused(self):
        """Указание из окружения роли в `in_dev`/`review` — отказ, ANSWER нет, записи указания нет.

        `runner.in_role_environment()` подменён на истину; файл — обычное
        непустое указание без мандатов. Для каждого состояния (своя задача)
        команда отказывает, ANSWER в ссылке документов нет, записи
        «указание Оператора» нет, состояние прежнее.

        Ловит мутацию: приём указания встроен отдельной ветвью до рубежа
        окружения роли (рубеж остался только перед разбором мандатов) —
        роль сама выпишет себе `ANSWER-1.md` и запись «указание
        Оператора».
        """
        states = list(STATES)
        self.rng.shuffle(states)
        for state in states:
            with self.subTest(state=state, зерно=self.seed):
                task = self.new_task(state)
                path = self.answer_file(self.text() + "\n")
                with mock.patch.object(runner, "in_role_environment",
                                       return_value=True):
                    out, failed = self.run_cmd(answer.cmd_answer, task, path)

                self.assertTrue(failed, self.why(f"{state}: не отказала:\n{out}"))
                self.assertEqual([], self.answers(task),
                                 self.why(f"{state}: ANSWER создан:\n{out}"))
                self.assertEqual([], self.instruction_rows(task),
                                 self.why(f"{state}: запись указания есть"))
                self.assertEqual(state, self.state(task), self.why("состояние сменилось"))


# --------------------------------------------------------------------- AC-7

class InstructionReachesReviewPackageTest(InstructionSandbox):

    def test_ac7_instruction_in_review_is_in_next_review_package(self):
        """Указание в `review` попадает в пакет ревью следующего шага.

        Задача в `review`, у части — прежние ответы на эскалацию; `answer`
        с указанием. Пакет ревью (`review.review_package`, вход роли
        reviewer) после команды несёт текст указания.

        Ловит мутацию: указание коммитится не в ссылку документов задачи
        (например, в рабочую копию кодовой ветки) — пакет, собирающий все
        `ANSWER-n.md` ссылки, его не видит; указание в `review` не
        принимается — текста в пакете нет.
        """
        task = self.new_task("review")
        self.seed_escalation_answers(task, self.rng.randrange(0, 2))
        text = self.text()

        out, failed = self.run_cmd(answer.cmd_answer, task,
                                   self.answer_file(text + "\n"))

        self.assertFalse(failed, self.why(f"answer отказала:\n{out}"))
        t = store.get_task(store.db(), task)
        package = review.review_package(store.db(), task, t["title"], t["branch"])
        self.assertIn(text, package["text"],
                      self.why("текста указания нет в пакете ревью"))


# --------------------------------------------------------------------- AC-8

class InstructionDuringLiveStepTest(InstructionSandbox):

    def test_ac8_instruction_is_accepted_while_a_live_step_holds_the_lease(self):
        """Указание в `in_dev` при живом lease идущего шага — принято, lease и процесс шага не тронуты.

        Lease задачи держит живой процесс шага на этом же host со свежим
        heartbeat — то чужой сессией (цикл `auto` в другом терминале), то
        сессией самого вызывающего под другим pid (выбор случаен). `answer`
        с указанием завершается без отказа: `ANSWER-1.md` в ссылке
        документов, запись «указание Оператора» есть, состояние `in_dev`,
        строка lease (сессия, pid, host, heartbeat) та же, что до команды;
        `os.kill`/`os.killpg` ни разу не вызваны с pid шага.

        Ловит мутацию: `answer` указания по-прежнему берёт lease задачи
        (`lease.run_locked` без исключения) — отказ «задачу ведёт сессия …»
        либо «ведёт процесс … этой же сессии», ANSWER нет; указание
        «перехватывает» lease (`force=True`) — строка lease переписана на
        вызывающую сессию; указание останавливает шаг, чтобы тот подхватил
        его сразу, — `os.kill` с pid шага.
        """
        task = self.new_task("in_dev")
        pid = _alive_foreign_pid(self)
        foreign = bool(self.rng.randrange(2))
        holder = (f"auto-{self.rng.randrange(10 ** 6)}" if foreign
                  else lease.resolve_session_id(None))
        conn = store.db()
        store.insert_lease(conn, task, holder, pid, socket.gethostname(),
                           store.now())
        conn.commit()
        before = dict(store.lease_row(store.db(), task))
        text = self.text()
        kill_spy = mock.Mock(wraps=os.kill)
        killpg_spy = mock.Mock(wraps=os.killpg)

        with mock.patch.object(os, "kill", kill_spy), \
                mock.patch.object(os, "killpg", killpg_spy):
            out, failed = self.run_cmd(answer.cmd_answer, task,
                                       self.answer_file(text + "\n"))

        case = "чужая сессия" if foreign else "своя сессия, другой pid"
        self.assertFalse(failed, self.why(f"{case}: answer отказала:\n{out}"))
        rel = answer_rel(task, 1)
        self.assertIn(rel, self.answers(task), self.why(f"{case}: ANSWER нет"))
        self.assertIn(text, self.show(task, rel), self.why(case))
        self.assertTrue(self.instruction_rows(task),
                        self.why(f"{case}: записи «указание Оператора» нет"))
        self.assertEqual("in_dev", self.state(task), self.why("состояние сменилось"))
        after = store.lease_row(store.db(), task)
        self.assertIsNotNone(after, self.why(f"{case}: lease шага снят"))
        self.assertEqual(before, dict(after), self.why(f"{case}: lease шага изменён"))
        for spy in (kill_spy, killpg_spy):
            hit = [c for c in spy.call_args_list if c.args and c.args[0] == pid]
            self.assertEqual([], hit, self.why(f"{case}: процессу шага послан "
                                               f"сигнал: {hit}"))


if __name__ == "__main__":
    unittest.main()
