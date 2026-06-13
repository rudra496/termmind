"""Lightweight, zero-dependency Web UI server for TermMind."""

import json
import os
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingTCPServer
from typing import Any, Optional
from pathlib import Path

from rich.console import Console

from termmind.api import APIClient
from termmind.commands import handle_command
from termmind.config import load_config, save_config, PROVIDER_PRESETS
from termmind.knowledge.rag import VectorStore

# In-memory session data for the Web UI
session_messages: list[dict[str, str]] = []
session_cost: float = 0.0
session_tokens: int = 0
context_files: list[str] = []

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TermMind — Workspace Console</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0a0e1a;
            --bg-card: #111827;
            --bg-card-hover: #1a2332;
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --primary-glow: rgba(99, 102, 241, 0.25);
            --cyan: #06b6d4;
            --cyan-glow: rgba(6, 182, 212, 0.25);
            --border: #1e293b;
            --text: #e2e8f0;
            --text-muted: #94a3b8;
            --text-bright: #f8fafc;
            --green: #10b981;
            --red: #ef4444;
            --purple: #a855f7;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* Header */
        header {
            background: rgba(17, 24, 39, 0.8);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            z-index: 10;
        }

        .logo {
            font-size: 1.3rem;
            font-weight: 800;
            color: var(--text-bright);
            display: flex;
            align-items: center;
            gap: 10px;
            background: linear-gradient(135deg, #f8fafc, var(--primary), var(--cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header-stats {
            display: flex;
            gap: 24px;
        }

        .stat-badge {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .stat-badge .label {
            color: var(--text-muted);
        }

        .stat-badge .value {
            font-weight: 600;
            color: var(--cyan);
        }

        /* Main Workspace Layout */
        .workspace {
            display: flex;
            flex: 1;
            overflow: hidden;
        }

        /* Sidebar Settings */
        .sidebar {
            width: 300px;
            background: rgba(17, 24, 39, 0.5);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            padding: 20px;
            gap: 24px;
        }

        .sidebar-section {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .sidebar-section h3 {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            font-weight: 700;
            border-bottom: 1px solid var(--border);
            padding-bottom: 6px;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .form-group label {
            font-size: 0.8rem;
            color: var(--text-muted);
            font-weight: 500;
        }

        .form-control {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px;
            color: var(--text);
            font-family: inherit;
            font-size: 0.9rem;
            width: 100%;
            outline: none;
            transition: border-color 0.2s;
        }

        .form-control:focus {
            border-color: var(--primary);
        }

        .btn-action {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px;
            font-weight: 600;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 4px 12px var(--primary-glow);
            text-align: center;
        }

        .btn-action:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 16px var(--primary-glow);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            color: var(--text);
            box-shadow: none;
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.08);
            box-shadow: none;
        }

        /* Center Chat & Console area */
        .content-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: radial-gradient(circle at 50% 50%, rgba(99, 102, 241, 0.03) 0%, transparent 60%);
        }

        /* Tabs */
        .tabs-header {
            display: flex;
            border-bottom: 1px solid var(--border);
            background: rgba(17, 24, 39, 0.3);
            padding: 0 16px;
        }

        .tab-btn {
            padding: 14px 20px;
            background: none;
            border: none;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.9rem;
            cursor: pointer;
            position: relative;
            outline: none;
        }

        .tab-btn.active {
            color: var(--text-bright);
        }

        .tab-btn.active::after {
            content: '';
            position: absolute;
            bottom: -1px;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--primary);
        }

        .tab-content {
            flex: 1;
            display: none;
            flex-direction: column;
            overflow: hidden;
        }

        .tab-content.active {
            display: flex;
        }

        /* Chat Window */
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .message-bubble {
            max-width: 80%;
            padding: 16px 20px;
            border-radius: 12px;
            line-height: 1.6;
            font-size: 0.95rem;
            position: relative;
        }

        .message-bubble.user {
            background: rgba(99, 102, 241, 0.1);
            border: 1px solid rgba(99, 102, 241, 0.2);
            align-self: flex-end;
            border-bottom-right-radius: 2px;
        }

        .message-bubble.assistant {
            background: var(--bg-card);
            border: 1px solid var(--border);
            align-self: flex-start;
            border-bottom-left-radius: 2px;
        }

        .message-bubble pre {
            background: rgba(0,0,0,0.3);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            margin: 12px 0;
            overflow-x: auto;
            font-family: 'Fira Code', monospace;
            font-size: 0.85rem;
        }

        .message-bubble code {
            font-family: 'Fira Code', monospace;
            background: rgba(255, 255, 255, 0.05);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.85rem;
        }

        .message-bubble pre code {
            background: none;
            padding: 0;
            border-radius: 0;
        }

        /* Chat Input */
        .chat-input-area {
            padding: 20px 24px;
            border-top: 1px solid var(--border);
            display: flex;
            gap: 12px;
            background: rgba(17, 24, 39, 0.6);
        }

        .chat-input {
            flex: 1;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 18px;
            color: var(--text);
            font-family: inherit;
            font-size: 0.95rem;
            outline: none;
            resize: none;
            height: 54px;
            max-height: 150px;
            transition: border-color 0.2s;
        }

        .chat-input:focus {
            border-color: var(--primary);
        }

        /* Terminal Window */
        .terminal-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: #020617;
            padding: 20px;
            font-family: 'Fira Code', monospace;
            font-size: 0.9rem;
            color: #f8fafc;
        }

        .terminal-output {
            flex: 1;
            overflow-y: auto;
            white-space: pre-wrap;
            margin-bottom: 16px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .terminal-prompt {
            color: var(--cyan);
            font-weight: 600;
        }

        .terminal-input-wrapper {
            display: flex;
            align-items: center;
            gap: 8px;
            border-top: 1px solid #1e293b;
            padding-top: 12px;
        }

        .terminal-input {
            flex: 1;
            background: transparent;
            border: none;
            outline: none;
            color: #f8fafc;
            font-family: inherit;
            font-size: inherit;
        }

        /* Right Panel: KB & Agents */
        .right-panel {
            width: 320px;
            background: rgba(17, 24, 39, 0.5);
            border-left: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            padding: 20px;
            gap: 24px;
        }

        .kb-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .kb-stat {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
        }

        .agent-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .agent-item {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .agent-item:hover {
            border-color: var(--cyan);
            transform: translateY(-1px);
        }

        .agent-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
        }

        .agent-avatar {
            width: 28px;
            height: 28px;
            border-radius: 6px;
            background: linear-gradient(135deg, var(--cyan), var(--primary));
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            color: white;
            font-size: 0.75rem;
        }

        .agent-name {
            font-weight: 600;
            font-size: 0.9rem;
            color: var(--text-bright);
        }

        .agent-desc {
            font-size: 0.75rem;
            color: var(--text-muted);
            line-height: 1.5;
        }

        /* File List context */
        .file-list {
            display: flex;
            flex-direction: column;
            gap: 6px;
            max-height: 150px;
            overflow-y: auto;
            padding: 6px;
            background: rgba(0,0,0,0.1);
            border-radius: 8px;
        }

        .file-item {
            font-size: 0.75rem;
            font-family: 'Fira Code', monospace;
            padding: 4px 8px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Loader */
        .typing-loader {
            display: inline-flex;
            gap: 4px;
            align-items: center;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 10px;
            align-self: flex-start;
            margin-top: 10px;
        }

        .typing-dot {
            width: 6px;
            height: 6px;
            background: var(--text-muted);
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }

        .typing-dot:nth-child(1) { animation-delay: -0.32s; }
        .typing-dot:nth-child(2) { animation-delay: -0.16s; }

        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1.0); }
        }

        .hidden {
            display: none !important;
        }
    </style>
