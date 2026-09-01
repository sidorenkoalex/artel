---
task: T087
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 2
---

# REVIEW: merge_gate — approve сам ожидает CI после подтяжки

## Соответствие SPEC

Диапазон `git diff` в пакете (sha предыдущего вердикта → HEAD) пуст,
но это НЕ означает, что после итерации 1 ничего не менялось — см.
разбор в «Замечания». Требования 1-12 перепроверены заново по
фактическому HEAD (`4085cf6`), не переписаны механически из итерации 1.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/fsm.py:1287-1300` (сдвиг строк из-за смёрженных изменений T086 выше по файлу, см. «Замечания») — после `pull_outcome == "pulled"` пуш `git push -u origin branch` выполняется до возврата `("wait", branch)`, внутри мьютекса (см. требование 2). Приёмочный `test_ac1_push_before_wait_loop.py` наблюдает push непосредственно перед первым чтением статуса CI. |
| 2 | OK | `_cmd_approve_merge_gate_cycle` (`fsm.py:1382-1423` и далее) берёт `merge_lock.acquire`/`release` напрямую вокруг каждого захода в `_cmd_approve_merge_gate`, `release` — в `finally`; `_wait_for_branch_ci_green` зовётся ПОСЛЕ `release`. Приёмочный `test_ac2_mutex_free_during_wait.py` проверяет свободу мьютекса непосредственно из моков `ci.branch_status`/`ci.trigger_rerun`/`time.sleep`. |
| 3 | OK | `_wait_for_branch_ci_green` (`fsm.py:1190-1229`) переиспользует `ci.branch_status`/`ci.status_kind`/`_ci_confirm_red_or_flake` (общий узел с однократной проверкой на пути `"fresh"`); running/unknown паузят `time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)` и продолжают цикл. |
| 4 | OK | Потолок вычисляется РОВНО один раз в `_cmd_approve_merge_gate_cycle` (`if deadline is None: start = time.monotonic(); deadline = start + config.MERGE_GATE_CI_WAIT_CEILING_SEC`, `fsm.py:1419-1421`), не пересчитывается на повторном исходе `("wait", ...)`. Подтверждено `test_ac4_ceiling_not_reset_by_repull.py` (приёмочный, честный контроль через скачок часов) и `test_ceiling_not_reset_by_a_second_wait_outcome` (юнит). |
| 5 | OK | Зелёный статус (включая флейк-ре-ран) — возврат из `_wait_for_branch_ci_green` в `confirmed_ci_note`, цикл перезаходит с тем же `sid`, тем же вызовом `approve`. `test_ac5_green_completes_same_call.py` проверяет `done` после одного `self.approve()`. |
| 6 | OK | Повторный `pull_outcome == "pulled"` на заходе после ожидания просто возвращает новый `("wait", branch)`, не читая `confirmed_ci_note` (ветка `"pulled"` в `_cmd_approve_merge_gate` этот параметр не трогает) — кэш корректно отбрасывается для нового head. `_pull_main_or_escalate` прогоняет `acceptance.run` при подтяжке (`fsm.py:321`), т.е. приёмочные тесты гоняются и на повторной подтяжке. `test_ac6_repull_on_second_main_advance.py` зелёный. |
| 7 | OK | `_ci_confirm_red_or_flake` (переиспользуется из фикс. пути T082) — подтверждённый красный `sys.exit` тем же текстом, что и раньше; тест `test_ac7_confirmed_red_stops_wait.py` (в т.ч. после нескольких "идёт"-итераций). |
| 8 | OK | Истечение `deadline` проверяется ДО `time.sleep` каждой непоследней итерации, `sys.exit` с "статус CI неизвестен". `test_ac8_ceiling_expiry_refuses.py`, `WaitLoopCeilingTest` (юнит). |
| 9 | OK | Каждая итерация: `store.journal(..., "ожидание CI (цикл merge_gate)", detail)` + `print(...)`, `detail` несёт note и `"(ожидание N сек)"`. `test_ac9_progress_logged_each_iteration.py`. |
| 10 | OK | Мьютекс не удерживается во время `_wait_for_branch_ci_green` (см. требование 2) — `KeyboardInterrupt` из `time.sleep`/чтения статуса ничего не оставляет захваченным; lease снимается в `finally` `lease.run_locked` выше по стеку. `test_ac10_ctrl_c_leaves_state_and_frees_mutex.py`. |
| 11 | OK | Путь `"fresh"` не заходит в ветку `pull_outcome == "pulled"` — ни push, ни цикл ожидания не исполняются, `ci.branch_status` читается ровно один раз. `test_ac11_fresh_branch_unchanged.py` (регресс, «зелёный с рождения» по докстрингу файла). |
| 12 | OK | Diff ветки (`main...HEAD`) по-прежнему ограничен `orchestrator/config.py`, `orchestrator/fsm.py`, тестами, `tasks/T087/*` и `docs/codebase-map.md`; `orchestrator/ci.py`/`orchestrator/merge_lock.py` не изменены. Merge-коммит HEAD (см. «Замечания») довносит T086/T088/T090 (уже approved отдельными REVIEW.md), но НЕ трогает merge_gate-код этой задачи — область T087 внутри `orchestrator/` не расширилась. |

## Замечания

Блокеров и major нет. Два наблюдения, оба не меняют вердикт:

- minor — `tasks/T087/REVIEW.md` (пакет ревью, не diff кода) — sha
  «предыдущего вердикта», переданный в пакете (`4085cf6...`), совпадает
  с текущим HEAD, из-за чего диапазон `git diff` пуст и наводит на
  мысль, что после итерации 1 ветка не менялась. На деле итерация 1
  (`status: approved`) была зафиксирована коммитом `e66787d`
  («T087: артефакты шага reviewer»), а ЗАТЕМ поверх него лёг мёрдж-коммит
  `4085cf6` («T087: подтяжка main — разрешение конфликта импортов
  fsm.py (time + datetime, T086×T087)»), затянувший main (T086/T088/T090)
  и вручную разрешивший конфликт импортов в `orchestrator/fsm.py` —
  ровно та подтяжка, которую сама T087 должна была бы делать
  автоматически, но делает пока руками, т.к. фича не в main. Это
  реальное изменение состояния ветки ПОСЛЕ вынесения вердикта итерации
  1, которое инкрементальный diff пакета скрыл. Перепроверено вручную:
  `git diff e66787d..HEAD -- orchestrator/fsm.py orchestrator/config.py`
  показывает изменения только в области T086 (блок `verifying` в
  `_cmd_advance`, константы `VERIFYING_POLL_INTERVAL_SEC`/
  `VERIFYING_CEILING_SEC`, импорт `datetime`) — код `_cmd_approve_
  merge_gate`/`_cmd_approve_merge_gate_cycle`/`_wait_for_branch_ci_green`
  и константы `MERGE_GATE_CI_WAIT_*` из этой мёрдж-подтяжки не задеты
  (см. также требование 12). Предложение системе ниже.
- minor — `docs/codebase-map.md` (committed на HEAD, `built_at_sha:
  499969c9...`) — мёрдж-коммит `4085cf6` привнёс правки в
  `orchestrator/*.py`/`tests/*.py` (T086/T088/T090), но не
  регенерировал карту тем же коммитом (conventions-core), из-за чего
  закоммиченная карта не перечисляет даже собственный новый тест этой
  задачи, `tests/test_merge_gate_ci_wait.py`, среди импортёров
  `orchestrator/{fsm,ci,gates,merge_lock,store}.py`. Не блокер: карта не
  проверяется на task-ветках (job `codebase-map` в `.github/workflows/
  ci.yml:54` — `if: github.ref == 'refs/heads/main'`, `scripts/
  guard.py --all` карту не проверяет — воспроизведено, «GUARD: ок»
  despite staleness), и `_regenerate_and_commit_map` (`fsm.py:72-128`,
  SPEC T042) сама перегенерирует и закоммитит карту на фактическом
  merge в main, независимо от состояния карты на ветке до этого. То есть
  дефект самокорректируется при реальном мерже и не требует правки для
  аппрува, но стоило регенерировать карту тем же коммитом при разрешении
  конфликта — по духу conventions-core.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tests -p "test_*.py"` — 1125 тестов, все зелёные на текущем HEAD (`4085cf6`, после мёрдж-подтяжки main) — на 19 тестов больше итерации 1 (1106) за счёт довнесённых T086/T088/T090 тестов, не T087.
- Целевой перезапуск наиболее чувствительных к мёрджу наборов —
  `python3 -m unittest tests.test_ci_status_kind_gate tests.test_merge_lock tests.test_invariants tests.test_merge_gate_ci_wait tests.test_verifying_ceiling tests.test_auto_cycle` — 104 теста, все зелёные (T082-гейт, мьютекс T053, инварианты, цикл ожидания T087, потолок verifying T086, полный auto-цикл — ни один регресс не пойман после конфликтного мёрджа).
- `cd tasks/T087/acceptance_tests && python3 -m unittest test_ac1_push_before_wait_loop test_ac2_mutex_free_during_wait test_ac3_pause_continues_on_non_final_status test_ac4_ceiling_not_reset_by_repull test_ac5_green_completes_same_call test_ac6_repull_on_second_main_advance test_ac7_confirmed_red_stops_wait test_ac8_ceiling_expiry_refuses test_ac9_progress_logged_each_iteration test_ac10_ctrl_c_leaves_state_and_frees_mutex test_ac11_fresh_branch_unchanged` — 13 тестов (AC-1..AC-11), все зелёные на текущем HEAD.
- `cd tasks/T086/acceptance_tests && python3 -m unittest discover -p "test_ac*.py"` — 12 тестов, все зелёные — приёмка T086 (соседняя область, довнесённая тем же мёрджем в `_cmd_advance`/`config.py`) не пострадала от разрешения конфликта импортов.
- `python3 scripts/guard.py --all` — «GUARD: ок (308 файлов)».
- `python3 scripts/codebase_map.py` (регенерация) — содержательный diff (см. «Замечания»: недостающий `tests/test_merge_gate_ci_wait.py` среди импортёров и устаревший `built_at_sha`); после проверки откатан `git checkout -- docs/codebase-map.md`, чтобы не оставить след в рабочем дереве ревью. Не блокер по причине, разобранной в «Замечания» (self-heal в T042 на реальном merge в main).
- `git diff e66787d..HEAD -- orchestrator/fsm.py orchestrator/config.py` — сверка «что реально изменилось между вердиктом итерации 1 и текущим HEAD» (т.к. sha в пакете дал пустой diff, см. «Замечания»): изменения строго в области T086 (`verifying`), merge_gate-код T087 не тронут.
- `grep -n "def _wait_for_branch_ci_green\|def _cmd_approve_merge_gate_cycle\|def _cmd_approve_merge_gate\b\|MERGE_GATE_CI_WAIT_POLL_SEC\|MERGE_GATE_CI_WAIT_CEILING_SEC\|deadline is None" orchestrator/fsm.py` — подтверждены актуальные номера строк для таблицы «Соответствие SPEC» после сдвига от смёрженного кода T086 выше по файлу.
- `git status --short` до и после регенерации карты — подтверждено, что рабочее дерево ветки чистое (нет незакоммиченных следов ревью).

## Предложения системе

- Инкрементальный diff в ревью-пакете («от sha предыдущего вердикта до
  HEAD») может оказаться пустым не потому, что ветка не менялась, а
  потому, что переданный sha сам является HEAD, хотя фактический
  коммит вердикта (артефакт `REVIEW.md` со `status: approved`) лежит
  РАНЬШЕ в истории, а между ними — мёрдж-коммит извне (freshness-
  подтяжка main). Разбор в этой задаче делался вручную (`git log -- tasks/<id>/REVIEW.md`
  + сравнение с HEAD); стоит явно определить в схеме пакета, что «sha
  предыдущего вердикта» — это коммит, где `REVIEW.md` получил свой
  предыдущий `status`, а не текущий HEAD ветки на момент сборки пакета,
  иначе ревьювер молча теряет право видеть промежуточные подтяжки.
- Класс «мёрдж/подтяжка main в задачную ветку не регенерирует
  `docs/codebase-map.md` тем же коммитом» — самокорректируется T042 на
  реальном merge в main, поэтому терпимо, но стоит добавить это явным
  пунктом в скил conventions-core рядом с существующим правилом про
  правку `*.py` — сейчас правило по факту не покрывает случай мёрджа
  main внутрь ветки (git merge тоже меняет `*.py`, просто не через
  Edit-инструмент разработчика).
