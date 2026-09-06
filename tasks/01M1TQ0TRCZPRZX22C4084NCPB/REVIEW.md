---
task: 01M1TQ0TRCZPRZX22C4084NCPB
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 5
---

# REVIEW: CI кодовой ветки до ревью: порядок in_dev -> verifying -> review (ADR-0015)

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (порядок состояний; семь рубежей переезжают на `in_dev -> verifying` целиком, без дублирования) | OK | Итерация 2: дубль `_origin_push_gate` в `review()` (был на строках 301-303) убран целиком (коммит `158d9135`); единственная точка вызова теперь `in_dev()` (`orchestrator/fsm_advance.py:1123`), подтверждено `grep -n "_origin_push_gate" orchestrator/fsm_advance.py` — одно определение (171) и один вызов (1123), второй вызов гейта в `fsm_merge_gate.py:319` — легитимный отдельный рубеж approve `merge_gate` (не часть семи переехавших), не дублирование. Регресс-тест `tests/test_auto_cycle.py::AutoStopsWhereTheOperatorIsNeededTest::test_origin_push_check_runs_once_not_twice_on_the_way_to_acceptance` гоняет полный цикл `in_dev -> verifying(зелёный CI) -> review(approved) -> acceptance` со шпионом на `github_adapter.ensure_head_in_origin` и проверяет `call_count == 1` — зелёный. Оба протухших докстринга (`fsm_advance.py:171-184`, `github_adapter.py:114-116`) переписаны под фактическое единственное место вызова. См. R1-F1 в реестре ниже — `accepted`. |
| 2 (`verifying -> review` только по зелёному CI) | OK | `orchestrator/fsm_advance.py:334-336`; `test_ac01_ac09_state_order.py::test_ac9_...`, `test_verifying_ceiling.py::test_green_ci_moves_on_regardless_of_elapsed_time` — зелёные. |
| 3 (`changes_requested` -> `in_dev`; повторный вход в review снова через `verifying`; счётчики без изменений) | OK | `_review_changes_requested` не тронута; `test_ac10_ac12_review_return_cycle.py` (AC-10..12) — зелёные; `test_invariants.CountersNeverResetTest` — зелёный. |
| 4 (ревью-пакет несёт строку статуса CI из журнала `verifying`, без нового опроса) | OK | `orchestrator/review.py:289-296`, `test_ac13_review_package_ci_status_line.py` — зелёный. |
| 5 (`auto`: `verifying` остаётся опрашивающим состоянием; подсказка после красного CI называет `reject` в `in_dev`) | OK | `orchestrator/auto.py` не тронут (обоснованно — `AUTO_STOP_VERIFYING_RED`/`_cmd_reject` уже вели в `in_dev` до этой задачи); `test_ac14_ac16_auto_verifying_loop.py` — зелёный. |
| 6 (`docs/invariants.md`, `docs/roadmap.md`, `artel.py --help`) | OK | Инвариант 36 добавлен, 27/34 поправлены; roadmap — абзац ADR-0015; `artel.py` docstring — новая схема, `cmd_help` печатает именно её (`artel.py:443`). `test_ac17_ac19_docs_state_order.py` — зелёный. |
| 7 (планки закрытых задач не гоняются/не правятся; R2/R3 дождались мержа) | OK | ANSWER-1.md подтверждает мандат Оператора; PLAN честно фиксирует, что реализация шла поверх уже смерженных R2/R3. |

## Замечания

- **major** — `docs/codebase-map.md` (весь файл; последний коммит,
  трогавший его — `158d9135`, `built_at_sha: fc2949235642607b9f68b2e3d47548a8c9957fc4`)
  — карта стухла ПОСЛЕ фикса R1-F1: коммит `d9893cd3` («подтяжка
  main», текущий HEAD кодовой ветки) внёс правки `orchestrator/config.py`,
  `tests/test_capacity_gate.py`, `tests/test_fsm_advance_gate_smoke.py`
  (гейт ёмкости, чужая задача 01M1TT9BPB, пришла подтяжкой), но карту
  не перегенерировал. Проверено запуском `python3 scripts/codebase_map.py`
  (единственный режим — генератор без `--check`, флаг не реализован,
  просто игнорируется: `scripts/codebase_map.py:302-311`, `main()` не
  читает `sys.argv`) — результат РЕАЛЬНО отличается от закоммиченного
  не только строкой `built_at_sha`, но и содержимым (список
  «Импортируется» модуля `orchestrator/config.py` не включает
  `tests/test_capacity_gate.py`, список «Импортирует» одного из модулей
  фазы merge_gate не включает `orchestrator/config.py` — обе строки
  актуальны после `d9893cd3`, но не отражены в закоммиченной карте);
  изменение отброшено `git checkout -- docs/codebase-map.md` после
  проверки, чтобы не оставлять посторонней правки от ревьювера.
  Последствие: CI-джоб `codebase-map` (`.github/workflows/ci.yml:213-249`,
  «карта кодовой базы генерируется и свежа») сверяет закоммиченную карту
  с перегенерированной ПОСИМВОЛЬНО (кроме строки `built_at_sha`) и красит
  сборку (`exit 1`), если они расходятся, — при мерже этой ветки в main
  джоб предсказуемо покраснеет тем же классом, который уже случался
  дважды (T079, T087, оба зафиксированы в conventions-core как
  подтверждённый повторяющийся класс «подтяжка main меняет `*.py`, но не
  через `Edit`, и не регенерирует карту»). PLAN.md, «Итерация 2» и
  «Влияние на систему», заявляет «`codebase_map.py` — пересчитан» —
  верно на момент коммита `158d9135`, но это утверждение больше не
  отражает фактическое состояние ветки после следующего же коммита
  (`d9893cd3`, тот же шаг или следующий).
  Предложение: `python3 scripts/codebase_map.py`, закоммитить
  `docs/codebase-map.md` отдельным или тем же коммитом, каким закрывается
  это замечание; сверить, что после этого `git diff -- docs/codebase-map.md`
  относительно `git show HEAD:...` пуст с точностью до строки
  `built_at_sha` (тем же приёмом, что использует сам CI-джоб).

