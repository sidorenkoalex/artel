"""Vitest 4 под пультом: флаг кэша `--no-cache`, хуки, `.only` и класс ошибки в отчётчике `pult-vitest`, «expected fail» итоговой строки, номер повтора `#1` у имени на `#<цифры>`.

Группа: долгоживущий
Красен до реализации: у Vitest 4 в таблице флаг `--cacheDir` и пульт заводит каталог кэша; отчётчик ищет упавший хук только по `"fail"`, не читает хуки и ошибки набора и модуля, берёт класс ошибки только из `name` и пишет `.only` как `run`/пропуск; `_VITEST_COUNTS` не знает «expected fail»; `test_id` не дописывает `#1` имени на `#<цифры>`, и гейты считают повтором любой номер — тесты AC-2, AC-4–AC-8, AC-10–AC-15 падают на этих местах; AC-1 падает на значении флага; AC-3 и AC-9 держат прежнее поведение и зелены и на базе.

Отчётчик исполняется настоящим `node` из `PATH` (нет `node` — тест
падает с текстом причины): копия `orchestrator/reporters/
pult_vitest_reporter.js` с расширением `.mjs` во временном каталоге и
рядом обвязка `.mjs`, которая строит поддельные `TestModule`/`TestSuite`/
`TestCase` формы Vitest 4.1.5 по сценарию JSON, вызывает `onInit`/
`onTestRunEnd` и пишет отчёт по `PULT_VITEST_REPORT` (или по
`outputFile`). Каждый вызов `node` — с пределом времени.

Флаг кэша (AC-2, AC-3) держит связка «запись проекта — профиль —
подготовка прогона — подменённый раннер» песочницы
`tests/report_outcome_sandbox.py::ReportSandbox`; гейт планки (AC-15) —
связка «SPEC — черновик планки — чекпоинт — FSM — отчёт раннера» песочницы
`FailToPassSandbox` долгоживущего файла честного `FAIL_TO_PASS`.
Итоговая строка и идентификаторы (AC-11–AC-14) — чистые функции, без
песочницы.

Имена тестов, файлов, компонентов и порядок записей — из `random`; зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
запись `--no-cache` и `_vitest_head` без каталога кэша, «expected fail» в
`_VITEST_COUNTS`, `#1` в `test_id`, повтор от 2 в `not_passed_kind` и сборе
`repeats`, отчётчик по правилам а)–е2) — все 64 теста файла зелёные.
"""
import dataclasses
import json
import os
import random
import shutil
import string
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import config, project_profile
from orchestrator.advance_gates.acceptance import not_passed_kind
from orchestrator.agent_log import vitest_summaries
from orchestrator.reporters import outcome
from tests.fixtures import _sandbox
from tests.report_outcome_sandbox import (REQUIRE_ASSERTIONS, VITEST_BASE,
                                          ReportSandbox, under, vitest_report,
                                          vitest_test)

NODE_LIMIT_SEC = 60
REPORT_ENV = "PULT_VITEST_REPORT"
FILE_LEVEL_NAME = "<ошибка уровня файла>"
REPEAT_KIND = "повтор имени теста в файле"
REPEAT_FINDING = "повтор имени теста в файле: "
ONLY_MESSAGE = ("[Vitest] Unexpected .only modifier. Remove it or pass "
                "--allowOnly argument to bypass this error")
FAILURE_ERRORS = ("AssertionError", "TestingLibraryElementError",
                  "JestExtendError", "HtmlElementTypeError")
SEP = " > "

# Обвязка: поддельные объекты API отчётчиков Vitest 4.1.5 по сценарию.
HARNESS = r"""import fs from "node:fs";
import path from "node:path";
import Reporter from "./reporter.mjs";

const scenario = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

function collection(kids) {
  return {
    *allTests() {
      for (const child of kids) {
        if (child.type === "test") {
          yield child;
        } else {
          yield* child.children.allTests();
        }
      }
    },
    array() {
      return [...kids];
    },
    [Symbol.iterator]() {
      return kids[Symbol.iterator]();
    },
  };
}

function taskOf(spec) {
  return {result: spec.hooks ? {hooks: spec.hooks} : {}};
}

function build(spec, parent, mod) {
  if (spec.type === "suite") {
    const kids = [];
    const suite = {
      type: "suite", name: spec.name, parent, module: mod,
      options: {mode: spec.mode || "run"}, task: taskOf(spec),
      errors: () => spec.errors || [], children: collection(kids),
    };
    for (const child of spec.children || []) {
      kids.push(build(child, suite, mod));
    }
    return suite;
  }
  return {
    type: "test", name: spec.name, parent, module: mod,
    options: {mode: spec.mode || "run", fails: Boolean(spec.fails)},
    task: taskOf(spec),
    result: () => ({state: spec.state, errors: spec.errors}),
    diagnostic: () => ({retryCount: spec.retryCount || 0,
                        duration: spec.duration}),
  };
}

const modules = scenario.modules.map((spec) => {
  const kids = [];
  const mod = {
    type: "module", moduleId: path.join(process.cwd(), spec.file),
    task: taskOf(spec), errors: () => spec.errors || [],
    children: collection(kids),
  };
  mod.module = mod;
  for (const child of spec.children || []) {
    kids.push(build(child, mod, mod));
  }
  return mod;
});

const reporter = new Reporter();
reporter.onInit({config: {outputFile: scenario.outputFile}});
await reporter.onTestRunEnd(modules, [], "failed");
"""


