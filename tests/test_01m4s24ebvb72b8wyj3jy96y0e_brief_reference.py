"""Справочник ядра в брифе developer и в добавке test_author: место
компонента, опись, журнал, граница недоверенных данных, пометка `note`,
предел размера в байтах UTF-8 и алерты предела и предупреждения; reviewer,
analyst и spec_auditor справочника не получают; при `state == "off"` бриф
прежний.

Группа: долгоживущий

Красен до реализации: модуля `orchestrator.reference_cache` (К-3а) и константы `config.CORE_REFERENCE_MAX_BYTES` ещё нет, а `brief.developer_brief`/`brief.test_author_answer_component` справочник не запрашивают — подмена `reference_cache.get_reference` падает на импорте модуля, подмена предела — на отсутствии атрибута; методы AC-3 и AC-4 (вариант `off`) зелены и сегодня — держат, что реализация не обязана менять.

Песочница — `tests.sandbox.LightTransitionSandbox`: задача заведена
`catalog.cmd_new` (проект `artel`), артефакты задачи и правила системы
читаются с диска песочницы, git подменён целиком. Карта и `CLAUDE.md` —
`seed_developer_brief_fixtures`, SPEC задачи — файл на диске. Справочник
отдаёт подмена `reference_cache.get_reference` (интерфейс К-3а: поля
`text`, `note`, `state`); вариант `off` и нечитаемый `targets.yaml` (AC-4)
идут через настоящую функцию К-3а на `targets.yaml` песочницы. Настоящие
`targets.yaml` и `.artel/projects` пульта не читаются и не пишутся.

Тексты справочника, пометки, размеры и предел подменённой константы
выбираются случайно; зерно печатается и входит в текст провала.
"""
import random
import re
import unittest
from pathlib import Path
from typing import NamedTuple
from unittest import mock

from orchestrator import alerts, brief, config, review, store
from tests.sandbox import LightTransitionSandbox, seed_developer_brief_fixtures

GET_REFERENCE = "orchestrator.reference_cache.get_reference"
OVERSIZED_SOURCE = "brief.core_reference_oversized"
NEAR_LIMIT_SOURCE = "brief.core_reference_near_limit"
BOUNDARY_OPEN = "=== ГРАНИЦА НЕДОВЕРЕННЫХ ДАННЫХ"
BOUNDARY_CLOSE = "=== КОНЕЦ ГРАНИЦЫ НЕДОВЕРЕННЫХ ДАННЫХ"
COMPONENT_ACTION = "бриф: компонент"
REFERENCE_PHRASE = "справочник ядра"
SKIP_TAIL = (" — не включён, решение за Оператором (сузить настройку проекта "
             "или поднять предел)")
CACHE_TAIL = "knowledge/derived/core-reference.md"
HEX_RUN = re.compile(r"[0-9a-f]{40,}")
ROLES = ("developer", "test_author")

# Поле `core_reference` в конце записи артели `targets.yaml` песочницы
# (отступы записи `artel` — 4 и 6 пробелов).
CORE_REFERENCE_FIELD = (
    "    core_reference:\n"
    "      modules: [orchestrator/store.py, orchestrator/config.py]\n"
    "      constants_module: orchestrator/config.py\n"
    "      constants: [ROOT, TASKS]\n")


class Reference(NamedTuple):
    """Ответ `get_reference` в форме интерфейса К-3а."""
    text: str
    note: str
    state: str


