# Записка test_author — 01M5N8A5JBEQ15DCHDP95EBDZR

## Выяснено
- Все AC-1…AC-11 — свойство кода `_flush_pending`; планка — один долгоживущий файл
  `tests/test_01m5n8a5jbeq15dchdp95ebdzr_batch_flush.py` (16 методов, AC-4 — subTest по
  `note --flush`/`doc-commit --flush`). `acceptance_tests/` пуст — `plank-run` поэтому
  отказывает «планки нет»; файл гоняется `python3 -m pytest tests/<файл> …`.
- Песочница: `RealGitSandbox` + bare origin + `clone_artel_from_origin` (образец —
  `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`); `core.hooksPath` клона тест
  ставит сам на свой каталог хуков.
- Счёт push — хук `post-receive` origin (sha головы main на каждый push; чужие push
  отброшены по теме «чужая правка»). Отказ non-ff до origin не доходит, поэтому сдвиг
  origin — хук `post-commit` клона (чужой коммит из отдельного клона между построением и
  push → настоящий `[rejected] (fetch first)`), счёт попыток (AC-7) — хук `pre-push`
  клона (git зовёт его и на отклонённом push).
- Хуки — на Python (`sys.executable`): в PATH шага нет `cat`/`mkdir`, sh-хук молча
  не работал.
- На текущем коде: красны все, кроме AC-8 (последовательная отправка даёт тот же отказ
  STALE, один push) — причины красноты верные (лишние push, нет строк с sha, AC-4 —
  конфигурация уходит в порядке удержания раньше пакета, AC-7 — 9 попыток вместо 3).
- Валидация стабом: пакетный `_flush_pending` + параметр `ref` у `_build_*`/
  `_content_already_in_origin`/`_foreign_base_refusal` — 16/16 зелёные трижды; мутация
  «known первой = свежий origin» краснит оба AC-11. Стаб снят `git checkout`.
- preflight 01M5N8A5JBEQ15DCHDP95EBDZR — все проверки пройдены.

## Не сработало
- sh-хуки (нет coreutils в PATH шага). Bash шага ограничен: `ls`, `cd /tmp`, `2>&1`
  в heredoc отказаны; работают `python3 - <<EOF`, `grep`, git.

## Где остановился
- Шаг завершён: файл теста готов, preflight пройден.

## Чего не хватило
- Способ сдвигать origin «между построением и push» без шпиона на gitcmd искал дольше всего.
