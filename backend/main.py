from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

from database import engine, get_db, Base
import models
import schemas
from ai.health_engine import calculate_health_score
from ai.churn_model import get_churn_prediction
from ai.nl_engine import execute_nl_query
from ai.email_agent import generate_weekly_email

load_dotenv()

app = FastAPI(title="NexusNet CRM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Customers ---
@app.get("/api/customers", response_model=schemas.PaginatedCustomers)
def get_customers(
    db: Session = Depends(get_db),
    page: int = 1,
    size: int = 20,
    region: Optional[str] = None,
    tier: Optional[str] = None,
    risk: Optional[str] = None
):
    query = db.query(models.Customer)
    if region:
        query = query.filter(models.Customer.region == region)
    if tier:
        query = query.filter(models.Customer.plan_tier == tier)
        
    total = query.count()
    customers = query.offset((page - 1) * size).limit(size).all()
    
    if risk:
        all_customers = query.all()
        now = datetime.utcnow()
        filtered = []
        for c in all_customers:
            churn = get_churn_prediction(c, now)
            if churn["risk_tier"] == risk:
                filtered.append(c)
        total = len(filtered)
        customers = filtered[(page - 1) * size : page * size]
        
    return {"items": customers, "total": total, "page": page, "size": size}

@app.get("/api/customers/{id}", response_model=schemas.CustomerDetail)
def get_customer(id: int, db: Session = Depends(get_db)):
    c = db.query(models.Customer).filter(models.Customer.id == id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c

@app.post("/api/customers", response_model=schemas.Customer)
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    db_cust = models.Customer(**customer.model_dump(), contract_start_date=datetime.utcnow(), contract_end_date=datetime.utcnow(), created_at=datetime.utcnow())
    db.add(db_cust)
    db.commit()
    db.refresh(db_cust)
    return db_cust

@app.put("/api/customers/{id}", response_model=schemas.Customer)
def update_customer(id: int, customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    c = db.query(models.Customer).filter(models.Customer.id == id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    for k, v in customer.model_dump().items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c

@app.delete("/api/customers/{id}")
def delete_customer(id: int, db: Session = Depends(get_db)):
    c = db.query(models.Customer).filter(models.Customer.id == id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(c)
    db.commit()
    return {"status": "ok"}

# --- Tickets ---
@app.get("/api/tickets", response_model=List[schemas.Ticket])
def get_tickets(
    db: Session = Depends(get_db),
    customer_id: Optional[int] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None
):
    query = db.query(models.Ticket)
    if customer_id:
        query = query.filter(models.Ticket.customer_id == customer_id)
    if severity:
        query = query.filter(models.Ticket.severity == severity)
    if status:
        query = query.filter(models.Ticket.status == status)
    return query.all()

@app.get("/api/tickets/{id}", response_model=schemas.Ticket)
def get_ticket(id: int, db: Session = Depends(get_db)):
    t = db.query(models.Ticket).filter(models.Ticket.id == id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t

@app.post("/api/tickets", response_model=schemas.Ticket)
def create_ticket(ticket: schemas.TicketCreate, db: Session = Depends(get_db)):
    db_ticket = models.Ticket(**ticket.model_dump(), created_at=datetime.utcnow())
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

@app.put("/api/tickets/{id}", response_model=schemas.Ticket)
def update_ticket(id: int, ticket: schemas.TicketBase, db: Session = Depends(get_db)):
    t = db.query(models.Ticket).filter(models.Ticket.id == id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    for k, v in ticket.model_dump().items():
        setattr(t, k, v)
    if ticket.status in ["Resolved", "Closed"] and not t.resolved_at:
        t.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return t

# --- Devices ---
@app.get("/api/devices", response_model=List[schemas.Device])
def get_devices(
    db: Session = Depends(get_db),
    customer_id: Optional[int] = None,
    status: Optional[str] = None
):
    query = db.query(models.Device)
    if customer_id:
        query = query.filter(models.Device.customer_id == customer_id)
    if status:
        query = query.filter(models.Device.status == status)
    return query.all()

@app.get("/api/devices/{id}", response_model=schemas.Device)
def get_device(id: int, db: Session = Depends(get_db)):
    d = db.query(models.Device).filter(models.Device.id == id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    return d

@app.post("/api/devices", response_model=schemas.Device)
def create_device(device: schemas.DeviceCreate, customer_id: int, db: Session = Depends(get_db)):
    db_device = models.Device(**device.model_dump(), customer_id=customer_id, install_date=datetime.utcnow(), last_seen_at=datetime.utcnow())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device

@app.put("/api/devices/{id}", response_model=schemas.Device)
def update_device(id: int, device: schemas.DeviceBase, db: Session = Depends(get_db)):
    d = db.query(models.Device).filter(models.Device.id == id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    for k, v in device.model_dump().items():
        setattr(d, k, v)
    db.commit()
    db.refresh(d)
    return d

# --- Metrics ---
@app.get("/api/metrics/{customer_id}", response_model=List[schemas.UsageMetric])
def get_metrics(customer_id: int, months: int = 6, db: Session = Depends(get_db)):
    c = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return sorted(c.usage_metrics, key=lambda x: x.month, reverse=True)[:months]

# --- AI Endpoints ---
@app.get("/api/health/{customer_id}")
def get_health(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return calculate_health_score(c, datetime.utcnow())

@app.get("/api/churn")
def get_churn(db: Session = Depends(get_db)):
    customers = db.query(models.Customer).all()
    now = datetime.utcnow()
    results = []
    for c in customers:
        churn_data = get_churn_prediction(c, now)
        results.append({
            "customer_id": c.id,
            "company_name": c.company_name,
            **churn_data
        })
    return results

@app.post("/api/nl-query", response_model=schemas.NLQueryResponse)
def nl_query(request: schemas.NLQueryRequest):
    # db_path depends on where we run it. Usually main.py runs from backend dir, so db is at ./nexusnet.db
    # Wait, in database.py we use sqlite:///./nexusnet.db. We should use absolute path if possible or keep relative
    return execute_nl_query(request.question, request.conversation_history)

@app.post("/api/email-agent", response_model=schemas.EmailAgentResponse)
def email_agent(request: schemas.EmailAgentRequest, db: Session = Depends(get_db)):
    c = db.query(models.Customer).filter(models.Customer.id == request.customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    now = datetime.utcnow()
    health = calculate_health_score(c, now)
    churn = get_churn_prediction(c, now)
    
    # Serialize for JSON using Pydantic model_dump
    customer_dict = schemas.Customer.model_validate(c).model_dump()
    customer_dict['contract_start_date'] = customer_dict['contract_start_date'].isoformat()
    customer_dict['contract_end_date'] = customer_dict['contract_end_date'].isoformat()
    customer_dict['created_at'] = customer_dict['created_at'].isoformat()
    
    tickets_list = []
    for t in c.tickets:
        if t.status in ["Open", "In Progress"]:
            t_dict = schemas.Ticket.model_validate(t).model_dump()
            t_dict['created_at'] = t_dict['created_at'].isoformat()
            if t_dict.get('resolved_at'):
                t_dict['resolved_at'] = t_dict['resolved_at'].isoformat()
            tickets_list.append(t_dict)
            
    metrics_list = []
    for m in sorted(c.usage_metrics, key=lambda x: x.month, reverse=True)[:3]:
        metrics_list.append(schemas.UsageMetric.model_validate(m).model_dump())
    
    customer_data = {
        "customer": customer_dict,
        "health": health,
        "churn": churn,
        "tickets": tickets_list,
        "devices": {
            "total": len(c.devices),
            "active": len([d for d in c.devices if d.status == "Active"]),
            "inactive": len([d for d in c.devices if d.status == "Inactive"]),
            "rma": len([d for d in c.devices if d.status == "RMA"])
        },
        "metrics": metrics_list
    }
    
    return generate_weekly_email(customer_data)
