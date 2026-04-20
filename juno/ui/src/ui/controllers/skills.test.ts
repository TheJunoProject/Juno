import { describe, expect, it, vi } from "vitest";
import {
  installSkill,
  loadJunoHubDetail,
  saveSkillApiKey,
  searchJunoHub,
  setJunoHubSearchQuery,
  updateSkillEnabled,
  type SkillsState,
} from "./skills.ts";

function createState(): { state: SkillsState; request: ReturnType<typeof vi.fn> } {
  const request = vi.fn();
  const state: SkillsState = {
    client: {
      request,
    } as unknown as SkillsState["client"],
    connected: true,
    skillsLoading: false,
    skillsReport: null,
    skillsError: null,
    skillsBusyKey: null,
    skillEdits: {},
    skillMessages: {},
    junohubSearchQuery: "github",
    junohubSearchResults: [
      {
        score: 0.9,
        slug: "github",
        displayName: "GitHub",
        summary: "Previous result",
        version: "1.0.0",
      },
    ],
    junohubSearchLoading: false,
    junohubSearchError: "old error",
    junohubDetail: null,
    junohubDetailSlug: null,
    junohubDetailLoading: false,
    junohubDetailError: null,
    junohubInstallSlug: null,
    junohubInstallMessage: null,
  };
  return { state, request };
}

function createDeferredRequestQueue(request: ReturnType<typeof vi.fn>) {
  const resolvers: Array<(value: unknown) => void> = [];
  request.mockImplementation(
    () =>
      new Promise((resolve) => {
        resolvers.push(resolve);
      }),
  );
  return {
    resolveNext(value: unknown) {
      resolvers.shift()?.(value);
    },
  };
}

function mockSkillMutationRequests(request: ReturnType<typeof vi.fn>, installMessage?: string) {
  request.mockImplementation(async (method: string) => {
    if (method === "skills.install" && installMessage) {
      return { message: installMessage };
    }
    return {};
  });
}

describe("searchJunoHub", () => {
  it("clears stale query state immediately when the input changes", () => {
    const { state } = createState();

    state.junohubSearchLoading = true;
    state.junohubInstallMessage = { kind: "success", text: "Installed github" };

    setJunoHubSearchQuery(state, "github app");

    expect(state.junohubSearchQuery).toBe("github app");
    expect(state.junohubSearchResults).toBeNull();
    expect(state.junohubSearchError).toBeNull();
    expect(state.junohubSearchLoading).toBe(false);
    expect(state.junohubInstallMessage).toBeNull();
  });

  it("clears stale results as soon as a new search starts", async () => {
    const { state, request } = createState();
    type SearchResponse = { results: SkillsState["junohubSearchResults"] };
    let resolveRequest: (value: SearchResponse) => void = () => {
      throw new Error("expected search request promise to be pending");
    };
    request.mockImplementation(
      () =>
        new Promise<SearchResponse>((resolve) => {
          resolveRequest = resolve;
        }),
    );

    const pending = searchJunoHub(state, "github");

    expect(state.junohubSearchResults).toBeNull();
    expect(state.junohubSearchLoading).toBe(true);
    expect(state.junohubSearchError).toBeNull();

    resolveRequest({
      results: [
        {
          score: 0.95,
          slug: "github-new",
          displayName: "GitHub New",
          summary: "Fresh result",
          version: "2.0.0",
        },
      ],
    });
    await pending;

    expect(state.junohubSearchResults).toEqual([
      {
        score: 0.95,
        slug: "github-new",
        displayName: "GitHub New",
        summary: "Fresh result",
        version: "2.0.0",
      },
    ]);
    expect(state.junohubSearchLoading).toBe(false);
  });

  it("clears stale results when the query is emptied", async () => {
    const { state, request } = createState();

    await searchJunoHub(state, "   ");

    expect(request).not.toHaveBeenCalled();
    expect(state.junohubSearchResults).toBeNull();
    expect(state.junohubSearchError).toBeNull();
    expect(state.junohubSearchLoading).toBe(false);
  });

  it("ignores stale search responses after query changes", async () => {
    const { state, request } = createState();
    const queue = createDeferredRequestQueue(request);

    const pending = searchJunoHub(state, "github");
    setJunoHubSearchQuery(state, "gitlab");
    queue.resolveNext({
      results: [{ score: 1, slug: "github", displayName: "GitHub" }],
    });
    await pending;

    expect(state.junohubSearchQuery).toBe("gitlab");
    expect(state.junohubSearchResults).toBeNull();
    expect(state.junohubSearchError).toBeNull();
    expect(state.junohubSearchLoading).toBe(false);
  });
});

describe("loadJunoHubDetail", () => {
  it("ignores stale detail responses after slug changes", async () => {
    const { state, request } = createState();
    const queue = createDeferredRequestQueue(request);

    const firstPending = loadJunoHubDetail(state, "github");
    const secondPending = loadJunoHubDetail(state, "gitlab");

    queue.resolveNext({
      skill: { slug: "github", displayName: "GitHub", createdAt: 1, updatedAt: 2 },
    });
    await firstPending;

    queue.resolveNext({
      skill: { slug: "gitlab", displayName: "GitLab", createdAt: 3, updatedAt: 4 },
    });
    await secondPending;

    expect(state.junohubDetailLoading).toBe(false);
    expect(state.junohubDetail?.skill?.slug).toBe("gitlab");
  });
});

describe("skill mutations", () => {
  it.each([
    {
      name: "updates skill enablement and records a success message",
      run: (state: SkillsState) => updateSkillEnabled(state, "github", true),
      expectedRequest: ["skills.update", { skillKey: "github", enabled: true }],
      expectedMessage: "Skill enabled",
    },
    {
      name: "saves API keys and reports success",
      run: async (state: SkillsState) => {
        state.skillEdits.github = "sk-test";
        await saveSkillApiKey(state, "github");
      },
      expectedRequest: ["skills.update", { skillKey: "github", apiKey: "sk-test" }],
      expectedMessage: "API key saved — stored in juno.json (skills.entries.github)",
    },
    {
      name: "installs skills and uses server success messages",
      run: (state: SkillsState) => installSkill(state, "github", "GitHub", "install-123", true),
      expectedRequest: [
        "skills.install",
        {
          name: "GitHub",
          installId: "install-123",
          dangerouslyForceUnsafeInstall: true,
          timeoutMs: 120000,
        },
      ],
      expectedMessage: "Installed from registry",
      installMessage: "Installed from registry",
    },
  ])("$name", async ({ run, expectedRequest, expectedMessage, installMessage }) => {
    const { state, request } = createState();
    mockSkillMutationRequests(request, installMessage);

    await run(state);

    const [method, params] = expectedRequest;
    expect(request).toHaveBeenCalledWith(method, params);
    expect(state.skillMessages.github).toEqual({ kind: "success", message: expectedMessage });
    expect(state.skillsBusyKey).toBeNull();
    expect(state.skillsError).toBeNull();
  });

  it("records errors from failed mutations", async () => {
    const { state, request } = createState();
    request.mockRejectedValue(new Error("skills update failed"));

    await updateSkillEnabled(state, "github", false);

    expect(state.skillsError).toBe("skills update failed");
    expect(state.skillMessages.github).toEqual({
      kind: "error",
      message: "skills update failed",
    });
    expect(state.skillsBusyKey).toBeNull();
  });
});
