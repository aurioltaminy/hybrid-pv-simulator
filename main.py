"""
main.py — Point d'entrée principal
Simulateur Système Hybride PV/Batterie/CIE
27 kWc LONGI Solar | DEYE 20kW LV | 2 × 15 kWh LFP
Abidjan, Côte d'Ivoire
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.append(os.path.dirname(__file__))

from data.irradiation_abidjan import get_hours
from models.pv_system import get_pv_profile, SYSTEM_POWER_KWC, NUM_PANELS
from models.battery import TOTAL_CAPACITY_KWH, NUM_BATTERIES
from models.load import (AC_CATALOG, DEYE_MAX_POWER_KW, DEYE_MAX_CURRENT_A,
                         DEYE_OVERLOAD_FACTOR, DEYE_OVERLOAD_DURATION_S,
                         simulate_progressive_startup, get_total_load_profile,
                         check_deye_limits)
from simulation.energy_manager import EnergyManager


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║       SIMULATEUR SYSTÈME HYBRIDE PV/BATTERIE/CIE             ║
║       Abidjan, Côte d'Ivoire                                 ║
╠══════════════════════════════════════════════════════════════╣
║  PV      : LONGI Solar 650Wc x 42 = 27.3 kWc                ║
║  Onduleur: DEYE 20kW LV (triphasé 400V)                      ║
║  Batterie: 2 x 15 kWh LFP = 30 kWh                          ║
║  Réseau  : CIE triphasé 400V (backup)                        ║
╚══════════════════════════════════════════════════════════════╝
""")


def scenario_1_journee_normale():
    print("\n" + "="*60)
    print("  SCENARIO 1 — Journée normale (Janvier, CIE disponible)")
    print("="*60)
    mgr = EnergyManager(month=1, ac_config={"1.5CV": 3, "2CV": 1},
                        cie_available=True)
    mgr.run()
    mgr.print_summary()
    return mgr


def scenario_2_coupure_cie():
    print("\n" + "="*60)
    print("  SCENARIO 2 — Coupure CIE (Juin, saison des pluies)")
    print("="*60)
    mgr = EnergyManager(month=6, ac_config={"1.5CV": 3, "2CV": 1},
                        cie_available=False)
    mgr.run()
    mgr.print_summary()
    return mgr


def scenario_3_charge_max():
    print("\n" + "="*60)
    print("  SCENARIO 3 — Charge maximale (6 climatiseurs)")
    print("="*60)
    mgr = EnergyManager(month=1, ac_config={"1.5CV": 2, "2CV": 2, "3CV": 2},
                        cie_available=True)
    mgr.run()
    mgr.print_summary()
    return mgr


def scenario_4_demarrage_progressif():
    print("\n" + "="*60)
    print("  SCENARIO 4 — Démarrage progressif climatiseurs")
    print("="*60)
    sequence = ["1.5CV", "1.5CV", "2CV", "2CV", "3CV", "3CV"]
    results = simulate_progressive_startup(sequence)
    print(f"\n  Séquence : {' > '.join(sequence)}")
    print(f"\n  {'Etape':6s} {'Description':25s} {'I_nom(A)':10s} "
          f"{'I_start(A)':12s} {'Statut démarrage'}")
    print(f"  {'-'*70}")
    for r in results:
        print(f"  {r['etape']:6d} {r['description']:25s} "
              f"{r['current_nominal_a']:10.2f} "
              f"{r['current_startup_a']:12.2f} "
              f"{r['deye_startup']['status']}")
    return results


