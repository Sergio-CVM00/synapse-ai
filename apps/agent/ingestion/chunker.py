"""Text chunking strategies for different file types.

Strategies:
- RecursiveCharacterTextSplitter: General text, code, JSON, YAML
- MarkdownHeaderTextSplitter: Markdown files with header preservation
- PythonCodeTextSplitter: Code files using tree-sitter AST parsing
- PDFTextSplitter: PDF documents with paragraph detection

All chunkers preserve metadata: file_path, start_line, end_line, heading
"""

import re
from pathlib import Path
from typing import Any

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)


# Supported code languages for tree-sitter
CODE_LANGUAGES = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".rs": "rust",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 200,
    file_path: str | None = None,
) -> list[dict[str, Any]]:
    """Split text using RecursiveCharacterTextSplitter.

    Args:
        text: Text to chunk
        chunk_size: Maximum tokens per chunk
        overlap: Overlap between chunks
        file_path: Optional file path for metadata

    Returns:
        List of chunk dictionaries with content and metadata
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", " ", ""],
        keep_separator=False,
    )

    chunks = splitter.split_text(text)

    result = []
    current_line = 1

    for chunk in chunks:
        # Calculate approximate line count
        lines = chunk.count("\n") + 1

        metadata = {
            "file_path": file_path,
            "start_line": current_line,
            "end_line": current_line + lines - 1,
        }

        result.append(
            {
                "content": chunk,
                "metadata": metadata,
            }
        )

        current_line += lines

    return result


def chunk_markdown(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    file_path: str | None = None,
) -> list[dict[str, Any]]:
    """Split markdown preserving header hierarchy.

    Args:
        text: Markdown text to chunk
        chunk_size: Maximum tokens per chunk
        overlap: Overlap between chunks
        file_path: Optional file path for metadata

    Returns:
        List of chunk dictionaries with content, heading, and line numbers
    """
    # Define markdown headers to split on
    headers_to_split_on = [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
        ("####", "h4"),
        ("#####", "h5"),
        ("######", "h6"),
    ]

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        return_on_error=True,
    )

    # Split by headers
    splits = splitter.split_text(text)

    result = []
    current_line = 1
    current_heading = None

    for split in splits:
        content = split.page_content
        metadata = split.metadata if hasattr(split, "metadata") else {}

        # Extract heading from metadata
        heading = None
        for level in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            if level in metadata:
                heading = metadata[level]
                current_heading = heading
                break

        # Calculate line numbers
        lines = content.count("\n") + 1

        chunk_metadata = {
            "file_path": file_path,
            "start_line": current_line,
            "end_line": current_line + lines - 1,
            "heading": current_heading,
        }

        result.append(
            {
                "content": content,
                "metadata": chunk_metadata,
            }
        )

        current_line += lines

    return result


def chunk_code(
    code: str,
    file_path: str | None = None,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """Split code using tree-sitter AST-aware chunking.

    Chunks by function, class, or method definitions.

    Args:
        code: Source code to chunk
        file_path: Optional file path for metadata
        language: Programming language (auto-detected from extension if not provided)

    Returns:
        List of chunk dictionaries with content and line numbers
    """
    if not code.strip():
        return []

    # Detect language from file extension if not provided
    if language is None and file_path:
        ext = Path(file_path).suffix.lower()
        language = CODE_LANGUAGES.get(ext, "python")
    elif language is None:
        language = "python"

    try:
        from tree_sitter import Language, Parser
    except ImportError:
        # Fallback to character-based chunking if tree-sitter not available
        return _chunk_code_fallback(code, file_path)

    try:
        # Get tree-sitter language
        lang = Language(f"tree-sitter-{language}", language)
        parser = Parser(lang)

        tree = parser.parse(bytes(code, "utf8"))

        return _extract_code_functions(tree.root_node, code, file_path)
    except Exception:
        # Fallback to character-based chunking on error
        return _chunk_code_fallback(code, file_path)


def _extract_code_functions(
    node, source_code: str, file_path: str | None
) -> list[dict]:
    """Recursively extract function/class definitions from AST."""
    result = []

    # Function/method definitions by language
    function_nodes = {
        "python": [
            "function_definition",
            "class_definition",
            "async_function_definition",
        ],
        "javascript": [
            "function_declaration",
            "arrow_function",
            "class_declaration",
            "method_definition",
        ],
        "typescript": [
            "function_declaration",
            "arrow_function",
            "class_declaration",
            "method_definition",
        ],
        "tsx": [
            "function_declaration",
            "arrow_function",
            "class_declaration",
            "method_definition",
        ],
        "go": ["function_declaration", "method_declaration"],
        "java": ["method_declaration", "class_declaration"],
        "rust": ["function_item", "impl_item"],
        "c": ["function_definition"],
        "cpp": ["function_definition", "class_specifier"],
    }

    # Check if this node is a function/class definition
    node_type = node.type

    # Get supported types for common languages (default to python)
    types = function_nodes.get("python", function_nodes["python"])

    if node_type in types:
        start_line = node.start_point.row + 1
        end_line = node.end_point.row + 1

        # Extract source for this node
        source_lines = source_code.split("\n")
        if start_line <= len(source_lines) and end_line <= len(source_lines):
            content = "\n".join(source_lines[start_line - 1 : end_line])
        else:
            # Fallback: use byte extraction
            try:
                content = source_code[node.start_byte : node.end_byte]
            except (TypeError, AttributeError):
                # If byte access fails, just take from start_line
                content = "\n".join(source_lines[start_line - 1 : start_line + 10])

        result.append(
            {
                "content": content,
                "metadata": {
                    "file_path": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "node_type": node_type,
                },
            }
        )

    # Recurse into children
    for child in node.children:
        result.extend(_extract_code_functions(child, source_code, file_path))

    # Sort by start_line
    result.sort(key=lambda x: x["metadata"]["start_line"])

    # Merge small chunks that are too short
    return _merge_small_chunks(result, min_size=100)


def _merge_small_chunks(chunks: list[dict], min_size: int = 100) -> list[dict]:
    """Merge chunks that are too small (< min_size characters)."""
    if not chunks:
        return []

    merged = [chunks[0]]

    for chunk in chunks[1:]:
        if len(merged[-1]["content"]) < min_size:
            # Merge with previous
            merged[-1]["content"] += "\n\n" + chunk["content"]
            merged[-1]["metadata"]["end_line"] = chunk["metadata"]["end_line"]
        else:
            merged.append(chunk)

    return merged


def _chunk_code_fallback(code: str, file_path: str | None) -> list[dict]:
    """Fallback chunking for code when tree-sitter is not available."""
    return chunk_text(code, chunk_size=400, overlap=100, file_path=file_path)


def chunk_pdf(
    text: str,
    chunk_size: int = 600,
    overlap: int = 150,
    file_path: str | None = None,
) -> list[dict[str, Any]]:
    """Split PDF text by paragraphs and sections.

    Args:
        text: Extracted PDF text
        chunk_size: Maximum tokens per chunk
        overlap: Overlap between chunks
        file_path: Optional file path for metadata

    Returns:
        List of chunk dictionaries with content and line numbers
    """
    # Split by paragraph boundaries (double newlines)
    paragraphs = re.split(r"\n\s*\n", text)

    result = []
    current_chunk = []
    current_size = 0
    current_line = 1

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_size = len(para)

        # If adding this paragraph exceeds chunk size, start new chunk
        if current_size + para_size > chunk_size and current_chunk:
            # Join current chunk
            content = "\n\n".join(current_chunk)
            lines = content.count("\n") + 1

            result.append(
                {
                    "content": content,
                    "metadata": {
                        "file_path": file_path,
                        "start_line": current_line,
                        "end_line": current_line + lines - 1,
                    },
                }
            )

            # Start new chunk with overlap
            overlap_text = current_chunk[-1] if current_chunk else ""
            current_chunk = [overlap_text + "\n" + para] if overlap_text else [para]
            current_size = len(overlap_text) + len(para) if overlap_text else len(para)
            current_line += lines - overlap_text.count("\n") if overlap_text else 0
        else:
            current_chunk.append(para)
            current_size += para_size

    # Add remaining chunk
    if current_chunk:
        content = "\n\n".join(current_chunk)
        lines = content.count("\n") + 1

        result.append(
            {
                "content": content,
                "metadata": {
                    "file_path": file_path,
                    "start_line": current_line,
                    "end_line": current_line + lines - 1,
                },
            }
        )

    return result


def detect_file_type(file_path: str) -> str:
    """Detect file type from extension.

    Args:
        file_path: Path to the file

    Returns:
        File type string: 'pdf', 'markdown', 'code', 'text', 'unknown'
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        return "pdf"
    elif ext in (".md", ".markdown", ".mdown", ".mkd"):
        return "markdown"
    elif ext in CODE_LANGUAGES:
        return "code"
    elif ext in (".txt", ".text"):
        return "text"
    elif ext in (".json", ".yaml", ".yml", ".toml"):
        return "text"  # Treat config files as text
    else:
        return "unknown"


def chunk_content(
    content: str,
    file_type: str,
    file_path: str | None = None,
    chunk_size: int = 800,
    overlap: int = 200,
) -> list[dict[str, Any]]:
    """Chunk content based on file type.

    Args:
        content: Raw text content
        file_type: Type of file ('pdf', 'markdown', 'code', 'text')
        file_path: Optional file path for metadata
        chunk_size: Maximum tokens per chunk
        overlap: Overlap between chunks

    Returns:
        List of chunk dictionaries with content and metadata
    """
    if not content.strip():
        return []

    # Detect file type if not provided
    if file_type == "unknown" and file_path:
        file_type = detect_file_type(file_path)

    # Route to appropriate chunker
    if file_type == "pdf":
        return chunk_pdf(content, chunk_size, overlap, file_path)
    elif file_type == "markdown":
        return chunk_markdown(content, chunk_size, overlap, file_path)
    elif file_type == "code":
        return chunk_code(content, file_path)
    else:
        # Default: recursive character splitter
        return chunk_text(content, chunk_size, overlap, file_path)
