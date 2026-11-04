# Записка test_author

## Выяснено
- Раскладка планки: AC-17 — разовый acceptance_tests/test_ac17_gh_calls_mandate.py (git show HEAD и DIFF_BASE через _pult, разбор ast); модульные свойства forge (AC-1,2,5..8,11..16) — tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py (75 методов); гейт мержа / verifying / mr-sync (AC-3,4,5,6,8,9,10,11,12,15,16) — tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_gate.py (21 метод, ~2 мин).
- Без кода задачи: 88 красных, 8 зелёных (AC-16 — держат прежнее поведение). Временный стаб (forge.github_call + 4 функции _GitHub + MergeRequest.already_exists + ASSIGNEE_BY_NAME + mr_assignee(policy, target) + ссылка при iid с причиной + ветви в _deliver_mr) — 96/96 зелёные; стаб откачен, ветка на 89698bf92.
- Признак «уже существует» тесты ищут как любое новое булево поле MergeRequest с умолчанием False (имя выбирает разработчик).
- Стенд гейта: url записи — путь голого origin на время git-операций стенда, https://localhost/<владелец>/<имя> — только на время approve/advance. Цвет CI ветки — подмена ci.branch_status.
- Инвариант 35: в tests/ адреса только localhost (guard ловит и f-строки с {HOST}); импорт gitcmd в долгоживущем файле — отказ, подмена hosting_token строкой пути.
- Загрузчик записи требует policy.weakening_scope/mutation_claim_scope; булеву mr_assignee отказывает — булево проверено прямым вызовом mr_assignee.

## Не сработало
- Карту docs/codebase-map.md не регенерировал: правку вне tests/ пульт откатывает у test_author; карту обновит разработчик.

## Где остановился
Готово: preflight пройдена, plank-run AC-17 красен по правильной причине.

## Чего не хватило
Дольше всего искал, как стенд гейта обходит белый список отправки при https-url записи (gitcmd.py:926-936) — решение «Стенд AC-3» в SPEC.
