"""Источник полного набора компонента на приёмке: `full_suite: ci` — итог задания CI через `forge`, `both` — оба источника.

Группа: долгоживущий
Красен до реализации: поле `full_suite` загрузчику неизвестно — профиль компонента стенда не читается, приёмка гоняет полный набор локально (шпион вызван) и итога задания CI не читает; зелён с рождения один вариант AC-11 (красный локальный при зелёном CI — итог не зелёный и без кода задачи).

Стенд — лёгкая песочница переходов (`light_transition`) с задачей
внешнего проекта: запись из одного компонента с `report`, `full_suite`,
`ci_job` и базовой веткой записи, отличной от `main` (выбирается
зерном). Хостинг подменён реестром `forge.IMPLEMENTATIONS` (значение
`forge` записи — `github`, чтобы задача проекта была исполняемой):
поддельная реализация отдаёт задания и отчёт ровно для sha головы.
Внешние источники трёх условий принятия итога CI подменены публичными
именами, как у прецедента итога CI артели
(`tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`): голова ветки
— `ci.head_sha`, деревья гейта и головы — `acceptance.suite_tree_hash`,
свежесть — `is_ancestor` модуля git-команд, взятого через `acceptance` (предок `origin/<ветка>` — по имени
ветки в ссылке). Локальный полный прогон компонента — шпион
`acceptance.full_suite`.

Связки, которые держит файл: `acceptance.acceptance_suite` (узел итога
приёмки, общий у `approve` и автогейта); `fsm.cmd_approve` над задачей в
`acceptance` — решение `--accept-red` по итогу; `fsm.cmd_advance` из
`review` с одобренным REVIEW — автогейт приёмки.
"""
import random
from unittest import mock

import pytest

from orchestrator import (acceptance, ci, config, fixation, forge, fsm, gates,
                          github_adapter, pull, store, workspace)
from tests.sandbox import make_project_repo

PROJECT = "uchcisuite"
BASES = ("develop", "trunk", "stable", "release")
REASON = "краснота задания CI принята Оператором осознанно"
CHECK_FAIL = "[python3, -c, raise SystemExit(3)]"

REVIEW_APPROVED = ("---\ntask: {task}\ntype: review\nauthor_role: reviewer\n"
                   "status: approved\niteration: 1\nschema_version: 2\n---\n\n"
                   "# REVIEW: итог задания CI\n\n## Соответствие SPEC\n"
                   "Критерии выполнены.\n\n## Замечания\nНет.\n\n"
                   "## Вердикт\napproved\n\n"
                   "## Проверено исполнением\nПланка зелёная.\n")

LOCAL_GREEN = acceptance.FullSuiteRun(
    True, acceptance.FULL_SUITE_GREEN, "12 passed", None,
    "локальный полный набор компонента зелёный")
LOCAL_RED = acceptance.FullSuiteRun(
    False, acceptance.FULL_SUITE_RED, "1 failed, 11 passed", None,
    "локальный полный набор компонента красный: 1 failed, 11 passed")


class FakeForge:
    """Поддельная реализация хостинга: задания и отчёт sha головы стенда.

    Другой sha — конвейера нет. Каждое обращение пишется в `calls`."""

    CI_BY_PIPELINE = False

    def __init__(self, stand):
        self.stand = stand
        self.calls = []

    def _jobs(self, sha):
        return list(self.stand.jobs) if sha == self.stand.sha else []

    def _last(self, sha, name):
        mine = [j for j in self._jobs(sha) if j.name == name]
        return max(mine, key=lambda j: j.id or 0) if mine else None

    def pipeline_status(self, target, sha):
        self.calls.append(("pipeline_status", sha))
        jobs = self._jobs(sha)
        if not jobs:
            return forge.PipelineStatus(forge.NONE, f"конвейера {sha[:8]} нет")
        latest = {}
        for job in sorted(jobs, key=lambda j: j.id or 0):
            latest[job.name] = job
        failed = sorted(j.name for j in latest.values()
                        if j.status == "failed" and not j.allow_failure)
        if failed:
            return forge.PipelineStatus(forge.RED, "упали задания", jobs, failed)
        if any(j.status in ("running", "pending") for j in latest.values()):
            return forge.PipelineStatus(forge.RUNNING, "задания идут", jobs)
        return forge.PipelineStatus(forge.GREEN, "", jobs)

    def job_result(self, target, sha, job_name):
        self.calls.append(("job_result", sha))
        job = self._last(sha, job_name)
        if job is None:
            return forge.JobResult(None, f"задания «{job_name}» нет")
        return forge.JobResult(job.status)

    def job_test_report(self, target, sha, job_name):
        self.calls.append(("job_test_report", sha))
        if self._last(sha, job_name) is None:
            return forge.TestReport(None, f"задания «{job_name}» нет")
        outcomes = self.stand.outcomes
        if outcomes is None:
            return forge.TestReport(None, "отчёт тестов задания недоступен")
        return forge.TestReport(dict(outcomes))


