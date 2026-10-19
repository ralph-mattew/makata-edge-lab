#!/usr/bin/env python3
"""PoC 011: Prepare contextual chunk texts (doc-only and doc+section variants).

Usage: python3 prep-contexts.py POC007_RAW_DIR OUTPUT_DIR

Reads PoC 007's chunks-index.jsonl and contracts, extracts section headers,
and creates contextual chunk texts in two variants:
- doc-only: "Document: {title}. Chunk: {text}"
- doc-section: "Document: {title}. Section: {header}. Chunk: {text}"

Outputs:
- chunks-contextual-doc.jsonl: doc-only variant
- chunks-contextual-full.jsonl: doc+section variant
- chunk-context-map.jsonl: metadata (section headers, validation)
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

# Section header patterns
SECTION_NUM = re.compile(r'^\s*(\d+\.?\d*\.?)\s+(.{4,})', re.MULTILINE)  # e.g., "5. TERMINATION", "12.3 Payment"
SECTION_CAPS = re.compile(r'^\s*([A-Z][A-Z\s]{3,})\s*$', re.MULTILINE)  # e.g., "TERMINATION AND RENEWAL"


def clean_title(filename):
    """Convert contract filename to human-readable title."""
    # Remove .txt extension
    title = filename.replace('.txt', '')
    # Replace underscores with spaces
    title = title.replace('_', ' ')
    # Add spaces around digits (e.g., "03142018" -> "03 14 2018")
    title = re.sub(r'(\d{2})(\d{2})(\d{4})', r'\1-\2-\3', title)
    return title.strip()


def extract_sections(contract_text):
    """Extract section headers from contract text.

    Returns: list of (line_number, header_text) tuples
    """
    sections = []
    lines = contract_text.split('\n')

    for i, line in enumerate(lines):
        # Pattern 1: Numbered sections (e.g., "5. TERMINATION")
        match = SECTION_NUM.match(line)
        if match:
            num, title = match.groups()
            header = f"{num.strip()} {title.strip()}"
            if len(header) <= 80:  # Reasonable header length
                sections.append((i, header))
                continue

        # Pattern 2: All-caps sections (e.g., "TERMINATION")
        match = SECTION_CAPS.match(line)
        if match:
            header = match.group(1).strip()
            if 4 <= len(header) <= 80:  # Between 4 and 80 chars
                sections.append((i, header))

    return sections


def find_nearest_section(chunk_start_line, sections):
    """Find the nearest section header before a chunk.

    Args:
        chunk_start_line: Approximate line number where chunk starts
        sections: List of (line_number, header_text) tuples

    Returns: header_text or "Document body" if no section found
    """
    if not sections:
        return "Document body"

    # Find the last section before the chunk
    nearest = None
    for line_num, header in sections:
        if line_num <= chunk_start_line:
            nearest = header
        else:
            break  # Sections are sorted, so we can stop

    return nearest if nearest else "Document body"


def estimate_chunk_line(chunk_range, total_words, total_lines):
    """Estimate line number from word range.

    Rough approximation: linearly map word position to line number.
    """
    word_start, _, _ = chunk_range
    if total_words == 0:
        return 0
    return int((word_start / total_words) * total_lines)


def read_contracts(cuad_dir):
    """Read CUAD contract texts.

    Returns: dict of {contract_name: text}
    """
    contracts = {}
    cuad_path = Path(cuad_dir)

    # CUAD contracts are in the zip, extract if needed
    if not cuad_path.exists():
        print(f"Error: {cuad_dir} not found")
        sys.exit(1)

    # Read .txt files
    for txt_file in cuad_path.glob('*.txt'):
        with open(txt_file, encoding='utf-8') as f:
            contracts[txt_file.stem] = f.read()

    return contracts


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 prep-contexts.py POC007_RAW_DIR OUTPUT_DIR")
        sys.exit(1)

    poc007_raw = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read PoC 007 chunk index
    print("Reading PoC 007 chunk index...")
    with open(poc007_raw / 'chunks-index.jsonl', encoding='utf-8') as f:
        chunk_indices = [json.loads(line) for line in f]

    # Read chunk texts
    print("Reading chunk texts...")
    chunk_texts = {}
    with open(poc007_raw / 'chunks.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            contract = data['contract']
            for i, chunk in enumerate(data['chunks']):
                # Combine overlap and own text (as PoC 007 does)
                text = (chunk.get('overlap', '') + ' ' + chunk['own']).strip()
                chunk_texts[f"{contract}_{i}"] = {
                    'contract': contract,
                    'chunk_id': i,
                    'text': text,
                    'page': chunk.get('page', 1)
                }

    print(f"Loaded {len(chunk_texts)} chunks from {len(chunk_indices)} contracts")

    # Read contracts for section extraction
    print("Reading contracts for section extraction...")
    # Note: chunks.jsonl has the text, we can extract from there
    contract_texts = {}
    with open(poc007_raw / 'contracts.jsonl', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            contract_texts[data['contract']] = '\n'.join(data['pages'])

    # Extract sections from each contract
    print("Extracting section headers...")
    contract_sections = {}
    section_stats = {'total_contracts': 0, 'with_sections': 0, 'total_sections': 0}

    for contract, text in contract_texts.items():
        sections = extract_sections(text)
        contract_sections[contract] = sections
        section_stats['total_contracts'] += 1
        if sections:
            section_stats['with_sections'] += 1
            section_stats['total_sections'] += len(sections)

    print(f"Section extraction stats:")
    print(f"  Contracts with sections: {section_stats['with_sections']}/{section_stats['total_contracts']}")
    print(f"  Total sections found: {section_stats['total_sections']}")
    print(f"  Average sections per contract: {section_stats['total_sections']/section_stats['total_contracts']:.1f}")

    # Build contextual chunks
    print("\nBuilding contextual chunk variants...")
    chunks_doc_only = []
    chunks_full = []
    context_map = []

    for contract_data in chunk_indices:
        contract = contract_data['contract']
        total_words = contract_data['words']
        total_lines = len(contract_texts.get(contract, '').split('\n'))
        sections = contract_sections.get(contract, [])
        doc_title = clean_title(contract)

        for chunk_id, chunk_range in enumerate(contract_data['chunks']):
            chunk_key = f"{contract}_{chunk_id}"
            if chunk_key not in chunk_texts:
                continue

            chunk_info = chunk_texts[chunk_key]
            chunk_text = chunk_info['text']

            # Estimate chunk position for section matching
            chunk_line = estimate_chunk_line(chunk_range, total_words, total_lines)
            section_header = find_nearest_section(chunk_line, sections)

            # Build contextual texts
            doc_only_text = f"Document: {doc_title}. Chunk: {chunk_text}"
            full_text = f"Document: {doc_title}. Section: {section_header}. Chunk: {chunk_text}"

            chunks_doc_only.append({
                'chunk_id': chunk_key,
                'contract': contract,
                'text': doc_only_text,
                'original_text': chunk_text
            })

            chunks_full.append({
                'chunk_id': chunk_key,
                'contract': contract,
                'text': full_text,
                'original_text': chunk_text
            })

            context_map.append({
                'chunk_id': chunk_key,
                'contract': contract,
                'doc_title': doc_title,
                'section_header': section_header,
                'chunk_line_est': chunk_line,
                'original_length': len(chunk_text.split()),
                'doc_only_length': len(doc_only_text.split()),
                'full_length': len(full_text.split())
            })

    # Write outputs
    print(f"\nWriting outputs to {output_dir}/")

    with open(output_dir / 'chunks-contextual-doc.jsonl', 'w', encoding='utf-8') as f:
        for chunk in chunks_doc_only:
            f.write(json.dumps(chunk) + '\n')

    with open(output_dir / 'chunks-contextual-full.jsonl', 'w', encoding='utf-8') as f:
        for chunk in chunks_full:
            f.write(json.dumps(chunk) + '\n')

    with open(output_dir / 'chunk-context-map.jsonl', 'w', encoding='utf-8') as f:
        for entry in context_map:
            f.write(json.dumps(entry) + '\n')

    # Print statistics
    print(f"\nContextual chunk statistics:")
    print(f"  Total chunks: {len(context_map)}")

    avg_orig = sum(c['original_length'] for c in context_map) / len(context_map)
    avg_doc = sum(c['doc_only_length'] for c in context_map) / len(context_map)
    avg_full = sum(c['full_length'] for c in context_map) / len(context_map)

    print(f"  Average chunk length (words):")
    print(f"    Original: {avg_orig:.1f}")
    print(f"    Doc-only: {avg_doc:.1f} ({avg_doc/avg_orig:.2f}x)")
    print(f"    Full: {avg_full:.1f} ({avg_full/avg_orig:.2f}x)")

    # Sample for validation
    print(f"\nSample chunks (for manual validation):")
    import random
    random.seed(42)
    samples = random.sample(context_map, min(5, len(context_map)))

    for i, s in enumerate(samples, 1):
        print(f"\n  Sample {i}: {s['chunk_id']}")
        print(f"    Document: {s['doc_title']}")
        print(f"    Section: {s['section_header']}")
        print(f"    Original length: {s['original_length']} words")
        print(f"    Full length: {s['full_length']} words")

    print(f"\n✓ Done! Contextual chunks ready for embedding.")


if __name__ == '__main__':
    main()
