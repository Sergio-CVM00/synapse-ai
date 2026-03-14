"""Local files connector for reading PDF, MD, TXT, and code files."""

import os
from pathlib import Path
from typing import Any

from connectors.base import BaseConnector


class LocalFilesConnector(BaseConnector):
    """Connector for reading local files.

    Supports: PDF, Markdown, Text, and code files (.py, .ts, .js, .go, etc.)
    """

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        ".pdf": "pdf",
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "text",
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
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
    }

    def __init__(self):
        self._connected = False

    def connect(self) -> None:
        """Establish connection (no-op for local files)."""
        self._connected = True

    def disconnect(self) -> None:
        """Close connection (no-op for local files)."""
        self._connected = False

    def fetch(self, source: str) -> dict[str, Any]:
        """Fetch content from a local file.

        Args:
            source: Path to the local file

        Returns:
            Dictionary with keys:
                - content: str - Raw text content
                - file_type: str - Detected file type
                - file_path: str - Absolute path to file
                - file_size: int - File size in bytes
                - error: str - Error message if failed
        """
        result = {
            "content": "",
            "file_type": "unknown",
            "file_path": source,
            "file_size": 0,
            "error": None,
        }

        # Validate file exists
        if not os.path.exists(source):
            result["error"] = f"File not found: {source}"
            return result

        # Check if it's a file (not directory)
        if not os.path.isfile(source):
            result["error"] = f"Not a file: {source}"
            return result

        # Check read permissions
        if not os.access(source, os.R_OK):
            result["error"] = f"Permission denied: {source}"
            return result

        # Get file size
        try:
            result["file_size"] = os.path.getsize(source)
        except OSError as e:
            result["error"] = f"Cannot get file size: {e}"
            return result

        # Determine file type
        ext = Path(source).suffix.lower()
        file_type = self.SUPPORTED_EXTENSIONS.get(ext, "unknown")
        result["file_type"] = file_type

        if file_type == "unknown":
            result["error"] = f"Unsupported file type: {ext}"
            return result

        # Read content based on file type
        try:
            if file_type == "pdf":
                result["content"] = self._read_pdf(source)
            else:
                result["content"] = self._read_text_file(source)
        except Exception as e:
            result["error"] = f"Error reading file: {e}"

        return result

    def _read_text_file(self, file_path: str) -> str:
        """Read a text file with proper encoding handling."""
        encodings = ["utf-8", "latin-1", "cp1252", "utf-16"]

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception as e:
                raise e

        raise ValueError(f"Could not decode file with any supported encoding")

    def _read_pdf(self, file_path: str) -> str:
        """Extract text from PDF using pypdf."""
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError(
                "pypdf is required for PDF processing. Install with: pip install pypdf"
            )

        try:
            reader = PdfReader(file_path)
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Error reading PDF: {e}")
