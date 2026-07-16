# Core Glossary

## Terms

**Inward Eyes**: A local Codex plugin for evidence-backed browser workflows.

**Evidence-backed browser workflow**: A browser task that produces structured outputs linked to source records, screenshots, timestamps, validation reports, and run manifests.

**Skill**: A focused Codex workflow such as `page-to-md`, `browser-research`, or `price-compare`.

**Plugin**: The installable Codex distribution unit that can bundle skills, references, schemas, scripts, and optional MCP configuration.

**MCP tool**: A Model Context Protocol tool server that can expose structured browser or data operations to Codex.

**SourceRecord**: Shared structured source metadata used across skills.

**Document AST**: Structured representation of headings, paragraphs, lists, quotes, code blocks, images, and tables before rendering Markdown.

**Claim ledger**: Research artifact mapping claims to sources, support type, confidence, and unknowns.

**PriceRecord**: Structured quote artifact for ecommerce comparisons.

**Manual review**: A run state requiring user inspection before conclusions should be trusted.

## Relationships

- A run manifest contains SourceRecords and references all artifacts.
- A rendered report must be traceable back to structured JSON.
- Browser screenshots help humans review; schemas help machines validate.
- Site profiles may inform extraction, but contracts define durable behavior.
