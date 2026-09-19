---
task: 01M2XFSE8G3MBRHHQR38H53J1M
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Мьютекс merge держит процесс, не сессия: очередь для параллельных approve одного пульта и повтор подтяжки при сдвиге main

Ревью-пакет не нашёл SPEC.md и PLAN.md («does not exist in branch; в
дереве — файл не найден»), хотя `tasks/01M2XFSE8G3MBRHHQR38H53J1M/`
материализован в рабочем каталоге шага (`git status` показывает его
непроиндексированным). SPEC, PLAN, TZ и приёмочные тесты прочитаны с
диска вручную — без них ни гейт плана, ни таблица соответствия
невозможны. Сверх пакета точечно читались `orchestrator/fsm_merge_gate.py`
(`_wait_for_branch_ci_green`, `_publish_merge_artifacts`, тело и цикл
гейта), `orchestrator/pull.py::evaluate` (условия `Fresh`),
`orchestrator/merge_queue.py`, `orchestrator/store.py:660-750`,
`orchestrator/schema.py` (таблицы `merge_locks`/`merge_queue`) и
`orchestrator/fsm_postmerge.py` — причина каждого чтения названа в
замечании R1-F1 либо в таблице ниже.

## Гейт плана (Фаза A)

1. Таблица покрытия полна: требования 1-10 SPEC каждое отнесено к шагам
   1-6, шаг 5 (тесты) и шаг 6 (карта + прогон) закрывают требование 10.
2. Шаги — единицы размера MR: четыре модуля по одному шагу, тесты одним
   шагом, карта отдельно. Не микрооперации и не «сделать всё».
3. Подход не конфликтует с архитектурой: ключ владения `(session_id,
   pid)` берётся из уже существующих колонок, `store` остаётся тонким
   CRUD с явным pid, публичные сигнатуры `acquire`/`release`/
   `wait_for_window` сохранены ради существующих моков.
4. Дефект плана — секция «Риски», второй пункт (PLAN.md:146-150):
   утверждение «отказ повторится, и цикл упрётся в общий потолок ожидания
   CI» не выдерживает проверки кодом — на этом пути потолок не
   проверяется вовсе (см. R1-F1). План опирался на несуществующее
   свойство цикла.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (свой = session_id И pid) | OK | `merge_lock._is_own_process` (merge_lock.py:46-53), ветка «свой» до `_holder_is_dead`. |
| 2 (живой процесс своей сессии — тот же отказ с pid, уход в очередь) | OK | Одна f-строка отказа с pid (merge_lock.py:76-79); цикл гейта не менялся, уход в `wait_for_window` прежним путём (fsm_merge_gate.py:771-773). |
| 3 (перехват мёртвого и повторный вход не меняются) | OK | Порядок веток сохранён; мёртвый pid своей сессии перехватывается с прежней записью (планка AC-3, `ProcessOwnershipTest`). |
| 4 (release только своим процессом, store тем же образом) | OK | `store.release_merge_lock(conn, session_id, pid)` — `WHERE session_id=? AND pid=?`; `merge_lock.release` передаёт `os.getpid()`. |
| 5 (очередь адресуется процессом, FIFO прежний) | OK | `enqueue_merge_wait` — plain INSERT без ключа по сессии (схема без PK), `touch`/`dequeue` по (sid, pid), `_head_task_id` — прежний `ORDER BY enqueued_ts, rowid`. Пруна по `_holder_is_dead` — по pid/heartbeat строки, не по сессии. |
| 6 (журнал «ждёт merge-окна: держит …» с pid) | OK | `_current_holder_label` → «<task> (pid <pid>)», «?» без держателя (merge_queue.py:58-68, 122-125). |
| 7 (суффикс `status` с pid; новых выводов нет) | OK | `wait_suffix` тем же label; `doctor`, `notes._silence_window_reason` не тронуты (проверено grep по `orchestrator/doctor/*.py`, `notes.py`). |
| 8 (сдвиг main → запись + повтор тела в том же approve) | OK | `_push_rejected_by_moved_main` по трём подстрокам, «moved» → `("wait", branch)`; scratch-worktree к этому моменту уже снят в `_publish_merge_artifacts` (fsm_merge_gate.py:564) — на повторе не течёт; карта/RETRO пересобираются в новом scratch, вне scratch не пишут. |
| 9 (потолок не сбрасывается; иные отказы как раньше) | Реализовано не так | Не сбрасывается — верно (`deadline` ставится один раз). Но на пути повтора потолок и не ПРИМЕНЯЕТСЯ: `_wait_for_branch_ci_green` при зелёном CI возвращается до проверки `deadline` и без `sleep` — повтор «moved»→тело→«moved» ничем не ограничен и горячий. Иные отказы — прежний «merge FAILED» + `sys.exit`, верно. См. R1-F1. |
| 10 (тесты; три модуля зелёные) | OK | Планка задачи и три модуля зелёные (см. «Проверено исполнением»). Единственная изменённая сверка `tests/test_merge_queue.py:132-135` — точная строка обновлена под pid держателя (требование 7), чувствительность не снижена. Все новые/изменённые тесты несут «Ловит мутацию» с правдоподобной мутацией. |

