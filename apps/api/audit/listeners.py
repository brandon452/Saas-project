import logging

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import IntegrityError
from django.dispatch import receiver

from audit.models import AuditEvent
from inventory import signals as inventory_signals
from tenancy.models import Organization

from .services import log_audit_event

logger = logging.getLogger(__name__)


def _audit_exists(*, organization_id: str, event_type: str, resource_id: str) -> bool:
    return AuditEvent.objects.filter(
        organization_id=organization_id,
        event_type=event_type,
        resource_id=resource_id,
    ).exists()


def _safe_log_audit_event(**kwargs):
    try:
        if _audit_exists(
            organization_id=str(kwargs["organization_id"]),
            event_type=kwargs["event_type"],
            resource_id=str(kwargs["resource_id"]),
        ):
            return
        payload = dict(kwargs)
        payload.pop("organization_id", None)
        log_audit_event(**payload)
    except IntegrityError:
        logger.warning(
            "Duplicate audit event ignored: org=%s event=%s resource=%s",
            kwargs["organization_id"],
            kwargs["event_type"],
            kwargs["resource_id"],
            exc_info=True,
        )
    except Exception:
        logger.exception(
            "Audit listener failed: org=%s event=%s resource=%s",
            kwargs.get("organization_id"),
            kwargs.get("event_type"),
            kwargs.get("resource_id"),
        )


def _resolve_org_and_user(organization_id: str, actor_user_id: str | None):
    organization = Organization.objects.filter(pk=organization_id).first()
    if organization is None:
        raise ValueError(f"Organization not found for audit listener: {organization_id}")
    actor_user = None
    if actor_user_id:
        actor_user = get_user_model().objects.filter(pk=actor_user_id).first()
    return organization, actor_user


@receiver(inventory_signals.goods_receipt_posted)
def on_goods_receipt_posted(sender, **kwargs):
    try:
        if not settings.USE_EVENT_AUDIT_GOODS_RECEIPTS:
            return
        organization, actor_user = _resolve_org_and_user(kwargs["organization_id"], kwargs["actor_user_id"])
        _safe_log_audit_event(
            organization_id=kwargs["organization_id"],
            organization=organization,
            actor_user=actor_user,
            event_type="goods_receipt.created",
            resource_type="goods_receipt",
            resource_id=kwargs["receipt_id"],
            summary=f"Created goods receipt {kwargs['receipt_id']}",
            metadata_json={
                "receipt_id": kwargs["receipt_id"],
                "receipt_type": kwargs["receipt_type"],
                "branch_id": kwargs["branch_id"],
                "supplier_id": kwargs["supplier_id"],
                "line_count": kwargs["line_count"],
            },
            diff_json=None,
        )
    except Exception:
        logger.exception("goods_receipt_posted listener failed")


@receiver(inventory_signals.branch_transfer_dispatched)
def on_branch_transfer_dispatched(sender, **kwargs):
    try:
        if not settings.USE_EVENT_AUDIT_BRANCH_TRANSFERS:
            return
        organization, actor_user = _resolve_org_and_user(kwargs["organization_id"], kwargs["actor_user_id"])
        _safe_log_audit_event(
            organization_id=kwargs["organization_id"],
            organization=organization,
            actor_user=actor_user,
            event_type="branch_transfer.dispatched",
            resource_type="branch_transfer",
            resource_id=kwargs["transfer_id"],
            summary=f"Dispatched transfer {kwargs['transfer_id']}",
            metadata_json={"transfer_id": kwargs["transfer_id"]},
            diff_json={"status": {"before": kwargs["before_status"], "after": kwargs["after_status"]}},
        )
    except Exception:
        logger.exception("branch_transfer_dispatched listener failed")


@receiver(inventory_signals.branch_transfer_received)
def on_branch_transfer_received(sender, **kwargs):
    try:
        if not settings.USE_EVENT_AUDIT_BRANCH_TRANSFERS:
            return
        organization, actor_user = _resolve_org_and_user(kwargs["organization_id"], kwargs["actor_user_id"])
        event_type = (
            "branch_transfer.received_complete"
            if kwargs["after_status"] == "RECEIVED_COMPLETE"
            else "branch_transfer.received_with_variance"
        )
        _safe_log_audit_event(
            organization_id=kwargs["organization_id"],
            organization=organization,
            actor_user=actor_user,
            event_type=event_type,
            resource_type="branch_transfer",
            resource_id=kwargs["transfer_id"],
            summary=f"Received transfer {kwargs['transfer_id']}",
            metadata_json={"transfer_id": kwargs["transfer_id"]},
            diff_json={"status": {"before": kwargs["before_status"], "after": kwargs["after_status"]}},
        )
    except Exception:
        logger.exception("branch_transfer_received listener failed")


@receiver(inventory_signals.quick_sale_created)
def on_quick_sale_created(sender, **kwargs):
    try:
        if not settings.USE_EVENT_AUDIT_QUICK_SALES:
            return
        organization, actor_user = _resolve_org_and_user(kwargs["organization_id"], kwargs["actor_user_id"] or None)
        _safe_log_audit_event(
            organization_id=kwargs["organization_id"],
            organization=organization,
            actor_user=actor_user,
            event_type="quick_sale.created",
            resource_type="quick_sale",
            resource_id=kwargs["sale_id"],
            summary=f"Created quick sale {kwargs['sale_id']}",
            metadata_json={
                "sale_id": kwargs["sale_id"],
                "branch_id": kwargs["branch_id"],
                "line_count": kwargs["line_count"],
            },
            diff_json=None,
        )
    except Exception:
        logger.exception("quick_sale_created listener failed")


@receiver(inventory_signals.quick_sale_voided)
def on_quick_sale_voided(sender, **kwargs):
    try:
        if not settings.USE_EVENT_AUDIT_QUICK_SALES:
            return
        organization, actor_user = _resolve_org_and_user(kwargs["organization_id"], kwargs["actor_user_id"] or None)
        _safe_log_audit_event(
            organization_id=kwargs["organization_id"],
            organization=organization,
            actor_user=actor_user,
            event_type="quick_sale.voided",
            resource_type="quick_sale",
            resource_id=kwargs["sale_id"],
            summary=f"Voided quick sale {kwargs['sale_id']}",
            metadata_json={"sale_id": kwargs["sale_id"], "branch_id": kwargs["branch_id"]},
            diff_json=None,
        )
    except Exception:
        logger.exception("quick_sale_voided listener failed")
