#!/usr/bin/env python3
"""
VERTICAL AI -- Shared Schema
Universal data contract. Code City maps this graph.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
import json


@dataclass
class ScoutTarget:
    name: str
    category: str
    source: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    has_website: bool = False
    rating: Optional[float] = None
    review_count: Optional[int] = None
    price_tier: Optional[str] = None
    cfpb_complaints: list = field(default_factory=list)
    web_signals: list = field(default_factory=list)
    risk_flags: list = field(default_factory=list)
    opportunity_flags: list = field(default_factory=list)
    scouted_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self): return asdict(self)
    def to_json(self): return json.dumps(self.to_dict(), indent=2)
    def to_conductor_context(self):
        return {"type": "scrape", "label": f"{self.name} -- {self.category}", "data": self.to_dict(), "raw": self.to_json()}

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class OutreachPayload:
    session_id: str
    target_name: str
    champion_thesis: str
    first_action: str
    subject_line: str = ""
    hook: str = ""
    value_proposition: str = ""
    pain_point: str = ""
    call_to_action: str = ""
    tone: str = "consultative"
    email_body: str = ""
    linkedin_body: str = ""
    sms_body: str = ""
    objection_no_budget: str = ""
    objection_not_interested: str = ""
    objection_have_someone: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self): return asdict(self)
    def to_json(self): return json.dumps(self.to_dict(), indent=2)
