---
task: 01M31Y3RXXKS1BGC6JH3527FN0
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Интерфейс исполнителя, часть 2: вывод, стоимость и провалы у провайдера, токены рядом с долларами

Источник: план провайдеров ролей, принятый Оператором 20.09
(docs/research/providers-codex-plan.md, задача 3 «Интерфейс исполнителя,
часть 2: вывод, стоимость, провалы»; принципы учёта расхода, раздел 2;
решения Оператора 20.09: тариф для ролей без цены от CLI — публичный
прейскурант, единица гейтов — доллар, токены показываются рядом).
Предшественники смержены: задача 1 (01M2ZNTHSN — пакет
`orchestrator/providers/`, `ClaudeProvider`: argv, окружение, дом,
предполётные проверки), задача 2 в двух частях (01M3009Y9A — каталог
`models.yaml`, ярусы, `models.resolve_role`; 01M300A14K — тариф на
модель, история тарифов, сверка по паре роль-модель).

Факты:
- Разбор вывода агента привязан к формату Claude `--output-format
  stream-json` в трёх модулях, мимо провайдера:
  `orchestrator/agent_log.py` (`render_agent_line` — событие → строка
  лога, `_parse_stream_event`, `_tool_use_calls`, `_tool_results`,
  `_friction_from_events` — трение шага, `OutputPump.catch_cost`);
  `orchestrator/spend.py` (`parse_cost_event` — событие `type: result`,
  `total_cost_usd`, `usage`; `stream_usage_by_type` — usage любого
  события; `partial_tokens_from_log`); `orchestrator/runner.py`
  (создаёт `OutputPump`, зовёт `spend.charge_step` /
  `spend.charge_missing_result`, ~стр. 1189-1260, `close_pump`).
- Виды токенов названы именами Claude: `config.USAGE_TOKEN_KEYS` =
  (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
  `cache_read_input_tokens`); каталог `models.yaml` и тариф модели
  называют те же виды общими именами `input`/`output`/`cache_write`/
  `cache_read` (`orchestrator/models.py`). Журнальная строка «agent cost
  KNOWN» несёт «разбивка по видам: input_tokens=…» — её разбирают
  `spend.known_cost_breakdown`/`known_cost_pairs`, `report` и RETRO по
  всей накопленной истории.
- Стоимость шага: `spend.charge_step` списывает `cost["usd"]` — только
  факт CLI из события `result`; без него — «agent cost UNKNOWN», и
  `spent_usd` не меняется. Расчёт по тарифу (`spend.tariff_cost_usd`,
  `partial_cost_usd`) идёт только на пути PARTIAL (таймаут, обрыв пайпа)
  и для сверки с фактом. У провайдера в каталоге есть признак
  `cost_from_cli` (`models.py::COST_FROM_CLI_KEY`, у `claude` — true),
  пультом не читается.
- Классы провалов попытки: `orchestrator/failure_classification.py` —
  сигнатуры текста Claude CLI (`MODEL_UNSUPPORTED_SIGNATURE`,
  `CLASS_1A_SIGNATURES`, `CLASS_1B_SIGNATURES`,
  `STREAM_BROKEN_SIGNATURE`, `SESSION_LIMIT_SIGNATURES`,
  `SYSTEM_CANDIDATE_ANCHOR`, `MODEL_REQUIRED_VERSION_RE`) и
  `classify_attempt_failure(text)`; классы общие для пульта (повтор,
  бэкофф, эскалация), сигнатуры — провайдера.
- Показ расхода: `status` (`orchestrator/catalog.py::cmd_status`) — только
  «$spent/budget»; RETRO (`orchestrator/retro.py::_cost_block`,
  `_actor_costs`) — доллары и общее число токенов по роли, разбивки по
  видам нет; `report` (`orchestrator/report.py`) — доллары и калибровка
  курса по модели. `orchestrator/retro_corpus.py` собирает поля RETRO
  (`RETRO_FIELDS` = operator, model, artel_sha) в кэш корпуса.

Требуется:
1. Разбор вывода — у провайдера. Интерфейс
   `orchestrator/providers/base.py::RoleExecutorProvider` получает разбор
   строки вывода агента в событие общего вида: текст для лога; вызов
   инструмента (имя, аргументы); результат инструмента; учёт токенов
   (разбивка по четырём ОБЩИМ видам `input`/`output`/`cache_write`/
   `cache_read` — тем же, что у тарифа модели); итог запуска (разбивка по
   видам, стоимость в долларах от CLI либо её отсутствие, признак
   ошибки и её текст). Форма события и имена — выбор аналитика
   (обосновать в SPEC). `ClaudeProvider` реализует разбор так, что
   поведение пульта на Claude не меняется: тот же текст лога, то же
   трение шага, та же стоимость, те же токены. `OutputPump`,
   `render_agent_line`, метрика трения, `parse_cost_event`,
   `stream_usage_by_type`, `partial_tokens_from_log` работают через
   провайдера роли шага, а не через литералы формата Claude.
