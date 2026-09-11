---
task: 01M1SHJX22EMEP4AJ9FFJJ09DC
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: approve без набора sha: сверка фиксации механикой; перечитывание budget_usd на гейте SPEC

## Подход

Обе части задачи меняют один и тот же диспетчер `orchestrator/fsm.py::_cmd_approve` (SPEC уже объяснила, почему они не режутся на отдельные подзадачи).

**Часть А (требования 1–3, AC-1..AC-5).** `fsm.confirm_fixation` сегодня
при `sha is None` безусловно печатает подсказку и возвращает `False` —
`fixation.read()` вызывается только ради текста подсказки, сравнения с
`tasks.fixed_sha` не происходит. Меняю ветку `sha is None`: читаю
`tasks.fixed_sha` из уже переданной `conn`/`task_id` и сравниваю с живым
`(current, clean)` от `fixation.read()` (тот же вызов, что уже есть) —
совпало и чисто → `True` (approve идёт дальше и переход сам зафиксирует
sha через `store.set_state` → `record_fixation`, AC-2 «журналирует sha»
закрывается этим существующим механизмом, отдельного журнала не пишу);
разошлось или грязно → именованный отказ (журнал + print, **не**
`sys.exit`) с обоими sha — мягкий `return False`, не исключение: тест
`tests/test_git_fixation.py::ExternalApproveDoesNotCommitOthersWorkInProgressTest.test_approve_without_sha_does_not_commit_another_tasks_wip`
(защищённый ADR-0002) ждёт именно мягкого возврата на этой ветке, не
`SystemExit` (см. приёмочный маркер `test_ac9_invariant_wording_and_regression.py`,
раздел «НАХОДКА для разработчика»). Ветка `sha is not None` (явный sha)
не трогается — AC-4.

Единственная существующая ADR-0002-планка, которая ловит именно
намеренную смену поведения (а не побочный эффект) —
`tests/test_git_fixation.py::ApproveByShaTest.test_approve_without_sha_prints_current_and_does_not_transition`:
она буквально утверждает «approve без sha никогда не переводит
состояние», хотя AC-2 требует обратного при совпадении и чистой копии.
Приёмочный маркер AC-9 явно разрешает и предписывает обновить именно
эту одну формулировку (не ослабляя сам инвариант 25 — «FSM решает по
зафиксированным хэшам» — остальные ассерты про несовпадение/грязноту/
`escalated` не трогаются). Переименовываю метод и меняю ассерт на
«совпадение+чистая копия → переход состоялся», сохраняя
`assertIn(sha, out)` — для этого `confirm_fixation` на успешной
автосверке печатает строку с живым sha, а не молчит.

`docs/invariants.md` (строка 25) и `docs/operator-session.md` (правило
«sha только копированием») — правки документации: инвариант правлю
прямо в этом коммите (это не защищённый путь `skills/`/`templates/`/
`gates.yaml`/`roles.yaml`/`.github/`, я могу его редактировать сам, а
не только Оператор), `operator-session.md` — по SPEC требование 3 идёт
unified-диффом приложением к PLAN, применяет Оператор, в кодовую ветку
не входит.

**Часть Б (требования 4–5, AC-6..AC-8).** `_cmd_approve` на `spec_gate`
уже читает `meta` (frontmatter SPEC с артефактной ветки или диска — та
же логика, что решает `tests_writing`/`in_dev`). Добавляю один вызов
`budget.apply_spec_budget(conn, t, meta)` сразу после того, как `meta`
получена (рядом с уже существующим сохранением `zones`) — та же
функция, что уже вызывает `fsm_advance.spec_writing` на переходе
`spec_writing -> spec_gate`. Идемпотентность (AC-7: потолок Оператора
не перебивается; AC-8: совпадающее значение не журналируется вторично)
уже целиком реализована внутри `apply_spec_budget` через `budget_source`
(значение из SPEC не применяется повторно, если `budget_source` уже
не `None` — не важно, `spec` или `operator`) — отдельного кода для этих
критериев не пишу, только сам вызов. Проверено ручным прогоном
приёмочных тестов AC-6/7/8 против этой логики (см. ниже).

