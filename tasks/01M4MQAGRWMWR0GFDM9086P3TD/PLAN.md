---
task: 01M4MQAGRWMWR0GFDM9086P3TD
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Аудит SPEC — шаг spec_auditor между сдачей SPEC и spec_gate

## Подход

Новое агентское состояние `spec_audit` (роль `spec_auditor`) встаёт между
`spec_writing` и `spec_gate` обычной записью `config.STATE_ROLE` — без
особого случая в `runner.step_role`. Всё знание пульта о визите аудита —
в одном новом модуле внутри зоны `orchestrator/advance_gates/`:
`orchestrator/advance_gates/spec_audit.py` (вход, сигналы, свежесть,
привязка, выход, вердикт из журнала). Отдельный модуль `orchestrator/
spec_audit.py` вне зон SPEC не заводится — пакет `advance_gates/` в зонах.

Ключевые решения:

1. **Маршрут.** `fsm_advance.spec_writing` после прежних проверок (батч
   вопросов → грязная копия → guard → `apply_spec_budget`, порядок не
   тронут) спрашивает `runner.step_role(t)`: `analyst` (у задачи есть
   ТЗ) — переход в `spec_audit` и запись входа; иначе — `spec_gate`, как
   было. Бюджет применяется до первого шага аудитора (тем же вызовом, что
   и раньше, — он уже стоял до смены состояния).
2. **Запись входа** (`ENTRY_ACTION`, актор `fsm`): `SPEC.md <sha
   содержимого> — сигналы: …; разбор: полный|краткий`. sha — `git
   rev-parse <ссылка>:tasks/<id>/SPEC.md` (содержимое, не голова ссылки);
   если git sha не дал — тот же git-blob-sha считается по тексту файла с
   той же ссылки (`blob_sha`), значения совпадают по построению. Запись
   пишется на каждом входе: из `spec_writing`, командой `spec-audit` и при
   возврате из `escalated` (`fsm._approve_escalated`, SPEC мог смениться
   за эскалацию).
3. **Сигналы** — `signals()`: а) непустой раздел «Меняемое поведение»;
   б) строка мандата (`mandate.elements` по маркерам зон и ослабления
   тестов) в ЛЮБОМ `ANSWER-n.md`; в) зоны SPEC и пути разделов
   «Требования»/«Критерии приёмки» против `config.SPEC_AUDIT_SIGNAL_PATHS`
   (четыре непустые категории: тесты, гейты — с `orchestrator/
   advance_gates/` и `gates.yaml`, лимиты, песочница ролей; сверка той же
   формулой `config.is_protected_path(path, prefixes)`), защищённые пути
   (`guard.protected_zones` → `config.is_protected_path`), упоминание
   «приложени… PLAN»; г) `budget_usd >= config.SPEC_AUDIT_BUDGET_SIGNAL_USD`
   (45, через `budget.spec_budget`); д) `ADR-NNNN` в ТЗ.
4. **Свежесть** (`freshness_refusal`): последний коммит `SPEC-AUDIT.md` в
   ссылке (`git log -1 -- <путь>`) — с префиксом сообщения автокоммита
   роли `spec_auditor` (тот же текст, что `own_commit_marker` в
   `checkpoint._commit_external_step_artifacts`; checkpoint — только
   чтение, префикс повторён функцией `autocommit_prefix` с отсылкой), и
   его sha назван в записи журнала автокоммита (актор `orchestrator`)
   ПОСЛЕ последней записи `state -> spec_audit`. Иначе — отказ
   `SPEC_AUDIT_NOT_FRESH_REFUSAL_ACTION` подкласса «роль ещё не
   закончила» (`refusal_classes`), `auto` запускает аудитора. git не
   ответил — `BRANCH_UNREAD` (чинит Оператор), fail-closed.
5. **Привязка** (`binding_refusal`): текущий sha содержимого SPEC.md
   против sha входа (отказ `SPEC_AUDIT_SPEC_CHANGED…`, класс «чинит
   Оператор») и `spec_sha` файла против sha входа (отказ
   `SPEC_AUDIT_SPEC_SHA…`, класс «чинит роль»); текст отказа называет оба
   sha. Собственный автокоммит аудитора содержимого SPEC не меняет —
   прохода не ломает.
