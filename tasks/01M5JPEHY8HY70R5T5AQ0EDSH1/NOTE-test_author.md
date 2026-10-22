# Записка test_author — 01M5JPEHY8HY70R5T5AQ0EDSH1

## Выяснено
- Долгоживущий файл: tests/test_01m5jpehy8hy70r5t5aq0edsh1_zone_dependency_start.py
  (AC-1..AC-7, AC-9); разовый: acceptance_tests/test_ac8_existing_tests_untouched.py
  (changed_paths() помощника пульта).
- Песочница — своя копия приёма ZoneQueueSandbox (импортировать её из чужого tests/test_*.py
  долгоживущему файлу нельзя: помощники только из tests/sandbox.py). Подслучаи — `self.case()`:
  subTest и закрытие (`done`) заведённых задач в finally, чтобы провал не засорял соседей.
- Занятость держателя в сценариях — запись `zone_lock.CLAIM_ACTION` актором developer.
- doctor: `doctor.check_zone_waits(conn)` → Check(name, status, detail); тест AC-7 ищет текст
  во ВСЕХ строках zone-waits (выходы могут быть отдельными строками), «взаимная блокировка с C»
  — в строке, где есть id A.
- Сейчас `merge_after` с id, которого нет в БД, роняет claim: `_ancestors` → `store.get_task`
  → SystemExit «Задача … не найдена». AC-2 требует, чтобы такая зависимость старт не держала.
- Временный стаб (обход зависимостей с task_exists, skip done/killed, `_reason` с (состоянием),
  блок в check_zone_waits через blocking_conflict + ancestors держателя): весь файл
  зелёный, test_zone_lock и zone_queue_start тоже. Все 6 мутаций AC-9 ловятся (каждая валит
  свой test_acN и test_ac9). Стаб откачен (`git checkout`).

## Не сработало
- Bash с `;`, `{"` и `grep -v` требует подтверждения; нет `ls`/`rm` в PATH — os.remove через python3.
- Запись в /tmp не разрешена.

## Где остановился
- Готово: plank-run зелёный (AC-8), preflight — все проверки пройдены.

## Чего не хватило
- Формат выходов doctor для взаимной блокировки SPEC не фиксирует побайтно — тест сверяет
  подстроки «answer <C>», «Зависимости мержа:», «zone-release <A>», «после перехода держателя в merge_gate».
