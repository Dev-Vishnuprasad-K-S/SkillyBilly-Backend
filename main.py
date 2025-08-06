from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
import pdfplumber
import tempfile
import re
import spacy
from typing import List, Dict
from skills import TECHNICAL_SKILLS
from google import genai
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Resume Parser: Skills & Experience")

# Load spaCy once
# nlp = spacy.load("en_core_web_sm")


# Configure CORS
origins = [
    "http://localhost:3000",  # React development server
    "http://localhost:5000",  # Alternative local development port
    # Add your production domain when ready
    # "https://yourdomain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

def extract_text_from_pdf(file_path: str) -> str:
    all_text = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text.append(text)
    return "\n".join(all_text)


def extract_skills(text: str, skill_list: List[str]) -> List[str]:
    """Case-insensitive keyword matching for skills."""
    found = set()
    lower = text.lower()
    for skill in skill_list:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, lower):
            found.add(skill)
    return sorted(found)

import re
import pdfplumber
from statistics import median

EXPERIENCE_PATTERNS = [
    # e.g., "5 years of experience", "7+ years experience", "over 10 years"
    r'(?P<num>\d+(?:\.\d+)?)(?:\s*[\+]?)(?:\s*-\s*(?P<num2>\d+(?:\.\d+)?))?\s*(?:\+|years?|yrs?)\s*(?:of\s*)?(?:experience|exp)\b',
    r'over\s*(?P<num>\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b',
    r'(?P<num>\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)\b',
]

def extract_years_of_experience_from_text(text: str) -> float | None:
    """
    Scans resume text and returns a single representative years-of-experience number.
    Strategy: collect all matches, normalize ranges by taking their average, take median of candidates.
    """
    candidates = []
    lower_text = text.lower()
    for pattern in EXPERIENCE_PATTERNS:
        for m in re.finditer(pattern, lower_text):
            try:
                if m.groupdict().get("num2"):
                    a = float(m.group("num"))
                    b = float(m.group("num2"))
                    val = (a + b) / 2.0  # average of range
                else:
                    val = float(m.group("num"))
                candidates.append(val)
            except (ValueError, TypeError):
                continue
    if not candidates:
        return None
    # Use median to be robust against outliers like "1 year" buried in other context
    return float(median(candidates))







