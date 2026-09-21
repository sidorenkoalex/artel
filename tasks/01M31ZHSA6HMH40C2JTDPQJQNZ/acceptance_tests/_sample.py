"""Общая обвязка планки 01M31ZHSA6HMH40C2JTDPQJQNZ: записанный образец
потока Claude и значения, которые извлекает из него код пульта ДО задачи.

Не тест: общий код нескольких файлов планки живёт только в модулях
`_*.py` рядом с тестами (skills/test-authoring.md). Здесь — сам образец
(события `type: assistant` с блоками `text`/`tool_use`, `type: user` с
блоком `tool_result`, служебное событие, не-JSON строка и финальное
`type: result` с `total_cost_usd` и `usage`), ожидания, снятые с
сегодняшнего кода (`orchestrator/agent_log.py`, `orchestrator/spend.py`),
и два помощника: вызов функции пульта, чья сигнатура после задачи может
получить роль/провайдера шага, и уплощение события общего вида.

Строки образца собираются `tests.sandbox.event` — той же функцией, какой
их собирают юнит-тесты пульта: собственная копия сериализации разошлась
бы с ней на первом же изменении формата.
"""
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.sandbox import event  # noqa: E402

#: Роль шага, на которой гоняется планка: у неё есть ярус в карте
#: исполнителей и, значит, разрешимый тариф модели.
ROLE = "developer"

#: Счётчики usage промежуточного события и финального итога — разные
#: числа по всем четырём видам: любое «взяли не тот счётчик» меняет
#: сумму, а не сходится случайно.
USAGE_ASSISTANT = {"input_tokens": 10, "output_tokens": 5,
                   "cache_creation_input_tokens": 400,
                   "cache_read_input_tokens": 1500}
USAGE_RESULT = {"input_tokens": 12, "output_tokens": 90,
                "cache_creation_input_tokens": 500,
                "cache_read_input_tokens": 2000}

RESULT_USD = 0.25
ERROR_USD = 0.7

#: Счётчик Claude -> общий вид цены (`models.PRICE_KINDS`). Записан
#: поимённо, а не порядком двух кортежей: имена счётчиков потока и имена
#: видов цены живут в разных файлах и по разным поводам.
KIND_FOR_COUNTER = {"input_tokens": "input",
                    "output_tokens": "output",
                    "cache_creation_input_tokens": "cache_write",
                    "cache_read_input_tokens": "cache_read"}

TOOL_NAME = "Read"
TOOL_ARG = "orchestrator/spend.py"
TOOL_RESULT_TEXT = "текст прочитанного файла"
ASSISTANT_TEXT = "работаю"
RESULT_TEXT = "готово"
ERROR_TEXT = "лимит контекста"

SYSTEM_LINE = event(type="system", subtype="init", session_id="sess-1")
TEXT_LINE = event(type="assistant", message={
    "role": "assistant",
    "content": [{"type": "text", "text": ASSISTANT_TEXT}],
    "usage": USAGE_ASSISTANT})
TOOL_USE_LINE = event(type="assistant", message={
    "role": "assistant",
    "content": [{"type": "tool_use", "id": "t1", "name": TOOL_NAME,
                 "input": {"file_path": TOOL_ARG}}]})
TOOL_RESULT_LINE = event(type="user", message={
    "role": "user",
    "content": [{"type": "tool_result", "tool_use_id": "t1",
                 "content": TOOL_RESULT_TEXT, "is_error": False}]})
TOOL_USE_REPEAT_LINE = event(type="assistant", message={
    "role": "assistant",
    "content": [{"type": "tool_use", "id": "t2", "name": TOOL_NAME,
                 "input": {"file_path": TOOL_ARG}}]})
PLAIN_LINE = "Traceback (most recent call last):\n"
RESULT_LINE = event(type="result", subtype="success", is_error=False,
                    result=RESULT_TEXT, total_cost_usd=RESULT_USD,
                    usage=USAGE_RESULT)
