"""Детерминированная генерация содержимого `docs/retro/<id>.md` (SPEC T043).

Только чтение и вёрстка текста: побочные эффекты (запись файла, `git
add`/`commit`, обработка провала как incident-алерта) — дело
`orchestrator/fsm.py`, тем же разделением, что `orchestrator/review.py`
(сборка пакета) и `orchestrator/acceptance.py` (сводка) отделены от
`orchestrator/fsm.py` (переходы). Источники данных — только журнал
`steps` (`store.task_steps`) и фронтматтеры/тексты артефактов задачи
(`tasks/<id>/SPEC.md`, `tasks/<id>/acceptance_tests/`) — требование 3
(детерминизм): один и тот же вход даёт байт-в-байт одинаковый файл.

С 01M31ZHWJWRSACYMRWTCPBC0DM здесь же живёт ЧИТАТЕЛЬ записей токенов
журнала — разбор строк «agent cost KNOWN»/«agent cost PARTIAL» на
разбивку по видам, провайдера и модель. Читателей у него трое: блок
стоимости RETRO ниже, строка задачи `status`
(`orchestrator/catalog.py`) и разрезы отчёта (`orchestrator/report.py`),
и три копии одной регулярки разошлись бы. Дом выбран этим модулем не по
предмету, а по тому, что разбор записей стоимости журнала регулярками
(`COST_RE`/`TOKENS_RE` ниже) уже здесь; писатель формата
(`orchestrator/spend.py`) для этой задачи — только чтение.

У СУММАРНОГО числа токенов носителей в журнале два, и читатель берёт их
с деградацией (REVIEW.md итерации 1, R1-F1): разбивка по видам есть —
сумма считается по ней, разбивки нет, но «agent run finished» несёт
`токенов N` — берётся это число. Узкое чтение одних лишь записей с
разбивкой показывало бы прочерк «записей токенов нет» там, где журнал
их несёт прежним видом записи (на журнале пульта — 120 задач из 256),
то есть неправду. Прочерк остаётся разбивке по видам и случаю, когда
токенов не записано нигде.
"""
import re
from typing import NamedTuple

from scripts import guard

from . import cleanup, config, models, spend, store

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

#: Прочерк «записей нет» — не ноль (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ линии,
#: требование 5): `sum({})` даёт 0, и он читался бы как «шаг отработал
#: бесплатно». Тот же символ, что у `report._DASH`.
DASH = "—"

#: Действия журнала, несущие разбивку токенов ПО ВИДАМ: обе пишет
#: `orchestrator/spend.py` (`charge_step`/`_charge_by_tariff` — KNOWN,
#: `charge_missing_result` — PARTIAL). Именованной константы у PARTIAL в
#: `spend.py` нет, а завести её эта задача не вправе (модуль — только
#: чтение), поэтому литерал; KNOWN берётся константой писателя.
TOKEN_JOURNAL_ACTIONS = (spend.KNOWN_COST_JOURNAL_ACTION, "agent cost PARTIAL")

#: Действие журнала завершённого шага (`orchestrator/runner.py::
#: _finish_ok`): деньги актёра считаются по нему, и он же — ВТОРОЙ
#: носитель суммарного числа токенов (`spend.cost_note` приписывает
#: `токенов N` к его детали). Разбивки по видам в нём нет.
FINISHED_JOURNAL_ACTION = "agent run finished"

# Поля разбивки в строке журнала — по ОБЕИМ формам имён видов: прежние
# имена (счётчики Claude, `config.LEGACY_TOKEN_KIND_NAMES`) несут строки,
# записанные до 21.09, общие имена (`models.PRICE_KINDS`) — записанные
# после. Пропустить одну из форм значило бы показывать половину журнала
# пустой, молча (тот же довод, что у `spend.known_cost_breakdown`).
#
# `spend.known_cost_breakdown` для этого чтения не годится: она отдаёт
# разбивку только вместе с `actual_usd=`, а этого поля нет ни у строки
# пути расчёта по тарифу (`spend._charge_by_tariff` его намеренно не
# пишет), ни у «agent cost PARTIAL».
#
# Хвост `(?<![a-z_])` отсекает совпадение внутри более длинного имени:
# без него `input=` нашёлся бы в `cache_creation_input_tokens=…`.
_TOKEN_FIELD_RE = tuple(
    (kind, re.compile(rf"(?<![a-z_]){re.escape(name)}=(\d+)"))
    for name, kind in
    list(config.LEGACY_TOKEN_KIND_NAMES.items())
    + [(kind, kind) for kind in models.PRICE_KINDS])

