"""Каталог задач: заведение, список, карточка задачи, журнал шагов."""
import re
import shutil
import sys
from pathlib import Path

from . import (alerts, artifact_branch, artifacts, budget, config, fixation,
              gitcmd, idgen, store, workspace)

# ГОСТ-подобная транслитерация: только stdlib, без внешних зависимостей.
# ъ/ь пропускаются; ё → yo; щ → sch; ю → yu; я → ya.
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(title: str) -> str:
    """Слаг ветки: транслит кириллицы, [^a-z0-9]+ → '-', ≤30, пустое → 'task'."""
    lowered = title.lower()
    translit = "".join(_TRANSLIT.get(ch, ch) for ch in lowered)
    return re.sub(r"[^a-z0-9]+", "-", translit)[:30].strip("-") or "task"


def cmd_init() -> None:
    """Заводит состояние пульта; на непустом проекте — холодный старт
    (SPEC T049, ADR-0005 п.5): счётчик номеров, слой ролей и программный
    расход досеваются от наблюдаемого мира, а не остаются пустыми.
    """
    conn = store.db()
    store.create_schema(conn)
    # `store.db()` выше уже звал `migrate()`, но ДО `create_schema` — на
    # свежей БД таблиц ещё не было, и `migrate` вышла первой же строкой
    # («табиц tasks ещё нет — схему ставит init»), не дойдя до сева.
    # Явный вызов здесь делает посев частью самого `init` (требование 2),
    # а не побочным эффектом первого следующего `store.db()`.
    store.seed_task_counters(conn)
    _deploy_role_home_reference()
    budget.reseed_program_spend(conn)
    print(f"OK: состояние в {config.DB}")
    print("Задачи в полёте (ветки task/* без строки в БД) холодный старт "
         "не восстанавливает автоматически — пересборка по веткам "
         "остаётся ручной сверкой Оператора (SPEC T049, требование 11).")


def _deploy_role_home_reference() -> None:
    """Разворачивает курируемый слой ролей из референса пульта, если
    `.artel/home` ещё не существует (SPEC T049, требования 8-9, AC-5).

    Каталог референса `docs/reference/role-home/claude/` копируется как
    `.artel/home/.claude/` — имя без ведущей точки в самом репозитории
    (docs/reference/role-home.md), переименование — только здесь, при
    развёртывании.
    """
    if config.ROLE_HOME.exists():
        return
    reference = config.ROOT / "docs" / "reference" / "role-home"
    if not reference.is_dir():
        return
    config.ROLE_HOME.mkdir(parents=True)
    for entry in reference.iterdir():
        dest_name = ".claude" if entry.name == "claude" else entry.name
        dest = config.ROLE_HOME / dest_name
        if entry.is_dir():
            shutil.copytree(entry, dest)
        else:
            shutil.copy2(entry, dest)


def _tz_document(task_id: str, title: str, raw: str) -> str:
    """Оборачивает свободный текст Оператора минимальным фронтматтером
    (SPEC T025, требование 1): Оператору не нужно писать шапку руками,
    а `tasks/<id>/TZ.md` остаётся артефактом, который guard проверяет
    как любой другой тип."""
    return (
        f"---\n"
        f"task: {task_id}\n"
        f"type: tz\n"
        f"author_role: operator\n"
        f"status: draft\n"
        f"schema_version: 2\n"
        f"---\n\n"
        f"# ТЗ: {title}\n\n"
        f"{raw}"
    )


