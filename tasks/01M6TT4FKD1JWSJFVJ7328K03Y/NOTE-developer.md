# Записка developer — 01M6TT4FKD1JWSJFVJ7328K03Y (итерация 2, после ревью 1)

## Выяснено
- R1-F2: `_ci_last_attempt` теперь возвращает третий элемент `unread` (`_pipeline_unread`: verdict unknown и нет заданий либо http_status); `_CiAttempt.unread`; `_ci_base_unfit` и `early_base_push` при unread не отправляют. Текст причины прежний (AC-14).
- R1-F1: новый файл `tests/test_ci_base_push_guard.py` (7 тестов, real_git, ~12 с) — force только когда все refspec в cbb, источник не предок, свежий origin/<base> vs локальная ссылка, хук, kill/уборка, unread.
- Стенд — копия подхода `tests/test_push_hook_stand.py` (там прецедент «долгоживущий минимум свойств разовой планки»).

## Не сработало
- Составные bash-команды с `;` и `|` иногда требуют подтверждения — по одной команде.

## Где остановился
- Итерация 2 завершена: мутации (6 шт.) красят свои тесты, затронутые тесты зелёные (96 + 45), plank-run 17 passed, карта регенерирована, реестр REVIEW размечен fixed, guard ок, PLAN ready.

## Чего не хватило