def scenario_5_analyse_courants():
    """
    Scénario 5 : Analyse complète des courants par phase.
    Montre heure par heure quand l'onduleur DEYE risque de décrocher.
    """
    print("\n" + "="*60)
    print("  SCENARIO 5 — Analyse des courants & décrochage DEYE")
    print("="*60)

    hours = get_hours()

    # Limite DEYE
    i_max_nominal  = DEYE_MAX_CURRENT_A                          # 29 A
    i_max_overload = DEYE_MAX_CURRENT_A * DEYE_OVERLOAD_FACTOR  # 36.25 A

    # Configurations à comparer
    configs = {
        "Sans clim":          {},
        "3x1.5CV":            {"1.5CV": 3},
        "3x1.5CV + 2x2CV":   {"1.5CV": 3, "2CV": 2},
        "3x1.5CV+2x2CV+1x3CV": {"1.5CV": 3, "2CV": 2, "3CV": 1},
    }

    print(f"\n  Limites onduleur DEYE 20kW LV :")
    print(f"  Courant nominal max  : {i_max_nominal:.1f} A/phase")
    print(f"  Courant surcharge    : {i_max_overload:.1f} A/phase "
          f"(x{DEYE_OVERLOAD_FACTOR} / {DEYE_OVERLOAD_DURATION_S}s max)")

    print(f"\n  COURANTS NOMINAUX PAR HEURE ET PAR CONFIGURATION :")
    print(f"\n  {'Heure':6s}", end="")
    for name in configs:
        print(f" {name:>22s}", end="")
    print(f"  {'Limite DEYE':>12s}")
    print(f"  {'-'*110}")

    all_currents = {}
    for name, cfg in configs.items():
        _, current = get_total_load_profile(cfg)
        all_currents[name] = current

    for h in hours:
        print(f"  {h:02d}h   ", end="")
        for name, current in all_currents.items():
            i = current[h]
            status = check_deye_limits(0, i)["status"]
            flag = " ⛔" if "DECROCHAGE" in status else (
                   " ⚠" if "LIMITE" in status else "   ")
            print(f" {i:>18.2f} A{flag}", end="")
        print(f"  {i_max_nominal:>10.1f} A")

    # Analyse démarrage simultané par type de clim
    print(f"\n  COURANTS DE DÉMARRAGE — Impact sur DEYE :")
    print(f"\n  {'Config':35s} {'I_nom(A)':10s} {'I_start(A)':12s} "
          f"{'Marge nom.(%)':15s} {'Marge start(%)':15s} {'Statut'}")
    print(f"  {'-'*100}")

    base_p, base_i = get_total_load_profile({})
    base_current = base_i[14]  # 14h = heure de pointe

    combos = [
        ("Base seule (14h)",          {},                       0),
        ("Base + 1x1.5CV",            {"1.5CV": 1},            1),
        ("Base + 2x1.5CV",            {"1.5CV": 2},            2),
        ("Base + 3x1.5CV",            {"1.5CV": 3},            3),
        ("Base + 1x2CV",              {"2CV": 1},              1),
        ("Base + 2x2CV",              {"2CV": 2},              2),
        ("Base + 1x3CV",              {"3CV": 1},              1),
        ("Base + 1x1.5CV + 1x2CV",   {"1.5CV": 1, "2CV": 1},  2),
        ("Base + 2x1.5CV + 1x2CV",   {"1.5CV": 2, "2CV": 1},  3),
        ("Base + 2x1.5CV + 2x2CV",   {"1.5CV": 2, "2CV": 2},  4),
        ("Base + 3x1.5CV + 2x2CV",   {"1.5CV": 3, "2CV": 2},  5),
    ]

    results_courant = []
    for label, cfg, n_ac in combos:
        _, i_profile = get_total_load_profile(cfg)
        i_nom = i_profile[14]

        # Courant de démarrage = courant nominal + pic du dernier clim ajouté
        i_start = i_nom
        for ac_type, count in cfg.items():
            ac = AC_CATALOG[ac_type]
            # On retire le courant nominal et ajoute le courant de démarrage
            i_start = i_start - (count * ac["current_nominal_a"]) + \
                      (count * ac["current_startup_a"])

        margin_nom   = ((i_max_nominal  - i_nom)   / i_max_nominal)  * 100
        margin_start = ((i_max_overload - i_start) / i_max_overload) * 100

        status_nom   = check_deye_limits(0, i_nom)["status"]
        status_start = check_deye_limits(0, i_start, is_startup=True)["status"]

        results_courant.append({
            "label":         label,
            "i_nom":         i_nom,
            "i_start":       i_start,
            "margin_nom":    margin_nom,
            "margin_start":  margin_start,
            "status_nom":    status_nom,
            "status_start":  status_start,
        })

        print(f"  {label:35s} {i_nom:10.2f} {i_start:12.2f} "
              f"{margin_nom:15.1f} {margin_start:15.1f} {status_start}")

    return all_currents, results_courant


