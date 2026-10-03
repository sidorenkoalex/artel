---
task: 01M3Z2DMQRD0BD7AARFVTCVVG8
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: ADR-0021, этап 1 (а) — документы задачи в одной ссылке refs/artifacts/<id>

## Фаза A — план
- Таблица покрытия требований 1–8 полная. Новые шаги 7 (возврат из ревью)
  и 8 (отказ гейта ёмкости) — проверяемые единицы. Раздел «Покрытие
  требований» исправлен по R1-F1: AC-2/AC-3/AC-6 теперь отнесены к
  `tests/test_artifact_ref_sync.py`, а прежняя ошибочная ссылка на
  `test_artifact_branch_push.py`/`test_merge_gate_ci_wait.py` в PLAN
  признана.
- Шаг 8 (сокращение докстрингов под потолок diff) сверен с диффом:
  `artifact_branch.py`, `snapshot.py`, `doctor/artifact_branches.py` меняют
  только докстринги. Исключение — рефакторинг отбора закрытых задач в
  `_closed_with_closing_sha`, он относится к R1-F2 и заявлен в PLAN. Поведение
  `check_artifact_ref_sync` сохранено: live — не терминальная задача с
  локальной ссылкой, closed — терминальная задача с записью о коммите
  закрытия. Это совпадает с прежним циклом.
- Влияние на систему: новый код ограничен `doctor`, где добавлена досылка под
  `--fix`, и `gitcmd.commit_exists`. Изменений вне зоны SPEC нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1; планка AC-1/AC-9 зелёная |
| 2 | OK | CAS и отправка после коммита с повтором на `set_state` теперь под сторожем `tests/test_artifact_ref_sync.py` (`CompareAndSwapRaceTest`, `SendAfterCommitTest`); мутации ревью итерации 1 краснеют |
| 3 | OK | отказ гейта мержа и `kill` при ссылке ≠ origin держат `MergeGateDocsRefTest`, `KillDocsRefTest`, `OriginSyncRefusalTest`; неотправленный коммит закрытия досылает `doctor --fix` (`_fix_unsent_closed_refs`, `doctor/cli.py:158`) |
| 4 | OK | без изменений |
| 5 | OK | recovery-сверка признаёт прежнее устройство по отсутствию объекта (`doctor/recovery.py:45`, `gitcmd.commit_exists`); ссылку, переписанную мимо пульта, видит (`RecoveryRewrittenRefTest`) |
| 6 | OK | исторические снимки без записи `CLOSING_ACTION` по-прежнему не сверяются и не досылаются (`_closed_with_closing_sha`) |
| 7 | OK | приложение не менялось; планка AC-11 зелёная |
| 8 | OK | поведения AC-2, AC-3, AC-6 и AC-7 (досылка) покрыты в `tests/`, у каждого метода есть заявка «Ловит мутацию» с наблюдаемым расхождением |

Сверка с base по изменённым тестам этой итерации:
- `tests/test_doctor.py::RecoveryCheckTest::test_sha_mismatch_raises_an_incident_alert`:
  подмена `gitcmd.is_ancestor → True` заменена подменой
  `commit_exists → True` вслед за сменой признака в коде. Утверждения не
  тронуты, условие срабатывания осталось тем же: зафиксированный sha
  признан коммитом ссылки, ослабления нет.
- 14 методов из раздела гейта «Изменённые утверждения» не изменились с
  итерации 1. Они сверены там и приняты ANSWER-1 п.2.

Проверка заявок новых тестов. `test_artifact_ref_sync.py` — новый файл, повтора долгоживущего
`tests/test_01m3z2dmqrd0bd7aarfvtcvvg8_*.py` нет, таких файлов у задачи
нет. Заявки называют наблюдаемый эффект: голову без `B.md`, `origin` на
прежней голове, проход гейта к следующему шагу, `status` проверки
recovery. Четыре заявки проверены временной мутацией (раздел «Проверено
исполнением»).

## Замечания

