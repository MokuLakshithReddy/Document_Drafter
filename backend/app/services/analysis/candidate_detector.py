import re
import uuid
from typing import List, Tuple, Dict
from app.services.extraction.models import ExtractedDocument, ExtractedUnit
from app.schemas.api_schemas import OccurrenceDTO, VariableDTO, SourceLocator

class CandidateDetector:
    # High-precision entity patterns
    DATE_PATTERNS = [
        r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
        r'\b(?:\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b',
        r'\b\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4}\b',
    ]

    MONEY_PATTERNS = [
        r'[\$€£₹]\s?[\d,]+(?:\.\d{2})?',
        r'\b(?:USD|EUR|GBP|INR)\s?[\d,]+(?:\.\d{2})?\b',
    ]

    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    PHONE_PATTERN = r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    ID_PATTERN = r'\b(?:ID|REF|REF#|EMP|NO|CODE|ACCOUNT|INV)[-:\s#]+([A-Z0-9-]{4,15})\b'

    ROLE_PATTERNS = [
        r'\b(?:Software Engineer|Product Manager|Director|Consultant|Manager|Analyst|Developer|Designer|Vice President|Coordinator)\b'
    ]

    # Contextual name patterns: "Dear Mr./Ms. John Doe", "First party: John Doe", "Employee: Jane Smith"
    NAME_CONTEXT_PATTERNS = [
        r'(?:Dear|To|Attention|Name|Employee|Client|Recipient|Consultant|Mr\.|Ms\.|Mrs\.|Dr\.|Party|Buyer|Witness|Seller|Contractor|Vendor)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'(?:First|Second|Third)\s+party[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
    ]

    # Organization patterns
    ORG_PATTERNS = [
        r'\b[A-Z][A-Za-z0-9&.,\'\- ]{2,35}\s+(?:LLC|Inc\.?|Corp\.?|Corporation|Ltd\.?|Limited|GmbH|Technologies|Enterprises|Solutions|Group|Services|Holdings|Bank|University|Agency)\b',
        r'(?:Company|Employer|Organization|Client|Firm|Institution)[:\s]+([A-Z][A-Za-z0-9&.,\'\- ]{2,35})',
    ]

    # Address patterns
    ADDRESS_PATTERNS = [
        r'\b\d{1,5}\s+[A-Za-z0-9.,\- ]+\s+(?:Street|St\.?|Avenue|Ave\.?|Boulevard|Blvd\.?|Road|Rd\.?|Drive|Dr\.?|Lane|Ln\.?|Court|Ct\.?|Way|Parkway|Pkwy\.?|Suite|Ste\.?|Apt\.?)(?:[,\s]+[A-Za-z\s]+[,\s]+[A-Z]{2}\s+\d{5}(?:-\d{4})?)?\b',
        r'\b(?:P\.?O\.?\s*Box\s+\d+)\b',
    ]

    COMMON_TITLES = {"Appointment Letter", "Employment Agreement", "United States", "Acme Technologies", "Terms And", "Director Of"}
    NAME_REGEX = r'\b([A-Z][a-z]{2,15}\s+[A-Z][a-z]{2,15})\b'

    @classmethod
    def detect(cls, extracted_doc: ExtractedDocument) -> Tuple[List[OccurrenceDTO], List[VariableDTO]]:
        occurrences: List[OccurrenceDTO] = []
        # Map of original_text -> list of occurrence IDs
        text_to_occ_ids: Dict[str, List[str]] = {}
        text_to_type: Dict[str, str] = {}
        text_to_label: Dict[str, str] = {}

        occ_counter = 1

        for unit in extracted_doc.units:
            text = unit.full_text
            if not text:
                continue

            matches: List[Tuple[str, str, str, int, int]] = [] # (matched_text, type, label, start, end)

            # Dates
            for p in cls.DATE_PATTERNS:
                for m in re.finditer(p, text, flags=re.IGNORECASE):
                    matches.append((m.group(0), "date", "Date", m.start(), m.end()))

            # Money
            for p in cls.MONEY_PATTERNS:
                for m in re.finditer(p, text):
                    matches.append((m.group(0), "money", "Amount", m.start(), m.end()))

            # Email
            for m in re.finditer(cls.EMAIL_PATTERN, text):
                matches.append((m.group(0), "email", "Email Address", m.start(), m.end()))

            # Phone
            for m in re.finditer(cls.PHONE_PATTERN, text):
                val = m.group(0).strip()
                if len(val) >= 10:
                    matches.append((val, "phone", "Phone Number", m.start(), m.end()))

            # IDs
            for m in re.finditer(cls.ID_PATTERN, text, flags=re.IGNORECASE):
                matches.append((m.group(0), "identifier", "Identifier / Ref Code", m.start(), m.end()))

            # Roles
            for p in cls.ROLE_PATTERNS:
                for m in re.finditer(p, text, flags=re.IGNORECASE):
                    matches.append((m.group(0), "role", "Role / Title", m.start(), m.end()))

            # Names from context
            for p in cls.NAME_CONTEXT_PATTERNS:
                for m in re.finditer(p, text):
                    name_val = m.group(1).strip()
                    n_start = text.find(name_val, m.start())
                    if n_start != -1:
                        matches.append((name_val, "person_name", "Person Name", n_start, n_start + len(name_val)))

            # Organizations
            for p in cls.ORG_PATTERNS:
                for m in re.finditer(p, text):
                    org_val = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else m.group(0).strip()
                    o_start = text.find(org_val, m.start())
                    if o_start != -1:
                        matches.append((org_val, "organization", "Organization", o_start, o_start + len(org_val)))

            # Addresses
            for p in cls.ADDRESS_PATTERNS:
                for m in re.finditer(p, text):
                    addr_val = m.group(0).strip()
                    a_start = m.start()
                    matches.append((addr_val, "address", "Address", a_start, a_start + len(addr_val)))

            # Deduplicate overlapping matches within the same unit
            matches = sorted(matches, key=lambda x: (x[3], -(x[4] - x[3])))
            selected_unit_matches = []
            last_end = -1
            for m_text, m_type, m_label, s, e in matches:
                if s >= last_end:
                    selected_unit_matches.append((m_text, m_type, m_label, s, e))
                    last_end = e

            # Create occurrences
            for m_text, m_type, m_label, s, e in selected_unit_matches:
                occ_id = f"occ_{occ_counter:03d}"
                occ_counter += 1

                locator = SourceLocator(
                    kind=unit.kind,
                    container_id=unit.container_id,
                    char_start=s,
                    char_end=e,
                    page=unit.page,
                    bbox=unit.bbox
                )

                occ = OccurrenceDTO(
                    id=occ_id,
                    source_locator=locator,
                    original_text=m_text,
                    status="active"
                )
                occurrences.append(occ)

                if m_text not in text_to_occ_ids:
                    text_to_occ_ids[m_text] = []
                    text_to_type[m_text] = m_type
                    text_to_label[m_text] = f"{m_label} ({m_text})"
                text_to_occ_ids[m_text].append(occ_id)

        # Build candidate VariableDTOs
        variables: List[VariableDTO] = []
        var_counter = 1
        for orig_text, occ_ids in text_to_occ_ids.items():
            var_id = f"var_{var_counter:03d}"
            v_type = text_to_type[orig_text]
            clean_key = re.sub(r'[^a-zA-Z0-9_]', '_', f"{v_type}_{var_counter}").lower()

            # Note from spec: replacement value is blank by default unless user supplies it
            var = VariableDTO(
                id=var_id,
                key=clean_key,
                label=text_to_label[orig_text],
                type=v_type,
                original_value=orig_text,
                replacement_value="",
                occurrence_ids=occ_ids,
                confidence=0.92,
                reason=f"Detected {v_type} pattern with {len(occ_ids)} occurrence(s)",
                required=False,
                status="active"
            )
            # Link occurrences to this variable
            for occ in occurrences:
                if occ.id in occ_ids:
                    occ.variable_id = var_id

            variables.append(var)
            var_counter += 1

        return occurrences, variables
