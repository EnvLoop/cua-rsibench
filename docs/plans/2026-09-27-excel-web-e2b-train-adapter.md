# Excel for the web train-only desktop adapter

The original Excel cell needs a screenshot-bound model action loop on the real
Microsoft surface. The offline 20/20/100 workbook inventory and per-final
control recipes do not establish that loop, and no hidden-final material may be
used to debug it.

Three implementation choices were considered: a separate browser DOM actor,
generalizing the PowerPoint E2B runner before any Excel pilot, and a small Excel
adapter over the current shared v0.6.5 screenshot/action boundary. The adapter
is the smallest change that keeps the common student contract. It uses only a
current E2B screenshot and the train actor task. Workbook content visible in
the GUI is permitted; the model receives no direct package bytes, oracle,
cloud URL, account detail, or final control recipe. The trusted
runner checks the current screenshot again after sampling and before dispatch.
All targets are screenshot coordinates because the desktop adapter supplies no
visible control references. Only the v0.6.5 validated GUI action vocabulary is
dispatched; no Office API, selector, shell, or direct workbook mutation is part
of the actor.

The admission boundary requires a private train package containing an actor
workbook and an allowlisted actor instruction, a bounded manually signed-in
E2B login session, and an Excel train cloud-item URL. A manually supplied URL
is not proof of upload identity. The first pilot therefore remains development
only and cannot score a task or admit a final item. Saved `.xlsx` retrieval is
fail-closed until a separate GUI download implementation binds the cloud item,
download, source workbook, and independent task oracle. The signed-in train
account must also be isolated from sealed final items; the URL shape alone
cannot establish that ACL boundary. An injected retriever
can exercise package sanity checks in tests but never upgrades this status.

Offline acceptance covers train/final path isolation, package and URL checks,
snapshot changes during inference, invalid action rejection, pixel-only
dispatch, append-only private intent/result logs, sandbox teardown, and the
unqualified artifact boundary. A live Excel train pass must later verify manual
account login, the exact cloud item and seed upload, Excel save, original-format
download, and independent saved-state readback before claiming a qualified
original-software workflow.
