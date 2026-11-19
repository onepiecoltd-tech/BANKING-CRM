#!/usr/bin/env python3
"""Push seeded customers to HubSpot contacts."""

import argparse
import time
from typing import Optional

import requests
from src.config import settings
from src.database import SessionLocal, Customer, IdentityGraph

HUBSPOT_API_BASE = "https://api.hubapi.com"


def make_hubspot_url(path: str, api_key: str) -> str:
    if api_key.startswith("hapikey-") or api_key.startswith("key-"):
        return f"{HUBSPOT_API_BASE}{path}?hapikey={api_key}"
    return f"{HUBSPOT_API_BASE}{path}"


def make_headers(api_key: str) -> dict:
    if api_key.startswith("hapikey-") or api_key.startswith("key-"):
        return {"Content-Type": "application/json"}
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }


def find_email_for_customer(session, customer: Customer) -> Optional[str]:
    email_record = session.query(IdentityGraph).filter_by(
        canonical_id=customer.customer_id,
        identifier_type="email"
    ).first()
    if email_record and email_record.identifier_value:
        return email_record.identifier_value

    safe_name = customer.name.lower().replace(" ", ".")
    return f"{safe_name}.{customer.customer_id.lower()}@example.com"


def find_phone_for_customer(session, customer: Customer) -> Optional[str]:
    phone_record = session.query(IdentityGraph).filter_by(
        canonical_id=customer.customer_id,
        identifier_type="mobile"
    ).first()
    if phone_record and phone_record.identifier_value:
        return phone_record.identifier_value
    return None


def search_contact_by_email(headers, api_key: str, email: str) -> Optional[str]:
    if not email:
        return None

    url = make_hubspot_url("/crm/v3/objects/contacts/search", api_key)
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email
                    }
                ]
            }
        ],
        "properties": ["email"]
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != 200:
        return None
    data = response.json()
    results = data.get("results", [])
    if not results:
        return None
    return results[0].get("id")


def create_or_update_contact(headers, api_key: str, customer: Customer, email: str, phone: Optional[str]):
    properties = {
        "email": email,
        "firstname": customer.name.split(" ", 1)[0],
        "lastname": customer.name.split(" ", 1)[1] if " " in customer.name else "",
        "phone": phone or "",
        "city": customer.city or "",
        "jobtitle": customer.occupation or "",
        "description": (
            f"Segment={customer.segment}; Income={customer.annual_income:.0f}; "
            f"CreditScore={customer.credit_score}; Balance={customer.monthly_avg_balance:.0f}; "
            f"Products=[{','.join([p for p, has in [('CC', customer.has_credit_card), ('PL', customer.has_personal_loan), ('HL', customer.has_home_loan), ('FD', customer.has_fd)] if has])}]"
        )
    }
    body = {"properties": properties}

    existing_id = search_contact_by_email(headers, api_key, email)
    if existing_id:
        url = make_hubspot_url(f"/crm/v3/objects/contacts/{existing_id}", api_key)
        response = requests.patch(url, headers=headers, json=body, timeout=30)
        action = "updated"
    else:
        url = make_hubspot_url("/crm/v3/objects/contacts", api_key)
        response = requests.post(url, headers=headers, json=body, timeout=30)
        action = "created"

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"HubSpot API error ({response.status_code}): {response.text}"
        )
    return action


def push_to_hubspot(limit: int):
    api_key = settings.hubspot_developer_key
    if not api_key:
        raise RuntimeError("HUBSPOT_DEVELOPER_KEY must be set in .env before pushing to HubSpot.")

    headers = make_headers(api_key)
    session = SessionLocal()
    pushed = 0
    skipped = 0
    try:
        customers = session.query(Customer).order_by(Customer.customer_id).limit(limit).all()
        for customer in customers:
            email = find_email_for_customer(session, customer)
            phone = find_phone_for_customer(session, customer)
            try:
                action = create_or_update_contact(headers, api_key, customer, email, phone)
                pushed += 1
                print(f"{customer.customer_id}: {action} contact {email}")
            except Exception as exc:
                skipped += 1
                print(f"{customer.customer_id}: skipped ({exc})")
            time.sleep(0.1)
    finally:
        session.close()

    print(f"\nFinished: pushed={pushed}, skipped={skipped}")


def parse_args():
    parser = argparse.ArgumentParser(description="Push seeded customer data to HubSpot contacts.")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum number of customers to push")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    push_to_hubspot(limit=args.limit)
