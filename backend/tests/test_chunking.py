from app.services.chunking import split_into_chunks


def test_chunker_produces_chunks():
    big = "Lorem ipsum dolor sit amet. " * 200
    pages = [{"page_num": 1, "text": big}]
    chunks = split_into_chunks(pages, chunk_size=500, chunk_overlap=50)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.text
        assert c.token_count > 0
        assert c.chunk_index >= 0
        assert c.page_number == 1


def test_chunk_indices_are_sequential():
    big = "alpha beta gamma delta epsilon. " * 300
    pages = [{"page_num": 1, "text": big}]
    chunks = split_into_chunks(pages)
    for i, c in enumerate(chunks):
        assert c.chunk_index == i


def test_multipage_chunks_assign_pages():
    pages = [
        {"page_num": 1, "text": "page one content " * 100},
        {"page_num": 2, "text": "page two content " * 100},
    ]
    chunks = split_into_chunks(pages)
    assert any(c.page_number == 1 for c in chunks)
    assert any(c.page_number == 2 for c in chunks)
