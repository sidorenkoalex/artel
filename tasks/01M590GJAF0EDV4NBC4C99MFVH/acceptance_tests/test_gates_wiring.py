"""G1б: итог из отчёта у вызывающих прогон (рубеж, сухой сбор, `plank-run`, подтяжка, `suite-run`, `approve`), гейт мержа по компонентам, `checks_local`, ключ итога у входов, приложение инварианта 41.

Группа: разовый

Красен до реализации: вызывающие передают компоненту без `runner` список команды либо ничего — прогон идёт раннером пульта по коду возврата (подменённый pytest зелёный), `approve --accept-red` принимает такой итог, гейт мержа гоняет один профиль и на записи из двух компонентов отказывает `MULTI_COMPONENT_PENDING`, `checks_local` не исполняется, `suite-run` отказывает компоненту «не запуск pytest» и не несёт `tools`, у PLAN нет приложения инварианта 41; отказ `MULTI_COMPONENT_PENDING` на входах гейтов (AC-14), прежний отказ `suite-run` записи без `report` (AC-12) и отсутствие полного прогона без приложений (AC-13) держат поведение main и зелёны с рождения.

Провалидировано временным стабом реализации (модуль в `orchestrator/`,
удалён, не закоммичен): профиль компонента из `decide`, итог из отчёта во
всех местах, `_task_own_profile`/`_profile_command` с профилем компонента,
узел гоняет затронутые компоненты со своими пределами, `checks_local` в
`acceptance_suite` и на гейте мержа — все методы файла зелёные, кроме AC-21:
приложения PLAN до разработчика нет (`artifact_text` — `None`), разбор блоков
приложения сверен на учебном тексте PLAN.

Почему разовый: сценарии опираются на сквозную песочницу вызывающих
`ProfileCallersSandbox` долгоживущего файла задачи 01M52EEHSRD93WMPHWB5VJYRKD
и на песочницу `doctor` задачи 01M58PG72PG64GS790XM2EWS61 (импорт чужого
тестового файла — правило разовой группы, не долгоживущей), на закрытые
узлы гейта мержа (`fsm_merge_gate._full_suite_or_refuse`,
`_profile_refusal_exit`, `_full_suite_command`), `acceptance._task_own_profile`
и `suite_run._profile_command` (ANSWER-2, В5: вызов закрытых узлов — в
разовом файле, прецедент `tests/test_worktree_db_files.py::
MergeGateDbAdviceTest`) и на приложения PLAN.md этой задачи (AC-21).

Учебный проект — внешний проект песочницы с записью `components:`: один
компонент `junit-xml` без `runner` (команда — подменённый раннер
`Fake` долгоживущего файла этой задачи), либо два компонента с `workdir`
и своими пределами. Раннер пишет заранее заданный отчёт JUnit по пути
после `--junitxml` либо не пишет его вовсе (исход «неизвестно»).
`checks_local` — исполняемый файл на Python, пишущий журнал вызовов и
метку в вывод, с кодом 1 по флагу сценария.

AC-21: приложения PLAN читаются из ссылки документов помощником пульта
`artifact_text("PLAN.md")`, применимость — `apply_check`; метод инварианта
гоняется на временном git worktree рабочей копии с наложенными
приложениями. Чувствительность метода к мутациям «"неизвестно" — зелёный»
и «повтор > 0 — зелёный» сверяет ревьювер по заявке «Ловит мутацию: …»
метода (ANSWER-2, В4, вариант A).
"""
import contextlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

from orchestrator import (acceptance, ci, config, fsm, fsm_merge_gate,  # noqa: E402
                          repo_context, stack, store, suite_run, targets,
                          workspace)
# Модулями, не именами классов: класс-песочница, импортированный в
# пространство имён планки, pytest собрал бы как набор тестов.
from tests import test_01m52eehsrd93wmphwb5vjyrkd_profile_callers as callers  # noqa: E402
from tests import test_01m58pg72pg64gs790xm2ews61_doctor_components as doctor_rows  # noqa: E402
from tests.test_01m590gjaf0edv4nbc4c99mfvh_report_outcome import (  # noqa: E402
    Fake, block, junit, writable)

ARTEL, ENTRY, capture_out = callers.ARTEL, callers.ENTRY, callers.capture_out
UNKNOWN_PREFIX = "итог неизвестен: "
COMPONENT = "компонент junit-xml"


class InstanceOnly:
    """Метод, видимый только у экземпляра: у класса — не вызываемый
    объект, и сборщик тестов не принимает его за тест (`tests_dir`
    песочницы прецедента начинается с `test`)."""

    def __init__(self, fn):
        self.fn = fn

    def __get__(self, obj, owner):
        return self if obj is None else self.fn.__get__(obj, owner)

