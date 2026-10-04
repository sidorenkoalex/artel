"""Команда `pin-update`: обновление пина запущенной версии (A7, Stage1,
требования 5-6); `pin --to` — откат пина (tasks/
01M1NGFK3N6MRMYGCC09H975V3/SPEC.md, требования 3-4, ADR-0013 ч.3).

Stage0 (`orchestrator/fsm_merge_gate.py`) удерживает рабочее дерево и
HEAD `config.ROOT` от изменения переходом `merge_gate -> done` —
единственный способ продвинуть его вперёд, к текущему main артели
(её `origin`), — эта операторская команда, вне цикла FSM любой задачи.
`doctor.check_root_pin` только СООБЩАЕТ о расхождении (AC-13); сам пин
обновляет только эта команда (AC-14).

`cmd_pin_update` (AC-1/AC-2, ANSWER-1 п.3-4): отказывает, если на
целевом sha нет зелёного прогона канарейки не старше
`config.CANARY_MAX_MERGES_SINCE_GREEN` мержей main
(`canary.merges_since_last_green_run`) — ADR-0013 требует зелёного
прогона канарейки v2 до обновления пина; проверка — ПОСЛЕ `fetch`, но
ДО `merge` (REVIEW.md итерации 1, R1-F1): `merge-base`/`rev-list`,
которыми считается возраст, нуждаются в том, чтобы целевой `sha` уже
был объектом ЛОКАЛЬНОЙ базы `config.ROOT` — обычно это как раз объект,
который ещё только принесёт `fetch` (`pin-update <sha>` продвигает пин
на sha main, ушедшего вперёд origin'а). `fetch` сам по себе HEAD не
двигает — только обновляет remote-tracking ref'ы, так что «отказ не
трогает HEAD» (ANSWER-1 п.4) верно и с гейтом после него.

Гейт всегда искал зелёный прогон на истории именно `sha` (параметра
функции), не `gitcmd.head_sha()` пина — SPEC 01M2B6K02YVJBWE1JDWP85EJH0
(требование 2, AC-5) убеждается, что это НЕ регрессирует к сравнению с
пином, потому что до этой задачи `canary.py` мог записать зелёный
прогон только на sha самого пина (клон всегда тестировал код ПИНА) —
сравнение с произвольным целевым `sha` было мертвым кодом; отказ теперь
называет и сам `sha`, и точную команду его получения (`--sha <sha>`,
AC-6), не общий `canary --k 1` без привязки к нужному sha.

`cmd_pin_to` (AC-5/AC-6/AC-7, ANSWER-1 п.5): откатывает HEAD `config.
ROOT` на явный `<sha>` (обязан быть предком текущего HEAD) либо, без
аргумента, на `main_sha` самого свежего зелёного прогона канарейки —
`git reset --hard`, БЕЗ fetch/push (main пульта на origin не трогается,
ADR-0013 ч.3). Каждый вызов — ровно одна запись журнала
(`config.PIN_UPDATE_JOURNAL_TASK_ID`), успешная или отказ. Сверка «пин
уже на sha последнего зелёного прогона» — по префиксу
(`_already_at_run_sha`, SPEC 01M3GKJFN90ATK2KECNDZXPPP6, требование 9):
в журнале прогонов живут короткие `main_sha`, записанные до нормализации
явного `--sha`.

Циклы на коде старше пина (SPEC 01M3Y75GCRESC2KDS9VPRJK4PS, требование
1): после успешного `merge --ff-only` `cmd_pin_update` называет живые
циклы `auto`/`run` этой машины, стартовавшие до сдвига, с готовыми
командами перезапуска — отбор общий с проверкой `doctor`
(`doctor/stale_cycles.py`), сигналов процессам команда не шлёт.
"""
import sys
from datetime import datetime, timezone

from . import canary, ci, config, doctor, gitcmd, store

STALE_CYCLES_ACTION = "pin: циклы на коде старше пина"


def _report_stale_cycles(conn, pin_moment: datetime) -> None:
    cycles = doctor.stale_cycles(conn, pin_moment)
    if not cycles:
        return
    lines = doctor.stale_cycle_lines(cycles)
    store.journal(conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                  STALE_CYCLES_ACTION, "\n".join(lines))
    print(f"[pin-update] живые циклы стартовали до сдвига пина и исполняют "
          f"прежний код ({len(cycles)}) — перезапуск за Оператором:")
    for line in lines:
        print(f"  {line}")


def _refuse_unless_main_ci_green(sha: str) -> None:
    """Зелёный завершённый CI коммита `sha` в origin — наряду с канарейкой
    (SPEC 01M3SF7DPFGEZ7VYEGGXGTX49E, требование 3, AC-2): цвет по
    проверкам первой родительской линии от `sha` (`ci.main_line_status`),
    тот же, что у `doctor` и гейта мержа. Канарейка гоняет пульт на учебной
    задаче и не видит красного `tests/` main — пин уезжал на коммит, чей
    CI упал. Вызывается после `fetch` (обход линии читает объекты, которые
    он принёс). `pin --to` этой сверки не получает: откат нужен именно
    тогда, когда CI красный или `gh` молчит.

    Линия читается в git главной копии — там же, куда был `fetch` (`pin`
    — в перечне требования 4 SPEC 01M42PENCS26D0656X8FR7DFA7): клон артели
    может отставать от `origin` (push мимо клона) или отсутствовать, и
    линия от `sha` оборвалась бы на нём самом."""
    status = ci.main_line_status(sha, repo=config.ROOT)
    if status.kind == ci.MAIN_GREEN:
        return
    if status.kind == ci.MAIN_RED:
        sys.exit(f"pin-update: CI коммита {sha[:8]} красный — {status.note}; "
                 f"пин не сдвинут, сначала почини main")
    sys.exit(f"pin-update: CI не подтверждён для {sha[:8]} — {status.note}; "
             f"пин не сдвинут, повтори, когда CI завершится")


