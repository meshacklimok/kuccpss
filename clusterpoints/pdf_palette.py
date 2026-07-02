"""
Shared ReportLab colour palette for clusterpoints PDF exports.
Kept in one place so export_cluster_pdf and export_full_results_pdf render
identical brand colours instead of maintaining two copies of the same hexes.
"""
from reportlab.lib import colors as rc

NAVY    = rc.HexColor("#1e3a8a")
TEAL    = rc.HexColor("#0e7490")
EMERALD = rc.HexColor("#059669")
AMBER   = rc.HexColor("#d97706")
PURPLE  = rc.HexColor("#7c3aed")
SLATE   = rc.HexColor("#475569")
LIGHT   = rc.HexColor("#f0f9ff")
RED     = rc.HexColor("#dc2626")
WHITE   = rc.white
