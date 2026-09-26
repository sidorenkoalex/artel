---
task: 01M3FQ2V77QNK95Z599DM124QN
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Гейт неослабления тестов: удалённые, переименованные и ослабленные тесты отказывают на in_dev -> verifying и на гейте мержа

## Фаза A: гейт плана

1. **Покрытие SPEC полно.** Таблица «Покрытие требований» PLAN.md несёт
   все 11 требований; шаг 2 — приложение (требование 9), остальное —
   шаг 1. Фактический дифф совпал с составом шага 1 файл-в-файл
   (`git diff --name-only 3b56de30...HEAD`: 9 файлов зоны +
   `docs/codebase-map.md`), лишнего нет.
2. **Размер шага.** Монолит обоснован в SPEC и повторён в PLAN по тем же
   двум связкам (один текст мандата на два гейта; одна строка инварианта
   про оба рубежа). Разрез дал бы заведомо ложную запись инварианта —
   согласен, дробить нечего.
3. **Конвенции и архитектура.** Подход не конфликтует: ast-разбор
   остался единственным адресом в `scripts/guard.py` (старый
   `_collect_test_functions` выражен через новый квалифицированный
   сборщик, а не скопирован), примитив чтения заведён в `gitcmd` рядом с
   `diff_names` с тем же контрактом `None`, обёртки гейтов повторяют
   форму соседей (`_run_gates`/`GateRefusal`, `merge_gate_escalates` по
   образцу `_protected_path_diff_gate`). Зоны SPEC не превышены,
   защищённых путей в кодовом коммите нет.
4. **Решение 2 плана** (имя `_dotted_name` уже занято в guard на строке
   1260 и определено НИЖЕ по файлу) — проверил: коллизия реальна,
   переиспользование через `_called_dotted_name` верное.
5. Возражений по плану, требующих правки, нет. Замечание R1-F3 ниже
   касается одной формулировки раздела «Влияние на систему».

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (один узел, ast в guard) | OK | `advance_gates/test_integrity.py::findings` — единственная сборка; ast в `guard.qualified_test_methods`/`test_skip_markers`, второй копии обхода нет. Классы (а)-(г) реализованы в `_file_findings` (test_integrity.py:100-141) |
| 2 (`tests/**/*.py` любой глубины) | OK | `_in_scope` (test_integrity.py:81-92) — префикс `tests/` + суффикс `.py`, без `count("/") == 1`; `tasks/*/acceptance_tests` вне области по построению |
| 3 (`git diff -M --name-status`) | OK | `gitcmd.diff_name_status` (gitcmd.py:282-315). Разбор `-z` сверил с живым git на репозитории с путём, содержащим пробел: поля `'R100'\|'tests_old file.py'\|'new.py'` разложены верно, `A`/`D` — по два поля. Сравнение методов у пары идёт старый-в-base против нового-в-head (`_pair` → `_file_findings`) |
| 4 (мандат Оператора) | OK | `_answer_mandate` (test_integrity.py:196-221) — тот же приём, что `zones._answer_zones_mandate`, включая `_answer_commit_is_role_step_autocommit`; `Finding.mandate_elements` даёт путь + `путь::имя`; покрытые находки уходят в журнал `TEST_INTEGRITY_ALLOWED_ACTION`, а не в отказ |
| 5 (файл с нулём тестов — не находка) | OK | `_file_findings`: удаление/переименование заводится только при непустом `base_methods` |
| 6 (гейт перехода, место, отказ, пропуски, fail-closed) | OK | `fsm_advance.py:533` — между `_mutation_claim_gate` и `_review_rework_gate_refuses`; канарейка/внешний target пропускаются; все три точки молчания git отказывают (`diff_base`, `diff_name_status`, `show`) |
| 7 (тот же узел на мерже, fail-open) | OK | `fsm_merge_gate.py:920`, сразу за `_protected_path_diff_gate`, до `_ensure_branch_head_published`; `merge_gate_escalates` на `found is None` возвращает `False` |
| 8 (гейт заявки мутации не меняется) | OK | `orchestrator/advance_gates/review.py` в диффе отсутствует; `test_file_deleted_in_head_is_skipped` на месте, `tests/test_mutation_claim_gate.py` зелёный |
| 9 (приложение к PLAN) | OK | Оба блока прогнал сам: `git apply --check` и реальный `git apply` на ЧИСТОМ дереве merge-base 3b56de30 — rc=0 у каждого; `guard.plan_appendices` разбирает оба раздела без ошибок (`paths=('docs/invariants.md',)`, `('tests/test_invariants.py',)`) |
| 10 (документация Оператора) | OK | `docs/operator-session.md` — пункт о снятии ручной сверки; `docs/operator-gates.md` — п.4 гейта мержа и п.6 гейта эскалации с дословным префиксом мандата |
| 11 (тесты в `tests/`) | реализовано не так | Находки, мандат, пропуски, сбой git, разбор `diff_name_status` покрыты. Теста «на порядок гейта» в `tests/` нет вовсе, а «на гейт мержа» покрыт только узел (`merge_gate_escalates`), не подключение. Подтверждено мутацией — R1-F1 |

