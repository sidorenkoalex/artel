"""Гейт мержа и черновой MR при сбое чтения записи проекта: отказ с причиной вместо пропуска (AC-1, AC-2, AC-3, AC-6, AC-13, AC-17, AC-18, AC-19, AC-20).

Группа: разовый
Красен до реализации: функции-читателя записи у `github_adapter.people_entry` нет (`people_entry` зовёт `targets.target` сам и глотает `TargetsError` в `None`) — поиск шва AC-1/AC-2/AC-3/AC-18/AC-19/AC-20 падает с именем причины; `_awaiting_limit_refuses` при `TargetsError` пропускает предел и открывает MR (AC-6); статус MR `locked`/пустой/`None` проходит к снятию черновика и `awaiting_human` (AC-13). Методы AC-17 — сторожа прежнего пути гейта, зелены и на main.

Почему разовый, хотя свойства — свойства кода: швы подмены, которые
называет SPEC (требование 12), — закрытые имена пульта, которые
долгоживущему файлу запрещены (`scripts/guard.py`, признаки «patch
закрытого»/«закрытый атрибут»): функция-читатель записи `people_entry`
(SPEC не даёт ей имени — её находит `reader_name` по коду `people_entry`),
возврат тела гейта `fsm_merge_gate._cmd_approve_merge_gate` (`("stopped",)`
в AC-1/AC-2/AC-6) и чтение внутри `_awaiting_limit_refuses` (AC-6).
Долгоживущий тест этих свойств — забота разработчика в `tests/`.

Стенд — `Stand` долгоживущего файла доставки через MR
(`tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py`; тем же приёмом его
берёт `tests/test_mr_delivery_units.py`): настоящий git песочницы, клон
внешнего проекта с bare `origin`, запись проекта в локальном слое,
подделка хостинга в `forge.IMPLEMENTATIONS`, шпионы `git`/`gh`.

Окно наблюдения отказа — само тело гейта мержа: обёртка `BodySpy` вокруг
`fsm_merge_gate._cmd_approve_merge_gate` (цикл гейта зовёт его по имени
модуля) снимает до и после тела строку задачи, ссылки клона и bare
`origin`, записи журнала, отправки и слияния шпиона git, вызовы `open_mr`
подделки, и запоминает возврат тела.

Провалидировано временным стабом (удалён, не закоммичен): читатель
записи `people_entry`, отказ места вызова в `fsm_merge_gate` для не-артели,
ловля в `ensure_forge_draft_mr`, отказ `_awaiting_limit_refuses` при
`TargetsError`, отказ `_mr_incident_stops` при статусе вне трёх известных.
"""
import inspect
import random
import sys
import types

import pytest

from orchestrator import (config, forge, fsm_merge_gate, github_adapter, idgen,
                          store, targets)
from orchestrator.advance_gates import tests_writing
from tests import test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery as delivery

NOT_READ = "запись проекта не прочитана:"
AWAITING_NOT_CHECKED = "предел awaiting_human не проверен:"


@pytest.fixture
def stand(real_git):
    return delivery.Stand(real_git)


# ------------------------------------------------------------ помощники


def _code_names(code: types.CodeType) -> set:
    """Глобальные и атрибутные имена кода вместе с вложенными (лямбды,
    генераторы)."""
    names = set(code.co_names)
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            names |= _code_names(const)
    return names


def reader_name() -> str:
    """Имя функции-читателя записи `people_entry` (SPEC, требование 1):
    функция модуля `github_adapter`, которую зовёт `people_entry` и не зовёт
    ни одна другая функция модуля. SPEC имени не задаёт — шов находится по
    коду, а не по догадке об имени."""
    module = github_adapter.__name__

    def own(obj) -> bool:
        return inspect.isfunction(obj) and obj.__module__ == module

    called = [n for n in sorted(_code_names(github_adapter.people_entry.__code__))
              if n != "people_entry" and own(getattr(github_adapter, n, None))]
    elsewhere = set()
    for name, obj in vars(github_adapter).items():
        if own(obj) and name != "people_entry":
            elsewhere |= _code_names(obj.__code__)
    only = [n for n in called if n not in elsewhere]
    assert len(only) == 1, (
        f"функция-читатель записи people_entry не найдена однозначно: "
        f"people_entry зовёт функции модуля {called}, из них только ею — "
        f"{only} (SPEC, требование 1: отдельная функция-читатель в "
        f"github_adapter, которой пользуется только people_entry)")
    return only[0]


