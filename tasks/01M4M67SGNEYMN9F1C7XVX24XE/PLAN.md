---
task: 01M4M67SGNEYMN9F1C7XVX24XE
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Этап 4 ADR-0021, часть A — мерж не кладёт в main снимок задачи и RETRO

## Подход

Шаг публикации мержа `fsm_merge_gate._publish_merge_artifacts` перестаёт
накладывать снимок ссылки документов (`_overlay_artifact_snapshot` удаляется)
и коммитить RETRO/долги (`fsm_postmerge._generate_and_commit_retro` и его
помощники удаляются). Вместо наложения первым шагом публикации идёт проверка
документов задачи на дереве `refs/artifacts/<id>` (новый
`_guard_task_docs_or_refuse`): ревизия — зафиксированная голова
(`tasks.fixed_sha`, без фиксации — голова ссылки), файлы читаются git-ом
(`ls-tree`/`show`) в репозитории задачи без выкладки на диск. Правила:
- любой проект — `guard.is_extraneous_task_root_file` (тот же критерий, что у
  `_guard_task_root_or_refuse`, включая подкаталоги);
- артель, в дереве мержа которой есть `scripts/guard.py` (там же, где их
  сегодня применял `guard --all` дерева мержа), — ещё правила `guard --all`
  к каталогу задачи: посторонние файлы
  `acceptance_tests/` (`is_extraneous_acceptance_test_file`, пропуск
  `__pycache__`), маркер AC-n с отступом (`indented_ac_marker_errors_from_files`),
  структура `.md` (`check_content`, паспорт пропускается) — БЕЗ освобождения
  по `docs/retro/<id>.md`: guard в `--all` освобождает закрытую историю, здесь
  проверяется живая мержащаяся задача.
Ссылки нет / ревизия не читается / файл не прочитан — отказ («merge FAILED»,
scratch снят, `sys.exit`, задача на `merge_gate`). Место — то же, где стояло
наложение: после приложений PLAN, до карты, `guard --all`, sha для push и
коммита закрытия. Правила берутся из guard пульта (он уже судил
`_guard_task_root_or_refuse`), не из `scripts/guard.py` дерева мержа: дерево
мержа каталога задачи больше не несёт.

`guard --all` по дереву мержа артели остаётся на месте (после карты, до
`final_sha`), видит приложения.

RETRO закрытия: sha коммита мержа (`gitcmd.head_sha(scratch)` сразу после
приложений, до публикации) и пути применённых приложений доезжают из
`_cmd_approve_merge_gate` до `cleanup._commit_closing(conn, id, merge_sha=,
applied_appendices=)` -> `snapshot.commit_closing(...)` -> текст
`retro.build_done(conn, id, merge_sha, address=ref)` +
`fsm_postmerge._with_appendices_line`. Без `merge_sha` (путь `kill`, прямые
вызовы) — прежний `gitcmd.head_sha()`.

Провал коммита закрытия: каждая ветка отказа `snapshot.commit_closing` (ссылки
нет, расхождение с фиксацией, git не ответил, исключение построения RETRO —
теперь перехватывается) журналируется, как сегодня, и поднимает
incident-алерт `snapshot.closing` с target проекта задачи; переход и уборка
идут дальше.

Читатели: `retro.build_done` без `address` пишет
`refs/artifacts/<id>` (`artifact_branch.branch_name`); `cleanup.artifacts_in_main`
— каталог в main ИЛИ голова ссылки в репозитории задачи (`artifact_branch.ref_head`).
`cleanup.drop_task_dir` остаётся на прежнем признаке «каталог в дереве main»
(вынесен в `_dir_in_main`): он бережёт отслеживаемый main каталог от rmtree, а
неотслеживаемая локальная копия задачи, чьи документы хранит ссылка, — хвост;
перевод его на ссылку оставлял бы каталог каждой убитой задачи и краснил
шесть методов `tests/test_kill_cleanup.py` (см. вопрос 4 эскалации).
`fsm_merge_gate._guard_task_root_or_refuse` сохранён без изменения поведения
(SPEC «Материалы»: его зовёт `test_guard_task_root_subdirectory.py`).

Тесты снятого механизма — по мандату ANSWER-1 п.1: удаляется
`tests/test_fsm_retro.py` и метод
`test_main_ci_line.py::GuardAllLaunchTest::test_task_retro_does_not_hide_snapshot_violation`;
смены ожидания — ровно три строки раздела «Меняемое поведение» SPEC. Замены —
долгоживущий `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`
(test_author, не правится).

