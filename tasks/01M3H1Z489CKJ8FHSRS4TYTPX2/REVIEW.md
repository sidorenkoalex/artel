---
task: 01M3H1Z489CKJ8FHSRS4TYTPX2
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Предварительные зоны и предупреждение о пересечении для подзадач деления

## Фаза A: гейт плана

- **Покрытие требований полно.** Таблица PLAN несёт все пять требований
  SPEC, каждое — на шаг 1. Требования без строки не осталось.
- **Размер шага.** Один шаг = один MR: два добавленных вызова в
  `spawn_subtask`, предложение в `docs/stack.md`, новый тестовый класс,
  регенерация карты. Фактический дифф (4 файла, +237/-8) совпадает с
  прогнозом SPEC (8 КиБ) — не микрооперация и не «сделать всё».
- **Подход не конфликтует с архитектурой.** Новых механик нет:
  подключение к существующим `_record_preliminary_zones` (
  `orchestrator/catalog.py:303`) и `_warn_zone_overlap` (
  `orchestrator/catalog.py:344`) в том же порядке, в каком их зовёт
  `cmd_new` (`orchestrator/catalog.py:480-487`). Свой разбор «Зоны:» не
  заводится — сверено с телом `cmd_new`, порядок «зоны → печать →
  предупреждение» идентичен.
- **Обоснование размещения (требование 3, AC-4) на месте** и
  проверяемо: PLAN, «Подход», части (а)/(б)/(в) — почему не сливать с
  `store.update_task(parent_task_id=…)`, почему порядок между привязкой и
  зонами безразличен, и почему граница `return` и есть та граница, за
  которой заводится следующая часть (`fsm._spawn_division_subtasks`,
  `orchestrator/fsm.py:707-711` — список подзадач одним comprehension).
  Утверждение проверено по коду: вызыватель действительно заводит части
  по одной, и родитель уходит в `killed` только после всего списка
  (`orchestrator/fsm.py:713`), поэтому его `spec_gate` попадает в
  `zone_lock.LATER_STATES` во время каждого заведения — вторая половина
  AC-3 достаётся без нового кода, как и заявлено.
- **«Влияние на систему» соответствует диффу.** Заявлены
  `orchestrator/catalog.py`, `docs/stack.md`,
  `tests/test_catalog_spawn_subtask.py` и регенерация карты — ровно это и
  изменено (`git diff --stat d910c523 HEAD`). `orchestrator/fsm.py`,
  `zone_lock.py`, `store.py`, `scripts/guard.py`, `gates.yaml`,
  `roles.yaml`, `.github/`, `templates/`, `skills/` не тронуты. Перечень
  читателей колонки `zones` в PLAN сверен грепом (`task_zone_paths`,
  `zones=`): `zone_lock.forecast_overlaps`, `zone_lock.blocking_conflict`
  (`orchestrator/zone_lock.py:406,418`), `catalog._zone_forecast_suffix`
  (`orchestrator/catalog.py:686`), `checkpoint._zone_paths` — полон,
  забытого читателя нет.
- **Откат описан** (revert одного merge-коммита, схем и миграций нет) —
  соответствует характеру правки.

Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (зоны «Зоны:» подзадачи общей механикой; пустая/отсутствующая строка колонку не трогает) | OK | `orchestrator/catalog.py:575` — `_record_preliminary_zones(conn, task_id, tz_raw)`, та же общая функция, что у `cmd_new`. Пустой перечень колонку не трогает ранним `return` (`catalog.py:326-328`), `NULL` сохраняется. |
| 2 (предупреждение о пересечении: вывод + журнал, не отказ) | OK | `orchestrator/catalog.py:579` — `_warn_zone_overlap(conn, task_id, tz_raw, target)`. `sys.exit` в функции нет (сверено по телу `catalog.py:344-388`): печать + `store.journal`. Заведение возвращает `task_id` как прежде. |
| 3 (порядок: ранее заведённая подзадача видна следующей; обоснование в плане) | OK | Оба вызова стоят после `_new_task_row`/привязки к родителю и до `return` (`catalog.py:571-580`); `spawn_subtask` отдельным вызовом на часть, следующая часть читает БД уже с зонами предыдущей. Обоснование — PLAN «Подход» и докстринг `catalog.py:530-551`. Проверено прогоном: AC-3. |
| 4 (документация о заведении и прогнозе очереди зон) | OK | `docs/stack.md:675-681` — предложение о подзадачах деления в том же пункте «Зоны ТЗ пишутся в `tasks.zones` сразу при заведении», внутри раздела о прогнозе очереди зон. |
| 5 (тесты покрывают, существующие не ослаблены) | OK | `tests/test_catalog_spawn_subtask.py` — `SubtaskZonesTest` (3 теста) и `SubtaskZoneOverlapTest` (4 теста). Дифф этого файла чисто аддитивный: изменены только модульный докстринг и блок импортов, ни один существующий `assert`/метод не тронут и не удалён; `tests/test_catalog_zone_overlap.py` и `tests/test_zone_lock_forecast.py` не правятся вовсе. |

