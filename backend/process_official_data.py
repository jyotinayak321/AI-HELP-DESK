"""
process_official_data.py — Official PDF → Seed Data Pipeline
==============================================================
Reads an official IT helpdesk PDF log (textual, not scanned), extracts
structured ticket data (Application Names, Subjects, Queries), strips
embedded HTML tags, deduplicates, and optionally calls the local Gemma
model (via vLLM) to auto-generate Application Purposes.

Outputs a file called `official_seed_data.json` in the exact same format
as `dummy_seed_data.json`, ready to be consumed by `seed_db.py`.

Usage:
    python process_official_data.py <path_to_pdf>

    Options:
        --generate-purposes   Call the local Gemma model to auto-generate
                              application purpose descriptions. Requires
                              the vLLM server to be running.
        --output <filename>   Output filename (default: official_seed_data.json)

Examples:
    # Extract only (no LLM needed — fast, offline)
    python process_official_data.py official_log.pdf

    # Extract + auto-generate purposes via local Gemma
    python process_official_data.py official_log.pdf --generate-purposes
"""

import argparse
import json
import logging
import os
import re
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# =========================================================================
# STEP 1: PDF Text Extraction
# =========================================================================

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a textual PDF file using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        logger.error(
            "pdfplumber is not installed. Install it with:\n"
            "  pip install pdfplumber\n"
            "Or use the wheel from the wheels/ folder."
        )
        sys.exit(1)

    if not os.path.exists(pdf_path):
        logger.error("PDF file not found: %s", pdf_path)
        sys.exit(1)

    logger.info("Opening PDF: %s", pdf_path)
    all_text = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        logger.info("Total pages: %d", total_pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                all_text.append(text)
            if (i + 1) % 20 == 0:
                logger.info("  Processed %d / %d pages...", i + 1, total_pages)

    full_text = "\n".join(all_text)
    logger.info(
        "Extracted %d characters of text from %d pages.",
        len(full_text), total_pages,
    )
    return full_text


# =========================================================================
# STEP 2: HTML Stripping
# =========================================================================

def strip_html(text: str) -> str:
    """
    Remove HTML tags, &nbsp; entities, and other markup from text.
    Falls back to regex if BeautifulSoup is not available.
    """
    if not text:
        return ""

    # First pass: decode common HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')

    # Try BeautifulSoup for robust HTML stripping
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        cleaned = soup.get_text(separator=" ")
    except ImportError:
        # Fallback: regex-based HTML tag removal
        cleaned = re.sub(r"<[^>]+>", " ", text)

    # Collapse multiple whitespace into single spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


# =========================================================================
# STEP 3: Ticket Parsing
# =========================================================================

def parse_tickets(full_text: str) -> list[dict]:
    """
    Parse the extracted PDF text into structured ticket records.

    Looks for patterns like:
        Issue ID    Application Name    Mode of Communication    Raised ON
        <id>        <app_name>          <mode>                   <date>
        Subject: <subject>
        Query: <query_text>

    Returns a list of dicts:
        [{"issue_id": "...", "application": "...", "subject": "...", "query": "..."}, ...]
    """
    tickets = []

    # Strategy: Split by "Issue ID" or "IssueID" boundaries, then parse each block
    # We use a flexible regex that catches common OCR/PDF variations
    blocks = re.split(
        r"(?:Issue\s*ID|IssueID|Issve\s*ID)",
        full_text,
        flags=re.IGNORECASE,
    )

    logger.info("Found %d potential ticket blocks.", len(blocks) - 1)

    for block in blocks[1:]:  # Skip the first chunk (before the first Issue ID)
        ticket = {}

        # Extract Issue ID (first number-like token on the line)
        id_match = re.search(r"^\s*[:\s]*(\d+)", block)
        if id_match:
            ticket["issue_id"] = id_match.group(1).strip()

        # Extract Application Name
        # Usually appears right after the issue ID on the same line
        app_match = re.search(
            r"(\d+)\s+(.+?)(?:Web|Email|Phone|Mobile|Telephone|Mode)",
            block,
            re.IGNORECASE,
        )
        if app_match:
            ticket["application"] = app_match.group(2).strip()
        else:
            # Fallback: try "ApplicationName" header pattern
            app_match2 = re.search(
                r"Application\s*(?:Name|name)\s*[:\s]+(.+?)(?:\n|Mode|Raised)",
                block,
                re.IGNORECASE,
            )
            if app_match2:
                ticket["application"] = app_match2.group(1).strip()

        # Extract Subject
        subj_match = re.search(
            r"Subject\s*[:\s]+(.+?)(?:Query|Raised|$)",
            block,
            re.IGNORECASE | re.DOTALL,
        )
        if subj_match:
            ticket["subject"] = strip_html(subj_match.group(1).strip())

        # Extract Query
        query_match = re.search(
            r"Query\s*[:\s]+(.+?)(?:Raised\s*(?:By|by)|$)",
            block,
            re.IGNORECASE | re.DOTALL,
        )
        if query_match:
            ticket["query"] = strip_html(query_match.group(1).strip())

        # Only keep tickets that have at minimum an application name and
        # either a subject or a query
        if ticket.get("application") and (ticket.get("subject") or ticket.get("query")):
            tickets.append(ticket)

    logger.info("Successfully parsed %d valid tickets.", len(tickets))
    return tickets


# =========================================================================
# STEP 4: Group tickets by application & build symptom list
# =========================================================================

def group_by_application(tickets: list[dict]) -> dict[str, list[str]]:
    """
    Group tickets by application name and collect unique symptoms.
    Symptoms are derived from the Subject and Query fields.

    Returns: {"E-Office": ["symptom 1", "symptom 2", ...], ...}
    """
    app_symptoms: dict[str, list[str]] = {}

    for ticket in tickets:
        app_name = ticket["application"].strip()
        # Normalise app name: strip trailing/leading whitespace, collapse spaces
        app_name = re.sub(r"\s+", " ", app_name)

        if app_name not in app_symptoms:
            app_symptoms[app_name] = []

        # Use Subject as the primary symptom (it's the concise summary)
        if ticket.get("subject"):
            symptom = ticket["subject"]
            if symptom and symptom not in app_symptoms[app_name]:
                app_symptoms[app_name].append(symptom)

        # Also use the Query if it adds meaningful detail beyond the Subject
        if ticket.get("query"):
            query_symptom = ticket["query"]
            # Only add query if it's substantially different from the subject
            if (
                query_symptom
                and len(query_symptom) > 15
                and query_symptom not in app_symptoms[app_name]
            ):
                app_symptoms[app_name].append(query_symptom)

    logger.info(
        "Grouped into %d unique applications with %d total symptoms.",
        len(app_symptoms),
        sum(len(v) for v in app_symptoms.values()),
    )
    return app_symptoms


# =========================================================================
# STEP 5: (Optional) Generate Application Purposes via Local Gemma
# =========================================================================

def generate_purposes_via_llm(
    app_symptoms: dict[str, list[str]],
) -> dict[str, str]:
    """
    Call the local vLLM (Gemma) server to auto-generate a one-sentence
    purpose description for each application, based on its historical
    ticket symptoms.

    Returns: {"E-Office": "E-Office is a digital document ...", ...}
    """
    logger.info("Generating application purposes via local Gemma model...")

    # Import config to get vLLM endpoint details
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from config import settings
    except ImportError:
        logger.error(
            "Cannot import config.py. Make sure you are running this "
            "script from the backend/ directory."
        )
        sys.exit(1)

    try:
        import openai
    except ImportError:
        logger.error(
            "openai package not installed. Install with:\n"
            "  pip install openai"
        )
        sys.exit(1)

    client = openai.OpenAI(
        base_url=settings.VLLM_API_URL,
        api_key=settings.VLLM_API_KEY,
    )

    purposes: dict[str, str] = {}

    for app_name, symptoms in app_symptoms.items():
        # Take up to 10 representative symptoms to keep the prompt short
        sample = symptoms[:10]
        symptoms_text = "\n".join(f"- {s}" for s in sample)

        system_prompt = (
            "You are an IT systems expert. Based on the application name and "
            "a sample of historical IT support tickets for that application, "
            "write a single, clear, concise sentence describing what this "
            "application is used for (its core purpose). "
            "Reply with ONLY the one sentence, nothing else."
        )

        user_prompt = (
            f"Application Name: {app_name}\n\n"
            f"Sample support tickets:\n{symptoms_text}\n\n"
            f"What is the purpose of '{app_name}'?"
        )

        try:
            response = client.chat.completions.create(
                model=settings.VLLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=128,
            )
            purpose = response.choices[0].message.content.strip()
            # Remove surrounding quotes if the model wraps the response
            purpose = purpose.strip('"').strip("'")
            purposes[app_name] = purpose
            logger.info("  ✅ %s → %s", app_name, purpose)

        except Exception as e:
            logger.warning("  ❌ Failed to generate purpose for '%s': %s", app_name, e)
            purposes[app_name] = f"{app_name} application."

    return purposes


# =========================================================================
# STEP 6: Build the Final JSON (same format as dummy_seed_data.json)
# =========================================================================

def build_seed_json(
    app_symptoms: dict[str, list[str]],
    purposes: dict[str, str] | None = None,
) -> dict:
    """
    Build a JSON structure identical to dummy_seed_data.json.

    The JSON contains:
      - applications: [{id, name, description, owning_team, contact}, ...]
      - application_purposes: [{application_id, purpose_text}, ...]
      - application_symptoms: [{application_id, symptom_text}, ...]
      - classification_configs: (copied from dummy data — these are universal)
      - user_roles: (copied from dummy data — these are org-specific)
      - application_dependencies: [] (empty — can be filled manually later)
    """
    # Load the existing dummy data to copy over classification_configs and user_roles
    dummy_path = os.path.join(os.path.dirname(__file__), "dummy_seed_data.json")
    classification_configs = []
    user_roles = []
    if os.path.exists(dummy_path):
        with open(dummy_path, "r", encoding="utf-8") as f:
            dummy = json.load(f)
        classification_configs = dummy.get("classification_configs", [])
        user_roles = dummy.get("user_roles", [])

    # Build applications list
    applications = []
    app_id_map: dict[str, int] = {}
    for idx, app_name in enumerate(sorted(app_symptoms.keys()), start=1):
        app_id_map[app_name] = idx
        applications.append({
            "id": idx,
            "name": app_name,
            "description": purposes.get(app_name, "") if purposes else "",
            "owning_team": None,
            "contact": None,
        })

    # Build application_symptoms list
    symptom_list = []
    for app_name, symptoms in app_symptoms.items():
        app_id = app_id_map[app_name]
        for symptom in symptoms:
            symptom_list.append({
                "application_id": app_id,
                "symptom_text": symptom,
            })

    # Build application_purposes list
    purpose_list = []
    if purposes:
        for app_name, purpose_text in purposes.items():
            if purpose_text:
                app_id = app_id_map.get(app_name)
                if app_id:
                    purpose_list.append({
                        "application_id": app_id,
                        "purpose_text": purpose_text,
                    })

    seed_data = {
        "applications": applications,
        "application_purposes": purpose_list,
        "application_symptoms": symptom_list,
        "application_dependencies": [],  # Fill manually if needed
        "classification_configs": classification_configs,
        "user_roles": user_roles,
    }

    return seed_data


# =========================================================================
# MAIN
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Process official IT helpdesk PDF into seed data JSON.",
    )
    parser.add_argument(
        "pdf_path",
        help="Path to the official IT helpdesk PDF file.",
    )
    parser.add_argument(
        "--generate-purposes",
        action="store_true",
        default=False,
        help=(
            "Call the local Gemma model (via vLLM) to auto-generate "
            "application purpose descriptions. Requires the vLLM server."
        ),
    )
    parser.add_argument(
        "--output",
        default="official_seed_data.json",
        help="Output filename (default: official_seed_data.json).",
    )

    args = parser.parse_args()

    # Step 1: Extract text
    full_text = extract_text_from_pdf(args.pdf_path)

    # Step 2 & 3: Parse tickets (HTML stripping happens inside parse_tickets)
    tickets = parse_tickets(full_text)

    if not tickets:
        logger.error(
            "No tickets could be parsed from the PDF. The document format "
            "may not match the expected structure. Please check the PDF "
            "and adjust the parsing patterns in this script if needed."
        )
        # Save raw text for debugging
        debug_path = os.path.join(os.path.dirname(__file__), "pdf_raw_text_debug.txt")
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        logger.info(
            "Raw extracted text saved to %s for debugging.", debug_path
        )
        sys.exit(1)

    # Step 4: Group by application
    app_symptoms = group_by_application(tickets)

    # Step 5: (Optional) Generate purposes via LLM
    purposes = None
    if args.generate_purposes:
        purposes = generate_purposes_via_llm(app_symptoms)
    else:
        logger.info(
            "Skipping purpose generation (use --generate-purposes to enable)."
        )

    # Step 6: Build the final JSON
    seed_data = build_seed_json(app_symptoms, purposes)

    # Write output
    output_path = os.path.join(os.path.dirname(__file__), args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(seed_data, f, indent=4, ensure_ascii=False)

    logger.info("=" * 60)
    logger.info("✅ SUCCESS! Output written to: %s", output_path)
    logger.info("   Applications found: %d", len(seed_data["applications"]))
    logger.info("   Symptoms extracted: %d", len(seed_data["application_symptoms"]))
    logger.info("   Purposes generated: %d", len(seed_data["application_purposes"]))
    logger.info("=" * 60)

    if not purposes:
        logger.info(
            "\n💡 TIP: To auto-generate application purposes, run again with:\n"
            "   python process_official_data.py %s --generate-purposes\n"
            "   (Requires the vLLM server to be running on the office network.)",
            args.pdf_path,
        )

    logger.info(
        "\n📋 NEXT STEP: Review the output file, then run:\n"
        "   python seed_db.py --data official_seed_data.json\n"
        "   to load it into the database."
    )


if __name__ == "__main__":
    main()
