from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import random
import re

app = Flask(__name__, static_folder=".")
CORS(app)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

SCRAPE_URLS = {
    "Web Development": {
        "Easy": [
            "https://www.geeksforgeeks.org/html-interview-questions-answers/",
            "https://www.geeksforgeeks.org/css-interview-questions-and-answers/",
            "https://www.geeksforgeeks.org/top-50-javascript-interview-questions/",
            "https://www.geeksforgeeks.org/commonly-asked-computer-networks-interview-questions/",
        ],
        "Medium": [
            "https://www.javatpoint.com/javascript-interview-questions",
            "https://www.tutorialspoint.com/javascript/javascript_interview_questions.htm",
            "https://www.geeksforgeeks.org/javascript-interview-questions-and-answers/",
        ],
        "Hard": [
            "https://www.javatpoint.com/react-interview-questions",
            "https://www.interviewbit.com/react-interview-questions/",
            "https://www.geeksforgeeks.org/react-interview-questions/",
        ]
    },
    "Data Science": {
        "Easy": [
            "https://www.javatpoint.com/data-science-interview-questions",
            "https://www.simplilearn.com/tutorials/data-science-tutorial/data-science-interview-questions",
            "https://www.geeksforgeeks.org/data-science-interview-questions-and-answers/",
        ],
        "Medium": [
            "https://www.javatpoint.com/machine-learning-interview-questions",
            "https://www.interviewbit.com/machine-learning-interview-questions/",
            "https://www.geeksforgeeks.org/machine-learning-interview-questions/",
        ],
        "Hard": [
            "https://www.javatpoint.com/deep-learning-interview-questions",
            "https://www.interviewbit.com/deep-learning-interview-questions/",
            "https://www.geeksforgeeks.org/deep-learning-interview-questions/",
        ]
    },
    "Data Analysis": {
        "Easy": [
            "https://www.javatpoint.com/sql-interview-questions",
            "https://www.tutorialspoint.com/sql/sql_interview_questions.htm",
            "https://www.geeksforgeeks.org/sql-interview-questions/",
        ],
        "Medium": [
            "https://www.javatpoint.com/python-interview-questions",
            "https://www.interviewbit.com/python-interview-questions/",
            "https://www.geeksforgeeks.org/python-interview-questions/",
        ],
        "Hard": [
            "https://www.geeksforgeeks.org/tableau-interview-questions/",
            "https://www.geeksforgeeks.org/python-interview-questions/",
            "https://www.geeksforgeeks.org/sql-interview-questions/",
            "https://www.geeksforgeeks.org/commonly-asked-dbms-interview-questions/",
        ]
    },
    "Machine Learning": {
        "Easy": [
            "https://www.javatpoint.com/machine-learning-interview-questions",
            "https://www.tutorialspoint.com/machine_learning/machine_learning_interview_questions.htm",
            "https://www.geeksforgeeks.org/machine-learning-interview-questions/",
        ],
        "Medium": [
            "https://www.interviewbit.com/machine-learning-interview-questions/",
            "https://www.simplilearn.com/tutorials/machine-learning-tutorial/machine-learning-interview-questions",
            "https://www.geeksforgeeks.org/deep-learning-interview-questions/",
        ],
        "Hard": [
            "https://www.javatpoint.com/nlp-interview-questions",
            "https://www.interviewbit.com/nlp-interview-questions/",
            "https://www.geeksforgeeks.org/nlp-interview-questions/",
        ]
    },
    "DevOps & Cloud": {
        "Easy": [
            "https://www.javatpoint.com/devops-interview-questions",
            "https://www.tutorialspoint.com/devops/devops_interview_questions.htm",
            "https://www.geeksforgeeks.org/devops-interview-questions/",
        ],
        "Medium": [
            "https://www.javatpoint.com/docker-interview-questions",
            "https://www.interviewbit.com/docker-interview-questions/",
            "https://www.geeksforgeeks.org/docker-interview-questions/",
        ],
        "Hard": [
            "https://www.javatpoint.com/kubernetes-interview-questions",
            "https://www.interviewbit.com/kubernetes-interview-questions/",
            "https://www.geeksforgeeks.org/kubernetes-interview-questions/",
        ]
    }
}

# ── Run tracking ──────────────────────────────────────────────────────────────
run_tracker = {}


def clean_question(text: str) -> str:
    """
    Remove ONLY leading number patterns like '37.', '7.', '53)', 'Q7.'
    Does NOT remove digits from inside the question (HTML5, CSS3, etc.)
    """
    t = text.strip()
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r'^\s*[Qq]?\s*\d+\s*[\.\)\:\-]\s*', '', t).strip()
    # Remove bare leading digits followed by capital letter e.g. "7 What..."
    t = re.sub(r'^\d+\s+(?=[A-Za-z])', '', t).strip()
    return t