class Inputs:
    """Случайные входы теста с напечатанным зерном."""

    def __init__(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(string.ascii_lowercase)
                           for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"


@pytest.fixture
def inputs():
    yield Inputs()


@pytest.fixture
def harness(tmp_path):
    """Каталог с копией отчётчика `.mjs` и обвязкой `.mjs` рядом."""
    root = tmp_path.resolve()
    shutil.copyfile(outcome.VITEST_REPORTER, root / "reporter.mjs")
    (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
    yield root


@pytest.fixture
def box():
    yield from _sandbox(ReportSandbox)


@pytest.fixture
def fail_to_pass():
    from tests.test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass import \
        FailToPassSandbox
    yield from _sandbox(FailToPassSandbox)


# --- сценарии обвязки ------------------------------------------------------

def case(name: str, state: str = "passed", *, errors=None, hooks=None,
         mode: str = "run", fails: bool = False, retry: int = 0,
         duration: int = 5) -> dict:
    spec = {"type": "test", "name": name, "state": state, "mode": mode,
            "fails": fails, "retryCount": retry, "duration": duration}
    if errors is not None:
        spec["errors"] = errors
    if hooks is not None:
        spec["hooks"] = hooks
    return spec


def suite(name: str, children, *, hooks=None, errors=None,
          mode: str = "run") -> dict:
    spec = {"type": "suite", "name": name, "mode": mode,
            "children": list(children)}
    if errors is not None:
        spec["errors"] = errors
    if hooks is not None:
        spec["hooks"] = hooks
    return spec


def module(file: str, children, *, hooks=None, errors=None) -> dict:
    spec = {"file": file, "children": list(children)}
    if errors is not None:
        spec["errors"] = errors
    if hooks is not None:
        spec["hooks"] = hooks
    return spec


def error(name, message: str, ctor: str | None = None) -> dict:
    """Сериализованная ошибка Vitest: `ctor` — собственное поле
    `constructor` вида `Function<Имя>`."""
    found = {"message": message}
    if name is not None:
        found["name"] = name
    if ctor is not None:
        found["constructor"] = ctor
    return found


def run_reporter(root: Path, modules, inputs: Inputs, *, via_env: bool = True,
                 output_file=None) -> list:
    """Записи отчёта, который отчётчик пульта под настоящим `node` пишет по
    сценарию `modules`: путь — `PULT_VITEST_REPORT` (`via_env`), иначе
    `outputFile` контекста `onInit`."""
    node = shutil.which("node")
    assert node, inputs.note(
        "node не найден в PATH — отчётчик pult-vitest исполнить нечем; "
        "поставь Node.js (>= 18) в PATH прогона тестов")
    scenario = root / "scenario.json"
    scenario.write_text(json.dumps({"modules": list(modules),
                                    "outputFile": output_file}),
                        encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != REPORT_ENV}
    report = root / f"out{inputs.word(4)}" / "report.json"
    if via_env:
        env[REPORT_ENV] = str(report)
    proc = subprocess.run([node, str(root / "harness.mjs"), str(scenario)],
                          cwd=root, env=env, capture_output=True, text=True,
                          timeout=NODE_LIMIT_SEC, check=False)
    assert proc.returncode == 0, inputs.note(
        f"node завершился с кодом {proc.returncode}:\n{proc.stdout}\n"
        f"{proc.stderr}")
    target = report if via_env else Path(_output_path(output_file))
    assert target.is_file(), inputs.note(
        f"отчёт {target} не записан; вывод node:\n{proc.stdout}\n"
        f"{proc.stderr}")
    return json.loads(target.read_text(encoding="utf-8"))["tests"]


def _output_path(output_file) -> str:
    if isinstance(output_file, dict):
        return next(iter(output_file.values()))
    return output_file


def by_name(records: list, name: str, inputs: Inputs) -> dict:
    found = [r for r in records if r.get("name") == name]
    assert len(found) == 1, inputs.note(
        f"записи «{name}» нет или не одна: {records}")
    return found[0]


def picked(record: dict, keys) -> dict:
    return {key: record.get(key) for key in keys}


# --- AC-1 -----------------------------------------------------------------

def test_ac1_vitest4_entry_no_cache_flag_and_form():
    """Запись таблицы для Vitest 4 — `VitestFlags("--no-cache", True, <проба>)`, форма записи прежняя.

    Сценарий: читается `VITEST_VERSION_FLAGS[4]`, поля класса `VitestFlags`
    и ответ `vitest_flags(4)`.

    Ловит мутацию: в таблице остался `--cacheDir` (или флаг с `=`); у
    записи пустая строка пробы; поля переставлены или переименованы —
    `cache_flag` уже не первое поле; `vitest_flags(4)` возвращает другую
    запись.
    """
    entry = project_profile.VITEST_VERSION_FLAGS[4]
    assert isinstance(entry, project_profile.VitestFlags), repr(entry)
    assert entry.cache_flag == "--no-cache", repr(entry)
    assert entry.require_assertions is True, repr(entry)
    assert isinstance(entry.probe, str) and entry.probe.strip(), repr(entry)
    names = [f.name for f in dataclasses.fields(project_profile.VitestFlags)]
    assert names[:3] == ["cache_flag", "require_assertions", "probe"], names
    assert project_profile.vitest_flags(4) is entry


# --- AC-2 -----------------------------------------------------------------

@pytest.mark.parametrize("workdir", [True, False])
def test_ac2_no_cache_right_after_require_assertions_without_cache_dir(box,
                                                                       workdir):
    """Компонент `pult-vitest` с Vitest 4 запускается с `--no-cache` сразу после `--expect.requireAssertions`, без `--cacheDir` и без каталога кэша пульта.

    Сценарий: учебный проект с компонентом `pult-vitest` (с `workdir` и в
    корне), версия Vitest 4.x из `tools`, подменённый раннер пишет
    зелёный отчёт. Прогон зелёный; argv раннера: базовый, затем
    `--expect.requireAssertions`, затем ровно `--no-cache`; ни один
    аргумент не начинается с `--cacheDir` и не указывает в каталог кэша
    пульта проекта; каталог `<проекты>/<проект>/cache/<компонент>/vitest`
    не создан.

    Ловит мутацию: флаг склеивается с каталогом (`--no-cache=<путь>`) —
    аргумент после `--expect.requireAssertions` не равен `--no-cache`;
    каталог кэша по-прежнему заводится — он есть на диске; флаг пропал —
    после `--expect.requireAssertions` идут `report_args`.
    """
    case_ = box.vitest_component(workdir=workdir, version=box.version(4))
    case_["fake"].scenario(
        version_out=f"vitest/{case_['version']} linux-x64 node-v22.11.0",
        report=vitest_report([vitest_test("src/a.test.js", "ok")]))
    run, out = box.full(case_["clone"], case_["task"], case_["profile"])
    assert run.green, box.note(f"{run}\n{out}")
    args = case_["fake"].runs()[-1]["args"]
    head = [*VITEST_BASE[1:], REQUIRE_ASSERTIONS]
    assert args[:len(head)] == head, box.note(str(args))
    assert args[len(head)] == "--no-cache", box.note(str(args))
    assert not [a for a in args if a.startswith("--cacheDir")], (
        box.note(str(args)))
    profile = case_["profile"]
    cache_root = config.PROJECTS / profile.project / "cache"
    assert not [a for a in args if under(a.split("=", 1)[-1], cache_root)], (
        box.note(f"аргумент указывает в каталог кэша {cache_root}: {args}"))
    cache_dir = cache_root / profile.component / "vitest"
    assert not cache_dir.exists(), box.note(f"каталог кэша заведён: {cache_dir}")


# --- AC-3 -----------------------------------------------------------------

@pytest.mark.parametrize("in_table", [False, True])
def test_ac3_version_refusals_keep_texts(box, in_table):
    """Версия вне таблицы и версия без `--expect.requireAssertions` — отказ подготовки прежним текстом, раннер не запускался.

    Сценарий: (а) компонент объявляет главную версию, которой в таблице
    нет; (б) таблица подменена копией с новой главной версией, запись
    которой — запись Vitest 4 с `require_assertions=False`. Итог не
    зелёный, деталь несёт прежний текст отказа, вызова `run` раннера нет.

    Ловит мутацию: правка флага кэша задела отказы — версия вне таблицы
    получает флаг по умолчанию и прогон идёт; проверка
    `require_assertions` снята или переставлена после флага кэша; текст
    отказа переписан.
    """
    major = box.absent_major()
    version = box.version(major)
    if in_table:
        patched = dict(project_profile.VITEST_VERSION_FLAGS)
        patched[major] = dataclasses.replace(
            project_profile.VITEST_VERSION_FLAGS[4], require_assertions=False)
        expected = (f"Vitest {version} не принимает {REQUIRE_ASSERTIONS} — "
                    f"без него прогон компонента не исполняется")
        with mock.patch.object(project_profile, "VITEST_VERSION_FLAGS",
                               patched):
            case_ = box.vitest_component(version=version)
            run, out = box.full(case_["clone"], case_["task"], case_["profile"])
    else:
        expected = (f"Vitest {version}: флаг кэша для главной версии {major} "
                    f"не подтверждён (её нет в "
                    f"project_profile.VITEST_VERSION_FLAGS) — прогон не "
                    f"запускался")
        case_ = box.vitest_component(version=version)
        run, out = box.full(case_["clone"], case_["task"], case_["profile"])
    assert not run.green, box.note(f"{run}\n{out}")
    assert expected in run.detail, box.note(run.detail)
    assert case_["fake"].runs() == [], box.note("прогон шёл")


# --- AC-4 -----------------------------------------------------------------

@pytest.mark.parametrize("err, expected", [
    ({"name": "AssertionError", "message": "expected 1 to be 2"},
     "AssertionError"),
    ({"name": "Error", "message": "Expected element to have text content",
      "constructor": "Function<JestExtendError>"}, "JestExtendError"),
    ({"name": "Error", "message": "received value must be an HTMLElement",
      "constructor": "Function<HtmlElementTypeError>"},
     "HtmlElementTypeError"),
    ({"name": "TestingLibraryElementError",
      "message": "Unable to find an element with the text",
      "constructor": "Function<Error>"}, "TestingLibraryElementError"),
    ({"name": "TypeError", "message": "Cannot read properties of null",
      "constructor": "Function<TypeError>"}, "TypeError"),
    ({"name": "Error", "message": "boom",
      "constructor": "Function<anonymous>"}, "Error"),
])
def test_ac4_error_class_from_constructor_then_name(harness, inputs, err,
                                                    expected):
    """Класс ошибки упавшего теста — из собственного `constructor` вида `Function<Имя>`, кроме `Error`/`anonymous`, иначе из `name`.

    Сценарий: модуль со случайным числом прошедших соседей и одним упавшим
    тестом с сериализованной ошибкой варианта; отчётчик под `node`. У
    записи упавшего теста `state: "fail"` и `error_name` варианта.

    Ловит мутацию: класс только из `name` — у `JestExtendError` и
    `HtmlElementTypeError` записано `Error`; класс только из
    `constructor` — у `TestingLibraryElementError` записано `Error`, у
    `AssertionError` без `constructor` — `Object`/`null`; обобщённый
    `Error` или `anonymous` из `constructor` перекрывает `name`.
    """
    name = f"падает {inputs.word()}"
    children = [case(f"идёт {inputs.word()}")
                for _ in range(inputs.rng.randint(0, 3))]
    children.insert(inputs.rng.randint(0, len(children)),
                    case(name, "failed", errors=[err]))
    records = run_reporter(harness, [module(f"src/{inputs.word()}.test.js",
                                            children)], inputs)
    record = by_name(records, name, inputs)
    assert record["state"] == "fail", inputs.note(str(record))
    assert record["error_name"] == expected, inputs.note(str(record))


# --- AC-5 -----------------------------------------------------------------

@pytest.mark.parametrize("hooks, err, expected", [
    ({"beforeEach": "run"}, "AssertionError", "beforeEach"),
    ({"beforeEach": "pass", "afterEach": "run"}, "Error", "afterEach"),
    ({"beforeEach": "fail"}, "Error", "beforeEach"),
    ({"beforeEach": "pass", "afterEach": "pass"}, "AssertionError", None),
])
def test_ac5_test_hook_failed_by_run_or_fail(harness, inputs, hooks, err,
                                             expected):
    """Хук теста считается упавшим по `"run"` (Vitest 4) или `"fail"`; `"pass"` — не упавший.

    Сценарий: упавший тест в наборе со случайным именем, состояние хуков
    теста в `task.result.hooks` — вариант; отчётчик под `node`. Поле
    `hook` записи — ожидаемое имя хука либо `null`.

    Ловит мутацию: признак падения только `"fail"` — у `{"beforeEach":
    "run"}` записан `hook: null`; `"pass"` считается падением — у
    прошедших хуков записан `beforeEach`; `afterEach` проверяется раньше
    `beforeEach` либо не проверяется вовсе.
    """
    group, name = f"набор {inputs.word()}", f"тест {inputs.word()}"
    mod = module(f"src/{inputs.word()}.test.js", [suite(group, [
        case(name, "failed", errors=[error(err, "boom")], hooks=hooks)])])
    record = by_name(run_reporter(harness, [mod], inputs),
                     f"{group}{SEP}{name}", inputs)
    assert record["state"] == "fail", inputs.note(str(record))
    assert record["hook"] == expected, inputs.note(str(record))


# --- AC-6 -----------------------------------------------------------------

@pytest.mark.parametrize("depth, err, expected", [
    (1, {"name": "TypeError", "message": "Cannot read properties of null",
         "constructor": "Function<TypeError>"}, "TypeError"),
    (2, {"name": "TypeError", "message": "Cannot read properties of null",
         "constructor": "Function<TypeError>"}, "TypeError"),
    (1, {"name": "Error", "message": "x is not a function",
         "constructor": "Function<TypeError>"}, "TypeError"),
    (2, {"name": "Error", "message": "x is not a function",
         "constructor": "Function<TypeError>"}, "TypeError"),
])
def test_ac6_suite_before_all_fails_skipped_tests(harness, inputs, depth, err,
                                                  expected):
    """Тест без своей ошибки под набором с упавшим `beforeAll` (и под вложенным в него набором) — провал с хуком `beforeAll` и классом ошибки набора.

    Сценарий: набор с `{"beforeAll": "run"}` и ошибкой варианта; тест —
    `skipped` без ошибок прямо в наборе (глубина 1) или во вложенном
    наборе без своих ошибок (глубина 2). Запись: `state: "fail"`, `hook:
    "beforeAll"`, `error_name` — класс по правилу `constructor`/`name`.

    Ловит мутацию: ошибки набора не читаются — тест записан `skip`;
    смотрится только непосредственный родитель — тест вложенного набора
    `skip`; класс ошибки хука набора берётся только из `name` — `Error`
    вместо `TypeError`.
    """
    outer, name = f"внешний {inputs.word()}", f"тест {inputs.word()}"
    leaf = case(name, "skipped")
    full = f"{outer}{SEP}{name}"
    if depth == 2:
        inner = f"вложенный {inputs.word()}"
        leaf = suite(inner, [leaf])
        full = f"{outer}{SEP}{inner}{SEP}{name}"
    mod = module(f"src/{inputs.word()}.test.js", [
        suite(outer, [leaf], hooks={"beforeAll": "run"}, errors=[err]),
        case(f"рядом {inputs.word()}")])
    record = by_name(run_reporter(harness, [mod], inputs), full, inputs)
    assert picked(record, ("state", "hook", "error_name")) == {
        "state": "fail", "hook": "beforeAll", "error_name": expected}, (
        inputs.note(str(record)))


def test_ac6_module_before_all_goes_to_tests_not_file_level(harness, inputs):
    """Упавший `beforeAll` верхнего уровня модуля — записи тестов с хуком `beforeAll`, записи уровня файла нет.

    Сценарий: модуль с `{"beforeAll": "run"}` и ошибкой `TypeError`, тесты
    `skipped` без ошибок — верхнего уровня и в наборе (число случайно).
    Каждая запись теста — `fail`, `beforeAll`, `TypeError`; записи с
    `file_level` в отчёте нет.

    Ловит мутацию: хук модуля превращается в ошибку уровня файла — в
    отчёте запись `<ошибка уровня файла>`, тесты `skip`; правило б) не
    поднимается до модуля — тесты `skip`.
    """
    top = [case(f"верх {inputs.word()}", "skipped")
           for _ in range(inputs.rng.randint(1, 3))]
    group = f"набор {inputs.word()}"
    nested = [case(f"в наборе {inputs.word()}", "skipped")
              for _ in range(inputs.rng.randint(1, 2))]
    mod = module(f"src/{inputs.word()}.test.js",
                 top + [suite(group, nested)], hooks={"beforeAll": "run"},
                 errors=[error("TypeError", "Cannot read properties of null",
                               "Function<TypeError>")])
    records = run_reporter(harness, [mod], inputs)
    assert not [r for r in records if r.get("file_level")], (
        inputs.note(str(records)))
    names = ([t["name"] for t in top]
             + [f"{group}{SEP}{t['name']}" for t in nested])
    for name in names:
        record = by_name(records, name, inputs)
        assert picked(record, ("state", "hook", "error_name")) == {
            "state": "fail", "hook": "beforeAll", "error_name": "TypeError"}, (
            inputs.note(str(record)))


@pytest.mark.parametrize("err, expected", [
    ({"name": "RangeError", "message": "Invalid array length",
      "constructor": "Function<RangeError>"}, "RangeError"),
    ({"name": "Error", "message": "Invalid array length",
      "constructor": "Function<RangeError>"}, "RangeError"),
    ({"name": "RangeError", "message": "Invalid array length"}, "RangeError"),
])
def test_ac6_collection_error_without_hooks_stays_file_level(harness, inputs,
                                                             err, expected):
    """Ошибка сбора модуля без хуков — прежняя запись уровня файла.

    Сценарий: модуль без тестов и без хуков, `errors()` — ошибка сбора
    варианта. В отчёте ровно запись уровня файла прежней формы: путь,
    `<ошибка уровня файла>`, `state: "fail"`, `file_level: true`, класс
    ошибки, сообщение.

    Ловит мутацию: правило хука модуля съедает ошибку сбора — записи
    уровня файла нет; запись уровня файла получает новые поля или теряет
    сообщение; класс ошибки уровня файла только из `name` — `Error`
    вместо `RangeError`.
    """
    file = f"src/{inputs.word()}.test.js"
    records = run_reporter(harness, [module(file, [], errors=[err])], inputs)
    assert records == [{"file": file, "name": FILE_LEVEL_NAME, "state": "fail",
                        "file_level": True, "error_name": expected,
                        "error_message": err["message"]}], (
        inputs.note(str(records)))


@pytest.mark.parametrize("variant, mode", [
    ("хук набора без ошибок", "run"),
    ("it.skip под упавшим beforeAll", "skip"),
    ("ctx.skip в beforeEach", "run"),
])
def test_ac6_skips_stay_skip_without_hook(harness, inputs, variant, mode):
    """Пропуск остаётся пропуском без хука: хук набора без ошибок, явный `it.skip` под упавшим `beforeAll`, `ctx.skip()` в `beforeEach`.

    Сценарий: тест `skipped` без ошибок (а) в наборе с `{"beforeAll":
    "run"}` и пустым `errors()`; (б) с `options.mode: "skip"` в наборе с
    упавшим `beforeAll` и ошибкой; (в) с `{"beforeEach": "run"}` у самого
    теста. Запись: `state: "skip"`, `mode` варианта, `hook: null`,
    `error_name: null`.

    Ловит мутацию: хук без ошибок засчитан падением — (а) `fail`;
    правило б) перекрывает явный пропуск — (б) `fail`; хук пишется в
    запись пропуска — (в) `hook: "beforeEach"`.
    """
    group, name = f"набор {inputs.word()}", f"тест {inputs.word()}"
    failing = [error("TypeError", "Cannot read properties of null",
                     "Function<TypeError>")]
    if variant == "хук набора без ошибок":
        node = suite(group, [case(name, "skipped")],
                     hooks={"beforeAll": "run"}, errors=[])
    elif variant == "it.skip под упавшим beforeAll":
        node = suite(group, [case(name, "skipped", mode="skip")],
                     hooks={"beforeAll": "run"}, errors=failing)
    else:
        node = suite(group, [case(name, "skipped",
                                  hooks={"beforeEach": "run"})])
    mod = module(f"src/{inputs.word()}.test.js", [node])
    record = by_name(run_reporter(harness, [mod], inputs),
                     f"{group}{SEP}{name}", inputs)
    assert picked(record, ("state", "mode", "hook", "error_name")) == {
        "state": "skip", "mode": mode, "hook": None, "error_name": None}, (
        inputs.note(f"{variant}: {record}"))


# --- AC-7 -----------------------------------------------------------------

def test_ac7_after_all_fails_passed_keeps_honest_failure_and_skip(harness,
                                                                  inputs,
                                                                  tmp_path):
    """Упавший `afterAll` набора: прошедший тест — провал с хуком `afterAll`, честный провал остаётся провалом проверки, `it.skip` — пропуском.

    Сценарий: набор с `{"afterAll": "run"}` и ошибкой `Error`; в нём в
    случайном порядке прошедший тест, тест с собственным `AssertionError`
    и `it.skip`. Записи: `fail`/`afterAll`; `fail`/`hook: null`/
    `AssertionError`, и разборщик `parse_vitest` с `failure_errors`
    `AssertionError` даёт ему `FAILED`; `skip`.

    Ловит мутацию: `afterAll` не учтён — прошедший тест записан `pass`;
    правило б) перекрывает честный провал ошибкой хука — у
    `AssertionError` записан `hook: "afterAll"` и разборщик даёт `ERROR`;
    явный пропуск становится провалом.
    """
    group = f"набор {inputs.word()}"
    passed, honest, skipped = (f"идёт {inputs.word()}",
                               f"падает {inputs.word()}",
                               f"пропуск {inputs.word()}")
    kids = [case(passed),
            case(honest, "failed",
                 errors=[error("AssertionError", "expected 1 to be 2")]),
            case(skipped, "skipped", mode="skip")]
    inputs.rng.shuffle(kids)
    file = f"src/{inputs.word()}.test.js"
    mod = module(file, [suite(group, kids, hooks={"afterAll": "run"},
                              errors=[error("Error", "after all boom")])])
    records = run_reporter(harness, [mod], inputs)
    got = {name: by_name(records, f"{group}{SEP}{name}", inputs)
           for name in (passed, honest, skipped)}
    assert picked(got[passed], ("state", "hook")) == {
        "state": "fail", "hook": "afterAll"}, inputs.note(str(got[passed]))
    assert picked(got[honest], ("state", "hook", "error_name")) == {
        "state": "fail", "hook": None, "error_name": "AssertionError"}, (
        inputs.note(str(got[honest])))
    assert got[skipped]["state"] == "skip", inputs.note(str(got[skipped]))
    report = tmp_path / "parsed.json"
    report.write_text(json.dumps({"tests": records}), encoding="utf-8")
    comp = f"c{inputs.word()}"
    parsed, reason = outcome.parse_vitest(report, comp, "",
                                          failure_errors=("AssertionError",))
    assert parsed is not None, inputs.note(reason)
    honest_id = project_profile.test_id(comp, file, f"{group}{SEP}{honest}")
    found = [r for r in parsed if r.id == honest_id]
    assert [r.outcome for r in found] == [outcome.FAILED], (
        inputs.note(str(parsed)))


# --- AC-8 -----------------------------------------------------------------

def test_ac8_only_error_marks_mode_only_up_the_chain(harness, inputs):
    """Ошибка `.only` у самого теста или у набора-предка (через вложенный набор) — `mode: "only"`, `fail`; сосед, пропущенный из-за `.only`, — `skip`/`skip`.

    Сценарий: модуль, в котором в случайном порядке: тест с собственной
    ошибкой `[Vitest] Unexpected .only modifier`; набор с такой ошибкой и
    `skipped`-тестом в нём; тот же набор с вложенным набором без ошибок и
    `skipped`-тестом в нём; сосед `skipped` с `options.mode: "skip"`.

    Ловит мутацию: `mode` берётся только из `options.mode` — у тестов с
    `.only` записано `run`; все пропущенные засчитаны `only` — сосед
    записан `only`/`fail`; смотрится только непосредственный родитель —
    тест вложенного набора записан `skip`.
    """
    own, group, inner = (f"свой {inputs.word()}", f"набор {inputs.word()}",
                         f"вложенный {inputs.word()}")
    in_group, in_inner, neighbour = (f"в наборе {inputs.word()}",
                                     f"глубже {inputs.word()}",
                                     f"сосед {inputs.word()}")
    only_own = error("Error", ONLY_MESSAGE, "Function<Error>")
    only_suite = error("Error", ONLY_MESSAGE)
    kids = [case(own, "failed", errors=[only_own]),
            suite(group, [case(in_group, "skipped"),
                          suite(inner, [case(in_inner, "skipped")])],
                  errors=[only_suite]),
            case(neighbour, "skipped", mode="skip")]
    inputs.rng.shuffle(kids)
    records = run_reporter(harness, [module(f"src/{inputs.word()}.test.js",
                                            kids)], inputs)
    expected = {own: {"mode": "only", "state": "fail"},
                f"{group}{SEP}{in_group}": {"mode": "only", "state": "fail"},
                f"{group}{SEP}{inner}{SEP}{in_inner}": {"mode": "only",
                                                       "state": "fail"},
                neighbour: {"mode": "skip", "state": "skip"}}
    got = {name: picked(by_name(records, name, inputs), ("mode", "state"))
           for name in expected}
    assert got == expected, inputs.note(str(records))


# --- AC-9 -----------------------------------------------------------------

@pytest.mark.parametrize("spec, expected", [
    ({"state": "passed", "hooks": {"beforeEach": "pass", "afterEach": "pass"},
      "duration": 7},
     {"state": "pass", "mode": "run", "fails": False, "retry_count": 0,
      "error_name": None, "timeout": False, "hook": None, "duration_ms": 7}),
    ({"state": "skipped", "mode": "todo", "duration": 0},
     {"state": "todo", "mode": "todo", "fails": False, "retry_count": 0,
      "error_name": None, "timeout": False, "hook": None, "duration_ms": 0}),
    ({"state": "skipped", "mode": "skip", "duration": 0},
     {"state": "skip", "mode": "skip", "fails": False, "retry_count": 0,
      "error_name": None, "timeout": False, "hook": None, "duration_ms": 0}),
    ({"state": "passed", "fails": True, "duration": 3},
     {"state": "pass", "mode": "run", "fails": True, "retry_count": 0,
      "error_name": None, "timeout": False, "hook": None, "duration_ms": 3}),
    ({"state": "failed", "fails": True, "duration": 4,
      "errors": [{"name": "Error", "message": "Expect test to fail"}]},
     {"state": "fail", "mode": "run", "fails": True, "retry_count": 0,
      "error_name": "Error", "timeout": False, "hook": None,
      "duration_ms": 4}),
    ({"state": "passed", "retryCount": 2, "duration": 9},
     {"state": "pass", "mode": "run", "fails": False, "retry_count": 2,
      "error_name": None, "timeout": False, "hook": None, "duration_ms": 9}),
])
def test_ac9_ordinary_records_unchanged(harness, inputs, spec, expected):
    """Записи зелёного теста, `todo`, `skip`, `it.fails` (тело упало и прошло) и теста с повторами — прежние литералы.

    Сценарий: тест варианта в наборе с прошедшими хуками набора
    (`{"beforeAll": "pass", "afterAll": "pass"}`, пустой `errors()`);
    отчётчик под `node`. Запись совпадает с литералом прежней формы
    целиком (путь и полное имя — от сценария).

    Ловит мутацию: правило хуков задевает обычные состояния — прошедший
    хук набора делает тест `fail`; правило `.only` переписывает `mode`
    пропуска; `hook` пишется в запись прошедшего теста; в записи появилось
    новое поле или пропало `retry_count`.
    """
    group, name = f"набор {inputs.word()}", f"тест {inputs.word()}"
    file = f"src/{inputs.word()}.test.js"
    leaf = dict(case(name), **spec)
    mod = module(file, [suite(group, [leaf],
                              hooks={"beforeAll": "pass", "afterAll": "pass"},
                              errors=[])])
    record = by_name(run_reporter(harness, [mod], inputs),
                     f"{group}{SEP}{name}", inputs)
    assert record == {"file": file, "name": f"{group}{SEP}{name}",
                      **expected}, inputs.note(str(record))


@pytest.mark.parametrize("as_mapping", [False, True])
def test_ac9_output_file_without_env(harness, inputs, as_mapping):
    """Без `PULT_VITEST_REPORT` отчёт пишется по `outputFile` контекста (строкой и отображением), запись прежняя.

    Сценарий: переменная `PULT_VITEST_REPORT` снята из окружения `node`,
    `ctx.config.outputFile` — путь строкой либо `{"pult": путь}`. Файл по
    этому пути записан, запись зелёного теста — прежний литерал.

    Ловит мутацию: путь вывода читается только из переменной — отчёта по
    `outputFile` нет; правка правил задела запись зелёного теста.
    """
    name, file = f"тест {inputs.word()}", f"src/{inputs.word()}.test.js"
    target = str(harness / f"o{inputs.word()}" / "report.json")
    output = {"pult": target} if as_mapping else target
    records = run_reporter(harness, [module(file, [case(name, duration=2)])],
                           inputs, via_env=False, output_file=output)
    assert records == [{"file": file, "name": name, "state": "pass",
                        "mode": "run", "fails": False, "retry_count": 0,
                        "error_name": None, "timeout": False, "hook": None,
                        "duration_ms": 2}], inputs.note(str(records))


# --- AC-10 ----------------------------------------------------------------

def test_ac10_table_end_to_end_with_parse_vitest(harness, inputs, tmp_path):
    """Отчёт обвязки по таблице случаев требования 2 через `parse_vitest`: `FAILED` у провалов проверки без хука, `ERROR` у хуков, `.only`, `TypeError` и таймаута.

    Сценарий: три модуля — (1) случаи теста и наборов таблицы в случайном
    порядке; (2) модуль с упавшим `beforeAll` верхнего уровня; (3) модуль с
    ошибкой сбора. Отчёт отчётчика под `node` передаётся в
    `outcome.parse_vitest(…, failure_errors=(AssertionError,
    TestingLibraryElementError, JestExtendError, HtmlElementTypeError))`;
    исход каждой записи — по таблице.

    Ловит мутацию: класс ошибки теряется между отчётчиком и разборщиком —
    `JestExtendError`/`HtmlElementTypeError` приходят как `Error` и дают
    `ERROR`; хук теряется — `expect` в `beforeEach` даёт `FAILED`; упавший
    `beforeAll` набора или модуля даёт `SKIPPED`; `.only` даёт `ERROR`
    только у `it.only`, а тест `describe.only` — `SKIPPED`.
    """
    w = inputs.word
    assertion = error("AssertionError", "expected 1 to be 2")
    type_error = error("TypeError", "Cannot read properties of null",
                       "Function<TypeError>")
    only = error("Error", ONLY_MESSAGE, "Function<Error>")
    names = {key: f"{key} {w()}" for key in (
        "assert", "jest_text", "jest_dom", "get_by_text", "null_x",
        "before_each", "after_each", "body_after_each", "hook_timeout",
        "it_only", "ctx_skip", "fails_body", "after_all", "before_all",
        "outer", "inner", "describe_only", "top")}
    n = {key: f"тест {w()}" for key in (
        "honest", "passed", "explicit_skip", "under", "nested", "in_only",
        "top")}
    first = [
        case(names["assert"], "failed", errors=[assertion]),
        case(names["jest_text"], "failed", errors=[error(
            "Error", "Expected element to have text content",
            "Function<JestExtendError>")]),
        case(names["jest_dom"], "failed", errors=[error(
            "Error", "received value must be an HTMLElement",
            "Function<HtmlElementTypeError>")]),
        case(names["get_by_text"], "failed", errors=[error(
            "TestingLibraryElementError", "Unable to find an element",
            "Function<Error>")]),
        case(names["null_x"], "failed", errors=[type_error]),
        case(names["before_each"], "failed", errors=[assertion],
             hooks={"beforeEach": "run"}),
        case(names["after_each"], "failed", errors=[error("Error", "boom")],
             hooks={"beforeEach": "pass", "afterEach": "run"}),
        case(names["body_after_each"], "failed",
             errors=[assertion, error("Error", "after each boom")],
             hooks={"afterEach": "run"}),
        case(names["hook_timeout"], "failed", errors=[error(
            "Error", "Hook timed out in 10000ms.")],
             hooks={"beforeEach": "run"}),
        case(names["it_only"], "failed", errors=[only]),
        case(names["ctx_skip"], "skipped", hooks={"beforeEach": "run"}),
        case(names["fails_body"], "passed", fails=True),
        suite(names["after_all"], [
            case(n["honest"], "failed", errors=[assertion]),
            case(n["passed"])], hooks={"afterAll": "run"},
            errors=[error("Error", "after all boom")]),
        suite(names["before_all"], [
            case(n["explicit_skip"], "skipped", mode="skip"),
            case(n["under"], "skipped")], hooks={"beforeAll": "run"},
            errors=[type_error]),
        suite(names["outer"], [suite(names["inner"], [
            case(n["nested"], "skipped")])], hooks={"beforeAll": "run"},
            errors=[type_error]),
        suite(names["describe_only"], [case(n["in_only"], "skipped")],
              errors=[error("Error", ONLY_MESSAGE)]),
    ]
    inputs.rng.shuffle(first)
    files = [f"src/{w()}.test.js" for _ in range(3)]
    modules = [module(files[0], first),
               module(files[1], [case(n["top"], "skipped")],
                      hooks={"beforeAll": "run"}, errors=[type_error]),
               module(files[2], [], errors=[error(
                   "RangeError", "Invalid array length",
                   "Function<RangeError>")])]
    records = run_reporter(harness, modules, inputs)
    report = tmp_path / "parsed.json"
    report.write_text(json.dumps({"tests": records}), encoding="utf-8")
    comp = f"c{w()}"
    parsed, reason = outcome.parse_vitest(report, comp, "",
                                          failure_errors=FAILURE_ERRORS)
    assert parsed is not None, inputs.note(reason)
    F, E, S, P = outcome.FAILED, outcome.ERROR, outcome.SKIPPED, outcome.PASSED
    expected = {
        (0, names["assert"]): F, (0, names["jest_text"]): F,
        (0, names["jest_dom"]): F, (0, names["get_by_text"]): F,
        (0, f"{names['after_all']}{SEP}{n['honest']}"): F,
        (0, names["null_x"]): E, (0, names["before_each"]): E,
        (0, names["after_each"]): E, (0, names["body_after_each"]): E,
        (0, names["hook_timeout"]): E, (0, names["it_only"]): E,
        (0, f"{names['after_all']}{SEP}{n['passed']}"): E,
        (0, f"{names['before_all']}{SEP}{n['under']}"): E,
        (0, f"{names['outer']}{SEP}{names['inner']}{SEP}{n['nested']}"): E,
        (0, f"{names['describe_only']}{SEP}{n['in_only']}"): E,
        (1, n["top"]): E,
        (2, FILE_LEVEL_NAME): E,
        (0, names["ctx_skip"]): S,
        (0, f"{names['before_all']}{SEP}{n['explicit_skip']}"): S,
        (0, names["fails_body"]): P,
    }
    by_id = {r.id: r for r in parsed}
    got = {key: getattr(by_id.get(project_profile.test_id(
        comp, files[key[0]], key[1])), "outcome", None) for key in expected}
    assert got == expected, inputs.note(
        f"исходы: {got}\nзаписи отчётчика: {records}")
    body_after_each = by_id[project_profile.test_id(
        comp, files[0], names["body_after_each"])]
    assert "падение хука afterEach" in body_after_each.failure, (
        inputs.note(str(body_after_each)))


# --- AC-11 ----------------------------------------------------------------

@pytest.mark.parametrize("lines, expected", [
    (["Test Files  2 failed | 1 passed (3)",
      "Tests  6 failed | 2 passed | 1 expected fail | 1 skipped | 1 todo (11)",
      "Start at  10:00:00", "Duration  1.94s (transform 120ms, setup 0ms)"],
     ["6 failed | 2 passed | 1 expected fail | 1 skipped | 1 todo (11) "
      "in 1.94s"]),
    (["Test Files  1 passed (1)", "Tests  1 expected fail | 3 passed (4)",
      "Duration  250ms"],
     ["1 expected fail | 3 passed (4) in 0.25s"]),
    (["Test Files  1 passed (1)", "Tests  3 passed | 2 expected fail (5)",
      "Duration  3.10s (transform 1ms)"],
     ["3 passed | 2 expected fail (5) in 3.10s"]),
    (["Test Files  1 failed | 1 passed (2)", "Tests  1 failed | 2 passed (3)",
      "Start at  10:00:00", "Duration  1.50s (transform 1ms)"],
     ["1 failed | 2 passed (3) in 1.50s"]),
    (["Tests  1 expected fail | 1 passed (2)", "Duration  1.00s"], []),
    (["Test Files  1 failed (1)", "Tests  1 failed | 2 bogus (3)",
      "Duration  1.00s"], []),
])
def test_ac11_summary_accepts_expected_fail_only(inputs, lines, expected):
    """Итоговый блок Vitest с «expected fail» в любой позиции ряда разбирается прежней деталью; без «Test Files» и с чужим счётчиком — не итог.

    Сценарий: блок варианта со случайным числом строк вывода до и после
    него, с отступами, как печатает Vitest. `vitest_summaries` даёт деталь
    «<счётчики Tests> (<n>) in <секунды>s» либо пустой список.

    Ловит мутацию: «expected fail» не принят — блоки 1–3 дают `[]`;
    принят любой текст между `|` — блок с `2 bogus` даёт деталь; строка
    «Tests» без «Test Files» засчитана итогом.
    """
    before = [f"✓ src/{inputs.word()}.test.js (1 test) 3ms"
              for _ in range(inputs.rng.randint(0, 3))]
    after = [f"note {inputs.word()}" for _ in range(inputs.rng.randint(0, 2))]
    text = "\n".join(before + [f"      {line}" for line in lines] + after)
    assert vitest_summaries(text) == expected, inputs.note(text)


# --- AC-12 ----------------------------------------------------------------

@pytest.mark.parametrize("name, suffix", [
    ("x #12", "#1"), ("a > b#3", "#1"), ("t#0", "#1"),
    ("t", ""), ("t[x#y]", ""), ("t#²", ""), ("t#", ""), ("#12", ""),
])
def test_ac12_test_id_adds_one_for_numbered_name_and_round_trips(inputs, name,
                                                                 suffix):
    """`test_id` без `n` дописывает `#1` имени на `#<ASCII-цифры>` с непустой частью перед `#`, и `parse_test_id` возвращает имя целиком.

    Сценарий: случайные компонент и путь, имя варианта. Идентификатор —
    `<компонент>:<путь>::<имя><суффикс>`; разбор даёт тот же компонент,
    путь и имя целиком.

    Ловит мутацию: `#1` дописывается всем именам — у `t` идентификатор
    `…::t#1`; условие `test_id` расходится с `parse_test_id` (без
    `isascii`) — `t#²` получает `#1` и разбор возвращает `t#²` с номером;
    без проверки непустой головы — `#12` получает `#1`.
    """
    comp, path = f"c{inputs.word()}", f"src/{inputs.word()}.test.js"
    text = project_profile.test_id(comp, path, name)
    assert text == f"{comp}:{path}::{name}{suffix}", inputs.note(text)
    assert project_profile.parse_test_id(text)[:3] == (comp, path, name), (
        inputs.note(text))


@pytest.mark.parametrize("name, n, expected", [
    ("x #12", 2, "x #12#2"), ("x #12", 1, "x #12#1"), ("t", 1, "t#1"),
    ("t", 3, "t#3"), ("a > b", 2, "a > b#2"),
])
def test_ac12_explicit_n_unchanged(inputs, name, n, expected):
    """С явным `n` идентификатор — прежний литерал `<компонент>:<путь>::<имя>#<n>`.

    Сценарий: случайные компонент и путь, имя и номер варианта.

    Ловит мутацию: к имени на `#<цифры>` с явным `n` дописывается ещё и
    `#1` (`x #12#1#2`); явный `n=1` отбрасывается.
    """
    comp, path = f"c{inputs.word()}", f"src/{inputs.word()}.test.js"
    text = project_profile.test_id(comp, path, name, n)
    assert text == f"{comp}:{path}::{expected}", inputs.note(text)


def test_ac12_random_names_round_trip(inputs):
    """Случайные имена с хвостом `#<цифры>` и без него: `parse_test_id(test_id(…))` возвращает имя целиком.

    Сценарий: двадцать случайных имён из букв, пробелов, `>` и `#`, у
    части — хвост `#<цифры>`. Для каждого разбор идентификатора без `n`
    возвращает исходное имя.

    Ловит мутацию: `test_id` не дописывает `#1` — у имени с хвостом разбор
    отрезает его номером; дописывает `#1` по иному условию, чем разбор, —
    имя теряет или получает лишний хвост.
    """
    comp, path = f"c{inputs.word()}", f"src/{inputs.word()}.test.js"
    alphabet = string.ascii_letters + " >#"
    for _ in range(20):
        name = "".join(inputs.rng.choice(alphabet)
                       for _ in range(inputs.rng.randint(1, 10)))
        if inputs.rng.random() < 0.5:
            name += f"#{inputs.rng.randint(0, 99)}"
        text = project_profile.test_id(comp, path, name)
        assert project_profile.parse_test_id(text)[2] == name, (
            inputs.note(f"{name!r} -> {text!r}"))


# --- AC-13 ----------------------------------------------------------------

def test_ac13_report_ids_number_first_occurrence_of_numbered_name(inputs,
                                                                  tmp_path):
    """Два теста `x #12` и тест `x` в одном файле дают идентификаторы `…::x #12#1`, `…::x #12#2` и `…::x`.

    Сценарий: отчёт `pult-vitest` из трёх прошедших записей одного файла,
    `x` — в случайной позиции; `parse_vitest` строит идентификаторы.

    Ловит мутацию: первое вхождение имени на `#<цифры>` остаётся без
    номера — `…::x #12`; номер повтора считается от имени без хвоста —
    `x` получает номер.
    """
    file = f"src/{inputs.word()}.test.js"
    names = ["x #12", "x #12"]
    names.insert(inputs.rng.randint(0, 2), "x")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"tests": [
        {"file": file, "name": name, "state": "pass", "mode": "run",
         "fails": False, "retry_count": 0, "error_name": None,
         "timeout": False, "hook": None, "duration_ms": 1}
        for name in names]}), encoding="utf-8")
    comp = f"c{inputs.word()}"
    parsed, reason = outcome.parse_vitest(report, comp, "")
    assert parsed is not None, inputs.note(reason)
    numbered = iter(["x #12#1", "x #12#2"])
    expected = [f"{comp}:{file}::" + ("x" if name == "x" else next(numbered))
                for name in names]
    assert [r.id for r in parsed] == expected, inputs.note(str(parsed))


