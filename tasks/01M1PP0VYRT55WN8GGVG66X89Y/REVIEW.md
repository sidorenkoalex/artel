---
task: 01M1PP0VYRT55WN8GGVG66X89Y
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 4
---

# REVIEW: Частичная стоимость шага по видам токенов, калибровка курса

## Фаза A: проверка плана

Покрытие требований в PLAN.md полное (таблица покрывает все 7
требований SPEC), подход не конфликтует с конвенциями, шаги — размера
проверяемого MR. Один дефект: шаг 8 и раздел «Влияние на систему»
утверждают, что оба файла приёмочной планки 01M1NWCM3TDY0YABEKE8DYQA1C
(`test_ac2_known_rate_partial_charge.py`,
`test_ac3_unknown_rate_alert_and_estimate.py`) «переведены на
`{"input_tokens": N}`» — фактический HEAD ветки несёт их откаченными на
плоский `int` (коммит `338b5f38`, см. R1-F3 ниже): секция «Влияние на
систему» не соответствует фактическому diff (review-checklist, Фаза B,
критерий 6). Это симптом того же дефекта, не отдельная находка.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (четыре цены на счётчик) | OK | `config.TOKEN_RATES[role]` несёт все 4 цены на все 4 роли (config.py:329-346); ac1-тесты планки зелёные. |
| 2 (сумма произведений по видам, не средняя ставка) | OK | `spend.partial_cost_usd` — сумма произведений по `config.USAGE_TOKEN_KEYS` (spend.py:195-225); ac2/ac4-тесты планки зелёные. |
| 3 (неполный курс — именованный отказ) | OK, R1-F1 закрыт | `ValueError` неполного курса бросается из `partial_cost_usd` и перехватывается в `charge_missing_result` (spend.py:286-291), деградация на верхнюю оценку с честной причиной в журнале/алерте — воспроизведено напрямую. |
| 4 (пульт печатает коэффициент по роли) | OK | `report.token_rate_divergence` + `_divergence_html`; ac6-тесты планки зелёные. |
| 5 (порог -> алерт warning) | OK, R1-F2 закрыт | алерт калибровки заводится через `alerts.raise_token_rate_divergence_alert` (alerts.py:127) с дедупом по роли, не по тексту — воспроизведено: растущие суммы между прогонами не плодят дубликат. |
| 6 (совместимость журнала/`spent_estimate_usd`) | OK | «agent cost KNOWN» — новое действие журнала, дополняет, не заменяет «agent cost»/«agent cost PARTIAL»; ac8-тесты планки зелёные. |
| 7 (существующие тесты тарифа зелёные) | **НЕ реализовано** | `tests/test_step_cost.py`/`tests/test_agent_log.py` зелёные (106/106), НО приёмочная планка `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/`, названная в требовании 7 по имени задачи, сейчас КРАСНАЯ — 6 из 18 тестов планки падают `AttributeError` (R1-F3, регрессия итерации 1, воспроизведено). |

## Замечания

