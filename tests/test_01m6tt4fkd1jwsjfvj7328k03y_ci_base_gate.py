"""Источник отчёта базы гейта исходов `full_suite: ci` — ветка `ci_base_branch` (`ci_base: branch`): отправка базы, ожидание её отчёта на `verifying`, очередь отправок проекта, ранний запуск на входе в `in_dev`, гейт мержа; без `ci_base` и при `ci_base: main` — прежнее поведение.

Группа: долгоживущий
Красен до реализации: поля компонента `ci_base`, `ci_base_branch`, `ci_base_push_options` загрузчик записей отказывает «неизвестное поле» — запись проекта сценария не читается, гейт исходов на `verifying` не судит; записи без поля `ci_base` (AC-3 без поля, AC-14) зелёные с рождения: отказ «нет отчёта базы» без отправки.

Провалидировано временным стабом реализации (удалён, не закоммичен):
поля записи, отправка базы через `gitcmd.in_repo` с очередью по журналу,
действие ожидания базы в `verifying_gate`, классификация годности базы,
ранняя отправка на выходе из `tests_writing`, отказ подготовки на мерже —
все методы файла зелёные; мутации «к отправке добавлены
`policy.push_options`», «очереди нет», «давность отправки не
учитывается», «эскалировать при отказе отправки», «ждать при
окончательной негодности» — красные.

Стенд — песочница гейта исходов `full_suite: ci` на `verifying`
(`VerifyingBox` из `tests/test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate.py`
поверх `tests.merge_outcome_sandbox.MergeOutcomeSandbox`): настоящий git,
учебный внешний проект `forge: gitlab` (`merge_gate: operator` — белого
списка нет, отправка из клона идёт в его голый `origin` как есть),
единственный компонент `junit-xml` с `full_suite: ci`, `ci_job` и
(по сценарию) `ci_base`. Хостинг подменён целиком (`ScenarioForge`):
задания, статусы и отчёты по sha задаёт тест; отчёт базы появляется, когда
тест его публикует, — как после отработавшего задания CI.

Отправка git — шпион `subprocess.run` песочницы, расширенный здесь: каждый
вызов `git … push …` записывается (`pushes`) и исполняется настоящим git
(ветку в голом `origin` тест читает `ls-remote`), либо отвечает отказом
сценария (`push_fail` — сбой git, отказ хука). Отказ белого списка —
настоящий: предикат `targets.push_whitelisted` подменён на «да», и единая
точка отправки сверяет клон с записью проекта (адрес `origin` клона — не
адрес записи) и отказывает до запуска git.

Опрос `verifying` — `fsm.cmd_advance`; задачи заводятся сразу в `verifying`
(`direct_task`) — без входа в `in_dev` из `tests_writing`, то есть без
ранней отправки; ранний запуск проверяется настоящим выходом из
`tests_writing` (`new_task`). Потолок `config.VERIFYING_CEILING_SEC` на
время теста огромен; исчерпание — потолок 0; возраст отправки предыдущей
задачи старше потолка — подменённые часы журнала (время её записей
сдвинуто в прошлое дальше потолка).

Имена проектов, компонентов, заданий, ветки отчёта базы и параметров
отправки — из `random`; зерно печатается и входит в текст каждого провала.
"""
import re
import subprocess
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

import pytest

from orchestrator import config, forge, store, targets
from orchestrator.advance_gates import outcome_integrity
from tests.fixtures import _sandbox
from tests.outcome_gate_sandbox import ENTRY_HEAD, flow, py_source
from tests.sandbox import make_project_repo
from tests.test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate import (
    UNFINISHED, VerifyingBox)

WAIT_BASE = "гейт исходов на verifying: ожидание отчёта CI базы"
WAIT_HEAD = outcome_integrity.PENDING_ACTION
PASSED = outcome_integrity.PASSED_ACTION
MERGE_PREPARE = outcome_integrity.MERGE_PREPARE_ACTION
NO_BASE_REPORT = "нет отчёта базы"
CANCELED = "задание отменено"
MERGE_WAIT = "отчёт базы ожидается, повтори approve"
CEILING = "потолок ожидания CI в verifying исчерпан"
REFUSED = "отправка отказана"
ESCALATED = "state -> escalated"
TO_REVIEW = "state -> review"
GLOBALS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace",
                      "--config-env", "--exec-path", "--super-prefix")


