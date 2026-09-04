"""AC-14 + AC-15 (SPEC.md), общая песочница (обе про одну операцию —
откат пина): буквальный синтаксис из ADR-0013 ч.3, процитированный в
SPEC требовании 14: `pin --to <sha>` — по умолчанию (без явного sha)
откатывает на предыдущий зелёный по журналу канарейки.

AC-14. `pin --to <sha>` возвращает запущенную версию пульта на
указанный коммит; без явного `<sha>` — откатывает на предыдущий
зелёный по журналу канарейки коммит.

AC-15. Каждый откат пина журналируется с прежним и новым sha и
причиной; main пульта при откате не изменяется.

«Зелёный прогон на sha0» сеется настоящим `canary --k 1` (тем же
приёмом, что `test_ac12_ac13_pin_gate_and_doctor_trigger.py` — интеграция,
не догадка о схеме журнала). Перевод локального HEAD пульта на более
свежий sha ПЕРЕД проверкой отката сделан сырым git (`fetch`+`merge
--ff-only` напрямую, в обход `pin.cmd_pin_update`/CLI): это только
подготовка сцены, не предмет AC-14/AC-15, а обходить её приходится
именно так — гейт AC-12 («без свежей канарейки pin-update отказывает»)
мог бы отказать самой команде `pin-update`, если бы подготовка сцены
шла через неё (N, `config.CANARY_PIN_STALE_MERGES`, соседней задаче
AC-12/13 неизвестен заранее и это не предмет ЭТОГО теста).

Красен до реализации: `pin --to` — команды `pin` нет вовсе в таблице
`orchestrator/artel.py::main` (есть только `pin-update`, не `pin`) —
`run_pin_rollback` (через `run_cli`, см. `_sandbox.py`) возвращает
текст с «Неизвестная команда pin», HEAD `self.root` не двигается,
первая содержательная проверка (`head_after == sha0`) падает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox  # noqa: E402

POOL_TEMPLATES = {
    "malaya-pravka.md": "Добавь маленькую синтетическую фичу X с тестами.",
}


class PinRollbackTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self.write_pool_templates(POOL_TEMPLATES)
        self.sha0 = self.origin_main_sha()
        out = self.run_canary_pool(1)
        self.assertNotIn(
            "[SystemExit]", out,
            f"сеющий прогон канарейки на sha0={self.sha0} не выполнился:\n{out}")

        # «Запущенная версия» пульта продвинута дальше зелёного sha0 —
        # сырым git, в обход pin-update/её собственного гейта (см.
        # докстринг модуля).
        self.sha_far = self.advance_origin_main(3)
        self._git("fetch", "-q", "origin", "main")
        self._git("merge", "-q", "--ff-only", self.sha_far)
        self.assertEqual(self._git("rev-parse", "HEAD").stdout.strip(),
                         self.sha_far)

    def test_ac14_explicit_sha_rolls_back_and_ac15_journals_old_new_and_reason(self):
        """`pin --to <sha0>` — HEAD `self.root` возвращается на sha0 (не
        на что-то ещё); журнал (`store.task_steps`/`store.journal` —
        синтетический task_id команды пина, тот же приём, что
        `config.PIN_UPDATE_JOURNAL_TASK_ID` у `pin-update`) несёт и
        прежний (`sha_far`), и новый (`sha0`) sha, и текст причины
        отката (не пустая строка).

        Ловит мутацию: разработчик делает откат (HEAD действительно
        двигается), но не журналирует ни одного из двух sha или пишет
        пустую причину (SPEC требование 15 — «с прежним и новым sha и
        причиной», не просто факт отката) — тогда объединённый текст
        журнала не содержит обеих подстрок sha.
        """
        from orchestrator import config, store

        out = self.run_pin_rollback(self.sha0)
        self.assertNotIn("[SystemExit]", out, out)

        head_after = self._git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(
            head_after, self.sha0,
            f"HEAD пульта после `pin --to {self.sha0}` — {head_after}, "
            f"ожидался {self.sha0}")

        conn = store.db()
        steps = store.task_steps(conn, config.PIN_UPDATE_JOURNAL_TASK_ID)
        journal_text = "\n".join(
            f"{r['actor']} | {r['action']} | {r['detail']}" for r in steps)
        self.assertIn(self.sha_far, journal_text,
                     f"журнал отката не несёт прежний sha {self.sha_far}: "
                     f"{journal_text}")
        self.assertIn(self.sha0, journal_text,
                     f"журнал отката не несёт новый sha {self.sha0}: "
                     f"{journal_text}")
        rollback_entries = [r for r in steps
                            if self.sha0 in (r["detail"] or "")
                            and self.sha_far in (r["detail"] or "")]
        self.assertTrue(rollback_entries, journal_text)
        last = rollback_entries[-1]
        reason_text = (last["detail"] or "") + (last["action"] or "")
        # Причина — что-то СВЕРХ голого факта двух sha: вычитаем оба
        # sha из текста и проверяем, что не пусто.
        stripped = reason_text.replace(self.sha0, "").replace(self.sha_far, "")
        self.assertTrue(
            stripped.strip(),
            f"запись отката несёт только два sha, без текста причины: "
            f"{last}")

    def test_ac15_rollback_does_not_touch_origin_main(self):
        """После отката main пульта (`origin`, bare-remote этой
        песочницы) стоит на том же sha, что и до отката, — откат
        двигает только ЛОКАЛЬНЫЙ HEAD запущенной версии пульта.

        Ловит мутацию: реализация отката делает `git push`/иным образом
        двигает `origin` (например, копирует логику `pin-update`
        «fetch + merge» не глядя и путает направление, приняв откат за
        обычное продвижение вперёд) — `self.origin_main_sha()` после
        отката отличался бы от значения до него.
        """
        origin_sha_before = self.origin_main_sha()

        out = self.run_pin_rollback(self.sha0)
        self.assertNotIn("[SystemExit]", out, out)

        origin_sha_after = self.origin_main_sha()
        self.assertEqual(
            origin_sha_before, origin_sha_after,
            f"main пульта (origin) изменился при откате пина: было "
            f"{origin_sha_before}, стало {origin_sha_after}")


if __name__ == "__main__":
    unittest.main()
