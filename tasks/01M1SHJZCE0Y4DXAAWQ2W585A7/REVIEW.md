---
task: 01M1SHJZCE0Y4DXAAWQ2W585A7
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: подзадачи деления заводит пульт из раздела «Деление» SPEC при approve

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (формат секции «Деление», guard) | OK | R1-F1 исправлен: `division_section_errors` (scripts/guard.py:1329-1337, коммит 6b2695e2) сверяет зону подраздела через `zone_lock._is_common_zone`/`zone_lock._covered_by` — покрытие с учётом вложенности каталог/файл, та же семантика, что у остального guard'а. R1-F3 исправлен: заголовок «## Деление» с непустым телом без единого `###`-подраздела теперь даёт явную ошибку (guard.py:1284-1297), а не тихий проход. |
| 2 (approve заводит подзадачи, TZ.md со ссылкой) | OK | Без изменений с итерации 1 — подтверждено AC-5/AC-11, `spawn_subtask` переиспользует общий скелет. |
| 3 (killed + журнал, идемпотентность) | OK | Без изменений с итерации 1 — подтверждено AC-6/AC-8/AC-12. |
| 4 (три unified-диффа приложением) | OK | Без изменений с итерации 1 — три диффа в PLAN.md, `git apply --check` пройден на текущем дереве, защищённые пути (`templates/`, `skills/`, `docs/operator-gates.md`) кодом MR не тронуты (`git diff main...HEAD --stat -- templates/ skills/ docs/operator-gates.md` — пусто). |
| 5 (тесты) | OK | R1-F2 исправлен: все 7 ранее голых тестовых методов несут докстринг «Ловит мутацию: …» с конкретным сценарием и наблюдаемым свойством (tests/test_catalog_spawn_subtask.py, tests/test_guard_division_section.py). Регрессия R1-F1 закрыта тремя новыми тестами с явной привязкой к каталожной вложенности; мутационно перепроверил сам (см. «Проверено исполнением») — ловят. |

## Замечания

(пусто — все замечания итерации 1 закрыты, новых не найдено)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | scripts/guard.py:1329-1337 | сверка зон подраздела с зонами родителя/COMMON_ZONES — плоское членство в множестве, без вложенности каталог/файл | guard ложно отказывал валидным заявкам на деление (файл внутри общей/родительской директории-зоны) | исправлено коммитом 6b2695e2: `zone_lock._is_common_zone(zone) or any(zone_lock._covered_by(zone, pz) for pz in parent_zones)`, три новых теста (в т.ч. обратная лазейка «зона шире зоны родителя»), мутационно перепроверено ревьювером — ловят |
| R1-F2 | accepted | tests/test_catalog_spawn_subtask.py; tests/test_guard_division_section.py | 7 из 11 новых тестовых методов без докстрин-заявки «Ловит мутацию: …» | ревьюверу и будущим читателям неизвестно, какую мутацию каждый тест ловит | всем семи методам добавлен докстринг с конкретным сценарием и наблюдаемым свойством (коммит 6b2695e2) — проверено построчно, заявки не пересказывают имя метода |
| R1-F3 | accepted | scripts/guard.py:1284-1297 | заголовок «## Деление» присутствует, но подразделов `###` нет — `division_section_errors` молча возвращала `[]` | намерение аналитика на деление тихо игнорировалось без диагностики | явная ошибка «секция не несёт ни одного подраздела '### <название>'» при непустом теле без `###`, тест `test_header_present_with_prose_but_no_subsections_errors` зелёный |
| R1-F4 | accepted | orchestrator/catalog.py:235-272 | `spawn_subtask` дублировала ~12 строк скелета `cmd_new` почти дословно | два места пришлось бы поддерживать синхронно при будущей правке общего скелета | вынесен приватный хелпер `_new_task_row(conn, task_id, title, target, tz_doc, *, is_canary, journal_detail)`, `cmd_new`/`spawn_subtask` — тонкие обёртки; `tests.test_catalog_new_race` и весь `test_catalog_spawn_subtask` зелёные без изменения тестового кода под рефакторинг |

## Вердикт

