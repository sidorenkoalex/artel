## Выяснено
- Итерация 2 (после fail аудита): исход — батч QUESTIONS.md, SPEC.md не трогаю.
- `tools` до `Profile` не доходят: `repo_context.profile_of` (repo_context.py:171-172) отдаёт только `targets.PROFILE_FIELDS` (targets.py:44-59), `tools` — только в `COMPONENT_FIELDS` (targets.py:103). Внутри зоны можно дозаполнить в `project_profile.decide` (project_profile.py:143-151) через `components(target)` — но ТЗ сужает зону до «только поле tools» → вопрос 1.
- Тест равенства `tests/test_01m58fnwbv25ff26e7az9q9912_components.py:657-694` — фикстура БЕЗ `tools`: различитель «непустые tools» с ним совместим, признак происхождения — нет → вопрос 2.
- Ключ базы: suite_run.py:521-523 зовёт `suite_result_key(tree, command, base=True)` без корня; отслеживаемые блокировки уже в `tree`, игнорируемых в коммите нет → вопрос 3 (дефолт: в base-ключе только tools).
- Запись, проходящая `targets.load`, но роняющая `full_suite_limit`: единственный компонент без обязательного подполя (UNREAD) — годится для второй половины AC-1 → вопрос 4.
- Ключ `full_suite` (acceptance.py:2265) тоже зовёт `full_suite_limit` — у записи с несколькими компонентами прогона нет до G1б.

## Не сработало
- `ls` в оболочке нет (zsh: command not found) — пользоваться Read/grep.

## Где остановился
- QUESTIONS.md записан (6 вопросов, дефолты: 1-A, 2-A, 3-A, 4-A, 5-A, 6-A), guard — ок. SPEC.md не тронут. После ANSWER: переписать SPEC по ответам и удалить QUESTIONS.md.

## Чего не хватило
- Формы строки `BACKEND_RE` в ci.yml sled (клон sled закрыт на чтение) — вопрос 5.
