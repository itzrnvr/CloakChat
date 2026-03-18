# Project Spect — Evaluation System Documentation

> **Purpose**: This document provides comprehensive context about the Project Spect evaluation system. It is designed to be dropped into any AI agent to give it full understanding of the what, why, and how.

---

## 📌 What Is Project Spect?

**Project Spect** is a privacy-first AI proxy that sits between users and cloud LLMs (Gemini, OpenAI). It intercepts user messages, **anonymizes PII locally** using a small LLM, sends the sanitized text to the cloud, and reconstructs original values when displaying responses.

### Core Architecture

```
┌─────────────┐      ┌─────────────────┐      ┌─────────────┐
│    User     │ ───▶ │  Anonymizer     │ ───▶ │  Cloud LLM  │
│   (Real)    │      │  (Local LLM)    │      │  (Gemini)   │
└─────────────┘      └─────────────────┘      └─────────────┘
       │                     │                       │
       │                     ▼                       │
       │              Entity Map:                    │
       │           "John" → "Marcus"                 │
       │                     │                       │
       ◀─────────────────────┼───────────────────────┘
                Reconstruct: "Marcus" → "John"
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| **Anonymizer** | `src/anonymizer.py` | Detects PII, generates semantic replacements, maps entities |
| **Local LLM** | `src/llm_local.py` | Runs a small GGUF model via `llama-cpp-python` for PII detection |
| **Cloud Provider** | `src/cloud_provider.py` | Unified interface for Gemini/OpenAI |
| **Config** | `config.yaml` | Model paths, strategies, provider settings |
| **Evaluation** | `eval/run_eval.py` | Benchmarks anonymization quality |

---

## 🎯 What Is the Evaluation System?

The evaluation system (`eval/run_eval.py`) measures how well the Anonymizer detects and replaces PII by comparing its output against a **ground truth dataset**.

### Purpose

1. **Benchmark Model Performance** — Measure Precision, Recall, and F1 scores
2. **Compare Strategies** — Test "fast" vs "verify" anonymization modes
3. **Track Progress** — Persist results across runs to compare improvements
4. **Identify Weaknesses** — Find specific PII types the model misses (emails, phones, etc.)

---

## 📊 Evaluation Metrics Explained

### Definitions

| Metric | Formula | Meaning |
|--------|---------|---------|
| **Precision** | `TP / Total Found` | Of everything we detected, how much was actually PII? |
| **Recall** | `TP / Total Truth` | Of all the actual PII, how much did we find? |
| **F1 Score** | `2 × (P × R) / (P + R)` | Harmonic mean — balances precision and recall |

### True/False Positives

- **True Positive (TP)**: Ground truth PII that was correctly detected
- **False Positive (FP)**: Something detected that wasn't in ground truth (over-detection)
- **False Negative (FN)**: Ground truth PII that was missed (under-detection)

### Matching Modes

The evaluation supports three ways to match detected values against ground truth:

| Mode | Description | Example |
|------|-------------|---------|
| `exact` | Exact string match required | `"John Doe"` must match `"John Doe"` |
| `partial` | Substring matching allowed | `"Patient John Doe"` matches `"John Doe"` |
| `fuzzy` | Levenshtein distance matching | `"Jon Doe"` matches `"John Doe"` (similarity ≥ 0.8) |

**Default**: `partial` (recommended, handles contextual captures)

---

## 🗂 Dataset Format

The evaluation uses a JSON dataset with ground truth annotations:

```json
[
  {
    "id": 1,
    "category": "Easy",
    "text": "Dr. Eleanor Vance saw patient John Doe on 2023-10-26...",
    "ground_truth": [
      "Dr. Eleanor Vance",
      "John Doe",
      "2023-10-26",
      "123 Main St",
      "Anytown",
      "CA",
      "1985-07-15"
    ]
  }
]
```

### Dataset Categories

| Category | Description |
|----------|-------------|
| `Easy` | Clear, well-formatted PII (names, dates, addresses) |
| `Medium` | Ambiguous entities, context-dependent detection |
| `Hard` | Edge cases, obscured PII, complex multi-entity text |

---

## ⚙️ Configuration Options

Located at the top of `eval/run_eval.py`:

```python
# Path to the golden dataset
DATASET_PATH = "/path/to/golden_dataset.json"

# Results storage
RESULTS_DIR = "eval/results/"
RESULTS_PATH = "eval/results/results.json"

# Matching mode: "exact", "partial", or "fuzzy"
MATCHING_MODE = "partial"

# Fuzzy matching threshold (0.0 to 1.0)
FUZZY_THRESHOLD = 0.8

# Verbose logging (shows per-record details)
VERBOSE = True

# Maximum number of records to evaluate (for quick testing)
MAX_EVALS = 10
```

---

## 🚀 How to Run the Evaluation

### Prerequisites

1. Ensure the local LLM model is configured in `config.yaml`:
   ```yaml
   local_model_path: "/path/to/Anonymizer-0.6B-Q8_0.gguf"
   anonymizer_strategy: "fast"  # or "verify"
   ```

2. Ensure the dataset exists at `DATASET_PATH`

### Run Command

```bash
cd /path/to/project-spect/eval
python run_eval.py
```

### Sample Output

```
🚀 Starting Evaluation...
   Matching Mode: partial
   Strategy: fast
   Verbose: True

📊 Evaluating 330 records...

