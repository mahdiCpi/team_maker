import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentTray } from "@/components/workspace/document-tray";
import type { AttachedDocument } from "@/components/workspace/workspace-state";
import {
  MAX_DOCUMENTS,
  MAX_DOCUMENT_TEXT_LENGTH,
  MAX_TOTAL_DOCUMENT_TEXT_LENGTH,
} from "@/lib/api-types";

/**
 * The document tray in isolation (Story 2.4 review patches).
 *
 * Rendered with a *fixed* `documents` prop and spy callbacks — which is not a
 * simplification but the point: the real parent dispatches to a reducer, so
 * the prop this component holds does not change while an async multi-file read
 * is in progress. Bounds checked against the prop rather than against a
 * running local count therefore silently passed, and this harness reproduces
 * exactly that.
 */

function textFile(name: string, text: string): File {
  return new File([text], name, { type: "text/plain" });
}

function renderTray(documents: AttachedDocument[] = []) {
  const onAttach = vi.fn();
  const onAttachFailed = vi.fn();
  render(
    <DocumentTray
      documents={documents}
      error={null}
      blockedReason={null}
      onAttach={onAttach}
      onAttachFailed={onAttachFailed}
      onRemove={vi.fn()}
    />
  );
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  return { onAttach, onAttachFailed, input };
}

describe("the document count cap", () => {
  it("holds within a single multi-file drop, not merely across separate ones", async () => {
    const user = userEvent.setup();
    const { onAttach, onAttachFailed, input } = renderTray([]);

    const files = Array.from({ length: MAX_DOCUMENTS + 3 }, (_, index) =>
      textFile(`file-${index}.txt`, `contents ${index}`)
    );
    await user.upload(input, files);

    // Every iteration used to compare against the same pre-drop count, so all
    // eight were attached and the cap was only enforced later, at Run time.
    expect(onAttach).toHaveBeenCalledTimes(MAX_DOCUMENTS);
    expect(onAttachFailed).toHaveBeenCalledWith(
      expect.stringContaining(`at most ${MAX_DOCUMENTS} documents`)
    );
  });

  it("counts documents that are already attached", async () => {
    const user = userEvent.setup();
    const existing: AttachedDocument[] = Array.from({ length: MAX_DOCUMENTS }, (_, index) => ({
      id: `doc-${index}`,
      name: `existing-${index}.txt`,
      text: "x",
    }));
    const { onAttach, onAttachFailed, input } = renderTray(existing);

    await user.upload(input, [textFile("one-too-many.txt", "nope")]);

    expect(onAttach).not.toHaveBeenCalled();
    expect(onAttachFailed).toHaveBeenCalled();
  });
});

describe("the total-characters cap", () => {
  it("is enforced at attach time, not only at Run time", async () => {
    const user = userEvent.setup();
    // Three files, each individually legal, that together exceed the total.
    // Two cannot do it: the per-file cap is exactly half the total.
    const each = Math.floor(MAX_TOTAL_DOCUMENT_TEXT_LENGTH / 3) + 1;
    expect(each).toBeLessThanOrEqual(MAX_DOCUMENT_TEXT_LENGTH);
    expect(each * 3).toBeGreaterThan(MAX_TOTAL_DOCUMENT_TEXT_LENGTH);
    const { onAttach, onAttachFailed, input } = renderTray([]);

    await user.upload(input, [
      textFile("first.txt", "a".repeat(each)),
      textFile("second.txt", "b".repeat(each)),
      textFile("third.txt", "c".repeat(each)),
    ]);

    expect(onAttach).toHaveBeenCalledTimes(2);
    expect(onAttachFailed).toHaveBeenCalledWith(
      expect.stringContaining(MAX_TOTAL_DOCUMENT_TEXT_LENGTH.toLocaleString())
    );
  });
});

describe("an empty file", () => {
  it("is refused at attach time, because the server would refuse the whole run", async () => {
    const user = userEvent.setup();
    const { onAttach, onAttachFailed, input } = renderTray([]);

    await user.upload(input, [textFile("empty.txt", "")]);

    // `RunDocumentInput.text` is `min_length=1`, so attaching this would have
    // turned the next Run into a 422 about a file the tray said was fine.
    expect(onAttach).not.toHaveBeenCalled();
    expect(onAttachFailed).toHaveBeenCalledWith(expect.stringContaining("empty"));
  });
});

describe("two files sharing a basename", () => {
  it("are removable independently, by id", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    const documents: AttachedDocument[] = [
      { id: "doc-0", name: "brief.txt", text: "from ~/specs" },
      { id: "doc-1", name: "brief.txt", text: "from ~/archive" },
    ];
    render(
      <DocumentTray
        documents={documents}
        error={null}
        blockedReason={null}
        onAttach={vi.fn()}
        onAttachFailed={vi.fn()}
        onRemove={onRemove}
      />
    );

    const items = document.querySelectorAll('[data-slot="workspace-document-item"]');
    expect(items).toHaveLength(2);

    await user.click(screen.getAllByRole("button", { name: "Remove brief.txt" })[1]);

    // By id, so the sibling with the same name survives. Removing by name
    // deleted both.
    expect(onRemove).toHaveBeenCalledWith("doc-1");
  });
});