## Замечания

- **major — tests/test_test_integrity_gate.py:396-400; tasks/01M3FQ2V77QNK95Z599DM124QN/PLAN.md:305-311 и :342-347 (приложение → tests/test_invariants.py) — три теста заявляют докстрингом мутацию «рубеж не подключён к маршруту», которую не ловят; в `tests/` подключения гейта не проверяет вообще ничто.**

  Все три зовут функции гейта НАПРЯМУЮ, минуя `fsm_advance.in_dev` и
  `_cmd_approve_merge_gate`, но обещают в «Ловит мутацию» ровно обратное:
  - `tests/test_test_integrity_gate.py:396` —
    «узел подключён только к `in_dev -> verifying` — ветка … сливается в
    main без единого слова», а вызывается `test_integrity.merge_gate_escalates`;
  - приложение PLAN, `TestWeakeningNeedsTheOperatorTest.
    test_a_deleted_test_does_not_pass_the_transition` (PLAN.md:306) —
    «рубеж снят с `in_dev → verifying` … и переход проходит молча», а
    вызывается `fsm_advance._test_integrity_gate_refuses`;
  - там же `test_the_merge_gate_escalates_the_same_finding` (PLAN.md:343)
    — «узел подключён только к переходу», а вызывается
    `test_integrity.merge_gate_escalates`.

  Сценарий поломки проверен исполнением, а не рассуждением. В отдельном
  worktree на HEAD ветки (с ПРИМЕНЁННЫМ приложением
  `tests/test_invariants.py`) я снял обе строки подключения —
  `fsm_advance.py:533` и `fsm_merge_gate.py:920`, — то есть отключил гейт
  от обоих маршрутов целиком, оставив модуль на месте. Прогон
  `tests/test_test_integrity_gate.py`, `tests/test_guard_test_ast.py`,
  `tests/test_invariants.py`, `tests/test_fsm_advance_gate_smoke.py`,
  `tests/test_fsm_advance_gate_framework.py`,
  `tests/test_mutation_claim_gate.py`,
  `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_auto_cycle.py`
  — **183 passed, 243 subtests passed**, ни одного падения. Планка на том
  же мутированном дереве краснеет как и должна (AC-12 и AC-13, 2 failed),
  но планка задачи в `pytest tests` не входит и после мержа регресс не
  сторожит: постоянный набор пульта пропустит снятие рубежа молча — то
  есть ровно ту потерю, ради предотвращения которой задача и делается.
  Это же делает строку 38 приложения `docs/invariants.md` частично
  необеспеченной: она называет `test_invariants.
  TestWeakeningNeedsTheOperatorTest` тестом инварианта «рубеж СТОИТ», а
  тот стоять рубеж не проверяет.

  Предложение: перенести приём планки AC-13 в постоянный набор —
  в `tests/test_test_integrity_gate.py` (путь незащищённый, правится этой
  же задачей) добавить сценарий по `inspect.getsource(fsm_advance.in_dev)`
  с порядком `_mutation_claim_gate` → `_test_integrity_gate_refuses` →
  `_review_rework_gate_refuses` и сценарий присутствия
  `_test_integrity_diff_gate` в
  `inspect.getsource(fsm_merge_gate._cmd_approve_merge_gate)` ПОСЛЕ
  `_protected_path_diff_gate`; докстринги трёх перечисленных тестов
  привести к тому, что они действительно ловят (поведение самого узла и
  обёртки, а не факт подключения). Требование 11 SPEC называет тест «на
  порядок гейта» в `tests/` прямо — сейчас он там отсутствует.

