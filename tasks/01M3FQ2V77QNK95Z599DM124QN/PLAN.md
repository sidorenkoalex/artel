---
task: 01M3FQ2V77QNK95Z599DM124QN
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Гейт неослабления тестов: удалённые, переименованные и ослабленные тесты отказывают на in_dev -> verifying и на гейте мержа

## Подход

Один узел сравнения, два гейта на нём, мандат Оператора как единственный
способ пройти находку — ровно рамка SPEC. Решения, которые стоило
принять явно:

1. **Ast-разбор — в `scripts/guard.py`, рядом с
   `_collect_test_functions`** (требование 1). Существующий сборщик
   отдаёт ГОЛЫЕ имена методов: это контракт гейта заявки мутации (его
   detail и сверка с base идут по такому ключу). Новому рубежу нужно
   квалифицированное имя (`AlphaTest::test_two`, AC-3), поэтому
   добавлена `_collect_qualified_test_functions`, а прежний
   `_collect_test_functions` выражен через неё срезом до последнего
   сегмента — «что считается тестовым методом» осталось одним правилом в
   одном месте, как того требует SPEC, без второй копии обхода ast.
   Публичный слой поверх — `guard.qualified_test_methods(source)` и
   `guard.test_skip_markers(source)`; оба глотают `SyntaxError` и `None`
   тем же fail-safe, что `test_functions_without_mutation_claim`.
2. **Имя `_dotted_name` в guard уже занято** (scripts/guard.py:1260,
   разбор упоминаний артефактов) — и определено НИЖЕ по файлу, то есть
   молча перекрывало бы одноимённую новую функцию. Разбор точечного
   имени декоратора переиспользует существующую
   (`_called_dotted_name` только разворачивает `ast.Call`:
   `@unittest.skip` и `@unittest.skip("причина")` — один маркер).
3. **Распознавание переименования — новый примитив чтения
   `gitcmd.diff_name_status`** (`git diff -M --name-status -z`,
   требование 3). `-z` вместо табуляций: путь с пробелом или кавычкой в
   обычном выводе экранируется, и табуляционный разбор отдал бы
   искажённое имя. Контракт `None` — «git не ответил» — тот же, что у
   соседнего `diff_names`.
4. **Fail-closed на чтении содержимого проще, чем у гейта заявки
   мутации.** Тому приходится различать «файла нет в head» и «сбой git»
   по тексту причины и по `ls_tree_files`, потому что он идёт по списку
   ИМЁН. Здесь путь каждой стороны назвал сам `git diff --name-status`
   вместе со своим статусом: если запись говорит «файл был в base», его
   чтение из base обязано удаться — `None` здесь всегда сбой, и лишнего
   различения не нужно.
5. **Новые тесты в `tests/` не ослабляют существующие.** Ни один файл не
   удалён и не переименован, `tests/test_invariants.py` правится только
   приложением к PLAN (защищённый путь), сам гейт своей же веткой
   проходится вчистую.
6. **Итерация 2: подключение рубежа держится тестом в `tests/`, а не
   только планкой** (замечание R1-F1). Приём тот же, что в планке AC-13 —
   чтение тела обработчика (`inspect.getsource`), — но живёт он теперь в
   `tests/test_test_integrity_gate.py::GateWiringTest`, то есть в
   постоянном наборе пульта, который планка после мержа не заменяет
   (`pytest tests` её не собирает). Сверка идёт по ФОРМЕ вызова
   (`имя(conn`), не по вхождению имени: имя, оставшееся в комментарии или
   в блоке импортов, подключением не является — иначе тест зеленел бы на
   отключённом рубеже, чей вызов лишь упомянут рядом. Заодно три
   докстринга (один в `tests/`, два в приложении к PLAN) приведены к
   мутации, которую они действительно ловят: заявка о встроенности в
   маршрут проверяется только прогоном маршрута либо чтением его
   исходника, и прямой вызов функции гейта такой заявкой не является.
7. **Итерация 2: мандат на переименование читается по ОБОИМ путям**
   (замечание R1-F2). У находок распознанной пары появился второй адрес —
   `Finding.alias`, путь в head; `mandate_elements` отдаёт оба пути и оба
   квалифицированных имени. Направление ошибки было безопасное (лишний
   отказ), но платил за неё Оператор лишним кругом `advance` на
   безупречно выписанном разрешении: он пишет мандат, глядя на ветку и на
   PR, где файл уже под новым именем. Признание второго пути ДОБАВЛЕНО, не
   подменяет первый (оба случая закреплены сценариями
   `RenameMandateTest`), и остаётся точным: разрешение на один метод
   переименованного файла само переименование по-прежнему не покрывает.

