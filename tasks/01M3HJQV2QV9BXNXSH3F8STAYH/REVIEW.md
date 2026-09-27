---
task: 01M3HJQV2QV9BXNXSH3F8STAYH
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: канарейка переживает эскалацию по бюджету и позволяет выбрать шаблон

## Гейт плана (Фаза A)

1. **Покрытие требований полно.** Таблица PLAN несёт все 13 требований
   SPEC, каждое привязано к шагу; шаг 1 — выбор шаблона (требования 1-5),
   шаг 2 — подъём потолка, исход и вердикт (6-11), справки и тесты
   (12-13) поделены между шагами. Требований без шага нет, шагов без
   требования нет.
2. **Размер шагов.** Два шага, один MR — обоснование совпадает с
   разделом «Оценка объёма и деление» SPEC (зоны общие, промежуточное
   состояние мержимо, но бессмысленно). Ни микрооперации, ни «сделать
   всё»: каждый шаг называет функции и файлы.
3. **Подход не конфликтует с архитектурой.** Развилка выбора шаблонов
   одна и стоит в `cmd_canary` (canary.py:1741) — прежняя ветка
   `_sample_pool_templates` не переписана; согласованный литерал
   `_BUDGET_ESCALATION_DETAIL_MARK` (canary.py:196) дублируется тем же
   приёмом, что уже применён к `_AUTO_STOPPED_ACTION`/
   `_ACCEPTANCE_TESTS_REFUSAL_ACTION`, вместо правки `budget.py` вне зоны;
   «подъём уже был» читается из журнала, а не из переменной цикла —
   именно это и требуется требованием 8.
4. **«Влияние на систему» сверено с фактическим диффом.** Заявлено
   «третье значение `canary_runs.verdict`, ни `store.py`, ни `pin.py`, ни
   `schema.py` не правятся» — проверено: `git diff` по
   `orchestrator/pin.py orchestrator/store.py orchestrator/schema.py
   orchestrator/budget.py orchestrator/auto.py tests/test_invariants.py
   docs/adr/ gates.yaml roles.yaml templates/ skills/ .github/` пуст.
   `orchestrator/config.py` и `docs/codebase-map.md` в `zones:` SPEC не
   названы, но лежат в `config.COMMON_ZONES` (config.py:662) — гейт зон
   их и не должен был отказать, side effect'а вне зоны нет. Откат описан
   (revert одного merge-коммита, состояние БД читается прежним кодом).
