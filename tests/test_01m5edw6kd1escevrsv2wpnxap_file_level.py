"""Ошибка уровня файла в отчёте компонента, засчитывание «нового модуля» гейтом честного FAIL_TO_PASS, строка пакета ревьювера и переносы приёмок G2б-2.

Группа: долгоживущий
Красен до реализации: у `CaseResult` нет полей `file_level`/`detail` — AC-1, AC-2, AC-5 падают на атрибуте или конструкторе; запись `file_level` Vitest не даёт находки уровня файла (AC-4 Vitest, AC-10); гейт честного FAIL_TO_PASS на ошибку уровня файла нового модуля из зон даёт находку, не пишет записи «ошибка уровня файла засчитана красным», не подавляет «теста нет в отчёте» и не проверяет отсутствие P в git (AC-6, AC-7, AC-11, AC-12, AC-13 — файл не засчитан, задача не уходит в `in_dev`); пакет ревьювера без строки засчитывания (AC-14); подсказка отказа FAIL_TO_PASS печатается дважды (AC-15). Зелёны и на базе ветки методы прежнего поведения: прежние поля разбора и вердикт (AC-3, модульный), граница `test_profile` (AC-3 сценарий, AC-14 вне границы), находки JUnit при несопоставленной записи и нарушенных (а)/(б) (AC-4 JUnit, AC-8, AC-9), файл Vitest без записей (AC-4), перенос 10 и подсказки прочих отказов (AC-15).

Модульные методы (разбор отчётов, вердикт, `outcome_integrity.compare`) —
без песочницы, на фикстурах JUnit XML и JSON отчётчика пульта со
случайными путями и именами.

Сценарные методы держат связку «запись проекта — профиль — опора SPEC —
журнал — FSM — пакет ревьювера» и идут на стенде гейта честного
FAIL_TO_PASS задачи G2б-2
(`tests.test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.FailToPassSandbox`):
настоящий git, учебный проект с одним компонентом `junit-xml` на
поддельном `pytest` либо `pult-vitest` без Node, раннеры — шпион
`subprocess.Popen`. Сверх стенда шпион пишет в отчёт запись сбора pytest
(`classname=""`, `name` — точечный путь файла от `workdir`, `message=
"collection failure"`, трассировка в тексте элемента) и запись уровня
файла отчётчика Vitest (`file_level: true`, `error_name`,
`error_message`) для файлов сценария. SPEC фикстуры несёт `zones:` во
фронтматтере; опора — настоящий переход гейта SPEC.

«Git не ответил при проверке отсутствия P» (AC-11) — шпион отвечает кодом
128 на вызов `git`, сделанный после прогона гейта (второй запуск раннера)
из кода модулей зон задачи (`advance_gates.tests_writing`,
`reporters.outcome`, `advance_gates.outcome_integrity`) вне кадров раннера
`orchestrator.acceptance`: проверка отсутствия P судит запись `file_level`
прогона, она идёт после него. Тот же шпион без условия «после прогона» —
сбой git проверки долгоживущих файлов (AC-15, отказ `:414`).

Имена проектов, файлов, модулей, номера критериев и тексты — из `random`;
зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен): поля
`CaseResult`, запись уровня файла в `parse_vitest`/`parse_junit`, исключение
записей `file_level` в `compare`, засчитывание в гейте (полный точечный
путь, зоны опорного SPEC, дерево `diff_base`/HEAD, итоговая строка
Python, три случая спецификатора Vitest), подавление находок по
засчитанным критериям, запись журнала, строка пакета и печать подсказки
отказа один раз — все методы файла зелёные.
"""
import contextlib
import io
import json
import random
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from xml.sax.saxutils import escape, quoteattr

from orchestrator import (answer, checkpoint, config, project_profile, review,
                          store, workspace)
from orchestrator.advance_gates import outcome_integrity
from orchestrator.reporters import outcome
from tests.test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass import (
    APPROVED_DETAIL, BRANCH_ACTION, F2P_ACTION, FILE_LEVEL, NO_RECORD,
    PLAN_READY, PLANK_DIR, PREPARE_ACTION, TASKS_DIR, FailToPassSandbox,
    spec_text, ulid)

COUNTED_ACTION = "ошибка уровня файла засчитана красным"
COUNTED_DETAIL = "новый модуль {path} (файл {name})"
FILE_LEVEL_NAME = "<ошибка уровня файла>"
COLLECTION = "collection failure"
TEST_GROUPS_ACTION = "переход отклонён: группы приёмочных тестов"
LONG_LIVED_ACTION = "переход отклонён: долгоживущие файлы tests/"
LONG_LIVED_GIT_ACTION = ("переход отклонён: долгоживущие файлы tests/ — git не "
                         "ответил")
NEXT = "дальше:"
SECTION = "Изменённые утверждения тестов"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
GIT_ZONE_MODULES = ("orchestrator.advance_gates.tests_writing",
                    "orchestrator.reporters.outcome",
                    "orchestrator.advance_gates.outcome_integrity")
RUNNER_MODULE = "orchestrator.acceptance"
# Метка граничных маркеров пакета — своя у каждой сборки.
BOUNDARY_ID = re.compile(r"[0-9a-f]{32}")
VITEST_FORMS = {
    "resolve": 'Failed to resolve import "{spec}" from "{file}". Does the '
               'file exist?',
    "cannot": "Cannot find module '{spec}'",
}
MATRIX_HEADERS = ("Что меняется", "Какое свойство сейчас держит",
                  "Остаётся ли свойство после изменения",
                  "Чем покрыто после", "Решение")


def parts_of(detail: str) -> list:
    """Находки детали отказа по отдельности: разделители `; ` и строки."""
    return [p.strip() for p in re.split(r"; |\n", detail) if p.strip()]


# ------------------------------------------------------------ модульные

