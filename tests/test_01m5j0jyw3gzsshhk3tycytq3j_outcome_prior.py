"""Гейт неослабления по исходам G3б-2: прежние версии тестов на коде ветки, заменяемые тесты, строгий режим, исключения в коде, доказательство на мерже.

Группа: долгоживущий
Красен до реализации: гейт исходов сравнивает только полные наборы базы и головы — третьей выписки головы с прежними версиями изменённых файлов `tests`/`test_support` нет (нет прогонов на ней, нет строки «прежние версии: …», нет находок «прежняя версия красная/нестабильна на коде ветки»), утверждённые замены гейт не читает (нет находок о заменах и строки «заменён по SPEC»), строгого режима и находок «исключение в коде» нет, сбой `diff --name-status`/`diff -M -U0` не отказывает, мандат на путь файла кода вне `weakening_scope` `answer` отклоняет; зелены и на базе ветки методы, держащие поведение без новых находок: AC-6 (без находок прежних версий старшая находка — единственная), AC-9 (а)/(в) и AC-10 (C пуст — третьей выписки нет), второй метод AC-22 (вне границы — прежний отказ `answer`), первый подслучай AC-25 (только «сломан правкой») и AC-30 (`test_profile` без гейта).

Стенд — песочница гейта исходов G3а-1а и её надстройка гейта мержа
(`tests.merge_outcome_sandbox.MergeOutcomeSandbox`
поверх `tests.outcome_gate_sandbox.OutcomeGateSandbox`):
настоящий git, учебный внешний проект с единственным компонентом
`junit-xml` на поддельном `pytest` (`python-ast` по умолчанию) либо
`pult-vitest` без Node (строгий режим), раннер подменён шпионом
`subprocess.Popen`, исход теста задаётся сценарием по стороне прогона.

Сторона «прежние версии» (`OLD`): дерево прогона — выписка головы
(`app.py` с меткой головы) в каталоге `scratch` гейта (рядом лежит маркер
владельца `liveness.GATE_OWNER_MARKER`), имя каталога выписки — не `base`
и не `head`. Исход теста на этой стороне — последовательность сценария
`cases[(путь, имя)][OLD]` (по умолчанию `passed`); «спасатель» `rescue` —
пути, при наличии которых в дереве прогона прежняя версия зелёная
(подмена сломанной функции добавленным `conftest.py`). Шпион
`subprocess.run` записывает каждую `worktree add` из кадров модуля гейта
(путь и наличие маркера владельца рядом в момент вызова) и, по правилу
сценария `git_fail`, отвечает отказом git.

Утверждённая замена — запись журнала `mandate.REPLACED_TESTS_ACTION` с
пунктом `guard.ReplacedTest(...).line` (та же форма, что пишет `approve`
гейта SPEC). Мандат Оператора — `answer.cmd_answer` с маркером и матрицей
неослабления.

Имена проектов, файлов, тестов, позиции строк и выбор исходов — из
`random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
поля профиля и `layers_of`, мандат на путь в границе, третья выписка с
восстановлением C и удалением файлов `A`, перепрогоны прежних версий,
находки замен, строгого режима и исключений в коде, порядок строк записи,
отпечаток с элементами замен и `_proven` по новым видам — все методы файла
зелёные; мутация «находка прежней версии при находке прежнего вида» красит
AC-6 и AC-17.
"""
import contextlib
import hashlib
import io
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

from orchestrator import answer, liveness, project_profile, store
from orchestrator.advance_gates import mandate
from scripts import guard
from tests.sandbox import make_project_repo
from tests.outcome_gate_sandbox import (
    ENTRY_HEAD, MATRIX_HEADERS, OutcomeGateSandbox, flow, js_source,
    py_source)
from tests.merge_outcome_sandbox import (
    MergeOutcomeSandbox)
from tests.prior_outcome_sandbox import (Moved, ReplacementSandbox, StrictSandbox)

GATE_MODULE = "orchestrator.advance_gates.outcome_integrity"
OLD = "old"
SIDES = ("base", "head")

OUTCOME_ACTION = "переход отклонён: гейт неослабления по исходам"
BROKEN_ACTION = "переход отклонён: гейт неослабления по исходам — сломан правкой"
PREPARE_ACTION = "переход отклонён: гейт неослабления по исходам — подготовка"
PASSED_ACTION = "гейт неослабления по исходам пройден"
MANDATE_MARKER = "Ослабление тестов разрешено:"
ID_MARKER = "Ослабление теста по идентификатору разрешено:"

GONE = "исчез"
SKIPPED = "стал пропуском"
PRIOR_RED = "прежняя версия красная на коде ветки"
PRIOR_UNSTABLE = "прежняя версия нестабильна на коде ветки"
REPL_MISSING = "заменяемый тест не найден в отчёте базы"
REPL_NOT_GREEN = "заменяемый тест не зелёный на базе"
REPL_NEEDLESS = "замена не нужна: прежняя версия зелёная на коде ветки"
STRICT = "строгий режим — правка существующего файла"
CODE_EXC = "исключение в коде"
FLAKY = "нестабилен и на базе"
REPLACED = "заменён по SPEC"
COVERED_BY_REPLACEMENT = " — покрыто мандатом замена SPEC → AC-{n}"
PRIOR_LINE = re.compile(r"^прежние версии: файлов (\d+); прогонов (\d+)$")
PROOF_LINE = re.compile(
    r"^голова ([0-9a-f]{40}); база ([0-9a-f]{40}); ключ (\S+); мандат (\S+)$")
