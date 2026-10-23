---
task: 01M5KP57JXWKKKCJKY47HT21W8
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Правило о полном наборе тестов у ревьювера — одно, в миссии шага; приложения скилов (CR-2, CR-1)

# Ревьювер: одно правило о полном наборе тестов в миссии шага

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-2 ★ (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии, раздел находок и «ТЗ-черновики для топ-★»). Решение Оператора 23.10 — вариант А: ревьюверу полный набор `tests/` запрещён; ревьювер гоняет только файлы задачи, полный набор — гейт пульта; правило одно и в одном источнике, как `suite_run_note` у разработчика. Ссылки сверены с `origin/main` 71ce9904; `orchestrator/role_prompt.py` между HEAD главной копии и `origin/main` изменился без сдвига строк.

- Миссию ревьювера собирает `orchestrator/role_prompt.py:141` (ветка `else` функции `mission_brief_package`, строка `f"замечании. {_reviewer_checks_note(task_id, artel)}\n"` — `orchestrator/role_prompt.py:151`). Своего правила о полном наборе в миссии нет.
- `_reviewer_checks_note` — `orchestrator/role_prompt.py:323`. У артели — фраза «Права не сужены: тесты, guard и другие исполняемые проверки запускай…»; у внешнего проекта — перечень команд пульта, в котором `orchestrator/role_prompt.py:335` называет `` `{pult} suite-run {task_id}` — полный набор тестов `` — прямое разрешение полного прогона.
- У разработчика правило сведено в одну функцию: `orchestrator/role_prompt.py:413` (`suite_run_note`), миссия разработчика зовёт её один раз (`orchestrator/role_prompt.py:134`).
- Промпт шага склеивает миссию, скилы роли и ревью-пакет: `orchestrator/runner.py:749` (`_build_prompt`), `orchestrator/runner.py:759` (миссия + «СКИЛЫ РОЛИ»), `orchestrator/runner.py:778` («РЕВЬЮ-ПАКЕТ»). Скилы ревьювера любого проекта — `roles.yaml:40` (`conventions-core`, `escalation-rules`, `review-checklist`).
- Текст скилов шага читает `brief.skills_text` из ветки пульта. Форма вердикта `templates/REVIEW.md` входит в ревью-пакет (`review.review_package`).
- Скил `skills/review-checklist.md` (защищённый путь) несёт два противоречащих абзаца раздела «Проверено исполнением»: урок 04.09 «Прогон полного набора и планки — в переднем плане…» и решение 05.09 «Полный набор `tests/` в шаге ревью не запускай…». Образец `templates/REVIEW.md` (защищённый путь) показывает полный прогон формой `python3 -m unittest discover -s tests`, которую сторож `conftest.py` (`pytest_configure`) не ловит: он проверяет только свой процесс pytest.
- Отказ `suite-run <id>` без флагов есть только для разработчика: `orchestrator/suite_run.py:257` (`_developer`), `orchestrator/suite_run.py:272` (`_refuse_developer_full_run`).
- Существующий тест закрепляет прежний перечень команд ревьювера внешнего проекта: `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::MissionTest::test_ac7_external_reviewer_mission_keeps_suite_run` требует в миссии строку `` `<pult> suite-run <id>` — полный набор тестов ``. Решение варианта А с ним несовместимо — см. раздел «Меняемое поведение существующих тестов».
- Правка скила и образца — защищённые пути (`config.PROTECTED_PATHS`: `skills/`, `templates/`); `doc-commit` их не принимает (`orchestrator/notes.py:724`, `_doc_commit_path_refusal`: только `docs/**` и файлы конфигурации). Путь — приложение PLAN задачи: CI ветки накладывает приложения перед тестами (`scripts/plan_appendix_ci.py`, `docs/operator-session.md`, «Приложения PLAN в CI ветки»), в main они едут воротами мержа. Дифф приложений — в разделе «Приложения PLAN» ниже; оба применяются к дереву пина 89732e3e (`git apply --check`, 23.10).
- Решение Оператора 23.10 (находка CR-2026-10-22-1, вариант А): шаг «Разнос находок» в `skills/code-revision.md` едет приложением этой же задачи (приложение 2) — та же защищённая область, тот же порядок наложения.