### Проверка корректности (сценарии поломки, которые я искал и не нашёл)

- **Ссылка на родителя ломает разбор «Зоны:».** `_tz_section_re`
  заякорена на начало строки (`re.M`, `catalog.py:151-154`), `link_line`
  кончается `\n` (`catalog.py:567-569`) — «Зоны:» остаётся началом
  строки. Путь, названный в НАЗВАНИИ родителя, в колонку не затекает:
  берётся тело раздела, не весь текст. Проверено тестом
  `test_the_parent_link_line_does_not_leak_into_the_zones_column` и
  приёмочным AC-1.
- **Расхождение `TZ.md` и разобранного текста.** Устранено конструктивно:
  один `tz_raw` идёт и в `_tz_document`, и в обе новые функции
  (`catalog.py:569-570`).
- **Строгость входа в `in_dev` не выросла.** `blocking_conflict`
  (`zone_lock.py:406,418`) требует от держателя ещё и `_occupies` —
  подзадача в `spec_writing`/`spec_gate` держателем зоны от одной записи
  в колонку не становится. Прогнал `tests.test_zone_lock`,
  `tests.test_zones_gate` — зелено.
- **`NULL` против пустой строки.** Различие сохранено (ранний `return`),
  фильтр WIP-чекпоинта не начинает считать посторонним каждый путь
  подзадачи без «Зоны:». Прогнал `tests.test_checkpoint_zone_filter` —
  зелено.
- **Чужой target.** Фильтр достаётся от `_warn_zone_overlap`
  (`catalog.py:377-378`), `target` подзадачи передан четвёртым
  аргументом. Тест `test_a_part_of_a_foreign_target_gets_no_warning`
  несёт якорь-контроль (то же заведение на основном target'е
  предупреждение даёт) — на сверке, сломанной целиком, он не зеленеет.
- **Незакрытая транзакция между вызовами `spawn_subtask`.** Каждый вызов
  берёт свой `store.db()`; видимость зон первой части второй фактически
  наблюдается (AC-3 зелёный), а не только выводится из кода.
- **Зона деления вне зон родителя.** Не новый риск: `Зоны:` подраздела
  обязательны и проверяются на покрытие зонами родителя ещё на гейте
  SPEC (`scripts/guard.py:2082-2112`), так что защищённый путь в колонку
  подзадачи этим путём не приходит.

### Системная целостность

- Ни один существующий тест, гейт, лимит или guard-проверка не ослаблены
  и не удалены: дифф `tests/` аддитивен, `orchestrator/fsm.py`,
  `zone_lock.py`, `store.py`, `scripts/guard.py` не тронуты.
- Приёмочная планка не правилась разработчиком:
  `git log --all -- tasks/01M3H1Z489CKJ8FHSRS4TYTPX2/acceptance_tests`
  отдаёт один коммит — 2132c9d0 (автокоммит шага test_author). Пометок
  `# AC-n: manual|skip` в планке нет вовсе (греп пуст) — автогейт
  acceptance задачи не выключен.
- Файлов вне зоны задачи нет: изменены `orchestrator/catalog.py`,
  `docs/stack.md`, `tests/test_catalog_spawn_subtask.py` и
  сгенерированная `docs/codebase-map.md` (общая зона). `.github/`,
  `gates.yaml`, `roles.yaml`, `templates/`, `skills/` не затронуты.
- Секретов, инъекций и недоверенного ввода правка не добавляет: новые
  данные — то же тело подраздела SPEC родителя, которое уже уходит в
  `TZ.md`.
- Карта кодовой базы свежа по содержимому: после `python3
  scripts/codebase_map.py` дифф `docs/codebase-map.md` — только строка
  `built_at_sha` (1 строка), то есть расхождения содержания нет.

### Тесты: сверка с заявками «Ловит мутацию»

Прошёл по всем семи новым тестам, сверяя докстринг с телом, а не с
именем метода. Заявки правдоподобны и выполняются:

- `test_zones_line_of_the_subsection_lands_in_the_task_row` — мутация
  «не зовёт `_record_preliminary_zones` / пишет зоны родителю» валит
  `assertEqual(..., zones_of(sub_id))`; мутация «молча, без журнала» —
  проверку `details(sub_id, PRELIMINARY_ZONES_ACTION)`.
- `test_a_subsection_without_zones_leaves_the_column_null` — безусловная
  запись валит `assertIsNone`, оба подслучая (нет строки / пустая строка)
  разведены `subTest`.
- `test_the_next_part_of_the_division_is_warned_about_the_previous` —
  вынос записи зон в конец волны деления оставляет колонку первой части
  пустой, вывод и журнал второй молчат: валятся обе проверки.
- `test_overlap_with_the_still_living_parent_is_reported` — исключение
  родителя из сверки валит `overlap_lines`/журнал.
- `test_a_part_of_a_foreign_target_gets_no_warning` — вызов без
  четвёртого аргумента даёт предупреждение там, где тест ждёт пустоту;
  якорь на основном target'е закрывает вырождение «сверка сломана
  целиком».