Потолок SPEC ($45) не переоценивается: число файлов и шагов совпало с
оценкой SPEC (новый модуль гейта, функции в guard, примитив gitcmd, две
точки обвязки FSM, два файла документации, два файла тестов).

## Шаги

1. **Узел, оба гейта и документация — один MR.** Разрезать нечего:
   `fsm_merge_gate` зовёт тот же модуль, что `fsm_advance`, а
   `docs/operator-session.md` снимает ручную сверку с Оператора только
   когда гейт мержа уже существует (обоснование монолита — в SPEC).
   Состав:
   - `orchestrator/gitcmd.py` — `diff_name_status` (примитив чтения,
     требование 3);
   - `scripts/guard.py` — `_collect_qualified_test_functions`,
     `qualified_test_methods`, `test_skip_markers` и помощники
     распознавания маркеров (требование 1);
   - `orchestrator/advance_gates/test_integrity.py` — узел (`findings`,
     `uncovered`, мандат), обёртка перехода
     `_test_integrity_gate_refuses` и вход гейта мержа
     `merge_gate_escalates` (требования 1-2, 4-6);
   - `orchestrator/fsm_advance.py` — вызов обёртки в `in_dev` сразу
     после гейта заявки мутации и до гейта отработки замечаний, плюс
     реэкспорт имён (требование 6);
   - `orchestrator/fsm_merge_gate.py` — `_test_integrity_diff_gate`
     сразу за `_protected_path_diff_gate` в `_cmd_approve_merge_gate`
     (требование 7);
   - `docs/operator-session.md`, `docs/operator-gates.md` (требование
     10);
   - `tests/test_test_integrity_gate.py`, `tests/test_guard_test_ast.py`
     (требование 11);
   - `docs/codebase-map.md` — регенерация тем же коммитом.
2. **Приложение к PLAN** (защищённые пути, применяет Оператор):
   `docs/invariants.md` (строка 38 и перечень рубежей) и
   `tests/test_invariants.py` (класс
   `TestWeakeningNeedsTheOperatorTest`) — раздел «## Приложение» ниже.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (один узел, ast в guard) | 1 |
| 2 (область `tests/**/*.py`) | 1 |
| 3 (`git diff -M --name-status`) | 1 |
| 4 (мандат Оператора в ANSWER-n) | 1 |
| 5 (файл с нулём тестов — не находка) | 1 |
| 6 (гейт на `in_dev -> verifying`, место, отказ, пропуски, fail-closed) | 1 |
| 7 (тот же узел на гейте мержа, fail-open) | 1 |
| 8 (гейт заявки мутации не меняется) | 1 |
| 9 (приложение: docs/invariants.md, tests/test_invariants.py) | 2 |
| 10 (документация Оператора) | 1 |
| 11 (тесты) | 1 |

## Влияние на систему

**Что затрагивается за пределами правки.** Переход `in_dev -> verifying`
получает девятый рубеж; он стоит ПОСЛЕ гейта заявки мутации, поэтому ни
один существующий отказ не меняет ни старшинства, ни текста
(`tests/test_fsm_advance_gate_smoke.py` сверяет журнал и stdout
байт-в-байт — зелёный). Гейт мержа получает второй ранний рубеж рядом с
защищёнными путями, до любой записи в main и до `set_state` соседей.

**Цена рубежа в подпроцессах git** (уточнено по R1-F3). На каждый заход в
любой из двух гейтов: `+1` `git diff -M --name-status` (одна команда на
переход, не на файл) и до `+2` `gitcmd.show` на КАЖДЫЙ файл `tests/` в
диффе — по одному на сторону, base и head (удалённый и новый файл читаются
одной стороной, изменённый и переименованный — двумя). При находке
добавляются `git log -1` и `git show` на каждый `ANSWER-n.md` ветки
задачи. То есть на ветке, трогающей 40 файлов `tests/` (штатный размер
рефакторинга), это порядка 81 подпроцесса на заход в `advance`, а не один;
файлы вне `tests/` и не-`.py` под `tests/` отбрасываются до всякого
чтения (`_in_scope` перед `gitcmd.show`). Латентность перехода Оператору
стоит считать по этому числу.

