# A Data Mixture and Curriculum Specification for a 40-Billion-Parameter India-First Language Model

**ERA V5 · Session 5 — Data Mixtures and Curriculum**<br>
**Document type:** Technical design specification.

---

## 1. Introduction

The same corpus and the same compute budget can produce materially different models depending on how the data is proportioned and ordered. The mixture is therefore a primary design decision rather than a bookkeeping detail.

The model has three target capabilities:

1. **Agentic coding.** The model should decompose a long task, issue tool calls across multiple steps, read intermediate results, recover from failed calls, and maintain the growing task history in context.
2. **Controllable-effort reasoning.** The model should answer simple questions briefly and expend proportionally greater effort on difficult ones, under an explicit effort setting.
3. **Native Indic fluency.** The model should understand and generate Indic languages natively. This is the differentiating capability and the primary motivation for the project.

This report makes four contributions: (i) a benchmark-driven method for sizing each capability lane (Section 3); (ii) a main-run and annealing mixture in which every lane is reconciled against its measured, published supply (Section 4); (iii) a concrete, stage-by-stage curriculum, including a protected selection floor and an annealing reserve (Section 5); and (iv) a validation protocol that reduces every proportion to a testable hypothesis (Section 6). No value in this document is treated as final prior to proxy-scale validation.

**Sourcing policy.** Every quantity in this report is either (a) a *measured or published figure* with a citation — the author's own Session 2–4 results, the ERA V4 course material, or a public dataset whose statistics are drawn from its dataset card or paper — or (b) an explicitly labelled *design allocation* proposed by the author and subject to the validation protocol of Section 6. Design allocations are never presented as sourced facts, and no lane is assigned a share exceeding its real supply without an explicit repetition (epoch) or synthesis statement.

---

## 2. Background and prior work

The present specification is the fourth step in a sequence, and its numbers depend on the tokenizer, the data ceilings, and the cleaned shards established earlier.

### 2.1 Tokenizer (Session 2)

A multilingual vocabulary of approximately 278,000 tokens with an Indic-aware pre-tokenizer was trained, and its per-language fertility was measured. All token counts in this document are expressed in that tokenizer. The dependency is arithmetic: training time is consumed in proportion to token counts rather than sample counts, so a fixed tokenizer is a precondition for an accurate budget.

### 2.2 Data strategy and the Indic-supply constraint (Session 3)

Session 3 examined the data required for a 40 B, India-first, Gemma-4-class model. Its principal conclusions carried forward here are: a scale of approximately 5.0 T pretraining tokens (100–150 tokens per parameter) across all 22 scheduled languages; a fertility-driven vocabulary allocation of approximately 278 K tokens; and an evaluation design that both targets published reference scores (MMLU-Pro 85.2, AIME 89.2, LiveCodeBench 80.0, GPQA 84.3) and adds India-first benchmarks — native-language sets and a purpose-built Indian competitive-examination suite (IIT-JEE, NEET, UPSC, UGC-NET, banking) — chosen because such examinations cannot be answered well from a predominantly Western knowledge distribution and therefore measure the differential the objective is intended to produce.

Session 3's central finding was that the India-first objective is constrained by the availability of *verified* data rather than by the mixture percentage chosen, and it estimated approximately 410 B *usable* Indic tokens (about 8 % of a 5 T budget) by expanding the verified base. The present report replaces that estimate with the measured public supply (Section 4.0): the genuinely verified native supply is approximately **64–78 B unique tokens**. At the four-epoch repetition limit this supports roughly 6 % of the budget as verified-effective tokens, which is why the Indic lane is sized to a native-majority 12 % (Section 4.2) rather than to the 20 % original aspiration.

To raise the verified ceiling over time, Session 3 identified a freely usable, legally clean acquisition tier — the Press Information Bureau (14 languages), the All India Radio and Doordarshan archives (opened to reuse in 2025), and court judgments and legislative debates (reproduction non-infringing under §52(1)(q)(iv) of the Copyright Act 1957) — because these government sources cover the languages for which verified data is scarcest. These are the collection targets of Section 7; they are not yet counted in the supply of Section 4.

### 2.3 Cleaning and deduplication (Session 4)

Session 4 implemented and executed an eight-stage cleaning pipeline — extract, normalize, language identification, quality filtering, deduplication, PII scrubbing, decontamination, and manifesting — and reported its yield on two contrasting English web sources without inflating the survival rate. The figures in Table 1 are measured on the author's own corpus.

**Table 1.** Measured cleaning yield on two contrasting sources (Session 4).

