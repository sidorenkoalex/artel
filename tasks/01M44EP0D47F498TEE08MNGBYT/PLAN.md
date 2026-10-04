---
task: 01M44EP0D47F498TEE08MNGBYT
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Порядок мержей по зависимостям задач: поле merge_after

## Подход
Вся механика `merge_after` собрана в одном новом модуле
`orchestrator/merge_after.py`. Его первая строка докстринга называет
`merge_after`, поэтому карта кодовой базы описывает поле через генератор
(AC-15). Остальные модули только зовут его в своих точках:

- **Форма (требование 1).** `scripts/guard.py`: `merge_after_items`,
  `merge_after_form_errors`, `spec_merge_after_errors`. Проверка вызывается
  из `_content_errors` для `type: spec` любой `schema_version`, если поле
  есть. Правило «строка в формате id» — `idgen.is_task_id_form`: алфавит
  ULID, длина не больше полного id, плюс исторический `Tnnn`. Модуль
  `idgen` объявлен единственным местом, знающим формат id, поэтому правило
  стоит рядом с генератором. `SUPPORTED_SCHEMA_VERSION` не тронут.
  Для PLAN guard поле не проверяет: самоссылка в PLAN — штатный случай
  отклонения каналом (AC-10), а отказ guard остановил бы переход.
- **Проверка по БД (требование 2).** `merge_after.check`: форма тем же
  узлом guard, затем по каждому элементу — `store.task_id_matches` (новый
  узел, вынесенный из `store.resolve_task_id`, который теперь его зовёт и
  поведения не меняет; отдельная функция нужна, потому что
  `resolve_task_id` при неоднозначности завершает процесс, а гейту нужен
  мягкий отказ). Дальше проверки: нет задачи, неоднозначный префикс,
  самоссылка после разрешения, `killed`, другой target, повтор после
  разрешения. В конце — цикл: обход в глубину по графу `merge_after` всех
  задач БД, где у проверяемой задачи стоит новое значение. SQL живёт только
  в `store.py` (`tests/test_multitarget.py::SqlOnlyInStoreTest`), поэтому
  добавлен `store.task_state`, а граф строится по `store.all_tasks`.
- **Гейт SPEC.** `fsm._approve_spec_gate` зовёт `merge_after.spec_gate_value`
  сразу после сверки путей с зонами и тем же мягким путём: журнал
  «approve отклонён», печать, `return`. Значение пишется тем же
  `store.update_task`, что `zones`. Колонка `tasks.merge_after` (TEXT, полные
  id через «, ») добавлена в DDL и миграцию `add_column`.
- **Каналы (требование 3).** Все каналы пишут значение через
  `merge_after.rewrite`: колонка и журнал «merge_after изменён» с текстом
  «было → стало (канал: …)».
  - PLAN: `merge_after.apply_plan` вызывается в `fsm_advance.in_dev` сразу
    после `_apply_plan_budget`. Без поля ничего не делает. Значение, которое
    после разрешения совпадает с БД, молча пропускается. Отличное значение
    без упоминания `merge_after` в «Влиянии на систему» или не прошедшее
    проверку даёт запись «merge_after из PLAN отклонён», переход идёт
    дальше.
  - Мандат: маркер `mandate.MERGE_AFTER_MANDATE_MARKER = "Зависимости мержа:"`
    добавлен в `MANDATE_MARKERS`. Для строки этого маркера `mandate.refusals`
    (новые keyword-параметры `conn`/`task_id`) применяет
    `merge_after.value_refusals` вместо правил путей; две такие строки в
    одном файле дают отказ. В `answer._cmd_answer` строка принимается в
    `escalated`, `in_dev`, `review` и в `merge_gate`. В `merge_gate`
    действует рубеж `runner.in_role_environment`, а файл без строки
    отказывается. Значение пишется в БД после коммита ANSWER; проверка
    стоит до него, в `_read_checked_answer_file`. `_has_mandate_lines`
    знает новый маркер, поэтому в `in_dev`/`review` файл с ним идёт путём
    мандата, а не указания.
  - Эскалация роли: отдельного кода нет, правило — в приложении к
    `skills/escalation-rules.md`.
