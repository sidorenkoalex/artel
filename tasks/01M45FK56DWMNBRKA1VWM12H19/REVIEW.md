---
task: 01M45FK56DWMNBRKA1VWM12H19
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Этап 3 ADR-0021, часть 2 из 3: защищённые пути проекта, зоны, приложения к PLAN и карта на repo_context

## Фаза A: план

- Таблица покрытия полна: требования 1–8 сопоставлены шагам 1–8, AC-1..AC-14
  распределены между долгоживущими файлами задачи и двумя файлами планки.
- Шаги размером в MR, не микрооперации. Подход — одна функция
  `repo_context.protected_paths(ctx)` и параметр `protected` у функций guard
  (`None` — перечень артели). Это ложится на существующую формулу
  `config.is_protected_path(path, protected)` (`orchestrator/config.py:729`),
  с конвенциями не конфликтует.
- Раздел «Влияние на систему» соответствует diff: затронуты ровно 11 файлов кода
  и 3 файла тестов из стат-списка. `ci_protected_paths.py`, `plan_appendix_ci.py`
  и `checkpoint.py` не тронуты, путь отката описан.
- Расширение объёма (`_appendix_already_in_base`) авторизовано ANSWER-5.
  Сверка зон на гейте SPEC у артели — ANSWER-2, вопрос 2. Приложение 1
  заменено диффом из ANSWER-6 слово в слово.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `repo_context.protected_paths`: у артели — `tuple(config.PROTECTED_PATHS)` на момент вызова, у внешнего проекта — `ctx.no_paths` из `resolve`. Пустой кортеж `()` у внешнего проекта не превращается в перечень пульта: `is_protected_path` сверяет `protected is None`, а не истинность (`config.py:746`). |
| 2 | OK | Перечень проекта получают все места из «Фактов»: `zones.py`, `fsm_merge_gate._protected_path_diff_gate` и `_handle_merge_conflict`, `github_adapter.ensure_draft_mr`, `guard.plan_appendices`/`protected_zones` (вызовы пульта: `appendix_tree.read_plan`, `plan_appendix.py`, `catalog._tz_path_check`, `fsm._spec_protected_zones_refusal`). Вызовы без перечня остались только в CLI guard и в `plan_appendix_ci.py` — это перечень артели по SPEC. |
| 3 | OK | Развилки в `zones.py`, `plan_appendix.py` и на гейте мержа (дифф, приложения, карта) сняты. Неразрешённый контекст приводит к отказу, называющему проект: зоны, приложения при наличии блоков, `new`, гейт SPEC. Гейт ёмкости не тронут. |
| 4 | OK | Зеркало внесено в main коммитом 09256315 (ANSWER-3). Приложение 1 по ANSWER-6 — только примечание; планка AC-14 зелёная. Сторож AC-13 зелёный на ветке. |
| 5 | OK | `zones.py`: `COMMON_ZONES` только при `is_artel(ctx)`. |
| 6 | OK | `_full_suite_command`: у артели прежние классы и команда пульта. У внешнего проекта с профилем — прогон после любого приложения командой профиля. Без профиля — запись `FULL_SUITE_SKIPPED_ACTION` в журнал. Вызов `run_full_suite(root)` при `command=None` не изменился. |
| 7 | OK | `_map_step` выбирает действие по наличию `scripts/codebase_map.py` в scratch. Без генератора — запись журнала, без коммита и инцидента. `guard --all` и RETRO остались под `is_artel`. |
| 8 | OK | Новый `tests/test_project_protected_paths.py` не повторяет долгоживущие файлы: покрывает неразрешённый контекст на `new`/SPEC/гейте приложений. Смена двух существующих методов покрыта мандатом ANSWER-2; удалены ровно два утверждения, оба названы в строках мандата. |

## Замечания

Замечаний уровня blocker/major/minor нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved.

## Проверено исполнением

- `python3 -m pytest -q` по пяти долгоживущим файлам `tests/test_01m45fk56dwmnbrka1vwm12h19_*.py`, а также `tests/test_project_protected_paths.py`, `tests/test_plan_appendix.py`, `tests/test_protected_paths_gate.py`, `tests/test_zones_gate.py` — 99 passed, 27 subtests passed. Сторож AC-13 зелёный.
- `python3 orchestrator/artel.py plank-run 01M45FK56DWMNBRKA1VWM12H19` (пульт) — 2 passed (`test_ac12_unresolved_context.py`, `test_ac14_targets_appendix.py`), код выхода pytest 0.
- Временная мутация: в `plan_appendix._appendix_already_in_base` условие `--reverse --check` заменено на `True` (исход «уже наложено» снят). `test_plan_appendix.py::SequentialApplyGateTest::test_appendix_already_in_base_passes_with_a_journal_record` стал красным. Код возвращён `git checkout`, дерево чистое.
- `git diff 09256315 -- tests/test_plan_appendix.py tests/test_protected_paths_gate.py`: удалены только `assertFalse(refuses)` и `diff_base.assert_not_called()`. Оба метода названы в строках «Ослабление тестов разрешено» ANSWER-2, новые ожидания соответствуют AC-12 и AC-5.
- `python3 scripts/guard.py <PLAN.md задачи>` — «GUARD: ок».
- `python3 scripts/codebase_map.py`: расхождение с закоммиченной картой — только строка `built_at_sha`. Карта возвращена `git checkout`.
- `grep` вызовов `read_plan`/`plan_appendices`/`protected_zones`/`_tz_path_*`: вызывающий код `read_plan` с новым обязательным параметром обновлён везде (`appendix_tree.py:224`, `fsm_merge_gate.py:808`).

## Предложения системе

- `orchestrator/advance_gates/zones.py::_untracked_worktree_paths`: докстринг по-прежнему говорит «worktree self-target задачи», хотя гейт теперь исполняется для любого проекта. Кандидат на правку в части 3 вместе с докстрингом `tests/test_zones_gate.py::ZonesGateExternalTargetSkipsTest`, который уже отметил разработчик.
- `fsm_merge_gate._map_step` и полный прогон профиля исполняют код внешнего репозитория (`scripts/codebase_map.py`, команда профиля) в окружении процесса пульта. Если в этом окружении есть токены keychain, стоит явно решить в части 3 / ADR-0021, какое окружение получают такие запуски.
