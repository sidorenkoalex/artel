---
task: 01M4G8N9KBTVNNT7YGZ59Q5WBF
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 5
---

# REVIEW: Гейт неослабления тестов видит утверждения в унаследованных помощниках и в tests/sandbox.py

## Фаза A — план
- Таблица покрытия полна (1–6 → шаги 1–5), шаг 5 описывает правки по
  ревью итерации 1. Риск о пакете `tests/<x>/__init__.py` исправлен
  (R1-F3).
- «Влияние на систему» отстаёт от кода: «`git grep` (только при
  ослабленном помощнике)» — теперь поиск идёт и по изменённым классам с
  утверждающей цепочкой (`guard.changed_classes`), например при любой
  смене импортов `tests/sandbox.py` — R2-F2.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1. |
| 2 | реализовано не полностью | Сценарии R1-F1 (пустое переопределение, смена базы, наследник наследника вне диффа) закрыты; но поиск наследников обрывается на промежуточном модуле, который сам лежит в диффе — R2-F1. |
| 3 | OK | AC-3 зелёный. |
| 4 | OK | Без изменений. |
| 5 | OK | 15 → 2 (проверено в итерации 1). |
| 6 | OK | Абзац п.4 дополнен наследниками; утверждение «то же — у наследника класса…» станет верным целиком после R2-F1. |

## Замечания

- major — `orchestrator/advance_gates/test_integrity.py`, `_compare`, цикл поиска (`if path in in_diff or path in visited or not in_scope(path): continue` перед `guard.subclass_names(text, classes)`) — наследники собираются только из файлов ВНЕ диффа: файл диффа, найденный `git grep` по имени изменённого класса, пропускается до `subclass_names`, и его классы-наследники не попадают в `pending`. Сценарий (воспроизведён зондом в `ConnRealGitSandbox` на коде ветки, файл зонда удалён): база — `tests/top.py` (`Root.check` с `assertEqual`, `class Top(Root)`), `tests/mid.py` (`class Mid(Top): pass`), `tests/test_caller.py` (`class CallerTest(Mid)`, `test_m` зовёт `self.check(1)`). В ветке `Top` меняет базу на `unittest.TestCase`, а `tests/mid.py` получает любую безобидную правку (комментарий). `merge_gate_escalates` → `False`, журнал пуст; без правки `tests/mid.py` тот же сценарий → `True`, находка у `CallerTest::test_m`. Тот же класс дефекта, что R1-F1 (эскалация зависит от того, тронут ли посторонний файл), и абзац п.4 `docs/operator-gates.md` («то же — у наследника класса, который перестал отдавать помощника») для него неверен. (Для ослабленного помощника обрыва нет — поиск идёт по имени помощника, зонд с `tests/mid.py` в диффе даёт находку.) — Предложение: до цикла (или в нём, до `continue` по `in_diff`) пополнять `classes`/`pending` наследниками из головного текста файлов диффа (`guard.subclass_names(head_source, classes)` до неподвижной точки), закрепить тестом «промежуточный модуль в диффе с несущественной правкой, вызывающий вне диффа — находка».
- minor — PLAN.md «Влияние на систему», пункт «Новые вызовы git» — заявлено «`git grep` (только при ослабленном помощнике)», фактически поиск идёт и по `changed_classes`; смена одного импорта `tests/sandbox.py` даёт изменёнными `RealGitSandbox`, `ConnRealGitSandbox`, `OriginRealGitSandbox`, `AutoOriginSandbox`, `SyncedOriginConnSandbox`, `GitignoreCommittedRealGitSandbox` (проверено вызовом `guard.changed_classes`), а `git grep -lw` по семейству песочниц даёт ~200 файлов `tests/`, каждый — отдельный `git show` и разбор на обеих сторонах. Ложных находок это не даёт, но стоимость гейта на таком диффе план не называет. — Предложение: поправить пункт «Влияние на систему»/«Риски» (условие запуска поиска и порядок числа чтений на правке `tests/sandbox.py`).

