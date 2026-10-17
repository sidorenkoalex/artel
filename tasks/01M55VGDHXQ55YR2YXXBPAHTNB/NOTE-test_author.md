# Записка test_author — 01M55VGDHXQ55YR2YXXBPAHTNB

## Выяснено
- Все AC-1…AC-8 — свойства кода → один долгоживущий файл tests/test_01m55vgdhxq55yr2yxxbpahtnb_zones_long_lived.py (8 методов test_ac<n>_…); acceptance_tests/ пуст (plank-run отвечает «планки нет» — ожидаемо; acceptance.collect при отсутствии каталога не блокирует).
- Сценарий через fsm.cmd_advance, песочница RealGitSandbox + make_project_repo (образец — tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py). Гейт зон стоит после _long_lived_manifest_refuses — без tests_locked_sha тот молчит даже при непрочитанном профиле.
- Подсказка (hint) гейта в журнал не пишется — только stdout «  дальше: …»; тесты читают её оттуда.
- У внешнего проекта «профиль не прочитан» при разрешённом контексте недостижим настоящим targets.yaml (resolve и profile_of оба зовут targets.target) → AC-5 подменяет публичный repo_context.profile_of (источник project_profile.decide, требование 1 SPEC). У артели resolve не читает targets.yaml → AC-8 — настоящий сломанный test_profile (нет long_lived_name).
- AC-1 держит и мутацию «расширение применено к артели»: профиль артели в песочнице объявляет каталог zl<слово> вне COMMON_ZONES, файл по шаблону там обязан отказываться прежним текстом.
- Прогон: красны только AC-2 (свой файл отказан гейтом зон) и AC-5 (причины профиля нет в тексте); остальные зелёные. Стаб в _zones_gate (is_long_lived по decide для не-артели + Decision.refusal в detail) — 8/8 зелёные; стаб откачен git checkout.
- preflight: все проверки пройдены.

## Не сработало
- `{7,40}` в регэкспе с str.format — KeyError; экранировал `{{7,40}}`.

## Где остановился
- Шаг завершён. docs/codebase-map.md не регенерировал: правку вне tests/ пульт у test_author откатывает.

## Чего не хватило
- Неочевидно, что hint отказа гейта не попадает в журнал (только печать в _base._run_gates).
