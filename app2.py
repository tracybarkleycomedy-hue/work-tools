import io
import json
from datetime import datetime
from pathlib import Path

import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer


st.set_page_config(page_title="Outbound Chargeback Response Generator", layout="wide")


# -------------------------------
# Helpers
# -------------------------------
def yes_no(value: str) -> str:
    return "Yes" if value == "Yes" else "No"


def strength_score(data: dict) -> tuple[int, str, list[str]]:
    score = 0
    notes = []

    if data["terms_accepted"] == "Yes":
        score += 2
        notes.append("terms accepted")
    if data["checkout_proof"] == "Yes":
        score += 2
        notes.append("checkout proof available")
    if data["kickoff_completed"] == "Yes":
        score += 2
        notes.append("kickoff completed")
    if data["work_started"] == "Yes":
        score += 2
        notes.append("service work began")
    if data["onboarding_emails_sent"] == "Yes":
        score += 1
        notes.append("onboarding emails sent")
    if data["refund_offered"] == "Yes":
        score += 1
        notes.append("good-faith refund offered")
    if data["refund_attempted"] == "Yes":
        score += 1
        notes.append("refund attempted")
    if data["refund_failed"] == "Yes":
        score += 1
        notes.append("refund blocked or failed")
    if data["client_requested_refund"] == "Yes":
        score += 1
        notes.append("client requested refund before dispute")
    if data["cancellation_submitted"] == "No":
        score += 1
        notes.append("no cancellation submitted")
    if data["proposal_sent"] == "Yes":
        score += 1
        notes.append("proposal/service outline sent")

    if score >= 11:
        label = "Strong"
    elif score >= 7:
        label = "Moderate"
    else:
        label = "Weak"

    return score, label, notes


def evidence_checklist(data: dict) -> list[str]:
    items = []
    if data["checkout_proof"] == "Yes":
        items.append("Checkout confirmation / secure payment record")
    if data["terms_accepted"] == "Yes":
        items.append("Terms and conditions acceptance proof")
    if data["proposal_sent"] == "Yes":
        items.append("Proposal / service outline")
    if data["kickoff_completed"] == "Yes":
        items.append("Kickoff call recording and/or transcript")
    if data["onboarding_emails_sent"] == "Yes":
        items.append("Onboarding / launch emails")
    if data["work_started"] == "Yes":
        items.append("Proof services began")
    if data["refund_offered"] == "Yes":
        items.append("Refund offer communication")
    if data["refund_attempted"] == "Yes":
        items.append("Refund attempt proof")
    if data["refund_failed"] == "Yes":
        items.append("Evidence refund was rejected/blocked")
    if data["other_evidence"].strip():
        items.append(data["other_evidence"].strip())
    if data.get("image_names"):
        for idx, name in enumerate(data["image_names"], start=1):
            items.append(f"Screenshot {idx}: {name}")
    return items


def generate_timeline(data: dict) -> list[tuple[str, str]]:
    timeline = []

    if data["signup_date"]:
        timeline.append((data["signup_date"], f"Client signed up for {data['company_name']} services and entered payment details through secure checkout."))
    if data["kickoff_date"]:
        timeline.append((data["kickoff_date"], "Kickoff call occurred and service onboarding began." if data["kickoff_completed"] == "Yes" else "Kickoff was scheduled / referenced in onboarding process."))
    if data["charge_date"]:
        timeline.append((data["charge_date"], f"Charge for ${data['dispute_amount']} was processed in accordance with the agreed billing terms."))
    if data["client_complaint_date"]:
        timeline.append((data["client_complaint_date"], "Client contacted the company regarding the charge or expressed dissatisfaction."))
    if data["refund_offer_date"] and data["refund_offered"] == "Yes":
        timeline.append((data["refund_offer_date"], "Company offered a good-faith resolution and/or refund-related option."))
    if data["refund_attempt_date"] and data["refund_attempted"] == "Yes":
        timeline.append((data["refund_attempt_date"], "Company attempted to process a refund."))
    if data["dispute_date"]:
        timeline.append((data["dispute_date"], "Client filed a chargeback/dispute with the card issuer."))

    return timeline


