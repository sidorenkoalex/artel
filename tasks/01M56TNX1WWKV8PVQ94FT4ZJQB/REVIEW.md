---
task: 01M56TNX1WWKV8PVQ94FT4ZJQB
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Гейт неослабления: async-тесты и пропуски через метку и модуль

## Фаза A: план
- Таблица покрытия полна: требования 1–8 → шаги 1–5; требование 7 — долгоживущие файлы задачи и шаг 3.
- Шаги размера MR: guard / узел сравнения / тесты / приложение / карта.
- Подход в рамках архитектуры: распознавание пропуска в `scripts/guard.py`, сравнение в `test_integrity.py`, контракт `guard.test_skip_markers` и `_excused_skips(node)` не меняется. Метки — второй слой поверх прежнего, импортёры ищутся тем же `_helper_callers`, что и у части 1.
- «Влияние на систему» сходится с diff: тронуты только `scripts/guard.py`, `orchestrator/advance_gates/test_integrity.py`, `tests/test_guard_test_ast.py` (+ карта). Защищённые пути не тронуты, `docs/invariants.md` меняется только приложением к PLAN. Откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `guard._module_labels` (форма а, последнее связывание побеждает) и `_imported_labels` (форма б, `from … import name` без `as`, level 0; модуль виден через `TestModules.module_path` — у артели `tests/**`, у внешнего проекта `weakening_scope` + `workdir`). Находка того же вида «<файл>: <маркер> на <имя>» |
| 2 | OK | `_resolved_reason` для метки идёт через `_decorator_occurrence`: условный вид, нужен аргумент условия, причина — константа. Послабление — только при `new_name`, у класса ключ не входит в `head_methods` → находка всегда. `skip(reason=)` и `skipif(reason=)` без условия причины не получают |
| 3 | OK | В маркер входит `ast.unparse(value)` → смена значения даёт новый маркер на прежнем имени. Импортёры вне диффа: `skip_label_values` по обе стороны файлов диффа → `_helper_callers` → `_file_findings(path, path, None, text, text, modules)`; стороны base/head разрешаются своими модулями. `pytestmark` тоже сравнивается по значению |
| 4 | OK | `_pytestmark_elements` (одна марка / список / кортеж), `_module_level_calls` (любая глубина вне тел функций/классов/lambda; условно только внутри `if`/`else`). У `importorskip` причина — только `reason=` (`_constant_reason(node, len(node.args))`) |
| 5 | OK | Путь в `_compare` общий. У артели `_helper_callers` с `everywhere=False` ищет в `tests/`, у внешнего проекта — по всему дереву с отсевом по `in_scope` |
| 6 | OK | `TEST_METHOD = ^\s*(?:async\s+)?def\s+…` |
| 7 | OK | Долгоживущий `test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py` гоняет песочницу с учебным `workdir: backend`, `weakening_scope: [backend/tests/**/*.py]`, без сети |
| 8 | OK | Приложение к PLAN применяется (`git apply --check` — код 0). В строке `| 38 |` есть `имя-метка`, `pytestmark`, `allow_module_level=True`, `pytest.importorskip(`, прежний перечень сохранён (планка AC-10 зелёная) |

## Замечания

Blocker и major нет. Наблюдения уровня ниже minor, замечаниями не заводятся:
- `scripts/guard.py` `resolved_skip_markers`: `{**_imported_labels(...), **_module_labels(...)}` — связывание в своём модуле перекрывает импорт независимо от порядка операторов. Расхождение возможно только при переопределении того же имени в одном файле; формы SPEC это не затрагивает.
- `TestModules.labels` парсит `entry.source` второй раз — дублирует работу, на корректность не влияет.
- Новому методу в файле, где уже есть безусловный `pytestmark = pytest.mark.skip(...)`, ставится находка «появившийся маркер». Это согласуется с требованием 4 и правилом прямого декоратора: безусловный пропуск нового метода — находка.

Тесты: у трёх новых методов `ResolvedSkipMarkersTest` заявки «Ловит мутацию» называют наблюдаемое расхождение (непустой словарь вместо `{}`), все три подтверждены временной мутацией (ниже). Долгоживущие файлы они не повторяют: переприсваивание метки, обычная марка `pytest.mark.slow` и вызовы в телах функций/классов в долгоживущих сценариях не встречаются. Изменённых или удалённых утверждений в `tests/` в diff нет — добавлен только новый класс.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет — замечаний на итерации 1 не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 orchestrator/artel.py plank-run 01M56TNX1WWKV8PVQ94FT4ZJQB` — 2 passed, код выхода 0.
- `python3 -m pytest -p no:xdist tests/test_01m56tnx1wwkv8pvq94ft4zjqb_async_test_method.py tests/test_01m56tnx1wwkv8pvq94ft4zjqb_skip_labels.py tests/test_guard_test_ast.py tests/test_test_integrity_gate.py tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py` — 83 passed, 145 subtests passed. С `-n 6` xdist падал на старте воркеров («node down»); это особенность окружения, прогон повторён последовательно.
- Временные мутации `scripts/guard.py` (после каждой файл восстановлен, `git status` чистый):
  - убран `labels.pop` при переприсваивании → `test_label_rebound_to_non_mark_is_not_a_skip` красный (1 failed);
  - любая `pytest.mark.*` считается пропуском → 2 failed (`test_ordinary_mark_label_is_not_a_skip` и тест переприсваивания);
  - `_module_level_calls` заходит в тела функций/классов → `test_skip_inside_function_or_class_body_is_not_module_level` красный;
  - якорь `TEST_METHOD` возвращён к `^\s*def` → `test_01m56tnx1wwkv8pvq94ft4zjqb_async_test_method.py` красный (8 failed subtests).
- `git apply --check` приложения из PLAN.md на дереве ветки — код 0.
- `python3 scripts/codebase_map.py` — содержимое карты без строки `built_at_sha` совпадает с закоммиченным (карта свежая); перегенерированный файл возвращён `git checkout`.
- `git grep` по `tests/` артели — модульных `pytestmark`/`importorskip` и присваиваний-меток нет, ложных находок на существующих тестах после мержа не будет.

## Предложения системе
- Шаг ревью: однострочные `python3 - <<EOF` и shell-функции в Bash отклоняются фильтром команд («function_definition», «brace with quote character»). Временную мутацию пришлось гонять скриптом, записанным в каталог документов. Стоит дать ревьюверу штатную команду пульта для временной мутации (по аналогии с `plank-run`).
