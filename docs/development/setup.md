# Local Development Setup Guide

This guide walks through setting up the local development environment for the Open Location Resolution Infrastructure.

---

## 1. Prerequisites

Ensure you have the following installed on your machine:
* **Python 3.11+**
* **Docker & Docker Compose**
* **uv** (recommended) or standard Python `venv` + `pip`

---

## 2. Setting Up Python Environment

Using `uv` (fastest):
```bash
# 1. Create a virtual environment
uv venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Install the project in editable mode with development dependencies
uv pip install -e ".[dev]"
```

Using standard `pip`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 3. Configuring Environment Variables

Copy the sample environment file:
```bash
cp .env.example .env
```

Review `.env` settings. The default credentials match the local PostGIS container configuration.

---

## 4. Starting the PostgreSQL + PostGIS Database

Start the database container in the background:
```bash
docker compose up -d
```

Verify that the database is running and healthy:
```bash
docker compose ps
```

---

## 5. Running the Test Suite

Execute the test suite using `pytest`:
```bash
pytest
```

---

## 6. Running Dataset Inspection

To inspect a raw OpenCelliD dataset (CSV or GZ) without modifying the database:
```bash
python scripts/inspect_dataset.py --file data/raw/<dataset_file.csv.gz>
```
Reports are automatically saved in `reports/dataset-inspection/`.
