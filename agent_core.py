import sqlite3
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime

# Setup FastAPI App
app = FastAPI(title="Carbon Footprint Analytics Agent Core")

DB_PATH = "friday_carbon.db"

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS carbon_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            electricity_kwh REAL,
            petrol_km REAL,
            lpg_kg REAL,
            meat_meals INTEGER,
            plant_meals INTEGER,
            electricity_co2e REAL,
            petrol_co2e REAL,
            lpg_co2e REAL,
            diet_co2e REAL,
            total_co2e REAL,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# Initialize Database on startup
init_db()

# Pydantic models for API validation
class FootprintInput(BaseModel):
    electricity_kwh: float
    petrol_km: float
    lpg_kg: float
    meat_meals: int
    plant_meals: int

# Emission Reference Constants
CO2E_ELECTRICITY_FACTOR = 0.85  # kg CO2e per kWh
CO2E_PETROL_FACTOR = 0.20       # kg CO2e per km
CO2E_LPG_FACTOR = 3.00          # kg CO2e per kg
CO2E_MEAT_MEAL_FACTOR = 2.50    # kg CO2e per meal
CO2E_PLANT_MEAL_FACTOR = 1.00   # kg CO2e per meal
WEEKS_PER_MONTH = 4.33          # To scale weekly meals to monthly emissions

@app.post("/api/calculate")
def calculate_emissions(data: FootprintInput):
    """
    Process raw consumption metrics and calculate emissions breakdown and projections.
    """
    # 1. Calculation Math
    elec_emissions = data.electricity_kwh * CO2E_ELECTRICITY_FACTOR
    petrol_emissions = data.petrol_km * CO2E_PETROL_FACTOR
    lpg_emissions = data.lpg_kg * CO2E_LPG_FACTOR
    
    # Scale weekly meal choices to monthly
    weekly_diet_emissions = (data.meat_meals * CO2E_MEAT_MEAL_FACTOR) + (data.plant_meals * CO2E_PLANT_MEAL_FACTOR)
    diet_emissions = weekly_diet_emissions * WEEKS_PER_MONTH
    
    total_monthly_emissions = elec_emissions + petrol_emissions + lpg_emissions + diet_emissions
    total_annual_emissions = total_monthly_emissions * 12

    # 2. Contextual Analysis Averages
    # Global average: 4800 kg CO2e / year (4.8 tons) -> 400 kg / month
    # National average (e.g. US: 16 tons, India: 1.9 tons, Average benchmark: 4.8 tons)
    # Target benchmark to hold warming to 1.5C: 2000 kg CO2e / year -> ~167 kg / month
    global_average_monthly = 400.0
    target_average_monthly = 167.0
    
    # Compare
    pct_of_global_avg = (total_monthly_emissions / global_average_monthly) * 100
    pct_of_target = (total_monthly_emissions / target_average_monthly) * 100

    # Determine highest sector
    sectors = {
        "Energy (Electricity)": elec_emissions,
        "Transportation (Petrol Vehicle)": petrol_emissions,
        "Cooking Gas (LPG)": lpg_emissions,
        "Dietary Footprint": diet_emissions
    }
    highest_sector = max(sectors, key=sectors.get)
    highest_val = sectors[highest_sector]

    # Return structured results
    return {
        "breakdown": {
            "electricity": round(elec_emissions, 2),
            "petrol": round(petrol_emissions, 2),
            "lpg": round(lpg_emissions, 2),
            "diet": round(diet_emissions, 2)
        },
        "totals": {
            "monthly_kg": round(total_monthly_emissions, 2),
            "annual_kg": round(total_annual_emissions, 2),
            "annual_tons": round(total_annual_emissions / 1000.0, 2)
        },
        "comparisons": {
            "pct_of_global_avg": round(pct_of_global_avg, 1),
            "pct_of_target": round(pct_of_target, 1),
            "highest_sector": highest_sector,
            "highest_emissions_kg": round(highest_val, 2)
        }
    }

@app.post("/api/logs")
def save_log(data: FootprintInput):
    """
    Calculates footprint and saves the entry to SQLite history database.
    """
    calc = calculate_emissions(data)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO carbon_logs (
            electricity_kwh, petrol_km, lpg_kg, meat_meals, plant_meals,
            electricity_co2e, petrol_co2e, lpg_co2e, diet_co2e, total_co2e, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.electricity_kwh, data.petrol_km, data.lpg_kg, data.meat_meals, data.plant_meals,
        calc["breakdown"]["electricity"], calc["breakdown"]["petrol"], calc["breakdown"]["lpg"],
        calc["breakdown"]["diet"], calc["totals"]["monthly_kg"], now_str
    ))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Consumption metrics successfully logged.", "data": calc}

@app.get("/api/history")
def get_logs_history():
    """
    Retrieve historical user carbon score entries from SQLite.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, electricity_kwh, petrol_km, lpg_kg, meat_meals, plant_meals,
               electricity_co2e, petrol_co2e, lpg_co2e, diet_co2e, total_co2e, timestamp
        FROM carbon_logs
        ORDER BY id DESC
        LIMIT 15
    """)
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        history.append({
            "id": r[0],
            "electricity_kwh": r[1],
            "petrol_km": r[2],
            "lpg_kg": r[3],
            "meat_meals": r[4],
            "plant_meals": r[5],
            "breakdown": {
                "electricity": r[6],
                "petrol": r[7],
                "lpg": r[8],
                "diet": r[9]
            },
            "total_co2e": r[10],
            "date": r[11].split("T")[0] if "T" in r[11] else r[11]
        })
        
    # Return chronologically (oldest to newest for graphing)
    history.reverse()
    return history

@app.post("/api/reset")
def reset_history():
    """
    Clear all logged entries in the database.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM carbon_logs")
    conn.commit()
    conn.close()
    return {"status": "success", "message": "History logs successfully cleared."}

# Static File Routes
@app.get("/")
def serve_index():
    return FileResponse("index.html")

@app.get("/style.css")
def serve_style():
    return FileResponse("style.css")

@app.get("/app.js")
def serve_app():
    return FileResponse("app.js")
