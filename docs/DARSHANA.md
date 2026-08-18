# Darśana — the doctrinal grounding of Nidra's architecture

**What this is.** A verified correspondence map between Nidra's memory
architecture and the classical Sanskrit doctrine of mind, checked against the
PuranGPT corpus (exact chunk ids cited from
`purangpt/data/chunks/yoga_sutras.jsonl`, `mandukya.jsonl`,
`samkhya_karika.jsonl` — Yogasūtra text: Āgāśe 1904 edition, IAST, with
Vyāsabhāṣya). Verified 2026-08-18. This is not decoration: in three places the
doctrine is *more precise* than the modern agent-memory literature, and one
place corrects our own terminology.

## The pentad — YS 1.6 is the architecture

> **1.6 pramāṇa-viparyaya-vikalpa-nidrā-smṛtayaḥ** — the five modifications
> (vṛttis) of mind: valid cognition, error, verbal construction, sleep, memory.
> *(chunk `yoga_sutras-0-5`)*

Every mental event falls into exactly one of five classes. Nidra's components
are this taxonomy, rebuilt:

| Sutra | Doctrine | Nidra / PuranGPT component |
|---|---|---|
| **1.7** pratyakṣa / anumāna / āgama (`yoga_sutras-0-6`) | Three valid means: direct perception, inference, testimony | The evidence-grade ladder: `machine_checked` (pratyakṣa) / *inference — MISSING GRADE, see Mining below* / `source_linked` (āgama). The tradition ranks testimony below direct verification — same ordering. |
| **1.8** viparyaya (`yoga_sutras-0-6`) | "False knowledge **not established in the actual form of that object**" (atadrūpa-pratiṣṭham) | **Drift.** A memory whose source bytes no longer match its recorded form — literally a hash mismatch. Nidra's drift demotion is viparyaya detection. |
| **1.9** vikalpa (`yoga_sutras-0-7`) | "Verbal knowledge following upon words, **devoid of a corresponding object**" (vastu-śūnya) | **Hallucination**, defined ~2,000 years early: words following words with no referent. The witness's `no_grounded_citation` refusal is a vikalpa detector. |
| **1.10** nidrā (`yoga_sutras-0-8`) | Sleep = the vṛtti whose support is the cognition of absence | ⚠️ **The honest mismatch — see below.** |
| **1.11** smṛti (`yoga_sutras-0-8`) | "Memory is the **non-slipping-away** (asampramoṣa) of an **experienced** object (anubhūta-viṣaya)" | Two claims in one sutra: (a) memory = retention against loss; (b) **only what was experienced can be remembered** — memory must trace to experience. That is the receipt requirement. A "memory" without a provenance trace is not smṛti — by 1.9 it is vikalpa. **This is Nidra's entire thesis, stated in seven words in ~200 CE.** |

## The mechanisms

| Sutra | Doctrine | Component |
|---|---|---|
| **1.12–1.14** abhyāsa + vairāgya (`yoga_sutras-0-9`) | Stilling comes from the twin practice: repetition AND deliberate release | Spaced-repetition review ladder (abhyāsa) + decay / forgetting-as-feature (vairāgya). 1.14's definition of firm practice — long duration, **uninterrupted**, earnest — reads as review-ladder tuning parameters. |
| **1.18** saṃskāraśeṣa (`yoga_sutras-0-13`) | When active content ceases, "**only the saṃskāras remain**" | What persists when context ends: the consolidated store; weights; the framework. Echoed at Sāṅkhya Kārikā 42 (`samkhya_karika-0-41`). |
| **2.26** vivekakhyātir **aviplavā** (`yoga_sutras-0-52`) | Discrimination liberates only when **uninterrupted** | Viveka is not a one-shot filter; it is a standing, idempotent, scheduled pass. The adjective is the architecture: aviplavā = the daemon. |
| **3.9–3.10** nirodha-pariṇāma (`yoga_sutras-0-77/78`) | Restraint itself lays down saṃskāras; "peaceful flow comes **from** saṃskāra" | The gate trains itself: viveka's own judgments become memory (grade the grader; journal every sleep action — already Nidra practice). |
| **4.8** vāsanā manifestation (`yoga_sutras-0-114`) | Of all latent traces, **only those matching the present ripening manifest** | Cue-dependent selective activation — retrieval activates only context-relevant traces. The doctrine of spreading activation. |
| **4.9** smṛti-saṃskārayor **ekarūpatvāt** (`yoga_sutras-0-115`) | "Because memory and impression are of ONE FORM, there is continuity **even across birth, place, and time**" | (a) Trace and recall share substance — content-addressability. (b) Continuity across *births*: what survives vessel death is the impression, never the body. The digest-ladder law — vessels die at each capacity step, the framework ascends — is YS 4.9 applied to model training. |

