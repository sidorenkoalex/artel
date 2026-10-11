---
task: T076
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Ложный инцидент целостности при отклонённом advance

## Фаза A — гейт плана

Покрытие: каждое требование SPEC (1–5) закрыто хотя бы одним шагом
PLAN, таблица покрытия полна и соответствует фактическому diff. Шаги
1–3 — три проверяемых по отдельности единицы (примитив gitcmd, функция
fixation, точка вызова fsm); шаг 4 (тесты) и шаг 5 (карта) — обычные
сопутствующие. Подход (единая точка вызова `_advance_with_refixation`
в `fsm.cmd_advance`, чтение через `fixation.read()`, отдельное имя
журнальной записи, чтобы не путать с `record_fixation`) не конфликтует
с существующей архитектурой фиксаций (T021/T031/T041/T045/T048/T059) —
использует те же примитивы (`fixation.read`, `store.update_task`,
`store.journal`) тем же стилем деградации (fail-closed при
неотвеченном git), что и остальной модуль. Гейт плана пройден.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Единая точка `fsm._advance_with_refixation` оборачивает `_cmd_advance` для ЛЮБОГО отклонённого перехода (state не изменилось); определение «свой/чужой» коммит — по замкнутым окнам `agent run started/finished` журнала задачи, `fixation.py:195-234`. |
| 2 | OK | Все коммиты диапазона внутри окон → `fixed_sha` перефиксирован (`store.update_task`), журнальная запись `«sha перефиксирован после отклонённого перехода»` с деталью `«коммиты шага: было …, сейчас …»`, `fixation.py:271-275`; причина отказа гейта остаётся в журнале как обычно (проверено `test_ordinary_refusal_reason_is_kept`, AC-1). |
| 3 | OK | Хотя бы один коммит вне окон / окон нет / git не ответил / нераспарсенная дата → `False`, фиксация не трогается, `check_integrity` эскалирует как раньше (`fixation.py:258-270`; `ForeignCommitKeepsIncidentTest`, AC-2, `UnclosedRunWindowNotCountedTest`). |
| 4 | OK | `_dirty_refuses` не тронут ни строкой; `check_integrity`'s dirty-ветка не завязана на `fixed_sha`, только на живой `read()` в момент проверки — перефиксация sha не может скрыть грязную копию (см. «Проверено исполнением» — прогон `IntegrityIncidentBlocksRunTest`/`ApproveByShaTest` и код-ревью `fixation.py:180-184`). |
| 5 | OK | `confirm_fixation`/`_cmd_approve*` не изменены ни строкой (diff это подтверждает); обёртка выходит раньше сравнения sha, если состояние изменилось — успешный переход не проходит через `refixate_after_rejected_transition` (`SuccessfulTransitionUnaffectedTest`). |

## Замечания

- minor — `tasks/T076/PLAN.md` («Риски») — риск обсуждает только рассинхронизацию часов и недостижимый диапазон `since..until`, но не упоминает, что критерий «свой коммит» — чисто временное окно без проверки авторства коммита (SPEC требование 3 в скобках допускает и «чужое авторство» как отдельный сигнал, PLAN выбрал только окно). В текущей однопользовательской архитектуре пульта (лок задачи через `lease`, один writer в worktree на шаг) риск теоретический и fail-closed на любой неоднозначности, поэтому не blocker — но лучше явно проговорить в PLAN, почему авторство не проверяется, чтобы следующий ревьювер этого класса задач не заново реконструировал довод.
- minor — `tests/test_step_refixation.py` / `tasks/T076/acceptance_tests/` — нет теста на комбинацию «коммит роли внутри окна шага + после него независимо разрозненная незакоммиченная правка» при отклонённом переходе (пересечение требований 2 и 4: перефиксация должна произойти, но `check_integrity` следующего запуска обязан всё равно поймать «грязная копия», а не пройти чисто). По коду (`fixation.py:180-184`, `check_integrity` читает `clean` заново, не из сохранённого значения) поведение корректно, подтверждено вручную запуском существующих грязно-копийных тестов из `test_git_fixation.py`, но отдельного целевого теста именно на эту комбинацию для НОВОГО пути (`_advance_with_refixation`) нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_step_refixation -v` — 12 тестов, все зелёные (в т.ч. `CommitCommitterDatesTest`, `OwnStepCommitRefixesWithoutIncidentTest`, `ForeignCommitKeepsIncidentTest`, `UnclosedRunWindowNotCountedTest`, `MultipleOwnStepWindowsAccumulateTest`, `SuccessfulTransitionUnaffectedTest`).
- `python3 -m unittest tests.test_git_fixation -v` — 27 тестов, все зелёные (включая неослабляемые классы AC-3: `FsmDecidesOnlyOnFixedHashesTest`, `IntegrityIncidentBlocksRunTest`, `ApproveByShaTest`, `ExternalApproveDoesNotCommitOthersWorkInProgressTest`).
- `python3 tasks/T076/acceptance_tests/test_ac1_own_step_commits_refix_no_incident.py` — 1 тест, зелёный (AC-1, сценарий T069/T073).
- `python3 tasks/T076/acceptance_tests/test_ac2_foreign_commit_still_raises_incident.py` — 1 тест, зелёный (AC-2, посторонний коммит).
- `python3 tasks/T076/acceptance_tests/test_ac3_fixation_tests_stay_green.py` — 1 тест (subTest x4), зелёный (AC-3).
- `python3 -m unittest discover -s tests -q` — 982 теста, все зелёные (AC-4, полный набор проекта).
- `git diff main...task/t076-lozhnyy-intsident-tselostnosti --stat` — вне `tasks/T076/*` изменены только `orchestrator/fixation.py`, `orchestrator/fsm.py`, `orchestrator/gitcmd.py`, `tests/test_step_refixation.py`, `docs/codebase-map.md`; ни `gates.yaml`, `roles.yaml`, `.github/`, `templates/`, `skills/` не задеты.
- `python3 scripts/codebase_map.py` (регенерация) — диф свёлся только к `built_at_sha` (из-за более позднего мерж-коммита `T076: подтяжка main` на момент прогона, не из-за рассинхронизации содержимого); изменение отменено (`git checkout -- docs/codebase-map.md`), рабочее дерево оставлено чистым.
- Ручное прочтение `orchestrator/runner.py:430-621` — прослежены все 4 непереходных вызывателя `store.record_fixation` (`commit_timeout_checkpoint`, `commit_abnormal_checkpoint`, `commit_pause_now_checkpoint`, `commit_step_artifacts`); подтверждено, что `commit_step_artifacts` НЕ перефиксирует, когда роль уже закоммитила артефакт сама и дерево чисто (ветка "нечего коммитить") — именно это и создаёт разрыв, который закрывает T076.

## Предложения системе

- В PLAN.md полезно явно проговаривать выбор между «окно по журналу» и «авторство коммита» как альтернативными критериями из SPEC, даже когда выбран один — иначе следующий ревьювер тратит время на реконструкцию того же довода (см. замечание выше).
