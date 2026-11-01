---
task: 01M6AB4VE2R0Q2V5D4MMJGNGH7
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/forge.py, orchestrator/gitlab_adapter.py, orchestrator/mr_sync.py, orchestrator/artel.py, orchestrator/fsm.py, orchestrator/fsm_merge_gate.py, orchestrator/cleanup.py, orchestrator/snapshot.py, orchestrator/retro.py, orchestrator/schema.py, orchestrator/store.py, orchestrator/targets.py, orchestrator/auto.py, orchestrator/catalog.py, orchestrator/board.py, orchestrator/watch.py, tests/
merge_after: 01M5XZ9Z68XE2EKPDHYCAK25KF
budget_usd: 50
---

# SPEC: Б2.2 — команда `mr-sync`: сверка MR и нахождения правки в `base`, закрытие `done` по подтверждению Оператора

## Контекст
ADR-0029 (принят 26.10.2026), п. 2, 3, 10. После Б2.1б (01M5XZ9Z68XE2EKPDHYCAK25KF)
гейт мержа проекта с `merge_gate: target-human` открывает MR через `forge`
и переводит задачу в `awaiting_human` (`fsm_merge_gate._approve_for_project_people`,
`fsm_merge_gate.py:1576`); дальше задачу не двигает ничто: `approve`/`reject`/
`answer`/`amend-tests` в `awaiting_human` отказывают подсказкой
`fsm.AWAITING_HUMAN_HINT` «состояние ждёт людей проекта — mr-sync (шаг Б2.2)»
(`fsm.py:43`; подсказка состояния в `status` — `config.py:941-943`). Людям
проекта MR могут влить, закрыть, перенести правку в другую ветку или влить
сжатием вместе с чужой правкой — пульт обязан проверять фактическое
нахождение правки в `base`, а не только статус MR (решение Оператора
26.10.2026 в ADR-0029).

Сегодня `forge.MergeRequest` (`forge.py:67`) несёт только `iid, url, title,
state, draft, assignee, reason`; GitLab заполняет его в
`gitlab_adapter._merge_request` (`gitlab_adapter.py:497`), `mr_status` —
`gitlab_adapter.py:545`. `closed_as` знает только `divided` (`schema.py:244`).
Путь `done` гейта мержа — `fsm_merge_gate.py:1549-1552`:
`_finalize_done_state` (`:1337`, `state -> done` и снятие lease) →
`cleanup._commit_closing` (`cleanup.py:736`) → `snapshot.commit_closing`
(`snapshot.py:96`) → `retro.build_done` (`retro.py:551`, строка «Итог: done,
sha …») → `_cleanup_merged_task` (`:1367`, рабочая копия, локальная ветка и
ветка на сервере). Зоны освобождаются по терминальному состоянию
(`zone_lock.py:111-116`), зависимости `merge_after` — по `done`. Последняя
своя отправка ветки — `gitcmd.last_sent_sha` (`gitcmd.py:233`). Поля доставки
читаются `targets.delivery_policy` (`targets.py:559`). `target-human` до Б2.3
неподдержан: в тестах — подменой `targets.SUPPORTED_MERGE_GATES`/
`SUPPORTED_FORGES`.

## Требования

1. **Поля `forge.MergeRequest`**: добавлены `target_branch`, `source_branch`,
   `sha` (голова MR), `merge_commit_sha`, `squash_commit_sha`, все `None` по
   умолчанию. `gitlab_adapter._merge_request` заполняет их из одноимённых
   полей ответа MR GitLab; поля нет в ответе — `None`. Прочие вызовы `forge`
   и белый список API (`ALLOWED_PAIRS`) не меняются.

2. **Команда `mr-sync [<id>…]`** — новый модуль `orchestrator/mr_sync.py`,
   регистрация и справка в `orchestrator/artel.py`.
   - Без id — все задачи проектов с `merge_gate: target-human` в
     `awaiting_human`; задачи прочих проектов и прочих состояний не
     сверяются. С id — только названные; задача не найдена, не в
     `awaiting_human` или её проект не `target-human` — отказ с причиной по
     этой задаче.
   - Только чтение: `fetch` базовой ветки в клон пульта и
     `forge.mr_status`; команда ничего не отправляет, MR и ветку не меняет.
   - По каждой задаче печатает и пишет в журнал задачи:
     - статус MR: открыт / влит / закрыт без вливания / не найден /
       переведён на другую целевую ветку (`target_branch` MR не равен
       `base` записи проекта);
     - признаки нахождения правки в `origin/<base>` от подтверждённой
       головы (sha `approve` на `merge_gate` из журнала задачи):
       - (а) коммит вливания — `merge_commit_sha`, иначе
         `squash_commit_sha`, иначе `sha` MR (метод без коммита слияния) —
         предок головы `origin/<base>`;
       - (б) все коммиты задачи найдены в базе по содержимому
         (`git cherry origin/<base> <голова> <точка ответвления>`, без
         merge-коммитов);
       - (в) обратное наложение диффа задачи от точки ответвления на
         `origin/<base>` проходит (`git apply --check -R --binary
         --whitespace=nowarn`), а прямое — нет; доказательство печатается
         по файлам;
     - итог, ровно один:
       - «влит этим MR» — признак (а); при (а) и провале (в) — с пометкой
         «после вливания файлы менялись»;
       - «в базе, влит иначе» — (а) нет, MR закрыт или открыт, правка в
         базе по (б) или по (в);
       - «в базе частично» — часть коммитов задачи найдена по (б), (в) не
         проходит;
       - «нет в базе» — ни одного признака;
       - «MR не найден»;
       - «MR переведён на другую ветку»;
       - «неизвестно» с причиной — любой отказ `forge` или git; такой итог
         не зелёный и закрытия не допускает.
   - Последний итог и время сверки сохраняются у задачи (БД,
     `schema.py`/`store.py`).

3. **Закрытие `mr-sync <id> --confirm`** — только для одной задачи (больше
   одного id или без id — отказ) и только при итоге «влит этим MR» или «в
   базе, влит иначе». Итог «в базе, влит иначе», полученный лишь по признаку
   (в), требует `--confirm --by-content`; без `--by-content` — отказ.
   - Итог пересчитывается в момент `--confirm` той же сверкой требования 2,
     а не берётся из прошлого запуска.
   - Успех: переход `awaiting_human → done`; `closed_as` =
     `merged_upstream` (итог по (а)) или `merged_upstream_other` (по (б)/(в));
     константы рядом с `schema.CLOSED_AS_DIVIDED`.
   - Коммит закрытия с RETRO в `refs/artifacts/<id>` — тем же путём, что
     `done` гейта мержа (`cleanup._commit_closing` → `snapshot.commit_closing`),
     с sha из доказательства: по (а) — коммит вливания; по (б) — найденный в
     базе коммит; по (в) — голова `origin/<base>` с пометкой «по содержимому»
     в RETRO.
   - Рабочая копия задачи убирается; ветка задачи на сервере и MR не
     трогаются (ни отправки в ветку, ни её удаления, ни вызовов `forge`,
     меняющих MR); lease снимается, как в `_finalize_done_state`; зоны
     освобождаются; задачи, зависящие от этой по `merge_after`, продолжают.
   - Прочие итоги — отказ `--confirm` с итогом и подсказкой (`kill`, новая
     задача, ожидание); задача остаётся в `awaiting_human`.

4. **Инциденты** (ADR-0029 п. 3):
   - MR задачи (ссылка `mr_iid` в БД) влит или закрыт до перехода в
     `awaiting_human` — проверка на `approve` гейта мержа
     (`fsm_merge_gate.py`) — эскалация задачи, MR не снимается с черновика и
     не назначается.
   - Голова ветки задачи на сервере не совпадает с последней своей отправкой
     (`gitcmd.last_sent_sha`; чужой коммит) — эскалация без перезаписи
     ветки; проверяют `mr-sync` (в том числе без `--confirm`) и `approve` на
     `merge_gate`.
   - Эскалация из `awaiting_human` возвращается в `awaiting_human` (механика
     Б2.1а).

5. **Опрос по расписанию — поле `policy.mr_sync_interval_min`** записи
   проекта (`targets.py`: только это поле и его проверка). Целое > 0; по
   умолчанию поля нет — опрос выключен, только ручной `mr-sync`; `0`,
   отрицательное, не целое — отказ загрузки с именем поля. При заданном
   значении надзор `auto` и надзор эпика (`orchestrator/auto.py`) раз в N
   минут вызывают `mr-sync` без `--confirm` для задач проекта в
   `awaiting_human` и пишут итог в журнал; при смене итога задачи
   относительно прошлой сверки — уведомление `watch` (`orchestrator/watch.py`).
   `--confirm` надзор не вызывает никогда.

6. **Показ**: `status` (`catalog.py`) и доска (`board.py`) у задачи в
   `awaiting_human` показывают последний итог `mr-sync` и время сверки.
   Подсказка состояния из Б2.1а — без «(шаг Б2.2)»: `fsm.AWAITING_HUMAN_HINT`
   (`fsm.py:43`) и подсказка `awaiting_human` в `config.py:941-943`.

7. **Инварианты** — приложением PLAN к `tests/test_invariants.py`
   (защищённый путь): `mr-sync` входит в обход команд
   (`commands()`, `tests/test_invariants.py:400`); тест свойства строки 18
   (`docs/invariants.md:48`): `mr-sync --confirm` — команда Оператора, `auto`
   (и надзор эпика) её не вызывает.

## Критерии приёмки
Поддержка `target-human` — подменой `targets.SUPPORTED_MERGE_GATES`/
`SUPPORTED_FORGES` в тесте; песочницы — вымышленные проекты с локальным
`origin`.

AC-1. Подменённый ответ GitLab на `GET /projects/:id/merge_requests/:n` с
`target_branch`, `source_branch`, `sha`, `merge_commit_sha`,
`squash_commit_sha` → одноимённые поля `forge.MergeRequest` из
`gitlab_adapter.mr_status` заполнены этими значениями; ответ без них — поля
`None`.

AC-2. `mr-sync` без id сверяет все задачи проектов с `target-human` в
`awaiting_human` и не сверяет задачи проекта с `operator` и задачи в других
состояниях; `mr-sync <id>` по задаче не в `awaiting_human` или проекта не
`target-human` — отказ с причиной.

AC-3. Итог «влит этим MR»: коммит вливания — предок `origin/<base>` →
признак (а) в выводе и журнале; `mr-sync <id> --confirm` переводит задачу в
`done`, `closed_as=merged_upstream`, коммит закрытия в `refs/artifacts/<id>`
несёт RETRO с sha коммита вливания, рабочая копия задачи убрана; шпион не
видит ни отправки в ветку задачи, ни удаления ветки на сервере, ни вызовов
`forge`, меняющих MR.

AC-4. Пометка «после вливания файлы менялись»: (а) есть, правка задачи затем
изменена в `base` (обратное наложение не проходит) → итог «влит этим MR» с
пометкой в выводе.

AC-5. MR закрыт, коммиты задачи перенесены в другую ветку и влиты в `base` →
признак (б), итог «в базе, влит иначе»; `--confirm` → `done`,
`closed_as=merged_upstream_other`, sha закрытия — найденный в базе коммит.

AC-6. MR закрыт, правка влита сжатием вместе с другой правкой → только
признак (в) с доказательством по файлам; `--confirm` без `--by-content` —
отказ, задача в `awaiting_human`; `--confirm --by-content` — `done`,
`closed_as=merged_upstream_other`, sha в RETRO — голова `origin/<base>`,
пометка «по содержимому».

AC-7. Итоги «в базе частично», «нет в базе», «MR не найден», «MR переведён на
другую ветку» (`target_branch` ≠ `base`) и отказ `forge` (итог «неизвестно» с
причиной) печатаются каждый своим текстом; `--confirm` при каждом из них
отказывает с итогом и подсказкой, задача в `awaiting_human`.

AC-8. Итог пересчитывается на `--confirm`: прошлый запуск `mr-sync` дал «влит
этим MR», затем ответ `forge` или `origin/<base>` изменён так, что итог —
«нет в базе», → `--confirm` отказывает, задача в `awaiting_human`.
`mr-sync --confirm` с двумя id или без id — отказ, ни одна задача не
закрыта.