Диф `tests/`: только добавления плюс адаптация одной точной строки
(выше) и сигнатуры в `tests/test_doctor.py:1768-1778`; удалённых или
ослабленных ассертов нет. Пометок `# AC-n: manual|skip` в планке нет.
Секция PLAN «Влияние на систему» совпадает с диффом: затронуты ровно
`store.py`, `merge_lock.py`, `merge_queue.py`, `fsm_merge_gate.py`,
`tests/`, карта. Защищённые пути не тронуты. Откат — revert одного
коммита, схема БД не менялась.

## Замечания

- major — orchestrator/fsm_merge_gate.py:722-723 (возврат `("wait",
  branch)` на «moved»), :776-786 (цикл: после `_wait_for_branch_ci_green`
  тело заходит заново без проверки `deadline` и без паузы), :280-281
  (`_wait_for_branch_ci_green`: зелёный CI возвращается ДО проверки
  `deadline` и без `sleep`), докстринг :687-688 («между повторами всегда
  стоит опрос CI с паузой и общим потолком — "горячего" бесконечного
  повтора нет»), PLAN.md:146-150 (то же утверждение как аргумент
  приемлемости риска) — суть: повтор по «main сдвинулся» ограничен
  потолком ТОЛЬКО если подтяжка реально сдвинула голову и CI пошёл
  заново. Голова не менялась → CI уже зелёный → `_wait_for_branch_ci_green`
  возвращает note на первой итерации (строка 280-281) — `deadline` не
  сверяется, `sleep` не зовётся, тело заходит заново мгновенно.
  Подтяжка возвращает `Fresh` не только при неподвижном main, но и при
  документном сдвиге и при недоступном sha origin (`pull.py:406-419`) —
  так что «push отвергнут как сдвиг, а подтяжка молчит» — не
  гипотетика. Последствие: любой устойчивый отказ push с маркером
  класса «moved» (застрявший серверный lock ref, отказ origin с тем же
  текстом, второй пульт, стабильно выигрывающий гонку) — бесконечный
  горячий цикл: на каждой итерации `git fetch` + `worktree add` +
  `merge` + регенерация карты (`python3 scripts/codebase_map.py`
  subprocess'ом) + RETRO + `push` + запрос `gh` к CI + две записи
  журнала, без единой паузы и без выхода. Подтверждено исполнением:
  пробник с реальным `_wait_for_branch_ci_green`, зелёным CI и вечно
  отвергаемым push сделал 26 заходов в тело, `sleep_calls=[]`, часы
  `0.0` (см. «Проверено исполнением»). Тесты
  `MovedMainRetryInCycleTest` этого не ловят: они мокают
  `_wait_for_branch_ci_green` и проверяют, что `start`/`deadline`
  ПЕРЕДАНЫ неизменными, а не что потолок ОГРАНИЧИВАЕТ путь.
  Предложение: (а) обязательное — потолок реально применить на пути
  повтора: в `_cmd_approve_merge_gate_cycle` перед новым заходом в тело
  после исхода «moved» сверять `time.monotonic() >= deadline` и
  завершать прежним «merge отклонён: потолок ожидания истёк» + запись
  «merge FAILED» (либо эквивалент — счётчик подряд идущих «moved» с
  именованным отказом; форма на усмотрение разработчика, свойство —
  «путь конечен»); (б) пауза `MERGE_GATE_CI_WAIT_POLL_SEC` перед
  повторным заходом на пути «moved» — либо убрать из докстринга и PLAN
  утверждение о паузе, если решено её не ставить; (в) тест в
  `tests/test_merge_gate_ci_wait.py` с РЕАЛЬНЫМ
  `_wait_for_branch_ci_green`, `ci.branch_status` → GREEN и push, всегда
  отвергаемым «cannot lock ref»: цикл обязан завершиться `SystemExit`
  за конечное число push (и, если пауза введена, `clock.sleep_calls`
  непуст) — с докстрингом «Ловит мутацию: проверка потолка на пути
  повтора убрана — пробник не завершится, `push` упрётся в лимит
  сценария».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/fsm_merge_gate.py:722-723, :776-786, :280-281, докстринг :687-688; PLAN.md:146-150 | Повтор по «main сдвинулся» при уже зелёном CI не проверяет `deadline` и не паузит: `_wait_for_branch_ci_green` возвращает зелёный до сверки потолка; докстринг и PLAN заявляют паузу и потолок, которых на этом пути нет | Устойчивый отказ push класса «moved» при подтяжке `Fresh` — бесконечный горячий цикл fetch/worktree/merge/карта/RETRO/push/`gh` с журналом, растущим без предела (подтверждено пробником: 26 заходов, 0 пауз, часы 0.0) | Применить общий потолок на пути повтора (сверка `deadline` перед новым заходом после «moved» либо конечный счётчик), пауза или снятие утверждения о ней из докстринга/PLAN, тест с реальным циклом ожидания и вечно отвергаемым push |

## Вердикт

changes_requested — исправить R1-F1: путь повтора по «main сдвинулся»
должен быть конечным (потолок `MERGE_GATE_CI_WAIT_CEILING_SEC` реально
применён, а не только «не сброшен»), утверждение о паузе — либо
реализовано, либо снято из докстринга `_cmd_approve_merge_gate` и
PLAN «Риски», и всё это покрыто тестом с реальным
`_wait_for_branch_ci_green`. Остальные девять требований реализованы
верно, тесты качественные, ослаблений нет.

## Проверено исполнением

- `python3 -m pytest -q tasks/01M2XFSE8G3MBRHHQR38H53J1M/acceptance_tests
  tests/test_merge_lock.py tests/test_merge_queue.py
  tests/test_merge_gate_ci_wait.py -p no:cacheprovider` — 73 passed за
  2.74 с (планка AC-1..AC-9 целиком плюс три затронутых модуля).
- `python3 -m pytest -q tests/test_doctor.py -k "MergeLock or MergeQueue
  or merge_lock or merge_queue" -p no:cacheprovider` — 13 passed, 122
  deselected (сторожа `merge_lock`/`merge_queue` доктора с новой
  сигнатурой `release_merge_lock`).
- Пробник R1-F1 (временный файл `_review_probe_tmp.py` в корне рабочего
  каталога, после прогона удалён; в дерево не попал — `git status`
  чист): подкласс
  `tests.test_merge_gate_ci_wait.MovedMainRetryInCycleTest`, в `setUp`
  возвращён РЕАЛЬНЫЙ `fsm_merge_gate._wait_for_branch_ci_green`,
  `ci.branch_status` → `GREEN`, `fake_git` на каждый `push` отдаёт
  `CANNOT_LOCK_REF` с кодом 1 и бросает `Stop` после 25-го;
  `run_cycle()`. Результат:
  `push_calls=26 sync_calls=26 sleep_calls=[] clock=0.0
  journal_moved=25 journal_ci_wait=25` — 26 заходов в тело без единой
  паузы, часы не сдвинулись, потолок не сработал.
- `grep -rn release_merge_lock|dequeue_merge_wait|touch_merge_queue_heartbeat
  orchestrator scripts tests` — все вызывающие в `orchestrator/` и
  `tests/` переведены на новую сигнатуру; иных вызывающих нет.
- `grep` по `orchestrator/doctor/*.py`, `orchestrator/notes.py`,
  `orchestrator/catalog.py` — `doctor` и окно тишины держателя не
  менялись, `status` берёт держателя только через
  `merge_queue.wait_suffix` (SPEC требование 7 — новых выводов нет).
- CI коммита 51ad3760 зелёный (7 проверок) — по описи пакета; полный
  набор `tests/` в шаге не гонялся (решение Оператора 05.09).

## Предложения системе

- Залоченные планки трёх закрытых задач
  (`tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/acceptance_tests/test_ac4_public_signatures_unchanged.py`,
  `tasks/01M291EPQ2VFGCHZTXXC81616V/acceptance_tests/test_ac6_ac7_ceilings.py:117`,
  `tasks/T054/acceptance_tests/test_auto_ack_leases_merge_lock.py:172,256`)
  зовут `store.release_merge_lock(conn, sid)` двумя аргументами и после
  этой задачи падают `TypeError`; их никто не гоняет (`acceptance.run` —
  только своя планка, `run_full_suite` — только `tests/`), так что это не
  дефект задачи, но класс «золотой снимок сигнатур переживает задачу и
  молча протухает» подтверждён третьим экземпляром (PLAN уже отметил
  первый). Адрес: `skills/test-authoring.md` — срок жизни/область
  залоченных планок.
- Класс «тест проверяет, что параметр ПЕРЕДАН, а не что свойство
  ДЕРЖИТСЯ»: `MovedMainRetryInCycleTest` мокает цикл ожидания и сверяет
  `start`/`deadline`, а докстринг рядом заявляет невозможность горячего
  повтора — заявление без теста с реальным циклом. Адрес:
  `skills/test-authoring.md` — утверждение о границе цикла требует
  теста с настоящим циклом, не с моком его.
- Сборщик ревью-пакета (`orchestrator/review.py`) не нашёл SPEC/PLAN ни
  в ветке, ни «в дереве», хотя каталог задачи материализован в рабочем
  каталоге шага; ревьювер восстановил их чтением вручную. Стоит
  проверить, куда смотрит поиск «в дереве» — на корень пульта или на
  worktree шага.
