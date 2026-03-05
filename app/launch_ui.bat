@echo off
cd /d "%~dp0.."
echo Starting Campaign In A Box Web UI...
echo Open your browser to: http://localhost:8501
streamlit run app/app.py --server.port 8501 --server.headless false
