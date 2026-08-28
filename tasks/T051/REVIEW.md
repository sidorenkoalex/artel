---
task: T051
type: review
author_role: reviewer
status: escalate
iteration: 1
schema_version: 2
---

# REVIEW: Сверка свежести ветки до гейта

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (сверка в двух точках перехода) | ESCALATE | Не реализовано. Единственный SPEC'ированный механизм (`git merge` на `advance` из `in_dev` и на `approve` из `acceptance`) сталкивается с неослабляемым `tests/test_invariants.py::MergeOnlyFromMergeGateTest::test_no_other_state_and_no_other_command_merges` (проверил: тест буквально прогоняет каждую пару состояние×команда, кроме `merge_gate`+`approve`, и требует отсутствия `git merge` в вызовах git — `in_dev`+`advance` и `acceptance`+`approve` входят в этот перебор). Файл несёт докстринг ADR-0002 «НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ... может только Оператор отдельным ADR». Эскалация обоснована, не изобретена. |
| 2 (определение отставания) | OK | `gitcmd.commits_behind` — `git rev-list --count branch..base`, направление подтверждено юнит-тестами (`test_counts_commits_on_main_absent_from_the_branch`, `test_custom_base_overrides_main_branch`), прогнал — зелёные. |
| 3 (подтяжка + прогон приёмки) | ESCALATE | Тот же блокер, что требование 1. |
| 4 (переход только после успеха обоих шагов) | ESCALATE | Тот же блокер. |
| 5 (конфликт → escalated, `merge --abort`, main цел) | ESCALATE | Тот же блокер; приёмочный `test_ac2_conflict_escalates_and_aborts.py` красный, воспроизвёл сам — переход остаётся `review`, не `escalated` (мехнизм не подключён). |
| 6 (красные приёмочные после подтяжки → escalated, merge остаётся) | ESCALATE | Тот же блокер; `test_ac3_red_acceptance_tests_after_pull_escalates.py` красный, воспроизвёл. |
| 7 (не отстала — поведение переходов байт-в-байт прежнее) | OK (защитная часть) | `fsm.py` не тронут; прогнал `python3 -m unittest discover -s tests` — 753/753 зелёных, включая `test_invariants.py` целиком. Как часть механизма подтяжки требование не закрыто — та же эскалация. |
| 8 (doctor: warn по отставшей активной задаче) | OK | `check_branch_freshness` реализован и подключён в `all_checks`; юнит-тесты `tests/test_doctor.py::BranchFreshnessCheckTest` зелёные. Приёмочный `test_ac5_...far_behind...` красный — не дефект реализации (см. «Замечания», п. minor). |
| 9 (молчаливый пропуск в песочницах без git) | OK | `commits_behind` возвращает `None` на нечисловой/пустой вывод и ненулевой код возврата; приёмочный `test_ac6_fake_git_skips_freshness_silently.py` зелёный, воспроизвёл. |
| 10 (подтяжка не трогает main) | ESCALATE | Часть нереализованного механизма; защитная часть (main вообще не изменяется этой веткой diff) подтверждена — код только читает git, ничего не пишет. |
| 11 (правки только в orchestrator/, тестах, карте) | OK | `git diff --stat main...` — только `orchestrator/{config,doctor,gitcmd}.py`, `tests/test_doctor.py`, `tests/test_gitcmd_branch_reads.py`, `docs/codebase-map.md`, собственные артефакты `tasks/T051/*`. Ничего вне зоны. |

## Замечания

- minor — `tasks/T051/acceptance_tests/test_ac5_doctor_warns_lagging_branch.py:26-34` (`DoctorWarnsLaggingActiveBranchTest.all_checks`) — мок `mock.patch.object(doctor.subprocess, "run", return_value=CompletedProcess([], 1, "", ""))` глушит `run` на объекте модуля `subprocess`, который у `doctor` и `gitcmd` — один и тот же объект (проверил: `doctor.subprocess is gitcmd.subprocess` → `True`; прогнал тест — вывод `all_checks()` в трейсбеке действительно показывает `git-identity: ok` через сквозной побочный эффект, но `branch-freshness: ok` вместо ожидаемого `warn`, и `live-smoke: fail` — все git/CLI вызовы получают код 1 одинаково). Из-за этого `commits_behind` внутри теста всегда получает «git не ответил» и код требования 8 не может показать `warn` независимо от реализации — воспроизвёл дефект напрямую. Тот же класс ошибки уже пойман и исправлен в этом репозитории приёмом `claude_only_run`/`claude_only_popen` (`tests/test_doctor.py:122-133`, side_effect по `args[0] == "claude"`, остальное — в настоящий `subprocess.run`). Файл — локед приёмочный тест (`tasks/T051/acceptance_tests/`), правка вне зоны роли developer и вне зоны роли reviewer (артефакт другой роли, `test_author`); чинится по образцу, уже задокументированному в репозитории. Не blocker/major для этой итерации: не влияет на реализацию требования 8, которая проверена отдельно юнит-тестами и прямым вызовом.

