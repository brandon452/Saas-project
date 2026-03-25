from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from tenancy.mixins import OrgScopedViewSetMixin
from tenancy.permissions import (
    IsOrgOperationalUser,
    ROLE_POLICY,
    RolePolicyMixin,
    get_member_role,
    get_org_membership,
    get_parent_membership,
)

from .models import BranchTransfer, BranchTransferLine
from .serializers import (
    BranchTransferCreateSerializer,
    BranchTransferReceiveSerializer,
    BranchTransferSerializer,
)
from .services import dispatch_transfer, receive_transfer


class BranchTransferViewSet(RolePolicyMixin, OrgScopedViewSetMixin, ModelViewSet):
    permission_resource = "branch_transfers"
    queryset = BranchTransfer.all_objects.none()
    permission_classes = OrgScopedViewSetMixin.permission_classes + [IsOrgOperationalUser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        permissions = [permission() for permission in self.permission_classes]
        if self.action in ("update", "partial_update", "destroy"):
            return permissions

        policy_action = "dispatch" if self.action == "dispatch_transfer" else self.action
        allowed_roles = ROLE_POLICY.get(self.permission_resource, {}).get(policy_action)
        if allowed_roles is None:
            return permissions

        class _ActionRolePermission(BasePermission):
            def has_permission(self_inner, request, view):
                parent = get_parent_membership(request)
                if parent:
                    return request.method in ("GET", "HEAD", "OPTIONS")
                role = get_member_role(request)
                return role in allowed_roles

        permissions.append(_ActionRolePermission())
        return permissions

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH")

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH")

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE")

    def get_queryset(self):
        parent_membership = get_parent_membership(self.request)
        if parent_membership:
            return (
                BranchTransfer.all_objects
                .select_related(
                    "from_branch",
                    "to_branch",
                    "to_organization",
                    "organization",
                    "created_by",
                    "approved_by",
                    "received_by",
                )
                .prefetch_related("lines__item__master_item")
                .order_by("-created_at")
            )

        org = self.request.org
        return (
            BranchTransfer.all_objects
            .filter(Q(organization=org) | Q(to_organization=org))
            .select_related(
                "from_branch",
                "to_branch",
                "to_organization",
                "organization",
                "created_by",
                "approved_by",
                "received_by",
            )
            .prefetch_related("lines__item__master_item")
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "create":
            return BranchTransferCreateSerializer
        if self.action == "receive":
            return BranchTransferReceiveSerializer
        return BranchTransferSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        out = BranchTransferSerializer(serializer.instance, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def perform_create(self, serializer):
        lines_data = serializer.validated_data["lines"]
        to_branch = serializer.validated_data["to_branch"]

        transfer = serializer.save(
            organization=self.request.org,
            to_organization=to_branch.organization,
            created_by=self.request.user,
        )

        for line_data in lines_data:
            BranchTransferLine.objects.create(
                transfer=transfer,
                item=line_data["item"],
                quantity_sent=line_data["quantity_sent"],
            )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, *args, **kwargs):
        transfer = self.get_object()

        membership = get_org_membership(request)
        if not membership or membership.organization != transfer.organization:
            return Response(
                {"detail": "Only the sending organisation can approve this transfer."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not transfer.can_transition_to(BranchTransfer.APPROVED):
            return Response(
                {"detail": f"Cannot approve a transfer with status {transfer.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transfer.status = BranchTransfer.APPROVED
        transfer.approved_by = request.user
        transfer.save(update_fields=["status", "approved_by", "updated_at"])
        return Response(BranchTransferSerializer(transfer).data)

    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_transfer(self, request, *args, **kwargs):
        transfer = self.get_object()

        membership = get_org_membership(request)
        if not membership or membership.organization != transfer.organization:
            return Response(
                {"detail": "Only the sending organisation can dispatch this transfer."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            dispatch_transfer(transfer=transfer, performed_by=request.user)
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages})

        transfer.refresh_from_db()
        return Response(BranchTransferSerializer(transfer).data)

    @action(detail=True, methods=["post"], url_path="receive")
    def receive(self, request, *args, **kwargs):
        transfer = self.get_object()

        membership = get_org_membership(request)
        if not membership or membership.organization != transfer.to_organization:
            return Response(
                {"detail": "Only the receiving organisation can confirm receipt."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BranchTransferReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            receive_transfer(
                transfer=transfer,
                lines_data=serializer.validated_data["lines"],
                performed_by=request.user,
                receive_notes=serializer.validated_data.get("notes", ""),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages})

        transfer.refresh_from_db()
        return Response(BranchTransferSerializer(transfer).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, *args, **kwargs):
        transfer = self.get_object()

        membership = get_org_membership(request)
        if not membership or membership.organization != transfer.organization:
            return Response(
                {"detail": "Only the sending organisation can cancel this transfer."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not transfer.can_transition_to(BranchTransfer.CANCELLED):
            return Response(
                {"detail": f"Cannot cancel a transfer with status {transfer.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transfer.status = BranchTransfer.CANCELLED
        transfer.save(update_fields=["status", "updated_at"])
        return Response(BranchTransferSerializer(transfer).data)
