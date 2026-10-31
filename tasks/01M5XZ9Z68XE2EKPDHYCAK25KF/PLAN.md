---
task: 01M5XZ9Z68XE2EKPDHYCAK25KF
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Б2.1б — гейт мержа `target-human` открывает MR, черновой MR и `max_in_flight` через `forge`

## Подход

Опора — имена Б2.1а, уже влитые в ветку: `targets.delivery_policy`,
`targets.merged_by_project_people`, `store.set_mr_link`/`store.mr_link`,
`fsm.AWAITING_HUMAN`, отказ отправки ветки в `awaiting_human` в
`gitcmd`. Своих полей и столбцов задача не вводит.

1. **Одна функция MR через `forge`** — `github_adapter.open_forge_mr`
   (модуль Draft-MR-флоу задачи; его уже импортируют и гейт мержа, и
   гейты входа в `verifying`): описание `mr_description` — только
   защищённые пути проекта, изменённые веткой до переданной головы
   (дифф от `gitcmd.diff_base`), исполнитель `mr_assignee` — только целое
   (`delivery_policy` уже делает целым строку цифр; булево, имя и
   отсутствие — без исполнителя с записью «исполнитель не числовой id —
   не назначен»), успех — `store.set_mr_link` и запись журнала «MR
   открыт» с адресом. Описание пишется только при открытии.
2. **Гейт мержа** — `fsm_merge_gate._approve_for_project_people`, ветвь
   из `_cmd_approve_merge_gate` сразу за `_profile_refusal_exit` (под тем
   же мьютексом и тем же циклом ожидания CI). Порядок: сверка ссылки
   документов с `origin` -> `_protected_path_diff_gate` ->
   `_test_integrity_diff_gate` -> отказ по приложениям PLAN
   (`appendix_tree.read_plan`) -> подтверждённая голова кода (`код=`
   записи «sha зафиксирован» с sha = `fixed_sha`: у внешнего проекта sha
   `approve` — голова ссылки документов) против головы ветки ->
   сдвиг `base` (`_origin_main_sha` не предок подтверждённой головы ->
   `in_dev` с причиной «base сдвинулся — подготовка ветки заново») ->
   публикация головы -> голова на сервере (`remote_branch_sha`) против
   подтверждённой -> неослабление по исходам -> лок планки -> зелёный CI
   головы ветки (прежний цикл `_wait_for_branch_ci_green`) -> канарейка
   (`_refuse_mr_during_canary`, тот же флаг `--during-canary`) -> предел
   `max_awaiting` (счёт задач своего проекта в `awaiting_human`) -> MR.
   Ссылки в БД нет — `open_forge_mr(draft=False)`; 409 по тексту адаптера
   (`ответил кодом 409 на`) — эскалация «MR ветки уже существует, ссылки
   в БД нет»; иной отказ — задача на гейте с причиной. Ссылка есть —
   `undraft_mr`, затем `assign_mr` только для числового id (ANSWER-2
   п. 3). Успех — `awaiting_human`. Прежний путь `operator` не тронут.
3. **Черновой MR на входе в `verifying`** — `tests_writing._origin_push_gate`
   делится на публикацию (`_publish_head_gate`, прежнее тело) и
   `_forge_draft_mr_gate` -> `github_adapter.ensure_forge_draft_mr`:
   запись `target-human`, `draft_mr: true`, ссылки нет — `open_mr(draft=True)`
   при любом исходе публикации, в том числе голова уже на сервере
   (повтор после отказа). Отказ — `GateRefusal` «переход отклонён:
   черновой MR не открыт», задача в `in_dev`. Путь `amend-tests` зовёт
   `ensure_head_in_origin` и черновик не открывает. Путь `gh`
   (`ensure_draft_mr`) для `target-human` выключен (ANSWER-2 п. 1).
4. **`max_in_flight`** — `gitcmd._in_flight_refusal` в `_push_plan`
   рядом со сверкой автора: отправка ветки задачи без записи «ветка
   отправлена» (обе формы) отказывается до git, если незакрытых задач
   этого проекта с такой записью уже `max_in_flight`. Отказ — обычный
   `_refuse` с журналом задачи, без алерта (у отказа всегда есть своя
   задача). `ensure_draft_mr` GitHub узнаёт отказ по
   `gitcmd.IN_FLIGHT_LIMIT_REASON` и не поднимает инцидент (ANSWER-2 п. 4).
5. **`status`** — `catalog._delivery_suffix`: последний отказ доставки
   после последней смены состояния или успешной отправки —
   «[очередь: предел awaiting_human]», «[очередь: предел max_in_flight]»,
   «[черновой MR не открыт: …]».

