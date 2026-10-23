"""Бриф, задание test_author, сводки Vitest и итог `plank-run` у задачи на компонент записи из нескольких компонентов — как у записи из одного этого компонента; при отказе `for_task` — прежний вывод.

Группа: долгоживущий
Красен до реализации: бриф, задание, насос сводок и `plank-run` берут профиль `decide(target)`, а у записи из нескольких компонентов он отказывает — у задачи на `frontend` нет документов `knowledge` компонента, задание прежнее (без метки `AC-<n>: `), записей «прогон vitest» нет, `plank-run` пишет «итог pytest» вместо «итог vitest»; вывод не совпадает с выводом для записи из одного `frontend`.

Свойство связки «строка задачи с зонами — `for_task` — потребитель
профиля»: четыре потребителя проверяются на их публичных входах в
песочницах соседних долгоживущих тестов, к которым дописаны записи
`targets.yaml` этой задачи: учебная запись из двух компонентов (`backend` и
`frontend`) и запись из одного `frontend` с теми же полями.

- бриф — сборщики ролей `brief.*` и пакет ревьювера
  (`tests.test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.KnowledgeSandbox`,
  настоящий git клона и ссылки документов);
- задание test_author — `role_prompt.mission_brief_package`
  (`tests.test_01m5enwtdd8np9smpfx3jn08j9_author_mission.MissionSandbox`);
- сводки Vitest шага — `runner.run_agent_once` с подставным агентом
  (`tests.test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary.StepSandbox`);
- итог `plank-run` — `plank_run.cmd_plank_run` с подменённым прогоном
  (`tests.test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.PlankRunSandbox`).

Вывод двух записей сравнивается после замены имён проекта, ветки и id
задачи (они разные по построению). Имена и числа — из `random`; зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`for_task` по зонам задачи и потребители на `for_task` — все методы файла
зелёные.
"""
import io
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from orchestrator import (catalog, config, plank_run, project_profile,
                          role_prompt, runner, store, workspace)
from tests.sandbox import FakeProc, capture, make_project_repo
from tests.test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief import (
    ALL_ROLES, BUILDERS, KnowledgeSandbox)
from tests.test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief import (
    PROFILE_FIELDS as BRIEF_FIELDS)
from tests.test_01m5enwtdd8np9smpfx3jn08j9_author_mission import MissionSandbox
from tests.test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary import (
    PlankRunSandbox)
from tests.test_01m5enwtdd8np9smpfx3jn08j9_vitest_summary import (
    RESULT_LINE, ROLE, VITEST_ACTION, StepSandbox, tool_result_line)

HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    components:
"""
BACKEND = {
    "command": "[python3, -m, pytest]",
    "report": "junit-xml",
    "long_lived_dir": "backend/tests",
    "long_lived_name": "test_<id>_<name>.py",
    "weakening_scope": "[backend/tests/**]",
    "mutation_claim_scope": "[backend/tests/test_*.py]",
    "tests": "[backend/tests/**/test_*.py]",
    "paths": "[^backend/]",
}
FRONTEND = {
    "command": "[" + ", ".join(project_profile.VITEST_BASE_ARGV) + "]",
    "report": "pult-vitest",
    "tests": "[frontend/src/**/*.test.jsx]",
    "plank_layout": "frontend/src/.pv/<id>",
    "long_lived": "frontend/src/<dir>/<name>.<id>.test.jsx",
    "weakening_scope": "[frontend/src/**]",
    "mutation_claim_scope": "[frontend/claims/**]",
    "paths": "[^frontend/]",
}
DEPENDS = ("        depends_on:\n          backend:\n            via: files\n"
           "            paths: [^backend/seed/]\n")
ZONES = {"frontend": "frontend/src/App.jsx", "both":
         "backend/app.py, frontend/src/App.jsx", "outside": "docs/notes.md",
         "none": None}
REFUSALS = ("both", "outside", "none")
REFUSAL_TEXTS = {
    "both": "задача затрагивает несколько компонентов (",
    "outside": "зоны задачи не задевают ни одного компонента записи",
    "none": ("зоны задачи не заданы — компонент задачи на записи из "
             "нескольких компонентов не выбран")}
BRIEF_ROLES = tuple(BUILDERS)


def block(name: str, fields: dict, extra: str = "") -> str:
    return (f"      {name}:\n"
            + "".join(f"        {k}: {v}\n" for k, v in fields.items()) + extra)


def multi_entry(name: str, frontend: dict | None = None) -> str:
    return (HEAD.format(name=name) + block("backend", BACKEND)
            + block("frontend", frontend or FRONTEND, DEPENDS))


def single_entry(name: str, frontend: dict | None = None) -> str:
    return HEAD.format(name=name) + block("frontend", frontend or FRONTEND)


def new_id(rng) -> str:
    return "01" + "".join(rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                          for _ in range(24))


def normalized(text: str, *pairs) -> str:
    for old, new in pairs:
        if old:
            text = text.replace(old, new)
    return text


# ------------------------------------------------------------------ бриф

class KnowledgeOutputSandbox(KnowledgeSandbox):
    """Записи `training` (два компонента, `knowledge` у `frontend`) и
    `single` (один `frontend`) песочницы брифа."""

    def entry(self, record: str, knowledge) -> str:
        kn = "[" + ", ".join(knowledge) + "]" if knowledge is not None else ""
        back = dict(BRIEF_FIELDS, paths="[^backend/]")
        front = dict(BRIEF_FIELDS, paths="[^frontend/]")
        if kn:
            front["knowledge"] = kn
        head = HEAD.replace("base: main", f"base: {self.base}").format(
            name=self.project)
        if record == "training":
            return head + block("backend", back) + block("frontend", front, DEPENDS)
        if record == "single":
            return head + block("frontend", front)
        return super().entry(record, knowledge)

    def knowledge_task(self, record: str, variant: str = "frontend") -> None:
        self.element = "frontend-guide.md"
        self.prepare({"CLAUDE.md": "# Конвенции\n\nПравило.\n",
                      self.element: "# Руководство frontend\n\nТекст.\n"},
                     [self.element], record=record)
        zones = ZONES[variant]
        if zones is not None:
            store.update_task(self.conn, self.task, zones=zones)

    def knowledge_lines(self, text: str) -> list:
        pairs = ((self.project, "<проект>"), (self.base, "<база>"),
                 (self.task, "<задача>"))
        return [normalized(line, *pairs) for line in text.splitlines()
                if "knowledge" in line or "Руководство frontend" in line]


class BriefTest(KnowledgeOutputSandbox):

    def test_ac22_brief_knowledge_of_frontend(self):
        """Бриф пяти ролей задачи на `frontend` несёт документ `knowledge` компонента `frontend`.

        Ловит мутацию: `_knowledge_of` на `decide(target)` — у записи из
        нескольких компонентов документов `knowledge` нет.
        """
        self.knowledge_task("training")
        for role in ALL_ROLES:
            with self.subTest(роль=role):
                text = self.text_of(role)
                self.assertIn("knowledge компонента frontend", text,
                              self.note(f"{role}: {text[-2000:]}"))
                self.assertIn("Руководство frontend", text, self.note(role))

    def test_ac24_brief_refusal_keeps_old_output(self):
        """Задача с отказом `for_task` (три варианта зон): брифы четырёх ролей собираются без документов `knowledge` — прежний вывод.

        Пакет ревьювера при отказе `for_task` не собирается — исход своей
        строки таблицы, его держат тесты пакета.

        Ловит мутацию: при отказе `for_task` бриф берёт первый компонент
        записи или роняет сборку — документы `knowledge` либо отказ.
        """
        for variant in REFUSALS:
            with self.subTest(variant=variant):
                self.knowledge_task("training", variant)
                for role in BRIEF_ROLES:
                    text = self.text_of(role)
                    self.assertNotIn("knowledge компонента", text,
                                     self.note(f"{variant}/{role}"))

    def test_ac20_brief_knowledge_as_single_component(self):
        """Строки документов `knowledge` в брифе задачи на `frontend` записи из нескольких компонентов побайтно равны строкам брифа записи из одного `frontend`.

        Ловит мутацию: подпись куска `knowledge` у записи из нескольких
        компонентов иная (имя компонента задачи не подставлено, лишняя
        пометка о выборе компонента).
        """
        self.knowledge_task("training")
        multi = {role: self.knowledge_lines(self.text_of(role)) for role in ALL_ROLES}
        self.knowledge_task("single")
        for role in ALL_ROLES:
            with self.subTest(роль=role):
                single = self.knowledge_lines(self.text_of(role))
                self.assertTrue(single, self.note(role))
                self.assertEqual(multi[role], single, self.note(role))


# ------------------------------------------------------------------ задание

class MissionOutputSandbox(MissionSandbox):

    def setUp(self):
        super().setUp()
        self.multi, self.single = f"m{self.word()}", f"o{self.word()}"
        self.project(multi_entry(self.multi), self.multi)
        self.project(single_entry(self.single), self.single)

    def zoned_mission(self, target: str, variant: str) -> tuple:
        task_id = new_id(self.rng)
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, "Учебная задача", "tests_writing",
                          branch, target, config.DEFAULT_BUDGET_USD)
        if ZONES[variant] is not None:
            store.update_task(self.conn, task_id, zones=ZONES[variant])
        t = store.get_task(self.conn, task_id)
        mission, _brief, _package = role_prompt.mission_brief_package(
            self.conn, task_id, t, "test_author", "/tmp/cwd-mission")
        return mission, task_id, branch


class MissionTest(MissionOutputSandbox):

    def test_ac22_test_author_mission_by_frontend_rule(self):
        """Задание test_author задачи на `frontend` — по правилу планки `frontend`: маска `*.test.jsx`, метка `AC-<n>: `.

        Ловит мутацию: `_labelled_profile` на `decide(target)` — прежнее
        задание «unittest … test_*.py».
        """
        mission, _tid, _branch = self.zoned_mission(self.multi, "frontend")
        self.assertIn("`*.test.jsx`", mission, self.note(mission))
        self.assertIn("AC-<n>: ", mission, self.note(mission))

    def test_ac24_mission_refusal_keeps_old_text(self):
        """Задача с отказом `for_task`: задание test_author прежнее, без маски `*.test.jsx`.

        Ловит мутацию: при отказе берётся правило первого компонента
        записи с меткой — задание по `frontend`.
        """
        for variant in REFUSALS:
            with self.subTest(variant=variant):
                mission, _tid, _branch = self.zoned_mission(self.multi, variant)
                self.assertNotIn("`*.test.jsx`", mission, self.note(mission))
                self.assertIn("test_ac<n>_", mission, self.note(mission))

    def test_ac20_mission_as_single_component(self):
        """Задание test_author задачи на `frontend` записи из нескольких компонентов побайтно равно заданию для записи из одного `frontend`.

        Ловит мутацию: задание у записи из нескольких компонентов называет
        маски всех компонентов записи (правило планки целиком), а не
        компонента задачи.
        """
        multi, mtid, mbranch = self.zoned_mission(self.multi, "frontend")
        single, stid, sbranch = self.zoned_mission(self.single, "frontend")
        pairs_m = ((mbranch, "<ветка>"), (mtid, "<id>"), (mtid.lower(), "<id_low>"),
                   (self.multi, "<проект>"))
        pairs_s = ((sbranch, "<ветка>"), (stid, "<id>"), (stid.lower(), "<id_low>"),
                   (self.single, "<проект>"))
        self.assertEqual(normalized(multi, *pairs_m), normalized(single, *pairs_s),
                         self.note("задания расходятся"))


# ------------------------------------------------------------------ сводки Vitest

class VitestStepSandbox(StepSandbox):

    def setUp(self):
        super().setUp()
        self.multi, self.single = f"m{self.word()}", f"o{self.word()}"
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + multi_entry(self.multi)
                                  + single_entry(self.single), encoding="utf-8")
        for name in (self.multi, self.single):
            make_project_repo(name)
        capture(catalog.cmd_init)

    def zoned_step(self, target: str, variant: str, outputs) -> str:
        task_id = new_id(self.rng)
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, "Учебная задача", "tests_writing",
                          branch, target, config.DEFAULT_BUDGET_USD)
        if ZONES[variant] is not None:
            store.update_task(self.conn, task_id, zones=ZONES[variant])
        _wt, error = workspace.ensure(task_id, branch, target)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        lines = [tool_result_line(text, n) for n, text in enumerate(outputs, 1)]
        with mock.patch.object(runner, "spawn_agent",
                               return_value=FakeProc(lines + [RESULT_LINE], 0)), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            runner.run_agent_once(self.conn, task_id, ROLE, "промпт шага", 1)
        return task_id


class VitestSummaryTest(VitestStepSandbox):

    def test_ac22_vitest_summaries_of_frontend_task(self):
        """Шаг задачи на `frontend` пишет записи «прогон vitest» по сводкам Vitest вывода агента.

        Ловит мутацию: `_reports_vitest` на `decide(target)` — насос без
        получателя сводок, записей нет.
        """
        _name, text, detail = self.fixtures()[0]
        task_id = self.zoned_step(self.multi, "frontend", [text])
        self.assertEqual(self.details(task_id, VITEST_ACTION), [detail],
                         self.note(text))

    def test_ac24_vitest_refusal_keeps_old_output(self):
        """Шаг задачи с отказом `for_task`: записей «прогон vitest» нет — прежний вывод.

        Ловит мутацию: при отказе берётся первый компонент записи с
        `pult-vitest` — записи сводок появляются.
        """
        _name, text, _detail = self.fixtures()[0]
        for variant in REFUSALS:
            with self.subTest(variant=variant):
                task_id = self.zoned_step(self.multi, variant, [text])
                self.assertEqual(self.details(task_id, VITEST_ACTION), [],
                                 self.note(variant))

    def test_ac20_vitest_summaries_as_single_component(self):
        """Записи «прогон vitest» шага задачи на `frontend` записи из нескольких компонентов равны записям шага записи из одного `frontend` на том же выводе.

        Ловит мутацию: сводки у записи из нескольких компонентов
        пишутся с иной деталью или не все.
        """
        outputs = [f[1] for f in self.fixtures()]
        multi = self.zoned_step(self.multi, "frontend", outputs)
        single = self.zoned_step(self.single, "frontend", outputs)
        self.assertEqual(self.details(multi, VITEST_ACTION),
                         self.details(single, VITEST_ACTION), self.note("сводки"))
        self.assertTrue(self.details(single, VITEST_ACTION), self.note("пусто"))


# ------------------------------------------------------------------ plank-run

class PlankRunOutputSandbox(PlankRunSandbox):

    def setUp(self):
        super().setUp()
        self.multi, self.single = f"m{self.word()}", f"o{self.word()}"
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + multi_entry(self.multi)
                                  + single_entry(self.single), encoding="utf-8")
        for name in (self.multi, self.single):
            make_project_repo(name, origin=False)

    def zoned_task(self, target: str, variant: str) -> str:
        task_id = new_id(self.rng)
        store.insert_task(self.conn, task_id, "Учебная задача", "tests_writing",
                          f"task/{task_id.lower()}-{self.word()}", target,
                          config.DEFAULT_BUDGET_USD)
        if ZONES[variant] is not None:
            store.update_task(self.conn, task_id, zones=ZONES[variant])
        workspace.path(task_id, target).mkdir(parents=True, exist_ok=True)
        plank = config.PROJECTS / target / config.TASKS.name / task_id / "acceptance_tests"
        plank.mkdir(parents=True, exist_ok=True)
        (plank / "a.test.jsx").write_text("// тест\n", encoding="utf-8")
        return task_id


class PlankRunTest(PlankRunOutputSandbox):

    def outcome(self, task_id: str, output: str) -> str:
        """Вывод команды, `SystemExit` и исключение одним текстом."""
        self.answer = (0, output)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            try:
                plank_run.cmd_plank_run(task_id)
            except SystemExit as exc:
                out.write(f"\nSystemExit: {exc.code}")
            except Exception as exc:  # noqa: BLE001 — исход любой формы
                out.write(f"\n{type(exc).__name__}: {exc}")
        return out.getvalue()

    def test_ac22_plank_run_vitest_line_for_frontend(self):
        """`plank-run` задачи на `frontend` пишет «итог vitest: <деталь>; код выхода vitest: <код>».

        Ловит мутацию: строка итога по `decide(target)` — «итог pytest: …».
        """
        task_id = self.zoned_task(self.multi, "frontend")
        text, detail = self.vitest_block()
        out, _exit = self.plank_run(task_id, 0, text)
        self.assertIn(f"итог vitest: {detail}; код выхода vitest: 0", out,
                      self.note(out))

    def test_ac24_plank_run_refusal_keeps_old_line(self):
        """`plank-run` задачи с отказом `for_task`: итог не по профилю компонента — нет «итог vitest»; строка прежняя «итог pytest: …» либо отказ с текстом `for_task`.

        Ловит мутацию: при отказе берётся первый компонент записи с
        `pult-vitest` — «итог vitest».
        """
        for variant in REFUSALS:
            with self.subTest(variant=variant):
                task_id = self.zoned_task(self.multi, variant)
                text, summary = self.pytest_line()
                out = self.outcome(task_id, text)
                self.assertNotIn("итог vitest", out, self.note(out))
                self.assertTrue(
                    f"итог pytest: {summary}; код выхода pytest: 0" in out
                    or REFUSAL_TEXTS[variant] in out, self.note(out))

    def test_ac20_plank_run_line_as_single_component(self):
        """Итоговая строка `plank-run` задачи на `frontend` записи из нескольких компонентов побайтно равна строке для записи из одного `frontend`.

        Ловит мутацию: строка у записи из нескольких компонентов прежняя
        «итог pytest» либо иная деталь.
        """
        text, _detail = self.vitest_block()
        multi = self.zoned_task(self.multi, "frontend")
        single = self.zoned_task(self.single, "frontend")
        out_m, _ = self.plank_run(multi, 1, text)
        out_s, _ = self.plank_run(single, 1, text)
        line_m = [line for line in out_m.splitlines() if "итог" in line]
        line_s = [line for line in out_s.splitlines() if "итог" in line]
        self.assertTrue(line_s, self.note(out_s))
        self.assertEqual([line.replace(multi, "<id>") for line in line_m],
                         [line.replace(single, "<id>") for line in line_s],
                         self.note(f"{out_m}\n---\n{out_s}"))
