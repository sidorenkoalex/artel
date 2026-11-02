"""Гейт неослабления по исходам для компонента `full_suite: ci` — на `verifying` по отчёту CI отправленной головы, а не на `in_dev` локальными выписками.

Группа: долгоживущий
Красен до реализации: компонент `full_suite: ci` судится на выходе из `in_dev` локальными выписками (задача с красным тестом головы не уходит в `verifying`), а опрос `verifying` при зелёном CI переводит задачу в `review` без гейта по исходам — без чтения отчётов задания `ci_job`, без возврата в `in_dev`, ожидания и эскалации по ним.

Стенд — песочница гейта исходов мержа
(`tests.merge_outcome_sandbox.MergeOutcomeSandbox` поверх
`tests.outcome_gate_sandbox.OutcomeGateSandbox`): настоящий git, учебный
внешний проект `forge: gitlab` с компонентом `junit-xml`, `full_suite: ci`
(или `both`, или запись из нескольких компонентов) и `ci_job`. Задача
проходит настоящий выход из `tests_writing` и шаг `developer`
(`developer_advance`), затем опросы `verifying` — `fsm.cmd_advance`.
Локальный раннер — шпион `subprocess.Popen` (`runs`), выписки гейта —
шпион `subprocess.run` в кадрах модулей гейта (`worktree add`), отправка
головы — шпион `github_adapter.ensure_head_in_origin` (`pushed`).

Хостинг подменён целиком: реестр `forge.IMPLEMENTATIONS` под ключом
`gitlab` указывает на хостинг сценария `ScenarioForge`. Его
`pipeline_status` отдаёт задания коммита (имя, статус, `id`,
`allow_failure`) и вердикт по ним, либо зелёный вердикт принудительно
(`green`): так «CI головы зелёный» в опросе `verifying` сочетается с любым
состоянием задания `ci_job`. `job_result` — статус последней попытки,
`job_test_report` — отчёт `<classname>::<name>` → статус GitLab; сбои
чтения и перезапуск задания во время чтения задаёт сценарий. Каждое
чтение записывается (`calls`).

Потолок ожидания `config.VERIFYING_CEILING_SEC` подменён: на время теста
он огромен (ожидание не истекает), сценарий «по истечении потолка»
ставит его в ноль.

Имена проектов, компонентов, файлов, тестов, заданий и `id` заданий — из
`random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
пропуск `ci` в гейте `in_dev`, гейт по ядру `_judge_ci` с базой
`_diff_base` в опросе `verifying` после зелёного CI, ожидание, эскалация,
возврат в `in_dev` и пределы цикла — все методы файла зелёные.
"""
import contextlib
import io
import re
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import (brief, checkpoint, config, forge, github_adapter,
                          project_profile, pull_main, store, workspace)
from orchestrator.advance_gates import outcome_integrity, refusal_classes
from tests.components_outcome_sandbox import ContextRunnerProc
from tests.fixtures import _sandbox
from tests.merge_outcome_sandbox import MergeOutcomeSandbox
from tests.outcome_gate_sandbox import (APPROVED_DETAIL, ENTRY_HEAD, PLANK_DIR,
                                        flow, py_source, spec_text, ulid)
from tests.sandbox import make_project_repo

PASSED = outcome_integrity.PASSED_ACTION
BROKEN_ACTION = refusal_classes.OUTCOME_BROKEN_REFUSAL_ACTION
OPERATOR_ACTION = refusal_classes.OUTCOME_INTEGRITY_REFUSAL_ACTION
PREPARE_ACTION = refusal_classes.OUTCOME_PREPARE_REFUSAL_ACTION
MERGE_PREPARE = outcome_integrity.MERGE_PREPARE_ACTION
GATE_ACTIONS = (BROKEN_ACTION, OPERATOR_ACTION, PREPARE_ACTION)
BROKEN = outcome_integrity.BROKEN
GONE = outcome_integrity.GONE
NO_BASE_REPORT = "нет отчёта базы"
BASE_AMBIGUOUS = "отчёт базы неоднозначен: "
RESTARTED = "перезапущено во время чтения"
REPEAT = "повтор находки гейта по исходам"
LIMIT = "предел возвратов гейта по исходам"
ESCALATED = "state -> escalated"
TO_IN_DEV = "state -> in_dev"
TO_REVIEW = "state -> review"
TO_VERIFYING = "state -> verifying"
OTHER_JOB = "lint"
STRANGE_STATUS = "unknown"
UNFINISHED = ("created", "pending", "running", "waiting_for_resource",
              "preparing", "scheduled")
HUGE = 10 ** 9
HEX_RUN = re.compile(r"[0-9a-f]{7,40}")

# Вердикт `pipeline_status` по статусу задания — для правдоподобия ответа
# хостинга; зелёный вердикт сценарий может задать и принудительно.
VERDICTS = {"success": forge.GREEN, "failed": forge.RED,
            "running": forge.RUNNING, "pending": forge.RUNNING,
            "created": forge.RUNNING}


class ScenarioForge:
    """Хостинг сценария под ключом `gitlab`: задания и отчёты по sha,
    сбои чтения и перезапуск задания; каждое чтение — в `calls`."""

    CI_BY_PIPELINE = True

    def __init__(self, box):
        self.box = box
        self.jobs: dict = {}
        self.reports: dict = {}
        self.report_reasons: dict = {}
        self.status_fail: dict = {}
        self.restart: set = set()
        self.green: set = set()
        self.explode = ""
        self.calls: list = []

    def record(self, name: str, sha: str) -> None:
        self.calls.append((name, sha, self.box.in_gate()))

    def last(self, sha: str, name: str):
        attempts = [j for j in self.jobs.get(sha, []) if j.name == name]
        return max(attempts, key=lambda j: j.id) if attempts else None

    def pipeline_status(self, target, sha):
        self.record("pipeline_status", sha)
        jobs = list(self.jobs.get(sha, []))
        if not jobs:
            return forge.PipelineStatus(forge.NONE, f"у коммита {sha[:8]} "
                                                    f"нет конвейера")
        if sha in self.green:
            return forge.PipelineStatus(forge.GREEN, "", jobs)
        verdict = forge.senior(VERDICTS.get(j.status, forge.UNKNOWN)
                               for j in jobs if not j.allow_failure)
        return forge.PipelineStatus(verdict, "", jobs)

    def job_result(self, target, sha, job_name):
        self.record("job_result", sha)
        if (sha, job_name) in self.status_fail:
            return forge.JobResult(None, self.status_fail[(sha, job_name)])
        job = self.last(sha, job_name)
        if job is None:
            return forge.JobResult(None, f"задания {job_name} у {sha[:8]} нет")
        return forge.JobResult(job.status, "")

    def job_test_report(self, target, sha, job_name):
        self.record("job_test_report", sha)
        if self.explode:
            raise RuntimeError(self.explode)
        job = self.last(sha, job_name)
        if job is None:
            return forge.TestReport(None, f"задания {job_name} у {sha[:8]} нет")
        if (sha, job_name) in self.restart:
            # Новая попытка задания появилась между чтением годности и
            # чтением отчёта.
            newer = job.id + self.box.rng.randrange(1, 10 ** 4)
            self.box.ids_used.add(newer)
            self.jobs[sha].append(forge.Job(job_name, job.status, "test",
                                            newer, False))
        report = self.reports.get((sha, job_name))
        if report is None:
            return forge.TestReport(None, self.report_reasons.get(
                (sha, job_name), "отчёт не разобран (сценарий)"))
        return forge.TestReport(dict(report), "")

    def __getattr__(self, name):
        if name not in forge.RESULT_TYPES:
            raise AttributeError(name)

        def call(*args):
            return forge.RESULT_TYPES[name](reason=f"{name}: не дано сценарием")
        return call


