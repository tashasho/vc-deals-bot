"""Shared data types for the VC deals bot."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class DealItem:
    """A funding event, market update, or deal-flow news item before enrichment."""
    id: str                   # stable ID, e.g. "tc-https://..."
    source: str               # e.g. "TechCrunch", "CrunchbaseNews", "Sifted"
    category: str             # "deal" | "market" | "fund" | "ipo" | "other"
    title: str
    url: str
    published: Optional[datetime] = None
    description: Optional[str] = None  # raw RSS summary

    # Populated by summarizer
    summary: Optional[str] = None
    company: Optional[str] = None       # company being invested in
    amount: Optional[str] = None        # e.g. "$15M Series A"
    investors: List[str] = field(default_factory=list)
    sector: Optional[str] = None
    why_interesting: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    emoji: str = "📈"
