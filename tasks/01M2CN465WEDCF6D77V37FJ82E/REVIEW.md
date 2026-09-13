---
task: 01M2CN465WEDCF6D77V37FJ82E
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Фикс утечки тестов в настоящий пульт: WORKTREES в песочнице test_git_fixation

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`_GitFixationTmpRootTest.PATCHED_ATTRS` несёт `WORKTREES`/`BACKUP_MARKER`) | OK | tests/test_git_fixation.py:159-161 — кортеж расширен ровно на эти два атрибута, остальные семь сохранены дословно. |
| 2 (прочие классы с собственным `PATCHED_ATTRS` сверены) | OK | Пересчитал grep `PATCHED_ATTRS` по `tests/*.py` независимо от таблицы PLAN — те же 8 классов вне `_GitFixationTmpRootTest`. Прочёл тела всех восьми: 6 классов (`test_acceptance_tests_flow.py:203`, `test_agent_failure.py:44`, `test_agent_log.py:81`, `test_analyst_role.py:133`, `test_multitarget_invariants.py:75`, `test_step_cost.py:70`) уже несут `WORKTREES` в своём кортеже — подтверждено чтением, не только таблицей. `test_catalog_new_race.py:34` тоже несёт `WORKTREES`. Оставшиеся два — заявленные исключения: `test_doctor.py:2413` (`_RoleHomeReferenceTmpRootTest`) патчит только `ROLE_HOME`/`ROLE_CONFIG_DIR`, `ROOT` намеренно настоящий и класс только читает (`doctor.check_role_home_reference()`) — записи по `WORKTREES` в теле нет; `test_multitarget.py:104` (`_MultitargetTmpRootTest`) патчит `runner.workspace.ensure` целиком через `mock.patch.object` (строки 134-138) — сам путь к записи подменён, а не обойдён, что явно допустимо AC-2. Таблица PLAN («Покрытие требований») соответствует фактическому коду. |
| 3 (полный прогон `tests/` не создаёт каталоги в `.artel/worktrees`, `git status --porcelain` пуст) | OK (частично — по модулям, не полным набором) | Прогнал `tests/test_git_fixation.py` (41/41), `tests/test_sandbox.py`+`tests/test_multitarget.py`+`tests/test_catalog_new_race.py` (65/65) — `git status --porcelain` до/после пуст, каталогов в `.artel/worktrees` не появилось. Полный набор `tests/` в шаге ревью не гоняется (решение Оператора 05.09) — AC-3 в целом остаётся за CI job `python` (см. «Статус CI» пакета — зелёный на 90443168). |
| 4 (новый инвариант — только приложением диффа к PLAN.md, `tests/test_invariants.py` не редактируется в ветке) | OK | Diff в код ветки не входит (git diff --stat подтверждает: только `docs/codebase-map.md` и `tests/test_git_fixation.py`). Оба приложенных унифицированных диффа (`tests/test_invariants.py`, `docs/invariants.md`) прогнал `git apply --check` на текущем дереве (эти два файла в ветке идентичны `main`@01b6a33c, что и заявляет PLAN) — оба применяются чисто. Новый тестовый класс несёт три метода, каждый с докстрингом «Ловит мутацию: …», описывающим сценарий и наблюдаемое свойство, не пересказ имени. |
| 5 (ассерты существующих тестов не меняются) | OK | Diff `tests/test_git_fixation.py` — только добавление двух строковых литералов в существующий кортеж, ни одна строка `assert`/тела теста не тронута. |

## Замечания

Замечаний нет.

## Реестр замечаний

Замечаний нет — реестр пуст.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_git_fixation -v` — 41 тест, все зелёные (26.5с); после прогона `git status --porcelain` пуст, новых каталогов в `.artel/worktrees` не появилось.
- `python3 -m unittest tests.test_sandbox tests.test_multitarget tests.test_catalog_new_race` — 65 тестов, все зелёные (30.8с).
- `git apply --check` на приложенных к PLAN.md диффах `tests/test_invariants.py` и `docs/invariants.md` (сохранены во временные файлы, прогнаны против текущего дерева задачи, где оба файла идентичны `main`@01b6a33c) — оба применяются чисто, оба временных файла удалены (`git clean -f`) до сдачи REVIEW.md, в диффе кода не участвуют.
- `python3 scripts/codebase_map.py` — контрольный прогон вручную (не для коммита): диф свёлся только к строке `built_at_sha` (текущий HEAD `90443168` вместо `812c9064` из коммита ветки) — по правилу скила («built_at_sha… не признак дефекта») это не расхождение по содержимому; тестовый прогон отменён (`git checkout -- docs/codebase-map.md`), в рабочем дереве изменений не осталось.
- `grep -rn "PATCHED_ATTRS" tests/*.py` + точечное чтение всех 8 внешних классов (offsets выше) — таблица ревизии PLAN подтверждена самостоятельным чтением кода, не принята на слово.
- Статус CI пакета (14 проверок, зелёный на 90443168) принят как подтверждение AC-3 на полном наборе — сам полный прогон в шаге не повторялся (решение Оператора 05.09).

## Предложения системе

- Идея хелпера `TmpRootTest.with_real_git()`/`.without_worktrees()` (PLAN.md, «Предложения системе») — согласен, класс «песочница вручную перечисляет узкое подмножение `PATCHED_ATTRS» уже дважды приводил к регрессии (d692f2a6 и, судя по докстрингу нового инварианта, повтору CR-2026-09-12-1) — стоит завести отдельной задачей R8, не блокирует эту.
