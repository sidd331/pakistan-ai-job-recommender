"""
=============================================================================
Resume Parser — Extracts structured data from PDF/DOCX resumes using NLP.
=============================================================================
Uses PyPDF2 for PDF, python-docx for DOCX, and spaCy for entity/skill
extraction.  Falls back gracefully if spaCy model is not installed.
=============================================================================
"""

import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TEXT EXTRACTION
# ---------------------------------------------------------------------------
def extract_text_from_pdf(file_path: str) -> str:
    """Extract raw text from a PDF file."""
    from PyPDF2 import PdfReader
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def extract_text_from_docx(file_path: str) -> str:
    """Extract raw text from a DOCX file."""
    from docx import Document
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def extract_text(file_path: str) -> str:
    """Auto-detect file type and extract text."""
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif lower.endswith(".docx"):
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")


# ---------------------------------------------------------------------------
# SKILLS DATABASE  (curated list — programming, data, cloud, soft skills, etc.)
# ---------------------------------------------------------------------------
SKILLS_DB = {
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "c",
    "ruby", "php", "swift", "kotlin", "go", "golang", "rust", "scala",
    "r", "matlab", "perl", "dart", "lua", "shell", "bash", "powershell",
    "sql", "nosql", "plsql", "html", "css", "sass", "less",

    # Frameworks & libraries
    "react", "angular", "vue", "vue.js", "node.js", "nodejs", "express",
    "django", "flask", "fastapi", "spring", "spring boot", ".net", "asp.net",
    "laravel", "rails", "ruby on rails", "nextjs", "next.js", "nuxt",
    "svelte", "jquery", "bootstrap", "tailwind", "tailwindcss",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "matplotlib", "seaborn", "opencv", "nltk", "spacy",
    "flutter", "react native", "xamarin", "electron",

    # Databases
    "mysql", "postgresql", "postgres", "mongodb", "redis", "sqlite",
    "oracle", "sql server", "dynamodb", "cassandra", "elasticsearch",
    "firebase", "supabase", "mariadb", "couchdb", "neo4j",

    # Cloud & DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
    "terraform", "ansible", "jenkins", "ci/cd", "github actions",
    "gitlab ci", "circleci", "nginx", "apache", "linux", "ubuntu",
    "heroku", "vercel", "netlify", "cloudflare", "lambda", "serverless",

    # Data & AI/ML
    "machine learning", "deep learning", "artificial intelligence", "ai",
    "natural language processing", "nlp", "computer vision",
    "data science", "data analysis", "data engineering", "data mining",
    "big data", "hadoop", "spark", "apache spark", "etl", "data warehouse",
    "power bi", "tableau", "excel", "looker", "dbt",
    "statistics", "regression", "classification", "clustering",
    "neural networks", "cnn", "rnn", "lstm", "transformers", "bert", "gpt",

    # Tools & Platforms
    "git", "github", "gitlab", "bitbucket", "jira", "confluence",
    "trello", "slack", "notion", "figma", "adobe xd", "sketch",
    "photoshop", "illustrator", "canva", "wordpress", "shopify",
    "salesforce", "sap", "erp", "crm", "hubspot",

    # Methodologies
    "agile", "scrum", "kanban", "devops", "microservices",
    "rest", "restful", "graphql", "api", "soap", "grpc",
    "oop", "design patterns", "solid", "tdd", "bdd",
    "ci/cd", "continuous integration", "continuous deployment",

    # Security
    "cybersecurity", "penetration testing", "ethical hacking",
    "encryption", "ssl", "oauth", "jwt", "authentication",
    "firewall", "ids", "ips", "siem", "compliance",

    # Networking
    "tcp/ip", "dns", "dhcp", "vpn", "lan", "wan", "routing",
    "switching", "ccna", "ccnp", "network security",

    # Soft skills
    "leadership", "teamwork", "communication", "problem solving",
    "critical thinking", "project management", "time management",
    "presentation", "negotiation", "strategic planning",
    "analytical", "research", "mentoring", "collaboration",

    # Business & Finance
    "accounting", "financial analysis", "budgeting", "auditing",
    "business development", "marketing", "digital marketing",
    "seo", "sem", "social media", "content marketing",
    "supply chain", "logistics", "procurement", "operations",

    # Domain-specific (Pakistan job market)
    "urdu", "english", "arabic", "teaching", "education",
    "civil engineering", "mechanical engineering", "electrical engineering",
    "chemical engineering", "biomedical", "pharmacy", "medicine",
    "law", "legal", "public administration", "governance",
    "banking", "microfinance", "insurance", "taxation",
    "ngo", "development sector", "humanitarian", "un",
    "ms office", "microsoft office", "word", "powerpoint",
    "autocad", "solidworks", "primavera", "project management",
}

