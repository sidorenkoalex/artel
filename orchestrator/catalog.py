"""Каталог задач: заведение, список, карточка задачи, журнал шагов."""
import json
import re
import shutil
import socket
import sys
from pathlib import Path

from scripts import guard

from . import (alerts, artifact_branch, artifacts, budget, config, cycle_hint,
              gitcmd, idgen, liveness, merge_queue, models, providers, retro, runner,
              store, zone_lock)

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
    """Заводит состояние пульта; на непустом проекте — холодный старт
    (SPEC T049, ADR-0005 п.5): счётчик номеров, слой ролей и программный
    расход досеваются от наблюдаемого мира, а не остаются пустыми.
    """
    conn = store.db()
    store.create_schema(conn)
    # `store.db()` выше уже звал `migrate()`, но ДО `create_schema` — на
    # свежей БД таблиц ещё не было, и `migrate` вышла первой же строкой
    # («табиц tasks ещё нет — схему ставит init»), не дойдя до сева.
    # Явный вызов здесь делает посев частью самого `init` (требование 2),
    # а не побочным эффектом первого следующего `store.db()`.
    store.seed_task_counters(conn)
    _deploy_role_home_reference()
    # Локальный слой моделей (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD, требование
    # 7): без него ни один агентный шаг не стартует — ярус роли не во что
    # разрешать. Шаблон кладётся только при отсутствии файла: выбор
    # Оператора `init` не перезаписывает (AC-9), тем же приёмом, что и
    # развёртывание дома роли выше.
    if models.ensure_local_template():
        print(f"OK: шаблон локального слоя моделей — {config.MODELS_LOCAL}")
    budget.reseed_program_spend(conn)
    # Ленивый импорт — `pool_seal.py` перенял эту функцию у `canary.py`
    # (SPEC 01M2CN42RV0EBBP7HS4HP2VNY1); `canary.py` по-прежнему сам
    # импортирует `catalog` на уровне модуля (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW,
    # требование 3) — та же лень оставлена и для нового источника.
    from . import pool_seal
    restore_msg = pool_seal.restore_pool_if_missing(conn)
    if restore_msg:
        print(restore_msg)
    print(f"OK: состояние в {config.DB}")
    print("Задачи в полёте (ветки task/* без строки в БД) холодный старт "
         "не восстанавливает автоматически — пересборка по веткам "
         "остаётся ручной сверкой Оператора (SPEC T049, требование 11).")


def _deploy_role_home_reference() -> None:
    """Разворачивает курируемый слой ролей из референса пульта, если
    `.artel/home` ещё не существует (SPEC T049, требования 8-9, AC-5).

    Какой каталог референса разворачивать и под каким именем, называет
    сам провайдер исполнителя роли (`home_reference()`, SPEC
    01M2ZNTHSNFYSTF904P6SZTPYF, требование 7): для `claude` —
    `docs/reference/role-home/claude/` в `.artel/home/.claude/`, то же
    самое, что этот код нёс литералом до задачи. Имя без ведущей точки
    в самом репозитории (docs/reference/role-home.md), переименование —
    только здесь, при развёртывании.

    Референса нет на диске вовсе (ни у одного провайдера) — каталог
    дома роли не создаётся: прежнее поведение на дереве без
    `docs/reference/`.
    """
    if config.ROLE_HOME.exists():
        return
    references = [ref for ref in providers.home_references()
                  if ref.reference.is_dir()]
    if not references:
        return
    config.ROLE_HOME.mkdir(parents=True)
    for reference in references:
        shutil.copytree(reference.reference,
                        config.ROLE_HOME / reference.deployed_name)


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


# Подсказка калибровки потолка при `new` (SPEC 01M1TQ11K4WJZD7ZE3MR0J4ZK4,
# требование 2): активна только если ТЗ несёт буквальную строку «Рамка:
# $N» — иначе Оператор просто не выразил рамку в этом формате, и
# подсказывать не о чем.
_TZ_RAMA_RE = re.compile(r"Рамка:\s*\$(\d+(?:\.\d+)?)")
# Раздел «Требуется:» — до первой пустой строки (тот же формат, что и
# нумерованный список без AC-разметки, `guard.PLAIN_NUMBERED_ITEM`).
_TZ_TREBUETSYA_RE = re.compile(r"Требуется:[ \t]*\n(.*?)(?:\n[ \t]*\n|\Z)",
                              re.S)
# Заякорен на начало строки (`re.M`) — иначе первое по тексту вхождение
# «Зоны:» в прозе (например, в пояснении требования 2 самого ТЗ) даёт
# ложное совпадение раньше настоящей строки «Зоны: ...» (REVIEW.md
# итерации 1, R1-F1). Захват продолжается за перенос строки (`re.S` +
# `.*?`) до пустой строки, следующей метки-раздела (Cyrillic-слово с
# двоеточием на новой строке — «Порядок:», «Не входит:» и т.п. могут
# идти сразу за «Зоны:» без пустой строки между ними) или конца текста.
_TZ_LABEL_LINE = r"[ \t]*[А-ЯЁ][А-Яа-яЁё]*:"
_TZ_ZONES_RE = re.compile(
    r"^Зоны:[ \t]*(.*?)(?:\n[ \t]*\n|\n(?=" + _TZ_LABEL_LINE + r")|\Z)",
    re.M | re.S)


# Сверка упомянутых в ТЗ путей с зонами (01M2XJKQNFTWHYAY4KBBQ1NVY7,
# требования 2-4). Разделы ТЗ Оператора — метка в начале строки
# («Зоны:», «Не входит:», «Только чтение (не менять):», «Приложением:»),
# тело до пустой строки, следующей метки или конца текста — тот же
# приём, что `_TZ_ZONES_RE` выше, но метка — параметр, а границей
# считается и многословная метка со скобками (`_TZ_ANY_LABEL_LINE`):
# «Только чтение (не менять):» однословный `_TZ_LABEL_LINE` границей не
# признаёт.
_TZ_ANY_LABEL_LINE = r"[ \t]*[А-ЯЁ][А-Яа-яЁё ()\-]*:"
# Метки классифицирующих разделов ТЗ (требование 2): «Только чтение…:»
# допускает хвост в скобках между словами и двоеточием.
_TZ_ZONES_LABEL = r"Зоны"
_TZ_DECLARING_LABELS = (r"Не входит", r"Только чтение[^:\n]*", r"Приложением")


