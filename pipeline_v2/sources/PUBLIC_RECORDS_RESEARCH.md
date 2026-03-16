# Public Records Data Sources: Attorneys, Therapists, and Dentists

**Research Date:** March 15, 2026
**Status:** Research complete — implementation recommendations included

---

## Summary Verdict

| Source | Profession | TOS Safety | Bulk Access | Priority |
|--------|-----------|------------|-------------|----------|
| NPPES NPI Registry (CMS) | Therapists, Dentists | SAFE — FOIA-required public data | Yes — monthly 1GB CSV + free REST API | HIGH |
| Florida MQA Data Download | Therapists, Dentists | SAFE — Florida Chapter 119 public records | Yes — daily pipe-delimited files | HIGH |
| Texas BHEC CSV Downloads | Therapists/Counselors | SAFE — explicitly public, no restrictions stated | Yes — daily CSV per license type | HIGH |
| Colorado Open Data Portal | Therapists, Dentists, Attorneys | SAFE — government open data, Socrata | Yes — Socrata API + CSV export | HIGH |
| Washington State data.wa.gov | Therapists, Dentists | CAUTION — explicitly prohibits commercial address use | Yes — Socrata API, but no address data | MEDIUM |
| State Bar Websites | Attorneys | CAUTION — varies by state, fees may apply | No — individual lookup only | LOW |
| California DCA | Therapists, Dentists | SAFE — monthly CSV via Box | Yes — monthly Box download | MEDIUM |
| SAMHSA FindTreatment.gov | Therapists (facilities only) | LIKELY SAFE — federal public data, requires API request | Application required | LOW |

---

## Section 1: Therapists and Mental Health Professionals

### 1.1 NPPES NPI Registry (CMS / HHS) — RECOMMENDED PRIMARY SOURCE

**URL:** https://npiregistry.cms.hhs.gov
**Bulk Download:** https://download.cms.gov/nppes/NPI_Files.html
**REST API:** https://npiregistry.cms.hhs.gov/api/

**What It Is:**
The National Plan and Provider Enumeration System (NPPES) is maintained by the Centers for Medicare & Medicaid Services (CMS). Every healthcare provider who bills Medicare/Medicaid or participates in HIPAA standard transactions must have an NPI. This covers essentially all licensed therapists, psychologists, social workers, counselors, and dentists in the US.

**TOS / Legal Status:**
FOIA-required disclosure. Per CMS: "The information disclosed on the NPI Registry and in the downloadable files are FOIA-disclosable and are required to be disclosed under the FOIA." No charge to download. No explicit commercial use prohibition found. The data is considered government-produced public information. Many existing commercial directories (Zocdoc, Psychology Today, etc.) are known to use NPPES data as a base.

**Data Fields Available:**
- NPI number
- Provider name (first, last, organization name)
- Credential (e.g., LCSW, PhD, MD)
- Gender
- Taxonomy codes (specialty type)
- Primary practice address (street, city, state, zip)
- Mailing address
- Phone number, fax
- License numbers and states
- Other provider names
- Entity type (individual vs. organization)

**How to Filter for Therapists/Mental Health:**
Use taxonomy codes in the REST API or filter the bulk CSV by taxonomy code column:

| Taxonomy Code | Description |
|---------------|-------------|
| 100000000X | Behavioral Health and Social Service Providers (parent) |
| 101Y00000X | Counselor |
| 101YA0400X | Addiction (Substance Use Disorder) Counselor |
| 101YP2500X | Professional Counselor (LPC) |
| 103T00000X | Psychologist |
| 103TC0700X | Clinical Psychologist |
| 103TC2200X | Clinical Child and Adolescent Psychologist |
| 106H00000X | Marriage & Family Therapist (MFT/LMFT) |
| 1041C0700X | Clinical Social Worker (LCSW) |
| 104100000X | Social Worker |