#: `provider=` строки журнала (`runner._numbered_with_model`) — тем же
#: приёмом, что `spend._MODEL_FIELD_RE` читает `model=`: значение до
#: пробела/запятой, хвостовое двоеточие поля в значение не входит
#: (`provider=` стоит последним в `numbered`, и учёт приписывает к нему
#: `": "`).
_PROVIDER_FIELD_RE = re.compile(r"provider=([^\s,]+?):?(?=[\s,]|$)")


def _detail_tokens(detail: str) -> dict:
    """Разбивка по видам из детали записи журнала; пустой словарь — полей
    разбивки в строке нет (запись старого формата, чужое действие)."""
    by_kind: dict = {}
    for kind, pattern in _TOKEN_FIELD_RE:
        match = pattern.search(detail or "")
        if match is not None:
            by_kind[kind] = int(match.group(1))
    return by_kind


def token_breakdown_by_actor(steps) -> dict:
    """{actor: {вид: число}} по записям `TOKEN_JOURNAL_ACTIONS` журнала.

    Актёр без единой разобранной записи в результат НЕ попадает вовсе —
    именно это отличает «записей токенов нет» от «токенов ноль»
    (требование 5): пустой словарь на месте разбивки был бы неотличим от
    честного нуля по всем четырём видам.
    """
    by_actor: dict = {}
    for s in steps:
        if s["action"] not in TOKEN_JOURNAL_ACTIONS:
            continue
        found = _detail_tokens(s["detail"])
        if not found:
            continue
        totals = by_actor.setdefault(s["actor"], {})
        for kind, count in found.items():
            totals[kind] = totals.get(kind, 0) + count
    return by_actor


def task_token_breakdown(steps) -> dict:
    """Суммарная разбивка по видам по ВСЕМ актёрам переданного журнала;
    пустой словарь — записей токенов нет (показывается прочерком)."""
    totals: dict = {}
    for by_kind in token_breakdown_by_actor(steps).values():
        for kind, count in by_kind.items():
            totals[kind] = totals.get(kind, 0) + count
    return totals


def token_totals_by_actor(steps) -> dict:
    """{actor: суммарное число токенов} по ОБОИМ носителям суммы, с
    деградацией: шаг с разбивкой по видам считается по ней, шаг без
    разбивки — по числу `токенов N` строки завершения (REVIEW.md
    итерации 1, R1-F1).

    Актёра без единой записи токенов в результате нет вовсе — это и
    отличает «записей нет» (прочерк) от «токенов ноль» (требование 5).

    Оба носителя ОДНОГО шага стоят в журнале рядом и сложились бы
    дважды: `spend.charge_step` пишет «agent cost KNOWN» и возвращает
    вызывающему хвост, который `runner._finish_ok` кладёт в «agent run
    finished» теми же токенами. Поэтому строка завершения гасит одну
    ещё не погашенную запись с разбивкой ТОГО ЖЕ актёра, а своё число
    прибавляет, только когда гасить нечего: тогда разбивки у шага не
    было вовсе (журнал до появления разбивки по видам, либо путь учёта,
    который её не пишет). Считать по парам «шаг = попытка N/M» нельзя —
    номер попытки повторяется у каждого шага роли внутри задачи.
    """
    totals: dict = {}
    pending: dict = {}
    for s in steps:
        actor = s["actor"]
        if s["action"] in TOKEN_JOURNAL_ACTIONS:
            found = _detail_tokens(s["detail"])
            if found:
                totals[actor] = totals.get(actor, 0) + sum(found.values())
                pending[actor] = pending.get(actor, 0) + 1
            continue
        if s["action"] != FINISHED_JOURNAL_ACTION:
            continue
        match = TOKENS_RE.search(s["detail"] or "")
        if match is None:
            continue
        if pending.get(actor):
            pending[actor] -= 1
            continue
        totals[actor] = totals.get(actor, 0) + int(match.group(1))
    return totals


def task_token_total(steps) -> int | None:
    """Суммарное число токенов задачи по всем её актёрам; `None` —
    записей токенов нет ни одним видом записи (показывается прочерком)."""
    totals = token_totals_by_actor(steps)
    return sum(totals.values()) if totals else None


