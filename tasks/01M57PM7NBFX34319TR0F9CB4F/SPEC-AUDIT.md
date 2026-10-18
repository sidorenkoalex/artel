---
task: 01M57PM7NBFX34319TR0F9CB4F
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py, tests/test_doctor.py, tests/test_main_ci_line.py, tests/test_merge_gate_ci_wait.py, tests/test_merge_lock.py, tests/test_merge_queue.py, tests/test_notes.py; в) пути-признаки (гейты): orchestrator/fsm_merge_gate.py; г) budget_usd 45 ≥ 45."
spec_sha: 5d980ac20efe1109fc4f2dfd2bdc718d7b8971e4
schema_version: 5
---

# SPEC-AUDIT: Несколько проектов: мьютекс и очередь мержа по проекту

## ТЗ и SPEC
- Требования 1, 3–5 ТЗ → требования SPEC 1–6, 12; критерии приёмки ТЗ →
  AC-1…AC-10, AC-16. Отражены.
- ANSWER-1: 1-A (store.py) → треб. 7, AC-11; 2-A (notes.py) → треб. 9,
  AC-13; 3-B заменён решением О-3 (подтверждено решением визита 2, п.1) →
  треб. 10, AC-14; бюджет $45 и монолит → frontmatter и «Оценка объёма».
- Решения гейта №1: О-1 → треб. 11, AC-15; О-2 → треб. 8, AC-12; О-3 →
  зоны, треб. 10, строка матрицы doctor; О-4 → треб. 3, AC-7; О-5 → треб. 3
  (`:1474`). Решения визита 2: п.2 → треб. 3 и AC-17; п.3 → AC-7 (а)/(б);
  п.4 → треб. 13, AC-16; п.5 → `tests/test_doctor.py` в треб. 11 и AC-15;
  п.6 → треб. 3 (`:631` — `_await_main_ci`). Всё отражено.
- **Отклонение 1 (требование 2 ТЗ).** ТЗ просит сверить, что разделяют
  мержи разных проектов кроме мьютекса. Сверка в SPEC (SPEC.md:20-28 и
  SPEC.md:270-272) заканчивается выводом «общий ресурс — только БД
  пульта» (SPEC.md:28). Общий замок полных прогонов машины `suite_lock`
  она не называет (`orchestrator/suite_lock.py:1-9`: «одновременно идёт не
  больше одного полного прогона», один на все проекты). Гейт мержа гоняет
  полный набор внутри окна мьютекса: `_full_suite_or_refuse`
  (`orchestrator/fsm_merge_gate.py:951-982`) → `acceptance.full_suite` →
  `run_full_suite`. Тот ждёт замок через `suite_lock.wait_acquire`
  (`orchestrator/acceptance.py:1568-1581`) до
  `config.FULL_SUITE_LOCK_WAIT_SEC = 1800` (`orchestrator/config.py:238`).
  После задачи мерж sled по-прежнему может до 30 минут ждать прогона
  гейта мержа артели, и наоборот. Критерий ТЗ «задачи разных проектов
  мержатся без ожидания друг друга» выполнен только для мьютекса и
  очереди. Скорее всего, замок общий намеренно: это нагрузка машины, а не
  исключение мержа. Тогда это надо записать в «Не входит» с решением
  Оператора. `orchestrator/suite_lock.py` вне зон: по ТЗ правка вне зон —
  эскалация до SPEC.
- Требований SPEC без опоры в ТЗ, ANSWER-1 или решениях гейта не найдено.

## Факты против кода
Подтверждено:
- `store.task_target` — `orchestrator/store.py:701-707` (нет строки или
  пустой target → `config.DEFAULT_TARGET`).
- `store.merge_lock_row` — `orchestrator/store.py:1232-1235`, `fetchone()`
  без `ORDER BY`. `store.set_merge_lock` — `:1249`, `DELETE FROM
  merge_locks` без `WHERE`. `release_merge_lock` — `:1264` по (session_id,
  pid).
- `merge_lock.acquire` — `orchestrator/merge_lock.py:56-92` под `BEGIN
  IMMEDIATE`, текст отказа `:76-79`, журнал «мьютекс merge перехвачен» —
  `:87-88`. `touch_heartbeat(conn)` — `:95-122`, продлевает строку
  `merge_lock_row` без сверки.
