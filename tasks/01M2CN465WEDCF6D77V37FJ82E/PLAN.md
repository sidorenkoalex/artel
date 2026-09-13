---
task: 01M2CN465WEDCF6D77V37FJ82E
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Фикс утечки тестов в настоящий пульт: WORKTREES в песочнице test_git_fixation

## Подход

Точечный фикс класса ошибки «песочница задаёт собственный `PATCHED_ATTRS`
уже, чем полный набор `tests/sandbox.py::ALL_CONFIG_ATTRS`, и забывает
`WORKTREES`/`BACKUP_MARKER`»:

1. `_GitFixationTmpRootTest.PATCHED_ATTRS` (tests/test_git_fixation.py:159)
   восстановлен до включения `WORKTREES` и `BACKUP_MARKER` — ровно то
   подмножество, которого не хватало (SPEC, «Контекст»: регрессия
   коммита d692f2a6, сузившая явный список).
2. Сверены ВСЕ прочие классы `tests/*.py`, задающие собственный
   `PATCHED_ATTRS` (grep `PATCHED_ATTRS` по `tests/`): 8 классов, кроме
   `_GitFixationTmpRootTest`. Для каждого проверено, реально ли его
   `setUp`/тела тестов дотягиваются до записи по `config.WORKTREES`
   (через `workspace.ensure`/настоящий `git worktree add`) или
   `config.BACKUP_MARKER` (единственный писатель этого пути в
   orchestrator-коде — никто; `doctor/misc_checks.py::check_backup_age`
   только читает `.exists()`/`.stat()`). Результат — таблица ниже
   («Покрытие требований»): 6 классов уже несли `WORKTREES` в своём
   `PATCHED_ATTRS` (были пофикшены раньше этой задачи, здесь только
   подтверждены), 2 класса (`test_doctor.py:2413`,
   `test_multitarget.py:104`) сознательно уже, но без реального пути к
   записи (read-only сценарий и мок самого `workspace.ensure`
   соответственно) — не утечка, правки не требуют. Ни BACKUP_MARKER не
   требуется ни одному классу, кроме AC-1: путь никогда не пишется
   продовым кодом, поэтому непатченность не создаёт риска записи для
   общего случая — только `_GitFixationTmpRootTest` восстанавливает его
   как часть точного отката регрессии d692f2a6.
3. Локальная проверка AC-3 (полный прогон всего `tests/`) НЕ ставится
   отдельным шагом этого PLAN: skills/coding-standards.md запрещает
   разработчику гонять полный набор `tests/` в шаге («уводится в фон,
   его и так гоняет CI на каждый пуш ветки») — вместо этого прогнаны
   `tests/test_git_fixation.py` (41/41, до/после фикса — каталогов в
   `.artel/worktrees` этого worktree не появилось, `git status
   --porcelain` не изменился) и смежные модули с уже патченным
   `WORKTREES` (`tests/test_sandbox.py`, `tests/test_multitarget.py`,
   `tests/test_catalog_new_race.py` — 65 тестов, 14 subtests, зелено).
   Полный прогон `tests/` остаётся за CI job `python` того же пуша
   (существующий сторож ссылок репозитория, инвариант 33) — AC-3
   проверяется им же.
4. Новый инвариант «после прогона тестов — рабочее дерево чисто»
   (AC-4) — НЕ отдельная интеграционная проверка, перезапускающая весь
   `pytest` изнутри юнит-теста (дорого и рекурсивно), а структурный скан
   AST по образцу уже существующих инвариантов этого файла
   (`StdlibOnlyImportsInvariantTest`, `CiJobsByPushClassInvariantTest`):
   каждый класс `tests/*.py` с собственным `PATCHED_ATTRS` обязан нести
   `WORKTREES`, кроме явного `ALLOWLIST` с обоснованием (те самые 2
   класса из п.2). Диф приложен ниже, `git apply --check` на чистом
   `main` пройден (см. «Влияние на систему»); сам файл в код ветки не
   входит (AC-4) — коммитит Оператор.

## Шаги

1. `tests/test_git_fixation.py:159` — `_GitFixationTmpRootTest.PATCHED_ATTRS`
   расширен до `("ROOT", "DB", "TASKS", "LOGS", "PROJECTS", "ROLE_HOME",
   "ROLE_CONFIG_DIR", "TARGETS", "WORKTREES", "BACKUP_MARKER")`.
