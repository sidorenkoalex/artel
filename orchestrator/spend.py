"""Стоимость шага: разбор чисел, событие потока, учёт в spent_usd.

Формат вывода исполнителя знает провайдер роли шага
(`orchestrator/providers/`, SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ): здесь —
только деньги, то есть что делать с уже разобранным событием общего
вида и как записать результат в журнал.
"""
import math
import re
from pathlib import Path

from . import alerts, config, models, providers, store


def json_number(value) -> float | None:
    """Число из JSON или None. bool — не число: `True` не стоит доллар."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def cli_number(raw: str) -> float | None:
    """Число из аргумента CLI; запятая как разделитель тоже считается."""
    try:
        value = float(raw.replace(",", ".").strip())
    except (AttributeError, ValueError):
        return None
    # float() принимает 'nan' и 'inf' — потолком ни то, ни другое не работает.
    return value if math.isfinite(value) else None


def run_result_cost(run_result) -> dict | None:
    """Итог запуска (`providers.RunResult`) -> стоимость шага словарём;
    `None` — итога запуска не было вовсе.

    Словарь тот же, каким его читает весь учёт: `usd` (цена от CLI либо
    `None`, если CLI её не сообщил — SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ,
    требование 4), `tokens` (сумма) и `tokens_by_type` (разбивка по
    общим видам `models.PRICE_KINDS`).
    """
    if run_result is None:
        return None
    by_kind = run_result.tokens_by_type
    tokens = sum(by_kind.values()) if by_kind is not None else None
    return {"usd": run_result.usd, "tokens": tokens,
            "tokens_by_type": by_kind}


def parse_run_result(raw_line: str, provider=None) -> dict | None:
    """Стоимость запуска из итога запуска в строке потока; `None` — эта
    строка итогом запуска не была.

    Отличается от `parse_cost_event` ровно тем, что отдаёт словарь и
    БЕЗ цены (`usd is None`): «итог запуска получен, но CLI цены не
    сообщил» — отдельный путь учёта (SPEC требование 4), и слить его с
    «итога запуска нет вовсе» значило бы списывать по обрывкам usage
    шаг, чей вывод вообще не дошёл.
    """
    event = providers.or_default(provider).parse_output_line(raw_line)
    return run_result_cost(event.run_result)


def parse_cost_event(raw_line: str, provider=None) -> dict | None:
    """Стоимость запуска из финального события потока, иначе None.

    Поток заканчивается итогом запуска с ценой и usage. В файл лога он
    не попадает (лог несёт рендер), поэтому стоимость снимается прямо с
    потока перекачкой.

    Всё, что не разобралось — чужой формат, поле не число, отрицательная
    цена, — это None: по SPEC неизвлечённая стоимость не проваливает шаг.
    Контракт сохранён дословно (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ,
    требование 3, AC-7): у функции есть читатель вне зоны задачи
    (`orchestrator/doctor/live_smoke.py`), который форматирует
    `cost['usd']` сразу после проверки на `None`. Путь учёта шага, где
    цены может не быть, читает `parse_run_result` выше.
    """
    cost = parse_run_result(raw_line, provider)
    return cost if cost is not None and cost["usd"] is not None else None


def stream_usage_by_type(raw_line: str, provider=None) -> dict | None:
    """Разбивка usage ЛЮБОГО события потока, не только финального итога.

    `parse_cost_event` намеренно смотрит только итог запуска — это
    единственное событие, где CLI считает доллары. Здесь другая задача
    (tasks/T040, уточнённая 01M1PP0VYRT55WN8GGVG66X89Y требованием 2):
    собрать хоть что-то по ВИДАМ токена, если финальное событие вообще не
    придёт (таймаут, обрыв stdout-пайпа) — раньше (`stream_usage_tokens`)
    счётчики сразу суммировались в одно число, и эта сумма тарифицировалась
    средней ставкой входа/выхода, что и завышало частичную стоимость шага,
    состоящего в основном из дешёвых чтений кэша (SPEC «Контекст»).
    """
    return providers.or_default(provider).parse_output_line(
        raw_line).tokens_by_type


def partial_tokens_from_log(path: Path, provider=None) -> tuple[dict, bool]:
    """(разбивка по видам, видели_ли_usage) из УЖЕ ЗАПИСАННОГО на диск лога
    шага.

    Тот же разбор, что `OutputPump.catch_event` делает по ходу потока
    (T040): каждая строка — событием провайдера, найденные счётчики
    складываются по видам (не одной суммой — SPEC
    01M1PP0VYRT55WN8GGVG66X89Y, требование 2). Здесь — постфактум по
    файлу, а не по живому потоку (SPEC T074, требование 4): `pause --now`
    живёт в ДРУГОМ процессе, чем прерванный шаг, — памяти его
    `OutputPump` уже нет, есть только то, что успело лечь в лог-файл на
    диск.

    Лог не прочитан (отсутствует прогон, ФС не ответила) — `({}, False)`,
    та же деградация без данных, что у отсутствия usage-событий в потоке.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}, False
    provider = providers.or_default(provider)
    totals: dict = {}
    saw = False
    for line in text.splitlines():
        found = provider.parse_output_line(line).tokens_by_type
        if found is not None:
            saw = True
            for kind, count in found.items():
                totals[kind] = totals.get(kind, 0) + count
    return totals, saw


def cost_note(cost: dict | None) -> str:
    """Стоимость шага для журнала и консоли; пустая строка — не извлеклась."""
    if cost is None:
        return ""
    note = f"стоимость ${cost['usd']:.4f}"
    return f"{note}, токенов {cost['tokens']}" if cost["tokens"] is not None else note


#: Вызывающий модель шага не назвал — восстановить её из `numbered`
#: (`model=`). Прежний путь прямых вызовов `charge_step`, которых в
#: пульте и тестах много (SPEC T040, требование 4): их поведение эта
#: задача не меняет. Отдельный часовой, а не `None`: «модель шага не
#: разрешилась» — законное значение параметра, и путать его с «параметр
#: не передан» нельзя.
_MODEL_FROM_NUMBERED = object()


def charge_step(conn, task_id: str, role: str, cost: dict | None,
                numbered: str, model_id=_MODEL_FROM_NUMBERED) -> str:
    """Прибавляет стоимость попытки к `spent_usd`; возвращает её для журнала.

    Три пути (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требования 4-5):

    - итога запуска нет вовсе (`cost is None`) — шаг не проваливаем (так
      решил SPEC T007): warning в журнал, `spent_usd` не трогаем. Цена
      сбоя формата события — потерянная метрика, а не остановленный
      конвейер;
    - итог есть, цена от CLI есть и провайдер модели шага помечен в
      каталоге `cost_from_cli: true` — прежний путь факта CLI со сверкой
      курса;
    - итог есть, а цены нет ЛИБО провайдер модели шага помечен
      `cost_from_cli: false` — расчёт по действующему тарифу модели шага
      (`_charge_by_tariff`).

    `model_id` — модель ШАГА от вызывающего (`runner._account_step`
    держит её на руках). Ветка учёта денег обязана выбираться по самой
    модели, а не по тому, попало ли `model=` в текст строки: `runner`
    приписывает поле только к строкам KNOWN/PARTIAL (требование 6 SPEC
    01M2DTT96FS25SHXP0HDTWARQH), и итог запуска без разбивки токенов
    остался бы без поля — а с ним и без признака `cost_from_cli`.
    Восстановление модели разбором собственной строки остаётся
    читателям журнала (`known_cost_pairs`), где другого источника нет.
    """
    if cost is None:
        store.journal(conn, task_id, role, "agent cost UNKNOWN",
                      f"{numbered}: в выводе нет события со стоимостью — "
                      f"spent_usd не изменён")
        return ""
    if model_id is _MODEL_FROM_NUMBERED:
        model_id = journal_model(numbered)
    if cost["usd"] is None or not _cost_from_cli(model_id):
        return _charge_by_tariff(conn, task_id, role, cost, numbered, model_id)
    store.charge(conn, task_id, cost["usd"])
    tokens_by_type = cost.get("tokens_by_type")
    if tokens_by_type:
        # Источник данных калибровки (SPEC 01M1PP0VYRT55WN8GGVG66X89Y,
        # требования 4/6, AC-6/AC-8): завершённый шаг с известной
        # фактической ценой (`cost["usd"]`, из `total_cost_usd` потока) и
        # разбивкой usage — `report.token_rate_divergence` читает эту
        # запись, чтобы сравнить расчётную цену с фактической. Отдельное
        # действие журнала, не замена существующего `cost_note` в «agent
        # run finished» — требование 6 (дополняет, не заменяет).
        #
        # Сверка тарифа с фактом считается ДО записи строки и попадает в
        # неё же (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 3, AC-4):
        # свежий шаг обязан входить в собственный коэффициент, а править
        # уже вставленную строку журнала нечем — `store` эта задача
        # держит на чтении.
        #
        effective = model_tariff(model_id)
        record_tariff(conn, effective)
        divergence_note = _divergence_note(conn, role, effective, cost["usd"],
                                           tokens_by_type)
        detail = (f"{numbered}: {cost_note(cost)}, {SOURCE_CLI_FACT}, "
                 f"разбивка по видам: "
                 f"{_tokens_by_type_text(tokens_by_type)} | "
                 f"actual_usd={cost['usd']!r}"
                 f"{_tariff_note(effective)}{divergence_note}")
        store.journal(conn, task_id, role, KNOWN_COST_JOURNAL_ACTION, detail)
    return f", {cost_note(cost)}"


#: Действие журнала: стоимость шага НЕ учтена на пути расчёта по тарифу
#: (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требование 6, AC-11). Отдельное имя
#: от «agent cost UNKNOWN» (итога запуска не было) и от «agent cost
#: ESTIMATED» (оборванный шаг без тарифа): здесь шаг ДОШЁЛ до конца, и
#: непосчитанной его цена осталась из-за конфигурации пульта, а не из-за
#: обрыва — чинится это разными действиями Оператора.
UNCHARGED_COST_JOURNAL_ACTION = "agent cost UNCHARGED"

#: Источник суммы в строке стоимости: факт CLI против расчёта по тарифу
#: (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH требование 2, SPEC
#: 01M31ZHSA6HMH40C2JTDPQJQNZ требование 4). Читатель журнала обязан
#: отличать одно от другого — недоучёт шага PARTIAL (SPEC «Контекст»)
#: начинался с того, что обе суммы выглядели одинаково.
SOURCE_CLI_FACT = "источник=факт CLI"
SOURCE_TARIFF = "источник=расчёт по тарифу"


def _cost_from_cli(model_id: str | None) -> bool:
    """Сообщает ли CLI провайдера ЭТОЙ модели цену запуска — признак
    `cost_from_cli` раздела провайдера в каталоге моделей (SPEC
    01M31ZHSA6HMH40C2JTDPQJQNZ, требование 4).

    Неизвестная модель, строка без поля `model=`, нечитаемый каталог —
    «истина», то есть сегодняшний путь факта CLI: учёт шага важнее
    признака и не имеет права ни упасть вместе с конфигурацией, ни
    молча увести шаг с ценой от CLI на расчёт по тарифу (та же
    деградация, что у `role_tariff`/`model_tariff`). Отсутствие цены в
    самом итоге запуска ветку расчёта включает и без этого признака.
    """
    if not model_id:
        return True
    try:
        return models.catalog_model(model_id).cost_from_cli
    except models.ModelsError:
        return True


def _tariff_path_cause(cost: dict) -> str:
    """Почему шаг считается по тарифу — первое, что читает Оператор в
    строке UNCHARGED и в тексте алерта.

    Две причины требования 4 (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ) названы
    порознь: цены в итоге запуска не было вовсе против «цена есть, но
    каталог объявил её недостоверной». Общий текст «цены от CLI нет» на
    второй причине отправил бы искать пропавшее поле потока вместо
    записи каталога.
    """
    if cost["usd"] is None:
        return "цены от CLI нет"
    return "цена от CLI не в счёт: каталог несёт cost_from_cli: false"


def _uncharged_reason(role: str, model_id: str | None,
                      tokens_by_type: dict | None) -> str:
    """Почему по тарифу посчитать НЕ удалось — вторая половина текста
    записи UNCHARGED и алерта (требование 6, AC-11).

    Источник тарифа назван тем же, каким его искал `_charge_by_tariff`:
    модель шага, если она известна, иначе цепочка РОЛИ (`role_tariff`) —
    дословно та же формулировка, что у соседней ветки недоучёта
    (`charge_missing_result`). Подставить роль на место модели значило бы
    отправить Оператора искать в каталоге модель с именем роли ровно в
    тот момент, когда деньги шага не учтены.
    """
    if not tokens_by_type:
        return "разбивки токенов нет в итоге запуска"
    if model_id:
        return f"тариф модели {model_id!r} не разрешён"
    return f"тариф модели роли {role!r} не разрешён"


def _charge_by_tariff(conn, task_id: str, role: str, cost: dict,
                      numbered: str, model_id: str | None) -> str:
    """Учёт завершённого шага по действующему тарифу модели: цены от CLI
    нет либо каталог объявил её недостоверной (`cost_from_cli: false`) —
    SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требования 4, 6.

    Сверки курса здесь нет намеренно: сверять расчёт не с чем — факта
    CLI у этого шага не существует, и коэффициент «расхождения расчёта с
    самим собой» был бы нулём, который выглядел бы как подтверждённая
    цена. По той же причине строка НЕ несёт `actual_usd=`: иначе расчёт
    вошёл бы в калибровку тарифа под видом факта (`known_cost_pairs`), и
    тариф начал бы подтверждать сам себя.

    Тариф не разрешился или разбивки токенов у итога нет — списывать
    нечего, но и молчать нельзя: именованная запись журнала плюс алерт
    (требование 6, AC-11). Ноль в `spent_usd` выглядел бы как учтённый
    шаг, и недоучёт копился бы до конца программы без единого сигнала.
    """
    tokens_by_type = cost.get("tokens_by_type")
    effective = model_tariff(model_id) if model_id else role_tariff(role)
    if effective is None or not tokens_by_type:
        cause = _tariff_path_cause(cost)
        reason = _uncharged_reason(role, model_id, tokens_by_type)
        detail = (f"{numbered}: {cause}, {reason} — стоимость шага "
                  f"не учтена, spent_usd не изменён")
        store.journal(conn, task_id, role, UNCHARGED_COST_JOURNAL_ACTION,
                      detail)
        alerts.raise_alert(
            conn, store.task_target(conn, task_id), "threshold",
            "spend.step_cost_uncharged",
            f"{task_id}/{role}: {numbered} — {cause}, {reason}; "
            f"стоимость шага не учтена")
        return ""

    record_tariff(conn, effective)
    usd = tariff_cost_usd(effective.tariff, tokens_by_type)
    store.charge(conn, task_id, usd)
    total_tokens = sum(tokens_by_type.values())
    detail = (f"{numbered}: стоимость ${usd:.4f}, токенов {total_tokens}, "
              f"{SOURCE_TARIFF}, разбивка по видам: "
              f"{_tokens_by_type_text(tokens_by_type)}"
              f"{_tariff_note(effective)}")
    store.journal(conn, task_id, role, KNOWN_COST_JOURNAL_ACTION, detail)
    return f", стоимость ${usd:.4f}, токенов {total_tokens}"


def _tariff_note(effective) -> str:
    """Хвост строки KNOWN/PARTIAL: дата действующего тарифа модели шага
    (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 7, AC-9). Пустая строка
    — тариф не разрешился.

    Дата стоит в строке САМА, а не только внутри коэффициента сверки:
    коэффициента может не быть вовсе (первый шаг модели, сверять не с
    чем), а вопрос «по какой цене посчитан этот шаг» читатель журнала
    задаёт всегда — RETRO и отчёт считают по тарифу, действовавшему на
    момент шага.
    """
    if effective is None:
        return ""
    return f" | тариф модели с {effective.calibrated_at}"


def _divergence_note(conn, role: str, effective, actual_usd: float,
                     tokens_by_type: dict) -> str:
    """Хвост строки KNOWN: расчёт по тарифу модели и коэффициент его
    расхождения с фактом CLI (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH,
    требования 3-4). Пустая строка — сверять нечем.

    В сверку идут прежние строки KNOWN этой ПАРЫ (роль, модель) с даты
    действующего тарифа модели (`known_cost_pairs`) ПЛЮС пара текущего
    шага: коэффициент в строке отвечает на вопрос «как тариф расходится
    с фактом на этот момент», включая сам записываемый шаг.

    Тариф не разрешился — тихий пропуск: учёт шага важнее сверки и не
    имеет права упасть вместе с ней (тот же урок, что R1-F1 у
    `charge_missing_result` ниже; SPEC 01M300A14KRHCFB0DQXVCBJEKF,
    требование 9).
    """
    if effective is None:
        return ""
    calculated = tariff_cost_usd(effective.tariff, tokens_by_type)
    pairs = known_cost_pairs(conn, role, effective.model).get(
        (role, effective.model), [])
    pairs.append((calculated, actual_usd))
    divergence = check_rate_divergence(conn, effective.model, pairs)
    if divergence is None:
        return ""
    return (f" | расчёт по тарифу=${calculated:.4f}, "
            f"коэффициент пары с {divergence.since}={divergence:.2f}")


#: Цены тарифа заданы за МИЛЛИОН токенов (`models.PRICE_KINDS`,
#: `list_price_usd_per_mtok`), а разбивка usage — в штуках.
TOKENS_PER_PRICE_UNIT = 1_000_000


def by_price_kind(tokens_by_type: dict) -> dict:
    """Разбивка токенов, приведённая к ОБЩИМ видам цены
    (`models.PRICE_KINDS`) — принимает обе формы имён (SPEC
    01M31ZHSA6HMH40C2JTDPQJQNZ, требования 1 и 7).

    Общие имена с 21.09 отдаёт событие провайдера, прежние имена
    (счётчики Claude, `config.LEGACY_TOKEN_KIND_NAMES`) несут строки
    журнала, записанные до задачи, и прямые вызовы учёта из кода,
    который эту задачу не видел. Разбор обязан считать по обеим —
    иначе половина журнала и вся калибровка тарифа на нём читались бы
    пустыми, молча.

    Чужие ключи отбрасываются, одинаковые виды складываются: строка,
    где один и тот же вид назван обеими формами, — это всё равно один
    вид.
    """
    out: dict = {}
    for key, count in (tokens_by_type or {}).items():
        kind = config.LEGACY_TOKEN_KIND_NAMES.get(key, key)
        if kind in models.PRICE_KINDS:
            out[kind] = out.get(kind, 0) + count
    return out

#: `model=` строки журнала «agent cost KNOWN/PARTIAL» (пишет
#: `runner._numbered_with_model`). Значение — либо идентификатор модели,
#: либо метка «дефолт CLI» с пробелом: до конца поля читается один токен
#: без пробелов и запятых, а идентификатор ли это — решает каталог.
#:
#: Хвостовое двоеточие поля НЕ входит в значение: `model=` стоит последним
#: в `numbered`, а `charge_step` приписывает к нему `": "` — без этого
#: отсечения моделью считалось бы `claude-opus-5:`, которой в каталоге
#: нет. Двоеточие отсекается только перед пробелом/запятой/концом строки:
#: идентификатор модели у другого провайдера сам может нести двоеточия
#: (arn Bedrock), и рубить по первому из них нельзя.
_MODEL_FIELD_RE = re.compile(r"model=([^\s,]+?):?(?=[\s,]|$)")


def journal_model(detail: str) -> str | None:
    """Идентификатор модели из поля `model=` строки журнала; `None` —
    поля нет (строка старого формата до 19.09) либо его значение — не
    один токен (метка «дефолт CLI»).

    Сверку значения с каталогом функция НЕ делает: «это вообще похоже на
    поле» и «такая модель у пульта есть» — разные вопросы, и второй
    отвечает `model_tariff` ниже, отдавая `None` на неизвестной модели.
    """
    match = _MODEL_FIELD_RE.search(detail or "")
    return match.group(1) if match else None


