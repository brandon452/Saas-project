from django.contrib import admin

from .models import MasterItem, OrgItem, StockLedger, StockOnHand

admin.site.register(MasterItem)
admin.site.register(OrgItem)
admin.site.register(StockOnHand)
admin.site.register(StockLedger)