# ---------------------------------------------------------------------------
# EDUCATION KEYWORDS
# ---------------------------------------------------------------------------
EDUCATION_PATTERNS = [
    r"\b(ph\.?d|doctorate|doctoral)\b",
    r"\b(m\.?s\.?|master(?:'?s)?|mba|msc|m\.?phil|mphil)\b",
    r"\b(b\.?s\.?|bachelor(?:'?s)?|bba|bsc|b\.?e\.?|b\.?tech)\b",
    r"\b(associate(?:'?s)?|diploma|certificate|certification)\b",
    r"\b(intermediate|fsc|fa|ics|icom)\b",
    r"\b(matriculation|matric|ssc|o[\s-]?level|a[\s-]?level)\b",
]

DEGREE_FIELDS = [
    "computer science", "software engineering", "information technology",
    "data science", "artificial intelligence", "electrical engineering",
    "mechanical engineering", "civil engineering", "chemical engineering",
    "business administration", "finance", "economics", "accounting",
    "mathematics", "statistics", "physics", "chemistry", "biology",
    "medicine", "pharmacy", "law", "education", "psychology",
    "mass communication", "journalism", "political science",
    "public administration", "islamic studies", "english literature",
    "urdu literature", "environmental science", "agriculture",
]

# ---------------------------------------------------------------------------
# JOB TITLE KEYWORDS
# ---------------------------------------------------------------------------
JOB_TITLE_PATTERNS = [
    r"\b(software\s+(?:engineer|developer|architect))\b",
    r"\b(web\s+developer)\b",
    r"\b(full[\s-]?stack\s+developer)\b",
    r"\b(front[\s-]?end\s+developer)\b",
    r"\b(back[\s-]?end\s+developer)\b",
    r"\b(data\s+(?:scientist|analyst|engineer))\b",
    r"\b(machine\s+learning\s+engineer)\b",
    r"\b(devops\s+engineer)\b",
    r"\b(cloud\s+(?:engineer|architect))\b",
    r"\b(project\s+manager)\b",
    r"\b(product\s+manager)\b",
    r"\b(business\s+analyst)\b",
    r"\b(quality\s+assurance|qa\s+engineer)\b",
    r"\b(network\s+(?:engineer|administrator))\b",
    r"\b(system\s+administrator)\b",
    r"\b(database\s+administrator|dba)\b",
    r"\b(ui/?ux\s+designer)\b",
    r"\b(graphic\s+designer)\b",
    r"\b(marketing\s+(?:manager|executive|specialist))\b",
    r"\b(accountant|auditor)\b",
    r"\b(teacher|lecturer|professor)\b",
    r"\b(civil\s+engineer)\b",
    r"\b(electrical\s+engineer)\b",
    r"\b(mechanical\s+engineer)\b",
    r"\b(manager|director|lead|head|chief|officer|executive|consultant|analyst|engineer|administrator|coordinator|specialist|intern|trainee)\b",
]

# ---------------------------------------------------------------------------
# LOCATION KEYWORDS
# ---------------------------------------------------------------------------
PAKISTAN_CITIES = [
    "islamabad", "rawalpindi", "lahore", "karachi", "peshawar",
    "quetta", "faisalabad", "multan", "hyderabad", "sialkot",
    "gujranwala", "bahawalpur", "sargodha", "abbottabad",
    "mardan", "mingora", "dera ismail khan", "kohat", "swat",
    "muzaffarabad", "mirpur", "gilgit", "skardu", "chitral",
    "pakistan", "punjab", "sindh", "khyber pakhtunkhwa",
    "balochistan", "azad kashmir", "gilgit-baltistan",
    "remote", "work from home",
]


# ---------------------------------------------------------------------------
# NLP PARSER
# ---------------------------------------------------------------------------
def _load_spacy():
    """Load spaCy model with fallback."""
    try:
        import spacy
        try:
            return spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model 'en_core_web_sm' not found. "
                           "Run: python -m spacy download en_core_web_sm")
            return None
    except ImportError:
        logger.warning("spaCy not installed. NER features will be limited.")
        return None


