# 🇵🇰 Pakistan Job Market AI Scraper Agent

An automated agent that monitors 6 major Pakistani job portals every 6 hours and maintains a professional Excel report.

## 📋 Monitored Portals

| # | Portal | Type | URL |
|---|--------|------|-----|
| 1 | Rozee.pk | Commercial | https://www.rozee.pk |
| 2 | Mustakbil.com | Commercial | https://www.mustakbil.com |
| 3 | FPSC | Federal Government | https://www.fpsc.gov.pk |
| 4 | KPPSC | KP Government | https://www.kppsc.gov.pk |
| 5 | SPSC | Sindh Government | https://spsc.gov.pk |
| 6 | AJKPSC | AJK Government | https://www.ajkpsc.gov.pk |

## 🗂️ Excel Report Structure

The output file `Pakistan_Jobs_Report.xlsx` contains:

| Sheet | Description |
|-------|-------------|
| 🏠 Dashboard | Summary KPI table with active/closed counts per source |
| Rozee.pk | All active jobs from Rozee.pk |
| Mustakbil.com | All active jobs from Mustakbil.com |
| FPSC | All active advertisements from FPSC |
| KPPSC | All active advertisements from KPPSC |
| SPSC | All active advertisements from SPSC |
| AJKPSC | All active advertisements from AJKPSC |
| 📊 All Active Jobs | Combined view of all active listings |
| ❌ Closed Jobs | Historical record of ended listings |

## 🚀 Running the Agent

### Step 1: Activate the virtual environment
```powershell
.\venv\Scripts\Activate.ps1
```

### Step 2: Run the agent
```powershell
python scraper_agent.py
```

The agent will:
1. Run immediately upon launch
2. Generate `Pakistan_Jobs_Report.xlsx`
3. Re-run every 6 hours automatically

> ⚠️ Keep the terminal window open for continuous operation.

## 📁 Project Structure

```
project/
├── scraper_agent.py     # Main entry point & scheduler
├── extractors.py        # Site-specific scraping logic
├── data_manager.py      # Excel writing with professional formatting
├── requirements.txt     # Python dependencies
├── logs/                # Automatic daily log files
│   └── agent_YYYYMMDD.log
└── Pakistan_Jobs_Report.xlsx  # Auto-generated output
```

## 🔧 Dependencies

Install with:
```bash
pip install -r requirements.txt
playwright install chromium
```
