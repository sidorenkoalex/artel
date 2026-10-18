# Записка analyst

## Выяснено
- Итерация 2 (возврат из spec_gate, 14 решений Оператора). Решение 2 фиксирует путь выкладки `<long_lived_dir>/.artel-plank/<id>/acceptance_tests/`.
- `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`: `targets_of` (:323) берёт realpath цели ПОСЛЕ возврата plank-run, то есть после уборки выкладки. Поэтому символьная ссылка на `tasks/<id>/acceptance_tests` смысл проверки не спасает.
  - :345-348 (`assert_runs_file`) — проверка станет пустой.
  - :471 и :480 (`Ac6…::test_ac6_foreign_paths_and_plain_calls_keep_previous_outcome`, цель ext, lld под workdir: :151-152) — покраснеют: ожидают `[realpath tasks/<id>/acceptance_tests]`.
  - Ожидания не скалярные литералы, поэтому «Меняемое поведение» не подходит, нужен мандат. Решение 1 велит в этом случае эскалацию до SPEC.
- Прочие тесты argv планки pytest-own узнают её по подстроке "acceptance_tests" (profile_callers :269, :716) — останутся зелёными. Заголовок «планка: …» и `.git/info/exclude` тестами не закреплены.
- `long_lived_dir` в targets.yaml отсчитывается от корня копии (:85 `backend/tests` при `workdir: backend`).
- Полный набор pytest-own идёт без путей из workdir. Каталог с точкой pytest пропускает по умолчанию (norecursedirs), но проект может это переопределить.

## Не сработало
- Символьная ссылка как способ сохранить проверку :345-348: realpath считается после уборки.

## Где остановился
- Написал QUESTIONS.md (вопрос 1: мандат на правку теста, вопрос 2: от чего отсчитывается путь). SPEC.md не трогал.

## Чего не хватило
- Нет перечня тестов, которые разрешают цель pytest после возврата команды (realpath постфактум). Искал агентом по tests/.
