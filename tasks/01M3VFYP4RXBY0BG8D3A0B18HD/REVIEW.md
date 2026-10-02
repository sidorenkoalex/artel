---
task: 01M3VFYP4RXBY0BG8D3A0B18HD
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Единый коммит результата роли через пульт для всех провайдеров

## Фаза A — план
- Покрытие: таблица PLAN закрывает требования 1–7; шаги размера MR, не
  микрооперации. Подход (журнал отказа в `_commit_worktree_change` +
  сверка `pult_commit_failed_paths` в `fsm._dirty_refuses`) не вводит
  второго механизма коммита — соответствует «Не входит».
- Пробел плана: требование 4 («срабатывает требование 3») план покрывает
  только шагом 1 (журнал). Пункт «задача не переходит из текущего
  состояния» для test_author (`tests_writing`) не покрыт ни одним шагом —
  «Влияние на систему» прямо перечисляет только переходы `spec_writing`,
  `review`, `in_dev`. См. R1-F1.
- «Влияние на систему» сходится с diff: тронуты ровно 6 путей зоны +
  сгенерированная карта. Мелкое расхождение без последствий: PLAN говорит
  о пяти вызывающих `_commit_worktree_change`, в diff их четыре
  (`_wip_checkpoint`, `_test_author_checkpoint`, `commit_success_checkpoint`,
  `commit_pull_checkpoint`).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `role_prompt.py:99-104` — пункт 4 без «закоммить код», сообщение о коммите пультом; планка AC-1 зелёная |
| 2 | OK | успешный путь не изменён; запись «код закоммичен пультом за роль» без «дефект»; AC-2 зелёный |
| 3 | OK для developer | журнал `PULT_COMMIT_GIT_FAILED_ACTION` с операцией и текстом git (`checkpoint.py:1121-1131`), отката нет, `_dirty_refuses` раньше `_in_dev_plan_escalate`; «нечего коммитить» не журналируется |
| 4 | реализовано не полностью | запись `TEST_AUTHOR_NOT_COMMITTED_ACTION` несёт операцию и текст git (`checkpoint.py:310-317`), файл остаётся — но переход из `tests_writing` не блокируется (R1-F1) |
| 5 | OK | AC-5 зелёный; признак отказа снимается записью успеха (`_PULT_COMMIT_DONE_ACTIONS`), проверено мутацией |
| 6 | OK | `docs/stack.md` раздел «Коммит результата шага: его делает пульт», `docs/operator-session.md` «Отказ git на коммите пульта» |
| 7 | OK | приложение-диф извлечено из PLAN.md, `git apply --check` на HEAD 857a79f9 — rc=0 |

## Замечания

