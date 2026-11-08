# Записка test_author 01M6XHJH6EJ8D0BR5PRNGZAY8C

## Выяснено
- Все AC-1…AC-9 — в двух долгоживущих файлах; `acceptance_tests/` пуст (сбор с отсутствующей планкой — штатный случай `acceptance.collect`, `plank-run` при этом отказывает «планки нет» — это ожидаемо):
  - `tests/test_01m6xhjh6ej8d0br5prngzay8c_size_rules.py` — малый: AC-1…5, 7, 8, 9 на чистых функциях (`test_lint.size_findings`, `test_lint.heavy_sandbox_names`, `guard.long_lived_errors_from_files`, `targets.check`);
  - `tests/test_01m6xhjh6ej8d0br5prngzay8c_size_gate_paths.py` — средний: AC-6, шесть путей (tests_writing:643; amend :725 рабочая копия и --from-branch; amend :317 рабочая копия и --from-branch; preflight:213), залоченный файл на :317 в обоих режимах, RealGitSandbox из дерева проекта.
- Путь amend.py:317 — запись `components:` из двух компонентов: Vitest (правило планки не умолчание) и pytest с `long_lived: tests/test_<id>_<name>.py`, `paths: [^back/]`; компонент задачи — колонкой `zones="back/app.py"` (зона под `tests/` вычеркивается COMMON_ZONES).
- Тесты провалидированы временным стабом (удалён, `git checkout --` отслеживаемых файлов): 84 зелёных. Стаб показал: при пустых `sandbox_sources` перечень пуст — корни входят, только если определены в исходниках (AC-6).
- Предпроверка `preflight` — все проверки пройдены. Красный прогон: AttributeError/TypeError (малый) и «неизвестное подполе/поле size_marks» (средний).

## Не сработало
- Составные команды bash с `cd … ;`/`|` иногда требуют подтверждения.
- Заявка «база = голова после правки в --from-branch» на :317 неразличима случаем «залоченный без метки» — снята из докстринга.

## Где остановился
- Готово к сдаче. Карту `docs/codebase-map.md` не регенерировал — правка вне `tests/` откатывается пультом; её обновит разработчик.

## Чего не хватило
- Как вывести amend на :317 с Python-файлом (project_profile.plank_rule/long_lived_rule, targets._long_lived_shape_error) — искал дольше всего.
