#!/usr/bin/env python3
"""Query the LLM-Wiki using natural language questions."""

import argparse
import os
import re
import subprocess
import sys

INDEX_FILE = '/home/hbtjm/library/index.md'
LIBRARY_DIR = '/home/hbtjm/library'

def get_default_model():
    """Determine default model - prefer fast, capable model."""
    return 'gemini-2.5-flash'

def find_relevant_files(question, max_files=5):
    """Find files relevant to the question by searching key terms."""
    # Extract key terms from question
    words = re.findall(r'\b[a-zA-Z]{3,}\b', question.lower())
    # Filter common stop words
    stop_words = {'what', 'is', 'are', 'was', 'were', 'the', 'and', 'for', 'that', 'this', 'with', 'from', 'your', 'how', 'when', 'where', 'why', 'about'}
    terms = [w for w in words if w not in stop_words]
    
    if not terms:
        terms = words[:5]  # Use original words if all filtered out
    
    # Find matching files
    matches = []
    for term in terms[:8]:  # Limit search terms
        for root, dirs, files in os.walk(LIBRARY_DIR):
            # Skip .obsidian
            if '.obsidian' in root:
                continue
            for f in files:
                if f.endswith('.md') and f not in ('index.md', 'SCHEMA.md'):
                    path = os.path.join(root, f)
                    try:
                        with open(path, 'r', errors='ignore') as fh:
                            content = fh.read()
                            if term in content.lower():
                                # Score by frequency
                                score = content.lower().count(term)
                                matches.append((path, score, term))
                    except:
                        pass
    
    # Aggregate scores and return top files
    scores = {}
    for path, score, term in matches:
        if path not in scores:
            scores[path] = 0
        scores[path] += score
    
    sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [f[0] for f in sorted_files[:max_files]]

def read_page(path, max_chars=3000):
    """Read a page, truncated to max_chars."""
    try:
        with open(path, 'r', errors='ignore') as f:
            content = f.read()
            # Skip frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    content = parts[2]
            # Truncate
            if len(content) > max_chars:
                content = content[:max_chars] + '\n... [truncated]'
            return content
    except:
        return ''

def build_prompt(question, context_pages):
    """Build prompt with context and question."""
    context_parts = []
    for path in context_pages:
        rel_path = path.replace(LIBRARY_DIR + '/', '')
        content = read_page(path)
        if content:
            context_parts.append(f"## From {rel_path}\n{content}\n")
    
    context = '\n---\n'.join(context_parts)
    
    prompt = f"""You are answering a question about the IT Service Startup wiki. Answer based ONLY on the provided context. If the context doesn't contain relevant information, say so.

## Context from Wiki
{context}

## Question
{question}

## Instructions
- Answer the question using the provided context
- Cite specific wiki pages using their filenames (e.g., "According to concepts/zero-trust-architecture.md...")
- If context is insufficient, clearly state that the wiki doesn't have relevant information
- Keep the answer focused and practical"""

    return prompt

def query_wiki(question, model=None):
    """Execute wiki query using hermes chat."""
    if model is None:
        model = get_default_model()
    
    # Read index for additional context
    index_content = ''
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, 'r', errors='ignore') as f:
            index_content = f.read()
    
    # Find relevant pages
    relevant_files = find_relevant_files(question)
    
    if not relevant_files:
        return "The wiki has no relevant information for this question."
    
    # Build prompt
    prompt = build_prompt(question, relevant_files)
    
    # Invoke hermes chat
    try:
        result = subprocess.run(
            ['hermes', 'chat', '-m', model, '-t', 'terminal,file,web', '-q', prompt],
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.stdout if result.stdout else result.stderr
    except subprocess.TimeoutExpired:
        return "Query timed out."
    except Exception as e:
        return f"Error running query: {e}"

def main():
    parser = argparse.ArgumentParser(description='Query the LLM-Wiki')
    parser.add_argument('--question', required=True, help='Question to answer')
    parser.add_argument('--model', help='Model to use (default: gemini-2.5-flash)')
    
    args = parser.parse_args()
    result = query_wiki(args.question, args.model)
    print(result)

if __name__ == '__main__':
    main()
