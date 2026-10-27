# Записка test_author — 01M5XZ9Z68V75VXF5Z66C708T4

## Выяснено
- Планка (acceptance_tests/, разовые): test_ac5_ac8_awaiting_push.py (AC-5..8), test_ac18_target_human_kill.py (AC-18, 8 состояний × gitlab/github), test_ac16_epic_supervision.py (AC-16, читает auto._epic_view — статус надзора публично не виден), test_ac20_existing_tests_untouched.py (AC-20: дифф ветки меняет из существующих tests/ только файлы мандата треб. 22; зелёность набора держит пульт).
- Долгоживущие tests/test_01m5xz9z68v75vxf5z66c708t4_*.py: delivery_policy (AC-1, AC-2), no_role_lists (AC-3), awaiting_commands (AC-4, AC-9, AC-17), awaiting_holds (AC-10, AC-11, AC-12, AC-19), awaiting_views (AC-13, AC-14, AC-15).
- Почему AC-5..8 и AC-18 в планке: guard запрещает долгоживущим файлам импорт orchestrator.gitcmd и git через subprocess (scripts/guard.py SIGN_GIT_MODULE/SIGN_GIT_CALL); ещё инвариант 35 — адреса в tests/ только localhost.
- Причина отказа отправки (AC-5..8) тест ждёт со словом `awaiting_human` или «ждёт людей проекта»; проверяется для проектов operator и target-human через gitcmd.in_repo клона.
- AC-2 «толкует как id»: тест независим от формы — N и "N" дают одно значение, не строку "N"; "alice" → "alice".
- Ссылка MR пишется store.update_task(mr_iid=, mr_url=); тесты ищут mr_url в выводе board (--md/--html/--json), status, report.html, watch (строка при переходе в awaiting_human, --until + patch_sleep).
- Валидация стабом сделана (стаб в orchestrator/ снят git checkout): все 33 долгоживущих и 26 тестов планки зелёные; мутация «старый вид записи не узнаётся» красит in_dev-legacy. Стаб поймал 2 дефекта тестов (ключи RENDERERS «--md»; insert_epic без commit → database locked) — исправлены.
- Сейчас: планка 25 красных/1 зелёный (AC-20); долгоживущие 27 красных/6 зелёных с рождения (AC-3 ×3, AC-11 false, AC-12, AC-17). preflight — все проверки пройдены.

## Не сработало
- Bash без cat/ls/mv/sed -i; составные python-heredoc с «{"» блокируются — переносы файлов через python3 -c os.replace.

## Где остановился
- Готово, шаг сдаётся.

## Чего не хватило
- Правила долгоживущих файлов (запрет gitcmd) нашёл только в scripts/guard.py после написания — стоило начать с preflight.
