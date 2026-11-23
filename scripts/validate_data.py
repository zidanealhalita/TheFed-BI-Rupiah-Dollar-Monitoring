"""Validasi lima file data di data/raw/ tanpa membuka Streamlit.

Pakai:  python scripts/validate_data.py
Keluar dengan kode 1 bila ada file yang tidak bisa dibaca atau ada peringatan serius.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fedbi.dataset import load_bundle  # noqa: E402


def main() -> int:
    try:
        b = load_bundle()
    except Exception as exc:  # noqa: BLE001
        print(f"GAGAL memuat data: {exc}")
        return 1

    print("Data OK. Observasi terakhir dan jumlah baris:")
    for k, v in b.report.last_obs.items():
        print(f"  {k:<9} s.d. {v:%Y-%m-%d}   ({b.report.n_obs[k]} obs)")
    print(f"Tabel harian gabungan: {b.daily.index.min():%Y-%m-%d} → {b.daily.index.max():%Y-%m-%d} ({len(b.daily)} hari)")
    if b.report.warnings:
        print("\nCatatan:")
        for w in b.report.warnings:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
