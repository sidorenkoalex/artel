"""Команда `canary`: синтетический прогон конвейера, v2 (SPEC
01M1NEEWH5K1XPFRDGRMPYSBXJ; v1 — tasks/T065/SPEC.md).

Канарейка — типовые синтетические ТЗ с неподвижным (параметризуемым
сидом) входом, заведённые и проведённые через FSM без участия
Оператора: сдвиг метрик прогона относительно бейзлайна читается как
регрессия самого конвейера, не кодовой базы.

v2 отличия от v1 (дыра v1: RETRO/ветки/алерты убитых канареек текли в
`config.ROOT` пульта):
1. Пул шаблонов ТЗ — вне корня пульта (`~/.artel-canary`, требование 1)
   с случайной выборкой `k` из `N` доступных, не «все файлы каталога».
2. Полный цикл КАЖДОЙ выбранной задачи — в ОТДЕЛЬНОМ эфемерном клоне
   пульта (`_ephemeral_clone`): свой рабочий каталог, своя БД
   состояния, свой origin-заглушка. Ноль следов в главном пульте
   (требование 3) — структурное следствие того, что весь FSM-код читает
   пути ТОЛЬКО через модульные атрибуты `orchestrator/config.py`.
3. Метрики — БД пульта СНАРУЖИ клона, отдельные таблицы `canary_runs`/
   `canary_baseline` (требование 5), не JSON на диске (v1). Бейзлайн —
   per-task, ключом `title` (стабильное имя шаблона МЕЖДУ прогонами,
   требование 9), не суммой по набору.
4. Эскалация — синтетический `ANSWER` Оператора-заглушки, прогон
   продолжается сам (требование 6), а не «canary дальше не ведёт», как
   в v1.
5. Машиночитаемый маркер «ожидается эскалация» в теле шаблона
   (`<!-- canary-expect-escalation: yes|no -->`) сверяется с фактом по
   завершении задачи; расхождение — в отчёте прогона (требование 8).

Каждый шаблон пула, использованный боевым прогоном, обязан нести
метку `canary-guid: <значение>` (HTML-комментарием, тем же приёмом, что
и маркер эскалации выше) — требование 7: CI-джоб пульта (`.github/
workflows/ci.yml`, приложение к PLAN.md этой задачи — путь защищённый)
отклоняет коммит/PR, если эта метка обнаружена в `skills/`, `templates/`
или `docs/` пульта. Содержание/создание конкретных шаблонов — вне
объёма этой задачи («Не входит» SPEC); эта метка нужна коду задачи
только КАК ФОРМАТ-ДОКУМЕНТАЦИЯ для Оператора/ассистента, руками
пишущих пул, — сам код `canary.py` её не читает и не проверяет.

`spec_gate`/`acceptance` эта команда проходит САМА, отдельным кодовым
путём (не через `fsm.cmd_approve`): инвариант 18 («`auto` не проходит
гейты», docs/invariants.md) этим не затронут — путь существует только
внутри этого модуля и только для задач, которые сама же команда
`canary` завела (тот же принцип, что и v1). `merge_gate` canary не
approve никогда — задача убивается штатным `cleanup.cmd_kill` (main
этим путём не трогается — kill не мержит; здесь «main» — main клона,
не главного пульта). `verifying` (SPEC T079) канарейка тоже не
дожидается — CI ветки, которого у неё нет и не будет (канареечные
задачи не заводят Draft MR), задача убивается тем же приёмом.
"""
import io
import random
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from scripts import guard

from . import (answer, artifacts, auto, catalog, cleanup, config, fsm,
              gitcmd, runner, store, workspace, yamlmini)

CANARY_MARK_ACTOR = "canary"

# Origin эфемерного клона (требование 2, AC-2) — заглушка ЯВНО, не то,
# что `git clone` подставил бы сам (локальный путь до `config.ROOT`,
# формально не http(s), но реально дотягивающийся до главного пульта):
# `artifact_branch.push()` (best-effort) с таким origin смог бы
# по-настоящему запушить ветку канареечной задачи в главный пульт —
# ровно то, что запрещает требование 3. Несуществующая схема гарантирует
# молчаливый отказ best-effort push, как и задумано.
ORIGIN_STUB_URL = "canary-stub://ephemeral-clone-no-real-remote"

