---
task: 01M5XXA2HY73D3WTXDR19Z5SWW
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py, tests/test_auto_cycle.py, tests/test_invariants.py, tests/test_report.py; в) пути-признаки (гейты): orchestrator/advance_gates/tests_writing.py, orchestrator/fsm_advance.py, orchestrator/fsm_merge_gate.py; в) защищённые пути: tests/test_invariants.py; в) SPEC требует приложения PLAN; г) budget_usd 70 ≥ 45; д) ТЗ ссылается на ADR: ADR-0003, ADR-0029.
spec_sha: b735cef3cda26d15a46ddd4b2b599f66d2e4febc
schema_version: 5
---

# SPEC-AUDIT: GitLab Б2.1 — гейт мержа `target-human`: MR вместо слияния, состояние `awaiting_human`

Аудит №2 — после возврата SPEC Оператором с гейта SPEC 27.10.2026
(решения 1–14). Глубина полная.

## ТЗ и SPEC

ТЗ → SPEC. Требования ТЗ 1–9 отражены в требованиях SPEC 1–2, 4–10;
решения Оператора на гейте SPEC отражены:

| Решение | Где в SPEC | Итог |
|---|---|---|
| 1 (ссылка в БД, 409 — эскалация, без списка MR) | треб. 3, 4; AC-10, AC-11; «Не входит» | отражено (см. отклонение 2 о форме сигнала 409) |
| 2 (запрет отправки в `gitcmd.py`, зона) | треб. 8; зоны; AC-19 | отражено |
| 3 (`max_in_flight` по записи «ветка отправлена», свой проект) | треб. 7; AC-17 | отражено |
| 4 (надзор эпика без удержания места) | треб. 2; AC-24 | отражено |
| 5 (подтяжка → возврат, MR не открыт) | AC-7 | отражено |
| 6 (отказ `undraft_mr`/`assign_mr`) | треб. 4; AC-12 | отражено |
| 7 (`kill` в каждом состоянии после отправки) | треб. 9; AC-26 | отражено (см. отклонение 3 о силе AC-26) |
| 8 (счёт только своего проекта) | треб. 5, 7; AC-13, AC-17 | отражено |
| 9 (`_refuse_if_main_red` не исполняется) | треб. 4; AC-5; матрица | отражено |
| 10 (`doctor` свежесть, зона) | треб. 2; зоны; AC-27 | отражено |
| 11 (мандат поимённо, только перечни состояний) | треб. 11 | отражено, но в конфликте с решением 12 — отклонение 1 |
| 12 (умолчания одной функцией; `mr_assignee` — цифры → `int`) | треб. 1; AC-1, AC-2 | отражено |
| 13 (AC «существующие зелёные», матрица таблицей) | AC-29; «Матрица неослабления» | отражено |
| 14 (регрессионные AC оставить) | AC-22, AC-25 | отражено |

SPEC → ТЗ. Сверх ТЗ и решений нет ничего, кроме разъяснений в рамках
решений. Пункт ТЗ «Не входит» и «Только чтение» перенесены; добавлен
`orchestrator/amend.py` в только чтение — следует из решения 2.

Конфликт решений Оператора 11 и 12 — отклонение 1 (вердикт).

## Факты против кода

Подтверждено по рабочему каталогу:
- `fsm.STATES`/`TERMINAL_STATES` `fsm.py:33-38`; `APPROVE_NEEDS_SHA`
  `fsm.py:839`; `SET_MODELS_STATES` `fsm.py:1959`; `escalated_from`
  `fsm.py:1757`; сверка sha `fsm.py:1802-1808`; `_maybe_ensure_draft_mr`
  `fsm.py:152` и вызовы `:1495`, `:1762`, `:1861`, `:1874`, `:1922`,
  `fsm_advance.py:361`, `:648`, `fsm_merge_gate.py:285`, `:1008`;
  `github_adapter.undraft_mr` вызов `fsm.py:1627`.
- Тело гейта `fsm_merge_gate.py:1442`, шаги `:1498-1550` (в т.ч.
  `_refuse_if_main_red` `:1525`, `_refuse_during_canary` `:1541`).
- `gitcmd.PUSH_SENT_ACTION` `gitcmd.py:176`, чтение последней
  `gitcmd.py:219-231`, `_whitelist_refusal` `gitcmd.py:625`.