def cmd_new(title: str, tz_path: str | None = None, *,
           canary: bool = False, target: str | None = None) -> str:
    """Заводит задачу: ТЗ/SPEC рождаются сразу в её ветке (ADR-0005 п.9,
    SPEC T048) — рабочая копия main не трогается ни на одном шаге
    (требование 4): ни новых файлов на диске main, ни коммитов в main.

    Id — ULID (SPEC T094, требование 2, AC-2): единственный генератор —
    `idgen.new_task_id()`, без счётчика и без коллизий по построению —
    ранняя peek-проверка ветки (T048) и повторный расход счётчика после
    неё, нужные только под гонку конкурентного `next_task_number`,
    отсюда убраны вместе с самим счётчиком как источником id (контур
    `task_counters` остаётся, но заморожен как legacy — требование 6, не
    удаляется этой задачей).

    `target` (SPEC T094, требования 7-9, AC-8/AC-9) — keyword-only,
    `None` (self/догфуд, `config.DEFAULT_TARGET`) не меняет поведение
    существующих вызывателей: `tasks/<id>/` рождается прямо в worktree
    кодовой ветки задачи, как и раньше (требование 16/AC-18 — self не
    заводит артефактную ветку пульта до A7). Для ЛЮБОГО другого target
    `tasks/<id>/` коммитится ВЕТКОЙ ПУЛЬТА (`orchestrator/
    artifact_branch.py`) — кодовая ветка `branch` только ЗАПИСЫВАЕТСЯ в
    БД (её создание и код — дело роли-разработчика в клоне целевого,
    `runner.role_cwd`, эта функция туда не пишет вовсе, AC-9). Push
    артефактной ветки в origin пульта — best-effort (требование 7,
    AC-8): отказ сети не отменяет заведение задачи.

    `canary` — keyword-only, дефолт `False` не меняет поведение
    существующих вызывателей: команда `canary` (tasks/T065/SPEC.md,
    требование 1) заводит свои задачи через ЭТУ же функцию с `canary=True`,
    пишущим пометку ТОЛЬКО в колонку БД `tasks.is_canary` (требование 6),
    не в `title` — `title` канареечной задачи ничем не отличается от
    продуктовой, роль его не видит иначе. Возвращает `task_id`, чтобы
    вызывающий код (тот же `canary`) мог собрать список заведённых задач.
    """
    conn = store.db()
    # Файл ТЗ читается ДО побочных эффектов: нечитаемый путь не должен
    # оставлять после себя наполовину созданную задачу.
    tz_raw = None
    if tz_path is not None:
        try:
            tz_raw = Path(tz_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            sys.exit(f"ТЗ не прочитано из {tz_path}: {exc}")

    target = target or config.DEFAULT_TARGET
    task_id = idgen.new_task_id()
    branch = f"task/{task_id.lower()}-{slugify(title)}"

    spec = (config.TEMPLATES / "SPEC.md").read_text(encoding="utf-8")
    spec = spec.replace("TASK_ID", task_id).replace("<название задачи>", title)
    tz_doc = _tz_document(task_id, title, tz_raw) if tz_raw is not None else None

    if target == config.DEFAULT_TARGET:
        _new_dogfood(task_id, title, branch, spec, tz_doc)
    else:
        _new_external_artifact_branch(task_id, title, spec, tz_doc)

    store.insert_task(conn, task_id, title, "spec_writing", branch, target,
                      config.DEFAULT_BUDGET_USD, is_canary=canary)
    store.journal(conn, task_id, "operator", "created", title)
    print(f"[{task_id}] «{title}» создана"
         + (f" в ветке {branch}" if target == config.DEFAULT_TARGET
            else f" (target {target}, артефактная ветка пульта "
                 f"{artifact_branch.branch_name(task_id)})"))
    if tz_path is not None:
        print(f"  затем: artel.py run {task_id}  (запуск analyst)")
    else:
        print(f"  затем: artel.py advance {task_id}  (SPEC status: ready)")
    return task_id


def _new_dogfood(task_id: str, title: str, branch: str, spec: str,
                 tz_doc: str | None) -> None:
    """Self/догфуд (требование 16/AC-18): однобраншевый флоу, байт-в-байт
    прежнее поведение `cmd_new` до SPEC T094 (worktree кодовой ветки,
    коммит оркестраторского авторства)."""
    if gitcmd.branch_exists(branch):
        sys.exit(f"ветка {branch} уже существует — задача не заведена")
    wt_path, error = workspace.ensure(task_id, branch)
    if error is not None:
        sys.exit(f"[{task_id}] worktree не создан: {error}")

    task_dir = wt_path / "tasks" / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "SPEC.md").write_text(spec, encoding="utf-8")
    if tz_doc is not None:
        (task_dir / "TZ.md").write_text(tz_doc, encoding="utf-8")

    commit_message = f"{task_id}: ТЗ Оператора ({title})"
    added = gitcmd.in_repo(wt_path, "add", "-A", f"tasks/{task_id}")
    if added is None or added.returncode != 0:
        # `res is None` — git не ответил вовсе, тот же вырожденный случай,
        # что и у `workspace.ensure`/`gitcmd.branch_exists` выше.
        sys.exit(f"[{task_id}] ТЗ/SPEC не застейджены: "
                 f"{added.stderr.strip()[:200] if added is not None else '—'}")
    committed = gitcmd.in_repo(
        wt_path, "-c", f"user.name={fixation.FIXATION_AUTHOR_NAME}",
        "-c", f"user.email={fixation.FIXATION_AUTHOR_EMAIL}",
        "commit", "-q", "-m", commit_message)
    if committed is None or committed.returncode != 0:
        sys.exit(f"[{task_id}] коммит ветки {branch} не сделан: "
                 f"{committed.stderr.strip()[:200] if committed is not None else '—'}")


