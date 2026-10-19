---
task: 01M590GJAF0EDV4NBC4C99MFVH
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: G1б — итог тестов компонента из отчёта (JUnit, отчётчик пульта Vitest, установка и окружение пультом)

## Подход

Один различитель и один узел прогона «по отчёту», в который сходятся все
места прогона; прежний путь артели и записей без `report` не трогается.

1. **Профиль несёт поля компонента.** `project_profile.Profile` получает
   `component`, `project`, `report_args`, `select`, `failure_errors`,
   `checks_local`, `from_components`. Заполняет их тот же помощник
   `with_tools`, что уже зовут `decide`, `acceptance._task_own_profile` и
   (теперь) `suite_run._profile_command` (требование 15); профили
   компонентов записи из нескольких компонентов строит
   `project_profile.component_profiles` (узлы полного прогона,
   требование 11). Различитель — `project_profile.reported(profile)`:
   `report` есть и (`from_components` или `runner: pytest-own`)
   (требование 4). Умолчание `report_args` `[--junitxml, {path}]` —
   `project_profile.report_args_of` (требование 2). Таблица версий
   Vitest — `project_profile.VITEST_VERSION_FLAGS` (ANSWER-2, В1): запись
   для Vitest 4 `--cacheDir`/принимает `--expect.requireAssertions`,
   пометка «не подтверждено пробой этапа 2».
2. **Разбор отчётов — новый пакет `orchestrator/reporters/`** (зона
   SPEC): отчётчик пульта `pult_vitest_reporter.js` (форма JSON —
   ANSWER-2, В2) и разбор JUnit/JSON в записи `TestRecord` (`id`,
   `outcome`, `failure`, `skip_reason`, `time`, `mode`, `fails`,
   `retries`, ANSWER-2, В3), вердикт «зелёный/красный/неизвестно» и
   синтезированная сводка в форме короткого итога pytest
   (`FAILED <id> - <вид>`, `N passed, M failed … in Xs`). Сводка
   дописывается в конец вывода прогона: прежние разборщики
   (`run_summary_line`, `failed_entries`, `suite_run.parse`, итоги по
   sha) читают из неё числа и упавших — из отчёта, не из текста раннера
   (требование 18); выжимка компонента строится только по ней.
3. **Узел прогона по отчёту в `acceptance.py`** (`_report_run`): сверка
   `command`/`report_args` `pult-vitest` с базовым argv, установка
   зависимостей пультом (один раз на сумму файла блокировки рабочей
   копии, каталог пульта `.artel/projects/<проект>/deps/…` только для
   чтения, символьная ссылка в `workdir`, сверка подключения перед
   каждым прогоном, исключение ссылки через `info/exclude`), версия
   Vitest из `tools` или `--version`, флаги пульта
   (`--expect.requireAssertions`, флаг кэша в
   `.artel/projects/<проект>/cache/…`, `CI=true`), подстановки `{path}`
   (файл во временном каталоге вне рабочей копии), `{pult_reporter}`,
   `{tests}` в `select`; запуск в `workdir` с чистым окружением
   (`_own_env`), своей группой процессов и таймаутом (`_run_in_session`).
   Отказ подготовки — «прогон не начат: <причина>»; неразборчивый итог —
   исход «неизвестно»: константа `FULL_SUITE_NOT_STARTED`, деталь
   `итог неизвестен: <причина> — исход «неизвестно» (лог прогона: …)`,
   лог пишется (требование 3).
4. **Места прогона** (требование 8): `run`, `collect`, `run_repeat`,
   `run_plank`, `run_full_suite`/`full_suite`, `two_sided._run_side`
   ветвятся на `_reported(command)` до прежней ветки `pytest-own`.
   Вызывающие получают профиль одним помощником
   `acceptance.place_channel(profile)` (профиль у `pytest-own` и у
   записей с отчётом, иначе список команды): рубеж
   (`advance_gates/acceptance.py`), сухой сбор (`fsm_advance.py`,
   `advance_gates/tests_writing.py`), гейт мержа; `pull`, `amend`,
   `plank-run` получают его через `_task_own_profile`.
5. **`suite-run`** (требование 9): `_profile_command` строит профиль через
   `with_tools`; компонент с отчётом не проверяется `_is_pytest` и идёт без
   `-vv`/`-n`; `--failed` переводит id `<компонент>:<путь>::<имя>` в
   пути подмножества.
