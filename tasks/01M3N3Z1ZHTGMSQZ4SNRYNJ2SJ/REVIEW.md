---
task: 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Долгоживущие приёмочные тесты пишутся в tests/ ветки задачи и фиксируются перечнем сумм (ADR-0020, задача 2)

## Фаза A: план

- Таблица покрытия PLAN полна: требования 1–12 привязаны к шагам 1–9.
- Шаги по размеру годятся для MR. Подход «одно правило — один узел»
  (`guard` для Р1/Р2, `_long_lived_manifest_refuses` для Р4) соответствует
  архитектуре гейтов (`_run_gates`, `GateRefusal`).
- «Влияние на систему» сходится с diff. Изменены три существующих теста.
  В каждом перенесена только предпосылка (коммит «кода фичи» после выхода
  из `tests_writing`, группа исправленного файла планки), ассерты не
  тронуты. Колонок БД нет, откат — revert merge-коммита.
- Все четыре приложения накладываются: `git apply --check` на чистом
  дереве. Это подтверждает AC-22 планки, он зелёный.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `checkpoint._test_author_own_paths`/`_test_author_checkpoint` подключены к WIP-чекпоинтам и к `commit_success_checkpoint`. Переименование засчитывается своим только целиком. Сторож в `tests/` покрывает свой коммит, откат правки базы и откат вне `tests_writing`. AC-3 (правка и удаление своего) покрыт только планкой, см. R1-F1 |
| 2 | OK (без сторожа в tests/) | `_diff_entry_error` + `_tests_writing_long_lived_gate` (tests_writing.py:255, :276). Проверка по `origin/main` идёт через `diff_base_source`. Сторожа в `tests/` нет, см. R1-F1 |
| 3 | OK | `long_lived_errors_from_files` над текстами с головы; сухой сбор одним вызовом `collect(..., extra=)` |
| 4 | OK | `guard.long_lived_plank_errors` в `_tests_writing_test_groups_gate`, подсказка с конкретным префиксом |
| 5 | OK (без сторожа в tests/) | Добавлен `extra_sources`/`long_lived_sources`: в него попадают только `A`-файлы с префиксом задачи. Сторожа в `tests/` нет, см. R1-F1 |
| 6 | OK (без сторожа в tests/) | `_tests_writing_manifest_gate` стоит последним гейтом до `set_state in_dev`; суммы считаются по байтам блоба. Сторожа в `tests/` нет, см. R1-F1 |
| 7 | OK | Узел один, вызывается на всех пяти рубежах Р4 (fsm_advance.py:546, :314, :277; fsm.py:931; fsm_merge_gate `_acceptance_locks_refuse`). Сбой git даёт отказ. Проводку рубежей сторожит только планка, см. R1-F1 |
| 8 | OK | `_acceptance_lock_refuses` на гейте мержа после `_sync_main_or_wait`. В `tests/` проверен только путь сбоя git, расхождение не проверено, см. R1-F1 |
| 9 | OK с оговоркой | Прогон один, итог называет обе группы. Если worktree не на ветке задачи, долгоживущая группа молча выпадает, см. R1-F2 |
| 10 | OK | Пункт 2а у test_author и строка у developer: префикс конкретный |
| 11 | OK | Узел, гейт мержа и `tests_writing` ограничены target `artel`; у `skip_tests` нет лока, сверка проходит |
| 12 | OK | Четыре приложения, `git apply --check` проходит (AC-22) |

## Замечания

- **major — нет сторожа в `tests/` для гейтов выхода из `tests_writing`, записи перечня и проводки рубежей Р4.**
  - Где:
    - `orchestrator/advance_gates/tests_writing.py:255`, `:276`, `:313`;
    - `orchestrator/fsm_advance.py:277`, `:314`, `:359`, `:546`;
    - `orchestrator/fsm.py:931`;
    - `orchestrator/fsm_merge_gate.py` (`_acceptance_locks_refuse`, ветка расхождения лока).
  - Суть. Эти свойства должны держаться после мержа (инвариант 27, по
    приложению PLAN). Сейчас их проверяет только планка, а все её файлы
    помечены `Группа: разовый`. После мержа планку не гоняет ни один
    джоб CI (review-checklist «Долгоживущие свойства — в `tests/`»).
  - Проверено временной мутацией:
    - гейт «только добавление» `_tests_writing_long_lived_gate` → `return None`;
    - запись перечня `_tests_writing_manifest_gate` → `return None`;
    - все четыре вызова `_long_lived_manifest_refuses` в `fsm_advance.py` → `pass`.

    Прогнал `tests/test_long_lived_manifest.py`, `test_acceptance_tests_flow`,
    `test_amend`, `test_fsm_advance_tests_writing_test_groups` и
    `test_invariants`: 199 passed, ни один не покраснел. `grep` по `tests/`
    находит новые гейты только в `test_long_lived_manifest.py`, и там
    тестируется лишь сам узел сверки.
  - Сценарий. Позднейший рефакторинг `fsm_advance.tests_writing` теряет
    элемент списка `gates` или вызов узла на `verifying`. Тогда
    test_author правит файл базы, а developer — долгоживущий файл после
    лока, и оба проходят в main при зелёном CI.
  - Приложение к `docs/invariants.md` называет сторожем инварианта 27
    `test_long_lived_manifest.MergeGateLocksTest`. Он проверяет только сбой
    git лока, а не расхождение лока или перечня на гейте мержа (AC-14,
    AC-18).
  - Что сделать — добавить в `tests/` (не в планку) сторожей с заявками «Ловит мутацию»:
    - отказ `tests_writing -> in_dev` на `M`/`D`/`R`, на путь вне
      `tests/`, на файл без префикса, на путь из `origin/main`, на файл
      без строки «долгоживущий»;
    - перечень есть в дереве коммита `tests_locked_sha`, в том числе пустой;
    - трассируемость: метод `test_ac<n>` своего долгоживущего файла
      покрывает критерий, а файл без префикса — нет;
    - отказ на каждом рубеже Р4 при изменённом файле, через публичные
      `fsm_advance.in_dev`/`verifying`/`review`, `fsm._approve_acceptance`
      и гейт мержа;
    - расхождение лока каталога на гейте мержа;
    - правка и удаление своего файла коммитятся (AC-3).

    Годятся фикстуры `_WorktreeCheckpointTest` и уже написанные
    `lock_with`. Сторож проверить той же временной мутацией.