class SeededTest(unittest.TestCase):
    """Модульные методы без песочницы: зерно и случайные слова."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def write(self, name: str, text: str) -> Path:
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return path

    @staticmethod
    def root_path(workdir: str, rel: str) -> str:
        """Путь от корня репозитория по пути от `workdir` (прежнее правило
        идентификатора)."""
        joined = f"{workdir}/{rel}" if workdir else rel
        return str(Path(joined)) if joined else "."

    def legacy(self, record) -> tuple:
        return (record.id, record.outcome, record.failure, record.skip_reason,
                record.time, record.mode, record.fails, record.retries)

    def long_trace(self, module: str) -> str:
        """Трассировка сбора длиннее 2000 символов, итог —
        `ModuleNotFoundError`."""
        lines = [f"ImportError while importing test module '/{self.word()}/x.py'.",
                 "Traceback:"]
        while sum(len(line) + 1 for line in lines) < 2600:
            lines.append(f"{self.word()}/{self.word()}.py:{self.rng.randint(1, 99)}: "
                         f"in <module> & {self.word(12)}")
        lines.append(f"E   ModuleNotFoundError: No module named '{module}'")
        return "\n".join(lines)


class Ac1VitestFileLevelRecordTest(SeededTest):

    def test_ac1_case_result_fields_and_parse_vitest_file_level(self):
        """Запись уровня файла отчётчика Vitest — `CaseResult` с исходом `error`, `file_level`, видом и сообщением; поля по умолчанию; итог прогона красный.

        Сценарий: `CaseResult` из двух позиционных полей несёт
        `file_level=False` и `detail=""`. JSON отчётчика пульта: запись
        `{file, name: "<ошибка уровня файла>", state: "fail", file_level:
        true, error_name, error_message}` (имена и тексты случайны) и
        обычная запись `pass`. `parse_vitest` даёт для первой исход
        `error`, `file_level=True`, `failure` — `error_name`, `detail` —
        `error_message`, у второй `file_level=False`; вердикт по этим
        записям при ненулевом коде возврата — «красный».

        Ловит мутацию: `parse_vitest` не переносит `file_level`/
        `error_message` в запись (поле ложно, `detail` пуст); `failure`
        берётся из сообщения, а не из имени ошибки; запись с `file_level`
        отбрасывается разбором — вердикт «неизвестно» по коду возврата.
        """
        plain = outcome.CaseResult(f"c:{self.word()}.js::t", outcome.PASSED)
        self.assertIs(plain.file_level, False, self.note(str(plain)))
        self.assertEqual(plain.detail, "", self.note(str(plain)))
        workdir = self.rng.choice(["", self.word()])
        rel = f"src/{self.word()}.test.jsx"
        error_name = self.rng.choice(["Error", "SyntaxError", "TypeError"])
        message = (f"Failed to resolve import \"../{self.word()}\" from "
                   f"\"{rel}\". {self.word()} {self.word()}")
        items = [{"file": rel, "name": FILE_LEVEL_NAME, "state": "fail",
                  "file_level": True, "error_name": error_name,
                  "error_message": message},
                 {"file": f"src/{self.word()}.test.jsx",
                  "name": f"AC-1: {self.word()}", "state": "pass",
                  "mode": "run", "duration_ms": 4}]
        report = self.write("report.json", json.dumps({"tests": items}))
        comp = f"c{self.word()}"
        records, reason = outcome.parse_vitest(report, comp, workdir,
                                               ("AssertionError",))
        self.assertIsNotNone(records, self.note(reason))
        self.assertEqual(len(records), 2, self.note(str(records)))
        first, second = records
        context = self.note(str(records))
        self.assertEqual(first.outcome, outcome.ERROR, context)
        self.assertIs(first.file_level, True, context)
        self.assertEqual(first.failure, error_name, context)
        self.assertEqual(first.detail, message, context)
        self.assertIs(second.file_level, False, context)
        state, why = outcome.verdict(records, 1)
        self.assertEqual(state, outcome.RED, self.note(why))


class Ac2JunitCollectionRecordTest(SeededTest):

    def test_ac2_parse_junit_collection_record_file_level_and_detail(self):
        """Запись сбора pytest в xunit2 — `file_level=True`, `detail` — первые 2000 символов текста элемента; `id`, `outcome`, `failure` прежние.

        Сценарий: отчёт с записью `<testcase classname="" name="<точечный
        путь>">` и `<error message="collection failure">` с трассировкой
        длиннее 2000 символов (случайные строки, `&` и `<module>` в
        тексте). `parse_junit` даёт запись: `file_level=True`, `detail`
        равен `text[:2000]`, `id` — идентификатор компонента с путём
        `workdir` и полным именем — точечным путём, исход `error`, вид
        «collection failure».

        Ловит мутацию: `detail` берётся из атрибута `message`, а не из
        текста элемента; текст не обрезан до 2000 (или обрезан до первой
        строки); признак `file_level` ставится по исходу `error`, но
        запись сбора не распознана по `message` — признак ложен.
        """
        workdir = self.rng.choice(["", self.word()])
        dotted = f"{self.word()}.{self.word()}.test_{self.word()}"
        trace = self.long_trace(f"{self.word()}.{self.word()}")
        xml = ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
               '<testsuite name="pytest">'
               f'<testcase classname="" name="{dotted}" time="0.000">'
               f'<error message="{COLLECTION}">{escape(trace)}</error>'
               '</testcase></testsuite></testsuites>')
        report = self.write("report.xml", xml)
        comp = f"c{self.word()}"
        records, reason = outcome.parse_junit(report, comp, workdir, self.tmp)
        self.assertIsNotNone(records, self.note(reason))
        self.assertEqual(len(records), 1, self.note(str(records)))
        record = records[0]
        context = self.note(str(record))
        self.assertIs(record.file_level, True, context)
        self.assertEqual(record.detail, trace[:2000], context)
        self.assertEqual(record.id, project_profile.test_id(
            comp, self.root_path(workdir, ""), dotted), context)
        self.assertEqual(record.outcome, outcome.ERROR, context)
        self.assertEqual(record.failure, COLLECTION, context)


class Ac3LegacyParseTest(SeededTest):

    def test_ac3_legacy_fields_and_verdict_unchanged(self):
        """Прежние поля записей `parse_junit`/`parse_vitest` и вердикт — те же, что до задачи.

        Сценарий: JUnit — тесты `passed`, `failure` (assert), `error`
        (`TypeError`), `skipped` с причиной и запись сбора; JSON отчётчика
        пульта — `pass`, `fail` с именем из `failure_errors` и вне его,
        `skip`, `todo`, `it.fails` с повтором, таймаут, падение хука.
        Поля `id`, `outcome`, `failure`, `skip_reason`, `time`, `mode`,
        `fails`, `retries` каждой записи и `verdict` при коде 1 совпадают
        с ожидаемыми по прежнему правилу (у записи сбора — путь `workdir`,
        вид «collection failure»).

        Ловит мутацию: новые поля вставлены в `CaseResult` перед прежними —
        позиционное построение сдвигает `time`/`mode`; вид падения записи
        сбора заменён текстом трассировки; исход записи сбора стал
        `failed`; запись уровня файла Vitest сменила вид `failure` на
        сообщение у прочих ошибок; вердикт стал судить по `file_level`.
        """
        workdir = self.rng.choice(["", self.word()])
        comp = f"c{self.word()}"
        rel = f"{self.word()}/test_{self.word()}.py"
        module = rel[:-3].replace("/", ".")
        klass = f"Test{self.word().capitalize()}"
        names = [f"test_{self.word()}" for _ in range(4)]
        dotted = f"{self.word()}.test_{self.word()}"
        reason_text = f"причина {self.word()}"
        xml = ('<?xml version="1.0" encoding="utf-8"?><testsuites>'
               '<testsuite name="pytest">'
               f'<testcase classname="{module}.{klass}" name="{names[0]}" '
               f'file="{rel}" time="0.5"/>'
               f'<testcase classname="{module}.{klass}" name="{names[1]}" '
               f'file="{rel}" time="0.25"><failure message="assert 1 == 2">'
               f'AssertionError: assert 1 == 2</failure></testcase>'
               f'<testcase classname="{module}.{klass}" name="{names[2]}" '
               f'file="{rel}" time="0.125"><error type="TypeError" '
               f'message="boom {self.word()}">trace</error></testcase>'
               f'<testcase classname="{module}.{klass}" name="{names[3]}" '
               f'file="{rel}" time="0"><skipped message="{reason_text}"/>'
               f'</testcase>'
               f'<testcase classname="" name="{dotted}" time="0.000">'
               f'<error message="{COLLECTION}">E   ModuleNotFoundError: No '
               f"module named '{self.word()}'</error></testcase>"
               '</testsuite></testsuites>')
        records, reason = outcome.parse_junit(self.write("r.xml", xml), comp,
                                              workdir, self.tmp)
        self.assertIsNotNone(records, self.note(reason))
        path = self.root_path(workdir, rel)

        def jid(name):
            return project_profile.test_id(comp, path, f"{klass}::{name}")

        error_failure = re.search(r'message="(boom \w+)"', xml).group(1)
        expected = [
            (jid(names[0]), outcome.PASSED, "", "", 0.5, "", False, 0),
            (jid(names[1]), outcome.FAILED, "assert 1 == 2", "", 0.25, "",
             False, 0),
            (jid(names[2]), outcome.ERROR, f"TypeError: {error_failure}", "",
             0.125, "", False, 0),
            (jid(names[3]), outcome.SKIPPED, "", reason_text, 0.0, "", False, 0),
            (project_profile.test_id(comp, self.root_path(workdir, ""), dotted),
             outcome.ERROR, COLLECTION, "", 0.0, "", False, 0)]
        self.assertEqual([self.legacy(r) for r in records], expected,
                         self.note(str(records)))
        self.assertEqual(outcome.verdict(records, 1), (
            outcome.RED, f"{expected[1][0]} — {outcome.FAILED}: assert 1 == 2"),
            self.note(str(records)))

        vrel = f"src/{self.word()}.test.js"
        vnames = [f"AC-{i}: {self.word()}" for i in range(1, 9)]
        items = [
            {"name": vnames[0], "state": "pass", "duration_ms": 12},
            {"name": vnames[1], "state": "fail", "error_name": "AssertionError",
             "duration_ms": 30},
            {"name": vnames[2], "state": "fail", "error_name": "TypeError"},
            {"name": vnames[3], "state": "skip", "mode": "skip"},
            {"name": vnames[4], "state": "todo", "mode": "todo"},
            {"name": vnames[5], "state": "fail", "error_name": "AssertionError",
             "fails": True, "retry_count": 2},
            {"name": vnames[6], "state": "fail", "error_name": "Error",
             "timeout": True},
            {"name": vnames[7], "state": "fail", "error_name": "Error",
             "hook": "beforeEach"}]
        for item in items:
            item["file"] = vrel
        vrecords, vreason = outcome.parse_vitest(
            self.write("r.json", json.dumps({"tests": items})), comp, workdir,
            ("AssertionError",))
        self.assertIsNotNone(vrecords, self.note(vreason))
        vpath = self.root_path(workdir, vrel)

        def vid(i):
            return project_profile.test_id(comp, vpath, vnames[i])

        vexpected = [
            (vid(0), outcome.PASSED, "", "", 0.012, "run", False, 0),
            (vid(1), outcome.FAILED, "AssertionError", "", 0.03, "run", False, 0),
            (vid(2), outcome.ERROR, "TypeError", "", 0.0, "run", False, 0),
            (vid(3), outcome.SKIPPED, "", "skip (mode: skip)", 0.0, "skip",
             False, 0),
            (vid(4), outcome.SKIPPED, "", "todo (mode: todo)", 0.0, "todo",
             False, 0),
            (vid(5), outcome.FAILED, "AssertionError", "", 0.0, "run", True, 2),
            (vid(6), outcome.ERROR, "timeout: Error", "", 0.0, "run", False, 0),
            (vid(7), outcome.ERROR, "падение хука beforeEach: Error", "", 0.0,
             "run", False, 0)]
        self.assertEqual([self.legacy(r) for r in vrecords], vexpected,
                         self.note(str(vrecords)))
        self.assertEqual(outcome.verdict(vrecords, 1), (
            outcome.RED, f"{vid(1)} — {outcome.FAILED}: AssertionError"),
            self.note(str(vrecords)))


class Ac5CompareTest(SeededTest):

    def test_ac5_file_level_record_is_not_a_test_id_in_compare(self):
        """Запись `file_level` базы, исчезнувшая на ветке, — не находка «исчезнувший тест»; обычная исчезнувшая запись — находка.

        Сценарий: база — запись сбора (`error`, `file_level=True`, случайный
        `detail`) и обычный тест `passed`; ветка — пусто (ошибка исправлена,
        тест удалён). `compare` даёт находку по идентификатору обычного
        теста и ни одной — по идентификатору записи `file_level`.

        Ловит мутацию: `compare` строит карту базы из всех записей, без
        исключения `file_level`, — находка «исчез» по записи ошибки
        уровня файла; исключение сделано по исходу `error` — исчезновение
        обычного теста с ошибкой тоже пропало (здесь — по `passed`).
        """
        comp = f"c{self.word()}"
        level_id = project_profile.test_id(comp, ".", f"{self.word()}.test_x")
        plain_id = project_profile.test_id(comp, f"{self.word()}.py",
                                           f"test_{self.word()}")
        base = [outcome.CaseResult(level_id, outcome.ERROR, COLLECTION,
                                   file_level=True,
                                   detail=f"E   ModuleNotFoundError: {self.word()}"),
                outcome.CaseResult(plain_id, outcome.PASSED)]
        found = outcome_integrity.compare(base, [])
        ids = [f.id for f in found]
        self.assertIn(plain_id, ids, self.note(str(found)))
        self.assertNotIn(level_id, ids, self.note(str(found)))


# ------------------------------------------------------------ сценарные

class FileLevelSandbox(FailToPassSandbox):
    """Стенд G2б-2 плюс записи уровня файла в отчётах шпиона, SPEC с
    `zones:` и сбой git проверки отсутствия P."""

    def setUp(self):
        # Шпион стенда ставится в его `setUp` и сразу зовётся.
        # Путь файла от рабочего каталога прогона -> текст записи сбора.
        self.collection: dict = {}
        # (точечное имя, текст) — записи сбора без файла сценария.
        self.stray_collection: list = []
        # Путь файла от рабочего каталога прогона -> (имя, сообщение).
        self.vitest_level: dict = {}
        self.git_break = None  # None | "после прогона" | "всегда"
        self.git_armed = False
        self.git_failed: list = []
        super().setUp()

    # --- шпион ----------------------------------------------------------

    def record_run(self, kind: str, parts: list, cwd: Path) -> dict:
        run = super().record_run(kind, parts, cwd)
        if run["index"] >= 1:
            self.git_armed = True
        return run

    def from_zone_code(self) -> bool:
        names = []
        frame = sys._getframe(1)
        while frame is not None:
            names.append(frame.f_globals.get("__name__", ""))
            frame = frame.f_back
        return (any(n in GIT_ZONE_MODULES for n in names)
                and RUNNER_MODULE not in names)

    def spy_popen(self, argv, *args, **kwargs):
        if (isinstance(argv, (list, tuple)) and argv and str(argv[0]) == "git"
                and self.git_break is not None
                and (self.git_break == "всегда" or self.git_armed)
                and self.from_zone_code()):
            self.git_failed.append([str(a) for a in argv])
            return self.answer(128, "", args, kwargs)
        return super().spy_popen(argv, *args, **kwargs)

    def junit_xml(self, files: list) -> str:
        cases, rest = [], []
        for rel, text in files:
            detail = self.collection.get(rel)
            if detail is None:
                rest.append((rel, text))
                continue
            cases.append(self.collection_case(rel[:-3].replace("/", "."),
                                              detail))
        cases += [self.collection_case(dotted, detail)
                  for dotted, detail in self.stray_collection]
        head = '<testsuite name="pytest">'
        return super().junit_xml(rest).replace(head, head + "".join(cases), 1)

    @staticmethod
    def collection_case(dotted: str, detail: str) -> str:
        return (f'<testcase classname="" name={quoteattr(dotted)} '
                f'time="0.000"><error message="{COLLECTION}">'
                f'{escape(detail)}</error></testcase>')

    def vitest_items(self, files: list) -> list:
        items, rest = [], []
        for rel, text in files:
            level = self.vitest_level.get(rel)
            if level is None:
                rest.append((rel, text))
                continue
            items.append({"file": rel, "name": FILE_LEVEL_NAME, "state": "fail",
                          "file_level": True, "error_name": level[0],
                          "error_message": level[1]})
        return super().vitest_items(rest) + items

    # --- задачи ---------------------------------------------------------

    def zoned_task(self, project, numbers, zones, green=(), ensure=True):
        """Задача проекта с `zones:` во фронтматтере SPEC и настоящим
        переходом гейта SPEC — опорой; `ensure=False` — без рабочей копии
        и кодовой ветки."""
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, "Фикстура уровня файла", "spec_gate",
                          branch, project.name, 25.0)
        if ensure:
            wt, error = workspace.ensure(tid, branch)
            self.assertIsNone(error, self.note(f"рабочая копия: {error}"))
        else:
            wt = workspace.path(tid, project.name)
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                            target=project.name, wt=Path(wt), project=project)
        t.docs = config.PROJECTS / project.name / TASKS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.docs.mkdir(parents=True, exist_ok=True)
        t.spec = spec_text(tid, numbers, green).replace(
            "schema_version: 5\n",
            f"schema_version: 5\nzones: {', '.join(zones)}\n", 1)
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, tid, "analyst")
        store.set_state(self.conn, tid, "tests_writing", "operator",
                        expected_state="spec_gate", detail=APPROVED_DETAIL)
        self.rematerialize(t)
        return t

    def rematerialize(self, t) -> None:
        """Файлы ссылки документов задачи — на диск каталога документов, как
        на старте шага роли (чекпоинт уносит их и чистит каталог)."""
        clone = str(self.clones[t.target])
        ref = f"refs/artifacts/{t.id}"
        prefix = f"{TASKS_DIR}/{t.id}"
        listed = self.git("-C", clone, "ls-tree", "-r", "--name-only", ref,
                          "--", prefix)
        for rel in listed.split():
            path = t.docs / rel[len(prefix) + 1:]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.git("-C", clone, "show", f"{ref}:{rel}"),
                            encoding="utf-8")
        t.plank.mkdir(parents=True, exist_ok=True)

    def py_module(self, init: bool = False) -> tuple:
        """(P, M): путь нового модуля от корня проекта и его имя."""
        package = f"p{self.word()}"
        if init:
            return f"{package}/__init__.py", package
        mod = f"m{self.word()}"
        return f"{package}/{mod}.py", f"{package}.{mod}"

    def importing_py(self, numbers, module: str, marker: str | None = None,
                     body: str | None = None) -> str:
        text = self.py_plank(numbers, marker)
        line = body if body is not None else f"import {module}  # noqa: F401"
        return text.replace("import unittest\n", f"import unittest\n{line}\n", 1)

    def py_detail(self, rel: str, module: str, last: str | None = None,
                  prefix: bool = True, early: str = "") -> str:
        """Текст записи сбора pytest: трассировка импорта файла `rel`;
        итоговая строка — `ModuleNotFoundError` модуля `module` (с
        префиксом `E   ` либо без) или `last`; `early` — строка в середине
        трассировки."""
        if last is None:
            last = f"ModuleNotFoundError: No module named '{module}'"
            if prefix:
                last = "E   " + last
        lines = [f"ImportError while importing test module "
                 f"'/{self.word()}/{rel}'.",
                 "Hint: make sure your test modules/packages have valid Python "
                 "names.",
                 "Traceback:",
                 "/usr/lib/python3/importlib/__init__.py:90: in import_module",
                 "    return _bootstrap._gcd_import(name[level:], package, level)",
                 f"{rel}:{self.rng.randint(3, 9)}: in <module>",
                 f"    import {module}"]
        if early:
            lines.append(early)
        return "\n".join(lines + [last]) + "\n\n"

    def long_py(self, n: int) -> str:
        name = self.word()
        return "\n".join([
            '"""Долгоживущая фикстура ' + name + ".", "",
            "Группа: долгоживущий",
            "Красен " + "до реализации: фикстура " + name + ".", '"""',
            "import unittest", "", "",
            "class FixtureLongLivedTest(unittest.TestCase):", "",
            f"    def test_ac{n}_{name}(self):",
            '        """Фикстурный метод.', "",
            "        Ловит " + "мутацию: фикстура " + name + " — сумма другая.",
            '        """', "        self.assertEqual(2 + 2, 5)", ""])

    def jsx_importing(self, numbers, spec: str) -> str:
        return self.jsx(numbers).replace(
            "import { expect, it } from 'vitest';",
            "import { expect, it } from 'vitest';\n"
            f"import {{ value }} from '{spec}';", 1)

    # --- наблюдения -----------------------------------------------------

    def counted(self, t) -> list:
        return [r["detail"] or "" for r in store.task_steps(self.conn, t.id)
                if r["action"] == COUNTED_ACTION]

    def f2p_parts(self, rows: list) -> list:
        return [p for d in self.details(rows, F2P_ACTION) for p in parts_of(d)]

    def file_level_named(self, rows: list, name: str) -> bool:
        return f"{name}: {FILE_LEVEL}" in self.f2p_parts(rows)

    def assert_counted(self, t, rows, output, path: str, name: str) -> None:
        context = self.explain(rows, output)
        self.assertFalse(self.file_level_named(rows, name), context)
        self.assertIn(COUNTED_DETAIL.format(path=path, name=name),
                      self.counted(t), context)

    def assert_not_counted(self, t, rows, output, name: str | None) -> None:
        """Прежняя находка уровня файла (`name` — имя файла в находке;
        `None` — любая) и ни одной записи засчитывания."""
        context = self.explain(rows, output)
        if name is None:
            self.assertTrue(any(p.endswith(f": {FILE_LEVEL}")
                                for p in self.f2p_parts(rows)), context)
        else:
            self.assertTrue(self.file_level_named(rows, name), context)
        self.assertEqual(self.counted(t), [], context)

    # --- сценарии -------------------------------------------------------

    def py_case(self, *, init: bool = False, zones=None, module=None,
                detail=None, marker=None, green=(), ensure=True,
                body=None, path=None) -> SimpleNamespace:
        """Компонент `junit-xml`: файл планки с тестом одного критерия,
        запись сбора файла; P и M — новый модуль (либо `path`/`module`
        сценария); `zones` — `zones:` опорного SPEC (по умолчанию `[P]`)."""
        n = self.numbers(1)[0]
        project = self.junit_project()
        p_rel, m_name = self.py_module(init)
        if path is not None:
            p_rel = path
        if module is not None:
            m_name = module
        t = self.zoned_task(project, (n,), zones if zones is not None else [p_rel],
                            green=green, ensure=ensure)
        name = f"test_{self.word()}.py"
        line = body(m_name) if callable(body) else body
        self.write_plank(t, {name: self.importing_py((n,), m_name, marker, line)})
        rel = self.layout_rel(t, name)
        self.collection[rel] = (detail(rel, m_name) if callable(detail)
                                else self.py_detail(rel, m_name))
        return SimpleNamespace(t=t, n=n, name=name, path=p_rel, module=m_name,
                               rel=rel)

    def vitest_case_level(self, *, path: str, spec: str, form: str,
                          zones=None) -> SimpleNamespace:
        """Компонент `pult-vitest`: файл планки с тестом одного критерия,
        запись `file_level` с сообщением формы `form` о спецификаторе
        `spec`; `path` — P."""
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.zoned_task(project, (n,), zones if zones is not None else [path])
        name = f"m{self.word()}.test.jsx"
        self.write_plank(t, {name: self.jsx_importing((n,), spec)})
        rel = self.layout_rel(t, name)
        self.vitest_level[rel] = ("Error", form.format(spec=spec, file=rel))
        return SimpleNamespace(t=t, n=n, name=name, path=path, rel=rel)