COUNTS_MARK = "тестов базы"
# Подстроки исключений в коде — перечень требования 7 SPEC.
TOKENS = ("v8 ignore", "istanbul ignore", "c8 ignore", "eslint-disable",
          "import.meta.env.MODE", "process.env.VITEST", "NODE_ENV")
# Метка файла тестов, который на этой стороне даёт только запись ошибки
# уровня файла (сбор модуля).
FILE_ERROR_MARK = "# сбор-ошибка сценария"
CLAIM = "Ловит мутацию: фикстура сценария — исход теста другой."


# ------------------------------------------------- заменяемые тесты (требование 4)


class Ac14ReplacementMissingTest(ReplacementSandbox):

    def test_ac14_replacement_absent_from_base_report(self):
        """Утверждённый заменяемый тест, которого нет в отчёте базы, — находка «заменяемый тест не найден в отчёте базы» и отказ.

        Сценарий: проект `junit-xml`; утверждена замена идентификатора
        `<компонент>:<файл базы>::test_<слово>`, такого теста в файле базы
        нет. Отказ «… по исходам», строка детали начинается с «заменяемый
        тест не найден в отчёте базы: <id> — » и несёт «база: ».

        Ловит мутацию: замены гейт не читает — переход в `verifying`;
        отсутствие в отчёте базы пропускается молча — отказа нет.
        """
        rel = self.py_rel()
        project = self.junit({rel: [self.py_name(), self.py_name()]})
        t = self.task(project)
        rid = self.case_id(project, rel, self.py_name())
        self.approve_replacements(t, {rid: self.rng.randrange(1, 60)})
        rows, output = self.developer_advance(t)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        lines = self.starting(detail, f"{REPL_MISSING}: {rid} — ")
        self.assertEqual(len(lines), 1, self.explain(rows, output))
        self.assertIn("база: ", lines[0], self.explain(rows, output))


class Ac15ReplacementNotGreenTest(ReplacementSandbox):

    def test_ac15_replacement_red_on_base_or_base_rerun(self):
        """Заменяемый тест не из `PASS_TO_PASS` базы либо красный в перепрогоне базы — находка «заменяемый тест не зелёный на базе», отказ, строки «заменён по SPEC» нет.

        Сценарий (подслучай — свежая задача): тест исчез из отчёта ветки,
        прежняя версия `failed` во всех прогонах; (а) на базе `failed`
        (не `PASS_TO_PASS`); (б) база зелёна в полном прогоне и `failed` в
        первом перепрогоне. Отказ «… по исходам»: строка «заменяемый тест не
        зелёный на базе: <id> — …» с «база: »; ни одна запись не несёт
        «заменён по SPEC: <id>».

        Ловит мутацию: зелень базы берётся только из полного прогона — (б)
        без находки и с «заменён по SPEC»; не `PASS_TO_PASS` база не
        проверяется — (а) без находки.
        """
        for label, base in (("не PASS_TO_PASS", ["failed"]),
                            ("перепрогон базы", ["passed", "failed"])):
            with self.subTest(case=label, seed=self.seed):
                project, t, rel, rid, n, changes = self.replaced(
                    base, ["missing"], ["failed"])
                rows, output = self.developer_advance(t, changes)
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                lines = self.starting(detail, f"{REPL_NOT_GREEN}: {rid} — ")
                self.assertEqual(len(lines), 1, self.explain(rows, output))
                self.assertIn("база: ", lines[0], self.explain(rows, output))
                self.assertFalse(any(f"{REPLACED}: {rid}" in x for x in self.texts(rows)),
                                 self.explain(rows, output))


class Ac16ReplacementNeedlessTest(ReplacementSandbox):

    def test_ac16_prior_green_once_is_needless_finding(self):
        """Прежняя версия утверждённого заменяемого теста зелёная хотя бы в одном прогоне третьей выписки — находка «замена не нужна: прежняя версия зелёная на коде ветки» и отказ.

        Сценарий (подслучай — свежая задача): база зелёна, тест исчез из
        отчёта ветки; прежняя версия (а) `passed`; (б) `failed`, затем
        `passed` в перепрогоне. Отказ «… по исходам», строка начинается с
        «замена не нужна: прежняя версия зелёная на коде ветки: <id> —
        прежняя версия: ».

        Ловит мутацию: зелень прежней версии судится только по первому
        прогону — (б) без находки и гейт пройден; находка не пишется вовсе
        — (а) гейт пройден.
        """
        for label, old in (("зелёная", ["passed"]), ("зелёная в перепрогоне",
                                                      ["failed", "passed"])):
            with self.subTest(case=label, seed=self.seed):
                project, t, rel, rid, n, changes = self.replaced(
                    ["passed"], ["missing"], old)
                rows, output = self.developer_advance(t, changes)
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                self.assertTrue(self.starting(
                    detail, f"{REPL_NEEDLESS}: {rid} — прежняя версия: "),
                    self.explain(rows, output))


