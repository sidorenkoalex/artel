---
task: 01M45FJVGQT1K0P8HDEXZX6HS7
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Этап 3 ADR-0021, часть 1 из 3 — профиль тестов проекта и проверки тестов на repo_context

## Фаза A: план

- Таблица покрытия полна: требования 1–8 → шаги 1–6.
- В разделе «Тесты» PLAN появился новый файл `tests/test_project_profile_gates.py`
  с перечнем сторожей и пятью временными мутациями. Это закрывает пробел
  между требованием 8 и планом из итерации 1.
- Раздел «Проверено исполнением» PLAN дополнен разбором CI 8ddb330d:
  красный `pull_request`-прогон шёл без приложений. ANSWER-2 этот диагноз
  принял. Код реализации и приложения с итерации 1 не менялись: в
  инкрементальном diff 098b8a0d…HEAD только `tests/test_project_profile_gates.py`
  (карта исключена из пакета).
- Правка `tests/test_ci_status_kind_gate.py::NonRedStatusSkipsRerunTest.setUp`
  — дополнение фикстуры, утверждения не тронуты. Её законность
  подтверждает ANSWER-2, вопрос 2.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py::_check_profile`; долгоживущий `test_..._test_profile.py` зелёный |
| 2 | OK | `repo_context.profile_of` — три исхода; `project_profile.decide` |
| 3 | OK | `journal_skip` во всех местах таблицы; сторож в `tests/`: `SkipIsJournaledTest` (4 места, настоящий `store.journal`) |
| 4 | OK | отказ артели без профиля; `test_..._profile_refusals.py` |
| 5 | OK | развилки сняты; области, каталог и шаблон берутся из профиля. Сторож с неартельным профилем — `ForeignProfile*Test` |
| 6 | OK | прогона в `config.ROOT` нет; AC-11 держат долгоживущие тесты |
| 7 | OK | приложения в PLAN; `test_plan_facts.py` планки (`git apply --check`, инварианты с приложениями) зелёный |
| 8 | OK | тесты в `tests/` на требования 1–6 с заявками; смен утверждений нет; правки фикстур перечислены |

## Замечания

Новых замечаний нет.

Сведение по R1-F1. Файл `tests/test_project_profile_gates.py`: у всех
11 методов есть докстринг с «Ловит мутацию», и каждая заявка называет
наблюдаемое расхождение (нет записи в журнале, есть или нет отказа,
текст подсказки). Сторожа не повторяют долгоживущие файлы задачи: те
держат артель и неразрешённый контекст, а этот файл — внешний проект.
Обе мутации ревьювера из итерации 1 и мутация `scope=None` на гейте
неослабления теперь ловятся (см. «Проверено исполнением»).

Одна мелочь, без отдельного замечания. `ForeignProfileLongLivedPathTest`
собирает `Profile` напрямую, а не через `targets.yaml`. Чтение профиля
из файла уже держат `test_..._test_profile.py` и `decide` в соседних
классах, поэтому пробела здесь нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_project_profile_gates.py | Требование 3 и требование 5 для внешнего проекта с профилем держала только планка «разовый» | после мержа правка, которая отключит запись о пропуске или зашьёт артельную область, прошла бы зелёный CI | закрыто: добавлен `tests/test_project_profile_gates.py`, 11 методов с заявками. Ревьювер сам повторил три временные мутации, все ловятся: `journal_skip` → `return` — 4 failed; зашитый фильтр `tests/test_*.py` в `_mutation_claim_gate` — 2 failed; `scope=None` в `_test_integrity_gate` — 2 failed |

## Вердикт

approved. R1-F1 закрыт, сторожа требований 3 и 5 в `tests/` проверены
временными мутациями. Новых blocker и major нет.

## Проверено исполнением

- `python3 -B -m pytest -q -p no:cacheprovider -p timeout -o timeout=120
  tests/test_project_profile_gates.py tests/test_project_profile.py
  tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py
  tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py` — 31 passed,
  46 subtests passed.
- Временные мутации, каждая отдельно; после каждой код возвращён
  `git checkout -- orchestrator/`, `git status` пуст:
  - `project_profile.journal_skip`, тело заменено на `return` — в
    `tests/test_project_profile_gates.py` 4 failed (все методы
    `SkipIsJournaledTest`);
  - `advance_gates/review.py:239`: `profile.in_mutation_claim_scope(f)`
    заменён зашитым `f.startswith("tests/test_") and f.count("/") == 1`
    — 2 failed (`ForeignProfileMutationClaimTest`);
  - `advance_gates/test_integrity.py:1125`: `scope=decision.profile.in_weakening_scope`
    заменён на `scope=None` — 2 failed (`ForeignProfileWeakeningTest`).
- `artel.py plank-run 01M45FJVGQT1K0P8HDEXZX6HS7` целиком оборван по
  лимиту пульта 300 с, итоговой строки pytest нет. По файлам:
  `test_profile_gates_git.py` — 23 passed (87 с), код выхода 0;
  `test_plan_facts.py` — 8 passed (164 с), код выхода 0. Всего 31, столько
  же, сколько в итерации 1.
- CI коммита f7e1aa62 зелёный (8 проверок, по пакету). Полный набор
  `tests/` в шаге не запускался (правило шага).

## Предложения системе

- `artel.py plank-run`: у этой задачи общий прогон планки (около 250 с
  чистого pytest) упирается в жёсткий лимит 300 с, хотя по файлам планка
  зелёная. Стоит выводить лимит из размера планки или называть в отказе
  обход «по файлам» (`orchestrator/plank_run.py`).
