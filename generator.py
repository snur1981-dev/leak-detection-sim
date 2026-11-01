"""Test pipeline parameters and the synthetic SCADA data generator.

Synthetic data only: a simplified hydraulic model, not a real pipeline or SCADA system.

Build order:
  Oct 22  steady-state hydraulics (Darcy-Weisbach + Swamee-Jain), pressure profile
  Oct 23  1-minute time series, meter noise and bias, historian-style CSV, one leak
  Oct 24  pump start/stop ramps with line pack built in
  Oct 29+ faults: comms dropout, frozen value, slow drift, clock skew / deadband
"""
import math

# --- Test pipeline (see README table) ---
PIPE = {
    "length_m": 100_000.0,
    "od_m": 0.4064,          # NPS 16
    "wall_m": 0.0079,
    "roughness_m": 0.045e-3,
    "steel_E_pa": 200e9,
}
FLUID = {
    "density_kgm3": 850.0,
    "nu_m2s": 1.0e-5,        # 10 cSt, assumed
    "bulk_modulus_pa": 1.4e9,
    "beta_per_c": 8e-4,      # thermal expansion, assumed
}
OPERATION = {"flow_m3s": 0.20}
METERS = {"flow_uncertainty_pct": 0.5}

TAGS = {
    "q_in": "PS1_FT101", "q_out": "TRM_FT201",
    "p_in": "PS1_PT101", "p_mid": "MID_PT201", "p_out": "TRM_PT301",
    "t_in": "PS1_TT101", "t_out": "TRM_TT201",
}


def derived(pipe=PIPE, fluid=FLUID):
    """Geometry and line pack numbers used everywhere else."""
    d = pipe["od_m"] - 2 * pipe["wall_m"]
    area = math.pi / 4 * d ** 2
    vol = area * pipe["length_m"]
    fluid_term = 1 / fluid["bulk_modulus_pa"]
    pipe_term = d / (pipe["steel_E_pa"] * pipe["wall_m"])
    return {
        "id_m": d,
        "area_m2": area,
        "volume_m3": vol,
        "linepack_m3_per_mpa": vol * (fluid_term + pipe_term) * 1e6,
        "linepack_m3_per_c": vol * fluid["beta_per_c"],
    }


if __name__ == "__main__":
    for k, v in derived().items():
        print(f"{k:22s} {v:,.4f}")
