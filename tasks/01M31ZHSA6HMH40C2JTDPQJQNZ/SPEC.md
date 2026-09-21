---
task: 01M31ZHSA6HMH40C2JTDPQJQNZ
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/providers/, orchestrator/agent_log.py, orchestrator/spend.py, orchestrator/failure_classification.py, orchestrator/runner.py, orchestrator/config.py, docs/stack.md, tests/
budget_usd: 45
diff_forecast_kib: 45
---

# SPEC: Вывод, стоимость и провалы у провайдера

## Контекст

Пакет `orchestrator/providers/` уже держит «что нужно исполнителю роли»:
команду шага, окружение, дом роли, предполёт, инструмент манифеста и
вердикт модели (`orchestrator/providers/base.py`,
`orchestrator/providers/claude.py`). Разбор того, что исполнитель
ОТДАЁТ, мимо него: `orchestrator/agent_log.py` знает формат Claude
`--output-format stream-json` литералами (`render_agent_line`,
`_parse_stream_event`, `_tool_use_calls`, `_tool_results`,
`OutputPump.catch_cost`), `orchestrator/spend.py` — тоже
(`parse_cost_event` по `type: result` и `total_cost_usd`,
`stream_usage_by_type` по `message.usage`, `partial_tokens_from_log`).
Виды токенов в общем коде названы именами Claude
(`config.USAGE_TOKEN_KEYS`), хотя каталог моделей и тариф называют те же
четыре вида общими именами (`models.PRICE_KINDS`: `input`, `output`,
`cache_write`, `cache_read`). Стоимость шага списывается только фактом
CLI; признак каталога `cost_from_cli` (у `claude` — `true`) пультом не
читается вовсе. Сигнатуры классов провала
(`orchestrator/failure_classification.py`) — дословные тексты Claude
CLI, а сами классы и их последствия общие. Эта задача — часть 1 линии
«Интерфейс исполнителя, часть 2»: разбор вывода, стоимость без цены от
CLI и сигнатуры провалов переезжают к провайдеру, поведение пульта на
Claude при этом не меняется.

## Требования

1. Разбор вывода — у провайдера. Интерфейс
   `orchestrator/providers/base.py::RoleExecutorProvider` получает разбор
   строки вывода исполнителя в событие ОБЩЕГО вида. Событие общего вида
   покрывает: текст для лога; вызов инструмента (имя и аргументы);
   результат инструмента; учёт токенов разбивкой по четырём общим видам
   (`input`, `output`, `cache_write`, `cache_read`); итог запуска
   (разбивка по видам, стоимость в долларах от CLI либо её отсутствие,
   признак ошибки и её текст).
2. `ClaudeProvider` реализует разбор так, что поведение пульта на Claude
   не меняется: тот же текст лога, то же трение шага, та же стоимость,
   те же токены на тех же входных строках потока.
3. `OutputPump`, `render_agent_line`, метрика трения шага,
   `spend.parse_cost_event`, `spend.stream_usage_by_type`,
   `spend.partial_tokens_from_log` работают через провайдера роли шага, а
   не через литералы формата Claude.
4. Стоимость для провайдера без цены от CLI. Итог запуска получен, но
   цены не несёт, ЛИБО провайдер модели шага помечен в каталоге
   `cost_from_cli: false` — стоимость шага считается по действующему
   тарифу модели шага (`spend.tariff_cost_usd`) и списывается в
   `spent_usd` как известная: запись журнала «agent cost KNOWN» с
   `источник=расчёт по тарифу`, без сверки с фактом CLI и без
   предупреждения о расхождении курса.
5. Провайдер с `cost_from_cli: true` и ценой в итоге запуска — путь
   прежний (факт CLI, сверка курса, запись тарифа). Итога запуска нет
   вовсе (таймаут шага, обрыв пайпа) — прежние пути «agent cost
   UNKNOWN»/«agent cost PARTIAL»/«agent cost ESTIMATED»/«agent cost
   LOST».
6. Модель без тарифа на пути расчёта по требованию 4 — не ноль и не
   молчание: именованная запись журнала о неучтённой стоимости и алерт.