**Bulk Download Details:**
- Monthly Full Replacement file: ~1.06 GB zipped (as of March 2026)
- Weekly Incremental file: ~8.5 MB
- Format: CSV (pipe-delimited in older versions, comma-separated in V.2)
- Version 2 now required (V.1 deprecated March 3, 2026)
- Includes: Other Name Reference, Practice Location Reference, Endpoint Reference files

**REST API:**
```
GET https://npiregistry.cms.hhs.gov/api/?version=2.1&taxonomy_description=therapist&state=FL&limit=200
GET https://npiregistry.cms.hhs.gov/api/?version=2.1&taxonomy_description=psychologist&city=Miami&limit=200
```
- Returns up to 1,200 results per query set
- For larger datasets, use bulk download file
- No authentication required
- No documented rate limits (but use politely)

**Implementation Feasibility:** HIGH — This is the gold standard source. Easy REST API, free bulk download, nationwide coverage, updated weekly/monthly.

---

### 1.2 Texas BHEC CSV Downloads — RECOMMENDED FOR TX COVERAGE

**URL:** https://bhec.texas.gov/verify-a-license/
**CSV Files:**
- Psychologists: `https://www.bhec.texas.gov/csv/PSY.csv`
- Marriage & Family Therapists: `https://www.bhec.texas.gov/csv/MFT.csv`
- Professional Counselors (LPC): `https://www.bhec.texas.gov/csv/LPC.csv`
- Social Workers: `https://www.bhec.texas.gov/csv/SW.csv`

**What It Is:**
Texas Behavioral Health Executive Council (BHEC) — the state licensing body for all behavioral health professionals in Texas. These are direct CSV downloads of all current licensees, updated every 24 hours.

**TOS / Legal Status:**
Government public records. No terms of use or restrictions stated on the page. Data is explicitly described as "public information." Excludes only those "made confidential by statute." This is squarely public government data — SAFE to use.

**Data Fields:**
- Lic_Type (license type code)
- Rank (license level/rank)
- Lic_Nbr (license number)
- Entity_Nbr (entity number)
- Last_Nme, First_Nme, Middle_Nme, SFX_Nme (full name)
- Lic_Status (active, inactive, expired, etc.)
- Lic_Expr_Dte (expiration date)
- Rank_Efct_Dte (rank effective date)
- Discpl_Actn (disciplinary action indicator)

**Note:** Does NOT include address or phone — would need to cross-reference with NPPES for contact info.

**Implementation Feasibility:** HIGH — Simple direct CSV download, daily updates, clean format. Best used to validate Texas license status, then NPPES for contact details.

---

### 1.3 Florida MQA Data Download — RECOMMENDED FOR FL COVERAGE

**URL:** https://mqa-internet.doh.state.fl.us/mqasearchservices/home
**Data Download Portal:** https://data-download.mqa.flhealthsource.gov/

**What It Is:**
Florida Department of Health Division of Medical Quality Assurance (MQA) licenses over 200 license types across 40+ healthcare professions. This includes clinical social workers, marriage and family therapists, mental health counselors, psychologists, and dentists.

**TOS / Legal Status:**
Provided in compliance with Chapter 119, Florida Statutes (Florida Public Records Law). This is a statutory public records release — SAFE to use. Florida's public records laws are among the strongest in the US.

**Data Fields:**
- Pipe-delimited ASCII text format
- Updated daily
- Metadata files available describing all field names and formats
- "Selecting All Professions generates a file with over 1 million records"
- Includes: name, license type, license number, status, expiration

**Access:**
The data download portal at `data-download.mqa.flhealthsource.gov` appears to be publicly accessible. The main search portal also allows CSV export of search results. The Help PDF (UserGuide) documents the full field list and import instructions for Excel/Access.

**Professions Covered (relevant):**
- Dentists
- Clinical Social Workers / LCSW
- Marriage and Family Therapists / LMFT
- Mental Health Counselors (LMHC)
- Psychologists
- And 35+ other regulated health professions

**Implementation Feasibility:** HIGH — Comprehensive Florida coverage, daily updates, pipe-delimited format easy to parse.

---

