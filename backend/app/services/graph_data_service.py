"""Graph data aggregation service — assembles KnowledgeGraph from compilation results."""

import json
import logging
import re
from typing import Any
from collections import deque

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compile_job import CompileJob
from app.models.multi_agent import SemanticLink
from app.models.wiki import WikiPage, WikiLink

logger = logging.getLogger(__name__)

# Map entity types from Researcher output to NodeType enum
_ENTITY_TYPE_MAP = {
    "technology": "technology",
    "concept": "concept",
    "tool": "tool",
    "person": "person",
    "framework": "framework",
    "language": "language",
    "method": "method",
    "theory": "theory",
    "organization": "organization",
}


def _make_node_id(name: str) -> str:
    """Generate a stable, URL-safe node ID from entity name."""
    sanitized = re.sub(r'[^a-z0-9_]', '_', name.lower())
    # Collapse consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return "entity_" + sanitized


def _make_edge_id(source: str, target: str, relation_type: str) -> str:
    """Generate a stable edge ID."""
    return f"edge_{source}_{target}_{relation_type}"


def _compute_max_connected_component(nodes: list[dict], edges: list[dict]) -> int:
    """BFS to find the size of the largest connected component."""
    if not nodes:
        return 0
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        src = e["source"] if isinstance(e["source"], str) else e["source"].get("id", "")
        tgt = e["target"] if isinstance(e["target"], str) else e["target"].get("id", "")
        if src in adj and tgt in adj:
            adj[src].append(tgt)
            adj[tgt].append(src)

    visited: set[str] = set()
    max_size = 0
    for node_id in adj:
        if node_id in visited:
            continue
        queue = deque([node_id])
        visited.add(node_id)
        size = 0
        while queue:
            curr = queue.popleft()
            size += 1
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        max_size = max(max_size, size)
    return max_size