| Source | Role | Documents (raw → clean) | Tokens (raw → clean) | Survival | Observations |
|---|---|---:|---:|---:|---|
| CC-News (raw web news) | Deduplication and PII test case | 20,000 → **15,338** | 9.46 M → **7.88 M** | ≈ 77 % | 2,247 near-duplicates removed across 1,684 clusters (largest cluster: 68 reposts of one boilerplate page); PII scrubbing redacted 110,746 names, 3,248 phone numbers, 2,592 URLs, 954 email addresses, and 103 card numbers |
| FineWeb (pre-cleaned) | Baseline for honest reporting | 20,000 → **19,494** | 12.51 M → **12.26 M** | ≈ 97 % | An already-deduplicated corpus is expected to lose few documents; the result is reported as measured rather than inflated |

Two design decisions from Session 4 feed directly into the present specification. First, **per-script quality classifiers rather than a single English filter**: a monolingual English quality filter was the mechanism that removed Indic text in the V4 run, so the pipeline instead preserves genuine Brahmic joiners (ZWNJ and ZWJ) while removing zero-width noise. Second, **provenance and determinism by construction**: each shard records its source, license, script hashes, a SHA-256 content hash, and token and language counts, and a re-run reproduces an identical shard hash. This allows every lane in the mixture below to be audited back to a stamped, licensed origin, and it is where the licensing of each source in Section 4.0 is recorded.

Session 4 also began populating the books and long-context lanes with public-domain material: approximately 300 British Library non-fiction volumes (1800–1899, about 28.7 M words) and 299 Internet Archive Indian-authored non-fiction volumes (36 distinct authors, about 19.9 M words).

---

## 3. Methodology

### 3.1 Composing backward from benchmarks

A capability that is not measured cannot be demonstrated. Each lane is therefore justified by a named benchmark, and each benchmark is analyzed at the level of which token receives a learning signal, because the position of the learning signal — not the benchmark's name — determines the required training-data shape.

**Table 2.** Mapping from target benchmarks to required training-data shape and learning signal.

| Benchmark | Group | Quantity scored | Required data shape | Learning signal |
|---|---|---|---|---|
| SWE-bench (Verified/Lite) | Agentic coding | Patch that makes the repository's tests pass | Issue and repository context → diff/patch | Loss on the generated patch only |
| τ-bench | Agentic | Multi-turn tool use under a policy | Full trajectory (plan → call → recovery → answer) | Loss on model turns; tool observations receive no loss |
| BFCL | Tool use | Correct function name and arguments | Prompt → function call / JSON | Loss on the emitted call |
| GAIA | Agentic | Multi-step research | Long trajectory containing dead ends | Loss on model steps only |
| HumanEval / MBPP | Coding | Function synthesis from a docstring | Docstring → code | Loss on generated code |
| LiveCodeBench | Coding | Recent, uncontaminated problems | Problem → solution and tests | Loss on the solution |
| GSM8K | Reasoning | Grade-school word problems | Short chain-of-thought | Loss on chain-of-thought and answer |
| MATH | Reasoning | Competition mathematics | Medium/long chain-of-thought | Loss on chain-of-thought and answer |
| AIME | Reasoning | Olympiad mathematics | Long chain-of-thought with self-check | Reward on the final answer (RLVR) |
| GPQA-Diamond | Reasoning | Graduate-level science | Long chain-of-thought | Loss on chain-of-thought / RLVR |
| MMLU / MMLU-Pro | Knowledge | Broad world knowledge | General web and curated text | Next-token (pretraining) |
| MILU / IndicMMLU | Indic | Indic knowledge and reasoning | Verified native and translated text | Next-token / SFT |
| IndicGenBench | Indic | Indic generation (QA, summarization, MT) | Native and parallel text | Loss on the generation |

The learning-signal column is the determining factor: applying loss to a tool observation would train the model to fabricate tool results instead of invoking the tool. This constraint is why the agentic lane is costly (Section 4.3) and why reasoning depth is installed after pretraining rather than during it (Sections 4.4 and 5).

### 3.2 Token budget and supply discipline

The budget is 5.0 T tokens (40 B × 125). It is deliberately not larger: the abundant lanes (general web and code) could supply more, but the capabilities that motivate the project — verified Indic text, genuine agentic trajectories, and long reasoning traces — do not exist at multi-trillion scale, so the budget is governed by scarce supply, not abundant supply.

