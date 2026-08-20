"""Каталог задач: заведение, список, карточка задачи, журнал шагов."""
import re

from . import artifacts, config, store

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
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
          review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
          reviewed_iter INTEGER DEFAULT 0, escalated_from TEXT,
          budget_usd REAL, spent_usd REAL DEFAULT 0, budget_source TEXT,
          created_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS steps (
          id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, ts TEXT,
          actor TEXT, action TEXT, detail TEXT
        );
        """
    )
    conn.commit()
    print(f"OK: состояние в {config.DB}")


def cmd_new(title: str) -> None:
    conn = store.db()
    n = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    task_id = f"T{n + 1:03d}"
    branch = f"task/{task_id.lower()}-{slugify(title)}"

    task_dir = config.TASKS / task_id
    task_dir.mkdir(parents=True)
    spec = (config.ROOT / "templates" / "SPEC.md").read_text(encoding="utf-8")
    spec = spec.replace("TASK_ID", task_id).replace("<название задачи>", title)
    (task_dir / "SPEC.md").write_text(spec, encoding="utf-8")

    conn.execute(
        "INSERT INTO tasks (id,title,state,branch,budget_usd,created_at,updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (task_id, title, "spec_writing", branch, config.DEFAULT_BUDGET_USD,
         store.now(), store.now()),
    )
    store.journal(conn, task_id, "operator", "created", title)
    print(f"[{task_id}] «{title}» создана: заполни {task_dir / 'SPEC.md'}")
    print(f"  затем: artel.py advance {task_id}  (SPEC status: ready)")


def cmd_status() -> None:
    conn = store.db()
    rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    if not rows:
        print("Задач нет. `new \"<название>\"` создаст первую.")
        return
    for r in rows:
        flag = " <- ЖДЁТ ОПЕРАТОРА" if r["state"] in (
            "spec_gate", "acceptance", "merge_gate", "escalated") else ""
        print(
            f"{r['id']}  {r['state']:<13} "
            f"ревью {r['review_iters']}/{config.LIMIT_REVIEW_ITERS}"
            f"  ${r['spent_usd']:.2f}/{r['budget_usd']:.2f}  {r['title']}{flag}"
        )


def cmd_show(task_id: str) -> None:
    conn = store.db()
    t = store.get_task(conn, task_id)
    print(f"{t['id']} «{t['title']}»  состояние: {t['state']}  ветка: {t['branch']}")
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
    for r in conn.execute(
        "SELECT * FROM steps WHERE task_id=? ORDER BY id", (task_id,)
    ):
        print(f"{r['ts']}  {r['actor']:<12} {r['action']}"
              + (f"  | {r['detail']}" if r["detail"] else ""))