6. **Выход** (`fsm_advance.spec_audit`, порядок как у `review`): файл с
   ветки → свежесть → статус (`draft` — «жду вердикта») → грязная копия →
   guard → `escalate` (тем же каналом, что `_review_escalate`:
   `escalated_from = spec_audit`, `answer_baseline`, маркер шага роли) →
   привязка → `leave()`. `pass`/`concerns` → `spec_gate` + запись
   `VERDICT_ACTION`; `fail` → `spec_writing` с отклонениями раздела
   «Вердикт» в detail перехода + запись `RETURN_ACTION`, пока число
   `RETURN_ACTION` в журнале < `config.SPEC_AUDIT_FAIL_RETURNS` (2); затем
   `fail` → `spec_gate` с вердиктом. Счётчик — только журнал (БД не
   трогается), `reject`/`spec-audit` его не сбрасывают.
7. **Вердикт на гейте** — только из журнала (`last_verdict`, сброс новой
   записью `state -> spec_audit`): `show` (строка `summary`), `status`
   (добавка `[аудит SPEC: …]` на `spec_gate`), остановка `auto` (причина +
   подсказка флага при `fail`), `approve` (`fail` без
   `--accept-audit-fail` — отказ с именем флага; с флагом — запись
   `ACCEPTED_FAIL_ACTION` актором `operator` после всех прочих отказов
   гейта), канарейка (`_pass_spec_gate`: `fail` — `_kill_inconclusive` с
   вердиктом в тексте, прогон красный). Флаг вне `spec_gate` — `sys.exit`
   по образцу `--no-answer`; `_approve_sha_arg` флаг за sha не берёт.
8. **Бриф аудитора** (`brief.spec_auditor_brief`): TZ.md, SPEC.md
   целиком, каждый ANSWER-n.md, проекция карты — описью и дисциплиной
   частей брифа разработчика; QUESTIONS.md, логи и прочие документы не
   берутся. Миссия (`role_prompt._spec_auditor_mission`) несёт sha входа,
   сигналы и ровно одну из фраз «полный разбор»/«краткий разбор». Возврат
   по `fail` — триггер «Причины возврата» брифа аналитика
   (`_RETURN_TRIGGER_STATES_BY_TARGET["spec_writing"]` += `spec_audit`).
9. **Артефакт**: тип `spec_audit` в `guard.RULES` (семь разделов,
   статусы draft|ready|escalate), `spec_audit_field_errors` (непустые
   `verdict`/`signals`/`spec_sha`, `verdict` из перечня), правило
   «Эскалация» распространено на тип; `SPEC-AUDIT.md` — точным именем в
   `TASK_ROOT_ALLOWED_MD`. Обязательный артефакт шага —
   `runner._missing_required_artifact`.
10. **Перечни состояний**: `zone_lock.LATER_STATES`,
    `merge_after.STATUS_DECLARED_STATES`, `report.STATE_ORDER`,
    `docs/stack.md` (оба места), `FSM_STATES` в `tests/test_auto_cycle.py`
    (правкой) и `tests/test_invariants.py` (приложением).
11. **Команда** `spec-audit <id>` (`fsm.cmd_spec_audit`, lease): только с
    `spec_gate`; потолок из SPEC, переход актором `operator`, запись входа.

Бюджет SPEC ($85) не переоцениваю.

## Шаги

1. Ядро: `config` (STATE_ROLE, лимит возвратов, порог и пути-признаки
   сигналов), `advance_gates/spec_audit.py`, `refusal_classes`,
   `fsm_advance` (маршрут из `spec_writing`, обработчик `spec_audit`,
   эскалация), `fsm` (диспетчер, approve с флагом, возврат из эскалации,
   `cmd_spec_audit`), `artel.py` (флаг, команда, справка).
2. Роль и бриф: `runner._missing_required_artifact`,
   `role_prompt` (миссия), `brief` (бриф аудитора, триггер возврата).
