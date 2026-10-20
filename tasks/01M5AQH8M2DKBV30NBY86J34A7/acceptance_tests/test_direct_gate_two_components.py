"""Прямой вызов гейта честного `FAIL_TO_PASS`: проект из двух компонентов (AC-9) и правило планки, не построенное по записи (AC-12).

Группа: разовый
Красен до реализации: функции `_tests_writing_fail_to_pass_gate` в `orchestrator/advance_gates/tests_writing.py` ещё нет — `getattr` модуля падает `AttributeError`.

Точка входа — из ответа Оператора (ANSWER-1.md, п. 1):
`_tests_writing_fail_to_pass_gate(conn, task_id, acc_tdir, run_cwd,
covered, profiles) -> GateRefusal | None`; профили — публичный
`project_profile.component_profiles(<проект>)`. Имя закрытое (с
подчёркиванием), поэтому файл разовый: долгоживущему файлу `tests/` такой
импорт запрещён, а запись из двух компонентов переходом недостижима
(`decide` её не проходит; SPEC, требование 10).

Стенд — песочница `FailToPassSandbox` долгоживущего файла задачи
(`tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py`): настоящий git,
учебный проект со своим `origin`, задача с опорой SPEC (переход гейта
SPEC), раннеры `pult-vitest` и pytest — шпион `subprocess.Popen`, пишущий
отчёт по тестам переданных файлов. Каталог планки — черновик каталога
документов задачи, рабочая копия — рабочая копия кодовой ветки.

Имена компонентов, файлов, номера критериев, порядок компонентов в записи —
из `random`; зерно печатается и входит в текст провала.

Провалидировано временным стабом гейта (удалён, не закоммичен): отказ
построения правила, пустой список компонента файла и прогон компонентов
с находками по спискам своих компонентов — все методы зелёные.
"""
import re
import unittest
from types import SimpleNamespace

from orchestrator import project_profile
from orchestrator.advance_gates import tests_writing as gates
from tests import test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass as ftp

GATE_NAME = "_tests_writing_fail_to_pass_gate"


class DirectGateSandbox(ftp.FailToPassSandbox):
    """Песочница с записью проекта из двух компонентов: `pult-vitest` и
    `junit-xml` на pytest, порядок в записи — от зерна."""

    def gate(self):
        fn = getattr(gates, GATE_NAME, None)
        self.assertIsNotNone(fn, self.note(
            f"в orchestrator/advance_gates/tests_writing.py нет {GATE_NAME}"))
        return fn

    def call_gate(self, t, numbers):
        """Прямой вызов гейта: каталог планки — черновик задачи, рабочая
        копия — кодовой ветки, покрытые — `AC-<n>` номеров `numbers`,
        профили — `component_profiles` проекта."""
        profiles = list(project_profile.component_profiles(t.target))
        self.runs.clear()
        return self.gate()(self.conn, t.id, t.plank, t.wt,
                           {f"AC-{n}" for n in numbers}, profiles)

    def component_lines(self, comp: str, fields: dict) -> str:
        lines = [f"      {comp}:\n"]
        for key, value in fields.items():
            lines.append(f"        {key}: {value}\n")
        return "".join(lines)

    def two_component_project(self, vitest_errors=("AssertionError",),
                              junit_errors=("AssertionError",),
                              vitest_tests: bool = True):
        name = f"w{self.word()}"
        vcomp, jcomp = f"v{self.word()}", f"j{self.word()}"
        vlayout = f"frontend/src/.pv{self.word(5)}/<id>"
        jlayout = f".pj{self.word(5)}/<id>"
        vfields = {"command": ftp.flow(project_profile.VITEST_BASE_ARGV),
                   "report": "pult-vitest",
                   "report_args": ftp.flow(ftp.VITEST_REPORT_ARGS),
                   "select": ftp.flow([f"--sel{self.word()}", "{tests}"]),
                   "install": ftp.flow([str(self.installer)]),
                   "plank_layout": vlayout,
                   "paths": ftp.flow(["frontend/"]),
                   "long_lived": ftp.LONG_TEMPLATE,
                   "weakening_scope": ftp.flow(["frontend/src/**"]),
                   "mutation_claim_scope": ftp.flow(["frontend/src/**"])}
        if vitest_tests:
            vfields["tests"] = ftp.flow(["frontend/src/**/*.test.jsx"])
        if vitest_errors:
            vfields["failure_errors"] = ftp.flow(vitest_errors)
        jfields = {"command": ftp.flow([str(self.pytest_cmd)]),
                   "report": "junit-xml",
                   "long_lived_dir": "tests",
                   "long_lived_name": "test_<id>_<name>.py",
                   "plank_layout": jlayout,
                   "paths": ftp.flow(["tests/"]),
                   "weakening_scope": ftp.flow(["tests/**"]),
                   "mutation_claim_scope": ftp.flow(["tests/**"])}
        if junit_errors:
            jfields["failure_errors"] = ftp.flow(junit_errors)
        vtext = (self.component_lines(vcomp, vfields)
                 + "        tools:\n"
                 + f'          vitest: "{self.vitest_version}"\n')
        jtext = self.component_lines(jcomp, jfields)
        vitest_first = self.rng.random() < 0.5
        body = vtext + jtext if vitest_first else jtext + vtext
        self.append_entry(ftp.ENTRY_HEAD.format(name=name) + "    components:\n"
                          + body)
        clone = ftp.make_project_repo(name)
        self.commit_project(clone, {
            "package.json": '{"name": "web"}\n',
            "vitest.config.js": "export default {}\n",
            "package-lock.json": '{"lockfileVersion": 3}\n',
            "frontend/src/app.jsx": "export const app = 1;\n",
            "tests/test_base.py": "def test_base():\n    pass\n",
            "app.py": "APP = 1\n"})
        self.clones[name] = clone
        # Проект — для помощников песочницы: компонент и выкладка `pult-vitest`.
        return SimpleNamespace(name=name, comp=vcomp, jcomp=jcomp,
                               layout=vlayout, jlayout=jlayout,
                               kind="two", code="app.py",
                               order="vitest первым" if vitest_first
                               else "junit первым")

    def commit_long_lived(self, t, rel: str, text: str) -> None:
        self.write_code(t, rel, text)
        self.git("-C", str(t.wt), "add", "--", rel)
        self.git("-C", str(t.wt), "commit", "-q", "-m", "долгоживущий файл")

    def why(self, refusal, project) -> str:
        runs = "\n".join(f"{r['kind']}: {r['argv']}" for r in self.runs)
        return self.note(f"порядок: {project.order}; исход: {refusal!r}\n"
                         f"запуски:\n{runs}")


