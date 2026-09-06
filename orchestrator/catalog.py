"""Каталог задач: заведение, список, карточка задачи, журнал шагов."""
import re
import shutil
import socket
import sys
from pathlib import Path

from . import (alerts, artifact_branch, artifacts, budget, config, gitcmd,
              idgen, liveness, store, zone_lock)

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
    # Ленивый импорт — `canary.py` сам импортирует `catalog` (SPEC
    # 01M1NSR5M5THYRC0RFWPMVE2DW, требование 3): импорт на уровне модуля
    # дал бы цикл.
    from . import canary
    restore_msg = canary.restore_pool_if_missing(conn)
    if restore_msg:
        print(restore_msg)
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

    `target` (SPEC T094, требования 7-9, AC-8/AC-9; A7 требование 2 —
    снятие особого случая догфуда) — keyword-only, `None` дефолтится в
    `config.DEFAULT_TARGET` (артель). Для ЛЮБОГО target, включая
    артель, `tasks/<id>/` коммитится ВЕТКОЙ ПУЛЬТА (`orchestrator/
    artifact_branch.py`) — кодовая ветка `branch` только ЗАПИСЫВАЕТСЯ в
    БД (её создание и код — дело роли-разработчика в клоне целевого
    либо, для артели, в `config.ROOT` напрямую; эта функция туда не
    пишет вовсе, AC-9). Push артефактной ветки в origin пульта —
    best-effort (требование 7, AC-8): отказ сети не отменяет заведение
    задачи, но журналируется классифицированной причиной (SPEC
    01M1TQ0X14Y5B3C87WC0Q31PK2, требование 1). До A7 self/догфуд
    заводил worktree и кодовую ветку сама
    (требование 16/AC-18 M1) — этот путь (`_new_dogfood`) убран вместе
    со особым случаем (A7, AC-5): исторические задачи в `tasks/`
    пульта, заведённые им, не трогаются, но новые задачи артели идут
    тем же generic-путём, что и любой другой target.

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

    _new_external_artifact_branch(task_id, title, spec, tz_doc)

    store.insert_task(conn, task_id, title, "spec_writing", branch, target,
                      config.DEFAULT_BUDGET_USD, is_canary=canary)
    store.journal(conn, task_id, "operator", "created", title)
    print(f"[{task_id}] «{title}» создана (target {target}, артефактная "
         f"ветка пульта {artifact_branch.branch_name(task_id)})")
    if tz_path is not None:
        print(f"  затем: artel.py run {task_id}  (запуск analyst)")
    else:
        print(f"  затем: artel.py advance {task_id}  (SPEC status: ready)")
    return task_id


def _new_external_artifact_branch(task_id: str, title: str, spec: str,
                                  tz_doc: str | None) -> None:
    """Внешний target (требования 7-9, AC-8/AC-9): `tasks/<id>/` коммитится
    в артефактную ветку пульта плотницки (`artifact_branch.commit_files`),
    рабочая копия/worktree пульта не трогаются вовсе. Push в origin —
    best-effort (требование 7): отказ не прерывает заведение задачи и не
    превращает его в ошибку команды (AC-8), но журналируется
    классифицированной причиной (SPEC 01M1TQ0X14Y5B3C87WC0Q31PK2,
    требования 1-2, AC-1/AC-2)."""
    files = {f"tasks/{task_id}/SPEC.md": spec}
    if tz_doc is not None:
        files[f"tasks/{task_id}/TZ.md"] = tz_doc
    commit_sha = artifact_branch.commit_files(
        task_id, files, f"{task_id}: ТЗ Оператора ({title})")
    if not commit_sha:
        sys.exit(f"[{task_id}] артефактная ветка пульта не создана — git "
                 f"не ответил")
    artifact_branch.push(task_id)


def _lease_holder_suffix(conn, task_id: str) -> str:
    """Держатель lease задачи, если он есть — identity + жив/мёртв (SPEC
    01M1G..., требование 6, AC-11), ДОБАВКОЙ в конец строки `status`, не
    заменой существующих колонок.

    Живость проверяется, только если держатель на ЭТОМ host — тот же
    приём различения «свой/чужой host», которым уже пользуется
    `doctor.check_leases`/`check_merge_lock`: pid чужого host нельзя ни
    подтвердить мёртвым, ни опровергнуть, поэтому он молча считается
    «жив» (то же допущение, что уже принял `doctor.check_merge_lock`
    для мёртвого держателя на чужом host).
    """
    row = store.lease_row(conn, task_id)
    if row is None:
        return ""
    if row["hostname"] == socket.gethostname():
        alive = liveness._pid_alive(row["pid"])
    else:
        alive = True
    return f"  [lease: {row['session_id']} {'жив' if alive else 'мёртв'}]"


def _zone_wait_suffix(conn, t) -> str:
    """Ожидание зоны, если ЭТА задача сейчас заблокирована первым шагом
    developer (SPEC 01M1P9QAG65GVF69YJEV0V18D9, требование 4) — ДОБАВКОЙ
    в конец строки `status`, тем же приёмом, что и `_lease_holder_suffix`.
    Вычисление занятости берётся у `zone_lock.blocking_conflict` целиком —
    та же проверка, что не пускает `run`/`auto` дальше, не отдельная копия.

    Позиция в очереди (`zone_lock.queue_position`, R1-F3, REVIEW.md
    итерация 1) — добавкой ПОСЛЕ держателя, только когда конкурентов по
    ЭТОЙ зоне больше одного; иначе строка не меняется (единственный
    заблокированный — очередь из одного не несёт новой информации).
    """
    conflict = zone_lock.blocking_conflict(conn, t["id"], t)
    if conflict is None:
        return ""
    path, occupier_id, occupier_state = conflict
    position, total = zone_lock.queue_position(conn, t["id"], path)
    queue = f", очередь {position}/{total}" if total > 1 else ""
    return (f"  [ждёт зоны {path}: занята {occupier_id} ({occupier_state})"
            f"{queue}]")


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
        holder = _lease_holder_suffix(conn, r["id"])
        zone = _zone_wait_suffix(conn, r)
        print(
            f"{r['id']}  {r['state']:<13} "
            f"ревью {r['review_iters']}/{config.LIMIT_REVIEW_ITERS}"
            f"  ${r['spent_usd']:.2f}/{r['budget_usd']:.2f}  {r['title']}"
            f"{flag}{mark}{holder}{zone}"
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
        line = f"{r['ts']}  {r['actor']:<12} {r['action']}"
        if r["detail"]:
            line += f"  | {r['detail']}"
        # session_id — ДОБАВКОЙ в конец, одной строкой (SPEC 01M1G...,
        # AC-3): NULL у записей старше миграции (`store.migrate`) — молча
        # не показывается, не «None» текстом.
        if r["session_id"]:
            line += f"  [{r['session_id']}]"
        print(line)
