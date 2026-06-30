from pathlib import Path

from applypilot.documents import build_docx, build_pdf
from applypilot.models import (
    CandidateProfile,
    TailoredArtifact,
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
)


output = Path("tmp/pdfs")
output.mkdir(parents=True, exist_ok=True)

profile = CandidateProfile(
    legal_name="Test Candidate",
    email="candidate@example.test",
    phone="+1 555 0100",
    city="Chicago",
    region="IL",
    country="US",
    linkedin_url="https://www.linkedin.com/in/test-candidate",
)
artifact = TailoredArtifact(
    tailored=TailoredResume(
        headline="Software Engineer | Python Automation",
        summary=(
            "Software engineer focused on reliable browser automation, APIs, and testable "
            "workflows for high-confidence operational systems."
        ),
        skills=["Python", "SQL", "FastAPI", "Browser Automation", "Automated Testing"],
        experiences=[
            TailoredExperience(
                heading="Software Engineer - Example Systems | 2023-Present",
                bullets=[
                    TailoredBullet(
                        text="Built reliable Python services and deployment automation.",
                        evidence_ids=["evidence-1"],
                    ),
                    TailoredBullet(
                        text="Created automated tests for critical API and browser workflows.",
                        evidence_ids=["evidence-2"],
                    ),
                    TailoredBullet(
                        text="Partnered with product teams to clarify requirements and ship maintainable features.",
                        evidence_ids=["evidence-3"],
                    ),
                ],
            ),
            TailoredExperience(
                heading="Software Developer - Sample Labs | 2021-2023",
                bullets=[
                    TailoredBullet(
                        text="Developed data-processing tools using Python and SQL.",
                        evidence_ids=["evidence-4"],
                    ),
                    TailoredBullet(
                        text="Improved operational visibility with structured logs and error reporting.",
                        evidence_ids=["evidence-5"],
                    ),
                ],
            ),
        ],
    )
)

(output / "sample-tailored-resume.docx").write_bytes(build_docx(artifact, profile))
(output / "sample-tailored-resume.pdf").write_bytes(build_pdf(artifact, profile))
print(output.resolve())
