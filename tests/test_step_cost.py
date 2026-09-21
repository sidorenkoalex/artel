"""Тесты учёта стоимости шага и потолка бюджета (см. tasks/T007/SPEC.md).

Реального `claude` CLI тут нет: `subprocess.Popen` подменяется фейковым
процессом, в поток которого подкладывается финальное событие
`--output-format stream-json` со стоимостью. Так проверяются и разбор
события, и деньги в БД, и реакция на потолок.

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002, принцип целостности): кодируют инвариант
«потолок задачи = её денежный бюджет, жёсткий, с алертом на 70%»
(README «Инварианты» 5, docs/design.md §6, §10). Ослабить, заскипать или
удалить их может только Оператор отдельным ADR; перечень «инвариант →
тест → откуда» — docs/invariants.md.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (agent_log, budget, catalog, config,  # noqa: E402
                          fsm, gitcmd, providers, runner, spend, store)
from tests.sandbox import (DeveloperBriefTmpRootTest as TmpRootTest,  # noqa: E402
                           FakeProc, FakeStream, capture_new_task_id, event,
                           fake_git, sync_spec_from_worktree)


def result_event(usd=0.5, **fields) -> str:
    """Финальное событие запуска: в нём стоимость и usage."""
    return event(type="result", subtype="success", is_error=False,
                 result="готово", total_cost_usd=usd, **fields)


def assistant_event(usage=None) -> str:
    """Промежуточное событие потока: usage лежит в `message.usage`."""
    message = {"role": "assistant", "content": [{"type": "text", "text": "работаю"}]}
    if usage is not None:
        message["usage"] = usage
    return event(type="assistant", message=message)


def tool_use_event(call_id: str, name: str, **input_kwargs) -> str:
    """Событие потока с вызовом инструмента (tasks/T095/SPEC.md)."""
    return event(type="assistant", message={"role": "assistant", "content": [
        {"type": "tool_use", "id": call_id, "name": name, "input": input_kwargs}]})



class ParseCostEventTest(unittest.TestCase):
    """Разбор финального события потока: цена шага и токены.

    Разбивка — по ОБЩИМ видам цены (`models.PRICE_KINDS`, SPEC
    01M31ZHSA6HMH40C2JTDPQJQNZ требование 1): счётчики своего CLI
    провайдер переводит в них при разборе строки.
    """

    def test_cost_and_tokens_are_taken_from_result_event(self):
        """Ловит мутацию: разбор итога запуска берёт цену из другого
        поля, теряет счётчик usage или суммирует виды в одно число —
        шаг по-прежнему «учтён», но списанная сумма и разбивка, на
        которой стоит вся сверка тарифа с фактом CLI, становятся
        другими."""
        cost = spend.parse_cost_event(result_event(
            usd=0.1234, usage={"input_tokens": 10, "output_tokens": 90,
                               "cache_creation_input_tokens": 400,
                               "cache_read_input_tokens": 500}))

        self.assertEqual(cost, {"usd": 0.1234, "tokens": 1000, "tokens_by_type": {
            "input": 10, "output": 90,
            "cache_write": 400, "cache_read": 500}})

    def test_tokens_are_optional(self):
        cost = spend.parse_cost_event(result_event(usd=0.5))

        self.assertEqual(cost, {"usd": 0.5, "tokens": None, "tokens_by_type": None})

    def test_known_usage_counters_are_summed(self):
        """Ловит мутацию: в разбивку попадает любое поле `usage` —
        `server_tool_use` становится «видом токенов», и первая же
        попытка тарифицировать такую разбивку падает на тарифе, у
        которого такого вида нет."""
        cost = spend.parse_cost_event(result_event(
            usd=0.5, usage={"input_tokens": 7, "server_tool_use": {"a": 1}}))

        self.assertEqual(cost["tokens"], 7, "чужие поля usage не считаются")
        self.assertEqual(cost["tokens_by_type"], {"input": 7},
                         "чужие поля usage не попадают в разбивку")

    def test_failed_run_still_costs_money(self):
        cost = spend.parse_cost_event(event(
            type="result", subtype="error_during_execution", is_error=True,
            result="лимит контекста", total_cost_usd=0.7))

        self.assertEqual(cost["usd"], 0.7)

    def test_free_run_is_zero_not_unknown(self):
        self.assertEqual(spend.parse_cost_event(result_event(usd=0))["usd"], 0.0)

    def test_events_without_cost_are_unknown(self):
        for raw in (event(type="system", subtype="init"),
                    event(type="assistant", message={"content": []}),
                    event(type="result", subtype="success"),
                    event(type="result", total_cost_usd=None),
                    event(type="result", total_cost_usd="0.5"),
                    event(type="result", total_cost_usd=True),
                    event(type="result", total_cost_usd=-1),
                    event(type="result", total_cost_usd=float("nan")),
                    '{"type": "result", "total_cost_usd": NaN}\n',
                    '{"type":"result","total_cost_usd":\n',
                    "Traceback (most recent call last):\n",
                    "[1, 2]\n"):
            with self.subTest(raw=raw[:45]):
                self.assertIsNone(spend.parse_cost_event(raw))

    def test_unknown_cost_renders_as_nothing(self):
        self.assertEqual(spend.cost_note(None), "")

    def test_cost_note_shows_dollars_and_tokens(self):
        note = spend.cost_note({"usd": 0.1234, "tokens": 1000})

        self.assertIn("$0.1234", note)
        self.assertIn("1000", note)


class StreamUsageByTypeTest(unittest.TestCase):
    """Разбивка usage по видам любого события потока (tasks/T040, уточнено
    01M1PP0VYRT55WN8GGVG66X89Y требованием 2) — не только `result`, и не
    одной суммой, а по видам цены `models.PRICE_KINDS` раздельно."""

    def test_assistant_event_usage_is_broken_down_by_type(self):
        """Ловит мутацию: разбор `assistant`-события суммирует счётчики в
        одно число вместо разбивки по видам (`input`/`output`
        раздельно)."""
        tokens = spend.stream_usage_by_type(assistant_event(
            usage={"input_tokens": 10, "output_tokens": 5}))

        self.assertEqual(tokens, {"input": 10, "output": 5})

    def test_result_event_usage_still_works(self):
        """Ловит мутацию: добавление ветки `assistant` в `stream_usage_by_type`
        ломает уже работавший разбор `result`-события."""
        tokens = spend.stream_usage_by_type(result_event(
            usd=0.5, usage={"input_tokens": 7, "output_tokens": 3}))

        self.assertEqual(tokens, {"input": 7, "output": 3})

    def test_assistant_event_without_usage_is_none(self):
        self.assertIsNone(spend.stream_usage_by_type(assistant_event()))

    def test_other_event_types_are_ignored(self):
        for raw in (event(type="system", subtype="init"),
                    event(type="user", message={"role": "user", "content": []}),
                    event(type="assistant", message="не словарь"),
                    "простой текст без json\n",
                    '{"type": "assistant", "message":\n'):
            with self.subTest(raw=raw[:40]):
                self.assertIsNone(spend.stream_usage_by_type(raw))


class PartialTokensFromLogTest(unittest.TestCase):
    """`spend.partial_tokens_from_log` (SPEC T074, требование 4; разбивка
    по видам — 01M1PP0VYRT55WN8GGVG66X89Y требование 2) — тот же разбор
    usage-событий, что `OutputPump.catch_cost` делает по потоку, только
    постфактум по уже записанному на диск файлу лога."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.log_path = Path(tmp.name) / "step.log"

    def write(self, lines: list) -> None:
        self.log_path.write_text("".join(lines), encoding="utf-8")

    def test_usage_events_are_summed_by_type(self):
        """Ловит мутацию: несколько usage-событий лога схлопываются в одну
        общую сумму вместо накопления по каждому виду счётчика отдельно."""
        self.write([
            "агент работает\n",
            assistant_event(usage={"input_tokens": 10, "output_tokens": 5}),
            assistant_event(usage={"input_tokens": 20, "output_tokens": 8}),
        ])

        tokens, saw = spend.partial_tokens_from_log(self.log_path)

        self.assertEqual(tokens, {"input": 30, "output": 13})
        self.assertTrue(saw)

    def test_no_usage_events_returns_empty_and_false(self):
        """Ловит мутацию: отсутствие usage-событий в логе возвращает
        непустой словарь или `saw=True` вместо честного `({}, False)`."""
        self.write(["агент работает, без usage\n"])

        tokens, saw = spend.partial_tokens_from_log(self.log_path)

        self.assertEqual(tokens, {})
        self.assertFalse(saw)

    def test_missing_file_returns_empty_and_false(self):
        """Ловит мутацию: отсутствующий файл лога роняет исключение вместо
        деградации до `({}, False)`."""
        tokens, saw = spend.partial_tokens_from_log(
            self.log_path.parent / "nope.log")

        self.assertEqual(tokens, {})
        self.assertFalse(saw)

    def test_result_event_in_log_counts_too(self):
        """Ловит мутацию: разбор лога учитывает только `assistant`-события,
        игнорируя usage финального `result`-события."""
        self.write([result_event(usd=0.5, usage={"input_tokens": 7,
                                                  "output_tokens": 3})])

        tokens, saw = spend.partial_tokens_from_log(self.log_path)

        self.assertEqual(tokens, {"input": 7, "output": 3})
        self.assertTrue(saw)