def failing_reader(monkeypatch, message: str) -> list:
    """Подменяет функцию-читатель записи `people_entry`: каждый вызов —
    `targets.TargetsError(message)`. Список вызовов."""
    calls: list = []

    def reader(*args, **kwargs):
        calls.append(args)
        raise targets.TargetsError(message)

    monkeypatch.setattr(github_adapter, reader_name(), reader)
    return calls


def refs(stand) -> dict:
    """Ссылки клона проекта и bare `origin` (ветки, ссылки документов)."""
    fmt = "--format=%(refname) %(objectname)"
    return {"clone": stand.git("-C", stand.clone, "for-each-ref", fmt),
            "origin": stand.git("--git-dir", stand.bare, "for-each-ref", fmt)}


class BodySpy:
    """Обёртка тела гейта мержа: возврат каждого захода (цикл гейта зовёт
    тело снова после `("wait", …)` ожидания CI) и снимки до/после
    ПОСЛЕДНЕГО захода — того, что закончил окно."""

    def __init__(self, stand):
        self.stand = stand
        self.real = fsm_merge_gate._cmd_approve_merge_gate
        self.outcomes: list = []
        self.new_rows: list = []

    def __call__(self, conn, task_id, *args, **kwargs):
        s = self.stand
        self.row_before = dict(store.get_task(conn, task_id))
        self.refs_before = refs(s)
        rows, pushes, calls, fake = (len(s.rows(task_id)), len(s.pushes),
                                     len(s.git_calls), len(s.fake.calls))
        outcome = ("исключение",)
        try:
            outcome = self.real(conn, task_id, *args, **kwargs)
        except SystemExit as exc:
            outcome = ("exit", exc.code)
            raise
        finally:
            self.outcomes.append(outcome)
            self.row_after = dict(store.get_task(conn, task_id))
            self.refs_after = refs(s)
            self.new_rows = s.rows(task_id)[rows:]
            self.pushes = s.pushes[pushes:]
            self.merges = [c for c in s.git_calls[calls:]
                           if delivery.git_sub(c) == "merge"]
            self.opened = [c for c in s.fake.calls[fake:]
                           if c["name"] == "open_mr"]
        return outcome

    def ended_stopped(self) -> bool:
        """Окно закончилось `("stopped",)`, прежние заходы — ожидание CI."""
        return (bool(self.outcomes) and self.outcomes[-1] == ("stopped",)
                and all(o[0] == "wait" for o in self.outcomes[:-1]))


def watch_body(monkeypatch, stand) -> BodySpy:
    body = BodySpy(stand)
    monkeypatch.setattr(fsm_merge_gate, "_cmd_approve_merge_gate", body)
    return body


def rows_text(rows) -> str:
    return "\n".join(f"{r['action']} | {r['detail'] or ''}" for r in rows)


def assert_untouched(stand, task: str, body: BodySpy, where: str) -> None:
    """Требование 12: состояние, поля задачи, ссылки и ветки не изменились;
    шпион не видит слияния, отправки и открытия MR."""
    assert body.row_after == body.row_before, where
    assert body.refs_after == body.refs_before, where
    assert body.pushes == [], where
    assert body.merges == [], where
    assert body.opened == [], where
    assert stand.state(task) == "merge_gate", where


def stop_after_people_entry(monkeypatch) -> tuple:
    """Тело гейта после выбора пути останавливается первым шагом пути:
    прежний путь артели — `_docs_ref_unsynced` (отвечает «не сверено»),
    путь людей проекта — `_approve_for_project_people`. Списки задач,
    дошедших до каждого шага."""
    artel_path: list = []
    people_path: list = []

    def unsynced(conn, task_id, *args, **kwargs):
        artel_path.append(task_id)
        return True

    def people(conn, task_id, *args, **kwargs):
        people_path.append(task_id)
        return ("stopped",)

    monkeypatch.setattr(fsm_merge_gate, "_docs_ref_unsynced", unsynced)
    monkeypatch.setattr(fsm_merge_gate, "_approve_for_project_people", people)
    return artel_path, people_path


