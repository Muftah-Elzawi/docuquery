import pytest

from app.services.chunking import chunk_pages


def test_short_page_is_one_chunk():
    chunks = chunk_pages(["Hello world."], size=100, overlap=10)
    assert [(c.page, c.content) for c in chunks] == [(1, "Hello world.")]


def test_chunks_never_cross_pages_and_keep_page_numbers():
    chunks = chunk_pages(["a " * 300, "", "b " * 300], size=200, overlap=20)
    assert {c.page for c in chunks} == {1, 3}
    assert all(set(c.content.split()) <= {"a"} for c in chunks if c.page == 1)
    assert [c.position for c in chunks] == list(range(len(chunks)))


def test_respects_size_and_overlaps_neighbours():
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_pages([text], size=200, overlap=50)
    assert all(len(c.content) <= 200 for c in chunks)
    for first, second in zip(chunks, chunks[1:]):
        assert first.content.split()[-1] in second.content  # overlap carries context over
    assert "word499" in chunks[-1].content


def test_prefers_sentence_boundaries():
    text = "First sentence is here. " * 20
    chunks = chunk_pages([text], size=120, overlap=20)
    assert all(c.content.endswith(".") for c in chunks)


def test_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_pages(["x"], size=100, overlap=100)
