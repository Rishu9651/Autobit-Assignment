import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from app.database import connect_to_mongo, get_database
from app.config import settings
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Email template
EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AutoBit Weekly Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f4f4f4; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; }
        .server { background-color: #f9f9f9; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .billing { background-color: #e8f4f8; padding: 15px; border-radius: 5px; }
        .footer { margin-top: 30px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>AutoBit Weekly Report</h1>
        <p>Hello {{ user_name }},</p>
        <p>Here's your weekly server usage summary for {{ week_start }} to {{ week_end }}.</p>
    </div>

    <div class="section">
        <h2>Active Servers</h2>
        {% for server in servers %}
        <div class="server">
            <h3>{{ server.name }}</h3>
            <p><strong>Status:</strong> {{ server.status }}</p>
            <p><strong>Average CPU:</strong> {{ server.avg_cpu }}%</p>
            <p><strong>Average RAM:</strong> {{ server.avg_ram }} MB</p>
            <p><strong>Resources:</strong> {{ server.cores }} cores, {{ server.ram_gib }} GB RAM, {{ server.disk_gib }} GB Disk</p>
        </div>
        {% endfor %}
    </div>

    <div class="section">
        <div class="billing">
            <h2>Billing Summary</h2>
            <p><strong>Current Month Estimated Charges:</strong> ${{ estimated_charges }}</p>
            <p><strong>Latest Invoice:</strong> <a href="{{ invoice_link }}">View Invoice</a></p>
        </div>
    </div>

    <div class="footer">
        <p>This is an automated message from AutoBit. Please do not reply to this email.</p>
        <p>If you have any questions, please contact our support team.</p>
    </div>
</body>
</html>
"""

# Send an email using SMTP
async def send_email(to_email: str, subject: str, html_content: str):
    
    if not settings.smtp_username or not settings.smtp_password:
        logger.warning("SMTP not configured, printing email to console instead")
        print(f"\n=== EMAIL TO: {to_email} ===")
        print(f"SUBJECT: {subject}")
        print(f"CONTENT:\n{html_content}")
        print("=== END EMAIL ===\n")
        return True
    
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.smtp_from_email or settings.smtp_username
        message["To"] = to_email
        
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=settings.smtp_use_tls
        )
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def get_user_servers_with_usage(user_id: str, db, days: int = 7):
   
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    servers = []
    async for server_doc in db.servers.find({"user_id": user_id}):
        server_id = server_doc["id"]

        pipeline = [
            {
                "$match": {
                    "server_id": server_id,
                    "ts": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_cpu": {"$avg": "$cpu_pct"},
                    "avg_ram": {"$avg": "$ram_mib"},
                    "sample_count": {"$sum": 1}
                }
            }
        ]
        
        usage_stats = await db.usage_samples.aggregate(pipeline).to_list(1)
        
        server_info = {
            "name": server_doc["name"],
            "status": server_doc["status"],
            "cores": server_doc["cores"],
            "ram_gib": server_doc["ram_gib"],
            "disk_gib": server_doc["disk_gib"],
            "avg_cpu": round(usage_stats[0]["avg_cpu"], 2) if usage_stats else 0,
            "avg_ram": round(usage_stats[0]["avg_ram"], 2) if usage_stats else 0,
            "sample_count": usage_stats[0]["sample_count"] if usage_stats else 0
        }
        
        servers.append(server_info)
    
    return servers

# Calculate estimated charges for current month
async def calculate_estimated_charges(user_id: str, db):

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    
   
    servers = []
    async for server_doc in db.servers.find({"user_id": user_id}):
        servers.append(server_doc)
    
    total_charges = 0.0
    
    for server in servers:
        server_id = server["id"]
        
        usage_samples = []
        async for sample_doc in db.usage_samples.find({
            "server_id": server_id,
            "ts": {"$gte": month_start, "$lte": now}
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
            ram_hours += (current_sample["ram_mib"] / 1024.0) * time_diff
            disk_hours += server["disk_gib"] * time_diff
        

        vcpu_charges = vcpu_hours * settings.vcpu_rate_per_core_hour
        ram_charges = ram_hours * settings.ram_rate_per_gib_hour
        disk_charges = disk_hours * settings.disk_rate_per_gib_hour
        
        total_charges += vcpu_charges + ram_charges + disk_charges
    
    return round(total_charges, 4)


async def get_latest_invoice_link(user_id: str, db):
    latest_invoice = await db.invoices.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    )
    
    if latest_invoice:
        return f"http://localhost:8000/billing/invoices/{latest_invoice['id']}"
    else:
        return "http://localhost:8000/billing/invoices"


async def send_weekly_email(user_id: str, db):

    try:
       
        user = await db.users.find_one({"id": user_id})
        if not user:
            logger.error(f"User {user_id} not found")
            return False

        servers = await get_user_servers_with_usage(user_id, db)
        
        estimated_charges = await calculate_estimated_charges(user_id, db)

        invoice_link = await get_latest_invoice_link(user_id, db)

        now = datetime.utcnow()
        week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        week_end = now.strftime("%Y-%m-%d")
        

        template = Template(EMAIL_TEMPLATE)
        html_content = template.render(
            user_name=user["name"],
            week_start=week_start,
            week_end=week_end,
            servers=servers,
            estimated_charges=estimated_charges,
            invoice_link=invoice_link
        )
        

        subject = f"AutoBit Weekly Report - {week_start} to {week_end}"
        success = await send_email(user["email"], subject, html_content)
        
        if success:
            logger.info(f"Weekly email sent successfully to {user['email']}")
        else:
            logger.error(f"Failed to send weekly email to {user['email']}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error sending weekly email to user {user_id}: {e}")
        return False

# Email worker
async def weekly_email_worker():

    logger.info("Starting weekly email worker...")
    
    await connect_to_mongo()
    db = await get_database()
    
    while True:
        try:
            users = []
            async for user_doc in db.users.find():
                users.append(user_doc)
            
            logger.info(f"Sending weekly emails to {len(users)} users")
            tasks = []
            for user in users:
                task = send_weekly_email(user["id"], db)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful = sum(1 for result in results if result is True)
            logger.info(f"Weekly emails sent: {successful}/{len(users)} successful")

            await asyncio.sleep(7 * 24 * 60 * 60)  
            
        except Exception as e:
            logger.error(f"Error in weekly email worker: {e}")
            await asyncio.sleep(60 * 60) 


if __name__ == "__main__":
    asyncio.run(weekly_email_worker())
