"""
Single source of truth for the Excel import column layout.
Both the importer (reads these headers from an uploaded file) and the
template generator (writes these headers into the downloadable template)
use this list, so the two can never drift out of sync.
"""

# Ordered (field_key, header_text) pairs — the canonical 52-column layout.
FIELD_HEADERS = [
    ("sn", "SN"),
    ("region", "Region"),
    ("circle", "Circle"),
    ("tnc", "T&C"),
    ("esd", "ESD"),
    ("ss_name", "Substation Name"),
    ("lat", "Latitude (DMS or decimal)"),
    ("lon", "Longitude (DMS or decimal)"),
    ("ss_type", "SS Type (Conventional/Compact)"),
    ("gss_primary", "Primary GSS (132/33kV)"),
    ("gss_alternate", "Alternate GSS"),
    ("tapping_info", "Tapping Info"),
    ("lilo_info", "LILO Info"),
    ("tr_capacity", "TR Capacity (MVA)"),
    ("tr_make", "TR Make"),
    ("tr_yom", "TR YOM"),
    ("tr_max_load", "TR Max Loading (MW)"),
    ("tr_oti", "TR Max OTI (°C)"),
    ("tr_wti", "TR Max WTI (°C)"),
    ("feeder_name", "Feeder Name"),
    ("feeder_type_raw", "Feeder Type"),
    ("feeder_voltage", "Feeder Voltage (33kV/11kV)"),
    ("meter_no", "Meter No."),
    ("meter_make", "Meter Make"),
    ("meter_type", "Meter Type (DLMS/Non-DLMS)"),
    ("meter_status", "Meter Status"),
    ("ctr", "CT Ratio (CTR)"),
    ("mf", "Meter Factor (MF)"),
    ("ct_type", "CT Type"),
    ("ct_status", "CT Status"),
    ("pt_type", "PT Type"),
    ("pt_status", "PT Status"),
    ("dcu_status", "DCU Status"),
    ("vcb_type", "VCB Type (Indoor/Outdoor)"),
    ("panel_make", "Panel Make"),
    ("vcb_status", "VCB Status"),
    ("vcb_make", "VCB Make"),
    ("vcb_yom", "VCB YOM"),
    ("oc_ef_relay", "OC/EF Relay Type (Numerical/Electromechanical)"),
    ("diff_relay", "Differential Relay Type"),
    ("relay_make", "OC/EF Relay Make"),
    ("diff_relay_make", "Diff Relay Make"),
    ("diff_relay_status", "Diff Relay Status"),
    ("oc_ef_relay_status", "OC/EF Relay Status"),
    ("aux_relay_status", "Aux Relay Status"),
    ("year_commissioned", "Year Commissioned"),
    ("remarks", "Remarks"),
    ("charger_status", "Charger Status"),
    ("charger_make", "Charger Make"),
    ("charger_yom", "Charger YOM"),
    ("battery_status", "Battery Status"),
    ("battery_type", "Battery Type"),
]

# Fields that must be present in the uploaded file's header row.
REQUIRED_FIELDS = ("ss_name", "feeder_name")