## Шаги

1. `orchestrator/fsm.py`: правка `confirm_fixation` (сверка при
   `sha is None`) + добавление `from . import budget` в импорты модуля +
   вызов `budget.apply_spec_budget(conn, t, meta)` в ветке `spec_gate`
   `_cmd_approve`.
2. `tests/test_git_fixation.py`: обновление ОДНОГО метода
   `ApproveByShaTest.test_approve_without_sha_prints_current_and_does_not_transition`
   под новое поведение (AC-9); юнит-тесты на новую сверку
   `confirm_fixation` и на перечитывание бюджета на approve
   (дополнительно к уже залоченным `acceptance_tests/`).
3. `docs/invariants.md`: уточнение формулировки строки инварианта 25 под
   AC-9 (не ослабляя сам принцип).
4. `docs/operator-session.md`: unified-дифф (приложение к этому PLAN,
   без коммита в кодовую ветку) — удаление строки «sha только
   копированием» (AC-5).
5. `python3 scripts/codebase_map.py` — карта не меняется по существу
   (сигнатуры публичных функций `fsm.py`/`budget.py` не менялись), но
   правило скила требует прогона при правке `*.py` в `orchestrator/` —
   регенерирую тем же коммитом.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 (ветка `sha is not None` не тронута), 2 (AC-4 регресс) |
| 3 | 4 |
| 4 | 1, 2 |
| 5 | 1 (идемпотентность уже в `apply_spec_budget`), 2 |
| 6 (инвариант 25) | 3 |

## Влияние на систему

- `confirm_fixation` — общий узел для ВСЕХ четырёх гейтов
  `APPROVE_NEEDS_SHA` (`spec_gate`, `acceptance`, `merge_gate`,
  `escalated`): правка меняет поведение сразу для всех четырёх
  одинаково (не точечно для одного), это и требует AC-1/AC-2 —
  унифицированность. Явный путь `sha is not None` (T021, T021-планка
  01M1GHZTX9…) не тронут ни строкой — сверял построчно.
- Механизм отказа для новой ветки `sha is None` — мягкий `return False`
  (не `sys.exit`), в отличие от явного пути ниже, который продолжает
  `sys.exit`. Это осознанная асимметрия (не непоследовательность):
  единственный протестированный сценарий отказа на этой ветке в
  защищённом (ADR-0002) `ExternalApproveDoesNotCommitOthersWorkInProgressTest`
  требует мягкого возврата — переход к `sys.exit` здесь сломал бы
  неослабляемый тест без замены его чем-то равноценным (эскалация
  Оператору была бы правильным путём, если бы SPEC требовала именно
  `sys.exit`; SPEC этого не требует — «SPEC не предписывает механизм
  отказа», приёмочные маркеры AC-1/AC-3 явно это оговаривают).
- `budget.apply_spec_budget` вызывается теперь из ДВУХ точек
  (`spec_writing -> spec_gate` advance и `spec_gate` approve) — сама
  функция уже была написана с расчётом на повторный вызов
  («Ставит потолок — один раз и никогда поверх ручного», её
  собственный докстринг), второй вызов не меняет её контракт и не
  требует правки самой функции — только новая точка вызова.
  Границы применения не расширяю и не сужаю — после подтяжки main
  (см. «Возврат — конфликт подтяжки main (R3)» ниже) ADR-0014 часть 1
  (потолок ролей `ROLE_BUDGET_CAP=$100`) в ветке ЕСТЬ, значит применяю
  границы `apply_spec_budget` как есть, в её ТЕКУЩЕМ (пост-ADR-0014)
  виде, без собственной логики верхней границы — ровно та развилка,
  которую сама SPEC предвидела в «Не входит».
- Ни один существующий гейт/лимit/guard не ослаблен: `APPROVE_SHA_PREFIX_MIN`,
  явный путь sha, лимиты `accept_rejects`, guard-проверки артефактов —
  не тронуты.
- Откат: правка `confirm_fixation`/`_cmd_approve` — чистая функция без
  побочных состояний вне журнала; откат — `git revert` коммита кода,
  без миграций схемы БД (колонки не добавлялись).