Итерация 2: новых замечаний класса «дефект в коде задачи» не найдено —
единственное замечание прошлой итерации (R1-F1) проверено и закрыто,
см. «Реестр замечаний» ниже.

Замена места регресс-теста (не `test_ac02_ac08_gates_moved_to_verifying.py`,
как предлагала итерация 1, а новый тест в `tests/test_auto_cycle.py`)
рассмотрена и принята: `test_ac02_ac08_gates_moved_to_verifying.py` —
часть залоченной приёмочной планки задачи
(`tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/`), правка которой
силами developer запрещена conventions-core (SPEC T023, «код чинится
под них, их правка — эскалация, не правка»); PLAN.md, раздел
«Итерация 2», прямо называет эту причину. Новый тест в незалоченной
зоне `tests/` покрывает тот же класс регрессии («рубеж не убран со
старого места после переноса») и фактически прогоняет более длинный
путь (`in_dev -> verifying -> review(approved) -> acceptance`), чем
просил исходный текст замечания — эквивалент принят, доработки не
требую.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm_advance.py:301-303 (дубль, удалён), 1123 (единственное место), 171-184 и orchestrator/github_adapter.py:114-116 (докстринги), tests/test_auto_cycle.py (регресс-тест) | Рубеж «сверка головы на origin» не был убран со старого места в `review()` после переноса в `in_dev()` | Лишний `git push` на каждый approved-вердикт; непредусмотренный путь отказа `review -> acceptance` | Проверено этой итерацией: поиском обоих имён (`_origin_push_gate`, `ensure_head_in_origin`) по `fsm_advance.py`/`fsm_merge_gate.py` — одна точка вызова гейта в `fsm_advance.py` (1123, внутри `in_dev`), старый блок 301-303 отсутствует; оба докстринга переписаны под `in_dev()`; `tests.test_auto_cycle` (42 теста, в т.ч. новый `test_origin_push_check_runs_once_not_twice_on_the_way_to_acceptance`) — зелёные; 20 приёмочных тестов задачи — зелёные. Решение разработчика не расширять залоченный `test_ac02_ac08_gates_moved_to_verifying.py`, а закрыть класс регрессии эквивалентным тестом в незалоченной `tests/test_auto_cycle.py`, принято (см. «Замечания» и PLAN.md «Итерация 2»). Закрыто. |
| R2-F1 | fixed | docs/codebase-map.md (весь файл) | Карта стухла после коммита `d9893cd3` («подтяжка main»): содержимое (не только `built_at_sha`) расходится с перегенерированным `python3 scripts/codebase_map.py` — `orchestrator/config.py`, `tests/test_capacity_gate.py`, `tests/test_fsm_advance_gate_smoke.py` пришли подтяжкой main и не отражены | CI-джоб `codebase-map` (`.github/workflows/ci.yml:213-249`) красит main тем же классом, что уже дважды случался (T079, T087) | Итерация 3: `python3 scripts/codebase_map.py` перегенерирован и закоммичен. Фактическая правка (сверх `built_at_sha`) ровно там, где указал ревьювер: «Импортируется» `orchestrator/config.py` пополнилось `tests/test_capacity_gate.py`, «Импортирует» `orchestrator/fsm_advance.py` пополнилось `orchestrator/config.py`. `tests.test_codebase_map` (21 тест) и 20 приёмочных тестов задачи — зелёные. См. PLAN.md «Итерация 3». |

## Вердикт
changes_requested — единственный пункт: `docs/codebase-map.md` стухла
после коммита `d9893cd3` (см. R2-F1). R1-F1 (блокер итерации 1) закрыт
и подтверждён этой итерацией — реестр несёт по нему `accepted`.
Остальная реализация (переходы, порядок, ревью-пакет, документация,
зоны) проверена итерацией 1 и не менялась с тех пор, кроме мандатной
правки двух строк докстринга `github_adapter.py` (ANSWER-3.md) —
сверено отдельно этой итерацией.

## Проверено исполнением
- `git log --all --oneline --grep=01M1TQ0TRCZPRZX22C4084NCPB` +
  `git show ae216d92`/`git show 158d9135` — восстановлена реальная
  граница «код, проверенный итерацией 1» -> «фикс R1-F1»: пакетный
  инкрементальный diff (sha `d9893cd3`..HEAD) пуст, потому что
  `d9893cd3` («подтяжка main») САМ является текущим HEAD кодовой ветки
  — фактический diff итерации 2 взят вручную как
  `git diff fc294923..d9893cd3` (код, ревьюированный итерацией 1, ->
  текущий HEAD), см. предупреждение скила про ненадёжный sha пакета.
- Чтением кода: `git show 158d9135 --stat` — правка ровно в
  `docs/codebase-map.md`, `orchestrator/fsm_advance.py`,
  `orchestrator/github_adapter.py`, `tests/test_auto_cycle.py`;
  `grep -n "_origin_push_gate\|ensure_head_in_origin" orchestrator/fsm_advance.py orchestrator/fsm_merge_gate.py`
  — ровно одна точка вызова гейта в `fsm_advance.py` (строка 1123,
  внутри `in_dev`), блок 301-303 отсутствует; вызов в
  `fsm_merge_gate.py:319` — отдельный легитимный рубеж (approve
  `merge_gate`), не дублирование семи переехавших.
- `python3 -m unittest tests.test_acceptance_tests_flow tests.test_advance_guard tests.test_amend tests.test_auto_cycle tests.test_branch_freshness_gate tests.test_fsm_map_conflict_autoresolve tests.test_git_fixation tests.test_invariants tests.test_review_freshness tests.test_review_registry_gate tests.test_verifying_ceiling tests.test_github_adapter tests.test_merge_gate_ci_wait` — все зелёные (фоновый прогон, exit 0); `tests.test_auto_cycle` отдельно — 42 теста, зелёные, включая новый регресс-тест `test_origin_push_check_runs_once_not_twice_on_the_way_to_acceptance`.
- `python3 -m unittest test_ac01_ac09_state_order test_ac02_ac08_gates_moved_to_verifying test_ac10_ac12_review_return_cycle test_ac13_review_package_ci_status_line test_ac14_ac16_auto_verifying_loop test_ac17_ac19_docs_state_order test_ac20_ac22_process_markers` (из каталога `acceptance_tests/`) — 20 тестов, все зелёные.
- `python3 scripts/codebase_map.py` (флаг `--check` не реализован, см. R2-F1) — перегенерированная карта РАСХОДИТСЯ с закоммиченной не только строкой `built_at_sha`, но и содержимым (см. R2-F1); регенерация отброшена `git checkout -- docs/codebase-map.md`, рабочее дерево по итогам шага чистое (`git status --short` — только untracked `tasks/01M1TQ0TRCZPRZX22C4084NCPB/`).
- `python3 scripts/guard.py tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md tasks/01M1TQ0TRCZPRZX22C4084NCPB/PLAN.md` — «GUARD: ок (2 файлов)».
- `git diff --stat main...HEAD -- . ':!tasks'` (полный диф ветки вне `tasks/`) — 19 файлов, список сверен с `zones:` SPEC + мандатами ANSWER-2.md (`orchestrator/artel.py`) и ANSWER-3.md (`orchestrator/github_adapter.py`) — расхождений нет; `.git-commit-msg.txt` и `baseline_fsm_advance_tmp.py` в рабочем дереве отсутствуют.
- PLAN.md, раздел «Расширение зон» — оба мандатных пути (`orchestrator/artel.py`, `orchestrator/github_adapter.py`) названы с обоснованием и ссылкой на ANSWER-2/ANSWER-3, соответствует фактическому диффу.

## Предложения системе
- Класс «рубеж не убран со старого места после переноса» (этот файл, R1-F1) — общий риск для задач-рефакторингов маршрута FSM: приёмочный тест, проверяющий «не дублируется на новом переходе», обязан идти ДО состояния, из которого рубеж раньше вызывался, а не только до непосредственно следующего перехода — иначе тест физически не может увидеть код, оставленный на старом месте по пути дальше. Стоит закрепить это как пункт чек-листа review для задач класса «перенос гейта/рубежа между переходами FSM».
- Подтверждён на этой задаче ещё раз класс «инкрементальный sha ревью-пакета ненадёжен после подтяжки main» (уже описан в скиле review-checklist со ссылкой на T087): пакет итерации 2 нёс `d9893cd3` (= текущий HEAD кодовой ветки, коммит «подтяжка main») и как diff, и как файл-стат — оба пустые, хотя фактический фикс R1-F1 (`158d9135`) лежит РАНЬШЕ этого sha в истории. Без ручного восстановления границы по `git log --all --grep=<id>` итерация рисковала бы уйти в «изменений нет, ревью не требуется» — стоит через кавычки в самой сборке пакета (`orchestrator/review.py`?) детектировать случай «sha предыдущего вердикта совпадает с текущим HEAD» отдельно и явно предупреждать в шапке пакета, а не только полагаться на память ревьювера про этот пункт скила.
