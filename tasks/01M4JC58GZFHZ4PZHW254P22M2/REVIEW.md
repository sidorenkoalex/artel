---
task: 01M4JC58GZFHZ4PZHW254P22M2
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Деление переписывает merge_after зависящих задач

## Фаза A: план
- Покрытие: требования 1–3 → шаг 1; таблица полна. Шаг один, но размер MR
  (≈50 строк кода и тестов) — это нормальная единица, не «сделать всё».
- Подход идёт через готовый `merge_after.rewrite` (требование 2), с
  архитектурой не конфликтует. Решение не звать `check` обосновано в PLAN и в
  докстринге. Я проверил это по коду: `catalog.spawn_subtask`
  (orchestrator/catalog.py:614–) не пишет подзадачам `merge_after` (строку
  «Порядок:» не разбирает), значит, свежая Sn ни от кого не зависит.
  Self-ссылка и цикл при замене невозможны. Target подзадачи совпадает с
  target родителя: `target=t["target"]` в fsm.py.
- «Влияние на систему» сходится с diff: тронуты fsm.py, merge_after.py,
  tests/test_merge_after.py и карта. Путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `merge_after.replace_divided` заменяет родителя на `new_ids[-1]` на той же позиции и обходит все задачи (`store.all_tasks`). Вызывается в `fsm._spawn_division_subtasks` сразу после `killed`, до уборки хвостов. |
| 2 | OK | Запись идёт через `rewrite`, запись «было → стало» ложится в журнал зависящей задачи. Канал «деление на гейте SPEC» id родителя не содержит. |
| 3 | OK | Существующие утверждения `tests/` не менялись: в diff `tests/test_merge_after.py` только новый класс. Раздела «Меняемое поведение» нет, и он не нужен. |
| AC-1…AC-3 | OK | Их держит долгоживущий файл `tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py`, он зелёный (см. ниже). |

## Замечания
Blocker и major нет.

Наблюдения (не замечания, исправлять не нужно):
- Зависящая задача в `done`/`killed` тоже будет переписана, в журнал ляжет лишняя запись. Риск назван в PLAN и не противоречит формулировке SPEC «каждой задачи».
- Сейчас уже есть зависимость на родителя, записанная полем `merge_after` в SPEC/PLAN задачи D до её гейта. Колонка D в этот момент ещё пуста, поэтому деление её не перепишет, и `check` на гейте D откажет «задача убита». Это вне требования 1: SPEC говорит о колонке. Вынесено в «Предложения системе».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m unittest tests.test_merge_after tests.test_catalog_spawn_subtask tests.test_division_parent_cleanup tests.test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after tests.test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after tests.test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after`: Ran 41 tests, OK (194 с). Долгоживущий файл AC-1…AC-3 прогнан со случайными зёрнами, все зелёные.
- Временная мутация из заявки `ReplaceDividedTest`: убрал фильтр `if parent_id not in old: continue` в `merge_after.replace_divided`. `python3 -m unittest tests.test_merge_after.ReplaceDividedTest` дал FAILED, `AssertionError: 2 != 1`: в журнале независимой задачи появилась лишняя запись. Код вернул (`git checkout -- orchestrator/merge_after.py`), `git status` чистый.
- `python3 scripts/codebase_map.py` → `git diff -- docs/codebase-map.md`: расхождение только в строке `built_at_sha`, по содержимому карта свежая. Регенерацию откатил.
- `artel.py plank-run 01M4JC58GZFHZ4PZHW254P22M2` отказал: «планки нет: в refs/artifacts/… нет файлов test_*.py». У задачи только долгоживущий файл в `tests/`, он прогнан выше.

## Предложения системе
- Деление переписывает только колонку `merge_after` (`merge_after.replace_divided`). Значение, записанное полем SPEC/PLAN ещё не прошедшей гейт задачи, остаётся с убитым родителем, и `check` на её гейте откажет «задача убита». Такой отказ ведёт к ручному мандату Оператора — классу, который эта задача закрывает. Можно добавить в отказ `check` для `killed`-родителя деления подсказку «поделена — замени на <Sn>» (по записи «поделена на:» журнала).
- `plank-run` отказывает задаче, у которой все тесты долгоживущие (планка пуста). Ревьюверу полезно было бы, чтобы команда в этом случае сама гоняла долгоживущие файлы из перечня лока.