- **minor — `orchestrator/advance_gates/acceptance.py:232`: долгоживущая группа молча выпадает из прогона.**
  - Суть. Если `workspace.on_task_branch(...)` не `True` (worktree
    утрачен или git не ответил), прогон идёт из `config.ROOT` без
    `extra`. Долгоживущие файлы перечня не исполняются, и в итоге нет
    строки групп. Отказа или записи в журнал об этом нет.
  - Последствие ограничено: `verifying` всё равно ждёт зелёного CI,
    который гоняет `tests/` ветки. Но требование 9 («исполняются в одном
    прогоне») в этом пути нарушено без следа.
  - Что сделать. Если в перечне есть записи, а рабочая копия не на ветке
    задачи, отказывать так же, как это уже делает
    `_tests_writing_long_lived_gate` (tests_writing.py, «рабочая копия …
    не выписана»). Как минимум — писать отметку в `detail` журнала.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/advance_gates/tests_writing.py:255,276,313; orchestrator/fsm_advance.py:277,314,359,546; orchestrator/fsm.py:931; orchestrator/fsm_merge_gate.py (`_acceptance_locks_refuse`) | Гейт «только добавление», запись перечня до лока, трассируемость по долгоживущим файлам, проводка рубежей Р4 и расхождение лока на гейте мержа покрыты только планкой (вся — «разовый»). Временная мутация всех трёх узлов не покраснила ни одного теста `tests/` | После мержа эти свойства без сторожа: регресс проводки в `fsm_advance` пропускает правку тестов мимо лока при зелёном CI (инвариант 27) | Добавить сторожей в `tests/` на каждое перечисленное свойство с «Ловит мутацию», проверить временной мутацией |
| R1-F2 | open | orchestrator/advance_gates/acceptance.py:232 | Если worktree не на ветке задачи, прогон `in_dev -> verifying` идёт без долгоживущих файлов перечня, молча | Требование 9 не выполняется в этом пути, в журнале нет следа | Отказ (как на выходе `tests_writing`) при непустом перечне и невыписанной рабочей копии, либо явная отметка в журнале |

## Вердикт

changes_requested. Нужно закрыть R1-F1: сторожа в `tests/` на гейт
выхода из `tests_writing`, запись перечня, трассируемость, рубежи Р4 и
лок на гейте мержа. R1-F2 — minor, но желательно закрыть в той же
итерации. Реализация по сути соответствует SPEC, планка зелёная.

## Проверено исполнением

- `timeout 590 python3 -m pytest tasks/01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ/acceptance_tests tests/test_long_lived_manifest.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 46 passed, 56 subtests passed. Это вся планка, включая AC-22 с `git apply --check` приложений.
- Временная мутация: `_tests_writing_long_lived_gate` и
  `_tests_writing_manifest_gate` → `return None`; четыре вызова
  `_long_lived_manifest_refuses` в `orchestrator/fsm_advance.py` → `pass`.
  - Под мутацией прогнал `tests/test_long_lived_manifest.py`,
    `tests/test_acceptance_tests_flow.py`, `tests/test_amend.py`,
    `tests/test_fsm_advance_tests_writing_test_groups.py`,
    `tests/test_invariants.py`: 199 passed, 222 subtests. Сторожа нет, это
    основа R1-F1.
  - Код возвращён: `git checkout -- …`, `git status` чист, кроме `tasks/`.
- `grep -rln "long_lived_gate|manifest_gate|_tests_writing_code_diff|long_lived_sources|extra_sources|_long_lived_manifest_refuses" tests/` находит только `tests/test_long_lived_manifest.py`.
- Diff `tests/` сверен глазами на ослабление. Удалённых ассертов нет.
  - `test_acceptance_tests_flow.LockTest` и `test_amend.AmendThenReviewGateTest`: коммит кода перенесён после лока.
  - `test_fsm_advance_tests_writing_test_groups`: группа исправленного файла сменена на «разовый».

## Предложения системе

- Сейчас планка задачи вся помечена «разовый», хотя проверяет свойства
  кода (гейты, проводку FSM). По ADR-0020 это неверная граница групп, но
  после лока исправить её может только Оператор. Автору тестов стоит
  напоминать об этом при выборе группы (`skills/test-authoring.md`).
  Иначе сторожей в `tests/` приходится добирать на ревью, как здесь.
