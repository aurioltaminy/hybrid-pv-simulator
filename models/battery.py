"""
Modèle des batteries - 2 × LV 15 kWh
Capacité totale : 30 kWh
Technologie : Lithium LFP (LiFePO4) basse tension
Compatible onduleur DEYE 20 kW LV
"""

import numpy as np


# ─── Caractéristiques batteries LV 15 kWh ────────────────────────────────────
NUM_BATTERIES        = 2          # Nombre de batteries
CAPACITY_PER_BAT_KWH = 15.0      # Capacité par batterie (kWh)
TOTAL_CAPACITY_KWH   = NUM_BATTERIES * CAPACITY_PER_BAT_KWH  # 30 kWh

SOC_MAX              = 0.95       # État de charge maximum : 95%
SOC_MIN              = 0.10       # État de charge minimum : 10% (protection)
SOC_INITIAL          = 0.80      # État de charge initial : 80%

CHARGE_EFFICIENCY    = 0.97       # Rendement en charge : 97%
DISCHARGE_EFFICIENCY = 0.97       # Rendement en décharge : 97%

# Puissance max de charge/décharge (limitée par l'onduleur DEYE 20 kW)
MAX_CHARGE_POWER_KW   = 10.0     # Puissance max de charge : 10 kW
MAX_DISCHARGE_POWER_KW = 10.0    # Puissance max de décharge : 10 kW


