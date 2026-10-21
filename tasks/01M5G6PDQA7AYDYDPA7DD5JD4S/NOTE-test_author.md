# Записка test_author

## Выяснено
- ЭСКАЛАЦИЯ AC-7, AC-8: на macOS (машина пульта) select.poll и kqueue (selectors.DefaultSelector)
  НЕ сообщают EOF именованного канала (FIFO) — проверено python3 -c: после закрытия писателя
  poll/kqueue пусты, select.select готовность видит; у безымянного pipe EOF виден всеми.
  test_ac9_timeout_kills_group_not_green ждёт EOF FIFO → со стабом (poll, перенос на 1100) он
  локально красен «потомок раннера пережил таймаут». Вопрос с вариантами — пометки в
  acceptance_tests/test_wait_function.py; черновики тестов — методы draft_ac7_…/draft_ac8_…
  (не собираются), прогнаны стабом: draft_ac7 зелёный, draft_ac8 красен именно этим.
- Раскладка: долгоживущий tests/test_01m5g6pdqa7aydydpa7dd5jd4s_store_db_fds.py — AC-1…AC-4;
  разовые: test_store_mechanism (AC-5, AC-6), test_wait_function (AC-9, AC-10; AC-7/8 escalate),
  test_two_sided_seed (AC-11, AC-12), test_kill_silent (AC-13…AC-17), test_plan_proof (AC-18); общий код — _util.py.
- Мутации AC-14…AC-17 — во временной копии рабочего каталога (git ls-files -co, без tasks/) с
  текстовой правкой orchestrator/cleanup.py / ci.py; зонд pytest (_util.PROBE, -p) пишет журнал
  (Silence.limit, присваивания config.GH_TIMEOUT_SEC по узлам, fd функции ожидания) и в мутантах
  урезает Silence.limit до 8 с. Узел перехвата AC-14 = узел SilentHostingTest с GH_TIMEOUT_SEC из
  7…300 (≠ исходного, ≠ 2); сквозной = узел с GH_TIMEOUT_SEC = 2.
- Стаб-валидация (стаб удалён, git status чист кроме долгоживущего файла): store (учёт + getrefcount − 2)
  — долгоживущий файл и test_store_mechanism зелёные; two_sided — зелёный; kill_cleanup — 14/14
  зелёные (~130 с); wait — AC-9, AC-10 зелёные; AC-18 — проверен подставным текстом PLAN.
- PYTHONPATH внутреннего прогона без корня кода: иначе вложенный pytest two_sided берёт пакет tests корня.
- Учёт утверждений гейтом: guard.test_assertions(src, path, guard.TestModules(load)) + changed_test_assertions.

## Не сработало
- Составные bash-команды и rm требуют одобрения — по одной команде / python3 -c.
- poll/kqueue на FIFO под macOS (см. выше).

## Где остановился
- Шаг 2 (после ANSWER-3, вариант A) завершён: эскалации AC-7/AC-8 сняты, draft_* заменены тестами
  test_ac7_…_off_darwin, test_ac8_…_off_darwin; AC-9 проверяет режим «вне Darwin» + зелёный «Darwin».
- Зонд (_util.PROBE): ARTEL_PROBE_PLATFORM подменяет sys.platform при загрузке зонда (до conftest);
  в режиме linux select.poll и селекторы заменены эмуляцией (os.dup на низкий fd + настоящий select —
  EOF FIFO виден и на Darwin); внутри функции ожидания пишутся события select/poll.
- Стаб (sys.platform-ветка: darwin → select.select, иначе DefaultSelector; dup ≥1100 вне Darwin)
  — 4/4 зелёные за ~7 с; мутации «всегда poll» и «всегда select.select» краснят AC-7/8(/9).
  Стаб удалён, git status чист. preflight пройден.

## Чего не хватило
- Знания, что на Darwin poll/kqueue не видят EOF FIFO — SPEC (требования 5–6) его не учитывает.
