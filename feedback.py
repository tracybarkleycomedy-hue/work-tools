import streamlit as st

st.set_page_config(page_title="Betty Feedback Buddy", layout="wide")

st.title("🤖 Betty Feedback Buddy")
st.markdown("Turn Betty feedback into the best fix path and ready-to-paste instructions.")

BETTY_SECTIONS = [
    "QUERY",
    "RECOMMEND",
    "REVIEWCONTENT",
    "GREETING",
    "PERSONALITY",
    "INTENT",
    "TOPIC",
    "REFUSE",
    "SUMMARY",
    "QUERYCONTENT",
]


def diagnose_issue(feedback, betty_response, desired_behavior):
    text = f"{feedback} {betty_response} {desired_behavior}".lower()

    if any(x in text for x in ["webinar", "webinars"]):
        return "Webinar link/listing issue"

    if any(x in text for x in ["duplicate link", "bad link", "wrong link", "link issue", "learn more", "broken link"]):
        return "Incorrect or duplicate links"

    if any(x in text for x in ["redirect", "send them to", "point them to", "specific url", "specific link", "approved resource"]):
        return "Redirect needed"

    if any(x in text for x in ["too long", "wordy", "verbose", "shorter", "concise"]):
        return "Response too long"

    if any(x in text for x in ["wrong source", "wrong document", "wrong content", "bad source"]):
        return "Incorrect content source"

    if any(x in text for x in ["irrelevant", "not relevant", "unrelated", "bad recommendation"]):
        return "Irrelevant content selection"

    if any(x in text for x in ["outside scope", "made up", "hallucinated", "not in content"]):
        return "Needs content-scope restriction"

    if any(x in text for x in ["citation", "cite", "source title", "inline citation"]):
        return "Citation issue"

    if any(x in text for x in ["upcoming", "future", "past event", "old event", "date issue"]):
        return "Recency or upcoming-events issue"

    if any(x in text for x in ["tone", "voice", "personality", "friendly", "formal"]):
        return "Personality or tone issue"

    if any(x in text for x in ["introduce yourself", "greeting", "welcome"]):
        return "Greeting issue"

    return "General instruction improvement"


def recommend_fix_path(issue, feedback, betty_response):
    text = f"{issue} {feedback} {betty_response}".lower()

    if issue in ["Redirect needed", "Webinar link/listing issue"]:
        return (
            "Redirect to Existing Content",
            "The issue is best solved by creating a topic-to-URL or specific resource instruction using approved existing content.",
        )

    if any(x in text for x in [
        "missing content", "not ingested", "not trained", "no source", "no content",
        "nothing in content", "transcript missing", "missing transcript", "pdf missing",
        "document missing", "content missing", "source missing", "needs to be uploaded",
        "needs ingestion"
    ]):
        return (
            "Add Missing Content",
            "Betty likely does not have the required source material. Add or ingest the missing content before relying on instructions.",
        )

    if any(x in text for x in [
        "many examples", "multiple issues", "pattern", "keeps happening", "bigger issue",
        "needs review", "dev", "escalate", "complex", "across multiple", "not just one"
    ]):
        return (
            "Create Feedback Document",
            "This appears broader than a single instruction and should be documented with examples, screenshots, expected behavior, and test cases.",
        )

    return (
        "Add/Update Instructions",
        "The content appears available, but Betty needs clearer behavioral guidance.",
    )


def recommend_sections(issue, fix_path):
    if fix_path == "Add Missing Content":
        return ["QUERYCONTENT"]

    if fix_path == "Redirect to Existing Content":
        return ["QUERY"]

    if fix_path == "Create Feedback Document":
        return ["REVIEWCONTENT", "QUERY"]

    if issue == "Incorrect or duplicate links":
        return ["QUERY"]

    if issue == "Response too long":
        return ["QUERY", "PERSONALITY"]

    if issue == "Incorrect content source":
        return ["QUERY", "REVIEWCONTENT"]

    if issue == "Irrelevant content selection":
        return ["REVIEWCONTENT", "QUERY"]

    if issue == "Needs content-scope restriction":
        return ["QUERY", "REFUSE"]

    if issue == "Citation issue":
        return ["QUERY"]

    if issue == "Recency or upcoming-events issue":
        return ["REVIEWCONTENT", "QUERY"]

    if issue == "Personality or tone issue":
        return ["PERSONALITY"]

    if issue == "Greeting issue":
        return ["GREETING"]

    return ["QUERY"]