## Шаги

1. `fsm_merge_gate.py`: удалить `_overlay_artifact_snapshot`; новый
   `_guard_task_docs_or_refuse` (+ чтение дерева ссылки); переписать
   `_publish_merge_artifacts` (проверка документов -> карта -> `guard --all`
   -> `final_sha`); в `_cmd_approve_merge_gate` — `merge_sha` после
   приложений и передача в `_commit_closing`. Докстринги.
2. `fsm_postmerge.py`: удалить `_generate_and_commit_retro`,
   `_write_and_stage_retro`, `_commit_retro`, `_retro_incident`; оставить
   `APPENDICES_RETRO_PREFIX`/`_with_appendices_line`.
3. `snapshot.py`: `commit_closing(..., merge_sha="", applied_appendices=None)`,
   инцидент на каждом провале, перехват исключения построения RETRO.
4. `cleanup.py`: `_commit_closing` пробрасывает аргументы; `artifacts_in_main`
   — по ссылке документов.
5. `retro.py`: адрес по умолчанию — `refs/artifacts/<id>`.
6. Тесты: удаление по мандату ANSWER-1; три смены ожидания из SPEC;
   регенерация карты.
7. Мандат ANSWER-2 (итерация после эскалации):
   - `tests/test_retro.py::RetroGenerationTest::test_build_done_has_merge_sha_address_and_first_context_line_only`
     — адрес → `assertIn(f"Адрес артефактов: refs/artifacts/{self.TASK}", text)`,
     добавлен `assertIn("Итог: done, sha " + "deadbeef" * 5, text)`; строки о
     первой строке контекста не тронуты (п.1);
   - `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py::MergeGuardAfterSnapshotTest::test_ac1_clean_snapshot_merges_as_before`
     — `assertTrue(origin_tree_has(...))` → `assertFalse(...)`, добавлена
     проверка, что `{dir}/acceptance_tests/test_ac1_fixture.py` есть в
     `ls-tree -r refs/artifacts/<id>` origin; `done` и сдвиг origin/main не
     тронуты (п.2);
   - `tests/test_retro_artifact_branch_reads.py::RetroBranchReadTest::test_done_address_names_the_snapshot_ref_when_asked`
     — явный адрес отличим (`address="X-адрес"`, проверяется он), вызов без
     `address` — на `refs/artifacts/{TASK}` (п.3);
   - два метода `tests/test_invariants.py` — приложением PLAN ниже (защищённый
     путь, в код ветки не коммитится): внутри метода
     `mock.patch.object(fsm_merge_gate, "_task_docs_files", ...)` с непустым
     чистым деревом `tasks/<id>/SPEC.md`; проверка документов настоящая,
     утверждения не тронуты, `SpyRun` не тронут; в докстринги добавлена
     строка «Ловит мутацию» (п.4);
   - `cleanup.drop_task_dir` — на прежнем признаке «каталог в дереве main»
     (`_dir_in_main`, «None — каталог оставлен» сохранён), шесть методов
     `tests/test_kill_cleanup.py` не тронуты (п.5).
8. Мандат ANSWER-3 (`tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py::MergeGateStepsOnCloneTest::test_ac5_code_map_and_retro_are_committed_in_the_clone_merge_copy`):
   - п.1 — `assertIn` → `assertNotIn(f"docs/retro/{task}.md", self.origin_tree(), …)`;
   - п.2 — после `assert_merged_in_clone` добавлена проверка RETRO закрытия:
     `self.in_repo(self.origin, "show", f"refs/artifacts/{task}:tasks/{task}/RETRO.md")`
     несёт «Итог: done»;
   - п.3 — `assert_merged_in_clone` и карта в origin/main не тронуты;
     докстринг: RETRO в ссылке документов, не в main; в «Ловит мутацию»
     добавлен пропуск RETRO закрытия.
   - Чтобы п.2 был исполним: общий помощник `TaskFlowSandbox.approve_until_settled`
     подменяет `fixation.read` на `("", True)` — с такой подменой
     `fixation.ref_drift` видит «голова ссылки не прочитана», и коммит
     закрытия fail-closed не пишется (требование 4 — инцидент, RETRO нет;
     это поведение кода верное). Помощнику добавлен ключ
     `live_fixation: bool = False`: по умолчанию подмена прежняя (прочие
     вызовы и их утверждения не меняются), метод AC-5 зовёт его с
     `live_fixation=True` — фиксация читается настоящая. Утверждения прочих
     методов не тронуты.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 7 |