def _tz_section_re(label: str) -> re.Pattern:
    return re.compile(
        r"^" + label + r":[ \t]*(.*?)(?:\n[ \t]*\n|\n(?=" + _TZ_ANY_LABEL_LINE
        + r")|\Z)", re.M | re.S)


def _tz_sections(tz_raw: str, labels,
                 joiner: str = "\n") -> tuple[str, list[tuple[int, int]]]:
    """(тела разделов с метками `labels`, склеенные `joiner`, их диапазоны
    в `tz_raw`) — все вхождения каждой метки, не только первое.

    `joiner` — параметр, потому что разбор зон (`_tz_zone_items`) склеивает
    тела запятой: для него граница двух тел — граница ЭЛЕМЕНТОВ перечня, а
    перенос строки он снимает как вёрстку (R2-F1), и тело, склеенное с
    соседним переносом, дало бы один элемент из двух зон."""
    bodies: list[str] = []
    spans: list[tuple[int, int]] = []
    for label in labels:
        for match in _tz_section_re(label).finditer(tz_raw):
            bodies.append(match.group(1))
            spans.append(match.span())
    return joiner.join(bodies), spans


def _tz_path_check(tz_raw: str) -> tuple[list[str], list[str]]:
    """(неклассифицированные пути ТЗ, защищённые пути из «Зоны:») —
    требования 2-4. Путь классифицирован, если покрыт «Зоны:» (с
    вложенностью и `config.COMMON_ZONES`, `guard.unclassified_paths`)
    либо назван в «Не входит:»/«Только чтение…:»/«Приложением:»;
    проверяется текст ТЗ ЗА ВЫЧЕТОМ этих четырёх разделов. Защищённость
    (`config.PROTECTED_PATHS`) сверяется только по элементам «Зоны:» —
    защищённый путь, названный «Приложением:», проходит (требование 4)."""
    zones_text, zone_spans = _tz_sections(tz_raw, (_TZ_ZONES_LABEL,))
    declared_text, declared_spans = _tz_sections(tz_raw, _TZ_DECLARING_LABELS)
    checked = list(tz_raw)
    for start, end in zone_spans + declared_spans:
        checked[start:end] = [" "] * (end - start)
    zones = guard.zone_items(zones_text)
    unclassified = guard.unclassified_paths("".join(checked), zones,
                                            declared_text)
    return unclassified, guard.protected_zones(zones)


def _tz_path_refusal(tz_path: str, tz_raw: str) -> str | None:
    """Текст отказа `new` по путям ТЗ (требования 3-4) либо `None`, если
    ТЗ сверку прошло — обе причины разом, чтобы Оператор чинил ТЗ за
    один заход."""
    unclassified, protected = _tz_path_check(tz_raw)
    lines = []
    if unclassified:
        lines.append(f"ТЗ {tz_path}: "
                     f"{guard.unclassified_paths_refusal(unclassified)}")
    if protected:
        lines.append(f"ТЗ {tz_path}: в «Зоны:» {', '.join(protected)} — "
                     f"{guard.PROTECTED_ZONE_REFUSAL}")
    return "\n".join(lines) if lines else None


def _tz_calibration_inputs(tz_raw: str) -> tuple[float, int, int] | None:
    """(рамка, число пунктов «Требуется:», число путей «Зоны:») из
    свободного текста ТЗ — `None`, если ТЗ не несёт строку «Рамка: $N»
    (требование 2: подсказка активна только при этом условии)."""
    rama_match = _TZ_RAMA_RE.search(tz_raw)
    if rama_match is None:
        return None
    rama = float(rama_match.group(1))

    trebuetsya_match = _TZ_TREBUETSYA_RE.search(tz_raw)
    ac_count = (len(guard.PLAIN_NUMBERED_ITEM.findall(trebuetsya_match.group(1)))
               if trebuetsya_match else 0)

    zones_match = _TZ_ZONES_RE.search(tz_raw)
    zone_files = budget.count_zone_paths(
        zones_match.group(1) if zones_match else None)

    return rama, ac_count, zone_files


def _print_new_calibration_hint(conn, task_id: str, tz_raw: str) -> None:
    """Печатает ориентир калибровки против «Рамки: $N» ТЗ и, при
    занижении больше чем на треть, предупреждение + запись в журнал
    (требования 2, AC-5/AC-6/AC-7). Не отказывает и не меняет потолок
    задачи (AC-8) — только печатает и, при срабатывании, журналирует."""
    calib = _tz_calibration_inputs(tz_raw)
    if calib is None:
        return
    rama, ac_count, zone_files = calib
    orientir = budget.recommended_budget_usd(ac_count, zone_files)
    print(f"[{task_id}] калибровка: ориентир ~${orientir:.2f} по ТЗ "
         f"({ac_count} «Требуется:», {zone_files} «Зоны:») против рамки "
         f"${rama:.2f}")
    warning = budget.calibration_warning(rama, orientir)
    if warning is not None:
        store.journal(conn, task_id, "operator", "калибровка бюджета", warning)
        print(f"[{task_id}] ВНИМАНИЕ: {warning}")


# Фиксированный текст действия журнала (SPEC 01M3GKJ84XM5QPC6TK5EE307Q9,
# требование 2): читатель журнала и тест находят запись по ДЕЙСТВИЮ, а не
# по вариативному detail (тот несёт конкретные id, состояния и пути).
ZONE_OVERLAP_ACTION = "пересечение зон при заведении"


