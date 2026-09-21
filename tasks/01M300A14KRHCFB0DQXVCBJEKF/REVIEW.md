---
task: 01M300A14KRHCFB0DQXVCBJEKF
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Тариф на модель, история тарифов и сверка по паре роль-модель

## Фаза A: гейт плана

1. **Покрытие требований полно.** Таблица PLAN отображает все двенадцать
   требований SPEC на шаги 1-8, без пропусков; шагов, не привязанных ни к
   одному требованию, нет.
2. **Шаги — единицы размера MR.** Восемь шагов по одному-двум модулям
   (`models.py`; `config.py`; `spend.py`; схема+история; `report.py`;
   `doctor/`; `docs/stack.md`; тесты) — ни микроопераций, ни «сделать
   всё».
3. **Подход не конфликтует с конвенциями.** SQL истории тарифов живёт в
   `store.py` (ADR-0003 3ж), паритет DDL/миграции держится одним литералом
   `schema.MODEL_TARIFFS_DDL` вместо двух копий текста, крутилки Оператора
   (`TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD`) не тронуты, `models.yaml`
   ветка не правит. Смена адресата алерта с роли на модель (п. 5
   «Подхода») — осознанная и обоснованная, порог и условие срабатывания
   дословно прежние, дедуп `alerts.raise_token_rate_divergence_alert`
   идёт по префиксу сообщения и с новым ключом работает так же
   (`orchestrator/alerts.py:171-176`).

Два замечания фазы A: секция «Влияние на систему» не полна (R1-F1), а
перечень «Обновляемые ожидания» расходится с фактическим диффом (R1-F2).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `TOKEN_RATES` удалена; `spend.role_tariff`/`model_tariff` тянут тариф через `models.py`; ссылок на имя в `orchestrator/`+`scripts/` нет (осталось только историческое упоминание в докстринге `orchestrator/alerts.py:45`, вне зоны задачи; планка AC-1 разбирает ссылки по `ast`, докстринг ссылкой не считает — законно) |
| 2 | OK | `known_cost_pairs` ключует пару `(роль, модель)`, модель берёт из `model=` строки, фильтрует по дате тарифа ЭТОЙ модели (`orchestrator/spend.py:477-492`) |
| 3 | OK | строка без опознаваемой модели и модель вне каталога — тихий `continue` тем же приёмом, что строка без `actual_usd` (`orchestrator/spend.py:477-486`) |
| 4 | OK | `report.token_rate_divergence` складывает пары всех ролей модели в один ключ-модель, значение остаётся `RateDivergence(float)` (`orchestrator/report.py:379-388`) |
| 5 | OK | `schema.MODEL_TARIFFS_DDL` подставлен и в `SCHEMA`, и в `migrate` одним литералом (`orchestrator/schema.py:35-42, 267-273`) |
| 6 | OK | `store.record_model_tariff` сравнивает по ценам+дате+источнику и пишет только на отличии; команды записи нет |
| 7 | OK | `_tariff_note` дописывает дату хвостом в обе строки — KNOWN и PARTIAL; `retro`/`report` разбор не сломан (`tests.test_retro` зелёный) |
| 8 | OK | `check_model_tariff_freshness` (потолок `MODEL_TARIFF_MAX_AGE_DAYS=90`) и `check_model_tariff_vs_model_change`; обе провязаны в `doctor/cli.py::all_checks` |
| 9 | OK | все отказы чтения слоёв завёрнуты в `ModelsError` (`models._document:184-196`), включая `FileNotFoundError`/`OSError`/`UnicodeDecodeError` — `role_tariff`/`model_tariff` их ловят, шаг учитывается; проверено тестом с битым каталогом |
| 10 | OK | раздел `docs/stack.md` «Тариф: по нему считаются деньги» несёт и `model_tariffs`, и действия Оператора при смене цен |
| 11 | ОК с оговоркой | новый `tests/test_model_tariffs.py` и правки трёх файлов зелёные; но обещанная PLAN правка `tests/test_report.py` не сделана — новая ветка `report.py` осталась без единого теста (R1-F2) |
| 12 | ОК с оговоркой | `models.yaml` в `PROTECTED_PATHS`, ветка файл не трогает, гейт зон его ловит; но требование инвертирует зафиксированную планку части 1 линии, и это нигде не объявлено (R1-F1) |

## Замечания

