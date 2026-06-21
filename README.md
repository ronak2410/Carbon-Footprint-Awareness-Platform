---
title: Carbon Footprint Dashboard
emoji: 🌍
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# AURA Carbon — Carbon Footprint Awareness Platform

**PromptWars Challenge 3 Submission** | Help individuals **understand**, **track**, and **reduce** their carbon footprint through simple actions and personalized insights.

## Live Demo

**Deployed App:** [https://ronak2410-carbon-footprint-dashboard.hf.space](https://ronak2410-carbon-footprint-dashboard.hf.space)

**GitHub Repository:** [https://github.com/ronak2410/Carbon-Footprint-Awareness-Platform](https://github.com/ronak2410/Carbon-Footprint-Awareness-Platform)

---

## Problem Statement Alignment

| Requirement | Implementation |
|---|---|
| **Understand** footprint | Real-time calculator with sector breakdown, gauge, donut chart, and global comparison scale |
| **Track** over time | SQLite-backed history logs, trend chart, data table, and CSV export |
| **Reduce** through actions | 6 habit micro-changes with live reduction simulation |
| **Personalized insights** | Dynamic recommendations targeting the user's highest-impact sector |
| **Simple actions** | Slider inputs, one-click logging, checkbox habit toggles, eco quiz |

---

## Features

### 1. Consumption Metrics Input
- Electricity (kWh/month), petrol travel (km/month), LPG cooking gas (kg/month)
- Weekly meat vs. plant-based meal tracking
- Custom log date picker

### 2. Impact Assessment Dashboard
- Animated CO₂e gauge with color-coded severity
- Sector breakdown progress bars (Energy, Transport, LPG, Diet)
- Proportional donut chart visualization
- Comparative analysis vs. eco-target (2t), global average (4.8t), and US average (16t)

### 3. Actionable Reduction Strategies
- 6 lifestyle habit toggles (LED bulbs, carpool, meatless Mondays, cold wash, unplug standby, local produce)
- Live simulated annual footprint after selected habits
- Percentage reduction badge and climate-target status

### 4. Historical Performance Tracker
- SVG trend chart with interactive tooltips
- Full log history table
- CSV report export
- Clear history option

### 5. Eco-Awareness Quiz & Badges
- 5-question climate literacy quiz with explanations
- Achievement badges: Eco Novice, Habit Hero, Quiz Wizard, Carbon Shield

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLite |
| Frontend | Vanilla HTML5, CSS3, JavaScript (no framework dependencies) |
| Deployment | Docker, Hugging Face Spaces |
| API | RESTful JSON endpoints |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serve dashboard UI |
| `POST` | `/api/calculate` | Calculate emissions breakdown from inputs |
| `POST` | `/api/logs` | Save a consumption log entry |
| `GET` | `/api/history` | Retrieve last 15 log entries |
| `POST` | `/api/reset` | Clear all history logs |

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn agent_core:app --host 0.0.0.0 --port 7860

# Open in browser
http://localhost:7860
```

### Docker

```bash
docker build -t aura-carbon .
docker run -p 7860:7860 aura-carbon
```

---

## Project Structure

```
├── agent_core.py    # FastAPI backend + SQLite + emission calculations
├── index.html       # Dashboard UI
├── app.js           # Frontend logic (calculator, charts, quiz, habits)
├── style.css        # Cinematic neon UI styling
├── Dockerfile       # Hugging Face Spaces container config
├── requirements.txt # Python dependencies
└── README.md        # This file
```

---

## Emission Factors Used

| Sector | Factor | Unit |
|---|---|---|
| Electricity | 0.85 | kg CO₂e / kWh |
| Petrol vehicle | 0.20 | kg CO₂e / km |
| LPG cooking gas | 3.00 | kg CO₂e / kg |
| Heavy meat meal | 2.50 | kg CO₂e / meal (weekly → monthly × 4.33) |
| Plant-based meal | 1.00 | kg CO₂e / meal (weekly → monthly × 4.33) |

---

## Author

Built for **PromptWars Challenge 3 — Carbon Footprint Awareness Platform** by **Ronak**.
