---
task: 01M1RA0N6FCFEQBB82K58GM12X
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 4
---

# REVIEW: Гейт ёмкости diff не считает артефакты задачи в кодовой ветке

## Соответствие SPEC

Ревью-пакет этой итерации несёт инкрементальный diff «от sha предыдущего
вердикта (`4a4598b9`) до HEAD (`9be518db`)» — этот diff НЕ отражает
работу этой задачи: единственный коммит между ними —
`01M1RA0N6FCFEQBB82K58GM12X: подтяжка main`, слияние main в ветку
задачи, а сам main в это окно получил слияния двух ДРУГИХ задач
(`01M1REVJ8AJDKAMK5VTKES5J6D` — zone_lock, `01M1RDCAFENSW2VVAPECHCVGMM`
— stack.py) и один одиночный коммит Оператора в `docs/backlog.md`.
Отсюда весь объём пакета (`orchestrator/zone_lock.py`,
`orchestrator/stack.py`, `tests/test_stack.py`,
`tests/test_zone_lock.py`, большая часть `docs/*`) — шум чужих задач,
затянутый подтяжкой, а не код этой задачи (тот же класс, что уже описан
в skill review-checklist, «Инкрементальный diff пакета — пустой не
значит без изменений», только здесь наоборот: diff непустой, но
полностью посторонний). Проверено: `git diff
4a4598b9...HEAD -- orchestrator/fsm_advance.py orchestrator/review.py
tests/test_capacity_gate.py tests/test_review_package.py` — 0 строк,
файлы этой задачи побайтово те же, что на момент предыдущего вердикта.

Настоящая работа этой задачи видна только трёхточечным диффом
`git diff main...HEAD` (относительно merge-base, `a94caf61`):
`docs/codebase-map.md`, `orchestrator/fsm_advance.py`,
`orchestrator/review.py`, `tests/test_capacity_gate.py`,
`tests/test_review_package.py` — 5 файлов, ровно зона SPEC
(`orchestrator/fsm_advance.py, orchestrator/review.py, tests/`) плюс
регенерация карты (обязательна при правке `*.py`, конвенция
conventions-core). Это тот же самый код, что получил `changes_requested`
в итерациях 1-3 (коммит `d8879975`), ПЛЮС фикс R1-F1 (коммит `4a4598b9`,
`01M1RA0N6FCFEQBB82K58GM12X: R1-F1 — вторая цифра гейта ёмкости не
путает пустой diff артефактов с плейсхолдером»), сделанный
разработчиком между итерацией 3 и этим шагом (артефактная ветка,
db0a9d0d, регистр R1-F1 → `fixed`).

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (гейт ёмкости исключает `tasks/<id>/`, порог не меняется) | OK | `_capacity_gate_refuses` меряет `code_diff` через `pathspec=(".", f":!{tasks_prefix}")` (`orchestrator/fsm_advance.py:471-472`), `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES` не тронут. AC-1/AC-4/AC-5 планки зелёные. |
| 2 (diff ревью-пакета, полный и инкрементальный, не несёт `tasks/<id>/`) | OK | `review_package` зовёт `git_diff_part` с исключающим pathspec `tasks_dir_exclude = (".", f":!tasks/{task_id}/")` для `--stat` и diff (`orchestrator/review.py:246-249`). AC-2/AC-6 планки зелёные, `tests/test_review_package.py` зелёные. |
| 3 (отказ называет обе цифры — код и исключённые артефакты) | OK | R1-F1 исправлен: плейсхолдер `git_diff_part` вынесен в именованную константу `review.EMPTY_DIFF_TEXT` (`orchestrator/review.py:13`), `_capacity_gate_refuses` сравнивает `code_diff`/`artifacts_diff` с этой константой ДО подсчёта байт (`orchestrator/fsm_advance.py:484`, `:492`) и печатает `«0 байт (изменений нет)»`, когда diff артефактов реально пуст, вместо байтового размера строки-плейсхолдера. Воспроизведено заново на текущем HEAD (см. «Проверено исполнением») — дефект R1-F1 больше не наблюдается. |

## Замечания

- minor — `tests/test_capacity_gate.py:94-193` (класс `CapacityGateTwoNumbersMessageTest`) и `tests/test_review_package.py:1254-1284` (класс `GitDiffPartPathspecTest`) — три новых теста без докстринга вовсе (`CapacityGateTwoNumbersMessageTest.test_refusal_message_names_code_size_and_artifacts_size_separately`, `GitDiffPartPathspecTest.test_no_pathspec_leaves_the_call_unchanged`, `GitDiffPartPathspecTest.test_pathspec_is_appended_after_a_double_dash`) и два теста с докстрингом, который хорошо описывает сценарий/наблюдаемое свойство, но не несёт литеральной заявки `Ловит мутацию: …` (`test_empty_artifacts_diff_reports_zero_bytes_not_placeholder_size`, `test_artifacts_diff_failure_does_not_invent_a_number`) — конвенция test-authoring (skill review-checklist, п. «Тесты») требует явную заявку в докстринге у каждого нового/изменённого теста, чтобы ревью сверяло тест с ней, а не мысленным мутационным тестом по наитию. Содержательно тесты корректны и не слепы к мутации (проверено запуском: все пять реально ловят соответствующий дефект/поведение — см. «Проверено исполнением»), поэтому не блокирует вердикт; предложение — дописать докстринги с явной заявкой `Ловит мутацию: …` при следующей правке этих файлов. (Тот же класс уже отмечен в памяти как повторяющийся паттерн — просадка конвенции конкретно в `tests/*.py`, не в `acceptance_tests/`.)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm_advance.py:484-499 | вторая цифра отказа гейта — байтовый размер плейсхолдера «(изменений нет)» (27), а не 0, когда diff `tasks/<id>/` реально пуст | Оператор на мосту видел вымышленный ненулевой размер «исключённых артефактов» там, где артефакты вовсе не менялись | Проверено на текущем HEAD: `review.EMPTY_DIFF_TEXT` — именованная константа, `_capacity_gate_refuses` сравнивает с ней ДО подсчёта байт (`code_size`/`artifacts_note`), сообщение при пустом diff артефактов — `«0 байт (изменений нет)»`. Регрессия закрыта дословно предложенным способом плюс отдельный юнит-тест `tests/test_capacity_gate.py::CapacityGateTwoNumbersMessageTest::test_empty_artifacts_diff_reports_zero_bytes_not_placeholder_size`, воспроизводящий именно этот (ранее не покрытый планкой AC-3) сценарий. Прогнано мной независимо — фиксирую `accepted`. |

## Вердикт

approved — R1-F1 закрыт, все три требования SPEC реализованы и
подтверждены тестами; регистр замечаний целиком `accepted`. Единственное
новое наблюдение (минорное, докстринги новых тестов без явной заявки
«Ловит мутацию») не блокирует — тесты содержательно корректны, см.
«Замечания».

## Проверено исполнением

- `git merge-base main task/01m1ra0n6fcfeqbb82k58gm12x-geyt-yomkosti-diff-ne-schitaet` → `a94caf61`; `git diff main...HEAD --stat` — 5 файлов (`docs/codebase-map.md`, `orchestrator/fsm_advance.py`, `orchestrator/review.py`, `tests/test_capacity_gate.py`, `tests/test_review_package.py`), ровно зона SPEC + регенерация карты.
- `git diff 4a4598b9...HEAD -- orchestrator/fsm_advance.py orchestrator/review.py tests/test_capacity_gate.py tests/test_review_package.py` — 0 строк: код задачи не менялся со времени предыдущего вердикта, весь объём инкрементального пакета — слияние main (две другие задачи).
- `python3 -m unittest tests.test_capacity_gate tests.test_review_package -v` — 97 тестов, все зелёные (включая новый `test_empty_artifacts_diff_reports_zero_bytes_not_placeholder_size`).
- `python3 -m unittest discover -s tasks/01M1RA0N6FCFEQBB82K58GM12X/acceptance_tests -v` — 6 тестов (AC-1..AC-6), все зелёные.
- `python3 scripts/codebase_map.py` и сравнение с закоммиченным `docs/codebase-map.md` — расхождение только в строке `built_at_sha` (не признак дефекта, skill review-checklist); откатил регенерацию (`git checkout -- docs/codebase-map.md`) перед вердиктом.
- Прочитан `orchestrator/review.py:1-135` и `orchestrator/fsm_advance.py:430-505` целиком — подтверждена корректность фикса R1-F1 (сравнение с `EMPTY_DIFF_TEXT` до форматирования, fail-closed на сбое git второго diff не изобретает число).
- Прочитан diff `tests/test_capacity_gate.py`/`tests/test_review_package.py` относительно main целиком (три-dot) — новые тесты бьют по реальному коду (`gitcmd.git` мокается на уровне subprocess, `_capacity_gate_refuses`/`git_diff_part` вызываются напрямую, не переимитированы).

## Предложения системе

- Инкрементальный ревью-пакет этой итерации был почти полностью занят содержимым ДВУХ чужих задач (zone_lock, stack.py), затянутых `подтяжкой main` — не пустой, но вводящий в заблуждение diff (класс уже описан в skill, «Инкрементальный diff пакета — пустой не значит без изменений», но здесь наоборот: непустой, но нерелевантный). Разбор занял отдельную сверку `git diff main...HEAD` против `git diff <prev_sha>...HEAD` — стоит подумать, не считать ли инкрементальный пакет по трёхточечному диффу от merge-base вместо диапазона `prev_sha...HEAD`, когда между ними лежит чистая подтяжка main без кодовых коммитов задачи.
- Докстринг «Ловит мутацию» продолжает проседать именно в `tests/*.py` (не в `acceptance_tests/`) — третий независимо отмеченный случай этого класса (см. «Замечания»).
