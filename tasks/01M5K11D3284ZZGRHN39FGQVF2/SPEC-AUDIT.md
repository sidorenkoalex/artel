---
task: 01M5K11D3284ZZGRHN39FGQVF2
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py, tests/test_artifact_branch_push.py, tests/test_artifact_ref_sync.py.
spec_sha: a7d90a77a61f5ad4bb9646d82fa73b22d6df14dc
schema_version: 5
---

# SPEC-AUDIT: Отправка документов задачи: ответ сервера 5xx — отдельная причина с повтором, запись успеха после отказа, снятие send_pending

## ТЗ и SPEC
ANSWER-n.md у задачи нет; решений Оператора на гейте SPEC в брифе нет.

ТЗ → SPEC: требования 1–6 ТЗ перенесены по смыслу и почти дословно
(SPEC.md:33–80); выбор Оператора «снять `send_pending`, не вызывать»
сохранён (SPEC.md:67–72, «Контекст» SPEC.md:24–28); «Ограничение зон по
смыслу» (только докстринг `_fix_unsent_closed_refs`) — SPEC.md:71–72 и
«Не входит»; «Только чтение» и «Не входит» ТЗ — в «Не входит» SPEC целиком;
девять тестовых пунктов ТЗ (требование 6) — AC-1…AC-9 один к одному.

Отличия SPEC от ТЗ, все обоснованные:
- Способ подмены паузы (SPEC.md:74–78): ТЗ называет подмену
  `artifact_branch.time.sleep`, SPEC — замену атрибута `artifact_branch.time`
  объектом-заместителем. Это уточнение: и строка `"…time.sleep"`, и пара
  «`<…>.time`, `"sleep"`» запрещены сторожем
  `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py:42` (`_TARGET_STRING`)
  и `:66–69` (пара соседних аргументов). Буквальное прочтение ТЗ сделало бы
  сторож красным на новом тесте. Смысл ТЗ не меняется.
- AC-3 добавляет «пауза не вызвана» и «запись non-fast-forward побайтно
  прежняя» — следуют из требований 2–3 ТЗ.
- Бюджет $25 вместо $20 ТЗ — пол калибровки `orchestrator/config.py:654`
  (`BUDGET_CALIBRATION_FLOOR_USD = 25.0`), `skills/spec-authoring.md:44`.
  Не отклонение.

Требований SPEC сверх ТЗ нет.

## Факты против кода
Каждое утверждение SPEC о коде сверено с рабочим каталогом (main bd01a928):
- `_classify_push_failure` — `orchestrator/artifact_branch.py:320`, подстрока
  `rejected`/`fetch first`/`non-fast-forward` → non-ff, остальное → «сеть»
  (`:330–333`) — подтверждено.
- Причины — `orchestrator/artifact_branch.py:55–57` — подтверждено.
- `_attempt_push` — `:336`, один `git push -q origin <ref>:<ref>` (`:346`),
  возврат тройкой (`:347–350`) — подтверждено.
- Совет «свести merge-коммитом» с парой sha — `_journal_push_outcome`
  `:369–373` — подтверждено.
- Все три вызова `_send` с `journal_success=False` — `:315` (в `_write`),
  `:425` (`send_pending`), `:444` (`origin_sync_refusal`); успех журналирует
  только `push` (`:378`, `:390–391`) — подтверждено.
- `send_pending` — `:418`; вызовов в `orchestrator/` нет
  (`git grep send_pending -- orchestrator`: только `:25`, `:418` и докстринг
  `orchestrator/doctor/artifact_branches.py:182`) — подтверждено.
- Докстринг модуля, строки 24–27, обещает досылку через `send_pending` —
  подтверждено (`orchestrator/artifact_branch.py:24–27`).
- Путь досылки на переходе: `store.set_state` (`orchestrator/store.py:839`)
  → `_append_passport_line` (`:890`, `:960`; докстринг `:967–969` прямо
  называет повтор отправки) → `artifact_branch.append_passport_line`
  (`orchestrator/artifact_branch.py:694`) → `commit_files` → `_write` →
  `_send` (`:315`) — подтверждено.
- `store.last_task_step_of(conn, task_id, actions)` —
  `orchestrator/store.py:1185`, `ORDER BY id DESC LIMIT 1` — подтверждено.
- Модуль не импортирует `time` сейчас (`orchestrator/artifact_branch.py:29–33`)
  — требование 2 его добавляет; противоречия нет.
- Инвариант 33 (`docs/invariants.md:63`): плотницкая запись через `gitcmd`;
  повтор идёт через модульный `_git` (`orchestrator/artifact_branch.py:99–102`
  → `gitcmd.in_repo`) — точку подмены не трогает, подтверждено.
