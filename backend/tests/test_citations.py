from app.services.rag import validate_citations


def test_valid_markers_pass_through():
    result = validate_citations("Refunds take 5 days [1]. Shipping is free [2].", 3)
    assert result.text == "Refunds take 5 days [1]. Shipping is free [2]."
    assert result.cited == [1, 2]
    assert result.removed == []
    assert not result.insufficient


def test_invented_marker_is_removed_and_reported():
    result = validate_citations("Refunds take 5 days [1]. Free shipping [7].", 3)
    assert result.text == "Refunds take 5 days [1]. Free shipping."
    assert result.cited == [1]
    assert result.removed == [7]


def test_combined_marker_keeps_only_valid_numbers():
    result = validate_citations("Both apply [1, 9].", 3)
    assert result.text == "Both apply [1]."
    assert result.cited == [1]
    assert result.removed == [9]


def test_answer_with_only_invented_markers_is_rejected():
    result = validate_citations("Something [5].", 3)
    assert result.insufficient
    assert result.reason == "uncited_answer"
    assert result.removed == [5]


def test_zero_is_not_a_valid_marker():
    result = validate_citations("Claim [0].", 3)
    assert result.insufficient and result.removed == [0]


def test_uncited_answer_is_not_accepted_as_grounded():
    result = validate_citations("Refunds take 5 days.", 3)
    assert result.insufficient
    assert result.reason == "uncited_answer"


def test_model_declining_is_recognised():
    result = validate_citations("INSUFFICIENT_EVIDENCE", 3)
    assert result.insufficient and result.reason == "model_declined"
    assert validate_citations("I think INSUFFICIENT_EVIDENCE here [1]", 3).insufficient


def test_year_in_brackets_is_not_treated_as_a_citation():
    result = validate_citations("In [2024] it rose [1].", 2)
    assert result.text == "In [2024] it rose [1]."
    assert result.cited == [1]


def test_spacing_inside_markers_is_normalised():
    assert validate_citations("Fact [1,2].", 3).text == "Fact [1, 2]."