</head>
<body>

    <header>
        <div class="logo">&#x1F9E0; TermMind Console</div>
        <div class="header-stats">
            <div class="stat-badge">
                <span class="label">Session Cost:</span>
                <span class="value" id="badge-cost">$0.0000</span>
            </div>
            <div class="stat-badge">
                <span class="label">Tokens:</span>
                <span class="value" id="badge-tokens">0</span>
            </div>
            <div class="stat-badge">
                <span class="label">Workspace:</span>
                <span class="value" style="color: var(--text-bright);" id="badge-workspace">Loading...</span>
            </div>
        </div>
    </header>

    <div class="workspace">
        <!-- Left Sidebar: Config -->
        <div class="sidebar">
            <div class="sidebar-section">
                <h3>Settings</h3>
                <div class="form-group">
                    <label for="select-provider">Provider</label>
                    <select id="select-provider" class="form-control" onchange="updateProviderSettings()">
                        <option value="ollama">Ollama (Local)</option>
                        <option value="openai">OpenAI</option>
                        <option value="anthropic">Anthropic (Claude)</option>
                        <option value="gemini">Google Gemini</option>
                        <option value="groq">Groq</option>
                        <option value="mistral">Mistral AI</option>
                        <option value="cohere">Cohere</option>
                        <option value="together">Together AI</option>
                        <option value="openrouter">OpenRouter</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="select-model">Model</label>
                    <select id="select-model" class="form-control" onchange="saveConfigToServer()"></select>
                </div>
                <div class="form-group">
                    <label for="slider-temp">Temperature: <span id="val-temp">0.7</span></label>
                    <input type="range" id="slider-temp" min="0" max="1" step="0.1" value="0.7" class="form-control" style="padding:0;" oninput="document.getElementById('val-temp').innerText=this.value" onchange="saveConfigToServer()">
                </div>
            </div>

            <div class="sidebar-section">
                <h3>Active Context Files</h3>
                <div class="file-list" id="active-files-list">
                    <div class="file-item">No files in context</div>
                </div>
            </div>

            <div class="sidebar-section">
                <h3>Workspace Files</h3>
                <div style="display:flex; gap:6px; margin-bottom:8px;">
                    <input type="text" id="input-add-file" class="form-control" style="padding:6px 10px; font-size:0.8rem;" placeholder="Path to file...">
                    <button class="btn-action" style="padding:0 12px; font-size:0.8rem;" onclick="addFileFromInput()">Add</button>
                </div>
                <div class="file-list" id="workspace-files-list" style="max-height: 120px;">
                    <div class="file-item">Loading files...</div>
                </div>
            </div>

            <div class="sidebar-section">
                <h3>Session Actions</h3>
                <button class="btn-action btn-secondary" onclick="clearSession()">Clear Chat History</button>
            </div>
        </div>

        <!-- Center Window: Chat / Terminal -->
        <div class="content-area">
            <div class="tabs-header">
                <button class="tab-btn active" onclick="switchTab('tab-chat', this)">Interactive Chat</button>
                <button class="tab-btn" onclick="switchTab('tab-terminal', this)">Terminal Console</button>
            </div>

            <!-- Tab 1: Chat -->
            <div id="tab-chat" class="tab-content active">
                <div class="chat-messages" id="chat-scroller">
                    <div class="message-bubble assistant">
                        Hello! I am TermMind. Let's write some code, explore repositories, or run analysis. Ask me anything or switch tabs to execute CLI commands!
                    </div>
                </div>

                <div class="typing-loader hidden" id="chat-loader">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>

                <div class="chat-input-area">
                    <textarea class="chat-input" id="chat-prompt" placeholder="Ask a question or request a code refactoring (Shift+Enter for newline)..." onkeydown="handleChatSubmit(event)"></textarea>
                    <button class="btn-action" style="padding: 0 24px;" onclick="sendChatMessage()">Send</button>
                </div>
            </div>

            <!-- Tab 2: Terminal Console -->
            <div id="tab-terminal" class="tab-content">
                <div class="terminal-container">
                    <div class="terminal-output" id="terminal-scroller">
                        Welcome to TermMind Terminal Console.<br>
                        Execute slash commands (e.g., /git status, /scan ., /eli5 RAG) or regular shell commands.
                    </div>
                    <div class="terminal-input-wrapper">
                        <span class="terminal-prompt">termmind $</span>
                        <input type="text" class="terminal-input" id="terminal-command" placeholder="Enter command here..." onkeydown="handleTerminalSubmit(event)">
                    </div>
                </div>
            </div>
        </div>

        <!-- Right Sidebar: KB & Agents -->
        <div class="right-panel">
            <div class="sidebar-section">
                <h3>Knowledge Base (RAG)</h3>
                <div class="kb-card">
                    <div class="kb-stat">
                        <span class="label">Documents:</span>
                        <span class="value" id="kb-docs-count">0</span>
                    </div>
                    <div class="kb-stat">
                        <span class="label">Total Size:</span>
                        <span class="value" id="kb-docs-size">0 chars</span>
                    </div>
                    <div style="display:flex; flex-direction:column; gap:6px; margin-top:4px;">
                        <input type="text" id="input-kb-path" class="form-control" style="padding:6px 10px; font-size:0.8rem;" placeholder="Path to index (e.g. ./docs)...">
                        <button class="btn-action" style="padding:6px; font-size:0.8rem;" onclick="addPathToKb()">Index Directory / File</button>
                    </div>
                    <button class="btn-action btn-secondary" style="font-size:0.8rem; padding:6px; margin-top:4px;" onclick="refreshKbStats()">Refresh Stats</button>
                </div>
            </div>

            <div class="sidebar-section">
                <h3>Agent Personas</h3>
                <div class="agent-list" id="agents-container">
                    <!-- Loaded dynamically -->
                </div>
            </div>
        </div>
    </div>

    <script>
        let providerPresets = {};
        let activeProvider = "ollama";
        let activeModel = "";

        // Tab Switching
        function switchTab(tabId, el) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            
            document.getElementById(tabId).classList.add('active');
            el.classList.add('active');
            
            if (tabId === 'tab-terminal') {
                document.getElementById('terminal-command').focus();
            } else {
                document.getElementById('chat-prompt').focus();
            }
        }

        // Fetch server status & configuration
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                providerPresets = data.presets || {};
                activeProvider = data.config.provider || "ollama";
                activeModel = data.config.model || "";
                
                // Update UI elements
                document.getElementById('badge-cost').innerText = '$' + data.cost.toFixed(4);
                document.getElementById('badge-tokens').innerText = data.tokens;
                document.getElementById('badge-workspace').innerText = data.workspace;
                
                // Set form control values
                document.getElementById('select-provider').value = activeProvider;
                document.getElementById('slider-temp').value = data.config.temperature || 0.7;
                document.getElementById('val-temp').innerText = data.config.temperature || 0.7;
                
                populateModelDropdown();
                document.getElementById('select-model').value = activeModel;
                
                // Update files in context
                const filesList = document.getElementById('active-files-list');
                filesList.innerHTML = '';
                if (data.context_files && data.context_files.length > 0) {
                    data.context_files.forEach(f => {
                        const item = document.createElement('div');
                        item.className = 'file-item';
                        
                        const display_name = f.split('/').pop().split('\\\\').pop();
                        
                        const nameSpan = document.createElement('span');
                        nameSpan.innerText = display_name;
                        item.appendChild(nameSpan);
                        
                        const delSpan = document.createElement('span');
                        delSpan.innerHTML = '&times;';
                        delSpan.style.cursor = 'pointer';
                        delSpan.style.color = 'var(--red)';
                        delSpan.style.fontWeight = 'bold';
                        delSpan.style.fontSize = '1.1rem';
                        delSpan.onclick = () => removeFileFromContext(f);
                        item.appendChild(delSpan);
                        
                        item.title = f;
                        filesList.appendChild(item);
                    });
                } else {
                    filesList.innerHTML = '<div class="file-item" style="color:var(--text-muted)">No files in context</div>';
                }
            } catch (err) {
                console.error("Error fetching status:", err);
            }
        }

        // Populate model selector based on provider
        function populateModelDropdown() {
            const provider = document.getElementById('select-provider').value;
            const modelDropdown = document.getElementById('select-model');
            modelDropdown.innerHTML = '';
            
            const preset = providerPresets[provider];
            if (preset && preset.models) {
                preset.models.forEach(model => {
                    const opt = document.createElement('option');
                    opt.value = model;
                    opt.innerText = model;
                    modelDropdown.appendChild(opt);
                });
            }
        }

        // Handle provider dropdown change
        function updateProviderSettings() {
            populateModelDropdown();
            saveConfigToServer();
        }

        // Save active settings to backend
        async function saveConfigToServer() {
            const provider = document.getElementById('select-provider').value;
            const model = document.getElementById('select-model').value;
            const temperature = parseFloat(document.getElementById('slider-temp').value);
            
            try {
                await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ provider, model, temperature })
                });
                fetchStatus();
            } catch (err) {
                console.error("Error saving config:", err);
            }
        }

        // Fetch and render agent personas
        async function fetchAgents() {
            try {
                const res = await fetch('/api/agents');
                const agents = await res.json();
                
                const container = document.getElementById('agents-container');
                container.innerHTML = '';
                agents.forEach(agent => {
                    const card = document.createElement('div');
                    card.className = 'agent-item';
                    card.onclick = () => loadAgentChat(agent.name, agent.persona);
                    card.innerHTML = `
                        <div class="agent-header">
                            <div class="agent-avatar">${agent.name[0].toUpperCase()}</div>
                            <div class="agent-name">${agent.name.charAt(0).toUpperCase() + agent.name.slice(1)}</div>
                        </div>
                        <div class="agent-desc">${agent.description}</div>
                    `;
                    container.appendChild(card);
                });
            } catch (err) {
                console.error("Error fetching agents:", err);
            }
        }

        // Fetch Knowledge Base stats
        async function refreshKbStats() {
            try {
                const res = await fetch('/api/kb/stats');
                const data = await res.json();
                document.getElementById('kb-docs-count').innerText = data.documents;
                document.getElementById('kb-docs-size').innerText = data.total_size.toLocaleString() + ' chars';
            } catch (err) {
                console.error("Error fetching KB stats:", err);
            }
        }

        // Clear session messages on backend and reload
        async function clearSession() {
            if (confirm("Are you sure you want to clear session chat history?")) {
                try {
                    await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ action: "clear" })
                    });
                    const scroller = document.getElementById('chat-scroller');
                    scroller.innerHTML = `<div class="message-bubble assistant">Chat cleared. Ask me anything!</div>`;
                    fetchStatus();
                } catch (err) {
                    console.error("Error clearing chat:", err);
                }
            }
        }

        // Quick load agent into chat input
        function loadAgentChat(name, description) {
            document.getElementById('chat-prompt').value = `/agent chat ${name} `;
            switchTab('tab-chat', document.querySelectorAll('.tab-btn')[0]);
            document.getElementById('chat-prompt').focus();
        }

        // Chat submit handler
        function handleChatSubmit(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        }

        // Send Chat prompt
        async function sendChatMessage() {
            const textarea = document.getElementById('chat-prompt');
            const prompt = textarea.value.trim();
            if (!prompt) return;
            
            textarea.value = '';
            
            // Render user bubble
            appendChatBubble(prompt, 'user');
            
            // Show loader
            const loader = document.getElementById('chat-loader');
            loader.classList.remove('hidden');
            scrollToBottom('chat-scroller');
            
            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt })
                });
                const data = await res.json();
                
                loader.classList.add('hidden');
                
                if (data.error) {
                    appendChatBubble('Error: ' + data.error, 'assistant');
                } else {
                    appendChatBubble(data.content, 'assistant');
                }
                
                fetchStatus();
            } catch (err) {
                loader.classList.add('hidden');
                appendChatBubble('Failed to communicate with local server.', 'assistant');
            }
        }

        // Helper: append bubble
        function appendChatBubble(text, sender) {
            const scroller = document.getElementById('chat-scroller');
            const bubble = document.createElement('div');
            bubble.className = `message-bubble ${sender}`;
            
            // Basic markdown-like parser (fenced code, bold, inline code)
            let formatted = text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;");
                
            // Code blocks
            formatted = formatted.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, (match, lang, code) => {
                return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
            });
            
            // Inline code
            formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
            
            // Bold
            formatted = formatted.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
            
            // Newlines
            formatted = formatted.replace(/\\n/g, '<br>');
            
            bubble.innerHTML = formatted;
            scroller.appendChild(bubble);
            scrollToBottom('chat-scroller');
        }

        // Helper: Scroll container to bottom
        function scrollToBottom(id) {
            const el = document.getElementById(id);
            el.scrollTop = el.scrollHeight;
        }

        // Terminal Submit Handler
        function handleTerminalSubmit(e) {
            if (e.key === 'Enter') {
                runTerminalCommand();
            }
        }

        // Run command in Terminal view
        async function runTerminalCommand() {
            const input = document.getElementById('terminal-command');
            const command = input.value.trim();
            if (!command) return;
            
            input.value = '';
            
            const scroller = document.getElementById('terminal-scroller');
            scroller.innerHTML += `<br><span class="terminal-prompt">termmind $</span> ${command}<br><span style="color:var(--text-muted)">Running command...</span><br>`;
            scrollToBottom('terminal-scroller');
            
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command })
                });
                const data = await res.json();
                
                // Clean output (ansi stripping or rendering)
                let output = data.output;
                // Basic ANSI escapes strip
                output = output.replace(/\\x1B\\[[0-9;]*[a-zA-Z]/g, '');
                
                scroller.innerHTML += `<div>${output}</div>`;
                scrollToBottom('terminal-scroller');
                fetchStatus();
            } catch (err) {
                scroller.innerHTML += `<span style="color:var(--red)">Command failed to run. Connection error.</span><br>`;
                scrollToBottom('terminal-scroller');
            }
        }

        // Fetch workspace files list
        async function fetchWorkspaceFiles() {
            try {
                const res = await fetch('/api/files');
                const files = await res.json();
                const container = document.getElementById('workspace-files-list');
                container.innerHTML = '';
                if (files && files.length > 0) {
                    files.forEach(f => {
                        const item = document.createElement('div');
                        item.className = 'file-item';
                        
                        const nameSpan = document.createElement('span');
                        nameSpan.innerText = f;
                        item.appendChild(nameSpan);
                        
                        const addSpan = document.createElement('span');
                        addSpan.innerHTML = '+';
                        addSpan.style.cursor = 'pointer';
                        addSpan.style.color = 'var(--green)';
                        addSpan.style.fontWeight = 'bold';
                        addSpan.style.fontSize = '1.1rem';
                        addSpan.onclick = () => addFile(f);
                        item.appendChild(addSpan);
                        
                        item.title = f;
                        container.appendChild(item);
                    });
                } else {
                    container.innerHTML = '<div class="file-item" style="color:var(--text-muted)">No files found</div>';
                }
            } catch (err) {
                console.error("Error fetching workspace files:", err);
            }
        }

        // Add file to context
        async function addFile(f) {
            await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: `/add ${f}` })
            });
            fetchStatus();
        }

        // Add file from text input
        async function addFileFromInput() {
            const input = document.getElementById('input-add-file');
            const file = input.value.trim();
            if (!file) return;
            input.value = '';
            await addFile(file);
        }

        // Remove file from context
        async function removeFileFromContext(f) {
            await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: `/remove ${f}` })
            });
            fetchStatus();
        }

        // Index path to KB
        async function addPathToKb() {
            const input = document.getElementById('input-kb-path');
            const path = input.value.trim();
            if (!path) return;
            input.value = '';
            
            // Show status in terminal
            const scroller = document.getElementById('terminal-scroller');
            scroller.innerHTML += `<br><span class="terminal-prompt">termmind $</span> kb add ${path} --recursive<br><span style="color:var(--text-muted)">Indexing files to default collection...</span><br>`;
            scrollToBottom('terminal-scroller');
            
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: `/run termmind kb add ${path} --recursive` })
                });
                const data = await res.json();
                let output = data.output.replace(/\\x1B\\[[0-9;]*[a-zA-Z]/g, '');
                scroller.innerHTML += `<div>${output}</div>`;
                scrollToBottom('terminal-scroller');
                refreshKbStats();
            } catch (err) {
                scroller.innerHTML += `<span style="color:var(--red)">Failed to index path.</span><br>`;
                scrollToBottom('terminal-scroller');
            }
        }

        // Initialize UI
        window.onload = function() {
            fetchStatus();
            fetchAgents();
            refreshKbStats();
            fetchWorkspaceFiles();
            document.getElementById('chat-prompt').focus();
        };
    </script>
