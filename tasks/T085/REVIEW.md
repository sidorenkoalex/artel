---
task: T085
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Исполнение ADR-0010 — стоп-лосс из автогейта в отчётную веху

## Гейт плана (Фаза A)

- Покрытие: все 5 требований SPEC покрыты шагом 1 плана (таблица
  «Покрытие требований» полна, требования 2/5 верно помечены как
  регрессия — код там не меняется).
- Шаги — проверяемая единица размера MR (правка двух файлов + прогон
  тестов), не микрооперации и не «сделать всё».
- Подход не конфликтует с конвенциями: правка `_autogate_conditions`
  точечная (удалён один блок `if`), комментарии `config.py` переписаны
  под ADR-0010 текстом («веха», ссылка на ADR-0010) — соответствует
  формулировке самого ADR.
- «Влияние на систему» описывает откат только для `fsm.py`/`config.py`
  (тривиальный revert одной ветки `if`), но не называет отдельно второй
  по объёму кусок диффа этой ветки — переработку маршрута
  `tasks/T066/acceptance_tests/` под состояние `verifying` (ADR-0009/
  T079) и CI-мок (~160 строк в 4 файлах). Правка легитимна и
  санкционирована `ANSWER-1.md` (мандат Оператора на эскалацию
  test_author'а, коммит 70cb297), но PLAN не фиксирует её как side
  effect явно — см. замечание ниже (minor, не блокер).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (убрать условие A1 из автогейта) | OK | `orchestrator/fsm.py::_autogate_conditions` — блок с `store.total_spent`/`PROGRAM_STOP_LOSS_USD` удалён (строки 374 diff), проверка отсутствует и в текущем коде. AC-1: `tasks/T085/acceptance_tests/test_ac1_*` — 2/2 зелёных (пробитый порог не мешает дойти до `merge_gate`, причина «порог расхода программы» не появляется ни в журнале, ни в выводе). |
| 2 (алерты остаются информационными) | OK | `budget.check_program_spend`/`alerts.raise_alert(kind=threshold)`/`alerts.ack` не тронуты диффом (нет в списке изменённых файлов). AC-3/AC-4: `tasks/T085/acceptance_tests/test_ac3_*`, `test_ac4_*` — зелёные. AC-7: `tests/test_doctor.py`, `tests/test_multitarget.py`, `tests/test_multitarget_invariants.py` — 138 тестов, зелёные. |
| 3 (комментарии config.py под ADR-0010) | OK | `orchestrator/config.py:109-117` — упоминает ADR-0010 и слово «веха» текстом для обеих констант. AC-5: `tasks/T085/acceptance_tests/test_ac5_*` (разбор исходника regex) — 2/2 зелёных. |
| 4 (тесты состава T066 обновлены) | OK (minor) | `tasks/T066/acceptance_tests/` — сценарий `ProgramThresholdBreachBlocksAutogateTest` удалён из `test_ac4_failing_condition_stays_in_acceptance.py`, маршрут остальных сценариев обновлён под `verifying`. `python3 -m unittest discover -s tasks/T066/acceptance_tests` — 14/14 зелёных. AC-6: `tasks/T085/acceptance_tests/test_ac6_*` (реальный subprocess-прогон каталога) — зелёный. Минус: осталась мёртвая функция-хелпер, см. замечания. |
| 5 (учёт расхода не тронут) | OK | `orchestrator/store.py`, `orchestrator/retro.py`, `orchestrator/budget.py` — не в списке изменённых файлов. AC-8: `tasks/T085/acceptance_tests/test_ac8_*` — 4/4 зелёных (total_spent, пересев, идемпотентность, живая строка не задваивается). |

## Замечания

- minor — `tasks/T066/acceptance_tests/_sandbox.py:68,369-378` — метод
  `seed_program_overspend()` и константа `OTHER_SPENDER_TASK` остались
  в файле мёртвым кодом: их единственный вызывающий,
  `ProgramThresholdBreachBlocksAutogateTest`, эта же ветка удалила из
  `test_ac4_failing_condition_stays_in_acceptance.py`. Проверено
  `grep -rn "seed_program_overspend" tasks/T066/acceptance_tests/*.py`
  — единственное определение, без вызовов. Сам PLAN в разделе «Риски»
  явно предупреждал не оставлять мёртвый код после удаления блока A1
  (упомянул только переменную `total` в `fsm.py`), но пропустил этот
  случай в тестовой фикстуре. Предложение: удалить оба символа из
  `_sandbox.py` (в `tasks/T085/acceptance_tests/_sandbox.py` есть
  собственная независимая копия того же хелпера для AC-1 — она
  используется и трогать её не нужно).
- minor — `tasks/T085/PLAN.md`, раздел «Влияние на систему» — не
  называет явно переработку маршрута `tasks/T066/acceptance_tests/`
  под `verifying`/CI-мок (ADR-0009/T079) как отдельный side effect
  этой ветки; откат описан только для `fsm.py`/`config.py`. Правка
  легитимна (санкционирована `ANSWER-1.md`, коммит 70cb297), но чтобы
  подтвердить «затронуто ровно то, что заявлено» без реконструкции по
  git log, это стоило бы одной строкой обозначить в самом PLAN.

## Вердикт
approved

## Проверено исполнением
- `python3 -m unittest discover -s tasks/T066/acceptance_tests` — 14 тестов, все зелёные.
- `python3 -m unittest discover -s tasks/T085/acceptance_tests` — 18 тестов, все зелёные.
- `python3 -m unittest discover -s tests` — 1118 тестов, все зелёные (шум `sqlite3.ProgrammingError` в stderr — предсуществующее сообщение `__del__` из `orchestrator/store.py:90` про кросс-тредовое закрытие соединений в тестовых fixtures, не относится к этой правке и не влияет на код возврата/итог прогона).
- `python3 -m unittest tests.test_doctor tests.test_multitarget tests.test_multitarget_invariants` (AC-7, поимённо) — 138 тестов, все зелёные.
- `python3 scripts/guard.py --all` — `GUARD: ок (308 файлов)`.
- `python3 scripts/codebase_map.py` (регенерация во временную проверку) → `git diff --stat -- docs/codebase-map.md` показал разницу только в строке `built_at_sha`, содержимое карты совпало с закоммиченным — карта не стухла; регенерацию откатил (`git checkout -- docs/codebase-map.md`), рабочее дерево чистое.
- `git show 7f2afd3 --stat` — подтвердил существование и содержимое операторского коммита, на который ссылается `ANSWER-1.md` (секция «Проверено исполнением» добавлена в `tasks/T047`, `T064`, `T066` фикстуры).
- Чтение текущего состояния `orchestrator/fsm.py` (строки 358-409), `orchestrator/config.py` (95-124), `orchestrator/budget.py::check_program_spend`, `orchestrator/alerts.py::ack` — код на диске совпадает с диффом, `store` в `fsm.py` не осиротел (используется в других местах файла).
- `grep -rln "ProgramThresholdBreachBlocksAutogateTest" .` — только докстринг-упоминания истории удаления (в самом удалённом тесте и в PLAN.md), не забытый код.

## Предложения системе
- Класс «дифф удаляет тест/сценарий, но не хелпер, которым он
  пользовался» (см. `seed_program_overspend` выше) — стоило бы держать
  в чек-листе test_author явным пунктом рядом с уже существующим
  «не оставляй мёртвый код» из PLAN, а не только применительно к
  production-коду.