- **major — tasks/01M300A14KRHCFB0DQXVCBJEKF/PLAN.md, «Влияние на
  систему» — ветка красит ПЯТЬ зафиксированных планок чужих задач (41
  проверка), а SPEC/PLAN называют одну планку одной задачи.** SPEC «Не
  входит» объявляет единственной жертвой AC-6 задачи
  01M1PP0VYRT55WN8GGVG66X89Y, PLAN не называет ни одной. Прогон каждой
  подозрительной планки на HEAD ветки и на базе `afd4ec66` (одинаковой
  командой, разница — только ветка) даёт:
  - `tasks/01M1PP0VYRT55WN8GGVG66X89Y/acceptance_tests/` — база OK, ветка
    18 ошибок: красна вся планка (AC-1…AC-7), а не один AC-6;
  - `tasks/01M2ZNJX2N5SPZCAQE6EHD4EWH/acceptance_tests/` — база OK, ветка
    12 (AC-1, AC-2, AC-4, AC-5, AC-6, AC-8); в SPEC не упомянута вовсе;
  - `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/` — база 4 отказа,
    ветка 13: девять новых (AC-1 `test_ac1_token_rate_table.py`, AC-2
    `test_ac2_known_rate_partial_charge.py`); в SPEC не упомянута;
  - `tasks/01M1RGQV4DG2FX1B90W4EEETTR/acceptance_tests/test_map_growth_cost_estimate.py:250`
    — база OK, ветка `AttributeError: module 'orchestrator.config' has no
    attribute 'TOKEN_RATES'`; в SPEC не упомянута;
  - `tasks/01M3009Y9AGGY6ZCFA7H1HJ1TD/acceptance_tests/test_ac4_protected_and_doc_commit.py:33`
    — база OK, ветка `AssertionError: 'models.yaml' unexpectedly found`:
    планка части 1 утверждает `assertNotIn("models.yaml",
    config.PROTECTED_PATHS)`, а требование 12 этой задачи её ровно
    переворачивает; в SPEC не упомянута.

  Сценарий последствий: CI гоняет только `tests/`, планки чужих задач он
  не трогает, поэтому после мержа пять залоченных планок останутся
  красными молча — вскроется это на первом же прогоне любой из этих задач
  (например, при возврате в неё на доработку) уже без контекста этой
  ветки. Оператор, читая PLAN, готовится к ОДНОЙ команде `amend-tests`, а
  нужно пять.

  Предложение: код не трогать — правка залоченных планок принадлежит
  Оператору (ADR-0012), а требования 1 и 12 делают их падение
  неизбежным. Внести в PLAN «Влияние на систему» полный перечень выше
  (путь планки, какие AC и почему падают, «база зелёная / ветка красная»)
  и явно назвать это решением, которое принимает Оператор на гейте.

- **major — orchestrator/report.py:696-709 — новая ветка «тариф не
  разрешён» не покрыта ни одним тестом, хотя PLAN её тест обещал.**
  `map_growth_cost_estimate` сменила контракт: `cost_usd` теперь может
  быть `None` (`orchestrator/report.py:261-265`), и печать этого состояния
  словами вместо `_usd(None)` = «$0.00» — новая ветка
  `_map_growth_estimate_html`. Таблица PLAN «Обновляемые ожидания» прямо
  заявляет строку `tests/test_report.py | добавляется ожидание строки
  оценки с нерезолвимым тарифом (новая ветка `_map_growth_estimate_html`)`,
  но `tests/test_report.py` в диффе ветки отсутствует, и поиск по всему
  репозиторию (`grep -rn "тариф модели роли developer не разрешён"
  tests/ tasks/*/acceptance_tests/`) находит только саму реализацию.
  Сценарий последствий: мутация `cost = f"{_usd(estimate['cost_usd'])}"`
  (снять условие) снова печатает «$0.00» на нерезолвимом тарифе — то есть
  «карта бесплатна» вместо «цену не по чему посчитать», ровно то, от чего
  ветка и заведена, — и ни один зелёный прогон этого не заметит; штатная
  сеть этой функции, планка 01M1RGQV4DG2FX1B90W4EEETTR AC-4, одновременно
  красна (R1-F1). Предложение: добавить в `tests/test_report.py` два
  теста — `cost_usd is None` печатается словами и не содержит «$0.00», и
  разрешимый тариф печатается суммой, — с заявкой «Ловит мутацию: …» на
  снятие условия.

- **minor — tests/test_token_rate_divergence.py:100-110
  (`test_old_format_and_cli_default_label_have_no_model`) — докстринг и
  имя теста утверждают не то, что тест проверяет.** Заголовок гласит
  «Строка до 19.09 (поля нет) и метка «дефолт CLI» модели не дают», а
  заявка — «Ловит мутацию: метка «дефолт CLI» читается как идентификатор
  модели»; при этом сам тест ассертит обратное:
  `assertEqual(spend.journal_model("попытка 1/3, model=дефолт CLI:"),
  "дефолт")`. Модель у метки `journal_model` как раз ДАЁТ, отсекает её
  каталог — следующей строкой `assertIsNone(spend.model_tariff("дефолт"))`.
  Сценарий последствий: ревьювер следующей итерации сверяет тест с
  заявкой (skills/review-checklist.md) и читает «ловит мутацию в
  `journal_model`», тогда как защиту здесь даёт `model_tariff`; мутация
  `journal_model`, которую заявка описывает, тестом не ловится — она в
  нём зафиксирована как ожидаемое поведение. Предложение: переписать
  заголовок и заявку под фактическое разделение ответственности («поле
  разбирается всегда, псевдомодель отсекает каталог») либо разнести на
  два теста.

