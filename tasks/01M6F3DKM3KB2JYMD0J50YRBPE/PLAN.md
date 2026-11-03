---
task: 01M6F3DKM3KB2JYMD0J50YRBPE
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab В2 — профиль проверок `verify`: ручные проверки `human:<имя>`, команды `verify-ok` и `verify-fail`

## Подход
Новый модуль `orchestrator/verify.py` держит ожидание и обе команды; остальные модули зоны получают точечные вызовы.

- **Поле `verify`** (`targets.py`): `VERIFY_FIELD` в `LOCAL_FIELDS["description"]`, перенос в плоскую запись (`_flatten`); значение проверяет `_verify_error` в `check(..., local=True)` — только для записи, сведённой `merge_local`. Запись слоя репозитория (`check` без `local`) с полем — отказ. Плоская запись локального слоя с полем вне раздела — прежний отказ `merge_local` «поле 'verify' вне раздела». `verify: []` = поля нет (`verify_checks` → `[]`).
- **Ожидание** (`fsm_advance.verifying` + `verify.hold`/`verify.enter_wait`): визит — журнал после последней `state -> verifying`. Задача ждёт отметки, пока последняя из записей `verify.WAIT_ACTION` / `fsm.VERIFYING_STATUS_ACTION` визита — запись ожидания «ждёт проверки <имя> по sha <sha>» (`verify.current_wait`). Опрос задачи, ждущей по текущей голове, CI не опрашивает и до потолка не доходит (`hold`); голова сменилась (подтяжка) — опрос идёт прежним путём CI, его запись статуса снимает прежнее ожидание. Запись ожидания пишет только зелёный путь после прохода `verifying_gate` (`enter_wait`) — одна на визит и голову. Запись проекта не прочитана — `review` не наступает (ожидание до потолка с причиной).
- **Отметки**: таблица `verify_marks` (задача, имя, sha, итог, `visit_step_id`, автор, время) — отметка действительна для своей головы и визита. `verify-ok` проверяет: `verifying`; имя в профиле; итог непуст; sha — префикс текущей головы не короче 7 знаков (иначе «отметка для другой головы»); ожидание текущего визита по этой голове (иначе «проверка не ожидается для этой головы»); имя ещё не отмечено. Пишет отметку и запись `OK_ACTION`; когда отмечены все — `review` автором `operator`.
- **`verify-fail`**: `verifying`, имя в профиле, причина непуста; счётчик `tasks.verify_fails` +1 на каждом возврате (эскалацией не сбрасывается); `fails >= LIMIT_REVIEW_ITERS` — `escalated` с причиной в тексте перехода (её берёт `brief._return_context`), иначе `in_dev` с причиной в тексте перехода. `review_iters` не трогается. Автор переходов — `operator` (ANSWER-1 п. 4): надзор эпика видит в `state -> …` автора `operator` действие Оператора (`auto._operator_actions`), путь подхвата — тот же, что после `approve`.
- **`auto`** (ANSWER-1 п. 3): `_advance_verifying_poll` после опроса — ожидание отметки → `auto_stop(..., alert=False)`, цикл выходит, lease снимает штатный выход `cmd_auto`. `_epic_view`: `verify.waiting` → `_WAITING` (ждёт Оператора, как гейт). Красный CI идёт прежним путём (`_NOT_HOLDING_STOP_STATES` не тронут) — удержание `_child_holds` прежнее.
- **Доска/статус/дозор**: `board.waiting_on` — `operator` при ожидании отметки, иначе `ci` (ANSWER-1 п. 5); `catalog._status_line` — «<- ЖДЁТ ОПЕРАТОРА  [ждёт проверки <первая неотмеченная> по sha <sha>]»; `watch` — `WAIT_ACTION` в классе `gates` и среди значимых для `--notify`.
- **CLI**: `verify-ok`/`verify-fail` в таблице `artel.main` (вне белого списка ролей) и в справке.
- `budget_usd` не переоценивается.

