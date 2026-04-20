import os
import json
import sqlite3
from anthropic import Anthropic

def execute_nl_query(question, conversation_history, db_path="nexusnet.db"):
    anthropic = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    
    schema = """
    Table: customers
    - id (INTEGER PRIMARY KEY)
    - company_name (VARCHAR)
    - industry (VARCHAR)
    - region (VARCHAR) - Values: APAC, EMEA, AMER, LATAM
    - plan_tier (VARCHAR) - Values: Starter, Business, Enterprise
    - contract_start_date (DATETIME)
    - contract_end_date (DATETIME)
    - account_manager (VARCHAR)
    - monthly_recurring_revenue (FLOAT)
    - nps_score (INTEGER) - 0 to 10
    - created_at (DATETIME)

    Table: devices
    - id (INTEGER PRIMARY KEY)
    - customer_id (INTEGER)
    - device_type (VARCHAR) - Values: Router, Switch, Firewall, AP, SD-WAN
    - model_number (VARCHAR)
    - firmware_version (VARCHAR)
    - install_date (DATETIME)
    - status (VARCHAR) - Values: Active, Inactive, RMA
    - last_seen_at (DATETIME)

    Table: tickets
    - id (INTEGER PRIMARY KEY)
    - customer_id (INTEGER)
    - title (VARCHAR)
    - severity (VARCHAR) - Values: P1, P2, P3, P4
    - status (VARCHAR) - Values: Open, In Progress, Resolved, Closed
    - created_at (DATETIME)
    - resolved_at (DATETIME)
    - satisfaction_rating (INTEGER) - 1 to 5

    Table: usage_metrics
    - id (INTEGER PRIMARY KEY)
    - customer_id (INTEGER)
    - month (VARCHAR) - Format: YYYY-MM
    - bandwidth_utilization_pct (FLOAT)
    - uptime_pct (FLOAT)
    - api_calls (INTEGER)
    - active_devices_count (INTEGER)
    """

    examples = """
    Q: "How many customers are in APAC?"
    SQL: SELECT COUNT(*) as count FROM customers WHERE region = 'APAC';
    
    Q: "Show all Enterprise customers with MRR above $10,000"
    SQL: SELECT company_name, region, monthly_recurring_revenue FROM customers WHERE plan_tier = 'Enterprise' AND monthly_recurring_revenue > 10000;
    
    Q: "Which customers have open P1 tickets?"
    SQL: SELECT c.company_name, t.title FROM customers c JOIN tickets t ON c.id = t.customer_id WHERE t.severity = 'P1' AND t.status IN ('Open', 'In Progress');
    
    Q: "What is the average NPS score by region?"
    SQL: SELECT region, AVG(nps_score) as avg_nps FROM customers GROUP BY region;
    
    Q: "Show customers whose contracts expire in the next 60 days"
    SQL: SELECT company_name, contract_end_date FROM customers WHERE contract_end_date BETWEEN datetime('now') AND datetime('now', '+60 days');
    
    Q: "Which plan tier has the highest average churn risk?"
    SQL: -- Proxy using NPS
    SELECT plan_tier, AVG(nps_score) as avg_nps FROM customers GROUP BY plan_tier;
    
    Q: "List customers with more than 3 RMA devices and low NPS"
    SQL: SELECT c.company_name, COUNT(d.id) as rma_count, c.nps_score FROM customers c JOIN devices d ON c.id = d.customer_id WHERE d.status = 'RMA' AND c.nps_score <= 5 GROUP BY c.id HAVING rma_count > 3;
    
    Q: "What is the total MRR at risk from high-churn customers?"
    SQL: SELECT SUM(monthly_recurring_revenue) as mrr_at_risk FROM customers WHERE nps_score <= 4 AND contract_end_date <= datetime('now', '+90 days');
    
    Q: "Show monthly uptime trend for Acme Corp over the last 6 months"
    SQL: SELECT u.month, u.uptime_pct FROM usage_metrics u JOIN customers c ON u.customer_id = c.id WHERE c.company_name LIKE '%Acme%' ORDER BY u.month DESC LIMIT 6;
    
    Q: "Which account managers have the most at-risk customers?"
    SQL: SELECT account_manager, COUNT(*) as at_risk_count FROM customers WHERE nps_score <= 4 OR contract_end_date <= datetime('now', '+90 days') GROUP BY account_manager ORDER BY at_risk_count DESC LIMIT 5;
    """

    system_prompt = f"""
    You are a SQL expert for the NexusNet CRM SQLite database.
    Your job is to translate a user's question into a SQLite SELECT query, explain it, and suggest a format for the frontend.
    
    CRITICAL RULES:
    1. Output ONLY a JSON object.
    2. The JSON MUST have this structure: {{"sql": "...", "explanation": "...", "result_format": "table|scalar"}}
    3. NEVER generate DML or DDL (no INSERT, UPDATE, DELETE, DROP). ONLY use SELECT.
    4. Handle follow-up questions using the conversation history (e.g., "Of those, which ones are in EMEA?").
    
    Schema:
    {schema}
    
    Examples:
    {examples}
    """
    
    messages = []
    for msg in conversation_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    try:
        if not anthropic.api_key:
            return {
                "answer": "Anthropic API key not configured. Please add ANTHROPIC_API_KEY to your .env file.",
                "sql": "-- Configuration Error",
                "data": []
            }

        response = anthropic.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )
        
        content = response.content[0].text
        # Parse JSON
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = content[start_idx:end_idx]
            parsed = json.loads(json_str)
        else:
            raise Exception("Claude did not return JSON format.")
        
        sql = parsed.get("sql")
        explanation = parsed.get("explanation", "Query generated.")
        
        # Execute SQL
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if any(keyword in sql.lower() for keyword in ["insert ", "update ", "delete ", "drop "]):
            raise Exception("Unsafe SQL detected.")
            
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        results = [{col: row[col] for col in columns} for row in rows]
            
        conn.close()
        
        return {
            "answer": explanation,
            "sql": sql,
            "data": results,
            "columns": columns
        }
    except Exception as e:
        return {
            "answer": f"Error processing query: {str(e)}",
            "sql": locals().get("sql", "-- None"),
            "data": [],
            "columns": []
        }
