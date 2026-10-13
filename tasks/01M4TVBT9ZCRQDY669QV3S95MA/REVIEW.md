---
task: 01M4TVBT9ZCRQDY669QV3S95MA
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: команда `reference <проект>` и порог справочника ядра — настройка проекта

## Фаза A: план
- Таблица покрытия полна (требования 1–7 → шаги 1–3); шаги размера MR.
- Подход — обёртка над существующей сборкой (`_build`), без второй
  реализации; команда в `projects.py` рядом с `target-init` — обосновано
  (зоны SPEC новых модулей не называют).
- «Влияние на систему» совпадает с diff: изменены только
  `artel.py`, `projects.py`, `reference_cache.py`, `targets.py`, новый
  `tests/test_reference_command.py`, карта. `brief.py`,
  `fsm_merge_gate.py`, `config.py`, `targets.yaml` не тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py:190-196`: `type(v) is int` в `(1, 1000)`, булево отсечено; текст отказа — `{field}` (проект + `core_reference`) и `'min_uses'`. |
| 2 | OK | `reference_cache.min_uses()` в `_build` (:194) и `_read_cache` (:262) одинаково; неверное значение — `targets.core_reference` бросает → `absent` с алертом (AC-5 зелёный). Временная мутация «`_read_cache` с порогом config» → красны AC-3/AC-4. |
| 3 | OK | `get_reference_for_target(conn, target, *, reason, sha, task_id=None)`; `get_reference` сводится к нему с `task_id`; повод `reference` → `_alert_source` = None → `_alert` ранний выход (единственный путь к `alerts.raise_alert` в модуле — проверено grep). `store.journal` с явным `target=` даёт для задачи то же значение, что прежнее чтение `task_target` (`store.py:1162`). |
| 4 | OK | `projects.cmd_reference`: argv → `targets.target()` → клон (подсказка `target-init`) → `SHA_FORM.fullmatch` → `store.db_usable()` без `store.db()` → `branch_commit` (`refs/heads/<base>^{commit}`, без fetch) → сводка; формулы `size > limit` / `size*10 > limit*9`, размер — байты UTF-8 полного `result.text`; код 1 вне `off/fresh/cached`. В `_ROLE_ALLOWED_COMMANDS` не внесена. |
| 5 | OK | `_target_init_reference`: нет поля / нет БД / коммит базы не узнан / исключение — строка без выхода; иначе та же сводка. Каталоги и клон не трогаются. |
| 6 | OK | Строка перечня и абзац справки `artel.py`; карта свежа (см. ниже). |
| 7 | OK | Долгоживущие файлы задачи покрывают перечень мутаций; `tests/test_reference_command.py` — края вне них (лишние аргументы до чтения targets, вход без задачи и sha, неузнанный коммит базы в `target-init`), заявки «Ловит мутацию» наблюдаемы, повторов долгоживущих свойств нет. Песочницы временные, настоящий `targets.yaml` не меняется. |

Наблюдение без замечания: `reference_summary` при `state == "off"` всегда
дописывает «(нет поля core_reference)», хотя `off` бывает и при
`projects_root() == NO_AREA` (песочница с боевой областью). В штатном
запуске команды Оператора недостижимо — дефектом не считаю.

## Замечания
Нет замечаний blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M4TVBT9ZCRQDY669QV3S95MA` — 1 passed, код pytest 0.
- `python3 -m pytest -q` по `tests/test_01m4tvbt9zcrqdy669qv3s95ma_min_uses_field.py`,
  `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`, `tests/test_reference_command.py`,
  `tests/test_merge_reference_step.py`, `tests/test_core_reference.py`,
  `tests/test_01m4s24963r9h18an2xdp6r15b_*.py`, `tests/test_01m4s24ebvb72b8wyj3jy96y0e_*.py`,
  `tests/test_git_fixation.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`,
  `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py` — 181 passed, 252 subtests passed (3 мин 40 с); тесты `target-init` на artel со следом сборки зелёные, их утверждения не менялись.
- Временные мутации `orchestrator/reference_cache.py` (возвращены `git checkout`, дерево чистое):
  (а) `_alert` поднимает алерт с источником `brief.core_reference` при `source is None` —
  красны `test_ac7` (сбой, недостатки, кэш не записан) и `test_no_task_no_sha_is_absent_without_alert`;
  (б) `_read_cache` сверяет с `config.CORE_REFERENCE_MIN_USES` — красны `test_ac3`, `test_ac4` (3 subtests).
- `python3 scripts/codebase_map.py` → `git diff` карты — расхождение только в `built_at_sha`; карта свежа, регенерация откачена.
- `git diff baf0432c...HEAD` по `tests/` — существующие тесты не изменены, только новый файл.

## Предложения системе
- Песочница роли отказывает Bash-командам с heredoc/подстановкой процесса
  (`<(…)`) при временной мутации — приём «временная мутация» из
  review-checklist удобнее описать через Edit + `git checkout -- <файл>`.
