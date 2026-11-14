"""Tests for workflow DAG execution, pause/resume, condition, loop, approval, validation."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import json

from workflows.workflow_engine import WorkflowEngine, WorkflowState, StepExecution
from core.exceptions import WorkflowError


class TestWorkflowDAGExecution:
    """Test DAG-based parallel workflow execution."""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.fetchone = Mock(return_value=None)
        db.fetchall = Mock(return_value=[])
        db.execute = Mock()
        return db

    @pytest.fixture
    def mock_job_manager(self):
        jm = Mock()
        jm.create_job = Mock(return_value="job_test123")
        jm.start_job = Mock()
        jm.complete_job = Mock()
        jm.fail_job = Mock()
        jm.cancel_job = Mock()
        jm.get_job = Mock(return_value={"id": "job_test123", "status": "completed"})
        jm.update_status = Mock()
        return jm

    @pytest.fixture
    def mock_mcp_client(self):
        client = Mock()
        client.dispatch = Mock(return_value={"status": "success", "layer_id": "layer_1"})
        return client

    @pytest.fixture
    def mock_agent_manager(self):
        manager = Mock()
        agent = Mock()
        agent.execute_task = AsyncMock(return_value={"status": "completed", "output": "agent result"})
        manager.get_agent = Mock(return_value=agent)
        return manager

    @pytest.fixture
    def mock_api_client(self):
        return AsyncMock()

    @pytest.fixture
    def mock_approval_manager(self):
        am = Mock()
        am.request = Mock(return_value="approval_abc123")
        am.is_approved = Mock(return_value=True)
        am.decide = Mock()
        return am

    @pytest.fixture
    def workflow_engine(self, mock_db, mock_job_manager, mock_mcp_client, mock_agent_manager, mock_api_client, mock_approval_manager):
        engine = WorkflowEngine(
            db=mock_db,
            job_manager=mock_job_manager,
            cluster_registry=None,
            mcp_client=mock_mcp_client,
            agent_manager=mock_agent_manager,
            api_client=mock_api_client,
            approval_manager=mock_approval_manager,
        )
        return engine

    def test_build_dag_simple(self, workflow_engine):
        """Test building DAG from linear steps."""
        steps = [
            {"id": "step1", "step_index": 0, "type": "start", "config": {}},
            {"id": "step2", "step_index": 1, "type": "mcp_tool", "config": {"tool": "qgis.layers.load", "depends_on": ["step1"]}},
            {"id": "step3", "step_index": 2, "type": "end", "config": {"depends_on": ["step2"]}},
        ]
        
        step_map = workflow_engine._build_dag(steps)
        
        assert len(step_map) == 3
        assert step_map["step1"].depends_on == []
        assert step_map["step2"].depends_on == ["step1"]
        assert step_map["step3"].depends_on == ["step2"]

    def test_build_dag_parallel(self, workflow_engine):
        """Test building DAG with parallel branches."""
        steps = [
            {"id": "start", "step_index": 0, "type": "start", "config": {}},
            {"id": "branch1", "step_index": 1, "type": "mcp_tool", "config": {"tool": "tool1", "depends_on": ["start"]}},
            {"id": "branch2", "step_index": 2, "type": "mcp_tool", "config": {"tool": "tool2", "depends_on": ["start"]}},
            {"id": "merge", "step_index": 3, "type": "end", "config": {"depends_on": ["branch1", "branch2"]}},
        ]
        
        step_map = workflow_engine._build_dag(steps)
        levels = workflow_engine._topological_sort(step_map)
        
        # Should have 3 levels: [start], [branch1, branch2], [merge]
        assert len(levels) == 3
        assert levels[0] == ["start"]
        assert set(levels[1]) == {"branch1", "branch2"}
        assert levels[2] == ["merge"]

    def test_topological_sort_cycle_detection(self, workflow_engine):
        """Test cycle detection in DAG."""
        steps = [
            {"id": "a", "step_index": 0, "type": "mcp_tool", "config": {"depends_on": ["c"]}},
            {"id": "b", "step_index": 1, "type": "mcp_tool", "config": {"depends_on": ["a"]}},
            {"id": "c", "step_index": 2, "type": "mcp_tool", "config": {"depends_on": ["b"]}},
        ]
        
        step_map = workflow_engine._build_dag(steps)
        
        with pytest.raises(WorkflowError, match="Circular dependency"):
            workflow_engine._topological_sort(step_map)

    def test_run_dag_parallel_execution(self, workflow_engine, mock_mcp_client):
        """Test parallel execution of independent steps."""
        wf = {
            "id": "wf_test",
            "steps": [
                {"id": "start", "step_index": 0, "type": "start", "config": {}},
                {"id": "parallel1", "step_index": 1, "type": "mcp_tool", "config": {"tool": "tool1", "depends_on": ["start"]}},
                {"id": "parallel2", "step_index": 2, "type": "mcp_tool", "config": {"tool": "tool2", "depends_on": ["start"]}},
                {"id": "end", "step_index": 3, "type": "end", "config": {"depends_on": ["parallel1", "parallel2"]}},
            ]
        }
        
        # Mock dispatch to return different results for each tool
        mock_mcp_client.dispatch.side_effect = [
            {"status": "success", "tool": "tool1", "result": "data1"},
            {"status": "success", "tool": "tool2", "result": "data2"},
        ]
        
        result = workflow_engine._run_dag(wf, {"input": "test"}, "job_test123")
        
        assert result["status"] == "completed"
        assert "parallel1" in result["outputs"]
        assert "parallel2" in result["outputs"]
        assert result["outputs"]["parallel1"]["result"] == "data1"
        assert result["outputs"]["parallel2"]["result"] == "data2"
        # Both parallel steps should have been called
        assert mock_mcp_client.dispatch.call_count == 2

    def test_run_dag_sequential_dependencies(self, workflow_engine, mock_mcp_client):
        """Test sequential execution when steps depend on each other."""
        wf = {
            "id": "wf_test",
            "steps": [
                {"id": "step1", "step_index": 0, "type": "mcp_tool", "config": {"tool": "tool1", "depends_on": []}},
                {"id": "step2", "step_index": 1, "type": "mcp_tool", "config": {"tool": "tool2", "depends_on": ["step1"]}},
                {"id": "step3", "step_index": 2, "type": "mcp_tool", "config": {"tool": "tool3", "depends_on": ["step2"]}},
            ]
        }
        
        mock_mcp_client.dispatch.side_effect = [
            {"result": "step1_out"},
            {"result": "step2_out"},
            {"result": "step3_out"},
        ]
        
        result = workflow_engine._run_dag(wf, {}, "job_test123")
        
        assert result["status"] == "completed"
        assert mock_mcp_client.dispatch.call_count == 3
        # Results should be in order
        assert result["outputs"]["step1"]["result"] == "step1_out"
        assert result["outputs"]["step2"]["result"] == "step2_out"
        assert result["outputs"]["step3"]["result"] == "step3_out"

    def test_flatten_outputs(self, workflow_engine):
        """Test flattening nested outputs for context access."""
        outputs = {
            "step1": {"layer_id": "layer_1", "count": 10},
            "step2": {"feature_count": 100},
            "step3": "simple_value",
        }
        
        flat = workflow_engine._flatten_outputs(outputs)
        
        assert flat["layer_id"] == "layer_1"
        assert flat["count"] == 10
        assert flat["feature_count"] == 100
        assert flat["step3"] == "simple_value"


class TestWorkflowConditionNode:
    """Test condition node with JMESPath expressions."""

    @pytest.fixture
    def workflow_engine(self):
        engine = WorkflowEngine(
            db=Mock(), job_manager=Mock(), cluster_registry=None,
            mcp_client=None, agent_manager=None, api_client=None, approval_manager=None
        )
        return engine

    def test_condition_simple_true(self, workflow_engine):
        """Test condition with simple true expression."""
        config = {"expression": "count > 5"}
        context = {"outputs": {"step1": {"count": 10}}}
        
        result = workflow_engine._condition_handler(config, context)
        
        assert result["proceed"] is True
        assert result["evaluation"] is True  # Boolean result of comparison

    def test_condition_simple_false(self, workflow_engine):
        """Test condition with false expression."""
        config = {"expression": "count > 5"}
        context = {"outputs": {"step1": {"count": 3}}}
        
        result = workflow_engine._condition_handler(config, context)
        
        assert result["proceed"] is False
        assert result["evaluation"] is False  # Boolean result of comparison

    def test_condition_jmespath_path(self, workflow_engine):
        """Test condition with JMESPath path expression."""
        # Flatten outputs: {"step1": {"result": {"success": True}}} -> {"result": {"success": True}}
        config = {"expression": "result.success"}
        context = {"outputs": {"step1": {"result": {"success": True, "data": "ok"}}}}
        
        result = workflow_engine._condition_handler(config, context)
        
        assert result["proceed"] is True

    def test_condition_no_expression(self, workflow_engine):
        """Test condition with no expression defaults to proceed."""
        config = {}
        context = {}
        
        result = workflow_engine._condition_handler(config, context)
        
        assert result["proceed"] is True


class TestWorkflowLoopNode:
    """Test loop node execution."""

    @pytest.fixture
    def workflow_engine(self):
        engine = WorkflowEngine(
            db=Mock(), job_manager=Mock(), cluster_registry=None,
            mcp_client=None, agent_manager=None, api_client=None, approval_manager=None
        )
        return engine

    def test_loop_fixed_iterations(self, workflow_engine):
        """Test loop with fixed iteration count."""
        config = {
            "max_iterations": 3,
            "body": [
                {"id": "inner", "type": "mcp_tool", "config": {"tool": "process_item"}}
            ],
            "iterator_var": "item",
        }
        context = {"outputs": {}}
        
        # Mock the node handler to return predictable results
        with patch.object(workflow_engine, '_node_handler') as mock_handler:
            mock_handler.return_value = lambda c, ctx: {"processed": True}
            
            result = workflow_engine._loop_handler(config, context)
        
        assert result["status"] == "loop_done"
        assert result["iterations"] == 3
        assert len(result["results"]) == 3

    def test_loop_iterator_from_context(self, workflow_engine):
        """Test loop iterating over array from context."""
        # Flatten outputs: {"step1": {"items": ["a", "b", "c"]}} -> {"items": ["a", "b", "c"]}
        config = {
            "max_iterations": 10,
            "iterator": "items",
            "iterator_var": "item",
            "body": [
                {"id": "process", "type": "mcp_tool", "config": {"tool": "process"}}
            ],
        }
        context = {"outputs": {"step1": {"items": ["a", "b", "c"]}}}
        
        with patch.object(workflow_engine, '_node_handler') as mock_handler:
            mock_handler.return_value = lambda c, ctx: {"processed": ctx.get("item")}
            
            result = workflow_engine._loop_handler(config, context)
        
        assert result["iterations"] == 3
        assert result["results"][0]["item"] == "a"
        assert result["results"][1]["item"] == "b"
        assert result["results"][2]["item"] == "c"


class TestWorkflowApprovalNode:
    """Test approval node integration."""

    @pytest.fixture
    def mock_approval_manager(self):
        am = Mock()
        am.request = Mock(return_value="approval_abc123")
        am.is_approved = Mock(return_value=False)
        am.decide = Mock()
        return am

    @pytest.fixture
    def workflow_engine(self, mock_approval_manager):
        engine = WorkflowEngine(
            db=Mock(), job_manager=Mock(), cluster_registry=None,
            mcp_client=None, agent_manager=None, api_client=None,
            approval_manager=mock_approval_manager
        )
        return engine

    def test_approval_creates_request(self, workflow_engine, mock_approval_manager):
        """Test approval node creates approval request."""
        config = {
            "action_type": "delete_layer",
            "target": "layer_123",
            "message": "Confirm layer deletion",
        }
        context = {}
        
        result = workflow_engine._approval_handler(config, context)
        
        assert result["status"] == "approval_required"
        assert result["approval_id"] == "approval_abc123"
        mock_approval_manager.request.assert_called_once_with(
            "delete_layer", "layer_123", "system"
        )

    def test_approval_no_manager_raises(self, workflow_engine):
        """Test approval raises when no approval manager."""
        workflow_engine.approval_manager = None
        config = {"action_type": "test"}
        context = {}
        
        with pytest.raises(WorkflowError, match="No approval manager"):
            workflow_engine._approval_handler(config, context)


class TestWorkflowValidationNode:
    """Test validation node with JMESPath expressions."""

    @pytest.fixture
    def workflow_engine(self):
        engine = WorkflowEngine(
            db=Mock(), job_manager=Mock(), cluster_registry=None,
            mcp_client=None, agent_manager=None, api_client=None, approval_manager=None
        )
        return engine

    def test_validation_all_pass(self, workflow_engine):
        """Test validation with all checks passing."""
        config = {
            "validations": [
                {"name": "check_count", "expression": "count", "expected": 10},
                {"name": "check_success", "expression": "success", "expected": True},
            ]
        }
        context = {"outputs": {"step1": {"count": 10, "success": True}}}
        
        result = workflow_engine._validation_handler(config, context)
        
        assert result["passed"] is True
        assert result["results"]["check_count"]["passed"] is True
        assert result["results"]["check_success"]["passed"] is True

    def test_validation_some_fail(self, workflow_engine):
        """Test validation with some checks failing."""
        config = {
            "validations": [
                {"name": "check_count", "expression": "count", "expected": 10},
                {"name": "check_name", "expression": "name", "expected": "expected_name"},
            ]
        }
        context = {"outputs": {"step1": {"count": 10, "name": "actual_name"}}}
        
        result = workflow_engine._validation_handler(config, context)
        
        assert result["passed"] is False
        assert result["results"]["check_count"]["passed"] is True
        assert result["results"]["check_name"]["passed"] is False
        assert result["results"]["check_name"]["actual"] == "actual_name"
        assert result["results"]["check_name"]["expected"] == "expected_name"


class TestWorkflowPauseResume:
    """Test pause/resume/checkpoint functionality."""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.fetchone = Mock(return_value=None)
        db.fetchall = Mock(return_value=[])
        db.execute = Mock()
        return db

    @pytest.fixture
    def mock_job_manager(self):
        jm = Mock()
        jm.get_job = Mock(return_value={"id": "job_test", "status": "paused"})
        jm.update_status = Mock()
        jm.cancel_job = Mock()
        return jm

    @pytest.fixture
    def mock_approval_manager(self):
        am = Mock()
        am.is_approved = Mock(return_value=True)
        am.decide = Mock()
        return am

    @pytest.fixture
    def workflow_engine(self, mock_db, mock_job_manager, mock_approval_manager):
        engine = WorkflowEngine(
            db=mock_db, job_manager=mock_job_manager, cluster_registry=None,
            mcp_client=None, agent_manager=None, api_client=None,
            approval_manager=mock_approval_manager
        )
        return engine

    def test_save_and_load_state(self, workflow_engine, mock_db):
        """Test saving and loading workflow state."""
        context = {"input": {"test": "data"}, "outputs": {"step1": {"result": "ok"}}}
        completed = ["step1"]
        pending = ["step2", "step3"]
        
        workflow_engine._save_state("job_test", "wf_test", 1, context, completed, pending)
        
        # Verify DB call was made
        mock_db.execute.assert_called()
        
        # Mock load
        mock_db.fetchone.return_value = {
            "job_id": "job_test",
            "workflow_id": "wf_test",
            "step_index": 1,
            "context": json.dumps(context),
            "completed_steps": json.dumps(completed),
            "pending_steps": json.dumps(pending),
            "status": "running",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        
        state = workflow_engine._load_state("job_test")
        
        assert state.job_id == "job_test"
        assert state.workflow_id == "wf_test"
        assert state.step_index == 1
        assert state.completed_steps == ["step1"]
        assert state.pending_steps == ["step2", "step3"]
        assert state.workflow_id == "wf_test"
        assert state.step_index == 1
        assert state.completed_steps == ["step1"]
        assert state.pending_steps == ["step2", "step3"]

    def test_pause_workflow(self, workflow_engine, mock_job_manager):
        """Test pausing workflow."""
        workflow_engine._state_cache["job_test"] = WorkflowState(
            job_id="job_test", workflow_id="wf_test", step_index=1,
            context={}, completed_steps=["step1"], pending_steps=["step2"]
        )
        
        workflow_engine.pause("job_test", "approval_123")
        
        mock_job_manager.update_status.assert_called_with("job_test", "paused")
        state = workflow_engine._state_cache["job_test"]
        assert state.status == "paused"
        assert state.context["_pending_approval"] == "approval_123"

    def test_resume_workflow(self, workflow_engine, mock_job_manager):
        """Test resuming paused workflow."""
        workflow_engine._state_cache["job_test"] = WorkflowState(
            job_id="job_test", workflow_id="wf_test", step_index=1,
            context={"_pending_approval": "approval_123", "outputs": {}},
            completed_steps=["step1"], pending_steps=["step2"],
            status="paused"
        )
        
        # Mock get_workflow to return a simple workflow
        with patch.object(workflow_engine, 'get_workflow') as mock_get_wf:
            mock_get_wf.return_value = {
                "id": "wf_test",
                "steps": [
                    {"id": "step1", "step_index": 0, "type": "start", "config": {}},
                    {"id": "step2", "step_index": 1, "type": "end", "config": {}},
                ]
            }
            with patch.object(workflow_engine, '_resume_dag') as mock_resume_dag:
                mock_resume_dag.return_value = {"status": "completed", "outputs": {}}
                
                workflow_engine.resume("job_test")
        
        assert mock_job_manager.update_status.called
        mock_resume_dag.assert_called_once()

    def test_cancel_workflow(self, workflow_engine, mock_job_manager):
        """Test cancelling workflow."""
        workflow_engine._state_cache["job_test"] = WorkflowState(
            job_id="job_test", workflow_id="wf_test", step_index=1,
            context={}, completed_steps=["step1"], pending_steps=["step2"]
        )
        
        workflow_engine.cancel("job_test")
        
        mock_job_manager.cancel_job.assert_called_with("job_test")
        state = workflow_engine._state_cache["job_test"]
        assert state.status == "cancelled"


class TestWorkflowReportNode:
    """Test report node generation."""

    @pytest.fixture
    def workflow_engine(self):
        engine = WorkflowEngine(
            db=Mock(), job_manager=Mock(), cluster_registry=None,
            mcp_client=None, agent_manager=None, api_client=None, approval_manager=None
        )
        return engine

    def test_report_with_template(self, workflow_engine):
        """Test report generation with template."""
        config = {
            "template": "Layer $layer_id has $count features"
        }
        context = {"outputs": {"step1": {"layer_id": "layer_1", "count": 42}}}
        
        result = workflow_engine._report_handler(config, context)
        
        assert result["status"] == "report_generated"
        assert result["content"] == "Layer layer_1 has 42 features"

    def test_report_without_template(self, workflow_engine):
        """Test report generation without template (JSON dump)."""
        config = {}
        context = {"outputs": {"step1": {"result": "ok"}}}
        
        result = workflow_engine._report_handler(config, context)
        
        assert result["status"] == "report_generated"
        assert "step1" in result["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])