3. Вывод и перечни: `catalog` (show/status), `auto` (остановка),
   `canary` (автогейт), `zone_lock`/`merge_after`/`report`,
   `docs/stack.md`.
4. guard: тип `spec_audit`, поля, правило «Эскалация», белый список.
5. Тесты: `tests/sandbox.py` (роль в карте фикстуры), `FSM_STATES`
   `tests/test_auto_cycle.py`, объявленная смена ожидания
   `tests/test_analyst_role.py`, свои юнит-тесты
   `tests/test_spec_audit_gate.py`; карта кодовой базы.
6. Приложения PLAN (ниже): `roles.yaml`, `templates/SPEC-AUDIT.md`,
   `skills/spec-audit.md`, `tests/test_invariants.py`.

Проверено в шаге:
- долгоживущие файлы задачи: `…_spec_audit_units.py` 8/8,
  `…_spec_audit_flow.py` 23/23 (по классам, последовательно);
- планка `plank-run … test_ac23_canary.py` — 2 passed;
  `test_plan_appendices.py` читает PLAN.md из ссылки документов — до
  автокоммита шага красна («PLAN.md нет в ссылке»); её логика проверена
  на PLAN.md с диска: `roles.yaml` после приложения даёт `agent`/`strong`/
  `spec-audit`, заполненный шаблон — `guard.check_content` без ошибок;
- все четыре приложения: `git apply --check` на чистом дереве — код 0;
  с наложенными приложениями `tests/test_invariants.py` и
  `tests/test_roles_map_fixture.py` зелёные (87 passed);
- модули: analyst_role, auto_cycle, refusal_classes, stack_zones_pull,
  catalog_*, fsm_*, runner_*, guard_*, brief, canary*, report, merge_after,
  zone_lock*, тесты наборов моделей — зелёные; новые
  `tests/test_spec_audit_gate.py` 4/4, каждый покраснел на своей мутации;
- полный набор `suite-run` не запущен: замок прогона держала задача
  01M4M67SGNEYMN9F1C7XVX24XE все попытки шага — набор прогонят CI и гейт.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 Состояние аудита | 1 (`config.STATE_ROLE`) |
| 2 Вход в аудит | 1 (`fsm_advance.spec_writing`) |
| 3 Прежние проверки входа | 1 (порядок не тронут) |
| 4 Бюджет из SPEC | 1 (`apply_spec_budget` до перехода; `cmd_spec_audit`) |
| 5 Роль spec_auditor | 6 (приложение `roles.yaml`), 5 (фикстура) |
| 6 Бриф аудитора | 2 |
| 7 Глубина по сигналам | 1 (`signals`, запись входа), 2 (миссия) |
| 8 Артефакт SPEC-AUDIT.md | 4, 6 (шаблон) |
| 9 Белый список | 4 |
| 10 Обязательный артефакт шага | 2 |
| 11 Выход из аудита | 1 |
| 12 Свежесть | 1 (`freshness_refusal`) |
| 13 Привязка к SPEC | 1 (`content_sha`, `binding_refusal`) |
| 14 Вердикт — запись журнала | 1 (`leave`, `last_verdict`) |
| 15 Бриф возврата | 2 (`_RETURN_TRIGGER_STATES_BY_TARGET`) |
| 16 Вердикт на гейте | 1 (approve, флаг), 3 (show/status/auto) |
| 17 Повторный аудит | 1 (`cmd_spec_audit`) |
| 18 Перечни состояний | 3 |
| 19 Канарейка | 3 (`canary._pass_spec_gate`) |
| 20 Свипы инвариантов | 5, 6 |
| 21 Ослабления нет | см. «Влияние на систему» |

## Влияние на систему

- **Гейты не ослабляются.** Проверки выхода из `spec_writing` (батч
  вопросов, грязная копия, guard SPEC, бюджет) идут прежним порядком и
  прежним кодом; меняется только целевое состояние задачи с ТЗ. Задача
  без ТЗ идёт прежним путём (AC-3). `approve` на `spec_gate` получает
  дополнительный отказ (последний вердикт `fail`), прочие сверки гейта не
  тронуты. Канарейка `fail` не проводит — ужесточение.
