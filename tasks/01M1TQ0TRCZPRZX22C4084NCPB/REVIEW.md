---
task: 01M1TQ0TRCZPRZX22C4084NCPB
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 5
---

# REVIEW: CI кодовой ветки до ревью: порядок in_dev -> verifying -> review (ADR-0015)

## Соответствие SPEC

Код не менялся с момента одобренного REVIEW.md итерации 3 (`bc331947`)
— `git diff bc331947..a29e0782` (текущий HEAD) трогает только
`docs/adr/0010-stop-loss-as-milestone.md`, `docs/backlog.md`,
`docs/roadmap.md` (третья подтяжка main + сведение конфликта
Оператором, `*.py` не затронуты). Инкрементальный пакетный diff (от
sha предыдущего вердикта `a29e0782` до HEAD `a29e0782`) пуст, потому
что предыдущий вердикт (итерация 3) уже стоит на этом самом коммите —
это не «нет работы с итерации 3», а «код не менялся, но приёмка
вернула шаг на доработку PLAN.md (AC-20/AC-22) и затем случился
конфликт подтяжки main, сведённый Оператором»: обе причины возврата
закрыты правками, не тронувшими код (см. PLAN.md «Итерация 4» и
«Итерация 5»). Таблица ниже — переподтверждение итерации 3 плюс
точечная проверка того, что изменилось (PLAN.md, docs после сведения
конфликта).

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (порядок состояний; семь рубежей переезжают на `in_dev -> verifying` целиком, без дублирования) | OK | Без изменений с итерации 3. `grep -n "_origin_push_gate\|ensure_head_in_origin" orchestrator/fsm_advance.py orchestrator/fsm_merge_gate.py` — одна точка вызова гейта (`in_dev`), второй вызов — легитимный отдельный рубеж `merge_gate`. |
| 2 (`verifying -> review` только по зелёному CI) | OK | Без изменений. `test_ac01_ac09_state_order.py`, `test_verifying_ceiling.py` — зелёные (прогнано этой итерацией). |
| 3 (`changes_requested` -> `in_dev`; повторный вход в review снова через `verifying`; счётчики без изменений) | OK | Без изменений. `test_ac10_ac12_review_return_cycle.py`, `tests.test_invariants.CountersNeverResetTest` — зелёные. |
| 4 (ревью-пакет несёт строку статуса CI из журнала `verifying`, без нового опроса) | OK | Без изменений. `orchestrator/review.py:289-296`, `test_ac13_review_package_ci_status_line.py` — зелёный. |
| 5 (`auto`: `verifying` остаётся опрашивающим состоянием; подсказка после красного CI называет `reject` в `in_dev`) | OK | Без изменений. `test_ac14_ac16_auto_verifying_loop.py` — зелёный. |
| 6 (`docs/invariants.md`, `docs/roadmap.md`, `artel.py --help`) | OK | Перепроверено ПОСЛЕ сведения конфликта подтяжки main (`a29e0782`): `docs/invariants.md:54,61,63` (инварианты 27/34/36) и `docs/roadmap.md:75-82` по-прежнему называют новый порядок; историческая строка «Фиксация К3» (`docs/roadmap.md:216`, старый маршрут `in_dev -> review`) не тронута умышленно — протокол прошлого прогона, не текущая механика (то же самое, что подтвердила итерация 3). `orchestrator/artel.py:8-19` — докстринг схемы состояний под новый порядок. `test_ac17_ac19_docs_state_order.py` — зелёный. |
| 7 (планки закрытых задач не гоняются/не правятся; R2/R3 дождались мержа; AC-22 — живые задачи со старым порядком эскалированы списком, не правятся) | OK | AC-22 в PLAN.md (итерация 4) перечисляет три живые задачи с точными адресами (файл:строки). Перепроверено этой итерацией: `git merge-base --is-ancestor artifact/<id> main` — все три НЕ являются предками main (живые, не `done`); `git grep -n "in_dev -> review" artifact/<id> -- tasks/<ID>/acceptance_tests` для каждой из трёх — точное совпадение количества мест и номеров строк с PLAN.md (6/5/2 соответственно, включая `01m1r5b33cc7e6bzk085xv3zcx` — 6 строк 6,12,43,93,118,202; `01m1thkwfxfynw28hdjgyhqwh6` — 5 мест; `01m1tnmby8g3ah3mycb07rw14n` — 2 места). Ни один из файлов не тронут этой задачей (подтверждено diff-статом). |

