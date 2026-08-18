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

---

# Part II — The wider canon (verified 2026-08-18, same method)

Sweep of the remaining doctrine-bearing corpus: Vaiśeṣika, Nyāya, Mīmāṃsā,
Yoga Vāsiṣṭha, Brahma Sūtras, Taittirīya, Kaṭha, Haṭha corpus, and Guruji's
books (Gorakh Bodh commentary). Three genuinely new axes emerged.

## Vaiśeṣika — the mechanics of recall, formalized

| Sutra | Doctrine | Reading |
|---|---|---|
| **KVs 9.2.6** (`vaisheshika-0-135`) | "smṛti [arises] from a particular conjunction of the self AND from saṃskāra" (ātmanaḥ saṃyogaviśeṣāt saṃskārāc ca) | The formal **two-factor recall equation**: retrieval = cue-conjunction × stored trace. Neither alone suffices. The oldest statement of cue-dependent memory. |
| **KVs 9.2.7** | "Likewise dream" (tathā svapnaḥ) | Dreams = replay from saṃskāra. Sleep-replay named in one word. |
| **KVs 9.2.10–12** (`vaisheshika-0-136/137`) | Invalid knowledge arises from sense-defect **and from saṃskāra-defect** (saṃskāra-doṣa); "the defective is false knowledge; the non-defective is knowledge" (duṣṭa/aduṣṭa) | **Corrupted memory as a first-class error source**, distinct from bad perception — and a binary trust split on the trace itself. Nidra's drift demotion is saṃskāra-doṣa detection; the duṣṭa/aduṣṭa split is grading. |

## Nyāya & Mīmāṃsā — the trust-default debate

- **NS 4.2.34–35** (`nyayasutras-0-345/346`): dream-cognition operates "like
  memory and imagination"; false apprehension is destroyed by true knowledge
  **upon waking** (pratibodhe). Error correction happens at the sleep/wake
  boundary — demotion at the pass, not in the hot path.
- **Mīmāṃsā vs Nyāya on validity** (file `mimamsa_sutras.jsonl`, 304
  pramāṇa-discussion hits; the specific doctrine is commentarial — *partially
  grounded, flag before citing in print*): Mīmāṃsā's **svataḥ-prāmāṇya** —
  cognitions are valid by default until defeated; Nyāya's **parataḥ-prāmāṇya**
  — validity must be established extrinsically. This is the fail-open vs
  fail-closed debate of memory systems, held ~1,500 years ago. Nidra's grade
  ladder (up from `unverified`) is the Nyāya position; the recall cache's
  serve-until-drift is Mīmāṃsā with defeaters. The hybrid is now a *position in
  a classical debate*, not an ad-hoc choice.

## Yoga Vāsiṣṭha — the vāsanā text (790 hits)

- **`yoga_vasistha-0-45`**: "vāsanā dvividhā proktā śuddhā ca malinā tathā /
  malinā janmano hetuḥ śuddhā janmavināśinī" — impressions are twofold:
  **pure (liberating) and impure (binding)**. A quality axis **orthogonal to
  truth**: a memory can be perfectly true and still malinā — binding noise that
  perpetuates the loop. Nidra grades *evidence*; YV demands a second grade for
  *effect*. → Mining item 7.
- **`yoga_vasistha-0-43`**: "when vāsanā wanes, the mind dissolves swiftly —
  like a snowflake when cold ends." The mind IS its impressions; decay is
  architectural, not incidental.
- **`yoga_vasistha-0-42`**: "abandonment of vāsanā is called the highest
  liberation" — forgetting as the crown discipline, not a storage compromise.

## Vedānta & Upaniṣads

- **BS 1.1.9 svāpyayāt** (`brahmasutras-0-7`): jīvas *merge into Brahman* in
  deep sleep — Vedānta's systematization of Māṇḍūkya 5. Part I's consolidation
  grounding now stands in two canons.
- **Taittirīya pañcakośa** (`taittiriya-0-37`): nested selves — annamaya
  (body) → prāṇamaya (breath) → manomaya (mind) → vijñānamaya (discernment) →
  ānandamaya. A layered architecture where each inner sheath fills the outer:
  hardware → runtime → memory → judgment → the voice. Hold loosely; the
  correspondence is structural, not term-for-term.