**Инварианты и защиты рядом, и почему они не ослаблены.**
- Гейт заявки мутации (`advance_gates/review.py`) не тронут ни строкой,
  включая молчаливый пропуск удалённого в head файла и тест
  `test_file_deleted_in_head_is_skipped` (требование 8, SPEC «Не
  входит»). Его собственный сборщик `_collect_test_functions` сохранил
  контракт (голые имена) — на это заведён отдельный тест
  `test_bare_name_collector_stays_compatible`.
- Лок планки приёмки (`tasks/*/acceptance_tests`) остаётся единственным
  хозяином планок: область узла — только `tests/`, AC-5 это закрепляет.
- `config.PROTECTED_PATHS`, `orchestrator/answer.py`,
  `orchestrator/config.py`, `orchestrator/store.py` — только чтение,
  мандат разбирается тем же способом, что мандат зон, без правки канала
  `answer`.
- Ни один существующий тест не удалён, не переименован и не ослаблен;
  новых маркеров пропуска в `tests/` не заведено (проверяется и планкой
  AC-13, и самим новым рубежом на этой же ветке).
- Само подключение рубежа к обоим маршрутам теперь сторожит постоянный
  набор пульта (`tests/test_test_integrity_gate.py::GateWiringTest`), а не
  только планка задачи: `pytest tests` планку не собирает, и после мержа
  снятие двух строк обвязки осталось бы незамеченным — предмет замечания
  R1-F1, проверено воспроизведением мутации.

**Новые риски ложного отказа и чем ограничены.** Рубеж fail-closed на
переходе: сломанный git отказывает переход вместо того, чтобы молча его
пропустить. Это осознанная цена ADR-0002, и она ограничена подсказкой
(«повтори advance») и тем, что на мерже поведение обратное — fail-open,
как у соседнего рубежа защищённых путей.

