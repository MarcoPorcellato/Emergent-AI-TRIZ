# EXP-001 R3 fixture boundary

These records are no-model authoring fixtures. They are not sealed targets,
model outputs, human labels, or evidence for any TRIZ claim.

- `items.jsonl` contains paired task prompts. Every blinded/exposed pair has a
  shared problem family, but each stratum is explicitly non-poolable.
- `matrix-cells.jsonl` retains three sparse, double-checked identifiers and
  principle-number sequences from the external Matrix 2003 page. It is not a
  reproduction of the table and does not imply symmetry: the reverse ordered
  cells must be independently checked or require abstention.
- `tool-edges.jsonl` retains two visually supported directed relations and two
  explicit `not_established` controls from the user-attributed Panitz map. Its
  rights state remains unverified; it is a reference-task fixture only.
- `source-exposures.jsonl` is independently written, bounded context. It does
  not contain copied source passages, images, or canonical examples.

Before an execution freeze, a separate fixture build must add a sufficient
predeclared split assignment, lexical-control counterparts, response options,
and a sealed target file. No target may be opened outside the one approved
analysis boundary.