# --- AC-14 ----------------------------------------------------------------

@pytest.mark.parametrize("name, expected", [
    ("x #12#1", ""),
    ("x #12#2", "повтор имени теста в файле"),
    ("x#2", "повтор имени теста в файле"),
    ("x#7", "повтор имени теста в файле"),
])
def test_ac14_not_passed_kind_repeat_from_two(inputs, name, expected):
    """`not_passed_kind` прошедшей записи считает повтором только номер от 2.

    Сценарий: прошедшая запись `CaseResult` со случайными компонентом и
    путём и именем варианта.

    Ловит мутацию: гейт считает повтором любой номер, в том числе `#1` —
    у `…::x #12#1` вид «повтор имени теста в файле»; порог поднят выше
    2 — `…::x#2` без находки.
    """
    record = outcome.CaseResult(
        f"c{inputs.word()}:src/{inputs.word()}.test.js::{name}", outcome.PASSED)
    assert not_passed_kind(record) == expected, inputs.note(record.id)


# --- AC-15 ----------------------------------------------------------------

def _repeat_findings(rows: list) -> set:
    found = set()
    for row in rows:
        for line in (row["detail"] or "").splitlines():
            for part in line.split("; "):
                if part.startswith(REPEAT_FINDING):
                    found.add(part)
    return found