class PumpCostTest(TmpRootTest):
    """Перекачка снимает стоимость с потока — в файл лога она не попадает."""

    def pump(self, lines, log_path=None) -> agent_log.OutputPump:
        pump = agent_log.OutputPump(iter(lines),
                                log_path or agent_log.new_agent_log("T007", "developer"))
        with redirect_stdout(io.StringIO()):
            pump.start()
            pump.join(5)
        return pump

    def test_cost_is_caught_from_the_stream(self):
        pump = self.pump(["работаю\n", result_event(usd=0.25)])

        self.assertEqual(pump.cost["usd"], 0.25)

    def test_cost_event_does_not_reach_the_log(self):
        log = agent_log.new_agent_log("T007", "developer")

        self.pump(["работаю\n", result_event(usd=0.25)], log)

        self.assertEqual(log.read_text(encoding="utf-8"), "работаю\n",
                         "служебное событие Оператору в логе не нужно")

    def test_last_result_wins(self):
        pump = self.pump([result_event(usd=0.1), result_event(usd=0.9)])

        self.assertEqual(pump.cost["usd"], 0.9, "итог запуска — последний")

    def test_cost_is_caught_even_when_log_is_not_writable(self):
        unreachable = config.LOGS / "нет-такого-каталога" / "шаг.log"

        pump = self.pump([result_event(usd=0.25)], unreachable)

        self.assertIsInstance(pump.error, OSError)
        self.assertEqual(pump.cost["usd"], 0.25,
                         "деньги потрачены независимо от того, записан ли лог")

    def test_stream_without_cost_leaves_none(self):
        self.assertIsNone(self.pump(["просто вывод\n"]).cost)

    def test_partial_tokens_are_summed_across_events_by_type(self):
        """Ловит мутацию: `OutputPump.partial_tokens` схлопывает несколько
        usage-событий потока в одно число вместо накопления по видам."""
        pump = self.pump([
            assistant_event(usage={"input_tokens": 10, "output_tokens": 5}),
            "просто текст, не usage-событие\n",
            assistant_event(usage={"input_tokens": 20, "output_tokens": 8}),
        ])

        self.assertEqual(pump.partial_tokens, {"input": 30, "output": 13})
        self.assertTrue(pump.saw_usage_event)

    def test_no_usage_events_leaves_partial_tokens_empty(self):
        """Ловит мутацию: `partial_tokens` остаётся не словарём (например,
        просто `0`) при отсутствии usage-событий — ломает `.get()`
        вызывающего кода вместо честного пустого словаря."""
        pump = self.pump(["просто вывод, ни одного usage-события\n"])

        self.assertEqual(pump.partial_tokens, {})
        self.assertFalse(pump.saw_usage_event,
                         "0 токенов не должен выглядеть как «usage видели»")

    def test_partial_tokens_are_kept_even_when_result_arrives(self):
        """Финальное событие пришло — частичные токены всё равно посчитаны:
        решение, использовать ли их, принимает вызывающий код.

        Ловит мутацию: накопление токенов обрывается на первом же итоге
        запуска — шаг, чей поток продолжился после него, теряет часть
        своего usage, и учёт оборванной попытки считается по остатку."""
        pump = self.pump([
            assistant_event(usage={"input_tokens": 10, "output_tokens": 5}),
            result_event(usd=0.5, usage={"input_tokens": 15, "output_tokens": 9}),
        ])

        self.assertEqual(pump.cost["usd"], 0.5)
        self.assertEqual(pump.partial_tokens, {"input": 25, "output": 14})