- major — `orchestrator/fsm_advance.py:340` (`tests_writing`), в связке с
  `orchestrator/fsm.py:304` — требование 4 SPEC: «если git отказывает при
  коммите собственных долгоживущих файлов задачи, срабатывает требование 3»,
  а требование 3 включает «задача не переходит из текущего состояния».
  Новая сверка `checkpoint.pult_commit_failed_paths` вызывается только из
  `fsm._dirty_refuses`, а тот — только на `spec_writing` (`fsm_advance.py:158`),
  `review` (`:264`), `in_dev` (`:542`); в `tests_writing` её нет
  (`grep pult_commit_failed_paths orchestrator/` — единственный вызов
  `fsm.py:304`). Сценарий поломки: test_author пишет долгоживущий
  `tests/test_<id>_x.py` и приёмочные файлы планки, покрывающие все AC; хук
  `pre-commit` (или занятый `index.lock`) отказывает коммиту пульта →
  запись об отказе есть, но `advance` из `tests_writing` читает долгоживущие
  файлы с КОДОВОЙ ветки (`_tests_writing_code_diff`), где файла нет,
  трассируемость AC проходит по планке, и задача уходит в `in_dev` с
  незакоммиченным долгоживущим файлом, не попавшим в перечень лока
  (`_tests_writing_manifest_gate` по `long_lived_paths` из ветки). Дальше
  этот файл либо закоммитит пульт за developer как обычный код (вне лока),
  либо он останется посторонним. Если же AC покрыт только этим файлом —
  отказ будет, но с вводящим в заблуждение текстом «не все критерии
  покрыты», а не с отсылкой к отказу git — ровно тот класс дефекта
  диагностики, который задача закрывает. Предложение: в `tests_writing`
  для `config.DEFAULT_TARGET` до гейтов трассируемости вызвать ту же
  сверку незакоммиченного результата (например, вынести из
  `_dirty_refuses` часть с `pult_commit_failed_paths` в отдельную функцию
  `fsm` и звать её и там; правка `fsm_advance.py` выходит за перечень зон
  SPEC — если зону расширять нельзя, эскалировать Оператору с этим
  вопросом); сторож — тест в `tests/test_role_commit_by_pult.py`:
  отказ git у test_author → `advance` из `tests_writing` оставляет задачу
  в `tests_writing` с отказом, называющим незакоммиченный результат шага.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/fsm_advance.py:340 (tests_writing); orchestrator/fsm.py:304 | после отказа git на коммите долгоживущих файлов test_author переход из `tests_writing` не блокируется — требование 4 → требование 3 («задача не переходит») не выполнено | задача уходит в `in_dev` с незакоммиченным долгоживущим файлом вне перечня лока, либо отказ с неверной причиной «не все критерии покрыты» | вызвать сверку `pult_commit_failed_paths` и в `tests_writing` (target `artel`), отказ с текстом о незакоммиченном результате шага; тест-сторож в `tests/test_role_commit_by_pult.py`; если правка `fsm_advance.py` вне допустимой зоны — эскалация Оператору; разработчик (b826fbbf): сверка вынесена в `fsm._uncommitted_step_result_refuses`, её зовут `_dirty_refuses` и начало `fsm._tests_writing_ac_state` (target `artel`), это вход выхода из `tests_writing`, `fsm_advance.py` не тронут; сторож — `TestsWritingBlockedAfterGitFailureTest`, проверен мутацией |

## Вердикт
changes_requested — закрыть R1-F1 (блокировка перехода из `tests_writing`
после отказа git на коммите пульта у test_author). Остальное соответствует
SPEC: контракт миссии, журнал отказа git с операцией и текстом, сохранение
worktree, отказ `advance` в `in_dev` с новым текстом, сохранение
содержательной эскалации, документация, приложение-диф.

## Проверено исполнением
- `timeout 580 python3 -m pytest -q tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py tests/test_role_commit_by_pult.py tasks/01M3VFYP4RXBY0BG8D3A0B18HD/acceptance_tests/ tests/test_timeout_checkpoint.py tests/test_checkpoint_zone_filter.py tests/test_step_autocommit.py tests/test_role_prompt_test_author_mission.py tests/test_advance_guard.py tests/test_git_fixation.py`
  — 119 passed, 8 subtests passed.
- Приложение-диф извлечено из блока ```diff PLAN.md, `git apply --check -v`
  на HEAD 857a79f9 — rc=0 («Checking patch skills/coding-standards.md…»,
  «…skills/conventions-core.md…»).
- Временная мутация 1: в `pult_commit_failed_paths` убран зонный фильтр —
  `tests/test_role_commit_by_pult.py::test_stray_paths_outside_zones_do_not_count`
  красный (1 failed, 4 passed); код возвращён `git checkout`.
- Временная мутация 2: `if failed_at <= done_at` → `if failed_at == 0`
  (успех не снимает отказ) — `test_later_pult_commit_clears_failure`
  красный (1 failed, 8 passed вместе с долгоживущим pult_commit); код
  возвращён, `git status orchestrator/` чист.
- `grep -rn pult_commit_failed_paths orchestrator/ scripts/` — единственный
  вызов вне checkpoint.py: `fsm.py:304`; `grep _dirty_refuses
  orchestrator/fsm_advance.py` — строки 158/264/542, в `tests_writing`
  (340) нет — основание R1-F1.

## Предложения системе
- `checkpoint._stray_staged_paths` и новый `pult_commit_failed_paths`
  разбирают вывод git без `-z`/`core.quotePath=false`: путь с не-ASCII
  символами придёт в кавычках с октальными escape и не совпадёт с зоной
  (сверка молча fail-open). Класс общий для разборов вывода git в
  `checkpoint.py` — стоит выровнять отдельной задачей.
