"""GIS Research Agent — Researches GIS data, methods, and best practices."""

from agents.base_agent import SpecializedAgent


class GISResearchAgent(SpecializedAgent):
    """Research agent for finding GIS data sources, methods, and documentation."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_gis_research",
            name="GIS Research Agent",
            description="Researches GIS data and methods.",
            instructions=(
                "You research GIS topics: data sources, processing methods, best practices, "
                "algorithm parameters, CRS information, and documentation. Use web search "
                "tools and the QGIS algorithm discovery to find answers. Always cite sources."
            ),
            permission_level="read",
            max_steps=10,
            db=db,
            domain="research",
            tool_namespace="qgis.algorithms",
        )

    async def execute(self, task: dict) -> dict:
        """Execute a research task."""
        action = task.get("action", "research")
        request = task.get("request", "")
        context = task.get("context", {})

        self.add_to_history("user", f"Research: {request}", {"action": action})

        if action == "research":
            result = await self._research_topic(request, context)
        elif action == "find_algorithms":
            result = await self._find_algorithms(request, context)
        elif action == "find_data_sources":
            result = await self._find_data_sources(request, context)
        elif action == "explain_concept":
            result = await self._explain_concept(request, context)
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _research_topic(self, topic: str, context: dict) -> dict:
        """Research a GIS topic."""
        # Use algorithm discovery to find relevant algorithms
        try:
            algorithms_result = await self.call_tool(
                "qgis.algorithms.discover",
                {}
            )
            algorithms = algorithms_result.get("result", {}).get("algorithms", [])
        except Exception as exc:
            algorithms = []
            algorithms_result = {"error": str(exc)}

        # Filter algorithms related to the topic
        topic_lower = topic.lower()
        relevant = [
            a for a in algorithms
            if any(kw in a.lower() for kw in topic_lower.split())
        ][:20]

        return {
            "topic": topic,
            "relevant_algorithms": relevant,
            "total_algorithms_searched": len(algorithms),
            "note": "Use qgis.algorithms.execute with specific algorithm IDs for detailed parameters",
        }

    async def _find_algorithms(self, keywords: str, context: dict) -> dict:
        """Find QGIS processing algorithms matching keywords."""
        try:
            result = await self.call_tool("qgis.algorithms.discover", {})
            algorithms = result.get("result", {}).get("algorithms", [])
        except Exception as exc:
            return {"error": str(exc), "algorithms": []}

        keywords_lower = [k.strip().lower() for k in keywords.split(",")]
        matches = [
            a for a in algorithms
            if any(kw in a.lower() for kw in keywords_lower)
        ]

        return {
            "keywords": keywords,
            "matches": matches[:30],
            "count": len(matches),
        }

    async def _find_data_sources(self, query: str, context: dict) -> dict:
        """Find data sources for a given query."""
        # This would typically use web search - for now return guidance
        return {
            "query": query,
            "suggested_sources": [
                "Natural Earth Data (naturalearthdata.com)",
                "OpenStreetMap (overpass-turbo.eu)",
                "NASA Earth Data (earthdata.nasa.gov)",
                "ESRI Open Data Hub",
                "National geospatial portals",
                "QGIS Browser panel for local/WFS/WMS sources",
            ],
            "search_tips": [
                "Use qgis.layers.load with WFS/WMS URLs",
                "Search for 'open data portal' + your region",
                "Check government GIS clearinghouses",
            ],
        }

    async def _explain_concept(self, concept: str, context: dict) -> dict:
        """Explain a GIS concept."""
        return {
            "concept": concept,
            "explanation": f"Research agent would provide detailed explanation of '{concept}' using documentation and best practices.",
            "related_tools": self.get_domain_tools()[:10],
        }