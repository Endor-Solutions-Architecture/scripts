#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import subprocess
import shlex


@dataclass
class PackageVersionInfo:
	id: Optional[str]
	uuid: Optional[str]
	name: Optional[str]
	namespace: Optional[str]
	meta_uuid: Optional[str]
	meta_parent_uuid: Optional[str]
	spec_project_uuid: Optional[str]
	relative_path: Optional[str]


class EndorClient:
	def __init__(self, timeout_seconds: int = 30, debug: bool = False) -> None:
		self.timeout_seconds = timeout_seconds
		self.debug = debug

	def _run_endorctl(self, args: List[str], *, parse_json: bool = True) -> Any:
		cmd = " ".join(shlex.quote(a) for a in ["endorctl", *args])
		if self.debug:
			print(f"DEBUG endorctl: {cmd}")
		proc = subprocess.run(
			cmd,
			shell=True,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
			timeout=self.timeout_seconds,
		)
		if self.debug:
			print(f"DEBUG endorctl exit={proc.returncode}")
			if proc.stderr:
				print(f"DEBUG endorctl stderr: {proc.stderr.strip()[:2000]}")
		if proc.returncode != 0:
			raise RuntimeError(f"endorctl failed: {proc.stderr.strip() or proc.stdout.strip()} (code {proc.returncode})")
		out = proc.stdout.strip()
		if not parse_json:
			return out
		if not out:
			return None
		try:
			return json.loads(out)
		except json.JSONDecodeError as exc:
			raise RuntimeError(f"Failed to parse endorctl JSON output: {exc}: {out[:2000]}")

	# ------------------------
	# Scan profile retrieval via endorctl
	# ------------------------
	def get_scan_profile_by_uuid(self, namespace: str, scan_profile_uuid: str) -> Dict[str, Any]:
		args = ["-n", namespace, "api", "get", "-r", "ScanProfile", f"--uuid={scan_profile_uuid}"]
		data = self._run_endorctl(args, parse_json=True)
		return data

	def get_package_version_by_uuid(self, namespace: str, pv_uuid: str) -> "PackageVersionInfo":
		args = ["-n", namespace, "api", "get", "-r", "PackageVersion", f"--uuid={pv_uuid}"]
		data = self._run_endorctl(args, parse_json=True)
		# Some outputs might wrap the object; attempt common shapes
		node: Dict[str, Any] = {}
		if isinstance(data, dict):
			if "object" in data and isinstance(data["object"], dict):
				node = data["object"]
			else:
				node = data
		return self._parse_package_version_node(node)

	@staticmethod
	def extract_exclude_patterns(scan_profile: Dict[str, Any]) -> List[str]:
		candidates: List[str] = []
		# Only read from spec.automated_scan_parameters.excluded_paths
		spec = scan_profile.get("spec")
		if isinstance(spec, str):
			try:
				spec = json.loads(spec)
			except Exception:
				spec = {}
		if isinstance(spec, dict):
			asp = spec.get("automated_scan_parameters")
			if isinstance(asp, dict):
				value = asp.get("excluded_paths")
				if isinstance(value, list):
					candidates.extend([str(v) for v in value])
		# Normalize, dedupe, keep ordering
		seen = set()
		normalized: List[str] = []
		for p in candidates:
			p = p.strip()
			if not p or p in seen:
				continue
			seen.add(p)
			normalized.append(p)
		return normalized

	# ------------------------
	# PackageVersion listing via endorctl
	# ------------------------
	def list_package_versions(self, namespace: str, project_uuid: Optional[str]) -> Iterable["PackageVersionInfo"]:
		filter_expr = "context.type==CONTEXT_TYPE_MAIN"
		if project_uuid:
			filter_expr += f" and spec.project_uuid=={project_uuid}"
		args = [
			"-n", namespace,
			"api", "list",
			"-r", "PackageVersion",
			"--list-all",
			f"--filter={filter_expr}",
		]
		data = self._run_endorctl(args, parse_json=True)
		items: List[Dict[str, Any]] = []
		if isinstance(data, dict):
			lst = data.get("list")
			if isinstance(lst, dict):
				objs = lst.get("objects")
				if isinstance(objs, list):
					items = objs
		# Fallbacks for other shapes if needed
		if not items:
			if isinstance(data, list):
				items = data
			elif isinstance(data, dict):
				items = data.get("items", []) or data.get("results", []) or data.get("nodes", []) or []
		for node in items:
			yield self._parse_package_version_node(node)

	@staticmethod
	def _parse_package_version_node(node: Dict[str, Any]) -> "PackageVersionInfo":
		def get_nested(dct: Dict[str, Any], path: List[str]) -> Optional[Any]:
			cur: Any = dct
			for k in path:
				if not isinstance(cur, dict) or k not in cur:
					return None
				cur = cur[k]
			return cur

		pv_id = node.get("id") or node.get("uuid") or node.get("uid")
		uuid_val = node.get("uuid") or node.get("id") or node.get("uid")
		name = (
			get_nested(node, ["meta", "name"]) or node.get("name") or get_nested(node, ["metadata", "name"])  # type: ignore
		)
		namespace = (
			get_nested(node, ["tenantMeta", "namespace"]) or get_nested(node, ["tenant_meta", "namespace"]) or node.get("namespace")
		)
		meta_uuid = (
			get_nested(node, ["meta", "uuid"]) or get_nested(node, ["metadata", "uuid"]) or None
		)
		meta_parent_uuid = (
			get_nested(node, ["meta", "parent_uuid"]) or get_nested(node, ["metadata", "parent_uuid"]) or None
		)
		spec_project_uuid = None
		relative_path = None
		spec = node.get("spec") or {}
		if isinstance(spec, dict):
			spec_project_uuid = spec.get("project_uuid")
			relative_path = spec.get("relative_path") or spec.get("relativePath")

		return PackageVersionInfo(
			id=str(pv_id) if pv_id is not None else None,
			uuid=str(uuid_val) if uuid_val is not None else None,
			name=str(name) if name is not None else None,
			namespace=str(namespace) if namespace is not None else None,
			meta_uuid=str(meta_uuid) if meta_uuid is not None else None,
			meta_parent_uuid=str(meta_parent_uuid) if meta_parent_uuid is not None else None,
			spec_project_uuid=str(spec_project_uuid) if spec_project_uuid is not None else None,
			relative_path=str(relative_path) if relative_path is not None else None,
		)

	# ------------------------
	# Deletion via endorctl
	# ------------------------
	def delete_package_version(self, namespace: str, pv: PackageVersionInfo) -> Tuple[bool, str]:
		uuid = pv.uuid or pv.id
		if not uuid:
			return False, "No id/uuid for deletion"
		args = ["-n", namespace, "api", "delete", "-r", "PackageVersion", f"--uuid={uuid}"]
		try:
			self._run_endorctl(args, parse_json=False)
			return True, "deleted"
		except Exception as exc:
			return False, str(exc)


