"""Команда `answer`: канал ответа Оператора на эскалацию (SPEC T075).

`artel.py answer <id> <файл-с-ответом>` читает текст ответа из файла
Оператора, создаёт `tasks/<id>/ANSWER-n.md` в worktree задачи (`n` —
порядковый номер, следующий за уже существующими файлами того же
префикса) и коммитит его в ветку задачи — Оператор не правит worktree
руками (требование 2).

Коммит НЕ несёт `-c user.name=.../-c user.email=...` (в отличие от
`catalog.cmd_new`, который явно проставляет служебную identity
`fixation.FIXATION_AUTHOR_NAME/EMAIL` артефактам, рождающимся из ТЗ):
ответ — содержательное решение Оператора, не служебный артефакт
оркестратора, и коммит обязан остаться под его identity (git-конфиг
или `GIT_AUTHOR_*` окружения вызывающей сессии), тот же довод, что и
`commit_task_dir` в `tests/test_git_fixation.RealPultGitTest`.
"""
import sys
from pathlib import Path

from . import gitcmd, lease, store, workspace


def _next_answer_number(task_dir: Path) -> int:
    """Следующий свободный номер `ANSWER-n.md`: максимум существующих + 1,
    не счёт файлов — второй раунд эскалации после первого ответа обязан
    получить `ANSWER-2.md`, даже если бы `ANSWER-1.md` когда-то убрали."""
    existing = []
    for path in task_dir.glob("ANSWER-*.md"):
        suffix = path.stem[len("ANSWER-"):]
        if suffix.isdigit():
            existing.append(int(suffix))
    return max(existing, default=0) + 1


def _answer_document(task_id: str, n: int, raw: str) -> str:
    return (
        f"---\n"
        f"task: {task_id}\n"
        f"type: answer\n"
        f"author_role: operator\n"
        f"status: ready\n"
        f"schema_version: 2\n"
        f"---\n\n"
        f"# ANSWER-{n}: ответ Оператора\n\n"
        f"## Ответы\n\n"
        f"{raw}"
    )


def cmd_answer(task_id: str, file_path: str,
              session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2) — тем же
    приёмом, что и остальные мутирующие команды задачи (approve/reject/
    run/kill/workspace)."""
    conn = store.db()
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_answer(conn, task_id, file_path))


def _cmd_answer(conn, task_id: str, file_path: str) -> None:
    t = store.get_task(conn, task_id)
    if t["state"] != "escalated":
        sys.exit(f"[{task_id}] answer доступна только для задачи в "
                 f"состоянии escalated (сейчас: {t['state']})")
    try:
        raw = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"[{task_id}] файл ответа не прочитан из {file_path}: {exc}")

    wt_path, error = workspace.ensure(task_id, t["branch"])
    if error is not None:
        sys.exit(f"[{task_id}] worktree не готов: {error}")

    task_dir = wt_path / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    n = _next_answer_number(task_dir)
    answer_path = task_dir / f"ANSWER-{n}.md"
    answer_path.write_text(_answer_document(task_id, n, raw), encoding="utf-8")

    # `add -- <файл>`, НЕ `add -A tasks/<id>`: worktree задачи живёт
    # дольше одного вызова (`workspace.ensure` его не чистит) и вполне
    # может нести чужие незакоммиченные правки (упавший на попытке шаг
    # роли, ручная правка Оператора) — стейджинг обязан захватить только
    # свежесозданный ANSWER, а не всё, что случайно лежит рядом в
    # tasks/<id> (REVIEW T075 итерация 1, замечание major).
    rel_answer = f"tasks/{task_id}/ANSWER-{n}.md"
    added = gitcmd.in_repo(wt_path, "add", "--", rel_answer)
    if added is None or added.returncode != 0:
        sys.exit(f"[{task_id}] ANSWER-{n}.md не застейджен: "
                 f"{added.stderr.strip()[:200] if added is not None else '—'}")
    commit_message = f"{task_id}: ANSWER-{n} — ответ Оператора"
    committed = gitcmd.in_repo(wt_path, "commit", "-q", "-m", commit_message)
    if committed is None or committed.returncode != 0:
        sys.exit(f"[{task_id}] коммит ANSWER-{n}.md не сделан: "
                 f"{committed.stderr.strip()[:200] if committed is not None else '—'}")

    store.journal(conn, task_id, "operator", "ANSWER создан",
                 f"tasks/{task_id}/ANSWER-{n}.md")
    print(f"[{task_id}] {answer_path} создан и закоммичен в ветку {t['branch']}")
