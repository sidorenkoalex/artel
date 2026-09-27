---
task: 01M3FQ2Z2PY0E9T5F5WQ207NP5
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Канарейка на наборе ролей: провайдер и модели ролей в клоне, бейзлайн по набору (задача 6б линии Codex)

# ТЗ: Канарейка на наборе ролей: провайдер и модели ролей в клоне, бейзлайн по набору (задача 6б линии Codex)

Источник: план провайдеров ролей (docs/research/providers-codex-plan.md,
раздел 7, задача 6: «прогон канарейки на наборе «роли на Codex» по
требованию; бейзлайн на набор «роль → модель»»). Задача 6 линии
разделена Оператором 26.09 на 6а (калибровка и report по провайдеру —
после первых прогонов Codex), 6б (эта), 6в (doctor: живой смок, лимит
окна подписки, сигнатуры — после операторских шагов входа). Задачи 0–5
линии смержены (последняя — 01M3F7BY, паритет безопасности).

Факты (origin/main a24d78fc):
- Команда `canary --k <N> [--sha <sha>]` (orchestrator/artel.py:727 →
  canary.cmd_canary, orchestrator/canary.py:1132); подкоманда pool-seal.
  Параметра провайдера или набора ролей нет.
- Клон: canary._ephemeral_clone (:238) — git clone пульта, checkout
  целевого sha, переадресация _CLONE_CONFIG_ATTRS (:219, в том числе
  MODELS_LOCAL) и catalog.cmd_init(), который через
  models.ensure_local_template() кладёт шаблон LOCAL_TEMPLATE
  (orchestrator/models.py:518): все ярусы → claude-opus-5. roles.yaml
  берётся из целевого sha (provider: у ролей не задан, по умолчанию
  claude — orchestrator/roles.py:74, providers/__init__.py:22). Итог:
  роли в клоне всегда идут на Claude; локальный .artel/models.yaml
  пульта в клон не попадает.
- Бейзлайн: таблица canary_baseline(title PK, steps, cost_usd,
  review_iterations, updated_at) (orchestrator/store.py:918), ключ —
  только title шаблона; canary_runs(run_stamp, title, task_id, steps,
  cost_usd, review_iterations, escalations, outcome, …, main_sha,
  verdict) (:913). Отклонение — canary._deviation_exceeds (:765) по
  config.CANARY_DEVIATION_RATIO = 0.5; бейзлайн заводится первым штатным
  прогоном шаблона (_baseline_deviation_note :1026). Бейзлайн шаблона
  canary-version-json на opus-5: $6.54 (13.09); прогоны 26.09 — $16.97 и
  $17.66 — уже за порогом отклонения на той же модели.
- Перевод роли на Codex требует трёх вещей: provider: codex у роли в
  roles.yaml (защищённый путь), ярус → gpt-* в локальном слое
  .artel/models.yaml (config.MODELS_LOCAL), allow_experimental для
  модели со status: experimental; согласованность проверяет
  doctor check_model_provider_cli (orchestrator/doctor/preflight.py:328).
  models.resolve_role (orchestrator/models.py:434) отдаёт Resolution
  (role, tier, model, provider, …).
- Тесты: tests/test_canary.py (EphemeralCloneConfigRemapTest,
  CloneConfigAttrsInvariantTest, CanaryBaselineStoreRoundtripTest,
  GreenCanaryRunsTest, CmdCanaryBadInputTest, DriveTask*, …),
  tests/test_doctor_canary_pool.py, tests/test_models_doctor.py.
- Живых запусков Codex в конвейере ещё не было; вход по подписке
  ChatGPT — операторские шаги после сдвига пина (dom роли doctor --fix,
  указатель default keychain изолированного HOME, codex login).

