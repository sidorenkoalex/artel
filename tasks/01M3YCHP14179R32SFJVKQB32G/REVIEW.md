---
task: 01M3YCHP14179R32SFJVKQB32G
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Наборы моделей: файл model_sets.yaml и команда допуска пары

## Фаза A — план

- Таблица покрытия полна: требования 1–8 → шаги 1–5; шаги размера MR.
- Подход (вся механика в `models.py`, путь от `config.ROOT` в момент вызова,
  общий хвост `doc-commit` через `notes.doc_commit_content`) не конфликтует
  с архитектурой: дублирования механизма `doc-commit` нет, `cmd_doc_commit`
  переведён на тот же `_doc_commit_request`.
- «Влияние на систему» сверено с diff: затронуты `model_sets.yaml`,
  `config.py` (константа + запись в `PROTECTED_PATHS`), `notes.py`
  (вынос хвоста, константа отказа роли, `doc_commit_content`), `models.py`,
  `artel.py` (диспетчер + справка), `docs/stack.md`, `tests/`; плюс
  `store.py` (+8 строк, одна функция `all_canary_runs`) — по мандату
  ANSWER-2/3/4, раздел «Расширение зон» в PLAN есть. Сверх заявленного
  ничего нет. Откат — revert merge, файл пуст и до части 2 никем, кроме
  `admit`, не читается.
- П.8 «Подхода» (зов `_ensure_canary_tables`) устарел — PLAN это сам
  отмечает в разделе исполнения ANSWER-2; код соответствует новому виду.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `model_sets.yaml` в корне, три пустых раздела + шапка-комментарий; читается `yamlmini`; счётчика нет. Отслеживается git (приёмочный `test_model_sets_repo_facts` зелёный). |
| 2 | OK | `config.py`: `"model_sets.yaml"` в `PROTECTED_PATHS`; `notes.py`: `config.MODEL_SETS_REL` в `DOC_COMMIT_CONFIG_PATHS`. |
| 3 | OK | `models.pair_admission`/`cmd_admit`: ≥3 чистых, ≥2 шаблона среди чистых, ≥1 чистый на «среднем»; analyst — прогон с `expected_escalation_met`; строка «повторы developer: нет данных» печатается в обеих ветках (сводка до отказа); шаблоны без класса называются в перечне; отказ до записи (`sys.exit` раньше `doc_commit_content`); флага обхода нет; `--revoke` → `приостановлена` с новой датой/основанием; запись — `notes.doc_commit_content` → `_run` (окно тишины, удержание с `held_base`, гейт полного набора). Роль сверяется с картой исполнителей, модель — с каталогом. |
| 4 | OK | `models.set_admitted`: не-боевые пары (сравнение с `resolve_role(role).model`; неразрешённая боевая → fail-closed) обязаны быть `допущена`; зелёный прогон с совпадением сводки по ВСЕМ ролям набора на шаблоне класса `трудный`; шаблон без класса не трудный. |
| 5 | OK | `unclean_reason`: `verdict`, `review_iterations != 0` (NULL — не ноль), эскалации кроме ожидаемой, правило вины. См. наблюдение ниже о `escalations > 1`. |
| 6 | OK | `autogate_refusal_blame`: префиксы сверены мной с реальными производителями — `fsm_autogate._autogate_conditions` (стр. 230–288: manual/skip/ci/worktree/бюджет/`run.detail`), `fsm_autogate._plank_sources` (стр. 90, 97), `acceptance._full_suite_detail` (стр. 462–475), `FULL_SUITE_NO_TESTS_NOTE` (стр. 391). Канарейка хранит `detail` журнала целиком с префиксом «автогейт: » (`canary._acceptance_from_steps`, стр. 1878–1896, запись — `fsm_autogate` стр. 331). Строки без префикса — через `failure_classification.classify_attempt_failure` по всем провайдерам. Прочее — «не установлена». |
| 7 | OK | Раздел «Наборы моделей задач…» в `docs/stack.md`; справка `artel.py`. |
| 8 | OK | Долгоживущий файл задачи + `tests/test_model_sets.py` (свойства сверх долгоживущего, без повтора). Ослабления нет — см. «Проверено исполнением». |

Наблюдения (не дефекты, в реестр не вносятся):

- `orchestrator/models.py::unclean_reason` — прогон с `escalations = 2` и
  выполненной ожидаемой эскалацией признаётся чистым, хотя одна эскалация
  в нём неожиданная (`canary.py:1792` считает все заметки эскалаций).
  Это буквально совпадает с формулой SPEC (требование 5 и AC-11:
  «`escalations = 0` либо заданный `expected_escalation`,
  `actual_escalation = 1`, `marker_mismatch = 0`»), поэтому замечанием не
  является; стоит уточнить у Оператора к части 3 (приостановка), не
  должно ли быть `escalations <= 1`.
- Две удержанные окном тишины записи `admit` подряд: вторая собрана от
  `config.ROOT` без первой; при флаше вторая упрётся в
  `DOC_COMMIT_STALE_REFUSAL` (сверка `held_base`, `notes.py:770–776`) —
  именованный отказ, а не затирание, т.е. поведение безопасно.

## Замечания

Нет замечаний уровня blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 замечаний не заведено.

## Вердикт

approved. Все требования SPEC 1–8 и AC-1…AC-14 реализованы, планка
задачи и тесты затронутых модулей зелёные, изменённое утверждение
`test_protected_test_settings` (17 → 18 + `assertIn("model_sets.yaml")`)
покрыто мандатом ANSWER-1 дословно, прочие утверждения метода не тронуты;
перенос SQL в `store.all_canary_runs` — в рамках ANSWER-2/3/4.

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py tests/test_model_sets.py tests/test_protected_test_settings.py tests/test_multitarget.py tests/test_doc_commit.py tests/test_doc_commit_suite_gate.py tests/test_notes.py tests/test_models.py tests/test_protected_paths_gate.py tests/test_ci_protected_paths.py tests/test_artel_role_restricted_commands.py` — 245 passed, 128 subtests passed (93,7 с). Включает долгоживущую планку AC-2…AC-13 и `test_no_sql_outside_store`.
- `python3 -m pytest -q -p no:cacheprovider tasks/01M3YCHP14179R32SFJVKQB32G/acceptance_tests` — 2 passed.
- `git diff 72a55089...HEAD -- tests/ | grep '^-'` — удалены только строка
  докстринга и `assertEqual(len(config.PROTECTED_PATHS), 17)` (заменена на
  18 + `assertIn`) — мандат ANSWER-1; иного сужения нет.
- Временная мутация в процессе (без правки файлов): из
  `models._PULT_BLAME_STARTS` убрана запись «tests/ нет в worktree», а
  `unclean_reason` переписан со сверкой счётчиков через ложность —
  `AutogateRefusalBlameTest.test_producer_texts_of_pult_causes_blame_pult`
  и `CleanRunTest.test_missing_counters_are_not_clean` оба красные
  (FAILED, failures=2) — заявки «Ловит мутацию» исполнимы.
- Чтение производителей текстов отказа (`fsm_autogate.py` 180–336,
  `acceptance.py` 391–475, `canary.py` 1838–1907, `store.py` 1075–1110)
  для проверки требования 6 и формата `autogate_refusal`.

## Предложения системе

- Формула «чистого прогона» в ADR-0019 п.5 / SPEC (`escalations = 0` либо
  ожидаемая) не говорит, что делать при ожидаемой эскалации плюс ещё одной
  — к части 3 деления (приостановка по красным прогонам) стоит
  зафиксировать `escalations <= 1` или явно оставить текущее толкование.
