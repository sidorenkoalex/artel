"""Общая песочница приёмочных тестов задачи 01M1THKRK8HPXA7Y2SRB0RFTN2
(«стоп-кран волны, часть 2 — пауза run/auto по открытому алерту и
видимость»).

Не подхватывается `unittest discover` напрямую (не `test_*.py`) — файлы
`test_ac*.py` этого каталога делят с ним фикстуры, тем же приёмом, что
`tasks/T070/acceptance_tests/_sandbox.py`.

## Допущения интерфейса (SPEC называет только наблюдаемое поведение)

SPEC этой задачи не фиксирует ни модуль/функцию, читающую «открыт ли
алерт стоп-крана», ни литеральный текст пометки `status`/`doctor` — она
описывает только внешне наблюдаемое поведение команд (`run`/`auto`
отказывают, `alert-ack` снимает блокировку, `doctor`/`status` показывают
факт). Тесты ниже опираются на два конкретных, но МИНИМАЛЬНО обязывающих
допущения, оба — прямое следствие уже согласованных документов, не
изобретение теста:

1. Алерт стоп-крана — обычный `kind=incident` (`orchestrator/alerts.py`),
   заводится (частью 1, задача 01M1THKPNZ11DBZAQDMJ33EMJR, SPEC на
   `artifact/01m1thkpnz11dbzaqdmj33emjr`, требование 3) с сообщением
   ДОСЛОВНО вида «стоп-кран волны: класс <класс> у N задач за M минут»
   и `target` = имя target'а (`config.DEFAULT_TARGET` для self), не id
   задачи. Фикстуры ниже заводят такой же алерт напрямую через
   `alerts.raise_alert` (публичный API, не требующий части 1) —
   распознавание «это алерт стоп-крана» по подстроке «стоп-кран» в
   `message` совпадающего `target` — единственный способ узнать факт,
   не зависящий от внутреннего имени `source`, которого часть 1 ещё не
   определила.
2. Пометка `status`/причина отказа `run`/`auto`/первая строка `doctor`
   называют это же слово «стоп-кран» текстом (AC-1 SPEC этой задачи:
   «текст упоминает стоп-кран») — тесты проверяют по этой подстроке, не
   по точному формату строки.

Прогон ДО реализации падает по-разному в зависимости от теста: там, где
предмет теста — сам факт блокировки, `run`/`auto` сейчас (без кода этой
задачи) просто НЕ отказывают, и assert на отказ не совпадёт (см. маркер
«Красен до реализации» каждого файла).
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import (alerts, auto, catalog, config, doctor,  # noqa: E402
                          fsm, runner, store)
from tests.test_invariants import FakeProc, FsmTest  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

__all__ = ["invoke", "LightSandbox", "RunPipelineSandbox", "FakeProc",
          "raise_stop_crane_alert", "stop_crane_message", "STOP_CRANE_WORD",
          "mentions_stop_crane", "OTHER_TARGET", "alerts", "auto", "catalog",
          "config", "doctor", "fsm", "runner", "store", "mock", "capture"]

# Слово, которым и SPEC (AC-1), и сообщение части 1 называют сигнал —
# единственная опора распознавания, не зависящая от внутреннего имени
# `source` (см. докстринг модуля, допущение 1).
STOP_CRANE_WORD = "стоп-кран"

# Второй target — тем же именем, что уже устоялось в остальных тестах
# пульта для внешнего проекта (`tests/test_doctor.py::TARGETS_YAML_WITH_SLED`,
# `tests/test_multitarget_invariants.py`).
OTHER_TARGET = "sled"


def mentions_stop_crane(text: str) -> bool:
    """Регистронезависимая проверка «текст называет стоп-кран» (AC-1: «текст
    упоминает стоп-кран») — пометка/причина отказа вправе быть капсом
    (`[СТОП-КРАН]`, по образцу существующих `[FAIL]`/`[canary]`), не только
    буквальным нижним регистром SPEC."""
    return STOP_CRANE_WORD in text.lower()


def stop_crane_message(klass: str = "1б", count: int = 3,
                       window_min: int = 15) -> str:
    """Дословный формат сообщения части 1 (SPEC 01M1THKPNZ11DBZAQDMJ33EMJR,
    требование 3): «стоп-кран волны: класс <класс> у N задач за M минут»."""
    return f"{STOP_CRANE_WORD} волны: класс {klass} у {count} задач за {window_min} минут"


def raise_stop_crane_alert(conn, target: str | None = None,
                           message: str | None = None):
    """Заводит алерт `kind=incident` стоп-крана волны для `target`
    (умолчание — self, `config.DEFAULT_TARGET`) и возвращает его строку
    БД целиком (id нужен `alert-ack`, остальное — сверке target/message).

    Источник (`source`) — литерал `"wave_breaker"`, тем же словом, что
    константы части 1 (`WAVE_BREAKER_WINDOW_SEC`/`WAVE_BREAKER_TASKS`,
    SPEC 01M1THKPNZ11DBZAQDMJ33EMJR, требование 1) — правдоподобное,
    но не обязывающее имя: распознавание тестов опирается на `message`
    (допущение 1 в докстринге модуля), не на этот `source`.
    """
    target = config.DEFAULT_TARGET if target is None else target
    message = message or stop_crane_message()
    opened = alerts.raise_alert(conn, target, "incident", "wave_breaker", message)
    assert opened, "фикстура теста не смогла завести алерт — уже открыт такой же"
    rows = alerts.open_alerts(conn, "incident")
    for row in rows:
        if row["target"] == target and row["message"] == message:
            return row
    raise AssertionError("алерт стоп-крана заведён, но не найден в open_alerts")


def invoke(call) -> tuple:
    """(стдаут, код выхода) — отказ команды пульта уходит либо `sys.exit`
    (код в исключении), либо печатью + обычным `return` (код `None`),
    тот же приём, что `tasks/T070/acceptance_tests/_sandbox.py::invoke`."""
    buf = io.StringIO()
    code = None
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        code = exc.code
    return buf.getvalue(), code


class LightSandbox(TmpRootTest):
    """БД во временном каталоге + одна задача `T001` (target self, in_dev) —
    для команд, не запускающих настоящий агентный шаг (`status`, `doctor`,
    `budget`), тем же приёмом, что `tests/test_pause.py::PauseTest`."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача self",
                          "in_dev", "task/t001-zadacha",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def row(self, task_id: str | None = None):
        return store.get_task(store.db(), task_id or self.TASK)

    def journal(self, task_id: str | None = None) -> list:
        return store.task_steps(store.db(), task_id or self.TASK)


