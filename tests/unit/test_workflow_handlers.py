"""Tests for workflow node handlers (mcp_tool, agent, api)."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import json

from workflows.workflow_engine import WorkflowEngine
from core.exceptions import WorkflowError


class TestWorkflowHandlers:
    """Test the three critical node handlers."""

    @pytest.fixture
    def mock_db(self):
        """Mock database."""
        db = Mock()
        db.fetchone = Mock(return_value=None)
        db.fetchall = Mock(return_value=[])
        db.execute = Mock()
        return db

    @pytest.fixture
    def mock_job_manager(self):
        """Mock job manager."""
        jm = Mock()
        jm.create_job = Mock(return_value="job_test123")
        jm.start_job = Mock()
        jm.complete_job = Mock()
        jm.fail_job = Mock()
        jm.cancel_job = Mock()
        jm.get_job = Mock(return_value={"id": "job_test123", "status": "completed"})
        return jm

    @pytest.fixture
    def mock_mcp_client(self):
        """Mock MCP client (QgisBridgeClient)."""
        client = Mock()
        client.dispatch = Mock(return_value={"status": "success", "result": "layer loaded"})
        return client

    @pytest.fixture
    def mock_agent_manager(self):
        """Mock agent manager."""
        manager = Mock()
        agent = Mock()
        agent.execute_task = AsyncMock(return_value={"status": "completed", "output": "agent result"})
        manager.get_agent = Mock(return_value=agent)
        return manager

    @pytest.fixture
    def mock_api_client(self):
        """Mock async HTTP client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def workflow_engine(self, mock_db, mock_job_manager, mock_mcp_client, mock_agent_manager, mock_api_client):
        """Create WorkflowEngine with mocked dependencies."""
        engine = WorkflowEngine(
            db=mock_db,
            job_manager=mock_job_manager,
            cluster_registry=None,
            mcp_client=mock_mcp_client,
            agent_manager=mock_agent_manager,
            api_client=mock_api_client,
        )
        return engine

    def test_mcp_tool_handler_success(self, workflow_engine, mock_mcp_client):
        """Test MCP tool handler calls dispatch correctly."""
        config = {
            "tool": "qgis.layers.load",
            "params": {"path": "/data/test.gpkg"},
            "use_context": True,
        }
        context = {"outputs": {"previous_step": {"layer_id": "layer_1"}}}
        
        result = workflow_engine._mcp_tool_handler(config, context)
        
        # Verify dispatch was called with merged params
        mock_mcp_client.dispatch.assert_called_once()
        call_args = mock_mcp_client.dispatch.call_args
        assert call_args.kwargs["tool"] == "qgis.layers.load"
        assert call_args.kwargs["params"]["path"] == "/data/test.gpkg"
        assert "request_id" in call_args.kwargs
        assert result == {"status": "success", "result": "layer loaded"}

    def test_mcp_tool_handler_no_client_raises(self, workflow_engine):
        """Test MCP tool handler raises when no client."""
        workflow_engine.mcp_client = None
        config = {"tool": "qgis.layers.load", "params": {}}
        context = {}
        
        with pytest.raises(WorkflowError, match="No MCP client available"):
            workflow_engine._mcp_tool_handler(config, context)

    def test_mcp_tool_handler_no_tool_raises(self, workflow_engine):
        """Test MCP tool handler raises when tool not specified."""
        config = {"params": {}}
        context = {}
        
        with pytest.raises(WorkflowError, match="tool is required"):
            workflow_engine._mcp_tool_handler(config, context)

    def test_agent_handler_success(self, workflow_engine, mock_agent_manager):
        """Test agent handler calls execute_task correctly."""
        config = {
            "agent_id": "agent_gis_research",
            "params": {"query": "find data"},
            "use_context": True,
        }
        context = {"outputs": {"previous_step": {"data": "some data"}}}
        
        result = workflow_engine._agent_handler(config, context)
        
        # Verify agent was retrieved and executed
        mock_agent_manager.get_agent.assert_called_once_with("agent_gis_research")
        assert result == {"status": "completed", "output": "agent result"}

    def test_agent_handler_no_manager_raises(self, workflow_engine):
        """Test agent handler raises when no agent manager."""
        workflow_engine.agent_manager = None
        config = {"agent_id": "agent_test", "params": {}}
        context = {}
        
        with pytest.raises(WorkflowError, match="No agent manager available"):
            workflow_engine._agent_handler(config, context)

    def test_agent_handler_no_agent_id_raises(self, workflow_engine):
        """Test agent handler raises when agent_id not specified."""
        config = {"params": {}}
        context = {}
        
        with pytest.raises(WorkflowError, match="agent_id is required"):
            workflow_engine._agent_handler(config, context)

    def test_agent_handler_agent_not_found_raises(self, workflow_engine, mock_agent_manager):
        """Test agent handler raises when agent not found."""
        mock_agent_manager.get_agent.return_value = None
        config = {"agent_id": "nonexistent_agent", "params": {}}
        context = {}
        
        with pytest.raises(WorkflowError, match="Agent nonexistent_agent not found"):
            workflow_engine._agent_handler(config, context)

    @pytest.mark.asyncio
    async def test_api_handler_openai_success(self, workflow_engine, mock_db, mock_api_client):
        """Test API handler for OpenAI provider."""
        # Mock database to return provider config
        mock_db.fetchone.return_value = {
            "id": "openai",
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "model_id": "gpt-4",
            "enabled": 1,
            "timeout_seconds": 60,
            "retry_count": 3,
        }
        
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value={
            "choices": [{"message": {"content": "API response content"}}]
        })
        mock_api_client.post = AsyncMock(return_value=mock_response)
        
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "prompt": "Analyze this data",
            "temperature": 0.5,
            "max_tokens": 1000,
        }
        context = {"outputs": {}}
        
        result = await workflow_engine._api_handler_async(config, context)
        
        assert result["content"] == "API response content"
        assert "raw" in result
        mock_api_client.post.assert_called_once()
        call_args = mock_api_client.post.call_args
        assert "chat/completions" in call_args.args[0]
        assert call_args.kwargs["json"]["model"] == "gpt-4"
        assert call_args.kwargs["json"]["messages"][0]["role"] == "user"
        assert call_args.kwargs["json"]["messages"][0]["content"] == "Analyze this data"

    @pytest.mark.asyncio
    async def test_api_handler_anthropic_success(self, workflow_engine, mock_db, mock_api_client):
        """Test API handler for Anthropic provider."""
        mock_db.fetchone.return_value = {
            "id": "anthropic",
            "name": "Anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "model_id": "claude-3-opus",
            "enabled": 1,
            "timeout_seconds": 60,
            "retry_count": 3,
        }
        
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value={
            "content": [{"text": "Claude response"}]
        })
        mock_api_client.post = AsyncMock(return_value=mock_response)
        
        config = {
            "provider": "anthropic",
            "model": "claude-3-opus",
            "prompt": "Hello Claude",
        }
        context = {}
        
        result = await workflow_engine._api_handler_async(config, context)
        
        assert result["content"] == "Claude response"
        call_args = mock_api_client.post.call_args
        assert "messages" in call_args.kwargs["json"]
        assert call_args.kwargs["json"]["model"] == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_api_handler_gemini_success(self, workflow_engine, mock_db, mock_api_client):
        """Test API handler for Gemini provider."""
        mock_db.fetchone.return_value = {
            "id": "gemini",
            "name": "Gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "model_id": "gemini-pro",
            "enabled": 1,
            "timeout_seconds": 60,
            "retry_count": 3,
        }
        
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value={
            "candidates": [{"content": {"parts": [{"text": "Gemini response"}]}}]
        })
        mock_api_client.post = AsyncMock(return_value=mock_response)
        
        config = {
            "provider": "gemini",
            "model": "gemini-pro",
            "prompt": "Hello Gemini",
        }
        context = {}
        
        result = await workflow_engine._api_handler_async(config, context)
        
        assert result["content"] == "Gemini response"

    @pytest.mark.asyncio
    async def test_api_handler_provider_not_found(self, workflow_engine, mock_db):
        """Test API handler raises when provider not found."""
        mock_db.fetchone.return_value = None
        
        config = {"provider": "unknown", "model": "test", "prompt": "test"}
        context = {}
        
        with pytest.raises(WorkflowError, match="API provider unknown not found"):
            await workflow_engine._api_handler_async(config, context)

    @pytest.mark.asyncio
    async def test_api_handler_no_model_raises(self, workflow_engine, mock_db):
        """Test API handler raises when model not specified."""
        mock_db.fetchone.return_value = {
            "id": "openai",
            "model_id": None,
            "enabled": 1,
        }
        
        config = {"provider": "openai", "prompt": "test"}
        context = {}
        
        with pytest.raises(WorkflowError, match="model is required"):
            await workflow_engine._api_handler_async(config, context)

    @pytest.mark.asyncio
    async def test_api_handler_no_prompt_raises(self, workflow_engine, mock_db):
        """Test API handler raises when prompt not specified."""
        mock_db.fetchone.return_value = {
            "id": "openai",
            "model_id": "gpt-4",
            "enabled": 1,
        }
        
        config = {"provider": "openai", "model": "gpt-4"}
        context = {}
        
        with pytest.raises(WorkflowError, match="prompt is required"):
            await workflow_engine._api_handler_async(config, context)

    @pytest.mark.asyncio
    async def test_api_handler_context_substitution(self, workflow_engine, mock_db, mock_api_client):
        """Test API handler substitutes context variables in prompt."""
        mock_db.fetchone.return_value = {
            "id": "openai",
            "model_id": "gpt-4",
            "enabled": 1,
            "base_url": "https://api.openai.com/v1",
        }
        
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value={
            "choices": [{"message": {"content": "response"}}]
        })
        mock_api_client.post = AsyncMock(return_value=mock_response)
        
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "prompt": "Analyze $previous_output",
            "use_context": True,
        }
        context = {"outputs": {"previous_step": {"previous_output": "some data"}}}
        
        result = await workflow_engine._api_handler_async(config, context)
        
        call_args = mock_api_client.post.call_args
        assert call_args.kwargs["json"]["messages"][0]["content"] == "Analyze some data"

    @pytest.mark.asyncio
    async def test_api_handler_retry_on_5xx(self, workflow_engine, mock_db, mock_api_client):
        """Test API handler retries on 5xx errors."""
        mock_db.fetchone.return_value = {
            "id": "openai",
            "model_id": "gpt-4",
            "enabled": 1,
            "base_url": "https://api.openai.com/v1",
            "timeout_seconds": 60,
            "retry_count": 2,
        }
        
        # First two calls fail with 500, third succeeds
        error_response = Mock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        
        success_response = Mock()
        success_response.raise_for_status = Mock()
        success_response.json = Mock(return_value={
            "choices": [{"message": {"content": "success after retry"}}]
        })
        
        mock_api_client.post = AsyncMock(side_effect=[
            Exception("500 error"),
            Exception("500 error"),
            success_response,
        ])
        
        # Need to patch httpx to raise HTTPStatusError properly
        import httpx
        error_exc = httpx.HTTPStatusError("500", request=Mock(), response=error_response)
        
        mock_api_client.post = AsyncMock(side_effect=[
            error_exc,
            error_exc,
            success_response,
        ])
        
        config = {"provider": "openai", "model": "gpt-4", "prompt": "test"}
        context = {}
        
        result = await workflow_engine._api_handler_async(config, context)
        
        assert result["content"] == "success after retry"
        assert mock_api_client.post.call_count == 3

    def test_sync_api_handler_wrapper(self, workflow_engine, mock_db, mock_api_client):
        """Test sync wrapper calls async handler."""
        mock_db.fetchone.return_value = {
            "id": "openai",
            "model_id": "gpt-4",
            "enabled": 1,
            "base_url": "https://api.openai.com/v1",
        }
        
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value={
            "choices": [{"message": {"content": "sync response"}}]
        })
        mock_api_client.post = AsyncMock(return_value=mock_response)
        
        config = {"provider": "openai", "model": "gpt-4", "prompt": "test"}
        context = {}
        
        result = workflow_engine._api_handler(config, context)
        
        assert result["content"] == "sync response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])