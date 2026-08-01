"""
Gestionnaire d'énergie - Système hybride PV/Batterie/CIE
Logique de dispatch : PV → Batterie → CIE
Onduleur DEYE 20kW LV en mode hybride
"""

import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from data.irradiation_abidjan import get_hours
from models.pv_system import get_pv_profile
from models.battery import Battery
from models.load import (get_total_load_profile, simulate_progressive_startup,
                         check_deye_limits, DEYE_MAX_POWER_KW,
                         DEYE_MAX_CURRENT_A, DEYE_OVERLOAD_FACTOR,
                         DEYE_OVERLOAD_DURATION_S)

# ─── Paramètres réseau CIE ────────────────────────────────────────────────────
CIE_VOLTAGE_V        = 400.0    # Tension CIE triphasé (V)
CIE_AVAILABLE        = True     # CIE disponible (peut être False = coupure)

# ─── Priorités de dispatch ────────────────────────────────────────────────────
# 1. PV couvre la charge en priorité
# 2. Excès PV → charge batterie
# 3. Déficit PV → batterie complète
# 4. Batterie vide → CIE prend le relais
# 5. CIE indisponible + batterie vide → délestage


class EnergyManager:
    """
    Gestionnaire d'énergie du système hybride PV/Batterie/CIE.

    Gère le dispatch heure par heure sur 24h et enregistre
    tous les flux d'énergie pour visualisation.
    """

    def __init__(self, month: int = 1, ac_config: dict = None,
                 cie_available: bool = True):
        """
        Args:
            month: Mois de simulation (1-12)
            ac_config: Configuration clims ex: {"1.5CV": 2, "2CV": 1}
            cie_available: True si le réseau CIE est disponible
        """
        self.month         = month
        self.ac_config     = ac_config or {}
        self.cie_available = cie_available
        self.battery       = Battery()
        self.hours         = get_hours()

        # Profils
        self.pv_profile, _      = get_pv_profile(month), None
        self.pv_profile         = get_pv_profile(month)
        self.load_power, self.load_current = get_total_load_profile(ac_config)

        # Historiques de simulation
        self.history = {
            "pv_power":       np.zeros(24),  # Production PV (kW)
            "load_power":     np.zeros(24),  # Charge totale (kW)
            "load_current":   np.zeros(24),  # Courant charge (A)
            "battery_power":  np.zeros(24),  # Batterie (+charge / -décharge)
            "cie_power":      np.zeros(24),  # Apport CIE (kW)
            "soc":            np.zeros(24),  # État de charge batterie (%)
            "pv_curtailed":   np.zeros(24),  # PV écrêté (kW)
            "load_shed":      np.zeros(24),  # Délestage (kW)
            "deye_status":    [],            # Statut onduleur par heure
            "source":         [],            # Source principale par heure
        }

    def run(self):
        """Lance la simulation sur 24h."""

        for h in self.hours:
            pv   = self.pv_profile[h]
            load = self.load_power[h]
            load_i = self.load_current[h]

            # Vérification limites onduleur DEYE
            deye = check_deye_limits(load, load_i)
            self.history["deye_status"].append(deye["status"])

            # ── Dispatch ──────────────────────────────────────────────────────
            pv_to_load    = 0.0
            pv_to_bat     = 0.0
            bat_to_load   = 0.0
            cie_to_load   = 0.0
            curtailed     = 0.0
            shed          = 0.0
            source        = "AUCUNE"

            if load <= 0:
                # Pas de charge — tout le PV va en batterie
                if pv > 0 and not self.battery.is_full():
                    pv_to_bat = self.battery.charge(pv)
                    curtailed = pv - pv_to_bat
                source = "PV→BAT"

            elif pv >= load:
                # PV couvre toute la charge + excès éventuel
                pv_to_load = load
                excess = pv - load

                if excess > 0 and not self.battery.is_full():
                    pv_to_bat = self.battery.charge(excess)
                    curtailed = excess - pv_to_bat
                elif excess > 0:
                    curtailed = excess
                    self.battery.soc_history.append(self.battery.soc)
                    self.battery.power_history.append(0)
                else:
                    self.battery.soc_history.append(self.battery.soc)
                    self.battery.power_history.append(0)

                source = "PV"

            else:
                # PV insuffisant — déficit à couvrir
                pv_to_load = pv
                deficit    = load - pv

                if not self.battery.is_empty():
                    # Batterie couvre le déficit
                    bat_to_load = self.battery.discharge(deficit)
                    remaining   = deficit - bat_to_load

                    if remaining > 0:
                        # Batterie insuffisante → CIE complète
                        if self.cie_available:
                            cie_to_load = remaining
                            source = "PV+BAT+CIE"
                        else:
                            shed = remaining
                            source = "PV+BAT (DELESAGE)"
                    else:
                        source = "PV+BAT"
                else:
                    # Batterie vide → CIE
                    if self.cie_available:
                        cie_to_load = deficit
                        source = "PV+CIE"
                    else:
                        shed = deficit
                        source = "PV (DELESTAGE)"

            # ── Enregistrement ────────────────────────────────────────────────
            self.history["pv_power"][h]     = pv
            self.history["load_power"][h]   = load
            self.history["load_current"][h] = load_i
            self.history["battery_power"][h]= pv_to_bat - bat_to_load
            self.history["cie_power"][h]    = cie_to_load
            self.history["soc"][h]          = self.battery.get_soc_percent()
            self.history["pv_curtailed"][h] = curtailed
            self.history["load_shed"][h]    = shed
            self.history["source"].append(source)

        return self.history

    def print_summary(self):
        """Affiche le bilan énergétique de la journée."""
        h = self.history
        pv_total   = np.sum(h["pv_power"])
        load_total = np.sum(h["load_power"])
        cie_total  = np.sum(h["cie_power"])
        shed_total = np.sum(h["load_shed"])
        curtail    = np.sum(h["pv_curtailed"])
        bat_charge = np.sum(np.maximum(h["battery_power"], 0))
        bat_dis    = np.sum(np.maximum(-h["battery_power"], 0))

        autonomy = ((load_total - cie_total - shed_total) /
                    load_total * 100) if load_total > 0 else 0

        print(f"\n{'='*60}")
        print(f"  BILAN ENERGETIQUE JOURNALIER — Mois {self.month}")
        print(f"{'='*60}")
        print(f"  Production PV totale    : {pv_total:7.2f} kWh")
        print(f"  Consommation totale     : {load_total:7.2f} kWh")
        print(f"  Apport CIE              : {cie_total:7.2f} kWh")
        print(f"  Charge batterie         : {bat_charge:7.2f} kWh")
        print(f"  Décharge batterie       : {bat_dis:7.2f} kWh")
        print(f"  PV écrêté               : {curtail:7.2f} kWh")
        print(f"  Délestage               : {shed_total:7.2f} kWh")
        print(f"  SOC final batterie      : {self.battery.get_soc_percent():7.1f}%")
        print(f"  Taux d'autonomie solaire: {autonomy:7.1f}%")
        print(f"{'='*60}")

        print(f"\n  STATUT ONDULEUR DEYE PAR HEURE :")
        print(f"  {'Heure':6s} {'Source':20s} {'Charge(kW)':12s} "
              f"{'Courant(A)':12s} {'Statut DEYE'}")
        print(f"  {'-'*65}")
        for hour in self.hours:
            print(f"  {hour:02d}h    {h['source'][hour]:20s} "
                  f"{h['load_power'][hour]:12.2f} "
                  f"{h['load_current'][hour]:12.2f} "
                  f"{h['deye_status'][hour]}")


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    hours = get_hours()

    # ── Scénario 1 : journée normale avec 3 clims 1.5CV + 1 clim 2CV ─────────
    print("\n>>> SCENARIO 1 : Journée normale")
    mgr1 = EnergyManager(
        month=1,
        ac_config={"1.5CV": 3, "2CV": 1},
        cie_available=True
    )
    h1 = mgr1.run()
    mgr1.print_summary()

    # ── Scénario 2 : coupure CIE (pas de réseau) ─────────────────────────────
    print("\n>>> SCENARIO 2 : Coupure CIE")
    mgr2 = EnergyManager(
        month=6,
        ac_config={"1.5CV": 3, "2CV": 1},
        cie_available=False
    )
    h2 = mgr2.run()
    mgr2.print_summary()

    # ── Visualisation Scénario 1 ──────────────────────────────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    fig.suptitle("Système Hybride PV/Batterie/CIE — Bilan journalier",
                 fontsize=14, fontweight='bold')

    # Graphe 1 : flux de puissance
    axes[0].plot(hours, h1["pv_power"],     label="Production PV (kW)",
                 color="#FFC107", linewidth=2.5)
    axes[0].plot(hours, h1["load_power"],   label="Charge totale (kW)",
                 color="#F44336", linewidth=2.5, linestyle='--')
    axes[0].plot(hours, h1["cie_power"],    label="Apport CIE (kW)",
                 color="#9C27B0", linewidth=2, linestyle=':')

    bat = h1["battery_power"]
    axes[0].fill_between(hours, 0, bat,
                         where=bat >= 0, alpha=0.4, color='green',
                         label='Charge batterie')
    axes[0].fill_between(hours, 0, bat,
                         where=bat < 0, alpha=0.4, color='orange',
                         label='Décharge batterie')

    axes[0].axhline(y=DEYE_MAX_POWER_KW, color='red', linestyle='--',
                    alpha=0.5, linewidth=1, label=f'Limite DEYE ({DEYE_MAX_POWER_KW}kW)')
    axes[0].set_title("Flux de puissance — Scénario 1 (CIE disponible)", fontsize=11)
    axes[0].set_ylabel("Puissance (kW)")
    axes[0].legend(fontsize=8, loc='upper left')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xticks(hours)

    # Graphe 2 : SOC batterie
    axes[1].plot(hours, h1["soc"], color='#2196F3', linewidth=2.5, label='SOC (%)')
    axes[1].fill_between(hours, h1["soc"], 10, alpha=0.2, color='blue')
    axes[1].axhline(y=95, color='green', linestyle='--', alpha=0.7,
                    label='SOC max (95%)')
    axes[1].axhline(y=10, color='red', linestyle='--', alpha=0.7,
                    label='SOC min (10%)')
    axes[1].set_title("État de charge batterie (SOC)", fontsize=11)
    axes[1].set_ylabel("SOC (%)")
    axes[1].set_ylim(0, 100)
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3)
    axes[1].set_xticks(hours)

    # Graphe 3 : comparaison CIE dispo vs coupure
    axes[2].plot(hours, h1["cie_power"], label="CIE disponible (Scén.1)",
                 color="#9C27B0", linewidth=2)
    axes[2].plot(hours, h2["load_shed"], label="Délestage coupure CIE (Scén.2)",
                 color="#F44336", linewidth=2, linestyle='--')
    axes[2].fill_between(hours, h2["load_shed"], 0, alpha=0.3, color='red')
    axes[2].set_title("Impact coupure CIE — Énergie non couverte (kW)",
                      fontsize=11)
    axes[2].set_ylabel("Puissance (kW)")
    axes[2].set_xlabel("Heure de la journée")
    axes[2].legend(fontsize=8)
    axes[2].grid(True, alpha=0.3)
    axes[2].set_xticks(hours)

    plt.tight_layout()
    plt.show()