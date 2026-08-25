"""Каталог задач: заведение, список, карточка задачи, журнал шагов."""
import re
import sys
from pathlib import Path

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


def cmd_new(title: str, tz_path: str | None = None) -> None:
    conn = store.db()
    # Файл ТЗ читается ДО того, как расходуется номер задачи и заводится
    # каталог: нечитаемый путь не должен оставлять после себя ни
    # наполовину созданную задачу, ни пропущенный номер счётчика.
    tz_raw = None
    if tz_path is not None:
        try:
            tz_raw = Path(tz_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            sys.exit(f"ТЗ не прочитано из {tz_path}: {exc}")

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

    # ТЗ — необязательный вход роли analyst (SPEC T025, требование 1):
    # без него задача живёт прежним флоу (SPEC пишет Оператор).
    if tz_raw is not None:
        (task_dir / "TZ.md").write_text(
            _tz_document(task_id, title, tz_raw), encoding="utf-8")

    store.insert_task(conn, task_id, title, "spec_writing", branch, target,
                      config.DEFAULT_BUDGET_USD)
    store.journal(conn, task_id, "operator", "created", title)
    print(f"[{task_id}] «{title}» создана: заполни {task_dir / 'SPEC.md'}")
    if tz_path is not None:
        print(f"  ТЗ сохранено: {task_dir / 'TZ.md'}")
        print(f"  затем: artel.py run {task_id}  (запуск analyst)")
    else:
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
