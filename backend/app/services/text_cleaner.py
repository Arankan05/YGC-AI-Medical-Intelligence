import re
from typing import Optional


class TextCleaner:
    """
    Conservative, deterministic text cleaner and normalizer for raw extracted medical text.

    Design Principles:
    - Highly conservative: Never alters medical terminology, numerical values, dosages,
      units, punctuation, or dates.
    - Deterministic: Standardizes whitespace, line endings, and tabs.
    - Fully idempotent: clean(clean(text)) == clean(text).
    - Standalone: Zero dependencies on database or API frameworks.
    """

    def __init__(
        self,
        max_consecutive_newlines: int = 2,
        tab_size: int = 4,
    ) -> None:
        self.max_consecutive_newlines = max(1, max_consecutive_newlines)
        self.tab_size = tab_size

    def clean(self, text: Optional[str]) -> str:
        """
        Cleans and normalizes raw medical text safely.

        Args:
            text: Raw string extracted from a document (e.g. PyMuPDF or Tesseract).

        Returns:
            Cleaned and normalized text string, or empty string if input is empty/whitespace.
        """
        if not text or not isinstance(text, str):
            return ""

        if not text.strip():
            return ""

        # 1. Normalize line endings: CRLF (\r\n) and CR (\r) -> LF (\n)
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")

        # 2. Normalize tabs to spaces
        if "\t" in normalized:
            normalized = normalized.expandtabs(self.tab_size)

        # 3. Process line-by-line:
        #    - Collapse redundant horizontal whitespace (multiple spaces -> single space)
        #    - Strip trailing whitespace from each line
        lines = normalized.split("\n")
        cleaned_lines = []
        for line in lines:
            cleaned_line = re.sub(r"[^\S\n]+", " ", line).rstrip()
            cleaned_lines.append(cleaned_line)

        # Re-join lines
        joined = "\n".join(cleaned_lines)

        # 4. Collapse excessive consecutive blank lines (e.g. 3+ newlines -> 2 newlines)
        newline_pattern = r"\n{" + str(self.max_consecutive_newlines + 1) + r",}"
        replacement_newlines = "\n" * self.max_consecutive_newlines
        joined = re.sub(newline_pattern, replacement_newlines, joined)

        # 5. Trim leading and trailing outer whitespace
        return joined.strip()


# Default singleton and convenience helper function
_default_cleaner = TextCleaner()


def clean_text(text: Optional[str]) -> str:
    """
    Convenience function to clean and normalize medical text using the default TextCleaner.

    Args:
        text: Raw text string.

    Returns:
        Cleaned text string.
    """
    return _default_cleaner.clean(text)