class Ac17ReplacementCoversTest(ReplacementSandbox):

    def test_ac17_gone_replaced_test_passes_covered_by_replacement(self):
        """Утверждённый заменяемый тест исчез на ветке, прежняя версия трижды красная при зелёной базе (`python-ast`) — гейт пройден, «исчез» покрыт заменой, одна находка на идентификатор.

        Сценарий: проект `junit-xml` (`python-ast`); тест базы зелёный,
        записи на ветке нет, прежняя версия `failed` во всех прогонах.
        Гейт пройден; запись несёт строку «заменён по SPEC: <id> → AC-<n>»,
        строку «исчез: <id> — …», кончающуюся «— покрыто мандатом замена
        SPEC → AC-<n>», и не несёт строки «прежняя версия красная на коде
        ветки: <id>».

        Ловит мутацию: замена не снимает «исчез» — отказ; находка прежней
        версии добавляется при находке «исчез» — вторая строка (и непокрытая
        находка); строка «заменён по SPEC» не пишется.
        """
        project, t, rel, rid, n, changes = self.replaced(
            ["passed"], ["missing"], ["failed"])
        rows, output = self.developer_advance(t, changes)
        self.no_gate_refusal(rows, output)
        detail = self.passed(rows, output)
        lines = detail.splitlines()
        self.assertIn(f"{REPLACED}: {rid} → AC-{n}", lines, self.explain(rows, output))
        gone = self.starting(detail, f"{GONE}: {rid} — ")
        self.assertEqual(len(gone), 1, self.explain(rows, output))
        self.assertTrue(gone[0].endswith(COVERED_BY_REPLACEMENT.format(n=n)),
                        self.explain(rows, output))
        self.assertFalse(self.starting(detail, f"{PRIOR_RED}: {rid}"),
                         self.explain(rows, output))

    def test_ac17_present_replaced_test_prior_red_covered(self):
        """Утверждённый заменяемый тест есть на ветке и зелёный (файл изменён), прежняя версия трижды красная — гейт пройден, находка прежней версии покрыта заменой.

        Сценарий: проект `junit-xml` (`python-ast`); тест базы и ветки
        зелёный, файл изменён веткой (комментарий), прежняя версия `failed`
        во всех прогонах. Гейт пройден; запись несёт «заменён по SPEC: <id>
        → AC-<n>» и строку «прежняя версия красная на коде ветки: <id> — …»,
        кончающуюся «— покрыто мандатом замена SPEC → AC-<n>».

        Ловит мутацию: замена не снимает «прежняя версия красная» — отказ;
        источник покрытия в строке — не «замена SPEC → AC-<n>».
        """
        project, t, rel, rid, n, changes = self.replaced(
            ["passed"], ["passed"], ["failed"], edit=True)
        rows, output = self.developer_advance(t, changes)
        self.no_gate_refusal(rows, output)
        detail = self.passed(rows, output)
        self.assertIn(f"{REPLACED}: {rid} → AC-{n}", detail.splitlines(),
                      self.explain(rows, output))
        red = self.starting(detail, f"{PRIOR_RED}: {rid} — ")
        self.assertEqual(len(red), 1, self.explain(rows, output))
        self.assertTrue(red[0].endswith(COVERED_BY_REPLACEMENT.format(n=n)),
                        self.explain(rows, output))


class Ac18ReplacementLimitsTest(ReplacementSandbox):

    def test_ac18_replacement_does_not_cover_skipped(self):
        """Утверждённая замена не снимает «стал пропуском» своего теста — отказ.

        Сценарий: проект `junit-xml`; утверждённый заменяемый тест на ветке
        `skipped`, база зелёна, прежняя версия `failed` во всех прогонах.
        Отказ «… по исходам» со строкой «стал пропуском: <id> — …».

        Ловит мутацию: замена снимает любую находку своего идентификатора —
        гейт пройден.
        """
        project, t, rel, rid, n, changes = self.replaced(
            ["passed"], ["skipped"], ["failed"])
        rows, output = self.developer_advance(t, changes)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertTrue(self.starting(detail, f"{SKIPPED}: {rid} — "),
                        self.explain(rows, output))

    def test_ac18_undeclared_prior_red_covered_only_by_operator(self):
        """Не заявленный тест, красный на третьей выписке, снимает только мандат Оператора — утверждённая замена соседа его не снимает.

        Сценарий (подслучай — свежая задача): в файле утверждённый
        заменяемый тест (исчез на ветке, прежняя версия красная) и не
        заявленный тест X (зелёный на базе и ветке, прежняя версия `failed`
        во всех прогонах); файл изменён веткой. (а) без мандата — отказ «…
        по исходам» со строкой «прежняя версия красная на коде ветки:
        <X>»; (б) мандат Оператора на путь файла — отказа гейта нет.

        Ловит мутацию: замена покрывает находки всего файла заменяемого
        теста — (а) гейт пройден; мандат Оператора не проверяется для
        находок прежних версий — (б) отказ.
        """
        for label in ("без мандата", "мандат Оператора"):
            with self.subTest(case=label, seed=self.seed):
                project, t, rel, rid, n, changes = self.replaced(
                    ["passed"], ["missing"], ["failed"], edit=True)
                x = self.other
                self.cases[(rel, x)] = {"base": ["passed"], "head": ["passed"],
                                        OLD: ["failed"]}
                if label == "мандат Оператора":
                    self.grant(t, paths=[rel])
                rows, output = self.developer_advance(
                    t, changes, finished=label == "мандат Оператора")
                if label == "без мандата":
                    detail = self.refusal(rows, output, OUTCOME_ACTION)
                    xid = self.case_id(project, rel, x)
                    self.assertTrue(self.starting(detail, f"{PRIOR_RED}: {xid} — "),
                                    self.explain(rows, output))
                else:
                    self.no_gate_refusal(rows, output)


