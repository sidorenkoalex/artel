---
task: 01M3Z2DMQRD0BD7AARFVTCVVG8
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: ADR-0021, этап 1 (а) — документы задачи в одной ссылке refs/artifacts/<id>

## Фаза A — план
- Таблица покрытия требований 1–8 полная, шаги размера MR, подход
  согласуется с ADR-0021 п.3/12/13 (один узел записи, закрытие коммитом
  RETRO, сверка с origin, doctor на ссылке). Приложение к
  `docs/invariants.md` — по таблице п.12, оговорки ANSWER-1 (внешний target
  отправляется в origin пульта; «(или грязная копия)» в 25) учтены.
- Раздел «Покрытие требований» PLAN утверждает лишнее: «AC-2/AC-3 —
  `test_artifact_branch_push.py`», «AC-6 — `test_merge_gate_ci_wait.py`
  (узел сверки в теле гейта)». В диффе `test_artifact_branch_push.py`
  поменялась только подготовка `PushNonFastForwardTest`. Сам файл проверяет
  явный `push()`, а не CAS и не автоматическую отправку. В
  `test_merge_gate_ci_wait.py` `_docs_ref_unsynced` подменён на `False`, то
  есть отказ там не проверяется. Подробно — R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `branch_name` → `refs/artifacts/<id>`, первый коммит без родителя (`_write`, `parent or None`), `gitcmd.qualified_ref` для чтения; планка AC-1/AC-9 зелёная |
| 2 | OK по коду, сторожа в `tests/` нет | `update-ref <ref> <new> <old>` + `_CAS_ATTEMPTS`, `_send` после коммита, `send_pending` в `set_state`; все пишущие места идут через `commit_files`/`commit_change`. Ни CAS, ни повтор отправки не держит ни один тест `tests/` (R1-F1) |
| 3 | OK, замечание minor | `snapshot.commit_closing` поверх головы, журнал `CLOSING_ACTION`, исход берётся из БД, снимка и `drop` нет; отказ гейта и `kill` по `origin_sync_refusal`. Если не прошла отправка самого коммита закрытия, повтора нет (R1-F2) |
| 4 | OK | `fixation.fix/read` = голова ссылки; `tests_locked_sha` = `branch_head_sha(ref)` после `set_state` (`fsm_advance.py:429`); паспорт пишется до `record_fixation` |
| 5 | OK | `check_artifact_ref_sync`: живая задача ≠ origin, закрытая ≠ коммит закрытия; orphan/CI/pending-снимки сняты. В `recovery_check` есть ослабление (R1-F3) |
| 6 | OK | исторические снимки не сверяются (нет записи `CLOSING_ACTION`), канарейка идёт тем же потоком |
| 7 | OK | приложение 25/27/28/33/34/38, планка AC-11 зелёная |
| 8 | Не полностью | удаления и изменённые утверждения покрыты мандатом ANSWER-1 и сверены с таблицами PLAN. Но поведения AC-2, AC-3 и AC-6 в `tests/` не покрыты (R1-F1) |

Сверка изменённых утверждений с base (14 методов из раздела гейта): все
перечислены в таблице «Изменены утверждения» PLAN и приняты ANSWER-1 п.2.
Новые формы проверяют свойства ADR-0021 (потомок прежней головы, ссылка в
origin), а не ослабленные. Удалённые 32 метода совпадают с мандатом
ANSWER-1 п.1 поимённо. Сужения данных под неизменными утверждениями не
нашёл: `test_step_refixation` убрал лишний коммит вне окна шага, а
`CommitCommitterDatesTest.repo()` указывает на `config.ROOT`, где теперь
живёт ссылка.

## Замечания

- **major** — `orchestrator/artifact_branch.py:188` (`_write`: `update-ref`
  со сверкой и повтор), `:297` (`_send` после коммита, журнал отказа),
  `:312` (`send_pending`), `:321` (`origin_sync_refusal`);
  `orchestrator/fsm_merge_gate.py:1027` (`_docs_ref_unsynced`);
  `orchestrator/cleanup.py:405` (`_refuse_unsynced_docs`);
  `orchestrator/store.py` (`_append_passport_line` → `send_pending`). У этих
  долгоживущих свойств нет сторожа в `tests/`. Все файлы планки помечены
  `Группа: разовый`, после мержа их не гоняет ни CI, ни автогейт
  (ADR-0018 п.3). SPEC, требование 8: «Тесты в `tests/` на каждое поведение
  из критериев». Проверено временными мутациями в процессе pytest, код не
  правился:
  1. `origin_sync_refusal` всегда возвращает `None` (гейт мержа и `kill`
     больше не отказывают). Прогон `test_merge_gate_ci_wait`,
     `test_snapshot_closing_outcome`, `test_fsm_merge_gate_done_snapshot`,
     `test_multitarget_invariants`, `test_01m3sf7…_main_ci`,
     `test_artifact_branch_push`, `test_doctor_artifact_branch_sync` —
     78 passed.
  2. `update-ref` без прежнего значения (CAS снят). Прогон 7 файлов, в том
     числе `test_artifact_branch_push`, `test_amend`, `test_git_fixation`,
     `test_step_refixation` — 117 passed.
  3. `send_pending` ничего не делает (повтора отправки на переходе нет).
     Прогон 6 файлов — 76 passed.

  Чем грозит: следующая правка узла записи или гейта мержа может молча
  вернуть потерю правок в гонке, закрытие задачи с документами только в
  одном месте или вечно неотправленную ссылку, и ни один тест не
  покраснеет. Что сделать: добавить в `tests/` тесты (на реальном git с
  bare-origin, как в `AutoOriginSandbox`) с заявками «Ловит мутацию: …» на
  (а) гонку двух записей от одной головы: обе правки в истории, история
  линейна; (б) коммит → ссылка в origin; отказ push → запись журнала,
  коммит цел; следующий `set_state` досылает; (в) гейт мержа и `kill`
  отказывают именованно при расхождении и при отсутствии ссылки в origin
  (журнал `MERGE_UNSYNCED_JOURNAL_ACTION`/`KILL_UNSYNCED_JOURNAL_ACTION`,
  состояние не меняется), при совпадении проходят. Исправить раздел
  «Покрытие требований» PLAN.
