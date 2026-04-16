"""Blacklist Service for Knoss governance.

This service provides operations for managing alias blacklists,
filtering out noisy and problematic aliases.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Set

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


class BlacklistEntryInput(BaseModel):
    """Input for adding an alias to the blacklist."""
    alias: str = Field(description="Alias text to blacklist")
    reason: str = Field(description="Reason for blacklisting")
    category: str = Field(default="noise", description="Blacklist category")
    severity: str = Field(default="medium", description="Severity level")


class BlacklistCheckInput(BaseModel):
    """Input for checking if aliases are blacklisted."""
    aliases: List[str] = Field(description="List of aliases to check")


class BlacklistCheckOutput(BaseModel):
    """Output from blacklist check."""
    is_blacklisted: bool
    blacklisted_aliases: List[str]
    reasons: Dict[str, str]
    total_checked: int = 0
    blacklisted_count: int = 0


class AliasBlacklistService:
    """Service for managing alias blacklists.

    This service maintains a blacklist of problematic aliases that
    should be filtered out during entity extraction and concept mapping.
    """

    # Default blacklist entries for common noise
    DEFAULT_BLACKLIST = {
        # Single characters (structural tokens)
        "的", "了", "是", "在", "和", "与", "或", "但", "而", "等",
        # Punctuation
        "。", "，", "、", "；", "：", "！", "？", "（", "）",
        # Numbers (when not part of medical terms)
        "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
        # Common function words
        "这个", "那个", "这些", "那些", "某些", "各种",
        # Non-medical common words
        "可以", "需要", "应该", "可能", "通常", "一般",
    }

    def __init__(self, session: Session):
        """Initialize the blacklist service.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session
        self._blacklist_cache: Set[str] = set()
        self._blacklist_reasons: Dict[str, str] = {}
        self._initialized = False

    def _initialize(self) -> None:
        """Initialize the blacklist with default entries."""
        if self._initialized:
            return

        # Load from database if available
        try:
            from ..repositories.models import AliasBlacklist

            db_entries = self.session.query(AliasBlacklist).all()
            for entry in db_entries:
                self._blacklist_cache.add(entry.alias)
                self._blacklist_reasons[entry.alias] = entry.reason
        except Exception:
            pass

        # Add default entries
        for alias in self.DEFAULT_BLACKLIST:
            if alias not in self._blacklist_cache:
                self._blacklist_cache.add(alias)
                self._blacklist_reasons[alias] = "Default blacklist entry"

        self._initialized = True

    def add_to_blacklist(
        self,
        alias: str,
        reason: str,
        category: str = "noise",
        severity: str = "medium",
    ) -> Dict[str, Any]:
        """Add an alias to the blacklist.

        Args:
            alias: Alias text to blacklist
            reason: Reason for blacklisting
            category: Blacklist category
            severity: Severity level

        Returns:
            Blacklist entry information
        """
        self._initialize()

        # Add to cache
        self._blacklist_cache.add(alias)
        self._blacklist_reasons[alias] = reason

        # Persist to database
        try:
            from ..repositories.models import AliasBlacklist

            existing = self.session.query(AliasBlacklist).filter_by(
                alias=alias
            ).first()

            if not existing:
                entry = AliasBlacklist(
                    alias=alias,
                    reason=reason,
                    category=category,
                    severity=severity,
                )
                self.session.add(entry)
                self.session.flush()
        except Exception:
            pass

        return {
            "alias": alias,
            "reason": reason,
            "category": category,
            "severity": severity,
        }

    def remove_from_blacklist(self, alias: str) -> bool:
        """Remove an alias from the blacklist.

        Args:
            alias: Alias to remove

        Returns:
            True if removed, False if not found
        """
        self._initialize()

        if alias in self._blacklist_cache:
            self._blacklist_cache.remove(alias)
            if alias in self._blacklist_reasons:
                del self._blacklist_reasons[alias]

            # Remove from database
            try:
                from ..repositories.models import AliasBlacklist

                entry = self.session.query(AliasBlacklist).filter_by(
                    alias=alias
                ).first()

                if entry:
                    self.session.delete(entry)
                    self.session.flush()
            except Exception:
                pass

            return True

        return False

    def check_blacklist(self, aliases: List[str]) -> BlacklistCheckOutput:
        """Check which aliases are blacklisted.

        Args:
            aliases: List of aliases to check

        Returns:
            Blacklist check results
        """
        self._initialize()

        blacklisted = []
        reasons = {}

        for alias in aliases:
            if alias in self._blacklist_cache:
                blacklisted.append(alias)
                reasons[alias] = self._blacklist_reasons.get(alias, "Blacklisted")

        return BlacklistCheckOutput(
            is_blacklisted=len(blacklisted) > 0,
            blacklisted_aliases=blacklisted,
            reasons=reasons,
            total_checked=len(aliases),
            blacklisted_count=len(blacklisted),
        )

    def is_blacklisted(self, alias: str) -> bool:
        """Check if a single alias is blacklisted.

        Args:
            alias: Alias to check

        Returns:
            True if blacklisted, False otherwise
        """
        self._initialize()
        return alias in self._blacklist_cache

    def filter_blacklisted_aliases(self, aliases: List[str]) -> List[str]:
        """Filter out blacklisted aliases from a list.

        Args:
            aliases: List of aliases to filter

        Returns:
            List of non-blacklisted aliases
        """
        check_result = self.check_blacklist(aliases)
        return [
            alias for alias in aliases
            if alias not in check_result.blacklisted_aliases
        ]

    def get_blacklist_statistics(self) -> Dict[str, Any]:
        """Get blacklist statistics.

        Returns:
            Blacklist statistics
        """
        self._initialize()

        return {
            "total_blacklisted": len(self._blacklist_cache),
            "default_entries": len(self.DEFAULT_BLACKLIST),
            "custom_entries": len(self._blacklist_cache) - len(self.DEFAULT_BLACKLIST),
        }


__all__ = [
    "AliasBlacklistService",
    "BlacklistEntryInput",
    "BlacklistCheckInput",
    "BlacklistCheckOutput",
]
