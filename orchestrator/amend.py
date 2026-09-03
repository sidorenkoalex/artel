"""Команда `amend-tests`: штатная правка зафиксированной планки приёмки
(ADR-0012, tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md).

Заменяет ручную цепочку «правка -> обновление tests_locked_sha прямой
записью в БД -> запись в журнал руками» (три случая 02.09, один — с
войной правок, один — с необнаруженной опечаткой 03.09) одной
атомарной, журналируемой командой с обязательным прогоном перед
фиксацией.

Оператор правит `tasks/<id>/acceptance_tests/` прямо в worktree задачи
(`workspace.path`) ДО вызова этой команды — сама команда только
фиксирует уже внесённую правку: коммитит, сдвигает лок, журналирует.
Существо правки (неослабление покрытия) не оценивает — зона ревьювера
по чек-листу (ADR-0012 п.4); агентов не запускает (SPEC требование 5).
"""
import re
import sys
from pathlib import Path

from scripts import guard

from . import acceptance, alerts, gitcmd, lease, store, workspace

AMEND_ACTION = "правка планки"
DEVALUATION_ALERT_SOURCE = "amend_tests.window_threshold"
# Окно и порог — ADR-0012 п.3, ANSWER-1 вопрос 1 (вариант B): последние
# WINDOW_SIZE задач пульта, дошедших до фиксации лока, program-wide;
# больше WINDOW_THRESHOLD правок в этом окне поднимает алерт.
WINDOW_SIZE = 5
WINDOW_THRESHOLD = 1

_RUN_SUMMARY = re.compile(
    r"Ran \d+ tests? in [\d.]+s\s*\n+\s*(?:OK\b.*|FAILED\b[^\n]*)")


