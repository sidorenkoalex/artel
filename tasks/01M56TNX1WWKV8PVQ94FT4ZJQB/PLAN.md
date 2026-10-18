---
task: 01M56TNX1WWKV8PVQ94FT4ZJQB
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Гейт неослабления: async-тесты и пропуски через метку и модуль

## Подход
Распознавание пропуска — по-прежнему в `scripts/guard.py` (единый адрес
правила «что такое пропуск»), сравнение и послабление — в узле
`orchestrator/advance_gates/test_integrity.py`. Существующие
`guard.test_skip_markers` и `test_integrity._excused_skips(node)` не
меняют контракта (на них опираются `tests/test_guard_test_ast.py`,
`tests/test_test_integrity_gate.py`); новые формы идут вторым слоем:

- `guard.resolved_skip_markers(source, modules)` → {имя: [SkipOccurrence]}:
  - декоратор-метка `@имя` (голое `ast.Name`) метода или класса с
    тестами, где имя связано присваиванием верхнего уровня `имя = <марка
    пропуска>` (то же правило последнего сегмента `SKIP_DECORATOR_NAMES`,
    что у прямого декоратора; последнее связывание побеждает) либо
    `from <модуль> import имя` (без `as`, level 0) из модуля, который
    `TestModules.module_path` признаёт областью тестов: у артели — любой
    `tests/**`, у внешнего проекта — `weakening_scope` с `workdir`
    (механизм части 1). Метки модуля кэширует новый `TestModules.labels`;
  - `pytestmark = <марка>` / список / кортеж — каждая марка пропуска на
    каждом тестовом методе файла;
  - `pytest.skip(` и `*.importorskip(` в любом операторе модуля вне тел
    функций/классов на любой глубине (`try`/`except`/`with`), с
    признаком «внутри ветки `if`/`else`» — на каждом тестовом методе файла.
  Маркер метки и `pytestmark` несёт `ast.unparse` значения
  (`@requires_pg = pytest.mark.skip(reason='…')`): смена значения при
  прежнем `@requires_pg` — новый маркер на прежнем имени, то есть та же
  находка «появившийся маркер», без отдельного канала (требование 3).
- `test_integrity._skip_markers` сливает оба слоя по стороне (модули
  стороны base/head из `_side_modules`); `_file_findings` получил
  `modules`; `_excused_skips(node, extra)` проверяет вхождения нового
  слоя тем же правилом «каждое вхождение годится»: метка/`pytestmark` —
  `_decorator_occurrence` (условный вид + аргумент условия + причина-
  константа), вызов модуля — только внутри `if`/`else` с причиной-
  константой (`pytest.skip` — позиционно или `reason=`, `importorskip` —
  только `reason=`). Послабление — только новому методу; класс — всегда
  находка (прежнее правило ключа-класса).
- Импортёры вне диффа (требования 3, 5): `guard.skip_label_values` по
  обе стороны каждого файла диффа даёт имена меток, сменивших значение;
  `_helper_callers` (тот же `git grep -w`, у внешнего — всё дерево с
  отсевом областью) находит файлы, которые сравниваются как неизменные
  (текст тот же) модулями своей стороны — маркер импортированной метки
  различается. Молчание git — `_git_failure`, как у остальных чтений узла.
- `guard.TEST_METHOD`: `^\s*(?:async\s+)?def\s+…` (требование 6).
- Инвариант 38 — приложением к PLAN (путь защищён, требование 8).

Оценка бюджета SPEC не пересматривается.

## Шаги
1. `scripts/guard.py`: `TEST_METHOD` с `async`; `SkipOccurrence`,
   `_module_labels`, `skip_label_values`, `_imported_labels`,
   `_module_level_calls`, `_pytestmark_elements`, `resolved_skip_markers`,
   `TestModules.labels`.
