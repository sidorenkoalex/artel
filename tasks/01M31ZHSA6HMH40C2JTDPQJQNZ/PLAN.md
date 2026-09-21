---
task: 01M31ZHSA6HMH40C2JTDPQJQNZ
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
# Однократная переоценка потолка задачи (ADR-0014 часть 2) — раскомментируй,
# только если PLAN расходится с оценкой SPEC (по числу файлов/шагов), с
# обоснованием в «Влиянии на систему». Применяется один раз, только вверх,
# в пределах потолка ролей (ROLE_BUDGET_CAP).
# budget_usd: 25
---

# PLAN: Вывод, стоимость и провалы у провайдера

## Подход

Разбор вывода переезжает к провайдеру одним событием общего вида: одна
строка потока — один вызов `provider.parse_output_line(raw_line)` —
одно событие `StreamEvent`. Шесть точек требования 3 перестают знать
формат Claude и читают поля события.

**Событие общего вида** (`orchestrator/providers/base.py`, namedtuple'ы
уровня модуля — не члены класса, чтобы состав интерфейса не разъехался):

```
StreamEvent = (log_text, text, tool_calls, tool_results,
               tokens_by_type, run_result)
ToolCall    = (id, name, argument)
ToolResult  = (call_id, text, is_error)
RunResult   = (tokens_by_type, usd, is_error, text)
```

Пять предметов требования 1 разложены по полям так, чтобы КАЖДЫЙ был
отдельным (AC-1 требует, чтобы вызов инструмента и его результат не
слились в одно): `log_text` — готовая строка лога (формат строки знает
провайдер: и «· Read <файл>», и сквозной проброс не-JSON stderr —
провайдерское знание, а не общее); `text` — сам текст ассистента;
`tool_calls`/`tool_results` — вызовы и результаты; `tokens_by_type` —
учёт токенов ЛЮБОГО события; `run_result` — итог запуска.

Три решения по форме события:

- **Учёт токенов — по общим видам** `models.PRICE_KINDS` (AC-2).
  Отображение «счётчик Claude -> вид цены» (сегодня
  `spend._PRICE_KIND_FOR_USAGE_KEY`, до задачи дублировавшее
  `config.USAGE_TOKEN_KEYS`) остаётся в ОДНОМ адресе —
  `config.LEGACY_TOKEN_KIND_NAMES`: одни и те же четыре имени нужны и
  `ClaudeProvider` (разобрать поток), и `spend` (прочитать строку
  журнала, записанную до задачи, требование 7). Две копии разошлись бы
  на первой же правке.
- **`usd = None` отличимо от `usd = 0.0`** (AC-3): бесплатный запуск и
  запуск провайдера, который цену не сообщает, — разные события, и
  требование 4 ветвится ровно по этому различию.
- **`run_result.text` несёт текст итога и для успеха, и для ошибки** —
  это одно поле потока (`result`), признак ошибки отдельным `is_error`.

**Стоимость без цены от CLI.** `spend.parse_cost_event` КОНТРАКТ НЕ
МЕНЯЕТ (`None`, когда пригодной цены нет) — её зовёт
`orchestrator/doctor/live_smoke.py:79` (вне зоны, «обязан продолжать
работать без правки») и форматирует `cost['usd']:.4f`. Вместо этого
заводится `spend.parse_run_result`, отдающая словарь ВСЕГДА, когда итог
запуска получен, с `usd=None` при отсутствии цены; `parse_cost_event`
становится её сужением. Так «итога запуска нет вовсе» (AC-10,
UNKNOWN/PARTIAL/ESTIMATED/LOST) и «итог есть, цены нет» (AC-9, расчёт по
тарифу) различает `OutputPump.cost is None`, а не новый флаг рядом с
ним.

`charge_step` ветвится: цена есть И `cost_from_cli` модели шага истинен
-> прежний путь факта CLI; иначе -> расчёт по тарифу. Признак берётся
записью каталога модели ШАГА (`models.catalog_model(...).cost_from_cli`),
а не провайдером роли: требование 4 говорит «провайдер МОДЕЛИ шага».
Саму модель `charge_step` получает ПАРАМЕТРОМ от `runner._account_step`,
который держит её на руках (итерация 2, R1-F2): восстановление модели
разбором собственной строки `numbered` не годится — `model=` туда
приписывается только у записей KNOWN/PARTIAL (требование 6 SPEC
01M2DTT96FS25SHXP0HDTWARQH), и итог запуска без разбивки токенов остался
бы без признака, то есть списался бы ценой, которую каталог объявил
недостоверной. Прямые вызовы `charge_step` без параметра (их много —
SPEC T040, требование 4) сохраняют прежний разбор строки через часовой
`_MODEL_FROM_NUMBERED`; «модель шага не разрешилась» — законное значение
параметра и с «параметр не передан» не путается. Строка расчёта по
тарифу НЕ несёт `actual_usd=` — иначе расчёт попал бы в сверку курса под
видом факта CLI и отравил калибровку.