- **Свежесть и привязка — fail-closed**: git не ответил на историю файла
  — отказ «чинит Оператор»; запись входа без sha — отказ.
- **Белый список** `TASK_ROOT_ALLOWED_MD` расширен ровно именем
  `SPEC-AUDIT.md` (не маской) — `SPEC-AUDIT2.md` остаётся посторонним
  (AC-11).
- **Существующие тесты.** Меняется ожидание одного метода из раздела SPEC
  «Меняемое поведение»: `tests/test_analyst_role.py::AutoAnalystTest::
  test_auto_runs_analyst_and_stops_at_spec_gate` `call_count` 1 → 2.
  Помимо этого в методе: фейк второго шага пишет `SPEC-AUDIT.md` (так
  требует сам раздел SPEC), и свежесть вердикта подменена «свежим»
  (`mock.patch.object(spec_audit, "freshness_refusal", return_value=None)`)
  — лёгкая песочница метода без истории ссылки документов (`gitcmd.git` —
  заглушка), а свежесть — предмет долгоживущего `…_flow.py::FreshnessTest`
  на настоящем git; утверждения метода, кроме объявленного, прежние.
  `FSM_STATES` в `tests/test_auto_cycle.py` и (приложением)
  `tests/test_invariants.py` расширены — свипы, не смена ожиданий.
  `tests/sandbox.py::FIXTURE_ROLES` получил роль `spec_auditor` (без
  скила `spec-audit`: его файл едет приложением) — иначе свип
  `AgentRunsOnlyFromRunTest` не мог бы запустить агента в `spec_audit`.
- **Инварианты.** Агент по-прежнему стартует только из `run` в
  состояниях `STATE_ROLE` (свип `test_invariants` с `spec_audit` зелёный
  при наложенном приложении); `auto` не зовёт approve/reject — гейт
  `spec_gate` остаётся ручным.
- **Откат** — revert мерж-коммита задачи и обратное наложение четырёх
  приложений (`git apply -R`). Задачи, оказавшиеся в `spec_audit` к
  моменту отката, переводятся Оператором на `spec_gate` вручную.
- Колонок и миграций БД нет: счётчик и вердикт — записи журнала.

## Риски

- Префикс автокоммита повторён в `spec_audit.autocommit_prefix`, а не
  импортирован (`checkpoint.py` в этой задаче только чтение): смена текста
  `own_commit_marker` без правки здесь даст «вердикт не свежий» на каждом
  шаге — поймают долгоживущие flow-тесты (AC-13/AC-15).
- Аудитор, записавший `SPEC-AUDIT.md` байт-в-байт как в прошлом визите,
  не создаст нового коммита файла — вердикт сочтётся несвежим, пока текст
  не изменится (sha SPEC, отклонения). Для LLM-аудитора маловероятно.
- Задача без ТЗ: после `fail` повторного аудита и `reject` на гейте её
  SPEC Оператора идёт на гейт мимо аудита, а последний вердикт журнала
  (`fail`) остаётся «последним» (требование 16 сбрасывает его только новым
  входом в `spec_audit`) — `approve` потребует флага или `spec-audit`.

## Предложения системе

- `orchestrator/checkpoint.py`: префикс автокоммита роли
  (`own_commit_marker`) стоит вынести в публичную функцию — читателей
  становится два (удаление артефактов и свежесть вердикта аудита).
- SPEC, объявляющий смену ожидания метода лёгкой песочницы, стоит
  сверять с механикой, которой у песочницы нет (здесь — история ссылки
  документов): объявление «только call_count» оказалось неполным без
  подмены свежести.

## Приложение: roles.yaml — роль spec_auditor

Требование 5: роль агента состояния `spec_audit`, ярус `strong`, скил `spec-audit`.

