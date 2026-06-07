"""Tests for agent system."""

import pytest
from unittest.mock import Mock

from termmind.agents.engine import (
    Agent, AgentPersona, WorkflowEngine,
    RESEARCHER, CODER, REVIEWER, WRITER, ARCHITECT
)


class MockAPIClient:
    def chat(self, messages):
        return f"Mock response to: {messages[-1]['content'][:50]}"


class TestAgentPersona:
    def test_persona_creation(self):
        p = AgentPersona(
            name="test",
            role="test role",
            system_prompt="You are a test",
            capabilities=["cap1", "cap2"]
        )
        assert p.name == "test"
        assert p.capabilities == ["cap1", "cap2"]


class TestAgent:
    def test_creation(self):
        client = MockAPIClient()
        agent = Agent(RESEARCHER, client)
        assert agent.persona.name == "researcher"
        assert agent.turns == 0
    
    def test_run(self):
        client = MockAPIClient()
        agent = Agent(CODER, client)
        result = agent.run("Write a function")
        assert "Mock response" in result
        assert agent.turns == 1
    
    def test_memory(self):
        client = MockAPIClient()
        agent = Agent(CODER, client)
        agent.remember("key", "value")
        assert agent.recall("key") == "value"
    
    def test_reset(self):
        client = MockAPIClient()
        agent = Agent(CODER, client)
        agent.run("task")
        agent.remember("k", "v")
        agent.reset()
        assert agent.turns == 0
        assert len(agent.state) == 0
    
    def test_max_turns(self):
        client = MockAPIClient()
        agent = Agent(CODER, client)
        agent.turns = agent.persona.max_turns
        result = agent.run("should fail")
        assert "Max turns reached" in result


class TestWorkflowEngine:
    def test_register_agent(self):
        engine = WorkflowEngine()
        client = MockAPIClient()
        agent = Agent(RESEARCHER, client)
        engine.register_agent(agent)
        assert "researcher" in engine.list_agents()
    
    def test_define_workflow(self):
        engine = WorkflowEngine()
        engine.define_workflow("test", ["a", "b"])
        assert "test" in engine.list_workflows()
    
    def test_run_workflow(self):
        engine = WorkflowEngine()
        client = MockAPIClient()
        
        r = Agent(RESEARCHER, client)
        c = Agent(CODER, client)
        engine.register_agent(r)
        engine.register_agent(c)
        engine.define_workflow("rc", ["researcher", "coder"])
        
        result = engine.run_workflow("rc", "Build API")
        assert "results" in result
        assert "final_output" in result
        assert "researcher" in result["results"]
        assert "coder" in result["results"]
    
    def test_save_load_state(self, tmp_path):
        engine = WorkflowEngine()
        engine.define_workflow("test", ["a"])
        
        path = tmp_path / "state.json"
        engine.save_state(str(path))
        
        engine2 = WorkflowEngine()
        engine2.load_state(str(path))
        assert "test" in engine2.list_workflows()


class TestBuiltInPersonas:
    def test_all_personas(self):
        personas = [RESEARCHER, CODER, REVIEWER, WRITER, ARCHITECT]
        for p in personas:
            assert p.name
            assert p.role
            assert p.system_prompt
            assert p.capabilities