# Фиксированный текст действия журнала (ответ Оператора ANSWER-1 п.2 по
# замечанию R1-F2 ревью итерации 1): предварительные зоны ТЗ, записанные в
# `tasks.zones` при заведении. Оператор читает по нему, откуда взялось
# значение колонки до гейта SPEC (approve на `spec_gate` перезапишет его
# зонами SPEC).
PRELIMINARY_ZONES_ACTION = "предварительные зоны из ТЗ"


# Перенос строки ВНУТРИ пути (замечание R2-F1 ревью итерации 2): вёрстка
# ТЗ по ~72 символа рвёт длинный путь, и точка разрыва — `/`, `-` или `_`
# (на 215 живых ТЗ пульта встречаются ровно такие: `orchestrator/⏎
# schema.py`, `docs/reference/⏎role-home.md`, `константа-⏎ориентир`).
# Разрыв склеивается ДО разбора: иначе обрывок перед переносом
# (`orchestrator/`) становится самостоятельной зоной-каталогом и накрывает
# почти любую задачу пульта (ложное пересечение), а сам путь теряется
# целиком (пропуск настоящего — ровно прецедент «Контекста» SPEC, где
# рвётся `docs/operator-session.md`).
#
# Снимать ВСЕ переносы нельзя: перенос после слова склеил бы прозу с
# путём, стоящим в начале следующей строки («… задачи 01M3FQ2V77⏎
# docs/stack.md»), а `guard.PATH_MENTION` запрещает букву/цифру слева от
# кандидата — путь пропал бы. Разрыв в иной точке (`orchestrator/con⏎
# fig.py`) не склеивается и остаётся, как до задачи: он даёт только
# непуть-элемент, но не обрывок-каталог, то есть промах, а не ложное
# срабатывание.
_TZ_WRAPPED_PATH_BREAK = re.compile(r"(?<=[/_-])\n[ \t]*")


def _tz_zone_items(tz_raw: str) -> list[str]:
    """Элементы строки `Зоны:` ТЗ — как они написаны, без фильтра общих
    зон. Разбор — ТОТ ЖЕ, что у существующей сверки путей ТЗ
    (`_tz_path_check`): один `_tz_sections` + `guard.zone_items` на все
    проверки одной команды, иначе перенос строки `Зоны:` или следующая
    метка-раздел разошлись бы между ними — плюс склейка пути, разорванного
    вёрсткой ТЗ (`_TZ_WRAPPED_PATH_BREAK`, замечание R2-F1).

    Отсортировано: `guard.zone_items` отдаёт МНОЖЕСТВО, и порядок его
    обхода у строк меняется от процесса к процессу (hash randomization)
    — записанное в `tasks.zones` значение обязано быть одинаковым при
    одном и том же ТЗ."""
    zones_text, _ = _tz_sections(tz_raw, (_TZ_ZONES_LABEL,), joiner=",")
    return sorted(guard.zone_items(_TZ_WRAPPED_PATH_BREAK.sub("", zones_text)))


def _tz_zone_paths(tz_raw: str) -> set[str]:
    """Пути строки `Зоны:` ТЗ — множеством, без путей, покрытых
    `config.COMMON_ZONES` (`zone_lock._own_paths`)."""
    return zone_lock._own_paths(",".join(_tz_zone_items(tz_raw)))


def _record_preliminary_zones(conn, task_id: str, tz_raw: str) -> None:
    """Зоны строки `Зоны:` ТЗ — в колонку `tasks.zones` СРАЗУ при
    заведении, как предварительные (ответ Оператора ANSWER-1 п.2). Зовут
    оба входа заведения: `cmd_new` (ТЗ Оператора) и `spawn_subtask`
    (подраздел секции «## Деление», SPEC 01M3H1Z489CKJ8FHSRS4TYTPX2,
    требование 1).

    Без этой записи колонка пуста до approve на гейте SPEC
    (`fsm._approve_spec_gate` — единственный, кто её писал), и прогноз
    очереди зон слеп ровно к тем состояниям, ради которых он и заведён:
    задача, чей SPEC пишется прямо сейчас, не попадала бы ни в
    предупреждение `new` (требование 1), ни в добавку `status`
    (требование 3) — то есть волна из «Контекста» SPEC не ловилась бы
    (замечание R1-F2 ревью итерации 1).

    Предварительность значения — в том, что его перезаписывает approve на
    `spec_gate` зонами SPEC (поведение не меняется); reject на том же
    гейте зон не пишет вовсе, и предварительное значение переживает
    возврат аналитику. Пустая строка `Зоны:` колонку не трогает: `NULL`
    остаётся признаком «зона не заявлена вовсе», который читают
    `checkpoint._zone_paths` и гейт зон."""
    items = _tz_zone_items(tz_raw)
    if not items:
        return
    zones = ", ".join(items)
    store.update_task(conn, task_id, zones=zones)
    store.journal(conn, task_id, "operator", PRELIMINARY_ZONES_ACTION, zones)


def _zone_overlap_warning_text(matches: list) -> str:
    """Текст предупреждения `new` о пересечении зон (требование 2): по
    строке на пересекающуюся задачу — общий путь, её id и состояние."""
    lines = ["ВНИМАНИЕ: зоны ТЗ пересекаются с задачами в полёте — "
            "задача встанет в очередь замка зон:"]
    lines += [f"  {path} — {task_id} ({state})" for path, task_id, state in matches]
    return "\n".join(lines)


