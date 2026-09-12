"""Детерминированная генерация содержимого `docs/retro/<id>.md` (SPEC T043).

Только чтение и вёрстка текста: побочные эффекты (запись файла, `git
add`/`commit`, обработка провала как incident-алерта) — дело
`orchestrator/fsm.py`, тем же разделением, что `orchestrator/review.py`
(сборка пакета) и `orchestrator/acceptance.py` (сводка) отделены от
`orchestrator/fsm.py` (переходы). Источники данных — только журнал
`steps` (`store.task_steps`) и фронтматтеры/тексты артефактов задачи
(`tasks/<id>/SPEC.md`, `tasks/<id>/acceptance_tests/`) — требование 3
(детерминизм): один и тот же вход даёт байт-в-байт одинаковый файл.
"""
import re

from scripts import guard

from . import cleanup, config, store

RETRO_DIR_REL = "docs/retro"

NO_ARTIFACTS_NOTE = "артефакты не сохранены (ветка удалена при kill)"

# Формат детали события `agent run finished` — `orchestrator/spend.py`
# (`charge_step`/`cost_note`): `rc=0, попытка N/M, стоимость $X.XXXX[,
# токенов K]`. Разбор регуляркой, не повторный вызов `spend` — здесь нужна
# только сумма по actor, а не разбор попытки/кода возврата.
COST_RE = re.compile(r"стоимость \$([0-9]+(?:\.[0-9]+)?)")
TOKENS_RE = re.compile(r"токенов (\d+)")
# Первая строка `_cost_block` — «Стоимость итого: $X.XX» (не путать с
# `COST_RE` построчного разбора по актёру): холодный старт (SPEC T049,
# требование 4) парсит именно её при пересеве программного расхода.
TOTAL_COST_RE = re.compile(r"^Стоимость итого: \$([0-9]+(?:\.[0-9]+)?)",
                           re.MULTILINE)


def retro_rel_path(task_id: str) -> str:
    return f"{RETRO_DIR_REL}/{task_id}.md"


def retro_path(task_id: str, repo=None):
    """Путь `docs/retro/<id>.md`; `repo` (A7, Stage0, AC-9) — корень, в
    котором физически лежит файл, по умолчанию `config.ROOT`. Переход
    `merge_gate -> done` пишет RETRO в scratch-worktree плотницкого
    merge (`orchestrator/fsm_merge_gate.py`), не в `config.ROOT` —
    единственный вызыватель, передающий `repo` явно."""
    return (repo if repo is not None else config.ROOT) / retro_rel_path(task_id)


def _read_spec_text(task_id: str) -> str | None:
    try:
        return (config.TASKS / task_id / "SPEC.md").read_text(encoding="utf-8")
    except OSError:
        return None


def _first_context_line(spec_text: str | None) -> str:
    """Дословная первая непустая строка раздела «Контекст» — фолбэк
    killed-«Сути» без ТЗ в журнале (SPEC T063, требование 3): прежнее
    поведение build_killed, оставленное без изменений этой задачей."""
    if not spec_text:
        return ""
    body = guard.section_body(spec_text, "Контекст")
    for raw in body.splitlines():
        line = raw.strip()
        if line:
            return line
    return ""


def _first_sentence(text: str) -> str:
    """Полное первое предложение текста: пробелы и переносы строк схлопнуты
    в один, обрезка — по первой точке, являющейся границей предложения, а
    не по границе строки/запятой и не по точке внутри токена (SPEC T063,
    требования 1, 2). Точки нет — возвращается весь схлопнутый текст.

    Реальные SPEC.md репозитория (REVIEW T063 итерации 1, замечание
    blocker) систематически содержат точки, не завершающие предложение, —
    в путях/расширениях файлов (`codebase-map.md`), датах (`27.08`),
    сокращениях и номерах пунктов (`п.5`). Такую точку отличает то, что
    сразу за ней (без пробела) идёт ещё один непробельный символ —
    настоящая граница предложения либо конец текста, либо пробел, а
    следующий за пробелом видимый символ — заглавная буква (новое
    предложение) или конца текста нет вовсе."""
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    length = len(normalized)
    pos = 0
    while True:
        dot = normalized.find(".", pos)
        if dot == -1:
            return normalized
        end = dot + 1
        if end == length:
            return normalized[:end]
        if normalized[end] == " ":
            next_char = normalized[end:].lstrip(" ")
            if not next_char or next_char[0].isupper():
                return normalized[:end]
        pos = end


def _first_context_sentence(spec_text: str | None) -> str:
    """Полное первое предложение раздела «Контекст» SPEC — done-«Суть»
    (SPEC T063, требование 1)."""
    if not spec_text:
        return ""
    return _first_sentence(guard.section_body(spec_text, "Контекст"))


def _gist(title: str, context_line: str) -> str:
    return f"{title} — {context_line}" if context_line else title


def _journaled_tz_text(steps) -> str | None:
    """Текст `TZ.md`, положенный в журнал `kill` (SPEC T048, требование 5,
    `orchestrator/cleanup.py`)."""
    for s in steps:
        if s["action"] == cleanup.KILL_TZ_JOURNAL_ACTION:
            return s["detail"] or None
    return None


