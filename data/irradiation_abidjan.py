"""
Profil d'irradiation solaire - Abidjan, Côte d'Ivoire
Données synthétiques basées sur TMY (Typical Meteorological Year)
Latitude: 5.35°N | Longitude: -4.00°W
Irradiation annuelle moyenne: ~1800 kWh/m²/an
"""

import numpy as np

def get_irradiation_profile(month: int = 1) -> np.ndarray:
    """
    Retourne le profil d'irradiation horaire (W/m²) sur 24h
    pour un mois donné à Abidjan.

    Args:
        month (int): Mois de l'année (1=Janvier ... 12=Décembre)

    Returns:
        np.ndarray: Tableau de 24 valeurs (W/m²), une par heure
    """

    # Irradiation de pointe (W/m²) par mois à Abidjan
    # Saison sèche (Nov-Mar) : ensoleillement fort
    # Saison des pluies (Avr-Oct) : ensoleillement réduit
    peak_irradiance = {
        1: 950,   # Janvier  - saison sèche
        2: 980,   # Février  - saison sèche
        3: 960,   # Mars     - transition
        4: 880,   # Avril    - début pluies
        5: 820,   # Mai      - pluies
        6: 750,   # Juin     - pluies (grande saison)
        7: 720,   # Juillet  - pluies
        8: 760,   # Août     - pluies
        9: 800,   # Septembre- transition
        10: 850,  # Octobre  - petite saison sèche
        11: 920,  # Novembre - saison sèche
        12: 940,  # Décembre - saison sèche
    }

    peak = peak_irradiance.get(month, 900)

    # Profil horaire sur 24h (modèle gaussien centré sur midi)
    hours = np.arange(0, 24)

    # Lever du soleil ~6h, coucher ~18h à Abidjan (proche équateur)
    sunrise = 6.0
    sunset = 18.0
    solar_noon = (sunrise + sunset) / 2  # 12h

    irradiation = np.zeros(24)
    for h in hours:
        if sunrise <= h <= sunset:
            # Courbe en cloche gaussienne
            irradiation[h] = peak * np.exp(-0.5 * ((h - solar_noon) / 2.8) ** 2)

    return irradiation


def get_hours() -> np.ndarray:
    """Retourne le tableau des heures de la journée (0-23)"""
    return np.arange(0, 24)


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    months_to_plot = [1, 4, 6, 11]
    month_names = {1: "Janvier", 4: "Avril", 6: "Juin", 11: "Novembre"}
    hours = get_hours()

    plt.figure(figsize=(12, 6))
    for m in months_to_plot:
        irr = get_irradiation_profile(m)
        plt.plot(hours, irr, label=month_names[m], linewidth=2)

    plt.title("Profil d'irradiation solaire - Abidjan, Côte d'Ivoire", fontsize=14)
    plt.xlabel("Heure de la journée")
    plt.ylabel("Irradiation (W/m²)")
    plt.xticks(hours)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()