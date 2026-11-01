---
task: 01M6AB4VE2R0Q2V5D4MMJGNGH7
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Б2.2 — команда `mr-sync`: сверка MR и нахождения правки в `base`, закрытие `done` по подтверждению Оператора

## Подход

Одна сверка — `orchestrator/mr_sync.py::evaluate` — общая для ручного
`mr-sync`, пересчёта на `--confirm`, опроса надзора эпика и проверки чужого
коммита (SPEC «Оценка объёма», обоснование монолита). Сверка только читает:
`forge.mr_status`, `gitcmd.fetch_ref_sha` базы в клон пульта, `rev-list`/
`cherry`/`patch-id`/`diff`, `git apply --cached --check` на временном индексе
(`GIT_INDEX_FILE` + `read-tree <голова origin/base>`) — рабочее дерево клона
не трогается.

Итог — первая подошедшая строка таблицы требования 3 с порядком ANSWER-1 п. 1:
«MR не найден» (нет `mr_iid` либо 404 хостинга) → «MR переведён на другую
ветку» → «неизвестно» (прочий отказ `forge`, нет `target_branch`, сбой git,
нет точки ответвления/подтверждённой головы) → (а) → (б) → (в) → «в базе
частично» → «нет в базе».
- (а) — только у MR в статусе «влит» (ANSWER-1 п. 3): `merge_commit_sha`,
  иначе `squash_commit_sha`, иначе `sha` MR — предок `origin/<base>`;
  провал (в) при (а) — пометка «после вливания файлы менялись».
- (б) — `git cherry origin/<base> <голова> <точка>` по коммитам
  `rev-list --no-merges <точка>..<голова>`; засчитывается целиком, только если
  найден sha закрытия: самый поздний коммит `<точка>..origin/<base>` с
  `patch-id --stable` последнего коммита задачи (ANSWER-1 п. 2).
- (в) — по каждому файлу диффа `<точка>..<голова>` печатается обратное и
  прямое наложение; признак — обратное наложение всего диффа проходит, прямое
  нет.

Точка ответвления — `mr_sync.record_fork_point` в `_deliver_mr` гейта мержа
перед переходом в `awaiting_human`: `merge-base <подтверждённая голова>
<голова origin/base>`, в столбец `tasks.fork_point` и журнал; сверка берёт
только записанное значение.

Инциденты (требование 5): на `approve` гейта мержа `target-human` —
`_mr_incident_stops` до публикации головы и снятия черновика (MR из БД влит
или закрыт → эскалация; MR открыт и голова ветки на сервере не своя →
эскалация без отправки; статус MR не прочитан → отказ `approve`, задача на
гейте — ANSWER-2 п. 2). Статус MR читается один раз за вызов `approve`
(ANSWER-2 п. 1): тело гейта повторяется после ожидания CI, сверенная задача
помечается в `ContextVar` цикла `_mr_incident_checked`. В `mr-sync` — чужой коммит при открытом MR →
`awaiting_human -> escalated` (`escalated_from=awaiting_human`, возврат
механикой Б2.1а). «Своя» голова — последняя из записей «ветка отправлена» и
«голова ветки на сервере принята»; принятая пишется в
`fsm._approve_escalated` (`mr_sync.accept_server_head`) только когда последняя
эскалация — «чужой коммит» (ANSWER-1 п. 6).

`--confirm` (одна задача, под lease задачи): пересчёт сверки → отказ при
итогах вне «влит этим MR»/«в базе, влит иначе» (с подсказкой `kill`/новая
задача/ожидание) и при (в) без `--by-content` → сверка ссылки документов с
`origin` тем же узлом `artifact_branch.origin_sync_refusal`, что
`_docs_ref_unsynced` пути `done`, текстом ANSWER-1 п. 7 → `awaiting_human ->
done`, `closed_as` (`merged_upstream` по (а), `merged_upstream_other` по
(б)/(в)), `lease.release_any`, `cleanup._commit_closing` с sha доказательства
и строкой «Закрытие: …» в RETRO (по (в) — «по содержимому»), уборка рабочей
копии и локальной ветки (`cleanup.drop_task_branch`, ANSWER-1 п. 8). Ветка на
сервере и MR не трогаются — ни отправок, ни вызовов `forge`, меняющих MR.