class VerifyingBox(MergeOutcomeSandbox):
    """Песочница гейта исходов с хостингом сценария, шпионами выписок и
    отправки головы и подменённым потолком `verifying`."""

    def setUp(self):
        super().setUp()
        self.forge = ScenarioForge(self)
        self.checkouts: list = []
        self.pushed: list = []
        self.ids_used: set = set()
        self.fail_git = None
        self.git_fail = self.watch_git
        for patcher in (
                mock.patch.dict(forge.IMPLEMENTATIONS, {"gitlab": self.forge}),
                mock.patch.object(github_adapter, "ensure_head_in_origin",
                                  self.spy_push),
                mock.patch.object(config, "VERIFYING_CEILING_SEC", HUGE)):
            patcher.start()
            self.addCleanup(patcher.stop)

    # --- шпионы ---------------------------------------------------------

    def watch_git(self, args: tuple) -> bool:
        if "worktree" in args and "add" in args:
            self.checkouts.append(args)
        return self.fail_git is not None and bool(self.fail_git(args))

    def spy_push(self, conn, task_id, branch, *args, **kwargs):
        self.pushed.append((task_id, branch))
        return True, ""

    def runner_run(self, kind, parts, cwd, args, kwargs):
        if kind == "pytest" and "--collect-only" in parts:
            # Сухой сбор планки: поддельный pytest собирает её без ошибок.
            return self.answer(0, "1 test collected\n", args, kwargs)
        proc = super().runner_run(kind, parts, cwd, args, kwargs)
        proc.__class__ = ContextRunnerProc
        return proc

    # --- проекты --------------------------------------------------------

    def component_fields(self, job: str, root: str, mode: str) -> dict:
        scope = f"{root}tests/**"
        fields = {"command": flow([str(self.pytest_cmd)]),
                  "report": "junit-xml",
                  "long_lived_dir": f"{root}tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": flow([scope]),
                  "mutation_claim_scope": flow([scope]),
                  "failure_errors": flow(["AssertionError"]),
                  "plank_layout": f"{root}.pg{self.word(5)}/<id>"}
        if mode != "local":
            fields.update(full_suite=mode, ci_job=job)
        return fields

    def project(self, mode: str = "ci", n: int = 3,
                squash: bool = False) -> SimpleNamespace:
        """Учебный проект `forge: gitlab` с единственным компонентом режима
        `mode` и файлом из `n` тестов."""
        return self.multi([mode], n=n, squash=squash, single=True)

    def multi(self, modes, n: int = 3, squash: bool = False,
              single: bool = False) -> SimpleNamespace:
        """Учебный проект из компонентов режимов `modes` (по порядку
        записи); у каждого — свой каталог `paths`, файл тестов и задание
        CI. `single` — один компонент без `paths` в корне проекта."""
        name = f"g{self.word()}"
        head = ENTRY_HEAD.format(name=name).replace("forge: github",
                                                    "forge: gitlab")
        lines = [head]
        if squash:
            lines.append("    squash_before_mr: true\n")
        lines.append("    components:\n")
        files = {"app.py": "APP = 'base'\n"}
        comps = []
        for mode in modes:
            comp, job = f"c{self.word()}", f"t{self.word()}"
            root = "" if single else f"{comp}/"
            fields = self.component_fields(job, root, mode)
            if not single:
                fields["paths"] = flow([f"^{comp}/"])
            lines.append(f"      {comp}:\n")
            lines += [f"        {k}: {v}\n" for k, v in fields.items()]
            rel = f"{root}tests/test_{self.word()}.py"
            names = [self.py_name() for _ in range(n)]
            files[rel] = py_source(names)
            comps.append(SimpleNamespace(comp=comp, job=job, mode=mode,
                                         rel=rel, names=names, root=root))
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        self.commit_project(clone, files)
        self.clones[name] = clone
        first = comps[0]
        return SimpleNamespace(name=name, clone=clone, comps=comps,
                               comp=first.comp, job=first.job, rel=first.rel,
                               names=first.names, kind="junit", layout="",
                               single=single)

    def main_commit(self, project) -> str:
        """Коммит кода на `main` проекта, отправленный в его `origin`."""
        self.commit_project(project.clone,
                            {f"lib/m{self.word()}.py": f"M = '{self.word()}'\n"})
        return self.git("-C", str(project.clone), "rev-parse",
                        config.MAIN_BRANCH).strip()

    # --- задачи ---------------------------------------------------------

    def new_task(self, project):
        """Задача проекта в `in_dev` после настоящего выхода из
        `tests_writing`; у записи из нескольких компонентов — задача на
        первый компонент (зоны «<компонент>/, app.py»)."""
        if project.single:
            return self.task(project)
        n = self.rng.randrange(1, 60)
        tid = ulid(self.rng)
        branch = f"task/{tid.lower()}-{self.word()}"
        zones = f"{project.comp}/, app.py"
        store.insert_task(self.conn, tid, "Фикстура гейта исходов", "spec_gate",
                          branch, project.name, 25.0)
        store.update_task(self.conn, tid, zones=zones)
        wt, error = workspace.ensure(tid, branch)
        assert error is None, self.note(f"рабочая копия не заведена: {error}")
        t = SimpleNamespace(id=tid, low=tid.lower(), branch=branch,
                            target=project.name, wt=Path(wt), project=project,
                            zones=zones)
        t.docs = config.PROJECTS / project.name / "tasks" / tid
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
        plank_name, plank_body = self.plank_text(project, n)
        (t.plank / plank_name).write_text(plank_body, encoding="utf-8")
        self.plank_green = False
        store.journal(self.conn, tid, "test_author", "agent run started",
                      f"шаг сценария {self.word()}")
        checkpoint.commit_step_artifacts(self.conn, tid, "test_author")
        checkpoint.commit_success_checkpoint(self.conn, tid, "test_author")
        self.current = tid
        rows, output = self.run_advance(tid)
        assert self.state(t) == "in_dev", self.explain(rows, output)
        self.plank_green = True
        return t

    def commit_code(self, t, changes: dict, message: str = "код разработчика"):
        super().commit_code(t, changes, message)
        if getattr(t, "zones", None):
            store.update_task(self.conn, t.id, zones=t.zones)

    def develop(self, t, changes: dict | None = None, **kwargs) -> tuple:
        """Шаг `developer` и `advance` из `in_dev`; шпионы очищены."""
        self.checkouts.clear()
        self.pushed.clear()
        self.forge.calls.clear()
        rows, output = self.developer_advance(t, changes, **kwargs)
        t.sent = self.head(t)
        return rows, output

    def to_verifying(self, t, changes: dict | None = None, **kwargs) -> tuple:
        rows, output = self.develop(t, changes, **kwargs)
        assert self.state(t) == "verifying", self.explain(rows, output)
        return rows, output

    def poll(self, t) -> tuple:
        """Один опрос `verifying` (`advance`): (новые записи, вывод)."""
        self.checkouts.clear()
        self.forge.calls.clear()
        self.counts.clear()
        return self.run_advance(t.id)

    def base(self, t) -> str:
        """Точка ответвления кодовой ветки — правило `gitcmd.diff_base`:
        merge-base ветки с `refs/remotes/origin/<основная ветка>` клона."""
        return self.git("-C", str(t.project.clone), "merge-base",
                        f"refs/remotes/origin/{config.MAIN_BRANCH}",
                        t.branch).strip()

    # --- отчёты ---------------------------------------------------------

    def job_id(self) -> int:
        while True:
            value = self.rng.randrange(10 ** 5, 10 ** 9)
            if value not in self.ids_used:
                self.ids_used.add(value)
                return value

    def jobs_of(self, sha: str) -> list:
        jobs = self.forge.jobs.setdefault(sha, [])
        if not jobs:
            jobs.append(forge.Job(OTHER_JOB, "success", "lint", self.job_id(),
                                  False))
        return jobs

    def publish(self, sha: str, job: str, status: str, report,
                allow_failure: bool = False) -> int:
        """Задание `job` коммита `sha` в статусе `status` и его отчёт
        (`None` — отчёта нет); `id` задания."""
        value = self.job_id()
        self.jobs_of(sha).append(forge.Job(job, status, "test", value,
                                           allow_failure))
        if report is not None:
            self.forge.reports[(sha, job)] = report
        return value

    @staticmethod
    def key(rel: str, full: str) -> str:
        """Ключ отчёта GitLab `<classname>::<name>` теста `full` файла `rel`."""
        module = rel[:-len(".py")].replace("/", ".")
        return f"{module}::{full}"

    def green(self, comp, names=None) -> dict:
        return {self.key(comp.rel, n): "success" for n in (names or comp.names)}

    def red(self, comp, name: str, status: str = "failed") -> dict:
        return dict(self.green(comp), **{self.key(comp.rel, name): status})

    @staticmethod
    def cid(comp, name: str) -> str:
        return project_profile.test_id(comp.comp, comp.rel, name)

    def ci_reports(self, t, head_reports: dict, base_reports: dict | None = None,
                   base: str | None = None) -> dict:
        """Зелёный CI головы `t.sent`: задания `ci_job` головы и базы с
        отчётами {компонент: отчёт}; база — `diff_base`, если не задана.
        {(сторона, компонент): `id` задания}."""
        base = base or self.base(t)
        ids = {}
        for comp in t.project.comps:
            if comp.mode == "local":
                continue
            head = head_reports.get(comp.comp, self.green(comp))
            ids[("head", comp.comp)] = self.publish(t.sent, comp.job,
                                                    "success", head)
            own = (base_reports or {}).get(comp.comp, self.green(comp))
            ids[("base", comp.comp)] = self.publish(base, comp.job,
                                                    "success", own)
        return ids

    # --- наблюдения -----------------------------------------------------

    def why(self, rows: list, output: str) -> str:
        return (self.explain(rows, output)
                + f"\nсостояние: {self.state_of(rows)}\nхостинг: "
                f"{self.forge.calls}\nвыписки: {self.checkouts}\n"
                f"отправки: {self.pushed}")

    @staticmethod
    def actions(rows: list) -> list:
        return [r["action"] for r in rows]

    @staticmethod
    def state_details(rows: list, action: str) -> list:
        return [r["detail"] or "" for r in rows if r["action"] == action]

    def report_reads(self) -> list:
        return [sha for name, sha, _in in self.forge.calls
                if name == "job_test_report"]