# ---------------------------------------------------------------- AC-3

class Ac3OutOfBoundsTest(FileLevelSandbox):

    def package(self, t) -> str:
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "PLAN.md").write_text(PLAN_READY.format(task=t.id),
                                        encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                return review.review_package(self.conn, t.id, "Фикстура",
                                             t.branch)["text"]
            except SystemExit as exc:
                return f"SystemExit: {exc.code}\n{buf.getvalue()}"

    def test_ac3_test_profile_new_module_no_gate_no_record_no_line(self):
        """Запись `test_profile` с `report: junit-xml` при выполненных (а) и (б): гейта нет, записи засчитывания нет, строки пакета нет.

        Сценарий: проект записи `test_profile` (`runner: pytest-own`,
        `report: junit-xml`), задача с опорой SPEC и P в `zones:`, файл
        планки без маркера «Зелёный с рождения:», отчёт — запись сбора с
        итоговой строкой `E   ModuleNotFoundError: No module named
        '<M>'`. Переход: ни одной записи журнала с «честный FAIL_TO_PASS»,
        ни одной находки «ошибка уровня файла», записи «ошибка уровня файла
        засчитана красным» нет; пакет ревьювера задачи не несёт строки
        «ошибка уровня файла засчитана красным: …».

        Ловит мутацию: засчитывание включено по `report` без границы
        `in_outcome_bounds` — у `test_profile` пишется запись журнала и
        строка пакета; находка уровня файла стала проверяться у любого
        профиля с отчётом — у `test_profile` появилась находка.
        """
        n = self.numbers(1)[0]
        project = self.own_profile_project()
        p_rel, m_name = self.py_module()
        t = self.zoned_task(project, (n,), [p_rel])
        name = f"test_{self.word()}.py"
        self.write_plank(t, {name: self.importing_py((n,), m_name)})
        self.collection = _AnyRel(lambda rel: self.py_detail(rel, m_name))
        rows, output = self.advance(t)
        context = self.explain(rows, output)
        self.assertFalse([r for r in rows
                          if "честный FAIL_TO_PASS" in (r["action"] or "")
                          or FILE_LEVEL in (r["detail"] or "")], context)
        self.assertEqual(self.counted(t), [], context)
        text = self.package(t)
        self.assertNotIn(COUNTED_ACTION, text, self.note(text[-3000:]))


class _AnyRel(dict):
    """Текст записи сбора для любого файла прогона, кроме `test_base.py`."""

    def __init__(self, make):
        super().__init__()
        self.make = make

    def get(self, rel, default=None):
        if Path(rel).name == "test_base.py":
            return default
        return self.make(rel)


# ---------------------------------------------------------------- AC-4

class Ac4MatchingTest(FileLevelSandbox):

    def test_ac4_long_lived_record_with_same_name_does_not_count_plank(self):
        """Запись сбора долгоживущего `tests/test_x.py` не засчитывает файл планки `…/test_x.py`: находка уровня файла, записи засчитывания нет.

        Сценарий: компонент `junit-xml`, P — новый модуль в `zones:`; файл
        планки и свой долгоживущий файл задачи — одно имя `test_<…>.py`;
        тест критерия файла планки падает на `assert`, у долгоживущего —
        запись сбора с итоговой строкой `ModuleNotFoundError` модуля P.
        Отказ «переход отклонён: честный FAIL_TO_PASS» с находкой «… ошибка
        уровня файла»; записи «ошибка уровня файла засчитана красным» нет.

        Ловит мутацию: запись сбора сопоставляется с файлом планки по
        последнему сегменту точечного пути (как текст находки) — файл
        планки засчитан, запись журнала есть, находки нет.
        """
        a, b = self.numbers(2)
        project = self.junit_project()
        p_rel, m_name = self.py_module()
        t = self.zoned_task(project, (a, b), [p_rel])
        name = f"test_{t.low}_{self.word()}.py"
        self.write_plank(t, {name: self.py_plank((a,))})
        long_rel = f"tests/{name}"
        self.write_code(t, long_rel, self.long_py(b))
        self.collection[long_rel] = self.py_detail(long_rel, m_name)
        rows, output = self.advance(t)
        self.assert_not_counted(t, rows, output, None)

    def test_ac4_unmatched_collection_record_keeps_finding(self):
        """Запись сбора, не сопоставленная ни с одним файлом планки, — прежняя находка уровня файла.

        Сценарий: компонент `junit-xml`, P — новый модуль в `zones:`; тест
        критерия файла планки падает на `assert`; отчёт сверх него несёт
        запись сбора с точечным именем вне файлов задачи и итоговой
        строкой `ModuleNotFoundError` модуля P. Отказ с находкой «<точечное
        имя>: ошибка уровня файла — тесты файла не исполнены»; записи
        засчитывания нет.

        Ловит мутацию: несопоставленная запись `file_level` пропускается
        молча (находки нет, задача в `in_dev`) либо засчитывается по одним
        условиям (а) и (б) без файла — запись журнала есть.
        """
        n = self.numbers(1)[0]
        project = self.junit_project()
        p_rel, m_name = self.py_module()
        t = self.zoned_task(project, (n,), [p_rel])
        self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
        dotted = f"{self.word()}.test_{self.word()}"
        self.stray_collection.append(
            (dotted, self.py_detail(dotted.replace(".", "/") + ".py", m_name)))
        rows, output = self.advance(t)
        self.assert_not_counted(t, rows, output, dotted)

    def test_ac4_vitest_file_level_record_without_conditions_is_finding(self):
        """Файл Vitest с записью `file_level`, у которой не выполнено (а) или (б), — находка `FILE_LEVEL_FINDING`.

        Сценарий (подслучай — свежая задача): запись `file_level` файла
        планки с сообщением `Failed to resolve import "<S>" from "<файл>"`;
        (а) не выполнено — P нет в `zones:` (там другой путь), S
        разрешается в P; (б) не выполнено — P в `zones:`, сообщение иной
        формы. Отказ «переход отклонён: честный FAIL_TO_PASS» с находкой
        «<файл>: ошибка уровня файла — тесты файла не исполнены»; записи
        засчитывания нет.

        Ловит мутацию: находка уровня файла Vitest — только по файлу без
        записей (второе правило) — у файла с записью `file_level` находки
        нет, задача уходит в `in_dev` или отказ называет лишь «теста нет
        в отчёте».
        """
        for label in ("а", "б"):
            with self.subTest(case=label, seed=self.seed):
                folder, mod = self.word(), self.word()
                path = f"frontend/src/{folder}/{mod}.jsx"
                spec = f"../../{folder}/{mod}.jsx"
                if label == "а":
                    case = self.vitest_case_level(
                        path=path, spec=spec, form=VITEST_FORMS["resolve"],
                        zones=[f"frontend/src/{folder}/{self.word()}.jsx"])
                else:
                    case = self.vitest_case_level(
                        path=path, spec=spec,
                        form="Error: Failed to load url {spec}")
                rows, output = self.advance(case.t)
                self.assert_not_counted(case.t, rows, output, case.name)

    def test_ac4_vitest_file_without_records_is_file_level(self):
        """Файл Vitest без записей в отчёте — по-прежнему находка уровня файла (второе правило).

        Сценарий: P — новый модуль в `zones:`; планка из двух файлов, отчёт
        базы не несёт ни одной записи второго (тест критерия первого падает
        с `AssertionError`). Отказ с находкой «<второй файл>: ошибка уровня
        файла — тесты файла не исполнены»; записи засчитывания нет.

        Ловит мутацию: второе правило `_file_level_findings` снято вместе с
        переходом на записи `file_level` — файл без записей даёт лишь
        «теста нет в отчёте».
        """
        folder, mod = self.word(), self.word()
        a, b = self.numbers(2)
        project = self.vitest_project()
        t = self.zoned_task(project, (a, b), [f"frontend/src/{folder}/{mod}.jsx"])
        name = f"e{self.word()}.test.jsx"
        self.write_plank(t, {f"d{self.word()}.test.jsx": self.jsx((a,)),
                             name: self.jsx_importing((b,),
                                                      f"../../{folder}/{mod}.jsx")})
        self.drop_files.add(name)
        rows, output = self.advance(t)
        self.assert_not_counted(t, rows, output, name)


# ---------------------------------------------------------------- AC-6

class Ac6PythonCountedTest(FileLevelSandbox):

    def test_ac6_python_new_module_counted_red(self):
        """Python, профиль в границе: новый модуль P из `zones:` в итоговой строке `ModuleNotFoundError` — засчитывание без находки уровня файла и запись журнала.

        Сценарий (подслучай — свежая задача): файл планки без маркера,
        запись сбора; P — элемент `zones:` опорного SPEC, нет в дереве
        `diff_base`; последняя непустая строка `detail` — (а) `E   Module
        NotFoundError: No module named '<M>'`; (б) та же без `E   `; (в) P —
        `<пакет>/__init__.py`, M — имя пакета. Находки «<файл>: ошибка
        уровня файла …» нет; запись «ошибка уровня файла засчитана
        красным» с деталью «новый модуль <P> (файл <имя>)».

        Ловит мутацию: строка без префикса `E   ` не распознана — в (б)
        находка; M для `__init__.py` строится как `<пакет>.__init__` — в (в)
        находка; деталь записи называет путь записи отчёта вместо P или
        не называет файл.
        """
        for label, init, prefix in (("E", False, True), ("без E", False, False),
                                    ("__init__", True, True)):
            with self.subTest(case=label, seed=self.seed):
                self.collection = {}
                case = self.py_case(
                    init=init, detail=lambda rel, m, p=prefix:
                    self.py_detail(rel, m, prefix=p))
                rows, output = self.advance(case.t)
                self.assert_counted(case.t, rows, output, case.path, case.name)


# ---------------------------------------------------------------- AC-7

class Ac7VitestCountedTest(FileLevelSandbox):

    def test_ac7_vitest_specifier_three_cases_two_forms(self):
        """Vitest, профиль в границе: спецификатор, разрешённый от каталога выкладки в P, — засчитывание в трёх случаях и двух формах сообщения.

        Сценарий (подслучай — свежая задача): каталог файла в выкладке
        `plank_layout` — `frontend/src/<скрытый>/<id>`; S — `../../<…>`;
        случаи: S с расширением, R = P; S без расширения, R = P без
        расширения; S — каталог, R + `/index` = P без расширения (P =
        `…/index.jsx`); формы — `Failed to resolve import "<S>" from
        "<файл>"` и `Cannot find module '<S>'`. Находки уровня файла нет;
        запись «ошибка уровня файла засчитана красным» с деталью «новый
        модуль <P> (файл <имя>)».

        Ловит мутацию: S разрешается от корня проекта, а не от каталога
        файла в выкладке — R не совпадает, находка; не разобрана одна из
        форм; нет случая `/index` или случая без расширения — находка в
        этом подслучае.
        """
        for case_kind in ("ext", "noext", "index"):
            for form in ("resolve", "cannot"):
                with self.subTest(case=case_kind, form=form, seed=self.seed):
                    self.vitest_level = {}
                    folder, mod = self.word(), self.word()
                    if case_kind == "ext":
                        path = f"frontend/src/{folder}/{mod}.jsx"
                        spec = f"../../{folder}/{mod}.jsx"
                    elif case_kind == "noext":
                        path = f"frontend/src/{folder}/{mod}.jsx"
                        spec = f"../../{folder}/{mod}"
                    else:
                        path = f"frontend/src/{folder}/index.jsx"
                        spec = f"../../{folder}"
                    case = self.vitest_case_level(path=path, spec=spec,
                                                  form=VITEST_FORMS[form])
                    rows, output = self.advance(case.t)
                    self.assert_counted(case.t, rows, output, case.path,
                                        case.name)


# ---------------------------------------------------------------- AC-8

class Ac8ConditionABreaksTest(FileLevelSandbox):

    def zones_extend(self, t, path: str) -> None:
        """Мандат Оператора `zones-extend` на `path` (матрица неослабления
        одной строкой) и зеркало ссылки документов на диске."""
        row = (f"`{path}`", "фикстура сценария", "да",
               f"tests/test_{self.word()}.py", "ок")
        text = ("## Матрица неослабления\n\n"
                "| " + " | ".join(MATRIX_HEADERS) + " |\n"
                + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
                + "| " + " | ".join(row) + " |\n")
        matrix = Path(tempfile.mkdtemp(prefix="artel-matrix-")) / "m.md"
        matrix.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                answer.cmd_zones_extend(t.id, path, None, str(matrix))
            except SystemExit as exc:
                self.fail(self.note(f"zones-extend отказала: {exc.code}\n"
                                    f"{buf.getvalue()}"))
        store.update_task(self.conn, t.id, zones_extension=path)
        self.rematerialize(t)

    def test_ac8_condition_a_and_exclusions_break_counting(self):
        """Условие (а) и исключения ломают засчитывание: прежняя находка уровня файла, записи журнала нет.

        Сценарий (подслучай — свежая задача, прочие условия AC-6): (1) в
        `zones:` только каталог модуля; (2) P — файл, уже лежащий в дереве
        `diff_base` (`app.py` проекта); (3) P добавлен только
        `zones-extend` (ANSWER мандата, `zones_extension`), в `zones:`
        другой путь; (4) файл планки с маркером «Зелёный с рождения:»
        (критерий в разделе SPEC); (5) файл — свой долгоживущий задачи.
        Отказ «переход отклонён: честный FAIL_TO_PASS» с находкой «…
        ошибка уровня файла»; записей «ошибка уровня файла засчитана
        красным» нет.

        Ловит мутацию: P сверяется с зонами по префиксу каталога — в (1)
        засчитано; отсутствие P не проверяется — в (2) засчитано; зоны
        берутся из `zones_extension`/мандатов — в (3) засчитано; маркер или
        долгоживущий файл не исключены — в (4)/(5) засчитано.
        """
        def directory():
            p_rel, m_name = self.py_module()
            case = self.py_case(path=p_rel, module=m_name,
                                zones=[p_rel.rsplit("/", 1)[0] + "/"])
            return case, case.name

        def in_base():
            case = self.py_case(path="app.py", module="app")
            return case, case.name

        def extended():
            p_rel, m_name = self.py_module()
            n = self.numbers(1)[0]
            project = self.junit_project()
            t = self.zoned_task(project, (n,), [f"{self.word()}.py"])
            self.zones_extend(t, p_rel)
            name = f"test_{self.word()}.py"
            self.write_plank(t, {name: self.importing_py((n,), m_name)})
            rel = self.layout_rel(t, name)
            self.collection[rel] = self.py_detail(rel, m_name)
            return SimpleNamespace(t=t), name

        def green_marker():
            n = self.numbers(1)[0]
            p_rel, m_name = self.py_module()
            project = self.junit_project()
            t = self.zoned_task(project, (n,), [p_rel], green=(n,))
            name = f"test_{self.word()}.py"
            marker = "Зелёный " + "с рождения: фикстура держит прежнее."
            self.write_plank(t, {name: self.importing_py((n,), m_name, marker)})
            rel = self.layout_rel(t, name)
            self.collection[rel] = self.py_detail(rel, m_name)
            return SimpleNamespace(t=t), name

        def long_lived():
            a, b = self.numbers(2)
            p_rel, m_name = self.py_module()
            project = self.junit_project()
            t = self.zoned_task(project, (a, b), [p_rel])
            self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((a,))})
            long_rel = f"tests/test_{t.low}_{self.word()}.py"
            self.write_code(t, long_rel, self.long_py(b))
            self.collection[long_rel] = self.py_detail(long_rel, m_name)
            return SimpleNamespace(t=t), None

        for label, arrange in (("каталог", directory), ("в базе", in_base),
                               ("zones-extend", extended),
                               ("маркер", green_marker),
                               ("долгоживущий", long_lived)):
            with self.subTest(case=label, seed=self.seed):
                self.collection = {}
                case, name = arrange()
                rows, output = self.advance(case.t)
                self.assert_not_counted(case.t, rows, output, name)


