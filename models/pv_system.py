"""
Modèle du système photovoltaïque - 27 kWc
Panneaux : LONGI Solar LR5-72HPH 650W
Nombre de panneaux : 42 (42 × 650W = 27.3 kWc)
"""

import numpy as np
import sys
import os

# Accès au module data depuis models/
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from data.irradiation_abidjan import get_irradiation_profile, get_hours


# ─── Caractéristiques LONGI LR5-72HPH 650W ───────────────────────────────────
PANEL_POWER_WC       = 650       # Puissance crête par panneau (Wc)
NUM_PANELS           = 42        # Nombre de panneaux (42 × 650 = 27.3 kWc)
SYSTEM_POWER_KWC     = (PANEL_POWER_WC * NUM_PANELS) / 1000  # 27.3 kWc

PANEL_EFFICIENCY     = 0.202     # Rendement panneau LONGI 650W : 20.2%
TEMP_COEFFICIENT     = -0.0034   # Coefficient de température : -0.34%/°C
NOCT                 = 45        # Température nominale de fonctionnement (°C)
STC_IRRADIANCE       = 1000      # Irradiance de référence STC (W/m²)
STC_TEMP             = 25        # Température de référence STC (°C)

# ─── Pertes système ───────────────────────────────────────────────────────────
LOSS_WIRING          = 0.02      # Pertes câblage DC : 2%
LOSS_MISMATCH        = 0.02      # Pertes mismatch panneaux : 2%
LOSS_SOILING         = 0.03      # Pertes salissures (Abidjan, saison sèche) : 3%
LOSS_SHADING         = 0.01      # Pertes ombrage : 1%
INVERTER_EFFICIENCY  = 0.975     # Rendement onduleur DEYE 20kW : 97.5%

TOTAL_SYSTEM_LOSSES  = (1 - LOSS_WIRING) * (1 - LOSS_MISMATCH) * \
                       (1 - LOSS_SOILING) * (1 - LOSS_SHADING) * \
                       INVERTER_EFFICIENCY  # ~89.7%


def get_cell_temperature(irradiance: float, ambient_temp: float = 30.0) -> float:
    """
    Calcule la température des cellules PV selon le modèle NOCT.

    T_cell = T_ambient + (NOCT - 20) / 800 × Irradiance

    Args:
        irradiance (float): Irradiance en W/m²
        ambient_temp (float): Température ambiante en °C (30°C par défaut à Abidjan)

    Returns:
        float: Température de cellule en °C
    """
    return ambient_temp + ((NOCT - 20) / 800) * irradiance


def get_temperature_correction(cell_temp: float) -> float:
    """
    Calcule le facteur de correction de puissance dû à la température.

    À Abidjan, la chaleur réduit la production PV — les panneaux
    produisent moins quand il fait chaud.

    Args:
        cell_temp (float): Température de cellule en °C

    Returns:
        float: Facteur de correction (ex: 0.92 = perte de 8%)
    """
    return 1 + TEMP_COEFFICIENT * (cell_temp - STC_TEMP)


def get_pv_power(irradiance: float, ambient_temp: float = 30.0) -> float:
    """
    Calcule la puissance AC produite par le système PV (kW).

    Puissance = Puissance_STC × (Irradiance/1000) × Correction_Temp × Pertes_Système

    Args:
        irradiance (float): Irradiance solaire en W/m²
        ambient_temp (float): Température ambiante en °C

    Returns:
        float: Puissance AC produite en kW
    """
    if irradiance <= 0:
        return 0.0

    # Température de cellule
    cell_temp = get_cell_temperature(irradiance, ambient_temp)

    # Correction température
    temp_correction = get_temperature_correction(cell_temp)

    # Puissance DC brute
    p_dc = SYSTEM_POWER_KWC * (irradiance / STC_IRRADIANCE) * temp_correction

    # Puissance AC après pertes système
    p_ac = p_dc * TOTAL_SYSTEM_LOSSES

    return max(0.0, p_ac)


def get_pv_profile(month: int = 1, ambient_temp: float = 30.0) -> np.ndarray:
    """
    Retourne le profil de puissance PV sur 24h (kW).

    Args:
        month (int): Mois de l'année (1-12)
        ambient_temp (float): Température ambiante moyenne en °C

    Returns:
        np.ndarray: Tableau de 24 valeurs de puissance (kW)
    """
    irradiation = get_irradiation_profile(month)
    pv_power = np.array([get_pv_power(irr, ambient_temp) for irr in irradiation])
    return pv_power


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    hours = get_hours()
    months_to_plot = {1: "Janvier", 6: "Juin", 11: "Novembre"}

    print(f"{'='*55}")
    print(f"  Système PV - LONGI {PANEL_POWER_WC}Wc × {NUM_PANELS} panneaux")
    print(f"  Puissance crête totale : {SYSTEM_POWER_KWC:.1f} kWc")
    print(f"  Rendement système total : {TOTAL_SYSTEM_LOSSES*100:.1f}%")
    print(f"{'='*55}")

    plt.figure(figsize=(12, 6))

    for month, name in months_to_plot.items():
        pv = get_pv_profile(month)
        energy_day = np.sum(pv)  # kWh/jour (1 valeur par heure)
        print(f"  {name:12s} → Pic : {max(pv):.2f} kW | Énergie/jour : {energy_day:.1f} kWh")
        plt.plot(hours, pv, label=f"{name} (pic: {max(pv):.1f} kW)", linewidth=2)

    print(f"{'='*55}")

    plt.axhline(y=20, color='red', linestyle='--', alpha=0.7, label='Limite onduleur DEYE (20 kW)')
    plt.title(f"Production PV - {NUM_PANELS} panneaux LONGI {PANEL_POWER_WC}Wc ({SYSTEM_POWER_KWC:.1f} kWc)", fontsize=14)
    plt.xlabel("Heure de la journée")
    plt.ylabel("Puissance AC produite (kW)")
    plt.xticks(hours)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()