import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
import joblib
from datetime import datetime
import sys
import os

# Add parent dir to path to import database and models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import SessionLocal
from models import Customer

def extract_features(customer, current_time):
    days_until_contract_end = (customer.contract_end_date - current_time).days
    nps_score = customer.nps_score
    
    open_tickets = [t for t in customer.tickets if t.status in ["Open", "In Progress"]]
    open_p1_tickets = len([t for t in open_tickets if t.severity == "P1"])
    open_p2_tickets = len([t for t in open_tickets if t.severity == "P2"])
    total_unresolved_tickets = len(open_tickets)
    
    resolved_tickets = [t for t in customer.tickets if t.status in ["Resolved", "Closed"] and t.satisfaction_rating is not None]
    if resolved_tickets:
        avg_ticket_satisfaction = sum(t.satisfaction_rating for t in resolved_tickets) / len(resolved_tickets)
    else:
        avg_ticket_satisfaction = 3.0 # Neutral default
        
    usage = sorted(customer.usage_metrics, key=lambda x: x.month, reverse=True)[:3]
    if len(usage) >= 2:
        bandwidth_trend = usage[0].bandwidth_utilization_pct - usage[-1].bandwidth_utilization_pct
    else:
        bandwidth_trend = 0.0
        
    if usage:
        uptime_avg_3m = sum(u.uptime_pct for u in usage) / len(usage)
    else:
        uptime_avg_3m = 100.0
        
    active_devices = [d for d in customer.devices if d.status != "Inactive"]
    device_rma_count = len([d for d in active_devices if d.status == "RMA"])
    active_device_ratio = len(active_devices) / len(customer.devices) if customer.devices else 0.0
    
    mrr = customer.monthly_recurring_revenue
    
    tier_map = {"Starter": 0, "Business": 1, "Enterprise": 2}
    plan_tier_encoded = tier_map.get(customer.plan_tier, 1)
    
    months_as_customer = (current_time - customer.contract_start_date).days // 30
    
    is_churned = 1 if days_until_contract_end < 0 else 0
    
    return {
        "days_until_contract_end": days_until_contract_end,
        "nps_score": nps_score,
        "open_p1_tickets": open_p1_tickets,
        "open_p2_tickets": open_p2_tickets,
        "total_unresolved_tickets": total_unresolved_tickets,
        "avg_ticket_satisfaction": avg_ticket_satisfaction,
        "bandwidth_trend": bandwidth_trend,
        "uptime_avg_3m": uptime_avg_3m,
        "device_rma_count": device_rma_count,
        "active_device_ratio": active_device_ratio,
        "mrr": mrr,
        "plan_tier_encoded": plan_tier_encoded,
        "months_as_customer": months_as_customer,
        "is_churned": is_churned
    }

def train_and_save_model():
    db = SessionLocal()
    customers = db.query(Customer).all()
    now = datetime.utcnow()
    
    data = []
    for c in customers:
        feats = extract_features(c, now)
        feats["customer_id"] = c.id
        data.append(feats)
        
    df = pd.DataFrame(data)
    
    features = [
        "days_until_contract_end", "nps_score", "open_p1_tickets",
        "open_p2_tickets", "total_unresolved_tickets", "avg_ticket_satisfaction",
        "bandwidth_trend", "uptime_avg_3m", "device_rma_count",
        "active_device_ratio", "mrr", "plan_tier_encoded", "months_as_customer"
    ]
    
    X = df[features]
    y = df["is_churned"]
    
    if sum(y) < 2:
        print("Not enough churned records for train-test split.")
        X_train, X_test, y_train, y_test = X, X, y, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    clf = GradientBoostingClassifier(random_state=42)
    clf.fit(X_train, y_train)
    
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]
    
    if len(np.unique(y_test)) > 1:
        auc = roc_auc_score(y_test, y_prob)
        print("Model Training Metrics:")
        print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.2f}")
        print(f"Recall: {recall_score(y_test, y_pred, zero_division=0):.2f}")
        print(f"F1 Score: {f1_score(y_test, y_pred, zero_division=0):.2f}")
        print(f"AUC-ROC: {auc:.2f}")
        if auc < 0.70:
            print("WARNING: AUC < 0.70. Recommended to add features: ticket_resolution_velocity, nps_momentum")
    
    model_path = os.path.join(os.path.dirname(__file__), "churn_model.pkl")
    features_path = os.path.join(os.path.dirname(__file__), "churn_features.pkl")
    joblib.dump(clf, model_path)
    joblib.dump(features, features_path)
    print(f"Churn model saved to {model_path}")

def get_churn_prediction(customer, current_time):
    model_path = os.path.join(os.path.dirname(__file__), "churn_model.pkl")
    features_path = os.path.join(os.path.dirname(__file__), "churn_features.pkl")
    try:
        clf = joblib.load(model_path)
        features_list = joblib.load(features_path)
    except FileNotFoundError:
        return {"churn_risk_score": 0.0, "risk_tier": "Low", "top_3_factors": []}
        
    feats_dict = extract_features(customer, current_time)
    X = pd.DataFrame([feats_dict], columns=features_list)
    
    prob = clf.predict_proba(X)[0, 1]
    
    if prob >= 0.7:
        risk_tier = "High"
    elif prob >= 0.4:
        risk_tier = "Medium"
    else:
        risk_tier = "Low"
        
    importances = clf.feature_importances_
    top_indices = np.argsort(importances)[::-1][:3]
    top_3_factors = []
    
    for idx in top_indices:
        feat_name = features_list[idx]
        val = feats_dict[feat_name]
        
        # Simple heuristic for direction
        if "days_until" in feat_name:
            direction = "Low" if val < 90 else "High"
        elif "nps" in feat_name:
            direction = "Low" if val < 6 else "High"
        elif "ticket" in feat_name:
            direction = "High" if val > 2 else "Normal"
        else:
            direction = "Significant"
            
        top_3_factors.append({
            "feature": feat_name,
            "direction": direction,
            "magnitude": round(float(importances[idx]), 3)
        })
        
    return {
        "churn_risk_score": float(prob),
        "risk_tier": risk_tier,
        "top_3_factors": top_3_factors
    }

if __name__ == "__main__":
    train_and_save_model()