## Риски

- Единственный риск, который проверял отдельно, — не сломать
  ADR-0002-защищённые тесты `tests/test_git_fixation.py`
  (`ApproveByShaTest`, `ExternalApproveDoesNotCommitOthersWorkInProgressTest`,
  остальные классы файла). Приёмочная планка (`test_ac9_invariant_wording_and_regression.py`,
  раздел «НАХОДКА для разработчика») уже разметила ровно эту зону
  заранее — следую её выводу: меняю формулировку одного метода, не
  ослабляя остальные.
- Прочие вызовы `fsm.cmd_approve(<id>)` без sha по кодовой базе (грепом
  проверено — `tests/test_invariants.py`, `test_acceptance_tests_flow.py`,
  `test_agent_failure.py`, `test_analyst_role.py`, `test_answer_gate.py`,
  `test_branch_freshness_gate.py`, `test_ci_status_kind_gate.py`,
  `test_step_cost.py`) все идут через `SpyRun`/`TmpRootTest` без
  реального git — `fixation.read()` там возвращает пустой sha, ветка
  `if not current: return True` отрабатывает как и раньше (правка их не
  касается — подтверждено чтением setUp каждого класса).

## Приложение: unified-дифф docs/operator-session.md (AC-5)

Удаление строки «sha только копированием» — правку применяет Оператор,
в кодовую ветку задачи не входит. `git apply --check` подтверждён на
чистом дереве этой ветки ПОСЛЕ подтяжки main (командой `git apply
--check <файл-с-диффом>` перед сдачей — файл диффа временный, удалён
после проверки командой `git clean -f`, само содержимое диффа приведено
ниже как приложение к этому PLAN.md). Номера строк хунка ниже —
актуальные для дерева ПОСЛЕ мержа main (см. «Возврат» ниже); диапазон
сдвинулся с `@@ -121,8 +121,6 @@` (до подтяжки) на `@@ -130,8 +130,6 @@`
из-за вставленных main строк выше по файлу.

```diff
--- a/docs/operator-session.md
+++ b/docs/operator-session.md
@@ -130,8 +130,6 @@
 - Команды пульта — только из главной копии репозитория
   (инвариант T056 отклонит прочее); git в worktree задачи —
   через `git -C <путь>`, не через смену каталога.
-- `approve` без sha печатает зафиксированный sha — брать его
-  копированием из вывода, никогда не набирать по памяти.
 - Помощник мержа (approve-по-sha + ожидание CI) запускать только на
   задаче в `merge_gate`: на эскалированной задаче `approve` означает
   возврат в работу, и цепочка молча увела две задачи в in_dev (05.09).
```

## Возврат — конфликт подтяжки main (R3)

Причина возврата (см. `ANSWER-1.md`): конфликт подтяжки main —
`orchestrator/fsm.py` и `docs/codebase-map.md`. Main ушёл на 374 коммита
вперёд с момента ветвления, из них ключевые для этой задачи: R3
(`01M1TKP08PKB87K8772H69GCXJ`) разобрала `fsm.py` — `pull.py` вынесен
отдельно, `_cmd_approve` стал таблицей «состояние -> обработчик»
(`_approve_spec_gate`/`_approve_acceptance`/`_approve_merge_gate`/
`_approve_escalated`); отдельно — ADR-0014 часть 1
(`01M1THKTJ7YT1K410G1KS17MK6`) добавила потолок ролей `ROLE_BUDGET_CAP`
в `apply_spec_budget`/`spec_budget`.

Сделано (`git merge origin/main`, коммит слияния `79b26a6f`):

1. Импорты `fsm.py` — взял сторону main (`pull`, без `acceptance`/
   `workspace` — R3 их вынесла, в файле они больше не используются;
   `budget` в списке уже был у main независимо от этой задачи).
