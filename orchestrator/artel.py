#!/usr/bin/env python3
"""Артель, Фаза 0 — FSM-оркестратор (CLI).

Детерминированный конечный автомат; агенты думают внутри шага, между
шагами не думает никто. Все гейты Фазы 0 — ручные (approve/reject из CLI).

Состояния:
  spec_writing -> spec_gate -> in_dev -> review -> acceptance -> merge_gate -> done
                     |            ^________|  (changes_requested, <=3)
                     |            ^___________ (acceptance reject, <=1)
  из любого: escalated (вопрос Оператору), killed.

Вердикт ревьювера учитывается конечным автоматом ровно один раз: после
возврата задачи в in_dev переход review -> acceptance требует нового
REVIEW.md (iteration больше уже учтённого, см. fresh_verdict_iteration).

Фаза 0: гейт плана (фаза A review-checklist) выполняется ревьювером в одном
прогоне с ревью MR. Отдельное состояние plan_review появится в MVP.

Команды:
  init | new "<название>" | status | show <id> | advance <id> |
  run <id> | approve <id> | reject <id> "<причина>" | kill <id> | log <id>
"""
import re
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".artel" / "state.db"
TASKS = ROOT / "tasks"
LOGS = ROOT / ".artel" / "logs"

AGENT_TIMEOUT_SEC = 1800
DEFAULT_BUDGET_USD = 5.0
LIMIT_REVIEW_ITERS = 3
LIMIT_ACCEPT_REJECTS = 1

# Статусы REVIEW.md, которые FSM отрабатывает как вердикт ревьювера.
REVIEW_VERDICTS = ("approved", "changes_requested", "escalate")

# Синхронизировано с roles.yaml (Фаза 0: без yaml-парсера).
ROLE_SKILLS = {
    "developer": ["conventions-core", "escalation-rules", "coding-standards"],
    "reviewer": ["conventions-core", "escalation-rules", "review-checklist"],
}
STATE_ROLE = {"in_dev": "developer", "review": "reviewer"}

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


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def db() -> sqlite3.Connection:
    DB.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Догоняет схему БД, созданной прошлой версией (Фаза 0: без alembic)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(tasks)")}
    if cols and "reviewed_iter" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN reviewed_iter INTEGER DEFAULT 0")
        conn.commit()


def journal(conn, task_id: str, actor: str, action: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO steps (task_id, ts, actor, action, detail) VALUES (?,?,?,?,?)",
        (task_id, now(), actor, action, detail),
    )
    conn.commit()


def set_state(conn, task_id: str, state: str, actor: str, detail: str = "") -> None:
    conn.execute(
        "UPDATE tasks SET state=?, updated_at=? WHERE id=?", (state, now(), task_id)
    )
    journal(conn, task_id, actor, f"state -> {state}", detail)
    print(f"[{task_id}] -> {state}" + (f"  ({detail})" if detail else ""))