def generate_response_letter(data: dict) -> str:
    evidence_items = evidence_checklist(data)
    timeline = generate_timeline(data)
    score, label, notes = strength_score(data)

    amount = data["dispute_amount"] or "0"
    client = data["client_name"] or "Client"
    merchant = data["company_name"] or "Outbound Consulting"
    reason = data["dispute_reason"] or "Not specified"
    dispute_id = data["dispute_id"] or "Not provided"
    term = data["contract_term"] or "120-day consulting term"
    payment_type = data["payment_type"]
    rate = data["rate_details"] or "Per agreement"

    intro = f"""Credit Card Dispute Response

Case Details
Disputed Amount: USD ${amount}
Disputer: {client}
Merchant: {merchant}
Dispute Reference: {dispute_id}
Reason for Dispute: {reason}

Comprehensive Response to Dispute
"""

    background = f"""Transaction Background
On {data['signup_date'] or '[signup date]'}, {client} entered into a services agreement with {merchant} under the following terms:

- Service Agreement: {term}
- Payment Structure: {payment_type}
- Rate / Billing Details: {rate}
- Billing Policy: {data['billing_policy'] or 'Per signed agreement / checkout terms'}
- Additional Service Context: {data['service_description'] or 'Professional consulting services'}
"""

    payment_confirmation = f"""Payment Confirmation
The client completed payment through the company's secure checkout process and {( 'accepted' if data['terms_accepted'] == 'Yes' else 'was presented with')} the applicable terms and conditions.

- Terms accepted: {yes_no(data['terms_accepted'])}
- Checkout proof available: {yes_no(data['checkout_proof'])}
- Proposal/service outline sent: {yes_no(data['proposal_sent'])}
- Onboarding emails sent: {yes_no(data['onboarding_emails_sent'])}
"""

    invalid_reasons = [
        "Services were initiated and/or performed.",
        "The client authorized the transaction during checkout.",
        "The charge followed the agreed billing structure.",
    ]

    if data["kickoff_completed"] == "Yes":
        invalid_reasons.append("The kickoff call occurred before or in connection with billing, showing service commencement.")
    if data["work_started"] == "Yes":
        invalid_reasons.append("Work had already begun before the dispute was filed.")
    if data["cancellation_submitted"] == "No":
        invalid_reasons.append("No valid cancellation was submitted before the dispute.")
    if data["refund_offered"] == "Yes":
        invalid_reasons.append("The company attempted to resolve the matter in good faith before or around the dispute.")
    if data["refund_attempted"] == "Yes":
        invalid_reasons.append("A refund attempt was made, which contradicts an allegation of unauthorized or bad-faith billing.")

    dispute_section = "Reason the Dispute Should Be Denied\n" + "\n".join(f"- {item}" for item in invalid_reasons)
    timeline_section = "Timeline of Events\n" + "\n".join(f"- {date}: {event}" for date, event in timeline)

    good_faith_section = f"""Good-Faith Resolution Efforts
- Refund offered: {yes_no(data['refund_offered'])}
- Refund attempted: {yes_no(data['refund_attempted'])}
- Refund failed/rejected: {yes_no(data['refund_failed'])}
- Client requested refund before dispute: {yes_no(data['client_requested_refund'])}
"""

    proof_section = "Proof of Services / Supporting Evidence\n" + "\n".join(f"- {item}" for item in evidence_items)

    summary = f"""Summary of Why the Dispute Should Be Reversed
- The transaction was authorized.
- The client accepted or was presented with the relevant terms during checkout.
- The company has documentation showing service initiation and/or performance.
- The billing followed the agreed structure and timeline.
- The company took good-faith steps to resolve the issue.
- Internal case strength assessment: {label} ({score}/14) based on {', '.join(notes) if notes else 'standard documentation'}.
"""

    requested_resolution = """Requested Resolution
We respectfully request that this chargeback be reversed and that the transaction be upheld. We are prepared to provide any additional supporting documentation upon request.
"""

    appendix = "Appendix / Suggested Attachments\n" + "\n".join(f"- {item}" for item in evidence_items)

    if data.get("image_names"):
        appendix += "\n\nScreenshots Included\n"
        for idx, name in enumerate(data["image_names"], start=1):
            appendix += f"- Screenshot {idx}: {name}\n"

    if data["custom_case_notes"].strip():
        appendix += f"\nAdditional Case Notes\n{data['custom_case_notes'].strip()}"

    sections = [
        intro,
        background,
        payment_confirmation,
        dispute_section,
        timeline_section,
        good_faith_section,
        proof_section,
        summary,
        requested_resolution,
        appendix,
    ]

    return "\n\n".join(sections)


def generate_client_email(data: dict) -> str:
    client = data["client_name"] or "there"
    amount = data["dispute_amount"] or "0"

    return f"""Hi {client},

I’m reaching out regarding the disputed charge for ${amount}.

Based on our records, the charge was processed in accordance with the agreement accepted during checkout, and service work had already begun. We also took good-faith steps to address the issue directly.

If you would still like to resolve this outside of the card dispute process, please reply and let us know. We would prefer to resolve matters directly where possible.

Best,
Tracy Barkley
{data['company_name'] or 'Outbound Consulting'}
"""


