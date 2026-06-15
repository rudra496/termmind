import { useState, useEffect, useRef } from 'react'
import './App.css'

interface Message {
  role: 'user' | 'agent' | 'system';
  content: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'system', content: 'TermMind Web UI v2 - Connected' },
    { role: 'agent', content: 'Hello! I am TermMind. How can I help you code today?' }
  ]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Connect to FastAPI WebSocket
    const ws = new WebSocket('ws://127.0.0.1:8000/ws');
    
    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'response') {
        setMessages(prev => [...prev, { role: 'agent', content: data.message }]);
      } else if (data.type === 'status') {
        // Handle thinking status if needed
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || !isConnected) return;

    const userMsg = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');

    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ message: userMsg }));
    }
  };

  return (
    <div className="ide-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>TermMind Explorer</h2>
        </div>
        <div className="file-tree">
          <div className="file-item folder">📁 termmind/</div>
          <div className="file-item">📄 api.py</div>
          <div className="file-item">📄 cli.py</div>
          <div className="file-item folder">📁 web/</div>
          <div className="file-item folder">📁 agents/</div>
        </div>
      </div>

      {/* Main Workspace */}
      <div className="main-workspace">
        <div className="workspace-header">
          <div className="tabs">
            <div className="tab active">💬 Chat</div>
            <div className="tab">📝 Editor</div>
          </div>
          <div className={`status ${isConnected ? 'online' : 'offline'}`}>
            {isConnected ? '🟢 Online' : '🔴 Offline'}
          </div>
        </div>

        {/* Chat Area */}
        <div className="chat-area">
          <div className="messages">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-wrapper ${msg.role}`}>
                <div className={`message-bubble ${msg.role}`}>
                  {msg.content}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask TermMind to build something..."
              disabled={!isConnected}
            />
            <button onClick={handleSend} disabled={!isConnected || !input.trim()}>
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
