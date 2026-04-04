from functools import lru_cache

import pvlib


@lru_cache(maxsize=1)
def _get_cec_database():
    return pvlib.pvsystem.retrieve_sam("CECMod")


def _normalize_lookup_value(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _find_panel_match(make: str, model: str) -> str:
    cec_db = _get_cec_database()
    make_query = _normalize_lookup_value(make)
    model_query = _normalize_lookup_value(model)

    matches = [
        column
        for column in cec_db.columns
        if make_query in column.lower() and model_query in column.lower()
    ]

    if not matches:
        raise ValueError(
            f"No panel found for make='{make}', model='{model}'. "
            "Try a shorter model prefix if the exact name is not present in the CEC database."
        )

    return matches[0]


def get_panel_specs(make: str, model: str) -> dict:
    """
    Return the full matched panel record from pvlib's CEC database.
    """
    cec_db = _get_cec_database()
    matched_name = _find_panel_match(make, model)
    panel = cec_db[matched_name]
    raw_specs = {
        key: value.item() if hasattr(value, "item") else value
        for key, value in panel.to_dict().items()
    }

    return {
        "source": "CEC Module Database (via pvlib)",
        "make": make,
        "model": model,
        "matched_name": matched_name,
        "raw_specs": raw_specs,
        "dimensions": {
            "length_m": panel.get("Length"),
            "width_m": panel.get("Width"),
            "area_m2": panel.get("A_c"),
        },
        "electrical": {
            "stc_w": panel.get("STC"),
            "ptc_w": panel.get("PTC"),
            "voc": panel.get("V_oc_ref"),
            "isc": panel.get("I_sc_ref"),
            "vmp": panel.get("V_mp_ref"),
            "imp": panel.get("I_mp_ref"),
        },
        "thermal": {
            "temp_coeff_isc": panel.get("alpha_sc"),
            "temp_coeff_voc": panel.get("beta_oc"),
            "temp_coeff_power": panel.get("gamma_r"),
            "t_noct": panel.get("T_NOCT"),
        },
        "metadata": {
            "technology": panel.get("Technology"),
            "bifacial": bool(panel.get("Bifacial")),
            "n_cells": panel.get("N_s"),
            "bipv": panel.get("BIPV"),
            "version": panel.get("Version"),
        },
        "diode_model": {
            "a_ref": panel.get("a_ref"),
            "i_l_ref": panel.get("I_L_ref"),
            "i_o_ref": panel.get("I_o_ref"),
            "r_s": panel.get("R_s"),
            "r_sh_ref": panel.get("R_sh_ref"),
            "adjust": panel.get("Adjust"),
        },
    }


def get_panel_dimensions(make: str, model: str) -> dict:
    """
    Return only the dimensions for a given panel make and model.

    Example:
        get_panel_dimensions("Canadian Solar", "CS6X")
    """
    specs = get_panel_specs(make, model)
    return {
        "make": specs["make"],
        "model": specs["model"],
        "matched_name": specs["matched_name"],
        **specs["dimensions"],
    }


if __name__ == "__main__":
    print(get_panel_specs("Ablytek", "6MN6A280"))
