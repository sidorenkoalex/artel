"""Приёмочные тесты AC-5, AC-6 (SPEC 01M2B6K02YVJBWE1JDWP85EJH0):
`pin.cmd_pin_update(sha)` принимает зелёный прогон на истории именно
`<sha>` даже когда прогон на текущем HEAD главной копии (пине)
красный/отсутствует; отказ, когда подходящего прогона на `<sha>` нет,
называет сам этот sha и команду `python3 orchestrator/artel.py canary
--k 1 --sha <sha>` для его получения.

`orchestrator/pin.py::cmd_pin_update` уже сегодня считает возраст
относительно ПЕРЕДАННОГО `sha` (`canary.merges_since_last_green_run(
conn, sha)`, не `gitcmd.head_sha()`) — AC-5 здесь прежде всего guard
против РЕГРЕССИИ именно к старому дефекту этой задачи (SPEC/Контекст:
канарейка гонялась на коде пина), которую эта задача устраняет в
`canary.py`: если при правке `pin.py` под AC-6 (текст отказа) кто-то
заодно вернёт сравнение к `gitcmd.head_sha()`, `test_ac5_...` обязан
покраснеть.

Красен до реализации: `test_ac6_...` — единственный, который
гарантированно красный на сегодняшнем `pin.py` (строка отказа не несёт
`--sha <sha>`, только `--k 1`); `test_ac5_...` может оказаться зелёным
уже сегодня (это не дефект теста — он фиксирует то самое поведение,
которое AC-5 требует НЕ ломать, см. абзац выше и `test-authoring`:
«краснота — объяснённая, не по умолчанию»).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, pin, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import TargetShaCanarySandbox  # noqa: E402


class PinUpdateAcceptsGreenOnTargetShaTest(TargetShaCanarySandbox):

    def _merge(self, name: str) -> str:
        self.checkout(name, create=True)
        (self.root / f"{name}.txt").write_text("x\n", encoding="utf-8")
        self.git("add", f"{name}.txt")
        self.git("commit", "-q", "-m", f"работа {name}")
        self.checkout(config.MAIN_BRANCH)
        self.git("merge", "--no-ff", "-q", "-m", f"merge {name}", name)
        sha = self.head_sha()
        self.git("push", "-q", "origin", config.MAIN_BRANCH)
        return sha

    def _insert_run(self, main_sha: str, verdict: str) -> None:
        conn = store.db()
        store.insert_canary_run(
            conn, f"run-{main_sha[:7]}", "t", f"01{main_sha[:7]}", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=main_sha, verdict=verdict)

    def test_ac5_accepts_green_run_on_target_sha_when_pin_head_has_no_run_at_all(self):
        """Пин (HEAD главной копии) не несёт НИ ОДНОГО прогона канарейки
        (журнал пуст на нём) — но целевой `<sha>`, на который двигают
        пин, несёт свежий зелёный прогон. `pin.cmd_pin_update(sha)`
        обязан пройти: пин продвигается до `sha`.

        Ловит мутацию: guard возвращается к старому источнику возраста
        (`gitcmd.head_sha()` пина вместо переданного `sha`) — на пине
        журнал пуст, возраст оказался бы `None`, и `pin-update` отказал
        бы вместо того чтобы принять целевой прогон.
        """
        target = self._merge("m1")
        self._insert_run(target, "green")

        pin.cmd_pin_update(target)

        self.assertEqual(self.head_sha(), target)

    def test_ac5_accepts_green_run_on_target_sha_even_when_pin_head_run_is_red(self):
        """На пине (старом HEAD главной копии) есть прогон, но КРАСНЫЙ;
        на целевом `<sha>` — свежий зелёный. `pin-update` всё равно
        обязан пройти, ориентируясь на прогон целевого `sha`, не пина.

        Ловит мутацию: guard берёт «последний прогон вообще» (без
        различения, на каком именно sha он висит) вместо прогона,
        привязанного к целевому `sha`, — красный прогон пина ложно
        заблокировал бы обновление, для которого целевой sha уже зелёный.
        """
        stale_pin_sha = self.head_sha()
        self._insert_run(stale_pin_sha, "red")
        target = self._merge("m1")
        self._insert_run(target, "green")

        pin.cmd_pin_update(target)

        self.assertEqual(self.head_sha(), target)

    def test_ac6_refusal_names_the_target_sha_and_the_canary_command_with_sha_flag(self):
        """Ни один зелёный прогон не покрывает целевой `sha` — отказ
        `pin-update` называет сам этот `sha` и команду `python3
        orchestrator/artel.py canary --k 1 --sha <sha>` для его
        получения (не просто `canary --k 1` без `--sha`).

        Ловит мутацию: текст отказа сохраняет старую команду без `--sha
        <sha>` — Оператор получил бы команду, прогоняющую канарейку на
        случайном шаблоне БЕЗ привязки к нужному целевому sha, то есть
        снова рискующую не дать зелёный прогон именно на нём.
        """
        target = self._merge("m1")

        with self.assertRaises(SystemExit) as ctx:
            pin.cmd_pin_update(target)

        message = str(ctx.exception)
        # Sha в тексте отказа может быть напечатан полностью или
        # сокращённо (`sha[:7]` — существующий приём этого же сообщения,
        # см. докстринг модуля); критерий не фиксирует формат буквально.
        self.assertTrue(target in message or target[:7] in message, message)
        self.assertTrue(
            f"canary --k 1 --sha {target}" in message
            or f"canary --k 1 --sha {target[:7]}" in message,
            message)


if __name__ == "__main__":
    import unittest
    unittest.main()