- **minor — orchestrator/advance_gates/test_integrity.py:68-76 — мандат на
  переименование засчитывается только по СТАРОМУ пути.**
  `Finding.path` у пары переименования — путь в base, поэтому строка
  Оператора `Ослабление тестов разрешено: tests/test_beta.py` (новое имя
  — то, которое он видит в ветке и в PR) находку не покрывает, и
  `advance` отказывает второй раз. Detail отказа называет старый путь
  первым, так что исход самокорректируемый, а направление ошибки
  безопасное (лишний отказ, не лишний пропуск) — отсюда minor.
  `docs/operator-gates.md` п.6 («элемент-путь снимает ВСЕ находки этого
  файла, включая … переименование») который из двух путей писать, не
  говорит. Предложение: либо засчитывать оба пути в
  `Finding.mandate_elements`, либо одной фразой назвать в
  `docs/operator-gates.md`, что пишется путь ДО переименования.

- **minor — tasks/01M3FQ2V77QNK95Z599DM124QN/PLAN.md, «Влияние на систему»
  — цена рубежа в git-вызовах названа неполно.** Сказано «`git diff -M` …
  — одна дополнительная git-команда на переход, не на файл»; про сам
  `git diff -M` это верно, но `findings` дополнительно зовёт
  `gitcmd.show` по одному разу на КАЖДУЮ сторону каждого файла диффа под
  `tests/` (test_integrity.py:172-187), а при находке добавляются
  `git log -1` + `git show` на каждый `ANSWER-n.md`. На ветке, трогающей
  40 файлов `tests/` (штатный размер рефакторинга), это 81 подпроцесс на
  каждый заход в `advance` вместо заявленного одного. Сценарий —
  не поломка, а недооценка латентности перехода Оператором, читающим
  PLAN; отсюда minor. Предложение: уточнить фразу («+1 `git diff -M` и до
  двух `git show` на каждый файл `tests/` в диффе»).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_test_integrity_gate.py:396; PLAN.md:305-311, :342-347 (приложение → tests/test_invariants.py) | Три теста заявляют «Ловит мутацию: узел/рубеж не подключён к маршруту», но зовут функции гейта напрямую; в `tests/` нет ни одного сценария на подключение и порядок (требование 11 называет его прямо) | Снятие обеих строк подключения (`fsm_advance.py:533`, `fsm_merge_gate.py:920`) оставляет 183 теста зелёными — постоянный набор пульта пропустит отключение рубежа молча, а строка 38 `docs/invariants.md` останется без теста, который её держит | Добавить в `tests/test_test_integrity_gate.py` сценарии по `inspect.getsource` для `fsm_advance.in_dev` (порядок между заявкой мутации и отработкой замечаний) и для `fsm_merge_gate._cmd_approve_merge_gate` (после `_protected_path_diff_gate`); докстринги трёх тестов привести к реально ловимой мутации |
