"""
Smart Traffic Monitoring System (STMS) — Reports Router

Endpoint export laporan traffic dalam format CSV atau PDF.
Dilindungi JWT dengan role management/admin.

Dependencies tambahan:
  - pandas       → DataFrame & CSV export
  - fpdf2        → PDF generation
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone, date
from typing import Optional
import io

import pandas as pd
from fpdf import FPDF

from .. import models
from ..dependencies import get_db, require_role

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Build query & fetch records
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_report_data(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    camera_id: Optional[str]
) -> list:
    """
    Query JOIN TRAFFIC_DENSITY ↔ CAMERA untuk mendapatkan semua kolom laporan
    dalam rentang [start_date, end_date], opsional filter per camera_id.
    """
    query = (
        db.query(models.TrafficDensity, models.Camera)
        .join(models.Camera, models.TrafficDensity.camera_id == models.Camera.camera_id)
        .filter(
            models.TrafficDensity.interval_start >= start_date,
            models.TrafficDensity.interval_end <= end_date
        )
    )
    if camera_id:
        query = query.filter(models.TrafficDensity.camera_id == camera_id)

    return query.order_by(models.TrafficDensity.interval_start.asc()).all()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Build pandas DataFrame
# ═══════════════════════════════════════════════════════════════════════════════

def _build_dataframe(rows: list) -> pd.DataFrame:
    """Ubah query result menjadi pandas DataFrame dengan kolom standar laporan."""
    data = []
    for density, camera in rows:
        data.append({
            "date": density.interval_start.strftime("%Y-%m-%d"),
            "time": density.interval_start.strftime("%H:%M"),
            "camera_id": density.camera_id,
            "location_name": camera.location_name,
            "total_vehicles": density.total_vehicles,
            "inflow_count": density.inflow_count,
            "outflow_count": density.outflow_count,
            "density_ratio": round(density.density_ratio, 4) if density.density_ratio is not None else None,
            "density_level": density.density_level,
        })
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Generate CSV
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_csv(df: pd.DataFrame, start_date: datetime, end_date: datetime) -> StreamingResponse:
    """Ubah DataFrame ke CSV dan return sebagai StreamingResponse."""
    csv_string = df.to_csv(index=False)
    filename = (
        f"stms_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
    )
    return StreamingResponse(
        iter([csv_string]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Generate PDF (fpdf2)
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_pdf(df: pd.DataFrame, start_date: datetime, end_date: datetime) -> Response:
    """
    Buat laporan PDF menggunakan fpdf2 dengan:
    - Header: judul + rentang tanggal
    - Summary: total kendaraan, rata-rata density, peak hour
    - Tabel: maks 50 baris pertama
    - Footer: generated timestamp
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Header ────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "STMS Traffic Report", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 11)
    date_range = (
        f"Periode: {start_date.strftime('%Y-%m-%d %H:%M')} "
        f"s.d. {end_date.strftime('%Y-%m-%d %H:%M')} UTC"
    )
    pdf.cell(0, 8, date_range, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    # ── Summary ───────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Ringkasan / Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    if not df.empty:
        total_vehicles = int(df["total_vehicles"].sum())
        avg_density = df["density_ratio"].dropna().mean()
        avg_density_str = f"{avg_density:.2%}" if pd.notna(avg_density) else "N/A"

        # Peak hour: jam dengan rata-rata density_ratio tertinggi
        peak_hour_str = "N/A"
        if "time" in df.columns and not df["density_ratio"].dropna().empty:
            df_tmp = df.dropna(subset=["density_ratio"]).copy()
            df_tmp["hour"] = pd.to_datetime(df_tmp["date"] + " " + df_tmp["time"]).dt.hour
            peak_h = df_tmp.groupby("hour")["density_ratio"].mean().idxmax()
            peak_hour_str = f"{peak_h:02d}:00 - {(peak_h + 1) % 24:02d}:00"

        pdf.cell(0, 7, f"  Total Kendaraan   : {total_vehicles:,}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, f"  Rata-rata Density : {avg_density_str}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, f"  Peak Hour         : {peak_hour_str}", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 7, "  Tidak ada data dalam rentang ini.", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # ── Tabel data (maks 50 baris) ────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 9, "Data Detail (maks 50 baris)", new_x="LMARGIN", new_y="NEXT")

    if not df.empty:
        display_df = df.head(50)

        # Lebar kolom (mm) — total ≈ 190mm (A4 portrait - margin)
        col_widths = {
            "date":           24,
            "time":           14,
            "camera_id":      22,
            "location_name":  40,
            "total_vehicles": 22,
            "inflow_count":   18,
            "outflow_count":  18,
            "density_ratio":  18,
            "density_level":  16,
        }
        col_labels = {
            "date":           "Tanggal",
            "time":           "Waktu",
            "camera_id":      "Camera ID",
            "location_name":  "Lokasi",
            "total_vehicles": "Total",
            "inflow_count":   "Inflow",
            "outflow_count":  "Outflow",
            "density_ratio":  "Ratio",
            "density_level":  "Level",
        }

        # Header tabel
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(52, 73, 94)
        pdf.set_text_color(255, 255, 255)
        for col, width in col_widths.items():
            pdf.cell(width, 7, col_labels[col], border=1, fill=True, align="C")
        pdf.ln()

        # Baris data
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(0, 0, 0)
        for _, row in display_df.iterrows():
            # Alternating row color
            fill = pdf.get_y() % 14 < 7
            pdf.set_fill_color(240, 240, 240) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.cell(col_widths["date"], 6, str(row.get("date", "")), border=1, fill=fill)
            pdf.cell(col_widths["time"], 6, str(row.get("time", "")), border=1, fill=fill)
            pdf.cell(col_widths["camera_id"], 6, str(row.get("camera_id", "")), border=1, fill=fill)
            loc = str(row.get("location_name", ""))
            pdf.cell(col_widths["location_name"], 6, loc[:20], border=1, fill=fill)
            pdf.cell(col_widths["total_vehicles"], 6, str(row.get("total_vehicles", "")), border=1, fill=fill, align="R")
            pdf.cell(col_widths["inflow_count"], 6, str(row.get("inflow_count", "")), border=1, fill=fill, align="R")
            pdf.cell(col_widths["outflow_count"], 6, str(row.get("outflow_count", "")), border=1, fill=fill, align="R")
            ratio_val = row.get("density_ratio")
            ratio_str = f"{ratio_val:.3f}" if ratio_val is not None and pd.notna(ratio_val) else "-"
            pdf.cell(col_widths["density_ratio"], 6, ratio_str, border=1, fill=fill, align="R")
            pdf.cell(col_widths["density_level"], 6, str(row.get("density_level", "")), border=1, fill=fill, align="C")
            pdf.ln()

        if len(df) > 50:
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 6, f"  ... dan {len(df) - 50} baris lainnya (tidak ditampilkan di PDF).",
                     new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, "Tidak ada data.", new_x="LMARGIN", new_y="NEXT")

    # ── Footer ────────────────────────────────────────────────────────────────
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.cell(0, 6, f"Generated by STMS — {generated_at}", align="C")

    # Serialisasi ke bytes
    pdf_bytes = bytes(pdf.output())
    filename = (
        f"stms_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/reports/export
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/export",
    summary="Export laporan traffic (CSV / PDF)",
    description=(
        "Export data TRAFFIC_DENSITY dalam rentang tanggal sebagai file CSV atau PDF. "
        "Role: management, admin."
    )
)
def export_report(
    format: str = Query(..., description="Format export: 'csv' atau 'pdf'"),
    start_date: datetime = Query(..., description="Batas awal rentang (ISO 8601, UTC)"),
    end_date: datetime = Query(..., description="Batas akhir rentang (ISO 8601, UTC)"),
    camera_id: Optional[str] = Query(None, description="Filter per camera_id (opsional)"),
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(require_role("management", "admin"))
):
    # Validasi format
    if format not in ("csv", "pdf"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": True,
                "code": "INVALID_FORMAT",
                "message": "Format harus 'csv' atau 'pdf'."
            }
        )

    # Validasi rentang tanggal
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail={
                "error": True,
                "code": "INVALID_DATE_RANGE",
                "message": "start_date tidak boleh lebih besar dari end_date."
            }
        )

    # Ambil data dari DB
    rows = _fetch_report_data(db, start_date, end_date, camera_id)
    df = _build_dataframe(rows)

    if format == "csv":
        return _generate_csv(df, start_date, end_date)
    else:
        return _generate_pdf(df, start_date, end_date)