def frontmatter(path: Path) -> dict:
    if not path.exists():
        return {}
    m = re.match(r"\A---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.split("#")[0].strip()
    return meta


def fresh_verdict_iteration(meta: dict, reviewed_iter: int) -> int | None:
    """Номер итерации вердикта, если он новее уже учтённого, иначе None.

    Вердикт учитывается FSM ровно один раз: после возврата задачи в in_dev
    прежний REVIEW.md не двигает её обратно в acceptance. Нечитаемый или
    отсутствующий `iteration` трактуем как несвежий — доказательства нового
    прогона ревьювера нет.
    """
    raw = str(meta.get("iteration", "")).strip()
    if not raw.isdigit():
        return None
    iteration = int(raw)
    return iteration if iteration > reviewed_iter else None


def get_task(conn, task_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        sys.exit(f"Задача {task_id} не найдена. `status` покажет существующие.")
    return row


def new_agent_log(task_id: str, role: str) -> Path:
    """Путь лога следующего прогона роли: <task>-<role>-<N>.log, N с 1.

    N берётся из имён уже лежащих файлов — прогоны не перезатирают друг
    друга. Файл создаётся сразу, чтобы `tail -f` можно было запустить,
    не дожидаясь первой строки агента.
    """
    LOGS.mkdir(parents=True, exist_ok=True)
    prefix = f"{task_id}-{role}-"
    used = [
        int(p.stem[len(prefix):])
        for p in LOGS.glob(f"{prefix}*.log")
        if p.stem[len(prefix):].isdigit()
    ]
    path = LOGS / f"{prefix}{max(used, default=0) + 1}.log"
    path.touch()
    return path


def stream_to_log(stream, log_path: Path) -> None:
    """Качает строки процесса в консоль и в лог-файл — по одной, сразу.

    Построчная буферизация обязательна: с ней Оператор видит работу шага
    через `tail -f` по ходу, а не одним куском после завершения агента.
    """
    with open(log_path, "a", encoding="utf-8", buffering=1) as log:
        for line in stream:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)


# ---------------------------------------------------------------- commands

def cmd_init() -> None:
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
          review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
          reviewed_iter INTEGER DEFAULT 0,
          budget_usd REAL, spent_usd REAL DEFAULT 0,
          created_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS steps (
          id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, ts TEXT,
          actor TEXT, action TEXT, detail TEXT
        );
        """
    )
    conn.commit()
    print(f"OK: состояние в {DB}")


def cmd_new(title: str) -> None:
    conn = db()
    n = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    task_id = f"T{n + 1:03d}"
    branch = f"task/{task_id.lower()}-{slugify(title)}"

    task_dir = TASKS / task_id
    task_dir.mkdir(parents=True)
    spec = (ROOT / "templates" / "SPEC.md").read_text(encoding="utf-8")
    spec = spec.replace("TASK_ID", task_id).replace("<название задачи>", title)
    (task_dir / "SPEC.md").write_text(spec, encoding="utf-8")

    conn.execute(
        "INSERT INTO tasks (id,title,state,branch,budget_usd,created_at,updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (task_id, title, "spec_writing", branch, DEFAULT_BUDGET_USD, now(), now()),
    )
    journal(conn, task_id, "operator", "created", title)
    print(f"[{task_id}] «{title}» создана: заполни {task_dir / 'SPEC.md'}")
    print(f"  затем: artel.py advance {task_id}  (SPEC status: ready)")


def cmd_status() -> None:
    conn = db()
    rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    if not rows:
        print("Задач нет. `new \"<название>\"` создаст первую.")
        return
    for r in rows:
        flag = " <- ЖДЁТ ОПЕРАТОРА" if r["state"] in (
            "spec_gate", "acceptance", "merge_gate", "escalated") else ""
        print(
            f"{r['id']}  {r['state']:<13} ревью {r['review_iters']}/{LIMIT_REVIEW_ITERS}"
            f"  ${r['spent_usd']:.2f}/{r['budget_usd']:.2f}  {r['title']}{flag}"
        )


def cmd_show(task_id: str) -> None:
    conn = db()
    t = get_task(conn, task_id)
    print(f"{t['id']} «{t['title']}»  состояние: {t['state']}  ветка: {t['branch']}")
    print(f"  ревью-итераций: {t['review_iters']}/{LIMIT_REVIEW_ITERS}"
          f"  отказов приёмки: {t['accept_rejects']}/{LIMIT_ACCEPT_REJECTS}"
          f"  бюджет: ${t['spent_usd']:.2f}/{t['budget_usd']:.2f}")
    for name in ("SPEC.md", "PLAN.md", "REVIEW.md", "TEST_REPORT.md"):
        meta = frontmatter(TASKS / task_id / name)
        if meta:
            print(f"  {name}: status={meta.get('status', '?')}")


def cmd_advance(task_id: str) -> None:
    """Единственная точка движения FSM: читает статусы артефактов."""
    conn = db()
    t = get_task(conn, task_id)
    state = t["state"]
    tdir = TASKS / task_id

    if state == "spec_writing":
        if frontmatter(tdir / "SPEC.md").get("status") == "ready":
            set_state(conn, task_id, "spec_gate", "fsm", "SPEC готов — ждёт approve")
        else:
            print(f"[{task_id}] SPEC.md ещё не ready — нечего продвигать")

    elif state == "review":
        meta = frontmatter(tdir / "REVIEW.md")
        status = meta.get("status")
        if status not in REVIEW_VERDICTS:
            print(f"[{task_id}] REVIEW.md status={status} — жду вердикта")
            return

        iteration = fresh_verdict_iteration(meta, t["reviewed_iter"])
        if iteration is None:
            detail = (
                f"вердикт REVIEW.md (status={status}, "
                f"iteration={meta.get('iteration', '—')}) уже учтён — "
                f"жду новый прогон ревьювера с iteration: {t['reviewed_iter'] + 1}"
            )
            journal(conn, task_id, "fsm", "переход отклонён", detail)
            print(f"[{task_id}] {detail}")
            print(f"  дальше: artel.py run {task_id}  (прогон ревьювера)")
            return
        conn.execute("UPDATE tasks SET reviewed_iter=? WHERE id=?",
                     (iteration, task_id))
        conn.commit()

        if status == "approved":
            set_state(conn, task_id, "acceptance", "fsm",
                      "ревью пройдено — приёмка Оператором (по критериям SPEC)")
        elif status == "changes_requested":
            iters = t["review_iters"] + 1
            if iters >= LIMIT_REVIEW_ITERS:
                set_state(conn, task_id, "escalated", "fsm",
                          f"лимит ревью {LIMIT_REVIEW_ITERS} исчерпан")
            else:
                conn.execute("UPDATE tasks SET review_iters=? WHERE id=?",
                             (iters, task_id))
                set_state(conn, task_id, "in_dev", "fsm",
                          f"замечания ревью, итерация {iters}")
        elif status == "escalate":
            set_state(conn, task_id, "escalated", "fsm", "эскалация от ревьювера")

    elif state == "in_dev":
        # разработчик закончил: PLAN ready и ветка запушена -> в ревью
        if frontmatter(tdir / "PLAN.md").get("status") in ("ready", "approved"):
            set_state(conn, task_id, "review", "fsm", "MR готов — прогон ревьювера")
        else:
            print(f"[{task_id}] PLAN.md не ready — разработчик ещё работает")

    else:
        print(f"[{task_id}] состояние {state} двигается через approve/reject/run")


def cmd_approve(task_id: str) -> None:
    conn = db()
    t = get_task(conn, task_id)
    state = t["state"]
    if state == "spec_gate":
        set_state(conn, task_id, "in_dev", "operator", "гейт SPEC пройден")
        print(f"  дальше: artel.py run {task_id}  (запуск разработчика)")
    elif state == "acceptance":
        set_state(conn, task_id, "merge_gate", "operator", "приёмка пройдена")
        print(f"  дальше: artel.py approve {task_id}  (выполнит merge)")
    elif state == "merge_gate":
        branch = t["branch"]
        for cmd in (["git", "checkout", "main"], ["git", "pull", "--ff-only"],
                    ["git", "merge", "--no-ff", branch, "-m",
                     f"{task_id}: merge {branch}"], ["git", "push"]):
            res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            if res.returncode != 0:
                journal(conn, task_id, "orchestrator", "merge FAILED",
                        res.stderr.strip()[:500])
                sys.exit(f"merge упал на {' '.join(cmd)}:\n{res.stderr}")
        set_state(conn, task_id, "done", "orchestrator", f"смержено: {branch}")
    elif state == "escalated":
        set_state(conn, task_id, "in_dev", "operator", "эскалация разрешена, продолжаем")
    else:
        print(f"[{task_id}] в состоянии {state} нечего подтверждать")


def cmd_reject(task_id: str, reason: str) -> None:
    conn = db()
    t = get_task(conn, task_id)
    if t["state"] != "acceptance":
        sys.exit(f"[{task_id}] reject применим только в acceptance (сейчас {t['state']})")
    rejects = t["accept_rejects"] + 1
    if rejects > LIMIT_ACCEPT_REJECTS:
        set_state(conn, task_id, "escalated", "fsm",
                  f"лимит отказов приёмки исчерпан: {reason}")
    else:
        conn.execute("UPDATE tasks SET accept_rejects=? WHERE id=?", (rejects, task_id))
        set_state(conn, task_id, "in_dev", "operator", f"приёмка отклонена: {reason}")


def cmd_run(task_id: str) -> None:
    """Запуск агента текущего шага (claude CLI, headless)."""
    conn = db()
    t = get_task(conn, task_id)
    role = STATE_ROLE.get(t["state"])
    if role is None:
        sys.exit(f"[{task_id}] в состоянии {t['state']} агент не запускается")

    skills = "\n\n".join(
        (ROOT / "skills" / f"{s}.md").read_text(encoding="utf-8")
        for s in ROLE_SKILLS[role]
    )
    task_ref = f"tasks/{task_id}"
    if role == "developer":
        mission = (
            f"Роль: разработчик. Задача {task_id}, ветка {t['branch']}.\n"
            f"1) Прочитай {task_ref}/SPEC.md. 2) Создай ветку от main.\n"
            f"3) Напиши {task_ref}/PLAN.md по templates/PLAN.md.\n"
            f"4) Реализуй по плану + юнит-тесты. Если есть {task_ref}/REVIEW.md "
            f"со статусом changes_requested — сначала закрой замечания.\n"
            f"5) Прогони scripts/guard.py на своих артефактах, закоммить всё "
            f"в ветку, поставь PLAN.md status: ready. НЕ мержи."
        )
    else:
        mission = (
            f"Роль: ревьювер. Задача {task_id}, ветка {t['branch']}. Свежий "
            f"контекст: тебе доступны ТОЛЬКО {task_ref}/SPEC.md, PLAN.md и "
            f"diff (git diff main...{t['branch']}).\n"
            f"Проведи обе фазы review-checklist (гейт плана + ревью MR) и "
            f"заполни {task_ref}/REVIEW.md по templates/REVIEW.md "
            # номер, которого ждёт FSM: вердикт с прежним iteration он уже учёл
            f"(iteration: {t['reviewed_iter'] + 1}). Код НЕ правь — только "
            f"REVIEW.md в ветке задачи."
        )
    prompt = f"{mission}\n\n--- СКИЛЫ РОЛИ ---\n\n{skills}"

    log_path = new_agent_log(task_id, role)
    print(f"[{task_id}] лог шага: {log_path}  (наблюдать: tail -f {log_path})")
    journal(conn, task_id, role, "agent run started", f"лог: {log_path}")
    try:
        proc = subprocess.Popen(
            ["claude", "-p", prompt, "--permission-mode", "acceptEdits",
             # белый список вместо полного Bash: только git и запуск тестов/guard
             "--allowedTools", "Bash(git:*),Bash(python3:*)"],
            cwd=ROOT, text=True, bufsize=1,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        journal(conn, task_id, role, "agent run SKIPPED", "claude CLI не найден")
        print("claude CLI не найден. Запусти роль вручную с этим промптом:\n")
        print(prompt)
        return

    # Перекачка в потоке: чтение строк блокируется, пока агент молчит, а
    # таймаут шага должен срабатывать и на замолчавшем агенте.
    pump = threading.Thread(target=stream_to_log, args=(proc.stdout, log_path))
    pump.start()
    try:
        rc = proc.wait(timeout=AGENT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        pump.join()
        journal(conn, task_id, role, "agent run TIMEOUT", "30 мин")
        print(f"[{task_id}] таймаут шага (30 мин) — разберись и перезапусти run")
        return
    pump.join()
    journal(conn, task_id, role, "agent run finished", f"rc={rc}")
    print(f"[{task_id}] {role} завершил (rc={rc}); "
          f"дальше: artel.py advance {task_id}")


def cmd_kill(task_id: str) -> None:
    conn = db()
    get_task(conn, task_id)
    set_state(conn, task_id, "killed", "operator", "kill switch")


def cmd_log(task_id: str) -> None:
    conn = db()
    for r in conn.execute(
        "SELECT * FROM steps WHERE task_id=? ORDER BY id", (task_id,)
    ):
        print(f"{r['ts']}  {r['actor']:<12} {r['action']}"
              + (f"  | {r['detail']}" if r["detail"] else ""))


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    table = {
        "init": lambda: cmd_init(),
        "new": lambda: cmd_new(rest[0]),
        "status": lambda: cmd_status(),
        "show": lambda: cmd_show(rest[0]),
        "advance": lambda: cmd_advance(rest[0]),
        "run": lambda: cmd_run(rest[0]),
        "approve": lambda: cmd_approve(rest[0]),
        "reject": lambda: cmd_reject(rest[0], rest[1] if len(rest) > 1 else ""),
        "kill": lambda: cmd_kill(rest[0]),
        "log": lambda: cmd_log(rest[0]),
    }
    fn = table.get(cmd)
    if fn is None:
        sys.exit(f"Неизвестная команда {cmd}. Без аргументов — справка.")
    fn()


if __name__ == "__main__":
    main()
