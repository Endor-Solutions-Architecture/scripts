"""All GraphQL for the bridge lives here.

Eight operations against https://api.linear.app/graphql. Linear API keys go in
the Authorization header raw -- no Bearer prefix. Every mutation nests a
`success` boolean, and a false value is an error even though HTTP said 200.

Retry policy: 429 and 5xx get jittered exponential backoff in-process, then
surface as LinearTransientError so the caller can return 503 and let Endor
retry at 1h/2h/4h. 4xx is a configuration problem and is never retried.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Awaitable, Callable, Iterable, Sequence

import httpx

RATE_LIMIT_REMAINING_HEADER = "X-RateLimit-Requests-Remaining"

DEFAULT_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 4.0, 15.0)
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class LinearError(Exception):
    """Base class for Linear API failures."""


class LinearRequestError(LinearError):
    """Linear rejected the request. Retrying will not help."""


class LinearTransientError(LinearError):
    """Linear was rate limited or unavailable after in-process retries."""


_TEAMS = """
query Teams { teams(first: 250) { nodes { id key name } } }
"""

_WORKFLOW_STATES = """
query States($teamId: ID!) {
  workflowStates(filter: { team: { id: { eq: $teamId } } }, first: 250) {
    nodes { id name type }
  }
}
"""

_ISSUE_LABELS = """
query Labels($teamId: ID!) {
  issueLabels(filter: { team: { id: { eq: $teamId } } }, first: 250) {
    nodes { id name }
  }
}
"""

_ISSUE_LABEL_CREATE = """
mutation LabelCreate($input: IssueLabelCreateInput!) {
  issueLabelCreate(input: $input) { success issueLabel { id name } }
}
"""

_ISSUE_CREATE = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) { success issue { id identifier } }
}
"""

_ISSUE_UPDATE = """
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) { success issue { id identifier } }
}
"""

_COMMENT_CREATE = """
mutation CommentCreate($input: CommentCreateInput!) {
  commentCreate(input: $input) { success }
}
"""

_SEARCH_ISSUES = """
query SearchIssues($term: String!, $first: Int!) {
  searchIssues(term: $term, first: $first) {
    nodes { id identifier description }
  }
}
"""