| 2 | 1, 2 |
| 3 | 1, 3 |
| 4 | 3, 4 |
| 5 | 2, 3 |
| 6 | 1 |
| 7 | 1, 7 |
| 8 | 1 |
| 9 | 4, 5, 7 |
| 10 | 1 |

## Влияние на систему

- Гейт посторонних файлов документов задачи не ослабляется: читает ту же
  голову, что раньше накладывалась, и строже — недоступная ссылка теперь
  отказ (раньше наложение деградировало до пустого каталога), освобождения по
  `docs/retro/<id>.md` нет.
- `guard --all` по дереву мержа артели сохранён на прежнем месте.
- Механизм killed-долгов снят; его заменяет коммит закрытия на пути `kill`
  с инцидентом на провале (требование 5).
- `docs/retro/*.md` в main больше не прирастает; `budget.py` его читает только
  по истории T-серии (SPEC «Не входит»).
- Откат — revert merge-коммита задачи.

## Риски

- Существующие тесты, которые доводят мерж до публикации без ссылки
  документов (прежнее наложение молча деградировало), теперь получат отказ —
  проверяется прогоном затронутых модулей и `suite-run`.
- Новые инциденты на провале коммита закрытия у задач без ссылки (старше
  ADR-0021) на пути `kill` — по требованию 4 это и есть желаемое.

## Проверки

- `python3 -m pytest tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py` —
  15 passed, 20 subtests (долгоживущий файл задачи, AC-1–AC-13).
- Затронутые модули (`test_plan_appendix`, `test_retro_artifact_branch_reads`,
  `test_snapshot_closing_outcome`, `test_main_ci_line`,
  `test_guard_task_root_subdirectory`, `test_merge_gate_ci_wait`,
  `test_full_suite_reuse`, `test_fsm_merge_gate_done_snapshot`,
  `test_kill_cleanup`, `test_artifact_ref_sync`,
  `test_doctor_artifact_branch_sync`, `test_01m41ab…`, `test_01m409…`,
  `test_01m446…`, `test_fsm_map_regen`, `test_01m42pencs…`) — зелёные, кроме
  `test_retro.py` (вопрос 1) и `FixesMainArgTest` (падает только в окружении
  процесса роли: «команда недоступна процессу роли developer»; в `suite-run`
  зелёный).
- `suite-run` №1: новые на ветке — ровно 4 падения, все перечислены в
  эскалации; на базе падений нет.
- `plank-run`: планка задачи — только перечень долгоживущих файлов,
  `test_*.py` нет («pytest не запускался»); долгоживущий файл прогнан напрямую.
- Карта кодовой базы регенерирована (`python3 scripts/codebase_map.py`).
- Итерация ANSWER-2: `test_retro.py`, `test_retro_artifact_branch_reads.py` —
  зелёные; мутации проверены: «Итог: done» несёт иной sha — красный
  `test_build_done_has_merge_sha_address…`; параметр `address` игнорируется —
  красный `test_done_address_names_the_snapshot_ref_when_asked`.
  `MergeGuardAfterSnapshotTest` в процессе роли не исполняется
  («artel.py approve: команда недоступна процессу роли developer» — тот же
  класс, что `FixesMainArgTest`), проверяется `suite-run`.
- Приложение к `tests/test_invariants.py`: применено во временной правке,
  `MergeOnlyFromMergeGateTest` + `MergeNeedsGreenCiTest` — 7 passed; правка
  снята, `git apply --check` приложения на чистом дереве ветки — проходит.
  `suite-run` этого шага приложение не видит (PLAN читается из ссылки
  документов, в неё он попадёт автокоммитом по итогам шага) — два метода
  там ожидаемо красные до применения приложения.
- `suite-run` №2 (после правок ANSWER-2): новые на ветке — ровно 2,
  `test_invariants.py::MergeOnlyFromMergeGateTest::test_merge_gate_approve_is_that_path`
  и `::MergeNeedsGreenCiTest::test_green_ci_merges` («ссылки документов …
  нет» — их и закрывает приложение); на базе падений нет. Остальные тесты
  вопросов 1–2 эскалации (`test_retro`, `MergeGuardAfterSnapshotTest`) —
  зелёные. Лог: `.artel/logs/suite-run/01M4M67SGNEYMN9F1C7XVX24XE/01M4M67SGNEYMN9F1C7XVX24XE-suiterun-2.log`.