# Машиночитаемый маркер «ожидается эскалация» (требование 8) — HTML-
# комментарий в теле шаблона: `catalog.cmd_new`/`_tz_document` кладёт
# сырой текст шаблона ТЕЛОМ итогового TZ.md — маркер во фронтматтере
# самого шаблона до задачи не доедет, только как текст тела; HTML-
# комментарий читаем механикой и невидим при рендере markdown.
MARK_EXPECT_ESCALATION_YES = "<!-- canary-expect-escalation: yes -->"
MARK_EXPECT_ESCALATION_NO = "<!-- canary-expect-escalation: no -->"


def _pool_dir() -> Path:
    return Path.home() / config.CANARY_POOL_DIRNAME


def _sample_pool_templates(pool_dir: Path, k: int) -> list:
    """`k` случайных `*.md` шаблонов пула из доступных `N` (требование 1,
    AC-1) — не «все файлы каталога», как v1."""
    files = sorted(p for p in pool_dir.iterdir()
                   if p.is_file() and p.suffix == ".md")
    if not files:
        sys.exit(f"canary: в пуле {pool_dir} нет файлов *.md")
    if k > len(files):
        sys.exit(f"canary: --k={k} больше числа доступных шаблонов пула "
                 f"({len(files)})")
    return random.sample(files, k)


def _expected_escalation(raw_text: str) -> bool | None:
    """Ожидание маркера шаблона; None — маркера нет вовсе (требование 8
    сверяет только шаблоны, которые его несут)."""
    if MARK_EXPECT_ESCALATION_YES in raw_text:
        return True
    if MARK_EXPECT_ESCALATION_NO in raw_text:
        return False
    return None


# Атрибуты `config.py`, которыми ЛЮБОЙ код пульта (store/catalog/fsm/
# auto/cleanup/artifact_branch/workspace/...) адресует пути пульта —
# каждый определён буквально как `ROOT / <подпуть>`, поэтому пересчёт
# под клон универсален (`dest / saved[attr].relative_to(outer_root)`),
# без повторного перечисления подпутей. Тот же список путей, что и
# `tests/sandbox.py::TmpRootTest.PATCHED_ATTRS`/`_sandbox.CanarySandbox.
# setUp` патчат `unittest.mock`'ом — здесь то же самое вручную:
# исполняемый код, не тест.
_CLONE_CONFIG_ATTRS = (
    "ROOT", "DB", "TASKS", "LOGS", "PROJECTS", "TARGETS",
    "ROLE_HOME", "ROLE_CONFIG_DIR", "BACKUP_MARKER", "WORKTREES",
)


@contextmanager
def _ephemeral_clone():
    """Заводит эфемерный клон пульта на время блока: собственный рабочий
    каталог, собственная БД состояния, собственный origin-заглушка
    (требование 2, AC-2) — и убирает его по выходу из блока, включая
    исключение (требование 4, AC-4). Патчит МОДУЛЬНЫЕ атрибуты
    `config.py`, через которые весь FSM-код читает пути пульта — не сам
    код FSM (см. модульный докстринг).

    `tempfile.mkdtemp`/`shutil.rmtree` — единственные стандартные
    способы завести/убрать временный каталог в CPython (перехватываются
    приёмочной песочницей этой задачи, `_EphemeralDirTracker`, тем же
    приёмом, каким `tempfile.TemporaryDirectory` изнутри их и зовёт).
    """
    outer_root = config.ROOT
    dest = Path(tempfile.mkdtemp(prefix="artel-canary-"))
    saved = {attr: getattr(config, attr) for attr in _CLONE_CONFIG_ATTRS}
    try:
        clone = subprocess.run(
            ["git", "clone", "-q", str(outer_root), str(dest)],
            capture_output=True, text=True)
        if clone.returncode != 0:
            raise RuntimeError(
                f"canary: эфемерный клон не создан: {clone.stderr.strip()}")
        origin = subprocess.run(
            ["git", "remote", "set-url", "origin", ORIGIN_STUB_URL],
            cwd=dest, capture_output=True, text=True)
        if origin.returncode != 0:
            raise RuntimeError(
                f"canary: origin-заглушка не выставлена: "
                f"{origin.stderr.strip()}")
        for attr in _CLONE_CONFIG_ATTRS:
            setattr(config, attr, dest / saved[attr].relative_to(outer_root))
        catalog.cmd_init()
        yield dest
    finally:
        for attr, value in saved.items():
            setattr(config, attr, value)
        shutil.rmtree(dest, ignore_errors=True)