def cmd_pin_update(sha: str) -> None:
    conn = store.db()
    old_sha = gitcmd.head_sha()

    fetch = gitcmd.git("fetch", "-q", "origin", config.MAIN_BRANCH)
    if fetch is None or fetch.returncode != 0:
        sys.exit(f"pin-update: git fetch origin {config.MAIN_BRANCH} не "
                 f"удался: {fetch.stderr.strip()[:300] if fetch is not None else 'git не ответил'}")

    age = canary.merges_since_last_green_run(conn, sha)
    if age is None or age >= config.CANARY_MAX_MERGES_SINCE_GREEN:
        sys.exit(
            "pin-update: нет зелёного прогона канарейки не старше "
            f"{config.CANARY_MAX_MERGES_SINCE_GREEN} мержей main на sha "
            f"{sha[:7]} (ADR-0013) — прогони канарейку на этом sha: "
            f"python3 orchestrator/artel.py canary --k 1 --sha {sha}")

    _refuse_unless_main_ci_green(sha)

    merge = gitcmd.git("merge", "--ff-only", sha)
    if merge is None or merge.returncode != 0:
        sys.exit(f"pin-update: git merge --ff-only {sha} не удался: "
                 f"{merge.stderr.strip()[:300] if merge is not None else 'git не ответил'}")

    pin_moment = datetime.now(timezone.utc)
    new_sha = gitcmd.head_sha()
    detail = f"pin обновлён: {old_sha} -> {new_sha}"
    store.journal(conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                  "pin обновлён", detail)
    print(f"[pin-update] {detail}")
    _report_stale_cycles(conn, pin_moment)


def _already_at_run_sha(head_sha: str, main_sha: str | None) -> bool:
    """HEAD пульта уже стоит на `main_sha` прогона канарейки — сравнение ПО
    ПРЕФИКСУ (SPEC 01M3GKJFN90ATK2KECNDZXPPP6, требование 9).

    `canary_runs.main_sha` до этой задачи писался как напечатан в `--sha`,
    и в живой БД лежат короткие строки (прогоны 26.09). Миграция их не
    дописывает — история остаётся как записана, — а эта ветка (`pin --to`
    без аргумента) единственная, где такая строка сравнивается СТРОКОЙ:
    строгое равенство не узнавало в семисимвольной записи текущий пин и
    пускало команду на `git reset --hard` короткой строки.

    Пустой (или `NULL`) `main_sha` — не «уже на пине»: префиксом пустой
    строки является любой HEAD, и без этой проверки прогон без
    записанного sha читался бы как совпавший с любым пином.
    """
    return bool(main_sha) and head_sha.startswith(main_sha)


def _refuse_rollback(conn, detail: str) -> None:
    """Отказ `pin --to` — журналируется НА КАЖДЫЙ вызов, не только успех
    (AC-7): Оператор не должен терять след неудачной попытки отката."""
    store.journal(conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                 "pin откат отклонён", detail)
    sys.exit(detail)


def cmd_pin_to(sha: str | None) -> None:
    conn = store.db()
    old_sha = gitcmd.head_sha()

    if sha is not None:
        if not gitcmd.is_ancestor(sha, old_sha):
            _refuse_rollback(
                conn, f"pin --to {sha}: sha не существует или не предок "
                f"текущего HEAD {old_sha} — main продвигается только "
                "вперёд, откат — назад по уже известной истории")
        target = sha
        reason = f"явный sha Оператора {sha}"
    else:
        latest_green = store.latest_green_canary_run(conn)
        if latest_green is None:
            _refuse_rollback(
                conn, "pin --to: в журнале нет зелёного прогона канарейки")
        target = latest_green["main_sha"]
        if _already_at_run_sha(old_sha, target):
            _refuse_rollback(
                conn, "pin --to: пин уже на sha последнего зелёного прогона")
        reason = ("последний зелёный прогон канарейки "
                  f"{latest_green['run_stamp']}")

    reset = gitcmd.git("reset", "--hard", target)
    if reset is None or reset.returncode != 0:
        _refuse_rollback(
            conn, f"pin --to {target}: git reset --hard не удался: "
            f"{reset.stderr.strip()[:300] if reset is not None else 'git не ответил'}")

    new_sha = gitcmd.head_sha()
    detail = f"pin откатан: {old_sha} -> {new_sha}; причина: {reason}"
    store.journal(conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                 "pin откатан", detail)
    print(f"[pin] {detail}")
