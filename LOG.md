# Engineering log

One entry per working day. Synthetic data only; record only numbers you actually got.

## Template

### YYYY-MM-DD: Part N, <title>
- **Did:**
- **Numbers I got:**
- **Checkpoint match?** (yes / no, and why)
- **Written answers:**
- **What surprised me:**
- **Open question:**

---

### 2026-10-21: Setup
- **Did:** Repo skeleton, README, reading list.
- **Numbers I got:** Line volume 11,983 m3; line pack 11.52 m3/MPa and 9.59 m3/degC (from `python generator.py`).
- **Open question:** Which CSA Z662 edition do Streamline's clients work to?

### 2026-11-01: Part 1, steady-state hydraulics and hand-checks
- **Did:** Set up Python, the virtual environment and git. Read Lesson 1. Did problems 1, 3 and 6 by hand. Added friction_factor, steady_state, wave_speed and check_hand_calcs to generator.py.
- **Numbers I got (code):** Pressure drop 1.76 / 3.64 / 6.10 MPa at 0.10 / 0.15 / 0.20 m3/s. Inlet pressure 6.60 MPa at 0.20 m3/s. Line pack 11.52 m3/MPa. Wave speed 1,106 m/s, so a pressure change takes about 90 s to cross 100 km.
- **Checkpoint match?** Yes. All hand-check asserts passed.
- **Hand calc vs code:**
  - Q1: My v (1.669 m/s) and Re (about 65,200) matched. My friction factor was wrong (0.111 instead of 0.0201) because I put roughness in mm (0.045) while the diameter was in metres. My pressure drop was also wrong, because I left out the f x L/D part. The correct answer is 6.10 MPa.
  - Q3: Correct. The fluid term is 7.14e-10 per Pa and the pipe term is 2.47e-10 per Pa. The pipe makes up about 26% of line pack. Multiplied by the line volume, that gives 8.56 + 2.96 = 11.52 m3/MPa.
  - Q6: Wave speed correct (1,106 m/s). I didn't know the unit at first: it's m/s.
- **Written answers:**
  1. Which do I trust when hand and code disagree? Neither automatically. I find the step where they split. Here it was a units mistake in my hand calc. The code avoids that because every variable carries its unit in its name, and the asserts check it against hand numbers.
  2. Why 11.52 and not the plan's 10.7? NPS 16 has a 406.4 mm outside diameter. With a 7.9 mm wall, the inside diameter is 390.6 mm, not 381 mm, so the pipe holds more and stretches more.
  3. Pipe share: about 26% of line pack comes from the steel stretching. This assumes a thin wall and ignores the soil holding the pipe in place. Including that would lower it slightly.
- **What surprised me:** Mixing up mm and m made the friction factor more than 5 times too big.
- **Open question:** Which CSA Z662 edition do Streamline's clients work to?