2. `_cmd_approve` — взял диспетчерскую таблицу main целиком (удалил
   старую inline-цепочку `if state == ...` со СВОЕЙ версией
   `spec_gate`/`acceptance` — она стала лишней дважды: тем же кодом,
   что уже вынесен в `_approve_spec_gate`/`_approve_acceptance`).
   Сверку фиксации без sha (требования 1–3, `confirm_fixation`) трогать
   не пришлось — это отдельная функция, вызываемая ДО таблицы, R3 её
   не касалась. Перечитывание `budget_usd` (требования 4–5) перенёс
   ИЗ удалённой inline-ветки `spec_gate` В main-функцию
   `_approve_spec_gate` — тот же вызов `budget.apply_spec_budget(conn,
   t, meta)` сразу после `store.update_task(conn, task_id,
   zones=meta.get("zones"))`, до `_print_spec_gate_calibration_hint`
   (эта функция читает `t["budget_usd"]` — оставил перечитывание ПЕРЕД
   ней, чтобы подсказка калибровки видела уже применённое значение).
3. `docs/codebase-map.md` — взял сторону main (`git checkout --theirs`),
   перегенерировал `python3 scripts/codebase_map.py` штатной командой
   (правка `orchestrator/fsm.py` того требует).
4. `docs/operator-session.md` — диф из приложения выше пересобран под
   новые номера строк (проверено `git apply --check` после подтяжки).

Планка задачи прогнана СИНХРОННО после слияния (пофайлово, в переднем
плане, `python3 <файл>.py -v`, не `unittest discover`/`-m unittest` на
каталоге — хук курируемого слоя роли отклоняет прогон целого набора
внутри шага):

- `test_ac1_diverged_or_dirty_live_sha_blocks_approve.py` — 2/2 OK
- `test_ac1_matching_live_sha_lets_approve_through.py` — 1/1 OK
- `test_ac2_matching_fixation_auto_confirms.py` — 2/2 OK
- `test_ac3_diverged_or_dirty_refuses_named.py` — 2/2 OK
- `test_ac4_explicit_sha_semantics_unchanged.py` — 3/3 OK
- `test_ac6_spec_gate_approve_rereads_budget.py` — **1/2**, см.
  «Эскалация» ниже
- `test_ac7_differing_spec_budget_does_not_override.py` — 1/1 OK
- `test_ac7_matching_spec_budget_does_not_override.py` — 1/1 OK
- `test_ac8_changed_value_is_journaled.py` — 1/1 OK
- `test_ac8_unchanged_value_no_duplicate_journal_record.py` — 1/1 OK
- `test_ac9_invariant_wording_and_regression.py` — 0 тестов (manual,
  зелёный с рождения)

Регрессия защищённых ADR-0002 тестов и соседних планок, тронутых
рефакторингом R3/ADR-0014 (пофайлово, в переднем плане):
`tests/test_git_fixation.py` — 39/39 OK; `tests/test_spec_budget.py` —
42/42 OK; `tests/test_cmd_approve_dispatch.py` +
`tests/test_zones_approve.py` — 9/9 OK; `tests/test_fsm_advance_gate_smoke.py`
+ `tests/test_invariants.py` — 55/55 OK (включает
`SpecCeilingRespectsRoleBudgetCapTest`, независимо покрывающий тот же
потолок ролей). Полный `tests/` не гонял (запрещено скилом, гоняет CI).

## Предложения системе

- `orchestrator/canary.py:540` несёт комментарий «`fsm.cmd_approve`:
  тот на `escalated` требует sha» — после этой задачи формулировка
  устарела (approve может пройти и без явного sha при совпадении).
  `canary.py` вне зоны этой задачи, поэтому не правлю — комментарий
  сам по себе не влияет на поведение, но следующая задача в этой зоне
  может обновить формулировку заодно.
- Класс «залоченный acceptance-тест устаревает не от рефакторинга
  fsm.py, а от независимого мержа в main» (эта же эскалация, ниже) —
  ANSWER-1 предупреждала конкретно про «старые якоря fsm.py»; здесь
  устарела не структура fsm.py, а формулировка сообщения в чужом,
  уже смерженном и отревьюженном модуле (`budget.py`, ADR-0014).
  Стоит явно продолжить в `docs/operator-session.md`/скиле
  test-authoring: приёмочный тест, фиксирующий текст стороннего отказа
  (`assertIn("<текст>", out)`), не пережил независимый мерж соседней
  ADR-задачи в main, случившийся МЕЖДУ выпиской SPEC и мержем этой
  задачи — тот же класс риска, что и «планка ссылается на устаревшие
  анкеры fsm.py», просто на другом модуле.

