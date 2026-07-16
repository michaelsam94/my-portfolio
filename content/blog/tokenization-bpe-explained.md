---
title: "Tokenization and BPE, Explained"
slug: "tokenization-bpe-explained"
description: "How LLM tokenization works: byte-pair encoding, vocabulary construction, token counting pitfalls, and why the same text costs different tokens across models."
datePublished: "2026-02-07"
dateModified: "2026-02-07"
tags: ["AI", "LLM", "NLP", "Machine Learning"]
keywords: "tokenization, BPE, byte-pair encoding, LLM tokens, tiktoken, tokenizer, vocabulary"
faq:
  - q: "What is a token in the context of large language models?"
    a: "A token is the atomic unit an LLM processes — not necessarily a word, but a chunk of text that the model's vocabulary maps to an integer ID. A token can be a full word ('hello'), a subword ('ing'), a punctuation mark, or even a single byte for rare characters. Models read and generate sequences of these integer IDs, not raw characters. Token count directly determines API cost, context window usage, and latency."
  - q: "How does byte-pair encoding (BPE) build a vocabulary?"
    a: "BPE starts with every individual byte as a token, then iteratively merges the most frequent adjacent pair into a new token. After thousands of merge operations, common words become single tokens, rare words split into subword pieces, and the vocabulary reaches a target size (typically 50k–100k tokens). The result handles any UTF-8 text without unknown-token errors because any byte sequence can be represented, even if inefficiently."
  - q: "Why does the same prompt cost different tokens on different models?"
    a: "Each model family uses a different tokenizer trained on different corpora with different vocabulary sizes and merge rules. GPT-4o's tokenizer splits code differently than Claude's or Llama's. A 500-word prompt might be 650 tokens on one model and 780 on another. You cannot assume word count equals token count, and you cannot port token budgets across models without re-counting with each model's specific tokenizer."
---

I once shipped a RAG pipeline that budgeted 4,000 tokens for retrieved context, counted words instead of tokens, and silently truncated half the documents. Retrieval quality dropped, users complained about missing information, and the bug was invisible in logs because nothing errored — the context just got cut. The root cause was treating "token" as a synonym for "word." It isn't. Understanding tokenization is prerequisite to controlling cost, fitting context windows, and debugging why a model sees your prompt differently than you expect.

## What tokenization actually does

Raw text is a string of Unicode characters. A neural network needs fixed-size integer sequences. Tokenization bridges that gap:

```
"unhappiness" → ["un", "happiness"] → [1234, 5678]
```

The tokenizer maps each chunk to an integer from a fixed vocabulary (typically 32k–128k entries). The model's embedding layer looks up a vector for each integer. Everything downstream — attention, feed-forward layers, output logits — operates on these integer sequences.

Token count matters because:
- **API billing** is per token (input + output)
- **Context windows** are token-limited (128k, 200k, 1M)
- **Latency** scales roughly linearly with token count
- **Memory** in KV cache is proportional to sequence length in tokens

## Byte-pair encoding step by step

BPE is the dominant algorithm for modern LLM tokenizers (GPT, Llama, Mistral). The training process:

1. Start with 256 byte-level tokens (every possible byte value)
2. Count all adjacent token pairs in the training corpus
3. Merge the most frequent pair into a new token
4. Repeat until vocabulary reaches target size (e.g., 50,000 merges → ~50,256 tokens)

After training, tokenizing new text applies the same merges in the same order:

```
Corpus: "low", "lower", "newest", "widest"

Initial: l o w | l o w e r | n e w e s t | w i d e s t

Merge 'e'+'s' → 'es':  l o w | l o w e r | n e w es t | w i d es t
Merge 'es'+'t' → 'est': l o w | l o w e r | n e w est | w i d est
Merge 'l'+'o' → 'lo':   lo w | lo w e r | n e w est | w i d est
...continues until vocabulary is full
```

Common words become single tokens. Rare or novel words decompose into subword pieces. Because the base vocabulary includes all 256 bytes, any UTF-8 string can be tokenized — even emoji, CJK characters, or malformed input — without an `<UNK>` token.

## Counting tokens in practice

Never estimate from word count. Use the model's actual tokenizer:

```python
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o")
text = "def calculate_total(items: list[Item]) -> Decimal:"
tokens = enc.encode(text)
print(len(tokens))        # 15
print(enc.decode(tokens)) # original text, lossless
```

For open models, Hugging Face tokenizers work the same way:

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.1-8B")
tokens = tokenizer.encode("Hello, world!")
print(len(tokens))
```

Build token counting into your pipeline's budget logic. Before sending a prompt, count tokens and truncate or summarize if over budget.

## Where tokenization surprises you

**Code is token-expensive.** Indentation, brackets, and camelCase split into many subword tokens. A 200-line Python file can be 3,000+ tokens. Syntax highlighting doesn't help the tokenizer — it sees raw characters.

**Numbers fragment.** "2026" might be one token or four ('2', '0', '2', '6') depending on the tokenizer and whether that number appeared in training data.

**Whitespace matters.** Leading spaces, newlines, and indentation each consume tokens. A prompt reformatted with extra newlines can cost 5–10% more tokens with identical semantics.

**Non-English text is less efficient.** Tokenizers trained primarily on English corpora split other languages into shorter subword pieces, increasing token count per character. Japanese or Arabic text can cost 2–3x more tokens than equivalent English.

**Special tokens.** Models reserve tokens for `<|endoftext|>`, tool call markers, and system prompt boundaries. These count against your context window but aren't visible in the text.

## BPE variants in production models

| Model family | Tokenizer | Vocab size | Notable trait |
|---|---|---|---|
| GPT-4o | tiktoken (BPE) | ~200k | Efficient on English and code |
| Claude | Custom BPE | ~100k | Strong multilingual |
| Llama 3 | SentencePiece (BPE) | 128k | Byte-fallback for all Unicode |
| Mistral | SentencePiece (BPE) | 32k | Smaller vocab, more subwords |

SentencePiece (used by Llama, Mistral) trains on raw UTF-8 without pre-tokenizing on whitespace, which handles multilingual text more evenly. Tiktoken (OpenAI) uses a regex pre-splitter before BPE, which is why whitespace and punctuation boundaries differ.

## Implications for system design

**Context budgeting.** When designing RAG or agent pipelines, count tokens with the target model's tokenizer before assembly. Reserve headroom for the model's response (typically 1,000–4,000 tokens).

**Cost estimation.** Multiply input token count by the model's input price per token. A prompt that looks "small" in words can be expensive if it's code-heavy or non-English.

**Truncation strategy.** When you must cut, truncate at token boundaries, not character boundaries. Cutting mid-token produces invalid input. Most tokenizer libraries handle this if you decode a token slice rather than slicing the raw string.

**Cross-model portability.** Prompts tuned for one model's token budget will not fit the same way on another. Re-count when switching models.

## Common production mistakes

Teams get tokenization bpe explained wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of tokenization bpe explained fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [OpenAI tiktoken library](https://github.com/openai/tiktoken)
- [Hugging Face tokenizers](https://huggingface.co/docs/tokenizers/)
- [SentencePiece documentation](https://github.com/google/sentencepiece)
- [Neural Machine Translation of Rare Words with Subword Units (Sennrich et al.)](https://arxiv.org/abs/1508.07909)
- [OpenAI tokenizer tool](https://platform.openai.com/tokenizer)