ERROR_RESULT_LINE = event(type="result", subtype="error_during_execution",
                          is_error=True, result=ERROR_TEXT,
                          total_cost_usd=ERROR_USD, usage=USAGE_RESULT)
#: Итог запуска БЕЗ цены (требование 4 SPEC) и итог с ценой РОВНО ноль —
#: два разных события, которые событие общего вида обязано различать.
RESULT_WITHOUT_PRICE_LINE = event(type="result", subtype="success",
                                  is_error=False, result=RESULT_TEXT,
                                  usage=USAGE_RESULT)
RESULT_ZERO_PRICE_LINE = event(type="result", subtype="success",
                               is_error=False, result=RESULT_TEXT,
                               total_cost_usd=0.0, usage=USAGE_RESULT)

#: Записанный образец потока шага целиком, в порядке появления строк.
STREAM = (SYSTEM_LINE, TEXT_LINE, TOOL_USE_LINE, TOOL_RESULT_LINE,
          TOOL_USE_REPEAT_LINE, PLAIN_LINE, RESULT_LINE)

#: Тот же образец, где финальный итог запуска цены не несёт.
STREAM_WITHOUT_PRICE = STREAM[:-1] + (RESULT_WITHOUT_PRICE_LINE,)

#: Образец без финального события вовсе (таймаут шага, обрыв пайпа).
STREAM_WITHOUT_RESULT = STREAM[:-1]

#: Образец, где usage несёт ТОЛЬКО итог запуска: на нём сумма по тарифу
#: одна и та же, считать её по разбивке итога или по накопленным за шаг
#: токенам (SPEC требование 4 выбор не фиксирует) — планка не вправе
#: навязывать разработчику ни одно из двух прочтений.
STREAM_RESULT_USAGE_ONLY = (SYSTEM_LINE, TOOL_USE_LINE, TOOL_RESULT_LINE,
                            RESULT_WITHOUT_PRICE_LINE)

#: То же, но итог запуска несёт цену CLI: вход сценария «провайдер
#: помечен в каталоге `cost_from_cli: false`».
STREAM_RESULT_USAGE_ONLY_PRICED = (SYSTEM_LINE, TOOL_USE_LINE,
                                   TOOL_RESULT_LINE, RESULT_LINE)

# --- ожидания, снятые с кода пульта ДО задачи -------------------------
#
# Значения ниже посчитаны по сегодняшним `agent_log.render_agent_line`,
# `agent_log.step_friction`, `spend.parse_cost_event`,
# `spend.stream_usage_by_type` на строках образца выше — литералами, а не
# повторным вызовом тех же функций: тест, сравнивающий функцию с ней же,
# пережил бы любую их правку.

EXPECTED_RENDER = {
    SYSTEM_LINE: "",
    TEXT_LINE: f"{ASSISTANT_TEXT}\n",
    TOOL_USE_LINE: f"· {TOOL_NAME} {TOOL_ARG}\n",
    TOOL_RESULT_LINE: "",
    TOOL_USE_REPEAT_LINE: f"· {TOOL_NAME} {TOOL_ARG}\n",
    PLAIN_LINE: PLAIN_LINE,
    RESULT_LINE: "",
    ERROR_RESULT_LINE: f"! ошибка агента: {ERROR_TEXT}\n",
}

#: Текст лога шага по образцу целиком — конкатенация непустых рендеров.
EXPECTED_LOG_TEXT = "".join(EXPECTED_RENDER[line] for line in STREAM)

#: Трение образца: два вызова инструмента, второй — повторное чтение уже
#: прочитанного файла, значит один непродуктивный из двух.
EXPECTED_FRICTION = 0.5

EXPECTED_COST_USD = RESULT_USD
EXPECTED_COST_TOKENS = sum(USAGE_RESULT.values())
EXPECTED_PARTIAL_TOKENS = {key: USAGE_ASSISTANT[key] + USAGE_RESULT[key]
                           for key in USAGE_ASSISTANT}


