"""An in-memory stand-in for LinearClient.

Records every call in order so tests can assert on the sequence of GraphQL
operations, and stores issue state so adoption and search paths work.
"""

from __future__ import annotations

from typing import Any, Iterable


class FakeLinearClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.issues: dict[str, dict] = {}
        self.comments: dict[str, list[str]] = {}
        self._next_id = 0
        # Set to an exception instance to make the next mutation raise.
        self.fail_next_create: Exception | None = None

    def _new_id(self, prefix="i"):
        self._next_id += 1
        return f"{prefix}{self._next_id}"

    def call_names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def calls_named(self, name: str) -> list[dict]:
        return [payload for called, payload in self.calls if called == name]

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
        payload = dict(
            team_id=team_id,
            title=title,
            description=description,
            parent_id=parent_id,
            state_id=state_id,
            priority=priority,
            label_ids=tuple(label_ids),
        )
        self.calls.append(("create_issue", payload))

        if self.fail_next_create is not None:
            error = self.fail_next_create
            self.fail_next_create = None
            raise error

        issue_id = self._new_id()
        identifier = f"PLAT-{self._next_id}"
        self.issues[issue_id] = dict(
            id=issue_id,
            identifier=identifier,
            title=title,
            description=description,
            parent_id=parent_id,
            state_id=state_id,
            priority=priority,
            label_ids=tuple(label_ids),
        )
        return {"id": issue_id, "identifier": identifier}

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
        payload = dict(
            issue_id=issue_id,
            title=title,
            description=description,
            state_id=state_id,
            priority=priority,
            label_ids=None if label_ids is None else tuple(label_ids),
        )
        self.calls.append(("update_issue", payload))

        issue = self.issues.setdefault(
            issue_id, {"id": issue_id, "identifier": "PLAT-?"}
        )
        for key, value in (
            ("title", title),
            ("description", description),
            ("state_id", state_id),
            ("priority", priority),
        ):
            if value is not None:
                issue[key] = value
        if label_ids is not None:
            issue["label_ids"] = tuple(label_ids)
        return {"id": issue_id, "identifier": issue["identifier"]}

    async def create_comment(self, issue_id: str, body: str) -> None:
        self.calls.append(("create_comment", {"issue_id": issue_id, "body": body}))
        self.comments.setdefault(issue_id, []).append(body)

    async def search_issues(self, query: str, first: int = 10) -> list[dict[str, Any]]:
        self.calls.append(("search_issues", {"query": query}))
        return [
            {
                "id": issue["id"],
                "identifier": issue["identifier"],
                "description": issue.get("description", ""),
            }
            for issue in self.issues.values()
            if query in (issue.get("description") or "")
        ][:first]

    def seed_issue(self, *, description: str, identifier="PLAT-99") -> dict:
        """Insert an issue as if a previous crashed run had created it."""
        issue_id = self._new_id("seed")
        issue = dict(
            id=issue_id, identifier=identifier, description=description, title="seeded"
        )
        self.issues[issue_id] = issue
        return issue