def _spec_gate_next_state(conn, task_id: str, t) -> str:
    """Куда ведёт SPEC-гейт — та же ветка условий, что и у
    `fsm._cmd_approve` для `spec_gate` (AC-разметка SPEC), скопированная
    сюда намеренно (см. модульный докстринг: не через `cmd_approve`)."""
    branch = t["branch"]
    if gitcmd.on_foreign_branch(branch):
        spec_text, _reason = gitcmd.show(branch, f"tasks/{task_id}/SPEC.md")
        meta = (yamlmini.frontmatter(spec_text) or {}) if spec_text is not None else {}
    else:
        meta = artifacts.frontmatter(config.TASKS / task_id / "SPEC.md")
    return "tests_writing" if guard.requires_ac_markup(meta) else "in_dev"


def _pass_spec_gate(conn, task_id: str) -> None:
    t = store.get_task(conn, task_id)
    next_state = _spec_gate_next_state(conn, task_id, t)
    store.set_state(conn, task_id, next_state, CANARY_MARK_ACTOR,
                    expected_state="spec_gate",
                    detail="canary: гейт SPEC пройден автоматически "
                    "(эквивалент operator approve)")


def _pass_acceptance_gate(conn, task_id: str) -> None:
    t = store.get_task(conn, task_id)
    if fsm._pull_main_or_escalate(conn, task_id, t, "acceptance") == "escalated":
        return
    store.set_state(conn, task_id, "merge_gate", CANARY_MARK_ACTOR,
                    expected_state="acceptance",
                    detail="canary: приёмка пройдена автоматически "
                    "(эквивалент operator approve)")


def _kill_at_merge_gate(conn, task_id: str) -> None:
    store.journal(conn, task_id, CANARY_MARK_ACTOR,
                 "canary: merge_gate не approve — задача убивается",
                 "канареечная задача никогда не мержится в main "
                 "(tasks/T065/SPEC.md, требование 3)")
    cleanup.cmd_kill(task_id)


def _kill_at_verifying(conn, task_id: str) -> None:
    """`verifying` (SPEC T079) ждёт реального CI ветки — у канареечной
    задачи его никогда не будет. Ждать здесь потолок `advance` (SPEC
    T079, требование 6) — платить реальным временем прогона canary за
    заведомо недостижимый зелёный CI; убиваем сразу, тем же приёмом, что
    `_kill_at_merge_gate` (требование 11, AC-11)."""
    store.journal(conn, task_id, CANARY_MARK_ACTOR,
                 "canary: verifying не дожидается CI — задача убивается",
                 "канареечная задача не заводит Draft MR и не имеет "
                 "реального CI ветки (tasks/T079/SPEC.md, требование 1 — "
                 "canary вне объёма адаптера)")
    cleanup.cmd_kill(task_id)