Бюджет: оценка SPEC не меняется.

## Шаги

1. `github_adapter.py`: `people_entry`, `mr_assignee`, `mr_description`,
   `open_forge_mr`, `ensure_forge_draft_mr`, константы действий; выключен
   `gh` для `target-human`; отказ пределом на черновике GitHub — не
   инцидент.
2. `gitcmd.py`: `IN_FLIGHT_LIMIT_REASON`, `_in_flight_refusal`, вызов в
   `_push_plan`.
3. `advance_gates/tests_writing.py`: `_publish_head_gate` +
   `_forge_draft_mr_gate` в `_origin_push_gate`.
4. `fsm_merge_gate.py`: `_approve_for_project_people` и помощники.
5. `catalog.py`: `_delivery_suffix` в строке `status`.
6. Тесты: `tests/test_mr_delivery_units.py` (свойства вне долгоживущего
   файла); приложение к `tests/test_invariants.py` ниже; карта
   `docs/codebase-map.md` регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (что исполняется / не исполняется на гейте, сверка sha с головой и с сервером) | 4 |
| 2 (сдвиг base -> `in_dev`) | 4 |
| 3 (приложения PLAN — отказ) | 4 |
| 4 (MR через `forge`, исполнитель, ссылка, 409, undraft/assign) | 1, 4 |
| 5 (`max_awaiting` под мьютексом, строка `status`) | 4, 5 |
| 6 (черновой MR на входе в `verifying`, повтор, описание) | 1, 3, 5 |
| 7 (`max_in_flight` в единой точке отправки) | 2, 1, 5 |
| 8 (инварианты — приложение к `tests/test_invariants.py`) | 6 |

Проверено исполнением: долгоживущий
`tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py` — 36 passed (до
кода — 27 failed); планка `plank-run` `test_ac3_await_main_ci_not_called.py`
— 1 passed; `tests/test_mr_delivery_units.py` — 10 passed, каждая заявка
мутации проверена временной мутацией (7 мутаций — красные); тесты
затронутых модулей (github_adapter, gitcmd_push_point, catalog_status,
rewrite_flow, draft_mr*, merge_gate*, fsm_advance*, amend*, awaiting*,
invariants, multitarget_invariants и др.) — 252 + 171 + 218 passed.
Приложение ниже наложено на рабочее дерево: `tests/test_invariants.py` —
87 passed; мутации «ветвь target-human выключена», «нет ожидания CI
головы», «точка отправки пропускает ветку в awaiting_human» — красные.
`git apply --check` приложения на чистом дереве — применяется.

## Влияние на систему

- Проекты с `operator` (артель, GitHub): ветвь гейта мержа выбирается
  `targets.merged_by_project_people`, прежнее тело не изменено;
  `_origin_push_gate` для них — прежняя публикация, черновой гейт
  возвращает `None` без обращения к хостингу; `ensure_draft_mr` для них —
  прежний (проверка гейта людей проекта — на уже прочитанной записи, без
  нового вызова `targets.target`).
- Точка отправки `gitcmd`: новый отказ срабатывает только при заданном
  `policy.max_in_flight` (умолчание `None`) и только на первой отправке;
  повторная отправка, удаление, `--dry-run`, ссылки документов — без
  изменений.
- Гейты не ослаблены: на ветви `target-human` исполняются все проверки
  целостности прежнего тела (документы, защищённые пути, неослабление по
  тексту и по исходам, лок планки, зелёный CI головы, канарейка);
  отменены только шаги механизма мержа, который пульт для этого проекта
  не выполняет (матрица неослабления SPEC). Сверка sha строже: добавлены
  голова ветки и голова на сервере.
- Откат — revert одного merge-коммита задачи; схема БД не меняется.

## Риски

- Подтверждённая голова кода берётся из записи фиксации: `approve` с
  sha, у которого записи «sha зафиксирован» нет (фиксация не
  записалась), отказывает «голова не подтверждена» — fail-closed.
- Добавка `status` читает журнал задачи на каждую строку (так же, как
  поле токенов).

## Предложения системе

- Миссия шага велит при `amend-tests` отказывать пределом «в начале
  команды» (ANSWER-2 п. 2), а SPEC выводит `orchestrator/amend.py` из
  зон: толкование Оператора на гейте SPEC, требующее файла вне зон, стоит
  сопровождать `zones-extend` в том же ответе — иначе разработчик
  упирается в гейт зон.
- `pytest -n` в шаге разработчика сторож трактует как полный прогон
  (каждый воркер получает отказ): в `coding-standards.md` стоит назвать,
  что тесты затронутых модулей гоняются без `-n`.