@pytest.fixture
def box():
    """Стенд VerifyingBox после setUp."""
    yield from _sandbox(VerifyingBox)


def has_number(text: str, value: int) -> bool:
    return re.search(rf"(?<!\d){value}(?!\d)", text) is not None


def no_transition(box, rows, output, *states) -> None:
    for state in states:
        assert f"state -> {state}" not in box.actions(rows), box.why(rows, output)


# ---------------------------------------------------------------- AC-1


def test_ac1_ci_component_skips_local_gate_on_in_dev(box):
    """Компонент `full_suite: ci`: выход из `in_dev` без выписок и полных прогонов сторон «база» и «голова», задача в `verifying`, ветка отправлена на `origin`.

    Сценарий: проект с единственным компонентом `full_suite: ci`; тест
    базы на голове локально красен все три прогона (сценарий раннера) —
    локальный гейт отказал бы «сломан правкой». Шаг `developer` и
    `advance` из `in_dev`: задача в `verifying`, отказа гейта по исходам
    нет; шпион не видит ни `worktree add` из кадров гейта, ни полного
    прогона сторон «база»/«голова»; голова ветки отправлена
    (`ensure_head_in_origin` с веткой задачи).

    Ловит мутацию: пропуск гейта `in_dev` для `ci` не сделан — выписки и
    полные прогоны есть, отказ «сломан правкой», задача остаётся в
    `in_dev`; отправка на `origin` пропущена для `ci` — шпион отправки пуст.
    """
    project = box.project()
    red = box.rng.choice(project.names)
    box.cases[(project.rel, red)] = {"base": ["passed"], "head": ["failed"]}
    t = box.new_task(project)
    rows, output = box.develop(t)
    assert box.state(t) == "verifying", box.why(rows, output)
    for action in GATE_ACTIONS:
        assert box.details(rows, action) == [], box.why(rows, output)
    assert box.checkouts == [], box.why(rows, output)
    assert box.full_runs() == [], box.why(rows, output)
    assert [c for c in box.suite_calls if c["side"] in ("base", "head")] == [], \
        box.why(rows, output)
    assert (t.id, t.branch) in box.pushed, box.why(rows, output)


# ---------------------------------------------------------------- AC-2


def test_ac2_clean_reports_pass_gate_to_review_with_record(box):
    """CI головы зелёный, отчёты головы и базы без расхождений — задача в `review`, запись пройденного гейта называет задания `ci_job` головы и базы, коммит базы (точку ответвления `diff_base`) и число тестов.

    Сценарий: проект `full_suite: ci` с файлом из случайного числа
    тестов; задача в `verifying`; после входа `main` проекта ушёл вперёд
    (коммит кода отправлен в `origin`), так что вершина `main` — не точка
    ответвления. Отчёты задания `ci_job` зелёные у головы и у точки
    ответвления `gitcmd.diff_base`; у вершины `main` отчёта нет. Опрос
    `verifying`: задача в `review`; в записях опроса есть
    `PASSED_ACTION` — до перехода в `review`; в ней `id` заданий головы и
    базы, sha точки ответвления и число тестов базы; sha вершины `main` в
    ней нет.

    Ловит мутацию: гейт на `verifying` берёт базой вершину `main`
    (`_merge_base_of` со свежим main или `origin/main`) — отчёта базы нет,
    эскалация вместо `review`; запись прохода без `id` задания базы или
    без коммита базы; переход в `review` без гейта — записи прохода нет.
    """
    n = box.rng.randint(2, 6)
    project = box.project(n=n)
    t = box.new_task(project)
    box.to_verifying(t)
    point = box.base(t)
    tip = box.main_commit(project)
    assert tip != point, box.note("main не ушёл вперёд")
    ids = box.ci_reports(t, {}, base=point)
    rows, output = box.poll(t)
    assert box.state(t) == "review", box.why(rows, output)
    actions = box.actions(rows)
    assert PASSED in actions, box.why(rows, output)
    assert actions.index(PASSED) < actions.index(TO_REVIEW), box.why(rows, output)
    detail = box.details(rows, PASSED)[-1]
    assert has_number(detail, ids[("head", project.comp)]), box.why(rows, output)
    assert has_number(detail, ids[("base", project.comp)]), box.why(rows, output)
    assert point in detail or point[:12] in detail, box.why(rows, output)
    assert tip not in detail and tip[:12] not in detail, box.why(rows, output)
    stripped = HEX_RUN.sub(" ", detail)
    for value in ids.values():
        stripped = stripped.replace(str(value), " ")
    assert has_number(stripped, n), box.why(rows, output)