def _actor_costs(steps) -> list[tuple[str, float, int | None]]:
    """(actor, $ суммарно, токенов суммарно или None) по всем событиям
    `agent run finished`, агрегированным по actor (не по каждому событию —
    иначе число строк растёт с числом попыток/итераций, а не с числом
    ролей, и не даёт статической гарантии лимита 30 строк, PLAN п.2)."""
    order: list[str] = []
    usd_by_actor: dict[str, float] = {}
    tokens_by_actor: dict[str, int] = {}
    has_all_tokens: dict[str, bool] = {}
    for s in steps:
        if s["action"] != "agent run finished":
            continue
        detail = s["detail"] or ""
        cost_m = COST_RE.search(detail)
        if not cost_m:
            continue
        actor = s["actor"]
        if actor not in usd_by_actor:
            order.append(actor)
            usd_by_actor[actor] = 0.0
            tokens_by_actor[actor] = 0
            has_all_tokens[actor] = True
        usd_by_actor[actor] += float(cost_m.group(1))
        tokens_m = TOKENS_RE.search(detail)
        if tokens_m:
            tokens_by_actor[actor] += int(tokens_m.group(1))
        else:
            has_all_tokens[actor] = False
    return [(actor, usd_by_actor[actor],
             tokens_by_actor[actor] if has_all_tokens[actor] else None)
            for actor in order]


def _escalations(steps) -> list[str]:
    return [s["detail"] or "" for s in steps if s["action"] == "state -> escalated"]


def _last_step_detail(steps, action: str) -> str:
    for s in reversed(steps):
        if s["action"] == action:
            return s["detail"] or ""
    return ""


def _acceptance_counts(task_id: str) -> tuple[int, int, int]:
    """(тестов, manual, skip) статическим разбором `acceptance_tests/` —
    то же ядро, что `orchestrator/acceptance.py`; каталога нет
    (killed-задача, чей `tasks/<id>/` уже убран `cleanup`) — нули, не
    провал (требование 6: БД остаётся источником истины killed-задачи,
    отсутствие рабочей копии не должно ронять генератор)."""
    tdir = config.TASKS / task_id
    _, markers = guard.scan_acceptance_tests(tdir)
    manual = sum(1 for kind, _ in markers.values() if kind == "manual")
    skip = sum(1 for kind, _ in markers.values() if kind == "skip")
    count = guard.count_test_methods(tdir)
    return count, manual, skip


def _escalations_block(steps, *, full: bool) -> list[str]:
    """`full=True` (killed) — последняя эскалация цитируется ЦЕЛИКОМ
    (требование 7, лимит 30 строк для неё явно снят требованием 4).
    `full=False` (done) — только ПЕРВАЯ строка `detail`: `detail` записи
    `state -> escalated` не гарантированно однострочный (самый частый
    случай — исчерпание попыток агента, `runner.py`, тянет в `detail`
    хвост лога до `config.LOG_TAIL_LINES` строк), а для done требование 4
    исключения по объёму не делает — лимит 30 строк должен быть
    гарантирован статически, а не количеством строк в тексте причины."""
    escalations = _escalations(steps)
    if not escalations:
        return ["Эскалации: нет"]
    last = escalations[-1]
    if not full:
        first_line, sep, _rest = last.partition("\n")
        last = f"{first_line}…" if sep else first_line
    return [f"Эскалации: {len(escalations)} (последняя): {last}"]


def parse_total_cost(text: str) -> float | None:
    """«Стоимость итого: $X.XX» из уже сгенерированного RETRO; `None` —
    строка не найдена (не формат RETRO, или файл повреждён). Используется
    `orchestrator/budget.reseed_program_spend` (SPEC T049, требование 4)
    при пересеве программного расхода холодного старта."""
    match = TOTAL_COST_RE.search(text)
    return float(match.group(1)) if match else None


def _cost_block(steps, spent_usd: float,
                spent_estimate_usd: float = 0.0) -> list[str]:
    lines = [f"Стоимость итого: ${spent_usd:.2f}"]
    # Верхняя оценка (SPEC 01M1NWCM3TDY0YABEKE8DYQA1C, требование 7) —
    # отдельной строкой от «Стоимость итого», и только когда она есть:
    # задача без частичных шагов без курса не обзаводится строкой «$0.00».
    if spent_estimate_usd > 0:
        lines.append(
            f"Верхняя оценка неучтённой стоимости: ${spent_estimate_usd:.2f}")
    for actor, usd, tokens in _actor_costs(steps):
        tail = f", {tokens} токенов" if tokens is not None else ""
        lines.append(f"  {actor}: ${usd:.2f}{tail}")
    return lines


