---
task: 01M3YJ7VQ7CSBBPC8X84Z0YG3R
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Часы теста гейта мержа не ловят паузы стандартной библиотеки

## Фаза A — план
- Таблица покрытия полна: требования 1–3, 6 — шаги 1–3/5; требование 4 —
  раздел «Проверка остальных файлов» с файлом, местом и утверждением по
  каждому из трёх файлов; требование 5 — явно «не задействовано».
- Шаги — размера MR, проверяемые. Подход (подмена `fsm_merge_gate.time`
  на `SimpleNamespace(sleep, monotonic)`) совпадает с выбором аналитика в
  SPEC и не требует правки кода пульта.
- «Влияние на систему» = фактический diff: три файла `tests/`,
  `orchestrator/` не тронут, откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tests/test_merge_gate_ci_wait.py:59-67` — одна подмена `fsm_merge_gate.time`; помощник `wait()` читает `fsm_merge_gate.time.monotonic()` (`:86`). В `fsm_merge_gate.py` к `time` обращаются только `sleep`/`monotonic` (grep: строки 319/330/335/560/573/577/1237/1242/1243/1260) — двух атрибутов хватает. |
| 2 | OK | `git diff b9cac34c -- tests/test_merge_gate_ci_wait.py tests/test_ci_status_kind_gate.py \| grep '^[-+].*assert'` — 0 строк; методы не тронуты, изменены только `setUp`, импорт и строка `start =` в помощнике (разрешена SPEC). |
| 3 | OK | `tests/test_ci_status_kind_gate.py:59-67` — тот же приём, `import time` → `import types`, импорт `fsm_merge_gate`. |
| 4 | OK | PLAN называет `tests/test_main_ci_line.py` (`sleep.assert_not_called()` под глобальным `mock.patch("time.sleep")`) как ту же уязвимость; `test_merge_queue.py`/`test_invariants.py` — без точных утверждений; ничего не правилось. |
| 5 | OK | `orchestrator/fsm_merge_gate.py` не изменён (diff --stat). |
| 6 | OK | `tests/test_merge_gate_clock_isolation.py` — настоящий `subprocess.run(... time.sleep(0.3) ..., timeout=10)`, утверждения `sleep_calls == []` и `monotonic()` без сдвига; заявка «Ловит мутацию» называет наблюдаемое расхождение (записи в `sleep_calls`) — подтверждена временной мутацией (ниже). Базовый класс импортирован модулем — его тестовые классы повторно не собираются; у `MergeGateCiWaitUnitTest` своих `test_*` нет. |

## Замечания
Нет замечаний уровня blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved. Косметика без последствий (не заводится в реестр): в
`tests/test_merge_gate_ci_wait.py:67-68` пропала пустая строка между
`setUp` и `journal_blob`.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider --durations=5 tests/test_merge_gate_clock_isolation.py tests/test_merge_gate_ci_wait.py tests/test_ci_status_kind_gate.py tasks/01M3YJ7VQ7CSBBPC8X84Z0YG3R/acceptance_tests` — 33 passed за 12.9 с (планка 9 из них).
- Проверка «изоляция не включила настоящих ожиданий»: временный скрипт-шпион подменял `time.sleep` модуля `time` на счётчик и прогонял `tests.test_merge_gate_ci_wait` + `tests.test_ci_status_kind_gate` через unittest — `Counter()`, суммарно 0 с реальных пауз (пути гейта не ждут через `time` других модулей). Скрипт удалён.
- Временная мутация сторожа: в `MergeGateCiWaitUnitTest.setUp` добавлен `mock.patch.object(time, "sleep", self.clock.sleep)` → `tests/test_merge_gate_clock_isolation.py` красный (`:43`, `sleep_calls` = `[0.001, 0.002, … 0.05, …]`, >4 млн символов: фиктивный sleep не спит, а `Popen._wait` считает остаток по настоящему `monotonic` модуля `subprocess`, пока ребёнок жив 0.3 с — красный при любой скорости машины). Мутация снята, файл снова 1 passed, `git status` по `tests/` чист.
- `git diff b9cac34c -- <оба файла> | grep '^[-+].*assert'` — 0 строк (утверждения не тронуты).
- `python3 scripts/codebase_map.py` → `git diff docs/` — отличие только в `built_at_sha` (карта свежая по содержимому); регенерация откачена `git checkout`.
- Планка: все три `test_*.py` помечены `Группа: разовый`; долгоживущее свойство изоляции держит `tests/test_merge_gate_clock_isolation.py`. Пометок `manual|skip` нет.

## Предложения системе
- Класс «глобальная подмена `time.sleep` + точное утверждение на паузы» остаётся в `tests/test_main_ci_line.py` (~строка 355, `sleep.assert_not_called()`) — поддерживаю кандидат в бэклог из PLAN.
