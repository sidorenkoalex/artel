---
task: 01M6R8W7TSA6G85PVZZFDMRY25
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: target-set: запись автора коммитов пульта machine.commit_author

## Фаза A — план
- Таблица покрытия полна (требования 1–5 → шаг 1); один шаг оправдан
  монолитом SPEC (новая ветка `_block_keys` + перечень проверяются вместе).
- Подход переиспользует форму `--from-file` и проверку формы
  `targets.merge_local` — без дублирования проверки в projects.py;
  с архитектурой не конфликтует.
- «Влияние на систему» совпадает с diff: код изменён только в
  `orchestrator/projects.py` (+ сгенерированная карта); откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/projects.py` `_block_keys`: ветка `keys == ["machine", "commit_author"]` — точное совпадение; заведение (AC-1) и замена (AC-2) зелёные |
| 2 | OK | `BLOCK_PATHS` дописана в конец, прежняя строка — начало перечня (AC-4, AC-5) |
| 3 | OK | Путь идёт тем же `_target_set_block` (сверка, копия, журнал); отказ формы — текст `merge_local` «нужно {name, email}», слой побайтно прежний, копии нет (AC-3) |
| 4 | OK | Точное сравнение списка ключей: `machine.url`, `machine.submodule_tokens`, `machine.token_slot`, `machine.commit_author.name` — отказ перечнем (AC-4) |
| 5 | OK | `orchestrator/artel.py:197-201` пишет общий `<путь блока>`, видов не перечисляет — не правится; карта перегенерирована, `python3 scripts/codebase_map.py` на HEAD даёт расхождение только в `built_at_sha` |

## Замечания
Нет blocker/major/minor.

Наблюдения:
- Существующие тесты не тронуты (diff `tests/` пуст вне долгоживущего файла лока); гейты/лимиты не ослаблены.
- Долгоживущий тест задачи несёт `Группа: долгоживущий` и заявки «Ловит мутацию» с наблюдаемыми расхождениями (поле не заведено/`merged_author` None, `было (нет)` vs 2, отказ без текста формы, приём префикса `machine.*` — ловится параметром `machine.url`/`machine.commit_author.name`).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M6R8W7TSA6G85PVZZFDMRY25` — `test_ac5_existing_block_test.py`: 1 passed, код выхода 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6r8w7tsa6g85pvzzfdmry25_commit_author_block.py tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py tests/test_projects_target_set.py tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py tests/test_01m6phs9xqtppz73v80acgszjs_target_set_key.py tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py` — 127 passed, 11 subtests passed.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — отличие только в строке `built_at_sha` (карта свежа); изменение откатано `git checkout`.
- `grep -n target-set orchestrator/artel.py` — справка видов пути блока не перечисляет (требование 5 правки не требует).
- Временная мутация (приём любого `machine.*`) не прогнана: команда с правкой файла требовала подтверждения; чувствительность оценена по параметрам AC-4 (`machine.url` с годным блоком был бы принят и записан → `refusal_kept` красный).

## Предложения системе
