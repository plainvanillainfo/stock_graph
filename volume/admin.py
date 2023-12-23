from django.contrib import admin

from .models import DataDay, Symbol, Chart, Correlation, MarketHoliday, SystemSetting


@admin.register(DataDay)
class DataDayAdmin(admin.ModelAdmin):
    date_hierarchy = "day"
    list_display = ("symbol", "day", "state", "last_tried")
    list_filter = ("state", )


@admin.register(Symbol)
class SymbolAdmin(admin.ModelAdmin):
    list_display = ("symbol", "type", "active")
    list_filter = ("type", "active" )


@admin.register(MarketHoliday)
class MarketHolidayAdmin(admin.ModelAdmin):
    list_display = ("day", "status", "exchange", "name")
    list_filter = ("status", "exchange")


@admin.register(Chart)
class ChartAdmin(admin.ModelAdmin):
    list_display = ("name", )


@admin.register(Correlation)
class CorrelationAdmin(admin.ModelAdmin):
    date_hierarchy = "day"
    list_display = ("symbol", "day", "data_type", )
    list_filter = ("data_type", )


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("name", "value")
