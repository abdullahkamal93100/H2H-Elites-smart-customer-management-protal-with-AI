from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DeviceBase(BaseModel):
    device_type: str
    model_number: str
    firmware_version: str
    status: str

class DeviceCreate(DeviceBase):
    pass

class Device(DeviceBase):
    id: int
    customer_id: int
    install_date: datetime
    last_seen_at: datetime
    
    class Config:
        from_attributes = True

class TicketBase(BaseModel):
    title: str
    severity: str
    status: str

class TicketCreate(TicketBase):
    customer_id: int

class Ticket(TicketBase):
    id: int
    customer_id: int
    created_at: datetime
    resolved_at: Optional[datetime] = None
    satisfaction_rating: Optional[int] = None
    
    class Config:
        from_attributes = True

class UsageMetricBase(BaseModel):
    month: str
    bandwidth_utilization_pct: float
    uptime_pct: float
    api_calls: int
    active_devices_count: int

class UsageMetric(UsageMetricBase):
    id: int
    customer_id: int
    
    class Config:
        from_attributes = True

class CustomerBase(BaseModel):
    company_name: str
    industry: str
    region: str
    plan_tier: str
    account_manager: str
    monthly_recurring_revenue: float
    nps_score: int

class CustomerCreate(CustomerBase):
    pass

class Customer(CustomerBase):
    id: int
    contract_start_date: datetime
    contract_end_date: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True

class CustomerDetail(Customer):
    devices: List[Device] = []
    tickets: List[Ticket] = []
    usage_metrics: List[UsageMetric] = []

class PaginatedCustomers(BaseModel):
    items: List[Customer]
    total: int
    page: int
    size: int

class NLQueryRequest(BaseModel):
    question: str
    conversation_history: List[dict] = []

class NLQueryResponse(BaseModel):
    answer: str
    sql: str
    data: List[dict]
    columns: List[str]

class EmailAgentRequest(BaseModel):
    customer_id: int

class EmailAgentResponse(BaseModel):
    subject: str
    body: str