class ChargeMissingResultTest(TmpRootTest):
    """`spend.charge_missing_result` — учёт попытки без финального события
    потока (tasks/T040, курс токенов — SPEC 01M1NWCM3TDY0YABEKE8DYQA1C):
    разрешимый тариф модели роли прибавляет частичную сумму
    к `spent_usd`; курс не задан — верхняя оценка в `spent_estimate_usd` и
    алерт `kind=threshold`; ни одного usage-события вовсе — `spent_usd`/
    `spent_estimate_usd` не трогаются, алерт `kind=incident`."""

    def setUp(self):
        super().setUp()
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        # `cmd_new` возвращает id ULID (SPEC T094, требование 2), больше не
        # предсказуемый "T001" — забираем реальный через
        # `capture_new_task_id`, а не `self.capture` (та отбрасывает возврат).
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Учёт стоимости без финального события")

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def journal(self) -> list[tuple[str, str, str]]:
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT * FROM steps WHERE task_id=? ORDER BY id", (self.TASK,))]

    def unknown_cost_alerts(self) -> list:
        return store.db().execute(
            "SELECT * FROM alerts WHERE kind='incident' AND "
            "source='spend.unknown_cost'").fetchall()

    def test_partial_tokens_are_journaled_without_touching_spent(self):
        """Имя метода унаследовано от T040 — ANSWER-2.md (эскалация AC-1/
        AC-2 задачи 01M1NWCM3TDY0YABEKE8DYQA1C, вариант A) переписывает его
        ожидание на ПРОТИВОПОЛОЖНОЕ: роль `developer` теперь несёт курс
        токенов (тариф модели её яруса), и частичная сумма по тарифу
        прибавляется к `spent_usd`, а не остаётся в стороне (решение
        Оператора, ADR-0002 — правка локнутого теста санкционирована этим
        же ANSWER).

        Ловит мутацию: разработчик оставляет прежнее поведение T040 без
        цены для `developer` — `assertGreater` ниже упадёт на 0.0.
        """
        conn = store.db()

        spent = spend.charge_missing_result(
            conn, self.TASK, "developer", "попытка 1/3", "таймаут шага",
            partial_tokens={"input_tokens": 150}, saw_usage_event=True)

        self.assertGreater(self.task_row()["spent_usd"], 0.0)
        self.assertIn("150", spent)
        self.assertIn("$", spent)
        actions = [(a, action) for a, action, _ in self.journal()]
        self.assertIn(("developer", "agent cost PARTIAL"), actions)
        detail = self.journal()[-1][2]
        self.assertIn("частичная стоимость по тарифу", detail)
        self.assertIn("150", detail)
        self.assertIn("таймаут шага", detail)
        self.assertEqual(self.unknown_cost_alerts(), [],
                         "известный курс — алерт неизвестной стоимости не заводится")

    def test_unrecoverable_cost_journals_and_raises_an_alert(self):
        conn = store.db()

        spent = spend.charge_missing_result(
            conn, self.TASK, "developer", "попытка 1/3", "обрыв stdout-пайпа",
            partial_tokens={}, saw_usage_event=False)

        self.assertEqual(self.task_row()["spent_usd"], 0.0)
        self.assertEqual(spent, "")
        detail = self.journal()[-1][2]
        self.assertIn("стоимость шага неизвестна", detail)
        self.assertIn("обрыв stdout-пайпа", detail)
        found = self.unknown_cost_alerts()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["kind"], "incident")
        self.assertEqual(found[0]["source"], "spend.unknown_cost")
        self.assertIn(self.TASK, found[0]["message"])

    def test_repeated_identical_failure_does_not_duplicate_the_alert(self):
        conn = store.db()

        for _ in range(2):
            spend.charge_missing_result(
                conn, self.TASK, "developer", "попытка 1/3", "таймаут шага",
                partial_tokens={}, saw_usage_event=False)

        self.assertEqual(len(self.unknown_cost_alerts()), 1,
                         "дедуп alerts.raise_alert не даёт повторам плодить копии")

    def test_known_rate_charge_matches_partial_cost_usd(self):
        """Сумма, прибавленная к `spent_usd`, — ровно та, что считает
        `spend.partial_cost_usd` по той же роли и числу токенов: одна
        формула на обе точки (учёт и отображение), не две рассинхронные.

        Ловит мутацию: `charge_missing_result` считает частичную сумму
        своей отдельной формулой (например, только по цене входного
        токена, без среднего) вместо вызова `partial_cost_usd` — тогда
        `assertAlmostEqual` ниже разойдётся с независимо посчитанным
        `expected`."""
        conn = store.db()
        tokens = {"input_tokens": 1000}

        spend.charge_missing_result(
            conn, self.TASK, "developer", "попытка 1/3", "таймаут шага",
            partial_tokens=tokens, saw_usage_event=True)

        expected = spend.partial_cost_usd("developer", tokens)
        self.assertAlmostEqual(self.task_row()["spent_usd"], expected)

    def test_unknown_rate_role_credits_the_estimate_and_raises_threshold_alert(self):
        """Роль, чей тариф не разрешается (`verifier`, `executor: none`, яруса
        не имеет), не может получить частичную сумму по тарифу — вместо неё
        верхняя оценка в `spent_estimate_usd` и алерт `kind=threshold`,
        `spent_usd` не тронут.

        Ловит мутацию: `charge_missing_result` при неизвестном курсе
        всё равно прибавляет что-то к `spent_usd` (или не заводит
        алерт `threshold`) — тогда `row["spent_usd"]` окажется
        ненулевым, либо список `threshold_alerts` будет пуст."""
        conn = store.db()

        spend.charge_missing_result(
            conn, self.TASK, "verifier", "попытка 1/3", "обрыв stdout-пайпа",
            partial_tokens={"input_tokens": 42}, saw_usage_event=True)

        row = self.task_row()
        self.assertEqual(row["spent_usd"], 0.0)
        self.assertAlmostEqual(row["spent_estimate_usd"],
                               config.STEP_COST_ESTIMATE_USD)
        threshold_alerts = store.db().execute(
            "SELECT * FROM alerts WHERE kind='threshold'").fetchall()
        self.assertEqual(len(threshold_alerts), 1)
        self.assertIn("42", threshold_alerts[0]["message"])
        detail = self.journal()[-1][2]
        self.assertIn("верхняя оценка стоимости шага", detail)


