---
task: 01M41AB597B330P2RCXCMVRZPE
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Перефиксация не узаконивает сдвиг ссылки документов мимо пульта

## Подход
Один узел сверки `orchestrator/fixation.py::ref_drift(conn, task_id)`:
читает голову `refs/artifacts/<id>` через `fixation.read` (→
`artifact_branch.ref_head`, репозиторий задачи: для внешнего target — git
проекта, для задачи артели — git главной копии, требование 7) и сравнивает
с `tasks.fixed_sha`. Возврат: `None` — фиксации нет или голова совпала;
`RefDrift(fixed, head)` — расхождение (`head` пуст — git не ответил,
`moved=False`; иначе сдвиг мимо пульта). Рядом — общие помощники вывода:
`journal_drift` (запись журнала с именованной причиной
`DOCS_REF_INCIDENT_ACTION` «инцидент целостности: ссылка документов
сдвинута мимо пульта» или `DOCS_REF_UNREAD_ACTION`), `incident_refusal`
(именованный отказ с обоими sha и подсказкой `approve <id> <sha>`),
`stop_on_moved_ref` (вход команд Оператора), `legitimize` (выход Оператора
через `approve <id> <sha>`).

Все записи пульта, перефиксирующие документы, зовут этот узел ДО записи:
- `store.set_state`: при сдвиге переход в `escalated`/`killed` идёт без
  паспорта и фиксации; любой другой переход вместо себя уводит задачу в
  `escalated` (уже эскалированная остаётся, журнал «переход … не
  выполнен») и бросает `store.DocsRefIncident` (`SystemExit` — именованный
  отказ команды). Голова не прочитана — переход идёт, паспорта и
  `record_fixation` нет: прежняя фиксация остаётся, сверка на старте шага
  остаётся fail-closed (требование 5).
- `answer`/`zones-extend` (`answer.py`), `amend-tests` (оба режима
  `amend.py`) — `fixation.stop_on_moved_ref` первой строкой после проверки
  аргументов: ничего не коммитится, рабочая задача уходит в эскалацию
  (через `set_state`, без паспорта), эскалированная остаётся; отказ с
  именем причины.
- `snapshot.commit_closing`, `doctor/ignored_artifacts._fix_ignored_artifact_files`,
  `checkpoint` (`harvest_code_copy_docs`, `_record_step_fixation`,
  `_commit_external_step_artifacts`, `commit_pull_checkpoint`) — при
  расхождении записи нет, журнал с причиной. Прежняя
  `checkpoint._docs_ref_moved_past_pult` (своя копия сравнения) заменена
  тонкой обёрткой `_docs_ref_drift` над узлом (требование 3, AC-6).
  `_commit_step_artifacts_to_branch` зовут только `harvest_code_copy_docs`
  и `_commit_external_step_artifacts` — оба сверяют узлом до вызова.
- Гейт перечня долгоживущих тестов (`advance_gates/tests_writing.py`)
  тоже коммитит в ссылку на переходе: при сдвиге перечень не пишется
  (переход ниже уводит в инцидент), а свой законный коммит он
  перефиксирует сам (требование 4) — иначе следующий `set_state` принял
  бы его за сдвиг.
- `kill` (`cleanup._cmd_kill`, требование 10): при сдвиге вместо сверки с
  `origin` (она досылала бы подмену в `origin`) — `_warn_moved_ref`:
  журнал инцидента с sha подменённой головы, именованное предупреждение в
  выводе; `set_state("killed")` без паспорта и фиксации, `commit_closing`
  не пишет коммит закрытия; ссылка с подменённой головой не удаляется.
- Выход Оператора (требование 6): `fsm._cmd_approve` после
  `confirm_fixation` с явным sha зовёт `fixation.legitimize` —
  `fixed_sha` := живая голова, журнал «голова ссылки документов узаконена
  Оператором»; без sha `confirm_fixation` по-прежнему отказывает с обоими
  sha. Подсказка `runner._refuse_before_start` уже несёт живой sha
  (`approve_sha_hint`) — поправлен только комментарий.

Бюджет SPEC не пересматривается.

## Шаги
1. Узел `fixation.ref_drift` + помощники; `store.set_state` с инцидентом
   и `DocsRefIncident`; `approve <sha>` → `legitimize`.
2. Вызовы узла во всех записях требования 1 (answer, zones-extend,
   amend-tests ×2, snapshot, doctor --fix, чекпоинты, гейт перечня), замена
   `_docs_ref_moved_past_pult`.
3. `kill` при сдвиге: предупреждение, закрытие без коммитов поверх
   подмены, голова сохранена.