def write_entry(s, mode: str, checks_local: bool = False) -> None:
    fields = {
        "command": "[python3, -m, pytest]",
        "report": "junit-xml",
        "long_lived_dir": "tests",
        "long_lived_name": "test_<id>_<name>.py",
        "weakening_scope": "[tests/**]",
        "mutation_claim_scope": "[tests/test_*.py]",
        "full_suite": mode,
        "ci_job": s.job,
    }
    if checks_local:
        fields["checks_local"] = CHECK_FAIL
    text = (f"  {PROJECT}:\n"
            "    forge: github\n"
            f"    url: https://localhost/artel-tests/{PROJECT}\n"
            f"    base: {s.base}\n"
            f"    token_slot: {PROJECT}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n"
            "    components:\n"
            "      app:\n"
            + "".join(f"        {k}: {v}\n" for k, v in fields.items()))
    config.TARGETS.write_text(s.artel_text.rstrip("\n") + "\n" + text,
                              encoding="utf-8")


def set_ci(s, status: str = "success", *, allow_failure: bool = False,
           present: bool = True, bad: str | None = None,
           report: str = "parsed") -> None:
    """Задания sha головы и отчёт: две попытки `ci_job` (ранняя — упавшая
    с правом падать), постороннее задание; `bad` — исход одного теста
    отчёта; `report` — `parsed` | `none` | `empty`."""
    rng = s.rng
    old = rng.randrange(1000, 5000)
    s.job_id = old + rng.randrange(1, 5000)
    jobs = [forge.Job("lint", "success", "test", rng.randrange(1, 999))]
    if present:
        jobs += [forge.Job(s.job, "failed", "test", old, True),
                 forge.Job(s.job, status, "test", s.job_id, allow_failure)]
    rng.shuffle(jobs)
    s.jobs = jobs
    s.n = rng.randrange(3, 40)
    outcomes = {f"pkg.test_mod{i % 4}.Case::test_{i}": "success"
                for i in range(s.n)}
    if bad is not None:
        outcomes[rng.choice(sorted(outcomes))] = bad
    s.outcomes = ({} if report == "empty" else None if report == "none"
                  else outcomes)


