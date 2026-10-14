## Выяснено
Статус шага: escalate. БД пульта подтверждает tests_writing. Прочитаны SPEC и существующий CanaryLifecycleTest целиком. Детерминированный опыт обнаружил продуктовый дефект раннего окна из AC-5: suite_alive=False, drive_alive=True, clone_exists=False, origin_exists=False; дочерний CLI завершился, stderr пуст. Зерно опыта 584974964. Это НЕ воспроизведение исходного CI TimeoutExpired: communicate завершился. Причина обоих CI остаётся неизвестной.

Точка: tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py, _CHILD, непосредственно перед `return drive`, после записи observation. Воздействие: `os.kill(os.getpid(), signal.SIGTERM)` внутри дочернего CLI. Отправка второго сигнала родителем отключена только в памяти на время launch_signalled. После выхода из подмены os.kill реальный alive обнаружил живой drive. Продуктовый Popen в orchestrator/canary.py:2333 находится до try защищённого wait (:2338); обработчик :2741–2744 бросает CanaryInterrupted. По SPEC требование 6 обнаружение продуктового дефекта требует возврата на согласование до продуктовой правки.

## Не сработало
Причинный воспроизводитель CI не получен; найден отдельный дефект раннего окна. Для него нельзя молча закреплять тестовую синхронизацию, исключающую окно. Стаб исправления не создавался: исполняемая планка не написана, работа остановлена по escalation-rules. В finally вызван штатный case.doCleanups(), включающий stop_suites; независимое доказательство ожидания всех потомков этим опытом не получено.

## Где остановился
В acceptance_tests/test_early_signal_escalation.py записан маркер AC-5: escalate. Остальные AC намеренно не размечены: test-authoring предписывает остановку при эскалации без ожидания остальных критериев. Код, существующие тесты и SPEC неизменны. Коммитов нет. plank-run выполнен: collected 0 items, exit 5 (только маркер эскалации). preflight выполнен: exit 1 — не покрыты AC-1–AC-4, AC-6–AC-7; маркер красноты, id, группа и долгоживущие файлы прошли. Предпроверка явно не проверяет перевод по escalate; результат не выдаётся за готовую планку. Проверено по orchestrator/fsm_advance.py:541–559: маркер escalate обрабатывается до отказа за неполную трассируемость.

## Чего не хватило
Для фиксации планки раннего окна нужен согласованный SPEC с решением о выявленном продуктовом дефекте. Причину исходного CI TimeoutExpired ещё предстоит устанавливать отдельно.

## Эскалация
- **Вопрос (блокирующий):** вернуть SPEC аналитику для обоснования минимальной продуктовой правки раннего окна и согласования зон? Варианты: (1) вернуть на анализ и согласование — рекомендуемый; (2) Оператор уточняет иной способ сохранения AC-5 без продуктовой правки. Дефолт при молчании: оставаться в escalated, продукт не менять, раннее окно не исключать.
- **Контекст:** SIGTERM перед возвратом Popen оставляет drive живым; выше приведены точка воздействия и наблюдения. SPEC AC-5 сохраняет это окно, требование 6 закрывает продуктовые зоны до согласования.
- **Блокирует:** фиксацию неизменяемой планки раннего окна и продолжение к разработчику при текущих зонах.

## Предложения системе
cat отсутствует в PATH (exit 127); чтение выполнено через pathlib и /bin/cat, что повторяет наблюдение аналитика. status <id> печатает весь список без отказа на лишний аргумент. Для разового инъекционного диагностического опыта нет команды пульта: выполнен python3 со штатной песочницей и подменой в памяти; полезна команда воспроизводимых диагностических опытов.

## Воспроизводимый опыт
Команда из рабочего каталога — python3 со следующим stdin (файлы репозитория не меняются):
```python
import importlib
import signal
from unittest import mock
m = importlib.import_module('tests.test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle')
case = m.CanaryLifecycleTest('test_ac1_sigterm_cleans_clone_origin_and_both_process_groups')
case.setUp()
try:
    injected = m._CHILD.replace('    return drive\n',
        '    os.kill(os.getpid(), signal.SIGTERM)\n    return drive\n')
    assert injected != m._CHILD
    with mock.patch.object(m, '_CHILD', injected), mock.patch.object(m.os, 'kill', return_value=None):
        state, stdout, stderr = case.launch_signalled(signal.SIGTERM)
    print('suite_alive', case.alive(state['suite_pid']))
    print('drive_alive', case.alive(state['drive_pid']))
    print('clone_exists', m.Path(state['clone']).exists())
    print('origin_exists', m.Path(state['origin']).exists())
    print('stdout', stdout, 'stderr', stderr)
finally:
    case.doCleanups()
```
