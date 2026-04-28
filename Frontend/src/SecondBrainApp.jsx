import { useEffect, useState } from "react";
import axios from "axios";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const api = axios.create({
  baseURL: "http://localhost:8000/api",
});

const sidebarSections = [
  { id: "dashboard", label: "Dashboard" },
  { id: "chat", label: "Chat" },
  { id: "upload", label: "Upload" },
  { id: "study", label: "Study" },
  { id: "graph", label: "Graph" },
];

const railSections = [
  { id: "chat", label: "Chat", short: "C" },
  { id: "upload", label: "Upload", short: "U" },
  { id: "dashboard", label: "Analytics", short: "A" },
  { id: "study", label: "Study", short: "S" },
  { id: "graph", label: "Graph", short: "G" },
];

const quickActions = [
  { label: "Explain", buildPrompt: (text) => (text ? `Explain this clearly with simple steps:\n${text}` : "Explain the most important concept from my uploaded knowledge.") },
  { label: "Summary", buildPrompt: (text) => (text ? `Summarize this into clear bullet points:\n${text}` : "Summarize the most relevant knowledge I have uploaded.") },
  { label: "Revise", buildPrompt: (text) => (text ? `Give me revision notes for this topic:\n${text}` : "Give me revision notes from my uploaded material.") },
  { label: "Next", buildPrompt: () => "next" },
];

const starterPrompts = [
  "Explain this topic with a mini diagram.",
  "Summarize this chapter and show the flow.",
  "Compare two ideas with a simple visual map.",
  "Teach this step by step with an example.",
];

function TopicPill({ topic }) {
  return <span className="topic-pill">{topic || "General"}</span>;
}

function unwrapPayload(payload) {
  return payload?.data ?? payload;
}

function normalizeAssistantText(text) {
  const cleaned = String(text || "").trim();
  return cleaned || "I am here, but I could not form a complete answer yet. Try asking in a more specific way.";
}

function parseDiagramLines(lines) {
  return lines
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/^[-*]\s*/, ""));
}

function DiagramBlock({ lines }) {
  const cleanedLines = parseDiagramLines(lines);

  return (
    <div className="diagram-block">
      {cleanedLines.map((line, index) => {
        const flowParts = line.split("->").map((part) => part.trim()).filter(Boolean);

        if (flowParts.length > 1) {
          return (
            <div className="diagram-flow" key={`${line}-${index}`}>
              {flowParts.map((part, partIndex) => (
                <div className="diagram-flow-part" key={`${part}-${partIndex}`}>
                  <span className="diagram-node">{part}</span>
                  {partIndex < flowParts.length - 1 && <span className="diagram-arrow">â†’</span>}
                </div>
              ))}
            </div>
          );
        }

        return (
          <div className="diagram-line" key={`${line}-${index}`}>
            <span className="diagram-node">{line}</span>
          </div>
        );
      })}
    </div>
  );
}

function MessageBody({ text }) {
  const normalizedText = normalizeAssistantText(text);
  const blocks = normalizedText.split(/\n\s*\n/).filter(Boolean);
  const sectionLabels = new Set([
    "direct answer",
    "main explanation",
    "key points",
    "example",
    "short summary",
    "formula / concept",
    "step-by-step solution",
    "mini diagram",
    "final result",
    "short intuition",
    "question focus",
  ]);

  return (
    <div className="message-body">
      {blocks.map((block, index) => {
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        const listLike = lines.length > 1 && lines.every((line) => /^([-*]|\d+\.)\s/.test(line));

        if (listLike) {
          return (
            <ul className="message-list" key={`${block.slice(0, 20)}-${index}`}>
              {lines.map((line) => (
                <li key={line}>{line.replace(/^([-*]|\d+\.)\s/, "")}</li>
              ))}
            </ul>
          );
        }

        if (lines.length === 1 && sectionLabels.has(lines[0].replace(/:$/, "").toLowerCase())) {
          return <h4 className="message-section-title" key={`${block.slice(0, 20)}-${index}`}>{lines[0]}</h4>;
        }

        if (lines.length > 1 && lines[0].replace(/:$/, "").toLowerCase() === "mini diagram") {
          return <DiagramBlock key={`${block.slice(0, 20)}-${index}`} lines={lines.slice(1)} />;
        }

        return <p key={`${block.slice(0, 20)}-${index}`}>{block}</p>;
      })}
    </div>
  );
}