# ---------------------------------------------------------------- AC-3


FINDING_LINE = "^{kind}: {cid} — ветка: .+; база: .+$"


def returned(box, t, rows, output) -> str:
    """Деталь отказа «сломан правкой» опроса, вернувшего задачу в `in_dev`:
    переход `verifying → in_dev`, ни `review`, ни `escalated`."""
    assert box.state(t) == "in_dev", box.why(rows, output)
    assert TO_IN_DEV in box.actions(rows), box.why(rows, output)
    no_transition(box, rows, output, "review", "escalated")
    found = box.details(rows, BROKEN_ACTION)
    assert found, box.why(rows, output)
    return found[-1]


def first_return(box, project=None, comp=None, red=None):
    """Сценарий AC-3: задача в `verifying`, тест `red` компонента `comp`
    зелёный в отчёте базы и красный в отчёте головы, мандата нет —
    опрос возвращает задачу в `in_dev`. (задача, компонент, тест, деталь
    отказа, записи, вывод)."""
    project = project or box.project()
    comp = comp or project.comps[0]
    red = red or box.rng.choice(comp.names)
    t = box.new_task(project)
    box.to_verifying(t)
    box.ci_reports(t, {comp.comp: box.red(comp, red)})
    rows, output = box.poll(t)
    detail = returned(box, t, rows, output)
    return t, comp, red, detail, rows, output


@pytest.mark.parametrize("status", ["failed", "error"])
def test_ac3_broken_on_verifying_returns_to_in_dev(box, status):
    """Тест зелёный в отчёте базы и красный в отчёте головы, мандата нет, возвратов ещё не было — опрос `verifying` возвращает задачу в `in_dev` с находкой «сломан правкой» тем же действием и текстом, что отказ гейта на `in_dev`.

    Сценарий: проект `full_suite: ci`; задача в `verifying`; CI головы
    зелёный; в отчёте задания `ci_job` головы один случайный тест
    `failed` либо `error`, в отчёте базы все `success`. Опрос: задача в
    `in_dev` (запись `state -> in_dev`), не в `review` и не в `escalated`;
    в записях опроса — действие `OUTCOME_BROKEN_REFUSAL_ACTION` (то же,
    что пишет отказ гейта на `in_dev`) со строкой находки в форме отказа
    на `in_dev`: «сломан правкой: <id> — ветка: …; база: …».

    Ловит мутацию: находка «сломан правкой» на `verifying` эскалирует
    задачу вместо возврата; находка пишется другим действием журнала
    (например, действием гейта мержа) или без идентификатора теста;
    статус `error` отчёта головы не считается красным — задача в `review`.
    """
    project = box.project()
    comp = project.comps[0]
    red = box.rng.choice(comp.names)
    t = box.new_task(project)
    box.to_verifying(t)
    box.ci_reports(t, {comp.comp: box.red(comp, red, status)})
    rows, output = box.poll(t)
    detail = returned(box, t, rows, output)
    line = FINDING_LINE.format(kind=re.escape(BROKEN),
                               cid=re.escape(box.cid(comp, red)))
    assert re.search(line, detail, re.MULTILINE), box.why(rows, output)


# ---------------------------------------------------------------- AC-4


def test_ac4_developer_brief_carries_verifying_findings(box):
    """После возврата из `verifying` бриф роли `developer` на `in_dev` несёт отказ гейта по исходам целиком — блоком «— <действие>:\\n<находки>», как после отказа на `in_dev`.

    Сценарий AC-3: возврат в `in_dev` с находкой «сломан правкой».
    `brief.advance_refusal_history(…, "developer", "in_dev")` — текст
    блока истории отказов: он содержит «— OUTCOME_BROKEN_REFUSAL_ACTION:»
    и следом деталь записи отказа целиком (тот же вид, каким бриф несёт
    отказ гейта на `in_dev`), в ней — идентификатор красного теста.

    Ловит мутацию: запись отказа сделана до записи `state -> in_dev`
    (выборка `store.refusal_history` её отсекает — блок пуст); находки
    журналируются действием вне префикса «переход отклонён» — бриф их не
    видит.
    """
    t, comp, red, detail, rows, output = first_return(box)
    text = brief.advance_refusal_history(box.conn, t.id, "developer", "in_dev")
    assert f"— {BROKEN_ACTION}:\n{detail}" in text, box.note(
        f"бриф: {text!r}\n") + box.why(rows, output)
    assert f"{BROKEN}: {box.cid(comp, red)} — " in text, box.why(rows, output)


# ---------------------------------------------------------------- AC-5


def test_ac5_operator_mandate_on_source_branch_lifts_finding(box):
    """Мандат Оператора на красный тест в ветке-источнике артефактов задачи снимает находку гейта на `verifying` — задача в `review`.

    Сценарий AC-3, но до шага `developer` Оператор отвечает (`answer`)
    строкой «Ослабление тестов разрешено: <путь>::<имя>» этого теста —
    ANSWER-n уходит в ссылку документов задачи. Задача в `verifying`,
    отчёт головы красен по этому тесту. Опрос: задача в `review`, отказа
    гейта нет, в записи пройденного гейта — строка находки этого теста
    «… — покрыто мандатом ANSWER-n».

    Ловит мутацию: гейт на `verifying` не читает мандат (или читает его
    из кодовой ветки, где ANSWER нет) — возврат в `in_dev` вместо
    `review`.
    """
    project = box.project()
    comp = project.comps[0]
    red = box.rng.choice(comp.names)
    t = box.new_task(project)
    box.operator_mandate(t, [f"{comp.rel}::{red}"])
    box.to_verifying(t, finished=True)
    box.ci_reports(t, {comp.comp: box.red(comp, red)})
    rows, output = box.poll(t)
    assert box.state(t) == "review", box.why(rows, output)
    for action in GATE_ACTIONS:
        assert box.details(rows, action) == [], box.why(rows, output)
    record = box.details(rows, PASSED)
    assert record, box.why(rows, output)
    cid = box.cid(comp, red)
    assert any(cid in line and "покрыто мандатом " in line
               for line in record[-1].splitlines()), box.why(rows, output)


# ---------------------------------------------------------------- AC-6


WAITS = (*(f"задание {s}" for s in UNFINISHED), "отчёт головы None",
         "задания нет", "отчёт не разобран", "статус не прочитан",
         "отчёт не прочитан")


def head_case(box, t, comp, case: str) -> list:
    """Состояние задания `ci_job` головы по случаю; отчёт базы зелёный.
    Слова, которые обязана назвать причина."""
    head = t.sent
    box.publish(box.base(t), comp.job, "success", box.green(comp))
    box.forge.green.add(head)
    word = box.word()
    if case.startswith("задание "):
        status = case.split(" ", 1)[1]
        box.publish(head, comp.job, status, None)
        return [comp.job, status]
    if case == "задания нет":
        box.jobs_of(head)
        return [comp.job]
    box.publish(head, comp.job, "success",
                None if case != "статус не прочитан" else box.green(comp))
    if case == "отчёт головы None":
        box.forge.report_reasons[(head, comp.job)] = ""
        return [comp.job]
    if case == "статус не прочитан":
        box.forge.status_fail[(head, comp.job)] = f"HTTP 502 {word}"
        return [comp.job, word]
    reason = (f"отчёт не разобран: {word}" if case == "отчёт не разобран"
              else f"HTTP 503 {word}")
    box.forge.report_reasons[(head, comp.job)] = reason
    return [comp.job, word]


