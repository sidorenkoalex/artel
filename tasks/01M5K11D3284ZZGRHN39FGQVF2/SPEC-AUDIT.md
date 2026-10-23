---
task: 01M5K11D3284ZZGRHN39FGQVF2
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py, tests/test_artifact_branch_push.py, tests/test_artifact_ref_sync.py; г) budget_usd 45 ≥ 45."
spec_sha: 2fe8c8e9dfb012208d5f4b54aeebc8cd83a1503b
schema_version: 5
---

# SPEC-AUDIT: Отправка документов задачи: ответ сервера 5xx — отдельная причина с повтором, запись успеха после отказа, снятие send_pending

Круг 2: аудит SPEC после решений Оператора на гейте SPEC 23.10.2026 (круг 1).
Sha проверенного SPEC сверен: `git hash-object SPEC.md` = 2fe8c8e9dfb012208d5f4b54aeebc8cd83a1503b.

## ТЗ и SPEC
- Требования ТЗ 1–6 перенесены в SPEC.md требования 1–6 (SPEC.md:31–91) без
  потерь: порядок (а)–(г), константы 3 и 5, `import time` на уровне модуля,
  форма детали `сервер (попыток N): …`, чтение через `store.last_task_step_of`
  с кортежем двух действий, удаление `send_pending` и правка двух докстрингов,
  тесты без сети.
- Расхождения SPEC с ТЗ — все от решений Оператора на гейте SPEC №1:
  точная форма `(failed)`, `(failure)` и `(failed to update ref)` — не «сервер»
  (ТЗ п.1(б) называл `(failure)` признаком — решение п.3 это прямо снимает;
  `fatal error in commit_refs … (failure)` остаётся «сервер» по признаку
  `fatal error in commit_refs`, AC-2 и AC-12 согласованы); AC-10–AC-14 —
  пп. 1, 2, 4, 5 решения. Отклонением не являются.
- Уточнение сверх ТЗ, оправданное кодом: ТЗ п.6 называл подмену
  `artifact_branch.time.sleep`; SPEC требование 6 (SPEC.md:84–91) заменяет её
  объектом-заместителем `artifact_branch.time` — форма ТЗ была бы находкой
  сторожа `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py:172-175`
  (`mock.patch.object(mod.time, "sleep", f)`), заместитель им разрешён
  (`:199-221`). Это не новое требование, а исполнимая форма прежнего.
- Бюджет $45 вместо $20 ТЗ обоснован в «Материалах» (пол калибровки $25,
  `orchestrator/config.py` `BUDGET_CALIBRATION_FLOOR_USD`) — решение за Оператором.

## Факты против кода
Всё сверено с рабочим каталогом (main bd01a928), подтвердилось:
- `orchestrator/artifact_branch.py:24-27` — докстринг обещает `send_pending` из `store.set_state`.
- `:320` `_classify_push_failure` — подстрока `rejected`/`fetch first`/`non-fast-forward` → non-ff, иначе «сеть»; `:55-57` три причины.
- `:336` `_attempt_push` — один `_git(repo, "push", "-q", "origin", f"{ref}:{ref}")`, возврат тройки; зовут `:390` (`push`) и `:412` (`_send`).
- `:315`, `:425`, `:444` — три вызова `_send(..., journal_success=False)`; `:418` `send_pending`; `:694` `append_passport_line`.
- `:353-374` `_journal_push_outcome` — совет «свести merge-коммитом» и пара sha только для non-ff; `:378` `push`.
- `:99` модульная `_git` — точка подмены для тестов; модуль `time` сейчас не импортирует (`:29-33`).
- `orchestrator/store.py:960` `_append_passport_line` (зовётся из `set_state` `:890`, сам зовёт `artifact_branch.append_passport_line` `:976`); `:1185` `last_task_step_of(conn, task_id, actions)` — `ORDER BY id DESC LIMIT 1`.
- `orchestrator/doctor/artifact_branches.py:165` — `push` из `doctor --fix`; `:180-185` докстринг `_fix_unsent_closed_refs` упоминает `send_pending`.
- `git grep send_pending -- orchestrator` — только `artifact_branch.py:25,418` и `doctor/artifact_branches.py:182`; вызовов нет. В `tests/` — только докстринги (`test_artifact_ref_sync.py:145`, `test_01m409…_project_docs_ref.py:578`, `test_01m484…_artel_docs_ref.py:191`), не код — удаление функции их не роняет.
- `orchestrator/config.py:814` `COMMON_ZONES` содержит `docs/codebase-map.md` и `tests/` — регенерация карты в общей зоне.
- В `tests/` нет stderr отправки ссылки документов с `Internal Server Error`/`(failed)`/`commit_refs`/`HTTP 5xx` (строки `HTTP 502` в `test_*ci*` — ответы `gh`, не `artifact_branch`); `[remote rejected]` в `tests/test_merge_gate_ci_wait.py:271,281` — путь `fsm_merge_gate`, вне задачи. Реальный отказ хука `reject_ref_pushes` (`tests/test_artifact_ref_sync.py:77`) даёт `(pre-receive hook declined)` → non-ff без повтора; `break_origin` (`:69`) → «сеть». Существующие тесты не получат настоящих пауз по 5 с и не изменят исходов.
- `tests/test_artifact_branch_push.py:104-115` (`PushSuccessTest`, ровно одна запись push) остаётся зелёным: требование 4 касается `_send`, а коммит в песочнице идёт до первого FAILED.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `[remote rejected] … (Internal Server Error)` уходит в (в) раньше (б) — non-ff |
| AC-2 | да | признак `(failed)` или `fatal error in commit_refs` выпущен из (б) |
| AC-3 | да | (в) снят (прочий `remote rejected` → «сеть»/«сервер»); повтор на non-ff; правка формы записи non-ff (вместе с `test_artifact_branch_push.py:162`) |
| AC-4 | да | регэкспы `HTTP 5\d\d`/`returned error: 5\d\d` не добавлены |
| AC-5 | да | (б) проверяется раньше (а) |
| AC-6 | да | нет повтора; пауза не та константа; успех после повтора не журналируется; FAILED пишется на промежуточной попытке |
| AC-7 | да | бесконечный/лишний повтор; FAILED на каждую попытку; совет «свести» в записи «сервер» |
| AC-8 | частично | ловит «успех не журналируется после отказа» и «успех журналируется всегда»; НЕ ловит «успех журналируется на каждой отправке после любого когда-либо бывшего FAILED» — см. вердикт, п.1 |
| AC-9 | да | `send_pending` оставлена; упоминание в докстринге; досылка на переходе сломана |
| AC-10 | да | повтор на всё, кроме non-ff |
| AC-11 | да | `--force`/`--force-with-lease=…`/`+refspec` в повторе |
| AC-12 | да | признак `(failed` подстрокой — `(failed to update ref)`/`(failure)` станут «сервер» |
| AC-13 | да | деталь успеха без числа попыток или с неверным N (1, 3) |
| AC-14 | да | пауза и после последней попытки (3 вместо 2) |