@pytest.fixture
def stand(light_transition):
    """Задача внешнего проекта в `acceptance` с подменённым хостингом и
    источниками трёх условий; по умолчанию все условия выполнены, CI
    зелёный, локальный прогон зелёный."""
    s = light_transition
    s.seed = random.randrange(1 << 32)
    print(f"зерно: {s.seed}")
    s.rng = random.Random(s.seed)
    s.base = s.rng.choice(BASES)
    s.sha = f"{s.rng.getrandbits(160):040x}"
    s.job = f"{s.rng.choice(('full-suite', 'pytest', 'tests'))}-{s.rng.randrange(1, 99)}"
    s.tree = f"{s.rng.getrandbits(160):040x}"
    s.gate_tree = s.tree
    s.head_tree = s.tree
    s.tree_fails = None
    s.head_ok = True
    s.contains = {s.base, config.MAIN_BRANCH}
    s.artel_text = config.TARGETS.read_text(encoding="utf-8")
    s.forge = FakeForge(s)
    s.local = mock.Mock(side_effect=lambda *a, **kw: s.local_result)
    s.local_result = LOCAL_GREEN
    set_ci(s)

    real_is_ancestor = acceptance.gitcmd.is_ancestor

    def is_ancestor(ancestor, descendant, repo=None):
        if "origin/" in ancestor:
            name = ancestor.split("origin/", 1)[1]
            return descendant == s.sha and name in s.contains
        return real_is_ancestor(ancestor, descendant, repo=repo)

    def head_sha(branch, repo=None):
        if s.head_ok:
            return s.sha, ""
        return "", f"головной коммит ветки {branch} не определён"

    def tree_hash(*args, **kwargs):
        head = kwargs.get("ref") not in (None, "HEAD") or \
            kwargs.get("worktree") is False
        if s.tree_fails == ("head" if head else "gate"):
            raise OSError("дерево не прочитано")
        return s.head_tree if head else s.gate_tree

    s.wt_path.mkdir(parents=True, exist_ok=True)
    for target, name, kwargs in (
            (pull, "evaluate", {"return_value": pull.Fresh()}),
            (fsm, "confirm_fixation", {"return_value": True}),
            (fixation, "approve_sha_hint", {"return_value": ""}),
            (github_adapter, "undraft_mr", {"return_value": None}),
            (workspace, "on_task_branch", {"return_value": True}),
            (workspace, "path", {"return_value": s.wt_path}),
            (ci, "head_sha", {"side_effect": head_sha}),
            (acceptance.gitcmd, "is_ancestor", {"side_effect": is_ancestor}),
            (acceptance, "full_suite", {"side_effect": s.local}),
            (acceptance, "suite_tree_hash", {"side_effect": tree_hash}),
    ):
        patcher = mock.patch.object(target, name, **kwargs)
        patcher.start()
        s.addCleanup(patcher.stop)
    patcher = mock.patch.dict(forge.IMPLEMENTATIONS, {"github": s.forge})
    patcher.start()
    s.addCleanup(patcher.stop)

    write_entry(s, "ci")
    make_project_repo(PROJECT, origin=False)
    store.update_task(store.db(), s.TASK, target=PROJECT)
    s.set_state("acceptance")
    return s


def suite(s, fresh: bool = False):
    """Итог приёмочного узла полного набора и новые записи журнала."""
    conn = store.db()
    before = len(store.task_steps(conn, s.TASK))
    run = acceptance.acceptance_suite(
        conn, s.wt_path, s.TASK, s.branch, workspace.task_repo(s.TASK),
        actor="operator", fresh=fresh)
    added = store.task_steps(store.db(), s.TASK)[before:]
    return run, "\n".join(f"{r['action']}: {r['detail'] or ''}" for r in added)


def approve(s, accept_red=None, fresh_suite=False) -> str:
    s.set_state("acceptance")
    return s.capture(lambda: fsm.cmd_approve(
        s.TASK, accept_red=accept_red, fresh_suite=fresh_suite))


def autogate(s) -> str:
    """Вход в `acceptance` из `review` с одобренным REVIEW при политике
    `auto` — попытка автогейта приёмки."""
    s.write_acceptance_plank()
    (s.tdir / "REVIEW.md").write_text(REVIEW_APPROVED.format(task=s.TASK),
                                      encoding="utf-8")
    s.set_state("review")
    with mock.patch.object(gates, "policy", return_value=gates.AUTO):
        return s.capture(fsm.cmd_advance, s.TASK)


def journal(s) -> str:
    return "\n".join(f"{r['action']}: {r['detail'] or ''}"
                     for r in store.task_steps(store.db(), s.TASK))


def refusals(s, action: str, reason: str) -> list:
    """Записи журнала с действием `action`, деталь которых несёт `reason`."""
    return [r for r in store.task_steps(store.db(), s.TASK)
            if r["action"] == action and reason in (r["detail"] or "")]


def reason_of(run) -> str:
    """Причина «неизвестно» — первая строка детали без `UNKNOWN_PREFIX` и
    без пометки компонента."""
    head = run.detail.splitlines()[0][len(acceptance.UNKNOWN_PREFIX):]
    return head.split(" [компонент ")[0].strip()


def assert_unknown(s, run, where: str) -> None:
    assert acceptance.is_unknown(run), \
        f"{where}: {run.outcome} {run.detail!r}; зерно: {s.seed}"
    assert not run.green, where
    assert reason_of(run), f"{where}: причина не названа; зерно: {s.seed}"