CHECK = r'''import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "checks.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"cwd": os.getcwd(), "argv": sys.argv}) + "\n")
marker = os.path.join(HERE, "marker")
print("lint: " + (open(marker, encoding="utf-8").read() if os.path.exists(marker) else "ok"))
sys.exit(1 if os.path.exists(os.path.join(HERE, "fails")) else 0)
'''

EXT_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: [{prot}/]
    project_skills: []
    merge_gate: operator
    components:
"""


class Check:
    """Поддельная проверка `checks_local`: журнал вызовов, метка вывода,
    провал по флагу."""

    def __init__(self, case: unittest.TestCase):
        self.dir = Path(tempfile.mkdtemp(prefix="artel-check-")).resolve()
        case.addCleanup(shutil.rmtree, self.dir, True)
        self.path = self.dir / "lint"
        self.path.write_text(f"#!{stack.pytest_python_executable()}\n{CHECK}",
                             encoding="utf-8")
        self.path.chmod(self.path.stat().st_mode | stat.S_IXUSR)

    def calls(self) -> int:
        path = self.dir / "checks.jsonl"
        return len(path.read_text(encoding="utf-8").splitlines()) \
            if path.is_file() else 0

    def fail(self, marker: str) -> None:
        (self.dir / "marker").write_text(marker, encoding="utf-8")
        (self.dir / "fails").write_text("1", encoding="utf-8")


class ComponentCallersSandbox(callers.ProfileCallersSandbox):
    """Сквозная песочница вызывающих с внешним проектом на записи
    `components:`."""

    tests_dir = InstanceOnly(callers.ProfileCallersSandbox.tests_dir)

    def setUp(self):
        super().setUp()
        self.addCleanup(writable, self.root)
        self.fake = Fake(self, "callers")
        self.check = Check(self)
        self.comp = f"c{self.word()}"
        self.tools = {f"t{self.word()}": f"1.{self.rng.randint(0, 9)}"}
        self.with_checks = False
        self.write_targets(COMPONENT)

    def single_fields(self) -> dict:
        fields = {"command": [str(self.fake.wrapper)], "long_lived_dir": "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": ["tests/**/*.py"],
                  "mutation_claim_scope": ["tests/test_*.py"],
                  "report": "junit-xml", "report_args": ["--junitxml", "{path}"],
                  "tools": self.tools}
        if self.with_checks:
            fields["checks_local"] = [str(self.check.path)]
        return fields

    def write_targets(self, kind: str, comps: dict | None = None) -> None:
        """`kind` прецедента — как у него; `COMPONENT` — внешний проект с
        записью `components:` (`comps` либо один компонент `junit-xml`)."""
        if kind != COMPONENT:
            super().write_targets(kind)
            return
        self.kind = kind
        artel = ENTRY.format(name=ARTEL, url="http://localhost/artel",
                             base=config.MAIN_BRANCH,
                             no_paths=", ".join(config.PROTECTED_PATHS),
                             command="python3, -m, pytest", lld="tests",
                             extra="      report: junit-xml\n      install: []\n")
        comps = comps or {self.comp: self.single_fields()}
        ext = EXT_HEAD.format(name=self.ext, base=config.MAIN_BRANCH,
                              prot=self.prot)
        for name, fields in comps.items():
            ext += f"      {name}:\n" + block(fields, "        ")
        config.TARGETS.write_text("targets:\n" + artel + ext, encoding="utf-8")
        targets.load()

    def green_report(self, fake: Fake | None = None) -> None:
        (fake or self.fake).scenario(
            stdout="1 passed in 0.01s\n",
            report=junit([("tests/test_x.py", "test_ok", "passed", "", "",
                           "0.01")]))

    def unknown(self) -> None:
        self.fake.scenario(stdout="1 passed in 0.01s\n", report=None)

    def suite_report(self, task: str) -> str:
        """Отчёт завершённого прогона `suite-run` — публичным `--wait`."""
        return capture_out(suite_run.cmd_suite_run, [task, "--wait", "1"])


# ------------------------------------------------------------------ AC-5

class UnknownAtGatesTest(ComponentCallersSandbox):

    def test_ac5_approve_accept_red_refuses_unknown(self):
        """`approve --accept-red` гейта приёмки на исходе «неизвестно» отказывает, задача остаётся в `acceptance`.

        Сценарий: задача внешнего проекта с компонентом `junit-xml` в
        `acceptance`; раннер выходит с кодом 0 и отчёта не пишет. `approve`
        с `--accept-red` — вывод «approve отклонён», состояние прежнее.

        Ловит мутацию: `_task_own_profile` не отдаёт профиль компонента —
        полный набор приёмки идёт раннером пульта и принимается (или
        «неизвестно» выдаётся красным прогоном, который `--accept-red`
        принимает).
        """
        self.unknown()
        task = self.new_task("acceptance", self.code())
        store.record_fixation(self.conn, task)
        with self.spy():
            out = capture_out(fsm.cmd_approve, task,
                              accept_red=f"основание {self.word()}")
        self.assertEqual(self.state(task), "acceptance",
                         self.context(task, out, []))
        self.assertIn("approve отклонён", out, self.context(task, out, []))

    def test_ac5_merge_gate_advice_names_unknown_and_reason(self):
        """Подсказка гейта мержа на исходе «неизвестно» называет исход и причину, а не «повтори, когда машина освободится».

        Сценарий: задача на `merge_gate` с приложением; узел полного прогона
        после приложений `fsm_merge_gate._full_suite_or_refuse` зовётся
        напрямую (уборка scratch подменена), раннер компонента отчёта не
        пишет. Узел завершается `SystemExit`; текст несёт «неизвестно» и
        деталь «итог неизвестен: …», но не «машина освободится».

        Ловит мутацию: ветка «прогон не начат» подсказки гейта мержа одна
        на «замок занят» и «неизвестно» — совет ждать освобождения машины.
        """
        self.unknown()
        task = self.new_task("merge_gate", self.code())
        ctx = repo_context.resolve(self.ext)
        with mock.patch.object(fsm_merge_gate, "_drop_scratch_worktree"), \
                self.assertRaises(SystemExit) as raised, \
                contextlib.redirect_stdout(io.StringIO()):
            fsm_merge_gate._full_suite_or_refuse(
                self.conn, task, [f"{self.prot}/{self.word()}.cfg"],
                self.wt(task), ctx)
        text = str(raised.exception.code)
        self.assertIn("неизвестно", text, self.note(text))
        self.assertIn(UNKNOWN_PREFIX, text, self.note(text))
        self.assertNotIn("машина освободится", text, self.note(text))


# ------------------------------------------------------------ AC-11, AC-12

class UnknownAtCallersTest(ComponentCallersSandbox):

    def test_ac11_callers_never_green_on_unknown(self):
        """Исход «неизвестно» компонента `junit-xml` не зелёный у вызывающих: рубеж `in_dev`, сухой сбор `tests_writing`, `plank-run`, подтяжка main, `suite-run`.

        Сценарий: раннер компонента выходит с кодом 0, печатает «1 passed» и
        отчёта не пишет; вызов pytest пульта подменён зелёным (если место
        пойдёт мимо профиля компонента — оно получит зелёный итог). Рубеж:
        `advance` из `in_dev` — задача осталась в `in_dev`. Сухой сбор:
        `advance` из `tests_writing` — осталась. `plank-run` — код выхода
        не 0. `pull-main` из `verifying` — задача эскалирована (красная
        планка после подтяжки). `suite-run` — строка отчёта не «зелёный
        прогон».

        Ловит мутацию: вызывающий (`advance_gates/acceptance.py`,
        `advance_gates/tests_writing.py`, `plank_run`, `pull`) передаёт
        профиль компонента только при `runner: pytest-own` — компонент без
        `runner` идёт раннером пульта и получает зелёный итог.
        """
        self.unknown()
        task, out, _plank, _repeats = self.run_in_dev()
        self.assertEqual(self.state(task), "in_dev", self.context(task, out, []))
        task, out, _calls = self.run_tests_writing(False)
        self.assertEqual(self.state(task), "tests_writing",
                         self.context(task, out, []))
        task, out, _calls = self.run_plank_run()
        self.assertNotIn("код выхода pytest: 0", out, self.context(task, out, []))
        task, out, _calls = self.run_pull(False)
        self.assertEqual(self.state(task), "escalated", self.context(task, out, []))
        task, out, _calls = self.run_suite_run()
        out += self.suite_report(task)
        line = [ln for ln in out.splitlines()
                if f"[{task}] suite-run №" in ln and "запущен" not in ln]
        self.assertTrue(line, self.context(task, out, []))
        self.assertNotIn(acceptance.FULL_SUITE_GREEN, line[-1],
                         self.context(task, out, []))

    def test_ac12_suite_run_component_non_pytest_no_xdist(self):
        """`suite-run` компонента с отчётом и не-pytest командой не отказывает «не запуск pytest» и не добавляет `-n`.

        Сценарий: компонент `junit-xml` с командой — подменённым раннером
        (не pytest), раннер пишет зелёный отчёт. `suite-run` задачи: в
        выводе нет «не запуск pytest», раннер запускался, его argv не несёт
        `-n`; отчёт — «зелёный прогон».

        Ловит мутацию: `_profile_command` по-прежнему зовёт `_is_pytest` для
        любой команды — компонент получает отказ; либо флаги параллели
        pytest добавляются к команде компонента.
        """
        self.green_report()
        task, out, _calls = self.run_suite_run()
        out += self.suite_report(task)
        context = self.context(task, out, [])
        self.assertNotIn("не запуск pytest", out, context)
        runs = self.fake.runs()
        self.assertTrue(runs, context)
        for record in runs:
            self.assertNotIn("-n", record["args"], self.note(str(record["args"])))
        self.assertIn(f"(полный набор): {acceptance.FULL_SUITE_GREEN}", out, context)

    def test_ac12_suite_run_no_report_non_pytest_refusal_kept(self):
        """`suite-run` записи `test_profile` без `report` с не-pytest командой отказывает прежним текстом.

        Сценарий: внешний проект переписан на `test_profile` без `report` с
        командой — подменённым раннером. `suite-run` завершается отказом
        «… — не запуск pytest: флаги параллели pytest (-n) к ней
        неприменимы», раннер не запускался.

        Ловит мутацию: признак «не pytest» снят для всех записей, а не
        только для компонентов с отчётом.
        """
        self.kind = "без report"
        text = config.TARGETS.read_text(encoding="utf-8")
        head, _sep, _rest = text.partition(f"  {self.ext}:\n")
        ext = ENTRY.format(name=self.ext, url=f"file:///nonexistent/{self.ext}",
                           base=config.MAIN_BRANCH, no_paths=f"{self.prot}/",
                           command=str(self.fake.wrapper), lld="tests", extra="")
        config.TARGETS.write_text(head + ext, encoding="utf-8")
        task = self.new_task("in_dev", self.code())
        out = capture_out(suite_run.cmd_suite_run, [task])
        self.assertIn("— не запуск pytest: флаги параллели pytest (-n) к ней "
                      "неприменимы", out, self.note(out))
        self.assertEqual(self.fake.runs(), [], self.note(out))


# ------------------------------------------------------------ AC-13, AC-14

class MergeGateComponentsTest(ComponentCallersSandbox):

    def two_components(self, limits=(30, 30)) -> dict:
        """Запись из двух компонентов `junit-xml` с `workdir`, своими
        раннерами и пределами; файлы каталогов — в main проекта."""
        self.fakes = {"a": Fake(self, "comp-a"), "b": Fake(self, "comp-b")}
        self.dirs = {"a": f"a{self.word(5)}", "b": f"b{self.word(5)}"}
        self.names = {"a": f"a{self.word()}", "b": f"b{self.word()}"}
        comps = {}
        for key, limit in zip(("a", "b"), limits):
            regex = (f"^({self.dirs['a']}|kod)/" if key == "a"
                     else f"^{self.dirs['b']}/")
            comps[self.names[key]] = {
                "command": [str(self.fakes[key].wrapper)],
                "weakening_scope": [f"{self.dirs[key]}/**"],
                "mutation_claim_scope": [f"{self.dirs[key]}/**"],
                "report": "junit-xml", "report_args": ["--junitxml", "{path}"],
                "workdir": self.dirs[key], "full_suite_timeout_sec": limit,
                "paths": regex}
        self.write_targets(COMPONENT, comps)
        self.commit_to_main(self.ext_clone, {
            f"{self.dirs['a']}/test_a.txt": "a\n",
            f"{self.dirs['b']}/test_b.txt": "b\n"})
        for key in ("a", "b"):
            self.green_report(self.fakes[key])
        return comps

    def gate(self, task: str, paths: list) -> str | None:
        """Узел полного прогона после приложений `paths` (файлы приложения
        закоммичены в scratch — рабочую копию задачи); текст отказа или
        `None`."""
        scratch = self.wt(task)
        for rel in paths:
            (scratch / rel).parent.mkdir(parents=True, exist_ok=True)
            (scratch / rel).write_text(f"# {self.word()}\n", encoding="utf-8")
        self.git("-C", str(scratch), "add", "--", *paths)
        self.git("-C", str(scratch), "commit", "-q", "-m", "приложения")
        ctx = repo_context.resolve(self.ext)
        try:
            with mock.patch.object(fsm_merge_gate, "_drop_scratch_worktree"), \
                    contextlib.redirect_stdout(io.StringIO()):
                fsm_merge_gate._full_suite_or_refuse(self.conn, task, paths,
                                                     scratch, ctx)
        except SystemExit as exc:
            return str(exc.code)
        return None

    def runs(self, key: str) -> int:
        return len(self.fakes[key].runs())

    def test_ac13_ac14_both_components_run_green_only_if_both_green(self):
        """Узел полного прогона гейта мержа на записи из двух компонентов гоняет оба; зелёный — только если зелёны оба.

        Сценарий: учебная запись из двух компонентов `junit-xml` (имена,
        каталоги от зерна); ветка задачи трогает компонент A (`kod/…`),
        приложение PLAN — путь компонента B. Вызов узла напрямую: оба
        раннера запускались, отказа нет. Затем раннер A пишет отчёт с
        провалом — отказ мержа; затем A зелёный, B с провалом — отказ.

        Ловит мутацию: узел гоняет только первый компонент записи (или
        компонент, выбранный по одному диффу ветки без путей приложений), а
        итог — по последнему прогнанному.
        """
        self.two_components()
        task = self.new_task("merge_gate", self.code())
        refusal = self.gate(task, [f"{self.dirs['b']}/conf_{self.word()}.txt"])
        context = self.note(f"отказ: {refusal}")
        self.assertIsNone(refusal, context)
        self.assertEqual((self.runs("a"), self.runs("b")), (1, 1), context)
        failed = junit([("t.py", "test_bad", "failed", "AssertionError", "x", "0.1")])
        for red in ("a", "b"):
            with self.subTest(red=red):
                for key in ("a", "b"):
                    if key == red:
                        self.fakes[key].scenario(report=failed)
                    else:
                        self.green_report(self.fakes[key])
                task = self.new_task("merge_gate", self.code())
                refusal = self.gate(task, [f"{self.dirs['b']}/c{self.word()}.txt"])
                self.assertIsNotNone(refusal, self.note(f"красный {red} — мерж прошёл"))

    def test_ac13_limit_per_component_and_selection_by_appendix_paths(self):
        """Предел каждого прогона — `full_suite_timeout_sec` своего компонента; компонент, не затронутый ни веткой, ни приложением, не гоняется.

        Сценарий: компонент A (первый в записи) — предел 30 с, раннер спит
        2 с и пишет зелёный отчёт; компонент B — предел 1 с, раннер спит
        дольше. Ветка трогает A, приложение — B: раннер A доспал паузу (его
        предел — не 1 с B), мерж отклонён таймаутом B, и текст отказа
        называет предел B — 1 с. Затем B зелёный, приложение — путь A:
        раннер B не запускался.

        Ловит мутацию: предел полного набора берётся один на запись
        (последнего или первого компонента, `config`) — A оборван через 1 с
        либо таймаут B назван чужим пределом; либо узел гоняет все
        компоненты записи независимо от путей.
        """
        self.two_components(limits=(30, 1))
        self.fakes["a"].scenario(sleep=2, report=junit([
            ("t.py", "test_ok", "passed", "", "", "0.1")]))
        self.fakes["b"].scenario(sleep=60, report=None)
        task = self.new_task("merge_gate", self.code())
        refusal = self.gate(task, [f"{self.dirs['b']}/conf_{self.word()}.txt"])
        self.assertIsNotNone(refusal, self.note("таймаут B не отказал мержу"))
        self.assertEqual(self.fakes["a"].slept(), 1,
                         self.note(f"A оборван чужим пределом: {refusal}"))
        self.assertRegex(refusal, r"(?<![\d.])1\s?с", self.note(
            f"отказ не называет предел B: {refusal}"))
        self.green_report(self.fakes["b"])
        self.fakes["a"].scenario(report=junit([("t.py", "test_ok", "passed", "",
                                                "", "0.1")]))
        before = self.runs("b")
        task = self.new_task("merge_gate", self.code())
        refusal = self.gate(task, [f"{self.dirs['a']}/conf_{self.word()}.txt"])
        self.assertIsNone(refusal, self.note(str(refusal)))
        self.assertEqual(self.runs("b"), before,
                         self.note("незатронутый компонент B прогонялся"))

    def test_ac13_no_appendices_no_full_run_at_merge_gate(self):
        """Без приложений полного прогона на гейте мержа нет.

        Сценарий: запись с одним компонентом `junit-xml`; задача на
        `merge_gate` без приложений PLAN; `approve` проводит мерж — раннер
        компонента ни разу не запускался.

        Ловит мутацию: на гейте мержа введён безусловный полный прогон по
        затронутым компонентам.
        """
        self.green_report()
        task = self.new_task("merge_gate", self.code())
        store.record_fixation(self.conn, task)
        with self.spy():
            out = capture_out(fsm.cmd_approve, task)
        self.assertEqual(self.state(task), "done", self.context(task, out, []))
        self.assertEqual(self.fake.runs(), [], self.context(task, out, []))

    def test_ac14_multi_component_refused_at_gate_entries(self):
        """Запись из двух компонентов отказывается `MULTI_COMPONENT_PENDING` на входе гейта мержа, в `_task_own_profile` и в `suite-run`.

        Сценарий: учебная запись из двух компонентов; задача проекта.
        `fsm_merge_gate._profile_refusal_exit` — `SystemExit` с причиной;
        `acceptance._task_own_profile` — `targets.ComponentsPending`;
        `suite-run` — отказ с причиной.

        Ловит мутацию: отказ снят на входах гейтов вместе с прогоном по
        компонентам в узлах — сквозной путь записи из двух компонентов
        открыт раньше G3а/G3б.
        """
        self.two_components()
        task = self.new_task("in_dev", self.code())
        with self.assertRaises(SystemExit) as raised, \
                contextlib.redirect_stdout(io.StringIO()):
            fsm_merge_gate._profile_refusal_exit(self.conn, task, self.ext)
        self.assertIn(targets.MULTI_COMPONENT_PENDING, str(raised.exception.code))
        with self.assertRaises(targets.ComponentsPending):
            acceptance._task_own_profile(self.conn, task)
        out = capture_out(suite_run.cmd_suite_run, [task])
        self.assertIn(targets.MULTI_COMPONENT_PENDING, out, self.note(out))


class DoctorPendingTest(doctor_rows.DoctorComponentsSandbox):

    def test_ac14_doctor_timeout_row_pending_for_two_components(self):
        """Строка предела `full-suite-timeout-<проект>` у `doctor` для записи из двух компонентов — `skip` с `MULTI_COMPONENT_PENDING`.

        Сценарий: учебная запись из двух компонентов (поля прецедента);
        `doctor` печатает строку предела проекта `skip`, причина — отказ
        `MULTI_COMPONENT_PENDING`.

        Ловит мутацию: строка предела `doctor` считает предел по компоненту
        и печатает `ok` — отказ на этом входе снят.
        """
        project = f"p{self.word()}"
        self.add_components(project, {
            f"a{self.word(5)}": self.minimal(f"^{self.word(5)}/"),
            f"b{self.word(5)}": self.minimal(f"^{self.word(5)}/")})
        self.write_targets()
        rows, out = self.run_doctor()
        detail = self.assert_status(rows, f"full-suite-timeout-{project}",
                                    "skip", out)
        self.assertIn(targets.MULTI_COMPONENT_PENDING, detail, self.note(detail))


# ------------------------------------------------------------------ AC-17

class ChecksLocalTest(ComponentCallersSandbox):

    def setUp(self):
        super().setUp()
        self.with_checks = True
        self.write_targets(COMPONENT)
        self.green_report()

    def suite(self, task: str, actor: str):
        t = store.get_task(self.conn, task)
        # Вызов pytest пульта подменён зелёным: место, ушедшее мимо профиля
        # компонента, проверку не гоняет и красноты не даёт.
        with self.spy(), contextlib.redirect_stdout(io.StringIO()):
            return acceptance.acceptance_suite(
                self.conn, self.wt(task), task, t["branch"],
                workspace.task_repo(task), actor=actor)

    def test_ac17_checks_local_in_acceptance_suite_both_actors_and_ci(self):
        """`checks_local` исполняются в `acceptance.acceptance_suite` при `actor="operator"` и `actor="fsm"`, и когда итог полного набора принят из CI или взят повторно.

        Сценарий: компонент `junit-xml` с `checks_local` (поддельная
        проверка); раннер пишет зелёный отчёт. Узел с `actor="operator"`,
        затем `actor="fsm"` (второй вызов на том же дереве — итог может
        быть взят повторно) — проверка исполнялась каждый раз. Затем итог
        CI головы ветки подменён принятым (`ci.head_sha`,
        `ci.accepted_full_suite`): узел принимает итог CI (раннер не
        запускался) — проверка всё равно исполнялась.

        Ловит мутацию: `checks_local` исполняются только рядом со свежим
        локальным прогоном — итог из CI или кэша проходит без проверок.
        """
        task = self.new_task("acceptance", self.code())
        for n, actor in enumerate(("operator", "fsm"), 1):
            run = self.suite(task, actor)
            self.assertTrue(run.green, self.note(f"{actor}: {run}"))
            self.assertEqual(self.check.calls(), n, self.note(actor))
        sha = self.git("-C", str(self.wt(task)), "rev-parse", "HEAD").strip()
        runs_before = len(self.fake.runs())
        with mock.patch.object(ci, "head_sha", lambda branch, repo=None: (sha, "")), \
                mock.patch.object(ci, "accepted_full_suite",
                                  lambda sha, repo=None: ("4242", "")):
            run = self.suite(task, "fsm")
        self.assertTrue(run.green, self.note(str(run)))
        self.assertIn("принят итог CI", run.detail, self.note(run.detail))
        self.assertEqual(len(self.fake.runs()), runs_before,
                         self.note("набор гонялся локально, путь CI не пройден"))
        self.assertEqual(self.check.calls(), 3, self.note("проверка не шла при итоге CI"))

    def test_ac17_failing_check_red_with_output(self):
        """Ненулевой код проверки — красный итог узла приёмки с выводом проверки в тексте.

        Сценарий: проверка выходит с кодом 1 и печатает метку от зерна;
        набор зелёный. `acceptance_suite` — не зелёный, метка видна в
        детали итога.

        Ловит мутацию: код проверки не влияет на итог, либо её вывод не
        попадает в текст итога.
        """
        marker = f"LINT-{self.word(8)}"
        self.check.fail(marker)
        task = self.new_task("acceptance", self.code())
        run = self.suite(task, "operator")
        self.assertFalse(run.green, self.note(str(run)))
        self.assertIn(marker, f"{run.detail}\n{run.digest}", self.note(str(run)))

    def test_ac17_checks_local_at_merge_gate_with_and_without_full_run(self):
        """`checks_local` исполняются на гейте мержа — без приложений (прогона нет) и с приложением; провал проверки останавливает мерж.

        Сценарий: `approve` задачи на `merge_gate` без приложений — мерж
        проведён, проверка исполнялась. Задача с приложением к защищённому
        пути проекта — проверка исполнялась (вместе с полным прогоном).
        Проверка с кодом 1 и меткой — мерж отклонён, задача на
        `merge_gate`, метка в выводе.

        Ловит мутацию: `checks_local` исполняются только в узле приёмки, а
        гейт мержа их не зовёт — либо зовёт только рядом с полным прогоном
        после приложений.
        """
        task = self.new_task("merge_gate", self.code())
        store.record_fixation(self.conn, task)
        with self.spy():
            out = capture_out(fsm.cmd_approve, task)
        self.assertEqual(self.state(task), "done", self.context(task, out, []))
        self.assertEqual(self.check.calls(), 1, self.context(task, out, []))
        task, out, _calls = self.run_merge_gate(False)
        self.assertEqual(self.check.calls(), 2, self.context(task, out, []))
        marker = f"LINT-{self.word(8)}"
        self.check.fail(marker)
        task = self.new_task("merge_gate", self.code())
        store.record_fixation(self.conn, task)
        with self.spy():
            out = capture_out(fsm.cmd_approve, task)
        self.assertEqual(self.state(task), "merge_gate", self.context(task, out, []))
        self.assertIn(marker, out, self.context(task, out, []))


# ------------------------------------------------------------------ AC-18

class KeyEntriesTest(ComponentCallersSandbox):

    def test_ac18_same_key_at_merge_gate_and_suite_run_with_tools(self):
        """Ключ итога полного набора одинаков у входа гейта мержа и у `suite-run`; профиль `suite-run` несёт `tools` компонента.

        Сценарий: компонент `junit-xml` с `tools` (имя и версия от зерна);
        рабочая копия задачи. Команда гейта мержа —
        `fsm_merge_gate._full_suite_command`, профиль `suite-run` —
        `suite_run._profile_command`; `tools` профиля `suite-run` равны
        объявленным; `acceptance.suite_result_key` дерева рабочей копии у
        обоих равны.

        Ловит мутацию: `_profile_command` строит профиль без
        `project_profile.with_tools` — ключ `suite-run` без `tools` и не
        совпадает с ключом гейта мержа.
        """
        task = self.new_task("merge_gate", self.code())
        wt = self.wt(task)
        ctx = repo_context.resolve(self.ext)
        with contextlib.redirect_stdout(io.StringIO()):
            needed, gate_command = fsm_merge_gate._full_suite_command(
                self.conn, task, [f"{self.prot}/x.cfg"], wt, ctx)
        command, refusal = suite_run._profile_command(self.ext)
        self.assertEqual(refusal, "", self.note(refusal))
        self.assertEqual(dict(getattr(command, "tools", {}) or {}), self.tools,
                         self.note(f"tools профиля suite-run: {command!r}"))
        tree = acceptance.suite_tree_hash(wt)
        self.assertIsNotNone(tree, self.note("дерево не снято"))
        gate_key = acceptance.suite_result_key(tree, gate_command, root=wt)
        run_key = acceptance.suite_result_key(tree, command, root=wt)
        self.assertIsNotNone(gate_key, self.note("ключа гейта нет"))
        self.assertEqual(gate_key, run_key, self.note("ключи входов различны"))


# ------------------------------------------------------------------ AC-21

DIFF_BLOCK = re.compile(r"```diff\n(.*?)```", re.DOTALL)
INVARIANTS = "docs/invariants.md"
INVARIANT_TESTS = "tests/test_invariants.py"


def touched(diff: str) -> set:
    return set(re.findall(r"^diff --git a/(\S+) b/", diff, re.MULTILINE))


class Invariant41AppendixTest(unittest.TestCase):

    def test_ac21_invariant_41_appendix_applies_and_check_is_green(self):
        """Инвариант 41 — строка `docs/invariants.md` и метод `tests/test_invariants.py` в приложениях PLAN; приложения применимы, метод зелёный на дереве с ними.

        Сценарий: PLAN.md из ссылки документов (`artifact_text`); его
        блоки ```diff, трогающие `docs/invariants.md` и
        `tests/test_invariants.py`. Каждый проходит `apply_check` на
        чистом дереве HEAD. Добавленные строки `docs/invariants.md` несут
        «41»; добавленные строки `tests/test_invariants.py` — новый метод
        `test_…`. Во временном git worktree HEAD рабочей копии приложения
        наложены `git apply`, новые методы прогнаны pytest — код 0.
        Чувствительность методов к мутациям «"неизвестно" — зелёный» и
        «повтор > 0 — зелёный» сверяет ревьювер (ANSWER-2, В4).

        Ловит мутацию: инвариант 41 вписан прямо в ветку (приложения нет),
        хедер хунка приложения не совпадает с файлом main (`apply_check`
        отказывает), либо метод инварианта красен на дереве с приложением.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md в ссылке документов нет")
        blocks = [b for b in DIFF_BLOCK.findall(plan)
                  if touched(b) & {INVARIANTS, INVARIANT_TESTS}]
        paths = set().union(*(touched(b) for b in blocks)) if blocks else set()
        self.assertIn(INVARIANTS, paths, "нет приложения к docs/invariants.md")
        self.assertIn(INVARIANT_TESTS, paths, "нет приложения к tests/test_invariants.py")
        added_doc, methods = [], []
        for diff in blocks:
            self.assertEqual(apply_check(diff), "", f"приложение не применимо:\n{diff[:500]}")
            current = None
            for line in diff.splitlines():
                if line.startswith("diff --git a/"):
                    current = line.split()[2][2:]
                elif line.startswith("+") and not line.startswith("+++"):
                    if current == INVARIANTS:
                        added_doc.append(line)
                    elif current == INVARIANT_TESTS:
                        found = re.match(r"\+\s+def (test_\w+)\(", line)
                        if found:
                            methods.append(found.group(1))
        self.assertTrue(any("41" in line for line in added_doc),
                        f"строки инварианта 41 нет: {added_doc}")
        self.assertTrue(methods, "нового метода в tests/test_invariants.py нет")

        tmp = Path(tempfile.mkdtemp(prefix="artel-inv41-")).resolve()
        tree = tmp / "tree"
        try:
            subprocess.run(["git", "-C", CODE_ROOT, "worktree", "add", "-q",
                            "--detach", str(tree), "HEAD"], check=True,
                           capture_output=True, text=True)
            for n, diff in enumerate(blocks):
                patch = tmp / f"appendix-{n}.diff"
                patch.write_text(diff, encoding="utf-8")
                res = subprocess.run(["git", "-C", str(tree), "apply", str(patch)],
                                     capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, res.stderr)
            env = {k: v for k, v in os.environ.items()
                   if k not in ("PYTHONPATH", config.ARTEL_ROLE_ENV)}
            res = subprocess.run(
                [stack.pytest_python_executable(), "-m", "pytest",
                 INVARIANT_TESTS, "-k", " or ".join(methods),
                 "-p", "no:cacheprovider", "-q"],
                cwd=tree, env=env, capture_output=True, text=True, timeout=600)
            self.assertEqual(res.returncode, 0,
                             f"метод инварианта 41 не зелёный:\n"
                             f"{(res.stdout + res.stderr)[-3000:]}")
        finally:
            subprocess.run(["git", "-C", CODE_ROOT, "worktree", "remove",
                            "--force", str(tree)], capture_output=True)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