### 1.4 Colorado Open Data Portal — RECOMMENDED FOR CO COVERAGE

**URL:** https://data.colorado.gov/Regulations/Professional-and-Occupational-Licenses-in-Colorado/7s5z-vewr
**Socrata API Endpoint:** `https://data.colorado.gov/resource/7s5z-vewr.json`

**What It Is:**
Colorado Department of Regulatory Agencies (DORA) publishes all professional and occupational license data on the Colorado Information Marketplace (Socrata-based open data portal). Updated nightly.

**TOS / Legal Status:**
Colorado state open data — government public records. Socrata platform with standard open data terms. SAFE to use.

**License Types Included (relevant):**
- Psychologists
- Dentists
- Marriage & Family Therapists
- Professional Counselors
- And many other DORA-regulated professions

**Access:**
Standard Socrata API allows filtering, pagination, CSV/JSON/XML export:
```
GET https://data.colorado.gov/resource/7s5z-vewr.json?license_type=Psychologist&$limit=1000
```

**Implementation Feasibility:** HIGH — Standard Socrata API, easy to query, official government open data. Best practice model for state data portals.

---

### 1.5 Washington State Health Care Provider Credential Data — MEDIUM PRIORITY

**URL:** https://data.wa.gov/health/Health-Care-Provider-Credential-Data/qxh8-f4bd
**Socrata API:** `https://data.wa.gov/resource/qxh8-f4bd.json`
**Human-readable story:** https://data.wa.gov/stories/s/Find-a-Health-Provider-Credential/k356-mc56/

**What It Is:**
Washington State Department of Health publishes all provider credential data on data.wa.gov via Socrata. Covers 236+ credential types.

**TOS / Legal Status:**
Government open data — SAFE. **HOWEVER:** The DOH explicitly states it "doesn't provide electronic lists of individuals for commercial purposes" and therefore **excludes mailing addresses, emails, and phone numbers** from the dataset. Also: "DOH advises not to use tools to scrape or mine data from Provider Credential Search."

**Data Fields Available:**
- Credential Number, Last Name, First Name, Middle Name
- Credential Type (236+ types, including Counselor Registration, Physical Therapist, Massage Therapist, etc.)
- Status
- Birth Year (not full DOB)
- CE Due Date, First Issue Date, Last Issue Date, Expiration Date
- Action Taken (disciplinary)
- **NOTE: No address, phone, or email**

**Professions Covered:**
"Counselor Registration," "Massage Therapist License," "Physical Therapist License," "Advanced Registered Nurse Practitioner License," and 230+ others. Therapists and behavioral health professions are included.

**Limitation:**
No contact details. Useful for license validation but must be cross-referenced with NPPES for location/contact data.

**Implementation Feasibility:** MEDIUM — Good for WA license verification, but requires NPPES cross-reference for complete profiles.

---

### 1.6 California DCA Licensee List — MEDIUM PRIORITY

**URL:** https://www.dca.ca.gov/consumers/public_info/index.shtml
**Download Link:** https://dca.box.com/s/oss6hf8jys2bmgxqd2gdz7w4oepm2il9

**What It Is:**
California Department of Consumer Affairs provides monthly downloadable files for all 150+ license types, including the Board of Behavioral Sciences (LMFT, LCSW, LPCC, LEP) and the Dental Board of California.

**TOS / Legal Status:**
Provided "in accordance with the Information Practices Act." Government public records — SAFE. No explicit commercial use restriction found. Refreshed at the beginning of each month.

**Excluded Boards (must contact separately):**
- California State Athletic Commission
- Contractors State License Board
- Bureau for Private Postsecondary Education

**Data Fields:**
Specific fields not documented on the public page — require downloading the Box file to inspect. Typically includes: name, license number, license type, status, expiration, address (varies by board).

**California BBS Specifically:**
Covers LMFT, LCSW, LPCC (Licensed Professional Clinical Counselor), LEP, and related license types.