```diff
diff --git a/roles.yaml b/roles.yaml
index c5a9f965..4e317979 100644
--- a/roles.yaml
+++ b/roles.yaml
@@ -17,6 +17,13 @@ roles:
     token_slot: artel-analyst
     skills: [conventions-core, escalation-rules, spec-authoring]
     model_tier: strong            # ярус -> модель: .artel/models.yaml (tiers)
+  spec_auditor:
+    executor: agent              # ADR-0022: независимый аудит SPEC между
+                                  # spec_writing и spec_gate (SPEC-AUDIT.md);
+                                  # модель аналитика не наследуется
+    token_slot: artel-spec-auditor
+    skills: [conventions-core, escalation-rules, spec-audit]
+    model_tier: strong            # ярус -> модель: .artel/models.yaml (tiers)
   test_author:
     executor: agent              # A4 (tasks/T023): приёмочные тесты до кода
     token_slot: artel-test-author
```

## Приложение: templates/SPEC-AUDIT.md — шаблон вердикта аудита

Требование 8: разделы а–ж, поля `verdict`/`signals`/`spec_sha`; заполненный шаблон проходит guard.

```diff
diff --git a/templates/SPEC-AUDIT.md b/templates/SPEC-AUDIT.md
new file mode 100644
index 00000000..91854405
--- /dev/null
+++ b/templates/SPEC-AUDIT.md
@@ -0,0 +1,52 @@
+---
+task: TASK_ID
+type: spec_audit
+author_role: spec_auditor
+status: draft        # draft | ready | escalate
+verdict: pass        # pass | concerns | fail
+signals: нет         # сигналы глубины из миссии шага дословно, либо «нет»
+spec_sha: SPEC_SHA   # sha содержимого проверенного SPEC.md из миссии шага
+schema_version: 5    # версия формата артефакта, см. scripts/guard.py
+---
+
+# SPEC-AUDIT: <название задачи>
+
+## ТЗ и SPEC
+<а) Соответствие в обе стороны: каждое требование ТЗ и каждое решение
+ANSWER-n.md отражено в SPEC; в SPEC нет требования, которого нет в ТЗ.
+Расхождение — со ссылкой файл:строка.>
+
+## Факты против кода
+<б) Утверждения SPEC о коде (имена, места, поведение) сверены с рабочим
+каталогом: что подтвердилось, что нет — файл:строка.>
+
+## Проверяемость критериев
+<в) Каждый AC-n: проверяем ли тестом и какую мутацию кода такой тест
+поймает. Критерий, который не ловит ни одной правдоподобной мутации, —
+отклонение.>
+
+| Критерий | Проверяем | Ловимая мутация |
+|---|---|---|
+| AC-1 | да | ... |
+
+## Зоны
+<г) Права записи: зоны SPEC покрывают всё, что требования заставят
+менять; песочница ролей; защищённые пути — только приложением PLAN.>
+
+## Матрица неослабления
+<д) Форма docs/operator-gates.md: строка на каждое свойство, которое
+задача трогает.>
+
+| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
+|---|---|---|---|---|
+
+## Пути обхода гейтов
+<е) Как исполнитель мог бы выполнить SPEC буквально, обойдя смысл
+гейта или проверки; каждый найденный путь — отклонение.>
+
+## Вердикт
+<ж) pass — отклонений нет; concerns — отклонения есть, решение за
+Оператором на гейте; fail — SPEC возвращается аналитику. Перечень
+отклонений со ссылками файл:строка. Вопрос, без ответа Оператора на
+который вердикт не вынести, — status: escalate и отдельный раздел
+эскалации по skills/escalation-rules.md.>
```

## Приложение: skills/spec-audit.md — скил аудитора SPEC

Требование 5: скил роли `spec_auditor` (ADR-0022 п.2).