class LinearClient:
    def __init__(
        self,
        api_key: str,
        api_url: str,
        client: httpx.AsyncClient | None = None,
        max_attempts: int = 3,
        backoff_seconds: Sequence[float] = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key
        self._api_url = api_url
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = client is None
        self._max_attempts = max_attempts
        self._backoff = tuple(backoff_seconds)
        self._sleep = sleep
        self.last_rate_limit_remaining: int | None = None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _backoff_delay(self, attempt: int) -> float:
        base = self._backoff[min(attempt, len(self._backoff) - 1)]
        return base * (0.5 + random.random())

    def _record_rate_limit(self, response: httpx.Response) -> None:
        raw = response.headers.get(RATE_LIMIT_REMAINING_HEADER)
        if raw is None:
            return
        try:
            self.last_rate_limit_remaining = int(raw)
        except ValueError:
            self.last_rate_limit_remaining = None

    async def execute(self, document: str, variables: dict[str, Any]) -> dict[str, Any]:
        """POST a GraphQL document, retrying transient failures, and return `data`."""
        payload = {"query": document, "variables": variables}
        headers = {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }

        last_detail = "no attempts made"
        for attempt in range(self._max_attempts):
            try:
                response = await self._client.post(
                    self._api_url, json=payload, headers=headers
                )
            except httpx.HTTPError as exc:
                last_detail = f"transport error: {exc}"
            else:
                self._record_rate_limit(response)

                if response.status_code in RETRYABLE_STATUS:
                    last_detail = f"HTTP {response.status_code}"
                elif response.status_code >= 400:
                    raise LinearRequestError(
                        f"Linear returned HTTP {response.status_code}: "
                        f"{response.text[:500]}"
                    )
                else:
                    return self._unwrap(response)

            if attempt < self._max_attempts - 1:
                await self._sleep(self._backoff_delay(attempt))

        raise LinearTransientError(
            f"Linear unavailable after {self._max_attempts} attempts ({last_detail})"
        )

    @staticmethod
    def _unwrap(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise LinearRequestError(
                f"Linear returned a non-JSON body: {response.text[:200]}"
            ) from exc

        if body.get("errors"):
            messages = "; ".join(
                str(err.get("message", err)) for err in body["errors"]
            )
            raise LinearRequestError(f"Linear GraphQL error: {messages}")

        data = body.get("data")
        if data is None:
            raise LinearRequestError("Linear response contained no data")
        return data

    @staticmethod
    def _require_success(data: dict[str, Any], field: str) -> dict[str, Any]:
        payload = data.get(field) or {}
        if not payload.get("success"):
            raise LinearRequestError(f"Linear {field} reported success: false")
        return payload

    async def teams(self) -> list[dict[str, Any]]:
        data = await self.execute(_TEAMS, {})
        return list(data["teams"]["nodes"])

    async def workflow_states(self, team_id: str) -> list[dict[str, Any]]:
        data = await self.execute(_WORKFLOW_STATES, {"teamId": team_id})
        return list(data["workflowStates"]["nodes"])

    async def issue_labels(self, team_id: str) -> list[dict[str, Any]]:
        data = await self.execute(_ISSUE_LABELS, {"teamId": team_id})
        return list(data["issueLabels"]["nodes"])

    async def create_issue_label(self, team_id: str, name: str) -> dict[str, Any]:
        data = await self.execute(
            _ISSUE_LABEL_CREATE, {"input": {"teamId": team_id, "name": name}}
        )
        return self._require_success(data, "issueLabelCreate")["issueLabel"]

    async def create_issue(
        self,
        *,
        team_id: str,
        title: str,
        description: str,
        parent_id: str | None = None,
        state_id: str | None = None,
        priority: int | None = None,
        label_ids: Iterable[str] = (),
    ) -> dict[str, Any]:
        issue_input: dict[str, Any] = {
            "teamId": team_id,
            "title": title,
            "description": description,
        }
        if parent_id:
            issue_input["parentId"] = parent_id
        if state_id:
            issue_input["stateId"] = state_id
        if priority is not None:
            issue_input["priority"] = priority
        label_list = list(label_ids)
        if label_list:
            issue_input["labelIds"] = label_list

        data = await self.execute(_ISSUE_CREATE, {"input": issue_input})
        return self._require_success(data, "issueCreate")["issue"]

    async def update_issue(
        self,
        issue_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        state_id: str | None = None,
        priority: int | None = None,
        label_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Update an issue. Only explicitly provided fields are sent.

        label_ids is a full replacement in Linear: passing an empty iterable
        clears every label, which is why it is distinguished from None.
        """
        issue_input: dict[str, Any] = {}
        if title is not None:
            issue_input["title"] = title
        if description is not None:
            issue_input["description"] = description
        if state_id is not None:
            issue_input["stateId"] = state_id
        if priority is not None:
            issue_input["priority"] = priority
        if label_ids is not None:
            issue_input["labelIds"] = list(label_ids)

        data = await self.execute(
            _ISSUE_UPDATE, {"id": issue_id, "input": issue_input}
        )
        return self._require_success(data, "issueUpdate")["issue"]

    async def create_comment(self, issue_id: str, body: str) -> None:
        data = await self.execute(
            _COMMENT_CREATE, {"input": {"issueId": issue_id, "body": body}}
        )
        self._require_success(data, "commentCreate")

    async def search_issues(self, query: str, first: int = 10) -> list[dict[str, Any]]:
        data = await self.execute(_SEARCH_ISSUES, {"term": query, "first": first})
        return list(data["searchIssues"]["nodes"])