- `zone_lock.BLOCKING_STATES` `zone_lock.py:110`, проверка `:494`;
  `_stay_since_id` (`zone_lock.py:370`) отсчитывает пребывание от
  `tests_writing` — `awaiting_human` после `merge_gate` в нём остаётся,
  удержание зон по `_occupies` работает без правки.
- `auto.py:70`, `:544`, `:1150`, `:1168`, `:1298-1306`, `:1338`;
  `report.MANUAL_GATE_STATES` `report.py:42`; `report.STATE_ORDER =
  fsm.STATES` `report.py:48`; `board.py:19-43`; `watch.py:40`;
  `catalog.py:1353`; `parallel_limit.py:24-36` (живые lease);
  `doctor/branch_freshness.py:40` (фильтр `TERMINAL_STATES`);
  `cleanup.py:296-306`; `amend.py:834`; `github_adapter.py:118`,
  `:195-208`, `:211-254`, `:257`, `:301`; `tests_writing.py:69`, `:156`.
- `targets.push_whitelisted` `targets.py:537-542`;
  `SUPPORTED_MERGE_GATES = ("operator",)` `targets.py:30`.
- Тесты: `tests/test_auto_cycle.py:64-66`, `:329`, `:382-383`, `:1166`;
  `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:37`, `:192-199`,
  `:202-218`; `tests/test_invariants.py:78`, `:611-616`, `:646`
  (`MergeOnlyFromMergeGateTest`), `:693`, `:1003`, `:1019`.

Расходится или не учтено SPEC:
- Б-1. `policy.mr_assignee` сегодня проверяется как «непустая строка»
  (`targets.py:648-651`), и долгоживущий тест Б1.1
  `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169` держит
  `"alice"` **допустимым** значением (загрузка обязана пройти,
  `:186-204`). Требование 1 («не из цифр — отказ загрузки») делает этот
  тест красным; в мандате требования 11 его нет, матрица строки не несёт.
- Б-2. `forge.MergeRequest` (`forge.py:67-74`) кода ответа не несёт —
  только текст `reason`; 409 доходит строкой «GitLab ответил кодом 409
  на POST …» (`gitlab_adapter.py:209`), `forge.py`/`gitlab_adapter.py` —
  только чтение. Требование 4/AC-11 не говорит, по какому признаку пульт
  узнаёт «уже существует».
- Б-3. `yamlmini.scalar` превращает `mr_assignee: 42` без кавычек в
  `int` (`yamlmini.py:59-60`), а нынешняя проверка отказывает не-строке
  (`targets.py:650`). SPEC («в записи строка из цифр») не говорит, отказ
  ли это или допустимая форма; естественная запись числового id без
  кавычек получит отказ загрузки.
- Б-4. `forge.undraft_mr`/`assign_mr` принимают номер MR (`mr: int`,
  `forge.py:223-228`), а SPEC хранит «ссылку на MR» (треб. 3). Что
  хранится — URL, iid или оба — не названо; из URL iid выводится
  разбором текста.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | умолчание `max_awaiting` 3 → иное; `>= 0` вместо `> 0`; `bool(...)` вместо проверки типа |
| AC-2 | да | `mr_assignee` уходит строкой; отказа на «abc» нет; запись журнала без исполнителя не пишется |
| AC-3 | да | задача не переведена в `awaiting_human`; ссылка не в БД/журнале; исполнитель не передан |
| AC-4 | да | для `target-human` не пропущены `_perform_carpentry_merge`/`_push_merged_main`/`_cleanup_merged_task`/`_await_main_ci` |
| AC-5 | да | `_refuse_if_main_red` оставлен для `target-human`; зелёный CI головы не требуется |
| AC-6 | да | сверка sha с головой MR снята |
| AC-7 | да | MR открыт после подтяжки без нового CI |
| AC-8 | да | приложения PLAN молча пропущены |
| AC-9 | да | ссылка записана при отказе `open_mr`; задача ушла в `awaiting_human` |
| AC-10 | да | при ссылке в БД снова зовётся `open_mr` |
| AC-11 | частично | ловит повторный `open_mr`; признак 409 не задан (Б-2) — тест вынужден выбрать форму `reason`, навязывая устройство |
| AC-12 | да | ссылка не сохранена после успешного `open_mr` при отказе `undraft_mr` → второй MR |
| AC-13 | да | счёт по всем проектам; `>` вместо `>=` |
| AC-14 | да | черновик через `gh`; на гейте открыт второй MR |
| AC-15 | да | при `draft_mr: false` MR на входе в `verifying` |
| AC-16 | да | описание без защищённых путей |
| AC-17 | частично | ловит счёт только `verifying..awaiting_human` и счёт чужих проектов; путь сжатия `_rewrite_push_gate` (`tests_writing.py:66-67`) не назван — мутация «предел только в `ensure_head_in_origin`» проходит при `squash_before_mr: false` в тесте |
| AC-18 | да | `approve`/`reject`/`answer` проходят в `awaiting_human` |
| AC-19 | да | проверка состояния в `amend.py` вместо `gitcmd.py` (шпион на прямой вызов `gitcmd.git`) |
| AC-20 | да | `awaiting_human` не в `_NO_ALERT_FINAL_STATES` |
| AC-21 | да | `awaiting_holds_zones` игнорируется |
| AC-22 | регрессия | смена `merge_after` на ожидание `awaiting_human` |
| AC-23 | да | `waiting_on` → `role`; флаг «ЖДЁТ ОПЕРАТОРА» |
| AC-24 | да | статус `_READY` → перезапуск по кругу (`auto.py:1306`) |
| AC-25 | регрессия | `escalated_from` не пишется для нового состояния |
| AC-26 | слабо | см. ниже |
| AC-27 | да | фильтр `doctor` без `awaiting_human` |
| AC-28 | да | приложение не применяется к base |
| AC-29 | да | поведение `operator` изменено |