def scrape(url: str) -> list:
    """Scrape Q&A pairs from multiple website structures."""
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        skip_kw = {
            "table of content", "introduction", "overview", "prerequisite",
            "conclusion", "summary", "faq", "related", "also read",
            "next article", "practice problem", "similar read", "advertisement",
            "must read", "explore more", "like article",
            "subscribe", "follow us", "share", "comment",
            "previous", "next", "home", "tutorial"
        }

        question_pattern = re.compile(
            r'\?|what|how|explain|difference|define|describe|when|why|which|types|list|write|compare',
            re.I
        )

        # ── Detect website and pick heading tags ──────────────────────────────
        if "javatpoint.com" in url:
            headings = soup.find_all(["h3", "h4"])
        elif "tutorialspoint.com" in url:
            headings = soup.find_all(["h2", "h3"])
        elif "interviewbit.com" in url:
            headings = soup.find_all(["h2", "h3", "h4"])
        elif "simplilearn.com" in url:
            headings = soup.find_all(["h2", "h3", "h4"])
        else:
            # GFG and others
            headings = soup.find_all(["h2", "h3"])

        for h in headings:
            raw      = h.get_text(" ", strip=True)
            question = clean_question(raw)

            if not question or len(question) < 8:
                continue
            if not question_pattern.search(question):
                continue
            if any(kw in question.lower() for kw in skip_kw):
                continue
            if len(question) > 300:
                continue

            # Collect answer paragraphs
            answer_parts = []
            sibling = h.find_next_sibling()
            for _ in range(8):
                if sibling is None:
                    break
                if sibling.name in ("h2", "h3", "h4"):
                    break
                if sibling.name in ("p", "li", "blockquote"):
                    part = sibling.get_text(" ", strip=True)
                    if part and len(part) > 15:
                        answer_parts.append(part)
                elif sibling.name in ("ul", "ol"):
                    items = [li.get_text(" ", strip=True)
                             for li in sibling.find_all("li")]
                    answer_parts.extend(items[:5])
                elif sibling.name == "div":
                    part = sibling.get_text(" ", strip=True)
                    if part and len(part) > 15:
                        answer_parts.append(part[:400])
                sibling = sibling.find_next_sibling()

            if not answer_parts:
                continue

            answer = " ".join(answer_parts)
            answer = re.sub(r'\s+', ' ', answer).strip()[:800]

            if len(answer) < 25:
                continue

            results.append({
                "question": question,
                "answer":   answer,
                "criteria": "Clarity, accuracy, depth, and real-world examples"
            })

        print(f"[Scraper] {url} → {len(results)} questions")

    except requests.exceptions.ConnectionError:
        print(f"[Scraper] No internet — {url}")
    except requests.exceptions.Timeout:
        print(f"[Scraper] Timeout — {url}")
    except Exception as e:
        print(f"[Scraper] Error — {url}: {e}")

    return results


def get_pool(domain: str, difficulty: str) -> list:
    """Try each URL until we have at least 10 unique questions."""
    urls     = SCRAPE_URLS.get(domain, {}).get(difficulty, [])
    pool     = []
    seen     = set()

    for url in urls:
        for q in scrape(url):
            cq = clean_question(q["question"])
            if cq and cq not in seen:
                seen.add(cq)
                q["question"] = cq
                pool.append(q)
        if len(pool) >= 20:
            break

    return pool


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data       = request.get_json(force=True) or {}
    domain     = data.get("domain", "Web Development")
    difficulty = data.get("difficulty", "Easy")
    COUNT      = 10

    pool = get_pool(domain, difficulty)

    if not pool:
        return jsonify({
            "error": "Could not scrape questions. Check your internet connection.",
            "questions": [], "run": 1
        })

    # ── Run rotation ──────────────────────────────────────────────────────────
    key = f"{domain}||{difficulty}"
    if key not in run_tracker:
        run_tracker[key] = {"count": 0, "batch1": [], "batch2": []}

    state   = run_tracker[key]
    state["count"] += 1
    run_num = state["count"]
    take    = min(COUNT, len(pool))

    if run_num == 1:
        selected = random.sample(pool, take)
        state["batch1"] = [q["question"] for q in selected]

    elif run_num == 2:
        used      = set(state["batch1"])
        remaining = [q for q in pool if q["question"] not in used]
        if len(remaining) >= take:
            selected = random.sample(remaining, take)
        else:
            extra = [q for q in pool if q["question"] in used]
            random.shuffle(extra)
            selected = remaining + extra[:take - len(remaining)]
            random.shuffle(selected)
        state["batch2"] = [q["question"] for q in selected]

    else:
        q_map    = {q["question"]: q for q in pool}
        combined = list(dict.fromkeys(state["batch1"] + state["batch2"]))
        mixed    = [q_map[k] for k in combined if k in q_map]
        # If old batches don't match current pool, fall back to full pool
        if not mixed:
            mixed = pool
        random.shuffle(mixed)
        selected = mixed[:take]

    run_labels = {1: "Run 1 — Fresh Questions", 2: "Run 2 — Different Questions"}
    run_label  = run_labels.get(run_num, f"Run {run_num} — Mixed Review")

    questions_out = []
    for i, q in enumerate(selected, 1):
        questions_out.append({
            "number":     i,
            "question":   q["question"],
            "answer":     q.get("answer", ""),
            "criteria":   q.get("criteria", "Clarity, accuracy, depth, examples"),
            "difficulty": difficulty,
            "domain":     domain
        })

    return jsonify({
        "questions":  questions_out,
        "run":        run_num,
        "run_label":  run_label,
        "total_pool": len(pool)
    })


@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json(force=True) or {}
    key  = f"{data.get('domain')}||{data.get('difficulty')}"
    run_tracker.pop(key, None)
    return jsonify({"status": "reset"})


if __name__ == "__main__":
    print("=" * 50)
    print("  Interview Question Generator")
    print("  Open: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)