# Записка spec_auditor

## Выяснено
- Аудит SPEC sha b91c7795 (после второго возврата): Решения №1 и №2 отражены, verdict pass.
- Факты: fsm.py:613-626, 1834, 1870-1871, 547-564; fsm_advance.py:94-124; canary.py:1445-1488; answer.py:626 — единственный update_task (zones_extension).
- Возврат канарейки — анкер рубежа (detail не в auto._ESCALATED_RETURN_DETAILS, auto.py:382).
- Опыт: функция с условным вызовом, подменённая в памяти, — 4 файла тестов 139 passed; единственный красный test_origin_spec_lives... — из-за отсутствия докстринга у подмены. Докстринг с номером 01M1NEEWH5K1XPFRDGRMPYSBXJ сохранять.

## Не сработало
- Запись в /tmp отклонена; временный файл писал в каталог документов и убирал task-rm.

## Где остановился
- SPEC-AUDIT.md: verdict pass, status ready.

## Чего не хватило
- —