class PartialCostUsdTest(unittest.TestCase):
    """`spend.partial_cost_usd` — тариф модели роли -> доллары по разбивке
    usage, без БД (SPEC 01M1NWCM3TDY0YABEKE8DYQA1C, требование 1-2;
    разбивка по видам — 01M1PP0VYRT55WN8GGVG66X89Y требование 2; тариф на
    модель — 01M300A14KRHCFB0DQXVCBJEKF, требование 1).

    Роль берётся боевая (`developer`, ярус которой ведёт на модель
    каталога репозитория): таблицы курса по роли, из которой прежняя
    версия этих тестов брала «любую роль с курсом», больше нет."""

    ROLE = "developer"

    def test_known_role_returns_a_positive_amount_proportional_to_tokens(self):
        """Ловит мутацию: `partial_cost_usd` возвращает фиксированную
        цену тарифа, не умноженную на количество токенов вида (например,
        забывает `*`) — тогда `double` останется равным `single`, а не
        удвоится."""
        single = spend.partial_cost_usd(self.ROLE, {"input_tokens": 1000})
        double = spend.partial_cost_usd(self.ROLE, {"input_tokens": 2000})

        self.assertGreater(single, 0.0)
        self.assertAlmostEqual(double, single * 2)

    def test_zero_tokens_is_zero_cost_even_with_a_known_rate(self):
        """Ловит мутацию: `partial_cost_usd` трактует нулевую разбивку
        как «тариф не разрешён» (например, `if not tokens_by_type: return
        None`) — тогда функция вернёт `None` вместо честного 0.0 для
        роли с разрешимым тарифом."""
        zero = {k: 0 for k in config.USAGE_TOKEN_KEYS}

        self.assertEqual(spend.partial_cost_usd(self.ROLE, zero), 0.0)

    def test_unknown_role_returns_none(self):
        """Ловит мутацию: `partial_cost_usd` возвращает 0.0 вместо
        `None` для роли, чей тариф не разрешается, — тогда
        `charge_missing_result` принял бы отсутствие тарифа за
        «стоимость нулевая» и молча начислил 0.0 в `spent_usd`, минуя
        ветку верхней оценки/алерта (требование 3)."""
        self.assertIsNone(spend.partial_cost_usd(
            "no-such-role", {"input_tokens": 1000}))