# ------------------------
# Pattern matching helpers
# ------------------------
class PatternMatcher:
	def __init__(self, patterns: List[str], debug: bool = False) -> None:
		self._compiled: List[Tuple[str, Any]] = []
		self.debug = debug
		for p in patterns:
			p = self._normalize_pattern(p)
			if not p:
				continue
			regex = fnmatch_translate_posix(p)
			self._compiled.append((p, re.compile(regex)))

	def matches_any(self, path: str) -> bool:
		path = self._normalize_path(path)
		for pat, rgx in self._compiled:
			matched = bool(rgx.search(path))
			if self.debug:
				print(f"DEBUG compare: pattern='{pat}' path='{path}' -> {matched}", flush=True)
			if matched:
				if not self.debug:
					print(f"MATCH pattern='{pat}' path='{path}'", flush=True)
				return True
		return False

	@staticmethod
	def _normalize_path(path: str) -> str:
		path = path.replace("\\", "/")
		while path.startswith("./"):
			path = path[2:]
		if path.startswith("/"):
			path = path[1:]
		return path

	@staticmethod
	def _normalize_pattern(pat: str) -> str:
		pat = (pat or "").strip()
		pat = pat.replace("\\", "/")
		while pat.startswith("./"):
			pat = pat[2:]
		if pat.startswith("/"):
			pat = pat[1:]
		return pat


def fnmatch_translate_posix(pat: str) -> str:
	import fnmatch

	regex = fnmatch.translate(pat)
	return regex