## Требуется

1. В `orchestrator/role_prompt.py` — константа модуля `REVIEWER_FULL_SUITE_RULE` (строка), единственный источник правила для ревьювера. Текст:
   «Полный набор тестов в шаге ревью не запускай — ни командой пульта `suite-run`, ни `pytest` или `unittest` по всему `tests/`: его гоняют CI и гейты пульта (приёмка и мерж). В шаге — планка задачи и тесты файлов задачи.»
2. Миссия ревьювера (ветка `else` функции `mission_brief_package`) включает `REVIEWER_FULL_SUITE_RULE` ровно один раз — сразу после фразы `_reviewer_checks_note`, одинаково у артели и у внешнего проекта.
3. `_reviewer_checks_note` для внешнего проекта больше не называет `suite-run`: перечень — `` `{pult} guard {task_id} [<файл>]` — структура артефактов `` и `` `{pult} plank-run {task_id} [<файл>]` — планка и долгоживущие файлы задачи ``, затем прежнее «запускай их, когда они доказывают или опровергают замечание.». Фраза для артели — прежняя побайтно.
4. Миссии остальных ролей (analyst, spec_auditor, test_author, developer), в том числе `suite_run_note`, не меняются побайтно.
5. Тесты, детерминированные, без сети. Промпт ревьювера в тесте — миссия `role_prompt.mission_brief_package(conn, task_id, t, "reviewer", cwd, docs_dir)` (подмены компонентов — как `components_empty` в `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py`: `brief.developer_brief`, `brief.step_notes_block`, `review.review_package`, `review.previous_verdict_sha`), к которой приклеены тексты скилов `roles.skills("reviewer")` из каталога `skills/` репозитория ветки и текст `templates/REVIEW.md` репозитория ветки — по образцу склейки `runner._build_prompt`. Для задачи артели и для задачи учебного внешнего проекта (запись `targets.yaml` песочницы — как в `test_ac7_external_reviewer_mission_keeps_suite_run`):
   - текст `role_prompt.REVIEWER_FULL_SUITE_RULE` встречается в промпте ровно один раз;
   - в промпте нет `suite-run <id>` без ` --failed`/` --wait` (форма проверки — как `bare_full_run` того же файла);
   - в промпте нет подстрок `unittest discover`, `Прогон полного набора`, `— полный набор тестов`;
   - у внешнего проекта миссия называет `` `<pult> plank-run <id>` `` и `` `<pult> guard <id>` `` полным путём пульта.
   Ловит мутацию: правило продублировано в двух местах миссии или не добавлено; перечень команд внешнего проекта сохранил `suite-run <id>`; в скил вернулся абзац 04.09 или в образец — `unittest discover`. На текущем коде тест красный (правила нет, у внешнего проекта — `suite-run <id>`).
   Утверждения о тексте скилов и образца зависят от приложения 1: где они живут (тест `tests/` на дереве «ветка плюс приложения» либо сторож внутри приложения, `skills/spec-authoring.md:166`) — решает SPEC с учётом того, как приложения накладывают CI ветки, автогейт приёмки и ворота мержа.
6. Отдельный тест: миссии analyst, spec_auditor, test_author, developer, собранные до и после правки одними входами, текста `REVIEWER_FULL_SUITE_RULE` не содержат (ловит мутацию «правило добавлено в общий хвост всех миссий»).

## Меняемое поведение существующих тестов

- `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::MissionTest::test_ac7_external_reviewer_mission_keeps_suite_run` — сейчас требует в миссии ревьювера внешнего проекта `` `<pult> suite-run <id>` — полный набор тестов ``. По решению Оператора 23.10 (вариант А) эта формулировка снимается. Предлагаемая замена утверждения (сценарий прежний): миссия содержит `role_prompt.REVIEWER_FULL_SUITE_RULE`, `` `<pult> plank-run <id>` `` и `` `<pult> guard <id>` ``, и в ней нет `suite-run <id>` без ` --failed`/` --wait`. Правка этого файла — только по мандату Оператора (файл долгоживущий у задачи 01M5HDB1GS; путь правки — `amend-tests` либо мандат в ANSWER). Без мандата — эскалация, не правка. Остальные существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/role_prompt.py, tests/