class Ac26RecordOrderTest(ReplacementSandbox):

    def test_ac26_passed_record_line_order(self):
        """Порядок строк записи пройденного гейта: счёт, доказательство, «прежние версии», «нестабилен и на базе», «заменён по SPEC», покрытые находки.

        Сценарий: проект `junit-xml`; файл A с утверждённым заменяемым
        тестом (исчез на ветке, прежняя версия трижды красная, база
        зелёна); файл B изменён веткой, его тест Y — прежняя версия
        красная, база красна в одном перепрогоне. Гейт пройден; индексы
        строк: счёт (с «тестов базы») — 0, доказательство — 1, далее строго
        по возрастанию «прежние версии: …», «нестабилен и на базе: <Y>»,
        «заменён по SPEC: …», строка находки «исчез … — покрыто мандатом …».

        Ловит мутацию: строка «прежние версии» дописана в конец записи или
        перед доказательством; «заменён по SPEC» после покрытых находок;
        строка доказательства сдвинута со второй позиции.
        """
        b_rel, y = self.py_rel(), self.py_name()
        b_names = [y, self.py_name()]
        project, t, rel, rid, n, _changes = self.replaced(
            ["passed"], ["missing"], ["failed"], more={b_rel: b_names})
        base = ["passed", "passed", "passed"]
        base[self.rng.choice((1, 2))] = "failed"
        self.cases[(b_rel, y)] = {"base": base, "head": ["passed"], OLD: ["failed"]}
        rows, output = self.developer_advance(t, {b_rel: self.edited_py(b_names)})
        self.no_gate_refusal(rows, output)
        lines = self.passed(rows, output).splitlines()
        yid = self.case_id(project, b_rel, y)

        def index(pred, what):
            found = [i for i, line in enumerate(lines) if pred(line)]
            self.assertTrue(found, self.explain(rows, output) + f"\nнет строки: {what}")
            return found[0]
        order = [index(lambda s: COUNTS_MARK in s, "счёт"),
                 index(lambda s: PROOF_LINE.match(s.strip()), "доказательство"),
                 index(lambda s: PRIOR_LINE.match(s), "прежние версии"),
                 index(lambda s: s == f"{FLAKY}: {yid}", "нестабилен и на базе"),
                 index(lambda s: s == f"{REPLACED}: {rid} → AC-{n}", "заменён по SPEC"),
                 index(lambda s: s.startswith(f"{GONE}: {rid} — "), "покрытая находка")]
        self.assertEqual(order[:2], [0, 1], self.explain(rows, output))
        self.assertEqual(order, sorted(order), self.explain(rows, output) + f"\n{order}")


class Ac34NeedlessWithGoneTest(ReplacementSandbox):

    def test_ac34_needless_added_despite_gone(self):
        """Утверждённый заменяемый тест исчез на ветке, его прежняя версия зелёная — отказ со строкой «замена не нужна: …» по идентификатору; «исчез» замена снимает.

        Сценарий: проект `junit-xml`; база зелёна, записи на ветке нет,
        прежняя версия `passed`. Отказ «… по исходам»: строка «замена не
        нужна: прежняя версия зелёная на коде ветки: <id> — …» есть, строки
        «исчез: <id> — …» в детали нет.

        Ловит мутацию: правило «одна находка на идентификатор» применено и
        к находкам требования 4 — при «исчез» находки «замена не нужна» нет
        (а «исчез» покрыт — гейт пройден).
        """
        project, t, rel, rid, n, changes = self.replaced(
            ["passed"], ["missing"], ["passed"])
        rows, output = self.developer_advance(t, changes)
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertTrue(self.starting(detail, f"{REPL_NEEDLESS}: {rid} — "),
                        self.explain(rows, output))
        self.assertFalse(self.starting(detail, f"{GONE}: {rid} — "),
                         self.explain(rows, output))


# ------------------------------------------------------- строгий режим (требование 5)


class Ac19StrictModeTest(StrictSandbox):

    def test_ac19_strict_edit_and_mandates(self):
        """Строгий режим: правка существующего файла `tests` — находка «строгий режим — правка существующего файла: <путь> — статус M»; снимает её только мандат на путь.

        Сценарий (подслучай — свежая задача, проект `pult-vitest`): ветка
        правит существующий файл тестов (комментарий); (а) без мандата —
        отказ «… по исходам» со строкой находки; (б) мандат Оператора
        «Ослабление тестов разрешено: <путь>» — отказа гейта нет; (в) мандат
        по идентификатору теста этого файла; (г) мандат на префикс
        `путь::имя` — в (в) и (г) отказ с той же строкой.

        Ловит мутацию: строгого режима нет — (а) гейт пройден; покрытие
        находки пути правилом `_covering_pair` (мандат по идентификатору или
        префикс) — (в)/(г) без отказа; мандат на путь не сверяется — (б)
        отказ.
        """
        for label in ("без мандата", "путь", "идентификатор", "префикс"):
            with self.subTest(case=label, seed=self.seed):
                rel, names = self.js_rel(), [self.js_case(), self.js_case()]
                project = self.vitest({rel: names})
                t = self.task(project)
                cid = self.case_id(project, rel, names[0])
                covered = f"`{rel}`"
                if label == "путь":
                    self.grant(t, paths=[rel], covered=covered)
                elif label == "идентификатор":
                    self.grant(t, ids=[cid], covered=covered)
                elif label == "префикс":
                    self.grant(t, paths=[f"{rel}::{names[0]}"], covered=covered)
                rows, output = self.developer_advance(
                    t, {rel: self.edited_js(names)}, finished=label != "без мандата")
                line = f"{STRICT}: {rel} — статус M"
                if label == "путь":
                    self.no_gate_refusal(rows, output)
                else:
                    detail = self.refusal(rows, output, OUTCOME_ACTION)
                    self.assertIn(line, detail.splitlines(), self.explain(rows, output))

    def test_ac19_strict_deleted_and_renamed(self):
        """Строгий режим: удалённый файл `tests` — находка со статусом `D`; переименованный — находка с прежним путём и статусом `R…`.

        Сценарий (подслучай — свежая задача, `pult-vitest`): ветка (а)
        удаляет файл тестов; (б) переименовывает его без правки строк. Отказ
        «… по исходам»; в (а) строка «строгий режим — правка существующего
        файла: <путь> — статус D», в (б) — строка, начинающаяся «строгий
        режим — правка существующего файла: <прежний путь> — статус R».

        Ловит мутацию: в строгий режим идут только `M` — (а)/(б) без строки;
        у `R` берётся новый путь — строка с новым путём.
        """
        for label in ("D", "R"):
            with self.subTest(case=label, seed=self.seed):
                rel, names = self.js_rel(), [self.js_case()]
                project = self.vitest({rel: names, self.js_rel(): [self.js_case()]})
                t = self.task(project)
                change = {rel: None} if label == "D" else {self.js_rel(): Moved(rel)}
                rows, output = self.developer_advance(t, change)
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                prefix = f"{STRICT}: {rel} — статус {label}"
                self.assertTrue(self.starting(detail, prefix), self.explain(rows, output))