def cmd_amend_tests(task_id: str, reason: str | None,
                    session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой — тем же приёмом, что и остальные
    мутирующие команды задачи (`answer.cmd_answer`/`fsm.cmd_approve`).

    Префикс -> полный id резолвится ЗДЕСЬ, до lease (тот же порядок,
    что у `answer.cmd_answer`/`workspace.cmd_workspace`)."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_amend_tests(conn, task_id, reason))


def _worktree_changed_paths(wt_path: Path) -> list[str] | None:
    """Пути worktree с незакоммиченными изменениями (staged и unstaged,
    включая untracked), относительно корня репозитория worktree; `None`
    — git не ответил.

    `git status --porcelain`: каждая строка — `XY путь` либо, для
    переименований, `XY старый -> новый` (интересна только новая
    сторона — старого пути на диске уже нет)."""
    res = gitcmd.in_repo(wt_path, "status", "--porcelain")
    if res is None or res.returncode != 0:
        return None
    paths = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        paths.append(rest)
    return paths


def _run_summary(tail: str) -> str:
    """Итоговая строка прогона unittest (`Ran N ... \\n\\n OK`/`FAILED`)
    из хвоста вывода `acceptance.run` — для журнала (AC-11), не только
    «прошло/не прошло» одним словом. Регулярка не найдена (вывод
    truncated иначе, чем ожидается) — весь хвост как есть, без потери
    диагностики."""
    match = _RUN_SUMMARY.search(tail)
    return match.group(0).strip() if match else tail.strip()


def _locked_window_task_ids(conn, limit: int = WINDOW_SIZE) -> list[str]:
    """id последних `limit` задач пульта, дошедших до фиксации лока
    (`tests_locked_sha` не пуст), program-wide, по порядку заведения
    (ANSWER-1, вопрос 1, вариант B).

    `created_at`, не строковое сравнение `id` — прокси «порядка
    заведения» (PLAN, «Подход»): легаси `Tnnn` и текущие ULID-id в
    одной программе не сопоставимы лексикографически с реальной
    хронологией, тот же столбец, которым уже пользуется
    `store.latest_fixed_sha` для похожей задачи «последняя по времени».
    """
    locked = [t for t in store.all_tasks(conn) if t["tests_locked_sha"]]
    locked.sort(key=lambda t: (t["created_at"] or "", t["id"]))
    return [t["id"] for t in locked[-limit:]]


def _amend_events_in_window(conn, window_ids: list[str]) -> int:
    """Число событий «правка планки» журнала, чей `task_id` — в окне."""
    count = 0
    for task_id in window_ids:
        count += sum(1 for s in store.task_steps(conn, task_id)
                    if AMEND_ACTION in s["action"])
    return count


def _cmd_amend_tests(conn, task_id: str, reason: str | None) -> None:
    t = store.get_task(conn, task_id)

    # AC-5: «флага нет» и «флаг пуст» — один и тот же отказ, не только
    # `is None` (REVIEW-урок из докстринга приёмочного теста).
    if not (reason or "").strip():
        sys.exit(f"[{task_id}] amend-tests: отказ — основание (--reason) "
                 f"пустое, правка планки требует непустой причины")

    old_locked = t["tests_locked_sha"]
    if not old_locked:
        sys.exit(f"[{task_id}] amend-tests: отказ — задача ещё не проходила "
                 f"фиксацию лока приёмочных тестов (tests_locked_sha пуст) "
                 f"— сверять правку не с чем")

    wt_path, error = workspace.ensure(task_id, t["branch"])
    if error is not None:
        sys.exit(f"[{task_id}] amend-tests: отказ — worktree не готов: {error}")

    rel_tests_dir = f"tasks/{task_id}/acceptance_tests"
    prefix = f"{rel_tests_dir}/"
    changed = _worktree_changed_paths(wt_path)
    if changed is None:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"статус worktree {wt_path}")
    in_tests = [p for p in changed if p.startswith(prefix)]
    outside = [p for p in changed if not p.startswith(prefix)]
    if not in_tests:
        sys.exit(f"[{task_id}] amend-tests: отказ — нет изменений в "
                 f"{rel_tests_dir}/, нечего фиксировать")
    if outside:
        sys.exit(f"[{task_id}] amend-tests: отказ — есть изменения за "
                 f"пределами {rel_tests_dir}/: {', '.join(sorted(outside))}")

    tdir = wt_path / "tasks" / task_id
    green, tail = acceptance.run(tdir)
    if not green:
        # Обязательный прогон (ТЗ п.6, инцидент опечатки 03.09) — не «OK»
        # блокирует, КРОМЕ падений, промаркированных «Красен до
        # реализации»/«Зелёный с рождения» (тем же разбором, что выход
        # из tests_writing, guard.scan_redness_markers): такой файл
        # ещё не имеет кода под собой, и это норма, не поломка правки.
        marker_errors = guard.scan_redness_markers(tdir)
        if marker_errors:
            sys.exit(
                f"[{task_id}] amend-tests: отказ — прогон "
                f"{rel_tests_dir}/ не «OK», и не все падения промаркированы "
                f"«Красен до реализации»: {'; '.join(marker_errors)}\n{tail}")

    added = gitcmd.in_repo(wt_path, "add", "--", rel_tests_dir)
    if added is None or added.returncode != 0:
        sys.exit(f"[{task_id}] amend-tests: {rel_tests_dir}/ не застейджен: "
                 f"{added.stderr.strip()[:200] if added is not None else '—'}")
    commit_message = f"{task_id}: правка планки приёмки — {reason}"
    committed = gitcmd.in_repo(wt_path, "commit", "-q", "-m", commit_message)
    if committed is None or committed.returncode != 0:
        sys.exit(
            f"[{task_id}] amend-tests: коммит правки не сделан: "
            f"{committed.stderr.strip()[:200] if committed is not None else '—'}")

    new_locked = gitcmd.head_sha(wt_path)
    store.update_task(conn, task_id, tests_locked_sha=new_locked)

    detail = (f"старый sha={old_locked}, новый sha={new_locked}, "
             f"основание: {reason}\nприёмочные тесты: {_run_summary(tail)}")
    store.journal(conn, task_id, "operator", AMEND_ACTION, detail)
    print(f"[{task_id}] {AMEND_ACTION}: {old_locked} -> {new_locked} "
         f"(ветка {t['branch']})")

    window_ids = _locked_window_task_ids(conn)
    count = _amend_events_in_window(conn, window_ids)
    if count > WINDOW_THRESHOLD:
        message = (
            f"планка девальвируется: {count} правок планки в скользящем "
            f"окне последних {len(window_ids)} задач(и), дошедших до "
            f"фиксации лока (порог — больше {WINDOW_THRESHOLD})")
        alerts.raise_alert(conn, None, "threshold", DEVALUATION_ALERT_SOURCE,
                           message)
        print(f"[{task_id}] ВНИМАНИЕ: {message}")
