"""
transient_analysis.py — Analyse transitoire seconde par seconde
Un graphique par étape de démarrage — analyse claire et détaillée
Fenêtre : 30 secondes | Résolution : 1 seconde
Comportement DEYE : délai 10s avant coupure si surcharge
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from models.load import (AC_CATALOG, DEYE_MAX_CURRENT_A, DEYE_OVERLOAD_FACTOR,
                         DEYE_OVERLOAD_DURATION_S, get_total_load_profile)

# ─── Paramètres ──────────────────────────────────────────────────────────────
WINDOW_S         = 30
DT_S             = 1
TIME_STEPS       = WINDOW_S // DT_S
I_MAX_NOMINAL    = DEYE_MAX_CURRENT_A
I_MAX_OVERLOAD   = DEYE_MAX_CURRENT_A * DEYE_OVERLOAD_FACTOR
T_OVERLOAD_MAX_S = DEYE_OVERLOAD_DURATION_S

STATE_COLORS = {
    "NORMAL":     "#4CAF50",
    "SURCHARGE":  "#FF9800",
    "DECROCHAGE": "#F44336",
}


def get_startup_current_profile(ac_type, t_array, t_start=2.0):
    ac    = AC_CATALOG[ac_type]
    i_nom = ac["current_nominal_a"]
    i_peak= ac["current_startup_a"]
    t_dur = ac["startup_duration_s"]
    tau   = 3.0
    current = np.zeros(len(t_array))
    for k, t in enumerate(t_array):
        dt = t - t_start
        if dt < 0:
            current[k] = 0.0
        elif dt <= t_dur:
            ramp = min(dt / 0.5, 1.0)
            current[k] = i_peak * ramp
        elif dt <= t_dur + tau * 3:
            current[k] = i_nom + (i_peak - i_nom) * np.exp(-(dt - t_dur) / tau)
        else:
            current[k] = i_nom
    return current


def simulate_deye_response(total_current, t_array):
    n = len(t_array)
    deye_current   = np.zeros(n)
    deye_state     = []
    events         = []
    overload_timer = 0
    is_tripped     = False
    trip_time      = None

    for k in range(n):
        t        = t_array[k]
        i_demand = total_current[k]

        if is_tripped:
            deye_current[k] = 0.0
            deye_state.append("DECROCHAGE")
            if i_demand <= I_MAX_NOMINAL * 0.85 and trip_time is not None and (t - trip_time) >= 5:
                is_tripped     = False
                overload_timer = 0
                events.append({"time": t, "type": "RETOUR_NORMAL",
                                "current": i_demand})

        elif i_demand > I_MAX_OVERLOAD:
            deye_current[k] = I_MAX_OVERLOAD
            deye_state.append("DECROCHAGE")
            is_tripped     = True
            trip_time      = t
            overload_timer = 0
            events.append({"time": t, "type": "DECROCHAGE_IMMEDIAT",
                           "current": i_demand})

        elif i_demand > I_MAX_NOMINAL:
            overload_timer += DT_S
            deye_current[k] = i_demand
            deye_state.append("SURCHARGE")
            if overload_timer == DT_S:
                events.append({"time": t, "type": "DEBUT_SURCHARGE",
                               "current": i_demand})
            if overload_timer >= T_OVERLOAD_MAX_S:
                is_tripped   = True
                trip_time    = t
                deye_state[-1] = "DECROCHAGE"
                events.append({"time": t, "type": "DECROCHAGE_10S",
                               "current": i_demand})

        else:
            overload_timer  = 0
            deye_current[k] = i_demand
            deye_state.append("NORMAL")

    return {"deye_current": deye_current, "deye_state": deye_state,
            "events": events, "trip_time": trip_time}


def simulate_progressive_transient(ac_sequence, base_current):
    results = []
    t = np.arange(0, WINDOW_S, DT_S)
    cumulative_nominal = base_current

    for step, ac_type in enumerate(ac_sequence):
        ac        = AC_CATALOG[ac_type]
        i_startup = get_startup_current_profile(ac_type, t, t_start=2.0)
        i_total   = cumulative_nominal + i_startup
        deye      = simulate_deye_response(i_total, t)

        results.append({
            "step":            step + 1,
            "ac_type":         ac_type,
            "ac":              ac,
            "t":               t,
            "i_base":          cumulative_nominal,
            "i_startup":       i_startup,
            "i_total":         i_total,
            "i_nominal_final": cumulative_nominal + ac["current_nominal_a"],
            "deye":            deye,
        })

        cumulative_nominal += ac["current_nominal_a"]

    return results


def plot_single_step(r, show=True):
    """Affiche un graphique clair pour une seule étape de démarrage."""
    t        = r["t"]
    i_total  = r["i_total"]
    deye     = r["deye"]
    ac       = r["ac"]
    ac_type  = r["ac_type"]
    step     = r["step"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8),
                                   gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle(
        f"Étape {step} — Démarrage climatiseur {ac_type}  "
        f"({ac['power_cv']} CV | cosφ={ac['cos_phi']} | "
        f"I_nom={ac['current_nominal_a']:.1f}A | "
        f"I_peak={ac['current_startup_a']:.1f}A)\n"
        f"Courant de base avant démarrage : {r['i_base']:.1f}A  |  "
        f"Courant nominal après régime : {r['i_nominal_final']:.1f}A",
        fontsize=12, fontweight='bold'
    )

    # ── Fond coloré selon état DEYE ───────────────────────────────────────────
    for k in range(len(t) - 1):
        state = deye["deye_state"][k]
        ax1.axvspan(t[k], t[k+1], alpha=0.12,
                    color=STATE_COLORS[state], zorder=0)

    # ── Courbes ───────────────────────────────────────────────────────────────
    ax1.plot(t, i_total, color='#1565C0', linewidth=3,
             label='I total demandé (A)', zorder=5)
    ax1.plot(t, deye["deye_current"], color='black', linewidth=2,
             linestyle='--', label='I fourni par DEYE (A)', zorder=5)
    ax1.plot(t, r["i_base"] + r["i_startup"], color='#E65100',
             linewidth=1.8, linestyle=':', alpha=0.8,
             label=f'Contribution clim {ac_type} (A)', zorder=4)

    # ── Lignes limites ────────────────────────────────────────────────────────
    ax1.axhline(y=I_MAX_NOMINAL, color='red', linestyle='--', linewidth=2,
                label=f'I_max nominal DEYE ({I_MAX_NOMINAL}A)')
    ax1.axhline(y=I_MAX_OVERLOAD, color='darkred', linestyle='-.',
                linewidth=2,
                label=f'I_max surcharge ({I_MAX_OVERLOAD:.1f}A / {T_OVERLOAD_MAX_S}s)')
    ax1.axhline(y=r["i_base"], color='gray', linestyle=':',
                linewidth=1.5, alpha=0.7,
                label=f'I base ({r["i_base"]:.1f}A)')
    ax1.axhline(y=r["i_nominal_final"], color='green', linestyle=':',
                linewidth=1.5, alpha=0.8,
                label=f'I nominal final ({r["i_nominal_final"]:.1f}A)')

    # ── Zones colorées ────────────────────────────────────────────────────────
    y_max = max(max(i_total) * 1.2, I_MAX_OVERLOAD * 1.15)
    ax1.axhspan(0, I_MAX_NOMINAL,   alpha=0.04, color='green',  zorder=0)
    ax1.axhspan(I_MAX_NOMINAL, I_MAX_OVERLOAD, alpha=0.06,
                color='orange', zorder=0)
    ax1.axhspan(I_MAX_OVERLOAD, y_max, alpha=0.06, color='red', zorder=0)

    # ── Annotations événements ────────────────────────────────────────────────
    for ev in deye["events"]:
        color_ev = "#B71C1C" if "DECROCHAGE" in ev["type"] else "#E65100"
        ax1.axvline(x=ev["time"], color=color_ev,
                    linestyle='--', linewidth=2, alpha=0.9)

        label_map = {
            "DEBUT_SURCHARGE":    f"⚠️ Surcharge\nt={ev['time']:.0f}s",
            "DECROCHAGE_IMMEDIAT":f"⛔ Décrochage\nimm. t={ev['time']:.0f}s",
            "DECROCHAGE_10S":     f"⛔ Décrochage\n10s t={ev['time']:.0f}s",
            "RETOUR_NORMAL":      f"✅ Retour\nnormal t={ev['time']:.0f}s",
        }
        label_ev = label_map.get(ev["type"], ev["type"])
        ax1.text(ev["time"] + 0.4, y_max * 0.88,
                 label_ev, fontsize=8.5, color=color_ev,
                 fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                           alpha=0.8, edgecolor=color_ev))

    ax1.set_ylabel("Courant (A)", fontsize=11)
    ax1.legend(fontsize=8.5, loc='upper right',
               framealpha=0.9, ncol=2)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, WINDOW_S)
    ax1.set_ylim(0, y_max)
    ax1.set_xticks(range(0, WINDOW_S + 1, 1))
    ax1.tick_params(axis='x', labelsize=8)

    # ── Barre d'état DEYE seconde par seconde ────────────────────────────────
    state_map   = {"NORMAL": 1, "SURCHARGE": 2, "DECROCHAGE": 3}
    state_nums  = [state_map[s] for s in deye["deye_state"]]
    state_color_list = [STATE_COLORS[s] for s in deye["deye_state"]]

    for k in range(len(t)):
        ax2.bar(t[k], state_nums[k], width=DT_S * 0.92,
                color=state_color_list[k], edgecolor='white',
                linewidth=0.5, alpha=0.95)

    ax2.set_yticks([1, 2, 3])
    ax2.set_yticklabels(["✅ NORMAL", "⚠️  SURCHARGE", "⛔ DÉCROCHAGE"],
                        fontsize=10)
    ax2.set_xlabel("Temps (s)", fontsize=11)
    ax2.set_xlim(0, WINDOW_S)
    ax2.set_xticks(range(0, WINDOW_S + 1, 1))
    ax2.tick_params(axis='x', labelsize=8)
    ax2.set_ylim(0.4, 3.6)
    ax2.set_title("État onduleur DEYE — seconde par seconde", fontsize=10)
    ax2.grid(True, alpha=0.2, axis='x')

    # Résumé textuel
    states = deye["deye_state"]
    n_ok  = states.count("NORMAL")
    n_ol  = states.count("SURCHARGE")
    n_tr  = states.count("DECROCHAGE")
    summary = (f"Normal: {n_ok}s  |  Surcharge: {n_ol}s  |  "
               f"Décrochage: {n_tr}s  |  "
               f"I_pic: {max(i_total):.1f}A  |  "
               f"I_final: {r['i_nominal_final']:.1f}A")
    fig.text(0.5, 0.01, summary, ha='center', fontsize=10,
             bbox=dict(boxstyle='round', facecolor='#E3F2FD', alpha=0.8))

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    fname = f"transient_step{step}_{ac_type}.png"
    plt.savefig(fname, dpi=150, bbox_inches='tight')
    print(f"  Graphique sauvegardé : {fname}")
    if show:
        plt.show()
    plt.close()


if __name__ == "__main__":
    _, base_i = get_total_load_profile({})
    base_current = base_i[14]

    sequence = ["1.5CV", "1.5CV", "2CV", "2CV", "3CV", "3CV"]

    print(f"\n{'='*65}")
    print(f"  ANALYSE TRANSITOIRE — DEYE 20kW LV | Résolution 1s")
    print(f"  Base domicile (14h) : {base_current:.2f} A")
    print(f"  I_max nominal       : {I_MAX_NOMINAL} A")
    print(f"  I_max surcharge     : {I_MAX_OVERLOAD:.2f} A / {T_OVERLOAD_MAX_S}s")
    print(f"  Séquence            : {' → '.join(sequence)}")
    print(f"{'='*65}")

    results = simulate_progressive_transient(sequence, base_current)

    for r in results:
        deye   = r["deye"]
        i_peak = max(r["i_total"])
        states = deye["deye_state"]

        print(f"\n  Étape {r['step']} — Clim {r['ac_type']} "
              f"({r['ac']['power_cv']}CV)")
        print(f"  I base : {r['i_base']:.2f}A | "
              f"I pic : {i_peak:.2f}A | "
              f"I final : {r['i_nominal_final']:.2f}A")
        print(f"  Normal: {states.count('NORMAL')}s | "
              f"Surcharge: {states.count('SURCHARGE')}s | "
              f"Décrochage: {states.count('DECROCHAGE')}s")
        for ev in deye["events"]:
            icon = "⛔" if "DECROCHAGE" in ev["type"] else (
                   "⚠️ " if "SURCHARGE" in ev["type"] else "✅")
            print(f"  {icon} t={ev['time']:.0f}s → {ev['type']} "
                  f"(I={ev['current']:.1f}A)")

        print(f"\n  → Affichage étape {r['step']}...")
        plot_single_step(r, show=True)