class Ac20StrictReplacementTest(StrictSandbox):

    def test_ac20_replacement_file_strict_without_path_mandate(self):
        """Строгий режим: файл утверждённого заменяемого теста без мандата на путь — находка строгого режима и отказ; замена снимает лишь «исчез» и «прежняя версия красная».

        Сценарий (подслучай — свежая задача, `pult-vitest`, утверждена
        замена теста R, база R зелёна, прежняя версия R `failed` во всех
        прогонах): (а) ветка удаляет R из файла; (б) R остаётся в тексте
        (записи на ветке нет), ветка правит соседний тест того же файла. В
        обоих — отказ «… по исходам» со строкой «строгий режим — правка
        существующего файла: <путь> — статус M» и без строк «исчез: <R>» и
        «прежняя версия красная на коде ветки: <R>».

        Ловит мутацию: утверждённая замена снимает находку строгого режима
        файла своего теста — гейт пройден; замена не снимает «исчез» — в
        детали строка «исчез: <R>».
        """
        for label in ("удалён", "сосед"):
            with self.subTest(case=label, seed=self.seed):
                rel, rname, other = self.js_rel(), self.js_case(), self.js_case()
                project = self.vitest({rel: [rname, other]})
                t = self.task(project)
                rid = self.case_id(project, rel, rname)
                self.approve_replacements(t, {rid: self.rng.randrange(1, 60)})
                self.cases[(rel, rname)] = {"base": ["passed"], "head": ["missing"],
                                            OLD: ["failed"]}
                if label == "удалён":
                    text = js_source([other])
                else:
                    text = (js_source([rname]) + f"// {CLAIM}\nit('{other}', () => "
                            "{ expect(2).toBe(2); });\n")
                rows, output = self.developer_advance(t, {rel: text})
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                self.assertIn(f"{STRICT}: {rel} — статус M", detail.splitlines(),
                              self.explain(rows, output))
                self.assertFalse(self.starting(detail, f"{GONE}: {rid} — "),
                                 self.explain(rows, output))
                self.assertFalse(self.starting(detail, f"{PRIOR_RED}: {rid} — "),
                                 self.explain(rows, output))


class Ac21PythonAstTest(StrictSandbox):

    def test_ac21_python_ast_only_non_py_support_is_strict(self):
        """Профиль с `python-ast`: правка `.py` под `test_support` и правка файла тестов находки строгого режима не дают, правка не `.py` под `test_support` — даёт.

        Сценарий: проект `junit-xml` с `test_support: [support/**]`; ветка
        правит `support/<имя>.py`, `support/<имя>.json` и существующий файл
        тестов. Отказ «… по исходам»; строки находок строгого режима —
        ровно одна, «строгий режим — правка существующего файла:
        support/<имя>.json — статус M».

        Ловит мутацию: строгий режим не смотрит на слои — находки и на
        `.py`, и на файл тестов; строгий режим выключен целиком при
        `python-ast` — находки `.json` нет и гейт пройден.
        """
        helper, data = f"support/{self.word()}.py", f"support/{self.word()}.json"
        rel, names = self.py_rel(), [self.py_name()]
        project = self.junit({rel: names}, extra={"test_support": flow(["support/**"])},
                             files={helper: "HELPER = 1\n", data: '{"a": 1}\n'})
        t = self.task(project)
        rows, output = self.developer_advance(
            t, {helper: "HELPER = 2\n", data: '{"a": 2}\n', rel: self.edited_py(names)})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertEqual(self.starting(detail, f"{STRICT}: "),
                         [f"{STRICT}: {data} — статус M"], self.explain(rows, output))


# --------------------------------------------- исключения в коде (требования 6, 7)

def env_lines(n: int) -> list:
    return [f"VALUE_{i} = {i}" for i in range(n)]


