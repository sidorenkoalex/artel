---
task: 01M27JPEGCGMDDRX5A98QWJW0Z
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: защищённые пути — единый список, гейт зон отказывает всегда, CI падает

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1. Единый список — `config.PROTECTED_PATHS` + 5 путей | OK | `orchestrator/config.py:513-514` — все 5 добавлены (`docs/invariants.md`, `tests/test_invariants.py`, `docs/adr/`, `CLAUDE.md`, `targets.yaml`) к пяти существующим; формула `==`/`startswith` не тронута (`fsm_merge_gate._touches_protected_path`, `fsm_advance._touches_zone` переиспользован). AC-1 подтверждён и приёмочным тестом. |
| 2. Гейт зон отказывает независимо от заявленности в zones | OK | `fsm_advance.py:754-768` — `_protected_paths_touched(files)` на полном списке файлов диффа, вставлена ДО построения `zones`/проверки `out_of_zone`. AC-2 приёмочным тестом зелёный. |
| 3а. Гейт зон: мандат «Расширение зон» не покрывает защищённый путь | OK | Проверка защищённых путей стоит раньше блока исключения (строки 775-790), физически недостижима после отказа. AC-3 приёмочным тестом зелёный; собственный юнит-тест `ZonesGateProtectedPathPriorityTest` кроет смешанный дифф (защищённый + обычный вне-zone файл). |
| 3б. Гейт мержа отказывает не только при конфликте `git merge --no-ff` | OK | `fsm_merge_gate.py:43-79` — `_protected_path_diff_gate` вызывается ПЕРВЫМ шагом `_cmd_approve_merge_gate` (строка 649), до публикации головы и до самого merge; работает по диффу база...branch, не по факту конфликта. AC-5 приёмочным тестом зелёный. |
| 4. Единый именованный текст на обоих гейтах | OK | Байт-идентичность двух копий текста подтверждена юнит-тестом `test_zones_gate_and_merge_gate_texts_are_byte_identical` и ручной сверкой (`fsm_advance._protected_path_refusal_detail` / `fsm_merge_gate._protected_path_refusal_detail`). AC-4 приёмочным тестом зелёный. |
| 5. CI-задание `protected-paths` — единый источник, падает безусловно | OK (приложение, не код-ветка) | `.github/` — защищённый путь; правка оформлена unified-диффом в приложении к PLAN.md, не в диффе кода (правильно — код-ветка не должна нести правку `.github/`). Дифф читает `config.PROTECTED_PATHS` python-однострочником, `exit 1` вместо `::warning`. Прогнан `git apply --check` на чистом дереве этой сессией — применяется чисто (см. «Проверено исполнением»). |

## Замечания

<Пусто — 0 blocker/major/minor находок. Одно системное наблюдение — в
«Предложения системе» ниже, не как замечание к этой задаче: см.
обоснование там.>

## Реестр замечаний

