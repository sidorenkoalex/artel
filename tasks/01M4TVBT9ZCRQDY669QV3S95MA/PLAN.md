---
task: 01M4TVBT9ZCRQDY669QV3S95MA
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: команда `reference <проект>` и порог справочника ядра — настройка проекта

## Подход
Монолит по SPEC: одна новая обёртка над существующей сборкой, без второй
реализации.

- `orchestrator/targets.py`: `min_uses` добавлен в `REFERENCE_FIELDS`;
  `_check_reference` принимает только `type(v) is int` в
  `REFERENCE_MIN_USES_RANGE = (1, 1000)` (булево отсекается явно — подкласс
  `int`), отказ называет проект, поле `core_reference` и подполе `min_uses`.
- `orchestrator/reference_cache.py`:
  - `min_uses(setting) -> (порог, источник)` — подполе либо
    `config.CORE_REFERENCE_MIN_USES` («настройка проекта» / «умолчание»);
    им пользуются и `_build` (генератор), и `_read_cache` (сверка), поэтому
    кэш, собранный с другим порогом, не годен (порог входит в шапку
    `CORE_REFERENCE_MIN_USES`, которую сверяет `core_reference.reference_sha`).
  - `get_reference_for_target(conn, target, *, reason, sha, task_id=None)` —
    общий вход; `get_reference` читает проект задачи и сводится к нему,
    передавая свой `task_id` (голова ветки задачи при `sha=None`, записи
    журнала по задаче — как прежде). Без задачи и без sha — `absent`.
  - Повод `reference` (`REFERENCE_REASON`): `_alert_source` даёт `None`,
    `_alert` при `None` ничего не делает — ни подъёма, ни снятия (снятий в
    модуле и не было). Записи «построен»/«сбой» пишутся с явным
    `target=` (по задаче значение то же, что `store.journal` читал сам).
  - `branch_commit(clone, branch)` — выделен из `_branch_head`
    (`refs/heads/<branch>^{commit}`, без `fetch`), тексты причин прежние.
- `orchestrator/projects.py`: `cmd_reference(rest)` — порядок проверок
  argv → `targets.target()` → клон (`repo_context.clone_path`, подсказка
  `target-init`) → форма `--sha` (`SHA_FORM`) → `store.db_usable()` (без
  `store.db()`) → коммит базы → вход повода `reference` → сводка; код 1 при
  состоянии не из `off/fresh/cached`. `reference_summary` — общая сводка
  (состояние с пометкой, sha, порог с источником, байты UTF-8 полного
  текста, предел, доля, вывод по формулам `brief.py:775/780`).
  `cmd_target_init` после клона печатает ту же сводку
  (`_target_init_reference`): нет поля — «выключен», нет БД — «журнал
  недоступен», коммит базы не узнан или сбой — строка причины, без выхода.
- `orchestrator/artel.py`: строка `reference <проект> [--sha <sha>]` в
  перечне «Команды:», абзац справки, запись таблицы диспетчера; в
  `_ROLE_ALLOWED_COMMANDS` НЕ внесена — белый список закрыт по умолчанию.

Команда живёт в `projects.py`, а не в новом модуле: зоны SPEC новых модулей
не называют, а `target-init` (тот же модуль) печатает ту же сводку.

## Шаги
1. targets.py + reference_cache.py: подполе, порог в сборке и сверке,
   общий вход, повод `reference` без алертов (требования 1–3).
2. projects.py + artel.py: команда, сводка, `target-init`, справка
   (требования 4–6); карта `docs/codebase-map.md` перегенерирована.
3. Тесты: долгоживущие файлы задачи (test_author) зелёные;
   `tests/test_reference_command.py` — края, не покрытые ими (лишние
   аргументы до чтения targets.yaml, вход без задачи и sha, `target-init`
   при неузнанном коммите базы); три мутации проверены — красны.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 |
| 7 | 3 |

## Влияние на систему
- Бриф и шаг мержа (`brief.py`, `fsm_merge_gate.py`) не менялись: их
  поводы дают прежние источники алертов, sha по умолчанию и журнал по
  задаче (AC-6 и существующие тесты справочника брифа/мержа зелёные).
- Проекты без `min_uses` получают прежний порог `config` — кэш прежний,
  пересборки нет. Неверное `min_uses` — `absent` с алертом, как любая
  неверная настройка.
- Белый список ролей не расширен; гейты, лимиты и сроки
  `CORE_REFERENCE_*` не тронуты — команда идёт через тот же `_build`.
- `target-init` на проекте с `core_reference` теперь собирает справочник
  (git, кэш, запись журнала) — след в тестах `target-init` на artel,
  предусмотренный SPEC; их утверждения не менялись и зелёные
  (`tests/test_git_fixation.py`, `..._declared_change.py`,
  `..._docs_ref_refixation.py`).
- Откат — revert коммита задачи; кэш `knowledge/derived/` пересоздаваем.

## Риски
- Сводка `target-init` на сломанной БД (файл есть, `store.db()` бросает) —
  ловится `except Exception` и печатается причиной: так требование 5
  «без падения».

## Предложения системе
- Сторож `conftest.py` отказывает запуску `pytest` из каталога `tests/` как
  «полному прогону» даже с явным перечнем файлов — запуск из корня с
  путями `tests/…` проходит; текст отказа это не подсказывает.
