# ADR-003: HTTPX Transport and Ownership

- **Status:** Accepted
- **Date:** 2026-09-02

## Context

SupaDL needs asynchronous streaming, explicit timeout behavior, bounded redirects, TLS
verification, connection pooling, and future HTTP/2 support. Domain code must remain free of
transport dependencies, and no global client may obscure resource ownership or shutdown.

## Decision

Use the stable HTTPX 0.28 release line with its HTTP/2 extra. HTTP implementation remains in
`supadl.transfer`; `supadl.domain` does not import HTTPX.

Create clients only through `create_http_client`. The factory configures separate connect,
read, write, and pool timeouts; a redirect cap; a declared SupaDL user agent; identity content
encoding; HTTP/2; TLS verification; and no implicit environment proxy/netrc behavior. Every
initial and redirected request URL is revalidated before transmission.

The constructing application scope owns each client and closes it explicitly or through an
async context manager. Services receive the client through constructor injection and do not
close a client they did not create. Probe responses use streaming contexts and close without
buffering the resource body.

## Consequences

- HTTPX and its HTTP/2 dependencies become runtime requirements.
- Tests can inject `MockTransport` or use the deterministic local fixture server without
  public network access.
- Redirect URLs cannot introduce unsupported schemes or embedded credentials unnoticed.
- Environment proxy and custom-certificate support require a future explicit, validated
  product setting rather than inheriting process state silently.
- HTTPX's pool limit is only a defensive global ceiling. Per-origin concurrency enforcement
  remains deferred to SUP-403.
- Probe metadata is serialization-ready; durable SQLite storage remains deferred to SUP-201.