2. `orchestrator/advance_gates/test_integrity.py`: `_resolved_reason`,
   `_excused_skips(node, extra)`, `_skip_markers`, `_file_findings(...,
   modules)`, поиск импортёров изменённой метки в `_compare`.
3. `tests/test_guard_test_ast.py::ResolvedSkipMarkersTest` — три границы,
   не покрытые долгоживущими файлами (переприсваивание метки, не-пропуск
   `pytest.mark.slow`, вызовы в телах функций/классов не уровень модуля);
   каждый проверен мутацией (все три красные на своей мутации).
4. Приложение к `docs/invariants.md` (ниже), `git apply --check` на чистом
   дереве ветки — проходит.
5. `python3 scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 2 |
| 3 | 1, 2 |
| 4 | 1, 2 |
| 5 | 2 (режим артели и внешнего проекта — один путь `_compare`) |
| 6 | 1 |
| 7 | долгоживущие файлы задачи + шаг 3 |
| 8 | 4 |

## Влияние на систему
- Только усиление находок гейта неослабления (инвариант 38): прежние
  маркеры и послабление не меняются, новые формы добавляют маркеры. Метка
  без изменений по обе стороны даёт одинаковый маркер — существующие
  тесты с метками находок не получат (в `tests/` артели меток и
  модульных пропусков сейчас нет — `git grep`).
- Поиск импортёров — лишний `git grep` только когда в диффе метка
  сменила значение.
- `TEST_METHOD` читают `acceptance.py` (число долгоживущих методов) и
  `dry_run.py` — `async def test_` теперь считается и там, что и есть
  требование 6.
- `merge_after` не меняется.
- Откат — revert merge-коммита задачи; приложение к инварианту
  откатывается вместе с ним.

Прогоны: `tests/test_01m56tnx1wwkv8pvq94ft4zjqb_*.py` — 11 passed;
`test_test_integrity_gate`, `test_guard_test_ast`,
`test_01m56tnty7hec85mc940kzr1zj_helper_scope`,
`test_01m45fjd46bx45vhc36s4vs9qn_declared_change`,
`test_guard_assertion_changes`,
`test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation` — 144 passed;
`suite-run` №1 (полный набор) — зелёный: 5790 прошло, 0 упало.

## Риски
- Маркер со значением длиннее прежнего текста находки; причина со «; » в
  значении разрежет элемент detail на два — читаемость, не пропуск.
- `from … import x as y`, аннотированное присваивание, `pytestmark +=` —
  известные пробелы SPEC («Не входит»).

## Приложение: docs/invariants.md — инвариант 38, формы пропуска этой задачи
Применимость проверена: `git apply --check` на чистом дереве ветки — код 0.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index 9e50e3aa..7dc02831 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -65,7 +65,7 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 35 | Тесты не читают сеть по DNS-имени: ни один файл `tests/**/*.py` не несёт адреса вида `http(s)://<DNS-имя>`, кроме `localhost`/`127.0.0.1` (допустимые исключения — именованная константа с обоснованием на каждую строку); сетевые git-команды (`fetch`/`push`/`ls-remote`/`clone`) с таким адресом перехватываются `tests/sandbox.py::TmpRootTest` мгновенным именованным отказом («сеть в тестах запрещена: `<команда>` `<адрес>`»), без обращения к сети | `test_invariants.NoNetworkAddressesInTestsTest`; `refs/artifacts/01M1QHQ277PQQA894X97RVEX9Y:tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests/test_ac1_network_command_interception.py`, `test_ac2_local_bare_repo_not_blocked.py`, `test_ac9_network_interception_speed.py` (приёмочные тесты задачи по адресу ссылки после мержа не исполняются, ADR-0018 п.2) | refs/artifacts/01M1QHQ277PQQA894X97RVEX9Y:tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md, требования 1, 3 (инцидент 05.09: `git fetch -q https://example.invalid/sled main` висел минуты на DNS-резолвере при обрыве сети — фикстурный адрес `sled`-target'а в `tests/test_git_fixation.py`) |
 | 36 | Прогон CI существует для каждого пуша в `main` и `task/**`: секция `on.push` в `.github/workflows/ci.yml` не несёт фильтров `paths`/`paths-ignore`; лишние на данном классе пуша проверки снимаются условием на job (статус `skipped`, зелёный для `ci.GREEN`), причём jobs `python` и `python-min` не исключают `refs/heads/task/` и не строятся как `== 'true'` по output соседнего job (fail-open). Пуш документов (`artifact/**`) прогона CI не требует и не получает: ни триггер, ни условие job не ссылаются на `artifact/`, а документы задачи проверяют гейты пульта на переходах и гейт мержа (`guard` полной проверкой, без мягкого режима для черновиков) | `test_invariants.CiJobsByPushClassInvariantTest` | ADR-0016; ADR-0021 пп. 4, 12 (снятие CI на пуше документов с заменой гейтами переходов, решение Оператора); `ci.verifying_status`/`ci.branch_status` читают пуш без прогона как «проверок нет вовсе» и держат задачу до потолка ожидания (инвариант 19) |
 | 37 | Класс `tests/*.py` с собственным `PATCHED_ATTRS` для `tests.sandbox.TmpRootTest` патчит `config.WORKTREES`, либо явно значится в `ALLOWLIST` скана с обоснованием, почему запись по этому пути для него недостижима (read-only сценарий или подмена самого `workspace.ensure`, не пути) — непропатченный `WORKTREES` не двигается вместе с `config.ROOT` (вычислен один раз при импорте) и уводит настоящий `git worktree add` в `.artel/worktrees` реального корня пульта, а не песочницы теста | `test_invariants.SandboxPatchedAttrsCoverWorktreesInvariantTest` | refs/artifacts/01M2CN465WEDCF6D77V37FJ82E:tasks/01M2CN465WEDCF6D77V37FJ82E/SPEC.md; docs/audits/code-revision-2026-09-12.md (CR-2026-09-12-1 ★), docs/audits/code-revision-2026-09-13.md (повтор) |
