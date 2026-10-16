from web.staff.models import StaffAuditEvent


def record_staff_action(request, action, obj):
    """Call inside the same transaction as the mutation; never log form payloads."""
    return StaffAuditEvent.objects.create(
        actor=request.user, action=action,
        object_type=obj._meta.label_lower, object_id=str(obj.pk),
    )