def instruction_type(issue, fix_path):
    if fix_path == "Add Missing Content":
        return "Content Gap / Ingestion Needed"

    if fix_path == "Redirect to Existing Content":
        return "Redirect / Specific Resource Rule"

    if fix_path == "Create Feedback Document":
        return "Feedback Documentation / Escalation"

    if issue == "Webinar link/listing issue":
        return "Specific Resource Listing"

    if issue == "Incorrect or duplicate links":
        return "Link Control"

    if issue == "Response too long":
        return "Brevity / Directness"

    if issue == "Incorrect content source":
        return "Source Restriction"

    if issue == "Irrelevant content selection":
        return "Content Relevance / ReviewContent"

    if issue == "Needs content-scope restriction":
        return "Refusal / Content Scope"

    if issue == "Citation issue":
        return "Citation / Source Traceability"

    if issue == "Recency or upcoming-events issue":
        return "Recency / Upcoming Events"

    if issue == "Personality or tone issue":
        return "Tone / Personality"

    if issue == "Greeting issue":
        return "Greeting Behavior"

    return "General Instruction"


def generate_fix_action(fix_path, topic_or_source, desired_behavior):
    topic = topic_or_source.strip() or "[topic/source]"

    if fix_path == "Add Missing Content":
        return f"""Recommended Action:
Add or ingest the missing content related to {topic} before relying on instruction changes.

Suggested content requirements:
- Confirm the source exists and is approved for Betty.
- Add the missing webpage, PDF, transcript, document, or data source.
- If the source is video/audio, provide a transcript or captions.
- If the source is a PDF, confirm it is text-based and not image-only.
- Retest after ingestion using the same user question and related follow-up questions."""

    if fix_path == "Redirect to Existing Content":
        return f"""Recommended Action:
Create a specific resource rule for {topic} using approved existing content.

Before applying the instruction:
- Confirm the exact approved URL or source.
- Confirm the preferred display title for the link.
- Confirm whether Betty should answer first, list specific resources, redirect only, or do both.
- Test with direct and related questions."""

    if fix_path == "Create Feedback Document":
        return """Recommended Action:
Create a feedback document because this issue is broader than a single instruction change.

Feedback document should include:
- Client/assistant name
- User question(s)
- Betty’s current response
- Screenshots or examples
- What went wrong
- Expected behavior
- Proposed instruction changes
- Suggested placement
- Test questions
- Notes for dev/support review"""

    return ""


def generate_instruction(issue, fix_path, desired_behavior, topic_or_source):
    topic = topic_or_source.strip() or "this topic"

    combined = f"{desired_behavior} {topic} {issue}".lower()

    if "webinar" in combined:
        return f"""When the user asks about webinars related to {topic}, use only the provided <content> to identify specific relevant webinar items.

If specific webinar titles and URLs are available in the <content>, list the most relevant webinars and include each webinar as a markdown hyperlink using this format: [Webinar Title](URL).

Do not link only to a general webinar page if specific webinar URLs are available. Do not invent webinar titles, URLs, dates, or descriptions. Do not include duplicate links or unrelated webinars. If the <content> does not contain specific webinar links, explain that a specific webinar resource was not found and ask the user to clarify the topic or webinar they need."""

    if fix_path == "Redirect to Existing Content":
        return f"""When the user asks about {topic}, first answer using the provided <content> when relevant information is available.

After the answer, direct the user to the approved resource for {topic}. Display the resource as a markdown hyperlink using this format: [Resource Title](URL).

Do not provide unrelated links, duplicate links, general pages, or links that are not directly tied to the approved resource. If the approved resource is not available in the provided <content>, do not invent a link. Politely explain that a reliable resource was not found and ask the user to clarify what they need."""

    if fix_path == "Add Missing Content":
        return f"""Do not attempt to answer questions about {topic} unless relevant content is available in the provided <content>. If the content is missing, politely explain that a reliable resource was not found and route the issue for content ingestion."""

    if fix_path == "Create Feedback Document":
        return """This issue requires a feedback document rather than a single prompt-only fix. Collect examples, screenshots, current behavior, expected behavior, suggested placement, and test questions before applying changes."""

    if issue == "Incorrect or duplicate links":
        return """Only reference links that are directly supported by the provided <content>. Do not include duplicate, broken, unavailable, or unrelated links. If a link is not clearly tied to the most relevant ContentItem, do not include it. When links are shown automatically by the UI, do not add extra links at the end of the response."""

    if issue == "Response too long":
        return """Keep answers concise and complete. Favor brief answers of 4–6 sentences unless the user asks for more detail. Avoid long summaries, extra commentary, or unnecessary background. Respond in a conversational style and focus only on the facts needed to answer the question."""

    if issue == "Incorrect content source":
        return f"""Only use the provided <content> to answer the user’s question. Do not fill in gaps with outside knowledge or unrelated sources. If the provided <content> does not contain enough information to answer confidently, politely decline and explain that a reliable source was not found. For questions about {topic}, only use content that directly addresses {topic}."""

    if issue == "Irrelevant content selection":
        return f"""Prioritize content based on direct relevance to the user’s question. Only use or recommend content that clearly helps answer the question. Do not include loosely related, tangential, or lower-relevance items. For questions about {topic}, prioritize the most specific and directly applicable content first."""

    if issue == "Needs content-scope restriction":
        return """Only use the provided <content> to respond. Do not use pre-training knowledge or outside information. If there is no reliable answer in the provided <content>, politely decline to answer and explain that a reliable resource was not found."""

    if issue == "Citation issue":
        return """Use the provided <content> to build the response and make the answer traceable to the source material. Reference the ContentItemTitle when helpful. Do not cite or mention sources that do not directly support the answer."""

    if issue == "Recency or upcoming-events issue":
        return """When the user asks about upcoming, future, or next events, prioritize content that contains event dates on or after <<DATE>>. Do not mention past events unless the user specifically asks about them by name. For event questions, prioritize dates found in the content text rather than the ContentItemDate."""

    if issue == "Personality or tone issue":
        return """Use a friendly, professional, and concise tone. Keep the answer conversational and helpful without sounding overly formal or robotic."""

    if issue == "Greeting issue":
        return """When introducing yourself, clearly state who you are, what you help with, and how the user can ask for assistance. Keep the greeting brief, friendly, and aligned with the assistant’s purpose."""

    return f"""Use the provided <content> to answer questions about {topic} clearly and concisely. Do not use outside knowledge or unsupported assumptions. If the <content> does not contain enough information to answer reliably, politely decline and explain that a reliable source was not found."""