- **Гейт мержа (требование 4).** `merge_after.merge_gate_refuses`
  вызывается в `fsm._approve_merge_gate` до `fsm_merge_gate.
  _cmd_approve_merge_gate_cycle`, то есть до `merge_lock.acquire` и до
  `merge_queue`. Убитая или пропавшая из БД зависимость даёт отказ
  «зависимость мержа убита» с каналом `answer` и строкой
  `Зависимости мержа:`. Незавершённая — отказ «зависимости мержа не в
  done» со списком `<id> (<состояние>)` и подсказкой `artel.py approve <id>`.
- **status/show (требование 5).** `merge_after.status_suffix` — последняя
  добавка строки `catalog.cmd_status`, считается из БД на каждый вызов.
  `merge_after.show_line` печатается в `catalog.cmd_show`.

Бюджет: оценка SPEC ($40) не пересматривается: объём совпал с перечнем
файлов SPEC плюс один новый модуль.

## Шаги
1. Схема, `store.task_id_matches`/`task_state`, `idgen.is_task_id_form`,
   проверка формы в guard.
2. `orchestrator/merge_after.py`; гейт SPEC и гейт мержа в `fsm.py`, канал
   PLAN в `fsm_advance.py`, мандат в `mandate.py`/`answer.py`, `status`/`show`
   в `catalog.py`.
3. Юнит-тесты `tests/test_merge_after.py`, регенерация карты
   `python3 scripts/codebase_map.py`, приложение к защищённым путям (ниже).

Сделано, код закоммичен в ветку задачи (`89933da3`).

Прогоны в шаге (каждый в переднем плане, `-p timeout -o timeout=120`):
- долгоживущие `tests/test_01m44ep0d47f498tee08mngbyt_*.py` (6 файлов) и
  `tests/test_merge_after.py`: 38 passed, 18 subtests; долгоживущие
  прогнаны трижды (зёрна случайные), все разы зелёные;
- планка `artel.py plank-run 01M44EP0D47F498TEE08MNGBYT`: 2 passed, код 0;
- смежные модули: `test_answer*.py`, `test_answer_mandate.py`,
  `test_class_mandate_units.py`, `test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`,
  `test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py`,
  `test_store_schema_migration_parity.py`, `test_zones_approve.py`,
  `test_fsm_spec_gate_path_check.py`, `test_fsm_spec_gate_reject.py`,
  `test_catalog_status_log.py`, `test_task_id_prefix_regression.py`,
  `test_fsm_advance_gate_smoke.py`, `test_guard_schema.py`,
  `test_guard_zones.py`, `test_spec_budget.py`, `test_codebase_map.py`,
  `test_cmd_approve_dispatch.py` — 265 passed;
  `test_merge_queue.py`, `test_merge_lock.py`, `test_merge_gate_ci_wait.py`,
  `test_catalog_zone_overlap.py`, `test_catalog_wave_breaker_status.py`,
  `test_parent_task_division.py`, `test_multitarget*.py`,
  `test_git_fixation.py`, `test_mutation_claim_gate.py`,
  `test_plan_appendix.py`, `test_zones_gate.py`,
  `test_checkpoint_zone_mandate.py`, `test_test_integrity_gate.py`,
  `test_invariants.py`, `test_protected_paths_gate.py`,
  `test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py` — зелёные после
  переноса SQL в `store.py` (первый прогон поймал SQL вне `store.py` в
  новом модуле).
- Сторожа `tests/test_merge_after.py` проверены временной мутацией кода
  по каждой заявке «Ловит мутацию»: все 9 тестов покраснели на своей
  мутации, код возвращён. Одна заявка («нет» вперемешку с id) сначала не
  покраснела: «нет» и так отсекает проверка формы. Заявка переписана под
  мутацию, которую тест действительно ловит (отбрасывание «нет» из
  перечня), и перепроверена.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (форма поля, guard, `SUPPORTED_SCHEMA_VERSION` = 5) | 1 |
