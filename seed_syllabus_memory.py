from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from memory_store import create_link, create_memory_record, load_records


SYLLABUS_PATH = Path("Syllabus - Model Context Protocol for AI Agents.docx")
SOURCE = str(SYLLABUS_PATH)


def main() -> None:
    paragraphs = extract_docx_paragraphs(SYLLABUS_PATH)
    if not paragraphs:
        raise SystemExit(f"No text found in {SYLLABUS_PATH}")

    existing = [record for record in load_records() if record.get("source") == SOURCE]
    if existing:
        print(json.dumps({"status": "already_seeded", "records": len(existing)}, indent=2))
        return

    specs = [
        {
            "key": "course_identity",
            "text": "AIM 5014 / COM 5014 / DAV 6300 is a 3-credit graduate course titled Model Context Protocol for AI Agents in Summer 2026.",
            "tags": ["syllabus", "course", "mcp"],
        },
        {
            "key": "prerequisites",
            "text": "The course recommends prior programming experience and familiarity with Python or TypeScript, Git/GitHub, command line work, and AI coding assistants.",
            "tags": ["syllabus", "prerequisites", "skills"],
        },
        {
            "key": "format",
            "text": "The course meets in person on Thursdays from 5:30 to 7:30 pm and uses lecture, guided demo, and hands-on projects.",
            "tags": ["syllabus", "schedule", "format"],
        },
        {
            "key": "description",
            "text": "The course teaches graduate students engineering foundations and practical methods for building AI agent systems through the Model Context Protocol.",
            "tags": ["syllabus", "course-description", "mcp"],
        },
        {
            "key": "agent_engineering",
            "text": "The syllabus treats AI agency as a software engineering discipline involving hosts, clients, servers, tools, resources, prompts, and secure environments.",
            "tags": ["syllabus", "architecture", "agent-systems"],
        },
        {
            "key": "server_building",
            "text": "Students progress from local utility MCP servers to grounded data systems and multi-agent workflows using Python, JavaScript/TypeScript, or Java SDKs.",
            "tags": ["syllabus", "mcp-servers", "projects"],
        },
        {
            "key": "security_emphasis",
            "text": "The course emphasizes context economics, secure autonomy, professional deployment, token reduction through local computation, sensitive data protection, and defenses against indirect prompt injection and tool poisoning.",
            "tags": ["syllabus", "security", "context-economics"],
        },
        {
            "key": "outcome_architecture",
            "text": "Students should be able to explain MCP host-client-server architecture and the roles of tools, resources, and prompts.",
            "tags": ["syllabus", "learning-outcomes", "architecture"],
        },
        {
            "key": "outcome_build",
            "text": "Students should be able to build local MCP utility servers with approved SDKs and AI coding hosts such as Claude Code, Gemini or Antigravity CLI, Codex/OpenAI, OpenCode, or comparable tools.",
            "tags": ["syllabus", "learning-outcomes", "mcp-servers"],
        },
        {
            "key": "outcome_grounding",
            "text": "Students should be able to ground agents in SQL, vector databases, RAG, and controlled resource access while optimizing costs for MCP-assisted code workflows.",
            "tags": ["syllabus", "learning-outcomes", "rag"],
        },
        {
            "key": "outcome_portfolio",
            "text": "Students should present a portfolio of secure, optimized, production-ready agentic systems.",
            "tags": ["syllabus", "learning-outcomes", "portfolio"],
        },
        {
            "key": "required_tools",
            "text": "Required tools include a laptop, a coding environment, a GitHub account, Python 3.10 or newer, Node.js 20 or newer when needed, and at least one approved MCP-capable AI coding host.",
            "tags": ["syllabus", "tools", "environment"],
        },
        {
            "key": "optional_tools",
            "text": "Optional tools may include Java, TypeScript SDKs, Docker, FastAPI, SQLite/Postgres, Chroma, StreamableHTTP/SSE, Claude Code, Gemini CLI, Antigravity CLI, Codex/OpenAI, MCP memory servers, and secure gateways.",
            "tags": ["syllabus", "tools", "environment"],
        },
        {
            "key": "grading",
            "text": "Grades are based on weekly MCP skill checks, project deliverables, documentation, testing, explanation, participation, peer review, final reflection, and code ownership interview.",
            "tags": ["syllabus", "grading", "assessment"],
        },
        {
            "key": "project_1",
            "text": "Project 1 is Hello MCP plus a Developer Utility Server and is worth 10 percent of the grade.",
            "tags": ["syllabus", "project", "assessment"],
        },
        {
            "key": "project_2",
            "text": "Project 2 is a Knowledge Base or SQLite Grounding MCP Server and is worth 20 percent of the grade.",
            "tags": ["syllabus", "project", "grounding"],
        },
        {
            "key": "project_3",
            "text": "Project 3 is a Task plus Review Agent Flow and is worth 20 percent of the grade.",
            "tags": ["syllabus", "project", "agent-flow"],
        },
        {
            "key": "project_4",
            "text": "Project 4 is an Extended MCP Portfolio System and is worth 20 percent of the grade.",
            "tags": ["syllabus", "project", "portfolio"],
        },
        {
            "key": "rubric",
            "text": "The suggested project rubric emphasizes functionality, MCP implementation and code clarity, student understanding explanations, skill and memory file quality, testing and limitations, and AI interaction process documentation.",
            "tags": ["syllabus", "rubric", "assessment"],
        },
        {
            "key": "ai_allowed",
            "text": "Students may use AI to learn concepts, brainstorm approaches, debug or improve work, generate drafts and examples, and support project development when they remain responsible for the final work.",
            "tags": ["syllabus", "ai-policy", "collaboration"],
        },
        {
            "key": "ai_responsibility",
            "text": "Students are responsible for understanding and explaining submitted work, revising AI-assisted work, keeping records of meaningful AI use when required, protecting sensitive information, and following instructions.",
            "tags": ["syllabus", "ai-policy", "responsibility"],
        },
        {
            "key": "ai_limits",
            "text": "Students may not submit work they do not understand, present AI-assisted work as entirely their own without acknowledgment, submit another student's work, violate academic integrity policies, upload restricted data without permission, or use AI to write the final personal reflection unless allowed.",
            "tags": ["syllabus", "ai-policy", "academic-integrity"],
        },
        {
            "key": "collaboration",
            "text": "Team and collaborative work may be assigned, and each student is assessed on both group submission quality and individual contribution and explanation.",
            "tags": ["syllabus", "collaboration", "assessment"],
        },
        {
            "key": "attendance",
            "text": "Students are expected to attend all scheduled classes, and missing 30 percent or more of the course can result in a final grade of F under the Katz School attendance policy.",
            "tags": ["syllabus", "attendance", "policy"],
        },
    ]

    created = {}
    for spec in specs:
        result = create_memory_record(spec["text"], SOURCE, spec["tags"])
        created[spec["key"]] = result["record"]["id"]

    links = [
        ("prerequisites", "course_identity", "related_to", "Prerequisites describe preparation for the course."),
        ("format", "course_identity", "related_to", "Meeting format is part of course identity."),
        ("description", "course_identity", "related_to", "Description explains the course identity."),
        ("agent_engineering", "description", "narrows_scope", "Software engineering framing narrows the course description."),
        ("server_building", "description", "narrows_scope", "Server-building progression is a concrete part of the course description."),
        ("security_emphasis", "description", "narrows_scope", "Security and context economics are emphasized themes in the course description."),
        ("outcome_architecture", "description", "supports", "Learning outcomes operationalize the course description."),
        ("outcome_build", "server_building", "supports", "Building local utility servers supports the server-building course arc."),
        ("outcome_grounding", "server_building", "related_to", "Grounded agent systems build on MCP server development."),
        ("outcome_portfolio", "project_4", "supports", "The extended portfolio project supports the portfolio outcome."),
        ("required_tools", "prerequisites", "related_to", "Required tools complement the recommended preparation."),
        ("optional_tools", "required_tools", "broadens_scope", "Optional tools broaden the required environment."),
        ("project_1", "grading", "narrows_scope", "Project 1 is one component of grading."),
        ("project_2", "grading", "narrows_scope", "Project 2 is one component of grading."),
        ("project_3", "grading", "narrows_scope", "Project 3 is one component of grading."),
        ("project_4", "grading", "narrows_scope", "Project 4 is one component of grading."),
        ("rubric", "grading", "narrows_scope", "The rubric explains project grading criteria."),
        ("ai_responsibility", "ai_allowed", "narrows_scope", "AI permissions are bounded by student responsibility."),
        ("ai_limits", "ai_allowed", "narrows_scope", "AI restrictions limit allowed AI use."),
        ("collaboration", "grading", "related_to", "Collaboration affects assessment and explanation."),
        ("attendance", "format", "related_to", "Attendance expectations are tied to scheduled in-person meetings."),
        ("security_emphasis", "ai_responsibility", "related_to", "Sensitive data protection connects course security themes to AI-use responsibilities."),
    ]
    for source_key, target_key, link_type, reason in links:
        create_link(created[source_key], created[target_key], link_type, reason, 0.92)

    print(
        json.dumps(
            {
                "status": "seeded",
                "source": SOURCE,
                "source_paragraphs": len(paragraphs),
                "records": len(created),
                "links": len(links),
                "record_ids": created,
            },
            indent=2,
        )
    )


def extract_docx_paragraphs(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"Missing source document: {path}")
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = [text.text or "" for text in paragraph.findall(".//w:t", namespace)]
        value = "".join(parts).strip()
        if value:
            paragraphs.append(value)
    return paragraphs


if __name__ == "__main__":
    main()