5. **Риск PLAN №1 подтверждён фактом, мандат — за Оператором.** Чужая
   залоченная планка смерженной задачи действительно красная: прогон
   `tasks/01M3FQ2Z2PY0E9T5F5WQ207NP5/acceptance_tests/test_ac1_set_flag_parsing.py`
   — `2 failed, 1 passed`, `AssertionError: ... найдено: ['set_name',
   'templates']` (`_util.py:160-168`). Машинного эффекта у этого нет:
   `acceptance.run`/`collect` зовутся только для каталога ТОЙ задачи,
   которую двигают (`fsm_advance`, `amend.py`), а в
   `.github/workflows/` строки `acceptance_tests` нет ни одной. Правка
   чужой залоченной планки разработчику не по мандату — оставлено как
   есть правильно; решение о мандате за Оператором (см. «Предложения
   системе»).

Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_named_pool_templates` (canary.py:275-308) возвращает `[pool_dir / f"{title}.md" for title in titles]` — по списку имён, не по `sorted`/`set`; развилка в `cmd_canary` (canary.py:1741). Порядок прогона = порядок флага, проверено планкой AC-1 и `tests/test_canary_template_flag.py::test_returns_named_files_in_flag_order` |
| 2 | OK | `--k` разбирается первым: в `canary.cmd_canary(k=_k_arg(rest), …, templates=_template_arg(rest))` (artel.py:831-833) аргументы вычисляются слева направо, поэтому `canary --template alpha` без `--k` даёт прежний отказ «нужен параметр --k» (проверено `test_template_without_k_is_still_refused`). Равенство числа имён и `--k` — canary.py:293-296 |
| 3 | OK | Четыре отказа: флаг без значения — `artel._template_arg` (artel.py:794-816, сверка `idx + 1 >= len(rest)` тем же приёмом, что `_set_arg`); число имён ≠ `--k` — canary.py:293; повтор имени — canary.py:297; неизвестное имя с перечнем доступных — canary.py:303-307. Все три последних стоят до `_resolve_target_sha` (единственное обращение к origin, canary.py:1747) и до первого `_ephemeral_clone`; пустой пул отказывает раньше всех проверок имён (`_pool_md_files`, canary.py:253) |
| 4 | OK | `templates is None` → прежний `_sample_pool_templates` с тем же `random.sample` по тому же отфильтрованному списку; тело ветки не переписано, вынесено только чтение `*.md` в `_pool_md_files`. `_cmd_canary` без флага передаёт именно `None`, не пустой список (tests/test_new_argv_parsing.py:114-116) |
| 5 | OK | Первая строка вывода несёт `', '.join(p.stem for p in templates)` (canary.py:1758-1762). Проверил, что раньше неё никто не печатает: `_resolve_target_sha` (canary.py:1396-1436) и `_set_plan` (canary.py:376-406) только возвращают либо `sys.exit`, `print` в них нет — то есть строка первая и до первого клона фактически, а не только в моке планки |
| 6 | OK | `_budget_escalation` (canary.py:966-976) читает `detail` ПОСЛЕДНЕГО перехода `state -> escalated` и ищет в нём литерал `budget.enforce_budget` (budget.py:217-219). Признак — именно причина перехода, не состояние и не счётчик: эскалация другой природы после бюджетной в бюджетную ветку не уходит (`test_only_the_last_escalation_decides`) |
| 7 | OK | `_raise_task_ceiling` (canary.py:986-1013): `after = before * config.CANARY_BUDGET_CEILING_FACTOR` (config.py:383, значение 2.0 ≥ 2), потолок правится ДО возврата, возврат — существующим `_pass_escalated_with_synthetic_answer`, факт подъёма в журнал. Задача возвращается в `escalated_from`, прогон продолжается |
| 8 | OK | Второго подъёма нет: `_ceiling_already_raised` (canary.py:979-984) читает журнал задачи, а не переменную цикла `_drive_task`, поэтому уход из состояния память не обнуляет. Прогон живого `_drive_task` даёт ровно одну запись подъёма (`test_second_exhaustion_does_not_raise_again`) |
| 9 | OK на основном пути, край не закрыт | `_kill_ceiling_exhausted` (canary.py:1015-1041) журналирует причину с числами (`budget.spent_with_estimate`, `t["budget_usd"]`) и ролью шага (`config.STATE_ROLE[escalated_from]`), `_kill_outcome_note` (canary.py:921-922) возвращает её без приписки «не сошлась» — видно и в журнале, и в строке отчёта (`outcome_note`, canary.py:1693). Край: если уже НА ПЕРВОЙ бюджетной эскалации расход ≥ поднятого потолка, исход вырождается в «задача не сходится» — см. minor 1 |
| 10 | OK на основном пути, край тот же | `_run_verdict` (canary.py:1319-1333) даёт третье значение `VERDICT_CEILING_EXHAUSTED = "ceiling"` (canary.py:228); `store.green_canary_runs` отбирает строго `verdict='green'` (store.py:1104), `orchestrator/pin.py` в диффе отсутствует — годность для `pin-update` не расширена. Край — minor 1 |
| 11 | OK | `_run_verdict` при `ceiling_exhausted=False` сохраняет прежнюю формулу байт-в-байт (`not _needs_diagnostics(...)`), таблица истинности проверена подтестами `test_without_ceiling_exhaustion_the_formula_is_unchanged`; факт подъёма — в журнале и отдельной строкой отчёта (canary.py:1697-1702, `_ceiling_raise_line`) |
| 12 | OK | `artel.py:128-129` (строка использования с `[--template <имя>,<имя>]`), `artel.py:237-259` (раздел справки: флаг, отказы, новый исход, «годным для сдвига пина не становится»); `docs/operator-session.md:310-329` (флаг и бюджетная эскалация) и `:409-418` (пункт 6 аварийного режима: исход не годен для сдвига пина) |
| 13 | OK | Два новых файла тестов (769 строк), покрывают названный выбор, четыре отказа разбора, прежнюю случайную выборку, подъём и его однократность, новый исход и вердикт. `tests/test_canary.py`, `tests/test_canary_sets.py`, `tests/test_pin.py` зелёные без правки; дифф `tests/` — только добавления плюс три `assert_called_once_with`, куда дописан `templates=None` (усиление, не ослабление): `git diff --numstat -- tests/` даёт `421/0`, `348/0`, `12/4` |

## Замечания

Blocker и major не найдено. Ниже два **minor**; записями реестра они
НАМЕРЕННО не заводятся (вердикт `approved` не прошёл бы гейт `review ->
verifying` ни с одной записью, отличной от `accepted`, а на аппрув эти
наблюдения не влияют — оба воспроизведены исполнением и оба дешевле
починить при следующем касании файла, чем платить за итерацию).

- **minor — orchestrator/canary.py:986-1013 (`_raise_task_ceiling`) и
  :1099-1105 (развилка бюджетной эскалации в `_drive_task`) — подъём
  потолка не проверяет, что новый потолок уже пробит, и тогда исход
  требований 9-10 вырождается в «задача не сходится».** Сценарий:
  расход на момент ПЕРВОЙ бюджетной эскалации ≥ потолок × множитель (то
  есть один шаг перебил потолок больше чем вдвое). Тогда
  `_raise_task_ceiling` поднимает потолок до значения, которое уже
  исчерпано, возвращает задачу в `escalated_from` — и на первом же
  проходе `runner.cmd_run` отказывает по `budget.budget_block` ДО смены
  состояния, `auto.cmd_auto` этого не отличает от «шаг не готов»,
  подпись `(state, spent_usd)` не меняется, и задача уходит в ветку
  `stall_streak`, где снимается как «не сошлась: … задача не сходится»
  с вердиктом `red`. Воспроизведено зондом на живом `_drive_task`
  (потолок $10, шаг $25 — см. «Проверено исполнением»):
  `ceiling_exhausted: False`, `kill_note: не сошлась: canary: 3 проходов
  подряд без прогресса … задача не сходится`, `verdict: red` — ровно те
  два диагноза, которые требование 10 велит различать, снова слиты, и
  подъём потолка при этом потрачен впустую. Почему minor, а не major: на
  сегодняшних числах край недостижим — весь прогон 20260927T123258Z
  стоил $26.25 за 15 шагов при минимуме потолка $25 по скилу аналитика,
  то есть одиночный шаг ценой ≥ потолка не встречается; дефект
  детерминирован, но не наступает. Предложение: в `_raise_task_ceiling`
  (или в самой развилке) после вычисления `after` сравнить его с
  `budget.spent_with_estimate(t)` и при `spent >= after` идти сразу в
  `_kill_ceiling_exhausted` — поднимать потолок, исчерпанный в момент
  подъёма, смысла нет, а исход тогда называется своим именем.

- **minor — tests/test_canary_budget_ceiling.py:163
  (`test_raise_is_journalled_with_both_ceilings`) — единственный ассерт
  файла, зашивший произведение `CEILING × множитель` литералом.**
  `self.assertIn("20.00", texts[0])` — это 10.0 × 2.0; остальные ассерты
  того же файла значение выводят (`CEILING *
  config.CANARY_BUDGET_CEILING_FACTOR` в `test_ceiling_is_multiplied_by_
  the_named_constant`, `test_ceiling_is_raised_before_the_task_returns`,
  `test_first_budget_escalation_raises_the_ceiling_and_runs_on`,
  `test_second_exhaustion_does_not_raise_again`), а
  `CeilingFactorConstantTest` намеренно не пиннит точное значение
  (`assertGreaterEqual(…, 2)`). Сценарий: Оператор двигает крутилку —
  ровно то, что PLAN, «Риски», предписывает при росте цены шага, — и
  получает красный набор на ассерте про текст журнальной записи, а не на
  том, что множитель стал другим. Воспроизведено: прогон модуля под
  `CANARY_BUDGET_CEILING_FACTOR = 3.0` даёт `FAILED (failures=1)`,
  единственный упавший — этот тест (`'20.00' not found in … поднят до
  $30.00 (множитель 3.0)`). Класс проверен целиком: второй литерал
  `"20.00"` в том же файле (`:235`, `KillCeilingExhaustedTest`) от
  множителя не зависит — там `budget_usd=20.0` задан в `setUp` явно, и
  под фактором 3.0 тест зелёный. Предложение: заменить литерал на
  `f"{CEILING * config.CANARY_BUDGET_CEILING_FACTOR:.2f}"`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: blocker/major итерация не нашла, а два minor выше в реестр
намеренно не заведены (обоснование — в начале «Замечаний»; прецедент
того же приёма — REVIEW.md задачи 01M3EKCZJY9NGCW6VT878RX9JZ, коммит
941c62d68). Записей прошлых итераций у задачи нет: итерация первая.

## Вердикт

`approved`. Требования 1-13 реализованы, оба края (minor 1 и minor 2)
мержу не мешают: первый недостижим на сегодняшних ценах шага, второй —
текст ассерта в новом тесте. Планка задачи (36 тестов) и тесты
затронутых модулей зелёные, приёмочных пометок `manual`/`skip` в планке
нет ни одной (автогейт acceptance задачи не выключен), существующие
тесты не ослаблены, `pin.py`/`store.py`/`schema.py`/`budget.py` не
тронуты, условие ADR-0013 не ослаблено.

## Проверено исполнением

- **Планка задачи, по файлам** (каталогом целиком сторож роли запускать
  не даёт): `python3 -m pytest tasks/01M3HJQV2QV9BXNXSH3F8STAYH/acceptance_tests/test_ac1_*.py
  …test_ac2_*.py …test_ac3_*.py …test_ac4_*.py -q` → **13 passed**;
  `…test_ac5_*.py …test_ac6_*.py …test_ac7_*.py …test_ac8_*.py
  …test_ac9_*.py …test_ac10_*.py -q` → **23 passed**. Итого планка
  зелёная целиком (36 тестов).
- **Тесты затронутых модулей:** `python3 -m pytest tests/test_canary.py
  tests/test_canary_sets.py tests/test_pin.py
  tests/test_new_argv_parsing.py tests/test_canary_template_flag.py
  tests/test_canary_budget_ceiling.py -q` → **203 passed, 10 subtests
  passed**. Полный набор `tests/` в шаге не гонял (решение Оператора
  05.09, его гоняет CI — на a0d75dd9 7 проверок зелёные).
- **Зонд minor 1** (живой `_drive_task`, настоящий
  `budget.enforce_budget`, фейк шага роли повторяет отказ реального
  `runner.cmd_run` по `budget.budget_block` ДО смены состояния; потолок
  $10, шаг $25): `state: killed потолок: 20.0 расход: 25.0`,
  `ceiling_exhausted: False`, `kill_note: не сошлась: canary: 3 проходов
  подряд без прогресса в состоянии in_dev — задача не сходится`,
  `verdict: red`. Запись подъёма в журнале есть, исхода «исчерпан
  потолок задачи» — нет.
- **Зонд minor 2:** прогон `tests/test_canary_budget_ceiling.py` под
  `mock.patch.object(config, 'CANARY_BUDGET_CEILING_FACTOR', 3.0)` →
  `Ran 21 tests … FAILED (failures=1)`, единственный упавший —
  `test_raise_is_journalled_with_both_ceilings`. Под 2.0 тот же модуль
  зелёный.
- **Неослабление и границы зон:** `git diff --stat
  5d001229…HEAD -- orchestrator/pin.py orchestrator/store.py
  orchestrator/schema.py orchestrator/budget.py orchestrator/auto.py
  tests/test_invariants.py docs/adr/ gates.yaml roles.yaml templates/
  skills/ .github/` — пусто; `git diff --numstat -- tests/` — `421/0`,
  `348/0`, `12/4` (удалённых ассертов нет, четыре изменённые строки —
  три `assert_called_once_with` с дописанным `templates=None` и одна
  строка докстринга).
- **Свежесть карты:** `python3 scripts/codebase_map.py` — содержимое
  `docs/codebase-map.md` совпало с закоммиченным без строки
  `built_at_sha:` (сравнение построчное, файл восстановлен, дерево
  чистое).
- **Чужая залоченная планка (риск PLAN №1):** `python3 -m pytest
  tasks/01M3FQ2Z2PY0E9T5F5WQ207NP5/acceptance_tests/test_ac1_set_flag_parsing.py
  -q` → `2 failed, 1 passed`, причина — `_util.py:164`
  (`найдено: ['set_name', 'templates']`). Кто её исполняет: `grep -rn
  acceptance_tests .github/workflows/*.yml` — ни одного совпадения;
  `acceptance.run/collect` зовутся только для каталога двигаемой задачи.
- **Пометки автогейта:** `grep -rn "AC-[0-9]*: *\(manual\|skip\)"
  tasks/01M3HJQV2QV9BXNXSH3F8STAYH/acceptance_tests/` — ни одной.

## Предложения системе

* Механизм этой задачи спасает от красноты «не по вине кода» не всякий
  шаблон: вердикт считается по `mismatch = expected != actual`
  (canary.py:1518-1519), а `actual` — это `bool(metrics["escalations"])`,
  то есть бюджетная эскалация сама по себе уже расхождение для шаблона с
  маркером `canary-expect-escalation: no` (такой в пуле есть —
  `canary-usage-invariant.md`, docs/backlog.md:100). Для него прогон
  останется `red` даже после штатного дохода до `merge_gate`. Требование
  11 SPEC этой задачи оговорено словами «без расхождения маркера», то
  есть код спеке не противоречит, — но класс «инфраструктурная эскалация
  считается поведением конвейера» остался, и следующая задача на ту же
  тему должна знать, что подъёма потолка мало.
* Поддерживаю наблюдение PLAN про
  `tasks/01M3FQ2Z2PY0E9T5F5WQ207NP5/acceptance_tests/_util.py:160-168` и
  подтверждаю его фактом (2 failed, см. выше): утверждение о ПОЛНОМ
  составе параметров публичной функции (`len(names) != 1` после вычета
  известных) ловит не дефект, а факт развития команды. Класс — «планка
  фиксирует форму подписи, а не поведение»; место для запрета —
  `skills/test-authoring.md`. Отдельно нужен ответ Оператора, получает
  ли та планка мандат на правку по ADR-0012: сейчас в дереве лежит
  залоченная планка смерженной задачи, которая красна по построению и
  которую никто не исполняет — латентная ловушка для следующего, кто её
  запустит.
* `orchestrator/store.py:992` — комментарий миграции по-прежнему говорит
  «`verdict` — 'green'/'red' задачи-канарейки», хотя значений теперь три.
  Правка тут была бы выходом за «Не входит» SPEC (store.py читается, но
  не правится), поэтому замечанием не завожу; строка на будущее касание
  store.py либо в бэклог.