# ---------------------------------------------------------------- AC-9

class Ac9PythonConditionBBreaksTest(FileLevelSandbox):

    def test_ac9_python_final_line_mismatch_breaks_counting(self):
        """Условие (б) у Python ломает засчитывание: другое имя модуля, имя, лишь содержащее ожидаемое, иное исключение, `RuntimeError` с текстом `ModuleNotFoundError`.

        Сценарий (подслучай — свежая задача, прочие условия AC-6): итоговая
        строка `detail` — (1) `E   ModuleNotFoundError: No module named
        '<другое>'`; (2) то же с `<префикс><M><суффикс>`; (3) `E
        AttributeError: …`, а строка `ModuleNotFoundError` с ожидаемым M —
        в середине трассировки; (4) файл планки падает на `raise
        RuntimeError("ModuleNotFoundError: No module named '<M>'")` —
        итоговая строка `E   RuntimeError: ModuleNotFoundError: No module
        named '<M>'`. Прежняя находка уровня файла, записи журнала нет.

        Ловит мутацию: M ищется вхождением ожидаемого имени — в (2)
        засчитано; распознаётся любая строка `ModuleNotFoundError` в
        `detail`, а не последняя — в (3) засчитано; строка ищется поиском
        без привязки к началу — в (4) засчитано.
        """
        def other(rel, m):
            return self.py_detail(rel, m, last="E   ModuleNotFoundError: No "
                                  f"module named '{self.word()}.{self.word()}'")

        def containing(rel, m):
            return self.py_detail(rel, m, last="E   ModuleNotFoundError: No "
                                  f"module named 'x{m}{self.word(3)}'")

        def other_kind(rel, m):
            return self.py_detail(
                rel, m, early=f"E   ModuleNotFoundError: No module named '{m}'",
                last=f"E   AttributeError: module '{m}' has no attribute "
                     f"'{self.word()}'")

        def runtime(rel, m):
            return self.py_detail(
                rel, m, last="E   RuntimeError: ModuleNotFoundError: No module "
                             f"named '{m}'")

        for label, detail in (("другое имя", other), ("содержит", containing),
                              ("иное исключение", other_kind),
                              ("RuntimeError", runtime)):
            with self.subTest(case=label, seed=self.seed):
                self.collection = {}
                body = None
                if detail is runtime:
                    def body(m):
                        return ("raise RuntimeError(\"ModuleNotFoundError: No "
                                f"module named '{m}'\")")
                case = self.py_case(detail=detail, body=body)
                rows, output = self.advance(case.t)
                self.assert_not_counted(case.t, rows, output, case.name)