def role_tariff(role: str) -> models.EffectiveTariff | None:
    """Действующий тариф модели РОЛИ (цепочка «роль -> ярус -> модель»);
    `None` — цепочка не разрешилась.

    Деградация вместо исключения — требование 9 SPEC
    01M300A14KRHCFB0DQXVCBJEKF: учёт шага важнее цены и не имеет права
    упасть вместе с ней. Роль без яруса (`verifier`, `executor: none`),
    нечитаемый локальный слой, модель вне каталога — всё это здесь
    «тарифа нет», ровно как раньше «курса роли нет»; называет причину
    поимённо `doctor` (строки `models-catalog`/`models-local`), а не
    стоимость шага.
    """
    try:
        resolved = models.resolve_role(role)
    except models.ModelsError:
        return None
    return models.EffectiveTariff(resolved.model, resolved.tariff,
                                  resolved.tariff_source,
                                  resolved.calibrated_at, resolved.source)


def model_tariff(model_id: str, catalog=None, local=None):
    """Действующий тариф МОДЕЛИ по идентификатору; `None` — модели нет в
    каталоге или слои не читаются (та же деградация, что `role_tariff`).

    `catalog`/`local` передаются вызывающим, который разрешает тариф в
    цикле по строкам журнала (`known_cost_pairs`): без них каждая строка
    перечитывала бы оба файла слоёв.
    """
    if not model_id:
        return None
    try:
        return models.resolve_model(model_id, catalog, local)
    except models.ModelsError:
        return None


def tariff_cost_usd(tariff, tokens_by_type: dict) -> float:
    """Стоимость разбивки usage по четырём ценам тарифа: каждый вид
    токенов — своей ценой (SPEC 01M1PP0VYRT55WN8GGVG66X89Y, требование 2),
    не средней ставкой на общую сумму токенов: чтения кэша почти всегда —
    большинство объёма шага и стоят на порядок дешевле входа, усреднение
    завышало частичную стоимость таймаута в ~20 раз (инцидент 04.09).

    Разбивка принимается в обеих формах имён видов (`by_price_kind`):
    у функции есть вызыватели, передающие прежние имена, — и строка
    журнала до задачи, и прямой вызов из кода вне зоны."""
    by_kind = by_price_kind(tokens_by_type)
    return sum(by_kind.get(kind, 0) * getattr(tariff, kind)
               / TOKENS_PER_PRICE_UNIT
               for kind in models.PRICE_KINDS)


def record_tariff(conn, effective) -> bool:
    """История тарифов: строка в `model_tariffs`, если действующий тариф
    модели отличается от последней её записи (SPEC
    01M300A14KRHCFB0DQXVCBJEKF, требование 6). `True` — строка добавлена.

    Зовётся в точке учёта шага — единственной, где есть и соединение с
    БД, и уже разрешённый тариф. Команды записи в таблицу нет: руками
    история не правится, её пишет только пульт, разрешая тариф.
    """
    if effective is None:
        return False
    return store.record_model_tariff(conn, effective.model,
                                     tuple(effective.tariff),
                                     effective.calibrated_at,
                                     effective.source)


def _tokens_by_type_text(tokens_by_type: dict) -> str:
    """Разбивка по видам как строка журнала — общий формат для «agent
    cost KNOWN» (`charge_step`) и «agent cost PARTIAL»
    (`charge_missing_result`), читаемый обратно `known_cost_breakdown`.

    Пишутся ОБЩИЕ имена видов (`models.PRICE_KINDS`, SPEC
    01M31ZHSA6HMH40C2JTDPQJQNZ, требование 1): вид токенов у каталога и
    у тарифа называется так, и строка журнала обязана называть его тем
    же словом, чтобы второй провайдер не выдумывал себе счётчики Claude
    ради тарификации. Прежние имена в строках, записанных до задачи,
    читаются по-прежнему — требование 7."""
    by_kind = by_price_kind(tokens_by_type)
    return ", ".join(f"{kind}={by_kind.get(kind, 0)}"
                     for kind in models.PRICE_KINDS)


def partial_cost_usd(role: str, tokens_by_type: dict) -> float | None:
    """Стоимость разбивки usage по действующему тарифу МОДЕЛИ роли, или
    `None` — тариф не разрешился (SPEC 01M300A14KRHCFB0DQXVCBJEKF,
    требования 1-2, AC-2).

    Принимает роль, а не модель: вызывающие (`charge_missing_result`,
    `runner._cost_partial_expected`) знают роль ШАГА, а модель у неё —
    результат разрешения цепочки, а не их знание. Две роли одного яруса
    считают одну и ту же разбивку одинаково, смена модели яруса меняет
    сумму — ровно то, чего не умел курс по роли.

    Неполный прейскурант больше не даёт здесь `ValueError`: набор из
    четырёх цен обязателен на разборе каталога и локального слоя
    (`models._prices`, `IncompletePriceError`) — отказ стал строже и
    переехал раньше по течению, к чтению файла, а сюда неполный тариф
    попасть уже не может.
    """
    effective = role_tariff(role)
    if effective is None:
        return None
    return tariff_cost_usd(effective.tariff, tokens_by_type)


