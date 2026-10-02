---
task: 01M3Y753QNG6TS5C7MTJS1MEV6
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Гейт неослабления замечает изменённые утверждения тестов (наблюдение); ревьювер сверяет утверждения

## Фаза A: план
- Таблица покрытия полна (требования 1–10 → шаги 1–4); шаги — проверяемые единицы (разбор в guard / узел гейта + пакет / документ / приложения).
- Подход не конфликтует с архитектурой: правило «что такое тестовый метод» — тот же `_collect_qualified_test_functions`; узел отказа (`findings()`/возврат `uncovered`) не меняется; `mandate.py` и файлы «только чтение» не тронуты (diff --stat: 6 файлов, все в `zones:`).
- Отклонение зон (`orchestrator/review.py` вместо `brief.py`) названо в SPEC «Материалы» и в PLAN, правка `brief.py` не делалась.
- «Влияние на систему» соответствует diff: новые записи журнала обычного уровня, раздел пакета, `_answer_mandate` читается и при одних находках наблюдения (только чтение). Путь отката — revert merge-коммита.
- Приложения 1–3 (`skills/review-checklist.md`, `docs/invariants.md`, `skills/coding-standards.md`) — `git apply --check` прогнан мной на дереве ветки, все три код 0.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `scripts/guard.py::_is_assertion`, `test_assertions`: `assert`, атрибут `assert*`/`fail`, `pytest.raises/warns`; `ast.walk` по всему телу; помощники первого уровня `_helper_calls` (self.<имя> того же класса, голое имя без `test_`), из той же стороны. |
| 2 | OK | `_AssertionNormalizer`: `msg=`, `assert …, msg`, таблица `ASSERTION_REQUIRED_ARGS` (методы с не-сообщением третьим исключены — корректно по 2б); `_local_names` — метка; корень цепочки из модульного импорта — метка, голое имя не трогается. |
| 3 | OK | `changed_test_assertions` — Counter по нормальной форме, только имена по обе стороны. |
| 4 | OK | `_assertion_observation`: один `Finding(path, Класс::метод, …)` на метод, ≤3 текста + «и ещё N», текст ≤120 (`_assertion_text`); удалённый/новый файл и исчезнувший метод не сравниваются; неразбираемая сторона → причина, не исключение. |
| 5 | OK | Наблюдение пишется в `uncovered` (оба рубежа), в возврат не идёт; отметка мандата через `Finding.mandate_elements`; молчание git → «наблюдение не выполнено»; раздел пакета в `review._changed_assertions_part`; канарейка/внешний target без изменений. |
| 6 | OK | `docs/operator-gates.md`: п.4 merge (абзац «что находка/нет»), п.6 эскалации (перечень + правило перед мандатом с «Ловит мутацию» base/head и основанием-требованием SPEC). |
| 7 | OK | Приложение 1, применяется. |
| 8 | OK | Приложение 2, применяется; в колонке тестов — новые классы. |
| 9 | OK | Приложение 3, применяется. |
| 10 | OK | 10а–в — `ChangedAssertionsTest`, 10г–ж — `AssertionObservationTest`; заявки «Ловит мутацию» с формулировками SPEC; diff `tests/` — только добавления, ни одного изменённого/удалённого assert. |

## Замечания
Блокирующих и major нет. Наблюдения без требования правки (в реестр не заносятся):
- `orchestrator/advance_gates/test_integrity.py` (`uncovered`) — запись наблюдения пишется при каждом прогоне гейта перехода; если переход отказывает позже (ревью-доработки, origin, планка) и повторяется, запись повторится. Тот же приём уже действует для «новый тест с условным пропуском», так что это согласованно с прецедентом, не дефект.
- 10г проверяет переход через `fsm_advance._test_integrity_gate_refuses` (не весь `advance`) — как и остальные тесты файла; свойство «гейт не отказывает и журналирует» держится.
- `_module_imports` видит только импорты верхнего уровня модуля (не под `try`/`if TYPE_CHECKING`) — смена корня через такой импорт даст ложную находку наблюдения; цена — строка журнала (риски PLAN это называют).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний уровня, требующего правки, в итерации 1 не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py tests/test_test_integrity_gate.py tests/test_guard_test_ast.py tests/test_review_package.py tests/test_fsm_advance_gate_smoke.py tests/test_mutation_claim_gate.py` — 242 passed, 3 subtests passed.
- `python3 -m pytest -q -p no:cacheprovider tasks/01M3Y753QNG6TS5C7MTJS1MEV6/acceptance_tests` — 9 passed.
- Временная мутация «помощники не разворачиваются» (цикл по `_helper_calls` заменён пустым) в `scripts/guard.py` → `tests/test_guard_test_ast.py -k ChangedAssertions`: 1 failed (`test_first_level_helpers_are_unfolded`), 3 passed; файл восстановлен, `git status scripts/` чист.
- `git apply --check` трёх приложений PLAN на дереве ветки — код 0 у всех трёх.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md | grep -v built_at_sha` — расхождений по содержимому нет (карта свежая); регенерация откачена.
- Diff `tests/` (8a629876...HEAD) просмотрен: только добавленные строки, существующие утверждения не изменены.

## Предложения системе
- Запись наблюдения/«условный пропуск» в `test_integrity.uncovered` повторяется на каждом прогоне перехода; когда наблюдение станет блокировкой, стоит договориться о дедупликации по голове ветки, иначе журнал задачи с несколькими кругами доработки будет нести дубли.
