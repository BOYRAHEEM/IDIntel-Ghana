"""Audit logging service: query, export, and compliance report generation."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.models.identity import AuditEvent


class AuditLogger:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_institution_logs(
        self,
        institution_id: str,
        start_date: date | None,
        end_date: date | None,
        user_id: str | None,
        query_type: str | None,
        page: int,
        per_page: int,
    ) -> tuple[list[dict], int]:
        conditions = [AuditEvent.institution_id == institution_id]

        if start_date:
            conditions.append(AuditEvent.created_at >= datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc))
        if end_date:
            from datetime import timedelta
            conditions.append(AuditEvent.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc))
        if user_id:
            conditions.append(AuditEvent.user_id == user_id)
        if query_type:
            conditions.append(AuditEvent.query_type == query_type)

        where_clause = and_(*conditions)

        count_result = await self._db.execute(
            select(func.count(AuditEvent.id)).where(where_clause)
        )
        total = count_result.scalar() or 0

        result = await self._db.execute(
            select(AuditEvent)
            .where(where_clause)
            .order_by(AuditEvent.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        events = result.scalars().all()

        return [_serialize_event(e) for e in events], total

    async def export_report(
        self,
        institution_id: str,
        start_date: date,
        end_date: date,
        format: str,
        include_signature_chain: bool,
    ) -> str:
        """Generate and upload a compliance report to S3, return pre-signed URL."""
        logs, total = await self.get_institution_logs(
            institution_id=institution_id,
            start_date=start_date,
            end_date=end_date,
            user_id=None,
            query_type=None,
            page=1,
            per_page=min(total := 10000, 10000),
        )

        report_data = {
            "institution_id": institution_id,
            "report_period": {"start": str(start_date), "end": str(end_date)},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_events": total,
            "events": logs,
        }

        if include_signature_chain:
            report_data["signature_chain"] = await self._get_signature_chain(
                institution_id, start_date, end_date
            )

        if format == "json":
            return await self._upload_json_report(institution_id, report_data)
        if format == "csv":
            return await self._upload_csv_report(institution_id, logs)
        if format == "pdf":
            return await self._generate_pdf_report(institution_id, report_data)

        return await self._upload_json_report(institution_id, report_data)

    async def _get_signature_chain(
        self, institution_id: str, start_date: date, end_date: date
    ) -> list[dict]:
        """Return the cryptographic hash chain for audit log integrity verification."""
        result = await self._db.execute(
            select(AuditEvent.sequence_number, AuditEvent.record_signature, AuditEvent.previous_record_hash)
            .where(AuditEvent.institution_id == institution_id)
            .order_by(AuditEvent.sequence_number)
        )
        chain = []
        for row in result.all():
            chain.append({
                "sequence": row.sequence_number,
                "signature": row.record_signature,
                "previous_hash": row.previous_record_hash,
            })
        return chain

    async def _upload_json_report(self, institution_id: str, data: dict) -> str:
        """Upload JSON report to S3 and return pre-signed URL."""
        import boto3
        import json
        from ...shared.config import get_settings

        s = get_settings()
        key = f"audit-exports/{institution_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_audit.json"

        s3 = boto3.client("s3", region_name=s.aws_region)
        s3.put_object(
            Bucket=s.aws_s3_bucket_audit,
            Key=key,
            Body=json.dumps(data, indent=2, default=str).encode(),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=s.aws_kms_audit_key_id,
        )

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": s.aws_s3_bucket_audit, "Key": key},
            ExpiresIn=3600,
        )
        return url

    async def _upload_csv_report(self, institution_id: str, logs: list[dict]) -> str:
        """CSV export — simplified placeholder."""
        return await self._upload_json_report(institution_id, {"logs": logs, "format": "csv"})

    async def _generate_pdf_report(self, institution_id: str, data: dict) -> str:
        """PDF report generation — simplified placeholder."""
        return await self._upload_json_report(institution_id, data)


def _serialize_event(event: AuditEvent) -> dict:
    return {
        "event_id": str(event.id),
        "timestamp": event.created_at.isoformat(),
        "institution_id": event.institution_id,
        "user_id": event.user_id,
        "user_role": event.user_role,
        "request_id": event.request_id,
        "endpoint": event.endpoint,
        "query_type": event.query_type,
        "purpose_code": event.purpose_code,
        "legal_basis": event.legal_basis,
        "subject_id_hash": event.subject_id_hash,
        "response_status": event.response_status,
        "http_status_code": event.http_status_code,
        "response_time_ms": event.response_time_ms,
        "record_signature": event.record_signature,
    }
