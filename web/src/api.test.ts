import { calculate } from "./api";
import { reply, sample } from "./test-data";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("sends POST /calculate with the question as JSON", async () => {
  fetchMock.mockResolvedValue(reply(200, sample));
  await calculate("15% de 3200");
  expect(fetchMock).toHaveBeenCalledWith(
    "/calculate",
    expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "15% de 3200" }),
    }),
  );
});

it("returns ok on 200", async () => {
  fetchMock.mockResolvedValue(reply(200, sample));
  expect(await calculate("q")).toEqual({ ok: sample });
});

it.each([
  [503, "not_configured"],
  [429, "rate_limited"],
  [502, "upstream_error"],
  [422, "refused"],
  [422, "truncated"],
  [422, "max_iterations"],
])("maps %i %s", async (status, code) => {
  fetchMock.mockResolvedValue(reply(status, { error: { code, message: "m" } }));
  expect(await calculate("q")).toEqual({ error: { code, message: "m" } });
});

it("maps FastAPI validation 422 to invalid_question", async () => {
  fetchMock.mockResolvedValue(reply(422, { detail: [{ msg: "too long" }] }));
  const outcome = await calculate("q");
  expect("error" in outcome && outcome.error.code).toBe("invalid_question");
});

it("maps rejected fetch to network_error", async () => {
  fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
  const outcome = await calculate("q");
  expect("error" in outcome && outcome.error.code).toBe("network_error");
});

it("maps non-JSON body to unexpected_response", async () => {
  fetchMock.mockResolvedValue(new Response("<html>", { status: 500 }));
  expect(await calculate("q")).toEqual({
    error: { code: "unexpected_response", message: "Resposta inesperada do servidor (HTTP 500)." },
  });
});

it("maps unknown JSON shape to unexpected_response", async () => {
  fetchMock.mockResolvedValue(reply(500, { oops: true }));
  const outcome = await calculate("q");
  expect("error" in outcome && outcome.error.code).toBe("unexpected_response");
});