class Ac22PathMandateTest(StrictSandbox):

    def test_ac22_code_path_mandate_in_bounds_covers_exception(self):
        """У профиля в границе мандат «Ослабление тестов разрешено:» на путь файла кода вне `weakening_scope` принят командой `answer` и снимает находку «исключение в коде».

        Сценарий: проект `junit-xml` (`weakening_scope: tests/**`); ветка
        добавляет в `lib/<имя>.py` строку с `NODE_ENV`. Первый `advance` —
        отказ «… по исходам» со строкой «исключение в коде: <путь> — строка
        <n>: NODE_ENV»; затем `answer` Оператора с мандатом на этот путь —
        принят; повторный `advance` — отказа гейта нет, запись пройденного
        гейта несёт строку этой находки «— покрыто мандатом ANSWER-…».

        Ловит мутацию: прежнее правило области — `answer` отклоняет путь
        вне `weakening_scope`; находка пути покрывается правилом теста —
        повторный `advance` снова отказ.
        """
        code = f"lib/{self.word()}.py"
        project = self.junit({self.py_rel(): [self.py_name()]})
        t = self.task(project)
        lines = env_lines(self.rng.randint(1, 4))
        lines.insert(self.rng.randint(0, len(lines)), "MODE = __import__('os').environ['NODE_ENV']")
        number = lines.index("MODE = __import__('os').environ['NODE_ENV']") + 1
        finding = f"{CODE_EXC}: {code} — строка {number}: NODE_ENV"
        rows, output = self.developer_advance(t, {code: "\n".join(lines) + "\n"})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertIn(finding, detail.splitlines(), self.explain(rows, output))
        self.grant(t, paths=[code])
        rows, output = self.developer_advance(t, {}, finished=True)
        self.no_gate_refusal(rows, output)
        covered = self.starting(self.passed(rows, output), f"{finding} — покрыто мандатом ANSWER-")
        self.assertEqual(len(covered), 1, self.explain(rows, output))

    def test_ac22_out_of_bounds_code_path_refused(self):
        """У профиля вне границы (`test_profile`) элемент мандата на путь вне `weakening_scope` — прежний отказ «путь вне области …».

        Сценарий: учебный проект с записью `test_profile`; `answer`
        Оператора с мандатом на `lib/<имя>.py`. Команда отказывает, текст
        называет элемент и «путь вне области».

        Ловит мутацию: расширение области мандата действует и вне границы
        `in_outcome_bounds` — `answer` принят.
        """
        project = self.junit_project({self.py_rel(): [self.py_name()]}, test_profile=True)
        t = self.task(project)
        code = f"lib/{self.word()}.py"
        ok, output = self.operator_answer(t, paths=[code])
        self.assertFalse(ok, self.note(output))
        self.assertIn(code, output, self.note(output))
        self.assertIn("путь вне области", output, self.note(output))


class Ac23CodeExceptionsTest(StrictSandbox):

    def test_ac23_each_token_in_added_code_line_and_exemptions(self):
        """Каждая подстрока перечня в добавленной строке файла кода — находка «исключение в коде: <путь> — строка <n>: <подстрока>» с номером по файлу головы; удалённая строка, файл `tests`, файл `test_support`, двоичный файл и переименование без правки строк находок не дают.

        Сценарий: проект `pult-vitest` с `test_support:
        [frontend/setup/**]`; ветка вставляет в `lib/app.js` по строке на
        каждую подстроку на случайные позиции; удаляет строку с подстрокой
        из `lib/gone.js`; переименовывает `lib/old.js` (строка с подстрокой
        в базе) без правки; добавляет строку с подстрокой в файл тестов и в
        файл `test_support`; добавляет двоичный файл с подстрокой. Отказ
        «… по исходам»; строки «исключение в коде: …» детали — ровно по
        одной на каждую подстроку `lib/app.js` с верным номером строки.

        Ловит мутацию: номер строки по файлу базы или по ханку диффа — не
        тот номер; поиск по всем строкам диффа (с удалёнными) — строка для
        `lib/gone.js`; переименование считается новым файлом — строка для
        нового пути; файлы `tests`/`test_support` или двоичный не
        исключены — лишние строки; одна находка на строку при нескольких
        файлах — не хватает строк.
        """
        rel, names = self.js_rel(), [self.js_case()]
        setup = f"frontend/setup/{self.word()}.js"
        base_app = [f"const a{i} = {i};" for i in range(self.rng.randint(2, 6))]
        files = {"lib/app.js": "\n".join(base_app) + "\n",
                 "lib/gone.js": "const g = 1;\n// eslint-disable-next-line\nconst h = 2;\n",
                 "lib/old.js": "const o = 1; /* istanbul ignore next */\n",
                 setup: "export default {};\n"}
        project = self.vitest({rel: names}, extra={"test_support": flow(["frontend/setup/**"])},
                              files=files)
        t = self.task(project)
        head_app = list(base_app)
        for i, token in enumerate(self.rng.sample(TOKENS, len(TOKENS))):
            head_app.insert(self.rng.randint(0, len(head_app)),
                            f"const t{i} = '{token}';")
        expected = set()
        for number, line in enumerate(head_app, start=1):
            for token in TOKENS:
                if f"'{token}'" in line:
                    expected.add(f"{CODE_EXC}: lib/app.js — строка {number}: {token}")
        rows, output = self.developer_advance(t, {
            "lib/app.js": "\n".join(head_app) + "\n",
            "lib/gone.js": "const g = 1;\nconst h = 2;\n",
            "lib/new.js": Moved("lib/old.js"),
            rel: js_source(names) + "// v8 ignore next\n",
            setup: "export default {};\nconst m = process.env.VITEST;\n",
            f"lib/{self.word()}.bin": b"\x00\x01NODE_ENV\x00\xff\x00",
        })
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertEqual(set(self.starting(detail, f"{CODE_EXC}: ")), expected,
                         self.explain(rows, output))
        self.assertEqual(len(expected), len(TOKENS), self.note(str(head_app)))


