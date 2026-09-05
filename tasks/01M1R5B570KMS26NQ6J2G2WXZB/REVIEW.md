---
task: 01M1R5B570KMS26NQ6J2G2WXZB
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: Плавающий тест лимитера параллельных задач: граница свежести heartbeat

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) — запас у границы увеличен до половины `LEASE_STALE_AFTER_SEC`, выбор задокументирован в PLAN.md | OK | `tests/test_parallel_limit.py:26` `_MARGIN_SEC = config.LEASE_STALE_AFTER_SEC // 2`; PLAN.md обосновывает выбор (меньший дифф, не трогает `liveness.py`). AC-1 acceptance-тест (симулированный сдвиг «сейчас» патчем `liveness.datetime` почти на половину порога) зелёный. |
| 2 (AC-2) — тот же приём применён ко всем родственным местам `_ts_ago`+`LEASE_STALE_AFTER_SEC` в файле | OK | Все 4 места (:81, :88, :111, :149 в новой версии файла) заменены на `_fresh_edge_ts()`/`_stale_edge_ts()`. AC-2 acceptance-тест (три «протухшие»-стороны теста под тем же симулированным сдвигом) зелёный. |
| 3 (AC-3) — grep по `tests/` на риск. запас ≤5 сек со стороны «ещё не протух», приведение найденного | OK | Независимый grep (`grep -rn "LEASE_STALE_AFTER_SEC" tests/ | grep -v test_parallel_limit.py`) подтверждает: все прочие вхождения в `test_lease.py`/`test_merge_lock.py`/`test_release.py` — со стороны «точно протух» (`+1`/`+100`), безопасны по построению; вне `test_parallel_limit.py` рискованных мест нет. Совпадает с выводом AC-3 acceptance-теста (программный grep, зелёный) и с «Влияние на систему» PLAN.md. |
| 3 (AC-4) — обе стороны границы по-прежнему проверяются | OK | `test_stale_heartbeat_is_excluded`/`test_heartbeat_just_under_the_threshold_still_counts` и парные сохранены, только источник метки заменён на хелперы; семантика (занят/протух) не изменилась. AC-4 acceptance-тест зелёный. |
| 3 (AC-5) — независимость от реальной задержки между посевом и проверкой | OK | AC-5 acceptance-тест инъецирует реальный `time.sleep(1.2)` перед `busy_other_tasks`/`refusal` для всех 4 целевых тестов — зелёный (6.1 сек прогона). |
| 3 (AC-6) — существующие тесты `tests/` зелёные, порог и механика lease не изменены по логике | OK | Diff ограничен `tests/test_parallel_limit.py`, ни один файл `orchestrator/liveness.py`/`lease.py`/`merge_lock.py`/`parallel_limit.py` не тронут — производственная логика и `LEASE_STALE_AFTER_SEC` нетронуты. `tests.test_parallel_limit` — 12/12 зелёных локально. AC-6 помечен `skip` с обоснованием класса «ci-covered» (полный набор гоняет CI-джоб на каждый пуш) — легитимная частая пометка, не понижает автогейт. |

## Замечания

Пусто.

## Реестр замечаний

Пусто — замечаний в этой итерации не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_parallel_limit -v` — 12/12 тестов зелёные.
- `python3 tasks/01M1R5B570KMS26NQ6J2G2WXZB/acceptance_tests/test_ac1_heartbeat_edge_case_time_independence.py` — 1/1 OK (симулированный сдвиг «сейчас» почти на половину порога, тест границы «свеж» переживает).
- `python3 tasks/01M1R5B570KMS26NQ6J2G2WXZB/acceptance_tests/test_ac2_stale_side_siblings_consistent_technique.py` — 1/1 OK (три родственных теста стороны «протух» переживают тот же сдвиг).
- `python3 tasks/01M1R5B570KMS26NQ6J2G2WXZB/acceptance_tests/test_ac3_no_new_risky_margin_elsewhere.py` — 1/1 OK (программный grep по `tests/*.py` кроме `test_parallel_limit.py` не находит запаса ≤5 сек со стороны «ещё не протух»).
- `python3 tasks/01M1R5B570KMS26NQ6J2G2WXZB/acceptance_tests/test_ac4_boundary_both_directions_preserved.py` — 1/1 OK.
- `python3 tasks/01M1R5B570KMS26NQ6J2G2WXZB/acceptance_tests/test_ac5_real_delay_between_seed_and_check.py` — 1/1 OK, 6.13 сек (реальный `time.sleep(1.2)` перед каждым из 4 целевых вызовов).
- AC-6: пометка `# AC-6: skip — ...` в файле, исполняемого теста нет по замыслу (обоснование — класс «ci-covered», см. SPEC/PLAN); отдельно проверено вручную `tests.test_parallel_limit` (12/12) — production-код зоны не тронут.
- `grep -rn "LEASE_STALE_AFTER_SEC" tests/ | grep -v test_parallel_limit.py` — независимая проверка AC-3: все найденные места (`test_release.py:93`, `test_merge_lock.py:77`, `test_lease.py:102,159,178,392,555`) со стороны `+N` (безопасно).
- `python3 scripts/codebase_map.py --check` — карта не устарела, регенерация не требуется (изменение не затронуло сигнатуры/докстринги, учитываемые картой).
- `git diff --stat main...HEAD` / `git log main..HEAD --oneline` — диф ограничен `tests/test_parallel_limit.py` (24+/4-), подтяжка main без побочных файлов; защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не тронуты.

## Предложения системе

- Все 4 изменённых тестовых метода в `tests/test_parallel_limit.py` (как и остальные 8 в этом файле) не несут докстрингов с заявкой «Ловит мутацию» (skills/test-authoring.md, skills/review-checklist.md Фаза B.3) — но это предсуществующий пробел файла T060, а не новый тест, и сама мутационная чувствительность этих тестов не пострадала (assерты не менялись, только источник метки времени). Не завожу как замечание этой задачи: SPEC/PLAN узко и намеренно ограничены правкой запаса, задним числом требовать докстринги на 8 непричастных тестов было бы расширением объёма. Фиксирую как повтор наблюдения из памяти (`feedback_test_authoring_mutation_claim_gap`) — гэп в `tests/*.py` систематический, стоит решить отдельной задачей на уровне файла/конвенции, а не точечно на каждом ревью, который его касается по касательной.