# --------------------------------------------------------------- AC-10

class Ac10VitestConditionBBreaksTest(FileLevelSandbox):

    def test_ac10_vitest_specifier_mismatch_and_other_form_break_counting(self):
        """Условие (б) у Vitest ломает засчитывание: R не подходит ни под один случай, сообщение иной формы.

        Сценарий (подслучай — свежая задача, прочие условия AC-7, форма
        `Failed to resolve import`): (1) S с расширением в другой файл
        каталога P; (2) S без расширения в другое имя; (3) S с расширением
        `.js` при P `….jsx`; (4) S — каталог P при P не `index`; (5) S верен,
        сообщение `Error: Failed to load url <S>`; (6) S верен, сообщение
        `Module not found: Can't resolve '<S>'`. Прежняя находка уровня
        файла, записи журнала нет.

        Ловит мутацию: расширение отбрасывается у R всегда — в (3)
        засчитано; случай `/index` применён к любому каталогу P — в (4)
        засчитано; спецификатор ищется в любом тексте в кавычках — в
        (5)/(6) засчитано.
        """
        resolve = VITEST_FORMS["resolve"]
        cases = (("другой файл", "{folder}/{other}.jsx", "{folder}/{mod}.jsx",
                  resolve),
                 ("другое имя", "{folder}/{other}", "{folder}/{mod}.jsx",
                  resolve),
                 ("расширение", "{folder}/{mod}.js", "{folder}/{mod}.jsx",
                  resolve),
                 ("каталог", "{folder}", "{folder}/{mod}.jsx", resolve),
                 ("иная форма", "{folder}/{mod}.jsx", "{folder}/{mod}.jsx",
                  "Error: Failed to load url {spec}"),
                 ("иная форма 2", "{folder}/{mod}.jsx", "{folder}/{mod}.jsx",
                  "Module not found: Can't resolve '{spec}'"))
        for label, spec_t, path_t, form in cases:
            with self.subTest(case=label, seed=self.seed):
                self.vitest_level = {}
                names = {"folder": self.word(), "mod": self.word(),
                         "other": self.word()}
                case = self.vitest_case_level(
                    path="frontend/src/" + path_t.format(**names),
                    spec="../../" + spec_t.format(**names), form=form)
                rows, output = self.advance(case.t)
                self.assert_not_counted(case.t, rows, output, case.name)