class ReferenceBriefSandbox(LightTransitionSandbox):
    """Задача артели с SPEC на диске, подмена `get_reference` по запросу."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        seed_developer_brief_fixtures(self.root)
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            "# SPEC\n\nМаркер-текста-SPEC.\n", encoding="utf-8")
        self.conn = store.db()
        self.target = store.task_target(self.conn, self.TASK)
        self.label = f".artel/projects/{self.target}/{CACHE_TAIL}"
        self.calls: list = []
        self.answer = Reference("", "", "off")

    # ------------------------------------------------------------ сборка

    def fake_get_reference(self, conn, task_id, *, reason, sha=None):
        self.calls.append({"task_id": task_id, "reason": reason, "sha": sha})
        return self.answer

    def build(self, role: str, answer: Reference | None = None):
        """Бриф роли при подменённом `get_reference`: developer — весь
        бриф, test_author — результат `test_author_answer_component`."""
        if answer is not None:
            self.answer = answer
        with mock.patch(GET_REFERENCE, new=self.fake_get_reference):
            return self.build_plain(role)

    def build_plain(self, role: str):
        if role == "developer":
            return brief.developer_brief(self.conn, self.TASK)
        return brief.test_author_answer_component(self.conn, self.TASK)

    # ----------------------------------------------------------- фикстуры

    def reference_text(self, size: int, cyrillic: bool = False) -> str:
        """Текст справочника ровно `size` байт UTF-8 с уникальной первой
        строкой (по ней виден факт включения)."""
        head = f"# core-reference {self.rng.randrange(10 ** 12)}\n"
        fill = size - len(head.encode("utf-8"))
        self.assertGreaterEqual(fill, 0, self.msg("размер меньше шапки"))
        body = ("ж" * (fill // 2) + "x" * (fill % 2)) if cyrillic else "x" * fill
        text = head + body
        self.assertEqual(len(text.encode("utf-8")), size)
        return text

    def some_reference(self) -> str:
        lines = [f"# core-reference {self.rng.randrange(10 ** 12)}", ""]
        for _ in range(self.rng.randrange(3, 30)):
            lines.append(f"- `orchestrator/модуль_{self.rng.randrange(1000)}.py`"
                         f" — функция f{self.rng.randrange(10 ** 6)}(conn)")
        return "\n".join(lines) + "\n"

    def some_note(self) -> str:
        return (f"ПОМЕТКА-СПРАВОЧНИКА {self.rng.randrange(10 ** 9)}: не сверен, "
                f"built_at_sha={self.rng.randrange(10 ** 9):x}")

    def seed_return_and_answer(self) -> str:
        """Возврат test_author из эскалации с ANSWER-1.md; метка ANSWER."""
        for actor, state, detail in (
                ("operator", "tests_writing", "гейт SPEC пройден"),
                ("fsm", "escalated", f"test_author: вопрос {self.rng.randrange(999)}"),
                ("operator", "tests_writing", "эскалация разрешена, продолжаем")):
            store.journal(self.conn, self.TASK, actor, f"state -> {state}", detail)
        (self.tdir / "ANSWER-1.md").write_text(
            "---\ntask: x\ntype: answer\nauthor_role: operator\n"
            "status: ready\nschema_version: 2\n---\n\n# ANSWER-1\n\nОК.\n",
            encoding="utf-8")
        return f"{config.TASKS.name}/{self.TASK}/ANSWER-1.md"

    def add_reference_field(self) -> None:
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + CORE_REFERENCE_FIELD,
                                  encoding="utf-8")

    # -------------------------------------------------------------- чтение

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def last_step_id(self) -> int:
        rows = store.task_steps(self.conn, self.TASK)
        return rows[-1]["id"] if rows else 0

    def rows_since(self, since: int) -> list:
        return store.task_steps_since(self.conn, self.TASK, since)

    def reference_records(self, since: int) -> list:
        return [r["detail"] or "" for r in self.rows_since(since)
                if r["action"] == COMPONENT_ACTION
                and self.label in (r["detail"] or "")]

    def header_index(self, text: str, label: str) -> int:
        """Начало строки заголовка компонента `### <label>…`; -1 — нет."""
        match = re.search(rf"^### {re.escape(label)}", text, re.M)
        return match.start() if match else -1

    def header_line(self, text: str) -> str:
        i = self.header_index(text, self.label)
        return text[i:text.index("\n", i)] if i >= 0 else ""

    def segment_before(self, text: str, index: int) -> str:
        """Текст от конца последней строки закрывающей границы перед
        `index` до `index`."""
        close = text.rfind(BOUNDARY_CLOSE, 0, index)
        self.assertGreaterEqual(close, 0, self.msg("перед компонентом нет компонента"))
        return text[text.index("\n", close) + 1:index]

    def open_alerts_of(self, kind: str, source: str, target: str) -> list:
        return [r for r in alerts.open_alerts(self.conn, kind)
                if r["source"] == source and r["target"] == target]

    def assert_message_clean(self, row, *numbers: int) -> None:
        message = row["message"] or ""
        for number in numbers:
            self.assertNotIn(str(number), message,
                             self.msg(f"размер {number} в тексте алерта: {message}"))
        self.assertIsNone(HEX_RUN.search(message), self.msg(f"sha в алерте: {message}"))

    def assert_included(self, text: str, reference: str, since: int, case: str):
        self.assertIsNotNone(text, self.msg(f"{case}: добавки нет"))
        self.assertIn(reference, text, self.msg(f"{case}: справочник не включён"))
        self.assertGreaterEqual(self.header_index(text, self.label), 0,
                                self.msg(f"{case}: нет заголовка компонента"))
        self.assertTrue(self.reference_records(since),
                        self.msg(f"{case}: нет записи «{COMPONENT_ACTION}»"))

    def assert_excluded(self, text: str, reference: str, since: int, case: str):
        self.assertIsNotNone(text, self.msg(f"{case}: добавки нет"))
        head = reference.split("\n", 1)[0]
        self.assertNotIn(head, text, self.msg(f"{case}: справочник включён"))
        self.assertEqual(self.header_index(text, self.label), -1,
                         self.msg(f"{case}: заголовок компонента есть"))
        self.assertEqual(self.reference_records(since), [],
                         self.msg(f"{case}: запись «{COMPONENT_ACTION}» есть"))


class DeveloperPlacementTest(ReferenceBriefSandbox):

    def test_ac1_developer_brief_carries_reference_between_map_and_conventions(self):
        """Справочник `fresh` и `cached` — бриф developer.

        Компонент справочника (заголовок с путём кэша и текст) стоит после
        компонента проекции карты и до компонента `CLAUDE.md`; в журнале
        задачи — запись «бриф: компонент» developer с путём кэша; каждый
        вызов `get_reference` — по этой задаче, `reason="brief"`, `sha=None`.

        Ловит мутацию: компонент не добавлен в бриф developer, поставлен до
        проекции карты или после `CLAUDE.md`, собран мимо
        `_manifest_component` без записи журнала, либо `get_reference`
        вызван с `reason="merge"` или с `sha` головы ветки — заголовок
        окажется не на месте, записи не будет или вызов не совпадёт.
        """
        for state in ("fresh", "cached"):
            with self.subTest(state=state, зерно=self.seed):
                self.calls.clear()
                since = self.last_step_id()
                reference = self.some_reference()

                text = self.build("developer", Reference(reference, "", state))

                self.assert_included(text, reference, since, state)
                ref_at = self.header_index(text, self.label)
                map_at = self.header_index(text, brief.MAP_PROJECTION_LABEL)
                conv_at = self.header_index(text, brief.CONVENTIONS_REL)
                self.assertGreaterEqual(map_at, 0, self.msg("нет проекции карты"))
                self.assertGreaterEqual(conv_at, 0, self.msg("нет CLAUDE.md"))
                self.assertLess(map_at, ref_at, self.msg("справочник до карты"))
                self.assertLess(ref_at, conv_at, self.msg("справочник после CLAUDE.md"))
                self.assertLess(text.index(reference), conv_at,
                                self.msg("текст справочника после CLAUDE.md"))
                actors = {r["actor"] for r in self.rows_since(since)
                          if self.label in (r["detail"] or "")}
                self.assertEqual(actors, {"developer"}, self.msg(f"авторы: {actors}"))
                self.assertTrue(self.calls, self.msg("get_reference не вызван"))
                for call in self.calls:
                    self.assertEqual(call, {"task_id": self.TASK, "reason": "brief",
                                            "sha": None}, self.msg(f"вызов: {call}"))


class TestAuthorPlacementTest(ReferenceBriefSandbox):

    def test_ac2_test_author_component_carries_reference_after_return_and_answer(self):
        """Справочник `fresh`/`cached` у test_author: с возвратом и ANSWER и без.

        С причиной возврата и ANSWER-1.md результат
        `test_author_answer_component` несёт раздел причины, затем ANSWER,
        затем компонент справочника; без них — результат всё равно не
        `None` и несёт компонент. В журнале — запись «бриф: компонент»
        test_author с путём кэша; вызов `get_reference` — `reason="brief"`,
        `sha=None`.

        Ловит мутацию: добавка test_author возвращает `None`, когда нет
        причины и ANSWER, даже при справочнике; компонент вставлен до ANSWER
        или до причины возврата; запись журнала не пишется; вызов с
        `reason="merge"` или с `sha` — порядок, `None`, журнал или вызов
        разойдутся с ожиданием.
        """
        for case in ("без возврата", "с возвратом и ANSWER"):
            with self.subTest(случай=case, зерно=self.seed):
                self.calls.clear()
                answer_label = (self.seed_return_and_answer()
                                if case != "без возврата" else None)
                since = self.last_step_id()
                reference = self.some_reference()
                state = self.rng.choice(("fresh", "cached"))

                text = self.build("test_author", Reference(reference, "", state))

                self.assert_included(text, reference, since, case)
                ref_at = self.header_index(text, self.label)
                if answer_label:
                    reason_at = text.find(brief.RETURN_REASON_HEADER)
                    answer_at = self.header_index(text, answer_label)
                    self.assertGreaterEqual(reason_at, 0, self.msg("нет причины"))
                    self.assertGreaterEqual(answer_at, 0, self.msg("нет ANSWER"))
                    self.assertLess(reason_at, ref_at, self.msg("справочник до причины"))
                    self.assertLess(answer_at, ref_at, self.msg("справочник до ANSWER"))
                    self.assertLess(answer_at, text.index(reference),
                                    self.msg("текст справочника до ANSWER"))
                actors = {r["actor"] for r in self.rows_since(since)
                          if self.label in (r["detail"] or "")}
                self.assertEqual(actors, {"test_author"}, self.msg(f"авторы: {actors}"))
                self.assertTrue(self.calls, self.msg("get_reference не вызван"))
                for call in self.calls:
                    self.assertEqual(call, {"task_id": self.TASK, "reason": "brief",
                                            "sha": None}, self.msg(f"вызов: {call}"))


class OtherRolesTest(ReferenceBriefSandbox):

    def test_ac3_reviewer_analyst_and_spec_auditor_get_no_reference(self):
        """Поле `core_reference` в записи проекта, `get_reference` отдаёт
        `fresh` с непустой `note`.

        Ревью-пакет reviewer (`review.review_package`), бриф analyst
        (`brief.analyst_map_component`) и бриф spec_auditor
        (`brief.spec_auditor_brief`) не несут ни текста справочника, ни
        пометки, ни пути кэша, ни строки «справочник ядра»; записей журнала
        с путём кэша нет.

        Ловит мутацию: компонент справочника добавлен в общий помощник,
        который зовут и `spec_auditor_brief`/`analyst_map_component` (или в
        ревью-пакет), — их текст понесёт справочник или пометку.
        """
        self.add_reference_field()
        reference, note = self.some_reference(), self.some_note()
        self.answer = Reference(reference, note, "fresh")
        head = reference.split("\n", 1)[0]
        builders = (
            ("reviewer", lambda: review.review_package(
                self.conn, self.TASK, "Ревью-пакет", self.branch)["text"]),
            ("analyst", lambda: brief.analyst_map_component(self.conn, self.TASK)),
            ("spec_auditor", lambda: brief.spec_auditor_brief(self.conn, self.TASK)),
        )
        for role, build in builders:
            with self.subTest(роль=role, зерно=self.seed):
                since = self.last_step_id()
                with mock.patch(GET_REFERENCE, new=self.fake_get_reference):
                    text = build()

                for needle in (head, note, CACHE_TAIL, REFERENCE_PHRASE):
                    self.assertNotIn(needle, text, self.msg(f"{role}: «{needle}»"))
                self.assertEqual(self.reference_records(since), [],
                                 self.msg(f"{role}: запись журнала справочника"))


class OffStateTest(ReferenceBriefSandbox):

    def component_headers(self, text: str) -> list:
        return re.findall(r"^### (.+)$", text, re.M)

    def test_ac4_off_project_brief_matches_the_reference_free_composition(self):
        """Запись проекта без поля `core_reference`, читаемый `targets.yaml`,
        настоящий `get_reference`.

        Бриф developer: ни пути кэша, ни «справочник ядра»; заголовки
        компонентов — ровно SPEC, проекция карты и `CLAUDE.md`; новые записи
        журнала — ровно три «бриф: компонент» с этими метками. Добавка
        test_author без причины и ANSWER — `None` без новых записей; с
        причиной и ANSWER — ровно компоненты «Причина возврата» и ANSWER,
        без пути кэша и «справочник ядра».

        Ловит мутацию: при `state == "off"` бриф всё равно получает пустой
        компонент справочника, пометку или запись журнала (например,
        компонент добавляется без проверки `state`), либо test_author
        возвращает не `None` при `off` — число заголовков или записей
        превысит эталон.
        """
        spec_label = f"{config.TASKS.name}/{self.TASK}/SPEC.md"
        developer_expected = [spec_label, brief.MAP_PROJECTION_LABEL,
                              brief.CONVENTIONS_REL]

        since = self.last_step_id()
        text = self.build_plain("developer")
        headers = [h.split(" — ")[0] for h in self.component_headers(text)]
        self.assertEqual(headers, developer_expected, self.msg(f"заголовки: {headers}"))
        for needle in (CACHE_TAIL, REFERENCE_PHRASE):
            self.assertNotIn(needle, text, self.msg(f"developer: «{needle}»"))
        rows = self.rows_since(since)
        self.assertEqual([r["action"] for r in rows], [COMPONENT_ACTION] * 3,
                         self.msg(f"журнал: {[tuple(r) for r in rows]}"))
        self.assertEqual([(r["detail"] or "").split(": sha256=")[0] for r in rows],
                         developer_expected, self.msg("метки записей журнала"))

        since = self.last_step_id()
        self.assertIsNone(self.build_plain("test_author"),
                          self.msg("добавка test_author при off"))
        self.assertEqual(self.rows_since(since), [], self.msg("записи журнала при off"))

        answer_label = self.seed_return_and_answer()
        test_author_expected = [brief.RETURN_REASON_HEADER, answer_label]
        since = self.last_step_id()
        text = self.build_plain("test_author")
        self.assertIsNotNone(text, self.msg("добавка с ANSWER потеряна"))
        headers = self.component_headers(text)
        self.assertEqual(headers, test_author_expected, self.msg(f"заголовки: {headers}"))
        for needle in (CACHE_TAIL, REFERENCE_PHRASE):
            self.assertNotIn(needle, text, self.msg(f"test_author: «{needle}»"))
        rows = self.rows_since(since)
        self.assertEqual([r["action"] for r in rows], [COMPONENT_ACTION] * 2,
                         self.msg(f"журнал: {[tuple(r) for r in rows]}"))

    def test_ac4_unreadable_targets_keeps_test_author_component_with_note_and_alert(self):
        """`targets.yaml` песочницы нечитаем (на его месте каталог),
        настоящий `get_reference` К-3а под наблюдением.

        `test_author_answer_component` без причины и ANSWER строится без
        исключения, не `None` и несёт непустую `note`, отданную
        `get_reference`; после сборки открыт новый алерт по проекту задачи.

        Ловит мутацию: добавка test_author читает `targets.yaml` сама и
        падает (или выходит `sys.exit`) на нечитаемом файле, либо
        отбрасывает `note` при `state == "absent"` и возвращает `None` —
        будет исключение, `None` или текст без пометки.
        """
        from orchestrator import reference_cache
        real = reference_cache.get_reference
        seen = []

        def spy(conn, task_id, *, reason, sha=None):
            result = real(conn, task_id, reason=reason, sha=sha)
            seen.append(result)
            return result

        config.TARGETS.unlink()
        config.TARGETS.mkdir()
        before = {r["id"] for r in alerts.open_alerts(self.conn)}

        with mock.patch(GET_REFERENCE, new=spy):
            text = self.build_plain("test_author")

        self.assertTrue(seen, self.msg("get_reference не вызван"))
        note = seen[-1].note
        self.assertTrue(note, self.msg(f"К-3а не дала пометки: {seen[-1]!r}"))
        self.assertIsNotNone(text, self.msg("добавка test_author — None"))
        self.assertIn(note, text, self.msg("пометка потеряна"))
        new = [r for r in alerts.open_alerts(self.conn)
               if r["id"] not in before and r["target"] == self.target]
        self.assertTrue(new, self.msg("алерт по проекту задачи не поднят"))


class ManifestTest(ReferenceBriefSandbox):

    def test_ac5_component_label_boundary_manifest_and_journal_hash(self):
        """Справочник `fresh` в брифе developer и в добавке test_author.

        Заголовок компонента начинается с `### .artel/projects/<проект>/
        knowledge/derived/core-reference.md` (без домашнего и иного
        абсолютного каталога) и несёт размер в байтах UTF-8 и sha256 текста
        справочника; текст лежит между открывающей и закрывающей строками
        границы недоверенных данных, идущими после заголовка; запись журнала
        «бриф: компонент» с путём кэша несёт тот же sha256.

        Ловит мутацию: метка собрана из абсолютного `config.PROJECTS`, текст
        вставлен без `wrap_boundary`, размер посчитан в символах, либо хэш в
        описи или журнале посчитан по тексту вместе с пометкой — заголовок,
        граница или sha разойдутся.
        """
        import hashlib
        for role in ROLES:
            with self.subTest(роль=role, зерно=self.seed):
                since = self.last_step_id()
                reference = self.some_reference()
                size = len(reference.encode("utf-8"))
                sha = hashlib.sha256(reference.encode("utf-8")).hexdigest()

                text = self.build(role, Reference(reference, "", "fresh"))

                line = self.header_line(text)
                self.assertTrue(line.startswith(f"### {self.label}"),
                                self.msg(f"заголовок: {line!r}"))
                for absolute in (str(Path.home()), str(self.root)):
                    self.assertNotIn(absolute, line, self.msg(f"абсолютный путь: {line}"))
                self.assertIn(f"{size} байт", line, self.msg(f"размер: {line}"))
                self.assertIn(f"sha256={sha}", line, self.msg(f"sha256: {line}"))
                head_at = self.header_index(text, self.label)
                open_at = text.find(BOUNDARY_OPEN, head_at)
                text_at = text.find(reference, head_at)
                self.assertGreater(open_at, head_at, self.msg("нет открывающей границы"))
                self.assertGreater(text_at, open_at, self.msg("текст до границы"))
                self.assertNotIn("\n### ", text[head_at + 1:text_at],
                                 self.msg("между заголовком и текстом чужой компонент"))
                close_at = text.find(BOUNDARY_CLOSE, open_at)
                self.assertGreaterEqual(close_at, text_at + len(reference),
                                        self.msg("закрывающая граница внутри текста"))
                records = self.reference_records(since)
                self.assertEqual(len(records), 1, self.msg(f"записи: {records}"))
                self.assertIn(f"sha256={sha}", records[0], self.msg(records[0]))


class NoteTest(ReferenceBriefSandbox):

    def test_ac6_note_precedes_component_and_stays_out_of_the_hash(self):
        """`unverified` с пометкой, `fresh` с пометкой (кэш не записан) и
        `fresh`/`cached` с пустой `note` — у developer и test_author (с
        возвратом и ANSWER, чтобы перед справочником стоял компонент).

        Непустая `note` стоит между концом предыдущего компонента и
        заголовком справочника; sha256 описи и записи журнала равен sha256
        текста справочника без пометки; без пометки участок перед
        заголовком тот же, что с ней, за вычетом самой пометки. У developer
        при пустой `note` участок между проекцией карты и справочником
        пуст.

        Ловит мутацию: `note` приклеена к тексту компонента до хэширования,
        выводится после компонента, отбрасывается при `state == "fresh"`,
        либо при пустой `note` пишется пометка по `state` — sha, порядок
        или участок перед заголовком разойдутся.
        """
        import hashlib
        self.seed_return_and_answer()
        for role in ROLES:
            for state, with_note in (("unverified", True), ("fresh", True),
                                     ("fresh", False), ("cached", False)):
                with self.subTest(роль=role, state=state, пометка=with_note,
                                  зерно=self.seed):
                    reference = self.some_reference()
                    sha = hashlib.sha256(reference.encode("utf-8")).hexdigest()
                    note = self.some_note() if with_note else ""

                    bare = self.build(role, Reference(reference, "", state))
                    since = self.last_step_id()
                    text = self.build(role, Reference(reference, note, state))

                    head_at = self.header_index(text, self.label)
                    self.assertGreaterEqual(head_at, 0, self.msg("нет компонента"))
                    self.assertIn(f"sha256={sha}", self.header_line(text),
                                  self.msg("sha описи не от текста справочника"))
                    records = self.reference_records(since)
                    self.assertTrue(records, self.msg("нет записи журнала"))
                    self.assertIn(f"sha256={sha}", records[-1], self.msg(records[-1]))
                    segment = self.segment_before(text, head_at)
                    bare_segment = self.segment_before(
                        bare, self.header_index(bare, self.label))
                    if with_note:
                        self.assertIn(note, segment,
                                      self.msg(f"пометка не перед компонентом: {segment!r}"))
                        self.assertEqual(segment.replace(note, "", 1).strip(),
                                         bare_segment.strip(),
                                         self.msg("пометка — не единственная разница"))
                    else:
                        self.assertEqual(segment, bare_segment)
                        if role == "developer":
                            self.assertEqual(segment.strip(), "",
                                             self.msg(f"пометка без note: {segment!r}"))


class AbsentTest(ReferenceBriefSandbox):

    def test_ac7_absent_gives_only_the_note(self):
        """`state == "absent"`, текст пуст, `note` непуста — у developer и
        у test_author без причины и ANSWER.

        Бриф несёт `note`; заголовка компонента с путём кэша и записи
        «бриф: компонент» с ним нет; добавка test_author не `None`.

        Ловит мутацию: при `absent` в бриф идёт пустой компонент
        `_manifest_component` с пустым текстом (заголовок и запись журнала с
        путём кэша), либо test_author при одной пометке возвращает `None`.
        """
        for role in ROLES:
            with self.subTest(роль=role, зерно=self.seed):
                since = self.last_step_id()
                note = self.some_note()

                text = self.build(role, Reference("", note, "absent"))

                self.assertIsNotNone(text, self.msg(f"{role}: добавка None"))
                self.assertIn(note, text, self.msg(f"{role}: нет пометки"))
                self.assertEqual(self.header_index(text, self.label), -1,
                                 self.msg(f"{role}: пустой компонент"))
                self.assertEqual(self.reference_records(since), [],
                                 self.msg(f"{role}: запись журнала"))


class LimitTest(ReferenceBriefSandbox):

    def test_ac8_limit_is_config_bytes_inclusive(self):
        """Предел — `config.CORE_REFERENCE_MAX_BYTES` как есть и подменённый
        случайным значением; у developer и test_author.

        Справочник ровно в предел включается; предел + 1 байт — нет;
        кириллический справочник, у которого символов не больше предела, а
        байт больше, — нет.

        Ловит мутацию: размер считается `len(text)` в символах (кириллица
        пройдёт), предел — литерал 32768 (подмена не сдвинет границу),
        сравнение `>=` вместо `>` (ровно предел исключён), `>` заменён на
        проверку после включения (предел + 1 включён), либо предел
        применён только у developer.
        """
        default = config.CORE_REFERENCE_MAX_BYTES
        for limit in (default, self.rng.randrange(400, 4000)):
            with mock.patch.object(config, "CORE_REFERENCE_MAX_BYTES", limit):
                for role in ROLES:
                    cases = (("ровно предел", limit, False, True),
                             ("предел + 1", limit + 1, False, False),
                             ("кириллица сверх байт", limit + 2, True, False))
                    for case, size, cyrillic, included in cases:
                        with self.subTest(предел=limit, роль=role, случай=case,
                                          зерно=self.seed):
                            reference = self.reference_text(size, cyrillic)
                            if cyrillic:
                                self.assertLessEqual(len(reference), limit)
                            since = self.last_step_id()

                            text = self.build(role, Reference(reference, "", "fresh"))

                            if included:
                                self.assert_included(text, reference, since, case)
                            else:
                                self.assert_excluded(text, reference, since, case)

    def test_ac9_oversized_reference_is_replaced_by_a_line_and_an_alert(self):
        """Справочник крупнее предела, затем снова в пределе; у developer и
        test_author; открыт алерт того же источника по другому проекту.

        Крупнее: в тексте строка «справочник ядра: <размер> байт > <предел>
        — не включён, решение за Оператором (…)», ни текста, ни пути кэша, ни
        записи «бриф: компонент»; открыт `incident` источника
        `brief.core_reference_oversized` по проекту задачи без размеров и
        sha в тексте. В пределе — этот алерт снят. Алерт другого проекта
        остаётся открытым, нового по нему нет.

        Ловит мутацию: алерт не поднят, поднят по `None`/чужому проекту, не
        снимается при возврате в предел или снимается по одному источнику
        без проекта; строка пропуска называет файл кэша для чтения; текст
        включён целиком; запись журнала пишется до проверки предела; у
        test_author предел не применён.
        """
        limit = self.rng.randrange(400, 4000)
        other = f"proekt{self.rng.randrange(1000)}"
        alerts.raise_alert(self.conn, other, "incident", OVERSIZED_SOURCE,
                           "справочник ядра чужого проекта крупнее предела")
        other_ids = [r["id"] for r in self.open_alerts_of(
            "incident", OVERSIZED_SOURCE, other)]
        with mock.patch.object(config, "CORE_REFERENCE_MAX_BYTES", limit):
            for role in ROLES:
                with self.subTest(роль=role, зерно=self.seed):
                    size = limit + self.rng.randrange(1, 500)
                    reference = self.reference_text(size, self.rng.random() < 0.5)
                    since = self.last_step_id()

                    text = self.build(role, Reference(reference, "", "fresh"))

                    self.assert_excluded(text, reference, since, "крупнее")
                    line = f"{REFERENCE_PHRASE}: {size} байт > {limit}{SKIP_TAIL}"
                    self.assertIn(line, text, self.msg("нет строки пропуска"))
                    self.assertNotIn(CACHE_TAIL, text, self.msg("строка зовёт читать файл"))
                    mine = self.open_alerts_of("incident", OVERSIZED_SOURCE, self.target)
                    self.assertEqual(len(mine), 1, self.msg(f"алерт предела: {mine}"))
                    self.assert_message_clean(mine[0], size, limit)

                    small = self.reference_text(self.rng.randrange(100, limit // 2))
                    since = self.last_step_id()
                    text = self.build(role, Reference(small, "", "fresh"))

                    self.assert_included(text, small, since, "снова в пределе")
                    self.assertEqual(
                        self.open_alerts_of("incident", OVERSIZED_SOURCE, self.target),
                        [], self.msg("алерт предела не снят"))
                    self.assertEqual(
                        [r["id"] for r in self.open_alerts_of(
                            "incident", OVERSIZED_SOURCE, other)],
                        other_ids, self.msg("алерт другого проекта тронут"))

    def test_ac10_near_limit_warning_raises_above_ninety_percent_and_clears(self):
        """Предел подменён случайным кратным 10; у developer и test_author.

        Ровно 90% предела — предупреждения нет; 90% + 1 байт — открыт
        `warning` источника `brief.core_reference_near_limit` по проекту
        задачи без размеров и sha в тексте; снова 90% — снят; ровно предел —
        открыт; предел + 1 байт — открыт алерт предела, предупреждение
        снято.

        Ловит мутацию: порог считается `>=` (ровно 90% поднимает), не
        поднимается у test_author, не снимается при возврате к 90% или при
        подъёме алерта предела, либо текст несёт размер — состав открытых
        алертов разойдётся с ожиданием.
        """
        limit = 10 * self.rng.randrange(60, 400)
        edge = limit * 9 // 10
        steps = (("ровно 90%", edge, False, False),
                 ("90% + 1", edge + 1, True, False),
                 ("снова 90%", edge, False, False),
                 ("ровно предел", limit, True, False),
                 ("предел + 1", limit + 1, False, True))
        with mock.patch.object(config, "CORE_REFERENCE_MAX_BYTES", limit):
            for role in ROLES:
                for case, size, warned, oversized in steps:
                    with self.subTest(роль=role, случай=case, зерно=self.seed):
                        self.build(role, Reference(self.reference_text(size), "", "fresh"))

                        near = self.open_alerts_of("warning", NEAR_LIMIT_SOURCE,
                                                   self.target)
                        self.assertEqual(bool(near), warned,
                                         self.msg(f"{case}: предупреждение {near}"))
                        for row in near:
                            self.assert_message_clean(row, size, limit, edge)
                        over = self.open_alerts_of("incident", OVERSIZED_SOURCE,
                                                   self.target)
                        self.assertEqual(bool(over), oversized,
                                         self.msg(f"{case}: алерт предела {over}"))
                # Возврат в предел перед следующей ролью — алерт предела снят.
                self.build(role, Reference(self.reference_text(edge // 2), "", "fresh"))
                self.assertEqual(
                    self.open_alerts_of("incident", OVERSIZED_SOURCE, self.target), [],
                    self.msg("алерт предела не снят перед следующей ролью"))


if __name__ == "__main__":
    unittest.main()