class Battery:
    """
    Modèle de batterie LFP avec gestion du SOC (State of Charge).

    La batterie peut :
    - Se charger quand le PV produit plus que la charge
    - Se décharger quand la charge dépasse le PV
    - Se protéger contre la surcharge et la décharge profonde
    """

    def __init__(self):
        self.capacity_kwh    = TOTAL_CAPACITY_KWH
        self.soc             = SOC_INITIAL        # État de charge actuel (0-1)
        self.soc_max         = SOC_MAX
        self.soc_min         = SOC_MIN
        self.charge_eff      = CHARGE_EFFICIENCY
        self.discharge_eff   = DISCHARGE_EFFICIENCY
        self.max_charge_kw   = MAX_CHARGE_POWER_KW
        self.max_discharge_kw = MAX_DISCHARGE_POWER_KW

        # Historique pour visualisation
        self.soc_history     = []
        self.power_history   = []  # + = charge, - = décharge

    def charge(self, power_kw: float, duration_h: float = 1.0) -> float:
        """
        Charge la batterie avec une puissance donnée.

        Args:
            power_kw (float): Puissance de charge disponible (kW)
            duration_h (float): Durée en heures (1h par défaut)

        Returns:
            float: Puissance réellement absorbée (kW)
        """
        # Limite par la puissance max de charge
        power_kw = min(power_kw, self.max_charge_kw)

        # Énergie qu'on peut encore stocker
        energy_available = (self.soc_max - self.soc) * self.capacity_kwh

        # Énergie qu'on veut charger (avec rendement)
        energy_to_store = power_kw * duration_h * self.charge_eff

        # On ne peut pas dépasser la capacité
        energy_stored = min(energy_to_store, energy_available)

        # Mise à jour du SOC
        self.soc += energy_stored / self.capacity_kwh

        # Puissance réellement absorbée
        actual_power = energy_stored / (duration_h * self.charge_eff)

        self.soc_history.append(self.soc)
        self.power_history.append(actual_power)

        return actual_power

    def discharge(self, power_kw: float, duration_h: float = 1.0) -> float:
        """
        Décharge la batterie pour alimenter la charge.

        Args:
            power_kw (float): Puissance demandée (kW)
            duration_h (float): Durée en heures (1h par défaut)

        Returns:
            float: Puissance réellement fournie (kW)
        """
        # Limite par la puissance max de décharge
        power_kw = min(power_kw, self.max_discharge_kw)

        # Énergie disponible dans la batterie
        energy_available = (self.soc - self.soc_min) * self.capacity_kwh

        # Énergie demandée (avec rendement)
        energy_needed = power_kw * duration_h / self.discharge_eff

        # On ne peut pas dépasser ce qui est disponible
        energy_used = min(energy_needed, energy_available)

        # Mise à jour du SOC
        self.soc -= energy_used / self.capacity_kwh

        # Puissance réellement fournie
        actual_power = energy_used * self.discharge_eff / duration_h

        self.soc_history.append(self.soc)
        self.power_history.append(-actual_power)  # Négatif = décharge

        return actual_power

    def get_soc_percent(self) -> float:
        """Retourne le SOC en pourcentage (0-100%)"""
        return self.soc * 100

    def is_full(self) -> bool:
        """Vérifie si la batterie est pleine"""
        return self.soc >= self.soc_max

    def is_empty(self) -> bool:
        """Vérifie si la batterie est vide (seuil de protection atteint)"""
        return self.soc <= self.soc_min

    def reset(self):
        """Réinitialise la batterie pour une nouvelle simulation"""
        self.soc = SOC_INITIAL
        self.soc_history = []
        self.power_history = []


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from data.irradiation_abidjan import get_hours
    from models.pv_system import get_pv_profile

    hours = get_hours()
    bat = Battery()

    print(f"{'='*55}")
    print(f"  Système Batterie - {NUM_BATTERIES} × {CAPACITY_PER_BAT_KWH} kWh LFP")
    print(f"  Capacité totale  : {TOTAL_CAPACITY_KWH} kWh")
    print(f"  SOC initial      : {SOC_INITIAL*100:.0f}%")
    print(f"  SOC min/max      : {SOC_MIN*100:.0f}% / {SOC_MAX*100:.0f}%")
    print(f"{'='*55}")

    # Simulation simple : charge avec excès PV, décharge la nuit
    pv = get_pv_profile(month=1)
    charge_base = 8.0   # kW charge de base du domicile

    soc_log = []
    power_log = []

    for h in hours:
        pv_power = pv[h]
        excess = pv_power - charge_base

        if excess > 0 and not bat.is_full():
            # Excès PV → charge batterie
            p = bat.charge(excess)
            power_log.append(p)
        elif excess < 0 and not bat.is_empty():
            # Déficit → décharge batterie
            p = bat.discharge(abs(excess))
            power_log.append(-p)
        else:
            bat.soc_history.append(bat.soc)
            bat.power_history.append(0)
            power_log.append(0)

        soc_log.append(bat.get_soc_percent())
        print(f"  H{h:02d}h → PV: {pv_power:5.2f} kW | "
              f"Charge: {charge_base:.1f} kW | "
              f"Batterie: {power_log[-1]:+.2f} kW | "
              f"SOC: {bat.get_soc_percent():.1f}%")

    # Visualisation
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    ax1.plot(hours, power_log, color='orange', linewidth=2, label='Puissance batterie (kW)')
    ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax1.fill_between(hours, power_log, 0,
                     where=[p > 0 for p in power_log], color='green', alpha=0.3, label='Charge')
    ax1.fill_between(hours, power_log, 0,
                     where=[p < 0 for p in power_log], color='red', alpha=0.3, label='Décharge')
    ax1.set_ylabel("Puissance (kW)")
    ax1.set_title("Comportement de la batterie - 2 × 15 kWh LFP")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(hours, soc_log, color='blue', linewidth=2, label='SOC (%)')
    ax2.axhline(y=SOC_MAX*100, color='green', linestyle='--', alpha=0.7, label=f'SOC max ({SOC_MAX*100:.0f}%)')
    ax2.axhline(y=SOC_MIN*100, color='red', linestyle='--', alpha=0.7, label=f'SOC min ({SOC_MIN*100:.0f}%)')
    ax2.set_ylabel("État de charge (%)")
    ax2.set_xlabel("Heure de la journée")
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.xticks(hours)
    plt.tight_layout()
    plt.show()