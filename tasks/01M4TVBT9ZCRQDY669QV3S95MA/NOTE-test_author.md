# Записка test_author — 01M4TVBT9ZCRQDY669QV3S95MA

## Выяснено
- Планка: долгоживущие tests/test_01m4tvbt9zcrqdy669qv3s95ma_min_uses_field.py
  (AC-1, AC-2 через публичный `targets.check`) и
  tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py (AC-3…AC-17,
  `ConnRealGitSandbox` + `make_project_repo`, команда через `artel.main()`
  с окружением Оператора); разовый acceptance_tests/test_ac18_tests_added.py
  (опорные слова заявок требования 7 в tests/ ветки, targets.yaml не в диффе).
- Вход без задачи тест ищет по форме среди публичных функций
  `reference_cache` (a, b, *, reason, sha, task_id=None).
- Стаб реализации (targets/reference_cache/projects/artel) — все зелёные,
  10 мутаций пойманы; стаб откачен (`git checkout`), дерево чистое кроме двух
  новых файлов tests/.
- Зелёные с рождения: AC-2, AC-5, прежний get_reference в AC-6, AC-15, AC-18.

## Не сработало
- `store.steps_of_action` не отдаёт колонку `target` — в тесте прямой SELECT.
- В AC-3 старые файлы use/ оставались в дереве при смене порога — `git rm -r use`.

## Где остановился
plank-run зелёный, preflight пройден. Шаг завершён.

## Чего не хватило
Формат сводки команды SPEC не фиксирует — тест ищет числа/слова в выводе,
порог и источник — на одной строке.
