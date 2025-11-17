# Django
import hashlib
import re
import time

# Native
from difflib import SequenceMatcher
from urllib.parse import urlparse

import requests
from autoflake import fix_code as autoflake_fix_code

# Third Party
from autoimport import fix_code as autoimport_fix_code
from autopep8 import fix_code as autopep_formatter
from black import Mode as black_mode
from black import format_str as black_formatter
from bs4 import BeautifulSoup
from django.conf import settings
from django.http import JsonResponse
from isort import code as isort_fix_code

# Analyzer-specific personalities (system prompts)
SYSTEM_PROMPTS = {
    "code_writer": ("You write only precise production grade Python code enclosed in triple backticks (```python ... ```). "),
}

# Security keyword gate for the coding path (refuse secure/remediation requests)
SECURITY_TERMS_PATTERN = (
    r"\b("
    r"bandit|dodgy|mypy|semgrep|vulture|"
    r"safe|security|secure|vulnerab\w*|exploit\w*|remediat\w*|mitigat\w*|"
    r"injection|sql\s*injection|sqli|xss|csrf|deserializ\w*|rce|cwe-\d+|cve-\d{4}-\d+|"
    r"sanitize\w*|escape\w*|harden\w*|crypt\w*|hash|authenticat\w*|authoriz\w*"
    r")\b"
)


def perform_brave_search_query(user_question):
    """
    Performs a Brave Search API query from the extracted user's question. From there the search is enhanced with boost
     domains and later filtered by discard domains.
    :param user_question: The extracted user question to perform search on.
    :return: citation block and high-trust result snippets and a combined string summary for summarization input
    """
    brave_url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": settings.BRAVE_API_KEY}

    # Integrate RELEVANT_SECURITY_DOMAINS preferences
    domain_rules = settings.RELEVANT_SECURITY_DOMAINS
    boost_domains = domain_rules.get("boost", [])
    discard_domains = domain_rules.get("discard", [])

    # Build query fragments
    boost_fragment = " OR ".join(f"site:{d}" for d in boost_domains) if boost_domains else ""
    query_base = f"({user_question})"
    if boost_fragment:
        query_base += f" ({boost_fragment})"
    query_base = re.sub(r"[^A-Za-z0-9:/._\-() ]+", " ", query_base).strip()

    # Progressive search variables
    high_trust_results = []
    low_trust_results = []
    iteration = 0
    max_iterations = 3  # don’t exceed 3 Brave calls
    site_count = 10  # items per query
    min_high_trust_needed = 5  # threshold to proceed early

    # Loop until enough high-trust or cutoff
    while iteration < max_iterations and len(high_trust_results) < min_high_trust_needed:
        params = {"q": query_base, "count": site_count, "offset": iteration * site_count}
        brave_resp = requests.get(brave_url, headers=headers, params=params, timeout=10)
        iteration += 1

        if brave_resp.status_code != 200:
            print(f"Brave API request failed at iteration {iteration} with {brave_resp.status_code}")
            break

        data = brave_resp.json()
        new_items = data.get("web", {}).get("results", [])
        if not new_items:
            break

        for item in new_items:
            title = (item.get("title") or "").strip()
            desc = (item.get("description") or "").strip()
            url = (item.get("url") or item.get("link") or "").strip()
            if not (title or desc):
                continue

            title = re.sub(r"\s+", " ", title)
            desc = re.sub(r"\s+", " ", desc)

            # Discard domain filtering
            for domain in discard_domains:
                if domain in url:
                    print(url)
                    continue

            # Tag high vs low trust
            tag = "[HIGH TRUST] " if any(domain in url for domain in boost_domains) else "[LOW TRUST] "
            snippet = f"Title: {title}; Hyperlink: ({url}); Description: {desc}"

            # Store appropriately
            if tag.startswith("[HIGH"):
                high_trust_results.append(snippet)
            else:
                low_trust_results.append(snippet)

        # Avoid hammering API
        time.sleep(1.0)

    # Combine — favor high trust, but backfill with low trust if needed
    results = high_trust_results
    if len(results) < min_high_trust_needed:
        results += low_trust_results[: (min_high_trust_needed - len(results))]

    # Deduplicate using (normalized_url + stripped_text_hash)
    seen_keys = set()
    deduped_results = []
    citation_list = []
    counter = 1

    for snippet in results:
        url = normalize_url(snippet)
        content_hash = hash_snippet_content(snippet)
        key = f"{url}_{content_hash}"
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_results.append(snippet)

            # Safely split and keep only the 2nd and 3rd parts
            parts = snippet.split(";")
            cut_parts = [p.strip() for p in parts[1:3]] if len(parts) >= 3 else parts[1:]
            cut_snippet = "; ".join(cut_parts)

            citation_list.append(
                f"  {counter}. {cut_snippet}".replace("Title:", "").replace("Hyperlink:", ""),
            )
            counter += 1

    results = deduped_results

    # Prepare summarizer input
    top_snippets = results[:min_high_trust_needed]
    formatted_snippet_block = "\n".join(top_snippets) or "No results found."

    # Remove html
    formatted_snippet_block = BeautifulSoup(formatted_snippet_block, "html.parser").get_text().strip()

    # Normalize encoding artifacts and apostrophes
    formatted_snippet_block = formatted_snippet_block.encode("utf-8", "ignore").decode("utf-8")
    formatted_snippet_block = re.sub(r"[’‘´`]", "'", formatted_snippet_block)  # apostrophes
    formatted_snippet_block = re.sub(r"[^ -~]", " ", formatted_snippet_block)  # remove non-ASCII safely
    formatted_snippet_block = re.sub(r"\s{2,}", " ", formatted_snippet_block).strip()  # spacing

    top_citations = citation_list[:min_high_trust_needed]
    citation_block = "\n".join(top_citations) or "No sources found."

    return citation_block, formatted_snippet_block


