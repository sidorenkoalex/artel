"""Итог тестов компонента из отчёта: `junit-xml`, отчётчик пульта `pult-vitest`, окружение и установка пультом, сторож зависших тестов; прежний разбор у артели.

Свод долгоживущего файла задачи 01M590GJAF0EDV4NBC4C99MFVH в стиле pytest
(волна сведения тестов 2б-3, ADR-0027). Песочница — `ReportSandbox` модуля
`tests/report_outcome_sandbox.py`: фикстура `box` создаёт её через
`tests.fixtures._sandbox`, тест берёт атрибуты и методы стенда так же, как
наследник песочницы брал `self`. Имена проектов, компонентов, файлов и
значения — из `random`, зерно печатается и входит в текст каждого провала
(`box.note(...)`).

Помощники бывших тестовых классов — функции модуля с первым параметром
стенда: `assert_unknown`, `key_case`, `main_head`, `vitest_reporter_full_vitest`,
`install_and_deps_full_vitest`, `artel_unchanged_channels`.
"""
import contextlib
import hashlib
import importlib.metadata
import inspect
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (acceptance, config, doctor, project_profile, stack,
                          store, suite_run)
from orchestrator.advance_gates import two_sided
from tests.fd_wait import high_fd, select_limited, wait_readable
from tests.fixtures import _sandbox
from tests.report_outcome_sandbox import (
    CHILD_GUARD_SEC, ENTRY_HEAD, INSTALL_WITHOUT_LOCK, REAL_POPEN, REAL_RUN,
    REQUIRE_ASSERTIONS, UNKNOWN_PREFIX, VITEST_BASE, Fake, ReportSandbox, entry,
    fld, flipped, junit, report_arg, under, vitest_report, vitest_test, writable)
from tests.sandbox import make_project_repo


class PytestSpy:
    """Замена модуля `subprocess` у `acceptance`: вызов pytest запоминает
    argv и отвечает заданным кодом и выводом (или таймаутом); прочие
    вызовы идут настоящим `subprocess`."""

    def __init__(self, code: int = 0, stdout: str = "1 passed in 0.01s\n",
                 timeout: bool = False):
        self.calls: list = []
        self.code, self.stdout, self.timeout = code, stdout, timeout

    def __getattr__(self, name):
        return getattr(subprocess, name)

    @staticmethod
    def is_pytest(argv) -> bool:
        parts = [str(a) for a in argv]
        return any(a == "-m" and b == "pytest" for a, b in zip(parts, parts[1:]))

    def run(self, argv, *args, **kwargs):
        if not self.is_pytest(argv):
            return REAL_RUN(argv, *args, **kwargs)
        self.calls.append([str(a) for a in argv])
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"),
                                            output="частичный вывод\n", stderr="")
        return subprocess.CompletedProcess(argv, self.code, self.stdout, "")

    def Popen(self, argv, *args, **kwargs):
        if not self.is_pytest(argv):
            return REAL_POPEN(argv, *args, **kwargs)
        self.calls.append([str(a) for a in argv])
        spy = self
        out = kwargs.get("stdout")
        if hasattr(out, "write"):
            out.write(self.stdout.encode() if "b" in getattr(out, "mode", "")
                      else self.stdout)
            out.flush()

        class Proc:
            pid = 2_000_000_000
            returncode = spy.code
            stdin = stdout = stderr = None

            def communicate(self, input=None, timeout=None):
                if spy.timeout and timeout is not None:
                    raise subprocess.TimeoutExpired(argv, timeout,
                                                    output="частичный вывод\n")
                return spy.stdout, ""

            def wait(self, timeout=None):
                if spy.timeout and timeout is not None:
                    raise subprocess.TimeoutExpired(argv, timeout)
                return spy.code

            def poll(self):
                return spy.code

            def kill(self):
                pass

            terminate = kill

        return Proc()


def pytest_output(rng: random.Random, word) -> tuple:
    """(вывод pytest с упавшими, ожидаемые пары `failed_entries`, единица
    подтеста и её родитель, итоговая строка)."""
    mod = f"tests/test_{word()}.py"
    c, d, e, b = (f"{mod}::T::test_{word()}" for _ in range(4))
    msgs = [f"AssertionError: {word()}", f"RuntimeError: {word()}",
            f"AssertionError: {word()}"]
    label = f"(i={rng.randint(1, 9)})"
    summary = f"1 failed, 1 passed, 1 error in {rng.randint(1, 99)}.{rng.randint(10, 99)}s"
    out = ("============================= test session starts =====\n"
           f"{b} PASSED\n{c} FAILED\n"
           "=================================== FAILURES ===========\n"
           "____ T.test ____\nAssertionError: traceback text\n"
           "=========================== short test summary info ====\n"
           f"FAILED {c} - {msgs[0]}\nERROR {d} - {msgs[1]}\n"
           f"SUBFAILED{label} {e} - {msgs[2]}\n"
           f"=================== {summary} ===================\n")
    entries = [(c, msgs[0]), (d, msgs[1]), (f"{e} {label}", msgs[2])]
    lines = [f"FAILED {c} - {msgs[0]}", f"ERROR {d} - {msgs[1]}",
             f"SUBFAILED{label} {e} - {msgs[2]}"]
    return out, entries, (f"{e} {label}", e), summary, lines


FLAGS = ["-p", "no:cacheprovider", "-p", "timeout", "-o",
         f"timeout={stack.PER_TEST_TIMEOUT_SEC}"]


@pytest.fixture
def box():
    yield from _sandbox(ReportSandbox)


def assert_unknown(box, run, context: str) -> None:
    box.assertFalse(run.green, box.note(f"{context}: {run}"))
    box.assertEqual(run.outcome, acceptance.FULL_SUITE_NOT_STARTED,
                     box.note(f"{context}: {run}"))
    box.assertTrue(run.detail.startswith(UNKNOWN_PREFIX),
                    box.note(f"{context}: {run.detail}"))


def key_case(box, tools: str, lock: str, extra_arg: str = "",
             report_args=("--junitxml", "{path}"), comp: str | None = None,
             project: str | None = None, clone: Path | None = None):
    """Ключ итога компонента `junit-xml` с `tools` `tools`, игнорируемым
    `package-lock.json` с текстом `lock` и (опционально) добавочным
    аргументом команды."""
    command = [str(box.fake.wrapper)] + ([extra_arg] if extra_arg else [])
    fields = box.junit_fields(box.fake, box.wd, command=command,
                               report_args=list(report_args),
                               tools={"node": tools})
    project = project or box.name
    box.entries = [e for e in box.entries
                    if not e.startswith(f"  {project}:\n")]
    box.entries.append(entry(project, fields, comp or box.comp))
    box.write_targets()
    clone = clone or box.clone
    (clone / box.wd / "package-lock.json").write_text(lock, encoding="utf-8")
    tree = acceptance.suite_tree_hash(clone)
    box.assertIsNotNone(tree, box.note("дерево клона не снято"))
    return tree, acceptance.suite_result_key(tree, box.profile(project),
                                             root=clone)


def vitest_reporter_full_vitest(box, case: dict, tests=None, **scenario) -> tuple:
    if tests is not None:
        scenario["report"] = vitest_report(tests)
    case["fake"].scenario(
        version_out=f"vitest/{case['version']} linux-x64 node-v22.11.0",
        **scenario)
    return box.full(case["clone"], case["task"], case["profile"])


def install_and_deps_full_vitest(box, case: dict) -> tuple:
    case["fake"].scenario(
        version_out=f"vitest/{case['version']} linux-x64 node-v22.11.0",
        report=vitest_report([vitest_test("src/a.test.js", "ok")]))
    return box.full(case["clone"], case["task"], case["profile"])


def main_head(box, command) -> list:
    head = list(command) if command else ["python3", "-m", "pytest"]
    if head[0] == "python3":
        head[0] = stack.pytest_python_executable()
    return head


def artel_unchanged_channels(box):
    """(метка, канал команды, начало команды на main): артель — без
    команды, её профиль и его список; запись `test_profile` без
    `report` — профиль и список."""
    fields = {"command": ["python3", "-m", "pytest", "-rN"],
              "long_lived_dir": "tests",
              "long_lived_name": "test_<id>_<name>.py",
              "weakening_scope": ["tests/**"],
              "mutation_claim_scope": ["tests/**"]}
    name, clone = box.project(fields, {"tests/test_x.py": "# тест\n"})
    artel = box.profile(config.DEFAULT_TARGET)
    plain = box.profile(name)
    return clone, [("артель без команды", None, None),
                   ("профиль артели", artel, artel.command),
                   ("список артели", list(artel.command), artel.command),
                   ("профиль без report", plain, plain.command),
                   ("список без report", list(plain.command), plain.command)]