# --- сверка тарифа модели с фактом CLI (01M2ZNJX2N5SPZCAQE6EHD4EWH, 3-7;
#     пара «роль, модель» — 01M300A14KRHCFB0DQXVCBJEKF, требование 2)
#
# Формат строки «agent cost KNOWN» пишет `charge_step` выше — разбор
# ниже его обратная операция. Оба живут в одном модуле с того момента,
# как точек чтения стало две (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH,
# требование 6): сверка при записи шага (`_divergence_note`) и отчёт
# (`report.token_rate_divergence`, зовёт эти же функции). До этого
# разбор стоял в `report.py` рядом с единственным читателем.
KNOWN_COST_JOURNAL_ACTION = "agent cost KNOWN"

_ACTUAL_USD_RE = re.compile(r"actual_usd=([0-9eE.+-]+)")

# Поле разбивки в строке журнала — по ОБЕИМ формам имён видов (SPEC
# 01M31ZHSA6HMH40C2JTDPQJQNZ, требование 7, AC-12): строки, записанные
# до задачи, несут прежние имена (счётчики Claude), записанные после —
# общие имена видов цены. Журнал живого пульта после мержа смешанный, и
# пропустить одну из форм значило бы считать калибровку тарифа по
# половине шагов, не сказав об этом.
#
# Хвост `(?<![a-z_])` отсекает совпадение внутри более длинного имени:
# без него `input=` нашёлся бы в `cache_...input_tokens=…`. Обратное
# перекрытие невозможно по построению — `input=` и `input_tokens=`
# различаются символом сразу после имени.
_TOKEN_FIELD_RE = tuple(
    (kind, re.compile(rf"(?<![a-z_]){re.escape(name)}=(\d+)"))
    for name, kind in
    list(config.LEGACY_TOKEN_KIND_NAMES.items())
    + [(kind, kind) for kind in models.PRICE_KINDS])


def known_cost_breakdown(detail: str) -> tuple:
    """(фактическая_цена, разбивка_по_видам) из детали «agent cost
    KNOWN», либо `(None, None)` — запись не несёт того, что нужно
    (старый формат, повреждённая строка).

    Разбивка отдаётся ОБЩИМИ видами независимо от того, какой формой
    имён записана сама строка: читателям (сверка курса, отчёт) нужны
    числа, а не форма записи, и одинаковые числа обязаны давать
    одинаковую разбивку (требование 7, AC-12).
    """
    usd_match = _ACTUAL_USD_RE.search(detail or "")
    if usd_match is None:
        return None, None
    try:
        actual_usd = float(usd_match.group(1))
    except ValueError:
        return None, None
    tokens_by_type = {}
    for kind, pattern in _TOKEN_FIELD_RE:
        m = pattern.search(detail)
        if m is not None:
            tokens_by_type[kind] = int(m.group(1))
    return actual_usd, tokens_by_type


def rate_calibrated_at(role: str) -> str | None:
    """Дата действующего тарифа модели роли, с которой идёт сверка:
    `calibrated_at` переопределения локального слоя, иначе `price_date`
    каталога (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 1, AC-3);
    `None` — тариф не разрешился."""
    effective = role_tariff(role)
    return effective.calibrated_at if effective is not None else None


def _within_tariff_period(since: str | None, ts) -> bool:
    """Записан ли шаг не раньше даты действующего тарифа его модели.

    `store.now()` пишет `YYYY-MM-DD HH:MM:SSZ`, дата тарифа —
    `YYYY-MM-DD`: сравнение префикса лексикографически и есть сравнение
    дат, разбирать их нечем. Строки старше даты — шаги, посчитанные по
    ДРУГОЙ цене той же модели (SPEC 01M300A14KRHCFB0DQXVCBJEKF,
    требование 2), в коэффициент пары не входят. Тариф без даты либо
    строка без `ts` — тоже мимо: отнести такой шаг к периоду тарифа
    нечем, а молча смешать две цены — ровно тот дефект, который линия и
    закрывает.
    """
    if not since or not ts:
        return False
    return str(ts)[:len(since)] >= since


