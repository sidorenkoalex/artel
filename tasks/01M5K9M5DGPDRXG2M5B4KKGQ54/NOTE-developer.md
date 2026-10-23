## Выяснено
- Реализовано: pin.py `_wait_for_main_ci_green` + `wait_ci`, artel.py `_cmd_pin_update`
  (разбор формы до cmd_pin_update), справка; карта регенерирована.
- Долгоживущий файл задачи 9/9 зелёный, соседние тесты pin/main_ci/role_refusal зелёные.
- Мутация `>=`→`>` в потолке ловится AC-5.

## Не сработало
- `ls` в Bash нет в PATH; `sed`/`grep` работают.

## Где остановился
- PLAN.md status: ready, guard прогнан.

## Чего не хватило
- Ничего.