</body>
</html>
"""


class WebUIRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for TermMind Web UI."""

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress logging in terminal to avoid cluttering TermMind output
        pass

    def _send_json(self, data: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _send_html(self, html: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/", "/index.html"):
            self._send_html(HTML_CONTENT)
            return

        if path == "/api/status":
            cfg = load_config()
            self._send_json({
                "config": {
                    "provider": cfg.get("provider", "ollama"),
                    "model": cfg.get("model", ""),
                    "temperature": cfg.get("temperature", 0.7)
                },
                "presets": PROVIDER_PRESETS,
                "cost": session_cost,
                "tokens": session_tokens,
                "context_files": context_files,
                "workspace": os.getcwd()
            })
            return

        if path == "/api/agents":
            # List available personas based on agent personae
            self._send_json([
                {"name": "researcher", "description": "Researches codebases, queries docs, gathers context.", "persona": "Researcher"},
                {"name": "coder", "description": "Generates, edits, refactors code. Runs syntax checks.", "persona": "Coder"},
                {"name": "reviewer", "description": "Scans code for logic, style, and optimizations.", "persona": "Reviewer"},
                {"name": "writer", "description": "Drafts clear technical documentation, readmes, and changelogs.", "persona": "Writer"},
                {"name": "architect", "description": "Plans systems, designs file trees, selects libraries.", "persona": "Architect"}
            ])
            return

        if path == "/api/kb/stats":
            # Load default collection stats
            docs_count = 0
            docs_size = 0
            store_path = Path.home() / ".termmind" / "kb" / "default.json"
            if store_path.exists():
                try:
                    store = VectorStore(collection_name="default")
                    store.load(str(store_path))
                    docs_count = store.count()
                    for doc_id in store.list():
                        doc = store.get(doc_id)
                        if doc:
                            docs_size += len(doc.content)
                except Exception:
                    pass
            self._send_json({
                "documents": docs_count,
                "total_size": docs_size
            })
        if path == "/api/files":
            files = []
            cwd = os.getcwd()
            for root, dirs, filenames in os.walk(cwd):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "build", "dist", "node_modules", "venv", ".git")]
                for f in filenames:
                    if not f.startswith("."):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, cwd)
                        files.append(rel_path.replace("\\", "/"))
            self._send_json(files[:100])
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        global session_messages, session_cost, session_tokens

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        
        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except json.JSONDecodeError:
            body = {}

        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/config":
            cfg = load_config()
            if "provider" in body:
                cfg["provider"] = body["provider"]
                # Auto-select default model for the provider
                preset = PROVIDER_PRESETS.get(body["provider"])
                if preset:
                    cfg["model"] = preset["default_model"]
            if "model" in body and body["model"]:
                cfg["model"] = body["model"]
            if "temperature" in body:
                cfg["temperature"] = float(body["temperature"])
            
            save_config(cfg)
            self._send_json({"status": "success", "config": cfg})
            return

        if path == "/api/chat":
            if body.get("action") == "clear":
                session_messages = []
                self._send_json({"status": "cleared"})
                return

            prompt = body.get("prompt", "")
            if not prompt:
                self._send_json({"error": "Empty prompt"}, 400)
                return

            # Append user message
            session_messages.append({"role": "user", "content": prompt})

            try:
                cfg = load_config()
                client = APIClient(
                    provider=cfg.get("provider", "ollama"),
                    api_key=cfg.get("api_key", ""),
                    model=cfg.get("model", ""),
                    temperature=cfg.get("temperature", 0.7)
                )
                
                # Execute chat completion
                response = client.chat(session_messages)
                session_messages.append({"role": "assistant", "content": response})
                
                # Update usage
                session_cost += client.get_cost()
                session_tokens += client.total_tokens()

                self._send_json({
                    "content": response,
                    "tokens": session_tokens,
                    "cost": session_cost
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        if path == "/api/command":
            command_str = body.get("command", "")
            if not command_str:
                self._send_json({"error": "Empty command"}, 400)
                return

            try:
                # Strip slash if present
                clean_cmd = command_str[1:] if command_str.startswith("/") else command_str
                parts = clean_cmd.strip().split(maxsplit=1)
                cmd = parts[0] if parts else ""
                
                # Run the command and capture stdout formatted via rich console
                console = Console(color_system="truecolor", force_terminal=True, width=90)
                cfg = load_config()
                client = APIClient(
                    provider=cfg.get("provider", "ollama"),
                    api_key=cfg.get("api_key", ""),
                    model=cfg.get("model", "")
                )

                with console.capture() as capture:
                    try:
                        # Check if command is registered in TermMind slash handlers
                        handled = handle_command(
                            cmd,
                            clean_cmd,
                            session_messages,
                            client,
                            console,
                            os.getcwd(),
                            context_files
                        )
                        if not handled:
                            # Run as shell command directly
                            import subprocess
                            result = subprocess.run(
                                command_str,
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=20.0
                            )
                            if result.stdout:
                                console.print(result.stdout)
                            if result.stderr:
                                console.print(f"[red]{result.stderr}[/red]")
                    except Exception as err:
                        console.print(f"[red]Execution error: {err}[/red]")

                output = capture.get()
                self._send_json({"output": output})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
            return

        self.send_error(404, "Not Found")


def start_webui(port: int = 8080, open_browser: bool = True) -> None:
    """Start local Web UI TCPServer and open in browser."""
    # Use ThreadingTCPServer to avoid blocking the server during chat requests
    ThreadingTCPServer.allow_reuse_address = True
    
    max_attempts = 10
    server = None
    for attempt in range(max_attempts):
        try:
            server = ThreadingTCPServer(("127.0.0.1", port), WebUIRequestHandler)
            break
        except OSError:
            print(f"Port {port} is already in use. Trying port {port + 1}...")
            port += 1

    if server is None:
        print("Error: Could not find any open port for the Web UI server.")
        return

    print(f"==================================================")
    print(f"🚀 TermMind Web UI starting on http://localhost:{port}")
    print(f"==================================================")
    
    if open_browser:
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Web UI server...")
        server.server_close()
