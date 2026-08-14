from drift.platforms import fit


def test_short_text_is_not_truncated():
    result = fit("a short post", "x")
    assert result.text == "a short post"
    assert result.truncated is False
    assert result.limit == 280


def test_long_text_is_truncated_to_limit():
    result = fit("x" * 500, "x")
    assert result.truncated is True
    assert len(result.text) == 280
    assert result.original_length == 500


def test_each_platform_has_a_limit():
    from drift.platforms import PLATFORMS

    assert PLATFORMS["x"].char_limit == 280
    assert PLATFORMS["linkedin"].char_limit == 3000
    assert PLATFORMS["instagram"].char_limit == 2200
