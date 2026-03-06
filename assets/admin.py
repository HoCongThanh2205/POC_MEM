from django.contrib import admin

from .models import (
    Accessory,
    Asset,
    AssetDocument,
    AuditLog,
    ComplianceRecord,
    Department,
    HandoverRecord,
    Incident,
    Location,
    MovementRecord,
    PartConsumption,
    Vendor,
    WorkOrder,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name")
    search_fields = ("code", "name")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "asset_code",
        "standardized_name",
        "operational_status",
        "is_disabled",
        "department",
        "updated_at",
    )
    list_filter = ("operational_status", "is_disabled", "department", "asset_type")
    search_fields = ("asset_code", "standardized_name", "serial_number", "imei", "barcode")


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("incident_code", "asset", "status", "reported_at", "resolved_at")
    list_filter = ("status", "priority")


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("wo_code", "asset", "wo_type", "status", "due_date", "completed_date")
    list_filter = ("wo_type", "status")


@admin.register(ComplianceRecord)
class ComplianceRecordAdmin(admin.ModelAdmin):
    list_display = ("record_code", "asset", "compliance_type", "result", "performed_at", "next_due_at")
    list_filter = ("compliance_type", "result")


@admin.register(HandoverRecord)
class HandoverRecordAdmin(admin.ModelAdmin):
    list_display = ("doc_id", "asset", "from_location", "to_location", "handover_date", "signed")


@admin.register(MovementRecord)
class MovementRecordAdmin(admin.ModelAdmin):
    list_display = ("asset", "moved_at", "from_location", "to_location", "action_by")


@admin.register(Accessory)
class AccessoryAdmin(admin.ModelAdmin):
    list_display = ("asset", "accessory_name", "quantity", "status", "mandatory", "last_verified_date")
    list_filter = ("status", "mandatory")


@admin.register(PartConsumption)
class PartConsumptionAdmin(admin.ModelAdmin):
    list_display = ("asset", "consumed_at", "part_code", "part_name", "quantity", "cost")


@admin.register(AssetDocument)
class AssetDocumentAdmin(admin.ModelAdmin):
    list_display = ("asset", "doc_type", "file_name", "related_to", "updated_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("entity_type", "entity_id", "action", "field_name", "actor", "acted_at")
    search_fields = ("entity_type", "action", "field_name", "actor")
    list_filter = ("entity_type", "action")
