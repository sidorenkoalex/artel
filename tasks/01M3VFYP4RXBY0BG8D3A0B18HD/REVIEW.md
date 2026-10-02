---
task: 01M3VFYP4RXBY0BG8D3A0B18HD
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Единый коммит результата роли через пульт для всех провайдеров

## Фаза A — план
- В таблице покрытия требование 4 теперь закрыто двумя шагами: шагом 1 и
  возвратом R1-F1, то есть блокировкой выхода из `tests_writing`. Пробел
  итерации 1 закрыт.
- «Влияние на систему» сходится с инкрементальным diff 857a79f9..b826fbbf.
  Тронуты `orchestrator/fsm.py` (вынос `_uncommitted_step_result_refuses`
  и второй вызов в начале `_tests_writing_ac_state`) и
  `tests/test_role_commit_by_pult.py` (сторож); карта регенерирована. Оба
  пути входят в зоны SPEC, `fsm_advance.py` не тронут. Путь отката
  (revert b81eb8de и b826fbbf) указан.
- Расхождение «пять/четыре вызывающих» PLAN признал в разделе возврата.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1, планка AC-1 зелёная |
| 2 | OK | без изменений, AC-2 зелёный |
| 3 | OK | текст и логика отказа перенесены в `fsm._uncommitted_step_result_refuses` дословно (сверено по diff), `_dirty_refuses` зовёт её на прежнем месте до сверки артефактного репозитория |
| 4 | OK | запись test_author несёт операцию и текст git; выход из `tests_writing` для target `artel` отклоняется до подсчёта покрытия AC (`fsm.py:496-498`), `fsm_advance.tests_writing` на `None` возвращает False, задача остаётся на месте (`fsm_advance.py:359-363`) |
| 5 | OK | AC-5 зелёный |
| 6 | OK | без изменений |
| 7 | OK | приложение-диф `git apply --check -v` на HEAD b826fbbf проходит |

## Замечания

Новых замечаний нет. Исправление R1-F1 проверено:
- `_tests_writing_ac_state` вызывается из одного места,
  `fsm_advance.tests_writing:359` (проверено `grep -rn _tests_writing_ac_state orchestrator/`;
  в `dry_run.py`, `amend.py` и `auto.py` есть только упоминания в
  комментариях). Значит, новая проверка не задевает другие пути.
- Перед ней стоит гейт `_tests_writing_code_diff`. Если он откажет раньше,
  задача всё равно не перейдёт, поэтому требование 3 выполняется. Временная
  мутация ниже показала, что в сценарии сторожа отказ приходит именно от
  новой проверки, а не от гейта.
- Для внешнего target стоит условие `store.task_target(...) ==
  config.DEFAULT_TARGET`, поэтому внешний target проверку не проходит, как
  и в `_dirty_refuses`.
- В diff `tests/` ни один ассерт не удалён: единственная строка `-` —
  заменённый импорт.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm.py:496-498 (`_tests_writing_ac_state`); orchestrator/fsm.py:278 (`_uncommitted_step_result_refuses`) | после отказа git на коммите долгоживущих файлов test_author переход из `tests_writing` не блокировался | закрыто: выход из `tests_writing` (target `artel`) отклоняется с текстом «результат шага не закоммичен» и путём файла | принято: сверка вынесена в общую функцию и вызывается в начале `_tests_writing_ac_state`; сторож `TestsWritingBlockedAfterGitFailureTest` проверен временной мутацией (ревьювер воспроизвёл её сам) |

## Вердикт
approved. R1-F1 закрыт, новых blocker/major нет.

## Проверено исполнением
- `timeout 580 python3 -m pytest -q -p no:cacheprovider tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py tests/test_role_commit_by_pult.py tasks/01M3VFYP4RXBY0BG8D3A0B18HD/acceptance_tests/ tests/test_acceptance_tests_flow.py tests/test_long_lived_transitions.py tests/test_long_lived_step_end_to_end.py tests/test_advance_guard.py tests/test_multitarget.py`
  — 164 passed, 41 subtests passed.
- `timeout 580 python3 -m pytest -q tests/test_fsm_advance_tests_writing_*.py tests/test_fsm_advance_gate_smoke.py tests/test_long_lived_manifest.py tests/test_git_fixation.py`
  — 79 passed, 7 subtests passed.
- Временная мутация: в `_tests_writing_ac_state` условие заменено на
  `if (False and _uncommitted_step_result_refuses(...))`. Результат
  `tests/test_role_commit_by_pult.py`: 1 failed
  (`TestsWritingBlockedAfterGitFailureTest::test_tests_writing_advance_refuses_uncommitted_long_lived_file`),
  5 passed. Код возвращён `git checkout orchestrator/fsm.py`, после чего
  `git status --short orchestrator/` пуст.
- Приложение-диф извлечено из блока ```diff в PLAN.md. `git apply --check -v`
  на HEAD b826fbbf вывел «Checking patch skills/coding-standards.md...» и
  «Checking patch skills/conventions-core.md...» без ошибок.
- `python3 scripts/codebase_map.py` дал расхождение с закоммиченной картой
  (без учёта `built_at_sha`), равное нулю: карта свежая. Регенерация
  откачена `git checkout`.
- `git diff 857a79f9 HEAD -- tests/ | grep '^-'` — удалена одна строка, это
  старый импорт; ассерты не удалены и не ослаблены.

## Предложения системе
- Повтор из итерации 1, в задаче не исправлен: `checkpoint._stray_staged_paths`
  и `pult_commit_failed_paths` разбирают вывод git без `-z` и без
  `core.quotePath=false`. Путь с не-ASCII символами при такой сверке
  пропускается молча (fail-open). Стоит завести отдельную задачу.
- В shell роли нет `ls`, а составные команды с `$?` отклоняются
  («simple_expansion»). Из-за этого проверку приложения пришлось разбить на
  несколько вызовов. То же неудобство отметил разработчик в PLAN.
