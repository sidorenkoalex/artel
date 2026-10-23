---
task: 01M5N8ASJ63ZKF3M9ETC7A3P5V
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: CR-8, этап 1 — самодостаточная часть выкладки планки в `orchestrator/plank_layout.py`; публичные имена для закрытых имён `acceptance`

## Подход
Перенос дословный, поведение не меняется.

1. Новый модуль `orchestrator/plank_layout.py`. В нём константы, функции
   и классы самодостаточной части выкладки из требования 1. Тела, тексты
   отказов и комментарии-заголовки блоков перенесены без изменений.
   Имена без подчёркивания получили те функции и классы, которым их
   назначило требование 1. `_inside`, `_layout_parent` и `_LAYOUT_ID`
   остались закрытыми. Из пакета модуль импортирует только `gitcmd` —
   у него нет верхнеуровневого импорта `acceptance`, поэтому цикла нет.
2. В `acceptance.py` на месте перенесённых определений стоит блок
   реэкспорта тех же объектов: `_exclude_layout = plank_layout.exclude_layout`,
   константы — `X = plank_layout.X`, и так далее. Пять несамодостаточных
   функций (`_layout_ignore`, `_layout_check`, `_plank_plan`,
   `_component_layout`, `_laid_plank`) остались на месте. Они, как и
   прочие вызывающие внутри `acceptance.py`, зовут перенесённое через
   прежние имена модуля `acceptance`. `plank_layout` добавлен в импорт
   `from . import (…)`.
3. В конце `acceptance.py` объявлены публичные двойники тринадцати
   закрытых имён требования 4 (`reported = _reported` и т. д.). Двойника
   `_last_full_suite_metrics` нет.
4. Восемь вызывающих модулей переведены с `acceptance._x` на
   `acceptance.x`. Менялись только обращения в коде. Два упоминания в
   докстрингах (`outcome_integrity.py`, `plank_run.py`) остались прежними:
   закрытое имя существует, а правка текста вне требования.
5. В `_durations_reader` ленивый импорт `suite_durations` перенесён внутрь
   `try`. Его сбой обрабатывается так же, как сбой запуска потока: прогон
   идёт без потока.
6. Тесты требования 8 уже написаны test_author'ом в долгоживущих файлах
   `tests/test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py`
   (а, б, в, г) и `tests/test_01m5n8asj63zkf3m9etc7a3p5v_durations_reader_failure.py`
   (д). Свойств вне их покрытия задача не вводит, поэтому своих тестов
   разработчик не добавлял.

Бюджет SPEC (30 USD) не переоценивался.

## Шаги
1. Создать `orchestrator/plank_layout.py`, в `acceptance.py` заменить
   перенесённые определения реэкспортом. Сделано.
2. Объявить 13 публичных двойников и перевести 8 вызывающих модулей.
   Сделано.
3. Перенести импорт `suite_durations` внутрь `try` в
   `_durations_reader`. Сделано.
4. Перегенерировать карту (`python3 scripts/codebase_map.py`). Сделано.
5. Прогнать долгоживущие файлы задачи и адресно файлы требования 10
   (список ниже).

## Поиск подмен тестами (требование 5, AC-8)
Поиск повторён на базе ветки (HEAD aee57e78, в `tests/` нет изменений
против 84c784aa, кроме двух долгоживущих файлов этой задачи). Искались
имена из списка требования 4 (`_reported`, `_own`, `_full_suite_outcome`,
`_own_cwd`, `_own_target`, `_place_command`, `_place_env`,
`_run_in_session`, `_report_run`, `_report_suite_result_key`,
`_task_own_profile`, `_component_name`, `_process_snapshot`) во всех четырёх
формах:
- `mock.patch.object(<…>.acceptance, "<имя>", …)` — разбор `ast`: любая
  строка-константа, равная имени из списка;
- `mock.patch("orchestrator.acceptance.<имя>")` — строка-константа с
  префиксом `orchestrator.acceptance.` и последним сегментом из списка;
  дополнительно `grep` по `acceptance\._<имя>` в строках с
  `patch`/`setattr`/`=`;
- присваивание `acceptance.<имя> = …` — узлы `Assign`/`AugAssign` с целью
  атрибутом модуля `acceptance`;
- `monkeypatch.setattr(<…>acceptance, "<имя>", …)` — покрыта первой
  проверкой (строка-константа с именем).

Результат: подмен не найдено. Единственные попадания — перечень строк
`CALLED_PRIVATE` в долгоживущем файле этой задачи
`tests/test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py:62–66`. Это
не подмена, а список проверяемых имён. Исключений требования 5 нет:
константа исключений — `{"_last_full_suite_metrics"}`.

Перенесённые имена выкладки (требование 1) тесты тоже не подменяют.
`tests/test_acceptance_plank_exclude_lock.py` только зовёт
`acceptance._exclude_layout`. Подмены `acceptance.fcntl.flock`,
`acceptance.shutil.rmtree` и `acceptance.gitcmd.*` подменяют атрибут
самого модуля `fcntl`/`shutil`/`gitcmd`, общего с `plank_layout`, поэтому
действуют и на перенесённый код.