class ByPriceKindTest(unittest.TestCase):
    """`spend.by_price_kind` — приведение разбивки к общим видам цены
    (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требования 1 и 7).

    Углы, которых приёмочная планка задачи не закрывает: она сверяет
    две формы имён ПОРОЗНЬ, а живой журнал после мержа смешанный, и
    чужие поля usage в нём тоже встречаются."""

    def test_both_name_forms_of_one_kind_are_summed_not_shadowed(self):
        """Прежнее и общее имя ОДНОГО вида в одной разбивке
        складываются.

        Ловит мутацию: приведение построено словарём-перезаписью
        (`{kinds.get(k, k): v for ...}`) — при обеих формах в одной
        строке половина токенов молча затирается второй, и шаг
        тарифицируется по части своего объёма.
        """
        self.assertEqual(
            spend.by_price_kind({"input_tokens": 10, "input": 5}),
            {"input": 15})

    def test_foreign_usage_fields_do_not_become_kinds(self):
        """Чужое поле usage видом цены не становится.

        Ловит мутацию: приведение пропускает любой ключ как есть — в
        разбивку попадает `server_tool_use`, и первая же попытка
        тарифицировать её падает `AttributeError` на тарифе, у которого
        такого поля нет.
        """
        self.assertEqual(
            spend.by_price_kind({"server_tool_use": 3, "output_tokens": 7}),
            {"output": 7})


class CostFromCliFlagTest(unittest.TestCase):
    """Признак каталога `cost_from_cli` на пути учёта шага (SPEC
    01M31ZHSA6HMH40C2JTDPQJQNZ, требование 4): его деградацию планка не
    проверяет — она гоняет обе ветки на исправном каталоге."""

    def test_unknown_model_keeps_the_cli_fact_path(self):
        """Модель, которой в каталоге нет (и строка без поля `model=`),
        считается «цену сообщает CLI» — прежний путь.

        Ловит мутацию: неизвестная модель деградирует в «цену не
        сообщает» — КАЖДЫЙ шаг, чья строка не назвала модель, уходит на
        расчёт по тарифу, и `spent_usd` тихо расходится с фактическим
        счётом провайдера на всём старом формате записей.
        """
        self.assertTrue(spend._cost_from_cli(None))
        self.assertTrue(spend._cost_from_cli("model-kotoroy-net"))

    def test_unreadable_catalog_keeps_the_cli_fact_path(self):
        """Каталог не читается — учёт шага не падает вместе с ним и
        остаётся на прежнем пути.

        Ловит мутацию: `ModelsError` разбора каталога летит наружу из
        точки учёта — шаг, который уже отработал и потратил деньги,
        роняет `cmd_run` трейсбеком вместо записи о стоимости.
        """
        with mock.patch.object(spend.models, "catalog_model",
                               side_effect=spend.models.CatalogError("битый")):
            self.assertTrue(spend._cost_from_cli("claude-opus-5"))


class ChargeByTariffTest(TmpRootTest):
    """`spend.charge_step` без цены от CLI — расчёт по тарифу (SPEC
    01M31ZHSA6HMH40C2JTDPQJQNZ, требования 4, 6).

    Планка задачи проверяет сам путь через `runner.cmd_run`; здесь —
    два угла, которые она не называет: строка расчёта не входит в
    калибровку тарифа, и итог без разбивки токенов не проходит молча."""

    ROLE = "developer"

    def setUp(self):
        super().setUp()
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Расчёт по тарифу")
        self.conn = store.db()
        self.model = spend.role_tariff(self.ROLE).model

    def numbered(self) -> str:
        return (f"попытка 1/3, model={self.model}, "
                f"provider={providers.DEFAULT_PROVIDER}")

    def priceless(self, tokens_by_type) -> dict:
        """Итог запуска, полученный БЕЗ цены от CLI."""
        return {"usd": None,
                "tokens": sum(tokens_by_type.values()) if tokens_by_type else None,
                "tokens_by_type": tokens_by_type}

    def details(self, action: str) -> list:
        return [row["detail"] for row in store.task_steps(self.conn, self.TASK)
                if row["action"] == action]

    def test_the_calculated_line_stays_out_of_the_tariff_calibration(self):
        """Строка расчёта по тарифу не несёт `actual_usd=` и в пары
        сверки курса не входит.

        Ловит мутацию: ветка расчёта пишет строку тем же составом
        полей, что и факт CLI, — расчёт по тарифу входит в калибровку
        как «факт», тариф начинает подтверждать сам себя, и
        коэффициент расхождения навсегда показывает ноль независимо от
        реального счёта.
        """
        spend.charge_step(self.conn, self.TASK, self.ROLE,
                          self.priceless({"input": 1000, "output": 500,
                                          "cache_write": 10, "cache_read": 20}),
                          self.numbered())

        detail = self.details(spend.KNOWN_COST_JOURNAL_ACTION)[-1]
        self.assertIn("источник=расчёт по тарифу", detail)
        self.assertNotIn("actual_usd=", detail)
        self.assertEqual(spend.known_cost_breakdown(detail), (None, None))
        self.assertEqual(spend.known_cost_pairs(self.conn), {})

    def test_a_run_result_without_any_usage_is_journaled_and_alerted(self):
        """Итог запуска без цены И без разбивки токенов: списывать
        нечего — именованная запись и алерт, а не тихий ноль.

        Ловит мутацию: пустая разбивка проходит в расчёт — тариф от
        нуля токенов даёт $0.0000, шаг выглядит учтённым за ноль, и
        недоучёт копится ровно там, где о нём никто не спросит.
        """
        spend.charge_step(self.conn, self.TASK, self.ROLE,
                          self.priceless(None), self.numbered())

        row = store.db().execute("SELECT * FROM tasks WHERE id=?",
                                 (self.TASK,)).fetchone()
        self.assertEqual(row["spent_usd"], 0.0)
        self.assertEqual(self.details(spend.KNOWN_COST_JOURNAL_ACTION), [])
        self.assertEqual(len(self.details(spend.UNCHARGED_COST_JOURNAL_ACTION)),
                         1)
        self.assertTrue(store.db().execute(
            "SELECT * FROM alerts WHERE source='spend.step_cost_uncharged'"
        ).fetchall())


