---
task: 01M1PP0VYRT55WN8GGVG66X89Y
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 4
---

# REVIEW: Частичная стоимость шага по видам токенов, калибровка курса

## Служебное: diff пакета не про эту задачу

Инкрементальный diff ревью-пакета (от sha `765345c5` до HEAD) целиком
состоит из «подтяжки main» — коммиты `51cd45c5`/`c6c2b03c`/`bed9c71c`
принадлежат ЧУЖОЙ задаче 01M1P9QCHPHSCEA6TK13PV85SP (гейт зон,
`orchestrator/fsm_advance.py`, `orchestrator/store.py`,
`tests/test_zones_gate.py`), а `765345c5` сам оказался предыдущей
«подтяжкой main» на ветке этой задачи (`git log` ветки: обе точки диапазона
— коммиты `01M1PP0VYRT55WN8GGVG66X89Y: подтяжка main`). Ни одного файла из
зоны этой SPEC (`spend.py`/`config.py`/`report.py`/`agent_log.py`/
`pause.py`/`alerts.py`/тесты тарифа) инкрементальный diff не содержит —
класс из копилки review-checklist («инкрементальный diff может указывать
не туда», T082/T087), см. «Предложения системе».

Фактическая работа итерации 4 (закрытие R3-F1 по ANSWER-1.md) лежит в
коммитах `35b62dd0` (правка текста пометки `# AC-9: skip`, скопирована из
артефактной ветки Оператора) и автокоммите шага developer `9274fa77`
(PLAN.md шаг 12 + обновление реестра REVIEW.md) — оба ДО `765345c5`.
Ревью проведено по факту текущего HEAD ветки (`7dcfdbaa`), не по
инкрементальному diff'у пакета: прочитаны PLAN.md/SPEC.md/ANSWER-1.md
целиком (из пакета), плюс точечно — `git show 9274fa77` (что именно
изменил шаг developer после ANSWER-1) и исходники `spend.py`/`report.py`/
`alerts.py`/`config.py` (подтвердить, что реализация требований 1-6
не деградировала между итерацией 3 и текущим HEAD).

## Фаза A: проверка плана

Изменение с итерации 3 — только шаг 12 (закрытие R3-F1), покрытие
требований и размер шагов без изменений с итерации 2. Шаг 12
соответствует ANSWER-1.md дословно: объём ограничен одной правкой
текста локованного файла, что и подтверждено при чтении текущего
содержимого `test_ac9_existing_tariff_tests_stay_green.py` (формулировка
про CI-покрытие `tests/` и ручное подтверждение чужой планки ревьювером/
Оператором — не заявляет несуществующего автопокрытия). Новых дефектов
Фазы A нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (четыре цены на счётчик) | OK | `orchestrator/config.py:329-346` — все четыре роли несут `input_usd_per_token`/`output_usd_per_token`/`cache_creation_usd_per_token`/`cache_read_usd_per_token`. Без изменений с итерации 2. |
| 2 (сумма произведений по видам, не средняя ставка) | OK | `spend.partial_cost_usd` — цикл по `config.USAGE_TOKEN_KEYS`, каждый вид своей ставкой; проверено чтением `orchestrator/spend.py:195-221`. |
| 3 (неполный курс — именованный отказ) | OK | `partial_cost_usd` бросает `ValueError` на отсутствующем поле ставки (R1-F1 итерации 2 закрыт: `charge_missing_result` перехватывает и деградирует на верхнюю оценку, не падает конвейер). |
| 4 (пульт печатает коэффициент по роли) | OK | `report.token_rate_divergence` — читает журнал, отсутствующая роль не входит в результат (AC-6). |
| 5 (порог -> алерт warning) | OK | `config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD=0.5`, `alerts.KINDS` несёт `warning`, дедуп по роли через `raise_token_rate_divergence_alert` (R1-F2 итерации 1 закрыт). |
| 6 (совместимость журнала/`spent_estimate_usd`) | OK | `charge_step` пишет ОТДЕЛЬНУЮ запись `KNOWN_COST_JOURNAL_ACTION`, не заменяет `cost_note`/«agent cost PARTIAL»; AC-8 тесты зелёные (см. «Проверено исполнением»). |
| 7 (существующие тесты тарифа зелёные) | **OK, R3-F1 закрыт** | `tests/test_step_cost.py`+`tests/test_agent_log.py` — 106/106; планка этой задачи — 18/18; планка 01M1NWCM3TDY0YABEKE8DYQA1C — 18/18 (регрессия итерации 2 не вернулась). R3-F1 (обоснование пометки `# AC-9: skip`) закрыто мостом Оператора (ANSWER-1.md, ADR-0012) — текущий текст пометки проверен построчно, соответствует описанному в ANSWER-1.md исправлению. |

