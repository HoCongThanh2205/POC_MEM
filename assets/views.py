import json
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

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


INSPECTION_WARNING_DAYS = getattr(settings, "INSPECTION_WARNING_DAYS", 30)
PM_WARNING_DAYS = getattr(settings, "PM_WARNING_DAYS", 30)
LIFE_WARNING_DAYS = getattr(settings, "LIFE_WARNING_DAYS", 60)


def _json_response(data, status=200):
    return JsonResponse(data, status=status, safe=True, json_dumps_params={"default": str})


def login_page(request):
    if request.user.is_authenticated:
        return redirect("asset-list-page")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get("next") or request.GET.get("next") or "/"
            return redirect(next_url)
        messages.error(request, "Tên đăng nhập hoặc mật khẩu không đúng.")

    return render(request, "auth/login.html")


def register_page(request):
    if request.user.is_authenticated:
        return redirect("asset-list-page")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""

        if not username:
            messages.error(request, "Vui lòng nhập tên đăng nhập.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Tên đăng nhập đã tồn tại.")
        elif password != confirm_password:
            messages.error(request, "Mật khẩu xác nhận không khớp.")
        elif len(password) < 8:
            messages.error(request, "Mật khẩu cần tối thiểu 8 ký tự.")
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            return redirect("asset-list-page")

    return render(request, "auth/register.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login-page")


def _serialize_asset(asset: Asset):
    inspection_status, inspection_days = asset.inspection_status(INSPECTION_WARNING_DAYS)
    pm_status, pm_days = asset.pm_status(PM_WARNING_DAYS)
    eol_status, eol_days, eol_date = asset.eol_status(LIFE_WARNING_DAYS)

    return {
        "id": asset.id,
        "asset_code": asset.asset_code,
        "standardized_name": asset.standardized_name,
        "asset_type": asset.asset_type,
        "category_group": asset.category_group,
        "department": asset.department.name if asset.department else None,
        "location": asset.location.name if asset.location else None,
        "pic_owner": asset.pic_owner,
        "operational_status": asset.effective_operational_status,
        "inspection": {
            "status": inspection_status,
            "days_remaining": inspection_days,
            "expiry_date": asset.inspection_expiry_date,
        },
        "pm": {
            "status": pm_status,
            "days_remaining": pm_days,
            "next_due_date": asset.pm_next_due_date,
        },
        "eol": {
            "status": eol_status,
            "days_remaining": eol_days,
            "expiry_date": eol_date,
        },
        "vendor": asset.vendor.name if asset.vendor else None,
        "manufacturer": asset.manufacturer,
        "model_name": asset.model_name,
        "warranty_end_date": asset.warranty_end_date,
        "serial_number": asset.serial_number,
        "imei": asset.imei,
        "updated_at": asset.updated_at,
        "is_disabled": asset.is_disabled,
    }


def _apply_status_filters(items, params):
    operational = params.get("operational_status", "all").lower()
    inspection = params.get("inspection_status", "all").lower()
    pm = params.get("pm_status", "all").lower()
    department_id = params.get("department_id", "all")

    filtered = items

    if operational != "all":
        filtered = [a for a in filtered if a.effective_operational_status.lower() == operational]

    if inspection != "all":
        filtered = [
            a
            for a in filtered
            if a.inspection_status(INSPECTION_WARNING_DAYS)[0].lower() == inspection
        ]

    if pm != "all":
        filtered = [a for a in filtered if a.pm_status(PM_WARNING_DAYS)[0].lower() == pm]

    if department_id not in {"", "all", None}:
        try:
            dep_id = int(department_id)
            filtered = [a for a in filtered if a.department_id == dep_id]
        except ValueError:
            filtered = []

    return filtered