export default function SecondBrainApp() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [activeSection, setActiveSection] = useState("chat");
  const [questionLoading, setQuestionLoading] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [analytics, setAnalytics] = useState({
    total_questions: 0,
    documents_uploaded: 0,
    due_flashcards: 0,
    topics: {},
    study_recommendations: { weak_topics: [], recommendation: "" },
    recent_documents: [],
    system_status: { ready: false, warnings: [] },
  });
  const [pdfFile, setPdfFile] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [flashcards, setFlashcards] = useState([]);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [statusMessage, setStatusMessage] = useState("");
  const [language, setLanguage] = useState("english");
  const [theme, setTheme] = useState("dark");
  const [uploadStatus, setUploadStatus] = useState("Ready");
  const [currentDocument, setCurrentDocument] = useState(null);

  const topicData = Object.entries(analytics.topics || {}).map(([topic, count]) => ({
    topic,
    count,
  }));
  const systemStatus = analytics.system_status || { ready: false, warnings: [] };
  const recentDocuments = analytics.recent_documents || [];
  const statCards = [
    { key: "total_questions", label: "Questions Asked", value: analytics.total_questions ?? 0 },
    { key: "tracked_topics", label: "Tracked Topics", value: topicData.length },
    { key: "documents_uploaded", label: "Documents Indexed", value: analytics.documents_uploaded ?? 0 },
  ];

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const sections = sidebarSections
      .map((section) => document.getElementById(section.id))
      .filter(Boolean);

    if (!sections.length) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];

        if (visible?.target?.id) {
          setActiveSection(visible.target.id);
        }
      },
      { rootMargin: "-20% 0px -55% 0px", threshold: [0.2, 0.5, 0.8] },
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  const loadSidebarData = async () => {
    try {
      const [analyticsRes, dueFlashcardsRes, graphRes] = await Promise.all([
        api.get("/analytics"),
        api.get("/study/flashcards/due"),
        api.get("/graph"),
      ]);

      setAnalytics(unwrapPayload(analyticsRes.data));
      setFlashcards(unwrapPayload(dueFlashcardsRes.data).flashcards || dueFlashcardsRes.data.flashcards || []);
      setGraph(unwrapPayload(graphRes.data) || { nodes: [], edges: [] });
      const latestDocument = unwrapPayload(analyticsRes.data)?.recent_documents?.[0];
      if (latestDocument) {
        setCurrentDocument({ id: latestDocument.id, title: latestDocument.title });
      }
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Failed to load dashboard data.");
    }
  };

  const refreshSidebarInBackground = async () => {
    try {
      await loadSidebarData();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Uploaded successfully, but dashboard refresh is still catching up.");
    }
  };

  const loadDashboard = async () => {
    setDashboardLoading(true);
    try {
      const historyRes = await api.get("/history");
      const historyPayload = unwrapPayload(historyRes.data);
      setMessages(historyPayload.messages || historyRes.data.messages || []);
      await loadSidebarData();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Failed to load dashboard data.");
    } finally {
      setDashboardLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const askQuestion = async (questionOverride) => {
    const currentQuestion = (questionOverride ?? input).trim();
    if (!currentQuestion) return;

    setMessages((prev) => [...prev, { role: "user", text: currentQuestion }]);
    setInput("");
    setQuestionLoading(true);
    setStatusMessage("");

    try {
      const response = await api.post("/ask", {
        question: currentQuestion,
        source: "all",
        language,
        document_id: currentDocument?.id ?? null,
      });
      const answerPayload = unwrapPayload(response.data);
      const safeAnswer = normalizeAssistantText(answerPayload.answer);
      if (answerPayload.document_id) {
        setCurrentDocument({
          id: answerPayload.document_id,
          title: answerPayload.document_title || currentDocument?.title || "active document",
        });
      }
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: safeAnswer,
          topic: answerPayload.topic,
          sources: answerPayload.sources || [],
          language: answerPayload.language,
          documentId: answerPayload.document_id,
          documentTitle: answerPayload.document_title,
        },
      ]);
      await loadSidebarData();
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: error.response?.data?.detail || "The assistant could not answer right now.",
          topic: "System",
        },
      ]);
    } finally {
      setQuestionLoading(false);
    }
  };

  const runQuickAction = (action) => {
    const prompt = action.buildPrompt(input.trim());
    setInput(prompt);
    if (action.label === "Next") {
      askQuestion(prompt);
    }
  };

  const clearHistory = async () => {
    try {
      await api.delete("/history");
      setMessages([]);
      await loadDashboard();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Unable to clear chat history.");
    }
  };

  const uploadPdf = async () => {
    if (!pdfFile) return;

    const formData = new FormData();
    formData.append("file", pdfFile);
    setUploadLoading(true);
    setUploadStatus("Indexing PDF...");
    setStatusMessage("");

    try {
      const response = await api.post("/upload-pdf", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      const payload = unwrapPayload(response.data);
      setStatusMessage(`Indexed PDF: ${payload.title || response.data.title || "uploaded document"}`);
      setCurrentDocument({ id: payload.document_id, title: payload.title || response.data.title || "uploaded document" });
      setPdfFile(null);
      setUploadLoading(false);
      setUploadStatus("Refreshing dashboard...");
      void refreshSidebarInBackground().finally(() => setUploadStatus("Ready"));
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "PDF upload failed.");
      setUploadStatus("Ready");
    } finally {
      setUploadLoading(false);
    }
  };

  const uploadYoutube = async () => {
    if (!youtubeUrl.trim()) return;

    setUploadLoading(true);
    setUploadStatus("Indexing YouTube...");
    setStatusMessage("");

    try {
      const response = await api.post("/upload-youtube", { url: youtubeUrl.trim() }, { timeout: 120000 });
      const payload = unwrapPayload(response.data);
      setStatusMessage(`Indexed YouTube source: ${payload.title || response.data.title || youtubeUrl.trim()}`);
      setCurrentDocument({ id: payload.document_id, title: payload.title || response.data.title || youtubeUrl.trim() });
      setYoutubeUrl("");
      setUploadLoading(false);
      setUploadStatus("Refreshing dashboard...");
      void refreshSidebarInBackground().finally(() => setUploadStatus("Ready"));
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "YouTube ingestion failed.");
      setUploadStatus("Ready");
    } finally {
      setUploadLoading(false);
    }
  };

  const uploadImage = async () => {
    if (!imageFile) return;

    const formData = new FormData();
    formData.append("file", imageFile);
    setUploadLoading(true);
    setUploadStatus("Running OCR...");
    setStatusMessage("");

    try {
      const response = await api.post("/upload-image", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      const payload = unwrapPayload(response.data);
      if (payload.warning || response.data.warning) {
        setStatusMessage(payload.warning || response.data.warning);
      } else if (payload.text || response.data.text) {
        setStatusMessage(`OCR done. Extracted text preview: ${(payload.text || response.data.text).slice(0, 140)}`);
      } else if (payload.text_preview || response.data.text_preview) {
        setStatusMessage(`Image indexed. OCR preview: ${(payload.text_preview || response.data.text_preview).slice(0, 140)}`);
      } else {
        setStatusMessage("Image processed, but no readable text was found.");
      }
      setCurrentDocument({ id: payload.document_id, title: payload.title || response.data.title || "uploaded image" });
      setImageFile(null);
      setUploadLoading(false);
      setUploadStatus("Refreshing dashboard...");
      void refreshSidebarInBackground().finally(() => setUploadStatus("Ready"));
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Image upload failed.");
      setUploadStatus("Ready");
    } finally {
      setUploadLoading(false);
    }
  };

  const generateFlashcards = async () => {
    try {
      const response = await api.post("/study/flashcards", { limit: 5 });
      const payload = unwrapPayload(response.data);
      setFlashcards(payload.flashcards || response.data.flashcards || []);
      setStatusMessage("Generated new flashcards. They are scheduled for review instead of becoming due immediately.");
      await loadDashboard();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Could not generate flashcards.");
    }
  };

  const reviewFlashcard = async (cardId, quality) => {
    try {
      await api.post(`/study/flashcards/${cardId}/review`, { quality });
      await loadDashboard();
    } catch (error) {
      setStatusMessage(error.response?.data?.detail || "Could not review the flashcard.");
    }
  };

  const handleEnter = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      askQuestion();
    }
  };

  return (
    <div className="app-shell app-root">
      <div className="app-layout">
        <aside className="rail-panel">
          <div className="rail-brand">SB</div>
          <div className="rail-stack">
            {railSections.map((section) => (
              <a
                className={`rail-link ${activeSection === section.id ? "active" : ""}`}
                href={`#${section.id}`}
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                title={section.label}
              >
                <span className="rail-badge">{section.short}</span>
                <small>{section.label}</small>
              </a>
            ))}
          </div>
          <button className="rail-profile" onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}>
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </aside>

        <aside className="glass-panel sidebar-panel" id="dashboard">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Workspace</p>
              <h1 className="panel-title">Second Brain AI</h1>
            </div>
            <div className="header-actions">
              <button className="ghost-button" onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}>
                {theme === "dark" ? "Light" : "Dark"}
              </button>
              <button className="ghost-button" onClick={clearHistory}>
                Clear Chat
              </button>
            </div>
          </div>

          <nav className="section-nav">
            {sidebarSections.map((section) => (
              <a
                className={`nav-link ${activeSection === section.id ? "active" : ""}`}
                href={`#${section.id}`}
                key={section.id}
                onClick={() => setActiveSection(section.id)}
              >
                {section.label}
              </a>
            ))}
          </nav>

          <div className="section-block section-block-tight">
            <div className="section-head">
              <h2>Response Mode</h2>
              <span>{language === "hinglish" ? "Hinglish" : "English"}</span>
            </div>
            <div className="toggle-row">
              <button
                className={`toggle-chip ${language === "english" ? "active" : ""}`}
                onClick={() => setLanguage("english")}
              >
                English
              </button>
              <button
                className={`toggle-chip ${language === "hinglish" ? "active" : ""}`}
                onClick={() => setLanguage("hinglish")}
              >
                Hinglish
              </button>
            </div>
          </div>

          <div className={`section-block section-block-tight status-panel ${systemStatus.ready ? "status-ok" : "status-warning"}`}>
            <div className="section-head">
              <h2>System Status</h2>
              <span>{systemStatus.ready ? "Ready" : "Needs Setup"}</span>
            </div>
            <p className="section-copy">
              {systemStatus.ready
                ? "Core services look ready for normal usage."
                : "Some dependencies or environment variables still need setup before the product runs at full quality."}
            </p>
            {(systemStatus.warnings || []).length > 0 && (
              <div className="warning-list">
                {systemStatus.warnings.slice(0, 4).map((warning) => (
                  <p className="warning-item" key={warning}>{warning}</p>
                ))}
              </div>
            )}
          </div>

          <div className="stats-grid">
            {statCards.map((card) => (
              <div className="stat-card" key={card.key}>
                <p className="stat-label">{card.label}</p>
                <p className="stat-value">
                  {dashboardLoading ? "..." : card.value}
                </p>
              </div>
            ))}
          </div>

          <div className="section-block" id="upload">
            <div className="section-head">
              <h2>Ingestion</h2>
              <span>{uploadLoading ? uploadStatus : uploadStatus}</span>
            </div>
            {currentDocument && (
              <p className="section-copy">
                Active source: <strong>{currentDocument.title}</strong>
              </p>
            )}

            <label className="upload-field">
              <span>Upload PDF</span>
              <input
                type="file"
                accept="application/pdf"
                onChange={(event) => setPdfFile(event.target.files?.[0] || null)}
              />
            </label>
            <button className="primary-button" onClick={uploadPdf} disabled={!pdfFile || uploadLoading}>
              Index PDF
            </button>

            <label className="upload-field">
              <span>Upload Image for OCR</span>
              <input
                type="file"
                accept="image/*"
                onChange={(event) => setImageFile(event.target.files?.[0] || null)}
              />
            </label>
            <button className="secondary-button" onClick={uploadImage} disabled={!imageFile || uploadLoading}>
              Extract Text
            </button>

            <label className="upload-field">
              <span>YouTube URL</span>
              <input
                value={youtubeUrl}
                onChange={(event) => setYoutubeUrl(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
              />
            </label>
            <button className="secondary-button" onClick={uploadYoutube} disabled={!youtubeUrl.trim() || uploadLoading}>
              Index YouTube
            </button>
          </div>

          <div className="section-block" id="study">
            <div className="section-head">
              <h2>Study Mode</h2>
              <button className="ghost-button" onClick={generateFlashcards}>
                Generate
              </button>
            </div>
            <p className="section-copy">
              {analytics.study_recommendations?.recommendation ||
                "Ask questions and upload more study material to unlock recommendations."}
            </p>
            <div className="topic-row">
              {(analytics.study_recommendations?.weak_topics || []).map((topic) => (
                <TopicPill topic={topic} key={topic} />
              ))}
            </div>
          </div>

          <div className="section-block" id="graph">
            <div className="section-head">
              <h2>Knowledge Graph</h2>
              <span>{graph.nodes.length} nodes</span>
            </div>
            <div className="graph-preview">
              {graph.nodes.slice(0, 8).map((node) => (
                <div className="graph-node" key={node.id}>
                  <span>{node.name}</span>
                  <small>{node.weight}</small>
                </div>
              ))}
            </div>
          </div>

          <div className="section-block">
            <div className="section-head">
              <h2>Recent Sources</h2>
              <span>{recentDocuments.length}</span>
            </div>
            <div className="document-list">
              {recentDocuments.length === 0 && (
                <p className="section-copy">Indexed sources will appear here after uploads.</p>
              )}
              {recentDocuments.slice(0, 6).map((document) => (
                <div className="document-item" key={`${document.id}-${document.title}`}>
                  <div>
                    <p className="document-title">{document.title}</p>
                    <p className="document-meta">{document.source_type} | {document.topic}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>

        <main className="main-layout">
          <section className="glass-panel chat-panel" id="chat">
            <div className="chat-hero">
              <div className="chat-hero-copy">
                <p className="eyebrow">AI Knowledge Engine</p>
                <h2 className="panel-title">Ask across your notes, videos, and memory</h2>
                <p className="section-copy">
                  A focused workspace for explanation, summarization, revision, and guided study.
                </p>
              </div>
              <div className="chat-hero-status">
                <div className="hero-status-card">
                  <span className="status-dot" />
                  <div>
                    <strong>{questionLoading ? "Thinking..." : "Ready"}</strong>
                    <p>{language === "hinglish" ? "Hinglish mode enabled" : "English mode enabled"}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="quick-actions">
              {quickActions.map((action) => (
                <button
                  className="quick-action-button"
                  key={action.label}
                  onClick={() => runQuickAction(action)}
                  disabled={questionLoading}
                >
                  {action.label}
                </button>
              ))}
            </div>

            <div className="chat-feed">
              {messages.length === 0 && (
                <div className="empty-state">
                  <p className="empty-title">Your knowledge workspace is ready.</p>
                  <p className="empty-copy">
                    Upload a PDF or YouTube transcript, then ask for summaries, explanations, or revision help.
                  </p>
                  <div className="starter-grid">
                    {starterPrompts.map((prompt) => (
                      <button
                        className="starter-card"
                        key={prompt}
                        onClick={() => setInput(prompt)}
                        type="button"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((message, index) => (
                <div className={`message-shell ${message.role}`} key={`${message.role}-${index}`}>
                  <div className="message-card">
                    <MessageBody text={message.text} />
                  </div>
                  {message.role === "assistant" && (
                    <div className="message-meta">
                      <TopicPill topic={message.topic} />
                      <span className="source-chip">
                        {message.language === "hinglish" ? "Hinglish" : "English"}
                      </span>
                      {(message.sources || []).slice(0, 2).map((source) => (
                        <span className="source-chip" key={`${source.chunk_id}-${source.score}`}>
                          Source: {source.metadata?.title || source.metadata?.source_type}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {questionLoading && (
                <div className="message-shell assistant">
                  <div className="message-card thinking-card">
                    <div className="thinking-dots" aria-label="Thinking">
                      <span />
                      <span />
                      <span />
                    </div>
                    <p className="thinking-text">{language === "hinglish" ? "Soch raha hoon..." : "Thinking through your context..."}</p>
                  </div>
                </div>
              )}
            </div>

            <div className="composer">
              <textarea
                className="composer-input"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleEnter}
                placeholder={
                  language === "hinglish"
                    ? "Koi concept poochho, summary maango, ya revision help lo..."
                    : "Ask a concept, request a summary, or generate revision help..."
                }
              />
              <button className="primary-button composer-button" onClick={askQuestion} disabled={questionLoading || !input.trim()}>
                {language === "hinglish" ? "Poochho" : "Send"}
              </button>
            </div>
            {statusMessage && <p className="status-text">{statusMessage}</p>}
          </section>

          <section className="bottom-grid">
            <div className="glass-panel">
              <div className="section-head">
                <h2>Topic Analytics</h2>
                <span>{topicData.length} tracked topics</span>
              </div>
              <div className="chart-grid">
                <div className="chart-card">
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={topicData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#314158" />
                      <XAxis dataKey="topic" stroke="#9db4d2" />
                      <YAxis stroke="#9db4d2" />
                      <Tooltip />
                      <Bar dataKey="count" fill="#3dd9b6" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="chart-card">
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Pie data={topicData} dataKey="count" nameKey="topic" outerRadius={80} fill="#8fd3ff" />
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <div className="glass-panel">
              <div className="section-head">
                <h2>Due Flashcards</h2>
                <span>{flashcards.length}</span>
              </div>
              <div className="flashcard-list">
                {flashcards.length === 0 && <p className="section-copy">No flashcards are due right now.</p>}
                {flashcards.map((card) => (
                  <div className="flashcard" key={card.id}>
                    <TopicPill topic={card.topic} />
                    <p className="flashcard-question">{card.question}</p>
                    <p className="flashcard-answer">{card.answer}</p>
                    <div className="flashcard-actions">
                      <button className="ghost-button" onClick={() => reviewFlashcard(card.id, 2)}>
                        Hard
                      </button>
                      <button className="ghost-button" onClick={() => reviewFlashcard(card.id, 4)}>
                        Good
                      </button>
                      <button className="ghost-button" onClick={() => reviewFlashcard(card.id, 5)}>
                        Easy
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

