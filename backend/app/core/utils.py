from sqlalchemy import inspect, select

from app.core.errors import not_found


def to_dict(obj, exclude=()):
    return {a.key: getattr(obj, a.key) for a in inspect(obj).mapper.column_attrs if a.key not in exclude}


def get_scoped(db, model, id_, org_id):
    """Every tenant-owned lookup goes through here: id AND org_id."""
    obj = db.scalar(select(model).where(model.id == id_, model.org_id == org_id))
    if not obj:
        raise not_found(model.__name__)
    return obj