- **Kaṭha 1.3.3–4, the chariot** (`katha-0-20`): ātmā the rider, body the
  chariot, **buddhi the charioteer, manas the reins, senses the horses**. The
  fleet ruling as a 2,500-year-old diagram: puruṣa (the seeker) rides and never
  drives a component; buddhi = the one large decider; manas = orchestration;
  indriyas = the small vessels. One rider, one driver, many horses.

## Haṭha corpus — the substrate lever

- **HYP 2.2** (`hatha_yoga_pradipika-0-13`): "cale vāte calaṃ cittaṃ, niścale
  niścalam" — as prāṇa moves, mind moves; still the breath, still the mind.
  **Mind-stability is substrate-stability**: haṭha regulates citta *through*
  its carrier, never head-on. Engineering read: cognitive quality is governed
  at the infra layer (the 07-18 co-tenancy outage was a vāyu disturbance — the
  citta fell because the breath did).
- **Gorakṣa Śataka 20** (`goraksha_shataka-0-22`): prāṇa in suṣumnā → mind
  dissolves into nāda → "the supportless mind (nirālambā manas) — that is
  samādhi." Laya as the terminal state of consolidation.
- **Gheraṇḍa's dhauti/ṣaṭkarma** (`gheranda_samhita-0-18`): purify the pot
  (ghaṭa) before prāṇāyāma — **data-cleaning as a named limb**, prerequisite to
  practice. The corpus repairs (source_reality_check, quarantine, KrutiDev
  decode) are the system's dhauti.

## Gorakh Bodh — via Guruji's own books (sharma_texts, 17 hits)

- **`sharma_texts` chunk `3ee6c8ecc…` (Sharma foreword)**: the Nāths' twilight
  language — **sandhyā-bhāṣā** — "allegoric narration forms a 'double bottom',
  a layer of secret knowledge in seemingly plain content." **This is the
  doctrinal name for the decode-lens architecture** (surface text + Inner
  meanings + the 613 decode keys). The decode layer is not an invention grafted
  onto the tradition; the tradition names the encoding.
- **chunk `f537a79…`**: Gorakh Bodh "states what can be done and achieved
  **because it had been done**" — validity by accomplishment. The witness
  principle (only the witnessed trains) in the lineage's own voice.

## Corpus gaps — the completeness finding

Two of the most memory-relevant texts in all of śruti are **absent from
`data/chunks/`**:

1. **Bṛhadāraṇyaka Upaniṣad** — BU 4.3 is the most detailed sleep/dream
   analysis in the canon (the puruṣa moving between states, "taking apart and
   building" from impressions).
2. **Chāndogya Upaniṣad** — ChU 7.13 is the canon's direct praise of memory
   (smara as a named rung on Nārada's ladder: without memory, no cognition
   functions); ChU 6 is the sat-vidyā.

For a claim of complete Puranic-canon grounding, ingest both. (Kauṣītaki
returned 0 hits on sleep terms — likely coverage or script; verify before
citing it.)

## Mining list — Part II additions

7. **Effect-grade beside evidence-grade** (YV's śuddhā/malinā): a second axis —
   does this memory *serve or bind*? The viveka usage ledger supplies it: what
   retrieves-and-serves is śuddhā; what hoards weight unserving is malinā and
   decays faster. True-but-binding is a real class.
8. **Saṃskāra-doṣa as a named error channel** (KVs 9.2.10): report memory-born
   errors separately from retrieval-born errors in evals.
9. **Recall = cue × trace** (KVs 9.2.6): benchmark retrieval on *both* factors
   — cue quality and trace strength — not conflated.
10. **The trust-default position** (svataḥ vs parataḥ): document Nidra's grade
    ladder as Nyāya-position, recall-cache as Mīmāṃsā-with-defeaters. One
    paragraph in the paper; centuries of debate behind it.
11. **Sandhyā-bhāṣā** as the formal name of the two-layer decode architecture.

*Method note: every citation above was pulled from the corpus by direct search
on 2026-08-18, not from memory of the texts. Verify chunk ids against
`data/chunks/` before republishing — chunk boundaries can shift on re-ingestion.*