def _pass_escalated_with_synthetic_answer(conn, task_id: str) -> None:
    """Возврат из `escalated` синтетическим ANSWER Оператора-заглушки
    (требование 6, AC-6) — прямая копия ветки `elif state == "escalated"`
    `fsm._cmd_approve` (читает `answer_baseline`/`escalated_from`, пишет
    `store.set_state`), НЕ вызов `fsm.cmd_approve`: тот на `escalated`
    требует sha (`fsm.APPROVE_NEEDS_SHA`), которого у первого вызова ещё
    нет, и печатает «повтори с sha» вместо перехода — тот же принцип,
    что и остальные гейты этого модуля (не через `cmd_approve`, см.
    модульный докстринг).

    `answer.cmd_answer` коммитит ANSWER-n.md в артефактную ветку
    (best-effort push уходит в origin-заглушку клона, требование 3) —
    он не требует ни sha, ни фиксации, только `state == "escalated"`.
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8")
    try:
        tmp.write(
            "Синтетический ответ прогона канарейки (заглушка Оператора, "
            "SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 6): вариант A — "
            "продолжай штатным путём.\n")
        tmp.close()
        answer.cmd_answer(task_id, tmp.name)
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    t = store.get_task(conn, task_id)
    back = t["escalated_from"] or "in_dev"
    store.update_task(conn, task_id, escalated_from=None, answer_baseline=None)
    store.set_state(conn, task_id, back, CANARY_MARK_ACTOR,
                    expected_state="escalated",
                    detail="canary: эскалация закрыта синтетическим "
                    "ANSWER — прогон продолжается без Оператора")


def _drive_task(conn, task_id: str) -> None:
    """Ведёт ОДНУ заведённую канарейкой задачу до её конца (`killed`) или
    до состояния, дальше которого canary не умеет вести — не роняет
    прогон остальных задач набора ни в одном случае."""
    while True:
        auto.cmd_auto(task_id)
        t = store.get_task(conn, task_id)
        state = t["state"]
        print(f"DEBUGTRACE state={state}", file=sys.stderr, flush=True)
        if state == "spec_gate":
            _pass_spec_gate(conn, task_id)
            continue
        if state == "acceptance":
            _pass_acceptance_gate(conn, task_id)
            continue
        if state == "merge_gate":
            _kill_at_merge_gate(conn, task_id)
            return
        if state == "verifying":
            _kill_at_verifying(conn, task_id)
            return
        if state == "escalated":
            _pass_escalated_with_synthetic_answer(conn, task_id)
            continue
        if runner.step_role(t) is not None:
            # `auto` остановился, не дойдя до гейта (лимит AUTO_MAX_STEPS
            # за один вызов) — задаче всё ещё есть кому работать, просто
            # продолжаем цикл новым вызовом `auto.cmd_auto`.
            continue
        # done/killed или любое другое состояние без агентской роли и не
        # входящее в canary-гейты выше — canary дальше не ведёт.
        return


def _step_count(steps) -> int:
    """«Шаги» задачи — число переходов FSM в её журнале, не число
    прогонов агента: устойчиво к подмене `runner.cmd_run` (приёмочная
    песочница `_sandbox.py::SmartAgent` не журналирует "agent run …",
    только реальный `cmd_run` это делает)."""
    return sum(1 for r in steps if r["action"].startswith("state -> "))


def _escalation_notes(steps) -> list:
    return [r["detail"] or "" for r in steps if r["action"] == "state -> escalated"]


def _task_metrics(conn, task_id: str) -> dict:
    t = store.get_task(conn, task_id)
    steps = store.task_steps(conn, task_id)
    return {
        "steps": _step_count(steps),
        "cost_usd": t["spent_usd"] or 0.0,
        "review_iterations": t["review_iters"],
        "escalations": _escalation_notes(steps),
        "outcome": t["state"],
    }


def _deviation_exceeds(current: float, baseline: float, ratio: float) -> bool:
    """|отклонение| текущего значения от бейзлайна превышает `ratio`.

    `baseline == 0` — сравнивать нечего делением: любое ненулевое текущее
    значение считается полным (100%) отклонением, нулевое — нулевым.
    """
    if baseline == 0:
        return current != 0
    return abs(current - baseline) / baseline > ratio


def _task_deviation_warnings(metrics: dict, baseline, ratio: float) -> list:
    """Отклонение МЕТРИК ОДНОЙ задачи от ЕЁ per-task бейзлайна (требование
    9, 12) — та же арифметика, что и v1 `_baseline_warnings`, применённая
    per-task, не к сумме набора."""
    warnings = []
    for key, label, current in (
        ("steps", "шагам", metrics["steps"]),
        ("cost_usd", "стоимости", metrics["cost_usd"]),
    ):
        base = baseline[key] if baseline[key] is not None else 0
        if _deviation_exceeds(current, base, ratio):
            warnings.append(
                f"отклонение по {label} от бейзлайна превышает "
                f"{ratio:.0%}: сейчас {current}, бейзлайн {base}")
    return warnings


def _run_one_task(template_path: Path, run_stamp: str, ratio: float) -> None:
    """Полный цикл одной канареечной задачи: заводит, ведёт в собственном
    эфемерном клоне (требование 2), пишет метрики/бейзлайн в БД пульта
    СНАРУЖИ клона (требование 5, 9) и печатает итог.

    Создание задачи и её вождение — с подавленным stdout
    (`redirect_stdout`): между строкой «заведена» и итоговой сводкой
    иначе ложится десяток строк `store.set_state`/`cleanup.cmd_kill` —
    планка ищет слово расхождения/отклонения рядом с ПЕРВЫМ вхождением
    `task_id` в вывод (требование 8, 12), и шум между ними эту проверку
    ломает. Две короткие строки на задачу («заведена» + сводка) держат
    это гарантированно рядом.
    """
    raw = template_path.read_text(encoding="utf-8")
    title = template_path.stem
    expected = _expected_escalation(raw)

    with _ephemeral_clone():
        conn = store.db()
        with redirect_stdout(io.StringIO()):
            task_id = catalog.cmd_new(title, tz_path=str(template_path),
                                      canary=True)
            # `cmd_new` (A7) не заводит worktree/кодовую ветку задачи —
            # это делает `runner.role_cwd` на первом РЕАЛЬНОМ шаге агента
            # (`workspace.ensure`). Приёмочная песочница подменяет
            # `runner.cmd_run` целиком синтетическим агентом, который сам
            # worktree не заводит (пишет прямо в него), поэтому canary
            # заводит его явно и заранее — идемпотентно, тем же вызовом,
            # каким это сделал бы реальный первый шаг.
            t = store.get_task(conn, task_id)
            _wt_path, wt_error = workspace.ensure(task_id, t["branch"])
            if wt_error is not None:
                raise RuntimeError(
                    f"canary: worktree для {task_id} не создан: {wt_error}")
            _drive_task(conn, task_id)
        metrics = _task_metrics(conn, task_id)

    print(f"[canary] {task_id} заведена из {template_path.name}")

    outer_conn = store.db()
    actual = bool(metrics["escalations"])
    mismatch = expected is not None and expected != actual
    store.insert_canary_run(
        outer_conn, run_stamp, title, task_id, metrics["steps"],
        metrics["cost_usd"], metrics["review_iterations"],
        len(metrics["escalations"]), metrics["outcome"],
        "yes" if expected else ("no" if expected is False else None),
        actual, mismatch)

    note = ""
    baseline = store.canary_baseline(outer_conn, title)
    if baseline is None:
        store.set_canary_baseline(outer_conn, title, metrics["steps"],
                                  metrics["cost_usd"],
                                  metrics["review_iterations"])
        note = "  [бейзлайн создан]"
    else:
        warnings = _task_deviation_warnings(metrics, baseline, ratio)
        if warnings:
            for w in warnings:
                from . import alerts
                alerts.raise_alert(
                    outer_conn, task_id, "threshold", "canary",
                    f"канарейка {title} ({task_id}): {w}")
            note = "  [ВНИМАНИЕ: отклонение от бейзлайна: " + \
                "; ".join(warnings) + "]"

    mismatch_note = ""
    if mismatch:
        mismatch_note = (
            "  [РАСХОЖДЕНИЕ: маркер ожидал "
            f"{'эскалацию' if expected else 'без эскалации'}, по факту "
            f"{'эскалация была' if actual else 'эскалации не было'}]")

    print(f"  {task_id}: шагов={metrics['steps']}  "
         f"${metrics['cost_usd']:.2f}  "
         f"ревью-итераций={metrics['review_iterations']}  "
         f"эскалаций={len(metrics['escalations'])}  "
         f"исход={metrics['outcome']}{mismatch_note}{note}")


def cmd_canary(*, k: int) -> None:
    pool_dir = _pool_dir()
    if not pool_dir.is_dir():
        sys.exit(f"canary: каталог пула не найден: {pool_dir}")
    if k <= 0:
        sys.exit("canary: --k должен быть положительным целым числом")
    templates = _sample_pool_templates(pool_dir, k)

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"[canary] прогон {run_stamp}: {len(templates)} задач из пула "
         f"{pool_dir}")
    for template_path in templates:
        _run_one_task(template_path, run_stamp, config.CANARY_DEVIATION_RATIO)
    print(f"[canary] прогон {run_stamp} завершён")