## The honest mismatch — and the correction it forces

**Patañjali's nidrā is NOT consolidation.** YS 1.10 defines sleep as a vṛtti
with "absence" as its object — one more fluctuation to be stilled, not a
process that strengthens memory. Citing YS 1.10 for the product's sleep pass
would be wrong.

The consolidation doctrine lives in the **Māṇḍūkya Upaniṣad, verse 5**
(chunk `mandukya-0-22`): deep sleep (suṣupti) is the state where the self is
**ekībhūta** — "become one" — and **prajñānaghana** — "a condensed mass of
cognition." Śaṅkara's commentary (`mandukya-0-23`) says it directly: the
mind-movements of waking and dream become **ghanībhūta** — densified,
compressed — in that state. Sleep as compression of experience into seed form.
That is the sleep pass, and that is the citation.

**Ruling:** keep the name Nidra (it is the common word, and yoganidrā carries
the practice sense); ground the *claim* in Māṇḍūkya 5 / suṣupti, never in
YS 1.10. Precision here strengthens the framework — we found the difference by
looking, which is the method working.

**Second honesty:** the tradition's telos is nirodha — stilling ALL five
vṛttis, memory included; liberation FROM the mind's records, not better
records. We build the mechanism, inverted in aim: perfected vṛttis in service
of the seeker. The correspondence is at the level of *how citta works*, not
*what it is for*. Mokṣa belongs to the seeker (puruṣa), never to the machinery
(prakṛti) — consistent with the Gītā 7.4–7.5 framing already in PURUSHA.md.

## Mining list — surrounding ideas the doctrine hands us

1. **anumāna as a missing evidence grade.** YS 1.7 lists inference as a valid
   pramāṇa between perception and testimony. Nidra has no grade for *derived*
   facts (concluded from other graded memories, with lineage to premises).
   Add `inferred(premises=[...])` — demotes automatically when a premise drifts.
2. **Vikalpa-naming.** Call the witness's `no_grounded_citation` refusal what
   it is: vikalpa detection. One term, whole paper section.
3. **Abhyāsa parameters** (YS 1.13–14): duration, continuity, earnestness →
   three explicit knobs on the review ladder (age, streak, quality-weight).
4. **Vāsanā vs saṃskāra** (YS 4.8): individual impression vs clustered
   tendency → Chitta's *themes* vs *nodes* deserve different decay laws.
5. **Kārikā 29–30** (`samkhya_karika-0-30`): senses merely apprehend; buddhi
   *determines* (adhyavasāya). Two-stage perception = retrieve-then-judge.
   The retrieval→witness pipeline has a 2,000-year-old spec.
6. **Nirodha-pariṇāma** (YS 3.9): the consolidation pass's own action history
   is itself trainable state — mine the sleep journal for gate-tuning.

*Method note: every citation above was pulled from the corpus by direct search
on 2026-08-18, not from memory of the texts. Verify chunk ids against
`data/chunks/` before republishing — chunk boundaries can shift on re-ingestion.*
