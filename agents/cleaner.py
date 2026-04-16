"""Cleaner Agent implementation for Knoss.

The Cleaner Agent processes raw article content by removing noise elements
such as advertisements, QR code prompts, signatures, and other non-content
elements while preserving the article structure.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from ..models.payloads import CleanerOutput, PreservedStructureBlock, RemovedBlock
from .base import Agent, AgentResult


class CleanerInput(BaseModel):
    """Input payload for Cleaner Agent.

    Attributes:
        article_id: Unique identifier for the article
        title: Article title
        raw_html: Raw HTML content of the article
        raw_text: Plain text extracted from the article
    """

    article_id: str = Field(description="Unique identifier for the article")
    title: str = Field(description="Article title")
    raw_html: Optional[str] = Field(default=None, description="Raw HTML content")
    raw_text: str = Field(description="Plain text content")


class CleanerAgent(Agent[CleanerInput, CleanerOutput]):
    """Agent that removes noise from raw article content.

    The Cleaner Agent processes articles by:
    1. Removing advertisements and promotional content
    2. Removing QR code prompts and call-to-action elements
    3. Removing signatures and author footers
    4. Preserving document structure (headings, sections)
    5. Tracking removed blocks for traceability

    This agent maintains source offsets to enable downstream traceability.
    """

    input_model = CleanerInput
    output_model = CleanerOutput

    # Noise detection patterns
    _QR_PATTERNS = [
        r"扫码[加入关注进群]",
        r"二维码[扫码识别]",
        r"长按[识别关注]",
        r"微信[公众号群聊]+",
    ]

    _PROMO_PATTERNS = [
        r"点击[阅读全文]+",
        r"更多[内容精彩]+",
        r"点赞[收藏分享转发在看]+",
        r"关注[我们公众号作者]+",
    ]

    _SIGNATURE_PATTERNS = [
        r"^[=－—]{3,}$",
        r"^[本文作者编辑来源]+：",
        r"^[免责声明声明]+：",
        r"^[转载注明]+：",
    ]

    _AD_PATTERNS = [
        r"^\s*广告\s*$",
        r"赞助商",
        r"AD\s*[:：]",
    ]

    def execute(self, input_data: CleanerInput) -> AgentResult:
        """Execute cleaning on raw article content.

        Args:
            input_data: Validated input with raw article content

        Returns:
            AgentResult with CleanerOutput containing cleaned text and metadata
        """
        if not input_data.raw_text and not input_data.raw_html:
            return AgentResult.fail("No content provided for cleaning")

        warnings = []
        metadata = {"article_id": input_data.article_id}

        # Use raw_text if available, otherwise extract from HTML
        if input_data.raw_text:
            text = input_data.raw_text
        elif input_data.raw_html:
            text = self._extract_text_from_html(input_data.raw_html)
            warnings.append("Extracted text from HTML (raw_text not provided)")
        else:
            return AgentResult.fail("No text content available for cleaning")

        # Detect and remove noise blocks
        removed_blocks, clean_text = self._remove_noise_blocks(
            text,
            input_data.article_id,
        )

        # Preserve structure blocks
        preserved_blocks = self._extract_structure_blocks(
            clean_text,
            input_data.title,
        )

        metadata["removed_count"] = len(removed_blocks)
        metadata["preserved_count"] = len(preserved_blocks)
        metadata["original_length"] = len(text)
        metadata["clean_length"] = len(clean_text)

        if removed_blocks:
            warnings.append(f"Removed {len(removed_blocks)} noise blocks")

        output = CleanerOutput(
            article_id=input_data.article_id,
            clean_text=clean_text,
            removed_blocks=removed_blocks,
            preserved_structure_blocks=preserved_blocks,
        )

        return AgentResult.ok(
            output=output,
            warnings=warnings,
            metadata=metadata,
        )

    def _extract_text_from_html(self, html: str) -> str:
        """Extract plain text from HTML content.

        Args:
            html: Raw HTML content

        Returns:
            Extracted plain text
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "noscript"]):
                script.decompose()

            # Remove common noise elements
            noise_selectors = [
                '.rich_media_meta',
                '.profile_meta',
                '.qr_code_pc',
                '.reward_container',
                '.mpwig_multiple',
                '[class*="ad"]',
                '[id*="ad"]',
            ]

            for selector in noise_selectors:
                for element in soup.select(selector):
                    element.decompose()

            # Get text
            text = soup.get_text(separator='\n', strip=True)

            # Clean up excessive whitespace
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)

            return text

        except ImportError:
            pass

        # Simple regex-based fallback
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"</(p|div|h[1-6]|li|br|section|article|tr|td|th)>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"<[^>]+>", "", html)
        html = re.sub(r"\u3000", " ", html)
        html = re.sub(r"&nbsp;", " ", html)
        html = re.sub(r"\s{3,}", "\n\n", html)
        html = html.strip()

        return html

    def _remove_noise_blocks(
        self,
        text: str,
        article_id: str,
    ) -> tuple[list[RemovedBlock], str]:
        """Detect and remove noise blocks from text.

        Args:
            text: The text to clean
            article_id: Article ID for tracking

        Returns:
            Tuple of (removed blocks list, cleaned text)
        """
        lines = text.split("\n")
        removed_blocks: list[RemovedBlock] = []
        clean_lines: list[str] = []

        for line in lines:
            noise_result = self._detect_noise_type(line)

            if noise_result:
                noise_type, reason = noise_result
                removed_blocks.append(
                    RemovedBlock(
                        type=noise_type,
                        text=line.strip()[:100],
                        reason=reason,
                    )
                )
            else:
                clean_lines.append(line)

        clean_text = "\n".join(clean_lines)

        return removed_blocks, clean_text

    def _detect_noise_type(self, line: str) -> Optional[tuple[str, str]]:
        """Detect if a line is noise and return its type.

        Args:
            line: The line to check

        Returns:
            Tuple of (noise_type, reason) if noise, None otherwise
        """
        stripped = line.strip()

        if not stripped:
            return None

        # Check QR code prompts
        for pattern in self._QR_PATTERNS:
            if re.search(pattern, stripped):
                return ("qr_prompt", "call_to_action_noise")

        # Check promotional content
        for pattern in self._PROMO_PATTERNS:
            if re.search(pattern, stripped):
                return ("promo", "promotional_content")

        # Check signatures
        for pattern in self._SIGNATURE_PATTERNS:
            if re.search(pattern, stripped):
                return ("signature", "author_signature")

        # Check advertisements
        for pattern in self._AD_PATTERNS:
            if re.search(pattern, stripped):
                return ("ad", "advertisement")

        # Check for very short lines that are likely navigation
        if len(stripped) <= 3 and stripped.isalpha():
            return ("nav", "navigation_element")

        return None

    def _extract_structure_blocks(
        self,
        text: str,
        title: str,
    ) -> list[PreservedStructureBlock]:
        """Extract structural blocks from cleaned text.

        Args:
            text: The cleaned text to parse
            title: Article title

        Returns:
            List of preserved structure blocks with heading paths
        """
        blocks: list[PreservedStructureBlock] = []
        lines = text.split("\n")

        current_heading_path: list[str] = [title]
        block_index = 0
        buffer: list[str] = []

        def flush_buffer() -> None:
            nonlocal block_index
            if buffer:
                blocks.append(
                    PreservedStructureBlock(
                        block_index=block_index,
                        heading_path=current_heading_path.copy(),
                        text=" ".join(buffer).strip(),
                    )
                )
                block_index += 1
                buffer.clear()

        for line in lines:
            stripped = line.strip()

            if not stripped:
                flush_buffer()
                continue

            # Detect headings
            if self._is_heading(stripped):
                flush_buffer()

                heading_level = self._get_heading_level(stripped)
                heading_text = stripped.lstrip("#").strip()

                # Adjust path based on heading level
                if heading_level == 1:
                    current_heading_path = [heading_text]
                elif heading_level == 2:
                    if len(current_heading_path) > 1:
                        current_heading_path[1:] = [heading_text]
                    else:
                        current_heading_path.append(heading_text)
                else:
                    while len(current_heading_path) >= heading_level:
                        current_heading_path.pop()
                    current_heading_path.append(heading_text)
            else:
                buffer.append(stripped)

        flush_buffer()

        return blocks

    def _is_heading(self, line: str) -> bool:
        """Check if a line is a heading.

        Args:
            line: The line to check

        Returns:
            True if the line appears to be a heading
        """
        if line.startswith("#"):
            return True

        if len(line) < 50 and not line.endswith(("。", ".", "!", "！")):
            if re.match(r"^[\u4e00-\u9fff]{2,20}$", line):
                return True
            if "？" in line or "?" in line:
                return True

        return False

    def _get_heading_level(self, line: str) -> int:
        """Get the heading level from a heading line.

        Args:
            line: The heading line

        Returns:
            Heading level (1-6)
        """
        match = re.match(r"^(#{1,6})\s", line)
        if match:
            return len(match.group(1))

        return 2


__all__ = ["CleanerAgent", "CleanerInput", "CleanerOutput"]
