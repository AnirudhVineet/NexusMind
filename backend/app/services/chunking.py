from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class ChunkResult:
    chunk_index: int
    text: str
    char_offset: int
    page_number: int | None
    token_count: int


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def split_into_chunks(
    pages: list[dict],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[ChunkResult]:
    """
    pages: list of {page_num: int|None, text: str}
    Returns ordered chunks with char_offset (in normalized full text) and page_number.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size * 4,  # convert token estimate -> chars
        chunk_overlap=chunk_overlap * 4,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    full_text_parts: list[str] = []
    page_offsets: list[tuple[int, int | None]] = []
    cursor = 0
    for p in pages:
        text = p["text"] or ""
        page_offsets.append((cursor, p.get("page_num")))
        full_text_parts.append(text)
        cursor += len(text) + 2  # join with "\n\n"

    full_text = "\n\n".join(full_text_parts)

    raw_chunks = splitter.split_text(full_text)

    results: list[ChunkResult] = []
    search_from = 0
    for idx, chunk in enumerate(raw_chunks):
        offset = full_text.find(chunk, search_from)
        if offset < 0:
            offset = search_from
        search_from = offset + max(1, len(chunk) - chunk_overlap * 4)

        page = None
        for start, page_num in page_offsets:
            if start <= offset:
                page = page_num
            else:
                break

        results.append(
            ChunkResult(
                chunk_index=idx,
                text=chunk,
                char_offset=offset,
                page_number=page,
                token_count=_approx_tokens(chunk),
            )
        )

    return results