def waits(box, t, rows, output, words) -> None:
    """Опрос оставил задачу в `verifying` с причиной: запись опроса
    называет все `words`; ни `review`, ни `in_dev`, ни `escalated`, ни
    прохода гейта."""
    assert box.state(t) == "verifying", box.why(rows, output)
    no_transition(box, rows, output, "review", "in_dev", "escalated")
    assert PASSED not in box.actions(rows), box.why(rows, output)
    assert any(all(w in (r["detail"] or "") for w in words) for r in rows), \
        box.note(f"причина без {words}\n") + box.why(rows, output)


def escalates_at_ceiling(box, t, words) -> None:
    """Опрос при истёкшем потолке (`VERIFYING_CEILING_SEC` = 0): задача в
    `escalated`, запись перехода называет те же `words`."""
    with mock.patch.object(config, "VERIFYING_CEILING_SEC", 0):
        rows, output = box.poll(t)
    assert box.state(t) == "escalated", box.why(rows, output)
    detail = box.state_details(rows, ESCALATED)
    assert detail and all(w in detail[-1] for w in words), box.note(
        f"эскалация без {words}\n") + box.why(rows, output)


@pytest.mark.parametrize("case", WAITS)
def test_ac6_unready_head_report_waits_then_escalates_at_ceiling(box, case):
    """Отчёт головы ещё не годен (задание не завершено, нет в конвейере, отчёт не разобран, сбой чтения хостинга) — задача остаётся в `verifying` с названной причиной; по истечении потолка — `escalated` с той же причиной.

    Сценарий (по случаю): CI головы зелёный (вердикт хостинга), отчёт
    базы зелёный; у головы — задание `ci_job` в статусе `created`/
    `pending`/`running`/`waiting_for_resource`/`preparing`/`scheduled`;
    либо задание `success` без отчёта (`None`), с неразобранным отчётом,
    с непрочитанным статусом или непрочитанным отчётом (причина хостинга
    — случайное слово); либо задания нет в конвейере (только `lint`).
    Первый опрос при огромном потолке: задача в `verifying`, ни
    `review`, ни `in_dev`, ни `escalated`, ни записи прохода; запись
    опроса называет задание (и статус либо слово причины хостинга).
    Второй опрос при потолке 0: задача в `escalated`, запись перехода
    называет те же слова.

    Ловит мутацию: неготовый отчёт головы — эскалация сразу (первый опрос
    уже `escalated`); неготовый отчёт засчитан зелёным или гейт пропущен
    — `review`; по потолку эскалация с прежней причиной «потолок ожидания
    CI» без причины гейта.
    """
    project = box.project()
    comp = project.comps[0]
    t = box.new_task(project)
    box.to_verifying(t)
    words = head_case(box, t, comp, case)
    rows, output = box.poll(t)
    waits(box, t, rows, output, words)
    escalates_at_ceiling(box, t, words)


# ---------------------------------------------------------------- AC-7


def escalated_now(box, t, rows, output) -> str:
    """Опрос при огромном потолке сразу эскалировал задачу: `escalated`,
    ни `review`, ни `in_dev`; деталь записи перехода."""
    assert box.state(t) == "escalated", box.why(rows, output)
    no_transition(box, rows, output, "review", "in_dev")
    detail = box.state_details(rows, ESCALATED)
    assert detail, box.why(rows, output)
    return detail[-1]


@pytest.mark.parametrize("parent", [False, True])
def test_ac7_no_base_report_escalates_at_once(box, parent):
    """Отчёта базы нет ни у точки ответвления, ни у её родителя с тем же деревом — задача сразу в `escalated` с причиной «нет отчёта базы».

    Сценарий (по случаю): CI и отчёт головы зелёные; у точки ответвления
    `diff_base` задания `ci_job` нет; (а) отчётов базы нет нигде; (б)
    зелёный отчёт есть у родителя точки ответвления, но дерево родителя
    другое. Опрос при огромном потолке: `escalated`, не `review` и не
    `in_dev`; запись перехода содержит «нет отчёта базы».

    Ловит мутацию: отсутствие отчёта базы — ожидание (задача остаётся в
    `verifying`) или пропуск (`review`); отчёт родителя берётся без сверки
    дерева — гейт пройден.
    """
    project = box.project()
    comp = project.comps[0]
    t = box.new_task(project)
    box.to_verifying(t)
    box.publish(t.sent, comp.job, "success", box.green(comp))
    if parent:
        point = box.base(t)
        older = box.git("-C", str(project.clone), "rev-parse",
                        f"{point}^").strip()
        box.publish(older, comp.job, "success", box.green(comp))
    rows, output = box.poll(t)
    detail = escalated_now(box, t, rows, output)
    assert NO_BASE_REPORT in detail, box.why(rows, output)


# ---------------------------------------------------------------- AC-8


@pytest.mark.parametrize("ambiguity", ["статус вне перечня", "модуль не найден",
                                       "два ключа"])
def test_ac8_ambiguous_base_report_escalates_at_once(box, ambiguity):
    """Неоднозначный отчёт базы или неоднозначный перевод его идентификаторов — задача сразу в `escalated` с причиной «отчёт базы неоднозначен: <запись>», не ожидание.

    Сценарий (по случаю): CI и отчёт головы зелёные и однозначные; в
    отчёте базы сверх зелёных тестов (а) тест со статусом вне перечня,
    (б) запись `tests.<нет файла>::<имя>`, модуля которой нет в дереве,
    (в) тест записан двумя ключами (точечным и с `/`). Опрос при
    огромном потолке: `escalated`, не `review`, не `in_dev`; запись
    перехода — «отчёт базы неоднозначен: <ключ или идентификатор>».

    Ловит мутацию: неоднозначность базы — ожидание (задача в `verifying`);
    неоднозначная запись базы молча выпадает — `review`; причина
    эскалации не дословная (без записи).
    """
    project = box.project()
    comp = project.comps[0]
    t = box.new_task(project)
    box.to_verifying(t)
    clean = box.green(comp)
    base = dict(clean)
    odd = box.rng.choice(comp.names)
    if ambiguity == "статус вне перечня":
        base[box.key(comp.rel, odd)] = STRANGE_STATUS
        named = box.cid(comp, odd)
    elif ambiguity == "модуль не найден":
        named = f"tests.test_{box.word()}::{box.py_name()}"
        base[named] = "success"
    else:
        base[f"{comp.rel}::{odd}"] = "success"
        named = box.cid(comp, odd)
    box.ci_reports(t, {comp.comp: clean}, {comp.comp: base})
    rows, output = box.poll(t)
    detail = escalated_now(box, t, rows, output)
    assert f"{BASE_AMBIGUOUS}{named}" in detail, box.why(rows, output)