def run_body(stand, task: str) -> tuple:
    """Тело гейта мержа задачи `task` прямым вызовом: (возврат, вывод)."""
    t = store.get_task(stand.conn, task)
    holder: list = []

    def call():
        holder.append(fsm_merge_gate._cmd_approve_merge_gate(
            stand.conn, task, "merge_gate", t))

    out = delivery.capture_out(call)
    return (holder[0] if holder else None), out


def random_word() -> str:
    """Случайное имя; зерно печатается."""
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(6))


def artel_task(stand, state: str) -> str:
    """Задача артели прямо в БД стенда."""
    task = idgen.new_task_id()
    store.insert_task(stand.conn, task, f"Артель {stand.word()}", state,
                      f"task/{task.lower()}-{stand.word()}",
                      config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
    return task


# ------------------------------------------------------------------- AC-1


def test_ac1_target_human_unread_entry_refuses_gate(stand, monkeypatch):
    """`target-human` на гейте мержа: читатель записи `people_entry` бросил `TargetsError` — отказ гейта, не слияние.

    Сценарий: запись проекта `target-human` читается; задача на
    `merge_gate`, ветка на сервере. Подменена только функция-читатель
    записи `people_entry` (`targets.target` не тронут — `repo_context.
    resolve` и `_profile_refusal_exit` читают запись успешно). `approve`:
    тело гейта возвращает `("stopped",)`; за тело — ровно одна запись
    журнала, её действие `PEOPLE_REFUSED_ACTION`, причина начинается
    «запись проекта не прочитана:»; строка задачи, ссылки клона и `origin`
    прежние; ни отправки, ни `git merge`, ни `open_mr`; задача на гейте.

    Ловит мутацию: место вызова `people_entry` в `fsm_merge_gate` не ловит
    `TargetsError` (исключение летит из `approve`, записи отказа нет) либо
    `people_entry` по-прежнему глотает сбой в `None` — гейт идёт путём
    слияния в `base` (шпион видит `git merge`, записи `PEOPLE_REFUSED_ACTION`
    нет).
    """
    stand.record(draft_mr="false")
    task = stand.new_task(state="merge_gate", published=True)
    calls = failing_reader(monkeypatch, f"сбой чтения {stand.word()}")
    body = watch_body(monkeypatch, stand)
    out = stand.approve(task)
    where = stand.context(task, out) + "\n--- за тело:\n" + rows_text(
        getattr(body, "new_rows", []))
    assert calls, stand.note(f"стенд: читатель people_entry не зван\n{where}")
    assert body.outcomes == [("stopped",)], where
    assert len(body.new_rows) == 1, where
    row = body.new_rows[0]
    assert row["action"] == fsm_merge_gate.PEOPLE_REFUSED_ACTION, where
    assert (row["detail"] or "").startswith(NOT_READ), where
    assert_untouched(stand, task, body, where)


# ------------------------------------------------------------------- AC-2


def test_ac2_github_operator_unread_entry_refuses_gate(stand, monkeypatch):
    """`github` + `operator` на гейте мержа: тот же сбой читателя записи — тот же отказ.

    Сценарий: запись проекта `forge: github`, `merge_gate: operator`
    читается; задача на `merge_gate`, ветка на сервере. Подменена только
    функция-читатель записи `people_entry`. `approve`: тело гейта
    возвращает `("stopped",)`; за тело — ровно одна запись журнала
    `PEOPLE_REFUSED_ACTION` с причиной «запись проекта не прочитана: …»;
    строка задачи, ссылки и ветки прежние; ни отправки, ни `git merge`, ни
    `open_mr`.

    Ловит мутацию: отказ при сбое оставлен только записям `target-human`
    (для `operator` сбой читается как «гейт не target-human») — тело идёт
    путём слияния в `base`, записи отказа нет.
    """
    stand.record(gate="operator", forge_name="github")
    task = stand.new_task(state="merge_gate", published=True)
    calls = failing_reader(monkeypatch, f"сбой чтения {stand.word()}")
    body = watch_body(monkeypatch, stand)
    out = stand.approve(task)
    where = stand.context(task, out) + "\n--- за тело:\n" + rows_text(
        getattr(body, "new_rows", []))
    assert calls, stand.note(f"стенд: читатель people_entry не зван\n{where}")
    assert body.outcomes == [("stopped",)], where
    assert len(body.new_rows) == 1, where
    row = body.new_rows[0]
    assert row["action"] == fsm_merge_gate.PEOPLE_REFUSED_ACTION, where
    assert (row["detail"] or "").startswith(NOT_READ), where
    assert_untouched(stand, task, body, where)


# ------------------------------------------------------------------- AC-3


@pytest.mark.parametrize("case", ["сбой", "operator", "target-human",
                                  "артель при сбое"])
def test_ac3_people_entry_distinguishes_gate_and_unread(monkeypatch, case):
    """`people_entry`: сбой читателя — `TargetsError`; гейт не `target-human` — `None`; `target-human` — запись; артель — `None` и при сбое.

    Сценарий: подменена функция-читатель записи `people_entry`. «сбой» —
    читатель бросает `TargetsError`, `people_entry` проекта вне артели
    бросает `targets.TargetsError`. «operator» — читатель отдаёт запись с
    `merge_gate: operator`, ответ `None`. «target-human» — запись с
    `merge_gate: target-human`, ответ — та же запись. «артель при сбое» —
    `people_entry(config.DEFAULT_TARGET)` при бросающем читателе — `None`.

    Ловит мутацию: `people_entry` по-прежнему ловит `TargetsError` и
    отдаёт `None` («сбой» не бросает); либо для артели сбой читателя
    пробрасывается («артель при сбое» бросает); либо запись `target-human`
    не возвращается (ответ `None`).
    """
    name = f"proj{random_word()}"
    entry = {"merge_gate": "target-human" if case == "target-human"
             else "operator", "forge": "gitlab", "base": config.MAIN_BRANCH}

    def reader(*args, **kwargs):
        if case in ("сбой", "артель при сбое"):
            raise targets.TargetsError(f"сбой чтения {name}")
        return entry

    monkeypatch.setattr(github_adapter, reader_name(), reader)
    if case == "сбой":
        with pytest.raises(targets.TargetsError):
            github_adapter.people_entry(name)
        return
    if case == "артель при сбое":
        assert github_adapter.people_entry(config.DEFAULT_TARGET) is None
        return
    got = github_adapter.people_entry(name)
    if case == "operator":
        assert got is None, got
    else:
        assert got == entry, got


# ------------------------------------------------------------------- AC-6


def test_ac6_awaiting_limit_unread_entry_refuses_gate(stand, monkeypatch):
    """`target-human`: сбой чтения записи внутри `_awaiting_limit_refuses` — отказ гейта «предел awaiting_human не проверен», а не пропуск предела.

    Сценарий: запись `target-human` с `max_awaiting`, задача на
    `merge_gate`, ветка на сервере. `targets.target` подменён так, что
    бросает `TargetsError` только когда в стеке вызова есть
    `_awaiting_limit_refuses`; прочие чтения (`repo_context.resolve`,
    `people_entry` — запись вернулась) успешны. `approve`: тело гейта
    возвращает `("stopped",)`; среди записей журнала за тело ровно одна с
    действием `PEOPLE_REFUSED_ACTION`, её причина начинается «предел
    awaiting_human не проверен:» и содержит «запись проекта не
    прочитана:»; `open_mr` не зван; строка задачи, ссылки и ветки прежние;
    ни отправки, ни `git merge`.

    Ловит мутацию: в `_awaiting_limit_refuses` оставлено `except
    TargetsError: return False` (`fsm_merge_gate.py:1796-1797`) — предел
    пропущен, `open_mr` зван, задача в `awaiting_human`.
    """
    stand.record(draft_mr="false", max_awaiting=str(stand.pick(1, 3)))
    task = stand.new_task(state="merge_gate", published=True)
    real_target = targets.target
    hits: list = []
    message = f"сбой чтения {stand.word()}"

    def target(*args, **kwargs):
        frame = sys._getframe(1)
        while frame is not None:
            if frame.f_code.co_name == "_awaiting_limit_refuses":
                hits.append(args)
                raise targets.TargetsError(message)
            frame = frame.f_back
        return real_target(*args, **kwargs)

    monkeypatch.setattr(targets, "target", target)
    body = watch_body(monkeypatch, stand)
    out = stand.approve(task)
    where = stand.context(task, out) + "\n--- за тело:\n" + rows_text(
        getattr(body, "new_rows", []))
    assert hits, stand.note(f"стенд: чтение в _awaiting_limit_refuses не "
                            f"состоялось\n{where}")
    where += f"\n--- возвраты тела: {body.outcomes}"
    assert body.ended_stopped(), where
    refused = [r for r in stand.rows(task)[stand.before:]
               if r["action"] == fsm_merge_gate.PEOPLE_REFUSED_ACTION]
    assert len(refused) == 1, where
    detail = refused[0]["detail"] or ""
    assert detail.startswith(AWAITING_NOT_CHECKED), where
    assert NOT_READ in detail, where
    assert_untouched(stand, task, body, where)


# ------------------------------------------------------------------ AC-13


@pytest.mark.parametrize("mr_state", ["locked", "", None])
def test_ac13_unknown_mr_state_refuses_gate(stand, mr_state):
    """Статус MR вне `opened`/`merged`/`closed` (`locked`, пустой, `None`) — отказ гейта с причиной, черновик не снят.

    Сценарий: запись `target-human` с `mr_assignee: "42"`, у задачи на
    `merge_gate` в БД ссылка на MR, ветка на сервере; подделка хостинга
    отвечает на `mr_status` MR со статусом по параметру (`None` — значение
    по умолчанию `forge.MergeRequest.state`, поле не передаётся). `approve`:
    задача на `merge_gate` (не `awaiting_human` и не `escalated`); новая
    запись журнала отказа гейта людей проекта (действие начинается
    `PEOPLE_REFUSED_ACTION`) с непустой причиной; `undraft_mr`,
    `assign_mr` и `open_mr` не званы; `git merge` нет.

    Ловит мутацию: `_mr_incident_stops` пропускает статус вне трёх
    известных (как сегодня `if not detail: return False`) — черновик снят
    (`undraft_mr` зван), исполнитель назначен, задача в `awaiting_human`.
    """
    stand.record(mr_assignee='"42"')
    task = stand.new_task(state="merge_gate", published=True)
    iid = stand.rng.randrange(100, 10 ** 6)
    store.update_task(stand.conn, task, mr_iid=iid,
                      mr_url=f"https://localhost/grp/{stand.ext}/-/merge_requests/{iid}")
    fields = {} if mr_state is None else {"state": mr_state}

    def mr_status(target, mr):
        stand.fake._record("mr_status", (target, mr))
        return forge.MergeRequest(iid=mr, draft=True,
                                  target_branch=config.MAIN_BRANCH, **fields)

    stand.fake.mr_status = mr_status
    out = stand.approve(task)
    where = stand.context(task, out)
    assert stand.fake.named("mr_status"), stand.note(
        f"стенд: статус MR не читался\n{where}")
    assert stand.state(task) == "merge_gate", where
    refused = [r for r in stand.rows(task)[stand.before:]
               if r["action"].startswith(fsm_merge_gate.PEOPLE_REFUSED_ACTION)
               and (r["detail"] or "").strip()]
    assert refused, where
    for name in ("undraft_mr", "assign_mr", "open_mr"):
        assert stand.fake.named(name) == [], where
    assert not [c for c in stand.git_calls
                if delivery.git_sub(c) == "merge"], where


# ------------------------------------------------------------------ AC-17


@pytest.mark.parametrize("project", ["артель", "github+operator"])
def test_ac17_readable_entry_keeps_artel_path(stand, monkeypatch, project):
    """Артель и `github` + `operator` при читаемой записи: тело гейта идёт прежним путём слияния, не путём людей проекта и без отказа.

    Сценарий: «артель» — задача артели на `merge_gate`; «github+operator»
    — задача проекта `github` + `operator` на `merge_gate`, ветка на
    сервере. Запись и БД читаются; читатель `people_entry` не подменён.
    Тело гейта (прямой вызов) останавливается первым шагом прежнего пути
    (`_docs_ref_unsynced` подменён ответом «не сверено»): шаг достигнут,
    путь людей проекта (`_approve_for_project_people`) не зван, возврат
    `("stopped",)`, записи `PEOPLE_REFUSED_ACTION` нет.

    Ловит мутацию: место вызова `people_entry` отказывает и без сбоя
    (например, ловит любой ответ `None` как непрочитанную запись) — запись
    `PEOPLE_REFUSED_ACTION` есть, `_docs_ref_unsynced` не достигнут; либо
    `people_entry` для `operator` отдаёт запись — тело идёт путём людей.
    """
    if project == "артель":
        task = artel_task(stand, "merge_gate")
    else:
        stand.record(gate="operator", forge_name="github")
        task = stand.new_task(state="merge_gate", published=True)
    artel_path, people_path = stop_after_people_entry(monkeypatch)
    before = len(stand.rows(task))
    outcome, out = run_body(stand, task)
    new = stand.rows(task)[before:]
    where = stand.note(f"{project}\n--- вывод:\n{out}\n--- журнал:\n"
                       + rows_text(new))
    assert artel_path == [task], where
    assert people_path == [], where
    assert outcome == ("stopped",), where
    assert not [r for r in new
                if r["action"] == fsm_merge_gate.PEOPLE_REFUSED_ACTION], where


# ------------------------------------------------------------------ AC-18


def test_ac18_artel_unread_entry_keeps_artel_path(stand, monkeypatch):
    """Задача артели на гейте мержа при сбое читателя записи `people_entry` — без отказа, прежним путём артели.

    Сценарий: задача артели на `merge_gate`; функция-читатель записи
    `people_entry` бросает `TargetsError`, `targets.target` не тронут. Тело
    гейта (прямой вызов) останавливается первым шагом прежнего пути артели
    (`_docs_ref_unsynced` подменён ответом «не сверено»): исключение не
    летит, шаг достигнут, путь людей проекта не зван, возврат
    `("stopped",)`, записи `PEOPLE_REFUSED_ACTION` нет.

    Ловит мутацию: место вызова отказывает при `TargetsError` для любого
    проекта, включая артель, — запись `PEOPLE_REFUSED_ACTION` «запись
    проекта не прочитана», `_docs_ref_unsynced` не достигнут; либо
    `people_entry` для артели читает запись и пробрасывает сбой —
    исключение из тела гейта.
    """
    task = artel_task(stand, "merge_gate")
    failing_reader(monkeypatch, f"сбой чтения {stand.word()}")
    artel_path, people_path = stop_after_people_entry(monkeypatch)
    before = len(stand.rows(task))
    outcome, out = run_body(stand, task)
    new = stand.rows(task)[before:]
    where = stand.note(f"--- вывод:\n{out}\n--- журнал:\n" + rows_text(new))
    assert artel_path == [task], where
    assert people_path == [], where
    assert outcome == ("stopped",), where
    assert not [r for r in new
                if r["action"] == fsm_merge_gate.PEOPLE_REFUSED_ACTION], where


# ------------------------------------------------------------------ AC-19


class DraftSpy:
    """Обёртка `github_adapter.ensure_forge_draft_mr`: ответ или исключение
    и отправки шпиона git за время вызова."""

    def __init__(self, stand):
        self.stand = stand
        self.real = github_adapter.ensure_forge_draft_mr
        self.results: list = []
        self.pushes: list = []

    def __call__(self, conn, task_id, t):
        before = len(self.stand.pushes)
        try:
            result = self.real(conn, task_id, t)
        except BaseException as exc:
            self.results.append(("исключение", f"{type(exc).__name__}: {exc}"))
            raise
        finally:
            self.pushes += self.stand.pushes[before:]
        self.results.append(("ответ", result))
        return result


def test_ac19_draft_mr_unread_entry_refuses_transition(stand, monkeypatch):
    """Переход `in_dev -> verifying` внешнего проекта при сбое читателя записи `people_entry` — отказ перехода с причиной, MR не открыт.

    Сценарий: запись `target-human`, `draft_mr: true`; задача в `in_dev` с
    коммитами. Подменена только функция-читатель записи `people_entry`
    (публикация головы и прочие чтения записи успешны). `advance`: задача
    в `in_dev`; в журнале запись `DRAFT_MR_REFUSAL_ACTION`, причина
    содержит «запись проекта не прочитана:»; `ensure_forge_draft_mr`
    вернула непустую причину (не `None` и не исключение); `forge.open_mr`
    не зван; ссылки на MR в БД нет; за вызов `ensure_forge_draft_mr` шпион
    не видит отправки.

    Ловит мутацию: `TargetsError` из `people_entry` не ловится в
    `ensure_forge_draft_mr` — исключение летит из `advance` (ответа нет,
    записи отказа нет); либо ловится в `None` — переход состоялся, задача
    в `verifying` без чернового MR.
    """
    stand.record(draft_mr="true")
    task = stand.new_task()
    calls = failing_reader(monkeypatch, f"сбой чтения {stand.word()}")
    spy = DraftSpy(stand)
    monkeypatch.setattr(github_adapter, "ensure_forge_draft_mr", spy)
    try:
        out = stand.advance(task)
    except targets.TargetsError as exc:
        out = f"исключение TargetsError: {exc}"
    where = stand.context(task, out) + f"\n--- ensure_forge_draft_mr: {spy.results}"
    assert calls, stand.note(f"стенд: читатель people_entry не зван\n{where}")
    assert stand.state(task) == "in_dev", where
    assert len(spy.results) == 1 and spy.results[0][0] == "ответ", where
    reason = spy.results[0][1]
    assert isinstance(reason, str) and reason.strip(), where
    refused = [r for r in stand.rows(task)[stand.before:]
               if r["action"] == github_adapter.DRAFT_MR_REFUSAL_ACTION]
    assert refused and NOT_READ in (refused[-1]["detail"] or ""), where
    assert stand.fake.named("open_mr") == [], where
    assert stand.mr(task) == (None, None), where
    assert spy.pushes == [], where


# ------------------------------------------------------------------ AC-20


def test_ac20_artel_draft_mr_unread_entry_no_refusal(stand, monkeypatch):
    """Задача артели на переходе `in_dev -> verifying` при сбое читателя записи `people_entry` — без отказа и без исключения.

    Сценарий: задача артели в `in_dev`; функция-читатель записи
    `people_entry` бросает `TargetsError`. `ensure_forge_draft_mr` задачи
    отвечает `None` без исключения; гейт чернового MR перехода
    (`tests_writing._forge_draft_mr_gate`) не отказывает (`None`); записи
    `DRAFT_MR_REFUSAL_ACTION` нет; `forge.open_mr` не зван.

    Ловит мутацию: `people_entry` для артели читает запись и пробрасывает
    сбой — `ensure_forge_draft_mr` бросает `TargetsError`; либо ловля в
    `ensure_forge_draft_mr` отказывает и задаче артели — ответ-причина,
    переход артели отклонён.
    """
    task = artel_task(stand, "in_dev")
    failing_reader(monkeypatch, f"сбой чтения {stand.word()}")
    before = len(stand.rows(task))
    row = store.get_task(stand.conn, task)
    try:
        result = github_adapter.ensure_forge_draft_mr(stand.conn, task, row)
        gate = tests_writing._forge_draft_mr_gate(stand.conn, task, row)
    except targets.TargetsError as exc:
        pytest.fail(stand.note(f"исключение TargetsError: {exc}"))
    new = stand.rows(task)[before:]
    where = stand.note(f"ответ {result!r}, гейт {gate!r}\n" + rows_text(new))
    assert result is None, where
    assert gate is None, where
    assert not [r for r in new
                if r["action"] == github_adapter.DRAFT_MR_REFUSAL_ACTION], where
    assert stand.fake.named("open_mr") == [], where
