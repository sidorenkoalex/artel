---
task: 01M57JYJQC8VAHEWMXFNM7D1GS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Планка внешнего проекта внутри workdir: конфиг, импорты и фикстуры проекта

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–13 сопоставлены шагам 1–8; 13 закрыто долгоживущими файлами test_author.
- Шаги — единицы размера MR (механика в `acceptance.py`, проводка `task_id` в `plank_run.py`, правка по мандату, два новых теста), не микрооперации.
- Подход (контекст-менеджер `_plank_layout` внутри `run`/`collect`/`run_plank`) с архитектурой не конфликтует: `amend.py` не трогается, потому что обе ветви `amend-tests` уже зовут эти функции с `cwd` рабочей копии и профилем. AC-4 зелёный, значит это так.
- «Влияние на систему» соответствует diff: `orchestrator/acceptance.py`, `orchestrator/plank_run.py`, две правки `tests/test_01m56g23…` и два новых файла `tests/`. Вне зон ничего не тронуто; `.github/`, `gates.yaml`, `skills/`, `templates/` не тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_plank_layout` встроен в `run` (acceptance.py ~:779), `collect` (~:915) и `run_plank` (~:1350). Через них идут гейты, подтяжка, `plank-run` и обе ветви `amend-tests`. AC-1/AC-4 гоняются настоящим pytest и зелёные |
| 2 | OK | `copytree(tests_dir)` копирует каталог как он лежит на диске: штатную выкладку с `_pult.py` или правку Оператора с помощником. AC-4 сверяет выкладку с диском побайтно |
| 3 | OK | `_layout_target` переводит путь вида `<файл>[::узел]` из каталога планки в выкладку; AC-2 |
| 4 | OK | `plank_run.py` передаёт `task_id` только в ветке планки; в ветке долгоживущего пути выкладки нет. AC-3 (шпион на `Popen`) и `assert_runs_file` после правки |
| 5 | OK | Уборка `_drop_layout` стоит в `finally`. AC-5 проверяет 5 исходов × 3 места |
| 6 | OK | `_exclude_layout`: `rev-parse --git-path info/exclude`, `flock` на самом файле, проверка и дописывание под блокировкой; шаблон пишется до `copytree`. `drop_from_code_copy` убирает остаток. AC-6, а также `test_acceptance_plank_layout_refusal.py` и `test_acceptance_plank_exclude_lock.py` (ANSWER-2 п.1–2) |
| 7 | OK | `--ignore=<lld от workdir>/.artel-plank` в `run_full_suite`, подстроки `acceptance_tests` в нём нет; ключ итога не тронут. AC-8 (обе ветви `norecursedirs`) |
| 8 | OK | Выкладку скрывает `info/exclude`; AC-9 и AC-10 через настоящий `commit_success_checkpoint` |
| 9 | OK | Путь узла `.artel-plank/<id>/acceptance_tests/<файл>`, заголовок по-прежнему `tests_dir`; AC-11 |
| 10 | OK | Режим «outside» печатает `LAYOUT_OUTSIDE_NOTE`; `collect` дописывает строку и к зелёному/пустому выводу. AC-12 |
| 11 | OK | У `pult-pytest` `_layout_mode` возвращает «», и путь прежний; `..._artel_plank_unchanged.py` зелёный |
| 12 | OK | Ровно две правки: в `assert_runs_file` к запретным целям добавлен путь выкладки (проверка по префиксу, прежний путь остался); в `Ac6…` для `self.ext` ожидаемый путь собран в тесте с `realpath`, для `ARTEL` всё прежнее, `assertEqual` над всем списком сохранён. Покрыто мандатом ANSWER-1/ANSWER-3 |
| 13 | OK | Учебный проект создаётся кодом теста во временном каталоге; в `tests/` нет новых `conftest.py`; сети нет |

## Замечания
Blocker/major/minor-замечаний нет. Ниже наблюдения, которые не требуют правки кода и не заведены в реестр:
- PLAN, шаг 6, утверждает: «Мутация (снят `flock`) краснит оба» теста блокировки. Временной мутацией (снят `fcntl.flock(fh, LOCK_EX)`) я воспроизвёл красноту только у `test_check_and_append_wait_for_lock_holder`. `test_parallel_tasks_leave_single_line` остался зелёным: окно гонки двух потоков слишком узкое. Заявка самого теста при этом про другую мутацию — «без проверки под блокировкой», то есть дописывание без проверки, — и такую мутацию тест ловит детерминированно (вторая строка появляется и без гонки). Блокировку держит первый тест, так что неточна только формулировка PLAN, не сторож.
- `tests/test_acceptance_plank_layout_refusal.py`: `test_refusal_without_exclude_launches_nothing` повторяет тела `places()` и `assert_refused()` вместо их вызова (`assert_refused("")`). Это вкус, на поведение не влияет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: blocker/major/minor-замечаний итерации 1 нет, прошлых итераций нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_acceptance_plank_exclude_lock.py tests/test_acceptance_plank_layout_refusal.py tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py tests/test_01m57jyjqc8vahewmxfnm7d1gs_artel_plank_unchanged.py tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py` — 24 passed, 78 subtests passed (68.9 с).
- Тесты затронутых модулей: `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`, `test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py`, `test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `test_acceptance.py`, `test_plank_run_edges.py`, `test_pull_long_lived_plank.py` — 71 passed, 80 subtests passed.
- `artel.py plank-run 01M57JYJQC8VAHEWMXFNM7D1GS` — отказ «планки нет»: в зафиксированной планке нет `test_*.py`, все AC закрыты долгоживущими файлами `tests/`. Рабочая копия после прогона чистая.
- Временная мутация 1: сняты `--ignore` в `run_full_suite` и уборка остатка в `drop_from_code_copy`. Покраснели `Ac8…` (подтест с `norecursedirs` без точек: собран узел остатка `.artel-plank/…/test_ac1_left_*.py`) и `Ac6…`. Код возвращён `git checkout`, дерево чистое.
- Временная мутация 2: снят `flock`, ошибка записи `info/exclude` проглатывается. Покраснели `test_check_and_append_wait_for_lock_holder`, `test_refusal_on_lock_io_error` (3 места) и `test_refusal_when_exclude_not_writable` (3 места); `test_parallel_tasks_leave_single_line` остался зелёным (см. наблюдение). Код возвращён, дерево чистое.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет, карта свежа. Изменение отменено `git checkout`.
- Дифф `tests/` от base сверен вручную: изменён только `test_01m56g23…` — две правки ровно по мандату ANSWER-1/ANSWER-3; удалённых или ослабленных утверждений нет. Остальное — новые файлы, у каждого метода есть «Ловит мутацию: …».

## Предложения системе
- Долгоживущий `tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py` идёт ~70 с (порог пакета 60 с): каждый метод поднимает настоящий git-клон и настоящий pytest. Класс «долгоживущий файл на настоящем pytest дороже порога» стоит назвать в skills/test-authoring.md (общая песочница на класс или сужение подтестов).
- Заявки двух тестов одного файла про близкие мутации (`flock` и проверка под ним) легко спутать в PLAN («краснит оба»): ревью по заявке, а не по PLAN, это ловит, но шаблону PLAN стоит просить называть мутацию по тесту.