@pytest.mark.parametrize("copies, repeats", [(1, []), (2, [2])])
def test_ac15_plank_gate_repeat_only_from_second_copy(fail_to_pass, copies,
                                                      repeats):
    """Гейт честного `FAIL_TO_PASS` на выходе из `tests_writing`: одиночный тест `x #12` — без находки «повтор», два — находка только у `…::x #12#2`.

    Сценарий: учебный проект `pult-vitest`, задача с одним критерием,
    файл планки с тестом `AC-<n>: x #12`; отчёт базы несёт его один или
    два раза (`AssertionError`). Находки «повтор имени теста в файле: …»
    в записях журнала `advance` — ровно у идентификаторов с номерами
    варианта (у одиночного — ни одной).

    Связка «SPEC — черновик планки — чекпоинт — FSM — отчёт раннера».

    Ловит мутацию: сбор `repeats` считает повтором любой номер — у
    одиночного теста находка `…::AC-<n>: x #12#1`; первое вхождение без
    `#1` и разбор отрезает `#12` — находка у `…::AC-<n>: x #12`.
    """
    box = fail_to_pass
    n = box.numbers(1)[0]
    project = box.vitest_project()
    t = box.new_task(project, (n,))
    label = f"AC-{n}: x #12"
    plank_name = f"r{box.word()}.test.jsx"
    box.write_plank(t, {plank_name: box.jsx((label,))})
    if copies == 2:
        box.duplicate_numbers.add(n)
    rows, output = box.advance(t)
    assert box.gate_runs(), box.explain(rows, output)
    rel = box.layout_rel(t, plank_name)
    expected = {REPEAT_FINDING + box.case_id(t, rel, label, k) for k in repeats}
    assert _repeat_findings(rows) == expected, box.explain(rows, output)