## Эскалация

**Вопросы:**

1. (блокирует) Залоченный приёмочный тест
   `tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/acceptance_tests/test_ac6_spec_gate_approve_rereads_budget.py:82`
   (`ApproveOnSpecGateRereadsBudgetFromArtifactBranchTest.test_ac6_applied_value_uses_apply_spec_budget_bounds`)
   проверяет `self.assertIn("выше дефолта", out)` — формулировку отказа
   `budget.spec_budget()` ДО ADR-0014. После подтяжки main в этой ветке
   уже действует ADR-0014 часть 1 (`01M1THKTJ7YT1K410G1KS17MK6`, коммит
   `52aa4de3`, смержена в main НЕЗАВИСИМО от этой задачи, ДО её
   возврата из эскалации): `spec_budget()` сравнивает с
   `ROLE_BUDGET_CAP=$100`, а не с `DEFAULT_BUDGET_USD`, и печатает
   «выше потолка ролей $100.00 — поднятие выше только командой budget
   (Оператором)» вместо «выше дефолта». Сумма из теста ($500) отклоняется
   в обоих случаях — различается только ТЕКСТ сообщения. Моя же SPEC
   (раздел «Не входит») явно предвидела эту развилку: «если к моменту
   мержа этой задачи ADR-0014 уже слита, `apply_spec_budget` перечитывает
   в её границах (до `ROLE_BUDGET_CAP`)» — она слита, значит корректно
   оставить `apply_spec_budget`/`spec_budget` как есть (я их не менял).
   Разрешить правку этой ОДНОЙ строки залоченного теста штатным каналом
   `amend-tests` (`orchestrator/amend.py::cmd_amend_tests`), заменив
   `"выше дефолта"` на `"выше потолка ролей"`?
   - Варианты: (а) да, поправить строку через `amend-tests` — на
     следующем шаге я это сделаю и продолжу к `status: ready`; (б) нет,
     правку внесёт сам Оператор/другая роль; (в) считать AC-6
     невыполнимым в этой формулировке и снять критерий ADR-решением.
   - Дефолт при молчании: (а) — вывод прямо следует из текста самой
     SPEC («Не входит»), и `tests/test_spec_budget.py` (не залоченный,
     уже отревьюженный вместе с ADR-0014) независимо подтверждает
     формулировку «выше потолка ролей» как текущую, правильную.

**Контекст:**

- Подтянул main (`git merge origin/main`, коммит слияния `79b26a6f`),
  разрешил оба конфликта (`orchestrator/fsm.py`, `docs/codebase-map.md`)
  — подробности и построчный список изменений в разделе «Возврат —
  конфликт подтяжки main (R3)» выше.
- Прогнал приёмочную планку задачи целиком (10 файлов, 16 методов):
  15 зелёных, 1 красный (см. вопрос 1). Прогнал регрессию защищённых
  ADR-0002 тестов (`tests/test_git_fixation.py`, 39/39), бюджетных
  тестов (`tests/test_spec_budget.py`, 42/42) и диспетчера approve
  (`tests/test_cmd_approve_dispatch.py`, `tests/test_zones_approve.py`,
  9/9) — все зелёные, класс сверки фиксации и класс перечитывания
  budget_usd отработали корректно после переноса кода в
  R3-декомпозированные обработчики.
- Не правил ни `orchestrator/budget.py` (чужое, уже смерженное и
  отревьюженное поведение ADR-0014, не моя зона правки по факту, хотя
  формально в zones этой SPEC), ни залоченный acceptance-тест (правило
  `tasks/T023`) — оба пути запрещены мне без решения Оператора.

**Блокирует:** не могу поставить `status: ready` — приёмочная планка
задачи не полностью зелёная, а её правка (даже одной строки) требует
явного решения Оператора (правило `tasks/T023`) и штатно идёт каналом
`amend-tests`, которым распоряжается не разработчик.

