---
task: 01M2ZZDP87DWKFJP4HAF59TES7
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Каталог моделей, ярусы ролей, локальный слой и тариф на модель

Источник: план провайдеров ролей, принятый Оператором 20.09
(docs/research/providers-codex-plan.md, задача 2, раздел 3 «Три слоя
данных о моделях»), строка бэклога «Явная модель роли, своя в каждом
пульте» (06.09, дополнение 13.09) и решения Оператора 20.09: смешанные
ярусы разрешены, тариф для ролей без цены от CLI — публичный прейскурант,
единица гейтов — доллар. Предшественники смержены: задача 0
(01M2ZNJX2N — курс opus-5, сверка при записи шага, `spend.rate_calibrated_at`)
и задача 1 (01M2ZNTHSN — пакет `orchestrator/providers/`, `roles.provider`).

Факты:
- Модель роли — поле `model:` роли в roles.yaml (`orchestrator/roles.py::
  model`), идентификатор конкретного провайдера; runner передаёт его
  флагом `--model` через `providers.for_role(role).command(model)`.
  Вердикт совместимости — `ClaudeProvider.model_verdict` по таблице
  `orchestrator/stack.py::MODEL_MIN_CLI_VERSION` (одна запись,
  `claude-fable-5-1`); `claude-opus-5` даёт «model WARNING: модель не в
  таблице совместимости» на каждом шаге.
- Курс токенов — `config.TOKEN_RATES` по РОЛИ (четыре цены + дата
  калибровки, с 20.09 цены opus-5); читают `spend.partial_cost_usd`,
  `spend.rate_calibrated_at`, `spend.check_rate_divergence`, отчёт
  `report.token_rate_divergence`/`_divergence_html`. При смене модели у
  роли курс остаётся прежним молча (инцидент 13.09–20.09).
- Строка «agent cost KNOWN/PARTIAL» несёт `model=<id>` (с 19.09) и
  источник стоимости («факт CLI» / «расчёт по тарифу», с 20.09).
