"""Команда `amend-tests`: штатная правка зафиксированной планки приёмки
(ADR-0012, tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md).

Заменяет ручную цепочку «правка -> обновление tests_locked_sha прямой
записью в БД -> запись в журнал руками» (три случая 02.09, один — с
войной правок, один — с необнаруженной опечаткой 03.09) одной
атомарной, журналируемой командой с обязательным прогоном перед
фиксацией.

Оператор правит `tasks/<id>/acceptance_tests/` прямо в worktree задачи
(`workspace.path`) ДО вызова этой команды — сама команда только
фиксирует уже внесённую правку. Существо правки (неослабление покрытия)
не оценивает — зона ревьювера по чек-листу (ADR-0012 п.4); агентов не
запускает (SPEC требование 5).

ANSWER-3 (переработка после A7, вопрос 2): с A7 планка `tasks/<id>/`
живёт ТОЛЬКО в артефактной ветке пульта (`artifact_branch.branch_name`),
никогда в кодовой ветке задачи (`orchestrator/artifact_source.py`,
`fsm_advance.py::in_dev` — `lock_ref = branch`, всегда артефактная).
До этой правки команда коммитила правку в worktree КОДОВОЙ ветки и
сдвигала `tests_locked_sha` на её HEAD — асимметрия с гейтом `in_dev ->
review`, который сверяет лок с АРТЕФАКТНОЙ веткой: любой успешный
`amend-tests` немедленно ломал бы собственный переход (PLAN.md,
раздел «Эскалация», вопрос 2). Теперь команда читает правку Оператора
с диска worktree (как и раньше — это единственная поверхность, на
которой Оператор реально работает), но коммитит её ПЛОТНИЦКИ прямо на
артефактную ветку (`artifact_branch.commit_files`, тот же приём, что
`checkpoint._commit_external_step_artifacts`) и сдвигает `tests_locked_sha`
на HEAD именно этой ветки — ту же, с которой сверяет лок гейт.
"""
import re
import sys
from pathlib import Path

from scripts import guard