# ---------------------------------------------------------------- AC-9

class Ac9TwoComponentsTest(DirectGateSandbox):

    def test_ac9_empty_list_named_by_component_of_file(self):
        """Пустой `failure_errors` на проекте из двух компонентов — отказ называет компонент, которому принадлежит файл, до прогона.

        Сценарий (подслучай — свежий проект и задача, порядок компонентов
        в записи от зерна): (а) пустой список у `pult-vitest`, планка — файл
        `.test.jsx` с тестом критерия; (б) пустой список у `junit-xml`,
        планка — `test_*.py`; (в) пустой список у `pult-vitest`, планка —
        только `test_*.py`, а тест второго критерия — в долгоживущем файле
        задачи по шаблону `long_lived` компонента `pult-vitest` (закоммичен в
        кодовую ветку). Прямой вызов гейта отдаёт отказ действием «переход
        отклонён: честный FAIL_TO_PASS — список «провал проверки» не
        задан» с деталью «список «провал проверки» не задан у компонента
        <имя компонента с пустым списком>», имени другого компонента в
        детали нет; раннеры не запускались.

        Ловит мутацию: компонент файла планки берётся первым компонентом
        записи, а не `PlankRule.component_of` — при обратном порядке в (а)
        или (б) отказа нет либо назван чужой компонент; долгоживущий файл
        отнесён к компоненту планки, а не к компоненту шаблона `long_lived`
        — в (в) отказа пустого списка нет, раннер запущен.
        """
        cases = (("пусто у pult-vitest, файл планки .test.jsx", "vitest", False),
                 ("пусто у junit-xml, файл планки test_*.py", "junit", False),
                 ("пусто у pult-vitest, долгоживущий файл", "vitest", True))
        for label, empty, long_lived in cases:
            with self.subTest(case=label, seed=self.seed):
                project = self.two_component_project(
                    vitest_errors=() if empty == "vitest" else ("AssertionError",),
                    junit_errors=() if empty == "junit" else ("AssertionError",))
                a, b = self.numbers(2)
                numbers = (a, b) if long_lived else (a,)
                t = self.new_task(project, numbers)
                if empty == "vitest" and not long_lived:
                    self.write_plank(t, {f"e{self.word()}.test.jsx": self.jsx((a,))})
                else:
                    self.write_plank(t, {f"test_{self.word()}.py":
                                         self.py_plank((a,))})
                if long_lived:
                    self.commit_long_lived(t, self.long_rel(t),
                                           self.long_jsx((b,)))
                refusal = self.call_gate(t, numbers)
                named, other = ((project.comp, project.jcomp) if empty == "vitest"
                                else (project.jcomp, project.comp))
                self.assertIsNotNone(refusal, self.why(refusal, project))
                self.assertEqual(refusal.action, ftp.NO_FAILURE_ERRORS_ACTION,
                                 self.why(refusal, project))
                self.assertIn(ftp.NO_LIST_TEXT + named, refusal.detail,
                              self.why(refusal, project))
                self.assertNotIn(other, refusal.detail, self.why(refusal, project))
                self.assertEqual(self.runs, [], self.why(refusal, project))

    def test_ac9_failure_list_of_file_component_in_findings(self):
        """Провал проверки на проекте из двух компонентов сверяется со списком компонента файла: планки и долгоживущего.

        Сценарий: `failure_errors` у `pult-vitest` — `[AssertionError]`, у
        `junit-xml` — `[TypeError]`; порядок компонентов от зерна. Планка —
        файл `.test.jsx` с тестами критериев A (на базе `TypeError`) и B
        (`AssertionError`) и файл `test_*.py` с тестом критерия C (JUnit
        `failure` с видом «TypeError: …»); долгоживущий файл задачи по
        шаблону `long_lived` `pult-vitest` — тест критерия D
        (`AssertionError`). Прямой вызов гейта — отказ «переход отклонён:
        честный FAIL_TO_PASS»: в детали метка теста A и имя «TypeError»;
        меток тестов B, C, D и находок «теста нет в отчёте» по B, C, D нет.

        Ловит мутацию: список берётся у первого компонента записи для всех
        файлов — при `pult-vitest` первым тест C («TypeError» вне
        `[AssertionError]`) объявлен находкой, при `junit-xml` первым тест A
        принят, а B объявлен находкой; долгоживущий файл сверяется со
        списком `junit-xml` — тест D объявлен находкой «AssertionError».
        """
        project = self.two_component_project(vitest_errors=("AssertionError",),
                                             junit_errors=("TypeError",))
        a, b, c, d = self.numbers(4)
        t = self.new_task(project, (a, b, c, d))
        jsx_text = self.jsx((a, b))
        py_text = self.py_plank((c,))
        long_text = self.long_jsx((d,))
        self.write_plank(t, {f"f{self.word()}.test.jsx": jsx_text,
                             f"test_{self.word()}.py": py_text})
        self.commit_long_lived(t, self.long_rel(t), long_text)
        self.vitest_case[a] = {"error_name": "TypeError"}
        self.junit_case[c] = ("failure", f"TypeError: {self.word()}")
        refusal = self.call_gate(t, (a, b, c, d))
        self.assertIsNotNone(refusal, self.why(refusal, project))
        self.assertEqual(refusal.action, ftp.F2P_ACTION, self.why(refusal, project))
        labels = self.labels_of(jsx_text)
        long_label = self.labels_of(long_text)[d]
        py_name = re.search(r"def (test_ac\d+_\w+)\(", py_text).group(1)
        self.assertIn(labels[a], refusal.detail, self.why(refusal, project))
        self.assertIn("TypeError", refusal.detail, self.why(refusal, project))
        for absent in (labels[b], py_name, long_label):
            self.assertNotIn(absent, refusal.detail, self.why(refusal, project))
        for n in (b, c, d):
            self.assertNotIn(f"AC-{n}: {ftp.NO_RECORD}", refusal.detail,
                             self.why(refusal, project))