## Зоны
- Зоны `orchestrator/artifact_branch.py, orchestrator/doctor/artifact_branches.py, tests/` (SPEC frontmatter) покрывают все правки требований 1–6. Защищённых путей (`config.PROTECTED_PATHS`) задача не трогает; песочница ролей не расширяется.
- `docs/codebase-map.md` (удаление `send_pending` из карты) — общая зона (`orchestrator/config.py:814`), вне зон SPEC допустим.
- Ограничение по смыслу для `doctor/artifact_branches.py` (только докстринг) сохранено (SPEC.md требование 5, «Не входит»).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `_classify_push_failure` — новая ветка (б) | non-ff для `[rejected]…(fetch first)` и `non-fast-forward` — `tests/test_artifact_branch_push.py:20-29`; прочее → «сеть» `:31-35` | да; намеренная смена только для `HTTP 5xx`/`returned error: 5xx` (существующими тестами не утверждается) | те же тесты без правок + AC-1–AC-5, AC-12 | ок |
| Повтор `git push` в `_attempt_push` | без `--force` — `tests/test_artifact_branch_push.py:180-201` | да | тот же тест + AC-11 | ок |
| Запись FAILED «сервер» вместо non-ff | запись non-ff с парой sha и советом — `tests/test_artifact_branch_push.py:162-178` | да, побайтно для non-ff | тот же тест + AC-3, AC-7 | ок |
| Удаление `send_pending` | досылка на переходе — `tests/test_artifact_ref_sync.py:140-164` (проверяет поведение через `set_state` → паспорт) | да | тот же тест без правок (AC-9) | ок |
| Журнал успеха в `_send` | журнал успеха `push` — `tests/test_artifact_branch_push.py:104-115` | да | тот же тест; AC-6, AC-8, AC-13 | ок; пробел AC-8 — вердикт п.1 |

Раздела «Меняемое поведение» в SPEC нет и не требуется: ожидания существующих тестов не меняются (SPEC «Не входит»).

## Пути обхода гейтов
1. Требование 4 (SPEC.md:67-75) исполнимо формально иначе, чем задумано: «последняя запись — FAILED» можно заменить на «в журнале задачи есть FAILED» или читать `last_task_step_of(conn, id, ("push артефактной ветки FAILED",))` (кортеж из одного действия). Оба варианта пройдут AC-6, AC-8, AC-13: AC-8 (SPEC.md:125-127) проверяет «отказ → успех журналируется» и «два успеха подряд без отказа — нет записи», но не «отказ → успех → успех: вторая запись успеха не появляется». Итог — после первого же отказа каждая строка паспорта пишет «push артефактной ветки», ровно то засорение журнала, от которого требование 4 защищает.
2. Деталь `сервер (попыток 3)` (AC-7, SPEC.md:120-123) проходит и с литералом «3» вместо фактического числа попыток, если тест не подменяет `PUSH_SERVER_RETRY_ATTEMPTS`; верный N для записи успеха держит AC-13, для записи отказа — только при значении константы 3. Мелкое: N отказа равен константе по построению.

## Вердикт
concerns. Факты SPEC о коде подтвердились все; все пять решений Оператора на гейте SPEC №1 перенесены в SPEC (AC-10–AC-14, требование 1(б)); с ТЗ расхождений, которые не снял бы Оператор, нет. Отклонения:

1. SPEC.md:125-127 (AC-8) при требовании 4 SPEC.md:67-75 — критерий не ловит мутацию «запись успеха на каждой отправке после любого прошлого FAILED» (или чтение `last_task_step_of` только по действию FAILED). Предложение Оператору на гейте: дополнить AC-8 сценарием «отказ → успех (запись есть) → ещё успех — новой записи успеха нет».
2. (мелкое) SPEC.md:120-123 (AC-7) — N в детали отказа «сервер» проверяется только при значении константы 3; литерал «3» вместо числа попыток не ловится. На усмотрение Оператора: проверка с подменённой `PUSH_SERVER_RETRY_ATTEMPTS` (требование 6 подмену констант разрешает).
