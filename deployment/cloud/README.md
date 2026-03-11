# Cloud Deployment Guide

You can deploy Campaign In A Box to a remote cloud server so your whole team can access it.

## Minimum Server Requirements
For optimal performance running Monte Carlo simulations and processing precinct maps:
- **CPU:** 2 Cores
- **RAM:** 4 GB (8 GB recommended for county-wide or larger races)
- **Disk:** 20 GB SSD
- **OS:** Ubuntu 22.04 LTS

## Supported Cloud Providers
We recommend the following providers for cost-effective deployment:

### 1. DigitalOcean
Deploy a standard Droplet (`$12/mo` or `$24/mo` tier).
- SSH into the droplet.
- Git clone your repository.
- Use the provided Docker setup (`docker-compose up -d`) to run it in the background.

### 2. AWS (Amazon Web Services)
Deploy an EC2 instance (e.g., `t3.medium`).
- Ensure Security Group rules allow inbound traffic on port `8501` (for Streamlit).
- Alternatively, put an Application Load Balancer in front to serve via standard HTTPS (port 443).

### 3. Linode / Hetzner
Great low-cost options for budget-conscious campaigns.
- Provision a standard Linux compute instance.
- Follow the same Docker deployment process.

## Securing Your Cloud Instance
Because the dashboard will process sensitive campaign configurations:
1. **Never commit raw voter files** (`data/voters/` is git-ignored).
2. Consider placing the dashboard behind a reverse proxy (e.g., Nginx) with **Basic Authentication** or OAuth to prevent unauthorized access.
3. Configure **HTTPS (Let's Encrypt)** so traffic is encrypted in transit. Use Nginx and Certbot for this.

## Running on Cloud
Once your server is provisioned:

```bash
git clone https://github.com/your-org/campaign-in-a-box.git
cd campaign-in-a-box

# Setup your data and config
# Note: You must SCP or manually upload your raw data/voters and data/elections since they are git-ignored!

# Start the app via Docker
cd deployment/docker
docker compose up -d
```

Visit `http://<your-server-ip>:8501`.
