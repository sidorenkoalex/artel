"""Записи журнала команды `knowledge` среди прочих: постоянный автор и
действия, не совпадающие ни с чем, что ищут читатели журнала; предел записей
обращения на пути досыла очереди и вместе с командой; гейт выхода
`tests_writing` при записях этого автора после маркера отброшенных файлов.

Константы и перечни имён пакета `orchestrator` проверяются без песочницы;
предел — на связке «очередь `suite_lock` — досыл — БД» во временном корне
(`TmpRootTest`), вместе с командой — через диспетчер `artel.main()`; гейт —
на связке «журнал — `fsm.cmd_advance`» лёгкой песочницы переходов
(`LightTransitionSandbox`). Число файлов очереди, их порядок и вставки
записей «предел исчерпан» порождаются от зерна (печатается).

Группа: долгоживущий
Красен до реализации: модуля orchestrator.knowledge_cards с JOURNAL_ACTOR/ACCESS_ACTION/HINT_REFUSAL_ACTION ещё нет — его импорт внутри тестов падает ModuleNotFoundError, констант config.KNOWLEDGE_CARD_* (К-4а) нет — AttributeError.
"""
import contextlib
import importlib
import io
import os
import pkgutil
import random
import sys
import unittest
from unittest import mock

import orchestrator
from orchestrator import (artel, brief, checkpoint, config, fsm,
                          review, roles, store, suite_lock)
from orchestrator.advance_gates import spec_audit
from tests.sandbox import LightTransitionSandbox, TmpRootTest


def knowledge_cards_module():
    """Модуль карточек — импорт в тесте, чтобы файл собирался и до реализации."""
    return importlib.import_module("orchestrator.knowledge_cards")


EXHAUSTED_PREFIX = "предел журнала обращений исчерпан"
FORBIDDEN_STARTS = ("state -> ", "переход отклонён", "ANSWER создан",
                    "agent run")
ROLE_NAMES = ("analyst", "spec_auditor", "test_author", "developer",
              "reviewer")

SPEC_ONE_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка гейта отброшенных файлов (фикстура)

## Критерии приёмки

