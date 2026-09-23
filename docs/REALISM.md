# Realism and evidence boundaries

The primary environment is **unmodified Kanboard 1.2.54** deployed to disposable E2B sandboxes. It uses its own PHP controllers, login, forms, comments, projects, save behavior and SQLite database. An external API actor receives native visible text and controls and can only click, fill, select, press a limited key, go back, or finish. It has no shell, database, file or application API tool.

Environment initialization uses the application's JSON-RPC API before the actor starts. Initialization is evaluator infrastructure; it is not credited as agent work. After execution the trusted host requests an independent SQLite snapshot. The verifier checks requested assignments, priorities and scores while preserving all unrelated tasks, descriptions, comments, project identities and source records. Passwords, auth tokens and author identities are excluded from exported data.

Public issue metadata is collected from kanboard/kanboard through GitHub, with source URLs, collection time, titles (24-word cap), states, timestamps, labels and comment counts. No issue bodies or author profiles are copied. The imported records are real-source data. The review policy, staff identities, project names and historical distractor copies are declared benchmark constructs. They are not represented as a real organization's workflow or as upstream staff decisions.

The earlier handwritten expense/workbench pages are development fixtures, not the primary realism claim. Their saturated results were excluded from formal RSI claims and the saturated campaign was stopped. Harder synthetic arithmetic/allocation fixtures remain useful for unit and oracle testing, but cannot replace real-software acceptance.

This release tests DOM-assisted browser use, not pixel-only mouse grounding, full Windows/macOS operation, or cross-application enterprise deployment. Any wider claims require corresponding execution evidence.

Native form equivalence is limited to LF/CRLF text line endings, null/zero time fields, and application-maintained timestamps. Content changes, extra records and unrelated object changes still fail. Original results are preserved alongside any corrected regrade.