6. **Гейт мержа** (требования 10, 13): `_full_suite_command` у записи из
   нескольких компонентов отдаёт кортеж профилей затронутых компонентов
   (`select_components` по диффу ветки и путям приложений), узел
   `acceptance.components_full_suite` гоняет каждый со своим пределом;
   подсказка гейта различает «неизвестно», отказ подготовки и занятую
   машину. `checks_local` — `acceptance.run_checks_local` в
   `acceptance_suite` (после любого источника итога) и на гейте мержа
   после приложений (с прогоном и без).
7. **Ключ итога** (требование 14): у профиля с отчётом —
   `_report_suite_result_key` (дерево, `tools`, суммы файлов блокировки,
   команда, действующие `report_args`, имя компонента, `workdir`, `env`);
   прежние ветки ключа не тронуты.
8. **Сторож зависших тестов** (требование 16): процесс признаётся и по
   командам компонентов записей `targets.yaml` (подпоследовательность
   токенов `command`), помощник — в `doctor/hung_test_watchdog.py`, фасад
   не меняется.
9. **Инвариант 41** — приложение PLAN (строка `docs/invariants.md` и класс
   `tests/test_invariants.py`), применимость проверена `git apply --check`.
10. **Итерация 2 (REVIEW итерации 1, R1-F1…F6).**
    - R1-F1: `acceptance_suite` — провал `checks_local` понижает в «красный
      прогон» только зелёный итог; незелёный («неизвестно», «не начат»,
      таймаут) сохраняет исход, вывод проверки дописывается к детали —
      `--accept-red` по-прежнему отказывает «неизвестно».
    - R1-F2: `_report_argv` — цель `long_lived_dir`, `--ignore` выкладки и
      `-p no:cacheprovider` добавляются только к команде pytest
      (`acceptance.is_pytest_command`, ему же делегирует
      `suite_run._is_pytest`), у `pult-vitest` — никогда.
    - R1-F3: `_install` — `fcntl.flock` на `deps/<компонент>/<сумма>.lock`
      вокруг проверки отметки и установки, отметка перепроверяется под
      замком (`_install_mark`, `_install_locked`).
    - R1-F4: сторожа в `tests/test_component_report_gates.py`: `checks_local`
      в `acceptance_suite` на обоих путях, цепочка `--accept-red` на
      «неизвестно» (`fsm._acceptance_full_suite_ok`), выбор компонентов
      гейта мержа по диффу и путям приложений, предел каждого компонента,
      ключ `suite-run` = ключ гейта мержа с `tools`, точный argv
      `pult-vitest` с `workdir`, замок установки, `parse` с отчётом.
    - R1-F5: `suite_run.parse(..., reported=True)` у профиля с отчётом не
      читает строки хода сырого вывода — упавшие только из сводки отчёта.
    - R1-F6: вызывающий `advance_gates/test_integrity.py:1770-1793` вне зон
      задачи — вынесен Оператору предложением отдельной задачи (раздел
      «Предложения системе»), код вне зон не тронут.
11. **Итерация 3 (возврат с приёмки Оператора на `merge_gate`).** Код не
    меняется: добавлены сторожа в `tests/test_component_report_gates.py`,
    все зелёные на коде ветки.
    - `ChecksLocalFromRecordTest.test_record_checks_local_runs_in_acceptance_suite`:
      запись с одним компонентом и `checks_local` в `targets.yaml`, без
      подмены `acceptance._task_profile`; `decide(...).profile.checks_local`
      непуст, `acceptance_suite` (`actor` `operator` и `fsm`) исполняет
      проверку записи: код 0 — зелёный, код 3 — «красный прогон» с выводом.
      Мутация «`_with_component_fields` теряет `checks_local`» — красный.
    - `ChecksLocalFromRecordTest.test_merge_gate_without_appendices_runs_record_checks_local`:
      тело `_cmd_approve_merge_gate` с настоящим `_apply_plan_appendices`
      (приложений нет), шаги до плотницкого мержа — «ок», публикация —
      стоп-исключение; упавшая проверка — `("stopped",)` и `merge FAILED` с
      выводом, прошедшая — запись `checks_local компонента` в журнале и
      гейт идёт дальше. Мутация «вызов `_checks_local_refuse` убран из тела
      (перенос внутрь `_full_suite_or_refuse`)» — красный.
    - `EmptyInstallTest`: `test_profile` (`pytest-own`, `junit-xml`) с
      `install: []` без файла блокировки — зелёный, без отказа и без
      `deps/` (у компонента `install` — непустая команда, `targets.py:88`,
      поэтому запись `test_profile`). Мутация `if profile.install is None`
      (`acceptance.py:480`) — красный.