def generate_pdf(response_text: str, uploaded_files: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []

    for raw_line in response_text.split("\n"):
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 8))
            continue

        safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        style = styles["Heading2"] if not line.startswith("-") and len(line) < 60 and ":" not in line and line == line.title() else styles["Normal"]
        story.append(Paragraph(safe_line, style))
        story.append(Spacer(1, 6))

    if uploaded_files:
        story.append(Spacer(1, 18))
        story.append(Paragraph("Appendix Screenshots", styles["Heading2"]))
        story.append(Spacer(1, 10))

        for idx, file in enumerate(uploaded_files, start=1):
            try:
                file.seek(0)
                img_reader = ImageReader(file)
                img_width, img_height = img_reader.getSize()
                max_width = 500
                max_height = 350
                scale = min(max_width / img_width, max_height / img_height, 1)
                display_width = img_width * scale
                display_height = img_height * scale
                file.seek(0)
                story.append(Paragraph(f"Screenshot {idx}: {file.name}", styles["Normal"]))
                story.append(Spacer(1, 6))
                story.append(Image(file, width=display_width, height=display_height))
                story.append(Spacer(1, 14))
            except Exception:
                story.append(Paragraph(f"Screenshot {idx}: {file.name} (unable to embed)", styles["Normal"]))
                story.append(Spacer(1, 10))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# -------------------------------
# Session state
# -------------------------------
if "submitted" not in st.session_state:
    st.session_state.submitted = False


# -------------------------------
# Header
# -------------------------------
header = st.container()
with header:
    logo_col, title_col = st.columns([1, 6])
    with logo_col:
        logo_path = Path("outbound_logo.png")
        if logo_path.exists():
            st.image(str(logo_path), width=80)
    with title_col:
        st.markdown("## Outbound Chargeback Response Generator")
        st.markdown(
            "<span style='color:#7AD7F0;font-size:16px;'>Generate structured chargeback response letters, timelines, evidence checklists, screenshots, and appendix-ready PDFs.</span>",
            unsafe_allow_html=True,
        )

st.markdown("---")


# -------------------------------
# Form
# -------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Case Details")
    client_name = st.text_input("Client Name")
    company_name = st.text_input("Merchant / Company Name", value="Outbound Consulting")
    dispute_amount = st.text_input("Disputed Amount", placeholder="6790")
    dispute_id = st.text_input("Dispute Reference")
    dispute_reason = st.selectbox(
        "Dispute Reason",
        ["Unauthorized", "Fraud", "Service Not Received", "Cancelled Recurring", "Other"],
    )
    payment_type = st.selectbox(
        "Payment Type",
        ["Monthly", "Upfront Discounted Plan", "Deposit + Autodraft", "Other"],
    )
    contract_term = st.text_input("Contract Term", value="120-day consulting contract")
    rate_details = st.text_input("Rate / Billing Details", value="USD $2,000 per month + applicable credit card processing fees")
    service_description = st.text_area(
        "Service Description",
        value="Consulting services to identify and validate target audience and warm the sales funnel.",
        height=100,
    )
    billing_policy = st.text_input(
        "Billing Policy",
        value="First bill drafts within 24 hours of the kickoff call per the signed terms.",
    )

with right:
    st.subheader("Timeline and Evidence")
    signup_date = st.text_input("Signup Date", placeholder="Feb 12, 2026")
    kickoff_date = st.text_input("Kickoff Date", placeholder="Feb 17, 2026")
    charge_date = st.text_input("Charge Date", placeholder="Feb 18, 2026")
    client_complaint_date = st.text_input("Client Complaint Date", placeholder="Feb 20, 2026")
    refund_offer_date = st.text_input("Refund Offer Date", placeholder="Feb 20, 2026")
    refund_attempt_date = st.text_input("Refund Attempt Date", placeholder="Feb 20, 2026")
    dispute_date = st.text_input("Dispute Filed Date", placeholder="[date]")

    terms_accepted = st.radio("Terms Accepted?", ["Yes", "No"], horizontal=True)
    checkout_proof = st.radio("Checkout Proof Available?", ["Yes", "No"], horizontal=True)
    proposal_sent = st.radio("Proposal / Service Outline Sent?", ["Yes", "No"], horizontal=True)
    onboarding_emails_sent = st.radio("Onboarding Emails Sent?", ["Yes", "No"], horizontal=True)
    kickoff_completed = st.radio("Kickoff Completed?", ["Yes", "No"], horizontal=True)
    work_started = st.radio("Work Started?", ["Yes", "No"], horizontal=True)
    client_requested_refund = st.radio("Client Requested Refund Before Dispute?", ["Yes", "No"], horizontal=True)
    refund_offered = st.radio("Refund Offered?", ["Yes", "No"], horizontal=True)
    refund_attempted = st.radio("Refund Attempted?", ["Yes", "No"], horizontal=True)
    refund_failed = st.radio("Refund Failed / Rejected?", ["Yes", "No"], horizontal=True)
    cancellation_submitted = st.radio("Client Submitted Cancellation?", ["Yes", "No"], horizontal=True)

