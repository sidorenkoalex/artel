---
task: 01M300A14KRHCFB0DQXVCBJEKF
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Тариф на модель, история тарифов и сверка по паре роль-модель

Родительская задача: 01M2ZZDP87DWKFJP4HAF59TES7 — Каталог моделей, ярусы ролей, локальный слой и тариф на модель
Зоны: orchestrator/spend.py, orchestrator/report.py, orchestrator/schema.py, orchestrator/store.py, orchestrator/models.py, orchestrator/doctor/, orchestrator/config.py, docs/stack.md, tests/
Порядок: после части 1
Рамка: $50

Часть 2 линии «три слоя данных о моделях»: цена токена перестаёт быть
свойством РОЛИ и становится свойством МОДЕЛИ, на которой шаг реально
исполнялся. Опора — часть 1: каталог `models.yaml`, локальный слой
`.artel/models.yaml` и `models.resolve_role`, уже отдающий действующий
тариф модели роли.

Факты: курс токенов — таблица по РОЛИ в `orchestrator/config.py` (четыре
цены + дата калибровки, с 20.09 цены opus-5); читают
`spend.partial_cost_usd`, `spend.rate_calibrated_at`,
`spend.check_rate_divergence`, отчёт `report.token_rate_divergence` и
`report._divergence_html`. При смене модели у роли курс оставался прежним
молча — инцидент 13.09–20.09. Строка «agent cost KNOWN/PARTIAL» несёт
`model=<id>` (с 19.09) и источник стоимости («факт CLI» / «расчёт по
тарифу», с 20.09). Схема и миграции БД — `orchestrator/schema.py`, тест
паритета — tests/test_store_schema_migration_parity.py.

Требуется:
1. Тариф на модель: таблица курса по роли в `orchestrator/config.py`
   удаляется; `orchestrator/spend.py` получает тариф по модели через
   `orchestrator/models.py` — действующий тариф модели роли на момент
   шага, даты калибровки — `calibrated_at` переопределения либо
   `price_date` каталога. `partial_cost_usd`, `rate_calibrated_at`,
   `check_rate_divergence`, `known_cost_pairs` работают по модели шага
   (поле `model=` строки KNOWN), а не по роли: коэффициент расхождения
   считается по паре (роль, модель) с даты калибровки тарифа модели.
2. Отчёт: `report.token_rate_divergence` и `report._divergence_html`
   группируют по модели — ключ возврата идентификатор модели, значение
   то же число, форма `{ключ: число}` сохраняется. Сверка ключа,
   поручённая аналитику родительской задачи, выполнена: зафиксированная
   планка 01M1PP0VYRT55WN8GGVG66X89Y AC-6 ожидает ключ-РОЛЬ
   (`assertIn("test_author", result)`) и патчит удаляемую таблицу курса
   (`mock.patch.dict`), поэтому после требования 1 она не переживает
   патч ни при каком выборе ключа; CI её не гоняет (полный набор —
   только `tests/`), правка зафиксированной планки — команда
   `amend-tests` Оператора и в эту задачу не входит. Сохраняется то, что
   живо: форма `{ключ: число}` и «значение остаётся числом» — контракт
   действующего набора tests/test_token_rate_divergence.py.
3. История тарифов — таблица `model_tariffs` в `state.db` (миграция в
   `orchestrator/schema.py`, паритет DDL и миграции): модель, четыре
   цены, `valid_from`, `source`. При каждом разрешении тарифа пульт
   сравнивает действующий тариф модели с последней записью и при
   отличии добавляет строку; совпал — не добавляет. Руками таблица не
   правится: команды записи нет.
4. Строка «agent cost KNOWN/PARTIAL» несёт дату действующего тарифа
   (модель она несёт с 19.09). Отчёт и RETRO считают по тарифу,
   действовавшему на момент шага; правки `orchestrator/retro.py` для
   этого не требуется — RETRO складывает цены, уже посчитанные и
   записанные в журнал самим шагом.
5. `doctor`: проверка «тариф свеж» (дата калибровки/прейскуранта
   действующего тарифа не старше `MODEL_TARIFF_MAX_AGE_DAYS` в
   `orchestrator/config.py` — 90 дней) и проверка «тариф не старше смены
   модели у роли» (по журналу: последняя строка KNOWN роли с другой
   моделью новее даты тарифа — предупреждение).
6. Документация: раздел `docs/stack.md` «Модели: каталог, ярусы, тариф»,
   заведённый частью 1, дополняется тарифом и историей тарифов — что
   делает Оператор при смене цен.
7. Тесты (tests/): тариф по модели и сверка по паре (роль, модель);
   история тарифов пишется при смене и не пишется без; `doctor` ok/fail
   по обеим новым проверкам; отчёт группирует по модели и остаётся
   числом. Существующие tests/test_token_rate_divergence.py,
   tests/test_step_cost.py, tests/test_report.py,
   tests/test_store_schema_migration_parity.py остаются зелёными —
   ожидания по удалённой таблице курса обновляются перечнем в PLAN.

Только чтение (не менять): models.yaml, orchestrator/roles.py,
orchestrator/runner.py, orchestrator/providers/, orchestrator/stack.py,
orchestrator/catalog.py, orchestrator/notes.py, orchestrator/artel.py
(часть 1), orchestrator/canary.py, orchestrator/budget.py (задача 6
плана), orchestrator/alerts.py, orchestrator/retro.py,
orchestrator/agent_log.py, docs/research/providers-codex-plan.md
(источник), gates.yaml, targets.yaml, roles.yaml, .artel/.

Не входит: каталог, локальный слой и ярусы (часть 1, уже смержена);
провайдер `codex` (задача 4 плана); показ токенов в `status`/RETRO
(задача 3 плана); пересчёт калибровочной таблицы бюджета и бейзлайнов
канарейки под модели, лимит подписки на окне (задача 6 плана); команда
записи в `model_tariffs`; правка зафиксированной планки чужой задачи
(`amend-tests` Оператора).

Рамка: $50.