## Возврат — правка планки AC-6 (ADR-0014)

Ответ Оператора (`ANSWER-2.md`): вариант (а) — планка поправлена штатным
каналом `amend-tests` самим Оператором (11.09, лок сдвинут `db814ba3` ->
`45c18dee`): в `test_ac6_spec_gate_approve_rereads_budget.py:82` строка
`assertIn("выше дефолта", out)` заменена на `assertIn("выше потолка
ролей", out)` — единственная правка планки, код (`apply_spec_budget`/
`spec_budget`) не тронут, как и было заложено в SPEC («Не входит»).
Никакой правки кода в этом ходе не потребовалось — код с прошлого хода
(`d4cd1ecd`, слияние `79b26a6f`) не менялся.

Прогон приёмочной планки задачи синхронно, пофайлово (12 файлов, из них
2 — `test_ac5_operator_session_diff.py` и `test_ac9_invariant_wording_
and_regression.py` — manual/0 тестов по конструкции самой планки, см.
их докстринги; 14 исполняемых методов):

- `test_ac1_diverged_or_dirty_live_sha_blocks_approve.py` — 2/2 OK
- `test_ac1_matching_live_sha_lets_approve_through.py` — 1/1 OK
- `test_ac2_matching_fixation_auto_confirms.py` — 2/2 OK
- `test_ac3_diverged_or_dirty_refuses_named.py` — 2/2 OK
- `test_ac4_explicit_sha_semantics_unchanged.py` — 3/3 OK
- `test_ac5_operator_session_diff.py` — 0 тестов (manual), зелёный
- `test_ac6_spec_gate_approve_rereads_budget.py` — **2/2 OK** (после
  правки планки — оба метода, включая ранее красный
  `test_ac6_applied_value_uses_apply_spec_budget_bounds`)
- `test_ac7_differing_spec_budget_does_not_override.py` — 1/1 OK
- `test_ac7_matching_spec_budget_does_not_override.py` — 1/1 OK
- `test_ac8_changed_value_is_journaled.py` — 1/1 OK
- `test_ac8_unchanged_value_no_duplicate_journal_record.py` — 1/1 OK
- `test_ac9_invariant_wording_and_regression.py` — 0 тестов (manual),
  зелёный

Итого: 16/16 (14 исполняемых + 2 manual) — планка полностью зелёная.

Регрессия по правилам скила (модули, затронутые диффом задачи: `git
diff --stat 9ba3bf62 HEAD -- orchestrator/ tests/ docs/` называет только
`orchestrator/fsm.py` и `tests/test_git_fixation.py`; `budget.py` в
диффе задачи нет — только новая точка вызова уже существующей функции
из `fsm.py`), каждый модуль отдельным прогоном в переднем плане:

- `tests/test_git_fixation.py` (ADR-0002-защищённый, класс
  approve-по-sha) — 39/39 OK
- `tests/test_spec_budget.py` (класс потолка задачи, который теперь
  дополнительно перечитывается на approve spec_gate) — 42/42 OK
- `tests/test_cmd_approve_dispatch.py` + `tests/test_zones_approve.py`
  (диспетчер `_cmd_approve`, куда включена правка) — 9/9 OK
- `tests/test_fsm_advance_gate_smoke.py` + `tests/test_invariants.py`
  (смоук гейтов R2/R3 и инварианты, включая
  `SpecCeilingRespectsRoleBudgetCapTest` — независимое покрытие того же
  потолка ролей) — 55/55 OK

Полный набор `tests/` в шаге не гонял (запрещено скилом — гоняет CI на
каждый пуш ветки); гонял планку задачи целиком плюс тесты всех модулей,
затронутых диффом.

`python3 scripts/codebase_map.py` прогнан для проверки — карта не
меняется по существу (в этом ходе не было ни одной правки `*.py`,
только правка теста через `amend-tests` Оператором и обновление этого
PLAN.md); единственное отличие — `built_at_sha` на текущий HEAD, что
является побочным эффектом самого запуска генератора после предыдущего
коммита карты, а не следствием кода этой задачи — не коммичу этот
файл, чтобы не гоняться за собственным хвостом (карту на merge
регенерирует и коммитит оркестратор из своей точки, ADR-0003/T042).