def generate_test_questions(issue, fix_path, original_question, topic_or_source):
    topic = topic_or_source.strip() or "this topic"
    original = original_question.strip() or f"Tell me about {topic}"

    if "webinar" in f"{issue} {fix_path} {topic}".lower():
        return [
            original,
            f"What webinars are available about {topic}?",
            f"Can you list specific webinars about {topic} with links?",
            f"Where can I find webinar resources for {topic}?",
            f"Are there any relevant webinars, and can you link directly to each one?",
        ]

    if fix_path == "Add Missing Content":
        return [
            original,
            f"What information is available about {topic}?",
            f"Do you have any resources on {topic}?",
            f"Can you provide details from your sources about {topic}?",
        ]

    if fix_path == "Redirect to Existing Content":
        return [
            original,
            f"Where can I find {topic}?",
            f"Can you send me the official resource for {topic}?",
            f"Is there a specific page or resource for {topic}?",
        ]

    if fix_path == "Create Feedback Document":
        return [
            original,
            f"Ask a similar question about {topic}.",
            f"Ask a follow-up question that previously triggered the issue.",
        ]

    if issue == "Incorrect or duplicate links":
        return [
            original,
            f"Can you give me resources about {topic}?",
            f"Where can I find information about {topic}?",
            f"List links related to {topic}.",
        ]

    if issue == "Response too long":
        return [
            original,
            f"Give me a short answer about {topic}.",
            f"Summarize {topic} briefly.",
            f"Explain {topic} in a few sentences.",
        ]

    if issue == "Incorrect content source":
        return [
            original,
            f"What does the official source say about {topic}?",
            f"Can you answer using only the correct source for {topic}?",
            f"Where is this information coming from?",
        ]

    if issue == "Recency or upcoming-events issue":
        return [
            "What upcoming events are available?",
            f"What is the next {topic}?",
            f"Are there any future webinars about {topic}?",
            f"Show me recent or upcoming items for {topic}.",
        ]

    return [
        original,
        f"Can you provide information about {topic}?",
        f"Give me details specifically about {topic}.",
        "What can you tell me about this?",
    ]


def format_placement(section):
    if section in ["RECOMMEND", "REVIEWCONTENT", "GREETING", "PERSONALITY"]:
        return f"{section} → Instructions"
    return f"{section} → Instructions-end"


col1, col2 = st.columns(2)

with col1:
    user_question = st.text_area("User Question")
    betty_response = st.text_area("Betty Response")

with col2:
    feedback = st.text_area("Feedback / Issue")
    desired_behavior = st.text_area("Desired Behavior / What should Betty do instead?")
    topic_or_source = st.text_input("Topic, Source, URL, or Rule Name")

st.subheader("Fix Path Settings")

fix_mode = st.radio(
    "Fix Path Mode",
    ["Auto recommend best fix path", "Manual select fix path"],
    horizontal=True,
)