class RunPipelineSandbox(FsmTest):
    """`FsmTest` (T001, git/CLI-preflight заглушены, `spawn_agent`
    подменяем) — для тестов, которым нужен НАСТОЯЩИЙ `runner.cmd_run`/
    `auto.cmd_auto` по задаче self (`self.TASK`, `config.DEFAULT_TARGET`),
    тем же приёмом, что `tasks/T070/acceptance_tests/_sandbox.py::PauseSandbox`
    поверх той же `FsmTest`."""

    def journal_tail_text(self, since: int = 0) -> str:
        rows = store.task_steps(store.db(), self.TASK)[since:]
        return "\n".join(f"{r['actor']} {r['action']} {r['detail']}"
                         for r in rows)

    def run_with_fake_agent(self, call) -> tuple:
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out, code = invoke(call)
        return out, popen, code

    def run_with_mid_step_side_effect(self, call, side_effect) -> tuple:
        """`spawn_agent`, который сначала исполняет `side_effect` (событие,
        случившееся «во время» уже стартовавшего шага), а затем как обычно
        отдаёт `FakeProc` успешного шага — тот же приём, что T070 применил
        к пометке паузы, поставленной прямо во время бегущего шага."""
        def fake_popen(*args, **kwargs):
            side_effect()
            return FakeProc(["готово\n"])
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=fake_popen) as popen:
            out, code = invoke(call)
        return out, popen, code
