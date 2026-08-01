#  Hybrid PV Simulator

> Simulation of a 27.3 kWc hybrid solar system with battery storage and grid backup
> **Abidjan, Côte d'Ivoire**

---

## System Architecture

| Component | Specification |
|-----------|--------------|
| **PV Panels** | LONGI Solar LR5-72HPH 650Wc × 42 = 27.3 kWc |
| **Inverter** | DEYE 20kW LV — Three-phase 400V |
| **Batteries** | 2 × 15 kWh LFP = 30 kWh total |
| **Grid** | CIE three-phase 400V (backup) |
| **Location** | Abidjan, Côte d'Ivoire (5.35°N, 4.00°W) |

---

## Project Structure

```
hybrid-pv-simulator/
├── data/
│   └── irradiation_abidjan.py     # Synthetic TMY solar irradiation profile
├── models/
│   ├── pv_system.py               # PV model with temperature correction
│   ├── battery.py                 # LFP battery model with SOC management
│   └── load.py                    # Load profile with electrical parameters
├── simulation/
│   ├── energy_manager.py          # Hybrid energy dispatch manager
│   └── transient_analysis.py      # Second-by-second transient analysis
└── main.py                        # Main entry point — all scenarios
```

---

## Simulated Scenarios

### Scenario 1 — Normal day (January, grid available)
- 3×1.5CV + 1×2CV air conditioners active
- PV → Battery → Grid dispatch logic
- Daily energy balance

### Scenario 2 — Grid outage (June, rainy season)
- Full CIE blackout simulation
- System autonomy on PV + battery only
- Load shedding analysis

### Scenario 3 — Maximum load (6 air conditioners)
- 2×1.5CV + 2×2CV + 2×3CV simultaneously
- DEYE inverter limit verification
- Battery stress test

### Scenario 4 — Progressive startup
- One air conditioner added at a time
- Nominal and startup current analysis
- DEYE tripping detection

### Scenario 5 — Current analysis & DEYE tripping
- Per-phase current profiles over 24h
- Startup surge vs DEYE limits
- Safety margins calculation

### Scenario 6 — Second-by-second transient analysis
- 1-second resolution over 30s windows
- Three-phase startup model (peak → exponential decay → nominal)
- DEYE response: 10s overload tolerance before trip
- One detailed graph per startup event

---

## Electrical Parameters

### Air Conditioner Catalog (Inverter type, 400V three-phase)

| Type | Power (kW) | cosφ | I nominal (A) | Startup factor | I startup (A) | Duration (s) |
|------|-----------|------|--------------|----------------|--------------|--------------|
| 1.5 CV | 1.103 | 0.85 | 5.64 | ×3 | 16.92 | 2.0 |
| 2 CV | 1.471 | 0.85 | 7.53 | ×4 | 30.12 | 2.5 |
| 3 CV | 2.207 | 0.85 | 11.29 | ×5 | 56.45 | 3.0 |

### DEYE 20kW LV Inverter Limits

| Parameter | Value |
|-----------|-------|
| Max active power | 20 kW |
| Max apparent power | 22 kVA |
| Max current per phase | 29 A |
| Overload tolerance | ×1.25 = 36.25 A for 10s max |
| Trip behavior | Immediate if I > 36.25A / Delayed 10s if 29A < I ≤ 36.25A |

---

## Installation & Usage

```bash
# Clone the repository
git clone https://github.com/aurioltaminy/hybrid-pv-simulator.git
cd hybrid-pv-simulator

# Install dependencies
pip install numpy matplotlib

# Run all scenarios
python main.py

# Run transient analysis only
python simulation/transient_analysis.py

# Run individual modules
python data/irradiation_abidjan.py
python models/pv_system.py
python models/battery.py
python models/load.py
python simulation/energy_manager.py
```

---

## Key Results

- **PV peak production** : ~21 kW (January, noon)
- **Daily energy** : ~95–120 kWh depending on season
- **Battery autonomy** : ~4–6h without grid at full load
- **DEYE tripping risk** : from 2×2CV simultaneous startup
- **Safe startup sequence** : 1.5CV first, then 2CV, avoid 3CV without grid

---

## Solar Resource — Abidjan

| Season | Peak Irradiance (W/m²) | Daily Energy (kWh/m²) |
|--------|----------------------|----------------------|
| Dry (Nov–Mar) | 920–980 | 5.5–6.0 |
| Rainy (Apr–Oct) | 720–880 | 4.2–5.2 |

---

## Author

**Niassan Auriol Frejus Taminy**
Pre-Sales Solar Engineer | Energy Systems Modeler
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://linkedin.com/in/niassan-dit-auriol-fr%C3%A9jus-taminy)
[![GitHub](https://img.shields.io/badge/GitHub-aurioltaminy-black)](https://github.com/aurioltaminy)

---

## License

MIT License — feel free to use and adapt for your own solar projects.