def test_ac6_green_ci_job_last_attempt_recorded(stand):
    """Последняя попытка `ci_job` (наибольший `id`) без права падать, `success`, отчёт без `failed`/`error` — итог зелёный, запись журнала называет задание, sha и число тестов.

    Ранняя попытка того же задания — упавшая с правом падать, задания в
    ответе `pipeline_status` перемешаны зерном: номер задания в записи —
    именно наибольший `id`, а не первое или последнее задание списка.

    Ловит мутацию: номер задания берётся из первой найденной попытки
    `ci_job` (или итог читается по `origin/main` вместо sha головы) —
    в журнале другой `id`/sha, либо поддельный хостинг не отдаёт заданий
    и итог не зелёный.
    """
    s = stand
    run, added = suite(s)
    assert run.green, f"{run.outcome} {run.detail!r}; зерно: {s.seed}"
    assert run.outcome == acceptance.FULL_SUITE_GREEN
    record = (f"полный набор: итог задания CI {s.job}, задание {s.job_id}, "
              f"sha {s.sha}, тестов {s.n}")
    assert record in added, f"{added!r}; зерно: {s.seed}"
    s.local.assert_not_called()


@pytest.mark.parametrize("status,bad", [
    ("success", "failed"), ("success", "error"),
    ("failed", "failed"), ("failed", "error")])
def test_ac7_red_ci_job_is_honest_red_accepted_by_flag(stand, status, bad):
    """Задание без права падать в `success`/`failed` с исходом `failed`/`error` в разобранном отчёте — красный итог, `approve --accept-red` его принимает.

    Ловит мутацию: краснота отчёта при статусе `failed` сведена к
    «неизвестно» (или исход `error` не считается падением) — итог не
    `FULL_SUITE_RED`, и `approve --accept-red` оставляет задачу в
    `acceptance` вместо перехода в `merge_gate`.
    """
    s = stand
    set_ci(s, status, bad=bad)
    run, _added = suite(s)
    assert run.outcome == acceptance.FULL_SUITE_RED, \
        f"{run.outcome} {run.detail!r}; зерно: {s.seed}"
    assert not acceptance.is_unknown(run)
    assert not run.green

    out = approve(s, accept_red=REASON)
    assert s.state() == "merge_gate", f"{out}; зерно: {s.seed}"
    assert fsm.ACCEPTANCE_RED_ACCEPTED_ACTION in journal(s)
    s.local.assert_not_called()


UNKNOWN_CASES = [
    "no_job", "manual", "running", "skipped", "report_none", "report_empty",
    "allow_failure", "failed_clean", "failed_no_report", "canceled_clean",
    "canceled_failed"]


def set_unknown_case(s, case: str) -> None:
    if case == "no_job":
        set_ci(s, present=False)
    elif case in ("manual", "running", "skipped"):
        set_ci(s, case)
    elif case == "report_none":
        set_ci(s, report="none")
    elif case == "report_empty":
        set_ci(s, report="empty")
    elif case == "allow_failure":
        set_ci(s, allow_failure=True)
    elif case == "failed_clean":
        set_ci(s, "failed")
    elif case == "failed_no_report":
        set_ci(s, "failed", report="none")
    elif case == "canceled_clean":
        set_ci(s, "canceled")
    else:
        set_ci(s, "canceled", bad="failed")


@pytest.mark.parametrize("case", UNKNOWN_CASES)
def test_ac8_unknown_ci_job_refused_by_flag_and_autogate(stand, case):
    """Каждый случай без доказанного итога задания — «неизвестно» с причиной; `approve --accept-red` и автогейт его не принимают.

    Случаи: задания нет; `manual`; `running`; `skipped`; отчёт `None`;
    отчёт пуст; задание с правом падать; `failed` при чистом отчёте и при
    отчёте `None`; `canceled` при чистом отчёте и при отчёте с `failed`.

    Ловит мутацию: задание `canceled` с `failed` в отчёте (или `failed`
    без падений в отчёте) читается как красный — `is_unknown` ложно, и
    `approve --accept-red` проводит задачу в `merge_gate`; либо задание с
    правом падать в `success` читается зелёным — автогейт проводит задачу.
    """
    s = stand
    set_unknown_case(s, case)
    run, added = suite(s)
    assert_unknown(s, run, case)
    assert reason_of(run) in added, f"{case}: {added!r}; зерно: {s.seed}"

    reason = reason_of(run)
    out = approve(s, accept_red=REASON)
    assert s.state() == "acceptance", f"{case}: {out}; зерно: {s.seed}"
    assert fsm.ACCEPTANCE_RED_ACCEPTED_ACTION not in journal(s)
    assert refusals(s, "approve отклонён", reason), \
        f"{case}: отказ approve не по итогу: {journal(s)!r}; зерно: {s.seed}"

    out = autogate(s)
    assert s.state() == "acceptance", f"{case}: {out}; зерно: {s.seed}"
    assert refusals(s, "автогейт acceptance не пройден", reason), \
        f"{case}: отказ автогейта не по итогу: {journal(s)!r}; зерно: {s.seed}"
    s.local.assert_not_called()