def plot_courants(all_currents, results_courant):
    """Visualisation complète des courants et seuils de décrochage."""
    hours = get_hours()
    i_max_nominal  = DEYE_MAX_CURRENT_A
    i_max_overload = DEYE_MAX_CURRENT_A * DEYE_OVERLOAD_FACTOR

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(
        "Analyse des courants — Décrochage onduleur DEYE 20kW LV\n"
        "Triphasé 400V | I_max = 29 A/phase | Surcharge = 36.25 A / 10s",
        fontsize=13, fontweight='bold'
    )

    colors = ["#607D8B", "#2196F3", "#FF9800", "#F44336"]

    # ── Graphe 1 : courants nominaux sur 24h ─────────────────────────────────
    ax = axes[0][0]
    for (name, current), color in zip(all_currents.items(), colors):
        ax.plot(hours, current, label=name, linewidth=2, color=color)

    ax.axhline(y=i_max_nominal, color='red', linestyle='--', linewidth=2,
               label=f'Limite nominale DEYE ({i_max_nominal} A)')
    ax.axhline(y=i_max_overload, color='orange', linestyle='--', linewidth=1.5,
               label=f'Surcharge courte ({i_max_overload:.1f} A / {DEYE_OVERLOAD_DURATION_S}s)')

    # Zones colorées
    ax.axhspan(0, i_max_nominal * 0.8, alpha=0.05, color='green')
    ax.axhspan(i_max_nominal * 0.8, i_max_nominal, alpha=0.08, color='orange')
    ax.axhspan(i_max_nominal, i_max_overload, alpha=0.08, color='red')
    ax.axhspan(i_max_overload, 80, alpha=0.1, color='darkred')

    ax.set_title("Courants nominaux par phase (24h)", fontsize=11)
    ax.set_ylabel("Courant (A)")
    ax.set_xlabel("Heure")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xticks(hours)
    ax.set_ylim(0, 80)

    # ── Graphe 2 : courants de démarrage vs limites DEYE ─────────────────────
    ax2 = axes[0][1]
    labels  = [r["label"].replace("Base + ", "") for r in results_courant]
    i_noms  = [r["i_nom"] for r in results_courant]
    i_starts= [r["i_start"] for r in results_courant]

    x = np.arange(len(labels))
    w = 0.38

    bar_colors_start = []
    for r in results_courant:
        if r["i_start"] <= i_max_nominal:
            bar_colors_start.append("#4CAF50")
        elif r["i_start"] <= i_max_overload:
            bar_colors_start.append("#FF9800")
        else:
            bar_colors_start.append("#F44336")

    ax2.bar(x - w/2, i_noms,   w, label='I nominal (A)',
            color='#2196F3', alpha=0.85, edgecolor='black')
    ax2.bar(x + w/2, i_starts, w, label='I démarrage (A)',
            color=bar_colors_start, alpha=0.85, edgecolor='black')

    ax2.axhline(y=i_max_nominal, color='red', linestyle='--', linewidth=2,
                label=f'Limite nominale ({i_max_nominal} A)')
    ax2.axhline(y=i_max_overload, color='orange', linestyle='--', linewidth=1.5,
                label=f'Surcharge ({i_max_overload:.1f} A / {DEYE_OVERLOAD_DURATION_S}s)')

    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=30, ha='right', fontsize=7)
    ax2.set_title("Courants nominaux vs démarrage — Configurations", fontsize=11)
    ax2.set_ylabel("Courant (A)")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_ylim(0, max(i_starts) * 1.2)

    for i, (bar, val) in enumerate(zip(
            ax2.patches[len(labels):], i_starts)):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + 0.5,
                 f"{val:.1f}A", ha='center', fontsize=6, fontweight='bold')

    # ── Graphe 3 : marges de courant ─────────────────────────────────────────
    ax3 = axes[1][0]
    margins_nom   = [r["margin_nom"] for r in results_courant]
    margins_start = [r["margin_start"] for r in results_courant]

    bar_m_colors = ["#4CAF50" if m > 10 else
                    "#FF9800" if m > 0 else
                    "#F44336" for m in margins_start]

    ax3.bar(x - w/2, margins_nom,   w, label='Marge nominale (%)',
            color='#2196F3', alpha=0.8, edgecolor='black')
    ax3.bar(x + w/2, margins_start, w, label='Marge démarrage (%)',
            color=bar_m_colors, alpha=0.8, edgecolor='black')

    ax3.axhline(y=0,  color='red',    linestyle='--', linewidth=2,
                label='Seuil décrochage (0%)')
    ax3.axhline(y=10, color='orange', linestyle='--', linewidth=1.5,
                label='Zone limite (10%)')

    ax3.set_xticks(x)
    ax3.set_xticklabels(labels, rotation=30, ha='right', fontsize=7)
    ax3.set_title("Marges par rapport aux limites DEYE (%)", fontsize=11)
    ax3.set_ylabel("Marge (%)")
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3, axis='y')

    # ── Graphe 4 : zones de fonctionnement DEYE ──────────────────────────────
    ax4 = axes[1][1]

    zone_labels = [
        f"Zone verte\n(0 → {i_max_nominal*0.8:.0f} A)\nFonctionnement normal",
        f"Zone orange\n({i_max_nominal*0.8:.0f} → {i_max_nominal} A)\nProche limite",
        f"Zone rouge\n({i_max_nominal} → {i_max_overload:.0f} A)\nSurcharge courte",
        f"Zone critique\n(> {i_max_overload:.0f} A)\nDécrochage garanti",
    ]
    zone_sizes  = [i_max_nominal*0.8,
                   i_max_nominal*0.2,
                   i_max_overload - i_max_nominal,
                   20]
    zone_colors = ["#4CAF50", "#FF9800", "#F44336", "#B71C1C"]

    wedges, texts, autotexts = ax4.pie(
        zone_sizes, labels=zone_labels, colors=zone_colors,
        autopct='%1.0f%%', startangle=90,
        textprops={'fontsize': 8},
        wedgeprops={'edgecolor': 'white', 'linewidth': 2}
    )
    ax4.set_title(
        f"Zones de fonctionnement DEYE 20kW\n"
        f"I_max = {i_max_nominal} A | Surcharge = {i_max_overload:.1f} A",
        fontsize=11
    )

    # Légende statuts
    legend_patches = [
        mpatches.Patch(color='#4CAF50', label='✅ OK — fonctionnement normal'),
        mpatches.Patch(color='#FF9800', label='⚠️  LIMITE — surveiller'),
        mpatches.Patch(color='#F44336', label='⛔ DÉCROCHAGE — onduleur coupe'),
    ]
    ax4.legend(handles=legend_patches, loc='lower center',
               bbox_to_anchor=(0.5, -0.15), fontsize=8)

    plt.tight_layout()
    plt.show()


