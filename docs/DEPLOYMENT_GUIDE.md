# Deployment Guide

Campaign In A Box is designed to run in three main physical environments, scaling from a single laptop in the field to a remote cloud server for distributed teams.

## 1. Local Laptop Install (Windows/Mac)
The simplest way to run the platform is locally.

### Requirements
- Python >= 3.10
- Git

### Installation
Clone the repository and run the setup script:

**Windows:**
```powershell
.\deployment\install\install_campaign_in_a_box.ps1
```

**Mac / Linux:**
```bash
./deployment/install/install_campaign_in_a_box.sh
```

### Running the App
Once installed, double click or run your launch script:
```powershell
.\run_campaign_box.ps1
# or
./run_campaign_box.sh
```
A setup wizard will automatically prompt you for your campaign details (Campaign Name, Jurisdiction, etc.) the first time you run it.

## 2. Docker Installation
For those with Docker installed, you can skip the python environment setup entirely.

```bash
cd deployment/docker
docker compose up -build -d
```
Access the application at `http://localhost:8501`.

## 3. Remote Cloud Server
Please see the dedicated cloud guide at `deployment/cloud/README.md` for specific instructions on provisioning AWS, DigitalOcean, or Linode instances.

---

## Operations Management

### System Diagnostics
To verify that your installation is healthy and all required libraries are mounted:
```bash
python deployment/scripts/system_check.py
```
This will produce a markdown report in `reports/system/system_health.md`.

### Backups
To safely archive your config, outputs, and reports without leaking raw voter data:
```bash
./deployment/scripts/backup_campaign.sh
```
Extracts a tarball into the `archive/` folder.

To restore:
```bash
./deployment/scripts/restore_campaign.sh archive/backup_YYYY_MM_DD.tar.gz
```