Блокирующих и major-замечаний нет. Новых замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/artifact_branch.py:188, :297, :312, :321; orchestrator/fsm_merge_gate.py:1027; orchestrator/cleanup.py:405 | CAS, автоматическая отправка с повтором и отказ гейта мержа/`kill` при ссылке ≠ origin без сторожа в `tests/` | регресс после мержа пройдёт незамеченным | Ревьювер (итерация 2): `tests/test_artifact_ref_sync.py` закрывает все три мутации итерации 1, каждая теперь даёт красный: `origin_sync_refusal → None` — 5 failed, `update-ref` без прежнего значения — 1 failed (`CompareAndSwapRaceTest`), `send_pending → no-op` — 1 failed. Тесты работают на настоящем git с bare origin. Раздел «Покрытие требований» PLAN исправлен |
| R1-F2 | accepted | orchestrator/snapshot.py:75 | отправку коммита закрытия, если она не прошла, никто не повторяет | RETRO закрытой задачи только локально | Ревьювер (итерация 2): `_fix_unsent_closed_refs` вызывается в `cmd_doctor` под `--fix` до `all_checks`. Он досылает ссылку обычным `push` без force и только когда локальная голова = коммит закрытия. Изменённую после закрытия ссылку не трогает, `origin` без ответа — печатает причину. Оба исхода держит `DoctorFixResendsClosingCommitTest` |
| R1-F3 | accepted | orchestrator/doctor/recovery.py:41 | `recovery-sha` молчал, если зафиксированный sha не предок головы | переписанная мимо пульта ссылка не видна в `doctor` | Ревьювер (итерация 2): признак — `gitcmd.commit_exists` (`cat-file -e <sha>^{commit}`). Мутация `commit_exists → False` (эквивалент прежнего поведения для переписанной ссылки) краснит `test_ref_rewritten_outside_its_history_is_a_mismatch`. Обратную сторону (старая фиксация `.artel/projects/` не сверяется) держит `test_fixation_of_the_old_device_is_not_compared` |

## Вердикт
approved — R1-F1…R1-F3 закрыты: сторожа в `tests/` проверены временными
мутациями, новых blocker/major нет.

## Проверено исполнением
Во всех прогонах `ARTEL_ROLE` снят из окружения процесса pytest.
- `tests/test_artifact_ref_sync.py`, `tests/test_doctor.py`,
  `tests/test_doctor_artifact_branch_sync.py` — 137 passed, 3 subtests
  passed.
- Планка `tasks/01M3Z2DMQRD0BD7AARFVTCVVG8/acceptance_tests/` вместе с
  `tests/test_snapshot_closing_outcome.py`,
  `tests/test_fsm_merge_gate_done_snapshot.py`,
  `tests/test_artifact_branch_push.py` — 64 passed (195 с).
- Временные мутации: monkeypatch в процессе pytest, файлы кода не
  правились. Прогон `tests/test_artifact_ref_sync.py`:
  1. `artifact_branch.origin_sync_refusal → None` — 5 failed;
  2. `update-ref` без третьего аргумента (CAS снят, обёртка `gitcmd.git`)
     — 1 failed;
  3. `artifact_branch.send_pending → no-op` — 1 failed;
  4. `gitcmd.commit_exists → False` — 1 failed.
- `python3 scripts/codebase_map.py` — расхождение
  `docs/codebase-map.md` без строки `built_at_sha`: 0 строк, карта свежая;
  рабочее дерево возвращено (`git checkout -- docs/codebase-map.md`).

## Предложения системе
- Шаблон пакета ревью: инкрементальный diff итерации 2 мал, 9 файлов.
  Ревьюверу пришлось отдельно подтверждать, что шаг 8 («сокращены только
  докстринги») не задел код: правки докстрингов и рефакторинг
  `_closed_with_closing_sha` лежат в одном хунке. Стоит, чтобы PLAN при
  отказе гейта ёмкости прикладывал `git diff -w` без докстрингов, либо
  чтобы гейт пакета размечал хунки «только докстринг».