AC-26 слабый: проект с `target-human` — под белым списком отправок
(`targets.push_whitelisted`, `targets.py:537-542`), и `_whitelist_refusal`
уже сегодня отказывает `push --delete` ветки задачи до запуска git
(`gitcmd.py:667-670`); закрытие PR `cleanup.py:304` идёт только для
`forge: github`. Для GitLab-записи AC-26 проходит на **неизменном**
`cleanup.py`, если шпион стоит на subprocess: `kill` по-прежнему пытается
удалить ветку (в журнале «отправка отказана»), но шпион ничего не видит.
Нужно: шпион на argv `gitcmd.git`/`gitcmd.in_repo` (вызова удаления нет
вовсе), отсутствие записи «отправка отказана» в журнале и вариант
`forge: github` + `target-human` (шпион `ci.gh` без `pr close`).

Требования без критерия: треб. 2 «`APPROVE_NEEDS_SHA`,
`SET_MODELS_STATES`, `STATE_ROLE` — по смыслу» (что именно — не сказано,
теста нет); «в `MAX_PARALLEL_TASKS` не считается» и «рабочая копия
хранится до `done`/`kill`» вне `approve` — без AC (последствие слабое:
лимит считает lease, `parallel_limit.py:24-36`).

## Зоны

- Зоны SPEC покрывают требования: `gitcmd.py` (треб. 8),
  `doctor/branch_freshness.py` (треб. 2), `store.py`/`schema.py`
  (треб. 3), `cleanup.py`, `answer.py`, `catalog.py` и прочие перечни.
- Защищённый путь `tests/test_invariants.py` — только приложением PLAN
  (треб. 10, AC-28); `config.PROTECTED_PATHS` иначе не задеты.
- Деление: часть 1 — без `fsm_merge_gate.py`, `fsm_advance.py`,
  `github_adapter.py`, `tests_writing.py`, и ей они не нужны; часть 2 —
  без `store.py`: запись ссылки — существующим `store.update_task`,
  счёт `awaiting_human` — `store.project_tasks`, счёт отправок —
  `store.journal_action_exists`; если части 2 понадобится новый запрос
  в `store.py`, это расширение зон. Часть 2 без `auto.py`: отказ
  `max_in_flight` неизвестного класса — «чинит Оператор»
  (`refusal_classes.py:6-9`), `auto` остановится; задача сама не
  продолжит, когда место освободится.
- Отклонение 1 затрагивает зону `tests/`: правка
  `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169` нужна, но
  мандата нет.

## Матрица неослабления

Матрица SPEC сверена; строки подтверждены по коду. Не хватает строк:

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Проверка `policy.mr_assignee`: «непустая строка» → «строка из цифр» | `targets.py:648-651`; допустимость `"alice"` — `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169` | проверка строже; ожидание теста «alice загружается» меняется | AC-2; правка теста вне мандата | вопрос Оператору (отклонение 1) |
| Отказ во время живой канарейки `_refuse_during_canary` для `target-human` | `fsm_merge_gate.py:1541` | не классифицировано SPEC | не покрыто | вопрос Оператору (отклонение 4) |
| Мьютекс merge-окна и очередь (`_cmd_approve_merge_gate_cycle`) для `target-human` | `fsm_merge_gate.py:1581-1601` | не классифицировано SPEC | не покрыто | вопрос Оператору (отклонение 4) |