CONDITIONS = ["head_unread", "gate_tree_unread", "head_tree_unread",
              "tree_differs", "stale_base"]


def break_condition(s, condition: str) -> None:
    if condition == "head_unread":
        s.head_ok = False
    elif condition == "gate_tree_unread":
        s.tree_fails = "gate"
    elif condition == "head_tree_unread":
        s.tree_fails = "head"
    elif condition == "tree_differs":
        s.gate_tree = f"{s.rng.getrandbits(160):040x}"
    else:
        s.contains = {config.MAIN_BRANCH}


@pytest.mark.parametrize("condition", CONDITIONS)
def test_ac9_unmet_condition_unknown_without_local_run(stand, condition):
    """Невыполненное условие принятия итога CI у записи с базой не `main` — «неизвестно» с причиной, локального прогона нет.

    Отставание от `origin/<base>` проверяется при голове, содержащей
    `origin/main`: свежесть судится по базе записи, не по `main`.

    Ловит мутацию: невыполненное условие ведёт, как у артели, в локальный
    полный прогон (шпион `acceptance.full_suite` вызван) либо свежесть
    сверяется с `origin/main` — голова, отставшая от `origin/<base>`, даёт
    зелёный итог.
    """
    s = stand
    break_condition(s, condition)
    run, _added = suite(s)
    assert_unknown(s, run, condition)
    s.local.assert_not_called()


def test_ac9_fresh_against_base_without_main_is_green(stand):
    """Голова свежа относительно `origin/<base>`, но не содержит `origin/main` — итог зелёный без локального прогона.

    Ловит мутацию: свежесть по-прежнему сверяется с
    `origin/{config.MAIN_BRANCH}` — итог «неизвестно» («ветка не свежа»)
    вместо зелёного.
    """
    s = stand
    s.contains = {s.base}
    run, _added = suite(s)
    assert run.green, f"{run.outcome} {run.detail!r}; зерно: {s.seed}"
    s.local.assert_not_called()


@pytest.mark.parametrize("condition", [None, "tree_differs", "stale_base"])
def test_ac10_fresh_suite_rereads_ci_without_local_run(stand, condition):
    """`fresh=True` в режиме `ci` заново читает итог задания через `forge`; при другом дереве или несвежей голове — «неизвестно», итог CI не принят.

    Ловит мутацию: `fresh=True`, как у артели, сразу гонит локальный
    полный набор (шпион вызван, хостинг не спрошен) либо пропускает три
    условия — при другом дереве гейта итог задания CI принят зелёным.
    """
    s = stand
    if condition is not None:
        break_condition(s, condition)
    s.forge.calls.clear()
    run, _added = suite(s, fresh=True)
    s.local.assert_not_called()
    if condition is None:
        assert run.green, f"{run.outcome} {run.detail!r}; зерно: {s.seed}"
        read = {name for name, sha in s.forge.calls if sha == s.sha}
        assert read & {"job_result", "job_test_report"}, \
            f"{s.forge.calls}; зерно: {s.seed}"
    else:
        assert_unknown(s, run, condition)


@pytest.mark.parametrize("local,ci_case,expected", [
    ("green", "green", "green"),
    ("red", "green", "not_green"),
    ("green", "red", "not_green"),
    ("green", "unknown", "unknown"),
    ("red", "unknown", "unknown")])
