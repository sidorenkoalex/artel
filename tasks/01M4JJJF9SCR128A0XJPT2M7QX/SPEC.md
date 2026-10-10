---
task: 01M4JJJF9SCR128A0XJPT2M7QX
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/liveness.py, docs/codebase-map.md, tests/
budget_usd: 25
---

# SPEC: Подсчёт членов группы процессов — сбой `ps` не выдаётся за пустую группу

## Контекст
`orchestrator/liveness.py::_group_member_count` (~70–83) считает членов
группы через `ps -o pid= -g <pgid>` с `timeout=5` и при `OSError`,
`TimeoutExpired` и ненулевом коде возврата отдаёт 0 — так же, как для
пустой группы. `terminate_process_group` (~86–120) по этому числу решает,
ждать ли дальше и слать ли `SIGKILL` (~112–116): сбой `ps` читается как
«группа пуста», выжившим не посылается `SIGKILL`, а вызывающий получает 0
«снятых». 10.10.2026 в suite-run задачи 01M4JC58GZFHZ4PZHW254P22M2
(`-n auto`, load average 10–14) оба прогона упали на
`tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
(«0 not greater than or equal to 1»); отдельно тот же класс зелёный 3 из
3, полный прогон автогейта 01M4JD3SRN — зелёный: падение неустойчиво.

## Требования
1. Причина нуля в полном прогоне (сбой/таймаут `ps` под нагрузкой, гонка
   с `setsid`, влияние соседних тестов того же процесса xdist или иное)
   установлена и записана в PLAN.md; исправление сделано по этой причине,
   а не подгонкой теста.
2. Подсчёт членов группы различает «группа пуста» и «подсчёт не удался»
   (`ps` не запустился — `OSError`, превысил срок — `TimeoutExpired`,
   завершился с ненулевым кодом на группе, в которой есть живые
   процессы); сбой подсчёта не выдаётся за пустую группу. Группа без
   единого процесса по-прежнему даёт 0 — в том числе когда штатный `ps`
   отвечает на неё ненулевым кодом (на macOS `ps -o pid= -g <pgid>` для
   пустой группы возвращает код 1 с пустыми stdout/stderr — сверка
   10.10.2026).
3. `terminate_process_group` при сбое подсчёта не отказывается от
   `SIGKILL`: после срока ожидания (`grace_sec`) выжившие члены группы
   добиваются `SIGKILL`, как при успешном подсчёте.
4. Возвращаемое `terminate_process_group` число не занижается до 0 из-за
   сбоя подсчёта: если подсчёт до сигнала не удался, а `SIGTERM` группе
   дошёл (группа существовала), возвращается число не меньше 1.
   Сигнатура и тип возврата (`int`) `terminate_process_group` не
   меняются — вызывающие из «Только чтение» ТЗ (`runner.py`, `pause.py`,
   `release.py`, `cleanup.py`, `canary.py`, `doctor/hung_test_watchdog.py`)
   не правятся.
5. `orchestrator/catalog.py` (~732, закрыт на запись) продолжает
   вызывать `liveness._group_member_count(pgid)` и сравнивать результат
   с `> 0`: при сбое `ps` этот вызов не бросает исключение и не ломает
   строку `status`.
6. `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
   устойчив в полном прогоне `-n auto` под нагрузкой без ослабления его
   утверждений (`assertGreaterEqual(count, 1)`, `proc.wait(timeout=5)`).
7. Ожидания существующих тестовых методов `tests/` не меняются; если
   разработчик обнаружит, что смена неизбежна, — эскалация, не правка
   (смена — только разделом «Меняемое поведение», инвариант 38).

## Критерии приёмки
AC-1. `ps` подменён так, что не запускается (`OSError`) либо не отвечает
в срок (`TimeoutExpired`); группа с живым лидером, который игнорирует
`SIGTERM`: `terminate_process_group(pgid, grace_sec=<малый>)` после срока
ожидания добивает лидера `SIGKILL` (лидер мёртв после вызова) и
возвращает число ≥ 1. Ловит мутацию «сбой подсчёта = пустая группа»
(сегодня лидер переживает вызов, возврат 0).