st.subheader("Supporting Evidence Uploads")
uploaded_files = st.file_uploader(
    "Upload screenshots / evidence images",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

st.subheader("Additional Notes")
other_evidence = st.text_input("Other Evidence to Reference")
custom_case_notes = st.text_area("Custom Case Notes", height=120)

if st.button("🚀 Generate Chargeback Response", type="primary", use_container_width=True):
    st.session_state.submitted = True


# -------------------------------
# Output
# -------------------------------
if st.session_state.submitted:
    image_names = [file.name for file in uploaded_files] if uploaded_files else []

    form_data = {
        "client_name": client_name,
        "company_name": company_name,
        "dispute_amount": dispute_amount,
        "dispute_id": dispute_id,
        "dispute_reason": dispute_reason,
        "payment_type": payment_type,
        "contract_term": contract_term,
        "rate_details": rate_details,
        "service_description": service_description,
        "billing_policy": billing_policy,
        "signup_date": signup_date,
        "kickoff_date": kickoff_date,
        "charge_date": charge_date,
        "client_complaint_date": client_complaint_date,
        "refund_offer_date": refund_offer_date,
        "refund_attempt_date": refund_attempt_date,
        "dispute_date": dispute_date,
        "terms_accepted": terms_accepted,
        "checkout_proof": checkout_proof,
        "proposal_sent": proposal_sent,
        "onboarding_emails_sent": onboarding_emails_sent,
        "kickoff_completed": kickoff_completed,
        "work_started": work_started,
        "client_requested_refund": client_requested_refund,
        "refund_offered": refund_offered,
        "refund_attempted": refund_attempted,
        "refund_failed": refund_failed,
        "cancellation_submitted": cancellation_submitted,
        "other_evidence": other_evidence,
        "custom_case_notes": custom_case_notes,
        "image_names": image_names,
    }

    response_letter = generate_response_letter(form_data)
    client_email = generate_client_email(form_data)
    timeline = generate_timeline(form_data)
    evidence = evidence_checklist(form_data)
    score, label, notes = strength_score(form_data)
    pdf_bytes = generate_pdf(response_letter, uploaded_files or [])

    st.divider()
    st.markdown("## Case Summary")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Case Strength", label)
    with m2:
        st.metric("Strength Score", score)
    with m3:
        st.metric("Evidence Items", len(evidence))

    tabs = st.tabs([
        "Response Letter",
        "Timeline",
        "Evidence Checklist",
        "Screenshots",
        "Strength Notes",
        "Client Email",
    ])

    with tabs[0]:
        st.text(response_letter)

    with tabs[1]:
        if timeline:
            for date, event in timeline:
                st.write(f"**{date}** — {event}")
        else:
            st.info("No timeline details entered yet.")

    with tabs[2]:
        if evidence:
            for item in evidence:
                st.write(f"- {item}")
        else:
            st.info("No evidence items identified yet.")

    with tabs[3]:
        if uploaded_files:
            for idx, file in enumerate(uploaded_files, start=1):
                st.image(file, caption=f"Screenshot {idx}: {file.name}", use_container_width=True)
        else:
            st.info("No screenshots uploaded.")

    with tabs[4]:
        st.write(f"**Case Strength:** {label} ({score}/14)")
        if notes:
            for note in notes:
                st.write(f"- {note}")

    with tabs[5]:
        st.text(client_email)

    st.divider()
    safe_name = (client_name.strip().replace(" ", "_") or "client")
    export_col1, export_col2 = st.columns(2)

    with export_col1:
        st.download_button(
            label="📄 Download Response Letter",
            data=response_letter,
            file_name=f"chargeback_response_{safe_name}_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
        )

    with export_col2:
        json_export = json.dumps(form_data, indent=2)
        st.download_button(
            label="📥 Download Case JSON",
            data=json_export,
            file_name=f"chargeback_case_{safe_name}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
        )

    export_col3, export_col4 = st.columns(2)

    with export_col3:
        st.download_button(
            label="📎 Download PDF with Appendix Screenshots",
            data=pdf_bytes,
            file_name=f"chargeback_packet_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
        )

    with export_col4:
        appendix_text = "Appendix\n\n"
        for idx, item in enumerate(evidence, start=1):
            appendix_text += f"{idx}. {item}\n"
        st.download_button(
            label="📋 Download Appendix List",
            data=appendix_text,
            file_name=f"appendix_{safe_name}_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
        )