def test_ac1_outcome_follows_report_not_runner_output(box):
    """Компонент `junit-xml`: исход полного прогона — по отчёту, а не по тексту вывода раннера.

    Сценарий: учебный компонент `junit-xml` (имена от зерна), раннер
    всегда выходит с кодом 0. Для каждого из двух текстов вывода
    («N passed …» и «N failed …») раннер пишет по очереди: зелёный
    отчёт — итог зелёный; отчёт с проваленным тестом — итог красный, и
    деталь называет упавший тест; отчёта нет — исход «неизвестно», не
    зелёный. Тот же вывод с другим отчётом даёт другой исход.

    Ловит мутацию: итог компонента по-прежнему читается из кода
    возврата и итоговой строки pytest — зелёный код без отчёта и с
    проваленным отчётом даёт «зелёный прогон», а вывод «N failed» при
    зелёном отчёте — «красный прогон».
    """
    case = box.junit_component()
    bad = f"test_{box.word()}"
    green = junit([("src/x.test.jsx", f"test_{box.word()}", "passed",
                    "", "", "0.1")])
    failed = junit([("src/x.test.jsx", f"test_{box.word()}", "passed",
                     "", "", "0.1"),
                    ("src/x.test.jsx", bad, "failed", "AssertionError",
                     "boom", "0.2")])
    n = box.rng.randint(2, 9)
    for stdout in (f"{n} passed in 0.1s\n", f"{n} failed in 0.1s\n"):
        seen = {}
        for label, report in (("зелёный", green), ("красный", failed),
                              ("нет", None)):
            case["fake"].scenario(stdout=stdout, report=report)
            run, out = box.full(case["clone"], case["task"],
                                 case["profile"])
            seen[label] = run.outcome
            context = f"вывод {stdout!r}, отчёт {label}: {out}"
            if label == "зелёный":
                assert run.green, (
                    box.note(f"{context}\n{run}") + "; " + f"stdout={stdout!r}; report={label!r}")
                assert run.outcome == acceptance.FULL_SUITE_GREEN, (
                    box.note(context) + "; " + f"stdout={stdout!r}; report={label!r}")
            elif label == "красный":
                assert not run.green, (
                    box.note(f"{context}\n{run}") + "; " + f"stdout={stdout!r}; report={label!r}")
                assert run.outcome == acceptance.FULL_SUITE_RED, (
                    box.note(f"{context}\n{run}") + "; " + f"stdout={stdout!r}; report={label!r}")
                assert bad in run.detail, (
                    box.note(run.detail) + "; " + f"stdout={stdout!r}; report={label!r}")
            else:
                assert_unknown(box, run, context)
        assert len(set(seen.values())) == 3, (
            box.note(
            f"вывод {stdout!r}: исходы не различаются отчётом: {seen}"))


def test_ac2_empty_or_unreadable_report_is_unknown(box):
    """Ненулевой код при отчёте без тестов и неразборчивый отчёт — исход «неизвестно», не зелёный.

    Сценарий: учебный компонент `junit-xml`. (а) Раннер выходит с
    ненулевым кодом и пишет отчёт без единого testcase. (б) Раннер
    пишет обрезанный XML — с кодом 0 и с ненулевым кодом. В каждом
    случае `full_suite` даёт `FULL_SUITE_NOT_STARTED` с деталью
    «итог неизвестен: …».

    Ловит мутацию: пустой отчёт читается как «тестов нет — зелено», а
    неразобранный отчёт — как красный прогон по коду возврата (или
    зелёный при коде 0); исход «неизвестно» не наступает.
    """
    case = box.junit_component()
    code = box.rng.randint(1, 3)
    empty = junit([])
    broken = junit([("src/x.test.jsx", "test_a", "passed", "", "", "0.1")])
    broken = broken[:box.rng.randint(40, len(broken) - 20)]
    for label, report, rc in (("пустой", empty, code),
                              ("обрезанный, код 0", broken, 0),
                              ("обрезанный, ненулевой код", broken, code)):
        case["fake"].scenario(stdout="1 passed in 0.1s\n",
                              report=report, code=rc)
        run, out = box.full(case["clone"], case["task"], case["profile"])
        assert_unknown(box, run, f"отчёт {label}: {out}")


def test_ac2_per_test_record_id_from_repo_root_outcome_kind_reason_time(box):
    """Итог по каждому тесту: идентификатор от корня репозитория с `workdir`, исход, вид падения, причина пропуска, время.

    Сценарий: компонент `junit-xml` с `workdir` (имя от зерна); отчёт
    с четырьмя тестами файла `src/x.test.jsx` (путь от `workdir`):
    прошедший, проваленный (`AssertionError`), ошибка
    (`RuntimeError`), пропущенный с причиной. У каждого — время.
    Записи `FullSuiteRun.tests` найдены по
    `project_profile.test_id(компонент, "<workdir>/src/x.test.jsx",
    имя)` — путь содержит `workdir`; исходы `passed`/`failed`/`error`/
    `skipped`; вид падения называет тип ошибки; причина пропуска — текст
    `skipped`; время — значение отчёта.

    Ловит мутацию: идентификатор строится от `workdir` (`src/x…`), а не
    от корня репозитория, — записи по ожидаемому id не находятся; либо
    ошибка схлопнута в провал (`failed`), либо причина пропуска и тип
    ошибки не переносятся в запись.
    """
    case = box.junit_component()
    names = {k: f"test_{box.word()}" for k in
             ("passed", "failed", "error", "skipped")}
    reason = f"нужна сеть {box.word()}"
    seconds = {k: round(box.rng.uniform(0.01, 2.0), 3) for k in names}
    cases = [("src/x.test.jsx", names["passed"], "passed", "", "",
              seconds["passed"]),
             ("src/x.test.jsx", names["failed"], "failed", "AssertionError",
              "boom", seconds["failed"]),
             ("src/x.test.jsx", names["error"], "error", "RuntimeError",
              "bad", seconds["error"]),
             ("src/x.test.jsx", names["skipped"], "skipped", "", reason,
              seconds["skipped"])]
    case["fake"].scenario(stdout="", report=junit(cases), code=1)
    run, out = box.full(case["clone"], case["task"], case["profile"])
    path = f"{case['wd']}/src/x.test.jsx"
    for kind, name in names.items():
        record = box.by_id(run, project_profile.test_id(case["comp"],
                                                         path, name))
        context = box.note(f"{kind}: {record}")
        assert fld(record, "outcome") == kind, context
        got = fld(record, "time")
        assert got is not None, context
        assert (abs(float(got) - seconds[kind]) < 1e-6
                        or abs(float(got) - seconds[kind] * 1000) < 1e-3), (
            context)
        if kind == "failed":
            assert "AssertionError" in str(fld(record, "failure")), context
        if kind == "error":
            assert "RuntimeError" in str(fld(record, "failure")), context
        if kind == "skipped":
            assert reason in str(fld(record, "skip_reason")), context
    ids = [fld(r, "id") for r in box.records_of(run)]
    assert not any(str(i).startswith(f"{case['comp']}:src/")
                         for i in ids), (
        box.note(f"id от workdir: {ids}"))


def test_ac3_report_path_outside_tree_workdir_and_clean_env(box):
    """Команда компонента получает `report_args` с `{path}` вне рабочей копии, идёт в `workdir` с окружением компонента.

    Сценарий: компонент `junit-xml` с явными `report_args`
    `[--report-to, {path}]`, `workdir` и переменной `env` (имена и
    значения от зерна); в окружении пульта — случайная переменная
    `ARTEL_LEAK_*`. Раннер пишет зелёный отчёт по пути после
    `--report-to`. Прогон зелёный (отчёт прочитан по этому пути); argv
    несёт `--report-to <путь>`, путь — вне клона; `cwd` — `workdir` в
    клоне; окружение несёт переменную компонента и не несёт переменной
    пульта.

    Ловит мутацию: `{path}` подставляется путём внутри рабочей копии
    (например, `workdir/report.xml`) либо команда идёт с копией
    окружения пульта из корня клона.
    """
    case = box.junit_component(report_args=["--report-to", "{path}"])
    case["fake"].scenario(report=junit([("src/x.test.jsx", "test_ok",
                                         "passed", "", "", "0.1")]))
    run, out = box.full(case["clone"], case["task"], case["profile"])
    assert run.green, box.note(f"{run}\n{out}")
    runs = case["fake"].runs()
    assert runs, box.note("раннер не запускался")
    record = runs[-1]
    path = report_arg(record["args"], "--report-to")
    assert path is not None, (
        box.note(f"нет --report-to: {record['args']}"))
    assert not under(path, case["clone"]), (
        box.note(f"отчёт внутри рабочей копии: {path}"))
    assert os.path.realpath(record["cwd"]) == os.path.realpath(case["clone"] / case["wd"]), (
        box.note("cwd не workdir"))
    env_name, env_value = case["env"]
    assert record["env"].get(env_name) == env_value, (
        box.note("нет переменной env компонента"))
    assert box.leak not in record["env"], (
        box.note("окружение пульта в прогоне"))


