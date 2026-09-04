"""AC-12: `doctor` различает по pid и последней журнальной записи цикла
три состояния: «цикл жив» (pid жив, свежий heartbeat lease), «цикл
завершился штатно» (в журнале задачи есть запись о штатном завершении
цикла) и «цикл умер» (pid мёртв, записи о штатном завершении в журнале
нет).

Тест намеренно не привязан к точному имени/тексту НОВОЙ проверки
doctor — только к УЖЕ существующей `doctor.check_leases` (`orchestrator/
doctor.py`, FAIL-строка `"<id>: lease сессии ... мёртв (...)"`, не меняется
этой задачей): различие в том, что задача с мёртвым pid, чей цикл вышел
ШТАТНО (через `stop`), НЕ должна попасть в этот FAIL-список — если бы
она в него попадала, «умер» и «завершился штатно» были бы неотличимы
именно там, где Оператор их и читает. «Задача B» и «задача C» ниже
устроены СИММЕТРИЧНО (тот же факт: процесс мёртв) — единственная
разница между ними по построению это КАК он умер (`stop` vs SIGKILL), а
единственный наблюдаемый эффект, которого требует AC-12, — доктор
обязан развести их по разным корзинам.

Красен до реализации: команды `stop` нет (задача B недостижима так, как
задумана этим тестом), а лог/lease не отвязаны от вызывающей команды —
тест падает уже на старте (см. AC-1/AC-9).
"""
import signal
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402


class Ac12DoctorThreeStatesTest(DetachedCycleSandbox):

    def _launch(self, task_id: str, sleep_sec: int):
        self.set_claude_sleep(sleep_sec)
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", task_id, timeout=5.0)
        self.assertFalse(
            timed_out, f"[{task_id}] auto не вернулась вовремя:\n{out}")
        self.assertEqual(rc, 0, out)
        pid = self.extract_pid(out)
        self.track_pid(pid)
        self.assertIsNotNone(pid, f"[{task_id}] вывод не назвал pid: {out!r}")
        started = self.wait_until(
            lambda: any(r["action"] == "agent run started"
                       for r in store_task_steps(task_id)),
            timeout=5.0)
        self.assertTrue(started, f"[{task_id}] шаг не начался")
        return pid

    def test_ac12_doctor_tells_alive_finished_and_dead_apart(self):
        """Заводит три задачи self/артели в `in_dev` и три отвязанных
        цикла с одинаковым фактом «процесс шага мёртв» у двух из трёх, но
        разной ПРИЧИНОЙ смерти: A остаётся живым весь тест; B получает
        `stop` и доигрывает шаг до штатного выхода; C убит напрямую
        (SIGKILL, в обход `stop`/`kill`) — реальный обрыв. Единственный
        прогон `doctor` обязан НЕ пометить B как мёртвого (в отличие от
        C), несмотря на то, что оба процесса к моменту прогона мертвы.

        Ловит мутацию: doctor решает «жив/мёртв» ТОЛЬКО по pid, не
        заглядывая в журнал за записью о штатном завершении, — тест
        покраснеет, потому что задача B попадёт в тот же FAIL-список
        «lease ... мёртв», что и C.
        """
        task_a = self.new_task_in_dev("Git-фиксация A (жив)")
        pid_a = self._launch(task_a, sleep_sec=40)

        task_b = self.new_task_in_dev("Git-фиксация B (штатно)")
        pid_b = self._launch(task_b, sleep_sec=3)
        stop_out, stop_rc, _, _, stop_timed_out = self.run_cli(
            "stop", task_b, timeout=10.0)
        self.assertFalse(stop_timed_out, f"[{task_b}] stop зависла")
        self.assertEqual(stop_rc, 0, f"[{task_b}] stop отказала: {stop_out}")
        died_b = self.wait_until(lambda: not self.is_alive(pid_b),
                                 timeout=10.0)
        self.assertTrue(died_b, f"[{task_b}] цикл не завершился после stop")

        task_c = self.new_task_in_dev("Git-фиксация C (обрыв)")
        pid_c = self._launch(task_c, sleep_sec=40)
        self.kill_pid(pid_c, signal.SIGKILL)
        died_c = self.wait_until(lambda: not self.is_alive(pid_c),
                                 timeout=10.0)
        self.assertTrue(died_c, f"[{task_c}] процесс не убит SIGKILL")

        self.assertTrue(self.is_alive(pid_a),
                        f"[{task_a}] должен был остаться живым")

        self.set_claude_sleep(2)
        doctor_out, doctor_rc, _, _, doctor_timed_out = self.run_cli(
            "doctor", timeout=60.0)
        self.assertFalse(doctor_timed_out, f"doctor зависла:\n{doctor_out}")

        dead_lines = [ln for ln in doctor_out.splitlines() if "мёртв" in ln]
        dead_text = "\n".join(dead_lines)

        self.assertTrue(
            any(task_c in ln for ln in dead_lines),
            f"doctor не пометил реально оборванный цикл C как мёртвый:\n"
            f"{doctor_out}")
        self.assertFalse(
            any(task_b in ln for ln in dead_lines),
            f"doctor пометил штатно завершившийся цикл B как мёртвый — "
            f"«умер» и «завершился штатно» неразличимы:\n{dead_text}")
        self.assertFalse(
            any(task_a in ln for ln in dead_lines),
            f"doctor пометил ЖИВОЙ цикл A как мёртвый:\n{dead_text}")


def store_task_steps(task_id: str) -> list:
    from orchestrator import store
    return store.task_steps(store.db(), task_id)


if __name__ == "__main__":
    unittest.main()
