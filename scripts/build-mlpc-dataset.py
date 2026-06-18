# -*- coding: utf-8 -*-
"""Build the MLPC static study dataset from local PDFs.

The question records are curated because Moodle PDF exports interleave useful
exam content with attempt-review noise. Slide chunks are extracted directly so
questions can be linked to lecture material and vectorized later.
"""

from __future__ import annotations

import json
import math
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz


APP_DIR = Path(__file__).resolve().parents[1]
PDF_DIR = APP_DIR.parent
DATA_DIR = APP_DIR / "lib" / "data"


LECTURE_FILES = [
    ("lecture-01", 1, "01_Introduction_to_Class.pdf", "Introduction to Classification"),
    ("lecture-02", 2, "02_Bayesian_Decision_Theory.pdf", "Bayesian Decision Theory"),
    ("lecture-03", 3, "03_Density_Estimation.pdf", "Density Estimation"),
    ("lecture-04", 4, "04_Classification_General_Issues.pdf", "Classification: General Issues"),
    ("lecture-05", 5, "05_Common_Machine_Learning_Algorithms.pdf", "Common Machine Learning Algorithms"),
    ("lecture-06", 6, "06_Improving_Learning_Results.pdf", "Improving Learning Results"),
    ("lecture-07", 7, "07_Neural_Networks.pdf", "Neural Networks"),
    ("lecture-08", 8, "08_Deep_Learning.pdf", "Deep Learning"),
    ("lecture-09", 9, "09_Deep_Learning_For_SED.pdf.pdf", "Deep Learning for Sound Event Detection"),
    ("lecture-10", 10, "10_Unsupervised_Learning.pdf", "Unsupervised Learning"),
]

EXAM_FILES = [
    ("exam-retake-1", "mlpc-retake-1.pdf", None, "MLPC retake question export 1"),
    ("exam-retake-2", "mlpc-retake-2.pdf", None, "MLPC retake question export 2"),
    ("exam-retake-3", "mlpc-retake-3.pdf", None, "MLPC retake question export 3"),
    ("exam-retake-4", "mlpc-retake-4.pdf", None, "MLPC retake question export 4"),
    ("exam-retake-5", "mlpc-retake-5.pdf", None, "MLPC retake question export 5"),
    ("exam-retake-6", "mlpc-retake-6.pdf", None, "MLPC retake question export 6"),
    ("exam-ss20", "MLPC_SS20.pdf", 2020, "MLPC SS20 exam"),
    ("exam-ss22", "MLPC_SS22_exam.pdf", 2022, "MLPC SS22 final exam"),
    ("exam-2023-retake", "pc_exam_2023_retry.pdf", 2023, "MLPC 2023 retake exam"),
]

IMAGE_FILES = [
    ("img-closed-book-2026-p02", "WhatsApp_Image_2026-06-15_at_13.37.38_2.jpeg", "closed-book-2026-group-b-page-02.jpeg", 2, "2026 closed-book exam image, Group B page 2", None),
    ("img-closed-book-2026-p03", "WhatsApp_Image_2026-06-15_at_13.37.37.jpeg", "closed-book-2026-group-b-page-03.jpeg", 3, "2026 closed-book exam image, Group B page 3", None),
    ("img-closed-book-2026-p04", "WhatsApp_Image_2026-06-15_at_13.37.38_3.jpeg", "closed-book-2026-group-b-page-04.jpeg", 4, "2026 closed-book exam image, Group B page 4", None),
    ("img-closed-book-2026-p05", "WhatsApp_Image_2026-06-15_at_13.37.39_3.jpeg", "closed-book-2026-group-b-page-05.jpeg", 5, "2026 closed-book exam image, Group B page 5", None),
    ("img-closed-book-2026-p06", "WhatsApp_Image_2026-06-15_at_13.37.39.jpeg", "closed-book-2026-group-b-page-06.jpeg", 6, "2026 closed-book exam image, Group B page 6", None),
    ("img-closed-book-2026-p07", "WhatsApp_Image_2026-06-15_at_13.37.39_2.jpeg", "closed-book-2026-group-b-page-07.jpeg", 7, "2026 closed-book exam image, Group B page 7", None),
    ("img-closed-book-2026-p08", "WhatsApp_Image_2026-06-15_at_13.37.38_4.jpeg", "closed-book-2026-group-b-page-08.jpeg", 8, "2026 closed-book exam image, Group B page 8", None),
    ("img-closed-book-2026-p09", "WhatsApp_Image_2026-06-15_at_13.37.38.jpeg", "closed-book-2026-group-b-page-09.jpeg", 9, "2026 closed-book exam image, Group B page 9", None),
    ("img-closed-book-2026-p10", "WhatsApp_Image_2026-06-15_at_13.37.39_1.jpeg", "closed-book-2026-group-b-page-10.jpeg", 10, "2026 closed-book exam image, Group B page 10", None),
    ("img-closed-book-2026-p10-alt", "WhatsApp_Image_2026-06-15_at_13.37.38_1.jpeg", "closed-book-2026-group-b-page-10-alt.jpeg", 10, "2026 closed-book exam image, Group B page 10 alternate capture", "img-closed-book-2026-p10"),
    ("img-closed-book-2026-p11", "WhatsApp_Image_2026-06-15_at_13.37.37_1.jpeg", "closed-book-2026-group-b-page-11.jpeg", 11, "2026 closed-book exam image, Group B page 11", None),
]

TOPICS = [
    {
        "id": "intro-classification",
        "title": "Classification Basics",
        "lectureIds": ["lecture-01"],
        "description": "Feature spaces, supervised learning setup, decision regions, and baseline ideas.",
    },
    {
        "id": "bayesian-classification",
        "title": "Bayesian Classification",
        "lectureIds": ["lecture-02"],
        "description": "Bayes rule, MAP, evidence, priors, likelihoods, posteriors, Bayes error, and minimum risk.",
    },
    {
        "id": "density-estimation",
        "title": "Density Estimation",
        "lectureIds": ["lecture-03"],
        "description": "Parametric and non-parametric density estimation, likelihoods, MLE, and estimation pitfalls.",
    },
    {
        "id": "nearest-neighbour",
        "title": "Nearest Neighbour Classifiers",
        "lectureIds": ["lecture-03", "lecture-05"],
        "description": "k-NN behavior, distance metrics, scaling, redundant features, and bias-variance effects.",
    },
    {
        "id": "classifier-evaluation",
        "title": "Classifier Evaluation",
        "lectureIds": ["lecture-04"],
        "description": "Training/test estimates, overfitting, precision, recall, ROC space, cost matrices, and operating points.",
    },
    {
        "id": "decision-trees",
        "title": "Decision Trees",
        "lectureIds": ["lecture-05"],
        "description": "ID3, entropy, information gain, symbolic vs numeric splits, pruning, and tree depth.",
    },
    {
        "id": "common-classifiers",
        "title": "Common Classifiers",
        "lectureIds": ["lecture-05"],
        "description": "Naive Bayes, SVMs, k-NN, decision-tree relatives, kernels, and practical classifier behavior.",
    },
    {
        "id": "learning-improvement",
        "title": "Improving Learning Results",
        "lectureIds": ["lecture-06"],
        "description": "Feature selection and construction, model selection, parameter optimization, ensembles, and post-processing.",
    },
    {
        "id": "neural-networks",
        "title": "Neural Networks",
        "lectureIds": ["lecture-07"],
        "description": "Feed-forward networks, activation functions, bias units, losses, gradient descent, and overfitting.",
    },
    {
        "id": "deep-learning",
        "title": "Deep Learning",
        "lectureIds": ["lecture-08", "lecture-09"],
        "description": "Tensor mappings, convolutional layers, data augmentation, depth, representation, and SED architectures.",
    },
    {
        "id": "unsupervised-learning",
        "title": "Unsupervised Learning",
        "lectureIds": ["lecture-10"],
        "description": "k-means, mean quantisation error, Gaussian mixture models, BIC, and clustering model selection.",
    },
    {
        "id": "markov-models-hmm",
        "title": "Markov Models and HMMs",
        "lectureIds": ["lecture-10"],
        "description": "Markov chains, transition matrices, observation matrices, priors, sequence likelihood, and the Forward algorithm.",
    },
]

TOPIC_BY_ID = {topic["id"]: topic for topic in TOPICS}

STOPWORDS = {
    "about",
    "above",
    "according",
    "after",
    "also",
    "always",
    "answer",
    "because",
    "before",
    "between",
    "class",
    "classes",
    "classifier",
    "classifiers",
    "classification",
    "could",
    "dataset",
    "defined",
    "does",
    "each",
    "equal",
    "examples",
    "feature",
    "features",
    "following",
    "from",
    "have",
    "into",
    "learned",
    "learning",
    "matrix",
    "model",
    "must",
    "number",
    "only",
    "predict",
    "probability",
    "question",
    "result",
    "same",
    "select",
    "should",
    "statement",
    "statements",
    "than",
    "that",
    "their",
    "then",
    "there",
    "these",
    "this",
    "true",
    "value",
    "values",
    "when",
    "where",
    "which",
    "with",
    "would",
}


def page_count(file_name: str) -> int:
    return len(fitz.open(PDF_DIR / file_name))