@pytest.mark.parametrize("status", ["canceled", "manual", "allow_failure"])
def test_ac8_other_head_job_state_escalates_at_once(box, status):
    """Иное состояние задания `ci_job` головы — `canceled`, `manual`, `failed` с `allow_failure` — задача сразу в `escalated` с причиной сбоя, не ожидание.

    Сценарий (по случаю): CI головы зелёный (вердикт хостинга), отчёт
    базы зелёный; последнее задание `ci_job` головы — `canceled`,
    `manual` либо `failed` с `allow_failure` (отчёт есть). Опрос при
    огромном потолке: `escalated`, не `review`, не `in_dev`; запись
    перехода называет задание и состояние (`canceled`/`manual`/
    `allow_failure`).

    Ловит мутацию: любая негодность головы (свёртка «нет отчёта головы»)
    — ожидание: задача остаётся в `verifying`; `failed` с `allow_failure`
    засчитан годным — сравнение, возврат в `in_dev`.
    """
    project = box.project()
    comp = project.comps[0]
    t = box.new_task(project)
    box.to_verifying(t)
    box.publish(box.base(t), comp.job, "success", box.green(comp))
    box.forge.green.add(t.sent)
    red = box.red(comp, box.rng.choice(comp.names))
    if status == "allow_failure":
        box.publish(t.sent, comp.job, "failed", red, allow_failure=True)
    else:
        box.publish(t.sent, comp.job, status, red)
    rows, output = box.poll(t)
    detail = escalated_now(box, t, rows, output)
    assert comp.job in detail and status in detail, box.why(rows, output)


@pytest.mark.parametrize("failure", ["дерево отчёта", "исключение"])
def test_ac8_other_prepare_failure_escalates_at_once(box, failure):
    """Прочий сбой подготовки гейта на `verifying` — непрочитанное дерево коммита отчёта головы, исключение при чтении — задача сразу в `escalated` с причиной дословно.

    Сценарий (по случаю): CI, отчёты головы и базы зелёные; (а) git в
    кадрах гейта отказывает `ls-tree` дерева коммита головы (stderr
    «сбой git сценария»); (б) чтение отчёта хостинга бросает
    `RuntimeError` со случайным словом. Опрос при огромном потолке:
    `escalated`, не `review`, не `in_dev`; запись перехода несёт текст
    сбоя (stderr git либо слово исключения).

    Ловит мутацию: прочий сбой подготовки — ожидание (задача в
    `verifying`) или пропуск гейта (`review`); причина эскалации без
    текста сбоя.
    """
    project = box.project()
    comp = project.comps[0]
    t = box.new_task(project)
    box.to_verifying(t)
    box.ci_reports(t, {})
    if failure == "дерево отчёта":
        head = t.sent
        box.fail_git = lambda args: "ls-tree" in args and head in args
        words = ["сбой git сценария"]
    else:
        box.forge.explode = f"обрыв {box.word()}"
        words = [box.forge.explode]
    rows, output = box.poll(t)
    detail = escalated_now(box, t, rows, output)
    assert all(w in detail for w in words), box.why(rows, output)


# ---------------------------------------------------------------- AC-9


def test_ac9_gate_reads_squashed_pushed_head_not_role_commit(box):
    """Проект со сжатием: гейт на `verifying` читает отчёт сжатого отправленного коммита, а не коммита роли.

    Сценарий: запись проекта с `squash_before_mr: true`; роль делает два
    коммита кода; выход из `in_dev` сжимает ветку — голова (`t.sent`)
    отличается от последнего коммита роли. Зелёные задания `ci_job` с
    одинаковыми зелёными отчётами есть и у сжатой головы, и у коммита
    роли; отчёт базы зелёный. Опрос: задача в `review`; шпион чтения
    `job_test_report` видел sha сжатой головы и не видел sha коммита роли.

    Ловит мутацию: голова гейта — коммит роли (последний коммит до
    сжатия, например sha из записи шага) — шпион видит sha коммита роли.
    """
    project = box.project(squash=True)
    comp = project.comps[0]
    t = box.new_task(project)
    t.zones = "app.py, lib/"
    box.commit_code(t, {f"lib/a{box.word()}.py": "A = 1\n"}, "первый коммит роли")
    role = []
    box.to_verifying(t, before=lambda: role.append(box.head(t)))
    assert role and t.sent != role[0], box.note(f"ветка не сжата: {role} {t.sent}")
    box.ci_reports(t, {})
    box.publish(role[0], comp.job, "success", box.green(comp))
    rows, output = box.poll(t)
    assert box.state(t) == "review", box.why(rows, output)
    reads = box.report_reads()
    assert t.sent in reads, box.why(rows, output)
    assert role[0] not in reads, box.why(rows, output)


def test_ac9_gate_reads_new_head_after_pull_main(box):
    """После подтяжки main на `verifying` (`pull-main`) и зелёного CI новой головы гейт читает отчёт новой отправленной головы, а не sha, отправленного на входе в `verifying`.

    Сценарий: задача в `verifying` с головой H1 (зелёные отчёты `ci_job`
    у H1 и её базы опубликованы); `main` проекта ушёл вперёд; Оператор
    подтягивает main командой `pull-main` — голова ветки H2 ≠ H1, задача
    по-прежнему в `verifying`. Зелёные задания и отчёты у H2 и новой
    базы (`diff_base`). Опрос: задача в `review`; шпион чтения
    `job_test_report` видел H2 и не видел H1.

    Ловит мутацию: голова гейта — sha, отправленный на входе в
    `verifying` (из записи отправки) — шпион видит H1.
    """
    project = box.project()
    comp = project.comps[0]
    t = box.new_task(project)
    box.to_verifying(t)
    first = t.sent
    box.ci_reports(t, {})
    box.main_commit(project)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            pull_main.cmd_pull_main(t.id)
        except SystemExit as exc:
            buf.write(f"\nSystemExit: {exc.code}")
    assert box.state(t) == "verifying", box.note(buf.getvalue())
    t.sent = box.head(t)
    assert t.sent != first, box.note(f"main не подтянут: {buf.getvalue()}")
    box.ci_reports(t, {})
    rows, output = box.poll(t)
    assert box.state(t) == "review", box.why(rows, output)
    reads = box.report_reads()
    assert t.sent in reads, box.why(rows, output)
    assert first not in reads, box.why(rows, output)


# ---------------------------------------------------------------- AC-10


def test_ac10_restart_during_read_waits_on_verifying(box):
    """Задание `ci_job` головы перезапущено между чтением годности и чтением отчёта — на `verifying` ожидание с причиной «перезапущено во время чтения», по потолку — `escalated` с ней же.

    Сценарий: CI, отчёты головы и базы зелёные, но каждое чтение отчёта
    головы порождает новую попытку задания (номер до и после чтения
    различается). Первый опрос при огромном потолке: задача в
    `verifying`, ни `review`, ни `in_dev`, ни `escalated`, ни прохода
    гейта; запись опроса — «перезапущено во время чтения». Второй опрос
    при потолке 0: `escalated`, запись перехода — та же причина.

    Ловит мутацию: проверка номера попытки снята — сравнение по отчёту
    другой попытки, `review`; перезапуск — эскалация сразу.
    """
    project = box.project()
    comp = project.comps[0]
    t = box.new_task(project)
    box.to_verifying(t)
    box.ci_reports(t, {})
    box.forge.restart.add((t.sent, comp.job))
    rows, output = box.poll(t)
    waits(box, t, rows, output, [RESTARTED])
    escalates_at_ceiling(box, t, [RESTARTED])


