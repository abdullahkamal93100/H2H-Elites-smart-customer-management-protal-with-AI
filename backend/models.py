from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, index=True)
    industry = Column(String)
    region = Column(String) # APAC/EMEA/AMER/LATAM
    plan_tier = Column(String) # Starter/Business/Enterprise
    contract_start_date = Column(DateTime)
    contract_end_date = Column(DateTime)
    account_manager = Column(String)
    monthly_recurring_revenue = Column(Float)
    nps_score = Column(Integer) # 0-10
    created_at = Column(DateTime)
    
    devices = relationship("Device", back_populates="customer", cascade="all, delete-orphan")
    tickets = relationship("Ticket", back_populates="customer", cascade="all, delete-orphan")
    usage_metrics = relationship("UsageMetric", back_populates="customer", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    device_type = Column(String) # Router/Switch/Firewall/AP/SD-WAN
    model_number = Column(String)
    firmware_version = Column(String)
    install_date = Column(DateTime)
    status = Column(String) # Active/Inactive/RMA
    last_seen_at = Column(DateTime)
    
    customer = relationship("Customer", back_populates="devices")

class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    title = Column(String)
    severity = Column(String) # P1/P2/P3/P4
    status = Column(String) # Open/In Progress/Resolved/Closed
    created_at = Column(DateTime)
    resolved_at = Column(DateTime, nullable=True)
    satisfaction_rating = Column(Integer, nullable=True) # 1-5
    
    customer = relationship("Customer", back_populates="tickets")

class UsageMetric(Base):
    __tablename__ = "usage_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    month = Column(String) # YYYY-MM
    bandwidth_utilization_pct = Column(Float)
    uptime_pct = Column(Float)
    api_calls = Column(Integer)
    active_devices_count = Column(Integer)
    
    customer = relationship("Customer", back_populates="usage_metrics")
