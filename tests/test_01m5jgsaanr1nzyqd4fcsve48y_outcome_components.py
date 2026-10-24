"""Гейт исходов у записи из нескольких компонентов: компоненты по диффу с потребителями, запись на компонент, граница по компоненту, строки пакета ревьювера; выход из `tests_writing` и `in_dev` задачи на один компонент; планка чужого компонента на выходе из `tests_writing` — отказ FAIL_TO_PASS в границе, прежнее поведение вне её.

Группа: долгоживущий
Красен до реализации: у записи `components:` из двух компонентов `decide` отказывает — выход из `tests_writing` задачи на компонент отклоняется отказом профиля, гейт исходов не создаётся (`_bounds` — `None`), прогонов компонентов нет, записей пройденного гейта и записи пропуска нет, пакет ревьювера не собирается, мандат на тест компонента-потребителя отказывает; нет ни отказа «файл планки <имя> — компонента <X>, задача — компонента <Y>», ни перехода в `in_dev` при чужом файле вне границы.

Стенд — песочница гейта исходов на мерже
(`tests.test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.MergeOutcomeSandbox`
поверх песочницы G3а-1а): настоящий git, раннеры pytest и Vitest — шпион
`subprocess.Popen` без Node и сети, сторона прогона — по метке `app.py`
выписки. Учебный проект — запись из двух компонентов: `backend` —
`junit-xml` на поддельном `pytest`, `frontend` — `pult-vitest`,
`depends_on` вида `files` на `backend/seed/`; варианты — без поля `report`
у одного или обоих компонентов (вне границы гейта исходов). Задача заводится
с зонами своего компонента и проходит настоящий выход из `tests_writing`
(планка критерия по правилу планки компонента задачи), шаг developer —
коммит правки и `fsm.cmd_advance`; зоны строки задачи — изменённые файлы
(как у песочницы G3а-1а).

Компонент записи гейта различается числом тестов базы («тестов базы N»):
у `backend` и `frontend` оно разное. Имена файлов, тестов и их число — из
`random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`for_task` по зонам задачи, гейт исходов по `select_components` диффа с
потребителями (прогон и запись на компонент в границе, строки «вне
границы», запись пропуска при всех вне границы), `review_lines` по записям
всех компонентов головы, мандат по компоненту находки — все методы файла
зелёные.
"""
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

from orchestrator import (answer, checkpoint, config, project_profile, store,
                          workspace)
from orchestrator.advance_gates import mandate, outcome_integrity
from tests.sandbox import make_project_repo
from tests.outcome_gate_sandbox import (
    ENTRY_HEAD, LONG_TEMPLATE, MATRIX_HEADERS, PLANK_DIR, TASKS_DIR,
    VITEST_REPORT_ARGS, RunnerProc, flow, js_source, py_source, spec_text,
    ulid)
from tests.merge_outcome_sandbox import (
    MergeOutcomeSandbox)

PASSED_ACTION = "гейт неослабления по исходам пройден"
OUTCOME_ACTION = "переход отклонён: гейт неослабления по исходам"
BROKEN_ACTION = OUTCOME_ACTION + " — сломан правкой"
PREPARE_ACTION = OUTCOME_ACTION + " — подготовка"
SKIP_RECORD = (f"{project_profile.SKIP_ACTION}: гейт неослабления по "
               f"исходам")
OUT_OF_BOUNDS = "компонент {name}: вне границы гейта исходов"
NOT_RUN = "гейт исходов для головы {head} не исполнялся"
APPROVED_DETAIL = "гейт SPEC пройден — приёмочные тесты до кода"
COUNTS = "тестов базы {n};"