<Пусто — замечаний нет, регистрировать нечего.>

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_protected_paths_gate -v` — 12/12 зелёных
  (все новые юнит-тесты: `_protected_paths_touched`, оба
  `_protected_path_refusal_detail`, приоритет защищённого пути над
  обычным «вне zones», `_protected_path_diff_gate` на self/внешнем
  target, fail-open при неответившем git).
- `python3 -m pytest tasks/01M27JPEGCGMDDRX5A98QWJW0Z/acceptance_tests/ -v`
  — 6 passed (AC-1..AC-5 исполняемые; AC-6/AC-7 — обоснованные `manual`/
  `skip`-пометки, проверил обоснование каждой — см. текст файлов: AC-6
  правит защищённый путь `.github/`, который код-ветка принципиально не
  несёт; AC-7(а/б/в) дословно дублирует AC-3/AC-5/AC-1, AC-7(г) —
  «ci-covered», уже закрыт штатным полным прогоном `tests/`).
- `python3 -m unittest tests.test_zones_gate tests.test_merge_gate_ci_wait
  tests.test_fsm_merge_gate_done_snapshot tests.test_split_assessment_merge_gate
  tests.test_fsm_merge_gate_scratch_worktree_cleanup tests.test_cmd_approve_dispatch
  tests.test_answer_gate tests.test_zones_approve tests.test_guard_zones
  tests.test_advance_guard tests.test_fsm_advance_gate_framework
  tests.test_fsm_advance_gate_smoke tests.test_invariants
  tests.test_multitarget_invariants` (все модули, перечисленные в PLAN
  «Влияние на систему» как прогнанные разработчиком, плюс оба теста
  инвариантов) — все зелёные, exit code 0 (прогнано двумя параллельными
  фоновыми батчами тем же итогом).
- `git diff --stat <sha вердикта предыдущего REVIEW-предка>...HEAD -- tests/test_zones_gate.py
  tests/test_fsm_merge_gate_done_snapshot.py tests/test_merge_gate_ci_wait.py
  tests/test_split_assessment_merge_gate.py
  tests/test_fsm_merge_gate_scratch_worktree_cleanup.py
  tests/test_cmd_approve_dispatch.py tests/test_answer_gate.py
  tests/test_zones_approve.py tests/test_guard_zones.py
  tests/test_advance_guard.py tests/test_fsm_advance_gate_framework.py
  tests/test_fsm_advance_gate_smoke.py tests/test_invariants.py
  tests/test_multitarget_invariants.py` — пусто: ни один существующий
  тестовый файл не тронут диффом задачи (AC-7г подтверждён и по диффу,
  не только прогоном).
- `git apply --check` на приложенном к PLAN.md unified-диффе
  `.github/workflows/ci.yml` (вставлен во временный файл этой сессии,
  удалён после проверки) — `APPLIES CLEANLY` на текущем чистом дереве;
  разработчик заявлял то же в PLAN, подтверждено независимо.
- `python3 scripts/codebase_map.py` (без аргументов, результат сверен
  `git diff`, затем откачен `git checkout -- docs/codebase-map.md`) —
  содержимое регенерированной карты совпадает с картой из диффа задачи
  байт-в-байт, кроме строки `built_at_sha` (ожидаемо: рабочее дерево
  сейчас на `6efb0c79`, задача коммитила карту с `369e22f2`) — не
  дефект (skills/review-checklist.md, built_at_sha).
- Прочитан код `orchestrator/fsm_advance.py:706-802` (`_zones_gate`
  целиком) и `orchestrator/fsm_merge_gate.py:616-669`
  (`_cmd_approve_merge_gate` целиком) для проверки порядка узлов —
  подтверждает claims PLAN/докстрингов дословно (защищённый путь
  проверяется раньше zones/exception на гейте зон; первым шагом,
  до `_ensure_branch_head_published`, на гейте мержа).
- `orchestrator/gitcmd.py:238-247,278-306` прочитан для проверки риска
  PLAN «диф ветки читается до публикации головы в origin» — `diff_base`/
  `diff_names` используют только локальные refs (`origin/main` или
  локальный `main` как база, `branch` — локальный ref ветки задачи), не
  требуют публикации самой ветки задачи в origin. Риск PLAN подтверждён
  как некритичный.

## Предложения системе

- `orchestrator/fsm_advance.py:726-730` — `_zones_gate` возвращает `None`
  без проверки диффа вовсе, если у задачи нет ни одной заявленной зоны
  (`zones`/`zones_extension` оба пусты) — это пре-существующее поведение
  (не эта задача), но новая проверка защищённых путей (требование 2/3
  этой задачи) унаследовала то же самое короткое замыкание: у задачи со
  старым SPEC (`schema_version < 4`, `guard.requires_zones` для неё не
  действует) гейт зон не звонится вовсе, и правка защищённого пути такой
  задачей НЕ будет остановлена гейтом зон (гейт мержа как второй рубеж
  по-прежнему сработает). На практике не влияет ни на одну новую задачу
  (schema_version 5 обязывает `zones`), это наблюдение о форме защиты
  «гейт зон отказывает всегда», а не дефект диффа этой задачи — не
  блокирует вердикт, фиксирую для Оператора на будущее (например, если
  когда-то понадобится ужесточить сам это короткое замыкание).
