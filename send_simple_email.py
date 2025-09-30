#!/usr/bin/env python3
"""
Simple Email Test Script
Tests basic email sending functionality via RabbitMQ to email microservice
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import os
import sys

import aio_pika
from aio_pika import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import crypto helper for password encryption
from crypto_helper import encrypt_smtp_password


class EmailServiceTester:
    """Simple email service tester using RabbitMQ"""

    def __init__(self):
        # Build RabbitMQ URL from environment variables
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")
        rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")

        self.rabbitmq_url = f"amqp://{rabbitmq_user}:{rabbitmq_password}@{rabbitmq_host}:{rabbitmq_port}/"
        self.queue_name = "email_queue"
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None

    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            print("= Connecting to RabbitMQ...")
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()

            # Use existing queue (avoid conflicts with queue settings)
            # Queue already exists with dead letter exchange configuration
            print(f" Connected to RabbitMQ, queue: {self.queue_name}")

        except Exception as e:
            print(f"L Failed to connect to RabbitMQ: {e}")
            raise

    async def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            print("= RabbitMQ connection closed")

    def create_email_job(
        self,
        to_emails: list[str],
        subject: str,
        body: str,
        body_html: str = "",
        smtp_config: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create email job payload following CLAUDE.md structure"""

        # SMTP configuration from environment
        smtp_password = os.getenv("SMTP_PASSWORD")

        # Encrypt SMTP password
        encrypted_password = encrypt_smtp_password(smtp_password)
        print(f"🔐 SMTP password encrypted (length: {len(encrypted_password)} chars)")

        default_smtp = {
            "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": os.getenv("SMTP_USER"),
            "password": encrypted_password,  # ✅ Encrypted password
            "from_name": "Email Service Test",
            "from_email": os.getenv("SMTP_USER"),  # Use same as user for Gmail
            "use_tls": True,
            "use_ssl": False,
            "timeout": 30
        }

        # Default metadata
        request_id = str(uuid.uuid4())
        default_metadata = {
            "source_app": "email-service-tester",
            "request_id": request_id,
            "queued_at": datetime.utcnow().isoformat() + "Z"
        }

        # Build email job
        email_job = {
            "email": {
                "to": to_emails,
                "subject": subject,
                "body": body,
                "priority": "normal"
            },
            "smtp": {**default_smtp, **(smtp_config or {})},
            "metadata": {**default_metadata, **(metadata or {})}
        }

        # Add HTML body if provided
        if body_html:
            email_job["email"]["body_html"] = body_html

        return email_job

    async def send_email_job(self, email_job: Dict[str, Any]) -> str:
        """Send email job to queue"""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")

        try:
            # Convert to JSON message
            message_body = json.dumps(email_job, indent=2)
            message = Message(
                message_body.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT  # Persistent message
            )

            # Send to queue
            await self.channel.default_exchange.publish(
                message,
                routing_key=self.queue_name
            )

            request_id = email_job["metadata"]["request_id"]
            print(f" Email job queued successfully!")
            print(f"=� Request ID: {request_id}")
            print(f"=� Recipients: {', '.join(email_job['email']['to'])}")
            print(f"=� Subject: {email_job['email']['subject']}")

            return request_id

        except Exception as e:
            print(f"L Failed to send email job: {e}")
            raise


async def test_simple_email():
    """Test sending a simple email"""
    print("=� Starting Simple Email Test")
    print("=" * 50)

    # Initialize tester
    tester = EmailServiceTester()

    try:
        # Connect to RabbitMQ
        await tester.connect()

        # Create simple email job
        print("=� Creating simple email job...")
        email_job = tester.create_email_job(
            to_emails=[os.getenv("TEST_EMAIL", "test@example.com")],
            subject="Test Email from Microservice",
            body="Hello! This is a test email from the email microservice.\n\nThis email was sent via RabbitMQ queue processing.",
            body_html="""
            <h2>Test Email from Microservice</h2>
            <p>Hello! This is a <strong>test email</strong> from the email microservice.</p>
            <p>This email was sent via RabbitMQ queue processing.</p>
            <hr>
            <small>Generated by email-service-tester</small>
            """
        )

        # Display email job details
        print("=� Email Job Details:")
        print(f"   To: {email_job['email']['to']}")
        print(f"   Subject: {email_job['email']['subject']}")
        print(f"   SMTP Host: {email_job['smtp']['host']}")
        print(f"   Source App: {email_job['metadata']['source_app']}")
        print()

        # Send email job
        print("=� Sending email job to queue...")
        request_id = await tester.send_email_job(email_job)

        print()
        print("<� Test completed successfully!")
        print(f"=� Track your email with Request ID: {request_id}")
        print()
        print("=� Next steps:")
        print("   1. Check email service logs for processing status")
        print("   2. Monitor database for email job status")
        print("   3. Check recipient inbox for delivered email")

    except Exception as e:
        print(f"=� Test failed: {e}")
        sys.exit(1)

    finally:
        # Clean up connection
        await tester.close()


def print_usage():
    """Print usage instructions"""
    print("=� Simple Email Test Script")
    print("=" * 30)
    print()
    print("This script sends a simple test email via the email microservice.")
    print()
    print("=' Environment Variables (optional):")
    print("   SMTP_USER        - SMTP username (default: your-email@gmail.com)")
    print("   SMTP_PASSWORD    - SMTP password (default: your-app-password)")
    print("   SMTP_FROM        - From email address (default: noreply@test.com)")
    print("   RABBITMQ_URL     - RabbitMQ connection URL")
    print()
    print("=� Example setup:")
    print("   export SMTP_USER='your-email@gmail.com'")
    print("   export SMTP_PASSWORD='your-app-password'")
    print("   export SMTP_FROM='noreply@yourapp.com'")
    print()
    print("=� Usage:")
    print("   python send_simple_email.py")
    print()


if __name__ == "__main__":
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
        sys.exit(0)

    # Run the test
    print(">� Email Service - Simple Email Test")
    print("=P", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print()

    # Check critical environment variables
    if not os.getenv("SMTP_USER") or not os.getenv("SMTP_PASSWORD"):
        print("�  Warning: SMTP credentials not set in environment variables")
        print("   The email will be queued but may fail to send without proper SMTP config")
        print()

    # Run async test
    asyncio.run(test_simple_email())