class GraphDataService:

    async def get_knowledge_graph(self, db: AsyncSession, job_id: str) -> dict:
        """Assemble the full knowledge graph from a completed compilation job."""
        job = await db.get(CompileJob, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if job.status != "done":
            raise ValueError(f"Job {job_id} is not completed (status={job.status})")

        # Parse integrated_knowledge (entities + relations from Integrator)
        ik = {}
        if job.integrated_knowledge:
            try:
                ik = json.loads(job.integrated_knowledge)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Job %s: corrupt integrated_knowledge JSON, graph will be partial", job_id)

        raw_entities = ik.get("entities", [])
        raw_relations = ik.get("relations", [])

        # Parse memo_ids with error handling
        try:
            memo_ids = json.loads(job.memo_ids) if job.memo_ids else []
        except (json.JSONDecodeError, TypeError):
            logger.warning("Job %s: corrupt memo_ids JSON", job_id)
            memo_ids = []

        # Get wiki pages created by this job (SQL-level filtering)
        wiki_pages = await self._get_wiki_pages_for_memos(db, memo_ids)

        # Get semantic links for these wiki pages (SQL-level filtering)
        page_slugs = [p.slug for p in wiki_pages]
        semantic_links = await self._get_semantic_links(db, page_slugs)

        # Get wiki links between these pages (SQL-level filtering)
        wiki_links = await self._get_wiki_links(db, page_slugs)

        # --- Build nodes ---
        nodes = {}
        for entity in raw_entities:
            name = entity.get("name", "")
            if not name:
                continue
            nid = _make_node_id(name)
            etype = _ENTITY_TYPE_MAP.get(entity.get("type", ""), "other")
            if nid in nodes:
                existing = nodes[nid]
                if len(entity.get("description", "")) > len(existing.get("description", "")):
                    existing["description"] = entity.get("description", "")
                existing["memoCount"] = max(existing["memoCount"], 1)
            else:
                nodes[nid] = {
                    "id": nid,
                    "label": name,
                    "type": etype,
                    "group": f"cluster_{etype}",
                    "weight": self._calc_entity_weight(entity, len(raw_entities)),
                    "memoCount": 1,
                    "description": entity.get("description", ""),
                    "sourceMemos": memo_ids,
                    "originalEntity": entity,
                }

        # Add wiki page nodes
        for page in wiki_pages:
            nid = f"wiki_{page.slug}"
            source_memo_ids = []
            try:
                source_memo_ids = json.loads(page.source_memo_ids or "[]")
            except (json.JSONDecodeError, TypeError):
                pass
            nodes[nid] = {
                "id": nid,
                "label": page.title,
                "type": page.wiki_type or "concept",
                "group": "wiki_pages",
                "weight": 0.6,
                "memoCount": len(source_memo_ids),
                "description": page.summary or "",
                "sourceMemos": source_memo_ids,
                "originalEntity": {"slug": page.slug, "title": page.title},
            }

        # --- Build edges ---
        edges = {}
        for rel in raw_relations:
            subj = rel.get("subject", "")
            obj = rel.get("object", "")
            if not subj or not obj:
                continue
            src_id = _make_node_id(subj)
            tgt_id = _make_node_id(obj)
            pred = rel.get("predicate", "relates_to")
            etype = self._map_relation_type(pred)
            eid = _make_edge_id(src_id, tgt_id, etype)
            if eid not in edges:
                edges[eid] = {
                    "id": eid,
                    "source": src_id,
                    "target": tgt_id,
                    "label": pred,
                    "type": etype,
                    "confidence": rel.get("confidence", 0.5),
                    "directed": True,
                }

        # Add semantic link edges
        for sl in semantic_links:
            src_id = f"wiki_{sl.source_slug}"
            tgt_id = f"wiki_{sl.target_slug}"
            eid = _make_edge_id(src_id, tgt_id, sl.relation_type or "relates_to")
            if eid not in edges:
                edges[eid] = {
                    "id": eid,
                    "source": src_id,
                    "target": tgt_id,
                    "label": sl.relation_type or "related",
                    "type": sl.relation_type or "relates_to",
                    "confidence": sl.confidence or 0.5,
                    "directed": True,
                }

        # Add wiki link edges (bidirectional [[links]])
        for wl in wiki_links:
            src_id = f"wiki_{wl.from_slug}"
            tgt_id = f"wiki_{wl.to_slug}"
            eid = _make_edge_id(src_id, tgt_id, "references")
            if eid not in edges:
                edges[eid] = {
                    "id": eid,
                    "source": src_id,
                    "target": tgt_id,
                    "label": "references",
                    "type": "references",
                    "confidence": 1.0,
                    "directed": True,
                }

        nodes_list = list(nodes.values())
        edges_list = list(edges.values())

        # Compute meta
        node_type_counts: dict[str, int] = {}
        for n in nodes_list:
            t = n["type"]
            node_type_counts[t] = node_type_counts.get(t, 0) + 1
        edge_type_counts: dict[str, int] = {}
        for e in edges_list:
            t = e["type"]
            edge_type_counts[t] = edge_type_counts.get(t, 0) + 1

        return {
            "nodes": nodes_list,
            "edges": edges_list,
            "meta": {
                "totalNodes": len(nodes_list),
                "totalEdges": len(edges_list),
                "nodeTypes": node_type_counts,
                "edgeTypes": edge_type_counts,
                "maxConnectedComponent": _compute_max_connected_component(nodes_list, edges_list),
                "compilationId": job_id,
                "compiledAt": (job.finished_at.isoformat() if job.finished_at else ""),
            },
        }

    async def get_aggregate_knowledge_graph(self, db: AsyncSession) -> dict:
        """Build a knowledge graph aggregating ALL completed compilation jobs."""
        result = await db.execute(
            select(CompileJob).where(
                CompileJob.status == "done",
                CompileJob.compile_type == "multi_agent",
            )
        )
        jobs = list(result.scalars().all())

        # Merge nodes and edges from all jobs
        merged_nodes: dict[str, dict] = {}
        merged_edges: dict[str, dict] = {}

        for job in jobs:
            ik = {}
            if job.integrated_knowledge:
                try:
                    ik = json.loads(job.integrated_knowledge)
                except (json.JSONDecodeError, TypeError):
                    continue

            raw_entities = ik.get("entities", [])
            raw_relations = ik.get("relations", [])

            try:
                memo_ids = json.loads(job.memo_ids) if job.memo_ids else []
            except (json.JSONDecodeError, TypeError):
                memo_ids = []

            for entity in raw_entities:
                name = entity.get("name", "")
                if not name:
                    continue
                nid = _make_node_id(name)
                etype = _ENTITY_TYPE_MAP.get(entity.get("type", ""), "other")
                if nid in merged_nodes:
                    existing = merged_nodes[nid]
                    if len(entity.get("description", "")) > len(existing.get("description", "")):
                        existing["description"] = entity.get("description", "")
                    existing["memoCount"] = max(existing["memoCount"], 1)
                    # Merge source memos
                    for mid in memo_ids:
                        if mid not in existing["sourceMemos"]:
                            existing["sourceMemos"].append(mid)
                else:
                    merged_nodes[nid] = {
                        "id": nid,
                        "label": name,
                        "type": etype,
                        "group": f"cluster_{etype}",
                        "weight": self._calc_entity_weight(entity, len(raw_entities)),
                        "memoCount": 1,
                        "description": entity.get("description", ""),
                        "sourceMemos": list(memo_ids),
                        "originalEntity": entity,
                    }

            for rel in raw_relations:
                subj = rel.get("subject", "")
                obj = rel.get("object", "")
                if not subj or not obj:
                    continue
                src_id = _make_node_id(subj)
                tgt_id = _make_node_id(obj)
                pred = rel.get("predicate", "relates_to")
                etype = self._map_relation_type(pred)
                eid = _make_edge_id(src_id, tgt_id, etype)
                if eid not in merged_edges:
                    merged_edges[eid] = {
                        "id": eid,
                        "source": src_id,
                        "target": tgt_id,
                        "label": pred,
                        "type": etype,
                        "confidence": rel.get("confidence", 0.5),
                        "directed": True,
                    }

        # Add wiki page nodes and links
        wiki_pages = await self._get_all_wiki_pages(db)
        for page in wiki_pages:
            nid = f"wiki_{page.slug}"
            source_memo_ids = []
            try:
                source_memo_ids = json.loads(page.source_memo_ids or "[]")
            except (json.JSONDecodeError, TypeError):
                pass
            if nid not in merged_nodes:
                merged_nodes[nid] = {
                    "id": nid,
                    "label": page.title,
                    "type": page.wiki_type or "concept",
                    "group": "wiki_pages",
                    "weight": 0.6,
                    "memoCount": len(source_memo_ids),
                    "description": page.summary or "",
                    "sourceMemos": source_memo_ids,
                    "originalEntity": {"slug": page.slug, "title": page.title},
                }

        all_slugs = [p.slug for p in wiki_pages]
        semantic_links = await self._get_semantic_links(db, all_slugs)
        wiki_links = await self._get_wiki_links(db, all_slugs)

        for sl in semantic_links:
            src_id = f"wiki_{sl.source_slug}"
            tgt_id = f"wiki_{sl.target_slug}"
            eid = _make_edge_id(src_id, tgt_id, sl.relation_type or "relates_to")
            if eid not in merged_edges:
                merged_edges[eid] = {
                    "id": eid,
                    "source": src_id,
                    "target": tgt_id,
                    "label": sl.relation_type or "related",
                    "type": sl.relation_type or "relates_to",
                    "confidence": sl.confidence or 0.5,
                    "directed": True,
                }

        for wl in wiki_links:
            src_id = f"wiki_{wl.from_slug}"
            tgt_id = f"wiki_{wl.to_slug}"
            eid = _make_edge_id(src_id, tgt_id, "references")
            if eid not in merged_edges:
                merged_edges[eid] = {
                    "id": eid,
                    "source": src_id,
                    "target": tgt_id,
                    "label": "references",
                    "type": "references",
                    "confidence": 1.0,
                    "directed": True,
                }

        nodes_list = list(merged_nodes.values())
        edges_list = list(merged_edges.values())

        node_type_counts: dict[str, int] = {}
        for n in nodes_list:
            t = n["type"]
            node_type_counts[t] = node_type_counts.get(t, 0) + 1
        edge_type_counts: dict[str, int] = {}
        for e in edges_list:
            t = e["type"]
            edge_type_counts[t] = edge_type_counts.get(t, 0) + 1

        return {
            "nodes": nodes_list,
            "edges": edges_list,
            "meta": {
                "totalNodes": len(nodes_list),
                "totalEdges": len(edges_list),
                "nodeTypes": node_type_counts,
                "edgeTypes": edge_type_counts,
                "maxConnectedComponent": _compute_max_connected_component(nodes_list, edges_list),
                "compilationId": "aggregate",
                "compiledAt": (jobs[-1].finished_at.isoformat() if jobs and jobs[-1].finished_at else ""),
                "totalJobs": len(jobs),
            },
        }

    async def get_node_detail(
        self, db: AsyncSession, job_id: str, node_id: str
    ) -> dict | None:
        """Get a single node with its related edges and wiki pages."""
        graph = await self.get_knowledge_graph(db, job_id)
        node = None
        for n in graph["nodes"]:
            if n["id"] == node_id:
                node = n
                break
        if not node:
            return None

        related_edges = [
            e for e in graph["edges"]
            if e["source"] == node_id or e["target"] == node_id
        ]

        # Build node label lookup for O(1) access
        node_label_map = {n["id"]: n["label"] for n in graph["nodes"]}

        # Find related wiki pages
        related_wikis = []
        for e in related_edges:
            other_id = e["target"] if e["source"] == node_id else e["source"]
            if other_id.startswith("wiki_"):
                other_node = next(
                    (n for n in graph["nodes"] if n["id"] == other_id), None
                )
                if other_node:
                    slug = other_node.get("originalEntity", {}).get("slug", "")
                    related_wikis.append({"slug": slug, "title": other_node["label"]})

        return {
            **node,
            "relatedEdges": related_edges,
            "relatedWikis": related_wikis,
        }

    async def search_nodes(
        self, db: AsyncSession, job_id: str, keyword: str
    ) -> list[dict]:
        """Search nodes by label (fuzzy match)."""
        graph = await self.get_knowledge_graph(db, job_id)
        kw = keyword.lower()
        return [n for n in graph["nodes"] if kw in n["label"].lower()]

    async def filter_subgraph(
        self,
        db: AsyncSession,
        job_id: str,
        node_types: list[str] | None = None,
        edge_types: list[str] | None = None,
    ) -> dict:
        """Filter graph by node/edge types."""
        graph = await self.get_knowledge_graph(db, job_id)
        if node_types:
            type_set = set(node_types)
            graph["nodes"] = [n for n in graph["nodes"] if n["type"] in type_set]
        node_ids = {n["id"] for n in graph["nodes"]}
        if edge_types:
            etype_set = set(edge_types)
            graph["edges"] = [
                e for e in graph["edges"]
                if e["type"] in etype_set
                and e["source"] in node_ids
                and e["target"] in node_ids
            ]
        else:
            graph["edges"] = [
                e for e in graph["edges"]
                if e["source"] in node_ids and e["target"] in node_ids
            ]
        graph["meta"]["totalNodes"] = len(graph["nodes"])
        graph["meta"]["totalEdges"] = len(graph["edges"])
        return graph

    # --- Private helpers ---

    def _calc_entity_weight(self, entity: dict, total: int) -> float:
        """Calculate node weight (0~1) based on description length and entity count."""
        # No confidence field in researcher output; use description length as signal
        desc_len = len(entity.get("description", ""))
        desc_factor = min(1.0, desc_len / 200.0)
        count_factor = min(1.0, 10.0 / max(total, 1))
        return min(1.0, desc_factor * 0.6 + count_factor * 0.4)

    def _map_relation_type(self, predicate: str) -> str:
        """Map Chinese/English predicate to EdgeType enum value."""
        pred = predicate.lower().strip()
        mapping = {
            "属于": "belongs_to", "belongs_to": "belongs_to",
            "用于": "used_for", "used_for": "used_for",
            "依赖": "depends_on", "depends_on": "depends_on",
            "相似": "similar_to", "similar_to": "similar_to",
            "关联": "relates_to", "relates_to": "relates_to",
            "衍生": "derived_from", "derived_from": "derived_from",
            "实现": "implements", "implements": "implements",
            "引用": "references", "references": "references",
            "prerequisite": "depends_on",
            "extended_by": "derived_from",
            "contradicted_by": "relates_to",
            "referenced_by": "references",
        }
        return mapping.get(pred, "relates_to")

    async def _get_all_wiki_pages(self, db: AsyncSession) -> list[WikiPage]:
        """Get all wiki pages."""
        result = await db.execute(select(WikiPage))
        return list(result.scalars().all())

    async def _get_wiki_pages_for_memos(
        self, db: AsyncSession, memo_ids: list[str]
    ) -> list[WikiPage]:
        """Get wiki pages whose source_memo_ids overlap with the given memo IDs."""
        if not memo_ids:
            return []
        # SQL-level LIKE filtering instead of full table scan
        conditions = []
        for mid in memo_ids:
            conditions.append(WikiPage.source_memo_ids.like(f'%"{mid}"%'))
        stmt = select(WikiPage).where(or_(*conditions))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_semantic_links(
        self, db: AsyncSession, slugs: list[str]
    ) -> list[SemanticLink]:
        """Get semantic links where source or target is in the given slugs."""
        if not slugs:
            return []
        stmt = select(SemanticLink).where(
            or_(
                SemanticLink.source_slug.in_(slugs),
                SemanticLink.target_slug.in_(slugs),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_wiki_links(
        self, db: AsyncSession, slugs: list[str]
    ) -> list[WikiLink]:
        """Get wiki links where from_slug or to_slug is in the given slugs."""
        if not slugs:
            return []
        stmt = select(WikiLink).where(
            or_(
                WikiLink.from_slug.in_(slugs),
                WikiLink.to_slug.in_(slugs),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


graph_data_service = GraphDataService()
