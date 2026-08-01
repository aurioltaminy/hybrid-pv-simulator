"""
Modèle de charge avancé - Domicile triphasé 400V
Climatiseurs Inverter : 1.5 CV, 2 CV, 3 CV
Paramètres électriques complets : tension, courant nominal, courant de démarrage
Vérification décrochage onduleur DEYE 20kW LV
"""

import numpy as np

# ─── Paramètres réseau triphasé ───────────────────────────────────────────────
VOLTAGE_PHASE    = 230.0    # Tension phase-neutre (V)
VOLTAGE_LINE     = 400.0    # Tension ligne-ligne (V)
FREQUENCY        = 50.0     # Fréquence (Hz)
NUM_PHASES       = 3        # Triphasé

# ─── Paramètres onduleur DEYE 20kW LV ────────────────────────────────────────
DEYE_MAX_POWER_KW     = 20.0   # Puissance active max (kW)
DEYE_MAX_APPARENT_KVA = 22.0   # Puissance apparente max (kVA)
DEYE_MAX_CURRENT_A    = 29.0   # Courant max par phase (A) à 400V triphasé
DEYE_OVERLOAD_FACTOR  = 1.25   # Tolérance surcharge courte durée (125%)
DEYE_OVERLOAD_DURATION_S = 10  # Durée max surcharge (secondes)

# ─── Catalogue climatiseurs Inverter ─────────────────────────────────────────
AC_CATALOG = {
    "1.5CV": {
        "power_cv":          1.5,
        "power_kw":          1.103,
        "power_kva":         1.298,
        "cos_phi":           0.85,
        "voltage_v":         230.0,
        "current_nominal_a": 5.64,
        "startup_factor":    3.0,
        "current_startup_a": 16.92,
        "startup_duration_s": 2.0,
        "color":             "#2196F3",
    },
    "2CV": {
        "power_cv":          2.0,
        "power_kw":          1.471,
        "power_kva":         1.731,
        "cos_phi":           0.85,
        "voltage_v":         230.0,
        "current_nominal_a": 7.53,
        "startup_factor":    4.0,
        "current_startup_a": 30.12,
        "startup_duration_s": 2.5,
        "color":             "#FF9800",
    },
    "3CV": {
        "power_cv":          3.0,
        "power_kw":          2.207,
        "power_kva":         2.596,
        "cos_phi":           0.85,
        "voltage_v":         230.0,
        "current_nominal_a": 11.29,
        "startup_factor":    5.0,
        "current_startup_a": 56.45,
        "startup_duration_s": 3.0,
        "color":             "#F44336",
    },
}

# ─── Appareils de base du domicile ───────────────────────────────────────────
BASE_APPLIANCES = {
    "refrigerateur": {"power_kw": 0.15, "current_a": 0.65,  "phase": 1},
    "congelateur":   {"power_kw": 0.20, "current_a": 0.87,  "phase": 1},
    "machine_laver": {"power_kw": 2.00, "current_a": 8.70,  "phase": 1},
    "four":          {"power_kw": 2.50, "current_a": 10.87, "phase": 1},
    "micro_ondes":   {"power_kw": 1.20, "current_a": 5.22,  "phase": 2},
    "tv":            {"power_kw": 0.15, "current_a": 0.65,  "phase": 2},
    "ordinateurs":   {"power_kw": 0.30, "current_a": 1.30,  "phase": 2},
    "eclairage":     {"power_kw": 0.40, "current_a": 1.74,  "phase": 3},
    "pompe_eau":     {"power_kw": 0.75, "current_a": 3.26,  "phase": 3},
}


def compute_current(power_kw, voltage_v=230.0, cos_phi=0.90, phases=1):
    if phases == 1:
        return (power_kw * 1000) / (voltage_v * cos_phi)
    else:
        return (power_kw * 1000) / (np.sqrt(3) * voltage_v * cos_phi)


def check_deye_limits(power_kw, current_a, is_startup=False):
    max_current = DEYE_MAX_CURRENT_A * (DEYE_OVERLOAD_FACTOR if is_startup else 1.0)
    max_power   = DEYE_MAX_POWER_KW  * (DEYE_OVERLOAD_FACTOR if is_startup else 1.0)

    current_ok = current_a <= max_current
    power_ok   = power_kw  <= max_power

    margin_current = ((max_current - current_a) / max_current) * 100
    margin_power   = ((max_power   - power_kw)  / max_power)   * 100

    if current_ok and power_ok:
        status = "⚠️  LIMITE" if min(margin_current, margin_power) < 10 else "✅ OK"
    else:
        status = "⛔ DÉCROCHAGE"

    return {
        "status": status,
        "current_ok": current_ok,
        "power_ok": power_ok,
        "margin_current": margin_current,
        "margin_power": margin_power,
        "is_startup": is_startup,
    }