Two rules maintain the integrity of the accounting. First, the **repetition rule**: consistent with the data-constrained scaling result of [Muennighoff et al. (2023)](https://arxiv.org/abs/2305.16264), up to approximately four epochs of a scarce pool are roughly as valuable as an equivalent quantity of unique tokens, and marginal value declines sharply beyond that point; any lane whose allocation exceeds four epochs of its unique data must close the gap through synthesis, stated explicitly. Second, **supply is stated for every lane**, using the measured figures of Section 4.0, so that no lane receives a large share unsupported by real data.

The budget divides into a **main pretraining phase of 4.6 T tokens (92 %)** and a **final annealing phase of 0.4 T tokens (8 %)** with a distinct mixture. Post-training — supervised fine-tuning (approximately 10–20 B tokens), preference optimization (approximately 1–5 B), and reinforcement learning with verifiable rewards (reward-based, no fixed token target) — lies outside the 5 T budget and consumes the reserves of Section 4.4.

---

## 4. Data mixture specification

### 4.0 Verified data inventory

Every supply figure used below is drawn from the dataset's own card or paper. Sizes are approximate as published and, per Section 2.3, must be re-measured in the Session-2 tokenizer against the team's provenance-stamped shards before the run; licensing for each source is recorded in the Session-4 manifests.

**Table 3.** Verified data inventory. Published sizes, with sources.

| Dataset | Lane | Published size | Reference |
|---|---|---|---|
| FineWeb / FineWeb-Edu | General web | 15 T / 1.3 T tokens | [HF](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu); Penedo et al. 2024, [arXiv:2406.17557](https://arxiv.org/abs/2406.17557) |
| DCLM-baseline | General web | 4 T tokens | [HF](https://huggingface.co/datasets/mlfoundations/dclm-baseline-1.0) |
| The Stack v2 (dedup) | Code | ≈ 900 B tokens (32.1 TB) | [HF](https://huggingface.co/datasets/bigcode/the-stack-v2-dedup); Lozhkov et al. 2024, [arXiv:2402.19173](https://arxiv.org/abs/2402.19173) |
| FineMath | Mathematics | 54 B tokens (34 B FineMath-3+) | [HF](https://huggingface.co/datasets/HuggingFaceTB/finemath) |
| Proof-Pile-2 | Mathematics | 55 B tokens | [HF](https://huggingface.co/datasets/EleutherAI/proof-pile-2); Azerbayev et al. 2023, [arXiv:2310.10631](https://arxiv.org/abs/2310.10631) |
| OpenWebMath | Mathematics | 14.7 B tokens | [HF](https://huggingface.co/datasets/open-web-math/open-web-math); Paster et al. 2023, [arXiv:2310.06786](https://arxiv.org/abs/2310.06786) |
| Nemotron-CC-Math | Mathematics | 133 B tokens | Nvidia 2025, [arXiv:2508.15096](https://arxiv.org/abs/2508.15096) |
| **Sangraha — Verified** | **Indic (verified)** | **64 B tokens** | [HF](https://huggingface.co/datasets/ai4bharat/sangraha); IndicLLMSuite 2024, [arXiv:2403.06350](https://arxiv.org/abs/2403.06350) |
| **Sangraha — Unverified** | **Indic (unverified)** | **24 B tokens** | same as above |
| **Sangraha — Synthetic** | **Indic (translated/romanized)** | **162 B tokens** | same as above |
| IndicCorp v2 | Indic (verified) | 20.9 B tokens (14.4 B Indic) | [HF](https://huggingface.co/datasets/ai4bharat/IndicCorpV2) |
| IndicTrans2 | Indic (translation engine) | 22-language MT model | Gala et al. 2023, [arXiv:2305.16307](https://arxiv.org/abs/2305.16307) |
| NuminaMath-CoT | Reasoning | 860 K problems with CoT | [HF](https://huggingface.co/datasets/AI-MO/NuminaMath-CoT) |
| OpenThoughts2 | Reasoning | 1 M reasoning samples | [HF](https://huggingface.co/datasets/open-thoughts/OpenThoughts2-1M) |
| xLAM / APIGen | Agentic / tool use | 60 K calls over 3,673 APIs | [HF](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k); APIGen 2024, [arXiv:2406.18518](https://arxiv.org/abs/2406.18518) |

### 4.1 Main pretraining mixture

**Table 4.** Main pretraining mixture (4.6 T tokens). Shares are the author's design allocation; supply figures are from Table 3.

| Lane | Share | Tokens | Unique supply (Table 3) | Supply verdict |
|---|---:|---:|---:|---|
| General web (EN, filtered) | 42 % | 1.93 T | > 5 T (FineWeb-Edu, DCLM, FineWeb) | Subsample, < 1 epoch |
| Code | 22 % | 1.01 T | ≈ 0.9 T (The Stack v2-dedup) | ≈ 1.1 epochs |
| Mathematics & STEM | 11 % | 0.51 T | ≈ 200 B (FineMath, Proof-Pile-2, Nemotron-CC-Math) | ≈ 2.5 epochs |
| Indic (all tiers) | 12 % | 0.55 T | See Section 4.2 | Native-majority; repetition and synthesis stated in 4.2 |
| Curated knowledge | 5 % | 0.23 T | ≈ 50 B (Wikipedia, StackExchange, S4 books) | ≈ 4 epochs |
| Long-context | 4 % | 0.18 T | Constructed (S4 books, arXiv, repo-packed code) | Packing |
| Reasoning seed | 2 % | 0.09 T | Single-digit B unique (NuminaMath, OpenThoughts2) | Mostly distilled; bulk deferred to SFT/RL |
| Agentic seed | 2 % | 0.09 T | ≈ 60 K calls unique (xLAM/APIGen) | Mostly synthetic; Tier-A trajectories reserved for anneal |
| **Total** | 100 % | **4.6 T** | | |

<!--CHART:main-mix-->

Figure 1 presents this allocation ranked by share. General web is the largest lane because it is the most abundant source, not the most valuable; the high-value but scarce lanes are held small in the main run and concentrated in the annealing phase (Section 4.4). Mathematics is repetition-bound at approximately 2.5 epochs once [Nemotron-CC-Math](https://arxiv.org/abs/2508.15096) (133 B) is included alongside FineMath and Proof-Pile-2, and curated knowledge at approximately four epochs. The reasoning and agentic seeds are supply-bound: their genuine unique data is small (single-digit billions of reasoning tokens; 60 K function-calling examples), so their pretraining seed is deliberately small — sufficient to teach the token format — with capability depth installed later (Sections 4.3, 4.4).

### 4.2 Indic tier decomposition

The Indic lane is the differentiating capability and is supply-constrained, so it is decomposed explicitly rather than reported as a single aggregate. The measured supply is: verified native ≈ 64 B ([Sangraha-Verified](https://huggingface.co/datasets/ai4bharat/sangraha)) plus 14.4 B ([IndicCorp v2](https://huggingface.co/datasets/ai4bharat/IndicCorpV2)) ≈ **78 B unique** (conservatively 64–78 B, allowing for overlap); unverified native 24 B (Sangraha-Unverified); and synthetic 162 B (Sangraha-Synthetic — Wikimedia translated to 14 languages and transliterated). The lane is set to 12 % (552 B) so that genuine native text (verified + unverified) forms the majority.

**Table 5.** Indic lane decomposition (552 B main-run tokens). Allocation is the author's design; supply and epochs are computed against Table 3.

| Tier | Allocation | Share of lane | Real unique supply | Repetition / synthesis |
|---|---:|---:|---|---|
| Verified native | 210 B | 38 % | ≈ 78 B (Sangraha-Verified 64 B + IndicCorp v2 14.4 B) | ≈ 2.7 epochs (within limit) |
| Unverified native | 90 B | 16 % | 24 B (Sangraha-Unverified) + noisy multilingual corpora | ≈ 3.8 epochs on the Sangraha portion (flagged) |
| Translated (EN→Indic) | 150 B | 27 % | Drawn first from Sangraha-Synthetic (162 B, real); remainder generated with IndicTrans2 | ≤ 1 epoch on real data, then generation |
| Synthetic / romanized | 102 B | 19 % | Sangraha-Synthetic (romanized subset) + generation | Generation |
| **Total** | 552 B | 100 % | | |

<!--CHART:indic-tiers-->

Figure 2 shows this decomposition alongside the annealing composition. Native text (verified + unverified) is **54 %** of the lane; translated and synthetic data together are capped at 46 %, and most of that non-native portion is drawn from Sangraha's *already-published* 162 B synthetic set rather than from new generation, so the lane rests predominantly on real, existing data. Verified data is repeated at approximately 2.7 epochs, within the four-epoch limit; the unverified tier is the most repetition-strained (approximately 3.8 epochs on the Sangraha portion) and is supplemented by additional multilingual corpora. Pushing the lane to 15 % would force the verified share below one third and make the lane translation- and synthetic-majority, which the measured supply does not justify; the lane is therefore held at 12 %.

Across the main and annealing phases, native Indic is protected by the always-on floor of Section 5.3. Within the lane, the higher-supply languages (Hindi, Bengali, Marathi, Tamil, Telugu) take the largest verified share, while the long tail (Dogri, Maithili, Santali, and others) is protected by a per-language minimum and filled proportionally more by translation and transliteration; the government sources of Section 7 are the route to raising the verified floor for exactly those languages.

### 4.3 Agentic data

A representative agentic task is: identify every U.S. research grant relevant to a project, determine the laboratories that received them, and establish which recipients could plausibly purchase a specific instrument because their funded work requires it. No single tool call answers this. The training example is a trajectory — plan, search, read, follow-up search, a failed call, recovery, a running summary, and a final answer.

The masking rule is an invariant: the user request and every tool observation are context and receive no loss, while only the model's planning, tool calls, and final answer receive loss. A trajectory of approximately 6,000 tokens may contain only about 1,200 supervised tokens. The largest verified open resource is [xLAM/APIGen](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k) (60 K executable function-calling examples over 3,673 APIs); genuine long multi-step trajectories are far scarcer. The seed is therefore small and mostly synthesized with a tool-execution harness, and the most valuable real trajectories are reserved for annealing because they cannot be regenerated once consumed. This lane targets SWE-bench (diff-shaped edit data), BFCL and τ-bench (function-call and full-trajectory data), and GAIA.

### 4.4 Reasoning data and the effort control

The inference-time effort control (low, medium, high, ultra) does not create reasoning; it selects among behaviours the model was trained to produce. The reserved reasoning data is therefore a distribution over trace lengths, delivered short-before-long by the curriculum, drawn from open resources such as [NuminaMath-CoT](https://huggingface.co/datasets/AI-MO/NuminaMath-CoT) (860 K problems) and [OpenThoughts2](https://huggingface.co/datasets/open-thoughts/OpenThoughts2-1M) (1 M samples) and extended by distillation.

**Table 6.** Reasoning-trace length bands, with representative behaviour and examples.

| Band | Thinking budget | Behaviour | Representative example |
|---|---|---|---|
| Low | ≤ 128 tokens | Direct answer, no trace | "12 × 11 → 132." |
| Medium | 128–512 | A few explicit steps | GSM8K: "2 bolts blue + half that white = 2 + 1 = 3." |
| High | 512–2048 | Explores and verifies an intermediate result | MATH L4: derive, check a boundary case, then answer. |
| Ultra | 2048–8192+ | Attempts an approach, encounters a contradiction, backtracks, and verifies numerically | AIME: casework → dead end → generating functions → sanity-check n = 3 → answer. |

The reserve's length distribution is set at **Low 15 %, Medium 25 %, High 40 %, Ultra 20 %**: weighted toward the high band, which is the working depth of most difficult problems, with a deliberate 20 % ultra tail so the model learns to sustain and self-correct long chains, and a 40 % short foundation so it also learns to answer concisely.

<!--CHART:reasoning-bands-->

Figure 3 shows this distribution. The reserve holds all four bands across mathematics, code, and general problem-solving; restricting it to a single domain would tie the effort control to that domain. Depth is installed after the base model exists — through supervised fine-tuning on worked traces and then reinforcement learning with verifiable rewards, in which a checker grades the final answer and no token-level target is required. The reservation decided here is what makes reasoning training feasible in Sessions 17–18.

---

## 5. Curriculum and training schedule

### 5.1 Stage sequence

Order is nearly as consequential as proportion. Difficult material presented before its prerequisites is largely wasted, and a constant mixture forgoes the advantage of learning simple patterns before complex ones. The run therefore proceeds through stages, and within each stage advances along a difficulty ladder.

**Table 7.** Curriculum stages, token spans, mixture direction, and difficulty band.

| Stage | Span | Tokens | Mixture direction | Difficulty |
|---|---|---:|---|---|
| Seed | 0 → 3 % | ~0.15 T | General web and Wikipedia; Indic floor active from step 0 | D1 |
| Foundation | 3 → 50 % | ~2.35 T | The broad mixture of Section 4.1 | D1 → D2 |
| STEM/reasoning ramp | 50 → 80 % | ~1.5 T | Web decreasing; code, mathematics, reasoning increasing | D2 → D3 |
| Long-context | 80 → 92 % | ~0.6 T | Context extended 4k → 32k → 128k; books, repo-level, long CoT | D3 |
| Final anneal | 92 → 100 % | **0.4 T** | Reduced learning rate; reserve preset (Section 5.4) | D3 → D4 |

Difficulty exemplars: D1 — "reverse a string" / "2 + 2"; D2 — MBPP "longest common prefix" / MATH L2; D3 — SWE-bench Django ORM fix / an AIME problem / MATH L5; D4 — GPQA-Diamond / a multi-file API-migration refactor / a research-level proof.

### 5.2 Per-stage mixture

The main-run mixture of Section 4.1 is a token-weighted average; the run does not hold it constant. Each stage reweights the eight lanes: general web decreases monotonically while code, mathematics, reasoning, and long-context increase; Indic is held above its floor and then upsampled; and the scarce lanes remain small until annealing. Values are percentages of each stage's tokens, and the columns sum to 100.

**Table 8.** Per-stage mixture (percentage of each stage's tokens). Stage share of the whole run is shown in the header.

| Lane | Seed · 3 % | Foundation · 47 % | STEM ramp · 30 % | Long-context · 12 % | Anneal · 8 % |
|---|--:|--:|--:|--:|--:|
| General web | 62 | 49 | 30 | 22 | 14 |
| Code | 8 | 22 | 28 | 22 | 18 |
| Mathematics & STEM | 2 | 9 | 16 | 12 | 16 |
| Indic (all tiers) | 8 | 13 | 11 | 10 | 24 |
| Curated knowledge | 18 | 5 | 3 | 2 | 0 |
| Long-context | 0 | 0 | 4 | 24 | 8 |
| Reasoning | 1 | 1 | 4 | 4 | 8 |
| Agentic | 1 | 1 | 4 | 4 | 12 |

<!--CHART:stage-evolution-->

Figure 4 visualizes this schedule. Token-weighted across the four main-run stages (weights 3, 47, 30, 12), the matrix integrates to a main-run mixture of approximately web 40, code 24, mathematics 11, Indic 12, curated 4, long-context 4, reasoning 2, and agentic 2, reproducing the Section 4.1 shares within about two points (the residuals are a target for proxy-scale tuning). Each boundary between columns is a mixture transition and is warmed up gradually, for the stability reason of Section 5.5.

The HTML reading view provides an **interactive version of this schedule**: each stage's lane shares can be adjusted with sliders (which renormalize to 100 %), and a supply panel recomputes, for the whole run, how each lane's token demand compares with the real verified data available in Table 3 — reporting each lane as verified-backed, as requiring *N* epochs of repetition, or as requiring synthesis. It makes the scarcity constraint of Section 4 directly manipulable: raising the Indic or agentic share turns those lanes red as their demand exceeds the real supply.

<!--WIDGET:stage-explorer-->


### 5.3 Protected always-on selection floor

OPUS — the V4 data-selection method, which retained approximately 40 % of candidate batches for an approximately sixfold effective-token gain at a few percent overhead — defines usefulness through a proxy. An English-web proxy structurally undervalues native Indic text and unfamiliar agentic trajectories, and thereby suppresses the target capabilities. A fixed fraction of every batch is therefore reserved outside the selector's control.

**Table 9.** Protected always-on floor. The selector operates on the remaining 90 %.

| Lane | Floor per batch | Rationale |
|---|---:|---|
| Indic (native: verified + unverified) | 8 % | Backed by ≈ 102 B real unique native tokens (Sangraha 64 B + 24 B + IndicCorp v2 14.4 B) at ≤ 3.6 epochs |
| Agentic | 1 % | Scarce and unfamiliar; the selector would otherwise suppress it |
| Reasoning | 1 % | As above |
| **Total protected** | **10 %** | The remaining 90 % is subject to aggressive selection |

The native Indic core is always present and is never judged by the selector, while the translated, synthetic, and additional unverified Indic data is left within the selector's pool so that it is quality-filtered.

### 5.4 Final annealing phase

The final annealing phase is the highest-leverage stage in the plan. Its 0.4 T preset inverts the pretraining mixture: general web falls from about 42 % to 14 %, while the scarce lanes are upsampled — mathematics and reasoning to about 24 % combined, Indic (verified-heavy) to 24 %, agentic to 12 %, code to 18 %, and long-context to 8 %. This is feasible only if the reserve survives the main run, so the following are quarantined from ordinary sampling before step 0 (approximately 150–200 B tokens): a large share of verified Indic, roughly half of all genuine agentic Tier-A trajectories, ultra-length reasoning traces with verified answers, and a set of tested code and competition mathematics. If the selector consumed the best data early, no high-value material would remain for annealing.

### 5.5 Stability under mixture transitions

In the V4 run, a sudden increase in the Hindi share interacting with frozen embeddings raised the gradient norm by approximately 150×, an event capable of destabilizing a run. No mixture change is therefore applied in a single step: each transition is blended over a warm-up band of approximately 20–40 B tokens, embeddings remain unfrozen during Indic ramps, and gradient norm and per-lane loss are monitored at every boundary. The architecture and mixture are frozen before the main run begins.

---

## 6. Validation protocol

No proportion above is adopted at 40 B until it has been evaluated on proxy runs at 1 B (approximately 25 B tokens; stability and loss checks) and 3 B (approximately 60–90 B tokens; benchmark movement), holding proportions fixed and using the Session-2 tokenizer with `lm-eval-harness`, IndicGenBench, and a BFCL/τ-bench harness.

**Table 10.** Validation hypotheses, metrics, and decision rules.

| # | Hypothesis | Metric | Decision rule |
|---|---|---|---|
| H1 | The 8 % native-Indic floor protects Indic performance under selection | MILU, IndicQA, IndicGenBench | Ablate the floor: retain it if Indic falls ≥ 5 points while EN-MMLU stays within 1 point; remove it and reallocate to code if the benefit is < 2 points |
| H2 | The agentic seed improves tool use without fabricated tool outputs | BFCL, τ-bench, tool-observation-emission rate | If the model emits tool-observation tokens, the mask is defective and must be corrected before scaling; if the BFCL gain is < 3 points, reduce the synthetic share |
| H3 | Code at 22 % is the knee of the code-versus-knowledge trade-off | HumanEval/MBPP versus MMLU | Sweep code ∈ {18, 22, 26}% at 1 B and select the knee; raise to 26 % if it still improves HumanEval at ≤ 1 point MMLU cost |
| H4 | A native-majority Indic split (54 % native) exceeds a translation-heavy split on native fluency at equal token count | Held-out native-Indic perplexity and IndicGenBench quality | Increase the (cheaper) translated share if the translation-heavy split matches native fluency; otherwise retain the native-majority split |
| H5 | An easy-to-hard curriculum reaches a target accuracy in fewer tokens than a constant mixture | Tokens-to-threshold on MATH-L3 / GSM8K | Reduce curriculum complexity if the constant mixture matches the curriculum |
| H6 | The 0.4 T anneal on the reserve exceeds a 0.4 T continuation of the broad mixture | SWE-bench-Lite, AIME, MILU, BFCL | Re-curate the reserve if the anneal gain is < 2 points over the broad continuation |

The proxy results, not this document, determine what is retained, changed, or removed. Executing the 1 B code and Indic-floor sweeps (H1 and H3) and reporting the resulting numbers is the immediate next action.

### 6.1 Verification harness and results

A companion script, [`experiments/experiment.py`](experiments/experiment.py) (pure Python standard library, no GPU), makes the plan's checkable claims reproducible. It has three modes.

**`verify`** recomputes every accounting and supply claim from the plan and the cited dataset sizes of Table 3. **Result: 14 / 14 checks pass.** It confirms that the main mixture and all five stage columns sum to 100 %, that the stage matrix integrates to the main mixture within 2.3 points, that the whole-run token demand totals 5.0 T, that the Indic lane is native-majority (54.3 %) with the verified (2.69×) and unverified (3.75×) tiers inside the four-epoch limit, and that the 8 % floor is backed by native supply at 3.6×. Critically, it *recomputes each lane's supply verdict independently and checks it against Table 4*; this is what established that the Indic lane's aggregate verdict is repetition of real data (2.4× of the 264 B real pool), not synthesis — only the ~18 % romanized tier is newly generated.

**`repetition`** is a trained-to-convergence linear-model experiment demonstrating the mechanism behind the supply discipline. Repeating a fixed 150-token pool converges to a flat held-out error (1.33) no matter how many passes, while the same budget of *fresh* unique tokens keeps reducing it (1.24 → 1.04 across 1× → 32× data); the value lost to repetition grows from +16 % to +28 %. This is the data-side of the ≤ 4-epoch rule of [Muennighoff et al. (2023)](https://arxiv.org/abs/2305.16264) that motivates sizing the budget by scarce unique supply.

**`proxy-plan`** prints the H1–H6 configurations, metrics, and decision rules for the 1 B / 3 B GPU runs, which this script does not execute.

The accounting and the underlying mechanism are therefore verified and reproducible (`python3 experiments/experiment.py all`); the benchmark-level hypotheses H1–H6 still require the GPU proxy runs, which remain the immediate next action.

---

## 7. Ongoing data collection

The supply figures of Section 4 make three shortages measurable, and Session-4 cleaning is directed at these lanes rather than at data already held:

1. **Verified native Indic**, the binding constraint. Acquire additional genuine native text — Indic broadcast and podcast transcripts from the opened AIR and Doordarshan archives, PIB releases (14 languages), court judgments, and digitized Indic books — to raise the ~64–78 B verified ceiling and reduce reliance on translation and synthesis. These sources are freely usable (Section 2.2) and cover the scarcest languages.
2. **Genuine agentic trajectories**, which must be constructed rather than collected: an instrumented tool-execution harness that captures real multi-step sessions, including failures and recoveries, with correct masking, together with repository-task trajectories in the SWE style.
3. **Long native-Indic documents**, for the Indic component of the long-context lane, which the verified supply barely covers.

---

## 8. Limitations and provenance of the numbers

- **Measured or published (cited):** the Session-4 cleaning funnels (Table 1); every dataset size in the verified inventory (Table 3), drawn from the dataset cards and papers linked there; the four-epoch repetition finding ([Muennighoff et al. 2023](https://arxiv.org/abs/2305.16264)); and the ERA V4 reference points reported in the course material (web 70 → 18 %, code 13 → 35 %, science and mathematics 7 → 39 %, protected 8 %; OPUS at approximately 40 % retention and an approximately sixfold effective-token gain; the approximately 150× frozen-embedding gradient spike). Published dataset sizes are measured in each dataset's own tokenizer and must be re-measured in the Session-2 tokenizer before the run.
- **Design allocations (the author's proposal, not sourced):** the lane shares in Tables 4, 5, 8, and 9, the annealing composition, the reasoning length bands, and the proxy thresholds. Each is constrained by the measured supply of Table 3 and carries an explicit repetition or synthesis statement; none is presented as a sourced fact.
- **Not yet executed:** the Section-6 proxies, and the Section-7 collection targets (whose tokens are not counted in Table 3). Until the proxies are run, this specification is a defensible, supply-grounded hypothesis rather than a result.

---

## 9. Discussion and conclusion

A data mixture is a set of trade-offs made against a fixed token budget and composed backward from the capabilities the model is intended to demonstrate. General web is the largest lane only because it is the least expensive to obtain; the capabilities that motivate the project are scarce and are therefore protected by an always-on selection floor, held in an annealing reserve, and ordered by a curriculum rather than left to a selector that would suppress them. The decisive constraint is measured, not assumed: the verified native Indic supply is approximately 64–78 B unique tokens, and because repetition beyond four epochs ceases to help, a native-majority Indic lane is bounded at about 12 % of the budget. Every supply figure in this report is drawn from a published source, and every allocation is a design proposal constrained by that supply and stated so that it can be overturned by a 1 B- or 3 B-parameter proxy before adoption at 40 B. Running the Indic-floor and code-share sweeps is the next step.

---

## References

Links current as of July 2026.

**Training dynamics and data selection.** N. Muennighoff et al., "Scaling Data-Constrained Language Models," NeurIPS 2023, [arXiv:2305.16264](https://arxiv.org/abs/2305.16264). ERA V4 course material — mixture schedule, OPUS data selection, and training-stability analysis.

**Pretraining datasets.** G. Penedo et al., "The FineWeb Datasets," 2024, [arXiv:2406.17557](https://arxiv.org/abs/2406.17557) · [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu). "DCLM-baseline," [HF](https://huggingface.co/datasets/mlfoundations/dclm-baseline-1.0). A. Lozhkov et al., "StarCoder2 and The Stack v2," 2024, [arXiv:2402.19173](https://arxiv.org/abs/2402.19173) · [the-stack-v2-dedup](https://huggingface.co/datasets/bigcode/the-stack-v2-dedup). "FineMath," [HF](https://huggingface.co/datasets/HuggingFaceTB/finemath). K. Paster et al., "OpenWebMath," 2023, [arXiv:2310.06786](https://arxiv.org/abs/2310.06786). Z. Azerbayev et al., "Llemma / Proof-Pile-2," 2023, [arXiv:2310.10631](https://arxiv.org/abs/2310.10631). "Nemotron-CC-Math," 2025, [arXiv:2508.15096](https://arxiv.org/abs/2508.15096).

**Indic datasets and tooling.** AI4Bharat, "IndicLLMSuite / Sangraha," 2024, [arXiv:2403.06350](https://arxiv.org/abs/2403.06350) · [sangraha](https://huggingface.co/datasets/ai4bharat/sangraha). AI4Bharat, "IndicCorp v2," [HF](https://huggingface.co/datasets/ai4bharat/IndicCorpV2). J. Gala et al., "IndicTrans2," 2023, [arXiv:2305.16307](https://arxiv.org/abs/2305.16307).

**Agentic and reasoning datasets.** Salesforce, "APIGen / xLAM function-calling," 2024, [arXiv:2406.18518](https://arxiv.org/abs/2406.18518) · [HF](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k). AI-MO, "NuminaMath-CoT," 2024, [HF](https://huggingface.co/datasets/AI-MO/NuminaMath-CoT). Open-Thoughts, "OpenThoughts2-1M," 2025, [HF](https://huggingface.co/datasets/open-thoughts/OpenThoughts2-1M).

**Benchmarks.** SWE-bench (Jimenez et al., [arXiv:2310.06770](https://arxiv.org/abs/2310.06770)); GAIA (Mialon et al., [arXiv:2311.12983](https://arxiv.org/abs/2311.12983)); HumanEval (Chen et al., [arXiv:2107.03374](https://arxiv.org/abs/2107.03374)); MBPP (Austin et al., [arXiv:2108.07732](https://arxiv.org/abs/2108.07732)); LiveCodeBench (Jain et al., [arXiv:2403.07974](https://arxiv.org/abs/2403.07974)); GSM8K (Cobbe et al., [arXiv:2110.14168](https://arxiv.org/abs/2110.14168)); MATH (Hendrycks et al., [arXiv:2103.03874](https://arxiv.org/abs/2103.03874)); GPQA (Rein et al., [arXiv:2311.12022](https://arxiv.org/abs/2311.12022)); MMLU-Pro (Wang et al., [arXiv:2406.01574](https://arxiv.org/abs/2406.01574)); IndicGenBench (Google Research, [arXiv:2404.16816](https://arxiv.org/abs/2404.16816)). τ-bench, BFCL, and MILU are cited by name; confirm their current references before external circulation.

**Internal prior work.** ERA V5 Session 2 — Tokenizer report. ERA V5 Session 3 — Data-strategy report. ERA V5 Session 4 — Cleaning and deduplication report.

---

## Appendix A. Session-to-session lineage

**Table 11.** Contributions of prior sessions and what the present specification inherits.

| Session | Contribution | Inherited by this specification |
|---|---|---|
| S2 | ≈ 278 K Indic-aware tokenizer; per-language fertility | The unit in which every token here is counted |
| S3 | 40 B / 5 T strategy; the Indic-supply constraint; evaluation design; free acquisition tier | The budget, the Indic constraint, and the benchmarks |
| S4 | Eight-stage cleaning/deduplication/PII pipeline; per-script filter; provenance and determinism; book corpora | Auditable, Indic-preserving shards behind every lane |
| S5 (this) | Mixture, tier split, protected floor, annealing reserve, curriculum, and validation protocol | — |