**Implementation Feasibility:** MEDIUM — Monthly updates (slower than daily), requires Box download, but covers all CA health professions in one file.

---

### 1.7 SAMHSA FindTreatment.gov API — LOW PRIORITY (Facilities, Not Individual Providers)

**URL:** https://findtreatment.gov
**API Request Form:** https://findtreatment.gov/api-request-form
**Developer Guide:** https://findtreatment.gov/assets/FindTreatment-Developer-Guide.pdf
**Data.gov Dataset:** https://catalog.data.gov/dataset/mental-health-treatement-facilities-locator

**What It Is:**
SAMHSA's FindTreatment.gov lists treatment facilities (not individual therapist practitioners) for mental health, substance abuse, and behavioral health. Includes public mental health facilities funded by State agencies, VA facilities, and licensed/accredited private facilities.

**TOS / Legal Status:**
Federal government data — public domain. However, requires submitting an API access request form (not automatic). Data is updated: annually via national survey, new facilities added monthly, facility updates weekly.

**Data Fields:**
Facility-level data: facility name, address, phone, services offered, payment options, hours, languages, special populations served.

**Key Limitation:**
This covers **treatment facilities**, not individual licensed therapist profiles. Useful for building a "treatment centers" section, not individual practitioner profiles.

**Implementation Feasibility:** LOW for individual therapists, MEDIUM for facility/clinic listings.

---

## Section 2: Dentists

### 2.1 NPPES NPI Registry — PRIMARY SOURCE (same as above)

Taxonomy codes for dentists:

| Taxonomy Code | Description |
|---------------|-------------|
| 122300000X | Dentist (general) |
| 122400000X | Denturist |
| 124Q00000X | Dental Hygienist |
| 125J00000X | Dental Therapist |
| 125K00000X | Advanced Practice Dental Therapist |
| 1223D0001X | Dental Public Health Dentist |
| 1223E0200X | Endodontist |
| 1223G0001X | General Practice Dentist |
| 1223P0106X | Oral & Maxillofacial Pathology |
| 1223P0221X | Orthodontist |
| 1223P0300X | Pediatric Dentist (Pedodontist) |
| 1223P0700X | Periodontist |
| 1223S0112X | Oral & Maxillofacial Surgery |

All dentists with NPI numbers are in the NPPES dataset. The REST API:
```
GET https://npiregistry.cms.hhs.gov/api/?version=2.1&taxonomy_description=dentist&state=CA&limit=200
```

### 2.2 Florida MQA — SAME PORTAL AS THERAPISTS

Florida MQA covers dentists. Same download portal applies: https://data-download.mqa.flhealthsource.gov/

### 2.3 Colorado Open Data Portal — SAME DATASET AS THERAPISTS

Dentists are included in the Colorado DORA dataset.

### 2.4 State Dental Boards — Individual State Reference

For states not covered by NPPES cross-reference, most state dental boards have online license verification:
- **Texas:** https://tsbde.texas.gov/resources/public-license-search/
- **Florida:** Covered by MQA (above)
- **California:** Covered by DCA (above)
- **New York:** https://www.op.nysed.gov (Office of the Professions — individual lookup only, no bulk)

Note: No state dental board was found offering a dedicated bulk download API separate from the statewide systems already documented above.

---

## Section 3: Attorneys

### 3.1 State Bar Associations — CHALLENGING, NO BULK API

**The Core Problem:**
Unlike healthcare professions (which have the unified NPPES system), there is no federal equivalent for attorney licensing. Each state bar association is a separate entity. While attorney license records are public, the access model is primarily:
1. Individual online lookup (search by name)
2. Public records requests for bulk data (fees may apply)
3. No standardized API across states

**State-by-State Findings:**

#### California State Bar
- **Search:** https://apps.calbar.ca.gov/attorney/LicenseeSearch/QuickSearch
- **Public Records:** https://calbarca.nextrequest.com/ (public records request portal)
- **Bulk Access:** No public bulk download or API found. Must submit formal public records request. Fees apply for "commercial use" requests.
- **Data Available:** Name, bar number, admission date, status (active/inactive/suspended/disbarred), address, phone, law school, disciplinary history
- **TOS:** Public records but commercial use fees may apply per CA Info Practices Act.

