"""Гейт неослабления по исходам на гейте мержа для компонента `full_suite: ci`: исходы базы и головы — из отчётов задания CI `ci_job`.

Группа: долгоживущий
Красен до реализации: запись компонента с полями `full_suite: ci`/`ci_job` не грузится (их вводит часть 1), а гейт исходов мержа не читает отчётов задания CI — `merge_gate_escalates` судит по локальным выпискам либо вне границы возвращает `False` без записей; AC-9 (локальные выписки на `in_dev`) красен только на загрузке записи.

Стенд — песочница гейта исходов мержа
(`tests.merge_outcome_sandbox.MergeOutcomeSandbox` поверх
`tests.outcome_gate_sandbox.OutcomeGateSandbox`): настоящий git, учебный
внешний проект `forge: gitlab` с компонентом `junit-xml`,
`full_suite: ci` и `ci_job`, раннер подменён шпионом `subprocess.Popen`
(локальный прогон — запись в `runs`), полный набор — шпионом
`acceptance.full_suite` (`suite_calls`). Шпион `subprocess.run` в кадрах
модулей гейта записывает выписки (`worktree add`) и чтения файлов
блокировки (`ls-tree` с именем файла блокировки); в AC-11 чтение файла
блокировки ещё и отказывает, как отказал бы недоступный git.

Хостинг подменён целиком: реестр `forge.IMPLEMENTATIONS` под ключом
`gitlab` указывает на хостинг сценария `FakeForge` — его `pipeline_status`
отдаёт задания коммита (имя, статус, `id`, `allow_failure`), `job_result` —
статус последней попытки задания, `job_test_report` — отчёт
`<classname>::<name>` → статус GitLab; каждое чтение записывается вместе с
признаком «из кадров гейта». Прочие функции интерфейса отвечают отказом и
тоже записываются.

Гейт мержа зовётся напрямую — `outcome_integrity.merge_gate_escalates`
задачи на `merge_gate` с `main_sha_of`, отдающим sha `origin/main`
проекта: `approve` хостинга `gitlab` пульт пока не ведёт
(`targets.SUPPORTED_FORGES`). Сбой подготовки — запись
`MERGE_PREPARE_ACTION` и выход `SystemExit` (задача остаётся на
`merge_gate`, вызывающий не идёт к отправке), отказ — запись
`MERGE_REFUSAL_ACTION`, `escalated` и `True`, проход — `False`.

Имена проектов, компонентов, файлов, тестов, заданий и `id` заданий — из
`random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
поля `full_suite`/`ci_job` компонента и режим `ci` гейта мержа — все
методы файла зелёные; мутации стаба «самый короткий префикс», «ключ без
имени компонента», «неоднозначная запись базы выпадает», «неизвестно в
голове — совпадение», «`workdir` не учтён», «отчёт головы от родителя»,
«`error` не красный», «родитель базы без сверки дерева», «режим `ci` и на
`in_dev`», «без находок G3б-2», «`id` первой попытки» красят свои методы.
"""
import contextlib
import io
import re
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import acceptance, config, forge, project_profile, store
from orchestrator.advance_gates import mandate, outcome_integrity
from orchestrator.reporters import outcome
from scripts import guard
from tests.fixtures import _sandbox
from tests.merge_outcome_sandbox import MergeOutcomeSandbox
from tests.outcome_gate_sandbox import ENTRY_HEAD, flow, py_source
from tests.sandbox import make_project_repo

MERGE_REFUSAL = outcome_integrity.MERGE_REFUSAL_ACTION
MERGE_PREPARE = outcome_integrity.MERGE_PREPARE_ACTION
PASSED = outcome_integrity.PASSED_ACTION
BROKEN_ACTION = outcome_integrity.BROKEN_REFUSAL_ACTION
BROKEN = outcome_integrity.BROKEN
GONE = outcome_integrity.GONE
BECAME_SKIPPED = outcome_integrity.BECAME_SKIPPED
STRICT_EDIT = outcome_integrity.STRICT_EDIT
CODE_EXCEPTION = outcome_integrity.CODE_EXCEPTION
REPLACED_MISSING = outcome_integrity.REPLACED_MISSING
REPLACED_NOT_GREEN = outcome_integrity.REPLACED_NOT_GREEN

NO_BASE_REPORT = "нет отчёта базы"
BASE_AMBIGUOUS = "отчёт базы неоднозначен: "
REPLACEMENT_UNCHECKABLE = "замена теста не проверяема в режиме ci"
BASE_FROM_PARENT = re.compile(r"отчёт базы: задание (\d+) коммита ([0-9a-f]{7,40}) "
                              r"\(дерево совпадает с ([0-9a-f]{7,40})\)")
COVERED_BY = "покрыто мандатом "
READS = ("pipeline_status", "job_result", "job_test_report")
OTHER_JOB = "lint"
STRANGE_STATUS = "unknown"

# Вердикт `pipeline_status` по статусу задания сценария — для правдоподобия
# ответа; гейт по ТЗ судит статус задания и `allow_failure`.
VERDICTS = {"success": forge.GREEN, "failed": forge.RED,
            "running": forge.RUNNING, "pending": forge.RUNNING,
            "created": forge.RUNNING}


class FakeForge:
    """Хостинг сценария под ключом `gitlab` реестра `forge.IMPLEMENTATIONS`:
    задания и отчёты по sha, каждое чтение — в `calls`."""

    CI_BY_PIPELINE = True

    def __init__(self, box):
        self.box = box
        self.jobs: dict = {}
        self.reports: dict = {}
        self.calls: list = []
        self.other: list = []

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
        verdict = forge.senior(VERDICTS.get(j.status, forge.UNKNOWN)
                               for j in jobs if not j.allow_failure)
        return forge.PipelineStatus(verdict, "", jobs)

    def job_result(self, target, sha, job_name):
        self.record("job_result", sha)
        job = self.last(sha, job_name)
        if job is None:
            return forge.JobResult(None, f"задания {job_name} у {sha[:8]} нет")
        return forge.JobResult(job.status, "")

    def job_test_report(self, target, sha, job_name):
        self.record("job_test_report", sha)
        if self.last(sha, job_name) is None:
            return forge.TestReport(None, f"задания {job_name} у {sha[:8]} нет")
        report = self.reports.get((sha, job_name))
        if report is None:
            return forge.TestReport(None, "отчёт не разобран (сценарий)")
        return forge.TestReport(dict(report), "")

    def __getattr__(self, name):
        if name not in forge.RESULT_TYPES:
            raise AttributeError(name)

        def call(*args):
            self.other.append((name, args))
            return forge.RESULT_TYPES[name](reason=f"{name}: не дано сценарием")
        return call