def test_ac4_explicit_report_args_win_over_default(box):
    """Компонент с явными `report_args` запускается с ними, а не с умолчанием `--junitxml`.

    Сценарий: компонент `junit-xml` с `report_args` `[--report-to,
    {path}]`. argv прогона несёт `--report-to` и не несёт ни одного
    аргумента `--junitxml`.

    Ловит мутацию: умолчание `[--junitxml, {path}]` подставляется
    всегда, поверх явных `report_args` компонента.
    """
    case = box.junit_component(report_args=["--report-to", "{path}"])
    case["fake"].scenario(report=junit([("src/x.test.jsx", "test_ok",
                                         "passed", "", "", "0.1")]))
    box.full(case["clone"], case["task"], case["profile"])
    args = case["fake"].runs()[-1]["args"]
    assert report_arg(args, "--report-to") is not None, (
        box.note(str(args)))
    assert not any(a.startswith("--junitxml") for a in args), (
        box.note(f"умолчание поверх явных: {args}"))


def test_ac4_ac6_sled_record_default_report_args_outcome_from_report(box):
    """Запись `test_profile` с `report: junit-xml` и `runner: pytest-own` без `report_args` идёт с `--junitxml <путь вне клона>` и судится отчётом.

    Сценарий: запись `test_profile` (не `components:`) с
    `runner: pytest-own`, `workdir`, `report: junit-xml`, командой —
    подменённым раннером. Раннер выходит с кодом 0: с зелёным отчётом
    и выводом «N failed» — итог зелёный; с проваленным отчётом и
    выводом «N passed» — красный; без отчёта — «неизвестно». argv несёт
    `--junitxml` с путём вне клона.

    Ловит мутацию: умолчание `report_args` подставляется только
    компонентам записи `components:` — у записи `test_profile`
    `pytest-own` итог по-прежнему по коду возврата (зелёный без отчёта).
    """
    fake = Fake(box, "sled")
    wd = f"be{box.word(5)}"
    name, clone = box.project(box.junit_fields(fake, wd),
                               {f"{wd}/src/x.test.jsx": "// тест\n"})
    task, profile = box.task(name), box.profile(name)
    green = junit([("src/x.test.jsx", "test_ok", "passed", "", "", "0.1")])
    failed = junit([("src/x.test.jsx", "test_bad", "failed",
                     "AssertionError", "boom", "0.1")])
    for label, report, stdout in (("зелёный", green, "3 failed in 0.1s\n"),
                                  ("красный", failed, "3 passed in 0.1s\n"),
                                  ("нет", None, "3 passed in 0.1s\n")):
        fake.scenario(report=report, stdout=stdout)
        run, out = box.full(clone, task, profile)
        if label == "зелёный":
            assert run.green, (
                box.note(f"{run}\n{out}") + "; " + f"report={label!r}")
        elif label == "красный":
            assert run.outcome == acceptance.FULL_SUITE_RED, (
                box.note(f"{run}\n{out}") + "; " + f"report={label!r}")
        else:
            assert_unknown(box, run, out)
        args = fake.runs()[-1]["args"]
        path = report_arg(args, "--junitxml")
        assert path is not None, (
            box.note(f"нет --junitxml: {args}") + "; " + f"report={label!r}")
        assert not under(path, clone), (
            box.note(path) + "; " + f"report={label!r}")


def test_ac5_unknown_outcome_form_and_log(box):
    """Исход «неизвестно»: константа «прогон не начат», деталь «итог неизвестен: …», лог записан и назван, вывод называет «неизвестно».

    Сценарий: компонент `junit-xml`, раннер выходит с кодом 0 и
    отчёта не пишет. `full_suite`: `outcome` —
    `acceptance.FULL_SUITE_NOT_STARTED`, `green` ложно, `detail`
    начинается с «итог неизвестен: », `log_path` — существующий файл, и
    его путь назван в `detail`; слово «неизвестно» есть в тексте узла
    (деталь, выжимка или вывод).

    Ловит мутацию: исход «неизвестно» возвращается веткой «прогон не
    начат» без лога (`log_path` — `None`, путь в детали не назван) или
    выдаётся красным прогоном.
    """
    case = box.junit_component()
    case["fake"].scenario(stdout=f"{box.rng.randint(1, 9)} passed in 0.1s\n")
    run, out = box.full(case["clone"], case["task"], case["profile"])
    assert_unknown(box, run, out)
    assert run.log_path is not None, box.note(str(run))
    assert Path(run.log_path).is_file(), box.note(str(run))
    assert str(run.log_path) in run.detail, box.note(run.detail)
    assert "неизвестно" in f"{run.detail}\n{run.digest}\n{out}", (
        box.note(f"{run}\n{out}"))


def test_ac6_pult_pytest_and_no_report_records_by_code_and_text(box):
    """Запись `test_profile` с `runner: pult-pytest` (с `report: junit-xml` и без `report`) судится кодом возврата и текстом pytest.

    Сценарий: две записи `test_profile` без `runner` (раннер пульта) —
    с `report: junit-xml`, как у артели, и без `report`; команда —
    подменённый раннер. Раннер отчёта не пишет: с кодом 0 и выводом
    «N passed» итог зелёный, с ненулевым кодом и «N failed» — красный.
    Исхода «неизвестно» нет.

    Ловит мутацию: различитель «итог из отчёта» смотрит на одно поле
    `report` — запись артели (`pult-pytest`, `report: junit-xml`)
    переходит на отчёт и без отчёта получает «неизвестно».
    """
    for with_report in (True, False):
        fake = Fake(box, "pult")
        fields = {"command": [str(fake.wrapper)], "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": ["tests/**"],
                  "mutation_claim_scope": ["tests/**"]}
        if with_report:
            fields["report"] = "junit-xml"
        name, clone = box.project(fields, {"tests/test_x.py": "# тест\n"})
        task, profile = box.task(name), box.profile(name)
        n = box.rng.randint(1, 9)
        for code, stdout, outcome in (
                (0, f"{n} passed in 0.1s\n", acceptance.FULL_SUITE_GREEN),
                (1, f"{n} failed in 0.1s\n", acceptance.FULL_SUITE_RED)):
            fake.scenario(code=code, stdout=stdout)
            run, out = box.full(clone, task, profile)
            assert run.outcome == outcome, (
                box.note(f"{run}\n{out}") + "; " + f"report={with_report!r}; code={code!r}")
            assert stdout.strip() in run.detail, (
                box.note(run.detail) + "; " + f"report={with_report!r}; code={code!r}")


def test_ac11_unknown_is_never_green_at_any_place(box):
    """Компонент `junit-xml` с исходом «неизвестно» не даёт зелёного итога ни в одном месте прогона пульта.

    Сценарий: компонент `junit-xml` записи `components:` без `runner`
    (в корне); раннер выходит с кодом 0, печатает «1 passed» и отчёта
    не пишет. Места: `acceptance.run` (рубеж, подтяжка main,
    `amend-tests`), `acceptance.collect` (сухой сбор),
    `acceptance.run_repeat` (повтор красных), `acceptance.run_plank`
    (`plank-run`), `acceptance.full_suite`, `two_sided.run`
    (двусторонний прогон на ветке клона). Ни одно не зелёное: `run` и
    `collect` — ложь, `run_repeat` — непустой список, `run_plank` —
    ненулевой код, `full_suite` — не зелёный, у `two_sided.run` есть
    отказы.

    Ловит мутацию: разбор отчёта есть только в полном прогоне, а
    точечные места (`run`, `collect`, `run_repeat`, `run_plank`) у
    компонента с отчётом по-прежнему судят по коду 0 — «зелено».
    """
    fake = Fake(box, "places")
    comp = f"c{box.word(5)}"
    rel = f"src/test_{box.word()}.py"
    name, clone = box.project(
        box.junit_fields(fake, "", report_args=["--junitxml", "{path}"]),
        {rel: "import unittest\n"}, comp=comp)
    task, profile = box.task(name), box.profile(name)
    fake.scenario(stdout="1 passed in 0.01s\n")
    tdir = box.plank_dir()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        green, tail = acceptance.run(tdir, cwd=clone, command=profile)
        assert not green, box.note(f"run: {tail}")
        ok, tail = acceptance.collect(tdir, cwd=clone, command=profile)
        assert not ok, box.note(f"collect: {tail}")
        reds = acceptance.run_repeat([rel], clone, command=profile)
        assert reds, box.note("run_repeat: зелёный повтор")
        code, output = acceptance.run_plank([rel], clone, profile=profile)
        assert code != 0, box.note(f"run_plank: {output}")
        run = acceptance.full_suite(clone, task, command=profile, fresh=True)
        assert not run.green, box.note(f"full_suite: {run}")
    base = box.git("-C", str(clone), "rev-parse", "HEAD").strip()
    branch = f"task/{box.word()}"
    box.git("-C", str(clone), "checkout", "-q", "-b", branch)
    box.commit(clone, {rel: "import unittest\n# ветка\n"})
    box.git("-C", str(clone), "checkout", "-q", config.MAIN_BRANCH)
    method = two_sided.Method(rel, rel, "T::test_a",
                              "import unittest\n", "import unittest\n")
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        outcome = two_sided.run(clone, branch, base, [method],
                                profile=profile)
    assert outcome.refusals, box.note(
        f"двусторонний прогон доказан без отчёта: {outcome}")