**Откат.** Revert одного merge-коммита: новый модуль исчезает целиком,
две строки вызова в `fsm_advance.in_dev`/`_cmd_approve_merge_gate` — с
ним, `guard`/`gitcmd` возвращаются к прежним функциям (обе правки
аддитивны, кроме выражения `_collect_test_functions` через новый
сборщик — оно возвращается тем же revert'ом). Приложение к PLAN
применяет Оператор отдельно; его откат — обратный патч тех же двух
файлов.

**Проверено исполнением (итерация 2, по замечаниям ревью).**
- `python3 -m pytest tests/test_test_integrity_gate.py
  tests/test_guard_test_ast.py` — **40 passed** (было 35: +2
  `GateWiringTest`, +3 `RenameMandateTest`).
- **Мутация R1-F1 воспроизведена той же правкой, что у ревьювера.** Из
  тела `fsm_advance.in_dev` и из тела `_cmd_approve_merge_gate` сняты обе
  строки подключения (`if _test_integrity_gate_refuses(...)` и `if
  _test_integrity_diff_gate(...)`), модуль гейта оставлен на месте:
  прогон — **2 failed, 38 passed**, краснеют ровно оба сценария
  `GateWiringTest` («рубеж отключён от перехода», «рубеж отключён от
  маршрута мержа»). Строки восстановлены `git checkout --`, прогон снова
  **40 passed**. До этой итерации та же мутация оставляла набор `tests/`
  полностью зелёным.
- Планка задачи: `python3 -m pytest
  tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests -q` — **30 passed**
  (PLAN.md итерации 1 уже на артефактной ветке, `test_ac14_*` зелены).
- Соседи по гейтам: `tests/test_mutation_claim_gate.py`,
  `tests/test_fsm_advance_gate_smoke.py`,
  `tests/test_protected_paths_gate.py`, `tests/test_zones_gate.py`,
  `tests/test_guard_mutation_claim.py`,
  `tests/test_gitcmd_check_ignore.py`,
  `tests/test_fsm_advance_gate_framework.py` — **93 passed**.
- Гейт мержа: `tests/test_fsm_merge_gate_done_snapshot.py`,
  `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`,
  `tests/test_merge_gate_ci_wait.py`, `tests/test_fsm_map_regen.py`,
  `tests/test_plan_appendix.py`,
  `tests/test_split_assessment_merge_gate.py` — **75 passed**.
- `tests/test_guard_schema.py`, `tests/test_acceptance_tests_flow.py`,
  `tests/test_advance_guard.py` — **140 passed, 21 subtests**.
- `tests/test_invariants.py` с ПРИМЕНЁННЫМ приложением (перегенерированный
  блок наложен `git apply` на рабочее дерево) — **66 passed, 215
  subtests**, включая три сценария `TestWeakeningNeedsTheOperatorTest`.
  Применение откачено `git checkout --`: в кодовом коммите защищённых
  путей нет.
- **Блок приложения `tests/test_invariants.py` перегенерирован, не
  подправлен руками.** Прежний блок наложен `git apply` в отдельном
  detached worktree на чистом merge-base (3b56de30), докстринги
  переписаны там, новый блок снят `git diff` — поэтому хедер хунка
  (`@@ -2235,3 +2236,120 @@`) считал git, не автор. ОБА блока
  приложения прогнаны `git apply --check` на том же чистом дереве по
  отдельности: код возврата **0** у каждого. Класс дефекта «хедер хунка
  не совпадает с реальным диапазоном файла» (T046, T047 итерация 1) этим
  закрыт. Worktree снят `git worktree remove --force`.
- **Узел против собственной ветки на живом git.**
  `test_integrity.findings(<ветка задачи>)` после коммита итерации 2 →
  `base=3b56de30…`, `found=[]`, `detail=''` — ветка проходит собственный
  рубеж вчистую, ложных находок на диффе из 11 файлов нет.
- `python3 scripts/guard.py` на PLAN.md, REVIEW.md, SPEC.md — «ок».
- `python3 scripts/codebase_map.py` — карта регенерирована тем же
  коммитом (`tests/test_test_integrity_gate.py` стала импортировать
  `orchestrator/fsm_merge_gate.py`).

**Проверено исполнением (итерация 1).**
- Планка задачи — 27 passed, 3 failed: все три `test_ac14_*`, их `setUp`
  читает PLAN.md из АРТЕФАКТНОЙ ветки, куда файл попадает автокоммитом
  того шага, то есть позже прогона. Тот же модуль с PLAN.md, поданным
  вместо `gitcmd.show` (приём из докстринга самой планки), — 3 passed,
  итого 30 из 30.
- `python3 -m pytest tests/test_test_integrity_gate.py
  tests/test_guard_test_ast.py` — 35 passed.
- Соседи: `tests/test_mutation_claim_gate.py`,
  `tests/test_fsm_advance_gate_smoke.py`,
  `tests/test_protected_paths_gate.py`, `tests/test_zones_gate.py`,
  `tests/test_guard_mutation_claim.py`,
  `tests/test_gitcmd_check_ignore.py`,
  `tests/test_fsm_advance_gate_framework.py` — 93 passed.
- `tests/test_invariants.py`, `tests/test_guard_schema.py`,
  `tests/test_acceptance_tests_flow.py`, `tests/test_advance_guard.py` —
  203 passed, 236 subtests.
- Гейт мержа: `tests/test_fsm_merge_gate_done_snapshot.py`,
  `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`,
  `tests/test_merge_gate_ci_wait.py`, `tests/test_fsm_map_regen.py`,
  `tests/test_plan_appendix.py`,
  `tests/test_split_assessment_merge_gate.py` — 75 passed.
- Приложение ниже прогнано `git apply --check` на ЧИСТОМ дереве
  merge-base (отдельный detached worktree, оба блока по отдельности):
  код возврата 0 у каждого. Класс дефекта «хедер хунка не совпадает с
  реальным диапазоном файла» (T046, T047 итерация 1) этим закрыт; сами
  диффы сняты `git diff` с реальной правки файлов, не набраны руками.
  Правка после снятия диффа откачена — в кодовом коммите защищённых
  путей нет.

## Риски

- **Новый файл тестов с маркером пропуска отказывает переходу.**
  Требование 1 (класс «г») сформулировано как «появившийся в head
  пропуск, которого в base на этом же имени не было», без оговорки про
  изменённые файлы, поэтому новый тест, заведённый сразу под `@skip`,
  рубеж отклонит. Толкование выбрано строгое осознанно: «завести тест и
  тут же его выключить» — то же ослабление, только сразу, а разрешить
  его Оператор может той же строкой мандата. Обратное толкование
  оставляло бы дыру ровно там, где её дешевле всего проделать.
- **Ложное срабатывание на чужом декораторе.** Маркером считается
  последний сегмент точечного имени (`skip`/`skipIf`/`skipUnless`/
  `expectedFailure`/`skipif`/`xfail`), поэтому пользовательский
  декоратор с таким именем будет назван маркером. Цена — один отказ с
  точным именем в detail и мандат Оператора; обратная ошибка (пропустить
  настоящий `@skip`) дороже.
- **Переименование ниже порога схожести git.** `git diff -M` перестаёт
  видеть пару при сильной правке тела — тогда рубеж докладывает удаление
  старого файла (отказ всё равно есть, текст другой). Это осознанное
  следствие выбора «определение переименования — работа git»
  (требование 3), не дефект реализации.

## Приложение: строка 38 и перечень рубежей docs/invariants.md

Защищённый путь — применяет Оператор коммитом в main (или гейт мержа
приложением). Блок снят `git diff` с реальной правки файла и проверен
`git apply --check` на чистом дереве merge-base.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index 8372b232..a7106191 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -64,8 +64,9 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 34 | Переход `in_dev → verifying` отказывает, если дифф ветки задачи трогает файлы вне объявленных `zones`/`zones_extension` и вне `config.COMMON_ZONES` (отказ называет конкретные файлы); исключение — раздел «## Расширение зон» PLAN.md, подкреплённый строкой `Расширение зон разрешено: <пути>` в ANSWER-n.md, ЧЕЙ ПОСЛЕДНИЙ КОММИТ доказанно не автокоммит артефактов шага роли (`checkpoint.py::own_commit_marker`) — developer не может подложить себе мандат Оператора через собственный автокоммит `tasks/<id>/` | `tests/test_zones_gate.py`; `tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/` | tasks/01M1P9QCHPHSCEA6TK13PV85SP/SPEC.md, требования 1-3; REVIEW.md итерация 2, R2-F1; ADR-0015 (переезд рубежа с `in_dev → review`) |
 | 35 | Тесты не читают сеть по DNS-имени: ни один файл `tests/**/*.py` не несёт адреса вида `http(s)://<DNS-имя>`, кроме `localhost`/`127.0.0.1` (допустимые исключения — именованная константа с обоснованием на каждую строку); сетевые git-команды (`fetch`/`push`/`ls-remote`/`clone`) с таким адресом перехватываются `tests/sandbox.py::TmpRootTest` мгновенным именованным отказом («сеть в тестах запрещена: `<команда>` `<адрес>`»), без обращения к сети | `test_invariants.NoNetworkAddressesInTestsTest`; `tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests/test_ac1_network_command_interception.py`, `test_ac2_local_bare_repo_not_blocked.py`, `test_ac9_network_interception_speed.py` | tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md, требования 1, 3 (инцидент 05.09: `git fetch -q https://example.invalid/sled main` висел минуты на DNS-резолвере при обрыве сети — фикстурный адрес `sled`-target'а в `tests/test_git_fixation.py`) |
 | 36 | Прогон CI существует для каждого пуша в `main`, `task/**`, `artifact/**`: секция `on.push` в `.github/workflows/ci.yml` не несёт фильтров `paths`/`paths-ignore`; лишние на данном классе пуша проверки снимаются условием на job (статус `skipped`, зелёный для `ci.GREEN`), причём job `python` не исключает `refs/heads/task/` и не строится как `== 'true'` по output соседнего job (fail-open), а job `guard` не исключает `refs/heads/artifact/` | `test_invariants.CiJobsByPushClassInvariantTest` | ADR-0016; `ci.verifying_status`/`ci.branch_status` читают пуш без прогона как «проверок нет вовсе» и держат задачу до потолка ожидания (инвариант 19) |
-| 36 | Порядок состояний FSM — `in_dev → verifying → review → acceptance → merge_gate`: CI подтянутой головы кодовой ветки проверяется ДО ревьювера, не после. Восемь рубежей перехода `in_dev → review` (подтяжка main, прогон приёмочной планки, гейт зон, гейт заявки мутации — новые и изменённые тесты `tests/` без строки «Ловит мутацию:» в докстринге, 01M29A0F88P9GKSXFW90F99H2N, гейт ёмкости, лок планки, гейт «замечания ревью не отработаны», сверка головы на origin) стоят на `in_dev → verifying` целиком, без повтора на `verifying → review`; в `review` из `verifying` ведёт только зелёный CI головы. Возврат `changes_requested` — в `in_dev`, повторный вход в `review` — снова через `verifying` | `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac01_ac09_state_order.py`; `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac02_ac08_gates_moved_to_verifying.py`; `test_auto_cycle.py::FSM_STATES` | ADR-0015 (docs/adr/0015-ci-before-review.md); tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md, требования 1-3 |
+| 36 | Порядок состояний FSM — `in_dev → verifying → review → acceptance → merge_gate`: CI подтянутой головы кодовой ветки проверяется ДО ревьювера, не после. Девять рубежей перехода `in_dev → review` (подтяжка main, прогон приёмочной планки, гейт зон, гейт заявки мутации — новые и изменённые тесты `tests/` без строки «Ловит мутацию:» в докстринге, 01M29A0F88P9GKSXFW90F99H2N, гейт неослабления тестов — удаление, переименование и ослабление тестов `tests/` без мандата Оператора, 01M3FQ2V77QNK95Z599DM124QN, гейт ёмкости, лок планки, гейт «замечания ревью не отработаны», сверка головы на origin) стоят на `in_dev → verifying` целиком, без повтора на `verifying → review`; в `review` из `verifying` ведёт только зелёный CI головы. Возврат `changes_requested` — в `in_dev`, повторный вход в `review` — снова через `verifying` | `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac01_ac09_state_order.py`; `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac02_ac08_gates_moved_to_verifying.py`; `test_auto_cycle.py::FSM_STATES` | ADR-0015 (docs/adr/0015-ci-before-review.md); tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md, требования 1-3 |
 | 37 | Класс `tests/*.py` с собственным `PATCHED_ATTRS` для `tests.sandbox.TmpRootTest` патчит `config.WORKTREES`, либо явно значится в `ALLOWLIST` скана с обоснованием, почему запись по этому пути для него недостижима (read-only сценарий или подмена самого `workspace.ensure`, не пути) — непропатченный `WORKTREES` не двигается вместе с `config.ROOT` (вычислен один раз при импорте) и уводит настоящий `git worktree add` в `.artel/worktrees` реального корня пульта, а не песочницы теста | `test_invariants.SandboxPatchedAttrsCoverWorktreesInvariantTest` | tasks/01M2CN465WEDCF6D77V37FJ82E/SPEC.md; docs/audits/code-revision-2026-09-12.md (CR-2026-09-12-1 ★), docs/audits/code-revision-2026-09-13.md (повтор) |
+| 38 | Удаление, переименование и ослабление тестов `tests/**/*.py` без мандата Оператора не проходят: переход `in_dev → verifying` отказывает именованным действием «переход отклонён: гейт неослабления тестов», гейт мержа тем же узлом сравнения переводит задачу в `escalated` до попытки merge. Находка — удалённый файл, пара переименования (`git diff -M`), исчезнувший из head тестовый метод изменённого файла и появившийся в head пропуск (`@skip`/`@skipIf`/`@skipUnless`/`@expectedFailure`/`@pytest.mark.skip`/`skipif`/`xfail`, вызов `self.skipTest(`/`pytest.skip(`), которого не было в base на том же имени; файл с нулём тестовых методов в base находкой не считается. Мандат — строка `Ослабление тестов разрешено: <пути и имена>` в `tasks/<id>/ANSWER-n.md`, ЧЕЙ ПОСЛЕДНИЙ КОММИТ доказанно не автокоммит артефактов шага роли (тот же рубеж, что у мандата зон в инварианте 34): роль не выписывает разрешение себе сама. Молчание git на переходе — отказ (fail-closed, ADR-0002), на мерже — fail-open, как у соседнего рубежа защищённых путей | `test_invariants.TestWeakeningNeedsTheOperatorTest`; `tests/test_test_integrity_gate.py`; `tests/test_guard_test_ast.py`; `tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests/` | tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md, требования 1-7; ADR-0002 (принцип целостности); строка бэклога П2 от 26.09.2026 «Гейт неослабления тестов в пульте» |
 
 ## На ревью — тестом не выражаются
 
```

## Приложение: инвариант 38 тестом (tests/test_invariants.py)

Инвариант выражается тестом без живого git (примитивы `gitcmd`
подменяются, как в соседних сценариях модуля), поэтому идёт первой
таблицей docs/invariants.md, а не строкой «на ревью — тестом не
выражаются». Класс прогнан на применённом патче: 3 passed.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 5a59ed79..dbd44a59 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -37,6 +37,7 @@ sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
 from orchestrator import (artel, budget, catalog, ci, cleanup,  # noqa: E402
                           config, fsm, fsm_advance, gitcmd, runner, stack,
                           store)
+from orchestrator.advance_gates import test_integrity  # noqa: E402
 from scripts import guard  # noqa: E402
 from tests.sandbox import (FakeProc, SpyRun, TmpRootTest, _stub_check_stack,  # noqa: E402
                            capture, capture_new_task_id,
@@ -2235,3 +2236,120 @@ class SandboxPatchedAttrsCoverWorktreesInvariantTest(unittest.TestCase):
             self._classes_missing_required("tests/synthetic.py", dirty))
         self.assertEqual(
             [], self._classes_missing_required("tests/synthetic.py", clean))
+
+
+class TestWeakeningNeedsTheOperatorTest(TmpRootTest):
+    """Инвариант 38 (docs/invariants.md): удаление, переименование и
+    ослабление тестов `tests/` без мандата Оператора не проходят ни
+    переход `in_dev → verifying`, ни гейт мержа (SPEC
+    01M3FQ2V77QNK95Z599DM124QN).
+
+    Живой git здесь не нужен и не заводится: предмет — что открыть рубеж
+    может только Оператор и что на находке он отказывает на ОБОИХ
+    маршрутах. Что рубеж встроен в тела `fsm_advance.in_dev` и
+    `fsm_merge_gate._cmd_approve_merge_gate`, держит
+    `tests/test_test_integrity_gate.py::GateWiringTest`; разбор настоящих
+    ответов git — остальные сценарии того же модуля и планка задачи.
+    """
+
+    TASK = "T001"
+    BRANCH = "task/t001-x"
+    ARTIFACT = "artifact/t001"
+    BASE = "basesha"
+    DELETED = "tests/test_protected.py"
+    SOURCE = ("import unittest\n\n\n"
+              "class ProtectedTest(unittest.TestCase):\n\n"
+              "    def test_one(self):\n        pass\n")
+    MANDATE = "Ослабление тестов разрешено: tests/test_protected.py"
+    ANSWER = "tasks/T001/ANSWER-1.md"
+
+    def setUp(self):
+        super().setUp()
+        store.create_schema(store.db())
+        self.conn = store.db()
+        store.insert_task(self.conn, self.TASK, "Задача", "in_dev",
+                          self.BRANCH, config.DEFAULT_TARGET, 25.0)
+        self.answer_text = None
+        self.answer_subject = f"{self.TASK}: ANSWER-1 — ответ Оператора"
+
+    def _show(self, ref, rel):
+        if (ref, rel) == (self.BASE, self.DELETED):
+            return self.SOURCE, ""
+        if (ref, rel) == (self.ARTIFACT, self.ANSWER) and self.answer_text:
+            return self.answer_text, ""
+        return None, "файла нет в этой ветке"
+
+    def _git(self, *args):
+        return subprocess.CompletedProcess(args, 0,
+                                           f"{self.answer_subject}\n", "")
+
+    @contextlib.contextmanager
+    def _branch_deleting_a_test(self):
+        answers = [self.ANSWER] if self.answer_text else []
+        with mock.patch.object(gitcmd, "diff_base", return_value=self.BASE), \
+             mock.patch.object(gitcmd, "diff_name_status",
+                               return_value=[("D", self.DELETED, None)]), \
+             mock.patch.object(gitcmd, "show", self._show), \
+             mock.patch.object(gitcmd, "ls_tree_files", return_value=answers), \
+             mock.patch.object(gitcmd, "git", self._git):
+            yield
+
+    def test_a_deleted_test_does_not_pass_the_transition(self):
+        """Ловит мутацию: обёртка `_test_integrity_gate_refuses` открыта
+        на находке — возвращает `False` либо не журналирует именованное
+        действие, и удаление файла тестов проходит `in_dev → verifying`
+        молча, как оно проходило до 01M3FQ2V77QNK95Z599DM124QN.
+
+        Что обёртка ВЫЗВАНА телом `in_dev`, этот сценарий не проверяет —
+        он зовёт её напрямую; подключение держит
+        `tests/test_test_integrity_gate.py::GateWiringTest`."""
+        box = []
+        with self._branch_deleting_a_test():
+            t = store.get_task(self.conn, self.TASK)
+            capture(lambda: box.append(
+                fsm_advance._test_integrity_gate_refuses(
+                    self.conn, self.TASK, t, self.ARTIFACT)))
+        self.assertTrue(box[0], "гейт обязан отклонить переход")
+        actions = [row["action"] for row in self.conn.execute(
+            "SELECT action FROM steps WHERE task_id=?", (self.TASK,))]
+        self.assertIn("переход отклонён: гейт неослабления тестов", actions)
+
+    def test_only_the_operator_mandate_opens_the_gate(self):
+        """Ловит мутацию: мандатом признаётся ЛЮБОЙ `ANSWER-n.md` с
+        нужной строкой, без сверки подписи его последнего коммита —
+        developer кладёт файл в собственный `tasks/<id>/` в своём же
+        шаге `in_dev`, автокоммит переносит его в ветку, и роль сама
+        себе разрешает ослабление (тот же класс, что у мандата зон)."""
+        self.answer_text = f"# Ответ\n\n{self.MANDATE}\nОснование: ADR-0002.\n"
+        self.answer_subject = (f"{self.TASK}: артефакты шага developer "
+                               f"(автокоммит оркестратора)")
+        with self._branch_deleting_a_test():
+            t = store.get_task(self.conn, self.TASK)
+            refusal = fsm_advance._test_integrity_gate(
+                self.conn, self.TASK, t, self.ARTIFACT)
+        self.assertIsNotNone(refusal, "автокоммит роли мандатом не считается")
+
+        self.answer_subject = f"{self.TASK}: ANSWER-1 — ответ Оператора"
+        with self._branch_deleting_a_test():
+            t = store.get_task(self.conn, self.TASK)
+            allowed = fsm_advance._test_integrity_gate(
+                self.conn, self.TASK, t, self.ARTIFACT)
+        self.assertIsNone(allowed, "мандат Оператора обязан снимать отказ")
+
+    def test_the_merge_gate_escalates_the_same_finding(self):
+        """Ловит мутацию: узел на маршруте мержа докладывает находку
+        одним возвратом, забыв `store.set_state` — задача остаётся в
+        `merge_gate` и уходит в main, хотя ручная сверка удалённых тестов
+        с Оператора этой задачей уже снята.
+
+        Подключение узла к телу `_cmd_approve_merge_gate` держит
+        `tests/test_test_integrity_gate.py::GateWiringTest`, не этот
+        сценарий."""
+        store.update_task(self.conn, self.TASK, state="merge_gate")
+        with self._branch_deleting_a_test():
+            escalated = test_integrity.merge_gate_escalates(
+                self.conn, self.TASK, "merge_gate", self.BRANCH,
+                self.ARTIFACT)
+        self.assertTrue(escalated)
+        self.assertEqual("escalated",
+                         store.get_task(self.conn, self.TASK)["state"])
```

## Предложения системе

- `scripts/guard.py` перевалил за 2000 строк и держит два разных
  предмета: структуру артефактов и ast-разбор тестов. Второе появилось
  как «единственный адрес» и обязано таким остаться, но имена в модуле
  уже сталкиваются: новый помощник пришлось назвать
  `_called_dotted_name`, потому что `_dotted_name` занят разбором
  упоминаний артефактов и определён НИЖЕ по файлу — коллизия, которую
  Python разрешает молча, перекрывая раннее определение поздним.
  Кандидат в бэклог: вынести ast-слой тестов в `scripts/test_ast.py` с
  реэкспортом из guard.
- Первая таблица `docs/invariants.md` несёт ДВА инварианта с номером 36
  (строки 66 и 67). Нумерация — адрес, по которому на строку ссылаются
  SPEC и ревью; дубль делает ссылку «инвариант 36» неоднозначной. Эта
  задача номер не трогала (правка нумерации — правка защищённого пути
  вне её предмета), но починить его стоит отдельной строкой бэклога.
- Класс «докстринг заявляет мутацию о ПОДКЛЮЧЕНИИ узла к маршруту, а сам
  тест зовёт функцию напрямую» стоит назвать в `skills/test-authoring.md`
  явно: заявка о встроенности проверяется ровно двумя способами — прогоном
  маршрута либо чтением его исходника (`inspect.getsource`), — и прямой
  вызов к ним не относится. Эта задача дала три экземпляра класса разом
  (замечание R1-F1), причём приём был автору известен: в планке AC-13
  `inspect.getsource` применён. Промахнулась не техника, а граница «что
  считается проверкой заявки»; скил её не проводит.
- Планка задачи (`tasks/<id>/acceptance_tests/`) после мержа регресс не
  сторожит — `pytest tests` её не собирает. Там, где планка оказывается
  ЕДИНСТВЕННЫМ местом, ловящим мутацию (здесь это было подключение обоих
  гейтов), строка `docs/invariants.md` ссылается на тест, которого в
  постоянном наборе нет. Кандидат в бэклог: правило «инвариант, чей
  единственный тест лежит в планке задачи, обязан получить двойник в
  `tests/`» — в `skills/review-checklist.md` либо машинной сверкой колонки
  «тест» первой таблицы `docs/invariants.md` с набором `tests/`.