2. Стоимость для провайдера без цены от CLI. Если провайдер модели шага
   помечен в каталоге `cost_from_cli: false` (или его итог стоимости не
   несёт), стоимость шага считается по действующему тарифу модели шага
   («токены вида × цена вида», `spend.tariff_cost_usd`) и списывается в
   `spent_usd` как известная: строка «agent cost KNOWN» с
   `источник=расчёт по тарифу`, без сверки с фактом и без
   предупреждения о расхождении. Для провайдера с `cost_from_cli: true`
   путь прежний (факт CLI, сверка с тарифом). Модель без тарифа на этом
   пути — не ноль и не молчание: именованная запись журнала и алерт
   (отказ до старта агента в `models.resolve_role` уже есть; здесь —
   страховка на случай смены слоёв во время шага).
3. Совместимость журнала. Строки стоимости, записанные до задачи и
   после неё, разбираются одними и теми же `known_cost_breakdown`,
   `known_cost_pairs`, `report`, RETRO и сверкой курса. Если имена видов
   в строке меняются на общие — разбор принимает обе формы; если
   остаются прежними для Claude — провайдер без таких имён пишет общие,
   и разбор принимает обе. Строка «agent cost KNOWN/PARTIAL» несёт имя
   провайдера шага (`provider=`), рядом с уже существующими `model=` и
   датой тарифа — основание для отчёта по провайдеру в задаче 6.
4. Классы провалов — сигнатуры у провайдера. Набор классов
   (`1a`, `1b`, `stream_broken`, `session_limit`, `system_candidate`,
   `model_unsupported`) и их последствия (повтор, бэкофф, эскалация)
   остаются общими в `failure_classification.py`; тексты-сигнатуры и
   извлечение требуемой версии CLI переезжают в провайдер
   (`ClaudeProvider` — прежние сигнатуры байт-в-байт), классификация
   попытки берёт сигнатуры провайдера роли шага.
5. Показ токенов рядом с долларами: `status` — по каждой задаче
   суммарные токены рядом с «$spent/budget» (формат — выбор аналитика,
   одна строка на задачу сохраняется); RETRO — по каждой роли доллары,
   токены суммарно и разбивка по четырём видам, плюс провайдер и модель
   шагов роли; `report` — токены по видам рядом с долларами в разрезе
   задач и ролей. Задача без записей токенов показывает прочерк, а не
   ноль. `retro_corpus.py` добавляет в собираемые поля провайдера, если
   RETRO его несёт.
6. Документация: `docs/stack.md` — абзац «Вывод и стоимость у
   провайдера» (что провайдер обязан отдавать, как считается стоимость
   при `cost_from_cli: false`, где показаны токены).
7. Тесты (tests/): разбор вывода Claude через провайдер даёт тот же лог,
   трение, стоимость и токены, что до задачи (на записанных образцах
   потока); провайдер-заглушка без стоимости в итоге — шаг списывается
   по тарифу строкой KNOWN с `источник=расчёт по тарифу` и без
   предупреждения о расхождении; модель без тарифа на этом пути —
   запись и алерт, не ноль; разбор журнала принимает строки старого и
   нового вида; сигнатуры провалов берутся у провайдера, классы Claude
   прежние; `status`/RETRO/`report` показывают токены по видам и
   прочерк без данных. Существующие `tests/test_step_cost.py`,
   `tests/test_token_rate_divergence.py`, `tests/test_model_tariffs.py`,
   `tests/test_providers.py`, `tests/test_report.py`,
   `tests/test_retro.py`, тесты трения и классификации провалов
   остаются зелёными; перечень обновлённых ожиданий — в PLAN.

Зоны: orchestrator/providers/, orchestrator/agent_log.py,
orchestrator/spend.py, orchestrator/failure_classification.py,
orchestrator/runner.py, orchestrator/retro.py,
orchestrator/retro_corpus.py, orchestrator/catalog.py,
orchestrator/report.py, orchestrator/config.py, docs/stack.md, tests/.

Только чтение (не менять): orchestrator/models.py (тариф и цепочка
разрешения как есть), models.yaml (каталог — защищённый путь; признак
`cost_from_cli` уже есть), orchestrator/store.py, orchestrator/alerts.py,
orchestrator/canary.py, orchestrator/budget.py (задача 6 плана),
docs/research/providers-codex-plan.md (источник), docs/backlog.md,
.artel/ (локальный слой пульта вне git).

Не входит: провайдер `codex` и его разбор JSONL (задача 4); отчёт и
бейзлайны канарейки по провайдеру и модели, лимит подписки на окне
(задача 6); паритет безопасности (задача 5); смена единицы бюджета —
доллар остаётся.

Оценка объёма: зон много (11 путей, из них 8 модулей), а правка в
каждом узкая. Если сигналы деления сработают, аналитик вправе
предложить деление на «разбор вывода, стоимость и провалы у
провайдера» (требования 1-4) и «показ токенов» (требование 5) —
решение на гейте SPEC.

Рамка: $60.
