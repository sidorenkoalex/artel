---
task: 01M3VFYP4RXBY0BG8D3A0B18HD
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Единый коммит результата роли через пульт для всех провайдеров

## Подход
Механика коммита пульта (`checkpoint._commit_worktree_change`) не
меняется. Меняется только обвязка вокруг неё.

- **Диагностика отказа git.** `_commit_worktree_change` на ненулевом коде
  `add`/`reset` (exclude и снятие посторонних)/`commit` пишет запись
  журнала `PULT_COMMIT_GIT_FAILED_ACTION` = «коммит пульта не принят git».
  В детали — `git <операция> (rc=N): <stderr/stdout git>` и пометка, что
  изменения остались в worktree. Ту же фразу функция отдаёт четвёртым
  элементом возврата (раньше возвращалось три). «Нечего коммитить»
  (`diff --cached --quiet` с кодом 0) отказом не считается. Отката нет:
  worktree не трогается. Все пять вызывающих функций обновлены под
  четыре элемента возврата. Запись `TEST_AUTHOR_NOT_COMMITTED_ACTION`
  вставляет фразу git вместо прежнего «git не принял коммит»
  (требование 4).
- **advance после отказа.** Новая функция
  `checkpoint.pult_commit_failed_paths(conn, task_id)` возвращает
  незакоммиченные пути worktree, но только когда в журнале последняя
  запись отказа git новее последнего успешного коммита пульта. Не в счёт
  `tasks/<id>/` и пути вне зон задачи: их пульт не коммитит и при успехе.
  Если git не ответил на статус, возвращается `None`. Её вызывает
  `fsm._dirty_refuses` (только для догфуда) до прежней сверки артефактного
  репозитория. Непустой результат или `None` дают отказ
  «переход отклонён: результат шага не закоммичен» с перечнем путей и
  отсылкой к записи об отказе git. Прежний текст «роль обязана коммитить
  артефакты» заменён на «результат шага остался в рабочей копии
  артефактов незакоммиченным».
  Почему проверка завязана на запись об отказе git, а не на любую грязь
  worktree: иначе посторонние файлы вне зон (`STRAY_WORKTREE_FILES_ACTION`)
  или WIP ролей без мандата кода держали бы переход вечно. Это регресс
  существующих путей.
- **Порядок в `in_dev`.** `_dirty_refuses` стоит раньше
  `_in_dev_plan_escalate`, поэтому после отказа git задача не уходит в
  `escalated` (AC-3). После успешного коммита пульта признак отказа снят,
  и PLAN `escalate` уводит в `escalated`, как и раньше (AC-5).
- **Контракт роли.** В миссии developer (`role_prompt.py`, пункт 4)
  требование «закоммить код в ветку» заменено сообщением: незакоммиченный
  код worktree по итогам шага коммитит пульт.
- **Документы.** В `docs/stack.md` добавлен раздел «Коммит результата
  шага: его делает пульт». В `docs/operator-session.md` добавлен раздел
  «Отказ git на коммите пульта»: какая запись появляется в журнале и
  порядок разбора.
- **Скилы** правятся только приложением ниже (требование 7).

Бюджет не переоцениваю: шесть путей зоны, объём совпадает с оценкой SPEC.

## Шаги
1. `orchestrator/checkpoint.py`: журналирование отказа git, четыре
   элемента возврата, запись test_author с операцией и текстом git,
   `pult_commit_failed_paths`.
2. `orchestrator/fsm.py::_dirty_refuses`: отказ по незакоммиченному
   результату шага, новый текст без «роль обязана».
3. `orchestrator/role_prompt.py`: пункт 4 миссии developer.
4. `docs/stack.md`, `docs/operator-session.md`.
5. `tests/test_role_commit_by_pult.py`: пять сторожей
   `pult_commit_failed_paths` и «нечего коммитить». Каждый проверен
   временной мутацией и краснел на ней: сверка без записи отказа, отказ
   не снимается успехом, нет исключения `tasks/<id>/`, нет зонного
   фильтра, «нечего коммитить» журналируется как отказ.
6. Приложение-диф к `skills/coding-standards.md` и
   `skills/conventions-core.md` (ниже). Карта регенерирована
   (`scripts/codebase_map.py`), код закоммичен b81eb8de.

Прогоны (передний план, `-p timeout -o timeout=120`):
- долгоживущие файлы задачи + `tests/test_role_commit_by_pult.py` +
  `test_timeout_checkpoint`, `test_checkpoint_zone_filter`,
  `test_long_lived_step_end_to_end`, `test_step_autocommit`,
  `test_agent_prompt`, `test_role_prompt_test_author_mission`: 82 passed;
- `test_git_fixation`, `test_advance_guard`, `test_fsm_advance_gate_smoke`,
  `test_stack_codex_section`, `test_stack_parity_table`,
  `test_stack_zones_pull_section`, `test_pull`,
  `test_long_lived_transitions`: 92 passed;