- `test_the_warning_does_not_turn_the_spawn_into_a_refusal` — `sys.exit`
  поднимет `SystemExit` в теле теста; слияние записи зон с привязкой
  валит `assertEqual(PARENT_ID, row["parent_task_id"])`.
- `test_the_parent_link_line_does_not_leak_into_the_zones_column` —
  вторая половина заявки (разбор всего документа вместо раздела «Зоны:»)
  ловится: путь `docs/operator-session.md` из названия родителя в колонку
  не попадает. Первая половина заявки («на разбор подан `tz_body` без
  ссылки») тестом не наблюдается, но и наблюдаться не может: такая
  подмена зоны не меняет — сценария поломки за ней нет, поэтому в
  замечание не оформляю; докстринг сам это оговаривает скобкой «сценарий
  … не наблюдается вовсе».

## Замечания

Blocker/major/minor — нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний итерации 1 нет, незакрытых записей прошлых
итераций у задачи не было (это первая итерация ревью).

## Вердикт

approved.

## Проверено исполнением

Полный набор `tests/` в шаге не гонял (решение Оператора 05.09, его
гоняет CI на пуш; CI коммита 2c81d8b6 зелёный, 14 проверок). Гонял планку
и затронутые модули, всё в переднем плане:

- `python3 -m pytest tasks/01M3H1Z489CKJ8FHSRS4TYTPX2/acceptance_tests
  -p no:cacheprovider -q` — **13 passed** за 3.26с. Планка задачи
  (AC-1…AC-5) зелёная целиком.
- `python3 -m unittest tests.test_catalog_spawn_subtask
  tests.test_catalog_zone_overlap tests.test_zone_lock_forecast
  tests.test_division_parent_cleanup -v` — **Ran 47 tests, OK** (13.3с).
  Отдельно смотрел, что `test_division_parent_cleanup` (деление
  насквозь) не покраснел от нового предупреждения — прогноз PLAN
  подтвердился.
- `python3 -m unittest tests.test_stack_zones_pull_section
  tests.test_catalog_tz_zones_parsing tests.test_checkpoint_zone_filter
  tests.test_zones_approve tests.test_zones_gate tests.test_zone_lock
  tests.test_invariants` — **Ran 152 tests, OK** (126.9с). Покрыты
  читатели колонки `zones` из «Влияния на систему» PLAN и раздел
  `docs/stack.md`, который правка трогает.
- `python3 -m unittest tests.test_multitarget` (в связке) — **Ran 52
  tests**, единственная ошибка прогона — мой опечатанный несуществующий
  модуль `tests.test_checkpoint`; сам `SqlOnlyInStoreTest` зелёный, то
  есть инвариант «SQL только в store.py», который красил CI итерации
  разработчика (4b829f37), закрыт правкой 2c81d8b6.
- `python3 scripts/guard.py --all` — **GUARD: ок (1061 файлов)**, два
  предупреждения по чужим задачам (`01M1RA0R9AH9RBAHD4A2Z5SEWQ`, `T067`),
  к этой ветке отношения не имеют.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  — расхождение только в строке `built_at_sha` (1 строка), содержание
  карты свежо.
- `git log --oneline --all -- tasks/01M3H1Z489CKJ8FHSRS4TYTPX2/
  acceptance_tests` — один коммит 2132c9d0 (шаг test_author): планка
  разработчиком не правилась.
- `grep -rn "AC-[0-9]*: manual\|AC-[0-9]*: skip" tasks/01M3H1Z489CKJ8FHS
  RS4TYTPX2/acceptance_tests/` — пусто: автогейт acceptance не выключен.
- `git diff --stat d910c523 HEAD` — 4 файла, все в зонах SPEC (+ общая
  зона `docs/codebase-map.md`); `git status --porcelain` — чисто, кроме
  неотслеживаемых артефактов задачи.

## Предложения системе

- Минорное замечание нельзя записать, не заблокировав аппрув:
  `_registry_gate` (`orchestrator/advance_gates/tests_writing.py:51`)
  отклоняет `approved` при ЛЮБОЙ записи реестра не в `accepted`, а
  `skills/review-checklist.md` велит оформлять записью каждое замечание
  из «Замечаний» и одновременно аппрувить при 0 blocker/major. Ревьювер
  с единственным minor вынужден выбирать между «умолчать» и
  «changes_requested из-за вкусовщины» — просится либо severity в
  реестре (гейт смотрит только blocker/major), либо терминальный статус
  вроде `noted` для minor, который гейт пропускает.
- Заявка «Ловит мутацию» не различает мутацию, меняющую поведение, и
  поведенчески-нейтральную подмену (`tz_body` вместо `tz_raw` в
  `tests/test_catalog_spawn_subtask.py:120`): вторую не поймает никакой
  тест, и обе стороны — автор теста и ревьювер — тратят проход на спор о
  невыполнимой заявке. `skills/test-authoring.md` стоило бы прямо
  сказать, что заявка обязана называть НАБЛЮДАЕМОЕ расхождение, а
  нейтральный рефакторинг в неё не пишется.