-| 38 | Удаление, переименование и ослабление тестов `tests/**/*.py` без мандата Оператора не проходят: переход `in_dev → verifying` отказывает именованным действием «переход отклонён: гейт неослабления тестов», гейт мержа тем же узлом сравнения переводит задачу в `escalated` до попытки merge. Находка — удалённый файл, пара переименования (`git diff -M`), исчезнувший из head тестовый метод изменённого файла и появившийся в head пропуск (`@skip`/`@skipIf`/`@skipUnless`/`@expectedFailure`/`@pytest.mark.skip`/`skipif`/`xfail`, вызов `self.skipTest(`/`pytest.skip(`), которого не было в base на том же имени; файл с нулём тестовых методов в base находкой не считается. Утверждение тестового метода, сохранившего имя, которого в head нет в той же нормальной форме (оператор `assert`, вызов `assert*`/`fail`, `pytest.raises`/`pytest.warns`; сообщение, локальные имена и корень импортированного модуля не различаются), — находка (SPEC 01M45FJD46BX45VHC36S4VS9QN): смена утверждений вне раздела SPEC «Меняемое поведение» и ослабление (утверждений меньше, другой вид, литерал заменён вычисленным значением, допуск шире, якорь регулярного выражения снят, граница в разрешающую сторону) отказывают переходу и эскалируют мерж; проходит только смена ожидания из перечня записи approve гейта SPEC «объявлена смена поведения тестов» с совпавшими парами «было → стало», строгостью не ниже прежней и двусторонним прогоном на переходе (новая версия теста падает на дереве базы, старая — на дереве головы, оба раза на утверждении; гейт мержа сверяет запись «двусторонний прогон пройден» с текущей головой ветки). Храповик: общее число тестовых методов и утверждений диффа `tests/` в голове не меньше, чем в базе. Запись «изменены утверждения тестов (наблюдение)» на обоих рубежах сохраняется, к ней добавлена «утверждения тестов: исход рубежа». Мандат — строка `Ослабление тестов разрешено: <пути и имена>` в `tasks/<id>/ANSWER-n.md`, ЧЕЙ ПОСЛЕДНИЙ КОММИТ в истории ссылки документов `refs/artifacts/<id>` доказанно не автокоммит артефактов шага роли (тот же рубеж, что у мандата зон в инварианте 34): роль не выписывает разрешение себе сама. Молчание git на переходе — отказ (fail-closed, ADR-0002), на мерже — fail-open, как у соседнего рубежа защищённых путей | `test_invariants.TestWeakeningNeedsTheOperatorTest` (в том числе `test_an_undeclared_assertion_change_needs_the_operator`); `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`; `tests/test_guard_assertion_changes.py`; `tests/test_test_integrity_gate.py` (в том числе `AssertionObservationTest`); `tests/test_guard_test_ast.py` (в том числе `ChangedAssertionsTest`); `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`; `refs/artifacts/01M3FQ2V77QNK95Z599DM124QN:tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests/` (приёмочные тесты задачи по адресу ссылки после мержа не исполняются, ADR-0018 п.2) | refs/artifacts/01M3FQ2V77QNK95Z599DM124QN:tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md, требования 1-7; ADR-0002 (принцип целостности); строка бэклога П2 от 26.09.2026 «Гейт неослабления тестов в пульте» |
+| 38 | Удаление, переименование и ослабление тестов `tests/**/*.py` без мандата Оператора не проходят: переход `in_dev → verifying` отказывает именованным действием «переход отклонён: гейт неослабления тестов», гейт мержа тем же узлом сравнения переводит задачу в `escalated` до попытки merge. Находка — удалённый файл, пара переименования (`git diff -M`), исчезнувший из head тестовый метод изменённого файла и появившийся в head пропуск (`@skip`/`@skipIf`/`@skipUnless`/`@expectedFailure`/`@pytest.mark.skip`/`skipif`/`xfail`, вызов `self.skipTest(`/`pytest.skip(`; имя-метка — декоратор `@<имя>`, где имя связано присваиванием уровня модуля `<имя> = pytest.mark.skip/skipif/xfail(…)`/`unittest.skip*(…)` или импортом `from <модуль тестов проекта> import <имя>`, со значением метки в маркере: смена значения при прежнем `@<имя>` — находка, в том числе в неизменном файле-импортёре; модульные `pytestmark = <марка пропуска или список>`, `pytest.skip(..., allow_module_level=True)` и `pytest.importorskip(` уровня модуля — пропуск каждого тестового метода файла, SPEC 01M56TNX1WWKV8PVQ94FT4ZJQB), которого не было в base на том же имени; файл с нулём тестовых методов в base находкой не считается. Утверждение тестового метода, сохранившего имя, которого в head нет в той же нормальной форме (оператор `assert`, вызов `assert*`/`fail`, `pytest.raises`/`pytest.warns`; сообщение, локальные имена и корень импортированного модуля не различаются), — находка (SPEC 01M45FJD46BX45VHC36S4VS9QN): смена утверждений вне раздела SPEC «Меняемое поведение» и ослабление (утверждений меньше, другой вид, литерал заменён вычисленным значением, допуск шире, якорь регулярного выражения снят, граница в разрешающую сторону) отказывают переходу и эскалируют мерж; проходит только смена ожидания из перечня записи approve гейта SPEC «объявлена смена поведения тестов» с совпавшими парами «было → стало», строгостью не ниже прежней и двусторонним прогоном на переходе (новая версия теста падает на дереве базы, старая — на дереве головы, оба раза на утверждении; гейт мержа сверяет запись «двусторонний прогон пройден» с текущей головой ветки). Храповик: общее число тестовых методов и утверждений диффа `tests/` в голове не меньше, чем в базе. Запись «изменены утверждения тестов (наблюдение)» на обоих рубежах сохраняется, к ней добавлена «утверждения тестов: исход рубежа». Мандат — строка `Ослабление тестов разрешено: <пути и имена>` в `tasks/<id>/ANSWER-n.md`, ЧЕЙ ПОСЛЕДНИЙ КОММИТ в истории ссылки документов `refs/artifacts/<id>` доказанно не автокоммит артефактов шага роли (тот же рубеж, что у мандата зон в инварианте 34): роль не выписывает разрешение себе сама. Молчание git на переходе — отказ (fail-closed, ADR-0002), на мерже — fail-open, как у соседнего рубежа защищённых путей | `test_invariants.TestWeakeningNeedsTheOperatorTest` (в том числе `test_an_undeclared_assertion_change_needs_the_operator`); `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`; `tests/test_guard_assertion_changes.py`; `tests/test_test_integrity_gate.py` (в том числе `AssertionObservationTest`); `tests/test_guard_test_ast.py` (в том числе `ChangedAssertionsTest`); `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`; `refs/artifacts/01M3FQ2V77QNK95Z599DM124QN:tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests/` (приёмочные тесты задачи по адресу ссылки после мержа не исполняются, ADR-0018 п.2) | refs/artifacts/01M3FQ2V77QNK95Z599DM124QN:tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md, требования 1-7; ADR-0002 (принцип целостности); строка бэклога П2 от 26.09.2026 «Гейт неослабления тестов в пульте» |
 | 39 | Порядок состояний FSM — `in_dev → verifying → review → acceptance → merge_gate`: CI подтянутой головы кодовой ветки проверяется ДО ревьювера, не после. Девять рубежей перехода `in_dev → review` (подтяжка main, прогон приёмочной планки, гейт зон, гейт заявки мутации — новые и изменённые тесты `tests/` без строки «Ловит мутацию:» в докстринге, 01M29A0F88P9GKSXFW90F99H2N, гейт неослабления тестов — удаление, переименование и ослабление тестов `tests/` без мандата Оператора, 01M3FQ2V77QNK95Z599DM124QN, гейт ёмкости, лок планки, гейт «замечания ревью не отработаны», сверка головы на origin) стоят на `in_dev → verifying` целиком, без повтора на `verifying → review`; в `review` из `verifying` ведёт только зелёный CI головы. Возврат `changes_requested` — в `in_dev`, повторный вход в `review` — снова через `verifying` | `refs/artifacts/01M1TQ0TRCZPRZX22C4084NCPB:tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac01_ac09_state_order.py`; `refs/artifacts/01M1TQ0TRCZPRZX22C4084NCPB:tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac02_ac08_gates_moved_to_verifying.py` (приёмочные тесты задачи по адресу ссылки после мержа не исполняются, ADR-0018 п.2); `test_auto_cycle.py::FSM_STATES` | ADR-0015 (docs/adr/0015-ci-before-review.md); refs/artifacts/01M1TQ0TRCZPRZX22C4084NCPB:tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md, требования 1-3 |
 | 40 | Git главной копии пульта не меняется в ходе задачи: от `new` до `done` (автокоммит шага, подтяжка `main`, мерж) ветки `refs/heads/*`, ссылки `refs/artifacts/*`, HEAD и `git worktree list` главной копии остаются прежними — ветка задачи, её рабочая копия, ссылка документов, временная рабочая копия мержа, коммит мержа и push живут в клоне проекта `.artel/projects/<имя>/repo`; git главной копии меняют только `pin-update`/`pin --to` и ремонт хуков самого пульта (`doctor --fix`) | `test_invariants.MainCopyGitUnchangedDuringTaskTest` | ADR-0021 пп. 1, 2, 12; refs/artifacts/01M42PENCS26D0656X8FR7DFA7:tasks/01M42PENCS26D0656X8FR7DFA7/SPEC.md, требования 2, 9 |
 
```
