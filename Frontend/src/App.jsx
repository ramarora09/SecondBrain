import { useState, useEffect } from "react";
import axios from "axios";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [analytics, setAnalytics] = useState(null);

  // 🔥 FETCH ANALYTICS
  const fetchAnalytics = async () => {
    try {
      const res = await axios.get("/api/analytics");
      setAnalytics(res.data);
    } catch (err) {
      console.log("Analytics error");
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await axios.get("/api/history");
      setMessages(res.data.messages || []);
    } catch (err) {
      console.log("History error");
    }
  };

  useEffect(() => {
    fetchAnalytics();
    fetchHistory();
  }, []);

  const clearHistory = async () => {
    try {
      await axios.delete("/api/history");
      setMessages([]);
    } catch (err) {
      console.log("Clear history error");
    }
  };

  // 🔥 SEND MESSAGE
  const sendMessage = async () => {
    if (!input) return;

    const userMsg = { role: "user", text: input };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await axios.get(
        `/api/ask?q=${encodeURIComponent(input)}`
      );

      const botMsg = {
        role: "assistant",
        text: res.data.answer || "No response",
        topic: res.data.topic || "General",
      };

      setMessages((prev) => [...prev, botMsg]);

      // 🔥 refresh analytics after question
      fetchAnalytics();

    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Error ❌" },
      ]);
    }

    setInput("");
    setLoading(false);
  };

  return (
    <div className="h-screen bg-[#0f172a] text-white flex">

      {/* 🔥 SIDEBAR (Analytics) */}
      <div className="w-64 bg-[#020617] border-r border-gray-800 p-4">
        <h2 className="text-lg font-bold mb-4">📊 Analytics</h2>

        {analytics ? (
          <>
            <p className="text-sm mb-2">
              Questions: {analytics.questions}
            </p>

            <div>
              <h3 className="text-sm font-semibold mb-1">Topics</h3>
              {Object.entries(analytics.topics).map(([topic, val]) => (
                <div key={topic} className="text-xs mb-1">
                  {topic}: {val}
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-gray-400 text-sm">Loading...</p>
        )}
      </div>

      {/* 🔥 MAIN CHAT */}
      <div className="flex-1 flex flex-col">

        {/* Header */}
        <div className="p-4 border-b border-gray-700 text-xl font-bold flex justify-between">
          🧠 Second Brain AI
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-400">
              AI Knowledge Engine
            </span>

            <button
              onClick={clearHistory}
              className="text-xs px-3 py-1 rounded bg-gray-800 hover:bg-gray-700"
            >
              Clear Chat
            </button>
          </div>
        </div>

        {/* Chat */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((msg, i) => (
            <div key={i}>

              <div
                className={`max-w-[70%] p-3 rounded ${
                  msg.role === "user"
                    ? "bg-blue-600 ml-auto"
                    : "bg-gray-700"
                }`}
              >
                {msg.text}
              </div>

              {/* 🔥 Show topic tag */}
              {msg.role === "assistant" && (
                <p className="text-xs text-gray-400 mt-1">
                  Topic: {msg.topic}
                </p>
              )}
            </div>
          ))}

          {loading && (
            <p className="text-gray-400 animate-pulse">
              🤖 Thinking...
            </p>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-700 flex gap-2">
          <input
            className="flex-1 p-3 rounded bg-gray-800 outline-none"
            placeholder="Ask anything..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />

          <button
            onClick={sendMessage}
            className="bg-blue-600 px-4 rounded hover:bg-blue-700"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