## Шаги

1. Профиль и различитель: `project_profile.py` (поля, `with_tools`,
   `component_profiles`, `reported`, `report_args_of`,
   `VITEST_VERSION_FLAGS`, предел по компоненту).
2. Пакет `orchestrator/reporters/`: отчётчик Vitest, разбор JUnit/JSON,
   вердикт, сводка.
3. `acceptance.py`: узел прогона по отчёту, установка и подключение
   зависимостей, исход «неизвестно», `FullSuiteRun.tests`, ключ,
   `checks_local`, `components_full_suite`, `place_channel`,
   `_task_own_profile`.
4. Вызывающие: `advance_gates/acceptance.py`, `tests_writing.py`,
   `fsm_advance.py`, `two_sided.py`, `suite_run.py`, `fsm_merge_gate.py`.
5. Сторож: `doctor/hung_test_watchdog.py`.
6. Юнит-тесты на свойства вне долгоживущего файла задачи; карта кода.
7. Приложение инварианта 41.
8. Итерация 2: замечания R1-F1…F5 кодом и сторожами в `tests/`, R1-F6 —
   предложением задачи Оператору (подход, п. 10).
9. Итерация 3: сторожа `checks_local` из записи (узел приёмки, гейт мержа
   без приложений) и пустого `install` (подход, п. 11).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2, 3 |
| 2 | 1 |
| 3 | 3, 4, 8 |
| 4 | 1, 8 |
| 5 | 2 |
| 6 | 2 |
| 7 | 1, 3 |
| 8 | 3, 4 |
| 9 | 4 |
| 10 | 3, 4 |
| 11 | 1, 3, 4 |
| 12 | 3 |
| 13 | 3, 4 |
| 14 | 3 |
| 15 | 4 |
| 16 | 5 |
| 17 | 3, 4 |
| 18 | 2, 3 |
| 19 | 7 |
| 20 | 6 |

## Влияние на систему

- **Артель и записи без `report` не меняются** (требование 17): различитель
  `project_profile.reported` ложен у `runner: pult-pytest` без компонента и
  у записи без `report`, их ветки (`_pytest_command`, `_own`, прежний ключ
  итога, тексты исходов, `run_digest`, `suite_run.parse`, отказ
  `_is_pytest`) не тронуты; закреплено зелёными с рождения методами AC-4 п.3,
  AC-6 п.1-2, AC-12 п.2, AC-20 долгоживущего файла.
- **Поведение меняется** у записей с отчётом: `test_profile` с `runner:
  pytest-own` и `report` (sled backend) и единственный компонент записи
  `components:` с `report` — их итог теперь только из отчёта (требования 4,
  18). Существующий тест `tests/test_01m58fnwbv25ff26e7az9q9912_components.py`
  сравнивает профиль `decide` с профилем `test_profile` и вручную собранным —
  новые поля `Profile` вне сравнения (`compare=False`), утверждения не
  тронуты.
- **Исход «неизвестно» = `FULL_SUITE_NOT_STARTED`**: `approve --accept-red`
  отказывает ему существующей веткой `fsm.py:1304-1313` (без правки
  `fsm.py`); итог «неизвестно» по sha не сохраняется и в кэш итогов не
  попадает.
- **Отказ `MULTI_COMPONENT_PENDING` на входах остаётся** (вход гейта мержа,
  `_task_own_profile`, `suite-run`, строка `doctor`); прогон по компонентам —
  только в узлах `components_full_suite` / `_full_suite_or_refuse`.
- **Новые побочные эффекты пульта**: каталоги `.artel/projects/<проект>/deps/`
  (установки, только чтение) и `.artel/projects/<проект>/cache/` (кэш
  Vitest), ссылка `node_modules` в `workdir` рабочей копии с исключением
  `/<путь>` в `info/exclude` клона (как выкладка планки) — чекпоинт её не
  коммитит.
- **Гейты, лимиты, инварианты не ослаблены**: добавлен инвариант 41
  (приложение ниже); `checks_local` и отказы подготовки только добавляют
  красноту.
- **Откат**: revert merge-коммита задачи; приложение инварианта — отдельным
  revert коммита приложений Оператора. Каталоги `deps/`/`cache/` пульта
  после отката безвредны (`chmod -R u+w` и удаление).

