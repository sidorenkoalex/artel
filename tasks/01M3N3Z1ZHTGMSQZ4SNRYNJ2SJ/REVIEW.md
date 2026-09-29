---
task: 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Долгоживущие приёмочные тесты пишутся в tests/ ветки задачи и фиксируются перечнем сумм (ADR-0020, задача 2)

## Фаза A: план

- В таблице покрытия появился шаг 10: замечания R1-F1 и R1-F2. Требования
  1–12 по-прежнему привязаны к шагам 1–9.
- «Влияние на систему» сходится с инкрементальным diff. Добавлены
  `tests/test_long_lived_transitions.py` и один метод в
  `tests/test_long_lived_manifest.py`, в `_acceptance_run_refuses`
  добавлена ветка `else`. Существующие тесты не тронуты: в диффе `tests/`
  0 удалённых строк.
- Приложение к `docs/invariants.md` (инвариант 27) теперь называет
  сторожей, которые действительно проверяют расхождение:
  `ManifestBoundariesTest`, `MergeGatePlankLockTest`,
  `TestsWritingManifestTest`. Приложения накладываются: AC-22 планки
  зелёный.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Сторож AC-3 — `TestAuthorCheckpointMandateTest.test_own_file_edit_and_delete_are_committed`: правка и удаление своего файла коммитятся |
| 2 | OK | `TestsWritingOnlyAdditionGateTest`: M/D/R, без префикса, вне `tests/`, «разовый», путь в `origin/main`. Каждый сценарий называет путь |
| 3 | OK | Без изменений с итерации 1 |
| 4 | OK | Без изменений с итерации 1 |
| 5 | OK | `LongLivedTraceabilityTest`: чужой `test_ac1` в файле базы не покрывает AC-1, свой долгоживущий файл покрывает |
| 6 | OK | `TestsWritingManifestTest`: перечень лежит в дереве коммита лока, сумма совпадает с головой. Пустой перечень тоже проверен |
| 7 | OK | `ManifestBoundariesTest.test_changed_file_refused_at_every_boundary` проверяет все пять рубежей Р4 через публичные входы. Контроль с CRLF подтверждает, что сумма считается от байтов |
| 8 | OK | `MergeGatePlankLockTest`: правка планки после лока → `("stopped",)` |
| 9 | OK | Красный долгоживущий файл отклоняет `in_dev -> verifying`, итог называет обе группы. R1-F2: без рабочей копии на ветке задачи и при непустом или непрочитанном перечне — отказ |
| 10 | OK | Без изменений |
| 11 | OK | Новая ветка `else` работает только для target `artel`: внешний target уходит в первую ветку. Для задач без лока или с пустым перечнем `long_lived_manifest` даёт `{}`, отказа нет |
| 12 | OK | AC-22 зелёный |

## Замечания

Замечаний уровня blocker и major нет. R1-F1 и R1-F2 закрыты, проверено
временными мутациями (см. ниже).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/advance_gates/tests_writing.py:276,313; orchestrator/fsm_advance.py:277,314,359,546; orchestrator/fsm.py:931; orchestrator/fsm_merge_gate.py:901,903 | Гейт «только добавление», перечень, трассируемость, рубежи Р4 и лок на гейте мержа были покрыты только планкой | — | Сторожа добавлены в `tests/test_long_lived_transitions.py` и `tests/test_long_lived_manifest.py`. Проверено 13 временными мутациями по одной, каждая краснит `tests/test_long_lived_transitions.py` (см. «Проверено исполнением») |
| R1-F2 | accepted | orchestrator/advance_gates/acceptance.py:242-256 | Без рабочей копии на ветке задачи долгоживущая группа молча выпадала из прогона | — | Добавлен отказ с журналом и подсказкой `workspace`. Мутация `if False:` краснит `test_run_refused_without_worktree_on_task_branch` |

## Вердикт

approved. Реестр закрыт. Реализация соответствует SPEC, сторожа
долгоживущих свойств лежат в `tests/` и проверены мутациями.

## Проверено исполнением

- `timeout 590 python3 -m pytest tests/test_long_lived_transitions.py tests/test_long_lived_manifest.py -p no:cacheprovider -p timeout -o timeout=120 -q`: 24 passed, 20 subtests.
- Временные мутации. Каждую вносил по одной, прогонял
  `tests/test_long_lived_transitions.py` и возвращал код (`git status`
  после прогона чист, кроме `tasks/`). Все 13 дали RED:
  - вызов `_long_lived_manifest_refuses` → `if False:`:
    - `fsm_advance.py:277`;
    - `fsm_advance.py:314`;
    - `fsm_advance.py:546`;
    - `fsm.py:931`;
  - `fsm_merge_gate.py:903` → `return False`;
  - `fsm_merge_gate.py:901`: `_acceptance_lock_refuses` отключён;
  - `tests_writing.py:296`: проверка пути в `origin/main` снята;
  - `tests_writing.py:299`: проверка строки «долгоживущий» снята;
  - `fsm_advance.py:359`: `long_lived_sources=[]`;
  - `acceptance.py:247` (R1-F2) → `if False:`;
  - `acceptance.run` без `extra=long_lived`;
  - `_tests_writing_manifest_gate` → `return None`: 9 failed;
  - `_tests_writing_long_lived_gate` → `return None`: 7 failed.
- Мутацию сторожа AC-3 в `checkpoint.py` сам не воспроизводил. Сверил
  тест с его заявкой по тексту: ассерты головы `branch_text` после правки
  и после удаления заявку фиксируют.
- `timeout 590 python3 -m pytest tasks/01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ/acceptance_tests tests/test_acceptance_tests_flow.py tests/test_amend.py tests/test_invariants.py -p no:cacheprovider -p timeout -o timeout=120 -q`: 211 passed, 266 subtests. Это вся планка, включая AC-22.
- `git diff e9dd950a..HEAD -- tests/ | grep -c '^-[^-]'` → 0: удалённых или изменённых строк в `tests/` нет.
- CI коммита aa8559b0 зелёный (из пакета).

## Предложения системе

- Сторожа переходов FSM на настоящем git (`_TransitionSandbox`) вышли
  удачными, но каждый гейт вне предмета подменяется вручную списком имён.
  Общая фикстура «переход с подменой всех гейтов, кроме X» в `tests/`
  сократила бы такие тесты и защитила бы от молчаливого устаревания
  списка при добавлении нового гейта.