#### Texas State Bar
- **Search:** https://www.texasbar.com/publicinformation/
- **Bulk Access:** No bulk download. Must submit Open Records Act request.
- **Fees:** $0.10/page for copies; labor at $15-$28.50/hour; estimates required >$40
- **Data Available:** Name, license number, status, practice location, law school, license date, grievance history
- **TOS:** Texas Public Information Act governs. Not explicitly prohibited for directories, but contact Public Information Coordinator (512) 427-1550 before building commercial product.

#### Florida Bar
- **Search:** https://www.floridabar.org
- **Bulk Access:** Public records request available for FL Bar membership data (circuit, county, law section, board certification filters). Form exists.
- **Data Available:** Name, address, year of birth, gender, law school, admission year; plus optional expanded professional data attorneys may have provided
- **TOS:** Florida Chapter 119 (public records) applies. SAFE but fees likely for bulk commercial requests.

#### New York State Bar
- **Agency:** NY State Education Department Office of the Professions (not NYSBA — the voluntary bar association)
- **Search:** https://www.op.nysed.gov — covers attorneys among 1.5M+ licensees in 50+ professions
- **Bulk Access:** No documented bulk download. Individual lookup only.

#### Illinois State Bar (IDFPR)
- **URL:** https://idfpr.illinois.gov/dpr/active-license-report.html
- **Bulk:** Monthly PDF Active License Reports available (2023-2026). PDF format only — not CSV.
- **Note:** Attorneys regulated by ARDC (Attorney Registration and Disciplinary Commission), separate from IDFPR.

### 3.2 CourtListener / Free Law Project — ATTORNEY CASE DATA (Not Profiles)

**URL:** https://www.courtlistener.com/help/api/
**Bulk Data:** https://www.courtlistener.com/help/api/bulk-data/

**What It Is:**
CourtListener (by Free Law Project, a 501c3) has ~500M PACER-related objects including attorney names from case filings. This is NOT attorney license data — it's attorney participation in federal cases.

**TOS:** "Free of known copyright restrictions." Open source, open access.

**Usefulness:**
Could supplement bar data with: courts where attorneys have appeared, cases, practice area inference from case types. NOT a substitute for bar license data.

**Implementation Feasibility:** LOW for core attorney directory, MEDIUM as enrichment data.

### 3.3 Recommendation for Attorneys

The attorney data problem requires a multi-step approach:

1. **Short term:** Submit public records requests to FL, TX, CA, NY, WA, MA, CO, IL state bars. Most should respond within 10 business days. FL and TX are strongest public records states.

2. **Medium term:** Use web scraping of state bar search portals (each allows public search — the question is TOS on automated access). Most state bar TOS do not explicitly prohibit reasonable automated queries for public data, but check each individually.

3. **Alternative:** Consider licensed data providers that have already aggregated bar data:
   - **Martindale-Hubbell / Lexis Nexis** — aggregated bar data, but licensed (expensive)
   - **CourtListener** — free but only federal case participation
   - **State-specific data vendors** already have this data

---

## Section 4: Implementation Recommendations

### Phase 1 — Quick Wins (implement immediately)

**1. NPPES Bulk Download**
- Download the monthly V.2 file from https://download.cms.gov/nppes/NPI_Files.html
- Filter by taxonomy codes for therapists (101Y00000X, 103T00000X, 106H00000X, 1041C0700X) and dentists (122300000X, 1223G0001X)
- This gives nationwide coverage in a single file
- Estimated records: ~300,000+ therapists/counselors, ~200,000+ dentists

**2. Texas BHEC CSV (TX Therapists)**
- Direct download: `https://www.bhec.texas.gov/csv/LPC.csv`, `/MFT.csv`, `/PSY.csv`, `/SW.csv`
- Cross-reference with NPPES for address/phone data
- Daily updates