class CiGateBox(MergeOutcomeSandbox):
    """Песочница гейта исходов мержа с хостингом сценария и шпионом выписок
    и чтений файлов блокировки в кадрах гейта."""

    def setUp(self):
        super().setUp()
        self.forge = FakeForge(self)
        patcher = mock.patch.dict(forge.IMPLEMENTATIONS, {"gitlab": self.forge})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.checkouts: list = []
        self.lock_reads: list = []
        self.ids_used: set = set()
        self.fail_locks = False
        self.git_fail = self.watch_git

    def watch_git(self, args: tuple) -> bool:
        if "worktree" in args and "add" in args:
            self.checkouts.append(args)
        locks = set(acceptance.LOCK_FILE_NAMES)
        if "ls-tree" in args and any(a.rsplit("/", 1)[-1] in locks for a in args):
            self.lock_reads.append(args)
            return self.fail_locks
        return False

    # --- проекты и задачи -----------------------------------------------

    def component_fields(self, job: str, scope: str, layers=None,
                         workdir: str = "") -> dict:
        fields = {"command": flow([str(self.pytest_cmd)]),
                  "report": "junit-xml",
                  "long_lived_dir": f"{workdir}/tests" if workdir else "tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": flow([scope]),
                  "mutation_claim_scope": flow([scope]),
                  "failure_errors": flow(["AssertionError"]),
                  "plank_layout": f".pg{self.word(5)}/<id>",
                  "full_suite": "ci",
                  "ci_job": job}
        if workdir:
            fields.update(runner="pytest-own", workdir=workdir)
        if layers is not None:
            fields["layers"] = flow(layers)
        return fields

    def ci_project(self, files: dict, layers=None,
                   workdir: str = "") -> SimpleNamespace:
        """Учебный проект `forge: gitlab` с единственным компонентом
        `full_suite: ci`; `files` — {путь от корня: текст} базы."""
        name, comp, job = f"g{self.word()}", f"c{self.word()}", f"t{self.word()}"
        scope = f"{workdir}/tests/**" if workdir else "tests/**"
        fields = self.component_fields(job, scope, layers, workdir)
        lines = [ENTRY_HEAD.format(name=name).replace("forge: github",
                                                      "forge: gitlab"),
                 "    components:\n", f"      {comp}:\n"]
        lines += [f"        {k}: {v}\n" for k, v in fields.items()]
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        self.commit_project(clone, {"app.py": "APP = 'base'\n", **files})
        self.clones[name] = clone
        return SimpleNamespace(name=name, comp=comp, job=job, clone=clone,
                               workdir=workdir, kind="junit", layout="")

    def scenario(self, n: int = 3, layers=None, extra: dict | None = None):
        """(проект, путь файла тестов, имена) — файл с `n` функциями."""
        rel = self.py_rel()
        names = [self.py_name() for _ in range(n)]
        project = self.ci_project({rel: py_source(names), **(extra or {})},
                                  layers=layers)
        return project, rel, names

    def merge_task(self, project, changes: dict | None = None,
                   empty_head: bool = False):
        """Задача проекта сразу на `merge_gate`; `empty_head` — сверх правки
        пустой коммит (дерево головы = дерево её родителя)."""
        t = self.direct_task(project, "merge_gate", changes)
        if empty_head:
            self.git("-C", str(t.wt), "commit", "-q", "--allow-empty", "-m",
                     "пустой коммит головы")
        t.main = self.origin_main(t)
        t.head = self.head(t)
        t.base = self.merge_base(t, t.main)
        return t

    def empty_main_commit(self, project) -> None:
        """Пустой коммит на `main` проекта: дерево точки ответвления
        совпадает с деревом её родителя."""
        self.git("-C", str(project.clone), "commit", "-q", "--allow-empty",
                 "-m", "пустой коммит main")
        self.git("-C", str(project.clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def tree(self, t, sha: str) -> str:
        return self.rev(t, f"{sha}^{{tree}}")

    # --- отчёты ---------------------------------------------------------

    def job_id(self) -> int:
        while True:
            value = self.rng.randrange(10 ** 5, 10 ** 9)
            if value not in self.ids_used:
                self.ids_used.add(value)
                return value

    def publish(self, sha: str, job: str, status: str, report,
                allow_failure: bool = False, attempts: int = 1) -> int:
        """Задание `job` коммита `sha` (последняя попытка — `status`,
        прежние — `failed`) и его отчёт; `id` последней попытки."""
        ids = sorted(self.job_id() for _ in range(attempts))
        jobs = self.jobs_of(sha)
        for value in ids[:-1]:
            jobs.append(forge.Job(job, "failed", "test", value, False))
        jobs.append(forge.Job(job, status, "test", ids[-1], allow_failure))
        self.forge.reports[(sha, job)] = report
        return ids[-1]

    def jobs_of(self, sha: str) -> list:
        jobs = self.forge.jobs.setdefault(sha, [])
        if not jobs:
            jobs.append(forge.Job(OTHER_JOB, "success", "lint", self.job_id(),
                                  False))
        return jobs

    @staticmethod
    def key(rel: str, full: str) -> str:
        """Ключ отчёта GitLab `<classname>::<name>` теста `full` файла `rel`
        (путь от рабочего каталога компонента): `classname` — точечный путь
        модуля и классов."""
        module = rel[:-len(".py")].replace("/", ".")
        klass, _sep, name = full.rpartition("::")
        classname = f"{module}.{klass.replace('::', '.')}" if klass else module
        return f"{classname}::{name}"

    def green(self, rel: str, names) -> dict:
        return {self.key(rel, n): "success" for n in names}

    @staticmethod
    def cid(project, rel: str, full: str) -> str:
        return project_profile.test_id(project.comp, rel, full)

    # --- прогон гейта ---------------------------------------------------

    def gate(self, t) -> SimpleNamespace:
        """Гейт исходов мержа задачи `t`: (итог, код выхода, новые записи,
        вывод, состояние, `origin/main` до и после)."""
        before = len(store.task_steps(self.conn, t.id))
        for spy in (self.runs, self.suite_calls, self.checkouts,
                    self.lock_reads, self.forge.calls, self.forge.other):
            spy.clear()
        main = self.origin_main(t)
        state = self.state(t)
        result, exited = None, None
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                result = outcome_integrity.merge_gate_escalates(
                    self.conn, t.id, state, lambda: main)
            except SystemExit as exc:
                exited = exc.code if exc.code is not None else ""
        rows = [dict(r) for r in store.task_steps(self.conn, t.id)[before:]]
        return SimpleNamespace(result=result, exited=exited, rows=rows,
                               output=buf.getvalue(), state=self.state(t),
                               main=main, main_after=self.origin_main(t))

    def why(self, run) -> str:
        return self.note(
            f"итог: {run.result!r}; выход: {run.exited!r}; состояние: "
            f"{run.state}\nзаписи: "
            f"{[(r['action'], r['detail']) for r in run.rows]}\n"
            f"вывод: {run.output[-2000:]}\nхостинг: {self.forge.calls}; "
            f"прочее: {self.forge.other}\nвыписки: {self.checkouts}; "
            f"файлы блокировки: {self.lock_reads}; запуски: "
            f"{[(r['side'], r['full']) for r in self.runs]}; полный набор: "
            f"{[c['side'] for c in self.suite_calls]}")

    def texts(self, rows: list) -> list:
        return [f"{r['action']} {r['detail'] or ''}" for r in rows]

    def gate_reads(self) -> list:
        return [(name, sha) for name, sha, in_gate in self.forge.calls
                if in_gate and name in READS]


@pytest.fixture
def box():
    """Стенд CiGateBox после setUp."""
    yield from _sandbox(CiGateBox)


def refused(box, run, case: str = "") -> str:
    """Деталь отказа гейта мержа: запись `MERGE_REFUSAL_ACTION`, `escalated`,
    итог `True`, записи сбоя подготовки нет."""
    found = box.details(run.rows, MERGE_REFUSAL)
    assert found, case + box.why(run)
    assert run.result is True and run.exited is None, case + box.why(run)
    assert run.state == "escalated", case + box.why(run)
    assert box.details(run.rows, MERGE_PREPARE) == [], case + box.why(run)
    return found[-1]


def prepare_failed(box, run, case: str = "") -> str:
    """Деталь сбоя подготовки: запись `MERGE_PREPARE_ACTION` с причиной,
    выход без пропуска, задача на `merge_gate`, отказа и отправки нет."""
    found = box.details(run.rows, MERGE_PREPARE)
    assert found and found[-1].strip(), case + box.why(run)
    assert run.exited is not None, case + box.why(run)
    assert run.state == "merge_gate", case + box.why(run)
    assert box.details(run.rows, MERGE_REFUSAL) == [], case + box.why(run)
    assert box.details(run.rows, PASSED) == [], case + box.why(run)
    assert run.main_after == run.main, case + box.why(run)
    return found[-1]


def passed(box, run, case: str = "") -> str:
    """Деталь записи пройденного гейта: итог `False`, без выхода и отказов."""
    assert run.result is False and run.exited is None, case + box.why(run)
    assert box.details(run.rows, MERGE_REFUSAL) == [], case + box.why(run)
    assert box.details(run.rows, MERGE_PREPARE) == [], case + box.why(run)
    found = box.details(run.rows, PASSED)
    assert found, case + box.why(run)
    return found[-1]


def no_local(box, run, case: str = "") -> None:
    """Ни выписки, ни перепрогона, ни полного набора, ни запуска раннера."""
    assert box.checkouts == [], case + box.why(run)
    assert box.runs == [], case + box.why(run)
    assert box.suite_calls == [], case + box.why(run)


def has_id(key: str, value: int) -> bool:
    return re.search(rf"(?<!\d){value}(?!\d)", key) is not None


# ---------------------------------------------------------------- AC-1


@pytest.mark.parametrize("head_outcome, head_job", [
    ("failed", "success"), ("error", "success"),
    ("failed", "failed"), ("error", "failed")])
def test_ac1_green_base_red_head_report_is_broken_without_checkouts(
        box, head_outcome, head_job):
    """Тест зелёный в отчёте базы и красный в отчёте головы — отказ гейта мержа с находкой «сломан правкой», `escalated`, без выписок и прогонов.

    Сценарий: компонент `full_suite: ci`; отчёт задания `ci_job` базы
    (точка ответвления) — все тесты `success`; в отчёте головы один
    случайный тест — `failed` либо `error`, задание головы завершено
    `success` либо `failed` без права падать (отчёт разобран). Гейт мержа:
    запись `MERGE_REFUSAL_ACTION` со строкой «сломан правкой: <id> — …»
    этого теста, задача `escalated`; шпион не видит ни `worktree add`, ни
    запуска раннера, ни полного набора.

    Ловит мутацию: гейт мержа `ci` по-прежнему делает выписки и
    гоняет полный набор (шпион видит `worktree add`/запуск); статус
    `error` отчёта не считается красным — находки нет, гейт пройден;
    задание головы `failed` без права падать признано негодным — сбой
    подготовки вместо отказа.
    """
    case = f"{head_outcome}/{head_job}: "
    project, rel, names = box.scenario()
    t = box.merge_task(project)
    report = box.green(rel, names)
    box.publish(t.base, project.job, "success", report)
    red = box.rng.choice(names)
    head = dict(report, **{box.key(rel, red): head_outcome})
    box.publish(t.head, project.job, head_job, head)
    run = box.gate(t)
    detail = refused(box, run, case)
    assert f"{BROKEN}: {box.cid(project, rel, red)} — " in detail, case + box.why(run)
    no_local(box, run, case)


def test_ac1_test_missing_in_head_report_is_refusal(box):
    """Тест зелёный в отчёте базы и отсутствующий в отчёте головы — отказ гейта мержа («исчез»), `escalated`, без выписок.

    Сценарий: отчёт головы — отчёт базы без одного случайного теста (файл
    теста в дереве головы не тронут). Гейт мержа: `MERGE_REFUSAL_ACTION`
    с находкой «исчез: <id> — …», `escalated`; выписок, прогонов и
    полного набора нет.

    Ловит мутацию: сравнение отчётов CI не ищет пропавших тестов
    (сравниваются только общие идентификаторы) — гейт пройден; пропавший
    тест засчитан зелёным — проход.
    """
    project, rel, names = box.scenario()
    t = box.merge_task(project)
    report = box.green(rel, names)
    box.publish(t.base, project.job, "success", report)
    gone = box.rng.choice(names)
    head = {k: v for k, v in report.items() if k != box.key(rel, gone)}
    box.publish(t.head, project.job, "success", head)
    run = box.gate(t)
    detail = refused(box, run)
    assert f"{GONE}: {box.cid(project, rel, gone)} — " in detail, box.why(run)
    no_local(box, run)


# ---------------------------------------------------------------- AC-2


@pytest.mark.parametrize("base_job", ["нет задания", "отчёт не разобран"])
def test_ac2_base_report_taken_from_parent_with_same_tree(box, base_job):
    """У точки ответвления нет задания `ci_job` с отчётом, у её родителя с тем же деревом отчёт есть — гейт сравнивает по отчёту родителя и пишет «отчёт базы: задание <id> коммита <sha> (дерево совпадает с <точка>)».

    Сценарий: на `main` проекта поверх коммита с файлами — пустой коммит
    (точка ответвления задачи), его родитель — с тем же деревом. У точки
    ответвления либо нет задания `ci_job` (только чужое задание), либо оно
    `success` с неразобранным отчётом. У родителя — две попытки `ci_job`,
    последняя `success`, отчёт: все тесты зелёные. В отчёте головы один
    тест красный. Гейт: отказ «сломан правкой: <id>» (сравнение шло по
    отчёту родителя), в записях журнала — строка «отчёт базы: задание
    <наибольший id> коммита <sha родителя> (дерево совпадает с <sha
    точки>)».

    Ловит мутацию: родитель с тем же деревом не ищется — сбой подготовки
    «нет отчёта базы» вместо отказа; запись не пишется или в ней `id`
    первой попытки вместо наибольшего; в записи перепутаны sha родителя
    и точки ответвления.
    """
    project, rel, names = box.scenario()
    box.empty_main_commit(project)
    t = box.merge_task(project)
    parent = box.rev(t, f"{t.base}^")
    assert box.tree(t, parent) == box.tree(t, t.base), box.note("стенд: деревья")
    report = box.green(rel, names)
    if base_job == "нет задания":
        box.jobs_of(t.base)
    else:
        box.publish(t.base, project.job, "success", None)
    job_id = box.publish(parent, project.job, "success", report, attempts=2)
    red = box.rng.choice(names)
    box.publish(t.head, project.job, "success",
                dict(report, **{box.key(rel, red): "failed"}))
    run = box.gate(t)
    detail = refused(box, run, base_job + ": ")
    assert f"{BROKEN}: {box.cid(project, rel, red)} — " in detail, box.why(run)
    found = [m for text in box.texts(run.rows)
             for m in BASE_FROM_PARENT.finditer(text)]
    assert found, base_job + ": " + box.why(run)
    assert any(m.group(1) == str(job_id) and parent.startswith(m.group(2))
               and t.base.startswith(m.group(3)) for m in found), (
        base_job + f": ожидалось задание {job_id} коммита {parent} (точка "
        f"{t.base})\n" + box.why(run))


# ---------------------------------------------------------------- AC-3


@pytest.mark.parametrize("base_case", [
    "нет задания", "running", "pending", "created", "canceled", "manual",
    "skipped", "failed с правом падать", "отчёт None",
    "родитель с другим деревом"])
def test_ac3_no_fit_base_report_is_prepare_failure(box, base_case):
    """Годного отчёта базы нет ни у точки ответвления, ни у родителя того же дерева — сбой подготовки «нет отчёта базы», задача на `merge_gate`, отправки нет.

    Сценарий (по случаю): отчёт головы годен и зелен. У точки ответвления
    задания `ci_job` нет; либо оно `running`/`pending`/`created`/
    `canceled`/`manual`/`skipped` (с разобранным зелёным отчётом); либо
    `failed` с правом падать; либо `success` с неразобранным отчётом;
    либо точки нет в CI вовсе, а родитель точки (дерево другое — первый
    пустой коммит проекта) несёт годный зелёный отчёт. Гейт: запись
    `MERGE_PREPARE_ACTION` с «нет отчёта базы», выход без пропуска,
    `merge_gate`, `origin/main` не сдвинут, записи отказа и прохода нет.

    Ловит мутацию: незавершённое, отменённое, ручное, пропущенное задание
    или задание с правом падать признано годным — гейт пройден; родитель
    взят без сверки дерева — проход по чужому отчёту; нет отчёта базы —
    пропуск гейта (`False`) или эскалация вместо сбоя подготовки.
    """
    case = base_case + ": "
    project, rel, names = box.scenario()
    t = box.merge_task(project)
    report = box.green(rel, names)
    box.publish(t.head, project.job, "success", report)
    if base_case == "нет задания":
        box.jobs_of(t.base)
    elif base_case == "failed с правом падать":
        box.publish(t.base, project.job, "failed", report, allow_failure=True)
    elif base_case == "отчёт None":
        box.publish(t.base, project.job, "success", None)
    elif base_case == "родитель с другим деревом":
        parent = box.rev(t, f"{t.base}^")
        assert box.tree(t, parent) != box.tree(t, t.base), box.note("стенд: деревья")
        box.publish(parent, project.job, "success", report)
    else:
        box.publish(t.base, project.job, base_case, report)
    run = box.gate(t)
    detail = prepare_failed(box, run, case)
    assert NO_BASE_REPORT in detail, case + box.why(run)


def test_ac3_failed_base_job_without_allow_failure_is_fit(box):
    """Задание базы `failed` без права падать с разобранным отчётом — отчёт годен: гейт сравнивает исходы по нему.

    Сценарий: в отчёте базы один тест `failed`, прочие `success`;
    задание базы — `failed` без права падать. Отчёт головы — тот же
    (красный тест красен и там). Гейт пройден: итог `False`, запись
    «гейт неослабления по исходам пройден», сбоя подготовки нет.

    Ловит мутацию: годным признан только `success` — сбой подготовки
    «нет отчёта базы» на честно упавшем задании базы.
    """
    project, rel, names = box.scenario()
    t = box.merge_task(project)
    report = dict(box.green(rel, names), **{box.key(rel, names[0]): "failed"})
    box.publish(t.base, project.job, "failed", report)
    box.publish(t.head, project.job, "failed", report)
    run = box.gate(t)
    passed(box, run)


# ---------------------------------------------------------------- AC-4


@pytest.mark.parametrize("head_case", [
    "нет задания", "running", "pending", "created", "canceled", "manual",
    "skipped", "failed с правом падать", "отчёт None",
    "родитель головы с тем же деревом"])
def test_ac4_no_fit_head_report_is_prepare_failure(box, head_case):
    """Годного отчёта головы нет — сбой подготовки с именованной причиной, задача на `merge_gate`, не пропуск и не эскалация.

    Сценарий (по случаю): отчёт базы годен и зелен. У головы задания
    `ci_job` нет; либо оно `running`/`pending`/`created`/`canceled`/
    `manual`/`skipped` (с разобранным зелёным отчётом); либо `failed` с
    правом падать; либо `success` с неразобранным отчётом; либо голова —
    пустой коммит без конвейера поверх коммита с тем же деревом, у
    которого годный зелёный отчёт есть. Гейт: запись
    `MERGE_PREPARE_ACTION` с непустой причиной, выход без пропуска,
    `merge_gate`, `origin/main` не сдвинут, отказа и прохода нет.

    Ловит мутацию: негодное задание головы признано годным — гейт
    пройден; отчёт головы подставлен от родителя с тем же деревом
    (правило базы применено к голове) — проход; нет отчёта головы —
    пропуск гейта или эскалация.
    """
    case = head_case + ": "
    project, rel, names = box.scenario()
    t = box.merge_task(project, empty_head=head_case.startswith("родитель"))
    report = box.green(rel, names)
    box.publish(t.base, project.job, "success", report)
    if head_case == "нет задания":
        box.jobs_of(t.head)
    elif head_case == "failed с правом падать":
        box.publish(t.head, project.job, "failed", report, allow_failure=True)
    elif head_case == "отчёт None":
        box.publish(t.head, project.job, "success", None)
    elif head_case.startswith("родитель"):
        parent = box.rev(t, f"{t.head}^")
        assert box.tree(t, parent) == box.tree(t, t.head), box.note("стенд: деревья")
        box.publish(parent, project.job, "success", report)
    else:
        box.publish(t.head, project.job, head_case, report)
    run = box.gate(t)
    prepare_failed(box, run, case)


# ---------------------------------------------------------------- AC-5


@pytest.mark.parametrize("replaced", ["нет в базе", "не зелёный", "зелёный"])
def test_ac5_approved_replacement_judged_by_base_report(box, replaced):
    """Утверждённая замена теста в режиме `ci`: нет в отчёте базы — REPLACED_MISSING, не зелёный — REPLACED_NOT_GREEN, зелёный — отказ «замена теста не проверяема в режиме ci»; без сбоя подготовки и без локального прогона.

    Сценарий (по случаю): журнал задачи несёт утверждение замены
    (`mandate.REPLACED_TESTS_ACTION`, пункт `guard.ReplacedTest`) теста
    компонента: (а) его нет в отчёте базы; (б) в отчёте базы он `failed`;
    (в) в отчёте базы он `success`. Отчёт головы — тот же, что базы.
    Гейт: запись `MERGE_REFUSAL_ACTION` — со строкой
    «заменяемый тест не найден в отчёте базы: <id>» / «заменяемый тест не
    зелёный на базе: <id>» / с причиной «замена теста не проверяема в
    режиме ci»; `escalated`; записи `MERGE_PREPARE_ACTION` нет; выписок,
    запусков раннера и полного набора нет.

    Ловит мутацию: зелёная замена идёт прежним путём третьей выписки —
    выписка и прогон либо сбой подготовки «прежняя версия … не прогнана»
    вместо отказа; REPLACED_MISSING/REPLACED_NOT_GREEN не выдаются в
    режиме `ci` — проход.
    """
    case = replaced + ": "
    project, rel, names = box.scenario()
    t = box.merge_task(project)
    report = box.green(rel, names)
    if replaced == "нет в базе":
        cid = box.cid(project, rel, box.py_name())
    else:
        cid = box.cid(project, rel, names[0])
        if replaced == "не зелёный":
            report[box.key(rel, names[0])] = "failed"
    box.publish(t.base, project.job, "success", report)
    box.publish(t.head, project.job, "success", report)
    store.journal(box.conn, t.id, "operator", mandate.REPLACED_TESTS_ACTION,
                  guard.ReplacedTest(cid, 1, f"замена {box.word()}").line)
    run = box.gate(t)
    detail = refused(box, run, case)
    wanted = {"нет в базе": f"{REPLACED_MISSING}: {cid}",
              "не зелёный": f"{REPLACED_NOT_GREEN}: {cid}",
              "зелёный": REPLACEMENT_UNCHECKABLE}[replaced]
    assert wanted in detail, case + box.why(run)
    no_local(box, run, case)


# ---------------------------------------------------------------- AC-6


def test_ac6_passed_record_does_not_prove_ci_gate(box):
    """Запись пройденного гейта с той же головой и базой не избавляет от сравнения: гейт заново читает отчёты базы и головы и сравнивает их.

    Сценарий: первый прогон гейта — отчёты зелёные, гейт пройден (запись
    `PASSED_ACTION`). Отчёт задания головы в CI сменился: один тест
    `failed`. Второй прогон гейта той же головы и базы: хостинг видит из
    кадров гейта `job_test_report` и головы, и точки ответвления; итог —
    отказ «сломан правкой: <id>», `escalated`; выписок нет.

    Ловит мутацию: в режиме `ci` оставлено доказательство `_proven` —
    второй прогон пишет «гейт исходов: доказан» без чтения отчётов и
    проходит.
    """
    project, rel, names = box.scenario()
    t = box.merge_task(project)
    report = box.green(rel, names)
    box.publish(t.base, project.job, "success", report)
    box.publish(t.head, project.job, "success", report)
    first = box.gate(t)
    passed(box, first, "первый прогон: ")
    red = box.rng.choice(names)
    box.forge.reports[(t.head, project.job)] = dict(
        report, **{box.key(rel, red): "failed"})
    run = box.gate(t)
    reads = box.gate_reads()
    assert ("job_test_report", t.head) in reads, box.why(run)
    assert ("job_test_report", t.base) in reads, box.why(run)
    detail = refused(box, run, "второй прогон: ")
    assert f"{BROKEN}: {box.cid(project, rel, red)} — " in detail, box.why(run)
    assert box.checkouts == [], box.why(run)


# ---------------------------------------------------------------- AC-7


def write_files(root: Path, files: dict) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def junit_ids(cases: list, component: str, workdir: str, files: dict) -> list:
    """Идентификаторы `outcome.parse_junit` отчёта JUnit без атрибута `file`
    (`cases` — (classname, name)) в каталоге с файлами `files` (пути от
    рабочего каталога компонента)."""
    holder = Path(tempfile.mkdtemp(prefix="artel-junit-")).resolve()
    try:
        write_files(holder, files)
        body = "".join(f'<testcase classname="{c}" name="{n}" time="0.01"/>'
                       for c, n in cases)
        report = holder / "report.xml"
        report.write_text('<?xml version="1.0" encoding="utf-8"?><testsuites>'
                          f'<testsuite name="pytest">{body}</testsuite>'
                          '</testsuites>', encoding="utf-8")
        records, reason = outcome.parse_junit(report, component, workdir, holder)
    finally:
        shutil.rmtree(holder, ignore_errors=True)
    return [r.id for r in records or []] or [f"не разобран: {reason}"]


def test_ac7_report_keys_translate_to_component_test_ids(box):
    """Ключи отчёта GitLab переводятся в идентификаторы `<компонент>:<путь>::<имя>` по правилу требования 8 и совпадают с локальным разбором JUnit.

    Сценарий: в базе файлы `tests/<a>.py`, `tests/<b>.py`, `tests/<c>.py` и
    `tests/<c>/<s>.py` (два префикса точечного пути — оба файлы),
    `tests/<d>.py`. Отчёт базы: `tests/<a>.py::<fa>` (classname с `/`),
    `tests.<b>.<K>::<fb1>` и `tests.<b>.<O>.<I>::<fb2>` (классы),
    `tests.<c>.<s>.<K2>::<fc>` (самый длинный префикс — `tests/<c>/<s>.py`),
    `tests.<d>::<fd>` и `tests.<d>::<keep>`; в отчёте головы — только
    `<keep>`. Гейт: отказ, в нём «исчез: <id> — » для каждого из пяти
    тестов с идентификаторами `…:tests/<a>.py::<fa>`,
    `…:tests/<b>.py::<K>::<fb1>`, `…:tests/<b>.py::<O>::<I>::<fb2>`,
    `…:tests/<c>/<s>.py::<K2>::<fc>`, `…:tests/<d>.py::<fd>`; те же
    тесты в отчёте JUnit без атрибута `file` дают в `parse_junit` те же
    идентификаторы.

    Ловит мутацию: `classname` с `/` разобран как точечный — модуль не
    найден, сбой подготовки; класс не отделён от модуля или точки класса
    не заменены на `::`; выбран самый короткий префикс (`tests/<c>.py`,
    имя `<s>::<K2>::<fc>`); ключ поделён по последнему `::`.
    """
    a, b, c, s, d = (f"test_{box.word()}" for _ in range(5))
    k, o, i, k2 = (f"K{box.word()}" for _ in range(4))
    fa, fb1, fb2, fc, fd, keep = (box.py_name() for _ in range(6))
    files = {f"tests/{a}.py": py_source([fa]),
             f"tests/{b}.py": f"class {k}:\n    pass\n\n\nclass {o}:\n    pass\n",
             f"tests/{c}.py": "VALUE = 1\n",
             f"tests/{c}/{s}.py": f"class {k2}:\n    pass\n",
             f"tests/{d}.py": py_source([fd, keep])}
    project = box.ci_project(files)
    t = box.merge_task(project)
    report = {f"tests/{a}.py::{fa}": "success",
              f"tests.{b}.{k}::{fb1}": "success",
              f"tests.{b}.{o}.{i}::{fb2}": "success",
              f"tests.{c}.{s}.{k2}::{fc}": "success",
              f"tests.{d}::{fd}": "success",
              f"tests.{d}::{keep}": "success"}
    box.publish(t.base, project.job, "success", report)
    box.publish(t.head, project.job, "success", {f"tests.{d}::{keep}": "success"})
    run = box.gate(t)
    detail = refused(box, run)
    wanted = [box.cid(project, f"tests/{a}.py", fa),
              box.cid(project, f"tests/{b}.py", f"{k}::{fb1}"),
              box.cid(project, f"tests/{b}.py", f"{o}::{i}::{fb2}"),
              box.cid(project, f"tests/{c}/{s}.py", f"{k2}::{fc}"),
              box.cid(project, f"tests/{d}.py", fd)]
    for cid in wanted:
        assert f"{GONE}: {cid} — " in detail, f"нет {cid}\n" + box.why(run)
    local = junit_ids([(f"tests.{b}.{k}", fb1), (f"tests.{c}.{s}.{k2}", fc),
                       (f"tests.{d}", fd)], project.comp, "", files)
    assert local == [wanted[1], wanted[3], wanted[4]], box.note(f"{local}")


def test_ac7_report_statuses_map_to_case_outcomes(box):
    """Статусы GitLab `success`/`failed`/`skipped`/`error` переводятся в `passed`/`failed`/`skipped`/`error` — видно по находкам сравнения.

    Сценарий: в отчёте базы тесты p1…p4 `success`, f1 `failed`, s1
    `skipped`; в отчёте головы p1 `success`, p2 `failed`, p3 `error`, p4
    `skipped`, f1 `failed`, s1 `skipped`. Гейт: отказ; «сломан правкой» у
    p2 и p3, «стал пропуском: <p4> — база: passed; ветка: skipped»;
    идентификаторов p1, f1, s1 в детали отказа нет.

    Ловит мутацию: `failed` базы переведён в `passed` — f1 в
    `PASS_TO_PASS`, находка «сломан правкой» у f1; `error` переведён в
    `skipped` — у p3 «стал пропуском» вместо «сломан правкой»; `skipped`
    переведён в `passed` — находки у p4 нет.
    """
    project, rel, names = box.scenario(n=6)
    p1, p2, p3, p4, f1, s1 = names
    t = box.merge_task(project)
    key = box.key
    base = {key(rel, p1): "success", key(rel, p2): "success",
            key(rel, p3): "success", key(rel, p4): "success",
            key(rel, f1): "failed", key(rel, s1): "skipped"}
    head = {key(rel, p1): "success", key(rel, p2): "failed",
            key(rel, p3): "error", key(rel, p4): "skipped",
            key(rel, f1): "failed", key(rel, s1): "skipped"}
    box.publish(t.base, project.job, "failed", base)
    box.publish(t.head, project.job, "failed", head)
    run = box.gate(t)
    detail = refused(box, run)
    cid = {n: box.cid(project, rel, n) for n in names}
    assert f"{BROKEN}: {cid[p2]} — " in detail, box.why(run)
    assert f"{BROKEN}: {cid[p3]} — " in detail, box.why(run)
    assert (f"{BECAME_SKIPPED}: {cid[p4]} — база: passed; ветка: skipped"
            in detail), box.why(run)
    for quiet in (p1, f1, s1):
        assert cid[quiet] not in detail, f"{quiet}\n" + box.why(run)


def test_ac7_workdir_module_searched_under_workdir_id_from_root(box):
    """Компонент с непустым `workdir`: модуль точечного `classname` ищется в дереве под `workdir`, путь идентификатора — от корня репозитория с префиксом `workdir`, как у локального разбора.

    Сценарий: компонент `workdir: <w>`; в базе файл `<w>/tests/<m>.py` и
    одноимённая приманка `tests/<m>.py` в корне. Отчёт базы:
    `tests.<m>::<f1>`, `tests.<m>.<K>::<f2>`, `tests/<m>.py::<f3>`,
    `tests.<m>::<keep>`; в отчёте головы — только `<keep>`. Гейт: отказ с
    «исчез: <id> — » для `…:<w>/tests/<m>.py::<f1>`,
    `…:<w>/tests/<m>.py::<K>::<f2>`, `…:<w>/tests/<m>.py::<f3>`; те же
    тесты в отчёте JUnit без `file` дают в `parse_junit` с тем же
    `workdir` те же идентификаторы.

    Ловит мутацию: модуль ищется от корня репозитория — найдена приманка,
    путь без префикса `<w>/`; путь из `classname` с `/` не приведён к
    корню (`_root_path` не применён).
    """
    workdir = f"w{box.word()}"
    m = f"test_{box.word()}"
    k = f"K{box.word()}"
    f1, f2, f3, keep = (box.py_name() for _ in range(4))
    inner = {f"tests/{m}.py": py_source([f1, keep, f3]) + f"\n\nclass {k}:\n    pass\n"}
    files = {f"{workdir}/{rel}": text for rel, text in inner.items()}
    files[f"tests/{m}.py"] = py_source([f1, keep])
    project = box.ci_project(files, workdir=workdir)
    t = box.merge_task(project)
    report = {f"tests.{m}::{f1}": "success", f"tests.{m}.{k}::{f2}": "success",
              f"tests/{m}.py::{f3}": "success", f"tests.{m}::{keep}": "success"}
    box.publish(t.base, project.job, "success", report)
    box.publish(t.head, project.job, "success", {f"tests.{m}::{keep}": "success"})
    run = box.gate(t)
    detail = refused(box, run)
    path = f"{workdir}/tests/{m}.py"
    wanted = [box.cid(project, path, f1), box.cid(project, path, f"{k}::{f2}"),
              box.cid(project, path, f3)]
    for cid in wanted:
        assert f"{GONE}: {cid} — " in detail, f"нет {cid}\n" + box.why(run)
    local = junit_ids([(f"tests.{m}", f1), (f"tests.{m}.{k}", f2)],
                      project.comp, workdir, inner)
    assert local == wanted[:2], box.note(f"{local}")


# ---------------------------------------------------------------- AC-8


@pytest.mark.parametrize("ambiguity", ["статус вне перечня", "два ключа"])
def test_ac8_unknown_in_head_is_broken_and_mandate_lifts_it(box, ambiguity):
    """Тест зелёный в отчёте базы и неоднозначный в отчёте головы — отказ с находкой «сломан правкой», не совпадение; мандат Оператора на неё снимает её.

    Сценарий (по случаю): в отчёте базы все тесты `success`; в отчёте
    головы у одного теста статус вне перечня (`unknown`), либо он записан
    двумя ключами, дающими один идентификатор (точечный `classname` и
    `classname` с `/`), оба `success`. Первый прогон гейта: отказ
    «сломан правкой: <id> — …», `escalated`. Оператор отвечает мандатом
    «Ослабление тестов разрешено: <путь>::<имя>» (`answer`), задача
    возвращена на `merge_gate`; второй прогон: гейт пройден, в записи
    прохода — строка находки этого теста «… — покрыто мандатом ANSWER-n».

    Ловит мутацию: неоднозначная запись головы засчитана совпадением
    (статус вне перечня принят за `passed`, из двух ключей взят первый) —
    гейт пройден с первого раза; «неизвестно» дало находку иного вида
    (не снимаемую мандатом как «сломан правкой») — второй прогон снова
    отказ.
    """
    case = ambiguity + ": "
    project, rel, names = box.scenario()
    t = box.merge_task(project)
    report = box.green(rel, names)
    box.publish(t.base, project.job, "success", report)
    odd = box.rng.choice(names)
    head = dict(report)
    if ambiguity == "статус вне перечня":
        head[box.key(rel, odd)] = STRANGE_STATUS
    else:
        head[f"{rel}::{odd}"] = "success"
    box.publish(t.head, project.job, "success", head)
    cid = box.cid(project, rel, odd)
    run = box.gate(t)
    detail = refused(box, run, case)
    assert f"{BROKEN}: {cid} — " in detail, case + box.why(run)
    box.operator_mandate(t, [f"{rel}::{odd}"])
    if box.state(t) != "merge_gate":
        store.set_state(box.conn, t.id, "merge_gate", "operator",
                        expected_state=box.state(t), detail="сценарий: снова мерж")
    again = box.gate(t)
    record = passed(box, again, case + "после мандата: ")
    assert any(cid in line and COVERED_BY in line
               for line in record.splitlines()), case + box.why(again)


def test_ac8_module_missing_in_head_tree_is_not_a_match(box):
    """Модуль точечного `classname` записи головы не найден в дереве головы — тест не засчитан совпадением с зелёным тестом базы: отказ гейта мержа.

    Сценарий: голова удаляет файл тестов, а отчёт головы по-прежнему
    несёт его тест `success` под тем же точечным ключом. Гейт: запись
    `MERGE_REFUSAL_ACTION`, `escalated`, прохода нет. (Вид находки здесь
    не утверждается: SPEC не задаёт, как запись без идентификатора
    сопоставляется с тестом базы.)

    Ловит мутацию: модуль ищется на диске клона или в дереве базы, а не
    в дереве коммита отчёта головы — идентификатор совпал, гейт пройден.
    """
    project, rel, names = box.scenario()
    t = box.merge_task(project, {rel: None})
    report = box.green(rel, names)
    box.publish(t.base, project.job, "success", report)
    box.publish(t.head, project.job, "success", report)
    run = box.gate(t)
    refused(box, run)
    assert box.details(run.rows, PASSED) == [], box.why(run)


# ---------------------------------------------------------------- AC-9


def test_ac9_in_dev_gate_of_ci_component_judges_local_checkouts(box):
    """На `in_dev → verifying` гейт компонента `full_suite: ci` судит по локальным выпискам базы и головы, как сейчас, и не читает отчётов CI.

    Сценарий: задача проекта с компонентом `full_suite: ci` прошла выход
    из `tests_writing`; тест базы на голове красен все три прогона
    (сценарий раннера). `advance` из `in_dev`: прежний отказ «переход
    отклонён: гейт неослабления по исходам — сломан правкой» с
    идентификатором теста, задача в `in_dev`; шпион видит `worktree add`
    и полные прогоны сторон «база» и «голова»; из кадров гейта нет ни
    одного чтения `pipeline_status`/`job_result`/`job_test_report`.

    Ловит мутацию: режим `ci` включён и на `in_dev` — гейт читает отчёты
    CI (у неотправленной головы их нет — сбой подготовки) вместо выписок;
    выписки на `in_dev` пропущены для `ci` — гейт пройден.
    """
    rel, name = box.py_rel(), box.py_name()
    project = box.ci_project({rel: py_source([name, box.py_name()])})
    box.cases[(rel, name)] = {"base": ["passed"], "head": ["failed"]}
    t = box.task(project)
    box.checkouts.clear()
    box.forge.calls.clear()
    rows, output = box.developer_advance(t)
    detail = box.refusal(rows, output, BROKEN_ACTION)
    context = box.explain(rows, output) + f"\nхостинг: {box.forge.calls}"
    assert box.cid(project, rel, name) in detail, context
    assert box.checkouts, context
    assert {r["side"] for r in box.full_runs()} >= {"base", "head"}, context
    assert box.gate_reads() == [], context


# ---------------------------------------------------------------- AC-10


@pytest.mark.parametrize("finding", ["строгий режим", "исключение в коде"])
def test_ac10_g3b2_findings_stay_without_checkouts(box, finding):
    """Годные отчёты без расхождений исходов, но дифф правит существующий файл тестов без `python-ast` или добавляет в код маркер исключения — отказ гейта мержа, без выписок.

    Сценарий (по случаю): (а) компонент с `layers: []`, голова дописывает
    строку в существующий файл тестов из отчёта базы — находка
    «строгий режим — правка существующего файла: <путь> — …»; (б) голова
    добавляет файл кода со строкой, несущей случайную подстроку
    `CODE_EXCEPTION_TOKENS`, — находка «исключение в коде: <путь> — …».
    Отчёты базы и головы одинаковы и зелены. Гейт: `MERGE_REFUSAL_ACTION`
    с находкой, `escalated`; выписок, прогонов и полного набора нет.

    Ловит мутацию: находки G3б-2 в режиме `ci` выключены — гейт пройден;
    дифф для них берётся из выписок — шпион видит `worktree add`.
    """
    case = finding + ": "
    strict = finding == "строгий режим"
    project, rel, names = box.scenario(layers=[] if strict else None)
    if strict:
        path = rel
        changes = {rel: py_source(names) + f"# правка {box.word()}\n"}
    else:
        path = f"lib/m{box.word()}.py"
        token = box.rng.choice(outcome_integrity.CODE_EXCEPTION_TOKENS)
        changes = {path: f"FLAG = '{token}'\n"}
    t = box.merge_task(project, changes)
    report = box.green(rel, names)
    box.publish(t.base, project.job, "success", report)
    box.publish(t.head, project.job, "success", report)
    run = box.gate(t)
    detail = refused(box, run, case)
    kind = STRICT_EDIT if strict else CODE_EXCEPTION
    assert f"{kind}: {path} — " in detail, case + box.why(run)
    no_local(box, run, case)


# ---------------------------------------------------------------- AC-11


def test_ac11_passed_record_key_by_head_tree_and_job_ids(box):
    """Пройденный гейт `ci` пишет `PASSED_ACTION` с ключом по дереву головы и `id` заданий `ci_job` головы и базы — без выписки и без чтения сумм файлов блокировки.

    Сценарий: в проекте есть файл блокировки (`uv.lock`), git в кадрах
    гейта отказывает его чтению `ls-tree` (так ключ по суммам блокировки
    не снялся бы). Отчёты базы и головы зелены (по две попытки задания).
    Гейт пройден: строка доказательства записи разбирается
    `proof_fields`, голова — sha головы, ключ содержит дерево головы
    (`<sha>^{tree}`) и наибольшие `id` попыток `ci_job` головы и базы;
    шпион не видел ни `worktree add`, ни `ls-tree` файла блокировки.

    Ловит мутацию: ключ по-прежнему `report_suite_result_key` с суммами
    файлов блокировки — их чтение отказано, сбой подготовки (или
    выписка головы ради них); ключ без `id` заданий; ключ по sha коммита,
    а не по дереву.
    """
    project, rel, names = box.scenario(extra={"uv.lock": f"# {box.word()}\n"})
    t = box.merge_task(project)
    box.fail_locks = True
    report = box.green(rel, names)
    base_id = box.publish(t.base, project.job, "success", report, attempts=2)
    head_id = box.publish(t.head, project.job, "success", report, attempts=2)
    run = box.gate(t)
    detail = passed(box, run)
    fields = outcome_integrity.proof_fields(detail)
    assert fields is not None, box.why(run)
    head, _base, key, _fp = fields
    assert head == t.head, box.why(run)
    assert box.tree(t, t.head) in key, box.why(run)
    assert has_id(key, head_id) and has_id(key, base_id), (
        f"ключ {key}: ждали {head_id} и {base_id}\n" + box.why(run))
    assert box.checkouts == [] and box.lock_reads == [], box.why(run)


# ---------------------------------------------------------------- AC-12


@pytest.mark.parametrize("ambiguity", ["модуль не найден", "статус вне перечня",
                                       "два ключа"])
def test_ac12_ambiguous_base_record_is_prepare_failure(box, ambiguity):
    """Неоднозначная запись в отчёте базы — сбой подготовки «отчёт базы неоднозначен: <id>», задача на `merge_gate`, отправки нет.

    Сценарий (по случаю): отчёт головы зелен и однозначен. В отчёте
    базы сверх зелёных тестов: (а) запись `tests.<нет файла>::<имя>`,
    модуля которой нет в дереве, — причина называет ключ записи; (б) тест
    файла со статусом вне перечня — причина называет его идентификатор;
    (в) тест записан двумя ключами (точечным и с `/`) — причина называет
    идентификатор. Гейт: `MERGE_PREPARE_ACTION` с «отчёт базы
    неоднозначен: …», выход без пропуска, `merge_gate`, `origin/main` не
    сдвинут.

    Ловит мутацию: неоднозначная запись базы молча выпадает из
    `PASS_TO_PASS` — гейт пройден; эскалация вместо сбоя подготовки;
    причина без идентификатора записи.
    """
    case = ambiguity + ": "
    project, rel, names = box.scenario()
    t = box.merge_task(project)
    clean = box.green(rel, names)
    base = dict(clean)
    odd = box.rng.choice(names)
    if ambiguity == "модуль не найден":
        named = f"tests.test_{box.word()}::{box.py_name()}"
        base[named] = "success"
    elif ambiguity == "статус вне перечня":
        base[box.key(rel, odd)] = STRANGE_STATUS
        named = box.cid(project, rel, odd)
    else:
        base[f"{rel}::{odd}"] = "success"
        named = box.cid(project, rel, odd)
    box.publish(t.base, project.job, "success", base)
    box.publish(t.head, project.job, "success", clean)
    run = box.gate(t)
    detail = prepare_failed(box, run, case)
    assert f"{BASE_AMBIGUOUS}{named}" in detail, case + box.why(run)


# ---------------------------------------------------------------- AC-13


def test_ac13_two_ci_components_one_head_tree_have_distinct_keys(box):
    """Два компонента `full_suite: ci` с одним деревом головы: строка доказательства каждой записи прохода разбирается `PROOF_LINE`, ключи различны и несут имя своего компонента, дерево головы и `id` заданий.

    Сценарий: запись проекта из двух компонентов (`paths` `^<a>/` и
    `^<b>/`), оба `full_suite: ci` с ОДНИМ именем `ci_job` (одни и те же
    задания и `id` у обоих); задача правит файл первого компонента и
    `app.py` (вне компонентов — гейт берёт оба). Отчёты базы и головы
    зелены. Гейт пройден: записей `PASSED_ACTION` две, у каждой
    `proof_fields` не `None`, ключи различны, каждый содержит имя своего
    компонента (и не содержит чужого), дерево головы и `id` заданий
    головы и базы.

    Ловит мутацию: ключ без имени компонента — ключи двух записей
    совпали; в ключе пробел или разделитель, ломающий `PROOF_LINE`, —
    `proof_fields` даёт `None`.
    """
    name, job = f"m{box.word()}", f"t{box.word()}"
    comps = (f"a{box.word()}", f"b{box.word()}")
    lines = [ENTRY_HEAD.format(name=name).replace("forge: github",
                                                  "forge: gitlab"),
             "    components:\n"]
    files = {"app.py": "APP = 'base'\n"}
    report = {}
    for comp in comps:
        fields = box.component_fields(job, f"{comp}/tests/**")
        fields["long_lived_dir"] = f"{comp}/tests"
        fields["paths"] = flow([f"^{comp}/"])
        lines.append(f"      {comp}:\n")
        lines += [f"        {k}: {v}\n" for k, v in fields.items()]
        rel = f"{comp}/tests/test_{box.word()}.py"
        names = [box.py_name() for _ in range(2)]
        files[rel] = py_source(names)
        report.update(box.green(rel, names))
    box.append_entry("".join(lines))
    clone = make_project_repo(name)
    box.commit_project(clone, files)
    box.clones[name] = clone
    project = SimpleNamespace(name=name, comp=comps[0], job=job, clone=clone,
                              workdir="", kind="multi", layout="")
    t = box.merge_task(project, {f"{comps[0]}/lib.py": "VALUE = 1\n"})
    base_id = box.publish(t.base, job, "success", report)
    head_id = box.publish(t.head, job, "success", report)
    run = box.gate(t)
    assert run.result is False and run.exited is None, box.why(run)
    records = box.details(run.rows, PASSED)
    assert len(records) == 2, box.why(run)
    keys = []
    for record in records:
        fields = outcome_integrity.proof_fields(record)
        assert fields is not None, box.why(run)
        keys.append(fields[2])
    assert keys[0] != keys[1], box.why(run)
    tree = box.tree(t, t.head)
    for comp in comps:
        own = [k for k in keys if comp in k]
        assert len(own) == 1, f"{comp}: {keys}\n" + box.why(run)
        assert tree in own[0], box.why(run)
        assert has_id(own[0], head_id) and has_id(own[0], base_id), box.why(run)