approved — реестр закрыт целиком (все четыре записи `accepted`), новых blocker/major/minor не найдено. Инкрементальный diff пакета оказался пуст, потому что sha предыдущего вердикта (6b2695e2) совпал с текущим HEAD (см. заметку в skills/review-checklist.md про этот класс ложного сигнала) — фактическую правку итерации нашёл через `git show --stat 6b2695e2` (единственный код-коммит после iteration-1-вердикта) и прочитал построчно; SPEC.md/PLAN.md пакет тоже не показал (untracked в коде, материализованы на диске рабочего каталога) — прочитал их инструментом чтения напрямую.

## Проверено исполнением

- `git show --stat 6b2695e2` + `git show 6b2695e2 -- scripts/guard.py orchestrator/catalog.py tests/test_catalog_spawn_subtask.py tests/test_guard_division_section.py` — построчное чтение фактической правки итерации (пакетный diff был пуст из-за совпадения sha с HEAD).
- `python3 -m unittest tests.test_guard_division_section tests.test_catalog_spawn_subtask -v` — 15/15 OK (11 прежних + 4 новых, все с докстрингами).
- Мутационная проверка R1-F1: временно вернул плоскую проверку членства (`zone not in parent_zones and zone not in common_zones` вместо `zone_lock._is_common_zone`/`_covered_by`) — `test_zone_nested_under_a_parent_directory_zone_does_not_error` покраснел (`AssertionError`, 2 ложных отказа), откатил правку `git checkout -- scripts/guard.py` — снова зелёный. Фикс действительно ловится тестом.
- `python3 -m unittest tests.test_advance_guard tests.test_zones_approve tests.test_guard_split_signals tests.test_catalog_new_race tests.test_cmd_approve_dispatch` — 40/40 OK (SPEC требование 5, регрессия по существующим тестам не нашлась).
- `python3 -m unittest` по всем 10 исполняемым файлам `tasks/01M1SHJZCE0Y4DXAAWQ2W585A7/acceptance_tests/` (AC-2..AC-9, AC-11, AC-12) — 13/13 OK.
- `python3 -m unittest tests.test_fsm_advance_gate_framework tests.test_fsm_advance_gate_smoke tests.test_fsm_autogate tests.test_fsm_branch_correct_status_reads tests.test_fsm_draft_mr_reentry tests.test_fsm_map_conflict_autoresolve tests.test_fsm_map_regen tests.test_fsm_merge_conflict_note tests.test_fsm_merge_gate_done_snapshot tests.test_fsm_merge_gate_scratch_worktree_cleanup tests.test_fsm_retro tests.test_catalog_status_log tests.test_catalog_tz_zones_parsing tests.test_catalog_wave_breaker_status tests.test_guard_artifact_branch_mode tests.test_guard_extraneous_acceptance_files tests.test_guard_schema tests.test_guard_task_root_subdirectory tests.test_fsm_review_rework_gate tests.test_fsm_review_rework_sha_gate tests.test_multitarget tests.test_multitarget_invariants tests.test_invariants` (фоном, таймаут превышен на переднем плане) — exit code 0, без сбоев.
- `python3 scripts/guard.py --all` — 724 файла, ок; два предсуществующих предупреждения `_sandbox.py` (T067, 01M1RA0R9AH9RBAHD4A2Z5SEWQ), не по зоне этой задачи.
- `python3 scripts/codebase_map.py` (регенерация) — diff с версией в ветке только по строке `built_at_sha` (легитимное расхождение); содержимое (`grep -v '^built_at_sha:'`) идентично; откатил регенерацию рабочего дерева (`git checkout -- docs/codebase-map.md`), т.к. коммит 6b2695e2 уже несёт актуальную карту.
- `git diff main...HEAD --stat -- templates/ skills/ docs/operator-gates.md` — пусто, защищённые пути кодом MR не тронуты (требование 4/AC-10 закрывается приложением диффов в PLAN.md, применяет Оператор).
- CI коммита 6b2695e2 (verifying) — зелёный, 14 проверок (см. статус пакета).

## Предложения системе

- Инкрементальный diff пакета ревью снова совпал с HEAD вместо диапазона «код итерации» (тот же класс, что T082/T087, уже описанный в skills/review-checklist.md) — источник в этой задаче другой: previous-verdict sha, судя по всему, взят от коммита-ФИКСА (который сам стал и HEAD, и точкой сравнения), а не от коммита, на котором ревью вынесло changes_requested. Стоит проверить логику вычисления base sha в оркестраторе на предмет этого конкретного случая (fix-коммит совпадает с HEAD на момент следующего ревью).