def normalized(tokens_by_type) -> dict:
    """Разбивка токенов по ОБЩИМ видам, принимающая обе формы имён:
    прежние счётчики Claude (`input_tokens`, …) и общие имена
    (`input`, …). Нужна там, где критерий говорит о ЗНАЧЕНИЯХ разбивки
    (AC-7: «те же значения, что до задачи»), а имена видов эта же задача
    меняет на общие (AC-2) — сравнивать имена там значило бы столкнуть
    два критерия лбами."""
    if not tokens_by_type:
        return {}
    out = {}
    for key, value in tokens_by_type.items():
        out[KIND_FOR_COUNTER.get(key, key)] = value
    return out


EXPECTED_COST_BY_KIND = normalized(USAGE_RESULT)
EXPECTED_PARTIAL_BY_KIND = normalized(EXPECTED_PARTIAL_TOKENS)
EXPECTED_ASSISTANT_BY_KIND = normalized(USAGE_ASSISTANT)


def flex(fn, *args, role=ROLE, provider=None):
    """Вызов функции пульта, чья сигнатура после задачи может получить
    роль или провайдера шага.

    Требование 3 SPEC переводит шесть точек разбора на провайдера роли
    шага, а как именно он туда попадёт — параметром `role`, параметром
    `provider` или уже разрешённым объектом, — критерии не фиксируют.
    Планка не вправе выдумывать сигнатуру: она передаёт роль/провайдера
    ровно тем параметрам, которые сама функция объявила, и ничего не
    передаёт, если параметров не прибавилось. Никаких `except TypeError`
    вокруг вызова: сигнатура читается заранее, а настоящая ошибка внутри
    функции обязана долететь до теста, а не быть принятой за «другую
    форму вызова».
    """
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):  # pragma: no cover — встроенная функция
        return fn(*args)
    kwargs = {}
    for param in params[len(args):]:
        if param.kind in (inspect.Parameter.VAR_POSITIONAL,
                          inspect.Parameter.VAR_KEYWORD):
            continue
        name = param.name.lower()
        if "provider" in name:
            kwargs[param.name] = provider
        elif "role" in name:
            kwargs[param.name] = role
    return fn(*args, **kwargs)


def leaves(value, acc=None) -> list:
    """Все листья структуры события: строки, числа, булевы, `None`.

    Событие общего вида — предмет самой задачи, и его форму (namedtuple,
    словарь, объект) критерии не называют: планка проверяет, что в
    событии ЕСТЬ названные критерием значения, не диктуя, как они
    разложены по полям.
    """
    acc = [] if acc is None else acc
    if isinstance(value, dict):
        for key, item in value.items():
            leaves(key, acc)
            leaves(item, acc)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            leaves(item, acc)
    elif hasattr(value, "_asdict"):
        leaves(value._asdict(), acc)
    elif hasattr(value, "__dict__") and vars(value):
        leaves(vars(value), acc)
    else:
        acc.append(value)
    return acc


def mappings(value, acc=None) -> list:
    """Все словари внутри структуры события — в них планка ищет разбивку
    токенов по видам, не зная имени поля, в котором она лежит."""
    acc = [] if acc is None else acc
    if isinstance(value, dict):
        acc.append(value)
        for key, item in value.items():
            mappings(key, acc)
            mappings(item, acc)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            mappings(item, acc)
    elif hasattr(value, "_asdict"):
        mappings(value._asdict(), acc)
    elif hasattr(value, "__dict__") and vars(value):
        mappings(vars(value), acc)
    return acc


def has_breakdown(value, expected: dict) -> bool:
    """Есть ли внутри структуры словарь, который отдаёт ровно `expected`
    по каждому его ключу (лишние нулевые виды допускаются: «вида не
    было» и «вид нулевой» — разные утверждения, и критерий AC-2 их не
    различает)."""
    for table in mappings(value):
        if not table:
            continue
        if all(table.get(kind) == count for kind, count in expected.items()):
            return True
    return False


def log_file(path: Path, lines) -> Path:
    """Файл сырого лога шага со строками образца — вход постфактум-
    разбора (`agent_log.step_friction`, `spend.partial_tokens_from_log`)."""
    path.write_text("".join(lines), encoding="utf-8")
    return path
