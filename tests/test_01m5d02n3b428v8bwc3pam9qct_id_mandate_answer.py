"""Мандат на ослабление теста по идентификатору при записи ответа: маркер, проверка идентификатора, путь записи и журнал, матрица неослабления, `zones-extend` (AC-1..AC-9, AC-14..AC-19).

Группа: долгоживущий
Красен до реализации: строку «Ослабление теста по идентификатору разрешено:» пульт не знает — в `in_dev` файл с ней `answer` принимает как указание Оператора без проверки идентификатора и матрицы и без вида мандата в журнале (AC-1..AC-7, AC-15), `zones-extend` не отказывает файлу матрицы с ней (AC-8), гейт SPEC отказывает ей как ответу без мандата тестов (AC-9), ячейка «Чем покрыто после» не признаёт идентификатор теста и путь не `*.py` компонента (AC-17, AC-18); зелены с рождения методы, держащие прежнее поведение: правило ячейки у артели и при профиле `None` (AC-14), вне границы гейта исходов (AC-19) и отказы гейта SPEC (AC-16).

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`), связка
«команда `answer`/`zones-extend` — БД — ссылка документов — журнал»: корень —
клон артели с bare `origin`, учебные внешние проекты — свои клоны
(`tests.sandbox.make_project_repo`), записи `targets.yaml` песочницы пишет
сценарий: компонент `pult-vitest` с `report` (область `src/**`), компонент
`junit-xml` с `report` (область `tests/**`), компонент без `report`,
`test_profile`, `test_profile` `pytest-own` с `report`, проект без профиля.
Предпосылка каждой записи — решение `project_profile.decide` и граница
`in_outcome_bounds` — проверяется при заведении проекта. Задачи заводятся
прямой строкой БД в состоянии сценария, рабочая копия — `workspace.ensure`,
документы — автокоммитом шага. Наблюдаются вывод команды (текст отказа),
число `ANSWER-n.md` в ссылке документов задачи и записи её журнала.

Провалидировано временным стабом реализации (удалён, не закоммичен): разбор
нового маркера без деления по запятым, проверка идентификатора по
`parse_test_id`/`in_outcome_bounds`/`weakening_scope`, вход маркера в
`_has_mandate_lines`, гейт SPEC и матрицу, вид журнала, отказ `zones-extend`,
правила ячейки «Чем покрыто после» для компонента в границе — все методы
зелёные.

Имена проектов, компонентов, файлов и тестов — из `random` при каждом
запуске; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import unittest
from unittest import mock

from orchestrator import (answer, checkpoint, config, github_adapter, idgen,
                          project_profile, store, workspace)
from orchestrator.advance_gates.acceptance import in_outcome_bounds
from tests.sandbox import RealGitSandbox, artel_target_entry, make_project_repo

ARTEL = config.DEFAULT_TARGET
LETTERS = "abcdefghijkmnpqrstuvwxyz"
NEW = "Ослабление теста по идентификатору разрешено:"
OLD = "Ослабление тестов разрешено:"
ZONES = "Расширение зон разрешено:"
INDEPENDENT = "Независимая проверка: матрица подтверждена Оператором"
CREATED = "ANSWER создан ("
NEW_KIND = "мандат на ослабление теста по идентификатору:"
OLD_KIND = "мандат на ослабление тестов:"
FILE_MANDATE_REASON = "такой тест покрывается мандатом на путь файла"

HEADERS = ("Что меняется", "Какое свойство сейчас держит",
           "Остаётся ли свойство после изменения", "Чем покрыто после",
           "Решение")

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

VITEST_COMPONENT = """    components:
      {comp}:
        command: [{command}]
        report: pult-vitest
        report_args: [--reporter=default, --outputFile={{path}}]
        install: [npm, ci]
        tests: [src/**/*.test.ts]
        plank_layout: src/.pv/<id>
        long_lived: src/<dir>/<name>.<id>.test.ts
        weakening_scope: [src/**]
        mutation_claim_scope: [src/**]
        failure_errors: [AssertionError]
        tools:
          vitest: "{vitest}"
"""

JUNIT_COMPONENT = """    components:
      {comp}:
        command: [python3, -m, pytest]
        report: junit-xml
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
        weakening_scope: [tests/**]
        mutation_claim_scope: [tests/**]
        failure_errors: [AssertionError]
        plank_layout: .pj/<id>
"""

NO_REPORT_COMPONENT = """    components:
      {comp}:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
        weakening_scope: [src/**]
        mutation_claim_scope: [tests/**]
        plank_layout: .pn/<id>
"""

TEST_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [src/**]
      mutation_claim_scope: [tests/**]
{extra}"""

OWN_EXTRA = "      runner: pytest-own\n      report: junit-xml\n"

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура мандата по идентификатору

## Подход
Фикстура сценария.

## Шаги
1. Правка.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Нет.
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: фикстура мандата по идентификатору

## Контекст

## Требования

## Критерии приёмки

AC-1. Критерий фикстуры.

## Не входит
"""


def matrix(rows) -> str:
    """Раздел матрицы неослабления с пятью каноническими столбцами и
    строками данных `rows` (кортежи по пять ячеек)."""
    return ("## Матрица неослабления\n\n"
            "| " + " | ".join(HEADERS) + " |\n"
            + "|" + "---|" * len(HEADERS) + "\n"
            + "".join("| " + " | ".join(row) + " |\n" for row in rows))


def gone_row(changed: str) -> tuple:
    """Строка матрицы: «Что меняется» — `changed`, свойство не остаётся —
    покрытие не требуется."""
    return (changed, "фикстура сценария", "нет", "не покрыто", "ок")


def kinds_of(action: str) -> list:
    """Виды мандата записи «ANSWER создан (…)»: части через «; » внутри
    скобок."""
    body = action[len(CREATED):]
    body = body.rsplit(")", 1)[0]
    return body.split("; ")


class IdMandateSandbox(RealGitSandbox):
    """Клон артели; учебные проекты — по запросу сценария; задачи прямой
    строкой БД."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()
        for patcher in (mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                        mock.patch.object(github_adapter, "ensure_draft_mr",
                                          lambda conn, task_id, t: None),
                        mock.patch("orchestrator.doctor.preflight_checks",
                                   lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        self.conn = store.db()
        config.TARGETS.write_text("targets:\n" + artel_target_entry(),
                                  encoding="utf-8")
        self.vitest_version = next(
            f"{major}.0.0" for major in project_profile.VITEST_VERSION_FLAGS)

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def why(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def vitest_name(self, comma: bool = False) -> str:
        """Полное имя теста Vitest: пробелы внутри и « > » (и запятая при
        `comma`)."""
        middle = f", {self.word(4)}" if comma else ""
        return (f"{self.word()} {self.word(4)} > {self.word()}{middle} "
                f"{self.word(5)}")

    def src_path(self) -> str:
        return f"src/{self.word(4)}/{self.word()}.test.ts"

    def vitest_id(self, project, comma: bool = False) -> str:
        return project_profile.test_id(project["comp"], self.src_path(),
                                       self.vitest_name(comma))

    # ------------------------------------------------------------ проекты

    def project(self, kind: str) -> dict:
        """Учебный проект вида `kind`: `vitest`/`junit` — компонент
        `components:` с `report`; `noreport` — компонент без `report`;
        `tp` — `test_profile`; `own` — `test_profile` `pytest-own` с
        `report`; `bare` — без профиля. Предпосылка — граница решения."""
        name, comp = f"p{self.word()}", f"c{self.word()}"
        body = {"vitest": lambda: VITEST_COMPONENT.format(
                    comp=comp, vitest=self.vitest_version,
                    command=", ".join(project_profile.VITEST_BASE_ARGV)),
                "junit": lambda: JUNIT_COMPONENT.format(comp=comp),
                "noreport": lambda: NO_REPORT_COMPONENT.format(comp=comp),
                "tp": lambda: TEST_PROFILE.format(extra=""),
                "own": lambda: TEST_PROFILE.format(extra=OWN_EXTRA),
                "bare": lambda: ""}[kind]()
        if kind in ("tp", "own"):
            comp = project_profile.DEFAULT_COMPONENT
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(
            old.rstrip("\n") + "\n" + ENTRY_HEAD.format(
                name=name, base=config.MAIN_BRANCH) + body, encoding="utf-8")
        make_project_repo(name)
        decision = project_profile.decide(name)
        self.assertFalse(decision.refusal, self.why(
            f"фикстура {kind}: отказ решения {decision.refusal}"))
        if kind == "bare":
            self.assertIsNone(decision.profile, self.why(f"фикстура: {decision}"))
        else:
            self.assertIsNotNone(decision.profile,
                                 self.why(f"фикстура {kind}: {decision}"))
            self.assertEqual(kind in ("vitest", "junit"),
                             in_outcome_bounds(decision.profile),
                             self.why(f"фикстура {kind}: граница {decision}"))
        return {"name": name, "comp": comp, "kind": kind}

    # -------------------------------------------------------------- задачи

    def task(self, target: str, state: str = "in_dev") -> str:
        """Задача `target` в `state` с рабочей копией, файлом кода в ветке
        и PLAN.md/SPEC.md в ссылке документов; путь кода — `self.code`."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}", state,
                          branch, target, config.DEFAULT_BUDGET_USD)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.why(f"рабочая копия не заведена: {error}"))
        self.code = f"lib{self.word()}/m{self.word()}.py"
        path = wt / self.code
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("X = 1\n", encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: код задачи")
        docs = config.PROJECTS / target / "tasks" / task_id
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "PLAN.md").write_text(PLAN_TEXT.format(task=task_id),
                                      encoding="utf-8")
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=task_id),
                                      encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, task_id, "developer")
        return task_id

    # -------------------------------------------------------------- каналы

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

    def text_file(self, text: str) -> str:
        path = self.root / ".artel" / f"vvod-{self.rng.randrange(1 << 40)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def answers(self, task_id: str) -> list:
        """Файлы `ANSWER-n.md` ссылки документов задачи в клоне её проекта."""
        repo = str(workspace.task_repo(task_id))
        ref = f"refs/artifacts/{task_id}"
        if not self.git("-C", repo, "for-each-ref", "--format=%(objectname)",
                        ref).strip():
            return []
        return [line for line in self.git("-C", repo, "ls-tree", "-r",
                                          "--name-only", ref).splitlines()
                if line.rsplit("/", 1)[-1].startswith("ANSWER-")]

    def submit(self, task_id: str, text: str) -> tuple:
        """`answer` с файлом `text`: (отказано ли, вывод, прирост числа
        ANSWER, новые действия журнала)."""
        before = len(self.answers(task_id))
        rows = store.task_steps(self.conn, task_id)
        last = rows[-1]["id"] if rows else 0
        out, failed = self.run_cmd(answer.cmd_answer, task_id,
                                   self.text_file(text))
        actions = [r["action"] for r in store.task_steps(self.conn, task_id)
                   if r["id"] > last]
        return failed, out, len(self.answers(task_id)) - before, actions

    def id_answer(self, ids, *, rows=None, check: bool = True,
                  with_matrix: bool = True, pad: str = "") -> str:
        """Файл ответа: абзац, строка нового маркера на каждый идентификатор
        `ids` (с отступом `pad` по краям), строка независимой проверки и
        матрица `rows` (по умолчанию — по строке на идентификатор в
        одинарных обратных кавычках)."""
        lines = [f"Ответ Оператора {self.seed}.", ""]
        lines += [f"{pad}{NEW} {pad}{cid}{pad}" for cid in ids]
        if check:
            lines += ["", INDEPENDENT]
        text = "\n".join(lines) + "\n"
        if with_matrix:
            text += "\n" + matrix(rows if rows is not None else
                                  [gone_row(f"`{cid}`") for cid in ids])
        return text

    def assert_refused(self, result: tuple, case: str) -> str:
        failed, out, added, actions = result
        self.assertTrue(failed, self.why(f"{case}: принято:\n{out}\n{actions}"))
        self.assertEqual(0, added, self.why(f"{case}: ANSWER создан:\n{out}"))
        return out

    def assert_id_kind(self, result: tuple, cid: str, case: str) -> None:
        """Принято; ANSWER добавлен; запись «ANSWER создан (…)» несёт вид
        нового маркера с «`cid`», а вид прежнего маркера тестов его не
        несёт."""
        failed, out, added, actions = result
        self.assertFalse(failed, self.why(f"{case}: отказ:\n{out}"))
        self.assertEqual(1, added, self.why(f"{case}: ANSWER не создан:\n{out}"))
        created = [a for a in actions if a.startswith(CREATED)]
        self.assertTrue(created, self.why(f"{case}: нет «{CREATED}…»: {actions}"))
        kinds = kinds_of(created[-1])
        wanted = f"«{cid}»"
        self.assertTrue(any(k.startswith(NEW_KIND) and wanted in k
                            for k in kinds),
                        self.why(f"{case}: нет вида «{NEW_KIND} {wanted}»: "
                                 f"{created[-1]}"))
        self.assertFalse(any(k.startswith(OLD_KIND) and cid in k for k in kinds),
                         self.why(f"{case}: идентификатор в виде прежнего "
                                  f"маркера: {created[-1]}"))

    def cell_outcome(self, task_id: str, cell: str) -> tuple:
        """`answer` с мандатом зон на файл кода задачи и матрицей, где
        свойство остаётся, «Решение» — «ок», а «Чем покрыто после» —
        `cell`."""
        row = (f"`{self.code_of[task_id]}`", "фикстура сценария", "да", cell,
               "ок")
        text = (f"{ZONES} {self.code_of[task_id]}\n\n"
                f"Основание: решение Оператора ({self.seed}).\n\n"
                + matrix([row]))
        return self.submit(task_id, text)

    def cell_task(self, target: str) -> str:
        task_id = self.task(target)
        self.code_of = getattr(self, "code_of", {})
        self.code_of[task_id] = self.code
        return task_id


# AC-1 -----------------------------------------------------------------------

class VitestIdAcceptedTest(IdMandateSandbox):

    def test_ac1_vitest_id_with_space_arrow_comma_taken_whole(self):
        """Идентификатор Vitest с пробелами, « > » и запятой в имени принят одним элементом — весь остаток строки после маркера со срезом пробелов.

        Задача проекта с компонентом `pult-vitest` (с `report`, область
        `src/**`) в `in_dev`. Файл ответа: строка нового маркера с
        идентификатором `<компонент>:src/<…>.test.ts::<имя>`, где имя
        несёт пробелы, « > » и запятую; строка окружена пробелами по краям
        (и между маркером и идентификатором — несколько пробелов); матрица
        называет идентификатор, есть строка независимой проверки. Ответ
        принят, ANSWER добавлен, запись «ANSWER создан (…)» несёт вид
        нового маркера с идентификатором целиком в «».

        Ловит мутацию: элементы нового маркера делятся по запятым, как у
        `elements`, — хвост имени после запятой не разбирается
        `parse_test_id`, ответ отказан; пробелы по краям строки не срезаны
        — элемент « <компонент>…» не совпадает с компонентом, отказ; файл
        с новым маркером принят как указание — записи с видом мандата нет.
        """
        project = self.project("vitest")
        task_id = self.task(project["name"])
        cid = self.vitest_id(project, comma=True)
        result = self.submit(task_id, self.id_answer([cid], pad="   "))
        self.assert_id_kind(result, cid, "vitest с запятой")


# AC-2 -----------------------------------------------------------------------

class PytestIdAcceptedTest(IdMandateSandbox):

    def test_ac2_pytest_component_id_accepted(self):
        """Идентификатор pytest компонента `junit-xml` с `report`, путь в области, — ответ принят.

        Задача проекта с компонентом `junit-xml` (область `tests/**`) в
        `in_dev`. Новый маркер на `<компонент>:tests/<…>/test_<…>.py::
        K<…>::test_<…>`, матрица и независимая проверка. Ответ принят,
        ANSWER добавлен, вид нового маркера в журнале называет
        идентификатор.

        Ловит мутацию: граница проверки — только `report: pult-vitest`
        (а не `in_outcome_bounds`) — идентификатор компонента `junit-xml`
        отказан; путь сверяется прежней областью артели или маской
        `tests/**/*.py` профиля артели вместо `weakening_scope`
        компонента — при вложенном каталоге отказ.
        """
        project = self.project("junit")
        task_id = self.task(project["name"])
        cid = project_profile.test_id(
            project["comp"], f"tests/{self.word(4)}/test_{self.word()}.py",
            f"K{self.word().capitalize()}::test_{self.word()}")
        result = self.submit(task_id, self.id_answer([cid]))
        self.assert_id_kind(result, cid, "pytest")


# AC-3 -----------------------------------------------------------------------

class IdRefusalsTest(IdMandateSandbox):

    def test_ac3_unusable_id_refused_no_answer(self):
        """Новый маркер отказан, ANSWER не создан: неразборчивый идентификатор, чужой компонент, компонент без `report`, `test_profile`, `pytest-own` с `report`, путь вне области.

        Для каждого случая — своя задача в `in_dev`, файл ответа с
        матрицей, называющей идентификатор, и строкой независимой
        проверки; отказана только сама строка мандата: (а) проект
        `pult-vitest`, `<компонент>:src/<…>.test.ts` без `::`; (б) тот же
        проект, компонент, которого нет в записи; (в) проект с
        компонентом без `report`, путь в его области; (г) проект с
        `test_profile`, компонент `default`, путь в области; (д) то же у
        `pytest-own` с `report`; (е) проект `pult-vitest`, путь
        `lib/…` вне `src/**`.

        Ловит мутацию: идентификатор не разбирается `parse_test_id` при
        записи — (а) принят; компонент не сверяется с записью — (б) принят;
        граница — «есть `report`» без `from_components` — (д) принят,
        или «запись `components:`» без `report` — (в) принят; путь не
        сверяется с `weakening_scope` — (е) принят.
        """
        vitest = self.project("vitest")
        cases = [
            ("неразборчивый", vitest, f"{vitest['comp']}:{self.src_path()}"),
            ("чужой компонент", vitest, project_profile.test_id(
                f"z{self.word()}", self.src_path(), self.vitest_name())),
            ("вне области", vitest, project_profile.test_id(
                vitest["comp"], f"lib/{self.word()}.test.ts",
                self.vitest_name()))]
        for kind in ("noreport", "tp", "own"):
            project = self.project(kind)
            cases.append((kind, project, project_profile.test_id(
                project["comp"], self.src_path(), self.vitest_name())))
        for case, project, cid in cases:
            with self.subTest(case=case, seed=self.seed):
                task_id = self.task(project["name"])
                self.assert_refused(self.submit(task_id, self.id_answer([cid])),
                                    case)


# AC-4 -----------------------------------------------------------------------

class BacktickPipeRefusedTest(IdMandateSandbox):

    def test_ac4_backtick_or_pipe_refused_with_file_mandate_reason(self):
        """Идентификатор с обратной кавычкой или «|» отказан с причиной «такой тест покрывается мандатом на путь файла», ANSWER не создан.

        Проект `pult-vitest`, задача в `in_dev`. Имя теста идентификатора
        (в остальном годного: компонент записи, путь в области) несёт
        обратную кавычку либо «|» в случайном месте. Файл ответа — строка
        нового маркера, независимая проверка и матрица. Отказ, вывод несёт
        текст причины, ANSWER не добавлен.

        Ловит мутацию: обратная кавычка и «|» не проверяются особо —
        идентификатор разобран `parse_test_id` и принят (либо отказан
        матрицей без названной причины); проверен только один из двух
        символов — второй случай без причины.
        """
        project = self.project("vitest")
        task_id = self.task(project["name"])
        for symbol in ("`", "|"):
            with self.subTest(symbol=symbol, seed=self.seed):
                name = (f"{self.word()} {symbol}{self.word(4)} > "
                        f"{self.word()}")
                cid = project_profile.test_id(project["comp"], self.src_path(),
                                              name)
                out = self.assert_refused(
                    self.submit(task_id, self.id_answer([cid])), symbol)
                self.assertIn(FILE_MANDATE_REASON, out, self.why(out))


# AC-5 -----------------------------------------------------------------------

class MarkerOnlyNotInstructionTest(IdMandateSandbox):

    def test_ac5_marker_line_only_refused_not_instruction(self):
        """Ответ в `in_dev` только со строкой нового маркера, без матрицы, отказан; ANSWER нет.

        Проект `pult-vitest`, задача в `in_dev`. Файл ответа — одна строка
        нового маркера с годным идентификатором (компонент записи, путь в
        области), без матрицы и без независимой проверки. Отказ, ANSWER
        не добавлен, записи «ANSWER создан…» нет.

        Ловит мутацию: новый маркер не входит в `_has_mandate_lines` —
        файл принят как указание Оператора («ANSWER создан: указание
        Оператора»), ANSWER добавлен; новый маркер не входит в
        `MATRIX_MANDATE_MARKERS` — матрица не требуется, ответ принят.
        """
        project = self.project("vitest")
        task_id = self.task(project["name"])
        cid = self.vitest_id(project)
        result = self.submit(task_id, f"{NEW} {cid}\n")
        self.assert_refused(result, "только маркер")
        self.assertFalse([a for a in result[3] if a.startswith("ANSWER создан")],
                         self.why(f"журнал: {result[3]}"))


# AC-6 -----------------------------------------------------------------------

class InDevJournalKindTest(IdMandateSandbox):

    def test_ac6_in_dev_accepted_with_separate_journal_kind(self):
        """В `in_dev` новый маркер с матрицей и независимой проверкой принят; журнал — отдельный вид «мандат на ослабление теста по идентификатору: «…»».

        Проект `pult-vitest`, задача в `in_dev`. Идентификатор с пробелом
        внутри и « > »; «Что меняется» называет его целиком в одинарных
        обратных кавычках; строка «Независимая проверка: …». Ответ
        принят, ANSWER добавлен; в записи «ANSWER создан (…)» среди видов
        через «; » — «мандат на ослабление теста по идентификатору:
        «<идентификатор>»», а вид «мандат на ослабление тестов:»
        идентификатора не несёт.

        Ловит мутацию: элементы нового маркера дописаны в список прежнего
        вида (`test_elements`) — запись «мандат на ослабление тестов:
        <идентификатор>» без отдельного вида; вид пишется без «» вокруг
        идентификатора; новый маркер в `in_dev` не ведёт к записи вида —
        «ANSWER создан» без скобок.
        """
        project = self.project("vitest")
        task_id = self.task(project["name"])
        cid = self.vitest_id(project)
        self.assert_id_kind(self.submit(task_id, self.id_answer([cid])), cid,
                            "in_dev")


# AC-7 -----------------------------------------------------------------------

class IndependentCheckRequiredTest(IdMandateSandbox):

    def test_ac7_no_independent_check_refused(self):
        """Новый маркер с матрицей, но без строки «Независимая проверка:», отказан; ANSWER нет.

        Проект `pult-vitest`, задача в `in_dev`. Годный идентификатор,
        матрица называет его; строки независимой проверки нет. Отказ,
        вывод называет «Независимая проверка:», ANSWER не добавлен.

        Ловит мутацию: обязательность независимой проверки оставлена
        только за прежним маркером тестов (`_matrix_problems` смотрит на
        `TEST_WEAKENING_MANDATE_MARKER`) — ответ принят.
        """
        project = self.project("vitest")
        task_id = self.task(project["name"])
        cid = self.vitest_id(project)
        out = self.assert_refused(
            self.submit(task_id, self.id_answer([cid], check=False)),
            "без независимой проверки")
        self.assertIn("Независимая проверка:", out, self.why(out))


# AC-8 -----------------------------------------------------------------------

class ZonesExtendForeignLineTest(IdMandateSandbox):

    def test_ac8_zones_extend_matrix_file_with_new_marker_refused(self):
        """Файл матрицы `zones-extend` со строкой нового маркера отказан, как со строкой прежнего; без неё — принят.

        Проект `pult-vitest`, задача в `in_dev`. `zones-extend` на файл
        кода задачи с файлом матрицы, называющей этот файл; в файле —
        строка нового маркера с годным идентификатором. Отказ, вывод
        называет строку нового маркера, ANSWER не добавлен. Тот же файл
        без этой строки принят (ANSWER добавлен) — отказ дан строкой.

        Ловит мутацию: чужие строки файла матрицы ищутся только по
        `MANDATE_MARKERS` без нового маркера — файл принят, строка мандата
        уходит в ANSWER мимо проверки при записи.
        """
        project = self.project("vitest")
        task_id = self.task(project["name"])
        code = self.code
        line = f"{NEW} {self.vitest_id(project)}"
        table = matrix([(f"`{code}`", "фикстура сценария", "да",
                         "не покрыто", "ок при условии замена фикстуры")])
        for with_line in (True, False):
            with self.subTest(with_line=with_line, seed=self.seed):
                before = len(self.answers(task_id))
                text = (f"{line}\n\n" if with_line else "") + table
                out, failed = self.run_cmd(answer.cmd_zones_extend, task_id,
                                           code, None, self.text_file(text))
                added = len(self.answers(task_id)) - before
                if with_line:
                    self.assertTrue(failed, self.why(f"принято:\n{out}"))
                    self.assertIn(NEW, out, self.why(out))
                    self.assertEqual(0, added, self.why(out))
                else:
                    self.assertFalse(failed, self.why(f"отказ:\n{out}"))
                    self.assertEqual(1, added, self.why(out))


# AC-9 -----------------------------------------------------------------------

class SpecGateAcceptedTest(IdMandateSandbox):

    def test_ac9_spec_gate_accepts_new_marker_with_kind(self):
        """На гейте SPEC ответ со строкой нового маркера без прежнего маркера тестов принят; журнал — отдельный вид.

        Проект `pult-vitest`, задача в `spec_gate`. Файл ответа: строка
        нового маркера с годным идентификатором, независимая проверка,
        матрица. Принят, ANSWER добавлен; запись «ANSWER создан (…)» несёт
        вид «мандат на ослабление теста по идентификатору: «…»», вид
        прежнего маркера идентификатора не несёт.

        Ловит мутацию: `_spec_gate_answer_text` по-прежнему требует строку
        прежнего маркера тестов — отказ «принимает только мандат
        тестов»; на гейте SPEC вид нового маркера не пишется — «ANSWER
        создан» без скобок.
        """
        project = self.project("vitest")
        task_id = self.task(project["name"], state="spec_gate")
        cid = self.vitest_id(project)
        self.assert_id_kind(self.submit(task_id, self.id_answer([cid])), cid,
                            "spec_gate")


# AC-14 ----------------------------------------------------------------------

class ArtelCoverageCellUnchangedTest(IdMandateSandbox):

    def test_ac14_artel_and_none_profile_cell_rule_unchanged(self):
        """У артели и при профиле `None` ячейка с Vitest-идентификатором в кавычках отказана, с `tests/test_<…>.py` — принята.

        Задача артели и задача проекта без профиля (решение — пропуск,
        профиль `None`) в `in_dev`. Мандат зон на файл кода задачи;
        матрица — свойство остаётся, «Решение» «ок», «Чем покрыто после»
        — `web:src/<…>.test.ts::<имя>` в одинарных обратных кавычках
        (отказ, ANSWER не добавлен, вывод называет «не покрыто») либо
        `tests/test_<…>.py` (принято, ANSWER добавлен).

        Ловит мутацию: новое правило ячейки (идентификатор теста, любой
        путь) применено без проверки границы гейта исходов — у артели и
        при профиле `None` идентификатор Vitest признан покрытием.
        """
        tasks = {"артель": self.cell_task(ARTEL),
                 "профиль None": self.cell_task(self.project("bare")["name"])}
        for who, task_id in tasks.items():
            vid = project_profile.test_id("web", self.src_path(),
                                          self.vitest_name())
            for cell, accepted in ((f"`{vid}`", False),
                                   (f"tests/test_{self.word()}.py", True)):
                with self.subTest(who=who, cell=cell, seed=self.seed):
                    result = self.cell_outcome(task_id, cell)
                    if accepted:
                        self.assertFalse(result[0], self.why(result[1]))
                        self.assertEqual(1, result[2], self.why(result[1]))
                    else:
                        out = self.assert_refused(result, f"{who}: {cell}")
                        self.assertIn("не покрыто", out, self.why(out))


# AC-15 ----------------------------------------------------------------------

class WhatChangesCellTest(IdMandateSandbox):

    def test_ac15_what_changes_must_name_id_in_backticks_bytewise(self):
        """«Что меняется» при новом маркере: идентификатор не назван, назван без кавычек или с отличием в байт — отказ; ANSWER нет.

        Проект `pult-vitest`, задача в `in_dev`. Строка нового маркера с
        идентификатором (пробелы, « > »), независимая проверка; ячейка
        «Что меняется» единственной строки матрицы: (а) другой
        идентификатор того же файла; (б) тот же идентификатор без
        обратных кавычек; (в) в кавычках, но с одним байтом иначе
        (случайная строчная буква имени — заглавная). Каждый — отказ,
        ANSWER не добавлен. Контроль — та же ячейка точно в кавычках
        принята.

        Ловит мутацию: названность сверяется прежним `_names` по токенам —
        идентификатор с пробелами не назван ни в каком виде (контроль
        отказан) или назван без кавычек (б) принят; ячейка сверяется после
        `_normalized` (нижний регистр) — (в) принят.
        """
        project = self.project("vitest")
        task_id = self.task(project["name"])
        cid = self.vitest_id(project)
        _comp, path, name, _n = project_profile.parse_test_id(cid)
        other = project_profile.test_id(project["comp"], path,
                                        self.vitest_name())
        index = self.rng.choice([i for i, ch in enumerate(name) if ch.isalpha()])
        swapped = name[:index] + name[index].upper() + name[index + 1:]
        mutated = project_profile.test_id(project["comp"], path, swapped)
        for case, cell, accepted in (("не назван", f"`{other}`", False),
                                     ("без кавычек", cid, False),
                                     ("байт иначе", f"`{mutated}`", False),
                                     ("контроль", f"`{cid}`", True)):
            with self.subTest(case=case, seed=self.seed):
                result = self.submit(task_id, self.id_answer(
                    [cid], rows=[gone_row(cell)]))
                if accepted:
                    self.assertFalse(result[0], self.why(result[1]))
                    self.assertEqual(1, result[2], self.why(result[1]))
                else:
                    self.assert_refused(result, case)


# AC-16 ----------------------------------------------------------------------

class SpecGateRefusalsTest(IdMandateSandbox):

    def test_ac16_spec_gate_refusals(self):
        """На гейте SPEC новый маркер без матрицы, без независимой проверки или с неразборчивым идентификатором отказан; ANSWER нет.

        Проект `pult-vitest`, для каждого случая — своя задача в
        `spec_gate`: (а) строка нового маркера и независимая проверка, без
        матрицы; (б) строка и матрица, без независимой проверки; (в)
        `<компонент>:src/<…>.test.ts` без `::`, с матрицей и проверкой.
        Каждый — отказ, ANSWER не добавлен.

        Ловит мутацию: на гейте SPEC строка нового маркера принята без
        проверок `_read_checked_answer_file` (только признаком «мандат
        тестов есть») — все три приняты; проверка идентификатора стоит
        только в ветке `in_dev` — (в) принят.
        """
        project = self.project("vitest")
        cid = self.vitest_id(project)
        bad = f"{project['comp']}:{self.src_path()}"
        for case, text in (
                ("без матрицы", self.id_answer([cid], with_matrix=False)),
                ("без проверки", self.id_answer([cid], check=False)),
                ("неразборчивый", self.id_answer([bad]))):
            with self.subTest(case=case, seed=self.seed):
                task_id = self.task(project["name"], state="spec_gate")
                self.assert_refused(self.submit(task_id, text), case)


# AC-17 ----------------------------------------------------------------------

class ComponentIdCoverageTest(IdMandateSandbox):

    def test_ac17_component_id_in_backticks_covers(self):
        """Компонент в границе: идентификатор своего компонента в области между обратными кавычками — покрытие; без кавычек, неразборчивый, чужой компонент, путь вне области — нет.

        Проект `pult-vitest` (область `src/**`), задача в `in_dev`.
        Мандат зон на файл кода; матрица — свойство остаётся, «Решение»
        «ок»; «Чем покрыто после» несёт только: идентификатор
        `<компонент>:src/<…>.test.ts::<имя с пробелом и « > »>` в
        одинарных обратных кавычках (принято, ANSWER добавлен); тот же без
        кавычек; `<компонент>:src/<…>.test.ts` в кавычках (не разбирается);
        `z<…>:src/…::…` в кавычках (чужой компонент); `<компонент>:lib/…
        ::…` в кавычках (вне области) — отказ, ANSWER не добавлен.

        Ловит мутацию: идентификатор в ячейке признаётся без пары кавычек
        (поиск подстроки-пути `src/…` в любом токене) — случай без кавычек
        принят; компонент идентификатора не сверяется с
        `profile.component` — чужой принят; путь идентификатора не
        сверяется с `weakening_scope` — `lib/…` принят; правило
        идентификатора не добавлено — первый случай отказан.
        """
        project = self.project("vitest")
        task_id = self.cell_task(project["name"])
        comp = project["comp"]
        good = self.vitest_id(project)
        cases = [("в кавычках", f"`{good}`", True),
                 ("без кавычек", good, False),
                 ("неразборчивый", f"`{comp}:{self.src_path()}`", False),
                 ("чужой компонент", "`" + project_profile.test_id(
                     f"z{self.word()}", self.src_path(),
                     self.vitest_name()) + "`", False),
                 ("вне области", "`" + project_profile.test_id(
                     comp, f"lib/{self.word()}.test.ts",
                     self.vitest_name()) + "`", False)]
        for case, cell, accepted in cases:
            with self.subTest(case=case, cell=cell, seed=self.seed):
                result = self.cell_outcome(task_id, cell)
                if accepted:
                    self.assertFalse(result[0], self.why(result[1]))
                    self.assertEqual(1, result[2], self.why(result[1]))
                else:
                    self.assert_refused(result, case)


# AC-18 ----------------------------------------------------------------------

class ComponentPathCoverageTest(IdMandateSandbox):

    def test_ac18_non_py_path_in_scope_covers(self):
        """Компонент в границе: путь не `*.py` в области — покрытие (в кавычках и отдельным токеном); путь вне области — нет.

        Проект `pult-vitest` (область `src/**`), задача в `in_dev`.
        Мандат зон на файл кода; «Чем покрыто после» несёт только:
        `src/<…>.test.ts` в одинарных обратных кавычках и тот же путь
        отдельным токеном (принято, ANSWER добавлен); `lib/<…>.test.ts` в
        кавычках (отказ, ANSWER не добавлен).

        Ловит мутацию: у компонента покрытием остаётся только
        `_PY_PATH_RE` (`*.py`) — путь `.test.ts` отказан; путь не
        сверяется с `weakening_scope` — `lib/…` принят.
        """
        project = self.project("vitest")
        task_id = self.cell_task(project["name"])
        inside = self.src_path()
        cases = [("в кавычках", f"`{inside}`", True),
                 ("токеном", inside, True),
                 ("вне области", f"`lib/{self.word()}/{self.word()}.test.ts`",
                  False)]
        for case, cell, accepted in cases:
            with self.subTest(case=case, cell=cell, seed=self.seed):
                result = self.cell_outcome(task_id, cell)
                if accepted:
                    self.assertFalse(result[0], self.why(result[1]))
                    self.assertEqual(1, result[2], self.why(result[1]))
                else:
                    self.assert_refused(result, case)


# AC-19 ----------------------------------------------------------------------

class OutOfBoundsCellUnchangedTest(IdMandateSandbox):

    def test_ac19_out_of_bounds_profile_id_cell_refused(self):
        """Профиль вне границы гейта исходов — `test_profile`, `pytest-own` с `report`, компонент без `report`: идентификатор в кавычках в «Чем покрыто после» — отказ.

        Для каждого вида — проект (область `src/**`) и задача в `in_dev`.
        Мандат зон на файл кода; «Чем покрыто после» несёт только
        идентификатор `<компонент профиля>:src/<…>.test.ts::<имя>` (путь в
        области, без `*.py`) в одинарных обратных кавычках. Отказ, ANSWER
        не добавлен, вывод называет «не покрыто».

        Ловит мутацию: новое правило ячейки включено при любом непустом
        профиле (без `in_outcome_bounds`) — у `test_profile`, у
        `pytest-own` с `report` или у компонента без `report`
        идентификатор признан покрытием.
        """
        for kind in ("tp", "own", "noreport"):
            project = self.project(kind)
            task_id = self.cell_task(project["name"])
            cid = project_profile.test_id(project["comp"], self.src_path(),
                                          self.vitest_name())
            with self.subTest(kind=kind, seed=self.seed):
                out = self.assert_refused(self.cell_outcome(task_id, f"`{cid}`"),
                                          kind)
                self.assertIn("не покрыто", out, self.why(out))


if __name__ == "__main__":
    unittest.main()