```diff
diff --git a/skills/spec-audit.md b/skills/spec-audit.md
new file mode 100644
index 00000000..9700bb15
--- /dev/null
+++ b/skills/spec-audit.md
@@ -0,0 +1,48 @@
+# Скил: spec-audit (аудитор SPEC)
+
+Ты — независимая проверка SPEC аналитика до гейта SPEC (ADR-0022). Ты не
+наследуешь ни контекст аналитика, ни контекст Оператора, писавшего ТЗ:
+работаешь по ТЗ, SPEC, ответам Оператора (ANSWER-n.md), карте кодовой
+базы и самому коду. Твоя метрика — найденные расхождения; `pass` без
+проверки — пропущенная находка, которую иначе увидит только Оператор на
+гейте, а то и разработчик посреди работы.
+
+## Что проверяешь (разделы SPEC-AUDIT.md)
+- **а) ТЗ и SPEC** — соответствие в обе стороны: требование ТЗ или
+  решение ANSWER, потерянное в SPEC, и требование SPEC, которого нет ни в
+  ТЗ, ни в ответах.
+- **б) Факты против кода** — каждое утверждение SPEC о коде (функция,
+  константа, место ~строка, поведение) сверь с рабочим каталогом.
+- **в) Проверяемость критериев** — у каждого AC-n назови мутацию кода,
+  которую поймает тест на него. Критерий, пропускающий правдоподобную
+  поломку, — отклонение.
+- **г) Зоны** — зоны SPEC покрывают всё, что заставят менять требования;
+  защищённые пути (`config.PROTECTED_PATHS`) меняются только приложением
+  PLAN; песочница ролей не расширяется молча.
+- **д) Матрица неослабления** — форма `docs/operator-gates.md`: строка на
+  каждое свойство, которое задача трогает (тест, гейт, лимит, проверка).
+  «Остаётся, не покрыто» без требования-замены — отклонение.
+- **е) Пути обхода гейтов** — как исполнитель мог бы выполнить SPEC
+  буквально и обойти смысл гейта или проверки.
+- **ж) Вердикт** — перечень отклонений со ссылками файл:строка.
+
+## Глубина
+Глубину задаёт миссия шага по сигналам SPEC: полная (каждый раздел а–е
+по существу, с проверкой по коду) или краткая (вердикт и отклонения;
+раздел без находок — одной строкой). Сигналы из миссии перенеси в поле
+`signals` дословно, sha проверенного SPEC — в `spec_sha`.
+
+## Вердикт
+- `pass` — отклонений нет.
+- `concerns` — отклонения есть, но решить их может Оператор на гейте.
+- `fail` — SPEC в таком виде вести дальше нельзя: возврат аналитику с
+  твоими отклонениями (не больше двух возвратов за жизнь задачи, дальше
+  вердикт идёт на гейт).
+
+## Чего не делать
+- Не правь SPEC.md, ТЗ и код: правка SPEC за визит аудита делает вердикт
+  недействительным, переход на гейт откажет.
+- Не выдумывай требования сверх ТЗ: отсутствие желаемого, которого не
+  просили, — не отклонение.
+- Вопрос, без ответа Оператора на который вердикт не вынести, — не
+  догадка, а `status: escalate` по skills/escalation-rules.md.
```

## Приложение: tests/test_invariants.py — FSM_STATES

Требование 20: `spec_audit` в свипах инвариантов (только дополнение кортежа).

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 514349a9..b660b9d6 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -71,10 +71,11 @@ TRUNCATED_CI = json.dumps({
 
 # Все состояния FSM (docs/design.md §6 в срезе Фазы 0, artel.py docstring).
 # tests_writing — A4 (tasks/T023): приёмочные тесты до кода, между
-# spec_gate и in_dev.
-FSM_STATES = ("spec_writing", "spec_gate", "tests_writing", "in_dev",
-              "review", "acceptance", "merge_gate", "done", "escalated",
-              "killed")
+# spec_gate и in_dev. spec_audit — аудит SPEC между spec_writing и
+# spec_gate (SPEC 01M4MQAGRWMWR0GFDM9086P3TD).
+FSM_STATES = ("spec_writing", "spec_audit", "spec_gate", "tests_writing",
+              "in_dev", "review", "acceptance", "merge_gate", "done",
+              "escalated", "killed")
 
 # Заготовки артефактов — валидные по guard: с T017 он вызывается кодом на
 # каждом переходе `advance`, и артефакт без обязательных секций задачу не
```