AC-1. Единственный критерий, покрытый тестом.
"""

PASSING_TEST = '''"""Зелёный с рождения: фикстура планки сценария гейта tests_writing.
Группа: разовый"""
import unittest


class PlankTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
'''


def new_seed() -> int:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed


def action_names() -> list:
    """(модуль, имя, значение) имён уровня модуля с `_ACTION` в имени во
    всех модулях пакета `orchestrator`."""
    found = []
    for info in pkgutil.walk_packages(orchestrator.__path__, "orchestrator."):
        module = importlib.import_module(info.name)
        for name, value in vars(module).items():
            if "_ACTION" in name:
                found.append((info.name, name, value))
    return found


class ConstantsTest(TmpRootTest):
    """AC-8: автор и действия записей команды."""

    def test_ac8_journal_actor_is_not_a_trusted_author_or_role(self):
        """Карта ролей песочницы (`roles.yaml` фикстуры) и особые авторы.

        Наблюдение: `JOURNAL_ACTOR` — непустая строка, не `operator`,
        `orchestrator`, `lease`, `fsm` и не имя роли карты.

        Ловит мутацию: `JOURNAL_ACTOR = "orchestrator"` (автор досыла) —
        запись обращения выглядит доверенной для `spec_audit`, тест видит
        совпадение с особым автором.
        """
        actor = knowledge_cards_module().JOURNAL_ACTOR
        self.assertIsInstance(actor, str)
        self.assertTrue(actor.strip())
        forbidden = {"operator", "orchestrator", "lease", "fsm"}
        forbidden |= set(roles.load())
        self.assertNotIn(actor, forbidden)

    def test_ac8_actions_distinct_from_every_known_action(self):
        """Обход всех модулей пакета `orchestrator`: имена с `_ACTION`.

        Наблюдение: `ACCESS_ACTION` равно «knowledge: обращение роли»,
        `HINT_REFUSAL_ACTION` — «knowledge: темы подсказки не прочитаны»;
        каждое не равно `VERDICT_TRANSITION_ACTION`/`FIXATION_ACTION`, не
        начинается ни с одного значения `*_ACTION_PREFIX`, не содержит
        `*_ACTION_MARKER`, не равно строковому значению прочих имён с
        `_ACTION` и элементам их кортежей/множеств (кроме самих двух
        констант), не начинается с «state -> », «переход отклонён»,
        «ANSWER создан», «agent run».

        Ловит мутацию: `ACCESS_ACTION` взято равным уже существующему
        действию (например `review.FIXATION_ACTION`) — читатель журнала
        принял бы запись обращения за свою.
        """
        own = (knowledge_cards_module().ACCESS_ACTION,
               knowledge_cards_module().HINT_REFUSAL_ACTION)
        self.assertEqual(own[0], "knowledge: обращение роли")
        self.assertEqual(own[1], "knowledge: темы подсказки не прочитаны")
        self.assertNotEqual(own[0], own[1])
        names = action_names()
        self.assertTrue(any(name.endswith("_ACTION_PREFIX")
                            for _m, name, _v in names))
        for action in own:
            self.assertNotEqual(action, review.VERDICT_TRANSITION_ACTION)
            self.assertNotEqual(action, review.FIXATION_ACTION)
            for start in FORBIDDEN_STARTS:
                self.assertFalse(action.startswith(start), action)
            for module, name, value in names:
                if any(value is c for c in own):
                    continue
                label = f"{module}.{name}"
                if isinstance(value, str):
                    if name.endswith("_ACTION_PREFIX"):
                        self.assertFalse(action.startswith(value), label)
                    if "_ACTION_MARKER" in name:
                        self.assertNotIn(value, action, label)
                    self.assertNotEqual(action, value, label)
                elif isinstance(value, (tuple, list, set, frozenset)):
                    for item in value:
                        if isinstance(item, str):
                            self.assertNotEqual(action, item, label)

    def test_ac8_last_access_record_changes_no_spec_audit_or_brief_output(self):
        """Журнал задачи с входом в аудит SPEC и вердиктом; затем последней
        дописана запись обращения, `detail` которой несёт текст, похожий на
        вердикт, sha и запись входа.

        Наблюдение: `spec_audit.entry`, `last_verdict`, `summary`,
        `return_count`, `status_suffix` и `brief.advance_refusal_history`
        для каждой роли — те же, что до записи.

        Ловит мутацию: `ACCESS_ACTION` совпадает с действием, которое читает
        `spec_audit` (`ENTRY_ACTION`/`VERDICT_ACTION`), — `entry` или
        `last_verdict` после записи обращения меняются.
        """
        seed = new_seed()
        rng = random.Random(seed)
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T301", "Задача", "spec_gate",
                          "task/t301-zadacha", config.DEFAULT_TARGET, 25.0)
        sha = "".join(rng.choice("0123456789abcdef") for _ in range(40))
        store.journal(conn, "T301", "fsm", "state -> spec_audit", "")
        store.journal(conn, "T301", "fsm", spec_audit.ENTRY_ACTION,
                      f"SPEC.md {sha} — сигналы: нет; разбор: краткий")
        store.journal(conn, "T301", "fsm", spec_audit.VERDICT_ACTION,
                      "вердикт pass; сигналы: нет")

        def outputs():
            row = store.get_task(conn, "T301")
            result = [spec_audit.entry(conn, "T301"),
                      spec_audit.last_verdict(conn, "T301"),
                      spec_audit.summary(conn, "T301"),
                      spec_audit.return_count(conn, "T301"),
                      spec_audit.status_suffix(conn, row)]
            for role in ROLE_NAMES:
                for state in ("spec_gate", "tests_writing", "in_dev"):
                    result.append(brief.advance_refusal_history(
                        conn, "T301", role, state))
            return result

        before = outputs()
        other = "".join(rng.choice("0123456789abcdef") for _ in range(40))
        store.journal(conn, "T301", knowledge_cards_module().JOURNAL_ACTOR,
                      knowledge_cards_module().ACCESS_ACTION,
                      f"SPEC.md {other} — сигналы: x; разбор: полный; "
                      f"вердикт fail; ANSWER-1.md")
        self.assertEqual(outputs(), before, f"зерно: {seed}")


class QueueLimitSandbox(TmpRootTest):
    """Временный корень пульта со схемой БД и задачей артели без поля
    `knowledge` (у команды — только «нет поля»/«не заведён»)."""

    def setUp(self):
        super().setUp()
        self.seed = new_seed()
        self.rng = random.Random(self.seed)
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T401", "Задача", "in_dev",
                          "task/t401-zadacha", config.DEFAULT_TARGET, 25.0)
        self.limit = config.KNOWLEDGE_CARD_JOURNAL_MAX_PER_TASK

    def access(self) -> list:
        return [r for r in store.task_steps(store.db(), "T401")
                if r["action"] == knowledge_cards_module().ACCESS_ACTION]

    def plain(self) -> list:
        return [r for r in self.access()
                if not (r["detail"] or "").startswith(EXHAUSTED_PREFIX)]

    def exhausted(self) -> list:
        return [r for r in self.access()
                if (r["detail"] or "").startswith(EXHAUSTED_PREFIX)]

    def seed_access(self, count: int) -> None:
        conn = store.db()
        for i in range(count):
            store.journal(conn, "T401", knowledge_cards_module().JOURNAL_ACTOR,
                          knowledge_cards_module().ACCESS_ACTION, f"посев {i}")

    def queue(self, plain: int, exhausted: int) -> None:
        """Файлы очереди: `plain` обращений и `exhausted` записей «предел
        исчерпан», записи «предел исчерпан» — в случайных местах."""
        kinds = ["plain"] * plain + ["exhausted"] * exhausted
        self.rng.shuffle(kinds)
        for i, kind in enumerate(kinds):
            detail = (f"{EXHAUSTED_PREFIX}: {i}" if kind == "exhausted"
                      else f"обращение из очереди {i}")
            self.assertTrue(suite_lock.defer_journal({
                "task_id": "T401", "action": knowledge_cards_module().ACCESS_ACTION,
                "detail": detail, "session_id": None, "at": store.now()}))

    def pending(self) -> list:
        return sorted(suite_lock.directory().rglob("*.json"))

    def run_knowledge(self, query: str) -> int:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": str(self.root)}):
            os.environ.pop(config.ARTEL_ROLE_ENV, None)
            os.environ.pop(config.ARTEL_TASK_ENV, None)
            with mock.patch.object(sys, "argv", ["artel.py", "knowledge",
                                                 "T401", query]), \
                    contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                try:
                    artel.main()
                except SystemExit as exc:
                    return 0 if exc.code is None else 1
        return 0


class DeliveryLimitTest(QueueLimitSandbox):
    """AC-9, AC-11: предел на пути досыла и вместе с командой."""

    def test_ac9_delivery_reaches_limit_plus_one_exhausted_record(self):
        """В журнале `MAX - 2` записей обращения; в очереди 3–6 обращений
        и 2–3 записи «предел исчерпан» вперемешку; досыл дважды.

        Наблюдение: записей обращения ровно `MAX`, записей «предел
        исчерпан» ровно одна, у всех автор `JOURNAL_ACTOR`; очередь пуста.

        Ловит мутацию: досыл пишет каждую запись «предел исчерпан» без
        проверки «уже писалась» — их в журнале две и больше.
        """
        self.seed_access(self.limit - 2)
        self.queue(self.rng.randint(3, 6), self.rng.randint(2, 3))
        suite_lock.deliver_journal()
        suite_lock.deliver_journal()
        self.assertEqual(len(self.plain()), self.limit, f"зерно: {self.seed}")
        self.assertEqual(len(self.exhausted()), 1, f"зерно: {self.seed}")
        for row in self.access():
            self.assertEqual(row["actor"], knowledge_cards_module().JOURNAL_ACTOR)
        self.assertEqual(self.pending(), [], f"зерно: {self.seed}")

    def test_ac11_many_queued_files_respect_limit(self):
        """Очередь одной задачи — `max(300, MAX + 100)` обращений и 0–3
        записи «предел исчерпан» в случайных местах; журнал пуст.

        Наблюдение: после досыла записей обращения не больше `MAX` (без
        записи «предел исчерпан»), таких записей не больше одной; файлов
        очереди не осталось.

        Ловит мутацию: предел проверяется только командой, досыл пишет всё —
        в журнале 300 записей обращения.
        """
        self.queue(max(300, self.limit + 100), self.rng.randint(0, 3))
        suite_lock.deliver_journal()
        self.assertLessEqual(len(self.plain()), self.limit,
                             f"зерно: {self.seed}")
        self.assertLessEqual(len(self.exhausted()), 1, f"зерно: {self.seed}")
        self.assertEqual(self.pending(), [], f"зерно: {self.seed}")

    def test_ac11_command_and_delivery_together_respect_limit(self):
        """`MAX - 3` записи посеяны, команда пишет ещё одну; в очереди
        10–20 обращений и запись «предел исчерпан»; досыл; команда ещё раз.

        Наблюдение: записей обращения не больше `MAX`, записей «предел
        исчерпан» не больше одной — и после досыла, и после второго вызова
        команды; очередь пуста.

        Ловит мутацию: досыл считает к пределу и запись «предел исчерпан»
        либо не видит записей команды — итог больше `MAX` или две записи
        «предел исчерпан».
        """
        self.seed_access(self.limit - 3)
        self.run_knowledge("pkg/a.py")
        self.assertEqual(len(self.plain()), self.limit - 2,
                         f"зерно: {self.seed}")
        self.queue(self.rng.randint(10, 20), 1)
        suite_lock.deliver_journal()
        self.assertLessEqual(len(self.plain()), self.limit)
        self.assertLessEqual(len(self.exhausted()), 1)
        self.assertEqual(self.pending(), [], f"зерно: {self.seed}")
        self.run_knowledge("pkg/b.py")
        self.assertLessEqual(len(self.plain()), self.limit)
        self.assertEqual(len(self.exhausted()), 1, f"зерно: {self.seed}")


class TestsWritingGateTest(LightTransitionSandbox):
    """AC-12: записи `JOURNAL_ACTOR` и гейт отброшенных файлов планки."""

    def enter_with_stray_files(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(SPEC_ONE_AC.format(task=self.TASK),
                                           encoding="utf-8")
        self.set_state("tests_writing")
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_ac.py").write_text(PASSING_TEST, encoding="utf-8")
        store.journal(store.db(), self.TASK, "orchestrator",
                      checkpoint.STRAY_ACCEPTANCE_FILES_ACTION,
                      f"{checkpoint.STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX}"
                      f"fixtures.json")

    def assert_refused(self, out: str) -> None:
        self.assertEqual(self.state(), "tests_writing", out)
        self.assertIn("планка ссылается на отброшенные файлы", out)
        self.assertIn("fixtures.json", out)

    def test_ac12_delivered_access_record_does_not_lift_refusal(self):
        """После маркера отброшенных файлов обращение досылается из очереди
        (`defer_journal` + `deliver_journal`) — последняя запись визита
        автора `JOURNAL_ACTOR` с действием `ACCESS_ACTION`.

        Наблюдение: `advance` отказывает «планка ссылается на отброшенные
        файлы», задача остаётся в `tests_writing`.

        Ловит мутацию: гейт не исключает записи `JOURNAL_ACTOR` — поздняя
        запись обращения заслоняет маркер, переход уходит в `in_dev`.
        """
        self.enter_with_stray_files()
        self.assertTrue(suite_lock.defer_journal({
            "task_id": self.TASK, "action": knowledge_cards_module().ACCESS_ACTION,
            "detail": "обращение", "session_id": None, "at": store.now()}))
        suite_lock.deliver_journal()
        last = store.task_steps(store.db(), self.TASK)[-1]
        self.assertEqual(last["actor"], knowledge_cards_module().JOURNAL_ACTOR)
        self.assert_refused(self.capture(fsm.cmd_advance, self.TASK))

    def test_ac12_hint_refusal_record_does_not_lift_refusal(self):
        """После маркера — запись `JOURNAL_ACTOR` + `HINT_REFUSAL_ACTION`.

        Наблюдение: `advance` отказывает по отброшенным файлам.

        Ловит мутацию: исключение пары «автор + действие» знает только
        `ACCESS_ACTION` — запись отказа подсказки заслоняет маркер, переход
        уходит в `in_dev`.
        """
        self.enter_with_stray_files()
        store.journal(store.db(), self.TASK, knowledge_cards_module().JOURNAL_ACTOR,
                      knowledge_cards_module().HINT_REFUSAL_ACTION, "отказ чтения вида")
        self.assert_refused(self.capture(fsm.cmd_advance, self.TASK))

    def test_ac12_journal_actor_with_stray_action_still_refuses(self):
        """Маркер отброшенных файлов записан автором `JOURNAL_ACTOR` и стоит
        последним (до него — запись обращения того же автора).

        Наблюдение: `advance` отказывает по отброшенным файлам.

        Ловит мутацию: исключение только по автору `JOURNAL_ACTOR` без
        действия — маркер скрыт от гейта, переход уходит в `in_dev`.
        """
        self.enter_with_stray_files()
        conn = store.db()
        store.journal(conn, self.TASK, "operator", "заметка Оператора",
                      "маркер снят")
        store.journal(conn, self.TASK, knowledge_cards_module().JOURNAL_ACTOR,
                      knowledge_cards_module().ACCESS_ACTION, "обращение")
        store.journal(conn, self.TASK, knowledge_cards_module().JOURNAL_ACTOR,
                      checkpoint.STRAY_ACCEPTANCE_FILES_ACTION,
                      f"{checkpoint.STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX}"
                      f"fixtures.json")
        self.assert_refused(self.capture(fsm.cmd_advance, self.TASK))


if __name__ == "__main__":
    unittest.main()
