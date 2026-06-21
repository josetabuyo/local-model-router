"""Benchmark task definitions."""
from dataclasses import dataclass


@dataclass
class Task:
    id: str
    name: str
    prompt: str
    max_tokens: int = 512


TASKS: list[Task] = [
    Task(
        id="reasoning",
        name="Reasoning",
        prompt=(
            "Solve step by step: A store sells apples for $0.75 each and oranges for $1.20 each. "
            "Maria buys 8 apples and 5 oranges. She pays with a $20 bill. "
            "How much change does she receive? Show all arithmetic."
        ),
        max_tokens=300,
    ),
    Task(
        id="coding",
        name="Coding",
        prompt=(
            "Write a Python function `sieve(n)` that returns all prime numbers up to n "
            "using the Sieve of Eratosthenes. Include the function only, no explanation."
        ),
        max_tokens=400,
    ),
    Task(
        id="summarization",
        name="Summarization",
        prompt=(
            "Summarize the following text in exactly 2 sentences:\n\n"
            "Artificial intelligence has transformed industries from healthcare to finance, "
            "enabling machines to perform tasks that once required human intelligence. "
            "Machine learning models, trained on vast datasets, can now diagnose diseases, "
            "detect fraud, translate languages, and generate creative content. "
            "However, these advances also raise important questions about privacy, bias, "
            "job displacement, and the ethical use of automated decision-making systems. "
            "Researchers and policymakers are working to establish guidelines that balance "
            "innovation with responsibility, ensuring AI benefits society broadly."
        ),
        max_tokens=150,
    ),
    Task(
        id="instruction",
        name="Instruction Following",
        prompt=(
            "List exactly 5 capital cities in alphabetical order. "
            "Output ONLY a valid JSON array of strings, nothing else."
        ),
        max_tokens=100,
    ),
    Task(
        id="math",
        name="Math",
        prompt=(
            "Solve: If f(x) = 3x² - 2x + 1, find f'(x) and the value of x where f'(x) = 0. "
            "Then compute f at that x. Show all steps."
        ),
        max_tokens=300,
    ),
    Task(
        id="multilingual",
        name="Multilingual",
        prompt=(
            "Translate the following sentence to French, German, and Japanese. "
            "Output ONLY a JSON object with keys 'fr', 'de', 'ja':\n\n"
            "\"The quick brown fox jumps over the lazy dog.\""
        ),
        max_tokens=150,
    ),
    Task(
        id="code_debug",
        name="Code Debug",
        prompt=(
            "Find and fix the bug in this Python function:\n\n"
            "```python\n"
            "def binary_search(arr, target):\n"
            "    left, right = 0, len(arr)\n"
            "    while left < right:\n"
            "        mid = (left + right) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        elif arr[mid] < target:\n"
            "            left = mid\n"
            "        else:\n"
            "            right = mid\n"
            "    return -1\n"
            "```\n\n"
            "Output ONLY the corrected function, no explanation."
        ),
        max_tokens=250,
    ),
    Task(
        id="context",
        name="Context Window",
        prompt=(
            "Read this conversation and answer the question at the end.\n\n"
            "Alice: I have 3 cats named Luna, Mochi, and Pepper.\n"
            "Bob: How old are they?\n"
            "Alice: Luna is 5, Mochi is 3, and Pepper just turned 1 last Tuesday.\n"
            "Bob: Which one is oldest?\n"
            "Alice: Luna. She was a rescue.\n"
            "Bob: What rescue organization?\n"
            "Alice: Paws & Hearts, based in Austin.\n"
            "Bob: Do any of them get along?\n"
            "Alice: Luna and Mochi are inseparable. Pepper is still adjusting.\n\n"
            "Question: What is the name of the youngest cat, how old is it, "
            "and which rescue organization did the oldest cat come from? "
            "Answer in one sentence."
        ),
        max_tokens=100,
    ),
]