Код в кодовую ветку не коммичу — коммитить нечего: правка теста ушла
отдельным коммитом Оператора через `amend-tests` (лок `45c18dee`), а
код задачи (`orchestrator/fsm.py`, `tests/test_git_fixation.py`) уже
закоммичен в предыдущем ходе (`d4cd1ecd`).

## Возврат — инвариант 25 правит Оператор

Причина возврата (`ANSWER-3.md`): гейт зон отклонил advance —
`docs/invariants.md` не входит в заявленные `zones` этой SPEC и не
входит в `COMMON_ZONES`; я правил его самостоятельно в шаге
«Возврат — конфликт подтяжки main (R3)» (перенёс формулировку строки
25 в рамках требования 6), хотя правку инвариантов по факту вносит
только Оператор. Решение Оператора 11.09: инварианты меняет только
Оператор, разработчик этот файл не правит.

Сделано:

- `git checkout origin/main -- docs/invariants.md` — строка 25
  возвращена к формулировке origin/main (до правки этого шага); диф
  файла к origin/main теперь пуст. Формулировку строки Оператор внесёт
  сам отдельным коммитом в main после мержа (требование 6 SPEC
  исполняется Оператором, не ролью — как и было указано в ANSWER-3).
- Код (`orchestrator/fsm.py`) и `tests/test_git_fixation.py` не
  менялись — правка ANSWER-3 касается только `docs/invariants.md`.
- AC-9 (manual) в приёмочной планке не трогал — Оператор сверит новую
  формулировку инварианта сам на приёмке (её вносит он же).

Прогон приёмочной планки задачи синхронно, пофайлово, в переднем
плане (14 исполняемых методов + 2 manual — `test_ac5_operator_session_diff.py`,
`test_ac9_invariant_wording_and_regression.py`):

- `test_ac1_diverged_or_dirty_live_sha_blocks_approve.py` — 2/2 OK
- `test_ac1_matching_live_sha_lets_approve_through.py` — 1/1 OK
- `test_ac2_matching_fixation_auto_confirms.py` — 2/2 OK
- `test_ac3_diverged_or_dirty_refuses_named.py` — 2/2 OK
- `test_ac4_explicit_sha_semantics_unchanged.py` — 3/3 OK
- `test_ac6_spec_gate_approve_rereads_budget.py` — 2/2 OK
- `test_ac7_differing_spec_budget_does_not_override.py` — 1/1 OK
- `test_ac7_matching_spec_budget_does_not_override.py` — 1/1 OK
- `test_ac8_changed_value_is_journaled.py` — 1/1 OK
- `test_ac8_unchanged_value_no_duplicate_journal_record.py` — 1/1 OK

Итого: 16/16 (14 исполняемых + 2 manual) — планка полностью зелёная.

Регрессия: `tests/test_git_fixation.py` (ADR-0002-защищённый, класс
approve-по-sha; единственный модуль, затронутый диффом этого хода
помимо самого `docs/invariants.md`, которое кодом не является) —
39/39 OK. `tests/test_invariants.py` содержит только структурный
`InvariantsTableWellFormedTest`-класс проверок (число/формат строк
таблицы), а не сверку текста конкретной строки 25 — ревёрт этой
правки не меняет его исход (проверено грепом: строка 25 нигде не
цитируется дословно в тестах). Полный набор `tests/` в шаге не гонял
(запрещено скилом — гоняет CI на каждый пуш ветки).

`python3 scripts/codebase_map.py` не прогонял — в этом ходе не было ни
одной правки `*.py` (правка затронула только `docs/invariants.md`),
регенерация не требуется.

Коммичу `docs/invariants.md` (ревёрт к origin/main) в кодовую ветку
задачи отдельным коммитом.

`status: ready`.

## Возврат — подтяжка main после hotfix №19 (CI на устаревшей голове)

