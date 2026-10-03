---
task: 01M41VTQJ9DSX64NFMFAF9W53B
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Отмена CI на документах и режима `guard --artifact-branch`

## Подход
Снимаем хвосты ветки `artifact/**` (ADR-0021 пп. 4, 12, 13) одним мержем:
код в ветке задачи (`scripts/guard.py`, `scripts/ci_push_class.py`, их
тесты, карта), защищённые пути — тремя приложениями ниже (применяет пульт
на мерже того же этапа, ADR-0021 п.12).

- `scripts/guard.py`: удалены ключ `--artifact-branch`
  (`ARTIFACT_BRANCH_FLAG`), `_artifact_branch_report`, `is_draft_lenient`,
  `basic_frontmatter_errors`, `DRAFT_LENIENT_TYPES`, `BASIC_META_FIELDS`
  (вне режима нигде не использовались — `git grep` по
  `orchestrator/`/`scripts/`/`tests/` пуст) и параметр
  `check_content(..., artifact_branch_mode)`. `check_content(label, text)`
  — прежний путь `artifact_branch_mode=False`, т.е. `_content_errors`.
  Модульный докстринг (он же справка `main()` при пустом argv) и
  комментарии в `main()`/`_content_errors` больше режим не описывают.
  `guard.py <файлы>` и `guard.py --all` не меняются: ветка `main()` без
  режима осталась дословной. Ключ `--artifact-branch` теперь — просто
  незнакомый аргумент: он трактуется как путь, `файл не найден`, код 1.
- `scripts/ci_push_class.py`: правило `branch.startswith("artifact/")`
  удалено, `artifact/<x>` попадает в общее правило не-`main` ветки
  («ветка … — тесты идут», `code=true`, git/gh не трогаются).
- `ci.yml` (приложение 1): `artifact/**` убран из `on.push.branches`,
  развилка `GUARD_ARGS`/`--artifact-branch` задания `guard` убрана (на
  `main` — прежний `guard.py --all`), условие `canary-guid-leak` больше не
  ссылается на `refs/heads/artifact/`; комментарий задания `guard` про
  `task/**` переписан: источник документов — ссылка
  `refs/artifacts/<id>`, проверка — гейты пульта.
- `docs/invariants.md` + `tests/test_invariants.py` (приложение 2):
  первый инвариант 36 — CI на `main` и `task/**`, задания `python` и
  `python-min`, пуш документов CI не получает, документы проверяют гейты
  переходов и гейт мержа; бывший второй 36 («Порядок состояний FSM»)
  получает следующий свободный номер 39 и переезжает в конец таблицы.
  `CiJobsByPushClassInvariantTest`: все прежние методы и проверки
  сохранены; свойство 3 расширено с job `guard` на любой job (условие со
  ссылкой на `refs/heads/artifact/`) плюс запрет вызова
  `--artifact-branch` в `guard`; новое свойство 4 — `on.push.branches`
  несёт `main` и `task/**` и не несёт `artifact/**`. Четыре новых
  метода `test_planted_*` — мутации на каждое новое свойство.
- Ссылки на бывший второй инвариант 36 (приложение 3, `docs/adr/` —
  защищённый путь): ADR-0003:415, ADR-0007:53, ADR-0015:58 → 39;
  ADR-0016:106 — пометка «до этапа 1 ADR-0021 — первый под этим
  номером». `docs/research/2026-09-22-chatgpt-agent-integration.md`
  (строки 1582, 1627) и `docs/backlog.md` не правлю: research —
  исторический документ вне зон и вне защищённых путей (приложением
  нельзя, `appendix_unprotected_path_error`), бэклог — только чтение по
  SPEC «Не входит».

Бюджет SPEC ($25) не пересматриваю.

## Шаги
1. Код: `scripts/guard.py`, `scripts/ci_push_class.py`; тесты
   `tests/test_ci_push_class.py`, `tests/test_guard_artifact_branch_mode.py`,
   докстринг `tests/test_guard_extraneous_acceptance_files.py`; карта
   `docs/codebase-map.md` регенерирована (`python3 scripts/codebase_map.py`).
2. Приложения 1–3 к защищённым путям (ниже), сняты `git diff` с временной
   правки рабочего дерева, правка откачена `git checkout --`.
3. Проверки (все — в переднем плане):
   - `git apply --check -v` всех трёх приложений подряд на чистом дереве
     ветки задачи (база `d860c974`, совпадает с `main`; `origin/main`
     411d8e37 эти файлы не меняет — `git diff --stat main origin/main`
     по ним пуст) — **проходит**: «Checking patch .github/workflows/ci.yml…
     docs/invariants.md… tests/test_invariants.py… docs/adr/0003…
     0007… 0015… 0016…», код 0.
   - С наложенными приложениями: `python3 -m pytest tests/test_invariants.py
     tests/test_ci_push_class.py tests/test_guard_artifact_branch_mode.py
     tests/test_guard_extraneous_acceptance_files.py
     tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py
     -p no:cacheprovider -p timeout -o timeout=120` — 100 passed,
     222 subtests passed.
   - `CiJobsByPushClassInvariantTest.violations` на `ci.yml` ДО
     приложения — три нарушения (триггер `artifact/**`, условие
     `canary-guid-leak`, `--artifact-branch` в `guard`), после — `[]`.
   - После отката приложений: `tests/test_guard_schema.py
     tests/test_guard_zones.py tests/test_advance_guard.py
     tests/test_plan_appendix.py tests/test_guard_split_signals.py
     tests/test_codebase_map.py` — 165 passed.
   - Мутация сторожа: возврат правила `artifact/` → `return False` в
     `classify` — `test_artifact_branch_is_code_true_without_touching_git_or_gh`
     красный; код возвращён.
   - Разовая планка `test_ac3_ac4_plan_attachments.py` читает PLAN.md из
     ссылки документов, куда он попадёт только автокоммитом шага;
     `plank-run` без файла отказывает сторожем полного набора. Прогнал её
     модуль из каталога документов с единственной подменой `_plan_text`
     на чтение этого PLAN.md с диска — 7 из 7 зелёные (в т.ч.
     `test_ac4_ci_jobs_invariant_test_green_on_patched_ci_yml`).
   - `guard.plan_appendices(PLAN.md)` — три приложения, ошибок нет;
     `git apply --check` каждого разобранного приложения — код 0;
     `python3 scripts/guard.py <PLAN.md>` — «GUARD: ок».

4. После ANSWER-1 (код не менялся): `python3 -m pytest
   tests/test_ci_push_class.py tests/test_guard_artifact_branch_mode.py
   tests/test_guard_extraneous_acceptance_files.py
   tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py
   tests/test_guard_schema.py -p no:cacheprovider -p timeout -o
   timeout=120` — 86 passed, 22 subtests passed; `guard.py PLAN.md` —
   «GUARD: ок». `plank-run 01M41VTQJ9DSX64NFMFAF9W53B` — и без файла, и
   с файлом `test_ac3_ac4_plan_attachments.py` (именем и путём
   `tasks/<id>/acceptance_tests/…`) — отказ сторожем полного набора, код
   2 (см. «Предложения системе»).

5. Отказ advance после ANSWER-1 (гейт неослабления тестов, 12 методов
   `IsDraftLenientTest::*` и `BasicFrontmatterErrorsTest::*`): мандат
   ANSWER-1 называет эти два класса элементом `путь::Класс`, а гейт
   засчитывает только точное совпадение — путь файла или
   `путь::Класс::метод` (`orchestrator/advance_gates/test_integrity.py:116-131`,
   `Finding.mandate_elements`; имя находки — `Класс::метод`,
   `scripts/guard.py:605`). Методы, названные в ANSWER-1 поимённо
   (`CheckContentDefaultIsUnaffectedTest::*`, `test_ci_push_class.py::*`),
   гейт принял. Кодом это не закрыть: методы проверяли функции, которые
   требование 3 SPEC удаляет, а гейт — вне зон задачи. Код не менялся,
   эскалирован мандат.

6. После ANSWER-2 (04.10.2026): мандат уточнён — элемент-путь
   `tests/test_guard_artifact_branch_mode.py` целиком и три метода
   `tests/test_ci_push_class.py` поимённо; гейт сопоставляет путь файла
   со всеми его находками, так что 12 непокрытых методов закрыты. Код
   задачи не менялся; после подтяжки main (83ae989d) карта
   `docs/codebase-map.md` регенерирована (`python3 scripts/codebase_map.py`,
   изменился только `built_at_sha`). Прогон `python3 -m pytest
   tests/test_ci_push_class.py tests/test_guard_artifact_branch_mode.py
   tests/test_guard_extraneous_acceptance_files.py
   tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py
   tests/test_guard_schema.py -p no:cacheprovider -p timeout -o
   timeout=120` — 86 passed, 22 subtests passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (ci.yml приложением) | 2 (приложение 1), 3 |
| 2 (класс `artifact/` в ci_push_class) | 1 |
| 3 (режим `--artifact-branch` в guard) | 1 |
| 4 (без новых гейтов и ослаблений) | 1, 2 — гейты не тронуты; см. «Влияние» |
| 5 (invariants.md + test_invariants.py приложением) | 2 (приложения 2, 3), 3 |
| 6 (перечень изменённых/удалённых тестов) | 1; перечень — «Изменённые и удалённые тесты», мандат — ANSWER-1, уточнён ANSWER-2 |

## Влияние на систему
- Гейты переходов, гейт мержа (`fsm_merge_gate` гоняет `guard --all` по
  дереву мержа) и `fsm.guard_refuses` зовут `guard.check`/`check_content`
  без параметра режима — их поведение не меняется. Мягкого режима
  черновиков больше нет нигде: это снятие послабления, не ослабление.
- Инвариант 36: требование CI на `artifact/**` снимается по ADR-0021
  п.12 (таблица: «снятие проверки CI с заменой гейтом, решение
  Оператора»); остальные свойства инварианта сохранены, тест расширен
  (свойства 3–4), ни один его метод не удалён. Номер второго 36 → 39;
  тест на него — планки закрытой задачи `01M1TQ0TRCZPRZX22C4084NCPB` и
  `test_auto_cycle.py::FSM_STATES`, номер в них не фигурирует.
- `ci.yml` без приложения 1 при уже снятом режиме guard ломался бы
  только на пуше `artifact/**` (вызов несуществующего ключа = «файл не
  найден»); пульт туда не пушит с пина d860c974, поэтому три приложения и
  код едут одним мержем, промежуточного красного состояния нет.
- Откат — revert одного merge-коммита: код и приложения возвращаются
  вместе.

## Риски
- Удаление/переименование/смена утверждений в `tests/` — гейт
  неослабления тестов (инвариант 38) отказывает без мандата Оператора;
  мандат выдан в ANSWER-1 и уточнён в ANSWER-2, перечень — «Изменённые и удалённые тесты».
- Ручной `guard.py --all --artifact-branch` (старые сценарии, заметки)
  теперь падает «файл не найден» вместо мягкого прогона — это и есть
  AC-2.