7. Совместимость журнала. Строки стоимости, записанные до и после этой
   задачи, разбираются одними и теми же `spend.known_cost_breakdown`,
   `spend.known_cost_pairs`, отчётом, RETRO и сверкой курса: разбор
   принимает ОБЕ формы имён видов токенов — прежние имена Claude
   (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
   `cache_read_input_tokens`) и общие имена (`input`, `output`,
   `cache_write`, `cache_read`).
8. Строка журнала «agent cost KNOWN» и строка «agent cost PARTIAL» несут
   имя провайдера шага полем `provider=` рядом с полем `model=` и датой
   действующего тарифа.
9. Классы провалов. Набор классов (`1a`, `1b`, `stream_broken`,
   `session_limit`, `system_candidate`, `model_unsupported`) и их
   последствия (связка транзиентных системных, бэкофф, алерты классов
   «обрыв потока» и «session limit», обрыв повторов у
   `model_unsupported`) остаются общими в
   `orchestrator/failure_classification.py`. Тексты-сигнатуры и
   извлечение требуемой версии CLI переезжают в провайдер; классификация
   попытки берёт сигнатуры провайдера роли шага.
10. `ClaudeProvider` несёт прежние сигнатуры провалов байт-в-байт — те
    же строки и то же выражение требуемой версии CLI, что сегодня живут
    в `orchestrator/failure_classification.py`.
11. Документация: `docs/stack.md` — абзац «Вывод и стоимость у
    провайдера»: что провайдер обязан отдавать и как считается стоимость
    при `cost_from_cli: false`.
12. Тесты (`tests/`) покрывают требования 1–11; существующие наборы
    `tests/test_step_cost.py`, `tests/test_token_rate_divergence.py`,
    `tests/test_model_tariffs.py`, `tests/test_providers.py`, тесты
    трения шага (`tests/test_agent_log.py`) и классификации провалов
    (`tests/test_failure_classification.py`) остаются зелёными; перечень
    обновлённых ожиданий разработчик перечисляет в PLAN.

## Критерии приёмки

AC-1. `orchestrator/providers/base.py::RoleExecutorProvider` объявляет
разбор строки вывода в событие общего вида, и событие различает пять
предметов требования 1: текст для лога; вызов инструмента (имя и
аргументы); результат инструмента; учёт токенов разбивкой по видам;
итог запуска. Базовая реализация тела не несёт — тем же
`NotImplementedError`, что остальные методы интерфейса.

AC-2. Учёт токенов события общего вида разложен по четырём ОБЩИМ видам
— `input`, `output`, `cache_write`, `cache_read` (`models.PRICE_KINDS`),
а не по именам счётчиков Claude.

AC-3. Итог запуска события общего вида несёт: разбивку по видам,
стоимость в долларах от CLI ЛИБО её явное отсутствие (отличимое от
нуля), признак ошибки и её текст.

AC-4. `ClaudeProvider` на записанном образце потока Claude (события
`type: assistant` с блоками `text`/`tool_use`, `type: user` с блоками
`tool_result`, финальное `type: result` с `total_cost_usd` и `usage`)
отдаёт события общего вида с теми же значениями, которые на том же
образце извлекает код пульта до задачи.

AC-5. `agent_log.render_agent_line` на том же образце даёт байт-в-байт
те же строки, что до задачи: текст ассистента, строка вызова
инструмента, строка `! ошибка агента: …`, не-JSON строка как есть,
служебное событие — пустая строка.

AC-6. Трение шага на том же образце даёт то же число, что до задачи, —
и на постфактум-разборе файла (`agent_log.step_friction`), и на
накоплении вживую (`OutputPump.friction`).

AC-7. Стоимость и токены шага на Claude не изменились: на том же
образце `OutputPump.cost`, `OutputPump.partial_tokens`,
`OutputPump.saw_usage_event`, `spend.parse_cost_event`,
`spend.stream_usage_by_type` и `spend.partial_tokens_from_log` дают те
же значения, что до задачи.