4. Тестовые песочницы существующих тестов, где коммит в ссылку изображал
   запись пульта без перефиксации, получили `store.record_fixation` после
   такого коммита (см. «Влияние на систему»); `docs/codebase-map.md`
   регенерирован.
5. Прогон долгоживущих тестов задачи и тестов затронутых модулей.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 2 |
| 3 | 1, 2 |
| 4 | 1, 2 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | — (инвариант 25 не меняется, см. ниже) |
| 9 | 5 |
| 10 | 3 |

Требование 8: формулировка инварианта 25 («фиксация = голова ссылки,
сдвиг — инцидент») уже покрывает новое поведение; код лишь перестаёт её
нарушать. Приложения к `docs/invariants.md`/`tests/test_invariants.py`
нет, поэтому AC-12 не применяется (проверка `git apply --check` не
требуется).

Требование 9 / AC-1..AC-13: долгоживущий файл задачи
`tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py`
(test_author, под локом, с заявками «Ловит мутацию»). Собственных новых
тестов разработчик не добавлял — свойства покрыты этим файлом.
Дополнен докстринг-заявкой один существующий метод
`tests/test_step_refixation.py::SuccessfulTransitionUnaffectedTest::test_no_extra_refixation_journal_on_success`
(утверждения не менялись).

Прогоны (`python3 -m pytest … -p no:cacheprovider -p timeout -o timeout=120`):
- `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py` — 18 passed;
- test_step_refixation, test_answer, test_answer_gate, test_answer_branch_reads,
  test_amend, test_amend_long_lived, test_amend_remove,
  test_long_lived_transitions, test_git_fixation, test_cas_set_state,
  test_kill_cleanup, test_snapshot_closing_outcome,
  test_doctor_fix_ignored_artifacts — 171 passed;
- test_step_autocommit, test_timeout_checkpoint,
  test_fsm_merge_gate_done_snapshot, test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir,
  test_01m409ynswacnfknje2x263zsd_project_docs_ref, test_docs_dir_layout,
  test_artifact_ref_sync, test_checkpoint_external_step_artifacts,
  test_invariants, test_long_lived_step_end_to_end — 183 passed;
- test_acceptance_tests_flow, test_multitarget, test_pull,
  test_kill_live_cycle_refusal — 156 passed;
- test_doctor, test_fsm_retro, test_auto_cycle, test_role_commit_by_pult,
  test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit, test_codebase_map,
  test_fsm_advance_gate_smoke — 232 passed.
Полный набор `tests/` в шаге не запускался (правило 05.09) — его гоняет CI.

## Влияние на систему
- Инвариант 25 усилен, не ослаблен: перефиксация теперь возможна только
  записью пульта поверх зафиксированной головы или решением Оператора
  `approve <id> <sha>`. Сверка на старте шага (`check_integrity`) не
  тронута.
- `store.set_state` получил один git-вызов (`rev-parse` головы ссылки) на
  переход — тот же, что `record_fixation` и так делал.
- Существующие тесты: в 7 файлах (`test_acceptance_tests_flow`,
  `test_amend`, `test_amend_long_lived`, `test_amend_remove`,
  `test_answer`, `test_long_lived_transitions`, `test_step_refixation`) в
  помощниках песочниц, которые коммитили в ссылку `artifact_branch.
  commit_files`/git напрямую, изображая автокоммит пульта, добавлен
  `store.record_fixation` после коммита — как делает настоящий автокоммит.
  Без этого такой коммит теперь (правильно) выглядит сдвигом мимо пульта.
  Ни одно утверждение, ни один метод не удалён и не переименован.
- Откат — revert merge-коммита задачи; схема БД не менялась.

## Риски
- `DocsRefIncident` — `SystemExit`: вызыватель `set_state`, который
  ловит `SystemExit` и продолжает, продолжил бы после инцидента.
  Перехваты в `orchestrator/`: `auto.py:996` (вокруг `runner.cmd_run` —
  печатает отказ и выбирает остановку; задача к этому моменту уже в
  `escalated`, цикл дальше её не ведёт), `auto.py:662` (журнал обрыва и
  повторный `raise`), `notes.py:1208` (не на пути переходов задачи). В
  любом случае задача уже в `escalated`, фиксация и голова не тронуты.
- `_commit_step_artifacts_to_branch` сам узел не зовёт — полагается на
  сверку двух своих вызывателей; новый вызыватель должен сверять так же.

## Предложения системе
- Шаг developer этой задачи ушёл в таймаут с готовым кодом, но без
  PLAN.md (WIP-чекпоинт e330691b): миссии разработчика стоит советовать
  писать PLAN.md первым, до реализации, — тогда таймаут не теряет план.
