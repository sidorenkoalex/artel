"""Наблюдаемость шага: файлы логов прогонов и перекачка вывода агента."""
import json
import sys
import threading
from pathlib import Path

from . import config, spend


def new_agent_log(task_id: str, role: str) -> Path:
    """Путь лога следующего прогона роли: <task>-<role>-<N>.log, N с 1.

    N берётся из имён уже лежащих файлов — прогоны не перезатирают друг
    друга. Файл создаётся сразу, чтобы `tail -f` можно было запустить,
    не дожидаясь первой строки агента.
    """
    config.LOGS.mkdir(parents=True, exist_ok=True)
    prefix = f"{task_id}-{role}-"
    used = [
        int(p.stem[len(prefix):])
        for p in config.LOGS.glob(f"{prefix}*.log")
        if p.stem[len(prefix):].isdigit()
    ]
    path = config.LOGS / f"{prefix}{max(used, default=0) + 1}.log"
    path.touch()
    return path


def last_agent_log(task_id: str, role: str) -> str:
    """Лог последнего прогона роли строкой; '—', если прогонов не было.

    Нужен циклу `auto`: `cmd_run` путь наружу не отдаёт, а сводка шага без
    ссылки на лог бесполезна. «Последний» — с наибольшим номером, который
    выдал `new_agent_log`, а не с самым свежим mtime: гранулярность времени
    на ФС путала бы соседние попытки одного шага.
    """
    prefix = f"{task_id}-{role}-"
    numbered = [(int(p.stem[len(prefix):]), p)
                for p in config.LOGS.glob(f"{prefix}*.log")
                if p.stem[len(prefix):].isdigit()]
    return str(max(numbered)[1]) if numbered else "—"


def log_tail(path: Path) -> str:
    """Последние строки лога прогона — в них причина падения (401, трейсбек).

    Ограничение и по строкам, и по символам: строка трейсбека бывает
    длиной в экран, а хвост читают глазами в журнале.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"лог не прочитан: {exc}"
    tail = "\n".join(text.splitlines()[-config.LOG_TAIL_LINES:]).strip()
    return tail[-config.LOG_TAIL_CHARS:] if tail else "лог пуст"


def render_block(block: dict) -> str:
    """Блок сообщения ассистента → строка Оператору (пустая — не показываем)."""
    kind = block.get("type")
    if kind == "text":
        text = block.get("text", "").strip()
        return f"{text}\n" if text else ""
    if kind == "tool_use":
        args = block.get("input") or {}
        arg = args.get("command") or args.get("file_path") or args.get("pattern") or ""
        return f"· {block.get('name')} {' '.join(str(arg).split())[:100]}".rstrip() + "\n"
    return ""


def render_agent_line(raw_line: str) -> str:
    """Событие `--output-format stream-json` → читаемая строка Оператору.

    Из потока событий Оператору нужны два: что агент сказал и что он делает
    инструментом, — по ним видно, работает шаг или встал. Служебные события
    (хуки, лимиты, сводки) отбрасываем. Не-JSON строки (stderr агента,
    трейсбек CLI) проходят как есть — молча не глотаем ничего.
    """
    if not raw_line.lstrip().startswith("{"):
        return raw_line
    try:
        event = json.loads(raw_line)
    except json.JSONDecodeError:
        return raw_line

    if event.get("type") == "assistant":
        content = event.get("message", {}).get("content")
        if not isinstance(content, list):
            return ""
        return "".join(render_block(b) for b in content if isinstance(b, dict))
    if event.get("type") == "result" and event.get("is_error"):
        return f"! ошибка агента: {str(event.get('result', ''))[:200]}\n"
    return ""


def tee_lines(stream, log, sink=None) -> None:
    """Строки процесса — в консоль и, если он открыт, в лог. По одной, сразу.

    `sink` получает сырую строку до отрисовки: служебные события (в них
    стоимость шага) до консоли и лога не доходят.
    """
    for raw_line in stream:
        if sink is not None:
            sink(raw_line)
        line = render_agent_line(raw_line)
        if not line:
            continue
        sys.stdout.write(line)
        sys.stdout.flush()
        if log is not None:
            log.write(line)


def stream_to_log(stream, log_path: Path, sink=None) -> None:
    """Качает вывод процесса в консоль и в лог-файл.

    Построчная буферизация обязательна: с ней Оператор видит работу шага
    через `tail -f` по ходу, а не одним куском после завершения агента.
    """
    try:
        log = open(log_path, "a", encoding="utf-8", buffering=1)
    except OSError:
        # Пайп дочитываем даже без лога: перестать читать — значит подвесить
        # агента на записи в переполненный пайп. О сбое узнает cmd_run.
        # Стоимость собираем и здесь: деньги потрачены независимо от лога.
        tee_lines(stream, None, sink)
        raise
    with log:
        tee_lines(stream, log, sink)


class OutputPump(threading.Thread):
    """Поток перекачки вывода агента; запоминает свой сбой для `cmd_run`.

    Демон: EOF на пайпе может не прийти вовсе (write-конец унаследовал
    переживший агента процесс), а вечно живой не-демон не дал бы
    интерпретатору выйти даже после возврата из `cmd_run`.
    """

    def __init__(self, stream, log_path: Path):
        super().__init__(daemon=True)
        self.stream = stream
        self.log_path = log_path
        self.error: Exception | None = None
        self.cost: dict | None = None

    def catch_cost(self, raw_line: str) -> None:
        """Запоминает стоимость из события потока: последнее — итог запуска."""
        cost = spend.parse_cost_event(raw_line)
        if cost is not None:
            self.cost = cost

    def run(self) -> None:
        try:
            stream_to_log(self.stream, self.log_path, self.catch_cost)
        except Exception as exc:  # noqa: BLE001 — сбой лога не роняет шаг
            self.error = exc