Тесты `tests/test_test_integrity_helper_heirs.py`: заявки «Ловит мутацию» у всех 8 методов, наблюдаемы; одна проверена временной мутацией (см. ниже). Существующие тесты `tests/` не изменены (дифф `tests/` — только новый файл). Долгоживущий файл задачи не дублируется.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/advance_gates/test_integrity.py (`_compare`); scripts/guard.py::weakened_helpers | Вызывающие вне диффа искались только по ослабленным помощникам | — | Принято: `changed_classes` + `subclass_names`, три сценария закреплены тестами `HeirOutsideDiffTest`; остаточный обрыв на промежуточном файле диффа заведён отдельно как R2-F1. |
| R1-F2 | accepted | orchestrator/advance_gates/test_integrity.py::_side_modules | Сбой `gitcmd.show` = «модуля нет» | — | Принято: переспрос `ls_tree_files`, сбой → `_git_failure`; тесты `SideModuleReadFailureTest` на оба исхода. |
| R1-F3 | accepted | PLAN.md «Риски» | Ложное утверждение о пакете `tests/<x>/__init__.py` | — | Принято: формулировка исправлена. |
| R2-F1 | open | orchestrator/advance_gates/test_integrity.py::_compare (цикл поиска, `continue` по `in_diff` до `subclass_names`) | Наследники изменённого класса не ищутся через промежуточный модуль, лежащий в диффе | Вызывающий вне диффа теряет утверждения молча, если ветка вдобавок тронула промежуточный модуль (комментарий) — мерж не эскалирует; без той правки эскалирует | Собирать наследников и из головных текстов файлов диффа до неподвижной точки; тест на сценарий |
| R2-F2 | open | PLAN.md «Влияние на систему» / «Риски» | Условие запуска `git grep` описано как «только при ослабленном помощнике» | План занижает стоимость гейта на правке `tests/sandbox.py` (~200 кандидатов) | Обновить формулировку |

## Вердикт
changes_requested — исправить R2-F1 (major) и формулировку плана R2-F2 (minor). R1-F1..R1-F3 приняты.

## Проверено исполнением
- `python3 -m pytest -q tests/test_test_integrity_helper_heirs.py tests/test_guard_helper_scope.py tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py tests/test_test_integrity_gate.py tests/test_guard_assertion_changes.py tests/test_guard_test_ast.py tests/test_class_mandate_units.py tests/test_answer_mandate.py tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py` — 130 passed, 30 subtests passed.
- `artel.py plank-run 01M4G8N9KBTVNNT7YGZ59Q5WBF` — отказ «планки нет» (в `refs/artifacts/…` нет `test_*.py`); долгоживущий файл задачи прогнан выше — зелёный.
- Зонд R2-F1 (временный `_review_probe_test.py` на `HeirSandbox` из теста ветки, `python3 -m unittest`, файл удалён): смена базы `Top` + комментарий в `tests/mid.py` → `merge_gate` `False`, журнал `[]`; без комментария → `True`, находка `CallerTest::test_m (помощник Root.check из tests/top.py)`; ослабленный `Top.check` + комментарий в `tests/mid.py` → `True` (обрыв только у ветки поиска по классам).
- `guard.changed_classes(sandbox, 'import os as _zz\n' + sandbox, 'tests/sandbox.py', TestModules)` — 6 классов семейства `RealGitSandbox`; `git grep -lw` по семейству песочниц в `tests/` — 203 файла (R2-F2).
- Временная мутация (возвращено `git checkout`): в `_compare` убрано `pending |= heirs - searched` → красный `HeirOutsideDiffTest::test_heir_of_heir_outside_diff_is_reached`, остальные 7 зелёные.
- `git show --stat 3adf4d86` — автокоммит пульта трогает только строку `docs/codebase-map.md` (`built_at_sha`).

## Предложения системе
- Сторож роли отказывает `pytest <файл вне tests/>` как «полный прогон набора» — временный зонд ревьювера пришлось гонять через `python3 -m unittest`; стоит различать в стороже явный путь файла и прогон без аргументов.
