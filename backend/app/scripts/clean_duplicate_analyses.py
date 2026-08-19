"""
Maintenance script for safely cleaning historical duplicate document_extraction AIAnalysis records.
Preserves QA records, single records, and the latest valid extraction per document.
"""

import argparse
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.ai_analysis import AIAnalysis
from app.models.document import Document

logger = logging.getLogger(__name__)


def clean_duplicate_ai_analyses(
    db: Session,
    patient_id: Optional[UUID] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Safely identifies and removes historical duplicate document_extraction AIAnalysis records.

    Rules:
    - Only targets analysis_type = "document_extraction".
    - Never deletes QA records ("qa") or any medical entity tables (findings, prescriptions, etc.).
    - Groups records by (patient_id, document_id).
    - Preserves the latest (newest created_at) record for each document.
    - Preserves unidentifiable legacy records when document identity cannot be established safely.
    - Supports dry_run mode (default True) to report actions without modifying database.

    Returns:
        Summary dict containing total scanned, duplicate count, deleted count, and dry_run status.
    """
    query = db.query(AIAnalysis).filter(AIAnalysis.analysis_type == "document_extraction")
    if patient_id:
        query = query.filter(AIAnalysis.patient_id == patient_id)

    records = query.order_by(AIAnalysis.created_at.desc()).all()

    # Fetch mapping of patient_id -> list of document_ids to resolve legacy records if possible
    doc_query = db.query(Document)
    if patient_id:
        doc_query = doc_query.filter(Document.patient_id == patient_id)
    all_docs = doc_query.all()

    patient_docs: Dict[UUID, List[str]] = {}
    for d in all_docs:
        p_id = d.patient_id if isinstance(d.patient_id, UUID) else UUID(str(d.patient_id))
        d_id = str(d.id)
        if p_id not in patient_docs:
            patient_docs[p_id] = []
        patient_docs[p_id].append(d_id)

    # Group records by (patient_id, document_id)
    grouped: Dict[tuple, List[AIAnalysis]] = {}
    unmapped: List[AIAnalysis] = []

    for rec in records:
        rec_p_id = rec.patient_id if isinstance(rec.patient_id, UUID) else UUID(str(rec.patient_id))
        doc_id_str = None
        if isinstance(rec.result, dict):
            doc_id_str = rec.result.get("document_id")

        if not doc_id_str:
            # Check if patient has exactly 1 document
            docs_for_p = patient_docs.get(rec_p_id, [])
            if len(docs_for_p) == 1:
                doc_id_str = docs_for_p[0]

        if doc_id_str:
            key = (rec_p_id, doc_id_str)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(rec)
        else:
            # Cannot safely associate with a specific document -> preserve record safely
            unmapped.append(rec)

    to_delete: List[AIAnalysis] = []
    kept: List[AIAnalysis] = []

    for key, group in grouped.items():
        # Sort newest first
        sorted_group = sorted(group, key=lambda x: x.created_at, reverse=True)
        kept.append(sorted_group[0])
        to_delete.extend(sorted_group[1:])

    deleted_count = 0
    if not dry_run and to_delete:
        for item in to_delete:
            db.delete(item)
        db.commit()
        deleted_count = len(to_delete)

    summary = {
        "dry_run": dry_run,
        "total_scanned": len(records),
        "unique_groups": len(grouped),
        "kept_records": len(kept) + len(unmapped),
        "duplicates_identified": len(to_delete),
        "records_deleted": deleted_count if not dry_run else 0,
        "unmapped_preserved": len(unmapped),
    }

    logger.info("AIAnalysis cleanup summary (dry_run=%s): %s", dry_run, summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Clean duplicate document_extraction AIAnalysis records.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute deletion (default is dry-run report only).",
    )
    parser.add_argument(
        "--patient-id",
        type=str,
        default=None,
        help="Optional UUID of specific patient to clean.",
    )
    args = parser.parse_args()

    patient_uuid = UUID(args.patient_id) if args.patient_id else None
    dry_run = not args.execute

    db = SessionLocal()
    try:
        res = clean_duplicate_ai_analyses(db=db, patient_id=patient_uuid, dry_run=dry_run)
        print(f"Cleanup Complete: {res}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