AC-9. После успешного `--confirm` зона задачи свободна (задача той же зоны
не ждёт её), а задача с `merge_after` на закрытую больше ею не держится.

AC-10. Инцидент «MR влит до `awaiting_human`»: у задачи на `merge_gate` есть
`mr_iid`, подменённый `forge.mr_status` отвечает «влит» (или «закрыт») →
`approve` эскалирует задачу, `undraft_mr`/`assign_mr` не званы, задача не в
`awaiting_human`.

AC-11. Инцидент «чужой коммит»: голова ветки на сервере не равна
`gitcmd.last_sent_sha` → `mr-sync` и `approve` на `merge_gate` эскалируют
задачу, шпион не видит отправки ветки; после `answer` + `approve` задача
снова в `awaiting_human`.

AC-12. `mr-sync` без `--confirm` (без инцидента) ничего не меняет в БД, кроме
записей журнала и последнего итога со временем сверки: снимок строки задачи
до и после отличается только этими полями.

AC-13. `policy.mr_sync_interval_min`: без поля надзор `auto` и надзор эпика
`mr-sync` не вызывают; с полем — вызывают только без `--confirm` и не чаще
раза в N минут (подменённые часы); шпион не видит `--confirm` от надзора ни
при каком итоге, включая «влит этим MR»; значения `0`, отрицательное, не
целое — отказ загрузки записи с именем поля.

AC-14. Опрос надзора сменил итог задачи (например «нет в базе» → «влит этим
MR») → `watch` показывает уведомление о смене; повторная сверка с тем же
итогом нового уведомления не даёт.

AC-15. `status` и доска у задачи в `awaiting_human` после `mr-sync`
показывают последний итог и время сверки; подсказка `awaiting_human` в
`status` и отказ `approve`/`reject`/`answer`/`amend-tests` не содержат
«(шаг Б2.2)» и называют `mr-sync`.

AC-16. PLAN несёт приложение к `tests/test_invariants.py`, которое
применяется к `base` (`git apply --check`), добавляет `mr-sync` в обход
команд и тест «`auto` и надзор эпика не вызывают `mr-sync --confirm`».

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны ≥ 5 (16 модулей `orchestrator/`);
критериев приёмки ≥ 10 (16); `budget_usd` ≥ $30 ($50 — рамка ТЗ); зона
задевает механизмы записей `docs/invariants.md` (переходы FSM, гейт мержа,
строка 18 — `auto` не проходит гейты, `tests/test_invariants.py`).

