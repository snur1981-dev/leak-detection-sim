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
        "roughness_m": 0.045e-3,  # 0.045 mm commercial steel, written in metres
    "steel_E_pa": 200e9,
}
FLUID = {
    "density_kgm3": 850.0,
    "nu_m2s": 1.0e-5,        # 10 cSt, assumed
    "bulk_modulus_pa": 1.4e9,
    "beta_per_c": 8e-4,      # thermal expansion, assumed
}
OPERATION = {"flow_m3s": 0.20, "p_out_mpa": 0.5}
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
def friction_factor(re, rel_rough):
    """Darcy friction factor by Swamee-Jain (turbulent flow).

    re: Reynolds number (dimensionless). rel_rough: roughness / diameter (dimensionless).
    """
    return 0.25 / math.log10(rel_rough / 3.7 + 5.74 / re ** 0.9) ** 2
def steady_state(q_m3s, p_out_mpa=OPERATION["p_out_mpa"], pipe=PIPE, fluid=FLUID):
    """Steady flow on a flat line: velocity, Re, f, friction loss and pressures (MPa)."""
    g = derived(pipe, fluid)
    v = q_m3s / g["area_m2"]
    re = v * g["id_m"] / fluid["nu_m2s"]
    f = friction_factor(re, pipe["roughness_m"] / g["id_m"])
    dp_pa = f * (pipe["length_m"] / g["id_m"]) * fluid["density_kgm3"] * v ** 2 / 2
    dp_mpa = dp_pa / 1e6
    return {
        "v_ms": v,
        "re": re,
        "f": f,
        "dp_mpa": dp_mpa,
        "p_in_mpa": p_out_mpa + dp_mpa,
        "p_mid_mpa": p_out_mpa + dp_mpa / 2,   # straight-line profile, midpoint
        "p_out_mpa": p_out_mpa,
        "p_avg_mpa": p_out_mpa + dp_mpa / 2,   # average of a straight line = midpoint
    }
def wave_speed(pipe=PIPE, fluid=FLUID):
    """Pressure wave speed in m/s, slowed by pipe elasticity."""
    d = derived(pipe, fluid)["id_m"]
    k = fluid["bulk_modulus_pa"]
    return math.sqrt((k / fluid["density_kgm3"]) / (1 + k * d / (pipe["steel_E_pa"] * pipe["wall_m"])))
def check_hand_calcs():
    """Fail loudly if the code drifts from the hand calculations (Lesson 1)."""
    def close(got, want, tol_frac):
        assert abs(got - want) <= tol_frac * want, f"got {got:.4f}, expected {want}"

    close(steady_state(0.10)["dp_mpa"], 1.76, 0.01)
    close(steady_state(0.15)["dp_mpa"], 3.64, 0.01)
    close(steady_state(0.20)["dp_mpa"], 6.10, 0.01)
    close(steady_state(0.20)["p_in_mpa"], 6.60, 0.01)
    assert abs(derived()["linepack_m3_per_mpa"] - 11.52) <= 0.01
    close(wave_speed(), 1106, 0.01)
    print("All hand-check asserts passed.")

if __name__ == "__main__":
    for k, v in derived().items():
        print(f"{k:22s} {v:,.4f}")
    print()
    print(f"{'Q (m3/s)':>9} {'v (m/s)':>8} {'Re':>8} {'f':>7} {'dP (MPa)':>9} {'P_in (MPa)':>10}")
    for q in (0.10, 0.15, 0.20):
        s = steady_state(q)
        print(f"{q:9.2f} {s['v_ms']:8.3f} {s['re']:8.0f} {s['f']:7.4f} {s['dp_mpa']:9.2f} {s['p_in_mpa']:10.2f}")
    a = wave_speed()
    print(f"\nWave speed {a:,.0f} m/s; crosses 100 km in {PIPE['length_m'] / a:.0f} s")
    print()
    check_hand_calcs()
