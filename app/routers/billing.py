from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timedelta
from app.models import (
    BillingRates, Invoice, InvoiceGenerateRequest, Transaction, TransactionInDB,
    LineItem, InvoiceStatus, TransactionMethod, ErrorResponse, SuccessResponse
)
from app.auth import get_current_user, UserInDB
from app.database import get_database
from app.config import settings
from app.nats_client import publish_invoice_generated
import uuid

router = APIRouter(tags=["Billing"])


@router.get("/rates", response_model=BillingRates)
async def get_billing_rates():
    """Get current billing rates"""
    return BillingRates(
        vcpu_rate_per_core_hour=settings.vcpu_rate_per_core_hour,
        ram_rate_per_gib_hour=settings.ram_rate_per_gib_hour,
        disk_rate_per_gib_hour=settings.disk_rate_per_gib_hour
    )


@router.post("/invoices/generate", response_model=Invoice)
async def generate_invoice(
    request: InvoiceGenerateRequest,
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Generate an invoice for a specific period"""
   
    if request.period_start >= request.period_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Period start must be before period end"
        )
    
    # Check if invoice already exists 
    existing_invoice = await db.invoices.find_one({
        "user_id": current_user.id,
        "period_start": request.period_start,
        "period_end": request.period_end
    })
    
    if existing_invoice:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice already exists for this period"
        )
    
    try:
        servers = []
        async for server_doc in db.servers.find({"user_id": current_user.id}):
            servers.append(server_doc)
        
        if not servers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No servers found for user"
            )
        
        line_items = []
        total_amount = 0.0
        
        for server in servers:
            server_id = server["id"]
            
            usage_samples = []
            async for sample_doc in db.usage_samples.find({
                "server_id": server_id,
                "ts": {
                    "$gte": request.period_start,
                    "$lt": request.period_end
                }
            }).sort("ts", 1):
                usage_samples.append(sample_doc)
            
            if not usage_samples:
                continue
            
            # Calculate resource hours used
            vcpu_hours = 0.0
            ram_hours = 0.0
            disk_hours = 0.0
            
            for i in range(len(usage_samples) - 1):
                current_sample = usage_samples[i]
                next_sample = usage_samples[i + 1]

                time_diff = (next_sample["ts"] - current_sample["ts"]).total_seconds() / 3600.0
                
               
                vcpu_hours += (current_sample["cpu_pct"] / 100.0) * server["cores"] * time_diff
                ram_hours += (current_sample["ram_mib"] / 1024.0) * time_diff  # Convert MB to GB
                disk_hours += server["disk_gib"] * time_diff
            
            if vcpu_hours > 0:
                vcpu_amount = vcpu_hours * settings.vcpu_rate_per_core_hour
                line_items.append(LineItem(
                    kind="vCPU",
                    unit="core-hour",
                    quantity=round(vcpu_hours, 4),
                    rate=settings.vcpu_rate_per_core_hour,
                    amount=round(vcpu_amount, 4)
                ))
                total_amount += vcpu_amount
            
            if ram_hours > 0:
                ram_amount = ram_hours * settings.ram_rate_per_gib_hour
                line_items.append(LineItem(
                    kind="RAM",
                    unit="gib-hour",
                    quantity=round(ram_hours, 4),
                    rate=settings.ram_rate_per_gib_hour,
                    amount=round(ram_amount, 4)
                ))
                total_amount += ram_amount
            
            if disk_hours > 0:
                disk_amount = disk_hours * settings.disk_rate_per_gib_hour
                line_items.append(LineItem(
                    kind="Disk",
                    unit="gib-hour",
                    quantity=round(disk_hours, 4),
                    rate=settings.disk_rate_per_gib_hour,
                    amount=round(disk_amount, 4)
                ))
                total_amount += disk_amount
        
        # Create invoice
        invoice = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "period_start": request.period_start,
            "period_end": request.period_end,
            "line_items": [item.dict() for item in line_items],
            "subtotal": round(total_amount, 4),
            "total": round(total_amount, 4),  # No taxes for now
            "status": InvoiceStatus.DRAFT,
            "created_at": datetime.utcnow()
        }
        
       
        await db.invoices.insert_one(invoice)
        
        # Publish event in NATS
        await publish_invoice_generated(invoice["id"])
        
        return Invoice(**invoice)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate invoice: {str(e)}"
        )


@router.get("/invoices", response_model=List[Invoice])
async def list_invoices(
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """List all invoices for the current user"""
    invoices = []
    async for invoice_doc in db.invoices.find({"user_id": current_user.id}).sort("created_at", -1):
        invoices.append(Invoice(**invoice_doc))
    
    return invoices


@router.get("/invoices/{invoice_id}", response_model=Invoice)
async def get_invoice(
    invoice_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get a specific invoice"""
    invoice_doc = await db.invoices.find_one({
        "id": invoice_id,
        "user_id": current_user.id
    })
    
    if not invoice_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return Invoice(**invoice_doc)


@router.post("/invoices/{invoice_id}/pay", response_model=Transaction)
async def pay_invoice(
    invoice_id: str,
    method: TransactionMethod = TransactionMethod.CREDIT_CARD,
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Record a payment for an invoice (mock payment)"""
    # Get invoice
    invoice_doc = await db.invoices.find_one({
        "id": invoice_id,
        "user_id": current_user.id
    })
    
    if not invoice_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    invoice = Invoice(**invoice_doc)
    
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already paid"
        )
    
    try:

        transaction = TransactionInDB(
            invoice_id=invoice_id,
            amount=invoice.total,
            method=method
        )
        
        await db.transactions.insert_one(transaction.dict())
        

        await db.invoices.update_one(
            {"id": invoice_id},
            {"$set": {"status": InvoiceStatus.PAID}}
        )
        
        return Transaction(
            id=transaction.id,
            invoice_id=transaction.invoice_id,
            amount=transaction.amount,
            method=transaction.method,
            ts=transaction.ts
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process payment: {str(e)}"
        )