## Риски

- Отчётчик `pult_vitest_reporter.js` и запись Vitest 4 в
  `VITEST_VERSION_FLAGS` (`--cacheDir`) не проверены настоящим Node — по
  SPEC это проба этапа 2; до неё `pult-vitest` идёт только на подменённом
  раннере.
- Двусторонний прогон: вызывающий `advance_gates/test_integrity.py` (вне
  зон) передаёт профиль в `two_sided.run` только при `runner: pytest-own`;
  единственный компонент без `runner` через гейт идёт раннером пульта.
  Сама `two_sided.run` с профилем компонента судит по отчёту (AC-11).
  Правка вызывающего — отдельной задачей (зона `test_integrity.py`);
  вынесено Оператору готовым предложением в «Предложениях системе».
- `collect()` профиля с отчётом не может «собрать без прогона» у
  произвольной команды — подмножество прогоняется, «собралось» = отчёт
  прочитан и назвал ≥1 тест.
- Установка копирует файлы верхнего уровня `workdir` в каталог пульта и
  подключает созданные ею каталоги (у npm — `node_modules`); проекту,
  чья установка требует исходников глубже, понадобится уточнение правила.

## Предложения системе

- **Задача-продолжение (R1-F6), адрес `orchestrator/advance_gates/test_integrity.py:1770-1793`:**
  двусторонний прогон гейта `in_dev -> verifying` передаёт профиль в
  `two_sided.run` только при `runner: pytest-own` (`_own_profile`); у
  единственного компонента с `report` без `workdir`/`runner` он идёт
  раннером пульта, а не по отчёту. Правка — передавать
  `acceptance.place_channel(decision.profile)` (профиль и у
  `project_profile.reported`); `test_integrity.py` вне зон этой задачи
  (SPEC «Не входит»), поэтому не тронут. Узел `two_sided.run` с профилем
  компонента уже судит по отчёту (AC-11).
- Класс «вызывающий вне зон не передаёт новый канал»: аналитику стоит
  включать в зоны всех вызывающих узла, переводимого на новый канал.
- `tests/test_invariants.py` не импортирует `io`; метод, проверенный
  исполнением вне файла, легко получить с `NameError` — проверка метода
  приложения стоит прогоном на дереве с применённым диффом (как AC-21), а
  не исполнением куска.

## Приложение 1: инвариант 41 — строка docs/invariants.md

Применимость проверена `git apply --check` на чистом дереве HEAD рабочей
копии задачи — проходит.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -70,2 +70,3 @@
 | 40 | Git главной копии пульта не меняется в ходе задачи: от `new` до `done` (автокоммит шага, подтяжка `main`, мерж) ветки `refs/heads/*`, ссылки `refs/artifacts/*`, HEAD и `git worktree list` главной копии остаются прежними — ветка задачи, её рабочая копия, ссылка документов, временная рабочая копия мержа, коммит мержа и push живут в клоне проекта `.artel/projects/<имя>/repo`; git главной копии меняют только `pin-update`/`pin --to` и ремонт хуков самого пульта (`doctor --fix`) | `test_invariants.MainCopyGitUnchangedDuringTaskTest` | ADR-0021 пп. 1, 2, 12; refs/artifacts/01M42PENCS26D0656X8FR7DFA7:tasks/01M42PENCS26D0656X8FR7DFA7/SPEC.md, требования 2, 9 |
+| 41 | Неизвестный или неразобранный местный итог тестов не зелёный; повторы внутри прогона компонентов с отчётом пульта запрещены: у компонента с отчётом (`project_profile.reported` — компонент записи `components:` с `report` либо `test_profile` с `runner: pytest-own` и `report`) итог читается только из отчёта, а не из кода возврата и текста раннера; отчёта нет, он не разобран или пуст при ненулевом коде возврата — исход «неизвестно» (значение `acceptance.FULL_SUITE_NOT_STARTED`, деталь «итог неизвестен: …»), не зелёный ни в одном месте прогона (прогон планки, сухой сбор, повтор красных, `plank-run`, полный набор, `suite-run`, двусторонний прогон), и `approve --accept-red` его не принимает; тест, прошедший с числом повторов больше 0, красит прогон с причиной «повтор» | `test_invariants.ReportedOutcomeNotGreenInvariantTest`; `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py` | refs/artifacts/01M590GJAF0EDV4NBC4C99MFVH:tasks/01M590GJAF0EDV4NBC4C99MFVH/SPEC.md, требования 3, 6, 19; ADR-0026 п. 4 |
 