def _apply_kpi_filter(items, kpi_filter):
    key = (kpi_filter or "").lower()
    if key in {"", "all"}:
        return [a for a in items if not a.is_disabled]
    if key == "in_use":
        return [a for a in items if not a.is_disabled and a.operational_status == "IN_USE"]
    if key == "standby":
        return [a for a in items if not a.is_disabled and a.operational_status == "STANDBY"]
    if key == "broken":
        return [a for a in items if not a.is_disabled and a.operational_status == "BROKEN"]
    if key == "inspection_due_soon":
        return [
            a
            for a in items
            if not a.is_disabled and a.inspection_status(INSPECTION_WARNING_DAYS)[0] == "DUE_SOON"
        ]
    if key == "inspection_overdue":
        return [
            a
            for a in items
            if not a.is_disabled and a.inspection_status(INSPECTION_WARNING_DAYS)[0] == "OVERDUE"
        ]
    if key == "pm_due_soon":
        return [a for a in items if not a.is_disabled and a.pm_status(PM_WARNING_DAYS)[0] == "DUE_SOON"]
    if key == "pm_overdue":
        return [a for a in items if not a.is_disabled and a.pm_status(PM_WARNING_DAYS)[0] == "OVERDUE"]
    if key == "life_due_soon":
        return [a for a in items if not a.is_disabled and a.eol_status(LIFE_WARNING_DAYS)[0] == "DUE_SOON"]
    if key == "life_expired":
        return [a for a in items if not a.is_disabled and a.eol_status(LIFE_WARNING_DAYS)[0] == "EXPIRED"]
    if key == "unassigned_department":
        return [a for a in items if not a.is_disabled and a.department_id is None]
    if key == "missing_serial":
        return [
            a
            for a in items
            if not a.is_disabled and (not a.serial_number.strip() or not (a.imei or "").strip())
        ]
    return [a for a in items if not a.is_disabled]


def _kpi_payload(items):
    active = [a for a in items if not a.is_disabled]
    return {
        "total": len(active),
        "in_use": len([a for a in active if a.operational_status == "IN_USE"]),
        "standby": len([a for a in active if a.operational_status == "STANDBY"]),
        "broken": len([a for a in active if a.operational_status == "BROKEN"]),
        "inspection_due_soon": len(
            [a for a in active if a.inspection_status(INSPECTION_WARNING_DAYS)[0] == "DUE_SOON"]
        ),
        "inspection_overdue": len(
            [a for a in active if a.inspection_status(INSPECTION_WARNING_DAYS)[0] == "OVERDUE"]
        ),
    }


def _chip_payload(items):
    active = [a for a in items if not a.is_disabled]
    return {
        "pm_due_soon": len([a for a in active if a.pm_status(PM_WARNING_DAYS)[0] == "DUE_SOON"]),
        "pm_overdue": len([a for a in active if a.pm_status(PM_WARNING_DAYS)[0] == "OVERDUE"]),
        "life_due_soon": len([a for a in active if a.eol_status(LIFE_WARNING_DAYS)[0] == "DUE_SOON"]),
        "life_expired": len([a for a in active if a.eol_status(LIFE_WARNING_DAYS)[0] == "EXPIRED"]),
        "unassigned_department": len([a for a in active if a.department_id is None]),
        "missing_serial": len(
            [a for a in active if not a.serial_number.strip() or not (a.imei or "").strip()]
        ),
    }


@login_required
def asset_list_page(request):
    return render(request, "assets/list.html")


@login_required
def create_asset_page(request):
    return render(request, "assets/create_asset.html")


@login_required
def edit_asset_page(request, asset_id: int):
    asset = get_object_or_404(Asset, id=asset_id)
    return render(request, "assets/edit_asset.html", {"asset": asset})


@login_required
def asset_detail_page(request, asset_id: int):
    asset = get_object_or_404(Asset, id=asset_id)
    return render(request, "assets/view_asset.html", {"asset": asset})


@require_GET
@login_required
def master_data_api(request):
    departments = list(Department.objects.values("id", "code", "name"))
    vendors = list(Vendor.objects.values("id", "name"))
    return _json_response({"departments": departments, "vendors": vendors})