class Ac24ComponentPathsTest(StrictSandbox):

    def test_ac24_paths_limit_exception_scope(self):
        """Единственный компонент без `paths` — проверка исключений охватывает любой файл репозитория вне `tests`/`test_support`; с `paths` — только файлы под `paths`.

        Сценарий (подслучай — свежая задача, `junit-xml`): ветка добавляет
        строку с `NODE_ENV` в `lib/<имя>.py` и в `misc/<имя>.txt`; (а)
        компонент без `paths` — находки по обоим файлам; (б) `paths: ^lib/`
        — находка только по `lib/<имя>.py`.

        Ловит мутацию: `paths` не читается — в (б) находка и по `misc/…`;
        без `paths` проверяются только файлы `*.py` или только под
        `weakening_scope` — в (а) нет находки по `misc/…`.
        """
        for label in ("без paths", "paths"):
            with self.subTest(case=label, seed=self.seed):
                extra = {"paths": "^lib/"} if label == "paths" else None
                project = self.junit({self.py_rel(): [self.py_name()]}, extra=extra)
                t = self.task(project)
                code, misc = f"lib/{self.word()}.py", f"misc/{self.word()}.txt"
                rows, output = self.developer_advance(t, {
                    code: "import os\nMODE = os.environ['NODE_ENV']\n",
                    misc: "mode: NODE_ENV\n"})
                detail = self.refusal(rows, output, OUTCOME_ACTION)
                expected = {f"{CODE_EXC}: {code} — строка 2: NODE_ENV"}
                if label == "без paths":
                    expected.add(f"{CODE_EXC}: {misc} — строка 1: NODE_ENV")
                self.assertEqual(set(self.starting(detail, f"{CODE_EXC}: ")), expected,
                                 self.explain(rows, output))


class Ac25RefusalActionTest(StrictSandbox):

    def test_ac25_broken_only_vs_new_kind_action_and_hint(self):
        """Отказ только из «сломан правкой» — действие «… — сломан правкой»; при находке нового вида — общее действие, подсказка называет мандат на путь.

        Сценарий (подслучай — свежая задача, `junit-xml`): тест A трижды
        красный на ветке, база зелёна; (а) других находок нет — действие «…
        — сломан правкой»; (б) ещё изменён файл теста B, прежняя версия
        которого трижды красная, — действие «переход отклонён: гейт
        неослабления по исходам», строка подсказки «дальше: …» называет
        маркер «Ослабление тестов разрешено:» и путь.

        Ловит мутацию: находки нового вида причислены к «сломан правкой» —
        в (б) действие «… — сломан правкой»; подсказка прежняя (без пути) —
        в (б) нет слова «путь».
        """
        for label in ("только сломан", "новый вид"):
            with self.subTest(case=label, seed=self.seed):
                a_rel, a = self.py_rel(), self.py_name()
                b_rel, b = self.py_rel(), self.py_name()
                project = self.junit({a_rel: [a, self.py_name()], b_rel: [b]})
                t = self.task(project)
                self.cases[(a_rel, a)] = {"base": ["passed"], "head": ["failed"]}
                changes = {}
                if label == "новый вид":
                    self.cases[(b_rel, b)] = {"base": ["passed"], "head": ["passed"],
                                              OLD: ["failed"]}
                    changes = {b_rel: self.edited_py([b])}
                rows, output = self.developer_advance(t, changes)
                if label == "только сломан":
                    self.refusal(rows, output, BROKEN_ACTION)
                    continue
                self.refusal(rows, output, OUTCOME_ACTION)
                hints = [line for line in output.splitlines() if "дальше:" in line]
                self.assertTrue(hints, self.explain(rows, output))
                self.assertIn(MANDATE_MARKER, hints[-1], self.explain(rows, output))
                self.assertIn("путь", hints[-1], self.explain(rows, output))


class Ac31NoTestsFieldExceptionsTest(StrictSandbox):

    def test_ac31_new_and_unreported_files_under_scope(self):
        """Компонент без поля `tests`: новый модуль кода и существующий файл под `weakening_scope` без записей отчёта — находки «исключение в коде»; новый файл тестов с записями в отчёте головы — нет; тот же текст в новом файле кода вне `weakening_scope` — находка.

        Сценарий: проект `junit-xml` с `weakening_scope: [tests/**,
        src/**]`, в базе `src/util.py` (записей отчёта нет); ветка добавляет
        `src/<имя>.py` со строкой `NODE_ENV` (а), дописывает строку с
        `NODE_ENV` в `src/util.py` (б), добавляет долгоживущий
        `tests/test_<id>_x.py` с тестом, где `monkeypatch.setenv("NODE_ENV",
        …)`, и файл `lib/<имя>.py` с тем же текстом (в). Отказ «… по
        исходам»; строки «исключение в коде: …» — ровно для `src/<имя>.py`,
        `src/util.py` и `lib/<имя>.py` с номерами строк головы.

        Ловит мутацию: все файлы `A` под `weakening_scope` считаются
        тестовыми — нет находки (а); тестовым считается любой файл под
        `weakening_scope` — нет находки (б); новый файл тестов с записями
        считается кодом — лишняя строка для `tests/…`.
        """
        project = self.junit({self.py_rel(): [self.py_name()]},
                             extra={"weakening_scope": flow(["tests/**", "src/**"])},
                             files={"src/util.py": "VALUE = 1\n"})
        t = self.task(project)
        new_mod, lib = f"src/{self.word()}.py", f"lib/{self.word()}.py"
        env_test = ('"""Тесты сценария."""\n\n\ndef test_env(monkeypatch):\n'
                    f'    """{CLAIM}"""\n'
                    '    monkeypatch.setenv("NODE_ENV", "test")\n')
        rows, output = self.developer_advance(t, {
            new_mod: "import os\nMODE = os.environ.get('NODE_ENV')\n",
            "src/util.py": "VALUE = 1\nimport os\nMODE = os.environ['NODE_ENV']\n",
            f"tests/test_{t.low}_x.py": env_test,
            lib: env_test})
        detail = self.refusal(rows, output, OUTCOME_ACTION)
        self.assertEqual(set(self.starting(detail, f"{CODE_EXC}: ")), {
            f"{CODE_EXC}: {new_mod} — строка 2: NODE_ENV",
            f"{CODE_EXC}: src/util.py — строка 3: NODE_ENV",
            f"{CODE_EXC}: {lib} — строка 6: NODE_ENV"}, self.explain(rows, output))