- Защищённые пути — `config.PROTECTED_PATHS` (roles.yaml в списке);
  `doc-commit` (`orchestrator/notes.py`) допускает docs/** и
  roles.yaml, gates.yaml, targets.yaml. Гейт зон и гейт защищённых
  путей читают список из кода главной копии на момент проверки.
- Локальный слой пульта `.artel/` создаёт `init`
  (`orchestrator/catalog.py::cmd_init`, разворачивает дом роли по
  `providers.home_references()`); `.artel/` в git не входит.
- БД: схема и миграции — `orchestrator/schema.py` (`SCHEMA`,
  `migrate`, `add_column`), тест паритета
  `tests/test_store_schema_migration_parity.py`.
- Предполётные проверки и `doctor`: `doctor.provider_preflight_checks`
  (по провайдеру каждой agent-роли), строка «провайдеры ролей: роль →
  провайдер» (задача 1); `runner._refuse_before_start` и
  `_resolved_role_model` — отказ до старта агента.
- Канарейка (`orchestrator/canary.py`) и калибровочная таблица бюджета
  (`orchestrator/budget.py`) моделью не параметризованы — задача 6 плана,
  здесь не трогаются.

Требуется:
1. Каталог поддерживаемых моделей — файл `models.yaml` в корне
   репозитория (создаётся этой задачей): по провайдерам (`claude`
   сейчас; раздел `codex` добавит задача 4) — имя инструмента CLI,
   минимальная версия CLI провайдера, признак `cost_from_cli`, и модели:
   идентификатор, минимальная версия CLI для модели, прейскурант по
   четырём видам токенов за миллион (`list_price_usd_per_mtok`:
   input/output/cache_write/cache_read), дата прейскуранта, статус
   (`supported` | `experimental`). Стартовое содержимое: модели Claude,
   которые роли использовали в журнале с 28.08 (`claude-sonnet-5`,
   `claude-opus-5`, `claude-fable-5-1`), минимумы из сегодняшней
   `stack.MODEL_MIN_CLI_VERSION`, прейскурант opus-5 из
   `config.TOKEN_RATES` 20.09, прочие цены — по публичному прейскуранту
   Anthropic с датой. Разбор — модуль `orchestrator/models.py`
   (загрузка, схема, именованные ошибки: неизвестный провайдер, модель
   без прейскуранта, неполный прейскурант, ноль как цена).
   `models.yaml` добавляется в `config.PROTECTED_PATHS` и в допустимые
   пути `doc-commit` (`notes.py`, префикс `config:`). Сверить с гейтом
   защищённых путей: файл впервые появляется в ветке задачи до того, как
   попадёт в список, — переход должен пройти (гейт читает список главной
   копии); если аналитик находит препятствие — путь Оператора:
   приложением к PLAN.
2. Ярусы у ролей: поле `model_tier` agent-роли в roles.yaml из
   закрытого перечня `strong | standard | cheap` (`orchestrator/roles.py::
   model_tier`). Поле `model` у роли больше не читается пультом —
   удаляется из roles.yaml тем же приложением, которым добавляется
   `model_tier` (roles.yaml — защищённый путь, приложение к PLAN;
   распределение ярусов для приложения: все четыре роли — `strong` на
   момент задачи, так как локально все на opus-5; смена — решение
   Оператора после). Agent-роль без `model_tier` или с ярусом вне
   перечня — именованный отказ `run`/`auto` до старта агента и красная
   строка `doctor`.
3. Локальный слой — `.artel/models.yaml` (вне git): `tiers:` ярус →
   идентификатор модели из каталога; необязательный `overrides:` по
   модели — собственный тариф по четырём видам с `calibrated_at` и
   `source`; необязательное явное разрешение модели со статусом
   `experimental`. Шаблон файла кладёт `init` (и `doctor --fix`, если
   файла нет): ярусы на `claude-opus-5`, без переопределений. Разбор в
   том же `orchestrator/models.py`. Разрешение цепочки роль → ярус →
   модель → провайдер, минимум CLI, действующий тариф (override, иначе
   прейскурант каталога): функция `models.resolve_role(role)`,
   fail-closed на каждом звене (ярус без модели, модель не в каталоге,
   `experimental` без разрешения — именованный отказ до старта агента).
4. Runner и провайдеры: `runner._resolved_role_model` и
   `_refuse_before_start` берут модель через `models.resolve_role`;
   `ClaudeProvider.model_verdict` сверяет установленную версию CLI с
   минимумом модели из каталога — таблица `stack.MODEL_MIN_CLI_VERSION`
   удаляется вместе с предупреждением «не в таблице совместимости»
   (модель не в каталоге — теперь отказ, не предупреждение). Инвариант
   «агент роли не стартует без явного `--model`» сохраняется (тест).
5. Тариф на модель: `config.TOKEN_RATES` по роли удаляется; `spend`
   получает тариф по модели через `models` (действующий тариф модели
   роли на момент шага, даты калибровки — `calibrated_at` override либо
   `price_date` каталога). `partial_cost_usd`, `rate_calibrated_at`,
   `check_rate_divergence`, `known_cost_pairs` работают по модели шага
   (поле `model=` строки KNOWN), а не по роли: коэффициент расхождения
   считается по паре (роль, модель) с даты калибровки тарифа модели.
   `report.token_rate_divergence`/`_divergence_html` группируют по модели
   (форма возврата `{ключ: число}` сохраняется — планка
   01M1PP0VYRT55WN8GGVG66X89Y AC-6 остаётся зелёной; аналитик сверяет,
   какой ключ она ожидает, и сохраняет совместимость).
6. История тарифов — таблица `model_tariffs` в `state.db` (миграция
   в `orchestrator/schema.py`): модель, четыре цены, `valid_from`,
   `source`. При каждом разрешении тарифа пульт сравнивает действующий
   тариф модели с последней записью и при отличии добавляет строку.
   Строка «agent cost KNOWN/PARTIAL» несёт модель (уже) и дату
   действующего тарифа; отчёт и RETRO считают по тарифу, действовавшему
   на момент шага. Руками таблица не правится (нет команды записи).
7. `doctor`: проверка «каталог моделей» (файл разобран, у каждой модели
   ярусов есть провайдер, минимум CLI и полный прейскурант), проверка
   «локальный слой» (файл есть, ярусы всех agent-ролей разрешаются,
   `experimental` разрешён явно), проверка «тариф свеж» (дата
   калибровки/прейскуранта не старше `MODEL_TARIFF_MAX_AGE_DAYS`
   в config, значение выбирает аналитик, например 90) и «тариф не
   старше смены модели у роли» (по журналу: последняя строка KNOWN роли
   с другой моделью новее даты тарифа — предупреждение). Строка
   «провайдеры ролей» расширяется до «роль → ярус → модель → провайдер».
8. Команда `models` (только чтение, `orchestrator/artel.py` +
   `orchestrator/models.py`): таблица «провайдер, модель, статус,
   минимум CLI, прейскурант, действующий тариф и его источник, роли по
   ярусам»; отказ из окружения роли не нужен (чтение).
9. Документация: docs/stack.md — раздел «Модели: каталог, ярусы,
   тариф» (три слоя, цепочка разрешения, что делает Оператор при смене
   модели или цен); docs/reference/models-local.example.yaml — шаблон
   локального слоя (тот же, что кладёт `init`).
10. Тесты (tests/): разбор каталога и локального слоя с именованными
    ошибками; разрешение цепочки и все отказы fail-closed; отказ
    `run`/`auto` до старта агента для роли без яруса и для модели вне
    каталога; `--model` всегда явный; тариф по модели и сверка по
    (роль, модель); история тарифов пишется при смене и не пишется без;
    `doctor` ok/fail по каждой проверке; `models` печатает цепочку;
    `init` кладёт шаблон. Существующие `tests/test_token_rate_divergence.py`,
    `tests/test_step_cost.py`, `tests/test_providers.py`,
    `tests/test_runner_role_model.py`, `tests/test_runner_model_preflight.py`,
    `tests/test_stack.py`, `tests/test_doctor.py`, `tests/test_report.py`,
    `tests/test_store_schema_migration_parity.py` остаются зелёными
    (ожидания по `TOKEN_RATES`/`MODEL_MIN_CLI_VERSION` обновляются с
    перечнем в PLAN).

Зоны: models.yaml, orchestrator/models.py, orchestrator/roles.py,
orchestrator/providers/, orchestrator/runner.py, orchestrator/spend.py,
orchestrator/report.py, orchestrator/config.py, orchestrator/stack.py,
orchestrator/doctor/, orchestrator/catalog.py, orchestrator/notes.py,
orchestrator/schema.py, orchestrator/store.py, orchestrator/artel.py,
docs/stack.md, docs/reference/models-local.example.yaml, tests/.

Приложением (защищённые пути, применяет пульт на мерже): roles.yaml
(`model_tier` у четырёх agent-ролей, удаление `model`).

Только чтение (не менять): orchestrator/alerts.py, orchestrator/keychain.py,
orchestrator/canary.py, orchestrator/budget.py (задача 6 плана),
orchestrator/agent_log.py, orchestrator/failure_classification.py,
orchestrator/retro.py (задача 3 плана — если RETRO требует правки для
даты тарифа, аналитик выносит в «Не входит» с пометкой), docs/backlog.md,
docs/research/providers-codex-plan.md (источник), gates.yaml, targets.yaml,
docs/reference/role-home/ (дом роли не меняется), .artel/ (локальный слой
пульта вне git — шаблон кладёт `init`, содержимое задачей не правится).

Не входит: провайдер `codex` и раздел `codex` каталога (задача 4);
показ токенов в `status`/RETRO (задача 3); пересчёт калибровочной
таблицы бюджета и бейзлайнов канарейки под модели (задача 6); лимит
подписки на окне (задача 6); переопределитель модели на уровне задачи
(решение Оператора 06.09 — только ярус у роли); команда записи в
`model_tariffs`.

Операторский шаг после мержа: локальная roles.yaml (skip-worktree)
получает `model_tier` вместо `model`; `init`/`doctor --fix` кладёт
`.artel/models.yaml`.

Рамка: $60.
