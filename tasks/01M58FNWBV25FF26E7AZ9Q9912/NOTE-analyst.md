# Записка analyst — 01M58FNWBV25FF26E7AZ9Q9912 (шаг 2, после аудита fail)

## Выяснено
- Аудит подтверждён по коду: `targets.load` → `yamlmini.mapping` (targets.py:111). Блочные списки отказываются (yamlmini.py:145), вложенные `[[`, кавычки в потоковом списке (yamlmini.py:178, :194); `{…}` становится строкой (:174). Отказы держит `tests/test_yaml_parsing.py::YamlMappingTest::test_unsupported_shapes_refuse_loudly` (стр. 190-201; подслучаи «блочный список» и «кавычки в списке»), `yamlmini.mapping` читают ещё roles.py, models.py, gates.py, knowledge_cards.py.
- Читатели `profile_of`: project_profile.decide :149, full_suite_limit :181, acceptance._task_own_profile :2393 (UNREAD/ABSENT → None → прежняя форма полного набора — обход), suite_run._profile_command :278.
- `mask_matches` (project_profile.py:46) — глоб с `*`/`**`, без `{a,b}`; у ADR в `tests` фронтенда `*.{test,spec}.{js,jsx}`.
- `_own_suite_result_key` (acceptance.py:2146) — без корня рабочей копии; отслеживаемые lock-файлы уже в `tree`.
- Решение шага: QUESTIONS.md (9 вопросов), SPEC.md не трогаю.

## Где остановился
- QUESTIONS.md записан, guard прогнан.

## Чего не хватило
- Что `targets.yaml` читает `yamlmini`, а не PyYAML, в первом шаге не проверила — это и стоило возврата.
