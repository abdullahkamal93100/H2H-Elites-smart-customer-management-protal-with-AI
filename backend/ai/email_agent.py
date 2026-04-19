import os
from anthropic import Anthropic
import json

def generate_weekly_email(customer_data):
    """
    customer_data contains all the necessary contextual data:
    {
        "customer": {...},
        "health": {...},
        "churn": {...},
        "tickets": [...],
        "devices": {...},
        "metrics": [...]
    }
    """
    anthropic = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    
    if not anthropic.api_key:
        return {
            "subject": "Missing API Key",
            "body": "<p>Anthropic API key not configured. Please add ANTHROPIC_API_KEY to your .env file.</p>"
        }

    system_prompt = """
    You are an AI Account Management Assistant for NexusNet Systems.
    Your task is to generate a professional, consultative, and proactive weekly account review email for a customer.
    The email should be in HTML format.
    Tone: Consultative, proactive, not alarming. Even if the customer is 'At Risk' or 'Critical', focus on solutions and action plans.
    
    The output must strictly be a JSON object containing:
    1. "subject": The email subject line.
    2. "body": The HTML content of the email.
    
    Use the provided customer data to personalize the email. Ensure you cover:
    - Customer overview (name, tier, account manager)
    - Health score and components (frame it constructively)
    - Churn risk factors (if applicable, phrase as areas of focus)
    - Open tickets summary
    - Device inventory summary
    - Recent usage metric trends
    - NPS score
    """
    
    try:
        response = anthropic.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Please generate the weekly review email using this data: {json.dumps(customer_data)}"}]
        )
        
        content = response.content[0].text
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        
        if start_idx != -1 and end_idx != 0:
            parsed = json.loads(content[start_idx:end_idx])
            return parsed
        else:
            return {"subject": "Weekly Account Review", "body": f"<p>{content}</p>"}
            
    except Exception as e:
        return {
            "subject": "Error generating email",
            "body": f"<p>An error occurred: {str(e)}</p>"
        }