Дополнительно перепроверено AC-20 (причина предыдущего возврата приёмки
— недостаточное обоснование по каждому файлу): выборочно сверены с
кодом 5 из 11 пунктов PLAN.md — `tests/test_verifying_ceiling.py:105-118`
(докстринг теста явно ссылается на AC-20 и ADR-0015, целевое состояние
`review` совпадает), `tests/test_advance_guard.py:92-98,285`
(`TRANSITIONS["in_dev"]` ведёт в `"verifying"`, ассерт после `review`
проверяет `"acceptance"` — совпадает), `tests/test_review_registry_gate.py:84,108`
(целевые состояния `"acceptance"` — совпадает), `tests/test_fsm_map_conflict_autoresolve.py:275,289-292`
(`self.state() == "verifying"`, `acc_run.call_count == 2`,
`call_args_list[0][0][0]` — совпадает), `tests/test_review_freshness.py`
(хелпер переименован в `back_to_review_after_acceptance_reject`,
класс `FreshVerdictGuardsAcceptanceTest` в `test_invariants.py`
существует под этим именем) — расхождений с заявленным в PLAN.md нет.

## Замечания

Итерация 4: новых замечаний класса «дефект в коде задачи» не найдено.
Код не менялся с итерации 3 (единственного одобренного прогона с
кодовыми изменениями); эта итерация закрывает причины возврата
приёмки (AC-20/AC-22 документация в PLAN.md — «Итерация 4»; сведение
конфликта подтяжки main Оператором — «Итерация 5»), обе — без изменений
кода, обе перепроверены выше и подтверждены соответствующими фактическому
состоянию репозитория.

Реестр замечаний прошлых итераций (R1-F1, R2-F1) закрыт `accepted`
итерацией 3 — новых открытий по нему нет, повторно не переношу
(восстановимо из git-истории файла REVIEW.md, правило скила).

## Реестр замечаний

Открытых записей нет. R1-F1 и R2-F1 — `accepted` с итерации 3, новых
записей эта итерация не заводит.

## Вердикт
approved — код идентичен коду, одобренному итерацией 3 (все 22 AC
SPEC проверены тогда и переподтверждены точечно сейчас); обе причины
возврата приёмки (документация AC-20/AC-22, конфликт подтяжки main)
закрыты без изменений кода и обе перепроверены самостоятельно (не на
слово PLAN.md) — расхождений не найдено.

## Проверено исполнением
- `git diff bc331947..a29e0782 --stat` — только `docs/adr/0010-stop-loss-as-milestone.md`, `docs/backlog.md`, `docs/roadmap.md`; `*.py` не затронуты с момента кода, одобренного итерацией 3.
- `python3 -m unittest` в каталоге `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests`: `test_ac01_ac09_state_order test_ac02_ac08_gates_moved_to_verifying test_ac10_ac12_review_return_cycle test_ac13_review_package_ci_status_line test_ac14_ac16_auto_verifying_loop test_ac17_ac19_docs_state_order test_ac20_ac22_process_markers` — 20 тестов, все зелёные.
- `python3 -m unittest tests.test_acceptance_tests_flow tests.test_advance_guard tests.test_amend tests.test_auto_cycle tests.test_branch_freshness_gate tests.test_fsm_map_conflict_autoresolve tests.test_git_fixation tests.test_invariants tests.test_review_freshness tests.test_review_registry_gate tests.test_verifying_ceiling tests.test_github_adapter tests.test_merge_gate_ci_wait tests.test_codebase_map` — 316 тестов, все зелёные (~174с).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` (исключая строку `built_at_sha`) — пусто, карта актуальна; изменение отброшено `git checkout -- docs/codebase-map.md`.
- `python3 scripts/guard.py tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md tasks/01M1TQ0TRCZPRZX22C4084NCPB/PLAN.md` — «GUARD: ок (2 файлов)».
- `grep -n "in_dev\|verifying\|review\|acceptance\|merge_gate" docs/roadmap.md` и чтение `docs/invariants.md:50-65`, `orchestrator/artel.py:1-30` — новый порядок состояний по-прежнему отражён после сведения конфликта подтяжки main Оператором (`a29e0782`).
- `git merge-base --is-ancestor artifact/<id> main` для трёх задач AC-22 (`01m1r5b33cc7e6bzk085xv3zcx`, `01m1thkwfxfynw28hdjgyhqwh6`, `01m1tnmby8g3ah3mycb07rw14n`) — все три живые (не предки main); `git grep -n "in_dev -> review" artifact/<id> -- tasks/<ID>/acceptance_tests` для каждой — точное совпадение с перечнем PLAN.md (места и номера строк), файлы не тронуты этой задачей.
- Выборочная сверка 5 из 11 пунктов AC-20 PLAN.md с фактическим содержимым тестовых файлов (`tests/test_verifying_ceiling.py`, `tests/test_advance_guard.py`, `tests/test_review_registry_gate.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_review_freshness.py`, `tests/test_invariants.py`) — расхождений с заявленным нет.
- Полный набор `tests/` не прогонялся в этом шаге (гоняется CI на каждый пуш, решение Оператора 05.09) — покрыт целевыми модулями зоны и приёмочной планкой задачи, оба зелёные.

## Предложения системе