@require_GET
@login_required
def asset_list_api(request):
    try:
        page = int(request.GET.get("page", 1))
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size", 10))
    except ValueError:
        page_size = 10

    page_size = min(max(page_size, 1), 100)

    queryset = Asset.objects.select_related("department", "location", "vendor")
    search = (request.GET.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(asset_code__icontains=search)
            | Q(standardized_name__icontains=search)
            | Q(serial_number__icontains=search)
            | Q(imei__icontains=search)
        )

    items = list(queryset)

    kpi_filter = request.GET.get("kpi_filter")
    if kpi_filter:
        filtered = _apply_kpi_filter(items, kpi_filter)
    else:
        filtered = _apply_status_filters(items, request.GET)

    paginator = Paginator(filtered, page_size)
    page_obj = paginator.get_page(page)

    all_assets = list(Asset.objects.select_related("department"))

    return _json_response(
        {
            "items": [_serialize_asset(a) for a in page_obj.object_list],
            "kpi": _kpi_payload(all_assets),
            "chips": _chip_payload(all_assets),
            "paging": {
                "page": page_obj.number,
                "page_size": page_size,
                "total_items": paginator.count,
                "total_pages": paginator.num_pages,
            },
        }
    )


@csrf_exempt
@require_POST
@login_required
def create_asset_api(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _json_response({"errors": {"__all__": "Invalid JSON payload."}}, status=400)

    required_fields = {
        "asset_code": "Asset Code is required.",
        "standardized_name": "Standardized Name is required.",
        "category_group": "Category is required.",
        "department_id": "Department is required.",
        "commissioning_date": "Commissioning Date is required.",
        "useful_life_years": "Useful Life Years is required.",
    }
    errors = {}

    for field, message in required_fields.items():
        value = payload.get(field)
        if value in (None, ""):
            errors[field] = message

    inspection_required = bool(payload.get("inspection_required", True))
    pm_required = bool(payload.get("pm_required", True))

    if inspection_required and not payload.get("inspection_expiry_date"):
        errors["inspection_expiry_date"] = "Inspection Expiry Date is required when inspection is required."

    if pm_required and not payload.get("pm_next_due_date"):
        errors["pm_next_due_date"] = "PM Next Due Date is required when PM is required."

    warranty_start = payload.get("warranty_start_date")
    warranty_end = payload.get("warranty_end_date")
    if warranty_start and warranty_end and warranty_end < warranty_start:
        errors["warranty_end_date"] = "Warranty End must be greater than or equal to Warranty Start."

    serial_number = (payload.get("serial_number") or "").strip()
    imei = (payload.get("imei") or "").strip()
    barcode = (payload.get("barcode") or "").strip()

    if Asset.objects.filter(asset_code=payload.get("asset_code", "").strip()).exists():
        errors["asset_code"] = "Asset Code already exists."
    if serial_number and Asset.objects.filter(serial_number=serial_number).exists():
        errors["serial_number"] = "Serial Number already exists."
    if imei and Asset.objects.filter(imei=imei).exists():
        errors["imei"] = "IMEI already exists."
    if barcode and Asset.objects.filter(barcode=barcode).exists():
        errors["barcode"] = "Barcode already exists."

    try:
        department = Department.objects.get(id=payload.get("department_id"))
    except Department.DoesNotExist:
        errors["department_id"] = "Department does not exist."
        department = None

    vendor = None
    vendor_name = (payload.get("vendor_name") or "").strip()
    if vendor_name:
        vendor, _ = Vendor.objects.get_or_create(name=vendor_name)

    location_name = (payload.get("location_name") or "").strip()
    location = None
    if location_name:
        location, _ = Location.objects.get_or_create(name=location_name)

    if errors:
        return _json_response({"errors": errors}, status=400)

    asset = Asset.objects.create(
        asset_code=payload["asset_code"].strip(),
        standardized_name=payload["standardized_name"].strip(),
        barcode=barcode or None,
        asset_type=payload.get("asset_type") or Asset.AssetType.MAIN,
        category_group=payload["category_group"].strip(),
        risk_class=(payload.get("risk_class") or "").strip(),
        manufacturer=(payload.get("manufacturer") or "").strip(),
        model_name=(payload.get("model_name") or "").strip(),
        year_of_manufacture=payload.get("year_of_manufacture") or None,
        department=department,
        location=location,
        pic_owner=(payload.get("pic_owner") or "").strip(),
        ops_note=(payload.get("ops_note") or "").strip(),
        operational_status=payload.get("operational_status") or Asset.OperationalStatus.IN_USE,
        inspection_required=inspection_required,
        inspection_last_date=payload.get("inspection_last_date") or None,
        inspection_expiry_date=payload.get("inspection_expiry_date") or None,
        pm_required=pm_required,
        pm_last_date=payload.get("pm_last_date") or None,
        pm_next_due_date=payload.get("pm_next_due_date") or None,
        commissioning_date=payload.get("commissioning_date"),
        useful_life_years=payload.get("useful_life_years") or 1,
        vendor=vendor,
        warranty_start_date=payload.get("warranty_start_date") or None,
        warranty_end_date=payload.get("warranty_end_date") or None,
        service_contract_id=(payload.get("service_contract_id") or "").strip(),
        contract_end_date=payload.get("contract_end_date") or None,
        serial_number=serial_number,
        imei=imei,
        notes=(payload.get("notes") or "").strip(),
    )

    AuditLog.objects.create(
        entity_type="ASSET",
        entity_id=asset.id,
        action="CREATE",
        after_value=json.dumps({"asset_code": asset.asset_code, "name": asset.standardized_name}),
        actor=request.user.username if request.user.is_authenticated else "anonymous",
    )

    return _json_response({"id": asset.id, "asset_code": asset.asset_code}, status=201)


@csrf_exempt
@require_POST
@login_required
def update_asset_api(request, asset_id: int):
    asset = get_object_or_404(Asset, id=asset_id)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _json_response({"errors": {"__all__": "Invalid JSON payload."}}, status=400)

    required_fields = {
        "asset_code": "Asset Code is required.",
        "standardized_name": "Standardized Name is required.",
        "category_group": "Category is required.",
        "department_id": "Department is required.",
        "commissioning_date": "Commissioning Date is required.",
        "useful_life_years": "Useful Life Years is required.",
    }
    errors = {}

    for field, message in required_fields.items():
        value = payload.get(field)
        if value in (None, ""):
            errors[field] = message

    inspection_required = bool(payload.get("inspection_required", True))
    pm_required = bool(payload.get("pm_required", True))

    if inspection_required and not payload.get("inspection_expiry_date"):
        errors["inspection_expiry_date"] = "Inspection Expiry Date is required when inspection is required."
    if pm_required and not payload.get("pm_next_due_date"):
        errors["pm_next_due_date"] = "PM Next Due Date is required when PM is required."

    warranty_start = payload.get("warranty_start_date")
    warranty_end = payload.get("warranty_end_date")
    if warranty_start and warranty_end and warranty_end < warranty_start:
        errors["warranty_end_date"] = "Warranty End must be greater than or equal to Warranty Start."

    asset_code = (payload.get("asset_code") or "").strip()
    serial_number = (payload.get("serial_number") or "").strip()
    imei = (payload.get("imei") or "").strip()
    barcode = (payload.get("barcode") or "").strip()

    if Asset.objects.exclude(id=asset.id).filter(asset_code=asset_code).exists():
        errors["asset_code"] = "Asset Code already exists."
    if serial_number and Asset.objects.exclude(id=asset.id).filter(serial_number=serial_number).exists():
        errors["serial_number"] = "Serial Number already exists."
    if imei and Asset.objects.exclude(id=asset.id).filter(imei=imei).exists():
        errors["imei"] = "IMEI already exists."
    if barcode and Asset.objects.exclude(id=asset.id).filter(barcode=barcode).exists():
        errors["barcode"] = "Barcode already exists."

    try:
        department = Department.objects.get(id=payload.get("department_id"))
    except Department.DoesNotExist:
        department = None
        errors["department_id"] = "Department does not exist."

    vendor = None
    vendor_name = (payload.get("vendor_name") or "").strip()
    if vendor_name:
        vendor, _ = Vendor.objects.get_or_create(name=vendor_name)

    location = None
    location_name = (payload.get("location_name") or "").strip()
    if location_name:
        location, _ = Location.objects.get_or_create(name=location_name)

    if errors:
        return _json_response({"errors": errors}, status=400)

    before_data = {
        "asset_code": asset.asset_code,
        "standardized_name": asset.standardized_name,
        "operational_status": asset.operational_status,
        "department_id": asset.department_id,
    }

    asset.asset_code = asset_code
    asset.standardized_name = (payload.get("standardized_name") or "").strip()
    asset.barcode = barcode or None
    asset.asset_type = payload.get("asset_type") or Asset.AssetType.MAIN
    asset.category_group = (payload.get("category_group") or "").strip()
    asset.risk_class = (payload.get("risk_class") or "").strip()
    asset.manufacturer = (payload.get("manufacturer") or "").strip()
    asset.model_name = (payload.get("model_name") or "").strip()
    asset.year_of_manufacture = payload.get("year_of_manufacture") or None
    asset.department = department
    asset.location = location
    asset.pic_owner = (payload.get("pic_owner") or "").strip()
    asset.ops_note = (payload.get("ops_note") or "").strip()
    asset.operational_status = payload.get("operational_status") or Asset.OperationalStatus.IN_USE
    asset.inspection_required = inspection_required
    asset.inspection_last_date = payload.get("inspection_last_date") or None
    asset.inspection_expiry_date = payload.get("inspection_expiry_date") or None
    asset.pm_required = pm_required
    asset.pm_last_date = payload.get("pm_last_date") or None
    asset.pm_next_due_date = payload.get("pm_next_due_date") or None
    asset.commissioning_date = payload.get("commissioning_date")
    asset.useful_life_years = payload.get("useful_life_years") or 1
    asset.vendor = vendor
    asset.warranty_start_date = payload.get("warranty_start_date") or None
    asset.warranty_end_date = payload.get("warranty_end_date") or None
    asset.service_contract_id = (payload.get("service_contract_id") or "").strip()
    asset.contract_end_date = payload.get("contract_end_date") or None
    asset.serial_number = serial_number
    asset.imei = imei
    asset.notes = (payload.get("notes") or "").strip()
    asset.save()

    after_data = {
        "asset_code": asset.asset_code,
        "standardized_name": asset.standardized_name,
        "operational_status": asset.operational_status,
        "department_id": asset.department_id,
    }

    AuditLog.objects.create(
        entity_type="ASSET",
        entity_id=asset.id,
        action="UPDATE",
        before_value=json.dumps(before_data),
        after_value=json.dumps(after_data),
        actor=request.user.username if request.user.is_authenticated else "anonymous",
    )

    return _json_response({"id": asset.id, "asset_code": asset.asset_code}, status=200)


@csrf_exempt
@require_POST
@login_required
def disable_assets_api(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _json_response({"error": "Invalid JSON body."}, status=400)

    ids = payload.get("ids") or []
    reason = (payload.get("reason") or "").strip()
    note = (payload.get("note") or "").strip()

    if not ids:
        return _json_response({"error": "No asset ids provided."}, status=400)
    if not reason:
        return _json_response({"error": "Disable reason is required."}, status=400)

    assets = list(Asset.objects.filter(id__in=ids, is_disabled=False))
    for asset in assets:
        asset.is_disabled = True
        asset.save(update_fields=["is_disabled", "updated_at"])
        AuditLog.objects.create(
            entity_type="ASSET",
            entity_id=asset.id,
            action="DISABLE",
            reason=reason,
            note=note,
            actor=request.user.username if request.user.is_authenticated else "anonymous",
        )

    return _json_response({"disabled_count": len(assets)})


def _overview_payload(asset: Asset):
    inspection = asset.inspection_status(INSPECTION_WARNING_DAYS)
    pm = asset.pm_status(PM_WARNING_DAYS)
    eol = asset.eol_status(LIFE_WARNING_DAYS)

    latest_compliance = asset.compliance_records.first()

    return {
        "identification": {
            "asset_code": asset.asset_code,
            "name": asset.standardized_name,
            "asset_type": asset.asset_type,
            "category": asset.category_group,
            "model": asset.model_name,
            "manufacturer": asset.manufacturer,
            "serial_number": asset.serial_number,
            "imei": asset.imei,
            "barcode": asset.barcode,
        },
        "ownership": {
            "department": asset.department.name if asset.department else "Unassigned",
            "location": asset.location.name if asset.location else "Unassigned",
            "custodian": asset.pic_owner or "Unassigned",
            "risk_class": asset.risk_class or "N/A",
        },
        "compliance_summary": {
            "inspection": inspection[0],
            "inspection_due": asset.inspection_expiry_date,
            "pm": pm[0],
            "pm_due": asset.pm_next_due_date,
            "eol": eol[0],
            "eol_date": eol[2],
            "warranty_end": asset.warranty_end_date,
            "latest_compliance_result": latest_compliance.result if latest_compliance else None,
        },
        "lifecycle": {
            "commissioning_date": asset.commissioning_date,
            "expected_eol": eol[2],
            "operational_status": asset.effective_operational_status,
            "notes": asset.notes,
        },
    }


def _header_payload(asset: Asset):
    inspection_status, inspection_days = asset.inspection_status(INSPECTION_WARNING_DAYS)
    pm_status, pm_days = asset.pm_status(PM_WARNING_DAYS)
    eol_status, eol_days, eol_date = asset.eol_status(LIFE_WARNING_DAYS)

    return {
        "asset_name": asset.standardized_name,
        "asset_code": asset.asset_code,
        "category": asset.category_group,
        "model": asset.model_name,
        "manufacturer": asset.manufacturer,
        "serial": asset.serial_number,
        "imei": asset.imei,
        "status": asset.effective_operational_status,
        "location": asset.location.name if asset.location else "Unassigned",
        "department": asset.department.name if asset.department else "Unassigned",
        "custodian": asset.pic_owner or "Unassigned",
        "risk_class": asset.risk_class or "N/A",
        "badges": {
            "inspection": {"status": inspection_status, "days": inspection_days, "date": asset.inspection_expiry_date},
            "pm": {"status": pm_status, "days": pm_days, "date": asset.pm_next_due_date},
            "eol": {"status": eol_status, "days": eol_days, "date": eol_date},
            "warranty": {"date": asset.warranty_end_date},
        },
    }


def _kpi_detail_payload(asset: Asset):
    cutoff = timezone.now() - timedelta(days=365)
    incidents_12m = asset.incidents.filter(reported_at__gte=cutoff)
    breakdown_count = incidents_12m.filter(status__in=["REPORTED", "CONFIRMED", "RESOLVED", "CLOSED"]).count()

    downtime_minutes = 0
    for inc in incidents_12m.filter(status__in=["RESOLVED", "CLOSED"], resolved_at__isnull=False):
        delta = inc.resolved_at - inc.reported_at
        downtime_minutes += int(max(delta.total_seconds(), 0) // 60)

    last_pm = asset.work_orders.filter(wo_type="PM", completed_date__isnull=False).order_by("-completed_date").first()
    next_pm = asset.work_orders.filter(wo_type="PM", due_date__isnull=False).order_by("due_date").first()

    next_cal = asset.compliance_records.filter(next_due_at__isnull=False).order_by("next_due_at").first()

    on_time = None
    if last_pm and last_pm.due_date:
        on_time = bool(last_pm.completed_date and last_pm.completed_date <= last_pm.due_date)

    return {
        "breakdown_12m": breakdown_count,
        "downtime_12m_minutes": downtime_minutes,
        "last_pm_date": last_pm.completed_date if last_pm else None,
        "last_pm_on_time": on_time,
        "next_pm_due": next_pm.due_date if next_pm else asset.pm_next_due_date,
        "next_calibration_due": next_cal.next_due_at if next_cal else asset.inspection_expiry_date,
        "warranty_expiry": asset.warranty_end_date,
    }


def _timeline_payload(asset: Asset):
    def _normalize_event_time(value):
        if value is None:
            return datetime.min
        if isinstance(value, datetime):
            if timezone.is_aware(value):
                return timezone.make_naive(value, timezone.get_current_timezone())
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        return datetime.min

    events = []

    for wo in asset.work_orders.all()[:50]:
        when = wo.completed_date or wo.scheduled_date or wo.due_date
        events.append(
            {
                "time": when,
                "type": "WO",
                "ref": wo.wo_code,
                "summary": f"{wo.wo_type} - {wo.status}",
                "actor": wo.technician or "N/A",
            }
        )

    for inc in asset.incidents.all()[:50]:
        events.append(
            {
                "time": inc.reported_at,
                "type": "INCIDENT",
                "ref": inc.incident_code,
                "summary": f"{inc.status} - {inc.symptom}",
                "actor": "Ward/Biomed",
            }
        )

    for comp in asset.compliance_records.all()[:50]:
        events.append(
            {
                "time": comp.performed_at,
                "type": "COMPLIANCE",
                "ref": comp.record_code,
                "summary": f"{comp.compliance_type} - {comp.result}",
                "actor": comp.performed_by,
            }
        )

    for hand in asset.handovers.all()[:50]:
        events.append(
            {
                "time": hand.handover_date,
                "type": "HANDOVER",
                "ref": hand.doc_id,
                "summary": f"{hand.from_location} -> {hand.to_location}",
                "actor": hand.custodian_after,
            }
        )

    for mov in asset.movements.all()[:50]:
        events.append(
            {
                "time": mov.moved_at,
                "type": "MOVE",
                "ref": "",
                "summary": f"{mov.from_location} -> {mov.to_location}",
                "actor": mov.action_by,
            }
        )

    for doc in asset.documents.all()[:50]:
        events.append(
            {
                "time": doc.updated_at,
                "type": "DOC",
                "ref": doc.file_name,
                "summary": f"{doc.doc_type} uploaded",
                "actor": "N/A",
            }
        )

    events.sort(key=lambda x: _normalize_event_time(x.get("time")), reverse=True)
    return events[:100]


@require_GET
@login_required
def asset_detail_api(request, asset_id: int):
    asset = get_object_or_404(
        Asset.objects.select_related("department", "location", "vendor"),
        id=asset_id,
    )

    pm_history = list(
        asset.work_orders.filter(wo_type="PM").values(
            "wo_code",
            "title",
            "scheduled_date",
            "completed_date",
            "due_date",
            "technician",
            "checklist_summary",
            "status",
        )
    )

    repair_history = []
    for inc in asset.incidents.all():
        linked_wo = asset.work_orders.filter(wo_type="REPAIR", title__icontains=inc.incident_code).first()
        downtime_minutes = None
        if inc.resolved_at:
            downtime_minutes = int(max((inc.resolved_at - inc.reported_at).total_seconds(), 0) // 60)
        repair_history.append(
            {
                "incident_code": inc.incident_code,
                "wo_code": linked_wo.wo_code if linked_wo else None,
                "reported_at": inc.reported_at,
                "symptom": inc.symptom,
                "priority": inc.priority,
                "root_cause": inc.root_cause,
                "downtime_minutes": downtime_minutes,
                "status": inc.status,
            }
        )

    compliance_history = list(
        asset.compliance_records.values(
            "record_code",
            "compliance_type",
            "performed_by",
            "performed_at",
            "next_due_at",
            "result",
            "certificate_name",
        )
    )

    handover_history = list(
        asset.handovers.values(
            "doc_id",
            "from_location",
            "to_location",
            "custodian_after",
            "handover_date",
            "accessories_summary",
            "signed",
        )
    )

    movement_history = list(
        asset.movements.values(
            "moved_at",
            "from_location",
            "to_location",
            "action_by",
            "reason",
        )
    )

    accessories = list(
        asset.accessories.values(
            "accessory_name",
            "code_or_serial",
            "quantity",
            "status",
            "mandatory",
            "last_verified_date",
            "notes",
        )
    )

    spare_parts = list(
        asset.part_consumptions.values(
            "consumed_at",
            "wo_code",
            "part_code",
            "part_name",
            "quantity",
            "batch_info",
            "issued_store",
            "cost",
        )
    )

    documents = list(
        asset.documents.values(
            "doc_type",
            "file_name",
            "related_to",
            "updated_at",
        )
    )

    audit = list(
        AuditLog.objects.filter(entity_type="ASSET", entity_id=asset.id).values(
            "acted_at",
            "actor",
            "action",
            "field_name",
            "before_value",
            "after_value",
        )
    )

    return _json_response(
        {
            "header": _header_payload(asset),
            "kpi": _kpi_detail_payload(asset),
            "overview": _overview_payload(asset),
            "timeline": _timeline_payload(asset),
            "tabs": {
                "pm": pm_history,
                "repair": repair_history,
                "compliance": compliance_history,
                "handover": handover_history,
                "movement": movement_history,
                "accessories": accessories,
                "spare_parts": spare_parts,
                "documents": documents,
                "audit": audit,
            },
        }
    )
