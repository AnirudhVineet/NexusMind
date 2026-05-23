from app.services.llm import (
    Excerpt,
    build_user_prompt,
    extract_citation_indices,
)


def test_extract_citation_indices():
    answer = "Self-attention [1] is key. Position encodings [2] also matter [1]."
    assert extract_citation_indices(answer) == [1, 2, 1]


def test_build_user_prompt_wraps_excerpts_and_includes_question():
    excerpts = [
        Excerpt(index=1, document_title="Paper.pdf", page_number=2, section=None, text="Hello"),
        Excerpt(index=2, document_title="Other.pdf", page_number=None, section="A", text="World"),
    ]
    prompt = build_user_prompt(excerpts, "What is X?")
    assert "[1] Source: Paper.pdf, Page 2" in prompt
    assert "[2] Source: Other.pdf, Page ?" in prompt
    assert "<<<EXCERPT>>>" in prompt
    assert "Question: What is X?" in prompt


def test_control_chars_stripped_from_prompt():
    excerpts = [
        Excerpt(index=1, document_title="P.pdf", page_number=1, section=None,
                text="hello\x01\x02world"),
    ]
    prompt = build_user_prompt(excerpts, "q?")
    assert "\x01" not in prompt
    assert "\x02" not in prompt
    assert "helloworld" in prompt