Требуется:
1. Набор ролей канарейки: `canary --k <N> [--sha <sha>] [--set <имя>]`.
   Набор — именованное сопоставление «роль → (провайдер, модель)» в
   локальном слое пульта (.artel/models.yaml, новый ключ, например
   `canary_sets:`; формат обосновать в SPEC и добавить в
   docs/reference/models-local.example.yaml), по умолчанию — набор
   «как пульт» (текущие ярусы локального слоя). Клон получает локальный
   слой, собранный из набора (ярусы/overrides/allow_experimental под
   выбранные модели), а не шаблон LOCAL_TEMPLATE; roles.yaml клона
   получает provider: по набору — способом, не требующим правки
   защищённого roles.yaml в главной копии (например, локальная
   переопределяющая карта «роль → провайдер» в клоне, читаемая
   roles.provider; обосновать и не сломать check_model_provider_cli).
   Неизвестный набор, роль вне roles.yaml, модель вне каталога —
   именованный отказ до клона.
2. Бейзлайн по набору: ключ canary_baseline и строка canary_runs несут
   имя набора и сводку «роль → модель» (миграция схемы с сохранением
   существующих строк как набор по умолчанию; образец —
   test_store_schema_migration_parity); отклонение считается против
   бейзлайна того же набора; первый прогон набора заводит его бейзлайн,
   как сегодня для шаблона. В журнале и выводе canary имя набора и
   модели ролей видны.
3. Стоимость шагов в клоне на провайдере без стоимости из CLI
   (cost_from_cli: false у codex) считается по тарифу каталога так же,
   как в пульте (узел задачи 4.2) — канарейка ничего не пересчитывает
   сама, только читает spent_usd; проверить тестом, что метрики
   (_task_metrics) не зависят от провайдера.
4. Doctor: проверка согласованности наборов (каждый набор ссылается на
   существующие роли, модели каталога и провайдеров; experimental
   разрешён) — строка в существующей проверке локального слоя
   (tests/test_models_doctor.py::LocalCheckTest как образец) либо новая
   строка; статус warn при отсутствии наборов, fail при битой ссылке.
5. Документация: docs/stack.md (раздел канарейки / провайдеров) и
   docs/operator-session.md (правило одной канарейки на волну —
   дополнить: канарейка на наборе Codex по требованию, не для сдвига
   пина); текст usage в artel.py.
6. Тесты (tests/): разбор `--set`, отказы до клона; локальный слой
   клона собран из набора (подмена clone/init как в
   EphemeralCloneConfigRemapTest); provider ролей в клоне — по набору;
   бейзлайн и отклонение — по набору, миграция сохраняет старые строки;
   набор по умолчанию воспроизводит сегодняшнее поведение байт-в-байт
   (argv, шаблон слоя); существующие tests/test_canary.py,
   tests/test_doctor_canary_pool.py, tests/test_models_doctor.py,
   tests/test_store_schema_migration_parity.py зелёные, не ослаблены.
   Живой Codex не запускается — всё синтетическое.

Зоны: orchestrator/canary.py, orchestrator/store.py, orchestrator/
schema.py, orchestrator/models.py, orchestrator/roles.py, orchestrator/
artel.py, orchestrator/doctor/, docs/stack.md, docs/operator-session.md,
docs/reference/models-local.example.yaml, tests/.

Только чтение (не менять): roles.yaml и models.yaml (защищённые пути;
задача НЕ переводит роли на Codex в главной копии), orchestrator/
providers/, orchestrator/runner.py, orchestrator/budget.py, orchestrator/
report.py, orchestrator/config.py (кроме новых констант, если нужны —
общая зона), docs/research/providers-codex-plan.md, docs/backlog.md,
.artel/ (локальный слой пульта вне git).

Не входит: калибровка бюджета по провайдеру и report по провайдеру
(6а); живой смок, лимит окна подписки, сигнатуры провалов Codex (6в);
перевод какой-либо роли пульта на Codex; сам живой прогон канарейки на
Codex (операторское действие после 6в); шаблоны канарейки.

Рамка: $45.