AC-8. Ни одна из шести точек требования 3 не разбирает строку вывода
сама: провайдер-заглушка роли шага с другим форматом строки меняет
результат каждой из них (лог, трение, итог запуска, разбивка usage,
частичные токены из файла лога).

AC-9. Итог запуска получен без цены (либо модель шага — у провайдера с
`cost_from_cli: false`): `spent_usd` задачи растёт на
`spend.tariff_cost_usd` по действующему тарифу модели шага, в журнале
появляется «agent cost KNOWN» с `источник=расчёт по тарифу`,
коэффициент расхождения в строке не считается и алерт расхождения курса
не заводится.

AC-10. Провайдер с `cost_from_cli: true` и ценой в итоге даёт прежнюю
строку «agent cost KNOWN» с `источник=факт CLI`, полем `actual_usd=`,
разбивкой по видам, датой тарифа и коэффициентом сверки; отсутствие
итога запуска даёт прежние «agent cost UNKNOWN»/«agent cost
PARTIAL»/«agent cost ESTIMATED»/«agent cost LOST» с прежними алертами.

AC-11. Модель без разрешённого тарифа на пути AC-9: `spent_usd` не
увеличивается на ноль молча — в журнале есть именованная запись о
неучтённой стоимости шага, и открыт алерт.

AC-12. `spend.known_cost_breakdown` разбирает и строку с прежними
именами видов токенов, и строку с общими именами, давая для одинаковых
чисел одинаковую разбивку; на журнале, где строки обеих форм лежат
вперемешку, `spend.known_cost_pairs`, отчёт, RETRO и сверка курса
считают по всем строкам, не пропуская ни одной формы.

AC-13. Строки журнала «agent cost KNOWN» и «agent cost PARTIAL» несут
поле `provider=` с именем провайдера шага рядом с полем `model=` и
датой действующего тарифа.

AC-14. Классификация попытки берёт сигнатуры у провайдера роли шага:
набор классов и их последствия остаются в
`orchestrator/failure_classification.py`, провайдер-заглушка с другими
сигнатурами меняет класс того же текста, а `ClaudeProvider` на текстах
инцидентов даёт те же классы, что до задачи (включая извлечение
требуемой версии CLI из текста класса `model_unsupported`).

AC-15. `docs/stack.md` несёт абзац «Вывод и стоимость у провайдера» —
что провайдер обязан отдавать и как считается стоимость при
`cost_from_cli: false`; полный прогон `tests/` зелёный, включая
`tests/test_step_cost.py`, `tests/test_token_rate_divergence.py`,
`tests/test_model_tariffs.py`, `tests/test_providers.py`,
`tests/test_agent_log.py`, `tests/test_failure_classification.py`.

## Оценка объёма и деление

Сработавшие сигналы: число затрагиваемых модулей/файлов зоны (восемь
элементов `zones:`, из них пять файлов `orchestrator/*.py` и пакет
`orchestrator/providers/`) и число критериев приёмки (15 ≥ 10). Прогноз
диффа: 45 КиБ.

Решение — **монолит**:

- Задача сама является частью 1 уже утверждённой нарезки родительской
  задачи 01M31Y3RXXKS1BGC6JH3527FN0 (ТЗ: «Порядок: первая, без
  зависимостей», рамка $45) — границы части заданы Оператором на гейте
  той задачи, дальнейшее дробление ломает их.
- Требования 1–3 — одна атомарная смена механики: пока хотя бы одна из
  шести точек (`OutputPump`, `render_agent_line`, трение,
  `parse_cost_event`, `stream_usage_by_type`, `partial_tokens_from_log`)
  читает формат Claude литералами, а остальные — через провайдера, в
  пульте живут ДВА разбора одного потока. Часть, переносящая интерфейс
  без перевода читателей, оставляет лог шага и учёт стоимости в
  промежуточном состоянии и отдельно не мержима с зелёной планкой.
- Требования 4–6 не отделимы от требования 1: «итог запуска без цены» —
  поле того же события общего вида, которого до требования 1 не
  существует; часть без него не имеет предмета.