def test_ac10_restart_during_read_on_merge_gate_is_prepare_failure(box):
    """На гейте мержа перезапуск задания `ci_job` головы во время чтения — сбой подготовки «перезапущено во время чтения», не сравнение.

    Сценарий: задача сразу на `merge_gate`; отчёты головы и точки
    ответвления зелёные, чтение отчёта головы порождает новую попытку
    задания. `merge_gate_escalates`: запись `MERGE_PREPARE_ACTION` с
    «перезапущено во время чтения», выход `SystemExit`, задача на
    `merge_gate`, записи прохода нет.

    Ловит мутацию: проверка номера попытки снята в общем ядре — гейт
    мержа пройден (запись прохода, итог `False`).
    """
    project = box.project()
    comp = project.comps[0]
    t = box.direct_task(project, "merge_gate", {})
    head = box.head(t)
    main = box.origin_main(t)
    base = box.merge_base(t, main)
    box.publish(base, comp.job, "success", box.green(comp))
    box.publish(head, comp.job, "success", box.green(comp))
    box.forge.restart.add((head, comp.job))
    before = len(store.task_steps(box.conn, t.id))
    buf, exited = io.StringIO(), None
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            outcome_integrity.merge_gate_escalates(box.conn, t.id, "merge_gate",
                                                   lambda: main)
        except SystemExit as exc:
            exited = exc
    rows = [dict(r) for r in store.task_steps(box.conn, t.id)[before:]]
    found = box.details(rows, MERGE_PREPARE)
    assert exited is not None, box.why(rows, buf.getvalue())
    assert found and RESTARTED in found[-1], box.why(rows, buf.getvalue())
    assert box.state(t) == "merge_gate", box.why(rows, buf.getvalue())
    assert PASSED not in box.actions(rows), box.why(rows, buf.getvalue())


# ---------------------------------------------------------------- AC-11


@pytest.mark.parametrize("case", ["находка", "нет задания головы", "чисто"])
def test_ac11_review_reached_only_through_verifying_gate(box, case):
    """Переход `verifying → review` для `ci` — только через проход гейта по исходам на `verifying`: при зелёном CI без прохода гейта задача в `review` не попадает, а попавшая — после записи прохода для текущей головы.

    Сценарий (по случаю): задача `full_suite: ci` в `verifying`, CI
    головы зелёный; (а) отчёт головы красен по одному тесту; (б) задания
    `ci_job` у головы нет (только `lint`); (в) отчёты головы и базы
    чисты. Опрос: в (а) и (б) записи `state -> review` нет и задача не в
    `review`; в (в) задача в `review`, и раньше записи `state -> review`
    стоит запись `PASSED_ACTION`, строка доказательства которой
    (`proof_fields`) называет головой текущую отправленную голову.

    Ловит мутацию: гейт на `verifying` не вызван — зелёный CI ведёт в
    `review` в (а) и (б); проход гейта записан не для текущей головы.
    """
    project = box.project()
    comp = project.comps[0]
    t = box.new_task(project)
    box.to_verifying(t)
    if case == "нет задания головы":
        box.publish(box.base(t), comp.job, "success", box.green(comp))
        box.jobs_of(t.sent)
    else:
        red = box.red(comp, box.rng.choice(comp.names))
        box.ci_reports(t, {comp.comp: red} if case == "находка" else {})
    rows, output = box.poll(t)
    if case != "чисто":
        assert TO_REVIEW not in box.actions(rows), box.why(rows, output)
        assert box.state(t) != "review", box.why(rows, output)
        return
    assert box.state(t) == "review", box.why(rows, output)
    actions = box.actions(rows)
    passed_at = [i for i, r in enumerate(rows) if r["action"] == PASSED
                 and (outcome_integrity.proof_fields(r["detail"]) or ("",))[0]
                 == t.sent]
    assert passed_at and passed_at[-1] < actions.index(TO_REVIEW), \
        box.why(rows, output)


# ---------------------------------------------------------------- AC-12


def test_ac12_finding_in_second_ci_component_returns_to_in_dev(box):
    """Запись из двух компонентов `full_suite: ci`: первый без расхождений, во втором тест зелёный в базе и красный в голове — задача в `in_dev`, находка названа с именем второго компонента.

    Сценарий: запись проекта из двух компонентов `ci` (`paths`
    `^<a>/` и `^<b>/`, у каждого своё задание `ci_job`); задача на первый
    компонент правит `app.py` вне компонентов — гейт судит оба. Отчёты
    первого компонента чисты; во втором один тест красен в голове.
    Опрос `verifying`: задача в `in_dev`; деталь отказа «сломан правкой»
    называет второй компонент и идентификатор его теста.

    Ловит мутацию: на `verifying` судится только первый компонент (или
    только компонент задачи) — задача в `review`; первый чистый компонент
    останавливает перебор.
    """
    project = box.multi(["ci", "ci"])
    first, second = project.comps
    red = box.rng.choice(second.names)
    t = box.new_task(project)
    box.to_verifying(t)
    box.ci_reports(t, {second.comp: box.red(second, red)})
    rows, output = box.poll(t)
    detail = returned(box, t, rows, output)
    assert second.comp in detail, box.why(rows, output)
    assert f"{BROKEN}: {box.cid(second, red)} — " in detail, box.why(rows, output)


# ---------------------------------------------------------------- AC-13


@pytest.mark.parametrize("case", ["локальный отказ", "отказ CI", "обе зелёные"])
def test_ac13_both_component_local_on_in_dev_ci_on_verifying(box, case):
    """Компонент `both`: локальная часть гейта — на `in_dev`, как сейчас; часть по отчётам CI — на `verifying`; `review` — только когда обе зелёные.

    Сценарий (по случаю): проект с компонентом `full_suite: both`; (а)
    тест локально красен на голове все три прогона — `advance` из
    `in_dev`: отказ «сломан правкой» с его идентификатором, выписки
    сделаны, задача в `in_dev`; (б) локально всё зелёно — задача в
    `verifying`, отчёт CI головы красен по тесту — опрос возвращает в
    `in_dev` с находкой; (в) локально и в CI всё зелёно — опрос ведёт в
    `review`.

    Ловит мутацию: `both` на `in_dev` судится как `ci` (локальная часть
    пропущена) — в (а) задача уходит в `verifying`; часть CI у `both` на
    `verifying` не судится — в (б) задача в `review`.
    """
    project = box.project(mode="both")
    comp = project.comps[0]
    red = box.rng.choice(comp.names)
    if case == "локальный отказ":
        box.cases[(comp.rel, red)] = {"base": ["passed"], "head": ["failed"]}
    t = box.new_task(project)
    rows, output = box.develop(t)
    if case == "локальный отказ":
        assert box.state(t) == "in_dev", box.why(rows, output)
        found = box.details(rows, BROKEN_ACTION)
        assert found and box.cid(comp, red) in found[-1], box.why(rows, output)
        assert box.checkouts, box.why(rows, output)
        return
    assert box.state(t) == "verifying", box.why(rows, output)
    assert box.checkouts, box.why(rows, output)
    heads = {comp.comp: box.red(comp, red)} if case == "отказ CI" else {}
    box.ci_reports(t, heads)
    rows, output = box.poll(t)
    if case == "отказ CI":
        detail = returned(box, t, rows, output)
        assert f"{BROKEN}: {box.cid(comp, red)} — " in detail, box.why(rows, output)
        return
    assert box.state(t) == "review", box.why(rows, output)


# ---------------------------------------------------------------- AC-15


