# Reference 06: Family Member Tracking, Character Continuity & Reception Dynamics

When processing 500 to 1,000 raw clips (6 to 7 hours of footage, 100–200 GB), the single most critical failure mode in wedding video editing is **omitting a key family member** (such as a grandmother, maternal uncle, or elder brother) or unevenly representing both family sides.

This guide details the facial tracking taxonomy, logging protocol, and reception stage editing techniques to guarantee character continuity and cinematic balance.

---

## 1. The Multi-Character Tracking Taxonomy

Every person in raw wedding footage must be logged into one of five tier categories:

```
[Tier 1: Core Couple] ────────► Bride (B01), Groom (G01)
       │
[Tier 2: Immediate Parents] ──► Bride's Father (BF01), Bride's Mother (BM01)
       │                        Groom's Father (GF01), Groom's Mother (GM01)
       │
[Tier 3: Siblings & In-Laws] ─► Brothers, Sisters, Bhabhi, Jija, Close Cousins
       │
[Tier 4: Elders & Guardians] ─► Grandparents, Nana-Nani, Dadi-Dada, Mamas, Chachas
       │
[Tier 5: VIP Dignitaries] ────► Special Guests, Senior Officials, Family Priests
```

### Logging Schema (Metadata Tagging)
Before slicing a single clip, run through the raw footage and tag clips with person codes:
* `C0012.MOV`: `[RITUAL: Haldi] [SUBJECTS: B01, BM01, SIB02] [EMOTION: Tears/Laughter] [RATING: 4-star]`
* `C0458.MOV`: `[RITUAL: DwarPuja] [SUBJECTS: G01, BM01, GF01] [ACTION: Nose Catching] [RATING: 5-star]`

---

## 2. Character Balance & Screen Time Audit Rule

To ensure familial satisfaction and prevent domestic friction after film delivery, the master edit must satisfy the **Family Screen-Time Balance Matrix**:

| Deliverable | Groom's Family Share | Bride's Family Share | Joint Couple Focus | Required Minimum Appearances |
| :--- | :--- | :--- | :--- | :--- |
| **Teaser (1-3 min)** | 20% | 20% | 60% | Couple (100%), Each Parent Set (At least 2 hero shots each) |
| **Trailer (5-10 min)** | 25% | 25% | 50% | Couple (100%), Parents (5+ shots), Siblings (3+ shots), Grandparents (2+ shots) |
| **Master Film (1-3 hrs)** | 40% | 40% | 20% | Every Tier 1–4 member must appear in their respective ritual interactions with verified presence. |

---

## 3. Reception & Bahubhoj Stage Shoot Mastery

The Reception / Bahubhoj is where hundreds of guests interact with the newlywed couple on the decorated stage. Handled poorly, reception video becomes a monotonous 45-minute slide of static smiles and awkward handshakes. Handled cinematically, it becomes a dynamic celebration of community and blessing.

### A. Stage Setup & Visual Elements
1. **The Stage & Décor**:
   * Establishing shots of the banquet hall architecture, chandelier lights, floral arches, entrance walkway, and stage backdrop.
   * Frame wide shots of the couple seated majestically on the reception sofa.
2. **The Gift & Shagun (*Lifafa*) Ritual**:
   * Relatives approach in groups with gift boxes, bouquets, and traditional monetary envelopes (*Lifafa*).
   * Elders place their hands on the heads of the bride and groom, whispering blessings (*Ashirwad*).
   * The couple bends forward to touch elders' feet (*Charan Sparsh*).

### B. Reception Dynamic Editing Formula (The "3-Cut Rhythm")
Never stay on a static wide shot for more than 4 seconds. Use the 3-Cut Rhythm for every guest group:

```
[Cut 1: Wide Angle (2.0s)]   ──► Group walks up stage, smiles, approaches couple
          │
[Cut 2: Medium-Close (2.5s)] ──► Envelope / Gift handover, elder placing hand on head in blessing
          │
[Cut 3: Candid Punch (1.5s)] ──► Warm hug, candid laugh between groom and cousin, or affectionate glance
```

### C. Banquet Hall Lighting & LED Color Management
Banquet halls in Patna and regional cities often feature high-contrast LED floodlights (often casting neon magenta, harsh cyan, or excessive yellow).
* **Fixing Stage Color Casts**:
  * Apply a secondary HSL Qualifier / Hue vs Sat curve in FCPX specifically on the background LED hue without touching the couple's face skin tone.
  * Use a digital soft-box / power window (vignette with warm lift) to illuminate the couple while slightly lowering exposure on distracting background guests.

### D. Intercutting Pangat & Dining Moments
* Intercut stage photography with the lavish wedding dinner (*Pangat* / Buffet).
* Film the live cooking counters: authentic Bihari delicacies (Litti Chokha, Malpua, fresh Jalebis, Dal Puri) and guests relishing food in warm conversation.