| R1-F2 | open | orchestrator/advance_gates/test_integrity.py:68-76 | Мандат на переименование сверяется только со старым путём; `docs/operator-gates.md` п.6 не называет, какой из двух путей писать | Оператор пишет новое имя файла (то, что видит в ветке), гейт отказывает повторно — лишний круг `advance` | Засчитывать оба пути в `mandate_elements` либо явно назвать в `docs/operator-gates.md` путь ДО переименования |
| R1-F3 | open | tasks/01M3FQ2V77QNK95Z599DM124QN/PLAN.md, «Влияние на систему» | Заявлена «одна дополнительная git-команда на переход, не на файл»; `findings` зовёт `gitcmd.show` по разу на сторону каждого файла `tests/` в диффе | На ветке с 40 изменёнными файлами `tests/` — 81 подпроцесс на заход в `advance`; Оператор недооценивает латентность перехода по PLAN | Уточнить формулировку: +1 `git diff -M` и до двух `git show` на файл `tests/` в диффе, плюс `git log -1`/`git show` на `ANSWER-n.md` при находке |

## Вердикт

`changes_requested`. Блокеров нет; реализация узла, обоих гейтов, мандата
и приложения к PLAN сделана по SPEC и проверена исполнением. К исправлению:

1. **R1-F1 (major)** — покрыть подключение гейта к обоим маршрутам
   сценариями в `tests/` и привести докстринги трёх тестов к реально
   ловимой мутации.
2. **R1-F2, R1-F3 (minor)** — на усмотрение: либо правка, либо
   обоснованный `rejected` в реестре.

Системной целостности изменение не нарушает: ни один существующий тест,
гейт, лимит или guard не ослаблен и не удалён; `orchestrator/advance_gates/
review.py` (включая `test_file_deleted_in_head_is_skipped`) в диффе
отсутствует; защищённых путей в кодовом коммите нет — `docs/invariants.md`
и `tests/test_invariants.py` идут приложением к PLAN, как требует SPEC.
Пометок `# AC-n: manual|skip` в планке нет. Откат описан (revert одного
merge-коммита) и достоверен: обе правки в `guard`/`gitcmd` аддитивны,
кроме выражения `_collect_test_functions` через новый сборщик, которое
возвращается тем же revert'ом.

## Проверено исполнением

Всё ниже — в переднем плане, из рабочего каталога шага.

- `python3 -m pytest tests/test_test_integrity_gate.py
  tests/test_guard_test_ast.py tests/test_mutation_claim_gate.py
  tests/test_fsm_advance_gate_smoke.py tests/test_protected_paths_gate.py
  tests/test_zones_gate.py -q` — **97 passed**.
- `python3 -m pytest tests/test_invariants.py
  tests/test_guard_mutation_claim.py tests/test_plan_appendix.py
  tests/test_fsm_advance_gate_framework.py tests/test_advance_guard.py -q`
  — **120 passed, 221 subtests passed**.
- Планка задачи: `python3 -m pytest
  tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests -q` — **30 passed**
  (три `test_ac14_*`, красневшие у разработчика, зелены: PLAN.md уже на
  артефактной ветке).
- **Узел на живом git против собственной ветки.**
  `test_integrity.findings("task/01m3fq2v77qnk95z599dm124qn-geyt-
  neoslableniya-testov-udal")` → `base=3b56de30…`, `found=[]`,
  `detail=""` — ветка проходит собственный рубеж вчистую, ложных находок
  на реальном диффе из 10 файлов нет.
- **Разбор `-z` сверен с настоящим git.** Во временном репозитории
  (`git mv "tests_old file.py" new.py`, `git rm gone.py`, новый файл)
  `git diff -M --name-status -z` отдал
  `'A\0added.py\0D\0gone.py\0R100\0tests_old file.py\0new.py\0'` —
  раскладка полей ровно та, на которую рассчитан
  `gitcmd.diff_name_status`, включая путь с пробелом без экранирования.
