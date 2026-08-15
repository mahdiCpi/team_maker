import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deleteTeam, listTeams, recordTeamRun, renameTeam } from "@/lib/api-client";
import { createTeamsFetchQueue, type TeamsFetchQueue } from "./harness";

const team = {
  name: "Article Team",
  created_at: "2026-08-01T00:00:00Z",
  last_run_at: null,
  run_count: 0,
};

describe("teams API client", () => {
  let queue: TeamsFetchQueue;

  beforeEach(() => {
    queue = createTeamsFetchQueue();
    queue.install();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists teams", async () => {
    queue.queueBrowse(200, { teams: [team] });

    const result = await listTeams();

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.teams).toEqual([team]);
    expect(queue.requests[0]).toMatchObject({ url: "/api/teams/browse", method: "GET" });
  });

  it("reports team_not_found from a 404 browse-adjacent failure without inventing a code", async () => {
    queue.queueBrowse(500, { error: { code: "internal_error", message: "boom" } });

    const result = await listTeams();

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("internal_error");
  });

  it("renames a team", async () => {
    const renamed = { ...team, name: "Renamed Team" };
    queue.queueRename(200, renamed);

    const result = await renameTeam("Article Team", "Renamed Team");

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.name).toBe("Renamed Team");
    expect(queue.requests[0]).toMatchObject({
      url: "/api/teams/rename",
      method: "PUT",
      body: { old_name: "Article Team", new_name: "Renamed Team" },
    });
  });

  it("rejects a too-short new name before sending a request", async () => {
    const result = await renameTeam("Article Team", "A");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("spec_invalid");
      expect(result.fields).toEqual([
        { path: "new_name", message: "Must be at least 2 characters." },
      ]);
    }
    expect(queue.requests).toHaveLength(0);
  });

  it("surfaces a server-side duplicate-name rejection in plain language", async () => {
    queue.queueRename(409, {
      error: { code: "output_exists", message: "Team name 'Renamed Team' already exists (case-insensitive)." },
    });

    const result = await renameTeam("Article Team", "Renamed Team");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("output_exists");
      expect(result.message).toContain("already exists");
    }
  });

  it("deletes a team by name via a query parameter, not a body", async () => {
    queue.queueDelete(200, { message: "Team 'Article Team' and all its saved runs/results have been deleted." });

    const result = await deleteTeam("Article Team");

    expect(result.ok).toBe(true);
    expect(queue.requests[0]).toMatchObject({
      url: "/api/teams/delete?team_name=Article%20Team",
      method: "DELETE",
    });
    expect(queue.requests[0].body).toBeUndefined();
  });

  it("records a re-run", async () => {
    queue.queueRecordRun(200, { ...team, last_run_at: "2026-08-14T00:00:00Z", run_count: 1 });

    const result = await recordTeamRun("Article Team");

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.run_count).toBe(1);
    expect(queue.requests[0]).toMatchObject({
      url: "/api/teams/Article%20Team/record-run",
      method: "POST",
    });
  });

  it("treats a team_not_found record-run response as a plain failure, not a thrown error", async () => {
    queue.queueRecordRun(404, {
      error: { code: "not_found", message: "Team 'Ghost Team' not found." },
    });

    const result = await recordTeamRun("Ghost Team");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("not_found");
  });
});
