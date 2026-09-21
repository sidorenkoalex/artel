---
task: 01M31ZHSA6HMH40C2JTDPQJQNZ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Вывод, стоимость и провалы у провайдера

Родительская задача: 01M31Y3RXXKS1BGC6JH3527FN0 — Интерфейс исполнителя, часть 2: вывод, стоимость и провалы у провайдера, токены рядом с долларами
Зоны: orchestrator/providers/, orchestrator/agent_log.py, orchestrator/spend.py, orchestrator/failure_classification.py, orchestrator/runner.py, orchestrator/config.py, docs/stack.md, tests/
Порядок: первая, без зависимостей
Рамка: $45

Часть 1 линии «Интерфейс исполнителя, часть 2» (план провайдеров ролей,
`docs/research/providers-codex-plan.md`, задача 3). Предшественники
смержены: 01M2ZNTHSN (пакет `orchestrator/providers/`, `ClaudeProvider`),
01M3009Y9A (каталог `models.yaml`, ярусы, `models.resolve_role`),
01M300A14K (тариф на модель, история тарифов, сверка по паре
роль-модель).

Факты: разбор вывода агента привязан к формату Claude `--output-format
stream-json` мимо провайдера — `orchestrator/agent_log.py`
(`render_agent_line`, разбор события потока, вызовы и результаты
инструментов, трение шага, `OutputPump.catch_cost`),
`orchestrator/spend.py` (`parse_cost_event` — событие `type: result`,
`total_cost_usd`, `usage`; `stream_usage_by_type`;
`partial_tokens_from_log`), `orchestrator/runner.py` (создаёт
`OutputPump`, зовёт `spend.charge_step`/`spend.charge_missing_result`).
Виды токенов названы именами Claude (`config.USAGE_TOKEN_KEYS`), а
каталог моделей и тариф называют те же виды общими именами
`input`/`output`/`cache_write`/`cache_read`. Стоимость шага списывается
только фактом CLI; признак каталога `cost_from_cli` (у `claude` — true)
пультом не читается. Сигнатуры классов провала
(`orchestrator/failure_classification.py`) — тексты Claude CLI, а классы
и их последствия общие.

Требуется:
1. Разбор вывода — у провайдера: интерфейс
   `orchestrator/providers/base.py::RoleExecutorProvider` получает разбор
   строки вывода в событие общего вида (текст для лога; вызов
   инструмента — имя и аргументы; результат инструмента; учёт токенов
   разбивкой по четырём ОБЩИМ видам; итог запуска — разбивка, стоимость
   в долларах от CLI либо её отсутствие, признак ошибки и её текст).
   `ClaudeProvider` реализует разбор так, что поведение пульта на Claude
   не меняется: тот же текст лога, то же трение шага, та же стоимость,
   те же токены. `OutputPump`, `render_agent_line`, метрика трения,
   `parse_cost_event`, `stream_usage_by_type`, `partial_tokens_from_log`
   работают через провайдера роли шага, а не через литералы формата
   Claude.
2. Стоимость для провайдера без цены от CLI: итог запуска получен, но
   цены не несёт, либо провайдер модели шага помечен
   `cost_from_cli: false` — стоимость считается по действующему тарифу
   модели шага (`spend.tariff_cost_usd`) и списывается в `spent_usd` как
   известная: «agent cost KNOWN» с `источник=расчёт по тарифу`, без
   сверки с фактом и без предупреждения о расхождении. Провайдер с
   `cost_from_cli: true` и ценой в итоге — путь прежний. Итога запуска
   нет вовсе (таймаут, обрыв пайпа) — прежние пути UNKNOWN/PARTIAL/LOST.
   Модель без тарифа на пути расчёта — не ноль и не молчание: именованная
   запись журнала и алерт.
3. Совместимость журнала: строки стоимости до и после задачи разбираются
   одними и теми же `spend.known_cost_breakdown`, `known_cost_pairs`,
   `report`, RETRO и сверкой курса — разбор принимает обе формы имён
   видов токенов. Строка «agent cost KNOWN/PARTIAL» несёт имя провайдера
   шага (`provider=`) рядом с `model=` и датой тарифа.
4. Классы провалов: набор классов (`1a`, `1b`, `stream_broken`,
   `session_limit`, `system_candidate`, `model_unsupported`) и их
   последствия остаются общими в `failure_classification.py`;
   тексты-сигнатуры и извлечение требуемой версии CLI переезжают в
   провайдер (`ClaudeProvider` — прежние сигнатуры байт-в-байт),
   классификация попытки берёт сигнатуры провайдера роли шага.
5. Документация: `docs/stack.md` — абзац «Вывод и стоимость у
   провайдера» (что провайдер обязан отдавать, как считается стоимость
   при `cost_from_cli: false`).
6. Тесты (tests/): разбор вывода Claude через провайдер даёт тот же лог,
   трение, стоимость и токены, что до задачи (на записанных образцах
   потока); провайдер-заглушка без стоимости в итоге — шаг списывается
   по тарифу строкой KNOWN с `источник=расчёт по тарифу` и без
   предупреждения о расхождении; модель без тарифа на этом пути — запись
   и алерт, не ноль; разбор журнала принимает строки старого и нового
   вида; сигнатуры провалов берутся у провайдера, классы Claude прежние.
   Существующие `tests/test_step_cost.py`,
   `tests/test_token_rate_divergence.py`, `tests/test_model_tariffs.py`,
   `tests/test_providers.py`, тесты трения шага и классификации провалов
   остаются зелёными; перечень обновлённых ожиданий — в PLAN.

Только чтение (не менять): `orchestrator/models.py`, `models.yaml`
(защищённый путь), `orchestrator/store.py`, `orchestrator/alerts.py`,
`orchestrator/pause.py` и `orchestrator/doctor/` (вызывающие затронутых
функций вне зон — обязаны продолжать работать без правки),
`orchestrator/canary.py`, `orchestrator/budget.py`, `docs/invariants.md`.

Не входит: показ токенов в `status`/RETRO/`report` и сбор провайдера
ретро-корпусом (часть 2 этой нарезки); провайдер `codex` и его разбор
JSONL (задача 4 плана); отчёт и бейзлайны канарейки по провайдеру и
модели (задача 6); паритет безопасности (задача 5); смена единицы
бюджета — доллар остаётся.