**Порог программы считает списанные деньги, а не цену итога** (итерация
2, R1-F1). `runner._program_cost` отдаёт `budget.check_program_spend`
разность `spent_usd` до и после шага БЕЗУСЛОВНО. Порог не сравнивает
суммы, а восстанавливает «до шага» вычитанием переданного числа
(`budget.py:250-256`), поэтому любое расхождение с фактом списания и
выдумывает пересечение порога, и прячет настоящее — а дедуп алерта
`budget.program_spend` не даёт пропущенному всплыть на следующем шаге.
На пути факта CLI число прежнее (`store.charge` прибавляет ровно
`cost["usd"]`), на пути расчёта по тарифу — расчёт, а не цена CLI.

**Классы провалов.** Набор классов, их подписи, связка транзиентных,
алерты и обрыв повторов остаются в
`orchestrator/failure_classification.py`. К провайдеру уезжают только
тексты: `failure_signatures()` отдаёт упорядоченный кортеж
`FailureSignature(failure_class, signatures)` — порядок и есть сегодняшнее
«специфичные списки раньше общего якоря», он часть данных, а не кода
классификатора; `required_cli_version(text)` — извлечение требуемой
версии CLI.

**Совместимость журнала** (требование 7): разбор строки KNOWN принимает
обе формы имён видов и нормализует их к общим видам, поэтому одинаковые
числа дают одинаковую разбивку независимо от формы записи. Тарификация
(`tariff_cost_usd`) и запись разбивки (`_tokens_by_type_text`) тоже
принимают обе формы — иначе прямые вызовы `charge_step`/
`charge_missing_result` с прежними именами (существующие тесты, живой
`pause --now` на логе до мержа) молча считали бы ноль.

**Бюджет.** PLAN согласен с рамкой SPEC ($45), поле `budget_usd` не
раскомментировано: аналитик уже посчитал восемь элементов зон и принял
решение осознанно, а однократный канал переоценки разумнее оставить
неизрасходованным. Расхождение с калибровкой отмечено в «Рисках».

## Шаги

Один MR (Фаза 0). Ниже — единицы, каждая из которых проверяется своим
набором тестов; порядок — порядок коммита.

1. **Событие общего вида в интерфейсе.**
   `orchestrator/providers/base.py`: namedtuple'ы `StreamEvent`,
   `ToolCall`, `ToolResult`, `RunResult`, `FailureSignature` уровня
   модуля; три новых члена `RoleExecutorProvider` —
   `parse_output_line(raw_line)`, `failure_signatures()`,
   `required_cli_version(text)`, все три телом `NotImplementedError`,
   как остальные методы интерфейса.
   `orchestrator/providers/__init__.py`: `or_default(provider=None)` —
   один адрес деградации «провайдер не передан -> провайдер по
   умолчанию» вместо трёх копий тернарника в `agent_log`/`spend`/
   `failure_classification`.
   `orchestrator/config.py`: `LEGACY_TOKEN_KIND_NAMES` (счётчик Claude ->
   вид цены), `USAGE_TOKEN_KEYS` остаётся кортежем его ключей — внешние
   читатели константы не ломаются.

2. **`ClaudeProvider` реализует разбор.**
   `orchestrator/providers/claude.py`: `parse_output_line` собирает
   `StreamEvent` из `--output-format stream-json`. Тела переносятся
   дословно из `agent_log.render_block`/`render_agent_line`/
   `_parse_stream_event`/`_tool_use_calls`/`_tool_results` и
   `spend.usage_tokens_by_type`/`parse_cost_event`/
   `stream_usage_by_type` — ни один символ строки лога и ни одно число
   не меняются (AC-4, AC-5, AC-7). Плюс `failure_signatures()` и
   `required_cli_version()` с сигнатурами байт-в-байт из
   `failure_classification` (требование 10).