# --------------------------------------------------------------- AC-11

class Ac11HeadAndGitTest(FileLevelSandbox):

    def test_ac11_no_code_branch_looks_in_run_head(self):
        """Кодовой ветки нет: P ищется в HEAD рабочей копии прогона — нет там P — засчитывание, есть — прежняя находка.

        Сценарий (подслучай — задача без рабочей копии и кодовой ветки до
        перехода, прочие условия AC-6): (1) P — новый модуль, его нет в HEAD
        — находки уровня файла нет, запись засчитывания с деталью «новый
        модуль <P> (файл <имя>)»; (2) P — `app.py`, лежащий в HEAD, —
        прежняя находка, записи нет.

        Ловит мутацию: без кодовой ветки засчитывание не проверяется вовсе
        — в (1) находка; отсутствие ищется в несуществующей ветке и
        трактуется как «нет» — в (2) засчитано.
        """
        with self.subTest(case="нет в HEAD", seed=self.seed):
            self.collection = {}
            case = self.py_case(ensure=False)
            rows, output = self.advance(case.t)
            self.assert_counted(case.t, rows, output, case.path, case.name)
        with self.subTest(case="есть в HEAD", seed=self.seed):
            self.collection = {}
            case = self.py_case(ensure=False, path="app.py", module="app")
            rows, output = self.advance(case.t)
            self.assert_not_counted(case.t, rows, output, case.name)

    def test_ac11_git_failure_on_absence_check_is_prepare_refusal(self):
        """Git не ответил при проверке отсутствия P (в дереве `diff_base` либо в HEAD) — отказ подготовки гейта, не засчитывание.

        Сценарий (подслучай — кодовая ветка есть / её нет, прочие условия
        AC-6): после прогона гейта шпион отвечает кодом 128 на `git` из
        кода модулей зон задачи. Отказ «переход отклонён: честный
        FAIL_TO_PASS — отказ подготовки»; записи засчитывания нет.

        Ловит мутацию: ответ git без кода 0 читается как «P нет в дереве»
        — засчитывание, задача в `in_dev`; сбой читается как «P есть» —
        прежняя находка общим отказом вместо отказа подготовки.
        """
        for label, ensure in (("ветка есть", True), ("ветки нет", False)):
            with self.subTest(case=label, seed=self.seed):
                self.collection = {}
                self.git_armed = False
                self.git_failed = []
                case = self.py_case(ensure=ensure)
                self.git_break = "после прогона"
                try:
                    rows, output = self.advance(case.t)
                finally:
                    self.git_break = None
                    self.git_armed = False
                context = self.explain(rows, output) + f"\ngit: {self.git_failed}"
                self.assertTrue(self.details(rows, PREPARE_ACTION), context)
                self.assertEqual(self.counted(case.t), [], context)