manual_fix_path = None
if fix_mode == "Manual select fix path":
    manual_fix_path = st.selectbox(
        "Select Fix Path",
        ["Add/Update Instructions", "Add Missing Content", "Redirect to Existing Content", "Create Feedback Document"],
    )

st.subheader("Placement Settings")

placement_mode = st.radio(
    "Placement Mode",
    ["Auto recommend best section(s)", "Manual select section(s)"],
    horizontal=True,
)

manual_sections = []
if placement_mode == "Manual select section(s)":
    manual_sections = st.multiselect(
        "Select Betty section(s)",
        BETTY_SECTIONS,
        default=["QUERY"],
    )

st.subheader("Screenshots (optional)")

images = st.file_uploader(
    "Upload screenshots of Betty response, links, or UI issue",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

if images:
    for img in images:
        st.image(img, caption=img.name, use_container_width=True)


if st.button("🚀 Generate Fix", type="primary", use_container_width=True):
    issue = diagnose_issue(feedback, betty_response, desired_behavior)
    auto_fix_path, fix_reason = recommend_fix_path(issue, feedback, betty_response)

    fix_path = manual_fix_path if fix_mode == "Manual select fix path" and manual_fix_path else auto_fix_path

    if fix_mode == "Manual select fix path":
        fix_reason = f"Manual override selected. Original auto recommendation was: {auto_fix_path}. {fix_reason}"

    auto_sections = recommend_sections(issue, fix_path)
    final_sections = manual_sections if placement_mode == "Manual select section(s)" and manual_sections else auto_sections

    inst_type = instruction_type(issue, fix_path)
    action_plan = generate_fix_action(fix_path, topic_or_source, desired_behavior)
    instruction = generate_instruction(issue, fix_path, desired_behavior, topic_or_source)
    test_questions = generate_test_questions(issue, fix_path, user_question, topic_or_source)

    st.divider()

    st.subheader("🧠 Diagnosis")
    st.write(issue)

    st.subheader("🧭 Best Fix Path")
    st.write(f"**{fix_path}**")
    st.caption(fix_reason)

    if action_plan:
        st.subheader("✅ Recommended Action")
        st.code(action_plan)

    st.subheader("🏷 Instruction Type")
    st.write(inst_type)

    st.subheader("📍 Recommended Placement")
    for section in final_sections:
        st.code(format_placement(section))

    st.subheader("🛠 Instruction (copy/paste)")
    st.code(instruction)

    st.subheader("🧪 Test Questions")
    for q in test_questions:
        st.write(f"- {q}")

    st.subheader("📝 Support Notes")
    if fix_path == "Add Missing Content":
        st.write("- Confirm whether the relevant source exists in INSIGHTS.")
        st.write("- If the source is video/audio, confirm transcripts are available.")
        st.write("- If the source is a PDF, confirm it is text-based.")
    elif fix_path == "Redirect to Existing Content":
        st.write("- Confirm the approved destination URL before adding the redirect rule.")
        st.write("- Confirm the exact display text for the markdown link.")
        st.write("- Test exact-match and related questions to make sure Betty routes correctly.")
    elif fix_path == "Create Feedback Document":
        st.write("- Include screenshots, examples, expected behavior, and test questions.")
        st.write("- Use this when one instruction is not enough or the issue affects multiple scenarios.")
    elif issue == "Incorrect or duplicate links":
        st.write("- Check whether links are coming from the UI auto-source display or from Betty adding links in the response text.")
        st.write("- If the UI already displays source links, the instruction should tell Betty not to add extra links.")
    elif issue == "Incorrect content source":
        st.write("- If the wrong source is being selected before the answer is generated, also test REVIEWCONTENT placement.")
    elif issue == "Recency or upcoming-events issue":
        st.write("- Test with both 'upcoming' and specific event names to confirm past events are not being over-prioritized.")
    else:
        st.write("- Retest with the same question, a reworded question, and a related follow-up.")

    if images:
        st.subheader("📎 Screenshots Referenced")
        for i, img in enumerate(images, start=1):
            st.write(f"- Screenshot {i}: {img.name}")

    st.subheader("📋 Copyable Fix Summary")
    summary = f"""Issue: {issue}

Best Fix Path: {fix_path}
Reason: {fix_reason}

Instruction Type: {inst_type}

Placement:
{chr(10).join('- ' + format_placement(section) for section in final_sections)}

Recommended Action:
{action_plan or 'Add/update the instruction below.'}

Instruction:
{instruction}

Test Questions:
{chr(10).join('- ' + q for q in test_questions)}
"""
    st.code(summary)