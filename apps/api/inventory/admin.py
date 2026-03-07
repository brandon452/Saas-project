from django.contrib import admin

from .models import Item, StockLedger, StockOnHand

admin.site.register(Item)
admin.site.register(StockOnHand)
admin.site.register(StockLedger)