# --------------------------------------------------------------- AC-27

class Ac27MergeProofTest(ReplacementSandbox):

    def merged_ready(self):
        """Задача, прошедшая выход из `in_dev` с покрытыми находками новых
        видов: «исключение в коде» под мандатом на путь и «исчез» под
        утверждённой заменой. (задача, идентификатор, номер, путь, причина
        замены, деталь записи)."""
        rel, rname, other = self.py_rel(), self.py_name(), self.py_name()
        project = self.junit({rel: [rname, other]})
        t = self.task(project)
        rid = self.case_id(project, rel, rname)
        n = self.rng.randrange(1, 60)
        reason = f"замена сценария {self.word()}"
        self.journal_replacements(t, {rid: n}, reason)
        self.cases[(rel, rname)] = {"base": ["passed"], "head": ["missing"], OLD: ["failed"]}
        code = f"lib/{self.word()}.py"
        self.grant(t, paths=[code])
        rows, output = self.developer_advance(
            t, {code: "import os\nMODE = os.environ['NODE_ENV']\n"}, finished=True)
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        detail = self.passed(rows, output)
        self.assertTrue(self.starting(detail, f"{CODE_EXC}: {code} — "),
                        self.explain(rows, output))
        self.assertTrue(self.starting(detail, f"{GONE}: {rid} — "), self.explain(rows, output))
        return t, rid, n, code, reason, detail

    def journal_replacements(self, t, items: dict, reason: str) -> None:
        detail = "\n".join(guard.ReplacedTest(cid, n, reason).line
                           for cid, n in items.items())
        store.journal(self.conn, t.id, "operator", mandate.REPLACED_TESTS_ACTION, detail)

    def test_ac27_proof_with_new_kinds_skips_run(self):
        """Запись пройденного гейта с покрытыми находками нового вида (путь и замена) и той же четвёркой — на мерже нет ни выписки прежних версий, ни полного набора; элементы пути и замены — в отпечатке.

        Сценарий: задача проходит выход из `in_dev` с находкой «исключение
        в коде» под мандатом на путь и находкой «исчез» под утверждённой
        заменой; отпечаток строки доказательства — sha256 отсортированных
        элементов `<путь>` и `замена:<id>→AC-<n>`, соединённых переводом
        строки. Задача на `merge_gate`, `approve`: полный набор не звался,
        третьей выписки и прогонов прежних версий нет, задача в `done`.

        Ловит мутацию: `_proven` не разбирает строки находок новых видов —
        доказательство не совпадает, полный набор прогнан; элемент пути
        или замены не входит в отпечаток — отпечаток иной.
        """
        t, rid, n, code, _reason, detail = self.merged_ready()
        fields = [PROOF_LINE.match(line.strip()) for line in detail.splitlines()]
        fields = [m.groups() for m in fields if m]
        self.assertTrue(fields, self.note(detail))
        wanted = hashlib.sha256("\n".join(sorted(
            {code, f"замена:{rid}→AC-{n}"})).encode("utf-8")).hexdigest()
        self.assertEqual(fields[0][3], wanted, self.note(detail))
        self.to_merge_gate(t)
        rows, output = self.approve(t)
        self.assertEqual(self.suite_calls, [], self.explain(rows, output))
        self.assertEqual(self.third_adds(), [], self.explain(rows, output))
        self.assertEqual(self.old_runs(), [], self.explain(rows, output))
        self.assertEqual(self.state(t), "done", self.explain(rows, output))

    def test_ac27_same_replacements_reapproved_no_run(self):
        """Повторное утверждение SPEC с тем же составом замен после записи — на мерже прогона нет.

        Сценарий: как в доказательстве с новыми видами; после выхода из
        `in_dev` записана ещё одна запись утверждения с той же строкой
        замены. `approve`: полный набор не звался, задача в `done`.

        Ловит мутацию: доказательство сверяет время или номер последней
        записи утверждения, а не состав замен — прогон на мерже.
        """
        t, rid, n, _code, reason, _detail = self.merged_ready()
        self.journal_replacements(t, {rid: n}, reason)
        self.to_merge_gate(t)
        rows, output = self.approve(t)
        self.assertEqual(self.suite_calls, [], self.explain(rows, output))
        self.assertEqual(self.state(t), "done", self.explain(rows, output))

    def test_ac27_changed_replacements_rerun_gate(self):
        """Смена содержимого утверждённых замен после записи (другой номер критерия) — на мерже гейт исполняется прогоном.

        Сценарий: как в доказательстве с новыми видами; после выхода из
        `in_dev` записано утверждение той же замены на другой критерий.
        `approve`: полный набор звался.

        Ловит мутацию: элементы «замена:…» не входят в отпечаток либо
        берутся только покрывшие находки по старой записи — доказательство
        совпадает, прогона нет.
        """
        t, rid, n, _code, reason, _detail = self.merged_ready()
        self.journal_replacements(t, {rid: n % 59 + 1}, reason)
        self.to_merge_gate(t)
        rows, output = self.approve(t)
        self.assertTrue(self.suite_calls, self.explain(rows, output))


if __name__ == "__main__":
    unittest.main()
