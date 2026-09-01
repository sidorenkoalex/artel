"""Общая песочница приёмочных тестов T095 (не test_*.py — не подхватывается
unittest discover напрямую, только импортом из test_ac*.py).

Интерфейс низкоуровневой функции метрики (SPEC требование 1, AC-1) нигде
буквально не зафиксирован — SPEC отдаёт «точный состав сигналов и
пороги» решению разработчика (требование 1). Эти тесты предполагают
`orchestrator.agent_log.step_friction(log_path: Path) -> float`:
- имя и модуль — по зоне задачи («`orchestrator/agent_log.py`
  (расширение парсера)», требование 5) и по соседству с уже
  существующим постфактум-разбором лога того же файла на диске,
  `spend.partial_tokens_from_log(path: Path)` (SPEC T074, требование 4);
- сигнатура (`Path` → `float`) — самое прямое прочтение форомулировки
  AC-1 «функция, вычисляющая долю ... событий шага»: доля — это одно
  число 0..1, а не структура, чью форму пришлось бы дополнительно
  придумывать.

Числа сигналов внутри (что считать «повтором», «большим куском» и т.п.)
эти тесты НЕ фиксируют — по SPEC это решение разработчика. Тесты AC-1
проверяют направление и границы, которые верны при ЛЮБОМ разумном
пороге: чистый шаг без единого поименованного в ТЗ сигнала — 0; шаг с
добавленным сигналом одного из трёх видов — строго больше эквивалентного
по числу обращений «чистого» шага.

Формат фикстур-логов — реальный `--output-format stream-json` построчно
(`event`/`assistant_event`/`tool_use_block`/`user_tool_result` ниже, по
образцу `tests/test_agent_log.py`), поскольку САМА SPEC называет именно
этот формат источником (материалы, требование 1). Файл `.artel/logs/
<id>-<role>-N.log`, как его реально пишет `agent_log.tee_lines`
(рендер-транскрипт, не сырой JSON, docstring `orchestrator/agent_log.py`
и `tests/test_step_cost.py::PumpCostTest`) — вопрос того, ЧТО разработчик
решит персистировать на диск при расширении парсера (та же зона), а не
предмет теста AC-1: функция принимает файл лога шага и обязана
детерминированно посчитать долю по его содержимому, каким бы оно ни
было.
"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


# ------------------------------------------------------- фикстуры-события

def event(**fields) -> str:
    """Строка потока `--output-format stream-json`."""
    return json.dumps(fields, ensure_ascii=False) + "\n"


def assistant_event(*blocks) -> str:
    return event(type="assistant",
                 message={"role": "assistant", "content": list(blocks)})


def user_event(*blocks) -> str:
    return event(type="user", message={"role": "user", "content": list(blocks)})


def tool_use_block(tool_use_id: str, name: str, **input_kwargs) -> dict:
    return {"type": "tool_use", "id": tool_use_id, "name": name,
           "input": input_kwargs}


def tool_result_line(tool_use_id: str, content: str, is_error: bool = False) -> str:
    """Событие `type: user` с результатом инструмента — так реальный CLI
    несёт ошибку/успех КОНКРЕТНОГО вызова (`is_error` на блоке
    `tool_result`), в отличие от событий `type: result`, которые
    `agent_log.render_agent_line` уже разбирает на уровне ВСЕГО шага."""
    return user_event({"type": "tool_result", "tool_use_id": tool_use_id,
                       "content": content, "is_error": is_error})


def read_call(tool_use_id: str, file_path: str) -> str:
    return assistant_event(tool_use_block(tool_use_id, "Read",
                                          file_path=file_path))


def bash_call(tool_use_id: str, command: str) -> str:
    return assistant_event(tool_use_block(tool_use_id, "Bash",
                                          command=command))


def edit_call(tool_use_id: str, file_path: str) -> str:
    return assistant_event(tool_use_block(tool_use_id, "Edit",
                                          file_path=file_path))


# ---------------------------------------------------------------- песочница

class FrictionSandboxTest(TmpRootTest):
    """`config.DB`/`config.LOGS` во временном каталоге, схема — `cmd_init`."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        from orchestrator import agent_log, report  # noqa: E402 — красное до реализации
        self.agent_log = agent_log
        self.report = report

    def write_log(self, task_id: str, role: str, run_n: int, lines: list) -> Path:
        config.LOGS.mkdir(parents=True, exist_ok=True)
        path = config.LOGS / f"{task_id}-{role}-{run_n}.log"
        path.write_text("".join(lines), encoding="utf-8")
        return path

    def mk_task(self, task_id: str, title: str, state: str = "in_dev", *,
               budget_usd: float = 1.0) -> str:
        conn = store.db()
        store.insert_task(conn, task_id, title, state,
                          branch=f"task/{task_id}-fixture",
                          target=config.DEFAULT_TARGET, budget_usd=budget_usd)
        return task_id

    def run_report_html(self) -> str:
        """Прогоняет `report.cmd_report()`, возвращает текст файла.

        Читает ФИКСИРОВАННЫЙ путь `orchestrator/report.py::cmd_report`
        (`config.ROOT/.artel/report.html`, тот же файл каждый раз, без
        истории версий) напрямую — не «новый файл за вызов», в отличие
        от `tasks/T092/acceptance_tests/_sandbox.py::run_report`: тесты
        этого файла зовут `cmd_report()` НЕСКОЛЬКО раз за один тест
        (до/после правки лога), а второй и последующие вызовы не создают
        НОВОГО файла — перезаписывают тот же (AC-11 T092)."""
        self.capture(self.report.cmd_report)
        path = config.ROOT / ".artel" / "report.html"
        return path.read_text(encoding="utf-8")

    def tmp_log_path(self, lines: list) -> Path:
        """Лог вне `config.LOGS` — для тестов низкоуровневой функции
        напрямую, без db/report вокруг."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "step.log"
        path.write_text("".join(lines), encoding="utf-8")
        return path


# ------------------------------------------------------- текстовые утилиты
#
# Разметку блока метрики трения SPEC не фиксирует (только «блок с
# метрикой трения», требование 3) — по образцу
# `tasks/T092/acceptance_tests/_sandbox.py` (`scope`/`all_scopes`) ниже
# идёт markup-агностичный поиск: по слову «трение» (буквальное имя
# метрики во всём SPEC/ТЗ) находится охватывающая `<section>`, а числа
# внутри сравниваются как МНОЖЕСТВА ТЕКСТОВЫХ токенов между двумя
# прогонами — без попытки угадать формат отображения доли (доля/проценты/
# округление), который тоже нигде не зафиксирован.

_NUM_TOKEN_RE = re.compile(r'\d+(?:[.,]\d+)?%?')


def numeric_tokens(text: str) -> set:
    return set(_NUM_TOKEN_RE.findall(text))


_HEADING_TRENIE_RE = re.compile(r'<h[1-4][^>]*>[^<]*трени', re.IGNORECASE)


def friction_section(html: str) -> str:
    """Блок `<section>`, где ЗАГОЛОВОК (`<h1>`..`<h4>`) несёт слово
    «трение»/«трения» (без учёта регистра) — не любое упоминание слова
    где угодно на странице: заголовок задачи-фикстуры в борде ТОЖЕ может
    случайно содержать «трение» (само название метрики этой задачи), а
    искать нужно именно РАЗДЕЛ метрики, а не любую строку с этим корнем."""
    match = _HEADING_TRENIE_RE.search(html)
    if match is None:
        return ""
    idx = match.start()
    start = html.rfind("<section", 0, idx)
    if start == -1:
        start = idx
    end = html.find("</section>", idx)
    if end == -1:
        end = len(html)
    return html[start:end]


def scope(html: str, needle: str, before_chars: int = 300,
         after_chars: int = 800) -> str | None:
    """Окно текста вокруг ПЕРВОГО вхождения `needle` — не привязывается
    к конкретной разметке, только к факту, что нужное поле расположено
    где-то рядом с искомым текстом (по образцу T092 `_sandbox.py`)."""
    idx = html.find(needle)
    if idx == -1:
        return None
    start = max(0, idx - before_chars)
    end = min(len(html), idx + len(needle) + after_chars)
    return html[start:end]
