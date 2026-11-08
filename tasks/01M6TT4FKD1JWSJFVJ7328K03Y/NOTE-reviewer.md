# NOTE-reviewer (итерация 1)

## Выяснено
- plank-run: 17 passed; долгоживущие файлы задачи + test_push_hook_units: 58 passed.
- Код по SPEC 1–9 соответствует. Вердикт — changes_requested.
- R1-F1 (major): ограничения отправки в ci_base_branch (force только туда,
  источник — предок свежего origin/<base>, проверка предка в хуке,
  неудаление при kill/уборке) стережёт только планка `Группа: разовый`.
  Временная мутация обеих проверок предка: tests/test_gitcmd_push_point.py,
  test_push_hook_units.py, test_push_hook_stand.py, *_ci_base_doctor.py —
  84 passed (не красные). Код возвращён.
- R1-F2 (minor): сбой pipeline_status (reason) = «задания нет» → отправка.

## Не сработало
- Составные bash-команды с `cd … && ls` отклоняются: используй абсолютные пути.

## Где остановился
- REVIEW.md записан (iteration 1, changes_requested).

## Чего не хватило
- Не было сразу видно, что планка помечена разовой: смотреть строку 3
  acceptance_tests/test_ci_base_push.py.
