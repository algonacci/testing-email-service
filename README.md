# Email Service Testing Suite

This repository contains comprehensive test scripts for the Go-based email microservice. The tests validate various email scenarios including simple emails, multiple recipients, scheduled delivery, and bulk sending.

## 🚀 Quick Start

### Prerequisites

1. **Email Microservice**: Make sure the email service is running
2. **RabbitMQ Server**: Accessible RabbitMQ instance
3. **SMTP Access**: Valid SMTP credentials (Gmail configured)
4. **Python 3.13+**: With required dependencies

### Setup

1. **Install Dependencies**
   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install aio-pika python-dotenv
   ```

2. **Configure Environment**

   Create a `.env` file in the root directory:
   ```env
   # RabbitMQ Configuration
   RABBITMQ_HOST=103.59.160.126
   RABBITMQ_PORT=5672
   RABBITMQ_USER=admin
   RABBITMQ_PASSWORD=Admin12345.

   # SMTP Configuration (Gmail)
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=braincore.id@gmail.com
   SMTP_PASSWORD=ebeorigzhteulciz
   ```

3. **Verify Email Service**

   Ensure your email microservice is running and connected to:
   - Same RabbitMQ server
   - PostgreSQL database
   - Properly configured SMTP settings

## 📧 Test Scripts

### 1. Simple Email Test
**File**: `send_simple_email.py`

Tests basic email functionality with a single recipient.

```bash
python send_simple_email.py
```

**What it tests**:
- Single recipient email
- Plain text + HTML content
- Basic SMTP delivery
- RabbitMQ integration

---

### 2. Multiple Recipients Test
**File**: `send_multiple_recipients.py`

Tests various multi-recipient scenarios with different priorities.

```bash
python send_multiple_recipients.py
```

**What it tests**:
- Multiple TO recipients (3 users)
- TO + CC + BCC combinations (1 TO, 2 CC, 2 BCC)
- Large distribution list (10 subscribers)
- Different priority levels (normal, high, low)
- Custom headers and content types

---

### 3. Scheduled Email Test
**File**: `send_scheduled_email.py`

Tests email scheduling functionality for future delivery.

```bash
python send_scheduled_email.py
```

**What it tests**:
- 5-minute delayed email
- 1-hour delayed email
- Daily report (tomorrow 9 AM)
- Immediate email (comparison)
- Background scheduler integration

---

### 4. Bulk Email Test
**File**: `send_bulk_emails.py`

Tests bulk email sending with multiple job types in batches.

```bash
python send_bulk_emails.py
```

**What it tests**:
- Newsletter distribution (15 emails)
- Personalized promotions (8 emails)
- System notifications (9 emails)
- Batched sending with delays
- Individual job tracking

**⚠️ Warning**: This test sends ~32 emails. Ensure your SMTP provider can handle the load.

## 📊 Monitoring & Verification

### During Testing

1. **Console Output**: Each script provides detailed progress information
2. **Request IDs**: Track individual email jobs
3. **RabbitMQ Queue**: Monitor queue depth and message processing

### Email Service Logs

Watch for these log patterns:
```
✅ [DATABASE] Created email job: <uuid>
📅 [SCHEDULER] Email scheduled for <timestamp>, skipping for now
🔐 [SMTP] Trying STARTTLS for smtp.gmail.com
✅ [DATABASE] Updated job <uuid>: status=sent, attempts=1
```

### Database Queries

Check email job status:
```sql
-- Overall status distribution
SELECT status, COUNT(*) as count
FROM email_jobs
GROUP BY status;

-- Recent test results
SELECT id, subject, status, attempts, error_message, created_at
FROM email_jobs
WHERE source_service LIKE '%tester%'
ORDER BY created_at DESC
LIMIT 10;

-- Scheduled emails
SELECT id, subject, scheduled_at, status
FROM email_jobs
WHERE scheduled_at IS NOT NULL
AND status = 'pending'
ORDER BY scheduled_at ASC;
```

## 🛠️ Customization

### Modify Recipients

Edit the test scripts to use your own email addresses:

```python
# In any script, change:
to_emails=["test@example.com"]

# To:
to_emails=["your-email@domain.com"]
```

### Adjust Timing

For scheduled emails, modify the timing:

```python
# Change from 5 minutes to 30 seconds
scheduled_time_1 = datetime.utcnow() + timedelta(seconds=30)
```

### Bulk Email Volume

Reduce bulk email count for testing:

```python
# In send_bulk_emails.py, reduce the range:
for i in range(1, 6):  # Instead of range(1, 16)
```

## 🐛 Troubleshooting

### Common Issues

1. **Connection Refused**
   ```
   ❌ Failed to connect to RabbitMQ: ...
   ```
   - Verify RabbitMQ host/port in `.env`
   - Check network connectivity
   - Confirm RabbitMQ service is running

2. **SMTP Authentication Failed**
   ```
   ❌ SMTP authentication failed
   ```
   - Verify SMTP credentials in `.env`
   - For Gmail: Use App Passwords, not regular password
   - Check "Less secure app access" settings

3. **Emails Not Sending**
   ```
   Status remains 'pending' in database
   ```
   - Check email service logs for errors
   - Verify email service is consuming from correct queue
   - Check database connection in email service

4. **Scheduled Emails Not Processing**
   ```
   Scheduled emails stay 'pending' past scheduled time
   ```
   - Verify scheduler is running (check email service logs)
   - Check scheduled_at timestamps are in correct timezone (UTC)
   - Confirm database connectivity

### Debug Mode

Add debug output to scripts:
```python
# Add at the top of any script
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📋 Test Results

After running tests, you should see:

1. **Immediate Emails**: Processed within seconds
2. **Multiple Recipients**: All recipients receive emails
3. **Scheduled Emails**: Database records with future `scheduled_at`
4. **Bulk Emails**: All jobs queued, processed sequentially

### Expected Database State

```sql
-- Example results after running all tests
SELECT
    source_service,
    status,
    COUNT(*) as count
FROM email_jobs
WHERE source_service LIKE '%tester%'
GROUP BY source_service, status;

-- Sample output:
-- email-service-tester     | sent    | 1
-- multi-recipient-tester   | sent    | 3
-- scheduled-email-tester   | sent    | 1
-- scheduled-email-tester   | pending | 3
-- bulk-email-tester        | sent    | 32
```

## 🔄 Continuous Testing

For ongoing testing, create a simple runner:

```bash
#!/bin/bash
# test-runner.sh

echo "🧪 Running Email Service Tests"

echo "1️⃣ Simple Email Test"
python send_simple_email.py

sleep 5

echo "2️⃣ Multiple Recipients Test"
python send_multiple_recipients.py

sleep 10

echo "3️⃣ Scheduled Email Test"
python send_scheduled_email.py

echo "✅ All tests completed!"
```

## 📞 Support

If you encounter issues:

1. Check the email service documentation: `CLAUDE.md`
2. Verify environment configuration
3. Review email service logs
4. Check database connectivity and schema

---

**Happy Testing!** 🚀