# ------------------------
# CLI
# ------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"Find PackageVersions whose dependency files match the provided scan profile's exclude-path patterns, "
			"and optionally delete them. Uses endorctl under the hood."
		)
	)
	parser.add_argument("namespace", help="Endor namespace to operate in")
	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument(
		"--scan-profile-uuid",
		help="Scan Profile UUID to source exclude-path patterns from",
	)
	group.add_argument(
		"--exclude-pattern",
		help="Single glob exclude pattern to use (quote to avoid shell expansion)",
	)
	parser.add_argument(
		"--project-uuid",
		help="Optional project UUID to filter PackageVersions where meta.parent_uuid matches",
	)
	parser.add_argument(
		"--no-dry-run",
		action="store_true",
		help="Actually delete matching PackageVersions (default: dry-run prints only)",
	)
	parser.add_argument(
		"--timeout",
		type=int,
		default=int(os.environ.get("ENDOR_API_TIMEOUT", "30")),
		help="Command timeout in seconds (default: 30)",
	)
	parser.add_argument(
		"--debug",
		action="store_true",
		help="Enable debug logging (prints endorctl commands)",
	)
	return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
	args = parse_args(argv)
	print(f"Using namespace: {args.namespace}")

	client = EndorClient(timeout_seconds=args.timeout, debug=args.debug)

	# Step 1: Determine patterns either from scan profile or from a provided pattern
	if args.exclude_pattern:
		print(f"Using provided excluded_pattern: '{args.exclude_pattern}'")
		patterns = [args.exclude_pattern]
		print(f"Found {len(patterns)} excluded_paths patterns in scan profile.")
	else:
		# Fetch scan profile by UUID and extract patterns
		try:
			sp = client.get_scan_profile_by_uuid(args.namespace, args.scan_profile_uuid)
		except Exception as exc:
			print(f"ERROR: Failed to fetch scan profile '{args.scan_profile_uuid}': {exc}", file=sys.stderr)
			return 2

		print(f"Retrieving excluded_paths from scan_profile with uuid: {args.scan_profile_uuid}")
		patterns = client.extract_exclude_patterns(sp)
		print(f"Found {len(patterns)} excluded_paths patterns in scan profile.")
		if not patterns:
			print("No exclude-path patterns found in the scan profile. Nothing to do.")
			return 0

	matcher = PatternMatcher(patterns, debug=args.debug)

	# Step 2: List PackageVersions and find matches (endorctl filter + code guard)
	if args.project_uuid:
		print(f"Retrieving package_versions for project with uuid: {args.project_uuid}")
	else:
		print("Retrieving package_versions for all projects")
	pvs = list(client.list_package_versions(args.namespace, args.project_uuid))
	print(f"Found {len(pvs)} package_versions")
	# Hydrate dependency_files by fetching full objects when list output lacks them
	for i, pv in enumerate(pvs):
		if not pv.relative_path:
			try:
				if args.debug:
					print(f"DEBUG hydrating relative_path for pv uuid={pv.uuid or pv.id}", flush=True)
				full_pv = client.get_package_version_by_uuid(args.namespace, (pv.uuid or pv.id or ""))
				pvs[i] = full_pv
			except Exception as exc:
				if args.debug:
					print(f"DEBUG failed to hydrate pv uuid={pv.uuid or pv.id}: {exc}", flush=True)
				# keep original pv if hydration fails

	matches: List[PackageVersionInfo] = []
	total = 0
	print("Checking package_versions against excluded_path patterns")
	for pv in pvs:
		total += 1
		if args.project_uuid and (pv.spec_project_uuid != args.project_uuid):
			continue
		path = pv.relative_path or ""
		if not path:
			if args.debug:
				ns = pv.namespace or args.namespace
				uid = pv.uuid or pv.id or "<unknown>"
				name = pv.name or "<unnamed>"
				print(f"DEBUG pv namespace={ns} uuid={uid} name=\"{name}\" has empty relative_path", flush=True)
			continue
		if args.debug:
			print(f"DEBUG check relative_path='{path}'", flush=True)
		if matcher.matches_any(path):
			matches.append(pv)

	# Step 3/4: Print and optionally delete
	if not matches:
		print(f"Scanned {total} PackageVersions; 0 matched exclude-path patterns.")
		return 0

	print(f"Found {len(matches)} PackageVersions (of {total}) with dependency_files matching exclude patterns:")
	for pv in matches:
		ns = pv.namespace or args.namespace
		uid = pv.uuid or pv.id or "<unknown>"
		name = pv.name or "<unnamed>"
		print(f"- namespace={ns} uuid={uid} name=\"{name}\"")

	if not args.no_dry_run:
		print("Dry run: no deletions performed. Pass --no-dry-run to delete the above PackageVersions.")
		return 0

	failures: List[Tuple[PackageVersionInfo, str]] = []
	for pv in matches:
		ok, msg = client.delete_package_version(args.namespace, pv)
		ns = pv.namespace or args.namespace
		uid = pv.uuid or pv.id or "<unknown>"
		name = pv.name or "<unnamed>"
		if ok:
			print(f"DELETED: namespace={ns} uuid={uid} name=\"{name}\" -> {msg}")
		else:
			print(f"FAILED DELETE: namespace={ns} uuid={uid} name=\"{name}\" -> {msg}")
			failures.append((pv, msg))

	if failures:
		print(f"Completed with {len(failures)} failures out of {len(matches)} deletions.", file=sys.stderr)
		return 1

	print("Completed deletions successfully.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main()) 