```

## Приложение 2: инвариант 41 — проверка tests/test_invariants.py

Применимость проверена `git apply --check` на чистом дереве HEAD — проходит;
метод исполнен зелёным, мутации «"неизвестно" — зелёный»
(`reporters.outcome.verdict` отдаёт `GREEN` без отчёта) и «повтор > 0 —
зелёный» (проверка `retries` снята) — красный.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -3215,3 +3215,68 @@
         for name, snapshot in observed:
             self.assertEqual(snapshot, before,
                              flow.msg(f"git главной копии изменился {name}"))
+
+
+class ReportedOutcomeNotGreenInvariantTest(unittest.TestCase):
+    """Инвариант 41: неизвестный или неразобранный местный итог тестов не
+    зелёный; повторы внутри прогона компонентов с отчётом пульта запрещены
+    (refs/artifacts/01M590GJAF0EDV4NBC4C99MFVH:tasks/01M590GJAF0EDV4NBC4C99MFVH/SPEC.md,
+    требования 3, 6, 19).
+
+    Учебные записи проектов песочницы долгоживущего файла задачи
+    (`ReportSandbox`: настоящий git, подменённый раннер компонента вне
+    дерева, поддельная установка зависимостей): компонент `junit-xml`,
+    раннер которого выходит с кодом 0 и печатает «1 passed», но отчёта не
+    пишет, и компонент `pult-vitest`, отчётчик которого называет тест
+    зелёным с числом повторов больше 0. Узел полного прогона
+    `acceptance.full_suite` и прогон планки `acceptance.run` судятся по
+    отчёту; контроль — тот же компонент с зелёным отчётом без повторов
+    зелёный (учебная запись исправна, краснота — от свойства).
+    """
+
+    def test_unknown_or_retried_component_outcome_is_never_green(self):
+        """Ловит мутацию: исход «неизвестно» (отчёта нет при коде 0)
+        считается зелёным — `full_suite`/`run` компонента `junit-xml`
+        отдают зелёный итог; либо тест с повтором больше 0 считается
+        зелёным — `full_suite` компонента `pult-vitest` зелёный при
+        `retry_count > 0`.
+        """
+        import io
+        from orchestrator import acceptance
+        from tests.test_01m590gjaf0edv4nbc4c99mfvh_report_outcome import (
+            ReportSandbox, junit, vitest_report, vitest_test)
+
+        class Flow(ReportSandbox):
+            def runTest(self):
+                pass
+
+        flow = Flow()
+        flow.setUp()
+        self.addCleanup(flow.doCleanups)
+
+        case = flow.junit_component()
+        case["fake"].scenario(stdout="1 passed in 0.01s\n", report=None)
+        run, out = flow.full(case["clone"], case["task"], case["profile"])
+        self.assertFalse(run.green, flow.note(f"«неизвестно» зелёное: {run}\n{out}"))
+        self.assertEqual(run.outcome, acceptance.FULL_SUITE_NOT_STARTED,
+                         flow.note(str(run)))
+        self.assertTrue(run.detail.startswith(acceptance.UNKNOWN_PREFIX),
+                        flow.note(run.detail))
+        with contextlib.redirect_stdout(io.StringIO()):
+            green, tail = acceptance.run(flow.plank_dir(), cwd=case["clone"],
+                                         command=case["profile"])
+        self.assertFalse(green, flow.note(f"планка «неизвестно» зелёная: {tail}"))
+        case["fake"].scenario(stdout="1 passed in 0.01s\n", report=junit(
+            [("src/x.test.jsx", "test_ok", "passed", "", "", "0.1")]))
+        run, out = flow.full(case["clone"], case["task"], case["profile"])
+        self.assertTrue(run.green, flow.note(f"контроль junit-xml: {run}\n{out}"))
+
+        vitest = flow.vitest_component()
+        version = f"vitest/{vitest['version']} linux-x64 node-v22.11.0"
+        for retries, expected in ((flow.rng.randint(1, 4), False), (0, True)):
+            vitest["fake"].scenario(version_out=version, report=vitest_report(
+                [vitest_test("src/a.test.js", "ok", retry_count=retries)]))
+            run, out = flow.full(vitest["clone"], vitest["task"],
+                                 vitest["profile"])
+            self.assertEqual(run.green, expected, flow.note(
+                f"повторов {retries}: {run}\n{out}"))
```