def tokens_text(by_kind: dict | None) -> str:
    """Разбивка по четырём видам строкой, либо прочерк — записей нет."""
    if not by_kind:
        return DASH
    return ", ".join(f"{kind}={by_kind.get(kind, 0)}"
                     for kind in models.PRICE_KINDS)


def total_tokens_text(total: int | None) -> str:
    """Суммарное число токенов строкой, либо прочерк — записей нет.

    Отличается именно `None`, а не нулём: записанный журналом ноль —
    факт («шаг не потребил токенов»), а прочерк — его отсутствие."""
    return DASH if total is None else str(total)


def tokens_detail_text(total: int | None, by_kind: dict | None) -> str:
    """Сумма токенов и разбивка по видам одним куском текста — ОДНИМ
    правилом на все три места показа (REVIEW.md итерации 2, R2-F1).

    Носителей у суммы два, а разбивку по видам несёт только один из них
    (`token_totals_by_actor`), поэтому разбивка бывает УЖЕ суммы: она
    покрывает часть шагов строки, а не все. Скобки при числе читаются
    как его разложение, и молчаливое расхождение врёт: на журнале пульта
    так расходятся все четыре строки разреза ролей отчёта (`developer`:
    6 252 661 902 против 3 375 837 567 в скобках). Поэтому неполная
    разбивка называет свою сумму явно.

    Три формы:
    - разбивки нет вовсе — «токенов N, разбивка по видам —»;
    - разбивка покрывает всю сумму — «токенов N (input=…, …)»;
    - покрывает часть — «токенов N (с разбивкой M: input=…, …)»."""
    total_part = f"токенов {total_tokens_text(total)}"
    if not by_kind:
        return f"{total_part}, разбивка по видам {DASH}"
    covered = sum(by_kind.values())
    if covered == total:
        return f"{total_part} ({tokens_text(by_kind)})"
    return f"{total_part} (с разбивкой {covered}: {tokens_text(by_kind)})"


def usd_text(usd: float | None) -> str:
    """Деньги актёра строкой, либо прочерк — записей стоимости нет.

    Тем же правилом, что и токены: `$0.00` у актёра, чью стоимость
    журнал не записал, читался бы как «шаг прошёл бесплатно»."""
    return DASH if usd is None else f"${usd:.2f}"


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


class ActorCost(NamedTuple):
    """Разрез расхода по одному актёру журнала: деньги, суммарные токены,
    разбивка токенов по видам, провайдер и модель его шагов.

    `tokens` — пустой словарь, `total`/`provider`/`model` — `None`, когда
    записей соответствующего вида по актёру нет вовсе: показывается это
    прочерком, не нулём (требование 5). `usd` — тоже `None`, когда
    стоимости актёра журнал не записал: актёр попадает в разрез и с
    одними лишь токенами (REVIEW.md итерации 1, R1-F2).

    `total` отдельным полем, а не `sum(tokens.values())`: сумма
    известна и у шага без разбивки по видам, и складывать её не из
    чего."""

    actor: str
    usd: float | None
    tokens: dict
    total: int | None
    provider: str | None
    model: str | None


def _journal_provider(detail: str) -> str | None:
    """Провайдер из поля `provider=` строки журнала; `None` — поля нет
    (строка старого формата, либо путь учёта, которому `runner` поля не
    приписывает). Пара к `spend.journal_model`, читающей `model=`."""
    match = _PROVIDER_FIELD_RE.search(detail or "")
    return match.group(1) if match else None


def _first_field(steps, actor: str, read) -> str | None:
    """Значение, которое `read(detail)` вернёт по первой записи токенов
    ЭТОГО актёра; `None` — ни одна запись его не несёт.

    Именно этого актёра, а не первой подходящей строки журнала: разрез
    отвечает на вопрос «чей это счёт», и провайдер соседней роли в строке
    роли был бы прямой ложью."""
    for s in steps:
        if s["actor"] != actor or s["action"] not in TOKEN_JOURNAL_ACTIONS:
            continue
        value = read(s["detail"] or "")
        if value is not None:
            return value
    return None