class ContextRunnerProc(RunnerProc):
    """Процесс раннера сценария и как менеджер контекста: прогон pytest без
    отчёта (компонент вне границы) зовёт `with subprocess.Popen(...)`."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.wait()
        return False


class ComponentsOutcomeSandbox(MergeOutcomeSandbox):
    """Учебный проект из двух компонентов и задачи на один из них."""

    def runner_run(self, kind, parts, cwd, args, kwargs):
        if kind == "pytest" and "--collect-only" in parts:
            # Сухой сбор планки компонента без отчёта: поддельный pytest
            # собирает её без ошибок.
            return self.answer(0, "1 test collected\n", args, kwargs)
        proc = super().runner_run(kind, parts, cwd, args, kwargs)
        proc.__class__ = ContextRunnerProc
        return proc

    def training(self, backend_report: bool = True,
                 frontend_report: bool = True) -> SimpleNamespace:
        name = f"t{self.word()}"
        back = {"command": flow([str(self.pytest_cmd)]),
                "long_lived_dir": "backend/tests",
                "long_lived_name": "test_<id>_<name>.py",
                "weakening_scope": flow(["backend/tests/**"]),
                "mutation_claim_scope": flow(["backend/tests/test_*.py"]),
                "tests": flow(["backend/tests/**/test_*.py"]),
                "paths": flow(["^backend/"])}
        if backend_report:
            back.update({"report": "junit-xml",
                         "failure_errors": flow(["AssertionError"]),
                         "plank_layout": f"backend/tests/.pb{self.word(5)}/<id>"})
        front = {"command": flow(project_profile.VITEST_BASE_ARGV),
                 "install": flow([str(self.installer)]),
                 "tests": flow(["frontend/src/**/*.test.jsx"]),
                 "long_lived": LONG_TEMPLATE,
                 "weakening_scope": flow(["frontend/src/**"]),
                 "mutation_claim_scope": flow(["frontend/claims/**"]),
                 "select": flow([f"--sel{self.word()}", "{tests}"]),
                 "paths": flow(["^frontend/"])}
        if frontend_report:
            front.update({"report": "pult-vitest",
                          "report_args": flow(VITEST_REPORT_ARGS),
                          "failure_errors": flow(["AssertionError"]),
                          "plank_layout": f"frontend/src/.pv{self.word(5)}/<id>"})
        lines = [ENTRY_HEAD.format(name=name), "    components:\n",
                 "      backend:\n"]
        lines += [f"        {k}: {v}\n" for k, v in back.items()]
        lines.append("      frontend:\n")
        lines += [f"        {k}: {v}\n" for k, v in front.items()]
        lines += ["        tools:\n",
                  f'          vitest: "{self.vitest_version}"\n',
                  "        depends_on:\n", "          backend:\n",
                  "            via: files\n",
                  "            paths: [^backend/seed/]\n"]
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        n_back = self.rng.randint(2, 4)
        n_front = n_back + self.rng.randint(1, 3)
        back_rel = f"backend/tests/test_{self.word()}.py"
        front_rel = f"frontend/src/{self.word()}.test.jsx"
        back_names = [self.py_name() for _ in range(n_back)]
        front_names = [self.js_name() for _ in range(n_front)]
        self.commit_project(clone, {
            "app.py": "APP = 'base'\n",
            "package.json": '{"name": "web"}\n',
            "vitest.config.js": "export default {}\n",
            "package-lock.json": json.dumps({"lockfileVersion": 3}) + "\n",
            "backend/seed/data.py": "SEED = 1\n",
            "backend/service.py": "VALUE = 1\n",
            "frontend/src/App.jsx": "export const App = 1;\n",
            back_rel: py_source(back_names),
            front_rel: js_source(front_names)})
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp="", layout="", kind="multi",
                               clone=clone, back_rel=back_rel,
                               back_names=back_names, front_rel=front_rel,
                               front_names=front_names)

    no_marker = False

    def zone_of(self, comp: str) -> str:
        return {"backend": "backend/service.py",
                "frontend": "frontend/src/App.jsx"}[comp]

    def zones_of(self, comp: str) -> str:
        """Зоны задачи: каталог компонента (зона-каталог — по файлам базы
        под ним) и метка стороны `app.py` (вне компонентов — выбор
        компонента задачи не расширяет)."""
        return f"{comp}/, app.py"

    def writing_task(self, project, comp: str, planks: dict | None = None):
        """Задача на компонент `comp` до выхода из `tests_writing`
        включительно: (задача, записи журнала выхода, вывод). `planks` —
        файлы планки {имя: текст}; без них — планка критерия по правилу
        компонента задачи."""
        n = self.rng.randrange(1, 60)
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        store.insert_task(self.conn, tid, "Задача на компонент", "spec_gate",
                          branch, project.name, 25.0)
        store.update_task(self.conn, tid, zones=self.zones_of(comp))
        wt, error = workspace.ensure(tid, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                            target=project.name, wt=Path(wt), project=project,
                            comp=comp)
        t.docs = config.PROJECTS / project.name / TASKS_DIR / tid
        t.plank = t.docs / PLANK_DIR
        t.plank.mkdir(parents=True, exist_ok=True)
        t.spec = spec_text(tid, (n,))
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, tid, "analyst")
        store.set_state(self.conn, tid, "tests_writing", "operator",
                        expected_state="spec_gate", detail=APPROVED_DETAIL)
        t.docs.mkdir(parents=True, exist_ok=True)
        (t.docs / "SPEC.md").write_text(t.spec, encoding="utf-8")
        t.plank.mkdir(parents=True, exist_ok=True)
        if planks is None:
            kind = SimpleNamespace(kind="vitest" if comp == "frontend" else "junit")
            name, body = self.plank_text(kind, n)
            planks = {name: body}
        for name, body in planks.items():
            (t.plank / name).write_text(body.replace("<n>", str(n)),
                                        encoding="utf-8")
        self.plank_green = False
        store.journal(self.conn, tid, "test_author", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, tid, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, tid, "test_author")
        self.current = tid
        rows, output = self.run_advance(tid)
        return t, rows, output

    def component_task(self, project, comp: str):
        """Задача на `comp`, прошедшая настоящий выход из `tests_writing`."""
        t, rows, output = self.writing_task(project, comp)
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        self.plank_green = True
        return t

    def commit_code(self, t, changes: dict, message: str = "код разработчика"):
        """Коммит правки песочницы G3а-1а; зоны строки задачи остаются
        зонами её компонента и меткой стороны `app.py` (песочница пишет в
        них изменённые файлы). `no_marker` — коммит без метки стороны:
        дифф только из правки сценария."""
        if self.no_marker:
            for rel, text in changes.items():
                path = t.wt / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                self.git("-C", str(t.wt), "add", "--", rel)
            self.git("-C", str(t.wt), "commit", "-q", "-m", message)
        else:
            super().commit_code(t, changes, message)
        store.update_task(self.conn, t.id, zones=self.zones_of(t.comp))

    def records(self, rows: list, action: str = PASSED_ACTION) -> list:
        return self.details(rows, action)

    def counts_of(self, detail: str) -> str:
        return detail.splitlines()[0] if detail else ""

    def runners_any(self, kind: str) -> list:
        """Полные прогоны раннера `kind` гейта (любая сторона)."""
        return [r for r in self.runs if r["kind"] == kind and not r["plank"]
                and r["full"]]

    def runners(self, kind: str) -> list:
        return [r for r in self.runs if r["kind"] == kind and not r["plank"]
                and r["full"] and r["side"] in ("base", "head")]


# ------------------------------------------------------------------ AC-16 / AC-23

class Ac16DiffComponentsTest(ComponentsOutcomeSandbox):

    def test_ac23_seed_change_runs_both_components(self):
        """Задача на `backend` с правкой под `backend/seed/`: гейт исходов гоняет `backend` и потребителя `frontend`, профиль задачи — `backend`.

        Сценарий: правка `backend/seed/data.py`; выход из `in_dev` проходит
        в `verifying`. Полные прогоны базы и головы — у раннера pytest и у
        Vitest; записей пройденного гейта две, по числу тестов базы —
        `backend`, затем `frontend`; `for_task` задачи — профиль `backend`.

        Ловит мутацию: гейт берёт только компонент задачи (`for_task`) —
        Vitest не гоняется, запись одна; `select_components` без
        потребителей `depends_on` — то же.
        """
        project = self.training()
        t = self.component_task(project, "backend")
        rows, output = self.developer_advance(t, {"backend/seed/data.py": "SEED = 2\n"})
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        self.assertEqual(project_profile.for_task(self.conn, t.id).profile.component,
                         "backend", self.note("профиль задачи"))
        for kind in ("pytest", "vitest"):
            sides = {r["side"] for r in self.runners(kind)}
            self.assertEqual(sides, {"base", "head"},
                             self.explain(rows, output) + f"\nраннер {kind}")
        passed = self.records(rows)
        self.assertEqual(len(passed), 2, self.explain(rows, output))
        self.assertTrue(passed[0].startswith(COUNTS.format(n=len(project.back_names))),
                        self.note(passed[0]))
        self.assertTrue(passed[1].startswith(COUNTS.format(n=len(project.front_names))),
                        self.note(passed[1]))

    def test_ac16_component_change_runs_only_its_component(self):
        """Задача на `frontend` с правкой только под `frontend/`: гейт берёт компоненты диффа — один `frontend`, профиль его записи — `component_profiles`.

        Сценарий: правка только `frontend/src/App.jsx` (коммит без метки
        стороны `app.py`); выход в `verifying`. Полные прогоны — только
        Vitest, запись пройденного гейта одна с числом тестов базы
        `frontend`.

        Ловит мутацию: гейт гоняет все компоненты записи без выбора по
        диффу — прогоны pytest и вторая запись; профиль гейта —
        `backend` (первый компонент записи).
        """
        project = self.training()
        t = self.component_task(project, "frontend")
        self.no_marker = True
        rows, output = self.developer_advance(
            t, {"frontend/src/App.jsx": "export const App = 2;\n"})
        self.no_marker = False
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        self.assertEqual(self.runners_any("pytest"), [], self.explain(rows, output))
        self.assertTrue(self.runners_any("vitest"), self.explain(rows, output))
        passed = self.records(rows)
        self.assertEqual(len(passed), 1, self.explain(rows, output))
        self.assertTrue(passed[0].startswith(COUNTS.format(n=len(project.front_names))),
                        self.note(passed[0]))

    def test_ac16_diff_read_failure_refuses_preparation(self):
        """Сбой чтения диффа гейтом — отказ «… — подготовка», задача остаётся в `in_dev`, прогонов нет.

        Сценарий: git отказывает вызовам `diff` из кадров модуля гейта.

        Ловит мутацию: сбой чтения диффа даёт пустой набор путей — гейт
        гоняет «все компоненты» либо молча проходит.
        """
        project = self.training()
        t = self.component_task(project, "backend")
        self.git_fail = lambda args: "diff" in args
        rows, output = self.developer_advance(t, {"backend/seed/data.py": "SEED = 3\n"})
        self.git_fail = None
        self.assertTrue(self.records(rows, PREPARE_ACTION), self.explain(rows, output))
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        self.assertEqual(self.records(rows), [], self.explain(rows, output))


# ------------------------------------------------------------------ AC-17

class Ac17PerComponentTest(ComponentsOutcomeSandbox):

    def test_ac17_first_refusal_names_component(self):
        """Тест `frontend` сломан правкой `backend/seed/`: `backend` проходит со своей записью, отказ гейта называет «компонент frontend: …».

        Ловит мутацию: компоненты гоняются одним прогоном без префикса
        компонента в детали; порядок не по записи — `frontend` первым, у
        `backend` записи нет.
        """
        project = self.training()
        t = self.component_task(project, "backend")
        broken = self.rng.choice(project.front_names)
        self.cases[(project.front_rel, broken)] = {"base": ["passed"],
                                                   "head": ["failed"]}
        rows, output = self.developer_advance(t, {"backend/seed/data.py": "SEED = 4\n"})
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        refused = (self.records(rows, BROKEN_ACTION)
                   or self.records(rows, OUTCOME_ACTION))
        self.assertTrue(refused, self.explain(rows, output))
        self.assertTrue(refused[-1].startswith("компонент frontend: "),
                        self.note(refused[-1]))
        self.assertIn(broken, refused[-1], self.note(refused[-1]))
        passed = self.records(rows)
        self.assertEqual(len(passed), 1, self.explain(rows, output))
        self.assertTrue(passed[0].startswith(COUNTS.format(n=len(project.back_names))))

    def test_ac17_out_of_bounds_component_line(self):
        """`backend` вне границы (без `report`), `frontend` в границе: запись гейта несёт строку «компонент backend: вне границы гейта исходов».

        Ловит мутацию: компонент вне границы молча опущен — строки нет;
        компонент вне границы прогоняется ядром — прогоны pytest.
        """
        project = self.training(backend_report=False)
        t = self.component_task(project, "backend")
        rows, output = self.developer_advance(t, {"backend/seed/data.py": "SEED = 5\n"})
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        self.assertEqual(self.runners("pytest"), [], self.explain(rows, output))
        passed = self.records(rows)
        self.assertTrue(passed, self.explain(rows, output))
        joined = "\n".join(passed)
        self.assertIn(OUT_OF_BOUNDS.format(name="backend"), joined.splitlines(),
                      self.note(joined))

    def test_ac17_all_out_of_bounds_skip_record_and_review_lines(self):
        """Оба компонента вне границы: гейт не гоняется, запись пропуска «проверка тестов не выполняется: гейт неослабления по исходам» с «голова <sha>» и строками «вне границы»; `review_lines` головы — «не исполнялся» и строки компонентов.

        Ловит мутацию: пропуск без записи (молча); деталь записи без
        головы или без строк компонентов; `review_lines` не читает запись
        пропуска — только «не исполнялся».
        """
        project = self.training(backend_report=False, frontend_report=False)
        t = self.component_task(project, "backend")
        rows, output = self.developer_advance(t, {"backend/seed/data.py": "SEED = 6\n"})
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        self.assertEqual(self.records(rows), [], self.explain(rows, output))
        skips = self.records(rows, SKIP_RECORD)
        self.assertEqual(len(skips), 1, self.explain(rows, output))
        head = self.head(t)
        lines = skips[0].splitlines()
        self.assertIn(f"голова {head}", lines, self.note(skips[0]))
        for name in ("backend", "frontend"):
            self.assertIn(OUT_OF_BOUNDS.format(name=name), lines, self.note(skips[0]))
        got = outcome_integrity.review_lines(self.conn, t.id, head)
        self.assertEqual(got[0], NOT_RUN.format(head=head[:7]), self.note(str(got)))
        for name in ("backend", "frontend"):
            self.assertIn(f"гейт исходов: {OUT_OF_BOUNDS.format(name=name)}", got,
                          self.note(str(got)))


# ------------------------------------------------------------------ AC-18

class Ac18ReviewLinesTest(ComponentsOutcomeSandbox):

    def review_section(self, t) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            from orchestrator import review
            package = review.review_package(self.conn, t.id, "Задача", t.branch)
        return package["text"]

    def test_ac18_package_shows_consumer_records(self):
        """Пакет ревьювера задачи на `backend`, чей гейт прогнал и `frontend`, показывает строки записей гейта обоих компонентов.

        Ловит мутацию: `review_lines` берёт только последнюю запись головы
        — строки `backend` пропадают; пакет фильтрует строки по профилю
        задачи — строк `frontend` нет.
        """
        project = self.training()
        t = self.component_task(project, "backend")
        rows, output = self.developer_advance(t, {"backend/seed/data.py": "SEED = 7\n"})
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        head = self.head(t)
        got = outcome_integrity.review_lines(self.conn, t.id, head)
        for n in (len(project.back_names), len(project.front_names)):
            self.assertTrue(any(COUNTS.format(n=n) in line for line in got),
                            self.note(f"{n}: {got}"))
        text = self.review_section(t)
        self.assertIn(COUNTS.format(n=len(project.front_names)), text, self.note(text[-3000:]))

    def test_ac18_out_of_bounds_task_shows_consumer_lines(self):
        """Задача на `backend` вне границы (без `report`), `frontend` в границе прогнан гейтом: пакет ревьювера показывает строки записи гейта `frontend`.

        Ловит мутацию: строки гейта исходов в пакете отфильтрованы по
        границе профиля задачи — у задачи вне границы раздела строк гейта
        нет.
        """
        project = self.training(backend_report=False)
        t = self.component_task(project, "backend")
        rows, output = self.developer_advance(t, {"backend/seed/data.py": "SEED = 8\n"})
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        text = self.review_section(t)
        self.assertIn(COUNTS.format(n=len(project.front_names)), text, self.note(text[-3000:]))


# ------------------------------------------------------------------ AC-22

class Ac22FrontendTaskTest(ComponentsOutcomeSandbox):

    def test_ac22_tests_writing_exit_by_frontend_rule(self):
        """Выход из `tests_writing` задачи на `frontend` с планкой `AC-<n>: ` по правилу `frontend` проходит в `in_dev`, честный FAIL_TO_PASS гоняет Vitest.

        Ловит мутацию: выход на `decide(target)` — отказ «переход
        отклонён: профиль тестов проекта», задача остаётся в
        `tests_writing`.
        """
        project = self.training()
        t, rows, output = self.writing_task(project, "frontend")
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        self.assertTrue([r for r in self.runs if r["kind"] == "vitest" and r["plank"]],
                        self.explain(rows, output))

    def test_ac22_in_dev_outcome_gate_by_frontend(self):
        """Гейт исходов на выходе из `in_dev` задачи на `frontend` гонит компонент `frontend` и пишет его запись.

        Ловит мутацию: `_bounds` на `decide(target)` — гейта нет, записи
        пройденного гейта нет.
        """
        project = self.training()
        t = self.component_task(project, "frontend")
        rows, output = self.developer_advance(
            t, {"frontend/src/App.jsx": "export const App = 3;\n"})
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        self.assertTrue(self.records(rows), self.explain(rows, output))

    def test_ac22_merge_gate_outcome_by_frontend(self):
        """Гейт мержа задачи на `frontend`: профиль не отказывает, гейт исходов окна мержа исполнен (доказан записью головы либо прогоном).

        Ловит мутацию: `_profile_refusal_exit` на `decide(target)` —
        «merge отклонён: профиль тестов проекта»; гейт исходов мержа
        молчит.
        """
        project = self.training()
        t = self.component_task(project, "frontend")
        rows, output = self.developer_advance(
            t, {"frontend/src/App.jsx": "export const App = 4;\n"})
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        self.to_merge_gate(t)
        rows, output = self.approve(t)
        refused = [r for r in rows if r["action"] == "merge отклонён: профиль тестов проекта"]
        self.assertEqual(refused, [], self.explain(rows, output))
        gate = [r for r in rows if "гейт исходов" in (r["action"] or "")
                or (r["action"] or "") == PASSED_ACTION]
        self.assertTrue(gate, self.explain(rows, output))


# ------------------------------------------------------------------ AC-13 / AC-14

class Ac13Ac14GateMandateTest(ComponentsOutcomeSandbox):

    def mandate_answer(self, t, marker: str, element: str, matrix_element: str,
                       covered: str) -> None:
        row = (f"`{matrix_element}`", "находка «сломан правкой» компонента frontend",
               "остаётся", covered, "ок")
        text = (f"{marker} {element}\n\n"
                "Независимая проверка: матрица подтверждена\n\n"
                f"Основание: решение Оператора ({self.seed}).\n\n"
                "## Матрица неослабления\n\n"
                "| " + " | ".join(MATRIX_HEADERS) + " |\n"
                + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
                + "| " + " | ".join(row) + " |\n")
        path = self.root / ".artel" / f"answer-{self.word()}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                answer.cmd_answer(t.id, str(path))
            except SystemExit as exc:
                self.assertIn(exc.code, (None, 0), self.note(
                    f"answer отказала: {buf.getvalue()}"))

    def broken_consumer(self):
        project = self.training()
        t = self.component_task(project, "backend")
        broken = self.rng.choice(project.front_names)
        self.cases[(project.front_rel, broken)] = {"base": ["passed"],
                                                   "head": ["failed"]}
        return project, t, broken

    def test_ac13_path_mandate_on_consumer_lifts_finding(self):
        """Задача на `backend`, тест `frontend` сломан правкой: мандат «Ослабление тестов разрешено:» на файл теста `frontend` с матрицей «остаётся / покрыто путём области frontend» принят `answer` и снимает находку на рубеже.

        Ловит мутацию: мандат проверяется по области компонента задачи —
        `answer` отказывает «путь вне области backend/tests/**»; находка
        другого компонента не покрывается мандатом — отказ «сломан
        правкой» на рубеже.
        """
        project, t, _broken = self.broken_consumer()
        self.mandate_answer(t, mandate.TEST_WEAKENING_MANDATE_MARKER,
                            project.front_rel, project.front_rel,
                            f"frontend/src/{self.word()}.test.jsx:1")
        rows, output = self.developer_advance(
            t, {"backend/seed/data.py": "SEED = 9\n"}, finished=True)
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        self.assertEqual(self.records(rows, BROKEN_ACTION), [], self.explain(rows, output))

    def test_ac14_id_mandate_on_consumer_lifts_finding(self):
        """Задача на `backend`: мандат «Ослабление теста по идентификатору разрешено:» с идентификатором `frontend:…` сломанного теста и матрицей «остаётся, покрыто `frontend:…`» принят `answer` и снимает находку на рубеже.

        Ловит мутацию: компонент идентификатора сверяется с профилем
        задачи — отказ «компонента «frontend» нет в записи components:
        проекта»; находка остаётся непокрытой.
        """
        project, t, broken = self.broken_consumer()
        cid = project_profile.test_id("frontend", project.front_rel, broken)
        other = project_profile.test_id("frontend", project.front_rel,
                                        self.rng.choice(project.front_names))
        self.mandate_answer(t, mandate.TEST_ID_MANDATE_MARKER, cid, cid,
                            f"покрыто `{other}`")
        rows, output = self.developer_advance(
            t, {"backend/seed/data.py": "SEED = 10\n"}, finished=True)
        self.assertEqual(self.state(t), "verifying", self.explain(rows, output))
        self.assertEqual(self.records(rows, BROKEN_ACTION), [], self.explain(rows, output))


# ============================================ планка чужого компонента

FAIL_TO_PASS_ACTION = "переход отклонён: честный FAIL_TO_PASS"
FOREIGN = "файл планки {name} — компонента {x}, задача — компонента {y}"


class ForeignPlankSandbox(ComponentsOutcomeSandbox):

    def plank(self, comp: str) -> tuple:
        """(имя, текст) файла планки компонента `comp` по правилу планки;
        `<n>` — номер критерия SPEC задачи."""
        kind = SimpleNamespace(kind="vitest" if comp == "frontend" else "junit")
        name, body = self.plank_text(kind, 0)
        return name, body.replace("AC-0:", "AC-<n>:").replace("test_ac0_",
                                                            "test_ac<n>_")

    def exit_with_foreign(self, project, task_comp: str, foreign_comp: str):
        own_name, own_body = self.plank(task_comp)
        name, body = self.plank(foreign_comp)
        t, rows, output = self.writing_task(project, task_comp,
                                            {own_name: own_body, name: body})
        return t, rows, output, name

    def foreign_refusals(self, rows) -> list:
        return [d for d in self.details(rows, FAIL_TO_PASS_ACTION)]


class Ac19ForeignPlankTest(ForeignPlankSandbox):

    def test_ac19_foreign_file_in_bounds_refused(self):
        """Задача на `frontend`, в планке файл `backend` (в границе): отказ FAIL_TO_PASS «файл планки <имя> — компонента backend, задача — компонента frontend», задача остаётся в `tests_writing`.

        Ловит мутацию: `criterion_files` молча пропускает файл, чьего
        компонента нет среди профилей гейта (профиль задачи один) —
        переход проходит в `in_dev`.
        """
        project = self.training()
        t, rows, output, name = self.exit_with_foreign(project, "frontend",
                                                       "backend")
        self.assertEqual(self.state(t), "tests_writing", self.explain(rows, output))
        found = self.foreign_refusals(rows)
        self.assertTrue(any(FOREIGN.format(name=name, x="backend", y="frontend") in d
                            for d in found), self.explain(rows, output))

    def test_ac19_task_out_of_bounds_still_refused(self):
        """Задача на `backend` без `report` (вне границы), в планке файл `frontend` (в границе): тот же отказ — «… компонента frontend, задача — компонента backend».

        Ловит мутацию: гейт FAIL_TO_PASS добавляется только по профилю
        задачи в границе (`fsm_advance.py:609–613`) — у задачи вне границы
        файл чужого компонента в границе не проверяется.
        """
        project = self.training(backend_report=False)
        t, rows, output, name = self.exit_with_foreign(project, "backend",
                                                       "frontend")
        self.assertEqual(self.state(t), "tests_writing", self.explain(rows, output))
        found = self.foreign_refusals(rows)
        self.assertTrue(any(FOREIGN.format(name=name, x="frontend", y="backend") in d
                            for d in found), self.explain(rows, output))


class Ac25TrainingProjectTest(ForeignPlankSandbox):

    def test_ac25_backend_file_on_frontend_task(self):
        """Учебный проект: файл планки `backend` у задачи на `frontend` получает отказ AC-19 с именем файла и обоими компонентами.

        Ловит мутацию: компоненты в тексте отказа перепутаны местами
        (X — компонент задачи); отказ без имени файла.
        """
        project = self.training()
        _t, rows, output, name = self.exit_with_foreign(project, "frontend",
                                                        "backend")
        found = self.foreign_refusals(rows)
        self.assertTrue(found, self.explain(rows, output))
        self.assertIn(FOREIGN.format(name=name, x="backend", y="frontend"),
                      "\n".join(found), self.explain(rows, output))
        self.assertNotIn(FOREIGN.format(name=name, x="frontend", y="backend"),
                         "\n".join(found), self.explain(rows, output))


class Ac27OutOfBoundsForeignTest(ForeignPlankSandbox):

    def test_ac27_foreign_out_of_bounds_not_checked(self):
        """Чужой компонент `backend` без `report` (вне границы): его файл у задачи на `frontend` не проверяется — отказа AC-19 и иного отказа по файлу нет, задача уходит в `in_dev`; тот же файл при `backend` в границе — отказ AC-19.

        Ловит мутацию: отказ AC-19 дан любому файлу чужого компонента без
        условия границы — у `backend` вне границы переход отклонён.
        """
        project = self.training(backend_report=False)
        t, rows, output, name = self.exit_with_foreign(project, "frontend",
                                                       "backend")
        self.assertEqual(self.state(t), "in_dev", self.explain(rows, output))
        self.assertEqual(self.foreign_refusals(rows), [], self.explain(rows, output))
        project = self.training()
        t, rows, output, name = self.exit_with_foreign(project, "frontend",
                                                       "backend")
        self.assertEqual(self.state(t), "tests_writing", self.explain(rows, output))
        self.assertTrue(any(FOREIGN.format(name=name, x="backend", y="frontend") in d
                            for d in self.foreign_refusals(rows)),
                        self.explain(rows, output))