- Единственный правдоподобный разрез — «классы провалов» (требования
  9–10) отдельной частью — режет зону `orchestrator/providers/`
  поперёк: сигнатуры переезжают в тот же класс `ClaudeProvider`, что и
  разбор вывода, и берутся тем же `providers.for_role(role)` в том же
  `orchestrator/runner.py`. Части не хватило бы своего куска зоны.

`budget_usd: 45` — рамка ТЗ; выше дефолта оркестратора не поднимаю.
Ориентир калибровочной таблицы для восьми элементов зон выше рамки
(восемь и более файлов — уровень ~$85), поэтому гейт назовёт «рамка ниже
калибровки»: два из восьми элементов — общие зоны (`tests/`,
`orchestrator/config.py`), которые калибровка считает наравне с
остальными, а правка в них по этой задаче мелкая. Если ревью пойдёт
дальше двух заложенных итераций, потолок поднимает Оператор командой
`budget` — сама задача выше рамки не запрашивает.

## Не входит

- Показ токенов в `status`/RETRO/отчёте и сбор провайдера
  ретро-корпусом — часть 2 этой нарезки. `orchestrator/report.py`,
  `orchestrator/retro.py`, `orchestrator/retro_corpus.py`,
  `orchestrator/catalog.py` — только чтение: по требованию 7 они обязаны
  продолжать работать без правки, поскольку разбор строк журнала живёт в
  `orchestrator/spend.py`. Если разбор обеих форм всё же потребует
  правки читателя вне зон — это расширение зон командой Оператора, а не
  тихая правка.
- Провайдер `codex` и его разбор JSONL — задача 4 плана провайдеров.
- Отчёт и бейзлайны канарейки по провайдеру и модели — задача 6 плана;
  `orchestrator/canary.py`, `orchestrator/budget.py` — только чтение.
- Паритет безопасности провайдеров — задача 5 плана.
- Смена единицы бюджета: доллар остаётся единицей потолка задачи и
  журнала.
- Каталог моделей и его разбор: `orchestrator/models.py` и `models.yaml`
  (защищённый путь) — только чтение. Признак `cost_from_cli` каталог уже
  отдаёт записью модели, заводить его заново не нужно.
- `orchestrator/store.py`, `orchestrator/alerts.py`,
  `orchestrator/pause.py`, `orchestrator/doctor/` — только чтение:
  вызывающие затронутых функций вне зон обязаны продолжать работать без
  правки.
- `docs/invariants.md` — только чтение.

## Материалы

- ТЗ: `tasks/01M31ZHSA6HMH40C2JTDPQJQNZ/TZ.md`; родительская задача
  01M31Y3RXXKS1BGC6JH3527FN0; план линии —
  `docs/research/providers-codex-plan.md` (задача 3).
- Смерженные предшественники: 01M2ZNTHSNFYSTF904P6SZTPYF (пакет
  `orchestrator/providers/`, `ClaudeProvider`),
  01M3009Y9AGGY6ZCFA7H1HJ1TD (каталог моделей, ярусы,
  `models.resolve_role`), 01M300A14KRHCFB0DQXVCBJEKF (тариф на модель,
  история тарифов, сверка по паре роль-модель).
- Адреса сегодняшнего разбора: `orchestrator/agent_log.py`
  (`render_agent_line`, `_parse_stream_event`, `_tool_use_calls`,
  `_tool_results`, `_friction_from_events`, `OutputPump.catch_cost`),
  `orchestrator/spend.py` (`parse_cost_event`, `stream_usage_by_type`,
  `partial_tokens_from_log`, `charge_step`, `charge_missing_result`,
  `known_cost_breakdown`, `known_cost_pairs`, `tariff_cost_usd`),
  `orchestrator/runner.py` (создание `OutputPump`, `_numbered_with_model`
  и вызовы учёта стоимости), `orchestrator/failure_classification.py`
  (сигнатуры и `required_cli_version`).
- Имена четырёх общих видов цены — `models.PRICE_KINDS`; отображение
  «счётчик Claude -> вид цены» уже есть в `orchestrator/spend.py`
  (`_PRICE_KIND_FOR_USAGE_KEY`).