Опрос: `policy.mr_sync_interval_min` (`targets.py`, целое > 0), только надзор
эпика (ANSWER-1 п. 5): `auto._poll_mr_sync` на каждом опросе зовёт
`mr_sync.supervised` для задач эпика в `awaiting_human`; срок — от
`tasks.mr_sync_at` по часам пульта (`store.now`), так что «не чаще раза в N
минут» держится и через перезапуск надзора. Смена итога относительно прошлой
сверки — запись «mr-sync: итог сменился», значимая для `watch` (класс
`gates`, уведомление); первая сверка задачи — тоже смена («(первая сверка) →
итог», ANSWER-2 п. 3).

Бюджет SPEC ($50) не пересматривается.

## Шаги

1. Поля `forge.MergeRequest` и их перенос в `gitlab_adapter._merge_request`;
   столбцы `fork_point`, `mr_sync_outcome`, `mr_sync_at` и константы
   `CLOSED_AS_MERGED_UPSTREAM(_OTHER)` (`schema.py`, реэкспорт `store.py`);
   поле `policy.mr_sync_interval_min` (`targets.py`).
2. `orchestrator/mr_sync.py`: сверка, вывод/журнал/строка задачи, инцидент
   «чужой коммит», `--confirm`, опрос надзора; команда в `artel.py` (таблица,
   справка, описание модуля; вне белого списка ролей).
3. Гейт мержа (`fsm_merge_gate.py`): `_mr_incident_stops`, запись точки
   ответвления; `fsm._approve_escalated` — принятая голова.
4. Путь закрытия: `note` в `cleanup._commit_closing` → `snapshot.commit_closing`
   → `retro.build_done`.
5. Надзор и показ: `auto._poll_mr_sync`, `watch` (значимость смены итога),
   `status` (`catalog.py`) и доска (`board.mr_sync_shown`, ячейка MR в `--md`,
   строка в `--html`, поле `mr_sync` в `--json`); подсказка `awaiting_human`
   без «(шаг Б2.2)» (`fsm.AWAITING_HUMAN_HINT`, `config.AUTO_STOP`) и константа
   `HINT` теста Б2.1а по мандату.
6. Юнит-тесты `tests/test_mr_sync_units.py`; приложение к
   `tests/test_invariants.py` (ниже); карта кодовой базы.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2, 3 |
| 3 | 2 |
| 4 | 2, 4 |
| 5 | 2, 3 |
| 6 | 1, 5 |
| 7 | 5 |
| 8 | 6 (приложение) |

## Влияние на систему

- Новый путь в `done` — только команда Оператора `mr-sync <id> --confirm`
  с пересчётом итога; надзор эпика зовёт сверку без `--confirm`
  (`mr_sync.supervised` не имеет пути к `_close`). Свойство держит новый
  инвариантный тест приложения (наблюдает состояние, RETRO в
  `refs/artifacts/<id>`, `closed_as`) и AC-17.
- Сверка ссылки документов с `origin` перед `done` на `--confirm` — тот же
  узел `artifact_branch.origin_sync_refusal`, что у `_docs_ref_unsynced`.
- Гейт мержа `target-human` строже: новые эскалации до публикации головы;
  `operator`-путь и артель не затронуты (ветвь `people_entry`).
- `approve` гейта мержа с `mr_iid` теперь читает `mr_status` (один раз за
  вызов) и отказывает при его сбое. `test_ac15_…` Б2.1б правлен по мандату
  ANSWER-2 п. 1 (множество + `mr_status`, предел одного чтения, строка
  документации). Отказ при сбое краснил ещё четыре теста того же файла —
  их подделка хостинга отвечала на `mr_status` отказом; подделке добавлен
  метод `mr_status` (открытый невлитый MR; отказ при `fail["mr_status"]`) —
  принят ANSWER-3 п. 1, вариант (а), утверждения тестов не менялись.
  Строка мандата ANSWER-3:
  `Ослабление тестов разрешено: tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac9_existing_link_undrafts_and_assigns, tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac11_undraft_or_assign_refusal_no_second_mr, tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac13_draft_on_verifying_undraft_on_gate`.
- Схема БД: три новых столбца `add_column` (идемпотентно), прежние данные не
  меняются. `delivery_policy` отдаёт ещё ключ `mr_sync_interval_min`.
- `watch`: новое значимое действие только «mr-sync: итог сменился».
- Подсказка `awaiting_human`: «состояние ждёт людей проекта — artel.py
  mr-sync <id> [--confirm]»; в существующем тесте меняется только константа
  `HINT` (мандат SPEC/ANSWER-1), утверждение `assert HINT in out` прежнее.
- Откат — revert merge-коммита задачи; столбцы БД остаются пустыми и никем не
  читаются.

