from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import random
import re
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__, static_folder=".")
CORS(app)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

CACHE_FILE   = "cache.json"   # scraped questions saved here
CACHE_HOURS  = 24             # refresh cache every 24 hours
FORCE_SCRAPE = False          # set True to always scrape fresh

SCRAPE_URLS = {
    "Web Development": {
        "Easy": [
            "https://www.javatpoint.com/html-interview-questions",
            "https://www.tutorialspoint.com/html/html_interview_questions.htm",
            "https://www.geeksforgeeks.org/html-interview-questions-answers/",
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
            "https://www.javatpoint.com/tableau-interview-questions",
            "https://www.simplilearn.com/tutorials/tableau-tutorial/tableau-interview-questions",
            "https://www.geeksforgeeks.org/tableau-interview-questions/",
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


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — CLEAN QUESTION TEXT
# ─────────────────────────────────────────────────────────────────────────────
def clean_question(text: str) -> str:
    """Remove leading number patterns like 37. 7. 53) Q7."""
    t = text.strip()
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r'^\s*[Qq]?\s*\d+\s*[\.\)\:\-]\s*', '', t).strip()
    t = re.sub(r'^\d+\s+(?=[A-Za-z])', '', t).strip()
    return t


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — SCRAPE FROM MULTIPLE WEBSITES
# Handles GFG, Javatpoint, Tutorialspoint, Interviewbit, Simplilearn
# ─────────────────────────────────────────────────────────────────────────────
def scrape(url: str) -> list:
    """
    Fetch a page and extract Q&A pairs using BeautifulSoup.
    Handles multiple website structures automatically.
    Returns list of {question, answer, criteria}
    """
    results = []
    try:
        print(f"[Scraper] Fetching: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        skip_kw = {
            "table of content", "introduction", "overview",
            "prerequisite", "conclusion", "summary", "faq",
            "related", "also read", "next article",
            "practice problem", "advertisement", "must read",
            "subscribe", "follow us", "share", "comment",
            "previous", "next", "home", "tutorial"
        }

        question_pattern = re.compile(
            r'\?|what|how|explain|difference|define|describe|when|why|which|types|compare|list|write',
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

            # Collect answer from next siblings
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
                    # Interviewbit and Simplilearn wrap answers in divs
                    part = sibling.get_text(" ", strip=True)
                    if part and len(part) > 15:
                        answer_parts.append(part[:400])
                sibling = sibling.find_next_sibling()

            if not answer_parts:
                continue

            answer = re.sub(r'\s+', ' ', " ".join(answer_parts)).strip()[:800]
            if len(answer) < 25:
                continue

            results.append({
                "question": question,
                "answer":   answer,
                "criteria": "Clarity, accuracy, depth, and real-world examples"
            })

        print(f"[Scraper] Found {len(results)} questions from {url}")

    except requests.exceptions.ConnectionError:
        print(f"[Scraper] No internet — {url}")
    except requests.exceptions.Timeout:
        print(f"[Scraper] Timeout — {url}")
    except Exception as e:
        print(f"[Scraper] Error — {url}: {e}")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — CHECK CACHE
# If cache.json exists and is under 24 hours old → return from cache
# Otherwise → scrape fresh and save to cache
# ─────────────────────────────────────────────────────────────────────────────
# ── Built-in fallback questions (used when scraping AND cache both fail) ──────
FALLBACK_QUESTIONS = {
    "Web Development": {
        "Easy": [
            {"question":"What is HTML?","answer":"HTML (HyperText Markup Language) is the standard language for creating web pages using elements represented by tags like headings, paragraphs, links, and images.","criteria":"Understanding of markup, elements, structure"},
            {"question":"What is CSS?","answer":"CSS (Cascading Style Sheets) describes how HTML elements are displayed on screen by applying styles like color, font, spacing, and layout.","criteria":"Selectors, properties, cascade rules"},
            {"question":"What is JavaScript?","answer":"JavaScript is a programming language that makes web pages interactive and dynamic by manipulating the DOM, handling events, and communicating with servers.","criteria":"Client-side scripting, events, DOM manipulation"},
            {"question":"What is the DOM?","answer":"The Document Object Model is a tree-like representation of an HTML page that JavaScript can read and modify dynamically to update content without reloading.","criteria":"Tree structure, nodes, dynamic updates"},
            {"question":"What is Responsive Web Design?","answer":"An approach using flexible layouts, images, and CSS media queries so pages adapt and display correctly on all screen sizes from mobile to desktop.","criteria":"Media queries, mobile-first, breakpoints"},
            {"question":"What is the CSS Box Model?","answer":"Every HTML element is a rectangular box consisting of content, padding, border, and margin layers from inside out. Box-sizing controls how dimensions are calculated.","criteria":"Layer order, box-sizing property, calculations"},
            {"question":"What is Flexbox?","answer":"A CSS layout model for arranging items in a row or column with powerful alignment and distribution control using properties like justify-content and align-items.","criteria":"justify-content, align-items, flex-direction"},
            {"question":"What is the difference between GET and POST?","answer":"GET retrieves data via URL parameters and is cacheable and bookmarkable. POST sends data in the request body and is used for form submissions and sensitive data.","criteria":"Caching, idempotency, security"},
            {"question":"What is localStorage?","answer":"A browser Web Storage API that stores key-value string pairs persistently across browser sessions with no expiry date unless manually cleared.","criteria":"Vs sessionStorage, size limit, security"},
            {"question":"What is event bubbling?","answer":"When an event fires on a child element, it propagates upward through each parent element in the DOM tree until it reaches the root.","criteria":"stopPropagation, capturing phase, delegation"},
            {"question":"What is a media query?","answer":"A CSS rule that applies styles based on device characteristics like screen width, height, or orientation enabling responsive design.","criteria":"Syntax, breakpoints, mobile-first approach"},
            {"question":"What is CSS specificity?","answer":"A set of rules determining which CSS declaration wins when multiple rules target the same element. Inline beats ID beats class beats element selector.","criteria":"Scoring, conflict resolution, !important"},
            {"question":"What is JavaScript hoisting?","answer":"The JavaScript engine moves variable and function declarations to the top of their scope before execution, so they can be used before they are written.","criteria":"var vs let/const, temporal dead zone"},
            {"question":"What is a cookie?","answer":"Small pieces of data stored in the browser and sent with every HTTP request, commonly used for sessions, authentication, and user preferences.","criteria":"Vs localStorage, HttpOnly, Secure flags"},
            {"question":"What is CSS Grid?","answer":"A two-dimensional CSS layout system that lets you define rows and columns to position and align elements precisely in both directions simultaneously.","criteria":"Vs Flexbox, template areas, fr unit"},
            {"question":"What is an HTTP status code?","answer":"A numeric code in the HTTP response indicating the result: 200 OK, 404 Not Found, 500 Server Error, 301 Redirect, 401 Unauthorized.","criteria":"Five categories, common codes, meaning"},
            {"question":"What are semantic HTML elements?","answer":"Elements like header, nav, article, section, and footer that describe the meaning of content, improving accessibility and SEO.","criteria":"Examples, accessibility benefits, SEO"},
            {"question":"What is the alt attribute in images?","answer":"Alternative text displayed when an image fails to load, also read by screen readers for accessibility and indexed by search engines.","criteria":"Accessibility, SEO, fallback content"},
            {"question":"What is null vs undefined in JavaScript?","answer":"undefined means a variable has been declared but not assigned a value. null is an intentional absence of any object value assigned by the developer.","criteria":"typeof quirk, use cases, comparison"},
            {"question":"What is the difference between inline and block elements?","answer":"Block elements take up full width and start on a new line like div and p. Inline elements flow within text content like span and a.","criteria":"Examples, display property, inline-block"},
        ],
        "Medium": [
            {"question":"What is a closure in JavaScript?","answer":"A function that retains access to variables from its outer scope even after the outer function has returned, enabling data privacy and factory functions.","criteria":"Lexical scoping, use cases, memory implications"},
            {"question":"What is the Virtual DOM?","answer":"An in-memory representation of the real DOM that React uses to compute minimal updates before applying them to the actual DOM for better performance.","criteria":"Diffing, reconciliation, performance gains"},
            {"question":"What are Promises in JavaScript?","answer":"Objects representing the eventual completion or failure of an async operation with three states: pending, fulfilled, and rejected. They enable cleaner async code than callbacks.","criteria":"Chaining, async/await, error handling"},
            {"question":"What is CORS?","answer":"Cross-Origin Resource Sharing is a browser security mechanism that restricts web pages from making requests to a different domain than the one that served the page.","criteria":"Same-origin policy, preflight, Access-Control headers"},
            {"question":"What is event delegation?","answer":"Attaching a single event listener to a parent element to handle events from all its children using event bubbling, improving performance for dynamic lists.","criteria":"Performance, dynamic elements, event.target"},
            {"question":"What is debouncing vs throttling?","answer":"Debouncing delays execution until after a pause in events like search input. Throttling limits execution to once per fixed interval like scroll handlers.","criteria":"Search input use case, implementation, comparison"},
            {"question":"What is REST?","answer":"Representational State Transfer is an architectural style using HTTP methods on URL-identified stateless resources following constraints like uniform interface and statelessness.","criteria":"Constraints, HTTP semantics, statelessness"},
            {"question":"What is memoization?","answer":"Caching the results of expensive function calls so repeated calls with the same inputs return the cached result instead of recomputing.","criteria":"React.memo, useMemo, performance tradeoff"},
            {"question":"What is lazy loading?","answer":"Deferring the loading of resources like images, components, or routes until they are actually needed, improving initial page load time.","criteria":"Intersection Observer, React.lazy, performance"},
            {"question":"What is async/await in JavaScript?","answer":"Syntactic sugar over Promises that makes asynchronous code look and behave like synchronous code, using try/catch for error handling.","criteria":"Error handling, sequential vs parallel, Promise.all"},
            {"question":"What is the difference between var, let, and const?","answer":"var is function-scoped and hoisted. let and const are block-scoped. const cannot be reassigned after declaration but its object properties can change.","criteria":"Temporal dead zone, hoisting, use cases"},
            {"question":"What is WebSocket?","answer":"A full-duplex communication protocol enabling the server to push data to the client over a persistent TCP connection without polling.","criteria":"Vs HTTP polling, real-time apps, handshake"},
            {"question":"What is tree shaking?","answer":"Dead code elimination by JavaScript bundlers using static analysis of ES module imports and exports to remove unused code from the final bundle.","criteria":"Bundle size, ES modules required, sideEffects flag"},
            {"question":"What is the prototype chain in JavaScript?","answer":"Objects inherit properties and methods from other objects via Prototype references up to null, forming a chain used in prototypal inheritance.","criteria":"Traversal, ES6 classes as sugar, Object.create"},
            {"question":"What is server-side rendering vs client-side rendering?","answer":"SSR renders HTML on the server for faster initial load and better SEO. CSR renders in the browser via JavaScript after loading a minimal HTML shell.","criteria":"SEO, hydration, performance tradeoffs"},
            {"question":"What is a higher-order function?","answer":"A function that takes another function as an argument or returns a function as its result. Examples include map, filter, reduce, and forEach.","criteria":"Currying, functional programming, Array methods"},
            {"question":"What is content security policy?","answer":"An HTTP response header that restricts which resources the browser can load from which sources, preventing XSS attacks effectively.","criteria":"Directives, nonce, reporting endpoint"},
            {"question":"What is hydration in web development?","answer":"The process of attaching JavaScript event listeners to server-rendered HTML to make it interactive on the client, used in SSR frameworks.","criteria":"SSR flow, mismatch errors, partial hydration"},
            {"question":"What is the difference between call, apply, and bind?","answer":"All three control the value of this. call and apply invoke immediately with different argument styles. bind returns a new function for later invocation.","criteria":"Argument passing syntax, deferred execution"},
            {"question":"What is ES Module?","answer":"The native JavaScript module system using import and export statements enabling static analysis, tree shaking, and top-level await support.","criteria":"Vs CommonJS, static analysis, top-level await"},
        ],
        "Hard": [
            {"question":"How does the JavaScript event loop work?","answer":"The call stack processes synchronous code. Web APIs handle async tasks. The microtask queue (Promises) drains completely before each macrotask (setTimeout) executes.","criteria":"Queue ordering, rendering phase, output prediction"},
            {"question":"How does React reconciliation work?","answer":"React Fiber compares element types first, uses keys to optimize list updates, batches state updates, and schedules work by priority to minimize re-renders.","criteria":"Fiber, keys importance, batching, diffing"},
            {"question":"Describe the Critical Rendering Path.","answer":"Browser parses HTML to DOM, CSS to CSSOM, combines into Render Tree, Layout computes geometry, Paint draws pixels, Composite layers merge on GPU.","criteria":"Render-blocking resources, defer/async, FCP/LCP"},
            {"question":"What are Web Workers?","answer":"Background threads for CPU-intensive tasks that run separately from the main thread, communicating via postMessage without blocking UI or accessing the DOM.","criteria":"Thread isolation, message passing, use cases"},
            {"question":"How would you design a frontend caching strategy?","answer":"Combine HTTP cache headers, Service Worker cache for offline, React Query for in-memory, localStorage for persistence. Bust cache via content hash in filenames.","criteria":"Multiple layers, TTL, invalidation, offline support"},
            {"question":"What is micro-frontend architecture?","answer":"Splitting a frontend application into independently deployable pieces owned by different teams, composed at runtime using Module Federation or iframe techniques.","criteria":"Module Federation, shell app, tradeoffs"},
            {"question":"How does JavaScript garbage collection work?","answer":"The mark-and-sweep algorithm marks all reachable objects from GC roots and sweeps away unmarked ones. Memory leaks occur via closures, detached DOM, global vars.","criteria":"GC algorithm, leak detection, WeakMap/WeakRef"},
            {"question":"What is partial hydration?","answer":"Hydrating only interactive components instead of the entire page, reducing JavaScript payload and improving Time To Interactive significantly.","criteria":"Astro, Next.js, progressive hydration"},
            {"question":"How would you optimize a slow React application?","answer":"Profile with React DevTools, memoize with React.memo/useMemo/useCallback, virtualize long lists with react-window, code split routes, avoid layout thrashing.","criteria":"Profiling, memoization, virtualization, bundle"},
            {"question":"What is the difference between authentication and authorization?","answer":"Authentication verifies who you are via credentials like passwords or tokens. Authorization determines what resources and actions you are allowed to access.","criteria":"JWT, OAuth, RBAC, examples"},
        ],
    },
    "Data Science": {
        "Easy": [
            {"question":"What is supervised learning?","answer":"A type of machine learning where the model learns from labeled training data to map inputs to known output labels for classification or regression tasks.","criteria":"Examples, labeled data, classification vs regression"},
            {"question":"What is overfitting?","answer":"When a model learns the training data too well including noise and outliers, resulting in poor performance on new unseen data due to lack of generalization.","criteria":"Train vs test gap, prevention techniques"},
            {"question":"What is cross-validation?","answer":"A technique dividing data into k folds, training on k-1 folds and testing on the remaining fold, repeated k times for a more reliable performance estimate.","criteria":"K-fold process, stratified, purpose"},
            {"question":"What is data normalization?","answer":"Scaling numerical features to a standard range so no single feature dominates distance-based algorithms due to differences in unit or magnitude.","criteria":"Min-max, z-score, when to apply"},
            {"question":"What is a confusion matrix?","answer":"A table summarizing classification model performance showing True Positives, True Negatives, False Positives, and False Negatives counts.","criteria":"All four cells, derived metrics like precision recall"},
            {"question":"What is feature engineering?","answer":"Creating, transforming, or selecting input variables using domain knowledge to improve model learning and achieve better predictive performance.","criteria":"Examples, transformation types, domain knowledge"},
            {"question":"What is a p-value?","answer":"The probability of observing results as extreme as the data assuming the null hypothesis is true. A small p-value suggests evidence against the null hypothesis.","criteria":"Correct interpretation, common misconceptions"},
            {"question":"What is EDA?","answer":"Exploratory Data Analysis is the process of summarizing and visualizing a dataset using statistics and plots to understand its structure before modeling.","criteria":"Goals, visualizations, statistical summaries"},
            {"question":"What is correlation vs causation?","answer":"Correlation means two variables move together statistically. Causation means one directly causes the other. Correlation never proves causation alone.","criteria":"Confounding variables, RCT, examples"},
            {"question":"What is a train-test split?","answer":"Dividing a dataset into a training portion for learning parameters and a test portion held out for unbiased final evaluation of model performance.","criteria":"Ratios, data leakage, validation set"},
            {"question":"What is variance in statistics?","answer":"The average squared deviation of each value from the mean, measuring how spread out the data is. Standard deviation is its square root.","criteria":"Relationship to standard deviation, empirical rule"},
            {"question":"What is the central limit theorem?","answer":"As sample size increases, the distribution of sample means approaches a normal distribution regardless of the population distribution shape.","criteria":"Practical implications, minimum sample size"},
            {"question":"What is a null hypothesis?","answer":"The default assumption that there is no effect or relationship between variables. It is rejected when the p-value falls below the significance threshold.","criteria":"H0 vs H1, p-value, significance level"},
            {"question":"What is a boxplot?","answer":"A visualization showing the five-number summary: minimum, Q1, median, Q3, maximum, with points beyond 1.5 times IQR marked as outliers.","criteria":"IQR, quartiles, outlier detection"},
            {"question":"What is data imputation?","answer":"Filling in missing values using strategies like mean, median, mode, KNN, or multiple imputation to preserve dataset size and avoid bias.","criteria":"MCAR MAR MNAR, strategy selection"},
        ],
        "Medium": [
            {"question":"Explain the bias-variance tradeoff.","answer":"Total prediction error equals bias squared plus variance plus irreducible noise. Complex models reduce bias but increase variance causing overfitting and vice versa.","criteria":"Mathematical decomposition, regularization solutions"},
            {"question":"What is PCA?","answer":"Principal Component Analysis reduces dimensionality by finding orthogonal components capturing maximum variance in descending order using eigenvectors of the covariance matrix.","criteria":"Eigenvectors, explained variance, preprocessing needed"},
            {"question":"What is L1 vs L2 regularization?","answer":"L1 (Lasso) adds absolute weight penalty producing sparse models with feature selection. L2 (Ridge) adds squared penalty shrinking all weights smoothly without zeroing them.","criteria":"Sparsity, geometric interpretation, ElasticNet"},
            {"question":"How does gradient descent work?","answer":"Iteratively updates model parameters by stepping in the negative gradient direction of the loss function. Learning rate controls step size toward the minimum.","criteria":"Learning rate, SGD vs batch, Adam optimizer"},
            {"question":"What is bagging vs boosting?","answer":"Bagging trains independent models in parallel on random subsets reducing variance like Random Forest. Boosting trains sequentially correcting previous errors reducing bias like XGBoost.","criteria":"Variance vs bias reduction, examples"},
            {"question":"What is A/B testing?","answer":"A controlled experiment randomly assigning users to two versions to measure which performs better on a target metric with statistical significance testing.","criteria":"Power analysis, significance, p-hacking risks"},
            {"question":"What is the ROC-AUC curve?","answer":"ROC plots True Positive Rate vs False Positive Rate at all classification thresholds. AUC measures overall discriminative ability where 1 is perfect and 0.5 is random.","criteria":"Threshold independence, imbalanced classes"},
            {"question":"What is K-means clustering?","answer":"An iterative algorithm partitioning data into K clusters by minimizing within-cluster sum of squared distances to centroids, reassigning points each iteration.","criteria":"Elbow method, limitations, initialization sensitivity"},
            {"question":"What is the F1 score?","answer":"The harmonic mean of precision and recall providing a balanced single metric especially useful when class distributions are imbalanced.","criteria":"When to use over accuracy, formula"},
            {"question":"What is feature selection?","answer":"Choosing the most informative subset of features to reduce dimensionality, improve generalization, speed up training, and reduce overfitting risk.","criteria":"Filter, wrapper, embedded methods"},
        ],
        "Hard": [
            {"question":"How does XGBoost work?","answer":"Uses second-order Taylor expansion of the loss to optimize a regularized objective with column subsampling, shrinkage, and parallel tree construction for speed and accuracy.","criteria":"Objective function, vs GBM, key hyperparameters"},
            {"question":"How do you handle class imbalance?","answer":"Use SMOTE oversampling, class_weight parameter, threshold tuning, cost-sensitive learning, and evaluate with AUC-ROC and F1 instead of raw accuracy.","criteria":"Multiple strategies, when to use each"},
            {"question":"Explain Bayesian inference.","answer":"Updates prior beliefs P(H) with observed evidence via likelihood P(D|H) to compute posterior P(H|D) proportional to likelihood times prior using Bayes theorem.","criteria":"Prior, posterior, likelihood, MCMC sampling"},
            {"question":"What is causal inference?","answer":"Estimating the causal effect of an intervention beyond correlation using randomized experiments or observational methods like instrumental variables and difference-in-differences.","criteria":"Confounders, counterfactuals, RCT vs observational"},
            {"question":"Explain SHAP values.","answer":"Shapley values from cooperative game theory assign each feature its average marginal contribution across all possible feature orderings ensuring fair attribution.","criteria":"vs LIME, consistency property, TreeSHAP efficiency"},
        ],
    },
    "Data Analysis": {
        "Easy": [
            {"question":"What is SQL?","answer":"Structured Query Language is the standard language for querying, manipulating, and managing relational databases using commands like SELECT, INSERT, UPDATE, DELETE.","criteria":"Core clauses, DDL vs DML, use cases"},
            {"question":"What is a JOIN in SQL?","answer":"An operation combining rows from two or more tables based on a related column. INNER returns matches only, LEFT returns all from left plus matches.","criteria":"All join types, NULL handling, examples"},
            {"question":"What is GROUP BY in SQL?","answer":"A clause grouping rows with the same values into summary rows for aggregate calculations like COUNT, SUM, AVG used with SELECT.","criteria":"Aggregate functions, HAVING clause, execution order"},
            {"question":"What is a NULL in SQL?","answer":"The absence of a value, distinct from zero or empty string. Comparisons require IS NULL or IS NOT NULL operators not equals sign.","criteria":"NULL arithmetic, COALESCE, NVL"},
            {"question":"What is data cleaning?","answer":"The process of detecting and correcting errors, inconsistencies, duplicates, and missing values in a dataset to ensure quality before analysis.","criteria":"Common issues, techniques, importance"},
            {"question":"What is an outlier?","answer":"A data point significantly different from other observations, detected using IQR method beyond 1.5 times IQR from quartiles or Z-score threshold of 3.","criteria":"Detection methods, impact, whether to remove"},
            {"question":"What is a KPI?","answer":"Key Performance Indicator is a measurable value demonstrating how effectively an organization or individual achieves specific business objectives over time.","criteria":"Leading vs lagging, SMART criteria, examples"},
            {"question":"What is ETL?","answer":"Extract Transform Load is the process of moving data from source systems, transforming it to the required format, and loading it into a target data store.","criteria":"Stages, tools, vs ELT, idempotency"},
            {"question":"What is a pivot table?","answer":"An interactive table that summarizes and aggregates data by grouping rows and columns for quick analysis of patterns and comparisons.","criteria":"Aggregation functions, Excel vs pandas pivot"},
            {"question":"What is a dashboard?","answer":"An interactive visual display aggregating key metrics and KPIs from multiple data sources into a single unified view for decision makers.","criteria":"Tools, refresh rate, audience"},
        ],
        "Medium": [
            {"question":"What are SQL window functions?","answer":"Functions performing calculations across rows related to the current row without collapsing them, using OVER clause with optional PARTITION BY and ORDER BY.","criteria":"ROW_NUMBER, LAG, LEAD, running totals"},
            {"question":"What is cohort analysis?","answer":"Tracking groups of users sharing a common characteristic within a defined time period to analyze retention, behavior, and lifetime value over time.","criteria":"Retention table, LTV calculation, interpretation"},
            {"question":"What is a CTE in SQL?","answer":"Common Table Expression is a temporary named result set defined using WITH clause that simplifies complex queries and enables recursive queries.","criteria":"Vs subquery, recursive CTE, readability"},
            {"question":"What is a star schema?","answer":"A data warehouse design with a central fact table containing metrics surrounded by denormalized dimension tables containing descriptive attributes.","criteria":"Vs snowflake schema, fact vs dimension, denormalized"},
            {"question":"What is OLAP vs OLTP?","answer":"OLAP optimizes for complex analytical queries on large historical data in warehouses. OLTP optimizes for fast transactional reads and writes on current operational data.","criteria":"Query patterns, normalization, data warehouse"},
            {"question":"What is data wrangling?","answer":"Transforming and mapping raw messy data into a clean format suitable for analysis through reshaping, merging, cleaning, filtering, and encoding steps.","criteria":"Pandas operations, common issues, tidy data"},
            {"question":"What is a funnel analysis?","answer":"Tracking how users progress through a sequence of steps in a conversion process to identify where the biggest drop-offs occur for optimization.","criteria":"Conversion rates, optimization, A/B testing"},
            {"question":"What is statistical significance?","answer":"A result is statistically significant when p is less than 0.05, meaning it is unlikely to occur by chance, though practical significance also matters.","criteria":"Effect size, p-hacking, statistical power"},
            {"question":"What is the Pareto Principle in data analysis?","answer":"80% of effects come from 20% of causes. Used to prioritize analysis and effort on the most impactful items first for maximum business impact.","criteria":"Pareto chart, ABC analysis, business applications"},
            {"question":"What is a running total in SQL?","answer":"A cumulative sum calculated using SUM() OVER ORDER BY column window function that adds each row value to the previous running total.","criteria":"Syntax, partitioned running totals, examples"},
        ],
        "Hard": [
            {"question":"How would you design an end-to-end analytics pipeline?","answer":"Source systems feed ingestion layer into raw storage. dbt transforms into staging and mart layers. BI tool serves business dashboards with proper testing at each stage.","criteria":"Full stack, tools, idempotency, testing"},
            {"question":"What is ETL vs ELT?","answer":"ETL transforms data before loading which is traditional. ELT loads raw data first then transforms using warehouse compute power, enabled and preferred in cloud data warehouses.","criteria":"Cloud warehouses, dbt, data lineage implications"},
            {"question":"What are Slowly Changing Dimensions?","answer":"SCD types handle historical changes in dimension data: Type 1 overwrites old value, Type 2 adds new row with effective dates, Type 3 adds previous value column.","criteria":"SQL implementation, surrogate keys, use cases"},
            {"question":"What is the medallion architecture?","answer":"Bronze layer stores raw ingested data. Silver layer applies cleaning and validation rules. Gold layer contains aggregated business-ready curated data products.","criteria":"Delta Lake, data quality, incremental processing"},
            {"question":"How do you ensure data quality at scale?","answer":"Implement Great Expectations tests, dbt schema and data tests, data contracts between producers and consumers, SLA monitoring, and automated anomaly detection alerts.","criteria":"Quality dimensions, tooling, alerting strategy"},
        ],
    },
    "Machine Learning": {
        "Easy": [
            {"question":"What is the difference between classification and regression?","answer":"Classification predicts discrete category labels like spam or not spam. Regression predicts continuous numerical values like house prices.","criteria":"Metrics for each, examples, boundary cases"},
            {"question":"What is a decision tree?","answer":"A tree-shaped model that recursively splits data on feature values using Gini impurity or entropy criteria, interpretable but prone to overfitting without pruning.","criteria":"Structure, splitting criteria, pruning"},
            {"question":"What is random forest?","answer":"An ensemble of decision trees each trained on a random subset of data and features, aggregating predictions by majority vote to reduce overfitting.","criteria":"Bagging, feature importance, out-of-bag error"},
            {"question":"What is a hyperparameter?","answer":"A configuration value set before training like learning rate, number of trees, or tree depth, as opposed to model parameters learned from data during training.","criteria":"Tuning methods, grid search, validation set"},
            {"question":"What is dropout regularization?","answer":"Randomly deactivating a fraction of neurons during each training forward pass to prevent co-adaptation and reduce overfitting in neural networks.","criteria":"Keep probability, behavior at test time"},
            {"question":"What is transfer learning?","answer":"Using a model pretrained on a large dataset as a starting point for a different but related task, requiring significantly less data and compute.","criteria":"Feature extraction vs fine-tuning, pretrained models"},
            {"question":"What is a loss function?","answer":"A function measuring the difference between model predictions and true target values, guiding parameter optimization during training to minimize prediction error.","criteria":"MSE for regression, cross-entropy for classification"},
            {"question":"What is precision vs recall?","answer":"Precision is TP divided by TP plus FP measuring exactness. Recall is TP divided by TP plus FN measuring completeness. The tradeoff depends on error costs.","criteria":"F1 score, threshold adjustment, use cases"},
            {"question":"What is gradient descent?","answer":"An optimization algorithm minimizing a loss function by iteratively moving parameters in the negative gradient direction by a step size called the learning rate.","criteria":"Learning rate, convergence, variants SGD Adam"},
            {"question":"What is batch normalization?","answer":"Normalizing layer inputs to zero mean and unit variance during training to stabilize learning, allow higher learning rates, and act as mild regularization.","criteria":"Internal covariate shift, gamma beta parameters"},
        ],
        "Medium": [
            {"question":"How does backpropagation work?","answer":"Computes gradients of the loss with respect to each weight using the chain rule of calculus, propagating error signals backward from output layer to input layer.","criteria":"Forward pass, chain rule, vanishing gradients"},
            {"question":"What is the attention mechanism?","answer":"Computes a weighted sum of values where weights are the softmax of scaled dot products between queries and keys, enabling dynamic focus on relevant inputs.","criteria":"Q K V matrices, multi-head attention, scaled dot product"},
            {"question":"What is an LSTM?","answer":"Long Short-Term Memory networks use forget, input, and output gates controlling information flow through a cell state, solving the vanishing gradient problem in sequences.","criteria":"Gates, cell state vs hidden state, vs GRU"},
            {"question":"What is a GAN?","answer":"Generative Adversarial Network trains a Generator to fool a Discriminator in a minimax game until the generator produces indistinguishable realistic data.","criteria":"Mode collapse, training instability, WGAN improvements"},
            {"question":"What is reinforcement learning?","answer":"An agent learns to maximize cumulative reward by taking actions in an environment through trial and error without labeled examples, guided by reward signals.","criteria":"MDP, policy, reward signal, exploration vs exploitation"},
            {"question":"What is XGBoost?","answer":"An optimized gradient boosting library using second-order Taylor expansion, L1/L2 regularization, column subsampling, and parallel tree construction for speed.","criteria":"Objective function, key parameters, vs LightGBM"},
            {"question":"What is a Transformer?","answer":"A sequence model using only multi-head self-attention and feed-forward layers with positional encoding, enabling parallelization and long-range dependency capture.","criteria":"Encoder decoder, positional encoding, BERT GPT"},
            {"question":"What is the vanishing gradient problem?","answer":"Gradients become exponentially small during backpropagation through many layers preventing early layers from updating and learning meaningful representations.","criteria":"Causes, solutions: ReLU, BatchNorm, residual connections"},
            {"question":"What is hyperparameter tuning?","answer":"Finding the optimal hyperparameter configuration using grid search, random search, or Bayesian optimization evaluated on a held-out validation set.","criteria":"Search strategies, cross-validation, Optuna"},
            {"question":"What is word2vec?","answer":"Learns dense word embeddings by training a shallow neural network to predict context words given a target or predict a target given context words.","criteria":"Embeddings, semantic similarity, analogies"},
        ],
        "Hard": [
            {"question":"How do GANs work and what are the training challenges?","answer":"Generator and Discriminator play minimax game until equilibrium. Key challenges are mode collapse, training instability, and vanishing gradients addressed by WGAN loss.","criteria":"Minimax objective, evaluation metrics, architectures"},
            {"question":"Explain the Transformer architecture in depth.","answer":"Encoder and decoder stacks with multi-head scaled dot-product attention, residual connections, layer normalization, and position-wise feed-forward sublayers with positional encoding.","criteria":"Attention computation, masking, scaling factor"},
            {"question":"What is contrastive learning?","answer":"Learns representations by pulling similar positive pairs together and pushing dissimilar negative pairs apart in embedding space using contrastive loss functions.","criteria":"SimCLR, NT-Xent loss, augmentation strategy, hard negatives"},
            {"question":"What are diffusion models?","answer":"Generate data by learning to reverse a gradual Gaussian noising process. Forward process adds noise step by step and reverse process denoises with a neural network.","criteria":"DDPM, score matching, DALL-E Stable Diffusion"},
            {"question":"What is federated learning?","answer":"Training models across decentralized devices without centralizing raw data. FedAvg aggregates locally computed gradient updates at a central server each round.","criteria":"Privacy, communication efficiency, heterogeneous data"},
        ],
    },
    "DevOps & Cloud": {
        "Easy": [
            {"question":"What is DevOps?","answer":"A cultural and technical movement combining Development and Operations teams to deliver software faster and more reliably through automation, collaboration, and continuous improvement.","criteria":"CALMS framework, benefits, CI/CD connection"},
            {"question":"What is Docker?","answer":"A containerization platform packaging applications with all their dependencies into portable lightweight containers that run consistently across any environment.","criteria":"Image, container, Dockerfile, registry, layers"},
            {"question":"What is CI/CD?","answer":"Continuous Integration automates building and testing on every commit. Continuous Delivery automates releasing validated artifacts to staging or production environments.","criteria":"Pipeline stages, tools, quality gates"},
            {"question":"What is Kubernetes?","answer":"An open-source container orchestration system automating deployment, scaling, load balancing, health checking, and self-healing of containerized applications across clusters.","criteria":"Pods, Deployments, Services, control plane"},
            {"question":"What are IaaS, PaaS, and SaaS?","answer":"IaaS provides virtual machines and storage. PaaS provides managed runtime platforms. SaaS provides fully managed software accessed via browser without installation.","criteria":"Shared responsibility model, examples of each"},
            {"question":"What is Infrastructure as Code?","answer":"Managing and provisioning infrastructure through machine-readable configuration files instead of manual clicking, enabling versioning, repeatability, and automation.","criteria":"Terraform, CloudFormation, declarative vs imperative"},
            {"question":"What is a microservice?","answer":"A small independently deployable service owning a specific business capability and its own database, communicating with other services via APIs or messaging.","criteria":"Vs monolith, bounded context, tradeoffs"},
            {"question":"What is a load balancer?","answer":"A component distributing incoming network traffic across multiple server instances to ensure no single server is overwhelmed, improving availability and throughput.","criteria":"Layer 4 vs 7, algorithms, health checks"},
            {"question":"What is horizontal vs vertical scaling?","answer":"Horizontal scaling adds more server instances to distribute load across them. Vertical scaling adds more CPU or RAM to existing instances. Cloud prefers horizontal.","criteria":"Stateless requirement, auto-scaling, limits"},
            {"question":"What is a VPC?","answer":"Virtual Private Cloud is a logically isolated section of a cloud provider network where you launch resources with custom IP ranges, subnets, and routing rules.","criteria":"Subnets, route tables, NAT gateway, security groups"},
        ],
        "Medium": [
            {"question":"Explain the CI/CD pipeline stages.","answer":"Source commit triggers build, unit and integration tests run, security scans execute, artifact deploys to staging, acceptance tests run, then production deployment.","criteria":"Testing pyramid, deployment strategies, rollback"},
            {"question":"What is blue-green vs canary deployment?","answer":"Blue-green switches all traffic instantly between two identical environments enabling fast rollback. Canary gradually shifts traffic percentage while monitoring metrics.","criteria":"Resource cost, rollback speed, risk reduction"},
            {"question":"What is observability?","answer":"The ability to understand a system internal state from external outputs using the three pillars: metrics for aggregation, logs for events, and traces for request flow.","criteria":"Three pillars, tools, vs monitoring, cardinality"},
            {"question":"What is GitOps?","answer":"Using Git as the single source of truth for infrastructure and application configuration, with operators continuously reconciling actual cluster state to desired Git state.","criteria":"ArgoCD, Flux, drift detection, pull vs push"},
            {"question":"What is Terraform?","answer":"A declarative Infrastructure as Code tool managing multi-cloud resources through HCL configuration files, tracking deployed resource state in a state file.","criteria":"Plan apply destroy, state file, modules, providers"},
            {"question":"What is Prometheus?","answer":"An open-source monitoring system scraping time-series metrics from instrumented targets via HTTP pull model and supporting alerting via Alertmanager.","criteria":"PromQL, exporters, Grafana integration, pull model"},
            {"question":"What is a service mesh?","answer":"An infrastructure layer handling service-to-service communication concerns including mutual TLS, retries, circuit breaking, and distributed tracing via sidecar proxies.","criteria":"Istio, Linkerd, Envoy sidecar, control plane"},
            {"question":"What is immutable infrastructure?","answer":"Servers are never modified after deployment. Updates deploy new instances from updated images and terminate old ones ensuring consistency and eliminating configuration drift.","criteria":"Golden images, reproducibility, vs mutable"},
            {"question":"What is the 12-factor app methodology?","answer":"Twelve principles for cloud-native apps covering codebase, dependencies, config in environment, backing services, stateless processes, and logs as event streams.","criteria":"Key factors, cloud-native, containers alignment"},
            {"question":"What is log aggregation?","answer":"Centralizing logs from multiple distributed services into a single searchable platform for debugging, monitoring, auditing, and compliance purposes.","criteria":"ELK stack, Fluentd, structured logging, retention"},
        ],
        "Hard": [
            {"question":"How would you design a multi-region highly available architecture?","answer":"Active-active with global load balancer using latency routing, cross-region database replication, CDN for static assets, accepting consistency tradeoffs per CAP theorem.","criteria":"RTO RPO objectives, CAP theorem, replication lag"},
            {"question":"What is chaos engineering?","answer":"Proactively injecting controlled failures into production systems to discover weaknesses before they cause incidents, starting with small blast radius experiments.","criteria":"Chaos Monkey, blast radius limiting, game days"},
            {"question":"What is the SRE approach to reliability?","answer":"Define SLIs as metrics, SLOs as targets, SLAs as commitments. Use error budgets to balance reliability and feature velocity. Blameless postmortems reduce toil.","criteria":"Error budget policy, alerting on symptoms, runbooks"},
            {"question":"How would you implement a disaster recovery strategy?","answer":"Define RTO and RPO objectives then choose appropriate strategy from backup-restore to active-active. Automate failover procedures and conduct regular DR drills.","criteria":"Recovery strategies, cost vs speed tradeoff, testing"},
            {"question":"What is zero-trust security?","answer":"Never trust always verify principle using workload identity, mutual TLS between services, policy-as-code authorization, secrets management, and micro-segmentation.","criteria":"BeyondCorp, SPIRE, least privilege, audit logging"},
        ],
    },
}


def get_fallback(domain: str, difficulty: str) -> list:
    """Return built-in questions when all else fails."""
    return FALLBACK_QUESTIONS.get(domain, {}).get(difficulty, [])


def load_cache() -> dict:
    """Load cache.json if it exists."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache: dict):
    """Save updated cache to cache.json."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"[Cache] Saved to {CACHE_FILE}")
    except Exception as e:
        print(f"[Cache] Could not save: {e}")


def is_cache_fresh(cache: dict, key: str) -> bool:
    """Check if cached data for this key is under 24 hours old."""
    if key not in cache:
        return False
    try:
        saved_time = datetime.fromisoformat(cache[key]["timestamp"])
        return datetime.now() - saved_time < timedelta(hours=CACHE_HOURS)
    except Exception:
        return False


def get_pool(domain: str, difficulty: str) -> list:
    """
    3 step fallback system:
    Step 1 → ALWAYS scrape websites first (never read cache first) ✅
    Step 2 → Scraping failed → use cache.json as backup ✅
    Step 3 → Cache also empty → use built-in questions ✅
    """
    cache_key = f"{domain}||{difficulty}"

    # ── STEP 1: ALWAYS scrape websites first — never skip this ───────────────
    print(f"[Scraper] Fetching LIVE from websites for {domain} / {difficulty}...")
    urls = SCRAPE_URLS.get(domain, {}).get(difficulty, [])
    pool = []
    seen = set()

    for url in urls:
        for q in scrape(url):
            cq = clean_question(q["question"])
            if cq and cq not in seen:
                seen.add(cq)
                q["question"] = cq
                pool.append(q)
        if len(pool) >= 20:
            break

    # Scraping succeeded → update cache silently and return live questions
    if pool:
        try:
            cache = load_cache()
            cache[cache_key] = {
                "timestamp": datetime.now().isoformat(),
                "questions": pool
            }
            save_cache(cache)
        except Exception:
            pass
        print(f"[Scraper] SUCCESS ✅ — {len(pool)} live questions from websites")
        return pool

    # ── STEP 2: Scraping failed → use cache as backup ────────────────────────
    print(f"[Scraper] All websites failed — trying cache backup...")
    cache = load_cache()
    if cache_key in cache:
        old_questions = cache[cache_key]["questions"]
        print(f"[Cache] Using cached backup ✅ ({len(old_questions)} questions)")
        return old_questions

    # ── STEP 3: Cache also empty → use built-in questions ────────────────────
    fallback = get_fallback(domain, difficulty)
    if fallback:
        print(f"[Fallback] Using built-in questions ✅ ({len(fallback)} questions)")
        return fallback

    print(f"[Error] No questions available for {domain} {difficulty}")
    return []


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
    print(f"[DEBUG] pool size = {len(pool)} for {domain} / {difficulty}")

    if not pool:
        return jsonify({
            "error": "Could not get questions. Check internet connection for first-time scraping.",
            "questions": [], "run": 1
        })

    # ── Run rotation logic ────────────────────────────────────────────────────
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
            "answer":     q["answer"],
            "criteria":   q["criteria"],
            "difficulty": difficulty,
            "domain":     domain
        })

    return jsonify({
        "questions":  questions_out,
        "run":        run_num,
        "run_label":  run_label,
        "total_pool": len(pool)
    })


if __name__ == "__main__":
    print("=" * 50)
    print("  Interview Question Generator")
    print("  Method: Web Scraping + Caching")
    if os.path.exists(CACHE_FILE):
        print(f"  Cache file found: {CACHE_FILE} ✅")
    else:
        print(f"  No cache yet — will scrape on first request")
    print("  Open: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)