## Вердикт

escalate — требования 1, 3–7, 10 (SPEC) и критерии AC-1–AC-4 не реализуемы в текущем виде без решения Оператора: единственный SPEC'ированный механизм подтяжки (`git merge` на `advance`/`approve` вне `merge_gate`) конфликтует с неослабляемым инвариантом `tests/test_invariants.py::MergeOnlyFromMergeGateTest` (docs/invariants.md, инвариант 12), и правка этого теста — по ADR-0002 право только Оператора. Проверил конфликт независимо (сам тест, полный прогон 753/753 тестов, приёмочные AC-1..AC-3 красные по этой же причине) — эскалация developer'а обоснована, не является уклонением от работы.

Реализованная в этой итерации часть (требования 2, 8, 9, 11 — `gitcmd.commits_behind`, `config.STALE_BRANCH_WARN_COMMITS`, `doctor.check_branch_freshness`) — без замечаний уровня blocker/major, покрыта юнит-тестами, не задевает зону вне SPEC, ничего не ослабляет. Один minor — дефект мока в локед-приёмочном тесте `test_ac5_...` (не в коде задачи, см. «Замечания»).

Вопрос Оператору — как реализовать требования 1, 3–7, 10 (передаю варианты из PLAN.md «Эскалация», вопрос 1, все три независимо непротиворечивы с проверенным фактом конфликта):
- (а) ADR, сужающий инвариант 12 до направления «ветка задачи → main» (не любой `git merge`), с правкой `test_invariants.py`/`docs/invariants.md` под Оператором или отдельной задачей конвейера по ADR — затем разработчик реализует SPEC буквально (`git merge --no-ff` в worktree, `git merge --abort` при конфликте, прогон `acceptance.py::run` на подтянутом дереве).
- (б) подтяжка git-плумбингом (`merge-tree`/`commit-tree`/`update-ref`) — не рекомендую (formально обходит букву инварианта, не решает конфликт по существу, и требует ещё переопределения требования 5, где явно назван `git merge --abort`).
- (в) отказ от автоматической подтяжки в этих точках — оркестратор только детектирует и блокирует переход текстом; меняет требование 3 по существу («подтягивает», не «просит») — тоже решение только Оператора.
- (default, если Оператор промолчит) ничего не подключать: T051 остаётся в текущем виде (только `doctor`-часть), сама подтяжка — открытый долг.

Дополнительно: `test_ac5_...` (см. «Замечания») чинится по образцу `claude_only_run`/`claude_only_popen` из `tests/test_doctor.py:122-133` — не требует решения Оператора, вопрос к `test_author` при возврате задачи в работу.

Вопрос «warn vs incident» (PLAN «Эскалация», вопрос 3) решаю на ревью, без выноса Оператору: SPEC требование 8 буквально говорит «предупреждение» — реализованный `Check(..., "warn", ...)` без записи в `alerts` соответствует тексту SPEC; заводить incident/`alert-ack` под самоустраняющееся состояние параллельной работы (roadmap §4 п.2а) было бы расширением зоны задачи. Как реализовано — годится.

## Предложения системе

- `tasks/T051/acceptance_tests/test_ac5_doctor_warns_lagging_branch.py` — класс ошибки «мок `subprocess.run` глушится на объекте модуля, общем для нескольких модулей оркестратора» уже словлен и задокументирован один раз в этом же репозитории (`tests/test_doctor.py:122-133`) — стоит вынести общий хелпер (`claude_only_run`-подобный side_effect) в `tests/sandbox.py` или соседний общий модуль песочниц, чтобы авторы приёмочных тестов не наступали на этот же класс бага заново в каждой новой задаче.