def known_cost_pairs(conn, role: str | None = None,
                     model_id: str | None = None) -> dict:
    """{(роль, модель): [(расчёт по тарифу, факт CLI), …]} по строкам
    журнала `KNOWN_COST_JOURNAL_ACTION`; `role`/`model_id` — сузить
    чтение до одной пары (путь записи шага).

    Ключ — ПАРА (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 2, AC-4):
    модель берётся из поля `model=` самой строки, а не из сегодняшней
    цепочки роли — шаг, прошедший на прежней модели, обязан считаться по
    её цене, а не по цене нынешней. Строка входит в пару, только если
    записана не раньше даты действующего тарифа ЭТОЙ модели.

    Журнал читается существующими функциями `store` (`all_tasks` +
    `task_steps`), тем же приёмом, что `report._all_steps`: функции «весь
    журнал одним запросом» в `store` нет. Слои моделей читаются ОДИН раз
    на вызов (`models.layers_or_none`), а тариф каждой встреченной модели
    — один раз и кладётся в `tariffs`: иначе длинный журнал упёрся бы в
    файловый ввод-вывод на каждой строке.

    Строка, которую нечем сверить, пропускается молча: старый формат без
    `actual_usd`, строка без опознаваемой модели (требование 3, AC-5),
    модель вне каталога, нечитаемые слои. Сверка не обязана падать из-за
    неполноты конфигурации — назвать её поимённо дело `doctor`.
    """
    catalog, local = models.layers_or_none()
    tariffs: dict = {}
    pairs: dict = {}
    for task in store.all_tasks(conn):
        for row in store.task_steps(conn, task["id"]):
            if row["action"] != KNOWN_COST_JOURNAL_ACTION:
                continue
            actor = row["actor"]
            if role is not None and actor != role:
                continue
            step_model = journal_model(row["detail"])
            if step_model is None or (model_id is not None
                                      and step_model != model_id):
                continue
            if step_model not in tariffs:
                tariffs[step_model] = model_tariff(step_model, catalog, local)
            effective = tariffs[step_model]
            if effective is None:
                continue
            if not _within_tariff_period(effective.calibrated_at, row["ts"]):
                continue
            actual_usd, tokens_by_type = known_cost_breakdown(row["detail"])
            if actual_usd is None or not tokens_by_type:
                continue
            pairs.setdefault((actor, step_model), []).append(
                (tariff_cost_usd(effective.tariff, tokens_by_type), actual_usd))
    return pairs


class RateDivergence(float):
    """Коэффициент расхождения тарифа модели с фактом CLI — число,
    которое помнит, по какой выборке оно посчитано: `steps` (сколько
    шагов в неё вошло) и `since` (дата тарифа, с которой идёт сверка).

    Именно число, а не словарь или кортеж: возврат
    `report.token_rate_divergence` — `{модель: коэффициент}` — читается
    как число (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 4, AC-6).
    Дату и число шагов обязаны назвать строка журнала (SPEC
    01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 3) и строка отчёта
    (требование 7), поэтому они едут рядом с коэффициентом — считать их
    второй раз у каждого читателя значило бы развести две математики.
    """

    __slots__ = ("steps", "since")

    def __new__(cls, coefficient: float, steps: int, since: str):
        value = super().__new__(cls, coefficient)
        value.steps = steps
        value.since = since
        return value


def check_rate_divergence(conn, model_id: str,
                          pairs: list) -> RateDivergence | None:
    """Коэффициент расхождения тарифа МОДЕЛИ с фактом CLI по парам
    «расчёт, факт» — и алерт, если он выше порога. `None` — сверять
    нечего либо тариф модели не разрешился.

    ЕДИНСТВЕННОЕ место, где живёт математика «сумма расчёта против суммы
    фактов» (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 6, AC-8): её
    зовут обе точки — запись шага (`_divergence_note`) и отчёт
    (`report.token_rate_divergence`). Суммарное расхождение по шагам, не
    среднее по шагам: несколько маленьких шагов не должны топить один
    крупный расходящийся.

    Адресат алерта — модель, а не роль (SPEC
    01M300A14KRHCFB0DQXVCBJEKF, требование 1): разошлась ЦЕНА, а она у
    модели одна на все роли яруса, и три роли на одной модели обязаны
    дать один устойчивый сигнал, а не три копии. Сам алерт прежний —
    `kind=warning`, `target=None` (расхождение считается поперёк всех
    задач и target'ов) через `alerts.raise_token_rate_divergence_alert`,
    не `alerts.raise_alert`: сообщение несёт растущие суммы, дедуп по
    точному тексту не сработал бы на повторных шагах (REVIEW.md
    01M1PP0VYRT55WN8GGVG66X89Y итерации 1, R1-F2) — дедуп идёт по
    префиксу сообщения, поэтому текст начинается с идентификатора модели.

    Возврат — `RateDivergence`: сам коэффициент числом (форма возврата
    `report.token_rate_divergence` этим и сохранена), а дата и число
    вошедших шагов — его атрибутами, потому что строка журнала и строка
    отчёта обязаны их назвать (требования 3, 7).
    """
    effective = model_tariff(model_id)
    if effective is None or not pairs:
        return None
    since = effective.calibrated_at
    actual_sum = sum(actual for _, actual in pairs)
    if actual_sum == 0:
        return None
    calculated_sum = sum(calculated for calculated, _ in pairs)
    coefficient = abs(calculated_sum - actual_sum) / actual_sum
    if coefficient > config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD:
        alerts.raise_token_rate_divergence_alert(
            conn, model_id,
            f"{model_id}: коэффициент расхождения тарифа модели "
            f"{coefficient:.2f} выше порога "
            f"{config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD} — расчётная "
            f"цена ${calculated_sum:.4f} против фактической "
            f"${actual_sum:.4f} по {len(pairs)} шагам с {since}")
    return RateDivergence(coefficient, len(pairs), since)


