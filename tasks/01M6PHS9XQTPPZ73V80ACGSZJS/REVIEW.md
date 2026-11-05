---
task: 01M6PHS9XQTPPZ73V80ACGSZJS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: target-set — запись и снятие ключа поля-отображения локального слоя

## Фаза A — план
Таблица покрытия PLAN полна (требования 1–9 → шаги 1–3); шаги размера MR;
подход (разбор по `rest[2]`, общие помощники `_target_set_load`/
`_target_set_write`, пробный `_render({ключ: None})` как единое правило
записываемости ключа, проверка значения функцией загрузчика) с
архитектурой не конфликтует. «Влияние на систему» совпадает с diff:
тронуты только `orchestrator/projects.py`, `orchestrator/artel.py`
(справка) и регенерированная карта.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `cmd_target_set` (projects.py:409) — `rest[2] in (--key, --drop-key)` всегда новая форма; число аргументов 5/4 строго, иначе отказ с `TARGET_SET_USAGE`; `KEY_FIELDS` — перечень, поле вне его — отказ с перечнем до загрузки. |
| 2 | OK | `keys = [*field_path.split("."), key]` — ключ не делится; проверка ключа — пробный `_render` (те же условия `:260-262`), отказ с `key!r`. |
| 3 | OK | `_argument_value` (пустое — отказ), затем `targets._submodule_tokens_error({key: value})` — текст проверки в отказе до записи. |
| 4 | OK | `_assign` с `setdefault` заводит поле; прочие ключи/поля не трогаются (AC-1/AC-2/AC-12 зелёные). |
| 5 | OK | снятие в копии, пустое поле удаляется целиком; отсутствие ключа — отказ с именем до копии и журнала. |
| 6 | OK | `--key` — `_target_set_mismatches` по имени модуля; `--drop-key` — новая `_drop_key_mismatches(data, text, name, keys, path)` с сигнатурой SPEC, сравнение по кортежам листьев (ключ `a.b` не совпадёт с вложенным путём), сведение — общий `_merge_mismatches`. Формат строки журнала `<раздел>.<поле>[<ключ>]: было → стало/(нет)`; «без изменений» до проверки журнала и копии — как у прежней формы; отказы прежней формы — через общий `_target_set_load`. |
| 7 | OK | тело прежней формы перенесено без смены текстов и порядка проверок; `_target_set_mismatches` — лишь вынесены `_changed_leaves`/`_merge_mismatches` с тем же поведением; существующие тесты target-set зелёные. |
| 8 | OK | `TARGET_SET_USAGE` и справка `artel.py:197-199` называют обе формы, каждая альтернатива с `target-set`; тест реестра справки зелёный; карта — только `built_at_sha` расходится после повторной генерации. |
| 9 | OK | тесты задачи — песочница `initialized_tmp_root`, имена от зерна. |

## Замечания

Замечаний уровня blocker/major/minor нет.

Наблюдение (не замечание): AC-5 и швы AC-12 закрыты только планкой
(`test_ac5_ac12_seams.py`, «Группа: разовый» — обосновано опорой на
закрытые имена). Само свойство «нестроковое значение не записывается»
после мержа держится дважды — проверкой ветки `--key` и сведением
`merge_local` в сверке, — поэтому без сторожа не остаётся.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M6PHS9XQTPPZ73V80ACGSZJS` — 10 passed, код выхода pytest 0.
- `python3 -m pytest tests/test_01m6phs9xqtppz73v80acgszjs_target_set_key.py tests/test_projects_target_set.py tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py tests/test_01m6p1z0zhvndywn3fzszwbcg3_submodule_tokens.py -p no:cacheprovider` — 140 passed, 11 subtests passed.
- Временный зонд (удалён `task-rm`): `--key` с ключами `a #b`, `{x}`, `a<TAB>b`, `-`, `a'b` — все записаны без трейсбека (сверка подтвердила, что разбор читает их тем же ключом).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождение только в `built_at_sha`; карта возвращена `git checkout`.

## Предложения системе
