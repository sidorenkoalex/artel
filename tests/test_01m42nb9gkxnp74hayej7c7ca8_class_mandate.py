"""Мандат на тесты: элемент-класс покрывает находки о методах класса, и
мандат тестов принимается командой `answer` в `in_dev` (AC-1..AC-6).

Группа: долгоживущий

Красен до реализации: элемент `путь::Класс` покрывает только находку с
точно таким квалифицированным именем, поэтому находки «метод Класс::m
исчез» им не покрыты — гейт мержа эскалирует (AC-1, контроль покрытия
класса `A` в AC-2); `answer` в `in_dev` с файлом, несущим только строку
«Ослабление тестов разрешено: …», отказывает «answer доступна только для
задачи в состоянии escalated» (AC-4). AC-3 (элемент метода покрывает
только свой метод), AC-5 (файл без маркеров — с задачи 01M443BPQEA9ZMJ3R50THNB1MF
указание Оператора, не мандат) и AC-6
(рубеж окружения роли отказывает) зелёные с рождения: они держат
сегодняшнее поведение против правки, которая расширит покрытие или приём.

Песочницы — `tests.sandbox`: для гейта `ConnRealGitSandbox` (база —
коммит на main, голова — ветка задачи, мандат — `ANSWER-1.md` на ветке
документов коммитом ответа Оператора); для `answer` —
`GitignoreCommittedRealGitSandbox` с задачей, заведённой `catalog.cmd_new`.
Гейт читается публичными входами `test_integrity.uncovered` (общий вход
перехода `in_dev -> verifying` и гейта мержа) и
`test_integrity.merge_gate_escalates`; `answer` — `answer.cmd_answer`.
Имена файла, классов, методов и элементов мандата берутся случайными при
каждом запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import unittest
from unittest import mock

from orchestrator import (answer, catalog, config, projects, runner,
                          store)
from orchestrator.advance_gates import test_integrity
from tests.sandbox import (ConnRealGitSandbox,
                           GitignoreCommittedRealGitSandbox)

TASK = "T001"
BRANCH = "task/t001-mandat-klassa"
DOCS = "artifact/t001"
STATE = "review"
ALLOWED_ACTION = "ослабление тестов разрешено мандатом Оператора"
ANSWER_SUBJECT = f"{TASK}: ANSWER-1 — ответ Оператора"
MARKER = test_integrity.TEST_WEAKENING_MANDATE_MARKER
SEP = "::"
OLD_REFUSAL = "answer доступна только для задачи в состоянии escalated"
DOCS_REF_PREFIX = "refs/artifacts/"

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


def seeded(test) -> random.Random:
    """Генератор входов с напечатанным зерном (`test.seed`)."""
    test.seed = random.randrange(1 << 30)
    print(f"зерно: {test.seed}")
    return random.Random(test.seed)


def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def class_source(classes: dict) -> str:
    """Файл тестов: {имя класса: [имена методов]}."""
    parts = ["import unittest\n"]
    for cls, methods in classes.items():
        parts.append(f"\n\nclass {cls}(unittest.TestCase):\n")
        for method in methods:
            parts.append(f"\n    def {method}(self):\n"
                         f"        self.assertEqual(compute(), 1)\n")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Гейт сохранности тестов: AC-1..AC-3.

class GateSandbox(ConnRealGitSandbox):
    """Задача `TASK` в `STATE`; дифф `tests/` между main и веткой задачи,
    мандат — `ANSWER-1.md` на ветке документов `DOCS`."""

    seed = None

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, TASK, "Мандат класса", STATE, BRANCH,
                          config.DEFAULT_TARGET, 10.0)
        self.conn.commit()

    def write(self, rel: str, text: str) -> None:
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit_diff(self, path: str, base: dict, head: dict) -> None:
        self.write(path, class_source(base))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        self.checkout(BRANCH, create=True)
        self.write(path, class_source(head))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "голова")
        self.checkout(config.MAIN_BRANCH)

    def add_mandate(self, elements: str) -> None:
        self.checkout(DOCS, create=True)
        self.write("/".join(("tasks", TASK, "ANSWER-1.md")),
                   f"# Ответ Оператора\n\n{MARKER} {elements}\n"
                   f"Основание: решение Оператора.\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", ANSWER_SUBJECT)
        self.checkout(config.MAIN_BRANCH)

    def uncovered_lines(self) -> list:
        found, git_detail = test_integrity.uncovered(self.conn, TASK, BRANCH,
                                                     DOCS)
        self.assertIsNotNone(found, self.why(f"git не ответил: {git_detail}"))
        return [f.line for f in found]

    def merge_gate(self) -> bool:
        return test_integrity.merge_gate_escalates(self.conn, TASK, STATE,
                                                   BRANCH, DOCS)

    def allowed(self) -> str:
        return "\n".join(row["detail"] or "" for row in self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (TASK,)) if row["action"] == ALLOWED_ACTION)

    def state(self) -> str:
        return self.conn.execute("SELECT state FROM tasks WHERE id=?",
                                 (TASK,)).fetchone()["state"]

    def why(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})" if self.seed is not None else text


def vanished(name: str) -> str:
    return f"метод {name} исчез"


class ClassElementCoversItsMethodsTest(GateSandbox):

    def test_ac1_class_element_covers_vanished_methods_of_the_class(self):
        """Мандат `tests/x.py::A` покрывает исчезнувшие методы класса `A`.

        Файл `tests/test_<случайно>.py`, класс `A` (случайное имя) с
        несколькими методами; в голове ветки два-три метода `A` удалены,
        один оставлен. Мандат — элемент `путь::A`. Общий вход гейтов
        (`uncovered`) не возвращает ни одной находки о `A`, гейт мержа не
        эскалирует и состояние прежнее, а запись «ослабление тестов
        разрешено мандатом Оператора» называет каждый исчезнувший метод.

        Ловит мутацию: покрытие сверяет только точное квалифицированное
        имя находки (элемент `путь::A` не покрывает `путь::A::m`) —
        находки о методах вернутся из `uncovered`, гейт мержа уйдёт в
        `escalated`, записи «разрешено» не будет.
        """
        rng = seeded(self)
        path = f"tests/test_{word(rng)}.py"
        cls = "C" + word(rng).capitalize()
        methods = [f"test_{word(rng)}_{i}" for i in range(rng.randrange(3, 5))]
        removed = methods[:-1][:rng.randrange(2, len(methods))]
        self.commit_diff(path, {cls: methods},
                         {cls: [m for m in methods if m not in removed]})
        self.add_mandate(f"{path}{SEP}{cls}")

        rest = self.uncovered_lines()
        self.assertEqual([], rest, self.why(f"не покрыты: {rest}"))
        self.assertFalse(self.merge_gate(), self.why("гейт мержа эскалировал"))
        self.assertEqual(STATE, self.state(), self.why("состояние сменилось"))
        allowed = self.allowed()
        for method in removed:
            self.assertIn(vanished(f"{cls}{SEP}{method}"), allowed,
                          self.why(f"запись «разрешено» не называет "
                                   f"{method}: {allowed!r}"))
        self.assertIn("ANSWER-1", allowed, self.why(allowed))


class ClassElementDoesNotCoverOtherClassTest(GateSandbox):

    def test_ac2_class_element_does_not_cover_another_class_of_the_file(self):
        """Мандат `tests/x.py::A` не покрывает исчезнувшие методы класса `B` того же файла.

        В файле классы `A` и `B`; имя `B` начинается с имени `A` (`A` +
        случайный хвост), чтобы покрытие по строковому префиксу без
        разделителя тоже было видно. В голове у каждого класса удалён
        метод. Мандат — `путь::A`. `uncovered` возвращает находку о методе
        `B` и не возвращает находку о методе `A` (контроль: элемент-класс
        работает), гейт мержа эскалирует, задача в `escalated`.

        Ловит мутацию: элемент `путь::A` покрывает все находки файла
        (сравнение по пути без имени) или сверяется префиксом строки
        `путь::A` без `::` на конце — находка о `B` покрыта, гейт мержа не
        эскалирует.
        """
        rng = seeded(self)
        path = f"tests/test_{word(rng)}.py"
        cls_a = "C" + word(rng).capitalize()
        cls_b = cls_a + word(rng, 4).capitalize()
        a_methods = [f"test_{word(rng)}_a{i}" for i in range(2)]
        b_methods = [f"test_{word(rng)}_b{i}" for i in range(2)]
        self.commit_diff(path, {cls_a: a_methods, cls_b: b_methods},
                         {cls_a: a_methods[1:], cls_b: b_methods[1:]})
        self.add_mandate(f"{path}{SEP}{cls_a}")

        rest = "\n".join(self.uncovered_lines())
        self.assertIn(vanished(f"{cls_b}{SEP}{b_methods[0]}"), rest,
                      self.why(f"находка о классе B покрыта: {rest!r}"))
        self.assertNotIn(vanished(f"{cls_a}{SEP}{a_methods[0]}"), rest,
                         self.why(f"контроль: находка о классе A не покрыта: "
                                  f"{rest!r}"))
        self.assertTrue(self.merge_gate(), self.why("гейт мержа не эскалировал"))
        self.assertEqual("escalated", self.state(), self.why("не escalated"))


class MethodElementCoversOnlyItsMethodTest(GateSandbox):

    def test_ac3_method_element_covers_only_the_named_method(self):
        """Мандат `tests/x.py::A::m1` покрывает `A::m1` и не покрывает `A::m2`.

        Имя `m2` начинается с имени `m1` (`m1` + случайный хвост). В
        голове удалены оба метода, третий оставлен. `uncovered` не
        возвращает находку о `m1` и возвращает находку о `m2`; гейт мержа
        эскалирует; запись «разрешено» называет `m1`.

        Ловит мутацию: элемент `путь::A::m1` трактуется как элемент-класс
        или как префикс строки — находка о `m2` покрыта и гейт мержа не
        эскалирует; элемент метода перестаёт покрывать свой метод при
        переделке покрытия под классы — находка о `m1` вернётся из
        `uncovered`.
        """
        rng = seeded(self)
        path = f"tests/test_{word(rng)}.py"
        cls = "C" + word(rng).capitalize()
        m1 = f"test_{word(rng)}"
        m2 = f"{m1}_{word(rng, 3)}"
        kept = f"test_{word(rng)}_kept"
        self.commit_diff(path, {cls: [m1, m2, kept]}, {cls: [kept]})
        self.add_mandate(f"{path}{SEP}{cls}{SEP}{m1}")

        rest = "\n".join(self.uncovered_lines())
        self.assertIn(vanished(f"{cls}{SEP}{m2}"), rest,
                      self.why(f"находка о m2 покрыта: {rest!r}"))
        self.assertNotIn(vanished(f"{cls}{SEP}{m1}"), rest,
                         self.why(f"находка о m1 не покрыта: {rest!r}"))
        self.assertTrue(self.merge_gate(), self.why("гейт мержа не эскалировал"))
        self.assertIn(vanished(f"{cls}{SEP}{m1}"), self.allowed(),
                      self.why(f"запись «разрешено» без m1: {self.allowed()!r}"))


# ---------------------------------------------------------------------------
# Команда `answer` в `in_dev`: AC-4..AC-6.

class AnswerSandbox(GitignoreCommittedRealGitSandbox):
    """Пульт на настоящем git, задача артели заведена `catalog.cmd_new` и
    переведена прямой записью БД в `in_dev`."""

    seed = None

    def setUp(self):
        super().setUp()
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
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.task = catalog.cmd_new("Мандат в in_dev",
                                        target=config.DEFAULT_TARGET)
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     ("in_dev", self.task))
        conn.commit()

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

    def answer_file(self, text: str) -> str:
        path = self.root / ".artel" / f"answer-{random.randrange(1 << 30)}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def docs_files(self) -> list:
        ref = DOCS_REF_PREFIX + self.task
        exists = self.git("for-each-ref", "--format=%(objectname)", ref).strip()
        if not exists:
            return []
        return [line for line in self.git("ls-tree", "-r", "--name-only",
                                          ref).splitlines() if line]

    def answers(self) -> list:
        return [p for p in self.docs_files()
                if p.rsplit("/", 1)[-1].startswith("ANSWER-")]

    def show(self, rel: str) -> str:
        return self.git("show", f"{DOCS_REF_PREFIX}{self.task}:{rel}")

    def state(self) -> str:
        return store.get_task(store.db(), self.task)["state"]

    def journal(self) -> list:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(store.db(), self.task)]

    def why(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})" if self.seed is not None else text


def random_elements(rng: random.Random) -> list:
    """Один-три элемента мандата тестов всех трёх форм."""
    out = []
    for _ in range(rng.randrange(1, 4)):
        path = f"tests/test_{word(rng)}.py"
        form = rng.randrange(3)
        if form == 0:
            out.append(path)
        elif form == 1:
            out.append(f"{path}{SEP}C{word(rng).capitalize()}")
        else:
            out.append(f"{path}{SEP}C{word(rng).capitalize()}{SEP}"
                       f"test_{word(rng)}")
    return out


class AnswerInDevTestMandateTest(AnswerSandbox):

    def test_ac4_test_mandate_answer_in_dev_commits_and_journals_elements(self):
        """`answer` в `in_dev` с файлом мандата тестов коммитит ANSWER-n, состояние прежнее, журнал называет элементы.

        Файл ответа несёт только строку «Ослабление тестов разрешено: …»
        со случайными элементами трёх форм (путь, путь::Класс,
        путь::Класс::метод) и абзац основания. Команда завершается без
        отказа; в ссылке документов задачи появился `ANSWER-1.md`,
        несущий строку мандата; задача осталась в `in_dev`; в журнале
        есть запись, называющая каждый элемент мандата.

        Ловит мутацию: ветка `in_dev`/`review` принимает только маркер
        мандата зон — команда отказывает «answer доступна только для
        задачи в состоянии escalated», ANSWER нет; приём есть, но запись
        журнала — прежняя «ANSWER создан» без элементов — элементов в
        журнале нет; приём переводит задачу в другое состояние — не
        `in_dev`.
        """
        rng = seeded(self)
        items = random_elements(rng)
        line = f"{MARKER} {', '.join(items)}"
        out, failed = self.run_cmd(answer.cmd_answer, self.task,
                                   self.answer_file(
                                       f"{line}\n\nОснование: решение "
                                       f"Оператора ({self.seed}).\n"))
        self.assertFalse(failed, self.why(f"answer отказала:\n{out}"))
        found = self.answers()
        self.assertTrue(any(p.endswith("/ANSWER-1.md") for p in found),
                        self.why(f"ANSWER-1.md нет в ссылке: {found}\n{out}"))
        rel = next(p for p in found if p.endswith("/ANSWER-1.md"))
        self.assertIn(line, self.show(rel), self.why("в ANSWER нет мандата"))
        self.assertEqual("in_dev", self.state(), self.why("состояние сменилось"))
        journal = self.journal()
        self.assertTrue(
            any(all(item in entry for item in items) for entry in journal),
            self.why(f"нет записи, называющей элементы {items}: {journal}"))


class AnswerInDevWithoutMarkersTest(AnswerSandbox):

    def test_ac5_answer_in_dev_without_markers_keeps_old_refusal(self):
        """`answer` в `in_dev` с файлом без маркеров мандата — указание Оператора, не мандат.

        Текст файла — случайный ответ, в котором маркер мандата тестов
        процитирован в середине строки (не в начале — мандатом не
        считается). С задачи 01M443BPQEA9ZMJ3R50THNB1MF (требование 1,
        решение Оператора ANSWER-1 п.1) такой файл — указание: команда
        завершается без отказа, `ANSWER-1.md` с текстом файла в ссылке
        документов, состояние `in_dev`; журнал несёт запись «указание
        Оператора» и не несёт ни записи мандата, ни процитированного
        элемента.

        Ловит мутацию: маркер мандата тестов, встреченный где угодно в
        тексте (а не началом строки), принимается мандатом — в журнале
        появится запись «ANSWER создан (мандат …)» с процитированным
        элементом и не будет записи «указание Оператора»; файл без
        маркеров по-прежнему отказывается — ANSWER-1.md нет.
        """
        rng = seeded(self)
        element = f"tests/test_{word(rng)}.py"
        text = (f"Ответ {word(rng)}: см. «{MARKER} {element}» "
                f"в прошлой задаче ({self.seed}).\n")
        out, failed = self.run_cmd(answer.cmd_answer, self.task,
                                   self.answer_file(text))
        self.assertFalse(failed, self.why(f"answer отказала:\n{out}"))
        self.assertNotIn(OLD_REFUSAL, out, self.why(out))
        found = self.answers()
        self.assertTrue(any(p.endswith("/ANSWER-1.md") for p in found),
                        self.why(f"ANSWER-1.md нет в ссылке: {found}\n{out}"))
        rel = next(p for p in found if p.endswith("/ANSWER-1.md"))
        self.assertIn(text.strip(), self.show(rel), self.why("текст не тот"))
        self.assertEqual("in_dev", self.state(), self.why("состояние сменилось"))
        journal = self.journal()
        self.assertTrue(any("указание Оператора" in entry for entry in journal),
                        self.why(f"нет записи указания: {journal}"))
        self.assertFalse(any("мандат" in entry.split(" | ", 1)[0]
                             for entry in journal),
                         self.why(f"запись мандата в журнале: {journal}"))
        self.assertFalse(any(element in entry for entry in journal),
                         self.why(f"элемент {element} в журнале: {journal}"))


class AnswerInDevFromRoleEnvironmentTest(AnswerSandbox):

    def test_ac6_test_mandate_answer_from_role_environment_refuses(self):
        """`answer` в `in_dev` с мандатом тестов из окружения роли отказывает, ANSWER не создан.

        `runner.in_role_environment()` подменён на истину; файл несёт
        корректную строку «Ослабление тестов разрешено: …». Команда
        отказывает, в ссылке документов нет ANSWER, состояние `in_dev`.

        Ловит мутацию: приём мандата тестов в `in_dev` встроен отдельной
        ветвью мимо рубежа окружения роли (рубеж проверяется только для
        мандата зон) — роль сама выпишет себе ANSWER-1.md с мандатом.
        """
        rng = seeded(self)
        line = f"{MARKER} {', '.join(random_elements(rng))}"
        path = self.answer_file(f"{line}\n\nОснование: решение Оператора.\n")
        with mock.patch.object(runner, "in_role_environment",
                               return_value=True):
            out, failed = self.run_cmd(answer.cmd_answer, self.task, path)
        self.assertTrue(failed, self.why(f"answer не отказала:\n{out}"))
        self.assertEqual([], self.answers(), self.why(f"ANSWER создан:\n{out}"))
        self.assertEqual("in_dev", self.state(), self.why("состояние сменилось"))


if __name__ == "__main__":
    unittest.main()