def get_base_load_profile():
    power = np.zeros(24)
    current = np.zeros(24)

    for h in range(24):
        p, i = 0.0, 0.0

        p += BASE_APPLIANCES["refrigerateur"]["power_kw"]
        i += BASE_APPLIANCES["refrigerateur"]["current_a"]
        p += BASE_APPLIANCES["congelateur"]["power_kw"]
        i += BASE_APPLIANCES["congelateur"]["current_a"]

        if h < 7 or h >= 18:
            p += BASE_APPLIANCES["eclairage"]["power_kw"]
            i += BASE_APPLIANCES["eclairage"]["current_a"]

        if 6 <= h <= 9 or h >= 17:
            p += BASE_APPLIANCES["tv"]["power_kw"]
            i += BASE_APPLIANCES["tv"]["current_a"]
            p += BASE_APPLIANCES["ordinateurs"]["power_kw"]
            i += BASE_APPLIANCES["ordinateurs"]["current_a"]

        if 7 <= h <= 9:
            p += BASE_APPLIANCES["machine_laver"]["power_kw"]
            i += BASE_APPLIANCES["machine_laver"]["current_a"]

        if h in [7, 12, 19, 20]:
            p += BASE_APPLIANCES["four"]["power_kw"] * 0.5
            i += BASE_APPLIANCES["four"]["current_a"] * 0.5
            p += BASE_APPLIANCES["micro_ondes"]["power_kw"] * 0.5
            i += BASE_APPLIANCES["micro_ondes"]["current_a"] * 0.5

        if h in [6, 7, 18, 19]:
            p += BASE_APPLIANCES["pompe_eau"]["power_kw"]
            i += BASE_APPLIANCES["pompe_eau"]["current_a"]

        power[h]   = p
        current[h] = i

    return power, current


def simulate_progressive_startup(ac_sequence):
    base_power, base_current = get_base_load_profile()
    current_power   = base_power[14]
    current_nominal = base_current[14]

    results = []
    results.append({
        "etape": 0,
        "description": "Charge de base (14h)",
        "ac_type": None,
        "power_nominal_kw": current_power,
        "power_startup_kw": current_power,
        "current_nominal_a": current_nominal,
        "current_startup_a": current_nominal,
        "deye_nominal": check_deye_limits(current_power, current_nominal),
        "deye_startup": check_deye_limits(current_power, current_nominal),
    })

    for i, ac_type in enumerate(ac_sequence):
        ac = AC_CATALOG[ac_type]
        current_power   += ac["power_kw"]
        current_nominal += ac["current_nominal_a"]

        startup_power   = current_power - ac["power_kw"] + \
                          ac["power_kw"] * ac["startup_factor"]
        startup_current = current_nominal - ac["current_nominal_a"] + \
                          ac["current_startup_a"]

        results.append({
            "etape": i + 1,
            "description": f"Ajout clim {ac_type} (#{i+1})",
            "ac_type": ac_type,
            "power_nominal_kw": current_power,
            "power_startup_kw": startup_power,
            "current_nominal_a": current_nominal,
            "current_startup_a": startup_current,
            "deye_nominal": check_deye_limits(current_power, current_nominal),
            "deye_startup": check_deye_limits(startup_power, startup_current,
                                              is_startup=True),
        })

    return results