## Шаги
1. `targets.py`: поле `verify`, проверка значения, отказ вне раздела и в слое репозитория — `tests/test_01m6f3dkm3kb2jymd0j50yrbpe_verify_record.py` 19/19 зелёные.
2. `schema.py`/`store.py`: `verify_marks`, `tasks.verify_fails` (тем же литералом в `SCHEMA` и `migrate`); `insert_verify_mark`, `verify_marked_names`.
3. `verify.py` + `fsm_advance.verifying`: ожидание, `hold`/`enter_wait`, команды.
4. `auto.py`, `board.py`, `catalog.py`, `watch.py`, `artel.py`: остановка, надзор, доска, статус, дозор, CLI.
5. Свои тесты `tests/test_verify_profile.py` (ANSWER-1 пп. 1, 2, 4, 5, 6): смена головы внутри визита, потолок при ожидании CI, `verify: []`, автор `operator`; каждый проверен временной мутацией (красный, код возвращён).
6. Приложение к `tests/test_invariants.py` (ниже): `verify-ok`/`verify-fail` в `FsmTest.commands` через `verify_call`; карта `docs/codebase-map.md` регенерирована; код закоммичен (81719054f).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2, 3, 4 |
| 3 | 2, 3 |
| 4 | 2, 3 |
| 5 | 4 |
| 6 | 3 (этап только ждёт отметок, внешних вызовов нет) |
| 7 | 6 |
| 8 | 4 |

## Влияние на систему
- Проекты без `verify` (и артель — `verify.checks` для неё запись не читает) идут прежним путём `verifying`: тот же опрос CI, тот же потолок, тот же переход в `review`. Прогнаны модули: `tests/test_verifying_ceiling.py`, `tests/test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate.py`, `tests/test_auto_cycle.py`, `tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`, доски, `watch`, миграций, `tests/test_store_schema_migration_parity.py` и др. — 390 зелёных; `tests/test_invariants.py` с приложением и без — зелёный.
- Потолок `VERIFYING_CEILING_SEC` снимается только для ожидания отметки (матрица SPEC); до записи ожидания действует (`test_ceiling_still_applies_while_waiting_for_ci`).
- `review` через `verify-ok` — только после записи ожидания текущего визита, которую пишет зелёный путь после `verifying_gate`: зелёный CI и гейт по исходам не обходятся (AC-9, AC-13).
- Новый счётчик `verify_fails` не сбрасывается эскалацией (инвариант 3); `review_iters` не трогается. `auto`/надзор эпика команд не зовут (инвариант 18, AC-19).
- `_NOT_HOLDING_STOP_STATES` не изменён: удержание задачи с красным CI прежнее; признак ожидания — само ожидание визита.
- `merge_after` не меняется.
- Откат — revert коммита 81719054f и снятие приложения; колонка `verify_fails` и таблица `verify_marks` в живой БД без кода безвредны.

## Риски
- Запись проекта с `verify` не прочитана на опросе — задача ждёт до потолка и эскалирует, а не уходит в `review` молча (сознательно строже).
- Смена головы туда и обратно в одном визите (X→Y→X) даст вторую запись ожидания по X — это новый вход в ожидание после записи статуса CI.

## Приложение: tests/test_invariants.py
`git apply --check` на чистом дереве (HEAD 81719054f) — проходит; `python3 -m pytest tests/test_invariants.py` с наложенным приложением — 88 passed, 1219 subtests passed. Временная мутация «`verify-ok`/`verify-fail` всегда отказывают» краснит свип (`AgentRunsOnlyFromRunTest`, 26 подтестов). `plank-run` в шаге — 2 failed «PLAN.md нет в ссылке документов задачи» (PLAN попадёт в ссылку автокоммитом по итогам шага); те же проверки по PLAN.md с диска: `guard.plan_appendices` — одно приложение к `tests/test_invariants.py` без ошибок, добавленные строки несут `verify-ok`, `verify-fail`, `human:stand`, `git apply --check` — код 0.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 1728829c5..7c647d42f 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -484,6 +484,12 @@ class FsmTest(unittest.TestCase):
             # id — по задаче проекта `target-human` в `awaiting_human`
             # песочницы (`mr_sync_call`), а не пустым отказом.
             ("mr-sync", self.mr_sync_call),
+            # Ручная проверка профиля `verify` (SPEC 01M6F3DKM3KB2JYMD0J50YRBPE,
+            # требование 7): по задаче проекта с `verify: [human:stand]` в
+            # ожидании отметки по текущей голове (`verify_call`), а не
+            # отказом «не в verifying».
+            ("verify-ok", lambda: self.verify_call("verify-ok")),
+            ("verify-fail", lambda: self.verify_call("verify-fail")),
         ]
 
     # ------------------------------------- эпик свипа (ADR-0028 п. 17)
@@ -634,6 +640,63 @@ class FsmTest(unittest.TestCase):
                   if r["action"] == mr_sync.SYNC_ACTION]
         assert synced, f"mr-sync не сверил задачу {human} проекта target-human"
 
