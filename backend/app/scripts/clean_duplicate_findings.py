"""
Maintenance script for safely cleaning historical duplicate legacy Finding records (source_document_id IS NULL).

Rules:
- Never globally collapse findings only by title across patients or across different documents.
- Preserves all document-linked findings (source_document_id IS NOT NULL).
- Preserves legacy findings when document identity is ambiguous (multiple document-linked matches exist for same patient + title).
- Preserves legacy findings when no document-linked match exists (unmapped).
- Only targets legacy NULL-source findings that have exactly ONE clear matching document-linked finding for the same patient + title.
- Supports dry-run mode (default True) to report candidate deletions without modifying the database.
"""

import argparse
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.document import Document
from app.models.finding import Finding

logger = logging.getLogger(__name__)


def clean_duplicate_findings(
    db: Session,
    patient_id: Optional[UUID] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Safely identifies and optionally removes historical duplicate legacy Finding records.

    Args:
        db: SQLAlchemy database session.
        patient_id: Optional UUID filter for a specific patient.
        dry_run: If True (default), simulates cleanup and returns candidates without database deletion.

    Returns:
        Summary dictionary containing counts, classifications, and candidate details.
    """
    query = db.query(Finding)
    if patient_id:
        query = query.filter(Finding.patient_id == patient_id)

    all_findings = query.all()

    # Pre-fetch documents to resolve filenames
    doc_query = db.query(Document)
    if patient_id:
        doc_query = doc_query.filter(Document.patient_id == patient_id)
    documents = doc_query.all()
    doc_filename_map: Dict[UUID, str] = {d.id: d.file_name for d in documents}

    # Separate into document-linked findings and legacy NULL-source findings
    doc_linked_findings: List[Finding] = []
    legacy_null_findings: List[Finding] = []

    for f in all_findings:
        if f.source_document_id is not None:
            doc_linked_findings.append(f)
        else:
            legacy_null_findings.append(f)

    # Group document-linked findings by (patient_id, title)
    doc_linked_by_patient_title: Dict[tuple, List[Finding]] = {}
    for f in doc_linked_findings:
        p_id = f.patient_id if isinstance(f.patient_id, UUID) else UUID(str(f.patient_id))
        key = (p_id, f.title)
        if key not in doc_linked_by_patient_title:
            doc_linked_by_patient_title[key] = []
        doc_linked_by_patient_title[key].append(f)

    safe_candidates: List[Finding] = []
    ambiguous_findings: List[Finding] = []
    unmapped_findings: List[Finding] = []
    candidates_details: List[Dict[str, Any]] = []

    for legacy_f in legacy_null_findings:
        p_id = legacy_f.patient_id if isinstance(legacy_f.patient_id, UUID) else UUID(str(legacy_f.patient_id))
        key = (p_id, legacy_f.title)

        matching_doc_linked = doc_linked_by_patient_title.get(key, [])

        if len(matching_doc_linked) == 1:
            target_finding = matching_doc_linked[0]
            target_doc_id = target_finding.source_document_id
            doc_filename = doc_filename_map.get(target_doc_id, "Unknown") if target_doc_id else "Unknown"

            safe_candidates.append(legacy_f)
            candidates_details.append({
                "legacy_finding_id": str(legacy_f.id),
                "patient_id": str(p_id),
                "title": legacy_f.title,
                "created_at": str(legacy_f.created_at),
                "legacy_source_document_id": None,
                "matching_current_finding_id": str(target_finding.id),
                "matching_current_source_document_id": str(target_doc_id) if target_doc_id else None,
                "matching_document_filename": doc_filename,
            })
        elif len(matching_doc_linked) > 1:
            # Multiple possible document-linked matches -> Ambiguous, preserve safely
            ambiguous_findings.append(legacy_f)
        else:
            # No document-linked matches -> Unmapped, preserve safely
            unmapped_findings.append(legacy_f)

    deleted_count = 0
    if not dry_run and safe_candidates:
        try:
            for item in safe_candidates:
                db.delete(item)
            db.commit()
            deleted_count = len(safe_candidates)
        except Exception:
            db.rollback()
            raise

    summary = {
        "dry_run": dry_run,
        "total_inspected": len(all_findings),
        "document_linked_preserved": len(doc_linked_findings),
        "legacy_null_total": len(legacy_null_findings),
        "safe_candidates": len(safe_candidates),
        "ambiguous_preserved": len(ambiguous_findings),
        "unmapped_preserved": len(unmapped_findings),
        "records_deleted": deleted_count if not dry_run else 0,
        "candidates_details": candidates_details,
    }

    logger.info("Finding cleanup summary (dry_run=%s): %s", dry_run, summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Safely clean historical duplicate legacy Finding records.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute deletion of safe legacy duplicates (default is dry-run report only).",
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
        res = clean_duplicate_findings(db=db, patient_id=patient_uuid, dry_run=dry_run)
        print(f"\n--- Finding Cleanup Summary (dry_run={res['dry_run']}) ---")
        print(f"Total Findings Inspected: {res['total_inspected']}")
        print(f"Document-Linked Findings Preserved: {res['document_linked_preserved']}")
        print(f"Legacy NULL-Source Findings Total: {res['legacy_null_total']}")
        print(f"  |- Safe Duplicate Candidates: {res['safe_candidates']}")
        print(f"  |- Ambiguous Legacy Findings Preserved: {res['ambiguous_preserved']}")
        print(f"  |- Unmapped Legacy Findings Preserved: {res['unmapped_preserved']}")
        print(f"Records Deleted: {res['records_deleted']}")

        if res["candidates_details"]:
            print("\n--- Safe Candidate Deletions Detail ---")
            for c in res["candidates_details"][:20]:  # Limit output to 20 lines for readability
                print(
                    f"Legacy ID: {c['legacy_finding_id']} | Title: '{c['title']}' | "
                    f"Created: {c['created_at']} -> Matches Current ID: {c['matching_current_finding_id']} "
                    f"(Doc: {c['matching_document_filename']})"
                )
            if len(res["candidates_details"]) > 20:
                print(f"... and {len(res['candidates_details']) - 20} more candidates.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
