"""Каталог задач: заведение, список, карточка задачи, журнал шагов."""
import re

from . import alerts, artifacts, config, store

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
    conn = store.db()
    store.create_schema(conn)
    print(f"OK: состояние в {config.DB}")


def cmd_new(title: str) -> None:
    conn = store.db()
    # Номер — из персистентного счётчика target'а, а не из COUNT(*) строк
    # (ADR-0003 3ж): архивация строки номер не освобождает, и реконнект
    # проекта не создаёт коллизий с уже отработанными задачами.
    target = config.DEFAULT_TARGET
    task_id = f"T{store.next_task_number(conn, target):03d}"
    branch = f"task/{task_id.lower()}-{slugify(title)}"

    task_dir = config.TASKS / task_id
    task_dir.mkdir(parents=True)
    spec = (config.ROOT / "templates" / "SPEC.md").read_text(encoding="utf-8")
    spec = spec.replace("TASK_ID", task_id).replace("<название задачи>", title)
    (task_dir / "SPEC.md").write_text(spec, encoding="utf-8")

    store.insert_task(conn, task_id, title, "spec_writing", branch, target,
                      config.DEFAULT_BUDGET_USD)
    store.journal(conn, task_id, "operator", "created", title)
    print(f"[{task_id}] «{title}» создана: заполни {task_dir / 'SPEC.md'}")
    print(f"  затем: artel.py advance {task_id}  (SPEC status: ready)")


def cmd_status() -> None:
    conn = store.db()
    rows = store.all_tasks(conn)
    if not rows:
        print("Задач нет. `new \"<название>\"` создаст первую.")
    for r in rows:
        flag = " <- ЖДЁТ ОПЕРАТОРА" if r["state"] in (
            "spec_gate", "acceptance", "merge_gate", "escalated") else ""
        print(
            f"{r['id']}  {r['state']:<13} "
            f"ревью {r['review_iters']}/{config.LIMIT_REVIEW_ITERS}"
            f"  ${r['spent_usd']:.2f}/{r['budget_usd']:.2f}  {r['title']}{flag}"
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
    t = store.get_task(conn, task_id)
    print(f"{t['id']} «{t['title']}»  состояние: {t['state']}  "
          f"ветка: {t['branch']}  проект: {t['target']}")
    print(f"  ревью-итераций: {t['review_iters']}/{config.LIMIT_REVIEW_ITERS}"
          f"  отказов приёмки: {t['accept_rejects']}"
          f"/{config.LIMIT_ACCEPT_REJECTS}"
          f"  бюджет: ${t['spent_usd']:.2f}/{t['budget_usd']:.2f}")
    for name in ("SPEC.md", "PLAN.md", "REVIEW.md", "TEST_REPORT.md"):
        meta = artifacts.frontmatter(config.TASKS / task_id / name)
        if meta:
            print(f"  {name}: status={meta.get('status', '?')}")


def cmd_log(task_id: str) -> None:
    conn = store.db()
    for r in store.task_steps(conn, task_id):
        print(f"{r['ts']}  {r['actor']:<12} {r['action']}"
              + (f"  | {r['detail']}" if r["detail"] else ""))