from . import acceptance, alerts, artifact_branch, gitcmd, lease, store, workspace

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
    сторона — старого пути на диске уже нет).

    Источник AC-3 («изменения за пределами acceptance_tests/») — целиком
    worktree, не только `tasks/<id>/`: правка планки не имеет права
    тихо игнорировать любой сторонний незакоммиченный дифф worktree,
    не только соседние файлы задачи (PLAN.md и т.п.).

    `--untracked-files=all` — с A7 `tasks/<id>/` целиком НЕ отслеживается
    кодовой веткой (планка живёт только в артефактной ветке): без этого
    флага git схлопывает полностью untracked каталог в одну строку
    `?? tasks/`, и ни один путь под ним не сопоставится с префиксом
    `acceptance_tests/` — правка ошибочно читалась бы как «за пределами»
    целиком, даже валидная (найдено на AC-1: `outside` содержал буквально
    `tasks/`, не пофайловый путь)."""
    res = gitcmd.in_repo(wt_path, "status", "--porcelain",
                         "--untracked-files=all")
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


def _materialize_tests_if_missing(task_id: str, tdir: Path) -> None:
    """Если `acceptance_tests/` ещё нет на диске worktree — заполняет её
    ТЕКУЩИМ содержимым артефактной ветки (ANSWER-3, вопрос 2: «если
    каталога нет — материализует его из артефактной ветки перед
    правкой»), прежде чем Оператор/эта же команда решают, есть ли
    реальная правка (AC-2). Каталог уже есть (Оператор уже положил
    правку) — не трогается вовсе, материализация поверх стёрла бы её."""
    tests_dir = tdir / "acceptance_tests"
    if tests_dir.is_dir():
        return
    prefix = f"tasks/{task_id}/acceptance_tests/"
    for rel, text in artifact_branch.read_tree(task_id).items():
        if not rel.startswith(prefix):
            continue
        dest = tdir / rel[len(f"tasks/{task_id}/"):]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def _tests_snapshot(wt_path: Path, rel_tests_dir: str) -> dict[str, bytes] | None:
    """{путь относительно корня worktree: байты} НЕ игнорируемых git
    файлов под `rel_tests_dir` — источник и сверки «есть ли правка»
    (AC-2), и самого коммита в артефактную ветку: `.gitignore`-исключённые
    файлы (`__pycache__`, `*.pyc` — сгенерированные обязательным прогоном
    AC-10 — ANSWER-3) в это множество не попадают, тем же критерием, что
    обычный `git add`. `None` — git не ответил.

    Байты, не текст (тот же довод, что `checkpoint._commit_external_
    step_artifacts`, REVIEW.md T094 итерация 2, замечание 1) — точная
    копия того, что реально лежит на диске, без риска потерять
    не-UTF8 содержимое."""
    res = gitcmd.in_repo(wt_path, "ls-files", "--others", "--exclude-standard",
                         "--", rel_tests_dir)
    if res is None or res.returncode != 0:
        return None
    files = {}
    for rel in res.stdout.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        try:
            files[rel] = (wt_path / rel).read_bytes()
        except OSError:
            continue
    return files


def _artifact_tests_snapshot(task_id: str, rel_tests_dir: str) -> dict[str, bytes]:
    """{путь: байты} текущего содержимого `rel_tests_dir` на артефактной
    ветке — baseline для сверки AC-2 (UTF-8: `acceptance_tests/` всегда
    текстовый python-код, тот же приём, что `artifact_branch.read_tree`
    уже применяет для чтения)."""
    prefix = f"{rel_tests_dir}/"
    return {rel: text.encode("utf-8")
           for rel, text in artifact_branch.read_tree(task_id).items()
           if rel.startswith(prefix)}


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
    tdir = wt_path / "tasks" / task_id
    _materialize_tests_if_missing(task_id, tdir)

    changed = _worktree_changed_paths(wt_path)
    if changed is None:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"статус worktree {wt_path}")
    outside = [p for p in changed if not p.startswith(prefix)]

    disk = _tests_snapshot(wt_path, rel_tests_dir)
    if disk is None:
        sys.exit(f"[{task_id}] amend-tests: отказ — git не ответил на "
                 f"содержимое {rel_tests_dir}/")
    baseline = _artifact_tests_snapshot(task_id, rel_tests_dir)
    if disk == baseline:
        # AC-2: материализация (выше) сама по себе не считается правкой —
        # сверка идёт по СОДЕРЖИМОМУ против артефактной ветки, не по
        # `git status` worktree (та всегда покажет материализованные
        # файлы как untracked, даже без реальной правки Оператора).
        sys.exit(f"[{task_id}] amend-tests: отказ — нет изменений в "
                 f"{rel_tests_dir}/, нечего фиксировать")
    if outside:
        sys.exit(f"[{task_id}] amend-tests: отказ — есть изменения за "
                 f"пределами {rel_tests_dir}/: {', '.join(sorted(outside))}")

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

    commit_message = f"{task_id}: правка планки приёмки — {reason}"
    new_locked = artifact_branch.commit_files(task_id, disk, commit_message)
    if not new_locked:
        sys.exit(f"[{task_id}] amend-tests: коммит правки в артефактную "
                 f"ветку не удался")
    store.update_task(conn, task_id, tests_locked_sha=new_locked)

    detail = (f"старый sha={old_locked}, новый sha={new_locked}, "
             f"основание: {reason}\nприёмочные тесты: {_run_summary(tail)}")
    store.journal(conn, task_id, "operator", AMEND_ACTION, detail)
    print(f"[{task_id}] {AMEND_ACTION}: {old_locked} -> {new_locked} "
         f"(ветка {artifact_branch.branch_name(task_id)})")

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