def test_ac18_component_key_follows_tools_lock_command_name_and_artel_key_is_main(box):
    """Ключ итога компонента с отчётом меняется с `tools`, файлом блокировки, командой, `report_args`, различен у двух компонентов; ключ артели — формулы main.

    Сценарий: компонент `junit-xml` с `workdir`, `tools` и
    `package-lock.json`, игнорируемым git (дерево клона от его
    содержимого не меняется); ключ — `acceptance.suite_result_key(
    дерево, decide(<проект>).profile, root=клон)`. Смена версии в
    `tools`, текста файла блокировки, добавочного аргумента команды,
    `report_args` — каждая даёт другой ключ. Второй проект с теми же
    полями и другим именем компонента на том же дереве — другой ключ.
    Ключ артели (`command=None` и список команды её профиля) равен
    ключу, посчитанному формулой main: sha256 JSON дерева, Python,
    пакетов и argv полного прогона пульта.

    Ловит мутацию: ключ компонента с отчётом считается прежней формой
    `pytest-own` — без имени компонента (ключи двух компонентов
    совпадают) и без `report_args`; либо ключ артели получает новые
    поля и перестаёт совпадать с сохранёнными итогами main.
    """
    box.fake = Fake(box, "key")
    box.wd = f"fe{box.word(5)}"
    box.comp = f"c{box.word(5)}"
    box.name, box.clone = box.project(
        box.junit_fields(box.fake, box.wd), {
            f"{box.wd}/src/x.test.jsx": "// тест\n",
            ".gitignore": "package-lock.json\nnode_modules/\n"},
        comp=box.comp)
    v1, v2 = box.version(1), box.version(2)
    tree, base = key_case(box, v1, "lock-a\n")
    assert base is not None, box.note("ключа нет")
    for label, kwargs in (("tools", {"tools": v2, "lock": "lock-a\n"}),
                          ("файл блокировки", {"tools": v1, "lock": "lock-b\n"}),
                          ("команда", {"tools": v1, "lock": "lock-a\n",
                                       "extra_arg": f"--x{box.word(4)}"}),
                          ("report_args", {"tools": v1, "lock": "lock-a\n",
                                           "report_args": ("--report-to",
                                                           "{path}")})):
        tree2, key = key_case(box, **kwargs)
        assert tree2 == tree, (
            box.note("дерево сменилось") + "; " + f"change={label!r}")
        assert key != base, (
            box.note(f"ключ не видит {label}") + "; " + f"change={label!r}")
    _tree, same = key_case(box, v1, "lock-a\n")
    assert same == base, box.note("ключ не воспроизводится")
    other = f"p{box.word()}"
    _tree, key_other = key_case(box, v1, "lock-a\n", comp=f"d{box.word(5)}",
                                     project=other)
    assert key_other != base, box.note("ключи двух компонентов совпали")

    artel_tree = "0123456789abcdef0123456789abcdef01234567"
    python = stack.pytest_python_executable()
    argv = [python, "-m", "pytest", "tests", "-p", "no:cacheprovider",
            "-p", "timeout", "-o", f"timeout={stack.PER_TEST_TIMEOUT_SEC}",
            "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"]
    packages = sorted((d.metadata["Name"].lower(), d.version)
                      for d in importlib.metadata.distributions())
    main_key = hashlib.sha256(json.dumps(
        {"tree": artel_tree, "python": sys.version, "packages": packages,
         "command": argv}, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    artel = list(box.profile(config.DEFAULT_TARGET).command)
    assert acceptance.suite_result_key(artel_tree, None) == main_key, (
        box.note("ключ артели (команда пульта)"))
    assert acceptance.suite_result_key(artel_tree, artel) == main_key, (
        box.note("ключ артели (список команды профиля)"))


def test_ac6_vitest_component_without_runner_outcome_from_report(box):
    """Компонент `pult-vitest` записи `components:` без поля `runner` судится отчётом.

    Сценарий: компонент `pult-vitest` в корне клона без `runner`. Раннер
    выходит с кодом 0: с зелёным отчётом — итог зелёный; без отчёта —
    «неизвестно»; с отчётом, где тест упал `AssertionError`, — красный.

    Ловит мутацию: различитель читает `runner` компонента — компонент
    без `runner` (умолчание `pult-pytest`) идёт прежним разбором по
    коду возврата и без отчёта получает зелёный итог.
    """
    case = box.vitest_component(workdir=False)
    run, out = vitest_reporter_full_vitest(box, case, [vitest_test("src/a.test.js", "ok")])
    assert run.green, box.note(f"{run}\n{out}")
    run, out = vitest_reporter_full_vitest(box, case, None, report=None)
    assert_unknown(box, run, out)
    run, out = vitest_reporter_full_vitest(box, case, [vitest_test(
        "src/a.test.js", "bad", state="fail", error_name="AssertionError")])
    assert run.outcome == acceptance.FULL_SUITE_RED, (
        box.note(f"{run}\n{out}"))


def test_ac7_failure_kinds_assertion_type_timeout_hook(box):
    """`TypeError` — ошибка, `AssertionError` (из `failure_errors`) — провал проверки, таймаут и хук — ошибки с признаком.

    Сценарий: компонент `pult-vitest` с `failure_errors:
    [AssertionError]`; отчёт с четырьмя упавшими тестами: `TypeError`;
    `AssertionError`; таймаут (`timeout: true`); падение хука
    `beforeEach` (имя хука — случайное из четырёх). Итог красный;
    записи: `TypeError` — `error`; `AssertionError` — `failed`;
    таймаут — `error`, вид падения называет таймаут; хук — `error`,
    вид падения называет хук.

    Ловит мутацию: любое падение считается провалом проверки (`TypeError`
    — `failed`), либо признаки таймаута и хука теряются при разборе.
    """
    case = box.vitest_component()
    hook = box.rng.choice(["beforeAll", "beforeEach", "afterEach",
                            "afterAll"])
    names = {k: f"t {box.word()}" for k in ("type", "assert", "timeout",
                                               "hook")}
    tests = [vitest_test("src/a.test.js", names["type"], state="fail",
                         error_name="TypeError"),
             vitest_test("src/a.test.js", names["assert"], state="fail",
                         error_name="AssertionError"),
             vitest_test("src/a.test.js", names["timeout"], state="fail",
                         error_name="Error", timeout=True),
             vitest_test("src/a.test.js", names["hook"], state="fail",
                         error_name="Error", hook=hook)]
    run, out = vitest_reporter_full_vitest(box, case, tests)
    assert not run.green, box.note(f"{run}\n{out}")
    rec = {k: box.by_id(run, box.vid(case, "src/a.test.js", n))
           for k, n in names.items()}
    assert fld(rec["type"], "outcome") == "error", box.note(str(rec))
    assert fld(rec["assert"], "outcome") == "failed", box.note(str(rec))
    assert fld(rec["timeout"], "outcome") == "error", box.note(str(rec))
    assert "timeout" in str(fld(rec["timeout"], "failure")).lower(), (
        box.note(str(rec["timeout"])))
    assert fld(rec["hook"], "outcome") == "error", box.note(str(rec))
    assert hook in str(fld(rec["hook"], "failure")), (
        box.note(str(rec["hook"])))


def test_ac8_modes_fails_todo_skip_only_and_retries(box):
    """`it.fails`, `todo`, `skip`, `only` различимы в итоге; число повторов видно; повтор при зелёном — красный итог «повтор».

    Сценарий: компонент `pult-vitest`; отчёт с тестами: зелёный,
    `it.fails` (состояние `pass`, `fails: true`), `todo`, `skip`,
    `only` и зелёный с `retry_count` от зерна (1–4). Тройки (исход,
    `mode`, `fails`) записей `fails`/`todo`/зелёного/`skip` попарно
    различны, `skip` и `only` различны; у теста с повтором `retries` —
    число отчёта. Отдельный прогон из одного зелёного теста с повтором
    больше 0 — `FULL_SUITE_RED`, деталь называет «повтор»; тот же тест
    без повтора — зелёный.

    Ловит мутацию: повтор внутри прогона не учитывается — зелёный тест
    с `retry_count > 0` даёт зелёный итог; либо `mode`/`fails` не
    переносятся из отчёта, и `it.fails` неотличим от зелёного.
    """
    case = box.vitest_component()
    retries = box.rng.randint(1, 4)
    names = {k: f"t {box.word()}" for k in
             ("pass", "fails", "todo", "skip", "only", "retry")}
    tests = [vitest_test("src/a.test.js", names["pass"]),
             vitest_test("src/a.test.js", names["fails"], fails=True),
             vitest_test("src/a.test.js", names["todo"], state="todo",
                         mode="todo"),
             vitest_test("src/a.test.js", names["skip"], state="skip",
                         mode="skip"),
             vitest_test("src/a.test.js", names["only"], mode="only"),
             vitest_test("src/a.test.js", names["retry"],
                         retry_count=retries)]
    run, out = vitest_reporter_full_vitest(box, case, tests)
    rec = {k: box.by_id(run, box.vid(case, "src/a.test.js", n))
           for k, n in names.items()}

    def shape(key):
        return (fld(rec[key], "outcome"), fld(rec[key], "mode"),
                bool(fld(rec[key], "fails")))

    group = ["fails", "todo", "pass", "skip"]
    for i, a in enumerate(group):
        for b in group[i + 1:]:
            assert shape(a) != shape(b), box.note(
                f"{a} и {b} неразличимы: {shape(a)}")
    assert shape("skip") != shape("only"), (
        box.note(f"skip и only: {shape('skip')}"))
    assert int(fld(rec["retry"], "retries")) == retries, (
        box.note(str(rec["retry"])))
    assert not run.green, box.note(f"повтор внутри прогона: {run}")

    run, out = vitest_reporter_full_vitest(box, case, [vitest_test(
        "src/a.test.js", names["retry"], retry_count=retries)])
    assert run.outcome == acceptance.FULL_SUITE_RED, (
        box.note(f"{run}\n{out}"))
    assert "повтор" in run.detail, box.note(run.detail)
    run, out = vitest_reporter_full_vitest(box, case, [vitest_test(
        "src/a.test.js", names["retry"])])
    assert run.green, box.note(f"без повтора: {run}\n{out}")


def test_ac9_run_conditions_argv_env_cache_and_flags(box):
    """Прогон `pult-vitest`: `workdir`, окружение компонента с `CI=true`, своя группа, базовый argv, отчётчик пульта, `--expect.requireAssertions`, флаг кэша вне дерева.

    Сценарий: компонент `pult-vitest` с `workdir`, переменной `env` и
    версией Vitest из таблицы, принимающей `--expect.requireAssertions`.
    Прогон зелёный; вызов `run` раннера: `cwd` — `workdir`; окружение
    несёт переменную компонента и `CI=true`, не несёт переменной
    пульта; группа процессов раннера — не группа процесса теста; argv
    начинается с базового (`argv[0]` — `node_modules/.bin/vitest`),
    несёт `--reporter=<файл каталога orchestrator/reporters/>` (файл
    есть), `--expect.requireAssertions` и флаг кэша таблицы с путём вне
    клона и вне `node_modules`.

    Ловит мутацию: пульт не добавляет флаги — нет
    `--expect.requireAssertions` или флага кэша; `{pult_reporter}`
    подставляется путём вне `orchestrator/reporters/`; прогон идёт с
    окружением пульта без `CI=true`.
    """
    case = box.vitest_component()
    run, out = vitest_reporter_full_vitest(box, case, [vitest_test("src/a.test.js", "ok")])
    assert run.green, box.note(f"{run}\n{out}")
    runs = case["fake"].runs()
    assert runs, box.note("раннер не запускался")
    record = runs[-1]
    assert os.path.realpath(record["cwd"]) == os.path.realpath(box.wd_path(case)), (
        box.note("cwd"))
    env = record["env"]
    assert env.get("CI") == "true", box.note(f"окружение: {env}")
    assert env.get(case["env"][0]) == case["env"][1], box.note("env")
    assert box.leak not in env, box.note("окружение пульта")
    assert record["pgid"] != os.getpgrp(), (
        box.note("раннер в группе процесса пульта"))
    argv = [record["argv0"], *record["args"]]
    assert argv[0].endswith("node_modules/.bin/vitest"), (
        box.note(str(argv)))
    assert argv[1:len(VITEST_BASE)] == VITEST_BASE[1:], (
        box.note(f"argv не начинается с базового: {argv}"))
    reporters = Path(inspect.getfile(acceptance)).resolve().parent / "reporters"
    reporter = [a.split("=", 1)[1] for a in argv
                if a.startswith("--reporter=") and a != "--reporter=default"]
    assert reporter, box.note(f"нет --reporter=<путь>: {argv}")
    assert (under(reporter[0], reporters) and
                    Path(reporter[0]).is_file()), (
        box.note(f"отчётчик не из {reporters}: {reporter}"))
    assert any(a.startswith(REQUIRE_ASSERTIONS) for a in argv), (
        box.note(f"нет {REQUIRE_ASSERTIONS}: {argv}"))
    flag = box.cache_flag(box.accepted_major()[1])
    cache = report_arg(argv, flag)
    assert cache is not None, box.note(f"нет флага кэша {flag}: {argv}")
    assert not under(cache, case["clone"]), box.note(cache)
    assert "node_modules" not in Path(cache).parts, box.note(cache)


def test_ac9_timeout_kills_group_not_green(box):
    """Раннер `pult-vitest`, превысивший предел компонента, снимается вместе с группой; итог не зелёный.

    Сценарий: компонент `pult-vitest` с `full_suite_timeout_sec: 1`;
    раннер держит конец записи именованного канала в дочернем процессе
    и спит дольше предела. `full_suite` не зелёный; после него читатель
    канала получает конец файла — раннер и его потомок мертвы (событие,
    предел ожидания — страховка).

    Ловит мутацию: прогон `pult-vitest` идёт без своей группы процессов
    и по таймауту убивается только главный процесс — потомок держит
    канал открытым.
    """
    case = box.vitest_component(timeout=1)
    fifo = case["fake"].dir / "fifo"
    os.mkfifo(fifo)
    reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
    if not select_limited():
        # Номер выше FD_SETSIZE в каждом прогоне: ожидание держится и
        # там, где исполнитель xdist уже занял тысячу дескрипторов.
        reader = high_fd(box, reader)
    box.addCleanup(os.close, reader)
    run, out = vitest_reporter_full_vitest(box, case, [vitest_test("src/a.test.js", "ok")],
                                fifo=str(fifo), sleep=120)
    assert not run.green, box.note(f"{run}\n{out}")
    assert case["fake"].runs(), box.note("раннер не запускался")
    gone = False
    while True:
        ready = wait_readable(reader, CHILD_GUARD_SEC)
        if not ready:
            break
        try:
            if os.read(reader, 4096) == b"":
                gone = True
                break
        except BlockingIOError:
            continue
    assert gone, box.note("потомок раннера пережил таймаут")


def test_ac9_version_refusals_require_assertions_and_unconfirmed_cache(box):
    """Версия Vitest, не принимающая `--expect.requireAssertions`, и версия вне таблицы — отказ подготовки с текстом, не зелёный.

    Сценарий: (а) таблица `VITEST_VERSION_FLAGS` подменена копией с
    новой главной версией, у записи которой булевы значения ложны;
    компонент объявляет эту версию в `tools`, раннер отвечает ею на
    `--version`. (б) Компонент с главной версией, которой в таблице нет.
    В обоих случаях итог не зелёный, деталь непуста, раннер не
    запускался с `run`; в (а) деталь называет `--expect.requireAssertions`.

    Ловит мутацию: подготовка не сверяет версию с таблицей — флаги
    подставляются по умолчанию, и прогон неподтверждённой версии идёт
    и даёт зелёный итог.
    """
    key, value = box.accepted_major()
    new_major = box.absent_major()
    new_key = new_major if isinstance(key, int) else str(new_major)
    patched = dict(box.table())
    patched[new_key] = flipped(value)
    with mock.patch.object(project_profile, "VITEST_VERSION_FLAGS", patched):
        case = box.vitest_component(version=box.version(new_major))
        run, out = vitest_reporter_full_vitest(box, case, [vitest_test("src/a.test.js", "ok")])
    assert not run.green, box.note(f"{run}\n{out}")
    assert REQUIRE_ASSERTIONS in run.detail, box.note(run.detail)
    assert case["fake"].runs() == [], box.note("прогон шёл")

    case = box.vitest_component(version=box.version(box.absent_major()))
    run, out = vitest_reporter_full_vitest(box, case, [vitest_test("src/a.test.js", "ok")])
    assert not run.green, box.note(f"{run}\n{out}")
    assert run.detail.strip(), box.note(str(run))
    assert case["fake"].runs() == [], box.note("прогон шёл")


def test_ac10_preparation_refusals_command_and_report_args(box):
    """Чужой `command` и `report_args` без `{pult_reporter}` или `{path}` — отказ подготовки с текстом, не зелёный.

    Сценарий: компонент `pult-vitest`, у которого по очереди: `command`
    `[npx, vitest, run]`; базовый argv с чужим `--config`; с
    `--retry=1`; с `--expect.requireAssertions` внутри `command`;
    `report_args` без `{pult_reporter}`; `report_args` без `{path}`.
    Каждый — итог не зелёный, деталь непуста, раннер не запускался с
    `run`.

    Ловит мутацию: сверка `command` с базовым argv требования 7 снята
    (или сравнивает только начало), и прогон с `--retry=1` или без
    отчётчика пульта идёт и даёт зелёный итог.
    """
    other_config = list(VITEST_BASE)
    other_config[3] = f"{box.word()}.config.js"
    retry = VITEST_BASE[:-1] + ["--retry=1"]
    variants = {
        "npx vitest run": {"command": ["npx", "vitest", "run"]},
        "чужой --config": {"command": other_config},
        "--retry=1": {"command": retry},
        "--expect.requireAssertions в command": {
            "command": VITEST_BASE + [REQUIRE_ASSERTIONS]},
        "без {pult_reporter}": {"report_args": ["--outputFile={path}"]},
        "без {path}": {"report_args": ["--reporter={pult_reporter}"]},
    }
    for label, extra in variants.items():
        case = box.vitest_component(**extra)
        run, out = vitest_reporter_full_vitest(box, case, [vitest_test("src/a.test.js",
                                                       "ok")])
        assert not run.green, (
            box.note(f"{label}: {run}\n{out}") + "; " + f"variant={label!r}")
        assert run.detail.strip(), (
            box.note(str(run)) + "; " + f"variant={label!r}")
        assert case["fake"].runs() == [], (
            box.note(f"{label}: прогон шёл") + "; " + f"variant={label!r}")


def test_ac10_subset_by_select_and_refusal_without_select(box):
    """Подмножество тестов идёт подстановкой `{tests}` в `select`; без `select` подмножество отказывает, полный прогон идёт.

    Сценарий: компонент `pult-vitest` с `select: ["{tests}"]` —
    `acceptance.run_repeat` двух файлов компонента (имена от зерна)
    зелёный, argv вызова `run` называет оба файла. Компонент без
    `select` — `run_repeat` красный (непустой список с текстом), раннер
    с `run` не запускался; полный прогон того же компонента зелёный.

    Ловит мутацию: без `select` пульт молча гонит полный набор вместо
    подмножества (повтор «зелёный»), либо `{tests}` не подставляется, и
    файлы подмножества не доходят до раннера.
    """
    case = box.vitest_component()
    files = [f"src/{box.word()}.test.js", f"src/{box.word()}.test.js"]
    prefix = f"{case['wd']}/"
    report = [vitest_test(f, "ok") for f in files]
    case["fake"].scenario(
        version_out=f"vitest/{case['version']} linux-x64 node-v22.11.0",
        report=vitest_report(report))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        reds = acceptance.run_repeat([prefix + f for f in files],
                                     case["clone"], command=case["profile"])
    assert reds == [], box.note(f"повтор подмножества: {reds}\n"
                                         f"{buf.getvalue()}")
    runs = case["fake"].runs()
    assert runs, box.note("раннер не запускался")
    args = " ".join(runs[-1]["args"])
    for f in files:
        assert Path(f).name in args, box.note(f"нет {f}: {args}")

    case = box.vitest_component(select=None)
    case["fake"].scenario(
        version_out=f"vitest/{case['version']} linux-x64 node-v22.11.0",
        report=vitest_report(report))
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        reds = acceptance.run_repeat([f"{case['wd']}/{f}" for f in files],
                                     case["clone"], command=case["profile"])
    assert reds, box.note("подмножество без select не отказало")
    assert any(red.note for red in reds), box.note(str(reds))
    assert case["fake"].runs() == [], box.note("прогон шёл")
    run, out = vitest_reporter_full_vitest(box, case, report)
    assert run.green, box.note(f"полный прогон без select: {run}")


def test_ac15_install_once_per_lock_content_from_task_branch(box):
    """Установка исполняется пультом один раз на содержимое `package-lock.json` рабочей копии ветки задачи.

    Сценарий: компонент `pult-vitest` с поддельной `install`. Два
    полных прогона — оба зелёные, раннер с `run` запускался дважды,
    установка — один раз. В клоне — ветка задачи с правкой
    `package-lock.json` (main не меняется); прогон на ней — вторая
    установка, и её сумма — сумма нового содержимого.

    Ловит мутацию: установка ключуется суммой файла блокировки main
    (или не ключуется вовсе) — правка в ветке установку не повторяет,
    либо установка идёт на каждом прогоне.
    """
    case = box.vitest_component()
    for _ in range(2):
        run, out = install_and_deps_full_vitest(box, case)
        assert run.green, box.note(f"{run}\n{out}")
    assert len(case["fake"].runs()) == 2, box.note("прогонов не два")
    assert len(case["fake"].installs()) == 1, (
        box.note(f"установки: {case['fake'].installs()}"))
    box.git("-C", str(case["clone"]), "checkout", "-q", "-b",
             f"task/{box.word()}")
    lock_rel = f"{case['wd']}/package-lock.json"
    text = json.dumps({"lockfileVersion": 3, "seed": box.word()}) + "\n"
    box.commit(case["clone"], {lock_rel: text}, "правка блокировки")
    run, out = install_and_deps_full_vitest(box, case)
    assert run.green, box.note(f"{run}\n{out}")
    installs = case["fake"].installs()
    assert len(installs) == 2, box.note(f"установки: {installs}")
    assert installs[-1]["lock"] == hashlib.sha256(text.encode()).hexdigest(), (
        box.note("установка не по файлу блокировки ветки"))


def test_ac15_install_without_lock_and_failed_install_refuse(box):
    """`install` без файла блокировки в `workdir` (npm и `uv sync`) не исполняется; сбой установки — отказ, не зелёный.

    Сценарий: (а) компонент `pult-vitest` без `package-lock.json`; (б)
    компонент `junit-xml` с `install: [<…>/uv, sync]` и без файлов
    блокировки в `workdir`. В обоих итог не зелёный, деталь несёт
    «install без файла блокировки не исполняется», установка не
    запускалась. (в) Компонент `pult-vitest`, установка выходит с
    ненулевым кодом: итог не зелёный, деталь непуста, раннер не
    запускался.

    Ловит мутацию: `install` без файла блокировки исполняется как есть
    (или пропускается молча, и прогон идёт); сбой установки не
    останавливает прогон.
    """
    case = box.vitest_component(lock=False)
    run, out = install_and_deps_full_vitest(box, case)
    assert not run.green, box.note(f"{run}\n{out}")
    assert INSTALL_WITHOUT_LOCK in run.detail, box.note(run.detail)
    assert case["fake"].installs() == [], box.note("установка шла")

    fake = Fake(box, "uv")
    uv = fake.tool("uv")
    junit_case = box.junit_component(install=[str(uv), "sync"])
    junit_case["fake"].scenario(report=junit([("src/x.test.jsx", "test_ok",
                                               "passed", "", "", "0.1")]))
    run, out = box.full(junit_case["clone"], junit_case["task"],
                         junit_case["profile"])
    assert not run.green, box.note(f"{run}\n{out}")
    assert INSTALL_WITHOUT_LOCK in run.detail, box.note(run.detail)
    assert fake.installs() == [], box.note("uv sync исполнялся")

    case = box.vitest_component()
    case["fake"].fail_install()
    run, out = install_and_deps_full_vitest(box, case)
    assert not run.green, box.note(f"{run}\n{out}")
    assert run.detail.strip(), box.note(str(run))
    assert case["fake"].installs(), box.note("установка не шла")
    assert case["fake"].runs() == [], box.note("прогон после сбоя")


def test_ac16_node_modules_read_only_shared_and_substitution_refused(box):
    """`node_modules` рабочей копии — подключение каталога пульта только для чтения, общее у мест прогона; подмена — отказ.

    Сценарий: компонент `pult-vitest`. После полного прогона
    `node_modules` в `workdir` ведёт в каталог вне клона; запись файла в
    него отказывает (`OSError`). Прогон планки `acceptance.run` и
    полный прогон видят один и тот же каталог `node_modules`. Затем
    `node_modules` заменён собственным каталогом с копией раннера —
    полный прогон не зелёный, раннер не запускался; затем ссылкой на
    копию каталога пульта в другом месте — так же.

    Ловит мутацию: пульт доверяет каталогу дерева — подменённый
    `node_modules` с чужим раннером исполняется, либо каталог пульта
    подключён с правом записи.
    """
    case = box.vitest_component()
    run, out = install_and_deps_full_vitest(box, case)
    assert run.green, box.note(f"{run}\n{out}")
    nm = box.wd_path(case) / "node_modules"
    assert os.path.lexists(nm), box.note("node_modules не подключён")
    pult_dir = os.path.realpath(nm)
    assert not under(pult_dir, case["clone"]), (
        box.note(f"node_modules — каталог дерева: {pult_dir}"))
    with pytest.raises(OSError):
        (nm / f"probe-{box.word()}.txt").write_text("x", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        acceptance.run(box.plank_dir(), cwd=case["clone"],
                       command=case["profile"])
    seen = {r["node_modules"] for r in case["fake"].runs()}
    assert seen == {pult_dir}, box.note(f"каталоги прогонов: {seen}")

    before = len(case["fake"].runs())
    os.unlink(nm) if os.path.islink(nm) else shutil.rmtree(nm)
    (nm / ".bin").mkdir(parents=True)
    shutil.copyfile(case["fake"].wrapper, nm / ".bin" / "vitest")
    (nm / ".bin" / "vitest").chmod(0o755)
    run, out = install_and_deps_full_vitest(box, case)
    assert not run.green, box.note(f"свой каталог: {run}\n{out}")
    assert len(case["fake"].runs()) == before, (
        box.note("исполнен раннер из подменённого каталога"))

    shutil.rmtree(nm)
    copy = Path(tempfile.mkdtemp(prefix="artel-nm-copy-")).resolve()
    box.addCleanup(shutil.rmtree, copy, True)
    box.addCleanup(writable, copy)
    shutil.copytree(pult_dir, copy / "node_modules")
    os.symlink(copy / "node_modules", nm)
    run, out = install_and_deps_full_vitest(box, case)
    assert not run.green, box.note(f"чужая ссылка: {run}\n{out}")
    assert len(case["fake"].runs()) == before, (
        box.note("исполнен раннер по чужой ссылке"))


def test_ac19_watchdog_knows_component_commands_only(box):
    """Сторож признаёт зависшим процесс с командой компонента проекта и не признаёт процесс с чужой командой.

    Сценарий: две записи проектов — компонент `pult-vitest` (базовый
    argv) и компонент `junit-xml` с командой из исполняемого файла и
    флага от зерна; у каждой задача без lease, `cwd` процессов — в
    рабочей копии задачи. `ps` (подменён) называет три процесса старше
    `config.HUNG_TEST_RUN_AGE_SEC`: команда Vitest с флагами пульта,
    команда второго компонента с аргументами и `node server.js`. Находки
    `doctor.check_hung_test_runs` — первые два pid, третьего нет.

    Ловит мутацию: сторож по-прежнему узнаёт только `pytest`/`unittest`
    — процессы компонентов не находятся; либо узнаёт любой процесс в
    рабочей копии задачи — `node server.js` тоже находка.
    """
    vitest = box.vitest_component()
    fake = Fake(box, "hung")
    flag = f"--{box.word(5)}"
    junit_case = box.junit_component(command=[str(fake.wrapper), flag])
    age = int(config.HUNG_TEST_RUN_AGE_SEC) + box.rng.randint(10, 500)
    etime = f"{age // 3600}:{age // 60 % 60:02}:{age % 60:02}"
    pids = {}
    cwds = {}
    rows = []
    for label, case, command in (
            ("vitest", vitest,
             f"node {' '.join(VITEST_BASE)} {REQUIRE_ASSERTIONS} "
             f"--reporter=/x/r.js"),
            ("junit", junit_case,
             f"{fake.wrapper} {flag} --junitxml /tmp/r.xml"),
            ("чужой", vitest, "node server.js --port 3000")):
        pid = box.rng.randint(400_000, 900_000)
        while pid in pids.values():
            pid += 1
        cwd = (config.PROJECTS / case["name"] / "worktrees" / case["task"]
               / (case["wd"] or "."))
        cwd.mkdir(parents=True, exist_ok=True)
        pids[label], cwds[pid] = pid, cwd
        rows.append(f"{pid} {etime} {command}")

    def run(argv, *args, **kwargs):
        argv = [str(a) for a in argv]
        if argv[:2] == ["ps", "-axww"]:
            return subprocess.CompletedProcess(argv, 0, "\n".join(rows) + "\n", "")
        if argv[:1] == ["lsof"]:
            pid = int(argv[argv.index("-p") + 1])
            cwd = cwds.get(pid)
            if cwd is None:
                return subprocess.CompletedProcess(argv, 1, "", "")
            return subprocess.CompletedProcess(argv, 0, f"p{pid}\nn{cwd}\n", "")
        return REAL_RUN(argv, *args, **kwargs)

    with mock.patch.object(subprocess, "run", run):
        checks = doctor.check_hung_test_runs(store.db())
    found = " ".join(c.detail for c in checks if c.status == "fail")
    assert f"pid {pids['vitest']}" in found, box.note(str(checks))
    assert f"pid {pids['junit']}" in found, box.note(str(checks))
    assert f"pid {pids['чужой']}" not in found, box.note(str(checks))


def test_ac4_ac6_pult_pytest_argv_and_outcome_as_main(box):
    """У артели и у записи `test_profile` без `report` argv полного прогона и прогона планки — как на main, итог — по коду и тексту.

    Сценарий: учебная запись `test_profile` без `report` и запись
    артели песочницы (`report: junit-xml`, `runner` — пульта); каналы
    команды — без команды, профиль `decide(...)`, список его команды.
    Вызов pytest подменён (`acceptance.subprocess`). argv
    `run_full_suite` равен argv main (интерпретатор пульта, `tests`,
    флаги пульта, `-n`, `-p xdist`); argv `acceptance.run` — начало
    команды, путь планки, флаги пульта, без `--junitxml`. Код 1 с
    выводом «N failed» — красный прогон полного набора, код 0 — зелёный.

    Ловит мутацию: умолчание `[--junitxml, {path}]` добавляется к
    записи с `report: junit-xml` без различителя — argv артели получает
    `--junitxml`, итог артели читается из отчёта.
    """
    clone, channels = artel_unchanged_channels(box)
    tdir = box.plank_dir()
    for label, command, head_src in channels:
        head = main_head(box, head_src)
        spy = PytestSpy()
        with mock.patch.object(acceptance, "subprocess", spy), \
                contextlib.redirect_stdout(io.StringIO()):
            green, _out = (acceptance.run_full_suite(clone)
                           if command is None else
                           acceptance.run_full_suite(clone, command=command))
            ok, _tail = (acceptance.run(tdir, cwd=clone) if command is None
                         else acceptance.run(tdir, cwd=clone, command=command))
        assert (green and ok), (
            box.note(label) + "; " + f"channel={label!r}")
        full, plank = spy.calls
        assert full == (head + ["tests", *FLAGS, "-n",
                                       str(config.FULL_SUITE_WORKERS),
                                       "-p", "xdist"]), (
            box.note(f"{label}: {full}") + "; " + f"channel={label!r}")
        assert len(plank) == (len(head) + 1 + len(FLAGS)), (
            box.note(f"{label}: {plank}") + "; " + f"channel={label!r}")
        assert plank[:len(head)] == head, (
            box.note(str(plank)) + "; " + f"channel={label!r}")
        assert plank[len(head)].endswith("acceptance_tests"), (
            box.note(str(plank)) + "; " + f"channel={label!r}")
        assert plank[len(head) + 1:] == FLAGS, (
            box.note(str(plank)) + "; " + f"channel={label!r}")
        n = box.rng.randint(1, 9)
        spy = PytestSpy(1, f"{n} failed in 0.1s\n")
        with mock.patch.object(acceptance, "subprocess", spy), \
                contextlib.redirect_stdout(io.StringIO()):
            green, out = (acceptance.run_full_suite(clone)
                          if command is None else
                          acceptance.run_full_suite(clone, command=command))
        assert not green, (
            box.note(f"{label}: {out}") + "; " + f"channel={label!r}")
        assert suite_run.parse(green, out).outcome == acceptance.FULL_SUITE_RED, (
            box.note(out) + "; " + f"channel={label!r}")


def test_ac20_constants_and_texts_as_main(box):
    """Константы исходов, тексты отказа и сводки — значения main.

    Сценарий: сверка значений `acceptance.FULL_SUITE_*`,
    `WORKDIR_REFUSAL`, `REFUSED_EXIT_CODE`, текста сводки без планки и
    текстов отказа `suite-run` записи `test_profile` без `report`:
    не-pytest команда (команда от зерна) и запись без профиля.

    Ловит мутацию: исход «неизвестно» заведён новой константой взамен
    `FULL_SUITE_NOT_STARTED` либо меняет её текст; отказ «не запуск
    pytest» снят и для записи без `report`.
    """
    assert acceptance.FULL_SUITE_GREEN == "зелёный прогон"
    assert acceptance.FULL_SUITE_RED == "красный прогон"
    assert acceptance.FULL_SUITE_TIMEOUT == "таймаут прогона"
    assert acceptance.FULL_SUITE_NO_TESTS == "tests/ нет в worktree"
    assert acceptance.FULL_SUITE_NOT_STARTED == "прогон не начат"
    assert acceptance.FULL_SUITE_NO_TESTS_NOTE == "tests/ нет в worktree — полный набор не проверен"
    assert acceptance.WORKDIR_REFUSAL == "отказ запуска pytest-own: workdir профиля"
    assert acceptance.REFUSED_EXIT_CODE == 4
    empty = Path(tempfile.mkdtemp(prefix="artel-empty-"))
    box.addCleanup(shutil.rmtree, empty, True)
    assert acceptance.summary(empty) == "acceptance_tests/ нет — приёмочные тесты не заведены"
    command = [f"./run-{box.word()}", f"--{box.word(4)}"]
    fields = {"command": command, "long_lived_dir": "tests",
              "long_lived_name": "test_<id>_<name>.py",
              "weakening_scope": ["tests/**"],
              "mutation_claim_scope": ["tests/**"]}
    name, _clone = box.project(fields, {"tests/test_x.py": "# тест\n"})
    bare = f"p{box.word()}"
    box.entries.append(ENTRY_HEAD.format(name=bare))
    box.write_targets()
    make_project_repo(bare, origin=False)
    expected = {
        name: (f"команда профиля тестов проекта «{name}» "
               f"({' '.join(command)}) — не запуск pytest: флаги "
               f"параллели pytest (-n) к ней неприменимы"),
        bare: (f"у проекта «{bare}» нет профиля тестов (test_profile в "
               f"targets.yaml) — команде прогона неоткуда взять команду")}
    for project, refusal in expected.items():
        task = box.task(project)
        with pytest.raises(SystemExit) as raised, \
                contextlib.redirect_stdout(io.StringIO()):
            suite_run.cmd_suite_run([task])
        assert str(raised.value.code) == (f"[{task}] suite-run: отказ — {refusal}; "
                         f"прогон не запускался"), (
            box.note(project) + "; " + f"project={project!r}")


def test_ac12_suite_run_no_report_non_pytest_refusal_as_main(box):
    """`suite-run` записи `test_profile` без `report` с не-pytest командой отказывает прежним текстом.

    Сценарий: запись `test_profile` без `report` с командой из
    исполняемого файла `./tool-<зерно>` и флага; `suite_run.cmd_suite_run`
    завершается `SystemExit` с текстом «… — не запуск pytest: флаги
    параллели pytest (-n) к ней неприменимы; прогон не запускался».

    Ловит мутацию: признак «итог из отчёта» смотрит на команду, а не на
    `report`, — запись без `report` с не-pytest командой больше не
    отказывает и уходит в прогон.
    """
    command = [f"./tool-{box.word()}", "--ci"]
    fields = {"command": command, "long_lived_dir": "tests",
              "long_lived_name": "test_<id>_<name>.py",
              "weakening_scope": ["tests/**"],
              "mutation_claim_scope": ["tests/**"]}
    name, _clone = box.project(fields, {"tests/test_x.py": "# тест\n"})
    task = box.task(name)
    with pytest.raises(SystemExit) as raised, \
            contextlib.redirect_stdout(io.StringIO()):
        suite_run.cmd_suite_run([task])
    assert ("— не запуск pytest: флаги параллели pytest (-n) к ней "
                  "неприменимы; прогон не запускался") in str(raised.value.code), (
        box.note())


def test_ac20_parsing_digest_journal_and_suite_run_lines_as_main(box):
    """Разбор вывода pytest, выжимка, строки журнала полного набора и строки `suite-run` артели — как на main.

    Сценарий: вывод pytest с упавшим, ошибкой и подтестом (имена и
    сообщения от зерна). `run_summary_line`, `failed_test_lines`,
    `failed_entries`, `short_summary_block`, `subtest_parents`,
    `run_digest` — значения разбора main; без итоговой строки выжимка —
    хвост вывода. `full_suite` задачи артели (вызов pytest подменён):
    зелёный, красный и таймаут — строки журнала «полный набор tests/
    зелёный|красный: <выжимка> (лог прогона: <путь>)» и «прогон
    полного набора tests/ превысил {N}с — … (источник: …)».
    `suite_run.parse` и `render` — строки «[<id>] suite-run №<n>
    (полный набор): красный прогон», «прошло: N, упало: M, пропущено:
    K», «полный лог: <путь>».

    Ловит мутацию: разбор итога артели переведён на отчёт —
    `full_suite` артели теряет итоговую строку pytest в выжимке, а
    `suite-run` считает «прошло/упало» не по итоговой строке.
    """
    out, entries, (unit, parent), summary, lines = pytest_output(
        box.rng, box.word)
    assert acceptance.run_summary_line(out) == summary
    assert acceptance.failed_test_lines(out) == lines
    assert acceptance.failed_entries(out) == entries
    assert acceptance.subtest_parents(out) == {unit: parent}
    block_text = acceptance.short_summary_block(out)
    assert block_text.strip().startswith(lines[0]), block_text
    assert summary not in block_text
    assert acceptance.run_digest(out) == "\n".join(lines + [summary])
    tail = f"ошибка сбора {box.word()}\nImportError: x"
    assert acceptance.run_digest(tail) == tail

    (box.root / "tests").mkdir(exist_ok=True)
    task = box.task(config.DEFAULT_TARGET)
    green_out = f"{box.rng.randint(2, 9)} passed in 0.5s\n"
    for label, spy, head in (
            ("зелёный", PytestSpy(0, green_out), "полный набор tests/ зелёный"),
            ("красный", PytestSpy(1, out), "полный набор tests/ красный")):
        with mock.patch.object(acceptance, "subprocess", spy), \
                contextlib.redirect_stdout(io.StringIO()):
            run = acceptance.full_suite(box.root, task, fresh=True)
        text = green_out if label == "зелёный" else out
        assert run.detail == (f"{head}: {acceptance.run_digest(text)} "
                         f"(лог прогона: {run.log_path})"), (
            box.note(label) + "; " + f"outcome={label!r}")
    seconds, source = project_profile.full_suite_limit(config.DEFAULT_TARGET)
    with mock.patch.object(acceptance, "subprocess", PytestSpy(timeout=True)), \
            contextlib.redirect_stdout(io.StringIO()):
        run = acceptance.full_suite(box.root, task, fresh=True)
    assert run.outcome == acceptance.FULL_SUITE_TIMEOUT, str(run)
    assert run.detail.startswith(
        f"прогон полного набора tests/ превысил {seconds}с — завис или "
        f"ждёт сетевой ответ (источник: {source})"), run.detail

    parsed = suite_run.parse(False, out)
    assert ((parsed.outcome, parsed.passed, parsed.failed,
                      parsed.skipped)) == ((acceptance.FULL_SUITE_RED, 1, 2, 0))
    log = box.root / "suite.log"
    report = suite_run.render(task, 3, suite_run.MODE_FULL, parsed, None,
                              "база не нужна", log).splitlines()
    assert report[0] == (f"[{task}] suite-run №3 (полный набор): "
                                f"красный прогон")
    assert report[1] == "прошло: 1, упало: 2, пропущено: 0"
    assert report[-1] == f"полный лог: {log}"
