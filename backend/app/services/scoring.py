from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Company, CompanyEventLink, Enrichment, EvidenceItem, ScoringRun, Stakeholder


@dataclass(frozen=True)
class ScoreWeights:
    industry_fit: int = 18
    application_fit: int = 16
    durability_adjacency: int = 14
    ecosystem_participation: int = 12
    scale_signal: int = 10
    stakeholder_quality: int = 12
    evidence_confidence: int = 10
    weak_signal_penalty: int = 8


class ScoringService:
    INDUSTRY_KEYWORDS = {"sign", "signage", "graphics", "print", "visual communications", "display"}
    APPLICATION_KEYWORDS = {
        "vehicle wrap",
        "wrap",
        "wallcover",
        "architectural",
        "branded environment",
        "large-format",
        "outdoor graphics",
    }
    DURABILITY_KEYWORDS = {
        "durable",
        "uv",
        "weather",
        "anti-graffiti",
        "graffiti",
        "cleanability",
        "stain",
        "overlaminate",
        "protective film",
    }
    SCALE_KEYWORDS = {"global", "enterprise", "nationwide", "multi-location", "public company"}

    def __init__(self, db: Session):
        self.db = db
        self.weights = ScoreWeights()

    @staticmethod
    def _tier(score: float) -> str:
        if score >= 80:
            return "A"
        if score >= 60:
            return "B"
        return "C"

    @staticmethod
    def _normalize_text(*values: str | None) -> str:
        return " ".join((v or "").lower() for v in values)

    @staticmethod
    def _keyword_density_score(text: str, keywords: set[str], max_points: int) -> tuple[int, list[str]]:
        hits = [kw for kw in keywords if kw in text]
        if not hits:
            return 0, []
        ratio = min(1.0, len(hits) / max(1, int(len(keywords) * 0.35)))
        points = int(round(ratio * max_points))
        return points, sorted(hits)

    def score_company(self, company: Company) -> ScoringRun:
        evidence_items = (
            self.db.query(EvidenceItem)
            .filter(EvidenceItem.entity_type == "company", EvidenceItem.entity_id == company.id)
            .all()
        )
        links = self.db.query(CompanyEventLink).filter(CompanyEventLink.company_id == company.id).all()
        stakeholders = self.db.query(Stakeholder).filter(Stakeholder.company_id == company.id).all()
        enrichments = self.db.query(Enrichment).filter(Enrichment.company_id == company.id).all()

        evidence_text = " ".join(item.evidence_snippet for item in evidence_items)
        source_count = len({item.source_url for item in evidence_items})
        enrichment_text = " ".join(str((en.raw_payload or {})) for en in enrichments)
        company_text = self._normalize_text(
            company.industry,
            company.description,
            " ".join(company.relevant_product_lines or []),
            enrichment_text,
            evidence_text,
        )

        industry_points, industry_hits = self._keyword_density_score(
            company_text,
            self.INDUSTRY_KEYWORDS,
            self.weights.industry_fit,
        )
        application_points, application_hits = self._keyword_density_score(
            company_text,
            self.APPLICATION_KEYWORDS,
            self.weights.application_fit,
        )
        durability_points, durability_hits = self._keyword_density_score(
            company_text,
            self.DURABILITY_KEYWORDS,
            self.weights.durability_adjacency,
        )

        ecosystem_points = min(self.weights.ecosystem_participation, len(links) * 3)

        scale_points = 0
        scale_reasons: list[str] = []
        if company.employee_count_range:
            scale_points += 4
            scale_reasons.append("employee_count_present")
        if company.revenue_estimate:
            scale_points += 4
            scale_reasons.append("revenue_estimate_present")
        scale_keyword_points, scale_hits = self._keyword_density_score(
            company_text,
            self.SCALE_KEYWORDS,
            max_points=2,
        )
        scale_points = min(self.weights.scale_signal, scale_points + scale_keyword_points)
        scale_reasons.extend(scale_hits)

        stakeholder_points = 0
        stakeholder_reasons: list[str] = []
        if stakeholders:
            avg_stakeholder_conf = sum(s.confidence_score for s in stakeholders) / len(stakeholders)
            stakeholder_points = min(self.weights.stakeholder_quality, int(round(avg_stakeholder_conf * self.weights.stakeholder_quality)))
            stakeholder_reasons.append(f"stakeholders={len(stakeholders)}")
            stakeholder_reasons.append(f"avg_conf={avg_stakeholder_conf:.2f}")

        evidence_confidence_points = 0
        if evidence_items:
            density_component = min(0.6, len(evidence_items) / 20)
            diversity_component = min(0.4, source_count / 8)
            evidence_confidence_points = int(round((density_component + diversity_component) * self.weights.evidence_confidence))

        penalty = 0
        disqualifiers: list[str] = []
        caveats: list[str] = []

        if not evidence_items:
            penalty += 6
            disqualifiers.append("No company-level evidence items found.")
        if not links:
            penalty += 2
            caveats.append("No ecosystem participation link found.")
        if stakeholder_points == 0:
            penalty += 2
            caveats.append("No qualified stakeholder found.")
        if industry_points == 0 and application_points == 0:
            penalty += 4
            disqualifiers.append("No industry/application fit signal found in evidence.")

        penalty = min(self.weights.weak_signal_penalty, penalty)

        raw_total = (
            industry_points
            + application_points
            + durability_points
            + ecosystem_points
            + scale_points
            + stakeholder_points
            + evidence_confidence_points
            - penalty
        )
        total = float(max(0, min(100, raw_total)))

        factors = {
            "industry_fit": {"score": industry_points, "max": self.weights.industry_fit, "hits": industry_hits},
            "application_fit": {
                "score": application_points,
                "max": self.weights.application_fit,
                "hits": application_hits,
            },
            "durability_adjacency": {
                "score": durability_points,
                "max": self.weights.durability_adjacency,
                "hits": durability_hits,
            },
            "ecosystem_participation": {
                "score": ecosystem_points,
                "max": self.weights.ecosystem_participation,
                "link_count": len(links),
            },
            "scale_signal": {"score": scale_points, "max": self.weights.scale_signal, "signals": scale_reasons},
            "stakeholder_quality": {
                "score": stakeholder_points,
                "max": self.weights.stakeholder_quality,
                "signals": stakeholder_reasons,
            },
            "evidence_confidence": {
                "score": evidence_confidence_points,
                "max": self.weights.evidence_confidence,
                "evidence_count": len(evidence_items),
                "source_count": source_count,
            },
            "weak_signal_penalty": {"score": -penalty, "max": self.weights.weak_signal_penalty},
        }

        explanations = [
            f"Industry fit: {industry_points}/{self.weights.industry_fit} from {len(industry_hits)} signal hits.",
            f"Application fit: {application_points}/{self.weights.application_fit} from {len(application_hits)} use-case hits.",
            f"Durability adjacency: {durability_points}/{self.weights.durability_adjacency} from protective-surface signals.",
            f"Ecosystem participation: {ecosystem_points}/{self.weights.ecosystem_participation} from {len(links)} links.",
            f"Scale signal: {scale_points}/{self.weights.scale_signal} from enrichment/profile data.",
            f"Stakeholder quality: {stakeholder_points}/{self.weights.stakeholder_quality} from stakeholder confidence.",
            f"Evidence confidence: {evidence_confidence_points}/{self.weights.evidence_confidence} from evidence depth/diversity.",
            f"Weak-signal penalty: -{penalty}/{self.weights.weak_signal_penalty}.",
        ]

        disqualifiers.extend([f"Caveat: {c}" for c in caveats])

        confidence = min(
            1.0,
            0.2
            + min(0.35, len(evidence_items) * 0.02)
            + min(0.2, source_count * 0.03)
            + min(0.15, len(stakeholders) * 0.05)
            + min(0.1, len(links) * 0.03),
        )

        run = ScoringRun(
            company_id=company.id,
            total_score=total,
            tier=self._tier(total),
            confidence=confidence,
            factors=factors,
            explanation_bullets=explanations,
            disqualifiers=disqualifiers,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run
