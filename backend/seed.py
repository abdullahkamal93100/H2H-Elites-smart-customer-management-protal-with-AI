import random
from datetime import datetime, timedelta
from faker import Faker
from database import engine, Base, SessionLocal
from models import Customer, Device, Ticket, UsageMetric

fake = Faker()
Base.metadata.create_all(bind=engine)

def seed_database():
    db = SessionLocal()
    
    # Clear existing data
    db.query(UsageMetric).delete()
    db.query(Ticket).delete()
    db.query(Device).delete()
    db.query(Customer).delete()
    db.commit()

    total_customers = 220
    at_risk_count = 35
    churned_count = 40
    normal_count = total_customers - at_risk_count - churned_count

    regions = ["APAC", "EMEA", "AMER", "LATAM"]
    device_types = ["Router", "Switch", "Firewall", "AP", "SD-WAN"]

    now = datetime.utcnow()

    # Generate normal
    for _ in range(normal_count):
        create_customer(db, fake, now, "normal", regions, device_types)
    
    # Generate at-risk
    for _ in range(at_risk_count):
        create_customer(db, fake, now, "at_risk", regions, device_types)
        
    # Generate churned
    for _ in range(churned_count):
        create_customer(db, fake, now, "churned", regions, device_types)

    db.commit()
    print("Database seeded with 220 customers!")

def create_customer(db, fake, now, c_type, regions, device_types):
    tier = random.choices(["Starter", "Business", "Enterprise"], weights=[0.4, 0.4, 0.2])[0]
    
    # Base MRR and Device Counts
    if tier == "Enterprise":
        mrr = round(random.uniform(8000, 40000), 2)
        dev_count = random.randint(15, 80)
    elif tier == "Starter":
        mrr = round(random.uniform(2000, 12000) / 10, 2) # $200-$1200
        dev_count = random.randint(1, 5)
    else: # Business
        mrr = round(random.uniform(1500, 7500), 2)
        dev_count = random.randint(5, 15)

    nps = random.randint(6, 10)
    contract_start = now - timedelta(days=random.randint(300, 1000))
    contract_end = contract_start + timedelta(days=365 * random.randint(1, 3))
    
    # Type specific overrides
    if c_type == "at_risk":
        nps = random.randint(0, 4)
        contract_end = now + timedelta(days=random.randint(5, 89)) # ending within 90 days
    elif c_type == "churned":
        contract_end = now - timedelta(days=random.randint(10, 180)) # ended in the past
        nps = random.randint(0, 5)

    customer = Customer(
        company_name=fake.company(),
        industry=fake.job(),
        region=random.choice(regions),
        plan_tier=tier,
        contract_start_date=contract_start,
        contract_end_date=contract_end,
        account_manager=fake.name(),
        monthly_recurring_revenue=mrr,
        nps_score=nps,
        created_at=contract_start
    )
    db.add(customer)
    db.flush() # get ID

    # Devices
    rma_count = 0
    for _ in range(dev_count):
        status = "Active"
        if c_type == "at_risk" and rma_count < 2:
            status = "RMA"
            rma_count += 1
        elif random.random() < 0.05:
            status = random.choice(["Inactive", "RMA"])
            
        device = Device(
            customer_id=customer.id,
            device_type=random.choice(device_types),
            model_number=f"{fake.word()[:3].upper()}-{random.randint(1000,9999)}",
            firmware_version=f"v{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,9)}",
            install_date=contract_start + timedelta(days=random.randint(1, 30)),
            status=status,
            last_seen_at=now - timedelta(minutes=random.randint(1, 1440)) if status == "Active" else now - timedelta(days=random.randint(1, 30))
        )
        db.add(device)

    # Tickets
    if c_type == "at_risk":
        ticket_count = random.randint(3, 6)
        for i in range(ticket_count):
            sev = random.choice(["P1", "P2"])
            status = "Open" if i < 3 else "Resolved" # At least 3 open P1/P2
            ticket = Ticket(
                customer_id=customer.id,
                title=fake.sentence(),
                severity=sev,
                status=status,
                created_at=now - timedelta(days=random.randint(1, 10)),
                resolved_at=None if status == "Open" else now - timedelta(hours=random.randint(1, 48)),
                satisfaction_rating=None if status == "Open" else random.randint(1, 3)
            )
            db.add(ticket)
    else:
        # random tickets
        for _ in range(random.randint(0, 5)):
            status = random.choice(["Open", "In Progress", "Resolved", "Closed"])
            ticket = Ticket(
                customer_id=customer.id,
                title=fake.sentence(),
                severity=random.choice(["P1", "P2", "P3", "P4"]),
                status=status,
                created_at=now - timedelta(days=random.randint(1, 60)),
                resolved_at=None if status in ["Open", "In Progress"] else now - timedelta(days=random.randint(1, 30)),
                satisfaction_rating=None if status in ["Open", "In Progress"] else random.randint(3, 5)
            )
            db.add(ticket)

    # Usage Metrics (18 months rolling)
    bw_base = random.uniform(30, 80)
    for m in range(18):
        month_date = now - timedelta(days=30 * (17 - m))
        
        # bandwidth trend
        bw = bw_base
        if c_type == "at_risk" and m >= 15: # trending down last 3 months
            bw = max(10, bw_base - (m - 14) * 15)
        else:
            bw = max(10, min(95, bw + random.uniform(-10, 10)))
            
        up_pct = 99.9 if c_type != "at_risk" else random.uniform(90.0, 98.0)
            
        metric = UsageMetric(
            customer_id=customer.id,
            month=month_date.strftime("%Y-%m"),
            bandwidth_utilization_pct=bw,
            uptime_pct=up_pct,
            api_calls=random.randint(1000, 50000),
            active_devices_count=int(dev_count * 0.9) if c_type != "at_risk" else max(1, int(dev_count * 0.6))
        )
        db.add(metric)

if __name__ == "__main__":
    seed_database()