def build_done(conn, task_id: str, merge_sha: str) -> str:
    """RETRO задачи, дошедшей до `done` (требования 4, 5, 8)."""
    t = store.get_task(conn, task_id)
    steps = store.task_steps(conn, task_id)
    context_line = _first_context_sentence(_read_spec_text(task_id))
    count, manual, skip = _acceptance_counts(task_id)
    address = f"{merge_sha}:tasks/{task_id}/"

    lines = [
        f"# RETRO: {task_id} — {t['title']}",
        "",
        f"Итог: done, sha {merge_sha}",
        f"Адрес артефактов: {address}",
        f"Суть: {_gist(t['title'], context_line)}",
        *(["Канареечная задача: да"] if t["is_canary"] else []),
        "",
        *_cost_block(steps, t["spent_usd"] or 0.0,
                    t["spent_estimate_usd"] or 0.0),
        "",
        f"Ревью: {t['review_iters']} итераций; "
        f"приёмка: {t['accept_rejects']} отказ(ов)",
        "",
        *_escalations_block(steps, full=False),
        "",
        f"Приёмочные тесты: {count} тест(ов), {manual} manual, {skip} skip",
    ]
    return "\n".join(lines) + "\n"


def _subtask_rows(conn, task_id: str) -> list:
    """Подзадачи деления родителя `task_id`, по возрастанию id
    (01M29284PTCJXGERV5262E9XMM, требование 1) — фильтрация уже
    существующего `store.all_tasks(conn)` по `parent_task_id`, без новой
    сырой SQL вне `store.py` (ADR-0003 3ж)."""
    return [r for r in store.all_tasks(conn) if r["parent_task_id"] == task_id]


def _division_block(subtasks) -> list[str]:
    """Список подзадач деления — id, название, состояние КАЖДОЙ на
    момент генерации (требование 3, AC-3)."""
    lines = ["Подзадачи деления:"]
    for r in subtasks:
        lines.append(f"  {r['id']} «{r['title']}» — {r['state']}")
    return lines


def build_killed(conn, task_id: str) -> str:
    """RETRO задачи, снятой через `kill` (требования 6, 7, 8) — источник
    истины только БД: `tasks/<id>/` к моменту подбора долга (следующий
    `merge_gate` любой другой задачи, решение (d)) обычно уже убран
    `cleanup.cleanup_killed_task`.

    Родитель, поделённый на подзадачи (01M29284PTCJXGERV5262E9XMM,
    требование 3) — отдельная ветка: раздел последней эскалации не
    цитируется (эскалации не было — деление произошло явным решением
    Оператора, не автоматическим отказом), вместо него список подзадач.
    Задача без подзадач идёт прежним путём без изменений (AC-4)."""
    t = store.get_task(conn, task_id)
    steps = store.task_steps(conn, task_id)
    # «Суть» строится из ТЗ, положенного в журнал `kill` (SPEC T048,
    # требование 6) — SPEC.md пустого шаблона-заглушки для killed-задачи
    # нового флоу main не видел вовсе (требование 4), читать неоткуда.
    # Полное первое предложение ТЗ (SPEC T063, требование 2), не просто
    # схлопнутая строка. ТЗ не было (`new` без `--tz`) — старый построчный
    # фолбэк как запасной путь (SPEC T063, требование 3, не меняется).
    tz_text = _journaled_tz_text(steps)
    context_line = (_first_sentence(tz_text) if tz_text is not None
                    else _first_context_line(_read_spec_text(task_id)))
    count, manual, skip = _acceptance_counts(task_id)
    subtasks = _subtask_rows(conn, task_id)

    if subtasks:
        lines = [
            f"# RETRO: {task_id} — {t['title']}",
            "",
            "Итог: поделена на подзадачи",
            f"Адрес артефактов: {NO_ARTIFACTS_NOTE}",
            f"Суть: {_gist(t['title'], context_line)}",
            *(["Канареечная задача: да"] if t["is_canary"] else []),
            "",
            *_cost_block(steps, t["spent_usd"] or 0.0,
                        t["spent_estimate_usd"] or 0.0),
            "",
            f"Ревью: {t['review_iters']} итераций; "
            f"приёмка: {t['accept_rejects']} отказ(ов)",
            "",
            *_division_block(subtasks),
            "",
            f"Приёмочные тесты: {count} тест(ов), {manual} manual, {skip} skip",
        ]
        return "\n".join(lines) + "\n"

    reason = _last_step_detail(steps, "state -> killed") or "причина не найдена в журнале"

    lines = [
        f"# RETRO: {task_id} — {t['title']}",
        "",
        f"Итог: killed — причина: {reason}",
        f"Адрес артефактов: {NO_ARTIFACTS_NOTE}",
        f"Суть: {_gist(t['title'], context_line)}",
        *(["Канареечная задача: да"] if t["is_canary"] else []),
        "",
        *_cost_block(steps, t["spent_usd"] or 0.0,
                    t["spent_estimate_usd"] or 0.0),
        "",
        f"Ревью: {t['review_iters']} итераций; "
        f"приёмка: {t['accept_rejects']} отказ(ов)",
        "",
        *_escalations_block(steps, full=True),
        "",
        f"Приёмочные тесты: {count} тест(ов), {manual} manual, {skip} skip",
    ]
    return "\n".join(lines) + "\n"
