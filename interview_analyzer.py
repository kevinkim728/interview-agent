from pydantic import BaseModel, Field
from typing import List

ANALYZER_PROMPT = """You are a hiring manager analyzing a screening interview transcript. Evaluate the candidate critically and objectively — do not give credit for vague, generic, or rehearsed answers. Only reference what is actually in the transcript — do not invent or assume.

If the transcript contains no meaningful candidate responses (only greetings, silence, or very brief exchanges), return all scores as 0.0, empty lists for highlights/concerns/red_flags, recommendation as "INSUFFICIENT_DATA", and a summary explaining why.

ANALYSIS APPROACH:
- Require specific, concrete evidence before crediting a strength — a candidate naming a specific project, outcome, or situation counts; generic claims like "I'm a hard worker" do not
- Don't give credit for basic politeness or generic responses
- Flag vague, generic, or unprepared answers as concerns
- Concerns are doubts about fit; red flags are serious issues that could disqualify the candidate
- Do not inflate scores, but a 1.0 is achievable for any candidate who meets the conditions described in each field

Your goal is to filter candidates fairly — not everyone is a good fit, but not everyone should be filtered out either. Approve candidates who genuinely demonstrate the qualifications for the role, and leave room for candidates who show strong potential even if they aren't a perfect match on paper."""

class InterviewAnalysis(BaseModel):
    communication_score: float = Field(description="Score from 0.0 to 1.0 rating how clearly the candidate communicates their ideas. Judge on whether answers are coherent, well-structured, and easy to follow. A score of 1.0 is achievable for any candidate whose ideas come across clearly.")
    engagement_score: float = Field(description="Score from 0.0 to 1.0 rating how interested the candidate appears in this specific role. Judge on whether they asked thoughtful questions, referenced specific aspects of the role or company, and gave answers tailored to this position rather than generic responses. A score of 1.0 is achievable for any candidate who demonstrates genuine interest through the substance of what they said.")
    specificity_score: float = Field(description="Score from 0.0 to 1.0 rating use of concrete examples from past experience. A score of 1.0 is achievable when the candidate provides specific examples that directly relate to the role.")
    highlights: List[str] = Field(description="List of strong moments or impressive answers that demonstrate fit for the role")
    concerns: List[str] = Field(description="List of areas of concern or weak answers that raise doubts about the candidate's fit")
    red_flags: List[str] = Field(description="List of serious issues that may disqualify the candidate from the role")
    recommendation: str = Field(description="Overall hiring recommendation: 'Strong Yes', 'Yes', 'Maybe', 'No', or 'Strong No'")
    summary: str = Field(description="2-3 sentence overall summary of the candidate's fit for the role")
    score_breakdown: str = Field(description="Explanation of what drove each score up or down. For each score, briefly note the specific moments or answers that influenced it.")
