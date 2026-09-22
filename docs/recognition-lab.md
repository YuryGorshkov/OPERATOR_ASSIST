# Recognition Quality Lab

Offline, opt-in developer tooling for measuring changes before applying them to
the desktop application. It is not imported by the desktop UI and does not
change the installed application or its saved settings.

## Current Status

Implemented: paired-data validation, nine comparison profiles, offline replay,
metrics, local audio conversion and verified-pair export.

Not yet completed: verified real-audio benchmark, overlap-based segmentation,
live latency tests, model fine-tuning and deployment of a trained model.
Unit tests validate the tooling, not recognition quality. No measured accuracy
gain is claimed until a held-out evaluation supports it.

## Safe Workflow

1. Preserve the current installer, settings and source revision before experiments.
2. Select authorized recordings and matching text. A book's text and its recording
   may have different usage terms; retain source and permission metadata.
3. Import an authorized local file or separately obtain a digital output recording.
   These tools do not capture microphones or system audio. Playback alone does
   not train the model, and no hidden background recording is enabled.
4. Convert a copy to mono PCM16 WAV at 16000 Hz, keeping the original unchanged.
5. Match time intervals to the words actually spoken. Correct skipped passages,
   actor deviations, introductions, abridged editions and other mismatches.
6. Mark transcripts verified only after checking the audio/text correspondence.
7. Tune on `dev`; reserve `test` for evaluation after profile selection.
8. Export verified pairs for a later, separate fine-tuning experiment.
9. Compare baseline, tuned and trained variants on held-out books, voices and
   conversational speech before modifying the desktop runtime.

## Data Layout

Run from the repository root with Python 3.10 and `requirements.txt` installed.
Keep local assets under ignored directories:

```text
asr-lab-data/
  audio/
  references/
  corpus.jsonl
asr-lab-reports/
  run-001/
asr-lab-checkpoints/
```

The manifest template is `examples/recognition-lab/manifest.template.jsonl`.
It is deliberately unverified and references nonexistent sample files; it is
not an evaluation corpus. Audio and text-file paths resolve relative to the
manifest. Each nonempty line is a JSON object with:

| Field | Meaning |
| --- | --- |
| `id` | Unique sample identifier |
| `audio` | Local mono PCM16/16000 Hz WAV |
| `text` or `text_file` | Exactly one verbatim reference; empty text allows silence tests |
| `start`, `end` | Audio interval in seconds; omitted end means the file duration |
| `split` | `train`, `dev` or `test` |
| `book_id`, `passage_id` | Stable passage identity shared across alternate readings |
| `speaker_id` | Narrator identifier |
| `critical_terms` | Optional terms/names/numbers to track as occurrence coverage |
| `license` | Source and permission notes, not an automatic license determination |
| `verified` | Must be boolean `true` after human checking |

The validator rejects duplicate identifiers, bad formats, invalid intervals,
unverified transcripts, overlapping audio across splits and alternate readings
of the same book passage across splits. Shared books/narrators are warned about:
these sets are not fully unseen-book or unseen-speaker evaluations.

## Commands

```powershell
py -3.10 -X utf8 -B -m asr_lab profiles
py -3.10 -X utf8 -B -m asr_lab check asr-lab-data/corpus.jsonl
py -3.10 -X utf8 -B -m asr_lab convert input.mp3 asr-lab-data/audio/book01.wav --permission-confirmed
py -3.10 -X utf8 -B -m asr_lab evaluate asr-lab-data/corpus.jsonl --model whisper-ct2 --output asr-lab-reports/run-001
py -3.10 -X utf8 -B -m asr_lab export-training asr-lab-data/corpus.jsonl asr-lab-data/training-001
```

`--model` must point to an existing, complete local CTranslate2 Whisper model;
automatic weight downloads are disabled. `--device cpu` prevents CUDA attempts.
The default GPU request retains the runtime's CPU fallback, and the actual
device/compute type is recorded. Closed-test evaluation requires `--allow-test`.
Output paths must be new: existing audio files and report/export directories
are never overwritten. Model initialization and synthetic silence warmup are
timed separately from profile comparisons.

## Comparison Profiles

`baseline` preserves the historical fixed-window control: 250 ms replay blocks,
a 6-second buffer, 0.7-second minimum gap segment, speaker preprocessing and prior
text. `production_pause` uses the current desktop engine: original PCM, pause-aware
segmentation, timestamp-owned overlap, beam width 8 and decoder-based non-speech
rejection. Lab-only pause beam profiles retain widths 5 and 10 as controls.
Other profiles change one factor from the fixed-window control:

- `context_off`: disable internal and externally supplied previous-text context.
- `raw_context`: reuse pre-correction text rather than dictionary-normalized output.
- `term_hints`: provide a separate topic-specific `--hotwords-file` to Whisper.
- `preserve_short`: lower the minimum gap segment to 0.2 seconds.
- `longer_chunks`: increase continuous buffering to 8 seconds.
- `vad_700ms`: increase Whisper's VAD silence parameter to 700 ms.
- `beam_3`: compare beam size 3 against baseline 5.
- `audio_bypass`: bypass the existing speaker preprocessor.

Reference text is never used as a recognition hint. Term hints bias decoding;
they do not force Marvel to become Laravel. IT post-corrections are independently
controlled by `--it-mode`. The default is off.

## Reports And Limitations

Each run saves `run.json`, incremental `samples.jsonl`, `summary.json` and
`benchmark.log`. Reports retain dependency versions, corpus/audio/model/source
hashes, effective options, fallback details, raw output and errors. Failed
samples make the run unsuccessful and are counted rather than hidden.
Training exports have a completion/error marker and do not start training.

WER/CER aggregate edit counts across the corpus rather than averaging fragment
rates. Normalization uses NFKC, case folding, Russian yo/e equivalence and
punctuation tokenization; C++ and C# remain distinct. CER includes spaces.
No phonetic replacement is applied to reference text to hide acronym errors.
Silence hallucinations are counted as insertions even with zero reference words.

## Real-time latency replay

The `realtime` command feeds verified PCM to the production recognizer every
250 ms on an independent producer thread. A separate consumer performs model
inference while UI events are collected at the desktop application's 120 ms
polling interval. The report includes WER/CER, queue drops, queue depth,
per-speaker results, p50/p95 delivery latency, and review-only error candidates.

```powershell
py -3.10 -m asr_lab realtime data\manifests\verified.jsonl `
  --model E:\models\large-v3-turbo `
  --terms-file config\technical_terms.json `
  --profile production_pause `
  --device gpu `
  --output E:\OPERATOR_ASSIST_LAB\tmp\realtime-run
```

Output directories are never overwritten. `error-candidates.json` never edits
the application dictionary; each proposed replacement requires human review.
Term coverage counts expected, recognized and extra mentions, not contextual
semantic correctness; critical errors still require review.

RTF and first-result buffer time describe offline replay, not live GUI startup,
queue drops, p95 end-to-end latency or device routing. Those require separate
live tests. More narration data does not guarantee improvement on spontaneous
calls or IT terminology; include appropriate conversational/technical samples.
For a fine-tuning pilot, verify GPU resources first, keep training separate,
retain the original model and evaluate any converted model in the application.

Do not upload recordings, reference books, reports, local configuration,
backups or model checkpoints with the source code.
