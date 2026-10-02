---
task: 01M3SF7DPFGEZ7VYEGGXGTX49E
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Main не краснеет незаметно: guard после снимка, CI main после мержа и в pin-update

## Фаза A: план

- Таблица покрытия полна (требования 1–5 → шаги 1–6), шаги — единицы размера MR.
- В «Подходе» и «Рисках» посылка обхода исправлена: класс push'а теперь считается по диапазону `before..after` между головами с проверками. Оценка «~4–5 вызовов `gh` на мерж плюс по одному на документный коммит» согласуется с тестом топологии гейта: там опрошено 5 коммитов.
- «Влияние на систему» соответствует инкрементальному диффу. Изменены `ci.py` (`_push_touches_code`, `skipped_at`), явная передача `fixes_main` в `fsm.py`/`fsm_merge_gate.py`, `tests/test_main_ci_line.py` (тесты, добавленные этой задачей) и сигнатуры двух `fake_body` в `tests/test_merge_gate_ci_wait.py`. Ничего вне заявленного не тронуто.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (guard после снимка, до push) | OK | В этой итерации не менялось. `_guard_all_or_refuse` стоит между картой и RETRO; планка AC-1 зелёная. |
| 2 (цвет CI main по проверкам первой родительской линии) | OK | Пропущенные на голове проверки откладываются (`skipped_at`, `orchestrator/ci.py:505,551-552`). С обхода они снимаются только на следующей голове с проверками и только если диапазон `commit..push_head` меняет код (`ci.py:528-534`). Это повторяет `before..after` job'а `changes`. Документная цепочка поверх красного кода красный не маскирует: проверено тестами и мутацией. |
| 3 (`pin-update` сверяет CI, `pin --to` нет; строка doctor) | OK | Проводка не менялась. После R1-F1 обход больше не упирается в потолок на топологии гейта, поэтому вечного `unknown`/`warn` нет. |
| 4 (ожидание CI новой головы main) | OK | `MAIN_CI_WAIT_LIMIT_SEC = 18*60` объявлена в модуле гейта мержа; опрос идёт до зелёного, красного или «не дождался». Планка AC-4 зелёная. |
| 5 (тесты, существующие не ослаблены) | OK | В `tests/test_merge_gate_ci_wait.py` у двух подмен только добавлен параметр `fixes_main=None`: ассерты и сценарии те же. В `tests/test_main_ci_line.py` переписан метод, который добавила сама эта задача: в main его нет, так что существующий тест не ослаблен. |

## Замечания

Новых замечаний нет. Обе записи прошлой итерации проверены:
- **R1-F1.** `_push_touches_code(base, head)` берёт дифф от предыдущей головы с проверками. На модели 70 мержей гейта (голова RETRO документная, код в merge-коммите без проверок) исход `green`, опрошено 5 коммитов вместо 200. Временная мутация «дифф с первым родителем» возвращает ровно дефект R1-F1: `unknown`, «protected-paths не исполнялись на 200 коммитах». Мутация «снимать пропущенное без сверки класса» краснит `test_doc_push_keeps_check_pending_to_the_code_push`, а также AC-2 и AC-6 долгоживущего файла задачи.
- **R1-F2.** `fixes_main=fixes_main` теперь передаётся явно (`orchestrator/fsm.py:1025`, `orchestrator/fsm_merge_gate.py:1231`); подмены адаптированы.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/ci.py:423-436, 528-552 | Снятие проверки, не исполняемой на push, опиралось на дифф коммита с первым родителем. | Обход до потолка, постоянный `unknown` у `pin-update`/`doctor`/ожидания после мержа. | Исправлено: класс push'а считается по диапазону между головами с проверками. Есть тест топологии гейта и тест документного push'а поверх красного; обе мутации проверены. Принято. |
| R1-F2 | accepted | orchestrator/fsm.py:1025; orchestrator/fsm_merge_gate.py:1231 | `fixes_main` передавался условным `**{}`. | Скрытая связка с сигнатурой тестовых подмен. | Исправлено: передаётся явно, подмены получили параметр. Принято. |

## Вердикт

approved. Реестр закрыт целиком (R1-F1, R1-F2 — `accepted`), blocker/major нет.

## Проверено исполнением

- `ARTEL_ROLE` снят внутри процесса через `os.environ.pop`, затем `pytest`:
  - файлы: `tests/test_main_ci_line.py`, `tests/test_merge_gate_ci_wait.py`, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`, `tasks/01M3SF7DPFGEZ7VYEGGXGTX49E/acceptance_tests`, `tests/test_pin.py`, `tests/test_cmd_approve_dispatch.py`, `tests/test_ci_status.py`, `tests/test_doctor.py`;
  - результат: 274 passed, 36 subtests passed (66 с).
- Временные мутации — через `mock.patch.object(ci, '_push_touches_code', …)` в процессе, файлы не правились:
  - Дифф с первым родителем (`real(head+'^1', head)`): красный `MainLineStatusTest::test_check_skipped_on_code_commit_stops_the_walk` с текстом «protected-paths не исполнялись на 200 коммитах линии». Это воспроизводит R1-F1.
  - `lambda b, h: True` (снятие без сверки класса push'а): 6 красных. Среди них `test_doc_push_keeps_check_pending_to_the_code_push`, `test_failure_outranks_running_check`, `test_check_unresolved_within_the_cap_is_not_confirmed` и долгоживущие `test_ac2_skipped_check_takes_result_from_earlier_commit` и `test_ac6_red_merge_then_doc_commit_keeps_main_red`.
- `tests/test_codebase_map.py` — 34 passed.
- `scripts/codebase_map.py` перегенерирован; содержимое без строки `built_at_sha:` совпадает с закоммиченной картой. Файл возвращён как был.
- Дифф `tests/` сверен: удалённых или ослабленных ассертов в существующих тестах нет.
- `__pycache__`, оставленный прогоном в `acceptance_tests/`, удалён.
- Ограничение: `main_line_status` на живом GitHub не проверялся, потому что `gh` в шаге роли не авторизован. Топология проверена на `FakeLine`.

## Предложения системе

- Временную мутацию в шаге ревьювера удобно вносить через `mock.patch.object` в процессе pytest. Правка файла с `cp` для бэкапа требует подтверждения, которого в шаге нет. Стоит упомянуть этот приём в skills/review-checklist.md («Сторож — проверен временной мутацией»).