## Предложения системе
- `orchestrator/advance_gates/test_integrity.py::Finding.mandate_elements`:
  докстринг обещает «элемент с `::` — только названный метод или
  класс», но элемент `путь::Класс` метод `Класс::метод` не покрывает
  (точное сравнение). А `mandate.refusals` при записи ANSWER такой элемент
  принимает молча (`_qualified_name_ok` допускает `<Класс>`) — тот же
  класс дефекта, что прецедент 26.09: годный по форме элемент гейт
  молча не засчитывает. В этой задаче он стоил лишнего круга эскалации.
  Надо одно из двух: засчитывать класс за все его методы либо отказывать
  классовому элементу при записи.
- `orchestrator/plank_run.py`: `plank-run <id>` без файла, когда планка
  — только разовые тесты, читающие PLAN.md из ссылки документов,
  упирается в сторож полного набора («итоговой строки нет», код 2) —
  сообщение не подсказывает назвать файл планки явно. Повторный шаг
  04.10: тот же отказ и с явно названным файлом планки (имя и путь
  `tasks/<id>/acceptance_tests/<файл>`) — `plank-run` в шаге
  developer этой задачи не работает вовсе.
- Разовая планка, читающая PLAN.md из ссылки документов, локально в шаге
  developer непрогоняема до автокоммита — шаг сдаёт приложения
  непроверенными планкой; `plank-run` мог бы подкладывать PLAN.md
  каталога документов поверх ссылки.

## Приложение 1: `.github/workflows/ci.yml` (требование 1, AC-3)

Подтверждено: `git apply --check` на чистом дереве ветки задачи проходит
(вместе с приложениями 2 и 3, подряд).

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 6c434c39..d29fced7 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -2,16 +2,16 @@ name: ci
 
 on:
   push:
-    # "artifact/**" — артефактная ветка пульта задачи внешнего target'а
-    # (SPEC T094, требование 7): guard обязан валидировать структуру
-    # tasks/<id>/ и там же, не только на кодовых ветках self.
+    # Веток `artifact/**` нет (ADR-0021 п.4, п.12): документы задачи живут
+    # в ссылке `refs/artifacts/<id>` и проверяются гейтами пульта на
+    # переходах, прогона CI на пуше документов нет.
     #
     # Фильтры `paths`/`paths-ignore` здесь ЗАПРЕЩЕНЫ (ADR-0016, инвариант
     # 36): пуш без прогона пульт читает как «проверок нет вовсе»
     # (`ci.verifying_status`/`ci.branch_status`) и висит до потолка
     # ожидания. Лишние проверки снимаются условием на job (статус
     # `skipped`, зелёный для `ci.GREEN`), не сужением триггера.
-    branches: ["main", "task/**", "artifact/**"]
+    branches: ["main", "task/**"]
   pull_request:
 
 jobs:
@@ -29,29 +29,19 @@ jobs:
       - name: guard.py по всем артефактам задач
         run: |
           # Ветка task/** — не источник истины для tasks/<id>/ (SPEC
