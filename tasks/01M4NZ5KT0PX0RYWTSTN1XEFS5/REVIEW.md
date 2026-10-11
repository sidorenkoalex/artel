---
task: 01M4NZ5KT0PX0RYWTSTN1XEFS5
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Правила аналитика — матрица последствий в вопросах и проверяемое «Меняемое поведение» (ADR-0022 п.4)

## Фаза A: план

- Таблица покрытия полна: требования 1–10 привязаны к шагам. 1, 4, 8, 9 — приложения к защищённым путям (шаг 5); 2–3 — шаг 1; 5–7 — шаг 2; 10 — шаг 3.
- Шаги размером с MR, не микрооперации. Подход повторно использует разбор guard, второй реализации нет. Конвенциям не противоречит: защищённые пути — приложениями, а `fsm_advance.py` и гейт неослабления не тронуты.
- «Влияние на систему» сходится с фактическим diff. Изменены `orchestrator/fsm.py` и `scripts/guard.py`, в `tests/` правились только данные фикстур, карта перегенерирована. Путь отката — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Приложения к `templates/QUESTIONS.md` и `skills/spec-authoring.md` задают четыре метки. Пример в шаблоне написан в форме матрицы. |
| 2 | OK | Правила формы — `_QUESTION_LINE`, `_VARIANT_LINE`, `_DEFAULT_LINE` и `_MATRIX_LABEL_LINE` в `scripts/guard.py`. `_questions_batch` засчитывает метку только открытому варианту. Строка дефолта, следующий вариант, чужая буква и следующий вопрос обрывают вариант. |
| 3 | OK | `questions_matrix_errors` подключён в `_content_errors` без проверки `status` и даёт все четыре отказа: нет вопроса; вопрос без вариантов (с номером); чужая буква (с номером); нет метки (с номером и буквой). `fsm_advance.py` не менялся. Неэскалацию задачи подтверждает `DraftQuestionsAdvanceTest`. |
| 4 | OK | Правило вписано в приложение к `skills/spec-authoring.md`. |
| 5 | OK | В `behavior_change_refusals` порядок а→б→в→г. а) использует `_is_assertion`/`_assertion_kind` и `SIGN_OTHER_KIND` (= «другой вид утверждения»), б) — `literal_pair_keys`, в) — `_CONTAINER_TYPES`, г) — `_value_key` по `_literal_positions` узлов `_assertion_records`. Это то же сравнение, что у `literal_pair_keys`, потому что тот тоже строит ключи через `_value_key`. Каждая причина подсказывает, что делать (`_BEHAVIOR_FIX_HINT` либо «вынеси её вопросом Оператору»). Отказ мягкий, через существующий `return "", reason`. |
| 6 | OK | Сверка в `fsm._behavior_change_declaration` стоит после ранних выходов и после проверки существования метода. |
| 7 | OK | `fsm.py` только вызывает `guard.TestModules`, `guard.method_literal_keys` и `guard.behavior_change_refusals`. `advance_gates/` не тронут. |
| 8 | OK | Приложение к `skills/spec-audit.md`, раздел д. |
| 9 | OK | Приложение к `templates/SPEC.md` меняет только текст комментария. Пример строки раздела по-прежнему с отступом, по PLAN (шаг 5) тесты шаблона зелёные. |
| 10 | OK | По `git diff 28cfe08c -- tests` ни одна строка `assert` существующих методов не изменена и не удалена. 10а: `base_two(first_was, second_was)` кладёт те же случайные `a1`/`a2`/`a3` литералами `assertNotEqual`, а по умолчанию тела прежние. 10б: изменён помощник `undeclared_scenario`, `test_kept` одинаков в базе и в голове; `assertGreaterEqual(app.VALUE, 1)` зелёный, потому что `two_values` даёт ≥10; пара `1`→`2` не совпадает с фактической парой; ветка «раздела нет» сохранена. 10в/10г: `QUESTIONS_READY`, `QUESTIONS_VALID`, `QUESTIONS_MD` ×2 и `QUESTIONS_TEXT` ×2 переписаны построчно с матрицей; `QUESTIONS_NO_SECTION` не тронут. |

## Замечания

Blocker и major нет.

Наблюдения ниже ниже порога замечаний — без сценария поломки в рамках SPEC:
- `scripts/guard.py` (`_VARIANT_LINE`): строчная латинская буква `- a)` не считается ни вариантом, ни ошибкой, и её метки уходят предыдущему варианту. SPEC такую форму не называет, PLAN указал это в «Рисках». Если понадобится строже — это отдельная задача.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: blocker и major не найдены.

## Вердикт

approved

## Проверено исполнением

- `python3 orchestrator/artel.py plank-run 01M4NZ5KT0PX0RYWTSTN1XEFS5` (пульт): 2 passed, код выхода 0.
- `pytest` по `tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py`, `tests/test_01m4nz5kt0px0rywtstn1xefs5_questions_matrix.py`, `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py`, `tests/test_fsm_branch_correct_status_reads.py`, `tests/test_analyst_role.py`, `tests/test_answer.py`: 108 passed, 6 subtests passed.
- Приложения PLAN: все четыре диффа извлечены из PLAN.md, `git apply --check` каждого на HEAD прошёл с кодом 0; `templates/` и `skills/` на ветке совпадают с main. Пропатченный `templates/QUESTIONS.md` с подставленным id: `guard.py` даёт 0 при `draft` и при `ready`. Без строки `цена:` у варианта A — код 1 с текстом «вопрос 1, вариант A: … нет пунктов `цена:`».
- Временная мутация, после каждой код возвращён `git checkout -- scripts/guard.py`, рабочее дерево чистое:
  - строка дефолта перестала обрывать вариант → покраснел `test_ac1_label_after_default_line_is_not_counted_for_variant`;
  - сверка вида отключена (`if False:`) → покраснел `test_ac6_kind_change_refused_and_literal_pair_passes`.
- `python3 scripts/codebase_map.py`: diff карты только в строке `built_at_sha`, по содержимому карта свежая; изменение откачено.
- `git diff 28cfe08c -- tests | grep '^[-+].*assert'`: в существующих файлах изменены только строки данных фикстур (тела методов-фикстур в `base_two`/`undeclared_scenario`), утверждения тестовых методов не изменены.
- CI коммита aace7644 зелёный (16 проверок, по пакету).

## Предложения системе

- Ревью-пакет: изменённые утверждения в планке и в фикстурах-строках (`fixture_source([...])`) выглядят в `grep assert` одинаково с настоящими утверждениями тестов. Сверку «утверждения не менялись» пришлось делать глазами; пригодился бы разбор, который отделяет строки-данные от вызовов.