- **minor** — `orchestrator/snapshot.py:75` / `orchestrator/cleanup.py:441`.
  Коммит закрытия пишется уже после терминального перехода. Если его
  отправка откажет (журнал запишет), досылать некому: `send_pending` висит
  на `set_state`, а у закрытой задачи переходов больше нет. `doctor` покажет
  WARN «закрытая … в origin не совпадает с коммитом закрытия», но
  `doctor --fix` ссылку не дошлёт. Итоговый RETRO останется только
  локально, а требование 2 обещает повтор на следующем переходе. Что
  сделать: досылать закрытую ссылку в `doctor --fix` (или в самой
  проверке), если локальная голова = коммит закрытия, а origin отстаёт.
- **minor** — `orchestrator/doctor/recovery.py:41`. `sha_mismatch` требует
  `is_ancestor(fixed_sha, current)`. Если ссылку переписали на коммит, не
  являющийся потомком зафиксированного (`update-ref`/force мимо пульта —
  тот самый случай подмены), `recovery-sha` молчит: этот sha принимается
  за фиксацию прежнего устройства. Первый рубеж (`check_integrity` на
  старте шага) такой случай ловит, ослаблен только doctor. Что сделать:
  отличать фиксацию прежнего устройства по отсутствию объекта в
  `config.ROOT` (`git cat-file -e <sha>^{commit}`), а не по «не предок».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/artifact_branch.py:188, :297, :312, :321; orchestrator/fsm_merge_gate.py:1027; orchestrator/cleanup.py:405 | CAS, автоматическая отправка с повтором и отказ гейта мержа/`kill` при ссылке ≠ origin без сторожа в `tests/` (планка вся «разовый»); три временные мутации зелёные | регресс узла записи или гейта после мержа пройдёт незамеченным: потеря правок в гонке, закрытие с документами в одном месте | тесты в `tests/` на AC-2, AC-3, AC-6 с заявками «Ловит мутацию»; поправить раздел «Покрытие требований» PLAN |
| R1-F2 | open | orchestrator/snapshot.py:75 | отправку коммита закрытия, если она не прошла, никто не повторяет | RETRO закрытой задачи только локально, `doctor` лишь предупреждает | досылка закрытой ссылки в `doctor --fix` |
| R1-F3 | open | orchestrator/doctor/recovery.py:41 | `recovery-sha` молчит, если зафиксированный sha не предок головы | переписанная мимо пульта ссылка не видна в `doctor` | отличать прежнее устройство по отсутствию объекта, а не по «не предок» |

## Вердикт
changes_requested — закрыть R1-F1 (тесты в `tests/` на AC-2, AC-3, AC-6).
R1-F2 и R1-F3 — minor, закрыть или отклонить с обоснованием.

## Проверено исполнением
Во всех прогонах `ARTEL_ROLE` снят из окружения процесса pytest.
- Планка `tasks/01M3Z2DMQRD0BD7AARFVTCVVG8/acceptance_tests/` — 46 passed
  (177 с).
- Затронутые модули: `test_artifact_branch_push`,
  `test_doctor_artifact_branch_sync`, `test_snapshot_closing_outcome`,
  `test_fsm_merge_gate_done_snapshot`, `test_merge_gate_ci_wait`,
  `test_git_fixation`, `test_step_refixation`, `test_amend`,
  `test_amend_remove`, `test_doctor`, `test_multitarget_invariants`,
  `test_retro_artifact_branch_reads`,
  `test_checkpoint_external_step_artifacts`, `test_01m3sf7…_main_ci` —
  303 passed, 3 subtests passed.
- Временные мутации (монкипатч в процессе pytest, файлы не правились,
  `git status` чистый, кроме `tasks/`):
  1. `origin_sync_refusal → None` — 78 passed, сторожа нет.
  2. `update-ref` без old — 117 passed, сторожа нет.
  3. `send_pending → no-op` — 76 passed, сторожа нет.
  4. Контроль: `_send → no-op` вместе с CAS-мутацией — 10 failed
     (`test_doctor_artifact_branch_sync`, `test_snapshot_closing_outcome`),
     то есть сама отправка после коммита косвенно покрыта.

## Предложения системе
- `skills/test-authoring.md`: в этой задаче test_author пометил «разовым»
  каждый файл планки, в том числе свойства кода (CAS, отказ гейта мержа).
  Граница групп ADR-0020 на долгоживущие свойства не сработала, и сторожа
  после мержа не осталось. Стоит, чтобы автогейт выхода из `tests_writing`
  предупреждал о планке, где нет ни одного долгоживущего файла, а у SPEC
  есть критерии поведения кода.
