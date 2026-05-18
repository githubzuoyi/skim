"""Tests for skim.commands."""

from skim.commands import _prefer_smaller_output


class TestPreferSmallerOutput:
    def test_compress_falls_back_to_raw_when_filtered_is_larger(self):
        output, mode = _prefer_smaller_output("short", "this is definitely longer", "compress")

        assert output == "short"
        assert mode == "full"

    def test_compress_keeps_filtered_output_when_it_is_smaller(self):
        output, mode = _prefer_smaller_output("x" * 100, "x" * 10, "compress")

        assert output == "x" * 10
        assert mode == "compress"