---
task: 01M5XZSKK8GZTECA2KWAFHE029
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab В1.1 — источник полного набора `full_suite: local | ci | both` на приёмке

## Подход
- **Поля компонента** (`targets.py`): `full_suite` (вид `full_suite`, точное
  значение из `COMPONENT_FULL_SUITES`) и `ci_job` (непустая строка) в
  `COMPONENT_FIELDS`; правило `_check_full_suite_source` после
  `_check_component_rules`: `ci_job` ровно при `ci`/`both`, `report`
  обязателен при `ci`/`both`, реализация хостинга записи в реестре должна
  иметь `job_test_report`. Реестр читается через атрибут
  `targets.hosting_registry`, который выставляет `ci.py`
  (`lambda: forge.IMPLEMENTATIONS`): `ci` уже импортирует `forge`, а
  `forge.py` вне зоны (только чтение) — так `targets` не импортирует `forge`
  по кругу, а подмена реестра (`patch.dict`/`patch.object`) видна загрузчику.
  Без загруженного `forge` проверка при загрузке пропускается, и хостинг без
  чтения отчёта ловится при использовании: `forge._call` отдаёт
  `TestReport(None, "не реализовано …")` → «неизвестно» (ANSWER-1, п. 2).
- **Профиль** (`project_profile.py`): поля `full_suite` (умолчание `local`) и
  `ci_job` в `Profile` вне сравнения, заполняет `_with_component_fields` —
  общий для `decide`/`with_tools`/`component_profiles`.
- **Итог задания CI** (`ci.job_full_suite`): последняя попытка `ci_job`
  (наибольший `id`) из `forge.pipeline_status(sha).jobs`; право падать →
  «неизвестно»; `job_result` + `job_test_report`; повторное чтение номера
  последней попытки — не совпал → «задание перезапущено во время чтения»
  (ANSWER-1, п. 3); статус не `success`/`failed` → «неизвестно»; отчёт
  `None`/пуст/исход вне `success|failed|skipped|error` → «неизвестно»
  (ANSWER-1, п. 1); `failed`/`error` в отчёте → красный; `failed` без падений
  в отчёте → «неизвестно»; иначе зелёный.
- **Приёмка** (`acceptance._acceptance_suite_run`): режим по профилю задачи;
  `ci`/`both` → `_ci_job_suite_run`. Три условия вынесены из пути артели в
  `_ci_result_conditions(root, branch, repo, base)` (артель — `base =
  config.MAIN_BRANCH`, тексты прежние; `ci`/`both` — `base` записи проекта).
  Невыполненное условие или недоказанный итог → `FULL_SUITE_NOT_STARTED` с
  деталью `UNKNOWN_PREFIX…` и записью журнала с причиной; `fresh` в
  `ci` — то же чтение через `forge`, локального прогона нет. `both` —
  локальный прогон всегда плюс итог CI; старший незелёный по
  `_NOT_GREEN_ORDER` (тот же порядок, что у `components_full_suite`, теперь
  общей константой), при равенстве решает CI. `checks_local` — в
  `acceptance_suite`, как прежде, после итога любого источника.
- **Автогейт** (`fsm_autogate.py:426`): `acceptance.is_ci_result(run)` —
  «принят итог CI» (артель) или деталь, начинающаяся записью
  `CI_JOB_RECORD` («полный набор: итог задания CI …»); у `both` деталь
  называет оба источника (ANSWER-1, п. 6).

## Шаги
1. `targets.py` + `ci.py` (регистрация реестра): поля, правила загрузки.
2. `project_profile.py`: поля профиля.
3. `ci.job_full_suite`: итог задания CI.
4. `acceptance.py`: режимы `ci`/`both`, общие условия, запись журнала.
5. `fsm_autogate.py`: распознавание записи; тест `tests/test_ci_job_full_suite.py`;
   регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 3, 4 |
| 3 | 4 |
| 4 | 5 |
| 5 | 4 (путь `local` и артели — прежний код за вынесенными условиями) |

## Влияние на систему
- Инвариант 41: любой недоказанный итог задания CI и любое невыполненное
  условие — форма `is_unknown`, которую `approve --accept-red` не принимает
  (`fsm.py:1573-1582` не менялся); у `both` «неизвестно» старше красного.
- Путь артели/`local`: условия вынесены в `_ci_result_conditions` дословно
  (тексты причин, порядок проверок, `origin/main`); `components_full_suite`
  использует ту же упорядоченность через `_not_green_rank`. Гейт мержа
  (`fsm_merge_gate.py`) не тронут — там прежний локальный набор.
- `_task_profile` теперь читается в начале `_acceptance_suite_run`;
  `ComponentsPending` там перехватывается, и отказ поднимается прежним
  путём (`_task_own_profile`) — поведение отказа прежнее.
- Проверки: долгоживущие файлы задачи — 51/51 зелёные; тесты затронутых
  модулей (34 файла: acceptance, autogate, approve, ci, targets,
  project_profile, components) — 401 passed; свой тест — 4 passed, три его
  мутации (перечитывание номера попытки, чужой исход, отчёт `None`) красят.
- Откат — revert коммита задачи; схема БД и форматы файлов не меняются.

## Риски
- Регистрация реестра побочным эффектом импорта `ci`: если когда-нибудь
  `targets.load()` позовут в процессе без `ci`/`forge`, проверка AC-3 при
  загрузке молча пропустится (остаётся проверка при использовании).
- Задача с приложением PLAN в `ci`/`both` получает «неизвестно» (дерево
  гейта ≠ дерево головы) — принято Оператором (ANSWER-1, п. 5).

## Предложения системе
- В PATH шага роли нет `ls`/`cp`/`mv` — временную мутацию сторожа пришлось
  делать сценарием Python; скил coding-standards предписывает мутации, а
  инструментов для обратимой правки нет.
- Регистрация реестра `forge` в `targets` из `ci.py` — обход запрета правки
  `forge.py`; естественное место — сам `forge.py` (одна строка) в задаче,
  где он в зоне.