- `merge_queue._head_task_id` — `orchestrator/merge_queue.py:41-45`
  (глобальный FIFO). `_current_holder_id`/`_current_holder_label` —
  `:48-68`. `queue_wait_minutes` — `:71-81`, ищет по записи самой задачи.
  `wait_suffix` — `:84-94`. `wait_for_window` — `:97-146`, журнал «ждёт
  merge-окна: держит …» — `:123-128`.
- `notes._silence_window_reason` — `orchestrator/notes.py:266-304`, одна
  строка `:281`.
- `doctor check_merge_lock` — `orchestrator/doctor/leases.py:162-194`, одна
  строка `:174`. Автоподтверждение — `orchestrator/doctor/lease_alerts.py:36-49`,
  сверка с одной строкой `:44-48`.
- `fsm_merge_gate`: `touch_heartbeat` вызывается в `:355`
  (`_wait_for_branch_ci_green`, `:324`), `:631` (`_await_main_ci`, `:613`)
  и `:1474` (повтор после «moved»). `acquire` и затем `wait_for_window` —
  `:1456-1458`.
- `tests/test_merge_gate_ci_wait.py:91` зовёт `_wait_for_branch_ci_green`
  прежней формой. `tests/test_main_ci_line.py:318` мокает
  `touch_heartbeat`. `tests/test_merge_queue.py:77-160,210` зовёт
  помощники с одним `conn`.
- `tests/test_doctor.py:1362-1477`: T001/T002 оба заведены с
  `config.DEFAULT_TARGET` (`tests/test_doctor.py:1052-1057`), поэтому
  `test_holder_changed_is_auto_acked_on_next_run` (`:1439-1451`) при
  нормализации треб. 13 остаётся совместимым: замена строки внутри одного
  проекта.
- `schema.py`: таблицы без ключа, несколько строк допустимы.

Уточнения без отклонения:
- В `_cmd_approve_merge_gate_cycle` (`orchestrator/fsm_merge_gate.py:1394`)
  `sid` у `:1474` уже есть в области видимости. Значение
  `session.resolve_session_id()` без аргумента совпадает с ним в боевом
  пути: `lease.run_locked` → `resolve_session_id(session_id)`,
  `orchestrator/lease.py:363`; CLI не передаёт `session_id` в
  `cmd_approve`. При явном `session_id` (тестовый шов
  `cmd_approve(session_id=…)`, `orchestrator/fsm.py:885-886`) значения
  разойдутся.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `acquire` читает одну строку на пульт (`merge_lock_row`) — отказ задаче другого проекта; `set_merge_lock` стирает всю таблицу — строка внешнего держателя исчезнет |
| AC-2 | да | `wait_for_window` ждёт любой живой строки мьютекса — не вернётся на первой итерации |
| AC-3 | да | сверка держателя без проекта у задачи того же проекта ведёт к взятию; текст отказа изменён |
| AC-4 | да | перехват мёртвого держателя чужого проекта или запись журнала убрана |
| AC-5 | да | `release` по одному session_id или по проекту |
| AC-6 | да | `touch_heartbeat` продлевает все строки или первую попавшуюся |
| AC-7 | да | сверка «своей» строки только по проекту либо без session_id — строка нового держателя продлится |
| AC-8 | частично | ловит голову через помощник. **Отклонение 3:** не ловит `wait_for_window`, оставленный на однопараметровом `_head_task_id(conn)`, который треб. 8 обязывает давать прежний, то есть глобальный, FIFO |
| AC-9 | да | пруна убрана или идёт после определения головы |
| AC-10 | частично | ловит текст по чужому держателю, если тест вставил его первым. **Отклонение 4:** нет «в любом порядке вставки» |
| AC-11 | да | `DELETE` без `WHERE` в `set_merge_lock`; смена сигнатуры прежних функций |
| AC-12 | да | однопараметровый вызов помощника падает (проект обязателен) или меняет исход |
| AC-13 | да | `notes` смотрит одну строку — при первой строке внешнего держателя окно не откроется |
| AC-14 | да | `check_merge_lock` по одной строке; автоподтверждение по любой живой строке закроет инцидент |
| AC-15 | да | правка любого из семи файлов тестов |
| AC-16 | да | проект берётся как сырой `tasks.target` (пустой/`NULL` ≠ `artel`) или нет строки → «нет проекта» вместо `DEFAULT_TARGET` |
| AC-17 | да | прежняя форма `touch_heartbeat(conn)` перестала продлевать строку или падает без неё |

