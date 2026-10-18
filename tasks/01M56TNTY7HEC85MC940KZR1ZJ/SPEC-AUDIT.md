---
task: 01M56TNTY7HEC85MC940KZR1ZJ
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py; в) пути-признаки (гейты): orchestrator/advance_gates/test_integrity.py, orchestrator/fsm_merge_gate.py"
spec_sha: c52dfe445ff40fbe0801236fb9d0d27e6487bd89
schema_version: 5
---

# SPEC-AUDIT: Гейт неослабления: помощники по области ослабления проекта

## ТЗ и SPEC
- ТЗ п.1 → SPEC требования 1–3: режим по `repo_context.is_artel`, область
  `weakening_scope`, перевод имени с `workdir`, профиль внутри зон, вызовы
  `review.py`/`fsm_merge_gate.py` не меняются, `TestModules`/
  `method_literal_keys` обратно совместимы, `fsm.py:1053-1060` не
  правится — перенесено полностью.
- ТЗ п.2 → требование 4 и AC-2 (а)–(д) — дословно совпадает с AC-10
  родителя (`refs/artifacts/01M56P60XS9AP4BH01YK35220D:…/SPEC.md:128`).
- ТЗ п.3 → требование 5. ТЗ «Критерии: AC-9, AC-10» → AC-1 (= AC-9
  родителя, `:127`), AC-2 (= AC-10). Раздел «Не входит» совпадает с ТЗ.
- Требований сверх ТЗ нет. ANSWER-n и решений Оператора на гейте SPEC в
  брифе нет.
- Замечание без отклонения: требование 10 родителя (`SPEC.md:109-113`)
  несёт ещё «тексты исходов, которые читает `orchestrator/report.py:117-123,
  996-1001`, сохраняются»; ни ТЗ, ни SPEC этого не переносят. Константы
  (`test_integrity.ASSERTIONS_COVERED`, `OUTCOME_FINDING`, …) импортируются
  report.py по имени — правка текста потекла бы в сводку без падения;
  задача тексты исходов менять не должна, риск низкий.

## Факты против кода
Подтвердилось:
- `orchestrator/advance_gates/test_integrity.py:631-650` — `_helper_callers`,
  `git grep … -- tests/` (`guard.TESTS_PACKAGE`, :639); фильтр
  `in_scope(path)` вызывающих — :765.
- `scripts/guard.py:1013-1019` — `_HelperScope._module`: первый сегмент
  `tests` (:1014), путь `dotted.replace(".", "/") + ".py"` (:1016).
- `scripts/guard.py:1087` — функция по импорту только из
  `SANDBOX_MODULE_PATH` (`:916`).
- `orchestrator/review.py:650-652`, `orchestrator/fsm_merge_gate.py:144-146`
  — передают только `scope=decision.profile.in_weakening_scope`.
- `review_lines` (:1237), `merge_gate_escalates` (:1571),
  `_test_integrity_gate` (:1475) имеют `task_id`; все три сходятся в
  `_evaluate(conn, task_id, …)` (:1074), откуда профиль читается
  `project_profile.for_task`/`decide` (`project_profile.py:140,162`) без
  правки вне зон — требование 2 выполнимо.
- `project_profile.py:72,78,95-100` — `weakening_scope`, `workdir`
  (умолчание `""`), `in_weakening_scope`; `repo_context.py:154` — `is_artel`.
- `orchestrator/fsm.py:1053-1060` — `guard.TestModules(...)` и
  `guard.method_literal_keys(..., modules)` без `workdir`.
- `targets.yaml:83,87` — sled: `workdir: backend`,
  `weakening_scope: [backend/tests/**/*.py]`; у артели `targets.yaml:49`
  — `[tests/**/*.py]`.

Не названо SPEC, но влияет на реализацию:
- `scripts/guard.py:929-958` (`_tests_import_bindings`, :936): пакет
  относительного импорта считается от пути файла от корня репозитория
  (`backend/tests/test_x.py` → пакет `backend.tests`), не от `workdir`
  (см. отклонение О3).
- Цепочка базовых классов (`_HelperScope.class_chain`, `resolve`) идёт
  через тот же `_module` — перевод с `workdir` в `_module` покроет и её.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да, частично | `_helper_callers` по-прежнему ищет в `tests/` (вызывающий `backend/tests/test_x.py` не найден); `_module` без `workdir` (`tests.rbac_support` → `tests/rbac_support.py`, модуля нет); ограничение «только `tests/sandbox.py`» (guard.py:1087) не снято у внешнего. Не ловит: `workdir` доведён только до `_test_integrity_gate`, а `review_lines`/`merge_gate_escalates` идут прежним путём (О2); режим включается по непустому `workdir`, а не по `is_artel` (О1). |
| AC-2 (а) | да | голое имя функции своего модуля перестаёт разворачиваться (guard.py:1077-1082, `_HelperScope.function`). |
| AC-2 (б) | да | функции `tests/sandbox.py` перестают прослеживаться у артели (режим внешнего не включается/включается неверно). |
| AC-2 (в) | да | у артели включён режим внешнего проекта («любой модуль области» = `tests/**`) — функция `tests/other.py` даёт находку. |
| AC-2 (г) | да | снят отказ по префиксу `test_` (guard.py:1080). |
| AC-2 (д) | да, при условии | наблюдаема только если тест подаёт узлу предикат области шире `tests/` у артели: фильтр `in_scope` (:765) иначе сам отсекает вызывающих вне `tests/`, и мутация «grep по всему репозиторию» не видна. Тест-автору — формулировка, не отклонение SPEC. |

