"""AC-5 (tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md): базу определить нельзя
(итерация 1, либо sha кодовой ветки в записи журнала не распознан) —
`review.review_package` строит diff к `config.MAIN_BRANCH` целиком (как и
сейчас), А ТЕКСТ ПАКЕТА называет причину отсутствия базы.

Первая половина требования (diff к `config.MAIN_BRANCH` на пустом
`prev_sha`) уже покрыта существующим `tests/test_review_package.py::
IncrementalReviewPackageTest.test_missing_prev_sha_falls_back_to_the_
full_diff` — этот тест проверяет ТОЛЬКО вторую, новую половину: пометка
причины в `package["text"]`.

Красен до реализации: `review_package` сегодня не добавляет в `parts`
НИКАКОГО текста для случая `incremental=False` (единственная ветка,
дописывающая текст по `incremental`, — противоположная, `if incremental:`
для инструкции о полном diff). Итерация 1 и «итерация > 1, но sha не
распознан» сегодня производят БАЙТ-В-БАЙТ одинаковый `text` (с точностью
до случайного `run_id` границ — см. `_normalize` ниже) — то есть причина
нигде не названа.
"""
import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import gitcmd, review, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import RecordingGit  # noqa: E402

TASK = "T001"

# `brief.new_run_id()` — `secrets.token_hex(16)`, 32 hex-символа: маркеры
# границ несут его в каждом компоненте пакета и делают ЛЮБЫЕ два вызова
# `review_package` текстуально разными, даже без единой смысловой
# правки — тест обязан вычесть этот шум ПЕРЕД сравнением, иначе сравнение
# ничего не доказывает (см. докстринг модуля: без нормализации две сборки
# и сегодня «различны» только этим шумом).
_RUN_ID_RE = re.compile(r"\b[0-9a-f]{32}\b")


def _normalize(text: str) -> str:
    return _RUN_ID_RE.sub("<run>", text)


class MissingBaseNamesTheReasonTest(TmpRootTest):

    BRANCH = "task/t001-ac5"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.git = RecordingGit()
        from unittest import mock
        patcher = mock.patch.object(gitcmd, "git", self.git)
        patcher.start()
        self.addCleanup(patcher.stop)

    def build(self, **kwargs) -> dict:
        return review.review_package(self.conn, TASK, "AC-5", self.BRANCH, **kwargs)

    def test_ac5_diff_falls_back_to_main_branch(self):
        """Требование 2 SPEC (первая половина, уже покрытая T029 —
        воспроизведена здесь для полноты AC-5, не дублирует
        `test_missing_prev_sha_falls_back_to_the_full_diff`: та проверяет
        `diff_type`/список вызовов на своей фикстуре `FakeGit`, эта — на
        своей).

        Ловит мутацию: `incremental` вычисляется без учёта пустого
        `prev_sha` (например, только по `iteration > 1`) — diff ушёл бы
        от `prev_sha=""` буквально, а не от `config.MAIN_BRANCH`.
        """
        from orchestrator import config
        package = self.build(iteration=2, prev_sha="")

        self.assertEqual(package["diff_type"], "полный")
        self.assertEqual(self.git.diff_bases(), [config.MAIN_BRANCH, config.MAIN_BRANCH])

    def test_ac5_package_text_names_the_reason_the_base_is_missing(self):
        """Итерация 1 (база не нужна вовсе) и «итерация 2, sha не
        распознан» (требование 2) сегодня дают текстуально ОДИНАКОВЫЙ
        `text` (с точностью до случайного `run_id`, см. `_normalize`) —
        AC-5 требует, чтобы второй случай назвал причину отсутствия базы,
        отличив себя от обычной первой итерации.

        Ловит мутацию: причина добавляется в журнальную пометку
        (`package_note`) или не добавляется вовсе, но не в сам
        `package["text"]` — этот тест смотрит именно в `text`, как
        буквально требует AC-5 («текст пакета»).
        """
        baseline = _normalize(self.build(iteration=1)["text"])
        missing_base = _normalize(self.build(iteration=2, prev_sha="")["text"])

        self.assertNotEqual(
            missing_base, baseline,
            "текст пакета итерации > 1 с нераспознанным sha неотличим "
            "от обычной первой итерации — причина отсутствия базы нигде "
            "не названа")


if __name__ == "__main__":
    unittest.main()
