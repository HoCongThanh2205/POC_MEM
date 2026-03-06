from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from assets.models import (
    Accessory,
    Asset,
    AssetDocument,
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


class Command(BaseCommand):
    help = "Seed sample assets for PoC"

    def handle(self, *args, **options):
        er = Department.objects.get_or_create(code="ER", defaults={"name": "Khoa Cap cuu"})[0]
        img = Department.objects.get_or_create(code="IMG", defaults={"name": "Khoa Chan doan hinh anh"})[0]
        lab = Department.objects.get_or_create(code="LAB", defaults={"name": "Khoa Xet nghiem"})[0]

        l1 = Location.objects.get_or_create(name="Toa A - Tang 2 - Phong 203")[0]
        l2 = Location.objects.get_or_create(name="Toa B - Tang 1 - Phong SA-02")[0]
        l3 = Location.objects.get_or_create(name="Toa C - Tang 3 - Lab-05")[0]

        v1 = Vendor.objects.get_or_create(name="GE Healthcare")[0]
        v2 = Vendor.objects.get_or_create(name="Philips")[0]
        v3 = Vendor.objects.get_or_create(name="Eppendorf")[0]

        today = date.today()
        now = timezone.now()

        samples = [
            {
                "asset_code": "TB-ICU-2026-00001",
                "standardized_name": "May theo doi benh nhan da thong so",
                "barcode": "QR-0001",
                "asset_type": "MAIN",
                "category_group": "Monitor",
                "risk_class": "Class C",
                "department": er,
                "location": l1,
                "pic_owner": "Nguyen A",
                "operational_status": "IN_USE",
                "inspection_required": True,
                "inspection_last_date": today - timedelta(days=160),
                "inspection_expiry_date": today + timedelta(days=20),
                "pm_required": True,
                "pm_last_date": today - timedelta(days=70),
                "pm_next_due_date": today + timedelta(days=16),
                "commissioning_date": today - timedelta(days=365 * 7),
                "useful_life_years": 8,
                "vendor": v1,
                "manufacturer": "GE",
                "model_name": "MX450",
                "warranty_start_date": today - timedelta(days=365 * 2),
                "warranty_end_date": today + timedelta(days=180),
                "service_contract_id": "SC-1001",
                "serial_number": "SN12345",
                "imei": "",
                "is_disabled": False,
            },
            {
                "asset_code": "TB-IMG-2025-00077",
                "standardized_name": "May sieu am Doppler mau",
                "barcode": "QR-0077",
                "asset_type": "MAIN",
                "category_group": "Ultrasound",
                "risk_class": "Class B",
                "department": img,
                "location": l2,
                "pic_owner": "Tran B",
                "operational_status": "STANDBY",
                "inspection_required": True,
                "inspection_last_date": today - timedelta(days=30),
                "inspection_expiry_date": today + timedelta(days=301),
                "pm_required": True,
                "pm_last_date": today - timedelta(days=40),
                "pm_next_due_date": today + timedelta(days=157),
                "commissioning_date": today - timedelta(days=365 * 2),
                "useful_life_years": 6,
                "vendor": v2,
                "manufacturer": "Philips",
                "model_name": "Affiniti 50",
                "warranty_start_date": today - timedelta(days=200),
                "warranty_end_date": today + timedelta(days=365),
                "service_contract_id": "SC-2002",
                "serial_number": "",
                "imei": "3569...",
                "is_disabled": False,
            },
            {
                "asset_code": "TB-LAB-2024-00310",
                "standardized_name": "May ly tam",
                "barcode": "QR-0310",
                "asset_type": "TOOL",
                "category_group": "Lab Centrifuge",
                "risk_class": "Class A",
                "department": lab,
                "location": l3,
                "pic_owner": "",
                "operational_status": "BROKEN",
                "inspection_required": True,
                "inspection_last_date": today - timedelta(days=370),
                "inspection_expiry_date": today - timedelta(days=35),
                "pm_required": True,
                "pm_last_date": today - timedelta(days=250),
                "pm_next_due_date": today - timedelta(days=21),
                "commissioning_date": today - timedelta(days=365 * 5),
                "useful_life_years": 5,
                "vendor": v3,
                "manufacturer": "Eppendorf",
                "model_name": "5804R",
                "warranty_start_date": today - timedelta(days=365 * 4),
                "warranty_end_date": today - timedelta(days=60),
                "service_contract_id": "",
                "serial_number": "",
                "imei": "",
                "is_disabled": False,
            },
        ]

        created_assets = []
        for row in samples:
            asset, _ = Asset.objects.update_or_create(asset_code=row["asset_code"], defaults=row)
            created_assets.append(asset)

        a = created_assets[0]

        Incident.objects.update_or_create(
            asset=a,
            incident_code="INC-000771",
            defaults={
                "reported_at": now - timedelta(days=15, hours=6),
                "resolved_at": now - timedelta(days=14, hours=20),
                "symptom": "Probe image noise",
                "priority": "HIGH",
                "root_cause": "Cable loose",
                "status": "RESOLVED",
            },
        )
        Incident.objects.update_or_create(
            asset=a,
            incident_code="INC-000702",
            defaults={
                "reported_at": now - timedelta(days=180),
                "resolved_at": now - timedelta(days=179, hours=20),
                "symptom": "Boot failure",
                "priority": "CRITICAL",
                "root_cause": "Power module",
                "status": "CLOSED",
            },
        )

        WorkOrder.objects.update_or_create(
            asset=a,
            wo_code="PM-002318",
            defaults={
                "wo_type": "PM",
                "title": "Quarterly preventive maintenance",
                "technician": "Nguyen A",
                "scheduled_date": today - timedelta(days=70),
                "due_date": today - timedelta(days=65),
                "completed_date": today - timedelta(days=66),
                "checklist_summary": "PASS 18/18",
                "status": "COMPLETED",
            },
        )
        WorkOrder.objects.update_or_create(
            asset=a,
            wo_code="PM-003001",
            defaults={
                "wo_type": "PM",
                "title": "Next PM",
                "technician": "Tran B",
                "scheduled_date": today + timedelta(days=12),
                "due_date": today + timedelta(days=16),
                "completed_date": None,
                "checklist_summary": "",
                "status": "OPEN",
            },
        )

        ComplianceRecord.objects.update_or_create(
            asset=a,
            record_code="CERT-2026-1001",
            defaults={
                "compliance_type": "CALIBRATION",
                "performed_by": "VENDOR",
                "performed_at": today - timedelta(days=140),
                "next_due_at": today + timedelta(days=25),
                "result": "PASS",
                "certificate_name": "cert_calibration_2026.pdf",
            },
        )

        HandoverRecord.objects.update_or_create(
            asset=a,
            doc_id="HD-000129",
            defaults={
                "from_location": "CS2 / ICU / ICU-01",
                "to_location": "CS2 / Imaging / SA-02",
                "custodian_after": "Tran B",
                "handover_date": today - timedelta(days=60),
                "accessories_summary": "2/2 verified",
                "signed": True,
            },
        )

        MovementRecord.objects.update_or_create(
            asset=a,
            moved_at=now - timedelta(days=60),
            defaults={
                "from_location": "CS2 / ICU / ICU-01",
                "to_location": "CS2 / Imaging / SA-02",
                "action_by": "Nguyen A",
                "reason": "Operational transfer",
            },
        )

        Accessory.objects.update_or_create(
            asset=a,
            accessory_name="Convex Probe",
            defaults={
                "code_or_serial": "ACC-PROBE-CVX / SN-PB-7741",
                "quantity": 1,
                "status": "OK",
                "mandatory": True,
                "last_verified_date": today - timedelta(days=60),
                "notes": "Included in handover",
            },
        )

        PartConsumption.objects.update_or_create(
            asset=a,
            consumed_at=today - timedelta(days=14),
            part_code="PC-LOGIQ-09",
            defaults={
                "wo_code": "RP-001045",
                "part_name": "Probe Cable",
                "quantity": 1,
                "batch_info": "LOT#L2409 / 12-2028",
                "issued_store": "Main Store",
                "cost": 3200000,
            },
        )

        AssetDocument.objects.update_or_create(
            asset=a,
            file_name="LOGIQ_P9_UserManual.pdf",
            defaults={
                "doc_type": "Manual",
                "related_to": "Asset Master",
                "updated_at": today - timedelta(days=54),
            },
        )

        self.stdout.write(self.style.SUCCESS("Seeded sample data with detail records."))