def push_words(argv) -> list | None:
    """Слова после подкоманды `push` вызова git `argv`; None — не отправка."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return None
    words = [str(a) for a in argv]
    if words[0].rsplit("/", 1)[-1] != "git":
        return None
    i = 1
    while i < len(words) and words[i].startswith("-"):
        i += 2 if words[i] in GLOBALS_WITH_VALUE else 1
    if i >= len(words) or words[i] != "push":
        return None
    return words[i + 1:]


def parse_push(rest: list) -> tuple:
    """(параметры `-o`, прочие флаги, [(источник, назначение)]) слов
    отправки."""
    options, flags, positional = [], [], []
    i = 0
    while i < len(rest):
        word = rest[i]
        if word in ("-o", "--push-option"):
            options.append(rest[i + 1] if i + 1 < len(rest) else "")
            i += 2
            continue
        if word.startswith("--push-option="):
            options.append(word.split("=", 1)[1])
        elif word.startswith("-o") and len(word) > 2:
            options.append(word[2:])
        elif word.startswith("-"):
            flags.append(word)
        else:
            positional.append(word)
        i += 1
    specs = []
    for spec in positional[1:]:
        src, _colon, dst = spec.removeprefix("+").partition(":")
        specs.append((src, dst.removeprefix("refs/heads/") or src))
    return options, flags, specs


class BaseBox(VerifyingBox):
    """Песочница гейта исходов `ci` со шпионом отправок git и проектом,
    чей компонент несёт поля `ci_base`."""

    def setUp(self):
        self.pushes: list = []
        self.push_fail = None
        super().setUp()

    def spy_run(self, argv, *args, **kwargs):
        rest = push_words(argv)
        if rest is not None:
            self.pushes.append(rest)
            reason = self.push_fail(rest) if self.push_fail else None
            if reason is not None:
                text = bool(kwargs.get("text") or kwargs.get("encoding")
                            or kwargs.get("universal_newlines"))
                return subprocess.CompletedProcess(
                    list(argv), 1, "" if text else b"",
                    reason if text else reason.encode())
        return super().spy_run(argv, *args, **kwargs)

    # --- проект ---------------------------------------------------------

    def ci_project(self, ci_base: str | None = "branch",
                   n: int = 3) -> SimpleNamespace:
        """Учебный проект GitLab с единственным компонентом `full_suite: ci`;
        `ci_base` — значение поля (None — поля нет); при `branch` — ветка
        отчёта базы и её параметры отправки. У записи свой
        `push_options` (параметры веток задач)."""
        name = f"g{self.word()}"
        head = ENTRY_HEAD.format(name=name).replace("forge: github",
                                                    "forge: gitlab")
        policy_options = [f"P{self.word().upper()}=1",
                          f"ci.variable=Q{self.word().upper()}=2"]
        base_options = [f"ci.variable=B{self.word().upper()}=1",
                        f"C{self.word().upper()}=x"]
        cbb = f"artel-base-{self.word()}"
        comp, job = f"c{self.word()}", f"t{self.word()}"
        fields = self.component_fields(job, "", "ci")
        if ci_base is not None:
            fields["ci_base"] = ci_base
        if ci_base == "branch":
            fields["ci_base_branch"] = cbb
            fields["ci_base_push_options"] = flow(base_options)
        lines = [head, f"    push_options: {flow(policy_options)}\n",
                 "    components:\n", f"      {comp}:\n"]
        lines += [f"        {k}: {v}\n" for k, v in fields.items()]
        rel = f"tests/test_{self.word()}.py"
        names = [self.py_name() for _ in range(n)]
        self.append_entry("".join(lines))
        clone = make_project_repo(name)
        # Голый `origin` принимает параметры отправки `-o`, как сервер GitLab.
        self.git("-C", str(config.PROJECTS / name / "origin.git"), "config",
                 "receive.advertisePushOptions", "true")
        self.commit_project(clone, {"app.py": "APP = 'base'\n",
                                    rel: py_source(names)})
        self.clones[name] = clone
        first = SimpleNamespace(comp=comp, job=job, mode="ci", rel=rel,
                                names=names, root="")
        return SimpleNamespace(name=name, clone=clone, comps=[first], comp=comp,
                               job=job, rel=rel, names=names, kind="junit",
                               layout="", single=True, cbb=cbb,
                               base_options=base_options,
                               policy_options=policy_options)

    def vtask(self, project):
        """Задача проекта, заведённая сразу в `verifying` (без ранней
        отправки); голова — последний коммит кодовой ветки."""
        t = self.direct_task(project, "verifying")
        t.sent = self.head(t)
        self.current = t.id
        return t

    def green_head(self, t) -> int:
        comp = t.project.comps[0]
        return self.publish(t.sent, comp.job, "success", self.green(comp))

    def reset_jobs(self, sha: str, job: str) -> None:
        self.forge.jobs[sha] = [j for j in self.forge.jobs.get(sha, [])
                                if j.name != job]
        self.forge.reports.pop((sha, job), None)

    # --- наблюдения -----------------------------------------------------

    def base_pushes(self, project, sha: str | None = None) -> list:
        """(параметры, флаги, источник) отправок в `ci_base_branch`
        проекта; `sha` — только с этим источником."""
        found = []
        for rest in self.pushes:
            options, flags, specs = parse_push(rest)
            for src, dst in specs:
                if dst == project.cbb and (sha is None or src == sha):
                    found.append((options, flags, src))
        return found

    def pushes_of(self, sha: str) -> list:
        """Отправки git, у которых `sha` — источник refspec."""
        return [rest for rest in self.pushes
                if any(src == sha for src, _dst in parse_push(rest)[2])]

    def origin_ref(self, project, branch: str) -> str:
        text = self.git("-C", str(project.clone), "ls-remote", "origin",
                        f"refs/heads/{branch}")
        return text.split()[0] if text.split() else ""

    def journal_text(self, t) -> str:
        return "\n".join(f"{r['action']} {r['detail'] or ''}"
                         for r in store.task_steps(self.conn, t.id))

    @staticmethod
    def rows_text(rows: list) -> str:
        return "\n".join(f"{r['action']} {r['detail'] or ''}" for r in rows)

    def report(self, rows, output) -> str:
        return self.why(rows, output) + f"\nотправки git: {self.pushes}"

    def age_journal(self, t) -> None:
        """Подменённые часы: записи журнала задачи `t` — старше потолка
        `config.VERIFYING_CEILING_SEC`."""
        old = datetime.now(timezone.utc) - timedelta(
            seconds=config.VERIFYING_CEILING_SEC + 3600)
        self.conn.execute("UPDATE steps SET ts=? WHERE task_id=?",
                          (old.strftime("%Y-%m-%d %H:%M:%SZ"), t.id))
        self.conn.commit()


@pytest.fixture
def box():
    """Стенд BaseBox после setUp."""
    yield from _sandbox(BaseBox)


def sent_line(sha: str, branch: str) -> re.Pattern:
    return re.compile(rf"отчёт базы: отправка {sha[:7]}[0-9a-f]* в "
                      rf"{re.escape(branch)}")


def job_line(job_id: int, sha: str) -> re.Pattern:
    return re.compile(rf"отчёт базы: задание {job_id} коммита {sha[:7]}[0-9a-f]*")


def waits_for_base(box, t, rows, output) -> None:
    """Опрос — ожидание отчёта базы: задача в `verifying`, ни `review`, ни
    `escalated`, записи прохода нет, есть действие ожидания базы и нет
    действия ожидания головы."""
    actions = box.actions(rows)
    assert box.state(t) == "verifying", box.report(rows, output)
    assert ESCALATED not in actions and TO_REVIEW not in actions, \
        box.report(rows, output)
    assert PASSED not in actions, box.report(rows, output)
    assert WAIT_BASE in actions, box.report(rows, output)
    assert WAIT_HEAD not in actions, box.report(rows, output)


def escalated_detail(box, t, rows, output) -> str:
    assert box.state(t) == "escalated", box.report(rows, output)
    detail = box.state_details(rows, ESCALATED)
    assert detail, box.report(rows, output)
    return detail[-1]


# ---------------------------------------------------------------- AC-1


def test_ac1_missing_base_report_pushes_base_then_compares(box):
    """`ci_base: branch`, у точки ответвления `B` нет ни отчёта, ни задания `ci_job`: опрос `verifying` отправляет `B` в `ci_base_branch` с `ci_base_push_options` и без `policy.push_options`; после появления отчёта `B` гейт сравнивает отчёты и пропускает задачу в `review`.

    Сценарий: проект GitLab с компонентом `full_suite: ci`, `ci_base:
    branch` и своими `push_options` записи; задача сразу в `verifying`,
    отчёт головы зелёный, у `B` (`diff_base`) заданий нет. Опрос 1: среди
    отправок git — refspec `<B>:refs/heads/<ci_base_branch>`, его
    параметры `-o` — все `ci_base_push_options` и ни одного из
    `push_options` записи; ветка в голом `origin` стоит на `B`; задача в
    `verifying`. Публикуется задание `ci_job` коммита `B` с зелёным
    отчётом. Опрос 2: задача в `review`, запись прохода гейта называет
    `B` и `id` задания базы.

    Ловит мутацию: «отправка не выполнена» — отправки `B` нет, ветки в
    `origin` нет; «к отправке добавлены `policy.push_options`» — среди
    `-o` отправки есть параметр записи; отчёт базы берётся не у `B` —
    запись прохода без `B`.
    """
    project = box.ci_project()
    t = box.vtask(project)
    point = box.base(t)
    box.green_head(t)
    rows, output = box.poll(t)
    pushed = box.base_pushes(project, point)
    assert pushed, box.report(rows, output)
    options = pushed[-1][0]
    for option in project.base_options:
        assert option in options, box.report(rows, output)
    for option in project.policy_options:
        assert option not in options, box.report(rows, output)
    assert box.origin_ref(project, project.cbb) == point, box.report(rows, output)
    assert box.state(t) == "verifying", box.report(rows, output)
    base_id = box.publish(point, project.job, "success",
                          box.green(project.comps[0]))
    rows, output = box.poll(t)
    assert box.state(t) == "review", box.report(rows, output)
    detail = box.details(rows, PASSED)
    assert detail, box.report(rows, output)
    assert point[:12] in detail[-1], box.report(rows, output)
    assert re.search(rf"(?<!\d){base_id}(?!\d)", detail[-1]), \
        box.report(rows, output)


# ---------------------------------------------------------------- AC-2


def test_ac2_existing_base_report_no_push(box):
    """`ci_base: branch` и отчёт базы `B` уже есть: опрос `verifying` проходит гейт без единой отправки в `ci_base_branch`.

    Сценарий: проект `ci_base: branch`; задача сразу в `verifying`;
    зелёные задания `ci_job` с отчётами у головы и у `B`. Опрос: задача в
    `review`; отправок git с назначением `ci_base_branch` нет, ветки в
    `origin` нет.

    Ловит мутацию: отправка базы делается при каждом опросе (без проверки
    наличия отчёта) — отправка в `ci_base_branch` есть.
    """
    project = box.ci_project()
    t = box.vtask(project)
    point = box.base(t)
    box.green_head(t)
    box.publish(point, project.job, "success", box.green(project.comps[0]))
    rows, output = box.poll(t)
    assert box.state(t) == "review", box.report(rows, output)
    assert box.base_pushes(project) == [], box.report(rows, output)
    assert box.origin_ref(project, project.cbb) == "", box.report(rows, output)


# ---------------------------------------------------------------- AC-3


@pytest.mark.parametrize("ci_base", ["main", None])
def test_ac3_main_or_absent_ci_base_keeps_old_refusal(box, ci_base):
    """`ci_base: main` или поле не задано, отчёта базы нет: прежний отказ «нет отчёта базы» и эскалация, отправки базы нет.

    Сценарий (по случаю): проект `full_suite: ci` с `ci_base: main` либо
    без поля; задача сразу в `verifying`, отчёт головы зелёный, у `B`
    заданий нет. Опрос: задача в `escalated`, запись перехода содержит
    «нет отчёта базы»; ни одной отправки git с источником `B`.

    Ловит мутацию: отправка базы и ожидание включены не только при
    `ci_base: branch` (умолчание `main` трактуется как `branch`) —
    отправка `B` есть, задача ждёт в `verifying`.
    """
    project = box.ci_project(ci_base)
    t = box.vtask(project)
    point = box.base(t)
    box.green_head(t)
    rows, output = box.poll(t)
    detail = escalated_detail(box, t, rows, output)
    assert NO_BASE_REPORT in detail, box.report(rows, output)
    assert box.pushes_of(point) == [], box.report(rows, output)


# ---------------------------------------------------------------- AC-4


def test_ac4_unfinished_base_job_waits_without_second_push(box):
    """Задание `ci_job` базы `B` есть и не завершено: две проверки подряд после одной отправки — обе ожидание, отправка `B` ровно одна.

    Сценарий: проект `ci_base: branch`, задача сразу в `verifying`, отчёт
    головы зелёный. Опрос 1 отправляет `B`. Публикуется задание `ci_job`
    коммита `B` в случайном незавершённом статусе без отчёта. Опросы 2 и
    3: каждый — ожидание (задача в `verifying`, действие ожидания отчёта
    базы, не эскалация); всего отправок `B` в `ci_base_branch` — одна.

    Ловит мутацию: отправка делается всякий раз, когда отчёта `B` нет
    (не смотрит на задание) — отправок три; незавершённое задание базы —
    эскалация сразу.
    """
    project = box.ci_project()
    t = box.vtask(project)
    point = box.base(t)
    box.green_head(t)
    rows, output = box.poll(t)
    assert len(box.base_pushes(project, point)) == 1, box.report(rows, output)
    box.publish(point, project.job, box.rng.choice(UNFINISHED), None)
    for _ in range(2):
        rows, output = box.poll(t)
        waits_for_base(box, t, rows, output)
    assert len(box.base_pushes(project, point)) == 1, box.report(rows, output)


# ---------------------------------------------------------------- AC-5


def test_ac5_tests_writing_exit_pushes_base_once(box):
    """Вход в `in_dev` из `tests_writing`: одна попытка отправки базы `diff_base` в `ci_base_branch`, переход в `in_dev` выполнен без отчёта базы.

    Сценарий: проект `ci_base: branch`; задача проходит настоящий выход из
    `tests_writing`; у `B` нет ни задания, ни отчёта. Задача в `in_dev`;
    отправок `B` в `ci_base_branch` за выход — ровно одна; ветка в
    `origin` стоит на `B`.

    Ловит мутацию: ранняя отправка не сделана — отправок нет; переход
    ждёт отчёт базы — задача не в `in_dev`; попытка повторяется в цикле —
    отправок больше одной.
    """
    project = box.ci_project()
    box.pushes.clear()
    t = box.new_task(project)
    point = box.base(t)
    assert box.state(t) == "in_dev", box.note(f"отправки: {box.pushes}")
    assert len(box.base_pushes(project, point)) == 1, box.note(
        f"отправки: {box.pushes}")
    assert box.origin_ref(project, project.cbb) == point, box.note(
        f"отправки: {box.pushes}")


def test_ac5_busy_queue_skips_early_push(box):
    """Очередь отправок проекта занята (задание предыдущей отправки не появилось): на входе в `in_dev` второй задачи попытки нет, переход выполнен.

    Сценарий: проект `ci_base: branch`; первая задача выходит из
    `tests_writing` (её база отправлена, задания у неё нет); `main`
    проекта уходит вперёд; вторая задача выходит из `tests_writing` с
    другой базой. Вторая задача в `in_dev`; отправок её базы нет; ветка
    в `origin` по-прежнему на базе первой.

    Ловит мутацию: ранняя отправка не смотрит на очередь — база второй
    задачи отправлена, ветка в `origin` сдвинута.
    """
    project = box.ci_project()
    first = box.new_task(project)
    first_base = box.base(first)
    box.main_commit(project)
    second = box.new_task(project)
    second_base = box.base(second)
    assert second_base != first_base, box.note("база второй задачи та же")
    assert box.state(second) == "in_dev", box.note(f"отправки: {box.pushes}")
    assert box.base_pushes(project, second_base) == [], box.note(
        f"отправки: {box.pushes}")
    assert box.origin_ref(project, project.cbb) == first_base, box.note(
        f"отправки: {box.pushes}")


@pytest.mark.parametrize("failure", ["сбой git", "отказ хука",
                                     "отказ белого списка"])
def test_ac5_failed_early_push_keeps_transition_and_journals(box, failure):
    """Ранняя отправка базы отказана (сбой git, отказ хука, отказ белого списка): переход в `in_dev` выполнен, причина — в журнале задачи.

    Сценарий (по случаю): проект `ci_base: branch`; отправка в
    `ci_base_branch` отвечает (а) кодом 128 с текстом сбоя git со
    случайным словом; (б) кодом 1 с текстом отказа хука `pre-push`
    со случайным словом; (в) настоящим отказом белого списка единой точки
    (предикат `targets.push_whitelisted` подменён на «да», адрес `origin`
    клона — не адрес записи). Задача проходит выход из `tests_writing`:
    состояние `in_dev`; журнал задачи несёт слово причины (а, б) либо
    отказ единой точки «отправка отказана» (в).

    Ловит мутацию: сбой ранней отправки останавливает переход (задача
    остаётся в `tests_writing`) или причина сбоя не пишется в журнал.
    """
    project = box.ci_project()
    word = box.word()
    patcher = None
    if failure == "отказ белого списка":
        patcher = mock.patch.object(targets, "push_whitelisted",
                                    lambda entry: True)
        needle = REFUSED
    else:
        needle = word
        text = (f"fatal: сбой отправки {word}\n" if failure == "сбой git" else
                f"pre-push (target-human): refs/heads/{project.cbb}: {word}\n")
        box.push_fail = (lambda rest: text if any(
            dst == project.cbb for _s, dst in parse_push(rest)[2]) else None)
    if patcher is not None:
        patcher.start()
    try:
        t = box.new_task(project)
    finally:
        if patcher is not None:
            patcher.stop()
    assert box.state(t) == "in_dev", box.note(f"отправки: {box.pushes}")
    assert needle in box.journal_text(t), box.note(
        f"журнал: {box.journal_text(t)}\nотправки: {box.pushes}")


def test_ac5_shifted_base_pushed_on_verifying(box):
    """База сдвинулась подтяжкой `main` до `verifying`: опрос `verifying` отправляет новую базу и ждёт её отчёта, отчёт прежней базы не засчитан.

    Сценарий: проект `ci_base: branch`; задача выходит из `tests_writing`
    (отправлена база `B1`); `main` проекта уходит вперёд, и в кодовую
    ветку подтянут `main` (`git merge origin/main` в рабочей копии) —
    `diff_base` теперь `B2`; шаг `developer`, задача в `verifying`. У `B1`
    зелёный отчёт задания `ci_job`, у `B2` заданий нет, отчёт головы
    зелёный. Опрос: отправка `B2` в `ci_base_branch`; задача в
    `verifying` с ожиданием отчёта базы; записи прохода нет.

    Ловит мутацию: база отправляется только на входе в `in_dev` — на
    `verifying` отправки `B2` нет; гейт берёт отчёт прежней базы `B1` —
    задача в `review`.
    """
    project = box.ci_project()
    t = box.new_task(project)
    first_base = box.base(t)
    box.main_commit(project)
    box.git("-C", str(t.wt), "merge", "-q", "--no-edit",
            f"origin/{config.MAIN_BRANCH}")
    box.to_verifying(t)
    point = box.base(t)
    assert point != first_base, box.note("база не сдвинулась")
    box.publish(first_base, project.job, "success", box.green(project.comps[0]))
    box.green_head(t)
    rows, output = box.poll(t)
    assert box.base_pushes(project, point), box.report(rows, output)
    waits_for_base(box, t, rows, output)


# ---------------------------------------------------------------- AC-6


def two_tasks(box) -> tuple:
    """Проект `ci_base: branch` и две задачи в `verifying` с разными
    базами, отчёты голов зелёные."""
    project = box.ci_project()
    first = box.vtask(project)
    box.main_commit(project)
    second = box.vtask(project)
    b1, b2 = box.base(first), box.base(second)
    assert b1 != b2, box.note("базы задач совпали")
    box.green_head(first)
    box.green_head(second)
    return project, first, second, b1, b2


@pytest.mark.parametrize("held, released", [(None, "running"),
                                            ("created", "success"),
                                            ("pending", "failed")])
def test_ac6_second_push_waits_for_first_job(box, held, released):
    """Отправки двух задач проекта в `ci_base_branch` — по одной: пока задания первого sha нет или оно `created`/`pending`, вторая отложена; при `running` или завершённом — выполнена; отчёт первой базы читается и после ухода ветки на второй sha.

    Сценарий (по случаю): две задачи одного проекта `ci_base: branch` в
    `verifying` с базами `B1` ≠ `B2`. Опрос первой — отправка `B1`.
    Задание `ci_job` коммита `B1`: нет / `created` / `pending`. Опрос
    второй: отправки `B2` нет, задача в `verifying`. Задание `B1` —
    `running` / `success` / `failed`. Опрос второй: отправка `B2` есть,
    ветка в `origin` на `B2`. Задание `B1` — `success` с зелёным отчётом;
    опрос первой: задача в `review`, запись прохода называет `B1`.

    Ловит мутацию: очереди нет — `B2` отправлена сразу, ветка ушла с
    `B1` до запуска его задания; очередь держит и `running` — `B2` не
    отправлена; отчёт базы читается по ветке, а не по sha, — после сдвига
    ветки первая задача не проходит.
    """
    project, first, second, b1, b2 = two_tasks(box)
    rows, output = box.poll(first)
    assert box.base_pushes(project, b1), box.report(rows, output)
    if held is not None:
        box.publish(b1, project.job, held, None)
    rows, output = box.poll(second)
    assert box.base_pushes(project, b2) == [], box.report(rows, output)
    assert box.state(second) == "verifying", box.report(rows, output)
    box.reset_jobs(b1, project.job)
    report = None if released == "running" else box.green(project.comps[0])
    box.publish(b1, project.job, released, report)
    rows, output = box.poll(second)
    assert box.base_pushes(project, b2), box.report(rows, output)
    assert box.origin_ref(project, project.cbb) == b2, box.report(rows, output)
    box.reset_jobs(b1, project.job)
    box.publish(b1, project.job, "success", box.green(project.comps[0]))
    rows, output = box.poll(first)
    assert box.state(first) == "review", box.report(rows, output)
    detail = box.details(rows, PASSED)
    assert detail and b1[:12] in detail[-1], box.report(rows, output)


def test_ac6_queue_released_after_ceiling_without_first_job(box):
    """Хостинг никогда не показывает задание первого sha: после истечения `config.VERIFYING_CEILING_SEC` от первой отправки (подменённые часы) вторая отправка выполнена, тест не зависает.

    Сценарий: две задачи проекта `ci_base: branch` в `verifying`, базы
    `B1` ≠ `B2`; задания у `B1` нет никогда. Опрос первой — отправка
    `B1`; опрос второй — отправки `B2` нет. Записи журнала первой задачи
    сдвинуты в прошлое дальше потолка. Опрос второй: отправка `B2` есть,
    ветка в `origin` на `B2`.

    Ловит мутацию: давность предыдущей отправки не учитывается — очередь
    держится вечно, `B2` не отправлена.
    """
    project, first, second, b1, b2 = two_tasks(box)
    rows, output = box.poll(first)
    assert box.base_pushes(project, b1), box.report(rows, output)
    rows, output = box.poll(second)
    assert box.base_pushes(project, b2) == [], box.report(rows, output)
    box.age_journal(first)
    rows, output = box.poll(second)
    assert box.base_pushes(project, b2), box.report(rows, output)
    assert box.origin_ref(project, project.cbb) == b2, box.report(rows, output)


# ---------------------------------------------------------------- AC-7


PASSING = ("задания нет", "незавершён", "статус не прочитан", "перезапуск",
           "отчёт не разобран")


def base_case(box, project, point, case: str):
    """Состояние задания `ci_job` базы по случаю проходящей негодности;
    `id` задания или None."""
    comp = project.comps[0]
    if case == "задания нет":
        box.jobs_of(point)
        return None
    if case == "незавершён":
        return box.publish(point, comp.job, box.rng.choice(UNFINISHED), None)
    if case == "отчёт не разобран":
        value = box.publish(point, comp.job, "success", None)
        box.forge.report_reasons[(point, comp.job)] = \
            f"отчёт не разобран: {box.word()}"
        return value
    value = box.publish(point, comp.job, "success", box.green(comp))
    if case == "статус не прочитан":
        box.forge.status_fail[(point, comp.job)] = f"HTTP 502 {box.word()}"
    else:
        box.forge.restart.add((point, comp.job))
    return value


@pytest.mark.parametrize("case", PASSING)
def test_ac7_passing_unfitness_of_base_waits(box, case):
    """Проходящая негодность отчёта базы после отправки — задания нет, не завершено, статус не прочитан, перезапуск во время чтения, отчёт не разобран: ожидание (не эскалация) с действием ожидания отчёта базы; в журнале — запись отправки `B` и, при найденном задании, запись задания `B`.

    Сценарий (по случаю): проект `ci_base: branch`, задача сразу в
    `verifying`, отчёт головы зелёный. Опрос 1 отправляет `B`. Состояние
    задания `ci_job` коммита `B` — по случаю. Опрос 2: задача в
    `verifying`, действие «гейт исходов на verifying: ожидание отчёта CI
    базы», нет действия ожидания головы, нет эскалации; журнал задачи
    содержит «отчёт базы: отправка <B> в <ci_base_branch>»; у
    незавершённого задания и неразобранного отчёта — «отчёт базы: задание
    <id> коммита <B>».

    Ловит мутацию: «эскалировать при проходящей» — негодность базы
    сразу эскалирует (прежний отказ «нет отчёта базы»); ожидание базы
    пишется действием ожидания головы.
    """
    project = box.ci_project()
    t = box.vtask(project)
    point = box.base(t)
    box.green_head(t)
    box.poll(t)
    job_id = base_case(box, project, point, case)
    rows, output = box.poll(t)
    waits_for_base(box, t, rows, output)
    text = box.journal_text(t)
    assert sent_line(point, project.cbb).search(text), box.report(rows, output)
    if case in ("незавершён", "отчёт не разобран"):
        assert job_line(job_id, point).search(text), box.report(rows, output)


@pytest.mark.parametrize("failure", ["сбой git", "отказ хука",
                                     "отказ белого списка"])
def test_ac7_refused_base_push_waits_and_retries(box, failure):
    """Отправка базы на `verifying` отказана (сбой git, отказ хука, отказ белого списка): ожидание, причина — в журнале задачи, на следующей проверке — повторная попытка.

    Сценарий (по случаю): проект `ci_base: branch`, задача сразу в
    `verifying`, отчёт головы зелёный, у `B` заданий нет; отправка в
    `ci_base_branch` отказана (а) сбоем git, (б) отказом хука — оба со
    случайным словом; (в) настоящим отказом белого списка (предикат
    подменён, адрес `origin` клона — не адрес записи). Опрос 1 и опрос 2:
    каждый — ожидание отчёта базы (не эскалация); в записях каждого опроса
    — причина отказа (слово сценария либо «отправка отказана»), то есть
    второй опрос снова пытался отправить; у (а) и (б) шпион видел
    отправку `B` в каждом опросе.

    Ловит мутацию: «эскалировать при отказе отправки на verifying» —
    первый опрос эскалирует; повторной попытки нет — второй опрос без
    отправки и без причины.
    """
    project = box.ci_project()
    t = box.vtask(project)
    point = box.base(t)
    box.green_head(t)
    word = box.word()
    if failure == "отказ белого списка":
        patcher = mock.patch.object(targets, "push_whitelisted",
                                    lambda entry: True)
        patcher.start()
        box.addCleanup(patcher.stop)
        needle = REFUSED
    else:
        needle = word
        text = (f"fatal: сбой отправки {word}\n" if failure == "сбой git" else
                f"pre-push (target-human): refs/heads/{project.cbb}: {word}\n")
        box.push_fail = (lambda rest: text if any(
            dst == project.cbb for _s, dst in parse_push(rest)[2]) else None)
    for number in (1, 2):
        before = len(box.base_pushes(project, point))
        rows, output = box.poll(t)
        waits_for_base(box, t, rows, output)
        assert needle in box.rows_text(rows), box.note(
            f"опрос {number}: ") + box.report(rows, output)
        if failure != "отказ белого списка":
            assert len(box.base_pushes(project, point)) > before, box.note(
                f"опрос {number}: ") + box.report(rows, output)


@pytest.mark.parametrize("status", ["canceled", "skipped", "manual",
                                    "allow_failure"])
def test_ac7_final_unfitness_of_base_escalates_at_once(box, status):
    """Окончательная негодность задания базы — `canceled`, `skipped`, `manual`, `failed` с `allow_failure`: сразу отказ «нет отчёта базы: <причина>» и эскалация без ожидания потолка; у `canceled` — причина «задание отменено» и без повторной отправки.

    Сценарий (по случаю): проект `ci_base: branch`, задача сразу в
    `verifying`, отчёт головы зелёный. Опрос 1 отправляет `B`.
    Публикуется задание `ci_job` коммита `B` в статусе случая (с
    отчётом; `allow_failure` — `failed` с правом падать). Опрос 2 при
    огромном потолке: задача в `escalated`, запись перехода содержит «нет
    отчёта базы: »; у `canceled` — и «задание отменено», а отправок `B`
    по-прежнему одна; журнал называет задание `B`.

    Ловит мутацию: «ждать при окончательной негодности» — задача остаётся
    в `verifying`; отменённое задание запускает повторную отправку `B`;
    `failed` с `allow_failure` засчитан годной базой — `review`.
    """
    project = box.ci_project()
    comp = project.comps[0]
    t = box.vtask(project)
    point = box.base(t)
    box.green_head(t)
    box.poll(t)
    assert len(box.base_pushes(project, point)) == 1, box.note(
        f"отправки: {box.pushes}")
    if status == "allow_failure":
        job_id = box.publish(point, comp.job, "failed", box.green(comp),
                             allow_failure=True)
    else:
        job_id = box.publish(point, comp.job, status, box.green(comp))
    rows, output = box.poll(t)
    detail = escalated_detail(box, t, rows, output)
    assert f"{NO_BASE_REPORT}: " in detail, box.report(rows, output)
    assert job_line(job_id, point).search(box.journal_text(t)), \
        box.report(rows, output)
    if status == "canceled":
        assert CANCELED in detail, box.report(rows, output)
        assert len(box.base_pushes(project, point)) == 1, box.report(rows, output)


@pytest.mark.parametrize("case", ["незавершён", "сбой git"])
def test_ac7_passing_unfitness_at_ceiling_escalates_with_base_reason(box, case):
    """Проходящая негодность отчёта базы при исчерпанном потолке (подменённые часы): прежняя эскалация «потолок ожидания CI в verifying исчерпан …», её `detail` содержит «нет отчёта базы: <причина>».

    Сценарий (по случаю): проект `ci_base: branch`, задача сразу в
    `verifying`, отчёт головы зелёный; (а) после отправки `B` задание
    `ci_job` коммита `B` не завершено; (б) отправка `B` отказывает сбоем
    git. Опрос 1 при огромном потолке — ожидание; опрос 2 при потолке 0:
    задача в `escalated`, запись перехода содержит «потолок ожидания CI в
    verifying исчерпан» и «нет отчёта базы: ».

    Ловит мутацию: по потолку эскалация с причиной без «нет отчёта базы»
    (последний статус — прежний текст ожидания CI); ожидание базы не
    подчиняется потолку — задача остаётся в `verifying`.
    """
    project = box.ci_project()
    t = box.vtask(project)
    point = box.base(t)
    box.green_head(t)
    if case == "сбой git":
        box.push_fail = (lambda rest: "fatal: сбой отправки\n" if any(
            dst == project.cbb for _s, dst in parse_push(rest)[2]) else None)
    rows, output = box.poll(t)
    waits_for_base(box, t, rows, output)
    if case == "незавершён":
        box.publish(point, project.job, box.rng.choice(UNFINISHED), None)
    with mock.patch.object(config, "VERIFYING_CEILING_SEC", 0):
        rows, output = box.poll(t)
    detail = escalated_detail(box, t, rows, output)
    assert CEILING in detail, box.report(rows, output)
    assert f"{NO_BASE_REPORT}: " in detail, box.report(rows, output)


def test_ac7_failed_base_job_with_report_is_fit(box):
    """Задание базы `failed` с разобранным отчётом — годная база: сравнение идёт, задача в `review`.

    Сценарий: проект `ci_base: branch`, задача сразу в `verifying`, отчёт
    головы зелёный. Опрос 1 отправляет `B`. Публикуется задание `ci_job`
    коммита `B` в статусе `failed` с отчётом, где один тест красен
    (`allow_failure` нет). Опрос 2: задача в `review`, запись прохода
    называет `B` и `id` задания базы; журнал — запись задания `B`.

    Ловит мутацию: `failed` базы считается негодным (свёртка «не
    success») — эскалация или ожидание вместо сравнения.
    """
    project = box.ci_project()
    comp = project.comps[0]
    t = box.vtask(project)
    point = box.base(t)
    box.green_head(t)
    box.poll(t)
    job_id = box.publish(point, comp.job, "failed",
                         box.red(comp, box.rng.choice(comp.names)))
    rows, output = box.poll(t)
    assert box.state(t) == "review", box.report(rows, output)
    detail = box.details(rows, PASSED)
    assert detail and point[:12] in detail[-1], box.report(rows, output)
    assert re.search(rf"(?<!\d){job_id}(?!\d)", detail[-1]), \
        box.report(rows, output)
    assert job_line(job_id, point).search(box.journal_text(t)), \
        box.report(rows, output)


# ---------------------------------------------------------------- AC-8


def test_ac8_merge_gate_pushes_merge_base_and_refuses_prepare(box):
    """Гейт мержа при `ci_base: branch` без отчёта и задания у базы мержа: база мержа отправлена, задача осталась на гейте мержа со сбоем подготовки «отчёт базы ожидается, повтори approve».

    Сценарий: проект `ci_base: branch`; задача сразу на `merge_gate`;
    зелёное задание `ci_job` с отчётом у головы; у базы мержа (merge-base
    головы и `main` в `origin`) заданий нет. Гейт исходов окна мержа —
    тот, что зовёт `approve` (`outcome_integrity.merge_gate_escalates` с
    sha `main` из `origin`; сам `approve` пару `gitlab` + `operator`
    учебного проекта до гейта не пускает) — возвращает управление выходом
    `SystemExit`, без ожидания внутри окна мержа: среди отправок —
    отправка базы мержа в `ci_base_branch`; задача на `merge_gate`; запись
    сбоя подготовки гейта мержа содержит «отчёт базы ожидается, повтори
    approve»; записи прохода нет.

    Ловит мутацию: гейт мержа не отправляет базу — отправки нет; отказ с
    прежней причиной «нет отчёта базы» без «ожидается»; задача
    эскалирована вместо отказа подготовки.
    """
    project = box.ci_project()
    comp = project.comps[0]
    t = box.direct_task(project, "merge_gate")
    head = box.head(t)
    main = box.origin_main(t)
    merge_base = box.merge_base(t, main)
    box.publish(head, comp.job, "success", box.green(comp))
    before = len(store.task_steps(box.conn, t.id))
    exited = None
    try:
        outcome_integrity.merge_gate_escalates(box.conn, t.id, "merge_gate",
                                               lambda: main)
    except SystemExit as exc:
        exited = exc
    rows = [dict(r) for r in store.task_steps(box.conn, t.id)[before:]]
    output = str(exited)
    assert exited is not None, box.report(rows, output)
    assert box.base_pushes(project, merge_base), box.report(rows, output)
    assert box.state(t) == "merge_gate", box.report(rows, output)
    found = box.details(rows, MERGE_PREPARE)
    assert found and MERGE_WAIT in found[-1], box.report(rows, output)
    assert PASSED not in box.actions(rows), box.report(rows, output)


# ---------------------------------------------------------------- AC-14


def test_ac14_record_without_ci_base_keeps_gate(box):
    """Запись GitLab без `ci_base`: при отчёте базы — прежний проход гейта в `review`, без отчёта — прежний отказ «нет отчёта базы» и эскалация; отправок базы нет ни там, ни там.

    Сценарий: проект `full_suite: ci` без поля `ci_base`; две задачи
    сразу в `verifying`, отчёты голов зелёные. У базы первой — зелёный
    отчёт задания `ci_job`: опрос ведёт в `review`. У базы второй (после
    сдвига `main`) отчёта нет: опрос — `escalated` с «нет отчёта базы».
    Ни одной отправки git с источником базы любой из задач.

    Ловит мутацию: отправка базы или ожидание её отчёта включены и у
    записи без `ci_base` — отправка есть, вторая задача ждёт в
    `verifying`.
    """
    project = box.ci_project(None)
    first = box.vtask(project)
    b1 = box.base(first)
    box.main_commit(project)
    second = box.vtask(project)
    b2 = box.base(second)
    box.green_head(first)
    box.green_head(second)
    box.publish(b1, project.job, "success", box.green(project.comps[0]))
    rows, output = box.poll(first)
    assert box.state(first) == "review", box.report(rows, output)
    box.current = second.id
    rows, output = box.poll(second)
    detail = escalated_detail(box, second, rows, output)
    assert NO_BASE_REPORT in detail, box.report(rows, output)
    assert box.pushes_of(b1) == [] and box.pushes_of(b2) == [], \
        box.report(rows, output)