Причина возврата: CI прогона `pull_request` был красным по СНИМКУ ветки
ДО правки main 11.09 (`f80bde10`, оператор: REVIEW.md 01M1GCHKG8 —
строка R6-F1 приведена к шести колонкам, hotfix №19) — повторная
попытка прогона брала старый merge-коммит вместо новой головы. Код не
менять, только подтянуть main (то же указание, что уже отработано в
шаге «Возврат — конфликт подтяжки main (R3)» выше).

Сделано:

- `git fetch origin main` — HEAD отставал от `origin/main` на 9
  коммитов (в т.ч. `f80bde10` — сама правка hotfix №19 — и стоп-кран
  волны часть 2, 01M1THKRK8HPXA7Y2SRB0RFTN2).
- `git merge origin/main` (коммит слияния `bf80dde2`) — единственный
  конфликт: `docs/codebase-map.md` (генерируемый файл, конфликтует на
  каждом слиянии по построению). `orchestrator/fsm.py` и
  `tests/test_git_fixation.py` — те же файлы, что правит эта задача —
  слились БЕЗ конфликта; сверено отдельно (`git diff origin/main --
  orchestrator/fsm.py tests/test_git_fixation.py` пуст после слияния) —
  код задачи с main не разошёлся.
- Конфликт `docs/codebase-map.md` разрешён взятием стороны main
  (`git checkout --theirs`) и штатной регенерацией
  `python3 scripts/codebase_map.py` (слияние затронуло `orchestrator/
  auto.py`, `orchestrator/catalog.py`, `orchestrator/config.py`,
  `orchestrator/doctor/cli.py`, `orchestrator/runner.py` — правка
  `*.py` из main требует регенерации тем же шагом, класс из скила).
  Диф после регенерации — только строка `built_at_sha`.
- Код самой задачи (`orchestrator/fsm.py`, `tests/test_git_fixation.py`,
  `docs/invariants.md`) в этом ходе не менялся — только подтяжка.

Прогон приёмочной планки задачи синхронно, пофайлово, в переднем
плане (14 исполняемых методов + 2 manual — `test_ac5_operator_
session_diff.py`, `test_ac9_invariant_wording_and_regression.py` — по
конструкции самой планки, см. их докстринги):

- `test_ac1_diverged_or_dirty_live_sha_blocks_approve.py` — 2/2 OK
- `test_ac1_matching_live_sha_lets_approve_through.py` — 1/1 OK
- `test_ac2_matching_fixation_auto_confirms.py` — 2/2 OK
- `test_ac3_diverged_or_dirty_refuses_named.py` — 2/2 OK
- `test_ac4_explicit_sha_semantics_unchanged.py` — 3/3 OK
- `test_ac6_spec_gate_approve_rereads_budget.py` — 2/2 OK
- `test_ac7_differing_spec_budget_does_not_override.py` — 1/1 OK
- `test_ac7_matching_spec_budget_does_not_override.py` — 1/1 OK
- `test_ac8_changed_value_is_journaled.py` — 1/1 OK
- `test_ac8_unchanged_value_no_duplicate_journal_record.py` — 1/1 OK

Итого: 16/16 (14 исполняемых + 2 manual) — планка полностью зелёная.

Регрессия, модули, затронутые диффом слияния (пофайлово, в переднем
плане):

- `tests/test_git_fixation.py` (ADR-0002-защищённый, класс
  approve-по-sha) — 39/39 OK
- `tests/test_spec_budget.py` + `tests/test_cmd_approve_dispatch.py` +
  `tests/test_zones_approve.py` (класс потолка задачи и диспетчер
  approve) — 51/51 OK
- `tests/test_auto_cycle.py` + `tests/test_catalog_wave_breaker_status.py`
  + `tests/test_doctor_wave_breaker.py` + `tests/test_runner_wave_breaker.py`
  (модули, принесённые слиянием main — стоп-кран волны часть 2) —
  61/61 OK

Полный набор `tests/` в шаге не гонял (запрещено скилом — гоняет CI на
каждый пуш ветки).

Коммит слияния `bf80dde2` — `01M1SHJX22EMEP4AJ9FFJJ09DC: подтяжка
main` — уже в кодовой ветке задачи. Коммитить более нечего: код задачи
не менялся, только голова ветки продвинута.

`status: ready`.
