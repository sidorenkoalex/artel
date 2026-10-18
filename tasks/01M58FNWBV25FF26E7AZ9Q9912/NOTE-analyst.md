# Записка analyst — 01M58FNWBV25FF26E7AZ9Q9912 (шаг 3, после ANSWER-1)

## Выяснено
- ANSWER-1: часть 1 = схема `components:` (отображение имя→поля, без правки yamlmini), `profile_of` (несколько компонентов → UNREAD с фразой G1б), отказ `_task_own_profile` на UNREAD, выбор компонентов, идентификатор теста. doctor и ключ кэша — вынесены в G1а-2. Рамка $45. Зоны: targets.py, project_profile.py, repo_context.py, acceptance.py, tests/.
- `_task_own_profile` зовут вне зон: pull.py:665, plank_run.py:220, amend.py:548/723, а внутри acceptance.py — :1298 (`drop_from_code_copy`) и :2372 (`acceptance_suite`). Форма отказа для внешних вызывающих — вопрос PLAN; в SPEC это в «Не входит» + эскалация при нужде.
- Краснеет `tests/test_acceptance_suite_profile.py::AcceptanceSuiteProfileTest::test_own_profile_passed_other_profiles_keep_old_call` (подслучай «не прочитан» ждёт прежний вызов `full_suite`). Это смена вида, не пара литералов — в «Меняемое поведение» записано свободным текстом без строки `- `, иначе approve откажет.
- yamlmini: дубликат ключа молча перезаписывается — уникальность имени компонента проверке недоступна без правки yamlmini (в «Не входит»).
- Компонент с одним элементом без обязательных подполей test_profile → UNREAD с причиной (иначе `Profile.from_values` даёт KeyError в `decide`).

## Где остановился
- SPEC.md (status: ready, 10 требований, AC-1…AC-9, budget 45) записан, guard ок; QUESTIONS.md удалён (через python — `rm` в шаге не разрешён).

## Чего не хватило
- Правила, как оформить в «Меняемое поведение» смену вида утверждения по прямому решению Оператора: формат раздела этого не принимает.