## Пути обхода гейтов

- Е-1 (`max_in_flight`). Предел ставится только «на входе в
  `verifying`» (треб. 7, как в ТЗ), а ветка первой отправкой уходит и
  другими путями: `github_adapter.ensure_draft_mr` отправляет ветку на
  каждом входе в `in_dev` для `forge: github` (`github_adapter.py:163-166`,
  через `fsm._maybe_ensure_draft_mr`); `amend-tests` в `in_dev` —
  `amend.py:834`. Буквально выполненное треб. 7 оставляет задачам
  GitHub-проекта с `target-human` ветку на сервере сверх предела. Треб. 6
  «через `forge`, а не через `gh`» выключение `ensure_draft_mr` для
  `target-human` прямо не называет.
- Е-2 (AC-26). Исполнитель может не менять `cleanup.cleanup_project_remote`
  для GitLab-записи — отказ белого списка уже скрывает удаление от шпиона
  subprocess (см. «Проверяемость»).
- Е-3 (AC-11). Признак 409 не задан — реализация, распознающая любой
  отказ `open_mr` с подстрокой «409» в тексте, и планка, подающая
  иную форму, расходятся; либо реализация сочтёт «уже существует»
  любой отказ и эскалирует вместо «остаётся на гейте» (AC-9).
- Е-4 (тело гейта). Шаги, не названые ни «исполняются», ни «не
  исполняются»: публикация головы `_ensure_branch_head_published`
  (`fsm_merge_gate.py:1513`) — без неё MR по неопубликованной голове;
  `_refuse_during_canary` (`:1541`); мьютекс merge-окна (`:1581-1601`);
  коммит закрытия `cleanup._commit_closing` (`:1545`). Исполнитель
  вправе выбрать любое прочтение.

## Вердикт

**concerns** — решения Оператора 1–14 перенесены, факты о коде верны;
остались отклонения, которые Оператор решает на гейте:

1. Конфликт решений 11 и 12: правило «`mr_assignee` — только цифры»
   (SPEC треб. 1, AC-2) ломает долгоживущий тест
   `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169`
   (`"alice"` — допустимое значение), которого нет в мандате треб. 11 и
   в матрице. Нужно: добавить его в мандат поимённо (замена допустимого
   значения на строку цифр) или иное решение.
2. Признак «MR уже существует (409)» не задан на интерфейсе `forge`
   (`forge.py:67-74` без кода; текст `gitlab_adapter.py:209`; оба файла
   только чтение) — SPEC треб. 4, AC-11. Нужно: назвать признак (разбор
   кода из `reason` в `fsm_merge_gate.py`) либо снять чтение-только.
3. AC-26 проходит на неизменном `cleanup.py` для GitLab-записи: удаление
   ветки уже отказано белым списком `gitcmd.py:667-670`, PR не
   закрывается не-GitHub (`cleanup.py:304`). Нужно: шпион на argv
   `gitcmd.git`/`in_repo`, нет записи «отправка отказана», вариант
   `forge: github` + `target-human`.
4. Не классифицированы шаги гейта для `target-human`: публикация головы
   (`fsm_merge_gate.py:1513`), `_refuse_during_canary` (`:1541`),
   мьютекс merge-окна (`:1581-1601`), коммит закрытия (`:1545`).
5. `max_in_flight` обходится первой отправкой вне входа в `verifying`:
   `github_adapter.py:163-166` (вход в `in_dev`, `forge: github`),
   `amend.py:834`; AC-17 не называет путь сжатия
   (`tests_writing.py:66-67`).
6. Форма `mr_assignee` без кавычек: `mr_assignee: 42` → `int`
   (`yamlmini.py:59-60`) — отказ или допустимо, SPEC не говорит.
7. Что хранит «ссылка на MR» (URL/iid) не названо, а `undraft_mr`/
   `assign_mr` берут iid (`forge.py:223-228`).
8. Требование 2 «`APPROVE_NEEDS_SHA`, `SET_MODELS_STATES`,
   `STATE_ROLE` — по смыслу» не говорит, входит ли `awaiting_human` в
   каждый перечень, и критерия не имеет.