Прогнано (`python3 -m pytest … -p timeout`): долгоживущие файлы задачи
(`mr_sync` 47, `mr_fields`, `awaiting_hint`) — зелёные; `tests/test_invariants.py`
с наложенным приложением — 88 passed; модули доставки, доски, `watch`,
надзора эпика, схемы, RETRO/закрытия, `answer`/эскалаций, `zone_lock`,
`merge_after`, карты — зелёные. После ANSWER-2: долгоживущие файлы задачи,
`test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py` (36), `test_mr_sync_units.py`
— 97 passed; `test_invariants.py`, `awaiting_views`, `awaiting_commands`,
`test_watch` — 114 passed; `test_invariants.py` с наложенным приложением
(`git apply --check` проходит) — 88 passed. Мутации своих тестов и приложения
проверены: приём головы при любой эскалации, интервал в секундах, показ итога
вне `awaiting_human`, надзор с `_close`, пустой отбор `mr-sync`, сбой
`mr_status` пропускает гейт, первая сверка не смена, повторное чтение
`mr_status` в цикле гейта — каждая краснит свой тест.

## Риски

- 404 различается по подстроке «(404)» причины адаптера GitLab
  (`gitlab_adapter._status_reason`); иной адаптер без этой формы даст
  «неизвестно», не «MR не найден» — безопасная сторона (закрытия нет).
- `git apply --check` по временному индексу: файлы-подмодули/симлинки не
  проверялись.

## Предложения системе

- Сторож Bash роли отклоняет команды с `$var`, `for`, `{…'…'}` и `cd` —
  мутации и уборку пришлось делать python-heredoc; `skills/coding-standards.md`
  о «временной мутации» молчит об этом ограничении среды.

## Приложение: tests/test_invariants.py

`git apply --check` на чистом дереве ветки задачи — проходит (проверено перед
сдачей).

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 2b6f9c51a..1728829c5 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -480,6 +480,10 @@ class FsmTest(unittest.TestCase):
                 store.REF_KIND_EPIC, self.sweep_epic())),
             ("link --remove epic", lambda: self.link_remove(
                 store.REF_KIND_EPIC, self.sweep_epic())),
+            # Сверка MR (SPEC 01M6AB4VE2R0Q2V5D4MMJGNGH7, требование 8): без
+            # id — по задаче проекта `target-human` в `awaiting_human`
+            # песочницы (`mr_sync_call`), а не пустым отказом.
+            ("mr-sync", self.mr_sync_call),
         ]
 
     # ------------------------------------- эпик свипа (ADR-0028 п. 17)
@@ -585,6 +589,51 @@ class FsmTest(unittest.TestCase):
                                   "SWEEP-2", None, "operator")
         catalog.cmd_link(["--remove", kind, obj, "tracker", "SWEEP-2"])
 
+    MR_SYNC_PROJECT = "sweephuman"
+
+    def mr_sync_call(self) -> None:
+        """`mr-sync` без id по песочнице, где есть проект `merge_gate:
+        target-human` и его задача в `awaiting_human` (SPEC
+        01M6AB4VE2R0Q2V5D4MMJGNGH7, требование 8): сверка обязана пройти по
+        ней — запись сверки в её журнале, — а не отказать пустым набором.
+        Задача свипа — артели: её `mr-sync` не сверяет ни в одном
+        состоянии. Запись проекта и хостинг (`mr_status`: MR открыт) —
+        подмены на время вызова, git — шпион класса."""
+        from orchestrator import forge, mr_sync, targets
+        conn = store.db()
+        human = getattr(self, "_mr_sync_task", None)
+        if human is None:
+            human = self._mr_sync_task = idgen.new_task_id()
+            store.insert_task(conn, human, "Задача людей проекта",
+                              "awaiting_human", f"task/{human.lower()}-mr",
+                              self.MR_SYNC_PROJECT, 1.0)
+            store.update_task(conn, human, mr_iid=7,
+                              mr_url="https://localhost/mr/7")
+        entry = {"forge": "gitlab", "base": config.MAIN_BRANCH,
+                 "url": f"https://localhost/grp/{self.MR_SYNC_PROJECT}",
+                 "token_slot": "sweep-token", "no_paths": [],
+                 "project_skills": [], "merge_gate": "target-human"}
+        real_target = targets.target
+
+        def target(name):
+            return dict(entry) if name == self.MR_SYNC_PROJECT else real_target(name)
+
+        class Hosting:
+            CI_BY_PIPELINE = True
+
+            @staticmethod
+            def mr_status(project, mr):
+                return forge.MergeRequest(iid=mr, state="opened",
+                                          target_branch=config.MAIN_BRANCH)
+
+        before = len(store.task_steps(conn, human))
+        with mock.patch.object(targets, "target", target), \
+                mock.patch.dict(forge.IMPLEMENTATIONS, {"gitlab": Hosting}):
+            mr_sync.cmd_mr_sync([])
+        synced = [r for r in store.task_steps(conn, human)[before:]
+                  if r["action"] == mr_sync.SYNC_ACTION]
+        assert synced, f"mr-sync не сверил задачу {human} проекта target-human"
+
     def run_command(self, call) -> tuple[str, mock.Mock]:
         """Прогон команды с подменённым агентом; SystemExit — тоже исход."""
         out = ""
