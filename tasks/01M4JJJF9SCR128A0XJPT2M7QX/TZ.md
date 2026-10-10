---
task: 01M4JJJF9SCR128A0XJPT2M7QX
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Подсчёт членов группы процессов: сбой ps не равен пустой группе

# ТЗ: Подсчёт членов группы процессов — сбой `ps` не выдаётся за пустую группу

Источник: строка копилки 10.10 «Тест test_liveness… падает в полном
прогоне на машине пульта 2 из 2»; решение Оператора 10.10.2026 —
заводить.

Случай:
- 10.10 suite-run задачи 01M4JC58GZFHZ4PZHW254P22M2 (ветка задачи и база
  main c6c9245c, `-n auto`, load average 10–14): оба прогона упали на
  `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  — «0 not greater than or equal to 1». Отдельно тот же класс 3 из 3
  зелёный. Полный прогон автогейта 01M4JD3SRN (788 с, та же машина) —
  зелёный: падение неустойчиво.

Факты (main, сверка 10.10):
- `orchestrator/liveness.py::_group_member_count` (~70–83): `ps -o pid= -g
  <pgid>`, `timeout=5`; `OSError`, `TimeoutExpired` и ненулевой код
  возврата — все дают 0, как пустая группа.
- `terminate_process_group` (~86–120): число до сигнала — из
  `_group_member_count`; после `SIGTERM` цикл ожидания и решение о
  `SIGKILL` (~112–116) тоже по `_group_member_count(pgid) > 0`: сбой `ps`
  читается как «группа пуста» — `SIGKILL` выжившим не посылается, а
  вызывающий получает 0 «снятых».
- Вызывающие (только чтение): `orchestrator/runner.py` ~1604,
  `orchestrator/pause.py` ~244, `orchestrator/release.py` ~62,
  `orchestrator/cleanup.py` ~367, `orchestrator/canary.py` ~1243, ~2284,
  ~2291, `orchestrator/doctor/hung_test_watchdog.py` ~204, ~226,
  `orchestrator/catalog.py` ~732 (показ числа членов группы).
- Тест: `tests/test_liveness.py` (`_spawn_group` ~31, тест ~90–110).

Требуется:
1. Установить причину нуля в полном прогоне (сбой/таймаут `ps` под
   нагрузкой, гонка с `setsid`, влияние соседних тестов того же
   процесса xdist или иное) и записать её в PLAN; исправление — по
   причине, а не подгонкой теста.
2. Подсчёт членов группы различает «группа пуста» и «подсчёт не удался»;
   сбой подсчёта не выдаётся за пустую группу.
3. `terminate_process_group` при сбое подсчёта не отказывается от
   `SIGKILL`: после срока ожидания выжившие члены группы добиваются, как
   при успешном подсчёте; возвращаемое число не занижается до 0 из-за
   сбоя подсчёта (либо сбой назван вызывающему явно — выбор за
   аналитиком, без смены сигнатуры для вызывающих из «Только чтение»).
4. Тест `test_kills_the_leader_and_returns_a_positive_count` устойчив в
   полном прогоне `-n auto` под нагрузкой без ослабления утверждений.
5. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- Подменённый `ps`, падающий по таймауту или с ненулевым кодом: подсчёт
  сообщает сбой, а не 0; `terminate_process_group` всё равно добивает
  живого лидера группы `SIGKILL` после срока ожидания.
- Живая группа при исправном `ps` — число членов ≥ 1, как сегодня.
- Пустая группа — 0, как сегодня.
- Мутация «сбой подсчёта = пустая группа» ловится тестом.

Зоны: orchestrator/liveness.py, docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/runner.py, orchestrator/pause.py,
orchestrator/release.py, orchestrator/cleanup.py, orchestrator/canary.py,
orchestrator/doctor/, orchestrator/catalog.py, orchestrator/config.py,
orchestrator/amend.py, orchestrator/acceptance.py,
orchestrator/plank_run.py, scripts/, .github/workflows/ci.yml,
tests/test_invariants.py, docs/invariants.md, docs/adr/, docs/roadmap.md,
docs/backlog.md, docs/operator-session.md, templates/, skills/,
CLAUDE.md, models.yaml, roles.yaml, targets.yaml, .artel/.

Не входит: время полного прогона и замок одновременных прогонов
(отдельная строка, пункт 3 очереди критичных); amend-tests и помощник
`_pult.py` (задача 01M4JD36367E5CG3GXDV429XTE).

Рамка: $25.

Набор моделей: по умолчанию.