[Record 1] Category: Easy
  📝 Input: Dr. Eleanor Vance saw patient John Doe...
  🎯 Ground Truth: ['Dr. Eleanor Vance', 'John Doe', '2023-10-26']
  🔍 Found: ['Dr. Eleanor Vance', 'John Doe', '2023-10-26']
  📊 Metrics: P=100.0% R=100.0% F1=100.0%
--------------------------------------------------------------------------------

🏆 Evaluation Complete!
==================================================
Average Precision        98.00%
Average Recall           96.00%
Average F1 Score         96.89%
==================================================
```

---

## 📁 Results Storage

Results are persisted in `eval/results/results.json` with run history:

```json
{
  "runs": [
    {
      "run_id": 1,
      "summary": {
        "timestamp": "2025-12-05T05:00:00",
        "config": {
          "matching_mode": "partial",
          "strategy": "fast",
          "model_path": "/path/to/model.gguf"
        },
        "total_records": 10,
        "overall": {
          "avg_precision": 0.98,
          "avg_recall": 0.96,
          "avg_f1": 0.9689
        },
        "by_category": {
          "Easy": { "count": 10, "avg_f1": 0.9689 }
        }
      },
      "details": [
        {
          "id": 1,
          "category": "Easy",
          "metrics": { "precision": 1.0, "recall": 1.0, "f1": 1.0 },
          "ground_truth": ["John Doe", "2023-10-26"],
          "found": ["John Doe", "2023-10-26"],
          "missed": [],
          "extra": []
        }
      ]
    }
  ]
}
```

---

## 🔍 How the Evaluation Works (Step by Step)

### 1. Initialization
```python
llm = LocalLLM()           # Load the local GGUF model
anonymizer = Anonymizer(llm)  # Initialize with the LLM
dataset = load_dataset()   # Load ground truth JSON
```

### 2. Per-Record Evaluation Loop
```python
for record in dataset[:MAX_EVALS]:
    # Reset anonymizer state for independent evaluation
    anonymizer.entity_map = {}
    
    # Run anonymization
    sanitized_text, entity_map = anonymizer.anonymize(record["text"])
    
    # entity_map = {"John Doe": "Marcus", "2023-10-26": "2024-01-15"}
    # Compare entity_map.keys() against record["ground_truth"]
    
    metrics = calculate_metrics(record["ground_truth"], entity_map)
```

### 3. Matching Logic
```python
def check_match(truth, found_values, mode="partial"):
    # For each ground truth value, check if it matches any found value
    # Partial mode: "John" matches "Patient John" (substring)
    # This handles cases where the model captures extra context
```

### 4. Metrics Calculation
```python
def calculate_metrics(ground_truth, entity_map):
    found_values = set(entity_map.keys())
    
    # Count true positives (ground truth items that were found)
    for truth in ground_truth:
        if check_match(truth, found_values):
            true_positives += 1
    
    precision = min(1.0, TP / len(found_values))
    recall = min(1.0, TP / len(ground_truth))
    f1 = 2 * (P * R) / (P + R)
```

### 5. Aggregation & Reporting
- Per-record metrics are averaged
- Results are grouped by category
- Worst performers are highlighted for debugging
- All data is saved to JSON for historical comparison

---

## 🐛 Common Issues & Debugging

### Issue: Missed Emails/Phones
**Symptom**: `❌ Missed: ['david.lee@email.com', '(555) 123-4567']`
**Cause**: The local LLM doesn't recognize certain PII patterns
**Fix**: Fine-tune the model or add regex pre-processing in the anonymizer

### Issue: Extra Detections
**Symptom**: `➕ Extra: ['62 years old', 'presented at']`
**Cause**: Model is over-aggressive or ground truth is incomplete
**Action**: Decide if these are valid PII (age is arguably PII), update ground truth if needed

### Issue: Precision > 100% (before fix)
**Symptom**: Metrics showing 116%, 200%
**Cause**: Partial matching allowing one found item to match multiple ground truths
**Fix**: Metrics are now capped at 100% (`min(1.0, value)`)

---

## 📈 Extending the Evaluation

### Add New PII Categories
1. Generate new test cases with `eval/generate_dataset.py`
2. Add category field to records
3. The evaluation will automatically group by category

### Compare Model Versions
1. Run evaluation with model A → results saved as run #1
2. Swap model in `config.yaml`
3. Run evaluation with model B → results saved as run #2
4. Compare `runs[0].summary` vs `runs[1].summary`

### Adjust Strictness
- Use `exact` matching for stricter evaluation
- Lower `FUZZY_THRESHOLD` for more lenient fuzzy matching
- Increase `MAX_EVALS` to test on more records

---

## 📚 Related Files

| File | Purpose |
|------|---------|
| `eval/run_eval.py` | Main evaluation script |
| `eval/generate_dataset.py` | Generates synthetic test data using Gemini |
| `eval/results/results.json` | Persisted evaluation history |
| `src/anonymizer.py` | The system being evaluated |
| `config.yaml` | Model and strategy configuration |
| `.proj-context/project_history.md` | Full project history and changelog |

---

## ✅ Quick Reference

```bash
# Run quick test (10 records)
MAX_EVALS=10 python eval/run_eval.py

# Run full evaluation
# Edit MAX_EVALS in run_eval.py to a large number or remove the limit

# Check results
cat eval/results/results.json | jq '.runs[-1].summary'
```

---

*Last updated: 2025-12-05*