- приёмочный `DocsDescribePultCommitTest` (AC-6): 2 passed. AC-7 читает
  PLAN.md из артефактной ветки, поэтому зеленеет после автокоммита шага.

### Возврат: конфликт подтяжки main (ANSWER-1)
- `git merge origin/main` (локальный `main` отставал — на нём
  `cycle_hint` ещё не было, конфликт воспроизводился только с
  `origin/main` 22662494). Конфликт `orchestrator/fsm.py` — только список
  `from . import (...)`: объединены `checkpoint` (ветка) и `cycle_hint`
  (main), алфавитный порядок, остальной код обеих сторон без изменений.
- `docs/codebase-map.md` взят из main и перегенерирован
  `python3 scripts/codebase_map.py`. Merge-коммит 857a79f9.
- Прогоны после подтяжки (передний план, `-p timeout -o timeout=120`):
  долгоживущие файлы задачи + `test_role_commit_by_pult` +
  `test_timeout_checkpoint`, `test_checkpoint_zone_filter`,
  `test_long_lived_step_end_to_end`, `test_step_autocommit`,
  `test_agent_prompt`, `test_role_prompt_test_author_mission`: 82 passed;
  `test_git_fixation`, `test_advance_guard`, `test_fsm_advance_gate_smoke`,
  `test_stack_*` (3), `test_pull`, `test_long_lived_transitions`,
  `test_fsm_merge_conflict_note`: 99 passed.
- Приложение-диф повторно проверено `git apply --check` на 857a79f9 — OK.

### Возврат: ревью итерации 1 (R1-F1)
- Сверка незакоммиченного результата шага вынесена из `_dirty_refuses`
  в `fsm._uncommitted_step_result_refuses(conn, task_id)`. `_dirty_refuses`
  зовёт её как раньше. Вторая точка вызова — начало
  `fsm._tests_writing_ac_state`, только для target `artel`
  (`store.task_target`). Это первая проверка выхода из `tests_writing`
  в `fsm.py`. Отказ возвращает `None`, и `fsm_advance.tests_writing`
  оставляет задачу на месте до гейтов трассируемости. Так требование 4
  («срабатывает требование 3», задача не переходит) выполняется и для
  test_author.
- Почему в `_tests_writing_ac_state`, а не новым вызовом в
  `fsm_advance.tests_writing`: `fsm_advance.py` не входит в зоны SPEC, и
  гейт зон отказал бы на `in_dev -> review`. Привязка к этой функции не
  случайна. Она считает покрытие AC по долгоживущим файлам с кодовой
  ветки (`long_lived_sources`), а после отказа git этих файлов на ветке
  нет. Считать покрытие в таком состоянии нельзя: задача либо уйдёт мимо
  лока, либо получит отказ с ложной причиной «не все критерии покрыты».
  Других вызывающих у функции нет (`grep _tests_writing_ac_state(`).
- Сторож: `tests/test_role_commit_by_pult.py::TestsWritingBlockedAfterGitFailureTest`.
  Хук `pre-commit` отказывает коммиту долгоживущего файла test_author,
  затем хук снимается, и `advance` из `tests_writing` должен оставить
  задачу в `tests_writing` с отказом «результат шага не закоммичен», где
  назван путь файла. Проверен временной мутацией (вызов в
  `_tests_writing_ac_state` отключён): тест красный (1 failed, 5 passed),
  код возвращён.
- Карта регенерирована, коммит b826fbbf.
- Прогоны (передний план, `-p timeout -o timeout=120`):
  долгоживущие файлы задачи, `test_role_commit_by_pult`, приёмочные
  задачи, `test_acceptance_tests_flow`, `test_long_lived_step_end_to_end`,
  `test_long_lived_transitions`, `test_id_format_guard`,
  `test_advance_guard`, `test_git_fixation`: 167 passed;
  `test_fsm_advance_tests_writing_*` (3), `test_fsm_advance_gate_smoke`,
  `test_long_lived_manifest`, `test_multitarget`: 89 passed.
- Попутно: вызывающих `_commit_worktree_change` четыре, а не пять, как
  было написано в шаге «Подход» (замечание фазы A ревью).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 3 |
| 2 | 1 (успешный путь не меняется, тест AC-2 зелёный) |
| 3 | 1, 2 |
| 4 | 1; возврат R1-F1 (блокировка выхода из `tests_writing`) |
| 5 | 2 (порядок `_dirty_refuses` → эскалация), тест AC-5 |
| 6 | 4 |
| 7 | 6 |

## Влияние на систему
- `_commit_worktree_change` — общая обвязка всех WIP-чекпоинтов
  (таймаут, аварийный, `pause --now`, подтяжка main, успешный шаг). Для
  них поведение git не меняется. Прибавилась только запись журнала на
  отказ git; вызывающие функции получают четвёртый элемент возврата и
  его игнорируют. Тесты не патчат `_commit_worktree_change`, поэтому
  смена формы возврата их не задевает.