- «Строки `HTTP 5xx`/`returned error: 5xx` в
  `ClassifyPushFailureTest` отсутствуют» — подтверждено
  (`tests/test_artifact_branch_push.py:20–35`, строки `fetch first`,
  `non-fast-forward updates`, `ssh: Could not resolve hostname`). Других
  тестов, подающих строки сервера в отправку документов, нет (вхождения
  `HTTP 502`/`Internal Server Error`/`[remote rejected]` в `tests/` — про
  `gh`, агента и `fsm_merge_gate`, не про `artifact_branch`).
- `docs/codebase-map.md:381` перечисляет `send_pending`; карта — общая зона
  (`orchestrator/config.py:814`) — подтверждено.

Расхождений фактов с кодом нет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `_classify_push_failure` без ветки (б) — строка с `[remote rejected] … (Internal Server Error)` уходит в non-ff по ветке «любое `rejected`» (красный на текущем коде) |
| AC-2 | да | признак `(failed)`/`fatal error in commit_refs` не входит в (б) — «сервер» не получается |
| AC-3 | да | (а) проверяет голое `rejected` вместо `[rejected]` (тогда pre-receive уходит туда же — не ловится), но повтор на non-ff (2+ вызова push или пауза) и изменение детали non-ff ловятся; потеря ветки (в) — hook declined уходит в «сеть» — ловится |
| AC-4 | да | регэксп `HTTP 5\d\d`/`returned error: 5\d\d` не добавлен — «сеть» (красный на текущем коде) |
| AC-5 | да | порядок (б) раньше (а) — строка с `fetch first` и `Internal Server Error` даёт «сервер» |
| AC-6 | да, частично | нет повтора (1 вызов push); пауза не та константа или до первой попытки (2 паузы); успех после повтора не журналируется; FAILED пишется за промежуточную попытку. НЕ ловится: деталь успеха без числа попыток (требование 4, SPEC.md:60) |
| AC-7 | да, частично | повторов не 3; FAILED на каждую попытку; деталь без `сервер (попыток 3): ` или с советом/sha. НЕ ловится: пауза и после последней попытки (3 паузы вместо 2 — «между попытками», SPEC.md:51) |
| AC-8 | да | успех журналируется всегда (вторая половина); успех журналируется только после повтора, не по последней записи FAILED (первая половина) |
| AC-9 | да | `send_pending` оставлена или упомянута в `orchestrator/`; досылка на переходе сломана правкой `_send`/`_write` (существующий тест краснеет) |

Пробелы (каждый — отклонение уровня concerns):
1. «Иные причины не повторяются» (SPEC.md:51–52) проверяется только для
   non-ff (AC-3). Мутация `if reason != PUSH_REASON_NON_FAST_FORWARD:
   повторять` (повтор и на «сеть») проходит все AC: AC-8 не требует одного
   вызова push при «сети». Нужна строка «отказ "сеть" — `git push` вызван
   один раз, пауза не вызвана».
2. «`--force` ни в какой форме не появляется» (SPEC.md:52) для пути
   повтора не покрыт: существующий
   `tests/test_artifact_branch_push.py:166` (`test_never_passes_force`)
   гоняет только non-ff без повтора. Мутация «повторная попытка с
   `--force-with-lease`» проходит AC-6/AC-7. Нужна проверка аргументов
   всех вызовов push в AC-6/AC-7.
3. Деталь успеха с числом попыток (SPEC.md:59–60) не проверяется AC-6.
4. Число пауз при исчерпании попыток (`PUSH_SERVER_RETRY_ATTEMPTS − 1`) не
   проверяется AC-7.