-          # 01M1R9YEK08XEQWBFX0929WFVJ, требование 4/AC-9): роли коммитят
-          # артефакты только в артефактную ветку (artifact/**), кодовая
-          # ветка задачи несёт в лучшем случае устаревшую легаси-копию —
-          # guard по ней красил CI на расхождении, которого в источнике
-          # истины не было (SPEC «Контекст», 01M1PP0VYRT55WN8GGVG66X89Y).
-          # Источник истины — свой собственный прогон на пуше artifact/**.
+          # 01M1R9YEK08XEQWBFX0929WFVJ, требование 4/AC-9): документы
+          # задачи живут в ссылке `refs/artifacts/<id>` (ADR-0021 п.3),
+          # кодовая ветка задачи несёт в лучшем случае устаревшую
+          # легаси-копию — guard по ней красил CI на расхождении, которого
+          # в источнике истины не было (SPEC «Контекст»,
+          # 01M1PP0VYRT55WN8GGVG66X89Y). Документы проверяют гейты пульта
+          # на переходах и гейт мержа (ADR-0021 п.4).
           if [[ "${GITHUB_REF#refs/heads/}" == task/* ]]; then
-            echo "ветка task/** — tasks/<id>/ не источник истины здесь, источник — artifact/** (SPEC 01M1R9YEK08XEQWBFX0929WFVJ)"
+            echo "ветка task/** — tasks/<id>/ не источник истины здесь, документы проверяют гейты пульта (ADR-0021 п.4)"
             exit 0
           fi
-          # На артефактной ветке пульта задачи (`artifact/<id>`) каждый
-          # автокоммит шага роли несёт промежуточные, по определению
-          # неполные артефакты (01M1R66X5SMD3ZEDCVAJ0DR7K2, требование 6):
-          # `--artifact-branch` понижает нарушения содержания черновика
-          # до предупреждения, оставляя нарушения frontmatter и полную
-          # проверку «сданных» артефактов ошибкой. На `main` — вызов без
-          # флага, поведение прежнее.
-          GUARD_ARGS="--all"
-          if [[ "${GITHUB_REF#refs/heads/}" == artifact/* ]]; then
-            GUARD_ARGS="--all --artifact-branch"
-          fi
           if ls tasks/*/*.md >/dev/null 2>&1; then
-            python3 scripts/guard.py $GUARD_ARGS
+            python3 scripts/guard.py --all
           else
             echo "артефактов пока нет — ок"
           fi
@@ -96,9 +86,7 @@ jobs:
     # Мержи пульта идут пушем в main без pull request (merge_gate ->
     # done), поэтому сторож работает и на push: база — sha до пуша
     # (`github.event.before`); для новой ветки она нулевая — пропуск.
-    # ADR-0016: artifact/** несёт только tasks/<id>/ — skills/, templates/,
-    # docs/ там не меняются, диффу нечего проверять.
-    if: ${{ (github.event_name == 'pull_request' || github.event_name == 'push') && !startsWith(github.ref, 'refs/heads/artifact/') }}
+    if: ${{ github.event_name == 'pull_request' || github.event_name == 'push' }}
     runs-on: ubuntu-latest
     steps:
       - uses: actions/checkout@v4
```

## Приложение 2: `docs/invariants.md`, `tests/test_invariants.py` (требование 5, AC-4)

Подтверждено: `git apply --check` на чистом дереве проходит;
`CiJobsByPushClassInvariantTest` зелёный на `ci.yml` после приложения 1.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index 16bc3538..830412af 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -63,10 +63,10 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 33 | Тесты не пишут в настоящий репозиторий пульта: полный прогон `tests/` не меняет набор ссылок (`refs/heads/*`, `refs/artifacts/*`) настоящего репозитория; вся плотницкая запись ссылки документов `refs/artifacts/<id>` (`artifact_branch.write_commit`/`commit_files`, коммит закрытия `snapshot.py`, `pin.py`; ADR-0021 п.3) идёт через единую точку подмены `gitcmd` (не `subprocess.run`/`Popen` напрямую), которую `tests/sandbox.py::TmpRootTest` патчит по умолчанию для всех наследников | `test_invariants.CarpentryGitCallsGoThroughGitcmdTest`; CI job `python` (сторож ссылок вокруг `unittest discover`, `.github/workflows/ci.yml`); `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/test_ac1_full_suite_ref_isolation.py`, `test_ac2_previous_verdict_sha_test_migration.py`, `test_ac3_unified_git_choke_point.py` | tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md, требования 1-3 (класс-дефект: `tests.test_review_package.PreviousVerdictShaTest` заводил задачу через `cmd_new` без подмены `config.ROOT`, `artifact_branch.py` звал `subprocess.run` в обход `gitcmd` — сотни осиротевших веток `artifact/*` в настоящем репозитории пульта) |
 | 34 | Переход `in_dev → verifying` отказывает, если дифф ветки задачи трогает файлы вне объявленных `zones`/`zones_extension` и вне `config.COMMON_ZONES` (отказ называет конкретные файлы); исключение — раздел «## Расширение зон» PLAN.md, подкреплённый строкой `Расширение зон разрешено: <пути>` в ANSWER-n.md, ЧЕЙ ПОСЛЕДНИЙ КОММИТ в истории ссылки документов `refs/artifacts/<id>` (ADR-0021 п.3) доказанно не автокоммит артефактов шага роли (`checkpoint.py::own_commit_marker`) — developer не может подложить себе мандат Оператора через собственный автокоммит `tasks/<id>/` | `tests/test_zones_gate.py`; `tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/` | tasks/01M1P9QCHPHSCEA6TK13PV85SP/SPEC.md, требования 1-3; REVIEW.md итерация 2, R2-F1; ADR-0015 (переезд рубежа с `in_dev → review`) |
 | 35 | Тесты не читают сеть по DNS-имени: ни один файл `tests/**/*.py` не несёт адреса вида `http(s)://<DNS-имя>`, кроме `localhost`/`127.0.0.1` (допустимые исключения — именованная константа с обоснованием на каждую строку); сетевые git-команды (`fetch`/`push`/`ls-remote`/`clone`) с таким адресом перехватываются `tests/sandbox.py::TmpRootTest` мгновенным именованным отказом («сеть в тестах запрещена: `<команда>` `<адрес>`»), без обращения к сети | `test_invariants.NoNetworkAddressesInTestsTest`; `tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests/test_ac1_network_command_interception.py`, `test_ac2_local_bare_repo_not_blocked.py`, `test_ac9_network_interception_speed.py` | tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md, требования 1, 3 (инцидент 05.09: `git fetch -q https://example.invalid/sled main` висел минуты на DNS-резолвере при обрыве сети — фикстурный адрес `sled`-target'а в `tests/test_git_fixation.py`) |
-| 36 | Прогон CI существует для каждого пуша в `main`, `task/**`, `artifact/**`: секция `on.push` в `.github/workflows/ci.yml` не несёт фильтров `paths`/`paths-ignore`; лишние на данном классе пуша проверки снимаются условием на job (статус `skipped`, зелёный для `ci.GREEN`), причём job `python` не исключает `refs/heads/task/` и не строится как `== 'true'` по output соседнего job (fail-open), а job `guard` не исключает `refs/heads/artifact/` | `test_invariants.CiJobsByPushClassInvariantTest` | ADR-0016; `ci.verifying_status`/`ci.branch_status` читают пуш без прогона как «проверок нет вовсе» и держат задачу до потолка ожидания (инвариант 19) |
-| 36 | Порядок состояний FSM — `in_dev → verifying → review → acceptance → merge_gate`: CI подтянутой головы кодовой ветки проверяется ДО ревьювера, не после. Девять рубежей перехода `in_dev → review` (подтяжка main, прогон приёмочной планки, гейт зон, гейт заявки мутации — новые и изменённые тесты `tests/` без строки «Ловит мутацию:» в докстринге, 01M29A0F88P9GKSXFW90F99H2N, гейт неослабления тестов — удаление, переименование и ослабление тестов `tests/` без мандата Оператора, 01M3FQ2V77QNK95Z599DM124QN, гейт ёмкости, лок планки, гейт «замечания ревью не отработаны», сверка головы на origin) стоят на `in_dev → verifying` целиком, без повтора на `verifying → review`; в `review` из `verifying` ведёт только зелёный CI головы. Возврат `changes_requested` — в `in_dev`, повторный вход в `review` — снова через `verifying` | `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac01_ac09_state_order.py`; `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac02_ac08_gates_moved_to_verifying.py`; `test_auto_cycle.py::FSM_STATES` | ADR-0015 (docs/adr/0015-ci-before-review.md); tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md, требования 1-3 |
+| 36 | Прогон CI существует для каждого пуша в `main` и `task/**`: секция `on.push` в `.github/workflows/ci.yml` не несёт фильтров `paths`/`paths-ignore`; лишние на данном классе пуша проверки снимаются условием на job (статус `skipped`, зелёный для `ci.GREEN`), причём jobs `python` и `python-min` не исключают `refs/heads/task/` и не строятся как `== 'true'` по output соседнего job (fail-open). Пуш документов (`artifact/**`) прогона CI не требует и не получает: ни триггер, ни условие job не ссылаются на `artifact/`, а документы задачи проверяют гейты пульта на переходах и гейт мержа (`guard` полной проверкой, без мягкого режима для черновиков) | `test_invariants.CiJobsByPushClassInvariantTest` | ADR-0016; ADR-0021 пп. 4, 12 (снятие CI на пуше документов с заменой гейтами переходов, решение Оператора); `ci.verifying_status`/`ci.branch_status` читают пуш без прогона как «проверок нет вовсе» и держат задачу до потолка ожидания (инвариант 19) |
 | 37 | Класс `tests/*.py` с собственным `PATCHED_ATTRS` для `tests.sandbox.TmpRootTest` патчит `config.WORKTREES`, либо явно значится в `ALLOWLIST` скана с обоснованием, почему запись по этому пути для него недостижима (read-only сценарий или подмена самого `workspace.ensure`, не пути) — непропатченный `WORKTREES` не двигается вместе с `config.ROOT` (вычислен один раз при импорте) и уводит настоящий `git worktree add` в `.artel/worktrees` реального корня пульта, а не песочницы теста | `test_invariants.SandboxPatchedAttrsCoverWorktreesInvariantTest` | tasks/01M2CN465WEDCF6D77V37FJ82E/SPEC.md; docs/audits/code-revision-2026-09-12.md (CR-2026-09-12-1 ★), docs/audits/code-revision-2026-09-13.md (повтор) |
 | 38 | Удаление, переименование и ослабление тестов `tests/**/*.py` без мандата Оператора не проходят: переход `in_dev → verifying` отказывает именованным действием «переход отклонён: гейт неослабления тестов», гейт мержа тем же узлом сравнения переводит задачу в `escalated` до попытки merge. Находка — удалённый файл, пара переименования (`git diff -M`), исчезнувший из head тестовый метод изменённого файла и появившийся в head пропуск (`@skip`/`@skipIf`/`@skipUnless`/`@expectedFailure`/`@pytest.mark.skip`/`skipif`/`xfail`, вызов `self.skipTest(`/`pytest.skip(`), которого не было в base на том же имени; файл с нулём тестовых методов в base находкой не считается. Утверждение тестового метода, сохранившего имя, которого в head нет в той же нормальной форме (оператор `assert`, вызов `assert*`/`fail`, `pytest.raises`/`pytest.warns`; сообщение, локальные имена и корень импортированного модуля не различаются), — находка наблюдения: запись журнала «изменены утверждения тестов (наблюдение)» на обоих рубежах и раздел ревью-пакета, переход и мерж от неё не зависят (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6). Мандат — строка `Ослабление тестов разрешено: <пути и имена>` в `tasks/<id>/ANSWER-n.md`, ЧЕЙ ПОСЛЕДНИЙ КОММИТ в истории ссылки документов `refs/artifacts/<id>` доказанно не автокоммит артефактов шага роли (тот же рубеж, что у мандата зон в инварианте 34): роль не выписывает разрешение себе сама. Молчание git на переходе — отказ (fail-closed, ADR-0002), на мерже — fail-open, как у соседнего рубежа защищённых путей | `test_invariants.TestWeakeningNeedsTheOperatorTest`; `tests/test_test_integrity_gate.py` (в том числе `AssertionObservationTest`); `tests/test_guard_test_ast.py` (в том числе `ChangedAssertionsTest`); `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`; `tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests/` | tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md, требования 1-7; ADR-0002 (принцип целостности); строка бэклога П2 от 26.09.2026 «Гейт неослабления тестов в пульте» |
+| 39 | Порядок состояний FSM — `in_dev → verifying → review → acceptance → merge_gate`: CI подтянутой головы кодовой ветки проверяется ДО ревьювера, не после. Девять рубежей перехода `in_dev → review` (подтяжка main, прогон приёмочной планки, гейт зон, гейт заявки мутации — новые и изменённые тесты `tests/` без строки «Ловит мутацию:» в докстринге, 01M29A0F88P9GKSXFW90F99H2N, гейт неослабления тестов — удаление, переименование и ослабление тестов `tests/` без мандата Оператора, 01M3FQ2V77QNK95Z599DM124QN, гейт ёмкости, лок планки, гейт «замечания ревью не отработаны», сверка головы на origin) стоят на `in_dev → verifying` целиком, без повтора на `verifying → review`; в `review` из `verifying` ведёт только зелёный CI головы. Возврат `changes_requested` — в `in_dev`, повторный вход в `review` — снова через `verifying` | `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac01_ac09_state_order.py`; `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac02_ac08_gates_moved_to_verifying.py`; `test_auto_cycle.py::FSM_STATES` | ADR-0015 (docs/adr/0015-ci-before-review.md); tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md, требования 1-3 |
 
 ## На ревью — тестом не выражаются
 
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 096685bc..109f1734 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -2030,10 +2030,11 @@ if __name__ == "__main__":
 
 
 class CiJobsByPushClassInvariantTest(unittest.TestCase):
-    """Инвариант 36 (docs/invariants.md, ADR-0016): прогон CI существует
-    для каждого пуша в `main`, `task/**`, `artifact/**` — лишние проверки
-    снимаются условием на job (статус `skipped`, зелёный для `ci.GREEN`),
-    не сужением триггера.
+    """Инвариант 36 (docs/invariants.md, ADR-0016, ADR-0021 пп. 4, 12):
+    прогон CI существует для каждого пуша в `main` и `task/**` — лишние
+    проверки снимаются условием на job (статус `skipped`, зелёный для
+    `ci.GREEN`), не сужением триггера. Пуш документов (`artifact/**`)
+    прогона не получает: документы проверяют гейты пульта на переходах.
 
     Почему это инвариант, а не вкус: `ci.verifying_status` и
     `ci.branch_status` читают check-runs головы кодовой ветки; пуш, для
@@ -2047,8 +2048,12 @@ class CiJobsByPushClassInvariantTest(unittest.TestCase):
        `refs/heads/task/`, и не построены как `== 'true'` по output
        соседнего job (упавший `changes` дал бы пустой output и молча снял
        тесты — fail-open);
-    3. job `guard` не несёт условия, исключающего `refs/heads/artifact/`
-       (ради этой ветки триггер и заводился, SPEC T094, требование 7).
+    3. ни один job не несёт собственного условия со ссылкой на
+       `refs/heads/artifact/`, а job `guard` не зовёт режим
+       `--artifact-branch` — режима и веток `artifact/**` больше нет
+       (ADR-0021 п.4), условие на них — мёртвая развилка;
+    4. `on.push.branches` перечисляет `main` и `task/**` и не перечисляет
+       `artifact/**` (ADR-0021 п.12: CI на пуше документов отменён).
 
     Полного YAML в пульте нет намеренно (`orchestrator/yamlmini.py`,
     блочные списки не читаются), поэтому разбор — по блокам отступов:
@@ -2081,6 +2086,11 @@ class CiJobsByPushClassInvariantTest(unittest.TestCase):
                 out.append(ln)
         return out
 
+    @classmethod
+    def _job_names(cls, text: str) -> list[str]:
+        return [ln.strip().split(":")[0] for ln in cls._top_block(text, "jobs")
+                if ln.startswith("  ") and not ln[2].isspace()]
+
     @classmethod
     def violations(cls, text: str) -> list[str]:
         found = []
@@ -2090,15 +2100,30 @@ class CiJobsByPushClassInvariantTest(unittest.TestCase):
         for ln in on:
             if re.match(r"\s+paths(-ignore)?:", ln):
                 found.append(f"фильтр путей под on: — {ln.strip()}")
+        branches = [ln for ln in on if re.match(r"\s+branches:", ln)]
+        if not branches:
+            found.append("под on: нет списка branches")
+        for ln in branches:
+            for required in ('"main"', '"task/**"'):
+                if required not in ln:
+                    found.append(f"on.push.branches без {required} — {ln.strip()}")
+            if "artifact/" in ln:
+                found.append(f"on.push.branches несёт artifact/** — {ln.strip()}")
+        for job in cls._job_names(text):
+            for ln in cls._job_block(text, job):
+                if re.match(r"    if:", ln) and "refs/heads/artifact/" in ln:
+                    found.append(f"job {job}: условие исключает 'artifact/' — {ln.strip()}")
+        if any("--artifact-branch" in ln for ln in cls._job_block(text, "guard")):
+            found.append("job guard: вызывает режим --artifact-branch")
         for job, forbidden in (("python", "task/"), ("python-min", "task/"),
-                               ("guard", "artifact/")):
+                               ("guard", None)):
             block = cls._job_block(text, job)
             if not block:
                 found.append(f"job {job} не найден")
                 continue
             own_if = [ln for ln in block if re.match(r"    if:", ln)]
             for ln in own_if:
-                if forbidden in ln:
+                if forbidden and forbidden in ln:
                     found.append(f"job {job}: условие исключает {forbidden!r} — {ln.strip()}")
                 if job != "guard" and "== 'true'" in ln:
                     found.append(f"job {job}: условие fail-open (== 'true') — {ln.strip()}")
@@ -2144,6 +2169,54 @@ class CiJobsByPushClassInvariantTest(unittest.TestCase):
         self.assertTrue(any("исключает 'artifact/'" in v for v in self.violations(planted)),
                         self.violations(planted))
 
+    def test_planted_artifact_exclusion_on_any_job_is_caught(self):
+        """Ловит мутацию: проверка условия `refs/heads/artifact/` сужена
+        обратно до одного job `guard` — развилка на несуществующие ветки
+        `artifact/**` в условии другого job (здесь `canary-guid-leak`, где
+        она стояла до ADR-0021) прошла бы молча."""
+        text = (REPO_ROOT / self.CI_REL).read_text(encoding="utf-8")
+        planted = re.sub(
+            r"(\n  canary-guid-leak:\n(?:    [^\n]*\n)*?    if: \$\{\{ )",
+            r"\1!startsWith(github.ref, 'refs/heads/artifact/') && ",
+            text, count=1)
+        self.assertNotEqual(text, planted)
+        self.assertTrue(
+            any("canary-guid-leak: условие исключает 'artifact/'" in v
+                for v in self.violations(planted)),
+            self.violations(planted))
+
+    def test_planted_artifact_branch_trigger_is_caught(self):
+        """Ловит мутацию: проверка списка `on.push.branches` снята —
+        возвращённый в триггер `artifact/**` (CI на пуше документов,
+        отменённый ADR-0021 п.12) прошёл бы молча."""
+        text = (REPO_ROOT / self.CI_REL).read_text(encoding="utf-8")
+        planted = text.replace('"task/**"]', '"task/**", "artifact/**"]', 1)
+        self.assertNotEqual(text, planted)
+        self.assertTrue(any("artifact/**" in v for v in self.violations(planted)),
+                        self.violations(planted))
+
+    def test_planted_task_branch_dropped_from_trigger_is_caught(self):
+        """Ловит мутацию: проверка обязательных веток триггера снята —
+        `task/**`, выпавший из `on.push.branches`, оставил бы кодовую
+        ветку задачи без прогона CI, а пульт висел бы до потолка ожидания
+        (инвариант 19)."""
+        text = (REPO_ROOT / self.CI_REL).read_text(encoding="utf-8")
+        planted = text.replace('["main", "task/**"]', '["main"]', 1)
+        self.assertNotEqual(text, planted)
+        self.assertTrue(any('без "task/**"' in v for v in self.violations(planted)),
+                        self.violations(planted))
+
+    def test_planted_artifact_branch_mode_in_guard_job_is_caught(self):
+        """Ловит мутацию: проверка вызова режима в job `guard` снята —
+        возвращённая развилка `--artifact-branch` звала бы режим, которого
+        у `scripts/guard.py` больше нет (ADR-0021 п.4)."""
+        text = (REPO_ROOT / self.CI_REL).read_text(encoding="utf-8")
+        planted = text.replace("python3 scripts/guard.py --all\n",
+                               "python3 scripts/guard.py --all --artifact-branch\n", 1)
+        self.assertNotEqual(text, planted)
+        self.assertTrue(any("--artifact-branch" in v for v in self.violations(planted)),
+                        self.violations(planted))
+
 
 class SandboxPatchedAttrsCoverWorktreesInvariantTest(unittest.TestCase):
     """Инвариант 37 (docs/invariants.md; SPEC 01M2CN465WEDCF6D77V37FJ82E):
```

## Приложение 3: ссылки ADR на перенумерованный инвариант (требование 5)

Подтверждено: `git apply --check` на чистом дереве проходит.

```diff
diff --git a/docs/adr/0003-target-projects.md b/docs/adr/0003-target-projects.md
index ace2734d..482be460 100644
--- a/docs/adr/0003-target-projects.md
+++ b/docs/adr/0003-target-projects.md
@@ -412,7 +412,7 @@ ADR-0001; решение 22.08-2).
 модерацию слов — но никогда не отменяет внутреннее ревью кода.
 
 Пересмотрено ADR-0015 (06.09.2026): порядок цикла — in_dev →
-verifying → review → acceptance (инвариант 36); verifying стоит до
+verifying → review → acceptance (инвариант 39); verifying стоит до
 review, а не после.
 
 Ответы в треды: только по делу, без споров — разногласие
diff --git a/docs/adr/0007-gate-policy-autogate.md b/docs/adr/0007-gate-policy-autogate.md
index d5332d0c..913d473e 100644
--- a/docs/adr/0007-gate-policy-autogate.md
+++ b/docs/adr/0007-gate-policy-autogate.md
@@ -49,8 +49,8 @@
 
    Состояние на 29.09.2026: детекторы ослабления тестов частично
    внедрены — гейт заявки мутации и гейт неослабления тестов на
-   переходе `in_dev → verifying` (`docs/invariants.md`, второй
-   инвариант 36 и инвариант 38); пересмотр автогейта `merge_gate` не
+   переходе `in_dev → verifying` (`docs/invariants.md`, инварианты
+   39 и 38); пересмотр автогейта `merge_gate` не
    проводился, в `gates.yaml` он `manual`.
 
 5. spec_gate остаётся ручным без горизонта автоматизации: единственный
diff --git a/docs/adr/0015-ci-before-review.md b/docs/adr/0015-ci-before-review.md
index a7e2643c..436495c7 100644
--- a/docs/adr/0015-ci-before-review.md
+++ b/docs/adr/0015-ci-before-review.md
@@ -55,7 +55,7 @@ acceptance -> merge_gate`. Ревьювер видит код до прогон
 - Инварианты: `docs/invariants.md` — записи про порядок гейтов
   обновляются задачей; ослабления нет, все рубежи сохранены, один из
   них передвинут раньше.
-  Исполнено: кодировано инвариантом 36 (второй под этим номером;
-  перенумеровывается по ADR-0021, п.12, с этапа 1).
+  Исполнено: кодировано инвариантом 39 (до этапа 1 ADR-0021 — второй
+  под номером 36, перенумерован по ADR-0021, п.12).
 - Тесты FSM с явным порядком состояний правятся в задаче; планки
   закрытых задач не гоняются (принцип «история не переписывается»).
diff --git a/docs/adr/0016-ci-jobs-by-push-class.md b/docs/adr/0016-ci-jobs-by-push-class.md
index 3864347d..9bc8eb46 100644
--- a/docs/adr/0016-ci-jobs-by-push-class.md
+++ b/docs/adr/0016-ci-jobs-by-push-class.md
@@ -103,8 +103,8 @@ Workflow `ci.yml` запускается на каждом пуше в `main`, `
    YAML файла и проверяет структуру, не текст.
    Уточнено при раскатке: условие job `python` — `!= 'false'`, не
    `== 'true'` по выходу job `changes`: при сбое или отмене `changes`
-   выход пуст и тесты идут. Кодировано инвариантом 36 (первый под
-   этим номером).
+   выход пуст и тесты идут. Кодировано инвариантом 36 (до этапа 1
+   ADR-0021 — первый под этим номером).
 6. **Наследование итога родителя** (дополнение 11.09.2026,
    01M28NWK5X10J139Z8TD69HFAC; копилка 11.09 «Main красный, а CI main
    зелёный»). П.3 в исходной редакции присваивал документному пушу
```

## Изменённые и удалённые тесты (требование 6)

Мандат гейта неослабления тестов (инвариант 38) выдан Оператором в
`ANSWER-1.md` (04.10.2026) строкой «Ослабление тестов разрешено: …» —
ровно на перечень ниже; `ANSWER-2.md` (04.10.2026) уточнил форму:
`tests/test_guard_artifact_branch_mode.py` целиком путём файла (гейт не
сопоставляет элемент `путь::Класс` с методами) и три метода
`tests/test_ci_push_class.py` поимённо. Код после ответов не менялся
(ветка — коммит пульта 1de356f1).

Перечень по каждому методу (причина → замена):

| Метод | Что | Причина (SPEC) | Замена |
|---|---|---|---|
| `tests/test_ci_push_class.py::AdrClassificationTest::test_artifact_branch_is_code_false_without_touching_git_or_gh` | переименован в `test_artifact_branch_is_code_true_without_touching_git_or_gh`; `assertFalse(code)` → `assertTrue(code)`, `run.assert_not_called()` сохранён | треб. 2 / AC-1: `artifact/<x>` — обычная не-`main` ветка | тот же метод под новым именем |
| `tests/test_ci_push_class.py::AdrClassificationTest::test_artifact_branch_code_is_false` | удалён (`assertFalse(code)`, `assertIn("артефактная", reason)`) | треб. 2 / AC-1: причина не называет артефактную ветку | `tests/test_01m41vtqj9dsx64nfmfaf9w53b_artifact_mode_removed.py::ArtifactBranchPushIsAnOrdinaryBranchTest::test_ac1_artifact_push_classified_like_any_other_non_main_branch` |
| `tests/test_ci_push_class.py::OutputFormatTest::test_script_prints_code_and_reason_lines` | имя сохранено; вход — `pull_request` вместо пуша `artifact/…`; `"code=false"` → `"code=true"`, `assertIn("артефактная", lines[1])` → `assertIn("событие pull_request", lines[1])`; проверки «две строки, `code=` первой, код 0» сохранены | треб. 2: единственный герметичный (без git/gh) исход `code=false` был классом `artifact/` | тот же метод |
| `tests/test_guard_artifact_branch_mode.py::IsDraftLenientTest` (7 методов: `test_spec_draft_is_lenient`, `test_plan_review_test_report_draft_are_lenient`, `test_tz_questions_answer_draft_are_not_lenient`, `test_non_draft_status_is_not_lenient`, `test_missing_status_is_not_lenient`, `test_missing_type_is_not_lenient`, `test_unknown_type_with_draft_status_is_not_lenient`) | удалены | треб. 3: функция `is_draft_lenient` удалена | долгоживущий `GuardHasNoArtifactBranchModeTest` (3 метода `test_ac2_*`) |
| `tests/test_guard_artifact_branch_mode.py::BasicFrontmatterErrorsTest` (5 методов: `test_clean_meta_has_no_errors`, `test_missing_task_is_an_error`, `test_missing_schema_version_is_an_error`, `test_schema_version_present_but_zero_is_not_reported_as_missing`, `test_too_new_schema_version_is_an_error_with_the_version_named`) | удалены | треб. 3: функция `basic_frontmatter_errors` удалена | полная проверка `_content_errors` (frontmatter, `schema_errors`) — её тесты `tests/test_guard_schema.py` |
| `…::CheckContentDefaultIsUnaffectedTest::test_explicit_false_matches_the_default` | удалён | треб. 3 / AC-2: параметра `artifact_branch_mode` нет | `…artifact_mode_removed.py::GuardHasNoArtifactBranchModeTest::test_ac2_check_content_has_no_artifact_branch_mode_parameter` |
| `…::CheckContentDefaultIsUnaffectedTest::test_mode_true_on_a_lenient_draft_returns_only_basic_errors` | удалён | то же | `…::test_ac2_flag_does_not_soften_draft_spec_content_violation` |
| `…::CheckContentDefaultIsUnaffectedTest::test_mode_true_on_a_non_lenient_type_is_unaffected` | удалён | то же | `…::test_ac2_check_content_has_no_artifact_branch_mode_parameter` |

Сохранён без изменения утверждений:
`tests/test_guard_artifact_branch_mode.py::CheckContentDefaultIsUnaffectedTest::test_default_call_reports_full_content_errors_for_a_draft`
(черновик без секций отказывает — верно и без режима; правлен только
докстринг). `tests/test_invariants.py` — ни один метод не удалён и не
изменён по утверждениям, только добавлены.
