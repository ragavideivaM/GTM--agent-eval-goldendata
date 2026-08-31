"""Versioned evaluation bundles and deterministic grounding-reference checks."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from evaluations.content_suite import EvaluationCheck, EvaluationReport, evaluate_suite
from models.brief import WeeklyResearchBrief
from models.content import ContentClaim, ContentSuite, ReviewedContentSuite


class EvaluationBundle(BaseModel):
    """Artifacts required to reproduce deterministic post-generation evaluations."""

    schema_version: int = Field(default=1, ge=1)
    saved_at: datetime
    research_brief: WeeklyResearchBrief
    original_content: ContentSuite
    review_result: ReviewedContentSuite


def _used_evidence_ids(suite: ContentSuite) -> set[str]:
    claim_groups: list[list[ContentClaim]] = [
        suite.linkedin.claims_used,
        suite.email.claims_used,
        suite.blog.claims_used,
        *(ad.claims_used for ad in suite.ad_variations),
    ]
    return {
        evidence_id
        for claims in claim_groups
        for claim in claims
        for evidence_id in claim.evidence_chunk_ids
    }


def evaluate_bundle(bundle: EvaluationBundle) -> EvaluationReport:
    """Evaluate the final suite and its evidence references against the brief."""
    final_report = evaluate_suite(
        bundle.review_result.revised_content,
        campaign_type=bundle.research_brief.campaign_type,
    )
    known_ids = {
        evidence_id
        for story in bundle.research_brief.stories
        for claim in story.claims
        for evidence_id in claim.evidence_chunk_ids
    }
    original_unknown = _used_evidence_ids(bundle.original_content) - known_ids
    revised_unknown = (
        _used_evidence_ids(bundle.review_result.revised_content) - known_ids
    )
    review = bundle.review_result.report
    review_integrity = not review.approved or not (
        review.unsupported_claims or review.required_revisions
    )
    bundle_checks = (
        EvaluationCheck(
            "Original evidence grounding",
            not original_unknown,
            "all evidence IDs exist in the research brief"
            if not original_unknown
            else "unknown IDs: " + ", ".join(sorted(original_unknown)),
        ),
        EvaluationCheck(
            "Revised evidence grounding",
            not revised_unknown,
            "all evidence IDs exist in the research brief"
            if not revised_unknown
            else "unknown IDs: " + ", ".join(sorted(revised_unknown)),
        ),
        EvaluationCheck(
            "Review resolution integrity",
            review_integrity,
            "approved review has no unresolved issues"
            if review_integrity
            else "approved review still contains unresolved issues",
        ),
    )
    return EvaluationReport(checks=final_report.checks + bundle_checks)


def save_evaluation_bundle(
    brief: WeeklyResearchBrief,
    original_content: ContentSuite,
    review_result: ReviewedContentSuite,
    output_directory: str | Path,
) -> Path:
    """Atomically save an approved review bundle and return its final path."""
    if not review_result.report.approved:
        raise ValueError("Only approved review results can be saved as eval bundles.")
    bundle = EvaluationBundle(
        saved_at=datetime.now(timezone.utc),
        research_brief=brief,
        original_content=original_content,
        review_result=review_result,
    )
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = bundle.saved_at.strftime("%Y%m%dT%H%M%S%fZ")
    destination = directory / f"{brief.week_id}-{timestamp}-evaluation-bundle.json"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".evaluation-bundle-",
        suffix=".tmp",
        dir=directory,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(bundle.model_dump_json(indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination

