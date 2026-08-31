"""Offline quality gates for a structured GTM content suite."""

from dataclasses import dataclass
from typing import Iterable

from models.campaign import CampaignType
from models.content import ContentClaim, ContentSuite


RISKY_PHRASES = (
    "best-in-class",
    "industry-leading",
    "10x",
    "100%",
    "guaranteed",
    "trusted by thousands",
    "award-winning",
    "revolutionary",
    "game-changing",
    "customers love",
    "teams love",
    "users love",
)


@dataclass(frozen=True)
class EvaluationCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class EvaluationReport:
    checks: tuple[EvaluationCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def _claim_ids(claims: Iterable[ContentClaim]) -> set[str]:
    return {
        evidence_id.strip()
        for claim in claims
        for evidence_id in claim.evidence_chunk_ids
        if evidence_id.strip()
    }


def _all_reader_copy(suite: ContentSuite) -> list[str]:
    return [
        suite.linkedin.post,
        *suite.email.subject_lines,
        suite.email.preview_text,
        suite.email.body,
        suite.blog.title,
        suite.blog.body,
        *(f"{ad.headline} {ad.ad_copy}" for ad in suite.ad_variations),
    ]


def evaluate_suite(
    suite: ContentSuite,
    *,
    campaign_type: CampaignType = CampaignType.NEWSLETTER,
) -> EvaluationReport:
    """Evaluate deterministic requirements without calling external services."""
    linkedin_words = len(suite.linkedin.post.split())
    blog_words = len(suite.blog.body.split())
    individual_asset_claim_groups = {
        "LinkedIn": suite.linkedin.claims_used,
        "email": suite.email.claims_used,
        "blog": suite.blog.claims_used,
        **{
            f"ad {index}": ad.claims_used
            for index, ad in enumerate(suite.ad_variations, start=1)
        },
    }
    ids_by_individual_asset = {
        asset: _claim_ids(claims)
        for asset, claims in individual_asset_claim_groups.items()
    }
    missing_claim_assets = [
        asset for asset, ids in ids_by_individual_asset.items() if not ids
    ]
    # Ads are variations within one output format. Require each variation to cite
    # evidence above, but aggregate their IDs for cross-format consistency.
    ids_by_format = {
        "LinkedIn": ids_by_individual_asset["LinkedIn"],
        "email": ids_by_individual_asset["email"],
        "blog": ids_by_individual_asset["blog"],
        "ads": set().union(
            *(
                ids_by_individual_asset[f"ad {index}"]
                for index in range(1, len(suite.ad_variations) + 1)
            )
        ),
    }
    shared_ids = (
        set.intersection(*ids_by_format.values()) if ids_by_format else set()
    )
    cta_terms = {
        CampaignType.NEWSLETTER: ("subscribe",),
        CampaignType.FEATURE: ("learn more", "explore", "try"),
        CampaignType.UPCOMING_EVENT: ("register", "join", "attend", "sign up"),
    }[campaign_type]
    cta_copy = {
        "LinkedIn": suite.linkedin.post,
        "email": suite.email.body,
        "blog": suite.blog.body,
        **{
            f"ad {index}": ad.ad_copy
            for index, ad in enumerate(suite.ad_variations, start=1)
        },
    }
    missing_ctas = [
        asset
        for asset, text in cta_copy.items()
        if not any(term in text.lower() for term in cta_terms)
    ]
    combined_copy = "\n".join(_all_reader_copy(suite)).lower()
    found_risky = [phrase for phrase in RISKY_PHRASES if phrase in combined_copy]

    checks = (
        EvaluationCheck(
            "LinkedIn length",
            100 <= linkedin_words <= 350,
            f"{linkedin_words} words; required 100-350",
        ),
        EvaluationCheck(
            "Blog length",
            500 <= blog_words <= 1_200,
            f"{blog_words} words; required 500-1,200",
        ),
        EvaluationCheck(
            "Email structure",
            len(suite.email.subject_lines) == 3,
            f"{len(suite.email.subject_lines)} subject lines; required exactly 3",
        ),
        EvaluationCheck(
            "Ad count",
            3 <= len(suite.ad_variations) <= 5,
            f"{len(suite.ad_variations)} variations; required 3-5",
        ),
        EvaluationCheck(
            "CTA coverage",
            not missing_ctas,
            "all assets contain the campaign CTA"
            if not missing_ctas
            else "missing in: " + ", ".join(missing_ctas),
        ),
        EvaluationCheck(
            "Evidence references",
            not missing_claim_assets,
            "every asset contains non-empty evidence IDs"
            if not missing_claim_assets
            else "missing in: " + ", ".join(missing_claim_assets),
        ),
        EvaluationCheck(
            "Cross-format evidence consistency",
            bool(shared_ids),
            f"{len(shared_ids)} evidence ID(s) shared by every format",
        ),
        EvaluationCheck(
            "Risky phrase check",
            not found_risky,
            "no obvious unsupported marketing phrases"
            if not found_risky
            else "found: " + ", ".join(found_risky),
        ),
    )
    return EvaluationReport(checks=checks)
