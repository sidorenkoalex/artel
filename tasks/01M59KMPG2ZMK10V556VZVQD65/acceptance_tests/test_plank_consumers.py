"""G2а-1: правило планки компонента у потребителей — чекпоинт, выход из `tests_writing`, `preflight`, `amend-tests`, сухой прогон, автогейт, сводка, документы перед мержем; сторож предпроверки.

Группа: разовый

Красен до реализации: потребители читают планку прежним фильтром `.py`/`test_*.py` и прежним разбором `def test_ac<n>_`/`# AC-<n>:` — чекпоинт отбрасывает `a.test.jsx` и `_util.jsx`, трассируемость не видит `it('AC-n: …')` и `// AC-n:`, маркер красноты `.jsx` не проверяется, автогейт видит «каталог пуст» вместо отказа по правилу компонента, сводка и сухой прогон не считают `.jsx`, документы перед мержем при `guard_rules=False` молчат, отказ построения правила (компонент `pult-vitest` без `tests`) нигде не назван; области чтения и тексты артели (AC-15) и неизменность сторожа предпроверки (AC-14) держат поведение main и зелёны с рождения.

Почему разовый: сценарии зовут закрытые узлы, которые SPEC называет
поимённо (`fsm_autogate._maybe_autogate_acceptance`,
`fsm_merge_gate._task_docs_violations`,
`fsm_merge_gate._guard_task_docs_or_refuse`), подменяют сбор и прогон
планки у `amend-tests` и опираются на сквозную песочницу вызывающих
`ProfileCallersSandbox` долгоживущего файла задачи
01M52EEHSRD93WMPHWB5VJYRKD (импорт чужого тестового файла — правило
разовой группы; прецедент — планка задачи 01M590GJAF0EDV4NBC4C99MFVH,
`test_gates_wiring.py`). AC-14 — факт этой задачи (дифф ветки).

Песочница: клон артели и клон внешнего проекта с bare `origin`, ссылка
документов — автокоммитом шага (`checkpoint.commit_step_artifacts`).
Запись внешнего проекта в `targets.yaml` — по сценарию:
- `vitest` — один компонент `pult-vitest` с `tests:
  [web/src/**/*.test.jsx]` (места через `decide`: переход, `preflight`,
  `amend-tests`);
- `vitest-bad` — один компонент `pult-vitest` без `tests` (имя случайное);
- `two` — учебный проект из двух компонентов: `junit-xml` на pytest и
  `pult-vitest` с `tests` (чекпоинт, сухой прогон, автогейт, сводка,
  документы перед мержем);
- `two-bad` — те же два компонента, у `pult-vitest` нет `tests`;
- `junit` — один компонент `junit-xml` на pytest (правило по умолчанию).

Подменены только внешние ответы: прогон pytest у мест запуска (подменённый
`subprocess` песочницы), политика гейта acceptance у автогейта
(`gates.policy`), у `amend-tests` — `acceptance.collect`/`acceptance.run`
(прогон планки компонента — предмет G2а-2, здесь нужен только исход: сбор
прошёл, прогон зелёный или красный). Путь «диск» выхода из
`tests_writing` — подменой `artifact_branch.on_foreign_rev` на `False`
(файлы — в `config.TASKS/<id>/`), путь «ветка» — ссылка документов
песочницы как есть.

Имена компонентов, файлов и тексты причин — из `random` песочницы (зерно
печатается и входит в текст провала).

Провалидировано временным стабом реализации (удалён, не закоммичен):
`PlankRule`/`DEFAULT_PLANK_RULE` и разбор меток/пометок/первого
комментария в `guard`, `plank_rule` в `project_profile`, правило у
чекпоинта, `_tests_writing_ac_state` (оба пути), `preflight`,
`amend-tests` (рабочая копия и `--from-branch`), сухого прогона,
`_plank_sources`/`_autogate_conditions`, `summary` и
`_task_docs_violations`/`_guard_task_docs_or_refuse` — все методы файла
зелёные, кроме AC-14: стаб перевёл ветку перехода на новую функцию
красноты, которой нет в `preflight`, и сторож предпроверки честно упал
(ровно та поломка, которую держит AC-14).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

from orchestrator import (acceptance, amend, artifact_branch, checkpoint,  # noqa: E402
                          config, dry_run, fsm, fsm_autogate, fsm_merge_gate,
                          gates, preflight, repo_context, store, workspace)
from scripts import guard  # noqa: E402
# Модулем, не именами классов: класс-песочница, импортированный в
# пространство имён планки, pytest собрал бы как набор тестов.
from tests import test_01m52eehsrd93wmphwb5vjyrkd_profile_callers as callers  # noqa: E402

ARTEL = callers.ARTEL
capture_out = callers.capture_out
SENTINEL_FILE = "tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py"

VITEST = "vitest"
VITEST_BAD = "vitest-bad"
TWO = "two"
TWO_BAD = "two-bad"
JUNIT = "junit"

VITEST_COMMAND = "node_modules/.bin/vitest, run, --config, vitest.config.js, " \
                 "--allowOnly=false, --update=false, --retry=0"
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
VITEST_SINGLE = """      {comp}:
        command: [{command}]
        long_lived_dir: web/src
        long_lived_name: <id>_<name>.test.js
        weakening_scope: [web/src/**]
        mutation_claim_scope: [web/src/**]
        report: pult-vitest
{tests}"""
VITEST_MULTI = """      {comp}:
        command: [{command}]
        paths: [^web/]
        weakening_scope: [web/src/**]
        mutation_claim_scope: [web/src/**]
        report: pult-vitest
{tests}"""
JUNIT_SINGLE = """      {comp}:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
        weakening_scope: [tests/**/*.py]
        mutation_claim_scope: [tests/test_*.py]
        report: junit-xml
"""
JUNIT_MULTI = """      {comp}:
        command: [python3, -m, pytest]
        paths: [^back/]
        weakening_scope: [back/tests/**/*.py]
        mutation_claim_scope: [back/tests/test_*.py]
        report: junit-xml
"""
TESTS_LINE = "        tests: [web/src/**/*.test.jsx]\n"

SECOND_AC = "AC-2. Второй фикстурный критерий.\n"
REDNESS_LINE = "// Красен до реализации: фикстура песочницы.\n"
IMPORTS = "import { describe, expect, it, test } from 'vitest';\n"
TRACE_ACTION = "переход отклонён: трассируемость AC"
AUTOGATE_REFUSED = "автогейт acceptance не пройден"


class InstanceOnly:
    """Метод, видимый только у экземпляра: у класса — не вызываемый
    объект, и сборщик тестов не принимает его за тест (`tests_dir`
    песочницы прецедента начинается с `test`)."""

    def __init__(self, fn):
        self.fn = fn

    def __get__(self, obj, owner):
        return self if obj is None else self.fn.__get__(obj, owner)


def jsx(body: str, marker: bool = True) -> str:
    return (REDNESS_LINE if marker else "// без маркера\n") + IMPORTS + "\n" + body


class PlankConsumersSandbox(callers.ProfileCallersSandbox):
    """Сквозная песочница вызывающих с записью `components:` внешнего
    проекта по сценарию."""

    tests_dir = InstanceOnly(callers.ProfileCallersSandbox.tests_dir)

    def setUp(self):
        super().setUp()
        self.vite_comp = f"v{self.word()}"
        self.junit_comp = f"j{self.word()}"

    def write_targets(self, kind: str) -> None:
        if kind not in (VITEST, VITEST_BAD, TWO, TWO_BAD, JUNIT):
            super().write_targets(kind)
            return
        super().write_targets(callers.OWN)
        self.kind = kind
        text = config.TARGETS.read_text(encoding="utf-8")
        head, _sep, _ext = text.partition(f"  {self.ext}:\n")
        tests = "" if kind in (VITEST_BAD, TWO_BAD) else TESTS_LINE
        comps = {
            VITEST: VITEST_SINGLE.format(comp=self.vite_comp,
                                         command=VITEST_COMMAND, tests=tests),
            VITEST_BAD: VITEST_SINGLE.format(comp=self.vite_comp,
                                             command=VITEST_COMMAND, tests=tests),
            TWO: JUNIT_MULTI.format(comp=self.junit_comp) + VITEST_MULTI.format(
                comp=self.vite_comp, command=VITEST_COMMAND, tests=tests),
            TWO_BAD: JUNIT_MULTI.format(comp=self.junit_comp) + VITEST_MULTI.format(
                comp=self.vite_comp, command=VITEST_COMMAND, tests=tests),
            JUNIT: JUNIT_SINGLE.format(comp=self.junit_comp),
        }[kind]
        ext = EXT_HEAD.format(name=self.ext, base=config.MAIN_BRANCH,
                              prot=self.prot) + comps
        config.TARGETS.write_text(head + ext, encoding="utf-8")

    def use(self, kind: str) -> None:
        self.write_targets(kind)

    # ------------------------------------------------------------ задача

    def refusal_text(self) -> str:
        return (f"у компонента {self.vite_comp} нет tests — допустимые файлы "
                f"планки не определены")

    def task_with(self, state: str, files: dict, two_criteria: bool = True,
                  code: bool = False) -> str:
        """Задача сценария в `state`: SPEC с AC-1 (и AC-2), файлы планки
        `files` (имя → текст) — в ссылке документов автокоммитом шага."""
        task = self.new_task(state, self.code() if code else None, plank=False,
                             section=SECOND_AC if two_criteria else "")
        if files:
            self.write_docs(task, {f"acceptance_tests/{name}": text
                                   for name, text in files.items()})
        return task

    def docs_paths(self, task: str) -> list:
        head = artifact_branch.ref_head(task)
        return artifact_branch.ls_tree(task, head, f"tasks/{task}") or []

    def steps(self, task: str) -> list:
        return [(r["action"], r["detail"] or "") for r in
                store.task_steps(self.conn, task)]

    def journal_text(self, task: str) -> str:
        return "\n".join(f"{a} | {d}" for a, d in self.steps(task))

    def write_disk_plank(self, task: str, files: dict) -> Path:
        """SPEC и планка задачи на диске `config.TASKS/<id>/` — источник
        пути «диск» выхода из `tests_writing`."""
        # `config.TASKS` песочницы — это `self.root / "tasks"` (tests/sandbox.py).
        tdir = self.root / "tasks" / task
        (tdir / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        spec, _ = artifact_branch.show(task, artifact_branch.ref_head(task),
                                       f"tasks/{task}/SPEC.md")
        (tdir / "SPEC.md").write_text(spec, encoding="utf-8")
        for name, text in files.items():
            (tdir / "acceptance_tests" / name).write_text(text, encoding="utf-8")
        return tdir

    def advance(self, task: str, disk: bool) -> str:
        store.record_fixation(self.conn, task)
        with self.spy():
            if disk:
                with mock.patch.object(artifact_branch, "on_foreign_rev",
                                       lambda task_id, rev: False):
                    return capture_out(fsm.cmd_advance, task)
            return capture_out(fsm.cmd_advance, task)

    def trace_refusals(self, task: str) -> list:
        return [d for a, d in self.steps(task) if a == TRACE_ACTION]

    def autogate(self, task: str) -> str:
        t = store.get_task(self.conn, task)
        real_policy = gates.policy
        with mock.patch.object(gates, "policy", lambda gate: gates.AUTO
                               if gate == "acceptance" else real_policy(gate)), \
                self.spy():
            return capture_out(fsm_autogate._maybe_autogate_acceptance,
                               self.conn, task, t,
                               workspace.path(task, store.task_target(self.conn, task)),
                               1)

    def autogate_reasons(self, task: str) -> list:
        return [d for a, d in self.steps(task) if a == AUTOGATE_REFUSED]

    def amend_plank(self, task: str, files: dict, green: bool = True) -> str:
        """`amend-tests` правки планки в рабочей копии задачи: файлы `files`
        вместо планки лока; сбор проходит, прогон — зелёный или красный."""
        tdir = self.wt(task) / "tasks" / task / "acceptance_tests"
        tdir.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (tdir / name).write_text(text, encoding="utf-8")
        tail = "1 passed in 0.01s" if green else "FAILED x\n1 failed in 0.01s"
        with mock.patch.object(acceptance, "collect",
                               lambda *a, **k: (True, "1 test collected")), \
                mock.patch.object(acceptance, "run",
                                  lambda *a, **k: (green, tail)), self.spy():
            return capture_out(amend.cmd_amend_tests, task,
                               f"правка планки {self.word()}")

    def amend_from_branch(self, task: str, files: dict) -> str:
        """`amend-tests --from-branch`: новая голова ссылки документов несёт
        файлы `files` (коммит роли, узаконенный фиксацией)."""
        artifact_branch.commit_files(task, {
            f"tasks/{task}/acceptance_tests/{name}": text
            for name, text in files.items()}, f"{task}: правка планки ролью")
        store.record_fixation(self.conn, task)
        with mock.patch.object(acceptance, "collect",
                               lambda *a, **k: (True, "1 test collected")), \
                mock.patch.object(acceptance, "run",
                                  lambda *a, **k: (True, "1 passed in 0.01s")), \
                self.spy():
            return capture_out(amend.cmd_amend_tests, task,
                               f"правка планки {self.word()}", from_branch=True)

    def spec_of(self, task: str) -> str:
        spec, reason = artifact_branch.show(task, artifact_branch.ref_head(task),
                                            f"tasks/{task}/SPEC.md")
        self.assertIsNotNone(spec, self.note(f"SPEC.md ссылки не прочитан: {reason}"))
        return spec

    def preflight_out(self, task: str, files: dict) -> str:
        """`preflight` по черновику каталога документов: SPEC.md и файлы
        планки `files` на диске (автокоммит шага каталог убирает)."""
        (self.docs_dir(task)).mkdir(parents=True, exist_ok=True)
        (self.docs_dir(task) / "SPEC.md").write_text(self.spec_of(task),
                                                     encoding="utf-8")
        docs = self.docs_dir(task) / "acceptance_tests"
        docs.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (docs / name).write_text(text, encoding="utf-8")
        return capture_out(preflight.cmd_preflight, task)

    def clean_vitest_plank(self) -> dict:
        reason = f"причина {self.word()}"
        self.manual_reason = reason
        return {f"{self.word()}.test.jsx": jsx(
            f"it('AC-1: кнопка {self.word()}', () => {{ expect(1).toBe(1); }});\n"
            f"// AC-2: manual — {reason}\n")}

    def bad_vitest_plank(self) -> tuple:
        """(файлы, имя файла без маркера): AC-1 покрыт, AC-2 нет, маркер
        красноты не в первом комментарии."""
        name = f"{self.word()}.test.jsx"
        text = (IMPORTS + "// Красен до реализации: после кода.\n"
                f"it('AC-1: кнопка {self.word()}', () => {{}});\n")
        return {name: text}, name


class CheckpointTest(PlankConsumersSandbox):

    def test_ac1_checkpoint_keeps_vitest_test_file(self):
        """Чекпоинт кладёт `a.test.jsx` компонента `pult-vitest` в ссылку документов.

        Сценарий: учебный проект из двух компонентов; роль пишет в каталог
        документов `a.test.jsx` с `it('AC-1: …')`; автокоммит шага.
        Файл есть в дереве ссылки документов, записи «посторонние файлы в
        каталоге планки» нет.

        Ловит мутацию: автокоммит фильтрует планку прежним
        `ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL` без правила проекта —
        `a.test.jsx` отброшен как посторонний.
        """
        self.use(TWO)
        task = self.task_with("tests_writing", {"a.test.jsx": jsx(
            f"it('AC-1: кнопка {self.word()}', () => {{}});\n")})
        paths = self.docs_paths(task)
        self.assertIn(f"tasks/{task}/acceptance_tests/a.test.jsx", paths,
                      self.note(f"{paths}\n{self.journal_text(task)}"))
        self.assertFalse([d for a, d in self.steps(task)
                          if a == checkpoint.STRAY_ACCEPTANCE_FILES_ACTION],
                         self.note(self.journal_text(task)))

    def test_ac6_checkpoint_stray_and_kept_files_by_component_rule(self):
        """Чекпоинт: `a.test.jsx` и `_util.jsx` — в ссылку, `a.test.py` и `vitest.config.js` — посторонние прежней записью.

        Сценарий: учебный проект из двух компонентов; роль пишет четыре
        файла планки; автокоммит. В дереве ссылки — `a.test.jsx` и
        `_util.jsx`, нет `a.test.py` и `vitest.config.js`; запись журнала —
        прежнее действие и деталь «в каталоге планки посторонние файлы:
        acceptance_tests/a.test.py, acceptance_tests/vitest.config.js».

        Ловит мутацию: помощник `_<имя>.jsx` не признан (расширение маски не
        учтено) либо правило компонента пропускает любой файл с
        расширением маски (`vitest.config.js` доезжает до ссылки).
        """
        self.use(TWO)
        task = self.task_with("tests_writing", {
            "a.test.jsx": jsx("it('AC-1: кнопка', () => {});\n"),
            "_util.jsx": "export const x = 1;\n",
            "a.test.py": "import unittest\n",
            "vitest.config.js": "export default {}\n"})
        prefix = f"tasks/{task}/acceptance_tests/"
        paths = self.docs_paths(task)
        for name in ("a.test.jsx", "_util.jsx"):
            with self.subTest(name=name):
                self.assertIn(prefix + name, paths, self.note(f"{paths}"))
        for name in ("a.test.py", "vitest.config.js"):
            with self.subTest(name=name):
                self.assertNotIn(prefix + name, paths, self.note(f"{paths}"))
        stray = [d for a, d in self.steps(task)
                 if a == checkpoint.STRAY_ACCEPTANCE_FILES_ACTION]
        self.assertIn("в каталоге планки посторонние файлы: "
                      "acceptance_tests/a.test.py, acceptance_tests/vitest.config.js",
                      stray, self.note(self.journal_text(task)))

    def test_ac8_checkpoint_takes_default_and_journals_refusal(self):
        """Отказ построения правила: чекпоинт берёт правило по умолчанию и пишет причину в журнал.

        Сценарий: два компонента, у `pult-vitest` (имя случайное) нет
        `tests`; роль пишет `a.test.jsx` и `test_a.py`; автокоммит.
        `test_a.py` — в ссылке, `a.test.jsx` — нет (умолчание строже), в
        журнале задачи — текст «у компонента <имя> нет tests — допустимые
        файлы планки не определены».

        Ловит мутацию: при отказе построения чекпоинт молча берёт
        умолчание, не записав причину, либо пропускает `.jsx` по
        неполному правилу компонента.
        """
        self.use(TWO_BAD)
        task = self.task_with("tests_writing", {
            "a.test.jsx": jsx("it('AC-1: кнопка', () => {});\n"),
            "test_a.py": "import unittest\n"})
        prefix = f"tasks/{task}/acceptance_tests/"
        paths = self.docs_paths(task)
        self.assertIn(prefix + "test_a.py", paths, self.note(f"{paths}"))
        self.assertNotIn(prefix + "a.test.jsx", paths, self.note(f"{paths}"))
        self.assertIn(self.refusal_text(), self.journal_text(task),
                      self.note(self.journal_text(task)))


class TransitionTest(PlankConsumersSandbox):

    def test_ac11_tests_writing_exit_by_rule_disk_and_branch(self):
        """Выход из `tests_writing` (диск и ветка) видит `*.test.jsx` и `//`: трассируемость и маркер красноты по правилу.

        Сценарий: запись из одного компонента `pult-vitest`; SPEC с AC-1 и
        AC-2. Чистая планка (`it('AC-1: …')`, `// AC-2: manual — …`,
        маркер в первом комментарии) — отказа «трассируемость AC» нет ни на
        диске, ни на ветке. Плохая планка (AC-2 без теста и пометки, маркер
        после первой строки кода) — отказ называет `AC-2: нет теста` с
        формой `it('AC-2:` и «в первом комментарии файла» с именем файла.

        Ловит мутацию: правило подключено только к одному из двух путей
        (`_tests_writing_ac_state` диск либо ветка) — другой путь видит
        прежний `.py`-разбор.
        """
        self.use(VITEST)
        for disk in (False, True):
            label = "диск" if disk else "ветка"
            clean = self.clean_vitest_plank()
            task = self.task_with("tests_writing", clean)
            if disk:
                self.write_disk_plank(task, clean)
            out = self.advance(task, disk)
            with self.subTest(path=label, plank="чистая"):
                self.assertEqual(self.trace_refusals(task), [],
                                 self.note(f"{label}\n{out}\n{self.journal_text(task)}"))
            bad, name = self.bad_vitest_plank()
            task = self.task_with("tests_writing", bad)
            if disk:
                self.write_disk_plank(task, bad)
            out = self.advance(task, disk)
            refusals = self.trace_refusals(task)
            with self.subTest(path=label, plank="плохая"):
                self.assertEqual(len(refusals), 1,
                                 self.note(f"{label}\n{out}\n{self.journal_text(task)}"))
                self.assertIn("AC-2: нет теста", refusals[0], self.note(refusals[0]))
                self.assertIn("it('AC-2:", refusals[0], self.note(refusals[0]))
                self.assertNotIn("AC-1: нет теста", refusals[0], self.note(refusals[0]))
                self.assertIn("в первом комментарии файла", refusals[0],
                              self.note(refusals[0]))
                self.assertIn(name, refusals[0], self.note(refusals[0]))

    def test_ac8_tests_writing_exit_refuses_with_build_refusal(self):
        """Компонент `pult-vitest` без `tests`: выход из `tests_writing` отказывает текстом отказа построения.

        Сценарий: запись из одного компонента `pult-vitest` без `tests`
        (имя случайное), чистая `.py`-планка. После `advance` задача в
        `tests_writing`, текст «у компонента <имя> нет tests — допустимые
        файлы планки не определены» — в выводе или журнале.

        Ловит мутацию: переход при отказе построения молча идёт по
        умолчанию (как чекпоинт), не отказывая.
        """
        self.use(VITEST_BAD)
        task = self.task_with("tests_writing", {
            f"test_ac1_{self.word()}.py": callers.PLANK_TEXT.format(word=self.word())},
            two_criteria=False)
        out = self.advance(task, False)
        self.assertEqual(self.state(task), "tests_writing", self.note(out))
        self.assertIn(self.refusal_text(), out + self.journal_text(task),
                      self.note(f"{out}\n{self.journal_text(task)}"))

    def test_ac15_branch_exit_reads_all_py_including_conftest_and_pult(self):
        """У артели путь «ветка» выхода из `tests_writing` читает все `.py` ссылки, включая `conftest.py` и `_pult.py`.

        Сценарий: задача артели, SPEC с AC-1..AC-3; в ссылке документов
        `test_*.py` с методом `test_ac1_…`, а коммитом мимо автокоммита —
        `conftest.py` с пометкой `# AC-2: manual — …` и `_pult.py` с методом
        `test_ac3_…`. Отказа «трассируемость AC» нет: AC-2 и AC-3 покрыты
        файлами, которые фильтр `DEFAULT_PLANK_RULE.component_of` отбросил
        бы.

        Ловит мутацию: путь «ветка» у правила-умолчания фильтрует пути
        `DEFAULT_PLANK_RULE.component_of` вместо прежнего
        `endswith(".py")` — AC-2 и AC-3 «нет теста».
        """
        self.use(callers.ARTEL_PULT)
        task = self.new_task("tests_writing", plank=False,
                             section=SECOND_AC + "AC-3. Третий фикстурный критерий.\n")
        self.write_docs(task, {f"acceptance_tests/test_ac1_{self.word()}.py":
                               callers.PLANK_TEXT.format(word=self.word())})
        artifact_branch.commit_files(task, {
            f"tasks/{task}/acceptance_tests/conftest.py":
                f"# AC-2: manual — проверит Оператор {self.word()}\n",
            f"tasks/{task}/acceptance_tests/_pult.py":
                "import unittest\n\n\nclass P(unittest.TestCase):\n\n"
                "    def test_ac3_helper(self):\n        pass\n"},
            f"{task}: файлы мимо автокоммита")
        out = self.advance(task, False)
        self.assertEqual(self.trace_refusals(task), [],
                         self.note(f"{out}\n{self.journal_text(task)}"))


class PreflightTest(PlankConsumersSandbox):

    def test_ac11_preflight_by_rule(self):
        """`preflight` на записи из одного компонента `pult-vitest` видит `*.test.jsx` и `//`.

        Сценарий: чистая планка черновика — трассируемость и маркер
        красноты «пройдена»; плохая планка — трассируемость «отказ» с
        `AC-2: нет теста` и формой `it('AC-2:`, маркер красноты «отказ» с
        «в первом комментарии файла» и именем файла.

        Ловит мутацию: `preflight` продолжает читать только `*.py`
        черновика (`_plank_py_files`) — чистая планка получает «AC-1: нет
        теста».
        """
        self.use(VITEST)
        task = self.task_with("tests_writing", {})
        out = self.preflight_out(task, self.clean_vitest_plank())
        self.assertIn(f"{preflight.CHECK_TRACEABILITY}: {preflight.PASSED}", out,
                      self.note(out))
        self.assertIn(f"{preflight.CHECK_REDNESS}: {preflight.PASSED}", out,
                      self.note(out))
        task = self.task_with("tests_writing", {})
        bad, name = self.bad_vitest_plank()
        out = self.preflight_out(task, bad)
        self.assertIn(f"{preflight.CHECK_TRACEABILITY}: {preflight.REFUSED}", out,
                      self.note(out))
        self.assertIn("AC-2: нет теста", out, self.note(out))
        self.assertIn("it('AC-2:", out, self.note(out))
        self.assertIn(f"{preflight.CHECK_REDNESS}: {preflight.REFUSED}", out,
                      self.note(out))
        redness = out.split(f"{preflight.CHECK_REDNESS}: ", 1)[1]
        self.assertIn("в первом комментарии файла", redness, self.note(out))
        self.assertIn(name, redness, self.note(out))

    def test_ac8_preflight_refuses_with_build_refusal(self):
        """Компонент `pult-vitest` без `tests`: `preflight` отказывает текстом отказа построения.

        Сценарий: запись из одного компонента `pult-vitest` без `tests`,
        черновик с чистой `.py`-планкой. Вывод несёт текст «у компонента
        <имя> нет tests — допустимые файлы планки не определены», код
        выхода 1.

        Ловит мутацию: `preflight` берёт умолчание молча — проверки
        «пройдена», код выхода 0.
        """
        self.use(VITEST_BAD)
        task = self.task_with("tests_writing", {}, two_criteria=False)
        out = self.preflight_out(task, {
            f"test_ac1_{self.word()}.py": callers.PLANK_TEXT.format(word=self.word())})
        self.assertIn(self.refusal_text(), out, self.note(out))
        self.assertTrue(out.rstrip().endswith("\n1"), self.note(out))

    def test_ac15_preflight_reads_all_py_of_draft(self):
        """У артели `preflight` читает все `.py` черновика (кроме отфильтрованных): пометка в `_<w>.py` покрывает критерий.

        Сценарий: задача артели, SPEC с AC-1 и AC-2; `test_*.py` с методом
        `test_ac1_…` и помощник `_<w>.py` с `# AC-2: manual — …` —
        трассируемость «пройдена».

        Ловит мутацию: у артели `preflight` переведён на тестовые файлы
        правила-умолчания (`test_*.py`) — AC-2 «нет теста».
        """
        self.use(callers.ARTEL_PULT)
        task = self.task_with("tests_writing", {})
        out = self.preflight_out(task, {
            f"test_ac1_{self.word()}.py": callers.PLANK_TEXT.format(word=self.word()),
            f"_{self.word()}.py": f"# AC-2: manual — помощник {self.word()}\n"})
        self.assertIn(f"{preflight.CHECK_TRACEABILITY}: {preflight.PASSED}", out,
                      self.note(out))


class AmendTest(PlankConsumersSandbox):

    def test_ac11_amend_tests_by_rule_worktree_and_branch(self):
        """`amend-tests` (рабочая копия и голова ветки) видит `*.test.jsx` и `//`; маркер красноты — по правилу.

        Сценарий: запись из одного компонента `pult-vitest`, задача в
        `in_dev` с локом. Рабочая копия: чистая правка при зелёном прогоне —
        запись «правка планки»; правка без AC-2 — отказ «трассируемость AC
        нарушена» с `AC-2: нет теста`; при красном прогоне файл с маркером
        в первом комментарии принят, файл с маркером после кода — отказ с
        «в первом комментарии файла». Голова ветки (`--from-branch`):
        чистая правка — без отказа трассируемости, правка без AC-2 — отказ
        с `AC-2: нет теста`.

        Ловит мутацию: `amend-tests` по правилу проверяет только рабочую
        копию (`--from-branch` читает `test_*.py`), либо маркер красноты
        берётся прежним `scan_redness_markers` по `test_*.py` (файл `.jsx`
        без маркера проходит красный прогон).
        """
        self.use(VITEST)
        cases = [("рабочая копия, зелёный", True, True),
                 ("рабочая копия, красный", True, False)]
        for label, clean, green in cases:
            task = self.task_with("in_dev", {"a.test.jsx": jsx(
                "it('AC-1: старое', () => {});\n// AC-2: manual — старое\n")},
                code=True)
            self.lock(task)
            out = self.amend_plank(task, {"a.test.jsx": jsx(
                f"it('AC-1: новое {self.word()}', () => {{}});\n"
                f"// AC-2: manual — новое {self.word()}\n")}, green=green)
            with self.subTest(case=label):
                self.assertNotIn("трассируемость AC нарушена", out, self.note(out))
                self.assertIn(amend.AMEND_ACTION,
                              [a for a, _d in self.steps(task)],
                              self.note(f"{out}\n{self.journal_text(task)}"))
        task = self.task_with("in_dev", {"a.test.jsx": jsx(
            "it('AC-1: старое', () => {});\n// AC-2: manual — старое\n")}, code=True)
        self.lock(task)
        out = self.amend_plank(task, {"a.test.jsx": jsx(
            f"it('AC-1: новое {self.word()}', () => {{}});\n")})
        with self.subTest(case="рабочая копия, без AC-2"):
            self.assertIn("трассируемость AC нарушена", out, self.note(out))
            self.assertIn("AC-2: нет теста", out, self.note(out))
        task = self.task_with("in_dev", {"a.test.jsx": jsx(
            "it('AC-1: старое', () => {});\n// AC-2: manual — старое\n")}, code=True)
        self.lock(task)
        out = self.amend_plank(task, {"a.test.jsx": (
            IMPORTS + "// Красен до реализации: после кода.\n"
            f"it('AC-1: новое {self.word()}', () => {{}});\n"
            "// AC-2: manual — новое\n")}, green=False)
        with self.subTest(case="рабочая копия, красный, маркер после кода"):
            self.assertIn("в первом комментарии файла", out, self.note(out))
            self.assertNotIn(amend.AMEND_ACTION, [a for a, _d in self.steps(task)],
                             self.note(out))
        for label, body in (("ветка, чистая",
                             f"it('AC-1: новое {self.word()}', () => {{}});\n"
                             f"// AC-2: manual — новое {self.word()}\n"),
                            ("ветка, без AC-2",
                             f"it('AC-1: новое {self.word()}', () => {{}});\n")):
            task = self.task_with("in_dev", {"a.test.jsx": jsx(
                "it('AC-1: старое', () => {});\n// AC-2: manual — старое\n")},
                code=True)
            self.lock(task)
            out = self.amend_from_branch(task, {"a.test.jsx": jsx(body)})
            with self.subTest(case=label):
                if "без AC-2" in label:
                    self.assertIn("трассируемость AC нарушена", out, self.note(out))
                    self.assertIn("AC-2: нет теста", out, self.note(out))
                else:
                    self.assertNotIn("трассируемость AC нарушена", out,
                                     self.note(out))

    def test_ac8_amend_tests_refuses_with_build_refusal(self):
        """Компонент `pult-vitest` без `tests`: `amend-tests` отказывает текстом отказа построения.

        Сценарий: запись из одного компонента `pult-vitest` без `tests`,
        задача в `in_dev` с локом `.py`-планки; правка `.py`-файла в рабочей
        копии. Вывод несёт текст отказа построения, записи «правка планки»
        нет.

        Ловит мутацию: `amend-tests` при отказе построения идёт по
        умолчанию и фиксирует правку.
        """
        self.use(VITEST_BAD)
        name = f"test_ac1_{self.word()}.py"
        task = self.task_with("in_dev", {name: callers.PLANK_TEXT.format(
            word=self.word())}, two_criteria=False, code=True)
        self.lock(task)
        out = self.amend_plank(task, {name: callers.PLANK_TEXT.format(
            word=self.word())})
        self.assertIn(self.refusal_text(), out, self.note(out))
        self.assertNotIn(amend.AMEND_ACTION, [a for a, _d in self.steps(task)],
                         self.note(out))

    def test_ac15_amend_branch_reads_test_py_only(self):
        """У артели `amend-tests --from-branch` читает разметку только `test_*.py` головы ветки.

        Сценарий: задача артели с локом; новая голова ссылки документов
        несёт `test_*.py` с методом `test_ac1_…` и помощник `_<w>.py` с
        `# AC-2: manual — …`. Отказ «трассируемость AC нарушена» с
        `AC-2: нет теста`.

        Ловит мутацию: голова ветки у артели читается всеми допустимыми
        файлами правила-умолчания — пометка помощника покрывает AC-2.
        """
        self.use(callers.ARTEL_PULT)
        name = f"test_ac1_{self.word()}.py"
        task = self.task_with("in_dev", {name: callers.PLANK_TEXT.format(
            word=self.word())}, code=True)
        self.lock(task)
        out = self.amend_from_branch(task, {
            name: callers.PLANK_TEXT.format(word=self.word()),
            f"_{self.word()}.py": f"# AC-2: manual — помощник {self.word()}\n"})
        self.assertIn("трассируемость AC нарушена", out, self.note(out))
        self.assertIn("AC-2: нет теста", out, self.note(out))


class DryRunAutogateSummaryTest(PlankConsumersSandbox):

    def dry_run(self, task: str, files: dict) -> str:
        """Планка — в кодовой ветке и в ссылке документов (источник сухого
        прогона SPEC не меняет)."""
        self.commit_code(task, {f"tasks/{task}/SPEC.md": self.spec_of(task),
                                **{f"tasks/{task}/acceptance_tests/{name}": text
                                   for name, text in files.items()}})
        return capture_out(dry_run.cmd_acceptance_dry_run, task)

    def test_ac12_dry_run_lists_jsx_literals_and_slash_markers(self):
        """`acceptance-dry-run` учебного проекта перечисляет `*.test.jsx`, литералы `AC-n: …` всех вызовов и пометки `//`.

        Сценарий: два компонента; в планке `a.test.jsx` с `it`, `test.each`
        и `it.concurrent` (литералы со случайным текстом) и пометкой
        `// AC-4: manual — …`. Под строкой файла — каждый литерал; в
        разделе пометок — `AC-4: manual — …`.

        Ловит мутацию: сухой прогон перечисляет файлы прежним фильтром
        `test_*.py` (раздел файлов пуст, отказ «нет тестовых файлов») либо
        имена тестов — прежним `TEST_METHOD` (литералов нет).
        """
        self.use(TWO)
        literals = [f"AC-1: кнопка {self.word()}", f"AC-2: таблица {self.word()} %s",
                    f"AC-3: параллельно {self.word()}"]
        reason = f"причина {self.word()}"
        plank = {"a.test.jsx": jsx(
            f"it('{literals[0]}', () => {{}});\n"
            f"test.each([[1], [2]])('{literals[1]}', (x) => {{}});\n"
            f"it.concurrent('{literals[2]}', async () => {{}});\n"
            f"// AC-4: manual — {reason}\n")}
        task = self.task_with("tests_writing", plank, code=True)
        out = self.dry_run(task, plank)
        self.assertIn("Тестовые файлы и методы", out, self.note(out))
        files_part = out.split("Тестовые файлы и методы", 1)[1].split(
            "AC-маркеры manual/skip/escalate", 1)[0]
        self.assertIn("a.test.jsx", files_part, self.note(out))
        after = files_part.split("a.test.jsx", 1)[1]
        for literal in literals:
            with self.subTest(literal=literal):
                self.assertIn(literal, after, self.note(out))
        markers_part = out.split("AC-маркеры manual/skip/escalate", 1)[1]
        self.assertIn(f"AC-4: manual — {reason}", markers_part, self.note(out))

    def test_ac15_dry_run_reads_test_py_only_and_headers(self):
        """У артели сухой прогон перечисляет только `test_*.py`, заголовки — прежние.

        Сценарий: задача артели; в планке `test_a.py` с методом и помощник
        `_<w>.py` с методом `test_ac2_…`. Заголовок «Тестовые файлы и
        методы (1 файл(ов)):», в списке `test_a.py`, помощника нет;
        заголовок «AC-маркеры manual/skip/escalate (0):».

        Ловит мутацию: сухой прогон у артели перечисляет все допустимые
        файлы правила-умолчания (`_<w>.py` попадает в раздел файлов).
        """
        self.use(callers.ARTEL_PULT)
        helper = f"_{self.word()}.py"
        plank = {"test_a.py": callers.PLANK_TEXT.format(word=self.word()),
                 helper: "def test_ac2_helper():\n    pass\n"}
        task = self.task_with("tests_writing", plank, code=True)
        out = self.dry_run(task, plank)
        self.assertIn("Тестовые файлы и методы (1 файл(ов)):", out, self.note(out))
        self.assertIn("  test_a.py", out, self.note(out))
        self.assertNotIn(helper, out, self.note(out))
        self.assertIn("AC-маркеры manual/skip/escalate (0):", out, self.note(out))

    def test_ac12_autogate_plank_sources_see_jsx_and_slash_markers(self):
        """Автогейт (`_plank_sources`) учебного проекта видит `*.test.jsx` и пометки `//`.

        Сценарий: два компонента, задача в `acceptance`; в ссылке
        документов `a.test.jsx` с `it('AC-1: …')` и `// AC-2: manual — …`.
        Запись «приёмка: что проверит approve» называет `AC-2: manual — …`
        среди того, что остаётся человеку.

        Ловит мутацию: `_plank_sources` читает прежние `.py` ветки —
        пометка `//` в `.jsx` не видна, запись обещает «автогейт пройдёт
        сам».
        """
        self.use(TWO)
        reason = f"причина {self.word()}"
        task = self.task_with("acceptance", {"a.test.jsx": jsx(
            f"it('AC-1: кнопка {self.word()}', () => {{}});\n"
            f"// AC-2: manual — {reason}\n")}, code=True)
        out = self.autogate(task)
        checklist = [d for a, d in self.steps(task)
                     if a == fsm_autogate.ACCEPTANCE_CHECKLIST_ACTION]
        self.assertTrue(checklist, self.note(f"{out}\n{self.journal_text(task)}"))
        self.assertIn(f"AC-2: manual — {reason}", checklist[-1],
                      self.note(checklist[-1]))

    def test_ac19_autogate_fail_closed_on_component_rule(self):
        """Автогейт при правиле не по умолчанию оставляет задачу в `acceptance` с причиной по правилу компонента.

        Сценарий: (1) учебный проект, `.jsx`-планка с зелёной
        трассируемостью (AC-1 и AC-2 покрыты `it`) — задача в `acceptance`,
        запись «автогейт acceptance не пройден» с причиной «автогейт:
        прогон планки компонента <имя pult-vitest> по правилу — до выкладки
        plank_layout (G2а-2) не исполняется; приёмку решает Оператор»;
        (2) отказ построения (у `pult-vitest` нет `tests`), `.py`-планка —
        задача в `acceptance`, причина «автогейт: у компонента <имя> нет
        tests — допустимые файлы планки не определены».

        Ловит мутацию: условие fail-closed проверяет только правило не по
        умолчанию (умолчание с причиной отказа построения проходит дальше),
        либо стоит после «каталог пуст» — `.jsx`-планка получает прежнюю
        причину «каталог приёмочных тестов пуст».
        """
        self.use(TWO)
        task = self.task_with("acceptance", {"a.test.jsx": jsx(
            f"it('AC-1: кнопка {self.word()}', () => {{}});\n"
            f"it('AC-2: поле {self.word()}', () => {{}});\n")}, code=True)
        out = self.autogate(task)
        expected = (f"автогейт: прогон планки компонента {self.vite_comp} по "
                    f"правилу — до выкладки plank_layout (G2а-2) не исполняется; "
                    f"приёмку решает Оператор")
        reasons = self.autogate_reasons(task)
        self.assertEqual(self.state(task), "acceptance", self.note(out))
        self.assertEqual(len(reasons), 1, self.note(f"{out}\n{self.journal_text(task)}"))
        self.assertTrue(reasons[0].startswith(expected),
                        self.note(f"{reasons[0]}\n!=\n{expected}"))
        self.use(TWO_BAD)
        task = self.task_with("acceptance", {
            f"test_ac1_{self.word()}.py": callers.PLANK_TEXT.format(word=self.word())},
            two_criteria=False, code=True)
        out = self.autogate(task)
        reasons = self.autogate_reasons(task)
        self.assertEqual(self.state(task), "acceptance", self.note(out))
        self.assertEqual(len(reasons), 1, self.note(f"{out}\n{self.journal_text(task)}"))
        self.assertTrue(reasons[0].startswith(f"автогейт: {self.refusal_text()}"),
                        self.note(reasons[0]))

    def test_ac19_autogate_unchanged_for_artel_and_default_rule(self):
        """У артели и у правила по умолчанию без отказа построения решение и тексты автогейта прежние.

        Сценарий: задача артели и задача внешнего проекта с одним
        компонентом `junit-xml` на pytest; в ссылке — `test_*.py` с методом
        и `# AC-2: manual — …`. Задача в `acceptance`, причина начинается с
        «автогейт: критерии manual — AC-2 (».

        Ловит мутацию: fail-closed срабатывает на любом проекте с
        `components:` (или на умолчании без причины) — у `junit-xml`
        причина «прогон планки компонента …».
        """
        for kind in (callers.ARTEL_PULT, JUNIT):
            self.use(kind)
            task = self.task_with("acceptance", {
                f"test_ac1_{self.word()}.py":
                    callers.PLANK_TEXT.format(word=self.word())
                    + f"\n# AC-2: manual — причина {self.word()}\n"}, code=True)
            out = self.autogate(task)
            reasons = self.autogate_reasons(task)
            with self.subTest(kind=kind):
                self.assertEqual(self.state(task), "acceptance", self.note(out))
                self.assertEqual(len(reasons), 1, self.note(self.journal_text(task)))
                self.assertTrue(reasons[0].startswith(
                    "автогейт: критерии manual — AC-2 ("), self.note(reasons[0]))

    def test_ac8_autogate_journals_build_refusal(self):
        """Отказ построения: автогейт пишет причину в журнал (задача остаётся в `acceptance`).

        Сценарий: два компонента, у `pult-vitest` нет `tests`, задача в
        `acceptance` с `.py`-планкой. В журнале задачи — текст «у
        компонента <имя> нет tests — допустимые файлы планки не
        определены».

        Ловит мутацию: автогейт при отказе построения берёт умолчание
        молча и идёт прежними условиями.
        """
        self.use(TWO_BAD)
        task = self.task_with("acceptance", {
            f"test_ac1_{self.word()}.py": callers.PLANK_TEXT.format(word=self.word())},
            two_criteria=False, code=True)
        out = self.autogate(task)
        self.assertEqual(self.state(task), "acceptance", self.note(out))
        self.assertIn(self.refusal_text(), self.journal_text(task),
                      self.note(self.journal_text(task)))

    def test_ac15_autogate_reads_all_py_and_empty_reason(self):
        """У артели автогейт читает все `.py` ветки, причина пустой планки — прежняя.

        Сценарий: задача артели с планкой из одного помощника `_<w>.py` с
        `# AC-1: manual — …` — причина «автогейт: критерии manual — AC-1 (»;
        задача артели без планки — причина «автогейт: каталог приёмочных
        тестов пуст или отсутствует (».

        Ловит мутацию: `_plank_sources` у артели переведён на тестовые
        файлы правила-умолчания — помощник не читается, причина «каталог
        пуст».
        """
        self.use(callers.ARTEL_PULT)
        task = self.task_with("acceptance", {
            f"_{self.word()}.py": f"# AC-1: manual — помощник {self.word()}\n"},
            two_criteria=False, code=True)
        self.autogate(task)
        reasons = self.autogate_reasons(task)
        self.assertEqual(len(reasons), 1, self.note(self.journal_text(task)))
        self.assertTrue(reasons[0].startswith("автогейт: критерии manual — AC-1 ("),
                        self.note(reasons[0]))
        task = self.task_with("acceptance", {}, two_criteria=False, code=True)
        self.autogate(task)
        reasons = self.autogate_reasons(task)
        self.assertEqual(len(reasons), 1, self.note(self.journal_text(task)))
        self.assertTrue(reasons[0].startswith(
            "автогейт: каталог приёмочных тестов пуст или отсутствует ("),
            self.note(reasons[0]))

    def summary_dir(self, task: str, files: dict) -> Path:
        tdir = Path(tempfile.mkdtemp(prefix="summary-", dir=self.root)) / task
        (tdir / "acceptance_tests").mkdir(parents=True)
        for name, text in files.items():
            (tdir / "acceptance_tests" / name).write_text(text, encoding="utf-8")
        return tdir

    def test_ac12_summary_counts_by_rule(self):
        """`acceptance.summary` учебного проекта считает тесты и пометки `.jsx` по правилу; вызывающий не изменён.

        Сценарий: два компонента; каталог задачи (имя — id задачи) с
        `a.test.jsx` (два вызова с меткой) и `b.test.jsx` (один вызов,
        `// AC-4: manual — …`, `// AC-5: skip — …`). Сводка — «приёмочные
        тесты: 3 тест(ов), 1 manual, 1 skip, 0 ci». Вызов
        `acceptance.summary` в `advance_gates/acceptance.py` — прежний
        текст строк 432-435 (ветка не меняет вызывающего).

        Ловит мутацию: сводка считает прежним `count_test_methods`/
        `scan_acceptance_tests` без правила — «0 тест(ов), 0 manual,
        0 skip».
        """
        self.use(TWO)
        task = self.task_with("acceptance", {})
        tdir = self.summary_dir(task, {
            "a.test.jsx": jsx(f"it('AC-1: кнопка {self.word()}', () => {{}});\n"
                              f"test('AC-2: поле {self.word()}', () => {{}});\n"),
            "b.test.jsx": jsx(f"it.concurrent('AC-3: {self.word()}', async () => {{}});\n"
                              f"// AC-4: manual — причина {self.word()}\n"
                              f"// AC-5: skip — причина {self.word()}\n")})
        card = acceptance.summary(tdir)
        self.assertIn("приёмочные тесты: 3 тест(ов), 1 manual, 1 skip, 0 ci", card,
                      self.note(card))
        self.assertNotIn("orchestrator/advance_gates/acceptance.py",
                         changed_paths(), self.note("вызывающий сводки изменён"))

    def test_ac15_summary_line_unchanged_for_artel(self):
        """У артели строка сводки прежняя: счёт методов — все `*.py`, пометки — `test_*.py`.

        Сценарий: задача артели; каталог с `test_a.py` (два метода,
        `# AC-3: manual — …`) и помощником `_<w>.py` (один метод,
        `# AC-4: skip — …`). Сводка — «приёмочные тесты: 3 тест(ов),
        1 manual, 0 skip, 0 ci».

        Ловит мутацию: сводка артели считает методы только тестовых файлов
        правила-умолчания («2 тест(ов)») либо читает пометки помощника
        («1 skip»).
        """
        self.use(callers.ARTEL_PULT)
        task = self.task_with("acceptance", {})
        tdir = self.summary_dir(task, {
            "test_a.py": ("import unittest\n\n\nclass T(unittest.TestCase):\n\n"
                          "    def test_one(self):\n        pass\n\n"
                          "    def test_two(self):\n        pass\n\n"
                          f"# AC-3: manual — причина {self.word()}\n"),
            f"_{self.word()}.py": ("def test_helper():\n    pass\n\n"
                                   f"# AC-4: skip — причина {self.word()}\n")})
        card = acceptance.summary(tdir)
        self.assertIn("приёмочные тесты: 3 тест(ов), 1 manual, 0 skip, 0 ci", card,
                      self.note(card))


class MergeDocsTest(PlankConsumersSandbox):

    def test_ac13_merge_docs_by_component_rule_without_guard_rules(self):
        """Документы перед мержем по правилу компонента при `guard_rules=False`; при отказе построения — по умолчанию.

        Сценарий: (1) учебный проект; в ссылке `a.test.jsx` с пометкой
        `// AC-1: manual — …` с отступом, в перечне путей — ещё
        `acceptance_tests/vitest.config.js`; `_task_docs_violations(...,
        False)` называет `vitest.config.js` посторонним и пометку
        `'// AC-1: manual'` с отступом. (2) отказ построения правила
        (у `pult-vitest` нет `tests`): `a.test.jsx` в перечне путей при
        `guard_rules=False` — нарушение «посторонний файл в каталоге
        планки».

        Ловит мутацию: правила планки применяются только при `guard_rules`
        (у внешнего проекта всегда `False`) — нарушений нет.
        """
        self.use(TWO)
        task = self.task_with("merge_gate", {"a.test.jsx": jsx(
            "describe('группа', () => {\n"
            f"  // AC-1: manual — причина {self.word()}\n"
            f"  it('AC-2: кнопка {self.word()}', () => {{}});\n}});\n")}, code=True)
        rev = artifact_branch.ref_head(task)
        stray = f"tasks/{task}/acceptance_tests/vitest.config.js"
        paths = self.docs_paths(task) + [stray]
        violations = fsm_merge_gate._task_docs_violations(task, rev, paths, False)
        self.assertIn(f"{stray}: {guard.EXTRANEOUS_ACCEPTANCE_FILE_REASON}",
                      violations, self.note(f"{violations}"))
        self.assertTrue(any("маркер '// AC-1: manual' с отступом" in v
                            for v in violations), self.note(f"{violations}"))
        self.use(TWO_BAD)
        task = self.task_with("merge_gate", {
            f"test_ac1_{self.word()}.py": callers.PLANK_TEXT.format(word=self.word())},
            code=True)
        rev = artifact_branch.ref_head(task)
        jsx_path = f"tasks/{task}/acceptance_tests/a.test.jsx"
        violations = fsm_merge_gate._task_docs_violations(
            task, rev, self.docs_paths(task) + [jsx_path], False)
        self.assertIn(f"{jsx_path}: {guard.EXTRANEOUS_ACCEPTANCE_FILE_REASON}",
                      violations, self.note(f"{violations}"))

    def test_ac8_merge_docs_journal_build_refusal(self):
        """Отказ построения: документы перед мержем пишут причину в журнал.

        Сценарий: два компонента, у `pult-vitest` нет `tests`; задача на
        `merge_gate` с `.py`-планкой; проверка документов задачи
        (`_guard_task_docs_or_refuse`). В журнале задачи — текст отказа
        построения.

        Ловит мутацию: документы перед мержем при отказе построения берут
        умолчание молча.
        """
        self.use(TWO_BAD)
        task = self.task_with("merge_gate", {
            f"test_ac1_{self.word()}.py": callers.PLANK_TEXT.format(word=self.word())},
            code=True)
        store.record_fixation(self.conn, task)
        scratch = Path(tempfile.mkdtemp(prefix="scratch-", dir=self.root))
        ctx = repo_context.resolve(self.ext)
        capture_out(fsm_merge_gate._guard_task_docs_or_refuse, self.conn, task,
                    scratch, ctx)
        self.assertIn(self.refusal_text(), self.journal_text(task),
                      self.note(self.journal_text(task)))

    def test_ac15_merge_docs_with_guard_rules_reads_test_py_only(self):
        """У артели при `guard_rules` пометка с отступом проверяется только в `test_*.py`.

        Сценарий: задача артели; в ссылке `test_a.py` и помощник `_<w>.py`,
        оба с `# AC-1: manual — …` с отступом внутри функции.
        `_task_docs_violations(..., True)` называет пометку в `test_a.py`
        прежним текстом с `#` и не называет помощника.

        Ловит мутацию: у артели документы перед мержем читают все
        допустимые файлы правила-умолчания (помощник даёт нарушение) либо
        текст отказа сменил префикс.
        """
        self.use(callers.ARTEL_PULT)
        helper = f"_{self.word()}.py"
        body = ("def f():\n"
                f"    # AC-1: manual — причина {self.word()}\n"
                "    return 1\n")
        task = self.task_with("merge_gate", {
            "test_a.py": callers.PLANK_TEXT.format(word=self.word()) + "\n\n" + body,
            helper: body}, code=True)
        rev = artifact_branch.ref_head(task)
        violations = fsm_merge_gate._task_docs_violations(
            task, rev, self.docs_paths(task), True)
        indented = [v for v in violations if "с отступом" in v]
        self.assertEqual(len(indented), 1, self.note(f"{violations}"))
        self.assertIn("test_a.py", indented[0], self.note(indented[0]))
        self.assertIn("маркер '# AC-1: manual' с отступом не учитывается "
                      "каталогом — вынеси в начало строки либо убери",
                      indented[0], self.note(indented[0]))


class SentinelTest(unittest.TestCase):

    def test_ac14_preflight_sentinel_unchanged_and_green(self):
        """Сторож предпроверки не изменён веткой задачи и его тесты зелёные.

        Сценарий: среди путей задачи (`changed_paths` помощника пульта —
        дифф ветки от базы и неотслеживаемые файлы) нет
        `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`; прогон этого
        файла pytest из корня рабочей копии — код выхода 0.

        Зелёный с рождения: сторож на main зелёный и веткой не тронут;
        покраснеет, если реализация правит сторожа либо ломает
        `preflight`/переход так, что его тесты падают.
        """
        self.assertNotIn(SENTINEL_FILE, changed_paths())
        env = dict(os.environ)
        env.pop("PYTEST_ADDOPTS", None)
        res = subprocess.run(
            [sys.executable, "-m", "pytest", SENTINEL_FILE, "-q",
             "-p", "no:cacheprovider", "-x"],
            cwd=CODE_ROOT, env=env, capture_output=True, text=True, timeout=110)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
