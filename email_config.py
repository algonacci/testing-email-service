#!/usr/bin/env python3
"""
Email Recipients Configuration
Edit this file to customize test email recipients
"""

# 📧 Email addresses from environment
import os
from dotenv import load_dotenv
load_dotenv()

TEST_EMAIL = os.getenv("TEST_EMAIL", "test@example.com")

# For backward compatibility
TEST_EMAILS = {
    "primary": TEST_EMAIL,
    "secondary": TEST_EMAIL,
    "personal": TEST_EMAIL,
}

# 🧪 Simple Email Test Recipients
SIMPLE_EMAIL_RECIPIENTS = [
    TEST_EMAILS["primary"]  # Single recipient for basic test
]

# 👥 Multiple Recipients Test Configuration
MULTIPLE_RECIPIENTS_CONFIG = {
    # Test Case 1: Multiple TO recipients
    "test_case_1": {
        "to": [
            TEST_EMAILS["primary"],
            TEST_EMAILS["secondary"],
            TEST_EMAILS["personal"]
        ]
    },

    # Test Case 2: TO + CC + BCC
    "test_case_2": {
        "to": [TEST_EMAILS["primary"]],
        "cc": [TEST_EMAILS["secondary"]],
        "bcc": [TEST_EMAILS["personal"]]
    },

    # Test Case 3: Large distribution (newsletter simulation)
    "test_case_3": {
        "to": [
            TEST_EMAILS["primary"],    # You'll get 1 email but simulate 10
            # Add more emails here if you have them:
            # "friend1@domain.com",
            # "friend2@domain.com",
        ]
    }
}

# ⏰ Scheduled Email Test Recipients
SCHEDULED_EMAIL_RECIPIENTS = {
    "5_minute_delay": [TEST_EMAILS["primary"]],
    "1_hour_delay": [TEST_EMAILS["primary"], TEST_EMAILS["secondary"]],
    "tomorrow_9am": [TEST_EMAILS["primary"]],
    "immediate": [TEST_EMAILS["primary"]]
}

# 📦 Bulk Email Test Recipients
BULK_EMAIL_RECIPIENTS = {
    # Newsletter subscribers (will be duplicated for testing)
    "newsletter_base": [
        TEST_EMAILS["primary"],
        TEST_EMAILS["secondary"],
        TEST_EMAILS["personal"]
    ],

    # Promotional email recipients
    "promotion_recipients": [
        {"email": TEST_EMAILS["primary"], "name": "Your Name", "category": "Tech"},
        {"email": TEST_EMAILS["secondary"], "name": "Your Name 2", "category": "Books"},
        {"email": TEST_EMAILS["personal"], "name": "Your Name 3", "category": "Fashion"}
    ],

    # Admin notification recipients
    "admin_recipients": [
        TEST_EMAILS["primary"],    # Admin 1
        TEST_EMAILS["secondary"],  # Admin 2
        TEST_EMAILS["personal"]    # Admin 3
    ]
}

# 🔧 Helper Functions
def get_simple_recipients():
    """Get recipients for simple email test"""
    return SIMPLE_EMAIL_RECIPIENTS

def get_multiple_recipients_config():
    """Get configuration for multiple recipients test"""
    return MULTIPLE_RECIPIENTS_CONFIG

def get_scheduled_recipients():
    """Get recipients for scheduled email test"""
    return SCHEDULED_EMAIL_RECIPIENTS

def get_bulk_recipients():
    """Get recipients for bulk email test"""
    return BULK_EMAIL_RECIPIENTS

def generate_newsletter_list(base_emails, count=15):
    """Generate a list of newsletter recipients by cycling through base emails"""
    if not base_emails:
        return []

    newsletter_list = []
    for i in range(count):
        # Cycle through base emails
        base_email = base_emails[i % len(base_emails)]
        # Add a number to make it unique for testing
        if "@" in base_email:
            local, domain = base_email.split("@", 1)
            unique_email = f"{local}+newsletter{i+1:02d}@{domain}"
        else:
            unique_email = f"{base_email}+{i+1:02d}"

        newsletter_list.append(unique_email)

    return newsletter_list

def print_config_summary():
    """Print a summary of current email configuration"""
    print("📧 Email Configuration Summary")
    print("=" * 40)
    print(f"All emails directed to: {TEST_EMAILS['primary']}")
    print()
    print("🧪 Test Scripts:")
    print(f"  Simple Test: {len(SIMPLE_EMAIL_RECIPIENTS)} recipient(s)")
    print(f"  Multiple Recipients: 3 test cases")
    print(f"  Scheduled Emails: 4 timing scenarios")
    print(f"  Bulk Emails: ~32 total emails")
    print()
    print("💡 To customize: Edit email_config.py and update TEST_EMAILS")

if __name__ == "__main__":
    print_config_summary()