| 2 (гейт SPEC по БД, колонка DDL + миграция) | 1, 2 |
| 3 (каналы PLAN, мандат ANSWER, эскалация через мандат) | 2, 3 (приложение к `skills/escalation-rules.md`) |
| 4 (гейт мержа до мьютекса и очереди) | 2 |
| 5 (`status`/`show`) | 2 |
| 6 (карта через докстринг) | 3 |
| 7 (приложение к защищённым путям) | 3 |

## Влияние на систему
- Новая колонка `tasks.merge_after`: NULL у всех существующих задач —
  гейты и вывод для них работают как раньше (AC-5/AC-8/AC-13/AC-14 «без
  поля»). DDL и `migrate` согласованы
  (`tests/test_store_schema_migration_parity.py` зелёный).
- `store.resolve_task_id` — тело вынесено в `task_id_matches` без смены
  поведения: точное совпадение первым, затем LIKE-префикс, тот же текст
  отказа (`tests/test_task_id_prefix_regression.py` зелёный).
- `mandate.MANDATE_MARKERS` теперь из трёх маркеров. Перебирает его только
  `mandate.refusals`. Гейт зон и гейт неослабления читают свои маркеры по
  имени, новый маркер их не задевает. Правила путей для прежних маркеров
  не изменены.
- `answer`: прежние состояния и тексты отказов сохранены; добавлены приём
  в `merge_gate` (только со строкой маркера и вне окружения роли) и
  запись значения после коммита ANSWER. Рубеж окружения роли не ослаблен.
- Гейт мержа: новая проверка только добавляет отказ до мьютекса; при
  пустом поле путь мьютекса/очереди/мержа не меняется. Новых состояний
  FSM нет, `tests/test_invariants.py` не затронут.
- guard: новая проверка срабатывает только при наличии поля `merge_after`
  в SPEC — существующие SPEC без поля валидны без правок.
- Откат — revert одного коммита кода (колонка останется в БД пустой;
  `add_column` идемпотентен) и неприменение приложения.

## Риски
- Зависимость, удалённая из БД мимо пульта (`prune`/ручная правка),
  считается на гейте мержа «не завершится» и требует снятия через
  `answer`. Это сознательно: ждать её бессмысленно.
- Граф цикла строится по всем задачам БД, включая `done`/`killed`, как
  требует SPEC. Задача, завершённая с зависимостью на текущую, тоже
  считается ребром — так цикл закрывается на любом шаге.

## Приложение: templates/SPEC.md, templates/PLAN.md, skills/spec-authoring.md, skills/escalation-rules.md

Требование 7 SPEC. Правка защищённых путей одним блоком на четыре файла.
Блок проверен на чистом дереве ветки задачи командой
`git apply --check -v <файл-с-диффом>`: все четыре файла
(«Checking patch templates/SPEC.md… templates/PLAN.md…
skills/spec-authoring.md… skills/escalation-rules.md…») применяются без
ошибок.

