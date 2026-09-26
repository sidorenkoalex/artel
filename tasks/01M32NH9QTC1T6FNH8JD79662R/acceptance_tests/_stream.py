"""Общий код планки: образцы строк потока `codex exec --json` и адреса,
нужные больше чем одному `test_*.py`.

Образцы — из материалов SPEC, не из фантазии: поток 0.154.0-alpha.6.2
(TZ.md родительской задачи, числа AC-1) и поток 0.155.1 (ANSWER-1.md той
же задачи — числа AC-2, пара `item.started`/`item.completed` и
`status: failed` при `error: null` AC-3). Строки собираются `json.dumps`
из словарей, а не копипастой текста: копипаста молча меняла бы предмет
теста на форматирование JSON.

Не песочница: собственных копий `disk_backed_*`/`advance_from_in_dev`
здесь нет — переходы FSM планке не нужны, шаг берётся готовыми точками
пульта (`spend.charge_step`, `runner._run_attempts`).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, models, providers  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

#: Имя провайдера — от самого провайдера, не литералом планки: реестр
#: знает его одним значением (`CodexProvider.name`).
PROVIDER = codex_provider.CLI_NAME


def provider():
    """Провайдер `codex` из реестра пульта — тот же объект, которым
    пойдёт шаг роли, а не свой экземпляр класса."""
    return providers.get(PROVIDER)


def stream_line(**fields) -> str:
    """Одна строка вывода `codex exec --json` — тем же приёмом, каким
    `tests/sandbox.py::event` собирает строку потока Claude."""
    return json.dumps(fields, ensure_ascii=False) + "\n"


def item_line(kind: str, **item) -> str:
    """Строка события об элементе: вид СОБЫТИЯ снаружи (`item.started`),
    вид ЭЛЕМЕНТА — полем `type` самого элемента."""
    return stream_line(type=kind, item=item)


# --- итог запуска ------------------------------------------------------

#: `usage` образца 0.154.0-alpha.6.2 (числа AC-1): кэшированный вход
#: ВХОДИТ в `input_tokens`.
USAGE_TZ = {"input_tokens": 17382, "cached_input_tokens": 12416,
            "cache_write_input_tokens": 0, "output_tokens": 6,
            "reasoning_output_tokens": 0}

#: `usage` живого запуска 0.155.1 (числа AC-2): `reasoning_output_tokens`
#: — ЧАСТЬ `output_tokens`.
USAGE_LIVE = {"input_tokens": 1310229, "cached_input_tokens": 1072000,
              "cache_write_input_tokens": 0, "output_tokens": 8513,
              "reasoning_output_tokens": 997}

TURN_COMPLETED_TZ = stream_line(type="turn.completed", usage=USAGE_TZ)
TURN_COMPLETED_LIVE = stream_line(type="turn.completed", usage=USAGE_LIVE)

# --- пара вызова инструмента -------------------------------------------

COMMAND_ID = "item_1"
COMMAND = "/bin/zsh -lc 'cat docs/stack.md'"
COMMAND_OUTPUT = "## Стек пульта"

COMMAND_STARTED = item_line(
    "item.started", id=COMMAND_ID, type="command_execution", command=COMMAND,
    aggregated_output="", exit_code=None, status="in_progress")
COMMAND_COMPLETED = item_line(
    "item.completed", id=COMMAND_ID, type="command_execution", command=COMMAND,
    aggregated_output=COMMAND_OUTPUT, exit_code=0, status="completed")
#: Тот же элемент с кодом выхода 6 и `status: failed` — второй
#: `command_execution` живого запуска 0.155.1.
COMMAND_FAILED = item_line(
    "item.completed", id=COMMAND_ID, type="command_execution", command=COMMAND,
    aggregated_output=COMMAND_OUTPUT, exit_code=6, status="failed")

MCP_ID = "item_9"
#: `mcp_tool_call`, завершившийся `status: failed` ПРИ `error: null` —
#: ровно тот случай живого запуска, из-за которого признак ошибки берётся
#: из `status`, а не из `error`.
MCP_FAILED = item_line(
    "item.completed", id=MCP_ID, type="mcp_tool_call", server="cua_repl",
    tool="js", arguments={"code": "await cua.getBrowser({url: \"…\"});"},
    result={"content": [{"type": "text", "text": "No browser is available"}]},
    error=None, status="failed")

# --- сказанный текст, служебные и незнакомые виды ----------------------

AGENT_MESSAGE_TEXT = "готово"
AGENT_MESSAGE = item_line("item.completed", id="item_0",
                          type="agent_message", text=AGENT_MESSAGE_TEXT)

THREAD_STARTED = stream_line(type="thread.started",
                             thread_id="01a0c52c-30bd-7132-a86a-56b86bd8602d")
TURN_STARTED = stream_line(type="turn.started")

#: Незнакомый вид СОБЫТИЯ: имя, которого нет среди пяти видов образца.
UNKNOWN_EVENT = stream_line(type="thread.vida-kotorogo-net",
                            payload={"a": 1})
#: `item.updated` — вид события, которого образцы не несут, а живой запуск
#: 0.155.1 несёт (SPEC требование 1, последний абзац): тот же незнакомый
#: вид, пустое событие.
ITEM_UPDATED = item_line("item.updated", id=COMMAND_ID,
                         type="command_execution", command=COMMAND,
                         aggregated_output="ещё пишется", status="in_progress")
#: Незнакомый вид ЭЛЕМЕНТА.
UNKNOWN_ITEM = item_line("item.completed", id="item_7",
                         type="element_kotorogo_net", payload={"a": 1})
#: `item.type=error` при переключении транспорта (SPEC требование 1): тот
#: же незнакомый вид элемента — пустое событие, шаг НЕ провален.
ERROR_ITEM = item_line("item.completed", id="item_8", type="error",
                       message="stream disconnected before completion")

# --- строки мимо формата событий ---------------------------------------

TRACEBACK_LINE = "Traceback (most recent call last):\n"
BROKEN_JSON_LINE = '{"type": "turn.completed", "usage":\n'
JSON_ARRAY_LINE = "[1, 2]\n"


def codex_model_id() -> str:
    """Идентификатор модели раздела `codex` каталога моделей — ОТ
    каталога, не литералом: состав раздела правит Оператор, и зашитое
    имя модели пережило бы только до первой его правки."""
    ids = sorted(entry.id for entry in models.load_catalog().models.values()
                 if entry.provider == PROVIDER)
    if not ids:
        raise AssertionError(
            f"в каталоге {config.MODELS} нет ни одной модели провайдера "
            f"{PROVIDER} — раздел каталога завела часть 1 линии")
    return ids[0]
