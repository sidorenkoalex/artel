---
task: 01M4KAJ0BJ9EC37RWXNFKQN7DW
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: amend-tests — признак сетевых адресов только для артели

## Фаза A: план
- Таблица покрытия полна: требования 1–4 → шаг 1 (одна правка вызова +
  регенерация карты); размер шага соразмерен MR (SPEC обосновал монолит).
- Подход совпадает с выходом из `tests_writing`
  (`orchestrator/fsm_advance.py:468` — `repo_context.is_artel(target)`);
  проект задачи берётся `workspace.task_target`, тем же путём, что соседний
  `_task_profile` (`orchestrator/amend.py:202`). Конфликта с архитектурой нет.
- «Влияние на систему» = diff: `orchestrator/amend.py` (импорт + один
  вызов), `docs/codebase-map.md` (строка импортов модуля `amend`), файл
  долгоживущих тестов задачи. Прочих путей нет; read-only пути SPEC не
  тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/amend.py:510-515` — `network_addresses=repo_context.is_artel(workspace.task_target(task_id))`; обе точки вызова `_long_lived_errors` (`amend.py:801` обычная правка, `amend.py:1070` `--from-branch`) идут через эту функцию. |
| 2 | OK | Прочие проверки `_long_lived_errors` и узла не тронуты; AC-3 (два подтеста: метод без «Ловит мутацию», литерал каталога задач) зелёный у чужого проекта. |
| 3 | OK | У артели `is_artel` → `True`, поведение прежнее; при непригодной БД `workspace.task_target` даёт артель — строгая сторона. AC-1 зелёный. |
| 4 | OK | Существующие тесты `tests/` не менялись (`git diff c7cc23db --stat -- tests/` — только новый долгоживущий файл задачи). |

Тесты: долгоживущий файл задачи несёт заявки «Ловит мутацию» у всех
четырёх методов; заявки называют наблюдаемое расхождение (отказ/сдвиг лока,
текст «инвариант 35»), сверены временной мутацией (ниже). Своих тестов
разработчик не добавлял — повтора долгоживущего файла нет. Ветки под литерал
фикстуры нет — решение общее (признак проекта по target задачи).

## Замечания
Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py tests/test_amend.py tests/test_amend_long_lived.py tests/test_amend_remove.py tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`
  — 71 passed, 11 subtests passed (160.8 с).
- Временная мутация критерия AC-4 (в `orchestrator/amend.py` вызов
  `guard.long_lived_errors_from_files(sorted(files.items()), task_id)` без
  `network_addresses`), прогон файла задачи: красные
  `test_ac2_foreign_long_lived_address_not_refused` и оба подтеста
  `test_ac3_…` (3 failed, 3 passed); код возвращён `git checkout`,
  `git status` чист.
- Свежесть карты: `python3 scripts/codebase_map.py` → `git diff --
  docs/codebase-map.md` без строки `built_at_sha` — 0 строк расхождения;
  карта возвращена `git checkout`.
- Diff карты против базы `c7cc23db` — только строки импортов/импортирующих
  модуля `amend` (добавлен `orchestrator/repo_context.py`).
- CI коммита 4da89441 зелёный (из пакета).
- `plank-run` не запускался: планки `test_*.py` у задачи нет, только
  долгоживущий файл в `tests/` (прогнан выше напрямую).

## Предложения системе
- Подтверждаю наблюдение PLAN: для задачи только с долгоживущими файлами
  нет команды пульта, гоняющей именно их (`artel.py plank-run`) — ревьювер
  гоняет их `pytest` по имени.
