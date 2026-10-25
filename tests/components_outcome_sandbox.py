"""Песочница гейта исходов по компонентам: учебный проект из двух компонентов и задача на один из них (ComponentsOutcomeSandbox), планка чужого компонента (ForeignPlankSandbox)."""
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