- **Отклонение 2.** Требование 3 обязывает три вызова в
  `fsm_merge_gate.py` (`:355`, `:631`, `:1474`) передавать `task_id` и
  сессию. Ни один AC этого не проверяет: AC-6, AC-7 и AC-17 бьют только
  по `merge_lock.touch_heartbeat` напрямую. `tests/test_main_ci_line.py:318`
  мокает функцию, `tests/test_merge_gate_ci_wait.py:91` идёт без строки
  мьютекса. Мутация, которую ничто не ловит: вызов оставлен прежней формы
  `touch_heartbeat(conn)`. Требование 3 разрешает эту форму
  (SPEC.md:67-68) и не определяет её исход при двух строках: «как сейчас»
  значит строку `merge_lock_row` без порядка (`orchestrator/store.py:1235`),
  то есть возможно строку другого проекта. Тогда heartbeat своего
  держателя не продлевается, а чужой мёртвый держатель на чужом host
  «оживает». Последствие смягчает `config.LEASE_STALE_AFTER_SEC = 7200`
  (`orchestrator/config.py:385`): это больше потолка ожидания CI
  `MERGE_GATE_CI_WAIT_CEILING_SEC = 3600` (`orchestrator/config.py:179`)
  плюс `MAIN_CI_WAIT_LIMIT_SEC` 18 мин (`orchestrator/fsm_merge_gate.py:46`).
  Поэтому серьёзность низкая. Но свойство строки матрицы `touch_heartbeat`
  проверкой вызывающих не покрыто.

## Зоны
- Зоны SPEC: ТЗ плюс `store.py`, `notes.py` (ANSWER-1, 1-A/2-A) и
  `doctor/leases.py`, `doctor/lease_alerts.py` (решение О-3, подтверждено
  решением визита 2, п.1). Мандат на зоны doctor задан решением гейта
  SPEC.
- `orchestrator/schema.py`, `catalog.py`, `pin.py`, `targets.yaml`,
  `docs/backlog.md` не нужны: проект строки берётся через `tasks.target`;
  `catalog.py:955` зовёт `merge_queue.wait_suffix(conn, r)` с неизменной
  сигнатурой. `orchestrator/config.py` и `docs/codebase-map.md` входят в
  `config.COMMON_ZONES` (`orchestrator/config.py:803`).
- Защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`,
  `.github/`) задача не трогает. Песочница ролей не расширяется.
- Наблюдение без отклонения: `doctor/leases.py` зовёт помощники через
  фасад `doctor.<имя>` (`orchestrator/doctor/leases.py:193`). Фасад
  реэкспортирует их в `orchestrator/doctor/__init__.py:161-166`, а этот
  файл вне зон. Требование 10 выполнимо без него, если менять сигнатуру
  существующего `_merge_lock_alert_live` и не заводить новое имя в
  `lease_alerts.py`. Новое имя потребует расширения зон.
- Связанная с отклонением 1 зона: если Оператор решит разделять и
  `suite_lock`, `orchestrator/suite_lock.py`/`acceptance.py` вне зон.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `store.set_merge_lock`/`merge_lock_row` по проекту | взаимное исключение мержа — `orchestrator/merge_lock.py:56-92`, `orchestrator/store.py:1249` | внутри проекта да; между проектами снимается по ТЗ | `tests/test_merge_lock.py` без изменений + AC-1, AC-3, AC-4, AC-11, AC-16 | строка SPEC верна |
| `notes._silence_window_reason` по всем строкам | окно тишины — `orchestrator/notes.py:281-294` | да | `tests/test_notes.py`, `tests/test_01m563947r…py` без изменений + AC-13 | строка SPEC верна |
| doctor `check_merge_lock`/автоподтверждение | видимость мёртвого держателя и незакрытие его инцидента — `orchestrator/doctor/leases.py:162-194`, `lease_alerts.py:36-49` | да | `tests/test_doctor.py:1362-1477` без изменений + AC-14 | строка SPEC верна |
| FIFO очереди по проекту | FIFO по пульту — `orchestrator/merge_queue.py:41-45`, `:134` | внутри проекта да | `tests/test_merge_queue.py` без изменений + AC-8, AC-9, AC-12; путь `wait_for_window` (`:134`) при чужих записях очереди не покрыт (отклонение 3) | строка SPEC переоценивает покрытие |
| `touch_heartbeat` только своей строки | продление heartbeat держателя во время ожидания CI — `orchestrator/merge_lock.py:95-122`, вызовы `orchestrator/fsm_merge_gate.py:355,631,1474` | да, если вызывающие передают задачу и сессию | AC-6, AC-7, AC-17 — функция; вызывающие — не покрыто (отклонение 2) | строка SPEC переоценивает покрытие |
| нормализация проекта (треб. 13) | исключение между всеми задачами артели — `orchestrator/merge_lock.py:56-92` | да | AC-16 | строка SPEC верна |
| — (не трогается) | один полный прогон на машину — `orchestrator/suite_lock.py:1-9`, `orchestrator/acceptance.py:1568-1581` | остаётся общим между проектами | в SPEC не названо (отклонение 1) | решение Оператора |

Раздела «Меняемое поведение» в SPEC нет. Треб. 11 запрещает менять семь
файлов тестов, смены утверждений не требуется — согласовано.

## Пути обхода гейтов
- П-1 (= отклонение 3). Все AC зелёные при `wait_for_window`, который
  зовёт `_head_task_id(conn)` без проекта, то есть прежний глобальный FIFO.
  Для этого достаточно двух условий. AC-8 проверяется через помощник с
  проектом. AC-2 ставит только держателя другого проекта, без его записей
  очереди. Тогда в бою задача sled, вставшая в очередь своего проекта за
  записью артели, ждёт мержа артели. Это прямо нарушает треб. 4 и критерий
  ТЗ.
- П-2 (= отклонение 4). Тексты AC-10 можно строить на однопараметровых
  `_current_holder_label(conn)`/`_current_holder_id(conn)` (первая строка
  таблицы). Тест пройдёт при порядке вставки «сначала держатель своего
  проекта».
- П-3 (= отклонение 2). Вызовы в `fsm_merge_gate.py` оставлены прежней
  формой `touch_heartbeat(conn)`: SPEC её допускает, тесты молчат.
- П-4. Тест требования 12 (детерминизм без сети) с мокнутым полным прогоном не
  увидит ожидание `suite_lock` между проектами (отклонение 1). Критерий
  «ни одна не ждёт другую» формально выполнен, но в бою ожидание остаётся.

## Вердикт
`concerns`. SPEC можно вести дальше: все решения ANSWER-1 и обоих
возвратов гейта отражены, факты о коде подтверждены. Решить отклонения
может Оператор на гейте: принять, вписать в SPEC при следующем возврате
или снять своим решением.

1. Сверка треб. 2 ТЗ не называет машинный замок полных прогонов
   `suite_lock`, общий для мержей всех проектов (SPEC.md:28, SPEC.md:270-272
   против `orchestrator/suite_lock.py:1-9`,
   `orchestrator/fsm_merge_gate.py:951-982`,
   `orchestrator/acceptance.py:1568-1581`, `orchestrator/config.py:238`).
   Нужно решение Оператора: замок остаётся общим (строка «Не входит» и
   матрицы) или разделяется (вне зон — эскалация).
2. Требование 3 (SPEC.md:56-72): у трёх вызовов `touch_heartbeat` в
   `orchestrator/fsm_merge_gate.py:355,631,1474` нет критерия. Исход
   прежней формы `touch_heartbeat(conn)` при строках нескольких проектов
   не определён (`orchestrator/store.py:1235`). Серьёзность низкая:
   `orchestrator/config.py:385` (7200 с) больше потолка ожидания
   (`orchestrator/config.py:179`).
3. AC-8 (SPEC.md:163-166) не задаёт точку наблюдения. Однопараметровый
   `_head_task_id(conn)`, который треб. 8 (SPEC.md:91-94) обязывает давать
   глобальный FIFO, оставленный в `wait_for_window`
   (`orchestrator/merge_queue.py:134`), не ловится ни AC-8, ни AC-2
   (SPEC.md:132-135). Нужен критерий через `wait_for_window`, где запись
   очереди другого проекта стоит раньше.
4. AC-10 (SPEC.md:171-174) без «в любом порядке вставки», в отличие от
   AC-13 и AC-14: мутация «держатель — первая строка таблицы»
   (`orchestrator/merge_queue.py:54,65`) проходит при удачном порядке.