def process_streamed_output(response):
    """
    Processes the streamed output chunk by chunk (supports llama_cpp format).
    """
    complete_output = ""
    for chunk in response:
        choice = chunk.get("choices", [{}])[0]
        content = choice.get("text", "") or choice.get("delta", {}).get("content", "")
        complete_output += content

    return complete_output


def dedupe_paragraphs(summary: str, similarity_threshold: float = 0.9) -> str:
    """
    An annoying occurrence of duplicating paragraphs from a llm is mitigated by the code below
    :param summary:
    :param similarity_threshold: float between 0 and 1; higher = stricter deduping
    :return:
    """
    summary_lines = [p.strip() for p in summary.split("\n\n") if p.strip()]
    if len(summary_lines) <= 1:
        return summary.strip()

    deduped = []
    for line in summary_lines:
        normalized = re.sub(r"\s+", " ", line.lower()).strip()
        if not normalized:
            continue

        is_duplicate = any(
            SequenceMatcher(
                None,
                normalized,
                re.sub(r"\s+", " ", d.lower()).strip(),
            ).ratio()
            > similarity_threshold
            for d in deduped
        )
        if not is_duplicate:
            deduped.append(line.strip())

    return "\n\n".join(deduped)


# Calculate the maximum new tokens allowed for the llm
def get_max_new_token_usage(llm, prompt, context_window):
    #  Compute prompt token usage
    prompt_tokens = len(llm.tokenize(prompt.encode("utf-8")))

    # Decide a safe max_new_tokens based on window
    safe_headroom = 16
    max_new_tokens = min(512, max(64, context_window - prompt_tokens - safe_headroom))

    # Too many tokens — tell user to refresh
    if prompt_tokens >= context_window:
        return JsonResponse(
            {
                "response": ("⚠️ Context limit reached — please refresh this page to start a new chat."),
                "usage": {
                    "context_window": context_window,
                    "prompt_tokens": prompt_tokens,
                    "total_tokens": prompt_tokens,
                    "pct_used": 100.0,
                },
            },
            status=200,
        )
    else:
        return prompt_tokens, max_new_tokens


# Extract and normalize URL from a search snippet.
def normalize_url(snippet: str) -> str:
    match = re.search(r'\((https?://[^\\)]+)\)', snippet)
    if not match:
        return ""
    parsed = urlparse(match.group(1))
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


# Strip HTML tags to normalize the textual content.
def strip_html(text: str) -> str:
    return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)


# Compute hash of snippet after stripping HTML.
def hash_snippet_content(snippet: str) -> str:
    text = strip_html(snippet.strip())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Create and return summary prompt
def build_summary_prompt(user_question, formatted_snippet_block):
    summary_prompt = (
        "You are only to formulate a short Response to the question from the given source material. "
        "If the question is in regards to a specific tool or library tune your Response to directly address only the "
        "tool or library in question. "
        "If the question is about common patterns in a specific tool your Response should be a single sentence listing "
        "out all the common patterns to said tool. "
        "Remove all source material from the Response. "
        "Remove all code from the Response. "
        "Remove all blog text. "
        "No clarification of the Response. "
        f"User question:\n{user_question}\n\n"
        f"Source Material:\n{formatted_snippet_block}\n\n"
        "Response:"
    )

    return summary_prompt


