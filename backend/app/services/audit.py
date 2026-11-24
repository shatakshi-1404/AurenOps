from app.models import AuditLog


def audit(db, org_id, user_id, action, resource_type=None, resource_id=None, run_id=None, details=None):
    db.add(AuditLog(org_id=org_id, user_id=user_id, run_id=run_id, action=action,
                    resource_type=resource_type, resource_id=str(resource_id) if resource_id else None,
                    details=details or {}))