- **Приложение к PLAN.** `guard.plan_appendices(PLAN.md)` → 2 приложения,
  0 ошибок разбора. В detached worktree на ЧИСТОМ merge-base 3b56de30:
  `git apply --check` rc=0 и `git apply` rc=0 у ОБОИХ блоков по
  отдельности. Второй блок, применённый на HEAD ветки (там модуль гейта
  уже есть), даёт
  `pytest tests/test_invariants.py::TestWeakeningNeedsTheOperatorTest` —
  **3 passed**.
- **Мутационная проверка R1-F1.** В detached worktree на HEAD с
  применённым приложением сняты обе строки подключения гейта
  (`fsm_advance.py:533`, `fsm_merge_gate.py:920`). Прогон восьми модулей
  `tests/` (включая `test_test_integrity_gate.py`, `test_invariants.py`,
  `test_fsm_merge_gate_done_snapshot.py`, `test_auto_cycle.py`) —
  **183 passed, 243 subtests passed, 0 failed**. Планка на том же
  мутированном дереве — **2 failed, 28 passed**
  (`test_ac12_finding_without_mandate_escalates_on_merge_gate`,
  `test_ac13_new_gate_stands_between_mutation_claim_and_review_rework`).
  Обе временные worktree сняты `git worktree remove --force`, рабочее
  дерево не тронуто.
- **Свежесть карты.** `python3 scripts/codebase_map.py` →
  `git diff -- docs/codebase-map.md` даёт одну строку различия, и это
  `built_at_sha`; содержательных расхождений **0**. Файл возвращён
  `git checkout --`.
- **Скан существующих пропусков.** `grep -rn` по `tests/` на
  `@unittest.skip*`/`@pytest.mark.skip|xfail`/`self.skipTest(`/
  `pytest.skip(`/`expectedFailure` вне двух новых файлов — **ни одного
  совпадения**: поверхность ложных отказов у строгого толкования класса
  «г» (новый тест сразу под `@skip`) сегодня пустая, риск PLAN оценён
  верно.
- Полный набор `tests/` не гонял — решение Оператора 05.09, его держит
  CI ветки (коммит 8c17fedb зелёный, 7 проверок).

## Предложения системе

- Класс «тест заявляет докстрингом мутацию о ПОДКЛЮЧЕНИИ узла к маршруту,
  а сам зовёт функцию напрямую» стоит назвать в
  `skills/test-authoring.md` отдельно: заявка о встроенности в маршрут
  проверяется только прогоном маршрута либо чтением его исходника
  (`inspect.getsource`), и это единственные два способа. Задача
  01M3FQ2V77QNK95Z599DM124QN дала три экземпляра класса разом, причём
  автор ЗНАЛ приём (`inspect.getsource` применён в планке AC-13) —
  значит промахнулась не техника, а граница «что считается проверкой
  заявки».
- Планка задачи (`tasks/<id>/acceptance_tests/`) после мержа регресс не
  сторожит: `pytest tests` её не собирает. Там, где планка — ЕДИНСТВЕННОЕ
  место, ловящее мутацию (здесь это оказалось подключение обоих гейтов),
  инвариант остаётся без постоянного сторожа, хотя строка
  `docs/invariants.md` на планку ссылается. Кандидат в бэклог: правило
  «инвариант, чей единственный тест лежит в планке задачи, обязан
  получить двойник в `tests/`» — либо в `skills/review-checklist.md`,
  либо машинной сверкой колонки «тест» первой таблицы
  `docs/invariants.md` с набором `tests/`.
- Подтверждаю оба наблюдения PLAN: первая таблица `docs/invariants.md`
  несёт ДВА инварианта с номером 36 (строки 66 и 67), и `scripts/guard.py`
  перевалил за 2000 строк с двумя разными предметами внутри (структура
  артефактов и ast-разбор тестов), из-за чего новому помощнику пришлось
  брать имя `_called_dotted_name` в обход занятого `_dotted_name`. Оба —
  в бэклог отдельными строками.