- Итерация ANSWER-3: `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`
  целиком — 30 passed. Мутация «мерж из клона пропускает коммит закрытия»
  (вызов `cleanup._commit_closing` в `_cmd_approve_merge_gate` убран) —
  `test_ac5_code_map_and_retro…` красный; код возвращён. Без
  `live_fixation=True` метод красный на чистом коде (RETRO.md в ссылке
  origin нет — см. шаг 8). Карта регенерирована.

## Предложения системе

- Сверка SPEC «Меняемое поведение» с кодом (аналитик/аудит на передаче)
  пропустила три утверждения, которые требования 1, 7, 9 опрокидывают прямо:
  `test_retro.py:195`, `test_01m3sf7…_main_ci.py:482`, фикстуры
  `test_invariants.py` без ссылки документов. Дешёвая проверка до гейта SPEC:
  grep по `tests/` литералов снимаемого поведения (здесь — «:tasks/{»,
  «снимок артефактной ветки», `origin_tree_has(...tasks/`).

## Приложение: правка tests/test_invariants.py (ANSWER-2 п.4)

Два метода инвариантов мержа в песочнице `FsmTest` (git не исполняется,
ссылки документов нет): чтение дерева ссылки подменено чистым деревом,
проверка документов задачи исполняется настоящая, утверждения методов не
меняются. `git apply --check` на чистом дереве ветки — проходит.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 514349a9..6d698989 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -549,10 +549,22 @@ class MergeOnlyFromMergeGateTest(FsmTest):
         именно ветку задачи) — сам мандат даёт ANSWER-1, образец —
         нелокированный `tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests/
         test_ac15_invariants_12_19_remain_green.py`.
+
+        Ловит мутацию: approve из merge_gate не вливает ветку задачи (merge
+        не вызван либо вливает не её) или не доводит задачу до `done`.
         """
+        from orchestrator import fsm_merge_gate
         self.set_state("merge_gate")
 
-        self.capture(fsm.cmd_approve, self.TASK)
+        # Песочница не исполняет git, и ссылки документов у задачи нет: без
+        # подмены чтения её дерева проверка документов задачи отказывает
+        # мерж «ссылки нет» (SPEC 01M4M67SGNEYMN9F1C7XVX24XE, требование 7).
+        # Сама проверка исполняется настоящая — подменено только чтение
+        # дерева ссылки, чистым деревом документов (ANSWER-2 п.4).
+        with mock.patch.object(
+                fsm_merge_gate, "_task_docs_files",
+                return_value=("d" * 40, [f"tasks/{self.TASK}/SPEC.md"], "")):
+            self.capture(fsm.cmd_approve, self.TASK)
 
         # Ассерт по содержанию инварианта, а не по точному списку вызовов:
         # merge случается здесь и мержит ветку задачи. Равенство всей
@@ -765,10 +777,21 @@ class MergeNeedsGreenCiTest(FsmTest):
         self.assertTrue(any("python=failure" in d for d in details), details)
 
     def test_green_ci_merges(self):
-        """Контроль: гейт проходим — зелёный CI мержит, как и раньше."""
+        """Контроль: гейт проходим — зелёный CI мержит, как и раньше.
+
+        Ловит мутацию: зелёный CI читается как не-зелёный — merge не
+        вызван, задача не доходит до `done`.
+        """
+        from orchestrator import fsm_merge_gate
         self.set_state("merge_gate")
 
-        self.capture(fsm.cmd_approve, self.TASK)
+        # Чтение дерева ссылки документов подменено чистым деревом — та же
+        # причина, что в `test_merge_gate_approve_is_that_path` (ANSWER-2
+        # п.4 SPEC 01M4M67SGNEYMN9F1C7XVX24XE).
+        with mock.patch.object(
+                fsm_merge_gate, "_task_docs_files",
+                return_value=("d" * 40, [f"tasks/{self.TASK}/SPEC.md"], "")):
+            self.capture(fsm.cmd_approve, self.TASK)
 
         self.assertIn("merge", self.git_spy.git_subcommands())
         self.assertEqual(self.state(), "done")
```