- **minor — orchestrator/doctor/model_tariffs.py:34-53, 70, 146 —
  `_role_tariffs` возвращает второй элемент, который не читает никто, а
  вторая проверка делает всю его работу заново.** `unresolved`
  собирается (строка 49) и отбрасывается обоими вызывающими (`tariffs, _
  = _role_tariffs()`, строки 70 и 146). Сверх того
  `check_model_tariff_vs_model_change` после `_role_tariffs()` (которая
  уже прочитала оба слоя и разрешила все роли) зовёт
  `doctor.models.layers_or_none()` и `resolve_role` по всем ролям во
  второй раз (строки 146, 151, 156). Сценарий последствий: каждый прогон
  `doctor` читает `models.yaml` и `.artel/models.yaml` вчетверо против
  нужного и разрешает цепочку каждой роли трижды; мёртвый элемент
  кортежа при этом выглядит контрактом и переживёт следующую правку.
  Предложение: вернуть из `_role_tariffs` один словарь (или отдать
  вместе с ним прочитанные слои и переиспользовать их во второй
  проверке).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tasks/01M300A14KRHCFB0DQXVCBJEKF/PLAN.md, «Влияние на систему» | ветка красит 5 зафиксированных планок чужих задач (41 проверка: 01M1PP0VYRT55WN8GGVG66X89Y — 18, 01M2ZNJX2N5SPZCAQE6EHD4EWH — 12, 01M1NWCM3TDY0YABEKE8DYQA1C — 9, 01M1RGQV4DG2FX1B90W4EEETTR:250 — 1, 01M3009Y9AGGY6ZCFA7H1HJ1TD/test_ac4_protected_and_doc_commit.py:33 — 1), SPEC называет одну планку, PLAN — ни одной | CI планки не гоняет: после мержа пять залоченных планок красны молча, Оператор готовится к одной команде `amend-tests` вместо пяти | код не трогать (ADR-0012 — право Оператора); внести полный перечень в «Влияние на систему» с пометкой «база зелёная / ветка красная» и вынести решение на гейт Оператора |
| R1-F2 | open | orchestrator/report.py:696-709 | новая ветка «тариф не разрешён» (`cost_usd is None`) без единого теста; обещанная PLAN правка `tests/test_report.py` в диффе отсутствует | снятие условия вернёт «$0.00» вместо «цена не разрешена» — «карта бесплатна» не покраснеет нигде, а штатная планка этой функции (01M1RGQV4DG2FX1B90W4EEETTR AC-4) одновременно красна | добавить в `tests/test_report.py` тесты на обе ветки `_map_growth_estimate_html` с заявкой «Ловит мутацию: …» |
| R1-F3 | open | tests/test_token_rate_divergence.py:100-110 | докстринг/имя теста утверждают, что метка «дефолт CLI» модели не даёт, а ассерт того же теста фиксирует `journal_model(...) == "дефолт"` | заявка «Ловит мутацию» описывает мутацию `journal_model`, которую тест не ловит; защиту даёт `model_tariff` — следующая сверка теста с заявкой введёт в заблуждение | переписать заголовок и заявку под фактическое разделение ответственности либо разнести на два теста |
| R1-F4 | open | orchestrator/doctor/model_tariffs.py:34-53, 70, 146 | второй элемент кортежа `_role_tariffs` не читает никто; `check_model_tariff_vs_model_change` повторно читает слои и заново разрешает все роли | каждый прогон `doctor` читает оба файла слоёв вчетверо и разрешает цепочку роли трижды; мёртвый элемент выглядит контрактом | вернуть один словарь либо отдать вместе с ним прочитанные слои и переиспользовать во второй проверке |

## Вердикт

`changes_requested` — два major (R1-F1, R1-F2) и два minor (R1-F3,
R1-F4).

Сам перевод цены с роли на модель сделан верно и в объявленных зонах:
все двенадцать требований реализованы, планка задачи зелена целиком
(22 теста), затронутые модули `tests/` зелены (654 теста двумя
прогонами), диффа за пределами `zones:` SPEC нет, `models.yaml` ветка не
трогает, существующие ассерты не ослаблены — удалённый
`test_role_missing_one_of_the_four_prices_raises` заменён более строгим
`test_incomplete_price_set_is_a_named_refusal_and_degrades_to_none`
(`assertRaises(models.IncompletePriceError)` вместо
`assertRaises(Exception)`), деградация без тарифа доказана прогоном, а не
чтением. `docs/codebase-map.md` совпадает с перегенерацией по содержимому
(расхождение только в `built_at_sha`, замечанием не является).