## Зоны
Зоны SPEC — `orchestrator/artifact_branch.py, orchestrator/doctor/artifact_branches.py, tests/`
— совпадают с ТЗ и покрывают всё, что требует правки:
`_classify_push_failure`/`_attempt_push`/`_journal_push_outcome`/`push`/
`_send`/`send_pending`/докстринг модуля — `orchestrator/artifact_branch.py`;
докстринг `_fix_unsent_closed_refs` — `orchestrator/doctor/artifact_branches.py:180–182`;
новые тесты — `tests/`. Карта `docs/codebase-map.md` — общая зона
(`orchestrator/config.py:814`). Вызывающие (`store.py`, `snapshot.py`,
`fsm_merge_gate.py`, …) не меняются — сигнатуры `commit_files`/`push`/
`origin_sync_refusal` прежние, форма возврата меняется только у закрытой
`_attempt_push` (вызывающие — `:390`, `:412`, оба в зоне; в `tests/`
`_attempt_push` никто не вызывает и не подменяет).
Защищённые пути (`orchestrator/config.py:769–775`): требования не заставляют
менять ни `tests/test_invariants.py`, ни `**/conftest.py`, ни `docs/invariants.md`;
песочница ролей не расширяется. Отклонений нет.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `_classify_push_failure`: порядок признаков | `[rejected]`/`fetch first`/`non-fast-forward` → non-ff — `tests/test_artifact_branch_push.py:20`, `:26` | да | те же тесты без правок + AC-3, AC-5 | остаётся |
| `_classify_push_failure`: остаток | прочее → «сеть» — `tests/test_artifact_branch_push.py:31` | да (строка ssh вне (а)–(в)) | тот же тест; новые строки 5xx — намеренная смена ТЗ, существующих ожиданий не меняет | остаётся |
| `_journal_push_outcome`: деталь non-ff | пара sha + «свести merge-коммитом» — `tests/test_artifact_branch_push.py:150` | да, побайтно | тот же тест + AC-3 | остаётся |
| `_attempt_push`: повтор | без `--force` — `tests/test_artifact_branch_push.py:166` (путь non-ff) | да по требованию 2 | путь повтора — не покрыто (пробел 2 «Проверяемости») | concerns: дополнить AC-6/AC-7 |
| `_send`: запись успеха | успех журналирует только `push` — `tests/test_artifact_branch_push.py:106` (`len == 1`) | да (до `push` отказа не было — записи `_send` не появляется) | тот же тест; новая запись — AC-6, AC-8 | остаётся |
| удаление `send_pending` | досылка на переходе — `tests/test_artifact_ref_sync.py:142` | да (путь — коммит паспорта, `orchestrator/store.py:890`) | тот же тест без правок (AC-9) | остаётся |
| новые тесты с паузой | запрет глобальной подмены `time.sleep` — `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` | да | SPEC.md:74–78 прямо предписывает объект-заместитель | остаётся |
| повтор `git push` через `_git` | плотницкая запись через `gitcmd` — `docs/invariants.md:63`, `tests/test_invariants.py:1901` | да | тот же тест | остаётся |

Раздела «Меняемое поведение» в SPEC нет — и не нужно: ожидания существующих
утверждений не меняются (сверено выше). «Остаётся, не покрыто» без замены —
только путь повтора без `--force` (пробел 2).

## Пути обхода гейтов
1. Признак `(failed)` подстрокой. SPEC.md:40 пишет «строка `[remote rejected] … (failed)`
   или `(failure)`», не уточняя, точная ли это скобочная форма и требует ли
   `(failure)` `[remote rejected]`. Реализация «`failed` где угодно после
   `[remote rejected]`» проходит AC-2, но переводит в «сервер» с повтором и
   отказы `(failed to update ref)`/`(failed to lock)` — по смыслу (в)
   «прочий `[remote rejected]` — non-ff, как прежде». AC без негативного
   случая это пропускает. Отклонение уровня concerns: дополнить AC
   негативной строкой `[remote rejected] … (failed to update ref)` → non-ff
   либо закрепить точную форму `\((failed|failure)\)`.
2. Повтор на любую причину, кроме non-ff (пробел 1 «Проверяемости»): AC
   проходятся, требование 2 «иные причины не повторяются» нарушено —
   10 с паузы на каждом сетевом отказе на переходе.
3. Повтор с `--force` (пробел 2): все AC зелёные, нарушен запрет SPEC.md:52.

## Вердикт
concerns — фактических ошибок, потерь ТЗ и проблем зон нет; критерии
пропускают правдоподобные поломки. Отклонения:
1. SPEC.md:51–52, AC-3/AC-8 (SPEC.md:93–98, :116–118) — нет критерия «отказ
   "сеть" не повторяется» (`git push` один раз, пауза не вызвана); мутация
   «повтор на всё, кроме non-ff» проходит.
2. SPEC.md:52, AC-6/AC-7 (SPEC.md:106–115) — нет проверки отсутствия
   `--force` в вызовах повтора; существующий
   `tests/test_artifact_branch_push.py:166` покрывает только путь без повтора.
3. SPEC.md:40 — неоднозначная форма признака `(failed)`/`(failure)`; без
   негативного AC подстрочная реализация переклассифицирует
   `[remote rejected] … (failed to update ref)` в «сервер» с повтором.
4. SPEC.md:59–60, AC-6 (SPEC.md:106–109) — деталь успеха «число попыток» не
   проверяется.
5. SPEC.md:50–51, AC-7 (SPEC.md:111–114) — число пауз
   (`PUSH_SERVER_RETRY_ATTEMPTS − 1`, «между попытками») не проверяется.

Все пять закрываются дополнением AC (Оператором на гейте или правкой
SPEC); вопроса, без которого вердикт не вынести, нет.