Материал для решения Оператора — **обоснование монолита**: ТЗ уже шаг Б2.2
плана ADR-0029 с рамкой $50. Сердце задачи — одна сверка (требование 2),
которой пользуются и ручной `mr-sync`, и `--confirm` (пересчёт в момент
подтверждения, AC-8), и опрос надзора, и проверка чужого коммита; закрытие
без сверки не мержимо (нечем решать), сверка без закрытия оставляет
`awaiting_human` тупиком, как сейчас. Возможный разрез по зонам, если
Оператор его предпочтёт: (1) поля `forge.MergeRequest`, `mr_sync.py` только
на чтение, хранение и показ итога, подсказка без «(шаг Б2.2)» (AC-1, AC-2,
AC-4, AC-7 без `--confirm`, AC-12, AC-15) — первой, без зависимостей; (2)
`--confirm` и путь `done` (`fsm.py`, `cleanup.py`, `snapshot.py`,
`retro.py`, `schema.py`), инциденты на `approve` (`fsm_merge_gate.py`),
опрос (`targets.py`, `auto.py`, `watch.py`) и приложение к инвариантам
(AC-3, AC-5, AC-6, AC-8–AC-11, AC-13, AC-14, AC-16) — после части 1.
Калибровка для >15 критериев — ~$85; потолок держит рамка ТЗ $50.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Новый путь в `done`: `awaiting_human → done` по `mr-sync --confirm` | `done` только по `approve` на `merge_gate` — `tests/test_invariants.py:1740` (`test_operator_approve_passes_each_gate`), инвариант 18 (`docs/invariants.md:48`) | остаётся: новый путь — команда Оператора с пересчётом итога, `auto` её не вызывает | AC-3, AC-8, AC-13, AC-16 | по ADR-0029 п. 3, 10 |
| Закрытие без мержа пультом: коммит закрытия с sha доказательства, а не коммита мержа пульта | RETRO «Итог: done, sha …» — sha мержа пульта, `retro.py:571`, `fsm_merge_gate.py:1550` | остаётся (тот же путь коммита закрытия), sha — из доказательства, по (в) с пометкой «по содержимому» | AC-3, AC-5, AC-6 | по ТЗ |
| Уборка при `--confirm`: ветка на сервере не удаляется | `_cleanup_merged_task` удаляет ветку на сервере — `fsm_merge_gate.py:1367-1380` | для `--confirm` — нет (ветку и MR ведут люди проекта); для `operator` без изменений | AC-3 | по ТЗ |
| Подсказка `awaiting_human` без «(шаг Б2.2)»: константа `HINT` `tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_commands.py:24` | `assert HINT in out` — `tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_commands.py:94` | остаётся: отказ четырёх команд с подсказкой `mr-sync`, проверка `mr-sync` в выводе (`:135`) не меняется | тот же тест с новой строкой подсказки; AC-15 | мандат Оператора 26.10 (ТЗ) — строку мандата вписывает Оператор на гейте SPEC |
| Новые эскалации на `approve` `merge_gate` и в `mr-sync` | Сверка подтверждённого sha с головой на сервере — Б2.1б (`fsm_merge_gate.py:1576`) | остаётся, строже (добавлены сверка с последней своей отправкой и статус MR до `awaiting_human`) | AC-10, AC-11 | ок |

## Не входит

- Профиль `verify`, `verify-ok`/`verify-fail` (В2).
- Хук `pre-push`, строки `doctor`, открытие `targets.SUPPORTED_FORGES`/
  `SUPPORTED_MERGE_GATES` в коде (Б2.3).
- Вариант с веб-хуком хостинга (бэклог, после переезда пульта на сервер).
- Правка файлов только для чтения: `orchestrator/gitcmd.py`,
  `orchestrator/zone_lock.py`, `orchestrator/merge_after.py`,
  `docs/adr/0029-external-delivery-via-mr.md`, `docs/adr/0028-*.md`.
- Правка строки 18 `docs/invariants.md` (защищённый путь) — ТЗ называет
  приложением только `tests/test_invariants.py`.
- Изменение `forge` сверх полей `MergeRequest`: новые вызовы API и белый
  список не меняются.
- «Проекты с `operator` и артель: поведение и существующие тесты прежние» —
  отдельного критерия нет: полный зелёный `tests/` и неизменность
  существующих ожиданий держит пульт (гейт неослабления); единственная
  правка существующего теста — константа `HINT` по мандату (матрица выше).

## Материалы

- ТЗ `tasks/01M6AB4VE2R0Q2V5D4MMJGNGH7/TZ.md`; ADR-0029 п. 2, 3, 10.
- SPEC Б2.1а (01M5XZ9Z68V75VXF5Z66C708T4) и Б2.1б (01M5XZ9Z68XE2EKPDHYCAK25KF).
- Путь `done` гейта мержа: `fsm_merge_gate.py:1337`, `:1367`, `:1549-1552`;
  `cleanup.py:718` (`_closing_outcome` читает состояние из БД), `:736`;
  `snapshot.py:96`; `retro.py:551`.
- Подсказка «(шаг Б2.2)»: `fsm.py:43` (используют `fsm.py:1793`, `:1861`,
  `answer.py:397`, `amend.py:846` — меняется только константа), `config.py:942`.
- Константа `HINT` теста — модульное имя, а не литерал утверждения, поэтому
  смена оформлена матрицей и мандатом, не разделом «Меняемое поведение».
- Обход команд инвариантов — `tests/test_invariants.py:400`; тест строки 18 —
  `tests/test_auto_cycle.py:1163` (`AutoNeverPassesAGateTest`).