- `fsm._dirty_refuses` вызывается на трёх переходах: `spec_writing`,
  `review`, `in_dev`. Новая сверка срабатывает только при свежей записи
  отказа git, без неё это прежняя сверка. Гейт ничего не ослабляет, он
  добавляет отказ. Та же сверка
  (`_uncommitted_step_result_refuses`) стоит и на выходе из
  `tests_writing`, в начале `_tests_writing_ac_state`. Без свежей записи
  отказа git она возвращает «нет отказа», и прежний путь не меняется.
- Новый отказ снимается сам, когда пульт успешно закоммитил код или
  worktree по зонам чист. Залипания нет; это проверяет тест
  `test_later_pult_commit_clears_failure`.
- Откат — revert коммитов b81eb8de и b826fbbf.

## Риски
- Если git не ответил на `status` worktree при свежей записи отказа,
  переход отклоняется (fail-closed). Пример: worktree удалён после
  отказа. Отказ печатается и журналируется с текстом «git не ответил на
  статус worktree». Разбор описан в `docs/operator-session.md`.
- Запись отказа git у test_author дублируется: общая запись и
  `TEST_AUTHOR_NOT_COMMITTED_ACTION`. Это сознательно: требование 4
  говорит «срабатывает требование 3», а вторая запись нужна для смысла
  именно для test_author.

## Приложение: skills/coding-standards.md и skills/conventions-core.md

Убирает требование, что ход разработчика должен заканчиваться коммитом
кода, и квалификацию коммита пультом как дефекта шага. Правит строку
«Коммитишь только код» и регенерацию карты «тем же коммитом». Проверено:
`git apply --check` на чистом дереве ветки (голова b81eb8de) проходит.

```diff
diff --git a/skills/coding-standards.md b/skills/coding-standards.md
index 8b8e7b90..116223fd 100644
--- a/skills/coding-standards.md
+++ b/skills/coding-standards.md
@@ -130,10 +130,13 @@ PLAN вправе один раз, при первой сдаче, поднят
   `doctor` без изменяющих флагов) с зафиксированным сравнением.
 
 ## Завершение хода
-- Ход разработчика заканчивается коммитом кода. Если шаг завершился
-  без коммита, незакоммиченный код закоммитит сам пульт и запишет это
-  в журнал как дефект шага — не как норму (SPEC
-  01M283NC4JJXK7QS68Y9ET8TBK).
+- Коммитить код самому не обязательно: код, оставленный в worktree
+  незакоммиченным, по итогам шага коммитит пульт существующим механизмом
+  `checkpoint.py` (SPEC 01M283NC4JJXK7QS68Y9ET8TBK,
+  01M3VFYP4RXBY0BG8D3A0B18HD) — это норма, не дефект шага. Свой коммит
+  тоже допустим: пульту тогда нечего коммитить.
+- Отказ git на коммите пульта — не твоя эскалация: пульт пишет его в
+  журнал с операцией и текстом git, а результат шага остаётся в worktree.
 
 ## Комментарии
 - Комментарий объясняет «почему», код объясняет «что». Комментарии-пересказ
diff --git a/skills/conventions-core.md b/skills/conventions-core.md
index b50988e4..e43a8d0f 100644
--- a/skills/conventions-core.md
+++ b/skills/conventions-core.md
@@ -29,10 +29,12 @@
 - Коммиты: `<id>: <что сделано>` — по-русски, по делу, без «фиксы».
 - Артефакты `tasks/<id>/` в кодовую ветку НЕ коммитишь (SPEC
   01M1NKTF173WV5CPDZ1C3WW69K): единственный путь артефактов в git —
-  автокоммит оркестратора в артефактную ветку по итогам шага. Коммитишь
-  только код — там, где твоя роль его меняет.
+  автокоммит оркестратора в артефактную ветку по итогам шага. Код, который
+  меняет твоя роль, коммитить самому не обязательно: оставленный в
+  worktree незакоммиченным, его по итогам шага коммитит пульт
+  (SPEC 01M3VFYP4RXBY0BG8D3A0B18HD).
 - Правишь `*.py` в orchestrator/, scripts/ или tests/ — регенерируй
-  карту тем же коммитом: `python3 scripts/codebase_map.py` (иначе
+  карту в том же шаге: `python3 scripts/codebase_map.py` (иначе
   CI-джоб свежести красит твою ветку; карту на merge в main чинит
   оркестратор — T042; T028/T029 — два улова).
 - То же самое правило действует, если `orchestrator/`, `scripts/` или
```

## Предложения системе
- `docs/invariants.md` / `checkpoint.py`: несколько докстрингов
  WIP-чекпоинтов всё ещё описывают «тихую деградацию без git». Теперь
  отказ git журналируется. Тексты стоит выровнять отдельной
  документационной правкой: в эту задачу она не вошла, чтобы не
  раздувать дифф.
- Окружение шага: `ls`/`cat` недоступны в shell роли, а `/bin/ls` требует
  подтверждения, которого в шаге никто не даст. Перечень файлов
  приходилось получать через `git status --porcelain -uall`.