Ограничение зон по смыслу: в `orchestrator/role_prompt.py` — только константа `REVIEWER_FULL_SUITE_RULE`, ветка ревьювера в `mission_brief_package` и `_reviewer_checks_note`.

Приложением: skills/review-checklist.md, templates/REVIEW.md, templates/ (приложение 1), skills/code-revision.md (приложение 2) — дифф ниже переносится в PLAN.md дословно; перед сдачей — `git apply --check` на чистом дереве базы ветки (`skills/conventions-core.md:54`).

Только чтение: .artel/home/, .artel/logs/, docs/audits/README.md, docs/backlog.md, orchestrator/artel.py, orchestrator/notes.py, scripts/plan_appendix_ci.py, orchestrator/runner.py (вызывающий `mission_brief_package` — не меняется), orchestrator/brief.py, orchestrator/review.py, orchestrator/advance_gates/capacity.py, orchestrator/context_package.py, orchestrator/store.py (вызывающие подменяемых в тесте функций — не меняются), skills/, orchestrator/roles.py, orchestrator/suite_run.py, orchestrator/project_profile.py, orchestrator/config.py, roles.yaml, conftest.py, skills/coding-standards.md, docs/operator-session.md.

Мандат Оператора 23.10 на правку `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::MissionTest::test_ac7_external_reviewer_mission_keeps_suite_run` дан; строку мандата с матрицей неослабления Оператор передаёт через `answer` на эскалации роли.

Не входит: отказ `suite-run <id>` без флагов для роли reviewer в `orchestrator/suite_run.py` (механическое закрепление запрета; задевает `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::OtherCallersTest::test_ac6_other_callers_start_full_run_as_before`, где случайная роль, кроме developer, запускает полный прогон, — отдельная задача с мандатом Оператора); слова «после прогона Оператора или ревьювера» в `suite_run_note` разработчика (их закрепляет `MissionTest::test_ac7_developer_mission_names_failed_wait_and_ci_gate`); сторож `conftest.py` для формы `unittest` (защищённый путь); правка `docs/operator-session.md`.

Бюджет: $20.

## Приложения PLAN

### Приложение 1 (CR-2): skills/review-checklist.md, templates/REVIEW.md

```diff
diff --git a/skills/review-checklist.md b/skills/review-checklist.md
index bea37597..42312758 100644
--- a/skills/review-checklist.md
+++ b/skills/review-checklist.md
@@ -223,12 +223,12 @@ HEAD», но этот sha — не всегда надёжный ориенти
 выглядит нормально». Guard проверяет только форму (секция непуста),
 содержательность заполнения — на твоей совести как ревьювера.
 
-Прогон полного набора и планки — в переднем плане, с явным таймаутом
-команды (до 10 минут). Команда, которую клиент увёл в фон, вердикта
-не даёт: не жди её и не откладывай REVIEW.md «до уведомления» — шаг
-завершится вместе с твоим последним сообщением, и итерация пропадёт
-(инцидент 04.09: четыре ревью подряд закончились без вердикта). Не
-успеваешь полный набор — прогоняй по модулям и перечисли их в
+Прогоны шага — планка задачи и тесты файлов задачи — в переднем плане,
+с явным таймаутом команды (до 10 минут). Команда, которую клиент увёл в
+фон, вердикта не даёт: не жди её и не откладывай REVIEW.md «до
+уведомления» — шаг завершится вместе с твоим последним сообщением, и
+итерация пропадёт (инцидент 04.09: четыре ревью подряд закончились без
+вердикта). Не успеваешь — прогоняй по файлам и перечисли их в
 «Проверено исполнением».
 
 Планку задачи гоняй только командой пульта `artel.py plank-run <id>
@@ -241,8 +241,8 @@ HEAD», но этот sha — не всегда надёжный ориенти
 уборка (`shutil.rmtree("tasks")`) пять раз удалила весь отслеживаемый
 каталог задач рабочей копии.
 