@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)) -> Dict:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        # Save PDF temporarily
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        # Extract full text
        text = extract_text_from_pdf(tmp_path)
        if not text.strip():
            return JSONResponse(
                status_code=200,
                content={
                    "message": "PDF uploaded, but no extractable text found.",
                    "skills": [],
                    "experience": []
                }
            )

        # Extract skills and experience
        skills = extract_skills(text, TECHNICAL_SKILLS)
        experience = extract_years_of_experience_from_text(text)
        
        course_data = fetch_course_recommendations(skills,experience)
        parsed = course_data.get('parsed_recommendations',{})
        return {
            "filename": file.filename,
            "skills": skills,
            "experience": experience,
            "full_text_snippet": text[:2000] + ("..." if len(text) > 2000 else ""),
            "course_list": parsed.get("courses", [])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {e}")


from typing import List, Dict, Optional
# import google.generativeai as genai



def classify_seniority(years: float) -> str:
    """Classify employee seniority by years of experience."""
    if years < 1:
        return "Intern / Entry Level"
    elif years < 3:
        return "Junior"
    elif years < 6:
        return "Mid-level"
    elif years < 10:
        return "Senior"
    else:
        return "Principal / Lead / Architect"


def build_prompt(skills: List[str], experience: float) -> str:

    # Flatten key experience snippets
    seniority = classify_seniority(experience)

#     prompt = f"""
#         You are a personalized learning advisor AI.

#         The employee profile:
#         - Inferred seniority: {seniority}
#         - Technical skills: {', '.join(skills) if skills else 'None'}

#         Task:
#         1. Based on this profile, suggest **5-8 courses** the employee should take to:
#         a. Strengthen gaps relevant to their current role.
#         b. Advance to the next level (e.g., Senior → Principal, Mid → Senior).
#         c. Complement their existing skill set.
#         2. For each course, provide:
#         - Course title
#         - Skill area it addresses
#         - Why it is recommended (one sentence)
#         - Estimated level (Foundational / Intermediate / Advanced)
#         - Suggested learning path order (1 N)
#         - If possible, a sample source or platform (e.g., Coursera, Udemy, Pluralsight) — if you don't have exact URLs, mention typical providers.

#         Format the output as JSON with keys: `courses` (list of objects) and a short `summary` recommendation.

#         Example output structure:
#         {{
#   "summary": "Short high-level recommendation summary",
#   "courses": [
#     {{
#       "title": "Advanced Python Design Patterns",
#       "skill_area": "python",
#       "reason": "Helps architect scalable systems and improve code maintainability.",
#       "level": "Advanced",
#       "order": 1,
#       "source": "Pluralsight"
#     }}
#   ]
# }}
#     """
    prompt = f"""
Act as a knowledgeable career counselor and industry expert. Your task is to recommend relevant upskilling courses and professional certifications based on a user's profile and career aspirations.
 
 
**User Profile:**
* **The employee profile:
* **          - Inferred seniority: {seniority}
* **          - Technical skills: {', '.join(skills) if skills else 'None'}
 
 
**Output Requirements:**
* Provide a list of 3-5 specific **upskilling courses** that are highly relevant to the user's goals. For each course, include:
    * **Course Title:** The name of the course or learning path.
    * **Reasoning:** A brief explanation of why this course is a good fit, connecting it directly to their career goals and skill gaps.
    * **Potential Platforms:** Mention popular platforms where this type of course can be found (e.g., Coursera, edX, Udemy, Pluralsight, LinkedIn Learning).
* Provide a list of 2-3 highly-regarded **professional certifications**. For each certification, include:
    * **Certification Name:** The full name of the certification (e.g., "Project Management Professional (PMP)," "AWS Certified Solutions Architect – Associate").
    * **Reasoning:** Explain the value of this certification in the user's target industry and how it can help them achieve their goals (e.g., "This certification is a globally recognized standard for project managers and is often a prerequisite for senior roles.").
    * **Issuing Body:** The organization that offers the certification (e.g., Project Management Institute (PMI), Amazon Web Services (AWS)).
* Include a section on **"Next Steps."** This should offer practical advice on how to start this upskilling journey, such as creating a learning plan, networking, and building a portfolio.
Format the output as JSON with keys: `courses` (list of objects) and a short `summary` recommendation.
        
        Example output structure:
        {{
  "summary": "Short high-level recommendation summary",
  "courses": [
    {{
      "title": "Advanced Python Design Patterns",
      "skill_area": "python",
      "reason": "Helps architect scalable systems and improve code maintainability.",
      "level": "Advanced",
      "order": 1,
      "source": "Pluralsight"
    }}
  ]
}}"""
    return prompt.strip()


def fetch_course_recommendations(
    skills: List[str],
    experience: int,
) -> Dict:
    """
    Sends the constructed prompt to Gemini and returns parsed JSON recommendations.
    """

    prompt = build_prompt(skills, experience)

    # genai.configure(api_key="AIzaSyC-6Us_1jOdWdRpyLsmtjMAJ_PU1Wzm_kY")

    client = genai.Client(api_key="your api key here")

    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    print(response.text)
    data = response.text
    match = re.search(r"```json\s*(\{.*?\})\s*```", data, re.DOTALL)
    json_str = match.group(1) if match else data.strip()
    

    # Try to parse JSON from the model output
    import json
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: return raw text for later manual parsing
        parsed = {"raw": data}

    return {
        "prompt_used": prompt,
        "raw_response": data,
        "parsed_recommendations": parsed,
    }



def fetch_course_plan(
    course_name: str,
    daily_hours: int,
) -> Dict:
    """
    Sends the constructed prompt to Gemini and returns parsed JSON recommendations.
    """

    prompt = f"""
    
You are a highly intelligent course planner AI. Your task is to generate a comprehensive daily study plan for a course, including detailed topics, subtopics, and explanations for each day based on the total duration of the course and the number of hours available each day for study. 

1. **Input Parameters:**
   - Course Title: {course_name}
   - Daily Hours Available for Study: {daily_hours}
   - Course Level (Beginner, Intermediate, Advanced): Intermediate

2. **Output :**
   - For each day, provide:
     - **Day [X]:**
       - **Main Topic:** [Title of the main topic for the day]
       - **Subtopics:** 
         1. [Subtopic 1]
         2. [Subtopic 2]
         3. [Subtopic 3]
         - (Continue as needed)
       - **Detailed Explanations:** 
         - [Provide a thorough explanation for each subtopic, including key concepts, examples, and any relevant resources or references.]
       - **Estimated Time Allocation:** 
         - [Suggest how much time to allocate to each subtopic based on the daily hours available.]
       - **Learning Objectives:** 
         - [List the learning objectives for the day’s topics to guide the learner’s focus and expectations.]

3. **Guidelines:**
   - Ensure that topics and subtopics logically build on each other and progressively advance in complexity.
   - Include a variety of learning methods such as reading, practice exercises, and assessments where applicable.
   - Maintain clarity and coherence in explanations, making sure they are easily understandable and engaging.
   - Consider including additional resources such as articles, videos, or tools that can enhance learning.

4. **Example Usage:**
   - User inputs: "Course Title: Introduction to Machine Learning, Total Duration: 10 days, Daily Hours: 2 hours, Level: Beginner"
   - Output should be a structured plan for 10 days detailing topics and subtopics with explanations and time allocations.
5. ** Output Structure :JSON**

**"output_example": **{{ "days": [ {{ "day": 1, "topics": 
                               [ {{ "topic_name": "Topic 1",
                                   "subtopics": 
                                                       [ {{ "subtopic_name": "Subtopic 1.1", 
                                                          "explanation": "Detailed explanation of Subtopic 1.1." }}, 
                                                          {{ "subtopic_name": "Subtopic 1.2", 
                                                           "explanation": "Detailed explanation of Subtopic 1.2." }} 
                                                          ]}} 
                                                          ]}}, 
                                                          ]}}


Generate a complete daily study plan based on the provided parameters, ensuring to cover all necessary topics within the specified timeframe.
    """


    client = genai.Client(api_key="AIzaSyC-6Us_1jOdWdRpyLsmtjMAJ_PU1Wzm_kY")

    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    print(response.text)
    data = response.text
    match = re.search(r"```json\s*(\{.*?\})\s*```", data, re.DOTALL)
    json_str = match.group(1) if match else data.strip()
    

    # Try to parse JSON from the model output
    import json
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: return raw text for later manual parsing
        parsed = {"raw": data}

    return {
        "prompt_used": prompt,
        "raw_response": data,
        "course_plan": parsed,
    }

def extract_day1_and_basic(course_plan: dict) -> dict:
    days = course_plan.get("days", [])
    day1 = next((d for d in days if d.get("day") == 1), None)
    if day1 is None:
        raise ValueError("Day 1 not found in plan.")

    basic_info = {
        "course_title": course_plan.get("course_title"),
        "daily_hours": course_plan.get("daily_hours"),
    }

    return {
        "basic_info": basic_info,
        "day1": day1
    }


@app.post("/course_plan")
async def course_plan(course_name: str = Form(...),daily_hours: int = Form(...),
        ) -> Dict:
    
    try:
        response_data = fetch_course_plan(course_name,daily_hours)
        course_data = extract_day1_and_basic(response_data.get('course_plan'))
        return {
            "course_plan": course_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process request: {e}")