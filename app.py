import json
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st


st.set_page_config(page_title="Betty Ingestion Assistant", layout="wide")


# -------------------------------
# CMS DETECTION
# -------------------------------
def detect_cms_from_website(url: str):
    if not url:
        return "Unknown", "Enter a website URL."

    test_url = url.strip()
    if not test_url.startswith("http://") and not test_url.startswith("https://"):
        test_url = f"https://{test_url}"

    try:
        response = requests.get(
            test_url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        html = response.text.lower()
        headers_text = " ".join(f"{k}: {v}" for k, v in response.headers.items()).lower()
        combined = html + "\n" + headers_text

        checks = [
            ("WordPress", ["wp-content", "wp-json", "wordpress"]),
            ("Drupal", ["drupal-settings-json", "/sites/default/files", "drupal"]),
            ("Sitefinity", ["sitefinity", "sf_", "telerik sitefinity"]),
            ("DNN", ["dotnetnuke", "__dnnvariable", "dnn"]),
            ("Umbraco", ["umbraco", "umbui", "umbraco_settings"]),
            ("Storyblok", ["storyblok", "storyblok-js-client", "storyblok.com"]),
        ]

        for cms_name, markers in checks:
            if any(marker in combined for marker in markers):
                return cms_name, f"Detected CMS: {cms_name}"

        return "Unknown", "CMS not detected."
    except Exception as e:
        return "Unknown", f"Error scanning site: {e}"


# -------------------------------
# SITEMAP DETECTION
# -------------------------------
def detect_sitemap(url: str):
    if not url:
        return False, ""

    base = url.strip()
    if not base.startswith("http://") and not base.startswith("https://"):
        base = f"https://{base}"
    base = base.rstrip("/")

    candidates = [
        f"{base}/sitemap.xml",
        f"{base}/sitemap_index.xml",
        f"{base}/wp-sitemap.xml",
        f"{base}/sitemap-index.xml",
    ]

    for candidate in candidates:
        try:
            response = requests.get(candidate, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            content = response.text.lower()
            content_type = response.headers.get("Content-Type", "").lower()
            if response.status_code == 200 and (
                "<urlset" in content or "<sitemapindex" in content or "xml" in content_type
            ):
                return True, candidate
        except Exception:
            continue

    return False, ""


# -------------------------------
# SITEMAP PAGE COUNT
# -------------------------------
def count_urls_in_sitemap(sitemap_url: str):
    if not sitemap_url:
        return None

    try:
        visited = set()

        def fetch_count(url):
            if url in visited:
                return 0
            visited.add(url)

            response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            text = response.text
            lower = text.lower()

            if "<urlset" in lower:
                return text.count("<url>")

            if "<sitemapindex" in lower:
                child_sitemaps = []
                parts = text.split("<loc>")
                for part in parts[1:]:
                    loc = part.split("</loc>")[0].strip()
                    if loc:
                        child_sitemaps.append(loc)

                total = 0
                for child in child_sitemaps:
                    total += fetch_count(child)
                return total

            return 0

        return fetch_count(sitemap_url)
    except Exception:
        return None


# -------------------------------
# SITEMAP INVENTORY
# -------------------------------
def classify_sitemap_url(url: str):
    lower = url.lower()

    if lower.endswith(".pdf"):
        return "PDF", "Document"
    if any(ext in lower for ext in [".mp4", ".mov", ".wmv", ".avi", ".m4v"]):
        return "Video File", "Video"
    if any(ext in lower for ext in [".mp3", ".wav", ".m4a"]):
        return "Audio File", "Audio"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "YouTube", "Video"
    if "/webinar/" in lower or "/webinars/" in lower:
        return "Webinar", "Video/HTML"
    if "/blog/" in lower or "/news/" in lower or "/articles/" in lower:
        return "Blog/Article", "HTML"
    if "/journal/" in lower or "/journals/" in lower:
        return "Journal", "HTML"
    if "/forum/" in lower or "/community/" in lower or "/discussion/" in lower:
        return "Forum", "HTML"
    if "/jobs/" in lower or "/careers/" in lower or "/job-board/" in lower:
        return "Job Board", "HTML"
    if "/events/" in lower or "/event/" in lower:
        return "Event", "HTML"
    if "/podcast/" in lower or "/podcasts/" in lower:
        return "Podcast", "Audio/HTML"
    if "/video/" in lower or "/videos/" in lower:
        return "Video Page", "HTML/Video"
    if "/marketplace/" in lower:
        return "Marketplace", "HTML"
    if "/white-paper" in lower or "/whitepaper" in lower:
        return "White Paper", "Document/HTML"
    if "/case-study" in lower or "/case-studies/" in lower:
        return "Case Study", "Document/HTML"
    return "Page", "HTML"


def extract_sitemap_inventory(sitemap_url: str, max_urls: int = 2000):
    if not sitemap_url:
        return []

    try:
        visited = set()
        collected = []

        def fetch_urls(url):
            if url in visited or len(collected) >= max_urls:
                return
            visited.add(url)

            response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            text = response.text
            lower = text.lower()

            if "<urlset" in lower:
                parts = text.split("<url>")
                for part in parts[1:]:
                    if "<loc>" in part and "</loc>" in part:
                        loc = part.split("<loc>", 1)[1].split("</loc>", 1)[0].strip()
                        category, asset_type = classify_sitemap_url(loc)
                        collected.append(
                            {"url": loc, "category": category, "asset_type": asset_type}
                        )
                        if len(collected) >= max_urls:
                            break
            elif "<sitemapindex" in lower:
                parts = text.split("<loc>")
                for part in parts[1:]:
                    child = part.split("</loc>", 1)[0].strip()
                    if child:
                        fetch_urls(child)
                        if len(collected) >= max_urls:
                            break

        fetch_urls(sitemap_url)
        return collected
    except Exception:
        return []


# -------------------------------
# API DISCOVERY
# -------------------------------
def discover_api_endpoints(base_url: str, cms: str):
    if not base_url:
        return []

    site = base_url.strip()
    if not site.startswith("http://") and not site.startswith("https://"):
        site = f"https://{site}"
    site = site.rstrip("/")

    cms_paths = {
        "WordPress": [
            "/wp-json/",
            "/wp-json/wp/v2/posts",
            "/wp-json/wp/v2/pages",
        ],
        "Drupal": [
            "/jsonapi",
            "/jsonapi/node/article",
        ],
        "Sitefinity": [
            "/api/default/",
            "/api/default/pages",
        ],
        "Umbraco": [
            "/umbraco/api/",
            "/umbraco/delivery/api/v1/content",
        ],
        "DNN": [
            "/API/",
            "/DesktopModules/",
        ],
        "Storyblok": [
            "/v2/cdn/stories",
        ],
    }

    results = []
    for path in cms_paths.get(cms, []):
        full_url = f"{site}{path}"
        try:
            response = requests.get(
                full_url,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            results.append(
                {
                    "endpoint": full_url,
                    "status_code": response.status_code,
                    "reachable": response.status_code < 400,
                }
            )
        except Exception:
            results.append(
                {
                    "endpoint": full_url,
                    "status_code": "error",
                    "reachable": False,
                }
            )
    return results


# -------------------------------
# HELPERS
# -------------------------------
def has_docs(content_types):
    doc_types = {
        "PDFs",
        "White Papers",
        "Case Studies",
        "Ebooks",
        "Journals",
        "Blog",
        "Job Board",
        "Moderated Forum",
    }
    return any(item in doc_types for item in content_types)


def has_media(content_types):
    media_types = {"Podcasts", "Webinars", "Videos", "YouTube"}
    return any(item in media_types for item in content_types)


def suggest_sources_from_content_types(content_types):
    suggestions = []
    if any(item in content_types for item in ["HTML pages", "Blog", "Job Board", "Moderated Forum", "Marketplace"]):
        suggestions.append("Website HTML content")
    if any(item in content_types for item in ["PDFs", "White Papers", "Case Studies", "Ebooks", "Journals"]):
        suggestions.append("Documents / PDF library")
    if "RSS Feeds" in content_types or "Blog" in content_types:
        suggestions.append("RSS feeds")
    if "YouTube" in content_types:
        suggestions.append("YouTube playlists or channels")
    if any(item in content_types for item in ["Podcasts", "Webinars", "Videos"]):
        suggestions.append("Transcript-based media sources")
    return suggestions or ["Website content review needed"]


def auto_recommend_method(cms, content_types, sitemap_found=False, public_content="Yes"):
    if "YouTube" in content_types and len(content_types) <= 2:
        return "YouTube Handler"

    if any(item in content_types for item in ["PDFs", "White Papers", "Case Studies", "Ebooks", "Journals"]) and len(content_types) <= 3:
        return "SFTP"

    if cms == "WordPress" and public_content == "Yes":
        return "WordPress Handler"

    if cms in {"WordPress", "Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok"}:
        return "API"

    if sitemap_found:
        return "Sitemap"

    if "RSS Feeds" in content_types or "Blog" in content_types:
        return "RSS"

    return "Crawler"


def primary_method(data):
    cms = data["cms"]
    preferred = data["preferred_method"]
    content_types = data["content_types"]
    public_content = data["public_content"]

    if preferred == "Sitemap":
        return "Sitemap Ingestion"
    if preferred == "SFTP":
        return "SFTP Document Ingestion"
    if preferred == "YouTube Handler":
        return "YouTube Handler"
    if preferred == "Google Handler":
        return "Google Handler"
    if preferred == "Direct Upload":
        return "Direct Upload"
    if preferred == "Upload Sheet":
        return "Upload Sheet Workflow"
    if preferred == "WordPress Handler":
        return "WordPress Handler" if public_content == "Yes" else "API Integration"
    if cms == "WordPress" and public_content == "Yes":
        return "WordPress Handler"
    if cms in {"WordPress", "Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok"}:
        return "API Integration"
    if preferred == "API":
        return "API Integration"
    if preferred == "RSS" or "RSS Feeds" in content_types:
        return "RSS Feed Ingestion"
    return "Web Crawler"


def complexity_score(data):
    score = 1
    notes = []

    if data.get("cms") in {"Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok"}:
        score += 1
        notes.append("specialized CMS")
    if data.get("member_content") == "Yes" or data.get("content_login") == "Yes":
        score += 2
        notes.append("gated content")
    if data.get("separate_instances") == "Yes":
        score += 2
        notes.append("dual instances")
    if has_docs(data.get("content_types", [])):
        score += 1
        notes.append("documents")
    if has_media(data.get("content_types", [])):
        score += 1
        notes.append("media/transcripts")
    if data.get("pdf_text_based") == "No":
        score += 2
        notes.append("non-text PDFs")
    if data.get("transcripts_available") == "No":
        score += 2
        notes.append("missing transcripts")
    if data.get("sitemap_page_count"):
        count = data.get("sitemap_page_count")
        if count > 500:
            score += 2
            notes.append("large sitemap")
        elif count > 150:
            score += 1
            notes.append("medium sitemap")
    if len(data.get("content_types", [])) >= 5:
        score += 1
        notes.append("mixed content set")

    if score <= 3:
        label = "Low"
    elif score <= 6:
        label = "Medium"
    else:
        label = "High"

    return score, label, notes


def generate_strategy(data):
    method = primary_method(data)
    cms = data["cms"]
    client_name = data["client_name"] or "this client"
    content_types = data["content_types"]

    lines = [f"**Primary Method: {method}**", ""]

    if method == "Sitemap Ingestion":
        lines.extend([
            "Sitemap ingestion is recommended when a clean XML sitemap is available and API access is not the best fit.",
            "",
            "**Why this works well:**",
            "- Useful for structured website discovery",
            "- Helps identify broad public site coverage",
            "- Good fallback when API access is unavailable",
        ])
    elif method == "SFTP Document Ingestion":
        lines.extend([
            "SFTP ingestion is the best fit when the client will deliver files directly rather than expose content through a live platform.",
            "",
            "**Why this works well:**",
            "- Good for document libraries and controlled uploads",
            "- Useful for ebooks, PDFs, and other file-based content",
            "- Helps when direct site access is limited",
        ])
    elif method == "YouTube Handler":
        lines.extend([
            "A YouTube handler is the best fit for video-heavy learning from channels or playlists.",
            "",
            "**Why this works well:**",
            "- Supports channel and playlist-based ingestion",
            "- Best for video libraries with captions enabled",
            "- Easier to maintain for ongoing video publishing",
        ])
    elif method == "Google Handler":
        lines.extend([
            "A Google handler is recommended when source content is maintained in Google assets such as Drive-based materials.",
            "",
            "**Why this works well:**",
            "- Useful for controlled document sets",
            "- Can simplify internal file-based delivery",
            "- Helps centralize managed content sources",
        ])
    elif method == "Direct Upload":
        lines.extend([
            "Direct upload is recommended when content will be manually supplied for ingestion in batches.",
            "",
            "**Why this works well:**",
            "- Fast for smaller content sets",
            "- Good for one-time uploads",
            "- Useful when no integration path exists",
        ])
    elif method == "Upload Sheet Workflow":
        lines.extend([
            "An upload sheet workflow is recommended when files and URLs need to be mapped in a structured handoff.",
            "",
            "**Why this works well:**",
            "- Standardizes content mapping",
            "- Helpful for mixed source sets",
            "- Creates a cleaner implementation handoff",
        ])
    elif method == "WordPress Handler":
        lines.extend([
            "A WordPress handler is recommended because this is a WordPress site and the primary focus is public content only.",
            "",
            "**Why this works well:**",
            "- Tailored to WordPress public content structures",
            "- Good for recurring public site updates",
            "- Supports clean ingestion planning for WordPress clients",
        ])
    elif method == "API Integration":
        if cms in {"WordPress", "Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok"}:
            lines.append(
                f"The site appears to use **{cms}**, so API ingestion is the best first option for {client_name}."
            )
        else:
            lines.append("API ingestion is the preferred approach based on the information provided.")
        lines.extend([
            "",
            "**Why this works well:**",
            "- More structured and reliable than crawling",
            "- Easier to keep content current",
            "- Better for large or complex sites",
        ])
    elif method == "RSS Feed Ingestion":
        lines.extend([
            "RSS feed ingestion is the best current fit based on the available information.",
            "",
            "**Why this works well:**",
            "- Simpler setup than API work",
            "- Useful for article/news style updates",
            "- Good backup when API access is limited",
        ])
    else:
        lines.extend([
            "A crawler is the most practical option when API, sitemap, or feed access is unavailable.",
            "",
            "**Why this works well:**",
            "- Can cover broad public website content",
            "- Useful when technical access is limited",
            "- Good fallback for basic HTML content",
        ])

    if "YouTube" in content_types:
        lines.extend([
            "",
            "**YouTube handling:**",
            "- Use Betty's YouTube/playlist workflow where available",
            "- Captions or transcripts should be enabled",
            "- Playlists should be organized before ingestion",
        ])

    if has_docs(content_types):
        lines.extend([
            "",
            "**Document handling:**",
            "- Text-based PDFs are preferred",
            "- Large document sets may be better delivered by SFTP",
        ])
        if data["pdf_text_based"] == "No":
            lines.append("- Current documents may need text conversion before ingestion")
        elif data["pdf_text_based"] == "Unknown":
            lines.append("- PDF text quality still needs to be confirmed")

    if data["member_content"] == "Yes" or data["content_login"] == "Yes":
        lines.extend([
            "",
            "**Gated/member content:**",
            "- Login credentials or another access method will be required",
            "- Protected areas should be clearly identified during setup",
        ])

    if data["separate_instances"] == "Yes":
        lines.extend([
            "",
            "**Instance recommendation:**",
            "- Configure separate Betty instances for public and member content",
        ])

    return "\n".join(lines)


def generate_secondary_method(data):
    method = primary_method(data)
    cms = data["cms"]
    preferred = data["preferred_method"]
    content_types = data["content_types"]
    sitemap_found = data.get("sitemap_found", False)
    sitemap_message = data.get("sitemap_message", "")

    if method == "Sitemap Ingestion":
        return """**Secondary Method: Web Crawler**

If a sitemap is incomplete or unavailable, a crawler can be used to cover the remaining public content."""
    if method == "SFTP Document Ingestion":
        return """**Secondary Method: Direct Upload**

If SFTP is delayed or unavailable, direct upload can support smaller batches of files as a fallback."""
    if method == "YouTube Handler":
        return """**Secondary Method: Direct Upload or Transcript Upload**

If the channel structure is not ready, direct file or transcript uploads can help bridge the gap."""
    if method == "Google Handler":
        return """**Secondary Method: Direct Upload**

If Google-based access is limited, direct upload can be used for approved source files."""
    if method == "Direct Upload":
        return """**Secondary Method: SFTP Document Ingestion**

If upload volume grows, SFTP may become the better long-term delivery option."""
    if method == "Upload Sheet Workflow":
        return """**Secondary Method: Direct Upload**

If the mapping sheet is incomplete, direct upload can temporarily support priority files."""
    if method == "WordPress Handler":
        return """**Secondary Method: API Integration**

API remains the fallback if the WordPress public-content workflow is not the best fit."""
    if method == "API Integration":
        if sitemap_found:
            return f"""**Secondary Method: Sitemap Ingestion**

A sitemap was found for this site at:
{sitemap_message}

If API access is delayed or unavailable, sitemap ingestion is the strongest next option for public content discovery."""
        if preferred == "RSS" or "RSS Feeds" in content_types:
            return """**Secondary Method: RSS Feed Ingestion**

If API access is delayed or limited, RSS can serve as a clean backup for regularly updated content."""
        return """**Secondary Method: Web Crawler**

If API access is not available, use a crawler for public content areas."""
    if method == "RSS Feed Ingestion":
        return """**Secondary Method: Web Crawler**

If feed coverage is incomplete, use a crawler for the remaining public web content."""
    if cms in {"WordPress", "Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok"}:
        return f"""**Secondary Method: API Integration**

Because the site uses **{cms}**, API should remain under consideration as a stronger long-term option."""
    return """**Secondary Method: Manual/SFTP Document Support**

For document-heavy projects, SFTP can supplement the main ingestion method when direct platform access is limited."""


def generate_internal_notes(data):
    score, label, notes = complexity_score(data)
    lines = [
        f"**Client:** {data['client_name'] or 'Not provided'}",
        f"**Website:** {data['website'] or 'Not provided'}",
        f"**CMS:** {data['cms']}",
        f"**Recommended method:** {primary_method(data)}",
        f"**Separate instances:** {data['separate_instances']}",
        f"**Complexity:** {label} ({score})",
        f"**Complexity factors:** {', '.join(notes) if notes else 'standard setup'}",
        f"**Content types:** {', '.join(data['content_types']) if data['content_types'] else 'None selected'}",
    ]

    if data.get("sitemap_found"):
        lines.append(f"**Sitemap found:** {data.get('sitemap_message', '')}")
    if data.get("sitemap_page_count") is not None:
        lines.append(f"**Sitemap page count:** {data.get('sitemap_page_count')}")
    if data.get("api_endpoints"):
        reachable = [x['endpoint'] for x in data['api_endpoints'] if x['reachable']]
        lines.append(f"**Reachable API endpoints:** {len(reachable)}")
    if has_docs(data["content_types"]):
        lines.append(f"**PDF text status:** {data['pdf_text_based']}")
    if has_media(data["content_types"]):
        lines.append(f"**Transcript status:** {data['transcripts_available']}")
    if data["additional_notes"].strip():
        lines.append(f"**Notes:** {data['additional_notes'].strip()}")

    return "\n".join(lines)


def generate_draft_email(data):
    client_name = data["client_name"].strip() if data["client_name"].strip() else "there"
    method = primary_method(data)
    intro_name = client_name.split()[0] if client_name != "there" else client_name

    email = [
        f"Hi {intro_name},",
        "",
        "Thank you for sharing your content and platform details.",
        "",
        f"Based on what we have so far, our recommended ingestion approach is **{method}**.",
        "",
        "At a high level, this should give us the best path to bring your content into Betty while keeping the setup as clean and scalable as possible.",
        "",
        "From here, the main next steps are:",
        "- confirm access details and any required credentials",
        "- review the final content scope",
        "- validate any document or transcript requirements",
        "- prepare for test ingestion",
    ]

    if data.get("sitemap_found"):
        email.append(
            f"- We also found a sitemap that may support public content discovery: {data.get('sitemap_message', '')}."
        )
    if data.get("api_endpoints"):
        reachable = [x['endpoint'] for x in data['api_endpoints'] if x['reachable']]
        if reachable:
            email.append("- We also identified likely API endpoints that can help technical discovery move faster.")
    if data["member_content"] == "Yes" or data["content_login"] == "Yes":
        email.append("- For gated content, we will also need login credentials or another approved access method.")
    if has_docs(data["content_types"]):
        email.append("- For document-heavy sources, text-based PDFs are preferred, and SFTP may be the best option for larger document sets.")
    if has_media(data["content_types"]):
        email.append("- For audio or video content, transcripts or captions will help ensure Betty can learn from that material effectively.")

    email.extend([
        "",
        "Once we have those items, we can finalize the ingestion setup and move into testing.",
        "",
        "Best,",
        "Tracy Barkley",
        "Betty Support",
    ])

    return "\n".join(email)


def quick_risk_label(risks_text):
    if "🚨" in risks_text or "Blocker" in risks_text:
        return "High"
    if "⚠️" in risks_text or "Risk" in risks_text:
        return "Medium"
    return "Low"


def generate_risks(data):
    risks = []
    if has_docs(data["content_types"]) and data["pdf_text_based"] == "No":
        risks.extend([
            "🚨 **Blocker: non-text PDFs**",
            "- Documents may need conversion before Betty can learn from them reliably",
            "",
        ])
    if has_media(data["content_types"]) and data["transcripts_available"] == "No":
        risks.extend([
            "🚨 **Blocker: missing transcripts/captions**",
            "- Audio and video content needs transcripts for strong ingestion quality",
            "",
        ])
    if data["cms"] == "Unknown":
        risks.extend([
            "⚠️ **Risk: CMS is unknown**",
            "- Technical discovery is still needed before finalizing strategy",
            "",
        ])
    if data["content_login"] == "Yes":
        risks.extend([
            "⚠️ **Risk: gated content complexity**",
            "- Protected content may require extra testing, credentials, or alternate access methods",
            "",
        ])
    if not data.get("sitemap_found") and data["preferred_method"] == "Sitemap":
        risks.extend([
            "⚠️ **Risk: sitemap not confirmed**",
            "- A sitemap method was chosen, but no sitemap was detected at common sitemap URLs",
            "",
        ])
    if not risks:
        return "✅ **No major blockers identified based on the current inputs.**"
    return "\n".join(risks).strip()


# -------------------------------
# SESSION STATE
# -------------------------------
for key, default in {
    "submitted": False,
    "cms": "Unknown",
    "detection_message": "",
    "suggested_method": "",
    "suggested_sources": [],
    "sitemap_found": False,
    "sitemap_message": "",
    "sitemap_page_count": None,
    "sitemap_inventory": [],
    "api_endpoints": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# -------------------------------
# HEADER
# -------------------------------
header = st.container()
with header:
    logo_col, title_col = st.columns([1, 6])
    with logo_col:
        logo_path = Path("betty_logo.png")
        if logo_path.exists():
            st.image(str(logo_path), width=80)
    with title_col:
        st.markdown("## Betty Ingestion Assistant")
        st.markdown(
            "<span style='color:#7AD7F0;font-size:16px;'>AI-powered ingestion planning for Betty implementations</span>",
            unsafe_allow_html=True,
        )

st.markdown("---")
st.caption("Working prototype for generating ingestion recommendations, blockers, client-ready next steps, and technical discovery hints.")


# -------------------------------
# FORM
# -------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Client Information")
    client_name = st.text_input("Client Name")
    website = st.text_input("Website", placeholder="https://example.com")
    public_content = st.radio("Public Content Only?", ["Yes", "No"], horizontal=True)

    if st.button("🔎 Detect CMS + Sitemap + API", use_container_width=True):
        cms, detection_message = detect_cms_from_website(website)
        st.session_state.cms = cms
        st.session_state.detection_message = detection_message

        sitemap_found, sitemap_message = detect_sitemap(website)
        st.session_state.sitemap_found = sitemap_found
        st.session_state.sitemap_message = sitemap_message
        st.session_state.sitemap_page_count = count_urls_in_sitemap(sitemap_message) if sitemap_found else None
        st.session_state.sitemap_inventory = extract_sitemap_inventory(sitemap_message) if sitemap_found else []
        st.session_state.api_endpoints = discover_api_endpoints(website, cms)

    if st.session_state.detection_message:
        if st.session_state.cms != "Unknown":
            st.success(st.session_state.detection_message)
        else:
            st.info(st.session_state.detection_message)

    if st.session_state.sitemap_found:
        st.success(f"Sitemap found: {st.session_state.sitemap_message}")
        if st.session_state.sitemap_page_count is not None:
            st.caption(f"Approximate sitemap page count: {st.session_state.sitemap_page_count}")

    st.subheader("Platform and Access")
    cms_options = ["WordPress", "Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok", "Other", "Unknown"]
    detected = st.session_state.get("cms", "Unknown")
    default_index = cms_options.index(detected) if detected in cms_options else len(cms_options) - 1
    cms = st.selectbox("CMS Platform", cms_options, index=default_index)
    member_content = st.radio("Member or gated content?", ["Yes", "No"], horizontal=True)
    content_login = st.radio("Content behind login?", ["Yes", "No"], horizontal=True)
    separate_instances = st.radio("Need separate public and member instances?", ["Yes", "No"], horizontal=True)
    preferred_method = st.selectbox(
        "Preferred ingestion method",
        [
            "API",
            "Sitemap",
            "RSS",
            "Crawler",
            "SFTP",
            "YouTube Handler",
            "Google Handler",
            "Direct Upload",
            "Upload Sheet",
            "WordPress Handler",
            "Unsure",
        ],
    )

with right:
    st.subheader("Content Details")
    content_types = st.multiselect(
        "Content Types",
        [
            "HTML pages",
            "PDFs",
            "White Papers",
            "Case Studies",
            "Marketplace",
            "Blog",
            "Job Board",
            "Moderated Forum",
            "Journals",
            "Podcasts",
            "Webinars",
            "Videos",
            "YouTube",
            "RSS Feeds",
            "Ebooks",
        ],
    )

    st.session_state.suggested_sources = suggest_sources_from_content_types(content_types)
    st.session_state.suggested_method = auto_recommend_method(
        cms,
        content_types,
        st.session_state.get("sitemap_found", False),
        public_content,
    )

    pdf_text_based = None
    transcripts_available = None

    if has_docs(content_types):
        pdf_text_based = st.radio("Are PDFs text-based?", ["Yes", "No", "Unknown"], horizontal=True)

    if has_media(content_types):
        transcripts_available = st.radio(
            "Are transcripts/captions available?",
            ["Yes", "No", "Unknown"],
            horizontal=True,
        )

    additional_notes = st.text_area("Additional notes", height=160)

if st.button("🚀 Generate Recommendation", type="primary", use_container_width=True):
    st.session_state.submitted = True


# -------------------------------
# RESULTS
# -------------------------------
if st.session_state.submitted:
    form_data = {
        "client_name": client_name,
        "website": website,
        "cms": cms,
        "public_content": public_content,
        "member_content": member_content,
        "content_login": content_login,
        "separate_instances": separate_instances,
        "preferred_method": preferred_method,
        "content_types": content_types,
        "pdf_text_based": pdf_text_based,
        "transcripts_available": transcripts_available,
        "additional_notes": additional_notes,
        "sitemap_found": st.session_state.get("sitemap_found", False),
        "sitemap_message": st.session_state.get("sitemap_message", ""),
        "sitemap_page_count": st.session_state.get("sitemap_page_count", None),
        "sitemap_inventory": st.session_state.get("sitemap_inventory", []),
        "api_endpoints": st.session_state.get("api_endpoints", []),
    }

    strategy = generate_strategy(form_data)
    secondary = generate_secondary_method(form_data)
    risks = generate_risks(form_data)
    internal_notes = generate_internal_notes(form_data)
    draft_email = generate_draft_email(form_data)
    score, complexity_label, complexity_notes = complexity_score(form_data)

    st.divider()

    st.markdown("## Betty Auto Insights")
    insight_col1, insight_col2 = st.columns(2)
    with insight_col1:
        st.info(f"**Suggested Method:** {st.session_state.get('suggested_method', 'Review needed')}")
    with insight_col2:
        st.info("**Likely Content Sources:** " + ", ".join(st.session_state.get("suggested_sources", [])))

    st.markdown("## Betty Quick Summary")
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        st.metric("Recommended Method", primary_method(form_data))
    with metric_col2:
        st.metric("Risk Level", quick_risk_label(risks))
    with metric_col3:
        st.metric("Complexity", complexity_label)
    with metric_col4:
        if form_data.get("sitemap_page_count") is not None:
            st.metric("Sitemap Pages", form_data.get("sitemap_page_count"))
        else:
            st.metric("Complexity Score", score)

    tabs = st.tabs([
        "Strategy",
        "Secondary Method",
        "Risks",
        "Complexity",
        "API Discovery",
        "Sitemap Inventory",
        "Internal Notes",
        "Draft Email",
    ])

    with tabs[0]:
        st.markdown(strategy)

    with tabs[1]:
        st.markdown(secondary)

    with tabs[2]:
        st.markdown(risks)

    with tabs[3]:
        st.markdown(f"### Complexity: {complexity_label} ({score})")
        if complexity_notes:
            st.write("This score reflects:")
            for note in complexity_notes:
                st.write(f"- {note}")
        else:
            st.write("- standard setup")

    with tabs[4]:
        api_rows = form_data.get("api_endpoints", [])
        if api_rows:
            st.caption("Likely CMS-specific API endpoints discovered during technical scan.")
            st.dataframe(api_rows, use_container_width=True)
        else:
            st.info("No API endpoints discovered for the selected CMS.")

    with tabs[5]:
        inventory = form_data.get("sitemap_inventory", [])
        if inventory:
            summary_counts = {}
            for row in inventory:
                key = row["category"]
                summary_counts[key] = summary_counts.get(key, 0) + 1

            st.caption("Detected sitemap items and estimated content type.")
            st.markdown("### Inventory Counts by Category")
            count_items = sorted(summary_counts.items(), key=lambda x: (-x[1], x[0]))
            count_cols = st.columns(3)
            for idx, (category, count) in enumerate(count_items):
                with count_cols[idx % 3]:
                    st.metric(category, count)

            st.markdown("### Inventory Breakdown Chart")
            chart_rows = [{"category": item[0], "count": item[1]} for item in count_items]
            st.bar_chart(chart_rows, x="category", y="count")

            st.markdown("### Inventory Table")
            st.dataframe(inventory, use_container_width=True)
        else:
            st.info("No sitemap inventory available.")

    with tabs[6]:
        st.markdown(internal_notes)

    with tabs[7]:
        st.text(draft_email)

    st.divider()
    safe_name = client_name.strip().replace(" ", "_") or "client"
    export_col1, export_col2 = st.columns(2)

    with export_col1:
        json_export = json.dumps(form_data, indent=2)
        st.download_button(
            label="📥 Download JSON",
            data=json_export,
            file_name=f"ingestion_{safe_name}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
        )

    with export_col2:
        inventory = form_data.get("sitemap_inventory", [])
        csv_export = "url,category,asset_type\n"
        for row in inventory:
            csv_export += f'"{row["url"]}","{row["category"]}","{row["asset_type"]}"\n'
        st.download_button(
            label="🗂️ Download Sitemap CSV",
            data=csv_export,
            file_name=f"sitemap_inventory_{safe_name}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