# --------------------------------------------------------------- AC-12

class Ac12PartialCriterionTest(FileLevelSandbox):

    def test_ac12_no_record_finding_stays_for_partially_counted_criterion(self):
        """Находка «теста нет в отчёте» подавляется только у критерия, все файлы которого засчитаны.

        Сценарий: компонент `junit-xml`; файл A — тесты критериев n и m,
        запись сбора нового модуля P из `zones:` (засчитан); файл B — тест
        критерия n, запись сбора модуля вне зон (не засчитан). Отказ
        «переход отклонён: честный FAIL_TO_PASS»: находка «AC-n: теста нет
        в отчёте» и «B: ошибка уровня файла …» есть; находок «AC-m: теста
        нет в отчёте» и «A: ошибка уровня файла …» нет.

        Ловит мутацию: «теста нет в отчёте» подавляется у критерия, у
        которого засчитан хоть один файл, — находки AC-n нет; подавление не
        сделано вовсе — находка AC-m есть.
        """
        n, m = self.numbers(2)
        project = self.junit_project()
        p_rel, m_name = self.py_module()
        t = self.zoned_task(project, (n, m), [p_rel])
        first, second = f"test_{self.word()}.py", f"test_{self.word()}.py"
        other = f"{self.word()}.{self.word()}"
        self.write_plank(t, {first: self.importing_py((n, m), m_name),
                             second: self.importing_py((n,), other)})
        rel_a, rel_b = self.layout_rel(t, first), self.layout_rel(t, second)
        self.collection[rel_a] = self.py_detail(rel_a, m_name)
        self.collection[rel_b] = self.py_detail(rel_b, other)
        rows, output = self.advance(t)
        found = self.f2p_parts(rows)
        context = self.explain(rows, output)
        self.assertIn(COUNTED_DETAIL.format(path=p_rel, name=first),
                      self.counted(t), context)
        self.assertTrue(any(p.startswith(f"AC-{n}: {NO_RECORD}") for p in found),
                        context)
        self.assertFalse(any(p.startswith(f"AC-{m}: {NO_RECORD}") for p in found),
                         context)
        self.assertIn(f"{second}: {FILE_LEVEL}", found, context)
        self.assertNotIn(f"{first}: {FILE_LEVEL}", found, context)


# --------------------------------------------------------------- AC-13

class Ac13BranchCheckTest(FileLevelSandbox):

    def test_ac13_counted_file_branch_check_missing_and_red(self):
        """Засчитанный файл и проверка ветки на `in_dev → review`: теста критерия нет — «теста нет в отчёте прогона ветки», тест красный — «тест критерия не прошёл на ветке».

        Сценарий (подслучай — свежая задача): файл планки с тестами
        критериев n и m засчитан на выходе из `tests_writing` (задача в
        `in_dev`); прогон ветки — (1) записи теста n нет, тест m прошёл;
        (2) тест n упал на `assert` при вердикте прогона, подменённом
        зелёным (`outcome.verdict` — так достигается защитная ветка
        проверки), тест m прошёл. Отказ «переход отклонён: приёмочные
        тесты — тест критерия не в отчёте» с деталью «AC-n — теста нет в
        отчёте прогона ветки» либо «AC-n — тест критерия не прошёл на
        ветке»; задача в `in_dev`.

        Ловит мутацию: засчитанный файл исключён из проверки ветки (или его
        критерии помечены покрытыми) — переход в `verifying` без отказа.
        """
        for label in ("нет записи", "красный"):
            with self.subTest(case=label, seed=self.seed):
                self.collection = {}
                self.branch_phase(base=True)
                n, m = self.numbers(2)
                project = self.junit_project()
                p_rel, m_name = self.py_module()
                t = self.zoned_task(project, (n, m), [p_rel, project.code])
                name = f"test_{self.word()}.py"
                self.write_plank(t, {name: self.importing_py((n, m), m_name)})
                rel = self.layout_rel(t, name)
                self.collection[rel] = self.py_detail(rel, m_name)
                self.passes(t)
                self.assertTrue(self.counted(t), self.note("файл не засчитан"))
                self.collection = {}
                self.branch_phase()
                if label == "нет записи":
                    self.drop_numbers.add(n)
                    rows, output = self.developer_advance(t)
                    expected = f"AC-{n} — теста нет в отчёте прогона ветки"
                else:
                    self.junit_case[n] = ("failure", "assert 1 == 2")
                    with mock.patch.object(
                            outcome, "verdict",
                            lambda records, code, reason="": (outcome.GREEN, "")):
                        rows, output = self.developer_advance(t)
                    expected = f"AC-{n} — тест критерия не прошёл на ветке"
                found = self.details(rows, BRANCH_ACTION)
                context = self.explain(rows, output)
                self.assertTrue(found, context)
                self.assertIn(expected, found[-1], context)
                self.assertEqual(self.state(t), "in_dev", context)