AC-2. `ps` подменён так, что завершается с ненулевым кодом, при живой
группе с лидером, который игнорирует `SIGTERM`: то же, что AC-1 — лидер
добит `SIGKILL` после срока ожидания, возврат ≥ 1.

AC-3. Живая группа при исправном `ps`: `terminate_process_group`
возвращает число ≥ 1 и лидер группы снят — как сегодня.

AC-4. Пустая группа (процесс уже завершён и дожат) при исправном `ps`:
`terminate_process_group` возвращает 0 без исключения — как сегодня.

AC-5. При подменённом сбойном `ps` (любой из видов AC-1/AC-2)
`catalog._lease_holder_suffix` для lease этой машины с мёртвым `pid` и
заданным `pgid` возвращает строку без исключения.

## Оценка объёма и деление
Сигналов нет: зон 3 (`orchestrator/liveness.py`, `docs/codebase-map.md`,
`tests/`), критериев 5, `budget_usd` 25, записи `docs/invariants.md` на
механизм группового снятия не опираются.

## Не входит
- Время полного прогона и замок одновременных прогонов (отдельная строка,
  пункт 3 очереди критичных).
- `amend-tests` и помощник `_pult.py` (задача 01M4JD36367E5CG3GXDV429XTE).
- Правка вызывающих и прочих путей из «Только чтение» ТЗ:
  `orchestrator/runner.py`, `orchestrator/pause.py`,
  `orchestrator/release.py`, `orchestrator/cleanup.py`,
  `orchestrator/canary.py`, `orchestrator/doctor/`,
  `orchestrator/catalog.py`, `orchestrator/config.py`,
  `orchestrator/amend.py`, `orchestrator/acceptance.py`,
  `orchestrator/plank_run.py`, `scripts/`,
  `.github/workflows/ci.yml`, `tests/test_invariants.py`,
  `docs/invariants.md`, `docs/adr/`, `docs/roadmap.md`, `docs/backlog.md`,
  `docs/operator-session.md`, `templates/`, `skills/`, `CLAUDE.md`,
  `models.yaml`, `roles.yaml`, `targets.yaml`, `.artel/`.
- Смена показа `status` в `catalog.py` при сбое `ps` (что именно
  показывать — «жив»/«мёртв»/иное): файл закрыт ТЗ, требование 5
  держит только отсутствие поломки.
- Зелёный полный набор `tests/` и CI ветки — их держит пульт.

## Материалы
- ТЗ: `tasks/01M4JJJF9SCR128A0XJPT2M7QX/TZ.md`; источник — строка копилки
  10.10 «Тест test_liveness… падает в полном прогоне на машине пульта 2 из
  2».
- Наблюдение аналитика 10.10.2026 (для требования 1, не вывод): в
  окружении шага роли `PATH` = `.artel/venv/bin:…/pyenv/…/bin:/usr/bin:/opt/homebrew/bin`
  без `/bin`, а `ps` на macOS лежит в `/bin/ps` — `subprocess.run(["ps",
  …])` здесь падает `FileNotFoundError` (→ сегодня 0). Стоит сверить
  `PATH` окружения suite-run против окружения автогейта и отдельного
  прогона класса.
- Факт для требования 2: `/bin/ps -o pid= -g <pid завершённого и
  дожатого процесса>` → код 1, stdout и stderr пусты; для живой группы —
  код 0 и список pid.
- Подмену `ps` в тестах AC-1/AC-2/AC-5 разумно делать на уровне внешней
  команды (например, подложным `ps` в `PATH`), а не по имени внутренних
  функций модуля — способ подсчёта (форма сигнала сбоя) выбирает
  разработчик.
