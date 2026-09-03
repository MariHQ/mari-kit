# Contradiction reference validation

This audit compares Mari's contradiction primitives with permissively licensed
implementations and datasets. It validates numerical and parsing behavior; it
does not import, vendor, or redistribute their code.

## References checked

| Reference | License | What was compared |
|---|---|---|
| [Overcomplete `a1781af`](https://github.com/KempnerInstitute/overcomplete/tree/a1781af49c6e4bbfdbfd763b9757bcf6c5dd6403) | MIT | Hoyer normalization and the one-hot/dense reference vectors in `tests/misc/test_metrics.py` |
| [RRC-DSCD `1e7b739`](https://github.com/MINE-USTC/RRC-DSCD/tree/1e7b7391f78d98edc7cdcfa4d91a83a9dbdfbc63) | MIT | sentence-range parsing, reference coverage, output-format reward, and positive/negative accuracy reward behavior |
| [ContraDoc `d1c42d1`](https://github.com/ddhruvkr/CONTRADOC/tree/d1c42d1e433595dd6e98fab7b669722cdc050b1d) | Apache-2.0 | Boolean self-contradiction labels, localized evidence conventions, and classification evaluation boundaries |

The official [SparseCL repository at `14fcd8b`](https://github.com/xuhaike/SparseCL/tree/14fcd8bcfeef2603f37b1e805cd3626800430711) does not
declare a license. It was inspected only to locate the authors' equations and
experimental entry points; no source was incorporated. SparseCL's Hoyer
primitive was cross-checked against the MIT Overcomplete implementation, while
the combined retrieval score and loss were checked directly against Equations
1--3 of the paper.

## Results

### Hoyer sparsity

Mari matches Overcomplete's published reference fixtures: a one-hot vector has
normalized Hoyer sparsity `1`, and an equal-valued dense vector has sparsity
`0`. Mari applies the measure to `h1 - h2`, as required by SparseCL. It also
defines the otherwise undefined zero difference as `0`, validates dimensions,
and clips floating-point noise to `[0, 1]`.

Overcomplete adds `1e-6` to its L2 denominator. Mari does not copy that numerical
bias because SparseCL's equation does not include it; Mari handles an exact zero
denominator explicitly instead.

### Reference coverage

Mari matches the RRC-DSCD implementation for `[i]` and `[i-j]`: ranges are
inclusive, repeated references are deduplicated, and coverage is the number of
referenced sentence IDs divided by the document sentence count. Mari also
accepts `[i]-[j]`, which is specified by the paper but not recognized by the
repository's regular expression. Unlike the reference script, Mari rejects
descending and out-of-document ranges instead of silently counting them.

### Accuracy reward

Mari deliberately follows Equation 5 in the paper, not the current
`code/rl/rewards.py` behavior where the two diverge:

- the paper uses `matched_gold_evidence / total_gold_evidence`; the repository
  divides each hit by the number of predicted evidence strings;
- the paper gives a correct positive judgment with no evidence hit `-1`; the
  repository starts at `1` and subtracts `0.5`, producing `0.5`;
- the repository can modify the score of an incorrect positive judgment while
  processing evidence, whereas Equation 5 gates the whole reward on judgment
  correctness.

Mari's paper-conformant behavior is covered by deterministic tests for partial
hits, zero hits, incorrect judgments, and negative examples. The difference is
documented so consumers reproducing the authors' exact training script can make
an explicit compatibility choice rather than receiving silent mixed semantics.

### ContraDoc boundary

ContraDoc treats document detection as a Boolean label and evidence localization
as a separate evaluation concern. Mari preserves the same boundary:
`DocumentContradictionAssessment.judgment` is Boolean, positive assessments must
carry localized sentence IDs, and negative assessments cannot claim
contradiction evidence. Semantic matching such as the reference benchmark's
BERTScore threshold remains an injected evaluator rather than a NumPy runtime
dependency.