def _warn_zone_overlap(conn, task_id: str, tz_raw: str,
                       target: str | None = None) -> None:
    """Предупреждение о пересечении зон ТЗ с зонами задач в полёте (SPEC
    01M3GKJ84XM5QPC6TK5EE307Q9, требования 1-2): печатается и
    журналируется ПОСЛЕ заведения строки задачи, тем же приёмом, что
    подсказка калибровки выше, и отказом НЕ становится — задача заведена,
    код возврата `new` тот же, что без пересечения. Второй вызыватель —
    `spawn_subtask` (SPEC 01M3H1Z489CKJ8FHSRS4TYTPX2, требование 2): для
    подзадачи деления «не отказ» тем важнее, что `sys.exit` оставил бы
    родителя поделённым на часть заявленных частей.

    Набор состояний — `zone_lock.FORECAST_STATES` (занимающие плюс те, что
    займут зону позже); признак «занимает зону» (`zone_lock._occupies`) не
    применяется: это прогноз будущей очереди, а не отказ входа в `in_dev`.

    Задача ЧУЖОГО target'а предупреждения не получает (ответ Оператора
    ANSWER-1 п.3 по замечанию R1-F3): замок зон — механика только
    основного target'а (`zone_lock.blocking_conflict` отдаёт `None` любой
    задаче не-`DEFAULT_TARGET`), очереди для такой задачи не будет
    никогда, и обещать её в журнале нечем. Тот же фильтр, что у парной
    добавки `status` (`_zone_forecast_suffix`)."""
    if (target or config.DEFAULT_TARGET) != config.DEFAULT_TARGET:
        return
    matches = zone_lock.forecast_overlaps(conn, _tz_zone_paths(tz_raw),
                                          exclude_task_id=task_id)
    if not matches:
        return
    warning = _zone_overlap_warning_text(matches)
    store.journal(conn, task_id, "operator", ZONE_OVERLAP_ACTION,
                 "; ".join(f"{path}: {other} ({state})"
                           for path, other, state in matches))
    print(f"[{task_id}] {warning}")


def _pin_divergence_warning_text(commits: list) -> str:
    """Текст предупреждения `cmd_new` о непушенных коммитах главной
    копии (SPEC 01M297HFSKV3GVZJ9YF20FZEZE, требование 3, AC-7): sha (7
    символов) и первая строка сообщения каждого коммита, одной строкой
    на коммит."""
    lines = [f"ВНИМАНИЕ: пин расходится с origin — {len(commits)} "
            f"непушенных коммитов главной копии:"]
    lines += [f"  {sha[:7]} {msg}" for sha, msg in commits]
    return "\n".join(lines)


def _pin_divergence_journal_detail(commits: list) -> str:
    """Текст записи журнала о расхождении пина (AC-7: «пин расходится с
    origin: N коммитов»)."""
    return f"пин расходится с origin: {len(commits)} коммитов"


def _warn_pin_divergence(conn, task_id: str) -> None:
    """Предупреждение о непушенных коммитах главной копии (SPEC
    01M297HFSKV3GVZJ9YF20FZEZE, требования 2-3): заведение задачи не
    блокируется расхождением (AC-7) — только видимость Оператору.

    `git fetch origin <MAIN_BRANCH>` не удался (нет сети, нет origin,
    песочница без настоящего git) — молчим (AC-8): недоступность origin
    — это «сверка не проведена», не повод трактовать её как расхождение.
    Импорт `doctor` — лениво, внутри функции: `doctor/__init__.py`
    импортирует `canary`, которая импортирует этот модуль (`catalog`) на
    уровне модуля — импорт `doctor` здесь на уровне модуля дал бы цикл
    (тот же приём, что уже несёт `cmd_init` для `canary`).
    """
    from . import doctor
    root_sha = gitcmd.head_sha()
    origin_sha, _ = doctor.fetch_origin_main_sha()
    if not origin_sha:
        return
    commits = doctor.unpushed_commits(root_sha, origin_sha)
    if not commits:
        return
    print(f"[{task_id}] {_pin_divergence_warning_text(commits)}")
    store.journal(conn, task_id, "operator", "pin-divergence",
                 _pin_divergence_journal_detail(commits))