def charge_missing_result(conn, task_id: str, role: str, numbered: str,
                          cause: str, partial_tokens: dict,
                          saw_usage_event: bool) -> str:
    """Учёт попытки без финального события потока (таймаут/обрыв пайпа).

    Вызывается вместо `charge_step`, когда `pump.cost is None` ИМЕННО
    из-за таймаута шага или обрыва stdout-пайпа (tasks/T040) — обычный
    «тихий» путь `charge_step` (cost=None без этих причин) не трогается.

    `partial_tokens` — разбивка усечённого usage по видам
    (`models.PRICE_KINDS`; прежние имена тоже принимаются —
    `by_price_kind`), не просуммированное число (SPEC
    01M1PP0VYRT55WN8GGVG66X89Y, требование 2): восстановить точную сумму
    в долларах, которую посчитал бы сам CLI в финальном событии, всё
    равно нечем, но раздельные счётчики позволяют тарифицировать каждый
    вид его собственной ценой, а не средней ставкой входа/выхода на всю
    сумму (`partial_cost_usd`, требование 2/4, AC-2/AC-3). Действующий
    тариф модели роли (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 1)
    переводит разбивку в доллары там, где цепочка роли разрешается;
    исходное решение T040 «курса нигде нет» осталось только для ролей,
    чей тариф не разрешился.

    `saw_usage_event=True` — до обрыва в потоке были usage-события:
    тариф модели разрешился — частичная сумма по нему прибавляется к
    `spent_usd` (требование 2, AC-2), алерт не заводится. Тариф НЕ
    разрешился — прибавить нечего, вместо этого заводится алерт
    `kind=threshold` и в `spent_estimate_usd` идёт именованная верхняя
    оценка `config.STEP_COST_ESTIMATE_USD` (требование 3, AC-3) — каждый
    повтор отказа прибавляет оценку заново, недоучёт не должен копиться
    молча только потому, что алерт уже открыт.
    `saw_usage_event=False` — восстановить нечего вовсе, ни точно, ни
    по тарифу, ни оценкой: в журнал идёт «стоимость шага неизвестна», и
    открывается алерт `alerts` (`kind=incident`,
    `source=spend.unknown_cost`) — требование 4, поведение T040 без
    изменений.

    Неразрешимый тариф здесь именно деградирует, а не обрушивает
    вызывающего (REVIEW.md 01M1NWCM3TDY0YABEKE8DYQA1C итерации 1, R1-F1;
    SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 9): этот путь зовётся
    ровно в момент обработки таймаута шага/`pause --now`, до коммита
    чекпоинта и записи журнала «agent run TIMEOUT» — необработанное
    исключение здесь потеряло бы и то, и другое.
    """
    if not saw_usage_event:
        detail = (f"{numbered}: {cause}, финальное событие потока "
                 f"отсутствует, промежуточных usage-событий тоже нет — "
                 f"стоимость шага неизвестна, spent_usd не изменён")
        store.journal(conn, task_id, role, "agent cost LOST", detail)
        target = store.task_target(conn, task_id)
        alerts.raise_alert(conn, target, "incident", "spend.unknown_cost",
                           f"{task_id}/{role}: {numbered}, {cause} — "
                           f"финальное событие потока отсутствует, "
                           f"стоимость шага не восстановлена")
        return ""

    total_tokens = sum(partial_tokens.values())
    effective = role_tariff(role)
    rate_reason = f"тариф модели роли {role!r} не разрешён"
    if effective is not None:
        record_tariff(conn, effective)
        usd = tariff_cost_usd(effective.tariff, partial_tokens)
        detail = (f"{numbered}: {cause}, финальное событие потока "
                 f"отсутствует — частичная стоимость по тарифу модели "
                 f"{effective.model}: ${usd:.4f}, {SOURCE_TARIFF}, "
                 f"{total_tokens} токенов, "
                 f"разбивка по видам: {_tokens_by_type_text(partial_tokens)}"
                 f"{_tariff_note(effective)}")
        store.journal(conn, task_id, role, "agent cost PARTIAL", detail)
        store.charge(conn, task_id, usd)
        return (f", частичная стоимость по тарифу: ${usd:.4f}, "
                f"{total_tokens} токенов")

    estimate = config.STEP_COST_ESTIMATE_USD
    detail = (f"{numbered}: {cause}, финальное событие потока "
             f"отсутствует, {rate_reason} — верхняя "
             f"оценка стоимости шага: ${estimate:.4f}, {total_tokens} "
             f"токенов")
    store.journal(conn, task_id, role, "agent cost ESTIMATED", detail)
    store.charge_estimate(conn, task_id, estimate)
    target = store.task_target(conn, task_id)
    alerts.raise_alert(conn, target, "threshold", "spend.step_cost_unknown_rate",
                       f"{task_id}/{role}: {numbered}, {cause} — стоимость "
                       f"шага не учтена ({rate_reason}), "
                       f"{total_tokens} токенов")
    return f", верхняя оценка стоимости шага: ${estimate:.4f}"