def get_total_load_profile(ac_config=None):
    power, current = get_base_load_profile()

    if ac_config:
        for ac_type, count in ac_config.items():
            ac = AC_CATALOG[ac_type]
            for h in range(24):
                if 9 <= h <= 23:
                    factor = 0.8 if 9 <= h <= 11 else (1.0 if h <= 18 else 0.7)
                    power[h]   += count * ac["power_kw"] * factor
                    current[h] += count * ac["current_nominal_a"] * factor

    return power, current


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from data.irradiation_abidjan import get_hours

    hours = get_hours()

    # ── Catalogue
    print(f"\n{'='*70}")
    print(f"  CATALOGUE CLIMATISEURS INVERTER")
    print(f"{'='*70}")
    print(f"  {'Type':8s} {'P(kW)':8s} {'cosφ':6s} {'I_nom(A)':10s} "
          f"{'Fact.':7s} {'I_start(A)':12s} {'Durée(s)'}")
    print(f"  {'-'*67}")
    for name, ac in AC_CATALOG.items():
        print(f"  {name:8s} {ac['power_kw']:8.3f} {ac['cos_phi']:6.2f} "
              f"{ac['current_nominal_a']:10.2f} x{ac['startup_factor']:.0f}    "
              f"{ac['current_startup_a']:12.2f} {ac['startup_duration_s']:8.1f}")

    print(f"\n  ONDULEUR DEYE 20kW LV :")
    print(f"  Puissance max     : {DEYE_MAX_POWER_KW} kW")
    print(f"  Puissance app.    : {DEYE_MAX_APPARENT_KVA} kVA")
    print(f"  Courant max/phase : {DEYE_MAX_CURRENT_A} A")
    print(f"  Surcharge courte  : x{DEYE_OVERLOAD_FACTOR} / {DEYE_OVERLOAD_DURATION_S}s")

    # ── Démarrage progressif
    sequence = ["1.5CV", "1.5CV", "2CV", "2CV", "3CV", "3CV"]
    results = simulate_progressive_startup(sequence)

    print(f"\n{'='*70}")
    print(f"  DEMARRAGE PROGRESSIF : {' > '.join(sequence)}")
    print(f"{'='*70}")
    print(f"  {'Etape':6s} {'Description':25s} {'P_nom(kW)':10s} "
          f"{'I_nom(A)':10s} {'I_start(A)':12s} {'Nominal':12s} {'Demarrage'}")
    print(f"  {'-'*85}")
    for r in results:
        print(f"  {r['etape']:6d} {r['description']:25s} "
              f"{r['power_nominal_kw']:10.2f} "
              f"{r['current_nominal_a']:10.2f} "
              f"{r['current_startup_a']:12.2f} "
              f"{r['deye_nominal']['status']:14s} "
              f"{r['deye_startup']['status']}")

    # ── Visualisation
    fig, axes = plt.subplots(3, 1, figsize=(13, 12))

    configs = [
        ("Sans clim",             {},                                "#607D8B"),
        ("2x1.5CV",               {"1.5CV": 2},                     "#2196F3"),
        ("2x1.5CV + 2x2CV",       {"1.5CV": 2, "2CV": 2},           "#FF9800"),
        ("2x1.5CV+2x2CV+2x3CV",   {"1.5CV": 2, "2CV": 2, "3CV": 2},"#F44336"),
    ]

    for label, cfg, color in configs:
        p, _ = get_total_load_profile(cfg)
        axes[0].plot(hours, p, label=label, linewidth=2, color=color)
    axes[0].axhline(y=DEYE_MAX_POWER_KW, color='red', linestyle='--',
                    linewidth=1.5, label=f'Limite DEYE ({DEYE_MAX_POWER_KW} kW)')
    axes[0].set_title("Charge progressive — Puissance (kW)", fontsize=12)
    axes[0].set_ylabel("Puissance (kW)")
    axes[0].legend(fontsize=9)
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xticks(hours)

    for label, cfg, color in configs:
        _, i = get_total_load_profile(cfg)
        axes[1].plot(hours, i, label=label, linewidth=2, color=color)
    axes[1].axhline(y=DEYE_MAX_CURRENT_A, color='red', linestyle='--',
                    linewidth=1.5, label=f'Limite DEYE ({DEYE_MAX_CURRENT_A} A/phase)')
    axes[1].set_title("Charge progressive — Courant par phase (A)", fontsize=12)
    axes[1].set_ylabel("Courant (A)")
    axes[1].legend(fontsize=9)
    axes[1].grid(True, alpha=0.3)
    axes[1].set_xticks(hours)

    etapes     = [r["etape"] for r in results]
    i_nominaux = [r["current_nominal_a"] for r in results]
    i_startups = [r["current_startup_a"] for r in results]
    labels_e   = [r["description"] for r in results]

    x = np.arange(len(etapes))
    w = 0.35
    bars1 = axes[2].bar(x - w/2, i_nominaux, w, label='Courant nominal (A)',
                        color='#4CAF50', alpha=0.85, edgecolor='black')
    bars2 = axes[2].bar(x + w/2, i_startups, w, label='Courant démarrage (A)',
                        color='#F44336', alpha=0.85, edgecolor='black')
    axes[2].axhline(y=DEYE_MAX_CURRENT_A, color='red', linestyle='--',
                    linewidth=2, label=f'Limite DEYE ({DEYE_MAX_CURRENT_A} A)')
    axes[2].axhline(y=DEYE_MAX_CURRENT_A * DEYE_OVERLOAD_FACTOR,
                    color='orange', linestyle='--', linewidth=1.5,
                    label=f'Surcharge ({DEYE_MAX_CURRENT_A*DEYE_OVERLOAD_FACTOR:.0f} A / {DEYE_OVERLOAD_DURATION_S}s)')
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels_e, rotation=15, ha='right', fontsize=8)
    axes[2].set_title("Courants nominaux vs démarrage progressif", fontsize=12)
    axes[2].set_ylabel("Courant (A)")
    axes[2].legend(fontsize=9)
    axes[2].grid(True, alpha=0.3, axis='y')

    for bar, val in zip(bars2, i_startups):
        axes[2].text(bar.get_x() + bar.get_width()/2,
                     bar.get_height() + 0.5,
                     f"{val:.1f}A", ha='center', fontsize=7, fontweight='bold')

    plt.tight_layout()
    plt.show()