@@ -3559,3 +3608,64 @@ class TargetHumanDeliveryInvariantTest(unittest.TestCase):
                 else:
                     self.assertEqual(len(stand.fake.named("open_mr")), 1,
                                      where)
+
+
+class MrSyncConfirmIsOperatorOnlyInvariantTest(unittest.TestCase):
+    """Инвариант 18 (`docs/invariants.md:48`) для закрытия задачи проекта
+    `target-human`: `mr-sync <id> --confirm` — команда Оператора, ни
+    `auto <id>`, ни надзор эпика (`auto --epic`) её не зовут и задачу из
+    `awaiting_human` сами не закрывают (SPEC 01M6AB4VE2R0Q2V5D4MMJGNGH7,
+    требование 8). Наблюдается исход, а не аргументы вызова: состояние,
+    коммит закрытия с RETRO в `refs/artifacts/<id>` и `closed_as`.
+
+    Стенд — настоящий git песочницы с bare `origin`, подменённый хостинг и
+    часы надзора: `Stand` долгоживущего файла задачи
+    (`tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py`).
+    """
+
+    def setUp(self):
+        from tests.sandbox import RealGitSandbox
+        from tests import test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync as mr
+        self.mr = mr
+        self.sb = RealGitSandbox()
+        self.sb.setUp()
+        self.addCleanup(self.sb.doCleanups)
+        self.stand = mr.Stand(self.sb)
+
+    def test_auto_and_epic_supervisor_never_confirm_mr_sync(self):
+        """`auto` и надзор эпика не закрывают задачу `mr-sync --confirm` даже при итоге «влит этим MR».
+
+        Сценарий: задача `target-human` в `awaiting_human`, люди влили её
+        коммитом слияния (`mr_status` — «merged»), в записи проекта
+        `policy.mr_sync_interval_min: 1`. `auto <id>`, затем надзор эпика
+        задачи на подменённых часах (5 минут опросов): надзор сверил задачу
+        — итог «влит этим MR» в журнале, — но задача в `awaiting_human`,
+        `closed_as` пуст, RETRO в `refs/artifacts/<id>` нет. Контроль:
+        `mr-sync <id> --confirm` Оператора закрывает её — `done`,
+        `closed_as` `merged_upstream`, RETRO в ссылке документов есть.
+
+        Ловит мутацию: надзор эпика или `auto` зовёт `mr-sync --confirm`
+        (или закрывает задачу по итогу сверки сам) — задача `done`,
+        `closed_as` заполнен, RETRO в `refs/artifacts/<id>`; либо надзор не
+        сверяет вовсе — итога в журнале нет, и свойство доказано пустым.
+        """
+        mr, stand = self.mr, self.stand
+        task = stand.to_awaiting()
+        merge = stand.merge_commit(task)
+        stand.reply(task, state="merged", merge_commit_sha=merge)
+        stand.record(mr_sync_interval_min="1")
+        epic, obs, _session = mr.epic_of(stand, task)
+        clock = mr.Clock(stand, task)
+        out = mr.task_auto(stand, clock, task)
+        out += mr.supervise(stand, clock, epic, obs, 5 * 60)
+        where = stand.context(task, out)
+        self.assertIn(mr.MERGED_THIS, stand.journal(task), where)
+        self.assertEqual(stand.state(task), "awaiting_human", where)
+        self.assertIn(stand.closed_as(task), (None, ""), where)
+        self.assertIsNone(stand.retro(task), where)
+        out = stand.mr_sync(task, "--confirm")
+        where = stand.context(task, out)
+        self.assertEqual(stand.state(task), "done", where)
+        self.assertEqual(stand.closed_as(task), store.CLOSED_AS_MERGED_UPSTREAM,
+                         where)
+        self.assertIsNotNone(stand.retro(task), where)
```

## Ответ Оператора (ANSWER-3)

Вариант (а): метод `mr_status` подделки `FakeForge` принят как есть, код не
менялся. После ответа прогнаны долгоживущие файлы задачи,
`test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py` и `test_mr_sync_units.py` —
97 passed.
