/* ==========================================================================
   AURA CARBON - APPLICATION CONTROLLER
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // 1. App State
    let currentLocalMetrics = {
        electricity_kwh: 150,
        petrol_km: 400,
        lpg_kg: 14,
        meat_meals: 7,
        plant_meals: 14
    };

    let activeHabits = {
        led_bulb: false,
        carpool: false,
        meatless_monday: false,
        cold_wash: false,
        unplug_standby: false,
        local_produce: false
    };

    let quizState = {
        currentQuestion: 0,
        score: 0,
        answered: false
    };

    // Constant coefficients (same as backend)
    const CO2E_ELEC_FACTOR = 0.85;
    const CO2E_PETROL_FACTOR = 0.20;
    const CO2E_LPG_FACTOR = 3.00;
    const CO2E_MEAT_FACTOR = 2.50;
    const CO2E_PLANT_FACTOR = 1.00;
    const WEEKS_PER_MONTH = 4.33;

    // AURA Quiz Questions
    const quizQuestions = [
        {
            q: "Which sector contributes the most greenhouse gas emissions globally?",
            options: [
                "Transportation (Cars, Ships, Planes)",
                "Electricity & Heat Production (Fossil fuels)",
                "Agriculture & Forestry (Cows, Deforestation)",
                "Manufacturing & Construction"
            ],
            correct: 1,
            explanation: "Electricity and Heat production represents roughly 25% of global emissions due to high coal and natural gas combustion."
        },
        {
            q: "What is the recommended annual target carbon footprint per person to limit global warming to 1.5°C?",
            options: [
                "Under 2.0 Metric Tons CO₂e",
                "Around 4.8 Metric Tons CO₂e",
                "Around 10.0 Metric Tons CO₂e",
                "Over 16.0 Metric Tons CO₂e"
            ],
            correct: 0,
            explanation: "To meet the IPCC 1.5°C target, global average emissions per person must fall under 2 tons of CO₂e annually by 2030."
        },
        {
            q: "How much more heat does methane trap in the atmosphere compared to carbon dioxide over a 20-year period?",
            options: [
                "Roughly the same",
                "About 5 times more",
                "Over 80 times more",
                "Over 500 times more"
            ],
            correct: 2,
            explanation: "Methane is a highly potent greenhouse gas, trapping 84-86 times more heat than CO₂ over a 20-year timeline."
        },
        {
            q: "Which dietary option typically has the lowest greenhouse gas emissions per gram of protein?",
            options: [
                "Pork & Poultry",
                "Dairy Cheese",
                "Peas & Legumes",
                "Farmed Fish"
            ],
            correct: 2,
            explanation: "Peas, lentils, and other legumes require minimal energy inputs and naturally fix nitrogen in the soil, yielding a tiny fraction of the emissions of meat or dairy."
        },
        {
            q: "What does 'Phantom Load' or 'Vampire Draw' refer to in household energy consumption?",
            options: [
                "Unapproved electricity theft by neighbors",
                "Defective electrical wiring leakage",
                "Power consumed by appliances when in standby mode",
                "High power surges when turning on light switches"
            ],
            correct: 2,
            explanation: "Appliances left plugged in draw power even when turned off. This 'phantom load' accounts for up to 10% of residential energy usage."
        }
    ];

    // 2. DOM Elements
    const elements = {
        // Inputs
        inputElec: document.getElementById("input-electricity"),
        inputPetrol: document.getElementById("input-petrol"),
        inputLpg: document.getElementById("input-lpg"),
        inputMeat: document.getElementById("input-meat-meals"),
        inputPlant: document.getElementById("input-plant-meals"),
        inputLogDate: document.getElementById("input-log-date"),
        btnExportCsv: document.getElementById("btn-export-csv"),
        donutChartSvg: document.getElementById("donut-chart-svg"),
        donutTotalVal: document.getElementById("donut-total-val"),
        insightsListContainer: document.getElementById("insights-list-container"),

        // Input Value Labels
        lblElec: document.getElementById("val-electricity"),
        lblPetrol: document.getElementById("val-petrol"),
        lblLpg: document.getElementById("val-lpg"),
        lblMeat: document.getElementById("val-meat-meals"),
        lblPlant: document.getElementById("val-plant-meals"),

        // Action Buttons
        btnSubmitLog: document.getElementById("btn-submit-log"),
        btnClearHistory: document.getElementById("btn-clear-history"),

        // Gauge & Breakdown Outputs
        gaugeFill: document.getElementById("gauge-fill-bar"),
        gaugeVal: document.getElementById("gauge-co2-value"),
        annualVal: document.getElementById("annual-tons-value"),
        
        breakdownValElec: document.getElementById("breakdown-val-elec"),
        breakdownValPetrol: document.getElementById("breakdown-val-petrol"),
        breakdownValLpg: document.getElementById("breakdown-val-lpg"),
        breakdownValDiet: document.getElementById("breakdown-val-diet"),
        
        breakdownFillElec: document.getElementById("breakdown-fill-elec"),
        breakdownFillPetrol: document.getElementById("breakdown-fill-petrol"),
        breakdownFillLpg: document.getElementById("breakdown-fill-lpg"),
        breakdownFillDiet: document.getElementById("breakdown-fill-diet"),

        // Comparative Analysis
        scaleProgress: document.getElementById("comparison-scale-progress"),
        scaleMarker: document.getElementById("comparison-scale-marker"),
        scaleMsg: document.getElementById("comparison-status-message"),

        // Habit Simulator Elements
        simScoreValue: document.getElementById("sim-score-value"),
        simReductionBadge: document.getElementById("sim-reduction-badge"),
        simTargetStatus: document.getElementById("sim-target-status"),

        // History UI
        historyTableBody: document.getElementById("history-table-body"),
        logCountIndicator: document.getElementById("log-count-indicator"),
        chartGridLines: document.getElementById("chart-grid-lines"),
        chartLinePath: document.getElementById("chart-line-path"),
        chartLineGlow: document.getElementById("chart-line-glow"),
        chartDataPoints: document.getElementById("chart-data-points"),
        chartAreaPath: document.getElementById("chart-area-path"),
        chartTooltip: document.getElementById("chart-tooltip"),

        // Quiz UI
        quizActiveContainer: document.getElementById("quiz-active-container"),
        quizCompleteContainer: document.getElementById("quiz-complete-container"),
        quizProgressFill: document.getElementById("quiz-progress-fill"),
        quizQuestionText: document.getElementById("quiz-question-text"),
        quizOptionsList: document.getElementById("quiz-options-list"),
        quizExplanationBox: document.getElementById("quiz-explanation-box"),
        quizExplanationText: document.getElementById("quiz-explanation-text"),
        btnNextQuestion: document.getElementById("btn-next-question"),
        btnRestartQuiz: document.getElementById("btn-restart-quiz"),
        quizFinalScore: document.getElementById("quiz-final-score"),

        // Badge Elements
        badgeEcoNovice: document.getElementById("badge-eco-novice"),
        badgeHabitHero: document.getElementById("badge-habit-hero"),
        badgeQuizWizard: document.getElementById("badge-quiz-wizard"),
        badgeCarbonNeutralist: document.getElementById("badge-carbon-neutralist")
    };

    // Set Date in Header
    const formattedDate = new Date().toISOString().split("T")[0];
    document.getElementById("timezone-status").innerText = `SYSTEM TIME: ${formattedDate}`;

    // Set default date in Date Picker to today
    if (elements.inputLogDate) {
        elements.inputLogDate.value = formattedDate;
    }

    // 3. Calculation & UI Update Functions (Client Side Live Preview)
    function performLiveCalculations() {
        // Read raw inputs
        const kwh = parseFloat(elements.inputElec.value);
        const km = parseFloat(elements.inputPetrol.value);
        const lpg = parseFloat(elements.inputLpg.value);
        const meat = parseInt(elements.inputMeat.value);
        const plant = parseInt(elements.inputPlant.value);

        // Core math
        const elecCo2 = kwh * CO2E_ELEC_FACTOR;
        const petrolCo2 = km * CO2E_PETROL_FACTOR;
        const lpgCo2 = lpg * CO2E_LPG_FACTOR;
        const weeklyDietCo2 = (meat * CO2E_MEAT_FACTOR) + (plant * CO2E_PLANT_FACTOR);
        const dietCo2 = weeklyDietCo2 * WEEKS_PER_MONTH;

        const totalMonthlyCo2 = elecCo2 + petrolCo2 + lpgCo2 + dietCo2;
        const totalAnnualCo2Tons = (totalMonthlyCo2 * 12) / 1000.0;

        currentLocalMetrics = {
            electricity_kwh: kwh,
            petrol_km: km,
            lpg_kg: lpg,
            meat_meals: meat,
            plant_meals: plant,
            monthly_total: totalMonthlyCo2,
            annual_total_tons: totalAnnualCo2Tons,
            breakdown: {
                electricity: elecCo2,
                petrol: petrolCo2,
                lpg: lpgCo2,
                diet: dietCo2
            }
        };

        updateGauge(totalMonthlyCo2, totalAnnualCo2Tons);
        updateBreakdownBars(elecCo2, petrolCo2, lpgCo2, dietCo2, totalMonthlyCo2);
        updateComparisonScale(totalAnnualCo2Tons);
        simulateHabitsReduction();
        renderDonutChart(elecCo2, petrolCo2, lpgCo2, dietCo2);
        updatePersonalizedInsights(elecCo2, petrolCo2, lpgCo2, dietCo2);
    }

    function updateGauge(monthlyKg, annualTons) {
        elements.gaugeVal.innerText = monthlyKg.toFixed(1);
        elements.annualVal.innerText = `${annualTons.toFixed(2)} Tons`;

        // Circumference is 263.89
        const maxExpectedMonthly = 1800.0; // scale basis
        const percentage = Math.min(100, (monthlyKg / maxExpectedMonthly) * 100);
        const offset = 264 - (264 * percentage) / 100;
        
        elements.gaugeFill.style.strokeDashoffset = offset;

        // Change color based on severity
        if (annualTons < 2.0) {
            elements.gaugeFill.style.stroke = "var(--neon-emerald)";
            elements.gaugeFill.style.filter = "drop-shadow(0 0 8px var(--neon-emerald-glow))";
        } else if (annualTons < 4.8) {
            elements.gaugeFill.style.stroke = "var(--neon-cyan)";
            elements.gaugeFill.style.filter = "drop-shadow(0 0 8px var(--neon-cyan-glow))";
        } else if (annualTons < 8.0) {
            elements.gaugeFill.style.stroke = "var(--neon-violet)";
            elements.gaugeFill.style.filter = "drop-shadow(0 0 8px var(--neon-violet-glow))";
        } else {
            elements.gaugeFill.style.stroke = "var(--neon-rose)";
            elements.gaugeFill.style.filter = "drop-shadow(0 0 8px var(--neon-rose-glow))";
        }
    }

    function updateBreakdownBars(elec, petrol, lpg, diet, total) {
        // Values text
        elements.breakdownValElec.innerText = `${elec.toFixed(1)} kg`;
        elements.breakdownValPetrol.innerText = `${petrol.toFixed(1)} kg`;
        elements.breakdownValLpg.innerText = `${lpg.toFixed(1)} kg`;
        elements.breakdownValDiet.innerText = `${diet.toFixed(1)} kg`;

        // Proportions
        const pctElec = total > 0 ? (elec / total) * 100 : 0;
        const pctPetrol = total > 0 ? (petrol / total) * 100 : 0;
        const pctLpg = total > 0 ? (lpg / total) * 100 : 0;
        const pctDiet = total > 0 ? (diet / total) * 100 : 0;

        elements.breakdownFillElec.style.width = `${pctElec}%`;
        elements.breakdownFillPetrol.style.width = `${pctPetrol}%`;
        elements.breakdownFillLpg.style.width = `${pctLpg}%`;
        elements.breakdownFillDiet.style.width = `${pctDiet}%`;
    }

    function updateComparisonScale(annualTons) {
        // We scale the bar from 0 to 20 tons
        const maxScaleTons = 20.0;
        const pct = Math.min(100, (annualTons / maxScaleTons) * 100);

        elements.scaleProgress.style.width = `${pct}%`;
        elements.scaleMarker.style.left = `${pct}%`;

        // Contextual analysis output
        let message = "";
        let colorClass = "";
        
        if (annualTons <= 2.0) {
            message = `Excellent! Your footprint (${annualTons.toFixed(2)}t) is below the Climate Safe Target of 2.0 Tons.`;
            elements.scaleMsg.style.color = "var(--neon-emerald)";
            elements.badgeCarbonNeutralist.classList.remove("locked");
            elements.badgeCarbonNeutralist.classList.add("unlocked");
        } else if (annualTons <= 4.8) {
            message = `Moderate. You are above the eco-target, but below the global average footprint (${annualTons.toFixed(2)}t < 4.8t).`;
            elements.scaleMsg.style.color = "var(--neon-cyan)";
            elements.badgeCarbonNeutralist.classList.add("locked");
            elements.badgeCarbonNeutralist.classList.remove("unlocked");
        } else {
            // Find highest sector
            const map = currentLocalMetrics.breakdown;
            const highestKey = Object.keys(map).reduce((a, b) => map[a] > map[b] ? a : b);
            const keyDisplay = highestKey === "electricity" ? "Utility Electricity" : highestKey === "petrol" ? "Petrol Transport" : highestKey === "lpg" ? "Cooking Gas (LPG)" : "Dietary Footprint";
            
            message = `Critical. Footprint (${annualTons.toFixed(2)}t) exceeds global averages. Highest impact area: ${keyDisplay}.`;
            elements.scaleMsg.style.color = "var(--neon-rose)";
            elements.badgeCarbonNeutralist.classList.add("locked");
            elements.badgeCarbonNeutralist.classList.remove("unlocked");
        }
        elements.scaleMsg.innerText = message;
    }

    // 4. Habit reduction simulation
    function simulateHabitsReduction() {
        const rawBreakdown = currentLocalMetrics.breakdown;
        let finalElectricity = rawBreakdown.electricity;
        let finalPetrol = rawBreakdown.petrol;
        let finalLpg = rawBreakdown.lpg;
        let finalDiet = rawBreakdown.diet;

        // Apply reductions based on checked habits
        let habitsCount = 0;

        if (activeHabits.led_bulb) {
            finalElectricity *= 0.85; // -15% energy impact
            habitsCount++;
        }
        if (activeHabits.carpool) {
            finalPetrol *= 0.75; // -25% transport impact
            habitsCount++;
        }
        if (activeHabits.meatless_monday) {
            // Converts 3 meat meals to plant meals
            // reduction: 3 meals * (2.5 - 1.0) = 4.5 kg CO2e / week
            const weeklySavings = 4.5;
            const monthlySavings = weeklySavings * WEEKS_PER_MONTH;
            finalDiet = Math.max(0, finalDiet - monthlySavings);
            habitsCount++;
        }
        if (activeHabits.cold_wash) {
            // subtract 10 kWh -> 10 * 0.85 = 8.5 kg CO2e / month
            finalElectricity = Math.max(0, finalElectricity - (10 * CO2E_ELEC_FACTOR));
            habitsCount++;
        }
        if (activeHabits.unplug_standby) {
            // subtract 15 kWh -> 15 * 0.85 = 12.75 kg CO2e / month
            finalElectricity = Math.max(0, finalElectricity - (15 * CO2E_ELEC_FACTOR));
            habitsCount++;
        }
        if (activeHabits.local_produce) {
            finalDiet *= 0.90; // -10% diet footprint
            habitsCount++;
        }

        // Calculate simulated total
        const simTotalMonthly = finalElectricity + finalPetrol + finalLpg + finalDiet;
        const simTotalAnnualTons = (simTotalMonthly * 12) / 1000.0;

        elements.simScoreValue.innerText = simTotalAnnualTons.toFixed(2);

        // Calculate percentage reduction
        const originalAnnualTons = currentLocalMetrics.annual_total_tons;
        const pctReduction = originalAnnualTons > 0 ? ((originalAnnualTons - simTotalAnnualTons) / originalAnnualTons) * 100 : 0;
        elements.simReductionBadge.innerText = `${pctReduction.toFixed(0)}% Reduced`;

        // Update target feedback
        if (simTotalAnnualTons <= 2.0) {
            elements.simTargetStatus.className = "sim-target-indicator target-reached";
            elements.simTargetStatus.innerText = "Target Reached! Projected footprint meets Climate Safe parameters (<2.0t/yr).";
        } else {
            elements.simTargetStatus.className = "sim-target-indicator";
            elements.simTargetStatus.innerText = "Target Exceeded. Adopt additional lifestyle habits to reach the 2.0-ton threshold.";
        }

        // Badge check
        if (habitsCount >= 3) {
            elements.badgeHabitHero.classList.remove("locked");
            elements.badgeHabitHero.classList.add("unlocked");
        } else {
            elements.badgeHabitHero.classList.add("locked");
            elements.badgeHabitHero.classList.remove("unlocked");
        }
    }

    // Dynamic Donut Chart Renderer
    function renderDonutChart(elec, petrol, lpg, diet) {
        const svg = elements.donutChartSvg;
        if (!svg) return;
        
        // Clear previous segments
        const existingSegments = svg.querySelectorAll(".donut-segment, .donut-bg");
        existingSegments.forEach(el => el.remove());

        const total = elec + petrol + lpg + diet;
        
        // Update center text value
        if (elements.donutTotalVal) {
            elements.donutTotalVal.innerText = total.toFixed(1);
        }

        const radius = 35;
        const circumference = 2 * Math.PI * radius; // ~219.91

        if (total === 0) {
            // Draw dummy grey background circle
            const bgCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            bgCircle.setAttribute("cx", "50");
            bgCircle.setAttribute("cy", "50");
            bgCircle.setAttribute("r", radius);
            bgCircle.setAttribute("stroke", "rgba(255, 255, 255, 0.05)");
            bgCircle.setAttribute("stroke-width", "8");
            bgCircle.setAttribute("fill", "none");
            bgCircle.setAttribute("class", "donut-bg");
            svg.appendChild(bgCircle);
            return;
        }

        const sectors = [
            { val: elec, color: "var(--neon-cyan)", glow: "var(--neon-cyan-glow)" },
            { val: petrol, color: "var(--neon-violet)", glow: "var(--neon-violet-glow)" },
            { val: lpg, color: "var(--neon-rose)", glow: "var(--neon-rose-glow)" },
            { val: diet, color: "var(--neon-emerald)", glow: "var(--neon-emerald-glow)" }
        ];

        let currentAngle = -90; // Start at 12 o'clock

        sectors.forEach(sector => {
            if (sector.val <= 0) return;

            const percentage = sector.val / total;
            const strokeDashLength = percentage * circumference;
            
            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", "50");
            circle.setAttribute("cy", "50");
            circle.setAttribute("r", radius);
            circle.setAttribute("stroke", sector.color);
            circle.setAttribute("stroke-width", "8");
            circle.setAttribute("fill", "none");
            circle.setAttribute("stroke-dasharray", `${strokeDashLength} ${circumference}`);
            circle.setAttribute("transform", `rotate(${currentAngle} 50 50)`);
            circle.setAttribute("class", "donut-segment");
            circle.style.filter = `drop-shadow(0 0 4px ${sector.glow})`;
            
            svg.appendChild(circle);

            currentAngle += percentage * 360;
        });
    }

    // Dynamic Personalized Insights
    function updatePersonalizedInsights(elec, petrol, lpg, diet) {
        const container = elements.insightsListContainer;
        if (!container) return;

        const total = elec + petrol + lpg + diet;
        if (total === 0) {
            container.innerHTML = `<p class="insight-empty">Adjust consumption inputs to see tailored reduction insights.</p>`;
            return;
        }

        const sectors = [
            { id: "electricity", name: "Utility Electricity", val: elec, icon: "⚡" },
            { id: "petrol", name: "Petrol Transport", val: petrol, icon: "🚗" },
            { id: "lpg", name: "LPG Cooking Gas", val: lpg, icon: "🔥" },
            { id: "diet", name: "Dietary Choices", val: diet, icon: "🥗" }
        ];

        // Sort to find the highest sector
        sectors.sort((a, b) => b.val - a.val);
        const primarySector = sectors[0];
        const pct = ((primarySector.val / total) * 100).toFixed(0);

        // Recommendations dictionary
        const recommendationsDict = {
            electricity: [
                {
                    title: "Optimize Temperature Settings",
                    desc: "Adjusting your AC or heating thermostat by just 2°C can save up to 10% on monthly electric consumption.",
                    saving: "~15-30 kg CO₂e / month"
                },
                {
                    title: "Switch to Star Rated Appliances",
                    desc: "Transition to 5-star energy efficient refrigerators, ceiling fans, and LED light bulbs to reduce passive baseload energy draws.",
                    saving: "~20-40 kg CO₂e / month"
                },
                {
                    title: "Eliminate Phantom Loads",
                    desc: "Use smart power strips or unplug electronics (TVs, gaming consoles, chargers) when idle to eradicate standby electricity loss.",
                    saving: "~10-15 kg CO₂e / month"
                }
            ],
            petrol: [
                {
                    title: "Combine Trips & Plan Routes",
                    desc: "Combine weekly errands into single, optimized route loops to avoid cold engine starts which burn 20% more fuel in the first 8 km.",
                    saving: "~15-35 kg CO₂e / month"
                },
                {
                    title: "Maintain Proper Tire Pressure",
                    desc: "Under-inflated tires increase rolling resistance, reducing fuel economy by up to 3%. Check tire pressures monthly.",
                    saving: "~5-10 kg CO₂e / month"
                },
                {
                    title: "Embrace Active or Shared Transit",
                    desc: "For trips under 3 km, try walking or biking. Alternatively, replace 1 driving day per week with public transit or carpooling.",
                    saving: "~25-60 kg CO₂e / month"
                }
            ],
            lpg: [
                {
                    title: "Maximize Cooking Efficiency",
                    desc: "Always keep lids on pots to trap steam, heat ingredients to room temperature before lighting, and use pressure cookers which reduce cooking time by 70%.",
                    saving: "~5-10 kg CO₂e / month"
                },
                {
                    title: "Optimize Burner Flames",
                    desc: "Adjust burner flame size so it doesn't wrap around the sides of the pot, preventing wasted heat dispersion. Clean burners regularly.",
                    saving: "~2-5 kg CO₂e / month"
                },
                {
                    title: "Switch to Induction Cooking",
                    desc: "Electric induction cooktops transfer 90% of heat directly to the pan (compared to only 40% for gas burners), making it cleaner and more efficient.",
                    saving: "~10-15 kg CO₂e / month"
                }
            ],
            diet: [
                {
                    title: "Substitute High-Impact Meats",
                    desc: "Swapping beef or lamb for poultry or fish just 3 times a week dramatically reduces dietary footprint (beef has 8-10x the carbon impact of chicken).",
                    saving: "~30-65 kg CO₂e / month"
                },
                {
                    title: "Eradicate Household Food Waste",
                    desc: "Up to 30% of grocery purchases are discarded. Meal plan, freeze leftovers early, and organize your fridge to use ingredients before expiry.",
                    saving: "~15-30 kg CO₂e / month"
                },
                {
                    title: "Choose Local and Seasonal Foods",
                    desc: "Buying local produce avoids trans-oceanic cargo transport emissions and heavy plastic preservation packaging.",
                    saving: "~8-20 kg CO₂e / month"
                }
            ]
        };

        const recs = recommendationsDict[primarySector.id];
        
        let html = `
            <div class="insight-highlight-box">
                <span class="insight-icon">${primarySector.icon}</span>
                <div class="insight-summary-text">
                    <p>Your primary emission contributor is <strong>${primarySector.name}</strong>, representing <strong>${pct}%</strong> of your monthly footprint.</p>
                </div>
            </div>
            <div class="insights-list">
        `;

        recs.forEach(rec => {
            html += `
                <div class="insight-item-card">
                    <div class="insight-card-main">
                        <h4>${rec.title}</h4>
                        <p>${rec.desc}</p>
                    </div>
                    <div class="insight-card-badge">
                        <span>Est. Savings:</span>
                        <strong>${rec.saving}</strong>
                    </div>
                </div>
            `;
        });

        html += `</div>`;
        container.innerHTML = html;
    }

    // CSV Exporter
    async function exportHistoryToCSV() {
        try {
            const response = await fetch("/api/history");
            if (!response.ok) throw new Error("Failed to fetch historical database entries for export.");
            const history = await response.json();
            
            if (history.length === 0) {
                alert("No logs available to export.");
                return;
            }

            let csvRows = [];
            csvRows.push("Date,Electricity (kWh),Petrol Transport (km),Cooking Gas LPG (kg),Heavy Meat Meals (weekly),Plant Meals (weekly),Electricity Emissions (kg CO2e),Petrol Emissions (kg CO2e),LPG Emissions (kg CO2e),Diet Emissions (kg CO2e),Total Monthly Emissions (kg CO2e)");

            history.forEach(log => {
                const row = [
                    log.date,
                    log.electricity_kwh,
                    log.petrol_km,
                    log.lpg_kg,
                    log.meat_meals,
                    log.plant_meals,
                    log.breakdown.electricity.toFixed(2),
                    log.breakdown.petrol.toFixed(2),
                    log.breakdown.lpg.toFixed(2),
                    log.breakdown.diet.toFixed(2),
                    log.total_co2e.toFixed(2)
                ].join(",");
                csvRows.push(row);
            });

            const csvString = csvRows.join("\n");
            const blob = new Blob([csvString], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.setAttribute("href", url);
            link.setAttribute("download", `carbon_footprint_report_${new Date().toISOString().split("T")[0]}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (error) {
            alert(error.message);
        }
    }

    // 5. API calls to SQLite backend
    async function loadLogsHistory() {
        try {
            const response = await fetch("/api/history");
            if (!response.ok) throw new Error("Failed to fetch historical database entries.");
            const history = await response.json();
            
            updateHistoryTable(history);
            renderHistoryChart(history);
            
            // Novice badge check
            if (history.length > 0) {
                elements.badgeEcoNovice.classList.remove("locked");
                elements.badgeEcoNovice.classList.add("unlocked");
            } else {
                elements.badgeEcoNovice.classList.add("locked");
                elements.badgeEcoNovice.classList.remove("unlocked");
            }
        } catch (error) {
            console.error(error);
        }
    }

    async function submitConsumptionLog() {
        const payload = {
            electricity_kwh: parseFloat(elements.inputElec.value),
            petrol_km: parseFloat(elements.inputPetrol.value),
            lpg_kg: parseFloat(elements.inputLpg.value),
            meat_meals: parseInt(elements.inputMeat.value),
            plant_meals: parseInt(elements.inputPlant.value),
            date: elements.inputLogDate ? elements.inputLogDate.value : null
        };

        try {
            const response = await fetch("/api/logs", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error("Database logging submission failed.");
            
            await loadLogsHistory();
            
            // Pulse button feedback
            elements.btnSubmitLog.style.background = "var(--neon-cyan)";
            setTimeout(() => {
                elements.btnSubmitLog.style.background = "";
            }, 300);
            
        } catch (error) {
            alert(error.message);
        }
    }

    async function clearLogsHistory() {
        if (!confirm("Are you sure you want to purge all footprint log entries? This action is irreversible.")) return;

        try {
            const response = await fetch("/api/reset", { method: "POST" });
            if (!response.ok) throw new Error("History purge failed.");
            await loadLogsHistory();
        } catch (error) {
            alert(error.message);
        }
    }

    // 6. Rendering SVG Historical line graph
    function updateHistoryTable(history) {
        elements.logCountIndicator.innerText = `${history.length} log${history.length !== 1 ? 's' : ''} available`;
        
        if (history.length === 0) {
            elements.historyTableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="table-empty-message">No logged footprints recorded.</td>
                </tr>
            `;
            return;
        }

        elements.historyTableBody.innerHTML = history.slice().reverse().map(log => `
            <tr>
                <td>${log.date}</td>
                <td>${log.electricity_kwh} kWh</td>
                <td>${log.petrol_km} km</td>
                <td>${log.lpg_kg} kg</td>
                <td>${log.meat_meals}M / ${log.plant_meals}P</td>
                <td style="font-weight: 700; color: var(--neon-cyan)">${log.total_co2e.toFixed(1)} kg</td>
            </tr>
        `).join("");
    }

    function renderHistoryChart(history) {
        const svg = document.getElementById("history-chart");
        elements.chartGridLines.innerHTML = "";
        elements.chartDataPoints.innerHTML = "";
        
        if (history.length < 2) {
            // Draw dummy placeholder state
            elements.chartLinePath.setAttribute("d", "");
            elements.chartLineGlow.setAttribute("d", "");
            elements.chartAreaPath.setAttribute("d", "");
            return;
        }

        const width = 500;
        const height = 220;
        const paddingLeft = 40;
        const paddingRight = 20;
        const paddingTop = 30;
        const paddingBottom = 30;

        const chartWidth = width - paddingLeft - paddingRight;
        const chartHeight = height - paddingTop - paddingBottom;

        // Get bounds
        const maxVal = Math.max(...history.map(d => d.total_co2e));
        const yMax = Math.max(600, maxVal * 1.15); // Add 15% head room, minimum 600kg scale

        // Draw Y grid lines and labels
        const gridLinesCount = 4;
        for (let i = 0; i <= gridLinesCount; i++) {
            const ratio = i / gridLinesCount;
            const y = paddingTop + chartHeight * (1 - ratio);
            const value = (yMax * ratio).toFixed(0);

            // Draw line
            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", paddingLeft);
            line.setAttribute("y1", y);
            line.setAttribute("x2", width - paddingRight);
            line.setAttribute("y2", y);
            line.setAttribute("class", "chart-grid-line");
            elements.chartGridLines.appendChild(line);

            // Draw text label
            const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
            text.setAttribute("x", paddingLeft - 8);
            text.setAttribute("y", y + 3);
            text.setAttribute("text-anchor", "end");
            text.setAttribute("class", "chart-grid-label");
            text.textContent = `${value}kg`;
            elements.chartGridLines.appendChild(text);
        }

        // Draw points coordinates
        const points = history.map((d, index) => {
            const x = paddingLeft + (index / (history.length - 1)) * chartWidth;
            const y = paddingTop + (1 - d.total_co2e / yMax) * chartHeight;
            return { x, y, data: d };
        });

        // Generate Line Path SVG
        let pathString = `M ${points[0].x} ${points[0].y}`;
        for (let i = 1; i < points.length; i++) {
            // Cubic bezier control points for smooth curves
            const cpX1 = points[i - 1].x + (points[i].x - points[i - 1].x) / 2;
            const cpY1 = points[i - 1].y;
            const cpX2 = points[i - 1].x + (points[i].x - points[i - 1].x) / 2;
            const cpY2 = points[i].y;
            pathString += ` C ${cpX1} ${cpY1}, ${cpX2} ${cpY2}, ${points[i].x} ${points[i].y}`;
        }
        
        elements.chartLinePath.setAttribute("d", pathString);
        elements.chartLineGlow.setAttribute("d", pathString);

        // Generate Area fill SVG
        const areaString = `${pathString} L ${points[points.length - 1].x} ${height - paddingBottom} L ${points[0].x} ${height - paddingBottom} Z`;
        elements.chartAreaPath.setAttribute("d", areaString);

        // Draw Dots & Add Tooltips
        points.forEach((p, idx) => {
            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", p.x);
            circle.setAttribute("cy", p.y);
            circle.setAttribute("r", 4);
            circle.setAttribute("class", "chart-point");
            elements.chartDataPoints.appendChild(circle);

            // Label text underneath for date
            if (idx === 0 || idx === points.length - 1 || points.length <= 6) {
                const dateText = document.createElementNS("http://www.w3.org/2000/svg", "text");
                dateText.setAttribute("x", p.x);
                dateText.setAttribute("y", height - 10);
                dateText.setAttribute("text-anchor", "middle");
                dateText.setAttribute("class", "chart-grid-label");
                dateText.textContent = p.data.date;
                elements.chartGridLines.appendChild(dateText);
            }

            // Interactive Tooltip Events
            circle.addEventListener("mouseenter", (e) => {
                const rect = svg.getBoundingClientRect();
                const scaleX = rect.width / width;
                const scaleY = rect.height / height;
                
                const tooltipX = (p.x * scaleX) + 10;
                const tooltipY = (p.y * scaleY) - 50;

                elements.chartTooltip.innerHTML = `
                    <div style="font-weight:700; color:var(--neon-cyan);">${p.data.date}</div>
                    <div>Emissions: ${p.data.total_co2e.toFixed(1)} kg</div>
                    <div style="font-size:0.65rem; color:var(--text-secondary); margin-top:2px;">
                        E: ${p.data.breakdown.electricity.toFixed(0)} | T: ${p.data.breakdown.petrol.toFixed(0)} | G: ${p.data.breakdown.lpg.toFixed(0)} | D: ${p.data.breakdown.diet.toFixed(0)}
                    </div>
                `;
                elements.chartTooltip.style.left = `${tooltipX}px`;
                elements.chartTooltip.style.top = `${tooltipY}px`;
                elements.chartTooltip.style.opacity = 1;
            });

            circle.addEventListener("mouseleave", () => {
                elements.chartTooltip.style.opacity = 0;
            });
        });
    }

    // 7. Interactive Quiz Engine
    function initQuiz() {
        quizState.currentQuestion = 0;
        quizState.score = 0;
        quizState.answered = false;
        elements.quizActiveContainer.style.display = "block";
        elements.quizCompleteContainer.style.display = "none";
        showQuestion();
    }

    function showQuestion() {
        quizState.answered = false;
        elements.quizExplanationBox.style.display = "none";
        
        const q = quizQuestions[quizState.currentQuestion];
        elements.quizQuestionText.innerText = q.q;
        
        // Update progress
        const pct = ((quizState.currentQuestion + 1) / quizQuestions.length) * 100;
        elements.quizProgressFill.style.width = `${pct}%`;

        // Render options
        elements.quizOptionsList.innerHTML = q.options.map((opt, idx) => `
            <button type="button" class="quiz-option-btn" data-index="${idx}">${opt}</button>
        `).join("");

        // Option click handlers
        const btns = elements.quizOptionsList.querySelectorAll(".quiz-option-btn");
        btns.forEach(btn => {
            btn.addEventListener("click", () => {
                if (quizState.answered) return;
                selectOption(parseInt(btn.getAttribute("data-index")), btns);
            });
        });
    }

    function selectOption(selectedIdx, buttons) {
        quizState.answered = true;
        const q = quizQuestions[quizState.currentQuestion];
        
        if (selectedIdx === q.correct) {
            quizState.score++;
            buttons[selectedIdx].classList.add("correct");
        } else {
            buttons[selectedIdx].classList.add("incorrect");
            buttons[q.correct].classList.add("correct"); // highlight correct one
        }

        // Show explanation
        elements.quizExplanationText.innerText = q.explanation;
        elements.quizExplanationBox.style.display = "block";

        if (quizState.currentQuestion === quizQuestions.length - 1) {
            elements.btnNextQuestion.innerText = "Finish Quiz";
        } else {
            elements.btnNextQuestion.innerText = "Next Question";
        }
    }

    function handleNextQuestion() {
        if (quizState.currentQuestion < quizQuestions.length - 1) {
            quizState.currentQuestion++;
            showQuestion();
        } else {
            // End quiz
            elements.quizActiveContainer.style.display = "none";
            elements.quizCompleteContainer.style.display = "block";
            elements.quizFinalScore.innerText = quizState.score;

            // Quiz Wizard badge check
            if (quizState.score === 5) {
                elements.badgeQuizWizard.classList.remove("locked");
                elements.badgeQuizWizard.classList.add("unlocked");
            } else {
                elements.badgeQuizWizard.classList.add("locked");
                elements.badgeQuizWizard.classList.remove("unlocked");
            }
        }
    }

    // 8. Event Listeners binding
    function bindEvents() {
        // Slider value update listeners
        elements.inputElec.addEventListener("input", (e) => {
            elements.lblElec.innerText = `${e.target.value} kWh`;
            performLiveCalculations();
        });

        elements.inputPetrol.addEventListener("input", (e) => {
            elements.lblPetrol.innerText = `${e.target.value} km`;
            performLiveCalculations();
        });

        elements.inputLpg.addEventListener("input", (e) => {
            elements.lblLpg.innerText = `${e.target.value} kg`;
            performLiveCalculations();
        });

        elements.inputMeat.addEventListener("input", (e) => {
            elements.lblMeat.innerText = `${e.target.value} / week`;
            performLiveCalculations();
        });

        elements.inputPlant.addEventListener("input", (e) => {
            elements.lblPlant.innerText = `${e.target.value} / week`;
            performLiveCalculations();
        });

        // Submit log
        elements.btnSubmitLog.addEventListener("click", submitConsumptionLog);

        // Clear history
        elements.btnClearHistory.addEventListener("click", clearLogsHistory);

        // Export CSV
        if (elements.btnExportCsv) {
            elements.btnExportCsv.addEventListener("click", exportHistoryToCSV);
        }

        // Habits checkboxes
        const habitCards = document.querySelectorAll(".habit-card");
        habitCards.forEach(card => {
            const cb = card.querySelector(".habit-checkbox");
            const habitId = card.getAttribute("data-habit-id");
            
            cb.addEventListener("change", (e) => {
                activeHabits[habitId] = e.target.checked;
                if (e.target.checked) {
                    card.style.borderColor = "var(--neon-emerald)";
                    card.style.boxShadow = "0 0 10px rgba(16, 185, 129, 0.15)";
                } else {
                    card.style.borderColor = "";
                    card.style.boxShadow = "";
                }
                simulateHabitsReduction();
            });
        });

        // Quiz buttons
        elements.btnNextQuestion.addEventListener("click", handleNextQuestion);
        elements.btnRestartQuiz.addEventListener("click", initQuiz);
    }

    // 9. Boot application
    bindEvents();
    performLiveCalculations();
    loadLogsHistory();
    initQuiz();
});