## Зоны
- Зоны `scripts/guard.py`, `orchestrator/advance_gates/test_integrity.py`,
  `tests/` покрывают всё, что требуют требования 1–5: профиль читается
  внутри `_evaluate` вызовом `project_profile` (только чтение);
  `docs/codebase-map.md` — в `config.COMMON_ZONES` (`config.py:803`).
- Защищённых путей (`config.py:758-764`) задача не требует: `targets.yaml`
  только читается, учебный проект строится в тестах. `**/conftest.py`
  защищён — учебный проект в тестах не должен класть его в репозиторий
  пульта (внутри временного git-сэндбокса — не путь пульта).
- `tests/sandbox.py` в зоне (`tests/`) — сигнал миссии; правка песочницы
  сама проходит гейт неослабления (её функции — помощники артели).
  Песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Поиск вызывающих ослабленного помощника (test_integrity.py:631-650) | у артели — только `tests/` | да, у артели; у внешнего — область `weakening_scope` (усиление) | AC-2 (д), AC-1 | ок |
| Перевод имени модуля (guard.py:1013-1019) | `tests.x` → `tests/x.py` | да без `workdir`; с `workdir` — `backend/tests/x.py` | AC-2 (а)–(г), AC-1; умолчание — tests/test_guard_helper_scope.py:62-73 | ок |
| Импорт-помощник только из `tests/sandbox.py` (guard.py:1087) | у артели | да, у артели; у внешнего — любой модуль области | AC-2 (б), (в); tests/test_guard_helper_scope.py:35-73 | ок |
| `TestModules`/`method_literal_keys` без `workdir` — сверка «Меняемого поведения» на гейте SPEC (fsm.py:1053-1060) | «было» ищется среди литералов метода, помощника своего класса, базового класса `tests/`, функции `tests/sandbox.py`; функция другого модуля `tests/` не помощник | да (требование 3) | умолчание `_HelperScope` — tests/test_guard_helper_scope.py:62; позитив — tests/test_01m4nz5kt0px0rywtstn1xefs5_approve_behavior_literals.py:400. Негатива «функция `tests/other.py` не даёт «было»» через `method_literal_keys` нет — держится общим `_assertion_records` | ок, при условии что новый параметр живёт в общем `_HelperScope`/`TestModules`, а не только в `method_literal_keys` |
| Fail-closed молчания git в поиске вызывающих (test_integrity.py:757-761) | отказ, не пропуск | должен остаться и у новой формы grep по маскам области | не покрыто AC этой задачи для внешнего пути (у артели — прежние тесты) | замечание, не отклонение: требование-замена не нужно, свойство не ослабляется SPEC |

## Пути обхода гейтов
1. Режим по `workdir`, а не по `is_artel`: требование 3 вводит в guard
   единственный новый аргумент `workdir` («без него поведение прежнее»);
   буквальная реализация «внешний режим ⇔ `workdir` задан» оставляет
   внешний проект без `workdir` (умолчание `""`,
   `project_profile.py:78,95`) в режиме артели — помощники вне
   `tests/sandbox.py` невидимы, AC-1 (`workdir: backend`) проходит (О1).
2. Вход узла: `workdir`/режим, доведённые только до `_test_integrity_gate`
   (у него `decision.profile` под рукой, test_integrity.py:1509-1518),
   проходят AC-1 через рубеж `in_dev → verifying`, а гейт мержа
   (`merge_gate_escalates`, :1587) и раздел ревью-пакета (`review_lines`,
   :1245) остаются слепыми к помощникам чужого стека (О2).
3. Относительный импорт: `from .rbac_support import f` в
   `backend/tests/test_x.py` даёт привязку `backend.tests.rbac_support.f`
   (guard.py:936,950-952), которую `_module` отбрасывает по первому
   сегменту (guard.py:1014). SPEC переводит только `tests.x`; ослабление
   помощника, импортированного относительно, проходит без находки при
   выполненном AC-1 (О3).

## Вердикт
**concerns** — SPEC выполнима в зонах, факты о коде верны, AC-2 ловит
регресс артели; решить остаток может Оператор на гейте:

- **О1** (`SPEC.md` требования 1 и 3; `project_profile.py:78,95`): у
  внешнего проекта без `workdir` требования 1 («любой модуль области») и
  3 («без `workdir` поведение прежнее») расходятся, и SPEC не говорит, как
  признак `is_artel` доходит до guard. Предложение: требование 3 уточнить
  — режим передаётся отдельно от `workdir` (или «без аргумента режима —
  поведение артели»); в AC-1 добавить случай внешнего проекта с пустым
  `workdir` (`weakening_scope: [tests/**/*.py]`, функция `tests/x.py`
  даёт находку).
- **О2** (`SPEC.md` AC-1; test_integrity.py:1245,1517,1587): AC-1 не
  называет вход узла; мутация «режим внешнего только на рубеже
  `in_dev → verifying`» не ловится. Предложение: AC-1 — находка на рубеже
  `in_dev → verifying`, на гейте мержа (`merge_gate_escalates`) и строка
  в разделе ревью-пакета (`review_lines`), либо проверка на общем узле
  `_evaluate` с чтением профиля по `task_id`.
- **О3** (`SPEC.md` требование 1; guard.py:936,1014): относительный
  импорт помощника у внешнего проекта с `workdir` не переводится — путь
  обхода. Решение Оператора: включить (`from .x import f` →
  `backend/tests/x.py`, критерий) или явно вынести в «Не входит».
- **О4** (`SPEC.md` требование 1, «из любого модуля области»; guard.py:1014):
  не сказано, остаётся ли фильтр пакета `tests` и проверяется ли
  принадлежность модуля помощника `weakening_scope`; критерия «функция
  модуля вне области (`backend/app/x.py`) — не помощник» нет. Ослабления
  это не даёт (перебор — лишние находки), но граница неоднозначна.
