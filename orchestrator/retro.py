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

from . import config, store

RETRO_DIR_REL = "docs/retro"

NO_ARTIFACTS_NOTE = "артефакты не сохранены (ветка удалена при kill)"

# Формат детали события `agent run finished` — `orchestrator/spend.py`
# (`charge_step`/`cost_note`): `rc=0, попытка N/M, стоимость $X.XXXX[,
# токенов K]`. Разбор регуляркой, не повторный вызов `spend` — здесь нужна
# только сумма по actor, а не разбор попытки/кода возврата.
COST_RE = re.compile(r"стоимость \$([0-9]+(?:\.[0-9]+)?)")
TOKENS_RE = re.compile(r"токенов (\d+)")


def retro_rel_path(task_id: str) -> str:
    return f"{RETRO_DIR_REL}/{task_id}.md"


def retro_path(task_id: str):
    return config.ROOT / retro_rel_path(task_id)


def _read_spec_text(task_id: str) -> str | None:
    try:
        return (config.TASKS / task_id / "SPEC.md").read_text(encoding="utf-8")
    except OSError:
        return None


def _first_context_line(spec_text: str | None) -> str:
    """Дословная первая непустая строка раздела «Контекст» — не пересказ,
    точечное извлечение (требование 5)."""
    if not spec_text:
        return ""
    body = guard.section_body(spec_text, "Контекст")
    for raw in body.splitlines():
        line = raw.strip()
        if line:
            return line
    return ""


def _gist(title: str, context_line: str) -> str:
    return f"{title} — {context_line}" if context_line else title


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


def _escalations_block(steps) -> list[str]:
    escalations = _escalations(steps)
    if not escalations:
        return ["Эскалации: нет"]
    return [f"Эскалации: {len(escalations)} (последняя): {escalations[-1]}"]


def _cost_block(steps, spent_usd: float) -> list[str]:
    lines = [f"Стоимость итого: ${spent_usd:.2f}"]
    for actor, usd, tokens in _actor_costs(steps):
        tail = f", {tokens} токенов" if tokens is not None else ""
        lines.append(f"  {actor}: ${usd:.2f}{tail}")
    return lines


def build_done(conn, task_id: str, merge_sha: str) -> str:
    """RETRO задачи, дошедшей до `done` (требования 4, 5, 8)."""
    t = store.get_task(conn, task_id)
    steps = store.task_steps(conn, task_id)
    context_line = _first_context_line(_read_spec_text(task_id))
    count, manual, skip = _acceptance_counts(task_id)
    address = f"{merge_sha}:tasks/{task_id}/"

    lines = [
        f"# RETRO: {task_id} — {t['title']}",
        "",
        f"Итог: done, sha {merge_sha}",
        f"Адрес артефактов: {address}",
        f"Суть: {_gist(t['title'], context_line)}",
        "",
        *_cost_block(steps, t["spent_usd"] or 0.0),
        "",
        f"Ревью: {t['review_iters']} итераций; "
        f"приёмка: {t['accept_rejects']} отказ(ов)",
        "",
        *_escalations_block(steps),
        "",
        f"Приёмочные тесты: {count} тест(ов), {manual} manual, {skip} skip",
    ]
    return "\n".join(lines) + "\n"


def build_killed(conn, task_id: str) -> str:
    """RETRO задачи, снятой через `kill` (требования 6, 7, 8) — источник
    истины только БД: `tasks/<id>/` к моменту подбора долга (следующий
    `merge_gate` любой другой задачи, решение (d)) обычно уже убран
    `cleanup.cleanup_killed_task`."""
    t = store.get_task(conn, task_id)
    steps = store.task_steps(conn, task_id)
    context_line = _first_context_line(_read_spec_text(task_id))
    count, manual, skip = _acceptance_counts(task_id)
    reason = _last_step_detail(steps, "state -> killed") or "причина не найдена в журнале"

    lines = [
        f"# RETRO: {task_id} — {t['title']}",
        "",
        f"Итог: killed — причина: {reason}",
        f"Адрес артефактов: {NO_ARTIFACTS_NOTE}",
        f"Суть: {_gist(t['title'], context_line)}",
        "",
        *_cost_block(steps, t["spent_usd"] or 0.0),
        "",
        f"Ревью: {t['review_iters']} итераций; "
        f"приёмка: {t['accept_rejects']} отказ(ов)",
        "",
        *_escalations_block(steps),
        "",
        f"Приёмочные тесты: {count} тест(ов), {manual} manual, {skip} skip",
    ]
    return "\n".join(lines) + "\n"