def cmd_new(title: str, tz_path: str | None = None, *,
           canary: bool = False, target: str | None = None,
           model_set: str | None = None) -> str:
    """Заводит задачу: ТЗ/SPEC рождаются сразу в её ветке (ADR-0005 п.9,
    SPEC T048) — рабочая копия main не трогается ни на одном шаге
    (требование 4): ни новых файлов на диске main, ни коммитов в main.

    Id — ULID (SPEC T094, требование 2, AC-2): единственный генератор —
    `idgen.new_task_id()`, без счётчика и без коллизий по построению —
    ранняя peek-проверка ветки (T048) и повторный расход счётчика после
    неё, нужные только под гонку конкурентного `next_task_number`,
    отсюда убраны вместе с самим счётчиком как источником id (контур
    `task_counters` остаётся, но заморожен как legacy — требование 6, не
    удаляется этой задачей).

    `target` (SPEC T094, требования 7-9, AC-8/AC-9; A7 требование 2 —
    снятие особого случая догфуда) — keyword-only, `None` дефолтится в
    `config.DEFAULT_TARGET` (артель). Для ЛЮБОГО target, включая
    артель, `tasks/<id>/` коммитится ВЕТКОЙ ПУЛЬТА (`orchestrator/
    artifact_branch.py`) — кодовая ветка `branch` только ЗАПИСЫВАЕТСЯ в
    БД (её создание и код — дело роли-разработчика в клоне целевого
    либо, для артели, в `config.ROOT` напрямую; эта функция туда не
    пишет вовсе, AC-9). Push артефактной ветки в origin пульта —
    best-effort (требование 7, AC-8): отказ сети не отменяет заведение
    задачи, но журналируется классифицированной причиной (SPEC
    01M1TQ0X14Y5B3C87WC0Q31PK2, требование 1). До A7 self/догфуд
    заводил worktree и кодовую ветку сама
    (требование 16/AC-18 M1) — этот путь (`_new_dogfood`) убран вместе
    со особым случаем (A7, AC-5): исторические задачи в `tasks/`
    пульта, заведённые им, не трогаются, но новые задачи артели идут
    тем же generic-путём, что и любой другой target.

    `canary` — keyword-only, дефолт `False` не меняет поведение
    существующих вызывателей: команда `canary` (tasks/T065/SPEC.md,
    требование 1) заводит свои задачи через ЭТУ же функцию с `canary=True`,
    пишущим пометку ТОЛЬКО в колонку БД `tasks.is_canary` (требование 6),
    не в `title` — `title` канареечной задачи ничем не отличается от
    продуктовой, роль его не видит иначе. Возвращает `task_id`, чтобы
    вызывающий код (тот же `canary`) мог собрать список заведённых задач.

    `model_set` — набор моделей задачи из `model_sets.yaml` (`new --set`,
    SPEC 01M3YCHS4F08VTV6XX10VF92H3, требования 1, 3): допуск набора
    проверкой части 1 (`models.admitted_set_members`) сверяется ДО id,
    ветки и строки БД — отказ не оставляет ни того, ни другого. Имя и
    состав набора на момент `new` пишутся в строку задачи той же записью, что
    заводит саму строку (`store.insert_task`).
    """
    conn = store.db()
    set_members = None
    if model_set is not None:
        try:
            set_members = models.admitted_set_members(conn, model_set)
        except models.ModelsError as exc:
            sys.exit(f"new: {exc} — задача не заведена")
    # Файл ТЗ читается ДО побочных эффектов: нечитаемый путь не должен
    # оставлять после себя наполовину созданную задачу.
    tz_raw = None
    if tz_path is not None:
        try:
            tz_raw = Path(tz_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            sys.exit(f"ТЗ не прочитано из {tz_path}: {exc}")
        # Сверка путей ТЗ с зонами (01M2XJKQNFTWHYAY4KBBQ1NVY7, требования
        # 2-4) — здесь же, ДО id/ветки/строки БД (требование 3, AC-3):
        # отказ не оставляет ни артефактной ветки, ни строки задачи.
        refusal = _tz_path_refusal(tz_path, tz_raw)
        if refusal is not None:
            sys.exit(refusal)

    target = target or config.DEFAULT_TARGET
    task_id = idgen.new_task_id()
    tz_doc = _tz_document(task_id, title, tz_raw) if tz_raw is not None else None

    _new_task_row(conn, task_id, title, target, tz_doc, is_canary=canary,
                 journal_detail=title, model_set=model_set,
                 set_members=set_members)
    if tz_raw is not None:
        _record_preliminary_zones(conn, task_id, tz_raw)
    print(f"[{task_id}] «{title}» создана (target {target}, артефактная "
         f"ветка пульта {artifact_branch.branch_name(task_id)})")
    if model_set is not None:
        print(f"  набор задачи: {model_set} "
              f"({models.members_text(set_members)}); приёмка — ручной "
              f"гейт Оператора")
    _warn_pin_divergence(conn, task_id)
    if tz_raw is not None:
        _print_new_calibration_hint(conn, task_id, tz_raw)
        _warn_zone_overlap(conn, task_id, tz_raw, target)
    if tz_path is not None:
        print("  затем: " + cycle_hint.launch_text(
            conn, task_id, "run", "(запуск analyst)"))
    else:
        print(f"  затем: artel.py advance {task_id}  (SPEC status: ready)")
    return task_id


def _new_task_row(conn, task_id: str, title: str, target: str,
                  tz_doc: str | None, *, is_canary: bool = False,
                  journal_detail: str, model_set: str | None = None,
                  set_members: dict | None = None) -> None:
    """Общий скелет заведения строки задачи (R1-F4, REVIEW.md итерация 1):
    SPEC из шаблона, `TZ.md` (если есть), артефактная ветка пульта, строка
    в БД, запись в журнал — переиспользуется `cmd_new` (ТЗ Оператора) и
    `spawn_subtask` (подраздел секции «## Деление»), отличающимися только
    источником `tz_doc`, пометкой `is_canary`, набором моделей и текстом
    записи журнала."""
    branch = f"task/{task_id.lower()}-{slugify(title)}"
    spec = (config.TEMPLATES / "SPEC.md").read_text(encoding="utf-8")
    spec = spec.replace("TASK_ID", task_id).replace("<название задачи>", title)

    _new_external_artifact_branch(task_id, title, spec, tz_doc)

    members_json = (json.dumps(set_members, ensure_ascii=False)
                    if model_set is not None else None)
    store.insert_task(conn, task_id, title, "spec_writing", branch, target,
                      config.DEFAULT_BUDGET_USD, is_canary=is_canary,
                      model_set=model_set, model_set_members=members_json)
    store.journal(conn, task_id, "operator", "created", journal_detail)
    if model_set is not None:
        store.journal(conn, task_id, "operator", "набор моделей задачи",
                      f"{model_set}: {models.members_text(set_members)}")


def spawn_subtask(parent_id: str, parent_title: str, title: str,
                  tz_body: str, *, target: str | None = None) -> str:
    """Заводит одну подзадачу деления (01M1SHJZCE0Y4DXAAWQ2W585A7,
    требования 1-2) — та же механика, что `cmd_new` с ТЗ Оператора
    (общий скелет `_new_task_row`, R1-F4), только источник ТЗ — подраздел
    секции «## Деление» родителя, не файл с диска Оператора.

    `TZ.md` подзадачи — `tz_body` (поля `Зоны:`/`Порядок:`/`Рамка:`
    подраздела и текст ТЗ: поля остаются текстом внутри `TZ.md`, в
    frontmatter подзадачи они не переезжают) с добавленной ПЕРВОЙ строкой
    «Родительская задача: <id> — <название>».

    Тот же текст (`tz_raw` — ссылка на родителя плюс тело подраздела)
    идёт в предварительные зоны и в сверку пересечений, теми же общими
    функциями, которыми их делает `cmd_new` (SPEC
    01M3H1Z489CKJ8FHSRS4TYTPX2, требования 1-3):
    `_record_preliminary_zones` разбирает строку «Зоны:» подраздела в
    колонку `tasks.zones`, `_warn_zone_overlap` печатает и журналирует
    пересечение с задачами в полёте. Без них прогноз очереди зон был слеп
    к подзадачам деления до approve их SPEC — в том числе к пересечениям
    внутри одной волны деления. Отказом ни то, ни другое не становится:
    `sys.exit` посреди списка частей оставил бы деление сделанным
    наполовину.

    Порядок (требование 3, AC-3/AC-4): и запись зон, и предупреждение
    стоят ПОСЛЕ привязки к родителю — отдельными вызовами, а не слитыми с
    ней в один `store.update_task` (два независимых факта об одной
    строке; слияние молча теряло бы один при правке другого). Порядок
    между привязкой и зонами корректности не меняет — это две записи в
    разные колонки одной строки, — но предупреждение первым ЧИТАЕТ все
    задачи разом (`zone_lock.forecast_overlaps` -> `store.all_tasks`) и пишет
    запись в журнал подзадачи: к этому моменту её строка уже полна как
    строка ЧАСТИ деления. Оба вызова обязаны стоять до `return`: граница
    возврата — единственное, что отделяет заведение этой части от
    заведения следующей (`fsm._spawn_division_subtasks` заводит их
    списком), поэтому зоны первой части попадают в БД раньше, чем
    сверяется пересечение для второй.

    Родитель из сверки не исключается: в момент каждого вызова он ещё в
    `spec_gate` (в `killed` его переводит `_spawn_division_subtasks` ПОСЛЕ
    всех подзадач) — состояние из `zone_lock.LATER_STATES`, и пересечение
    части с зоной родителя видно без отдельного кода.

    Вызывается только из `orchestrator/fsm.py::_approve_spec_gate` при
    заведении деления — не публичный CLI-путь, поэтому не печатает
    подсказку калибровки/следующей команды `cmd_new` (эти подсказки
    ведут к `analyst`, к которому подзадача и так придёт своим ходом).
    """
    conn = store.db()
    target = target or config.DEFAULT_TARGET
    task_id = idgen.new_task_id()
    link_line = f"Родительская задача: {parent_id} — {parent_title}"
    # Один текст на `TZ.md` и на разбор зон: разойдись они, колонка зон
    # описывала бы не тот документ, который читает роль.
    tz_raw = f"{link_line}\n{tz_body}"
    tz_doc = _tz_document(task_id, title, tz_raw)

    _new_task_row(conn, task_id, title, target, tz_doc,
                 journal_detail=f"деление {parent_id}: {title}")
    store.update_task(conn, task_id, parent_task_id=parent_id)
    _record_preliminary_zones(conn, task_id, tz_raw)
    print(f"[{task_id}] «{title}» создана делением {parent_id} (target "
         f"{target}, артефактная ветка пульта "
         f"{artifact_branch.branch_name(task_id)})")
    _warn_zone_overlap(conn, task_id, tz_raw, target)
    return task_id


def _new_external_artifact_branch(task_id: str, title: str, spec: str,
                                  tz_doc: str | None) -> None:
    """Внешний target (требования 7-9, AC-8/AC-9): `tasks/<id>/` коммитится
    в артефактную ветку пульта плотницки (`artifact_branch.commit_files`),
    рабочая копия/worktree пульта не трогаются вовсе. Push в origin —
    best-effort (требование 7): отказ не прерывает заведение задачи и не
    превращает его в ошибку команды (AC-8), но журналируется
    классифицированной причиной (SPEC 01M1TQ0X14Y5B3C87WC0Q31PK2,
    требования 1-2, AC-1/AC-2)."""
    files = {f"tasks/{task_id}/SPEC.md": spec}
    if tz_doc is not None:
        files[f"tasks/{task_id}/TZ.md"] = tz_doc
    commit_sha = artifact_branch.commit_files(
        task_id, files, f"{task_id}: ТЗ Оператора ({title})")
    if not commit_sha:
        sys.exit(f"[{task_id}] артефактная ветка пульта не создана — git "
                 f"не ответил")
    artifact_branch.push(task_id)


def _lease_holder_suffix(conn, task_id: str) -> str:
    """Держатель lease задачи, если он есть — identity + жив/мёртв (SPEC
    01M1G..., требование 6, AC-11), ДОБАВКОЙ в конец строки `status`, не
    заменой существующих колонок.

    Живость проверяется, только если держатель на ЭТОМ host — тот же
    приём различения «свой/чужой host», которым уже пользуется
    `doctor.check_leases`/`check_merge_lock`: pid чужого host нельзя ни
    подтвердить мёртвым, ни опровергнуть, поэтому он молча считается
    «жив» (то же допущение, что уже принял `doctor.check_merge_lock`
    для мёртвого держателя на чужом host).

    Pid держателя мёртв на СВОЁМ host — вторая проверка (SPEC
    01M2B6JWGS9HMR9XZJBASXVNSY, требование 3, AC-7/AC-8): группа
    `row["pgid"]` (агент шага, `runner.spawn_agent`/`store.
    update_lease_pgid`) может пережить смерть самого держателя (ровно
    инцидент из «Контекст» SPEC — команда сессии завершилась, цикл
    `auto` под её же lease продолжает работать). Непустая группа —
    «жив (агент pgid N)», а не «мёртв»; `pgid` отсутствует (`NULL`,
    lease, ни разу не видевший `update_lease_pgid`) или группа уже
    пуста — «мёртв», как и раньше.
    """
    row = store.lease_row(conn, task_id)
    if row is None:
        return ""
    if row["hostname"] == socket.gethostname():
        if liveness._pid_alive(row["pid"]):
            status = "жив"
        else:
            pgid = row["pgid"]
            group_count = liveness._group_member_count(pgid) if pgid is not None else 0
            status = f"жив (агент pgid {pgid})" if group_count > 0 else "мёртв"
    else:
        status = "жив"
    return f"  [lease: {row['session_id']} {status}]"


def _zone_wait_suffix(conn, t) -> str:
    """Ожидание зоны, если ЭТА задача сейчас заблокирована первым шагом
    developer (SPEC 01M1P9QAG65GVF69YJEV0V18D9, требование 4) — ДОБАВКОЙ
    в конец строки `status`, тем же приёмом, что и `_lease_holder_suffix`.
    Вычисление занятости берётся у `zone_lock.blocking_conflict` целиком —
    та же проверка, что не пускает `run`/`auto` дальше, не отдельная копия.

    Позиция в очереди (`zone_lock.queue_position`, R1-F3, REVIEW.md
    итерация 1) — добавкой ПОСЛЕ держателя, только когда конкурентов по
    ЭТОЙ зоне больше одного; иначе строка не меняется (единственный
    заблокированный — очередь из одного не несёт новой информации).

    Минуты ожидания (SPEC 01M1VBEAWZW4EBZHKMGNBBK648, требование 4,
    AC-6) — добавкой ПОСЛЕ держателя/очереди, только пока задача реально
    в цикле `auto --wait-zone` (`zone_lock.wait_minutes` не `None`):
    `run`/`auto` без флага останавливаются немедленно и не оставляют
    записи входа — строка в этом случае не меняется, тем же приёмом, что
    и очередь из одного конкурента выше.
    """
    conflict = zone_lock.blocking_conflict(conn, t["id"], t)
    if conflict is None:
        return ""
    path, occupier_id, occupier_state = conflict
    position, total = zone_lock.queue_position(conn, t["id"], path)
    queue = f", очередь {position}/{total}" if total > 1 else ""
    minutes = zone_lock.wait_minutes(conn, t["id"])
    waited = f", ждёт {minutes} мин" if minutes is not None else ""
    return (f"  [ждёт зоны {path}: занята {occupier_id} ({occupier_state})"
            f"{queue}{waited}]")


def _zone_forecast_suffix(conn, t) -> str:
    """Добавка «зона занята: <id>» строке задачи ДО `in_dev` (SPEC
    01M3GKJ84XM5QPC6TK5EE307Q9, требование 3) — тем же приёмом добавки в
    конец строки, что `_lease_holder_suffix`/`_zone_wait_suffix`.

    Только три состояния `zone_lock.LATER_STATES`: задача в `in_dev` этой
    добавки не получает — её ожидание зоны уже печатает `_zone_wait_suffix`
    по `zone_lock.blocking_conflict` (держатель, очередь, минуты), и
    поведение того суффикса не меняется. Кандидаты — только
    `zone_lock.BLOCKING_STATES`: «занята» обещает занявшего зону, не
    будущего конкурента из того же набора `LATER_STATES`."""
    if t["state"] not in zone_lock.LATER_STATES:
        return ""
    if (t["target"] or config.DEFAULT_TARGET) != config.DEFAULT_TARGET:
        return ""
    matches = zone_lock.forecast_overlaps(
        conn, zone_lock.task_zone_paths(t), exclude_task_id=t["id"],
        states=zone_lock.BLOCKING_STATES)
    if not matches:
        return ""
    holders = sorted({task_id for _, task_id, _ in matches})
    return f"  [зона занята: {', '.join(holders)}]"


def _wave_breaker_suffix(t, wave_breaker_open: bool) -> str:
    """Пометка стоп-крана волны (01M1THKRK8HPXA7Y2SRB0RFTN2, требование
    4): ДОБАВКОЙ в конец строки, тем же приёмом, что и `_lease_holder_
    suffix`/`_zone_wait_suffix`. У КАЖДОЙ задачи target self, пока хоть
    один алерт открыт (требование 4: «блокирует весь target, не только
    задачи, вызвавшие срабатывание») — не только у задач, чей класс
    отказа поднял алерт. Задачи любого другого target не помечаются
    (требование 5)."""
    if not wave_breaker_open:
        return ""
    if (t["target"] or config.DEFAULT_TARGET) != config.DEFAULT_TARGET:
        return ""
    return "  [СТОП-КРАН ВОЛНЫ: run/auto не начинают новый шаг]"


def _division_suffix(rows, r) -> str:
    """Добавка «[поделена: <id1>, <id2>]»/«[часть N/M родителя <id>]»
    (01M29284PTCJXGERV5262E9XMM, требование 2) — ДОБАВКОЙ в конец строки,
    тем же приёмом, что и `_lease_holder_suffix`/`_zone_wait_suffix`.
    `rows` — уже прочитанный `store.all_tasks(conn)` (по возрастанию id),
    отдельного запроса на строку не делается: подзадачи — те же строки,
    отфильтрованные по `parent_task_id`."""
    subtask_ids = [x["id"] for x in rows if x["parent_task_id"] == r["id"]]
    if subtask_ids:
        return f"  [поделена: {', '.join(subtask_ids)}]"
    parent_id = r["parent_task_id"]
    if not parent_id:
        return ""
    sibling_ids = [x["id"] for x in rows if x["parent_task_id"] == parent_id]
    n = sibling_ids.index(r["id"]) + 1
    return f"  [часть {n}/{len(sibling_ids)} родителя {parent_id}]"


def _tokens_field(conn, task_id: str) -> str:
    """Суммарное число токенов задачи для строки `status` — либо прочерк,
    если записей токенов у задачи нет (SPEC 01M31ZHWJWRSACYMRWTCPBC0DM,
    требования 1 и 5).

    Поле выровнено по правому краю по ширине десятизначного числа:
    на журнале пульта самая дорогая задача несёт 263 335 360 токенов
    (девять знаков), и прежняя ширина 8 выталкивала число у каждой
    двенадцатой строки (REVIEW.md итерации 2, R2-F2). Ровной колонкой
    вывод от этого всё равно не становится — соседнее
    `${spent}/{budget}` само переменной ширины; выравнивание здесь
    держит типичные числа в одном столбце, а не обещает колонку на
    любом числе. Разбивка по видам сюда не идёт намеренно — на задачу
    приходится ровно одна строка (AC-1), а место для видов есть в RETRO
    и в `report`.

    Считается по журналу (`store.task_steps`) — тем же приёмом, каким
    журнал уже читают `report._all_steps` и `spend.known_cost_pairs`:
    специализированной выборки в `store.py` нет, а заводить её эта задача
    не вправе.

    Источник суммы — оба носителя журнала (`retro.task_token_total`):
    задача, чьи шаги записаны прежним видом записи, без разбивки по
    видам, показывает своё число, а не прочерк «записей нет»."""
    total = retro.task_token_total(store.task_steps(conn, task_id))
    return f"{retro.total_tokens_text(total):>10}"


def cmd_status() -> None:
    conn = store.db()
    rows = store.all_tasks(conn)
    if not rows:
        print("Задач нет. `new \"<название>\"` создаст первую.")
    # Стоп-кран волны, часть 2 (01M1THKRK8HPXA7Y2SRB0RFTN2, требование 4):
    # один запрос на весь вывод, не по строке на задачу — критерий «алерт
    # открыт» не меняется между строками одного вызова `status`.
    wave_breaker_open = bool(runner.wave_breaker_alerts_open(conn))
    for r in rows:
        flag = " <- ЖДЁТ ОПЕРАТОРА" if r["state"] in (
            "spec_gate", "acceptance", "merge_gate", "escalated") else ""
        # Пометка canary — ТОЛЬКО здесь и в RETRO (tasks/T065/SPEC.md,
        # требование 6), не в `title` самой задачи: строка `status` видна
        # Оператору, не роли внутри промпта шага.
        mark = "  [canary]" if r["is_canary"] else ""
        holder = _lease_holder_suffix(conn, r["id"])
        zone = _zone_wait_suffix(conn, r) + _zone_forecast_suffix(conn, r)
        merge_wait = merge_queue.wait_suffix(conn, r)
        wave_breaker = _wave_breaker_suffix(r, wave_breaker_open)
        division = _division_suffix(rows, r)
        tokens = _tokens_field(conn, r["id"])
        # Набор моделей задачи — сразу за бюджетом (SPEC
        # 01M3YCHS4F08VTV6XX10VF92H3, требование 8): от набора зависят и
        # модели шагов, и тариф, по которому тратится этот бюджет.
        model_set = models.task_set_name(r)
        set_field = f"  набор {model_set}" if model_set else ""
        print(
            f"{r['id']}  {r['state']:<13} "
            f"ревью {r['review_iters']}/{config.LIMIT_REVIEW_ITERS}"
            f"  ${r['spent_usd']:.2f}/{r['budget_usd']:.2f}{set_field}"
            f"  токенов {tokens}  {r['title']}"
            f"{flag}{mark}{holder}{zone}{wave_breaker}{division}{merge_wait}"
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
    # Префикс -> полный id ОДИН РАЗ здесь (SPEC T094, требование 3, AC-3),
    # до любого использования task_id ниже — иначе строки статуса читались
    # бы неразрешённым префиксом мимо сводной строки (REVIEW T094 итерация
    # 1, замечание 1: `_artifact_frontmatter` теряла SPEC.md/PLAN.md/...).
    task_id = store.resolve_task_id(conn, task_id)
    t = store.get_task(conn, task_id)
    print(f"{t['id']} «{t['title']}»  состояние: {t['state']}  "
          f"ветка: {t['branch']}  проект: {t['target']}")
    print(f"  ревью-итераций: {t['review_iters']}/{config.LIMIT_REVIEW_ITERS}"
          f"  отказов приёмки: {t['accept_rejects']}"
          f"/{config.LIMIT_ACCEPT_REJECTS}"
          f"  бюджет: ${t['spent_usd']:.2f}/{t['budget_usd']:.2f}")
    model_set = models.task_set_name(t)
    if model_set:
        print(f"  набор задачи: {model_set} "
              f"({t['model_set_members'] or '—'})")
    for name in ("SPEC.md", "PLAN.md", "REVIEW.md", "TEST_REPORT.md"):
        meta = _artifact_frontmatter(t["target"], task_id, name)
        if meta:
            print(f"  {name}: status={meta.get('status', '?')}")


def _artifact_frontmatter(target: str, task_id: str, name: str) -> dict:
    """Frontmatter артефакта задачи для `cmd_show` — с диска для self
    (прежнее поведение), из артефактной ветки пульта для любого другого
    target (SPEC T094, требование 10, AC-11 — реестр AC-1: `tasks/<id>/`
    внешнего target на диске `config.TASKS` не существует вовсе)."""
    if target == config.DEFAULT_TARGET:
        return artifacts.frontmatter(config.TASKS / task_id / name)
    from . import yamlmini
    text, _ = gitcmd.show(artifact_branch.branch_name(task_id),
                          f"tasks/{task_id}/{name}")
    return (yamlmini.frontmatter(text) or {}) if text is not None else {}


def cmd_log(task_id: str) -> None:
    conn = store.db()
    # Префикс -> полный id (SPEC T094, требование 3, AC-3) — без этого
    # `task_steps` требует точного совпадения `id` и молча печатает 0
    # строк для валидного уникального префикса (REVIEW T094 итерация 1,
    # замечание 1).
    task_id = store.resolve_task_id(conn, task_id)
    for r in store.task_steps(conn, task_id):
        line = f"{r['ts']}  {r['actor']:<12} {r['action']}"
        if r["detail"]:
            line += f"  | {r['detail']}"
        # session_id — ДОБАВКОЙ в конец, одной строкой (SPEC 01M1G...,
        # AC-3): NULL у записей старше миграции (`store.migrate`) — молча
        # не показывается, не «None» текстом.
        if r["session_id"]:
            line += f"  [{r['session_id']}]"
        print(line)
