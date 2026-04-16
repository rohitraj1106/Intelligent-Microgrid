# ⚡ Honeybee — AI-Powered Energy Management

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-ML-FF6600?style=for-the-badge)
![NASA POWER](https://img.shields.io/badge/NASA-POWER%20API-0033A0?style=for-the-badge&logo=nasa&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**An AI-driven microgrid platform for Northern India that forecasts solar generation and residential load demand, enabling intelligent P2P energy trading and battery scheduling.**

</div>

---

## 🎯 Problem Statement

India's push towards decentralized renewable energy requires microgrids that can **predict** both energy supply and demand in real-time. Without accurate forecasting, microgrids suffer from:
- ❌ Energy imbalance (excess solar wasted, or shortfall during peak hours)
- ❌ Inefficient battery cycling
- ❌ Poor P2P trading decisions

This project builds the **Predictive Forecasting Engine** — the AI backbone that gives a Strategic LLM Agent the foresight to make optimal energy decisions.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Strategic LLM Agent                       │
│            (Battery Scheduling + P2P Trading)               │
└──────────────────────┬──────────────────────────────────────┘
                       │ queries
          ┌────────────┴────────────┐
          ▼                         ▼
  ┌───────────────┐       ┌──────────────────┐
  │ Solar         │       │ Load             │
  │ Forecaster    │       │ Forecaster       │
  │ (Supply)      │       │ (Demand)         │
  │ MAPE: 2.84%   │       │ MAPE: 13.95%     │
  └───────┬───────┘       └────────┬─────────┘
          │                        │
          ▼                        ▼
  ┌───────────────┐       ┌──────────────────┐
  │ NASA POWER    │       │ NASA POWER       │
  │ GHI, Temp,    │       │ Temp, Humidity   │
  │ Wind Speed    │       │ + Load Profiles  │
  └───────────────┘       └──────────────────┘
```

---

## 📊 Model Performance

| Model | MAPE | RMSE | Data | Target |
|:---|:---|:---|:---|:---|
| **Solar Forecaster** | **2.84%** | 0.0088 kW | 175K rows (5 cities × 5 years) | ✅ < 15% |
| **Load Forecaster** | **13.95%** | 0.2066 kW | 3.28M rows (75 homes × 5 years) | ✅ < 15% |

### Solar Forecaster — Feature Drivers
| Rank | Feature | Weight | Why |
|:---|:---|:---|:---|
| 1 | GHI (Irradiance) | ~63% | Physics: sunlight drives generation |
| 2 | Cell Temperature | ~17% | Thermal degradation in Indian heat |
| 3 | Power Lag (1h) | ~7% | Short-term trend detection |

### Load Forecaster — Feature Drivers
| Rank | Feature | Weight | Why |
|:---|:---|:---|:---|
| 1 | Load Lag (1h) | ~61% | Current usage predicts next hour |
| 2 | Load Lag (24h) | ~27% | Daily behavioral repetition |
| 3 | Temperature | ~7% | AC/heater activation threshold |

---

## 🗂️ Project Structure

```
Intelligent-Microgrid/
│
├── forecasting/                     # Predictive Engine
│   ├── solar/                       # ☀️ Solar Generation Forecasting
│   │   ├── forecaster.py            # SolarForecaster class (XGBoost)
│   │   ├── data_curator.py          # NASA POWER API → PVLib simulation
│   │   ├── train.py                 # Training entry-point
│   │   ├── visualize.py             # Actual vs Predicted plots
│   │   └── sensitivity.py           # Weather uncertainty analysis
│   │
│   ├── load/                        # 🔌 Load Demand Forecasting
│   │   ├── forecaster.py            # LoadForecaster class (XGBoost)
│   │   ├── data_curator.py          # NASA POWER API → Load synthesis
│   │   ├── train.py                 # Training entry-point
│   │   ├── visualize.py             # Actual vs Predicted plots
│   │   └── sensitivity.py           # Weather uncertainty analysis
│   │
│   └── data/                        # Datasets (gitignored — too large)
│       ├── solar/                   # Solar training CSV (~22 MB)
│       ├── load/                    # Load training CSV (~435 MB)
│       └── raw/                     # Cached NASA API responses
│
├── models/                          # Trained Model Artifacts
│   ├── solar forecaster/
│   │   ├── solar_model.json         # XGBoost weights
│   │   ├── solar_forecaster.pkl     # LabelEncoder metadata
│   │   └── results/                 # Performance report + plots
│   │
│   └── load forecaster/
│       ├── load_model.json          # XGBoost weights
│       ├── load_forecaster.pkl      # LabelEncoder metadata
│       └── results/                 # Performance report + plots
│
├── LOAD_FORECASTING_PLAN.md         # Implementation blueprint
├── requirements.txt                 # Python dependencies
└── README.md                        # You are here
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/theabhinav0231/Intelligent-Microgrid.git
cd Intelligent-Microgrid
pip install -r requirements.txt
```

### 2. Generate Training Data (Optional — requires internet)

The data curators fetch real weather from NASA's POWER API and synthesize training datasets:

```bash
# Solar data (GHI + PVLib simulation)
python -m forecasting.solar.data_curator

# Load data (Temperature + Residential profiles)
python -m forecasting.load.data_curator
```

### 3. Train Models

```bash
# Train Solar Forecaster
python -m forecasting.solar.train

# Train Load Forecaster
python -m forecasting.load.train
```

### 4. Generate Visualizations

```bash
python -m forecasting.solar.visualize
python -m forecasting.load.visualize
```

### 5. Run Sensitivity Analysis

```bash
python -m forecasting.solar.sensitivity
python -m forecasting.load.sensitivity
```

### 6. Use in Code

```python
from forecasting.solar.forecaster import SolarForecaster
from forecasting.load.forecaster import LoadForecaster

# Load pre-trained models
solar = SolarForecaster(model_dir="models/solar forecaster")
solar.load_model()

load = LoadForecaster(model_dir="models/load forecaster")
load.load_model()

# Predict next 24 hours
supply_24h = solar.predict_24h(recent_weather_data, city="Delhi")
demand_24h = load.predict_24h(recent_load_data, city="Delhi")

# Net energy = Supply - Demand → drives battery + trading decisions
net = [s - d for s, d in zip(supply_24h, demand_24h)]
```

---

## 🌍 Cities Covered

| City | Lat | Lon | Elevation | Climate |
|:---|:---|:---|:---|:---|
| **Delhi** | 28.61 | 77.21 | 216m | Hot semi-arid |
| **Noida** | 28.54 | 77.39 | 200m | Hot semi-arid |
| **Gurugram** | 28.46 | 77.03 | 217m | Hot semi-arid |
| **Chandigarh** | 30.73 | 76.78 | 321m | Humid subtropical |
| **Dehradun** | 30.32 | 78.03 | 640m | Humid subtropical |

---

## 🔬 Methodology

### Solar Forecasting
1. **Data**: NASA POWER API → GHI, Temperature, Wind Speed (5 cities × 5 years)
2. **Simulation**: PVLib physics engine simulates 1kW rooftop panel output
3. **Model**: XGBoost Regressor (500 trees, LR=0.05, depth=6)
4. **Evaluation**: Daytime-only MAPE (solar = 0 at night)

### Load Forecasting
1. **Data**: NASA POWER API → Temperature, Humidity (5 cities × 5 years)
2. **Synthesis**: Behavioral model with double-peak profile (morning + evening), weather modulation (AC/heater), 15 unique homes per city with individualized habits
3. **Model**: XGBoost Regressor (800 trees, LR=0.03, depth=7, stronger regularization)
4. **Evaluation**: All-hours MAPE (load never reaches zero)

### Robustness Testing
Both models undergo **Monte Carlo sensitivity analysis** (10 trials × 5 noise levels) to quantify degradation under real-world weather forecast uncertainty.

---

## 📦 Dependencies

| Package | Purpose |
|:---|:---|
| `pandas` | Data manipulation |
| `numpy` | Numerical operations |
| `xgboost` | Gradient boosted tree models |
| `scikit-learn` | Preprocessing & metrics |
| `pvlib` | Solar PV physics simulation |
| `requests` | NASA POWER API calls |
| `matplotlib` | Visualization |
| `joblib` | Model serialization |

---

## 📄 License

This project is developed as a Minor Project for academic purposes.

---

<div align="center">
  <b>Built with ☀️ and ⚡ for smarter energy in Northern India</b>
</div>
