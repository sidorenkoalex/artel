"""AC-5: Завершение процесса-родителя (промежуточной оболочки),
запустившего отвязанный цикл, не останавливает сам цикл — он продолжает
шаги задачи после того, как породившая его оболочка уже завершилась.

Красен до реализации: сегодня `auto <id>` не порождает никакого
отдельного отвязанного процесса — она И ЕСТЬ единственный процесс,
несущий цикл. Запущенная через промежуточную оболочку (`sh -c "..."`),
она (вместе с самой оболочкой) исполняет цикл целиком в переднем плане:
`communicate()` вернёт управление только после ЕСТЕСТВЕННОЙ остановки
всего цикла (`natural_stall_timeout`), а не почти сразу, как ожидает
тест — начальные проверки этого файла (`pid is not None` после короткого
таймаута) покраснеют первыми.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox, natural_stall_timeout  # noqa: E402

IMMEDIATE_RETURN_TIMEOUT_SEC = 8.0


class Ac5SurvivesParentShellExitTest(DetachedCycleSandbox):

    def test_ac5_detached_cycle_survives_parent_shell_exit(self):
        """Запускает `auto <id>` не напрямую, а через промежуточную
        оболочку (`sh -c "python3 artel.py auto <id>"`) — так «родитель»
        (оболочка) и «вызывающая команда» (короткоживущий `auto`) не
        совпадают с самим тестовым процессом, и их совместное завершение
        наблюдаемо отдельно от жизни отвязанного цикла. Дожидается, пока
        оболочка (вместе со своим прямым потомком — короткоживущей
        командой `auto`) полностью завершится, затем проверяет, что
        отвязанный цикл (pid из вывода) остаётся живым и продолжает
        писать в свой лог уже ПОСЛЕ этого момента.

        Ловит мутацию: `start_new_session=True` (или его аналог) убран из
        `_launch_detached` — на большинстве платформ это не обрывает
        процесс немедленно при выходе родителя, но сессия остаётся той
        же, что и у оболочки; тест ловит именно НАБЛЮДАЕМОЕ следствие
        (живость и прогресс цикла спустя время ПОСЛЕ смерти оболочки),
        а не механизм ОС — красным он станет, если процесс к моменту
        проверки уже не найден живым.
        """
        task_id = self.new_task()

        shell_proc = self.spawn_via_shell("auto", task_id)
        try:
            out, _ = shell_proc.communicate(timeout=IMMEDIATE_RETURN_TIMEOUT_SEC)
        except Exception:
            shell_proc.kill()
            out, _ = shell_proc.communicate()
            self.fail(
                f"промежуточная оболочка не завершилась за "
                f"{IMMEDIATE_RETURN_TIMEOUT_SEC}с — похоже, цикл выполняется "
                f"в переднем плане, внутри самой оболочки:\n{out}")

        self.assertEqual(
            shell_proc.returncode, 0,
            f"вызывающая команда под оболочкой отказала: {out}")
        cycle_pid = self.extract_pid(out)
        self.assertIsNotNone(cycle_pid, f"вывод не назвал pid: {out!r}")
        self.track_pid(cycle_pid)

        # Оболочка и её прямой потомок (короткоживущий `auto`) к этому
        # моменту уже гарантированно завершились — `communicate()` дождался
        # именно этого. Отвязанный цикл обязан пережить их обоих.
        self.assertTrue(
            self.is_alive(cycle_pid),
            f"отвязанный цикл (pid={cycle_pid}) уже не жив сразу после "
            f"завершения породившей его оболочки")

        log_path = self.root / ".artel" / "logs" / f"{task_id}-auto-1.log"
        size_at_shell_exit = log_path.stat().st_size if log_path.exists() else 0
        progressed = self.wait_until(
            lambda: (log_path.exists()
                    and log_path.stat().st_size > size_at_shell_exit),
            timeout=natural_stall_timeout())
        self.assertTrue(
            progressed,
            f"цикл (pid={cycle_pid}) не продвинулся дальше своего "
            f"состояния на момент смерти оболочки — лог {log_path} не "
            f"вырос: {self.journal_text(task_id)}")


if __name__ == "__main__":
    unittest.main()
