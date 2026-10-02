"""Подсказка запуска цикла `run`/`auto` (SPEC 01M3XTFJCC5TG63FHW907GQM4D).

Отсоединённый `run`/`auto` требует `--client`/`--chat` и активного
наблюдения той же сессии и проекта со свежей связью с `watch`
(`artel.py::_launch_detached`). Голая строка `artel.py run <id>`, которую
раньше собирало каждое место подсказки само, вела Оператора в отказ —
здесь единственное место, где подсказка собирается, с недостающими
шагами наблюдения по состоянию БД. Подсказка только читает БД: ничего не
регистрирует и не включает (регистрация — решение Оператора).
"""
from . import session, store

_WATCH_NOTE = "— фоновой задачей сессии"


def launch_hint(conn, task_id: str, cmd: str, note: str = "") -> list[str]:
    """Строка запуска, затем `сначала:` и недостающие шаги по порядку исполнения."""
    target = store.task_target(conn, task_id)
    rows = store.session_observations(conn, task_id, target,
                                      session.resolve_session_id(None))
    if rows:
        chosen = rows[0]
        client, chat, observation_id = chosen["client"], chosen["chat"], chosen["id"]
        steps = [] if chosen["task_enabled"] else [
            f"artel.py observe add {observation_id} --tasks {task_id}"]
        steps.append(f"artel.py watch --observation {observation_id} "
                     f"{_WATCH_NOTE}, если ещё не идёт")
    else:
        client, chat = "codex|claude", "<ID чата>"
        steps = [f"artel.py observe register --client {client} --chat {chat} "
                 f"--tasks {task_id}  (ID наблюдения — из её вывода)",
                 f"artel.py watch --observation <ID наблюдения> {_WATCH_NOTE}"]
    launch = f"artel.py {cmd} {task_id} --client {client} --chat {chat}"
    if note:
        launch = f"{launch}  {note}"
    return [launch, "сначала:"] + [f"{n}. {step}" for n, step in enumerate(steps, 1)]


def cycle_command(cmd: str, task_id: str, client: str | None = None,
                  chat: str | None = None) -> str:
    """Строка запуска цикла по уже известным аргументам наблюдения — без
    чтения БД и без заглушек: перезапуск цикла, наблюдение которого
    известно месту вызова (`doctor/stale_cycles.py`). Без пары
    `client`/`chat` — строка без `--client`/`--chat`."""
    launch = f"artel.py {cmd} {task_id}"
    if client is not None and chat is not None:
        launch = f"{launch} --client {client} --chat {chat}"
    return launch


def launch_text(conn, task_id: str, cmd: str, note: str = "",
                indent: str = "    ") -> str:
    """`launch_hint` одним текстом: строка запуска продолжает префикс места
    вызова («дальше: …»), шаги — отдельными строками с отступом."""
    first, *rest = launch_hint(conn, task_id, cmd, note)
    return "\n".join([first] + [indent + line for line in rest])