def plot_all_scenarios(mgr1, mgr2, mgr3):
    """Visualisation comparative des 3 scénarios principaux."""
    hours = get_hours()
    fig, axes = plt.subplots(3, 2, figsize=(16, 14))
    fig.suptitle(
        "Simulateur Hybride PV/Batterie/CIE — 27.3 kWc | DEYE 20kW | 30 kWh\n"
        "Abidjan, Côte d'Ivoire",
        fontsize=13, fontweight='bold'
    )

    scenarios = [
        (mgr1, "Scén.1 — Normal (Jan, CIE dispo)", 0),
        (mgr2, "Scén.2 — Coupure CIE (Juin)",      1),
        (mgr3, "Scén.3 — Charge max (6 clims)",    2),
    ]

    for mgr, title, row in scenarios:
        h = mgr.history

        ax = axes[row][0]
        ax.plot(hours, h["pv_power"],   label="PV (kW)",
                color="#FFC107", linewidth=2)
        ax.plot(hours, h["load_power"], label="Charge (kW)",
                color="#F44336", linewidth=2, linestyle='--')
        ax.plot(hours, h["cie_power"],  label="CIE (kW)",
                color="#9C27B0", linewidth=1.5, linestyle=':')

        bat = h["battery_power"]
        ax.fill_between(hours, 0, bat, where=bat >= 0,
                        alpha=0.35, color='green', label='Charge bat.')
        ax.fill_between(hours, 0, bat, where=bat < 0,
                        alpha=0.35, color='orange', label='Décharge bat.')

        if np.sum(h["load_shed"]) > 0:
            ax.fill_between(hours, 0, h["load_shed"],
                            alpha=0.5, color='red', label='Délestage')

        ax.axhline(y=DEYE_MAX_POWER_KW, color='red',
                   linestyle='--', alpha=0.4, linewidth=1)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("Puissance (kW)")
        ax.set_xlabel("Heure")
        ax.legend(fontsize=7, loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.set_xticks(range(0, 24, 2))

        ax2 = axes[row][1]
        ax2.plot(hours, h["soc"], color='#2196F3', linewidth=2, label='SOC (%)')
        ax2.fill_between(hours, h["soc"], 10, alpha=0.2, color='blue')
        ax2.axhline(y=95, color='green', linestyle='--',
                    alpha=0.7, linewidth=1, label='SOC max (95%)')
        ax2.axhline(y=10, color='red', linestyle='--',
                    alpha=0.7, linewidth=1, label='SOC min (10%)')
        ax2.set_title(f"SOC Batterie — {title}", fontsize=10)
        ax2.set_ylabel("SOC (%)")
        ax2.set_xlabel("Heure")
        ax2.set_ylim(0, 100)
        ax2.legend(fontsize=7)
        ax2.grid(True, alpha=0.3)
        ax2.set_xticks(range(0, 24, 2))

    plt.tight_layout()
    plt.show()


def main():
    print_banner()

    mgr1 = scenario_1_journee_normale()
    mgr2 = scenario_2_coupure_cie()
    mgr3 = scenario_3_charge_max()
    scenario_4_demarrage_progressif()
    all_currents, results_courant = scenario_5_analyse_courants()

    print("\n  Génération des graphiques — Scénarios énergie...")
    plot_all_scenarios(mgr1, mgr2, mgr3)

    print("\n  Génération des graphiques — Analyse courants DEYE...")
    plot_courants(all_currents, results_courant)


if __name__ == "__main__":
    main()