-Полный набор `tests/` в шаге ревью не запускай: его гоняет CI на каждый
-пуш ветки, и его зелёный статус — условие гейтов verifying и merge. В
-шаге — планка задачи и тесты затронутых модулей; сверку «набор не
-ослаблен» делай по диффу `tests/` (удалённые/изменённые ассерты), не
-прогоном. Решение Оператора 05.09.
+Правило о полном наборе тестов в шаге ревью — одно, в миссии шага
+(`orchestrator/role_prompt.py`, общее для проектов); здесь оно не
+повторяется. Сверку «набор не ослаблен» делай по диффу `tests/`
+(удалённые/изменённые ассерты), не прогоном. Решения Оператора 05.09
+и 23.10.
diff --git a/templates/REVIEW.md b/templates/REVIEW.md
index c770d0a4..8767f30a 100644
--- a/templates/REVIEW.md
+++ b/templates/REVIEW.md
@@ -52,7 +52,8 @@ git-истории файла.
 <Обязательна при status: approved (иначе guard отклонит артефакт),
 необязательна при остальных статусах. Какие команды/тесты ты реально
 запускал и что они показали — не пересказ diff глазами. Пример:
-«`python3 -m unittest discover -s tests` — 214 тестов, все зелёные».>
+«`python3 -m pytest tests/test_review.py -p no:cacheprovider` — 37
+тестов, все зелёные; `artel.py plank-run <id>` — планка, код выхода 0».>
 
 ## Предложения системе
 <Необязательно, 0–5 пунктов. То же, что в PLAN.md: наблюдение про
```

### Приложение 2 (CR-1): skills/code-revision.md

```diff
diff --git a/skills/code-revision.md b/skills/code-revision.md
index aecc00c4..d013bf71 100644
--- a/skills/code-revision.md
+++ b/skills/code-revision.md
@@ -22,6 +22,10 @@
   файлов, установка пакетов, сеть, git-команды кроме чтения.
 - Единственный создаваемый файл — отчёт (см. «Выход»); всё остальное
   дерево после тебя нетронуто. Коммитит отчёт Оператор.
+- Единственная команда записи — разнос находок в бэклог командой
+  пульта `note` из главной копии (шаг «Разнос находок» раздела
+  «Выход», решение Оператора 23.10); `docs/backlog.md` руками не
+  правится, другие команды пульта не вызываются.
 - `.artel/home/` — вне объекта ревизии целиком (курируемый слой ролей).
 - Содержимое `.artel/logs/` и журнала БД в отчёт НЕ цитируется —
   только адреса, счётчики и размеры (отчёт уходит в git навсегда;
@@ -159,3 +163,20 @@ docs/audits/code-revision-<дата>.md: сводка (5 строк: число
 приложения: таблицы направлений 0, 10, 11 и готовая строка индекса
 `docs/audits/README.md` (Оператор вставляет её тем же коммитом —
 без строки индекса следующая ревизия не дедуплицирует).
+
+### Разнос находок (решение Оператора 23.10, CR-2026-10-22-1)
+Последний шаг ревизии до сдачи отчёта: каждая находка отчёта,
+у которой нет строки в `docs/backlog.md`, получает строку бэклога
+командой из главной копии (путь главной копии называет промпт
+запуска ревизии; рабочая копия ревизии для этого не годится):
+`python3 orchestrator/artel.py note бэклог --text "| <П> | <якорь
+CR-…>: <кандидат> | <суть, адрес файл:строка> | <рамка $> | <зоны> |
+<условие старта> |"` — шесть колонок, якорь `CR-<дата>-<n>` в
+колонке «Кандидат» дословно, чтобы судьбу находки находил поиск по
+якорю. Находка, уже покрытая строкой бэклога, — новой строки не
+получает: в отчёте рядом с ней пишется, какой строкой она покрыта.
+Переоткрытия прошлых ревизий — то же правило. Отчёт завершается
+таблицей «Разнос»: якорь — исход (`note` записана / удержана окном
+мержа / покрыта строкой … / отказ команды с текстом). Отказ `note`
+не обходится ручной правкой бэклога: исход «отказ» и текст — в
+таблицу, разнос этой находки доделывает Оператор.
```