2. Ревизия прочих классов с собственным `PATCHED_ATTRS` — без правок кода
   (см. «Подход» п.2, «Покрытие требований»).
3. Unified diff `tests/test_invariants.py` (новый класс
   `SandboxPatchedAttrsCoverWorktreesInvariantTest`) и `docs/invariants.md`
   (строка реестра #37) — приложены ниже, применяются `git apply` на
   чистом `main` Оператором отдельно от кода этой ветки (AC-4).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (`_GitFixationTmpRootTest.PATCHED_ATTRS` несёт WORKTREES/BACKUP_MARKER) | 1 |
| 2 (прочие классы с собственным PATCHED_ATTRS сверены) | 2 |
| 3 (полный прогон `tests/` не создаёт каталоги в `.artel/worktrees`, `git status --porcelain` пуст) | 1 (фикс) + CI job `python` (замер) |
| 4 (новый инвариант — приложением диффа к PLAN.md, `tests/test_invariants.py` в коде ветки не редактируется) | 3 |
| 5 (ассерты существующих тестов не меняются) | 1, 2 (диф не трогает ни один существующий `assert*`) |

Таблица ревизии прочих классов с собственным `PATCHED_ATTRS` (требование 2):

| Класс | Файл | WORKTREES в PATCHED_ATTRS | Реально пишет по WORKTREES? | Вывод |
|---|---|---|---|---|
| `_GitFixationTmpRootTest` | tests/test_git_fixation.py:159 | было нет → добавлен (шаг 1) | да (настоящий `git worktree add`, `network_guarded_real_run`) | утечка, исправлена |
| `_RoleHomeReferenceTmpRootTest` | tests/test_doctor.py:2413 | нет | нет — только `doctor.check_role_home_reference()`, read-only; `ROOT` намеренно настоящий (читает `docs/reference/role-home`) | не утечка |
| `_MultitargetTmpRootTest` | tests/test_multitarget.py:104 | нет | нет — `runner.workspace.ensure` подменён моком целиком (SPEC, «Не входит», явный пример) | не утечка |
| `_AcceptanceFlowTmpRootTest` | tests/test_acceptance_tests_flow.py:203 | да | — | ок |
| `_MultitargetInvariantsTmpRootTest` | tests/test_multitarget_invariants.py:75 | да | — | ок |
| `_AgentLogTmpRootTest` | tests/test_agent_log.py:81 | да | — | ок |
| `_AnalystRoleTmpRootTest` | tests/test_analyst_role.py:133 | да | — | ок |
| `_StepCostTmpRootTest` | tests/test_step_cost.py:70 | да | — | ок |
| `PeekTaskNumberRaceTest` | tests/test_catalog_new_race.py:34 | да | — | ок |
| `_AgentFailureTmpRootTest` | tests/test_agent_failure.py:44 | да | — | ок |

## Влияние на систему

Изменение — расширение `PATCHED_ATTRS` одного тестового класса плюс
приложенный (не применённый в этой ветке) диф двух защищённых файлов
реестра инвариантов. Продовый код (`orchestrator/workspace.py`,
`orchestrator/config.py`) не тронут — по требованию SPEC («Не входит»).

Инварианты и защиты:
- Ни один существующий `assert*`/тестовый метод не изменён (требование
  5) — расширение кортежа `PATCHED_ATTRS` не меняет поведение уже
  проходящих сценариев файла (41/41 тестов `test_git_fixation.py`
  зелёные и до, и после правки; конкретные тесты, которым нужен именно
  реальный `config.WORKTREES` пульта, в файле отсутствуют — иначе
  правка их сломала бы).
- `_GitFixationTmpRootTest` по-прежнему делает настоящий `git worktree
  add`/`remove` — только уже во временном каталоге песочницы
  (`self.root/.artel/worktrees`), не в `.artel/worktrees` настоящего
  корня пульта.
- Приложенный диф `tests/test_invariants.py`/`docs/invariants.md`
  (защищённые пути, `config.PROTECTED_PATHS`) НЕ входит в код этой
  ветки — не пытается обойти гейт защищённых путей, отдан Оператору как
  приложение, `git apply --check tests_invariants.diff` /
  `git apply --check invariants_md.diff` пройдены на чистом `main`
  (sha `01b6a33c6078e8dd071828c1e7e2e41d7f871e0d`) перед сдачей — оба
  диффа приведены целиком ниже.
- Откат: `git revert` коммита этой ветки — тривиален, диапазон правки
  (`tests/test_git_fixation.py`, одна строка кортежа) не пересекается ни
  с чем ещё.

## Риски

- Диф `tests/test_invariants.py`/`docs/invariants.md` не в коде этой
  ветки: если Оператор применит его позже другим коммитом на `main`, а
  между тем кто-то заведёт новый класс `tests/*.py` с собственным
  `PATCHED_ATTRS` без `WORKTREES`, новый инвариант поймает это на
  следующем прогоне `tests/test_invariants.py` — ожидаемое поведение
  защиты, не риск.

## Предложения системе

- Класс «песочница задаёт узкое подмножество `PATCHED_ATTRS` вручную,
  без опоры на новый вспомогательный конструктор» повторился минимум
  дважды (эта задача, R8 в роадмапе — перенос общих песочниц в единый
  модуль, «Не входит»): стоит рассмотреть хелпер вида
  `TmpRootTest.with_real_git()`/`.without_worktrees()`, который
  расширяет `ALL_CONFIG_ATTRS` минус явно перечисленное исключение,
  вместо перечисления вручную с нуля в каждом файле — тогда регрессия
  класса d692f2a6 (сужение списка вместо явного вычитания) структурно
  невозможна.

---

## Приложение: unified diff `tests/test_invariants.py` (AC-4)

Применять на чистом `main` (проверено `git apply --check` на sha
`01b6a33c6078e8dd071828c1e7e2e41d7f871e0d`):

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 3e7cce92..5a59ed79 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -2113,3 +2113,125 @@ class CiJobsByPushClassInvariantTest(unittest.TestCase):
         self.assertNotEqual(text, planted)
         self.assertTrue(any("исключает 'artifact/'" in v for v in self.violations(planted)),
                         self.violations(planted))
+
+
+class SandboxPatchedAttrsCoverWorktreesInvariantTest(unittest.TestCase):
+    """Инвариант 37 (docs/invariants.md; SPEC 01M2CN465WEDCF6D77V37FJ82E):
+    класс `tests/*.py` с СОБСТВЕННЫМ `PATCHED_ATTRS` для
+    `tests.sandbox.TmpRootTest` патчит `config.WORKTREES`, либо явно
+    значится в `ALLOWLIST` ниже с обоснованием, почему запись по этому
+    пути для него недостижима (read-only сценарий или подмена самого
+    `workspace.ensure`, не пути).
+
+    Находка (docs/audits/code-revision-2026-09-13.md, повтор
+    CR-2026-09-12-1): `_GitFixationTmpRootTest`
+    (`tests/test_git_fixation.py`) задавал собственный `PATCHED_ATTRS`
+    без `WORKTREES` — файл делает настоящий `git worktree add`
+    (`network_guarded_real_run` вместо `SpyRun`), а `workspace.path`
+    (`orchestrator/workspace.py`) строит путь от `config.WORKTREES`,
+    вычисленного один раз при импорте: подмена `config.ROOT` в тесте его
+    не двигает. 54 осиротевших каталога `.artel/worktrees` за один
+    прогон `tests/` до фикса.
+
+    `config.BACKUP_MARKER` не входит в автоматический скан ниже: ни один
+    путь orchestrator-кода его не пишет (только читает —
+    `doctor/misc_checks.py::check_backup_age`), поэтому непропатченный
+    `BACKUP_MARKER` в ОБЩЕМ случае не создаёт риска записи. Для
+    `_GitFixationTmpRootTest` конкретно (AC-1 задачи
+    01M2CN465WEDCF6D77V37FJ82E) он всё равно возвращён в
+    `PATCHED_ATTRS` — восстановление полного набора, из которого класс
+    был сужен регрессией d692f2a6, не вывод из анализа записи; отдельный
+    тест ниже проверяет именно эту пару для этого класса.
+    """
+
+    # Каждая запись — обоснование, почему конкретный класс безопасен без
+    # WORKTREES в PATCHED_ATTRS.
+    ALLOWLIST = {
+        ("tests/test_doctor.py", "_RoleHomeReferenceTmpRootTest"):
+            "только doctor.check_role_home_reference() — read-only; "
+            "ROOT намеренно настоящий (читает docs/reference/role-home)",
+        ("tests/test_multitarget.py", "_MultitargetTmpRootTest"):
+            "runner.workspace.ensure подменён моком целиком, не путём — "
+            "механика worktree в сценариях класса не участвует",
+    }
+
+    REQUIRED = "WORKTREES"
+
+    @classmethod
+    def _classes_missing_required(cls, rel_path: str, source: str) -> list:
+        tree = ast.parse(source, filename=rel_path)
+        missing = []
+        for node in ast.walk(tree):
+            if not isinstance(node, ast.ClassDef):
+                continue
+            for stmt in node.body:
+                if not (isinstance(stmt, ast.Assign)
+                        and len(stmt.targets) == 1
+                        and isinstance(stmt.targets[0], ast.Name)
+                        and stmt.targets[0].id == "PATCHED_ATTRS"):
+                    continue
+                if not isinstance(stmt.value, (ast.Tuple, ast.List)):
+                    continue
+                values = {elt.value for elt in stmt.value.elts
+                         if isinstance(elt, ast.Constant)
+                         and isinstance(elt.value, str)}
+                if cls.REQUIRED not in values:
+                    missing.append((rel_path, node.name))
+        return missing
+
+    def test_repo_tree_sandboxes_patch_worktrees_or_are_allowlisted(self):
+        """Ловит мутацию: новый/изменённый класс `tests/*.py` заводит
+        собственный `PATCHED_ATTRS` без `WORKTREES` и без записи в
+        `ALLOWLIST` — `assertEqual([], ...)` откажет списком таких
+        классов (тот самый класс дефекта, что увёл
+        `_GitFixationTmpRootTest` на 54 осиротевших каталога за прогон,
+        SPEC 01M2CN465WEDCF6D77V37FJ82E)."""
+        violations = []
+        for path in sorted((REPO_ROOT / "tests").glob("*.py")):
+            rel = str(path.relative_to(REPO_ROOT))
+            for item in self._classes_missing_required(
+                    rel, path.read_text(encoding="utf-8")):
+                if item not in self.ALLOWLIST:
+                    violations.append(item)
+        self.assertEqual(
+            [], violations,
+            f"классы с PATCHED_ATTRS без WORKTREES и без записи в "
+            f"ALLOWLIST: {violations}")
+
+    def test_git_fixation_sandbox_also_patches_backup_marker(self):
+        """AC-1: `_GitFixationTmpRootTest` — специально восстановленный
+        полный список (`WORKTREES` И `BACKUP_MARKER`), не только
+        `WORKTREES`, как остальные классы этого скана. Ловит мутацию:
+        правку, возвращающую сужение `PATCHED_ATTRS` этого класса без
+        `BACKUP_MARKER`."""
+        path = REPO_ROOT / "tests" / "test_git_fixation.py"
+        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
+        found = None
+        for node in ast.walk(tree):
+            if (isinstance(node, ast.ClassDef)
+                    and node.name == "_GitFixationTmpRootTest"):
+                for stmt in node.body:
+                    if (isinstance(stmt, ast.Assign)
+                            and len(stmt.targets) == 1
+                            and isinstance(stmt.targets[0], ast.Name)
+                            and stmt.targets[0].id == "PATCHED_ATTRS"):
+                        found = {elt.value for elt in stmt.value.elts
+                                if isinstance(elt, ast.Constant)}
+        self.assertIsNotNone(
+            found, "_GitFixationTmpRootTest.PATCHED_ATTRS не найден")
+        self.assertIn("WORKTREES", found)
+        self.assertIn("BACKUP_MARKER", found)
+
+    def test_planted_missing_worktrees_is_caught_on_synthetic_source(self):
+        """Ловит мутацию: сканер перестаёт замечать урезанный
+        `PATCHED_ATTRS` — синтетический дефектный класс обязан попасть в
+        список нарушителей, класс с `WORKTREES` — нет."""
+        dirty = ("class _Dirty(TmpRootTest):\n"
+                "    PATCHED_ATTRS = ('ROOT', 'DB', 'TASKS')\n")
+        clean = ("class _Clean(TmpRootTest):\n"
+                "    PATCHED_ATTRS = ('ROOT', 'DB', 'WORKTREES')\n")
+        self.assertEqual(
+            [("tests/synthetic.py", "_Dirty")],
+            self._classes_missing_required("tests/synthetic.py", dirty))
+        self.assertEqual(
+            [], self._classes_missing_required("tests/synthetic.py", clean))
```

## Приложение: unified diff `docs/invariants.md` (AC-4)

Применять на чистом `main` (проверено `git apply --check` на sha
`01b6a33c6078e8dd071828c1e7e2e41d7f871e0d`):

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index 5f853961..8372b232 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -65,6 +65,7 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 35 | Тесты не читают сеть по DNS-имени: ни один файл `tests/**/*.py` не несёт адреса вида `http(s)://<DNS-имя>`, кроме `localhost`/`127.0.0.1` (допустимые исключения — именованная константа с обоснованием на каждую строку); сетевые git-команды (`fetch`/`push`/`ls-remote`/`clone`) с таким адресом перехватываются `tests/sandbox.py::TmpRootTest` мгновенным именованным отказом («сеть в тестах запрещена: `<команда>` `<адрес>`»), без обращения к сети | `test_invariants.NoNetworkAddressesInTestsTest`; `tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests/test_ac1_network_command_interception.py`, `test_ac2_local_bare_repo_not_blocked.py`, `test_ac9_network_interception_speed.py` | tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md, требования 1, 3 (инцидент 05.09: `git fetch -q https://example.invalid/sled main` висел минуты на DNS-резолвере при обрыве сети — фикстурный адрес `sled`-target'а в `tests/test_git_fixation.py`) |
 | 36 | Прогон CI существует для каждого пуша в `main`, `task/**`, `artifact/**`: секция `on.push` в `.github/workflows/ci.yml` не несёт фильтров `paths`/`paths-ignore`; лишние на данном классе пуша проверки снимаются условием на job (статус `skipped`, зелёный для `ci.GREEN`), причём job `python` не исключает `refs/heads/task/` и не строится как `== 'true'` по output соседнего job (fail-open), а job `guard` не исключает `refs/heads/artifact/` | `test_invariants.CiJobsByPushClassInvariantTest` | ADR-0016; `ci.verifying_status`/`ci.branch_status` читают пуш без прогона как «проверок нет вовсе» и держат задачу до потолка ожидания (инвариант 19) |
 | 36 | Порядок состояний FSM — `in_dev → verifying → review → acceptance → merge_gate`: CI подтянутой головы кодовой ветки проверяется ДО ревьювера, не после. Восемь рубежей перехода `in_dev → review` (подтяжка main, прогон приёмочной планки, гейт зон, гейт заявки мутации — новые и изменённые тесты `tests/` без строки «Ловит мутацию:» в докстринге, 01M29A0F88P9GKSXFW90F99H2N, гейт ёмкости, лок планки, гейт «замечания ревью не отработаны», сверка головы на origin) стоят на `in_dev → verifying` целиком, без повтора на `verifying → review`; в `review` из `verifying` ведёт только зелёный CI головы. Возврат `changes_requested` — в `in_dev`, повторный вход в `review` — снова через `verifying` | `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac01_ac09_state_order.py`; `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac02_ac08_gates_moved_to_verifying.py`; `test_auto_cycle.py::FSM_STATES` | ADR-0015 (docs/adr/0015-ci-before-review.md); tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md, требования 1-3 |
+| 37 | Класс `tests/*.py` с собственным `PATCHED_ATTRS` для `tests.sandbox.TmpRootTest` патчит `config.WORKTREES`, либо явно значится в `ALLOWLIST` скана с обоснованием, почему запись по этому пути для него недостижима (read-only сценарий или подмена самого `workspace.ensure`, не пути) — непропатченный `WORKTREES` не двигается вместе с `config.ROOT` (вычислен один раз при импорте) и уводит настоящий `git worktree add` в `.artel/worktrees` реального корня пульта, а не песочницы теста | `test_invariants.SandboxPatchedAttrsCoverWorktreesInvariantTest` | tasks/01M2CN465WEDCF6D77V37FJ82E/SPEC.md; docs/audits/code-revision-2026-09-12.md (CR-2026-09-12-1 ★), docs/audits/code-revision-2026-09-13.md (повтор) |
 
 ## На ревью — тестом не выражаются
 
```