def _new_external_artifact_branch(task_id: str, title: str, spec: str,
                                  tz_doc: str | None) -> None:
    """Внешний target (требования 7-9, AC-8/AC-9): `tasks/<id>/` коммитится
    в артефактную ветку пульта плотницки (`artifact_branch.commit_files`),
    рабочая копия/worktree пульта не трогаются вовсе. Push в origin —
    best-effort (требование 7): отказ не прерывает заведение задачи и не
    превращает его в ошибку команды (AC-8)."""
    files = {f"tasks/{task_id}/SPEC.md": spec}
    if tz_doc is not None:
        files[f"tasks/{task_id}/TZ.md"] = tz_doc
    commit_sha = artifact_branch.commit_files(
        task_id, files, f"{task_id}: ТЗ Оператора ({title})")
    if not commit_sha:
        sys.exit(f"[{task_id}] артефактная ветка пульта не создана — git "
                 f"не ответил")
    artifact_branch.push(task_id)


def cmd_status() -> None:
    conn = store.db()
    rows = store.all_tasks(conn)
    if not rows:
        print("Задач нет. `new \"<название>\"` создаст первую.")
    for r in rows:
        flag = " <- ЖДЁТ ОПЕРАТОРА" if r["state"] in (
            "spec_gate", "acceptance", "merge_gate", "escalated") else ""
        # Пометка canary — ТОЛЬКО здесь и в RETRO (tasks/T065/SPEC.md,
        # требование 6), не в `title` самой задачи: строка `status` видна
        # Оператору, не роли внутри промпта шага.
        mark = "  [canary]" if r["is_canary"] else ""
        print(
            f"{r['id']}  {r['state']:<13} "
            f"ревью {r['review_iters']}/{config.LIMIT_REVIEW_ITERS}"
            f"  ${r['spent_usd']:.2f}/{r['budget_usd']:.2f}  {r['title']}{flag}{mark}"
        )

    # Требование 7 SPEC T022: триггеры docs/triggers.md — отдельная секция
    # в status/doctor, не смешиваются с задачами и остальными алертами.
    triggers = alerts.open_alerts(conn, "trigger")
    if triggers:
        print("\nТриггеры (docs/triggers.md) — ack обязан нести решение:")
        for a in triggers:
            print(f"  #{a['id']} [{a['target'] or '-'}] {a['source']}: "
                  f"{a['message']}")


def cmd_show(task_id: str) -> None:
    conn = store.db()
    # Префикс -> полный id ОДИН РАЗ здесь (SPEC T094, требование 3, AC-3),
    # до любого использования task_id ниже — иначе строки статуса читались
    # бы неразрешённым префиксом мимо сводной строки (REVIEW T094 итерация
    # 1, замечание 1: `_artifact_frontmatter` теряла SPEC.md/PLAN.md/...).
    task_id = store.resolve_task_id(conn, task_id)
    t = store.get_task(conn, task_id)
    print(f"{t['id']} «{t['title']}»  состояние: {t['state']}  "
          f"ветка: {t['branch']}  проект: {t['target']}")
    print(f"  ревью-итераций: {t['review_iters']}/{config.LIMIT_REVIEW_ITERS}"
          f"  отказов приёмки: {t['accept_rejects']}"
          f"/{config.LIMIT_ACCEPT_REJECTS}"
          f"  бюджет: ${t['spent_usd']:.2f}/{t['budget_usd']:.2f}")
    for name in ("SPEC.md", "PLAN.md", "REVIEW.md", "TEST_REPORT.md"):
        meta = _artifact_frontmatter(t["target"], task_id, name)
        if meta:
            print(f"  {name}: status={meta.get('status', '?')}")


def _artifact_frontmatter(target: str, task_id: str, name: str) -> dict:
    """Frontmatter артефакта задачи для `cmd_show` — с диска для self
    (прежнее поведение), из артефактной ветки пульта для любого другого
    target (SPEC T094, требование 10, AC-11 — реестр AC-1: `tasks/<id>/`
    внешнего target на диске `config.TASKS` не существует вовсе)."""
    if target == config.DEFAULT_TARGET:
        return artifacts.frontmatter(config.TASKS / task_id / name)
    from . import yamlmini
    text, _ = gitcmd.show(artifact_branch.branch_name(task_id),
                          f"tasks/{task_id}/{name}")
    return (yamlmini.frontmatter(text) or {}) if text is not None else {}


def cmd_log(task_id: str) -> None:
    conn = store.db()
    # Префикс -> полный id (SPEC T094, требование 3, AC-3) — без этого
    # `task_steps` требует точного совпадения `id` и молча печатает 0
    # строк для валидного уникального префикса (REVIEW T094 итерация 1,
    # замечание 1).
    task_id = store.resolve_task_id(conn, task_id)
    for r in store.task_steps(conn, task_id):
        print(f"{r['ts']}  {r['actor']:<12} {r['action']}"
              + (f"  | {r['detail']}" if r["detail"] else ""))