class CmdRunCostTest(TmpRootTest):
    """`run` считает деньги: журнал шага, spent_usd, реакция на потолок."""

    def setUp(self):
        super().setUp()
        # Шаг ревью собирает пакет настоящим git (T011); в песочнице
        # репозитория нет, а этому модулю важны деньги шага, не diff.
        # Патчится ДО `cmd_new` (SPEC T048): он сам заводит ветку/worktree
        # через `gitcmd`, и без фейка ушёл бы в РЕАЛЬНЫЙ репозиторий пульта.
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        # `cmd_new` возвращает id ULID (SPEC T094, требование 2), больше не
        # предсказуемый "T001" — забираем реальный через
        # `capture_new_task_id`, а не `self.capture` (та отбрасывает возврат).
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Учёт стоимости шага")
        sync_spec_from_worktree(self.TASK)
        self.set_task(state="in_dev")
        # Обязательный артефакт роли developer (SPEC 01M1RQ12JVHE3PQYDFV1XPSTQ3,
        # требование 3) — без него на диске рабочего каталога роли успешная
        # попытка (rc=0) честно ретраится вместо одного тихого прогона,
        # которого ждут тесты этого класса (они проверяют учёт денег, не
        # факт отказа без артефакта).
        tdir = config.WORKTREES / self.TASK / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text("маркер\n", encoding="utf-8")

        patcher = mock.patch.object(runner.time, "sleep", lambda _: None)
        patcher.start()
        self.addCleanup(patcher.stop)

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def set_task(self, **fields) -> None:
        conn = store.db()
        assignments = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                     (*fields.values(), self.TASK))
        conn.commit()

    def run_agent(self, *attempts) -> str:
        """attempts: (rc, строки вывода) — по одной паре на попытку."""
        procs = [FakeProc(lines, rc) for rc, lines in attempts]
        with mock.patch.object(runner, "spawn_agent", side_effect=procs) as popen:
            out = self.capture(runner.cmd_run, self.TASK)
        self.popen = popen
        return out

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def test_step_cost_lands_in_spent_and_journal(self):
        out = self.run_agent((0, [result_event(
            usd=0.25, usage={"input_tokens": 100, "output_tokens": 20})]))

        self.assertAlmostEqual(self.task_row()["spent_usd"], 0.25)
        detail = self.journal_details("agent run finished")[0]
        self.assertIn("стоимость $0.2500", detail)
        self.assertIn("токенов 120", detail)
        self.assertIn("стоимость $0.2500", out, "цена шага видна Оператору сразу")

    def test_costs_accumulate_over_steps(self):
        self.run_agent((0, [result_event(usd=0.25)]))
        self.run_agent((0, [result_event(usd=0.5)]))

        self.assertAlmostEqual(self.task_row()["spent_usd"], 0.75)

    def test_step_friction_lands_in_journal_from_the_live_stream(self):
        """tasks/T095/SPEC.md, вариант 4б: трение считается по СЫРЫМ
        событиям потока (не по персистентному рендер-логу) и журналируется
        точкой завершения шага (`runner.py`) сразу же."""
        self.run_agent((0, [
            tool_use_event("t1", "Read", file_path="a.py"),
            tool_use_event("t2", "Read", file_path="a.py"),
            result_event(usd=0.1),
        ]))

        detail = self.journal_details(agent_log.FRICTION_JOURNAL_ACTION)
        self.assertEqual(len(detail), 1, "трение шага не попало в журнал")
        self.assertEqual(float(detail[0]), 0.5)

    def test_step_friction_is_journaled_even_for_a_clean_step(self):
        self.run_agent((0, [
            tool_use_event("t1", "Read", file_path="a.py"),
            result_event(usd=0.1),
        ]))

        detail = self.journal_details(agent_log.FRICTION_JOURNAL_ACTION)
        self.assertEqual(float(detail[0]), 0.0)

    def test_failed_attempts_are_paid_for_too(self):
        """Ретраи после T006 стоят денег — иначе потолок обходится провалами."""
        self.set_task(budget_usd=10.0)

        self.run_agent(*[(1, [result_event(usd=0.2)])] * config.AGENT_ATTEMPTS)

        self.assertAlmostEqual(self.task_row()["spent_usd"],
                               0.2 * config.AGENT_ATTEMPTS)
        self.assertIn("стоимость $0.2000", self.journal_details("agent run FAILED")[0])

    def test_missing_cost_is_warned_but_step_survives(self):
        out = self.run_agent((0, ["агент отработал без события стоимости\n"]))

        self.assertEqual(self.task_row()["spent_usd"], 0.0, "нечего прибавлять")
        self.assertEqual(self.task_row()["state"], "in_dev", "шаг не провален")
        self.assertIn("developer завершил (rc=0)", out)
        self.assertEqual(self.journal_details("agent cost UNKNOWN"),
                         [f"попытка 1/{config.AGENT_ATTEMPTS}: в выводе нет "
                          f"события со стоимостью — spent_usd не изменён"])
        finished = self.journal_details("agent run finished")
        self.assertEqual(len(finished), 1)
        self.assertTrue(
            finished[0].startswith(f"rc=0, попытка 1/{config.AGENT_ATTEMPTS}, "),
            finished[0])

    def test_status_and_log_show_the_money(self):
        """Критерий приёмки 1: ненулевой spent_usd в status, цена шага в log."""
        self.set_task(budget_usd=5.0)

        self.run_agent((0, [result_event(usd=0.25)]))

        self.assertIn("$0.25/5.00", self.capture(catalog.cmd_status))
        self.assertIn("стоимость $0.2500", self.capture(catalog.cmd_log, self.TASK))

    def test_warning_at_seventy_percent(self):
        self.set_task(budget_usd=1.0)

        out = self.run_agent((0, [result_event(usd=0.7)]))

        self.assertIn("ВНИМАНИЕ", out)
        self.assertIn("больше 70% бюджета",
                      self.journal_details("бюджет: предупреждение")[0])
        self.assertEqual(self.task_row()["state"], "in_dev", "70% — не блокировка")

    def test_no_warning_below_the_threshold(self):
        self.set_task(budget_usd=1.0)

        out = self.run_agent((0, [result_event(usd=0.69)]))

        self.assertNotIn("ВНИМАНИЕ", out)
        self.assertEqual(self.journal_details("бюджет: предупреждение"), [])

    def test_exhausted_budget_escalates_the_task(self):
        self.set_task(budget_usd=0.3)

        out = self.run_agent((0, [result_event(usd=0.5)]))

        row = self.task_row()
        self.assertEqual(row["state"], "escalated")
        self.assertEqual(row["escalated_from"], "in_dev", "вернуться надо в шаг")
        self.assertIn("бюджет исчерпан",
                      self.journal_details("state -> escalated")[0])
        self.assertIn(f"artel.py budget {self.TASK}", out, "видно, чем разблокировать")

    def test_exhausted_budget_stops_the_retries(self):
        """Потолок пробит первой же попыткой — остальные не запускаются."""
        self.set_task(budget_usd=0.3)

        self.run_agent((1, [result_event(usd=0.5)]))

        self.assertEqual(self.popen.call_count, 1)
        self.assertEqual(self.task_row()["state"], "escalated")

    def test_exhausted_review_step_remembers_its_state(self):
        self.set_task(state="review", budget_usd=0.3)

        self.run_agent((0, [result_event(usd=0.5)]))

        self.assertEqual(self.task_row()["escalated_from"], "review")

    def test_run_refuses_to_start_over_budget(self):
        """Критерий приёмки 2: повторный run не стартует и объясняет, почему."""
        self.set_task(budget_usd=0.3)
        self.run_agent((0, [result_event(usd=0.5)]))
        self.capture(fsm.cmd_approve, self.TASK)  # Оператор снял эскалацию

        with mock.patch.object(runner, "spawn_agent") as popen:
            with self.assertRaises(SystemExit) as exit_:
                self.capture(runner.cmd_run, self.TASK)

        self.assertEqual(popen.call_count, 0, "агент не запускается")
        self.assertIn("бюджет исчерпан", str(exit_.exception))
        self.assertIn(f"artel.py budget {self.TASK}", str(exit_.exception))

    def test_task_without_budget_is_not_blocked(self):
        """БД прошлых версий: budget_usd NULL — потолка нет, а не потолок 0."""
        self.set_task(budget_usd=None)

        out = self.run_agent((0, [result_event(usd=0.5)]))

        self.assertEqual(self.task_row()["state"], "in_dev")
        self.assertNotIn("бюджет исчерпан", out)