## Приложение: инварианты доставки target-human к tests/test_invariants.py

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 887e2c28e..2b6f9c51a 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -3429,3 +3429,133 @@ class SharedFixturesWrapSandboxClassesInvariantTest(unittest.TestCase):
                     issubclass(cls, (sandbox.TmpDirTest, sandbox.TmpRootTest)),
                     f"{node.name}: {cls.__name__} — не песочница")
         self.assertTrue(fixtures, "в tests/fixtures.py нет фикстур")
+
+
+class TargetHumanDeliveryInvariantTest(unittest.TestCase):
+    """Инварианты доставки через MR проекта с `merge_gate: target-human`
+    (SPEC 01M5XZ9Z68XE2EKPDHYCAK25KF, требование 8; ADR-0029 п. 1, 7).
+
+    Пульт такого проекта не вливает ветку задачи и не отправляет `base`:
+    MR вливают люди проекта, и ветка задачи в `awaiting_human` — их. MR
+    (нечерновой, гейта мержа) открывается или снимается с черновика только
+    для головы, подтверждённой Оператором, с зелёным CI. Черновой MR на
+    входе в `verifying` открывается до CI (требование 6) — его этот
+    инвариант не касается.
+
+    Стенд — настоящий git песочницы с bare `origin` и подменённым
+    хостингом: `Stand` долгоживущего файла задачи
+    (`tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py`), образец
+    свипа — `MergeOnlyFromMergeGateTest`.
+    """
+
+    def setUp(self):
+        from tests.sandbox import RealGitSandbox
+        from tests import test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery as delivery
+        self.delivery = delivery
+        self.sb = RealGitSandbox()
+        self.sb.setUp()
+        self.addCleanup(self.sb.doCleanups)
+        self.stand = delivery.Stand(self.sb)
+
+    def _base_pushes(self) -> list:
+        return [p for p in self.stand.pushes
+                if any(a.endswith(f":{config.MAIN_BRANCH}")
+                       or a.endswith(f"refs/heads/{config.MAIN_BRANCH}")
+                       for a in p)]
+
+    def test_target_human_never_merges_pushes_base_or_awaiting_branch(self):
+        """Пульт не сливает, не отправляет `base` и не отправляет ветку задачи в `awaiting_human`.
+
+        Сценарий: `approve` гейта мержа записи `target-human` уводит задачу
+        в `awaiting_human` — без единого `git merge` и отправки `base`,
+        голова `base` на сервере прежняя. Затем в ветку задачи ложится
+        коммит, и команды пульта, публикующие голову ветки (`advance`,
+        `approve`, `ensure_head_in_origin`), её не отправляют: голова
+        ветки на сервере прежняя, шпион отправок её не видит.
+
+        Ловит мутацию: ветвь `target-human` гейта мержа проходит
+        плотницкое слияние и отправку `base` прежнего пути; либо точка
+        отправки пропускает ветку задачи в `awaiting_human`.
+        """
+        from orchestrator import github_adapter
+        stand = self.stand
+        stand.record(draft_mr="false")
+        task = stand.new_task(state="merge_gate", published=True)
+        base_before = stand.main_sha()
+        out = stand.approve(task)
+        where = stand.context(task, out)
+        self.assertEqual(stand.state(task), "awaiting_human", where)
+        self.assertFalse([c for c in stand.git_calls
+                          if self.delivery.git_sub(c) == "merge"], where)
+        self.assertEqual(self._base_pushes(), [], where)
+        self.assertEqual(stand.main_sha(), base_before, where)
+        served = stand.origin_head(task)
+        stand.commit_code(task, {"kod/posle.py": "P = 1\n"})
+        stand.reset_spies()
+        with stand.spy():
+            self.delivery.capture_out(fsm.cmd_advance, task)
+            self.delivery.capture_out(fsm.cmd_approve, task)
+            github_adapter.ensure_head_in_origin(stand.conn, task,
+                                                 stand.branch(task))
+        where = stand.context(task)
+        self.assertEqual(stand.branch_pushes(task), [], where)
+        self.assertEqual(stand.origin_head(task), served, where)
+        self.assertEqual(self._base_pushes(), [], where)
+        self.assertEqual(stand.state(task), "awaiting_human", where)
+
+    def test_mr_opens_or_undrafts_only_for_confirmed_green_head(self):
+        """MR гейта мержа открывается или снимается с черновика только для подтверждённой головы с зелёным CI.
+
+        Сценарий: запись `target-human`. Красный CI подтверждённой головы —
+        ни `open_mr`, ни `undraft_mr` (у задачи с черновым MR в БД).
+        Голова ветки после фиксации ушла вперёд — `open_mr` не зван.
+        Зелёный CI подтверждённой головы — `open_mr` зван один раз, голова
+        ветки на сервере — подтверждённая; у задачи с черновым MR —
+        `undraft_mr` один раз, `open_mr` не зван.
+
+        Ловит мутацию: CI головы ветки не требуется перед MR (MR открыт или
+        черновик снят при красной голове); либо в MR уходит голова, не
+        сверенная с подтверждённой фиксацией.
+        """
+        stand = self.stand
+        stand.record(draft_mr="false")
+        cases = []
+        for linked in (False, True):
+            task = stand.new_task(state="merge_gate", published=True)
+            if linked:
+                iid = stand.rng.randrange(100, 10 ** 6)
+                store.update_task(stand.conn, task, mr_iid=iid,
+                                  mr_url=f"https://localhost/mr/{iid}")
+            cases.append((task, linked))
+        for task, linked in cases:
+            with self.subTest(черновик_в_бд=linked, ci="красный"):
+                stand.fake.red.add(stand.head(task))
+                out = stand.approve(task)
+                where = stand.context(task, out)
+                self.assertEqual(stand.fake.named("open_mr"), [], where)
+                self.assertEqual(stand.fake.named("undraft_mr"), [], where)
+                self.assertEqual(stand.state(task), "merge_gate", where)
+                stand.fake.red.discard(stand.head(task))
+        task, _linked = cases[0]
+        with self.subTest(голова="не подтверждена"):
+            store.record_fixation(stand.conn, task)
+            sha = store.get_task(stand.conn, task)["fixed_sha"]
+            stand.commit_code(task, {"kod/lishniy.py": "L = 1\n"})
+            out = stand.approve(task, sha, refix=False)
+            where = stand.context(task, out)
+            self.assertEqual(stand.fake.named("open_mr"), [], where)
+            self.assertEqual(stand.state(task), "merge_gate", where)
+        for task, linked in cases:
+            with self.subTest(черновик_в_бд=linked, ci="зелёный"):
+                out = stand.approve(task)
+                where = stand.context(task, out)
+                self.assertEqual(stand.state(task), "awaiting_human", where)
+                self.assertEqual(stand.origin_head(task), stand.head(task),
+                                 where)
+                if linked:
+                    self.assertEqual(stand.fake.named("open_mr"), [], where)
+                    self.assertEqual(len(stand.fake.named("undraft_mr")), 1,
+                                     where)
+                else:
+                    self.assertEqual(len(stand.fake.named("open_mr")), 1,
+                                     where)
```

## Эскалация

**Вопросы**

1. ANSWER-2 п. 2 требует отказа пределом `max_in_flight` на пути
   `amend-tests` в начале команды, до коммита правки. Для этого нужен
   вызов проверки первым действием `amend._cmd_amend_tests` — файл
   `orchestrator/amend.py` вне зон SPEC («Не входит»: «`orchestrator/amend.py`
   вне зон (предел `max_in_flight` на его пути — в `gitcmd.py`)»); гейт
   зон откажет такой правке. Сейчас реализован отказ в единой точке
   отправки `gitcmd` (AC-17 зелёный): `amend-tests` коммитит правку в
   кодовую ветку, отправка отказывается пределом, команда выходит
   recovery-путём (`amend._recovery_exit`, «tests_locked_sha не сдвинут»),
   локальный коммит остаётся неотправленным.
   Варианты:
   (а) `zones-extend 01M5XZ9Z68XE2EKPDHYCAK25KF orchestrator/amend.py` —
   добавлю публичную `gitcmd.in_flight_refusal(task_id)` и её вызов первым
   действием `_cmd_amend_tests` (отказ до коммита, без отправки), плюс
   юнит-тест;
   (б) оставить отказ только в точке отправки `gitcmd` (как сейчас),
   отказ «в начале команды» — отдельной задачей.
   **Дефолт при молчании: (б).**

**Контекст**

Реализация остальных требований закончена и проверена (раздел «Покрытие
требований»): долгоживущий файл 36/36, планка зелёная, приложение к
инвариантам применяется. Вызов `github_adapter.ensure_head_in_origin` на
пути `amend-tests` — `amend.py:834`; коммит правки идёт раньше
(`_amend_with_long_lived`/`_amend_plank_only`).

**Блокирует**

Только п. 2 ANSWER-2 (момент отказа на пути `amend-tests`); остальной
код готов к ревью в нынешнем виде.