## Замечания

(пусто — 0 blocker/major/minor поверх уже закрытого реестра)

## Реестр замечаний

Все записи прошлых итераций (R1-F1, R1-F2, R1-F3, R1-F4, R3-F1) —
статус `accepted`, не повторяю (кумулятивное правило review-checklist:
уже `accepted` восстановимы из git-истории файла). Новых записей эта
итерация не заводит.

R3-F1 отдельно перепроверен в этой итерации (не просто унаследован):
текст `# AC-9: skip` на текущем HEAD (`tasks/01M1PP0VYRT55WN8GGVG66X89Y/
acceptance_tests/test_ac9_existing_tariff_tests_stay_green.py:24-32`)
прочитан целиком и сверен с описанием правки в ANSWER-1.md и PLAN.md
шаге 12 — формулировка корректна (CI видит только `tests/`, чужая планка
подтверждена ручным прогоном ревьювера и Оператором на приёмке, не
автоматикой). Закрытие подтверждаю.

## Вердикт

approved — все семь требований SPEC/AC-1..AC-9 реализованы верно;
единственный открытый пункт прошлой итерации (R3-F1, minor) закрыт
Оператором по мандату ADR-0012 и независимо перепроверен в этой
итерации; регрессия предыдущей итерации (R1-F3) не вернулась;
инкрементальный diff пакета не относится к этой задаче (см. «Служебное»
выше) — вердикт вынесен по факту текущего HEAD ветки, не по этому diff'у.

## Проверено исполнением

- `python3 -m unittest tests.test_step_cost tests.test_agent_log -v` — 106 тестов, все зелёные.
- `python3 -m unittest discover -s tasks/01M1PP0VYRT55WN8GGVG66X89Y/acceptance_tests -p "test_*.py" -v` — 18 тестов, все зелёные.
- `python3 -m unittest discover -s tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests -p "test_*.py" -v` — 18 тестов, все зелёные (регрессия R1-F3 не вернулась).
- `python3 scripts/guard.py --all` — «GUARD: ок (463 файлов)».
- `python3 scripts/guard.py tasks/01M1PP0VYRT55WN8GGVG66X89Y/SPEC.md tasks/01M1PP0VYRT55WN8GGVG66X89Y/PLAN.md tasks/01M1PP0VYRT55WN8GGVG66X89Y/ANSWER-1.md` — «GUARD: ок (3 файлов)».
- `git show 9274fa77` (артефактная ветка, шаг developer после ANSWER-1) — прочитан целиком, изменил только PLAN.md (шаг 12) и REVIEW.md (реестр R3-F1 -> accepted), кода не тронул — соответствует ограничению объёма ANSWER-1.md.
- `git log task/01m1pp0vyrt55wn8ggvg66x89y-chastichnaya-stoimost-shaga-po` — подтверждено, что диапазон `765345c5..HEAD` инкрементального diff'а пакета не содержит ни одного коммита этой задачи (только подтяжки main и коммиты чужой задачи 01M1P9QCHPHSCEA6TK13PV85SP).
- Чтение исходников `orchestrator/spend.py` (`usage_tokens_by_type`, `stream_usage_by_type`, `partial_cost_usd`, `charge_missing_result`, `charge_step`), `orchestrator/report.py` (`token_rate_divergence`), `orchestrator/alerts.py` (`KINDS`, `raise_token_rate_divergence_alert`), `orchestrator/config.py` (`TOKEN_RATES`, `TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD`) — соответствуют требованиям 1-6 и решениям R1-F1/R1-F2 прошлых итераций.
- Полный набор `tests/` в этом шаге не гонялся (решение Оператора 05.09) — его зелёность на каждый пуш проверяет CI; в шаге прогнаны затронутые модули и обе приёмочные планки (выше).

## Предложения системе

- Инкрементальный diff ревью-пакета этой итерации указывал не на код
  этой задачи, а на «подтяжку main», принёсшую коммиты чужой задачи
  (01M1P9QCHPHSCEA6TK13PV85SP) — тот же класс, что уже отмечен по T082/
  T087 в review-checklist («sha предыдущего вердикта не всегда надёжный
  ориентир»), но здесь диапазон не пустой и не короткий, а **полный и
  правдоподобный дифф чужой задачи** — заметить подмену труднее, чем
  пустой diff: без сверки `git log` ветки легко было бы review дифф
  чужой задачи вместо этой. Стоит явно добавить в скил этот подвид:
  непустой diff, целиком состоящий из «подтяжки main», — тоже повод
  сверить вручную, не только пустой/короткий.
