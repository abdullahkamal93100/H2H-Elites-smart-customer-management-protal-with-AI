def calculate_health_score(customer, current_time):
    # nps component
    nps_component = (customer.nps_score / 10.0) * 25

    # ticket component
    open_tickets = [t for t in customer.tickets if t.status in ["Open", "In Progress"]]
    critical_tickets = [t for t in open_tickets if t.severity in ["P1", "P2"]]
    
    ratio = len(critical_tickets) / len(open_tickets) if open_tickets else 0
    ticket_component = (1 - ratio) * 25

    # usage component
    usage = sorted(customer.usage_metrics, key=lambda x: x.month, reverse=True)[:3]
    if usage:
        avg_uptime = sum(u.uptime_pct for u in usage) / len(usage)
    else:
        avg_uptime = 100.0
    usage_component = (avg_uptime / 100.0) * 25

    # contract component
    days_until_expiry = (customer.contract_end_date - current_time).days
    if days_until_expiry > 365:
        days_score = 1.0
    elif days_until_expiry > 180:
        days_score = 0.7
    elif days_until_expiry > 90:
        days_score = 0.4
    elif days_until_expiry > 0:
        days_score = 0.1
    else:
        days_score = 0.0
    
    contract_component = days_score * 15

    # device component
    active_devices = [d for d in customer.devices if d.status != "Inactive"]
    rma_devices = [d for d in active_devices if d.status == "RMA"]
    rma_ratio = len(rma_devices) / len(active_devices) if active_devices else 0
    device_health = (1 - rma_ratio) * 10

    score = nps_component + ticket_component + usage_component + contract_component + device_health
    
    if score >= 80:
        grade = "Healthy"
    elif score >= 60:
        grade = "Needs Attention"
    elif score >= 40:
        grade = "At Risk"
    else:
        grade = "Critical"
        
    return {
        "score": round(score, 1),
        "grade": grade,
        "components": {
            "nps": round(nps_component, 1),
            "tickets": round(ticket_component, 1),
            "usage": round(usage_component, 1),
            "contract": round(contract_component, 1),
            "devices": round(device_health, 1)
        }
    }
