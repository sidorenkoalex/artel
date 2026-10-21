# Записка developer

## Выяснено
- Реализовано всё по SPEC: store.py (учёт _TRACKED + эталон-замер), tests/fd_wait.py + tests/test_fd_wait.py,
  report_outcome/timeout_integrations на wait_readable, two_sided (location_literals, помощник, тест на зерне),
  kill_cleanup (флаг Silence.expired, gh_slept, сценарий перехвата test_ac6_limit_arguments_follow_gh_timeout).
- Планка: 22/23 зелёные, test_plan_proof красен только потому, что PLAN.md ещё не в ссылке документов
  (логика теста на тексте PLAN.md проверена локально — зелёная).
- Замер fd после report_outcome при gc.disable(): до починки 4→310, после 4→16.
- Без урезания срока молчания мутация «предел пуша числом 60» сквозной метод не краснит (60 < 75 с) — её держит
  сценарий перехвата; так и написано в описании и PLAN.

## Не сработало
- Bash: ls/cat/sleep/sed -i/составные команды недоступны. pytest.main в процессе отвергает сторож conftest.

## Где остановился
- Запущен suite-run №1; после отчёта — status: ready в PLAN.md.

## Чего не хватило
- Команды пульта «прогон файла с замером ресурсов» (замер fd пришлось делать временным плагином).