3. **Шесть точек — через провайдера.**
   `orchestrator/agent_log.py`: `render_agent_line(raw_line,
   provider=None)`, `tee_lines`/`stream_to_log` получают `provider` и
   разбирают строку ОДИН раз, отдавая `sink` уже событие;
   `OutputPump.__init__(stream, log_path, provider=None)`,
   `catch_cost` -> `catch_event(event)`; `_friction_from_events`
   считает по `StreamEvent`, `step_friction(log_path, provider=None)`.
   `render_block`, `_parse_stream_event`, `_tool_use_calls`,
   `_tool_results` уезжают в провайдера целиком (внешних читателей
   нет — проверено grep'ом по `orchestrator/`, `scripts/`, `tests/`).
   `orchestrator/spend.py`: `parse_run_result`/`parse_cost_event`/
   `stream_usage_by_type`/`partial_tokens_from_log` получают
   `provider=None`; `usage_tokens_by_type`/`step_tokens` уезжают в
   провайдера (внешних читателей нет).
   `orchestrator/runner.py`: `OutputPump` создаётся с
   `providers.for_role(role)`.

4. **Стоимость по тарифу и поле `provider=`.**
   `orchestrator/spend.py`: ветвление `charge_step(…, model_id)` (факт
   CLI против расчёта по тарифу; модель шага — параметром от
   `runner._account_step`, часовой `_MODEL_FROM_NUMBERED` сохраняет
   прежний путь прямых вызовов), `_cost_from_cli(model_id)` с
   деградацией в «истина» на нечитаемом каталоге/неизвестной модели
   (сегодняшний путь), именованная запись
   `UNCHARGED_COST_JOURNAL_ACTION` + алерт `kind=threshold` на «тариф не
   разрешён / разбивки нет» (AC-11); текст записи и алерта собирают
   `_tariff_path_cause` (почему считаем по тарифу — цены нет против
   `cost_from_cli: false`) и `_uncharged_reason` (почему не посчитали —
   тариф модели против тарифа модели РОЛИ).
   `orchestrator/runner.py`: `_numbered_with_model` приписывает
   `provider=` рядом с `model=` (AC-13); `budget.check_program_spend`
   получает РЕАЛЬНО списанную сумму (`_program_cost` — разность
   `spent_usd` до и после шага, безусловно), а `budget.py` вне зоны и
   обязан работать без правки.

5. **Классификация по сигнатурам провайдера.**
   `orchestrator/failure_classification.py`: `classify_attempt_failure(
   text, provider=None)` и `required_cli_version(text, provider=None)`
   читают таблицу провайдера; `CLASS_LABELS`,
   `TRANSIENT_SYSTEM_CLASSES`, `MODEL_UNSUPPORTED_CLASS`, алерты и
   `_record_failure_classification` остаются на месте, последний
   разрешает провайдера по роли шага.
   `orchestrator/runner.py`: текст отказа «модель не поддерживается CLI»
   берёт и версию, и саму сигнатуру у провайдера роли.

6. **Совместимость журнала.**
   `orchestrator/spend.py`: `_TOKEN_FIELD_RE` собирается по ОБЕИМ формам
   имён и нормализует к общим видам; `known_cost_breakdown` отдаёт общие
   виды; `_tokens_by_type_text` пишет общие виды в порядке
   `models.PRICE_KINDS`; `tariff_cost_usd` нормализует вход.

7. **Документация и тесты.** `docs/stack.md` — абзац «Вывод и стоимость
   у провайдера». Тесты — раздел «Тесты» ниже.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 4 |
| 5 | 4 |
| 6 | 4 |
| 7 | 6 |
| 8 | 4 |
| 9 | 5 |
| 10 | 2, 5 |
| 11 | 7 |
| 12 | 7 |

## Тесты

Планка задачи (`tasks/<id>/acceptance_tests/`, 39 тестов) закрывает
AC-1..AC-15 целиком. Новые юнит-тесты `tests/` берут УГЛЫ, которых она
не называет — тем же приёмом, что `tests/test_parent_task_division.py`
(все — с заявкой мутации в докстринге):

- `tests/test_providers.py::OutputEventTest` — событие, несущее текст И
  вызов инструмента сразу (планка гоняет по одному блоку на событие);
  два РАЗНЫХ порядка предпочтения аргумента (`command`-first для строки
  лога, `file_path`-first для ключа сравнения вызовов) — отличие
  молчаливое, числа стоимости при нём верны; usage сообщения с
  нечитаемыми блоками; отрицательная цена как «цены нет»; таблица
  сигнатур не расширяет общий набор классов.
- `tests/test_step_cost.py` — `by_price_kind` на СМЕШАННОЙ разбивке
  (планка сверяет формы порознь) и на чужом поле usage; деградация
  `_cost_from_cli` на неизвестной модели и нечитаемом каталоге; строка
  расчёта по тарифу не входит в калибровку (`known_cost_pairs` её не
  берёт); итог без разбивки токенов -> `UNCHARGED` + алерт.
- `tests/test_agent_log.py` — провайдер с ПО-НАСТОЯЩЕМУ другим форматом
  строки (планка строит заглушку над `ClaudeProvider`): JSON Claude под
  ним — просто текст, а его собственный формат считается трением; плюс
  связка «вызов -> результат» по идентификатору, не по порядку.
- `tests/test_token_rate_divergence.py` — перекрытие имён двух форм
  (`input` — префикс `input_tokens`): разбор не должен находить общее
  имя внутри длинного счётчика.
- `tests/test_failure_classification.py` — класс провайдера вне
  `CLASS_LABELS` игнорируется; побеждает ПЕРВАЯ подошедшая запись
  таблицы.
- `tests/test_runner_role_model.py` — `provider=` рядом с `model=` не
  рвёт разбор поля модели; шаг, посчитанный по тарифу, двигает порог
  программы на реально списанную сумму.

Добавлено итерацией 2 (регрессии на замечания ревью, все — с заявкой
мутации в докстринге):

- `tests/test_runner_role_model.py::test_the_program_threshold_gets_the_
  charged_sum_not_the_cli_price` (R1-F1) — `cost_from_cli: false` И цена
  в итоге запуска: порог программы получает $0.0175 расчёта, а не $0.10
  цены CLI. Прежний тест той же ветки смотрел только случай «цены нет
  вовсе», где числа совпадали и подмена была не видна.
- `tests/test_runner_role_model.py::test_the_catalog_flag_is_read_by_the_
  step_model_without_usage` (R1-F2) — итог запуска с ценой и БЕЗ usage:
  признак каталога спрашивается по модели шага (`claude-opus-5`), а не
  по отсутствующему в строке полю `model=`; шаг уходит в `UNCHARGED` с
  алертом, `spent_usd` не двигается.
- `tests/test_step_cost.py::ChargeByTariffTest::test_the_step_model_comes_
  from_the_parameter_not_from_the_line` и `…::test_without_the_parameter_
  the_model_is_still_read_from_the_line` (R1-F2) — параметр побеждает
  строку, а его отсутствие оставляет прежний разбор `numbered` для
  прямых вызовов.
- `tests/test_step_cost.py::ChargeByTariffTest::test_the_uncharged_line_
  names_the_role_tariff_as_the_role_tariff` (R1-F4) — роль в тексте
  записи и алерта названа ролью, а не моделью.

Обновлённые ожидания существующих наборов (требование 12 SPEC называет
их перечислить; каждое — следствие требования, не ослабление):

| Файл, тест | Было | Стало | Почему |
|---|---|---|---|
| `test_step_cost.py::ParseCostEventTest` — `test_cost_and_tokens_are_taken_from_result_event`, `test_known_usage_counters_are_summed` | разбивка именами счётчиков Claude | разбивка общими видами | AC-2 |
| `test_step_cost.py::StreamUsageByTypeTest` — `test_assistant_event_usage_is_broken_down_by_type`, `test_result_event_usage_still_works` | то же | то же | AC-2 |
| `test_step_cost.py::PartialTokensFromLogTest` — `test_usage_events_are_summed_by_type`, `test_result_event_in_log_counts_too` | то же | то же | AC-2 |
| `test_step_cost.py::PumpCostTest` — `test_partial_tokens_are_summed_across_events_by_type`, `test_partial_tokens_are_kept_even_when_result_arrives` | то же | то же | AC-2: `partial_tokens` копятся из события общего вида |
| `test_agent_log.py::OutputPumpTest::test_partial_tokens_survive_a_broken_pipe` | то же | то же | AC-2 |
| `test_step_cost.py` — три теста выше без заявки мутации в докстринге (написаны до правила) | докстринга нет либо он без «Ловит мутацию:» | заявка дописана | гейт `in_dev -> verifying` требует её у КАЖДОГО изменённого теста |

Ассерты, значения и сценарии этих тестов не трогаются ничем, кроме имён
видов токенов; ни один тест не удаляется и не скипается. Ожидание
`parse_cost_event` на `result`-событии без пригодной цены (`None`)
менять НЕ пришлось: контракт функции сохранён намеренно (см. «Подход»),
а путь «итог есть, цены нет» читает новая `parse_run_result`.

Прогон в шаге (передним планом, с таймаутом, по модулям —
`skills/coding-standards.md`) — всё зелёное:

| Набор | Итог |
|---|---|
| планка задачи `acceptance_tests/` | 39 passed, 17 subtests |
| шесть файлов AC-15 + `test_runner_role_model`, `test_report`, `test_retro`, `test_pause`, `test_pause_now` | 322 passed, 39 subtests |
| `test_invariants`, `test_multitarget`, `test_multitarget_invariants`, `test_agent_failure`, `test_auto_cycle` | 205 passed, 257 subtests |
| `test_doctor`, `test_models`, `test_models_doctor`, `test_stack` и соседи | 366 passed, 245 subtests |

Итерация 2 (после правок R1-F1..R1-F4) — прогнаны наборы, которых
касаются `spend.charge_step`/`runner._program_cost`:

| Набор | Итог |
|---|---|
| планка задачи `acceptance_tests/` | 39 passed, 17 subtests |
| `test_step_cost`, `test_runner_role_model` | 73 passed, 23 subtests |
| `test_token_rate_divergence`, `test_model_tariffs`, `test_providers`, `test_agent_log`, `test_failure_classification`, `test_report`, `test_retro`, `test_pause`, `test_pause_now` | 254 passed, 16 subtests |
| `test_multitarget`, `test_multitarget_invariants`, `test_spec_budget`, `test_agent_failure` | 131 passed, 45 subtests |
| `test_invariants`, `test_program_spend_reseed`, `test_budget_live_lease_and_escalation`, `test_budget_calibration_table` | 93 passed, 219 subtests |

Полный набор `tests/` гоняет CI на пуш ветки.

## Влияние на систему

**Что затрагивается за пределами правки.** Вне зон остаются читатели
затронутых функций: `orchestrator/pause.py` (зовёт
`partial_tokens_from_log` и `charge_missing_result`),
`orchestrator/report.py` (`step_friction`, `known_cost_breakdown`,
`token_rate_divergence`), `orchestrator/retro.py` (разбор «agent run
finished»), `orchestrator/doctor/live_smoke.py` (`parse_cost_event`),
`orchestrator/budget.py` (`check_program_spend`). Все пять обязаны
работать без правки (SPEC «Не входит»), поэтому:

- каждая функция получает `provider` НЕОБЯЗАТЕЛЬНЫМ параметром с
  деградацией в провайдера по умолчанию — ни одна сигнатура не ломается;
- `parse_cost_event` сохраняет контракт «`None`, когда цены нет»,
  и `live_smoke` не получает `None` в `f"{cost['usd']:.4f}"`;
- `check_program_spend` получает сумму, реально списанную шагом, —
  на прежних путях это то же самое число, что и сегодня
  (`store.charge` прибавляет ровно `cost["usd"]`), то есть поведение
  порога программы не меняется;
- RETRO продолжает считать по «стоимость $X» строки «agent run
  finished»: путь расчёта по тарифу возвращает тот же хвост-заметку с
  суммой, а не пустую строку.

**Инварианты, гейты, лимиты рядом — и почему не ослабляются.**

- `tests/test_step_cost.py` помечен НЕОСЛАБЛЯЕМЫМ (ADR-0002, инвариант
  «потолок задачи = денежный бюджет»): ни один его ассерт о потолке,
  алерте 70% и блокировке `run` не трогается — правятся только имена
  видов токенов и разделение перечня «событий без стоимости».
- Недоучёт стоимости, ради которого заведены ветки PARTIAL/ESTIMATED/
  LOST, становится СТРОЖЕ, а не слабее: «итог запуска без цены» больше
  не уходит в тихий UNKNOWN с нулём, а модель без тарифа на новом пути
  получает именованную запись и алерт (AC-11) — тот же приём, что уже
  защищает `charge_missing_result`.
- Порог расхождения курса (`config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD`)
  и его математика (`check_rate_divergence`) не трогаются; путь расчёта
  по тарифу в сверку не входит намеренно — сверять расчёт с расчётом
  бессмысленно, а `actual_usd=` в его строке сделал бы это молча.
- Связка транзиентных классов, бэкофф, алерты «обрыв потока»/«session
  limit» и обрыв повторов у `model_unsupported` остаются в
  `failure_classification` дословно (AC-14).
- Защищённые пути (`models.yaml`, `roles.yaml`, `gates.yaml`,
  `skills/`, `templates/`, `.github/`) не правятся; приложений к PLAN
  нет.

**Как откатить.** Одним `git revert` merge-коммита задачи: правка
целиком в `orchestrator/` + `docs/stack.md` + `tests/`, схема БД не
меняется, миграций нет, формат строк журнала расширяется совместимо
(старые строки продолжают читаться — это и есть требование 7), поэтому
откат не оставляет нечитаемых данных ни в ту, ни в другую сторону.

**Карта кодовой базы** регенерируется тем же коммитом
(`python3 scripts/codebase_map.py`) — правятся `*.py` в `orchestrator/`
и `tests/`.

## Риски

- **Рамка ниже калибровки.** Правка вышла на 10 файлов кода/документации
  и 6 файлов тестов (+1418/−355 строк против прогноза 45 КиБ);
  калибровочная таблица для восьми и более файлов зон даёт уровень ~$85
  против рамки $45. Однократную переоценку не расходую
  (см. «Подход»), но если ревью пойдёт дальше двух итераций, потолок
  придётся поднимать Оператору командой `budget` — это ожидаемый исход,
  а не сбой.
- **Двойной разбор одной строки.** Ошибка здесь не видна глазом:
  `tee_lines` и `sink` сегодня разбирают строку независимо. Разбор
  сведён к одному вызову на строку, и `sink` получает уже событие —
  иначе «лог под заглушкой поменялся, а стоимость нет» (ровно то, что
  ловит AC-8) можно было бы получить случайно.
- **Имена видов в журнале меняются с этого мержа.** Журнал живого
  пульта станет смешанным с первого же шага. Риск закрыт требованием 7
  и AC-12; отдельно проверяю, что коллизий регулярных выражений между
  формами нет (`input=` не матчит `input_tokens=10` из-за
  `(?<![a-z_])` и обратно).
- **`pause --now` и `report` разбирают лог провайдером по умолчанию.**
  Пока провайдер один — поведение верное; с появлением второго обе точки
  станут читать чужой формат как Claude. Правка их вызовов — вне зон
  этой задачи (SPEC «Не входит»), поэтому вынесено в «Предложения
  системе» и ниже, как известный долг части 2.
- **`cost_from_cli` читается из каталога на каждом учёте шага.** Это
  чтение файла в точке учёта; деградация на нечитаемом каталоге — в
  сегодняшний путь факта CLI, чтобы учёт шага не падал вместе с
  конфигурацией (тот же принцип, что у `role_tariff`).

## Предложения системе

- `orchestrator/pause.py:153` и `orchestrator/report.py:438` разбирают
  лог шага провайдером по умолчанию, хотя роль шага им известна: с
  появлением второго провайдера обе точки начнут считать чужой формат
  Claude'ом. Зона части 2 линии провайдеров — стоит внести явным
  требованием, а не оставлять на внимательность автора.
- `skills/coding-standards.md` говорит «существующие тесты остаются
  зелёными», но не описывает класс «ожидание теста меняется потому, что
  этого требует SPEC». SPEC этой задачи закрыл пробел вручную
  (требование 12: «перечень обновлённых ожиданий разработчик перечисляет
  в PLAN») — правило стоит поднять в скил, иначе каждая SPEC будет
  изобретать его заново.
- **Второй контур учёта денег угадывает списанную сумму вместо того,
  чтобы получать её фактом** (ревью итерации 1, R1-F1/R1-F3).
  `budget.check_program_spend` восстанавливает «до шага» вычитанием
  переданного числа, поэтому КАЖДАЯ новая ветка учёта обязана помнить,
  что в порог идёт не её входной словарь, а факт списания. Эта задача
  закрыла свою ветку (`runner._program_cost` считает разность
  `spent_usd`), но пробел остался у соседней: частичная стоимость
  оборванного шага (`spend.charge_missing_result`, ветка PARTIAL)
  списывается в `spent_usd` и в порог программы не попадает вовсе —
  `_program_cost` отдаёт `None` при `cost is None`. Чинится это не
  перечислением веток в вызывающем, а обязанностью точки учёта
  ОТДАВАТЬ факт списания (`store.charge`/возврат `charge_step`/
  `charge_missing_result`) — отдельной задачей, зоны которой включают
  `orchestrator/budget.py`.