# Clean summary via regexes and
def clean_and_build_summary(summary, citation_block, formatted_snippet_block):
    # Clean up any bracketed trust markers or redundancies
    #  Clean up any bracketed trust markers or redundancies
    summary = re.sub(r"\[(HIGH|LOW)\s+TRUST\\]\s*", "", summary)

    #  Remove hyperlinks like <https://...> or (https://...)
    summary = re.sub(r"<https?://[^>]+>", "", summary)  # removes <https://...>
    summary = re.sub(r"\(https?://[^)]+\)", "", summary)  # removes (https://...)
    summary = re.sub(r"http[s]?://\S+", "", summary)  # fallback for bare URLs

    #  Normalize paragraph spacing
    summary = re.sub(r"\s*[/\[\]]\s*", " ", summary)  # remove stray [/], [ ] markers
    summary = re.sub(r"\n{2,}", "\n\n", summary)  # collapse multiple blank lines
    summary = re.sub(r"\s{2,}", " ", summary)  # collapse double spaces
    summary = re.sub(
        r"(?<=[.!?])\s+(?=[A-Z])",
        "\n\n",
        summary,
    )  # add newline after sentences that start new ideas
    summary = summary.strip()

    # Semantically similar deduping of paragraphs that the prompt misses
    summary = dedupe_paragraphs(summary)

    # Get rid of excessive periods from the above edits
    summary = re.sub(r'\.{2,}', '.', summary)

    # Get rid of the annoying Here is... and all its variants...but only if there are other answers prior
    summary = re.sub(r'(?is)^[ \t]*here(?:\'s|\s+is)\b.*?:\s*(?=\S)', '', summary, count=1).strip()

    # Add the citations to the summary
    summary += "\n\nSource(s):\n" + citation_block

    # If no snippets or the model hallucinated an unsupported answer, replace with fallback
    if "no results found" in formatted_snippet_block.lower() or "no sources found" in summary.lower() or not summary.strip():
        summary = "I could not find any reliable sources to answer your question.\n\n" "Source(s): No sources found."

    clean_result = summary

    return clean_result


# Summary persona cleaned response
def get_cleaned_summary_response(llm, user_question):
    # Perform search query and retrieve top snippets
    citation_block, formatted_snippet_block = perform_brave_search_query(user_question)

    # Strong factual summarizer prompt (revised)
    max_new_tokens = 360

    prompt = build_summary_prompt(user_question, formatted_snippet_block)

    response = llm.create_completion(
        prompt=prompt,  # input text
        max_tokens=max_new_tokens,  # max output length
        temperature=0.0,  # creativity
        top_p=0.9,  # nucleus filter
        top_k=30,  # token shortlist
        frequency_penalty=1.2,  # less word reuse
        repeat_penalty=1.6,  # less repetition
        stop=["<|END_OF_RESPONSE|>", "INST"],  # stop tokens
    )["choices"][0][
        "text"
    ].strip()  # grab and trim final text

    prompt_tokens = len(llm.tokenize(response.encode("utf-8")))

    cleaned_response = clean_and_build_summary(response, citation_block, formatted_snippet_block)

    return cleaned_response, prompt_tokens, max_new_tokens


# Code cleanup operations
def code_cleanup_operations(raw_extracted_result):
    # Add missing import statements
    added_missing_imports = autoimport_fix_code(raw_extracted_result)

    # Fix up import statements (dedup and sort)
    organized_imports = isort_fix_code(added_missing_imports)

    # Remove unused imports and variables
    unflaked_code = autoflake_fix_code(
        organized_imports,
        remove_all_unused_imports=True,
        remove_unused_variables=True,
    )

    # Formatters
    formatted_code_stage_autopep8 = autopep_formatter(unflaked_code)
    formatted_code_stage_black = black_formatter(formatted_code_stage_autopep8, mode=black_mode())
    cleaned_response = formatted_code_stage_black

    return cleaned_response


# Code persona cleaned response
def get_cleaned_code_response(llm, user_question):
    # Normalize analyzer key and safely resolve a system prompt
    system_prompt = SYSTEM_PROMPTS["code_writer"]

    # Rebuild full_prompt with explicit instruction boundary
    full_prompt = (
        "Use the following context for reference only and do NOT summarize or repeat it unless it directly"
        " answers the user's question.\n\n"
        f"{system_prompt}\n\n"
        f"User: {user_question}\n"
        f"Assistant:\n```python\n"
    )

    # Coding allowance
    max_new_tokens = 1024

    # Default LLM path (Pathway 2 --> code remediation)
    response = llm.create_completion(
        prompt=full_prompt,
        temperature=0.0,  # creativity level
        top_p=0.95,  # probability cutoff for choices
        top_k=50,  # consider top 50 words
        repeat_penalty=1.05,  # discourage repeated text
        frequency_penalty=0.0,  # no penalty for repetition
        stop=["```", "<|END_OF_RESPONSE|>"],
        max_tokens=max_new_tokens,
    )["choices"][0][
        "text"
    ].strip()  # grab and trim final text

    prompt_tokens = len(llm.tokenize(response.encode("utf-8")))

    cleaned_response = code_cleanup_operations(response)

    return cleaned_response, prompt_tokens, max_new_tokens