## Файлы `tests/`, прогнанные адресно (требование 10, AC-8)
Файлы `tests/` с подменой атрибутов `orchestrator.acceptance` (56 файлов,
дерево 84c784aa, детектор `patching_test_files` планки):

test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py,
test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py,
test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py,
test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py,
test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py,
test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py,
test_01m46c776szemypbqgpnjn1txy_appendix_gates.py,
test_01m484rnv3qbdy3b0m16j916zp_external_flow.py,
test_01m48wt5x7zc7332drh85vy19d_base_reuse.py,
test_01m48wt5x7zc7332drh85vy19d_suite_reuse.py,
test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py,
test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py,
test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py,
test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py,
test_01m4jd36367e5cg3gxdv429xte_amend_pult.py,
test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py,
test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py,
test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py,
test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py,
test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py,
test_01m52eedeyv14658x8vfnhcw8k_launch_places.py,
test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py,
test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py,
test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py,
test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py,
test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py,
test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py,
test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py,
test_01m5enwtdd8np9smpfx3jn08j9_plank_run_summary.py,
test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py,
test_acceptance.py,
test_acceptance_plank_layout_refusal.py,
test_acceptance_pycache.py,
test_acceptance_suite_profile.py,
test_approve_acceptance_full_suite.py,
test_branch_freshness_gate.py,
test_component_report_gates.py,
test_component_report_run.py,
test_docs_dir_layout.py,
test_external_code_copy_refusal.py,
test_fsm_advance_tests_writing_artifact_source.py,
test_fsm_advance_tests_writing_dry_collect.py,
test_fsm_advance_tests_writing_test_groups.py,
test_fsm_autogate.py,
test_fsm_map_conflict_autoresolve.py,
test_full_suite_profile_timeout.py,
test_full_suite_reuse.py,
test_long_lived_transitions.py,
test_pull.py,
test_pull_conflict_marker_states.py,
test_pull_long_lived_plank.py,
test_pytest_own_result_ids.py,
test_suite_lock.py,
test_suite_near_limit.py,
test_suite_run.py,
test_task_component_places.py.

Кроме них, по требованию 10 прогнаны:
- test_acceptance_plank_exclude_lock.py;
- test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py;
- test_01m5edw6kd1escevrsv2wpnxap_file_level.py;
- (уже в списке выше) test_acceptance_plank_layout_refusal.py,
  test_task_component_places.py, test_01m4jd36367e5cg3gxdv429xte_amend_pult.py.

Все эти файлы прогнаны одной командой: `python3 -m pytest <файлы>
-p no:cacheprovider -p timeout -o timeout=300 -n 0`. Итог — в разделе «Результаты».
Долгоживущие файлы задачи прогнаны отдельно: 7 passed, 74 subtests passed.

## Результаты
- Адресный прогон 59 файлов выше (последовательно, `-n 0`, код c401a42a):
  `631 passed, 794 subtests passed in 681.75s`, код выхода 0.
- Долгоживущие файлы задачи: `7 passed, 74 subtests passed`.
- Планка (`artel.py plank-run 01M5N8ASJ63ZKF3M9ETC7A3P5V`): `4 passed`,
  код выхода 0.
- Карта: `python3 scripts/codebase_map.py` на c401a42a меняет только
  `built_at_sha`, содержимое свежее.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | раздел «Поиск подмен тестами» |
| 6 | 1, 2 (логика, argv, окружение, ключ кэша не тронуты) |
| 7 | 3 |
| 8 | долгоживущие файлы test_author'а (а–д) |
| 9 | 4 |
| 10 | 5 |
| 11 | 1–3 |

## Влияние на систему
- Поведение не меняется. Перенесённые объекты те же: `acceptance.X is
  plank_layout.Y`. Поэтому код и тесты, которые берут прежние имена у
  `acceptance`, работают как раньше. Публичные имена — алиасы тех же
  функций, закрытые имена остались.
- Есть одно отличие в связывании. Внутри `plank_layout.plank_layout`
  вызовы `exclude_layout`, `layout_mode`, `layout_root` и `drop_layout`
  теперь разрешаются по глобалам `plank_layout`, а не `acceptance`.
  Подмена `acceptance._exclude_layout` в тесте больше не повлияла бы на
  `_plank_layout`. Поиск показал, что таких подмен в `tests/` нет.
- Гейты, лимиты, тексты отказов, argv и окружение прогонов, ключ кэша
  итога не тронуты. Блок раннеров `acceptance.py:37–948` не тронут.
- `_durations_reader` перехватывает теперь и сбой импорта. Перехват
  прежний (`except Exception`), он уже покрывал запуск потока.
- Откат — revert коммита ветки задачи.

## Риски
- Новый вызывающий модуль может снова обратиться к закрытому имени
  `acceptance`. Это ловит долгоживущий тест AC-6.

## Предложения системе
- Сторож `conftest.py` роняет воркеры `pytest -n` при адресном прогоне
  большого списка файлов: «node down: Not properly terminated», «no tests
  ran», код выхода 0. Вывод — молчаливый ноль вместо отказа с причиной;
  легко принять за зелёный прогон.