# --------------------------------------------------------------- AC-14

class Ac14ReviewLineTest(FileLevelSandbox):

    def review_task(self, project):
        n = self.numbers(1)[0]
        t = self.zoned_task(project, (n,), [project.code])
        store.set_state(self.conn, t.id, "review", "operator",
                        expected_state="tests_writing", detail="сценарий: ревью")
        return t

    def package(self, t) -> str:
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "PLAN.md").write_text(PLAN_READY.format(task=t.id),
                                        encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            checkpoint.commit_step_artifacts(self.conn, t.id, "developer")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                return review.review_package(self.conn, t.id, "Фикстура",
                                             t.branch)["text"]
            except SystemExit as exc:
                return f"SystemExit: {exc.code}\n{buf.getvalue()}"

    @staticmethod
    def section(text: str) -> str | None:
        mark = f"### {SECTION}"
        start = text.find(mark)
        if start < 0:
            return None
        end = text.find("\n### ", start + len(mark))
        return text[start:end if end >= 0 else len(text)]

    def detail(self) -> str:
        return COUNTED_DETAIL.format(path=f"p{self.word()}/m{self.word()}.py",
                                     name=f"test_{self.word()}.py")

    def test_ac14_review_section_line_per_distinct_detail(self):
        """Пакет ревьювера профиля в границе: строка «ошибка уровня файла засчитана красным: <деталь>» по одной на различную деталь; без записей строки нет.

        Сценарий (подслучай): (1) задача проекта `junit-xml` в `review`,
        журнал несёт три записи «ошибка уровня файла засчитана красным» с
        двумя различными деталями (одна повторена) — в разделе
        «Изменённые утверждения тестов» каждая строка «… засчитана
        красным: <деталь>» ровно один раз; (2) такая же задача без записей
        — в пакете нет текста «ошибка уровня файла засчитана красным».

        Ловит мутацию: строки пишутся по каждой записи журнала (повтор
        даёт две строки); записи берутся по всему пульту, а не задачи —
        или не читаются вовсе — строки нет.
        """
        project = self.junit_project()
        with self.subTest(case="записи", seed=self.seed):
            t = self.review_task(project)
            first, second = self.detail(), self.detail()
            for text in (first, second, first):
                store.journal(self.conn, t.id, "fsm", COUNTED_ACTION, text)
            part = self.section(self.package(t)) or ""
            for text in (first, second):
                self.assertEqual(part.count(f"{COUNTED_ACTION}: {text}"), 1,
                                 self.note(part))
        with self.subTest(case="без записей", seed=self.seed):
            t = self.review_task(project)
            text = self.package(t)
            self.assertNotIn(COUNTED_ACTION, text, self.note(text[-3000:]))

    def test_ac14_out_of_bounds_section_unchanged(self):
        """Вне границы (запись `test_profile`) раздел пакета прежний побайтно и при записях засчитывания в журнале.

        Сценарий: задача проекта записи `test_profile` в `review`; раздел
        «Изменённые утверждения тестов» пакета без записей и после двух
        записей «ошибка уровня файла засчитана красным» совпадают (с
        точностью до метки граничных маркеров сборки); текста «… засчитана
        красным» в пакете нет.

        Ловит мутацию: строки засчитывания добавляются в раздел без
        проверки границы `in_outcome_bounds` — у `test_profile` раздел
        несёт строку.
        """
        project = self.own_profile_project()
        t = self.review_task(project)
        before = self.section(self.package(t))
        for _ in range(2):
            store.journal(self.conn, t.id, "fsm", COUNTED_ACTION, self.detail())
        text = self.package(t)
        after = self.section(text)
        normal = (lambda s: None if s is None else BOUNDARY_ID.sub("#", s))
        self.assertEqual(normal(after), normal(before), self.note(str(after)))
        self.assertNotIn(COUNTED_ACTION, text, self.note(text[-3000:]))


# --------------------------------------------------------------- AC-15

class Ac15CarryOverTest(FileLevelSandbox):

    def test_ac15_junit_type_error_is_not_check_failure(self):
        """Перенос 10: компонент `junit-xml` со списком `[AssertionError]` — запись `failed` с `TypeError` не провал проверки, отказ гейта FAIL_TO_PASS.

        Сценарий: тест критерия на базе — `<failure message="TypeError:
        …">`. Отказ «переход отклонён: честный FAIL_TO_PASS», деталь
        называет идентификатор теста и «TypeError»; задача в
        `tests_writing`.

        Ловит мутацию: у `junit-xml` провалом проверки считается любой
        `failed` (как у прежнего прогона) — `TypeError` принят, задача в
        `in_dev`.
        """
        n = self.numbers(1)[0]
        project = self.junit_project()
        t = self.new_task(project, (n,))
        self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
        self.junit_case[n] = ("failure", f"TypeError: {self.word()}")
        detail, rows, output = self.refusal(t, F2P_ACTION)
        self.assertIn("TypeError", detail, self.explain(rows, output))
        self.assertIn(f"test_ac{n}_", detail, self.explain(rows, output))

    def test_ac15_fail_to_pass_hint_printed_once(self):
        """Перенос 15: печать отказа FAIL_TO_PASS несёт «дальше:» ровно один раз, деталь записи журнала — «\\nдальше:».

        Сценарий: компонент `pult-vitest`, тест критерия на базе прошёл —
        отказ «переход отклонён: честный FAIL_TO_PASS». В выводе `advance`
        «дальше:» встречается один раз; деталь записи содержит
        «\\nдальше:».

        Ловит мутацию: подсказка отказа (`hint`) оставлена непустой рядом с
        подсказкой в детали — печать несёт «дальше:» дважды; подсказка
        убрана из детали — бриф test_author её не видит.
        """
        n = self.numbers(1)[0]
        project = self.vitest_project()
        t = self.new_task(project, (n,))
        self.write_plank(t, {f"h{self.word()}.test.jsx": self.jsx((n,))})
        self.vitest_case[n] = {"state": "pass", "error_name": None}
        detail, rows, output = self.refusal(t, F2P_ACTION)
        self.assertEqual(output.count(NEXT), 1, self.explain(rows, output))
        self.assertIn(f"\n{NEXT}", detail, self.explain(rows, output))

    def test_ac15_other_refusals_keep_hint_in_detail(self):
        """Перенос 15: детали отказов групп, долгоживущих файлов и сбоя git долгоживущих файлов по-прежнему несут «\\nдальше: <подсказка>».

        Сценарий (подслучай — свежая задача компонента `junit-xml`): (1)
        файл планки без строки группы — «переход отклонён: группы
        приёмочных тестов»; (2) свой файл `tests/` с группой «разовый» —
        «переход отклонён: долгоживущие файлы tests/»; (3) шпион отвечает
        кодом 128 на `git` из кода гейтов `tests_writing` — «… — git не
        ответил». Деталь каждой записи содержит «\\nдальше: » с непустой
        подсказкой.

        Ловит мутацию: правка переноса 15 убрала подсказку из детали у всех
        отказов `tests_writing` (а не только у FAIL_TO_PASS) — деталь без
        «\\nдальше:», бриф test_author без подсказки.
        """
        def groups(t, n):
            self.write_plank(t, {f"test_{self.word()}.py": self.py_plank(
                (n,)).replace("Группа: разовый\n", "")})
            return TEST_GROUPS_ACTION

        def long_lived(t, n):
            self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
            self.write_code(t, f"tests/test_{t.low}_{self.word()}.py",
                            self.long_py(n).replace("Группа: долгоживущий",
                                                    "Группа: разовый"))
            return LONG_LIVED_ACTION

        def git_failure(t, n):
            self.write_plank(t, {f"test_{self.word()}.py": self.py_plank((n,))})
            self.git_break = "всегда"
            return LONG_LIVED_GIT_ACTION

        for label, arrange in (("группы", groups), ("долгоживущие", long_lived),
                               ("git", git_failure)):
            with self.subTest(case=label, seed=self.seed):
                n = self.numbers(1)[0]
                t = self.new_task(self.junit_project(), (n,))
                action = arrange(t, n)
                try:
                    detail, rows, output = self.refusal(t, action)
                finally:
                    self.git_break = None
                self.assertRegex(detail, rf"\n{NEXT} \S",
                                 self.explain(rows, output))


if __name__ == "__main__":
    unittest.main()