- **blocker** — `orchestrator/spend.py:285` (`charge_missing_result`) ×
  `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/test_ac2_known_rate_partial_charge.py:63,87`
  и `test_ac3_unknown_rate_alert_and_estimate.py:59,76,99,124` —
  **R1-F3 закрыт регрессией, не исправлением.** Коммит `338b5f38`
  откатил оба файла приёмочной планки завершённой задачи
  01M1NWCM3TDY0YABEKE8DYQA1C обратно на плоский `partial_tokens=1000`/
  `777` (`int`), но `spend.charge_missing_result` (строка 285:
  `total_tokens = sum(partial_tokens.values())`) требует словарь
  буквально — `.values()` на `int` кидает `AttributeError`. Воспроизведено
  напрямую: `python3 -m unittest discover -s
  tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests -p "test_*.py" -v`
  → 18 тестов, 6 ошибок, все `AttributeError: 'int' object has no
  attribute 'values'`. Это прямое нарушение требования 7/AC-9 этой же
  SPEC («существующие тесты тарифа... остаются зелёными без
  ослабления»), причём AC-9 называет именно эту планку по имени задачи.
  Усугубляет дело: приёмочный тест этой задачи
  `tasks/01M1PP0VYRT55WN8GGVG66X89Y/acceptance_tests/test_ac9_existing_tariff_tests_stay_green.py`
  помечен `# AC-9: skip` с обоснованием «регрессия уже покрыта штатным
  CI-гейтом... (включая... 01M1NWCM3TDY0YABEKE8DYQA1C)» — обоснование
  ФАКТИЧЕСКИ НЕВЕРНО и маскирует именно эту регрессию: ни CI-джоб
  `python` (`.github/workflows/ci.yml:70`, `unittest discover -s tests`,
  не видит `tasks/`), ни `orchestrator/acceptance.py::run_full_suite`
  (discover по `root/tests`, тоже не видит `tasks/`), ни
  `orchestrator/acceptance.py::run` (сканирует только
  `acceptance_tests/` ТЕКУЩЕЙ задачи, не чужой) ни разу не запускают
  `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/` — эта планка не
  гоняется НИКАКИМ штатным гейтом, только ручным прогоном (как выше).
  PLAN.md шаг 8 при этом всё ещё утверждает, что файлы «переведены на
  `{"input_tokens": N}`» — расходится с фактическим кодом (см. Фаза A).
  Предложение: вернуть оба файла планки к варианту с
  `{"input_tokens": 1000}`/`{"input_tokens": 777}` — единственный
  вариант, совместимый с новой сигнатурой `charge_missing_result`; в
  коммите явно сослаться на основание правки локальной планки
  (интерфейс сменился этой же SPEC намеренно, требование 2/AC-2, а не
  произвольная косметика) и актуализировать PLAN.md шаг 8 под
  фактический diff. Альтернатива, если Оператор сочтёт саму правку
  чужой планки недопустимой без отдельного основания, — научить
  `charge_missing_result` принимать также плоский `int` (нормализовать
  к `{"input_tokens": partial_tokens}` в начале функции), но это слабее
  первого варианта: типизация по видам вводится этой же SPEC намеренно
  (требование 2), обратная совместимость с `int` нигде не требуется
  явно ни одним АС.

- minor — `tasks/01M1PP0VYRT55WN8GGVG66X89Y/acceptance_tests/test_ac9_existing_tariff_tests_stay_green.py` —
  независимо от исхода R1-F3, обоснование пометки `# AC-9: skip`
  фактически неточно (см. выше: ни один штатный гейт не гоняет чужую
  планку) и должно быть переформулировано, когда planка снова станет
  зелёной — иначе следующий читатель унаследует то же ложное
  представление о покрытии.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/spend.py:228-291 | `ValueError` неполного курса не перехватывался в `charge_missing_result` | таймаут/`pause --now` обрушил бы процесс необработанным исключением, потеряв чекпоинт и запись журнала | исправлено: `try/except ValueError` (spend.py:286-291), деградация на верхнюю оценку с честной причиной — воспроизведено, работает корректно |
| R1-F2 | accepted | orchestrator/alerts.py:79-102; orchestrator/report.py:253-318 | дедуп `raise_alert` не работал для алерта калибровки (текст несёт растущие суммы) | повторные прогоны `cmd_report` при сохраняющемся расхождении плодили новый алерт на каждый вызов | исправлено: `alerts.raise_token_rate_divergence_alert`, дедуп по (target=None, kind=warning, source, префикс роли в message) — воспроизведено через ac7-тесты планки |
| R1-F3 | needs_work | orchestrator/spend.py:285; tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/test_ac2_known_rate_partial_charge.py, test_ac3_unknown_rate_alert_and_estimate.py | откат планки на плоский `int` (338b5f38) несовместим с сигнатурой `charge_missing_result` (требует dict) | все 6 из 18 тестов планки красные (`AttributeError`), требование 7/AC-9 нарушено; PLAN.md шаг 8 описывает состояние, которого нет в коде | вернуть планку на `{"input_tokens": N}` с явной ссылкой на основание правки в коммите (интерфейс сменился этой же SPEC намеренно), актуализировать PLAN.md шаг 8 |
| R1-F4 | accepted | tests/test_step_cost.py, tests/test_agent_log.py | докстринги «Ловит мутацию» отсутствовали у изменённых тестов | конвенция test-authoring не соблюдалась, следующему ревьюеру сложнее сверить тест с заявленной мутацией | докстринги добавлены к перечисленным методам, содержательные (описывают сценарий/наблюдаемое свойство, не пересказ имени) — проверено чтением диффа и прогоном (106/106 зелёных) |

