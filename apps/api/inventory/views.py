from django.db import IntegrityError
from rest_framework import status, viewsets
from rest_framework.response import Response

from branches.mixins import BranchRequiredMixin
from tenancy.mixins import OrgScopedViewSetMixin

from .models import Item, StockLedger, StockOnHand
from .serializers import ItemSerializer, StockLedgerSerializer, StockMovementSerializer, StockOnHandSerializer
from .services import record_stock_movement


class ItemViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ItemSerializer
    queryset = Item.all_objects.none()

    def perform_create(self, serializer):
        serializer.save(organization=self.request.org)


class StockOnHandViewSet(OrgScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = StockOnHandSerializer
    queryset = StockOnHand.all_objects.none()


class StockMovementViewSet(
    OrgScopedViewSetMixin,
    BranchRequiredMixin,
    viewsets.GenericViewSet,
):
    serializer_class = StockMovementSerializer
    queryset = Item.all_objects.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = Item.objects.for_org(request.org).filter(id=serializer.validated_data["item"]).first()
        if item is None:
            return Response({"detail": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

        idempotency_key = serializer.validated_data.get("idempotency_key")

        try:
            ledger, created = record_stock_movement(
                org=request.org,
                branch=request.branch,
                item=item,
                quantity=serializer.validated_data["quantity"],
                movement_type=serializer.validated_data["movement_type"],
                performed_by=request.user,
                reference_type=serializer.validated_data.get("reference_type"),
                reference_id=serializer.validated_data.get("reference_id"),
                reason=serializer.validated_data.get("reason"),
                occurred_at=serializer.validated_data.get("occurred_at"),
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            ledger = StockLedger.objects.for_org(request.org).get(idempotency_key=idempotency_key)
            created = False

        out = StockLedgerSerializer(ledger)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out.data, status=status_code)