# Manual voice test plan — ArkByte 1.2.0

This is the next stage after installing the source package. Use only your own voice or a voice for which you have explicit permission. Do not use a third party's voice without permission.

## 1. Prepare ten source recordings

Record in a quiet room with one microphone and consistent distance (approximately 15–20 cm with a pop filter where available). Do not apply noise suppression, EQ, pitch correction, compression or voice enhancement. WAV is preferred; 24 kHz or 44.1/48 kHz mono/stereo is fine for intake. Keep the original files private.

Aim for roughly 45–120 seconds per item (10–20 minutes total). Use your natural voice; do not exaggerate your accent.

| Recording | Content | What it tests |
|---|---|---|
| 01 | Natural conversation about your day, work and interests | Baseline timbre and normal delivery |
| 02 | Neutral reading of a short paragraph | Stable reading voice |
| 03 | Questions and answers | Rising/falling intonation |
| 04 | Words with varied vowels and diphthongs | Vowel quality |
| 05 | Words with T/D, R, V/W, TH, S/SH and consonant clusters | Consonant articulation |
| 06 | Your own names, local place names, dates, numbers and acronyms | Personal pronunciation |
| 07 | Slow but natural speech | Deliberate articulation |
| 08 | Normal conversational pace | Everyday rhythm |
| 09 | Expressive narration | Natural emphasis and pitch variation |
| 10 | A continuous 1–2 minute story | Long-form consistency |

Keep a verbatim transcript for each recording, including repetitions and disfluencies. If uncertain, replay the source rather than guessing. ArkByte lets you add/correct transcripts after enrolment.

## 2. Enrol and review

1. Start the local services and open `http://127.0.0.1:3000`.
2. Open **Voice Lab** and enrol the ten recordings under one profile.
3. Tick the consent/ownership confirmation.
4. Add speaker-confirmed accent notes in plain language. Do not treat this field as an automatic accent detector.
5. Review every sample's duration, signal level, clipping, silence, pitch and warnings.
6. Listen to the proposed reference anchor and manually change it if a different clip is more representative.
7. Use Auto-transcribe where available to create draft text, then replay each original recording, correct every word and click Save transcript. Transcripts must display REVIEWED before export.
8. Add personal pronunciation dictionary items for names/words the baseline model mispronounces.
9. Export the Qwen training ZIP only after all ten transcripts are marked REVIEWED. The export rejects missing or unreviewed drafts. Keep the ZIP private.

## 3. Fixed held-out test script

Do not use the following phrases as training text. Use them for all model comparisons:

```text
Good morning. I am testing whether this voice sounds like my natural speaking voice.

Are we meeting at quarter past seven, or should I arrive at half past seven?

I usually speak at a steady pace, but I naturally change my rhythm when I explain something important.

Thirty-three thoughtful people visited the old theatre on Thursday.

Please read these names, numbers and abbreviations exactly as written: [insert your own names], 17, 27, 105, AI, ML, API and SQL.

This is a longer paragraph with commas, pauses, a question, and a final statement. I want the voice to sound conversational rather than like a formal announcer.
```

Replace bracketed content with names and words you naturally use. Keep the exact test script identical across model runs.

## 4. Compare outputs

- Generate the held-out test script using Chatterbox and save the output.
- If VoxCPM 2 is installed in the tested environment, generate the same script with the same anchor.
- Compare at the same playback loudness. Avoid judging a louder sample as automatically better.
- Run Benchmark Studio's acoustic proxy. If ECAPA is installed and the pretrained weights are available, run the speaker-embedding comparison as an additional signal.
- Listen blind where possible and rate identity/timbre, accent/pronunciation, pitch, rhythm/pauses, naturalness and text accuracy separately.
- Write down the exact phrase or phoneme that sounds wrong and update the pronunciation dictionary or reference anchor. Do not change multiple model settings between comparisons.

## 5. Acceptance table

| Dimension | Rating 1–5 | Notes / failed words |
|---|---:|---|
| Speaker identity / timbre | | |
| Accent and vowel pronunciation | | |
| Consonant articulation | | |
| Pitch and resonance | | |
| Rhythm and pause behaviour | | |
| Naturalness | | |
| Text accuracy | | |
| Consistency between sentences | | |

A useful acceptance target is repeatable improvement across several held-out scripts, not a single high model score. ECAPA cosine similarity is not a percentage match and there is no scientifically defensible universal threshold for every speaker, language, recording setup and model.

## 6. When to attempt fine-tuning

Only attempt Qwen3-TTS fine-tuning after all source transcripts are checked and the base-model results are recorded. Use the separate official Qwen environment, begin with the smaller Base model if hardware is limited, retain held-out phrases, monitor for overfitting and compare generated outputs before replacing the default model. A ten-recording set is an enrolment baseline, not a guarantee of sufficient data for robust fine-tuning.
