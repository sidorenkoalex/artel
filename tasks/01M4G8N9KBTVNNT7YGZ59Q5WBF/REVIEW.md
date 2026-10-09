---
task: 01M4G8N9KBTVNNT7YGZ59Q5WBF
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Гейт неослабления тестов видит утверждения в унаследованных помощниках и в tests/sandbox.py

## Фаза A — план
- Таблица покрытия полна: требования 1–6 → шаги 1–4; числа требования 5
  названы в «Подходе» (15 → 2) и подтверждены моим прогоном (см.
  «Проверено исполнением»).
- Шаги размера MR, подход (одно свойство в `_assertion_records` и три
  потребителя через общий `_compare`) конвенциям не противоречит.
- Неточность «Рисков»: пакет `tests/<x>/__init__.py` по общему правилу НЕ
  разрешается — `_HelperScope._module` (`scripts/guard.py`, ~строка 1000)
  строит путь только как `<x>.py` (R1-F3).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_HelperScope.class_chain`/`method`/`function`: базовые классы своего файла, других модулей `tests/` и `tests/sandbox.py`, функции песочницы (голое имя, `sandbox.fn`, псевдоним), один уровень. |
| 2 | реализовано не полностью | Ослабление внутри помощника находит вызывающих вне диффа; но вызывающие вне диффа ищутся только по `weakened_helpers`, и потеря утверждений вызывающего из‑за изменения цепочки классов в файле диффа (переопределение помощника без утверждений, смена базового класса) не видна — R1-F1. |
| 3 | OK | `_counts` с модулями стороны; AC-3 зелёный. |
| 4 | OK | `Finding.helpers` + `_helper_paths`; смешанная находка fail-closed; убыль храповика покрывается (`_decline_source(..., helpers)`). |
| 5 | OK | 15 → 2 на `af5e1111`, воспроизведено. |
| 6 | OK | Абзац в `docs/operator-gates.md` п.4. |

## Замечания

- major — `orchestrator/advance_gates/test_integrity.py` (блок «Вызывающие вне диффа» в `_compare`, `guard.weakened_helpers(...)`) и `scripts/guard.py::weakened_helpers` — кандидаты в вызывающие вне диффа выбираются только по именам помощников, ПОТЕРЯВШИХ своё утверждение, тогда как сравнение, которое они питают, смотрит на список утверждений вызывающего целиком. Сценарий (проверен скриптом на `guard` ветки): `tests/top.py::Top.check` с `assertEqual`, `tests/mid.py: class Mid(Top): pass`, `tests/test_c.py: class C(Mid)`, `test_m` зовёт `self.check(1)`. В ветке меняется только `tests/mid.py` — либо `Mid` получает переопределение `def check(self, v): pass`, либо базовый класс `Mid` меняется на `unittest.TestCase`. `weakened_helpers(mid_base, mid_head)` = `set()` в обоих случаях → `git grep` не запускается → у `C::test_m` (утверждения base `[assertEqual]`, head `[]`) находки нет, мерж не эскалирует. Тот же `C::test_m`, окажись `tests/test_c.py` в диффе, находку получает — гейт ведёт себя по-разному для одного и того же ослабления, и абзац `docs/operator-gates.md` («находка у каждого метода, который его зовёт, в том числе в файле, не менявшемся в ветке») для этого класса неверен. То же через `tests/sandbox.py`: класс песочницы, которому добавили пустое переопределение метода базового класса. — Предложение: кандидатов искать не только по ослабленным помощникам, но и по классам файлов диффа, у которых изменились базовые классы или набор методов (`git grep -w <ИмяКласса>` даёт наследников), и сравнивать их тем же `_assertion_observation(path, path, …, modules)`; закрепить тестом на оба варианта (переопределение и смена базы) с вызывающим вне диффа.
- minor — `orchestrator/advance_gates/test_integrity.py::_side_modules`, `load` (`gitcmd.show(ref, path, repo=repo)[0]` для файла диффа вне области узла) и `read_unchanged` — сбой чтения модуля молча даёт `None`: если сбой у стороны base, помощники модуля невидимы только в базе, и ослабление в нём не даёт находки (fail-open), в отличие от остальных чтений узла, где молчание git — `_git_failure`. Сценарий редкий (сбой git на одной стороне). — Предложение: различать «модуля нет» и «git не ответил» (причина второго элемента `gitcmd.show`) и на сбой возвращать `_git_failure`.
- minor — PLAN.md «Риски» / `scripts/guard.py::_HelperScope._module` — PLAN утверждает, что модуль-пакет `tests/<x>/__init__.py` разрешается по общему правилу, но путь строится только как `tests/<x>.py`; помощники из `tests/<x>/__init__.py` не видны. Вне требований SPEC, но документ плана неверен. — Предложение: поправить формулировку риска либо пробовать `<путь>/__init__.py` вторым.

Тесты `tests/test_guard_helper_scope.py`: заявки «Ловит мутацию» правдоподобны и наблюдаемы; две проверены временной мутацией (см. ниже), долгоживущий файл задачи не дублируется. Существующие тесты `tests/` не изменены (дифф `tests/` — только новый файл). Карта кодовой базы свежа.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/advance_gates/test_integrity.py (`_compare`, вызывающие вне диффа); scripts/guard.py::weakened_helpers | Вызывающие вне диффа ищутся только по помощникам, потерявшим своё утверждение; переопределение помощника без утверждений или смена базового класса в файле диффа не порождает кандидатов | Метод вызывающего в неизменённом файле теряет все утверждения — гейт мержа молчит; тот же метод в файле диффа получил бы находку | Искать кандидатов и по классам файлов диффа с изменёнными базами/набором методов; тест на оба варианта с вызывающим вне диффа |
| R1-F2 | open | orchestrator/advance_gates/test_integrity.py::_side_modules | Сбой `gitcmd.show` при чтении модуля стороны молча = «модуля нет» | При сбое на стороне base ослабление в помощнике этого модуля не видно (fail-open) | Отличать отсутствие файла от сбоя git, сбой → `_git_failure` |
| R1-F3 | open | PLAN.md «Риски»; scripts/guard.py::_HelperScope._module | План заявляет разрешение `tests/<x>/__init__.py`, код его не делает | Ложное утверждение в плане о покрытии | Исправить формулировку или добавить разрешение `__init__.py` |

## Вердикт
changes_requested — исправить R1-F1 (major); R1-F2 и R1-F3 — minor, по желанию в той же итерации, но реестр должен быть закрыт до `approved`.

## Проверено исполнением
- `python3 -m pytest -q tests/test_guard_helper_scope.py tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py tests/test_test_integrity_gate.py tests/test_guard_assertion_changes.py tests/test_guard_test_ast.py tests/test_class_mandate_units.py tests/test_answer_mandate.py tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py` — 122 passed, 30 subtests passed.
- `artel.py plank-run 01M4G8N9KBTVNNT7YGZ59Q5WBF` — отказ «планки нет» (в `refs/artifacts/…` нет `test_*.py`); долгоживущий файл задачи прогнан в наборе выше — 6/6 зелёные.
- Скрипт-зонд (во временном файле, удалён): `guard.weakened_helpers` и `guard.test_assertions` с `TestModules` на сценарии R1-F1 — `weakened_helpers` = `set()` для переопределения и для смены базы, утверждения `C::test_m` base `[self.assertEqual(v, 1)]`, head `[]`.
- Скрипт-зонд требования 5: старый `guard` (`git show af5e1111:scripts/guard.py`) vs новый с `TestModules` рабочего дерева — 4665 методов, без утверждений 15 → 2 (те же два метода, что в PLAN).
- Временные мутации (код возвращён `git checkout`): `_decline_source` без `helpers.get(...)` → красный `test_ratchet_decline_in_caller_covered_by_helper_path`; привязка импорта по `alias.name` вместо `asname` → красный `test_aliased_import_is_helper`.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — отличие только в `built_at_sha`, карта свежа (изменение откачено).

## Предложения системе
- Гейт неослабления выбирает «затронутых» вне диффа эвристикой по именам; класс «эвристика выбора кандидатов уже, чем сравнение, которое она питает» стоит держать в review-checklist как отдельный пункт для инкрементальных гейтов (`orchestrator/advance_gates/`).
