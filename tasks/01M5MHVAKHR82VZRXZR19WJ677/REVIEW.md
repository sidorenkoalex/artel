---
task: 01M5MHVAKHR82VZRXZR19WJ677
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Удалить тринадцать определений пульта, которые никто не вызывает

## Фаза A: план
- Таблица покрытия полна: требования 1–6 → шаги 1–4; требования 3–4 закрыты долгоживущим файлом автора тестов (так разрешает SPEC, отдельный дубль не нужен — повтора долгоживущего теста нет).
- Шаги — размера MR, подход (механическое удаление + правка упоминаний + карта) не конфликтует с конвенциями.
- «Влияние на систему» совпадает с diff: 11 модулей зон, карта, новый файл `tests/`; существующие `tests/` не тронуты (`git diff --name-only 55d469fd...HEAD -- tests/` → только `tests/test_01m5mhvakhr82vzrxzr19wj677_dead_definitions.py`). Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Все 13 определений удалены целиком с докстрингами (diff по 11 модулям). Импорты не тронуты; имена, которыми пользовались удалённые тела, остаются в работе: `_answer_texts`, `workspace`/`_compare`/`_answer_mandate`/`_observation_lines`, `gitcmd`/`workspace` (fixation), `_mandate_items`, `GUIDS_REL` (`pool_seal.py:352`), `config` (retro), `json` (retro_corpus), `store` (rounds), `re` (core_reference). Планка AC-3/AC-9 (разбор AST против merge-base) зелёная. `del`/переименований нет. |
| 2 | OK | `gitcmd.py:242`, `:499` — остаётся «что у `head_sha`»; `fixation.py:87` — «как и у `external_artifact_sha`»; `models.py:1580-1581` — «`return` и `approved`; константа есть только для `return`: её читает сверка пары». Абзацы не удалены, смысл сохранён. |
| 3 | OK | `test_ac1_removed_names_absent_from_modules` — 13 subTest, `hasattr` ложно, сообщение называет модуль и имя; `scripts.core_reference` импортируется пакетом. |
| 4 | OK | `test_ac2_no_references_in_orchestrator_and_scripts` — AST по `orchestrator/`, `scripts/`: `Name/Load`, `Attribute.attr`, `alias.name`; def/Store/строки не считаются. |
| 5 | OK | Перегенерация `scripts/codebase_map.py` даёт расхождение только в `built_at_sha`; ни одно из 10 удалённых имён функций в карте не встречается. |
| 6 | OK | Существующие тесты не правились; тесты изменённых модулей зелёные; строковых обращений (`getattr`/`patch.object` по строке) к 13 именам в `orchestrator/ scripts/ tests/ skills/ templates/ .github/` нет. |

Тесты: заявки «Ловит мутацию» обоих методов исполнимы — подтверждено временной мутацией (ниже). Группа `долгоживущий` верна: оба свойства — свойства кода, не факты ветки. AC-3/AC-7/AC-9 (факты задачи против merge-base) только в планке — как требует SPEC.

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет — замечаний в итерации 1 не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5MHVAKHR82VZRXZR19WJ677` — 7 passed, код выхода pytest 0.
- `python3 -m pytest tests/test_01m5mhvakhr82vzrxzr19wj677_dead_definitions.py -p no:cacheprovider -q` — 2 passed, 13 subtests passed.
- Временная мутация (возвращено `git checkout`, `git status` чист): добавлен `def is_clean()` в `orchestrator/gitcmd.py` и `def _z(): return retro_rel_path` в `scripts/core_reference.py` → оба теста красные: «orchestrator.gitcmd: определение is_clean не удалено…» и «scripts/core_reference.py:619: retro_rel_path».
- `python3 -m pytest -p no:cacheprovider -q tests/test_core_reference.py tests/test_merge_after.py tests/test_models.py tests/test_retro.py tests/test_retro_corpus.py tests/test_rounds.py` — 92 passed, 25 subtests passed.
- `python3 scripts/codebase_map.py` + `git diff -U0 -- docs/codebase-map.md` — изменена только строка `built_at_sha`; карта восстановлена `git checkout`. `grep -cE` 10 удалённых имён функций в карте — 0.
- `grep -rnE "['\"](<13 имён>)['\"]" orchestrator scripts tests skills templates .github` — совпадений вне файла задачи нет.
- `git diff --name-only 55d469fd...HEAD -- tests/` — только новый файл задачи.

## Предложения системе
- Песочница шага ревью отказывает в записи в `/tmp` и в подстановке процессов `<(...)`, поэтому CI-сверка карты «без `built_at_sha`» в виде из `ci.yml` не воспроизводится одной командой; рабочая замена — регенерация + `git diff -U0` + `git checkout`. Стоит назвать этот приём в review-checklist (раздел про `built_at_sha`).
