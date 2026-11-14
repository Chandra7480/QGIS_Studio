"""Database Agent — GeoPackage, PostGIS, spatial SQL."""

from agents.base_agent import SpecializedAgent


class DatabaseAgent(SpecializedAgent):
    """Agent for spatial databases: GeoPackage, PostGIS, SpatiaLite, spatial SQL."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_database",
            name="Database Agent",
            description="GeoPackage, PostGIS, spatial SQL.",
            instructions=(
                "You manage spatial databases: GeoPackage, PostGIS, SpatiaLite connections, "
                "spatial SQL queries, data import/export, and database administration. "
                "Use qgis.database.info and processing algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="database",
            tool_namespace="qgis.database",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "query")
        params = task.get("params", {})

        self.add_to_history("user", f"Database: {action}", {"action": action})

        if action == "query":
            result = await self._query(params)
        elif action == "info":
            result = await self._info()
        elif action == "import":
            result = await self._import(params)
        elif action == "export":
            result = await self._export(params)
        elif action == "execute_sql":
            result = await self._execute_sql(params)
        elif action == "list_operations":
            result = {"operations": ["query", "info", "import", "export", "execute_sql"]}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _query(self, params: dict) -> dict:
        """Run spatial query."""
        sql = params.get("sql")
        connection = params.get("connection")
        if not sql:
            return {"error": "Missing SQL query"}
        return {
            "note": "Direct SQL execution requires bridge support for database connections. "
                   "Use qgis.algorithms.execute with native:executesql for GeoPackage.",
            "sql": sql,
            "connection": connection,
        }

    async def _info(self) -> dict:
        """List database connections."""
        return await self.call_tool("qgis.database.info", {})

    async def _import(self, params: dict) -> dict:
        """Import layer to database."""
        layer = params.get("layer")
        connection = params.get("connection")
        table = params.get("table")
        if not layer or not connection or not table:
            return {"error": "Missing layer, connection, or table"}
        return await self._run_algorithm("native:importintopostgis", params)

    async def _export(self, params: dict) -> dict:
        """Export database table to file."""
        connection = params.get("connection")
        table = params.get("table")
        output = params.get("output")
        if not connection or not table or not output:
            return {"error": "Missing connection, table, or output"}
        return await self._run_algorithm("native:exporttopostgis", params)

    async def _execute_sql(self, params: dict) -> dict:
        """Execute SQL on GeoPackage."""
        database = params.get("database")
        sql = params.get("sql")
        if not database or not sql:
            return {"error": "Missing database or sql"}
        return await self._run_algorithm("native:executesql", params)

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": params}
        )