def test_ac11_both_needs_both_sources_green(stand, local, ci_case, expected):
    """`full_suite: both` — зелёный только при зелёных обоих источниках; «неизвестно» CI старше локального красного, `--accept-red` его не принимает.

    Ловит мутацию: в `both` решает один источник (только локальный или
    только CI) — пара «зелёный локальный + красный CI» зелёная; либо
    красный локальный старше «неизвестно» CI — итог красный, и
    `approve --accept-red` проводит задачу.
    """
    s = stand
    write_entry(s, "both")
    s.local_result = LOCAL_GREEN if local == "green" else LOCAL_RED
    if ci_case == "red":
        set_ci(s, "failed", bad="failed")
    elif ci_case == "unknown":
        set_ci(s, "running")
    run, _added = suite(s)
    assert s.local.called, f"в both локальный прогон обязателен; зерно: {s.seed}"
    if expected == "green":
        assert run.green, f"{run.outcome} {run.detail!r}; зерно: {s.seed}"
        read = {name for name, sha in s.forge.calls if sha == s.sha}
        assert read & {"job_result", "job_test_report"}, \
            f"в both итог задания CI обязателен: {s.forge.calls}; зерно: {s.seed}"
        return
    assert not run.green, f"{local}/{ci_case}; зерно: {s.seed}"
    if expected == "unknown":
        assert_unknown(s, run, f"{local}/{ci_case}")
        approve(s, accept_red=REASON)
        assert s.state() == "acceptance", f"зерно: {s.seed}"
        assert fsm.ACCEPTANCE_RED_ACCEPTED_ACTION not in journal(s)
        assert refusals(s, "approve отклонён", reason_of(run)), \
            f"{journal(s)!r}; зерно: {s.seed}"


@pytest.mark.parametrize("ci_case", ["green", "red", "unknown"])
def test_ac12_ci_mode_never_runs_local_suite(stand, ci_case):
    """Приёмка компонента `ci` при любом итоге задания (и через `approve`) не запускает локальный полный набор.

    Ловит мутацию: незелёный итог задания CI откатывается в локальный
    полный прогон, как у артели, — шпион `acceptance.full_suite` вызван.
    """
    s = stand
    if ci_case == "red":
        set_ci(s, "success", bad="error")
    elif ci_case == "unknown":
        set_ci(s, present=False)
    suite(s)
    approve(s)
    s.local.assert_not_called()


def test_ac13_autogate_takes_ci_job_record_as_ci_result(stand):
    """Автогейт приёмки проводит зелёный итог задания CI; деталь его перехода несёт запись итога CI, а не текст локального прогона.

    Ловит мутацию: автогейт распознаёт итог CI только подстрокой
    «принят итог CI» артели — деталь перехода в `merge_gate` несёт
    «полный набор tests/ в worktree ветки зелёный» вместо записи задания.
    """
    s = stand
    out = autogate(s)
    assert s.state() == "merge_gate", f"{out}; зерно: {s.seed}"
    record = (f"полный набор: итог задания CI {s.job}, задание {s.job_id}, "
              f"sha {s.sha}, тестов {s.n}")
    moves = [r["detail"] or "" for r in store.task_steps(store.db(), s.TASK)
             if r["actor"] == "autogate"]
    assert any(record in d for d in moves), f"{moves!r}; зерно: {s.seed}"
    assert not any("полный набор tests/ в worktree ветки зелёный" in d
                   for d in moves), f"{moves!r}; зерно: {s.seed}"
    s.local.assert_not_called()


@pytest.mark.parametrize("mode", ["ci", "both"])
@pytest.mark.parametrize("ci_case", ["green", "unknown"])
def test_ac15_failed_checks_local_after_ci_result(stand, mode, ci_case):
    """Непрошедшая `checks_local` красит зелёный итог задания CI (в `both` — и зелёный локальный) в красный с записью `checks_local компонента`; «неизвестно» остаётся «неизвестно».

    Ловит мутацию: в режиме `ci` `checks_local` пропущены (итог CI
    возвращается до них) — итог зелёный и записи `checks_local компонента`
    нет; либо проверка красит «неизвестно» в красный — `is_unknown` ложно.
    """
    s = stand
    write_entry(s, mode, checks_local=True)
    if ci_case == "unknown":
        set_ci(s, "manual")
    run, added = suite(s)
    assert acceptance.CHECKS_LOCAL_ACTION in added, f"{added!r}; зерно: {s.seed}"
    if ci_case == "green":
        assert run.outcome == acceptance.FULL_SUITE_RED, \
            f"{run.outcome} {run.detail!r}; зерно: {s.seed}"
        assert not acceptance.is_unknown(run)
    else:
        assert_unknown(s, run, f"{mode}/checks_local")