Что исправить: R1-F1 — дополнить PLAN полным перечнем падающих планок
чужих задач и вынести решение на Оператора (код планок НЕ править);
R1-F2 — написать обещанные PLAN тесты новой ветки `report.py`; R1-F3,
R1-F4 — по тексту замечаний.

## Проверено исполнением

- `python3 -m unittest tests.test_model_tariffs tests.test_token_rate_divergence
  tests.test_step_cost tests.test_models tests.test_report
  tests.test_protected_paths_gate tests.test_store_schema_migration_parity
  tests.test_doctor tests.test_models_doctor` — 348 тестов, OK.
- `python3 -m unittest tests.test_retro tests.test_agent_log tests.test_pause
  tests.test_invariants tests.test_store_journal tests.test_multitarget
  tests.test_multitarget_invariants tests.test_runner_role_model
  tests.test_runner_model_preflight tests.test_spent_estimate_store
  tests.test_stack tests.test_providers` — 306 тестов, OK (проверял, что
  хвост даты тарифа в строках KNOWN/PARTIAL не сломал разбор `retro` и
  учёт `runner`).
- Планка задачи: `python3 -m unittest discover -s
  tasks/01M300A14KRHCFB0DQXVCBJEKF/acceptance_tests -t
  tasks/01M300A14KRHCFB0DQXVCBJEKF/acceptance_tests` — 22 теста, OK.
  Пометок `# AC-n: manual|skip` в планке нет (`grep`), автогейт acceptance
  не выключен.
- Планки соседних задач, на HEAD ветки и на базе `afd4ec66` (база — во
  временном worktree `git worktree add --detach`, удалён после сверки),
  одной и той же командой `unittest discover`: 01M1PP0VYRT55WN8GGVG66X89Y
  — база OK / ветка 18 ошибок; 01M2ZNJX2N5SPZCAQE6EHD4EWH — база OK /
  ветка 12; 01M1NWCM3TDY0YABEKE8DYQA1C — база 4 / ветка 13;
  01M1RGQV4DG2FX1B90W4EEETTR — база OK / ветка 1 ошибка;
  01M3009Y9AGGY6ZCFA7H1HJ1TD — база 14 / ветка 15; 01M2DTT96FS25SHXP0HDTWARQH
  и 01M1THKPNZ11DBZAQDMJ33EMJR — одинаково красны на базе и на ветке
  (предсуществующие, этой ветке не приписываю); 01M1TQ11K4WJZD7ZE3MR0J4ZK4
  — OK. Это и есть доказательная база R1-F1.
- `python3 scripts/codebase_map.py` с последующим `git diff
  docs/codebase-map.md` — единственная изменённая строка `built_at_sha`,
  содержимое карты совпадает; файл возвращён `git checkout`.
- `grep -rn "TOKEN_RATES" orchestrator/ scripts/ tests/` — единственное
  вхождение `orchestrator/alerts.py:45`, и оно в докстринге (AC-1 разбирает
  ссылки по `ast`, докстринг ссылкой не считает — планка AC-1 зелёная).
- `grep -rn "тариф модели роли developer не разрешён|_map_growth_estimate_html"
  tests/ tasks/*/acceptance_tests/ orchestrator/` — совпадения только в
  `orchestrator/report.py`: тестов новой ветки нет (доказательство R1-F2).
- `python3 -c "from orchestrator import spend; print(spend.role_tariff('developer'))"`
  в рабочем каталоге без `.artel/models.yaml` — `None`, учёт не падает:
  деградация требования 9 подтверждена и вне песочницы.

## Предложения системе

- Ревью-пакет несёт SPEC, PLAN и diff, но не несёт статуса зафиксированных
  планок ДРУГИХ задач — а именно они молча краснеют от задач класса
  «убрать имя из `config`». Здесь класс стоил ручной сверки пяти планок на
  двух ревизиях (и нашёлся только потому, что ревьювер её затеял). Лечится
  строкой в пакете «планки чужих задач, зелёные на базе и красные на
  ветке» — её умеет посчитать тот же скрипт, что собирает пакет.
- `skills/review-checklist.md` требует проверять «правку зафиксированных
  планок» (редактирование), но молчит о том, что планку можно СЛОМАТЬ, не
  прикасаясь к ней. Обе ситуации ведут к одной команде Оператора
  (`amend-tests`, ADR-0012) и обе стоит называть в одном пункте.