def clean_text(text: str) -> str:
    text = text.replace("\uf0fc", "").replace("\uf00c", "").replace("\uf00d", "")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokens(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    return [word for word in words if word not in STOPWORDS]


def keywords(text: str, limit: int = 12) -> list[str]:
    counts = Counter(tokens(text))
    return [word for word, _ in counts.most_common(limit)]


def extract_slide_chunks(now: str) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    skip_prefixes = (
        "Machine Learning and Pattern Classification",
        "Johannes Kepler",
        "Institute",
        "University",
        "Prof.",
        "MLPC",
    )

    for lecture_id, _number, file_name, lecture_title in LECTURE_FILES:
        doc = fitz.open(PDF_DIR / file_name)
        for index, page in enumerate(doc, start=1):
            text = clean_text(page.get_text("text"))
            lines = [
                re.sub(r"\s+", " ", line).strip()
                for line in text.splitlines()
                if line.strip()
            ]
            title_candidates = [
                line
                for line in lines[:12]
                if not any(line.startswith(prefix) for prefix in skip_prefixes)
            ]
            title = title_candidates[-1] if title_candidates else lecture_title
            retrieval = f"{lecture_title}. {title}. {text}"
            chunks.append(
                {
                    "id": f"{lecture_id}-p{index:03d}",
                    "sourceId": lecture_id,
                    "lectureId": lecture_id,
                    "page": index,
                    "title": title,
                    "text": text,
                    "keywords": keywords(retrieval),
                    "retrievalText": retrieval,
                }
            )

    return {"version": "1.0.0", "generatedAt": now, "chunks": chunks}


def sources() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source_id, number, file_name, title in LECTURE_FILES:
        result.append(
            {
                "id": source_id,
                "kind": "lecture_slides",
                "title": title,
                "fileName": file_name,
                "pageCount": page_count(file_name),
                "lectureNumber": number,
            }
        )
    for source_id, file_name, year, title in EXAM_FILES:
        row = {
            "id": source_id,
            "kind": "past_exam",
            "title": title,
            "fileName": file_name,
            "pageCount": page_count(file_name),
        }
        if year:
            row["year"] = year
        result.append(row)
    for source_id, file_name, asset_name, page_number, title, duplicate_of in IMAGE_FILES:
        row = {
            "id": source_id,
            "kind": "exam_image",
            "title": title,
            "fileName": f"new_img/{file_name}",
            "assetPath": f"/sources/new_img/{asset_name}",
            "pageCount": 1,
            "year": 2026,
            "pageNumber": page_number,
            "sourceQuality": "alternate_capture" if duplicate_of else "primary_capture",
        }
        if duplicate_of:
            row["duplicateOf"] = duplicate_of
            row["note"] = "Alternate photo of the same printed page; questions are linked to the clearer primary capture."
        result.append(row)
    return result


def copy_image_assets() -> None:
    target_dir = APP_DIR / "public" / "sources" / "new_img"
    target_dir.mkdir(parents=True, exist_ok=True)
    for _source_id, file_name, asset_name, _page_number, _title, _duplicate_of in IMAGE_FILES:
        shutil.copy2(PDF_DIR / "new_img" / file_name, target_dir / asset_name)


def choice_true_false() -> list[dict[str, str]]:
    return [{"id": "true", "text": "True"}, {"id": "false", "text": "False"}]


def lecture_ids_for(topic_ids: list[str]) -> list[str]:
    seen: list[str] = []
    for topic_id in topic_ids:
        for lecture_id in TOPIC_BY_ID[topic_id]["lectureIds"]:
            if lecture_id not in seen:
                seen.append(lecture_id)
    return seen


def base_question(
    *,
    qid: str,
    origin: str,
    source_id: str,
    page: int | None,
    question_number: str | None,
    topic_ids: list[str],
    difficulty: str,
    cognitive_level: str,
    interaction_type: str,
    stem: str,
    explanation: str,
    tags: list[str],
    answer_source: str,
    confidence: float,
    group_id: str | None = None,
    requires_visual: bool = False,
    figure_description: str | None = None,
) -> dict[str, Any]:
    source_ref: dict[str, Any] = {"sourceId": source_id}
    if page is not None and page > 0:
        source_ref["pages"] = [page]
    if question_number is not None:
        source_ref["questionNumber"] = question_number
    question = {
        "id": qid,
        "origin": origin,
        "sourceRefs": [source_ref],
        "topicIds": topic_ids,
        "lectureIds": lecture_ids_for(topic_ids),
        "difficulty": difficulty,
        "cognitiveLevel": cognitive_level,
        "interactionType": interaction_type,
        "stem": clean_text(stem),
        "answerSource": answer_source,
        "confidence": confidence,
        "explanation": clean_text(explanation),
        "tags": tags,
        "retrievalText": "",
    }
    if group_id:
        question["groupId"] = group_id
    if requires_visual:
        question["requiresVisual"] = True
    if figure_description:
        question["figureDescription"] = figure_description
    return question


QUESTIONS: list[dict[str, Any]] = []


def add_tf(
    qid: str,
    source_id: str,
    page: int,
    qn: str,
    topic_ids: list[str],
    stem: str,
    correct: bool,
    explanation: str,
    tags: list[str],
    *,
    origin: str = "real_exam",
    answer_source: str = "explicit_pdf",
    confidence: float = 0.98,
    difficulty: str = "medium",
    cognitive_level: str = "conceptual",
    group_id: str | None = None,
    requires_visual: bool = False,
    figure_description: str | None = None,
) -> None:
    q = base_question(
        qid=qid,
        origin=origin,
        source_id=source_id,
        page=page,
        question_number=qn,
        topic_ids=topic_ids,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
        interaction_type="true_false",
        stem=stem,
        explanation=explanation,
        tags=tags,
        answer_source=answer_source,
        confidence=confidence,
        group_id=group_id,
        requires_visual=requires_visual,
        figure_description=figure_description,
    )
    q["choices"] = choice_true_false()
    q["correctChoiceIds"] = ["true" if correct else "false"]
    q["correctAnswerText"] = "True" if correct else "False"
    QUESTIONS.append(q)


def add_single(
    qid: str,
    source_id: str,
    page: int,
    qn: str,
    topic_ids: list[str],
    stem: str,
    choices: list[str],
    correct_index: int,
    explanation: str,
    tags: list[str],
    *,
    origin: str = "real_exam",
    answer_source: str = "explicit_pdf",
    confidence: float = 0.98,
    difficulty: str = "medium",
    cognitive_level: str = "conceptual",
    group_id: str | None = None,
    requires_visual: bool = False,
    figure_description: str | None = None,
) -> None:
    q = base_question(
        qid=qid,
        origin=origin,
        source_id=source_id,
        page=page,
        question_number=qn,
        topic_ids=topic_ids,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
        interaction_type="single_choice",
        stem=stem,
        explanation=explanation,
        tags=tags,
        answer_source=answer_source,
        confidence=confidence,
        group_id=group_id,
        requires_visual=requires_visual,
        figure_description=figure_description,
    )
    q["choices"] = [{"id": f"c{i + 1}", "text": text} for i, text in enumerate(choices)]
    q["correctChoiceIds"] = [f"c{correct_index + 1}"]
    q["correctAnswerText"] = choices[correct_index]
    QUESTIONS.append(q)


def add_multi(
    qid: str,
    source_id: str,
    page: int,
    qn: str,
    topic_ids: list[str],
    stem: str,
    choices: list[str],
    correct_indices: list[int],
    explanation: str,
    tags: list[str],
    *,
    origin: str = "real_exam",
    answer_source: str = "explicit_pdf",
    confidence: float = 0.98,
    difficulty: str = "medium",
    cognitive_level: str = "comparison",
    group_id: str | None = None,
) -> None:
    q = base_question(
        qid=qid,
        origin=origin,
        source_id=source_id,
        page=page,
        question_number=qn,
        topic_ids=topic_ids,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
        interaction_type="multi_select",
        stem=stem,
        explanation=explanation,
        tags=tags,
        answer_source=answer_source,
        confidence=confidence,
        group_id=group_id,
    )
    q["choices"] = [{"id": f"c{i + 1}", "text": text} for i, text in enumerate(choices)]
    q["correctChoiceIds"] = [f"c{i + 1}" for i in correct_indices]
    q["correctAnswerText"] = "; ".join(choices[i] for i in correct_indices)
    QUESTIONS.append(q)


def add_numeric(
    qid: str,
    source_id: str,
    page: int,
    qn: str,
    topic_ids: list[str],
    stem: str,
    answer: str,
    explanation: str,
    tags: list[str],
    *,
    origin: str = "real_exam",
    answer_source: str = "explicit_pdf",
    confidence: float = 0.98,
    difficulty: str = "medium",
    cognitive_level: str = "calculation",
    group_id: str | None = None,
) -> None:
    q = base_question(
        qid=qid,
        origin=origin,
        source_id=source_id,
        page=page,
        question_number=qn,
        topic_ids=topic_ids,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
        interaction_type="numeric",
        stem=stem,
        explanation=explanation,
        tags=tags,
        answer_source=answer_source,
        confidence=confidence,
        group_id=group_id,
    )
    q["correctAnswerText"] = answer
    q["acceptedAnswers"] = [answer]
    QUESTIONS.append(q)


def add_short(
    qid: str,
    source_id: str,
    page: int,
    qn: str,
    topic_ids: list[str],
    stem: str,
    answer: str,
    explanation: str,
    tags: list[str],
    *,
    origin: str = "real_exam",
    answer_source: str = "inferred_from_slides",
    confidence: float = 0.9,
    difficulty: str = "medium",
    cognitive_level: str = "conceptual",
    group_id: str | None = None,
) -> None:
    q = base_question(
        qid=qid,
        origin=origin,
        source_id=source_id,
        page=page,
        question_number=qn,
        topic_ids=topic_ids,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
        interaction_type="short_answer",
        stem=stem,
        explanation=explanation,
        tags=tags,
        answer_source=answer_source,
        confidence=confidence,
        group_id=group_id,
    )
    q["correctAnswerText"] = clean_text(answer)
    q["acceptedAnswers"] = [clean_text(answer)]
    QUESTIONS.append(q)


def build_real_exam_questions() -> None:
    bayes_fish = (
        "Consider Bayes' Rule for classification, P(ω_i | x) = p(x | ω_i)P(ω_i)/p(x). "
        "Assume a classification problem with 5 fish classes, a 100-dimensional real-valued feature space, "
        "and a training set D of 5000 examples. Which statement is correct?"
    )
    add_tf("real-retake1-q001", "exam-retake-1", 1, "1", ["bayesian-classification"], f"{bayes_fish}\nFor any fish x in D, p(x) <= 1/5000.", False, "p(x) is the evidence or density/mass assigned to a feature vector, not a uniform count over training examples.", ["bayes-rule", "evidence"], group_id="retake1-bayes-fish")
    add_tf("real-retake1-q002", "exam-retake-1", 1, "2", ["bayesian-classification"], f"{bayes_fish}\nFor any fish x in D, p(x) is a vector with 100 values.", False, "The feature vector x has 100 components, but p(x) is one scalar density or probability value.", ["bayes-rule", "feature-space"], group_id="retake1-bayes-fish")
    add_tf("real-retake1-q003", "exam-retake-1", 2, "3", ["bayesian-classification"], f"{bayes_fish}\nFor any x, sum_i p(x | ω_i) = 1.0.", False, "Class-conditional likelihoods are densities over x for each fixed class; they do not have to sum to one across classes.", ["likelihood", "density"], group_id="retake1-bayes-fish")
    add_tf("real-retake1-q004", "exam-retake-1", 2, "4", ["bayesian-classification"], f"{bayes_fish}\nP(ω_1 | x) is a vector with 5 entries.", False, "P(ω_1 | x) is the scalar posterior probability for one class; the full posterior over all five classes would have five entries.", ["posterior"], group_id="retake1-bayes-fish")
    min_risk_context = (
        "Consider the 5 x 5 zero-one loss function λ for the above classification problem, "
        "a specific set of prior and class-conditional distributions learned from some training set, "
        "and a Bayesian minimum-risk classifier."
    )
    add_tf("real-retake1-q005", "exam-retake-1", 2, "5", ["bayesian-classification", "classifier-evaluation"], f"{min_risk_context}\nWhen tested on a specific test set T, the minimum-risk classifier will end up in exactly the same position in ROC space as a MAP classifier.", True, "With zero-one loss, minimum-risk classification is equivalent to MAP classification, so the predictions and ROC point are identical.", ["minimum-risk", "map", "roc"], group_id="retake1-zero-one-loss")
    add_tf("real-retake1-q006", "exam-retake-1", 3, "6", ["bayesian-classification"], f"{min_risk_context}\nsum_i sum_j λ_ij = 1.0.", False, "A zero-one loss matrix has zero diagonal entries and one off-diagonal entries; its total is not constrained to one.", ["loss-matrix"], group_id="retake1-zero-one-loss")
    add_tf("real-retake1-q007", "exam-retake-1", 3, "7", ["bayesian-classification"], f"{min_risk_context}\nIf we multiply all values in λ by 5, the result will be an invalid loss function.", False, "Scaling all costs by a positive constant keeps the loss function valid and preserves the risk-minimizing action.", ["loss-scaling"], group_id="retake1-zero-one-loss")

    density_context = (
        "In the context of estimating the mean θ of a normal distribution with fixed variance from 1D observations, "
        "answer the question about the likelihood plot from the lecture slides."
    )
    add_tf("real-retake2-q008", "exam-retake-2", 1, "8", ["density-estimation"], f"{density_context}\nThe likelihood function cannot be negative anywhere.", True, "A likelihood is a product of probability density values and is therefore non-negative.", ["likelihood", "mle"], group_id="retake2-density-figure")
    add_tf("real-retake2-q009", "exam-retake-2", 1, "9", ["density-estimation"], f"{density_context}\nThe y values in the lower plot cannot be probabilities, because they are negative.", True, "Negative y-values cannot be probability values; the lower plot is not a probability/likelihood curve.", ["probability", "likelihood"], group_id="retake2-density-figure")
    add_single("real-retake2-q010", "exam-retake-2", 2, "10", ["density-estimation"], f"{density_context}\nIn the figure, the likelihood function is the plot ...", ["at the top", "at the bottom", "at the middle"], 2, "The lecture figure places the likelihood as a function of θ in the middle plot.", ["likelihood", "mle"], group_id="retake2-density-figure", requires_visual=True, figure_description="Lecture figure with three plots for observations, likelihood over θ, and another curve.")
    add_tf("real-retake2-q011", "exam-retake-2", 2, "11", ["density-estimation"], f"{density_context}\nThe likelihood function is itself a normal distribution.", False, "As a function of the parameter θ, the likelihood can be proportional to a Gaussian in simple cases, but it is not itself the data distribution.", ["likelihood", "normal-distribution"], group_id="retake2-density-figure")
    add_tf("real-retake2-q012", "exam-retake-2", 2, "12", ["density-estimation"], f"{density_context}\nθ-hat is the maximum probability of the dataset.", False, "θ-hat is the parameter value that maximizes the likelihood, not the value of the maximum likelihood itself.", ["mle", "parameter"], group_id="retake2-density-figure")
    add_tf("real-retake2-q013", "exam-retake-2", 2, "13", ["density-estimation"], f"{density_context}\nWe need to plot the likelihood function in order to find the maximum.", False, "The maximum can be found analytically or numerically; plotting is only a visualization.", ["mle"], group_id="retake2-density-figure")

    knn_context = (
        "Consider a k-nearest-neighbour classifier in a d-dimensional numeric feature space, "
        "with training set D containing N > 0 instances of two classes and Euclidean distance. If k = N, then:"
    )
    add_tf("real-retake3-q014", "exam-retake-3", 1, "14", ["nearest-neighbour"], f"{knn_context}\nThe classifier will maximally overfit on the training data.", False, "Using all training examples produces a very high-bias majority-vote classifier, not a maximally overfit nearest-neighbour classifier.", ["knn", "bias-variance"], group_id="retake3-knn-k-equals-n")
    add_tf("real-retake3-q015", "exam-retake-3", 1, "15", ["nearest-neighbour"], f"{knn_context}\nThe resulting classifier will have an expected accuracy of 1/N.", False, "Accuracy depends on the class distribution, not simply the reciprocal of the training-set size.", ["knn", "accuracy"], group_id="retake3-knn-k-equals-n")
    add_tf("real-retake3-q016", "exam-retake-3", 1, "16", ["nearest-neighbour"], f"{knn_context}\nEach example from the training set will be classified into the correct class.", False, "With k = N, each point is classified by the global majority vote, so minority-class training examples are misclassified.", ["knn", "resubstitution"], group_id="retake3-knn-k-equals-n")
    add_tf("real-retake3-q017", "exam-retake-3", 2, "17", ["nearest-neighbour"], f"{knn_context}\nThe resubstitution estimate on D will be 1.0.", False, "The training-set accuracy is not necessarily perfect when all examples vote for each prediction.", ["knn", "resubstitution"], group_id="retake3-knn-k-equals-n")
    add_tf("real-retake3-q018", "exam-retake-3", 2, "18", ["nearest-neighbour"], f"{knn_context}\nAll test examples will be classified into the same class.", True, "Every test point uses all N training examples as neighbours, so the prediction is always the training-set majority class.", ["knn", "majority-class"], group_id="retake3-knn-k-equals-n")

    tree_context = (
        "A decision tree learner randomly selects one discrete feature from F, builds a one-level tree by splitting on it, "
        "and labels each resulting leaf with the majority class in that node. Which statement is true?"
    )
    add_tf("real-retake4-q019", "exam-retake-4", 1, "19", ["decision-trees", "common-classifiers"], f"{tree_context}\nIt makes no sense to combine several such trees into a Random Forest, because the trees rely on incompatible features.", False, "Voting over diverse weak trees can still improve performance; incompatible feature choices are a source of diversity, not invalidity.", ["random-forest", "ensemble"], group_id="retake4-trees-forests")
    add_tf("real-retake4-q020", "exam-retake-4", 1, "20", ["decision-trees"], f"{tree_context}\nThe chosen feature split might have an information gain of zero.", True, "A random feature can be unrelated to the class labels, producing no entropy reduction.", ["information-gain"], group_id="retake4-trees-forests")
    add_tf("real-retake4-q021", "exam-retake-4", 1, "21", ["decision-trees"], f"{tree_context}\nAny such decision tree will have an accuracy on D that is higher than the default accuracy.", False, "A one-level split can fail to improve over predicting the majority class everywhere.", ["default-classifier", "accuracy"], group_id="retake4-trees-forests")
    add_tf("real-retake4-q022", "exam-retake-4", 2, "22", ["decision-trees"], f"{tree_context}\nAny such decision tree will have exactly the default accuracy on D.", False, "Some splits improve on the default classifier, while others may not.", ["default-classifier", "accuracy"], group_id="retake4-trees-forests")
    add_tf("real-retake4-q023", "exam-retake-4", 2, "23", ["decision-trees"], f"{tree_context}\nThe resulting structure is not a decision tree.", False, "A root split with majority-class leaves is still a valid decision tree.", ["decision-tree"], group_id="retake4-trees-forests")

    visual_dataset_context = (
        "Consider the two-class 2D dataset from the lecture slides, with classes indicated by filled vs empty dots. "
        "Which statement is correct?"
    )
    add_tf("real-retake5-q024", "exam-retake-5", 1, "24", ["common-classifiers"], f"{visual_dataset_context}\nAn SVM with a quadratic kernel can achieve an error of zero on this dataset.", True, "The quadratic feature mapping can make the dataset linearly separable in the transformed space.", ["svm", "kernel"], group_id="retake5-various-classifiers", requires_visual=True, figure_description="Two-class 2D dot dataset from lecture slides.")
    add_tf("real-retake5-q025", "exam-retake-5", 2, "25", ["decision-trees", "common-classifiers"], f"{visual_dataset_context}\nIf we map this dataset into a new 2D feature space defined by x1^2 and x2^2, ID3 can separate the two classes with a two-level decision tree.", False, "The stated two-dimensional squared mapping is not sufficient for the claimed two-level ID3 separation.", ["feature-construction", "id3"], group_id="retake5-various-classifiers", requires_visual=True, figure_description="Two-class 2D dot dataset from lecture slides.")
    add_tf("real-retake5-q026", "exam-retake-5", 2, "26", ["decision-trees"], f"{visual_dataset_context}\nA decision tree learned by ID3 would have to have infinite depth to achieve zero error on this dataset.", False, "Decision trees can create finite axis-aligned partitions for a finite dataset.", ["id3", "tree-depth"], group_id="retake5-various-classifiers", requires_visual=True, figure_description="Two-class 2D dot dataset from lecture slides.")
    add_tf("real-retake5-q027", "exam-retake-5", 2, "27", ["nearest-neighbour"], f"{visual_dataset_context}\nA nearest-neighbour classifier can only perform well on this dataset if it uses circular, not rectangular, neighbourhoods.", False, "Nearest-neighbour performance depends on the distance/neighbourhood definition, but rectangular neighbourhoods are not inherently incapable.", ["knn", "distance"], group_id="retake5-various-classifiers", requires_visual=True, figure_description="Two-class 2D dot dataset from lecture slides.")
    add_tf("real-retake5-q028", "exam-retake-5", 2, "28", ["common-classifiers"], f"{visual_dataset_context}\nThe max-margin hyperplane that an SVM with quadratic kernel would learn remains the same regardless of which class is labelled +1 and which -1.", True, "Swapping class labels flips the sign convention but not the geometric separating hyperplane.", ["svm", "max-margin"], group_id="retake5-various-classifiers", requires_visual=True, figure_description="Two-class 2D dot dataset from lecture slides.")
    add_tf("real-retake5-q029", "exam-retake-5", 3, "29", ["nearest-neighbour"], f"{visual_dataset_context}\nThere exists no k for which k-NN would predict class 'white' for point (0,0).", False, "The prediction at a point can change with k depending on the class composition among the k nearest examples.", ["knn"], group_id="retake5-various-classifiers", requires_visual=True, figure_description="Two-class 2D dot dataset from lecture slides.")

    nn_threshold_context = (
        "Consider a feed-forward neural network for the above 2D dataset: two inputs x1,x2, one tanh hidden unit, "
        "one identity output unit, class targets 0/1, squared error loss, and threshold τ for classifying the output."
    )
    add_tf("real-retake5-q030", "exam-retake-5", 3, "30", ["neural-networks", "classifier-evaluation"], f"{nn_threshold_context}\nIncreasing τ cannot increase the recall of the model on class 0 on the training set.", False, "Raising the threshold makes class 0 easier to predict, so recall for class 0 can increase.", ["threshold", "recall"], group_id="retake5-nn-threshold")
    add_tf("real-retake5-q031", "exam-retake-5", 3, "31", ["neural-networks"], f"{nn_threshold_context}\nThe single hidden unit is unnecessary and makes no difference; a network without hidden unit could learn the same function.", False, "A tanh hidden unit allows nonlinear transformations that a purely linear input-output model cannot express.", ["hidden-unit", "nonlinearity"], group_id="retake5-nn-threshold")
    add_tf("real-retake5-q032", "exam-retake-5", 4, "32", ["neural-networks"], f"{nn_threshold_context}\nIf τ is set to 0.0 or 1.0, all possible inputs will always be classified into the same class by any model trained this way.", False, "The identity output is not restricted to [0,1], so thresholding at 0 or 1 need not make predictions constant.", ["threshold", "identity-output"], group_id="retake5-nn-threshold")
    add_tf("real-retake5-q033", "exam-retake-5", 4, "33", ["neural-networks"], f"{nn_threshold_context}\nThe output predicted by the output unit is a probability.", False, "An identity output trained with squared error is a numeric score, not automatically a calibrated probability.", ["identity-output", "probability"], group_id="retake5-nn-threshold")
    add_tf("real-retake5-q034", "exam-retake-5", 4, "34", ["neural-networks", "classifier-evaluation"], f"{nn_threshold_context}\nBy choosing different values for τ for a fixed learned model, we can obtain classifiers with different positions in ROC space.", True, "Changing the threshold trades off true positives and false positives, moving the operating point in ROC space.", ["threshold", "roc"], group_id="retake5-nn-threshold")
    add_tf("real-retake5-q035", "exam-retake-5", 4, "35", ["neural-networks"], f"{nn_threshold_context}\nThe output predicted by the output unit will always be in the interval [0,1].", False, "The output unit is identity/linear, so its output is unbounded unless constrained by architecture or training.", ["identity-output"], group_id="retake5-nn-threshold")

    hmm_context = (
        "Model a neighbour's football-watching noises as a Hidden Markov Model with states S = {game, nogame} "
        "and observations O = {none, cheer, shout, curse, snore}."
    )
    add_numeric("real-retake6-q036", "exam-retake-6", 1, "36", ["markov-models-hmm"], f"{hmm_context}\nWhat is the dimension of transition matrix A (rows x columns)?", "2 x 2", "The transition matrix has one row and one column per hidden state.", ["hmm", "transition-matrix"], group_id="retake6-hmm-dimensions")
    add_numeric("real-retake6-q037", "exam-retake-6", 1, "37", ["markov-models-hmm"], f"{hmm_context}\nWhat is the dimension of observation matrix B (rows x columns) as defined in the lecture slides?", "5 x 2", "In the lecture convention used by this exam, B has one row per observation symbol and one column per hidden state.", ["hmm", "observation-matrix"], answer_source="inferred_from_slides", confidence=0.88, group_id="retake6-hmm-dimensions")
    add_numeric("real-retake6-q038", "exam-retake-6", 1, "38", ["markov-models-hmm"], f"{hmm_context}\nWhat is the dimension of Π?", "2", "The initial state distribution has one entry per hidden state.", ["hmm", "prior"], answer_source="inferred_from_slides", confidence=0.92, group_id="retake6-hmm-dimensions")
    add_tf("real-retake6-q039", "exam-retake-6", 2, "39", ["markov-models-hmm"], f"{hmm_context}\nWith only two states, matrix A must be symmetric.", False, "A transition matrix must have normalized transition probabilities, but symmetry is not required.", ["hmm", "transition-matrix"], group_id="retake6-hmm-statements")
    add_tf("real-retake6-q040", "exam-retake-6", 2, "40", ["markov-models-hmm"], f"{hmm_context}\nIf your neighbour never snores, one row of matrix B will be all zeros.", True, "Under the lecture convention where rows correspond to observation symbols, an impossible observation has a zero row.", ["hmm", "observation-matrix"], group_id="retake6-hmm-statements")
    add_tf("real-retake6-q041", "exam-retake-6", 2, "41", ["markov-models-hmm"], f"{hmm_context}\nMatrix B represents a Markov process.", False, "B is an observation/emission model, while the Markov process over states is represented by A.", ["hmm", "emission"], group_id="retake6-hmm-statements")
    add_tf("real-retake6-q042", "exam-retake-6", 2, "42", ["markov-models-hmm"], f"{hmm_context}\nThe diagonal of A must sum to 1.0.", False, "Rows or columns, depending on convention, must normalize transition probabilities; the diagonal has no such constraint.", ["hmm", "transition-matrix"], group_id="retake6-hmm-statements")
    add_single("real-retake6-q043", "exam-retake-6", 3, "43", ["markov-models-hmm"], f"{hmm_context}\nWe can estimate the expected duration of a game, i.e. the number of consecutive time points t with q_t = game, from:", ["matrix A of the model", "vector Π of the model", "not at all", "matrix B of the model"], 0, "Expected run length in a state depends on the self-transition probability in A.", ["hmm", "duration"], group_id="retake6-hmm-statements")

    build_ss20_questions()
    build_ss22_questions()
    build_2023_questions()


def build_ss20_questions() -> None:
    source = "exam-ss20"
    add_short("real-ss20-q001", source, 1, "1", ["bayesian-classification"], "Consider Bayes' Rule for classification in a binary task. Why can we say that p(x) is irrelevant for determining the MAP class?", "Because p(x) is the same positive normalizing denominator for every class, so it does not change which posterior is largest.", "MAP only needs the argmax over classes; constants independent of the class can be omitted.", ["map", "evidence"], confidence=0.94)
    add_short("real-ss20-q002", source, 2, "2", ["bayesian-classification"], "What will happen if the prior P(Ω) is very uneven, with a high value for one class and a low value for another?", "The classifier is biased toward the high-prior class; if the prior is strong enough, it can dominate the likelihood.", "Bayesian classification multiplies likelihood by prior, so unequal priors shift decision boundaries.", ["prior", "decision-boundary"], confidence=0.92)
    add_short("real-ss20-q003", source, 2, "3", ["bayesian-classification", "classifier-evaluation"], "One class ω1 is so critical that the classifier must not miss any instance of ω1. How can we obtain such a classifier?", "Choose a cost/threshold/operating point that makes false negatives for ω1 prohibitively expensive, giving recall 1.0 for ω1.", "Minimum-risk classification can encode asymmetric error costs; ROC thresholding can also choose an operating point with full recall.", ["minimum-risk", "recall", "cost"], confidence=0.88)
    add_tf("real-ss20-q004", source, 2, "4", ["bayesian-classification"], "Two zero-one loss matrices λ1 = [[0,1],[1,0]] and λ2 = [[0,10],[10,0]] lead to different values of the Bayes risk.", True, "Scaling all off-diagonal costs by 10 scales the numerical risk values.", ["loss-matrix", "bayes-risk"])
    add_tf("real-ss20-q005", source, 3, "5", ["bayesian-classification"], "The two loss matrices λ1 = [[0,1],[1,0]] and λ2 = [[0,10],[10,0]] lead a Bayesian classifier to make different predictions.", False, "Multiplying all costs by the same positive constant does not change the risk-minimizing class.", ["loss-scaling"])
    add_tf("real-ss20-q006", source, 3, "6", ["nearest-neighbour"], "For k = 1, the k-NN classifier cannot overfit the training data.", False, "1-NN can fit training examples very closely and is a classic high-variance setting.", ["knn", "overfitting"])
    add_tf("real-ss20-q007", source, 3, "7", ["nearest-neighbour"], "Increasing k will increase the danger of overfitting in k-NN.", False, "Increasing k usually smooths the decision boundary, increasing bias and reducing variance.", ["knn", "bias-variance"])
    add_tf("real-ss20-q008", source, 3, "8", ["nearest-neighbour"], "Setting k to a high value will lower the bias of the k-NN classifier.", False, "A high k makes the classifier more rigid and therefore higher-bias.", ["knn", "bias"])
    add_tf("real-ss20-q009", source, 4, "9", ["nearest-neighbour"], "If we add additional redundant features to the data, such as identical copies of a feature, the predictions of k-NN can change.", True, "Duplicating a feature changes Euclidean distances by giving that feature extra weight.", ["knn", "feature-scaling"])
    add_tf("real-ss20-q010", source, 4, "10", ["nearest-neighbour"], "If we change the scale of one feature, for example multiplying all values by 1000, the predictions of k-NN can change.", True, "Euclidean distance is scale-sensitive, so one feature can dominate after rescaling.", ["knn", "normalization"])
    add_numeric("real-ss20-q011", source, 4, "11", ["decision-trees"], "For the one-dimensional training sequence + + - + + + - + - - -, what is the minimum depth of a binary-split decision tree on X that has zero training error?", "3", "A finite set of alternating label runs can be separated by interval thresholds; this sequence needs depth 3 for zero error.", ["decision-tree", "numeric-split"], difficulty="hard")
    add_short("real-ss20-q012", source, 5, "12", ["decision-trees"], "Why can the same numeric feature be used several times along a path in a decision tree, but a symbolic feature cannot?", "A numeric split only restricts an interval, so another threshold on the same feature can further refine it. A symbolic split fixes the feature value on each branch, so repeating it adds no information.", "Numeric features can be thresholded repeatedly; symbolic branch tests exhaust the value choice.", ["decision-tree", "numeric-feature"], confidence=0.92)
    add_tf("real-ss20-q013", source, 5, "13", ["decision-trees", "classifier-evaluation"], "The ID3 stop criterion 'if a node contains <= k examples, turn it into a majority leaf' can help against overfitting.", True, "Stopping small leaves reduces model complexity and can prevent fitting noise.", ["id3", "overfitting", "pruning"])
    add_tf("real-ss20-q014", source, 5, "14", ["decision-trees"], "If k is made larger for this stop criterion, the error on the training data cannot go down.", True, "A larger stopping threshold restricts the tree more, so it cannot fit training data better than a less restricted tree.", ["id3", "bias-variance"])
    add_tf("real-ss20-q015", source, 6, "15", ["decision-trees", "classifier-evaluation"], "If k is made larger for this stop criterion, the error on independent test data cannot go up.", False, "More regularization can help or hurt test error depending on whether it removes noise or useful structure.", ["model-selection", "test-error"])
    add_tf("real-ss20-q016", source, 6, "16", ["decision-trees", "classifier-evaluation"], "If k is made larger for this stop criterion, the error on independent test data cannot go down.", False, "Regularization can reduce overfitting and therefore reduce test error.", ["model-selection", "test-error"])
    add_tf("real-ss20-q017", source, 6, "17", ["classifier-evaluation"], "A classifier cannot have both recall = 1.0 and precision = 1.0 on class ω1.", False, "Perfect classification of class ω1 gives both recall and precision equal to 1.", ["precision", "recall"])
    add_tf("real-ss20-q018", source, 6, "18", ["classifier-evaluation"], "A classifier cannot have both recall = 1.0 and precision = 0.0 on class ω1.", True, "If recall is 1, there is at least one true positive for class ω1; precision cannot be zero when true positives exist among predicted positives.", ["precision", "recall"])
    add_tf("real-ss20-q019", source, 7, "19", ["classifier-evaluation"], "If classifier A has higher recall on class ω1 than classifier B on a dataset, A must have lower precision on ω1 than B.", False, "Recall and precision trade off often, but no strict implication holds for arbitrary classifiers.", ["precision", "recall"])
    add_tf("real-ss20-q020", source, 7, "20", ["classifier-evaluation"], "No line segment of the ROC convex hull can be strictly horizontal.", False, "A horizontal ROC hull segment can occur when TPR is constant while FPR changes.", ["roc", "convex-hull"])
    add_tf("real-ss20-q021", source, 7, "21", ["classifier-evaluation"], "Classifiers in different places on the ROC convex hull can have the same classification accuracy.", True, "Accuracy depends on class distribution and both TPR/FPR; different ROC points can yield the same accuracy.", ["roc", "accuracy"])
    add_tf("real-ss20-q022", source, 7, "22", ["classifier-evaluation"], "If two classifiers have the same accuracy, then their TPR difference must exactly equal their FPR difference.", False, "The accuracy equation also depends on class priors, so the simple equality is not generally required.", ["roc", "accuracy"])
    add_single("real-ss20-q023", source, 8, "23", ["bayesian-classification", "classifier-evaluation"], "If we multiply every entry in the cost matrix by 2.0, what happens to the optimal classifier?", ["it moves to ROC heaven", "it moves to ROC hell", "it stays where it is", "it becomes invalid"], 2, "Positive scaling of all costs preserves the argmin of expected risk.", ["cost-matrix", "roc"])
    add_tf("real-ss20-q024", source, 9, "25", ["neural-networks"], "For a regression problem, root mean squared error is a meaningful loss function.", True, "RMSE is non-negative and penalizes prediction errors.", ["loss", "regression"])
    add_tf("real-ss20-q025", source, 9, "26", ["neural-networks"], "For a regression problem, the plain sum of signed residuals is a meaningful loss function.", False, "Positive and negative errors can cancel, hiding large mistakes.", ["loss", "regression"])
    add_tf("real-ss20-q026", source, 9, "27", ["neural-networks"], "For a regression problem, the maximum squared error over the dataset is a meaningful loss function.", True, "It is a valid objective, although it focuses only on the worst case.", ["loss", "regression"])
    add_short("real-ss20-q027", source, 10, "28", ["neural-networks"], "Which of these loss functions could be problematic for backpropagation, and why?", "The max-error loss can be problematic because the max operation is non-smooth and routes gradient through only the current worst example; signed residual sums are not meaningful because errors cancel.", "Backpropagation prefers differentiable objectives that provide useful gradients across examples.", ["backpropagation", "loss"], confidence=0.86)
    add_single("real-ss20-q028", source, 10, "29", ["neural-networks"], "When you add an additional hidden layer to a feed-forward network, how does that affect the bias of the network model?", ["it increases", "it decreases", "it is unchanged", "it becomes undefined"], 1, "A deeper model is more expressive, so its bias generally decreases.", ["bias-variance", "hidden-layer"])
    add_single("real-ss20-q029", source, 10, "30", ["neural-networks"], "When you add an additional hidden layer to a feed-forward network, how does that affect the variance of the network model?", ["it increases", "it decreases", "it is unchanged", "it becomes zero"], 0, "A more flexible model is more sensitive to training data variation, so variance generally increases.", ["bias-variance", "hidden-layer"])
    add_tf("real-ss20-q030", source, 11, "31", ["deep-learning"], "Deep learning researches the simulation of biological neurons with computers.", False, "Deep learning mainly studies representation learning with many-layer neural networks, not faithful biological neuron simulation.", ["deep-learning", "definition"])
    add_tf("real-ss20-q031", source, 11, "32", ["deep-learning"], "Artificial neural networks are mappings from tensors to other tensors.", True, "Modern neural networks transform vector, matrix, or higher-order tensor inputs into tensor outputs.", ["tensor", "neural-network"])
    add_tf("real-ss20-q032", source, 11, "33", ["deep-learning"], "The majority of parameters in a deep neural network is specified by hand.", False, "Parameters such as weights are learned from data; only architecture and hyperparameters are manually chosen.", ["parameters", "training"])
    add_short("real-ss20-q033", source, 12, "34", ["deep-learning"], "You want to train a network to play the yellow player in Connect Four. How would you represent the board state for the neural network?", "Use a fixed tensor representation of the 6x7 board, e.g. separate channels for yellow stones, red stones, and empty cells or signed values per cell.", "The input should preserve board geometry and player occupancy in a numeric tensor.", ["representation", "tensor"], confidence=0.88)
    add_short("real-ss20-q034", source, 12, "35", ["deep-learning"], "How would you represent the expected output of the Connect Four network?", "Use seven output values, one per possible slot/column, representing a move score or probability distribution over legal moves.", "The target is a move choice, so the output should align with the seven possible actions.", ["output-representation", "classification"], confidence=0.88)
    add_short("real-ss20-q035", source, 12, "36", ["deep-learning"], "What is a possible data augmentation method for recorded Connect Four expert games?", "Mirror the board horizontally and transform the target column accordingly.", "Connect Four is symmetric under left-right reflection, so mirrored states are valid additional examples.", ["data-augmentation"], confidence=0.92)
    add_single("real-ss20-q036", source, 12, "37", ["deep-learning"], "For Connect Four board-state learning, would you recommend only dense layers or also convolutional layers?", ["only dense layers", "include convolutional layers", "no hidden layers", "only recurrent layers"], 1, "Convolutions exploit local spatial patterns and translation-like structure on the board.", ["convolution", "architecture"])


def build_ss22_questions() -> None:
    source = "exam-ss22"
    strategy_context = (
        "In a two-class problem with classes ω1,ω2, consider strategies: "
        "S1 predict ω1 iff P(ω1) > P(ω2); "
        "S2 predict ω1 iff p(x|ω1) > p(x|ω2); "
        "S3 predict ω1 iff P(ω1|x) > P(ω2|x); "
        "S4 predict ω1 iff P(ω1) > 0.5; "
        "S5 predict ω1 iff p(x|ω1) > p(x); "
        "S6 predict ω1 iff P(ω1|x) > P(ω1)."
    )
    options = ["S1", "S2", "S3", "S4", "S5", "S6"]
    add_multi("real-ss22-q001", source, 1, "1", ["bayesian-classification"], f"{strategy_context}\nWhich strategies result in the baseline accuracy?", options, [0, 3], "S1 and S4 ignore x and always predict according to the prior majority class.", ["baseline", "prior"], group_id="ss22-bayes-strategies")
    add_single("real-ss22-q002", source, 2, "2", ["bayesian-classification"], f"{strategy_context}\nWhich strategy is guaranteed to have the Bayes Error?", options, 2, "S3 is MAP classification using the posterior and therefore achieves Bayes-optimal zero-one decisions.", ["map", "bayes-error"], group_id="ss22-bayes-strategies")
    add_multi("real-ss22-q003", source, 2, "3", ["bayesian-classification"], f"{strategy_context}\nWhich strategies take into account both prior and likelihood?", options, [2, 5], "Posterior-based rules combine likelihood and prior through Bayes' rule.", ["posterior", "prior", "likelihood"], group_id="ss22-bayes-strategies")
    condition_stem = f"{strategy_context}\nUnder which conditions will S2 and S3 make identical predictions? Is this statement true?"
    add_tf("real-ss22-q004", source, 3, "4", ["bayesian-classification"], f"{condition_stem}\nP(ω1) = 0.", False, "A zero prior for one class makes posterior comparison degenerate and not equivalent to likelihood-only comparison.", ["prior", "likelihood"], group_id="ss22-bayes-conditions")
    add_tf("real-ss22-q005", source, 3, "5", ["bayesian-classification"], f"{condition_stem}\nP(ω1) = P(ω2).", True, "With equal priors, MAP posterior comparison reduces to comparing the likelihoods.", ["prior", "likelihood"], group_id="ss22-bayes-conditions")
    add_tf("real-ss22-q006", source, 3, "6", ["bayesian-classification"], f"{condition_stem}\np(x|ω1) = p(x|ω2).", False, "Equal likelihoods alone do not make likelihood-only and posterior rules equivalent when priors differ.", ["likelihood", "posterior"], group_id="ss22-bayes-conditions")
    add_tf("real-ss22-q007", source, 3, "7", ["bayesian-classification"], f"{condition_stem}\nP(ω1) = 1.", False, "A certain prior for one class makes posterior decisions constant, not equivalent to likelihood-only decisions in general.", ["prior"], group_id="ss22-bayes-conditions")
    add_tf("real-ss22-q008", source, 4, "8", ["bayesian-classification"], f"{condition_stem}\nIf the two classes are equally frequent, P(ω1)=P(ω2), then S2 and S3 are equivalent.", True, "Equal priors cancel in the posterior comparison.", ["prior", "map"], group_id="ss22-bayes-conditions")
    add_tf("real-ss22-q009", source, 4, "9", ["bayesian-classification"], "If P(ω1|x) > P(ω1), then P(ω2|x) < P(ω2) in a two-class problem.", True, "The two posterior probabilities and the two priors each sum to one, so an increase for one class implies a decrease for the other.", ["posterior", "two-class"], group_id="ss22-bayes-conditions")
    add_tf("real-ss22-q010", source, 4, "10", ["bayesian-classification"], "If p(x|ω1) > p(x), then p(x|ω2) < p(x) in a two-class problem.", True, "The evidence p(x) is a prior-weighted average of the class-conditional likelihoods, so if one likelihood is above the average, the other must be below it.", ["likelihood", "evidence"], group_id="ss22-bayes-conditions")

    positive_context = "A binary classifier X is evaluated on a test set T consisting only of positive examples. The accuracy of X on T can be expected to be ..."
    add_tf("real-ss22-q011", source, 5, "11", ["classifier-evaluation"], f"{positive_context}\n... equal to the baseline accuracy on T.", False, "Baseline accuracy on an all-positive test set is 1.0, but an arbitrary classifier need not predict all positives.", ["accuracy", "baseline"], group_id="ss22-positive-only")
    add_tf("real-ss22-q012", source, 5, "12", ["classifier-evaluation"], f"{positive_context}\n... 0.0.", False, "An arbitrary classifier may correctly classify some positives, so its accuracy is not necessarily zero.", ["accuracy"], group_id="ss22-positive-only")
    add_tf("real-ss22-q013", source, 5, "13", ["classifier-evaluation"], f"{positive_context}\n... equal to its recall on T.", True, "With only positive examples, accuracy equals TP/(TP+FN), which is recall for the positive class.", ["accuracy", "recall"], group_id="ss22-positive-only")
    add_tf("real-ss22-q014", source, 6, "14", ["classifier-evaluation"], f"{positive_context}\n... equal to the accuracy on T of a classifier that always predicts the positive class.", False, "The all-positive classifier gets accuracy 1.0; arbitrary X need not.", ["accuracy", "baseline"], group_id="ss22-positive-only")
    add_tf("real-ss22-q015", source, 6, "15", ["classifier-evaluation"], f"{positive_context}\n... 1.0 (100%).", False, "Only a classifier predicting all examples as positive would reach 1.0 on this test set.", ["accuracy"], group_id="ss22-positive-only")

    rp_choices = ["lower left corner", "upper left corner", "upper right corner", "lower right corner", "possibly some other point in the space", "one of the measures is undefined"]
    add_multi("real-ss22-q016", source, 7, "16", ["classifier-evaluation"], "In recall-precision space for class p, which points correspond to an all-p classifier?", rp_choices, [2, 4], "Recall is 1; precision equals the prevalence of p, which is upper right only when all examples are p, otherwise another point with x=1.", ["precision", "recall"], group_id="ss22-rp-space")
    add_single("real-ss22-q017", source, 7, "17", ["classifier-evaluation"], "In recall-precision space for class p, which point corresponds to an all-n classifier?", rp_choices, 5, "No positive predictions are made, so precision is undefined.", ["precision", "recall"], group_id="ss22-rp-space")
    add_multi("real-ss22-q018", source, 8, "18", ["classifier-evaluation"], "In recall-precision space for class p, which point corresponds to a random 50:50 guessing classifier?", ["point (x = 1.0, y = 0.5)", "point (x = 0.5, y = 1.0)", "point (x = 0.5, y = 0.5)", "possibly some other point in the space", "one of the measures is undefined"], [2, 3], "Expected recall is 0.5, but precision depends on class distribution; it is 0.5 only for balanced classes.", ["precision", "recall"], group_id="ss22-rp-space")
    add_tf("real-ss22-q019", source, 8, "19", ["classifier-evaluation"], "A classifier that predicts between the two classes randomly will have Recall = Precision = 0.5.", False, "Recall may be 0.5 in expectation for balanced random guessing, but precision depends on the dataset's class distribution.", ["precision", "recall"])
    add_tf("real-ss22-q020", source, 8, "20", ["classifier-evaluation"], "Two classifiers with the same recall and same precision can have different accuracy on the same fixed dataset.", False, "For a fixed binary dataset, recall and precision determine TP, FP, FN and therefore TN and accuracy.", ["precision", "recall", "accuracy"])
    add_tf("real-ss22-q021", source, 9, "21", ["classifier-evaluation"], "If classifier A has higher recall than B on a fixed dataset D, it must have lower precision than B.", False, "There is no necessary monotonic tradeoff between independently chosen classifiers.", ["precision", "recall"])

    fish_context = (
        "Assume a binary classification task with classes {salmon, bass} and two discretized features Length and Lightness. "
        "Training set D: [short,dark] -> salmon; [short,light] -> salmon; [long,dark] -> bass; [long,light] -> bass."
    )
    add_numeric("real-ss22-q022", source, 10, "22", ["decision-trees"], f"{fish_context}\nCalculate the empirical entropy (log base 2) of the class distribution in D.", "1", "The class distribution is 2 salmon and 2 bass, so entropy is one bit.", ["entropy", "id3"], group_id="ss22-fish-dataset")
    add_numeric("real-ss22-q023", source, 10, "23", ["decision-trees"], f"{fish_context}\nCalculate the information gain of Length and Lightness on D.", "1", "Length perfectly separates salmon from bass, so its information gain is 1; the exam accepted 1 for the requested gains.", ["information-gain"], group_id="ss22-fish-dataset")
    add_numeric("real-ss22-q024", source, 11, "24", ["decision-trees"], f"{fish_context}\nWhat is the depth of the simplest decision tree consistent with this dataset?", "1", "A single split on Length separates the classes perfectly.", ["tree-depth"], group_id="ss22-fish-dataset")
    add_tf("real-ss22-q025", source, 11, "25", ["decision-trees"], f"{fish_context}\nOn this dataset, ID3 is guaranteed to find the simplest possible tree.", True, "The feature with perfect information gain gives a depth-1 tree.", ["id3", "information-gain"], group_id="ss22-fish-dataset")
    add_short("real-ss22-q026", source, 11, "26", ["common-classifiers"], f"{fish_context}\nSpecify the probability distributions Naive Bayes would use for classification.", "P(Class) = [salmon: 0.5, bass: 0.5]; P(Length|salmon) = [short: 1, long: 0]; P(Length|bass) = [short: 0, long: 1]; P(Lightness|salmon) = [dark: 0.5, light: 0.5]; P(Lightness|bass) = [dark: 0.5, light: 0.5].", "Naive Bayes estimates priors and feature-conditional distributions by relative frequencies within each class.", ["naive-bayes", "probability"], confidence=0.98, group_id="ss22-fish-dataset")
    add_tf("real-ss22-q027", source, 12, "27", ["decision-trees"], f"{fish_context}\nAfter adding 5 copies of [long, light] -> bass, the ID3 tree would degenerate to a root node predicting the majority class bass.", False, "Length still separates salmon from bass, so an informative split remains.", ["id3"], group_id="ss22-fish-duplicates")
    add_tf("real-ss22-q028", source, 12, "28", ["decision-trees"], f"{fish_context}\nAfter adding 5 copies of [long, light] -> bass, the bass examples from D would end up in the same leaf.", True, "Splitting on Length puts all long examples, including bass examples, in the same branch.", ["id3"], group_id="ss22-fish-duplicates")
    add_tf("real-ss22-q029", source, 12, "29", ["common-classifiers"], f"{fish_context}\nAfter adding 5 copies of [long, light] -> bass, the prior for Naive Bayes would change.", True, "The class frequencies change from balanced to bass-majority.", ["naive-bayes", "prior"], group_id="ss22-fish-duplicates")
    add_tf("real-ss22-q030", source, 12, "30", ["decision-trees"], f"{fish_context}\nAfter adding 5 copies of [long, light] -> bass, the ID3 tree would get one level deeper.", False, "The perfect Length split still gives a one-level tree.", ["id3", "tree-depth"], group_id="ss22-fish-duplicates")
    add_tf("real-ss22-q031", source, 13, "31", ["decision-trees"], f"{fish_context}\nAfter adding 5 copies of [long, light] -> bass, the ID3 tree would stay exactly the same.", True, "The same root split on Length remains optimal and sufficient.", ["id3"], group_id="ss22-fish-duplicates")
    add_tf("real-ss22-q032", source, 13, "32", ["common-classifiers"], f"{fish_context}\nEncode short=0, long=1, dark=0, light=1, salmon=0, bass=1. Are the classes linearly separable?", True, "The class label is determined by Length, so a linear boundary separates x1=0 from x1=1.", ["linear-separability"], group_id="ss22-fish-linear")
    add_numeric("real-ss22-q033", source, 13, "33", ["neural-networks"], f"{fish_context}\nHow many units are needed to express a classifier without hidden layer that predicts P(bass|Features), including the bias unit?", "4", "Two input units, one bias unit, and one output unit give four units total.", ["feed-forward-network", "bias-unit"], group_id="ss22-fish-linear")
    add_single("real-ss22-q034", source, 14, "34", ["common-classifiers"], f"{fish_context}\nWhich examples are exactly on the margin (support vectors) in a maximum-margin linear classifier?", ["([short,dark], salmon), ([short,light], salmon)", "([short,dark], salmon), ([long,light], bass)", "([short,dark], salmon)", "all four", "none of them", "a maximum margin linear classifier does not exist"], 3, "The symmetric four-corner setup makes all four examples lie on the margin.", ["svm", "support-vector"], group_id="ss22-fish-linear")
    add_tf("real-ss22-q035", source, 14, "35", ["nearest-neighbour"], f"{fish_context}\nAfter adding four copies of [long, light] -> bass, the decision boundary for k-NN with k=4 would look different than with k=1.", True, "k=4 voting is affected by duplicate neighbours and differs from nearest-neighbour voting.", ["knn"], group_id="ss22-fish-knn")
    add_tf("real-ss22-q036", source, 14, "36", ["neural-networks"], f"{fish_context}\nAfter adding four copies of [long, light] -> bass, a feed-forward neural network would require twice as many input units.", False, "Duplicating training examples changes the dataset frequency, not the feature dimensionality.", ["feed-forward-network"], group_id="ss22-fish-knn")
    add_tf("real-ss22-q037", source, 15, "37", ["nearest-neighbour"], f"{fish_context}\nAfter adding four copies of [long, light] -> bass, a k-NN classifier with k=1 would change its prediction behaviour.", False, "Nearest-neighbour predictions are determined by closest distinct positions; duplicates do not change 1-NN boundaries.", ["knn"], group_id="ss22-fish-knn")
    add_tf("real-ss22-q038", source, 15, "38", ["nearest-neighbour"], f"{fish_context}\nAfter adding four copies of [long, light] -> bass, a k-NN classifier with k=9 would always predict bass.", True, "There are nine training examples after duplication, and bass is the global majority.", ["knn", "majority-class"], group_id="ss22-fish-knn")

    add_tf("real-ss22-q043", source, 17, "43", ["neural-networks"], "In gradient descent for neural networks, a loss function can be defined over several output units.", True, "Multi-output networks use losses that aggregate errors over all output units.", ["gradient-descent", "loss"])
    add_tf("real-ss22-q044", source, 18, "44", ["neural-networks"], "In gradient descent, a gradient of zero will result in unchanged weights.", True, "The weight update is proportional to the negative gradient, so zero gradient gives no update.", ["gradient-descent"])
    add_tf("real-ss22-q045", source, 18, "45", ["neural-networks"], "A large learning rate may lead to convergence more quickly.", True, "A larger step size can accelerate convergence, although it can also overshoot.", ["learning-rate"])
    add_tf("real-ss22-q046", source, 18, "46", ["neural-networks"], "The gradient must be calculated for each weight in the network.", True, "Gradient descent needs a partial derivative for every trainable parameter.", ["gradient-descent", "weights"])
    add_tf("real-ss22-q047", source, 18, "47", ["neural-networks"], "A loss function can have more than one minimum.", True, "Non-convex neural-network losses often have multiple local or global minima.", ["loss", "non-convex"])
    add_tf("real-ss22-q048", source, 19, "48", ["neural-networks"], "A small learning rate leads to more complex neural network models.", False, "The learning rate controls optimization steps, not the representational complexity of the architecture.", ["learning-rate", "complexity"])
    add_tf("real-ss22-q049", source, 19, "49", ["neural-networks"], "The gradient is a number in the range [-1, 1].", False, "Gradient components can take arbitrary real values depending on the loss landscape.", ["gradient"])
    add_tf("real-ss22-q050", source, 19, "50", ["neural-networks"], "Decreasing the number of hidden units could help prevent overfitting in a neural network.", True, "Fewer hidden units reduce model capacity.", ["overfitting", "capacity"])
    add_tf("real-ss22-q051", source, 20, "51", ["neural-networks"], "Decreasing the number of hidden layers could help prevent overfitting in a neural network.", True, "A shallower network usually has lower capacity.", ["overfitting", "capacity"])
    add_tf("real-ss22-q052", source, 20, "52", ["neural-networks"], "Reducing the learning rate could help prevent overfitting in a neural network.", False, "Learning rate mainly affects optimization; it is not a direct capacity-control method.", ["learning-rate", "overfitting"])
    add_tf("real-ss22-q053", source, 20, "53", ["neural-networks"], "Reducing the number of training iterations could help prevent overfitting in a neural network.", True, "Early stopping is a common regularization strategy.", ["early-stopping", "overfitting"])
    add_tf("real-ss22-q054", source, 20, "54", ["neural-networks"], "Limiting the size of the gradient by cropping it if too large could help prevent overfitting.", False, "Gradient clipping stabilizes optimization; it is not primarily an overfitting-avoidance strategy.", ["gradient-clipping"])
    add_tf("real-ss22-q055", source, 21, "55", ["neural-networks"], "Changing weights in the direction of the gradient, instead of the negative direction, could help prevent overfitting.", False, "Moving in the gradient direction increases the loss for minimization.", ["gradient-descent"])

    add_single("real-ss22-q056", source, 22, "56", ["unsupervised-learning"], "For k-means, what quality does Mean Quantisation Error (MQE) implicitly try to encode?", ["average size of cluster centers", "compactness of clusters", "average distance between cluster centers", "equal distribution among clusters", "number of clusters"], 1, "MQE is based on distances from examples to their assigned cluster centers.", ["k-means", "mqe"])
    add_single("real-ss22-q057", source, 23, "57", ["unsupervised-learning"], "Which common definition variants of MQE are equivalent in the sense of leading to the exact same k-means behaviour?", ["all three are equivalent", "only (2) and (3) are equivalent", "only (1) and (2) are equivalent", "none; they may all lead to different behaviour", "only (1) and (3) are equivalent"], 0, "Multiplying or averaging the same objective by constants does not change the minimizer for fixed k.", ["k-means", "mqe"])
    add_tf("real-ss22-q058", source, 23, "58", ["unsupervised-learning"], "If we multiplied the BIC score by some constant, a model-selection algorithm using this score would tend to return simpler models.", False, "Multiplying the whole score by a positive constant preserves the ordering of models.", ["bic", "model-selection"])
    add_tf("real-ss22-q059", source, 24, "59", ["unsupervised-learning"], "If we removed the fit term from BIC and left only the penalty term, the resulting measure would favor simple models without regard to fit.", False, "The referenced removed term in the exam is the penalty term; the remaining term would focus on fit.", ["bic"])
    add_tf("real-ss22-q060", source, 24, "60", ["unsupervised-learning"], "The second term of the BIC formula puts a penalty on cluster partitionings that have a large number of objects per cluster.", False, "The BIC penalty is for model complexity/number of parameters, not objects per cluster.", ["bic", "model-complexity"])
    add_tf("real-ss22-q061", source, 24, "61", ["unsupervised-learning"], "If we removed the second term from BIC, the resulting measure would favor models that maximally fit the data.", True, "Removing the complexity penalty leaves only the goodness-of-fit term.", ["bic", "overfitting"])
    add_tf("real-ss22-q062", source, 25, "62", ["markov-models-hmm"], "In MAP classification of a particular observation sequence, the prior in Bayes' rule can be calculated from the HMM.", False, "A class prior over models/classes is external to a single HMM's sequence likelihood.", ["hmm", "map"])
    add_tf("real-ss22-q063", source, 25, "63", ["markov-models-hmm"], "In an HMM, the number of observation symbols must equal the number of states.", False, "State space and observation alphabet are separate and can have different sizes.", ["hmm"])
    add_tf("real-ss22-q064", source, 25, "64", ["markov-models-hmm"], "An HMM observation matrix may contain columns that consist only of zeroes.", False, "A full zero column would make a state's observation probabilities sum to zero under the column-as-state convention.", ["hmm", "observation-matrix"])
    add_tf("real-ss22-q065", source, 26, "65", ["markov-models-hmm"], "The HMM state transition matrix is always square.", True, "It maps states to states, so it has one row and one column per state.", ["hmm", "transition-matrix"])
    add_tf("real-ss22-q066", source, 26, "66", ["markov-models-hmm"], "The Forward Algorithm calculates the probability of a state sequence.", False, "The Forward algorithm sums over state sequences to compute an observation-sequence probability.", ["hmm", "forward-algorithm"])
    add_tf("real-ss22-q067", source, 26, "67", ["markov-models-hmm"], "If all rows of the transition matrix are identical for all states, the same process could be modelled with just a single state.", False, "Identical transition distributions do not imply identical observation behaviour or equivalent hidden-state semantics.", ["hmm", "transition-matrix"])
    add_tf("real-ss22-q068", source, 26, "68", ["markov-models-hmm"], "An HMM observation model matrix may contain zeroes.", True, "Zero probabilities are allowed for impossible observations under a state.", ["hmm", "observation-matrix"])
    add_tf("real-ss22-q069", source, 27, "69", ["markov-models-hmm"], "The Forward Algorithm calculates the probability of an observation sequence.", True, "It efficiently marginalizes over all hidden state paths.", ["hmm", "forward-algorithm"])
    add_tf("real-ss22-q070", source, 27, "70", ["markov-models-hmm"], "A HMM permits us to calculate the probability of any state sequence, disregarding observations, of arbitrary length.", True, "The initial distribution and transition matrix define probabilities for state paths of any length.", ["hmm", "markov-chain"])


def build_2023_questions() -> None:
    source = "exam-2023-retake"
    cost_context = "Consider minimum-risk classification with conditional risk R(α_i|x)=sum_j λ(α_i|ω_j)P(ω_j|x)."
    add_tf("real-2023-q001", source, 1, "1", ["bayesian-classification"], f"{cost_context}\nMAP classification behaviour can be obtained by an appropriate setting of the cost function.", True, "Zero-one loss makes minimum-risk decisions equivalent to MAP decisions.", ["minimum-risk", "map"])
    add_tf("real-2023-q002", source, 1, "2", ["bayesian-classification"], f"{cost_context}\nThe effect of any change to the cost function can also be achieved by leaving the cost unchanged and modifying the likelihoods accordingly.", False, "Costs alter action-dependent risks and cannot in general be represented by valid class-conditional likelihood changes.", ["minimum-risk", "likelihood"])
    add_tf("real-2023-q003", source, 2, "3", ["bayesian-classification"], f"{cost_context}\nWritten as a matrix, λ is of quadratic shape.", True, "With one prediction action per class and one true class per column/row, the cost matrix is c x c.", ["loss-matrix"])
    add_tf("real-2023-q004", source, 2, "4", ["bayesian-classification"], f"{cost_context}\nFor any cost function, the expected cost is equal to the Bayes Error.", False, "Bayes error is the minimum expected zero-one error, not arbitrary expected cost.", ["bayes-error", "risk"])
    add_tf("real-2023-q005", source, 2, "5", ["bayesian-classification"], f"{cost_context}\nThe expected risk defines decision boundaries only in a two-dimensional feature space.", False, "Risk-based decision boundaries exist in any feature-space dimension.", ["decision-boundary", "risk"])
    add_multi("real-2023-q006", source, 3, "6", ["bayesian-classification"], f"{cost_context}\nIf we multiply the cost function by a constant k, the probability of all classes will ...", ["remain the same", "sum to 1.0*k", "change so probable classes become less probable", "increase by factor k", "be reduced by factor k"], [0], "Changing the cost function does not alter class probabilities.", ["cost-scaling", "posterior"], answer_source="inferred_from_slides", confidence=0.92)
    add_multi("real-2023-q007", source, 3, "7", ["bayesian-classification"], f"{cost_context}\nIf all λ_ij = 1, which statements are true?", ["minimum risk classification becomes MAP", "risk for all actions becomes c", "all decisions have the same cost for any x", "risk for all actions becomes 1 for any x", "for any x, every decision is equally good"], [2, 3, 4], "If every action has cost 1 for every true class, each action has risk sum_j P(ω_j|x)=1, so all decisions tie.", ["loss-matrix", "risk"], answer_source="inferred_from_slides", confidence=0.9)

    add_numeric("real-2023-q008", source, 4, "8", ["classifier-evaluation"], "A test set has 1000 examples with P:N = 3:7. For a classifier that randomly predicts n or p with probability 0.5, give TP, FP, FN, TN, Recall, Precision.", "TP=150, FP=350, FN=150, TN=350, Recall=0.5, Precision=0.3", "There are 300 positives and 700 negatives; random half-positive predictions split each class in expectation.", ["confusion-matrix", "precision", "recall"], answer_source="inferred_from_slides", confidence=0.94, difficulty="hard")
    add_numeric("real-2023-q009", source, 4, "9", ["classifier-evaluation"], "A test set has 1000 examples with P:N = 3:7. For a classifier that always predicts n, give TP, FP, FN, TN, Recall, Precision. Use -1 if undefined.", "TP=0, FP=0, FN=300, TN=700, Recall=0, Precision=-1", "No positive predictions are made, so precision is undefined; all positives are false negatives.", ["confusion-matrix", "precision", "recall"], answer_source="inferred_from_slides", confidence=0.94, difficulty="hard")
    add_tf("real-2023-q010", source, 5, "10", ["classifier-evaluation"], "The iso-performance line cannot go through points (0,0) and (1,1) in ROC space.", False, "An iso-performance line can have a slope that passes through both corners depending on costs/class priors.", ["roc", "iso-performance"], answer_source="explicit_pdf")
    add_tf("real-2023-q011", source, 5, "11", ["classifier-evaluation"], "For any classifier C and dataset D, Recall(C,D) + Precision(C,D) = 1.0.", False, "Recall and precision are independent measures and do not generally sum to one.", ["precision", "recall"], answer_source="explicit_pdf")
    add_tf("real-2023-q012", source, 5, "12", ["classifier-evaluation"], "If two classifiers have the same TPRs but different FPRs, they cannot have the same accuracy on any given fixed test set T.", True, "For fixed class counts, accuracy changes with false positives if true positives are fixed.", ["roc", "accuracy"], answer_source="explicit_pdf")
    add_tf("real-2023-q013", source, 5, "13", ["classifier-evaluation"], "Two classifiers with the same accuracy cannot occupy different places in ROC space.", False, "Different TPR/FPR tradeoffs can yield the same accuracy under fixed class priors.", ["roc", "accuracy"], answer_source="explicit_pdf")

    gd_context = (
        "Consider an alternative decision-tree split criterion GD(A)=sum_i |D_i|/|D| * |p_i-n_i|/(p_i+n_i) "
        "for a binary task with classes + and -."
    )
    add_single("real-2023-q014", source, 6, "14", ["decision-trees"], f"{gd_context}\nThe best feature is the one that ... this measure.", ["minimises", "maximises", "ignores", "normalizes"], 1, "The measure is high when branch class distributions are pure, so it should be maximized.", ["decision-tree", "split-criterion"], answer_source="inferred_from_exam_context", confidence=0.88)
    add_tf("real-2023-q015", source, 6, "15", ["decision-trees"], f"{gd_context}\nThis measure becomes maximal when each branch contains examples of only one class.", True, "For a pure branch, |p_i-n_i|/(p_i+n_i)=1, the largest possible value.", ["split-criterion", "purity"], answer_source="inferred_from_exam_context", confidence=0.9)
    add_single("real-2023-q016", source, 7, "16", ["decision-trees"], f"{gd_context}\nWhen feature A perfectly discriminates between the classes in D, GD(A) is ...", ["useless", "undefined", "equal to information gain", "< 0.0", "= 1.0", "> 1.0", "= 0.0"], 4, "Every branch is pure, so each weighted term is 1 and the weighted sum is 1.", ["split-criterion", "purity"], answer_source="inferred_from_exam_context", confidence=0.9)
    id3s_context = "ID3-S learns only trees of at most one level: it chooses a root feature by information gain and labels each child with its majority class."
    add_tf("real-2023-q017", source, 7, "17", ["decision-trees"], f"{id3s_context}\nThis is not a valid learning algorithm.", False, "It is a valid restricted learner; it simply has limited hypothesis space.", ["id3", "bias"], answer_source="explicit_pdf")
    add_tf("real-2023-q018", source, 7, "18", ["decision-trees"], f"{id3s_context}\nThis algorithm cannot result in a classifier with training accuracy 1.0.", False, "A depth-one tree can be perfectly accurate when one feature separates the classes.", ["id3", "accuracy"], answer_source="explicit_pdf")
    add_tf("real-2023-q019", source, 8, "19", ["decision-trees"], f"{id3s_context}\nThis is a high-bias learner.", True, "Restricting trees to one split severely limits expressiveness.", ["bias", "id3"], answer_source="explicit_pdf")
    add_tf("real-2023-q020", source, 8, "20", ["common-classifiers", "decision-trees"], f"{id3s_context}\nCombining different such trees via voting can improve accuracy on some dataset.", True, "An ensemble of weak, diverse trees can represent more robust decision behaviour.", ["ensemble", "voting"], answer_source="explicit_pdf")

    simple_nn = "Consider a simple network with one input x, one tanh hidden unit, one output y with identity activation, and sum-squared error."
    add_tf("real-2023-q021", source, 9, "21", ["neural-networks"], f"{simple_nn}\nA training set for this network has to consist of pairs of numbers.", True, "Each example supplies one numeric input and one numeric target output.", ["feed-forward-network", "training-data"], answer_source="explicit_pdf")
    add_tf("real-2023-q022", source, 9, "22", ["neural-networks"], f"{simple_nn}\nChanging the output activation from identity to tanh makes no difference because the hidden unit already uses tanh.", False, "The output activation constrains and transforms the final prediction, so it changes the function class.", ["activation", "tanh"], answer_source="inferred_from_slides", confidence=0.93)
    add_tf("real-2023-q023", source, 10, "23", ["neural-networks"], f"{simple_nn}\nIf the bias unit output changes from 1.0 to 2.0, the result is no longer a valid neural network.", False, "A constant bias input can be any nonzero constant if weights adapt accordingly.", ["bias-unit"], answer_source="inferred_from_slides", confidence=0.92)
    add_tf("real-2023-q024", source, 10, "24", ["neural-networks"], f"{simple_nn}\nChanging the bias output from 1.0 to 2.0 changes the absolute SSE but not the minimizing network weights.", False, "Changing the bias scale changes the parameterization; equivalent functions require correspondingly changed weights.", ["bias-unit", "loss"], answer_source="explicit_pdf")
    add_tf("real-2023-q025", source, 10, "25", ["neural-networks"], f"{simple_nn}\nThe loss function is defined over a four-dimensional parameter space.", True, "There are weights for input-to-hidden, bias-to-hidden, hidden-to-output, and bias-to-output.", ["weights", "parameter-space"], answer_source="inferred_from_slides", confidence=0.86)
    ce_context = "Now use the simple network for binary classification with logistic output, class labels 0/1, binary cross-entropy, and classify as 1 iff output >= 0.5."
    add_tf("real-2023-q026", source, 11, "26", ["neural-networks"], f"{ce_context}\nThis classifier can only learn decision boundaries that split the feature space into two regions.", True, "With one scalar input and one hidden unit, thresholding produces at most a simple two-region split.", ["decision-boundary", "neural-network"], answer_source="explicit_pdf")
    add_tf("real-2023-q027", source, 11, "27", ["neural-networks"], f"{ce_context}\nIf the network is made deeper, the cross-entropy function must be extended with additional terms.", False, "Cross-entropy is defined on target and predicted output, independent of the number of hidden layers.", ["cross-entropy"], answer_source="explicit_pdf")
    add_tf("real-2023-q028", source, 11, "28", ["neural-networks"], f"{ce_context}\nIf the class distribution is 50:50, binary cross-entropy encourages predictions close to 0.5.", False, "Cross-entropy encourages confident correct predictions for each example, not the class prior as every output.", ["cross-entropy", "classification"], answer_source="inferred_from_slides", confidence=0.93)
    add_tf("real-2023-q029", source, 11, "29", ["neural-networks"], f"{ce_context}\nThis classifier can easily overfit because the cross-entropy is non-linear.", False, "Overfitting depends on model capacity and data, not merely on nonlinearity of the loss.", ["overfitting", "cross-entropy"], answer_source="inferred_from_slides", confidence=0.9)

    add_tf("real-2023-q030", source, 12, "30", ["unsupervised-learning"], "In k-means with N observations, D numeric features, Euclidean distance, and k=5, increasing the number of features automatically makes the BIC model-complexity penalty larger.", True, "More dimensions increase the number of parameters in a probabilistic cluster model.", ["bic", "model-complexity"], answer_source="inferred_from_slides", confidence=0.88)
    add_tf("real-2023-q031", source, 12, "31", ["unsupervised-learning"], "In k-means, k has to be at least N/2.", False, "k can range from 1 up to N depending on the clustering task.", ["k-means"], answer_source="explicit_pdf")
    add_tf("real-2023-q032", source, 12, "32", ["unsupervised-learning"], "To use BIC for selecting k, a k-means cluster model must be converted into a probabilistic model.", True, "BIC is defined for probabilistic likelihood-based models.", ["bic", "k-means"], answer_source="explicit_pdf")
    add_tf("real-2023-q033", source, 13, "33", ["unsupervised-learning"], "The cluster with the smallest number of members will have the lowest/best MQE.", False, "MQE depends on distances to the center, not just cluster size.", ["mqe", "k-means"], answer_source="explicit_pdf")
    add_tf("real-2023-q034", source, 13, "34", ["unsupervised-learning"], "Feature normalization will change the MQE, but not the clusters found.", False, "Normalization changes distances and can change k-means assignments.", ["normalization", "k-means"], answer_source="explicit_pdf")
    add_single("real-2023-q035", source, 13, "35", ["unsupervised-learning"], "A GMM with k components learned from N examples in a D-dimensional numeric feature space is specified by how many parameters, ignoring redundancies from constraints and symmetries?", ["k + kD + D", "k(D*N)", "k + kD + kD^2", "3kD", "kD + N", "kN + kD + kD^2", "3k"], 2, "A full-covariance GMM needs mixture weights, a D-dimensional mean per component, and a D x D covariance per component.", ["gmm", "parameters"], answer_source="inferred_from_slides", confidence=0.86)

    markov_context = "Consider a Markov process with 3 states and transition matrix A with columns summing to one, plus uniform prior Π=[1/3,1/3,1/3]."
    add_tf("real-2023-q036", source, 14, "36", ["markov-models-hmm"], f"{markov_context}\nIf some a_ij is changed to zero, then a_ji must also be zero for a valid Markov process.", False, "Transition probabilities need not be symmetric.", ["markov-chain", "transition-matrix"], answer_source="inferred_from_slides", confidence=0.93)
    add_tf("real-2023-q037", source, 14, "37", ["markov-models-hmm"], f"{markov_context}\nIf one number is made smaller, at least one number in the same column must become larger.", True, "With the exam's column-normalized matrix convention, each column must still sum to one.", ["markov-chain", "transition-matrix"], answer_source="inferred_from_slides", confidence=0.84)
    add_tf("real-2023-q038", source, 14, "38", ["markov-models-hmm"], f"{markov_context}\nIf one number is made smaller, at least one number in the same row must become larger.", False, "The normalization constraint is on columns in this exam convention, not rows.", ["markov-chain", "transition-matrix"], answer_source="inferred_from_slides", confidence=0.84)
    add_tf("real-2023-q039", source, 15, "39", ["markov-models-hmm"], "The expected number of consecutive occurrences of state S2 is higher than that of state S1 for the shown transition matrix.", True, "Expected duration in a state grows with the self-transition probability; S2 has the larger self-transition in the exam matrix.", ["markov-chain", "duration"], answer_source="explicit_pdf")
    add_numeric("real-2023-q040", source, 15, "40", ["markov-models-hmm"], "With identity transition matrix A and uniform prior over S1,S2,S3, what is P((S1,S1,S2,S2,S3,S3)|M)?", "0", "Identity transitions never switch state, so a sequence with state changes has probability zero.", ["markov-chain", "sequence-probability"], answer_source="inferred_from_slides", confidence=0.96)
    add_numeric("real-2023-q041", source, 15, "41", ["markov-models-hmm"], "With identity transition matrix A and uniform prior over S1,S2,S3, what is P((S1,S1,S1,S1,S1)|M)?", "1/3", "The prior probability of starting in S1 is 1/3 and all self-transitions have probability 1.", ["markov-chain", "sequence-probability"], answer_source="inferred_from_slides", confidence=0.96)
    add_numeric("real-2023-q042", source, 15, "42", ["markov-models-hmm"], "With identity transition matrix A and uniform prior over S1,S2,S3, what is P((S1,S2,S3,S1,S2,S3)|M)?", "0", "The identity transition matrix assigns zero probability to every state change.", ["markov-chain", "sequence-probability"], answer_source="inferred_from_slides", confidence=0.96)
    add_multi("real-2023-q043", source, 16, "43", ["markov-models-hmm", "bayesian-classification"], "To classify whether a weather observation sequence S came from city A or B using Markov models M_A and M_B with the MAP principle, which quantities are needed?", ["P(A)", "P(S|M_B)", "P(M_B|M_A)", "P(S|M_A)", "P(B)"], [0, 1, 3, 4], "MAP compares P(S|M_A)P(A) with P(S|M_B)P(B).", ["map", "markov-model", "likelihood"], answer_source="inferred_from_slides", confidence=0.94)
    add_tf("real-2023-q044", source, 16, "44", ["markov-models-hmm"], "If S2 is produced by concatenating two copies of S, the likelihoods change, but the MAP decision always remains the same.", False, "Likelihood ratios can change under concatenation, and priors may affect the MAP decision differently.", ["map", "sequence-likelihood"], answer_source="explicit_pdf")
    add_tf("real-2023-q045", source, 17, "45", ["markov-models-hmm"], "This Markov-model classification procedure is only possible if the length of S is at least 2.", False, "A length-one sequence can still be scored using initial/state probabilities or observation probabilities, depending on the model.", ["markov-model"], answer_source="explicit_pdf")
    add_tf("real-2023-q046", source, 17, "46", ["markov-models-hmm"], "The same decision could be made without a Markov model, simply by counting the different states in S.", False, "A Markov model uses order and transition probabilities, not only state counts.", ["markov-model", "sequence"], answer_source="inferred_from_slides", confidence=0.94)


def build_generated_questions() -> None:
    gen_source = "generated-study-bank"
    generated_specs = [
        ("gen-bayes-001", ["bayesian-classification"], "A binary MAP classifier compares p(x|ω1)P(ω1) and p(x|ω2)P(ω2). If both class priors are multiplied by the same positive constant before normalization, can the MAP decision change?", False, "MAP depends on relative posterior scores. Multiplying both priors equally preserves their ratio and cannot change the argmax.", ["map", "prior"], "conceptual"),
        ("gen-intro-001", ["intro-classification"], "In supervised classification, the training examples include class labels.", True, "A supervised classifier learns from feature vectors paired with target classes.", ["supervised-learning", "labels"], "definition"),
        ("gen-intro-002", ["intro-classification"], "A decision boundary is defined in feature space, not in the space of class labels.", True, "The boundary separates regions of the input/feature space assigned to different classes.", ["feature-space", "decision-boundary"], "definition"),
        ("gen-bayes-002", ["bayesian-classification"], "A minimum-risk classifier with zero-one loss is equivalent to MAP classification.", True, "Zero-one loss makes the conditional risk of predicting a class equal to one minus that class posterior.", ["minimum-risk", "zero-one-loss"], "definition"),
        ("gen-bayes-003", ["bayesian-classification"], "The Bayes error is the error rate of any classifier trained with Bayes' rule.", False, "Bayes error is the irreducible error of the optimal classifier under the true distributions.", ["bayes-error"], "conceptual"),
        ("gen-density-001", ["density-estimation"], "In maximum likelihood estimation, the parameter value θ-hat is chosen to maximize p(D|θ), not p(θ|D).", True, "MLE maximizes likelihood of data under parameters; posterior maximization would be MAP estimation.", ["mle", "likelihood"], "definition"),
        ("gen-density-002", ["density-estimation"], "A likelihood value for continuous data can be greater than 1.", True, "Continuous probability densities can exceed 1; probabilities over regions must integrate to at most 1.", ["density", "likelihood"], "conceptual"),
        ("gen-knn-001", ["nearest-neighbour"], "Normalizing numeric features before k-NN can change predictions.", True, "k-NN relies on distances, and normalization changes feature contributions to distance.", ["knn", "normalization"], "application"),
        ("gen-knn-002", ["nearest-neighbour"], "As k increases in k-NN, the decision boundary typically becomes more jagged.", False, "Larger k averages over more neighbours, usually smoothing the boundary.", ["knn", "bias-variance"], "conceptual"),
        ("gen-eval-001", ["classifier-evaluation"], "A classifier can have high accuracy and low recall for a rare positive class.", True, "Accuracy can be dominated by the majority class, while recall focuses on positives.", ["accuracy", "recall", "imbalance"], "application"),
        ("gen-eval-002", ["classifier-evaluation"], "Moving a threshold over a fixed score-producing classifier can trace different ROC points.", True, "Thresholds change the tradeoff between TPR and FPR.", ["roc", "threshold"], "conceptual"),
        ("gen-eval-003", ["classifier-evaluation"], "Precision is undefined when a classifier makes no positive predictions.", True, "Precision divides true positives by predicted positives; the denominator is zero.", ["precision"], "definition"),
        ("gen-tree-001", ["decision-trees"], "Information gain chooses a split by maximizing the reduction in class entropy.", True, "ID3 uses information gain as an entropy-reduction heuristic.", ["id3", "information-gain"], "definition"),
        ("gen-tree-002", ["decision-trees"], "A numeric feature can appear more than once on a decision-tree path using different thresholds.", True, "Thresholds can successively narrow an interval.", ["decision-tree", "numeric-split"], "conceptual"),
        ("gen-tree-003", ["decision-trees"], "Pruning a decision tree always decreases test error.", False, "Pruning can reduce overfitting, but too much pruning can underfit and increase test error.", ["pruning", "test-error"], "conceptual"),
        ("gen-common-001", ["common-classifiers"], "Naive Bayes assumes conditional independence of features given the class.", True, "The classifier factorizes the likelihood into per-feature terms under this assumption.", ["naive-bayes"], "definition"),
        ("gen-common-002", ["common-classifiers"], "Changing class labels from +1/-1 to -1/+1 changes the geometric max-margin hyperplane of a trained hard-margin SVM.", False, "The orientation/sign changes, but the separating hyperplane geometry is the same.", ["svm", "max-margin"], "conceptual"),
        ("gen-common-003", ["common-classifiers"], "Bagging can reduce variance by averaging/voting over models trained on different bootstrap samples.", True, "Bootstrap diversity plus aggregation stabilizes predictions.", ["bagging", "ensemble"], "definition"),
        ("gen-improve-001", ["learning-improvement"], "Feature construction can make a classifier succeed even when the original feature space is not linearly separable.", True, "A transformed feature space can expose a simpler decision boundary.", ["feature-construction", "linear-separability"], "application"),
        ("gen-improve-002", ["learning-improvement"], "Model selection should usually be evaluated on the same training examples used to fit the final model parameters.", False, "Using the same data for fitting and selection gives optimistic estimates; validation or cross-validation is used to estimate generalization.", ["model-selection", "validation"], "conceptual"),
        ("gen-improve-003", ["learning-improvement"], "Averaging several high-variance models can reduce prediction variance.", True, "Ensemble averaging cancels part of the instability of individual models when their errors are not perfectly correlated.", ["ensemble", "variance"], "conceptual"),
        ("gen-nn-001", ["neural-networks"], "A bias unit lets a neuron shift its activation threshold away from the origin.", True, "The bias is an intercept term in the affine net input.", ["bias-unit"], "definition"),
        ("gen-nn-002", ["neural-networks"], "Gradient descent updates weights in the direction of the gradient when minimizing a loss.", False, "For minimization, weights move in the negative gradient direction.", ["gradient-descent"], "definition"),
        ("gen-nn-003", ["neural-networks"], "A logistic output unit is appropriate for interpreting a binary classifier output as a probability-like score.", True, "The logistic function maps real-valued net input to (0,1).", ["logistic", "binary-classification"], "conceptual"),
        ("gen-nn-004", ["neural-networks"], "Reducing the number of hidden units can increase model bias.", True, "Lower capacity tends to increase bias while reducing variance.", ["bias-variance", "capacity"], "conceptual"),
        ("gen-dl-001", ["deep-learning"], "Convolutional layers are useful when local patterns can occur at different positions in a structured input.", True, "Shared filters exploit locality and translation-like reuse.", ["convolution"], "conceptual"),
        ("gen-dl-002", ["deep-learning"], "Data augmentation may transform both inputs and targets if the transformation changes the correct label/action.", True, "For tasks like board games, mirroring the input also changes the target move.", ["data-augmentation"], "application"),
        ("gen-dl-003", ["deep-learning"], "The parameters of a deep neural network are mostly manually specified rather than learned.", False, "Weights are learned from data; architecture/hyperparameters are chosen manually.", ["parameters"], "definition"),
        ("gen-sed-001", ["deep-learning"], "For sound event detection, a model may need frame-level or segment-level outputs rather than one label for an entire recording.", True, "SED is about detecting event presence over time, so temporal localization matters.", ["sound-event-detection"], "application"),
        ("gen-unsup-001", ["unsupervised-learning"], "k-means directly optimizes cluster compactness around centroids.", True, "Its objective is based on squared distances to assigned centers.", ["k-means", "mqe"], "definition"),
        ("gen-unsup-002", ["unsupervised-learning"], "Increasing k in k-means always improves the BIC score.", False, "BIC balances fit with a complexity penalty, so more clusters are not always preferred.", ["bic", "k-means"], "conceptual"),
        ("gen-unsup-003", ["unsupervised-learning"], "A full-covariance Gaussian component in D dimensions needs O(D^2) covariance parameters.", True, "A D x D covariance matrix is quadratic in D before accounting for symmetry.", ["gmm", "parameters"], "calculation"),
        ("gen-hmm-001", ["markov-models-hmm"], "A Markov transition matrix must be square because it maps states to states.", True, "There is one transition probability for each ordered pair of states.", ["markov-chain", "transition-matrix"], "definition"),
        ("gen-hmm-002", ["markov-models-hmm"], "An HMM observation alphabet must have the same size as its hidden state set.", False, "Hidden states and possible observations are separate model components.", ["hmm", "observation-model"], "definition"),
        ("gen-hmm-003", ["markov-models-hmm"], "The Forward algorithm computes the likelihood of an observation sequence by summing over possible hidden state sequences.", True, "Dynamic programming avoids enumerating all paths explicitly.", ["forward-algorithm"], "conceptual"),
        ("gen-hmm-004", ["markov-models-hmm"], "The expected duration of staying in a state depends on that state's self-transition probability.", True, "Higher self-transition probability means longer expected runs.", ["markov-chain", "duration"], "application"),
    ]

    for qid, topic_ids, stem, correct, explanation, tags, level in generated_specs:
        add_tf(
            qid,
            gen_source,
            0,
            qid,
            topic_ids,
            stem,
            correct,
            explanation,
            tags,
            origin="generated_from_slides",
            answer_source="generated",
            confidence=0.86,
            difficulty="medium",
            cognitive_level=level,
        )

    add_single(
        "gen-bayes-004",
        gen_source,
        0,
        "gen-bayes-004",
        ["bayesian-classification"],
        "Which quantity can be ignored when choosing the MAP class for a fixed x?",
        ["p(x|ω_i)", "P(ω_i)", "p(x)", "P(ω_i|x)"],
        2,
        "p(x) is the same normalizer for every class in the argmax.",
        ["map", "evidence"],
        origin="generated_from_slides",
        answer_source="generated",
    )
    add_single(
        "gen-eval-004",
        gen_source,
        0,
        "gen-eval-004",
        ["classifier-evaluation"],
        "A classifier makes no positive predictions. What happens to precision for the positive class?",
        ["It is 0 by definition", "It is 1 by definition", "It is undefined", "It equals recall"],
        2,
        "Precision has predicted positives in the denominator.",
        ["precision"],
        origin="generated_from_slides",
        answer_source="generated",
    )
    add_single(
        "gen-unsup-004",
        gen_source,
        0,
        "gen-unsup-004",
        ["unsupervised-learning"],
        "What does the penalty term in BIC discourage?",
        ["More data points", "More complex models with more parameters", "Higher likelihood", "Lower dimensional data"],
        1,
        "BIC trades off model fit against parameter count.",
        ["bic", "model-selection"],
        origin="generated_from_slides",
        answer_source="generated",
    )


def attach_retrieval_text_and_slide_refs(slide_index: dict[str, Any]) -> None:
    chunks = slide_index["chunks"]
    by_lecture: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        by_lecture.setdefault(chunk["lectureId"], []).append(chunk)

    for question in QUESTIONS:
        retrieval = " ".join(
            [
                question["stem"],
                question["explanation"],
                " ".join(question.get("tags", [])),
                " ".join(question.get("topicIds", [])),
            ]
        )
        question["retrievalText"] = clean_text(retrieval)
        q_tokens = Counter(tokens(question["retrievalText"]))
        scored: list[tuple[float, dict[str, Any]]] = []
        for lecture_id in question["lectureIds"]:
            for chunk in by_lecture.get(lecture_id, []):
                c_tokens = Counter(tokens(chunk["retrievalText"]))
                overlap = sum(min(q_tokens[tok], c_tokens[tok]) for tok in q_tokens)
                if overlap:
                    score = overlap / math.sqrt(max(1, sum(c_tokens.values())))
                    scored.append((score, chunk))
        seen_pages: set[tuple[str, int]] = set()
        for _score, chunk in sorted(scored, key=lambda item: item[0], reverse=True)[:3]:
            key = (chunk["sourceId"], chunk["page"])
            if key in seen_pages:
                continue
            seen_pages.add(key)
            question["sourceRefs"].append(
                {
                    "sourceId": chunk["sourceId"],
                    "pages": [chunk["page"]],
                    "note": "Automatically linked lecture slide by keyword overlap.",
                }
            )


def validate_questions() -> None:
    ids = [question["id"] for question in QUESTIONS]
    duplicates = [qid for qid, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate question ids: {duplicates}")
    for question in QUESTIONS:
        if question["interactionType"] in {"true_false", "single_choice", "multi_select"}:
            if not question.get("choices"):
                raise ValueError(f"{question['id']} has no choices")
            valid_ids = {choice["id"] for choice in question["choices"]}
            for correct_id in question.get("correctChoiceIds", []):
                if correct_id not in valid_ids:
                    raise ValueError(f"{question['id']} has invalid correct choice {correct_id}")
        if not question["sourceRefs"]:
            raise ValueError(f"{question['id']} has no source refs")
        if not (0 <= question["confidence"] <= 1):
            raise ValueError(f"{question['id']} confidence out of range")


def approve_last(priority: str, rationale: str, mode: str = "closed_book") -> None:
    QUESTIONS[-1].update(
        {
            "examMode": mode,
            "sourcePriority": priority,
            "approvalStatus": "approved",
            "selectionRationale": rationale,
        }
    )


IMAGE_RATIONALE = "Directly transcribed from the 2026 closed-book exam image and solved against the lecture theory."
LEGACY_RATIONALE = "Kept from older exams because it is compact, closed-book-compatible, and matches the new one-best-answer schema."
GENERATED_RATIONALE = "AI-created and checked against the lecture slides to match the new closed-book exam style."


def img_single(
    qid: str,
    page: int,
    qn: str,
    topic_ids: list[str],
    stem: str,
    choices: list[str],
    correct_index: int,
    explanation: str,
    tags: list[str],
    *,
    difficulty: str = "medium",
    cognitive_level: str = "conceptual",
    confidence: float = 0.96,
    group_id: str | None = None,
) -> None:
    add_single(
        qid,
        f"img-closed-book-2026-p{page:02d}",
        page,
        qn,
        topic_ids,
        stem,
        choices,
        correct_index,
        explanation,
        tags,
        origin="real_closed_book_exam",
        answer_source="expert_verified",
        confidence=confidence,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
        group_id=group_id,
    )
    approve_last("primary", IMAGE_RATIONALE)


def img_tf(
    qid: str,
    page: int,
    qn: str,
    topic_ids: list[str],
    stem: str,
    correct: bool,
    explanation: str,
    tags: list[str],
    *,
    difficulty: str = "medium",
    cognitive_level: str = "conceptual",
    confidence: float = 0.96,
    group_id: str | None = None,
) -> None:
    add_tf(
        qid,
        f"img-closed-book-2026-p{page:02d}",
        page,
        qn,
        topic_ids,
        stem,
        correct,
        explanation,
        tags,
        origin="real_closed_book_exam",
        answer_source="expert_verified",
        confidence=confidence,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
        group_id=group_id,
    )
    approve_last("primary", IMAGE_RATIONALE)


def legacy_tf(
    qid: str,
    source_id: str,
    page: int,
    qn: str,
    topic_ids: list[str],
    stem: str,
    correct: bool,
    explanation: str,
    tags: list[str],
    *,
    difficulty: str = "medium",
    cognitive_level: str = "conceptual",
) -> None:
    add_tf(
        qid,
        source_id,
        page,
        qn,
        topic_ids,
        stem,
        correct,
        explanation,
        tags,
        origin="real_open_book_exam_approved",
        answer_source="explicit_pdf",
        confidence=0.95,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
    )
    approve_last("supporting", LEGACY_RATIONALE, mode="open_book_reference")


def legacy_single(
    qid: str,
    source_id: str,
    page: int,
    qn: str,
    topic_ids: list[str],
    stem: str,
    choices: list[str],
    correct_index: int,
    explanation: str,
    tags: list[str],
    *,
    difficulty: str = "medium",
    cognitive_level: str = "conceptual",
) -> None:
    add_single(
        qid,
        source_id,
        page,
        qn,
        topic_ids,
        stem,
        choices,
        correct_index,
        explanation,
        tags,
        origin="real_open_book_exam_approved",
        answer_source="explicit_pdf",
        confidence=0.95,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
    )
    approve_last("supporting", LEGACY_RATIONALE, mode="open_book_reference")


def gen_tf(
    qid: str,
    topic_ids: list[str],
    stem: str,
    correct: bool,
    explanation: str,
    tags: list[str],
    *,
    difficulty: str = "medium",
    cognitive_level: str = "conceptual",
) -> None:
    add_tf(
        qid,
        "generated-study-bank",
        0,
        qid,
        topic_ids,
        stem,
        correct,
        explanation,
        tags,
        origin="generated_from_slides",
        answer_source="generated",
        confidence=0.9,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
    )
    approve_last("supporting", GENERATED_RATIONALE)


def gen_single(
    qid: str,
    topic_ids: list[str],
    stem: str,
    choices: list[str],
    correct_index: int,
    explanation: str,
    tags: list[str],
    *,
    difficulty: str = "medium",
    cognitive_level: str = "conceptual",
) -> None:
    add_single(
        qid,
        "generated-study-bank",
        0,
        qid,
        topic_ids,
        stem,
        choices,
        correct_index,
        explanation,
        tags,
        origin="generated_from_slides",
        answer_source="generated",
        confidence=0.9,
        difficulty=difficulty,
        cognitive_level=cognitive_level,
    )
    approve_last("supporting", GENERATED_RATIONALE)


def build_new_image_questions() -> None:
    metric_context = (
        "In country A, 10% of people have disease X. T1 always predicts true, T2 always predicts false, "
        "T3 predicts true with probability 50%, and T4 predicts true with probability 10%, independently of the true class."
    )
    percent_choices = ["0%", "5%", "10%", "50%", "80%", "90%", "95%", "100%", "other"]
    img_single("img-q001", 2, "1", ["classifier-evaluation"], f"{metric_context}\nWhat is the expected accuracy that T2 will achieve on the population of A?", percent_choices, 5, "T2 always predicts false, so it is correct for the 90% of people without the disease.", ["accuracy", "baseline"], difficulty="easy", cognitive_level="calculation", group_id="img-classifier-metrics")
    img_single("img-q002", 2, "2", ["classifier-evaluation"], f"{metric_context}\nWhat is the expected accuracy that T4 will achieve on the population of A?", percent_choices, 8, "T4 is correct for diseased people when it predicts true (0.1*0.1) and for healthy people when it predicts false (0.9*0.9), totaling 0.82.", ["accuracy", "random-classifier"], cognitive_level="calculation", group_id="img-classifier-metrics")
    img_single("img-q003", 2, "3", ["classifier-evaluation"], f"{metric_context}\nWhat is the expected recall that T1 will achieve on the population of A?", percent_choices, 7, "T1 predicts true for every person, so it finds every diseased person.", ["recall"], difficulty="easy", cognitive_level="calculation", group_id="img-classifier-metrics")
    img_single("img-q004", 2, "4", ["classifier-evaluation"], f"{metric_context}\nWhat is the expected precision that T2 will achieve on the population of A?", percent_choices, 8, "T2 makes no positive predictions, so precision is undefined rather than a percentage.", ["precision", "undefined"], cognitive_level="calculation", group_id="img-classifier-metrics")

    cost_context = (
        "Using the same country A and tests T1-T4, classes are ordered as Ω=(true,false). "
        "The loss matrix λ_ij is the cost of predicting class i when the true class is j. Which test should be bought?"
    )
    test_choices = ["T1", "T2", "T3", "T4", "all equally good"]
    img_single("img-q005", 3, "5", ["bayesian-classification", "classifier-evaluation"], f"{cost_context}\nλ = [[0, 1], [1, 0]]", test_choices, 1, "With equal error costs, always predicting false has expected error 10%, lower than T4's 18%, T3's 50%, and T1's 90%.", ["cost-matrix", "risk"], cognitive_level="calculation", group_id="img-cost-decisions")
    img_single("img-q006", 3, "6", ["bayesian-classification", "classifier-evaluation"], f"{cost_context}\nλ = [[0, 100], [1, 0]]", test_choices, 1, "False positives are extremely expensive, so the always-negative test T2 has the lowest expected cost.", ["cost-matrix", "risk"], cognitive_level="calculation", group_id="img-cost-decisions")
    img_single("img-q007", 3, "7", ["bayesian-classification", "classifier-evaluation"], f"{cost_context}\nλ = [[0, 1], [100, 0]]", test_choices, 0, "False negatives are extremely expensive, so always predicting true avoids them and has the lowest expected cost.", ["cost-matrix", "risk"], cognitive_level="calculation", group_id="img-cost-decisions")
    img_single("img-q008", 3, "8", ["bayesian-classification", "classifier-evaluation"], f"{cost_context}\nλ = [[0, 100], [100, 0]]", test_choices, 1, "Both error types are equally expensive, so the lowest expected error rate still comes from T2.", ["cost-matrix", "risk"], cognitive_level="calculation", group_id="img-cost-decisions")

    img_tf("img-q009", 4, "9", ["classifier-evaluation"], "For a fixed dataset, two classifiers can occupy the same position in ROC space but have different accuracies.", False, "For a fixed class distribution, identical TPR and FPR imply identical accuracy.", ["roc", "accuracy"], group_id="img-classification-general")
    img_tf("img-q010", 4, "10", ["classifier-evaluation"], "Precision can never be strictly zero.", False, "Precision is zero when there are predicted positives but none of them are true positives.", ["precision"], group_id="img-classification-general")
    img_tf("img-q011", 4, "11", ["classifier-evaluation"], "Any classifier above the diagonal in ROC space, except the one at (0,0), has recall > 0.", True, "Above the diagonal means TPR > FPR. With TPR=0, FPR would have to be negative, which is impossible.", ["roc", "recall"], group_id="img-classification-general")
    img_tf("img-q012", 4, "12", ["classifier-evaluation"], "Two classifiers can have the same accuracy on a fixed dataset but occupy different places in ROC space.", True, "Different TPR/FPR tradeoffs can yield the same weighted accuracy for a fixed class distribution.", ["roc", "accuracy"], group_id="img-classification-general")
    img_tf("img-q013", 4, "13", ["classifier-evaluation"], "Recall can never be higher than precision.", False, "Recall and precision measure different denominators; recall can be higher, lower, or equal to precision.", ["recall", "precision"], group_id="img-classification-general")
    img_tf("img-q014", 4, "14", ["classifier-evaluation"], "In a world where false positives and false negatives have the same misclassification costs, recall = accuracy.", False, "Equal costs relate to error rate/accuracy, not to recall, which ignores true negatives.", ["recall", "accuracy", "cost"], group_id="img-classification-general")

    img_tf("img-q015", 5, "15", ["decision-trees"], "Reducing the set of features permitted in decision tree construction tends to reduce the learner's ability to overfit data.", True, "Fewer candidate splits reduce tree flexibility.", ["overfitting", "features"], group_id="img-overfitting")
    img_tf("img-q016", 5, "16", ["common-classifiers"], "Increasing the number of trees in a random forest tends to reduce the learner's ability to overfit data.", False, "More trees usually stabilise the ensemble; they do not reduce the capacity of the individual tree learner in the same way as pruning or feature limits.", ["random-forest", "overfitting"], confidence=0.9, group_id="img-overfitting")
    img_tf("img-q017", 5, "17", ["bayesian-classification"], "Not normalising by p(x) in a Bayesian MAP classifier tends to reduce its ability to overfit data.", False, "Dropping p(x) does not change MAP predictions because p(x) is constant across classes for a fixed x.", ["map", "evidence"], group_id="img-overfitting")
    img_tf("img-q018", 5, "18", ["neural-networks"], "Stopping neural network training before the training error has reached its minimum tends to reduce overfitting.", True, "Early stopping limits how closely the network fits the training set.", ["early-stopping", "overfitting"], group_id="img-overfitting")
    img_tf("img-q019", 5, "19", ["neural-networks"], "Doubling the number of hidden units in a feed-forward neural network tends to reduce its ability to overfit data.", False, "More hidden units increase capacity and can increase overfitting risk.", ["hidden-units", "capacity"], group_id="img-overfitting")
    img_tf("img-q020", 5, "20", ["decision-trees"], "Limiting the depth of a decision tree tends to reduce its ability to overfit data.", True, "A shallower tree has fewer possible decision regions.", ["tree-depth", "overfitting"], group_id="img-overfitting")
    img_tf("img-q021", 5, "21", ["nearest-neighbour"], "Increasing k in a k-NN classifier tends to reduce its ability to overfit data.", True, "Larger k smooths predictions over more neighbours.", ["knn", "overfitting"], group_id="img-overfitting")
    img_tf("img-q022", 5, "22", ["neural-networks"], "Replacing a non-linear activation function in a feed-forward neural network with a linear one tends to reduce its ability to overfit data.", True, "Removing nonlinearities reduces representational power.", ["activation", "capacity"], group_id="img-overfitting")

    img_single("img-q023", 6, "23", ["neural-networks"], "The gradient of the loss with respect to some weight w_i in a network tells us ...", ["whether w_i is positive or negative", "whether we need to make w_i smaller or larger to reduce the error", "what direction w_i is pointing", "how large the error is that is caused by w_i"], 1, "The gradient gives local sensitivity of the loss to the weight and therefore the update direction.", ["gradient", "weights"], group_id="img-ann")
    img_single("img-q024", 6, "24", ["neural-networks"], "The purpose of gradient descent in artificial neural networks is ...", ["to find the optimal number of weights", "to find the smallest values for the weights that produce zero error", "to find the optimal combination of values for the weights", "to find the optimal combination of values for the input units", "to find the optimal number of units"], 2, "Gradient descent optimizes trainable parameter values for a fixed architecture.", ["gradient-descent"], group_id="img-ann")
    img_single("img-q025", 6, "25", ["neural-networks"], "The loss function must be differentiable because ...", ["otherwise it would not be a proper function", "otherwise it could not reach zero", "otherwise it would not have a minimum", "otherwise we could not calculate how weights need to be changed", "otherwise changes to the weights would have no effect"], 3, "Gradient-based learning needs derivatives to compute weight updates.", ["loss", "differentiability"], group_id="img-ann")
    img_single("img-q026", 6, "26", ["neural-networks"], "Binary cross-entropy is ...", ["a measure of difference between two binary class distributions", "a measure of influence between two binary class distributions", "a measure of information gain in decision trees in binary classification problems", "a measure of the prediction error of an FFNN in a binary classification problem"], 3, "In this lecture context, BCE is used as the loss/error measure for binary neural-network classification.", ["cross-entropy", "binary-classification"], group_id="img-ann")
    img_single("img-q027", 6, "27", ["neural-networks"], "The learning rate is used to ...", ["control the amount of change to a weight during training", "control how close the error must come to zero before stopping", "control how much overfitting is permitted", "control the direction of change to a weight during training"], 0, "The learning rate scales the gradient update step.", ["learning-rate", "gradient-descent"], group_id="img-ann")
    img_single("img-q028", 6, "28", ["neural-networks"], "The sum-squared error measures ...", ["the error of a regression model on a specific dataset", "the sum of the squares of the errors a classifier will make in the future", "the sum of the errors a classifier will make in the future", "the square of the sum of the errors a classifier will make in the future"], 0, "SSE aggregates squared prediction errors over the given dataset.", ["sum-squared-error", "regression"], group_id="img-ann")

    img_single("img-q029", 7, "29", ["neural-networks"], "When running an ANN training algorithm several times on the same dataset, different models can result because of ...", ["randomness in the loss function", "randomness in the input feature values", "randomness due to the learning rate", "randomness in the initialisation of the weights", "randomness in the backpropagation update algorithm"], 3, "Random initialization can put gradient descent on different paths through the loss surface.", ["initialization", "training"], group_id="img-ann-continued")
    img_single("img-q030", 7, "30", ["neural-networks"], "Parameter optimisation via iterative gradient descent ...", ["may end up in a global optimum", "will always end up in a global optimum if the learning rate is small enough", "cannot end up in a global optimum"], 0, "Gradient descent may find a global optimum, but it is not guaranteed in non-convex neural-network losses.", ["gradient-descent", "optimization"], group_id="img-ann-continued")
    img_single("img-q031", 7, "31", ["neural-networks"], "A single unit in a hidden layer of an FFNN calculates ...", ["a weighted sum of non-linearly transformed inputs", "a sum of weights and inputs, transformed by a non-linear activation function", "a linear transformation of a non-linear weighted sum of inputs", "a non-linear transformation of a weighted sum of inputs"], 3, "A neuron first forms an affine weighted sum, then applies its activation function.", ["hidden-unit", "activation"], group_id="img-ann-continued")
    img_single("img-q032", 7, "32", ["neural-networks"], "In early stopping, we stop training an ANN ...", ["when the training error reaches zero", "when the validation error reaches zero", "when the training error goes above the validation error", "when the validation error starts going up", "when the validation error reaches the training error", "when the training error starts going up"], 3, "Rising validation error indicates that continued training is starting to hurt generalization.", ["early-stopping", "validation"], group_id="img-ann-continued")
    img_single("img-q033", 7, "33", ["neural-networks"], "If neighbouring fully connected layers L1 and L2 have N and M units, respectively, the weight matrix for L1 to L2 including bias weights has ...", ["N^2 + M^2 + M weights", "M x N + N weights", "N x M weights", "N x M + M weights", "(N + M)^2 + N weights"], 3, "Each of M output units receives N incoming weights plus one bias weight.", ["weights", "bias-unit"], cognitive_level="calculation", group_id="img-ann-continued")

    img_single("img-q034", 8, "34", ["nearest-neighbour"], "A k-Nearest Neighbour classifier ...", ["predicts the class of x based on a majority vote of x's k closest neighbours", "predicts the class of x based on the number of neighbours in a neighbourhood of radius k", "predicts the class of x based on the number of neighbours of x", "predicts the class of x based on the colour of x's k neighbours", "predicts the class of x based on the distance between x and its k-th neighbour"], 0, "k-NN assigns the majority class among the k closest training examples.", ["knn"], group_id="img-learning-algorithms")
    img_single("img-q035", 8, "35", ["decision-trees"], "In decision tree learning, the Information Gain ...", ["of a feature that has the same value for all training examples is zero", "is negative for all features in nodes where all examples already belong to the same class", "measures how much information a training example gives about the class", "of a feature cannot be zero when there are still examples of more than one class in the current subset", "is always highest for the feature at the root of a decision tree"], 0, "A constant feature cannot reduce entropy because it does not split the data.", ["information-gain", "id3"], group_id="img-learning-algorithms")
    img_single("img-q036", 8, "36", ["common-classifiers"], "A Support Vector Machine ...", ["fits a linear decision boundary into a space of non-linear feature combinations", "bases its classification decisions on vectors between pairs of examples of different classes", "moves some training examples apart by forcing a maximal margin between different classes", "bases its decisions on training examples that are linear combinations of each other", "fits a non-linear decision boundary into a space of linear feature combinations"], 0, "Kernel SVMs can learn a linear separator in a transformed feature space.", ["svm", "kernel"], group_id="img-learning-algorithms")
    img_single("img-q037", 8, "37", ["decision-trees"], "Which statement about decision trees and ID3 is correct?", ["In an ID3 tree, nodes at the same level are labelled with the same feature", "In an ID3 tree, no leaf can contain training examples of different classes", "If two training examples have the same feature values but different class labels, no decision tree can be 100% consistent with the training data", "There can be no dataset for which a consistent decision tree consists only of a root node", "In an ID3 tree, all leaves are at the same level"], 2, "Identical feature vectors cannot be separated by any feature test if their labels conflict.", ["id3", "consistency"], group_id="img-learning-algorithms")

    img_single("img-q038", 9, "38", ["decision-trees"], "Which of the following will not reduce the probability of overfitting when learning a decision tree from D?", ["discretise numeric features", "reduce the set of features", "add new features that are non-linear combinations of existing ones", "use a numeric feature at most once along each branch", "stop splitting at a node when the number of examples is below a fixed threshold"], 2, "Adding nonlinear feature combinations increases the available split space and can increase overfitting risk.", ["decision-tree", "overfitting"], group_id="img-learning-algorithms-continued")
    img_single("img-q039", 9, "39", ["decision-trees"], "A decision tree can overfit a given training set ...", ["only if there are errors in the training data", "only if all features in the data are irrelevant", "only if we apply no pruning", "only if the data contain numeric features", "only if the training set does not contain all observations that are possible in the world"], 4, "Overfitting is possible because a finite training set may not represent the full data-generating world.", ["decision-tree", "overfitting"], confidence=0.9, group_id="img-learning-algorithms-continued")
    img_single("img-q040", 9, "40", ["common-classifiers"], "A Naive Bayes classifier ...", ["assumes that features and classes are uncorrelated", "assumes pairwise independence between classes", "assumes that examples of two different classes have no feature values in common", "assumes pairwise independence between features in each class", "assumes that any pair of features is uncorrelated in D"], 3, "Naive Bayes assumes conditional independence of features given the class.", ["naive-bayes", "conditional-independence"], group_id="img-learning-algorithms-continued")
    img_single("img-q041", 9, "41", ["common-classifiers"], "The motivation for the Random Forest classifier is the idea that ...", ["combining classifiers with different errors reduces the danger of overfitting", "decision trees are high-bias classifiers", "multiplying the input features permits more confident class predictions", "more training data reduces the danger of overfitting", "combining decision trees into a larger tree reduces the danger of overfitting"], 0, "Random forests reduce variance by aggregating diverse trees.", ["random-forest", "ensemble"], group_id="img-learning-algorithms-continued")

    unsup_context = "Dataset D has N training examples x_i in a d-dimensional feature space and no class labels. Parameters mean numbers that must be learned."
    img_single("img-q042", 10, "42", ["unsupervised-learning"], f"{unsup_context}\nA Gaussian Mixture Model with k components trained on this dataset will have ...", ["k(d + d(d+1)/2 + 1) parameters", "kdN^2 parameters", "k^2 parameters", "kd^2 parameters", "k(d+1) parameters", "kd parameters", "kN + d parameters"], 0, "Each component needs a mean vector, covariance parameters, and a mixture weight.", ["gmm", "parameters"], cognitive_level="calculation", group_id="img-unsupervised")
    img_single("img-q043", 10, "43", ["unsupervised-learning"], "In clustering, the Bayes Information Criterion (BIC) is used ...", ["to determine the optimal number of clusters", "to determine the optimal center for each cluster", "to determine the optimal number of examples per cluster", "to determine the optimal initialisation for each cluster center", "to determine the optimal number of parameters"], 0, "BIC compares model choices such as k by balancing fit and model complexity.", ["bic", "model-selection"], group_id="img-unsupervised")
    img_single("img-q044", 10, "44", ["unsupervised-learning"], "Running the complete k-means algorithm several times on the same dataset D ...", ["may result in a different clustering every time", "will produce the same result every time", "will gradually reduce the MQE in each run until it reaches a global minimum", "is a strategy for preventing overfitting", "will reduce the MQE until it starts to grow on an independent evaluation set"], 0, "Different random initializations can converge to different local optima.", ["k-means", "initialization"], group_id="img-unsupervised")
    img_single("img-q045", 10, "45", ["unsupervised-learning"], "A Gaussian Mixture Model is ...", ["a compact description of D as a weighted sum of examples", "a mixture of Gaussian and uniform distributions", "an alternative to Bayes' Rule for calculating posterior class probabilities", "a partitioning of D into k subsets based on random mixing", "a probability density function over feature space"], 4, "A GMM defines a weighted sum of Gaussian component densities over feature space.", ["gmm", "density"], group_id="img-unsupervised")
    img_single("img-q046", 10, "46", ["unsupervised-learning"], "The Mean Quantisation Error measures ...", ["the average distance of examples from their cluster mean", "the mean distance between any pair of cluster centers", "the error from quantising each feature dimension into discrete clusters", "the average difference between mean and median of all features in D"], 0, "MQE measures compactness via distances from points to their assigned centers.", ["mqe", "k-means"], group_id="img-unsupervised")
    img_single("img-q047", 11, "47", ["unsupervised-learning"], "For a fixed dataset D and any k < N, which statement is correct?", ["The quantisation error for any cluster is only defined if the cluster contains at least 2 examples", "The quantisation error for any cluster cannot be larger than k", "The MQE can be non-zero only for even k", "The minimal MQE obtainable with k clusters cannot be larger than the minimal MQE obtainable with k+1 clusters"], 3, "Adding one more cluster cannot make the best achievable MQE worse; the k+1 solution can always emulate the k-cluster solution.", ["mqe", "k-means"], confidence=0.88, group_id="img-unsupervised")
    img_single("img-q048", 11, "48", ["unsupervised-learning"], "A k-means clustering model trained on this dataset will have ...", ["kdN^2 parameters", "k(d + d(d+1)/2 + 1) parameters", "k^2 parameters", "k(d+1) parameters", "kN + d parameters", "kd^2 parameters", "kd parameters"], 6, "A k-means model stores k cluster centers, each with d coordinates.", ["k-means", "parameters"], cognitive_level="calculation", group_id="img-unsupervised")


def build_legacy_approved_questions() -> None:
    legacy_tf("legacy-q001", "exam-retake-2", 1, "8", ["density-estimation"], "The likelihood function cannot be negative anywhere.", True, "Likelihoods are products of probability or density values, so they are non-negative.", ["likelihood"])
    legacy_tf("legacy-q002", "exam-retake-2", 2, "11", ["density-estimation"], "The likelihood function is itself a normal distribution.", False, "A likelihood is a function of parameters for fixed data; it is not itself the data-generating distribution.", ["likelihood", "mle"])
    legacy_tf("legacy-q003", "exam-retake-1", 2, "5", ["bayesian-classification"], "With zero-one loss, a Bayesian minimum-risk classifier makes the same predictions as a MAP classifier.", True, "Zero-one loss turns risk minimization into choosing the class with largest posterior probability.", ["minimum-risk", "map"])
    legacy_tf("legacy-q004", "exam-retake-1", 3, "7", ["bayesian-classification"], "Multiplying every value in a loss matrix by the same positive constant makes the loss function invalid.", False, "Positive scaling keeps the loss valid and preserves the risk-minimizing action.", ["cost-matrix"])
    legacy_tf("legacy-q005", "exam-retake-3", 1, "14", ["nearest-neighbour"], "For k-NN with k=N, the classifier will maximally overfit the training data.", False, "Using every training example gives a high-bias global majority vote, not maximal overfitting.", ["knn", "bias"])
    legacy_tf("legacy-q006", "exam-retake-3", 2, "18", ["nearest-neighbour"], "For k-NN with k=N, all test examples are classified into the same class.", True, "Every prediction uses the same full training set vote.", ["knn"])
    legacy_tf("legacy-q007", "exam-retake-4", 1, "20", ["decision-trees"], "A chosen feature split in a decision tree might have information gain zero.", True, "A feature can be unrelated to the class labels.", ["information-gain"])
    legacy_tf("legacy-q008", "exam-retake-4", 2, "23", ["decision-trees"], "A one-level tree with majority-class leaves is not a decision tree.", False, "A root split with leaves is a valid decision tree.", ["decision-tree"])
    legacy_tf("legacy-q009", "exam-ss20", 4, "9", ["nearest-neighbour"], "Adding redundant copies of a feature can change k-NN predictions.", True, "Duplicating a feature changes Euclidean distances by increasing that feature's weight.", ["knn", "feature-scaling"])
    legacy_tf("legacy-q010", "exam-ss20", 4, "10", ["nearest-neighbour"], "Changing the scale of one feature can change k-NN predictions.", True, "Euclidean distance is sensitive to feature scale.", ["knn", "normalization"])
    legacy_single("legacy-q011", "exam-ss20", 10, "29", ["neural-networks"], "Adding an additional hidden layer to a feed-forward network generally affects model bias how?", ["it increases", "it decreases", "it is unchanged", "it becomes undefined"], 1, "More expressive models generally have lower bias.", ["bias-variance", "hidden-layer"])
    legacy_single("legacy-q012", "exam-ss20", 10, "30", ["neural-networks"], "Adding an additional hidden layer to a feed-forward network generally affects model variance how?", ["it increases", "it decreases", "it is unchanged", "it becomes zero"], 0, "More flexible models are usually more sensitive to the training sample.", ["bias-variance", "hidden-layer"])
    legacy_tf("legacy-q013", "exam-ss22", 26, "65", ["markov-models-hmm"], "The state transition matrix of a Hidden Markov Model is always square.", True, "It contains transition probabilities between every pair of hidden states.", ["hmm", "transition-matrix"])
    legacy_tf("legacy-q014", "exam-ss22", 27, "69", ["markov-models-hmm"], "The Forward Algorithm calculates the probability of an observation sequence.", True, "It sums over hidden state paths efficiently with dynamic programming.", ["hmm", "forward-algorithm"])


def build_closed_book_generated_questions() -> None:
    gen_single("gen-closed-q001", ["bayesian-classification"], "In MAP classification, which term can be omitted when comparing classes for one fixed input x?", ["p(x|ω_i)", "P(ω_i)", "p(x)", "P(ω_i|x)"], 2, "The evidence p(x) is the same denominator for every class.", ["map", "evidence"])
    gen_single("gen-closed-q002", ["bayesian-classification"], "A classifier that always predicts the most frequent class is best described as ...", ["a MAP classifier with equal priors", "a baseline/default classifier", "a nearest-neighbour classifier", "a minimum-risk classifier with arbitrary costs"], 1, "The default classifier ignores x and predicts the majority class.", ["baseline"])
    gen_single("gen-closed-q003", ["bayesian-classification"], "If false negatives are much more expensive than false positives, a risk-minimizing binary classifier should tend to ...", ["predict the positive class less often", "predict the positive class more often", "ignore the posterior", "use only the likelihood"], 1, "The classifier avoids costly false negatives by lowering the bar for positive predictions.", ["minimum-risk", "cost"])
    gen_tf("gen-closed-q004", ["bayesian-classification"], "The posterior P(ω_i|x) is a scalar value for a fixed class ω_i and feature vector x.", True, "The full posterior distribution has one scalar per class.", ["posterior"])
    gen_tf("gen-closed-q005", ["bayesian-classification"], "Class-conditional likelihoods p(x|ω_i) must sum to one over i for a fixed x.", False, "They are densities/likelihoods per class, not posterior probabilities over classes.", ["likelihood"])
    gen_single("gen-closed-q006", ["density-estimation"], "Maximum likelihood estimation chooses parameters by maximizing ...", ["p(θ|D)", "p(D|θ)", "P(ω|x)", "the prior P(θ) only"], 1, "MLE maximizes the likelihood of the observed data under the parameter.", ["mle"])
    gen_tf("gen-closed-q007", ["density-estimation"], "For continuous variables, a probability density value can be larger than 1.", True, "Densities can exceed one; integrals over regions correspond to probabilities.", ["density"])
    gen_single("gen-closed-q008", ["density-estimation"], "A non-parametric density estimator mainly differs from a parametric one because it ...", ["assumes a fixed small family such as a Gaussian", "does not fix the shape to a finite-parameter family in the same way", "cannot use training data", "always has zero variance"], 1, "Non-parametric methods let complexity grow with data or local structure.", ["non-parametric"])
    gen_single("gen-closed-q009", ["classifier-evaluation"], "Which metric ignores true negatives?", ["accuracy", "recall", "error rate", "specificity"], 1, "Recall is TP/(TP+FN), so true negatives are absent.", ["recall"])
    gen_single("gen-closed-q010", ["classifier-evaluation"], "A classifier that predicts every example as positive has recall ...", ["0", "undefined", "1 for the positive class if positives exist", "equal to precision"], 2, "All actual positives are predicted positive.", ["recall"])
    gen_tf("gen-closed-q011", ["classifier-evaluation"], "Two classifiers with the same ROC point must have the same TPR and FPR.", True, "ROC coordinates are FPR and TPR.", ["roc"])
    gen_tf("gen-closed-q012", ["classifier-evaluation"], "Accuracy is a reliable standalone measure when the positive class is very rare.", False, "A majority-class classifier can have high accuracy while missing rare positives.", ["accuracy", "imbalance"])
    gen_single("gen-closed-q013", ["classifier-evaluation"], "If a classifier makes no positive predictions, precision is ...", ["0", "1", "undefined", "equal to recall"], 2, "The denominator TP+FP is zero.", ["precision"])
    gen_single("gen-closed-q014", ["decision-trees"], "ID3 chooses a split using ...", ["Euclidean distance", "information gain", "gradient descent", "posterior probability"], 1, "ID3 greedily maximizes information gain.", ["id3"])
    gen_tf("gen-closed-q015", ["decision-trees"], "A symbolic feature that has already been used on a decision-tree path usually gives no further split information on that path.", True, "The branch already fixes its symbolic value.", ["decision-tree"])
    gen_tf("gen-closed-q016", ["decision-trees"], "A numeric feature can be tested multiple times along one decision-tree path using different thresholds.", True, "Repeated thresholds can refine intervals.", ["numeric-split"])
    gen_single("gen-closed-q017", ["decision-trees"], "Pruning a decision tree primarily aims to ...", ["increase tree depth", "reduce overfitting", "make all leaves the same level", "remove the class labels"], 1, "Pruning reduces model complexity.", ["pruning"])
    gen_single("gen-closed-q018", ["nearest-neighbour"], "Why can feature normalization matter for k-NN?", ["It changes class priors", "It changes Euclidean distances", "It changes the number of examples", "It makes k irrelevant"], 1, "k-NN bases predictions on distances.", ["knn", "normalization"])
    gen_tf("gen-closed-q019", ["nearest-neighbour"], "A 1-NN classifier usually has lower bias and higher variance than a large-k classifier.", True, "Small k creates flexible local decision boundaries.", ["knn", "bias-variance"])
    gen_single("gen-closed-q020", ["nearest-neighbour"], "If k equals the number of training examples, k-NN predicts according to ...", ["the nearest single example", "the global majority vote of the training set", "a random class", "the smallest-distance class only"], 1, "Every query uses all training examples as neighbours.", ["knn"])
    gen_single("gen-closed-q021", ["common-classifiers"], "The 'naive' assumption in Naive Bayes is about ...", ["equal class priors", "conditional independence of features given the class", "linear decision boundaries only", "zero training error"], 1, "Naive Bayes factorizes feature likelihoods given the class.", ["naive-bayes"])
    gen_single("gen-closed-q022", ["common-classifiers"], "A hard-margin linear SVM chooses a separating hyperplane by maximizing ...", ["entropy", "the margin", "the learning rate", "the number of support vectors"], 1, "The margin is the distance to the closest training examples.", ["svm"])
    gen_tf("gen-closed-q023", ["common-classifiers"], "A random forest tries to reduce variance by combining diverse decision trees.", True, "Averaging/voting over decorrelated trees stabilizes predictions.", ["random-forest"])
    gen_single("gen-closed-q024", ["learning-improvement"], "Feature construction can help because it may ...", ["remove all priors", "make a hard boundary simpler in the transformed space", "force all classifiers to be linear", "make validation unnecessary"], 1, "Constructed features can expose structure that was not simple in the original space.", ["feature-construction"])
    gen_tf("gen-closed-q025", ["learning-improvement"], "Choosing hyperparameters on the final test set gives an unbiased estimate of generalization.", False, "Using the test set for selection leaks information and biases the estimate.", ["model-selection"])
    gen_single("gen-closed-q026", ["neural-networks"], "A bias unit in a neural network acts like ...", ["a fixed input enabling an intercept term", "a validation set", "a loss function", "a random forest tree"], 0, "Bias weights shift activation thresholds.", ["bias-unit"])
    gen_tf("gen-closed-q027", ["neural-networks"], "Without nonlinear activations, a stack of fully connected layers collapses to a linear transformation.", True, "Compositions of linear functions are linear.", ["activation"])
    gen_single("gen-closed-q028", ["neural-networks"], "Gradient descent minimizes a loss by moving weights ...", ["in the positive gradient direction", "in the negative gradient direction", "only when the gradient is zero", "randomly at every step"], 1, "The negative gradient is the local steepest descent direction.", ["gradient-descent"])
    gen_tf("gen-closed-q029", ["neural-networks"], "A learning rate that is too large can overshoot good parameter values.", True, "Large updates can bounce across or diverge from minima.", ["learning-rate"])
    gen_single("gen-closed-q030", ["neural-networks"], "Early stopping uses which data signal most directly?", ["training error only", "validation error", "test-set labels after deployment", "class priors only"], 1, "Training is stopped when validation performance starts worsening.", ["early-stopping"])
    gen_single("gen-closed-q031", ["neural-networks"], "For binary classification with a logistic output, binary cross-entropy penalizes ...", ["only false positives", "only false negatives", "confident wrong probability predictions strongly", "the number of hidden units directly"], 2, "The log terms grow large when the predicted probability is confidently wrong.", ["cross-entropy"])
    gen_single("gen-closed-q032", ["deep-learning"], "Convolutional layers are especially useful for inputs with ...", ["no local structure", "local patterns that can appear at different positions", "only one scalar feature", "no repeated patterns"], 1, "Convolutions share filters over spatial or temporal positions.", ["convolution"])
    gen_tf("gen-closed-q033", ["deep-learning"], "Data augmentation may transform the target as well as the input.", True, "For structured tasks, transformations such as mirroring can change the correct target.", ["data-augmentation"])
    gen_single("gen-closed-q034", ["unsupervised-learning"], "k-means stores which learned quantities?", ["class priors", "cluster centers", "support vectors", "decision-tree thresholds only"], 1, "The learned k-means model is the set of centroids.", ["k-means"])
    gen_tf("gen-closed-q035", ["unsupervised-learning"], "Increasing k in k-means cannot increase the best achievable within-cluster quantisation error.", True, "More clusters can emulate fewer clusters or improve the fit.", ["mqe"])
    gen_single("gen-closed-q036", ["unsupervised-learning"], "BIC trades off model fit against ...", ["feature scaling", "model complexity", "training-set ordering", "activation functions"], 1, "The BIC penalty discourages overly complex models.", ["bic"])
    gen_single("gen-closed-q037", ["unsupervised-learning"], "A full-covariance Gaussian component in d dimensions needs covariance parameters on the order of ...", ["d", "d^2", "N", "kN"], 1, "A covariance matrix is d by d, with symmetry reducing but not eliminating quadratic growth.", ["gmm", "parameters"])
    gen_tf("gen-closed-q038", ["markov-models-hmm"], "A Markov transition matrix is square because it maps states to states.", True, "There is one transition probability for each state-to-state pair.", ["markov-chain"])
    gen_tf("gen-closed-q039", ["markov-models-hmm"], "In an HMM, the observation alphabet must have the same size as the hidden state set.", False, "Hidden states and observation symbols are separate sets.", ["hmm"])
    gen_single("gen-closed-q040", ["markov-models-hmm"], "The Forward algorithm is used to compute ...", ["the probability of an observation sequence", "the number of clusters", "the information gain of a feature", "the SVM margin"], 0, "It marginalizes over hidden state paths.", ["forward-algorithm"])


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    copy_image_assets()
    now = datetime.now(timezone.utc).isoformat()
    slide_index = extract_slide_chunks(now)
    build_new_image_questions()
    build_legacy_approved_questions()
    build_closed_book_generated_questions()
    attach_retrieval_text_and_slide_refs(slide_index)
    validate_questions()

    bank = {
        "version": "1.0.0",
        "generatedAt": now,
        "course": {
            "code": "MLPC",
            "title": "Machine Learning and Pattern Classification",
            "university": "Johannes Kepler University Linz",
            "language": "en",
        },
        "defaults": {
            "choicesPerMultipleChoice": 4,
            "generatedQuestionStyle": "Closed-book Group-B-style prompts: compact theory, one best answer, true/false only where the new paper used it.",
            "realExamPolicy": "The 2026 closed-book exam images in new_img are the primary source. Older open-book exam questions are kept only when they match the compact closed-book schema.",
            "answerPolicy": "Image questions do not include an answer key, so their answers are expert_verified against the lecture theory. Older retained questions use explicit PDF answers where available.",
        },
        "sources": sources()
        + [
            {
                "id": "generated-study-bank",
                "kind": "generated",
                "title": "Generated exam-style study questions based on lecture slides and past-exam patterns",
                "fileName": "generated",
                "pageCount": 0,
            }
        ],
        "topics": TOPICS,
        "questions": QUESTIONS,
    }

    (DATA_DIR / "question-bank.json").write_text(
        json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DATA_DIR / "slide-index.json").write_text(
        json.dumps(slide_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    counts = Counter(question["origin"] for question in QUESTIONS)
    topic_counts = Counter(topic_id for question in QUESTIONS for topic_id in question["topicIds"])
    print(f"Wrote {len(QUESTIONS)} questions")
    print(dict(counts))
    print("Top topics:", dict(topic_counts.most_common()))
    print(f"Wrote {len(slide_index['chunks'])} slide chunks")


if __name__ == "__main__":
    main()