```diff
diff --git a/templates/SPEC.md b/templates/SPEC.md
--- a/templates/SPEC.md
+++ b/templates/SPEC.md
@@ -9,6 +9,13 @@
 # требует поле для schema_version >= 4. Общие зоны (пути, которые трогают
 # все задачи — orchestrator/config.py::COMMON_ZONES) не в счёт.
 # zones: orchestrator/store.py, orchestrator/config.py
+# Зависимости мержа (SPEC 01M44EP0D47F498TEE08MNGBYT) — необязательное
+# поле: id задач (полные или префиксы) через запятую, которые обязаны попасть
+# в main (done) раньше этой. Заполни ТОЛЬКО из ТЗ — строки «Порядок: после
+# …»; без основания поля нет. guard проверяет форму, approve на spec_gate —
+# что задачи есть, не killed, того же target и не замыкают цикл; approve на
+# merge_gate не пустит задачу в main, пока зависимости не в done.
+# merge_after: <id1>, <id2>
 # Потолок задачи, $ — ОБЯЗАТЕЛЬНОЕ поле (ADR-0014): guard отказывает
 # SPEC без него. Класс задачи и ориентир по нему — калибровка
 # orchestrator/config.py::BUDGET_CALIBRATION_TABLE (её уровни и правило
diff --git a/templates/PLAN.md b/templates/PLAN.md
--- a/templates/PLAN.md
+++ b/templates/PLAN.md
@@ -9,6 +9,13 @@
 # обоснованием в «Влиянии на систему». Применяется один раз, только вверх,
 # в пределах потолка ролей (ROLE_BUDGET_CAP).
 # budget_usd: 25
+# Смена зависимостей мержа (SPEC 01M44EP0D47F498TEE08MNGBYT) —
+# раскомментируй, только если порядок мержа задачи должен измениться: новое
+# значение целиком, id через запятую; пустое поле снимает все зависимости.
+# Смену обосновывает раздел «Влияние на систему», и в нём упоминается
+# merge_after — без этого пульт значение отклонит. Проверки те же, что на
+# гейте SPEC; отказ значения пишется в журнал и переход не останавливает.
+# merge_after: <id1>, <id2>
 ---
 
 # PLAN: <название задачи>
diff --git a/skills/spec-authoring.md b/skills/spec-authoring.md
--- a/skills/spec-authoring.md
+++ b/skills/spec-authoring.md
@@ -58,6 +58,12 @@
   объёма и деление» уже использует для сигналов деления, одна разметка
   зон на обе механики. `guard.py` требует поле для `schema_version >=
   4`. `status: ready` в конце.
+  Поле `merge_after:` (SPEC 01M44EP0D47F498TEE08MNGBYT) — id задач,
+  которые обязаны попасть в main раньше этой, через запятую. Заполняй
+  его ТОЛЬКО из ТЗ — строки «Порядок: после …» (или подраздела
+  «## Деление», где порядок назван); изобретать зависимости без
+  основания нельзя: лишняя зависимость держит задачу на гейте мержа, а
+  отказ гейта SPEC по ней возвращает тебе SPEC. Нет основания — поля нет.
 - **Недостаточно.** Один батч — не переписка по одному вопросу за раз:
   `tasks/<id>/QUESTIONS.md` по `templates/QUESTIONS.md`, все неясности
   разом, отсортированные по блокирующести (то, без чего вообще нельзя
diff --git a/skills/escalation-rules.md b/skills/escalation-rules.md
--- a/skills/escalation-rules.md
+++ b/skills/escalation-rules.md
@@ -31,6 +31,14 @@
    если вопрос не снят, новую эскалацию с новым батчем. Оставленный
    прежний `status: escalate` пульт читает как новую эскалацию — задача
    снова встанет, не продвинувшись.
+5. Нужна смена зависимостей мержа задачи (`merge_after`, SPEC
+   01M44EP0D47F498TEE08MNGBYT) — зависимость убита, или порядок мержа
+   оказался другим, — предложи новое значение в эскалации готовой
+   строкой мандата: `Зависимости мержа: <id1>, <id2>` либо `Зависимости
+   мержа: нет` (снять все), значение целиком. В силу оно вступит, только
+   когда Оператор перенесёт строку в ANSWER-n.md (`answer`); сама
+   эскалация значение не меняет. (Разработчик вправе сменить его и
+   полем `merge_after` PLAN.md — см. templates/PLAN.md.)
 
 ## Чего не делать
 - Не выбирать интерпретацию «на свой вкус» при неоднозначности SPEC.
```

## Предложения системе
- Песочница Bash шага роли отказывает heredoc с f-строками
  («brace with quote character») и `for … done`. Чтобы собрать unified-дифф
  приложения, скрипт пришлось класть временным файлом в каталог
  документов. Не хватает команды пульта, которая строит дифф приложения к
  защищённому пути из правленой копии (например, `appendix-diff <id>
  <путь> <правленый файл>`) и сразу гоняет `git apply --check`.
- `idgen.py` объявлен единственным местом, знающим формат id, но правила
  формы (префикс/полный id) до этой задачи там не было. Проверки формы id
  в других местах стоит сводить к `idgen.is_task_id_form`.