def timeout_then_killed_proc(lines) -> mock.Mock:
    """Процесс, чей `wait()` сперва бросает `TimeoutExpired` — таймаут шага
    без единого ретрая (см. `tests/test_agent_log.py::
    CmdRunLoggingTest.test_timeout_kills_process_and_journals`)."""
    proc = mock.Mock(stdout=FakeStream(lines))
    proc.wait.side_effect = [
        runner.subprocess.TimeoutExpired(cmd="claude", timeout=config.AGENT_TIMEOUT_SEC),
        -9,
    ]
    return proc


class CmdRunPartialCostTest(TmpRootTest):
    """`run` при таймауте, но с usage-событиями в потоке до обрыва (tasks/
    T040): частичная сумма токенов в журнале, `spent_usd` не меняется, алерт
    не заводится. Локальные приёмочные тесты T040 сознательно не фиксируют
    эту ветку числом (курс токена в доллары не задан) — здесь код всё равно
    обязан её реально проходить (skills/coding-standards: юнит-тесты — часть
    определения «сделано»)."""

    def setUp(self):
        super().setUp()
        # ДО `cmd_new` (SPEC T048) — сам заводит ветку/worktree через
        # `gitcmd`, без фейка ушёл бы в реальный репозиторий пульта.
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        # `cmd_new` возвращает id ULID (SPEC T094, требование 2), больше не
        # предсказуемый "T001" — забираем реальный через
        # `capture_new_task_id`, а не `self.capture` (та отбрасывает возврат).
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Частичная стоимость при таймауте")
        sync_spec_from_worktree(self.TASK)
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()

        patcher = mock.patch.object(runner.time, "sleep", lambda _: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def journal_text(self) -> str:
        rows = store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id", (self.TASK,)).fetchall()
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in rows)

    def unknown_cost_alerts(self) -> list:
        return store.db().execute(
            "SELECT * FROM alerts WHERE kind='incident' AND "
            "source='spend.unknown_cost'").fetchall()

    def test_timeout_with_usage_events_charges_a_partial_token_sum(self):
        """ANSWER-2.md (эскалация AC-1/AC-2 задачи
        01M1NWCM3TDY0YABEKE8DYQA1C, вариант A) переписывает ожидание этого
        теста на ПРОТИВОПОЛОЖНОЕ прежнему T040: роль `developer` (state
        `in_dev` этого сценария) теперь несёт курс токенов
        (тариф модели её яруса) — частичная сумма по тарифу прибавляется к
        `spent_usd`, а не остаётся в стороне (решение Оператора, ADR-0002).

        Ловит мутацию: разработчик оставляет прежнее поведение T040 без
        цены для `developer` — `assertGreater` ниже упадёт на 0.0.
        """
        proc = timeout_then_killed_proc([
            assistant_event(usage={"input_tokens": 100, "output_tokens": 50}),
            assistant_event(usage={"input_tokens": 40, "output_tokens": 10}),
        ])

        with mock.patch.object(runner, "spawn_agent", return_value=proc):
            out = self.capture(runner.cmd_run, self.TASK)

        self.assertGreater(self.task_row()["spent_usd"], 0.0)
        text = self.journal_text()
        self.assertIn("частичная стоимость по тарифу", text)
        self.assertIn("200", text)
        self.assertNotIn("стоимость шага неизвестна", text)
        self.assertEqual(self.unknown_cost_alerts(), [],
                         "usage-события были — алерт неизвестной стоимости не нужен")
        self.assertIn(
            f"таймаут шага ({config.AGENT_TIMEOUT_SEC // 60} мин)", out)