@pytest.mark.parametrize("case", ["отказ на in_dev", "verifying без отчётов"])
def test_ac15_local_component_keeps_in_dev_gate(box, case):
    """Компонент `local` (по умолчанию): гейт по исходам — на `in_dev` локальными выписками, как прежде; на `verifying` отчёты CI не читаются и зелёный CI ведёт в `review`.

    Сценарий (по случаю): проект с компонентом без `full_suite` (режим
    `local`); (а) тест локально красен на голове — `advance` из `in_dev`:
    отказ «сломан правкой» тем же действием, выписки сделаны, задача в
    `in_dev`; (б) локально всё зелёно — задача в `verifying`, CI головы
    зелёный (`lint`) — опрос ведёт в `review` без единого чтения
    `job_test_report`.

    Ловит мутацию: пропуск гейта `in_dev` распространён на все компоненты
    с отчётом — в (а) задача уходит в `verifying`; гейт на `verifying`
    судит и `local` — в (б) чтение отчёта и ожидание или эскалация вместо
    `review`.
    """
    project = box.project(mode="local")
    comp = project.comps[0]
    red = box.rng.choice(comp.names)
    if case == "отказ на in_dev":
        box.cases[(comp.rel, red)] = {"base": ["passed"], "head": ["failed"]}
    t = box.new_task(project)
    rows, output = box.develop(t)
    assert box.checkouts, box.why(rows, output)
    if case == "отказ на in_dev":
        assert box.state(t) == "in_dev", box.why(rows, output)
        found = box.details(rows, BROKEN_ACTION)
        assert found and box.cid(comp, red) in found[-1], box.why(rows, output)
        return
    assert box.state(t) == "verifying", box.why(rows, output)
    box.jobs_of(t.sent)
    rows, output = box.poll(t)
    assert box.state(t) == "review", box.why(rows, output)
    assert box.report_reads() == [], box.why(rows, output)


# ---------------------------------------------------------------- AC-16


@pytest.mark.parametrize("case", ["находка local", "находка ci"])
def test_ac16_local_and_ci_components_split_between_in_dev_and_verifying(
        box, case):
    """Запись с компонентами `local` и `full_suite: ci`: находка `local` — отказ на `in_dev`, задача не уходит в `verifying`; находка `ci` при чистом `local` — уход в `verifying` и возврат из него в `in_dev`.

    Сценарий (по случаю): запись проекта из компонентов `local` (первый,
    задача на него) и `ci`; задача правит `app.py` вне компонентов —
    гейт судит оба. (а) Тест `local` локально красен на голове —
    `advance` из `in_dev`: отказ «сломан правкой» с его идентификатором,
    задача в `in_dev`, записи `state -> verifying` нет. (б) `local`
    чист — задача в `verifying`; отчёт CI головы `ci` красен по тесту —
    опрос возвращает в `in_dev` с находкой этого теста.

    Ловит мутацию: при наличии компонента `ci` в записи пропущен весь
    гейт `in_dev` — в (а) задача уходит в `verifying`; `ci` той же записи
    не судится на `verifying` — в (б) `review`.
    """
    project = box.multi(["local", "ci"])
    local, remote = project.comps
    t = box.new_task(project)
    if case == "находка local":
        red = box.rng.choice(local.names)
        box.cases[(local.rel, red)] = {"base": ["passed"], "head": ["failed"]}
        rows, output = box.develop(t)
        assert box.state(t) == "in_dev", box.why(rows, output)
        assert TO_VERIFYING not in box.actions(rows), box.why(rows, output)
        found = box.details(rows, BROKEN_ACTION)
        assert found and box.cid(local, red) in found[-1], box.why(rows, output)
        return
    red = box.rng.choice(remote.names)
    box.to_verifying(t)
    box.ci_reports(t, {remote.comp: box.red(remote, red)})
    rows, output = box.poll(t)
    detail = returned(box, t, rows, output)
    assert f"{BROKEN}: {box.cid(remote, red)} — " in detail, box.why(rows, output)


# ---------------------------------------------------------------- AC-17


def test_ac17_operator_class_finding_escalates_from_verifying(box):
    """Тест зелёный в отчёте базы и пропавший в отчёте головы (класс «чинит Оператор») без мандата — задача из `verifying` сразу в `escalated` с находкой тем же действием и текстом, что у отказа на `in_dev`; ни `in_dev`, ни `review`.

    Сценарий: задача `ci` в `verifying`; в отчёте головы нет одного
    случайного теста базы, остальные зелёные. Опрос: `escalated`; в
    записях опроса — действие `OUTCOME_INTEGRITY_REFUSAL_ACTION` со
    строкой «исчез: <id> — база: …»; переходов в `in_dev` и `review` нет.

    Ловит мутацию: находка класса «чинит Оператор» возвращает задачу в
    `in_dev`; находка записана другим действием (например, «сломан
    правкой») или исчезновение не находка — `review`.
    """
    project = box.project()
    comp = project.comps[0]
    gone = box.rng.choice(comp.names)
    t = box.new_task(project)
    box.to_verifying(t)
    head = box.green(comp, [n for n in comp.names if n != gone])
    box.ci_reports(t, {comp.comp: head})
    rows, output = box.poll(t)
    escalated_now(box, t, rows, output)
    found = box.details(rows, OPERATOR_ACTION)
    assert found and f"{GONE}: {box.cid(comp, gone)} — база: " in found[-1], \
        box.why(rows, output)


# ---------------------------------------------------------------- AC-18


def second_visit(box, t, comp, head) -> tuple:
    """Шаг `developer` после возврата, снова `verifying`, зелёный CI новой
    головы с отчётом `head`; опрос — (записи, вывод)."""
    box.to_verifying(t, {f"lib/f{box.word()}.py": f"FIX = '{box.word()}'\n"})
    box.ci_reports(t, {comp.comp: head})
    return box.poll(t)


def test_ac18_same_findings_after_developer_step_is_repeat(box):
    """Тот же набор находок после возврата, шага `developer` и нового `verifying` — эскалация с причиной «повтор находки гейта по исходам», второго возврата в `in_dev` нет.

    Сценарий AC-3: возврат в `in_dev` по красному тесту X. Шаг
    `developer` (новый коммит), задача снова в `verifying`, CI новой
    головы зелёный, отчёт головы снова красен ровно по X. Опрос:
    `escalated`, запись перехода — «повтор находки гейта по исходам»;
    записи `state -> in_dev` в опросе нет.

    Ловит мутацию: поиск предыдущего отказа обрывается на записи
    `state -> …` (возврат `verifying → in_dev` её пишет) — повтор не
    узнан, эскалация по пределу возвратов с другой причиной; правило
    повтора не работает на `verifying` — второй возврат в `in_dev`.
    """
    t, comp, red, _detail, _rows, _output = first_return(box)
    rows, output = second_visit(box, t, comp, box.red(comp, red))
    detail = escalated_now(box, t, rows, output)
    assert REPEAT in detail, box.why(rows, output)


# ---------------------------------------------------------------- AC-19


def test_ac19_other_findings_on_second_visit_hit_return_limit(box):
    """Чередование наборов X → Y: после первого возврата по X и шага `developer` другой набор Y «сломан правкой» — эскалация с причиной «предел возвратов гейта по исходам», второго возврата в `in_dev` нет.

    Сценарий AC-3 с тестом X: возврат в `in_dev`. Шаг `developer`, задача
    снова в `verifying`, CI новой головы зелёный; в отчёте головы X
    зелёный, красен другой тест Y. Опрос: `escalated`, запись перехода —
    «предел возвратов гейта по исходам»; записи `state -> in_dev` в
    опросе нет.

    Ловит мутацию: предел возвратов не проверяется — эскалирует только
    тот же набор, а другой набор даёт второй возврат в `in_dev`; счёт
    возвратов по визиту состояния, а не по истории задачи.
    """
    project = box.project(n=4)
    comp = project.comps[0]
    x, y = box.rng.sample(comp.names, 2)
    t, comp, _red, _detail, _rows, _output = first_return(box, project, comp, x)
    rows, output = second_visit(box, t, comp, box.red(comp, y))
    detail = escalated_now(box, t, rows, output)
    assert LIMIT in detail, box.why(rows, output)
