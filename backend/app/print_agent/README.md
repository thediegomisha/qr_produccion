```markdown
# Print Agent (FastAPI) - quick start

Location: backend/print_agent

1) Create and activate venv:
   python3 -m venv .venv
   source .venv/bin/activate

2) Install deps:
   pip install -r requirements.txt

3) Configure env vars:
   export AGENT_TOKEN="s3cr3t"
   export AGENT_ID="agent-001"
   export PRINTERS_JSON='[{"name":"zebra1","type":"network","host":"192.168.1.50","port":9100}]'
   export DB_PATH="./print_agent_jobs.db"

4) Run:
   uvicorn agent_app:app --host 0.0.0.0 --port 5000

5) Example request:
   curl -X POST http://localhost:5000/jobs \
     -H "X-Agent-Token: s3cr3t" \
     -H "Content-Type: application/json" \
     -d '{"printer":"zebra1","raw_base64":"<BASE64>","copies":1}'
```