class CmdBudgetTest(TmpRootTest):
    """`budget <id> <usd>`: поднятие потолка и снятие блокировки."""

    def setUp(self):
        super().setUp()
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        # `cmd_new` возвращает id ULID (SPEC T094, требование 2), больше не
        # предсказуемый "T001" — забираем реальный через
        # `capture_new_task_id`, а не `self.capture` (та отбрасывает возврат).
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Потолок бюджета")

    def set_task(self, **fields) -> None:
        conn = store.db()
        assignments = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                     (*fields.values(), self.TASK))
        conn.commit()

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def journal(self) -> list[tuple[str, str, str]]:
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT * FROM steps WHERE task_id=? ORDER BY id", (self.TASK,))]

    def exhausted(self) -> None:
        """Задача, вставшая на исчерпанном бюджете."""
        self.set_task(state="escalated", escalated_from="in_dev",
                      budget_usd=0.3, spent_usd=0.5)

    def test_new_ceiling_is_saved_and_journaled(self):
        self.set_task(state="in_dev", budget_usd=5.0, spent_usd=1.0)

        out = self.capture(budget.cmd_budget, self.TASK, "12.5")

        self.assertAlmostEqual(self.task_row()["budget_usd"], 12.5)
        self.assertIn(("operator", "бюджет изменён",
                       "$5.00 -> $12.50, израсходовано $1.00"), self.journal())
        self.assertIn("$5.00 -> $12.50", out)

    def test_raised_ceiling_unblocks_the_task(self):
        """Критерий приёмки 2: после `budget` шаг продолжается."""
        self.exhausted()

        out = self.capture(budget.cmd_budget, self.TASK, "5")

        row = self.task_row()
        self.assertEqual(row["state"], "in_dev")
        self.assertIsNone(row["escalated_from"], "точка возврата одноразовая")
        self.assertIn(f"дальше: artel.py run {self.TASK}", out)
        self.assertIsNone(budget.budget_block(row))

    def test_unblocked_review_step_returns_to_review(self):
        self.exhausted()
        self.set_task(escalated_from="review")

        self.capture(budget.cmd_budget, self.TASK, "5")

        self.assertEqual(self.task_row()["state"], "review")

    def test_too_small_ceiling_keeps_the_block(self):
        self.exhausted()

        out = self.capture(budget.cmd_budget, self.TASK, "0.4")

        self.assertEqual(self.task_row()["state"], "escalated", "денег всё ещё нет")
        self.assertIn("этого мало", out)
        self.assertIn(("operator", "бюджет изменён",
                       "$0.30 -> $0.40, израсходовано $0.50"), self.journal(),
                      "в журнал пишется и неудачная попытка поднять потолок")

    def test_other_escalation_is_not_resolved_by_budget(self):
        """Эскалацию по провалу агента снимает approve, а не деньги."""
        self.set_task(state="escalated", escalated_from="review",
                      budget_usd=5.0, spent_usd=1.0)

        self.capture(budget.cmd_budget, self.TASK, "10")

        row = self.task_row()
        self.assertEqual(row["state"], "escalated")
        self.assertEqual(row["escalated_from"], "review", "точка возврата цела")

    def test_working_task_keeps_its_state(self):
        self.set_task(state="in_dev", spent_usd=1.0)

        self.capture(budget.cmd_budget, self.TASK, "10")

        self.assertEqual(self.task_row()["state"], "in_dev")

    def test_bad_amount_is_refused(self):
        for raw in ("", "дорого", "-5", "0", "nan", "inf"):
            with self.subTest(raw=raw):
                with self.assertRaises(SystemExit) as exit_:
                    self.capture(budget.cmd_budget, self.TASK, raw)
                self.assertIn("не сумма в долларах", str(exit_.exception))
        self.assertAlmostEqual(self.task_row()["budget_usd"],
                               config.DEFAULT_BUDGET_USD)

    def test_comma_is_accepted_as_decimal_separator(self):
        self.capture(budget.cmd_budget, self.TASK, "7,5")

        self.assertAlmostEqual(self.task_row()["budget_usd"], 7.5)

    def test_unknown_task_is_reported(self):
        with self.assertRaises(SystemExit) as exit_:
            self.capture(budget.cmd_budget, "T404", "10")

        self.assertIn("не найдена", str(exit_.exception))


if __name__ == "__main__":
    unittest.main()