def parse_resume(file_path: str) -> dict:
    """
    Parse a resume file and extract structured profile information.

    Returns dict with keys:
        raw_text, skills, education, experience, locations,
        job_titles, experience_years, summary
    """
    raw_text = extract_text(file_path)
    if not raw_text.strip():
        return {
            "raw_text": "",
            "skills": [],
            "education": [],
            "experience": [],
            "locations": [],
            "job_titles": [],
            "experience_years": 0,
            "summary": "Could not extract text from the uploaded file.",
        }

    text_lower = raw_text.lower()

    # ---- Skill extraction (word-boundary for all skills) ----
    found_skills = []
    for skill in SKILLS_DB:
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, text_lower):
            display = skill.upper() if len(skill) <= 3 else skill.title()
            found_skills.append(display)
    found_skills = sorted(set(found_skills))

    # ---- Education extraction ----
    found_education = []
    for pattern in EDUCATION_PATTERNS:
        matches = re.findall(pattern, text_lower)
        for m in matches:
            degree = m.strip().upper() if len(m) <= 4 else m.strip().title()
            if degree not in found_education:
                found_education.append(degree)

    for field in DEGREE_FIELDS:
        if field in text_lower:
            found_education.append(field.title())
    found_education = list(dict.fromkeys(found_education))  # deduplicate, preserve order

    # ---- Experience years estimation ----
    experience_years = 0
    year_patterns = [
        r"(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
        r"experience\s*(?:of\s+)?(\d{1,2})\+?\s*(?:years?|yrs?)",
    ]
    for pattern in year_patterns:
        match = re.search(pattern, text_lower)
        if match:
            experience_years = max(experience_years, int(match.group(1)))
            break

    # ---- Location extraction (word-boundary matching) ----
    found_locations = []
    for city in PAKISTAN_CITIES:
        pattern = rf"\b{re.escape(city)}\b"
        if re.search(pattern, text_lower):
            found_locations.append(city.title())
    found_locations = sorted(set(found_locations))

    # ---- Job title extraction ----
    found_titles = []
    for pattern in JOB_TITLE_PATTERNS:
        matches = re.findall(pattern, text_lower)
        for m in matches:
            title = m.strip().title()
            if title not in found_titles and len(title) > 3:
                found_titles.append(title)
    found_titles = list(dict.fromkeys(found_titles))[:10]  # top 10

    # ---- spaCy NER (if available) — with strong false-positive filtering ----
    nlp = _load_spacy()
    if nlp:
        try:
            doc = nlp(raw_text[:100000])  # limit to 100k chars
            for ent in doc.ents:
                if ent.label_ == "GPE":
                    loc = ent.text.strip().title()
                    loc_lower = ent.text.strip().lower()

                    # FILTER 1: Skip very short strings (1-2 chars) — noise
                    if len(loc_lower) <= 2:
                        continue

                    # FILTER 2: Skip if it matches a known skill from SKILLS_DB
                    # This catches sklearn, numpy, pandas, flask, django, keras, etc.
                    if loc_lower in SKILLS_DB:
                        logger.debug("Rejected GPE '%s' — matches SKILLS_DB entry", loc)
                        continue

                    # FILTER 3: Skip multi-word tech terms that contain skill words
                    loc_words = set(loc_lower.split())
                    tech_indicators = {
                        "sklearn", "scikit", "numpy", "scipy", "pandas", "matplotlib",
                        "seaborn", "keras", "pytorch", "tensorflow", "flask", "django",
                        "fastapi", "react", "angular", "vue", "node", "express",
                        "spring", "laravel", "bootstrap", "tailwind", "jupyter",
                        "colab", "hadoop", "spark", "docker", "kubernetes", "redis",
                        "mongo", "mongodb", "postgres", "mysql", "sqlite", "oracle",
                        "firebase", "heroku", "vercel", "netlify", "lambda", "azure",
                        "aws", "gcp", "api", "sdk", "npm", "pip", "git",
                        "excel", "powerpoint", "matlab", "tableau", "power",
                        "learning", "engineering", "science", "intelligence",
                        "framework", "library", "module", "package",
                    }
                    if loc_words & tech_indicators:
                        logger.debug("Rejected GPE '%s' — contains tech indicator word", loc)
                        continue

                    # FILTER 4: Only accept if it looks like a real geographic entity
                    # Accept if it's already in our curated PAKISTAN_CITIES list
                    if loc_lower in PAKISTAN_CITIES:
                        if loc not in found_locations:
                            found_locations.append(loc)
                        continue

                    # Accept if it looks like a proper geographic name
                    # (capitalized, no dots/slashes, not a pure number)
                    if (loc[0].isupper()
                            and not any(c in loc_lower for c in "./_+=")
                            and not loc_lower.replace(" ", "").isdigit()):
                        if loc not in found_locations:
                            found_locations.append(loc)

        except Exception as e:
            logger.warning(f"spaCy processing failed: {e}")

    # ---- Build summary ----
    summary_parts = []
    if experience_years:
        summary_parts.append(f"{experience_years} years of experience")
    if found_skills:
        top_skills = found_skills[:5]
        summary_parts.append(f"skilled in {', '.join(top_skills)}")
    if found_education:
        summary_parts.append(f"education: {', '.join(found_education[:3])}")
    if found_locations:
        summary_parts.append(f"based in {', '.join(found_locations[:3])}")

    summary = ". ".join(summary_parts).capitalize() + "." if summary_parts else "Profile parsed from resume."

    return {
        "raw_text": raw_text,
        "skills": found_skills,
        "education": found_education,
        "experience": [f"{experience_years} years"] if experience_years else [],
        "locations": found_locations,
        "job_titles": found_titles,
        "experience_years": experience_years,
        "summary": summary,
    }