def _actor_costs(steps) -> list[ActorCost]:
    """Разрез по actor (не по каждому событию — иначе число строк растёт
    с числом попыток/итераций, а не с числом ролей, и не даёт статической
    гарантии лимита 30 строк, PLAN п.2).

    Деньги по-прежнему считаются по событиям `agent run finished`: задача
    01M31ZHWJWRSACYMRWTCPBC0DM ставит токены РЯДОМ с долларами, а не
    переучитывает доллары. Разбивка по видам, провайдер и модель
    приезжают из строк `TOKEN_JOURNAL_ACTIONS` — единственных, где они
    вообще есть; суммарное число — из обоих носителей
    (`token_totals_by_actor`).

    Список актёров — ОБЪЕДИНЕНИЕ обоих множеств (REVIEW.md итерации 1,
    R1-F2): актёр, чьи токены журнал записал, а стоимость — нет (шаг не
    дошёл до строки завершения), прежде исчезал из разреза целиком,
    вместе со своими токенами. Деньги такого актёра показываются
    прочерком, не нулём."""
    tokens_by_actor = token_breakdown_by_actor(steps)
    totals_by_actor = token_totals_by_actor(steps)
    order: list[str] = []
    usd_by_actor: dict[str, float] = {}
    for s in steps:
        actor = s["actor"]
        if s["action"] == FINISHED_JOURNAL_ACTION:
            cost_m = COST_RE.search(s["detail"] or "")
            if cost_m is not None:
                usd_by_actor[actor] = (usd_by_actor.get(actor, 0.0)
                                       + float(cost_m.group(1)))
        if actor not in order and (actor in usd_by_actor
                                   or actor in totals_by_actor):
            order.append(actor)
    return [ActorCost(actor, usd_by_actor.get(actor),
                      tokens_by_actor.get(actor, {}),
                      totals_by_actor.get(actor),
                      _first_field(steps, actor, _journal_provider),
                      _first_field(steps, actor, spend.journal_model))
            for actor in order]


def actor_costs(steps) -> list[ActorCost]:
    """Тот же разрез по актёрам, что печатает блок стоимости RETRO, —
    публичным адресом для `orchestrator/report.py` (разрез расхода и
    токенов по ролям, требование 4).

    Приватное имя `_actor_costs` оставлено как есть: на него ссылается
    комментарий `orchestrator/cleanup.py` рядом с
    `KILL_TZ_JOURNAL_ACTION`, а этот модуль вне зоны задачи."""
    return _actor_costs(steps)


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


def _actor_cost_line(row: ActorCost) -> str:
    """Строка роли блока стоимости: деньги, сумма токенов, разбивка по
    четырём видам, провайдер и модель ЕЁ шагов (SPEC
    01M31ZHWJWRSACYMRWTCPBC0DM, требования 2-3).

    Роль без записей токенов несёт прочерк вместо КАЖДОГО из этих чисел
    (требование 5): `input=0, output=0, …` читалось бы как «роль
    отработала бесплатно», а не как «пульт разбивку не записал».

    Сумма и разбивка показываются НЕЗАВИСИМО: у роли, чьи шаги записаны
    прежним видом записи, сумма известна, а разбивки нет — такая роль
    несёт число рядом с прочерком разбивки (REVIEW.md итерации 1,
    R1-F1), а не прочерк вместо обоих. Разбивка, покрывающая ЧАСТЬ шагов
    роли, называет свою сумму явно — `tokens_detail_text` (REVIEW.md
    итерации 2, R2-F1)."""
    return (f"  {row.actor}: {usd_text(row.usd)}, "
            f"{tokens_detail_text(row.total, row.tokens)}, "
            f"провайдер {row.provider or DASH}, модель {row.model or DASH}")


def _cost_block(steps, spent_usd: float,
                spent_estimate_usd: float = 0.0) -> list[str]:
    lines = [f"Стоимость итого: ${spent_usd:.2f}"]
    # Верхняя оценка (SPEC 01M1NWCM3TDY0YABEKE8DYQA1C, требование 7) —
    # отдельной строкой от «Стоимость итого», и только когда она есть:
    # задача без частичных шагов без курса не обзаводится строкой «$0.00».
    if spent_estimate_usd > 0:
        lines.append(
            f"Верхняя оценка неучтённой стоимости: ${spent_estimate_usd:.2f}")
    # Роль — ОДНОЙ строкой, сколько бы полей в неё ни добавили (SPEC
    # 01M31ZHWJWRSACYMRWTCPBC0DM, требования 2-3): число строк блока
    # растёт с числом ролей, и потолок 30 строк done-RETRO (требование 4
    # SPEC T043) держится именно этим — три строки на роль пробили бы его
    # на полном наборе ролей-агентов.
    for row in _actor_costs(steps):
        lines.append(_actor_cost_line(row))
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
