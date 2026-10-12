---
task: 01M4PMPMZ7PPCN3JWX75RTJZQN
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: База сравнения джоба защищённых путей — первый родитель merge-коммита PR

## Фаза A: план
- Покрытие: все 6 требований SPEC сведены к одному шагу. Для правки одной
  функции одного файла (~100 строк) это размер одного MR, а не «сделать всё»;
  SPEC сам обосновывает монолит.
- Подход (условия проверяются по порядку, первое невыполненное — причина
  отката; сбой чтения от доказанного `HEAD^1` — код 2) совпадает с
  требованиями 1 и 4 и не трогает `ci.yml` (требование 3).
- «Влияние на систему» сходится с диффом: изменены только
  `scripts/ci_protected_paths.py` и `tests/test_ci_protected_paths.py`
  (+ долгоживущий файл автора тестов). `docs/codebase-map.md` отличается от
  регенерации только строкой `built_at_sha`. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `merge_first_parent` (`scripts/ci_protected_paths.py`): `rev-list --parents` → ровно 2 родителя; `merge-base --is-ancestor BASE_SHA HEAD^1` (код 0 — да, 1 — нет, иначе — названная ошибка); `pull_request.head.sha` из `GITHUB_EVENT_PATH`; `HEAD^2 == head.sha`. Перечень и дифф берутся от выбранной базы. Каждое невыполненное условие печатается строкой «HEAD не признан merge-коммитом PR — база BASE_SHA: …». |
| 2 | OK | Пустой `BASE_SHA` проверяется в `main` до `merge_first_parent` → код 2, причина с «BASE_SHA»; `CiScriptRunsAsScriptTest` зелёный без правки. |
| 3 | OK | `ci.yml` не тронут; строка «база сравнения: <sha> (<источник>)» печатается до чтения перечня, поэтому видна при кодах 0, 1 и 2. |
| 4 | OK | Сбой перечня или диффа от `HEAD^1` → код 2 без отката (`label`=источник в причине); ошибка git/исключение при проверке предка и любой дефект файла события → откат на `BASE_SHA` с причиной; сбой чтения от `BASE_SHA` → код 2, как прежде. |
| 5 | OK | Перечень по-прежнему берётся из базы, а не из HEAD (AC-10 зелёный); PR, правящий защищённый путь, красный при обеих формах HEAD (AC-3). |
| 6 | OK | Долгоживущий файл задачи (временный git-репозиторий, явное окружение без `GITHUB_*`) несёт заявки на все три мутации. Добавленный `EventHeadShaTest` проверяет JSON не той формы; долгоживущий файл этот случай не повторяет (AC-6 там — только dict без `sha`). Существующие ассерты не изменены и не удалены: дифф `tests/` 4582f129..HEAD — только добавления. |

## Замечания
Блокирующих и major-замечаний нет.

Проверено и замечанием не стало:
- `BASE_SHA`, начинающийся с `-`, ушёл бы в `merge-base` как опция. Это тот же класс, что прежний `git show <base>:…`; значение даёт payload GitHub, а не ветка PR. Нового риска нет.
- В `PLAN.md` в покрытии всё сведено к одному шагу. Это оправдано размером правки.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 замечаний не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m4pmpmz7ppcn3jwx75rtjzqn_merge_base_choice.py tests/test_ci_protected_paths.py tests/test_protected_test_settings.py`: 37 passed, 123 subtests passed (17.3 с локально).
- `python3 …/orchestrator/artel.py plank-run 01M4PMPMZ7PPCN3JWX75RTJZQN`: 1 passed (`test_ac7_existing_script_test_untouched.py`), код pytest 0.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`: расходится только строка `built_at_sha`, содержимое свежее. Файл восстановлен через `git checkout`.
- Временные мутации `scripts/ci_protected_paths.py`. После каждой код восстановлен, `git status` чистый.
  - Выброшены проверки `isinstance` в `_event_head_sha` (цепочка `event["pull_request"]["head"]["sha"]`) → `EventHeadShaTest` красный, 3 подслучая.
  - Сверка `HEAD^2` с `head.sha` заменена на `if False:` → AC-4 и AC-5 (each) красные.
  - Возврат `second` вместо `first` → AC-1, AC-2 и AC-8 красные.
  - Код 128 `merge-base --is-ancestor` принят как «предок» → `test_ac5_git_error_on_ancestor_check_is_failed_condition` красный. Первая попытка по ошибке мутировала одноимённую строку в `_git`, после перенацеливания тест покраснел.
  - Сбой перечня `HEAD^1` → откат на `BASE_SHA` → `test_ac9_unreadable_list_at_first_parent_is_code_2` красный (2 подслучая).
- Проверено, что `git merge-base --is-ancestor <несуществующий sha> HEAD^1` на git 2.50.1 отвечает кодом 128: этот путь кода реально исполняется.
- `git diff 4582f129 HEAD --stat -- tests/ .github gates.yaml roles.yaml skills templates`: правки только в двух файлах `tests/`, обе — добавления; защищённые пути не тронуты.

## Предложения системе
- Долгоживущий файл `tests/test_01m4pmpmz7ppcn3jwx75rtjzqn_merge_base_choice.py` идёт в CI 63 с, при пороге 60 с; локально весь трёхфайловый набор занимает 17 с. Расхождение CI и локального прогона примерно в 4 раза у тестов на реальном git (`RealGitSandbox`) стоит учесть в пороге или в скиле test-authoring: много `merge_head`/`checkout` на сценарий.
- Временная мутация через `str.replace(..., 1)` легко попадает в одноимённую строку другой функции: так было здесь с `_git` и `merge_first_parent`. Приём «временная мутация» в review-checklist стоит дополнить: перед прогоном проверить, что мутирована именно заявленная функция.