**3. Florida MQA (FL Therapists + Dentists)**
- Download from https://data-download.mqa.flhealthsource.gov/
- Covers all 40+ health professions regulated by FL DOH
- Daily updates

**4. Colorado DORA (CO Therapists + Dentists + Attorneys)**
- Socrata API: `https://data.colorado.gov/resource/7s5z-vewr.json`
- Query by license_type filter
- Includes attorneys licensed through DORA (not all CO attorneys — check if DORA regulates attorneys or if that's Colorado Supreme Court/bar)

### Phase 2 — State Supplemental Data

- **Washington:** data.wa.gov Socrata API — license validation, no contact info
- **California:** DCA monthly Box download — covers BBS therapists and Dental Board dentists
- **Illinois IDFPR:** Submit public records request for CSV data (PDFs available but not machine-readable)

### Phase 3 — Attorney Data

- Submit FL Public Records Act requests to FL Bar, TX Open Records to TX Bar
- Evaluate whether state bar web search portals allow reasonable automated queries
- Consider CourtListener to infer practice areas from case history

---

## Section 5: Legal Safety Assessment

### Clearly Safe (Government FOIA/Public Records)
- NPPES/NPI data (federal, FOIA-required)
- Texas BHEC CSV (explicit public data, no restrictions)
- Florida MQA (Chapter 119, FL Statutes)
- Colorado DORA open data portal
- SAMHSA FindTreatment.gov (federal public data)

### Likely Safe (Government Open Data, Verify Terms)
- Washington data.wa.gov — safe for license lookup, but explicitly prohibits commercial address lists
- California DCA Box downloads — IPA-governed, no explicit commercial restriction found

### Requires Verification / Caution
- State bar attorney data — public records but commercial use fees may apply in some states
- Any state board where TOS are not explicitly stated — default to public records request with written confirmation

### Do NOT Use
- Psychology Today directory (private commercial site, restrictive TOS)
- Zocdoc, Healthgrades, etc. (private, commercial, restrictive TOS)
- Any source that requires Terms of Service agreement prohibiting commercial use
- ADA Find-a-Dentist (private directory, commercial restrictions)

---

## Section 6: API Quick Reference

### NPPES REST API
```
Base URL: https://npiregistry.cms.hhs.gov/api/
Version: 2.1

# Search by taxonomy for therapists in Florida
GET /api/?version=2.1&taxonomy_description=counselor&state=FL&limit=200&skip=0

# Search by taxonomy code directly
GET /api/?version=2.1&taxonomy_description=psychologist&city=Austin&state=TX&limit=200

# Search by name
GET /api/?version=2.1&first_name=Jane&last_name=Smith&state=CA&version=2.1

Response fields: results[].basic (name, credential, gender, enumeration_date, last_updated),
                 results[].addresses[] (address, city, state, zip, phone, fax),
                 results[].taxonomies[] (code, desc, primary, state, license)
```

### Colorado DORA (Socrata)
```
Base URL: https://data.colorado.gov/resource/7s5z-vewr.json
GET ?license_type=Psychologist&$limit=1000&$offset=0
GET ?license_type=Dentist&$where=license_status='ACTIVE'&$limit=1000
```

### Washington DOH (Socrata)
```
Base URL: https://data.wa.gov/resource/qxh8-f4bd.json
GET ?credential_type=Psychologist%20License&$limit=1000
GET ?$where=credential_type%20like%20%27%25Counselor%25%27&$limit=1000
```

### Texas BHEC (Direct CSV)
```
https://www.bhec.texas.gov/csv/PSY.csv   # Psychologists
https://www.bhec.texas.gov/csv/MFT.csv   # Marriage & Family Therapists
https://www.bhec.texas.gov/csv/LPC.csv   # Professional Counselors
https://www.bhec.texas.gov/csv/SW.csv    # Social Workers
```

---

*Research conducted March 15, 2026. Sources: CMS.gov, SAMHSA, state government portals, direct API inspection.*
