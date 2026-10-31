"""Regression tests for reviewed moments and portrait video rendering.

Run from backend/: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models import Moment, Review, Transcript
from app.pipeline import moments, render


def make_moment(
    moment_id: str, start: float, end: float, status: str = "candidate",
) -> Moment:
    review = None
    if status in ("approved", "rejected"):
        review = Review(decision=status, by="editor@test", reason="Reviewed")
    return Moment(
        id=moment_id, source_id="src_test", start=start, end=end,
        orig_start=start, orig_end=end, start_utt=0, end_utt=0,
        headline="Test", quote="Literal text", status=status, review=review,
        clip_id="c_published" if status == "approved" else None,
    )


class ReviewedMomentRerunTests(unittest.TestCase):
    def test_rerun_preserves_reviewed_moments_and_skips_overlapping_candidates(self) -> None:
        approved = make_moment("m_approved", 10, 25, "approved")
        rejected = make_moment("m_rejected", 40, 55, "rejected")
        old_approval = approved.review
        duplicate_approved = make_moment("m_duplicate_approved", 12, 26)
        duplicate_rejected = make_moment("m_duplicate_rejected", 41, 57)
        fresh = make_moment("m_new", 80, 95)

        with (
            patch.object(moments.db, "list_moments", return_value=[approved, rejected]),
            patch.object(moments.db, "get_transcript", return_value=Transcript(
                source_id="src_test", asr_model="fixture", utterances=[],
            )),
            patch.object(moments.db, "set_source_status"),
            patch.object(moments, "find_moments_raw", return_value=[]),
            patch.object(moments, "materialize", return_value=[
                duplicate_approved, duplicate_rejected, fresh,
            ]),
            patch.object(moments.db, "save_moments") as save,
            patch.object(moments.db, "index_moments"),
        ):
            result = moments.find_moments("src_test", force=True, with_integrity=False)

        self.assertEqual([m.id for m in result], ["m_approved", "m_rejected", "m_new"])
        self.assertIs(result[0].review, old_approval)
        self.assertEqual(result[0].clip_id, "c_published")
        self.assertEqual(result[1].review.decision, "rejected")
        save.assert_called_once_with("src_test", result)


class PortraitRenderTests(unittest.TestCase):
    def test_scale_to_cover_before_center_cropping(self) -> None:
        tr = Transcript(source_id="src_test", asr_model="fixture", utterances=[])
        with tempfile.TemporaryDirectory() as tempdir, patch.object(render, "_run") as run:
            render.render_body(Path("source.mp4"), tr, 1, 3, Path(tempdir), captions_on=False)
            cmd = run.call_args.args[0]
        vf = cmd[cmd.index("-vf") + 1]
        self.assertEqual(
            vf,
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
        )

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            self.skipTest("ffmpeg not installed")
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             "color=c=black:s=360x800:r=1:d=1", "-vf", vf,
             "-frames:v", "1", "-f", "null", "-"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