## Вердикт

changes_requested — R1-F3 закрыт неверно: то, что коммит `338b5f38`
назвал исправлением, на деле регрессия (планка `01M1NWCM3TDY0YABEKE8DYQA1C`
красная, требование 7/AC-9 нарушено). Разработчику: вернуть планку на
разбивку по видам (`{"input_tokens": N}`) с явным основанием правки в
коммите, актуализировать PLAN.md шаг 8 под фактический код и
переформулировать обоснование пометки `# AC-9: skip` (minor). R1-F1,
R1-F2, R1-F4 закрыты корректно, воспроизведены — приняты.

Примечание для следующей итерации: в рабочем каталоге на старте этого
шага уже лежал черновик REVIEW.md (не закоммичен, `??` в git status) с
похожими выводами по R1-F3, но дополнительно заявлявший блокер R2-F1
(коллизия `docs/invariants.md`/`scripts/guard.py`, `python3 scripts/guard.py
--all` якобы красный). Этот блокер не воспроизвёлся: `guard.py --all` и
точечный прогон на SPEC.md/PLAN.md этой задачи сейчас зелёные —
SPEC.md уже несёt секцию «Оценка объёма и деление» (добавлена
Оператором на гейте, что и написано в самой секции), которая гасит
сигнал независимо от текстового совпадения с `docs/invariants.md`.
Черновик был написан по более старой версии SPEC.md, ещё без этой
секции — в реестр не включаю, это не текущий дефект.

## Проверено исполнением

- `python3 -m unittest tests.test_step_cost tests.test_agent_log -v` — 106 тестов, все зелёные.
- `python3 -m unittest discover -s tasks/01M1PP0VYRT55WN8GGVG66X89Y/acceptance_tests -p "test_*.py" -v` — 18 тестов, все зелёные (AC-9 помечен `skip`, обоснование неточно — см. «Замечания»).
- `python3 -m unittest discover -s tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests -p "test_*.py" -v` — 18 тестов, 6 ошибок (`AttributeError: 'int' object has no attribute 'values'`, spend.py:285) — регрессия R1-F3.
- `python3 -m unittest tasks.01M1NWCM3TDY0YABEKE8DYQA1C.acceptance_tests.test_ac4_no_usage_events_unchanged -v` — 2 теста, зелёные (сценарий `saw_usage_event=False` не задет отказом типа, подтверждает границу PLAN.md шага 8).
- `python3 scripts/guard.py --all` — «GUARD: ок (458 файлов)»; отдельно `python3 scripts/guard.py tasks/01M1PP0VYRT55WN8GGVG66X89Y/SPEC.md tasks/01M1PP0VYRT55WN8GGVG66X89Y/PLAN.md` — «GUARD: ок (2 файлов)». Проверено также напрямую через `guard._zone_paths`/`guard._invariants_doc_text` — сигнал «затронут инвариантный механизм» действительно срабатывает (пересечение с `docs/invariants.md:82`), но секция «Оценка объёма и деление» в SPEC.md непуста, поэтому `split_assessment_errors` гасится корректно, ошибки нет.
- `python3 scripts/codebase_map.py` в рабочем дереве, сравнение с закоммиченной картой без строки `built_at_sha` (`grep -v '^built_at_sha:'`) — идентично, карта актуальна; изменение отменено (`git checkout -- docs/codebase-map.md`) перед завершением ревью.
- Diff ветки: `git diff main...task/01m1pp0vyrt55wn8ggvg66x89y-chastichnaya-stoimost-shaga-po` (пакетный инкрементальный diff «от прошлого вердикта» пуст, т.к. записанный sha совпадает с текущим HEAD — перепроверено вручную полным diff ветки от merge-base `fb7895da`, см. review-checklist «Инкрементальный diff — пустой не значит без изменений»).

## Предложения системе

- Пакетный инкрементальный diff «от sha прошлого вердикта до HEAD» второй раз подряд (после T087) совпал с текущим HEAD и оказался пуст, хотя на ветке лежал непринятый фикс-коммит (`338b5f38`) — механика фиксации sha прошлого вердикта у оркестратора всё ещё не отличает «после автокоммита фикса разработчика» от «на момент вердикта ревьювера»; стоит завести юнит-тест этого класса при следующей правке места, которое пишет этот sha в пакет ревью.