+    VERIFY_PROJECT = "sweepverify"
+    VERIFY_SHA = "c" * 40
+
+    def verify_call(self, command: str) -> None:
+        """`verify-ok`/`verify-fail` по песочнице, где у проекта профиль
+        `verify: [human:stand]`, а его задача ждёт отметки по текущей голове
+        (SPEC 01M6F3DKM3KB2JYMD0J50YRBPE, требование 7): команда обязана
+        сработать — без отказа (код выхода 0) и с эффектом: `verify-ok` —
+        отметка в БД и `review`, `verify-fail` — `in_dev`. Задача свипа —
+        артели: профиля у неё нет. Перед вызовом — новый визит `verifying` с
+        записью ожидания и нулевой счётчик возвратов (иначе свип по всем
+        состояниям довёл бы `verify-fail` до предела); запись проекта и
+        голова ветки — подмены на время вызова."""
+        from orchestrator import targets, verify
+        conn = store.db()
+        task = getattr(self, "_verify_task", None)
+        if task is None:
+            task = self._verify_task = idgen.new_task_id()
+            store.insert_task(conn, task, "Задача ручной проверки",
+                              "verifying", f"task/{task.lower()}-verify",
+                              self.VERIFY_PROJECT, 1.0)
+        store.update_task(conn, task, state="verifying", verify_fails=0)
+        store.journal(conn, task, "fsm", verify.VISIT_ACTION, "свип")
+        store.journal(conn, task, "fsm", verify.WAIT_ACTION,
+                      verify.wait_text("stand", self.VERIFY_SHA))
+        visit = store.last_task_step_of(conn, task, (verify.VISIT_ACTION,))
+        entry = {"forge": "gitlab", "base": config.MAIN_BRANCH,
+                 "url": f"https://localhost/grp/{self.VERIFY_PROJECT}",
+                 "token_slot": "sweep-token", "no_paths": [],
+                 "project_skills": [], "merge_gate": "target-human",
+                 "verify": ["human:stand"]}
+        real_target = targets.target
+
+        def target(name):
+            return dict(entry) if name == self.VERIFY_PROJECT else real_target(name)
+
+        with mock.patch.object(targets, "target", target), \
+                mock.patch.object(verify, "head",
+                                  lambda task_id, branch: self.VERIFY_SHA):
+            try:
+                if command == "verify-ok":
+                    verify.cmd_verify_ok(task, "stand", self.VERIFY_SHA,
+                                         "стенд проверен")
+                else:
+                    verify.cmd_verify_fail(task, "stand", "стенд не прошёл")
+            except SystemExit as exc:
+                if exc.code not in (None, 0):
+                    raise AssertionError(f"{command} отказал: {exc.code}")
+        state = store.get_task(conn, task)["state"]
+        if command == "verify-ok":
+            marked = store.verify_marked_names(conn, task, self.VERIFY_SHA,
+                                               visit["id"])
+            assert "stand" in marked, f"verify-ok не записал отметку {task}"
+            assert state == "review", f"verify-ok: {task} в {state}, не в review"
+        else:
+            assert state == "in_dev", f"verify-fail: {task} в {state}, не в in_dev"
+
     def run_command(self, call) -> tuple[str, mock.Mock]:
         """Прогон команды с подменённым агентом; SystemExit — тоже исход."""
         out = ""
```

## Предложения системе
- Подтяжка main в ветку задачи после фиксации долгоживущих тестов может сделать их фикстуру устаревшей (здесь `SUPPORTED_PAIRS` из 01M6EZXVFG405Y1BTFDSGBKS8E), а правка — только `amend-tests`: класс «зафиксированная фикстура против подтянутого main» стоит отдельной проверки пульта на подтяжке (прогон долгоживущих файлов задачи на голове после подтяжки).
- Сторож `conftest.py` считает полным прогоном `pytest.main` из `python -c` с одним файлом — временную подмену для диагностики пришлось делать плагином `-p` в корне рабочей копии.

## Ответ на эскалацию (ANSWER-2)
Оператор выбрал вариант (а): подмена `targets.SUPPORTED_PAIRS | {("gitlab", "operator")}` добавлена в стенд `tests/test_01m6f3dkm3kb2jymd0j50yrbpe_verify_flow.py` командой `amend-tests`, утверждения не менялись. Код не менялся. Прогон 04.11: `verify_flow` + `verify_record` + `tests/test_verify_profile.py` — 55 passed.
