---
task: 01M446WN0V7JW4NSYQFKTBJ05C
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Мандат Оператора на расширение зон доходит до коммита пульта

## Фаза A: план
- Таблица покрытия полна (требования 1–6 → шаги 1–2); шаги размера MR.
- Подход не копирует разбор мандата: `checkpoint._mandate_covered` зовёт
  общий узел `zones._answer_zones_mandate` отложенным импортом (идиома
  модуля, цикл `zones → checkpoint`) и покрывает путь формулой гейта
  `zones._touches_zone` — та же, что в `_zones_gate`
  (`orchestrator/advance_gates/zones.py`, строка
  `all(_touches_zone(f, mandate_paths) for f in out_of_zone)`).
- «Влияние на систему» соответствует diff: тронуты только
  `orchestrator/checkpoint.py`, новый `tests/test_checkpoint_zone_mandate.py`,
  долгоживущий файл задачи и `docs/codebase-map.md`. `pull.py`, гейт зон,
  `_zone_paths` не меняются. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Мандат применён в `_commit_worktree_change` (покрывает автокоммит, WIP таймаута/аварии/`pause --now`, `commit_pull_checkpoint`), в `restore_out_of_bounds_deletions` и `pult_commit_failed_paths`. Отказ `pull.py` строится по записи `STRAY_WORKTREE_FILES_ACTION`, из которой пути мандата исключены до записи. |
| 2 | OK | Один узел — `zones._answer_zones_mandate` на `artifact_branch.branch_name(task_id)`; правило исключения ANSWER автокоммита роли унаследовано. Ветка сверена с `artifact_source.resolve` тестом `test_reads_mandate_from_the_task_docs_ref`. |
| 3 | OK | Формула покрытия общая (`_touches_zone`); защищённые пути исключены — гейт их отклоняет безусловно, так что «покрыто гейтом» для них не наступает. AC-7 зелёный. |
| 4 | OK | Гейт не тронут; AC-8 зелёный (без раздела PLAN — `ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION`, с разделом — `verifying`). |
| 5 | OK | `commit_success_checkpoint`: «; по мандату Оператора вне зон: <пути>» отдельно от сводки. AC-9 зелёный. |
| 6 | OK | AC-1–AC-9 закрыты долгоживущим файлом `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`; юнит-тесты разработчика проверяют другие свойства (защищённый путь, ленивое чтение, формула гейта, ветка источника) — повтора долгоживущего нет. |

## Замечания
Блокирующих и major нет. Наблюдения без замечания:
- `_answer_commit_is_role_step_autocommit` при сбое git возвращает
  `False` (ANSWER засчитывается мандатом) — это прежнее поведение гейта;
  коммит пульта его наследует, паритет с гейтом (AC-7) сохранён. Не
  дефект этой задачи.
- Заявки «Ловит мутацию» в `tests/test_checkpoint_zone_mandate.py` все
  четыре на наблюдаемое расхождение (возврат списка / вызов узла /
  аргументы вызова) и правдоподобны; докстринги описывают сценарий.
  Новых изменённых утверждений в существующих тестах нет (diff `tests/`
  — только новые файлы).
- Пятый элемент возврата `_commit_worktree_change` обновлён во всех
  вызывающих (`_wip_checkpoint`, `_test_author_checkpoint`,
  `commit_success_checkpoint`, `commit_pull_checkpoint`) и во всех ветках
  возврата функции.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py tests/test_checkpoint_zone_mandate.py`
  — 15 passed, 26 subtests passed (40 c).
- Затронутые модули: `test_checkpoint_zone_filter`, `test_timeout_checkpoint`,
  `test_step_autocommit`, `test_zones_gate`, `test_answer_mandate`,
  `test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted`,
  `test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit`, `test_role_commit_by_pult`,
  `test_pause_now`, `test_pull`, `test_runner_pre_step_pull` — 157 passed,
  31 subtests passed (3 мин 05 с).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` —
  расхождение только в строке `built_at_sha`, карта свежая (изменение
  откачено `git checkout`, дерево чистое).
- `artel.py plank-run 01M446WN0V7JW4NSYQFKTBJ05C` — отказ «планки нет: …
  нет файлов test_*.py»: у задачи только долгоживущая группа в `tests/`,
  она прогнана напрямую pytest (первая строка).
- CI коммита f76ff73e зелёный (16 проверок), по пакету.
- Временную мутацию (снять `is_protected_path` в `_mandate_covered`)
  запустить не удалось — команда правки файла отклонена правами шага;
  сторож защищённого пути проверен чтением: при снятой проверке результат
  `["skills/developer.md", "docs/extra/note.md"]` ≠ ожидаемому
  `["docs/extra/note.md"]`.

## Предложения системе
- `orchestrator/plank_run.py`: подтверждаю наблюдение PLAN — для задачи,
  планка которой целиком долгоживущая (в `acceptance_tests/` только
  `long_lived.sha256.txt`), `plank-run` отказывает «планки нет», а миссия
  ревью требует гонять планку только им; стоит гонять перечень лока из
  `tests/`.