# --------------------------------------------------------------- AC-12

class Ac12RuleNotBuiltTest(DirectGateSandbox):

    def test_ac12_rule_not_built_refused_with_build_refusal_text(self):
        """Правило планки не построено по записи — гейт отказывает текстом отказа построения, без прогона.

        Сценарий: запись из двух компонентов, у компонента `pult-vitest` нет
        поля `tests` — `project_profile.plank_rule(<проект>)` отдаёт правило
        с непустым `refusal`; планка — файл `.test.jsx` с тестом критерия.
        Прямой вызов гейта отдаёт `GateRefusal`, чья деталь содержит текст
        `refusal` правила; раннеры не запускались.

        Ловит мутацию: защитная ветка снята — правило-умолчание с отказом
        принимается как обычное, гейт гонит планку (запуск раннера) или
        проходит (`None`); отказ выдан без текста причины построения.
        """
        project = self.two_component_project(vitest_tests=False)
        reason = project_profile.plank_rule(project.name).refusal
        self.assertTrue(reason, self.note(
            "фикстура: правило планки построено без отказа"))
        n = self.numbers(1)[0]
        t = self.new_task(project, (n,))
        self.write_plank(t, {f"r{self.word()}.test.jsx": self.jsx((n,))})
        refusal = self.call_gate(t, (n,))
        self.assertIsNotNone(refusal, self.why(refusal, project))
        self.assertIn(reason, refusal.detail, self.why(refusal, project))
        self.assertEqual(self.runs, [], self.why(refusal, project))


if __name__ == "__main__":
    unittest.main()
