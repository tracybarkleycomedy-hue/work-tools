import json
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st


st.set_page_config(page_title="Betty Ingestion Assistant", layout="wide")


# --------------------------------------------------
# CMS DETECTION
# --------------------------------------------------
def detect_cms_from_website(url: str):
    if not url:
        return "Unknown", "Enter a website URL."

    site = url.strip()
    if not site.startswith("http://") and not site.startswith("https://"):
        site = f"https://{site}"

    try:
        response = requests.get(
            site,
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
            ("YM", ["yourmembership", "ymcdn", "yourmembership.com"]),
        ]

        for cms_name, markers in checks:
            if any(marker in combined for marker in markers):
                return cms_name, f"Detected CMS: {cms_name}"

        return "Unknown", "CMS not detected."

    except Exception as e:
        return "Unknown", f"Error scanning site: {e}"


# --------------------------------------------------
# MEMBER LOGIN DETECTION
# --------------------------------------------------
def detect_member_login(url: str):
    if not url:
        return False, []

    site = url.strip()
    if not site.startswith("http://") and not site.startswith("https://"):
        site = f"https://{site}"

    signals = []

    try:
        response = requests.get(
            site,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        html = response.text.lower()

        login_markers = [
            "member login",
            "member sign in",
            "sign in",
            "login",
            "log in",
            "my account",
            "member portal",
            "members only",
            "dashboard",
            "sso",
            "single sign-on",
            "auth",
            "/login",
            "/signin",
            "/member-login",
            "/members",
        ]

        for marker in login_markers:
            if marker in html:
                signals.append(marker)

        return len(signals) > 0, sorted(list(set(signals)))

    except Exception:
        return False, []


# --------------------------------------------------
# EXTERNAL PLATFORM DETECTION
# --------------------------------------------------
def detect_external_platforms(url: str):
    results = {
        "vimeo": False,
        "google_drive": False,
        "sharepoint": False,
        "signals": [],
    }

    if not url:
        return results

    site = url.strip()
    if not site.startswith("http://") and not site.startswith("https://"):
        site = f"https://{site}"

    try:
        response = requests.get(
            site,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        html = response.text.lower()

        if "vimeo.com" in html:
            results["vimeo"] = True
            results["signals"].append("Vimeo embeds/links")

        if any(marker in html for marker in ["drive.google.com", "docs.google.com", "googleusercontent.com"]):
            results["google_drive"] = True
            results["signals"].append("Google Drive/Docs content")

        if any(marker in html for marker in [".sharepoint.com", "sharepoint", "onedrive"]):
            results["sharepoint"] = True
            results["signals"].append("SharePoint/OneDrive content")

        return results

    except Exception:
        return results


# --------------------------------------------------
# SITEMAP DETECTION
# --------------------------------------------------
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
            response = requests.get(
                candidate,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            content = response.text.lower()
            content_type = response.headers.get("Content-Type", "").lower()

            if response.status_code == 200 and (
                "<urlset" in content
                or "<sitemapindex" in content
                or "xml" in content_type
            ):
                return True, candidate

        except Exception:
            continue

    return False, ""


# --------------------------------------------------
# SITEMAP PAGE COUNT
# --------------------------------------------------
def count_urls_in_sitemap(sitemap_url: str):
    if not sitemap_url:
        return None

    try:
        visited = set()

        def fetch_count(url):
            if url in visited:
                return 0

            visited.add(url)

            response = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            response.raise_for_status()

            text = response.text
            lower = text.lower()

            if "<urlset" in lower:
                return text.count("<url>")

            if "<sitemapindex" in lower:
                child_sitemaps = []

                for part in text.split("<loc>")[1:]:
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


# --------------------------------------------------
# SITEMAP INVENTORY
# --------------------------------------------------
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
    if "vimeo.com" in lower:
        return "Vimeo", "Video"
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
    if "/publication/" in lower or "/publications/" in lower:
        return "Publication", "HTML/Document"
    if "/guide/" in lower or "/guides/" in lower:
        return "Guide", "HTML/Document"
    if "/course/" in lower or "/courses/" in lower or "/education/" in lower:
        return "Education/Course", "HTML"

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

            response = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            response.raise_for_status()

            text = response.text
            lower = text.lower()

            if "<urlset" in lower:
                for part in text.split("<url>")[1:]:
                    if "<loc>" in part and "</loc>" in part:
                        loc = part.split("<loc>", 1)[1].split("</loc>", 1)[0].strip()
                        category, asset_type = classify_sitemap_url(loc)

                        collected.append(
                            {
                                "url": loc,
                                "category": category,
                                "asset_type": asset_type,
                            }
                        )

                        if len(collected) >= max_urls:
                            break

            elif "<sitemapindex" in lower:
                for part in text.split("<loc>")[1:]:
                    child = part.split("</loc>", 1)[0].strip()

                    if child:
                        fetch_urls(child)

                    if len(collected) >= max_urls:
                        break

        fetch_urls(sitemap_url)

        return collected

    except Exception:
        return []


# --------------------------------------------------
# API DISCOVERY
# --------------------------------------------------
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
            "/wp-json/wp/v2/media",
        ],
        "Drupal": [
            "/jsonapi",
            "/jsonapi/node/article",
            "/jsonapi/node/page",
        ],
        "Sitefinity": [
            "/api/default/",
            "/api/default/pages",
            "/api/default/newsitems",
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
        "YM": [
            "/api",
            "/ams/api",
            "/members/api",
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


# --------------------------------------------------
# HELPERS
# --------------------------------------------------
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
        "Publications",
        "Guides",
        "Education/Courses",
    }

    return any(item in doc_types for item in content_types)


def has_media(content_types):
    media_types = {
        "Podcasts",
        "Webinars",
        "Videos",
        "YouTube",
        "Vimeo",
    }

    return any(item in media_types for item in content_types)


def suggest_sources_from_content_types(content_types):
    suggestions = []

    if any(
        item in content_types
        for item in ["HTML pages", "Blog", "Job Board", "Moderated Forum", "Marketplace"]
    ):
        suggestions.append("Website HTML content")

    if any(
        item in content_types
        for item in ["PDFs", "White Papers", "Case Studies", "Ebooks", "Journals", "Publications", "Guides"]
    ):
        suggestions.append("Documents / PDF library")

    if "RSS Feeds" in content_types or "Blog" in content_types:
        suggestions.append("RSS feeds")

    if "YouTube" in content_types:
        suggestions.append("YouTube playlists or channels")

    if "Vimeo" in content_types:
        suggestions.append("Vimeo videos / webinar library")

    if any(item in content_types for item in ["Podcasts", "Webinars", "Videos"]):
        suggestions.append("Transcript-based media sources")

    if "Education/Courses" in content_types:
        suggestions.append("Education/course content source")

    if "Google Drive" in content_types:
        suggestions.append("Google Drive / shared drive content")

    if "SharePoint" in content_types:
        suggestions.append("SharePoint / shared drive content")

    return suggestions or ["Website content review needed"]


def auto_recommend_method(
    cms,
    content_types,
    sitemap_found=False,
    public_content="Yes",
    member_login_found=False,
    vimeo_found=False,
    google_found=False,
    sharepoint_found=False,
):
    if "Vimeo" in content_types or vimeo_found:
        return "Vimeo Handler"

    if "Google Drive" in content_types or google_found:
        return "Google Handler"

    if "SharePoint" in content_types or sharepoint_found:
        return "Shared Drive Handler"

    if "YouTube" in content_types and len(content_types) <= 2:
        return "YouTube Handler"

    if any(
        item in content_types
        for item in ["PDFs", "White Papers", "Case Studies", "Ebooks", "Journals", "Publications", "Guides"]
    ) and len(content_types) <= 3:
        return "SFTP"

    if cms == "WordPress" and public_content == "Yes" and not member_login_found:
        return "WordPress Handler"

    if cms in {"WordPress", "Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok", "YM"}:
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
    if preferred == "Vimeo Handler":
        return "Vimeo Handler"
    if preferred == "Google Handler":
        return "Google Handler"
    if preferred == "SharePoint Handler":
        return "SharePoint Handler"
    if preferred == "Shared Drive Handler":
        return "Shared Drive Handler"
    if preferred == "Direct Upload":
        return "Direct Upload"
    if preferred == "Upload Sheet":
        return "Upload Sheet Workflow"

    if preferred == "WordPress Handler":
        if public_content == "Yes" and not data.get("member_login_found"):
            return "WordPress Handler"
        return "API Integration"

    if data.get("vimeo_found") or "Vimeo" in content_types:
        return "Vimeo Handler"

    if data.get("google_found") or "Google Drive" in content_types:
        return "Google Handler"

    if data.get("sharepoint_found") or "SharePoint" in content_types:
        return "Shared Drive Handler"

    if cms == "WordPress" and public_content == "Yes" and not data.get("member_login_found"):
        return "WordPress Handler"

    if cms in {"WordPress", "Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok", "YM"}:
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

    if data.get("cms") == "YM":
        score += 2
        notes.append("YM API complexity")

    if data.get("member_content") == "Yes" or data.get("content_login") == "Yes":
        score += 2
        notes.append("gated content")

    if data.get("member_login_found"):
        score += 2
        notes.append("member login detected")

    if data.get("separate_instances") == "Yes":
        score += 2
        notes.append("dual instances")

    if has_docs(data.get("content_types", [])):
        score += 1
        notes.append("documents")

    if has_media(data.get("content_types", [])):
        score += 1
        notes.append("media/transcripts")

    if data.get("vimeo_found"):
        score += 1
        notes.append("Vimeo detected")

    if data.get("google_found"):
        score += 1
        notes.append("Google Drive/Docs detected")

    if data.get("sharepoint_found"):
        score += 1
        notes.append("SharePoint/OneDrive detected")

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

    reachable_api = [x for x in data.get("api_endpoints", []) if x.get("reachable")]
    if data.get("cms") in {"WordPress", "Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok", "YM"} and not reachable_api:
        score += 1
        notes.append("API endpoints not confirmed")

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
        lines.extend(
            [
                "Sitemap ingestion is recommended when a clean XML sitemap is available and API access is not the best fit.",
                "",
                "**Why this works well:**",
                "- Useful for structured website discovery",
                "- Helps identify broad public site coverage",
                "- Good fallback when API access is unavailable",
            ]
        )

    elif method == "SFTP Document Ingestion":
        lines.extend(
            [
                "SFTP ingestion is recommended when the client will deliver files directly instead of exposing content through a live website or API.",
                "",
                "**Why this works well:**",
                "- Good for controlled document libraries",
                "- Useful for PDFs, publications, guides, and ebooks",
                "- Helps when documents do not have stable public URLs",
            ]
        )

    elif method == "Vimeo Handler":
        lines.extend(
            [
                "Vimeo Handler is recommended because Vimeo video/webinar content appears to be part of the source mix.",
                "",
                "**Why this works well:**",
                "- Supports video-heavy content planning",
                "- Helps separate video ingestion from standard webpage crawling",
                "- Transcripts or captions should be confirmed before ingestion",
            ]
        )

    elif method == "YouTube Handler":
        lines.extend(
            [
                "YouTube Handler is recommended for YouTube channel or playlist-based content.",
                "",
                "**Why this works well:**",
                "- Supports playlist-based ingestion",
                "- Best when captions/transcripts are available",
                "- Easier to maintain for ongoing video publishing",
            ]
        )

    elif method in ["Google Handler", "Shared Drive Handler", "SharePoint Handler"]:
        lines.extend(
            [
                f"{method} is recommended because shared-drive or externally hosted document content appears to be involved.",
                "",
                "**Why this works well:**",
                "- Helps avoid relying on crawler access to hosted files",
                "- Better for controlled document sets",
                "- Supports cleaner handoff if content is maintained in Drive or SharePoint",
            ]
        )

    elif method == "WordPress Handler":
        lines.extend(
            [
                "WordPress Handler is recommended because this appears to be a public WordPress site without member-login signals.",
                "",
                "**Why this works well:**",
                "- Tailored to public WordPress content structures",
                "- Good for recurring public updates",
                "- Better than a generic crawler when WordPress content is public and structured",
            ]
        )

    elif method == "API Integration":
        if cms == "YM":
            lines.extend(
                [
                    "The site appears to use **YM / YourMembership**, so API validation is recommended before finalizing ingestion.",
                    "",
                    "**YM / YourMembership notes:**",
                    "- YM implementations often require additional API validation",
                    "- Public/member separation should be reviewed carefully",
                    "- API access or add-ons may be required",
                    "- Crawler-only ingestion is usually not ideal for YM environments",
                ]
            )
        elif cms in {"WordPress", "Drupal", "Sitefinity", "DNN", "Umbraco", "Storyblok"}:
            lines.append(
                f"The site appears to use **{cms}**, so API ingestion is the best first option for {client_name}."
            )
            lines.extend(
                [
                    "",
                    "**Why this works well:**",
                    "- More structured and reliable than crawling",
                    "- Easier to keep content current",
                    "- Better for large or complex sites",
                ]
            )
        else:
            lines.append("API ingestion is the preferred approach based on the information provided.")

    elif method == "RSS Feed Ingestion":
        lines.extend(
            [
                "RSS feed ingestion is recommended for regularly updated content such as news, blogs, or article feeds.",
                "",
                "**Why this works well:**",
                "- Simpler than API work",
                "- Useful for article/news updates",
                "- Good backup when API access is limited",
            ]
        )

    else:
        lines.extend(
            [
                "A crawler is the most practical option when API, sitemap, feed, or handler access is unavailable.",
                "",
                "**Why this works well:**",
                "- Can cover broad public website content",
                "- Useful when technical access is limited",
                "- Good fallback for basic HTML content",
            ]
        )

    if data.get("member_login_found"):
        lines.extend(
            [
                "",
                "**Possible member login detected:**",
                "- This site appears to include login/member access signals",
                "- API or authenticated access should be prioritized over crawler-only ingestion",
                "- Do not rely only on WordPress Handler if gated/member content is involved",
                "- Request a member test account or approved credentials before finalizing ingestion scope",
            ]
        )

    if data.get("vimeo_found"):
        lines.extend(
            [
                "",
                "**Vimeo content detected:**",
                "- Vimeo webinar/video content appears present",
                "- Vimeo Handler or transcript workflow may be appropriate",
                "- Video transcripts/captions should be reviewed",
            ]
        )

    if data.get("google_found"):
        lines.extend(
            [
                "",
                "**Google Drive content detected:**",
                "- Google-hosted documents or shared drives appear present",
                "- Google Handler or Shared Drive ingestion may be appropriate",
            ]
        )

    if data.get("sharepoint_found"):
        lines.extend(
            [
                "",
                "**SharePoint/OneDrive content detected:**",
                "- SharePoint or OneDrive-hosted assets appear present",
                "- Shared Drive Handler may be preferred over crawler ingestion",
            ]
        )

    if has_docs(content_types):
        lines.extend(
            [
                "",
                "**Document handling:**",
                "- Text-based PDFs are preferred",
                "- Large document sets may be better delivered by SFTP or shared-drive workflows",
            ]
        )

        if data["pdf_text_based"] == "No":
            lines.append("- Current documents may need conversion before ingestion")
        elif data["pdf_text_based"] == "Unknown":
            lines.append("- PDF text quality still needs to be confirmed")

    if has_media(content_types):
        lines.extend(
            [
                "",
                "**Media handling:**",
                "- Audio/video content should have transcripts or captions",
                "- Webinar, podcast, YouTube, and Vimeo content should be mapped to transcript sources where possible",
            ]
        )

    if data["member_content"] == "Yes" or data["content_login"] == "Yes":
        lines.extend(
            [
                "",
                "**Gated/member content:**",
                "- Login credentials or another access method will be required",
                "- Protected areas should be clearly identified during setup",
            ]
        )

    if data["separate_instances"] == "Yes":
        lines.extend(
            [
                "",
                "**Instance recommendation:**",
                "- Configure separate Betty instances for public and member content",
            ]
        )

    return "\n".join(lines)


def generate_secondary_method(data):
    method = primary_method(data)

    if method in ["Vimeo Handler", "YouTube Handler"]:
        return """**Secondary Method: Transcript Upload or Direct Upload**

If the video handler workflow is not available, use transcripts or direct upload as the backup path."""

    if method in ["Google Handler", "Shared Drive Handler", "SharePoint Handler"]:
        return """**Secondary Method: SFTP or Direct Upload**

If shared-drive access is delayed, SFTP or direct upload can temporarily support approved document delivery."""

    if method == "WordPress Handler":
        return """**Secondary Method: API Integration**

API remains the fallback if the WordPress public-content workflow is not the best fit."""

    if method == "API Integration":
        if data.get("sitemap_found"):
            return f"""**Secondary Method: Sitemap Ingestion**

A sitemap was found:
{data.get("sitemap_message", "")}

If API access is delayed, sitemap ingestion is the strongest next option for public content discovery."""
        return """**Secondary Method: Web Crawler**

If API access is not available, use a crawler for public content areas."""

    if method == "Sitemap Ingestion":
        return """**Secondary Method: Web Crawler**

If the sitemap is incomplete or unavailable, a crawler can be used for remaining public content."""

    if method == "SFTP Document Ingestion":
        return """**Secondary Method: Direct Upload**

If SFTP is delayed, direct upload can support smaller batches of files."""

    return """**Secondary Method: Manual/SFTP Document Support**

For document-heavy projects, SFTP can supplement the main ingestion method when direct platform access is limited."""


def generate_risks(data):
    risks = []

    if data.get("member_login_found"):
        risks.extend(
            [
                "⚠️ **Risk: member login detected**",
                "- Site may contain gated or member-only content",
                "- WordPress Handler or crawler-only access may not be enough",
                "- Credentials or API access may be required",
                "",
            ]
        )

    if data.get("cms") == "YM":
        risks.extend(
            [
                "⚠️ **Risk: YM / YourMembership complexity**",
                "- YM often requires API validation or additional access paths",
                "- Member/public separation should be confirmed early",
                "",
            ]
        )

    if has_docs(data["content_types"]) and data["pdf_text_based"] == "No":
        risks.extend(
            [
                "🚨 **Blocker: non-text PDFs**",
                "- Documents may need conversion before Betty can learn from them reliably",
                "",
            ]
        )

    if has_media(data["content_types"]) and data["transcripts_available"] == "No":
        risks.extend(
            [
                "🚨 **Blocker: missing transcripts/captions**",
                "- Audio and video content needs transcripts for strong ingestion quality",
                "",
            ]
        )

    if data["cms"] == "Unknown":
        risks.extend(
            [
                "⚠️ **Risk: CMS is unknown**",
                "- Technical discovery is still needed before finalizing strategy",
                "",
            ]
        )

    if data["content_login"] == "Yes":
        risks.extend(
            [
                "⚠️ **Risk: gated content complexity**",
                "- Protected content may require credentials, API access, or alternate access methods",
                "",
            ]
        )

    if not data.get("sitemap_found") and data["preferred_method"] == "Sitemap":
        risks.extend(
            [
                "⚠️ **Risk: sitemap not confirmed**",
                "- A sitemap method was chosen, but no sitemap was detected at common sitemap URLs",
                "",
            ]
        )

    if not risks:
        return "✅ **No major blockers identified based on the current inputs.**"

    return "\n".join(risks).strip()


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

    if data.get("cms") == "YM":
        lines.append("**YM note:** API validation likely required before finalizing ingestion approach")

    if data.get("member_login_found"):
        lines.append(
            f"**Member login detected:** Yes — signals: {', '.join(data.get('member_login_signals', []))}"
        )

    if data.get("external_signals"):
        lines.append(
            f"**External platform signals:** {', '.join(data.get('external_signals', []))}"
        )

    if data.get("sitemap_found"):
        lines.append(f"**Sitemap found:** {data.get('sitemap_message', '')}")

    if data.get("sitemap_page_count") is not None:
        lines.append(f"**Sitemap page count:** {data.get('sitemap_page_count')}")

    if data.get("api_endpoints"):
        reachable = [x["endpoint"] for x in data["api_endpoints"] if x["reachable"]]
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
        "At a high level, this should give us the best path to bring your content into Betty while keeping setup clean and scalable.",
        "",
        "From here, the main next steps are:",
        "- confirm access details and any required credentials",
        "- review the final content scope",
        "- validate document, transcript, and media requirements",
        "- prepare for test ingestion",
    ]

    if data.get("member_login_found"):
        email.append("- We also detected possible member-login signals, so we may need credentials or API access to validate gated content.")

    if data.get("sitemap_found"):
        email.append(f"- We also found a sitemap that may support public content discovery: {data.get('sitemap_message', '')}.")

    if data.get("external_signals"):
        email.append(f"- We noticed external content signals: {', '.join(data.get('external_signals', []))}.")

    if data["member_content"] == "Yes" or data["content_login"] == "Yes":
        email.append("- For gated content, we will need login credentials or another approved access method.")

    if has_docs(data["content_types"]):
        email.append("- For document-heavy sources, text-based PDFs are preferred.")

    if has_media(data["content_types"]):
        email.append("- For audio or video content, transcripts or captions will help ensure Betty can learn from that material effectively.")

    email.extend(
        [
            "",
            "Once we have those items, we can finalize the ingestion setup and move into testing.",
            "",
            "Best,",
            "Tracy Barkley",
            "Betty Support",
        ]
    )

    return "\n".join(email)


def quick_risk_label(risks_text):
    if "🚨" in risks_text or "Blocker" in risks_text:
        return "High"
    if "⚠️" in risks_text or "Risk" in risks_text:
        return "Medium"
    return "Low"


# --------------------------------------------------
# AGENT JSON OUTPUT
# --------------------------------------------------
def build_agent_json_payload(data, strategy, secondary, risks, internal_notes, draft_email, score, complexity_label, complexity_notes):
    """Builds a structured JSON object for downstream agents.

    This is intentionally more normalized than the raw Streamlit form_data export.
    Use this output when another agent needs to reliably understand where content
    should come from, how it should be ingested, and what risks/blockers exist.
    """
    method = primary_method(data)
    suggested_sources = suggest_sources_from_content_types(data.get("content_types", []))

    risk_items = []
    current_risk = None

    for raw_line in risks.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("⚠️") or line.startswith("🚨") or line.startswith("✅"):
            if current_risk:
                risk_items.append(current_risk)

            severity = "high" if line.startswith("🚨") else "medium" if line.startswith("⚠️") else "low"
            current_risk = {
                "severity": severity,
                "title": line.replace("⚠️", "").replace("🚨", "").replace("✅", "").replace("**", "").strip(),
                "details": [],
            }
        elif current_risk:
            current_risk["details"].append(line.lstrip("- "))

    if current_risk:
        risk_items.append(current_risk)

    next_steps = [
        "Confirm final content scope and source ownership.",
        "Confirm access credentials/API keys if gated or member content is included.",
        "Validate document quality for text-selectable PDFs and supported file types.",
        "Validate transcript/caption availability for audio and video content.",
        "Run a test ingestion and review answers before production launch.",
    ]

    if data.get("member_login_found") or data.get("member_content") == "Yes" or data.get("content_login") == "Yes":
        next_steps.insert(1, "Request a member test account or approved authenticated access path.")

    if data.get("cms") == "YM":
        next_steps.insert(1, "Validate YM/YourMembership API access or required add-on availability.")

    if data.get("sitemap_found"):
        next_steps.append("Review sitemap inventory for content that should be included or excluded.")

    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "client": {
            "name": data.get("client_name", ""),
            "website": data.get("website", ""),
        },
        "platform": {
            "cms": data.get("cms", "Unknown"),
            "public_content_only": data.get("public_content"),
            "member_or_gated_content": data.get("member_content"),
            "content_behind_login": data.get("content_login"),
            "separate_public_member_instances_needed": data.get("separate_instances"),
        },
        "content": {
            "content_types": data.get("content_types", []),
            "likely_content_sources": suggested_sources,
            "pdf_text_based": data.get("pdf_text_based"),
            "transcripts_available": data.get("transcripts_available"),
            "additional_notes": data.get("additional_notes", ""),
        },
        "ingestion_recommendation": {
            "primary_method": method,
            "preferred_method_input": data.get("preferred_method"),
            "auto_suggested_method": auto_recommend_method(
                data.get("cms"),
                data.get("content_types", []),
                data.get("sitemap_found", False),
                data.get("public_content", "Yes"),
                data.get("member_login_found", False),
                data.get("vimeo_found", False),
                data.get("google_found", False),
                data.get("sharepoint_found", False),
            ),
            "strategy_markdown": strategy,
            "secondary_method_markdown": secondary,
        },
        "sitemap": {
            "found": data.get("sitemap_found", False),
            "url": data.get("sitemap_message", ""),
            "page_count": data.get("sitemap_page_count"),
            "inventory": data.get("sitemap_inventory", []),
        },
        "api_discovery": {
            "endpoints": data.get("api_endpoints", []),
            "reachable_endpoints": [
                row for row in data.get("api_endpoints", []) if row.get("reachable")
            ],
        },
        "external_platforms": {
            "vimeo": data.get("vimeo_found", False),
            "google_drive": data.get("google_found", False),
            "sharepoint_or_onedrive": data.get("sharepoint_found", False),
            "signals": data.get("external_signals", []),
        },
        "member_login": {
            "detected": data.get("member_login_found", False),
            "signals": data.get("member_login_signals", []),
        },
        "risk_assessment": {
            "risk_level": quick_risk_label(risks),
            "risks_markdown": risks,
            "risks": risk_items,
        },
        "complexity": {
            "score": score,
            "label": complexity_label,
            "factors": complexity_notes,
        },
        "handoff": {
            "internal_notes_markdown": internal_notes,
            "draft_email": draft_email,
            "next_steps": next_steps,
        },
        "raw_form_data": data,
    }

    return payload


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------
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
    "member_login_found": False,
    "member_login_signals": [],
    "vimeo_found": False,
    "google_found": False,
    "sharepoint_found": False,
    "external_signals": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# --------------------------------------------------
# HEADER
# --------------------------------------------------
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
st.caption("Generates ingestion recommendations, blockers, complexity scoring, CMS/API discovery, member-login flags, and sitemap inventory.")


# --------------------------------------------------
# FORM
# --------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Client Information")
    client_name = st.text_input("Client Name")
    website = st.text_input("Website", placeholder="https://example.com")
    public_content = st.radio("Public Content Only?", ["Yes", "No"], horizontal=True)

    if st.button("🔎 Detect CMS + Sitemap + API + Login + Platforms", use_container_width=True):
        cms, detection_message = detect_cms_from_website(website)
        st.session_state.cms = cms
        st.session_state.detection_message = detection_message

        sitemap_found, sitemap_message = detect_sitemap(website)
        st.session_state.sitemap_found = sitemap_found
        st.session_state.sitemap_message = sitemap_message
        st.session_state.sitemap_page_count = count_urls_in_sitemap(sitemap_message) if sitemap_found else None
        st.session_state.sitemap_inventory = extract_sitemap_inventory(sitemap_message) if sitemap_found else []

        st.session_state.api_endpoints = discover_api_endpoints(website, cms)

        login_found, login_signals = detect_member_login(website)
        st.session_state.member_login_found = login_found
        st.session_state.member_login_signals = login_signals

        platforms = detect_external_platforms(website)
        st.session_state.vimeo_found = platforms["vimeo"]
        st.session_state.google_found = platforms["google_drive"]
        st.session_state.sharepoint_found = platforms["sharepoint"]
        st.session_state.external_signals = platforms["signals"]

    if st.session_state.detection_message:
        if st.session_state.cms != "Unknown":
            st.success(st.session_state.detection_message)
        else:
            st.info(st.session_state.detection_message)

    if st.session_state.sitemap_found:
        st.success(f"Sitemap found: {st.session_state.sitemap_message}")
        if st.session_state.sitemap_page_count is not None:
            st.caption(f"Approximate sitemap page count: {st.session_state.sitemap_page_count}")

    if st.session_state.member_login_found:
        st.warning("Possible member login detected: " + ", ".join(st.session_state.member_login_signals))

    if st.session_state.external_signals:
        st.info("External platform signals: " + ", ".join(st.session_state.external_signals))

    st.subheader("Platform and Access")
    cms_options = [
        "WordPress",
        "Drupal",
        "Sitefinity",
        "DNN",
        "Umbraco",
        "Storyblok",
        "YM",
        "Other",
        "Unknown",
    ]

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
            "Vimeo Handler",
            "Google Handler",
            "SharePoint Handler",
            "Shared Drive Handler",
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
            "Vimeo",
            "RSS Feeds",
            "Ebooks",
            "Publications",
            "Guides",
            "Education/Courses",
            "Google Drive",
            "SharePoint",
        ],
    )

    st.session_state.suggested_sources = suggest_sources_from_content_types(content_types)
    st.session_state.suggested_method = auto_recommend_method(
        cms,
        content_types,
        st.session_state.get("sitemap_found", False),
        public_content,
        st.session_state.get("member_login_found", False),
        st.session_state.get("vimeo_found", False),
        st.session_state.get("google_found", False),
        st.session_state.get("sharepoint_found", False),
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


# --------------------------------------------------
# RESULTS
# --------------------------------------------------
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
        "member_login_found": st.session_state.get("member_login_found", False),
        "member_login_signals": st.session_state.get("member_login_signals", []),
        "vimeo_found": st.session_state.get("vimeo_found", False),
        "google_found": st.session_state.get("google_found", False),
        "sharepoint_found": st.session_state.get("sharepoint_found", False),
        "external_signals": st.session_state.get("external_signals", []),
    }

    strategy = generate_strategy(form_data)
    secondary = generate_secondary_method(form_data)
    risks = generate_risks(form_data)
    internal_notes = generate_internal_notes(form_data)
    draft_email = generate_draft_email(form_data)
    score, complexity_label, complexity_notes = complexity_score(form_data)
    agent_payload = build_agent_json_payload(
        form_data,
        strategy,
        secondary,
        risks,
        internal_notes,
        draft_email,
        score,
        complexity_label,
        complexity_notes,
    )

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

    tabs = st.tabs(
        [
            "Strategy",
            "Secondary Method",
            "Risks",
            "Complexity",
            "API Discovery",
            "Sitemap Inventory",
            "Internal Notes",
            "Draft Email",
            "Agent JSON",
        ]
    )

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

    with tabs[8]:
        st.caption("Structured handoff object for another agent to consume.")
        st.json(agent_payload)

    st.divider()
    safe_name = client_name.strip().replace(" ", "_") or "client"
    export_col1, export_col2, export_col3 = st.columns(3)

    with export_col1:
        agent_json_export = json.dumps(agent_payload, indent=2)
        st.download_button(
            label="🤖 Download Agent JSON",
            data=agent_json_export,
            file_name=f"agent_ingestion_handoff_{safe_name}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
        )

    with export_col2:
        raw_json_export = json.dumps(form_data, indent=2)
        st.download_button(
            label="📥 Download Raw Form JSON",
            data=raw_json_export,
            file_name=f"raw_ingestion_{safe_name}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
        )

    with export_col3:
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