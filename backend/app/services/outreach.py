import re

from sqlalchemy.orm import Session

from app.models import EvidenceItem, OutreachDraft, Stakeholder


class OutreachService:
    def __init__(self, db: Session):
        self.db = db

    def _fact_bundle(self, stakeholder: Stakeholder) -> list[dict]:
        company_facts = (
            self.db.query(EvidenceItem)
            .filter(EvidenceItem.entity_type == "company", EvidenceItem.entity_id == stakeholder.company_id)
            .limit(6)
            .all()
        )
        person_facts = (
            self.db.query(EvidenceItem)
            .filter(EvidenceItem.entity_type == "stakeholder", EvidenceItem.entity_id == stakeholder.id)
            .limit(3)
            .all()
        )
        return [
            {
                "source_url": item.source_url,
                "fact": item.evidence_snippet,
                "method": item.extraction_method,
                "entity_type": item.entity_type,
            }
            for item in [*company_facts, *person_facts]
        ]

    @staticmethod
    def _clean_fact(text: str, limit: int = 120) -> str:
        trimmed = re.sub(r"\s+", " ", text.strip())
        return trimmed[:limit]

    @staticmethod
    def _choose_value_angle(facts: list[dict]) -> str:
        blob = " ".join(f["fact"].lower() for f in facts)
        if any(k in blob for k in ["vehicle wrap", "wrap"]):
            return "durable overlaminate performance for vehicle-wrap lifecycle"
        if any(k in blob for k in ["wallcover", "architectural"]):
            return "long-life protection for architectural graphics and wallcoverings"
        if any(k in blob for k in ["graffiti", "clean"]):
            return "graffiti resistance and cleanability for public-facing graphics"
        if any(k in blob for k in ["uv", "weather", "outdoor", "exterior"]):
            return "UV/weather durability for exterior graphics"
        return "durable protective-film performance for graphics and signage"

    def draft(self, stakeholder: Stakeholder) -> OutreachDraft | None:
        facts = self._fact_bundle(stakeholder)
        if not facts:
            return None

        company_facts = [f for f in facts if f["entity_type"] == "company"]
        stakeholder_facts = [f for f in facts if f["entity_type"] == "stakeholder"]
        anchor_company = company_facts[0] if company_facts else facts[0]
        anchor_person = stakeholder_facts[0] if stakeholder_facts else None

        company_signal = self._clean_fact(anchor_company["fact"])
        person_signal = self._clean_fact(anchor_person["fact"]) if anchor_person else stakeholder.title
        angle = self._choose_value_angle(facts)

        email = (
            f"{stakeholder.full_name}, your team’s public materials reference {company_signal}. "
            f"Given your role ({stakeholder.title}), this may connect to {angle}."
        )

        linkedin = (
            f"Hi {stakeholder.full_name} - saw {person_signal}. "
            f"Would a brief comparison of Tedlar options for {angle} be useful?"
        )

        three_sentence = (
            f"I found this signal in public evidence: {company_signal}. "
            f"Your role ({stakeholder.title}) suggests you influence this area. "
            f"If helpful, I can share a concise fit-check on Tedlar for {angle}."
        )

        draft = OutreachDraft(
            stakeholder_id=stakeholder.id,
            email_opener=email,
            linkedin_note=linkedin,
            outreach_three_sentence=three_sentence,
            fact_trace=facts,
            llm_model="rule_based_fact_guard_v2",
            token_usage=0,
            estimated_cost_usd=0.0,
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft
